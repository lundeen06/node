import * as THREE from "three";

import { EARTH_RADIUS_M, type ECEF } from "./ecef";

/** Scene scale: 1 unit = 1,000 km (keeps Earth ~6.4 units radius, stable for float32). */
export const METERS_PER_SCENE_UNIT = 1_000_000;

export const EARTH_RADIUS_SCENE = EARTH_RADIUS_M / METERS_PER_SCENE_UNIT;

/**
 * WGS84 ECEF (meters, Z = north pole) → Three.js Y-up scene coordinates, scaled.
 */
export function ecefToSceneVector3(ecef: ECEF, target = new THREE.Vector3()): THREE.Vector3 {
  const s = 1 / METERS_PER_SCENE_UNIT;
  const { x, y, z } = ecef;
  return target.set(x * s, z * s, -y * s);
}
