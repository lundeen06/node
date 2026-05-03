import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MOCK_AGENT_PLAN } from "@/lib/mock-data";

export function ManeuverDiff() {
  const m = MOCK_AGENT_PLAN.maneuvers[0] ?? null;
  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-xs">Diff vs active plan</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 p-4 pt-0 md:grid-cols-2">
        <div>
          <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Current</div>
          <pre className="mt-2 whitespace-pre-wrap rounded-md border border-border bg-background p-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
            No active plan loaded.
          </pre>
        </div>
        <div>
          <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Proposed</div>
          <pre className="mt-2 whitespace-pre-wrap rounded-md border border-border bg-background p-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
            {m
              ? `epoch: ${m.epoch.instant}
Δv_RIC: [${m.deltaVMps.x.toFixed(3)}, ${m.deltaVMps.y.toFixed(3)}, ${m.deltaVMps.z.toFixed(3)}] m/s`
              : "No proposal loaded."}
          </pre>
        </div>
      </CardContent>
    </Card>
  );
}
