VOLUME 10 CHAPTER 5 — FORWARDS, FUTURES AND SWAPS
Original Larch Treasury teaching laboratory, 9 October 2026

PURPOSE AND PROVENANCE
All inputs are authored synthetic contracts, not historical or current market
observations. Use alongside the chapter for price/value, dated cash, funding,
projection and basis reasoning. No data download, credentials, third-party
packages or network are required. The model is not a clearing or trading system.
No real exchange's margin, settlement rounding or collateral rules are encoded.

FILES
v10-c05-inputs.json       original contract inputs
v10-c05-analysis.py       standard-library Python model
v10-c05-output.json       full reference result, exact rational strings
v10-c05-README.txt        this specification and interpretation
v10-c05-manifest.json     SHA256 for the preceding four files

RUN
Save the five files together. From that directory:
  python3 v10-c05-analysis.py --input v10-c05-inputs.json
  python3 v10-c05-analysis.py --input v10-c05-inputs.json --output result.json
  python3 -O v10-c05-analysis.py --input v10-c05-inputs.json --output optimized.json

From any other working directory, give explicit absolute paths to the script,
input and optional output. The output argument is a requested destination and
will replace an existing file at that exact path. Importing the module is quiet.
run(data) is the public API; it returns a new JSON-safe dictionary and leaves its
input unchanged. The CLI without --output prints only its JSON result. Invalid
input produces a nonzero exit and diagnostic. Duplicate JSON object keys and
NaN/Infinity constants are rejected by the CLI. There is no random seed because
all calculations are deterministic and exact.

NUMBER AND SCOPE CONTRACT
Every financial input is an integer or an exact decimal/fraction STRING, for
example "0.95" or "19/20". Floats (including 0.95), booleans, nonfinite strings,
zero denominators and strings longer than 64 characters are rejected. The
parsed rational must have denominator <=10^12 and numerator magnitude <=10^24;
the numeric bounds below apply as well. Lists are at most 24 entries. Required
object keys must match exactly; extra fields are rejected. The schema string is
v10-c05-1, and provenance must be text. No global cross-case consistency is
implied: the seven independent cases represent different contracts.

All financial OUTPUT numbers are exact rational strings, including exact zeros.
Ledger date indices remain integers, matched_quantity is Boolean, and schema
is text. JSON serialization disallows nonfinite outputs. Decimal displays in
the chapter are rounding for reading; use the rational output for arithmetic.
The script uses explicit validation, not assert statements that disappear under
Python -O. Bounds describe a teaching domain, not market admissibility.

CASE DEFINITIONS

1. carry
spot is positive CU/unit and <=10^9; maturity is in (0,30] years; discount is in
(0,3]. delivery_price is in [0,10^9]. Up to 24 events are strictly increasing,
strictly before maturity, and each has a positive time <=30 and discount <=3.
income and cost are nonnegative CU/unit, each <=10^9. The complete carry
package is stipulated reversible. Net income is borrowed against a dated
repayment; net cost means that this borrowing is negative (a deposit). Prepaid
delivery must be positive, or the case is outside this positive-asset model.
Discounts above one are allowed. Cash-flow strips may belong to any positive
matched discount curve; no monotonicity is imposed. The model does not infer
delivery rights, ex-dividend entitlement, uncertain income or short-sale access.
Baseline: prepaid98.04, fair103.2, old long value2.09; every interim residual0.

2. fx
spot and delivery price are domestic CU per FU, bounded above by10^6; spot is
strictly positive and delivery is nonnegative. Both discounts are in (0,3].
foreign_notional is in (0,10^9] FU. The model prices a long old contract and
reconstructs a short-forward funded deposit. Long value is in domestic CU NOW;
short surplus is in domestic CU AT MATURITY, not its undiscounted value today.
Symmetric matched funding is assumed for this case; executable bid/ask and
asymmetric access are handled explicitly in the chapter's separate exercise.
Baseline: fair1.2375, deposit1,980,000FU, funding2,376,000CU, repayment2,475,000CU,
short terminal surplus25,000CU, old long value-24,000CU.

3. tree
This is a two-interval finite pricing tree. First gross return is known at date0.
State is revealed at date1, when BOTH the next gross return and terminal spot
are known. Each gross is in [0.1,3]. From1 to24 strictly positive pricing
probabilities sum EXACTLY to1. State lists must have matching lengths. Terminal
spots are positive and <=10^9. The terminal spot has no payouts/carry costs;
node spot is terminal_spot/second_gross. Initial spot and bond are calculated
from the same supplied positive pricing rule. These are NOT physical forecasts.
The futures has zero residual value after each settlement and no margin funding
wedge. All its price uncertainty is resolved at date1, so final variation is0.
The output's funded terminal futures cash accumulates date1 variation at the
state-specific second gross. Date0 valuation discounts both intervals.
Baseline: bond11/12, spot90, forward1080/11, futures100, gap20/11. Date1 variation
is(20,-20), terminal funded cash(24,-20); discounted value is exactly0.

4. margin
contracts is a nonzero integer in [-10000,10000], positive for long, negative
for short. multiplier is in (0,10^6]. There are2–24 settlement quotes, each in
[-10^6,10^6]. Unlike the positive-asset tree, this invented settlement ledger
allows negative quotes. There is one funding_gross per quote interval, in
[0.1,3]. These are interval gross factors, not annual yields. initial is in
(0,10^9] for the ENTIRE account. maintenance is in (0,initial].
The account earns zero; gains stay in it. At each nonfinal date, balance strictly
below maintenance triggers a contribution restoring initial. Equality does not
trigger a call. At final close, a negative balance is paid to bring it to zero;
otherwise the balance is released. There is no post-close initial-margin call.
All contributions are borrowed. Debt earns the interval gross BEFORE that
date's new contribution is added. No early withdrawals or debt repayments are
modeled. Release repays debt at the final date. total_posted is cumulative
contributions; no withdrawals means it is the maximum contributed principal.
It is NOT the highest account balance, which may include trading gains.
funding_cost = terminal debt - contributed principal and may be negative when
gross factors are below1. net_after_funding = release - debt. The cash residual
release - total_posted - total_variation must be zero.
Baseline: variations(-200,300,-50), call200 atdate1, posted600, released650,
terminal debt634.5624, funding cost34.5624, net15.4376.

5. swap
notional is in (0,10^9] CU. Lists have equal lengths1–24. accruals are positive
year fractions <=5; discounts are in (0,3]. projected_rates and fixed_rate are
annual rates in [-2,2]. Each 1+accrual*projected_rate must be positive.
The supplied projections represent payment-weighted index pricing, not physical
means. The model computes the PV of those specified projections; it does not
prove existence of a joint market model or calibrate a multi-curve system.
The alternative single-curve rates come from adjacent discount ratios, starting
from D0=1. single_curve_floating_pv and single_curve_par explicitly describe
THAT alternative projection. The same-currency swap exchanges no principal.
pv_change_per_fixed_rate_unit holds projections and discounts fixed. A basis
point is0.0001 rate units; this sensitivity is not full market-rate DV01.
Known first fixing can be supplied in place of the first projected rate.
Baseline: annuity1.9 years, floating PV94400, fixed PV85500, payer value8900,
par118/2375, alternate floating PV75000, alternate par3/76.

6. collateral
receipt is a positive certain CU payment <=10^9, and collateral_gross is in
[0.1,3]. fully_reusable_claim_value assumes precisely the chapter's one-period
fully reusable, equal-value cash collateral, symmetric, no-default arrangement.
It is not general stochastic derivative valuation. segregated_initial is in
[0,10^9], funding_rate and remuneration_rate in [-1,2], year_fraction in (0,5].
Both simple accumulation factors must be positive. The segregated calculation
is an INDEPENDENT fixed-deposit funding cost, not an automatic adjustment to
the first claim. Baseline claim value100; independent deposit returns10050,
funding requires10150, net cost100.

7. basis
units is positive and <=10^9. Price quotes and total measured funding_cost are
signed CU amounts with magnitude <=10^9. contracts is an integer in[0,10000]
and denotes a SHORT position; multiplier is in (0,10^6]. Sale receipt is local
spot*units, nominal futures receipt is contracts*multiplier*(initial-final).
Funding_cost is supplied as an already measured adjustment in consistent final
cash units; the model does not infer a path or cost from endpoint quotations.
matched_quantity only checks contract units equal sale units. Local basis is
local spot minus futures fixing. Baseline sale9400, futures600, basis-2,
matched_quantity true, combined before funding10000 and after funding9850.

INTERVENTIONS TO TRY
Swap the baseline tree's two second gross factors, preserving spots and Q. The
futures quote remains100; forward becomes1120/11 and the gap becomes-20/11.
Set both second gross factors to1.1: forward=futures100, initial spot1000/11,
bond10/11. The entire cash-price environment adjusts coherently.
Reduce baseline maintenance to200: equality after first loss avoids a call.
Final release is450, contributed400 and debt424.4424, leaving25.5576. Trading
variation is still50; changing the collateral rule changes financing, not prices.
Increase only the swap's fixed_rate to0.055: value falls by19000 to-10100.
Set funding_gross to all ones: the margin's net equals nominal variation50.
Set carry income and cost equal: net strips vanish; no-payout carry is recovered.

VALIDATION AND LIMITS
The chapter checker separately reconstructs every worked numerical case and
determinate exercise, tests economic interventions and input boundaries, checks
the four-payload manifest, and executes portable normal/optimized CLI runs from
an unrelated working directory. Saved output is compared in full but is not the
sole numerical oracle. Proof assumptions, exercise teaching and source scope
also require editorial review; computation is not proof of theorems or empirical
model adequacy. Whole-site visual/mobile/keyboard/print QA remains separately
recorded. No independent human academic or market certification is claimed.
