import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Placeholder } from "@/components/Placeholder";
import { NeglectBadge } from "@/components/NeglectBadge";
import { ChangeIndicator } from "@/components/ChangeIndicator";
import { RankCI } from "@/components/RankCI";
import { QueryState } from "@/components/QueryState";
import { ScoreSparkline } from "@/components/charts/ScoreSparkline";
import { neglectColor } from "@/lib/chartTheme";
import { fetchRankings } from "@/lib/api";
import type { CrisisRanking } from "@/lib/types";

type RankMode = "overlooked" | "structural";

function pctNeed(pin: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(pin);
}

function CrisisRow({ row }: { row: CrisisRanking }) {
  return (
    <Link
      to={`/crisis/${row.iso3}`}
      className="group grid grid-cols-[3rem_1fr_auto_1.25rem] items-center gap-4 rounded-md border border-transparent px-3 py-3 transition-colors hover:border-border hover:bg-accent/40"
    >
      <div className="flex flex-col items-center">
        <RankCI rank={row.rank_position} low={row.rank_ci_low} high={row.rank_ci_high} stable={row.stable_top_n} />
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium">{row.country_name}</span>
          <span className="text-xs text-muted-foreground">{row.iso3}</span>
          <ChangeIndicator direction={row.change_direction} magnitude={row.change_magnitude} />
          {row.data_sparsity_flag && (
            <Badge variant="outline" className="text-[10px] text-muted-foreground">
              admin1 sparse
            </Badge>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>{row.region}</span>
          <span className="tnum">{pctNeed(row.people_in_need)} PIN</span>
          <span className="tnum">{Math.round(row.gap_ratio * 100)}% unfunded</span>
          <span className="tnum">INFORM {row.inform_severity.toFixed(1)}</span>
          <NeglectBadge value={row.neglect_class} />
        </div>
      </div>

      <div className="flex flex-col items-end" title="overlooked_score, last 5 years">
        <ScoreSparkline data={row.score_history} color={neglectColor[row.neglect_class]} />
      </div>

      <ChevronRight className="h-4 w-4 justify-self-end text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </Link>
  );
}

export function TriageScreen() {
  const [mode, setMode] = useState<RankMode>("overlooked");
  const [region, setRegion] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["rankings", 2026],
    queryFn: () => fetchRankings({ year: 2026 }),
  });

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.4fr_1fr]">
      <QueryState query={query} skeleton={<TriageSkeleton />}>
        {(data) => <TriageBody data={data.rankings} mode={mode} setMode={setMode} region={region} setRegion={setRegion} />}
      </QueryState>
    </div>
  );
}

function TriageBody({
  data,
  mode,
  setMode,
  region,
  setRegion,
}: {
  data: CrisisRanking[];
  mode: RankMode;
  setMode: (m: RankMode) => void;
  region: string | null;
  setRegion: (r: string | null) => void;
}) {
  const regions = useMemo(
    () => Array.from(new Set(data.map((r) => r.region))).sort(),
    [data]
  );

  const rows = useMemo(() => {
    let r = [...data];
    if (region) r = r.filter((x) => x.region === region);
    if (mode === "structural") {
      r = r
        .filter((x) => x.neglect_class === "chronic_neglect" || x.neglect_class === "chronic_no_plan")
        .sort((a, b) => b.overlooked_score - a.overlooked_score);
    } else {
      r = r.sort((a, b) => a.rank_position - b.rank_position);
    }
    return r;
  }, [data, mode, region]);

  const newCount = data.filter((r) => r.change_direction === "new").length;
  const noPlanCount = data.filter((r) => r.neglect_class === "chronic_no_plan").length;

  return (
    <>
      <div className="space-y-4 xl:order-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Global overview</CardTitle>
          </CardHeader>
          <CardContent>
            <Placeholder
              height="h-[420px]"
              label="[Global choropleth map]"
              detail="admin0 overlooked_score percentile · MapLibre + react-map-gl · maps are a separate workstream (GeoJSON from fieldmaps GeoParquet)"
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">This period</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-semibold tnum">{data.length}</div>
              <div className="text-xs text-muted-foreground">crises ranked</div>
            </div>
            <div>
              <div className="text-2xl font-semibold tnum text-acute">{newCount}</div>
              <div className="text-xs text-muted-foreground">new to top 10</div>
            </div>
            <div>
              <div className="text-2xl font-semibold tnum text-noplan">{noPlanCount}</div>
              <div className="text-xs text-muted-foreground">chronic, no plan</div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4 xl:order-1">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Most overlooked crises</h1>
            <p className="text-sm text-muted-foreground">
              {mode === "overlooked"
                ? "Ranked by current overlooked_score."
                : "Ranked by structural neglect (chronic + no-plan)."}
            </p>
          </div>
          <Tabs value={mode} onValueChange={(v) => setMode(v as RankMode)}>
            <TabsList>
              <TabsTrigger value="overlooked">Current mismatch</TabsTrigger>
              <TabsTrigger value="structural">Structural neglect</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant={region === null ? "secondary" : "ghost"} size="sm" onClick={() => setRegion(null)}>
            All regions
          </Button>
          {regions.map((reg) => (
            <Button
              key={reg}
              variant={region === reg ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setRegion(reg)}
              className="text-xs"
            >
              {reg}
            </Button>
          ))}
        </div>

        <Card>
          <CardContent className="divide-y divide-border/60 p-2">
            {rows.length === 0 ? (
              <p className="p-6 text-center text-sm text-muted-foreground">No crises match the current filters.</p>
            ) : (
              rows.map((row) => <CrisisRow key={row.iso3} row={row} />)
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function TriageSkeleton() {
  return (
    <>
      <div className="space-y-4 xl:order-2">
        <Skeleton className="h-[480px] w-full" />
      </div>
      <div className="space-y-4 xl:order-1">
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-8 w-full" />
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    </>
  );
}
