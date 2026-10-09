Aster bond laboratory — Volume 10, Chapter 1
===========================================

Purpose and provenance
----------------------
Every contract, quote and date combination in these files was created for this
textbook. There are no market observations, licensed data, authenticated security
terms or forecasts. The lab reconciles dated guaranteed cash flows, settlement
cash, discount factors and rate quotations. It does not provide investment advice
or establish that a hypothetical arbitrage can be traded in a real market.

Files
-----
v10-c01-inputs.json     Original bounded contract inputs.
v10-c01-analysis.py     Standard-library Python implementation.
v10-c01-output.json     Complete preserved reference output.
v10-c01-README.txt      This execution and interpretation guide.
v10-c01-manifest.json   SHA256/byte counts for those four payloads.

Put the five files in one directory. Use a Python version supporting the standard
library syntax in the script (Python 3.9 or later). No installation, account,
network, environment variable or paid service is needed. From that directory:

  python3 v10-c01-analysis.py
  python3 v10-c01-analysis.py --input v10-c01-inputs.json --output result.json

The first command prints strict JSON. With --output, the report is written to
that path without printing it. Inputs default to the file beside the script, so
an absolute script path works from another working directory. Relative explicit
--input and --output paths are interpreted from the current working directory.
The normal run does not alter the original input or reference file. An existing
explicit output path will be overwritten, so use a new filename for experiments.

run(data) is quiet and leaves the supplied dictionary unchanged. Importing the
module does not run the CLI. Exceptions report invalid or contradictory inputs;
there is no silent repair. Runtime domain checks remain active under python -O.

Numbers and units
-----------------
Financial inputs are bounded decimal or rational strings, such as "0.96" or
"24/25". JSON integers are used only for schema, annual forward dates and bill
day counts. Booleans, floating-point financial inputs, NaN, Infinity, unknown
keys and arbitrarily large numeric strings are not accepted. Monetary amounts
and most arithmetic are exact Fraction values serialized as strings, including
whole amounts. Roots, logarithms and geometric interpolation are finite floats.
Compare those with a stated numerical tolerance; do not demand exact textual
decimal equality across unrelated implementations.

All amounts are fictional currency units (CU), all payments are guaranteed, and
all examples omit fees, taxes, default and collateral unless the chapter states
a separate exercise. Present-value identities assume compatible claims. The
arbitrage illustrations also assume signed trading at simultaneous executable
prices. They do not imply a free cash-storage facility beyond the supplied
instruments. A positive discount can exceed one in the bounded lab, allowing
negative quoted rates. Implied discounts must be positive and at most ten; this
upper bound is a numerical teaching-domain limit, not a no-arbitrage theorem.

Settlement contract
-------------------
The fixed regular schedule is previous coupon 2025-01-15, next coupon 2025-07-15,
maturity 2026-01-15. Dates are unadjusted calendar dates. The buyer receives the
entire next coupon; no ex-coupon period, holiday calendar or record-date rule is
being inferred. Settlement may vary within [previous_coupon, next_coupon).
Changing the three contractual payment boundaries is unsupported and rejected.

Coupon = face * annual_coupon / 2. The final payment adds the entire face.
Accrued interest = coupon * elapsed calendar days / full current period days.
Dirty value is the sum of the two entitled payments times their supplied
settlement-date discount factors. Clean = dirty - accrued. Invoice components
scale by invoice_face / face. The default face is 100, making the prices per 100.
If face is changed, the lab reports values for that changed face rather than
silently retaining a per-100 label. invoice_face is the total purchased principal.

Baseline: 91 elapsed days out of 181; 90 days to the next coupon and 274 to the
final payment; coupon 3; dirty 2494/25 = 99.76; accrued 273/181; clean 444589/4525.
The invoice for 250,000 face is 249,400. Accrued interest is a quote allocation,
not another issuer payment. Moving settlement while leaving both supplied
settlement discounts unchanged is a hypothetical comparison of different dates
with the same input discounts, not an observed market roll-down experiment.

Annual bootstrap and replication
--------------------------------
A, B and C have fixed future cash-flow rows [100], [4,104], [6,6,106] at annual
dates 1,2,3. Their default dirty prices are 96,97.44,100.20. The implementation
solves the triangular system sequentially, producing D = [.96,.90,.84]. It then
reprices every instrument, derives annual and continuous spot quotes, and values
the target cash-flow vector [5,5,105]. Target fair value is 97.5.

Backward payoff matching derives actual holdings in A/B/C, rather than assuming
all zeros have separately executable quotes: [-25/2756,-25/2756,105/106]. Their
cost and each of their dated cash flows are reported. At a target quote of 98,
the quoted price minus fair value is .5. A positive difference means the target
is more expensive than its replica, conditional on the stated trading rights.

The three observed cash-flow contracts are fixed in this lab; price edits are
allowed if they yield positive bounded discounts. Replacing a failed discount
with zero would conceal a contradiction and is not implemented. The target
cash-flow vector and quote may be edited within the stated nonnegative bounds.
No extrapolation, smoothing objective or hidden default adjustment is fitted.

Yield and realized wealth
-------------------------
A separate two-year claim uses the first two recovered annual discounts, a face
of 100 and annual coupon rate .08. It pays [8,108], costs 104.88, and has annual
YTM approximately .05362041243. The root is found by monotone bisection in
log(1+y), with a wide bounded numerical bracket, and is checked by repricing.
This root algorithm is deliberately limited to one to three annual future cash
flows; the used case has two. It is not a general irregular-date IRR engine.

The output distinguishes the IRR of the bond's promised payments from terminal
wealth after an explicit coupon-reinvestment strategy. With reinvestment rate
zero, final wealth is 116 and annualized account growth is about .05167767610.
Accumulating the first coupon at the initial YTM instead gives 116.4289632994.
The root identity does not itself assume that the coupon is actually reinvested.

An independently supplied Year-1 resale yield .10 gives an ex-coupon sale price
1080/11. Including the received coupon, the one-year holding return is 179/14421.
Changing that resale yield changes this outcome, not the original curve price.
The comparison with the two-year zero uses .90^(-1/2)-1, about .05409255339.

Forward loan
------------
The start/end years are distinct observed curve dates, with 1 <= start < end <=3.
Gross locked repayment per unit lent is D(start)/D(end). The quoted annual
forward is effective, so a multi-year offered repayment uses (1+offered_rate)
raised to the number of annual intervals. All rates must have positive gross
factors; negative rates are permitted within the bounded input domain.

Baseline lending 60 at Year 1 locks receipt 64 at Year 2, with zero initial cost.
The default offered 7% loan pays 64.2. Its lender-side present value is .18, and
its terminal excess over the curve-implied repayment is .2. These fields have
signs: an unfavorable offered lender contract has a negative value. A claim
with zero initial value can still owe cash at a future date; it is not a funding
source for an investor who holds it without the required offsetting assets.

Interpolation
-------------
The unquoted midpoint between annual dates 1 and 2 is valued by linear discount,
log-linear discount, and an explicitly different positive log perturbation:
log D(u) = log D_base(u) + .02*(u-1)*(2-u).
All three retain the observed endpoints. Default prices for a 100-CU midpoint
payment are 93,92.95160030898,93.41752214444. The lab's .02 perturbation is a
fixed illustration, not an estimate or a user-optimized smoothing parameter.
For the default endpoints it also preserves positive instantaneous forwards.
After allowed price edits, positivity of discounts still holds but monotonicity
or nonnegative forwards is not guaranteed and is not silently imposed.

Bill quotation
--------------
This fictional bill has a fixed quote convention: face-discount rate on a
360-day year. P=face*(1-discount_rate*days/360). The default 180-day,6% quote gives
P=97 per face100. The investment gain is 3/97. Simple annual investment yields
are 6/97 on the 360 clock and 73/1164 on Actual/365. Effective and continuous
annual returns are also reported on the 360 clock. These are alternative
quotations of one supplied payoff, not different realized investments.
The incorrect_simple_yield_price field deliberately demonstrates the result of
using the discount quote as an investment yield: 100/1.03 instead of 97.

Useful interventions
--------------------
1. Move settlement to 2025-04-17: elapsed becomes92; dirty value is unchanged
   if the two supplied discounts are unchanged; AI rises3/181 and clean falls.
2. Change only B price to97: D2 becomes2329/2600 and D3 becomes23157/27560.
   The target price becomes268721/2756. Opposite discount movements arise from
   preserving C's quote; this is not a parallel yield shock.
3. Change offered forward rate to .06: the offered lender value becomes -.36
   and terminal difference -.4; the curve-implied fair repayment stays64.
4. Change reinvestment rate to .10: terminal wealth becomes116.8, but the bond's
   price and initial YTM do not change.
5. Set curve prices to [101,110.12,128.78], the fixed cash-flow rows evaluated
   at D=[1.01,1.02,1.10]. Positive discounts above one are permitted. Their
   interpretation still depends on the supplied asset/storage perimeter.

Meaningful failure checks include negative or zero implied discounts, altered
fixed cash-flow rows, settlement after the next coupon, inconsistent payment
dates, a bill price that would be nonpositive, invalid forward date order,
nonpositive gross rates, missing fields and nonfinite/bool financial inputs.

Verification limits
-------------------
The chapter checker independently reconstructs date counts, invoices, cash-flow
systems, a quadratic yield root, forward cash, quote conversions and every
determinate exercise. It checks complete reference output, file hashes, allowed
interventions and rejected domains, plus normal and optimized execution from an
unrelated working directory. Proofs and the research critique are also reviewed
editorially. These checks do not authenticate market data, certify every future
input, test browser/print layout or establish human mastery.
