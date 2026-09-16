-- JalJeev — initial schema (Phase 0 / Week 1)
-- Mirrors PRD Section 12. Extended with more tables as later phases land.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- USERS AND VESSEL PROFILES
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    language_code   CHAR(2) NOT NULL DEFAULT 'en',
    home_port_name  TEXT,
    home_port_lat   DOUBLE PRECISION,
    home_port_lon   DOUBLE PRECISION,
    alert_enabled   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS vessel_profiles (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID REFERENCES users(id) ON DELETE CASCADE,
    vessel_name             TEXT,
    vessel_class            TEXT NOT NULL,   -- 'small_fishing' | 'medium_trawler' | 'large_vessel'
    length_m                DOUBLE PRECISION,
    engine_hp               INTEGER,
    max_safe_wave_m         DOUBLE PRECISION,
    wind_threshold_ms       DOUBLE PRECISION,
    operational_range_km    DOUBLE PRECISION,
    draft_m                 DOUBLE PRECISION,
    fuel_efficiency         DOUBLE PRECISION,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- H3 MARINE STATE GRID (time-partitioned; upgrade to TimescaleDB hypertable when available)
CREATE TABLE IF NOT EXISTS h3_marine_states (
    cell_id                 TEXT NOT NULL,
    timestamp               TIMESTAMPTZ NOT NULL,
    sst_c                   DOUBLE PRECISION,
    chlorophyll_mg_m3       DOUBLE PRECISION,
    wave_height_m           DOUBLE PRECISION,
    wave_period_s           DOUBLE PRECISION,
    wind_speed_ms           DOUBLE PRECISION,
    current_speed_knots     DOUBLE PRECISION,
    tide_height_m           DOUBLE PRECISION,
    pfz_active              BOOLEAN,
    risk_score              DOUBLE PRECISION,
    sources_used            JSONB,
    PRIMARY KEY (cell_id, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_h3_marine_states_cell ON h3_marine_states (cell_id);
CREATE INDEX IF NOT EXISTS idx_h3_marine_states_time ON h3_marine_states (timestamp);

-- RAW INGESTION LOG (data provenance — PRD Section 8/9 principle)
CREATE TABLE IF NOT EXISTS ingestion_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          TEXT NOT NULL,
    variable        TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_time      TIMESTAMPTZ,
    status          TEXT NOT NULL,  -- 'success' | 'failed' | 'stale'
    detail          TEXT
);

-- QUERY / DECISION AUDIT TRAIL (evidence graph, PRD Section 8.9)
CREATE TABLE IF NOT EXISTS decisions (
    decision_id     TEXT PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    query_text      TEXT,
    response_json   JSONB,
    confidence      DOUBLE PRECISION,
    risk_tier       TEXT
);
