#!/usr/bin/env python3
"""
Resource Limits — CPU/RAM constraint control for UnityBrain.

Allows users to limit resource usage to prevent UnityBrain from
consuming all system resources.
"""

import asyncio
import psutil
import time
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import toml
import logging

logger = logging.getLogger("ResourceLimits")


@dataclass
class ResourceConfig:
    """Resource limits configuration."""

    cpu_limit_percent: float = 50.0      # Max CPU per peer
    ram_limit_percent: float = 70.0      # Max RAM per peer
    max_concurrent_requests: int = 3     # Simultaneous queries
    request_timeout_seconds: int = 60    # Per query timeout
    query_queue_max_size: int = 50       # Max queued queries

    @classmethod
    def from_file(cls, config_path: str) -> 'ResourceConfig':
        """Load from p2p_config.toml."""
        try:
            with open(config_path, 'r') as f:
                config = toml.load(f)

            limits = config.get('resource_limits', {})

            return cls(
                cpu_limit_percent=limits.get('cpu_limit_percent', 50.0),
                ram_limit_percent=limits.get('ram_limit_percent', 70.0),
                max_concurrent_requests=limits.get('max_concurrent_requests', 3),
                request_timeout_seconds=limits.get('request_timeout_seconds', 60),
                query_queue_max_size=limits.get('query_queue_max_size', 50)
            )
        except Exception as e:
            logger.warning(f"Could not load resource config: {e}, using defaults")
            return cls()


class ResourceMonitor:
    """Monitor system resources and enforce limits."""

    def __init__(self, config: ResourceConfig):
        self.config = config
        self._current_requests = 0
        self._total_requests_handled = 0
        self._rejected_requests = 0
        self._last_check = time.time()

    def get_system_usage(self) -> dict:
        """Get current system resource usage."""
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent
            return {
                'cpu': cpu,
                'ram': ram,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"Could not get system usage: {e}")
            return {'cpu': 0, 'ram': 0, 'timestamp': datetime.now().isoformat()}

    def can_accept_request(self) -> tuple[bool, str]:
        """Check if system can accept another request."""
        usage = self.get_system_usage()

        # Check CPU limit
        if usage['cpu'] >= self.config.cpu_limit_percent:
            reason = f"CPU too high: {usage['cpu']:.1f}% >= limit {self.config.cpu_limit_percent}%"
            return False, reason

        # Check RAM limit
        if usage['ram'] >= self.config.ram_limit_percent:
            reason = f"RAM too high: {usage['ram']:.1f}% >= limit {self.config.ram_limit_percent}%"
            return False, reason

        # Check concurrent request limit
        if self._current_requests >= self.config.max_concurrent_requests:
            reason = f"Too many concurrent requests: {self._current_requests} >= limit {self.config.max_concurrent_requests}"
            return False, reason

        return True, "OK"

    async def with_resource_limit(self, coro):
        """Run a coroutine with resource limit checking."""
        can_accept, reason = self.can_accept_request()

        if not can_accept:
            logger.warning(f"⚠️ Request rejected: {reason}")
            self._rejected_requests += 1
            return {
                'error': 'Resource limit exceeded',
                'reason': reason,
                'current_usage': self.get_system_usage(),
                'limits': {
                    'cpu': self.config.cpu_limit_percent,
                    'ram': self.config.ram_limit_percent,
                    'max_concurrent': self.config.max_concurrent_requests
                }
            }

        # Accept request
        self._current_requests += 1
        self._total_requests_handled += 1

        try:
            # Run with timeout
            result = await asyncio.wait_for(
                coro,
                timeout=self.config.request_timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout after {self.config.request_timeout_seconds}s")
            return {
                'error': 'Request timeout',
                'timeout_seconds': self.config.request_timeout_seconds
            }
        finally:
            self._current_requests -= 1

    def get_stats(self) -> dict:
        """Get resource limit statistics."""
        return {
            'config': {
                'cpu_limit': self.config.cpu_limit_percent,
                'ram_limit': self.config.ram_limit_percent,
                'max_concurrent': self.config.max_concurrent_requests,
                'queue_max': self.config.query_queue_max_size,
                'request_timeout': self.config.request_timeout_seconds
            },
            'current': {
                'active_requests': self._current_requests,
                'total_handled': self._total_requests_handled,
                'rejected': self._rejected_requests
            },
            'system': self.get_system_usage()
        }

    def configure(self, **kwargs):
        """Reconfigure limits at runtime."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated resource limit: {key} = {value}")


class RequestQueue:
    """Queue for pending requests with size limit."""

    def __init__(self, max_size: int):
        self.max_size = max_size
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._dropped = 0

    async def put(self, request_id: str) -> bool:
        """Add request to queue. Returns True if added, False if dropped."""
        try:
            await asyncio.wait_for(self.queue.put(request_id), timeout=0.1)
            return True
        except asyncio.TimeoutError:
            self._dropped += 1
            return False

    async def get(self) -> Optional[str]:
        """Get next request from queue."""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    def size(self) -> int:
        """Current queue size."""
        return self.queue.qsize()

    def dropped_count(self) -> int:
        """Number of dropped requests."""
        return self._dropped

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return {
            'size': self.size(),
            'max_size': self.max_size,
            'dropped': self.dropped_count()
        }


# ============ CLI for Resource Limits ============

def print_current_usage():
    """Print current system resource usage."""
    usage = ResourceMonitor(ResourceConfig()).get_system_usage()
    print("\n📊 Current System Resource Usage:")
    print(f"   CPU  : {usage['cpu']:.1f}%")
    print(f"   RAM  : {usage['ram']:.1f}%")
    print(f"   Time : {usage['timestamp']}\n")


if __name__ == "__main__":
    # Quick test
    print_current_usage()

    # Load config and print
    config_path = Path(__file__).parent / "p2p_config.toml"
    config = ResourceConfig.from_file(str(config_path))

    print("🔧 Resource Limits Configuration:")
    print(f"   CPU Limit     : {config.cpu_limit_percent}%")
    print(f"   RAM Limit     : {config.ram_limit_percent}%")
    print(f"   Max Concurrent: {config.max_concurrent_requests}")
    print(f"   Request Timeout: {config.request_timeout_seconds}s")
    print(f"   Queue Max    : {config.query_queue_max_size}\n")