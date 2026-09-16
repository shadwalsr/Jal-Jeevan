package com.jaljeev.marine

import com.jaljeev.marine.data.remote.ChatResponse
import com.jaljeev.marine.data.remote.FusedMarineState
import com.jaljeev.marine.data.remote.QuickCheckResult
import com.jaljeev.marine.domain.RiskLevel
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Contract tests against real backend response shapes.
 *
 * These exist because the app's models are hand-mirrored from
 * backend/app/models/schemas.py: if a field is renamed on the server, the
 * failure mode without these tests is a silently defaulted value on a safety
 * screen, which is exactly the class of bug this project refuses to ship.
 */
class WireContractTest {

    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    @Test
    fun `absent measurements stay null rather than defaulting to zero`() {
        val payload = """
        {
          "lat": 17.65, "lon": 83.35, "queried_at": "2026-08-27T04:00:00Z",
          "weather": {"wind_speed_ms": 6.2, "missing": ["visibility"]},
          "ocean": {"significant_wave_height_m": 0.9},
          "geo": {"depth_m": 48.0, "inside_indian_eez": true},
          "risk": {"risk_score": 18, "risk_level": "LOW", "factor_breakdown": {"wind": 8},
                   "explanation": ["wind 6.2 m/s -> +8"]},
          "confidence_note": "All queried sources responded successfully."
        }
        """.trimIndent()

        val state = json.decodeFromString<FusedMarineState>(payload)

        assertEquals(6.2, state.weather.windSpeedMs!!, 1e-9)
        // The source did not report gusts. That must remain "unknown", never 0.
        assertNull(state.weather.windGustMs)
        assertNull(state.ocean.tideHeightM)
        assertEquals(listOf("visibility"), state.weather.missing)
        assertEquals(RiskLevel.Low, RiskLevel.from(state.risk.riskLevel))
    }

    @Test
    fun `a vetoed point parses as REJECTED with no factor breakdown`() {
        val payload = """
        {
          "lat": 19.8, "lon": 85.83, "maps_url": "https://maps.google.com/?q=19.8,85.83",
          "checked_at": "2026-08-27T04:00:00Z",
          "risk_score": 0, "risk_level": "REJECTED", "vetoed": true,
          "reasons": ["Depth 0.0 m is below the vessel draft of 0.6 m"],
          "explanation": [], "insufficient_confidence": false
        }
        """.trimIndent()

        val result = json.decodeFromString<QuickCheckResult>(payload)
        val level = RiskLevel.from(result.riskLevel)

        assertTrue(result.vetoed)
        assertTrue(level.isVeto)
        assertFalse(level.isScored) // a veto has no meaningful score to render
        assertTrue(level.isUnsafe)
        assertEquals(1, result.reasons.size)
    }

    @Test
    fun `chat response carries the evidence receipt and session id`() {
        val payload = """
        {
          "answer": "Conditions are workable 20 km east of Visakhapatnam.",
          "trace": ["parse_intent", "resolve_location", "execute_tools"],
          "data": {"risk": {"risk_level": "LOW"}},
          "evidence": {
            "recommendation_summary": "LOW risk at 17.65, 83.35",
            "risk_score": 18, "risk_level": "LOW",
            "factor_lines": ["wind 6.2 m/s -> +8"],
            "sources_used": ["Open-Meteo", "Copernicus Marine"],
            "data_gaps": ["IMD nowcast unavailable"],
            "confidence_statement": "Partial data.",
            "location_lat": 17.65, "location_lon": 83.35
          },
          "decision_id": "d-123", "session_id": "abc123"
        }
        """.trimIndent()

        val response = json.decodeFromString<ChatResponse>(payload)

        assertEquals("abc123", response.sessionId)
        assertFalse(response.evidence.isEmpty)
        assertEquals(listOf("IMD nowcast unavailable"), response.evidence.dataGaps)
        assertEquals(17.65, response.evidence.locationLat!!, 1e-9)
    }

    @Test
    fun `an empty receipt is recognised so the UI can omit the card`() {
        val payload = """
        {"answer": "Hello.", "trace": [], "data": {}, "evidence": {},
         "decision_id": "d-1", "session_id": "s-1"}
        """.trimIndent()

        val response = json.decodeFromString<ChatResponse>(payload)
        assertTrue(response.evidence.isEmpty)
    }

    @Test
    fun `unknown risk levels degrade to Unknown instead of throwing`() {
        assertEquals(RiskLevel.Unknown, RiskLevel.from("SOMETHING_NEW"))
        assertEquals(RiskLevel.Unknown, RiskLevel.from(null))
        assertEquals(RiskLevel.InsufficientData, RiskLevel.from("INSUFFICIENT_DATA"))
    }
}
