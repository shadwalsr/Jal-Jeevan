import { useEffect, useState } from "react";
import { getPorts, type Port } from "./api";
import { useLanguage } from "./i18n/LanguageContext";

interface Props {
  planning: boolean;
  onPlan: (destinationName: string) => void;
  error: string | null;
}

const FALLBACK_PORTS: Port[] = [
  { name: "Goa (Mormugao)", state: "Goa", lat: 15.4028, lon: 73.7996 },
  { name: "Kochi (Cochin)", state: "Kerala", lat: 9.965, lon: 76.22 },
  { name: "New Mangalore Port", state: "Karnataka", lat: 12.928, lon: 74.815 },
  { name: "Karwar Port", state: "Karnataka", lat: 14.805, lon: 74.12 },
  { name: "Mumbai (JNP / Nhava Sheva)", state: "Maharashtra", lat: 18.95, lon: 72.95 },
  { name: "Visakhapatnam Port", state: "Andhra Pradesh", lat: 17.6868, lon: 83.2185 },
  { name: "Chennai Port", state: "Tamil Nadu", lat: 13.0827, lon: 80.2707 },
  { name: "Tuticorin (V.O.C.)", state: "Tamil Nadu", lat: 8.7642, lon: 78.1348 },
];

/**
 * Destination picker for a port-to-port passage.
 */
export default function PassagePanel({
  planning,
  onPlan,
  error,
}: Props) {
  const { t } = useLanguage();
  const [ports, setPorts] = useState<Port[]>(FALLBACK_PORTS);
  const [destination, setDestination] = useState("Goa (Mormugao)");

  useEffect(() => {
    getPorts()
      .then((resp) => {
        if (resp.ports && resp.ports.length > 0) {
          setPorts(resp.ports);
        }
      })
      .catch(() => {
        // Fallbacks already in place
      });
  }, []);

  return (
    <div className="passage-panel surface">
      <div className="passage-panel__header">
        <label className="vessel-selector__label" htmlFor="passage-destination">
          {t("destination_port")}
        </label>
      </div>

      <div className="passage-panel__row">
        <select
          id="passage-destination"
          className="vessel-selector__select"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
        >
          <option value="">{t("destination_port")}…</option>
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
          {planning ? t("planning") : t("plan_passage")}
        </button>
      </div>

      <div className="passage-panel__hint">
        Departs from the point currently on the map.
      </div>
      {error && <div className="safety-readout surface safety-readout__error">{error}</div>}
    </div>
  );
}
