import type { TrajectoryResponse } from "@/lib/api";
import type { GroundTrack, GroundTrackBurnArrow, GroundTrackSegment } from "@/components/globe/earthGlobeRenderer";

/** Pre-first-burn / nominal arc (slate). */
export const MANEUVER_LEG_INITIAL = 0x64748b;
/** Between burns — transfer arc (amber). */
export const MANEUVER_LEG_TRANSFER = 0xf59e0b;
/** After final burn — target orbit (teal). */
export const MANEUVER_LEG_FINAL = 0x2dd4bf;
/** Δv arrow — first burn (rose). */
export const MANEUVER_BURN_ARROW_0 = 0xfb7185;
/** Δv arrow — second burn (violet). */
export const MANEUVER_BURN_ARROW_1 = 0xc084fc;
/** Proposed post-burn orbit overlay (green-500): "what the trajectory would be if accepted". */
export const MANEUVER_PROPOSED_PATH = 0x22c55e;

type Sample = { t: number; p: [number, number, number] };

function parseSamples(traj: TrajectoryResponse): Sample[] {
  const out: Sample[] = [];
  for (const s of traj.samples) {
    const t = Date.parse(s.epoch_utc);
    if (!Number.isFinite(t)) continue;
    out.push({
      t,
      p: [s.position_km[0]! * 1000, s.position_km[1]! * 1000, s.position_km[2]! * 1000],
    });
  }
  out.sort((a, b) => a.t - b.t);
  return out;
}

/** Keep samples from ``nowMs`` onward (interpolated point at sim time as the first vertex). */
function clipSamplesToFuture(samples: Sample[], nowMs: number): Sample[] {
  if (samples.length === 0) return [];
  if (nowMs <= samples[0]!.t) return samples;
  const last = samples[samples.length - 1]!;
  if (nowMs >= last.t) {
    const p = last.p;
    return [
      { t: nowMs, p: [p[0]!, p[1]!, p[2]!] },
      { t: nowMs + 1, p: [p[0]!, p[1]!, p[2]!] },
    ];
  }
  let lo = 0;
  let hi = samples.length - 1;
  while (hi - lo > 1) {
    const mid = Math.floor((lo + hi) / 2);
    if (samples[mid]!.t <= nowMs) lo = mid;
    else hi = mid;
  }
  const a = samples[lo]!;
  const b = samples[hi]!;
  const span = b.t - a.t;
  const u = span > 0 ? (nowMs - a.t) / span : 0;
  const p: [number, number, number] = [
    a.p[0]! + u * (b.p[0]! - a.p[0]!),
    a.p[1]! + u * (b.p[1]! - a.p[1]!),
    a.p[2]! + u * (b.p[2]! - a.p[2]!),
  ];
  const head: Sample = { t: nowMs, p };
  return [head, ...samples.slice(hi)];
}

/**
 * ECI polyline (m) for ground tracks: only the portion at or after ``whenUtc`` along sample times.
 * Returns at least two points when any geometry exists (degenerate end-of-window uses a duplicated point).
 */
export function trajectoryPathEciFromNow(
  traj: TrajectoryResponse,
  whenUtc: Date,
): [number, number, number][] | null {
  const clipped = clipSamplesToFuture(parseSamples(traj), whenUtc.getTime());
  if (clipped.length === 0) return null;
  if (clipped.length === 1) {
    const s = clipped[0]!;
    return [s.p, s.p];
  }
  return clipped.map((s) => s.p);
}

/**
 * ECI position (m) on a trajectory polyline at ``whenUtc`` (linear interp between samples).
 * Used for burn-arrow placement and (when applicable) fleet alignment with that polyline.
 */
export function positionEciMetersFromTrajectoryAt(
  traj: TrajectoryResponse,
  whenUtc: Date,
): [number, number, number] | null {
  const whenMs = whenUtc.getTime();
  const samples = parseSamples(traj);
  if (samples.length === 0) return null;
  if (whenMs <= samples[0]!.t) return samples[0]!.p;
  const last = samples[samples.length - 1]!;
  if (whenMs >= last.t) return last.p;
  let lo = 0;
  let hi = samples.length - 1;
  while (hi - lo > 1) {
    const mid = Math.floor((lo + hi) / 2);
    if (samples[mid]!.t <= whenMs) lo = mid;
    else hi = mid;
  }
  const a = samples[lo]!;
  const b = samples[hi]!;
  const span = b.t - a.t;
  const u = span > 0 ? (whenMs - a.t) / span : 0;
  return [
    a.p[0]! + u * (b.p[0]! - a.p[0]!),
    a.p[1]! + u * (b.p[1]! - a.p[1]!),
    a.p[2]! + u * (b.p[2]! - a.p[2]!),
  ];
}

/** Largest index with sample time strictly before ``burnT``, or -1. */
function lastIndexBefore(samples: Sample[], burnT: number): number {
  let lo = -1;
  for (let i = 0; i < samples.length; i++) {
    if (samples[i]!.t < burnT) lo = i;
    else break;
  }
  return lo;
}

function uniqueMarks(raw: number[], n: number): number[] {
  const sorted = [...new Set(raw)].filter((x) => x >= 0 && x <= n).sort((a, b) => a - b);
  const out: number[] = [0];
  for (const x of sorted) {
    if (x > out[out.length - 1]!) out.push(x);
  }
  if (out[out.length - 1]! < n) out.push(n);
  return out;
}

function legColor(legIndex: number, burnCount: number): number {
  if (legIndex === 0) return MANEUVER_LEG_INITIAL;
  if (legIndex >= burnCount) return MANEUVER_LEG_FINAL;
  return MANEUVER_LEG_TRANSFER;
}

function burnArrowColor(i: number): number {
  return i === 0 ? MANEUVER_BURN_ARROW_0 : MANEUVER_BURN_ARROW_1;
}

export type BuildManeuverGroundTrackOpts = {
  /** When set, Δv arrows are omitted once sim time is past each burn epoch (``simNowUtc.getTime() > burn``). */
  simNowUtc?: Date;
  /**
   * ``nominal_single``: one orbit-colored path (catalog/SGP4 samples) + Δv arrows at burn epochs — no post-Δv coast.
   * ``burn_split``: colored legs between burns (use with a trajectory that already includes maneuver propagation).
   */
  pathStyle?: "nominal_single" | "burn_split";
};

/**
 * Ground track from trajectory samples plus optional Δv arrows at maneuver epochs.
 */
export function buildManeuverGroundTrack(
  satId: string,
  traj: TrajectoryResponse,
  maneuvers: ReadonlyArray<{
    epoch_utc: string;
    delta_v_mps: { x: number; y: number; z: number };
  }>,
  opts?: BuildManeuverGroundTrackOpts,
): GroundTrack | null {
  const simNowUtc = opts?.simNowUtc;
  const pathStyle = opts?.pathStyle ?? "burn_split";
  let samples = parseSamples(traj);
  if (simNowUtc !== undefined) {
    samples = clipSamplesToFuture(samples, simNowUtc.getTime());
  }
  if (samples.length < 2) {
    if (samples.length === 1) {
      const s = samples[0]!;
      samples = [s, { t: s.t + 1, p: [s.p[0]!, s.p[1]!, s.p[2]!] }];
    } else return null;
  }

  const burnRaw = [...maneuvers]
    .map((m) => ({
      t: Date.parse(m.epoch_utc),
      dv: m.delta_v_mps,
    }))
    .filter((x) => Number.isFinite(x.t))
    .sort((a, b) => a.t - b.t);
  const seenT = new Set<number>();
  const burnMs = burnRaw.filter((b) => {
    if (seenT.has(b.t)) return false;
    seenT.add(b.t);
    return true;
  });

  const segments: GroundTrackSegment[] = [];
  const windowStartT = samples[0]!.t;
  const burnMsForSplits = burnMs.filter((b) => b.t >= windowStartT - 1e-6);
  if (pathStyle === "nominal_single") {
    const path = samples.map((s) => s.p);
    if (path.length >= 2) {
      segments.push({ path, color: MANEUVER_LEG_INITIAL });
    }
  } else {
    const rawMarks: number[] = [0];
    for (const b of burnMsForSplits) {
      rawMarks.push(lastIndexBefore(samples, b.t) + 1);
    }
    rawMarks.push(samples.length);
    const marks = uniqueMarks(rawMarks, samples.length);

    for (let k = 0; k < marks.length - 1; k++) {
      const a = marks[k]!;
      const b = marks[k + 1]!;
      const slice = samples.slice(a, b).map((s) => s.p);
      if (slice.length < 2) continue;
      segments.push({ path: slice, color: legColor(k, burnMs.length) });
    }
  }

  const nowMs = simNowUtc !== undefined ? simNowUtc.getTime() : undefined;
  const burns: GroundTrackBurnArrow[] = [];
  for (let bi = 0; bi < burnMs.length; bi++) {
    const b = burnMs[bi]!;
    if (nowMs !== undefined && nowMs > b.t) {
      continue;
    }
    const onChord =
      positionEciMetersFromTrajectoryAt(traj, new Date(b.t)) ??
      (() => {
        let best = 0;
        let bestDt = Infinity;
        for (let i = 0; i < samples.length; i++) {
          const dt = Math.abs(samples[i]!.t - b.t);
          if (dt < bestDt) {
            bestDt = dt;
            best = i;
          }
        }
        return samples[best]!.p;
      })();
    burns.push({
      positionEciM: onChord,
      deltaVEciMps: [b.dv.x, b.dv.y, b.dv.z],
      color: burnArrowColor(bi),
    });
  }

  return { satId, segments, burns };
}

/**
 * Green "proposed" overlay path drawn from the propagated trajectory (post-burn).
 *
 * The path is clipped to start at the **first burn epoch** when one is provided (so the green
 * overlay doesn't overdraw the nominal pre-burn arc), or at ``simNowUtc`` otherwise.
 *
 * Uses ``GroundTrack.path`` + ``pathColor`` (single color line). ``satId`` is suffixed with
 * ``__proposed`` so the renderer pool keys don't collide with the nominal track; ``pickSatId``
 * routes picking back to the real satellite id.
 */
export function buildProposedAfterBurnTrack(
  satId: string,
  propagatedTraj: TrajectoryResponse,
  opts?: { simNowUtc?: Date; firstBurnUtc?: Date },
): GroundTrack | null {
  const samples = parseSamples(propagatedTraj);
  if (samples.length < 2) return null;
  const burnMs = opts?.firstBurnUtc?.getTime();
  const simMs = opts?.simNowUtc?.getTime();
  const startMs = Number.isFinite(burnMs)
    ? (burnMs as number)
    : Number.isFinite(simMs)
      ? (simMs as number)
      : samples[0]!.t;
  const clipped = clipSamplesToFuture(samples, startMs);
  if (clipped.length < 2) return null;
  return {
    satId: `${satId}__proposed`,
    pickSatId: satId,
    path: clipped.map((s) => s.p),
    pathColor: MANEUVER_PROPOSED_PATH,
  };
}
