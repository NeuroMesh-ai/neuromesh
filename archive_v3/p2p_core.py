#!/usr/bin/env python3
"""
Bug P2P Core — Fully decentralized peer management.

No orchestrator. Every node is equal.
"""

import asyncio
import json
import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import socket
import logging

# Crypto
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519

# Network
import aiohttp
from aiohttp import web

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BugP2P")


# ============ Data Structures ============

@dataclass
class PeerInfo:
    peer_id: str
    host: str
    port: int
    models: List[str]
    cpu_load: float
    ram_free_gb: float
    last_seen: str
    reputation: int = 100

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class PeerState:
    peer_info: PeerInfo
    pending_queries: int
    total_queries: int
    avg_latency_ms: float


# ============ P2P Peer ============

class BugPeer:
    """A fully decentralized P2P peer."""

    def __init__(
        self,
        my_host: str = "127.0.0.1",
        my_port: int = 8001,
        models: List[str] = None,
        bootstrap_peers: List[str] = None
    ):
        self.my_host = my_host
        self.my_port = my_port
        self.models = models or ["micro-llm"]  # Models this node runs

        # Crypto key
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        self.my_id = self._peer_id_from_pubkey()

        # Peer management
        self.peers: Dict[str, PeerInfo] = {}  # peer_id → PeerInfo
        self.peer_states: Dict[str, PeerState] = {}

        # Bootstrap nodes (fixed list)
        self.bootstrap_peers = bootstrap_peers or [
            "127.0.0.1:8001",  # Self (for testing)
            # Add remote seeds here:
            # "seed1.bug-p2p.io:8001",
            # "seed2.bug-p2p.io:8001",
        ]

        # Gossip
        self._gossip_interval = 30  # seconds
        self._gossip_neighbors = 3  # Send to k=3 random peers

        # Cache
        self.query_cache: Dict[str, Tuple[str, float]] = {}  # query_hash → (response, timestamp)
        self._cache_ttl = 3600  # 1 hour

        # HTTP Server
        self._app = web.Application()
        self._app.add_routes([
            web.get('/', self.handle_root),
            web.post('/p2p/query', self.handle_p2p_query),
            web.post('/p2p/response', self.handle_p2p_response),
            web.post('/p2p/gossip', self.handle_gossip),
            web.get('/p2p/peers', self.handle_peers_list),
        ])

        # Background tasks
        self._tasks = []

    @property
    def my_address(self) -> str:
        return f"{self.my_host}:{self.my_port}"

    def _peer_id_from_pubkey(self) -> str:
        """Generate peer ID from public key."""
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return hashlib.sha256(pub_bytes).hexdigest()[:16]

    def sign_message(self, message: dict) -> dict:
        """Sign a message with private key."""
        message_data = json.dumps(message, sort_keys=True).encode()
        signature = self._private_key.sign(message_data)

        return {
            "payload": message,
            "signature": signature.hex(),
            "signer": self.my_id
        }

    def verify_message(self, signed_msg: dict) -> Optional[dict]:
        """Verify a signed message."""
        try:
            # Get signer's peer info
            signer_id = signed_msg.get("signer")
            if signer_id == self.my_id:
                peer_key = self._public_key
            elif signer_id in self.peers:
                # For now, assume we have pubkey (in full impl, exchange keys)
                logger.warning(f"Signature verification not fully implemented for peer {signer_id}")
                return signed_msg["payload"]
            else:
                logger.warning(f"Unknown signer: {signer_id}")
                return None

            message_data = json.dumps(signed_msg["payload"], sort_keys=True).encode()
            signature = bytes.fromhex(signed_msg["signature"])

            peer_key.verify(signature, message_data)
            return signed_msg["payload"]

        except Exception as e:
            logger.warning(f"Signature verification failed: {e}")
            return None

    # ============ Discovery ============

    async def discover_peers(self):
        """Discover peers via bootstrap."""
        logger.info("🔍 Starting peer discovery...")

        # Try bootstrap peers
        for peer_addr in self.bootstrap_peers:
            if peer_addr == self.my_address:
                continue

            try:
                host, port = peer_addr.split(":")
                await self._connect_to_peer(host, int(port))
            except Exception as e:
                logger.debug(f"Could not connect to {peer_addr}: {e}")

        logger.info(f"🌐 Discovered {len(self.peers)} peers")

    async def _connect_to_peer(self, host: str, port: int):
        """Connect to a peer and exchange info."""
        url = f"http://{host}:{port}/p2p/gossip"

        # Send our info
        my_info = PeerInfo(
            peer_id=self.my_id,
            host=self.my_host,
            port=self.my_port,
            models=self.models,
            cpu_load=0.0,  # Will be updated by gossip
            ram_free_gb=0.0,
            last_seen=datetime.now().isoformat()
        )

        signed_msg = self.sign_message(my_info.to_dict())

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=signed_msg, timeout=5) as resp:
                if resp.status == 200:
                    # Verify response
                    data = await resp.json()
                    if isinstance(data, dict) and "payload" in data:
                        payload = data["payload"]
                        if payload:
                            self._add_or_update_peer(PeerInfo.from_dict(payload))

    def _add_or_update_peer(self, peer_info: PeerInfo):
        """Add or update a peer in our registry."""
        self.peers[peer_info.peer_id] = peer_info

        if peer_info.peer_id not in self.peer_states:
            self.peer_states[peer_info.peer_id] = PeerState(
                peer_info=peer_info,
                pending_queries=0,
                total_queries=0,
                avg_latency_ms=0.0
            )

        logger.debug(f"✅ Updated peer: {peer_info.peer_id} ({peer_info.models})")

    # ============ Gossip Protocol ============

    async def gossip_loop(self):
        """Periodically gossip with random neighbors."""
        while True:
            await asyncio.sleep(self._gossip_interval)

            if not self.peers:
                continue

            # Select random neighbors
            neighbors = random.sample(
                list(self.peers.keys()),
                min(self._gossip_neighbors, len(self.peers))
            )

            for peer_id in neighbors:
                await self._gossip_to_peer(peer_id)

    async def _gossip_to_peer(self, peer_id: str):
        """Send gossip to a specific peer."""
        peer = self.peers.get(peer_id)
        if not peer:
            return

        # Prepare state
        state = {
            "peer_id": self.my_id,
            "models": self.models,
            "cpu_load": self._get_cpu_load(),
            "ram_free_gb": self._get_ram_free(),
            "known_peers": list(self.peers.keys())[:10]  # Share some peers
        }

        signed_msg = self.sign_message(state)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{peer.host}:{peer.port}/p2p/gossip",
                    json=signed_msg,
                    timeout=3
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict) and "payload" in data:
                            payload = data["payload"]
                            if payload:
                                peer_info = PeerInfo.from_dict(payload)
                                self._add_or_update_peer(peer_info)

                            # Learn about new peers
                            if "known_peers" in data["payload"]:
                                for new_peer_id in data["payload"]["known_peers"]:
                                    # In full impl, would fetch peer details
                                    pass

        except Exception as e:
            logger.debug(f"Gossip to {peer_id} failed: {e}")

    async def handle_gossip(self, request):
        """Handle incoming gossip."""
        signed_msg = await request.json()

        # Verify message
        payload = self.verify_message(signed_msg)
        if not payload:
            return web.Response(status=403, text="Invalid signature")

        # Update peer info
        peer_info = PeerInfo(
            peer_id=payload["peer_id"],
            host=request.remote or "unknown",
            port=0,  # Not included in gossip
            models=payload["models"],
            cpu_load=payload["cpu_load"],
            ram_free_gb=payload["ram_free_gb"],
            last_seen=datetime.now().isoformat()
        )

        self._add_or_update_peer(peer_info)

        # Respond with our state
        my_state = {
            "peer_id": self.my_id,
            "models": self.models,
            "cpu_load": self._get_cpu_load(),
            "ram_free_gb": self._get_ram_free(),
            "known_peers": list(self.peers.keys())
        }

        return web.json_response(self.sign_message(my_state))

    # ============ Distributed Query ============

    async def distributed_query(
        self,
        query: str,
        model_required: Optional[str] = None,
        k: int = 3
    ) -> dict:
        """
        Send query to k best peers in the P2P network.

        Returns: Best response from peers.
        """
        logger.info(f"🔍 Query: {query[:50]}...")

        # Check cache first
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        if query_hash in self.query_cache:
            resp, cached_at = self.query_cache[query_hash]
            if datetime.now().timestamp() - cached_at < self._cache_ttl:
                logger.info("✅ Cache hit")
                return {
                    "response": resp,
                    "source": "cache",
                    "peer_id": "local",
                    "latency_ms": 0
                }

        # Select best peers
        capable_peers = self._select_peers_for_model(model_required, k)

        # Fallback to local if no peers available
        if not capable_peers:
            logger.warning("⚠️  No remote peers available, using local")
            # Would call local model here
            return {
                "response": "Local model response (not implemented in this demo)",
                "source": "local",
                "peer_id": self.my_id,
                "latency_ms": 0
            }

        # Query in parallel
        start_time = datetime.now()
        responses = await self._query_peers_parallel(capable_peers, query)
        total_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Select best response
        best = self._select_best_response(responses) if responses else None

        if best:
            # Cache it
            self.query_cache[query_hash] = (best["response"], datetime.now().timestamp())

            return {
                **best,
                "total_latency_ms": total_ms,
                "responses_count": len(responses)
            }

        # Fallback
        return {
            "response": "No valid responses from peers",
            "source": "none",
            "peer_id": "none",
            "latency_ms": total_ms
        }

    def _select_peers_for_model(self, model: Optional[str], k: int) -> List[str]:
        """Select best k peers that have the required model."""
        candidates = []

        for peer_id, state in self.peer_states.items():
            peer = self.peers.get(peer_id)
            if not peer:
                continue

            # Filter by model if specified
            if model and model not in peer.models:
                continue

            # Score by: latency + load
            score = (state.avg_latency_ms * 0.6) + (peer.cpu_load * 100 * 0.4)

            candidates.append((peer_id, score))

        # Sort by score (lower is better)
        candidates.sort(key=lambda x: x[1])

        return [c[0] for c in candidates[:k]]

    async def _query_peers_parallel(self, peer_ids: List[str], query: str) -> List[dict]:
        """Query multiple peers in parallel."""
        tasks = [
            self._send_query_to_peer(peer_id, query)
            for peer_id in peer_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = []
        for peer_id, result in zip(peer_ids, results):
            if isinstance(result, dict):
                result["peer_id"] = peer_id
                responses.append(result)
            else:
                logger.debug(f"Query to {peer_id} failed: {result}")

        return responses

    async def _send_query_to_peer(self, peer_id: str, query: str) -> Optional[dict]:
        """Send query to a specific peer."""
        peer = self.peers.get(peer_id)
        if not peer:
            return None

        payload = {
            "query": query,
            "timestamp": datetime.now().isoformat()
        }

        signed_msg = self.sign_message(payload)

        try:
            start = datetime.now()
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{peer.host}:{peer.port}/p2p/query",
                    json=signed_msg,
                    timeout=30
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latency = (datetime.now() - start).total_seconds() * 1000

                        # Update peer state
                        if peer_id in self.peer_states:
                            state = self.peer_states[peer_id]
                            state.total_queries += 1
                            # Exponential moving average for latency
                            state.avg_latency_ms = (
                                state.avg_latency_ms * 0.7 + latency * 0.3
                            )

                        if isinstance(data, dict) and "payload" in data:
                            result = data["payload"]
                            return result

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Query to {peer_id} failed: {e}")

        return None

    def _select_best_response(self, responses: List[dict]) -> Optional[dict]:
        """Select the best response from multiple peers."""
        if not responses:
            return None

        # Simple heuristic: prefer shorter, faster responses
        scored = [
            (
                r,
                len(r.get("response", "")) * 0.5 + r.get("latency_ms", 1000) * 0.5
            )
            for r in responses
        ]

        scored.sort(key=lambda x: x[1])

        return scored[0][0]

    # ============ HTTP Handlers ============

    async def handle_root(self, request):
        """Root endpoint."""
        return web.json_response({
            "network": "Bug P2P",
            "version": "0.1.0",
            "peer_id": self.my_id,
            "models": self.models,
            "peers_known": len(self.peers),
            "stats": {
                "query_cache_size": len(self.query_cache),
                "total_queries": sum(s.total_queries for s in self.peer_states.values())
            }
        })

    async def handle_p2p_query(self, request):
        """Handle incoming query from another peer."""
        signed_msg = await request.json()

        payload = self.verify_message(signed_msg)
        if not payload:
            return web.Response(status=403, text="Invalid signature")

        query = payload["query"]
        timestamp = payload["timestamp"]

        # In full impl, would call local model here
        # For now, simple response
        response_text = f"[{self.my_id}] Local model response to: {query[:30]}..."

        result = {
            "peer_id": self.my_id,
            "response": response_text,
            "latency_ms": 10,
            "model": self.models[0] if self.models else "unknown"
        }

        return web.json_response(self.sign_message(result))

    async def handle_p2p_response(self, request):
        """Handle response back from a peer."""
        signed_msg = await request.json()

        # In full impl, would match with pending query
        # For now, just acknowledge
        return web.Response(text="OK")

    async def handle_peers_list(self, request):
        """Return list of known peers."""
        return web.json_response({
            "peers": [p.to_dict() for p in self.peers.values()],
            "total": len(self.peers)
        })

    # ============ System Info ============

    def _get_cpu_load(self) -> float:
        """Get current CPU load (mock for now)."""
        # In real impl, use psutil
        return 0.3

    def _get_ram_free(self) -> float:
        """Get free RAM in GB (mock for now)."""
        # In real impl, use psutil
        return 8.0

    # ============ Lifecycle ============

    async def start(self):
        """Start the P2P peer."""
        logger.info(f"🚀 Starting Bug P2P Peer: {self.my_id}")
        logger.info(f"   Address: {self.my_address}")
        logger.info(f"   Models: {self.models}")

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self.discover_peers()),
            asyncio.create_task(self.gossip_loop())
        ]

        # Start HTTP server
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, self.my_host, self.my_port)
        await site.start()

        logger.info(f"✅ P2P server listening on {self.my_address}")

    async def stop(self):
        """Stop the P2P peer."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("🛑 P2P peer stopped")


# ============ CLI ============

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bug P2P Peer")
    parser.add_argument("--host", default="127.0.0.1", help="My host")
    parser.add_argument("--port", type=int, default=8001, help="My port")
    parser.add_argument("--model", action="append", default=[], help="Models I provide")
    parser.add_argument("--bootstrap", action="append", default=[], help="Bootstrap peers")
    parser.add_argument("--query", help="Send a query to the P2P network")
    args = parser.parse_args()

    peer = BugPeer(
        my_host=args.host,
        my_port=args.port,
        models=args.model or ["qwen3:8b"],
        bootstrap_peers=args.bootstrap
    )

    await peer.start()

    if args.query:
        result = await peer.distributed_query(args.query)
        print("\n🔍 Query Result:")
        print(json.dumps(result, indent=2))

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        await peer.stop()


if __name__ == "__main__":
    asyncio.run(main())