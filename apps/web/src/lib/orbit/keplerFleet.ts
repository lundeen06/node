import type { FleetFolderId } from "@/lib/orbit/constellationGroups";
import { eciMetersToLonLatDeg, oeToPositionMeters, propagateOeJ2 } from "@/lib/orbit/kepler";
import { sgp4PositionEciMeters } from "@/lib/orbit/sgp4Teme";
import type { SpacecraftMapGeoJSON } from "@/lib/api";

export type KeplerFleetEntry = {
  sat_id: string;
  name: string;
  norad_catalog_id: number;
  purpose: string;
  ephemeris_epoch_utc: string;
  oe: readonly number[];
  folder: FleetFolderId;
  /** When present, globe uses SGP4 (matches API trajectory); otherwise mean-element J2. */
  tle_line1?: string;
  tle_line2?: string;
};

export function propagateKeplerEntryEciMeters(
  entry: KeplerFleetEntry,
  whenUtc: Date,
): [number, number, number] | null {
  if (entry.tle_line1 && entry.tle_line2) {
    const r = sgp4PositionEciMeters(entry.tle_line1, entry.tle_line2, whenUtc);
    if (r) return r;
  }
  const t0 = Date.parse(entry.ephemeris_epoch_utc);
  if (!Number.isFinite(t0)) return null;
  const dtSec = (whenUtc.getTime() - t0) / 1000;
  const oe = propagateOeJ2(entry.oe, dtSec);
  try {
    return oeToPositionMeters(oe);
  } catch {
    return null;
  }
}

export function propagateKeplerEntryLonLat(
  entry: KeplerFleetEntry,
  whenUtc: Date,
): [number, number] | null {
  const r = propagateKeplerEntryEciMeters(entry, whenUtc);
  if (!r) return null;
  return eciMetersToLonLatDeg(r, whenUtc);
}

export function buildGeoJsonFeatures(
  entries: KeplerFleetEntry[],
  whenUtc: Date,
): SpacecraftMapGeoJSON["features"] {
  const features: SpacecraftMapGeoJSON["features"] = [];
  for (const e of entries) {
    const ll = propagateKeplerEntryLonLat(e, whenUtc);
    if (!ll) continue;
    const [lon, lat] = ll;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: {
        sat_id: e.sat_id,
        name: e.name,
        norad_catalog_id: e.norad_catalog_id,
        purpose: e.purpose,
      },
    });
  }
  return features;
}

export function groundTrackKepler(
  entry: KeplerFleetEntry,
  startUtc: Date,
  durationMinutes: number,
  stepSeconds: number,
): [number, number][] {
  const t0 = Date.parse(entry.ephemeris_epoch_utc);
  if (!Number.isFinite(t0)) return [];
  const coords: [number, number][] = [];
  const endMs = startUtc.getTime() + durationMinutes * 60 * 1000;
  const stepMs = stepSeconds * 1000;
  for (let t = startUtc.getTime(); t <= endMs; t += stepMs) {
    const d = new Date(t);
    const dtSec = (t - t0) / 1000;
    const oe = propagateOeJ2(entry.oe, dtSec);
    try {
      const r = oeToPositionMeters(oe);
      coords.push(eciMetersToLonLatDeg(r, d));
    } catch {
      /* skip sample */
    }
  }
  return coords.length >= 2 ? coords : [];
}

/** Inertial ground track (ECI meters) — prefer SGP4 API for accuracy; see ``SpacecraftGlobeLayers``. */
export function groundTrackKeplerEci(
  entry: KeplerFleetEntry,
  startUtc: Date,
  durationMinutes: number,
  stepSeconds: number,
): [number, number, number][] {
  const t0 = Date.parse(entry.ephemeris_epoch_utc);
  if (!Number.isFinite(t0)) return [];
  const coords: [number, number, number][] = [];
  const endMs = startUtc.getTime() + durationMinutes * 60 * 1000;
  const stepMs = stepSeconds * 1000;
  for (let t = startUtc.getTime(); t <= endMs; t += stepMs) {
    const dtSec = (t - t0) / 1000;
    const oe = propagateOeJ2(entry.oe, dtSec);
    try {
      coords.push(oeToPositionMeters(oe));
    } catch {
      /* skip */
    }
  }
  return coords.length >= 2 ? coords : [];
}
