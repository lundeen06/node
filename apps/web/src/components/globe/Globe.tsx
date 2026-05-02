"use client";

import { useEffect, useRef, useState } from "react";

import { attachEarthGlobe } from "./earthGlobeRenderer";
import { ConjunctionMarker } from "./ConjunctionMarker";

export function Globe() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [glError, setGlError] = useState<string | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    setGlError(null);
    let handle: ReturnType<typeof attachEarthGlobe> | null = null;

    try {
      handle = attachEarthGlobe(el);
    } catch (err) {
      console.error("[Globe] WebGL init failed:", err);
      setGlError(err instanceof Error ? err.message : "WebGL initialization failed");
    }

    return () => {
      handle?.dispose();
    };
  }, []);

  return (
    <div className="relative flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden rounded-md border border-border/70 bg-zinc-950">
      <div ref={containerRef} className="relative z-0 min-h-0 w-full flex-1" />

      <div className="pointer-events-none absolute inset-0 z-10">
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
