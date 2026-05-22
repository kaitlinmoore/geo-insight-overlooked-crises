import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function NotFoundScreen() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <h1 className="text-2xl font-semibold">Screen not found</h1>
      <p className="text-sm text-muted-foreground">That route doesn't exist in the command center.</p>
      <Button asChild>
        <Link to="/">Back to Triage</Link>
      </Button>
    </div>
  );
}
