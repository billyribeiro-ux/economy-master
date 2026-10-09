SABLE QUANTITATIVE MODEL REVIEW — v10-c12

PURPOSE AND PROVENANCE
Original synthetic pricing, calibration, portfolio, outcome and review evidence.
No market observation, real approval authority, credential, network or external
dataset is used. All prices are CU; the curve-family prices are per100CU future
payment. Position signs are explicit. Notional limits are separate CU measures,
not a calculation of market value or risk. The synthetic as-of date is supplied
in the input and is not read from the computer's wall clock.

The lab evaluates six evidence objects and a declared fictional review policy.
Passing its gates means only eligibility under those stated rules. It does not
prove empirical model adequacy, regulatory compliance or real trading permission.
The control rules are not a claim that a deterministic workflow is itself within
the particular regulatory definition of a quantitative financial model.

FILES AND EXECUTION
Keep these five files together:
  v10-c12-inputs.json       complete original inputs and interpretation contracts
  v10-c12-analysis.py       Python3.9+ standard-library implementation
  v10-c12-output.json       complete baseline reference output
  v10-c12-README.txt        this contract and run guide
  v10-c12-manifest.json     byte lengths and SHA256 of the other four files

No installation is necessary. From their folder:
  python3 v10-c12-analysis.py
  python3 v10-c12-analysis.py --input v10-c12-inputs.json --output result.json
  python3 -O v10-c12-analysis.py --input v10-c12-inputs.json --output result-O.json

Use absolute paths when running from another directory. The default input is
the file beside the script, not a file in the current directory. Explicit
relative paths are relative to the calling directory. Without --output, JSON
is printed to stdout. With --output, successful execution is quiet and replaces
that file only after successful validation/computation. Choose a fresh output
name, not an input or code filename. Malformed inputs raise an error and exit
nonzero without replacing an existing output. A financially adverse but valid
case returns a rejection recommendation; it is not a program failure.

Import is quiet; run(data) accepts a decoded dictionary, returns JSON-safe
results and does not mutate input. The CLI rejects duplicate JSON keys and
NaN/Infinity constants. An already decoded dictionary cannot expose keys lost
by an earlier non-strict decoder. Validation uses explicit exceptions and stays
active under Python -O. No seed is needed because there are no random draws.

The source repository also contains scripts/check_v10_c12.py and review records.
The independent checker uses other cash, linear-system, vertex and moment
calculations and verifies portable normal/-O execution. It is not required to
run this five-file package. A digest binds bytes, not mathematical correctness.

NUMERIC AND OBJECT CONTRACT
All modeled objects have exactly the documented keys; extra/missing keys fail.
Financial numbers are strings: optional minus sign, one to nine digits, and
optionally either a decimal point with one to eight fractional digits or a
slash with a positive denominator of one to nine digits beginning1–9. Parsed
values use exact Fraction arithmetic. No whitespace, plus sign, exponent,
JSON numeric value, Boolean, zero denominator or nonfinite token is permitted
in these financial fields. Examples: "0.98", "40", "-1/2". Integer observation
counts/days, Boolean flags and date/identifier strings have separate types.

schema is exactly "v10-c12-sable-1". provenance is the supplied fixed sentence
identifying original synthetic evidence. The top-level keys are schema,
provenance, bond, curve_family, conditioning, book, holdout, decision.

BOND
Keys: cash_flows, benchmark_discounts, candidate_discounts, position,
price_tolerance. Three equal-length lists, each with1–24 entries, align by the
same payment dates. No schedule is inferred from array indices; the chapter's
baseline dates are years1,2,3. Cash flows lie in[-1000000,1000000]CU, discounts
in[1/1000,3], position in[-10000,10000], tolerance in[0,100]CU per bond.
Negative cash obligations and signed holdings are valid. Different discounts
can intentionally represent an input-version failure, not malformed JSON.

The benchmark/candidate values are the respective dated dot products. Price
error is candidate minus benchmark; position_value_error includes signed
quantity. per_cash_flow_error isolates each cf*(candidateD-benchmarkD).
absolute_error_pass uses inclusive tolerance. Baseline values2040,2061,error21,
position error840. These are comparisons against a specified benchmark, not
proof that the benchmark is the correct real-world price.

CURVE FAMILY
Keys: price_at_one, price_at_two, curvature_lower, curvature_upper,
requested_tenor, spread_limit. Prices per100CU payment lie in[90,105] and
[85,110] respectively; c endpoints lie in[-1,1] and must be ordered. Target
tenor is in[0,3] years and spread_limit in[0,100]CU per100CU payment.
P(t)=100+a*t+b*t^2+c*t*(t-1)*(t-2). The two observations determine a,b, leaving
c unidentified. Endpoints determine the requested value range because its
dependence on c is affine. The program orders the endpoint prices even if the
loading on c is negative, and requires a positive lower target price.

Outputs: calibrated linear/quadratic coefficients, two calibration residuals,
unidentified_loading, target_lower/upper/spread and inclusive spread gate.
Baseline a=b=-1, target loading6, range[82,94], spread12 versus limit2. At
tenor2 the range is exactly[94,94]. The c interval is an input assumption, not
a fitted confidence interval. Only named tenors are evaluated; no global
continuous-curve monotonicity, positive-forward-rate or empirical fit is implied.

CONDITIONING
Keys: first_tenor, second_tenor, first_quote, second_quote, target_tenor,
quote_error_bound. Calibration tenors lie in[0,5], ordered with gap at least
1/10000 year. Quotes lie in[0,1000]CU, target in[0,10] years and common absolute
quote bound epsilon in[0,10]CU. Extrapolated affine values need not be positive;
this is a conditioning experiment, not an automatically valid discount curve.

The target weights are 1-w and w for w=(target-t1)/(t2-t1). Report slope,
intercept, prediction, change from increasing ONLY the second quote by epsilon,
and the worst target error over independent bounded quote perturbations.
The latter is (abs(1-w)+abs(w))*epsilon. Baseline prediction97, weights-199/200,
single-quote change2, two-quote bound3.99 and condition factor399. This is an
absolute input-to-output bound, not a probabilistic or relative-error statement.

BOOK
Keys: benchmark_prices, candidate_prices, positions, unit_tolerances,
signed_error_limit, gross_error_limit. Four matched lists have1–24 entries.
Prices lie in[0,1000000]CU, signed positions in[-10000,10000], unit tolerances
in[0,100]CU. Both aggregate limits lie in[0,1000000]CU.

Unit error is candidate minus benchmark. Position contribution is quantity
times error. signed_error sums contributions; gross_comparison_error sums their
absolute values. Unit tests are inclusive. signed_pass compares absolute signed
error with its limit; gross_pass compares gross error with its separate limit.
bound_from_unit_tolerances sums abs(quantity)*unit_tolerance. This is a valid
bound if all those unit bounds simultaneously apply; sample standard errors
do not automatically satisfy that premise. unit_rmse_approx has CU-per-unit
units and intentionally ignores portfolio quantities.
Baseline errors.01,-.02,-.01; contributions2,3,-1; signed4,gross6,bound9;
all unit checks pass while both aggregate gates fail.

HOLDOUT
Keys: training_ids, evaluation_ids, forecast_errors, contract. Each ID list
has1–100 distinct entries, and the two sets must be disjoint. Identifiers use
[a-z][a-z0-9_]{0,39}. Errors require2–100 observations, each in[-1000,1000]CU,
one per evaluation identifier. Consequently evaluation_ids also has at least2
entries in a valid complete input. The supplied interpretation contract is fixed.

This object does not train a model. The user supplies frozen forecast-minus-
comparison errors and split IDs. Disjoint IDs detect direct overlap only; they
cannot establish event independence, honest feature timestamps or absence of
later tuning. Output gives count, exact mean error, MSE and n-1 sample variance,
plus floating RMSE and an IID-conditional estimated standard error sqrt(s^2/n).
The program never asserts that the synthetic errors actually are IID, nor
attaches a coverage guarantee. Baseline mean1/2,MSE3/2,variance10/7,RMSE about
1.224744871 and conditional SE about.422577127. All-zero errors are valid and
produce exact zero moments and zero floating square roots.

DECISION
Keys: as_of, requested_version, reviewed_version, owner, challenger,
data_age_days, max_data_age_days, requested_notional, ordinary_limit, exception.
Version/party labels use the same bounded identifier syntax as observation IDs.
Distinct names illustrate a separation rule; they do not authenticate actual
independence, skill, authority or identity. Equal requested/reviewed labels
illustrate version binding; real artifact binding needs immutable bytes.
Both ages are JSON integers0–365, not booleans or floating values. Notional and
ordinary_limit are financial strings in[0,100000000]CU.

exception has exactly enabled (JSON Boolean), approver (identifier), reason
(nonblank string of1–240 characters), expires (ISO date), notional_limit
(financial string in[0,100000000]CU). Both dates have exactYYYY-MM-DD form and
must be real calendar dates from2000-01-01 through2100-12-31. No timezone or
time-of-day interpretation is inferred. Expiry is inclusive on the as-of date.

The size exception is valid only if enabled, its approver differs from BOTH
owner and challenger, and as_of <= expires. If valid, the effective size limit
is max(ordinary_limit,exception.notional_limit); otherwise it is ordinary_limit.
Thus an exception is an optional size extension, never a reduction of ordinary
permission. An invalid/disabled exception does not itself bar a request already
inside the ordinary limit. Its reason is recorded in the input but not judged
for persuasiveness by the program.

All nine gates must pass for eligible_with_stated_limits:
  numeric_benchmark: the bond absolute comparison passes
  curve_scope: the scenario-family target spread passes
  book_units: every unit comparison passes
  book_signed: aggregate signed comparison passes
  book_gross: aggregate gross comparison passes
  version_binding: requested and reviewed labels match
  independent_challenge: owner and challenger labels differ
  fresh_evidence: data_age_days <= max_data_age_days
  notional_limit: request <= effective size limit
Any failed gate gives reject_requested_use and the complete ordered failed list.
The exception can affect only the last gate. No count or average of passing
checks overrides a failure. These are declared case rules, not agency standards.
Holdout metrics are descriptive evidence for human review; the fictional policy
does not transform them into an automatic empirical-adequacy threshold.

INTERVENTIONS
Baseline failed gates: numeric_benchmark,curve_scope,book_signed,book_gross.
To reproduce the repaired scenario, set candidate bond discounts to benchmark
discounts, curve requested_tenor to"2", and candidate book prices to benchmarks.
The existing date/version/parties and size-only exception then make the request
eligible under the stated case rules. Expire that exception before as_of and
the100000CU request exceeds the50000 ordinary limit. Reducing request to50000
restores size eligibility. A mismatched requested version still fails even with
current prices and a valid size exception. Overlapping training/evaluation IDs
is malformed evidence and is rejected before any output file is replaced.

NUMERICAL AND REVIEW LIMITS
Financial values and moment calculations are exact rational strings. Only fields
ending _approx contain ordinary floating square roots; tolerance is used for
those comparisons. Manifest/reference bytes record this edition, not a promise
of identical transcendental bits on every platform. No statistical confidence,
universal error bound, real approval or independent human certification follows
from a successful run. The chapter's proofs state the assumptions needed for
each bound. Whole-library visual/mobile/keyboard/print review is separate.
