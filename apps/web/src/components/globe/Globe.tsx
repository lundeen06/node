"use client";

import type { Map as MapboxMap } from "mapbox-gl";
import { useEffect, useRef } from "react";

import { getMapboxAccessToken, getMapboxStyleUrl } from "@/lib/mapbox";

import { ConjunctionMarker } from "./ConjunctionMarker";
import { OrbitLayer } from "./OrbitLayer";
import { SatelliteLayer } from "./SatelliteLayer";

export function Globe() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    const token = getMapboxAccessToken();
    if (!token || !el) return;

    let disposed = false;
    let resizeObserver: ResizeObserver | null = null;

    void (async () => {
      try {
        const mapboxgl = (await import("mapbox-gl")).default;
        await import("mapbox-gl/dist/mapbox-gl.css");

        if (disposed || !el) return;

        mapboxgl.accessToken = token;

        const map = new mapboxgl.Map({
          container: el,
          style: getMapboxStyleUrl(),
          center: [0, 16],
          zoom: 1.25,
          pitch: 0,
          bearing: 0,
          projection: "globe",
          attributionControl: true,
        });

        if (disposed) {
          map.remove();
          return;
        }

        mapRef.current = map;

        const applyFog = () => {
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
      } catch {
        // Mapbox failed to initialize; placeholder UI remains.
      }
    })();

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      resizeObserver = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  const token = getMapboxAccessToken();

  return (
    <div className="relative h-full w-full min-h-0 overflow-hidden rounded-md border border-border/70 bg-zinc-950">
      <div ref={containerRef} className="absolute inset-0 z-0" />

      {!token ? (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 p-6 text-center">
          <p className="text-sm text-muted-foreground">
            Add <span className="font-mono text-xs text-foreground">NEXT_PUBLIC_MAPBOX_TOKEN</span> to{" "}
            <span className="font-mono text-xs text-foreground">.env.local</span> to enable the live globe.
          </p>
          <p className="text-xs text-muted-foreground">
            Optional: set <span className="font-mono text-foreground">NEXT_PUBLIC_MAPBOX_STYLE_URL</span> for a custom
            Studio style.
          </p>
        </div>
      ) : null}

      <div className="pointer-events-none absolute inset-0 z-10">
        <OrbitLayer />
        <SatelliteLayer />
        <ConjunctionMarker />
      </div>
    </div>
  );
}
