/**
 * Hand-written mirrors of backend Pydantic models (replace with OpenAPI codegen later).
 */

export type TimeScale = "UTC" | "UT1" | "TAI" | "TT" | "GPS";

export interface Epoch {
  instant: string;
  scale: TimeScale;
}

export type Frame =
  | "ECI_J2000"
  | "ECI_GCRF"
  | "ECI_TEME"
  | "ECEF_ITRF"
  | "RIC"
  | "VNB"
  | "LVLH"
  | "TOPOCENTRIC";

export interface Vector3Km {
  x: number;
  y: number;
  z: number;
}

export interface StateVector {
  positionKm: Vector3Km;
  velocityKmS: Vector3Km;
  epoch: Epoch;
  frame: Frame;
}

export type ConjunctionStatus = "NEW" | "ACKNOWLEDGED" | "MITIGATED" | "EXPIRED";

export interface ConjunctionSummary {
  id: string;
  primaryId: string;
  secondaryId: string;
  tca: Epoch;
  missDistanceKm: number;
  relativeVelocityKmS: number;
  pc: number;
  status: ConjunctionStatus;
}

export type BurnFrame = "RIC" | "VNB" | "ECI";

export interface Maneuver {
  epoch: Epoch;
  deltaVMps: Vector3Km;
  frame: BurnFrame;
  durationS?: number;
}

export interface ManeuverPlan {
  satId: string;
  maneuvers: Maneuver[];
  totalDeltaVMps: number;
  objective: string;
  generatedBy: "AGENT" | "SOLVER" | "OPERATOR";
}
