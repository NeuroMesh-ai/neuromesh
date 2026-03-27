#!/usr/bin/env python3
"""
Bug Reputation System — Hash-based trust (edonkey-utils style).

Principle:
- Good responses get verified and shared via hash
- Reputation is community-driven, not centralized
- Peers with good hash-verified responses become trusted
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict, deque

from cryptography.exceptions import InvalidSignature


@dataclass
class QualityScore:
    response_hash: str
    peer_id: str
    score: float  # 0-10
    timestamp: float
    verified_count: int  # How many peers verified this hash
    user_reports: int  # Negative feedback count


@dataclass
class ResponsePacket:
    response_hash: str
    query: str
    response: str
    peer_id: str
    signature: str  # Ed25519 signature
    timestamp: float
    metadata: dict


class BugReputationSystem:
    """
    Hash-based reputation system, inspired by edonkey-utils.

    Trust is earned by providing quality responses verified by the network.
    """

    def __init__(self, max_history: int = 1000, decay_hours: float = 720):
        # peer_id → reputation score (0-100)
        self.peer_reputation: Dict[str, float] = defaultdict(lambda: 50.0)

        # response_hash → QualityScore
        self.response_quality: Dict[str, QualityScore] = {}

        # peer_id → historical query hash
        self.peer_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))

        # Config
        self.max_history = max_history
        self.decay_hours = decay_hours  # 30 days
        self.min_reputation = 0.0
        self.max_reputation = 100.0

    def hash_response(self, response: str) -> str:
        """Generate SHA256 hash of response."""
        return hashlib.sha256(response.encode()).hexdigest()

    def create_signed_packet(
        self,
        query: str,
        response: str,
        peer_id: str,
        private_key
    ) -> ResponsePacket:
        """
        Create a signed response packet.

        This is the "edonkey-style file hash" equivalent for AI responses.
        """
        response_hash = self.hash_response(response)

        # Data to sign
        data_to_sign = {
            "hash": response_hash,
            "query": query,
            "timestamp": time.time()
        }
        data_bytes = json.dumps(data_to_sign, sort_keys=True).encode()

        # Sign with Ed25519
        signature = private_key.sign(data_bytes).hex()

        return ResponsePacket(
            response_hash=response_hash,
            query=query,
            response=response,
            peer_id=peer_id,
            signature=signature,
            timestamp=time.time(),
            metadata={"model": "unknown"}  # Would be filled in real impl
        )

    def verify_signed_packet(self, packet: ResponsePacket, peer_public_key) -> Optional[bool]:
        """
        Verify a signed response packet.

        Returns True if signature is valid, None if peer unknown.
        """
        try:
            data_to_verify = {
                "hash": packet.response_hash,
                "query": packet.query,
                "timestamp": packet.timestamp
            }
            data_bytes = json.dumps(data_to_verify, sort_keys=True).encode()

            signature = bytes.fromhex(packet.signature)
            peer_public_key.verify(signature, data_bytes)
            return True

        except InvalidSignature:
            return False
        except Exception as e:
            print(f"Verification error: {e}")
            return None

    def score_response(
        self,
        response_hash: str,
        peer_id: str,
        user_score: float,
        verified_by_others: int = 0
    ):
        """
        Score a response based on user feedback and community verification.

        This is the "community trust" mechanism from edonkey.
        """
        existing = self.response_quality.get(response_hash)

        if existing:
            # Update existing score (exponential moving average)
            new_verified = existing.verified_count + verified_by_others
            new_score = existing.score * 0.7 + user_score * 0.3
        else:
            new_verified = verified_by_others
            new_score = user_score

        quality = QualityScore(
            response_hash=response_hash,
            peer_id=peer_id,
            score=new_score,
            timestamp=time.time(),
            verified_count=new_verified,
            user_reports=0
        )

        self.response_quality[response_hash] = quality
        self.peer_history[peer_id].append(response_hash)

        # Update peer reputation
        self._update_peer_reputation(peer_id, new_score)

    def _update_peer_reputation(self, peer_id: str, response_score: float):
        """Update peer's reputation based on response quality."""
        current = self.peer_reputation[peer_id]

        # Reputation moves toward response score
        delta = (response_score * 10) - current  # Convert score 0-10 to 0-100

        # Adjustment rate (how fast reputation changes)
        adjustment_rate = 0.1

        new_rep = current + (delta * adjustment_rate)
        self.peer_reputation[peer_id] = max(
            self.min_reputation,
            min(self.max_reputation, new_rep)
        )

    def get_peer_reputation(self, peer_id: str) -> float:
        """Get reputation score for a peer."""
        return self.peer_reputation[peer_id]

    def get_response_quality(self, response_hash: str) -> Optional[float]:
        """Get quality score for a response hash."""
        quality = self.response_quality.get(response_hash)
        return quality.score if quality else None

    def report_bad_response(
        self,
        response_hash: str,
        peer_id: str,
        reason: str
    ):
        """
        Report a bad response (decreases reputation).

        Community moderation mechanism.
        """
        quality = self.response_quality.get(response_hash)

        if quality:
            quality.user_reports += 1

            # Penalize peer more if multiple reports
            penalty = 2.0 * quality.user_reports
            self.peer_reputation[peer_id] = max(
                self.min_reputation,
                self.peer_reputation[peer_id] - penalty
            )

        else:
            # Unknown response reported -> peer penalty
            self.peer_reputation[peer_id] = max(
                self.min_reputation,
                self.peer_reputation[peer_id] - 5.0
            )

    def select_peers(
        self,
        candidate_peers: List[str],
        k: int = 3,
        min_reputation: float = 30.0
    ) -> List[str]:
        """
        Select k peers by reputation.

        Similar to selecting "good peers" in edonkey.
        """
        # Filter by min reputation
        valid = [
            p for p in candidate_peers
            if self.peer_reputation[p] >= min_reputation
        ]

        if len(valid) <= k:
            return valid

        # Sort by reputation (highest first)
        scored = [(p, self.peer_reputation[p]) for p in valid]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [p for p, _ in scored[:k]]

    def decay_old_scores(self):
        """
        Decay old response scores (time-based).

        Reputation should reflect recent performance.
        """
        now = time.time()
        cutoff = now - (self.decay_hours * 3600)

        to_remove = []
        for h, quality in self.response_quality.items():
            if quality.timestamp < cutoff:
                to_remove.append(h)

        for h in to_remove:
            peer_id = self.response_quality[h].peer_id
            del self.response_quality[h]
            # Peer reputation stays, but old influence gone

    def get_stats(self) -> dict:
        """Get system statistics."""
        total_scores = len(self.response_quality)
        avg_score = (
            sum(q.score for q in self.response_quality.values()) / total_scores
            if total_scores > 0 else 0.0
        )

        peer_rep_list = list(self.peer_reputation.values())
        avg_reputation = (
            sum(peer_rep_list) / len(peer_rep_list)
            if peer_rep_list else 50.0
        )

        # Top trusted peers
        top_peers = sorted(
            self.peer_reputation.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Distrusted peers
        low_peers = [
            p for p, r in self.peer_reputation.items()
            if r < 30.0
        ]

        return {
            "total_response_scores": total_scores,
            "average_quality_score": avg_score,
            "total_peers": len(self.peer_reputation),
            "average_reputation": avg_reputation,
            "top_trusted_peers": [{"peer_id": p, "reputation": r} for p, r in top_peers],
            "distrusted_peers_count": len(low_peers),
            "distrusted_peers": low_peers[:10]
        }

    def export_trusted_responses(self, count: int = 100) -> List[dict]:
        """
        Export trusted responses for sharing.

        Similar to edonkey's hash lists for verification.
        """
        trusted = sorted(
            self.response_quality.items(),
            key=lambda x: (x[1].score, x[1].verified_count),
            reverse=True
        )[:count]

        return [
            {
                "hash": h,
                "score": q.score,
                "verified_count": q.verified_count,
                "peer_id": q.peer_id
            }
            for h, q in trusted
        ]


# ============ CLI for Testing ============

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bug Reputation System")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--peers", action="store_true", help="Show top peers")
    parser.add_argument("--score-hash", help="Score a response hash")
    parser.add_argument("--score", type=float, help="Score value (0-10)")
    parser.add_argument("--peer", help="Peer ID")
    args = parser.parse_args()

    rep = BugReputationSystem()

    if args.stats:
        stats = rep.get_stats()
        print(json.dumps(stats, indent=2))

    elif args.peers:
        stats = rep.get_stats()
        print("Top Trusted Peers:")
        print("=" * 50)
        for p in stats["top_trusted_peers"]:
            print(f"{p['peer_id'][:16]}... : {p['reputation']:.1f}/100")

    elif args.score_hash and args.score and args.peer:
        rep.score_response(args.score_hash, args.peer, args.score)
        print(f"✅ Scored {args.score_hash[:16]}... : {args.score}/10")
        print(f"   Peer {args.peer[:16]}... reputation: {rep.get_peer_reputation(args.peer):.1f}/100")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()