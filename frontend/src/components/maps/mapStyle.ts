/**
 * mapStyle.ts — shared MapLibre base style + choropleth color helpers.
 *
 * Base map: an offline, token-free background-only style. The app is dark-first
 * and is intended to deploy inside a Databricks App that may have no network
 * egress, so we do NOT pull external tiles (MapLibre demotiles / OpenFreeMap)
 * by default — the choropleth polygons ARE the map, on a deep-slate canvas that
 * matches `index.css` (`--background`). To add a basemap later, swap
 * `EMPTY_DARK_STYLE` for a URL string, e.g. "https://tiles.openfreemap.org/styles/dark"
 * (needs egress) — react-map-gl accepts either a style object or a URL.
 */
import type { StyleSpecification } from "maplibre-gl";

export const EMPTY_DARK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "hsl(222 47% 9%)" },
    },
  ],
};

/** Fill for polygons we have no data for (matches the muted token, dimmed). */
export const NEUTRAL_FILL = "hsl(217 33% 16%)";
/** Polygon outline — just above the canvas so shapes stay legible. */
export const BORDER_COLOR = "hsl(217 33% 28%)";
export const BORDER_HIGHLIGHT = "hsl(187 85% 43%)"; // teal, hovered feature

// Sequential ramp endpoints (RGB to avoid HSL hue-wrap through greens/yellows).
// 0.0 muted slate -> 0.5 chronic orange -> 1.0 acute red. Matches chartTheme intent.
const RAMP: Array<[number, [number, number, number]]> = [
  [0.0, [55, 75, 109]],
  [0.5, [243, 123, 37]],
  [1.0, [225, 71, 71]],
];

function lerp(a: number, b: number, t: number) {
  return Math.round(a + (b - a) * t);
}

/** Continuous overlooked_score (0..1) -> rgb() string along the sequential ramp. */
export function scoreColor(score: number): string {
  const s = Math.max(0, Math.min(1, score));
  for (let i = 1; i < RAMP.length; i++) {
    const [hi, hiC] = RAMP[i];
    const [lo, loC] = RAMP[i - 1];
    if (s <= hi) {
      const t = (s - lo) / (hi - lo || 1);
      return `rgb(${lerp(loC[0], hiC[0], t)},${lerp(loC[1], hiC[1], t)},${lerp(loC[2], hiC[2], t)})`;
    }
  }
  const last = RAMP[RAMP.length - 1][1];
  return `rgb(${last[0]},${last[1]},${last[2]})`;
}

type GJ = { type: string; features: Array<{ geometry: { coordinates: unknown } }> };

/** [minLon, minLat, maxLon, maxLat] across a GeoJSON FeatureCollection. */
export function bboxOf(fc: GJ): [number, number, number, number] {
  let minX = 180, minY = 90, maxX = -180, maxY = -90;
  const walk = (c: unknown): void => {
    if (Array.isArray(c)) {
      if (typeof c[0] === "number" && typeof c[1] === "number") {
        const [x, y] = c as [number, number];
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      } else {
        for (const v of c) walk(v);
      }
    }
  };
  for (const f of fc.features) walk(f.geometry.coordinates);
  return [minX, minY, maxX, maxY];
}
