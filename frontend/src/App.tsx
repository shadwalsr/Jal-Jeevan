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

import { LanguageProvider, useLanguage } from "./i18n/LanguageContext";
import { LanguageSelector } from "./LanguageSelector";
import "./app.css";

// Default map centre — Indian coastal waters
const DEFAULT_LAT = 12.5;
const DEFAULT_LON = 75.0;

type LocationStatus = "requesting" | "granted" | "denied" | "unsupported";

function AppContent() {
  const { t } = useLanguage();
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lon, setLon] = useState(DEFAULT_LON);
  const [route, setRoute] = useState<OptimizedRoute | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  // Null means "the backend default" (the original 8m fishing boat) rather
  // than a class this UI picked
  const [vesselClass, setVesselClass] = useState<string | null>(null);
  const [passage, setPassage] = useState<PassagePlan | null>(null);
  const [passageLoading, setPassageLoading] = useState(false);
  const [passageError, setPassageError] = useState<string | null>(null);
  const [clientLocation, setClientLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [locationStatus, setLocationStatus] = useState<LocationStatus>("requesting");
  const [chatOpen, setChatOpen] = useState(true);

  // Ask for location once, on load
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
        <span className="header-strip__name">{t("app_name")}</span>
        <span className="header-strip__divider" />
        <span className="header-strip__coords mono">
          {lat.toFixed(4)}, {lon.toFixed(4)}
        </span>
        <span className="header-strip__divider" />

        <span className="header-strip__divider" />
        <LanguageSelector />
      </div>

      {/* Slides clear of the evidence panel when it is present. */}
      <div className="top-controls" style={{ right: hasEvidence ? 392 : 16 }}>
        <div className="top-controls__row">
          <button className="btn btn--primary" onClick={handleFindRoute} disabled={routeLoading}>
            {routeLoading ? t("routing") : t("find_safest_route")}
          </button>
          <SafetyMonitor />
        </div>
        {routeError && (
          <div className="safety-readout surface safety-readout__error">{routeError}</div>
        )}
        <div className="top-controls__panels">
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
        </div>
      </div>

      <div className="chat-dock">
        <ChatPanel
          clientLocation={clientLocation ?? { lat, lon }}
          locationStatus={locationStatus}
          open={chatOpen}
          onRequestClose={() => setChatOpen(false)}
          onLocationResolved={(la, lo) => {
            setLat(la);
            setLon(lo);
            setRoute(null);
            setPassage(null);
          }}
          onPassageResolved={(p) => {
            setRoute(null);
            setPassage(p);
            setLat(p.origin_lat);
            setLon(p.origin_lon);
          }}
        />
      </div>

      {!chatOpen && (
        <button className="btn chat-reopen surface" onClick={() => setChatOpen(true)}>
          {t("show_chat")}
        </button>
      )}

      {hasEvidence && <EvidencePanel route={route} passage={passage} />}
    </div>
  );
}

export default function App() {
  return (
    <LanguageProvider>
      <AppContent />
    </LanguageProvider>
  );
}
