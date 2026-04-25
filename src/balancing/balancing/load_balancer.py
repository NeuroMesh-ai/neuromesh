# Auto-imports for extracted module
from typing import Any
from typing import Dict
from typing import Optional
import os


class LoadBalancer:
    """Intelligent load balancing between nodes.
    Routes queries based on:
    - Model availability (primary filter)
    - Latency + success rate (secondary)
    - Circuit breaker state (safety)
    - Local CPU load (offload when busy)
    """
    
    def __init__(self):
        self.node_scores: Dict[str, float] = {}
    
    def calculate_score(self, peer, model: str = None) -> float:
        """Calculate routing score (lower = better).
        Factors: latency (40%), model availability (30%), success rate (20%), CB (10%)
        """
        if peer.latency == float('inf') or not peer.available:
            return float('inf')
        
        # Latency score (0-100)
        latency_score = min(peer.latency / 10, 100)
        
        # Model availability penalty
        model_penalty = 0
        if model and model not in peer.models and peer.models:
            model_penalty = 50
        
        # Success rate from model stats
        stats = peer.model_stats.get(model, {}) if model else {}
        total = stats.get('total', 0)
        success = stats.get('success', 0)
        success_rate = success / total if total > 0 else 1.0
        success_score = (1 - success_rate) * 100
        
        # CB penalty
        cb_penalty = 0 if peer.circuit_breaker.state == 'closed' else 50
        
        score = (
            latency_score * 0.4 +
            model_penalty * 0.3 +
            success_score * 0.2 +
            cb_penalty * 0.1
        )
        self.node_scores[peer.name] = score
        return score
    
    def select_best_peer(self, peers: list, model: str = None,
                          exclude: str = None) -> Optional[Any]:
        """Select the best peer for a query, prioritizing model availability."""
        candidates = [p for p in peers 
                       if p.available 
                       and p.circuit_breaker.can_execute()
                       and p.name != exclude]
        if not candidates:
            return None
        
        # Prefer peers that have the requested model
        if model:
            model_peers = [p for p in candidates if model in p.models]
            if model_peers:
                candidates = model_peers
        
        scored = [(self.calculate_score(p, model), p) for p in candidates]
        scored.sort(key=lambda x: x[0])
        
        if scored[0][0] == float('inf'):
            return None
        return scored[0][1]
    
    def should_handle_locally(self, local_cpu: float, local_mem_pct: float,
                                peers: list, model: str) -> bool:
        """Decide if query should be handled locally or offloaded.
        - CPU > 80% and fast peer available -> offload
        - CPU < 50% or no peers -> handle locally
        - Medium: prefer local (network overhead > latency gain)
        """
        available_peers = [p for p in peers if p.available]
        
        if local_cpu > 80 and available_peers:
            best = self.select_best_peer(peers, model)
            if best and best.latency < 200:
                return False
        
        if local_cpu < 50 or not available_peers:
            return True
        
        return True


# ============================================================================
# ============== PEER & P2P NETWORK ========================================
# ============================================================================

# Peer purge constants
PEER_STALE_SECONDS = 600      # 10 min without being seen = stale
PEER_PURGE_SECONDS = 1800     # 30 min without being seen = purge (remove)
PEER_CB_PURGE_FAILURES = 50   # CB failures above this = candidate for purge

