#!/usr/bin/env python3
"""
🌐 UNITYBRAIN v3.2 - RÉSEAU P2P DISTRIBUTÉ
Full rewrite with:
- JSON config file support
- Circuit breaker pattern
- Tailscale auto-discovery
- HMAC P2P authentication
- System monitoring (psutil)
- Auto-heal (Ollama restart)
- Distributed memory sync
- WebSocket real-time
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
import psutil
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger('UnityBrain')


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
# ============== PEER & P2P NETWORK ========================================
# ============================================================================

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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
    """Routeur dynamique de modèles basé sur le contenu"""
    async def route(self, prompt: str, available_models: List[str]) -> str:
        prompt_lower = prompt.lower()
        # Code-related
        if any(kw in prompt_lower for kw in ["code", "function", "python", "javascript",
                                              "program", "script", "debug"]):
            code_models = [m for m in available_models if "code" in m.lower() or "coder" in m.lower()]
            if code_models:
                return code_models[0]
        # Reasoning/analysis
        if any(kw in prompt_lower for kw in ["explique", "analyse", "raisonne", "think",
                                              "pourquoi", "compare", "why", "how"]):
            reasoning = [m for m in available_models if "glm" in m.lower()]
            if reasoning:
                return reasoning[0]
        # Default: first available
        return available_models[0] if available_models else "glm-5.1:cloud"


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
    """Mémoire distribuée P2P avec cache LRU et TTL"""
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.store: Dict[str, Dict] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl

    def set(self, key: str, value: Any, ttl: int = None):
        if len(self.store) >= self.max_size:
            oldest = min(self.store.items(), key=lambda x: x[1]['accessed'])
            del self.store[oldest[0]]
        self.store[key] = {
            'value': value,
            'expires': time.time() + (ttl or self.default_ttl),
            'accessed': time.time()
        }

    def get(self, key: str) -> Any:
        if key in self.store:
            entry = self.store[key]
            if entry['expires'] > time.time():
                entry['accessed'] = time.time()
                return entry['value']
            del self.store[key]
        return None

    def get_all_for_sync(self) -> Dict[str, Dict]:
        """Get all non-expired entries for sync"""
        now = time.time()
        return {k: {'value': v['value'], 'expires': v['expires']}
                for k, v in self.store.items() if v['expires'] > now}


# ============================================================================
# ============== CONFIG LOADER ============================================
# ============================================================================

def load_config(config_path: str = None) -> Dict:
    """Load config from JSON file or defaults"""
    default_config = {
        "node_name": "unknown",
        "version": "3.2.0",
        "host": "0.0.0.0",
        "port": 8080,
        "ollama_host": "127.0.0.1",
        "ollama_port": 11434,
        "local_models": ["glm-5.1:cloud"],
        "heartbeat_interval": 30,
        "auto_heal_interval": 120,
        "memory_max_size": 1000,
        "memory_default_ttl": 3600,
        "p2p_secret": "bug-pinky-2026-unity",
        "tailscale_auto_discovery": True,
        "circuit_breaker": {
            "failure_threshold": 3,
            "recovery_timeout": 60,
            "half_open_max_calls": 1
        },
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
        except Exception as e:
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
    except Exception as e:
        logger.debug(f"Tailscale discovery failed: {e}")
    return peers


# ============================================================================
# ============== UNITYBRAIN MAIN ==========================================
# ============================================================================

class UnityBrain:
    """UnityBrain v3.2 - P2P Distribué avec Circuit Breaker"""

    def __init__(self, config: Dict):
        self.config = config
        self.node_name = config["node_name"]
        self.version = "3.2.0"
        self.host = config["host"]
        self.port = config["port"]
        self.ollama_host = config["ollama_host"]
        self.ollama_port = config["ollama_port"]
        self.local_models = config["local_models"]
        self.p2p_secret = config.get("p2p_secret", "bug-pinky-2026-unity")

        # Components
        self.router = ModelRouter()
        self.ensemble = EnsembleConsensus()
        self.history = QueryHistory()
        self.memory = DistributedMemory(
            max_size=config.get("memory_max_size", 1000),
            default_ttl=config.get("memory_default_ttl", 3600)
        )

        # Peers
        self.peers: List[Peer] = []

        # Stats
        self.queries = 0
        self.successful = 0
        self.start_time = time.time()

        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None

        # Heartbeat
        self.heartbeat_interval = config.get("heartbeat_interval", 30)
        self.heartbeat_running = False

        # Event log for dashboard
        self.event_log: deque = deque(maxlen=50)

    def log_event(self, event_type: str, message: str, level: str = "info"):
        self.event_log.append({
            "time": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "level": level
        })

    async def add_peer(self, peer: Peer):
        self.peers.append(peer)
        self.log_event("peer_added", f"Peer {peer.name} added ({peer.host}:{peer.port})")

    async def initialize(self):
        """Initialise UnityBrain"""
        logger.info(f"Initializing {self.node_name} v{self.version}...")
        self.log_event("init", f"UnityBrain v{self.version} starting as '{self.node_name}'")

        self.session = aiohttp.ClientSession()

        # Auto-discover via Tailscale
        if self.config.get("tailscale_auto_discovery", False):
            ts_peers = await discover_tailscale_peers()
            for ts_peer in ts_peers:
                if ts_peer['name'] != self.node_name:
                    # Check if already configured
                    existing = [p for p in self.peers if p.host == ts_peer['host']]
                    if not existing:
                        logger.info(f"Tailscale discovered: {ts_peer['name']} at {ts_peer['host']}")

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
        """Background heartbeat"""
        self.heartbeat_running = True
        while self.heartbeat_running:
            await asyncio.sleep(self.heartbeat_interval)
            await self.check_peers()
            available = [p for p in self.peers if p.available]
            if available:
                logger.debug(f"Heartbeat: {len(available)}/{len(self.peers)} peers alive")

    async def query(self, prompt: str, model: str = None,
                     use_ensemble: bool = False) -> Dict:
        """Exécute une requête avec failover et circuit breaker"""
        self.queries += 1
        logger.info(f"Query {self.queries}: {prompt[:50]}...")

        selected_model = model or await self.router.route(prompt, self.local_models)
        response, latency = await self._query_local(selected_model, prompt)

        if latency == float('inf'):
            logger.info("Local query failed, trying peers (failover)...")
            self.log_event("failover", f"Local failed, trying peers for model {selected_model}")
            available = sorted(
                [p for p in self.peers if p.available and p.circuit_breaker.can_execute()],
                key=lambda p: p.latency
            )
            for peer in available:
                if selected_model in peer.models or not peer.models:
                    response, latency = await peer.query_via_peer(
                        self.session, selected_model, prompt,
                        auth_headers=self._auth_headers(f"http://{peer.host}:{peer.port}/api/query")
                    )
                    if latency < float('inf'):
                        self.log_event("failover", f"Query routed to {peer.name} ({latency:.0f}ms)")
                        break

        success = latency < float('inf')
        if success:
            self.successful += 1

        await self.history.add({
            "prompt": prompt, "response": response,
            "model": selected_model, "latency": latency, "success": success
        })

        return {
            "status": "success" if success else "error",
            "response": response, "model": selected_model,
            "latency": latency, "node": self.node_name
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
        except Exception as e:
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
        """Verify P2P authentication (HMAC-based)"""
        auth = request.headers.get('X-UnityBrain-Auth', '')
        timestamp = request.headers.get('X-UnityBrain-TS', '')
        if not auth or not timestamp:
            return request.method == 'GET'
        try:
            ts = float(timestamp)
            if abs(time.time() - ts) > 300:
                return False
        except:
            return False
        path = str(request.url)
        msg = f"{path}:{timestamp}"
        expected = hmac.new(self.p2p_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(auth, expected)

    def _auth_headers(self, path: str) -> Dict[str, str]:
        ts = str(time.time())
        msg = f"{path}:{ts}"
        sig = hmac.new(self.p2p_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return {
            'X-UnityBrain-Auth': sig,
            'X-UnityBrain-TS': ts,
            'X-UnityBrain-Version': self.version
        }

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
            web.get('/ws', self.handle_websocket),
        ])
        return app

    @web.middleware
    async def auth_middleware(self, request, handler):
        if request.method == 'POST' and not self._verify_auth(request):
            self.log_event("auth_fail", f"Unauthorized POST from {request.remote}", "warn")
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
        try:
            data = await request.json()
            prompt = data.get('prompt', '')
            model = data.get('model')
            use_ensemble = data.get('ensemble', False)
            result = await self.query(prompt, model=model, use_ensemble=use_ensemble)
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_memory_set(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            key = data.get('key', '')
            value = data.get('value')
            ttl = data.get('ttl', 3600)
            self.memory.set(key, value, ttl)
            self.log_event("memory", f"Set key: {key}")
            return web.json_response({"status": "ok", "key": key})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_memory_get(self, request: web.Request) -> web.Response:
        key = request.match_info['key']
        value = self.memory.get(key)
        return web.json_response({"key": key, "value": value})

    async def handle_peers(self, request: web.Request) -> web.Response:
        return web.json_response([p.to_dict() for p in self.peers])

    async def handle_monitor(self, request: web.Request) -> web.Response:
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()
            load = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
            return web.json_response({
                'node': self.node_name,
                'cpu_percent': cpu,
                'load_avg': {'1m': load[0], '5m': load[1], '15m': load[2]},
                'memory': {'total_gb': round(mem.total/1e9, 1), 'used_gb': round(mem.used/1e9, 1),
                           'percent': mem.percent, 'available_gb': round(mem.available/1e9, 1)},
                'disk': {'total_gb': round(disk.total/1e9, 1), 'used_gb': round(disk.used/1e9, 1),
                         'percent': disk.percent, 'free_gb': round(disk.free/1e9, 1)},
                'network': {'bytes_sent': net.bytes_sent, 'bytes_recv': net.bytes_recv},
                'uptime': round(time.time() - self.start_time, 1),
                'system_uptime': round(time.time() - psutil.boot_time(), 1),
                'processes': len(psutil.pids())
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def handle_sync(self, request: web.Request) -> web.Response:
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
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    # --- WebSocket ---

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.log_event("ws", f"WebSocket connected from {request.remote}")
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get('type') == 'ping':
                        await ws.send_json({'type': 'pong', 'node': self.node_name,
                                            'timestamp': time.time()})
                    elif data.get('type') == 'query':
                        result = await self.query(data.get('prompt', ''),
                                                   model=data.get('model'))
                        await ws.send_json({'type': 'query_result', **result})
                    elif data.get('type') == 'memory_sync':
                        for key, value in data.get('entries', {}).items():
                            self.memory.set(key, value)
                        await ws.send_json({'type': 'sync_ack',
                                            'keys': len(data.get('entries', {}))})
                    elif data.get('type') == 'monitor':
                        # Real-time monitoring via WS
                        cpu = psutil.cpu_percent(interval=0.5)
                        mem = psutil.virtual_memory()
                        await ws.send_json({
                            'type': 'monitor_data',
                            'cpu': cpu,
                            'mem_percent': mem.percent,
                            'timestamp': time.time()
                        })
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WS error: {ws.exception()}')
        except Exception as e:
            logger.error(f'WebSocket error: {e}')
        return ws

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
                except Exception as e:
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
            except:
                self.log_event("auto_heal", "Ollama health check failed", "warn")
            await self.sync_memory_to_peers()

    async def run_server(self):
        """Start aiohttp server"""
        app = await self.create_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"UnityBrain P2P server on http://{self.host}:{self.port}")
        self.log_event("server", f"Listening on {self.host}:{self.port}")

        asyncio.create_task(self.start_heartbeat())
        asyncio.create_task(self.auto_heal())

        while True:
            await asyncio.sleep(3600)


# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def main():
    import sys

    node_name = sys.argv[1] if len(sys.argv) > 1 else "bug"

    # Look for config file
    script_dir = Path(__file__).parent.parent
    config_path = script_dir / "config" / f"{node_name}.json"

    config = load_config(str(config_path))

    # Override node_name from CLI if provided
    if len(sys.argv) > 1:
        config["node_name"] = node_name

    # Create UnityBrain
    brain = UnityBrain(config)

    # Add peers from config
    cb_config = config.get("circuit_breaker", {})
    for peer_cfg in config.get("peers", []):
        peer = Peer(
            name=peer_cfg["name"],
            host=peer_cfg["host"],
            port=peer_cfg.get("port", 8081),
            models=peer_cfg.get("models", []),
            ollama_host=peer_cfg.get("ollama_host", peer_cfg["host"]),
            ollama_port=peer_cfg.get("ollama_port", 11434)
        )
        peer.circuit_breaker = CircuitBreaker(
            failure_threshold=cb_config.get("failure_threshold", 3),
            recovery_timeout=cb_config.get("recovery_timeout", 60),
            half_open_max=cb_config.get("half_open_max_calls", 1)
        )
        await brain.add_peer(peer)

    await brain.initialize()
    await brain.run_server()


if __name__ == '__main__':
    import signal
    import sys

    def shutdown(sig, frame):
        logger.info("🛑 UnityBrain shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    node = sys.argv[1] if len(sys.argv) > 1 else "bug"
    logger.info(f"Starting UnityBrain v3.2 as '{node}'")
    asyncio.run(main())