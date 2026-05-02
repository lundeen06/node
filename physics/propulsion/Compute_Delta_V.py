# Function to compute the delta-v for a given trajectory candidate
from Propulsion.util_dyn import * 
from Propulsion.impulsiveSIP import *
from Run_Code import params

def compute_delta_v(roe_0, roe_f, t_0, t_f, chief_oe_0):
    """
    Compute the delta-v for a given trajectory candidate.
    
    Args:
        roe_0 (np.array): Initial relative orbital elements [dimless]
        roe_f (np.array): Final relative orbital elements [dimless]
        t_0 (float): Initial time [s]
        t_f (float): Final time [s]
        chief_oe_0 (np.array): Initial chief orbital elements [km, dimless, rad, rad, rad, rad]
        
    Returns:
        topt (np.array): Optimal times for the burns [n_time, 1]
        uopt (np.array): Optimal delta-vs at the burn times [n_time, 3]
        total_delta_v (float): Total delta-v [1x1]
    """
    
    # === BASE CASE ===
    # Solver cannot handle roe_0 = roe_f
    # Need to return 0 delta-v if roe_0 = roe_f
    if np.allclose(roe_0, roe_f):
        return np.zeros((1,4)), np.zeros((3,4)), 0
 

    # === Initial conditions ===
    # Convert to meters:
    chief_oe_0[0] = chief_oe_0[0]*1e3

    # === Get Initial and Final QNS ROEs ===
    # Convert to meters:
    roe_0 = roe_0*params.a_chief*1e3
    roe_f = roe_f*params.a_chief*1e3

    # === Use ROE-based propagation with QNS ROEs ===
    # Define lambda-functions - STMs as a function of time
    B = lambda t: cim_roe(propagate_oe(chief_oe_0, t - t_0, params.MU*1e9, params.J2), params.MU*1e9)
    Φ = lambda t2, t1: stm_roe(propagate_oe(chief_oe_0, t1 - t_0, params.MU*1e9, params.J2), t2 - t1, params.MU*1e9, params.EARTH_RADIUS*1e3, params.J2)
    Γ = lambda t: Φ(t_f, t) @ B(t)

    nx = roe_0.size
    assert Φ(t_f, t_0).shape == (nx, nx),    f"Φ shape is {Φ(t_f, t_0).shape}, expected {(nx,nx)}"
    assert B(t_0).shape == (nx, 3),          f"B shape is {B(t_0).shape}, expected {(nx,3)}"
    assert Γ(t_0).shape == (nx, 3),          f"Γ shape is {Γ(t_0).shape}, expected {(nx,3)}"


    # === Run SIP ===
    SIP = impulsiveSIP(Φ, Γ, roe_0, roe_f, t_0, t_f)
    
    try:
        topt, uopt, λopt = SIP.solve()
        
        # === Filter and print ===
        epsilon = 1e-3
        mask = np.linalg.norm(uopt, axis=1) > epsilon
        topt = topt[mask]
        uopt = uopt[mask].T
            
        # === Compute and Return Delta-V Metrics ===
        total_delta_v = np.sum(np.linalg.norm(uopt, axis=0))
        return topt, uopt, total_delta_v
        
    except (ValueError, RuntimeError) as e:
        # If optimization becomes infeasible or fails, return a large default cost
        print(f"Warning: Delta-V optimization failed for trajectory. Error: {e}")
        print("Returning default high cost of 1000 m/s")
        # Return empty arrays and large cost
        return np.array([]), np.array([]), 1000
    
    
    
    