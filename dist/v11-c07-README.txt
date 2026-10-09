V 11-C 07 — ONE INVENTORY, ONE CLOCK, ONE LOSS
==========================================

PURPOSE AND PROVENANCE

This original synthetic teaching lab accompanies Stress testing and risk
aggregation. One institution I holds cash, a zero-coupon bond, a borrower
claim and a claim on a two-node clearing network. Five joint scenarios pass
through asset marks, cash incidents, actual network receipts, collateral
constraints, secured funding and partially fulfilled withdrawal requests.
A separate monotone severity family has certified reverse-stress brackets.
All amounts, scenarios, contract terms and thresholds were created for this
chapter. They are not observed market data, estimated probabilities, current
regulatory requirements or an accounting-standard implementation.

The original chapter derives the finite network and funding results. The
source proposal records the actual final 2018 BCBS PDF scope read for general
methodological context; the BCBS does not supply these numbers or contracts.

PORTABLE FILES AND EXECUTION

Keep these five files together:
  v11-c07-inputs.json     original exact assumptions
  v11-c07-analysis.py    Python standard-library implementation
  v11-c07-output.json    saved complete baseline result
  v11-c07-README.txt     this contract and reproduction guide
  v11-c07-manifest.json  hashes and bytes of the four preceding payloads

Python 3.9 or later suffices. No package installation, network, randomness,
environment variable or other repository file is needed by the model.

  python3 /path/v11-c07-analysis.py --input /path/v11-c07-inputs.json --output /path/result.json
  python3 -O /path/v11-c07-analysis.py --input /path/v11-c07-inputs.json --output /path/result-O.json

If arguments are omitted, input and output resolve beside the model, not in
the working directory. Both successful CLI commands are quiet and produce
identical UTF-8 JSON with a terminal newline. Invalid input exits 2, emits a
concise stderr message and does not open the output for writing. Input/model
output aliases are rejected using resolved paths and existing-file identity,
including direct, relative, symbolic-link and hard-link aliases. These
protected files remain unchanged. A filesystem failure is still possible;
this CLI is not a transactional storage system.

Import using importlib or runpy and call run(data) with a decoded object.
Import and run are quiet. run performs no I/O, does not mutate data, and
returns a fresh strict-JSON-compatible result; invalid API inputs raise
ValueError. Duplicate serialized JSON keys can only be detected by the
loader, not after a caller has decoded them into a dictionary. Validation
uses explicit exceptions and is unchanged under python -O.

The repository's separate checker is scripts/check_v11_c07.py. Its quiet
check() API returns a summary; its CLI prints that summary. It uses explicit
resource/journal certificates, independently derived reverse-boundary
polynomials, meaningful financial transfers and normal/-O portable checks.
Passing numerical checks does not validate external assumptions or replace
the separate peer/coordinator acceptance gate.

EXACT INPUT FORMAT

The root object has exactly schema, institution, network, reference,
scenarios and reverse. schema equals "v11-c07-inputs-1". Nested key sets
must match the supplied file exactly. No unknown or missing fields are
silently ignored.

All monetary quantities, fractions and rates are decimal/integer/rational
STRINGS, such as "12", "0.05" or "1/20". Floating JSON numbers, booleans,
NaN, Infinity, exponent notation, spaces, plus signs, integer leading zeros,
zero/negative denominators and strings longer than 32 characters are rejected.
After fraction reduction, the absolute numerator and denominator must each
be at most 1,000,000,000. Values normally lie in[0,1000], with tighter limits
below. A minus sign is accepted only for a scenario yield, whose lower bound
is-1/2. Rates use decimal proportions, not percentage-point labels.

The two integer exceptions are institution.bond_years, an actual JSON
integer 1..5, and reverse.bisections, an actual integer 8..48. A bool is not an
integer for this contract. CLI input is at most 65,536 bytes; the reader reads
one extra byte to detect excess. Duplicate JSON keys and nonfinite tokens
are rejected. Financial output is reduced rational strings. Flags are bool,
bond maturity is an integer, and absent boundary endpoints are null.

DOMAIN AND ECONOMIC RIGHTS

institution:
  cash, deposits, secured_old, facility_limit, cash_floor, equity_floor:
    nonnegative strings <=1000.
  bond_face, loan_face: strictly positive strings <=1000.
  bond_years: integer 1..5.
  base_yield: [0,1/2].
  pledged_fraction: [0,1].
  secured_daily_rate: [0,1/100].

Opening bond value is bond_face/(1+base_yield)^bond_years, borrower value is
loan_face/(1+base_yield), and network claim is the outside share of its total
obligation. Opening equity equals all four assets less deposits and old
secured principal and must be strictly positive. Both policy floors are
allowed to be above the initial slack: this produces an already-triggered
reference rather than a fabricated later root.

network:
  obligation: common positive promised amount T<=1000 for B and C.
  interbank_share: common share a in[0,3/4].
  external_b, external_c: reference external cash in[0,1000], each at least
    (1-a)T so all promised reference payments are made.

B owes aT to C and(1-a)T to I. C owes aT to B and the remainder outside the
network. There are no other assets, outside borrowing, bankruptcy costs,
guarantees or priority classes. Payments are pari passu and limited by
resources. A legally/operationally effective simultaneous batch makes
incoming funds available for outgoing clearing. This is not a simulation of
sequential gross settlement. I owes nothing back to B/C in this batch.

The unique solution satisfies pB=min(T,b+a*pC),pC=min(T,c+a*pB). The model
checks all four capped/uncapped candidates exactly; duplicate candidate
labels at a boundary are allowed only when the vector is identical. The
chapter proves existence, uniqueness and continuity using a<1. A closed
a=1 cycle is deliberately unsupported. The output includes each internal
receipt, each outside receipt, retained resources, unpaid obligations,
zero external resource residual, a standalone full-counterparty benchmark,
and the loss already embedded in the final receipt through feedback.

reference:
  haircut: [0,9/10].
  withdrawal: [0,opening deposits].

Old secured principal cannot exceed (1-reference haircut)*pledged_fraction
times opening bond value. Thus the reference is initially adequately
collateralized, even though policy thresholds or later payment requests
may still be problematic. The reference object sets the x=0 reverse path;
it is not required to occur among the finite scenario rows.

scenarios:
  One to eight exact objects; ids are unique strings matching a lower-case
  letter followed by 0..31 lower-case letters, digits or underscores.
  yield is in[-1/2,1], so every discount factor is strictly positive.
  loan_loss_fraction is in[0,1].
  external_b and external_c are nonnegative <=1000.
  haircut is in[0,19/20].
  withdrawal is at most the initial deposit liability.
  operating_cash_loss is at most initial cash, since that incident occurs
  before all receipts or funding and cannot steal nonexistent initial cash.
  facility_limit is nonnegative and no larger than the contractual ceiling
  in institution. It is the amount operationally available in that scenario.

The reference is a value/contract baseline, not a forecast. Scenario rows
need not be ordered and carry no probabilities. Adverse results are valid
outputs: capital may turn negative, requests may remain unpaid, and policy
thresholds may be breached. Unsupported inputs, not adverse economics,
produce errors. Lowering operational facility availability is valid; raising
it above the contract without changing the contract is invalid.

reverse:
  Seven nonnegative slopes: yield_increase, loan_loss_increase,
  b_resource_drop, c_resource_drop, haircut_increase, withdrawal_increase,
  operating_loss_increase; each bounded by 1000 before tighter endpoint tests.
  The parameter x is restricted to[0,1]. Yield starts at base_yield and rises;
  borrower loss fraction starts 0; b,c decline from network reference cash;
  haircut and withdrawal start at reference values; the cash incident starts 0.
  Facility availability remains the contractual ceiling along this family.
  Endpoint yield must be<=1, b/c must remain nonnegative, and the entire
  scenario-domain conditions must hold at x=1. Nonnegative slopes make the
  endpoint tests sufficient for all intervening x. bisections is 8..48.

COMMON DATES, JOURNALS AND COLLATERAL

The initial inventory contains cash, bond, borrower claim and the B claim.
Scenario marks occur at today's opening instant. Losses are the differences
between initial and stressed asset values, plus the specified cash incident.
They enter this teaching measure of current profit/equity. Liability principal
stays at par. This convention is not a comprehensive fair-value or regulatory
capital standard and is not claimed to be a no-arbitrage pricing model.

The seven ledger rows are:
  1 opening snapshot;
  2 joint asset marks, with the complete network impairment included once;
  3 cash incident, reducing available cash and equity;
  4 network batch receipt, removing the marked claim and adding equal cash;
  5 new secured draw, adding cash and a new secured principal liability;
  6 old secured principal paydown, reducing cash and that liability;
  7 deposit payment, reducing cash and deposits.

Every row carries assets, independent equity and a zero accounting residual.
Rows 6 and 7 pay only available cash. An unfilled request remains in the
outstanding liability; no unexplained negative cash or liability cancellation
is used to make the balance sheet close. Any acceleration, legal resolution,
withdrawal-priority change or bankruptcy expense after failure is outside
this cutoff model and needs additional rules.

The originally pledged bond fraction q remains fully reserved. Its collateral
capacity is (1-h)*q*P and the required old principal reduction is the positive
part of old debt minus that amount. New capacity is the minimum of available
facility and (1-h)*(1-q)*P. Old collateral is not freed and recycled inside
the cutoff, even after principal is repaid. The draw to reach the chosen cash
floor is capped by this new capacity. New pledge fraction is draw/((1-h)*P);
the output reports it and the remaining free fraction.

Funding-capacity slack uses the MAXIMUM potential draw, less full required
paydown, full withdrawals and cash_floor. This signed certificate is not the
actual closing-cash balance under the smallest-draw policy. The baseline
actually closes with 2 but has 20 additional CU of funding headroom. A zero
capacity slack triggers the chosen reserve policy, including equality; a
negative cash budget is needed for actual payment shortage.

Both old remaining secured principal and the new draw are due next day with
the specified daily interest. The output separately gives principal, interest
and total. Today's balances precede that accrual. The stressed borrower cash
is due in year 1; bond_face is due in bond_years. No next-day refinancing,
future asset sale or payment ability is proved by these later receipts. The
model's acceptance at today's cutoff must not be relabeled survival to final
maturity.

REVERSE BRACKETS AND AGGREGATION

For capital_slack, funding_slack and their minimum first, output is one of:
  triggered_at_reference: equality or failure already at x=0; endpoints 0.
  no_trigger_in_supported_interval: slack remains strictly positive at x=1;
    endpoints/width null, reference/endpoint values provided.
  boundary_bracketed: lower is strictly safe, upper triggers at equality or
    below, and width is exactly 2^-bisections.

Continuity, compactness and monotonicity justify the first-trigger bracket.
The model does not report an arbitrary midpoint as an exact root. This search
does not optimize over all imaginable paths, and the finite outage scenario
is outside the one-dimensional reverse family. A strict-positive-shortage
condition can have an infimum that is not itself a shortage; reserve/capital
intervention uses a closed condition including equality.

The finite aggregation output compares the maximum total loss of a COMMON
scenario with the sum of each component's separate maximum over the same
menu. Their nonnegative difference need not correspond to an admissible
row. Negative component losses are gains, not discarded. No independence,
confidence level, missing-tail guarantee or stress probability is inferred.

BASELINE ANCHORS AND TRANSFERS

Assets 202 and equity 45. The stressed B/C resources 2/8 clear payments 8/12;
I receives 4, so its 10 claim loses 6 including the 2 feedback increment.
Joint loss 24440/529 and equity-635/529; with a 20 facility, unpaid withdrawals
16483/1058 and actual cash 0. A funding outage instead leaves equity 45 and
unpaid withdrawals 8. Component maxima sum 496624/8993, whereas the largest
common-scenario loss is 24440/529; gap 3528/391.

The 40-step reverse upper endpoints approximate:
  reserve-capacity boundary .545784230258;
  capital boundary .751688814506.
At the first boundary equity is about 19.650135 and payments still occur.
With cash_floor 0, zero cash occurs near.596675093210; strict nonpayment begins
above that boundary. With 5 external cash funded as equity, funding/capital
boundaries become about.673395979956/.861274373503. Funding the same cash by
an additional deposit gives the same frozen-demand liquidity benefit but
leaves the original capital boundary. A changed withdrawal response requires
a changed scenario, not reuse of those numbers.

Try those interventions, the b 4/c 6 network, and a 40-CU facility with the
unchanged collateral inventory. Read the chapter's full solutions only after
reconciling both the resource equations and each changed balance sheet.
