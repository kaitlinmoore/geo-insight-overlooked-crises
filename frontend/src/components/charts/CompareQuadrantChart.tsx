import {
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { CrisisRanking } from "@/lib/types";
import { chartColors, neglectColor, pct } from "@/lib/chartTheme";
import { NEGLECT_CLASS_META } from "@/lib/types";

/**
 * Compare quadrant: chronic_index (percentile) on X, gap_ratio on Y, point
 * size ∝ people_in_need, colored by neglect_class. Reads the full ranking rows
 * the /compare endpoint returns. chronic_index here is the WITHIN-YEAR
 * PERCENTILE (0–1), consistent with how the composite normalizes it.
 */
interface Point {
  iso3: string;
  country_name: string;
  chronic_pct: number;
  gap_ratio: number;
  pin: number;
  neglect_class: CrisisRanking["neglect_class"];
}

function toPoints(rankings: CrisisRanking[]): Point[] {
  return rankings.map((r) => ({
    iso3: r.iso3,
    country_name: r.country_name,
    chronic_pct: r.components.find((c) => c.key === "chronic_index")?.percentile ?? 0,
    gap_ratio: r.gap_ratio,
    pin: r.people_in_need,
    neglect_class: r.neglect_class,
  }));
}

function QuadrantTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0].payload as Point;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="font-medium text-foreground">
        {p.country_name} <span className="text-muted-foreground">{p.iso3}</span>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-x-3 text-muted-foreground">
        <span>Chronic pct</span>
        <span className="text-right tnum text-foreground">{pct(p.chronic_pct)}</span>
        <span>Funding gap</span>
        <span className="text-right tnum text-foreground">{pct(p.gap_ratio)}</span>
        <span>Neglect</span>
        <span className="text-right text-foreground">{NEGLECT_CLASS_META[p.neglect_class].label}</span>
      </div>
    </div>
  );
}

export function CompareQuadrantChart({ rankings }: { rankings: CrisisRanking[] }) {
  const points = toPoints(rankings);
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ScatterChart margin={{ top: 16, right: 24, bottom: 28, left: 8 }}>
        <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="chronic_pct"
          name="Chronic index (pct)"
          domain={[0, 1]}
          tickFormatter={pct}
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          axisLine={{ stroke: chartColors.grid }}
          tickLine={false}
          label={{ value: "Chronic index (percentile)", position: "insideBottom", offset: -16, fill: chartColors.axis, fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="gap_ratio"
          name="Funding gap"
          domain={[0, 1]}
          tickFormatter={pct}
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={40}
          label={{ value: "Funding gap", angle: -90, position: "insideLeft", fill: chartColors.axis, fontSize: 11 }}
        />
        <ZAxis type="number" dataKey="pin" range={[80, 600]} name="PIN" />
        <Tooltip content={<QuadrantTooltip />} cursor={{ strokeDasharray: "3 3" }} />
        <Scatter data={points} isAnimationActive={false}>
          {points.map((p) => (
            <Cell key={p.iso3} fill={neglectColor[p.neglect_class]} fillOpacity={0.8} />
          ))}
          <LabelList
            dataKey="iso3"
            position="top"
            style={{ fill: chartColors.axis, fontSize: 10 }}
          />
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}
