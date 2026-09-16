import { useEffect, useState } from "react";
import ChatPanel from "./ChatPanel";
import MarineMap from "./MarineMap";
import EvidencePanel from "./EvidencePanel";
import SafetyMonitor from "./SafetyMonitor";
import VesselSelector from "./VesselSelector";
import PassagePanel from "./PassagePanel";
import {
  getOptimizedRoute,
  getPassagePlan,
  type OptimizedRoute,
  type PassagePlan,
} from "./api";
import "./app.css";

// Verified real demo point — 15km offshore Visakhapatnam. Puri's exact
// coastline sits on a genuinely very shallow river-delta shelf and will
// correctly hit the draft-vs-depth veto (see CLAUDE.md gotcha #8).
const DEFAULT_LAT = 17.65;
const DEFAULT_LON = 83.35;

type LocationStatus = "requesting" | "granted" | "denied" | "unsupported";

export default function App() {
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lon, setLon] = useState(DEFAULT_LON);
  const [route, setRoute] = useState<OptimizedRoute | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  // Null means "the backend default" (the original 8m fishing boat) rather
  // than a class this UI picked — see api.ts on why it is omitted from the
  // request rather than sent as an empty string.
  const [vesselClass, setVesselClass] = useState<string | null>(null);
  const [passage, setPassage] = useState<PassagePlan | null>(null);
  const [passageLoading, setPassageLoading] = useState(false);
  const [passageError, setPassageError] = useState<string | null>(null);
  const [clientLocation, setClientLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [locationStatus, setLocationStatus] = useState<LocationStatus>("requesting");
  // Lives here, not inside ChatPanel: the reopen tab has to sit on a plain
  // (untransformed) ancestor. .chat-dock carries `transform: translateX(...)`
  // for centring, and a CSS transform on an ancestor becomes the containing
  // block for any position:fixed descendant — so a reopen tab nested inside
  // the dock could not reliably anchor to the viewport. Rendering it here,
  // as a sibling of .chat-dock under the untransformed .app-shell, sidesteps
  // that entirely.
  const [chatOpen, setChatOpen] = useState(true);

  // Ask for location once, on load — this is what lets a question like
  // "where can I go to fish?" (no place named) resolve against where the
  // user actually is, instead of going unanswered (see ChatPanel/api.ts
  // client_lat/client_lon and graph.py's resolve_location fallback).
  // Best-effort only: a denial or an unsupported browser just means that
  // one convenience is unavailable — everything else still works exactly
  // as before by naming a place in the chat.
  useEffect(() => {
    if (!("geolocation" in navigator)) {
      setLocationStatus("unsupported");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setClientLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setLocationStatus("granted");
      },
      () => setLocationStatus("denied"),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
    );
  }, []);

  async function handleFindRoute() {
    setRouteLoading(true);
    setRouteError(null);
    try {
      const result = await getOptimizedRoute(lat, lon, 25, vesselClass ?? undefined);
      // A radial route and a passage answer different questions; showing
      // both at once would leave the map ambiguous about which path is
      // being recommended.
      setPassage(null);
      setRoute(result);
    } catch (err) {
      setRouteError(err instanceof Error ? err.message : String(err));
    } finally {
      setRouteLoading(false);
    }
  }

  async function handlePlanPassage(destinationName: string) {
    setPassageLoading(true);
    setPassageError(null);
    try {
      const result = await getPassagePlan(
        { lat, lon },
        destinationName,
        vesselClass ?? undefined
      );
      setRoute(null);
      setPassage(result);
    } catch (err) {
      setPassageError(err instanceof Error ? err.message : String(err));
    } finally {
      setPassageLoading(false);
    }
  }

  const hasEvidence = route !== null || passage !== null;

  return (
    <div className="app-shell">
      {/* The map is the page, not a panel on it. */}
      <div className="map-layer">
        <MarineMap lat={lat} lon={lon} route={passage ?? route} />
      </div>

      <div className="header-strip surface">
        <img className="header-strip__logo" src="/logo-mark.svg" alt="" width={24} height={24} />
        <span className="header-strip__name">Jal Jeevan</span>
        <span className="header-strip__divider" />
        <span className="header-strip__coords mono">
          {lat.toFixed(4)}, {lon.toFixed(4)}
        </span>
      </div>

      {/* Slides clear of the evidence panel when it is present. */}
      <div className="top-controls" style={{ right: hasEvidence ? 392 : 16 }}>
        <div>
          <button className="btn" onClick={handleFindRoute} disabled={routeLoading}>
            {routeLoading ? "Routing…" : "Find safest route"}
          </button>
          {routeError && (
            <div className="safety-readout surface safety-readout__error">{routeError}</div>
          )}
        </div>
        {/* Changing the vessel invalidates any result on screen: the same
            water produces a genuinely different verdict for a different
            hull, so keeping the old path visible would misattribute it. */}
        <VesselSelector
          value={vesselClass}
          onChange={(next) => {
            setVesselClass(next);
            setRoute(null);
            setPassage(null);
          }}
        />
        <PassagePanel
          planning={passageLoading}
          onPlan={handlePlanPassage}
          error={passageError}
        />
        <SafetyMonitor />
      </div>

      <div className="chat-dock">
        <ChatPanel
          clientLocation={clientLocation}
          locationStatus={locationStatus}
          open={chatOpen}
          onRequestClose={() => setChatOpen(false)}
          onLocationResolved={(la, lo) => {
            setLat(la);
            setLon(lo);
            setRoute(null);
            setPassage(null);
          }}
        />
      </div>

      {/* Mounted only while closed — a plain entrance animation is enough
          here, since there is nothing to slide back FROM (the widget it
          reopens does its own slide-up). */}
      {!chatOpen && (
        <button className="btn chat-reopen surface" onClick={() => setChatOpen(true)}>
          Show chat
        </button>
      )}

      {hasEvidence && <EvidencePanel route={route} passage={passage} />}
    </div>
  );
}
