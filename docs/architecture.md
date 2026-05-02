# node library architecture

The **node** backend exposes a typed function library that an AI agent calls like tools. Functions are grouped into **nine conceptual layers** (0–9). Lower layers are pure transforms and data access; higher layers encode mission intent, validation, and **gated actions** that require human accountability.

## Layer 0 — Ingress (`lib/ingress/`)

External data providers: TLE/CDM feeds, catalog snapshots, space weather, Earth orientation parameters. No propagation or screening—only fetch, normalize, and subscribe.

## Layer 1 — Frames (`lib/frames.py`)

Time and reference frame conversions: ECI/ECEF/RIC/VNB/LVLH, geodetic ↔ ECEF, element sets ↔ Cartesian state. All outputs carry explicit `Frame` and `Epoch` metadata.

## Layer 2 — Propagation (`lib/propagation.py`)

Trajectory prediction: analytic (e.g. SGP4), numerical with force models, and uncertainty-aware propagation. Consumes states/catalog inputs from ingress or frames.

## Layer 3 — Conjunction (`lib/conjunction.py`)

Close-approach search, probability of collision (Pc) computation, and catalog screening against ego or full constellation geometry.

## Layer 4 — Environment (`lib/environment.py`)

Mission constraints tied to the physical environment: ground passes, eclipses, sun geometry, thermal and radiation exposure estimates, and geometric checks against keep-out volumes.

## Layer 5 — Solvers (`lib/solvers/`)

Maneuver primitives: impulsive transfers (Hohmann, Lambert), avoidance timing, finite-burn and low-thrust parameterizations. These return **plans** or burn parameters, not executed commands.

## Layer 6 — Mission (`lib/mission/`)

End-to-end operational recipes: collision avoidance, station keeping, phasing, plane change, deorbit, replenishment. They orchestrate solvers and propagate post-maneuver states.

## Layer 7 — Validation (`lib/validation.py`)

Post-solve checks: induced conjunction risk, keep-out and fuel compliance, policy gates. Always run after solvers or mission planners produce a candidate plan.

## Layer 8 — Constellation (`lib/constellation.py`)

Multi-satellite coordination: collective avoidance, phasing across slots, fleet-level constraints.

## Layer 9 — Actions (`lib/actions.py`)

**Side effects**: queue maneuvers, schedule uplinks, acknowledge CDMs, append audit logs. Every function in this layer **requires** an `ApprovalRecord` so accountability is enforced in the type system.

## Automation graphs (backend model only)

`WorkflowGraph` and related Pydantic types describe **headless automation graphs** (nodes reference library functions by string id, edges wire outputs to inputs, `ExecutionPolicy` encodes thresholds). There is no dedicated product UI for this in the current web shell.

## HTTP surface

FastAPI routes in `routes/` are thin wrappers over `lib/`. During scaffold they return `501 Not Implemented` while the route and import surface are stabilized.
