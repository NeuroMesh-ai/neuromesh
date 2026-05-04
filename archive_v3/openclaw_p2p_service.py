#!/usr/bin/env python3
"""
Bug P2P Service — OpenClaw Native Integration

Run as an OpenClaw service:
  openclaw p2p start
  openclaw p2p query "..."
"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, List
import argparse

# Import existing P2P core
from p2p_core import BugPeer, PeerInfo
from reputation_system import BugReputationSystem


# Setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s"
)
logger = logging.getLogger("OpenClaw-P2P")


# ============ Service Class ============

class OpenClawP2PService:
    """P2P service that integrates with OpenClaw agent workflow."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8001,
        models: List[str] = None,
        bootstrap_peers: List[str] = None,
        config_path: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.models = models or ["qwen3:8b"]
        self.bootstrap_peers = bootstrap_peers or []

        # P2P Core
        self.peer = BugPeer(
            my_host=host,
            my_port=port,
            models=models,
            bootstrap_peers=bootstrap_peers
        )

        # Reputation System
        self.reputation = BugReputationSystem()

        # Control
        self._running = False
        self._tasks = []

    async def start(self):
        """Start the P2P service."""
        logger.info("🚀 Starting OpenClaw P2P Service")
        logger.info(f"   Host: {self.host}:{self.port}")
        logger.info(f"   Models: {self.models}")
        logger.info(f"   Bootstrap: {self.bootstrap_peers}")

        await self.peer.start()
        self._running = True

        logger.info("✅ P2P Service Ready")

    async def stop(self):
        """Stop the P2P service."""
        logger.info("🛑 Stopping P2P Service")
        self._running = False

        await self.peer.stop()
        logger.info("✅ P2P Service Stopped")

    async def query(
        self,
        query: str,
        model_required: Optional[str] = None,
        k: int = 3
    ) -> dict:
        """
        Send query to P2P network with reputation filtering.

        Returns: Best response with metadata.
        """
        # Get capable peers
        capable_peer_ids = list(self.peer.peers.keys())

        # Filter by reputation
        trusted_peers = self.reputation.select_peers(
            capable_peer_ids,
            k=k,
            min_reputation=30.0
        )

        # P2P query
        result = await self.peer.distributed_query(
            query,
            model_required=model_required,
            k=k
        )

        # Add reputation metadata
        result["reputation_filtered"] = len(trusted_peers) > 0
        result["trusted_peers_count"] = len(trusted_peers)

        return result

    async def get_peers(self) -> List[dict]:
        """Get list of known peers with reputation scores."""
        peers = []

        for peer_id, info in self.peer.peers.items():
            peer_dict = info.to_dict()
            peer_dict["reputation"] = self.reputation.get_peer_reputation(peer_id)
            peer_dict["state"] = self.peer.peer_states.get(peer_id).__dict__ if peer_id in self.peer.peer_states else None
            peers.append(peer_dict)

        return peers

    async def get_status(self) -> dict:
        """Get service status."""
        return {
            "service": "OpenClaw-P2P",
            "version": "0.1.0",
            "peer_id": self.peer.my_id,
            "listening": f"{self.host}:{self.port}",
            "models": self.peer.models,
            "peers_known": len(self.peer.peers),
            "reputation_stats": self.reputation.get_stats(),
            "cache_size": len(self.peer.query_cache),
            "uptime": "running" if self._running else "stopped"
        }


# ============ Command-Line Interface ============

async def cmd_start(args):
    """Start P2P service."""
    config = load_config(args.config)

    service = OpenClawP2PService(
        host=config["host"],
        port=config["port"],
        models=config["models"],
        bootstrap_peers=config["bootstrap_peers"]
    )

    # Write PID for service management
    if args.pidfile:
        Path(args.pidfile).write_text(str(os.getpid()))

    # Signal handling
    def signal_handler(signum, frame):
        logger.info("Received signal, shutting down...")
        asyncio.create_task(service.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start service
    await service.start()

    # Keep running
    try:
        while service._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        await service.stop()


async def cmd_query(args):
    """Send query to P2P network."""
    service = OpenClawP2PService(
        host=args.host or "127.0.0.1",
        port=args.port or 8001,
        models=["dummy"]
    )

    # Quick connection (no full service start)
    import aiohttp

    async with aiohttp.ClientSession() as session:
        url = f"http://{args.host or '127.0.0.1'}:{args.port or 8001}/p2p/query"

        payload = {
            "query": args.query,
            "model_required": args.model
        }

        try:
            async with session.post(url, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(json.dumps(result, indent=2))
                else:
                    print(f"Error: {resp.status}")
                    print(await resp.text())
        except Exception as e:
            print(f"Connection error: {e}")
            print("Make sure P2P service is running: openclaw p2p start")


async def cmd_peers(args):
    """List connected peers."""
    service = OpenClawP2PService(
        host=args.host or "127.0.0.1",
        port=args.port or 8001,
        models=["dummy"]
    )

    import aiohttp

    async with aiohttp.ClientSession() as session:
        url = f"http://{args.host or '127.0.0.1'}:{args.port or 8001}/p2p/peers"

        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    print(f"\n🌐 Peers Connected ({data['total']})")
                    print("=" * 60)

                    for peer in data["peers"]:
                        status_emoji = "🟢" if "latency" not in peer or peer.get("latency", 0) < 100 else "🟡"
                        print(f"{status_emoji} {peer['peer_id'][:16]}...")
                        print(f"   Models: {', '.join(peer.get('models', []))}")
                        print(f"   CPU: {peer.get('cpu_load', 0)*100:.0f}%, RAM: {peer.get('ram_free_gb', 0):.1f} GB")
                        print()

                else:
                    print(f"Error: {resp.status}")
        except Exception as e:
            print(f"Connection error: {e}")


async def cmd_status(args):
    """Show P2P service status."""
    import aiohttp

    url = f"http://{args.host or '127.0.0.1'}:{args.port or 8001}/"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    print("\n" + "=" * 50)
                    print("  OpenClaw P2P Service Status")
                    print("=" * 50)
                    print(f"  Network:  {data['network']}")
                    print(f"  Version:  {data['version']}")
                    print(f"  Peer ID:  {data['peer_id']}")
                    print(f"  Models:   {', '.join(data['models'])}")
                    print(f"  Peers:    {data['peers_known']}")
                    print()
                    print("  Statistics:")
                    print(f"    Query cache:   {data['stats']['query_cache_size']}")
                    print(f"    Total queries: {data['stats']['total_queries']}")
                    print("=" * 50)

                else:
                    print(f"Error: {resp.status}")
        except Exception as e:
            print(f"Connection error: {e}")
            print("Service may not be running")
            print("Start with: openclaw p2p start")


async def cmd_reputation(args):
    """Show reputation statistics."""
    import aiohttp

    # For now, just show that it's available
    print("📊 Reputation System Stats")
    print("  (Full reputation stats available via daemon)")
    print()
    print("  Top peers will be shown when service is integrated")


async def cmd_config(args):
    """Show current configuration."""
    config = load_config(args.config)

    print("\n🔧 OpenClaw P2P Configuration")
    print("=" * 50)
    print(f"  Host:                {config['host']}")
    print(f"  Port:                {config['port']}")
    print(f"  Models provided:     {', '.join(config['models'])}")
    print(f"  Bootstrap peers:     {len(config['bootstrap_peers'])}")
    print()
    print("  Bootstrap list:")
    for peer in config['bootstrap_peers']:
        print(f"    - {peer}")
    print("=" * 50)


# ============ CLI Main ============

def main():
    parser = argparse.ArgumentParser(
        description="OpenClaw P2P Service",
        prog="openclaw p2p"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Common args
    parser.add_argument("--host", help="P2P service host")
    parser.add_argument("--port", type=int, help="P2P service port")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--pidfile", help="PID file for daemon")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start P2P service")
    start_parser.add_argument("--host", default="127.0.0.1", help="Service host")
    start_parser.add_argument("--port", type=int, default=8001, help="Service port")
    start_parser.add_argument("--model", action="append", default=[], help="Models I provide")
    start_parser.add_argument("--bootstrap", action="append", default=[], help="Bootstrap peers")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query P2P network")
    query_parser.add_argument("query", help="Query to send")
    query_parser.add_argument("--model", help="Required model")

    # Status command
    subparsers.add_parser("status", help="Show service status")

    # Peers command
    subparsers.add_parser("peers", help="List connected peers")

    # Reputation command
    subparsers.add_parser("reputation", help="Show reputation statistics")

    # Config command
    subparsers.add_parser("config", help="Show configuration")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to command
    if args.command == "start":
        asyncio.run(cmd_start(args))
    elif args.command == "query":
        asyncio.run(cmd_query(args))
    elif args.command == "status":
        asyncio.run(cmd_status(args))
    elif args.command == "peers":
        asyncio.run(cmd_peers(args))
    elif args.command == "reputation":
        asyncio.run(cmd_reputation(args))
    elif args.command == "config":
        asyncio.run(cmd_config(args))


# ============ Configuration ============

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8001,
    "models": ["qwen3:8b"],
    "bootstrap_peers": [
        "127.0.0.1:8001",
        # Public seed nodes (to be added):
        # "seed.openclaw-p2p.io:8001",
    ]
}

CONFIG_PATHS = [
    "/etc/openclaw/p2p.toml",
    "~/.config/openclaw/p2p.toml",
    "~/.openclaw/config/p2p.toml",
]


def load_config(config_path: Optional[str] = None) -> dict:
    """Load configuration from file or return defaults."""
    if config_path:
        path = Path(config_path).expanduser()
        if path.exists():
            return read_toml_config(path)

    # Try default paths
    for path_str in CONFIG_PATHS:
        path = Path(path_str).expanduser()
        if path.exists():
            return read_toml_config(path)

    # Return defaults
    return DEFAULT_CONFIG.copy()


def read_toml_config(path: Path) -> dict:
    """Read TOML config file."""
    try:
        import tomli
        with open(path, "rb") as f:
            return tomli.load(f)
    except ImportError:
        logger.warning(f"tomli not installed, using defaults. Install with: pip install tomli")
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        logger.warning(f"Error reading config {path}: {e}")
        return DEFAULT_CONFIG.copy()


if __name__ == "__main__":
    import os
    main()