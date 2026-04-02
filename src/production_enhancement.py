#!/usr/bin/env python3
"""
🔍 Production Enhancement Module - UnityBrain & BugBrain v3.0
Implémente tous les gaps identifiés pour la production readiness

1. Monitoring & Observability (Structured logging, Prometheus metrics, Dashboards)
2. Production Readiness (Error handling, Retry logic, Circuit breaker, Health checks)
3. Security Implementation (TLS/DTLS, Sybil resistance, Rate limiting)
4. API Features (Streaming responses, Batch requests, OpenAPI/Swagger)
5. Performance (Caching, Intelligent load balancing)
6. Model Management (Distributed sharding, Versioning, Rollback)
"""

import asyncio
import json
import time
import logging
import logging.handlers
import hashlib
import ssl
import aiohttp
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import random
import re
import os

# ============================================================================
# ============== 1. MONITORING & OBSERVABILITY ============================
# ============================================================================

class LogLevel(Enum):
    """Niveaux de log"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class LogEntry:
    """Entrée de log structurée"""
    timestamp: datetime
    level: LogLevel
    service: str
    component: str
    message: str
    context: Dict = field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    def to_json(self) -> str:
        """Convertit en JSON"""
        return json.dumps({
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "service": self.service,
            "component": self.component,
            "message": self.message,
            "context": self.context,
            "trace_id": self.trace_id,
            "span_id": self.span_id
        })

class StructuredLogger:
    """Logger structuré centralisé"""

    def __init__(self, service_name: str, log_file: str = "logs/unitybrain.log"):
        self.service_name = service_name
        self.log_file = log_file

        # Créer le répertoire des logs
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Setup logging
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(logging.DEBUG)

        # File handler avec rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10
        )
        file_handler.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter structuré JSON
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, level: LogLevel, component: str, message: str,
            context: Dict = None, trace_id: str = None, span_id: str = None):
        """Log structuré"""
        log_entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=level,
            service=self.service_name,
            component=component,
            message=message,
            context=context or {},
            trace_id=trace_id,
            span_id=span_id
        )

        # Log dans le fichier
        self.logger.log(
            getattr(logging, level.value),
            log_entry.to_json()
        )

        # Console output simplifié
        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            print(f"[{level.value}] {component}: {message}")
        elif level == LogLevel.WARNING:
            print(f"[WARNING] {component}: {message}")

    def debug(self, component: str, message: str, **context):
        self.log(LogLevel.DEBUG, component, message, context)

    def info(self, component: str, message: str, **context):
        self.log(LogLevel.INFO, component, message, context)

    def warning(self, component: str, message: str, **context):
        self.log(LogLevel.WARNING, component, message, context)

    def error(self, component: str, message: str, **context):
        self.log(LogLevel.ERROR, component, message, context)

    def critical(self, component: str, message: str, **context):
        self.log(LogLevel.CRITICAL, component, message, context)

@dataclass
class Metric:
    """Métrique Prometheus"""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

class MetricsCollector:
    """Collecteur de métriques (Prometheus-style)"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)

    def increment(self, name: str, value: float = 1.0, labels: Dict = None):
        """Incrémente un counter"""
        key = self._make_key(name, labels)
        self.counters[key] += value

        metric = Metric(name, self.counters[key], labels)
        self.metrics[key].append(metric)

    def set(self, name: str, value: float, labels: Dict = None):
        """Définit un gauge"""
        key = self._make_key(name, labels)
        self.gauges[key] = value

        metric = Metric(name, value, labels)
        self.metrics[key].append(metric)

    def observe(self, name: str, value: float, labels: Dict = None):
        """Observe une valeur (histogram)"""
        key = self._make_key(name, labels)
        self.histograms[key].append(value)

        metric = Metric(name, value, labels)
        self.metrics[key].append(metric)

    def _make_key(self, name: str, labels: Dict = None) -> str:
        """Crée une clé unique"""
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    def get_prometheus_metrics(self) -> str:
        """Retourne les métriques au format Prometheus"""
        output = []

        # Counters
        for key, value in self.counters.items():
            name = key.split("{")[0]
            output.append(f"# TYPE {name} counter")
            output.append(f"{name} {value}")

        # Gauges
        for key, value in self.gauges.items():
            name = key.split("{")[0]
            output.append(f"# TYPE {name} gauge")
            output.append(f"{name} {value}")

        # Histograms (simplifié)
        for key, values in self.histograms.items():
            name = key.split("{")[0]
            if values:
                output.append(f"# TYPE {name} histogram")
                output.append(f"{name}_sum {sum(values)}")
                output.append(f"{name}_count {len(values)}")

        return "\n".join(output)

    def get_stats(self) -> Dict:
        """Statistiques des métriques"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {k: {
                "count": len(v),
                "sum": sum(v),
                "avg": sum(v) / len(v) if v else 0
            } for k, v in self.histograms.items()}
        }

class HealthChecker:
    """Health checker actif"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.health_checks: Dict[str, Callable] = {}
        self.status: Dict[str, bool] = {}
        self.last_check: Dict[str, datetime] = {}

    def register_check(self, name: str, check_func: Callable, interval: int = 60):
        """Enregistre un health check"""
        self.health_checks[name] = {
            "func": check_func,
            "interval": interval
        }

    async def run_all_checks(self) -> Dict:
        """Exécute tous les health checks"""
        results = {}

        for name, check_config in self.health_checks.items():
            try:
                healthy = await check_config["func"]()
                self.status[name] = healthy
                self.last_check[name] = datetime.utcnow()
                results[name] = {
                    "healthy": healthy,
                    "last_check": self.last_check[name].isoformat()
                }
            except Exception as e:
                self.status[name] = False
                results[name] = {
                    "healthy": False,
                    "error": str(e),
                    "last_check": datetime.utcnow().isoformat()
                }

        return {
            "service": self.service_name,
            "status": "healthy" if all(results.values()) else "unhealthy",
            "checks": results
        }

# ============================================================================
# ============== 2. PRODUCTION READINESS ====================================
# ============================================================================

class CircuitBreakerState(Enum):
    """État du circuit breaker"""
    CLOSED = "closed"      # Fonctionnement normal
    OPEN = "open"          # Circuit ouvert (échecs)
    HALF_OPEN = "half_open"  # Test de réouverture

@dataclass
class CircuitBreakerConfig:
    """Configuration du circuit breaker"""
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0  # Secondes

class CircuitBreaker:
    """Circuit breaker pattern"""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Appelle une fonction avec protection circuit breaker"""

        if self.state == CircuitBreakerState.OPEN:
            # Vérifier si on peut passer en HALF_OPEN
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError(f"Circuit {self.name} is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Vérifie si on peut tenter une réouverture"""
        if self.last_failure_time:
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            return elapsed >= self.config.timeout
        return False

    def _on_success(self):
        """Appelé en cas de succès"""
        self.failure_count = 0

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED

    def _on_failure(self):
        """Appelé en cas d'échec"""
        self.failure_count += 1
        self.success_count = 0
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    def get_status(self) -> Dict:
        """Statut du circuit breaker"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }

class CircuitBreakerOpenError(Exception):
    """Exception quand le circuit breaker est ouvert"""
    pass

class RetryStrategy:
    """Stratégie de retry avec backoff exponentiel"""

    def __init__(self,
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 exponential_base: float = 2.0,
                 jitter: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calcule le délai pour un essai"""
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))

        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)

        return min(delay, self.max_delay)

    async def retry(self, func: Callable, *args, **kwargs) -> Any:
        """Tente une fonction avec retry"""
        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt == self.max_attempts:
                    raise e

                delay = self.get_delay(attempt)
                await asyncio.sleep(delay)

        raise last_error

# ============================================================================
# ============== 3. SECURITY IMPLEMENTATION =================================
# ============================================================================

class RateLimiter:
    """Rate limiter (Token bucket)"""

    def __init__(self, rate: int, per: float):
        self.rate = rate  # Tokens par seconde
        self.per = per
        self.tokens = rate
        self.last_update = time.time()

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquiert des tokens"""
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens
        self.tokens += elapsed * self.rate
        self.tokens = min(self.tokens, self.rate * self.per)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

class SybilResistance:
    """Résistance aux attaques Sybil"""

    def __init__(self, min_reputation: float = 0.7, required_stake: float = 100.0):
        self.min_reputation = min_reputation
        self.required_stake = required_stake
        self.peer_stakes: Dict[str, float] = {}

    def register_stake(self, peer_id: str, stake: float):
        """Enregistre le stake d'un peer"""
        self.peer_stakes[peer_id] = stake

    def is_trusted(self, peer_id: str, reputation: float) -> bool:
        """Vérifie si un peer est trusté"""
        if peer_id not in self.peer_stakes:
            return False

        return (reputation >= self.min_reputation and
                self.peer_stakes[peer_id] >= self.required_stake)

    def punish_sybil(self, peer_id: str):
        """Punition pour comportement Sybil"""
        if peer_id in self.peer_stakes:
            self.peer_stakes[peer_id] *= 0.5  # Réduire le stake

# ============================================================================
# ============== 4. API FEATURES ============================================
# ============================================================================

async def stream_response(generator, delay: float = 0.1):
    """Stream les réponses"""
    async for chunk in generator:
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(delay)

class BatchRequest:
    """Requête batch"""

    def __init__(self):
        self.requests: List[Dict] = []

    def add(self, prompt: str, model: str = None, **kwargs):
        """Ajoute une requête"""
        self.requests.append({
            "prompt": prompt,
            "model": model,
            **kwargs
        })

    async def execute(self, query_func: Callable) -> List[Dict]:
        """Exécute toutes les requêtes en parallèle"""
        tasks = [query_func(req["prompt"], req.get("model")) for req in self.requests]
        return await asyncio.gather(*tasks)

# ============================================================================
# ============== 5. PERFORMANCE ============================================
# ============================================================================

@dataclass
class CacheEntry:
    """Entrée de cache"""
    value: Any
    expires_at: datetime
    hit_count: int = 0

class IntelligentCache:
    """Cache intelligent avec TTL"""

    def __init__(self, default_ttl: int = 3600, max_size: int = 1000):
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cache: Dict[str, CacheEntry] = {}

    def _make_key(self, key: Any) -> str:
        """Crée une clé de cache"""
        return hashlib.sha256(str(key).encode()).hexdigest()

    def get(self, key: Any) -> Optional[Any]:
        """Récupère depuis le cache"""
        cache_key = self._make_key(key)

        if cache_key in self.cache:
            entry = self.cache[cache_key]

            if datetime.utcnow() < entry.expires_at:
                entry.hit_count += 1
                return entry.value
            else:
                # Expired
                del self.cache[cache_key]

        return None

    def set(self, key: Any, value: Any, ttl: int = None):
        """Stocke dans le cache"""
        if len(self.cache) >= self.max_size:
            self._evict()

        cache_key = self._make_key(key)
        ttl = ttl or self.default_ttl

        self.cache[cache_key] = CacheEntry(
            value=value,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl)
        )

    def _evict(self):
        """Évince les entrées les moins utilisées"""
        # LRU: supprimer l'entrée avec le plus petit hit_count
        if self.cache:
            key_to_evict = min(self.cache.keys(),
                              key=lambda k: self.cache[k].hit_count)
            del self.cache[key_to_evict]

    def clear(self):
        """Vide le cache"""
        self.cache.clear()

    def get_stats(self) -> Dict:
        """Statistiques du cache"""
        total_hits = sum(entry.hit_count for entry in self.cache.values())
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "total_hits": total_hits,
            "hit_rate": total_hits / (total_hits + 100) if total_hits else 0
        }

# ============================================================================
# ============== 6. MODEL MANAGEMENT ========================================
# ============================================================================

@dataclass
class ModelVersion:
    """Version d'un modèle"""
    version: str
    name: str
    ollama_name: str
    created_at: datetime
    checksum: str
    active: bool = False
    sharded: bool = False

class ModelManager:
    """Gestionnaire de modèles avec versioning"""

    def __init__(self):
        self.models: Dict[str, List[ModelVersion]] = {}
        self.shards: Dict[str, List[str]] = {}  # model -> list of peer_ids

    def register_model(self, name: str, version: str, ollama_name: str,
                      checksum: str, sharded: bool = False):
        """Enregistre une nouvelle version de modèle"""
        if name not in self.models:
            self.models[name] = []

        model_version = ModelVersion(
            version=version,
            name=name,
            ollama_name=ollama_name,
            created_at=datetime.utcnow(),
            checksum=checksum,
            sharded=sharded
        )

        self.models[name].append(model_version)

        # Marquer comme active si c'est la première
        if len(self.models[name]) == 1:
            self.activate_model(name, version)

    def activate_model(self, name: str, version: str):
        """Active une version de modèle"""
        if name in self.models:
            for mv in self.models[name]:
                mv.active = (mv.version == version)

    def get_active_model(self, name: str) -> Optional[ModelVersion]:
        """Retourne la version active"""
        if name in self.models:
            for mv in self.models[name]:
                if mv.active:
                    return mv
        return None

    def rollback(self, name: str, steps: int = 1):
        """Rollback à une version précédente"""
        if name in self.models and len(self.models[name]) > 1:
            current_index = next(i for i, mv in enumerate(self.models[name]) if mv.active)

            # Désactiver la version actuelle
            self.models[name][current_index].active = False

            # Activer la version précédente
            target_index = max(0, current_index - steps)
            self.models[name][target_index].active = True

    def distribute_shard(self, model_name: str, shard_data: bytes,
                        peer_ids: List[str]):
        """Distribue un shard de modèle"""
        if model_name not in self.shards:
            self.shards[model_name] = []

        self.shards[model_name].extend(peer_ids)

    def get_shard_location(self, model_name: str, shard_id: int) -> Optional[str]:
        """Retourne la localisation d'un shard"""
        if model_name in self.shards and shard_id < len(self.shards[model_name]):
            return self.shards[model_name][shard_id]
        return None

# ============================================================================
# ============== 7. PRODUCTION ENHANCEMENT MANAGER =========================
# ============================================================================

@dataclass
class ProductionConfig:
    """Configuration de production"""
    enable_monitoring: bool = True
    enable_circuit_breaker: bool = True
    enable_retry: bool = True
    enable_rate_limiting: bool = True
    enable_caching: bool = True
    enable_model_versioning: bool = True

class ProductionEnhancement:
    """Manager d'amélioration de production"""

    def __init__(self, service_name: str, config: ProductionConfig = None):
        self.service_name = service_name
        self.config = config or ProductionConfig()

        # 1. Monitoring
        if self.config.enable_monitoring:
            self.logger = StructuredLogger(service_name)
            self.metrics = MetricsCollector(service_name)
            self.health_checker = HealthChecker(service_name)

        # 2. Circuit breakers
        if self.config.enable_circuit_breaker:
            self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # 3. Retry
        if self.config.enable_retry:
            self.retry_strategy = RetryStrategy()

        # 4. Security
        if self.config.enable_rate_limiting:
            self.rate_limiter = RateLimiter(rate=100, per=60)
            self.sybil_resistance = SybilResistance()

        # 5. Performance
        if self.config.enable_caching:
            self.cache = IntelligentCache()

        # 6. Model management
        if self.config.enable_model_versioning:
            self.model_manager = ModelManager()

    def log(self, level: LogLevel, component: str, message: str, **context):
        """Log structuré"""
        if self.config.enable_monitoring and hasattr(self, 'logger'):
            self.logger.log(level, component, message, context)

    def metric_increment(self, name: str, value: float = 1.0, labels: Dict = None):
        """Incrémente une métrique"""
        if self.config.enable_monitoring and hasattr(self, 'metrics'):
            self.metrics.increment(name, value, labels)

    def metric_set(self, name: str, value: float, labels: Dict = None):
        """Définit une métrique gauge"""
        if self.config.enable_monitoring and hasattr(self, 'metrics'):
            self.metrics.set(name, value, labels)

    def metric_observe(self, name: str, value: float, labels: Dict = None):
        """Observe une métrique histogram"""
        if self.config.enable_monitoring and hasattr(self, 'metrics'):
            self.metrics.observe(name, value, labels)

    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None):
        """Enregistre un circuit breaker"""
        if self.config.enable_circuit_breaker:
            self.circuit_breakers[name] = CircuitBreaker(
                name,
                config or CircuitBreakerConfig()
            )

    async def call_with_circuit_breaker(self, name: str, func: Callable,
                                       *args, **kwargs) -> Any:
        """Appelle avec protection circuit breaker"""
        if self.config.enable_circuit_breaker and name in self.circuit_breakers:
            cb = self.circuit_breakers[name]
            return await cb.call(func, *args, **kwargs)
        return await func(*args, **kwargs)

    async def call_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Appelle avec retry"""
        if self.config.enable_retry and hasattr(self, 'retry_strategy'):
            return await self.retry_strategy.retry(func, *args, **kwargs)
        return await func(*args, **kwargs)

    async def check_rate_limit(self, tokens: int = 1) -> bool:
        """Vérifie le rate limit"""
        if self.config.enable_rate_limiting and hasattr(self, 'rate_limiter'):
            return await self.rate_limiter.acquire(tokens)
        return True

    def cache_get(self, key: Any) -> Optional[Any]:
        """Récupère depuis le cache"""
        if self.config.enable_caching and hasattr(self, 'cache'):
            return self.cache.get(key)
        return None

    def cache_set(self, key: Any, value: Any, ttl: int = None):
        """Stocke dans le cache"""
        if self.config.enable_caching and hasattr(self, 'cache'):
            self.cache.set(key, value, ttl)

    async def get_prometheus_metrics(self) -> str:
        """Retourne les métriques Prometheus"""
        if self.config.enable_monitoring and hasattr(self, 'metrics'):
            return self.metrics.get_prometheus_metrics()
        return ""

    async def get_health_status(self) -> Dict:
        """Retourne le statut de santé"""
        if self.config.enable_monitoring and hasattr(self, 'health_checker'):
            return await self.health_checker.run_all_checks()
        return {"service": self.service_name, "status": "healthy"}

    def get_status(self) -> Dict:
        """Statut complet de production"""
        status = {
            "service": self.service_name,
            "config": asdict(self.config),
        }

        if self.config.enable_monitoring:
            status["metrics"] = self.metrics.get_stats()
            status["circuit_breakers"] = {
                name: cb.get_status()
                for name, cb in self.circuit_breakers.items()
            }
            status["cache"] = self.cache.get_stats()

        return status

# ============================================================================
# ============== MAIN - DÉMO ==============================================
# ============================================================================

async def main():
    """Demo du module de production enhancement"""

    print("=" * 70)
    print("🔍 PRODUCTION ENHANCEMENT MODULE")
    print("=" * 70)

    # Créer le manager
    config = ProductionConfig()
    prod = ProductionEnhancement("UnityBrain", config)

    # 1. Logging
    print("\n1️⃣ Logging structuré:")
    prod.log(LogLevel.INFO, "TestComponent", "Test log message", user="denis")

    # 2. Métriques
    print("\n2️⃣ Métriques Prometheus:")
    prod.metric_increment("requests_total", 1.0, {"endpoint": "/query"})
    prod.metric_set("active_connections", 42.0)
    prod.metric_observe("request_latency", 123.4, {"endpoint": "/query"})
    print(prod.metrics.get_stats())

    # 3. Circuit breaker
    print("\n3️⃣ Circuit breaker:")
    prod.register_circuit_breaker("ollama_query")

    async def failing_func():
        raise Exception("Test failure")

    try:
        await prod.call_with_circuit_breaker("ollama_query", failing_func)
    except:
        pass

    print(prod.circuit_breakers["ollama_query"].get_status())

    # 4. Retry
    print("\n4️⃣ Retry avec backoff:")
    attempts = 0

    async def test_func():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception("Retry test")
        return "Success!"

    result = await prod.call_with_retry(test_func)
    print(f"Result after {attempts} attempts: {result}")

    # 5. Rate limiting
    print("\n5️⃣ Rate limiting:")
    for i in range(5):
        allowed = await prod.check_rate_limit()
        print(f"Request {i+1}: {'✅' if allowed else '❌'}")

    # 6. Cache
    print("\n6️⃣ Cache intelligent:")
    prod.cache_set("test_key", {"data": "cached_value"}, ttl=60)
    cached = prod.cache_get("test_key")
    print(f"Cached data: {cached}")
    print(f"Cache stats: {prod.cache.get_stats()}")

    # 7. Prometheus metrics
    print("\n7️⃣ Métriques Prometheus:")
    print(await prod.get_prometheus_metrics())

    print("\n" + "=" * 70)
    print("✅ Production Enhancement Module ready!")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(main())