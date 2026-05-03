import type { ConjunctionSummary, Epoch, ManeuverPlan } from "@/lib/types";

export const MOCK_EPOCH: Epoch = { instant: "2026-05-02T14:32:00Z", scale: "UTC" };

export const MOCK_CONJUNCTION: ConjunctionSummary = {
  id: "CJX-2041",
  primaryId: "EO-12",
  secondaryId: "DEB-49811",
  tca: { instant: "2026-05-02T16:04:12Z", scale: "UTC" },
  missDistanceKm: 0.62,
  relativeVelocityKmS: 14.8,
  pc: 2.3e-4,
  status: "NEW",
};

export const MOCK_AGENT_PLAN: ManeuverPlan = {
  satId: "EO-12",
  maneuvers: [
    {
      epoch: { instant: "2026-05-02T15:10:00Z", scale: "UTC" },
      deltaVMps: { x: 0.052, y: -0.011, z: 0.004 },
      frame: "RIC",
      durationS: 8,
    },
  ],
  totalDeltaVMps: 0.054,
  objective:
    "Reduce Pc below 1e-4 with minimal in-track cost; preserve ground contacts GS-12 and GS-04.",
  generatedBy: "AGENT",
};
