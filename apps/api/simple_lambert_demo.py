#!/usr/bin/env python3
"""Pure NumPy: Lambert ΔV between two circular equatorial orbits (7000 km vs 8000 km SMA)."""

from __future__ import annotations

import math

import numpy as np

MU = 3.986004415e14  # Earth GM [m^3/s^2]


def stumpff_c2(psi: float) -> float:
    eps = 1.0
    if psi > eps:
        return (1.0 - math.cos(math.sqrt(psi))) / psi
    if psi < -eps:
        return (math.cosh(math.sqrt(-psi)) - 1.0) / (-psi)
    return 0.5


def stumpff_c3(psi: float) -> float:
    eps = 1.0
    if psi > eps:
        sq = math.sqrt(psi)
        return (sq - math.sin(sq)) / (psi * sq)
    if psi < -eps:
        sn = math.sqrt(-psi)
        return (math.sinh(sn) - sn) / ((-psi) * sn)
    return 1.0 / 6.0


def mean_to_eccentric(M: float, e: float) -> float:
    M = M % (2 * math.pi)
    E = M if e < 0.8 else math.pi
    for _ in range(100):
        f = E - e * math.sin(E) - M
        d = 1 - e * math.cos(E)
        E -= f / d
        if abs(f) < 1e-12:
            break
    return E


def oe_to_rv(a: float, e: float, i: float, raan: float, argp: float, M: float, mu: float) -> tuple[np.ndarray, np.ndarray]:
    """Classical elements (a [m], angles [rad], M mean anomaly) → r, v in SI."""

    def Rx(x: float) -> np.ndarray:
        c, s = math.cos(x), math.sin(x)
        return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])

    def Rz(x: float) -> np.ndarray:
        c, s = math.cos(x), math.sin(x)
        return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])

    E = mean_to_eccentric(M, e)
    nu = 2 * math.atan(math.sqrt((1 + e) / (1 - e)) * math.tan(E / 2))
    p = a * (1 - e**2)
    r = p / (1 + e * math.cos(nu))
    rp = r * np.array([math.cos(nu), math.sin(nu), 0.0])
    vp = math.sqrt(mu / p) * np.array([-math.sin(nu), e + math.cos(nu), 0.0])
    R = Rz(-raan) @ Rx(-i) @ Rz(-argp)
    r_eci = R @ rp
    v_eci = R @ vp
    return r_eci, v_eci


def nu_to_M(nu: float, e: float) -> float:
    E = 2 * math.atan(math.sqrt((1 - e) / (1 + e)) * math.tan(nu / 2))
    return E - e * math.sin(E)


def lambert(r0: np.ndarray, r1: np.ndarray, tof_s: float, mu: float, prograde: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Vallado universal-variable Lambert; positions [m], TOF [s]; v0, v1 [m/s]."""
    r0 = np.asarray(r0, dtype=float).reshape(3)
    r1 = np.asarray(r1, dtype=float).reshape(3)
    t_m = 1.0 if prograde else -1.0
    n0, n1 = np.linalg.norm(r0), np.linalg.norm(r1)
    n01 = n0 * n1
    cdn = float(np.clip(np.dot(r0, r1) / n01, -1.0, 1.0))
    A = t_m * math.sqrt(n0 * n1 * (1.0 + cdn))
    if abs(A) < 1e-12:
        raise ValueError("degenerate geometry")

    psi = 0.0
    psi_lo, psi_hi = -4 * math.pi**2, 4 * math.pi**2
    rtol, numiter = 1e-8, 60
    y = 0.0
    for _ in range(numiter):
        c2, c3 = stumpff_c2(psi), stumpff_c3(psi)
        sq = math.sqrt(c2)
        y = n0 + n1 + A * (psi * c3 - 1.0) / sq
        if A > 0.0:
            while y < 0.0:
                psi_lo = psi
                psi = 0.8 * (1.0 / c3) * (1.0 - n01 * sq / A)
                c2, c3 = stumpff_c2(psi), stumpff_c3(psi)
                sq = math.sqrt(c2)
                y = n0 + n1 + A * (psi * c3 - 1.0) / sq
        xi = math.sqrt(y / c2)
        tof_new = (xi**3 * c3 + A * math.sqrt(y)) / math.sqrt(mu)
        if abs((tof_new - tof_s) / tof_s) < rtol:
            break
        if tof_new <= tof_s:
            psi_lo = psi
        else:
            psi_hi = psi
        psi = (psi_hi + psi_lo) / 2.0
    else:
        raise RuntimeError("Lambert did not converge")

    f = 1.0 - y / n0
    g = A * math.sqrt(y / mu)
    gdot = 1.0 - y / n1
    v0 = (r1 - f * r0) / g
    v1 = (gdot * r1 - r0) / g
    return v0, v1


def main() -> None:
    tof = 3600.0  # s
    e = 1e-8
    i = raan = argp = 0.0

    # Orbit 1: a=7000 km, ν=0  →  M
    a0 = 7000e3
    M0 = nu_to_M(0.0, e)
    r0, v0 = oe_to_rv(a0, e, i, raan, argp, M0, MU)

    # Orbit 2: a=8000 km, ν=90° (avoid collinear r)
    a1 = 8000e3
    M1 = nu_to_M(math.pi / 2, e)
    r2, v2 = oe_to_rv(a1, e, i, raan, argp, M1, MU)

    vt0, vt1 = lambert(r0, r2, tof, MU, prograde=True)
    dv0 = np.linalg.norm(vt0 - v0)
    dv1 = np.linalg.norm(v2 - vt1)
    print("Time of flight (s):", tof)
    print("Time of flight (h):", tof / 3600.0)
    print("Total delta-V (m/s):", dv0 + dv1)
    print("  departure burn:", dv0)
    print("  arrival burn:  ", dv1)


if __name__ == "__main__":
    main()
