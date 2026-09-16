"""Tests for the minimal circuit breaker (app/tools/_circuit_breaker.py)."""
import time

from app.tools import _circuit_breaker as cb


def setup_function():
    cb._state.clear()


def test_closed_by_default():
    assert cb.is_open("test-source") is False


def test_opens_after_threshold_failures():
    for _ in range(cb.FAILURE_THRESHOLD):
        cb.record_failure("test-source")
    assert cb.is_open("test-source") is True


def test_stays_closed_below_threshold():
    for _ in range(cb.FAILURE_THRESHOLD - 1):
        cb.record_failure("test-source")
    assert cb.is_open("test-source") is False


def test_success_resets_failure_count():
    for _ in range(cb.FAILURE_THRESHOLD - 1):
        cb.record_failure("test-source")
    cb.record_success("test-source")
    assert cb._state["test-source"]["failures"] == 0
    assert cb.is_open("test-source") is False


def test_reopens_closed_after_cooldown_elapses(monkeypatch):
    for _ in range(cb.FAILURE_THRESHOLD):
        cb.record_failure("test-source")
    assert cb.is_open("test-source") is True

    # Simulate cooldown having elapsed without a real sleep
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + cb.COOLDOWN_S + 1)
    assert cb.is_open("test-source") is False
