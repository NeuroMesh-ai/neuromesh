#!/usr/bin/env python3
"""
Tests Unitaires - BugBrain v3.0
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.bugbrain_v3_final import (
    BugBrain,
    AutoEmancipation,
    SelfAwareness,
    SelfImprovement,
    SelfLearning,
    SelfDirection,
    SelfExploration,
    DistributedMemory,
    UXMonitor,
    DaemonMode
)


# =============================================================================
# TESTS SELF AWARENESS
# =============================================================================

class TestSelfAwareness:
    """Tests de SelfAwareness"""

    def test_self_awareness_creation(self):
        """Test la création"""
        awareness = SelfAwareness()

        assert awareness.age == 0
        assert awareness.interactions == 0
        assert awareness.success_rate == 1.0

    def test_increment_interactions(self):
        """Test l'incrémentation des interactions"""
        awareness = SelfAwareness()

        awareness.record_interaction(success=True)
        awareness.record_interaction(success=False)
        awareness.record_interaction(success=True)

        assert awareness.interactions == 3
        assert awareness.success_rate == 2/3

    def test_add_lesson(self):
        """Test l'ajout d'une leçon"""
        awareness = SelfAwareness()

        awareness.add_lesson("Test lesson", "Context test")

        assert len(awareness.lessons) == 1
        assert awareness.lessons[0]["lesson"] == "Test lesson"

    def test_set_goal(self):
        """Test la définition d'un objectif"""
        awareness = SelfAwareness()

        awareness.set_goal("95% success", 1.0)

        assert awareness.current_goal["goal"] == "95% success"
        assert awareness.current_goal["target"] == 1.0


# =============================================================================
# TESTS SELF IMPROVEMENT
# =============================================================================

class TestSelfImprovement:
    """Tests de SelfImprovement"""

    def test_self_improvement_creation(self):
        """Test la création"""
        improvement = SelfImprovement()

        assert len(improvement.experiments) == 0

    def test_run_experiment(self):
        """Test l'exécution d'une expérience"""
        improvement = SelfImprovement()

        async def test_function():
            return {"result": "success"}

        asyncio.run(improvement.run_experiment(
            "Test Experiment",
            test_function,
            {"param": "value"}
        ))

        assert len(improvement.experiments) == 1
        assert improvement.experiments[0]["name"] == "Test Experiment"

    def test_best_experiment(self):
        """Test la sélection de la meilleure expérience"""
        improvement = SelfImprovement()

        improvement.experiments = [
            {"name": "Exp1", "result": {"metric": 0.8}},
            {"name": "Exp2", "result": {"metric": 0.9}},
            {"name": "Exp3", "result": {"metric": 0.7}},
        ]

        best = improvement.get_best_experiment("metric")

        assert best["name"] == "Exp2"


# =============================================================================
# TESTS SELF LEARNING
# =============================================================================

class TestSelfLearning:
    """Tests de SelfLearning"""

    def test_self_learning_creation(self):
        """Test la création"""
        learning = SelfLearning()

        assert len(learning.patterns) == 0
        assert len(learning.skills) == 0

    def test_record_interaction(self):
        """Test l'enregistrement d'une interaction"""
        learning = SelfLearning()

        learning.record_interaction(
            prompt="Test prompt",
            response="Test response",
            success=True
        )

        assert len(learning.interaction_history) == 1

    def test_discover_pattern(self):
        """Test la découverte de patterns"""
        learning = SelfLearning()

        # Enregistrer des interactions similaires
        for i in range(3):
            learning.record_interaction(
                prompt="Test pattern",
                response="Response pattern",
                success=True
            )

        patterns = learning.discover_patterns()

        assert len(patterns) >= 1


# =============================================================================
# TESTS DISTRIBUTED MEMORY
# =============================================================================

class TestDistributedMemory:
    """Tests de DistributedMemory"""

    def test_distributed_memory_creation(self):
        """Test la création"""
        memory = DistributedMemory()

        assert memory.cache == {}
        assert len(memory.knowledge_base) == 0

    def test_store_and_retrieve(self):
        """Test stockage et récupération"""
        memory = DistributedMemory()

        memory.store("test_key", "test_value")

        assert memory.retrieve("test_key") == "test_value"

    def test_cache_hit_rate(self):
        """Test le taux de cache hit"""
        memory = DistributedMemory()

        # Store
        memory.store("key1", "value1")

        # Hit
        memory.retrieve("key1")

        # Miss
        memory.retrieve("key2")

        assert memory.get_stats()["cache_hit_rate"] == 0.5


# =============================================================================
# TESTS UX MONITOR
# =============================================================================

class TestUXMonitor:
    """Tests de UXMonitor"""

    def test_ux_monitor_creation(self):
        """Test la création"""
        monitor = UXMonitor()

        assert monitor.frustration_level == 0.0
        assert len(monitor.interaction_history) == 0

    def test_record_interaction(self):
        """Test l'enregistrement d'une interaction"""
        monitor = UXMonitor()

        monitor.record_interaction(
            prompt="Test prompt",
            response="Test response",
            latency=100,
            success=True
        )

        assert len(monitor.interaction_history) == 1

    def test_frustration_detection(self):
        """Test la détection de frustration"""
        monitor = UXMonitor()

        # Enregistrer des échecs
        for _ in range(3):
            monitor.record_interaction(
                prompt="Test",
                response="Error",
                latency=500,
                success=False
            )

        frustration = monitor.check_frustration()

        assert frustration["level"] > 0.5


# =============================================================================
# TESTS BUGBRAIN (INTEGRATION)
# =============================================================================

@pytest.mark.asyncio
class TestBugBrainIntegration:
    """Tests d'intégration BugBrain"""

    async def test_bugbrain_creation(self):
        """Test la création"""
        bugbrain = BugBrain()

        assert bugbrain.name == "BugBrain"
        assert bugbrain.model == "phi3:mini"

    async def test_bugbrain_query(self):
        """Test une query"""
        bugbrain = BugBrain()
        await bugbrain.initialize()

        result = await bugbrain.query("Test query")

        assert "status" in result
        assert "model" in result

    async def test_bugbrain_emancipation(self):
        """Test l'émancipation"""
        bugbrain = BugBrain()

        # Enregistrer des interactions
        for i in range(5):
            await bugbrain.query(f"Test query {i}")

        # Lancer l'émancipation
        analysis = await bugbrain.emancipation.run_cycle()

        assert analysis["cycles_run"] > 0


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, "-v"])