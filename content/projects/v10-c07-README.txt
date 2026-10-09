Rill stochastic-calculus workshop — v10-c07

PURPOSE AND SCOPE
This original teaching case supports Brownian motion and Ito calculus. It has
three deliberately separate objects:
1. Sixteen authored rational observations, with exact finite left/right gain
   ledgers and coarser aggregations. They are not sampled market observations.
2. Analytical moment formulas for Brownian Gaussian increments and a finite
   three-point cubature that matches only moments through degree four.
3. Exact geometric Brownian motion (GBM) formulas and analytical Euler errors
   under genuinely Gaussian independent increments.
The chapter supplies the mathematical proofs. No table, finite enumeration,
interpolation or numerical output proves Brownian existence or convergence.
There is no random draw, seed, network request, dependency or market download.

FILES
v10-c07-inputs.json       Original inputs and fixed interpretation contract.
v10-c07-analysis.py       Python 3 standard-library implementation.
v10-c07-output.json       Deterministic reference output.
v10-c07-README.txt        These standalone instructions.
v10-c07-manifest.json    Byte counts and SHA-256 hashes of the four files above.
The manifest cannot include its own hash. The author review separately binds
the manuscript, all five project files, the independent checker and sources.

RUN FROM ANY DIRECTORY
Copy the five files together. The following example assumes the copy is in the
current directory; replace paths with absolute paths if it is elsewhere:

python3 v10-c07-analysis.py --input v10-c07-inputs.json --output /tmp/rill.json
python3 -O v10-c07-analysis.py --input v10-c07-inputs.json --output /tmp/rill-O.json

With --output, successful execution is silent. Without it, strict JSON is
written to stdout. The optional default input is the file beside the script,
not a path relative to the current working directory. The examples above use
explicit paths to make provenance reviewable. An invalid input exits nonzero
with a diagnostic on stderr. The checks do not depend on Python assertions,
which optimization can remove. Never overwrite the supplied inputs with an
output path. Use a fresh destination for variants.

The repository coordinator can run:
python3 scripts/check_v10_c07.py
python3 -O scripts/check_v10_c07.py

The checker independently reconstructs rational finite ledgers, evaluates
Gaussian moments with polynomial integration, checks Brownian analytical
variance/error anchors, reconstructs GBM/Euler moments with recurrences,
checks exercise arithmetic, intervenes on economic/model parameters, rejects
invalid fields and values, verifies hashes, and runs the model in an isolated
temporary directory in both ordinary and optimized Python. It prints one
JSON summary only when run as a script. Import and check() are quiet.

API
Importing the analysis module is quiet. run(data) accepts the decoded input
dictionary, validates it, does not mutate it and returns a JSON-safe result.
Only the Python standard library is needed. Serialize with allow_nan=False.
Input numbers are integers or exact rational/decimal strings. Floats and
booleans are rejected even where Python might treat True as integer 1.
The provided CLI additionally rejects duplicate JSON keys and nonfinite JSON
tokens. Once a caller has already decoded duplicate keys into a dictionary,
run(data) cannot recover that lost information; use load_json(path) or an
equivalent strict decoder for untrusted serialized input.

FIXED CONTRACT
Schema: v10-c07-ito-1. Case: Rill stochastic-calculus workshop.
The provenance and contract dictionaries are fixed semantic fields, not
parameters to relabel as actual observations or a risk-neutral experiment.
Time unit: year. Brownian increment unit: square root of year. Price: CU.
The analytical Brownian and GBM probability statements use the specified P
law; the script neither infers nor constructs a pricing measure.
The path is a finite authored record; its fixed linear interpolation is a
different finite-variation process. Cubature is degree-four moment matching,
not a Gaussian path law. No output is a claim about actual market adequacy.

ACCEPTED INPUT DOMAIN
Unknown or missing fields are rejected at every modeled object level.
Numeric syntax is an integer or a string of at most 60 characters, with no
spaces, plus sign, exponent or leading zeros (except zero itself). A string
may be a signed integer, exact decimal, or signed numerator/positive-integer
denominator fraction. Parsed absolute values and denominators are at most
1,000,000. More specific bounds below also apply.

grid:
- horizon T: 1/16 through 2 years, inclusive.
- increments: a list of 2, 4, 8, 16, 32 or 64 authored increments, each with
  absolute value at most 4. Zero increments are allowed.
- blocks: 1 through 12 distinct positive integer aggregation sizes, each
  dividing the observation count. A block is a number of fine increments,
  not a new time step in years.
- polygon_subdivisions: 1 through 12 distinct integers in [1,64].
- theory_steps: 1 through 12 distinct integers in [1,4096].
- cubature_steps: one integer in [1,7], limiting enumeration to 2187 states.

adapted_integrand:
- first_holding a and feedback b each have absolute value at most 10.
  H=a on the first half of the horizon, H=b*W_(T/2) on the second half.

chain_product:
- x0, x_drift, x_diffusion, y0, y_drift, y_diffusion and decay have absolute
  value at most 10; decay must also be nonnegative. Diffusions can be signed
  because the shared Brownian exposure can be positive or negative.

gbm:
- initial_price: 1/1000 through 1,000,000 CU, strictly positive here because
  the lab reports logarithmic quantities. The chapter treats S0=0 separately.
- drift mu: -1/2 through 1/2 per year.
- diffusion sigma: 0 through 1 per square root of year.
- euler_steps: 1 through 12 distinct integers in [1,4096].
- probe_time: 1/16 through 2 years; this is a separate stress-update length.
- probe_increment: absolute value at most 4; it is a supplied hypothetical
  increment, not a generated quantile or observed frequency.

Bounds limit both runtime and numerical magnitude. They are teaching-domain
choices, not universal financial limits. Zero sigma and negative mu are valid.
The script reports negative Euler values if they occur; it does not clip them
to zero, since that would silently change the numerical scheme.

OUTPUT AND EXACTNESS
All Fraction results serialize as strings such as "23/32", "0" and "2".
Fields ending in _approx are ordinary binary floating values. Floating
exponentials may differ in their last bits across Python/platform math
libraries; meaningful independent comparisons use scaled tolerances, not a
claim of bitwise portability of transcendentals. The committed output and
manifest record the exact bytes produced in this edition. Normal and -O
execution on the same environment must agree.

finite_grids:
For every requested block, sum the original observations in consecutive
groups. List W before/after each group and its left and right gains. The
identities R-L=Q and R+L=W_T^2 hold for every finite path starting at zero.
The Brownian endpoint expression is (W_T^2-T)/2, not the ordinary polygon
integral. L minus that expression equals (T-Q)/2. Aggregating a finite path
need not make Q monotonically closer to T.

polygon_refinements:
Subdividing each original straight segment m times gives squared sum Q/m,
while the ordinary integral of that polygon against itself is W_T^2/2.
Refining a fixed polygon is not refining observations of a Brownian path.

brownian_grid_theory:
For n equal Gaussian intervals of length h=T/n:
 E Q=T; Var Q=2*T^2/n;
 E L=0; Var L=(T^2-T^2/n)/2;
 E R=T; Var R=(T^2+3*T^2/n)/2;
 Var(integral W dW)=T^2/2;
 E[(L-integral W dW)^2]=T^2/(2*n).
These are analytical expectations, not estimates from the authored record.

finite_moment_cubature:
Use independent Z in {-1,0,1} with weights {1/6,2/3,1/6} and increment
sqrt(3*h)*Z. Squares and pairwise products can be represented exactly without
computing a square root. The enumeration matches the Gaussian degree-four
identities, including E W_T^2=T and E W_T^4=3*T^2. It is not a normal law:
the one-step standardized sixth moment is 9, not the Gaussian value 15.
Do not use this finite enumeration to validate tail probabilities or GBM
exponential expectations. n<=7 bounds the state space.

adapted_two_step_integral:
Writing U,V independent N(0,T/2), I=U*(a+b*V). Output gives E I=0, its variance
and fourth moment, alongside the fourth moment of a centered normal having
the same variance. Disagreement is an explicit nonnormal-integral example.

chain_and_product:
For X=x0+a*t+b*W and Y=y0+c*t+d*W, evaluate the discounted-square Ito drift
and diffusion at the authored endpoint, but compute expectations under the
Brownian model. [X,Y]_T=b*d*T. Mixing these endpoint and expectation fields
would confuse a realization with a population moment.

gbm:
The finite-record evaluation uses S0*exp((mu-sigma^2/2)*t+sigma*W_t).
Euler uses E_(i+1)=E_i*(1+mu*h+sigma*dW_i), with exact rational products.
Separate analytical fields use the genuinely Gaussian model:
 log return mean=(mu-sigma^2/2)*T; log variance=sigma^2*T;
 mean S=S0*exp(mu*T); median S=S0*exp((mu-sigma^2/2)*T);
 Var S=S0^2*exp(2*mu*T)*(exp(sigma^2*T)-1).
For n equal steps, the exact and Euler variables share the same Gaussian
increments. Their coupled cross moment is
 S0^2*exp(mu*T)*(1+(mu+sigma^2)*T/n)^n.
Together with exact and Euler second moments this gives the mean-square
terminal error. These moment formulas are evaluated with 80-digit Decimal
exponentials before final float conversion to protect their cancellation.
Mean bias has units CU; strong MSE has units CU^2. Neither is a Monte Carlo
standard error. The positivity probe is separate from the finite record.

BASELINE ANCHORS
Fine record: W_T=1/4, Q=23/32, absolute sum=3, L=-21/64, R=25/64;
symmetric sum=1/32; Brownian endpoint formula=-15/32; discrepancy=9/64.
Four-step cubature: total mass=1, Q variance=1/2, L variance=3/8,
R variance=7/8, L-to-endpoint MSE=1/8.
Adapted integral: variance=17/4, fourth=2217/16; same-variance normal=867/16.
Affine case at t=1,W=1/4: X=51/20, Y=117/40, product drift=24/25,
product diffusion=303/100, E[XY]=351/50, cross variation=3/10.
GBM: log mean=3/200, log variance=9/100, mean price about 84.94692372,
median about 81.20904517, variance about 679.55973362 CU^2.
Euler n=4,16,64: coupled MSE about 8.044270660, 2.002214658, 0.499876899.
Stress update h=1/4,dW=-4: Euler factor=-37/200, price=-74/5;
exact exponential price about 24.18606485 CU.

REVIEW LIMITS
The checker is a numerical/structural author audit, not a formal proof checker
or independent human certification. The chapter explicitly invokes Brownian
existence and usual filtration augmentation. It proves the predictable-L2
density identification and scalar Ito formula for localized continuous
adapted coefficients.
No simulation validates Gaussian market dynamics, continuous trading,
transaction-free funding, a risk-neutral law or actual hedging performance.
Visual/mobile/keyboard/print inspection is an edition-level task and is not
claimed by these script checks.
