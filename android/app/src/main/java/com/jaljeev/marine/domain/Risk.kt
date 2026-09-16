package com.jaljeev.marine.domain

import androidx.compose.ui.graphics.Color

/**
 * The two-stage decision pipeline, as a UI type.
 *
 * REJECTED is deliberately NOT "a very high score" here, and must never be
 * rendered as one. It is the outcome of Stage 1 (check_hard_constraints in
 * backend/app/agents/risk_agent.py): a legal or physical veto that
 * short-circuits before scoring ever runs, which is why a REJECTED result
 * arrives with an empty factor_breakdown. Collapsing it into the same visual
 * scale as a scored 90/100 would undo exactly the bug that pipeline was
 * built to fix, so [Rejected] gets its own colour, its own label, and shows
 * veto reasons instead of factor points.
 */
enum class RiskLevel(val wire: String, val label: String, val color: Color) {
    Low("LOW", "Low risk", Color(0xFF3ECFA8)),
    Moderate("MODERATE", "Moderate risk", Color(0xFFD9C94F)),
    High("HIGH", "High risk", Color(0xFFE3A53D)),
    Extreme("EXTREME", "Extreme risk", Color(0xFFE3675A)),
    Rejected("REJECTED", "Not permitted / not survivable", Color(0xFFD6455D)),
    InsufficientData("INSUFFICIENT_DATA", "Not enough data", Color(0xFF8FA3B8)),
    Unknown("", "Unknown", Color(0xFF8FA3B8));

    /** A veto is categorical: no score is meaningful, so none is shown. */
    val isVeto: Boolean get() = this == Rejected

    val isScored: Boolean get() = this == Low || this == Moderate || this == High || this == Extreme

    val isUnsafe: Boolean get() = this == High || this == Extreme || this == Rejected

    companion object {
        fun from(wire: String?): RiskLevel =
            entries.firstOrNull { it.wire.equals(wire?.trim(), ignoreCase = true) } ?: Unknown
    }
}

/**
 * Colour for a bare 0-100 score with no level attached (route waypoints).
 * Thresholds match the web client's riskColor() in frontend/src/MarineMap.tsx
 * so the two front-ends can never disagree about what "amber" means.
 */
fun riskColorForScore(score: Int): Color = when {
    score >= 75 -> RiskLevel.Extreme.color
    score >= 50 -> RiskLevel.High.color
    score >= 25 -> RiskLevel.Moderate.color
    else -> RiskLevel.Low.color
}
