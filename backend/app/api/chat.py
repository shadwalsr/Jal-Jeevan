"""
/chat — the conversational front door (PRD Section 1). Thin wrapper around
the LangGraph planner; all the real work happens in app/planner/graph.py
and the deterministic agents it calls.
"""
import asyncio
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.core.decisions import new_decision_id, save_decision
from app.planner.graph import run_planner

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # omit on the first message; reuse the returned one for follow-ups
    # Browser geolocation (navigator.geolocation), when the user has granted
    # it — used as a LAST-RESORT location fallback (see resolve_location in
    # graph.py): a place named in the message, or a place established
    # earlier in this same session, still wins. This exists specifically
    # for "where can I go to fish?" with no place named at all — the
    # question this system is supposed to answer for someone already out on
    # the water, not just someone planning a trip from home.
    client_lat: float | None = None
    client_lon: float | None = None

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty")
        if len(v) > 2000:
            raise ValueError("message too long (max 2000 characters)")
        return v


class ChatResponse(BaseModel):
    answer: str
    trace: list[str]
    data: dict
    evidence: dict
    decision_id: str
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or secrets.token_hex(8)

    client_lat, client_lon = request.client_lat, request.client_lon
    if client_lat is not None and client_lon is not None:
        if not (-90 <= client_lat <= 90 and -180 <= client_lon <= 180):
            client_lat, client_lon = None, None  # malformed browser geolocation — ignore, don't fail the chat

    try:
        # Worst-case budget (28 Aug 2026), all three stages at their bounds:
        #   parse_intent   ~40s  (20s timeout + 1 retry, graph.py LLM_TIMEOUT_S)
        #   execute_tools  ~50s  (route_agent's 2 verification phases; the
        #                         expansion rings are scanned concurrently,
        #                         never one ring after another — see the
        #                         timing note on EXPANSION_GROWTH)
        #   synthesize     ~8s   (SYNTHESIS_LLM_TIMEOUT_S, no retry — the
        #                         rule-based renderer is an equally correct
        #                         answer, so waiting longer buys nothing)
        # ~98s, so 115s leaves headroom without letting a genuine hang sit
        # on the client forever. If this ceiling is ever hit again, find the
        # stage that blew its own bound rather than raising this number.
        result = await asyncio.wait_for(
            run_planner(request.message, session_id=session_id, client_lat=client_lat, client_lon=client_lon),
            timeout=115,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="The request took too long to process. Try again shortly.")

    decision_id = new_decision_id()
    tool_results = result.get("tool_results", {})
    risk_tier = None
    if isinstance(tool_results, dict):
        risk_tier = (tool_results.get("risk") or {}).get("risk_level") or (
            (tool_results.get("destination_risk") or {}).get("risk_level")
        )

    asyncio.create_task(
        save_decision(
            decision_id,
            query_text=request.message,
            response=result,
            confidence=None,
            risk_tier=risk_tier,
        )
    )

    return ChatResponse(
        answer=result.get("answer", ""),
        trace=result.get("trace", []),
        data=tool_results,
        evidence=result.get("evidence", {}),
        decision_id=decision_id,
        session_id=session_id,
    )
