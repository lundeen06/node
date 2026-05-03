"use client";

import type { Map as MapboxMap } from "mapbox-gl";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type OpsShellValue = {
  map: MapboxMap | null;
  setMap: (m: MapboxMap | null) => void;
  selectedSatId: string | null;
  setSelectedSatId: (id: string | null) => void;
};

const OpsShellContext = createContext<OpsShellValue | null>(null);

export function OpsShellProvider({ children }: { children: ReactNode }) {
  const [map, setMap] = useState<MapboxMap | null>(null);
  const [selectedSatId, setSelectedSatId] = useState<string | null>(null);
  const value = useMemo(
    () => ({ map, setMap, selectedSatId, setSelectedSatId }),
    [map, selectedSatId],
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
