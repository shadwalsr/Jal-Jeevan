import type { OptimizedRoute, PassagePlan } from "./api";

interface Props {
  route: OptimizedRoute | null;
  passage?: PassagePlan | null;
}

/** Hours as something a skipper reads off a plan, not a raw float. */
function formatDuration(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  const whole = Math.floor(hours);
  const minutes = Math.round((hours - whole) * 60);
  if (whole < 24) return minutes ? `${whole}h ${minutes}m` : `${whole}h`;
  const days = Math.floor(whole / 24);
  return `${days}d ${whole % 24}h`;
}

function riskModifier(score: number): string {
  if (score >= 75) return "extreme";
  if (score >= 50) return "high";
  if (score >= 25) return "moderate";
  return "low";
}

/** A measurement the source did not report. Never 0, never a dash. */
function Reading({ value, unit }: { value: number | null | undefined; unit?: string }) {
  if (value == null) return <span className="na">not available</span>;
  return (
    <span>
      {value}
      {unit ? ` ${unit}` : ""}
    </span>
  );
}

export default function EvidencePanel({ route, passage }: Props) {
  // A passage is the more specific answer — when one has been planned it is
  // what the user just asked for, so it takes the panel.
  if (passage) return <PassageEvidence passage={passage} />;
  if (!route) return null;

  if (!route.found_route) {
    return (
      <aside className="evidence-panel surface">
        <div className="evidence-panel__head">
          <span className="evidence-panel__title">Route optimizer</span>
        </div>
        <div className="evidence-panel__body">
          <div className="risk-veto">
            <div className="risk-veto__head">
              <span className="risk-veto__swatch" />
              <span>No route found</span>
            </div>
            <div className="risk-veto__reasons">{route.reason ?? "No viable path within range."}</div>
          </div>
          {route.cells_evaluated > 0 && route.cells_viable === 0 && (
            <div className="evidence-rejected" style={{ fontSize: 13 }}>
              Every cell in range was vetoed by a hard constraint. That is a legal or
              survivability answer, not a search failure.
            </div>
          )}
        </div>
      </aside>
    );
  }

  return (
    <aside className="evidence-panel surface">
      <div className="evidence-panel__head">
        <span className="evidence-panel__title">Route evidence — A*</span>
        <span className="evidence-panel__id mono">
          {route.waypoints.length} waypoints
        </span>
      </div>

      <div className="evidence-panel__body">
        <div>
          <div className="evidence-section__title">Search</div>
          <div className="evidence-section__rule" />
          <div className="evidence-rows mono">
            <div className="evidence-row evidence-row--stat">
              <span>Cells evaluated</span>
              <Reading value={route.cells_evaluated} />
            </div>
            <div className="evidence-row evidence-row--stat">
              <span>Cells viable after vetoes</span>
              <span>
                {route.cells_viable} of {route.cells_evaluated}
              </span>
            </div>
            <div className="evidence-row evidence-row--stat">
              <span>Total risk cost</span>
              <Reading value={route.total_risk_cost} />
            </div>
          </div>
        </div>

        <div>
          <div className="evidence-section__title">Waypoints</div>
          <div className="evidence-section__rule" />
          <table className="evidence-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Lat</th>
                <th>Lon</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {route.waypoints.map((w, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{w.lat.toFixed(4)}</td>
                  <td>{w.lon.toFixed(4)}</td>
                  <td>
                    <span className={`risk-dot risk-dot--${riskModifier(w.risk_score)}`} />
                    {w.risk_score}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {route.destination_maps_url && (
          <div>
            <a
              className="link-btn"
              href={route.destination_maps_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open destination in Maps
            </a>
          </div>
        )}
      </div>
    </aside>
  );
}

/**
 * Passage evidence — the sailor and trader view.
 *
 * Structured around the two things a passage is actually judged on, which a
 * single overall score cannot express: the WORST leg (a passage is only as
 * good as its roughest hours, never its average) and how much of it is real
 * forecast. A leg beyond the forecast horizon is called out in the table
 * and again in the note, because that is the one thing here the system does
 * not actually know.
 */
function PassageEvidence({ passage }: { passage: PassagePlan }) {
  if (!passage.found_route) {
    return (
      <aside className="evidence-panel surface">
        <div className="evidence-panel__head">
          <span className="evidence-panel__title">Passage plan</span>
        </div>
        <div className="evidence-panel__body">
          <div className="risk-veto">
            <div className="risk-veto__head">
              <span className="risk-veto__swatch" />
              <span>No passage found</span>
            </div>
            <div className="risk-veto__reasons">
              {passage.reason ?? "No viable passage for this vessel."}
            </div>
          </div>
          <div className="evidence-rejected" style={{ fontSize: 13 }}>
            This is a verdict about {passage.vessel_name} on this water — a different
            vessel may well be able to make the same passage.
          </div>
        </div>
      </aside>
    );
  }

  const tacking =
    passage.sailed_distance_nm != null &&
    passage.routed_distance_nm != null &&
    passage.sailed_distance_nm > passage.routed_distance_nm + 0.1;

  const detour =
    passage.routed_distance_nm != null && passage.direct_distance_nm != null
      ? passage.routed_distance_nm - passage.direct_distance_nm
      : null;

  const unforecast = passage.legs.filter((l) => l.beyond_forecast_horizon).length;

  return (
    <aside className="evidence-panel surface">
      <div className="evidence-panel__head">
        <span className="evidence-panel__title">
          {passage.origin_name ?? "Departure"} to {passage.destination_name ?? "Destination"}
        </span>
        <span className="evidence-panel__id mono">{passage.legs.length} legs</span>
      </div>

      <div className="evidence-panel__body">
        <div>
          <div className="evidence-section__title">Passage</div>
          <div className="evidence-section__rule" />
          <div className="evidence-rows mono">
            <div className="evidence-row evidence-row--stat">
              <span>Vessel</span>
              <span>{passage.vessel_name}</span>
            </div>
            <div className="evidence-row evidence-row--stat">
              <span>Distance</span>
              <Reading value={passage.routed_distance_nm} unit="nm" />
            </div>
            {tacking && (
              <div className="evidence-row evidence-row--stat">
                <span>Actually sailed</span>
                <span>{passage.sailed_distance_nm?.toFixed(1)} nm with tacks</span>
              </div>
            )}
            <div className="evidence-row evidence-row--stat">
              <span>ETA</span>
              <span>
                {passage.total_eta_hours != null ? (
                  formatDuration(passage.total_eta_hours)
                ) : (
                  <span className="na">not available</span>
                )}
              </span>
            </div>
            <div className="evidence-row evidence-row--stat">
              <span>Worst leg</span>
              <span>
                {passage.max_leg_risk_level ? (
                  <>
                    <span
                      className={`risk-dot risk-dot--${riskModifier(
                        passage.max_leg_risk_score ?? 0
                      )}`}
                    />
                    {passage.max_leg_risk_level} ({passage.max_leg_risk_score}/100)
                  </>
                ) : (
                  <span className="na">not available</span>
                )}
              </span>
            </div>
            <div className="evidence-row evidence-row--stat">
              <span>Cells viable after vetoes</span>
              <span>
                {passage.cells_viable} of {passage.cells_evaluated}
              </span>
            </div>
          </div>
          {detour != null && detour > 0.5 && (
            <div className="evidence-rejected" style={{ fontSize: 13, marginTop: 8 }}>
              Routed {detour.toFixed(1)} nm longer than the{" "}
              {passage.direct_distance_nm?.toFixed(1)} nm direct track, to stay clear of
              higher-risk or vetoed water.
            </div>
          )}
        </div>

        <div>
          <div className="evidence-section__title">Legs</div>
          <div className="evidence-section__rule" />
          <table className="evidence-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Steer</th>
                <th>Dist</th>
                <th>ETA</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {passage.legs.map((leg, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{leg.bearing_deg.toFixed(0)}</td>
                  <td>
                    {leg.distance_nm.toFixed(1)} nm
                    {leg.must_tack && <span className="leg-flag leg-flag--tack">tack</span>}
                  </td>
                  <td>
                    +{formatDuration(leg.eta_hours_from_departure)}
                    {leg.beyond_forecast_horizon && (
                      <span className="leg-flag leg-flag--unforecast">no forecast</span>
                    )}
                  </td>
                  <td>
                    <span className={`risk-dot risk-dot--${riskModifier(leg.risk_score)}`} />
                    {leg.risk_score}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {passage.diversion_ports.length > 0 && (
          <div>
            <div className="evidence-section__title">Diversion ports</div>
            <div className="evidence-section__rule" />
            <div className="evidence-rows mono">
              {passage.diversion_ports.map((d) => (
                <div
                  className="evidence-row evidence-row--stat"
                  key={`${d.name}-${d.from_leg_index}`}
                >
                  <span>From leg {d.from_leg_index + 1}</span>
                  <span>
                    {d.name} — {d.distance_km.toFixed(0)} km
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {passage.forecast_note && (
          <div
            className={unforecast > 0 ? "risk-veto" : "evidence-rejected"}
            style={{ fontSize: 13 }}
          >
            {passage.forecast_note}
          </div>
        )}

        {passage.destination_maps_url && (
          <div>
            <a
              className="link-btn"
              href={passage.destination_maps_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open destination in Maps
            </a>
          </div>
        )}
      </div>
    </aside>
  );
}
