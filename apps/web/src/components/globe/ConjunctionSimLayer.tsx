"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";

import { useOpsShell } from "@/components/shell/OpsShellContext";
import { useSimClock } from "@/components/shell/SimClockContext";
import { postCatalogConjunctionScreen } from "@/lib/api";

/** Avoid hammering catalog-screen (new CNJ ids each run made red markers “teleport”). */
const MIN_SCREENING_INTERVAL_MS = 28_000;

export function ConjunctionSimLayer() {
  const { globe, setConjunctionHits, maneuverPreviewConfig } = useOpsShell();
  const { getSimInstant } = useSimClock();
  const inflight = useRef(false);
  const lastRunWallMs = useRef(-Infinity);

  const maneuverScreenPayload = useMemo(() => {
    const c = maneuverPreviewConfig;
    if (!c?.burnApplied || !c.maneuvers.length) return undefined;
    const eciOnly = c.maneuvers.every((m) => String(m.frame).toUpperCase() === "ECI");
    if (!eciOnly) return undefined;
    return {
      maneuver_preview_sat_id: c.satId,
      maneuver_preview_maneuvers: c.maneuvers.map((m) => ({
        epoch_utc: m.epoch_utc,
        delta_v_mps: { ...m.delta_v_mps },
        frame: "ECI",
      })),
    };
  }, [maneuverPreviewConfig]);

  const runScreen = useCallback(async () => {
    if (!globe || inflight.current) return;
    const nowWall = Date.now();
    if (nowWall - lastRunWallMs.current < MIN_SCREENING_INTERVAL_MS) return;
    inflight.current = true;
    try {
      const sim = getSimInstant();
      const res = await postCatalogConjunctionScreen({
        sim_utc: sim.toISOString(),
        max_satellites: 72,
        separation_prefilter_km: 2800,
        sphere_radius_km: 12,
        step_s: 120,
        search_max_orbits: 2,
        ...maneuverScreenPayload,
      });
      lastRunWallMs.current = Date.now();
      setConjunctionHits(res.events);
    } catch (err) {
      console.warn("[ConjunctionSimLayer] screen failed", err);
    } finally {
      inflight.current = false;
    }
  }, [globe, getSimInstant, maneuverScreenPayload, setConjunctionHits]);

  useEffect(() => {
    lastRunWallMs.current = -Infinity;
    void runScreen();
  }, [maneuverScreenPayload, runScreen]);

  useEffect(() => {
    void runScreen();
    const id = window.setInterval(() => void runScreen(), 4000);
    return () => window.clearInterval(id);
  }, [runScreen]);

  return null;
}
