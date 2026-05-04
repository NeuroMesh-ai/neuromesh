#!/usr/bin/env python3
"""
🌐 UNITYBRAIN v4.1.0 — RÉSEAU P2P DISTRIBUÉ
===============================================
v4.1.0 Multi-LLM provider support:
1. ProviderAdapter base class — OllamaProvider, OpenAIProvider, AnthropicProvider
2. Config `providers` section — connect any LLM API alongside Ollama
3. _query_local() routes to correct provider based on model name
4. ModelRouter considers all provider models
5. Backward compatible — if no providers, falls back to ollama_host/ollama_port

v4.0.1 Bug fixes:
1. Memory gossip: send correct payload for memory_update messages
2. Outgoing WS: connect to peers via WS for real-time sync
3. Memory sync: decoupled from auto_heal into own 30s loop
4. Auth: fix timestamp race in _auth_headers
5. Discovery: skip stale/duplicate Tailscale peers

v4.0 Features:
1. WebSocket temps réel — bidirectional WS with typed messages, reconnect, heartbeat
2. Auth renforcée — Ed25519 identity, challenge-response, Web of Trust, stealth mode
3. Mémoire Sync P2P — CRDT-based, gossip protocol, vector clocks, last-write-wins
4. Clean architecture — lightweight, async, brain_llm non-blocking

HTTP REST API remains available (retrocompatibility). WS is an ADDON.
"""

import asyncio
import aiohttp
from aiohttp import web
import json
import time
import socket
import os
import uuid
import psutil
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import deque
from pathlib import Path
import logging.handlers

# ============================================================================
# LOGGING
# ============================================================================

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
# FEATURE 2: ED25519 IDENTITY & WEB OF TRUST
# ============================================================================

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import BadSignatureError
    HAS_NACL = True
except ImportError:
    HAS_NACL = False
    logger.info("PyNaCl not available — using HMAC fallback for Ed25519 identity")


class NodeIdentity:
    """Ed25519-based node identity. Self-generated, no central registry.
    Falls back to HMAC if PyNaCl is not installed.
    """
    def __init__(self, name: str, secret_seed: str = None):
        self.name = name
        self.created = time.time()

        if HAS_NACL:
            if secret_seed:
                seed = hashlib.sha256(secret_seed.encode()).digest()[:32]
                self._signing_key = SigningKey(seed)
            else:
                self._signing_key = SigningKey.generate()
            self._verify_key = self._signing_key.verify_key
            self.public_key_hex = self._verify_key.encode().hex()
            self.fingerprint = self.public_key_hex[:16]
        else:
            # HMAC fallback — deterministic identity from secret
            seed = secret_seed or os.environ.get("P2P_SECRET", "changeme")
            self._fallback_secret = hashlib.sha256(f"{seed}:{name}".encode()).digest()
            self.public_key_hex = self._fallback_secret.hex()
            self.fingerprint = self.public_key_hex[:16]

    def sign(self, message: str) -> str:
        """Sign a message. Returns hex signature."""
        if HAS_NACL:
            sig = self._signing_key.sign(message.encode())
            return sig.signature.hex()
        else:
            import hmac as hmac_mod
            return hmac_mod.new(self._fallback_secret, message.encode(), hashlib.sha256).hexdigest()

    def verify(self, message: str, signature_hex: str, public_key_hex: str = None) -> bool:
        """Verify a signed message. Tries Ed25519 first, then falls back to HMAC."""
        # Try Ed25519 if PyNaCl is available AND the key looks like an Ed25519 key
        # (Ed25519 public keys are 32 bytes = 64 hex chars, but so are HMAC fallback keys)
        # We need to try Ed25519 first, and fall back to HMAC if it fails.
        if HAS_NACL and public_key_hex:
            try:
                vk = VerifyKey(bytes.fromhex(public_key_hex))
                vk.verify(message.encode(), bytes.fromhex(signature_hex))
                return True
            except (BadSignatureError, ValueError, TypeError, Exception):
                # Ed25519 verification failed — fall through to HMAC
                pass

        # HMAC verification (fallback or when Ed25519 fails)
        import hmac as hmac_mod
        # If verifying with our own key, use our fallback_secret directly
        if public_key_hex == self.public_key_hex and HAS_NACL:
            # Both nodes use Ed25519 — Ed25519 already failed, so this is a genuine failure
            return False
        # Use the public_key_hex as HMAC key (works for HMAC-fallback nodes)
        verify_key = bytes.fromhex(public_key_hex) if public_key_hex else self._fallback_secret
        expected = hmac_mod.new(verify_key, message.encode(), hashlib.sha256).hexdigest()
        return hmac_mod.compare_digest(expected, signature_hex)

    def challenge(self) -> Dict:
        """Generate a challenge for another node."""
        nonce = uuid.uuid4().hex
        timestamp = int(time.time())
        challenge_str = f"{self.name}:{nonce}:{timestamp}"
        return {
            "type": "auth_challenge",
            "from": self.name,
            "from_key": self.public_key_hex,
            "nonce": nonce,
            "timestamp": timestamp,
            "challenge": challenge_str,
            "signature": self.sign(challenge_str)
        }

    def respond_challenge(self, challenge: Dict) -> Dict:
        """Respond to an auth challenge."""
        challenge_str = challenge["challenge"]
        return {
            "type": "auth_response",
            "from": self.name,
            "from_key": self.public_key_hex,
            "nonce": challenge["nonce"],
            "response": self.sign(challenge_str),
            "signature": self.sign(f"{self.name}:{challenge['nonce']}")
        }

    def verify_challenge_response(self, response: Dict) -> bool:
        """Verify a challenge response from another node."""
        # Anti-replay: timestamp must be within 60s
        if abs(time.time() - response.get("timestamp", 0)) > 60:
            return False
        # Verify the signature
        challenge_str = response.get("challenge", "")
        return self.verify(challenge_str, response.get("response", ""), response.get("from_key", ""))

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "public_key": self.public_key_hex,
            "fingerprint": self.fingerprint,
            "created": self.created
        }


class WebOfTrust:
    """Decentralized trust via peer signatures.
    Nodes sign each other's public keys. Trust is transitive.
    """
    def __init__(self):
        self.trust_edges: Dict[str, Set[str]] = {}  # public_key -> set of trusted public_keys
        self.signed_by: Dict[str, Set[str]] = {}     # public_key -> set of signers

    def add_trust(self, signer_key: str, trusted_key: str):
        """Record that signer_key vouches for trusted_key."""
        if signer_key not in self.trust_edges:
            self.trust_edges[signer_key] = set()
        self.trust_edges[signer_key].add(trusted_key)
        if trusted_key not in self.signed_by:
            self.signed_by[trusted_key] = set()
        self.signed_by[trusted_key].add(signer_key)

    def trust_score(self, target_key: str, max_depth: int = 3) -> float:
        """Calculate trust score for a key based on transitive trust.
        More signers = higher trust. Direct signers count more than transitive.
        """
        direct = len(self.signed_by.get(target_key, set()))
        if direct == 0:
            return 0.0
        # Simple scoring: direct signers weighted 1.0, each hop halves
        score = direct * 1.0
        visited = {target_key}
        frontier = self.signed_by.get(target_key, set()).copy()
        depth = 1
        while frontier and depth < max_depth:
            next_frontier = set()
            for key in frontier:
                if key in visited:
                    continue
                visited.add(key)
                weight = 1.0 / (2 ** depth)
                signers = self.signed_by.get(key, set())
                score += len(signers & visited) * weight
                next_frontier |= signers
            frontier = next_frontier
            depth += 1
        return min(score, 10.0)  # Cap at 10

    def is_trusted(self, target_key: str, min_score: float = 1.0) -> bool:
        return self.trust_score(target_key) >= min_score


# ============================================================================
# FEATURE 2: RATE LIMITING
# ============================================================================

class RateLimiter:
    """Token bucket rate limiter per node."""
    def __init__(self, rate: float = 10.0, burst: int = 20):
        self.rate = rate          # tokens per second
        self.burst = burst        # max bucket size
        self._buckets: Dict[str, Dict] = {}  # node_key -> {tokens, last_refill}

    def _refill(self, key: str):
        bucket = self._buckets.setdefault(key, {"tokens": float(self.burst), "last": time.time()})
        now = time.time()
        elapsed = now - bucket["last"]
        bucket["tokens"] = min(self.burst, bucket["tokens"] + elapsed * self.rate)
        bucket["last"] = now

    def allow(self, key: str) -> bool:
        self._refill(key)
        if self._buckets[key]["tokens"] >= 1.0:
            self._buckets[key]["tokens"] -= 1.0
            return True
        return False

    def to_dict(self) -> Dict:
        return {"rate": self.rate, "burst": self.burst, "active_nodes": len(self._buckets)}


# ============================================================================
# CIRCUIT BREAKER (unchanged from v3.3, but cleaner)
# ============================================================================

class CircuitBreaker:
    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

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
        else:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.STATE_OPEN

    @property
    def is_available(self) -> bool:
        return self.can_execute()

    def to_dict(self) -> Dict:
        return {"state": self.state, "failures": self.failure_count,
                "last_failure": self.last_failure_time}


# ============================================================================
# FEATURE 3: CRDT-BASED MEMORY WITH VECTOR CLOCKS
# ============================================================================

class VectorClock:
    """Vector clock for ordering distributed events."""
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.clocks: Dict[str, int] = {}

    def increment(self):
        self.clocks[self.node_id] = self.clocks.get(self.node_id, 0) + 1

    def merge(self, other: Dict[str, int]):
        for key, value in other.items():
            self.clocks[key] = max(self.clocks.get(key, 0), value)

    def happens_before(self, other: Dict[str, int]) -> bool:
        """Check if this clock happens-before other."""
        all_leq = True
        any_lt = False
        for key in set(list(self.clocks.keys()) + list(other.keys())):
            mine = self.clocks.get(key, 0)
            theirs = other.get(key, 0)
            if mine > theirs:
                all_leq = False
            if mine < theirs:
                any_lt = True
        return all_leq and any_lt

    def is_concurrent(self, other: Dict[str, int]) -> bool:
        return not self.happens_before(other) and not self._reverse_happens_before(other)

    def _reverse_happens_before(self, other: Dict[str, int]) -> bool:
        vc_other = VectorClock(self.node_id)
        vc_other.clocks = dict(other)
        return vc_other.happens_before(self.clocks)

    def to_dict(self) -> Dict[str, int]:
        return dict(self.clocks)

    @classmethod
    def from_dict(cls, node_id: str, data: Dict[str, int]):
        vc = cls(node_id)
        vc.clocks = dict(data)
        return vc


class CRDTMemory:
    """CRDT-based distributed memory with Last-Write-Wins.
    Uses vector clocks for ordering. Gossip protocol for propagation.
    """
    def __init__(self, node_id: str, max_size: int = 1000, default_ttl: int = 3600):
        self.node_id = node_id
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.vector_clock = VectorClock(node_id)
        self.store: Dict[str, Dict] = {}  # key -> {value, version, tombstone, metadata}

    def set(self, key: str, value: Any, ttl: int = None, author: str = None):
        """Set a value. Increments vector clock. Last-write-wins on conflict."""
        self.vector_clock.increment()
        version = self.vector_clock.to_dict()
        existing = self.store.get(key)
        # Last-write-wins: if existing has same or newer version, skip
        if existing and not self._is_newer(version, existing.get("version", {})):
            # Concurrent write — last-write-wins by timestamp
            existing_ts = existing.get("metadata", {}).get("timestamp", 0)
            new_ts = time.time()
            if new_ts <= existing_ts:
                return  # existing is newer, skip
        self.store[key] = {
            "value": value,
            "version": version,
            "tombstone": False,
            "expires": time.time() + (ttl or self.default_ttl),
            "metadata": {
                "author": author or self.node_id,
                "timestamp": time.time(),
                "node_id": self.node_id
            }
        }
        # Evict if over max_size (LRU by access time)
        while len(self.store) > self.max_size:
            oldest_key = min(self.store, key=lambda k: self.store[k]["metadata"]["timestamp"])
            del self.store[oldest_key]

    def _is_newer(self, version_a: Dict, version_b: Dict) -> bool:
        """Check if version_a is strictly newer than version_b."""
        a_greater = False
        for key in set(list(version_a.keys()) + list(version_b.keys())):
            va = version_a.get(key, 0)
            vb = version_b.get(key, 0)
            if va < vb:
                return False
            if va > vb:
                a_greater = True
        return a_greater

    def get(self, key: str) -> Any:
        entry = self.store.get(key)
        if not entry:
            return None
        if entry["tombstone"]:
            return None
        if entry["expires"] < time.time():
            del self.store[key]
            return None
        return entry["value"]

    def delete(self, key: str) -> bool:
        if key in self.store:
            self.vector_clock.increment()
            self.store[key]["tombstone"] = True
            self.store[key]["version"] = self.vector_clock.to_dict()
            self.store[key]["metadata"]["timestamp"] = time.time()
            return True
        return False

    def get_all_for_sync(self) -> Dict[str, Dict]:
        """Get all non-expired, non-tombstoned entries for P2P sync."""
        now = time.time()
        return {k: v for k, v in self.store.items()
                if not v["tombstone"] and v["expires"] > now}

    def get_delta_since(self, vector_clock: Dict[str, int]) -> Dict[str, Dict]:
        """Get entries that are newer than the given vector clock (for incremental sync)."""
        result = {}
        for key, entry in self.store.items():
            if entry["tombstone"] and entry["expires"] < time.time():
                continue
            entry_vc = entry.get("version", {})
            # Entry is newer if any component is greater
            is_newer = False
            for node, tick in entry_vc.items():
                if tick > vector_clock.get(node, 0):
                    is_newer = True
                    break
            if is_newer:
                result[key] = entry
        return result

    def merge_from_sync(self, data: Dict[str, Dict]) -> int:
        """Merge entries from a P2P sync. Returns count of merged entries."""
        merged = 0
        for key, entry in data.items():
            existing = self.store.get(key)
            if not existing:
                self.store[key] = entry
                self.vector_clock.merge(entry.get("version", {}))
                merged += 1
            else:
                # Last-write-wins by timestamp
                existing_ts = existing.get("metadata", {}).get("timestamp", 0)
                new_ts = entry.get("metadata", {}).get("timestamp", 0)
                if new_ts > existing_ts:
                    self.store[key] = entry
                    self.vector_clock.merge(entry.get("version", {}))
                    merged += 1
                elif new_ts == existing_ts:
                    # Same timestamp: deterministic tiebreak by node_id
                    if entry.get("metadata", {}).get("node_id", "") > existing.get("metadata", {}).get("node_id", ""):
                        self.store[key] = entry
                        self.vector_clock.merge(entry.get("version", {}))
                        merged += 1
        return merged

    def stats(self) -> Dict:
        active = sum(1 for v in self.store.values() if not v["tombstone"] and v["expires"] > time.time())
        return {
            "total_entries": len(self.store),
            "active_entries": active,
            "vector_clock": self.vector_clock.to_dict()
        }


# ============================================================================
# PEER DISCOVERY
# ============================================================================

class PeerDiscovery:
    """Dynamic peer discovery: Tailscale, mDNS, config fallback, peer referral."""

    def __init__(self, node_name: str, own_host: str, own_port: int,
                 config_peers: List[Dict] = None):
        self.node_name = node_name
        self.own_host = own_host
        self.own_port = own_port
        self.known_peers: Dict[str, Dict] = {}
        self.config_peers = config_peers or []
        self.last_discovery = 0
        self.discovery_interval = 300

    async def discover_all(self) -> List[Dict]:
        found = {}
        for p in self.config_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            found[key] = p

        ts_peers = await self._discover_tailscale()
        for p in ts_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            if key not in found:
                found[key] = p

        mdns_peers = await self._discover_mdns()
        for p in mdns_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            if key not in found:
                found[key] = p

        self.known_peers = found
        self.last_discovery = time.time()
        if found:
            logger.info(f"Discovery: found {len(found)} potential peers")
        return list(found.values())

    async def _discover_tailscale(self) -> List[Dict]:
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
                        if peer.get('HostName') == self.node_name:
                            continue
                        own_ts_ip = status.get('Self', {}).get('TailscaleIPs', [])
                        if own_ts_ip and any(ip in own_ts_ip for ip in ips):
                            continue
                        # Bug #5 fix: skip if same IP as a config peer but different port (duplicate)
                        # Also skip if IP matches our own Tailscale IP
                        is_dup = False
                        for cp in self.config_peers:
                            if ips and ips[0] == cp.get('host') and 8081 != cp.get('port', 8080):
                                is_dup = True
                                break
                        if is_dup:
                            continue
                        if ips:
                            peers.append({
                                'name': peer.get('HostName', 'unknown'),
                                'host': ips[0],
                                'port': 8081,
                                'source': 'tailscale'
                            })
        except (OSError, json.JSONDecodeError, asyncio.TimeoutError):
            pass
        return peers

    async def _discover_mdns(self) -> List[Dict]:
        """Simple UDP broadcast for local network discovery."""
        peers = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2)
            msg = json.dumps({
                'type': 'unitybrain_discovery',
                'node': self.node_name,
                'port': self.own_port
            }).encode()
            for subnet in ['192.168.1.255', '192.168.129.255', '100.64.0.255']:
                try:
                    sock.sendto(msg, (subnet, 8090))
                except OSError:
                    pass
            sock.close()
        except OSError:
            pass
        return peers


# ============================================================================
# LOAD BALANCER
# ============================================================================

class LoadBalancer:
    """Route queries based on latency, model availability, success rate, CB state."""

    def __init__(self):
        self.node_scores: Dict[str, float] = {}

    def calculate_score(self, peer, model: str = None) -> float:
        if peer.latency == float('inf') or not peer.available:
            return float('inf')
        latency_score = min(peer.latency / 10, 100)
        model_penalty = 0
        if model and model not in peer.models and peer.models:
            model_penalty = 50
        success_score = 100 - (peer.success_rate * 100)
        cb_penalty = 0
        if peer.circuit_breaker.state != CircuitBreaker.STATE_CLOSED:
            cb_penalty = 100
        return (latency_score * 0.4) + (model_penalty * 0.3) + (success_score * 0.2) + (cb_penalty * 0.1)

    def select_best_peer(self, peers: list, model: str = None) -> Optional[Any]:
        if not peers:
            return None
        best = None
        best_score = float('inf')
        for peer in peers:
            if not peer.circuit_breaker.can_execute():
                continue
            score = self.calculate_score(peer, model)
            if score < best_score:
                best_score = score
                best = peer
        return best

    def should_handle_locally(self, local_cpu: float, local_mem_pct: float,
                               peer_count: int) -> bool:
        if peer_count == 0:
            return True
        if local_cpu < 50 and local_mem_pct < 70:
            return True
        return False


# ============================================================================
# PEER
# ============================================================================

class Peer:
    def __init__(self, name: str, host: str, port: int, models: List[str],
                 public_key_hex: str = None):
        self.name = name
        self.host = host
        self.port = port
        self.models = models
        self.public_key_hex = public_key_hex or ""
        self.available = True
        self.latency = float('inf')
        self.success_rate = 1.0
        self.circuit_breaker = CircuitBreaker()
        self.last_seen = 0
        self.model_stats: Dict[str, Dict] = {}

    async def ping(self, session: aiohttp.ClientSession, auth_headers: Dict = None) -> float:
        start = time.time()
        try:
            headers = auth_headers or {}
            async with session.get(
                f'http://{self.host}:{self.port}/api/ping',
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    self.latency = (time.time() - start) * 1000
                    self.available = True
                    self.last_seen = time.time()
                    self.circuit_breaker.record_success()
                    return self.latency
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            pass
        self.available = False
        self.circuit_breaker.record_failure()
        self.latency = float('inf')
        return float('inf')

    def _update_stats(self, model: str, success: bool, latency: float):
        if model not in self.model_stats:
            self.model_stats[model] = {"queries": 0, "success": 0, "avg_latency": 0}
        stats = self.model_stats[model]
        stats["queries"] += 1
        if success:
            stats["success"] += 1
        stats["avg_latency"] = (stats["avg_latency"] * (stats["queries"] - 1) + latency) / stats["queries"]

    def to_dict(self) -> Dict:
        return {
            "name": self.name, "host": self.host, "port": self.port,
            "models": self.models, "available": self.available,
            "latency": round(self.latency, 1), "public_key": self.public_key_hex,
            "circuit_breaker": self.circuit_breaker.to_dict()
        }


# ============================================================================
# MODEL ROUTING
# ============================================================================

# ========================================================================
# MULTI-LLM PROVIDER ADAPTERS
# ========================================================================

class ProviderAdapter:
    """Base class for LLM providers. Each adapter knows how to query its API."""
    provider_type: str = "base"

    def __init__(self, name: str, config: Dict):
        self.name = name
        self.enabled = config.get("enabled", True)
        self.models = config.get("models", [])

    async def query(self, session: aiohttp.ClientSession, model: str, prompt: str, timeout: int = 120) -> Dict:
        raise NotImplementedError

    def supports(self, model: str) -> bool:
        if not self.models:
            return True  # Empty models list = supports all
        return model in self.models or model.startswith(tuple(self.models))


class OllamaProvider(ProviderAdapter):
    """Ollama API provider (default, backward compatible)."""
    provider_type = "ollama"

    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 11434)
        self.base_url = f"http://{self.host}:{self.port}"

    async def query(self, session: aiohttp.ClientSession, model: str, prompt: str, timeout: int = 120) -> Dict:
        try:
            async with session.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "response": data.get("response", ""),
                        "model": model,
                        "source": f"ollama:{self.name}",
                        "tokens_used": data.get("eval_count", 0)
                    }
                return {"response": "", "model": model, "source": f"ollama:{self.name}",
                        "error": f"Ollama {self.name}: HTTP {resp.status}"}
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionRefusedError) as e:
            return {"response": "", "model": model, "source": f"ollama:{self.name}", "error": str(e)}


class OpenAIProvider(ProviderAdapter):
    """OpenAI Chat Completions API provider. Also works for any OpenAI-compatible API."""
    provider_type = "openai"

    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")

    async def query(self, session: aiohttp.ClientSession, model: str, prompt: str, timeout: int = 120) -> Dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        try:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    return {
                        "response": content,
                        "model": model,
                        "source": f"openai:{self.name}",
                        "tokens_used": usage.get("total_tokens", 0)
                    }
                text = await resp.text()
                return {"response": "", "model": model, "source": f"openai:{self.name}",
                        "error": f"OpenAI {self.name}: HTTP {resp.status} {text[:200]}"}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return {"response": "", "model": model, "source": f"openai:{self.name}", "error": str(e)}


class AnthropicProvider(ProviderAdapter):
    """Anthropic Messages API provider."""
    provider_type = "anthropic"

    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.anthropic.com").rstrip("/")

    async def query(self, session: aiohttp.ClientSession, model: str, prompt: str, timeout: int = 120) -> Dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            async with session.post(
                f"{self.base_url}/v1/messages",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("content", [{}])
                    text = content[0].get("text", "") if content else ""
                    usage = data.get("usage", {})
                    return {
                        "response": text,
                        "model": model,
                        "source": f"anthropic:{self.name}",
                        "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    }
                text = await resp.text()
                return {"response": "", "model": model, "source": f"anthropic:{self.name}",
                        "error": f"Anthropic {self.name}: HTTP {resp.status} {text[:200]}"}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return {"response": "", "model": model, "source": f"anthropic:{self.name}", "error": str(e)}


class OpenAICompatibleProvider(OpenAIProvider):
    """Alias for OpenAI provider — works with any OpenAI-compatible endpoint (LM Studio, vLLM, etc.)."""
    provider_type = "openai_compatible"


PROVIDER_TYPES = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


class ModelRouter:
    CODE_KEYWORDS = ['code', 'program', 'script', 'debug', 'implement', 'class ', 'def ', 'async ']
    REASONING_KEYWORDS = ['explain', 'why', 'how does', 'analyze', 'compare', 'what if']
    CREATIVE_KEYWORDS = ['write', 'story', 'poem', 'creative', 'imagine', 'design']

    def route(self, prompt: str, available_models: List[str]) -> str:
        p = prompt.lower()
        if any(kw in p for kw in self.CODE_KEYWORDS):
            for m in available_models:
                if 'coder' in m or 'code' in m or 'deepseek' in m:
                    return m
        if any(kw in p for kw in self.REASONING_KEYWORDS):
            for m in available_models:
                if 'reason' in m or 'think' in m or 'qwen' in m:
                    return m
        if available_models:
            return available_models[0]
        return "glm-5.1:cloud"

    def get_fallback(self, model: str, available_models: List[str]) -> Optional[str]:
        if model in available_models:
            return model
        if available_models:
            return available_models[0]
        return None


# ============================================================================
# ENSEMBLE CONSENSUS
# ============================================================================

class EnsembleConsensus:
    def __init__(self, agreement_threshold: float = 0.6):
        self.agreement_threshold = agreement_threshold

    async def query_ensemble(self, session: aiohttp.ClientSession,
                              peers: list, prompt: str, model: str = None) -> Dict:
        results = []
        for peer in peers:
            if peer.available and peer.circuit_breaker.can_execute():
                try:
                    async with session.post(
                        f'http://{peer.host}:{peer.port}/api/query',
                        json={"prompt": prompt, "model": model},
                        timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results.append(data.get("response", ""))
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass
        if not results:
            return {"response": "", "consensus": 0, "sources": 0}
        # Simple consensus: most common response wins
        from collections import Counter
        counter = Counter(r[:200] for r in results)
        best, count = counter.most_common(1)[0]
        consensus = count / len(results) if results else 0
        # Return the full response that matches the best prefix
        for r in results:
            if r[:200] == best:
                return {"response": r, "consensus": consensus, "sources": len(results)}
        return {"response": results[0], "consensus": consensus, "sources": len(results)}


# ============================================================================
# QUERY HISTORY
# ============================================================================

class QueryHistory:
    def __init__(self, max_entries: int = 1000):
        self._entries: deque = deque(maxlen=max_entries)

    async def add(self, query: Dict):
        self._entries.append({**query, "timestamp": time.time()})

    async def get(self, limit: int = 10) -> List[Dict]:
        return list(self._entries)[-limit:]


# ============================================================================
# CONFIG LOADER
# ============================================================================

def load_config(config_path: str = None) -> Dict:
    """Load config from JSON file or defaults."""
    default_config = {
        "node_name": "unknown",
        "version": "4.0.1",
        "host": "0.0.0.0",
        "port": 8080,
        "ollama_host": "127.0.0.1",
        "ollama_port": 11434,
        "local_models": ["glm-5.1:cloud"],
        "providers": {},
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
        "stealth_mode": False,
        "share_ai": False,
        "rate_limit": 10.0,
        "rate_burst": 20,
        "peers": [],
        "seed_nodes": []
    }

    if config_path and Path(config_path).exists():
        try:
            with open(config_path) as f:
                user_config = json.load(f)
            for key, value in user_config.items():
                default_config[key] = value
            logger.info(f"Config loaded from {config_path}")
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Config load failed, using defaults: {e}")

    return default_config


# ============================================================================
# UNITYBRAIN v4.0 MAIN
# ============================================================================

class UnityBrain:
    """UnityBrain v4.0 — P2P Distributed AI Network"""

    def __init__(self, config: Dict):
        self.config = config
        self.node_name = config["node_name"]
        self.version = "4.1.0"
        self.host = config["host"]
        self.port = config["port"]
        self.ollama_host = config["ollama_host"]
        self.ollama_port = config["ollama_port"]
        self.local_models = config["local_models"]
        self.p2p_secret = config.get("p2p_secret", os.environ.get("P2P_SECRET", "changeme-configure-in-config"))
        if self.p2p_secret == "changeme-configure-in-config" or self.p2p_secret == "changeme":
            logger.warning("⚠️  Using default p2p_secret — configure a strong secret in config or P2P_SECRET env var!")
        self.stealth_mode = config.get("stealth_mode", False)
        self.share_ai = config.get("share_ai", False)
        # v4.1.0: Multi-LLM providers
        self.providers: Dict[str, ProviderAdapter] = {}
        self._model_provider_map: Dict[str, str] = {}  # model_name -> provider_name
        self._init_providers(config)

        # v4.0: Node Identity (Ed25519 or HMAC fallback)
        self.identity = NodeIdentity(self.node_name, self.p2p_secret)

        # v4.0: Web of Trust
        self.web_of_trust = WebOfTrust()

        # v4.0: Rate Limiter
        self.rate_limiter = RateLimiter(
            rate=config.get("rate_limit", 10.0),
            burst=config.get("rate_burst", 20)
        )

        # Components
        self.router = ModelRouter()
        self.ensemble = EnsembleConsensus()
        self.history = QueryHistory()

    def _init_providers(self, config: Dict):
        """Initialize LLM providers from config. Falls back to Ollama-only if no providers."""
        providers_config = config.get("providers", {})

        if providers_config:
            # v4.1.0: Multi-provider mode
            for name, pconf in providers_config.items():
                ptype = pconf.get("type", "ollama")
                if not pconf.get("enabled", True):
                    logger.info(f"Provider '{name}' disabled, skipping")
                    continue
                cls = PROVIDER_TYPES.get(ptype, OllamaProvider)
                provider = cls(name, pconf)
                self.providers[name] = provider
                # Map models to provider
                for model in provider.models:
                    self._model_provider_map[model] = name
                logger.info(f"Provider '{name}' ({ptype}): {len(provider.models)} models "
                            f"- {', '.join(provider.models[:3])}{'...' if len(provider.models) > 3 else ''}")
        else:
            # v4.0 backward compat: create default Ollama provider from legacy config
            ollama_conf = {
                "type": "ollama",
                "host": config.get("ollama_host", "127.0.0.1"),
                "port": config.get("ollama_port", 11434),
                "models": config.get("local_models", ["glm-5.1:cloud"]),
                "enabled": True
            }
            self.providers["ollama"] = OllamaProvider("ollama", ollama_conf)
            for model in self.local_models:
                self._model_provider_map[model] = "ollama"
            logger.info(f"No providers configured, using Ollama at {self.ollama_host}:{self.ollama_port}")

        # Build complete local_models list from all providers
        all_models = set(self.local_models) if self.local_models else set()
        for provider in self.providers.values():
            all_models.update(provider.models)
        self.local_models = list(all_models)
        logger.info(f"Available models ({len(self.local_models)}): {', '.join(sorted(self.local_models)[:5])}{'...' if len(self.local_models) > 5 else ''}")

        # v4.0: CRDT Memory
        self.memory = CRDTMemory(
            node_id=self.node_name,
            max_size=config.get("memory_max_size", 1000),
            default_ttl=config.get("memory_default_ttl", 3600)
        )

        # Discovery
        self.discovery = PeerDiscovery(
            node_name=self.node_name,
            own_host=self.host,
            own_port=self.port,
            config_peers=config.get("peers", [])
        )

        # Load Balancer
        self.load_balancer = LoadBalancer()

        # Peers
        self.peers: List[Peer] = []

        # Stats
        self.queries = 0
        self.successful = 0
        self.start_time = time.time()

        # Brain LLM (async, non-blocking, cloud on demand)
        try:
            from brain_llm import BrainLLM
            self.brain_llm = BrainLLM(node_name=self.node_name)
        except ImportError:
            self.brain_llm = None
            logger.info("brain_llm not available (optional)")

        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None

        # Heartbeat
        self.heartbeat_interval = config.get("heartbeat_interval", 30)
        self.heartbeat_running = False

        # WebSocket clients
        self.ws_clients: Dict[str, web.WebSocketResponse] = {}  # id -> ws
        self.ws_authenticated: Set[str] = set()  # authenticated ws client ids

        # v4.0: Gossip protocol state
        self._gossip_seen: Set[str] = set()  # message IDs already seen
        self._gossip_queue: deque = deque(maxlen=200)  # pending gossip messages

        # Event log
        self.event_log: deque = deque(maxlen=50)

    def log_event(self, event_type: str, message: str, level: str = "info"):
        entry = {
            "time": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "level": level
        }
        self.event_log.append(entry)
        try:
            log_file = Path(__file__).parent.parent / "logs" / "events.jsonl"
            log_file.parent.mkdir(exist_ok=True)
            with open(log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except OSError:
            pass

    async def add_peer(self, peer: Peer):
        if peer.host in (self.host, '127.0.0.1', 'localhost') and peer.port == self.port:
            return
        # Skip duplicates
        for p in self.peers:
            if p.host == peer.host and p.port == peer.port:
                return
        self.peers.append(peer)
        self.log_event("peer_added", f"Peer {peer.name} added ({peer.host}:{peer.port})")

    def purge_dead_peers(self):
        """Remove peers with open circuit breaker and stale last_seen."""
        cutoff = time.time() - 600  # 10 min
        before = len(self.peers)
        self.peers = [p for p in self.peers
                      if p.circuit_breaker.state != CircuitBreaker.STATE_OPEN
                      or p.last_seen > cutoff]
        removed = before - len(self.peers)
        if removed:
            logger.info(f"Purged {removed} dead peers")

    async def initialize(self):
        self.session = aiohttp.ClientSession()
        self.heartbeat_running = True

        # Discover peers
        if True:
            found_peers = await self.discovery.discover_all()
            for peer_info in found_peers:
                peer = Peer(
                    name=peer_info.get('name', 'unknown'),
                    host=peer_info['host'],
                    port=peer_info.get('port', 8081),
                    models=peer_info.get('models', []),
                    public_key_hex=peer_info.get('public_key', '')
                )
                await self.add_peer(peer)

            # Ping all peers
            if self.peers:
                tasks = [p.ping(self.session) for p in self.peers]
                await asyncio.gather(*tasks, return_exceptions=True)
        else:
            logger.info("🏠 Standalone mode — skipping peer discovery")

        # Start brain_llm if available
        if self.brain_llm:
            try:
                await self.brain_llm.start()
            except Exception as e:
                logger.warning(f"brain_llm start failed: {e}")

        self.log_event("init", f"UnityBrain v{self.version} initialized as '{self.node_name}'")

    async def check_peers(self):
        if not self.session:
            return
        for peer in self.peers:
            await peer.ping(self.session)
        self.purge_dead_peers()

    async def start_heartbeat(self):
        while self.heartbeat_running:
            await asyncio.sleep(self.heartbeat_interval)
            await self.check_peers()

    async def query(self, prompt: str, model: str = None,
                    strategy: str = "auto") -> Dict:
        start = time.time()
        self.queries += 1
        result = {"response": "", "model": model or "auto", "latency_ms": 0, "source": "local"}

        # Check if should handle locally
        local_cpu = psutil.cpu_percent(interval=0.1)
        local_mem = psutil.virtual_memory()

        if strategy == "consensus":
            consensus = await self.ensemble.query_ensemble(
                self.session, self.peers, prompt, model)
            result["response"] = consensus.get("response", "")
            result["source"] = f"consensus:{consensus.get('sources', 0)}"
            result["consensus"] = consensus.get("consensus", 0)
        elif (strategy == "auto" and self.peers and
              not self.load_balancer.should_handle_locally(local_cpu, local_mem.percent, len(self.peers))):
            best = self.load_balancer.select_best_peer(self.peers, model)
            if best:
                result = await self._query_peer(best, prompt, model)
                if not result.get("response"):
                    result = await self._query_local(model, prompt)
            else:
                result = await self._query_local(model, prompt)
        else:
            result = await self._query_local(model, prompt)

        result["latency_ms"] = round((time.time() - start) * 1000, 1)
        if result.get("response"):
            self.successful += 1
        await self.history.add({"prompt": prompt[:100], "model": result.get("model", ""),
                                 "latency_ms": result["latency_ms"], "source": result.get("source", "")})
        return result

    async def _query_local(self, model: str, prompt: str) -> Dict:
        target = model or self.router.route(prompt, self.local_models)
        # Route to the correct provider
        provider_name = self._model_provider_map.get(target)
        if provider_name and provider_name in self.providers:
            provider = self.providers[provider_name]
            result = await provider.query(self.session, target, prompt)
            if not result.get("source"):
                result["source"] = f"provider:{provider_name}"
            return result
        # Fallback: try Ollama directly if model not in any provider
        try:
            async with self.session.post(
                f'http://{self.ollama_host}:{self.ollama_port}/api/generate',
                json={"model": target, "prompt": prompt, "stream": False},
                timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"response": data.get("response", ""), "model": target,
                            "source": "local", "tokens_used": data.get("eval_count", 0)}
                return {"response": "", "model": target, "source": "local",
                        "error": f"Ollama: {resp.status}"}
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionRefusedError) as e:
            return {"response": "", "model": target, "source": "local", "error": str(e)}

    async def _query_peer(self, peer: Peer, prompt: str, model: str = None) -> Dict:
        try:
            headers = self._auth_headers()
            async with self.session.post(
                f'http://{peer.host}:{peer.port}/api/query',
                json={"prompt": prompt, "model": model},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    peer._update_stats(model or "auto", True, 0)
                    return data
                peer._update_stats(model or "auto", False, 0)
                return {"response": "", "source": f"peer:{peer.name}", "error": f"Peer: {resp.status}"}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            peer._update_stats(model or "auto", False, 0)
            return {"response": "", "source": f"peer:{peer.name}", "error": str(e)}

    def get_status(self) -> Dict:
        uptime = time.time() - self.start_time
        # Build provider info
        providers_info = {}
        for name, provider in self.providers.items():
            providers_info[name] = {
                "type": provider.provider_type,
                "models": provider.models,
                "enabled": provider.enabled
            }
            if isinstance(provider, OllamaProvider):
                providers_info[name]["host"] = provider.host
                providers_info[name]["port"] = provider.port
            elif isinstance(provider, (OpenAIProvider, OpenAICompatibleProvider)):
                providers_info[name]["base_url"] = provider.base_url
            elif isinstance(provider, AnthropicProvider):
                providers_info[name]["base_url"] = provider.base_url
        return {
            "node": self.node_name,
            "version": self.version,
            "uptime": round(uptime, 0),
            "identity": self.identity.to_dict(),
                        "stealth_mode": self.stealth_mode,
            "share_ai": self.share_ai,

            "queries": {"total": self.queries, "success": self.successful,
                        "rate": round(self.successful / max(self.queries, 1) * 100, 1)},
            "memory": self.memory.stats(),
            "peers": {"total": len(self.peers),
                      "available": sum(1 for p in self.peers if p.available)},
            "ws_clients": len(self.ws_clients),
            "local_models": self.local_models,
            "providers": providers_info,
            "web_of_trust": len(self.web_of_trust.trust_edges),
            "rate_limiter": self.rate_limiter.to_dict()
        }

    # ========================================================================
    # AUTH
    # ========================================================================

    def _auth_headers(self) -> Dict[str, str]:
        """Generate auth headers for outgoing requests using BOTH Ed25519/HMAC Bearer token
        AND shared-secret HMAC. Sends both so the receiver can use either method.
        Bug #4 fix: generate timestamp once and reuse it for both signing and header."""
        ts = str(int(time.time()))
        token = self.identity.sign(f"{self.node_name}:{ts}")
        # Also compute shared-secret HMAC for v3 compat fallback
        import hmac as hmac_mod
        path = "/api/query"  # Generic path; receivers using HMAC method use their own path
        hmac_sig = hmac_mod.new(
            self.p2p_secret.encode(), f"{path}:{ts}".encode(), hashlib.sha256).hexdigest()
        return {
            'Authorization': f'Bearer {token}',
            'X-UnityBrain-Node': self.node_name,
            'X-UnityBrain-Key': self.identity.public_key_hex,
            'X-UnityBrain-TS': ts,
            'X-UnityBrain-Auth': hmac_sig,
            'X-UnityBrain-Version': '4.1.0'
        }

    def _verify_auth(self, request: web.Request) -> Optional[Dict]:
        """Verify incoming request auth. Returns identity info or None."""
        # Rate limiting first
        client_key = request.remote or "unknown"
        if not self.rate_limiter.allow(client_key):
            logger.debug(f"Auth blocked by rate limiter for {client_key}")
            return None

        # Check Bearer token (Ed25519/HMAC signature)
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            ts = request.headers.get('X-UnityBrain-TS', '')
            node_name = request.headers.get('X-UnityBrain-Node', '')
            node_key = request.headers.get('X-UnityBrain-Key', '')

            # Anti-replay: timestamp must be within 60s
            if ts:
                try:
                    if abs(time.time() - int(ts)) > 60:
                        logger.debug(f"Auth rejected: timestamp too old ({abs(time.time() - int(ts)):.0f}s)")
                        return None
                except ValueError:
                    logger.debug(f"Auth rejected: invalid timestamp '{ts}'")
                    return None

            # If we have the node's public key, verify signature
            if node_key and node_name:
                sig = auth[7:]
                challenge = f"{node_name}:{ts}"
                verified = self.identity.verify(challenge, sig, node_key)
                if verified:
                    return {"node": node_name, "public_key": node_key, "method": "ed25519"}
                else:
                    # Debug: compute expected signature to diagnose
                    import hmac as _hmac_dbg
                    _expected = _hmac_dbg.new(bytes.fromhex(node_key), challenge.encode(), hashlib.sha256).hexdigest()
                    logger.info(
                        f"Auth rejected: sig verify failed for node={node_name} "
                        f"ts={ts} challenge={challenge} "
                        f"sig={sig[:16]}... expected={_expected[:16]}..."
                    )

        # Fallback: shared secret HMAC (v3 compat)
        hmac_auth = request.headers.get('X-UnityBrain-Auth', '')
        hmac_ts = request.headers.get('X-UnityBrain-TS', '')
        if hmac_auth and hmac_ts:
            try:
                ts = float(hmac_ts)
                if abs(time.time() - ts) > 300:
                    return None
                path = request.path
                msg = f"{path}:{hmac_ts}"
                import hmac as hmac_mod
                expected_sig = hmac_mod.new(
                    self.p2p_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
                if hmac_mod.compare_digest(hmac_auth, expected_sig):
                    return {"node": "legacy", "method": "hmac"}
            except (ValueError, TypeError):
                pass
        return None

    # ========================================================================
    # STEALTH MODE
    # ========================================================================

    def _stealth_check(self, request: web.Request) -> bool:
        """In stealth mode, reject requests from unknown nodes.
        Returns True if request should be allowed."""
        if not self.stealth_mode:
            return True
        node_key = request.headers.get('X-UnityBrain-Key', '')
        if node_key and self.web_of_trust.is_trusted(node_key, min_score=0.5):
            return True
        # Check if it's a known peer
        for peer in self.peers:
            if peer.public_key_hex == node_key:
                return True
        return False

    # ========================================================================
    # HTTP API (retrocompatible REST)
    # ========================================================================

    async def create_app(self) -> web.Application:
        app = web.Application()
        # Add auth middleware manually per-handler instead of global middleware
        app.router.add_get('/', self.handle_dashboard)
        app.router.add_get('/api/status', self.handle_status)
        app.router.add_get('/api/ping', self.handle_ping)
        app.router.add_post('/api/query', self._auth_required(self.handle_query))
        app.router.add_post('/api/memory/set', self._auth_required(self.handle_memory_set))
        app.router.add_get('/api/memory/{key}', self.handle_memory_get)
        app.router.add_post('/api/memory/sync', self._auth_required(self.handle_memory_sync_push))
        app.router.add_post('/api/memory/push', self._auth_required(self.handle_memory_push))
        app.router.add_post('/api/memory/pull', self._auth_required(self.handle_memory_pull))
        app.router.add_get('/api/peers', self.handle_peers)
        app.router.add_get('/api/monitor', self.handle_monitor)
        app.router.add_get('/api/brain/status', self.handle_brain_status)
        app.router.add_get('/api/brain/models', self.handle_brain_models)
        app.router.add_post('/api/brain/query', self._auth_required(self.handle_brain_query))
        app.router.add_post('/api/brain/consensus', self.handle_brain_consensus)
        app.router.add_post('/api/brain/chain', self._auth_required(self.handle_brain_chain))
        app.router.add_post('/api/trust/sign', self._auth_required(self.handle_trust_sign))
        app.router.add_get('/api/trust/score/{key}', self.handle_trust_score)
        # WebSocket endpoint
        app.router.add_get('/ws', self.handle_websocket)
        return app

    def _auth_required(self, handler):
        """Decorator: require auth for a handler."""
        async def wrapper(request: web.Request):
            # Stealth mode check
            if self.stealth_mode and not self._stealth_check(request):
                return web.Response(status=404, text="Not found")
            auth_result = self._verify_auth(request)
            if auth_result is None:
                return web.Response(status=401, text="Unauthorized")
            request['auth'] = auth_result
            return await handler(request)
        return wrapper

    async def handle_dashboard(self, request: web.Request) -> web.Response:
        status = self.get_status()
        uptime = status['uptime']
        hours, remainder = divmod(int(uptime), 3600)
        mins, secs = divmod(remainder, 60)

        html = f"""<!DOCTYPE html>
<html><head><title>UnityBrain v{self.version}</title>
<style>
body {{ font-family: system-ui; background: #0a0a0a; color: #e0e0e0; margin: 2rem; }}
.card {{ background: #1a1a2e; border: 1px solid #333; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }}
.header {{ text-align: center; padding: 2rem; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
.stat {{ display: flex; justify-content: space-between; padding: 0.3rem 0; }}
.label {{ color: #888; }} .value {{ color: #4ecdc4; font-weight: bold; }}
.peer {{ padding: 0.5rem; border-left: 3px solid #4ecdc4; margin: 0.3rem 0; }}
.ok {{ color: #4ecdc4; }} .ko {{ color: #e74c3c; }}
h1 {{ color: #4ecdc4; }} h2 {{ color: #888; font-size: 0.9rem; text-transform: uppercase; }}
.stealth {{ background: #2d1b00; border-color: #e67e22; padding: 0.5rem; border-radius: 4px; color: #e67e22; margin: 1rem 0; }}
</style></head><body>
<div class="header">
<h1>🌐 UnityBrain v{self.version}</h1>
<div class="subtitle">Node: <strong>{self.node_name}</strong> | Uptime: {hours}h {mins}m {secs}s</div>
{'<div class="stealth">🔒 STEALTH MODE ACTIVE</div>' if self.stealth_mode else ''}
{'<div class="stealth" style="border-color:#4ecdc4;color:#4ecdc4;">📤 AI SHARING ENABLED</div>' if self.share_ai else ''}
</div>
<div class="grid">
<div class="card"><h2>Queries</h2>
<div class="stat"><span class="label">Total</span><span class="value">{status['queries']['total']}</span></div>
<div class="stat"><span class="label">Success</span><span class="value">{status['queries']['rate']}%</span></div>
<div class="stat"><span class="label">Memory</span><span class="value">{status['memory']['active_entries']} keys</span></div>
<div class="stat"><span class="label">Models</span><span class="value">{', '.join(self.local_models)}</span></div>
</div>
<div class="card"><h2>Network</h2>
<div class="stat"><span class="label">Peers</span><span class="value">{status['peers']['available']}/{status['peers']['total']}</span></div>
<div class="stat"><span class="label">WS Clients</span><span class="value">{status['ws_clients']}</span></div>
<div class="stat"><span class="label">Trust Links</span><span class="value">{status['web_of_trust']}</span></div>
<div class="stat"><span class="label">Identity</span><span class="value">{self.identity.fingerprint}</span></div>
</div>
</div>
<div class="card"><h2>Peers</h2>"""

        for p in self.peers:
            icon = "✅" if p.available else "❌"
            cb_state = p.circuit_breaker.state
            html += f"""<div class="peer">
<span class="{'ok' if p.available else 'ko'}">{icon} {p.name}</span>
{p.host}:{p.port} — {round(p.latency, 1)}ms — CB:{cb_state}
</div>"""

        if not self.peers:
            html += "<div>No peers connected</div>"

        html += "</div>"

        # Providers section
        html += '<div class="card"><h2>Providers</h2>'
        if self.providers:
            for name, provider in self.providers.items():
                status_icon = "\u2705" if provider.enabled else "\u274c"
                model_list = ', '.join(provider.models[:5])
                if len(provider.models) > 5:
                    model_list += f'... (+{len(provider.models) - 5} more)'
                extra = ""
                if isinstance(provider, OllamaProvider):
                    extra = f' @ {provider.host}:{provider.port}'
                elif isinstance(provider, (OpenAIProvider, OpenAICompatibleProvider, AnthropicProvider)):
                    extra = f' @ {provider.base_url}'
                html += f'<div class="peer">{status_icon} <strong>{name}</strong> ({provider.provider_type}){extra}<br/><span class="label">Models:</span> {model_list}</div>'
        else:
            html += '<div>No providers configured</div>'
        html += '</div>'

        html += """</body></html>"""
        return web.Response(text=html, content_type='text/html')

    async def handle_status(self, request: web.Request) -> web.Response:
        return web.json_response(self.get_status())

    async def handle_ping(self, request: web.Request) -> web.Response:
        return web.json_response({"pong": True, "node": self.node_name,
                                   "version": self.version, "time": time.time()})

    async def handle_query(self, request: web.Request) -> web.Response:
        data = await request.json()
        prompt = data.get("prompt", "")
        model = data.get("model")
        strategy = data.get("strategy", "auto")
        if not prompt:
            return web.json_response({"error": "prompt required"}, status=400)
        
        # Check if this is a peer request
        auth_info = request.get('auth', {})
        is_peer_request = auth_info.get('node', self.node_name) != self.node_name
        
        # If share_ai is False and this comes from a peer, reject
        if is_peer_request and not self.share_ai:
            return web.json_response({
                "error": "AI sharing disabled on this node",
                "share_ai": False
            }, status=403)
        
        result = await self.query(prompt, model, strategy)
        return web.json_response(result)

    async def handle_memory_set(self, request: web.Request) -> web.Response:
        data = await request.json()
        key = data.get("key", "")
        value = data.get("value")
        ttl = data.get("ttl")
        author = request.get('auth', {}).get('node', self.node_name)
        if not key:
            return web.json_response({"error": "key required"}, status=400)
        self.memory.set(key, value, ttl, author=author)
        # Gossip the update
        await self._gossip_broadcast({
            "type": "memory_update", "key": key,
            "entry": self.memory.store.get(key, {}),
            "source": self.node_name
        })
        return web.json_response({"status": "ok", "key": key})

    async def handle_memory_get(self, request: web.Request) -> web.Response:
        key = request.match_info['key']
        value = self.memory.get(key)
        if value is None:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response({"key": key, "value": value})

    async def handle_memory_sync_push(self, request: web.Request) -> web.Response:
        """Full memory sync push from another node."""
        data = await request.json()
        entries = data.get("entries", data.get("memory", {}))
        merged = self.memory.merge_from_sync(entries)
        self.log_event("sync", f"Merged {merged} entries via HTTP push")
        return web.json_response({"keys_merged": merged, "status": "ok"})

    async def handle_memory_push(self, request: web.Request) -> web.Response:
        """Push specific entries to this node (CRDT merge)."""
        data = await request.json()
        entries = data.get("entries", {})
        merged = self.memory.merge_from_sync(entries)
        return web.json_response({"keys_merged": merged, "status": "ok"})

    async def handle_memory_pull(self, request: web.Request) -> web.Response:
        """Pull entries newer than given vector clock (incremental sync)."""
        data = await request.json()
        since_vc = data.get("vector_clock", {})
        delta = self.memory.get_delta_since(since_vc)
        return web.json_response({"entries": delta, "vector_clock": self.memory.vector_clock.to_dict()})

    async def handle_peers(self, request: web.Request) -> web.Response:
        peer_list = [p.to_dict() for p in self.peers]
        return web.json_response(peer_list)

    async def handle_monitor(self, request: web.Request) -> web.Response:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        return web.json_response({
            "cpu": cpu, "mem_percent": mem.percent,
            "mem_total_gb": round(mem.total / (1024**3), 1),
            "peers": len(self.peers),
            "uptime": time.time() - self.start_time,
            "load_balancer": self.load_balancer.node_scores
        })

    async def handle_brain_status(self, request: web.Request) -> web.Response:
        if self.brain_llm:
            return web.json_response(self.brain_llm.status())
        return web.json_response({"error": "brain_llm not available"}, status=503)

    async def handle_brain_models(self, request: web.Request) -> web.Response:
        if self.brain_llm:
            return web.json_response(self.brain_llm.status().get("models", {}))
        return web.json_response({}, status=503)

    async def handle_brain_query(self, request: web.Request) -> web.Response:
        if not self.brain_llm:
            return web.json_response({"error": "brain_llm not available"}, status=503)
        data = await request.json()
        result = await self.brain_llm.query(
            data.get("prompt", ""), model=data.get("model"),
            strategy=data.get("strategy", "auto"))
        return web.json_response({
            "response": result.response, "model": result.model,
            "provider": result.provider, "latency_ms": result.latency_ms,
            "tokens_used": result.tokens_used, "confidence": result.confidence
        })

    async def handle_brain_consensus(self, request: web.Request) -> web.Response:
        data = await request.json()
        result = await self.ensemble.query_ensemble(
            self.session, self.peers, data.get("prompt", ""), data.get("model"))
        return web.json_response(result)

    async def handle_brain_chain(self, request: web.Request) -> web.Response:
        if not self.brain_llm:
            return web.json_response({"error": "brain_llm not available"}, status=503)
        data = await request.json()
        result = await self.brain_llm.query(
            data.get("prompt", ""), strategy="chain")
        return web.json_response({
            "response": result.response, "model": result.model,
            "provider": result.provider, "latency_ms": result.latency_ms
        })

    async def handle_trust_sign(self, request: web.Request) -> web.Response:
        """Sign (vouch for) another node's public key."""
        data = await request.json()
        target_key = data.get("public_key", "")
        if not target_key:
            return web.json_response({"error": "public_key required"}, status=400)
        self.web_of_trust.add_trust(self.identity.public_key_hex, target_key)
        # Gossip the trust edge
        await self._gossip_broadcast({
            "type": "trust_sign",
            "signer": self.identity.public_key_hex,
            "target": target_key,
            "source": self.node_name
        })
        score = self.web_of_trust.trust_score(target_key)
        return web.json_response({"status": "signed", "trust_score": score})

    async def handle_trust_score(self, request: web.Request) -> web.Response:
        key = request.match_info['key']
        score = self.web_of_trust.trust_score(key)
        return web.json_response({"public_key": key, "trust_score": score,
                                   "is_trusted": self.web_of_trust.is_trusted(key)})

    # ========================================================================
    # FEATURE 1: WEBSOCKET TEMPS RÉEL
    # ========================================================================

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=self.heartbeat_interval)
        await ws.prepare(request)

        client_id = str(uuid.uuid4())[:8]
        self.ws_clients[client_id] = ws
        self.log_event("ws", f"WS connected {client_id} from {request.remote} ({len(self.ws_clients)} total)")

        # Stealth mode: reject unknown nodes
        if self.stealth_mode and not self._stealth_check(request):
            await ws.send_json({'type': 'error', 'message': 'Node not recognized'})
            await ws.close()
            self.ws_clients.pop(client_id, None)
            return ws

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    msg_type = data.get('type', '')

                    # Auth via WS
                    if msg_type == 'auth':
                        authenticated = await self._ws_authenticate(data, ws, client_id)
                        if authenticated:
                            self.ws_authenticated.add(client_id)
                        continue

                    # All write operations require WS auth
                    if msg_type in ('memory_sync', 'memory_update', 'query',
                                    'trust_sign') and client_id not in self.ws_authenticated:
                        await ws.send_json({'type': 'error', 'message': 'Authentication required'})
                        continue

                    # Typed message handlers
                    if msg_type == 'ping':
                        await ws.send_json({'type': 'pong', 'node': self.node_name,
                                            'version': self.version, 'time': time.time()})
                    elif msg_type == 'query':
                        result = await self.query(data.get('prompt', ''), data.get('model'))
                        await ws.send_json({'type': 'query_result', **result})
                    elif msg_type == 'memory_sync':
                        entries = data.get('entries', {})
                        merged = self.memory.merge_from_sync(entries)
                        await ws.send_json({'type': 'sync_ack', 'keys_merged': merged})
                        self.log_event("ws_sync", f"Merged {merged} entries via WS")
                    elif msg_type == 'memory_update':
                        key = data.get('key', '')
                        entry = data.get('entry', {})
                        if key and entry:
                            merged = self.memory.merge_from_sync({key: entry})
                            # Gossip to other clients
                            await self._broadcast_ws({
                                'type': 'memory_update', 'key': key, 'entry': entry
                            }, exclude=client_id)
                    elif msg_type == 'memory_request':
                        vc = data.get('vector_clock', {})
                        if vc:
                            delta = self.memory.get_delta_since(vc)
                            await ws.send_json({'type': 'memory_delta', 'entries': delta})
                        else:
                            entries = self.memory.get_all_for_sync()
                            await ws.send_json({'type': 'memory_full', 'entries': entries})
                    elif msg_type == 'notification':
                        # Broadcast notification to all WS clients (with gossip propagation)
                        gossip_msg = {
                            'type': 'notification',
                            'message': data.get('message', ''),
                            'source': data.get('source', self.node_name),
                            'msg_id': data.get('msg_id', f"{self.node_name}:{uuid.uuid4().hex[:8]}"),
                            'timestamp': time.time()
                        }
                        await self._gossip_propagate(gossip_msg)
                    elif msg_type == 'peer_discovery':
                        # Node announces itself
                        peer_info = data.get('peer', {})
                        peer_key = data.get('public_key', '')
                        self.log_event("ws_discover", f"Peer {peer_info.get('name', '?')} via WS")
                        await ws.send_json({
                            'type': 'discover_ack',
                            'node': self.node_name,
                            'models': self.local_models,
                            'public_key': self.identity.public_key_hex,
                            'peers': [p.to_dict() for p in self.peers]
                        })
                    elif msg_type == 'status':
                        await ws.send_json({'type': 'status', **self.get_status()})

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WS error: {ws.exception()}')

        except (aiohttp.ServerDisconnectedError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            self.ws_clients.pop(client_id, None)
            self.ws_authenticated.discard(client_id)
            self.log_event("ws", f"WS disconnected {client_id} ({len(self.ws_clients)} total)")
        return ws

    async def _ws_authenticate(self, data: Dict, ws: web.WebSocketResponse,
                                client_id: str) -> bool:
        """Authenticate a WS client via Ed25519 challenge-response or shared secret."""
        # Ed25519 challenge-response
        if data.get('response') and data.get('from_key'):
            challenge = data.get('challenge', '')
            if self.identity.verify(challenge, data['response'], data['from_key']):
                await ws.send_json({'type': 'auth_ack', 'status': 'ok',
                                     'node': self.node_name,
                                     'public_key': self.identity.public_key_hex})
                return True

        # Shared secret HMAC
        hmac_sig = data.get('hmac', '')
        hmac_ts = data.get('ts', '')
        if hmac_sig and hmac_ts:
            import hmac as hmac_mod
            msg_str = f"/ws:{hmac_ts}"
            expected_sig = hmac_mod.new(
                self.p2p_secret.encode(), msg_str.encode(), hashlib.sha256).hexdigest()
            if hmac_mod.compare_digest(hmac_sig, expected_sig):
                await ws.send_json({'type': 'auth_ack', 'status': 'ok'})
                return True

        await ws.send_json({'type': 'auth_ack', 'status': 'failed'})
        return False

    async def _broadcast_ws(self, data: Dict, exclude: str = None):
        """Broadcast data to all authenticated WS clients except excluded one."""
        msg = json.dumps(data)
        dead = []
        for cid, client in list(self.ws_clients.items()):
            if cid == exclude:
                continue
            # Only broadcast to authenticated clients
            if cid not in self.ws_authenticated:
                continue
            if client.closed:
                dead.append(cid)
                continue
            try:
                await client.send_str(msg)
            except ConnectionResetError:
                dead.append(cid)
        for cid in dead:
            self.ws_clients.pop(cid, None)
            self.ws_authenticated.discard(cid)

    # ========================================================================
    # FEATURE 3: GOSSIP PROTOCOL
    # ========================================================================

    async def _gossip_broadcast(self, message: Dict):
        """Broadcast a message via gossip to all connected WS peers and known HTTP peers.
        Bug #1 fix: send correct payload based on message type."""
        msg_id = f"{self.node_name}:{uuid.uuid4().hex[:8]}"
        message["msg_id"] = msg_id
        message["source"] = self.node_name
        message["timestamp"] = time.time()

        self._gossip_seen.add(msg_id)

        # 1. Broadcast to connected WS clients
        await self._broadcast_ws(message)

        # 2. Push to known HTTP peers — build correct payload per message type
        if self.session:
            msg_type = message.get("type", "")
            if msg_type == "memory_update":
                # Bug #1: was sending message.get("entries", {}) which is empty;
                # a memory_update has "key" and "entry" (singular)
                key = message.get("key", "")
                entry = message.get("entry", {})
                payload = {"entries": {key: entry} if key else {}}
            elif msg_type == "trust_sign":
                payload = {"type": msg_type, "signer": message.get("signer", ""),
                           "target": message.get("target", "")}
            else:
                # Generic: send entries as-is
                payload = {"entries": message.get("entries", {})}

            for peer in self.peers:
                if peer.available and peer.circuit_breaker.can_execute():
                    try:
                        url = f'http://{peer.host}:{peer.port}/api/memory/push'
                        async with self.session.post(
                            url,
                            json=payload,
                            headers=self._auth_headers(),
                            timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                logger.debug(f"Gossip push to {peer.name}: OK")
                            else:
                                logger.debug(f"Gossip push to {peer.name}: {resp.status}")
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        logger.debug(f"Gossip push to {peer.name} failed: {e}")

    async def _gossip_propagate(self, message: Dict):
        """Propagate a gossip message (if not already seen)."""
        msg_id = message.get("msg_id", "")
        if not msg_id or msg_id in self._gossip_seen:
            return
        self._gossip_seen.add(msg_id)

        # Process locally based on type
        msg_type = message.get("type", "")
        if msg_type == "memory_update":
            key = message.get("key", "")
            entry = message.get("entry", {})
            if key and entry:
                self.memory.merge_from_sync({key: entry})
        elif msg_type == "trust_sign":
            signer = message.get("signer", "")
            target = message.get("target", "")
            if signer and target:
                self.web_of_trust.add_trust(signer, target)

        # Forward to other WS clients (with 1-hop limit to avoid storms)
        await self._broadcast_ws(message)

    # ========================================================================
    # BACKGROUND TASKS
    # ========================================================================

    async def sync_memory_to_peers(self):
        """Push local memory to all available peers (periodic HTTP sync)."""
        if not self.session:
            return
        memory_data = self.memory.get_all_for_sync()
        if not memory_data:
            return
        for peer in self.peers:
            if peer.available and peer.circuit_breaker.can_execute():
                try:
                    async with self.session.post(
                        f'http://{peer.host}:{peer.port}/api/memory/sync',
                        json={"entries": memory_data},
                        headers=self._auth_headers(),
                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            logger.debug(f"Synced {data.get('keys_merged', 0)} keys to {peer.name}")
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass

    async def auto_heal(self):
        """Check Ollama and restart if needed. Memory sync is now separate."""
        import subprocess
        heal_interval = self.config.get("auto_heal_interval", 120)
        while self.heartbeat_running:
            await asyncio.sleep(heal_interval)
            try:
                async with self.session.get(
                    f'http://{self.ollama_host}:{self.ollama_port}/api/tags',
                    timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        self.log_event("auto_heal", "Ollama down, restarting...", "warn")
                        proc = await asyncio.create_subprocess_exec(
                            'fuser', '-k', f'{self.ollama_port}/tcp',
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        await proc.communicate()
                        proc = await asyncio.create_subprocess_exec(
                            'systemctl', 'restart', 'ollama',
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        await proc.communicate()
                        self.log_event("auto_heal", "Ollama restart triggered")
            except (OSError, subprocess.SubprocessError):
                pass

    async def _memory_sync_loop(self):
        """Bug #3 fix: Memory sync decoupled from auto_heal. Runs every 30s."""
        sync_interval = self.config.get("memory_sync_interval", 30)
        while self.heartbeat_running:
            await asyncio.sleep(sync_interval)
            await self.sync_memory_to_peers()

    async def _ws_memory_sync_loop(self):
        """Periodic memory sync via WS (lightweight delta push)."""
        while self.heartbeat_running:
            await asyncio.sleep(60)
            if self.ws_clients and self.memory.store:
                memory_data = self.memory.get_all_for_sync()
                if memory_data:
                    await self._broadcast_ws({
                        'type': 'memory_sync',
                        'entries': memory_data,
                        'vector_clock': self.memory.vector_clock.to_dict()
                    })

    # ========================================================================
    # FEATURE: OUTGOING WS CONNECTIONS TO PEERS (Bug #2 fix)
    # ========================================================================

    async def _connect_to_peers_ws(self):
        """Periodically establish outgoing WS connections to known peers.
        This enables real-time bidirectional sync between nodes."""
        while self.heartbeat_running:
            await asyncio.sleep(10)  # Initial delay then try every 30s
            if not self.session:
                continue
            for peer in self.peers:
                if not peer.available:
                    continue
                ws_key = f"ws_out:{peer.host}:{peer.port}"
                if ws_key in self.ws_clients:
                    continue  # Already connected
                try:
                    await self._connect_peer_ws(peer, ws_key)
                except Exception as e:
                    logger.debug(f"WS connect to {peer.name} failed: {e}")
            # Wait 30s between reconnect cycles
            await asyncio.sleep(30)

    async def _connect_peer_ws(self, peer: 'Peer', ws_key: str):
        """Connect to a single peer via WebSocket with HMAC auth. Keeps connection alive with pings."""
        ws_url = f'ws://{peer.host}:{peer.port}/ws'
        try:
            async with self.session.ws_connect(
                    ws_url,
                    heartbeat=15,  # Send ping every 15s to keep alive
                    timeout=aiohttp.ClientTimeout(total=10)) as ws:
                # Authenticate with HMAC
                ts = str(int(time.time()))
                import hmac as hmac_mod
                sig = hmac_mod.new(
                    self.p2p_secret.encode(),
                    f'/ws:{ts}'.encode(),
                    hashlib.sha256).hexdigest()
                await ws.send_json({'type': 'auth', 'hmac': sig, 'ts': ts})
                # Wait for auth_ack, ignoring any pre-auth broadcast messages
                auth_ok = False
                for _ in range(10):
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=5)
                    if msg.get('type') == 'auth_ack':
                        auth_ok = msg.get('status') == 'ok'
                        break
                    # Ignore pre-auth broadcasts (memory_update, memory_sync, etc.)
                    logger.debug(f"WS pre-auth message from {peer.name}: {msg.get('type', '?')}")
                if not auth_ok:
                    logger.warning(f"WS auth to {peer.name} failed: no auth_ack received")
                    await ws.close()
                    return

                logger.info(f"WS connected to {peer.name} ({peer.host}:{peer.port})")
                self.ws_clients[ws_key] = ws
                self.ws_authenticated.add(ws_key)

                # Request memory delta from peer
                await ws.send_json({
                    'type': 'memory_request',
                    'vector_clock': self.memory.vector_clock.to_dict()
                })

                # Listen for messages from this peer (persistent connection)
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                        except json.JSONDecodeError:
                            continue
                        await self._handle_incoming_ws_message(data, ws_key)
                    elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                        break
                    # PONG messages are handled automatically by the heartbeat

                logger.info(f"WS disconnected from {peer.name}, will reconnect")

        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionRefusedError) as e:
            logger.debug(f"WS connection to {peer.name} failed: {e}")
        finally:
            self.ws_clients.pop(ws_key, None)
            self.ws_authenticated.discard(ws_key)

    async def _handle_incoming_ws_message(self, data: Dict, source_id: str):
        """Handle a message received from an outgoing WS connection to a peer."""
        msg_type = data.get('type', '')

        if msg_type == 'memory_delta':
            entries = data.get('entries', {})
            if entries:
                merged = self.memory.merge_from_sync(entries)
                if merged > 0:
                    self.log_event("ws_sync", f"Merged {merged} entries from WS peer")
        elif msg_type == 'memory_full':
            entries = data.get('entries', {})
            if entries:
                merged = self.memory.merge_from_sync(entries)
                if merged > 0:
                    self.log_event("ws_sync", f"Merged {merged} entries from WS full sync")
        elif msg_type == 'memory_update':
            key = data.get('key', '')
            entry = data.get('entry', {})
            if key and entry:
                self.memory.merge_from_sync({key: entry})
        elif msg_type == 'memory_sync':
            entries = data.get('entries', {})
            if entries:
                merged = self.memory.merge_from_sync(entries)
                if merged > 0:
                    self.log_event("ws_sync", f"Merged {merged} entries from WS sync")
        elif msg_type == 'pong':
            pass  # heartbeat response
        elif msg_type == 'auth_ack':
            pass  # already authenticated
        elif msg_type == 'status':
            logger.debug(f"WS status from peer: {data.get('node', '?')}")
        elif msg_type == 'discover_ack':
            peer_info = data.get('peers', [])
            logger.debug(f"WS discover_ack: {len(peer_info)} peers")
        else:
            logger.debug(f"WS unknown message type: {msg_type}")

    async def _discovery_loop(self):
        """Periodic peer re-discovery."""
        interval = self.config.get("discovery_interval", 300)
        while self.heartbeat_running:
            await asyncio.sleep(interval)
            new_peers = await self.discovery.discover_all()
            for peer_info in new_peers:
                existing = [p for p in self.peers
                            if p.host == peer_info['host'] and p.port == peer_info.get('port', 8081)]
                if not existing:
                    peer = Peer(
                        name=peer_info.get('name', 'unknown'),
                        host=peer_info['host'],
                        port=peer_info.get('port', 8081),
                        models=peer_info.get('models', []),
                        public_key_hex=peer_info.get('public_key', '')
                    )
                    await self.add_peer(peer)
                    self.log_event("discovery", f"Auto-discovered {peer.name}")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    import sys
    import signal

    node_name = sys.argv[1] if len(sys.argv) > 1 else "bug"
    script_dir = Path(__file__).parent.parent
    config_path = script_dir / "config" / f"{node_name}.json"
    config = load_config(str(config_path))
    if len(sys.argv) > 1:
        config["node_name"] = node_name

    brain = UnityBrain(config)
    await brain.initialize()

    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("🛑 UnityBrain shutting down...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    app = await brain.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, brain.host, brain.port, reuse_address=True, reuse_port=True)
    await site.start()
    logger.info(f"🌐 UnityBrain v{brain.version} on http://{brain.host}:{brain.port}")
    brain.log_event("server", f"Listening on {brain.host}:{brain.port}")

    if brain.stealth_mode:
        logger.info("🔒 Stealth mode ACTIVE — node is hidden from discovery")
    if brain.share_ai:
        logger.info("📤 AI sharing ENABLED — models available to the network")
    if not brain.share_ai:
        logger.info("🔇 AI sharing DISABLED — peers cannot use your models")
        logger.info("💡 Set share_ai: true to allow peers to use your CPU/RAM")

    tasks = [
        asyncio.create_task(brain.start_heartbeat()),
        asyncio.create_task(brain.auto_heal()),
        asyncio.create_task(brain._memory_sync_loop()),
    ]

    # P2P tasks
    tasks.extend([
        asyncio.create_task(brain._ws_memory_sync_loop()),
        asyncio.create_task(brain._connect_to_peers_ws()),
        asyncio.create_task(brain._discovery_loop()),
    ])

    await shutdown_event.wait()

    logger.info("Cleaning up...")
    brain.heartbeat_running = False
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    if brain.session:
        await brain.session.close()
    if brain.brain_llm:
        try:
            await brain.brain_llm.stop()
        except Exception:
            pass
    await runner.cleanup()
    logger.info("UnityBrain stopped.")


if __name__ == '__main__':
    import sys
    node = sys.argv[1] if len(sys.argv) > 1 else "bug"
    logger.info(f"Starting UnityBrain v4.1.0 as '{node}'")
    asyncio.run(main())