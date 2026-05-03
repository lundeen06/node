"use client";

import { useEffect, useState } from "react";
import { ChevronRight, Satellite } from "lucide-react";

import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { ApiError, fetchSpacecraftList, type SpacecraftSummary } from "@/lib/api";

import { useOpsShell } from "./OpsShellContext";

export function FleetPanel() {
  const { selectedSatId, setSelectedSatId } = useOpsShell();
  const [items, setItems] = useState<SpacecraftSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSpacecraftList()
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          const msg = e instanceof ApiError ? e.message : "Could not reach API.";
          setError(msg);
          setItems([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <aside className="flex min-h-0 flex-col border-r border-border bg-background/60">
      <div className="flex items-center justify-between px-3 py-2">
        <div className="text-xs font-semibold tracking-wide text-muted-foreground">FLEET</div>
        <div className="font-mono text-[10px] text-muted-foreground">
          {loading ? "…" : `${items.length} registered`}
        </div>
      </div>
      <Separator />
      <ScrollArea className="min-h-0 flex-1 px-2 py-2">
        {error ? (
          <p className="px-2 text-[11px] text-muted-foreground">{error}</p>
        ) : items.length === 0 && !loading ? (
          <p className="px-2 text-[11px] text-muted-foreground">
            No spacecraft in the database. POST to <span className="font-mono">/spacecraft/register</span> with
            Space-Track credentials configured on the API.
          </p>
        ) : (
          <div className="space-y-1">
            {items.map((s) => (
              <button
                key={s.sat_id}
                type="button"
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs hover:bg-muted",
                  selectedSatId === s.sat_id && "border border-amber-500/50 bg-muted",
                )}
                onClick={() => setSelectedSatId(selectedSatId === s.sat_id ? null : s.sat_id)}
              >
                <Satellite className="h-4 w-4 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-foreground">{s.name}</div>
                  <div className="truncate font-mono text-[10px] text-muted-foreground">
                    {s.sat_id} · NORAD {s.norad_catalog_id}
                  </div>
                  {s.purpose ? (
                    <div className="truncate text-[10px] text-muted-foreground/90">{s.purpose}</div>
                  ) : null}
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </button>
            ))}
          </div>
        )}
      </ScrollArea>
    </aside>
  );
}
