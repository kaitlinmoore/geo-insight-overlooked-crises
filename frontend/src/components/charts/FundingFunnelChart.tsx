import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { FundingFunnelStage } from "@/lib/types";
import { chartColors, pct, usdCompact } from "@/lib/chartTheme";

/**
 * Funding funnel as a horizontal per-stage bar chart (NOT a Recharts FunnelChart,
 * which visually exaggerates differences). Stages descend required → paid; each
 * bar is labeled with its dollar amount and % of requirement.
 */
const STAGE_LABEL: Record<FundingFunnelStage["stage"], string> = {
  required: "Required",
  pledged: "Pledged",
  committed: "Committed",
  paid: "Paid",
};

const STAGE_COLOR: Record<FundingFunnelStage["stage"], string> = {
  required: chartColors.muted,
  pledged: "hsl(187 60% 38%)",
  committed: "hsl(187 72% 40%)",
  paid: chartColors.primary,
};

function FunnelTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const s = payload[0].payload as FundingFunnelStage & { label: string };
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="font-medium text-foreground">{s.label}</div>
      <div className="mt-1 text-muted-foreground tnum">
        {usdCompact(s.amount_usd)} · {pct(s.pct_of_requirement)} of requirement
      </div>
    </div>
  );
}

export function FundingFunnelChart({ funnel }: { funnel: FundingFunnelStage[] }) {
  const data = funnel.map((f) => ({ ...f, label: STAGE_LABEL[f.stage] }));
  const max = Math.max(...data.map((d) => d.amount_usd), 1);
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 40)}>
      <BarChart
        layout="vertical"
        data={data}
        margin={{ top: 4, right: 72, bottom: 4, left: 8 }}
        barCategoryGap={8}
      >
        <XAxis type="number" domain={[0, max]} hide />
        <YAxis
          type="category"
          dataKey="label"
          width={78}
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<FunnelTooltip />} cursor={{ fill: "hsl(217 33% 20% / 0.4)" }} />
        <Bar dataKey="amount_usd" radius={[0, 3, 3, 0]} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.stage} fill={STAGE_COLOR[d.stage]} />
          ))}
          <LabelList
            dataKey="amount_usd"
            position="right"
            formatter={(v: number) => usdCompact(v)}
            style={{ fill: chartColors.axis, fontSize: 11 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
