import { Line, LineChart } from "recharts";
import type { ScoreHistoryPoint } from "@/lib/types";
import { chartColors } from "@/lib/chartTheme";

/**
 * Tiny axis-less sparkline of a country's overlooked_score history, sized for a
 * Triage row. Fixed dimensions (not responsive) to keep the list cheap to render.
 */
export function ScoreSparkline({
  data,
  color = chartColors.primary,
  width = 72,
  height = 26,
}: {
  data: ScoreHistoryPoint[];
  color?: string;
  width?: number;
  height?: number;
}) {
  if (!data || data.length < 2) return null;
  return (
    <LineChart
      width={width}
      height={height}
      data={data}
      margin={{ top: 3, right: 2, bottom: 3, left: 2 }}
    >
      <Line
        type="monotone"
        dataKey="overlooked_score"
        stroke={color}
        strokeWidth={1.5}
        dot={false}
        isAnimationActive={false}
      />
    </LineChart>
  );
}
