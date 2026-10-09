CEDAR CRITICAL-PAYMENT CONTROLS — VOLUME 11 CHAPTER 06
Original synthetic teaching file, 9 October 2026. Amounts in CU.

PURPOSE
The lab separates a fitted staffing forecast, a gateway-constrained payment
plan, observed settlement evidence, and a stipulated control-risk experiment.
It tests instruction identities and deadlines as well as total cash. It does
not send payments, inspect an actual bank, estimate cyber/fraud effectiveness,
resolve legal rights or close a real incident.

FILES AND EXECUTION
v11-c06-inputs.json: original incident example and declared assumptions.
v11-c06-analysis.py: standalone Python 3 standard-library model.
v11-c06-output.json: saved complete baseline output.
v11-c06-manifest.json: hashes/byte counts for input, model, output and this guide.
v11-c06-README.txt: execution and domain contract.

Copy the model and input together to any directory; no network, package install,
credentials or other chapter is needed. From that directory:
  python3 v11-c06-analysis.py
  python3 -O v11-c06-analysis.py
  python3 v11-c06-analysis.py --input v11-c06-inputs.json --output result.json

The default input is beside the script, regardless of current working directory.
Explicit paths may be absolute. Without --output, one strict JSON document is
printed. With --output, success writes the file and emits no stdout/stderr.
Input/model overwrite is rejected through direct/resolved paths, symbolic links
and existing hard-link aliases. Invalid data cannot replace an existing output.
Validation errors produce a nonzero exit and an error on stderr; checks do not
depend on assert and remain active under -O.

The quiet API is run(data). Load the hyphenated filename with importlib or runpy:
  import json, runpy
  model = runpy.run_path("v11-c06-analysis.py")
  with open("v11-c06-inputs.json", encoding="utf-8") as stream:
      data = json.load(stream)
  result = model["run"](data)

Import/run print and write nothing, and run preserves the supplied data. The
result is a fresh strict-JSON-safe structure. Currency, fitted rates and risk
probabilities use exact Fraction arithmetic and serialize as rational strings;
dates/counts remain integers and gates remain booleans. No floating tolerance
changes an economic inequality. The CLI rejects duplicate keys and nonfinite
JSON constants. API callers must themselves reject duplicate keys when parsing
untrusted JSON, because a parsed dictionary cannot retain them.

The separate author checker scripts/check_v11_c06.py uses independent deadline
allocation, conservation/identity certificates and finite failure-state weights.
Its quiet check() requires all nine author-package paths in the source layout.
It is not needed to run the two-file portable model. Hashes bind byte identity,
not the truth or completeness of the modeled assumptions.

INPUT CONTRACT
Every object has exactly its documented fields. Unknown/missing fields and
wrong types fail. Financial fields are bounded plain decimal or rational strings,
not JSON numbers/booleans. Optional leading minus is allowed by grammar but each
field has its own range. Integer parts and nonzero fraction numerator/denominator
have at most nine digits; decimal fractions have at most eight digits; total
string length is at most32. No exponent, whitespace, plus sign, leading zero
(except the integer0), zero/negative denominator or nonfinite token is accepted.
Examples: "10", "0.05", "1/49". Write zero as "0", not "0/2".
IDs match a letter followed by at most39 ASCII letters, digits, underscores or
hyphens. The CLI input is limited to1,000,000 bytes.

Top level: schema, provenance, run_label, horizon, unit_amount, opening_cash,
opening_payment_liability, opening_equity, payments, training, operation,
observed_settlements, control_risk, closure.

schema is "v11-c06-cedar-1"; provenance must exactly equal the original synthetic
sentence in the supplied input. run_label is an ID identifying this scenario or
retest. A changed test input is a labeled counterfactual or new rehearsal, not
permission to replace a historical incident record.

horizon is an integer1–12. Every release, deadline and observed cutoff is an
integer1–horizon; booleans are excluded. unit_amount is in[0.00000001,1000000].
Every instruction consumes one service slot and has this same amount. There is
one currency, entity and fully usable cash account, with no fees or cash interest.
opening_cash and opening_payment_liability are in[0,999999999]; opening_equity
is in[-999999999,999999999]. The cash-only balance sheet must satisfy C=L+E.
Payment liabilities must equal unit_amount times the authorized instruction
count. Cash must fund every authorized payment and every supplied observed debit;
the supported domain excludes an unmodeled credit line or negative cash. Together
these funding conditions imply nonnegative opening equity in this inventory.

payments is a list of1–200 objects {id,release,deadline}; IDs are unique. Release
must not exceed deadline. All arrivals are available before that window's service;
service completes by its cutoff. There are no within-window payment phases,
preemption, routing eligibility, precedence, multi-slot jobs or additional cash
restrictions. Those require an expanded model, not a changed label on this one.

training is a list of2–20 {staff,throughput} integer pairs. Staff is0–50;
throughput0–500. Sum of squared staffing must be positive. These are synthetic
comparable-window observations made without a binding downstream constraint.
The rate minimizes sum(theta*staff-throughput)^2 through the origin. The model
does not infer stable productivity or causal effects from this small sample.

operation has staff (one integer0–50 per window), gateway_capacity (one integer
0–500 per window) and deployed_rule, either "staff_only" or "bottleneck".
Staff-only capacity is floor(fitted_rate*staff); constrained capacity is its
minimum with the gateway reservation. The lab treats those as deterministic
capacity assumptions, not confidence bounds. The staff_only candidate deliberately
omits the gateway. Both its forecast and the constrained plan are reported.
An actually usable reservation and necessary legal authority must exist before
the relevant cutoff; the model cannot establish that from a number.

observed_settlements has0–400 objects {id,cutoff}, in nondecreasing cutoff order.
IDs can be repeated or absent from the authorized inventory: those are meaningful
observed anomalies, not rejected data. Every row is assumed to represent an actual
cash debit of unit_amount. A first matching ID settled no earlier than its release
discharges its whole liability. A later copy is a duplicate; an unknown ID or a
known ID before release is an exception. A premature row does not prevent a later
first properly authorized settlement from discharging that obligation.

For this accounting case only, exceptions are irreversible bank-borne losses,
with no recovery or customer charge. This is not a universal statement about
payment finality, legal discharge or accounting treatment. Real conclusions need
the actual mandate, destination, amount, external reference, rights and evidence.
The lab has equal amounts and no partial settlements. Authorized settlement after
deadline is late but still discharges the liability. Missing instructions remain
liabilities. Actual records above stated window capacity are reported as a closure
failure requiring reconciliation; they are not silently dropped or declared proof
that the capacity assumption was accurate.

control_risk has requests (integer1–1000000); unauthorized_attempt_probability,
common_failure_probability, first_miss_given_no_common,
second_miss_given_no_common, second_control_coverage (each rational in[0,1]);
and loss_per_escape in[0,1000000]. This is a SEPARATE stipulated request-population
experiment, not a frequency estimate from the observed payment log.

Conditional on an unauthorized attempt, a common event defeats both controls.
Outside that event, the two misses are independent with the supplied conditional
probabilities. Second-control coverage is selected independently of those states;
uncovered requests rely only on the first control. Adaptive or risk-selective
bypass needs a different conditional model. A fixed escaped-attempt loss includes
the assumed irrecoverable severity. No loss-recovery, operational-tail or actual
control-effectiveness estimate is generated. Cross-request independence is not
required for the expected loss, but the expectation supplies no tail law.

closure has IDs preparer, approver, developer, reviewer, reviewed_version and
deployed_version. The respective pairs must differ/match for their gates; equal
names are valid data causing a failed gate. Four boolean declarations are
legal_basis_verified, restore_evidence_verified, replay_evidence_verified and
external_confirmation_verified. maximum_expected_loss is in[0,999999999] and
maximum_fit_error in[0,1000000]. All limits are fictional teaching choices.
Declarations and labels do not authenticate staff independence, legal documents,
test records or a running artifact. In real use, bind reproducible evidence and
the deployed build/configuration, with qualified independent challenge.

QUEUE AND IDENTITY ACCOUNTING
EDF chooses released unfinished instructions by earliest deadline, then release,
then ID. It retains overdue work. Each row reports arrivals, available work,
capacity, completed IDs, unused capacity, backlog and overdue unfinished IDs.
Forecast cash and liabilities both fall by unit_amount per planned completion;
equity does not change merely because a correct payment settles late. All-on-time
feasibility is guaranteed by EDF if it exists under this unit-job domain, by an
exchange argument. The lab makes no claim that its late-job policy maximizes
timely job count in every infeasible instance.

Observed classification is independent of the proposed queue. For M total debits
and U unique properly authorized obligations discharged, cash decreases M*unit,
liabilities decrease U*unit, and equity decreases (M-U)*unit. The resulting
identity is checked. The actual log is not populated from the modeled forecast;
this separation permits the duplicate-substitution counterexample.

BASELINE ANCHORS
Instructions: A01–A04 release1/deadline2; B01–B05 release2/deadline3;
C01–C03 release3/deadline3; D01–D02 release4/deadline4. All are10 CU.
Opening cash/liability/equity200/140/60. Training (1,2),(2,4),(4,8) gives rate2
and zero residuals. Staffing1/1/4/3 forecasts2/2/8/6 slots; the gateway yields
effective2/2/4/6. Stressed backlogs2/5/4/0 and deadline missesB05,C01,C02,C03.
Fourteen finish, ten on time. Reallocating four reserved slots from4 to3 gives
2/2/8/2 and zero deadline misses, conditional on timely usable authorization.

Observed log replaces planned C03 at4 with duplicate B02. Fourteen debits140
discharge thirteen obligations130; C03 remains missing, B05/C01/C02 are late.
Exception loss10; final cash60/liability10/equity50. Matching count/amount totals
alone would conceal both the loss and the remaining obligation.

Risk experiment: c.05, q1.10, q2.20, coverage.80. Marginal misses.145/.24;
joint both-control miss.069; incorrect marginal product.0348; escape conditional
on attempt.0842. With1000 requests, attempt probability.02 and severity25,
expected escapes1.684 and loss42.1. Full coverage gives34.5. With full coverage,
the fictional20 loss ceiling requires c<=1/49. With c=0 it requires coverage>=.75.
These are exact conditional inequalities, not agency policy or estimates.

CLOSURE AND INTERVENTIONS
The baseline disposition is keep_incident_open_or_restrict_use. Its fit, distinct
declared personnel, version labels and record/capacity consistency pass; runtime
bottleneck mapping, constrained deadlines, observed identity/timing, expected
loss ceiling, legal evidence and restore/replay/external evidence do not.
No favorable gate overrides a failed material one.

Test repairs separately: include the gateway (correct forecast, same shortage);
change the timely reservation (new resource plan); reconcile a new correctly
executed rehearsal (not a rewrite of the incident); change common dependency and
coverage with separately declared supporting evidence; then verify independent
authority, artifact and recovery records. Only all gates passing yields
eligible_for_independent_closure_review, not actual closure or legal approval.

Suggested sensitivities: remove a duplicate without supplying the missing ID;
replace it with a late correct ID; try an unknown or premature debit; move service
slots before versus after a due cutoff; test exact c=1/49 or coverage=.75 bounds;
use the one-job release2/deadline2 example with capacity1/0; change only the
deployed version or the reviewer; use a legal confirmation arriving too late as
an explicit counterfactual limitation, never retrospective available capacity.

SOURCE AND REVIEW LIMITS
The new source is the actual final March2021 BCBS operational-resilience PDF,
with its inspected printed3–8 scope. The existing April17,2026 SR26-2 letter and
interagency model-risk guidance are reused within their recorded US scope;
SR11-7 is superseded, and deterministic calculators are not automatically models
under the revised definition. No source prescribes Cedar's invented thresholds.
Sources, proofs, exact problems and independent validation are documented in the
author package. Review remains machine-assisted; real evidence, dependency and
jurisdiction review, human expertise and whole-edition UI checks are separate.
