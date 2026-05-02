/**
 * WGS84 ECEF (Earth-Centered Earth-Fixed), meters.
 * Axes: +X through (0°,0°), +Y through (90°E,0°), +Z through North Pole.
 */
export type ECEF = { x: number; y: number; z: number };

/** Bowring-style closed-form ECEF → geodetic (radians lat/lon, meters height). */
export function ecefToGeodeticWgs84(e: ECEF): { lon: number; lat: number; h: number } {
  const { x, y, z } = e;
  const a = 6378137.0;
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
