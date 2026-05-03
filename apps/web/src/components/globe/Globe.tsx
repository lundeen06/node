"use client";

import { useEffect, useRef, useState } from "react";

import { useOpsShell } from "@/components/shell/OpsShellContext";
import { useSimClock } from "@/components/shell/SimClockContext";

import { attachEarthGlobe, type EarthGlobeHandle } from "./earthGlobeRenderer";
import { BurnSequenceBar } from "./BurnSequenceBar";
import { ConjunctionCollisionAlert } from "./ConjunctionCollisionAlert";
import { GlobeCoeReadout } from "./GlobeCoeReadout";
import { ConjunctionMarker } from "./ConjunctionMarker";
import { ConjunctionSimLayer } from "./ConjunctionSimLayer";
import { SpacecraftGlobeLayers } from "./SpacecraftGlobeLayers";

export function Globe() {
  const { setGlobe, toggleSatSelection, replaceSatSelection, setSelectedConjunctionId, selectedConjunctionId } =
    useOpsShell();
  const { getSimInstant } = useSimClock();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const earthHandleRef = useRef<EarthGlobeHandle | null>(null);
  const [glError, setGlError] = useState<string | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    setGlError(null);
    let handle: EarthGlobeHandle | null = null;

    try {
      handle = attachEarthGlobe(el, {
        getSimInstant,
        onFleetPick: (satId) => toggleSatSelection(satId),
        onFleetTrack: (satId) => {
          setSelectedConjunctionId(null);
          replaceSatSelection([satId]);
        },
        onEarthCentricFocus: () => setSelectedConjunctionId(null),
        onConjunctionPick: (id) => {
          setSelectedConjunctionId(id);
          handle?.setCameraTrack({ kind: "conjunction", id });
        },
      });
      earthHandleRef.current = handle;
      setGlobe(handle);
    } catch (err) {
      console.error("[Globe] WebGL init failed:", err);
      setGlError(err instanceof Error ? err.message : "WebGL initialization failed");
    }

    return () => {
      earthHandleRef.current = null;
      setGlobe(null);
      handle?.dispose();
    };
  }, [setGlobe, toggleSatSelection, replaceSatSelection, getSimInstant, setSelectedConjunctionId]);

  /** Re-apply conjunction follow when selection comes from the fleet panel / catalog (not only canvas pick). */
  useEffect(() => {
    if (!selectedConjunctionId) return;
    const id = selectedConjunctionId;
    const apply = () => earthHandleRef.current?.setCameraTrack({ kind: "conjunction", id });
    apply();
    const r = requestAnimationFrame(apply);
    return () => cancelAnimationFrame(r);
  }, [selectedConjunctionId]);

  /** When screening clears the event (or selection is cleared), stop conjunction camera / red marker retention. */
  useEffect(() => {
    if (selectedConjunctionId != null) return;
    const h = earthHandleRef.current;
    if (!h) return;
    if (h.getCameraTrack().kind === "conjunction") {
      h.setCameraTrack({ kind: "none" });
    }
  }, [selectedConjunctionId]);

  return (
    <div className="relative flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden rounded-md border border-border/70 bg-zinc-950">
      <div ref={containerRef} className="relative z-0 min-h-0 w-full flex-1" />

      <div className="pointer-events-none absolute inset-0 z-10">
        <SpacecraftGlobeLayers />
        <ConjunctionSimLayer />
        <ConjunctionCollisionAlert />
        <BurnSequenceBar />
        <GlobeCoeReadout />
        <ConjunctionMarker />
      </div>

      {glError ? (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-background/90 p-6 text-center">
          <p className="text-sm font-medium text-destructive-foreground">Globe failed to start</p>
          <p className="max-w-md font-mono text-xs text-muted-foreground">{glError}</p>
        </div>
      ) : null}
    </div>
  );
}
