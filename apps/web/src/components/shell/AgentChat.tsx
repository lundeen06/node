import { Bot, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { MOCK_AGENT_PLAN } from "@/lib/mock-data";

export function AgentChat() {
  return (
    <aside className="flex min-h-0 w-full min-w-0 flex-col border-l border-border bg-background/60">
      <div className="flex items-center justify-between px-3 py-2">
        <div className="text-xs font-semibold tracking-wide text-muted-foreground">AGENT</div>
        <Badge variant="outline" className="font-mono text-[10px]">
          session demo
        </Badge>
      </div>
      <Separator />
      <ScrollArea className="min-h-0 flex-1 px-3 py-3">
        <div className="space-y-3">
          <div className="flex gap-2">
            <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-md border border-border bg-card">
              <Bot className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1 rounded-md border border-border bg-card p-2 text-xs leading-relaxed text-muted-foreground">
              I screened catalog debris against <span className="text-foreground">EO-12</span> for the next 36h. One
              internal close approach exceeds your mitigation threshold. Proposed a single RIC burn at TCA−54m.
            </div>
          </div>

          <Card>
            <CardHeader className="p-3 pb-2">
              <CardTitle className="text-xs">Proposed maneuver</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-3 pt-0">
              <div className="rounded-md border border-border bg-background p-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
                <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-muted-foreground">
                  <span>Δv (RIC, m/s)</span>
                  <span className="font-mono text-foreground">
                    [{MOCK_AGENT_PLAN.maneuvers[0]!.deltaVMps.x.toFixed(3)},{" "}
                    {MOCK_AGENT_PLAN.maneuvers[0]!.deltaVMps.y.toFixed(3)}, {MOCK_AGENT_PLAN.maneuvers[0]!.deltaVMps.z.toFixed(3)}]
                  </span>
                </div>
                <Separator className="my-2" />
                <div className="text-[11px] text-muted-foreground">{MOCK_AGENT_PLAN.objective}</div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Button size="sm" variant="secondary" type="button" className="h-8 text-xs" disabled>
                  Edit in planner
                </Button>
                <Button size="sm" type="button" className="h-8 text-xs" disabled>
                  <ShieldCheck className="mr-1 h-3.5 w-3.5" />
                  Approve
                </Button>
              </div>
              <p className="text-[10px] text-muted-foreground">Buttons are intentionally disabled in the scaffold.</p>
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
      <Separator />
      <div className="p-3">
        <Input disabled placeholder="Message the agent (stub)" className="font-mono text-xs" />
      </div>
    </aside>
  );
}
