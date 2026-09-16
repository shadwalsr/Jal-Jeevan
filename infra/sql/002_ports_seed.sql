-- Curated seed list of major Indian fishing harbours / ports.
-- Coordinates are approximate (harbour entrance), sourced from public
-- knowledge — NOT an authoritative dataset. Replace/expand with an
-- official Coast Guard or Ports Authority dataset when available.

CREATE TABLE IF NOT EXISTS ports (
    id      SERIAL PRIMARY KEY,
    name    TEXT NOT NULL,
    state   TEXT,
    lat     DOUBLE PRECISION NOT NULL,
    lon     DOUBLE PRECISION NOT NULL,
    geom    GEOMETRY(Point, 4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)) STORED
);

INSERT INTO ports (name, state, lat, lon) VALUES
    ('Puri', 'Odisha', 19.8135, 85.8312),
    ('Paradip', 'Odisha', 20.2648, 86.6947),
    ('Visakhapatnam', 'Andhra Pradesh', 17.6868, 83.2185),
    ('Kakinada', 'Andhra Pradesh', 16.9891, 82.2475),
    ('Chennai', 'Tamil Nadu', 13.0827, 80.2907),
    ('Nagapattinam', 'Tamil Nadu', 10.7661, 79.8420),
    ('Rameswaram', 'Tamil Nadu', 9.2876, 79.3129),
    ('Tuticorin', 'Tamil Nadu', 8.7642, 78.1348),
    ('Kochi', 'Kerala', 9.9312, 76.2673),
    ('Kollam', 'Kerala', 8.8932, 76.6141),
    ('Mangalore', 'Karnataka', 12.9141, 74.8560),
    ('Goa (Mormugao)', 'Goa', 15.4028, 73.7996),
    ('Mumbai', 'Maharashtra', 18.9220, 72.8347),
    ('Veraval', 'Gujarat', 20.9159, 70.3629),
    ('Porbandar', 'Gujarat', 21.6417, 69.6293),
    ('Kandla', 'Gujarat', 23.0333, 70.2167),
    ('Port Blair', 'Andaman & Nicobar', 11.6234, 92.7265)
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_ports_geom ON ports USING GIST (geom);
