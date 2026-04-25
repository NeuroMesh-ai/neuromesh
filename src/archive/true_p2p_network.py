#!/usr/bin/env python3
"""
🔄 TRUE P2P NETWORK - DÉCENTRALISÉ
Système P2P pur sans serveur centralisé
DHT (Distributed Hash Table) + Gossip Protocol + Bootstrap
"""

import asyncio
import socket
import json
import time
import hashlib
import random
import string
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

# ============================================================================
# ============== P2P CONFIG ================================================
# ============================================================================

class P2PConfig:
    """Configuration P2P"""
    def __init__(self):
        self.bootstrap_nodes = []  # List of (host, port) for initial discovery
        self.k = 16  # Kademlia K parameter (nodes in bucket)
        self.alpha = 3  # Kademlia alpha (parallel lookups)
        self.id_length = 160  # SHA-1 hash length (bits)
        self.redundancy = 3  # Number of replicas for values
        self.refresh_interval = 3600  # Refresh buckets every hour
        self.gossip_interval = 30  # Gossip interval
        self.max_connections = 100

# ============================================================================
# ============== DHT NODE ID ===============================================
# ============================================================================

class NodeID:
    """ID de nœud (hash SHA-1)"""
    def __init__(self, node_id: str = None):
        self.id = node_id or self._generate_id()

    def _generate_id(self) -> str:
        """Génère un ID aléatoire"""
        # Simuler un hash SHA-1 de 160 bits (40 hex chars)
        return ''.join(random.choices('0123456789abcdef', k=40))

    @staticmethod
    def from_address(host: str, port: int) -> 'NodeID':
        """Crée un ID depuis une adresse"""
        data = f"{host}:{port}".encode()
        hash_obj = hashlib.sha1(data)
        return NodeID(hash_obj.hexdigest())

    def distance(self, other: 'NodeID') -> int:
        """Calcule la distance XOR"""
        return int(self.id, 16) ^ int(other.id, 16)

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"NodeID({self.id[:16]}...)"

# ============================================================================
# ============== PEER INFO ================================================
# ============================================================================

@dataclass
class PeerInfo:
    """Information sur un peer"""
    node_id: NodeID
    host: str
    port: int
    last_seen: float = 0.0
    last_ping: float = 0.0
    latency: float = float('inf')
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            "node_id": str(self.node_id),
            "host": self.host,
            "port": self.port,
            "last_seen": self.last_seen,
            "last_ping": self.last_ping,
            "latency": self.latency,
            "capabilities": self.capabilities,
            "metadata": self.metadata
        }

    @staticmethod
    def from_dict(data: Dict) -> 'PeerInfo':
        """Crée depuis un dictionnaire"""
        return PeerInfo(
            node_id=NodeID(data["node_id"]),
            host=data["host"],
            port=data["port"],
            last_seen=data.get("last_seen", 0.0),
            last_ping=data.get("last_ping", 0.0),
            latency=data.get("latency", float('inf')),
            capabilities=data.get("capabilities", []),
            metadata=data.get("metadata", {})
        )

# ============================================================================
# ============== KADEMLIA ROUTING TABLE ==================================
# ============================================================================

class RoutingTable:
    """Table de routage Kademlia"""
    def __init__(self, local_node_id: NodeID, config: P2PConfig):
        self.local_node_id = local_node_id
        self.config = config
        self.buckets: List[Set[PeerInfo]] = [set() for _ in range(config.id_length)]

    def add_peer(self, peer: PeerInfo):
        """Ajoute un peer à la table"""
        bucket_index = self._get_bucket_index(peer.node_id)
        bucket = self.buckets[bucket_index]

        if peer not in bucket:
            # Si le bucket est plein, supprimer le plus ancien
            if len(bucket) >= self.config.k:
                oldest = min(bucket, key=lambda p: p.last_seen)
                bucket.remove(oldest)

            bucket.add(peer)

    def get_bucket_index(self, node_id: NodeID) -> int:
        """Retourne l'index du bucket pour un node_id"""
        return self.local_node_id.distance(node_id).bit_length() - 1

    def _get_bucket_index(self, node_id: NodeID) -> int:
        return self.get_bucket_index(node_id)

    def find_closest(self, target: NodeID, count: int = None) -> List[PeerInfo]:
        """Trouve les peers les plus proches d'une cible"""
        count = count or self.config.k

        all_peers = [peer for bucket in self.buckets for peer in bucket]
        all_peers.sort(key=lambda p: target.distance(p.node_id))

        return all_peers[:count]

    def remove_peer(self, peer: PeerInfo):
        """Supprime un peer"""
        bucket_index = self._get_bucket_index(peer.node_id)
        self.buckets[bucket_index].discard(peer)

    def get_stats(self) -> Dict:
        """Statistiques de la table"""
        return {
            "total_peers": sum(len(bucket) for bucket in self.buckets),
            "buckets": len(self.buckets),
            "k": self.config.k
        }

# ============================================================================
# ============== DHT STORE ================================================
# ============================================================================

class DHTStore:
    """DHT Store - Stockage distribué"""
    def __init__(self, config: P2PConfig):
        self.config = config
        self.data: Dict[str, Any] = {}  # key -> value
        self.replicas: Dict[str, Set[NodeID]] = {}  # key -> set of responsible nodes

    def store(self, key: str, value: Any, responsible_nodes: List[NodeID]):
        """Stocke une valeur avec réplication"""
        self.data[key] = {
            "value": value,
            "timestamp": time.time(),
            "replicas": [str(node_id) for node_id in responsible_nodes]
        }

    def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur"""
        if key in self.data:
            return self.data[key]["value"]
        return None

    def find_responsible(self, key: str, my_node_id: NodeID,
                       known_peers: List[PeerInfo]) -> List[NodeID]:
        """Trouve les nœuds responsables d'une clé"""
        key_id = NodeID(hashlib.sha1(key.encode()).hexdigest())

        all_nodes = [my_node_id] + [peer.node_id for peer in known_peers]
        all_nodes.sort(key=lambda n: key_id.distance(n))

        return all_nodes[:self.config.redundancy]

# ============================================================================
# ============== GOSSIP PROTOCOL =========================================
# ============================================================================

class GossipProtocol:
    """Protocol de Gossip pour propagation d'informations"""
    def __init__(self, config: P2PConfig):
        self.config = config
        self.information: Dict[str, Dict] = {}  # info_type -> {info_id: info}

    def add_info(self, info_type: str, info_id: str, info: Any):
        """Ajoute une information"""
        if info_type not in self.information:
            self.information[info_type] = {}

        self.information[info_type][info_id] = {
            "info": info,
            "timestamp": time.time(),
            "hops": 0
        }

    def get_info(self, info_type: str, info_id: str) -> Optional[Dict]:
        """Récupère une information"""
        if info_type in self.information and info_id in self.information[info_type]:
            return self.information[info_type][info_id]
        return None

    def get_all_info(self, info_type: str) -> Dict:
        """Récupère toutes les informations d'un type"""
        return self.information.get(info_type, {})

    def merge_info(self, info_type: str, incoming_info: Dict):
        """Fusionne les informations reçues"""
        if info_type not in self.information:
            self.information[info_type] = {}

        for info_id, info_data in incoming_info.items():
            if info_id not in self.information[info_type]:
                # Nouvelle information
                self.information[info_type][info_id] = info_data
            else:
                # Fusionner (garder la plus récente)
                if info_data["timestamp"] > self.information[info_type][info_id]["timestamp"]:
                    self.information[info_type][info_id] = info_data

# ============================================================================
# ============== P2P MESSAGE ==============================================
# ============================================================================

class P2PMessage:
    """Message P2P"""
    def __init__(self, msg_type: str, payload: Dict, sender_id: NodeID,
                 message_id: str = None):
        self.msg_type = msg_type
        self.payload = payload
        self.sender_id = sender_id
        self.message_id = message_id or self._generate_id()
        self.timestamp = time.time()

    def _generate_id(self) -> str:
        """Génère un ID de message unique"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=16))

    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            "msg_type": self.msg_type,
            "payload": self.payload,
            "sender_id": str(self.sender_id),
            "message_id": self.message_id,
            "timestamp": self.timestamp
        }

    @staticmethod
    def from_dict(data: Dict) -> 'P2PMessage':
        """Crée depuis un dictionnaire"""
        return P2PMessage(
            msg_type=data["msg_type"],
            payload=data["payload"],
            sender_id=NodeID(data["sender_id"]),
            message_id=data["message_id"]
        )

# ============================================================================
# ============== P2P NODE ================================================
# ============================================================================

class P2PNode:
    """Nœud P2P complet"""
    def __init__(self, host: str, port: int, config: P2PConfig = None):
        self.host = host
        self.port = port
        self.config = config or P2PConfig()

        # Node ID
        self.node_id = NodeID.from_address(host, port)

        # Components
        self.routing_table = RoutingTable(self.node_id, self.config)
        self.dht_store = DHTStore(self.config)
        self.gossip = GossipProtocol(self.config)

        # Server
        self.server_socket = None
        self.running = False

        # Connections
        self.active_connections: Dict[NodeID, socket.socket] = {}

        # Background tasks
        self.tasks = []

    async def start(self):
        """Démarre le nœud"""
        print(f"\n🔄 Starting P2P Node...")
        print(f"   Node ID: {self.node_id}")
        print(f"   Host: {self.host}:{self.port}")

        # Start server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(self.config.max_connections)
        self.server_socket.setblocking(False)

        self.running = True

        # Bootstrap
        await self._bootstrap()

        # Start background tasks
        self._start_background_tasks()

        print(f"✅ P2P Node started!")

        # Accept connections
        await self._accept_connections()

    async def _bootstrap(self):
        """Bootstrap - Rejoindre le réseau via les nodes de bootstrap"""
        if not self.config.bootstrap_nodes:
            print(f"   📭 No bootstrap nodes configured, starting in isolation")
            return

        print(f"   🚀 Bootstrapping from {len(self.config.bootstrap_nodes)} nodes...")

        for bootstrap_host, bootstrap_port in self.config.bootstrap_nodes:
            try:
                # PING le bootstrap node
                await self._send_ping(bootstrap_host, bootstrap_port)

                # FIND_NODE pour trouver des peers proches
                await self._find_node(self.node_id, bootstrap_host, bootstrap_port)

            except Exception as e:
                print(f"   ⚠️ Failed to bootstrap from {bootstrap_host}:{bootstrap_port}: {e}")

    async def _send_ping(self, host: str, port: int) -> bool:
        """Envoie un PING"""
        message = P2PMessage("ping", {}, self.node_id)
        response = await self._send_message(host, port, message)
        return response is not None and response.get("msg_type") == "pong"

    async def _find_node(self, target: NodeID, host: str, port: int) -> List[PeerInfo]:
        """FIND_NODE - Trouve les nœuds proches d'une cible"""
        message = P2PMessage("find_node", {"target": str(target)}, self.node_id)
        response = await self._send_message(host, port, message)

        if response and response.get("msg_type") == "nodes":
            peers = [PeerInfo.from_dict(p) for p in response["payload"]["peers"]]
            for peer in peers:
                self.routing_table.add_peer(peer)
            return peers

        return []

    async def _send_message(self, host: str, port: int, message: P2PMessage,
                           timeout: int = 10) -> Optional[Dict]:
        """Envoie un message à un peer"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))

            # Send message
            sock.send(json.dumps(message.to_dict()).encode() + b"\n")

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
            return response

        except Exception as e:
            print(f"   ❌ Error sending message to {host}:{port}: {e}")
            return None

    def _start_background_tasks(self):
        """Démarre les tâches de fond"""
        # Gossip
        asyncio.create_task(self._gossip_loop())

        # Refresh routing table
        asyncio.create_task(self._refresh_loop())

        # Cleanup
        asyncio.create_task(self._cleanup_loop())

    async def _gossip_loop(self):
        """Boucle de Gossip"""
        while self.running:
            await asyncio.sleep(self.config.gossip_interval)
            await self._propagate_gossip()

    async def _propagate_gossip(self):
        """Propage les informations via gossip"""
        # Sélectionner quelques peers aléatoires
        all_peers = [peer for bucket in self.routing_table.buckets for peer in bucket]
        if not all_peers:
            return

        gossip_peers = random.sample(all_peers, min(3, len(all_peers)))

        for peer in gossip_peers:
            try:
                message = P2PMessage("gossip", {
                    "info": self.gossip.get_all_info("presence")
                }, self.node_id)
                await self._send_message(peer.host, peer.port, message)
            except Exception:
                pass

    async def _refresh_loop(self):
        """Boucle de refresh"""
        while self.running:
            await asyncio.sleep(self.config.refresh_interval)
            await self._refresh_routing_table()

    async def _refresh_routing_table(self):
        """Refresh la table de routage"""
        # Refresh chaque bucket
        for i in range(self.routing_table.config.id_length):
            if self.routing_table.buckets[i]:
                continue

            # Générer un ID aléatoire dans ce bucket
            random_id = NodeID._generate_id()
            await self._lookup_node(random_id)

    async def _cleanup_loop(self):
        """Boucle de cleanup"""
        while self.running:
            await asyncio.sleep(60)
            await self._cleanup_stale_peers()

    async def _cleanup_stale_peers(self):
        """Nettoie les peers obsolètes"""
        current_time = time.time()

        for i, bucket in enumerate(self.routing_table.buckets):
            stale_peers = [peer for peer in bucket if current_time - peer.last_seen > 3600]

            for peer in stale_peers:
                print(f"   🗑️ Removing stale peer: {peer.node_id}")
                self.routing_table.remove_peer(peer)

    async def _accept_connections(self):
        """Accepte les connexions entrantes"""
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                client, addr = await loop.sock_accept(self.server_socket)
                asyncio.create_task(self._handle_client(client, addr))
            except Exception as e:
                if self.running:
                    print(f"   ⚠️ Server error: {e}")

    async def _handle_client(self, client: socket.socket, addr):
        """Gère un client"""
        loop = asyncio.get_event_loop()
        try:
            data = await loop.sock_recv(client, 8192)
            request = json.loads(data.decode().strip())

            # Parser le message
            message = P2PMessage.from_dict(request)

            # Créer le peer info
            peer_info = PeerInfo(
                node_id=message.sender_id,
                host=addr[0],
                port=addr[1],
                last_seen=time.time()
            )

            # Ajouter à la table de routage
            self.routing_table.add_peer(peer_info)

            # Dispatch
            response = await self._handle_message(message, peer_info)

            # Envoyer la réponse
            await loop.sock_sendall(client, json.dumps(response).encode() + b"\n")

        except Exception as e:
            print(f"   ⚠️ Client handler error: {e}")
        finally:
            client.close()

    async def _handle_message(self, message: P2PMessage, sender: PeerInfo) -> Dict:
        """Gère un message"""
        msg_type = message.msg_type

        if msg_type == "ping":
            return await self._handle_ping(message, sender)
        elif msg_type == "find_node":
            return await self._handle_find_node(message, sender)
        elif msg_type == "store":
            return await self._handle_store(message, sender)
        elif msg_type == "get":
            return await self._handle_get(message, sender)
        elif msg_type == "gossip":
            return await self._handle_gossip(message, sender)
        else:
            return {"msg_type": "error", "payload": {"message": f"Unknown message type: {msg_type}"}}

    async def _handle_ping(self, message: P2PMessage, sender: PeerInfo) -> Dict:
        """Gère PING"""
        return P2PMessage("pong", {}, self.node_id).to_dict()

    async def _handle_find_node(self, message: P2PMessage, sender: PeerInfo) -> Dict:
        """Gère FIND_NODE"""
        target = NodeID(message.payload["target"])
        closest = self.routing_table.find_closest(target, self.config.k)

        return P2PMessage("nodes", {
            "peers": [peer.to_dict() for peer in closest]
        }, self.node_id).to_dict()

    async def _handle_store(self, message: P2PMessage, sender: PeerInfo) -> Dict:
        """Gère STORE"""
        key = message.payload["key"]
        value = message.payload["value"]

        responsible = self.dht_store.find_responsible(
            key, self.node_id,
            [peer for bucket in self.routing_table.buckets for peer in bucket]
        )

        if self.node_id in responsible:
            self.dht_store.store(key, value, responsible)
            return P2PMessage("stored", {"key": key, "replicas": len(responsible)}, self.node_id).to_dict()
        else:
            # Rediriger vers les nœuds responsables
            return P2PMessage("redirect", {
                "target": str(responsible[0])
            }, self.node_id).to_dict()

    async def _handle_get(self, message: P2PMessage, sender: PeerInfo) -> Dict:
        """Gère GET"""
        key = message.payload["key"]
        value = self.dht_store.get(key)

        if value is not None:
            return P2PMessage("value", {"key": key, "value": value}, self.node_id).to_dict()
        else:
            return P2PMessage("not_found", {"key": key}, self.node_id).to_dict()

    async def _handle_gossip(self, message: P2PMessage, sender: PeerInfo) -> Dict:
        """Gère GOSSIP"""
        info = message.payload.get("info", {})

        if info:
            # Fusionner les informations de présence
            self.gossip.merge_info("presence", info)

        return P2PMessage("gossip_ack", {}, self.node_id).to_dict()

    async def lookup_node(self, target: NodeID) -> List[PeerInfo]:
        """LOOKUP - Trouve des nœuds proches"""
        closest = self.routing_table.find_closest(target, self.config.alpha)

        for peer in closest:
            try:
                found = await self._find_node(target, peer.host, peer.port)
                if found:
                    closest.extend(found)
            except Exception:
                pass

        closest.sort(key=lambda p: target.distance(p.node_id))
        return closest[:self.config.k]

    async def _lookup_node(self, target: NodeID):
        """LOOKUP interne"""
        return await self.lookup_node(target)

    async def store(self, key: str, value: Any) -> bool:
        """STORE - Stocke une valeur dans la DHT"""
        responsible = self.dht_store.find_responsible(
            key, self.node_id,
            [peer for bucket in self.routing_table.buckets for peer in bucket]
        )

        # Stocker localement si responsable
        if self.node_id in responsible:
            self.dht_store.store(key, value, responsible)
            return True

        # Sinon, propager aux nœuds responsables
        for peer_id in responsible:
            peer = self._find_peer_by_id(peer_id)
            if peer:
                try:
                    message = P2PMessage("store", {"key": key, "value": value}, self.node_id)
                    await self._send_message(peer.host, peer.port, message)
                    return True
                except Exception:
                    pass

        return False

    def _find_peer_by_id(self, node_id: NodeID) -> Optional[PeerInfo]:
        """Trouve un peer par ID"""
        for bucket in self.routing_table.buckets:
            for peer in bucket:
                if peer.node_id.id == node_id.id:
                    return peer
        return None

    async def get(self, key: str) -> Optional[Any]:
        """GET - Récupère une valeur de la DHT"""
        value = self.dht_store.get(key)

        if value is not None:
            return value

        # Chercher sur les peers proches
        key_id = NodeID(hashlib.sha1(key.encode()).hexdigest())
        closest = self.routing_table.find_closest(key_id, self.config.alpha)

        for peer in closest:
            try:
                message = P2PMessage("get", {"key": key}, self.node_id)
                response = await self._send_message(peer.host, peer.port, message)

                if response and response.get("msg_type") == "value":
                    return response["payload"]["value"]

            except Exception:
                pass

        return None

    async def broadcast(self, msg_type: str, payload: Dict):
        """Broadcast un message à tous les peers"""
        all_peers = [peer for bucket in self.routing_table.buckets for peer in bucket]

        for peer in all_peers:
            try:
                message = P2PMessage(msg_type, payload, self.node_id)
                await self._send_message(peer.host, peer.port, message)
            except Exception:
                pass

    def get_status(self) -> Dict:
        """Statut du nœud"""
        return {
            "node_id": str(self.node_id),
            "host": self.host,
            "port": self.port,
            "routing_table": self.routing_table.get_stats(),
            "dht_store": {
                "keys": len(self.dht_store.data)
            },
            "gossip": {
                "info_types": len(self.gossip.information)
            }
        }

    def stop(self):
        """Arrête le nœud"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def main():
    """Main function - Demo"""
    print("=" * 70)
    print("🔄 TRUE P2P NETWORK - DÉCENTRALISÉ")
    print("=" * 70)
    print("\n✅ DHT (Distributed Hash Table)")
    print("✅ Gossip Protocol")
    print("✅ Kademlia Routing")
    print("✅ Bootstrap Nodes")
    print("✅ Store & Get")
    print("✅ Broadcast")

    # Configurer les nodes de bootstrap (pour la demo, on crée 3 nodes locaux)
    config = P2PConfig()
    config.bootstrap_nodes = [
        ("127.0.0.1", 9991),
        ("127.0.0.1", 9992),
    ]

    # Créer le nœud
    node = P2PNode("127.0.0.1", 9990, config)

    # Démarrer le nœud
    await node.start()

    # Attendre un peu
    await asyncio.sleep(5)

    # Store une valeur
    await node.store("test_key", {"data": "Hello P2P!"})

    # Get la valeur
    value = await node.get("test_key")
    print(f"\n📦 Stored value: {value}")

    # Broadcast
    await node.broadcast("hello", {"message": "Hello from P2P Node!"})

    # Status
    status = node.get_status()
    print(f"\n📊 Status:")
    print(f"   Node ID: {status['node_id']}")
    print(f"   Routing Table: {status['routing_table']}")
    print(f"   DHT Store: {status['dht_store']}")

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
            status = node.get_status()
            print(f"\n📊 [Every 60s] Peers: {status['routing_table']['total_peers']}")
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping P2P Node...")
        node.stop()
        print("✅ P2P Node stopped")

if __name__ == '__main__':
    asyncio.run(main())