"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type { EarthGlobeHandle } from "@/components/globe/earthGlobeRenderer";
import type { CatalogScreenEvent } from "@/lib/api";

/**
 * Active maneuver visualization on the globe.
 * ``burnApplied: false`` — proposal only: catalog orbit + Δv arrows (no propagated orbit).
 * ``burnApplied: true`` — operator approved: propagated trajectory (impulses applied in preview physics).
 */
export type ManeuverPreviewConfig = {
  /** Which agent ``PlanResponse.plan_id`` is on the globe (multiple pending plans). */
  planId: string;
  satId: string;
  maneuvers: Array<{
    epoch_utc: string;
    delta_v_mps: { x: number; y: number; z: number };
    frame: string;
  }>;
  /**
   * Fixed sim-time span (ms) for the burn timeline, set at apply time so tick positions stay
   * affine as sim clock advances (see ``computeManeuverTimelineWindowMs``).
   */
  timelineWindowMs: number;
  /** ``false`` until the operator clicks **Approve**; then ``true`` (propagated preview). */
  burnApplied: boolean;
  /**
   * When ``burnApplied``, ISO UTC of the sim instant at **Approve** — used as fixed ``start_utc`` for
   * trajectory-preview refetches so burns are not dropped when the sim clock advances.
   */
  trajectoryPreviewAnchorUtc?: string;
};

export type OpsShellValue = {
  globe: EarthGlobeHandle | null;
  setGlobe: (g: EarthGlobeHandle | null) => void;
  /** Currently selected satellite IDs (ground track + marker rendered for each). */
  selectedSatIds: ReadonlySet<string>;
  isSatSelected: (id: string) => boolean;
  toggleSatSelection: (id: string) => void;
  clearSatSelection: () => void;
  /** Replace selection (e.g. single sat for maneuver preview). */
  replaceSatSelection: (satIds: readonly string[]) => void;
  /** First selected satellite — used by single-target views (planner deep-link, etc.). */
  primarySatId: string | null;
  /** Latest catalog screening hits (SGP4 demo). */
  conjunctionHits: CatalogScreenEvent[];
  setConjunctionHits: (rows: CatalogScreenEvent[]) => void;
  /** Empty hits and skip the next in-flight catalog-screen write so the list stays cleared briefly after approve/dismiss. */
  clearConjunctionHitsForOperator: () => void;
  selectedConjunctionId: string | null;
  setSelectedConjunctionId: (id: string | null) => void;
  /** Select both satellites and focus this catalog-screen event (globe red TCA markers). */
  focusConjunctionFromCatalog: (ev: CatalogScreenEvent) => void;
  /** Globe maneuver overlay: proposal arrows (``burnApplied: false``) or approved propagated path (``true``). */
  maneuverPreviewConfig: ManeuverPreviewConfig | null;
  setManeuverPreviewConfig: (c: ManeuverPreviewConfig | null) => void;
};

const OpsShellContext = createContext<OpsShellValue | null>(null);

export function OpsShellProvider({ children }: { children: ReactNode }) {
  const [globe, setGlobeState] = useState<EarthGlobeHandle | null>(null);
  const globeRef = useRef<EarthGlobeHandle | null>(null);

  const setGlobe = useCallback((g: EarthGlobeHandle | null) => {
    globeRef.current = g;
    setGlobeState(g);
  }, []);

  const [selectedSatIds, setSelectedSatIds] = useState<Set<string>>(() => new Set());
  const [conjunctionHits, setConjunctionHitsState] = useState<CatalogScreenEvent[]>([]);
  /** Skip N catalog-screen ``setConjunctionHits`` calls (in-flight POST completes right after operator clear). */
  const conjunctionScreenApplySkipsRef = useRef(0);

  const setConjunctionHits = useCallback((rows: CatalogScreenEvent[]) => {
    if (conjunctionScreenApplySkipsRef.current > 0) {
      conjunctionScreenApplySkipsRef.current -= 1;
      return;
    }
    setConjunctionHitsState(rows);
  }, []);

  const clearConjunctionHitsForOperator = useCallback(() => {
    conjunctionScreenApplySkipsRef.current = 2;
    setConjunctionHitsState([]);
  }, []);

  const [selectedConjunctionId, setSelectedConjunctionId] = useState<string | null>(null);
  const [maneuverPreviewConfig, setManeuverPreviewState] = useState<ManeuverPreviewConfig | null>(null);
  const setManeuverPreviewConfig = useCallback((c: ManeuverPreviewConfig | null) => {
    setManeuverPreviewState(c);
  }, []);

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

  const replaceSatSelection = useCallback((satIds: readonly string[]) => {
    setSelectedSatIds(new Set(satIds));
  }, []);

  const focusConjunctionFromCatalog = useCallback((ev: CatalogScreenEvent) => {
    conjunctionScreenApplySkipsRef.current = 0;
    setSelectedSatIds(new Set([ev.primary_sat_id, ev.secondary_sat_id]));
    setSelectedConjunctionId(ev.id);
    globeRef.current?.setCameraTrack({ kind: "conjunction", id: ev.id });
  }, []);

  const isSatSelected = useCallback((id: string) => selectedSatIds.has(id), [selectedSatIds]);

  const primarySatId = useMemo(() => {
    const it = selectedSatIds.values().next();
    return it.done ? null : it.value;
  }, [selectedSatIds]);

  /** Catalog-screen assigns new ``id`` strings each run; keep follow by pair (+ TCA) not by stale id. */
  const conjunctionFollowAnchorRef = useRef<{
    primary: string;
    secondary: string;
    tcaMs: number;
  } | null>(null);

  useEffect(() => {
    if (!selectedConjunctionId) {
      conjunctionFollowAnchorRef.current = null;
      return;
    }

    const found = conjunctionHits.find((e) => e.id === selectedConjunctionId);
    if (found) {
      const tcaMs = Date.parse(found.tca_utc);
      conjunctionFollowAnchorRef.current = {
        primary: found.primary_sat_id,
        secondary: found.secondary_sat_id,
        tcaMs: Number.isFinite(tcaMs) ? tcaMs : NaN,
      };
      return;
    }

    const anchor = conjunctionFollowAnchorRef.current;
    if (!anchor) {
      setSelectedConjunctionId(null);
      return;
    }

    const { primary, secondary, tcaMs } = anchor;
    const matches = conjunctionHits.filter(
      (e) =>
        (e.primary_sat_id === primary && e.secondary_sat_id === secondary) ||
        (e.primary_sat_id === secondary && e.secondary_sat_id === primary),
    );

    let next: CatalogScreenEvent | undefined;
    if (matches.length === 1) {
      next = matches[0];
    } else if (matches.length > 1) {
      next = Number.isFinite(tcaMs)
        ? matches.reduce((best, e) => {
            const dt = Math.abs(Date.parse(e.tca_utc) - tcaMs);
            const bdt = Math.abs(Date.parse(best.tca_utc) - tcaMs);
            return dt < bdt ? e : best;
          })
        : matches[0];
    }

    if (next) {
      if (next.id !== selectedConjunctionId) {
        setSelectedConjunctionId(next.id);
        globeRef.current?.setCameraTrack({ kind: "conjunction", id: next.id });
      }
    } else {
      setSelectedConjunctionId(null);
      conjunctionFollowAnchorRef.current = null;
    }
  }, [conjunctionHits, selectedConjunctionId]);

  const value = useMemo<OpsShellValue>(
    () => ({
      globe,
      setGlobe,
      selectedSatIds,
      isSatSelected,
      toggleSatSelection,
      clearSatSelection,
      replaceSatSelection,
      primarySatId,
      conjunctionHits,
      setConjunctionHits,
      clearConjunctionHitsForOperator,
      selectedConjunctionId,
      setSelectedConjunctionId,
      focusConjunctionFromCatalog,
      maneuverPreviewConfig,
      setManeuverPreviewConfig,
    }),
    [
      globe,
      selectedSatIds,
      isSatSelected,
      toggleSatSelection,
      clearSatSelection,
      replaceSatSelection,
      focusConjunctionFromCatalog,
      primarySatId,
      conjunctionHits,
      setConjunctionHits,
      clearConjunctionHitsForOperator,
      selectedConjunctionId,
      maneuverPreviewConfig,
      setManeuverPreviewConfig,
    ],
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
