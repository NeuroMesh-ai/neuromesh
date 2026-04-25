# Auto-imports for extracted module
from typing import Dict
from typing import List
import aiohttp
from discovery.peer import Peer


class EnsembleConsensus:
    """Consensus multi-modèles pour réponses fiables"""
    def __init__(self, agreement_threshold: float = 0.6):
        self.agreement_threshold = agreement_threshold

    async def query_ensemble(self, session: aiohttp.ClientSession,
                              models: List[str], prompt: str, peer: Peer,
                              auth_headers: Dict = None) -> Dict:
        responses = []
        for model in models:
            response, latency = await peer.query_model(session, model, prompt,
                                                        auth_headers=auth_headers)
            responses.append({"model": model, "response": response, "latency": latency})

        if not responses:
            return {"consensus": "", "individual_responses": [], "agreement_score": 0}

        consensus = max(responses, key=lambda r: len(r["response"]))["response"]
        max_len = max(len(r["response"]) for r in responses) or 1
        agreement = sum(len(r["response"]) for r in responses) / (len(responses) * max_len)

        return {"consensus": consensus, "individual_responses": responses,
                "agreement_score": round(agreement, 3)}


# ============================================================================
# ============== QUERY HISTORY ============================================
# ============================================================================
from discovery.peer import Peer
import aiohttp
