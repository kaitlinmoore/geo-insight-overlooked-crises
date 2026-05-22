import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MapGL, { Layer, Source } from "react-map-gl/maplibre";
import type { MapLayerMouseEvent, MapRef } from "react-map-gl/maplibre";
import type { Feature, FeatureCollection, Point } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import { Skeleton } from "@/components/ui/skeleton";
import { chartColors } from "@/lib/chartTheme";
import { fetchHotspots } from "@/lib/api";
import type { AcledHotspot, SubnationalArea } from "@/lib/types";
import { BORDER_COLOR, BORDER_HIGHLIGHT, EMPTY_DARK_STYLE, NEUTRAL_FILL, bboxOf, scoreColor } from "./mapStyle";

type HoverInfo = { kind: "area" | "hotspot"; pcode: string; lng: number; lat: number; title: string; lines: string[] };

async function fetchAdmin1(iso3: string): Promise<FeatureCollection> {
  const res = await fetch(`/maps/admin1/${iso3}.geojson`);
  if (!res.ok) throw new Error(`admin1/${iso3}.geojson ${res.status}`);
  return (await res.json()) as FeatureCollection;
}

function recencyColor(ratio: number): string {
  if (ratio >= 0.2) return chartColors.acute;
  if (ratio >= 0.12) return chartColors.chronic;
  return chartColors.primary;
}

/**
 * Subnational admin1 choropleth filled by overlooked_score (joined to the
 * crisis detail's subnational[] on admin1_pcode), with ACLED conflict hotspots
 * overlaid as circles — sized by event_count, colored by recency. Areas with no
 * score (e.g. data_sparsity_flag countries) render neutral; hotspots still show,
 * since ACLED severity is independent of HNO admin1 coverage.
 */
export function SubnationalMap({ iso3, subnational }: { iso3: string; subnational: SubnationalArea[] }) {
  const mapRef = useRef<MapRef | null>(null);
  const [hover, setHover] = useState<HoverInfo | null>(null);

  const geo = useQuery({ queryKey: ["geojson", "admin1", iso3], queryFn: () => fetchAdmin1(iso3), staleTime: Infinity, retry: false });
  const hot = useQuery({ queryKey: ["hotspots", iso3], queryFn: () => fetchHotspots(iso3) });

  const byPcode = useMemo(() => {
    const m = new globalThis.Map<string, SubnationalArea>();
    for (const a of subnational) m.set(a.pcode, a);
    return m;
  }, [subnational]);

  const data = useMemo<FeatureCollection | null>(() => {
    if (!geo.data) return null;
    return {
      type: "FeatureCollection",
      features: geo.data.features.map((f) => {
        const pcode = (f.properties?.admin1_pcode as string) ?? "";
        const a = byPcode.get(pcode);
        return {
          ...f,
          properties: {
            admin1_pcode: pcode,
            admin1_name: (f.properties?.admin1_name as string) ?? pcode,
            fillColor: a ? scoreColor(a.overlooked_score) : NEUTRAL_FILL,
            scored: a ? 1 : 0,
            score: a?.overlooked_score ?? null,
            severity: a?.inform_severity ?? null,
          },
        };
      }),
    };
  }, [geo.data, byPcode]);

  const hotspots = useMemo<FeatureCollection<Point> | null>(() => {
    if (!hot.data) return null;
    const max = Math.max(1, ...hot.data.hotspots.map((h) => h.event_count));
    const features: Feature<Point>[] = hot.data.hotspots.map((h: AcledHotspot) => {
      const ratio = h.event_count ? h.recent_event_count / h.event_count : 0;
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [h.longitude, h.latitude] },
        properties: {
          admin1_pcode: h.admin1_pcode,
          event_count: h.event_count,
          recent_event_count: h.recent_event_count,
          last_event_date: h.last_event_date,
          radius: 5 + (h.event_count / max) * 16,
          color: recencyColor(ratio),
        },
      };
    });
    return { type: "FeatureCollection", features };
  }, [hot.data]);

  if (geo.isLoading) return <Skeleton className="h-72 w-full" />;
  if (geo.isError || !data)
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
        No admin1 boundaries for {iso3} — not a priority country, or run <code className="mx-1">extract_geojson.py</code>
      </div>
    );

  const onLoad = () => {
    if (!data) return;
    const [w, s, e, n] = bboxOf(data);
    mapRef.current?.fitBounds([[w, s], [e, n]], { padding: 24, duration: 0 });
  };

  const onMove = (ev: MapLayerMouseEvent) => {
    const f = ev.features?.[0];
    if (!f) {
      setHover(null);
      return;
    }
    const p = f.properties as Record<string, unknown>;
    if (f.layer.id === "hotspot-circles") {
      setHover({
        kind: "hotspot",
        pcode: (p.admin1_pcode as string) ?? "",
        lng: ev.lngLat.lng,
        lat: ev.lngLat.lat,
        title: "ACLED hotspot",
        lines: [
          `${p.event_count as number} events · ${p.recent_event_count as number} recent`,
          `last: ${p.last_event_date as string}`,
        ],
      });
    } else {
      const scored = Boolean(p.scored);
      setHover({
        kind: "area",
        pcode: (p.admin1_pcode as string) ?? "",
        lng: ev.lngLat.lng,
        lat: ev.lngLat.lat,
        title: (p.admin1_name as string) ?? "",
        lines: scored
          ? [`Overlooked ${((p.score as number) * 100).toFixed(0)}%`, `INFORM ${(p.severity as number).toFixed(1)}`]
          : ["No admin1 need data"],
      });
    }
  };

  return (
    <div className="relative h-72 w-full overflow-hidden rounded-lg border border-border">
      <MapGL
        ref={mapRef}
        initialViewState={{ longitude: 20, latitude: 12, zoom: 3 }}
        mapStyle={EMPTY_DARK_STYLE}
        style={{ width: "100%", height: "100%" }}
        attributionControl={false}
        interactiveLayerIds={["admin1-fill", "hotspot-circles"]}
        onLoad={onLoad}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        maxZoom={9}
      >
        <Source id="admin1" type="geojson" data={data}>
          <Layer id="admin1-fill" type="fill" paint={{ "fill-color": ["get", "fillColor"], "fill-opacity": 0.82 }} />
          <Layer id="admin1-line" type="line" paint={{ "line-color": BORDER_COLOR, "line-width": 0.5 }} />
          <Layer
            id="admin1-hover"
            type="line"
            filter={["==", ["get", "admin1_pcode"], hover?.kind === "area" ? hover.pcode : ""]}
            paint={{ "line-color": BORDER_HIGHLIGHT, "line-width": 1.6 }}
          />
        </Source>

        {hotspots && (
          <Source id="hotspots" type="geojson" data={hotspots}>
            <Layer
              id="hotspot-circles"
              type="circle"
              paint={{
                "circle-radius": ["get", "radius"],
                "circle-color": ["get", "color"],
                "circle-opacity": 0.55,
                "circle-stroke-width": 1,
                "circle-stroke-color": ["get", "color"],
              }}
            />
          </Source>
        )}
      </MapGL>

      {hover && (
        <div className="pointer-events-none absolute left-3 top-3 max-w-[15rem] rounded-md border border-border bg-popover/95 px-3 py-2 text-xs shadow-md backdrop-blur">
          <div className="font-medium text-foreground">{hover.title}</div>
          <div className="mt-0.5 space-y-0.5 text-muted-foreground">
            {hover.lines.map((l) => (
              <div key={l} className="tnum">{l}</div>
            ))}
          </div>
        </div>
      )}

      <HotspotLegend />
    </div>
  );
}

function HotspotLegend() {
  return (
    <div className="pointer-events-none absolute bottom-3 right-3 rounded-md border border-border bg-popover/90 px-3 py-2 text-[10px] text-muted-foreground shadow-md backdrop-blur">
      <div className="mb-1 font-medium text-foreground/80">ACLED hotspots</div>
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: chartColors.acute }} /> high recency
        <span className="ml-2 h-2.5 w-2.5 rounded-full" style={{ backgroundColor: chartColors.primary }} /> older
      </div>
      <div className="mt-0.5">circle size ∝ event count</div>
    </div>
  );
}
