# Auto-imports for extracted module
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
import asyncio
import json
import os
import time


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
