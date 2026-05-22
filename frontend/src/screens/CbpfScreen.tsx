import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { QueryState } from "@/components/QueryState";
import { RankCI } from "@/components/RankCI";
import { chartColors, usdCompact } from "@/lib/chartTheme";
import { fetchCbpf, fetchCrisis } from "@/lib/api";
import type { CbpfResponse, CbpfFund } from "@/lib/types";

function AllocTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const a = payload[0].payload as { reserve_usd: number; standard_usd: number; allocated_usd: number; label: string };
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="font-medium text-foreground">{a.label}</div>
      <div className="mt-1 text-muted-foreground tnum">
        Reserve {usdCompact(a.reserve_usd)} · Standard {usdCompact(a.standard_usd)}
      </div>
    </div>
  );
}

function FundCard({ fund }: { fund: CbpfFund }) {
  // Per-country rank lookup so allocations show alongside overlooked-ness.
  const isoQueries = fund.allocations.map((a) => a.iso3);
  const rankQuery = useQuery({
    queryKey: ["cbpf-rank", fund.fund_id, isoQueries],
    queryFn: async () => {
      const out: Record<string, Awaited<ReturnType<typeof fetchCrisis>>["ranking"]> = {};
      for (const iso of isoQueries) {
        out[iso] = (await fetchCrisis(iso)).ranking;
      }
      return out;
    },
  });

  const barData = fund.allocations.map((a) => ({
    ...a,
    label: a.country_name,
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{fund.fund_name}</CardTitle>
        <CardDescription>
          {fund.fund_id} · operates in {fund.countries.join(", ")}
          {fund.sector_breakdown.length === 0 && " · no sector breakdown (CBPF has no allocation-level sector tag)"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="py-1 pr-4 font-medium">Country</th>
              <th className="py-1 pr-4 font-medium">Reserve</th>
              <th className="py-1 pr-4 font-medium">Standard</th>
              <th className="py-1 pr-4 font-medium">Total</th>
              <th className="py-1 pr-4 font-medium">Overlooked rank</th>
            </tr>
          </thead>
          <tbody>
            {fund.allocations.map((a) => {
              const r = rankQuery.data?.[a.iso3];
              return (
                <tr key={a.iso3} className="border-b border-border/40">
                  <td className="py-1.5 pr-4">
                    {a.country_name} <span className="text-xs text-muted-foreground">{a.iso3}</span>
                  </td>
                  <td className="py-1.5 pr-4 tnum">{usdCompact(a.reserve_usd)}</td>
                  <td className="py-1.5 pr-4 tnum">{usdCompact(a.standard_usd)}</td>
                  <td className="py-1.5 pr-4 tnum">{usdCompact(a.allocated_usd)}</td>
                  <td className="py-1.5 pr-4">
                    {r ? (
                      <RankCI rank={r.rank_position} low={r.rank_ci_low} high={r.rank_ci_high} stable={r.stable_top_n} />
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <div>
          <div className="mb-1 text-xs font-medium text-muted-foreground">Allocation by window (reserve vs standard)</div>
          <ResponsiveContainer width="100%" height={Math.max(120, barData.length * 56)}>
            <BarChart layout="vertical" data={barData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
              <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={usdCompact} tick={{ fill: chartColors.axis, fontSize: 11 }} axisLine={{ stroke: chartColors.grid }} tickLine={false} />
              <YAxis type="category" dataKey="label" width={120} tick={{ fill: chartColors.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<AllocTooltip />} cursor={{ fill: "hsl(217 33% 20% / 0.4)" }} />
              <Bar dataKey="reserve_usd" stackId="a" radius={[0, 0, 0, 0]} isAnimationActive={false}>
                {barData.map((d) => (
                  <Cell key={`r-${d.iso3}`} fill={chartColors.primary} />
                ))}
              </Bar>
              <Bar dataKey="standard_usd" stackId="a" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                {barData.map((d) => (
                  <Cell key={`s-${d.iso3}`} fill={chartColors.muted} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-1 flex gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: chartColors.primary }} /> Reserve</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: chartColors.muted }} /> Standard</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function CbpfScreen() {
  const query = useQuery({ queryKey: ["cbpf", 2026], queryFn: () => fetchCbpf(2026) });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-tight">CBPF Allocation View</h1>
        <Badge variant="outline" className="text-[10px] text-muted-foreground">optional · PFM</Badge>
      </div>
      <p className="-mt-4 text-sm text-muted-foreground">
        Fund-scoped: ranking filtered to the countries the selected fund operates in. Allocation history
        shown <em>alongside</em> overlooked-ness, never blended into it.
      </p>

      <QueryState query={query} skeleton={<Skeleton className="h-80 w-full" />}>
        {(data: CbpfResponse) => (
          <div className="space-y-6">
            <p className="text-xs text-muted-foreground tnum">Allocation year {data.year}</p>
            {data.funds.map((fund) => (
              <FundCard key={fund.fund_id} fund={fund} />
            ))}
          </div>
        )}
      </QueryState>
    </div>
  );
}
