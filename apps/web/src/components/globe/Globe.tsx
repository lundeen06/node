"use client";

import "mapbox-gl/dist/mapbox-gl.css";

import type { Map as MapboxMap } from "mapbox-gl";
import mapboxgl from "mapbox-gl";
import { useEffect, useRef, useState } from "react";

import { useOpsShell } from "@/components/shell/OpsShellContext";
import { getMapboxAccessToken, getMapboxStyleUrl, shouldUseGlobeProjection } from "@/lib/mapbox";

import { ConjunctionMarker } from "./ConjunctionMarker";
import { OrbitLayer } from "./OrbitLayer";
import { SpacecraftMapLayers } from "./SpacecraftMapLayers";

export function Globe() {
  const { setMap } = useOpsShell();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    const token = getMapboxAccessToken();
    setMapError(null);

    if (!token || !el) return;

    let disposed = false;
    let resizeObserver: ResizeObserver | null = null;

    try {
      mapboxgl.accessToken = token;

      const styleUrl = getMapboxStyleUrl();
      const useGlobe = shouldUseGlobeProjection();

      const map = new mapboxgl.Map({
        container: el,
        style: styleUrl,
        center: [0, 16],
        zoom: 1.25,
        pitch: 0,
        bearing: 0,
        ...(useGlobe ? { projection: "globe" as const } : {}),
        attributionControl: true,
      });

      if (disposed) {
        map.remove();
        return;
      }

      mapRef.current = map;

      map.on("error", (e) => {
        const msg = e.error?.message ?? String(e.error ?? "Map error");
        console.error("[Globe] mapbox error:", e.error);
        setMapError(msg);
      });

      const applyFog = () => {
        if (!useGlobe) return;
        try {
          map.setFog({
            color: "rgb(12, 12, 20)",
            "high-color": "rgb(36, 92, 223)",
            "horizon-blend": 0.08,
            "space-color": "rgb(0, 0, 6)",
            "star-intensity": 0.45,
          });
        } catch {
          // Custom styles may not support fog; ignore.
        }
      };

      map.on("style.load", () => {
        if (disposed) return;
        applyFog();
        map.resize();
      });

      map.on("load", () => {
        if (disposed) return;
        map.resize();
        setMap(map);
      });

      resizeObserver = new ResizeObserver(() => {
        if (!disposed) {
          mapRef.current?.resize();
        }
      });
      resizeObserver.observe(el);

      map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");

      queueMicrotask(() => {
        if (!disposed) map.resize();
      });
    } catch (err) {
      console.error("[Globe] failed to initialize Mapbox:", err);
      setMapError(err instanceof Error ? err.message : "Failed to initialize map");
    }

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      resizeObserver = null;
      setMap(null);
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [setMap]);

  const token = getMapboxAccessToken();

  return (
    <div className="relative flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden rounded-md border border-border/70 bg-zinc-950">
      {/* Map fills all vertical space; flex-1 gives Mapbox a real height (not just min-h). */}
      <div ref={containerRef} className="relative z-0 min-h-0 w-full flex-1" />

      <div className="pointer-events-none absolute inset-0 z-10">
        <OrbitLayer />
        <SpacecraftMapLayers />
        <ConjunctionMarker />
      </div>

      {!token ? (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-zinc-950/95 p-6 text-center">
          <p className="text-sm text-muted-foreground">
            Add <span className="font-mono text-xs text-foreground">NEXT_PUBLIC_MAPBOX_TOKEN</span> to{" "}
            <span className="font-mono text-xs text-foreground">.env.local</span> to enable the live globe.
          </p>
          <p className="text-xs text-muted-foreground">
            Optional: <span className="font-mono text-foreground">NEXT_PUBLIC_MAPBOX_STYLE_URL</span> · for custom
            Studio styles we default to a <span className="text-foreground">flat mercator</span> view unless you set{" "}
            <span className="font-mono text-foreground">NEXT_PUBLIC_MAPBOX_GLOBE=1</span>.
          </p>
        </div>
      ) : null}

      {token && mapError ? (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-background/90 p-6 text-center">
          <p className="text-sm font-medium text-destructive-foreground">Map failed to load</p>
          <p className="max-w-md font-mono text-xs text-muted-foreground">{mapError}</p>
          <p className="text-xs text-muted-foreground">
            If you use a custom style, try <span className="font-mono text-foreground">NEXT_PUBLIC_MAPBOX_GLOBE=0</span>{" "}
            (default when a style URL is set) or fix the style / token in{" "}
            <span className="font-mono text-foreground">apps/web/.env.local</span> and restart{" "}
            <span className="font-mono text-foreground">npm run dev</span>.
          </p>
        </div>
      ) : null}
    </div>
  );
}
