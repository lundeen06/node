"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import type { EarthGlobeHandle } from "@/components/globe/earthGlobeRenderer";

export type OpsShellValue = {
  globe: EarthGlobeHandle | null;
  setGlobe: (g: EarthGlobeHandle | null) => void;
  /** Currently selected satellite IDs (ground track + marker rendered for each). */
  selectedSatIds: ReadonlySet<string>;
  isSatSelected: (id: string) => boolean;
  toggleSatSelection: (id: string) => void;
  clearSatSelection: () => void;
  /** First selected satellite — used by single-target views (planner deep-link, etc.). */
  primarySatId: string | null;
};

const OpsShellContext = createContext<OpsShellValue | null>(null);

export function OpsShellProvider({ children }: { children: ReactNode }) {
  const [globe, setGlobe] = useState<EarthGlobeHandle | null>(null);
  const [selectedSatIds, setSelectedSatIds] = useState<Set<string>>(() => new Set());

  const toggleSatSelection = useCallback((id: string) => {
    setSelectedSatIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const clearSatSelection = useCallback(() => {
    setSelectedSatIds(new Set());
  }, []);

  const isSatSelected = useCallback((id: string) => selectedSatIds.has(id), [selectedSatIds]);

  const primarySatId = useMemo(() => {
    const it = selectedSatIds.values().next();
    return it.done ? null : it.value;
  }, [selectedSatIds]);

  const value = useMemo<OpsShellValue>(
    () => ({
      globe,
      setGlobe,
      selectedSatIds,
      isSatSelected,
      toggleSatSelection,
      clearSatSelection,
      primarySatId,
    }),
    [globe, selectedSatIds, isSatSelected, toggleSatSelection, clearSatSelection, primarySatId],
  );

  return <OpsShellContext.Provider value={value}>{children}</OpsShellContext.Provider>;
}

export function useOpsShell(): OpsShellValue {
  const ctx = useContext(OpsShellContext);
  if (!ctx) {
    throw new Error("useOpsShell must be used within OpsShellProvider");
  }
  return ctx;
}
