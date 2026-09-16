import { useEffect, useState } from "react";
import { getVesselClasses, type VesselClass } from "./api";

interface Props {
  value: string | null;
  onChange: (vesselClass: string | null, profile: VesselClass | null) => void;
}

// Order the groups the way the problem statement reads them, rather than
// whatever order the backend dict happens to serialise in.
const GROUP_ORDER = ["fisherman", "sailor", "trader"];
const GROUP_LABELS: Record<string, string> = {
  fisherman: "Fishing",
  sailor: "Sailing",
  trader: "Trade & commercial",
};

/**
 * Vessel picker, populated from GET /marine/vessel-classes.
 *
 * Deliberately not a hardcoded list: the backend registry
 * (app/agents/vessel_profiles.py) is the single source of truth for which
 * classes the risk engine can actually score, and a class added there
 * should appear here with no frontend change. It also means this control
 * can never offer a class the backend would reject and silently replace
 * with an 8m fishing boat.
 *
 * The chosen vessel is shown with the numbers that actually drive the
 * verdict (draft, wave and wind limits, range, speed) — a user should be
 * able to see why the same sea came back safe for one boat and rejected
 * for another, without having to ask.
 */
export default function VesselSelector({ value, onChange }: Props) {
  const [groups, setGroups] = useState<Record<string, VesselClass[]>>({});
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getVesselClasses()
      .then((resp) => {
        setGroups(resp.groups);
        setNote(resp.note);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const all = Object.values(groups).flat();
  const selected = all.find((v) => v.vessel_class === value) ?? null;

  if (error) {
    // Report the gap rather than falling back to an invented list — an
    // offered class the backend doesn't know is worse than no picker.
    return (
      <div className="vessel-selector surface">
        <span className="na">Vessel classes unavailable: {error}</span>
      </div>
    );
  }

  const orderedGroups = [
    ...GROUP_ORDER.filter((g) => groups[g]?.length),
    ...Object.keys(groups).filter((g) => !GROUP_ORDER.includes(g)),
  ];

  return (
    <div className="vessel-selector surface">
      <label className="vessel-selector__label" htmlFor="vessel-class">
        Vessel
      </label>
      <select
        id="vessel-class"
        className="vessel-selector__select"
        value={value ?? ""}
        onChange={(e) => {
          const next = e.target.value || null;
          onChange(next, all.find((v) => v.vessel_class === next) ?? null);
        }}
      >
        <option value="">Default — small fishing boat (8m)</option>
        {orderedGroups.map((group) => (
          <optgroup key={group} label={GROUP_LABELS[group] ?? group}>
            {groups[group].map((v) => (
              <option key={v.vessel_class} value={v.vessel_class}>
                {v.vessel_name}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      {selected && (
        <div className="vessel-selector__spec mono">
          <div className="vessel-selector__spec-row">
            <span>Draft</span>
            <span>{selected.draft_m.toFixed(1)} m</span>
          </div>
          <div className="vessel-selector__spec-row">
            <span>Max safe wave</span>
            <span>{selected.max_safe_wave_m.toFixed(1)} m</span>
          </div>
          <div className="vessel-selector__spec-row">
            <span>Wind limit</span>
            <span>{selected.wind_threshold_ms.toFixed(0)} m/s</span>
          </div>
          <div className="vessel-selector__spec-row">
            <span>Range</span>
            <span>{selected.operational_range_km.toLocaleString()} km</span>
          </div>
          <div className="vessel-selector__spec-row">
            <span>Cruise</span>
            <span>{selected.cruise_speed_kn.toFixed(1)} kn</span>
          </div>
          {selected.propulsion !== "motor" && (
            <div className="vessel-selector__sail-note">
              Under sail — wind is scored as a resource as well as a hazard, and
              legs that cannot be laid direct are costed as tacks.
            </div>
          )}
        </div>
      )}

      {note && <div className="vessel-selector__note">{note}</div>}
    </div>
  );
}
