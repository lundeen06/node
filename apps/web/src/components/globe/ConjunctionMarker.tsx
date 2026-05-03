"use client";

import { MessageSquareText, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useOpsShell } from "@/components/shell/OpsShellContext";

const DRAFT_EVENT = "node-agent-set-draft";

export function ConjunctionMarker() {
  const { conjunctionHits, selectedConjunctionId, setSelectedConjunctionId } = useOpsShell();
  const hit = conjunctionHits.find((e) => e.id === selectedConjunctionId) ?? null;
  /** Hide the HUD after “Describe in chat” while keeping ``selectedConjunctionId`` for camera follow. */
  const [hudHidden, setHudHidden] = useState(false);

  useEffect(() => {
    setHudHidden(false);
  }, [selectedConjunctionId]);

  if (!hit) return null;
  if (hudHidden) return null;

  const draft = [
    `Conjunction ${hit.id}: primary \`${hit.primary_sat_id}\` vs secondary \`${hit.secondary_sat_id}\`.`,
    `TCA (sim) ${hit.tca_utc}. Miss distance ≈ ${hit.miss_distance_km.toFixed(2)} km.`,
    `Heuristic P ≈ ${hit.pc_heuristic.toExponential(2)} (not CDM Pc).`,
    "What mitigation options should we consider?",
  ].join("\n");

  return (
    <div className="pointer-events-auto absolute bottom-6 left-1/2 z-20 w-[min(22rem,calc(100%-2rem))] -translate-x-1/2 rounded-xl border border-border/60 bg-background/95 p-3 text-xs shadow-xl shadow-black/15 ring-1 ring-black/5 backdrop-blur-md dark:ring-white/10">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-foreground">Close approach</div>
          <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{hit.id}</div>
        </div>
        <button
          type="button"
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Dismiss"
          onClick={() => setSelectedConjunctionId(null)}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="space-y-1 text-[11px] text-muted-foreground">
        <p>
          <span className="text-foreground">{hit.primary_sat_id}</span> ·{" "}
          <span className="text-foreground">{hit.secondary_sat_id}</span>
        </p>
        <p>TCA {hit.tca_utc}</p>
        <p>
          Miss ≈ {hit.miss_distance_km.toFixed(2)} km · P<sub>h</sub> ≈ {hit.pc_heuristic.toExponential(2)}
        </p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant="default"
          className="h-8 gap-1 text-[11px]"
          onClick={() => {
            window.dispatchEvent(new CustomEvent(DRAFT_EVENT, { detail: { text: draft } }));
            setHudHidden(true);
          }}
        >
          <MessageSquareText className="h-3.5 w-3.5" />
          Describe in chat
        </Button>
        <Button type="button" size="sm" variant="outline" className="h-8 text-[11px]" onClick={() => setSelectedConjunctionId(null)}>
          Close
        </Button>
      </div>
    </div>
  );
}
