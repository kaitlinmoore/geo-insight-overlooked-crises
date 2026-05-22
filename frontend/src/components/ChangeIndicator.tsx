import { ArrowDown, ArrowUp, Minus, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChangeDirection } from "@/lib/mockData";

/**
 * Triage change indicator: `↑5 positions`, `NEW to top 10`, `↓3`, or `—`.
 * "up" means more overlooked (worse) — colored as a warning, not success.
 */
export function ChangeIndicator({
  direction,
  magnitude,
}: {
  direction: ChangeDirection;
  magnitude: number;
}) {
  if (direction === "new") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-noplan">
        <Sparkles className="h-3.5 w-3.5" /> NEW
      </span>
    );
  }
  if (direction === "same" || magnitude === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
        <Minus className="h-3.5 w-3.5" /> —
      </span>
    );
  }
  const up = direction === "up";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-medium tnum",
        up ? "text-acute" : "text-improving"
      )}
    >
      {up ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />}
      {magnitude}
    </span>
  );
}
