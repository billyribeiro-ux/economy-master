V16 RESEARCH REHEARSAL: FUNDING SUPPORT AND BORROWER CREDIT

This is an original synthetic instructional release, not a real bank study,
replication of an external paper, original scholarly contribution, or record of
human evaluation. The full research notes, seven tasks, instructor reports,
proposal, short paper and continuation bridge are in the volume assessment.

FIVE-FILE CAPSULE
Keep v16-assessment-inputs.json, v16-assessment-analysis.py,
v16-assessment-output.json, v16-assessment-manifest.json and this README together.
No dependencies, network, credentials, external files or installation beyond a
Python 3 standard-library interpreter are needed. Check the manifest's SHA-256
and byte counts against the other four files before running. The manifest does
not hash itself, authenticate an author, grant release rights or prove science.

RUN
  python3 -B v16-assessment-analysis.py
quietly rewrites the neighboring v16-assessment-output.json.
  python3 -B v16-assessment-analysis.py INPUT.json OUTPUT.json
supports explicit paths. From another working directory, give the script's path.
The script uses its own directory for default inputs/output. Optimized Python
(-O) retains all input and protected-path checks. Successful CLI stdout/stderr
are empty; malformed input/protected output raises an error before writing.
The API run(data) returns strict JSON-compatible data, never prints, never
writes and does not mutate data. No NaN/infinity is emitted. Exact rationals
are serialized as integers when integral, otherwise strings such as "1/4".

PROTECTED INPUTS
The CLI refuses an output that directly, by resolution, by symlink or by an
existing hardlink aliases inputs, code, README or manifest. It checks the
selected input and relevant canonical filenames beside both input and code.
Run alias experiments only in disposable copies and verify every protected
byte afterward. Do not point the output at evidence you intend to preserve.

INPUT CONTRACT AND PROVENANCE
All six bank records and twenty-five ledger records were authored for this
project. No external data or real persons are represented. Each bank's fixed
original borrower cohort has100borrowers; all cohorts are disjoint. Banks
A/B,C/D,E/F form three pairs, with one offered bank per pair. Fair independent
pair lotteries and no cross-cohort interference are maintained assumptions,
not facts established by these invented observations.
Date0 precedes assignment; date1 is90days later. Own and other lender stocks
cover the same fixed cohort and currency. Raw integer amounts are thousands;
analysis amounts are millions, dividing by1000. Equal cohort weighting is the
specified target. Unequal sizes require a new weighting contract and are
rejected here. Own-bank stock is not total borrower credit or new originations.

JOIN, MISSINGNESS, VERSIONS
Registry cohort IDs join to ledger(cohort,date,component,revision). Each chosen
snapshot needs24unique analysis cells. Duplicate exact keys, unmatched cohorts,
null values and absent cells are errors; they are never zero-filled or dropped.
Revision0 supplies all24cells. Revision1 restates CA/date1/other from26000to14000
thousand; it represents a disclosed teaching reporting error. The old row stays
in the raw ledger. Select the maximum revision no greater than snapshot0or1;
never sum versions. The reader reconstructs both snapshots and the correction.
The restatement was known after the first analysis, not a preregistered choice.

OUTPUT MAP
snapshots: full six analysis rows, three component pair contrasts, means, exact
8-assignment sharp-null reference distributions/tail/p for each release.
restatements: each old/new value and its change.
correction_delta: propagation to the own/other/total contrast.
measurement_sensitivity: corrected observed contrast plus hypothetical omitted
component contrast bounds; not a causal confidence interval.
policies: all five subsidy/budget cases, unique constrained lending choices,
component/transport responses, spending and explicit infeasibility diagnostics.
No unaffordable case is silently classified as a valid zero-result policy.

REFERENCE RESULTS
v0 mean(own,other,total)=(12,-6,6); v1=(12,-10,2). The CA restatement lowers
the mean total contrast by4. Both exact sharp-null two-sided p-values are1/4.
The main subsidy4gives choices8,12,16, mean borrower gain2 and spending144:
feasible at budget150, infeasible at100. Subsidy8hits capacities10,14,18,
giving mean borrower gain85/36 and spending336, infeasible at150.
Hypothetical omitted-credit contrast[-3,1] gives observed-plus-omitted range
[-1,3]. Transport displacement5/4gives main-policy mean borrower response-3.

MODEL AND SCIENTIFIC LIMITS
The bank maximizes(a-r)x-h*x*x/2 on[0,K]. Strict concavity for h>0 gives the
projection of(a-r)/h onto that interval, including zero/capacity boundaries.
Subsidy s reduces cost r0to r0-s, with0<=s<=r0; it pays s times all modeled
offered lending. The cost coefficients are toy objective units, not calibrated
annual interest rates. Other credit changes by-lambda*incremental bank credit.
Parameters, substitution and transport are assumed. Negative resulting other
stocks and unaffordable policies receive explicit infeasibility diagnostics.
Budget feasibility is not welfare approval. Exact arithmetic does not validate
mechanisms. Paired-randomization expectation concerns assignment effects under
its assumptions; the sharp-null p-value is not a weak-mean-null test or proof
of zero. Counterfactuals, interference, omitted lenders and real power/design
need separate evidence. No actual registration, access approval or defense
has occurred. The later research portfolio capstone remains distinct.

REAL-DATA CONTINUATION
Obtain actual access/ethics/linkage/release decisions before acquiring records.
Retain permitted raw vintages and an audit trail; minimize identifiers and
review disclosure risks. If raw records cannot be released, give authorized
access instructions and synthetic tests without claiming synthetic outputs
verify confidential estimates. A real original paper needs a documented
literature contribution, defensible new evidence/theory, independent
reproduction where authorized, substantive reports and an observed defense.
