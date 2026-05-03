/**
 * Keplerian propagation aligned with ``physics.propulsion.util_dyn.propagate_oe`` (J2 secular)
 * and ``oe_to_pv`` (two-body position in ECI, meters).
 */

export const MU_EARTH = 3.986004415e14;
export const R_EARTH = 6.3781363e6;
export const J2 = 0.001082635819197;

const TWO_PI = 2 * Math.PI;

export function mod2pi(x: number): number {
  return ((x % TWO_PI) + TWO_PI) % TWO_PI;
}

/** Port of ``util_dyn.mean_to_ecc_anomaly`` (elliptic). */
export function meanToEccAnomaly(M: number, e: number, tol = 1e-8, maxIter = 100): number {
  let Mw = M % TWO_PI;
  if (Mw < 0) Mw += TWO_PI;
  let E: number;
  if (e < 0.8) {
    E = Mw;
  } else {
    E = Math.PI;
  }
  const Mt = Mw;
  for (let k = 0; k < maxIter; k++) {
    const f = E - e * Math.sin(E) - Mt;
    const fp = 1 - e * Math.cos(E);
    const dE = -f / fp;
    E += dE;
    if (Math.abs(dE) < tol) return E;
  }
  return E;
}

/** Secular J2 propagation from oe0 at dt seconds (matches ``propagate_oe`` scalar path). */
export function propagateOeJ2(oe0: readonly number[], dtSec: number): number[] {
  const mu = MU_EARTH;
  const R = R_EARTH;
  const J2v = J2;
  const a = oe0[0];
  const e = oe0[1];
  const i = oe0[2];
  const n = Math.sqrt(mu / (a * a * a));
  const eta = Math.sqrt(1 - e * e);
  const kappa = (0.75 * J2v * R * R * Math.sqrt(mu)) / (Math.pow(a, 3.5) * eta ** 4);
  const P = 3 * Math.cos(i) ** 2 - 1;
  const Q = 5 * Math.cos(i) ** 2 - 1;
  const raanDot = -2 * Math.cos(i) * kappa;
  const aopDot = kappa * Q;
  const mDot = n + kappa * eta * P;
  const dt = dtSec;
  return [
    oe0[0],
    oe0[1],
    oe0[2],
    mod2pi(oe0[3] + raanDot * dt),
    mod2pi(oe0[4] + aopDot * dt),
    mod2pi(oe0[5] + mDot * dt),
  ];
}

function Rz(a: number): number[][] {
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [
    [c, s, 0],
    [-s, c, 0],
    [0, 0, 1],
  ];
}

function Rx(a: number): number[][] {
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [
    [1, 0, 0],
    [0, c, s],
    [0, -s, c],
  ];
}

function matMul33(A: number[][], B: number[][]): number[][] {
  const C = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
  ];
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      let s = 0;
      for (let k = 0; k < 3; k++) s += A[i][k]! * B[k][j]!;
      C[i]![j] = s;
    }
  }
  return C;
}

function matVec33(A: number[][], v: readonly [number, number, number]): [number, number, number] {
  return [
    A[0]![0]! * v[0] + A[0]![1]! * v[1] + A[0]![2]! * v[2],
    A[1]![0]! * v[0] + A[1]![1]! * v[1] + A[1]![2]! * v[2],
    A[2]![0]! * v[0] + A[2]![1]! * v[1] + A[2]![2]! * v[2],
  ];
}

/** ECI position (meters) from classical elements (same convention as ``util_dyn.oe_to_pv``). */
export function oeToPositionMeters(oe: readonly number[]): [number, number, number] {
  const a = oe[0]!;
  const e = oe[1]!;
  const i = oe[2]!;
  const Omega = oe[3]!;
  const omega = oe[4]!;
  const M = oe[5]!;
  const E = meanToEccAnomaly(M, e);
  const nu = 2 * Math.atan(Math.sqrt((1 + e) / (1 - e)) * Math.tan(E / 2));
  const p = a * (1 - e * e);
  const r = p / (1 + e * Math.cos(nu));
  const rp: [number, number, number] = [r * Math.cos(nu), r * Math.sin(nu), 0];
  const R = matMul33(matMul33(Rz(-Omega), Rx(-i)), Rz(-omega));
  return matVec33(R, rp);
}

/** Julian date (days) for UTC instant — matches ``node_api.lib.geodesy._julian_date`` algorithm. */
export function julianDateUtc(date: Date): number {
  const y = date.getUTCFullYear();
  let m = date.getUTCMonth() + 1;
  let yAdj = y;
  const d =
    date.getUTCDate() +
    date.getUTCHours() / 24 +
    date.getUTCMinutes() / 1440 +
    date.getUTCSeconds() / 86400 +
    date.getUTCMilliseconds() / 86400000;
  let y2 = yAdj;
  let m2 = m;
  if (m2 <= 2) {
    y2 -= 1;
    m2 += 12;
  }
  const a = Math.floor(y2 / 100);
  const b = 2 - a + Math.floor(a / 4);
  return Math.floor(365.25 * (y2 + 4716)) + Math.floor(30.6001 * (m2 + 1)) + d + b - 1524.5;
}

/** GMST radians — matches ``node_api.lib.geodesy.gmst_radians``. */
export function gmstRadiansUtc(date: Date): number {
  const jd = julianDateUtc(date);
  const t = (jd - 2451545.0) / 36525.0;
  let gmstDeg =
    280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * t * t - (t * t * t) / 38710000.0;
  gmstDeg %= 360;
  if (gmstDeg < 0) gmstDeg += 360;
  return (gmstDeg * Math.PI) / 180;
}

/** Approximate ECI (m) → (lon, lat) degrees via GMST z-rotation, matching API maps. */
export function eciMetersToLonLatDeg(rEci: readonly [number, number, number], dateUtc: Date): [number, number] {
  const gmst = gmstRadiansUtc(dateUtc);
  const c = Math.cos(gmst);
  const s = Math.sin(gmst);
  const x = c * rEci[0]! + s * rEci[1]!;
  const y = -s * rEci[0]! + c * rEci[1]!;
  const z = rEci[2]!;
  const lonRad = Math.atan2(y, x);
  const latRad = Math.atan2(z, Math.hypot(x, y));
  return [(lonRad * 180) / Math.PI, (latRad * 180) / Math.PI];
}
