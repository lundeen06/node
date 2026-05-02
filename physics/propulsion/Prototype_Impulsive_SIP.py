# Imports:
# %load_ext autoreload
# %autoreload 2

import os 
import sys 
import numpy as np 
import matplotlib.pyplot as plt

def find_root_path(path:str, word:str):
    parts = path.split(word, 1)
    if len(parts) > 1:
        return parts[0] + word
    else:
        return path

root_folder = find_root_path(os.getcwd(), 'Code')
sys.path.append(root_folder)

from util_dyn import * 
from impulsiveSIP import *
from Run_Code import params
from Trajectory_Selection.Trajectory_Candidates import trajectory_candidates

# === Define Constants ===
# Earth parameters
J2 = 0.001082635819197
R_E = 6.3781363e+06    # Earth radius [m]
mu_E = 3.986004415e+14 # Earth gravitational parameter [m^3/s^2]


# === Initial conditions ===
oe_chief_0 = np.array([params.a_chief*1e3, params.e_chief, params.i_chief, params.raan_chief, params.w_chief, params.M_chief])


# === Time settings ===
t0_sec = 0
tf_sec = params.T_single_orbit

# === Get Initial and Final QNS ROEs ===
# Call the generate candidates function
roe_candidates = trajectory_candidates()
# For now define the first ROE as the initial orbit
roe0 = roe_candidates[0]
roe0 = roe0*params.a_chief*1e3
# For now define the second ROE as the final orbit:
roef = roe_candidates[2]
roef = roef*params.a_chief*1e3

# === Use ROE-based propagation with QNS ROEs ===
# Define lambda-functions - STMs as a function of time
B = lambda t: cim_roe(propagate_oe(oe_chief_0, t - t0_sec, mu_E, J2), mu_E)
Φ = lambda t2, t1: stm_roe(propagate_oe(oe_chief_0, t1 - t0_sec, mu_E, J2), t2 - t1, mu_E, R_E, J2)
Γ = lambda t: Φ(tf_sec, t) @ B(t)

nx = roe0.size
assert Φ(tf_sec, t0_sec).shape == (nx, nx), f"Φ shape is {Φ(tf_sec, t0_sec).shape}, expected {(nx,nx)}"
assert B(t0_sec).shape == (nx, 3),          f"B shape is {B(t0_sec).shape}, expected {(nx,3)}"
assert Γ(t0_sec).shape == (nx, 3),           f"Γ shape is {Γ(t0_sec).shape}, expected {(nx,3)}"


# === Run SIP ===
SIP = impulsiveSIP(Φ, Γ, roe0, roef, t0_sec, tf_sec)
topt, uopt, λopt = SIP.solve()

# === Filter and print ===
epsilon = 1e-3
mask = np.linalg.norm(uopt, axis=1) > epsilon
topt = topt[mask]
uopt = uopt[mask].T

print("solved!")
print("optimal burn times (sec): ", topt)
print("optimal delta-Vs (RTN): ", uopt)
print("total cost (magnitude sum): ", np.sum(np.linalg.norm(uopt, axis=0)))
