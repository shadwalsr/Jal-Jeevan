import type { Feature } from "geojson";

// JalJeev API client — thin wrapper over the FastAPI backend.
// No fabricated data anywhere in this file: every function is a real HTTP
// call to a real endpoint built and verified during backend development.

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export interface ChatResponse {
  answer: string;
  trace: string[];
  data: Record<string, unknown>;
  evidence: EvidenceReceipt;
  decision_id: string;
  session_id: string;
}

export interface EvidenceReceipt {
  decision_id: string | null;
  recommendation_summary: string;
  risk_score: number | null;
  risk_level: string | null;
  factor_lines: string[];
  sources_used: string[];
  data_freshness: Record<string, string>;
  data_gaps: string[];
  rejected_alternatives: string[];
  confidence_statement: string;
  validation_note: string | null;
  location_lat: number | null;
  location_lon: number | null;
  location_maps_url: string | null;
}

export interface RouteWaypointRisk {
  lat: number;
  lon: number;
  risk_score: number;
}

export interface OptimizedRoute {
  origin_lat: number;
  origin_lon: number;
  found_route: boolean;
  reason: string | null;
  waypoints: RouteWaypointRisk[];
  destination_maps_url: string | null;
  total_risk_cost: number | null;
  cells_evaluated: number;
  cells_viable: number;
}

// ---------------------------------------------------------------------------
// Vessel classes (GET /marine/vessel-classes)
//
// Built from the backend registry rather than hardcoded here, so the classes
// this UI offers can never drift from the ones the risk engine actually
// knows how to score. Sending a class the backend doesn't recognise would
// silently fall back to an 8m fishing boat's thresholds — which for someone
// asking about a tanker is exactly the kind of quietly-wrong answer this
// project treats as worse than no answer.
// ---------------------------------------------------------------------------

export interface VesselClass {
  vessel_class: string;
  vessel_name: string;
  propulsion: "motor" | "sail" | "motor_sail";
  length_m: number;
  draft_m: number;
  max_safe_wave_m: number;
  wind_threshold_ms: number;
  operational_range_km: number;
  cruise_speed_kn: number;
  commercial: boolean;
}

export interface VesselClassesResponse {
  groups: Record<string, VesselClass[]>;
  note: string;
}

export function getVesselClasses(): Promise<VesselClassesResponse> {
  return getJSON<VesselClassesResponse>("/marine/vessel-classes", {});
}

export interface Port {
  name: string;
  state: string | null;
  lat: number;
  lon: number;
}

export function getPorts(): Promise<{ ports: Port[]; count: number }> {
  return getJSON<{ ports: Port[]; count: number }>("/marine/ports", {});
}

// ---------------------------------------------------------------------------
// Passage planning (GET /marine/passage)
//
// The sailor's and trader's primitive: get from port A to port B. Distinct
// from getOptimizedRoute, which searches outward from where you are (the
// fisherman's question) and has no destination at all.
// ---------------------------------------------------------------------------

export interface PassageLeg {
  from_lat: number;
  from_lon: number;
  to_lat: number;
  to_lon: number;
  bearing_deg: number;
  distance_nm: number;
  sailed_distance_nm: number;
  eta_hours_from_departure: number;
  risk_score: number;
  risk_level: string;
  forecast_hour_offset: number;
  beyond_forecast_horizon: boolean;
  must_tack: boolean;
  explanation: string[];
}

export interface DiversionPort {
  name: string;
  lat: number;
  lon: number;
  distance_km: number;
  from_leg_index: number;
}

export interface PassagePlan {
  origin_name: string | null;
  origin_lat: number;
  origin_lon: number;
  destination_name: string | null;
  destination_lat: number;
  destination_lon: number;
  vessel_class: string;
  vessel_name: string;
  found_route: boolean;
  reason: string | null;
  legs: PassageLeg[];
  waypoints: RouteWaypointRisk[];
  diversion_ports: DiversionPort[];
  direct_distance_nm: number | null;
  routed_distance_nm: number | null;
  sailed_distance_nm: number | null;
  total_eta_hours: number | null;
  max_leg_risk_score: number | null;
  max_leg_risk_level: string | null;
  h3_resolution: number | null;
  cells_evaluated: number;
  cells_viable: number;
  forecast_note: string | null;
  destination_maps_url: string | null;
}

export function getPassagePlan(
  origin: { lat: number; lon: number },
  destinationName: string,
  vesselClass?: string
): Promise<PassagePlan> {
  return getJSON<PassagePlan>("/marine/passage", {
    origin_lat: origin.lat,
    origin_lon: origin.lon,
    destination_name: destinationName,
    ...(vesselClass ? { vessel_class: vesselClass } : {}),
  });
}

export interface FusedMarineState {
  lat: number;
  lon: number;
  maps_url: string | null;
  queried_at: string;
  weather: Record<string, unknown>;
  ocean: Record<string, unknown>;
  geo: Record<string, unknown>;
  risk: {
    risk_score: number;
    risk_level: string;
    factor_breakdown: Record<string, number>;
    explanation: string[];
    hard_constraints: { vetoed: boolean; reasons: string[] };
  };
  validation: { valid: boolean; issues: string[] };
  confidence_note: string;
}

export interface QuickCheckResult {
  lat: number;
  lon: number;
  maps_url: string;
  checked_at: string;
  risk_score: number;
  risk_level: string;
  vetoed: boolean;
  reasons: string[];
  explanation: string[];
  insufficient_confidence: boolean;
  confidence_reason: string | null;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  return resp.json();
}

async function getJSON<T>(path: string, params: Record<string, string | number>): Promise<T> {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
  const resp = await fetch(`${API_BASE}${path}?${qs}`);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  return resp.json();
}

export function sendChat(
  message: string,
  sessionId?: string,
  clientLocation?: { lat: number; lon: number } | null
): Promise<ChatResponse> {
  return postJSON<ChatResponse>("/chat", {
    message,
    session_id: sessionId,
    client_lat: clientLocation?.lat,
    client_lon: clientLocation?.lon,
  });
}

// vesselClass is omitted rather than defaulted on every call: the backend
// treats an absent class as the original 8m fishing boat, and sending an
// empty string instead would be a class it has to reject.
export function getMarineState(
  lat: number,
  lon: number,
  vesselClass?: string
): Promise<FusedMarineState> {
  return getJSON<FusedMarineState>("/marine/state", {
    lat,
    lon,
    ...(vesselClass ? { vessel_class: vesselClass } : {}),
  });
}

export function getOptimizedRoute(
  lat: number,
  lon: number,
  rangeKm: number = 40,
  vesselClass?: string
): Promise<OptimizedRoute> {
  return getJSON<OptimizedRoute>("/marine/optimize-route", {
    lat,
    lon,
    range_km: rangeKm,
    ...(vesselClass ? { vessel_class: vesselClass } : {}),
  });
}

// Fast single-point safety check — see app/api/marine.py's /quick-check for
// why this is a separate, lighter endpoint than getMarineState: it's built
// to be polled every ~10s from a moving vessel's browser (SafetyMonitor.tsx)
// without repeatedly hitting Copernicus login or the DB pool.
export function getQuickCheck(
  lat: number,
  lon: number,
  vesselClass?: string
): Promise<QuickCheckResult> {
  return getJSON<QuickCheckResult>("/marine/quick-check", {
    lat,
    lon,
    ...(vesselClass ? { vessel_class: vesselClass } : {}),
  });
}

// ---------------------------------------------------------------------------
// Boundary layers (GET /map/boundaries)
//
// These are the Stage 1 exclusion layer: legal/physical boundaries that veto
// outright, as opposed to the risk field which scores what already passed.
// The map draws them hatched rather than filled so a boundary you crossed
// never looks like a number that got high.
// ---------------------------------------------------------------------------

export interface BoundaryFeatureCollection {
  type: "FeatureCollection";
  features: Feature[];
  unavailable?: string;
}

export interface BoundariesResponse {
  bbox: [number, number, number, number];
  simplify_tolerance_deg: number;
  eez?: BoundaryFeatureCollection;
  mpa?: BoundaryFeatureCollection;
  ports?: BoundaryFeatureCollection;
  coverage_note: string;
}

export function getBoundaries(
  minLat: number,
  minLon: number,
  maxLat: number,
  maxLon: number,
  types: string = "eez,mpa,ports"
): Promise<BoundariesResponse> {
  return getJSON<BoundariesResponse>("/map/boundaries", {
    min_lat: minLat,
    min_lon: minLon,
    max_lat: maxLat,
    max_lon: maxLon,
    types,
  });
}
