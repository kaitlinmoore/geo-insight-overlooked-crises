import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { Globe2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { TooltipProvider } from "@/components/ui/tooltip";

/** The six screens (docs/architecture.md "Six screens"). CBPF is optional. */
const NAV_ITEMS: { to: string; label: string; persona: string }[] = [
  { to: "/", label: "Triage", persona: "HC" },
  { to: "/compare", label: "Compare", persona: "HAO" },
  { to: "/ask", label: "Ask", persona: "HAO · HC" },
  { to: "/methodology", label: "Methodology", persona: "All" },
  { to: "/cbpf", label: "CBPF", persona: "PFM" },
];

function Breadcrumbs() {
  const { pathname } = useLocation();
  const params = useParams();
  const segments: string[] = [];

  if (pathname === "/") segments.push("Triage");
  else if (pathname.startsWith("/crisis/")) segments.push("Triage", `Crisis · ${params.iso3 ?? ""}`);
  else if (pathname.startsWith("/compare")) segments.push("Compare");
  else if (pathname.startsWith("/ask")) segments.push("Ask");
  else if (pathname.startsWith("/methodology")) segments.push("Methodology");
  else if (pathname.startsWith("/cbpf")) segments.push("CBPF Allocation View");

  return (
    <nav className="flex items-center gap-2 text-xs text-muted-foreground" aria-label="Breadcrumb">
      {segments.map((seg, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-muted-foreground/50">/</span>}
          <span className={cn(i === segments.length - 1 && "text-foreground")}>{seg}</span>
        </span>
      ))}
    </nav>
  );
}

export function AppShell() {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex min-h-screen flex-col bg-background">
        <header className="sticky top-0 z-40 border-b border-border bg-card/80 backdrop-blur">
          <div className="flex h-14 items-center gap-6 px-6">
            <div className="flex items-center gap-2">
              <Globe2 className="h-5 w-5 text-primary" />
              <div className="leading-tight">
                <div className="text-sm font-semibold tracking-tight">Geo-Insight</div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Overlooked Crises
                </div>
              </div>
            </div>
            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-primary/15 text-primary"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="ml-auto text-xs text-muted-foreground tnum">
              Analysis year <span className="font-medium text-foreground">2026</span>
            </div>
          </div>
        </header>

        <div className="flex items-center justify-between border-b border-border px-6 py-2">
          <Breadcrumbs />
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Mocked data · not for citation
          </span>
        </div>

        <main className="flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>
    </TooltipProvider>
  );
}
