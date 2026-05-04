#!/usr/bin/env python3
"""
Sharing Parity System — Reward contribution with query quotas.

More you share, more you can query.
"""

import asyncio
import logging
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import toml
import json

logger = logging.getLogger("SharingParity")


@dataclass
class SharingConfig:
    """Configuration for Sharing Parity System."""

    enabled: bool = True

    # Weights for factors (0-1, must sum to 1.0)
    weights_models: float = 0.40
    weights_chunks: float = 0.30
    weights_uptime: float = 0.20
    weights_reputation: float = 0.10

    # Query quotas (per minute)
    quota_min: int = 1
    quota_max: int = 200

    # Decay settings
    chunks_decay_hours: int = 168  # 7 days
    uptime_min_hours: int = 1

    # Score thresholds for quota levels
    score_threshold_1: int = 10
    score_threshold_2: int = 20
    score_threshold_3: int = 40
    score_threshold_4: int = 60
    score_threshold_5: int = 80

    @classmethod
    def from_file(cls, config_path: str) -> 'SharingConfig':
        """Load from p2p_config.toml."""
        try:
            with open(config_path, 'r') as f:
                config = toml.load(f)

            parity = config.get('sharing_parity', {})

            return cls(
                enabled=parity.get('enabled', True),
                weights_models=parity.get('weights_models', 0.40),
                weights_chunks=parity.get('weights_chunks', 0.30),
                weights_uptime=parity.get('weights_uptime', 0.20),
                weights_reputation=parity.get('weights_reputation', 0.10),
                quota_min=parity.get('quota_min', 1),
                quota_max=parity.get('quota_max', 200),
                chunks_decay_hours=parity.get('chunks_decay_hours', 168),
                uptime_min_hours=parity.get('uptime_min_hours', 1)
            )
        except Exception as e:
            logger.warning(f"Could not load sharing parity config: {e}, using defaults")
            return cls()


@dataclass
class PeerSharingStats:
    """Track sharing statistics for a peer."""

    models_hosted: int = 0
    chunks_distributed: int = 0
    uptime_hours: float = 0.0
    reputation: float = 100.0  # From reputation system
    chunks_expired: int = 0
    last_updated: Optional[datetime] = None

    # Track chunks distribution with timestamp
    chunks_timestamps: Dict[str, datetime] = field(default_factory=dict)

    record(self) -> dict:
        """Return as dictionary for storage."""
        return {
            'models_hosted': self.models_hosted,
            'chunks_distributed': self.chunks_distributed - self.chunks_expired,
            'uptime_hours': round(self.uptime_hours, 2),
            'reputation': self.reputation
        }


class SharingParityManager:
    """Manage sharing parity system."""

    def __init__(self, config: SharingConfig, storage_dir: str):
        self.config = config
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of peer stats
        self.peer_stats: Dict[str, PeerSharingStats] = {}

        # Query quotas (peer_id → queries_per_minute)
        self.quota_cache: Dict[str, int] = {}

        # Query counters (to enforce quotas)
        self.quota_counters: Dict[str, int] = {}
        self.quota_reset_time: Dict[str, datetime] = {}

    def record_chunk_distribution(self, peer_id: str, chunk_hash: str):
        """Record that a peer distributed a chunk."""
        if peer_id not in self.peer_stats:
            self.peer_stats[peer_id] = PeerSharingStats()

        peer_stats = self.peer_stats[peer_id]
        peer_stats.chunks_distributed += 1
        peer_stats.chunks_timestamps[chunk_hash] = datetime.now()
        peer_stats.last_updated = datetime.now()

        # Expire old chunks
        self._expire_old_chunks(peer_id)

        logger.debug(f"Peer {peer_id} distributed chunk, total: {peer_stats.chunks_distributed}")

    def record_model_hosted(self, peer_id: str, model_id: str):
        """Record that a peer is hosting a model."""
        if peer_id not in self.peer_stats:
            self.peer_stats[peer_id] = PeerSharingStats()

        # In full impl, would track unique models
        self.peer_stats[peer_id].models_hosted += 1
        self.peer_stats[peer_id].last_updated = datetime.now()

        logger.info(f"Peer {peer_id} is now hosting model {model_id}")

    def update_uptime(self, peer_id: str, hours: float):
        """Update peer uptime."""
        if peer_id not in self.peer_stats:
            self.peer_stats[peer_id] = PeerSharingStats()

        if hours >= self.config.uptime_min_hours:
            self.peer_stats[peer_id].uptime_hours = hours
            self.peer_stats[peer_id].last_updated = datetime.now()

    def update_reputation(self, peer_id: str, reputation: float):
        """Update peer reputation."""
        if peer_id not in self.peer_stats:
            self.peer_stats[peer_id] = PeerSharingStats()

        self.peer_stats[peer_id].reputation = reputation
        self.peer_stats[peer_id].last_updated = datetime.now()

    def _expire_old_chunks(self, peer_id: str):
        """Remove chunks older than decay period."""
        if peer_id not in self.peer_stats:
            return

        peer_stats = self.peer_stats[peer_id]
        cutoff = datetime.now() - timedelta(hours=self.config.chunks_decay_hours)

        expired_chunks = 0
        chunks_to_remove = []

        for chunk_hash, timestamp in list(peer_stats.chunks_timestamps.items()):
            if timestamp < cutoff:
                chunks_to_remove.append(chunk_hash)
                expired_chunks += 1

        # Remove expired chunks
        for chunk_hash in chunks_to_remove:
            del peer_stats.chunks_timestamps[chunk_hash]

        if expired_chunks > 0:
            peer_stats.chunks_expired += expired_chunks
            logger.debug(f"Peer {peer_id}: {expired_chunks} chunks decayed")

    def calculate_score(self, peer_id: str) -> float:
        """Calculate sharing score for a peer."""
        if peer_id not in self.peer_stats:
            return 0.0

        stats = self.peer_stats[peer_id]

        # Calculate each factor score (0-100)
        models_score = min(stats.models_hosted * 20, 100)  # Max 100 with 5 models
        chunks_score = min(stats.chunks_distributed / 10, 100)  # Max 100 with 1000 chunks
        uptime_score = min(stats.uptime_hours / 24, 100)  # Max 100 with 24 hours
        reputation_score = min(stats.reputation, 100)

        # Weighted total
        total_score = (
            models_score * self.config.weights_models +
            chunks_score * self.config.weights_chunks +
            uptime_score * self.config.weights_uptime +
            reputation_score * self.config.weights_reputation
        )

        return round(total_score, 2)

    def get_query_quota(self, peer_id: str) -> int:
        """Get query quota for a peer (queries per minute)."""
        score = self.calculate_score(peer_id)

        if score < self.config.score_threshold_1:
            return self.config.quota_min
        elif score < self.config.score_threshold_2:
            return 5
        elif score < self.config.score_threshold_3:
            return 20
        elif score < self.config.score_threshold_4:
            return 50
        elif score < self.config.score_threshold_5:
            return 100
        else:
            return self.config.quota_max

    def can_query(self, peer_id: str) -> tuple[bool, str]:
        """Check if peer can make a query."""

        if not self.config.enabled:
            return True, "Sharing parity disabled"

        quota = self.get_query_quota(peer_id)

        # Reset counter if new minute
        now = datetime.now()
        if peer_id in self.quota_reset_time:
            reset_time = self.quota_reset_time[peer_id]
            if (now - reset_time).total_seconds() >= 60:
                self.quota_counters[peer_id] = 0
                self.quota_reset_time[peer_id] = now

        # Initialize counter
        if peer_id not in self.quota_counters:
            self.quota_counters[peer_id] = 0
            self.quota_reset_time[peer_id] = now

        # Check quota
        current = self.quota_counters[peer_id]

        if current >= quota:
            return False, f"Quota exceeded: {current}/{quota} queries this minute"

        # Increment counter
        self.quota_counters[peer_id] += 1
        return True, f"OK (quota {current + 1}/{quota})"

    def record_suggestion(self, peer_id: str) -> dict:
        """Suggest ways to increase quota."""
        stats = self.peer_stats.get(peer_id)

        if not stats:
            return {
                'message': 'Host a model to start earning quota',
                'suggestions': [
                    {
                        'action': 'Host a model',
                        'potential': '+20 score',
                        'description': 'Héberger un modèle local'
                    }
                ]
            }

        suggestions = []

        # Models suggestion
        if stats.models_hosted == 0:
            suggestions.append({
                'action': 'Host a model',
                'potential': '+20 score',
                'description': 'Héberger un modèle local'
            })

        # Chunks suggestion
        chunks_needed = 1000 - stats.chunks_distributed
        if chunks_needed > 0:
            suggestions.append({
                'action': f'Distribute {chunks_needed} more chunks',
                'potential': f'+{min(chunks_needed / 100 * 3, 30):.1f} score',
                'description': 'Distribuer des chunks aux autres peers'
            })

        # Uptime suggestion
        uptime_needed = 24 - stats.uptime_hours
        if uptime_needed > 0:
            suggestions.append({
                'action': f'Increase uptime by {uptime_needed:.1f} hours',
                'potential': f'+{min(uptime_needed / 24 * 20, 20):.1f} score',
                'description': 'Rester connecté continu'
            })

        total_potential = self._estimate_potential(stats)
        current_quota = self.get_query_quota(peer_id)

        return {
            'current_score': self.calculate_score(peer_id),
            'current_quota': f"{current_quota}/minute",
            'next_milestone': self._next_milestone(current_quota),
            'suggestions': suggestions
        }

    def _next_milestone(self, current_quota: int) -> Optional[dict]:
        """Get next quota milestone."""
        milestones = [
            {'quota': 5, 'from': 1, 'name': 'Starter'},
            {'quota': 20, 'from': 5, 'name': 'Moderate'},
            {'quota': 50, 'from': 20, 'name': 'Contributor'},
            {'quota': 100, 'from': 50, 'name': 'Seeder'},
            {'quota': 200, 'from': 100, 'name': 'Power Seeder'}
        ]

        for milestone in milestones:
            if current_quota < milestone['quota']:
                return milestone

        return None

    def _estimate_potential(self, stats: PeerSharingStats) -> dict:
        """Estimate maximum potential score."""
        potential_models = min((5 - stats.models_hosted) * 20, 100)
        potential_chunks = min((1000 - stats.chunks_distributed) / 100 * 3, 30)
        potential_uptime = min((24 - stats.uptime_hours) / 24 * 20, 20)

        return {
            'models': potential_models,
            'chunks': potential_chunks,
            'uptime': potential_uptime,
            'total': potential_models + potential_chunks + potential_uptime
        }

    def get_stats(self, peer_id: str) -> dict:
        """Get comprehensive sharing statistics for a peer."""

        stats = self.peer_stats.get(peer_id)

        if not stats:
            return {
                'peer_id': peer_id,
                'message': 'No sharing statistics yet'

,
                'score': 0.0,
                'quota': 1,
                'factors': {
                    'models': 0,
                    'chunks': 0,
                    'uptime': 0,
                    'reputation': 100
                }
            }

        score = self.calculate_score(peer_id)
        quota = self.get_query_quota(peer_id)

        return {
            'peer_id': peer_id,
            'score': score,
            'quota': f"{quota}/minute",
            'current_queries': self.quota_counters.get(peer_id, 0),
            'factors': {
                'models_hosted': stats.models_hosted,
                'models_score': min(stats.models_hosted * 20, 100),
                'chunks_distributed': stats.chunks_distributed - stats.chunks_expired,
                'chunks_score': min(stats.chunks_distributed / 10, 100),
                'uptime_hours': round(stats.uptime_hours, 2),
                'uptime_score': min(stats.uptime_hours / 24, 100),
                'reputation': stats.reputation,
                'reputation_score': min(stats.reputation, 100)
            },
            'config': {
                'weights': {
                    'models': self.config.weights_models,
                    'chunks': self.config.weights_chunks,
                    'uptime': self.config.weights_uptime,
                    'reputation': self.config.weights_reputation
                }
            }
        }

    def save_stats(self):
        """Persist stats to disk."""
        stats_file = self.storage_dir / "sharing_parity_stats.json"

        stats_data = {}
        for peer_id, stats in self.peer_stats.items():
            stats_data[peer_id] = stats.record()

        with open(stats_file, 'w') as f:
            json.dump(stats_data, f, indent=2)

        logger.debug(f"Saved sharing parity stats for {len(stats_data)} peers")

    def load_stats(self):
        """Load stats from disk."""
        stats_file = self.storage_dir / "sharing_parity_stats.json"

        if not stats_file.exists():
            return

        with open(stats_file, 'r') as f:
            stats_data = json.load(f)

        for peer_id, data in stats_data.items():
            peer_stats = PeerSharingStats(
                models_hosted=data['models_hosted'],
                chunks_distributed=data['chunks_distributed'],
                uptime_hours=data['uptime_hours'],
                reputation=data['reputation']
            )
            self.peer_stats[peer_id] = peer_stats

        logger.debug(f"Loaded sharing parity stats for {len(peer_stats)} peers")


# ============ CLI ============

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python sharing_parity.py <peer_id>")
        return 1

    peer_id = sys.argv[1]

    config = SharingConfig()
    manager = SharingParityManager(config, "/tmp/unitybrain_parity")

    # Test with some sample data
    manager.record_model_hosted(peer_id, "qwen3:8b")
    manager.record_chunk_distribution(peer_id, "abc123")
    manager.update_uptime(peer_id, 12)
    manager.update_reputation(peer_id, 100)

    stats = manager.get_stats(peer_id)

    print(f"📊 Sharing Stats for: {peer_id}")
    print(f"   Score: {stats['score']}")
    print(f"   Quota: {stats['quota']}")
    print(f"\nFactors:")
    print(f"   Models: {stats['factors']['models_hosted']} (score: {stats['factors']['models_score']})")
    print(f"   Chunks: {stats['factors']['chunks_distributed']} (score: {stats['factors']['chunks_score']})")
    print(f"   Uptime: {stats['factors']['uptime_hours']}h (score: {stats['factors']['uptime_score']})")
    print(f"   Reputation: {stats['factors']['reputation']} (score: {stats['factors']['reputation_score']})")

    suggestion = manager.record_suggestion(peer_id)
    print(f"\nNext Milestone: {suggestion.get('next_milestone', 'Max quota reached').get('name', '')}")
    print(f"Suggestions to increase quota:")
    for s in suggestion['suggestions']:
        print(f"  - {s['action']}: {s['potential']}")

    return 0


if __name__ == "__main__":
    main()