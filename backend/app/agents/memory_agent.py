"""
Context & Memory Agent (PRD Section 8). Redis-backed conversation memory,
scoped per session_id, TTL-bounded — a follow-up question ("what about
tomorrow?") can resolve location/vessel from earlier in the SAME
conversation without the user repeating themselves, but memory doesn't
persist forever or leak across unrelated sessions.

Deterministic storage, no LLM involved in the storage/retrieval itself —
only the planner's own intent-parsing step (already an LLM call) decides
HOW to use retrieved context; this agent just remembers and forgets.
"""
import json
from datetime import datetime, timezone

import redis.asyncio as redis

from app.core.config import settings

SESSION_TTL_S = 3600  # 1 hour conversation window
MAX_TURNS_KEPT = 10

_client: redis.Redis | None = None


def _get_client() -> redis.Redis | None:
    global _client
    if _client is not None:
        return _client
    if not settings.REDIS_URL:
        return None
    try:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        return _client
    except Exception:
        return None


def _key(session_id: str) -> str:
    return f"jaljeev:session:{session_id}"


async def get_history(session_id: str) -> list[dict]:
    client = _get_client()
    if client is None:
        return []
    try:
        raw = await client.get(_key(session_id))
        return json.loads(raw) if raw else []
    except Exception:  # pragma: no cover - memory is best-effort, never fatal
        return []


async def append_turn(
    session_id: str,
    user_message: str,
    resolved_lat: float | None = None,
    resolved_lon: float | None = None,
    location_name: str | None = None,
    intent_type: str | None = None,
) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        history = await get_history(session_id)
        history.append(
            {
                "user_message": user_message,
                "resolved_lat": resolved_lat,
                "resolved_lon": resolved_lon,
                "location_name": location_name,
                "intent_type": intent_type,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        history = history[-MAX_TURNS_KEPT:]
        await client.set(_key(session_id), json.dumps(history), ex=SESSION_TTL_S)
    except Exception:  # pragma: no cover - memory is best-effort, never fatal
        pass


async def get_last_location(session_id: str) -> dict | None:
    """Most recent turn in this session that actually resolved a location —
    what a follow-up question like 'what about tomorrow?' should reuse."""
    history = await get_history(session_id)
    for turn in reversed(history):
        if turn.get("resolved_lat") is not None and turn.get("resolved_lon") is not None:
            return {
                "lat": turn["resolved_lat"],
                "lon": turn["resolved_lon"],
                "location_name": turn.get("location_name"),
                "from_message": turn["user_message"],
            }
    return None
