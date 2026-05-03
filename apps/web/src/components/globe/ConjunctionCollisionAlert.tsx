"use client";

import { useEffect, useState } from "react";

import { AlertTriangle, X } from "lucide-react";

import { useOpsShell } from "@/components/shell/OpsShellContext";
import { cn } from "@/lib/utils";

/** Compact card when catalog screening reports close approaches; dismiss (×) top-right. */
export function ConjunctionCollisionAlert() {
  const { conjunctionHits, selectedConjunctionId, focusConjunctionFromCatalog } = useOpsShell();
  const [dismissed, setDismissed] = useState(false);

  const hitKey = conjunctionHits.map((e) => e.id).join("|");
  useEffect(() => {
    setDismissed(false);
  }, [hitKey]);

  if (conjunctionHits.length === 0 || selectedConjunctionId || dismissed) {
    return null;
  }

  return (
    <div
      className={cn(
        "pointer-events-auto absolute right-3 top-3 z-[25] flex max-h-[min(10rem,40vh)] w-[min(22rem,calc(100%-1.5rem))] flex-col overflow-hidden rounded-xl border border-destructive/40 bg-gradient-to-b from-destructive/20 to-destructive/10 shadow-lg shadow-destructive/20 ring-1 ring-destructive/25 backdrop-blur-md sm:right-4",
      )}
      role="alert"
    >
      <div className="relative shrink-0 border-b border-destructive/25 px-3 py-2 pr-9">
        <button
          type="button"
          className="absolute right-1 top-1 rounded p-0.5 text-destructive-foreground/80 hover:bg-destructive/20 hover:text-destructive-foreground"
          aria-label="Dismiss close approach alert"
          onClick={() => setDismissed(true)}
        >
          <X className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2 text-[11px] font-semibold tracking-tight text-destructive-foreground">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            {conjunctionHits.length === 1
              ? "Close approach — tap row to focus & track TCA"
              : `${conjunctionHits.length} close approaches · tap to track`}
          </span>
        </div>
      </div>
      <ul className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2 pt-1.5">
        {conjunctionHits.map((e) => (
          <li key={e.id}>
            <button
              type="button"
              className={cn(
                "w-full rounded-lg border border-destructive/25 bg-background/95 px-2.5 py-1.5 text-left text-[11px] shadow-sm",
                "text-foreground transition-all hover:border-destructive/50 hover:bg-destructive/5 hover:shadow",
              )}
              onClick={() => focusConjunctionFromCatalog(e)}
            >
              <span className="font-mono text-[10px] text-muted-foreground">{e.id}</span>
              <span className="mx-1 text-muted-foreground">·</span>
              <span className="font-medium">{e.primary_sat_id}</span>
              <span className="text-muted-foreground"> vs </span>
              <span className="font-medium">{e.secondary_sat_id}</span>
              <span className="block pt-0.5 font-mono text-[10px] text-muted-foreground">
                TCA {e.tca_utc} · miss ≈ {e.miss_distance_km.toFixed(2)} km · P<sub className="text-[9px]">h</sub> ≈{" "}
                {e.pc_heuristic.toExponential(1)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
