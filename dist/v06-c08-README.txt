V06-C08: FINITE STABILIZATION LAB
Edition boundary: 2026-10-06. Original synthetic teaching cases, prepared 2026-10-08.

FILES AND RUN
Keep v06-c08-analysis.py and v06-c08-inputs.json in one directory.
Run: python3 /path/to/v06-c08-analysis.py
Or:  python3 /path/to/v06-c08-analysis.py /path/to/alternate-inputs.json
Python 3 standard library only; no packages, network, data download or file writes.
The default input path is relative to the script, so the working directory is irrelevant.
Success prints one JSON document to stdout. Invalid inputs print one JSON error to
stderr and exit with code 1. Imports are quiet. Python -O does not remove validation.

MODEL AND TIMING
All shock paths are announced at date 0 and deterministic. Forecasts equal the
next solution on that path. The supplied terminal_x and terminal_pi are boundary
conditions; the program neither estimates nor derives them from shock persistence.

x[t] = x[t+1] - sigma*(j[t] - pi[t+1] - n[t])
pi[t] = beta*pi[t+1] + kappa*x[t] + u[t]
j[t] = max(-2, phi_pi*pi[t] + phi_x*x[t] + v[t])

x is 100*ln(actual output / shock-specific flexible-price output).
pi is total 100*ln(P[t]/P[t-1]), with ZERO target inflation.
The nominal log rate is 2+j; the natural real log rate is 2+n.
The j floor -2 is therefore a zero total nominal rate. Rates and gaps are log
points, not ordinary percentage changes. beta is a supplied forward coefficient
in this reduced model, not a calibration of a common household discount factor.

METHOD AND OUTPUT
Substitution gives a positive scalar denominator at each date. The solver first
computes the unconstrained solution, then recomputes x and pi at the floor if the
requested rate is too low. requested_j reports the request AFTER that recomputation.
strictly_floor_limited is false when the requested rate exactly equals the floor:
the floor binds weakly then and both formulas coincide. Demand, inflation and policy
residuals must all be exactly zero. Fractions are encoded as strings such as "-1/2".
JSON integers and finite decimals are converted with Fraction(str(value)); no
floating tolerance is needed for the solved linear system.

BOUNDS AND VALIDATION
The exact schema rejects missing or extra fields, booleans used as numbers,
nonfinite values, duplicate case names and unequal or empty paths. There are 1-20
cases, each with 1-6 dates; shock and terminal values are in [-20,20]. sigma and
kappa lie in (0,10], beta in [0,1], phi_pi and phi_x in [0,10]. Bounds keep the lab
small and deterministic; they are not empirical confidence intervals or a guarantee
that all resulting gaps lie in a reliable linear-approximation neighborhood.

REFERENCE TARGETS (x,pi,j)
one_date_demand: (-1,-1/2,-1)
one_date_cost: (-1,1/2,1)
deep_demand: (-4,-2,-2), requested j = -4
future_demand: date 0 (-1/2,-1/2,-1); date 1 (-1,-1/2,-1)
future_cost: date 0 (-1/2,0,0); date 1 (-1,1/2,1)
persistent_floor: date 0 (-10,-6,-2); date 1 (-4,-2,-2)
floor_equality: (-2,-1,-2), strictly_floor_limited false
future_tightening: date 0 (-1/2,-1/2,-1); date 1 (-1,-1/2,1)
nonzero_terminal: date 0 (1/4,3/4,3/2); date 1 (1/2,5/4,5/2)

INDEPENDENT AUDIT AND EXTENSION
The repository checker scripts/check_v06_c08.py uses exact Gaussian elimination
on all dates jointly, enumerating possible floor regimes and checking their
inequalities. It also verifies the manuscript's IS-LM, AD-AS, real-investment,
loss and exercise results, schema rejection, portable execution and mutants.
Compare the terminal experiment to baseline before interpreting a simulated path.
This is not an infinite-horizon determinacy test, empirical estimate, full DSGE
microfoundation or welfare appraisal of an actual policy. The static and real
models are checked separately; they are not silently combined into this lab.
