"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { ApiError, fetchSpacecraftKeplerCatalog, type KeplerCatalogRow } from "@/lib/api";
import { FOLDER_ORDER, inferFleetFolder, type FleetFolderId } from "@/lib/orbit/constellationGroups";
import type { KeplerFleetEntry } from "@/lib/orbit/keplerFleet";

export type FleetCatalogContextValue = {
  loading: boolean;
  error: string | null;
  entries: KeplerFleetEntry[];
  /** Folders that appear in the catalog, stable sort order. */
  folderIds: FleetFolderId[];
  grouped: Map<FleetFolderId, KeplerFleetEntry[]>;
  hiddenFolders: ReadonlySet<FleetFolderId>;
  toggleFolderPlot: (folder: FleetFolderId) => void;
  isFolderPlotted: (folder: FleetFolderId) => boolean;
  /** Entries whose folder is enabled for plotting (globe). */
  plottedEntries: KeplerFleetEntry[];
  refetch: () => void;
};

const FleetCatalogContext = createContext<FleetCatalogContextValue | null>(null);

function rowsToEntries(rows: KeplerCatalogRow[]): KeplerFleetEntry[] {
  const out: KeplerFleetEntry[] = [];
  for (const r of rows) {
    if (!Array.isArray(r.oe) || r.oe.length !== 6) continue;
    const oe = r.oe.map((x) => Number(x));
    if (oe.some((x) => !Number.isFinite(x))) continue;
    const folder = inferFleetFolder(r.name, r.purpose ?? "", r.sat_id);
    out.push({
      sat_id: r.sat_id,
      name: r.name,
      norad_catalog_id: r.norad_catalog_id,
      purpose: r.purpose ?? "",
      ephemeris_epoch_utc: r.ephemeris_epoch_utc,
      oe,
      folder,
    });
  }
  return out;
}

export function FleetCatalogProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entries, setEntries] = useState<KeplerFleetEntry[]>([]);
  const [hiddenFolders, setHiddenFolders] = useState<Set<FleetFolderId>>(new Set());
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSpacecraftKeplerCatalog(25_000)
      .then((rows) => {
        if (cancelled) return;
        const parsed = rowsToEntries(rows);
        setEntries(parsed);
        setHiddenFolders(parsed.length > 0 ? new Set(parsed.map((e) => e.folder)) : new Set());
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = e instanceof ApiError ? e.message : "Could not load Kepler catalog.";
        setError(msg);
        setEntries([]);
        setHiddenFolders(new Set());
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const grouped = useMemo(() => {
    const m = new Map<FleetFolderId, KeplerFleetEntry[]>();
    for (const e of entries) {
      const list = m.get(e.folder) ?? [];
      list.push(e);
      m.set(e.folder, list);
    }
    for (const list of m.values()) {
      list.sort((a, b) => a.name.localeCompare(b.name));
    }
    return m;
  }, [entries]);

  const folderIds = useMemo(() => {
    const ids = new Set<FleetFolderId>();
    for (const e of entries) ids.add(e.folder);
    const ordered: FleetFolderId[] = [];
    for (const id of FOLDER_ORDER) {
      if (ids.has(id)) ordered.push(id);
    }
    for (const id of ids) {
      if (!ordered.includes(id)) ordered.push(id);
    }
    return ordered;
  }, [entries]);

  const toggleFolderPlot = useCallback((folder: FleetFolderId) => {
    setHiddenFolders((prev) => {
      const n = new Set(prev);
      if (n.has(folder)) n.delete(folder);
      else n.add(folder);
      return n;
    });
  }, []);

  const isFolderPlotted = useCallback(
    (folder: FleetFolderId) => !hiddenFolders.has(folder),
    [hiddenFolders],
  );

  const plottedEntries = useMemo(
    () => entries.filter((e) => !hiddenFolders.has(e.folder)),
    [entries, hiddenFolders],
  );

  const refetch = useCallback(() => setReloadToken((t) => t + 1), []);

  const value = useMemo<FleetCatalogContextValue>(
    () => ({
      loading,
      error,
      entries,
      folderIds,
      grouped,
      hiddenFolders,
      toggleFolderPlot,
      isFolderPlotted,
      plottedEntries,
      refetch,
    }),
    [
      loading,
      error,
      entries,
      folderIds,
      grouped,
      hiddenFolders,
      toggleFolderPlot,
      isFolderPlotted,
      plottedEntries,
      refetch,
    ],
  );

  return <FleetCatalogContext.Provider value={value}>{children}</FleetCatalogContext.Provider>;
}

export function useFleetCatalog(): FleetCatalogContextValue {
  const ctx = useContext(FleetCatalogContext);
  if (!ctx) {
    throw new Error("useFleetCatalog must be used within FleetCatalogProvider");
  }
  return ctx;
}
