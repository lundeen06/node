import { AlertTriangle } from "lucide-react";

import { MOCK_CONJUNCTION } from "@/lib/mock-data";

import { Badge } from "@/components/ui/badge";

export function ConjunctionMarker() {
  return (
    <div className="absolute bottom-4 left-1/2 w-[min(520px,calc(100%-2rem))] -translate-x-1/2">
      <div className="flex items-start gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 shadow-sm backdrop-blur">
        <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive-foreground" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-foreground">Conjunction {MOCK_CONJUNCTION.id}</span>
            <Badge variant="destructive">Pc {MOCK_CONJUNCTION.pc.toExponential(1)}</Badge>
            <Badge variant="outline">{MOCK_CONJUNCTION.status}</Badge>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {MOCK_CONJUNCTION.primaryId} vs {MOCK_CONJUNCTION.secondaryId} · miss{" "}
            <span className="font-mono text-foreground">{MOCK_CONJUNCTION.missDistanceKm.toFixed(2)} km</span> · TCA{" "}
            <span className="font-mono text-foreground">{MOCK_CONJUNCTION.tca.instant}</span>
          </p>
        </div>
      </div>
    </div>
  );
}
