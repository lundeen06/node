"use client";

import { useEffect, useMemo, useState } from "react";

import { useOpsShell } from "@/components/shell/OpsShellContext";
import { useSimClock } from "@/components/shell/SimClockContext";
import { effectiveManeuverTimelineWindowMs } from "@/lib/orbit/maneuverTimeline";
import { formatBurnUtcReadable, formatTMinusSim } from "@/lib/orbit/simClockLabels";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

function parseBurnEpochUtcMs(iso: string): number | null {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
}

/** Bottom timeline: sim window with burn epochs (driven by active maneuver preview config). */
export function BurnSequenceBar() {
  const { maneuverPreviewConfig, setManeuverPreviewConfig } = useOpsShell();
  const { getSimInstant } = useSimClock();
  const [, setRaf] = useState(0);
  /** Hiding the strip must not clear the maneuver — globe track reads ``maneuverPreviewConfig`` independently. */
  const [stripHidden, setStripHidden] = useState(false);

  const burnSignature = useMemo(
    () =>
      maneuverPreviewConfig
        ? `${maneuverPreviewConfig.planId}|${maneuverPreviewConfig.satId}|${maneuverPreviewConfig.burnApplied ? "1" : "0"}|${maneuverPreviewConfig.timelineWindowMs}|${maneuverPreviewConfig.maneuvers.map((m) => m.epoch_utc).join("|")}`
        : "",
    [maneuverPreviewConfig],
  );

  const sortedManeuvers = useMemo(() => {
    const m = maneuverPreviewConfig?.maneuvers;
    if (!m?.length) return [];
    return [...m].sort((a, b) => {
      const ta = parseBurnEpochUtcMs(a.epoch_utc) ?? 0;
      const tb = parseBurnEpochUtcMs(b.epoch_utc) ?? 0;
      return ta - tb;
    });
  }, [maneuverPreviewConfig]);

  useEffect(() => {
    if (burnSignature) setStripHidden(false);
  }, [burnSignature]);

  useEffect(() => {
    if (!maneuverPreviewConfig || stripHidden) return;
    let id = 0;
    const loop = () => {
      setRaf((n) => (n + 1) % 10_000);
      id = requestAnimationFrame(loop);
    };
    id = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(id);
  }, [maneuverPreviewConfig, stripHidden]);

  if (!maneuverPreviewConfig) return null;

  if (stripHidden) {
    return (
      <div
        className={cn(
          "pointer-events-auto absolute bottom-3 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-lg border border-border/70 bg-background/95 px-2.5 py-1.5 text-[10px] shadow-lg shadow-black/20 backdrop-blur-md",
        )}
      >
        <span className="max-w-[14rem] truncate text-muted-foreground">
          {maneuverPreviewConfig.burnApplied ? (
            <>
              Applied maneuver · <span className="font-mono text-foreground">{maneuverPreviewConfig.satId}</span>
            </>
          ) : (
            <>
              Burn plan · <span className="font-mono text-foreground">{maneuverPreviewConfig.satId}</span>
            </>
          )}
        </span>
        {!maneuverPreviewConfig.burnApplied ? (
          <button
            type="button"
            className="shrink-0 rounded px-1.5 py-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={() => setManeuverPreviewConfig(null)}
          >
            Cancel preview
          </button>
        ) : null}
        <button
          type="button"
          className="shrink-0 rounded px-1.5 py-0.5 text-foreground hover:bg-muted"
          onClick={() => setStripHidden(false)}
        >
          Show timeline
        </button>
      </div>
    );
  }

  const sim = getSimInstant();
  const t0 = sim.getTime();
  const spanMs = Math.max(
    1,
    effectiveManeuverTimelineWindowMs(maneuverPreviewConfig, t0),
  );
  const windowMin = spanMs / (60 * 1000);

  const burns = sortedManeuvers.map((m, sortIndex) => {
    const t = parseBurnEpochUtcMs(m.epoch_utc);
    if (t == null) {
      return { sortIndex, pct: 0, epoch: m.epoch_utc, inWindow: false };
    }
    const rawPct = ((t - t0) / spanMs) * 100;
    const pct = Math.max(0, Math.min(100, rawPct));
    return {
      sortIndex,
      pct,
      epoch: m.epoch_utc,
      inWindow: rawPct >= 0 && rawPct <= 100,
    };
  });

  let nextBurn: { epoch: string; label: string } | null = null;
  for (const m of sortedManeuvers) {
    const burnMs = parseBurnEpochUtcMs(m.epoch_utc);
    if (burnMs == null) continue;
    if (burnMs >= t0 - 500) {
      nextBurn = { epoch: m.epoch_utc, label: formatTMinusSim(t0, burnMs) };
      break;
    }
  }

  return (
    <div
      className={cn(
        "pointer-events-auto absolute bottom-3 left-1/2 z-20 flex w-[min(32rem,calc(100%-2rem))] -translate-x-1/2 flex-col gap-1.5 rounded-xl border border-border/70 bg-background/95 px-3 py-2 shadow-lg shadow-black/25 ring-1 ring-black/5 backdrop-blur-md dark:ring-white/10",
      )}
    >
      <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
        <span className="truncate font-medium text-foreground">
          Burn sequence · <span className="font-mono">{maneuverPreviewConfig.satId}</span>
          {maneuverPreviewConfig.burnApplied ? (
            <span className="ml-1.5 font-normal text-teal-400/90">· applied</span>
          ) : (
            <span className="ml-1.5 font-normal text-amber-500/90">· preview</span>
          )}
        </span>
        <div className="flex shrink-0 items-center gap-0.5">
          {!maneuverPreviewConfig.burnApplied ? (
            <button
              type="button"
              className="rounded px-1.5 py-0.5 text-[9px] text-muted-foreground hover:bg-muted hover:text-foreground"
              title="Remove Δv arrows from the globe (proposal still here until Approve or Deny)"
              onClick={() => setManeuverPreviewConfig(null)}
            >
              Cancel preview
            </button>
          ) : null}
          <button
            type="button"
            className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label={
              maneuverPreviewConfig.burnApplied
                ? "Hide burn timeline (applied maneuver stays on the globe)"
                : "Hide burn timeline"
            }
            title={
              maneuverPreviewConfig.burnApplied
                ? "Hide timeline only — approved Δv stays applied on the map until you reset the preview from the agent or reload."
                : "Hide timeline strip (proposal preview chip stays)"
            }
            onClick={() => {
              setStripHidden(true);
            }}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="relative h-7 w-full overflow-hidden rounded-md border border-border/50 bg-gradient-to-b from-muted/50 to-muted/30 shadow-inner">
        {/* Equal-time grid: 25% of bar width = quarter of [sim now → window end]. */}
        {[25, 50, 75].map((q) => (
          <div
            key={q}
            className="pointer-events-none absolute inset-y-0 w-px bg-muted-foreground/12"
            style={{ left: `${q}%`, transform: "translateX(-50%)" }}
          />
        ))}
        <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-primary/50" title="Sim now" />
        <div
          className="pointer-events-none absolute inset-y-0 right-0 w-px bg-muted-foreground/30"
          title={`+${windowMin.toFixed(0)} min (sim)`}
        />
        {burns.map((b) => (
          <div
            key={`${b.epoch}-${b.sortIndex}`}
            className={cn(
              "absolute top-0.5 bottom-0.5 w-px rounded-sm",
              b.inWindow
                ? b.sortIndex === 0
                  ? "bg-rose-400"
                  : "bg-violet-400"
                : "bg-muted-foreground/40",
            )}
            style={{ left: `${b.pct}%`, transform: "translateX(-50%)" }}
            title={`${formatBurnUtcReadable(b.epoch)} · ${formatTMinusSim(t0, parseBurnEpochUtcMs(b.epoch) ?? t0)}`}
          />
        ))}
      </div>
      <div className="flex justify-between font-mono text-[9px] text-muted-foreground">
        <span>now</span>
        <span>+{windowMin.toFixed(0)}m</span>
      </div>
      {nextBurn ? (
        <div className="truncate font-mono text-[9px] text-muted-foreground">
          Next burn · <span className="text-foreground">{formatBurnUtcReadable(nextBurn.epoch)}</span> ·{" "}
          <span className="tabular-nums text-foreground">{nextBurn.label}</span>
        </div>
      ) : null}
    </div>
  );
}
