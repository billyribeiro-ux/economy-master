V14 PROJECT: INSURANCE, FOREIGN FUNDING AND THE PRICE OF A STATE
All inputs are original synthetic teaching quantities and conditional panel counts.
No empirical estimates, real household observations or learner achievement are claimed.

FIVE FILES
Keep v14-assessment-inputs.json, v14-assessment-analysis.py,
v14-assessment-output.json, v14-assessment-manifest.json and this README together.
Python 3 standard library only; no installations, network or textbook dependencies.
From any working directory:
  python3 /path/to/v14-assessment-analysis.py
This quietly regenerates output beside the implementation.
  python3 /path/to/v14-assessment-analysis.py --input /path/to/inputs.json --output /path/to/new-output.json
  python3 -O /path/to/v14-assessment-analysis.py
The quiet run(data) API returns strict JSON-safe data without writing or mutating data.
Rational primitives are strings; counts and iteration controls are genuine integers,
not booleans. Duplicate JSON keys, nonfinite values and unsupported schemas fail.
The CLI protects the actual input, implementation, default input, README and manifest
against direct/resolved/symbolic-link/existing-hard-link output aliases before writes.
Use disposable copies to test refusal and compare every protected byte afterward.

MODEL
State order is ascending asset principal, then low/high income. Receive y+transfer+R*a,
choose next asset from the finite grid and consume the strictly positive remainder.
Fit the income transition rows by conditional count frequencies. Baseline, funded
redistribution, higher contractual R, and a nested asset-grid refinement are solved.
The common initial income marginal must equal the fitted stationary income law.
Transfers to low income are funded by a high-income tax weighted by that law;
this balances every date of the common-initial cross-sectional comparison.
Foreign consumption W-R*A+A_next supplies the explicit counterparty account.
The higher-rate comparison changes inherited payoffs too, not just refinancing.

CERTIFICATES AND LIMITS
Value iteration locates a candidate. Policy values use exact rational linear algebra
and rational atanh-series logarithm centers with an explicit remainder bound.
All feasible alternative-action gaps receive a conservative rational lower bound.
Positive lower bounds prove the finite policy; unresolved ties are not certified.
The reader lists closed communicating classes, periods and invariant laws. Its full
project certificate requires a unique globally convergent law and foreign resources
sufficient in every state, not merely on a reported stationary path.
Economically valid failed cases return not_certified with diagnostics; invalid input
raises ValueError. In particular, foreign_endowment="0" exposes funding shortfalls.
Iteration convergence and policy certification are distinct reported fields.

Conditional beta*c/c_next kernels value tiny consumption transfers with the existing
finite policy locally unchanged. These shadow/marginal values are not equilibrium
prices for a newly introduced security. A finite grid does not imply a continuous
Euler equality at the external safe rate. World interest-rate determination, labor
choice, default and an expanded portfolio-market equilibrium are not modeled.
The refined grid nests actions but does not give a continuous-model error bound.
Common-initial discounted welfare and stationary resource flows are different objects.
Held-out scores compare two prespecified synthetic laws; they do not identify
preferences, borrowing constraints, policy causality or real-world validity.

OUTPUT AND INDEPENDENT WORK
Exact rational accounts and probabilities appear as rational strings. Readable value,
likelihood and gap summaries are finite JSON numbers; rational log-error bounds
underlie the certificate. The manifest hashes the other four downloadable files.
Changing code or inputs requires regenerating output and honestly replacing hashes;
matching hashes establish file identity, not mathematical correctness.
The accompanying instructor project has seven solved tasks and a 100-point rubric.
Its independent checker is an editorial artifact outside this five-file reader.
Submit your own implementation, proofs, actual execution/discrepancy log and oral
changed-primitive defense. The supplied package does not certify that learner work.
