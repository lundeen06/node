/**
 * WGS84 ECEF (Earth-Centered Earth-Fixed), meters.
 * Axes: +X through (0°,0°), +Y through (90°E,0°), +Z through North Pole.
 */
export type ECEF = { x: number; y: number; z: number };

/** WGS84 semi-major axis (m); common shorthand “Earth radius” for visualization. */
export const EARTH_RADIUS_M = 6378137.0;

/** Geodetic radians + ellipsoidal height → ECEF (WGS84). */
export function geodeticRadToEcef(lonRad: number, latRad: number, hM: number): ECEF {
  const a = EARTH_RADIUS_M;
  const f = 1 / 298.257223563;
  const e2 = f * (2 - f);
  const sinLat = Math.sin(latRad);
  const cosLat = Math.cos(latRad);
  const cosLon = Math.cos(lonRad);
  const sinLon = Math.sin(lonRad);
  const N = a / Math.sqrt(1 - e2 * sinLat * sinLat);
  const x = (N + hM) * cosLat * cosLon;
  const y = (N + hM) * cosLat * sinLon;
  const z = (N * (1 - e2) + hM) * sinLat;
  return { x, y, z };
}

/** Degrees on WGS84 ellipsoid → ECEF (height above ellipsoid, meters). */
export function lonLatDegHeightToEcef(lonDeg: number, latDeg: number, hM: number): ECEF {
  const r = Math.PI / 180;
  return geodeticRadToEcef(lonDeg * r, latDeg * r, hM);
}

/** Bowring-style closed-form ECEF → geodetic (radians lat/lon, meters height). */
export function ecefToGeodeticWgs84(e: ECEF): { lon: number; lat: number; h: number } {
  const { x, y, z } = e;
  const a = EARTH_RADIUS_M;
  const f = 1 / 298.257223563;
  const b = a * (1 - f);
  const e2 = f * (2 - f);
  const ep2 = (a * a - b * b) / (b * b);

  const p = Math.hypot(x, y);
  const lon = Math.atan2(y, x);
  const theta = Math.atan2(z * a, p * b);
  const st = Math.sin(theta);
  const ct = Math.cos(theta);
  const lat = Math.atan2(z + ep2 * b * st * st * st, p - e2 * a * ct * ct * ct);
  const sinLat = Math.sin(lat);
  const N = a / Math.sqrt(1 - e2 * sinLat * sinLat);
  const h = p / Math.cos(lat) - N;
  return { lon, lat, h };
}

export function geodeticToLngLatDeg(geo: { lon: number; lat: number; h: number }): { lng: number; lat: number; h: number } {
  return {
    lng: (geo.lon * 180) / Math.PI,
    lat: (geo.lat * 180) / Math.PI,
    h: geo.h,
  };
}
