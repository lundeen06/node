/**
 * Demo orbit stub — **not** a real SGP4 pipeline.
 *
 * **Frames (important for your propagator):**
 * - `eciLikePosition` returns a vector in an **Earth-centered inertial (ECI-like)** sense: classical
 *   elements are applied as a fixed rotation from the orbital plane into **equatorial inertial**
 *   axes (X/Y in the equatorial plane, Z = north pole). The Earth does **not** rotate underneath
 *   that vector between time steps.
 * - `getSatelliteECEF` then applies a **crude Z-rotation** (`gmst` stand-in) to mimic body-fixed
 *   longitude drift. The result is labeled `ECEF` for the renderer, but it is **not** rigorous
 *   WGS84 ECEF (no full IAU / IERS reduction).
 *
 * **When you wire a real propagator:** pick one output frame and convert explicitly:
 * - Many libraries give **TEME** (SGP4) or **ECEF** directly — transform to **ECEF** (ITRF) for
 *   a rotating globe texture, or keep **ECI** and rotate Earth / use a star-fixed camera.
 * - If your propagator outputs **ECI (J2000 / GCRF)**, multiply by the time-varying **ECI→ECEF**
 *   rotation (GMST / ERA + polar motion if you care) before feeding `ecefToSceneVector3`.
 */
import type { ECEF } from "./ecef";

import { MOCK_SATELLITES } from "@/lib/mock-data";

/** WGS84 equatorial radius (m). */
export const EARTH_RADIUS_M = 6378137;

/** μ for Earth (m³/s²) */
const GM = 3.986004418e14;

export const SATELLITE_IDS = MOCK_SATELLITES.map((s) => s.id) as readonly string[];

type OrbitParams = {
  a: number;
  inc: number;
  raan: number;
  argp: number;
  ma0: number;
  n: number;
};

function orbitForIndex(idx: number): OrbitParams {
  const alt = 520e3 + idx * 180e3;
  const a = EARTH_RADIUS_M + alt;
  const n = Math.sqrt(GM / (a * a * a));
  return {
    a,
    inc: (51.6 + idx * 7) * (Math.PI / 180),
    raan: (idx * 47 + 12) * (Math.PI / 180),
    argp: (idx * 31 + 5) * (Math.PI / 180),
    ma0: (idx * 19) * (Math.PI / 180),
    n,
  };
}

/** Circular orbit: classical elements → Cartesian in **ECI-like equatorial inertial** axes (m). */
function eciLikePosition(o: OrbitParams, tSec: number): { x: number; y: number; z: number } {
  const M = o.ma0 + o.n * tSec;
  const r = o.a;
  const u = M;
  const cosu = Math.cos(u);
  const sinu = Math.sin(u);
  const xOrb = r * cosu;
  const yOrb = r * sinu;
  const zOrb = 0;

  const cosΩ = Math.cos(o.raan);
  const sinΩ = Math.sin(o.raan);
  const cosi = Math.cos(o.inc);
  const sini = Math.sin(o.inc);
  const cosω = Math.cos(o.argp);
  const sinω = Math.sin(o.argp);

  const px = cosω * xOrb - sinω * yOrb;
  const py = sinω * xOrb + cosω * yOrb;
  const pz = zOrb;

  const x1 = px;
  const y1 = cosi * py - sini * pz;
  const z1 = sini * py + cosi * pz;

  const x = cosΩ * x1 - sinΩ * y1;
  const y = sinΩ * x1 + cosΩ * y1;
  const z = z1;
  return { x, y, z };
}

function satIndex(satId: string): number {
  const i = SATELLITE_IDS.indexOf(satId as (typeof SATELLITE_IDS)[number]);
  return i < 0 ? 0 : i;
}

/**
 * Cartesian position (meters) for rendering — **stub**: ECI-like orbit + toy body rotation.
 * Replace with your propagator output; if you get true **ECI**, convert to **ECEF** before plotting
 * on a rotating Earth. See file-level comment above.
 *
 * @param timeMs Wall clock or simulation time (ms).
 */
export function getSatelliteECEF(timeMs: number, satId: string): ECEF {
  const idx = satIndex(satId);
  const tSec = timeMs / 1000;
  const o = orbitForIndex(idx);
  const p = eciLikePosition(o, tSec);
  const gmst = 7.292115e-5 * tSec * 0.35;
  const cg = Math.cos(gmst);
  const sg = Math.sin(gmst);
  return {
    x: cg * p.x - sg * p.y,
    y: sg * p.x + cg * p.y,
    z: p.z,
  };
}

/**
 * Orbit polyline samples — same frame contract as {@link getSatelliteECEF}.
 */
export function sampleOrbitPathECEF(timeMs: number, satId: string, durationMs: number, steps: number): ECEF[] {
  if (steps < 2) return [];
  const out: ECEF[] = [];
  for (let i = 0; i < steps; i++) {
    const t = timeMs + (durationMs * i) / (steps - 1);
    out.push(getSatelliteECEF(t, satId));
  }
  return out;
}
