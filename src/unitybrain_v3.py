import subprocess
#!/usr/bin/env python3
"""
🌐 UNITYBRAIN v3.3 - RÉSEAU P2P DISTRIBUTÉ
Evolution from v3.2:
- JWT token auth with rotation (replaces HMAC)
- Real-time WebSocket memory sync
- Dynamic peer discovery (Tailscale + mDNS + config fallback)
- Intelligent load balancing (latency, CPU, memory)
- Circuit breaker pattern
- System monitoring (psutil)
- Auto-heal (Ollama restart)
- Health dashboard
"""

import asyncio
import aiohttp
from aiohttp import web
import json
import time
import socket
import hashlib
import hmac
import os
import base64
import uuid
import psutil
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import deque
from pathlib import Path
import logging.handlers
try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

# Modular imports (extracted classes)
try:
    from auth import CircuitBreaker, TokenAuth
    from discovery import PeerDiscovery, Peer
    from balancing import LoadBalancer
    from models import ModelRouter, EnsembleConsensus, QueryHistory
    from monitoring import DistributedMemory
    _MODULAR = True
except ImportError:
    _MODULAR = False

# File logging + console
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger('UnityBrain')
file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "unitybrain.log", maxBytes=5*1024*1024, backupCount=3
)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s'))
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


# ============================================================================
# ============== CIRCUIT BREAKER ==========================================
# ============================================================================

class CircuitBreaker:
    """Circuit breaker pattern for peer failover protection"""
    STATE_CLOSED = "closed"      # Normal operation
    STATE_OPEN = "open"          # Failing, reject calls
    STATE_HALF_OPEN = "half_open"  # Testing if recovered

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60,
                 half_open_max: int = 1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        if self.state == self.STATE_CLOSED:
            return True
        if self.state == self.STATE_OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.STATE_HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker: OPEN → HALF_OPEN")
                return True
            return False
        if self.state == self.STATE_HALF_OPEN:
            if self.half_open_calls < self.half_open_max:
                self.half_open_calls += 1
                return True
            return False
        return False

    def record_success(self):
        if self.state == self.STATE_HALF_OPEN:
            self.success_count += 1
            self.state = self.STATE_CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker: HALF_OPEN → CLOSED (recovered)")
        else:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.STATE_OPEN
            logger.warning(f"Circuit breaker: CLOSED → OPEN ({self.failure_count} failures)")

    @property
    def is_available(self) -> bool:
        return self.can_execute()

    def to_dict(self) -> Dict:
        return {
            "state": self.state,
            "failures": self.failure_count,
            "last_failure": self.last_failure_time
        }


# ============================================================================
# ============== JWT TOKEN AUTH (Point 1) ==================================
# ============================================================================

class TokenAuth:
    """JWT-based token auth with rotation for P2P security.
    Replaces simple HMAC with:
    - Signed JWT tokens (HS256 or Ed25519)
    - Automatic token rotation every N hours
    - Token blacklist for revocation
    - Fallback to HMAC for v3.2 compatibility
    """
    
    def __init__(self, secret: str, token_lifetime: int = 86400,
                 rotation_interval: int = 3600):
        self.secret = secret.encode() if isinstance(secret, str) else secret
        self.token_lifetime = token_lifetime  # 24h default
        self.rotation_interval = rotation_interval  # Rotate signing key every hour
        self.current_key_id = str(uuid.uuid4())[:8]
        self.key_history: deque = deque(maxlen=5)  # Keep last 5 keys for validation
        self.blacklisted_tokens: set = set()
        self.key_history.append({
            'key_id': self.current_key_id,
            'secret': self.secret,
            'created': time.time()
        })
        self.last_rotation = time.time()
    
    def _check_rotation(self):
        """Rotate signing key if interval exceeded"""
        if time.time() - self.last_rotation >= self.rotation_interval:
            old_key_id = self.current_key_id
            self.current_key_id = str(uuid.uuid4())[:8]
            new_secret = f"{self.secret.decode()}-{self.current_key_id}".encode()
            self.key_history.append({
                'key_id': self.current_key_id,
                'secret': new_secret,
                'created': time.time()
            })
            self.secret = new_secret
            self.last_rotation = time.time()
            logger.info(f"🔑 Token key rotated: {old_key_id} → {self.current_key_id}")
    
    def generate_token(self, node_name: str, scopes: List[str] = None) -> str:
        """Generate a JWT token for a peer"""
        self._check_rotation()
        now = time.time()
        payload = {
            'sub': node_name,
            'iat': now,
            'exp': now + self.token_lifetime,
            'kid': self.current_key_id,
            'scopes': scopes or ['query', 'sync', 'ping']
        }
        if HAS_JWT:
            token = jwt.encode(payload, self.secret, algorithm='HS256')
        else:
            # Fallback: base64-encoded payload + HMAC signature
            payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
            sig = hmac.new(self.secret, payload_b64.encode(), hashlib.sha256).hexdigest()
            token = f"{payload_b64}.{sig}"
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify a JWT token. Returns payload if valid, None otherwise."""
        if token in self.blacklisted_tokens:
            return None
        
        # Try current key first, then history
        for key_entry in reversed(list(self.key_history)):
            try:
                if HAS_JWT:
                    payload = jwt.decode(token, key_entry['secret'], 
                                        algorithms=['HS256'],
                                        options={'require': ['exp', 'sub']})
                else:
                    # Fallback verification
                    parts = token.split('.')
                    if len(parts) != 2:
                        continue
                    payload_b64, sig = parts
                    expected_sig = hmac.new(key_entry['secret'], 
                                           payload_b64.encode(), 
                                           hashlib.sha256).hexdigest()
                    if not hmac.compare_digest(sig, expected_sig):
                        continue
                    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                    
                # Check expiry
                if payload.get('exp', 0) < time.time():
                    continue
                return payload
            except (ValueError, KeyError):
                continue
        return None
    
    def revoke_token(self, token: str):
        """Blacklist a token"""
        self.blacklisted_tokens.add(token)
    
    def auth_headers(self, node_name: str, path: str) -> Dict[str, str]:
        """Generate auth headers for outgoing requests"""
        token = self.generate_token(node_name)
        return {
            'Authorization': f'Bearer {token}',
            'X-UnityBrain-Version': '3.3.0'
        }
    
    def verify_request(self, request: web.Request, secret: str = None) -> Optional[Dict]:
        """Verify an incoming request's auth. Returns payload or None."""
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
            payload = self.verify_token(token)
            if payload:
                return payload
            # JWT failed — fall through to HMAC below
        # Fallback: verify legacy HMAC headers for v3.2 compat
        hmac_auth = request.headers.get('X-UnityBrain-Auth', '')
        hmac_ts = request.headers.get('X-UnityBrain-TS', '')
        if hmac_auth and hmac_ts and secret:
            try:
                ts = float(hmac_ts)
                if abs(time.time() - ts) > 300:
                    return None
                # Use request.path for consistent signing (not full URL which varies by host)
                path = request.path
                msg = f"{path}:{hmac_ts}"
                expected = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
                if hmac.compare_digest(hmac_auth, expected):
                    return {'sub': 'legacy', 'scopes': ['query', 'sync', 'ping']}
            except (ValueError, TypeError):
                return None
        return None


# ============================================================================
# ============== DYNAMIC DISCOVERY (Point 3) ================================
# ============================================================================

class PeerDiscovery:
    """Dynamic peer discovery via multiple mechanisms:
    1. Tailscale status API
    2. mDNS broadcast on local network
    3. Config file fallback (v3.2 compat)
    4. Peer referral (learn about new peers from existing ones)
    """
    
    def __init__(self, node_name: str, own_host: str, own_port: int,
                 config_peers: List[Dict] = None):
        self.node_name = node_name
        self.own_host = own_host
        self.own_port = own_port
        self.known_peers: Dict[str, Dict] = {}  # host:port → peer info
        self.config_peers = config_peers or []
        self.last_discovery = 0
        self.discovery_interval = 300  # Re-discover every 5 min
    
    async def discover_all(self) -> List[Dict]:
        """Run all discovery mechanisms and return found peers"""
        found = {}
        now = time.time()
        
        # 1. Config file peers (always checked)
        for p in self.config_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            found[key] = p
        
        # 2. Tailscale discovery
        ts_peers = await self._discover_tailscale()
        for p in ts_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            if key not in found:
                found[key] = p
        
        # 3. mDNS discovery
        mdns_peers = await self._discover_mdns()
        for p in mdns_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            if key not in found:
                found[key] = p
        
        # 4. Peer referral
        referral_peers = await self._discover_referrals()
        for p in referral_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            if key not in found:
                found[key] = p
        
        self.known_peers = found
        self.last_discovery = now
        logger.info(f"Discovery: found {len(found)} potential peers")
        return list(found.values())
    
    async def _discover_tailscale(self) -> List[Dict]:
        """Discover peers via Tailscale status API"""
        peers = []
        try:
            proc = await asyncio.create_subprocess_exec(
                'tailscale', 'status', '--json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode == 0:
                status = json.loads(stdout)
                for peer in status.get('Peer', {}).values():
                    if peer.get('Online', False):
                        ips = peer.get('TailscaleIPs', [])
                        # Skip self: check by hostname OR by IP matching our Tailscale IP
                        if peer.get('HostName') == self.node_name:
                            continue
                        # Also skip if this peer's IP is our own
                        own_ts_ip = status.get('Self', {}).get('TailscaleIPs', [])
                        if own_ts_ip and any(ip in own_ts_ip for ip in ips):
                            continue
                        if ips:
                            peers.append({
                                'name': peer.get('HostName', 'unknown'),
                                'host': ips[0],
                                'port': 8081,  # Default UnityBrain port
                                'source': 'tailscale'
                            })
        except (OSError, json.JSONDecodeError) as e:
            logger.debug(f"Tailscale discovery failed: {e}")
        return peers
    
    async def _discover_mdns(self) -> List[Dict]:
        """Discover peers via mDNS/DNS-SD on local network"""
        peers = []
        try:
            # Use zeroconf if available, otherwise use socket broadcast
            import socket
            # Simple UDP broadcast on UnityBrain discovery port
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2)
            
            # Send discovery broadcast
            msg = json.dumps({
                'type': 'unitybrain_discovery',
                'node': self.node_name,
                'port': self.own_port
            }).encode()
            
            # Broadcast on common subnets
            for subnet in ['192.168.1.255', '192.168.129.255', '100.64.0.255']:
                try:
                    sock.sendto(msg, (subnet, 8090))
                except OSError:
                    pass
            
            # Listen for responses
            sock.close()
        except OSError as e:
            logger.debug(f"mDNS discovery failed: {e}")
        return peers
    
    async def _discover_referrals(self) -> List[Dict]:
        """Ask known peers about other peers they know"""
        referred = []
        for key, peer_info in list(self.known_peers.items()):
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"http://{peer_info['host']}:{peer_info.get('port', 8081)}/api/peers"
                    headers = {"X-UnityBrain-Auth": "referral", "X-UnityBrain-TS": str(time.time())}
                    # Use HMAC auth for referral requests
                    if hasattr(self, 'p2p_secret') and self.p2p_secret:
                        ts = str(time.time())
                        msg = f"/api/peers:{ts}"
                        sig = hmac.new(self.p2p_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
                        headers = {"X-UnityBrain-Auth": sig, "X-UnityBrain-TS": ts}
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status == 200:
                            peer_list = await resp.json()
                            for p in peer_list:
                                pkey = f"{p['host']}:{p.get('port', 8081)}"
                                if pkey not in self.known_peers:
                                    p['source'] = 'referral'
                                    referred.append(p)
                        elif resp.status == 401:
                            logger.warning(f"Referral auth failed for {key}")
            except (ValueError, KeyError, aiohttp.ClientError) as e:
                logger.debug(f"Referral from {key} failed: {e}")
        return referred


# ============================================================================
# ============== LOAD BALANCER (Point 4) ===================================
# ============================================================================

class LoadBalancer:
    """Intelligent load balancing between nodes.
    Routes queries based on:
    - Model availability (primary filter)
    - Latency + success rate (secondary)
    - Circuit breaker state (safety)
    - Local CPU load (offload when busy)
    """
    
    def __init__(self):
        self.node_scores: Dict[str, float] = {}
    
    def calculate_score(self, peer, model: str = None) -> float:
        """Calculate routing score (lower = better).
        Factors: latency (40%), model availability (30%), success rate (20%), CB (10%)
        """
        if peer.latency == float('inf') or not peer.available:
            return float('inf')
        
        # Latency score (0-100)
        latency_score = min(peer.latency / 10, 100)
        
        # Model availability penalty
        model_penalty = 0
        if model and model not in peer.models and peer.models:
            model_penalty = 50
        
        # Success rate from model stats
        stats = peer.model_stats.get(model, {}) if model else {}
        total = stats.get('total', 0)
        success = stats.get('success', 0)
        success_rate = success / total if total > 0 else 1.0
        success_score = (1 - success_rate) * 100
        
        # CB penalty
        cb_penalty = 0 if peer.circuit_breaker.state == 'closed' else 50
        
        score = (
            latency_score * 0.4 +
            model_penalty * 0.3 +
            success_score * 0.2 +
            cb_penalty * 0.1
        )
        self.node_scores[peer.name] = score
        return score
    
    def select_best_peer(self, peers: list, model: str = None,
                          exclude: str = None) -> Optional[Any]:
        """Select the best peer for a query, prioritizing model availability."""
        candidates = [p for p in peers 
                       if p.available 
                       and p.circuit_breaker.can_execute()
                       and p.name != exclude]
        if not candidates:
            return None
        
        # Prefer peers that have the requested model
        if model:
            model_peers = [p for p in candidates if model in p.models]
            if model_peers:
                candidates = model_peers
        
        scored = [(self.calculate_score(p, model), p) for p in candidates]
        scored.sort(key=lambda x: x[0])
        
        if scored[0][0] == float('inf'):
            return None
        return scored[0][1]
    
    def should_handle_locally(self, local_cpu: float, local_mem_pct: float,
                                peers: list, model: str) -> bool:
        """Decide if query should be handled locally or offloaded.
        - CPU > 80% and fast peer available -> offload
        - CPU < 50% or no peers -> handle locally
        - Medium: prefer local (network overhead > latency gain)
        """
        available_peers = [p for p in peers if p.available]
        
        if local_cpu > 80 and available_peers:
            best = self.select_best_peer(peers, model)
            if best and best.latency < 200:
                return False
        
        if local_cpu < 50 or not available_peers:
            return True
        
        return True


# ============================================================================
# ============== PEER & P2P NETWORK ========================================
# ============================================================================

# Peer purge constants
PEER_STALE_SECONDS = 600      # 10 min without being seen = stale
PEER_PURGE_SECONDS = 1800     # 30 min without being seen = purge (remove)
PEER_CB_PURGE_FAILURES = 50   # CB failures above this = candidate for purge


class Peer:
    """Représente un peer dans le réseau P2P"""
    def __init__(self, name: str, host: str, port: int, models: List[str],
                 ollama_host: str = None, ollama_port: int = 11434):
        self.name = name
        self.host = host
        self.port = port
        self.models = models
        self.ollama_host = ollama_host or host
        self.ollama_port = ollama_port
        self.available = False
        self.latency = float('inf')
        self.reputation = 1.0
        self.last_seen = 0
        self.circuit_breaker = CircuitBreaker()
        self.model_stats: Dict[str, Dict] = {}

    async def ping(self, session: aiohttp.ClientSession, auth_headers: Dict = None) -> float:
        """Ping le peer via HTTP API"""
        if not self.circuit_breaker.can_execute():
            self.available = False
            return float('inf')
        try:
            start = time.time()
            url = f"http://{self.host}:{self.port}/api/ping"
            headers = auth_headers or {}
            async with session.get(url, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.latency = round((time.time() - start) * 1000, 2)
                    self.available = True
                    self.last_seen = time.time()
                    self.circuit_breaker.record_success()
                    if 'models' in data:
                        for m in data['models']:
                            if m not in self.model_stats:
                                self.model_stats[m] = {"success": 0, "total": 0, "latency_sum": 0}
                                if m not in self.models:
                                    self.models.append(m)
                    return self.latency
            self.available = False
            self.circuit_breaker.record_failure()
            return float('inf')
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
            self.available = False
            self.circuit_breaker.record_failure()
            logger.debug(f"Ping {self.name} failed: {e}")
            return float('inf')

    async def query_model(self, session: aiohttp.ClientSession, model: str,
                          prompt: str, max_length: int = 2000,
                          auth_headers: Dict = None) -> Tuple[str, float]:
        """Query un modèle via Ollama HTTP API"""
        try:
            start = time.time()
            url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False,
                       "options": {"num_predict": max_length}}
            async with session.post(url, json=payload,
                                     timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get('response', '')[:max_length]
                    latency = round((time.time() - start) * 1000, 2)
                    self._update_stats(model, True, latency)
                    return response, latency
                error = await resp.text()
                logger.error(f"Ollama error from {self.name}: {resp.status}")
                self._update_stats(model, False, 0)
                return f"Error: {resp.status}", float('inf')
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Query {model}@{self.name} failed: {e}")
            self._update_stats(model, False, 0)
            return f"Error: {str(e)}", float('inf')

    async def query_via_peer(self, session: aiohttp.ClientSession, model: str,
                              prompt: str, max_length: int = 2000,
                              auth_headers: Dict = None) -> Tuple[str, float]:
        """Query via the peer's UnityBrain API"""
        if not self.circuit_breaker.can_execute():
            return "Error: circuit breaker open", float('inf')
        try:
            start = time.time()
            url = f"http://{self.host}:{self.port}/api/query"
            payload = {"prompt": prompt, "model": model}
            headers = auth_headers or {}
            async with session.post(url, json=payload, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get('response', '')[:max_length]
                    latency = round((time.time() - start) * 1000, 2)
                    self.circuit_breaker.record_success()
                    return response, latency
                self.circuit_breaker.record_failure()
                return f"Error: {resp.status}", float('inf')
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
            self.circuit_breaker.record_failure()
            return f"Error: {str(e)}", float('inf')

    def _update_stats(self, model: str, success: bool, latency: float):
        if model not in self.model_stats:
            self.model_stats[model] = {"success": 0, "total": 0, "latency_sum": 0}
        self.model_stats[model]["total"] += 1
        if success:
            self.model_stats[model]["success"] += 1
            self.model_stats[model]["latency_sum"] += latency

    def vote_reputation(self, delta: float):
        self.reputation = max(0.0, min(1.0, self.reputation + delta))

    def to_dict(self) -> Dict:
        return {
            "name": self.name, "host": self.host, "port": self.port,
            "models": self.models, "available": self.available,
            "latency": self.latency, "reputation": self.reputation,
            "last_seen": self.last_seen,
            "circuit_breaker": self.circuit_breaker.to_dict()
        }


# ============================================================================
# ============== MODEL ROUTING ============================================
# ============================================================================

class ModelRouter:
    """Routeur dynamique de modèles basé sur le contenu du prompt.
    
    Strategies de routing:
    - Code/dev → qwen3-coder (spécialiste)
    - Raisonnement/logique/math → deepseek (thinking model)
    - Chat/general → glm-5.1 (rapide, équilibré)
    - Si modèle demandé explicitement → utilise ce modèle
    - Si modèle indisponible → fallback intelligent
    """
    
    # Catégories de prompts avec mots-clés
    CATEGORIES = {
        'code': {
            'keywords': ['code', 'function', 'python', 'javascript', 'typescript', 'rust',
                         'program', 'script', 'debug', 'implement', 'class ', 'def ', 'async ',
                         'import ', 'return ', 'compile', 'refactor', 'api endpoint',
                         'fonction', 'programme', 'script', 'débog', 'implément', 'codez',
                         'écris un', 'write a', 'create a', 'build a'],
            'models': ['qwen3-coder-next:cloud', 'deepseek-v3.1:671b-cloud', 'glm-5.1:cloud'],
        },
        'reasoning': {
            'keywords': ['explique', 'analyse', 'raisonne', 'think', 'pourquoi', 'compare',
                         'why', 'how does', 'what if', 'calculate', 'solve', 'proof',
                         'logique', 'mathématique', 'déduire', 'infér', 'prouve',
                         'step by step', 'étape par étape', 'résonnement',
                         'démontr', 'what is the reason', 'caus'],
            'models': ['deepseek-v3.1:671b-cloud', 'glm-5.1:cloud', 'qwen3-coder-next:cloud'],
        },
        'creative': {
            'keywords': ['écris', 'write', 'story', 'histoire', 'poem', 'poème', 'creative',
                         'imagine', 'invent', 'fiction', 'narratif', 'romain',
                         'conte', 'chanson', 'song', 'letter', 'lettre'],
            'models': ['glm-5.1:cloud', 'deepseek-v3.1:671b-cloud', 'qwen3-coder-next:cloud'],
        },
        'factual': {
            'keywords': ['quoi', 'what is', 'qui', 'où', 'quand', 'combien',
                         'définition', 'definition', 'capitale', 'capital',
                         'explique-moi', 'tell me about', 'describe', 'décris',
                         'résumé', 'summary', 'liste', 'list'],
            'models': ['glm-5.1:cloud', 'deepseek-v3.1:671b-cloud', 'qwen3-coder-next:cloud'],
        },
    }
    
    # Fallback chains per model
    FALLBACK_CHAINS = {
        'glm-5.1:cloud': ['deepseek-v3.1:671b-cloud', 'qwen3-coder-next:cloud'],
        'deepseek-v3.1:671b-cloud': ['glm-5.1:cloud', 'qwen3-coder-next:cloud'],
        'qwen3-coder-next:cloud': ['glm-5.1:cloud', 'deepseek-v3.1:671b-cloud'],
    }
    
    # Approximate model speeds (ms for simple prompt) — lower = faster
    MODEL_SPEED = {
        'glm-5.1:cloud': 4000,
        'deepseek-v3.1:671b-cloud': 5000,
        'qwen3-coder-next:cloud': 15000,
    }
    
    async def route(self, prompt: str, available_models: List[str]) -> str:
        """Route le prompt vers le meilleur modèle disponible."""
        if not available_models:
            return 'glm-5.1:cloud'
        
        prompt_lower = prompt.lower()
        
        # Detect category by keyword scoring
        best_category = None
        best_score = 0
        for cat_name, cat_data in self.CATEGORIES.items():
            score = sum(1 for kw in cat_data['keywords'] if kw in prompt_lower)
            if score > best_score:
                best_score = score
                best_category = cat_name
        
        # If we detected a category, pick best available model from it
        if best_category and best_score >= 1:
            preferred = self.CATEGORIES[best_category]['models']
            for model in preferred:
                if model in available_models:
                    return model
        
        # Default: fastest model (glm-5.1)
        sorted_by_speed = sorted(available_models, key=lambda m: self.MODEL_SPEED.get(m, 99999))
        return sorted_by_speed[0]
    
    def get_fallback(self, model: str, available_models: List[str]) -> Optional[str]:
        """Get the best fallback model if the requested one fails."""
        chain = self.FALLBACK_CHAINS.get(model, [])
        for fallback in chain:
            if fallback in available_models:
                return fallback
        # Last resort: any available model
        return available_models[0] if available_models else None


# ============================================================================
# ============== ENSEMBLE CONSENSUS =======================================
# ============================================================================

class EnsembleConsensus:
    """Consensus multi-modèles pour réponses fiables"""
    def __init__(self, agreement_threshold: float = 0.6):
        self.agreement_threshold = agreement_threshold

    async def query_ensemble(self, session: aiohttp.ClientSession,
                              models: List[str], prompt: str, peer: Peer,
                              auth_headers: Dict = None) -> Dict:
        responses = []
        for model in models:
            response, latency = await peer.query_model(session, model, prompt,
                                                        auth_headers=auth_headers)
            responses.append({"model": model, "response": response, "latency": latency})

        if not responses:
            return {"consensus": "", "individual_responses": [], "agreement_score": 0}

        consensus = max(responses, key=lambda r: len(r["response"]))["response"]
        max_len = max(len(r["response"]) for r in responses) or 1
        agreement = sum(len(r["response"]) for r in responses) / (len(responses) * max_len)

        return {"consensus": consensus, "individual_responses": responses,
                "agreement_score": round(agreement, 3)}


# ============================================================================
# ============== QUERY HISTORY ============================================
# ============================================================================

class QueryHistory:
    def __init__(self, max_entries: int = 1000):
        self.history: List[Dict] = []
        self.max_entries = max_entries

    async def add(self, query: Dict):
        self.history.append({"timestamp": time.time(), **query})
        if len(self.history) > self.max_entries:
            self.history.pop(0)

    async def get(self, limit: int = 10) -> List[Dict]:
        return self.history[-limit:]


# ============================================================================
# ============== DISTRIBUTED MEMORY ======================================
# ============================================================================

class DistributedMemory:
    """Volatile LRU cache for UnityBrain P2P sync.
    Private persistent memory is handled by the standalone PersistentMemory service."""
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600, **kwargs):
        self.store: Dict[str, Dict] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl

    def set(self, key: str, value: Any, ttl: int = None, **kwargs):
        if len(self.store) >= self.max_size:
            oldest = min(self.store.items(), key=lambda x: x[1]['accessed'])
            del self.store[oldest[0]]
        self.store[key] = {
            'value': value,
            'expires': time.time() + (ttl or self.default_ttl),
            'accessed': time.time()
        }

    def get(self, key: str, **kwargs) -> Any:
        if key in self.store:
            entry = self.store[key]
            if entry['expires'] > time.time():
                entry['accessed'] = time.time()
                return entry['value']
            del self.store[key]
        return None

    def delete(self, key: str, **kwargs) -> bool:
        if key in self.store:
            del self.store[key]
            return True
        return False

    def get_all_for_sync(self) -> Dict[str, Dict]:
        """Get all non-expired entries for P2P sync"""
        now = time.time()
        return {k: {'value': v['value'], 'expires': v['expires']}
                for k, v in self.store.items() if v['expires'] > now}

    def import_from_sync(self, data: Dict[str, Dict]):
        """Import entries from P2P sync"""
        count = 0
        for key, entry in data.items():
            if entry.get('expires', 0) > time.time():
                self.store[key] = entry
                count += 1
        return count

    def search(self, **kwargs) -> list:
        return []

    def stats(self) -> Dict:
        return {'total_entries': len(self.store), 'categories': {}}


# ============================================================================
# ============== CONFIG LOADER ============================================
# ============================================================================

def load_config(config_path: str = None) -> Dict:
    """Load config from JSON file or defaults"""
    default_config = {
        "node_name": "unknown",
        "version": "3.3.0",
        "host": "0.0.0.0",
        "port": 8080,
        "ollama_host": "127.0.0.1",
        "ollama_port": 11434,
        "local_models": ["glm-5.1:cloud"],
        "heartbeat_interval": 30,
        "auto_heal_interval": 120,
        "memory_max_size": 1000,
        "memory_default_ttl": 3600,
        "p2p_secret": os.environ.get("P2P_SECRET", "changeme-configure-in-config"),
        "tailscale_auto_discovery": True,
        "circuit_breaker": {
            "failure_threshold": 3,
            "recovery_timeout": 60,
            "half_open_max_calls": 1
        },
        "token_lifetime": 86400,
        "token_rotation_interval": 3600,
        "discovery_interval": 300,
        "peers": []
    }

    if config_path and Path(config_path).exists():
        try:
            with open(config_path) as f:
                user_config = json.load(f)
            # Deep merge
            for key, value in user_config.items():
                default_config[key] = value
            logger.info(f"Config loaded from {config_path}")
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Config load failed, using defaults: {e}")

    return default_config


# ============================================================================
# ============== TAILSCALE DISCOVERY ======================================
# ============================================================================

async def discover_tailscale_peers() -> List[Dict]:
    """Discover other UnityBrain nodes via Tailscale"""
    peers = []
    try:
        proc = await asyncio.create_subprocess_exec(
            'tailscale', 'status', '--json',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            status = json.loads(stdout)
            for peer in status.get('Peer', {}).values():
                if peer.get('Online', False):
                    peers.append({
                        'name': peer.get('HostName', 'unknown'),
                        'host': peer.get('TailscaleIPs', [''])[0],
                        'online': True
                    })
    except (OSError, json.JSONDecodeError) as e:
        logger.debug(f"Tailscale discovery failed: {e}")
    return peers


# ============================================================================
# ============== UNITYBRAIN MAIN ==========================================
# ============================================================================

class UnityBrain:
    """UnityBrain v3.3 - P2P Distribué avec Auth JWT, Discovery, Load Balancing"""

    def __init__(self, config: Dict):
        self.config = config
        self.node_name = config["node_name"]
        self.version = "3.3.0"
        self.host = config["host"]
        self.port = config["port"]
        self.ollama_host = config["ollama_host"]
        self.ollama_port = config["ollama_port"]
        self.local_models = config["local_models"]
        self.p2p_secret = config.get("p2p_secret", os.environ.get("P2P_SECRET", "changeme"))

        # Components
        self.router = ModelRouter()
        self.ensemble = EnsembleConsensus()
        self.history = QueryHistory()
        self.memory = DistributedMemory(
            max_size=config.get("memory_max_size", 1000),
            default_ttl=config.get("memory_default_ttl", 3600)
        )
        


        # v3.3: Token Auth (Point 1)
        self.auth = TokenAuth(
            secret=self.p2p_secret,
            token_lifetime=config.get("token_lifetime", 86400),
            rotation_interval=config.get("token_rotation_interval", 3600)
        )
        
        # v3.3: Dynamic Discovery (Point 3)
        self.discovery = PeerDiscovery(
            node_name=self.node_name,
            own_host=self.host,
            own_port=self.port,
            config_peers=config.get("peers", [])
        )
        
        # v3.3: Load Balancer (Point 4)
        self.load_balancer = LoadBalancer()

        # Peers
        self.peers: List[Peer] = []

        # Stats
        self.queries = 0
        self.successful = 0
        self.start_time = time.time()

        # Brain LLM engine
        try:
            from brain_llm import BrainLLM
            self.brain_llm = BrainLLM(node_name=self.node_name)
        except ImportError:
            self.brain_llm = None
            logger.warning("brain.llm not available")

        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None

        # Heartbeat
        self.heartbeat_interval = config.get("heartbeat_interval", 30)
        self.heartbeat_running = False

        # WebSocket clients for real-time sync (Point 2)
        self.ws_clients: Set[web.WebSocketResponse] = set()

        # Event log for dashboard
        self.event_log: deque = deque(maxlen=50)

    def log_event(self, event_type: str, message: str, level: str = "info"):
        entry = {
            "time": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "level": level
        }
        self.event_log.append(entry)
        # Persist to event log file (append mode, one JSON per line)
        try:
            log_file = Path(__file__).parent.parent / "logs" / "events.jsonl"
            log_file.parent.mkdir(exist_ok=True)
            with open(log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except OSError:
            pass  # Non-critical, don't crash on log write failure

    async def add_peer(self, peer: Peer):
        # Don't add self as a peer
        if peer.host in (self.host, '127.0.0.1', 'localhost') and peer.port == self.port:
            logger.debug(f"Skipping self-peer: {peer.name} ({peer.host}:{peer.port})")
            return
        self.peers.append(peer)
        self.log_event("peer_added", f"Peer {peer.name} added ({peer.host}:{peer.port})")

    def purge_dead_peers(self):
        """Remove peers that are definitively dead:
        - CB open AND stale (not seen recently)
        - CB open AND excessive failures
        - Never seen AND excessive CB failures
        """
        now = time.time()
        to_remove = []
        for p in self.peers:
            # Skip config peers (from config file) — they get a pass
            is_config_peer = any(cp['host'] == p.host and cp.get('port', 8081) == p.port 
                                 for cp in self.config.get('peers', []))
            
            # Never seen and lots of failures → ghost peer
            if p.last_seen == 0 and p.circuit_breaker.failure_count >= PEER_CB_PURGE_FAILURES:
                to_remove.append(p)
                self.log_event("peer_purged", 
                    f"Purged ghost peer {p.name} ({p.host}:{p.port}) — {p.circuit_breaker.failure_count} failures, never seen",
                    level="warn")
                continue
            
            # Stale peer (not seen in PEER_STALE_SECONDS) with open CB and many failures
            if (p.last_seen > 0 and now - p.last_seen > PEER_STALE_SECONDS 
                and p.circuit_breaker.state == CircuitBreaker.STATE_OPEN
                and p.circuit_breaker.failure_count >= PEER_CB_PURGE_FAILURES):
                to_remove.append(p)
                self.log_event("peer_purged",
                    f"Purged stale peer {p.name} ({p.host}:{p.port}) — last seen {int(now-p.last_seen)}s ago, {p.circuit_breaker.failure_count} failures",
                    level="warn")
                continue
            
            # Not config peer, never seen, stale
            if (not is_config_peer and p.last_seen == 0 
                and p.circuit_breaker.state == CircuitBreaker.STATE_OPEN):
                to_remove.append(p)
                self.log_event("peer_purged",
                    f"Purged undiscovered peer {p.name} ({p.host}:{p.port}) — CB open, never seen",
                    level="warn")
                continue
        
        for p in to_remove:
            self.peers.remove(p)
        
        return len(to_remove)

    async def initialize(self):
        """Initialise UnityBrain v3.3"""
        logger.info(f"Initializing {self.node_name} v{self.version}...")
        self.log_event("init", f"UnityBrain v{self.version} starting as '{self.node_name}'")

        self.session = aiohttp.ClientSession()

        # Initialize brain.llm engine
        if self.brain_llm:
            self.brain_llm.session = self.session
            await self.brain_llm.start()
            logger.info(f"brain.llm started — {self.brain_llm.status()['models_available']} models")

        # v3.3: Dynamic peer discovery
        discovered = await self.discovery.discover_all()
        for peer_info in discovered:
            # Check if peer already added
            existing = [p for p in self.peers if p.host == peer_info['host'] 
                        and p.port == peer_info.get('port', 8081)]
            if not existing:
                peer = Peer(
                    name=peer_info.get('name', 'unknown'),
                    host=peer_info['host'],
                    port=peer_info.get('port', 8081),
                    models=peer_info.get('models', []),
                    ollama_host=peer_info.get('ollama_host', peer_info['host']),
                    ollama_port=peer_info.get('ollama_port', 11434)
                )
                cb_config = self.config.get('circuit_breaker', {})
                peer.circuit_breaker = CircuitBreaker(
                    failure_threshold=cb_config.get('failure_threshold', 3),
                    recovery_timeout=cb_config.get('recovery_timeout', 60),
                    half_open_max=cb_config.get('half_open_max_calls', 1)
                )
                await self.add_peer(peer)
                self.log_event("discovery", f"Discovered {peer.name} via {peer_info.get('source', 'config')}")

        # Generate auth token for self
        self.self_token = self.auth.generate_token(self.node_name)
        self.log_event("auth", f"Token generated (key_id: {self.auth.current_key_id})")

        await self.check_peers()
        available = [p for p in self.peers if p.available]
        self.log_event("init", f"Initialized with {len(available)}/{len(self.peers)} peers")
        logger.info(f"{self.node_name} initialized! Peers: {len(available)}/{len(self.peers)}")

    async def check_peers(self):
        """Ping all peers"""
        if not self.session:
            return
        headers = self._auth_headers("")
        for peer in self.peers:
            await peer.ping(self.session, auth_headers=headers)

    async def start_heartbeat(self):
        """Background heartbeat with peer purge"""
        self.heartbeat_running = True
        while self.heartbeat_running:
            await asyncio.sleep(self.heartbeat_interval)
            await self.check_peers()
            # Purge dead peers every heartbeat
            purged = self.purge_dead_peers()
            if purged:
                logger.info(f"Purged {purged} dead peers")
            available = [p for p in self.peers if p.available]
            if available:
                logger.debug(f"Heartbeat: {len(available)}/{len(self.peers)} peers alive")

    async def query(self, prompt: str, model: str = None,
                     use_ensemble: bool = False) -> Dict:
        """Exécute une requête avec failover intelligent, load balancing et circuit breaker.
        
        Strategy:
        1. Route to best model based on prompt content
        2. Try local first (if model available and not overloaded)
        3. If local fails, try peer with same model
        4. If all fail, fallback to alternative model
        5. Return error if nothing works
        """
        self.queries += 1
        logger.info(f"Query {self.queries}: {prompt[:50]}...")

        selected_model = model or await self.router.route(prompt, self.local_models)
        
        # Use cached CPU if available (avoid psutil per-query)
        now = time.time()
        if hasattr(self, '_monitor_cache_time') and now - self._monitor_cache_time < 10:
            local_cpu = self._monitor_cache.get('cpu_percent', 0)
            local_mem = self._monitor_cache.get('memory', {}).get('percent', 0)
        else:
            local_cpu = psutil.cpu_percent(interval=0.1)
            local_mem = psutil.virtual_memory().percent
        
        handle_local = self.load_balancer.should_handle_locally(
            local_cpu, local_mem, self.peers, selected_model)
        
        # Build fallback chain
        fallback_models = self.router.FALLBACK_CHAINS.get(selected_model, [])
        all_models_to_try = [selected_model] + [m for m in fallback_models if m != selected_model]
        # Filter to models we actually have
        all_local = list(self.local_models)
        for p in self.peers:
            if p.available:
                all_local.extend(p.models)
        all_local = list(set(all_local))
        models_to_try = [m for m in all_models_to_try if m in all_local]
        if not models_to_try:
            models_to_try = [selected_model]  # fallback to original even if missing
        
        response, latency, used_model = '', float('inf'), selected_model
        
        # Try each model in priority order
        for try_model in models_to_try:
            if handle_local and try_model in self.local_models:
                # Try local
                resp, lat = await self._query_local(try_model, prompt)
                if lat < float('inf'):
                    response, latency, used_model = resp, lat, try_model
                    break
            
            # Try peer
            best_peer = self.load_balancer.select_best_peer(
                self.peers, model=try_model, exclude=self.node_name)
            if best_peer:
                resp, lat = await best_peer.query_via_peer(
                    self.session, try_model, prompt,
                    auth_headers=self.auth.auth_headers(self.node_name,
                        f"http://{best_peer.host}:{best_peer.port}/api/query")
                )
                if lat < float('inf'):
                    response, latency, used_model = resp, lat, try_model
                    self.log_event("load_balance", 
                        f"Query routed to {best_peer.name} ({try_model}, {latency:.0f}ms)")
                    break
            
            # Fallback: try any available peer
            available = sorted(
                [p for p in self.peers if p.available and p.circuit_breaker.can_execute()],
                key=lambda p: p.latency
            )
            for peer in available:
                if try_model in peer.models or not peer.models:
                    resp, lat = await peer.query_via_peer(
                        self.session, try_model, prompt,
                        auth_headers=self.auth.auth_headers(self.node_name,
                            f"http://{peer.host}:{peer.port}/api/query")
                    )
                    if lat < float('inf'):
                        response, latency, used_model = resp, lat, try_model
                        self.log_event("failover", f"Failover to {peer.name} ({try_model}, {latency:.0f}ms)")
                        break
            if latency < float('inf'):
                break

        success = latency < float('inf')
        if success:
            self.successful += 1

        await self.history.add({
            "prompt": prompt, "response": response,
            "model": used_model, "latency": latency, "success": success,
            "routed_to": "local" if handle_local and success else "peer",
            "fallback": used_model != selected_model
        })

        return {
            "status": "success" if success else "error",
            "response": response, "model": used_model,
            "latency": latency, "node": self.node_name,
            "routed_locally": handle_local and success,
            "fallback_used": used_model != selected_model,
            "original_model": selected_model
        }

    async def _query_local(self, model: str, prompt: str) -> Tuple[str, float]:
        """Query local Ollama"""
        try:
            url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False,
                       "options": {"num_predict": 2000}}
            start = time.time()
            async with self.session.post(url, json=payload,
                                          timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    latency = round((time.time() - start) * 1000, 2)
                    return data.get('response', '')[:2000], latency
                return f"Error: {resp.status}", float('inf')
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
            return f"Error: {str(e)}", float('inf')

    def get_status(self) -> Dict:
        available = [p for p in self.peers if p.available]
        return {
            "version": self.version,
            "node": self.node_name,
            "uptime": round(time.time() - self.start_time, 1),
            "peers": {
                "total": len(self.peers),
                "available": len(available),
                "list": [p.to_dict() for p in self.peers]
            },
            "queries": {
                "total": self.queries,
                "successful": self.successful,
                "rate": round((self.successful / self.queries * 100), 1) if self.queries > 0 else 0
            },
            "memory": {"keys": len(self.memory.store)},
            "history": {"entries": len(self.history.history)},
            "local_models": self.local_models,
            "event_log": list(self.event_log)[-10:]
        }

    # ========================================================================
    # ============== AUTH ====================================================
    # ========================================================================

    def _verify_auth(self, request: web.Request) -> bool:
        """Verify P2P authentication (JWT tokens + HMAC fallback for v3.2 compat)"""
        # v3.3: Try JWT/Bearer token first, then HMAC fallback
        payload = self.auth.verify_request(request, secret=self.p2p_secret)
        if payload:
            return True
        return False

    def _auth_headers(self, path: str) -> Dict[str, str]:
        """Generate auth headers (v3.3 JWT + v3.2 HMAC for compatibility)
        path should be just the URL path (e.g. '/api/ping'), not the full URL."""
        headers = self.auth.auth_headers(self.node_name, path)
        # Also include HMAC for v3.2 peer compat
        # Strip full URL to path-only for consistent signing with server-side verify
        if path.startswith('http'):
            from urllib.parse import urlparse
            path = urlparse(path).path
        ts = str(time.time())
        msg = f"{path}:{ts}"
        sig = hmac.new(self.p2p_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        headers['X-UnityBrain-Auth'] = sig
        headers['X-UnityBrain-TS'] = ts
        return headers

    # ========================================================================
    # ============== HTTP API ================================================
    # ========================================================================

    async def create_app(self) -> web.Application:
        app = web.Application()
        app.middlewares.append(self.auth_middleware)
        app.add_routes([
            web.get('/', self.handle_dashboard),
            web.get('/api/status', self.handle_status),
            web.get('/api/ping', self.handle_ping),
            web.post('/api/query', self.handle_query),
            web.post('/api/memory', self.handle_memory_set),
            web.get('/api/memory/{key}', self.handle_memory_get),
            web.get('/api/peers', self.handle_peers),
            web.get('/api/monitor', self.handle_monitor),
            web.post('/api/sync', self.handle_sync),
            web.get('/api/brain/status', self.handle_brain_status),
            web.post('/api/brain/query', self.handle_brain_query),
            web.post('/api/brain/consensus', self.handle_brain_consensus),
            web.post('/api/brain/chain', self.handle_brain_chain),
            web.get('/api/brain/models', self.handle_brain_models),
            web.get('/ws', self.handle_websocket),
        ])
        return app

    @web.middleware
    async def auth_middleware(self, request, handler):
        # Public endpoints (no auth needed)
        public_paths = ['/api/status', '/api/ping']
        # Dashboard requires auth too (exposes peers, events, models)
        if request.path in public_paths:
            return await handler(request)
        # All other endpoints require auth (including / dashboard)
        if not self._verify_auth(request):
            # Allow unauthenticated dashboard access from localhost only
            if request.path == '/' and request.remote in ('127.0.0.1', '::1', 'localhost'):
                return await handler(request)
            self.log_event("auth_fail", f"Unauthorized {request.method} from {request.remote} on {request.path}", "warn")
            if request.path == '/':
                return web.json_response({'error': 'unauthorized', 'hint': 'Use /api/status for public info'}, status=401)
            return web.json_response({'error': 'unauthorized'}, status=401)
        return await handler(request)

    # --- Dashboard ---

    async def handle_dashboard(self, request: web.Request) -> web.Response:
        status = self.get_status()
        uptime = status['uptime']
        hours = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)
        secs = int(uptime % 60)

        peer_rows = ""
        for p in status['peers']['list']:
            icon = "✅" if p['available'] else "❌"
            lat = f"{p['latency']:.0f}ms" if p['latency'] < float('inf') else "∞"
            cb = p.get('circuit_breaker', {})
            cb_state = cb.get('state', 'unknown')
            cb_color = {"closed": "#2ecc71", "open": "#e74c3c", "half_open": "#f39c12"}.get(cb_state, "#888")
            peer_rows += f"""<div class="peer">
                <span class="{"ok" if p["available"] else "ko"}">{icon}</span>
                <strong>{p["name"]}</strong> — {lat}
                <span class="cb" style="background:{cb_color}">CB:{cb_state}</span>
                <small>rep:{p["reputation"]:.2f} models:{", ".join(p["models"])}</small>
            </div>"""

        event_rows = ""
        for e in reversed(list(self.event_log)[-20:]):
            level_color = {"info": "#3498db", "warn": "#f39c12", "error": "#e74c3c"}.get(e.get("level", "info"), "#3498db")
            event_rows += f"""<tr>
                <td style="color:#888">{e['time'][:19]}</td>
                <td style="color:{level_color}">{e['type']}</td>
                <td>{e['message'][:80]}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html><head><title>UnityBrain v{self.version}</title>
<meta http-equiv="refresh" content="10">
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 0; background: #0d1117; color: #c9d1d9; }}
.header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px 30px; border-bottom: 2px solid #2ecc71; }}
.header h1 {{ margin: 0; color: #2ecc71; font-size: 24px; }}
.header .subtitle {{ color: #8b949e; font-size: 14px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }}
.card h2 {{ margin: 0 0 15px 0; color: #58a6ff; font-size: 16px; border-bottom: 1px solid #21262d; padding-bottom: 10px; }}
.stat {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #21262d; }}
.stat .label {{ color: #8b949e; }} .stat .value {{ color: #f0f6fc; font-weight: bold; }}
.peer {{ background: #21262d; padding: 10px 15px; margin: 5px 0; border-radius: 6px; }}
.ok {{ color: #2ecc71; }} .ko {{ color: #e74c3c; }}
.cb {{ font-size: 10px; padding: 2px 6px; border-radius: 3px; color: white; margin-left: 8px; }}
.events {{ grid-column: 1 / -1; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; color: #8b949e; padding: 8px; border-bottom: 1px solid #30363d; }}
td {{ padding: 6px 8px; border-bottom: 1px solid #21262d; }}
.full {{ grid-column: 1 / -1; }}
</style></head><body>
<div class="header">
    <h1>🌐 UnityBrain v{self.version}</h1>
    <div class="subtitle">Node: <strong>{self.node_name}</strong> | Uptime: {hours}h {mins}m {secs}s</div>
</div>
<div class="grid">
    <div class="card">
        <h2>📊 Status</h2>
        <div class="stat"><span class="label">Queries</span><span class="value">{status['queries']['total']} ({status['queries']['rate']}% success)</span></div>
        <div class="stat"><span class="label">Memory keys</span><span class="value">{status['memory']['keys']}</span></div>
        <div class="stat"><span class="label">History</span><span class="value">{status['history']['entries']}</span></div>
        <div class="stat"><span class="label">Models</span><span class="value">{', '.join(self.local_models)}</span></div>
    </div>
    <div class="card">
        <h2>🤖 Peers ({status['peers']['available']}/{status['peers']['total']})</h2>
        {peer_rows if peer_rows else '<div style="color:#8b949e">No peers configured</div>'}
    </div>
    <div class="card events full">
        <h2>📋 Event Log</h2>
        <table><tr><th>Time</th><th>Type</th><th>Message</th></tr>
        {event_rows if event_rows else '<tr><td colspan="3" style="color:#8b949e">No events</td></tr>'}
        </table>
    </div>
</div>
</body></html>"""
        return web.Response(text=html, content_type='text/html')

    # --- API Endpoints ---

    async def handle_status(self, request: web.Request) -> web.Response:
        return web.json_response(self.get_status())

    async def handle_ping(self, request: web.Request) -> web.Response:
        return web.json_response({
            "node": self.node_name, "version": self.version,
            "models": self.local_models,
            "uptime": round(time.time() - self.start_time, 1),
            "timestamp": time.time()
        })

    async def handle_query(self, request: web.Request) -> web.Response:
        auth = self._verify_auth(request)
        if not auth:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            data = await request.json()
            prompt = data.get('prompt', '')
            if not prompt or not prompt.strip():
                return web.json_response(
                    {"status": "error", "message": "'prompt' is required and cannot be empty"},
                    status=400)
            model = data.get('model')
            use_ensemble = data.get('ensemble', False)
            # Validate model exists locally or on a peer
            all_models = list(self.local_models)
            for p in self.peers:
                all_models.extend(p.models)
            if model and model not in all_models:
                return web.json_response(
                    {"status": "error", "message": f"Model '{model}' not found. Available: {list(set(all_models))}"},
                    status=404)
            result = await self.query(prompt, model=model, use_ensemble=use_ensemble)
            return web.json_response(result)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)
        except Exception as e:
            logger.error(f"Unexpected query error: {e}")
            return web.json_response({"status": "error", "message": "Internal error"}, status=500)

    async def handle_memory_set(self, request: web.Request) -> web.Response:
        auth = self._verify_auth(request)
        if not auth:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            data = await request.json()
            key = data.get('key', '')
            value = data.get('value')
            ttl = data.get('ttl', 3600)
            self.memory.set(key, value, ttl)
            self.log_event("memory", f"Set key: {key}")
            return web.json_response({"status": "ok", "key": key})
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return web.json_response({"status": "error", "message": str(e)}, status=400)
        except Exception as e:
            logger.error(f"Unexpected memory_set error: {e}")
            return web.json_response({"status": "error", "message": "Internal error"}, status=500)

    async def handle_memory_get(self, request: web.Request) -> web.Response:
        # v3.3: Require auth for memory reads (may contain sensitive data)
        # Bypass _verify_auth's default GET exemption - check JWT/HMAC directly
        auth = self.auth.verify_request(request, secret=self.p2p_secret)
        if not auth:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        key = request.match_info['key']
        value = self.memory.get(key)
        return web.json_response({"key": key, "value": value})

    async def handle_peers(self, request: web.Request) -> web.Response:
        auth = self._verify_auth(request)
        if not auth:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        return web.json_response([p.to_dict() for p in self.peers])

    async def handle_monitor(self, request: web.Request) -> web.Response:
        auth = self._verify_auth(request)
        if not auth:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            # Cache monitor results for 10 seconds to avoid slow psutil calls
            now = time.time()
            if hasattr(self, '_monitor_cache') and hasattr(self, '_monitor_cache_time'):
                if now - self._monitor_cache_time < 10:
                    return web.json_response(self._monitor_cache)
            
            cpu = psutil.cpu_percent(interval=0.1)  # Much faster than 0.5s
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()
            load = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
            result = {
                'node': self.node_name,
                'cpu_percent': cpu,
                'load_avg': {'1m': load[0], '5m': load[1], '15m': load[2]},
                'memory': {'total_gb': round(mem.total/1e9, 1), 'used_gb': round(mem.used/1e9, 1),
                           'percent': mem.percent, 'available_gb': round(mem.available/1e9, 1)},
                'disk': {'total_gb': round(disk.total/1e9, 1), 'used_gb': round(disk.used/1e9, 1),
                         'percent': disk.percent, 'free_gb': round(disk.free/1e9, 1)},
                'network': {'bytes_sent': net.bytes_sent, 'bytes_recv': net.bytes_recv},
                'uptime': round(now - self.start_time, 1),
                'system_uptime': round(now - psutil.boot_time(), 1),
                'processes': len(psutil.pids())
            }
            self._monitor_cache = result
            self._monitor_cache_time = now
            return web.json_response(result)
        except (RuntimeError, OSError) as e:
            return web.json_response({'error': str(e)}, status=500)

    async def handle_sync(self, request: web.Request) -> web.Response:
        auth = self._verify_auth(request)
        if not auth:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            data = await request.json()
            keys_synced = 0
            for key, entry in data.get('memory', {}).items():
                if entry.get('expires', 0) > time.time():
                    self.memory.set(key, entry['value'], entry.get('expires', 0) - time.time())
                    keys_synced += 1
            if keys_synced:
                self.log_event("sync", f"Received {keys_synced} keys from peer")
            return web.json_response({'status': 'ok', 'keys_synced': keys_synced})
        except (aiohttp.ClientError, json.JSONDecodeError, KeyError) as e:
            return web.json_response({'error': str(e)}, status=500)

    # --- Brain LLM Endpoints ---

    async def handle_brain_status(self, request: web.Request) -> web.Response:
        """GET /api/brain/status — Brain LLM engine status"""
        auth = self._verify_auth(request)
        if not auth:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        if not self.brain_llm:
            return web.json_response({"error": "brain.llm not available"}, status=503)
        return web.json_response(self.brain_llm.status())

    async def handle_brain_models(self, request: web.Request) -> web.Response:
        """GET /api/brain/models — Available models"""
        auth = self._verify_auth(request)
        if not auth:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        if not self.brain_llm:
            return web.json_response({"error": "brain.llm not available"}, status=503)
        return web.json_response(self.brain_llm.status().get("models", {}))

    async def handle_brain_query(self, request: web.Request) -> web.Response:
        """POST /api/brain/query — Intelligent query routing"""
        if not self.brain_llm:
            return web.json_response({"error": "brain.llm not available"}, status=503)
        try:
            data = await request.json()
            prompt = data.get('prompt', '')
            model = data.get('model')
            strategy = data.get('strategy', 'auto')
            if not prompt:
                return web.json_response({"error": "prompt is required"}, status=400)
            result = await self.brain_llm.query(prompt, model=model, strategy=strategy)
            return web.json_response({
                "response": result.response,
                "model": result.model,
                "provider": result.provider,
                "latency_ms": result.latency_ms,
                "tokens_used": result.tokens_used,
                "confidence": result.confidence,
                "error": result.error
            })
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=502)
        except Exception as e:
            logger.error(f"Unexpected brain_query error: {e}")
            return web.json_response({"error": "Internal error"}, status=500)

    async def handle_brain_consensus(self, request: web.Request) -> web.Response:
        """POST /api/brain/consensus — Multi-model consensus query"""
        if not self.brain_llm:
            return web.json_response({"error": "brain.llm not available"}, status=503)
        try:
            data = await request.json()
            prompt = data.get('prompt', '')
            if not prompt:
                return web.json_response({"error": "prompt is required"}, status=400)
            result = await self.brain_llm.query(prompt, strategy="consensus")
            return web.json_response({
                "response": result.response,
                "model": result.model,
                "latency_ms": result.latency_ms,
                "confidence": result.confidence
            })
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=502)
        except Exception as e:
            logger.error(f"Unexpected brain_consensus error: {e}")
            return web.json_response({"error": "Internal error"}, status=500)

    async def handle_brain_chain(self, request: web.Request) -> web.Response:
        """POST /api/brain/chain — Chain-of-thought query"""
        if not self.brain_llm:
            return web.json_response({"error": "brain.llm not available"}, status=503)
        try:
            data = await request.json()
            prompt = data.get('prompt', '')
            if not prompt:
                return web.json_response({"error": "prompt is required"}, status=400)
            result = await self.brain_llm.query(prompt, strategy="chain")
            return web.json_response({
                "response": result.response,
                "model": result.model,
                "latency_ms": result.latency_ms,
                "confidence": result.confidence
            })
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=500)

    # --- WebSocket (Point 2: Real-time Memory Sync) ---

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        # v3.3: Authenticate WebSocket connections
        # Check for token in query params or first message
        ws_authenticated = False
        
        await ws.prepare(request)
        self.ws_clients.add(ws)
        self.log_event("ws", f"WebSocket connected from {request.remote} ({len(self.ws_clients)} clients)")
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get('type', '')
                    
                    # v3.3: Require auth for write operations via WS
                    # Allow ping, memory_request, monitor without auth
                    if msg_type == 'auth':
                        # Authenticate via JWT or HMAC
                        token = data.get('token', '')
                        hmac_auth = data.get('hmac', '')
                        hmac_ts = data.get('ts', '')
                        if token:
                            payload = self.auth.verify_token(token)
                            if payload:
                                ws_authenticated = True
                                await ws.send_json({'type': 'auth_ack', 'status': 'ok'})
                                self.log_event("ws_auth", f"WS client authenticated via JWT")
                        elif hmac_auth and hmac_ts:
                            msg_str = f"/ws:{hmac_ts}"
                            expected_sig = hmac.new(self.p2p_secret.encode(), msg_str.encode(), hashlib.sha256).hexdigest()
                            if hmac.compare_digest(hmac_auth, expected_sig):
                                ws_authenticated = True
                                await ws.send_json({'type': 'auth_ack', 'status': 'ok'})
                                self.log_event("ws_auth", f"WS client authenticated via HMAC")
                        if not ws_authenticated:
                            await ws.send_json({'type': 'auth_ack', 'status': 'failed'})
                        continue
                    
                    # Write operations require authentication
                    if msg_type in ('memory_sync', 'query', 'discover', 'memory_request', 'monitor') and not ws_authenticated:
                        await ws.send_json({'type': 'error', 'message': 'Authentication required'})
                        continue
                    
                    if msg_type == 'ping':
                        await ws.send_json({'type': 'pong', 'node': self.node_name,
                                            'timestamp': time.time()})
                    elif msg_type == 'query':
                        result = await self.query(data.get('prompt', ''),
                                                   model=data.get('model'))
                        await ws.send_json({'type': 'query_result', **result})
                    elif msg_type == 'memory_sync':
                        # v3.3: Real-time memory sync via WebSocket
                        keys_synced = 0
                        for key, entry in data.get('entries', {}).items():
                            if isinstance(entry, dict) and 'value' in entry:
                                ttl = entry.get('ttl', 3600)
                                self.memory.set(key, entry['value'], ttl)
                                keys_synced += 1
                            else:
                                self.memory.set(key, entry)
                                keys_synced += 1
                        self.log_event("ws_sync", f"Received {keys_synced} keys via WebSocket")
                        await ws.send_json({'type': 'sync_ack',
                                            'keys': keys_synced})
                        # Broadcast to other WS clients
                        await self._broadcast_ws({'type': 'memory_update',
                                                   'keys': list(data.get('entries', {}).keys())},
                                                   exclude=ws)
                    elif msg_type == 'memory_request':
                        # Peer requests our memory state
                        memory_data = self.memory.get_all_for_sync()
                        await ws.send_json({'type': 'memory_full',
                                            'entries': memory_data})
                    elif msg_type == 'discover':
                        # v3.3: Peer announces itself
                        peer_info = data.get('peer', {})
                        self.log_event("ws_discover", f"Peer {peer_info.get('name', '?')} announced via WS")
                        await ws.send_json({'type': 'discover_ack',
                                            'node': self.node_name,
                                            'models': self.local_models,
                                            'peers': [p.to_dict() for p in self.peers]})
                    elif msg_type == 'monitor':
                        cpu = psutil.cpu_percent(interval=0.5)
                        mem = psutil.virtual_memory()
                        await ws.send_json({
                            'type': 'monitor_data',
                            'cpu': cpu,
                            'mem_percent': mem.percent,
                            'load_balancer_scores': self.load_balancer.node_scores,
                            'timestamp': time.time()
                        })
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WS error: {ws.exception()}')
        except (aiohttp.ServerDisconnectedError, ConnectionResetError) as e:
            logger.error(f'WebSocket error: {e}')
        finally:
            self.ws_clients.discard(ws)
            self.log_event("ws", f"WebSocket disconnected ({len(self.ws_clients)} clients)")
        return ws
    
    async def _broadcast_ws(self, data: Dict, exclude=None):
        """Broadcast data to all connected WebSocket clients except excluded one"""
        msg = json.dumps(data)
        for client in list(self.ws_clients):
            if client != exclude and not client.closed:
                try:
                    await client.send_str(msg)
                except ConnectionResetError:
                    self.ws_clients.discard(client)
    
    async def _ws_memory_sync_loop(self):
        """Background task: periodically push memory updates to WebSocket peers"""
        while self.heartbeat_running:
            await asyncio.sleep(60)  # Sync every 60s via WS
            if self.ws_clients and self.memory.store:
                memory_data = self.memory.get_all_for_sync()
                if memory_data:
                    await self._broadcast_ws({
                        'type': 'memory_sync',
                        'entries': memory_data
                    })
                    self.log_event("ws_sync", f"Pushed {len(memory_data)} keys to {len(self.ws_clients)} WS clients")

    # --- Background Tasks ---

    async def sync_memory_to_peers(self):
        """Push local memory to all available peers"""
        if not self.session:
            return
        memory_data = self.memory.get_all_for_sync()
        if not memory_data:
            return
        for peer in self.peers:
            if peer.available and peer.circuit_breaker.can_execute():
                try:
                    url = f'http://{peer.host}:{peer.port}/api/sync'
                    headers = self._auth_headers(url)
                    async with self.session.post(url, json={'memory': memory_data},
                                                  headers=headers,
                                                  timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            logger.debug(f"Synced {data.get('keys_synced', 0)} keys to {peer.name}")
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.debug(f"Sync to {peer.name} failed: {e}")

    async def auto_heal(self):
        """Auto-healing: check Ollama and restart if needed"""
        heal_interval = self.config.get("auto_heal_interval", 120)
        while self.heartbeat_running:
            await asyncio.sleep(heal_interval)
            try:
                async with self.session.get(
                    f'http://{self.ollama_host}:{self.ollama_port}/api/tags',
                    timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        self.log_event("auto_heal", "Ollama down, restarting...", "warn")
                        logger.warning("Ollama seems down, attempting restart...")
                        proc = await asyncio.create_subprocess_exec(
                            'fuser', '-k', f'{self.ollama_port}/tcp',
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        await proc.communicate()
                        proc = await asyncio.create_subprocess_exec(
                            'systemctl', 'restart', 'ollama',
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        await proc.communicate()
                        self.log_event("auto_heal", "Ollama restart triggered")
                        logger.info("Ollama restart triggered")
            except (OSError, subprocess.SubprocessError):
                self.log_event("auto_heal", "Ollama health check failed", "warn")
            await self.sync_memory_to_peers()

    async def _discovery_loop(self):
        """Background task: periodically re-discover peers"""
        interval = self.config.get("discovery_interval", 300)
        while self.heartbeat_running:
            await asyncio.sleep(interval)
            new_peers = await self.discovery.discover_all()
            for peer_info in new_peers:
                existing = [p for p in self.peers if p.host == peer_info['host'] 
                            and p.port == peer_info.get('port', 8081)]
                if not existing:
                    peer = Peer(
                        name=peer_info.get('name', 'unknown'),
                        host=peer_info['host'],
                        port=peer_info.get('port', 8081),
                        models=peer_info.get('models', [])
                    )
                    await self.add_peer(peer)
                    self.log_event("discovery", f"Auto-discovered {peer.name} via {peer_info.get('source', 'unknown')}")


# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def main():
    import sys
    import signal

    node_name = sys.argv[1] if len(sys.argv) > 1 else "bug"

    # Look for config file
    script_dir = Path(__file__).parent.parent
    config_path = script_dir / "config" / f"{node_name}.json"

    config = load_config(str(config_path))

    # Override node_name from CLI if provided
    if len(sys.argv) > 1:
        config["node_name"] = node_name

    # Create UnityBrain v3.3
    brain = UnityBrain(config)

    # v3.3: Peers are added during initialize() via PeerDiscovery
    # Config peers are passed to PeerDiscovery as fallback
    await brain.initialize()

    # Graceful shutdown via asyncio Event
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("🛑 UnityBrain shutting down...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    # Start server
    app = await brain.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, brain.host, brain.port, reuse_address=True, reuse_port=True)
    await site.start()
    logger.info(f"UnityBrain P2P server on http://{brain.host}:{brain.port}")
    brain.log_event("server", f"Listening on {brain.host}:{brain.port}")

    # Start background tasks
    tasks = [
        asyncio.create_task(brain.start_heartbeat()),
        asyncio.create_task(brain.auto_heal()),
        asyncio.create_task(brain._ws_memory_sync_loop()),
        asyncio.create_task(brain._discovery_loop()),
    ]

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Cleanup
    logger.info("Cleaning up...")
    brain.heartbeat_running = False
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    if brain.session:
        await brain.session.close()
    await runner.cleanup()
    logger.info("UnityBrain stopped.")


if __name__ == '__main__':
    import sys
    node = sys.argv[1] if len(sys.argv) > 1 else "bug"
    logger.info(f"Starting UnityBrain v3.3 as '{node}'")
    asyncio.run(main())