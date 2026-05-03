import { Bot } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

export function AgentChat() {
  return (
    <aside className="flex min-h-0 w-full min-w-0 flex-col border-l border-border bg-background/60">
      <div className="flex items-center justify-between px-3 py-2">
        <div className="text-xs font-semibold tracking-wide text-muted-foreground">AGENT</div>
        <Badge variant="outline" className="font-mono text-[10px]">
          idle
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
              Connect an agent backend and conjunction screening endpoints to populate proposals here. Spacecraft state
              comes from <span className="font-mono text-foreground">/spacecraft</span> and physics propagation from{" "}
              <span className="font-mono text-foreground">/spacecraft/…/trajectory</span>.
            </div>
          </div>

          <Card>
            <CardHeader className="p-3 pb-2">
              <CardTitle className="text-xs">Proposed maneuver</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-3 pt-0">
              <p className="text-[11px] text-muted-foreground">No maneuver proposal loaded.</p>
              <Button size="sm" variant="secondary" type="button" className="h-8 text-xs" disabled>
                Edit in planner
              </Button>
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
      <Separator />
      <div className="p-3">
        <Input disabled placeholder="Agent messaging not wired" className="font-mono text-xs" />
      </div>
    </aside>
  );
}
