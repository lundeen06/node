# Domain glossary

Short definitions for orbital operations and data products used across **node**. Intended for engineers new to flight dynamics or conjunction assessment.

## Time and frames

| Term | Meaning |
|------|--------|
| **UTC** | Coordinated Universal Time; civil time basis for operations and logging. |
| **UT1** | Earth rotation angle time; used with IERS models for ECEF rotation. |
| **TAI** | International Atomic Time; uniform atomic clock time without leap seconds. |
| **TT** | Terrestrial Time; uniform dynamical time scale used in ephemerides. |
| **GPS time** | Time scale used by GPS navigation messages (offset from TAI). |
| **Epoch** | An instant in time with an explicit time scale—never an ambiguous “naive” datetime. |
| **ECI** | Earth-Centered Inertial: origin at Earth center, axes fixed to celestial references (e.g. J2000, GCRF, TEME). |
| **ECEF** | Earth-Centered Earth-Fixed: rotates with Earth (e.g. ITRF). |
| **RIC** | Radial-In-Cross-track: local frame aligned with position/velocity of a reference orbit. |
| **VNB** | Velocity-Normal-Binormal: another local orbital frame variant. |
| **LVLH** | Local Vertical Local Horizontal: common for rendezvous/cooperative ops. |
| **Topocentric** | Horizon-based frame tied to a ground site (azimuth/elevation context). |
| **RAAN** | Right Ascension of the Ascending Node: orientation of the orbital plane around Earth’s spin axis. |
| **Argument of periapsis (ω)** | Angle in the orbital plane from ascending node to periapsis. |
| **True anomaly (ν)** | Angle from periapsis to current position along the orbit. |
| **Mean anomaly (M)** | Keplerian angle linear in time for two-body motion; related to ν through Kepler’s equation. |

## State representations

| Term | Meaning |
|------|--------|
| **State vector** | Position and velocity in a specific frame at a specific epoch (units explicit, e.g. km, km/s). |
| **Keplerian elements** | Classical orbital elements (a, e, i, RAAN, ω, ν or M). Singular for e→0 or i→0 unless handled with equinoctial or other nonsingular forms. |
| **Equinoctial elements** | Nonsingular element set preferred for near-circular or near-equatorial orbits. |
| **Covariance 6×6** | Uncertainty on position/velocity in a consistent frame and epoch with the mean state. |

## Catalog and ephemeris products

| Term | Meaning |
|------|--------|
| **NORAD ID** | Catalog number identifying an Earth-orbiting object in public catalogs. |
| **TLE** | Two-Line Element set: mean elements for SGP4 propagation (not osculating truth). |
| **OEM** | Orbit Ephemeris Message (CCSDS): time-tagged state history or prediction with metadata. |
| **CDM** | Conjunction Data Message: standardized close-approach warning between two objects, including miss distance, relative speed, states, covariances, and often Pc. |

## Conjunction assessment

| Term | Meaning |
|------|--------|
| **TCA** | Time of Closest Approach: epoch of minimum miss distance in a screened encounter. |
| **Miss distance** | Minimum spatial separation between two hard bodies (or their uncertainty ellipsoids) at TCA—geometric, not probabilistic. |
| **Pc** | Probability of collision: risk metric combining geometry and state uncertainty; method-dependent. |
| **Close approach** | Geometric encounter (miss distance, TCA, relative velocity) **without** necessarily computing Pc. |
| **CDM originator** | Agency or system that produced the conjunction message. |

## Maneuvers and operations

| Term | Meaning |
|------|--------|
| **Δv** | Change in velocity vector (impulsive idealization or integrated for finite burns). |
| **RIC burn** | Δv expressed in radial/in-track/cross-track components relative to a reference trajectory. |
| **Finite burn** | Maneuver realized over non-negligible duration with thrust and attitude profiles. |
| **Operational box (keep-in)** | Allowed region in element space or state space for routine operations. |
| **Keep-out zone** | Forbidden region (volume, geographic, or temporal) for safety or policy. |

## Space weather

| Term | Meaning |
|------|--------|
| **Kp / Ap** | Geomagnetic activity indices. |
| **F10.7** | Solar radio flux at 10.7 cm; proxy for EUV heating of the upper atmosphere (drag drivers). |

## Governance

| Term | Meaning |
|------|--------|
| **Approval record** | Cryptographically or procedurally attested operator (or policy) approval tying a human or automated gate to a specific plan before Layer-9 actions execute. |
| **Audit entry** | Append-only record of agent suggestions, operator decisions, and executed actions. |
