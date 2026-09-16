import { useEffect, useState } from "react";
import { getPorts, type Port } from "./api";

interface Props {
  planning: boolean;
  onPlan: (destinationName: string) => void;
  error: string | null;
}

/**
 * Destination picker for a port-to-port passage.
 *
 * Ports, not free text or a geocoded place name: the ports table holds
 * HARBOUR ENTRANCE coordinates, whereas geocoding a city name resolves to
 * the city centre — which is on land and correctly hard-vetoes (CLAUDE.md's
 * Visakhapatnam note). Offering only real, plannable endpoints means a
 * failed passage here always means something about the water, never about
 * the place lookup.
 *
 * The origin is wherever the map is currently focused, so this control only
 * has to ask for the half the user actually has to choose.
 */
export default function PassagePanel({ planning, onPlan, error }: Props) {
  const [ports, setPorts] = useState<Port[]>([]);
  const [destination, setDestination] = useState("");
  const [portsError, setPortsError] = useState<string | null>(null);

  useEffect(() => {
    getPorts()
      .then((resp) => setPorts(resp.ports))
      .catch((err) => setPortsError(err instanceof Error ? err.message : String(err)));
  }, []);

  if (portsError) {
    return (
      <div className="passage-panel surface">
        <span className="na">Ports unavailable: {portsError}</span>
      </div>
    );
  }

  if (ports.length === 0) {
    // Empty, not an error: the backend returns an empty list when the ports
    // table hasn't been loaded. Say which it is rather than showing a
    // control that silently can't work.
    return (
      <div className="passage-panel surface">
        <span className="na">
          No ports loaded — passage planning needs infra/sql/002_ports_seed.sql.
        </span>
      </div>
    );
  }

  return (
    <div className="passage-panel surface">
      <label className="vessel-selector__label" htmlFor="passage-destination">
        Passage to
      </label>
      <div className="passage-panel__row">
        <select
          id="passage-destination"
          className="vessel-selector__select"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
        >
          <option value="">Choose a destination port…</option>
          {ports.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name}
              {p.state ? ` — ${p.state}` : ""}
            </option>
          ))}
        </select>
        <button
          className="btn"
          disabled={!destination || planning}
          onClick={() => destination && onPlan(destination)}
        >
          {planning ? "Planning…" : "Plan passage"}
        </button>
      </div>
      <div className="passage-panel__hint">
        Departs from the point currently on the map.
      </div>
      {error && <div className="safety-readout surface safety-readout__error">{error}</div>}
    </div>
  );
}
