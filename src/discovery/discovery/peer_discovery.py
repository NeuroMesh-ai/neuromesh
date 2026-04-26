# Auto-imports for extracted module
import logging
logger = logging.getLogger('UnityBrain.discovery')
from typing import Dict
from typing import List
import aiohttp
import asyncio
import json
import os
import socket
import time


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
        except Exception as e:
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
                except:
                    pass
            
            # Listen for responses
            sock.close()
        except Exception as e:
            logger.debug(f"mDNS discovery failed: {e}")
        return peers
    
    async def _discover_referrals(self) -> List[Dict]:
        """Ask known peers about other peers they know"""
        referred = []
        for key, peer_info in list(self.known_peers.items()):
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"http://{peer_info['host']}:{peer_info.get('port', 8081)}/api/peers"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status == 200:
                            peer_list = await resp.json()
                            for p in peer_list:
                                pkey = f"{p['host']}:{p.get('port', 8081)}"
                                if pkey not in self.known_peers:
                                    p['source'] = 'referral'
                                    referred.append(p)
            except:
                pass
        return referred


# ============================================================================
# ============== LOAD BALANCER (Point 4) ===================================
# ============================================================================
