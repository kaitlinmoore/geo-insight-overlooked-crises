import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import MapGL, { Layer, Source } from "react-map-gl/maplibre";
import type { MapLayerMouseEvent } from "react-map-gl/maplibre";
import type { FeatureCollection } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import { Skeleton } from "@/components/ui/skeleton";
import { NEGLECT_CLASS_META } from "@/lib/types";
import type { CrisisRanking, NeglectClass } from "@/lib/types";
import { neglectColor } from "@/lib/chartTheme";
import { BORDER_COLOR, BORDER_HIGHLIGHT, EMPTY_DARK_STYLE, NEUTRAL_FILL } from "./mapStyle";

type HoverInfo = {
  lng: number;
  lat: number;
  iso3: string;
  country: string;
  rank: number | null;
  neglect: NeglectClass | null;
};

async function fetchAdmin0(): Promise<FeatureCollection> {
  const res = await fetch("/maps/admin0.geojson");
  if (!res.ok) throw new Error(`admin0.geojson ${res.status}`);
  return (await res.json()) as FeatureCollection;
}

/**
 * Global admin0 choropleth. Each country polygon is filled by its neglect_class
 * color (ties the map to the row badges + sparklines); countries with no ranking
 * get a neutral fill. Hover -> tooltip; click -> Crisis Explorer.
 */
export function TriageMap({ rankings }: { rankings: CrisisRanking[] }) {
  const navigate = useNavigate();
  const [hover, setHover] = useState<HoverInfo | null>(null);

  const geo = useQuery({ queryKey: ["geojson", "admin0"], queryFn: fetchAdmin0, staleTime: Infinity });

  const byIso = useMemo(() => {
    const m = new Map<string, CrisisRanking>();
    for (const r of rankings) m.set(r.iso3, r);
    return m;
  }, [rankings]);

  // Inject fill color + lookup fields onto each feature (data-driven paint reads them).
  const data = useMemo<FeatureCollection | null>(() => {
    if (!geo.data) return null;
    return {
      type: "FeatureCollection",
      features: geo.data.features.map((f) => {
        const iso3 = (f.properties?.iso3 as string) ?? "";
        const r = byIso.get(iso3);
        return {
          ...f,
          properties: {
            iso3,
            country_name: (f.properties?.country_name as string) ?? iso3,
            fillColor: r ? neglectColor[r.neglect_class] : NEUTRAL_FILL,
            ranked: r ? 1 : 0,
            rank: r?.rank_position ?? null,
            neglect: r?.neglect_class ?? null,
          },
        };
      }),
    };
  }, [geo.data, byIso]);

  if (geo.isLoading) return <Skeleton className="h-[420px] w-full" />;
  if (geo.isError || !data)
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
        Map data unavailable — run <code className="mx-1">extract_geojson.py</code> to generate /maps/admin0.geojson
      </div>
    );

  const onMove = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0];
    if (!f) {
      setHover(null);
      return;
    }
    const p = f.properties as Record<string, unknown>;
    setHover({
      lng: e.lngLat.lng,
      lat: e.lngLat.lat,
      iso3: (p.iso3 as string) ?? "",
      country: (p.country_name as string) ?? "",
      rank: p.ranked ? (p.rank as number) : null,
      neglect: p.ranked ? (p.neglect as NeglectClass) : null,
    });
  };

  const onClick = (e: MapLayerMouseEvent) => {
    const p = e.features?.[0]?.properties as Record<string, unknown> | undefined;
    if (p?.ranked) navigate(`/crisis/${p.iso3 as string}`);
  };

  return (
    <div className="relative h-[420px] w-full overflow-hidden rounded-lg border border-border">
      <MapGL
        initialViewState={{ longitude: 12, latitude: 18, zoom: 1.25 }}
        mapStyle={EMPTY_DARK_STYLE}
        style={{ width: "100%", height: "100%" }}
        attributionControl={false}
        interactiveLayerIds={["admin0-fill"]}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        onClick={onClick}
        cursor={hover?.rank ? "pointer" : "default"}
        maxZoom={6}
        minZoom={0.5}
      >
        <Source id="admin0" type="geojson" data={data}>
          <Layer
            id="admin0-fill"
            type="fill"
            paint={{ "fill-color": ["get", "fillColor"], "fill-opacity": ["case", ["==", ["get", "ranked"], 1], 0.85, 0.5] }}
          />
          <Layer id="admin0-line" type="line" paint={{ "line-color": BORDER_COLOR, "line-width": 0.4 }} />
          <Layer
            id="admin0-hover"
            type="line"
            filter={["==", ["get", "iso3"], hover?.iso3 ?? ""]}
            paint={{ "line-color": BORDER_HIGHLIGHT, "line-width": 1.4 }}
          />
        </Source>
      </MapGL>

      {hover && (
        <div
          className="pointer-events-none absolute left-3 top-3 max-w-[16rem] rounded-md border border-border bg-popover/95 px-3 py-2 text-xs shadow-md backdrop-blur"
        >
          <div className="font-medium text-foreground">
            {hover.country} <span className="text-muted-foreground">{hover.iso3}</span>
          </div>
          {hover.rank ? (
            <div className="mt-0.5 flex items-center gap-2 text-muted-foreground">
              <span className="tnum">Rank #{hover.rank}</span>
              {hover.neglect && (
                <span className={NEGLECT_CLASS_META[hover.neglect].tokenClass}>
                  {NEGLECT_CLASS_META[hover.neglect].label}
                </span>
              )}
            </div>
          ) : (
            <div className="mt-0.5 text-muted-foreground/70">Not in the current ranking</div>
          )}
        </div>
      )}

      <Legend />
    </div>
  );
}

function Legend() {
  const items: Array<{ label: string; cls: NeglectClass }> = [
    { label: "Chronic neglect", cls: "chronic_neglect" },
    { label: "Acute deterioration", cls: "acute_deterioration" },
    { label: "Chronic, no plan", cls: "chronic_no_plan" },
    { label: "Improving / funded", cls: "improving" },
  ];
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 rounded-md border border-border bg-popover/90 px-3 py-2 text-[10px] shadow-md backdrop-blur">
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        {items.map((it) => (
          <span key={it.cls} className="flex items-center gap-1.5 text-muted-foreground">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: neglectColor[it.cls] }} />
            {it.label}
          </span>
        ))}
      </div>
    </div>
  );
}
