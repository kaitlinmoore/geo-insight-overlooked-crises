import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Placeholder } from "@/components/Placeholder";
import { RankCI } from "@/components/RankCI";
import { MOCK_CBPF_FUND, getCrisisDetail } from "@/lib/mockData";

const usd = (n: number) =>
  new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1, style: "currency", currency: "USD" }).format(n);

export function CbpfScreen() {
  const fund = MOCK_CBPF_FUND;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-tight">CBPF Allocation View</h1>
        <Badge variant="outline" className="text-[10px] text-muted-foreground">optional · PFM</Badge>
      </div>
      <p className="-mt-4 text-sm text-muted-foreground">
        Fund-scoped: ranking filtered to the countries the selected fund operates in.
        Allocation history shown <em>alongside</em> overlooked-ness, never blended into it.
      </p>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{fund.fund_name}</CardTitle>
          <CardDescription>
            {fund.fund_id} · operates in {fund.countries.join(", ")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-1 pr-4 font-medium">Country</th>
                <th className="py-1 pr-4 font-medium">Allocated</th>
                <th className="py-1 pr-4 font-medium">Overlooked rank</th>
              </tr>
            </thead>
            <tbody>
              {fund.allocations.map((a) => {
                const detail = getCrisisDetail(a.iso3);
                const r = detail?.ranking;
                return (
                  <tr key={a.iso3} className="border-b border-border/40">
                    <td className="py-1.5 pr-4">{a.country_name} <span className="text-xs text-muted-foreground">{a.iso3}</span></td>
                    <td className="py-1.5 pr-4 tnum">{usd(a.allocated_usd)}</td>
                    <td className="py-1.5 pr-4">
                      {r ? (
                        <RankCI rank={r.rank_position} low={r.rank_ci_low} high={r.rank_ci_high} stable={r.stable_top_n} />
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Allocations vs. overlooked-ness</CardTitle>
          <CardDescription>Are allocations aligned with documented need signals?</CardDescription>
        </CardHeader>
        <CardContent>
          <Placeholder
            height="h-64"
            label="[Recharts scatter: allocated_usd vs overlooked_score]"
            detail="CBPF allocation history joined to gold_forgotten_crisis_index; factual framing only — no recommendations"
          />
        </CardContent>
      </Card>
    </div>
  );
}
