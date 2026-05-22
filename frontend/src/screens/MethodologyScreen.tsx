import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Placeholder } from "@/components/Placeholder";

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
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Methodology &amp; validation</h1>
        <p className="text-sm text-muted-foreground">
          How the overlooked_score is computed, and the evidence it holds up.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Composite formula</CardTitle>
            <CardDescription>Seven within-year percentile components, weighted.</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-md bg-muted/50 p-3 font-mono text-xs leading-relaxed">
{`overlooked_score =
   0.30·gap_ratio + 0.20·severity_rate
 + 0.10·(1−$/PIN) + 0.15·chronic_index
 + 0.10·sector_imbalance − 0.10·media_attention
 + 0.05·geo_isolation·severity_rate`}
            </pre>
            <p className="mt-2 text-xs text-muted-foreground">
              Weights are placeholders, calibrated against UFE; reported as configurable.
            </p>
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
              detail="2.5–97.5 percentile rank range; stable_top_n highlighted"
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
              detail="gold_ufe_validation, ECHO FCA & NRC Most Neglected comparators"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Responsible-AI scorecard</CardTitle>
            <CardDescription>Seven custom judges over the eval suite.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="grid grid-cols-1 gap-1.5 text-sm sm:grid-cols-2">
              {RAI_JUDGES.map((j) => (
                <li key={j} className="flex items-center justify-between rounded-md bg-muted/40 px-2 py-1">
                  <span className="font-mono text-xs">{j}</span>
                  <span className="text-xs text-muted-foreground">—</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-muted-foreground">
              Scores populate from MLflow eval runs next session.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Sector coverage explorer</CardTitle>
        </CardHeader>
        <CardContent>
          <Placeholder
            height="h-64"
            label="[Recharts heatmap/matrix: sector_gap by country × sector]"
            detail="gold_sector_coverage · direct SQL Connector read"
          />
        </CardContent>
      </Card>
    </div>
  );
}
