import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Placeholder } from "@/components/Placeholder";
import { cn } from "@/lib/utils";
import { MOCK_COMPARE_METRICS } from "@/lib/mockData";

const SELECTED = ["SDN", "COD", "BFA"]; // 2–4 countries; mocked selection

export function CompareScreen() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Compare crises</h1>
        <p className="text-sm text-muted-foreground">
          Side-by-side across 2–4 countries, metrics aligned on a shared 0–1 scale.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Country selection</CardTitle>
          <CardDescription>
            [Multi-select country picker — 2 to 4 — will replace this fixed set]
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          {SELECTED.map((iso) => (
            <span key={iso} className="rounded-md bg-secondary px-3 py-1 text-sm font-medium">
              {iso}
            </span>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Aligned metrics</CardTitle>
          <CardDescription>Each metric on its own shared scale.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {MOCK_COMPARE_METRICS.map((m) => (
            <div key={m.metric_key} className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">{m.label}</div>
              <div className="grid grid-cols-[4rem_1fr_3rem] items-center gap-3">
                {SELECTED.map((iso) => {
                  const v = m.values[iso] ?? 0;
                  return (
                    <div key={iso} className="contents">
                      <span className="text-sm tnum">{iso}</span>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className={cn("h-full rounded-full bg-primary")}
                          style={{ width: `${v * 100}%` }}
                        />
                      </div>
                      <span className="text-right text-xs tnum text-muted-foreground">
                        {Math.round(v * 100)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Trend overlay</CardTitle>
        </CardHeader>
        <CardContent>
          <Placeholder
            height="h-72"
            label="[Recharts multi-series line: gap_ratio over time per country]"
            detail="gold_funding_trend joined across the selected countries"
          />
        </CardContent>
      </Card>
    </div>
  );
}
