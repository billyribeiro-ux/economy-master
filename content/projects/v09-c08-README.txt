MORAINE MANDATE REVIEW — VOLUME 9, CHAPTER 8
Original synthetic performance accounting and evaluation lab

RUN OFFLINE
Save v09-c08-inputs.json, v09-c08-analysis.py, v09-c08-output.json,
v09-c08-manifest.json and this README together. Run:

  python3 v09-c08-analysis.py
  python3 v09-c08-analysis.py path/to/an-input-copy.json

Only the Python standard library is used. The script reads inputs and prints a
complete JSON report; it does not write files, access the network or obtain real
market data. Import is quiet. run(data) accepts an already decoded input object,
is quiet, and returns strict JSON-compatible results. The manifest hashes the
four other distributed files, excluding itself. The library's separate focused
checker independently verifies the case; it is not needed to run this bundle.

Exact values use Fraction arithmetic and serialize as fraction strings, such as
"1/17500". These are decimal-return variances, not percentage numbers. A return
"1/500" means 0.002, or 0.2%. Fields ending in _approx use finite floating-point
values for square roots, ratios and root solving. Undefined ratios have Python
None internally and JSON null in actual output; they are not zero or infinity.
No approximate standard error carries an assertion of valid inference. For
verification, use absolute tolerance 1e-12 for reported rates/statistics and
1e-8 CU for the money-weighted terminal-value residual. Preserve exact fractions
until the final display; the chapter rounds table amounts to six decimals.

DATA, DATES AND THE EX-ANTE CONTRACT
All inputs are newly created teaching data. The 2027 dates are fictional labels,
not observed or forecast market outcomes. There is no external data license or
live-series dependency. The report contains three separate cases:

1. Eight successive monthly fund observations, January–August 2027.
2. A separate two-month, two-sector attribution sleeve.
3. A separate four-year panel of six funds with every entry and exit retained.

Do not treat the sleeve as the holdings behind the eight-month series, or the
four-year panel as additional monthly observations. All returns are simple total
returns in the fictional currency CU, with distributions reinvested. The panel
uses annual return periods Y1–Y4; the main fund uses equally spaced MONTHLY rate
periods, not actual/365 daily discounting. Calendar labels must be consecutive
month ends and do not alter that declared rate convention.

The main mandate is set before observation on 1 January 2027. It compares the
fund with an investable policy index whose excess return over cash is M. Its
benchmark return is therefore rf + M. The zero benchmark fee and frictionless
index implementation are stipulated only for this case. A risk/style regression
is a supplementary comparison, not a replacement mandate selected after returns
are known. Policy labels for the benchmark and fees are validated, rather than
silently ignored if edited.

The eight monthly cash rates are all 0.2%. M equals -1.5% in months 1–4 and 2.5%
in months 5–8. Z equals (-0.6%,-0.6%,1.4%,1.4%,-0.6%,-0.6%,1.4%,1.4%). Z is a
synthetic zero-cost long-short style payoff per fixed CU notional, not a fully
invested fund return. Its positive sample mean does not establish a priced
premium or a future trading opportunity. An actual replication would need
explicit shorting, financing, trading costs and capacity.

The gross fund returns are (-2.1%,-1.5%,-1.1%,-0.5%,2.7%,3.3%,3.7%,4.3%). They
include all modeled security-level trading costs, with no additional trading
costs or taxes in this toy contract. The monthly management fee is 0.2% of
BEGINNING NAV, paid after the return but before any end-of-month contribution.
Thus each net return is gross return minus 0.2 percentage points. This is not a
fee proportional to ending wealth or a performance fee.

MEASUREMENT AND FACTOR ANCHORS
Benchmark returns are -1.3% four times and 2.7% four times. Gross fund mean is
1.1% monthly, net mean 0.9%, and benchmark mean 0.7%. Gross and net active means
are therefore 0.4% and 0.2% monthly. Tracking-error sample variance uses n-1 = 7:

  active variance = 1/17500
  tracking error = 0.007559289460184544 decimal return per month
  gross information ratio = 0.5291502622129182
  net information ratio = 0.2645751311064591

The Sharpe numerator instead subtracts each period's cash return. Net excess mean
is 0.007 and its sample variance is 61/87500, giving Sharpe ratio approximately
0.2651167389017556. The similar numerical value is incidental. Main benchmark
variance is 2/4375; covariance of active and benchmark return is 2/21875. The
identity Var(P)=Var(B)+Var(active)+2 Cov(B,active) closes exactly.

The synthetic construction is

  gross fund return - rf = 0.001 + 1.2 M + 0.5 Z + residual.

The residual alternates -0.003,+0.003. Centered M, centered Z and the residual
are orthogonal in these eight observations. Full-rank OLS recovers gross alpha
0.001 and slopes 1.2, 0.5; the constant fee makes NET alpha -0.001 without
changing slopes, residuals or tracking error. Net active mean closes as

  -0.001 + (1.2-1)*0.005 + 0.5*0.004 = 0.002.

The market-only regression has net alpha +0.001, since its intercept absorbs
0.5 times Z's mean. This is model sensitivity, not evidence that either sample
intercept is a causal skill parameter or that any factor mean is priced risk.

Two-factor residual SSE is 9/125000. Its variance estimator uses n-3 = 5, giving
9/625000. The classic intercept variance is 4401/2000000000, standard error
0.0014834082378091338, and net intercept t about -0.6741232618991748. The code uses
(X'X)^-1 and the fixed-design homoskedastic, uncorrelated-error variance formula.
Those assumptions, normal-reference distribution and post-selection validity
are NOT established for the constructed observations. There are no p-values,
validated confidence intervals or skill estimates in the report.

Conditional annual fields multiply the arithmetic mean by 12, variance by 12,
and the ratio by sqrt(12). These refer to additive horizon sums under stable
moments and zero serial covariances. They are not exact compounded annual
performance or proof that these assumptions apply. The exact variance of an
h-period stationary sum is h*gamma0 + 2*sum((h-k)*gammak,k=1..h-1).

FEE, EXTERNAL-FLOW AND OPPORTUNITY-WEALTH LEDGERS
Initial wealth is 1,000 CU. The 500-CU contribution arrives after month 4's return
and fee, before month 5. It receives no month 4 investment return and does not
pay month 4's fee. The same timestamp is used for the benchmark and MWR equation.
The input array end_contributions is indexed by the just-completed period.

Fund next-NAV values, rounded to six decimals:
  1:   977.000000
  2:   960.391000
  3:   947.905917
  4: 1,441.270576  (941.270576 before the contribution)
  5: 1,477.302340
  6: 1,523.098713
  7: 1,576.407167
  8: 1,641.039861

Each full output row provides beginning NAV, gross profit, fee cash, pre-flow
NAV, contribution and next NAV. Net currency profit after 1,500 CU of total
contributions is 141.039861313 CU. Total management fee cash is 19.806751425 CU.
The eight-month net TWR is 7.173667525%; it removes external-flow weighting but
retains the contract's fees. It is not the arithmetic mean times eight.

Matched benchmark final wealth is
  [1000*(0.987)^4 + 500]*(1.027)^4 = 1611.950608605 CU.
Benchmark eight-month TWR is 5.572397688%. The final matched-flow wealth gap is
29.089252708 CU. This currency amount and the TWR difference are different
quantities with different bases.

The fund MWR equation is 1000*G^8 + 500*G^4 = final fund wealth. Investor cash
signs are -1000 at date 0, -500 at month 4 and +final wealth at month 8. The unique
positive gross root gives monthly MWR 1.352254267%; benchmark monthly MWR is
1.082438841%. The model's nonnegative-contribution contract makes the general
terminal-value polynomial strictly increasing for G>0, so bisection has a unique
positive gross root. The baseline also permits an independent quadratic check
in z=G^4. No general multiple-IRR engine or withdrawal schedule is implemented.

ARITHMETIC ATTRIBUTION AND ITS MULTIPERIOD LIMIT
The separate sleeve has 100 CU initial wealth, two sectors and two months.
Portfolio and benchmark both hold positive sector weights summing to one.
Holdings are fixed within a month; rebalancing occurs at the next opening,
costlessly. No external flows, taxes or fees exist in this sleeve.

The disclosed attribution is
  A_i=(w_i-W_i)*(b_i-R_B)
  S_i=W_i*(r_i-b_i)
  I_i=(w_i-W_i)*(r_i-b_i).
The three sums reconcile to R_P-R_B. The output includes all sector effects and
actual beginning/end currency holdings, not just aggregate labels.

Month 1: P return 7.6%, B return 6%; A/S/I = 0.5%/0.8%/0.3%.
Month 2: P return 0.5%, B return 0%; A/S/I = 0.5%/-0.2%/0.2%.
P ends with 108.138 CU, B with 106 CU. Return difference is 2.138 percentage
points; relative terminal wealth is 1069/53000, about 2.016981%. Merely summing
active returns gives 2.1%, and compounding them gives 2.108%; neither is the
compound wealth gap per initial CU.

The explicit exact link multiplies a period's effects by all earlier portfolio
gross factors and all later benchmark gross factors. Its two links are 1 and
1.076. Linked A/S/I = 0.01038/0.005848/0.005152, totaling 0.02138. This follows
from telescoping hybrid portfolio/benchmark products. It is an order-dependent
component convention, not a unique causal allocation or a skill estimate.

COMPLETE PANEL, SELECTION DATES AND CLOSURE CASH
The six-fund input has explicit entry/exit years and one net return or JSON null
for every year. Null means outside the fund's life, never a zero live return.
Terminal observations include all liquidation proceeds exactly once. Returns
are already net of fund costs; no additional investor dealing cost exists.
C exits after Y3's -50%; F exits after Y4's -20%, so both returns must remain.
All new entries are known and investable at their stated opening.

The fixed initial cohort A,B,C,D is chosen at date 0. Rank after Y2 using only
Y1–Y2 total returns; select two, breaking ties by ascending ID. E starts at Y3,
F at Y2; neither has the required initial-cohort history. Their observations
remain in the panel instead of being backfilled or discarded.

Training returns: A 21%, C 20%, B 10.25%, D -19%. Selected A and C each receive
100 CU at Y3 opening and are not rebalanced across Y3–Y4. A ends with 90.25;
C liquidates for 50 after Y3 and that cash earns the stipulated zero return
through Y4. Selected return is -29.875%, versus -9.75% if C is removed with
hindsight. The other initial managers deliver 10.34%; all four deliver -9.7675%.
Holdout top managers are B,D; overlap with A,C is zero. Under a hypothetical
exchangeable uniform ranking of four managers, zero overlap has probability
1/6. No such exchangeability or skill claim is inferred from this tiny panel.

A DIFFERENT all-available strategy rebalances equally at each year opening.
Eligible counts are 4,5,6,5; annual returns 6.25%,7%,-5%,0%; compound return
8.003125%. C's liquidation funds the next opening rebalance. The hindsight
final-survivor filter keeps A,B,D,E and still does not invent pre-entry E data.
Its yearly means 1/60,1/60,1/20,1/20 compound to 13.955625%. This is a look-ahead
comparison, not an implementable version of the all-available rule. The output
shows each year's opening entries, eligible fund returns, closing exits and
hindsight-kept identities, plus initial-cohort records and closure-to-cash paths.

BOUNDED EDITS AND MEANINGFUL REJECTIONS
Supported variants preserve the stated policy and dimensions. You may change
exact fund/factor returns while retaining a full-rank design; the constant fee;
positive starting wealth; nonnegative contributions before the last month;
positive fully invested sleeve weights and admissible sector returns; or panel
returns/valid entry-exit histories while preserving the four initial funds and
two-year ranking window. A fund's full liquidation loss of -100% is admissible
in the panel. The main monthly wealth factors must stay strictly positive.

Examples:
- Change the monthly fee to 0.003: active mean becomes 0.001, two-factor alpha
  -0.002, market-only alpha zero; tracking error is unchanged, net IR 0.132288.
- Move the 500-CU contribution to the end of month 3: the TWR is unchanged;
  month 4 fee cash and final wealth change, and matched benchmark/MWR use the
  new timestamp. This is not an alteration to the manager's return sequence.
- Change C's Y3 liquidation return to -0.20: selected holdout return becomes
  -14.875%, all initial managers -2.2675%, all-available four-year return
  13.6875%. The survivor-filtered comparison conceals the change to C.

A zero tracking-error variant returns an undefined ratio, including when the
constant active mean is positive. No infinite IR or arbitrage claim is returned.
Rejected policy changes include a different fee base, a nonzero benchmark fee,
a nonzero closure-cash return, negative external contributions, terminal-date
subscriptions, non-month-end/misaligned dates, invalid sector budgets or absent
sector weights, missing live/terminal observations, pre-entry/post-exit backfill,
and a factor design that loses rank. Use a different explicitly developed model
for those contracts instead of relabeling this fixture. The script is not a
universal holdings reconciler, manager database, optimization engine, statistical
selection correction or standards-compliance tool.

REVIEW PERIMETER
The separate quiet checker reconstructs factor coefficients from orthogonal
contrasts, cash wealth from contribution lots, attribution from currency and
counterfactual holdings, and panel outcomes from independent terminal-wealth
ledgers. It checks all eight exercise anchors, allowed interventions, important
failure cases, file hashes, source structure and portable normal/optimized CLI.
A passing checker supports this bounded numerical report; complete instructional
and source reviews are recorded separately. Neither agent review nor exact
arithmetic is independent human certification or evidence of real investment
skill. Future performance, broader sources, policies and implementation require
their own dated analysis.
