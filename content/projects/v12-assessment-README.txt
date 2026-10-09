HARBOR SKILLS OUTREACH — VOLUME 12 REPLICATION AND EXTENSION
Original fictional fixed population; standard-library Python only.

PURPOSE AND FILES

This project reproduces a synthetic research brief and audits what its estimates
identify. It does not replicate an actual empirical paper. The learner separately
selects and audits a real paper using the manuscript's external-transfer rubric.

Keep these files together:
  v12-assessment-inputs.json    original observed data and separate teaching oracle
  v12-assessment-analysis.py    exact bounded reference implementation
  v12-assessment-output.json   reference output for the supplied settings
  v12-assessment-README.txt    this standalone guide
  v12-assessment-manifest.json byte hashes for the four files above

Python 3 with its standard library is sufficient. No installation, network,
random seed, proprietary software or empirical dataset is required.

From any working directory:
  python3 /absolute/path/v12-assessment-analysis.py
The command is quiet on success and writes v12-assessment-output.json beside
the script. To preserve the distributed reference output, choose a new file:
  python3 /absolute/path/v12-assessment-analysis.py \
    --input /absolute/path/v12-assessment-inputs.json \
    --output /absolute/path/harbor-reproduced.json
The same commands work with python3 -O. No assertion is a validation gate.

API:
  import json, runpy
  from pathlib import Path
  model = Path("/absolute/path/v12-assessment-analysis.py")
  module = runpy.run_path(str(model), run_name="harbor_import")
  data = json.loads(model.with_name("v12-assessment-inputs.json").read_text())
  result = module["run"](data)
  json.dumps(result, allow_nan=False)

Import and run(data) print nothing. The API reads/writes no files, opens no
network connection, mutates neither the input nor module state, and returns
deterministic strict-JSON-compatible data. Fractions are reduced rational strings
such as "11/3"; integers in metadata and record IDs remain integers. A null
estimate has an explicit reason. Infinity and NaN are never output.

INPUT CONTRACT AND DATA DICTIONARY

Top-level keys are exactly schema, project, provenance, design,
observed_columns, observed_rows and teaching_oracle. Schema is integer 1 and
project is "v12-project". The original provenance text is part of the fixed
contract. Unknown keys, malformed records and unsupported designs are rejected.

design contains:
  centres                    6
  workers_per_centre         2
  encouraged_count           3
  actual_encouraged_centres   sorted distinct list of three IDs in 1..6
  alpha                      "1/5" or "1/20"
  direct_effect_delta        exact rational in [-1,1]

The supplied assignment is [1,3,5]. There are exactly twenty equally likely
assignments; each centre has marginal encouragement probability one half.
Both workers share their centre's assignment. Assignment is without replacement,
so even the centre indicators are not independent.

observed_columns fixes the following seven columns, in this order:
  centre  integer 1..6, the assignment unit
  worker  integer 1 or 2 within centre; together these form a unique key
  Z       binary centre encouragement
  D       binary individual course receipt, after Z; not randomly assigned
  B       individual baseline readiness-score points, measured before Z
  Y       follow-up readiness-score points
  W       change Y-B in score points

The twelve rows are ordered by centre then worker. Validation checks their exact
coherence with the declared fixed teaching population and selected assignment,
including binary fields, unique keys, common centre Z and Y=B+W. The analysis
routine then uses only these seven observed columns. It does not use unobserved
types or potential outcomes to compute a coefficient or a sharp-null reference.

teaching_oracle is separate, deliberately disclosed pedagogical information:
  worker_offsets [-1,1]
  centres        six ordered original records with id, g, types, tau, B
  weak_override  centre 2 worker 1 changes C to N; assignment [1,2,4]

For worker r in centre j, v=g_j+e_r, e=(-1,1). Type A receives under either
assignment; type C receives iff encouraged; type N never receives.
Baseline W(d,z)=v+tau*d and Y=B+W. There are no spillovers between workers.
The observed data do not identify a worker's principal type or missing potential
outcome; oracle access is for validation, not evidence inferred from the trial.

The fixed original centre tuples are:
  id   g    types   tau     B
   1  -2    C,C     2,4     40,42
   2   1    C,N     6,1     44,46
   3   3    A,C     3,2     48,50
   4  -1    N,N     8,0     52,54
   5   2    A,N     5,1     56,58
   6   0    C,C     4,6     60,62

Counts, original population and weak transformation are fixed purposefully.
Changing arbitrary baselines, effects, types or population sizes is unsupported,
rather than silently running a purported general causal-inference engine.

SUPPORTED CHANGES

1. Set alpha to "1/20". Both supplied sharp adjusted-outcome inversions become
   the whole real line. All other estimates and teaching-law moments are fixed.
2. Set direct_effect_delta to "-1", "1", "1/2" or another admitted exact value.
   This changes the isolated complier receipt effect to 4-delta but leaves
   every realized assignment observable unchanged.
3. Choose any of the twenty actual assignments. Update all twelve observed
   rows to that newly assigned, separately labelled teaching realization.
   For each worker, use the potential rule above to update Z,D,Y,W; retain B.
   The original actual observations must not be overwritten in a research log.
   A mismatched declared assignment/table is rejected.
4. The output always includes the separate prospective weak world. Its records
   are generated from the stipulated C-to-N change and assignment [1,2,4].
   It is not a post hoc edit to evidence from the baseline trial.

alpha and delta accept Python integers or canonical integer/fraction strings.
Examples accepted: 0, "0", "-1", "1/2". No floats, bools, decimal strings,
whitespace, unreduced fractions, leading-zero spellings or Fraction objects are
accepted. The parsed numerator/denominator must describe a value of magnitude
at most 1000 with reduced denominator at most 1,000,000; delta and alpha then
have their tighter domains above. This is a reduced-denominator limit, not a
decimal-place rule. Rational strings are at most 40 characters. The CLI rejects
input files larger than 65,536 bytes before reading their contents.

JSON duplicate keys and NaN/Infinity constants are rejected by the CLI loader.
The API receives an already-decoded dictionary, where duplicate keys cannot be
represented; all surviving keys and types are still checked. Validation and
protected-output checks finish before the output file is opened. Invalid input
raises ValueError through the API or exits nonzero through the CLI.

INFORMATION FLOW: TWO DIFFERENT ORBITS

Observed-data analysis:
  observed rows -> equal-weight centre means -> assignment contrasts, receipt
  slope, centre ANCOVA, observed variance estimates and sharp-null references.
  ANCOVA regresses centre W on 1, Z and centre B minus its overall mean.

Sharp-null reference:
  freeze the actual observed W (or W-tau*D) and B; vary centre Z over all twenty
  allowed assignments. ANCOVA is refitted for every assignment. Count absolute
  statistics at least as large as the actual one, INCLUDING ties.
  This calculation does not regenerate data under the teaching alternative.

Teaching-oracle distribution:
  hold the potential population fixed and regenerate D and W for every assigned
  set. Compute finite-law truth, expectations, variances and ratio failures.
  These inaccessible-in-an-actual-trial potential records are explicitly labelled
  oracle information. No normal approximation or population sampling is used.

All centre means have equal weight because each centre has exactly two workers.
Observed before/after changes do not by themselves justify parallel trends for
an observational study; here it is the declared randomization that identifies
the finite assignment effect.

OUTPUT AND BENCHMARKS

observed_analysis:
  change ITT                           11/3
  post-only ITT                        -1/3
  baseline group difference            -4
  first stage                          5/6
  sample Wald                          22/5
  descriptive receipt slope            118/35
  ANCOVA (intercept, Z, centred B)      (-5/32,191/48,5/64)
  observed cluster Neyman variance     79/36
  incorrect individual iid variance    68/45
  sharp outcome-null change p          1/5
  sharp outcome-null ANCOVA p          3/10

teaching_oracle:
  encouragement ATE / first stage      2 / (1/2)
  complier receipt ATE under exclusion  4
  E[change ITT] = E[post ITT]           2
  E[Wald]                              133/40, not 4
  E[ANCOVA Z coefficient]              6057/4160, not 2
  true change-ITT variance             37/9
  E[Neyman estimate]                   43/9
  centre-effect sample variance        4
  expected variance gap                2/3
  all baseline first stages            within [1/6,5/6]

The finite variance formula equals the enumerated variance. Conservative in
expectation does not mean every realized variance estimate is an upper bound:
79/36 is less than 37/9. No exact normal interval is implied by either number.
The two sharp-null p-values use separately declared statistics; selecting the
smaller after seeing results would require accounting for the selection rule.

EXACT INVERSION AND ITS LIMIT

H_tau says each worker's W(z)-tau*D(z) is invariant across assignments. Under
baseline exclusion this requires the same effect tau for all receipt-switchers,
not merely an average effect tau. Always/never-takers do not switch receipt.

Let a_S and b_S be change and receipt contrasts calculated from fixed observed
vectors under assignment S. The p-value is the fraction of the twenty values
|a_S-b_S*tau| that are >= the actual |a_0-b_0*tau|.
Reject when p<=alpha and retain p>alpha. Squared comparisons factor into two
linear terms, so their signs change only at finitely many exact rational roots.
Identically tied comparisons remain counted everywhere and supply no roots.
The implementation evaluates every root, every intervening open interval and
both unbounded tails, then merges connected accepted pieces with correct
endpoint closure. It uses neither a numerical grid nor a finite plotting range.

At alpha=1/5:
  baseline inversion              [1,9]
  weak-world inversion            (-infinity,1] union [7,infinity)

Endpoints are included because of the inclusive reference ties and p>alpha
acceptance rule. JSON uses null for an unbounded endpoint and supplies explicit
lower_unbounded, upper_unbounded, lower_closed and upper_closed flags. A null
endpoint is not missing data. Whole R has both endpoints null, both unbounded
flags true and both closure flags false.

Every assignment's complement has the opposite contrast and the same absolute
value. Hence the two-sided p-value is at least 2/20, and at alpha=1/20 the
inversion is all real numbers. The baseline complier effects are heterogeneous,
so no scalar H_tau is true. Containing 4 does not confer generic CACE coverage.
The checker separately validates a population with all complier effects 4:
rejection at the true sharp null has probability 1/5 at alpha=1/5 and zero at
alpha=1/20. That validation population is not another claimed trial result.

EXTENSIONS

Weak world: centre 2 worker 1 loses access and becomes a never-taker. The new
actual assignment is [1,2,4]. True encouragement ATE=3/2, first stage=5/12 and
CACE=18/5. The observed contrast is -8/3, first stage is 0 and Wald is null with
status undefined_zero_first_stage. Three of the twenty assignment ratios are
undefined, so expected_Wald is null with status undefined_on_assignment_support.
No conditional-on-defined average is passed off as an unconditional expectation.

Direct-effect class: for compliers only,
  W_delta(d,z)=v+(tau-delta)*d+delta*z, delta in [-1,1].
Since their D(z)=z, every assignment observable remains v+tau*z. A/N laws are
unchanged. Holding z fixed, the complier receipt effect averages 4-delta,
giving sharp [3,5]. Every point is attained by delta=4-target. The assignment
effects remain 2 and 1/2; their ratio 4 now mixes direct and receipt-mediated
assignment effects. The bound is specific to this declared class.

SCOPE, SOURCES AND EXTERNAL TRANSFER

All original inputs are synthetic. Analysis and exact enumeration establish
properties of this fixed population and law, not actual programme effectiveness,
a representative population ATE or transportability. Random assignment does
not prove exclusion, no interference, truthful receipt measurement or policy
scalability. A randomization p-value is not the probability the null is true.

The manuscript reuses the accepted Imbens-Angrist binary-compliance scope and
Ding finite-randomization scope; ASA interpretation and the dated February 2026
AEA documentation/access policy scope guide the research audit. Prior actual
inspectors and limits are recorded separately. No fresh primary inspection or
institutional endorsement is asserted by these runtime files.

For the mandatory external paper, log the primary body, version, exact claim,
assignment/sampling law, data/code provenance, access and license restrictions.
If lawful compatible inputs are available, reproduce one bounded result and log
commands, hashes and discrepancies. If access is unavailable, record the actual
evidence, mark reproduction not executed, and provide a testable protocol.
Do not fabricate a result or bypass access restrictions. Two feasible extensions
and a referee report are required in either branch. An excellent access audit
is not an executed empirical replication.

PROTECTION AND VERIFICATION

The CLI protects its script, input argument, neighbouring original input, README
and manifest from output writes. Direct, symbolic-link and existing hard-link
aliases are rejected before opening a destination. The distributed output itself
may be deliberately regenerated. Protection is a bounded same-process check,
not a concurrent hostile-filesystem transaction guarantee.

The manifest binds the four payload bytes; it does not prove their mathematics.
Independent editorial checks reconstruct the original law and algebra rather
than treating the model's internal helpers as expected answers. Computation
does not replace separate substantive review or the learner's research defence.

