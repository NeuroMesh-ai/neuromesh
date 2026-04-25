# Auto-imports for extracted module
from typing import Dict
import os
import time


class CircuitBreaker:
    """Circuit breaker pattern for peer failover protection"""
    STATE_CLOSED = "closed"      # Normal operation
    STATE_OPEN = "open"          # Failing, reject calls
    STATE_HALF_OPEN = "half_open"  # Testing if recovered

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60,
                 half_open_max: int = 1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        if self.state == self.STATE_CLOSED:
            return True
        if self.state == self.STATE_OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.STATE_HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker: OPEN → HALF_OPEN")
                return True
            return False
        if self.state == self.STATE_HALF_OPEN:
            if self.half_open_calls < self.half_open_max:
                self.half_open_calls += 1
                return True
            return False
        return False

    def record_success(self):
        if self.state == self.STATE_HALF_OPEN:
            self.success_count += 1
            self.state = self.STATE_CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker: HALF_OPEN → CLOSED (recovered)")
        else:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.STATE_OPEN
            logger.warning(f"Circuit breaker: CLOSED → OPEN ({self.failure_count} failures)")

    @property
    def is_available(self) -> bool:
        return self.can_execute()

    def to_dict(self) -> Dict:
        return {
            "state": self.state,
            "failures": self.failure_count,
            "last_failure": self.last_failure_time
        }


# ============================================================================
# ============== JWT TOKEN AUTH (Point 1) ==================================
# ============================================================================
