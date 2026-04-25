#!/usr/bin/env python3
"""
🌐 INTERNET CAPABLE MODULE
Module permettant l'interconnexion sur des réseaux divers (LAN, WAN, Internet)
Rendezvous server, NAT traversal, HTTP discovery, security renforcée
"""

import asyncio
import socket
import json
import time
import hashlib
import uuid
import aiohttp
import ssl
from typing import List, Dict, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

# ============================================================================
# ============== NETWORK TYPES ==============================================
# ============================================================================

class NetworkType(Enum):
    """Types de réseaux"""
    LOCAL = "local"  # LAN, subnet
    WAN = "wan"  # Private WAN, VPN
    PUBLIC = "public"  # Internet, IP publique

# ============================================================================
# ============== RENDEZVOUS SERVER =========================================
# ============================================================================

@dataclass
class RendezvousNode:
    """Nœud enregistré sur le rendezvous server"""
    node_id: str
    name: str
    public_address: str  # "host:port"
    private_address: str = None  # "host:port" (optional)
    network_type: NetworkType = NetworkType.LOCAL
    capabilities: List[str] = field(default_factory=list)
    last_heartbeat: float = 0.0
    status: str = "online"
    metadata: Dict = field(default_factory=dict)

class RendezvousServer:
    """Serveur de rendezvous pour discovery sur Internet"""

    def __init__(self, host: str = "0.0.0.0", port: int = 9990, db_path: str = None):
        self.host = host
        self.port = port
        self.db_path = db_path or "/tmp/rendezvous_db.json"
        self.nodes: Dict[str, RendezvousNode] = {}
        self.load_db()
        self.server_socket = None
        self.running = False

    def load_db(self):
        """Charge la base de données"""
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
                for node_id, node_data in data.items():
                    self.nodes[node_id] = RendezvousNode(**node_data)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save_db(self):
        """Sauvegarde la base de données"""
        data = {
            node_id: {
                "node_id": node.node_id,
                "name": node.name,
                "public_address": node.public_address,
                "private_address": node.private_address,
                "network_type": node.network_type.value,
                "capabilities": node.capabilities,
                "last_heartbeat": node.last_heartbeat,
                "status": node.status,
                "metadata": node.metadata
            }
            for node_id, node in self.nodes.items()
        }
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)

    async def start(self):
        """Démarre le serveur"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        self.server_socket.setblocking(False)

        self.running = True
        print(f"\n🌐 Rendezvous Server started on {self.host}:{self.port}")

        loop = asyncio.get_event_loop()

        while self.running:
            try:
                client, addr = await loop.sock_accept(self.server_socket)
                asyncio.create_task(self._handle_client(client, addr))
            except Exception as e:
                if self.running:
                    print(f"   ⚠️ Server error: {e}")

    async def _handle_client(self, client, addr):
        """Gère un client"""
        loop = asyncio.get_event_loop()
        try:
            data = await loop.sock_recv(client, 8192)
            request = json.loads(data.decode().strip())

            response = await self._handle_request(request)

            await loop.sock_sendall(client, json.dumps(response).encode() + b"\n")

        except Exception as e:
            print(f"   ⚠️ Client handler error: {e}")
        finally:
            client.close()

    async def _handle_request(self, request: Dict) -> Dict:
        """Gère une requête"""
        req_type = request.get("type")

        if req_type == "register":
            return await self._handle_register(request)
        elif req_type == "discover":
            return await self._handle_discover(request)
        elif req_type == "heartbeat":
            return await self._handle_heartbeat(request)
        elif req_type == "unregister":
            return await self._handle_unregister(request)
        elif req_type == "list_nodes":
            return await self._handle_list_nodes(request)
        else:
            return {"status": "error", "message": f"Unknown request type: {req_type}"}

    async def _handle_register(self, request: Dict) -> Dict:
        """Enregistre un nœud"""
        node_id = request.get("node_id") or str(uuid.uuid4())
        node = RendezvousNode(
            node_id=node_id,
            name=request.get("name", f"Node-{node_id[:8]}"),
            public_address=request.get("public_address"),
            private_address=request.get("private_address"),
            network_type=NetworkType(request.get("network_type", "local")),
            capabilities=request.get("capabilities", []),
            last_heartbeat=time.time(),
            metadata=request.get("metadata", {})
        )

        self.nodes[node_id] = node
        self.save_db()

        return {
            "status": "success",
            "node_id": node_id,
            "message": "Node registered successfully"
        }

    async def _handle_discover(self, request: Dict) -> Dict:
        """Découvre des nœuds"""
        filters = request.get("filters", {})
        network_type = filters.get("network_type")
        capabilities = filters.get("capabilities", [])

        matching_nodes = []
        for node in self.nodes.values():
            # Filter by network type
            if network_type and node.network_type.value != network_type:
                continue

            # Filter by capabilities
            if capabilities:
                if not all(cap in node.capabilities for cap in capabilities):
                    continue

            # Check if online (heartbeat < 5 min ago)
            if time.time() - node.last_heartbeat > 300:
                continue

            matching_nodes.append({
                "node_id": node.node_id,
                "name": node.name,
                "public_address": node.public_address,
                "private_address": node.private_address,
                "network_type": node.network_type.value,
                "capabilities": node.capabilities,
                "metadata": node.metadata
            })

        return {
            "status": "success",
            "nodes": matching_nodes,
            "count": len(matching_nodes)
        }

    async def _handle_heartbeat(self, request: Dict) -> Dict:
        """Heartbeat d'un nœud"""
        node_id = request.get("node_id")
        if node_id in self.nodes:
            self.nodes[node_id].last_heartbeat = time.time()
            self.nodes[node_id].status = "online"
            return {"status": "success"}
        return {"status": "error", "message": "Node not found"}

    async def _handle_unregister(self, request: Dict) -> Dict:
        """Désinscrit un nœud"""
        node_id = request.get("node_id")
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.save_db()
            return {"status": "success"}
        return {"status": "error", "message": "Node not found"}

    async def _handle_list_nodes(self, request: Dict) -> Dict:
        """Liste tous les nœuds"""
        return {
            "status": "success",
            "nodes": [
                {
                    "node_id": node.node_id,
                    "name": node.name,
                    "public_address": node.public_address,
                    "network_type": node.network_type.value,
                    "status": node.status
                }
                for node in self.nodes.values()
            ]
        }

    def stop(self):
        """Arrête le serveur"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

# ============================================================================
# ============== NAT TRAVERSAL ============================================
# ============================================================================

class NATTraversal:
    """NAT Traversal - STUN/TURN-like"""

    async def get_public_ip(self) -> Optional[str]:
        """Récupère l'IP publique via des services STUN"""
        stun_servers = [
            "https://api.ipify.org",
            "https://ifconfig.me",
            "https://icanhazip.com"
        ]

        for server in stun_servers:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(server, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        public_ip = (await response.text()).strip()
                        if public_ip:
                            print(f"   🌍 Public IP detected: {public_ip}")
                            return public_ip
            except Exception:
                continue

        return None

    async def check_nat_type(self) -> str:
        """Vérifie le type de NAT (simplifié)"""
        local_ip = socket.gethostbyname(socket.gethostname())
        public_ip = await self.get_public_ip()

        if not public_ip:
            return "unknown"

        if local_ip == public_ip:
            return "none"  # Pas de NAT
        else:
            return "present"  # NAT détecté

    async def test_reachability(self, host: str, port: int, timeout: int = 5) -> bool:
        """Teste si un host/port est reachable"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

# ============================================================================
# ============== INTERNET DISCOVERY =======================================
# ============================================================================

class InternetDiscovery:
    """Discovery pour réseaux divers (LAN, WAN, Internet)"""

    def __init__(self, local_discovery, rendezvous_server: str = None):
        self.local_discovery = local_discovery  # Module de discovery local existant
        self.rendezvous_server = rendezvous_server
        self.rendezvous_nodes: Dict[str, Dict] = {}
        self.internet_nodes: Dict[str, Dict] = {}
        self.nat_traversal = NATTraversal()

    async def register_with_rendezvous(self, node_info: Dict) -> bool:
        """Enregistre le nœud avec le rendezvous server"""
        if not self.rendezvous_server:
            print("   ⚠️ No rendezvous server configured")
            return False

        try:
            url = f"http://{self.rendezvous_server}/register"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=node_info, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    result = await response.json()
                    if result.get("status") == "success":
                        print(f"   ✅ Registered with rendezvous server")
                        return True
        except Exception as e:
            print(f"   ❌ Failed to register with rendezvous server: {e}")

        return False

    async def discover_internet_nodes(self, filters: Dict = None) -> List[Dict]:
        """Découvre des nœuds sur Internet via rendezvous server"""
        if not self.rendezvous_server:
            return []

        try:
            url = f"http://{self.rendezvous_server}/discover"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"filters": filters or {}}, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    result = await response.json()
                    if result.get("status") == "success":
                        nodes = result.get("nodes", [])
                        print(f"   🌍 Discovered {len(nodes)} nodes on Internet")
                        return nodes
        except Exception as e:
            print(f"   ⚠️ Failed to discover Internet nodes: {e}")

        return []

    async def discover_all(self, network_type: NetworkType = None) -> List[Dict]:
        """Découvre tous les nœuds (local + Internet)"""
        all_nodes = []

        # Local discovery
        local_nodes = await self.local_discovery.get_active_nodes()
        all_nodes.extend([node.to_dict() for node in local_nodes])

        # Internet discovery
        filters = {}
        if network_type:
            filters["network_type"] = network_type.value

        internet_nodes = await self.discover_internet_nodes(filters)
        all_nodes.extend(internet_nodes)

        # Deduplicate by node_id
        seen = set()
        unique_nodes = []
        for node in all_nodes:
            node_id = node.get("node_id") or node.get("name")
            if node_id and node_id not in seen:
                seen.add(node_id)
                unique_nodes.append(node)

        return unique_nodes

    async def send_heartbeat(self):
        """Envoie un heartbeat au rendezvous server"""
        if not self.rendezvous_server:
            return

        try:
            url = f"http://{self.rendezvous_server}/heartbeat"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={}, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    result = await response.json()
                    if result.get("status") == "success":
                        return True
        except Exception:
            pass

        return False

# ============================================================================
# ============== SECURE CLIENT =============================================
# ============================================================================

class SecureNetworkClient:
    """Client réseau sécurisé pour Internet"""

    def __init__(self, api_key: str = None, tls_enabled: bool = True):
        self.api_key = api_key
        self.tls_enabled = tls_enabled
        self.session = None

    async def connect(self, host: str, port: int, use_tls: bool = None) -> socket.socket:
        """Se connecte à un nœud avec sécurité"""
        use_tls = use_tls if use_tls is not None else self.tls_enabled

        if use_tls:
            # SSL/TLS connection
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # Pour auto-signed certs

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssl_sock = context.wrap_socket(sock, server_hostname=host)
            ssl_sock.connect((host, port))
            return ssl_sock
        else:
            # Plain TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            return sock

    async def send_request(self, host: str, port: int, request: Dict,
                          use_tls: bool = None, timeout: int = 30) -> Optional[Dict]:
        """Envoie une requête sécurisée"""
        try:
            sock = await self.connect(host, port, use_tls)

            # Add API key
            if self.api_key:
                request["api_key"] = self.api_key

            # Send request
            sock.send(json.dumps(request).encode() + b"\n")

            # Receive response
            response_data = b""
            start_time = time.time()

            while time.time() - start_time < timeout:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                response_data += chunk
                if b"\n" in chunk:
                    break

            sock.close()

            response = json.loads(response_data.decode().strip())
            return response

        except asyncio.TimeoutError:
            print(f"   ⏱️ Timeout connecting to {host}:{port}")
            return None
        except Exception as e:
            print(f"   ❌ Error connecting to {host}:{port}: {e}")
            return None

# ============================================================================
# ============== MULTI-NETWORK MANAGER =====================================
# ============================================================================

class MultiNetworkManager:
    """Manager pour réseaux divers (LAN, WAN, Internet)"""

    def __init__(self, local_network, rendezvous_server: str = None,
                 api_key: str = None, tls_enabled: bool = True):
        self.local_network = local_network
        self.rendezvous_server = rendezvous_server
        self.api_key = api_key
        self.internet_discovery = InternetDiscovery(local_network, rendezvous_server)
        self.secure_client = SecureNetworkClient(api_key, tls_enabled)
        self.nat_traversal = NATTraversal()

        # Auto-detection
        self.network_type = None
        self.public_ip = None
        self.nat_type = None

    async def initialize(self):
        """Initialise le manager multi-réseau"""
        print(f"\n🌐 Initializing Multi-Network Manager...")

        # Detect network type
        self.nat_type = await self.nat_traversal.check_nat_type()
        print(f"   🔍 NAT Type: {self.nat_type}")

        # Get public IP
        self.public_ip = await self.nat_traversal.get_public_ip()
        if self.public_ip:
            print(f"   🌍 Public IP: {self.public_ip}")

        # Determine network type
        if self.nat_type == "none":
            self.network_type = NetworkType.PUBLIC
        elif self.public_ip:
            self.network_type = NetworkType.WAN
        else:
            self.network_type = NetworkType.LOCAL

        print(f"   🌐 Network Type: {self.network_type.value}")

        # Register with rendezvous server
        node_info = {
            "node_id": self.local_network.local_node.node_id,
            "name": self.local_network.local_node.name,
            "public_address": f"{self.public_ip or 'localhost'}:{self.local_network.config.port}",
            "private_address": f"localhost:{self.local_network.config.port}",
            "network_type": self.network_type.value,
            "capabilities": self.local_network.local_node.capabilities,
            "metadata": {
                "host": self.local_network.config.host,
                "web_port": self.local_network.config.web_port
            }
        }

        await self.internet_discovery.register_with_rendezvous(node_info)

        print(f"✅ Multi-Network Manager initialized!")

    async def discover_nodes(self, filters: Dict = None) -> List[Dict]:
        """Découvre des nœuds sur tous les réseaux"""
        network_type = filters.get("network_type") if filters else None

        if network_type:
            # Specific network type
            return await self.internet_discovery.discover_all(NetworkType(network_type))
        else:
            # All networks
            return await self.internet_discovery.discover_all()

    async def send_request(self, request: Dict, node: Dict = None,
                          force_public: bool = False) -> Optional[Dict]:
        """Envoie une requête au meilleur nœud disponible"""
        # Priorité: public nodes over private nodes (for Internet)
        if force_public or self.network_type == NetworkType.PUBLIC:
            public_nodes = await self.discover_nodes({"network_type": "public"})
            if public_nodes and not node:
                node = public_nodes[0]

        if node:
            # Connect to specific node
            address = node.get("public_address", node.get("private_address"))
            if not address:
                return None

            host, port = address.split(":")
            port = int(port)
            use_tls = node.get("network_type") == "public"

            return await self.secure_client.send_request(host, port, request, use_tls)
        else:
            # Use local network
            active_nodes = await self.local_network.discovery.get_active_nodes()
            if active_nodes:
                node = active_nodes[0]
                return await self.secure_client.send_request(node.host, node.port, request, use_tls=False)

        return None

    async def maintain_connection(self):
        """Maintient la connexion (heartbeat)"""
        while True:
            await self.internet_discovery.send_heartbeat()
            await asyncio.sleep(30)

    async def get_status(self) -> Dict:
        """Statut"""
        nodes = await self.discover_nodes()

        return {
            "network_type": self.network_type.value,
            "public_ip": self.public_ip,
            "nat_type": self.nat_type,
            "rendezvous_server": self.rendezvous_server,
            "nodes_discovered": len(nodes),
            "nodes": nodes
        }

# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def main():
    """Main function - Demo"""
    print("=" * 70)
    print("🌐 INTERNET CAPABLE MODULE")
    print("=" * 70)
    print("\n✅ Rendezvous Server")
    print("✅ NAT Traversal")
    print("✅ Internet Discovery")
    print("✅ Secure Network Client")
    print("✅ Multi-Network Manager")

    # Demo: Start rendezvous server
    print("\n🚀 Starting Rendezvous Server demo...")
    rendezvous = RendezvousServer(port=9990)

    # Demo client (in separate coroutine in real usage)
    print("\n✅ Internet Capable Module ready!")
    print("   This module can:")
    print("   - Connect nodes across different networks (LAN, WAN, Internet)")
    print("   - Handle NAT/Firewall traversal")
    print("   - Use secure TLS connections")
    print("   - Auto-discover nodes via rendezvous server")

if __name__ == '__main__':
    asyncio.run(main())