"""
Shared per-agent timeout wrapper.

WHY THIS MODULE EXISTS (29 Aug 2026). This helper was originally a private
function inside app/api/marine.py, so only the REST endpoints were protected
by it. The /chat path (app/planner/graph.py::execute_tools) called the same
three agents through a bare `asyncio.gather(...)` with no timeout at all —
so a hung Copernicus fetch or a stalled Postgres connection made the planner
hang indefinitely, and the ONLY backstop was /chat's own 115s ceiling, which
fired and returned `504 The request took too long to process`.

Measured on the same coordinates (17.65, 83.35):
    /marine/state  -> HTTP 200 in 25.0s  (agent hit AGENT_TIMEOUT_S, degraded)
    /chat          -> hung past 300s     -> 504

Same agents, same data, opposite behaviour — purely because one path had the
timeout and the other did not. It lives here now so both callers import ONE
implementation, the same way check_hard_constraints is shared between the
risk, route and passage paths rather than being reimplemented per caller
(see CLAUDE.md's conventions, and gotcha #3 on why the ceiling has to be
per-agent rather than wrapped around the whole gather).
"""
import asyncio

# Per-agent ceiling, not a whole-request one. An earlier version wrapped the
# entire asyncio.gather() in one outer timeout — which meant one slow source
# (Copernicus, on a bad night) discarded fast, successful results from the
# other two agents as well, turning a partial-data situation into a total
# failure. Bounding each agent independently means a slow Ocean Agent
# degrades to "ocean data missing" while Weather/Geo still come back — the
# graceful-degradation behaviour the PRD actually asks for.
#
# 40s, not 25 (29 Aug 2026). Measured cold on a demo point: the Ocean Agent
# completes in ~33s and comes back with real wave height, SST, salinity and
# tide — but the old 25s ceiling cut it off at exactly 25.0s every time and
# this wrapper then returned an EMPTY OceanState, throwing away the
# Open-Meteo wave reading that had already succeeded in under a second.
# The endpoint looked healthy (HTTP 200, fast) while reporting "wave height
# missing" for data the system genuinely had. 40s clears the measured cold
# path with margin and still fits inside /chat's 115s budget alongside the
# LLM stages.
#
# NOTE the real shortcoming this exposes: on timeout we discard partial
# results instead of keeping whatever sources already answered. Raising the
# ceiling avoids it here rather than fixing it — the durable fix is for each
# agent to bound its own sub-sources and always return what it collected.
AGENT_TIMEOUT_S = 40


async def run_with_timeout(coro, agent_name: str, empty_state):
    """
    Await `coro`, but never longer than AGENT_TIMEOUT_S. On timeout return
    `empty_state` marked with an honest gap note rather than raising — a
    missing source is reported as missing (`missing: [...]`), never silently
    filled in and never allowed to take the whole request down with it.
    """
    try:
        return await asyncio.wait_for(coro, timeout=AGENT_TIMEOUT_S)
    except asyncio.TimeoutError:
        timeout_note = f"{agent_name} timed out after {AGENT_TIMEOUT_S}s"
        if hasattr(empty_state, "partial"):
            empty_state.partial = True
        empty_state.missing = [timeout_note]
        return empty_state
