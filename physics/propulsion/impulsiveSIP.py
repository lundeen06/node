import numpy as np 
import cvxpy as cp 

class impulsiveSIP():
    """
    Globally Optimal Impulsive Control Algorithm 
    Ref: Koenig and D'Amico "Fast Algorithm for Fuel-Optimal Impulsive Control of Linear Systems with Time-Varying Cost"
    """
    
    def __init__(self, Φ, Γ, x0, xf, t0, tf, nu=3, p=2, N=4, Q=None, ϵcost=1e-3, ϵrmv=1e-3):
        """
        Arguments:
            Φ : State Transiton Matrix (function)
            Γ : Control Matrix (function)
            x0 : Initial state vector
            xf : Final state vector
            t0 : Initial time
            tf : Final time
            nu : Number of control inputs (default: 3)
            p : Norm to use for the cost function (default: 2, i.e., Euclidean norm)
            N : Initial guess of the number of burns (default: 4)
            Q : Cost matrix (default: identity matrix)
            ϵcost : Tolerance for the cost function (default: 1e-6)
            ϵrmv : Tolerance for removing non-critical times (default: 1e-6)
        """
        
        self.Φ = Φ
        self.Γ = Γ
        self.x0 = x0 
        self.xf = xf
        self.t0 = t0
        self.tf = tf
        
        self.nx = np.shape(x0)[0]
        self.nu = nu 
        self.N = N  # initial guess of burn number 

        self.ϵcost = ϵcost
        self.ϵrmv = ϵrmv
        self.p = p
        self.q = 1 if p == np.inf else int(1/(1-1/p)) 
        self.Q = Q if Q is not None else np.eye(self.nx)        
        
        self.w = self.xf - self.Φ(self.tf,self.t0) @ self.x0

    
    def _compute_gU(self, t, λ):
        # Debug prints
      
        t_arr = np.array(t, ndmin=1)
        values = [np.linalg.norm(self.Γ(ti).T @ λ, self.q) for ti in t_arr]
        values = np.array(values)
        if np.isscalar(t):
            return values.item()
        return values
    

    
    def compute_sU(self, λ):
        """
        Suppport function 
        """
        if self.p == 2: 
            return λ / np.linalg.norm(λ, 2)
        elif self.p == 1:
            n = len(λ)
            W = np.concatenate([np.eye(n), -np.eye(n)])
            idx = np.argmax(W.T @ λ)
            return W.T[idx]
        else: 
            raise ValueError("p must be 1 or 2. Others are not implemented yet.")

    def _initialize(self):
        Td = np.linspace(self.t0, self.tf, 2*self.N)
        λest = self.w / np.linalg.norm(self.w)
        gU = [self._compute_gU(t, λest) for t in Td]
        # pair (gU, time), sort descending by gU, and get the top N times
        Test = [t for _, t in sorted(zip(gU, Td), reverse=True)[:self.N+1]]
        return Test
    
    def _refine(self, Test):
        
        iteration = 0
        while True:
            
            # solve optimization for lambda 
            λ = cp.Variable(self.nx)
            obj = cp.Maximize(λ.T @ self.w)
            constraints = [cp.norm(self.Γ(t).T @ λ, self.q) <= 1 for t in Test]
            prob = cp.Problem(obj, constraints)
            prob.solve(solver=cp.MOSEK, verbose=False)
            # if prob.status != cp.OPTIMAL:
            #     raise ValueError("Problem is not optimal")


            λest = λ.value
            
            # remove non-critical times 
            for t in Test.copy():
                if self._compute_gU(t, λest) < 1 - self.ϵrmv:
                    Test.remove(t)
                
            t_grid = np.linspace(self.t0, self.tf, 1000)
            gU      = self._compute_gU(t_grid, λest)
            peaks = [i for i in range(1, len(gU)-1) if gU[i] > gU[i-1] and gU[i] > gU[i+1]]
            gU_localmax = gU[peaks]
            t_localmax  = t_grid[peaks]
            

            
            # add if t seems like a critical time 
            for (i,t) in enumerate(t_localmax):
                if gU_localmax[i] > 1:
                    Test.append(t)

            # terminate condition (dual's optimality)
            if max(gU) < 1 + self.ϵcost: 
                break 
            
            print(f"Iteration {iteration}: max gU = {max(gU)}")
            iteration += 1
            if iteration > 100:
                raise ValueError("Too many iterations. Problem might be infeasible.")
            
        return Test, λest
    
    def _extract(self, Topt, λopt):
        
        uhat = np.zeros((len(Topt),self.nu))
        y = np.zeros((len(Topt), self.nx))
        for (j,tj) in enumerate(Topt):
            sU_tj = self.compute_sU(self.Γ(tj).T @ λopt)
            uhat[j] = sU_tj
            y[j] = self.Γ(tj) @ sU_tj
            
        # solve for coefficients (magnitudes) of thrusts 
        α = cp.Variable(len(Topt)) 
        w_err = cp.Variable(self.nx)
        obj = cp.Minimize(cp.quad_form(w_err, self.Q))
        con = [w_err == self.w - y.T @ α, α >= 0, cp.sum(α) <= λopt.T @ self.w]
        prob = cp.Problem(obj, con)
        prob.solve(solver=cp.MOSEK, verbose=False)
        # if prob.status != cp.OPTIMAL:
        #     raise ValueError("Problem is not optimal")
        αopt = α.value
        
        # generate control histories
        uopt = np.zeros((len(Topt),self.nu))
        for j in range(len(Topt)):
            uopt[j] = αopt[j] * uhat[j]
            
        return uopt 
            
    def solve(self):
        """
        Main function of the impulsive SIP algorithm.
        It initializes the problem, refines the time grid, and extracts the optimal control inputs.
        
        Returns:
            Topt : Optimal times for the burns (n_time,)
            uopt : Optimal control inputs at the burn times (n_time, nu)
            λopt : Optimal dual variable / Lagrange multiplier (n_time, nx)
        """
        
        Test = self._initialize()
        Topt, λopt = self._refine(Test) 
        uopt = self._extract(Topt, λopt) 
        # Topt, uopt = zip(*sorted(zip(Topt, uopt), key=lambda x: x[0]))

        Topt, uopt = np.array(Topt), np.array(uopt)
        idx = np.argsort(np.array(Topt)) 
        return Topt[idx], uopt[idx], λopt


    
    
    