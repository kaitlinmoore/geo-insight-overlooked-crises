/**
 * chartTheme.ts — concrete colors for Recharts.
 *
 * Recharts renders SVG and won't reliably resolve `hsl(var(--token))` in fill
 * attributes, so these are literal HSL values that MATCH the dark-mode tokens
 * in `index.css`. Keep them in sync if the theme changes.
 */
import type { NeglectClass } from "@/lib/types";

export const chartColors = {
  primary: "hsl(187 85% 43%)", // teal — default series / "on track"
  acute: "hsl(0 72% 58%)", // red — flagged gaps, acute deterioration
  chronic: "hsl(25 90% 55%)", // orange — chronic neglect
  improving: "hsl(142 65% 47%)", // green — improving / well funded
  noplan: "hsl(270 65% 68%)", // purple — chronic, no plan
  muted: "hsl(217 33% 32%)", // gray — unflagged bars
  grid: "hsl(217 33% 20%)", // gridlines / borders
  axis: "hsl(215 20% 65%)", // axis text (muted-foreground)
  reference: "hsl(25 90% 55%)", // threshold reference lines
} as const;

/** neglect_class -> chart color (matches NEGLECT_CLASS_META token intent). */
export const neglectColor: Record<NeglectClass, string> = {
  chronic_neglect: chartColors.chronic,
  acute_deterioration: chartColors.acute,
  improving: chartColors.improving,
  well_funded: chartColors.improving,
  chronic_no_plan: chartColors.noplan,
};

/** Compact USD formatter for axis ticks and tooltips. */
export const usdCompact = (n: number) =>
  new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
    style: "currency",
    currency: "USD",
  }).format(n);

export const pct = (n: number) => `${Math.round(n * 100)}%`;
