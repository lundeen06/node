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

// Agent conversation types

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

/** Optional conjunction focused in the ops UI (from latest catalog screening). */
export interface AgentConjunctionContext {
  conjunction_id?: string;
  primary_sat_id?: string;
  secondary_sat_id?: string;
  tca_utc?: string;
  miss_distance_km?: number;
  pc_heuristic?: number;
  source?: string;
}

export interface AgentTurnRequest {
  session_id: string;
  operator_id: string;
  messages: ChatMessage[];
  focus_sat_id?: string;
  conjunction_context?: AgentConjunctionContext;
}

export interface DeltaVMps {
  x: number;
  y: number;
  z: number;
}

export interface ManeuverResponse {
  epoch_utc: string;
  delta_v_mps: DeltaVMps;
  frame: string;
  duration_s?: number;
}

export interface PlanResponse {
  plan_id: string;
  sat_id: string;
  maneuvers: ManeuverResponse[];
  total_delta_v_mps: number;
  objective: string;
  generated_by: string;
  validation_passed: boolean;
}

export interface AgentTurnResponse {
  assistant_message: string;
  proposed_plans: PlanResponse[];
  citations: string[];
}
