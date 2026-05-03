/**
 * Browser SGP4 (TEME / ECI-like) using the same NORAD SGP4 as the API trajectory route.
 * Positions returned in **meters** for the Three.js globe (matches ``eciMetersToSceneVector3``).
 */

import { propagate, twoline2satrec } from "satellite.js";

export function sgp4PositionEciMeters(
  tleLine1: string,
  tleLine2: string,
  whenUtc: Date,
): [number, number, number] | null {
  try {
    const satrec = twoline2satrec(tleLine1, tleLine2);
    const pv = propagate(satrec, whenUtc);
    const p = pv.position;
    if (typeof p !== "object" || p === null) return null;
    const { x, y, z } = p as { x: number; y: number; z: number };
    if (![x, y, z].every((v) => Number.isFinite(v))) return null;
    return [x * 1000, y * 1000, z * 1000];
  } catch {
    return null;
  }
}
