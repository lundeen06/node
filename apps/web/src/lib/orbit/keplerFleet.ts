import type { FleetFolderId } from "@/lib/orbit/constellationGroups";
import { eciMetersToLonLatDeg, oeToPositionMeters, propagateOeJ2 } from "@/lib/orbit/kepler";
import type { SpacecraftMapGeoJSON } from "@/lib/api";

export type KeplerFleetEntry = {
  sat_id: string;
  name: string;
  norad_catalog_id: number;
  purpose: string;
  ephemeris_epoch_utc: string;
  oe: readonly number[];
  folder: FleetFolderId;
};

export function propagateKeplerEntryLonLat(
  entry: KeplerFleetEntry,
  whenUtc: Date,
): [number, number] | null {
  const t0 = Date.parse(entry.ephemeris_epoch_utc);
  if (!Number.isFinite(t0)) return null;
  const dtSec = (whenUtc.getTime() - t0) / 1000;
  const oe = propagateOeJ2(entry.oe, dtSec);
  try {
    const r = oeToPositionMeters(oe);
    return eciMetersToLonLatDeg(r, whenUtc);
  } catch {
    return null;
  }
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
