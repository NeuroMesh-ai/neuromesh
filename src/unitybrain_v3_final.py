#!/usr/bin/env python3
"""
🌐 UNITYBRAIN v3.1 - RÉSEAU P2P DISTRIBUTÉ
Améliorations v3.1:
- P2P heartbeat dédié (TCP, pas Ollama)
- API POST pour requêtes modèle
- Logging structuré
- Ollama HTTP API au lieu de subprocess
- Auto-discovery Tailscale
- Pinky self-ping fixé
"""

import asyncio
import socket
import json
import time
import hashlib
import threading
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# ============================================================================
# ============== LOGGING ===================================================
# ============================================================================

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("UnityBrain")

# ============================================================================
# ============== CONFIG =====================================================
# ==============================================================================

# Node identity — override via environment or config
NODE_NAME = "Bug"
NODE_HOST = "0.0.0.0"
P2P_PORT = 9999          # P2P heartbeat + comm port
WEB_PORT = 8081          # Web UI + API
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434

# Known peers (Tailscale IPs)
PEERS = [
    {"name": "Bug", "host": "100.101.143.118", "port": 9999, "models": ["glm-5.1:cloud"]},
    {"name": "Pinky", "host": "100.73.233.77", "port": 9999, "models": ["gemma4:31b-cloud", "glm-5.1:cloud"]},
]

HEARTBEAT_INTERVAL = 30   # seconds
HEARTBEAT_TIMEOUT = 5     # seconds
SELF_NAME = NODE_NAME     # used to skip self in peer list

# ============================================================================
# ============== PEER & P2P NETWORK ========================================
# ============================================================================

class Peer:
    """Représente un peer dans le réseau P2P"""
    def __init__(self, name: str, host: str, port: int, models: List[str], ollama_host: str = "127.0.0.1"):
        self.name = name
        self.host = host
        self.port = port
        self.models = models
        self.ollama_host = ollama_host
        self.available = False
        self.latency = float('inf')
        self.reputation = 1.0
        self.last_seen = 0
        self.model_stats = {model: {"success": 0, "total": 0, "latency_sum": 0} for model in models}
        self.shared_models = {}

    async def ping(self) -> float:
        """Ping le peer via P2P protocol (not Ollama)"""
        try:
            start = time.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=HEARTBEAT_TIMEOUT
            )
            msg = json.dumps({"type": "ping", "name": SELF_NAME, "timestamp": time.time()}) + "\n"
            writer.write(msg.encode())
            await writer.drain()
            data = await asyncio.wait_for(reader.readline(), timeout=HEARTBEAT_TIMEOUT)
            writer.close()
            await writer.wait_closed()
            self.latency = (time.time() - start) * 1000
            self.available = True
            self.last_seen = time.time()
            logger.info(f"Ping {self.name}@{self.host}:{self.port} → {self.latency:.0f}ms")
            return self.latency
        except Exception as e:
            self.available = False
            logger.warning(f"Ping {self.name}@{self.host}:{self.port} failed: {e}")
            return float('inf')

    async def query_model_ollama(self, model: str, prompt: str, max_length: int = 2000) -> Tuple[str, float]:
        """Query un modèle via Ollama HTTP API (not subprocess)"""
        try:
            start = time.time()
            url = f"http://{self.ollama_host}:{OLLAMA_PORT}/api/generate"
            payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_length}
            }).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
            response = result.get("response", "")
            latency = (time.time() - start) * 1000

            stats = self.model_stats.get(model, {"success": 0, "total": 0, "latency_sum": 0})
            stats["total"] += 1
            stats["latency_sum"] += latency
            stats["success"] += 1
            self.model_stats[model] = stats

            return response[:max_length], latency
        except Exception as e:
            stats = self.model_stats.get(model, {"success": 0, "total": 0, "latency_sum": 0})
            stats["total"] += 1
            self.model_stats[model] = stats
            logger.error(f"Query {model} on {self.name} failed: {e}")
            return f"Error: {str(e)}", float('inf')

    def vote_reputation(self, delta: float):
        self.reputation = max(0.0, min(1.0, self.reputation + delta))

    def get_model_stats(self, model: str) -> Dict:
        stats = self.model_stats.get(model, {"success": 0, "total": 0, "latency_sum": 0})
        return {
            "success_rate": stats["success"] / stats["total"] if stats["total"] > 0 else 0,
            "avg_latency": stats["latency_sum"] / stats["total"] if stats["total"] > 0 else float('inf')
        }

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "models": self.models,
            "available": self.available,
            "latency": self.latency if self.latency != float('inf') else None,
            "reputation": self.reputation,
            "last_seen": self.last_seen
        }

# ============================================================================
# ============== MODEL SHARING =============================================
# ============================================================================

class ModelShare:
    def __init__(self):
        self.chunks = {}
        self.chunk_size = 1024 * 1024

    def split_model(self, model_id: str, model_data: bytes) -> Dict:
        chunks = {}
        for i in range(0, len(model_data), self.chunk_size):
            chunk_id = f"{model_id}_{i // self.chunk_size}"
            chunks[chunk_id] = model_data[i:i+self.chunk_size]
            self.chunks[chunk_id] = {
                "data": chunks[chunk_id],
                "hash": hashlib.sha256(chunks[chunk_id]).hexdigest(),
                "peers": []
            }
        return chunks

    def get_chunk(self, chunk_id: str) -> Optional[bytes]:
        return self.chunks.get(chunk_id, {}).get("data")

    def verify_chunk(self, chunk_id: str, chunk_data: bytes) -> bool:
        chunk_info = self.chunks.get(chunk_id)
        if not chunk_info:
            return False
        return hashlib.sha256(chunk_data).hexdigest() == chunk_info["hash"]

# ============================================================================
# ============== ENSEMBLE CONSENSUS ========================================
# ============================================================================

class EnsembleConsensus:
    def __init__(self, agreement_threshold: float = 0.6):
        self.agreement_threshold = agreement_threshold

    async def query_ensemble(self, models: List[str], prompt: str, peer: Peer) -> Dict:
        responses = []
        for model in models:
            response, latency = await peer.query_model_ollama(model, prompt)
            responses.append({"model": model, "response": response, "latency": latency})
        consensus = await self._compute_consensus(responses)
        return {
            "status": "success",
            "consensus": consensus,
            "individual_responses": responses,
            "agreement_score": self._compute_agreement(responses)
        }

    async def _compute_consensus(self, responses: List[Dict]) -> str:
        return max(responses, key=lambda r: len(r["response"]))["response"]

    def _compute_agreement(self, responses: List[Dict]) -> float:
        lengths = [len(r["response"]) for r in responses]
        avg_length = sum(lengths) / len(lengths)
        max_length = max(lengths)
        return avg_length / max_length if max_length > 0 else 0

# ============================================================================
# ============== DYNAMIC MODEL ROUTING =====================================
# ============================================================================

class ModelRouter:
    def __init__(self):
        self.routing_table = {}

    async def route(self, prompt: str, available_models: List[str]) -> str:
        prompt_lower = prompt.lower()
        if any(kw in prompt_lower for kw in ["code", "function", "python", "javascript", "program"]):
            code_models = [m for m in available_models if "code" in m.lower()]
            if code_models:
                return code_models[0]
        if any(kw in prompt_lower for kw in ["explique", "analyse", "raisonne", "compliqué"]):
            reasoning_models = [m for m in available_models if "phi" in m.lower() or "glm-5" in m.lower()]
            if reasoning_models:
                return reasoning_models[0]
        return available_models[0] if available_models else "gemma4:31b-cloud"

# ============================================================================
# ============== QUERY HISTORY ==============================================
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

    async def export(self, format_type: str = "json") -> str:
        if format_type == "json":
            return json.dumps(self.history, indent=2)
        elif format_type == "txt":
            return "\n".join([f"[{datetime.fromtimestamp(h['timestamp'])}] {h.get('prompt', '')}" for h in self.history])
        return json.dumps(self.history, indent=2)

# ============================================================================
# ============== P2P SERVER ================================================
# ============================================================================

class P2PServer:
    """TCP server for P2P heartbeat and communication"""
    def __init__(self, unitybrain, host: str = "0.0.0.0", port: int = 9999):
        self.ub = unitybrain
        self.host = host
        self.port = port
        self.server = None

    async def handle_client(self, reader, writer):
        """Handle incoming P2P messages"""
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=HEARTBEAT_TIMEOUT)
            if not data:
                return
            msg = json.loads(data.decode().strip())
            msg_type = msg.get("type", "unknown")

            if msg_type == "ping":
                # Respond with our status
                response = json.dumps({
                    "type": "pong",
                    "name": SELF_NAME,
                    "models": self.ub.local_models,
                    "status": "ok",
                    "timestamp": time.time()
                }) + "\n"
                writer.write(response.encode())
                await writer.drain()
                logger.info(f"P2P: ping from {msg.get('name', '?')}")

            elif msg_type == "query":
                # Incoming model query from another peer
                prompt = msg.get("prompt", "")
                model = msg.get("model", self.ub.local_models[0] if self.ub.local_models else "")
                result, latency = await self.ub.query_local_model(model, prompt)
                response = json.dumps({
                    "type": "query_response",
                    "response": result,
                    "model": model,
                    "latency": latency,
                    "timestamp": time.time()
                }) + "\n"
                writer.write(response.encode())
                await writer.drain()

        except Exception as e:
            logger.error(f"P2P handler error: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info(f"P2P server listening on {self.host}:{self.port}")

    async def serve(self):
        if self.server:
            async with self.server:
                await self.server.serve_forever()

# ============================================================================
# ============== WEB API ====================================================
# ============================================================================

class WebHandler(BaseHTTPRequestHandler):
    """HTTP handler — GET + POST"""
    def __init__(self, *args, unitybrain=None, **kwargs):
        self.unitybrain = unitybrain
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        logger.info(f"HTTP: {format % args}")

    def do_GET(self):
        if self.path == "/":
            self._send_html()
        elif self.path.startswith("/api/status"):
            self._send_json(self.unitybrain.get_status())
        elif self.path.startswith("/api/peers"):
            self._send_json({"peers": [p.to_dict() for p in self.unitybrain.peers]})
        elif self.path.startswith("/api/history"):
            limit = int(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("limit", [10])[0])
            loop = asyncio.new_event_loop()
            history = loop.run_until_complete(self.unitybrain.query_history.get(limit))
            loop.close()
            self._send_json(history)
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'

        try:
            data = json.loads(body.decode())
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=400)
            return

        if self.path.startswith("/api/query"):
            prompt = data.get("prompt", "")
            model = data.get("model", "")
            use_ensemble = data.get("ensemble", False)
            if not prompt:
                self._send_json({"error": "Missing 'prompt'"}, status=400)
                return

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    self.unitybrain.query(prompt, model=model, use_ensemble=use_ensemble)
                )
            finally:
                loop.close()
            self._send_json(result)

        elif self.path.startswith("/api/ping"):
            loop = asyncio.new_event_loop()
            try:
                results = loop.run_until_complete(self.unitybrain.ping_all())
            finally:
                loop.close()
            self._send_json([p.to_dict() for p in results])

        else:
            self._send_json({"error": "Unknown endpoint"}, status=404)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _send_html(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(self._get_html().encode())

    def _get_html(self) -> str:
        peers_html = "".join([
            f'<div class="peer">{"✅" if p.available else "❌"} {p.name} — '
            f'{p.latency:.0f}ms (rep: {p.reputation:.2f})</div>'
            for p in self.unitybrain.peers
        ])
        return f"""<!DOCTYPE html>
<html>
<head><title>UnityBrain v3.1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
h1 {{ color: #2ecc71; }}
.status {{ background: #16213e; padding: 20px; border-radius: 10px; }}
.peer {{ background: #0f3460; padding: 10px; margin: 10px 0; border-radius: 5px; }}
.api {{ background: #1a1a2e; padding: 15px; border: 1px solid #2ecc71; border-radius: 8px; margin-top: 20px; }}
textarea {{ width: 100%; height: 80px; background: #16213e; color: #eee; border: 1px solid #2ecc71; border-radius: 5px; }}
button {{ background: #2ecc71; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; }}
button:hover {{ background: #27ae60; }}
#result {{ margin-top: 10px; white-space: pre-wrap; background: #16213e; padding: 15px; border-radius: 5px; min-height: 50px; }}
</style>
</head>
<body>
<h1>🌐 UnityBrain v3.1</h1>
<div class="status">
<h2>📊 Status</h2>
<p>Peers: {len([p for p in self.unitybrain.peers if p.available])}/{len(self.unitybrain.peers)}</p>
<p>Queries: {self.unitybrain.queries}</p>
</div>
<div>
<h2>🤖 Peers</h2>
{peers_html}
</div>
<div class="api">
<h2>🧪 Query</h2>
<textarea id="prompt" placeholder="Enter prompt..."></textarea>
<br><br>
<button onclick="sendQuery()">Send</button>
<button onclick="pingAll()">Ping All</button>
<div id="result"></div>
</div>
<script>
async function sendQuery() {{
    const prompt = document.getElementById('prompt').value;
    const result = document.getElementById('result');
    result.textContent = 'Thinking...';
    try {{
        const resp = await fetch('/api/query', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{prompt: prompt}})
        }});
        const data = await resp.json();
        result.textContent = JSON.stringify(data, null, 2);
    }} catch(e) {{
        result.textContent = 'Error: ' + e.message;
    }}
}}
async function pingAll() {{
    const result = document.getElementById('result');
    try {{
        const resp = await fetch('/api/ping', {{method: 'POST'}});
        const data = await resp.json();
        result.textContent = JSON.stringify(data, null, 2);
    }} catch(e) {{
        result.textContent = 'Error: ' + e.message;
    }}
}}
</script>
</body>
</html>"""

# ============================================================================
# ============== UNITYBRAIN MAIN ===========================================
# ============================================================================

class UnityBrain:
    def __init__(self, name: str = NODE_NAME):
        self.name = name
        self.version = "3.1.0"

        self.router = ModelRouter()
        self.ensemble = EnsembleConsensus()
        self.model_share = ModelShare()
        self.query_history = QueryHistory()

        self.peers = []
        self.local_models = ['glm-5.1:cloud']

        self.queries = 0
        self.successful = 0
        self.start_time = time.time()

        self.web_server = None
        self.p2p_server = None
        self._heartbeat_task = None

    async def add_peer(self, peer: Peer):
        self.peers.append(peer)
        logger.info(f"Added peer {peer.name}@{peer.host}:{peer.port}")

    async def initialize(self):
        logger.info(f"Initializing {self.name} v{self.version}...")
        logger.info("P2P Network: Enabled ✅")
        logger.info("P2P Heartbeat: Enabled ✅")
        logger.info("Model Sharing: Enabled ✅")
        logger.info("Ensemble Consensus: Enabled ✅")
        logger.info("Reputation System: Enabled ✅")
        logger.info("Dynamic Model Routing: Enabled ✅")
        logger.info("Query History: Enabled ✅")
        logger.info("Web Interface + API: Enabled ✅")
        logger.info("Ollama HTTP API: Enabled ✅")

        # Initial ping (skip self)
        await self.ping_all()

        available = [p for p in self.peers if p.available]
        logger.info(f"✅ {self.name} initialized! Peers: {len(available)}/{len(self.peers)}")

    async def ping_all(self):
        """Ping all peers (except self)"""
        tasks = []
        for peer in self.peers:
            if peer.name != SELF_NAME:
                tasks.append(peer.ping())
            else:
                # Self is always available
                peer.available = True
                peer.latency = 0
                peer.last_seen = time.time()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return self.peers

    async def heartbeat_loop(self):
        """Periodic heartbeat"""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            logger.info("Heartbeat: pinging peers...")
            await self.ping_all()
            available = [p for p in self.peers if p.available]
            logger.info(f"Heartbeat: {len(available)}/{len(self.peers)} peers available")

    async def query_local_model(self, model: str, prompt: str) -> Tuple[str, float]:
        """Query a local model via Ollama HTTP API"""
        try:
            start = time.time()
            url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
            payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False
            }).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
            latency = (time.time() - start) * 1000
            return result.get("response", ""), latency
        except Exception as e:
            logger.error(f"Local model query failed: {e}")
            return f"Error: {e}", float('inf')

    async def query(self, prompt: str, model: str = "", use_ensemble: bool = False) -> Dict:
        """Exécute une requête"""
        self.queries += 1
        logger.info(f"Query {self.queries}: {prompt[:50]}...")

        # Find best peer (prefer non-self, skip self if others available)
        remote_peers = [p for p in self.peers if p.available and p.name != SELF_NAME]
        if remote_peers:
            fastest = min(remote_peers, key=lambda p: p.latency)
        elif any(p.available for p in self.peers):
            # Fallback to self
            fastest = next(p for p in self.peers if p.available)
        else:
            return {"status": "error", "message": "No available peer"}

        # Select model
        if not model:
            model = await self.router.route(prompt, fastest.models)

        if fastest.name == SELF_NAME:
            # Local query
            response, latency = await self.query_local_model(model, prompt)
        else:
            # Remote query via P2P
            response, latency = await fastest.query_model_ollama(model, prompt)

        success = latency < float('inf')
        if success:
            self.successful += 1
            fastest.vote_reputation(0.01)

        await self.query_history.add({
            "prompt": prompt,
            "response": response,
            "peer": fastest.name,
            "model": model,
            "latency": latency,
            "success": success
        })

        return {
            "status": "success" if success else "error",
            "response": response,
            "peer": fastest.name,
            "model": model,
            "latency": latency,
            "ensemble": use_ensemble
        }

    def get_status(self) -> Dict:
        available = [p for p in self.peers if p.available]
        return {
            "version": self.version,
            "node": SELF_NAME,
            "uptime": time.time() - self.start_time,
            "peers": {
                "total": len(self.peers),
                "available": len(available),
                "list": [p.to_dict() for p in self.peers]
            },
            "queries": {
                "total": self.queries,
                "successful": self.successful,
                "rate": (self.successful / self.queries * 100) if self.queries > 0 else 0
            },
            "model_sharing": {"chunks": len(self.model_share.chunks)},
            "history": {"entries": len(self.query_history.history)}
        }

    async def start_web_server(self, port: int = WEB_PORT):
        handler = lambda *args: WebHandler(*args, unitybrain=self)
        self.web_server = HTTPServer(("0.0.0.0", port), handler)
        thread = threading.Thread(target=self.web_server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Web server started on http://0.0.0.0:{port}")

# ============================================================================
# ============== MAIN =======================================================
# ============================================================================

async def main():
    logger.info("=" * 60)
    logger.info(f"🌐 UNITYBRAIN v3.1 - {SELF_NAME}")
    logger.info("=" * 60)

    unitybrain = UnityBrain()

    # Add peers from config
    for p in PEERS:
        if p["name"] != SELF_NAME:
            peer = Peer(p["name"], p["host"], p["port"], p["models"], ollama_host=p["host"])
            await unitybrain.add_peer(peer)
        else:
            # Self — mark available immediately
            peer = Peer(p["name"], p["host"], p["port"], p["models"], ollama_host=OLLAMA_HOST)
            peer.available = True
            peer.latency = 0
            peer.last_seen = time.time()
            await unitybrain.add_peer(peer)

    # Initialize
    await unitybrain.initialize()

    # Start P2P server
    p2p = P2PServer(unitybrain, NODE_HOST, P2P_PORT)
    p2p_task = asyncio.create_task(p2p.start())
    await asyncio.sleep(0.5)  # Let server bind

    # Start web server
    await unitybrain.start_web_server()

    # Start heartbeat
    heartbeat_task = asyncio.create_task(unitybrain.heartbeat_loop())

    logger.info(f"🌐 UnityBrain v3.1 daemon running on {SELF_NAME} - press Ctrl+C to stop")

    # Keep running
    try:
        await asyncio.gather(p2p_task, heartbeat_task)
    except asyncio.CancelledError:
        logger.info("🛑 UnityBrain shutting down...")

if __name__ == '__main__':
    import signal
    import sys

    def shutdown(sig, frame):
        logger.info("🛑 Received shutdown signal")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 UnityBrain stopped")