import { useEffect, useRef, useState } from "react";
import { getQuickCheck, type QuickCheckResult } from "./api";

// Live guide feature: "nothing is sure about when the parameters might
// change and it might put the user in danger" — once started, this polls
// the user's OWN current position (not a place they typed) every 10s and
// re-runs the same deterministic hard-constraint check used everywhere
// else in the system, so a fisherman already out on the water gets warned
// the moment conditions where they actually are turn unsafe, not just at
// the moment they asked.
const POLL_INTERVAL_MS = 10_000;
// Once already unsafe, don't fire a fresh OS notification on every single
// 10s tick — that would be alarm-fatigue noise, not a warning. Re-notify at
// most this often while the unsafe condition persists (still updates the
// in-page banner every tick regardless).
const RENOTIFY_INTERVAL_MS = 60_000;

type MonitorStatus = "idle" | "watching" | "error";

function isUnsafe(r: QuickCheckResult): boolean {
  return r.vetoed || r.risk_level === "HIGH" || r.risk_level === "EXTREME";
}

function reasonText(r: QuickCheckResult): string {
  const lines = r.vetoed ? r.reasons : r.explanation;
  return lines.length ? lines.join("; ") : "risk score crossed the safe threshold";
}

export default function SafetyMonitor() {
  const [status, setStatus] = useState<MonitorStatus>("idle");
  const [result, setResult] = useState<QuickCheckResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const intervalRef = useRef<number | null>(null);
  const wasUnsafeRef = useRef(false);
  const lastNotifiedAtRef = useRef(0);

  function notify(r: QuickCheckResult) {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    try {
      new Notification("⚠️ JalJeev — not safe to continue", {
        body: `${r.risk_level} (${r.risk_score}/100) at ${r.lat.toFixed(4)}, ${r.lon.toFixed(4)} — ${reasonText(r)}`,
        tag: "jaljeev-safety", // replaces any prior alert instead of stacking a new one every tick
      });
    } catch {
      // Notification constructor can throw in some contexts (e.g. no service
      // worker on some mobile browsers) — the in-page banner below is the
      // guaranteed fallback, so a failed OS notification is not fatal.
    }
  }

  function tick() {
    if (!("geolocation" in navigator)) {
      setStatus("error");
      setErrorMsg("This browser does not support location access.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const r = await getQuickCheck(pos.coords.latitude, pos.coords.longitude);
          setResult(r);
          setErrorMsg(null);
          setStatus("watching");
          const unsafe = isUnsafe(r);
          const now = Date.now();
          if (unsafe && (!wasUnsafeRef.current || now - lastNotifiedAtRef.current > RENOTIFY_INTERVAL_MS)) {
            notify(r);
            lastNotifiedAtRef.current = now;
          }
          wasUnsafeRef.current = unsafe;
        } catch (err) {
          setErrorMsg(err instanceof Error ? err.message : String(err));
        }
      },
      (geoErr) => {
        setStatus("error");
        setErrorMsg(
          geoErr.code === geoErr.PERMISSION_DENIED
            ? "Location access denied — allow it in your browser's site settings to use live monitoring."
            : `Location error: ${geoErr.message}`
        );
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
    );
  }

  async function start() {
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      await Notification.requestPermission();
    }
    setStatus("watching");
    setErrorMsg(null);
    wasUnsafeRef.current = false;
    lastNotifiedAtRef.current = 0;
    tick();
    intervalRef.current = window.setInterval(tick, POLL_INTERVAL_MS);
  }

  function stop() {
    setStatus("idle");
    setResult(null);
    setErrorMsg(null);
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) window.clearInterval(intervalRef.current);
    };
  }, []);

  const unsafe = result ? isUnsafe(result) : false;
  const uncertain = result ? result.insufficient_confidence : false;

  return (
    <div>
      <button
        className={`btn${status === "watching" ? " btn--primary" : ""}`}
        onClick={status === "watching" || status === "error" ? stop : start}
      >
        {status === "watching" || status === "error" ? "Stop monitoring" : "Start monitoring"}
      </button>

      {(status === "watching" || errorMsg) && (
        <div className="safety-readout surface">
          {status === "watching" && result && (
            <>
              <div className="safety-readout__row">
                {unsafe ? (
                  <span className="risk-veto__swatch" />
                ) : (
                  <span
                    className={`risk-chip__swatch`}
                    style={{
                      background: uncertain
                        ? "var(--field)"
                        : result.risk_score >= 50
                          ? "var(--risk-high)"
                          : result.risk_score >= 25
                            ? "var(--risk-moderate)"
                            : "var(--risk-low)",
                    }}
                  />
                )}
                <span className="mono" style={{ fontSize: 13 }}>
                  {result.vetoed ? result.risk_level : `${result.risk_level} ${result.risk_score}/100`}
                </span>
              </div>
              <div className="mono" style={{ fontSize: 13, color: "var(--ink-2)" }}>
                {result.lat.toFixed(4)}, {result.lon.toFixed(4)}
              </div>
            </>
          )}

          {unsafe && result && (
            <div className="safety-readout__warning">
              Not safe to continue where you are: {reasonText(result)}. Head back toward safer
              water or port.
            </div>
          )}

          {uncertain && !unsafe && result && (
            <div className="safety-readout__warning safety-readout__warning--uncertain">
              Cannot confirm this is safe:{" "}
              {result.confidence_reason ?? "too much data is missing right now"}. Proceed with
              caution.
            </div>
          )}

          {errorMsg && <div className="safety-readout__error">{errorMsg}</div>}
        </div>
      )}
    </div>
  );
}
