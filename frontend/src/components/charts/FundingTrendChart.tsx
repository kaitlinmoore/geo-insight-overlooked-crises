import {
  CartesianGrid,
  Dot,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { FundingTrendPoint } from "@/lib/types";
import { chartColors, pct } from "@/lib/chartTheme";

/**
 * Multi-year funding-gap trend. Y axis locked 0–1 (gap_ratio). A dashed
 * reference line marks the 0.5 chronic threshold; years above it (which would
 * count toward chronic_neglect) get an orange dot.
 */
const CHRONIC_THRESHOLD = 0.5;

function TrendTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0].payload as FundingTrendPoint;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="font-medium text-foreground">{label}</div>
      <div className="mt-1 text-muted-foreground tnum">
        Gap {pct(p.gap_ratio)}
        {p.gap_ratio >= CHRONIC_THRESHOLD && <span className="ml-1 text-chronic">· chronic</span>}
      </div>
    </div>
  );
}

export function FundingTrendChart({ trend }: { trend: FundingTrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={trend} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="year"
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          axisLine={{ stroke: chartColors.grid }}
          tickLine={false}
        />
        <YAxis
          domain={[0, 1]}
          tickFormatter={pct}
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={36}
        />
        <Tooltip content={<TrendTooltip />} />
        <ReferenceLine
          y={CHRONIC_THRESHOLD}
          stroke={chartColors.reference}
          strokeDasharray="4 4"
          label={{ value: "chronic 50%", position: "insideTopRight", fill: chartColors.reference, fontSize: 10 }}
        />
        <Line
          type="monotone"
          dataKey="gap_ratio"
          stroke={chartColors.primary}
          strokeWidth={2}
          isAnimationActive={false}
          dot={(props) => {
            const { cx, cy, payload, key } = props as unknown as {
              cx: number;
              cy: number;
              payload: FundingTrendPoint;
              key: string;
            };
            const chronic = payload.gap_ratio >= CHRONIC_THRESHOLD;
            return (
              <Dot
                key={key}
                cx={cx}
                cy={cy}
                r={3.5}
                fill={chronic ? chartColors.chronic : chartColors.primary}
                stroke="none"
              />
            );
          }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
