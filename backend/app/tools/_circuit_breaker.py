"""
Minimal circuit breaker for external adapters (readiness-audit item). Before
this, a source that was already failing got hit again on the very next
request with no backoff — directly contributed to the Copernicus slowdowns
observed during development (repeated logins to an already-struggling
service). Per-adapter, in-memory, process-local — fine for a single-process
deployment; would need a shared store (Redis) for multi-worker.

Usage: wrap a call site, not the adapter's public function signature, so
callers don't need to change:

    if circuit_breaker.is_open("copernicus"):
        return {"status": "unavailable", "reason": "circuit breaker open — too many recent failures"}
    try:
        result = await do_the_call()
        circuit_breaker.record_success("copernicus")
        return result
    except Exception:
        circuit_breaker.record_failure("copernicus")
        raise
"""
import time

FAILURE_THRESHOLD = 3  # consecutive failures before opening
COOLDOWN_S = 60  # how long the breaker stays open before allowing a retry

_state: dict[str, dict] = {}


def _get(name: str) -> dict:
    return _state.setdefault(name, {"failures": 0, "opened_at": None})


def is_open(name: str) -> bool:
    s = _get(name)
    if s["opened_at"] is None:
        return False
    if time.time() - s["opened_at"] >= COOLDOWN_S:
        # Cooldown elapsed — allow one attempt through (half-open); a
        # failure will re-open it, a success resets it via record_success.
        return False
    return True


def record_success(name: str) -> None:
    _state[name] = {"failures": 0, "opened_at": None}


def record_failure(name: str) -> None:
    s = _get(name)
    s["failures"] += 1
    if s["failures"] >= FAILURE_THRESHOLD and s["opened_at"] is None:
        s["opened_at"] = time.time()
