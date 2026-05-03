""" Ancillary file for the RPOD dynamics """

import numpy as np
import numpy.linalg as la

# Earth parameters
J2 = 0.001082635819197
R_E = 6.3781363e+06    # Earth radius [m]
mu_E = 3.986004415e+14 # Earth gravitational parameter [m^3/s^2]

######### ABSOLUTE ORBITAL DYNAMICS #########

def propagate_oe(oe0, dt, mu=mu_E, R=R_E, J2=0):

    dt_arr = np.atleast_1d(dt).astype(float)
    
    a = oe0[0]
    n = np.sqrt(mu/a**3)    
    eta   = np.sqrt(1 - oe0[1]**2)
    kappa = 3/4 * J2*R**2*np.sqrt(mu) / (a**(7/2)*eta**4)
    P     = 3*np.cos(oe0[2])**2 - 1
    Q     = 5*np.cos(oe0[2])**2 - 1
    RAAN_dot = -2*np.cos(oe0[2])*kappa
    aop_dot  = kappa * Q
    M_dot    = n + kappa*eta*P
    
    # tile the constant [a,e,i]
    base = np.tile(oe0[0:3], (dt_arr.size, 1))  # (N,3)

    # integrate each element linearly
    RAANs = oe0[3] + RAAN_dot * dt_arr
    aops  = oe0[4] + aop_dot  * dt_arr
    Ms    = oe0[5] + M_dot    * dt_arr

    new_oe = np.column_stack((base, np.mod(RAANs, 2*np.pi), np.mod(aops, 2*np.pi), np.mod(Ms, 2*np.pi)))  # (N,6)

    # if user passed a scalar, unwrap to (6,)
    if new_oe.shape[0] == 1:
        return new_oe[0]
    return new_oe.T

def mean_to_ecc_anomaly(M, e, tol=1e-6, max_iter=100):
    M = M % (2*np.pi)
    if e < 0.8:
        E = M
    else:
        E = np.pi
    for _ in range(max_iter):
        f = E - e * np.sin(E) - M      
        fdot = 1 - e * np.cos(E)    
        delta_E = -f / fdot         
        E += delta_E             
        if abs(delta_E) < tol:
            break
    else:
        raise RuntimeError("Solution did not converge: M = {}, e = {}".format(M, e))
    return E 

def ecc_to_mean_anomaly(E, e):
    return (E - e * np.sin(E)) % (2 * np.pi)

def true_to_ecc_anomaly(nu, e):
    return 2 * np.arctan(np.sqrt((1-e)/(1+e)) * np.tan(nu/2))

def ecc_to_true_anomaly(E, e):
    return 2 * np.arctan(np.sqrt((1+e)/(1-e)) * np.tan(E/2))

def true_to_mean_anomaly(nu, e):
    E = 2 * np.arctan(np.sqrt((1-e)/(1+e)) * np.tan(nu/2))
    M = E - e * np.sin(E)
    return M % (2 * np.pi)
    
def mean_to_true_anomaly(M, e, tol=1e-8, max_iter=100):
    E = mean_to_ecc_anomaly(M, e, tol, max_iter)
    if (1+e)/(1-e) < 0:
        raise ValueError(f"Eccentricity must be less than 1 for true anomaly calculation. e = {e}")
    return 2 * np.arctan(np.sqrt((1+e)/(1-e)) * np.tan(E/2))


######### RELATIVE ORBITAL ELEMENTS MAPPING #########

def mtx_roe_to_rtn(oe, t=0):
    """
    For eccentric case, see: 
    Willis, M. Ph.D. thesis (Eq. 2.47)
    """
    a = oe[0]
    e = oe[1]
    u = oe[4] + mean_to_true_anomaly(oe[5], oe[1])
    n = np.sqrt(mu_E/a**3)
    cos_u = np.cos(u)
    sin_u = np.sin(u)
    
    map = np.array([
        [1,             0,  -cos_u,       -sin_u,      0,              0   ],
        [-(3/2)*n*t,    1,   2*sin_u,     -2*cos_u,    0,              0   ],
        [0,             0,   0,               0,       sin_u,      -cos_u  ],
        [0,             0,   sin_u*n,    -cos_u*n,     0,               0  ],
        [-(3/2)*n,      0,   2*cos_u*n,   2*sin_u*n,   0,               0  ],
        [0,             0,   0,               0,     cos_u*n,      sin_u*n ]
    ])
    
    if e > 1e-3:       
        eta = np.sqrt(1 - e**2)
        e_x, e_y = e * np.cos(oe[4]), e * np.sin(oe[4])
        k = 1 + e_x * cos_u + e_y * sin_u
        kdot = -e_x * sin_u + e_y * cos_u
        cot_i = 1 / np.tan(oe[2])
        mat1 = np.block([
            [(eta**2)*np.eye(3), np.zeros((3,3))],
            [np.zeros((3,3)), (n/eta)*np.eye(3)]
        ])
        mat2 = np.zeros((6, 6))
        mat2[0, 0] = 1 / k + (3/2) * kdot * n / eta**3 * t
        mat2[0, 1] = -kdot / eta**3
        mat2[0, 2] = (1 / eta**3) * (e_x * ((k - 1)/(1 + eta)) - cos_u)
        mat2[0, 3] = (1 / eta**3) * (e_y * ((k - 1)/(1 + eta)) - sin_u)
        mat2[0, 5] = kdot / eta**3 * cot_i
        mat2[1, 0] = - (3/2) * k * n / eta**3 * t
        mat2[1, 1] = k / eta**3
        mat2[1, 2] =   (1 / eta**2) * ((1 + 1/k) * sin_u + e_y / k + (k / eta) * (e_y / (1 + eta)))
        mat2[1, 3] = - (1 / eta**2) * ((1 + 1/k) * cos_u + e_x / k + (k / eta) * (e_x / (1 + eta)))
        mat2[1, 5] = (1 / k - k / eta**3) * cot_i
        mat2[2, 4] =  1 / k * sin_u
        mat2[2, 5] = -1 / k * cos_u
        mat2[3, 0] = kdot / 2 + (3/2) * k**2 * (1 - k) * n / eta**3 * t
        mat2[3, 1] =  k**2 / eta**3 * (k - 1)
        mat2[3, 2] =  k**2 / eta**3 * (eta * sin_u + e_y * (k - 1) / (1 + eta))
        mat2[3, 3] = -k**2 / eta**3 * (eta * cos_u + e_x * (k - 1) / (1 + eta))
        mat2[3, 5] = -k**2 / eta**3 * (k - 1) * cot_i
        mat2[4, 0] = - (3/2) * k * (1 + k * kdot * n / eta**3 * t)
        mat2[4, 1] = k**2 / eta**3 * kdot
        mat2[4, 2] =   (1 + k**2 / eta**3) * cos_u + e_x * k / eta**2 * (1 + (k / eta) * (1 - k) / (1 + eta))
        mat2[4, 3] =   (1 + k**2 / eta**3) * sin_u + e_y * k / eta**2 * (1 + (k / eta) * (1 - k) / (1 + eta))
        mat2[4, 5] = - (1 + k**2 / eta**3) * kdot * cot_i
        mat2[5, 0] = cos_u + e_x 
        mat2[5, 1] = sin_u + e_y
        map = mat1 @ mat2
    return map

def dpsi_roe(oe, mu=mu_E):


    return None

def mtx_eroe_to_rtn(oe, t=0, mu=mu_E):
    """
    Ref: Guffanti PhD thesis Eq. (A.1), or Delurgio (2024) Eq. 65
    """
    a, e, omega, M0 = oe[0], oe[1], oe[4], oe[5]
    n     = np.sqrt(mu / a**3)                
    M_t   = M0 + n * t                        
    nu    = mean_to_true_anomaly(M_t, e)       
    lam   = omega + nu               
    eta   = np.sqrt(1.0 - e**2) 
    ρ     = 1.0 + e * np.cos(nu)              

    nu_dot = n * ρ**2 / eta**3          
    ρ_dot  = -e * np.sin(nu) * nu_dot  
    sλ, cλ = np.sin(lam), np.cos(lam)
    sν, cν = np.sin(nu),  np.cos(nu)

    Ψ = np.zeros((6, 6))
    Ψ[0, 0] = 1/ρ - 1.5 * e/eta**3 * sν * n * t
    Ψ[0, 2] = -cλ
    Ψ[0, 3] = -sλ

    Ψ[1, 0] = -1.5 * ρ/eta**3 * n * t
    Ψ[1, 1] =  1/ρ
    Ψ[1, 2] =  (1/ρ + 1) * sλ
    Ψ[1, 3] = -(1/ρ + 1) * cλ

    Ψ[2, 4] =  1/ρ * sλ
    Ψ[2, 5] = -1/ρ * cλ

    Ψ[3, 0] = -ρ_dot/ρ**2 - 1.5*e/eta**3*(cν*nu_dot*n*t + sν*n)
    Ψ[3, 2] =  sλ * nu_dot
    Ψ[3, 3] = -cλ * nu_dot

    Ψ[4, 0] = -1.5 * ρ_dot/eta**3 * n * t - 1.5 * ρ/eta**3 * n
    Ψ[4, 1] = -ρ_dot / ρ**2
    Ψ[4, 2] = -ρ_dot/ρ**2 * sλ + (1/ρ + 1) * cλ * nu_dot
    Ψ[4, 3] =  ρ_dot/ρ**2 * cλ + (1/ρ + 1) * sλ * nu_dot

    Ψ[5, 4] = -ρ_dot/ρ**2 * sλ + 1/ρ * cλ * nu_dot
    Ψ[5, 5] =  ρ_dot/ρ**2 * cλ + 1/ρ * sλ * nu_dot

    return Ψ

def dpsi_eroe(oe, t=0.0, mu=mu_E):
     
    a, e, omega, M0 = oe[0], oe[1], oe[4], oe[5]
    n   = np.sqrt(mu / a**3)
    eta = np.sqrt(1 - e**2)

    # anomalies --------------------------------------------------------------
    M  = M0 + n * t
    nu = mean_to_true_anomaly(M, e)
    lam = omega + nu

    sν, cν = np.sin(nu), np.cos(nu)
    sλ, cλ = np.sin(lam), np.cos(lam)

    rho     = 1 + e*cν
    rho_inv = 1.0 / rho

    # first & second derivatives --------------------------------------------
    nu_dot  = n * rho**2 / eta**3
    rho_dot = -e*sν * nu_dot

    nu_dd   = 2*n*rho*rho_dot / eta**3
    rho_dd  = -e*cν*nu_dot**2 - e*sν*nu_dd

    term_rr = rho_dd * rho_inv**2 - 2 * rho_dot**2 * rho_inv**3   # ρ̈/ρ² - 2ρ̇²/ρ³

    dPsi = np.zeros((6, 6))

    # ---------- row 0 -------------------------------------------------------
    dPsi[0,0] = -rho_dot*rho_inv**2 - 1.5*e/eta**3*(n*sν + n*t*cν*nu_dot)
    dPsi[0,2] =  sλ * nu_dot
    dPsi[0,3] = -cλ * nu_dot

    # ---------- row 1 -------------------------------------------------------
    dPsi[1,0] = -1.5*n/eta**3 * (rho + t*rho_dot)
    dPsi[1,1] = -rho_dot * rho_inv**2
    dPsi[1,2] = -(rho_dot*rho_inv**2)*sλ + (rho_inv + 1)*cλ*nu_dot
    dPsi[1,3] =  (rho_dot*rho_inv**2)*cλ + (rho_inv + 1)*sλ*nu_dot

    # ---------- row 2 -------------------------------------------------------
    dPsi[2,4] = -(rho_dot*rho_inv**2)*sλ + rho_inv*cλ*nu_dot
    dPsi[2,5] =  (rho_dot*rho_inv**2)*cλ + rho_inv*sλ*nu_dot

    # ---------- row 3 -------------------------------------------------------
    dPsi[3,0] = -rho_dd * rho_inv**2 + 2*rho_dot**2 * rho_inv**3 \
                -1.5*e/eta**3 * (2*n*cν*nu_dot +
                                 n*t*(-sν*nu_dot**2 + cν*nu_dd))
    dPsi[3,2] =  cλ*nu_dot**2 + sλ*nu_dd
    dPsi[3,3] =  sλ*nu_dot**2 - cλ*nu_dd

    # ---------- row 4 -------------------------------------------------------
    dPsi[4,0] = -1.5*n/eta**3 * (2*rho_dot + t*rho_dd)
    dPsi[4,1] = -term_rr
    dPsi[4,2] = -term_rr*sλ - 2*rho_dot*rho_inv**2*cλ*nu_dot \
                - (rho_inv + 1)*sλ*nu_dot**2 + (rho_inv + 1)*cλ*nu_dd
    dPsi[4,3] =  term_rr*cλ - 2*rho_dot*rho_inv**2*sλ*nu_dot \
                + (rho_inv + 1)*cλ*nu_dot**2 + (rho_inv + 1)*sλ*nu_dd

    # ---------- row 5 (patched) --------------------------------------------
    dPsi[5,4] = -term_rr*sλ - 2*rho_dot*rho_inv**2*cλ*nu_dot \
                - rho_inv*sλ*nu_dot**2 + rho_inv*cλ*nu_dd
    dPsi[5,5] =  term_rr*cλ - 2*rho_dot*rho_inv**2*sλ*nu_dot \
                + rho_inv*cλ*nu_dot**2 + rho_inv*sλ*nu_dd

    return dPsi

def mtx_roe_to_eroe(oe): 
    """
    Guffanti Ph.D. thesis Eq. (A.2) and (5.17) / Delurgio (2024) Eq. 68. 
    Linear mapping from D'Amico QNSROE to EROE / YA-IC. 
    """
    
    e, inc, w = oe[1], oe[2], oe[4] 

    eta = np.sqrt(1.0 - e**2)
    cos_w, sin_w = np.cos(w),  np.sin(w)
    cos_i, sin_i = np.cos(inc), np.sin(inc)
    cot_i = cos_i / max(sin_i, 1e-12) 
    e_x, e_y = e * cos_w, e * sin_w

    kappa = eta**2 - 1.0/eta  

    M = np.zeros((6, 6))
    M[0, 0] = eta**2           

    M[1, 1] = 1.0 / eta 
    M[1, 2] = -kappa * sin_w / e
    M[1, 3] =  kappa * cos_w / e
    M[1, 5] =  kappa * cot_i 

    M[2, 1] =  e_y / eta           
    M[2, 2] =  cos_w**2 + sin_w**2 / eta         
    M[2, 3] =  (1 - 1/eta) * cos_w * sin_w
    M[2, 5] = -e_y * cot_i / eta  

    M[3, 1] = -e_x / eta             
    M[3, 2] =  (1 - 1/eta) * cos_w * sin_w 
    M[3, 3] =  sin_w**2 + cos_w**2 / eta     
    M[3, 5] =  e_x * cot_i / eta 

    M[4, 4] = eta**2   
    M[5, 5] = eta**2   

    return M
    
def roe_to_rtn(roe, oe, t=0.0):
    """
    roe: (6, n_times) array
    oe: (6, n_times) array 
    """
    assert np.shape(roe) == np.shape(oe), "oe and roe must have the same shape"
    rtn = np.zeros_like(roe, dtype=float)
    
    if np.ndim(roe) == 1:
        return mtx_roe_to_rtn(oe, t) @ (roe)
    
    if np.ndim(t) == 0:
        t = np.full(np.shape(roe)[1], float(t))
    
    for i in range(np.shape(roe)[1]):
        rtn[:,i] = mtx_roe_to_rtn(oe[:,i], t[i]) @ (roe[:,i])
    return rtn

def rtn_to_roe(rtn, oe, t=0):   
    """
    rtn: (6, n_times) array
    oe: (6, n_times) array 
    """
    assert np.shape(rtn) == np.shape(oe), "oe and rtn must have the same shape"
    roe = np.zeros_like(rtn, dtype=float)
    
    if rtn.ndim == 1:
        return la.solve(mtx_roe_to_rtn(oe, t), rtn)
    
    if np.ndim(t) == 0:
        t = np.full(np.shape(rtn)[1], float(t))
    
    for i in range(np.shape(rtn)[1]):
        roe[:,i] = la.solve(mtx_roe_to_rtn(oe[:,i], t[i]), rtn[:,i])
    return roe

def eroe_to_rtn(eroe, oe, t=0):
    """
    eroe: (6, n_times) array
    oe: (6, n_times) array 
    """
    assert np.shape(eroe) == np.shape(oe), "oe and eroe must have the same shape"
    rtn = np.zeros_like(eroe, dtype=float)
    
    if eroe.ndim == 1:
        return mtx_eroe_to_rtn(oe, t) @ (eroe)
    
    if np.ndim(t) == 0:
        t = np.full(np.shape(eroe)[1], float(t))
    
    for i in range(np.shape(eroe)[1]):
        rtn[:,i] = mtx_eroe_to_rtn(oe[:,i], t[i]) @ (eroe[:,i])
    return rtn

def rtn_to_eroe(eroe, oe, t=0):
    """
    eroe: (6, n_times) array
    oe: (6, n_times) array 
    """
    assert np.shape(eroe) == np.shape(oe), "oe and eroe must have the same shape"
    rtn = np.zeros_like(eroe, dtype=float)
    
    if eroe.ndim == 1:
        return la.solve(mtx_eroe_to_rtn(oe, t), eroe)
    
    if np.ndim(t) == 0:
        t = np.full(np.shape(eroe)[1], float(t))
    
    for i in range(np.shape(eroe)[1]):
        rtn[:,i] = la.solve(mtx_eroe_to_rtn(oe[:,i], t[i]), eroe[:,i])
    return rtn    
    
def koekoe_to_roe(oec, oed):
    
    def _koekoe_to_roe(oec, oed):     
        roe = np.array([
            (oed[0]-oec[0])/oec[0],
            (oed[4]+oed[5]) - (oec[4]+oec[5]) + (oed[3]-oec[3])* np.cos(oec[2]),    
            oed[1]*np.cos(oec[4]) - oec[1]*np.cos(oec[4]),
            oed[1]*np.sin(oec[4]) - oec[1]*np.sin(oec[4]),
            oed[2] - oec[2],
            (oed[3]-oec[3]) * np.sin(oec[2])
            ]) 
        return roe
    
    if np.ndim(oec) == 1:
        return _koekoe_to_roe(oec, oed)
    
    roe = np.zeros_like(oec, dtype=float)
    for i in range(oec.shape[1]):
        roe[:,i] = _koekoe_to_roe(oec[:,i], oed[:,i])

    return roe    

def koeroe_to_koe(oec, roe):
    
    def _koeroe_to_koe(oec, roe):
        """
        First-order inverse of koekoe_to_roe for quasi-nonsingular ROE.
        oec : chief Keplerian elements [a,e,i,Ω,ω,M]  (rad)
        roe : relative orbital elements ρ = [δa/a, λ, Δe_x, Δe_y, Δi, ΔΩ sin i_c]
        Returns deputy Keplerian elements oed.
        """
        a_c, e_c, i_c, Om_c, w_c, M_c = oec[0], oec[1], oec[2], oec[3], oec[4], oec[5]
        δa, δlam, δex, δey, δix, δiy = roe

        a_d  = a_c * (1.0 + δa)
        i_d  = i_c + δix
        Om_d = Om_c + δiy / (np.sin(i_c) + 1e-12)       # robust near i=0

        ex_c, ey_c = e_c*np.cos(w_c), e_c*np.sin(w_c)
        ex_d       = ex_c + δex
        ey_d       = ey_c + δey
        e_d        = np.hypot(ex_d, ey_d)
        w_d        = np.arctan2(ey_d, ex_d)

        Δω   = (w_d - w_c + np.pi) % (2*np.pi) - np.pi      # wrap to (−π,π]
        ΔOm  = Om_d - Om_c
        ΔM   = δlam - Δω - ΔOm*np.cos(i_c)
        M_d  = M_c + ΔM
        return np.array([a_d, e_d, i_d, Om_d, w_d, M_d])
    
    if np.ndim(oec) == 1:
        return _koeroe_to_koe(oec, roe)
    
    oed = np.zeros_like(oec, dtype=float)
    for i in range(oec.shape[1]):
        oed[:,i] = _koeroe_to_koe(oec[:,i], roe[:,i])
    return oed

def koekoe_to_eroe(oec, oed): 
    """
    Reference: Delurgio and D'Amico, "Closed-form Modeling and Control of Spaceraft Swarms in Eccentric Orbits"
    """
    def _koekoe_to_eroe(oec, oed):
        
        ac, ec, ic, Omc, wc, Mc = oec[0], oec[1], oec[2], oec[3], oec[4], oec[5]
        ad, ed, id, Omd, wd, Md = oed[0], oed[1], oed[2], oed[3], oed[4], oed[5]
        eta = np.sqrt(1 - ec**2)
        eroe = np.array([
            eta**2 * (ad - ac) / ac,
            1/eta * (Md - Mc) + eta**2 * ((wd - wc) + (Omd - Omc) * np.cos(ic)),    
            (ed - ec) * np.cos(wc) + ec/eta * (Md - Mc) * np.sin(wc),
            (ed - ec) * np.sin(wc) - ec/eta * (Md - Mc) * np.cos(wc),
            eta**2 * (id - ic),
            eta**2 * (Omd - Omc) * np.sin(ic)
        ])
        return eroe
    
    if np.ndim(oec) == 1:
        return _koekoe_to_eroe(oec, oed)
    
    eroe = np.zeros_like(oec, dtype=float)
    for i in range(oec.shape[1]):
        eroe[:,i] = _koekoe_to_eroe(oec[:,i], oed[:,i])
    return eroe

def koeeroe_to_koe(oec, eroe): 
    
    def _koeeroe_to_koe(oec, eroe):
        """Approximate inverse of koekoe_to_eroe – first-order consistent."""
        a_c, e_c, i_c, Om_c, w_c, M_c = oec[0], oec[1], oec[2], oec[3], oec[4], oec[5]
        eta = np.sqrt(1 - e_c**2)

        a_d  = a_c * (1.0 + eroe[0]/eta**2)
        i_d  = i_c + eroe[4]/eta**2
        Om_d = Om_c + eroe[5]/(eta**2*np.sin(i_c) + 1e-12)   # avoid division by zero

        # 2. Solve for Δe, ΔM  (eq. 2)
        cosw, sinw = np.cos(w_c), np.sin(w_c)
        if e_c > 1e-12:
            d_e =  eroe[2]*cosw + eroe[3]*sinw
            d_M = (eroe[2]*sinw - eroe[3]*cosw) * eta / e_c
        else:   # near-circular chief
            d_e = 0.0
            d_M = eta * eroe[1]

        e_vec_x = e_c*cosw + d_e*cosw
        e_vec_y = e_c*sinw + d_e*sinw
        e_d     = np.hypot(e_vec_x, e_vec_y)
        w_d     = np.arctan2(e_vec_y, e_vec_x)

        d_w  = w_d - w_c
        d_Om = Om_d - Om_c
        M_d  = M_c + eta*(eroe[1] - eta**2*(d_w + d_Om*np.cos(i_c))) + d_M   # add first-order ΔM

        return np.array([a_d, e_d, i_d, Om_d, w_d, M_d])
    
    if np.ndim(oec) == 1:
        return _koeeroe_to_koe(oec, eroe)
    
    oed = np.zeros_like(oec, dtype=float)
    for i in range(oec.shape[1]):
        oed[:,i] = _koeeroe_to_koe(oec[:,i], eroe[:,i])
    return oed

def pv_to_oe(x, mu=mu_E): 
    
    def _pv_to_oe(x, mu=mu_E):
        rvec = x[0:3]
        vvec = x[3:6]
        hvec = np.cross(rvec, vvec)
        
        r = la.norm(rvec)
        v = la.norm(vvec)
        h = la.norm(hvec)

        ene = 1 / 2 * v**2 - mu / r
        a = -mu / (2 * ene)
        evec = (np.cross(vvec, hvec) - mu * rvec / r) / mu
        e = la.norm(evec)
        i = np.arccos(np.clip(hvec[2] / h, -1.0, 1.0))
        sin_i = np.sin(i)

        # Equatorial (h ∥ ±ẑ): line of nodes is undefined; avoid 0/0 in node vector.
        if sin_i < 1e-10:
            Omega = 0.0
            if e < 1e-12:
                omega = 0.0
                nu = np.arctan2(rvec[1], rvec[0])
            else:
                omega = np.arctan2(evec[1], evec[0])
                nu = np.arctan2(
                    np.dot(np.cross(evec, rvec), hvec) / (h * e),
                    np.dot(evec, rvec) / e,
                )
        else:
            n_cross = np.cross(np.array([0.0, 0.0, 1.0]), hvec)
            nvec = n_cross / la.norm(n_cross)
            Omega = np.arctan2(nvec[1], nvec[0])
            omega = np.arctan2(np.dot(np.cross(nvec, evec), hvec) / h, np.dot(nvec, evec))
            nu = np.arctan2(np.dot(np.cross(evec, rvec), hvec) / (h * e), np.dot(evec, rvec) / e)
        assert e < 1 + 1e-5, 'Eccentricity must be less than 1 for Keplerian elements'
        
        E = 2 * np.arctan(np.sqrt((1-e)/(1+e))*np.tan(nu/2))
        M = E - e*np.sin(E)
        
        return np.array([a, e, i, Omega, omega, M])
    
    if np.ndim(x) == 1:
        return _pv_to_oe(x, mu)
    oe = np.zeros_like(x, dtype=float)
    for i in range(x.shape[1]):
        oe[:,i] = _pv_to_oe(x[:,i], mu)
    return oe

    
def oe_to_pv(oe, mu=mu_E):
    def _oe_to_pv(koe, mu):   
        
        def Rx(x):
            mat = np.array([[1, 0, 0],
                            [0, np.cos(x), np.sin(x)],
                            [0, -np.sin(x), np.cos(x)]])
            return mat

        def Rz(x):
            mat = np.array([[np.cos(x), np.sin(x), 0],
                            [-np.sin(x), np.cos(x), 0],
                            [0, 0, 1]])
            return mat
        
        a, e, i, Omega, omega, M = koe[0], koe[1], koe[2], koe[3], koe[4], koe[5]
        E = mean_to_ecc_anomaly(M, e)
        nu = 2*np.arctan(np.sqrt((1+e)/(1-e))*np.tan(E/2))

        p = a*(1-e**2)
        r = p/(1+e*np.cos(nu))    
        
        # perifocal frame 
        rp = r*np.array([np.cos(nu), np.sin(nu), 0]).reshape((3,1))
        vp = np.sqrt(mu/p)*np.array([-np.sin(nu), e+np.cos(nu), 0]).reshape((3,1))
        
        # rotation matrix from perifocal to ECI
        r_cart = Rz(-Omega).dot(Rx(-i)).dot(Rz(-omega)).dot(rp)
        v_cart = Rz(-Omega).dot(Rx(-i)).dot(Rz(-omega)).dot(vp)
        
        return np.concatenate((r_cart, v_cart), axis=0).flatten() 

    if np.ndim(oe) == 1:
        return _oe_to_pv(oe, mu)
    pv = np.zeros_like(oe, dtype=float)
    for i in range(oe.shape[1]):
        pv[:,i] = _oe_to_pv(oe[:,i], mu)
    return pv

    
######### RELATIVE ORBITAL ELEMENTS DYNAMICS #########

def stm_roe(oe, t, mu=mu_E, R_E=R_E, J2=J2):
    """
        STM of QNS-ROE with J2 perturbation. Also applicable to eccentric orbits 
        Reference : Koenig et al. (2017) "New State Transition Matrices for Spacecraft Relative Motion in Perturbed Orbits; "    
    """
    a, e, i, w = oe.item(0), oe.item(1), oe.item(2), oe.item(4)
    n = np.sqrt(mu/a**3)
    eta = np.sqrt(1-e**2)
    k = 3/4*J2*R_E**2*np.sqrt(mu)/(a**(7/2)*eta**4)
    E = 1+eta
    F = 4+3*eta
    G = 1/eta**2
    P = 3*np.cos(i)**2-1
    Q = 5*np.cos(i)**2-1
    S = np.sin(2*i)
    T = np.sin(i)**2

    w_dot = k*Q
    w_f  = w+w_dot*t
    e_xi = e*np.cos(w)
    e_yi = e*np.sin(w)
    e_xf = e*np.cos(w_f)
    e_yf = e*np.sin(w_f)

    Phi = np.array([
        [1,                      0,   0,                                     0,                                       0,            0],
        [-(7/2*k*E*P + 3/2*n)*t, 1,  k*e_xi*F*G*P*t,                         k*e_yi*F*G*P*t,                         -k*F*S*t,      0],
        [7/2*k*e_yf*Q*t,         0,  np.cos(w_dot*t) - 4*k*e_xi*e_yf*G*Q*t,  -np.sin(w_dot*t) - 4*k*e_yi*e_yf*G*Q*t,  5*k*e_yf*S*t, 0],
        [-7/2*k*e_xf*Q*t,        0,  np.sin(w_dot*t) + 4*k*e_xi*e_xf*G*Q*t,   np.cos(w_dot*t) + 4*k*e_yi*e_xf*G*Q*t, -5*k*e_xf*S*t, 0],
        [0,                      0,  0,                                      0,                                       1,            0],
        [7/2*k*S*t,              0,  -4*k*e_xi*G*S*t,                        -4*k*e_yi*G*S*t,                         2*k*T*t,      1]
    ])
    
    return Phi

def jac_roe(oe, t=0.0, mu=mu_E, R=R_E, J2=J2):   
    """
    Time derivative of the state transition matrix for ROE dynamics stm_ROE(). 
    This is equivalent to the linearized plant matrix for the ROE dynamics,
    Koenig "New State Transition Matrices for Spacecraft Relative Motion in Perturbed Orbits," Eq. 20 and 24
    """
    a, e, i, w = oe[0], oe[1], oe[2], oe[4]
    n = np.sqrt(mu/a**3)
    eta = np.sqrt(1-e**2)
    k = 3/4*J2*R**2*np.sqrt(mu)/(a**(7/2)*eta**4)
    E = 1+eta
    F = 4+3*eta
    G = 1/eta**2
    P = 3*np.cos(i)**2-1
    Q = 5*np.cos(i)**2-1
    S = np.sin(2*i)
    T = np.sin(i)**2
    w_dot = k*Q

    dPhi_dt = np.array([
        [0, 0, 0, 0, 0, 0], 
        [-3.5*E*P*k - 1.5*n  , 0, F*G*P*e*k*np.cos(w), F*G*P*e*k*np.sin(w), -F*S*k, 0], 
        [ 3.5*Q*e*k*np.sin(w), 0, -4*G*Q*e**2*k*np.sin(w)*np.cos(w) - Q*k*np.sin(w_dot*t), -4*G*Q*e**2*k*np.sin(w)**2 - Q*k*np.cos(w_dot*t), 5*S*e*k*np.sin(w), 0], 
        [-3.5*Q*e*k*np.cos(w), 0, 4*G*Q*e**2*k*np.cos(w)**2 + Q*k*np.cos(w_dot*t), 4*G*Q*e**2*k*np.sin(w)*np.cos(w) - Q*k*np.sin(w_dot*t), -5*S*e*k*np.cos(w), 0], 
        [0, 0, 0, 0, 0, 0], 
        [3.5*S*k, 0, -4*G*S*e*k*np.cos(w), -4*G*S*e*k*np.sin(w), 2*T*k, 0]
        ])
    
    return dPhi_dt  

def stm_eroe(oe, t=0, mu=mu_E, R=R_E, J2=J2):
    """
    Ref: Delurguio and D'Amico (2024). Eq. 67  (For Keplerian motion, Eq. 10) 
    This is the STM used for "rotated" Yamanaka-Ankersen IC used in Tommaso's PhD, which has a first-order 
    equivalence to the EROE defined by Delurgio. 
    """
    a, e, inc, w0 = oe[0], oe[1], oe[2], oe[4]
    n = np.sqrt(mu / a**3)           
    eta = np.sqrt(1 - e**2)     
    kappa = 0.75 * J2 * R**2 * np.sqrt(mu) / a**(7/2) / eta**4

    C = 3*np.cos(inc)**2 - 1
    S = 3*np.sin(inc)**2 - 2
    Mbar = eta**3 - eta - 2
    Nbar = 4*eta**2 + 3
    Lbar = eta + 2

    A =  3 * C * e**2 * kappa * np.cos(w0)**2
    B = 1.5 * C * e**2 * kappa * np.sin(2*w0)
    Q =  3 * C * e**2 * kappa * np.sin(w0)**2
    U = -3 * e * kappa * np.sin(2*inc) * np.sin(w0)
    V = -3 * e * kappa * np.sin(2*inc) * np.cos(w0)

    w_dot = kappa * (5*np.cos(inc)**2 - 1) 
    wt    = w0 + w_dot * t
    sin_wt, cos_wt = np.sin(wt), np.cos(wt)
    sin2i  = np.sin(2*inc)

    Φ = np.zeros((6, 6))
    Φ[0, 0] = Φ[1, 1] = Φ[4, 4] = Φ[5, 5] = eta**2

    Φ[1, 0] = -t * (3*n - 7*kappa*Mbar*C) / (2*eta)        
    Φ[1, 2] =  t * kappa * e * np.cos(w0) * Nbar * C        
    Φ[1, 3] =  t * kappa * e * np.sin(w0) * Nbar * C        
    Φ[1, 4] = -t * kappa * sin2i * Nbar                      

    Φ[2, 0] = -t * e * (3*n + 7*kappa* Lbar * S) * sin_wt / (2*eta) 
    Φ[2, 2] =  t * A * np.sin(w_dot*t) + (t*B + eta**2)*np.cos(w_dot*t)    
    Φ[2, 3] =  t * Q * np.cos(w_dot*t) + (t*B - eta**2)*np.sin(w_dot*t)  
    Φ[2, 4] =  t * U * np.cos(w_dot*t) +  t*V*np.sin(w_dot*t)    

    Φ[3, 0] =  t * e * (3*n - 7*kappa* Lbar * C) * cos_wt / (2*eta) 
    Φ[3, 2] = -t * A * np.cos(w_dot*t) + (t*B + eta**2)*np.sin(w_dot*t)  
    Φ[3, 3] =  t * Q * np.sin(w_dot*t) - (t*B - eta**2)*np.cos(w_dot*t)    
    Φ[3, 4] = -t * V * np.cos(w_dot*t) +  t*U*np.sin(w_dot*t)    

    Φ[5, 0] = 3.5 * t * eta**2 * kappa * sin2i              
    Φ[5, 2] = -4  * t * e * eta**2 * kappa * sin2i * np.cos(w0) 
    Φ[5, 3] = -4  * t * e * eta**2 * kappa * sin2i * np.sin(w0) 
    Φ[5, 4] =  2  * t * eta**2 * kappa * np.sin(inc)**2            
    
    Phi = Φ / eta**2
    
    return Phi

def jac_eroe(oe, t=0.0, mu=mu_E, R=R_E, J2=J2):
    """
    Jacobian of the state transition matrix for EROE dynamics.
    """
    a, e, inc, w0 = oe[0], oe[1], oe[2], oe[4]

    n     = np.sqrt(mu / a**3)
    eta   = np.sqrt(1 - e**2)          
    kappa = 0.75 * J2 * R**2 * np.sqrt(mu) / a**(7/2) / eta**4

    C     = 3*np.cos(inc)**2 - 1
    S     = 3*np.sin(inc)**2 - 2
    Mbar  = eta**3 - eta - 2
    Nbar  = 4*eta**2 + 3
    Lbar  = eta + 2
    sin2i = np.sin(2*inc)
    
    A =  3 * C * e**2 * kappa * np.cos(w0)**2
    B = 1.5 * C * e**2 * kappa * np.sin(2*w0)
    Q =  3 * C * e**2 * kappa * np.sin(w0)**2
    U = -3 * e * kappa * np.sin(2*inc) * np.sin(w0)
    V = -3 * e * kappa * np.sin(2*inc) * np.cos(w0)

    w_dot = kappa * (5*np.cos(inc)**2 - 1) 
    wt    = w0 + w_dot * t
    sin_wt, cos_wt = np.sin(wt), np.cos(wt)
    A_sin = np.sin(w_dot*t)
    A_cos = np.cos(w_dot*t)

    dPhi_dt = np.zeros((6, 6))
    dPhi_dt[1, 0] = -(3*n - 7*kappa*Mbar*C) / (2*eta)
    dPhi_dt[1, 2] =  kappa * e * np.cos(w0) * Nbar * C
    dPhi_dt[1, 3] =  kappa * e * np.sin(w0) * Nbar * C
    dPhi_dt[1, 4] = -kappa * sin2i * Nbar

    dPhi_dt[2, 0] = -(e*(3*n + 7*kappa*Lbar*S) / (2*eta) * (sin_wt + t*w_dot*cos_wt)) 
    dPhi_dt[2, 2] = A*A_sin + t*A*w_dot*A_cos + B*A_cos - (t*B + eta**2)*w_dot*A_sin
    dPhi_dt[2, 3] = Q*A_cos - t*Q*w_dot*A_sin + B*A_sin + (t*B - eta**2)*w_dot*A_cos
    dPhi_dt[2, 4] = U*A_cos - t*U*w_dot*A_sin + V*A_sin + t*V*w_dot*A_cos

    dPhi_dt[3, 0] =  (e*(3*n - 7*kappa*Lbar*C) / (2*eta) * (cos_wt - t*w_dot*sin_wt)) 
    dPhi_dt[3, 2] = -A*A_cos + t*A*w_dot*A_sin + B*A_sin + (t*B + eta**2)*w_dot*A_cos 
    dPhi_dt[3, 3] =  Q*A_sin + t*Q*w_dot*A_cos - B*A_cos + (t*B - eta**2)*w_dot*A_sin
    dPhi_dt[3, 4] = -V*A_cos + t*V*w_dot*A_sin + U*A_sin + t*U*w_dot*A_cos

    dPhi_dt[5, 0] = 3.5 *kappa * sin2i * eta**2
    dPhi_dt[5, 2] = -4 *e*kappa * sin2i * np.cos(w0) * eta**2
    dPhi_dt[5, 3] = -4 *e*kappa * sin2i * np.sin(w0) * eta**2
    dPhi_dt[5, 4] =  2 *kappa * np.sin(inc)**2 * eta**2

    return dPhi_dt / eta**2

def stm_HCW(n, t):
    """ Hill–Clohessy–Wiltshire state-transition matrix."""
    ct, st, nt = np.cos(n*t), np.sin(n*t), n*t
    Phi = np.array([
        [4 - 3*ct,    0,    0,     st/n,        2*(1-ct)/n,     0],
        [6*(st-nt),   1,    0,     2*(ct-1)/n,  (4*st-3*nt)/n,  0],
        [0,           0,    ct,    0,           0,              st/n],
        [3*n*st,      0,    0,     ct,          2*st,           0],
        [6*n*(ct-1),  0,    0,    -2*st,        4*ct - 3,       0],
        [0,           0,  -n*st,   0,           0,              ct]
    ])
    return Phi 

def stm_YA(oe, dt, mu=mu_E):
    """
    Yamanaka-Ankersen State Transition Matrix for Elliptic Orbits
    Eq.82 - 84
    Warning: currently not working...? 
    """
    a,e,M0 = oe[0], oe[1], oe[5]
    p = a * (1 - e**2)
    h = np.sqrt(mu * p)
    k2 = h / p**2
    
    E0  = mean_to_ecc_anomaly(M0, e) 
    θ0  = ecc_to_true_anomaly(E0, e) 
    Mt = M0 + np.sqrt(mu/a**3) * dt 
    Et = mean_to_ecc_anomaly(Mt, e)  
    θt = ecc_to_true_anomaly(Et, e)
    
    ρ0, ρt, ρdt = 1 + e*np.cos(θ0), 1 + e*np.cos(θt), 1 + e*np.cos(θt-θ0)  # radius at time t and t+dt
    s0, c0   = ρ0 * np.sin(θ0), ρ0 * np.cos(θ0)
    st, ct   = ρt * np.sin(θt), ρt * np.cos(θt)
    sdt, cdt = ρdt * np.sin(θt-θ0), ρdt * np.cos(θt-θ0)
    
    st_ = np.cos(θt) + e * np.cos(2*θt)
    ct_ = - (np.sin(θt) + e * np.sin(2*θt))
    J = k2 * dt  
    
    # in-plane (x-z), Eq. 82 
    mat1 = 1/(1-e**2) * np.array([
        [1-e**2, 3*e*s0*(1/ρ0 + 1/ρ0**2), -e*s0*(1+1/ρ0), -e*c0+2],
        [0,     -3*s0*(1/ρ0 + e**2/ρ0**2),   s0*(1+1/ρ0),  c0-2*e],
        [0,     -3*(c0/ρ0 + e),          c0*(1+1/ρ0)+e, -s0   ],
        [0,      3*ρ0+e**2-1,           -ρ0**2,         e*s0  ],
    ]) 
    
    # Eq. 83
    mat2 = np.array([
        [1, -ct*(1+1/ρt), st*(1+1/ρt), 3*ρt**2*J       ], 
        [0, st,          ct,         2-3*e*st*J        ], 
        [0, 2*st,        2*ct-e,     3*(1-2*e*st*J)    ], 
        [0, st_,        ct_,       -3*e*(st_*J+st/ρt**2)]
    ]) 
    stm_xz = mat2 @ mat1  
    
    # out-of-plane (y), Eq. 84
    stm_y = 1/ρdt * np.array([[cdt,  sdt], [-sdt, cdt]])  
    
    stm_xyz = np.array([
        [stm_xz[0,0], 0         , stm_xz[0,1], stm_xz[0,2], 0         , stm_xz[0,3]],   
        [0          , stm_y[0,0], 0          , 0          , stm_y[0,1], 0          ],
        [stm_xz[1,0], 0         , stm_xz[1,1], stm_xz[1,2], 0         , stm_xz[1,3]],
        [stm_xz[2,0], 0         , stm_xz[2,1], stm_xz[2,2], 0         , stm_xz[2,3]],
        [0          , stm_y[1,0], 0          , 0          , stm_y[1,1], 0          ],
        [stm_xz[3,0], 0         , stm_xz[3,1], stm_xz[3,2], 0         , stm_xz[3,3]]
    ])
    
    # Eq. 86 
    R = np.block([
        [ρ0 * np.eye(3),                 np.zeros((3, 3))],
        [-e * np.sin(θ0) * np.eye(3),    (1/(k2*ρ0)) * np.eye(3)]
    ])
    # Eq. 87
    L = np.block([
        [(1/ρt) * np.eye(3),             np.zeros((3, 3))],
        [k2 * e * np.sin(θt) * np.eye(3), k2 * ρt * np.eye(3)]
    ])
    stm = L @ stm_xyz @ R

    #lvlh to rtn
    T = np.array([
        [  0,   0,  -1,   0,   0,   0],  # -z
        [  1,   0,   0,   0,   0,   0],  # x
        [  0,  -1,   0,   0,   0,   0],  # -y
        [  0,   0,   0,   0,   0,  -1],  # -vz
        [  0,   0,   0,   1,   0,   0],  # vx
        [  0,   0,   0,   0,  -1,   0],  # -vy
    ])
    return T @ stm @ T.T

def cim_roe(oe, mu=mu_E):
    """control input matrix from DV_RTN to variation in ROE """
    a = oe[0]
    u = oe[4] + mean_to_true_anomaly(oe[5], oe[1])
    n = np.sqrt(mu/a**3)

    B = np.array([
        [0,             2/n,                0],
        [-2/n,          0,                  0],
        [np.sin(u)/n,   2*np.cos(u)/n,      0],
        [-np.cos(u)/n,  2*np.sin(u)/n,      0],
        [0,             0,         np.cos(u)/n],
        [0,             0,         np.sin(u)/n]
    ])
            
    # if oe[1] < 1e-3:
        # B = np.array([
        #     [0,             2/n,                0],
        #     [-2/n,          0,                  0],
        #     [np.sin(u)/n,   2*np.cos(u)/n,      0],
        #     [-np.cos(u)/n,  2*np.sin(u)/n,      0],
        #     [0,             0,         np.cos(u)/n],
        #     [0,             0,         np.sin(u)/n]
        # ])
        
    # else: 
    #     raise ValueError("Eccentricity must be less than 1e-4 for cim_roe calculation. No clean mapping to the eccentric case.")
    #     # Chernick PhD, modified relative mean longitude (by eta) 
    #     e = oe[1]
    #     nu = mean_to_true_anomaly(oe[5], e)
    #     eta = np.sqrt(1 - e**2)
    #     sin_nu = np.sin(nu)
    #     cos_nu = np.cos(nu) 
    #     sin_th = np.sin(oe[4] + nu)
    #     cos_th = np.cos(oe[4] + nu) 
    #     e_x, e_y = e*np.cos(oe[4]), e*np.sin(oe[4])
    #     d = 1 + e*cos_nu
    #     B = np.array([
    #         [ 2/eta*e*sin_nu, 2/eta*d, 0],
    #         [-2*eta**2/d, 0, 0],
    #         [ eta*sin_th, eta*((1+d)*cos_th+e_x)/d,  eta*e_y*sin_th/(np.tan(oe[2])*d)],
    #         [-eta*cos_th, eta*((1+d)*sin_th+e_y)/d, -eta*e_x*sin_th/(np.tan(oe[2])*d)],
    #         [0, 0, eta*cos_th/d],
    #         [0, 0, eta*sin_th/d]
    #     ]) / n
    
    return B

def dcim_roe(oe, mu=mu_E):
    return None

def cim_eroe(oe, mu=mu_E): 
    '''
    Compute the effect of a control input on the ROEs
    This is the same as the B matrix from the Steindorf paper
    '''
    
    a, e, omega, M = oe[0], oe[1], oe[4], oe[5]
    eta   = np.sqrt(1 - e**2)
    nu    = mean_to_true_anomaly(M, e)
    theta = omega + nu
    sin_nu, cos_nu = np.sin(nu), np.cos(nu)
    sin_th, cos_th = np.sin(theta), np.cos(theta)
    k = 1 + e*cos_nu
    n = np.sqrt(mu / a**3)
    e_x = e * np.cos(omega)
    e_y = e * np.sin(omega)

    mat = np.array([
        [2*e*sin_nu,                   2*k,                          0],
        [(k+1)*(k-2)/k,                -e*sin_nu*(1 + k)/k,          0],
        [(k*sin_th - 2*e_y)/k,         ((k+1)*cos_th + e_x)/k,       0],
        [-(k*cos_th - 2*e_x)/k,        ((k+1)*sin_th + e_y)/k,       0],
        [0,                             0,                      eta**2 * cos_th / k],
        [0,                             0,                      eta**2 * sin_th / k]
    ])
    B = eta/n * mat
    return B 

def dcim_eroe(oe, mu=mu_E):    
    """
    Analytic time derivative dB/dt of the 6×3 EROE→RTN input matrix
    for a Keplerian chief (all elements except M advance linearly).
    Parameters
    ----------
    oe : array_like (6,)  [a, e, i, Ω, ω, M0]  (rad where applicable)
    t  : float            Time since epoch [s]
    mu : float            Gravitational parameter [km^3/s^2]
    Returns
    -------
    dB_dt : (6,3) ndarray
    """
    a, e, omega, M0 = oe[0], oe[1], oe[4], oe[5]
    n   = np.sqrt(mu / a**3)
    eta = np.sqrt(1 - e**2)

    # anomalies --------------------------------------------------------------
    nu  = mean_to_true_anomaly(M0, e)
    th  = omega + nu
    sin_nu, cos_nu = np.sin(nu),  np.cos(nu)
    sin_th, cos_th = np.sin(th),  np.cos(th)

    k        = 1 + e * cos_nu
    k_inv    = 1.0 / k
    k_inv2   = k_inv * k_inv
    nu_dot   = n * k*k / eta**3           
    e_x, e_y = e*np.cos(omega), e*np.sin(omega)

    dmat_dt = np.zeros((6, 3))

    dmat_dt[0, 0] =  2*e*cos_nu * nu_dot
    dmat_dt[0, 1] = -2*e*sin_nu * nu_dot

    dmat_dt[1, 0] = (1 + 2*k_inv2)*(-e*sin_nu) * nu_dot
    d_g_dnu = -e*cos_nu*(1 + k_inv) - e**2*sin_nu**2 * k_inv2
    dmat_dt[1, 1] = d_g_dnu * nu_dot

    d_f1_dnu = cos_th - 2*e_y*e*sin_nu * k_inv2         
    dmat_dt[2, 0] = d_f1_dnu * nu_dot
    d_f2_dnu = (-sin_th*(1 + k_inv) + (cos_th + e_x)*e*sin_nu * k_inv2)
    dmat_dt[2, 1] = d_f2_dnu * nu_dot

    d_f3_dnu = sin_th + 2*e_x*e*sin_nu * k_inv2   
    dmat_dt[3, 0] = d_f3_dnu * nu_dot
    d_f4_dnu = (cos_th*(1 + k_inv) + (sin_th + e_y)*e*sin_nu * k_inv2)
    dmat_dt[3, 1] = d_f4_dnu * nu_dot

    d_f5_dnu = eta**2*(-sin_th*k_inv + cos_th*e*sin_nu * k_inv2) 
    dmat_dt[4, 2] = d_f5_dnu * nu_dot

    d_f6_dnu = eta**2*( cos_th*k_inv + sin_th*e*sin_nu * k_inv2)  
    dmat_dt[5, 2] = d_f6_dnu * nu_dot

    return (eta / n) * dmat_dt

def cim_HCW():
    return np.vstack((np.zeros((3, 3)), np.eye(3)))

# nonlinear dynamics 
def gve_koe(oe ,t, F, mu, J2=J2, R=R_E):
    """
    GVE for KOE [a, e, i, Omega, omega, M]
    inputs:
        oe : orbital elements [a, e, i, Omega, omega, M]
        t  : time
        mu : gravitational parameter
        F  : non-two-body forces [F_R, F_T, F_N]
        j2 : boolean for J2 perturbation
    returns:
        d_oe : time derivative of the KOE
    """

    a,e,i,Omega,w,M = oe[0], oe[1], oe[2], oe[3], oe[4], oe[5]
    nu = mean_to_true_anomaly(M, e) 

    if np.isnan(nu):
        print("e = ", e)
        print("nu = ", nu)
        print(" X = ", (1+e)/(1-e))
        raise ValueError('nu is NaN')
    
    h = np.sqrt(mu*a*(1-e**2))
    n = np.sqrt(mu/a**3)
    p = a*(1-e**2)
    r = a*(1-e**2)/(1+e*np.cos(nu))
    L = Omega + w + nu

    if J2 > 0:
        h_ = np.tan(i/2)*np.cos(Omega)
        k_ = np.tan(i/2)*np.sin(Omega)
        kappa1 = (h_ * np.sin(L) - k_ * np.cos(L))
        kappa2 = (h_ * np.cos(L) + k_ * np.sin(L))
        kappa3 = (1 + h_**2 + k_**2)**2
        Delta_J2r = (-3  * mu * J2 * R**2 / (2 * r**4)) * (1 - 12 * kappa1**2 / kappa3)
        Delta_J2t = (-12 * mu * J2 * R**2 / r**4) * (kappa1 * kappa2 / kappa3)
        Delta_J2n = (-6  * mu * J2 * R**2 / r**4) * (1 - h_**2 - k_**2) * kappa1 / kappa3
        F = np.array([F[0] + Delta_J2r, F[1] + Delta_J2t, F[2] + Delta_J2n]).reshape((3,1))      
        
    η     = np.sqrt(1 - e**2)
    coeff = η / (n * a)
    coeff_e = η / (n * a * e)
    coeff_h = h/mu * η / e

    # Zero-initialize A
    A = np.zeros((6, 3))
    A[0, 0] = (2 * a**2 * e * np.sin(nu)) / h
    A[0, 1] = (2 * a**2 * p) / (r * h)
    A[1, 0] = coeff * np.sin(nu)
    A[1, 1] = coeff * ( np.cos(nu) + (e + np.cos(nu)) / (1 + e*np.cos(nu)) )
    A[2, 2] = (r * np.cos(nu + w)) / h
    A[3, 2] = (r * np.sin(nu + w)) / (h * np.sin(i))
    A[4, 0] = coeff_e * (-np.cos(nu))
    A[4, 1] = coeff_e * np.sin(nu) * (1 + r/p)
    A[4, 2] = - (r * np.sin(nu + w) * np.cos(i)) / (h * np.sin(i))
    A[5, 0] =  coeff_h * ( np.cos(nu) - 2*e/(1 - e**2) * r/a )
    A[5, 1] = -coeff_h * (1 + r/(a*(1 - e**2))) * np.sin(nu)

    B = np.array([0, 0, 0, 0, 0, n])   
    return (A.dot(F.flatten()) + B).flatten()


def eom_pv(x, t, mu=mu_E, J2=J2, R_E=R_E):
    
    """
    Equations of motion for relative motion in Keplerian orbits.
    
    Parameters:
        x  : state vector [x, y, z, vx, vy, vz]
        t  : time (not used in this function)
        mu : gravitational parameter (default: mu_E)
        J2 : J2 perturbation coefficient (default: J2)
        R_E: radius of Earth (default: R_E)
    
    Returns:
        dx : time derivative of the state vector
    """
    r_vec = x[:3]
    r = np.linalg.norm(r_vec)

    # J2 perturbation (first-order)
    z2_r2 = (r_vec[2] / r) ** 2                      
    coeff = 1.5 * J2 * mu * R_E**2 / r**5            
    a_J2 = coeff * np.array([
        r_vec[0] * (5.0 * z2_r2 - 1.0),
        r_vec[1] * (5.0 * z2_r2 - 1.0),
        r_vec[2] * (5.0 * z2_r2 - 3.0)
    ])

    acc = -mu / r**3 * x[:3] + a_J2 
    
    return np.concatenate((x[3:], acc))


########## ACTUATION ERRROR ##########


def dv_cov_gates(dv, sigma, lib=np):
    """
    Generate an error covariance corresponding to DV, represented in the LVLH frame.
    Reference: Berning Jr. "CHANCE-CONSTRAINED, DRIFT-SAFE GUIDANCE FOR SPACECRAFT RENDEZVOUS" (2023) (Eq.11)
    
    Parameters:
        dv    : impulsive delta-v (LVLH frame)
        sigma : tuple containing (sigma_s, sigma_p, sigma_r, sigma_a)
        lib   : library to use for calculations (default: numpy)
    
    Returns:
        cov   : error covariance in LVLH space
    """
    sigma_s, sigma_p, sigma_r, sigma_a = sigma
    dv_norm = lib.linalg.norm(dv)
    dv_uvec = dv / dv_norm
    
    # Create a constant vector [0, 0, 1] in the appropriate library format.
    one_vec = lib.array([0, 0, 1])
    
    # Compute orthogonal unit vectors.
    uvec2 = lib.cross(dv_uvec, one_vec)
    uvec2 = uvec2 / lib.linalg.norm(uvec2)
    
    uvec3 = lib.cross(dv_uvec, uvec2)
    uvec3 = uvec3 / lib.linalg.norm(uvec3)
    
    # Construct the error covariance in the "G" space.
    P_G = lib.diag([
        sigma_r**2 + (dv_norm**2) * (sigma_s**2),
        sigma_a**2 + (dv_norm**2) * (sigma_p**2),
        sigma_a**2 + (dv_norm**2) * (sigma_p**2)
    ])
    
    # Construct the rotation matrix (rows are unit vectors) from G space to Cartesian (LVLH) space.
    Rmat = lib.vstack([dv_uvec, uvec2, uvec3])
    cov = Rmat @ P_G @ Rmat.T
    return cov


def dv_cov_simple(dv, actuation_noise_std, lib=np):
    U_j = np.diag(dv @ actuation_noise_std)
    UU_j = U_j @ U_j.T
    return UU_j



########## NAVIGATION ERROR ##########

def rel_nav_artms_roe(range, artms_scale_range_1e5=None, artms_scale_range_1e3=None, lib=np):
    # ARTMS relative nagivation error parameterization. Based on discussion with Justin Kruger 
    
    if artms_scale_range_1e5 is None:
        artms_scale_range_1e5 = np.array([4e-5, 4e-3, 4e-5, 2e-5, 2e-5, 4e-5])  # roe error per meter 
        
    if artms_scale_range_1e3 is None:
        artms_scale_range_1e3 = np.array([1e-4, 4e-3, 2e-3, 2e-3, 2e-3, 2e-3]) 
        
    
    if range > 1e5:
        artms_roe_std = artms_scale_range_1e5*range #[m,m,m,m,m,m]
    elif range < 1e3:
        artms_roe_std = artms_scale_range_1e3*range #[m,m,m,m,m,m]
    else:
        # linear transition
        scale_range_lintra = artms_scale_range_1e3 + (range - 1e3)*(artms_scale_range_1e5 - artms_scale_range_1e3)/(1e5 - 1e3)
        artms_roe_std = scale_range_lintra*range #[m,m,m,m,m,m]

    S_artms_roe = lib.diag(artms_roe_std)  
    Sigma_nav_artms_roe = S_artms_roe @ S_artms_roe.T

    return Sigma_nav_artms_roe
    


def generate_koz(dim_arr, n_time, t_switch=None):
    """
    Generate time-variant DEED matrix and ellipsoid surfaces for plotting.
    
    Parameters:
    -----------
    dim_arr : array_like
        - If 1D (3 elements): Single ellipsoid dimensions [x, y, z]
        - If 2D (N x 3): N ellipsoid dimensions, each row is [x, y, z]
    n_time : int
        Number of time steps
    t_switch : array_like, optional
        Time indices when to switch ellipsoids (length N-1).
        If None or empty, uses single ellipsoid for all time.
    
    Returns:
    --------
    DEED : ndarray, shape (6, 6, n_time)
        Time-variant ellipsoid constraint matrices
    x_ell, y_ell, z_ell : ndarray, shape (N, 100, 100)
        Ellipsoid surfaces for plotting (N ellipsoids)
    """
    
    # Position selection matrix (only position, not velocity)
    D_pos = np.eye(3, 6, dtype=float)
    
    # Handle input dimensions
    dim_arr = np.atleast_2d(dim_arr)
    if dim_arr.shape[1] != 3:
        dim_arr = dim_arr.T  # Transpose if needed
    
    n_ellipsoids = dim_arr.shape[0]
    
    # Handle time switching
    if t_switch is None or len(t_switch) == 0:
        # Single ellipsoid case
        t_switch = [n_time]
    else:
        t_switch = list(t_switch) + [n_time]  # Add final time
    
    # Validate dimensions
    if len(t_switch) != n_ellipsoids:
        raise ValueError(f"Number of switch times ({len(t_switch)}) must match number of ellipsoids ({n_ellipsoids})")
    
    # Pre-compute DEED matrices for each ellipsoid
    DEED_list = []
    for i in range(n_ellipsoids):
        dim = dim_arr[i]
        E = np.diag([1/dim[0], 1/dim[1], 1/dim[2]])
        ED = D_pos * np.diag(E)[:, np.newaxis]
        DEED_i = ED.T @ ED
        DEED_list.append(DEED_i)
    
    # Build time-variant DEED array
    DEED = np.empty((6, 6, n_time), dtype=float)
    t_start = 0
    
    for i, t_end in enumerate(t_switch):
        t_end = min(t_end, n_time)  # Ensure we don't exceed n_time
        if t_start < t_end:
            DEED[:, :, t_start:t_end] = np.tile(
                DEED_list[i][:, :, np.newaxis], 
                (1, 1, t_end - t_start)
            )
        t_start = t_end
    
    # Generate ellipsoid surfaces for plotting
    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    
    x_ell = np.zeros((n_ellipsoids, 100, 100))
    y_ell = np.zeros((n_ellipsoids, 100, 100))
    z_ell = np.zeros((n_ellipsoids, 100, 100))
    
    for i in range(n_ellipsoids):
        dim = dim_arr[i]
        rx, ry, rz = dim[0], dim[1], dim[2]
        
        x_ell[i] = rx * np.outer(np.cos(u), np.sin(v))
        y_ell[i] = ry * np.outer(np.sin(u), np.sin(v))
        z_ell[i] = rz * np.outer(np.ones_like(u), np.cos(v))
        
    r_ell = np.stack([x_ell, y_ell, z_ell], axis=1)

    return DEED, r_ell


