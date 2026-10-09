V11-C10 — Financial regulation and incentives
Original Rowan cases; portable standard-library Python, schema 1

PURPOSE AND STATUS
This lab implements three related but financially separate teaching experiments:
(1) a finite portfolio choice with a funded guarantee, external harm and policy
perimeters; (2) a conduct incentive with collectible sanctions; (3) a deterministic
resolution loss and dated cash ledger. Do not merge their balance sheets. All
CU units, probabilities, screens, priorities, thresholds and rights are synthetic.
They are not observed data, current national rules or a legal opinion. The
historical UK statute and dated FSB standard in the chapter provide institutional
context, not the numerical law of these experiments.

FILES AND EXECUTION
Keep these five files in one folder:
  v11-c10-inputs.json       Original case inputs
  v11-c10-analysis.py       Pure run(data) API and command line
  v11-c10-output.json       Saved exact baseline result
  v11-c10-README.txt        This guide
  v11-c10-manifest.json     SHA-256 and byte bindings for the four files above

No installation, network, external service or nonstandard package is required.
Use a Python 3 interpreter with standard-library fractions and pathlib:
  python3 v11-c10-analysis.py
  python3 -O v11-c10-analysis.py
  python3 v11-c10-analysis.py --input v11-c10-inputs.json --output result.json

Default input and output are next to the implementation, independent of working
directory. Without --output, success quietly writes v11-c10-output.json; an explicit
--output selects another destination. Every successful run writes one UTF-8 JSON
object without stdout output. Importing the file is quiet; run(data) neither prints
nor mutates its argument, and returns only JSON-safe values. Numeric results are
canonical exact-rational strings: 75/4 means 18.75 CU, not a string approximation.
There is no random simulation. Output file writes are not claimed to be atomic
against concurrent filesystem replacement; use an ordinary private working folder.

An output path cannot alias the input or implementation by direct path, resolved
path, symbolic link or existing hard link. Invalid input is rejected before an
existing output is overwritten. A malformed input or unsupported economic family
raises ValueError in the API; the CLI exits nonzero with an error on stderr. Guards
use explicit conditions, not assert, so optimization does not disable them.

INPUT CONTRACT
The root has exactly schema, provenance, portfolio, conduct and resolution.
schema is the integer 1 (not a boolean). provenance is a nonempty string of at
most 1,000 characters. Unexpected/missing fields are rejected at every object.

Every economic number must be a string in integer, finite decimal or rational
form, such as "0", "0.25" or "1/4". Scientific notation, surrounding spaces,
nonfinite values, floats, booleans and null are rejected. Each string is at most
40 characters; its reduced numerator magnitude is at most 10^12 and denominator
at most 10^6. A slash denominator must be a positive integer. Unless a narrower
range below applies, numbers must lie in [0,1,000,000]. No approximate probability
normalization is performed. IDs use an ASCII letter followed by at most 31 ASCII
letters, digits, underscores or hyphens. Duplicate IDs within a list are rejected.
The CLI additionally rejects duplicate JSON keys, NaN/Infinity and files larger
than 262,144 bytes. The input contract is intentionally finite and bounded.

PORTFOLIO MODULE
Exact fields:
  initial_assets, capital, insurer_reserve, harm_if_default, probabilities,
  options, policies, capture_weight.
initial_assets lies in [1,1,000,000]; capital in [0,initial_assets]. Deposits are
initial_assets-capital, so varying capital replaces deposit funding rather than
adding assets. capture_weight is in [0,10]. probabilities has 2–6 entries in [0,1]
and sums exactly to one. These are physical scenario probabilities, not pricing
weights. Zero-probability states are allowed but must still satisfy the stated
resource domain. insurer_reserve must cover the largest deposit shortfall in
EVERY listed state/option, including a zero-probability state. This is the declared
support of the fully funded guarantee, not a probabilistic chance constraint.

options has 1–6 objects with exactly id, assets, reported_exposure and
lookthrough_exposure. assets has one nonnegative payoff per state. All exposures
are nonnegative measurements stipulated by the input, not a risk-weighting
formula. Routing costs, if any, must already be included in asset payoffs.

policies has 1–6 objects with exactly id, basis, ratio and resource_cost. basis is
reported or lookthrough; ratio lies in [0,1]. Feasibility is the weak inequality
capital >= ratio*the selected exposure. A zero ratio represents no capital
screen. Policy resource cost comes from a separately endowed outside budget and
does not enter bank capital or private profit. The experiment assumes this real
resource cost is financeable and includes no public-funding distortion.

State accounting:
  bank deposit payment = min(assets,deposits)
  guarantor payment = max(deposits-assets,0)
  owner residual = max(assets-deposits,0)
  real harm = harm_if_default if assets < deposits, otherwise zero.
The guarantor begins with its explicit reserve, receives no premium and can pay
the full shortfall in every supported state. Guaranteed depositors break even at
zero interest. Insurer reserve wealth changes by minus the payout. Owners invest
capital, so their expected profit subtracts that initial amount.

Welfare_before_policy_cost = expected_assets-initial_assets-expected_real_harm.
It equals owner_profit-expected_insurance-expected_real_harm. Guarantee payments
are transfers, not an extra subtraction from asset-based welfare. Policy welfare
subtracts resource_cost. score = welfare+capture_weight*private_profit is a
stylized extra incumbent weight, not evidence of actual regulatory capture.

Each policy reports its required capital, feasible choices and ALL private best
responses. An empty feasible menu is a reported policy failure, not a malformed
input. The model does not invent an exit or safe portfolio. A policy with several
best responses reports every associated welfare and score. score_maximizers is
null if any feasible policy's tied choices give different scores; ranking_status
then says tie-dependent. Otherwise all score-maximizing feasible policies are
returned, preserving ties between policies. If every policy is infeasible, that
list is empty. No hidden favorable action selection is used.

Baseline: private profits C=8, H=75/4, routed_H=18; expected insurance 0,35/4,9;
pre-policy welfare 8,5,4. Induced choices none/narrow/broad are H/routed_H/C and
after-cost welfare 5,7/2,6. At harm16, none and broad tie. At harm20 and extra
private weight4/43, none and broad tie in score. Narrow is dominated by none for
every nonnegative extra weight in this baseline funding mix.

CONDUCT MODULE
Exact fields:
  fee, gross_benefit, care_cost, harm, care_harm_probability,
  shortcut_harm_probability, inspection_probability, fine, pledged_funds,
  inspection_cost, authority_budget.
All probabilities lie in [0,1]; care_harm_probability cannot exceed the shortcut
probability in this supported family. care_cost <= fee makes the care cost
financeable from the fee. The pledged reserve is separately available for fines;
collectible_fine=min(fine,pledged_funds). A nominal fine above the reserve adds no
collection. If inspection probability is positive, authority_budget must cover
the cost of an inspection in every inspection state, not merely in expectation.

An inspection detects the shortcut itself, regardless of whether harm occurred.
Care is never fined. Inspection probability is the same under both actions. The
result needs these marginal probabilities and sanction rules, not independence
between realized harm and inspection: additive expected flows use their marginals.
No restitution, appeals, delayed collection, risk aversion or further behavior is
modeled. Such changes need new flow and incentive equations, not a reused result.

Seller profit is fee-care_cost under care and fee-a*collectible_fine under a
shortcut. Both actions remain best responses when a*collectible_fine=care_cost.
Buyer net is gross benefit minus fee and expected harm. Authority net is expected
fine minus expected inspection cost. Fee and fine cancel in aggregate welfare.

Baseline collectible fine10, deterrence margin1/2, unique care response. Under
care, buyer/seller/authority net flows are 9/2,4,-1/4, summing33/4. Under shortcut
they are -3,7/2,9/4, summing11/4. At paperfine100, reserve7 and a1/10, shortcut
profit53/10 exceeds care4. Weak deterrence requires a>=2/7; equality is a tie.

RESOLUTION MODULE
Exact fields:
  cash, long_assets, asset_loss, deposits, senior, junior, conversion,
  capital_floor, due_first, bridge_capacity, lender_cash, bridge_rate,
  liquidation_cost.
Opening equity=cash+long_assets-deposits-senior-junior must be nonnegative.
asset_loss <= long_assets. After loss, remaining assets must lie between deposits
and deposits+senior, inclusive. This is an intentionally restricted resolution
region: old equity and junior debt are fully wiped, deposit principal is covered,
and a senior residual may remain. Inputs outside it need a different loss case
and are explicitly rejected; the lab is not a general insolvency engine.

conversion cannot exceed surviving senior debt. due_first cannot exceed deposits.
bridge_capacity <= lender_cash proves the whole committed facility is backed by
the outside lender's cash. bridge_rate is a horizon rate in [0,1], not an annualized
rate. liquidation_cost cannot exceed remaining assets. All rights and priority
are stipulated to be effective and enforceable in time, in one currency without
transfer restrictions. These are not current legal findings.

Deposit due_first is owed at cutoff1. Long assets realize their known remaining
value only at cutoff2. Early funding need g=max(due_first-cash,0). A successful
bridge advances g at cutoff1 and is repaid g(1+r) at cutoff2. Principal is not
income. The lender has no other cash flows. The first payment reduces cash and
deposits; conversion reduces senior debt and raises equity without changing cash.
At maturity, interest gr reduces equity and increases the bridge liability.

The module preserves every dated balance-sheet snapshot. If g exceeds capacity,
it reports the unfunded gap and stops after conversion: no first payment or later
continuation is silently assumed. If the bridge is funded but conversion<gr, it
records the first payment and the insolvent maturity balance sheet, then leaves
final null because no secondary default waterfall has been stipulated. Valid
inputs can therefore produce a financially failed continuation. If solvent,
final reports all deposit and senior receipts, new equity, and lender net income.
continuing_capital_pass also requires first-cutoff funding; a merely algebraic
capital value cannot make an unfunded plan pass.

Immediate liquidation realizes remaining_assets-liquidation_cost before cutoff1
and pays the same stipulated priority. Its time and valuation assumptions are
separate from continuation. The result does not certify any actual legal creditor
safeguard or discount/risk adjustment.

Baseline: original equity10; loss30 allocated10/10/10 to equity/junior/senior;
surviving senior10. Conversion5 gives equity5 but cash6 remains short4 of due10.
Advance4, pay10, realize64, accrueinterest1/5, pay bridge21/5, deposits50 and
senior5, leaving equity24/5. Old senior value49/5 plus deposits60 plus lender
netinterest1/5 equals70. Conversion26/5 restores terminal capital5, leaves senior
24/5 and still needs the same advance4. Liquidation net62 pays deposit60/senior2.

VALIDATION AND LIMITS
The author checker is scripts/check_v11_c10.py in the book source tree. Its quiet
check() returns a JSON-safe summary and checks this package in normal and optimized
modes. It uses separate stakeholder and probability-state sums, all-tie choice
comparisons, ordered loss absorption and additive journal vectors; the model's
helpers and saved output are not its numerical oracle. It targets finite economic
boundary changes and invalid data, direct/resolved/symbolic/hard output aliases,
source/structure routes, manifest integrity and eight nonself author bindings.
It can run with only the nine owned author files in their same relative layout.

Model and checker agreement do not estimate external harm, identify actual capture,
prove a policy's causal effects, create a legal power or substitute for separately
scoped peer review. The chapter supplies the limits and further evidence required.
