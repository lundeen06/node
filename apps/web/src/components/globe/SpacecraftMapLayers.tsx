"use client";

import type { Map as MapboxMap } from "mapbox-gl";
import { useEffect, useState } from "react";

import { useOpsShell } from "@/components/shell/OpsShellContext";
import { ApiError, fetchSpacecraftMapPositions, fetchSpacecraftTrajectory, type SpacecraftMapGeoJSON } from "@/lib/api";

const SC_SRC = "spacecraft-positions";
const SC_LAYER = "spacecraft-positions-circle";
const SC_SEL = "spacecraft-positions-selected";
const SC_TRACK_SRC = "spacecraft-ground-track";
const SC_TRACK_LAYER = "spacecraft-ground-track-line";

/** LineString FeatureCollection for Mapbox ``setData`` (not the same as point catalog). */
type TrackGeoJSON = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties: Record<string, string | undefined>;
    geometry: { type: "LineString"; coordinates: [number, number][] };
  }>;
};

function removeSpacecraftLayers(map: MapboxMap) {
  try {
    if (map.getLayer(SC_TRACK_LAYER)) map.removeLayer(SC_TRACK_LAYER);
    if (map.getLayer(SC_SEL)) map.removeLayer(SC_SEL);
    if (map.getLayer(SC_LAYER)) map.removeLayer(SC_LAYER);
    if (map.getSource(SC_TRACK_SRC)) map.removeSource(SC_TRACK_SRC);
    if (map.getSource(SC_SRC)) map.removeSource(SC_SRC);
  } catch {
    /* style torn down */
  }
}

export function SpacecraftMapLayers() {
  const { map, selectedSatId } = useOpsShell();
  const [layersReady, setLayersReady] = useState(false);
  const [status, setStatus] = useState<
    { kind: "idle" } | { kind: "loading" } | { kind: "ok"; count: number } | { kind: "error"; message: string }
  >({ kind: "idle" });

  useEffect(() => {
    if (!map) return;

    let cancelled = false;

    const ensureLayers = () => {
      if (map.getSource(SC_SRC)) return;

      const emptyPoints: SpacecraftMapGeoJSON = { type: "FeatureCollection", features: [] };
      const emptyTrack: TrackGeoJSON = {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: [] },
          },
        ],
      };

      map.addSource(SC_SRC, { type: "geojson", data: emptyPoints });
      map.addSource(SC_TRACK_SRC, { type: "geojson", data: emptyTrack });

      map.addLayer({
        id: SC_LAYER,
        type: "circle",
        source: SC_SRC,
        paint: {
          "circle-radius": 2,
          "circle-color": "#38bdf8",
          "circle-opacity": 0.92,
          "circle-stroke-width": 0.35,
          "circle-stroke-color": "#0369a1",
        },
      });

      map.addLayer({
        id: SC_SEL,
        type: "circle",
        source: SC_SRC,
        filter: ["literal", false],
        paint: {
          "circle-radius": 8,
          "circle-color": "#fbbf24",
          "circle-opacity": 0.45,
          "circle-stroke-width": 1.2,
          "circle-stroke-color": "#d97706",
        },
      });

      map.addLayer({
        id: SC_TRACK_LAYER,
        type: "line",
        source: SC_TRACK_SRC,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#e879f9",
          "line-width": 2,
          "line-opacity": 0.92,
        },
      });
    };

    const loadData = async () => {
      setStatus({ kind: "loading" });
      try {
        const data = await fetchSpacecraftMapPositions(25_000);
        if (cancelled) return;
        ensureLayers();
        const src = map.getSource(SC_SRC);
        if (src && "setData" in src) {
          (src as { setData: (d: SpacecraftMapGeoJSON) => void }).setData(data);
        }
        setLayersReady(true);
        setStatus({ kind: "ok", count: data.features.length });
      } catch (e: unknown) {
        if (cancelled) return;
        const msg = e instanceof ApiError ? e.message : "Could not load positions";
        setStatus({ kind: "error", message: msg });
      }
    };

    const run = () => {
      if (!map.isStyleLoaded()) {
        map.once("style.load", () => {
          if (!cancelled) void loadData();
        });
        return;
      }
      void loadData();
    };

    run();

    return () => {
      cancelled = true;
      removeSpacecraftLayers(map);
      setLayersReady(false);
      setStatus({ kind: "idle" });
    };
  }, [map]);

  useEffect(() => {
    if (!map || !layersReady || !map.getLayer(SC_SEL)) return;

    if (selectedSatId) {
      map.setFilter(SC_SEL, ["==", ["get", "sat_id"], selectedSatId]);
    } else {
      map.setFilter(SC_SEL, ["literal", false]);
    }

    const trackSrc = map.getSource(SC_TRACK_SRC);
    if (!trackSrc || !("setData" in trackSrc)) return;

    if (!selectedSatId) {
      (trackSrc as { setData: (d: TrackGeoJSON) => void }).setData({
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: [] },
          },
        ],
      });
      return;
    }

    let cancelled = false;
    fetchSpacecraftTrajectory(selectedSatId, { duration_minutes: 90, step_seconds: 90 })
      .then((traj) => {
        if (cancelled) return;
        const coords: [number, number][] = [];
        for (const s of traj.samples) {
          if (s.lon_deg != null && s.lat_deg != null) {
            coords.push([s.lon_deg, s.lat_deg]);
          }
        }
        (trackSrc as { setData: (d: TrackGeoJSON) => void }).setData({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: { sat_id: selectedSatId },
              geometry: { type: "LineString", coordinates: coords },
            },
          ],
        });
      })
      .catch(() => {
        if (!cancelled && trackSrc && "setData" in trackSrc) {
          (trackSrc as { setData: (d: TrackGeoJSON) => void }).setData({
            type: "FeatureCollection",
            features: [
              {
                type: "Feature",
                properties: {},
                geometry: { type: "LineString", coordinates: [] },
              },
            ],
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [map, layersReady, selectedSatId]);

  const label =
    status.kind === "loading"
      ? "Propagating catalog → map…"
      : status.kind === "ok"
        ? `${status.count.toLocaleString()} spacecraft · click fleet for ground track`
        : status.kind === "error"
          ? status.message
          : null;

  if (!label) return null;

  return (
    <div className="pointer-events-none absolute left-4 top-4 z-10 max-w-md">
      <div className="rounded-md border border-border/70 bg-background/85 px-2 py-1 text-[11px] text-muted-foreground shadow-sm backdrop-blur">
        {label}
      </div>
    </div>
  );
}
