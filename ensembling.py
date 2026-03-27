#!/usr/bin/env python3
"""
Bug Multi-Model Ensembling System

Combine responses from multiple LLMs and select the best one.

Key principle:
"Don't rely on one model. Vote on quality."
"""

import asyncio
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
import re


@dataclass
class ModelResponse:
    """Response from a model/peer."""
    peer_id: str
    model_name: str
    response: str
    latency_ms: float
    timestamp: float
    metadata: dict = None


@dataclass
class EnsembleResult:
    """Result of ensembling multiple responses."""
    final_response: str
    method_used: str  # e.g., "consensus", "best_quality", "fusion"
    responses_considered: int
    response_sources: List[str]  # peer_ids used
    confidence: float  # 0-1
    alternative_responses: List[Dict]  # Other good options


class BugEnsembling:
    """
    Ensemble multiple model responses.

    Strategies implemented:
    1. Consensus: Most common answer (voting)
    2. Quality Scoring: Best quality score
    3. Fusion: Combine best parts (semantic merge)
    4. Redundancy: Cross-verify confidence
    """

    def __init__(self, use_reputation=True):
        self.use_reputation = use_reputation
        self.quality_weights = {
            "length": 0.1,  # Prefer appropriate length
            "structure": 0.2,  # Has structure (lists, sections)
            "clarity": 0.25,  # Clear language
            "completeness": 0.3,  # Addresses all aspects
            "accuracy": 0.15  # Factual accuracy (hard to measure auto)
        }

    async def ensemble_responses(
        self,
        responses: List[ModelResponse],
        original_query: str,
        method: str = "auto",
        reputation_scores: Dict[str, float] = None
    ) -> EnsembleResult:
        """
        Ensemble multiple responses into one best answer.

        Args:
            responses: List of model responses
            original_query: The user's original question
            method: "auto", "consensus", "quality", "fusion", "redundancy"
            reputation_scores: Peer reputation scores (0-100)

        Returns:
            EnsembleResult with best response and metadata
        """
        if not responses:
            return EnsembleResult(
                final_response="No responses available",
                method_used="none",
                responses_considered=0,
                response_sources=[],
                confidence=0.0,
                alternative_responses=[]
            )

        if method == "auto":
            # Choose best method automatically
            method = self._select_best_method(responses)

        # Apply method
        if method == "consensus":
            result = self._consensus_ensemble(responses, original_query)
        elif method == "quality":
            result = self._quality_ensemble(
                responses,
                original_query,
                reputation_scores
            )
        elif method == "fusion":
            result = self._fusion_ensemble(responses, original_query)
        elif method == "redundancy":
            result = self._redundancy_check(responses, original_query)
        else:
            # Default: quality
            result = self._quality_ensemble(
                responses,
                original_query,
                reputation_scores
            )

        # Add metadata
        result.responses_considered = len(responses)
        result.response_sources = [r.peer_id for r in responses]

        return result

    def _select_best_method(self, responses: List[ModelResponse]) -> str:
        """Automatically select the best ensembling method."""
        n = len(responses)

        if n == 1:
            return "quality"  # Only one response

        if n == 2:
            # Two models: check similarity
            similarity = self._calculate_similarity(
                responses[0].response,
                responses[1].response
            )
            if similarity > 0.8:
                return "consensus"  # Similar enough
            else:
                return "quality"  # Different, pick best

        if n >= 3:
            # Three+ models: try consensus first
            return "consensus"

        return "quality"

    def _consensus_ensemble(
        self,
        responses: List[ModelResponse],
        original_query: str
    ) -> EnsembleResult:
        """
        Majority vote based on response similarity.

        If most models agree, return that consensus.
        If they disagree, fall back to quality scoring.
        """
        # Hash responses for comparison
        response_hashes = [
            (
                r,
                self._hash_response(r.response),
                self._score_quality(r.response, original_query)
            )
            for r in responses
        ]

        # Find hash groups (similar responses)
        hash_groups = {}
        for resp, h, score in response_hashes:
            if h not in hash_groups:
                hash_groups[h] = []
            hash_groups[h].append((resp, score))

        # Best group = largest or highest quality
        if len(hash_groups) == 1:
            # All models agree
            best_group = list(hash_groups.values())[0]
            best_resp = max(best_group, key=lambda x: x[1])[0]

            return EnsembleResult(
                final_response=best_resp.response,
                method_used="consensus",
                responses_considered=len(responses),
                response_sources=[r.peer_id for r in responses],
                confidence=0.95,  # High confidence when all agree
                alternative_responses=[]
            )

        # Groups exist: find majority or best quality
        largest_group = max(hash_groups.values(), key=len)
        majority_size = len(largest_group)

        if majority_size > len(responses) / 2:
            # Majority consensus (>50%)
            best_resp = max(largest_group, key=lambda x: x[1])[0]
            confidence = 0.8 + (majority_size / len(responses)) * 0.15

            return EnsembleResult(
                final_response=best_resp.response,
                method_used="consensus_majority",
                responses_considered=len(responses),
                response_sources=[r.peer_id for r in responses],
                confidence=confidence,
                alternative_responses=[]
            )

        # No clear majority: fallback to quality
        return self._quality_ensemble(responses, original_query)

    def _quality_ensemble(
        self,
        responses: List[ModelResponse],
        original_query: str,
        reputation_scores: Dict[str, float] = None
    ) -> EnsembleResult:
        """
        Select best response based on quality scoring (+ reputation).
        """
        # Score each response
        scored = []
        for r in responses:
            quality = self._score_quality(r.response, original_query)

            # Adjust by reputation if provided
            if self.use_reputation and reputation_scores:
                rep = reputation_scores.get(r.peer_id, 50)
                quality = quality * (rep / 100)

            scored.append((r, quality))

        # Sort by quality (highest first)
        scored.sort(key=lambda x: x[1])
        best = scored[-1]  # Best quality

        # Get alternatives (top 3)
        alternatives = [
            {
                "peer_id": r.peer_id,
                "model": r.model_name,
                "response": r.response[:200] + "...",
                "quality_score": q,
                "was_selected": False
            }
            for r, q in scored[-2:]  # Top alternatives
        ]
        alternatives[-1]["was_selected"] = False  # Second best

        return EnsembleResult(
            final_response=best[0].response,
            method_used="quality_scored",
            responses_considered=len(responses),
            response_sources=[best[0].peer_id],
            confidence=best[1],
            alternative_responses=alternatives
        )

    def _fusion_ensemble(
        self,
        responses: List[ModelResponse],
        original_query: str
    ) -> EnsembleResult:
        """
        Fuse multiple responses into one comprehensive answer.

        Strategy: Take the best parts from each response.
        """
        if len(responses) == 1:
            return EnsembleResult(
                final_response=responses[0].response,
                method_used="fusion_single",
                responses_considered=1,
                response_sources=[responses[0].peer_id],
                confidence=0.7,
                alternative_responses=[]
            )

        # Score responses
        scored = [
            (r, self._score_quality(r.response, original_query))
            for r in responses
        ]
        scored.sort(key=lambda x: x[1])

        # Build fused response
        # Strategy: Use best quality for intro/conclusion
        #        Use most detailed for body
        #        Use best examples for illustration

        best_response = scored[-1][0]
        second_best = scored[-2][0] if len(scored) >= 2 else None

        # Simple fusion: append second best details if different enough
        if second_best:
            sim = self._calculate_similarity(
                best_response.response,
                second_best.response
            )

            if sim < 0.7:  # Different enough to add
                # Add clarification from second best
                fused = best_response.response + "\n\n"

                # Find unique parts in second best
                unique_parts = self._find_unique_parts(
                    best_response.response,
                    second_best.response
                )

                if unique_parts:
                    fused += "Additional context:\n" + "\n".join(unique_parts)

                return EnsembleResult(
                    final_response=fused,
                    method_used="fusion_merged",
                    responses_considered=len(responses),
                    response_sources=[best_response.peer_id, second_best.peer_id],
                    confidence=0.75,
                    alternative_responses=[]
                )

        return EnsembleResult(
            final_response=best_response.response,
            method_used="fusion_primary",
            responses_considered=len(responses),
            response_sources=[best_response.peer_id],
            confidence=scored[-1][1],
            alternative_responses=[]
        )

    def _redundancy_check(
        self,
        responses: List[ModelResponse],
        original_query: str
    ) -> EnsembleResult:
        """
        Cross-verify responses against each other.

        High confidence if multiple models agree on key points.
        """
        if len(responses) < 2:
            return self._quality_ensemble(responses, original_query)

        # Measure overall similarity
        similarities = []
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                sim = self._calculate_similarity(
                    responses[i].response,
                    responses[j].response
                )
                similarities.append(sim)

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0

        # High agreement: pick consensus
        if avg_similarity > 0.85:
            consensus_result = self._consensus_ensemble(responses, original_query)
            consensus_result.method_used = "redundancy_high_agreement"
            return consensus_result

        # Medium agreement: pick best quality
        if avg_similarity > 0.5:
            quality_result = self._quality_ensemble(responses, original_query)
            quality_result.method_used = "redundancy_moderate_agreement"
            return quality_result

        # Low agreement: flag as uncertain
        quality_result = self._quality_ensemble(responses, original_query)
        quality_result.confidence *= 0.7  # Reduce confidence
        quality_result.method_used = "redundancy_low_agreement"

        # Add disclaimer to response
        disclaimer = "\n\n[Note: Multiple models provided different answers. This response has lower confidence.]"
        quality_result.final_response += disclaimer

        return quality_result

    def _score_quality(self, response: str, query: str) -> float:
        """
        Score response quality (0-1).

        Metrics:
        - Length appropriateness
        - Structure (headers, lists, code blocks)
        - Clarity (readability)
        - Completeness (addresses query)
        """
        score = 0.0
        weights = self.quality_weights

        # Length score
        word_count = len(response.split())
        if 50 <= word_count <= 500:
            score += weights["length"]
        elif word_count < 50:
            score += weights["length"] * 0.5  # Too short
        # Long responses get partial credit

        # Structure score
        if "**" in response or "##" in response:
            score += weights["structure"]
        if "```" in response or "```python" in response:
            score += weights["structure"] * 0.5
        if "•" in response or "-" in response or "\n-" in response:
            score += weights["structure"] * 0.5

        # Clarity score
        sentences = re.split(r'[.!?]+', response)
        avg_sentence_length = sum(len(s.split()) for s in sentences if s) / len(sentences) if sentences else 0

        if 10 <= avg_sentence_length <= 25:  # Good average length
            score += weights["clarity"]
        elif avg_sentence_length < 10:
            score += weights["clarity"] * 0.7
        # Long sentences OK for technical content

        # Completeness score
        query_lower = query.lower()
        response_lower = response.lower()

        # Check if key query words are addressed
        key_terms = set(re.findall(r'\b\w+\b', query_lower))
        key_terms = key_terms - set(['le', 'la', 'les', 'un', 'une', 'des', 'et', 'ou', 'en', 'à'])

        if key_terms:
            addressed = sum(1 for term in key_terms if term in response_lower)
            completeness = addressed / len(key_terms)
            score += weights["completeness"] * completeness

        return min(score, 1.0)

    def _hash_response(self, response: str) -> str:
        """Hash response for similarity comparison."""
        # Normalize first
        normalized = re.sub(r'\s+', ' ', response.lower().strip())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _calculate_similarity(self, resp1: str, resp2: str) -> float:
        """
        Calculate similarity between two responses.

        Simple Jaccard-like similarity on words.
        """
        words1 = set(re.findall(r'\b\w+\b', resp1.lower()))
        words2 = set(re.findall(r'\b\w+\b', resp2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _find_unique_parts(self, base_response: str, other_response: str) -> List[str]:
        """Find sentences/paragraphs unique to other_response."""
        base_sentences = set(re.split(r'[.!?]', base_response.lower()))
        other_sentences = re.split(r'[.!?]', other_response)

        unique = []
        for sent in other_sentences:
            sent_lower = sent.lower().strip()
            if sent_lower and sent_lower not in base_sentences:
                unique.append(sent.strip())

        return unique[:3]  # Max 3 unique parts


# ============ Async Ensembling with P2P ============

class DistributedEnsembles:
    """
    Combine P2P distributed queries with ensembling.

    Workflow:
    1. Query k peers in parallel
    2. Collect responses
    3. Ensemble them
    4. Return best response
    """

    def __init__(self, p2p_peer):
        self.p2p = p2p_peer
        self.ensembling = BugEnsembling(use_reputation=True)

    async def query_and_ensemble(
        self,
        query: str,
        model_required: Optional[str] = None,
        k: int = 3,
        method: str = "auto"
    ) -> EnsembleResult:
        """
        Query P2P network and ensemble responses.

        Args:
            query: User's question
            model_required: Specific model needed
            k: Number of peers to query
            method: Ensembling method

        Returns:
            EnsembleResult with best response
        """
        # Select k capable peers
        capable_peers = self.p2p._select_peers_for_model(model_required, k)

        # Query in parallel
        responses_data = await self.p2p._query_peers_parallel(
            capable_peers[:k],
            query
        )

        # Convert to ModelResponse objects
        responses = []
        for r in responses_data:
            responses.append(ModelResponse(
                peer_id=r.get("peer_id", "unknown"),
                model_name=r.get("model", "unknown"),
                response=r.get("response", ""),
                latency_ms=r.get("latency_ms", 0),
                timestamp=r.get("timestamp", 0),
                metadata=r
            ))

        # Get reputation scores
        reputation_scores = self.p2p.reputation.peer_reputation

        # Ensemble
        result = await self.ensembling.ensemble_responses(
            responses,
            query,
            method=method,
            reputation_scores=reputation_scores
        )

        return result


# ============ CLI Test ============

async def main():
    """Test ensembling system."""
    ensemble = BugEnsembling()

    # Mock responses
    responses = [
        ModelResponse(
            peer_id="peer_a",
            model_name="qwen3:8b",
            response="**Creating recursive functions**\n\nA recursive function calls itself. Example:\n```python\ndef factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)\n```",
            latency_ms=3000,
            timestamp=0
        ),
        ModelResponse(
            peer_id="peer_b",
            model_name="GLM-4.7",
            response="Recursive functions are functions that call themselves. They need a base case to stop. For example, factorial:\n```python\ndef factorial(n):\n    return 1 if n == 1 else n * factorial(n-1)\n```",
            latency_ms=4500,
            timestamp=0
        ),
        ModelResponse(
            peer_id="peer_c",
            model_name="phi3-mini",
            response="Recursive function = function calls itself. Base case is required. Example:\ndef factorial(n): return 1 if n==1 else n*factorial(n-1)",
            latency_ms=1200,
            timestamp=0
        )
    ]

    query = "How do I create a recursive function in Python?"

    print("🔍 Testing Multi-Model Ensembling")
    print("=" * 50)
    print(f"Query: {query}\n")
    print(f"Models: {[r.model_name for r in responses]}\n")

    for method in ["consensus", "quality", "fusion", "redundancy"]:
        print(f"\n--- Method: {method.upper()} ---")
        result = await ensemble.ensemble_responses(responses, query, method=method)

        print(f"✓ Method used: {result.method_used}")
        print(f"✓ Responses considered: {result.responses_considered}")
        print(f"✓ Confidence: {result.confidence:.2f}")
        print(f"✓ Sources: {[s[:12]+'...' for s in result.response_sources]}")
        print(f"\n📝 Selected Response:")
        print(result.final_response[:300] + "...")

        if result.alternative_responses:
            print(f"\n🔄 Alternatives ({len(result.alternative_responses)})")
            for alt in result.alternative_responses:
                print(f"  - {alt['peer_id'][:12]}... (quality: {alt['quality_score']:.2f})")

    print("\n✅ Ensembling test complete")


if __name__ == "__main__":
    asyncio.run(main())