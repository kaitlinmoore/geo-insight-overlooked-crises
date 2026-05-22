import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Placeholder } from "@/components/Placeholder";
import { QueryState } from "@/components/QueryState";
import { fetchCascadeDistribution, fetchCompositeWeights } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { CompositeWeightsResponse, CascadeResponse } from "@/lib/types";

const RAI_JUDGES = [
  "grounded_numerics",
  "citation_completeness",
  "honest_uncertainty",
  "geographic_fairness",
  "counterfactual_stability",
  "driver_disclosure",
  "decision_support_framing",
];

export function MethodologyScreen() {
  const weightsQuery = useQuery({ queryKey: ["weights"], queryFn: fetchCompositeWeights });
  const cascadeQuery = useQuery({ queryKey: ["cascade"], queryFn: fetchCascadeDistribution });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Methodology &amp; validation</h1>
        <p className="text-sm text-muted-foreground">How the overlooked_score is computed, and the evidence it holds up.</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Composite weights — live from /methodology/composite-weights */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Composite weights</CardTitle>
            <CardDescription>Seven within-year percentile components; media attention is negative.</CardDescription>
          </CardHeader>
          <CardContent>
            <QueryState query={weightsQuery} skeleton={<Skeleton className="h-48 w-full" />}>
              {(data: CompositeWeightsResponse) => <WeightBars data={data} />}
            </QueryState>
          </CardContent>
        </Card>

        {/* Cascade distribution — live from /methodology/cascade-distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Multi-country flow cascade</CardTitle>
            <CardDescription>Share of flow dollars handled by each allocation method.</CardDescription>
          </CardHeader>
          <CardContent>
            <QueryState query={cascadeQuery} skeleton={<Skeleton className="h-48 w-full" />}>
              {(data: CascadeResponse) => <CascadeTable data={data} />}
            </QueryState>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Bootstrap uncertainty</CardTitle>
            <CardDescription>500 Dirichlet weight perturbations → rank CIs.</CardDescription>
          </CardHeader>
          <CardContent>
            <Placeholder
              height="h-48"
              label="[Recharts: rank CI bands per country]"
              detail="2.5–97.5 percentile rank range; needs a bootstrap endpoint (later session)"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Validation</CardTitle>
            <CardDescription>UFE precision/recall · ECHO &amp; NRC overlap.</CardDescription>
          </CardHeader>
          <CardContent>
            <Placeholder
              height="h-48"
              label="[Recharts: precision/recall @ K=15 + Jaccard overlap bars]"
              detail="gold_ufe_validation + ECHO/NRC comparators (later session)"
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Responsible-AI scorecard</CardTitle>
          <CardDescription>Seven custom judges over the eval suite.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid grid-cols-1 gap-1.5 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {RAI_JUDGES.map((j) => (
              <li key={j} className="flex items-center justify-between rounded-md bg-muted/40 px-2 py-1">
                <span className="font-mono text-xs">{j}</span>
                <span className="text-xs text-muted-foreground">—</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted-foreground">Scores populate from MLflow eval runs next session.</p>
        </CardContent>
      </Card>
    </div>
  );
}

function WeightBars({ data }: { data: CompositeWeightsResponse }) {
  const maxAbs = Math.max(...data.weights.map((w) => Math.abs(w.weight)));
  return (
    <div className="space-y-2">
      {data.weights.map((w) => {
        const negative = w.weight < 0;
        return (
          <div key={w.key} className="grid grid-cols-[8.5rem_1fr_2.75rem] items-center gap-3 text-sm" title={w.rationale}>
            <span className="truncate text-muted-foreground">{w.label}</span>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full", negative ? "bg-acute" : "bg-primary")}
                style={{ width: `${(Math.abs(w.weight) / maxAbs) * 100}%` }}
              />
            </div>
            <span className={cn("text-right tnum", negative ? "text-acute" : "text-foreground")}>
              {negative ? "−" : "+"}
              {Math.abs(w.weight).toFixed(2)}
            </span>
          </div>
        );
      })}
      <p className="pt-1 text-xs text-muted-foreground">{data.note}</p>
    </div>
  );
}

function CascadeTable({ data }: { data: CascadeResponse }) {
  return (
    <div className="space-y-2">
      {data.methods.map((m) => (
        <div key={m.method} className="grid grid-cols-[1fr_3.5rem] items-center gap-3 text-sm" title={m.note}>
          <div className="min-w-0">
            <div className="truncate">{m.label}</div>
            <div className="truncate text-xs text-muted-foreground">{m.note}</div>
          </div>
          <span className="text-right tnum font-medium">{m.share_pct}%</span>
        </div>
      ))}
      <p className="pt-1 text-xs text-muted-foreground">{data.note}</p>
    </div>
  );
}
