"""
Decision persistence — readiness audit item 4. Writes every recommendation
to the (previously unused) `decisions` table, matching the PRD's own
"Decision ID" / audit-trail concept (Section 25): every answer should be
traceable back to the exact inputs and timestamp that produced it. Without
this there is no history, and no way to later build the prediction-
verification loop the PRD describes (Section 11) — compare what was
predicted against what actually happened.

Best-effort: a logging failure must never break the response the user is
waiting on, so every error here is swallowed after being reported.
"""
import json
import secrets
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.session import async_session


def new_decision_id() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"JALJEEV-{date_part}-{secrets.token_hex(3).upper()}"


async def save_decision(
    decision_id: str,
    query_text: str,
    response: dict,
    confidence: float | None = None,
    risk_tier: str | None = None,
) -> None:
    try:
        async with async_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO decisions (decision_id, query_text, response_json, confidence, risk_tier)
                    VALUES (:decision_id, :query_text, CAST(:response_json AS jsonb), :confidence, :risk_tier)
                    ON CONFLICT (decision_id) DO NOTHING
                    """
                ),
                {
                    "decision_id": decision_id,
                    "query_text": query_text,
                    "response_json": json.dumps(response, default=str),
                    "confidence": confidence,
                    "risk_tier": risk_tier,
                },
            )
            await session.commit()
    except Exception as exc:  # pragma: no cover - persistence is best-effort
        print(f"[decisions] failed to persist {decision_id}: {exc}")
