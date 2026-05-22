import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { SectorCoverage } from "@/lib/types";
import { chartColors, pct, usdCompact } from "@/lib/chartTheme";

/**
 * Horizontal bar chart of sector funding gaps. Bars are red when the sector is
 * a flagged gap (gap > 70% AND PIN share ≥ 10%), gray otherwise. X axis is
 * locked to 0–100% so gaps are comparable across countries.
 */
function GapTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const s = payload[0].payload as SectorCoverage;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="font-medium text-foreground">{s.sector}</div>
      <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-muted-foreground">
        <span>Gap</span>
        <span className="text-right tnum text-foreground">{pct(s.sector_gap)}</span>
        <span>PIN share</span>
        <span className="text-right tnum text-foreground">{pct(s.pin_share)}</span>
        <span>Required</span>
        <span className="text-right tnum text-foreground">{usdCompact(s.requirement_usd)}</span>
        <span>Funded</span>
        <span className="text-right tnum text-foreground">{usdCompact(s.funding_usd)}</span>
      </div>
      {s.is_flagged_gap && <div className="mt-1 text-acute">Flagged gap</div>}
    </div>
  );
}

export function SectorGapChart({ sectors }: { sectors: SectorCoverage[] }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, sectors.length * 34)}>
      <BarChart
        layout="vertical"
        data={sectors}
        margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
        barCategoryGap={6}
      >
        <XAxis
          type="number"
          domain={[0, 1]}
          tickFormatter={pct}
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          axisLine={{ stroke: chartColors.grid }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="sector"
          width={92}
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<GapTooltip />} cursor={{ fill: "hsl(217 33% 20% / 0.4)" }} />
        <Bar dataKey="sector_gap" radius={[0, 3, 3, 0]} isAnimationActive={false}>
          {sectors.map((s) => (
            <Cell key={s.sector} fill={s.is_flagged_gap ? chartColors.acute : chartColors.muted} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
