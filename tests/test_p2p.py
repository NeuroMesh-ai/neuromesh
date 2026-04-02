#!/usr/bin/env python3
"""
Tests Unitaires - True P2P Network
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.true_p2p_network import (
    P2PConfig,
    NodeID,
    PeerInfo,
    RoutingTable,
    DHTStore,
    GossipProtocol,
    P2PMessage,
    P2PNode
)


# =============================================================================
# TESTS P2P CONFIG
# =============================================================================

class TestP2PConfig:
    """Tests de P2PConfig"""

    def test_config_creation(self):
        """Test la création"""
        config = P2PConfig()

        assert config.k == 16
        assert config.alpha == 3
        assert config.id_length == 160
        assert config.redundancy == 3


# =============================================================================
# TESTS NODE ID
# =============================================================================

class TestNodeID:
    """Tests de NodeID"""

    def test_node_id_generation(self):
        """Test la génération"""
        node_id = NodeID()

        assert len(node_id.id) == 40  # SHA-1 hash

    def test_node_id_from_address(self):
        """Test depuis une adresse"""
        node_id = NodeID.from_address("127.0.0.1", 9999)

        assert node_id.id is not None

    def test_node_id_distance(self):
        """Test la distance XOR"""
        id1 = NodeID("a1b2c3d4" + "0" * 32)
        id2 = NodeID("a1b2c3d5" + "0" * 32)

        distance = id1.distance(id2)

        assert distance > 0


# =============================================================================
# TESTS PEER INFO
# =============================================================================

class TestPeerInfo:
    """Tests de PeerInfo"""

    def test_peer_info_creation(self):
        """Test la création"""
        peer = PeerInfo(
            node_id=NodeID("a1b2c3d4" + "0" * 32),
            host="127.0.0.1",
            port=9999
        )

        assert peer.host == "127.0.0.1"
        assert peer.port == 9999

    def test_peer_info_to_dict(self):
        """Test la conversion"""
        peer = PeerInfo(
            node_id=NodeID("a1b2c3d4" + "0" * 32),
            host="127.0.0.1",
            port=9999
        )

        data = peer.to_dict()

        assert data["host"] == "127.0.0.1"
        assert data["port"] == 9999


# =============================================================================
# TESTS ROUTING TABLE
# =============================================================================

class TestRoutingTable:
    """Tests de RoutingTable"""

    def test_routing_table_creation(self):
        """Test la création"""
        config = P2PConfig()
        local_id = NodeID()

        table = RoutingTable(local_id, config)

        assert len(table.buckets) == config.id_length

    def test_routing_table_add_peer(self):
        """Test l'ajout"""
        config = P2PConfig()
        local_id = NodeID()

        table = RoutingTable(local_id, config)

        peer = PeerInfo(
            node_id=NodeID.from_address("127.0.0.1", 9999),
            host="127.0.0.1",
            port=9999
        )

        table.add_peer(peer)

        assert len(table.buckets[0]) == 1

    def test_routing_table_find_closest(self):
        """Test find closest"""
        config = P2PConfig()
        local_id = NodeID()

        table = RoutingTable(local_id, config)

        # Ajouter des peers
        for i in range(5):
            peer = PeerInfo(
                node_id=NodeID.from_address("127.0.0.1", 9999 + i),
                host="127.0.0.1",
                port=9999 + i
            )
            table.add_peer(peer)

        target = NodeID()
        closest = table.find_closest(target, count=3)

        assert len(closest) == 3


# =============================================================================
# TESTS DHT STORE
# =============================================================================

class TestDHTStore:
    """Tests de DHTStore"""

    def test_dht_store_creation(self):
        """Test la création"""
        config = P2PConfig()
        store = DHTStore(config)

        assert store.data == {}

    def test_dht_store_and_get(self):
        """Test store et get"""
        config = P2PConfig()
        store = DHTStore(config)

        store.store("test_key", {"value": "test"}, [NodeID()])

        value = store.get("test_key")

        assert value == {"value": "test"}

    def test_dht_find_responsible(self):
        """Test find responsible"""
        config = P2PConfig()
        store = DHTStore(config)
        local_id = NodeID()

        peers = [
            PeerInfo(
                node_id=NodeID.from_address("127.0.0.1", 9999 + i),
                host="127.0.0.1",
                port=9999 + i
            )
            for i in range(5)
        ]

        responsible = store.find_responsible("test_key", local_id, peers)

        assert len(responsible) == config.redundancy


# =============================================================================
# TESTS GOSSIP PROTOCOL
# =============================================================================

class TestGossipProtocol:
    """Tests de GossipProtocol"""

    def test_gossip_creation(self):
        """Test la création"""
        config = P2PConfig()
        gossip = GossipProtocol(config)

        assert gossip.information == {}

    def test_gossip_add_info(self):
        """Test l'ajout"""
        config = P2PConfig()
        gossip = GossipProtocol(config)

        gossip.add_info("test_type", "test_id", {"data": "test"})

        assert len(gossip.information["test_type"]) == 1

    def test_gossip_get_info(self):
        """Test get"""
        config = P2PConfig()
        gossip = GossipProtocol(config)

        gossip.add_info("test_type", "test_id", {"data": "test"})

        info = gossip.get_info("test_type", "test_id")

        assert info is not None
        assert info["info"]["data"] == "test"

    def test_gossip_merge(self):
        """Test merge"""
        config = P2PConfig()
        gossip = GossipProtocol(config)

        # Add local info
        gossip.add_info("presence", "peer1", {"data": "test1"})

        # Merge incoming
        incoming = {"peer2": {"info": {"data": "test2"}, "timestamp": 0, "hops": 0}}
        gossip.merge_info("presence", incoming)

        assert len(gossip.information["presence"]) == 2


# =============================================================================
# TESTS P2P MESSAGE
# =============================================================================

class TestP2PMessage:
    """Tests de P2PMessage"""

    def test_message_creation(self):
        """Test la création"""
        msg = P2PMessage(
            msg_type="ping",
            payload={},
            sender_id=NodeID()
        )

        assert msg.msg_type == "ping"
        assert msg.message_id is not None

    def test_message_to_dict(self):
        """Test conversion"""
        msg = P2PMessage(
            msg_type="ping",
            payload={"test": "data"},
            sender_id=NodeID()
        )

        data = msg.to_dict()

        assert data["msg_type"] == "ping"
        assert data["payload"]["test"] == "data"

    def test_message_from_dict(self):
        """Test depuis dict"""
        data = {
            "msg_type": "ping",
            "payload": {"test": "data"},
            "sender_id": "a1b2c3d4" + "0" * 32,
            "message_id": "msg123",
            "timestamp": 1234567890
        }

        msg = P2PMessage.from_dict(data)

        assert msg.msg_type == "ping"
        assert msg.message_id == "msg123"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, "-v"])