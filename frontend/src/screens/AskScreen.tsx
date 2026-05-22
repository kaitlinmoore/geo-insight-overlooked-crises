import { useState } from "react";
import { Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MOCK_ASK_EXCHANGE, type AskExchange } from "@/lib/mockData";

/** Custom Genie chat UI: question → generated SQL → result → NL answer. */
function Exchange({ ex }: { ex: AskExchange }) {
  const columns = ex.result_rows.length > 0 ? Object.keys(ex.result_rows[0]) : [];
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg rounded-br-sm bg-primary/15 px-3 py-2 text-sm">
          {ex.question}
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
            Generated SQL
            <Badge variant="outline" className="text-[10px]">Genie</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-md bg-muted/50 p-3 font-mono text-xs leading-relaxed">
            {ex.generated_sql}
          </pre>
        </CardContent>
      </Card>

      {columns.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
              Result
            </CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  {columns.map((c) => (
                    <th key={c} className="py-1 pr-4 font-medium">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ex.result_rows.map((row, i) => (
                  <tr key={i} className="border-b border-border/40">
                    {columns.map((c) => (
                      <td key={c} className="py-1 pr-4 tnum">{String(row[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      <div className="rounded-lg border border-border bg-card p-3 text-sm">
        <p>{ex.answer}</p>
        <div className="mt-3 flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Helpful">
            <ThumbsUp className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Not helpful">
            <ThumbsDown className="h-3.5 w-3.5" />
          </Button>
          <span className="text-xs text-muted-foreground">
            Feedback writes to a Delta table (wired next session)
          </span>
        </div>
      </div>
    </div>
  );
}

export function AskScreen() {
  const [draft, setDraft] = useState("");

  return (
    <div className="mx-auto flex h-[calc(100vh-10rem)] max-w-3xl flex-col">
      <div className="mb-4">
        <h1 className="text-lg font-semibold tracking-tight">Ask</h1>
        <p className="text-sm text-muted-foreground">
          Natural-language questions over Gold tables via the Genie REST API.
        </p>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto pr-1">
        <Exchange ex={MOCK_ASK_EXCHANGE} />
        <p className="text-center text-xs text-muted-foreground">
          [Streaming responses + MLflow trace link land in the integration session]
        </p>
      </div>

      <form
        className="mt-4 flex items-center gap-2 border-t border-border pt-4"
        onSubmit={(e) => {
          e.preventDefault();
          setDraft("");
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about overlooked crises, funding gaps, sectors…"
          className="h-10 flex-1 rounded-md border border-input bg-transparent px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <Button type="submit" size="icon" disabled={!draft.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
