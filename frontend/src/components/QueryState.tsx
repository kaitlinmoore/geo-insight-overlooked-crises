import type { UseQueryResult } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Renders a TanStack Query result with consistent loading / error / success
 * states across screens. The loading state uses shadcn's Skeleton; the error
 * state surfaces the message (honest failure, not a silent empty screen).
 */
export function QueryState<T>({
  query,
  children,
  skeleton,
}: {
  query: UseQueryResult<T>;
  children: (data: T) => React.ReactNode;
  skeleton?: React.ReactNode;
}) {
  if (query.isPending) {
    return <>{skeleton ?? <DefaultSkeleton />}</>;
  }
  if (query.isError) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>
          Couldn’t load data: {query.error instanceof Error ? query.error.message : "unknown error"}.
          Is the API running on :8000?
        </span>
      </div>
    );
  }
  return <>{children(query.data)}</>;
}

function DefaultSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}
