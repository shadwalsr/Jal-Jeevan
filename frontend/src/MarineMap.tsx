import { useEffect, useRef, useState } from "react";
import * as L from "leaflet";
import "leaflet/dist/leaflet.css";
import { getBoundaries, type RouteWaypointRisk } from "./api";

/**
 * Leaflet, not MapLibre GL JS — deliberate, and a real fix for a real
 * failure, not a style preference.
 *
 * MapLibre renders through WebGL, raster tiles included (a raster tile is
 * still a texture drawn by the GPU, not a plain image). On at least one real
 * machine (confirmed live, 28 Aug 2026, by reading the WebGL framebuffer
 * directly: valid context, no GL error, correct size, every sampled pixel
 * [0,0,0,0] — nothing had ever actually been drawn into it, despite tile
 * requests succeeding), the render loop that MapLibre depends on to paint
 * anything simply never executes a frame. Three independent "map is ready"
 * signals were tried against that (the 'load' event, polling
 * isStyleLoaded(), a hard timeout) and none of them help, because the
 * problem isn't the readiness signal — it's that WebGL rendering itself
 * never happens on that machine. Switching the basemap source (OSM, CARTO,
 * a local vector layer) couldn't have fixed this either, and didn't.
 *
 * Leaflet's default renderer draws tiles as plain <img> elements and vector
 * overlays as SVG — ordinary DOM content, composited by the browser like any
 * other page content, with no dependency on a working WebGL/GPU pipeline.
 * CARTO Positron is back as the tile source per instruction; the difference
 * this time is HOW it's drawn, not where the tiles come from.
 */
const CARTO_TILE_URL = "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const CARTO_ATTRIBUTION = "© OpenStreetMap contributors © CARTO";

function riskColor(score: number): string {
  if (score >= 75) return "#e3675a"; // EXTREME
  if (score >= 50) return "#e3a53d"; // HIGH
  if (score >= 25) return "#d9c94f"; // MODERATE
  return "#3ecfa8"; // LOW
}

// Exclusions are drawn in the chart convention for restricted areas: a
// magenta-crimson hatch, never a solid fill. Deliberate and load-bearing —
// a hard-constraint veto (foreign EEZ, protected area) is categorically
// different from a high risk score, and painting them the same way would
// undo on screen exactly what risk_agent.py's two-stage pipeline enforces
// in the backend. Hatching also survives greyscale and does not rely on
// hue, which matters for the ~8% of men with red/green colour blindness.
const EXCLUSION_COLOR = "#c2185b";
const PERMITTED_COLOR = "#3ecfa8";
const PORT_COLOR = "#4f8fe0";
const HATCH_PATTERN_ID = "jaljeev-hatch-pattern";

/**
 * Injects the hatch <pattern> once into Leaflet's own SVG renderer, so
 * `fillColor: "url(#jaljeev-hatch-pattern)"` resolves on any path drawn
 * afterward. Leaflet passes fillColor straight through as the SVG `fill`
 * attribute, so a pattern reference works exactly like a solid colour would
 * — no library-level "fill pattern" feature needed, this is just SVG.
 */
function ensureHatchPattern(svgRoot: SVGSVGElement) {
  if (svgRoot.querySelector(`#${HATCH_PATTERN_ID}`)) return;
  const ns = "http://www.w3.org/2000/svg";
  let defs = svgRoot.querySelector("defs");
  if (!defs) {
    defs = document.createElementNS(ns, "defs");
    svgRoot.insertBefore(defs, svgRoot.firstChild);
  }
  const pattern = document.createElementNS(ns, "pattern");
  pattern.setAttribute("id", HATCH_PATTERN_ID);
  pattern.setAttribute("width", "8");
  pattern.setAttribute("height", "8");
  pattern.setAttribute("patternUnits", "userSpaceOnUse");
  pattern.setAttribute("patternTransform", "rotate(45)");
  const line = document.createElementNS(ns, "line");
  line.setAttribute("x1", "0");
  line.setAttribute("y1", "0");
  line.setAttribute("x2", "0");
  line.setAttribute("y2", "8");
  line.setAttribute("stroke", EXCLUSION_COLOR);
  line.setAttribute("stroke-width", "1.4");
  pattern.appendChild(line);
  defs.appendChild(pattern);
}

// Both an OptimizedRoute (radial search) and a PassagePlan (port-to-port)
// carry the same found_route + risk-scored waypoint list, which is all this
// map needs to draw a path. Typing on that shared shape rather than on
// either concrete result keeps one drawing path for both, instead of two
// that can drift apart visually.
interface DrawablePath {
  found_route: boolean;
  waypoints: RouteWaypointRisk[];
}

interface Props {
  lat: number;
  lon: number;
  route: DrawablePath | null;
}

export default function MarineMap({ lat, lon, route }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const boundaryLayerRef = useRef<{ eez: L.GeoJSON; mpa: L.GeoJSON; ports: L.GeoJSON } | null>(null);
  const routeLayerRef = useRef<L.LayerGroup | null>(null);
  const originMarkerRef = useRef<L.CircleMarker | null>(null);
  const fetchTimer = useRef<number | null>(null);
  const [coverageNote, setCoverageNote] = useState<string | null>(null);
  const [inView, setInView] = useState<number | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  // Mount once. Unlike MapLibre, Leaflet has no async "style load" phase —
  // the map object and its layers are usable synchronously right after
  // construction, so none of the readiness-race handling the WebGL version
  // needed applies here.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let map: L.Map;
    try {
      map = L.map(containerRef.current, {
        center: [lat, lon],
        zoom: 9,
        zoomControl: true,
        attributionControl: true,
      });
      L.tileLayer(CARTO_TILE_URL, {
        attribution: CARTO_ATTRIBUTION,
        maxZoom: 19,
      }).addTo(map);
    } catch (err) {
      console.error("[MarineMap] failed to create the map:", err);
      setMapError(err instanceof Error ? err.message : "The map could not start.");
      return;
    }
    mapRef.current = map;

    // Leaflet measures its container once, at construction, and caches
    // that size internally. Confirmed live (28 Aug 2026): the container was
    // properly sized (1280x720) by the time anything queried it directly,
    // yet map.getBounds() kept returning a degenerate single point — the
    // cached size from the split second BEFORE the browser had finished a
    // layout pass on this absolutely-positioned parent chain never got
    // refreshed on its own. invalidateSize() forces Leaflet to re-measure;
    // deferred one frame so it runs after that layout pass has definitely
    // completed, rather than racing it again.
    requestAnimationFrame(() => map.invalidateSize());

    const eez = L.geoJSON(undefined, {
      style: (feature) => {
        const excluded = !!feature?.properties?.exclusion;
        return excluded
          ? { color: EXCLUSION_COLOR, weight: 2, fillColor: `url(#${HATCH_PATTERN_ID})`, fillOpacity: 0.55 }
          : { color: PERMITTED_COLOR, weight: 1.5, fill: false, opacity: 0.8 };
      },
      onEachFeature: (feature, layer) => {
        if (!feature.properties?.exclusion) return;
        layer.on("click", () => {
          layer.bindPopup(`${feature.properties?.territory ?? "Foreign"} EEZ — outside Indian waters`).openPopup();
        });
      },
    }).addTo(map);

    const mpa = L.geoJSON(undefined, {
      style: { color: EXCLUSION_COLOR, weight: 1.5, dashArray: "3,2", fillColor: `url(#${HATCH_PATTERN_ID})`, fillOpacity: 0.75 },
      onEachFeature: (feature, layer) => {
        layer.on("click", () => {
          const name = feature.properties?.name ?? "Protected area";
          const designation = feature.properties?.designation ? ` — ${feature.properties.designation}` : "";
          layer.bindPopup(`Protected area: ${name}${designation}`).openPopup();
        });
      },
    }).addTo(map);

    const ports = L.geoJSON(undefined, {
      pointToLayer: (_feature, latlng) =>
        L.circleMarker(latlng, { radius: 4, color: "#ffffff", weight: 1.5, fillColor: PORT_COLOR, fillOpacity: 1 }),
      onEachFeature: (feature, layer) => {
        layer.on("click", () => {
          layer.bindPopup(`Port: ${feature.properties?.name} (${feature.properties?.state})`).openPopup();
        });
      },
    }).addTo(map);

    boundaryLayerRef.current = { eez, mpa, ports };

    // The hatch pattern needs Leaflet's own SVG root, created once the first
    // vector layer is added — but not synchronously within the same tick as
    // that .addTo(map) call (confirmed live: querying immediately after
    // adding all three geoJSON layers above still found nothing, while the
    // exact same query moments later found it, complete with rendered
    // paths). A couple of animation-frame retries comfortably covers that
    // gap without guessing at a fixed delay.
    let attempts = 0;
    const tryInstallHatch = () => {
      const svgRoot = containerRef.current?.querySelector("svg.leaflet-zoom-animated") as SVGSVGElement | null;
      if (svgRoot) {
        ensureHatchPattern(svgRoot);
      } else if (attempts++ < 10) {
        requestAnimationFrame(tryInstallHatch);
      } else {
        console.error("[MarineMap] Leaflet's SVG renderer root never appeared — hatch pattern not installed.");
      }
    };
    requestAnimationFrame(tryInstallHatch);

    void loadBoundaries(map);

    // Boundaries are bbox-scoped, so refetch when the view settles.
    // Debounced: a pan fires moveend once, but a drag-zoom can fire several.
    map.on("moveend", () => {
      if (fetchTimer.current) window.clearTimeout(fetchTimer.current);
      fetchTimer.current = window.setTimeout(() => void loadBoundaries(map), 400);
    });

    return () => {
      if (fetchTimer.current) window.clearTimeout(fetchTimer.current);
      map.remove();
      mapRef.current = null;
      boundaryLayerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadBoundaries(map: L.Map) {
    if (mapRef.current !== map) return;
    const b = map.getBounds();
    const minLat = b.getSouth();
    const maxLat = b.getNorth();
    const minLon = b.getWest();
    const maxLon = b.getEast();
    // The endpoint rejects anything wider than 40 degrees a side; at that
    // zoom the layer would be unreadable anyway, so skip rather than error.
    if (maxLat - minLat > 39 || maxLon - minLon > 39) return;
    // getBounds() can return a degenerate, zero-size rectangle if called
    // before the map container has settled its real layout size (confirmed
    // live, 28 Aug 2026 — the very first call after mount, before React/CSS
    // had finished laying out the flex/absolute-positioned parent, produced
    // north === south). The backend correctly rejects that with a 400
    // ("max_lat/max_lon must be greater than min_lat/min_lon") — this skips
    // the request entirely rather than sending one already known to fail;
    // the next moveend (Leaflet fires several while settling initial tiles)
    // retries with real bounds.
    if (maxLat <= minLat || maxLon <= minLon) {
      console.warn("[MarineMap] skipping boundaries fetch — map bounds not settled yet", { minLat, maxLat, minLon, maxLon });
      return;
    }
    try {
      const data = await getBoundaries(minLat, minLon, maxLat, maxLon);
      const layers = boundaryLayerRef.current;
      if (!layers) return;
      layers.eez.clearLayers().addData((data.eez ?? { type: "FeatureCollection", features: [] }) as GeoJSON.GeoJsonObject);
      layers.mpa.clearLayers().addData((data.mpa ?? { type: "FeatureCollection", features: [] }) as GeoJSON.GeoJsonObject);
      layers.ports.clearLayers().addData((data.ports ?? { type: "FeatureCollection", features: [] }) as GeoJSON.GeoJsonObject);

      const exclusions =
        (data.eez?.features.filter((f) => f.properties?.exclusion).length ?? 0) +
        (data.mpa?.features.length ?? 0);
      setInView(exclusions);
      setCoverageNote(data.coverage_note ?? null);
    } catch (err) {
      // A failed boundary fetch must not break the map. It does mean the
      // exclusion layer is absent, though, and the legend says so rather
      // than letting an empty map imply "nothing is restricted here".
      console.error("[MarineMap] boundaries fetch failed:", err);
      setCoverageNote("Boundary layer unavailable — exclusions are not being shown.");
    }
  }

  // Origin marker + route overlay, redrawn whenever the queried point or the
  // route result changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (originMarkerRef.current) originMarkerRef.current.remove();
    originMarkerRef.current = L.circleMarker([lat, lon], {
      radius: 7,
      color: "#ffffff",
      weight: 2,
      fillColor: "#4f8fe0",
      fillOpacity: 1,
    })
      .bindPopup("Origin")
      .addTo(map);

    if (routeLayerRef.current) {
      routeLayerRef.current.remove();
      routeLayerRef.current = null;
    }

    if (route && route.found_route && route.waypoints.length > 0) {
      const group = L.layerGroup();
      const coords = route.waypoints.map((w) => [w.lat, w.lon] as [number, number]);

      L.polyline(coords, { color: "#3ecfa8", weight: 3, dashArray: "1,1" }).addTo(group);

      route.waypoints.forEach((w, i) => {
        L.circleMarker([w.lat, w.lon], {
          radius: 7,
          color: "#ffffff",
          weight: 2,
          fillColor: riskColor(w.risk_score),
          fillOpacity: 1,
        })
          .bindPopup(`Waypoint ${i + 1}: risk ${w.risk_score}/100`)
          .addTo(group);
      });

      group.addTo(map);
      routeLayerRef.current = group;
      map.fitBounds(L.latLngBounds(coords), { padding: [60, 60], maxZoom: 12 });
    } else {
      map.flyTo([lat, lon], 9);
    }
  }, [lat, lon, route]);

  if (mapError) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
          background: "var(--field, #f6f6f4)",
        }}
      >
        <div className="surface" style={{ maxWidth: 420, padding: "14px 16px" }}>
          <div style={{ fontWeight: 500, marginBottom: 6 }}>Map unavailable</div>
          <div style={{ fontSize: 13, color: "var(--ink-2, #5a5a5a)" }}>{mapError}</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      <div className="map-legend">
        <div className="map-legend-title">Exclusions</div>
        <div className="map-legend-row">
          <span className="legend-swatch legend-hatch" /> Foreign EEZ / protected area — do not enter
        </div>
        <div className="map-legend-row">
          <span className="legend-swatch legend-permitted" /> Indian EEZ — permitted
        </div>
        <div className="map-legend-row">
          <span className="legend-swatch legend-port" /> Port
        </div>
        {inView === 0 && (
          <div className="map-legend-clear">No exclusions in this view — pan south to Palk Bay to see one.</div>
        )}
        {coverageNote && <div className="map-legend-note">{coverageNote}</div>}
      </div>
    </div>
  );
}
