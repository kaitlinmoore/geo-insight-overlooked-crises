import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { NEGLECT_CLASS_META, type NeglectClass } from "@/lib/mockData";

export function NeglectBadge({ value }: { value: NeglectClass }) {
  const meta = NEGLECT_CLASS_META[value];
  return (
    <Badge variant="outline" className={cn("gap-1.5 border-border", meta.tokenClass)}>
      <span className={cn("h-1.5 w-1.5 rounded-full bg-current")} aria-hidden />
      {meta.label}
    </Badge>
  );
}
