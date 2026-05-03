"use client";

import { useEffect, useRef } from "react";

import { useFleetCatalog } from "@/components/shell/FleetCatalogContext";
import { useOpsShell } from "@/components/shell/OpsShellContext";
import type { KeplerFleetEntry } from "@/lib/orbit/keplerFleet";
import { groundTrackKepler, propagateKeplerEntryLonLat } from "@/lib/orbit/keplerFleet";

import { fleetItemsFromKepler, type GroundTrack, type SelectedMarker } from "./earthGlobeRenderer";

export function SpacecraftGlobeLayers() {
  const { globe, selectedSatIds } = useOpsShell();
  const { loading: catalogLoading, error: catalogError, plottedEntries, entries } = useFleetCatalog();

  /* Refs let the rAF loop see the latest values without re-subscribing every render. */
  const plottedEntriesRef = useRef<KeplerFleetEntry[]>([]);
  plottedEntriesRef.current = plottedEntries;
  const selectedSatIdsRef = useRef<ReadonlySet<string>>(new Set());
  selectedSatIdsRef.current = selectedSatIds;
  const entriesByIdRef = useRef<Map<string, KeplerFleetEntry>>(new Map());
  useEffect(() => {
    const map = new Map<string, KeplerFleetEntry>();
    for (const e of entries) map.set(e.sat_id, e);
    entriesByIdRef.current = map;
  }, [entries]);

  /* Single rAF loop drives plotted points and selection markers (~60 fps). */
  useEffect(() => {
    if (!globe) return;
    let raf = 0;
    const loop = () => {
      const now = new Date();
      const items = fleetItemsFromKepler(plottedEntriesRef.current, now, propagateKeplerEntryLonLat);
      globe.setFleetPositions(items.length > 0 ? items : null);

      const selIds = selectedSatIdsRef.current;
      if (selIds.size === 0) {
        globe.setSelectedMarkers(null);
      } else {
        const markers: SelectedMarker[] = [];
        for (const id of selIds) {
          const hit = entriesByIdRef.current.get(id);
          if (!hit) continue;
          const ll = propagateKeplerEntryLonLat(hit, now);
          if (!ll) continue;
          markers.push({ satId: id, lonDeg: ll[0], latDeg: ll[1] });
        }
        globe.setSelectedMarkers(markers.length > 0 ? markers : null);
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [globe]);

  /* Ground tracks update only when the selection set changes (orbit periods are minutes-long). */
  useEffect(() => {
    if (!globe) return;
    if (selectedSatIds.size === 0) {
      globe.setGroundTracks(null);
      return;
    }
    const now = new Date();
    const tracks: GroundTrack[] = [];
    for (const id of selectedSatIds) {
      const hit = entriesByIdRef.current.get(id) ?? entries.find((e) => e.sat_id === id);
      if (!hit) continue;
      const path = groundTrackKepler(hit, now, 90, 90);
      if (path.length >= 2) tracks.push({ satId: id, path });
    }
    globe.setGroundTracks(tracks.length > 0 ? tracks : null);
  }, [globe, selectedSatIds, entries]);

  const selCount = selectedSatIds.size;

  const label =
    catalogLoading
      ? "Loading catalog…"
      : catalogError
        ? catalogError
        : `${plottedEntries.length.toLocaleString()} plotted${selCount > 0 ? ` · ${selCount} selected` : ""}`;

  return (
    <div className="pointer-events-none absolute left-4 top-4 z-10 max-w-md">
      <div className="rounded-md border border-border/70 bg-background/85 px-2 py-1 text-[11px] text-muted-foreground shadow-sm backdrop-blur">
        {label}
      </div>
    </div>
  );
}
