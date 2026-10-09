VOLUME 10 CHAPTER 10: NUMERICAL PRICING AND MONTE CARLO

All parameters and cases are original synthetic teaching inputs, not observed
prices, investment recommendations or a calibrated market model. Prices are CU
per option, time is in years, rates/yields are continuous annual rates and sigma
is per square-root year. The target European claim is a put on an ex-dividend
GBM stock under Q, dS=(r-q)S dt+sigma S dW. Finite tree exercise values are distinct
targets. The lab implements only the stated bounded domain.

RUN FROM ANY DIRECTORY (Python 3.9+; standard library only)

  python3 v10-c10-analysis.py --input v10-c10-inputs.json --output result.json
  python3 -O v10-c10-analysis.py --input v10-c10-inputs.json --output result-O.json

Use absolute paths when the files are elsewhere. --input and --output are both
required and must refer to different resolved paths. Input is capped at 65536
bytes. Successful execution is quiet and writes one strict JSON object to the
explicit output path. Invalid JSON/domain values produce a nonzero exit and a
useful error on stderr. The program does not create missing output directories.
No network access, installation, current-directory dependency or library data
is used. Duplicate keys and JSON NaN/Infinity/-Infinity tokens are rejected.
The reference output is regenerated only when an intentional change is reviewed.

PORTABLE API

  import runpy
  import json
  module = runpy.run_path('/path/to/v10-c10-analysis.py')
  data = json.loads(open('/path/to/v10-c10-inputs.json').read())
  result = module['run'](data)
  json.dumps(result, allow_nan=False)

Import and run(data) print nothing, do no I/O, do not change the input object,
and do not alter global random state. They have no hidden seed or cached state.
run validates its complete nested domain with explicit exceptions under normal
and optimized Python. Assertions are not used for input validation. Only run is
the validated public computation API; numerical helpers expect validated inputs.

EXACT INPUT SCHEMA

Every object must have exactly the listed keys, with no extra/missing keys.
Numbers must be Python int/float (JSON numbers), finite, and not Boolean. Integer
fields must be actual int, not floats that happen to have integer values.

Root keys: schema_version, market, tree, finite_difference, monte_carlo.
schema_version is integer 1.

market keys and inclusive bounds:
  spot: [20,200]; strike: [20,200]; spot/strike additionally in [0.5,2].
  rate: [-0.05,0.15]; dividend_yield: [0,0.12].
  volatility: [0.1,0.6]; maturity: [0.25,2].
Zero spot, zero volatility and expiry are deliberately outside this numerical
comparison domain; Chapter 8 derives their separate financial cases.

tree keys:
  steps: list of 1 to 6 strictly increasing integer counts in [2,256].
  exercise_stride: integer in [1,32]; it must divide each step count.
For every tree require strictly
  -sigma*sqrt(T/N) < (r-q)*T/N < sigma*sqrt(T/N).
This makes the pricing probability strictly between 0 and 1. No clipping occurs.
Finite dates i=0,stride,2*stride,...,N permit exercise in the Bermudan value.
The all_grid_dates_put permits every node date, including date zero. Strict
exercise counts use intrinsic > continuation; pricing uses max and is unaffected
by how equality is resolved. strict_exercise_nodes counts all pre-maturity nodes,
including nodes that an earlier optimal exercise decision would render unvisited;
it is not an exercise probability, expected count or continuous exercise boundary.

finite_difference keys:
  log_half_width: L in [0.6,2.4]. Require |log(strike/spot)| < L strictly.
  grids: list of 1 to 4 objects with exactly space_steps and time_steps.
  space_steps: even integer M in [8,200].
  time_steps: integer n in [4,10000].
Both counts must increase strictly from grid to grid. Total sum(M*n) <= 2000000.
For h=2L/M, k=T/n, a=sigma^2/2, b=r-q-a require
  a/h^2 - |b|/(2h) >= 0 and 1-2*a*k/h^2 >= 0.
These constraints are evaluated in binary64; a request exactly on a theoretical
boundary may need a modest interior margin to avoid a floating sign discrepancy.
The log grid is centered on spot, and even M puts the reported spot exactly at
the central node. Each grid performs three bounded sweeps: exact-boundary put,
asymptotic-boundary put, and manufactured smooth solution. No unstable grid is
silently repaired. Changing volatility, rates or L requires rechecking stability.

monte_carlo keys:
  seed: integer in [0,4294967295].
  pairs: integer in [32,16384].
  control_beta: finite number in [-2,2], fixed BEFORE evaluation.
  alpha: number in [0.001,0.2], used only for the Hoeffding bound.
The CLT diagnostic is always a 95% interval, using 1.959963984540054.

REPRODUCIBLE STREAM AND INDEPENDENCE UNITS

For each index i=0,...,pairs-1, compute SHA256 of exactly ASCII
  v10-c10:<seed as base-10 integer>:<i as base-10 integer>
with no newline, spaces or zero padding. Interpret digest bytes 0..7 and 8..15
as two big-endian unsigned 64-bit integers. Discard their bottom 11 bits, giving
integers j in [0,2^53-1]. Set U=(j+0.5)/2^53. In binary64 the largest midpoint
can round to 1; cap at math.nextafter(1.0,0.0). All values are strictly positive.
The last 16 digest bytes are unused. Set R=sqrt(-2 log U1), theta=2*pi*U2 and
(Z1,Z2)=(R*cos(theta),R*sin(theta)). A seed is an input, not entropy obtained
from the operating system. Small libm differences may affect last-place digits.

The continuous idealization of independent uniform inputs gives independent
standard normals by the Box-Muller polar-density calculation. This deterministic
finite stream is not proved to have that distribution or independence. Analytical
means, variances and confidence statements below concern the ideal iid law.
Generator/moment diagnostics can detect errors but do not establish statistical
quality. SHA256 is used for transparent reproducibility, not a novel random-number
theorem. This finite-seed experiment is not a randomized coverage study.

All four estimators have 2*pairs payoff evaluations per method; shared calculations
avoid actual redundant work in this demonstration. Plain and fixed-control use
both Z1 and Z2 from each block, so have 2*pairs ideal independent observations.
Antithetic and antithetic_fixed_control use Z1 and -Z1, then average to one unit
per block. Their estimated variances and standard errors use pairs, not 2*pairs.
The estimators share random inputs and are dependent with one another. Their
reported intervals are individual diagnostic intervals, not simultaneous coverage.

The put receipt Y=exp(-rT)*max(K-ST,0) is paired with
X=exp(-rT)*ST, E[X]=S*exp(-qT). Adjustment is Y-beta*(X-E[X]). The coefficient is
not estimated from the evaluation sample. A coefficient suitable for raw Y,X need
not reduce paired variance; the supplied example deliberately illustrates this.

MEANING OF OUTPUT

analytic: dividend-adjusted vanilla call/put formulas, useful benchmark anchors.
tree: up/down factors, probability, European values, every-stride Bermudan put,
  all-grid-date put, strict exercise-node count, parity residual, European error.
  Refining N changes the law and the exercise opportunities simultaneously;
  cross-N monotonicity or a rigorous tree error rate is not asserted.
finite_difference: dx,dt,three weights,finite stock endpoints and central prices.
  w=exp(r*tau)*V is evolved with constant log-coordinate drift/diffusion.
  Exact-boundary values are analytic vanilla prices at both endpoints; this is
  a verification device and is not a generic unknown-claim boundary prescription.
  Asymptotic lower w=max(K-Slow*exp((r-q)*tau),0), upper w=0.
  boundary_effect is asymptotic minus exact central price on the SAME mesh.
  discrete_boundary_effect_bound is exp(-rT) times the largest discrepancy of
  these two boundary arrays over every supplied time node. The discrete maximum
  principle proves it bounds that two-scheme difference in exact arithmetic. It
  does not bound a continuum truncation error, payoff mesh error or total error.
  Tiny discrepancies can round to zero at the center; zero reported difference
  does not establish that the boundary approximation is exact.
  manufactured_max_error uses w=exp(1.3*x+(a*1.3^2+b*1.3)*tau) and exact endpoints.
  manufactured_global_bound is T[(k/2)Mtt + a*h^2*M4/12 + |b|*h^2*M3/6], with
  derivative suprema computed analytically on the full rectangle. This is a
  smooth-solution theorem. The vanilla payoff kink violates its hypotheses.
monte_carlo: stream/seed, first three normal pairs, moment diagnostics, fixed
  coefficient, independent units, sample variances, standard errors and intervals.
  ideal_analytic computes put/stock moments by truncated lognormal integration.
  fixed_control_variance concerns RAW observations, not antithetic pair means.
  Hoeffding widths apply to plain and pair put observations in [0,K*exp(-rT)],
  under ideal independent sampling, with the supplied alpha. They are null for
  control-adjusted variables, which are generally unbounded. CLT95 intervals are
  approximate fixed-sample intervals and are never clipped to payoff bounds.

REFERENCE AND INTERVENTIONS

Main European put: 11.596767760843868 CU. Last CRR European put: 11.589741071281363;
every-fourth-date put: 12.14231680446702; all-grid-date put: 12.152470369297182.
The FD (160,1600) exact-boundary put is 11.592656261694971, not a theorem-certified
four-decimal price. The first option-grid refinement increases absolute error;
the three manufactured-solution errors do decrease within proved bounds.

Useful independent interventions:
1. Change only seed: all trees, PDE grids and analytical anchors stay unchanged.
2. Set control_beta=0: adjusted and unadjusted observations agree exactly.
3. Set control_beta=+1: raw put-control variance increases in this case.
4. Compare stride=1,4,24 with tree.steps=[24] under an unchanged law.
5. Increase q or sigma using grids that remain stable; European put should rise.
6. To expose finite-boundary error, set sigma=.4, L=.8 and just grid (80,800).
   Exact/asymptotic boundary put values are about 18.349509/18.336108; the signed
   effect is -.013401 and its discrete bound about 1.467946. Change L separately
   from h when designing a domain-refinement study.

VALIDATION AND LIMITS

The author checker in scripts/check_v10_c10.py has a quiet check() returning a
JSON-safe summary. It uses independent payoff quadrature, terminal binomial sums,
small-tree exhaustive policy enumeration, a killed-random-walk representation of
the finite-difference stencil, analytical smooth bounds, independent sample
summary reconstruction, financial interventions and malformed-domain tests. It
checks portable normal/-O CLI and API use. Saving expected output is not its sole
oracle. A four-file manifest binds input, model, reference output and this README;
the author review binds those plus manuscript, manifest, checker and source record.

No test establishes empirical calibration, tree/optimal-stopping convergence,
full nonsmooth PDE convergence, continuous-barrier monitoring accuracy, LSM
consistency, novel RNG quality or general SDE weak convergence. No regression
early-exercise algorithm is implemented in this lab; the chapter proves the
finite feasible-policy lower-bound direction and supplies exact toy cases.
Chapter 8 supplies financial limits outside the lab domain. Independent peer and
coordinator review remain separate from the author's numerical and proof checks.
