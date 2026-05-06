#!/usr/bin/env python3
"""
🧪 Resource Guard Tests — UnityBrain v5
========================================

Comprehensive test suite covering:
- Initialization and configuration
- CPU/RAM threshold checks
- User activity detection
- State transitions (ACTIVE, THROTTLED, PAUSED, DISABLED, ERROR)
- Rate limiting and burst protection
- Request size limits (anti-DoS)
- Edge cases: no psutil, 100% CPU at startup, config clamping
- Concurrency safety
"""

import asyncio
import time
import threading
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from collections import deque

# Import the module
from resource_guard import ResourceGuard, GuardState, HAS_PSUTIL


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def default_config():
    """Default public_mesh config."""
    return {
        "enabled": True,
        "max_cpu_percent": 30.0,
        "max_ram_share_mb": 2048,
        "gpu_share": False,
        "priority": "local_first",
        "bandwidth_limit_kbps": 5000,
    }


@pytest.fixture
def guard(default_config):
    """Create a ResourceGuard with default config."""
    g = ResourceGuard(default_config)
    # Override user activity to avoid flaky tests
    g._last_user_activity = 0.0  # no activity detected
    return g


@pytest.fixture
def guard_no_psutil(default_config):
    """Create a ResourceGuard when psutil is unavailable."""
    with patch('resource_guard.HAS_PSUTIL', False):
        g = ResourceGuard(default_config)
        return g


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

class TestInitialization:
    def test_default_config(self):
        g = ResourceGuard({"enabled": True})
        assert g.max_cpu_percent == 30.0
        assert g.max_ram_share_mb == 2048
        assert g.gpu_share is False
        assert g.priority == "local_first"
        assert g.enabled is True

    def test_custom_config(self, default_config):
        default_config["max_cpu_percent"] = 50.0
        default_config["max_ram_share_mb"] = 4096
        default_config["gpu_share"] = True
        g = ResourceGuard(default_config)
        assert g.max_cpu_percent == 50.0
        assert g.max_ram_share_mb == 4096
        assert g.gpu_share is True

    def test_config_clamping_high_cpu(self, default_config):
        """CPU limit cannot exceed hard cap (80%)."""
        default_config["max_cpu_percent"] = 99.0
        g = ResourceGuard(default_config)
        assert g.max_cpu_percent == 80.0

    def test_config_clamping_low_cpu(self, default_config):
        """CPU limit cannot go below 5%."""
        default_config["max_cpu_percent"] = 1.0
        g = ResourceGuard(default_config)
        assert g.max_cpu_percent == 5.0

    def test_config_clamping_high_ram(self, default_config):
        """RAM limit cannot exceed 16GB."""
        default_config["max_ram_share_mb"] = 65536
        g = ResourceGuard(default_config)
        assert g.max_ram_share_mb == 16384

    def test_config_clamping_low_ram(self, default_config):
        """RAM limit cannot go below 256MB."""
        default_config["max_ram_share_mb"] = 50
        g = ResourceGuard(default_config)
        assert g.max_ram_share_mb == 256

    def test_disabled_by_default(self):
        g = ResourceGuard()
        assert g.enabled is False
        assert g._state == GuardState.DISABLED

    def test_enabled_config(self, default_config):
        default_config["enabled"] = True
        g = ResourceGuard(default_config)
        assert g.enabled is True

    def test_no_psutil_refuses_all(self, guard_no_psutil):
        """When psutil is unavailable, all requests are refused."""
        assert guard_no_psutil._state == GuardState.ERROR
        assert guard_no_psutil.can_accept_request() is False

    def test_initial_snapshot_taken(self, guard):
        """ResourceGuard takes a snapshot on init."""
        # Even if psutil isn't available, the init should not crash
        assert guard._current_ram_total_mb >= 0


# ============================================================================
# STATE TRANSITION TESTS
# ============================================================================

class TestStateTransitions:
    def test_disabled_state(self):
        g = ResourceGuard({"enabled": False})
        assert g._state == GuardState.DISABLED
        assert g.can_accept_request() is False

    def test_error_state_when_no_psutil(self):
        with patch('resource_guard.HAS_PSUTIL', False):
            g = ResourceGuard({"enabled": True})
            assert g._state == GuardState.ERROR
            assert g.can_accept_request() is False

    def test_manual_pause(self, guard):
        guard.pause()
        assert guard._state == GuardState.PAUSED

    def test_manual_resume(self, guard):
        guard.pause()
        assert guard._state == GuardState.PAUSED
        guard.resume()
        assert guard._state == GuardState.ACTIVE

    def test_resume_sets_resume_time(self, guard):
        guard.pause()
        guard.resume()
        assert guard._resume_time is not None
        assert time.time() - guard._resume_time < 1.0

    def test_pause_sets_pause_time(self, guard):
        guard.pause()
        assert guard._pause_time is not None

    def test_update_state_paused_when_cpu_high(self, guard):
        """When CPU exceeds threshold, state should move to PAUSED."""
        # Simulate high CPU
        guard._cpu_samples = deque([85.0, 90.0, 88.0, 87.0, 86.0], maxlen=5)
        guard._current_cpu = 87.0
        guard._current_ram_percent = 50.0
        guard._state = GuardState.ACTIVE
        guard._update_state()
        assert guard._state == GuardState.PAUSED

    def test_update_state_throttled_when_cpu_approaching(self, guard):
        """When CPU is approaching threshold, state should be THROTTLED."""
        # CPU threshold for local_first = min(70, 30+40) = 70
        # 70% * 0.7 = 49% — throttle threshold
        guard._cpu_samples = deque([50.0, 51.0, 52.0, 50.0, 51.0], maxlen=5)
        guard._current_cpu = 51.0
        guard._current_ram_percent = 50.0
        guard._state = GuardState.ACTIVE
        guard._update_state()
        assert guard._state == GuardState.THROTTLED

    def test_update_state_active_when_resources_free(self, guard):
        """When resources are free, state should be ACTIVE."""
        guard._cpu_samples = deque([10.0, 15.0, 12.0, 14.0, 11.0], maxlen=5)
        guard._current_cpu = 12.0
        guard._current_ram_percent = 40.0
        guard._state = GuardState.PAUSED
        guard._update_state()
        assert guard._state == GuardState.ACTIVE

    def test_disabled_stays_disabled(self, guard):
        """DISABLED state should not change via _update_state."""
        guard._state = GuardState.DISABLED
        guard._cpu_samples = deque([5.0] * 5, maxlen=5)
        guard._current_ram_percent = 20.0
        guard._update_state()
        assert guard._state == GuardState.DISABLED

    def test_ram_over_90_pauses(self, guard):
        """RAM over 90% should pause sharing."""
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_percent = 92.0
        guard._current_ram_available_mb = 200.0
        guard._state = GuardState.ACTIVE
        guard._update_state()
        assert guard._state == GuardState.PAUSED

    def test_ram_approaching_limit_throttles(self, guard):
        """RAM at ~76.5% (85% of 90%) should throttle."""
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_percent = 80.0
        guard._current_ram_available_mb = 2000.0
        guard._state = GuardState.ACTIVE
        guard._update_state()
        assert guard._state == GuardState.THROTTLED


# ============================================================================
# CAN_ACCEPT_REQUEST TESTS
# ============================================================================

class TestCanAcceptRequest:
    def test_accepts_when_active_and_resources_free(self, guard):
        guard._state = GuardState.ACTIVE
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_percent = 40.0
        guard._current_ram_available_mb = 8000.0
        guard._last_user_activity = 0.0  # no user activity
        guard._resume_time = time.time() - 20  # past cooldown
        assert guard.can_accept_request() is True

    def test_rejects_when_disabled(self):
        g = ResourceGuard({"enabled": False})
        assert g.can_accept_request() is False

    def test_rejects_when_paused(self, guard):
        guard._state = GuardState.PAUSED
        assert guard.can_accept_request() is False

    def test_rejects_when_error(self, guard):
        guard._state = GuardState.ERROR
        assert guard.can_accept_request() is False

    def test_rejects_when_cpu_high(self, guard):
        guard._state = GuardState.ACTIVE
        guard._cpu_samples = deque([85.0] * 5, maxlen=5)
        guard._current_cpu = 85.0
        guard._current_ram_available_mb = 8000.0
        guard._last_user_activity = 0.0
        guard._resume_time = time.time() - 20
        assert guard.can_accept_request() is False

    def test_rejects_when_ram_low(self, guard):
        guard._state = GuardState.ACTIVE
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 100.0  # below 512MB reserve
        guard._current_ram_percent = 95.0
        guard._last_user_activity = 0.0
        guard._resume_time = time.time() - 20
        assert guard.can_accept_request() is False

    def test_rejects_oversized_prompt(self, guard):
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._resume_time = time.time() - 20
        # Prompt too long
        assert guard.can_accept_request(prompt_length=60000) is False

    def test_rejects_oversized_context(self, guard):
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._resume_time = time.time() - 20
        assert guard.can_accept_request(context_length=300000) is False

    def test_rejects_during_cooldown(self, guard):
        guard._state = GuardState.ACTIVE
        guard._resume_time = time.time() - 2  # only 2s ago, cooldown is 10s
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_ram_available_mb = 8000.0
        assert guard.can_accept_request() is False

    def test_accepts_after_cooldown(self, guard):
        guard._state = GuardState.ACTIVE
        guard._resume_time = time.time() - 15  # 15s ago, past 10s cooldown
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_ram_available_mb = 8000.0
        guard._current_cpu = 10.0
        guard._current_ram_percent = 40.0
        assert guard.can_accept_request() is True

    def test_rejects_when_user_active_local_first(self, guard):
        """local_first priority should reject when user is active."""
        guard._state = GuardState.ACTIVE
        guard.priority = "local_first"
        guard._last_user_activity = time.time() - 10  # active 10s ago
        guard._user_idle_threshold = 60.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_ram_available_mb = 8000.0
        guard._resume_time = time.time() - 20
        assert guard.can_accept_request() is False

    def test_accepts_when_user_idle_local_first(self, guard):
        """local_first should accept when user has been idle."""
        guard._state = GuardState.ACTIVE
        guard.priority = "local_first"
        guard._last_user_activity = time.time() - 120  # idle for 2 min
        guard._user_idle_threshold = 60.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._resume_time = time.time() - 20
        assert guard.can_accept_request() is True


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    def test_burst_limit(self, guard):
        """Should reject requests exceeding burst limit."""
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._resume_time = time.time() - 20

        accepted = 0
        rejected = 0
        for i in range(40):
            if guard.can_accept_request():
                accepted += 1
            else:
                rejected += 1

        assert accepted > 0, "Should accept some requests"
        assert rejected > 0, "Should reject burst after limit"
        assert accepted <= guard.MAX_BURST_REQUESTS

    def test_burst_window_reset(self, guard):
        """After the burst window, requests should be accepted again."""
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._resume_time = time.time() - 20

        # Fill up timestamps with old entries
        old_time = time.time() - 15  # 15s ago, outside the 10s window
        for _ in range(guard.MAX_BURST_REQUESTS):
            guard._request_timestamps.append(old_time)

        # Should still accept because old timestamps are outside window
        assert guard.can_accept_request() is True


# ============================================================================
# GET_AVAILABLE_RESOURCES TESTS
# ============================================================================

class TestGetAvailableResources:
    def test_returns_zero_when_disabled(self):
        g = ResourceGuard({"enabled": False})
        result = g.get_available_resources()
        assert result["ram_mb"] == 0
        assert result["cpu_available_percent"] == 0
        assert result["gpu"] is False
        assert result["can_accept"] is False

    def test_returns_zero_when_error(self):
        with patch('resource_guard.HAS_PSUTIL', False):
            g = ResourceGuard({"enabled": True})
            result = g.get_available_resources()
            assert result["ram_mb"] == 0
            assert result["can_accept"] is False

    def test_reports_available_resources(self, guard):
        guard._state = GuardState.ACTIVE
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._last_user_activity = 0.0

        result = guard.get_available_resources()
        assert result["ram_mb"] > 0
        assert result["cpu_available_percent"] > 0
        assert result["state"] == "active"

    def test_ram_capped_by_config(self, guard):
        """Available RAM should not exceed config limit."""
        guard._state = GuardState.ACTIVE
        guard.max_ram_share_mb = 1024
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 16000.0  # lots of free RAM
        guard._current_ram_percent = 30.0
        guard._last_user_activity = 0.0

        result = guard.get_available_resources()
        assert result["ram_mb"] <= 1024

    def test_ram_capped_by_50_percent_free(self, guard):
        """Available RAM should not exceed 50% of actually free."""
        guard._state = GuardState.ACTIVE
        guard.max_ram_share_mb = 8192  # high config limit
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 3000.0  # 3GB free
        guard._current_ram_percent = 40.0
        guard._last_user_activity = 0.0

        result = guard.get_available_resources()
        # Should be capped at 50% of 3000 = 1500
        assert result["ram_mb"] <= 1500


# ============================================================================
# GET_STATUS TESTS
# ============================================================================

class TestGetStatus:
    def test_returns_full_status(self, guard):
        status = guard.get_status()
        assert "state" in status
        assert "enabled" in status
        assert "current_cpu_percent" in status
        assert "current_ram_percent" in status
        assert "current_ram_available_mb" in status
        assert "max_cpu_percent" in status
        assert "max_ram_share_mb" in status
        assert "requests_served" in status
        assert "requests_rejected" in status

    def test_tracks_request_counts(self, guard):
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._resume_time = time.time() - 20

        initial_served = guard._total_requests_served

        result = guard.can_accept_request()  # should be accepted
        assert result is True

        status = guard.get_status()
        assert status["requests_served"] == initial_served + 1

        # Now pause and test rejection tracking
        guard._state = GuardState.PAUSED
        initial_rejected = guard._total_requests_rejected

        result = guard.can_accept_request()  # should be rejected
        assert result is False

        status = guard.get_status()
        assert status["requests_rejected"] == initial_rejected + 1


# ============================================================================
# UPDATE_CONFIG TESTS
# ============================================================================

class TestUpdateConfig:
    def test_update_cpu(self, guard):
        guard.update_config({"max_cpu_percent": 50.0})
        assert guard.max_cpu_percent == 50.0

    def test_update_ram(self, guard):
        guard.update_config({"max_ram_share_mb": 4096})
        assert guard.max_ram_share_mb == 4096

    def test_update_clamps_high(self, guard):
        guard.update_config({"max_cpu_percent": 99.0})
        assert guard.max_cpu_percent == 80.0  # hard cap

    def test_disable_via_config(self, guard):
        guard.update_config({"enabled": False})
        assert guard.enabled is False
        assert guard._state == GuardState.DISABLED

    def test_re_enable_via_config(self, guard):
        guard.update_config({"enabled": False})
        assert guard._state == GuardState.DISABLED
        guard.update_config({"enabled": True})
        assert guard.enabled is True
        assert guard._state == GuardState.PAUSED  # resumes to paused, not active


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    def test_100_percent_cpu_at_startup(self):
        """If CPU is 100% at startup, should not crash and should refuse requests."""
        with patch('resource_guard.psutil') as mock_psutil:
            mock_psutil.cpu_percent.return_value = 100.0
            mock_psutil.virtual_memory.return_value = MagicMock(
                percent=95.0, available=500*1024*1024, total=8*1024*1024*1024
            )
            mock_psutil.pids.return_value = []
            mock_psutil.cpu_count.return_value = 4

            g = ResourceGuard({"enabled": True})
            g._cpu_samples = deque([100.0] * 5, maxlen=5)
            g._current_cpu = 100.0
            g._current_ram_percent = 95.0
            g._current_ram_available_mb = 500.0
            g._last_user_activity = 0.0
            g._resume_time = time.time() - 20

            # Should refuse requests
            assert g.can_accept_request() is False

    def test_empty_cpu_samples(self, guard):
        """Empty CPU samples should default to 0 (no CPU usage)."""
        guard._cpu_samples = deque(maxlen=5)
        assert guard._get_avg_cpu() == 0.0

    def test_concurrent_access(self, guard):
        """Thread-safety: multiple threads should not cause crashes."""
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._resume_time = time.time() - 20

        results = []

        def check():
            r = guard.can_accept_request()
            results.append(r)

        threads = [threading.Thread(target=check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not crash, results should be True or False
        assert len(results) == 20
        assert all(isinstance(r, bool) for r in results)

    def test_snapshot_failure_sets_error(self, guard):
        """If psutil snapshot fails, state should go to ERROR."""
        with patch('resource_guard.psutil') as mock_psutil:
            mock_psutil.cpu_percent.side_effect = RuntimeError("psutil broken")
            # The snapshot should handle the error
            guard._take_snapshot()
            assert guard._state == GuardState.ERROR

    def test_negative_ram_available(self, guard):
        """Negative available RAM should be handled gracefully."""
        guard._current_ram_available_mb = -100.0
        result = guard.get_available_resources()
        assert result["ram_mb"] == 0

    def test_user_activity_never_detected(self, guard):
        """If no user activity was ever detected, should not block."""
        guard._last_user_activity = 0.0
        assert guard._is_user_active() is False

    def test_user_activity_recently_detected(self, guard):
        """Recent user activity should block in local_first mode."""
        guard._last_user_activity = time.time() - 5  # 5 seconds ago
        guard._user_idle_threshold = 60.0
        assert guard._is_user_active() is True

    def test_user_activity_long_ago(self, guard):
        """User activity from long ago should not block."""
        guard._last_user_activity = time.time() - 300  # 5 minutes ago
        guard._user_idle_threshold = 60.0
        assert guard._is_user_active() is False


# ============================================================================
# ASYNC LIFECYCLE TESTS
# ============================================================================

class TestAsyncLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_stop(self, guard):
        """Start and stop should work without errors."""
        if not HAS_PSUTIL:
            pytest.skip("psutil not available")
        await guard.start()
        assert guard._running is True
        await guard.stop()
        assert guard._running is False

    @pytest.mark.asyncio
    async def test_double_start(self, guard):
        """Double start should be idempotent."""
        if not HAS_PSUTIL:
            pytest.skip("psutil not available")
        await guard.start()
        await guard.start()  # should not crash
        await guard.stop()

    @pytest.mark.asyncio
    async def test_disabled_does_not_start(self):
        """Disabled guard should not start monitoring."""
        g = ResourceGuard({"enabled": False})
        await g.start()
        assert g._monitor_task is None
        assert g._running is False


# ============================================================================
# DO / INJECTION PROTECTION
# ============================================================================

class TestDoSProtection:
    def test_reject_massive_prompt(self, guard):
        """Extremely large prompts should be rejected."""
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_ram_available_mb = 8000.0
        guard._resume_time = time.time() - 20

        assert guard.can_accept_request(prompt_length=1_000_000) is False

    def test_reject_massive_context(self, guard):
        """Extremely large context should be rejected."""
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_ram_available_mb = 8000.0
        guard._resume_time = time.time() - 20

        assert guard.can_accept_request(context_length=500_000) is False

    def test_normal_sized_requests_pass(self, guard):
        """Normal-sized requests should pass size checks."""
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._resume_time = time.time() - 20

        assert guard.can_accept_request(prompt_length=100, context_length=500) is True

    def test_burst_protection(self, guard):
        """Burst rate limiting should prevent DoS."""
        guard._state = GuardState.ACTIVE
        guard._last_user_activity = 0.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._resume_time = time.time() - 20

        accepted = 0
        for _ in range(50):
            if guard.can_accept_request(prompt_length=100):
                accepted += 1

        assert accepted <= guard.MAX_BURST_REQUESTS


# ============================================================================
# HARD LIMIT TESTS
# ============================================================================

class TestHardLimits:
    def test_cpu_hard_cap_80(self):
        """max_cpu_percent cannot exceed 80%."""
        g = ResourceGuard({"enabled": True, "max_cpu_percent": 95.0})
        assert g.max_cpu_percent == 80.0

    def test_cpu_minimum_5(self):
        """max_cpu_percent cannot go below 5%."""
        g = ResourceGuard({"enabled": True, "max_cpu_percent": 0.5})
        assert g.max_cpu_percent == 5.0

    def test_ram_hard_cap_16gb(self):
        """max_ram_share_mb cannot exceed 16GB."""
        g = ResourceGuard({"enabled": True, "max_ram_share_mb": 100000})
        assert g.max_ram_share_mb == 16384

    def test_ram_minimum_256mb(self):
        """max_ram_share_mb cannot go below 256MB."""
        g = ResourceGuard({"enabled": True, "max_ram_share_mb": 100})
        assert g.max_ram_share_mb == 256

    def test_total_ram_90_percent_hard_limit(self, guard):
        """Should refuse if total RAM usage > 90%, regardless of config."""
        guard._state = GuardState.ACTIVE
        guard._current_ram_percent = 91.0
        guard._current_ram_available_mb = 500.0
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._last_user_activity = 0.0
        guard._resume_time = time.time() - 20

        assert guard.can_accept_request() is False

    def test_512mb_reserve_hard_limit(self, guard):
        """Should refuse if available RAM < 512MB, regardless of config."""
        guard._state = GuardState.ACTIVE
        guard._current_ram_percent = 50.0
        guard._current_ram_available_mb = 300.0  # < 512MB
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._last_user_activity = 0.0
        guard._resume_time = time.time() - 20

        # 300MB < max(512MB reserve, 2048MB config) = 2048MB
        assert guard.can_accept_request() is False


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    def test_full_lifecycle(self, guard):
        """Test full lifecycle: start → accept → load → pause → recover → accept."""
        # Initially active with low load
        guard._state = GuardState.ACTIVE
        guard._cpu_samples = deque([10.0] * 5, maxlen=5)
        guard._current_cpu = 10.0
        guard._current_ram_available_mb = 8000.0
        guard._current_ram_percent = 40.0
        guard._last_user_activity = 0.0
        guard._resume_time = time.time() - 20

        # Should accept
        assert guard.can_accept_request() is True

        # Simulate load spike
        guard._cpu_samples = deque([85.0] * 5, maxlen=5)
        guard._current_cpu = 85.0
        guard._current_ram_percent = 92.0
        guard._update_state()
        assert guard._state == GuardState.PAUSED

        # Should reject
        assert guard.can_accept_request() is False

        # Resources recover
        guard._cpu_samples = deque([15.0] * 5, maxlen=5)
        guard._current_cpu = 15.0
        guard._current_ram_available_mb = 6000.0
        guard._current_ram_percent = 40.0
        guard._update_state()
        assert guard._state == GuardState.ACTIVE

    def test_config_cannot_bypass_hard_limits(self):
        """Even with malicious config, hard limits hold."""
        evil_config = {
            "enabled": True,
            "max_cpu_percent": 100.0,  # try to use 100% CPU
            "max_ram_share_mb": 999999,  # try to share all RAM
        }
        g = ResourceGuard(evil_config)
        assert g.max_cpu_percent == 80.0  # clamped to hard cap
        assert g.max_ram_share_mb == 16384  # clamped to hard cap

    def test_get_status_completes(self, guard):
        """get_status should always return valid dict."""
        status = guard.get_status()
        assert isinstance(status, dict)
        assert "state" in status
        assert "enabled" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])