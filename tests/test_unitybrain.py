#!/usr/bin/env python3
"""
Tests Unitaires - UnityBrain v3.0
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.unitybrain_v3_final import (
    UnityBrain,
    Peer,
    Model,
    Query,
    QueryResult,
    QueryHistory,
    ReputationSystem,
    ConsensusManager
)


# =============================================================================
# TESTS PEER
# =============================================================================

class TestPeer:
    """Tests de la classe Peer"""

    def test_peer_creation(self):
        """Test la création d'un peer"""
        peer = Peer(
            name="TestPeer",
            host="127.0.0.1",
            port=9999,
            models=["model1", "model2"]
        )

        assert peer.name == "TestPeer"
        assert peer.host == "127.0.0.1"
        assert peer.port == 9999
        assert peer.models == ["model1", "model2"]
        assert peer.available is True
        assert peer.reputation == 1.0

    def test_peer_to_dict(self):
        """Test la conversion en dictionnaire"""
        peer = Peer(
            name="TestPeer",
            host="127.0.0.1",
            port=9999,
            models=["model1"]
        )

        data = peer.to_dict()

        assert data["name"] == "TestPeer"
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 9999

    def test_peer_from_dict(self):
        """Test la création depuis un dictionnaire"""
        data = {
            "name": "TestPeer",
            "host": "127.0.0.1",
            "port": 9999,
            "models": ["model1"],
            "reputation": 0.95
        }

        peer = Peer.from_dict(data)

        assert peer.name == "TestPeer"
        assert peer.host == "127.0.0.1"
        assert peer.port == 9999
        assert peer.reputation == 0.95


# =============================================================================
# TESTS MODEL
# =============================================================================

class TestModel:
    """Tests de la classe Model"""

    def test_model_creation(self):
        """Test la création d'un modèle"""
        model = Model(
            name="test-model",
            ollama_name="test-model:latest"
        )

        assert model.name == "test-model"
        assert model.ollama_name == "test-model:latest"
        assert model.available is True
        assert model.latency == 0.0


# =============================================================================
# TESTS QUERY HISTORY
# =============================================================================

class TestQueryHistory:
    """Tests de QueryHistory"""

    def test_query_history_creation(self):
        """Test la création de l'historique"""
        history = QueryHistory(max_size=100)

        assert history.max_size == 100
        assert len(history.queries) == 0

    def test_query_history_add(self):
        """Test l'ajout d'une query"""
        history = QueryHistory()

        query = Query(
            prompt="Test prompt",
            models=["model1"],
            use_ensemble=False
        )
        result = QueryResult(
            status="success",
            response="Test response",
            peer="TestPeer",
            model="model1",
            latency=100
        )

        history.add(query, result)

        assert len(history.queries) == 1
        assert history.queries[0].prompt == "Test prompt"

    def test_query_history_export(self):
        """Test l'export"""
        history = QueryHistory()

        query = Query(
            prompt="Test",
            models=["model1"],
            use_ensemble=False
        )
        result = QueryResult(
            status="success",
            response="Test response",
            peer="TestPeer",
            model="model1",
            latency=100
        )

        history.add(query, result)

        # Export JSON
        json_data = history.export("json")
        assert len(json_data) == 1

        # Export CSV
        csv_data = history.export("csv")
        assert "Test" in csv_data


# =============================================================================
# TESTS REPUTATION SYSTEM
# =============================================================================

class TestReputationSystem:
    """Tests de ReputationSystem"""

    def test_reputation_creation(self):
        """Test la création"""
        system = ReputationSystem()

        assert system.default_reputation == 1.0
        assert system.min_reputation == 0.0
        assert system.max_reputation == 1.0

    def test_reputation_add_vote(self):
        """Test l'ajout d'un vote"""
        system = ReputationSystem()

        system.add_vote("TestPeer", 0.9)

        assert system.get_reputation("TestPeer") == 0.9

    def test_reputation_average(self):
        """Test la moyenne des votes"""
        system = ReputationSystem()

        system.add_vote("TestPeer", 0.8)
        system.add_vote("TestPeer", 0.9)

        assert system.get_reputation("TestPeer") == 0.85

    def test_reputation_ban(self):
        """Test le ban"""
        system = ReputationSystem()

        system.add_vote("BadPeer", 0.2)
        system.add_vote("BadPeer", 0.1)

        assert system.is_banned("BadPeer")


# =============================================================================
# TESTS CONSENSUS MANAGER
# =============================================================================

class TestConsensusManager:
    """Tests de ConsensusManager"""

    def test_consensus_creation(self):
        """Test la création"""
        manager = ConsensusManager(
            consensus_threshold=0.7,
            max_voters=10
        )

        assert manager.consensus_threshold == 0.7
        assert manager.max_voters == 10

    def test_consensus_simple_majority(self):
        """Test consensus majorité simple"""
        manager = ConsensusManager(consensus_threshold=0.6)

        results = [
            {"peer": "peer1", "model": "model1", "response": "Réponse 1", "quality": 0.8},
            {"peer": "peer2", "model": "model2", "response": "Réponse 2", "quality": 0.9},
            {"peer": "peer3", "model": "model3", "response": "Réponse 2", "quality": 0.85},
        ]

        consensus = manager.consensus_simple_majority(results)

        assert consensus["response"] == "Réponse 2"
        assert consensus["voters"] == 2


# =============================================================================
# TESTS UNITYBRAIN (INTEGRATION)
# =============================================================================

@pytest.mark.asyncio
class TestUnityBrainIntegration:
    """Tests d'intégration UnityBrain"""

    async def test_unitybrain_creation(self):
        """Test la création"""
        unitybrain = UnityBrain()

        assert unitybrain.name == "UnityBrain"
        assert unitybrain.peers == []
        assert len(unitybrain.models) > 0

    async def test_unitybrain_add_peer(self):
        """Test l'ajout d'un peer"""
        unitybrain = UnityBrain()

        peer = Peer(
            name="TestPeer",
            host="127.0.0.1",
            port=9999,
            models=["model1"]
        )

        await unitybrain.add_peer(peer)

        assert len(unitybrain.peers) == 1

    async def test_unitybrain_select_best_peer(self):
        """Test la sélection du meilleur peer"""
        unitybrain = UnityBrain()

        peer1 = Peer(
            name="FastPeer",
            host="127.0.0.1",
            port=9999,
            models=["model1"],
            latency=10,
            reputation=1.0
        )
        peer2 = Peer(
            name="SlowPeer",
            host="127.0.0.1",
            port=9998,
            models=["model1"],
            latency=100,
            reputation=0.8
        )

        await unitybrain.add_peer(peer1)
        await unitybrain.add_peer(peer2)

        best = unitybrain._select_best_peer(["model1"])

        assert best.name == "FastPeer"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, "-v"])