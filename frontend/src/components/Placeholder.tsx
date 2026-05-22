import { cn } from "@/lib/utils";

/**
 * A labeled placeholder for a visualization that is intentionally NOT built in
 * the scaffolding session. The label states exactly what will eventually go
 * here (chart type, data shape, library) so the next session has a spec.
 */
export function Placeholder({
  label,
  detail,
  className,
  height = "h-64",
}: {
  label: string;
  detail?: string;
  className?: string;
  height?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 p-4 text-center",
        height,
        className
      )}
    >
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      {detail ? (
        <span className="mt-1 max-w-md text-xs text-muted-foreground/70">{detail}</span>
      ) : null}
    </div>
  );
}
