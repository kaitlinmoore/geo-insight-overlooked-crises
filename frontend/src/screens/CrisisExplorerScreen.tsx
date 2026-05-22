import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Placeholder } from "@/components/Placeholder";
import { NeglectBadge } from "@/components/NeglectBadge";
import { RankCI } from "@/components/RankCI";
import { QueryState } from "@/components/QueryState";
import { SectorGapChart } from "@/components/charts/SectorGapChart";
import { FundingFunnelChart } from "@/components/charts/FundingFunnelChart";
import { FundingTrendChart } from "@/components/charts/FundingTrendChart";
import { cn } from "@/lib/utils";
import { fetchCrisis } from "@/lib/api";
import type { CrisisDetail, ScoreComponent } from "@/lib/types";

function DecompositionRow({ c }: { c: ScoreComponent }) {
  const negative = c.contribution < 0;
  const width = Math.min(100, Math.abs(c.contribution) * 220);
  return (
    <div className="grid grid-cols-[10rem_1fr_4rem] items-center gap-3 py-1.5 text-sm">
      <span className="truncate text-muted-foreground">{c.label}</span>
      <div className="flex items-center">
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full", negative ? "bg-improving" : "bg-primary")}
            style={{ width: `${width}%` }}
          />
        </div>
      </div>
      <span className={cn("text-right tnum", negative ? "text-improving" : "text-foreground")}>
        {negative ? "−" : "+"}
        {Math.abs(c.contribution).toFixed(2)}
      </span>
    </div>
  );
}

export function CrisisExplorerScreen() {
  const { iso3 } = useParams();
  const query = useQuery({
    queryKey: ["crisis", iso3],
    queryFn: () => fetchCrisis(iso3 ?? ""),
    enabled: Boolean(iso3),
  });

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/">
          <ArrowLeft className="h-4 w-4" /> Triage
        </Link>
      </Button>
      <QueryState query={query} skeleton={<CrisisSkeleton />}>
        {(detail) => <CrisisBody detail={detail} />}
      </QueryState>
    </div>
  );
}

function CrisisBody({ detail }: { detail: CrisisDetail }) {
  const r = detail.ranking;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{r.country_name}</h1>
            <span className="text-sm text-muted-foreground">{r.iso3}</span>
            <NeglectBadge value={r.neglect_class} />
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              Rank <RankCI rank={r.rank_position} low={r.rank_ci_low} high={r.rank_ci_high} stable={r.stable_top_n} />
            </span>
            <span className="tnum">{Math.round(r.gap_ratio * 100)}% unfunded</span>
            <span className="tnum">INFORM {r.inform_severity.toFixed(1)}</span>
            <span>{r.region}</span>
          </div>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          <div>HNO updated: {r.hno_last_updated ?? "unknown / stale"}</div>
          {r.data_sparsity_flag && <div className="text-acute">admin1 data sparse</div>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Deterministic decomposition */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Why this rank — deterministic decomposition</CardTitle>
            <CardDescription>Within-year percentile × nominal weight. Drivers sorted by contribution.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-border/40">
              {r.components.map((c) => (
                <DecompositionRow key={c.key} c={c} />
              ))}
            </div>
            <Separator className="my-3" />
            <p className="text-xs text-muted-foreground">
              Media attention carries a negative weight — visibility reduces overlooked-ness.
              Geographic isolation interacts with severity rate.
            </p>
          </CardContent>
        </Card>

        {/* Sector decomposition bar chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Sector coverage</CardTitle>
            <CardDescription>Funding gap by sector. Red = flagged (gap &gt; 70% &amp; PIN share ≥ 10%).</CardDescription>
          </CardHeader>
          <CardContent>
            <SectorGapChart sectors={detail.sectors} />
          </CardContent>
        </Card>

        {/* Funding funnel */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Funding funnel</CardTitle>
            <CardDescription>Required → pledged → committed → paid.</CardDescription>
          </CardHeader>
          <CardContent>
            <FundingFunnelChart funnel={detail.funnel} />
          </CardContent>
        </Card>

        {/* Multi-year trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Multi-year funding trend</CardTitle>
            <CardDescription>gap_ratio per year; dashed line marks the 50% chronic threshold.</CardDescription>
          </CardHeader>
          <CardContent>
            <FundingTrendChart trend={detail.trend} />
          </CardContent>
        </Card>
      </div>

      {/* Subnational */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Subnational severity (admin1)</CardTitle>
          <CardDescription>
            {detail.subnational.length > 0
              ? `${detail.subnational.length} admin1 areas · ${detail.subnational.filter((a) => a.is_hotspot).length} ACLED hotspot(s)`
              : "No machine-readable admin1 data — ranked at country level."}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Placeholder
            height="h-64"
            label="[Subnational choropleth: admin1 overlooked_score]"
            detail="MapLibre fill from gold_subnational_index + ACLED hotspot overlay — maps are a separate workstream"
          />
          {detail.subnational.length > 0 ? (
            <ul className="space-y-1 self-center text-sm">
              {detail.subnational.map((a) => (
                <li key={a.pcode} className="flex items-center justify-between border-b border-border/40 py-1">
                  <span className="flex items-center gap-2">
                    {a.admin1_name}
                    {a.is_hotspot && <Badge variant="destructive" className="text-[10px]">hotspot</Badge>}
                  </span>
                  <span className="tnum text-muted-foreground">INFORM {a.inform_severity.toFixed(1)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="self-center text-sm text-muted-foreground">
              This country carries a <code>data_sparsity_flag</code>; the national rank may reflect one
              severe area or broad moderate need — the distinction isn’t resolvable without admin1 data.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Narrative (KA stretch) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Narrative context</CardTitle>
          <CardDescription>Optional Knowledge-Assistant panel — Day 4 stretch goal.</CardDescription>
        </CardHeader>
        <CardContent>
          {detail.narrative ? (
            <p className="text-sm">{detail.narrative}</p>
          ) : (
            <Placeholder
              height="h-24"
              label="[KA narrative panel — dormant until stretch goal lands]"
              detail="ReliefWeb situation reports via Vector Search; renders only when KA is enabled"
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function CrisisSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-1/2" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-64 w-full" />
        ))}
      </div>
    </div>
  );
}
