import { cn } from "@/lib/utils";

/**
 * Honest rank display: "#2  [#1–3]". The bootstrap CI travels with every rank
 * (methodology.md "Bootstrap uncertainty"). Never show a rank without it.
 */
export function RankCI({
  rank,
  low,
  high,
  stable,
  className,
}: {
  rank: number;
  low: number;
  high: number;
  stable?: boolean;
  className?: string;
}) {
  const wide = high - low >= 5;
  return (
    <span className={cn("inline-flex items-baseline gap-1.5 tnum", className)}>
      <span className="font-semibold">#{rank}</span>
      <span
        className={cn(
          "text-xs",
          wide ? "text-acute" : "text-muted-foreground",
          stable && "text-improving"
        )}
        title={
          wide
            ? "Wide confidence interval — rank is uncertain"
            : stable
              ? "Stable across ≥90% of bootstrap samples"
              : "95% bootstrap CI on rank position"
        }
      >
        [#{low}–{high}]
      </span>
    </span>
  );
}
