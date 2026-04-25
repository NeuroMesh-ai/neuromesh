# Auto-imports for extracted module
from typing import Dict
from typing import List
from typing import Tuple
import aiohttp
import json
import os
import time


class Peer:
    """Représente un peer dans le réseau P2P"""
    def __init__(self, name: str, host: str, port: int, models: List[str],
                 ollama_host: str = None, ollama_port: int = 11434):
        self.name = name
        self.host = host
        self.port = port
        self.models = models
        self.ollama_host = ollama_host or host
        self.ollama_port = ollama_port
        self.available = False
        self.latency = float('inf')
        self.reputation = 1.0
        self.last_seen = 0
        self.circuit_breaker = CircuitBreaker()
        self.model_stats: Dict[str, Dict] = {}

    async def ping(self, session: aiohttp.ClientSession, auth_headers: Dict = None) -> float:
        """Ping le peer via HTTP API"""
        if not self.circuit_breaker.can_execute():
            self.available = False
            return float('inf')
        try:
            start = time.time()
            url = f"http://{self.host}:{self.port}/api/ping"
            headers = auth_headers or {}
            async with session.get(url, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.latency = round((time.time() - start) * 1000, 2)
                    self.available = True
                    self.last_seen = time.time()
                    self.circuit_breaker.record_success()
                    if 'models' in data:
                        for m in data['models']:
                            if m not in self.model_stats:
                                self.model_stats[m] = {"success": 0, "total": 0, "latency_sum": 0}
                                if m not in self.models:
                                    self.models.append(m)
                    return self.latency
            self.available = False
            self.circuit_breaker.record_failure()
            return float('inf')
        except Exception as e:
            self.available = False
            self.circuit_breaker.record_failure()
            logger.debug(f"Ping {self.name} failed: {e}")
            return float('inf')

    async def query_model(self, session: aiohttp.ClientSession, model: str,
                          prompt: str, max_length: int = 2000,
                          auth_headers: Dict = None) -> Tuple[str, float]:
        """Query un modèle via Ollama HTTP API"""
        try:
            start = time.time()
            url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False,
                       "options": {"num_predict": max_length}}
            async with session.post(url, json=payload,
                                     timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get('response', '')[:max_length]
                    latency = round((time.time() - start) * 1000, 2)
                    self._update_stats(model, True, latency)
                    return response, latency
                error = await resp.text()
                logger.error(f"Ollama error from {self.name}: {resp.status}")
                self._update_stats(model, False, 0)
                return f"Error: {resp.status}", float('inf')
        except Exception as e:
            logger.error(f"Query {model}@{self.name} failed: {e}")
            self._update_stats(model, False, 0)
            return f"Error: {str(e)}", float('inf')

    async def query_via_peer(self, session: aiohttp.ClientSession, model: str,
                              prompt: str, max_length: int = 2000,
                              auth_headers: Dict = None) -> Tuple[str, float]:
        """Query via the peer's UnityBrain API"""
        if not self.circuit_breaker.can_execute():
            return "Error: circuit breaker open", float('inf')
        try:
            start = time.time()
            url = f"http://{self.host}:{self.port}/api/query"
            payload = {"prompt": prompt, "model": model}
            headers = auth_headers or {}
            async with session.post(url, json=payload, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get('response', '')[:max_length]
                    latency = round((time.time() - start) * 1000, 2)
                    self.circuit_breaker.record_success()
                    return response, latency
                self.circuit_breaker.record_failure()
                return f"Error: {resp.status}", float('inf')
        except Exception as e:
            self.circuit_breaker.record_failure()
            return f"Error: {str(e)}", float('inf')

    def _update_stats(self, model: str, success: bool, latency: float):
        if model not in self.model_stats:
            self.model_stats[model] = {"success": 0, "total": 0, "latency_sum": 0}
        self.model_stats[model]["total"] += 1
        if success:
            self.model_stats[model]["success"] += 1
            self.model_stats[model]["latency_sum"] += latency

    def vote_reputation(self, delta: float):
        self.reputation = max(0.0, min(1.0, self.reputation + delta))

    def to_dict(self) -> Dict:
        return {
            "name": self.name, "host": self.host, "port": self.port,
            "models": self.models, "available": self.available,
            "latency": self.latency, "reputation": self.reputation,
            "last_seen": self.last_seen,
            "circuit_breaker": self.circuit_breaker.to_dict()
        }


# ============================================================================
# ============== MODEL ROUTING ============================================
# ============================================================================
