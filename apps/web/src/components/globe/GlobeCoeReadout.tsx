"use client";

import { Menu, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useFleetCatalog } from "@/components/shell/FleetCatalogContext";
import { useOpsShell } from "@/components/shell/OpsShellContext";
import { classicalFromOe } from "@/lib/orbit/classicalElements";
import type { KeplerFleetEntry } from "@/lib/orbit/keplerFleet";
import { cn } from "@/lib/utils";

const HDR: readonly string[] = ["a", "e", "i", "Ω", "ω", "M"];

function coeValues(entry: KeplerFleetEntry): string[] {
  const c = classicalFromOe(entry.oe);
  return [
    `${c.aKm.toFixed(2)} km`,
    c.e < 1e-3 ? c.e.toExponential(2) : c.e.toFixed(5),
    `${c.iDeg.toFixed(2)}°`,
    `${c.raanDeg.toFixed(2)}°`,
    `${c.argpDeg.toFixed(2)}°`,
    `${c.MDeg.toFixed(2)}°`,
  ];
}

/** Classical elements (a e i Ω ω M) — bottom-right, vertical panel behind a hamburger toggle. */
export function GlobeCoeReadout({ className }: { className?: string }) {
  const { selectedSatIds } = useOpsShell();
  const { entries } = useFleetCatalog();
  const [open, setOpen] = useState(false);

  const rows = useMemo(() => {
    const byId = new Map(entries.map((e) => [e.sat_id, e]));
    const ordered = [...selectedSatIds];
    return ordered.map((id) => byId.get(id)).filter(Boolean) as KeplerFleetEntry[];
  }, [entries, selectedSatIds]);

  if (rows.length === 0) return null;

  return (
    <div className={cn("pointer-events-auto absolute bottom-3 right-3 z-[18] flex flex-col items-end gap-2", className)}>
      {open ? (
        <div
          className={cn(
            "max-h-[min(52vh,22rem)] w-[min(14rem,calc(100vw-2rem))] overflow-y-auto overscroll-y-contain rounded-lg border border-border/70 bg-background/95 py-2 pl-2.5 pr-2 font-mono text-[10px] leading-snug text-foreground shadow-lg shadow-black/25 backdrop-blur-md",
          )}
        >
          {rows.map((entry, ri) => {
            const vals = coeValues(entry);
            return (
              <div
                key={entry.sat_id}
                className={cn("space-y-1", ri > 0 && "mt-3 border-t border-border/50 pt-3")}
              >
                <div className="truncate text-[9px] font-medium text-muted-foreground" title={entry.sat_id}>
                  {entry.name}
                </div>
                <dl className="space-y-0.5">
                  {HDR.map((h, i) => (
                    <div key={h} className="flex items-baseline justify-between gap-3">
                      <dt className="shrink-0 text-muted-foreground">{h}</dt>
                      <dd className="min-w-0 text-right tabular-nums text-foreground">{vals[i]}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            );
          })}
        </div>
      ) : null}

      <Button
        type="button"
        size="icon"
        variant="secondary"
        className="h-10 w-10 shrink-0 rounded-full border border-border/80 bg-background/95 shadow-md backdrop-blur-md"
        aria-expanded={open}
        aria-label={open ? "Hide orbital elements" : "Show orbital elements"}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
      </Button>
    </div>
  );
}
