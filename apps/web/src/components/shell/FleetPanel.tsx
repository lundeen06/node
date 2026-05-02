import { ChevronRight, Satellite } from "lucide-react";

import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { MOCK_SATELLITES } from "@/lib/mock-data";

export function FleetPanel() {
  return (
    <aside className="flex min-h-0 flex-col border-r border-border bg-background/60">
      <div className="flex items-center justify-between px-3 py-2">
        <div className="text-xs font-semibold tracking-wide text-muted-foreground">FLEET</div>
        <div className="font-mono text-[10px] text-muted-foreground">12 assets</div>
      </div>
      <Separator />
      <ScrollArea className="min-h-0 flex-1 px-2 py-2">
        <div className="space-y-1">
          {MOCK_SATELLITES.map((s) => (
            <button
              key={s.id}
              type="button"
              className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs hover:bg-muted"
            >
              <Satellite className="h-4 w-4 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-foreground">{s.name}</div>
                <div className="truncate font-mono text-[10px] text-muted-foreground">
                  {s.id} · {s.regime}
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            </button>
          ))}
        </div>
      </ScrollArea>
    </aside>
  );
}
