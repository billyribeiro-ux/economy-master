Identification and confounding — exact synthetic benchmark
Chapter v04-c08; authored 2026-10-07 for edition boundary 2026-10-06.

FILES
Save this file, v04-c08-cases.json and v04-c08-identification.py together.
Use an existing Python 3 installation; no third-party package or network is
needed. These cases are original synthetic teaching constructions. No actual
worker, treatment, earnings observation or current market fact is asserted.
The potential outcomes are deliberately supplied to make truth available.
They would generally be missing in an actual observational study.

RUN
  python3 v04-c08-identification.py
Windows with the Python launcher:
  py -3 v04-c08-identification.py
Optional alternate input:
  python3 v04-c08-identification.py my-case.json

The default JSON path is resolved next to the script, not relative to the
current working directory. An explicitly supplied path is resolved as the
user writes it. Inputs are read-only. Results go to standard output as JSON;
invalid inputs produce a diagnostic on standard error and nonzero exit status.
Rational results are exact strings: "-34/5" means -6.8, "4" means exact 4.
No Monte Carlo uncertainty or seed is involved: every small state is enumerated.

CASE CONTRACT AND DATA DICTIONARY
All root fields are required and extra fields are rejected. Duplicate JSON
field names, booleans in integer fields, nonfinite constants and wrong units
are rejected. Integer outcome/coefficient/trait fields lie in [-1000000,
1000000]. These are computational teaching bounds, not economic restrictions.

schema_version: exactly integer 1.
provenance: kind, created, edition_boundary and observations are nonblank text;
  kind must be "original synthetic teaching cases". Date strings are metadata,
  not used to retrieve data or assert a historical empirical vintage.
outcome_unit: exactly "thousand USD over twelve months at a fixed price basis".

training_groups: 1 to 20 rows, total n at most 10000. Each row has:
  x: distinct integer baseline category;
  n: integer group population, 1 to 10000;
  treated: integer assigned count, 0 to n;
  y0, y1: integer potential outcomes, identical within that group.
  There are no missing potential outcomes because this is a teaching model.
  The program expands counts, exposes only x,d,y to standardization and uses
  the separate full population to compute labeled synthetic ATE/ATT/selection.
  Thus no hidden outcome is used to fill a missing observed comparison cell.
  Missing comparisons return value null plus an explanation. An all-treated
  population has no observed raw difference; an all-untreated population
  also has no ATT because its target group is empty.

lottery: treated_count plus workers. There are 2 to 12 workers, with distinct
  nonblank text id and integer y0,y1. treated_count lies between 1 and N-1.
  All combinations of exactly treated_count are equally probable. Potential
  outcomes are fixed. No attrition, noncompliance or interference is modeled.
  At most 924 assignments occur (N=12, treated_count=6).

mediation: u_values is a list of 1 to 20 distinct integers, each equally likely.
  D is an independent fair binary variable. The equations are:
    M = d_to_m * D + U
    Y = intercept + direct * D + m_to_y * M
  M and U are skill-point quantities; d_to_m is skill points per treatment,
  direct and intercept are in the outcome unit and m_to_y is earnings per
  skill point. controlled_m specifies a joint intervention setting M there.
  The report distinguishes the structural direct effect from the observable
  contrast at that m. The latter is null if either treatment state is absent.

collider: independent fair baseline binaries A, B and E; C is the flag
  A+B+E >= threshold, recorded before D=A. Y=intercept+b_to_y*B.
  threshold is integer 1 to 3. Earnings have no dependence on intervening D.
  The table reports all eight states, four cells, the raw difference, zero
  synthetic ATE and an attempted observed-only standardization over C.

equivalent_worlds: 2 to 10 rows, with unique text name, integer y0_intercept,
  y0_u and effect. In each world U is fair binary, D=U, and
    Y(0) = y0_intercept + y0_u*U
    Y(1) = Y(0) + effect.
  The report checks whether all candidate worlds really produce the same
  observed distribution. Modified worlds need not remain equivalent.

BASELINE BENCHMARKS
Training: raw gap -34/5; ATE 4; ATT 26/5; selection -12;
          standardized all 4 and treated 26/5.
Lottery: gaps -17,-6,5,5,16,27; average 5; variance 605/3.
Mediation: total 11; controlled direct 3; observed gap at M=2 is 3.
Collider: raw gap 0; true ATE 0; adjusted contrast -4/3.
Worlds: identical observed pairs (0,20),(1,30), but ATEs 10,0,-10.

MODIFICATION EXPERIMENTS
1. Set training treated counts to 30 and 20. Raw gap becomes 2/5,
   ATT 22/5, selection -4 and ATE 4. Target weights matter.
2. Set the first training group's treated count to its n. Standardization
   over all is unavailable; the script must not exploit supplied y0 to fill
   the missing untreated cell. Synthetic truth remains separately calculable.
3. Change mediation d_to_m=3, direct=2, m_to_y=2, intercept=5,
   controlled_m=3. Total effect is 8 and controlled direct effect 2.
4. Set collider b_to_y=0. Both unadjusted and adjusted effects become zero:
   conditioning on a collider can introduce bias but need not in every
   degenerate parameter case. Set threshold=1 or 3 to expose support failures.
5. Change model C's effect without changing its baseline mechanism. The
   same_observed_distribution flag should become false. Equivalence is a
   property of the complete model, not a label to assign by hand.

LIMITS
These exact calculations check implications of chosen assumptions. They
cannot verify real-world exchangeability, measurement quality, treatment
delivery, external validity or the absence of interference. The examples
do not implement mediation identification in general, full graphical
criteria, causal confidence intervals, longitudinal treatments or a service
for hostile files. This chapter has separate complete exercise solutions.
