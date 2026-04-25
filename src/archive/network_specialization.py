#!/usr/bin/env python3
"""
🌐 NETWORK SPECIALIZATION MODULE
Spécialisation réseau pour UnityBrain & BugBrain v3.0
Interconnexion, déploiement, auto-discovery, load balancing, failover
"""

import asyncio
import socket
import json
import time
import hashlib
import uuid
import subprocess
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import ssl

# ============================================================================
# ============== NETWORK CONFIG ===========================================
# ============================================================================

class NetworkConfig:
    """Configuration réseau"""
    def __init__(self):
        # Basic
        self.host = "0.0.0.0"
        self.port = 9999
        self.web_port = 8080

        # Discovery
        self.discovery_enabled = True
        self.discovery_port = 9998
        self.discovery_interval = 30  # seconds
        self.broadcast_enabled = True

        # Load Balancing
        self.load_balancing_enabled = True
        self.load_balancing_strategy = "round_robin"  # round_robin, least_connections, weighted

        # Failover
        self.failover_enabled = True
        self.failover_threshold = 3  # failures before failover
        self.failover_timeout = 60  # seconds before retry

        # Security
        self.tls_enabled = False
        self.tls_cert_path = None
        self.tls_key_path = None
        self.api_key = None

        # Deployment
        self.deployment_mode = "standalone"  # standalone, cluster, distributed
        self.cluster_nodes = []  # List of node addresses

# ============================================================================
# ============== NETWORK NODE ==============================================
# ============================================================================

class NodeStatus(Enum):
    """Statut d'un nœud"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"

@dataclass
class NetworkNode:
    """Représente un nœud dans le réseau"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "unknown"
    host: str = "localhost"
    port: int = 9999
    web_port: int = 8080
    status: NodeStatus = NodeStatus.INACTIVE
    last_seen: float = 0.0
    latency: float = float('inf')
    connections: int = 0
    max_connections: int = 100
    capabilities: List[str] = field(default_factory=list)

    # Failover tracking
    consecutive_failures: int = 0
    last_failure: float = 0.0

    # Load balancing
    weight: float = 1.0

    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "web_port": self.web_port,
            "status": self.status.value,
            "last_seen": self.last_seen,
            "latency": self.latency,
            "connections": self.connections,
            "max_connections": self.max_connections,
            "capabilities": self.capabilities,
            "consecutive_failures": self.consecutive_failures,
            "last_failure": self.last_failure,
            "weight": self.weight
        }

# ============================================================================
# ============== SERVICE DISCOVERY =========================================
# ============================================================================

class ServiceDiscovery:
    """Service discovery - Auto-discovery des nœuds"""
    def __init__(self, config: NetworkConfig):
        self.config = config
        self.nodes: Dict[str, NetworkNode] = {}
        self.local_node_id = str(uuid.uuid4())
        self.discovered_nodes = set()
        self.heartbeat_interval = config.discovery_interval

    async def broadcast_presence(self):
        """Broadcast la présence du nœud local"""
        if not self.config.broadcast_enabled:
            return

        presence = {
            "type": "presence",
            "node_id": self.local_node_id,
            "host": self.config.host,
            "port": self.config.port,
            "web_port": self.config.web_port,
            "timestamp": time.time(),
            "capabilities": ["unitybrain", "bugbrain"]
        }

        # UDP broadcast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1)

        try:
            sock.sendto(
                json.dumps(presence).encode(),
                ("255.255.255.255", self.config.discovery_port)
            )
        except Exception:
            pass
        finally:
            sock.close()

    async def listen_for_presence(self):
        """Écoute les broadcasts de présence"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", self.config.discovery_port))
        except Exception as e:
            print(f"   ⚠️ Cannot bind to discovery port: {e}")
            return

        sock.settimeout(1)

        while True:
            try:
                data, addr = sock.recvfrom(8192)
                presence = json.loads(data.decode())

                # Ignore notre propre broadcast
                if presence.get("node_id") == self.local_node_id:
                    continue

                # Ajouter ou mettre à jour le nœud
                await self._update_node_from_presence(presence, addr[0])

            except socket.timeout:
                continue
            except Exception as e:
                print(f"   ⚠️ Discovery error: {e}")

    async def _update_node_from_presence(self, presence: Dict, sender_host: str):
        """Met à jour un nœud depuis un broadcast de présence"""
        node_id = presence["node_id"]

        if node_id not in self.nodes:
            node = NetworkNode(
                node_id=node_id,
                name=presence.get("name", f"Node-{node_id[:8]}"),
                host=sender_host,
                port=presence["port"],
                web_port=presence["web_port"],
                capabilities=presence.get("capabilities", [])
            )
            self.nodes[node_id] = node
            self.discovered_nodes.add(node_id)
            print(f"   🆕 Discovered new node: {node.name} ({sender_host}:{node.port})")
        else:
            node = self.nodes[node_id]
            node.last_seen = time.time()
            node.status = NodeStatus.ACTIVE

    async def check_node_health(self):
        """Vérifie la santé des nœuds"""
        for node_id, node in list(self.nodes.items()):
            # Remove stale nodes
            if time.time() - node.last_seen > self.heartbeat_interval * 3:
                if node.status != NodeStatus.INACTIVE:
                    print(f"   ⚠️ Node {node.name} became inactive")
                    node.status = NodeStatus.INACTIVE

    async def get_active_nodes(self) -> List[NetworkNode]:
        """Retourne les nœuds actifs"""
        return [node for node in self.nodes.values() if node.status == NodeStatus.ACTIVE]

# ============================================================================
# ============== LOAD BALANCER ============================================
# ============================================================================

class LoadBalancer:
    """Load balancer"""
    def __init__(self, config: NetworkConfig, nodes: Dict[str, NetworkNode]):
        self.config = config
        self.nodes = nodes
        self.round_robin_index = 0

    async def select_node(self, nodes: List[NetworkNode]) -> Optional[NetworkNode]:
        """Sélectionne un nœud selon la stratégie"""
        if not nodes:
            return None

        if not self.config.load_balancing_enabled:
            return nodes[0]

        strategy = self.config.load_balancing_strategy

        if strategy == "round_robin":
            return await self._select_round_robin(nodes)
        elif strategy == "least_connections":
            return await self._select_least_connections(nodes)
        elif strategy == "weighted":
            return await self._select_weighted(nodes)
        else:
            return nodes[0]

    async def _select_round_robin(self, nodes: List[NetworkNode]) -> NetworkNode:
        """Sélection Round Robin"""
        node = nodes[self.round_robin_index % len(nodes)]
        self.round_robin_index += 1
        return node

    async def _select_least_connections(self, nodes: List[NetworkNode]) -> NetworkNode:
        """Sélection least connections"""
        return min(nodes, key=lambda n: n.connections)

    async def _select_weighted(self, nodes: List[NetworkNode]) -> NetworkNode:
        """Sélection pondérée"""
        # Sélection pondérée par le weight
        total_weight = sum(n.weight for n in nodes)
        if total_weight == 0:
            return nodes[0]

        threshold = random.uniform(0, total_weight)
        current = 0
        for node in nodes:
            current += node.weight
            if current >= threshold:
                return node
        return nodes[0]

# ============================================================================
# ============== FAILOVER MANAGER ==========================================
# ============================================================================

class FailoverManager:
    """Gestionnaire de failover"""
    def __init__(self, config: NetworkConfig, nodes: Dict[str, NetworkNode]):
        self.config = config
        self.nodes = nodes

    async def record_failure(self, node: NetworkNode):
        """Enregistre une failure sur un nœud"""
        node.consecutive_failures += 1
        node.last_failure = time.time()

        # Marquer comme degraded si threshold atteint
        if node.consecutive_failures >= self.config.failover_threshold:
            if node.status != NodeStatus.DEGRADED:
                print(f"   ⚠️ Node {node.name} marked as DEGRADED")
                node.status = NodeStatus.DEGRADED

    async def record_success(self, node: NetworkNode):
        """Enregistre un succès sur un nœud"""
        node.consecutive_failures = 0
        if node.status == NodeStatus.DEGRADED:
            print(f"   ✅ Node {node.name} recovered to ACTIVE")
            node.status = NodeStatus.ACTIVE

    async def get_healthy_nodes(self) -> List[NetworkNode]:
        """Retourne les nœuds sains"""
        return [
            node for node in self.nodes.values()
            if node.status in [NodeStatus.ACTIVE, NodeStatus.DEGRADED]
        ]

# ============================================================================
# ============== NETWORK CLIENT ============================================
# ============================================================================

class NetworkClient:
    """Client réseau"""
    def __init__(self, config: NetworkConfig, failover: FailoverManager):
        self.config = config
        self.failover = failover
        self.session_cache = {}

    async def send_request(self, node: NetworkNode, request: Dict) -> Optional[Dict]:
        """Envoie une requête à un nœud"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.config.tls_enabled:
                # TLS wrapping
                context = ssl.create_default_context()
                if self.config.tls_cert_path:
                    context.load_verify_locations(self.config.tls_cert_path)
                sock = context.wrap_socket(sock, server_hostname=node.host)

            sock.settimeout(10)
            sock.connect((node.host, node.port))

            # Send request
            sock.send(json.dumps(request).encode() + b"\n")

            # Receive response
            response_data = b""
            while True:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                response_data += chunk
                if b"\n" in chunk:
                    break

            sock.close()

            response = json.loads(response_data.decode().strip())

            # Enregistrer le succès
            await self.failover.record_success(node)

            return response

        except Exception as e:
            # Enregistrer la failure
            await self.failover.record_failure(node)
            print(f"   ❌ Error connecting to {node.name}: {e}")
            return None

# ============================================================================
# ============== NETWORK SERVER ============================================
# ============================================================================

class NetworkServer:
    """Serveur réseau"""
    def __init__(self, config: NetworkConfig, local_node: NetworkNode):
        self.config = config
        self.local_node = local_node
        self.server_socket = None
        self.request_handlers = {}
        self.running = False

    def register_handler(self, request_type: str, handler: Callable):
        """Enregistre un handler pour un type de requête"""
        self.request_handlers[request_type] = handler

    async def start(self):
        """Démarre le serveur"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.config.host, self.config.port))
        self.server_socket.listen(5)
        self.server_socket.setblocking(False)

        self.running = True
        print(f"\n🌐 Network server started on {self.config.host}:{self.config.port}")

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

            # Dispatch to handler
            request_type = request.get("type", "unknown")
            handler = self.request_handlers.get(request_type)

            if handler:
                response = await handler(request)
            else:
                response = {"status": "error", "message": f"Unknown request type: {request_type}"}

            await loop.sock_sendall(client, json.dumps(response).encode() + b"\n")

            # Update connection count
            self.local_node.connections += 1

        except Exception as e:
            print(f"   ⚠️ Client handler error: {e}")
        finally:
            client.close()
            if self.local_node.connections > 0:
                self.local_node.connections -= 1

    def stop(self):
        """Arrête le serveur"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

# ============================================================================
# ============== NETWORK MANAGER ===========================================
# ============================================================================

class NetworkManager:
    """Manager réseau complet"""
    def __init__(self, config: NetworkConfig = None):
        self.config = config or NetworkConfig()

        # Local node
        self.local_node = NetworkNode(
            name=f"Node-{str(uuid.uuid4())[:8]}",
            host=self.config.host,
            port=self.config.port,
            web_port=self.config.web_port,
            status=NodeStatus.ACTIVE,
            last_seen=time.time()
        )

        # Components
        self.discovery = ServiceDiscovery(self.config)
        self.load_balancer = LoadBalancer(self.config, self.discovery.nodes)
        self.failover = FailoverManager(self.config, self.discovery.nodes)
        self.client = NetworkClient(self.config, self.failover)
        self.server = NetworkServer(self.config, self.local_node)

        # Running tasks
        self.tasks = []

    async def initialize(self):
        """Initialise le réseau"""
        print(f"\n🌐 Initializing Network Specialization...")
        print(f"   Host: {self.config.host}:{self.config.port}")
        print(f"   Discovery: {'Enabled' if self.config.discovery_enabled else 'Disabled'}")
        print(f"   Load Balancing: {'Enabled' if self.config.load_balancing_enabled else 'Disabled'}")
        print(f"   Failover: {'Enabled' if self.config.failover_enabled else 'Disabled'}")

        # Register default handlers
        self._register_default_handlers()

        print(f"\n✅ Network Specialization initialized!")

    def _register_default_handlers(self):
        """Enregistre les handlers par défaut"""
        self.server.register_handler("ping", self._handle_ping)
        self.server.register_handler("status", self._handle_status)
        self.server.register_handler("query", self._handle_query)

    async def _handle_ping(self, request: Dict) -> Dict:
        """Handler pour ping"""
        return {
            "status": "success",
            "type": "pong",
            "node_id": self.local_node.node_id,
            "timestamp": time.time()
        }

    async def _handle_status(self, request: Dict) -> Dict:
        """Handler pour status"""
        return {
            "status": "success",
            "node": self.local_node.to_dict()
        }

    async def _handle_query(self, request: Dict) -> Dict:
        """Handler pour query (à override)"""
        return {
            "status": "success",
            "response": "Query received"
        }

    async def start(self):
        """Démarre le réseau"""
        # Start server
        server_task = asyncio.create_task(self.server.start())
        self.tasks.append(server_task)

        # Start discovery
        if self.config.discovery_enabled:
            discovery_listen_task = asyncio.create_task(self.discovery.listen_for_presence())
            self.tasks.append(discovery_listen_task)

            # Broadcast presence periodically
            async def broadcast_loop():
                while True:
                    await self.discovery.broadcast_presence()
                    await asyncio.sleep(self.config.discovery_interval)

            broadcast_task = asyncio.create_task(broadcast_loop())
            self.tasks.append(broadcast_task)

            # Check node health
            async def health_check_loop():
                while True:
                    await self.discovery.check_node_health()
                    await asyncio.sleep(self.config.discovery_interval)

            health_task = asyncio.create_task(health_check_loop())
            self.tasks.append(health_task)

        print(f"\n🚀 Network Specialization started!")

    async def stop(self):
        """Arrête le réseau"""
        self.server.stop()
        for task in self.tasks:
            task.cancel()
        print(f"\n🛑 Network Specialization stopped")

    async def send_request(self, request: Dict, node: NetworkNode = None) -> Optional[Dict]:
        """Envoie une requête"""
        if node:
            return await self.client.send_request(node, request)
        else:
            # Sélectionner un nœud via load balancer
            active_nodes = await self.discovery.get_active_nodes()
            selected_node = await self.load_balancer.select_node(active_nodes)
            if selected_node:
                return await self.client.send_request(selected_node, request)
            return None

    async def get_status(self) -> Dict:
        """Statut du réseau"""
        active_nodes = await self.discovery.get_active_nodes()

        return {
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "discovery_enabled": self.config.discovery_enabled,
                "load_balancing_enabled": self.config.load_balancing_enabled,
                "failover_enabled": self.config.failover_enabled
            },
            "local_node": self.local_node.to_dict(),
            "nodes": {
                "total": len(self.discovery.nodes),
                "active": len(active_nodes),
                "list": [node.to_dict() for node in active_nodes]
            }
        }

# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def main():
    """Main function"""
    print("=" * 70)
    print("🌐 NETWORK SPECIALIZATION MODULE")
    print("=" * 70)
    print("\n✅ Service Discovery")
    print("✅ Load Balancing")
    print("✅ Failover Management")
    print("✅ Auto-Discovery")
    print("✅ Network Client & Server")

    # Create network manager
    network = NetworkManager()

    # Initialize
    await network.initialize()

    # Start
    await network.start()

    # Test status
    status = await network.get_status()
    print(f"\n📊 Status:")
    print(f"   Local Node: {status['local_node']['name']}")
    print(f"   Active Nodes: {status['nodes']['active']}/{status['nodes']['total']}")

    # Keep running
    try:
        while True:
            await asyncio.sleep(10)
            status = await network.get_status()
            print(f"\n📊 [Every 10s] Active Nodes: {status['nodes']['active']}")
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping...")
        await network.stop()

if __name__ == '__main__':
    asyncio.run(main())