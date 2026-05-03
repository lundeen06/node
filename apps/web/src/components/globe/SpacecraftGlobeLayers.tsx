"use client";

import { useEffect, useRef } from "react";

import { useFleetCatalog } from "@/components/shell/FleetCatalogContext";
import { useOpsShell } from "@/components/shell/OpsShellContext";
import { useSimClock } from "@/components/shell/SimClockContext";
import type { CatalogScreenEvent, TrajectoryResponse } from "@/lib/api";
import { fetchSpacecraftTrajectory, postTrajectoryPreviewManeuvers } from "@/lib/api";
import type { KeplerFleetEntry } from "@/lib/orbit/keplerFleet";
import { propagateKeplerEntryEciMeters } from "@/lib/orbit/keplerFleet";
import {
  buildManeuverGroundTrack,
  buildProposedAfterBurnTrack,
  positionEciMetersFromTrajectoryAt,
  trajectoryPathEciFromNow,
} from "@/lib/orbit/maneuverPreviewViz";
import { effectiveManeuverTimelineWindowMs } from "@/lib/orbit/maneuverTimeline";

import type { ManeuverPreviewConfig } from "@/components/shell/OpsShellContext";
import { fleetItemsFromKepler, type ConjunctionMarkerInput, type GroundTrack } from "./earthGlobeRenderer";

/** Wider maneuver windows need coarser steps so the preview response stays light. */
function maneuverPreviewStepSeconds(preview: ManeuverPreviewConfig, startMs: number): number {
  const spanMs = effectiveManeuverTimelineWindowMs(preview, startMs);
  const spanMin = spanMs / (60 * 1000);
  if (spanMin > 720) return 300;
  if (spanMin > 360) return 180;
  if (spanMin > 180) return 120;
  return 90;
}

function isBurnPropagated(preview: ManeuverPreviewConfig | null): boolean {
  return preview != null && preview.burnApplied === true;
}

/**
 * Pin the red conjunction marker to the **server-side TCA intersection point** so it stays
 * fixed in inertial space at the predicted collision center while the satellites approach
 * it (and continue past it after a maneuver). ``eci_mid_m`` / ``primary_eci_m`` /
 * ``secondary_eci_m`` are evaluated at TCA by ``screen_catalog_close_approaches`` and are
 * the operationally meaningful "where would the collision happen" point — not a moving
 * midpoint of the live propagated positions.
 */
function conjunctionMarkersForSim(hits: CatalogScreenEvent[]): ConjunctionMarkerInput[] | null {
  if (hits.length === 0) return null;
  return hits.map((e) => ({
    id: e.id,
    eciM: e.eci_mid_m,
    primaryEciM: e.primary_eci_m,
    secondaryEciM: e.secondary_eci_m,
  }));
}

export function SpacecraftGlobeLayers() {
  const {
    globe,
    selectedSatIds,
    conjunctionHits,
    maneuverPreviewConfig,
    selectedConjunctionId,
  } = useOpsShell();
  const previewActive = Boolean(maneuverPreviewConfig);
  const { getSimInstant } = useSimClock();
  const { loading: catalogLoading, error: catalogError, plottedEntries, entries } = useFleetCatalog();

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

  const conjunctionHitsRef = useRef<CatalogScreenEvent[]>([]);
  conjunctionHitsRef.current = conjunctionHits;

  const maneuverPreviewRef = useRef(maneuverPreviewConfig);
  maneuverPreviewRef.current = maneuverPreviewConfig;

  /** Latest trajectory samples for the previewing satellite (nominal SGP4 or propagated maneuver). */
  const previewTrajectoryRef = useRef<{ satId: string; traj: TrajectoryResponse } | null>(null);
  /**
   * Proposal-phase only: post-burn-propagated trajectory used to render the green "if accepted"
   * overlay path. Cleared when the burn is approved (the approved trajectory is owned by
   * ``previewTrajectoryRef``).
   */
  const proposedTrajectoryRef = useRef<{ satId: string; traj: TrajectoryResponse } | null>(null);
  const lastGroundTracksRef = useRef<GroundTrack[] | null>(null);

  const selectedConjunctionIdRef = useRef<string | null>(null);
  selectedConjunctionIdRef.current = selectedConjunctionId;

  useEffect(() => {
    if (!maneuverPreviewConfig) {
      previewTrajectoryRef.current = null;
      proposedTrajectoryRef.current = null;
    }
  }, [maneuverPreviewConfig]);

  useEffect(() => {
    if (!globe) return;
    let raf = 0;
    const loop = () => {
      const now = getSimInstant();
      const track = globe.getCameraTrack();
      const cfg = maneuverPreviewRef.current;
      const bundle = previewTrajectoryRef.current;
      const propagated = isBurnPropagated(cfg);
      const previewSatId =
        cfg && bundle && bundle.satId === cfg.satId && bundle.traj.samples.length > 0 ? cfg.satId : null;
      const previewEci =
        propagated && previewSatId && bundle
          ? positionEciMetersFromTrajectoryAt(bundle.traj, now)
          : null;

      let fleet = fleetItemsFromKepler(plottedEntriesRef.current, now, propagateKeplerEntryEciMeters);
      if (previewSatId && previewEci) {
        const hasPreview = fleet.some((it) => it.satId === previewSatId);
        fleet = hasPreview
          ? fleet.map((it) => (it.satId === previewSatId ? { satId: it.satId, eciM: previewEci } : it))
          : [...fleet, { satId: previewSatId, eciM: previewEci }];
      }
      if (track.kind === "satellite") {
        const tid = track.satId;
        if (!fleet.some((it) => it.satId === tid)) {
          const fromPreview = tid === previewSatId ? previewEci : null;
          const ent = entriesByIdRef.current.get(tid);
          const r =
            fromPreview ??
            (ent ? propagateKeplerEntryEciMeters(ent, now) : null);
          if (r) fleet = [...fleet, { satId: tid, eciM: r }];
        }
      }
      globe.setFleetPositions(fleet.length > 0 ? fleet : null);

      const hitsForMarkers = conjunctionHitsRef.current;
      globe.setConjunctionMarkers(
        hitsForMarkers.length > 0 ? conjunctionMarkersForSim(hitsForMarkers) : null,
      );

      const snap = lastGroundTracksRef.current;
      const cfgLoop = maneuverPreviewRef.current;
      const bundleLoop = previewTrajectoryRef.current;
      if (
        snap?.length &&
        cfgLoop &&
        bundleLoop &&
        bundleLoop.satId === cfgLoop.satId &&
        bundleLoop.traj.samples.length >= 2
      ) {
        const pathStyle = isBurnPropagated(cfgLoop) ? "burn_split" : "nominal_single";
        const fresh = buildManeuverGroundTrack(bundleLoop.satId, bundleLoop.traj, cfgLoop.maneuvers, {
          simNowUtc: now,
          pathStyle,
        });
        if (fresh) {
          const others = snap.filter((t) => t.satId !== fresh.satId);
          globe.setGroundTracks([...others, fresh]);
        }
      }

      const selIds = selectedSatIdsRef.current;
      if (selIds.size === 0) {
        globe.setSelectedMarkers(null);
      } else {
        const markers: { satId: string; eciM: [number, number, number] }[] = [];
        for (const id of selIds) {
          const hit = entriesByIdRef.current.get(id);
          if (!hit) continue;
          const r =
            previewSatId === id && previewEci ? previewEci : propagateKeplerEntryEciMeters(hit, now);
          if (!r) continue;
          markers.push({ satId: id, eciM: r });
        }
        globe.setSelectedMarkers(markers.length > 0 ? markers : null);
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [globe, getSimInstant]);

  useEffect(() => {
    if (!globe) return;
    if (selectedSatIds.size === 0 && !maneuverPreviewConfig) {
      lastGroundTracksRef.current = null;
      globe.setGroundTracks(null);
      return;
    }
    let cancelled = false;

    async function loadTracks() {
      const g = globe;
      if (!g) return;
      const sim = getSimInstant();
      const preview = maneuverPreviewRef.current;
      const trackIds: string[] = [...selectedSatIds];
      if (preview?.satId && !selectedSatIds.has(preview.satId)) {
        trackIds.push(preview.satId);
      }
      const tracks: GroundTrack[] = [];
      for (const id of trackIds) {
        const hit = entriesByIdRef.current.get(id) ?? entries.find((e) => e.sat_id === id);
        if (!hit) continue;
        const usePreview = Boolean(preview && preview.satId === id);
        try {
          if (usePreview && preview) {
            const burnedIn = isBurnPropagated(preview);
            const simMs = sim.getTime();
            const anchorIso =
              burnedIn && preview.trajectoryPreviewAnchorUtc ? preview.trajectoryPreviewAnchorUtc : null;
            const startIso = anchorIso ?? sim.toISOString();
            const startMs = Date.parse(startIso);
            const anchorMs = Number.isFinite(startMs) ? startMs : simMs;
            const baseSpanMs = effectiveManeuverTimelineWindowMs(preview, anchorMs);
            const coverToNowMs = Math.max(0, simMs - anchorMs) + 45 * 60 * 1000;
            // Stretch the window to comfortably cover TCA so the green post-burn overlay extends
            // past the predicted close-approach time (selected conjunction context).
            let coverToTcaMs = 0;
            if (!burnedIn) {
              const cid = selectedConjunctionIdRef.current;
              const ev = cid ? conjunctionHitsRef.current.find((e) => e.id === cid) : undefined;
              const tcaMs = ev ? Date.parse(ev.tca_utc) : NaN;
              if (Number.isFinite(tcaMs)) {
                coverToTcaMs = Math.max(0, (tcaMs as number) - anchorMs) + 30 * 60 * 1000;
              }
            }
            const spanMs = Math.max(baseSpanMs, coverToNowMs, coverToTcaMs);
            const durationMinutes = Math.min(24 * 60, Math.max(95, Math.ceil(spanMs / 60000)));
            const stepSeconds = maneuverPreviewStepSeconds(preview, anchorMs);
            const burnsBody = preview.maneuvers.map((m) => ({
              epoch_utc: m.epoch_utc,
              delta_v_mps: m.delta_v_mps,
              frame: m.frame || "ECI",
            }));
            if (burnedIn) {
              const traj = await postTrajectoryPreviewManeuvers(id, {
                start_utc: startIso,
                duration_minutes: durationMinutes,
                step_seconds: stepSeconds,
                maneuvers: burnsBody,
              });
              if (!cancelled) {
                previewTrajectoryRef.current = { satId: id, traj };
                proposedTrajectoryRef.current = null;
              }
              const maneuverTrack = buildManeuverGroundTrack(id, traj, preview.maneuvers, {
                simNowUtc: getSimInstant(),
                pathStyle: "burn_split",
              });
              if (maneuverTrack) tracks.push(maneuverTrack);
            } else {
              // Proposal phase: render the current SGP4 path AND a green post-burn overlay so the
              // operator can compare "current trajectory until collision" with the adjusted orbit.
              const [nominalTraj, propagatedTraj] = await Promise.all([
                fetchSpacecraftTrajectory(id, {
                  start_utc: startIso,
                  duration_minutes: durationMinutes,
                  step_seconds: stepSeconds,
                }),
                postTrajectoryPreviewManeuvers(id, {
                  start_utc: startIso,
                  duration_minutes: durationMinutes,
                  step_seconds: stepSeconds,
                  maneuvers: burnsBody,
                }),
              ]);
              if (!cancelled) {
                previewTrajectoryRef.current = { satId: id, traj: nominalTraj };
                proposedTrajectoryRef.current = { satId: id, traj: propagatedTraj };
              }
              const nominalTrack = buildManeuverGroundTrack(id, nominalTraj, preview.maneuvers, {
                simNowUtc: getSimInstant(),
                pathStyle: "nominal_single",
              });
              if (nominalTrack) tracks.push(nominalTrack);
              const firstBurnMs = preview.maneuvers
                .map((m) => Date.parse(m.epoch_utc))
                .filter((t) => Number.isFinite(t))
                .sort((a, b) => a - b)[0];
              const proposedTrack = buildProposedAfterBurnTrack(id, propagatedTraj, {
                simNowUtc: getSimInstant(),
                firstBurnUtc: Number.isFinite(firstBurnMs) ? new Date(firstBurnMs as number) : undefined,
              });
              if (proposedTrack) tracks.push(proposedTrack);
            }
          } else {
            const traj = await fetchSpacecraftTrajectory(id, {
              start_utc: sim.toISOString(),
              duration_minutes: 95,
              step_seconds: 90,
            });
            const path = trajectoryPathEciFromNow(traj, getSimInstant());
            if (path && path.length >= 2) tracks.push({ satId: id, path });
          }
        } catch (err) {
          if (usePreview) {
            console.warn(`[SpacecraftGlobeLayers] maneuver preview track failed for ${id}`, err);
            if (!cancelled && previewTrajectoryRef.current?.satId === id) {
              previewTrajectoryRef.current = null;
            }
            if (!cancelled && proposedTrajectoryRef.current?.satId === id) {
              proposedTrajectoryRef.current = null;
            }
          }
        }
      }
      if (!cancelled) {
        lastGroundTracksRef.current = tracks.length > 0 ? tracks : null;
        g.setGroundTracks(tracks.length > 0 ? tracks : null);
      }
    }

    void loadTracks();
    const iv = window.setInterval(() => {
      if (!cancelled) void loadTracks();
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(iv);
    };
  }, [globe, selectedSatIds, entries, getSimInstant, maneuverPreviewConfig]);

  const selCount = selectedSatIds.size;

  const label =
    catalogLoading
      ? "Loading catalog…"
      : catalogError
        ? catalogError
        : `${plottedEntries.length.toLocaleString()} plotted${selCount > 0 ? ` · ${selCount} selected` : ""}${previewActive && selCount === 0 ? " · burn plan" : ""}`;

  return (
    <div className="pointer-events-none absolute left-4 top-4 z-10 max-w-md">
      <div className="rounded-lg border border-border/50 bg-background/90 px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground shadow-md ring-1 ring-black/5 backdrop-blur-md dark:bg-background/80 dark:ring-white/10">
        {label}
      </div>
    </div>
  );
}
