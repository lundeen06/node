/** Default horizon for burn UI + trajectory preview (minutes). */
export const MANEUVER_TIMELINE_DEFAULT_MIN = 95;
/** Post-last-burn coast on the timeline (minutes), aligned with API preview extension. */
export const MANEUVER_TIMELINE_POST_BURN_MIN = 30;

const DEFAULT_WINDOW_MS = MANEUVER_TIMELINE_DEFAULT_MIN * 60 * 1000;
const POST_BURN_TAIL_MS = MANEUVER_TIMELINE_POST_BURN_MIN * 60 * 1000;

/**
 * Fixed sim-time width (ms) for the burn strip: ``max(95m, lastBurn + 30m − anchor)`` at plan apply.
 * Holding this constant while ``now`` advances makes bar position = ``(burn − now) / width`` affine in sim time.
 */
export function computeManeuverTimelineWindowMs(
  anchorUtcMs: number,
  maneuvers: ReadonlyArray<{ epoch_utc: string }>,
): number {
  let lastBurnMs = 0;
  for (const m of maneuvers) {
    const t = Date.parse(m.epoch_utc);
    if (Number.isFinite(t)) lastBurnMs = Math.max(lastBurnMs, t);
  }
  if (lastBurnMs <= 0) return DEFAULT_WINDOW_MS;
  return Math.max(DEFAULT_WINDOW_MS, lastBurnMs + POST_BURN_TAIL_MS - anchorUtcMs);
}

/** Resolve stored window or recompute from sim anchor (legacy configs without ``timelineWindowMs``). */
export function effectiveManeuverTimelineWindowMs(
  preview: { maneuvers: ReadonlyArray<{ epoch_utc: string }>; timelineWindowMs?: number },
  fallbackAnchorUtcMs: number,
): number {
  const w = preview.timelineWindowMs;
  if (w != null && Number.isFinite(w) && w > 0) return w;
  return computeManeuverTimelineWindowMs(fallbackAnchorUtcMs, preview.maneuvers);
}
