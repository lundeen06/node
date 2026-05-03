import { MU_EARTH, R_EARTH, normalizeOeSemiMajorAxisMeters } from "@/lib/orbit/kepler";

const RAD2DEG = 180 / Math.PI;

export type ClassicalOeDisplay = {
  aKm: number;
  e: number;
  iDeg: number;
  raanDeg: number;
  argpDeg: number;
  MDeg: number;
  periodMin: number;
  rpKm: number;
  raKm: number;
};

export function classicalFromOe(oe: readonly number[]): ClassicalOeDisplay {
  const n = normalizeOeSemiMajorAxisMeters(oe);
  const a = n[0]!;
  const e = n[1]!;
  const periodMin = (2 * Math.PI * Math.sqrt((a * a * a) / MU_EARTH)) / 60;
  const rpKm = (a * (1 - e) - R_EARTH) / 1000;
  const raKm = (a * (1 + e) - R_EARTH) / 1000;
  return {
    aKm: a / 1000,
    e,
    iDeg: n[2]! * RAD2DEG,
    raanDeg: n[3]! * RAD2DEG,
    argpDeg: n[4]! * RAD2DEG,
    MDeg: n[5]! * RAD2DEG,
    periodMin,
    rpKm,
    raKm,
  };
}
