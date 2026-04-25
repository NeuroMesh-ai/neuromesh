#!/usr/bin/env python3
"""
🌐 UNITYBRAIN v3.1 - RÉSEAU P2P DISTRIBUTÉ
Fixed version: P2P protocol, Ollama HTTP API, Heartbeat, POST endpoints

Changes from v3.0:
- P2P server using aiohttp (replaces broken TCP ping)
- Ollama HTTP API (replaces subprocess)
- Heartbeat between nodes
- POST /api/query endpoint
- Auto-discovery via Tailscale
- Failover on peer failure
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
import threading
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import deque

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger('UnityBrain')

# Shared secret for P2P authentication
P2P_SECRET = os.environ.get('UNITYBRAIN_SECRET', 'bug-pinky-2026-unity')

# ============================================================================
# ============== PEER & P2P NETWORK ========================================
# ============================================================================

class Peer:
    """Représente un peer dans le réseau P2P"""
    def __init__(self, name: str, host: str, port: int, models: List[str], 
                 ollama_host: str = "127.0.0.1", ollama_port: int = 11434):
        self.name = name
        self.host = host
        self.port = port  # UnityBrain P2P port
        self.models = models
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.available = False
        self.latency = float('inf')
        self.reputation = 1.0
        self.last_seen = 0
        self.model_stats = {model: {"success": 0, "total": 0, "latency_sum": 0} for model in models}

    async def ping(self, session: aiohttp.ClientSession) -> float:
        """Ping le peer via HTTP API (fix #1)"""
        try:
            start = time.time()
            url = f"http://{self.host}:{self.port}/api/ping"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.latency = round((time.time() - start) * 1000, 2)
                    self.available = True
                    self.last_seen = time.time()
                    # Update peer's models from response
                    if 'models' in data:
                        for m in data['models']:
                            if m not in self.model_stats:
                                self.model_stats[m] = {"success": 0, "total": 0, "latency_sum": 0}
                                self.models.append(m)
                    return self.latency
            self.available = False
            return float('inf')
        except Exception as e:
            self.available = False
            logger.debug(f"Ping {self.name} failed: {e}")
            return float('inf')

    async def query_model(self, session: aiohttp.ClientSession, model: str, 
                          prompt: str, max_length: int = 2000) -> Tuple[str, float]:
        """Query un modèle via Ollama HTTP API (fix #3)"""
        try:
            start = time.time()
            url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_length}
            }
            async with session.post(url, json=payload, 
                                     timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get('response', '')[:max_length]
                    latency = round((time.time() - start) * 1000, 2)
                    
                    stats = self.model_stats.get(model, {"success": 0, "total": 0, "latency_sum": 0})
                    stats["total"] += 1
                    stats["success"] += 1
                    stats["latency_sum"] += latency
                    self.model_stats[model] = stats
                    
                    return response, latency
                else:
                    error = await resp.text()
                    logger.error(f"Ollama error from {self.name}: {resp.status} {error[:100]}")
                    latency = round((time.time() - start) * 1000, 2)
                    stats = self.model_stats.get(model, {"success": 0, "total": 0, "latency_sum": 0})
                    stats["total"] += 1
                    self.model_stats[model] = stats
                    return f"Error: {resp.status}", latency
        except Exception as e:
            logger.error(f"Query {model}@{self.name} failed: {e}")
            stats = self.model_stats.get(model, {"success": 0, "total": 0, "latency_sum": 0})
            stats["total"] += 1
            self.model_stats[model] = stats
            return f"Error: {str(e)}", float('inf')

    async def query_via_peer(self, session: aiohttp.ClientSession, model: str, 
                              prompt: str, max_length: int = 2000) -> Tuple[str, float]:
        """Query via the peer's UnityBrain API (remote Ollama)"""
        try:
            start = time.time()
            url = f"http://{self.host}:{self.port}/api/query"
            payload = {"prompt": prompt, "model": model}
            async with session.post(url, json=payload,
                                     timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get('response', '')[:max_length]
                    latency = round((time.time() - start) * 1000, 2)
                    return response, latency
            return "Error: peer query failed", float('inf')
        except Exception as e:
            return f"Error: {str(e)}", float('inf')

    def vote_reputation(self, delta: float):
        self.reputation = max(0.0, min(1.0, self.reputation + delta))

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "models": self.models,
            "available": self.available,
            "latency": self.latency,
            "reputation": self.reputation,
            "last_seen": self.last_seen
        }


# ============================================================================
# ============== MODEL ROUTING ============================================
# ============================================================================

class ModelRouter:
    """Routeur dynamique de modèles"""
    async def route(self, prompt: str, available_models: List[str]) -> str:
        prompt_lower = prompt.lower()
        if any(kw in prompt_lower for kw in ["code", "function", "python", "javascript"]):
            code_models = [m for m in available_models if "code" in m.lower()]
            if code_models:
                return code_models[0]
        if any(kw in prompt_lower for kw in ["explique", "analyse", "raisonne"]):
            reasoning = [m for m in available_models if "glm" in m.lower()]
            if reasoning:
                return reasoning[0]
        return available_models[0] if available_models else "glm-5.1:cloud"


# ============================================================================
# ============== ENSEMBLE CONSENSUS =======================================
# ============================================================================

class EnsembleConsensus:
    def __init__(self, agreement_threshold: float = 0.6):
        self.agreement_threshold = agreement_threshold

    async def query_ensemble(self, session: aiohttp.ClientSession, 
                              models: List[str], prompt: str, peer: Peer) -> Dict:
        responses = []
        for model in models:
            response, latency = await peer.query_model(session, model, prompt)
            responses.append({"model": model, "response": response, "latency": latency})
        
        consensus = max(responses, key=lambda r: len(r["response"]))["response"]
        agreement = sum(len(r["response"]) for r in responses) / (len(responses) * max(len(r["response"]) for r in responses)) if responses else 0
        
        return {"consensus": consensus, "individual_responses": responses, "agreement_score": agreement}


# ============================================================================
# ============== QUERY HISTORY ============================================
# ============================================================================

class QueryHistory:
    def __init__(self, max_entries: int = 1000):
        self.history = []
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
    """Mémoire distribuée P2P avec cache LRU"""
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.store = {}
        self.max_size = max_size
        self.default_ttl = default_ttl

    def set(self, key: str, value: Any, ttl: int = None):
        if len(self.store) >= self.max_size:
            # LRU eviction
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


# ============================================================================
# ============== UNITYBRAIN MAIN ==========================================
# ============================================================================

class UnityBrain:
    """UnityBrain v3.1 - P2P Distribué avec vrai protocole"""

    def __init__(self, name: str = "UnityBrain", node_name: str = "unknown",
                 host: str = "0.0.0.0", port: int = 8080,
                 ollama_host: str = "127.0.0.1", ollama_port: int = 11434,
                 models: List[str] = None):
        self.name = name
        self.node_name = node_name
        self.version = "3.1.0"
        self.host = host
        self.port = port
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.local_models = models or ["glm-5.1:cloud"]

        # Composants
        self.router = ModelRouter()
        self.ensemble = EnsembleConsensus()
        self.history = QueryHistory()
        self.memory = DistributedMemory()

        # Peers
        self.peers: List[Peer] = []

        # Stats
        self.queries = 0
        self.successful = 0
        self.start_time = time.time()

        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None

        # Heartbeat
        self.heartbeat_interval = 30  # seconds
        self.heartbeat_running = False

    async def add_peer(self, peer: Peer):
        self.peers.append(peer)

    async def initialize(self):
        """Initialise UnityBrain"""
        logger.info(f"Initializing {self.name} v{self.version}...")

        # Create HTTP session
        self.session = aiohttp.ClientSession()

        # Check peers
        await self.check_peers()

        available = [p for p in self.peers if p.available]
        logger.info(f"{self.name} initialized! Peers: {len(available)}/{len(self.peers)}")

    async def check_peers(self):
        """Ping all peers"""
        if not self.session:
            return
        for peer in self.peers:
            await peer.ping(self.session)

    async def start_heartbeat(self):
        """Background heartbeat (fix #6)"""
        self.heartbeat_running = True
        while self.heartbeat_running:
            await asyncio.sleep(self.heartbeat_interval)
            await self.check_peers()
            available = [p for p in self.peers if p.available]
            if available:
                logger.info(f"Heartbeat: {len(available)}/{len(self.peers)} peers alive")

    async def query(self, prompt: str, model: str = None, 
                     use_ensemble: bool = False) -> Dict:
        """Exécute une requête avec failover (fix #9)"""
        self.queries += 1
        logger.info(f"Query {self.queries}: {prompt[:50]}...")

        # Try local first
        selected_model = model or await self.router.route(prompt, self.local_models)
        response, latency = await self._query_local(selected_model, prompt)

        if latency == float('inf'):
            # Local failed, try peers (failover)
            logger.info(f"Local query failed, trying peers...")
            available = [p for p in self.peers if p.available]
            if available:
                # Sort by latency
                available.sort(key=lambda p: p.latency)
                for peer in available:
                    response, latency = await peer.query_via_peer(
                        self.session, selected_model, prompt)
                    if latency < float('inf'):
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
            "local_models": self.local_models
        }

    # ========================================================================
    # ============== HTTP API (aiohttp - fix #2 & #4) ========================
    # ========================================================================

    def _verify_auth(self, request: web.Request) -> bool:
        """Verify P2P authentication (HMAC-based)"""
        auth = request.headers.get('X-UnityBrain-Auth', '')
        timestamp = request.headers.get('X-UnityBrain-TS', '')
        if not auth or not timestamp:
            # Allow unauthenticated for GET endpoints (status, ping)
            return request.method == 'GET'
        # Verify timestamp freshness (±5 min)
        try:
            ts = float(timestamp)
            if abs(time.time() - ts) > 300:
                return False
        except:
            return False
        # Verify HMAC
        path = str(request.url)
        msg = f"{path}:{timestamp}"
        expected = hmac.new(P2P_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(auth, expected)

    def _auth_headers(self, path: str) -> Dict[str, str]:
        """Generate auth headers for outgoing P2P requests"""
        ts = str(time.time())
        msg = f"{path}:{ts}"
        sig = hmac.new(P2P_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return {
            'X-UnityBrain-Auth': sig,
            'X-UnityBrain-TS': ts,
            'X-UnityBrain-Version': self.version
        }

    async def create_app(self) -> web.Application:
        """Create aiohttp web application with P2P endpoints"""
        app = web.Application()
        app.middlewares.append(self.auth_middleware)
        app.add_routes([
            web.get('/', self.handle_index),
            web.get('/api/status', self.handle_status),
            web.get('/api/ping', self.handle_ping),
            web.post('/api/query', self.handle_query),
            web.post('/api/memory', self.handle_memory_set),
            web.get('/api/memory/{key}', self.handle_memory_get),
            web.get('/api/peers', self.handle_peers),
            web.get('/api/monitor', self.handle_monitor),     # Monitoring
            web.post('/api/sync', self.handle_sync),         # Memory sync
            web.get('/ws', self.handle_websocket),            # WebSocket
        ])
        return app

    @web.middleware
    async def auth_middleware(self, request, handler):
        """Middleware: require auth for POST endpoints"""
        if request.method == 'POST' and not self._verify_auth(request):
            return web.json_response({'error': 'unauthorized'}, status=401)
        return await handler(request)

    async def handle_index(self, request: web.Request) -> web.Response:
        status = self.get_status()
        html = f"""<!DOCTYPE html>
<html><head><title>UnityBrain v{self.version}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
h1 {{ color: #2ecc71; }} .status {{ background: #16213e; padding: 20px; border-radius: 10px; margin: 10px 0; }}
.peer {{ background: #0f3460; padding: 10px; margin: 5px 0; border-radius: 5px; }}
.ok {{ color: #2ecc71; }} .ko {{ color: #e74c3c; }}
</style></head><body>
<h1>🌐 UnityBrain v{self.version}</h1>
<div class="status">
<h2>📊 Node: {self.node_name}</h2>
<p>Uptime: {status['uptime']}s | Queries: {status['queries']['total']} ({status['queries']['rate']}% success)</p>
<p>Local models: {', '.join(self.local_models)}</p>
</div>
<div class="status">
<h2>🤖 Peers ({status['peers']['available']}/{status['peers']['total']})</h2>
{''.join(f'<div class="peer"><span class="{"ok" if p["available"] else "ko"}">{"✅" if p["available"] else "❌"}</span> {p["name"]}: {p["latency"]:.0f}ms (rep: {p["reputation"]:.2f})</div>' for p in status['peers']['list'])}
</div>
</body></html>"""
        return web.Response(text=html, content_type='text/html')

    async def handle_status(self, request: web.Request) -> web.Response:
        return web.json_response(self.get_status())

    async def handle_ping(self, request: web.Request) -> web.Response:
        """P2P ping endpoint - returns node info (fix #1)"""
        return web.json_response({
            "node": self.node_name,
            "version": self.version,
            "models": self.local_models,
            "uptime": round(time.time() - self.start_time, 1),
            "timestamp": time.time()
        })

    async def handle_query(self, request: web.Request) -> web.Response:
        """POST /api/query - execute a query (fix #4)"""
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
        """POST /api/memory - store in distributed memory"""
        try:
            data = await request.json()
            key = data.get('key', '')
            value = data.get('value')
            ttl = data.get('ttl', 3600)
            self.memory.set(key, value, ttl)
            return web.json_response({"status": "ok", "key": key})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_memory_get(self, request: web.Request) -> web.Response:
        """GET /api/memory/{key} - retrieve from distributed memory"""
        key = request.match_info['key']
        value = self.memory.get(key)
        return web.json_response({"key": key, "value": value})

    async def handle_peers(self, request: web.Request) -> web.Response:
        """GET /api/peers - list all known peers"""
        return web.json_response([p.to_dict() for p in self.peers])

    async def handle_monitor(self, request: web.Request) -> web.Response:
        """GET /api/monitor - system monitoring"""
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()
            return web.json_response({
                'node': self.node_name,
                'cpu_percent': cpu,
                'memory': {'total_gb': round(mem.total/1e9, 1), 'used_gb': round(mem.used/1e9, 1), 'percent': mem.percent},
                'disk': {'total_gb': round(disk.total/1e9, 1), 'used_gb': round(disk.used/1e9, 1), 'percent': disk.percent},
                'network': {'bytes_sent': net.bytes_sent, 'bytes_recv': net.bytes_recv},
                'uptime': round(time.time() - self.start_time, 1),
                'processes': len(psutil.pids())
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def handle_sync(self, request: web.Request) -> web.Response:
        """POST /api/sync - sync distributed memory from peer"""
        try:
            data = await request.json()
            keys_synced = 0
            for key, entry in data.get('memory', {}).items():
                if entry.get('expires', 0) > time.time():
                    self.memory.set(key, entry['value'], entry.get('expires', 0) - time.time())
                    keys_synced += 1
            return web.json_response({'status': 'ok', 'keys_synced': keys_synced})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket for real-time P2P communication"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        logger.info(f'WebSocket connection from {request.remote}')
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get('type') == 'ping':
                        await ws.send_json({'type': 'pong', 'node': self.node_name, 'timestamp': time.time()})
                    elif data.get('type') == 'query':
                        result = await self.query(data.get('prompt', ''), model=data.get('model'))
                        await ws.send_json({'type': 'query_result', **result})
                    elif data.get('type') == 'memory_sync':
                        for key, value in data.get('entries', {}).items():
                            self.memory.set(key, value)
                        await ws.send_json({'type': 'sync_ack', 'keys': len(data.get('entries', {}))})
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WS error: {ws.exception()}')
        except Exception as e:
            logger.error(f'WebSocket error: {e}')
        finally:
            logger.info(f'WebSocket closed from {request.remote}')
        return ws

    async def sync_memory_to_peers(self):
        """Push local memory to all available peers"""
        if not self.session:
            return
        memory_data = {}
        for key, entry in self.memory.store.items():
            if entry['expires'] > time.time():
                memory_data[key] = {'value': entry['value'], 'expires': entry['expires']}
        
        if not memory_data:
            return
            
        for peer in self.peers:
            if peer.available:
                try:
                    url = f'http://{peer.host}:{peer.port}/api/sync'
                    headers = self._auth_headers(url)
                    async with self.session.post(url, json={'memory': memory_data}, headers=headers,
                                                  timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            logger.debug(f'Synced {data.get("keys_synced", 0)} keys to {peer.name}')
                except Exception as e:
                    logger.debug(f'Sync to {peer.name} failed: {e}')

    async def auto_heal(self):
        """Auto-healing: check critical services and restart if needed"""
        while self.heartbeat_running:
            await asyncio.sleep(120)  # Check every 2 min
            try:
                # Check Ollama
                async with self.session.get(f'http://{self.ollama_host}:{self.ollama_port}/api/tags',
                                             timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        logger.warning('Ollama seems down, attempting restart...')
                        proc = await asyncio.create_subprocess_exec(
                            'fuser', '-k', f'{self.ollama_port}/tcp',
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        await proc.communicate()
                        proc = await asyncio.create_subprocess_exec(
                            'systemctl', 'restart', 'ollama',
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        await proc.communicate()
                        logger.info('Ollama restart triggered')
            except:
                logger.warning('Ollama health check failed')
            
            # Sync memory to peers
            await self.sync_memory_to_peers()

    async def run_server(self):
        """Start aiohttp server"""
        app = await self.create_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"UnityBrain P2P server on http://{self.host}:{self.port}")
        
        # Start heartbeat in background
        asyncio.create_task(self.start_heartbeat())
        
        # Start auto-heal
        asyncio.create_task(self.auto_heal())
        
        # Keep running
        while True:
            await asyncio.sleep(3600)


# ============================================================================
# ============== TAILSCALE DISCOVERY (fix #5) ==============================
# ============================================================================

async def discover_tailscale_peers() -> List[Dict]:
    """Discover other UnityBrain nodes via Tailscale"""
    peers = []
    try:
        # Get Tailscale status
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
# ============== MAIN ========================================================
# ============================================================================

async def main():
    """Main entry point"""
    import sys
    
    # Config from environment or defaults
    node_name = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    
    # Node-specific config
    configs = {
        "bug": {
            "port": 8080,
            "ollama_host": "127.0.0.1",
            "models": ["glm-5.1:cloud"],
            "peers": [
                ("Pinky", "100.73.233.77", 8081, ["gemma4:31b-cloud", "glm-5.1:cloud"])
            ]
        },
        "pinky": {
            "port": 8081,
            "ollama_host": "127.0.0.1",
            "models": ["gemma4:31b-cloud", "glm-5.1:cloud"],
            "peers": [
                ("Bug", "100.101.143.118", 8080, ["glm-5.1:cloud"])
            ]
        }
    }
    
    config = configs.get(node_name, configs["bug"])
    
    # Create UnityBrain
    brain = UnityBrain(
        name=f"UnityBrain-{node_name}",
        node_name=node_name,
        port=config["port"],
        ollama_host=config["ollama_host"],
        models=config["models"]
    )
    
    # Add peers
    for peer_name, host, port, models in config["peers"]:
        peer = Peer(peer_name, host, port, models, ollama_host=host)
        await brain.add_peer(peer)
    
    # Initialize
    await brain.initialize()
    
    # Try Tailscale auto-discovery
    ts_peers = await discover_tailscale_peers()
    if ts_peers:
        logger.info(f"Tailscale peers found: {[p['name'] for p in ts_peers]}")
    
    # Run server (blocks forever)
    await brain.run_server()


if __name__ == '__main__':
    import signal
    import sys
    
    def shutdown(sig, frame):
        logger.info("UnityBrain shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    node = "bug"  # default
    if len(sys.argv) > 1:
        node = sys.argv[1]
    
    logger.info(f"Starting UnityBrain v3.1 as '{node}'")
    asyncio.run(main())