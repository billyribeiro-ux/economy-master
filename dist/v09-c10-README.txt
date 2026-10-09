ROWAN ALTERNATIVES DESK — v09-c10
Original synthetic cases. No observed prices, return estimates or current fund
terms are embedded. Standard-library Python 3 only; no network, installations,
spreadsheet engine or other package is required.

RUN OFFLINE
Keep these five files together:
  v09-c10-inputs.json
  v09-c10-analysis.py
  v09-c10-output.json
  v09-c10-README.txt
  v09-c10-manifest.json

From that directory:
  python3 -B v09-c10-analysis.py --input v09-c10-inputs.json

The default input, if --input is omitted, is the input beside the script, not
the working directory. The CLI writes only strict JSON to stdout. To save a
new comparison without overwriting the reference:
  python3 -B v09-c10-analysis.py --input copied-inputs.json --output my-result.json

An explicitly requested output must not already exist. It cannot be the input
file. Existing files, including the reference output, are never overwritten.
Successful --output runs produce no stdout/stderr. Invalid input exits with
code 2 and a concise stderr message. Import, load() and run() are quiet.
run(data) returns ordinary JSON-ready values. Economic rational values are
strings such as "146/5"; Fraction(value) recovers the exact number. IRRs and
square roots are finite floating-point JSON numbers. No NaN/Infinity is valid.
Booleans are not numeric inputs. Duplicate JSON keys, missing/unknown fields
and altered convention strings are rejected. Numeric strings may have at most
100 characters; input magnitudes are capped at 1e9 as a teaching-domain guard.

FILES AND REVIEW BOUNDARY
The manifest hashes exactly the four other distributed files. It does not
include its own hash. The repository's author review hashes all eight payloads
other than itself, including chapter, checker and source proposals. The quiet
checker lives at scripts/check_v09_c10.py and is run from the project root by:
  python3 -B book/scripts/check_v09_c10.py
Its check() returns strict JSON and emits nothing. It independently reconstructs
the financial anchors and all determinate exercises, checks meaningful accepted
edits/rejections, compares every reference output field, validates asset hashes,
and tests copied offline assets under normal and optimized Python. Structural
and numeric checks are not browser/mobile/print inspection or external academic
certification. The HTML links to these assets by flat filenames in the built
edition; do not add a projects/ prefix to those browser links.

FIXED TIMING AND CLAIM CONTRACTS
The exact conventions object is part of the model interface. Numeric inputs
may change within the stated domain, but changing payment order, taxes, carry
rules, commitment coverage, mark frequency or borrowing rights requires a new
model and explicit review. The script rejects unsupported convention changes.

1. PROPERTY: THREE ANNUAL PERIODS, NO DEFAULT MODEL
At date 0 buy for 1000 and pay 20 acquisition costs, financed by quoted par
debt 600 and equity 420. At annual dates 1–3, NOI is 90/96/102 and capex is 12
each. Interest is 6% of opening debt, before principal repayments 20/20/560.
Opening debt is therefore 600/580/560. All debt is repaid at 3; no refinancing,
cash reserve, tax, new equity injection or default recovery is assumed.
Sale at 3 follows operations and uses forward year-4 NOI 105 / cap rate .07.
Selling cost is 3% of gross price. The supplied asset discount rate .10 is
distinct from both the loan quote and the capitalization rate.

Gross sale 1500, net sale 1455.
Asset cash [-1020,78,84,1545].
Lender cash [-600,56,274/5,2968/5].
Equity cash [-420,22,146/5,4757/5].
Asset equals lender plus equity at every date. NPV at .10 = 374160/1331.
Asset IRR ~.1989252878; equity IRR ~.3488927379; lender IRR .06.
The separate stress uses forward NOI84 and cap rate .10; net sale4074/5,
equity terminal1556/5 and equity IRR ~-.0512233341. Debt still pays fully.

Allowed numeric edits must preserve nonnegative operating cash, sufficient
interim cash for debt service, full principal amortization and positive initial
equity and exit residual. Selling-cost fraction is [0,1); cap rates positive;
the supplied discount rate and loan rate are nonnegative in this bounded lab.
Default/workout and extra capital are not silently introduced. Zero debt is
allowed only with zero principal payments; lender IRR then becomes null.

2. APPRAISAL REPORTING: POPULATION AND FINITE PATH ARE SEPARATE
a[t] = theta*a[t-1] + (1-theta)*r[t], with known 0 <= theta < 1.
Population formulas assume stationary initialization, iid latent returns and
jointly iid latent/market pairs across time. Latent mean .08, sigma .20;
market sigma .15; latent market correlation .5; theta .6; safe simple return .02.
Reported variance is .01; covariance .006; beta4/15 versus latent2/3;
reported contemporary correlation .4; reported Sharpe .6 versus latent .3.
Variance of the sum of four reported simple returns is296/3125, not .04.
The long-run variance per period of that additive sum is latent variance .04.
These statements are not formulas for compounded wealth-return variance.

The separate finite path fixes initial report .08 and latent returns
[-.20,.20,-.10,.30]. Reports [-.032,.0608,-.00352,.117888] invert exactly.
Latent final wealth index =702/625; reported final index
=4363508509074/3814697265625. Neither the path nor its population parameters
are estimated from market data. Reported NAV need not be realizable cash.
Simple returns in this positive-wealth illustration must exceed -1; both sigmas
must be positive, correlation [-1,1], sum_horizon an integer1–100. Theta0 is
valid and restores the identity report. Theta1 is rejected as noninvertible.
No automatic empirical unsmoothing parameter is estimated.

3. PRIVATE FUND AND INVESTOR CASH: THREE ANNUAL PERIODS
Commitment100 covers investment capital only. Investment calls at dates0–3
are[40,30,20,0]; unused10 is formally released at3. Management fee2% of
original commitment is paid at1,2,3 outside that commitment. Gross distributions
are[0,8,12,120]. Terminal carry =20%*max(0,total gross distributions-investment
capital). Management fees are EXCLUDED from this stipulated carry base. No
hurdle, catch-up, interim carry, retained NAV or fund debt is assumed.
Carry10; LP contributions[40,32,22,2]; LP net distributions[0,8,12,110].
LP net cash[-40,-24,-10,108], net profit34, net IRR ~.1673123633.
Gross investment multiple14/9. LP TVPI=DPI=65/48; RVPI0. GP fees+carry16.
Benchmark gross returns[1.10,1.05,.95] compound each positive contribution and
distribution leg separately to3: FV(C)=98.71; FV(D)=129.38; ratio12938/9871;
terminal relative excess30.67. This is a specified cash-flow-matched ratio,
not risk-adjusted alpha or proof of a feasible self-financing benchmark account.

Investor liquidity is a separate ledger: initial cash90, other gated allocation
25, no cash interest, borrowing or sale of the gated investment. Initial call40
is paid at0. At every annual date: receive income5, pay spending6, pay the full
contribution (investment call plus management fee), THEN receive distribution.
Baseline pre-distribution balances50/17/2/11, final cash121. Delay8 from the
first distribution until3: pre-distribution balances50/17/-6/3. The date2
shortfall6 is a policy failure. The script continues arithmetic only to expose
the diagnostic deficit and required reserve; terminal_cash is null and
unfunded_diagnostic_terminal_balance is121. It does not treat this as a loan
or a successfully implemented path. Conditional delayed IRR ~.1555294901 uses
[-40,-32,-10,116] and is labeled 'if funded'.

At date0 before either investment, reserve6 more cash by reducing the planned
gated allocation25 to19, preserving total resources115. Initial cash96 then
gives balances56/23/0/9 and final cash127. The extra final cash comes from the
extra initial reserve, not additional fund profit. Gated NAV is never a cash
inflow. If an edited scenario needs more initial reserve than the planned gated
allocation, this repair is labeled infeasible and its ledger is null. An input
may be edited to another available initial budget, but the model never creates it.

Calls must be nonnegative, within investment commitment, with positive initial
call and zero final call. Gross distribution0 must be zero, final positive.
Carry must be payable from final distribution; before liquidation the NET cash
must remain nonpositive and final net cash positive. This maintains the single
sign-change IRR domain. Benchmark gross returns must be positive. The delayed
amount must be between zero and the first net distribution. All these are
scope limits, not claims that every private fund has this cash pattern.

4. FUTURES WRAPPER: THREE MODEL PERIODS, NOT ANNUALIZED
Initial cash1000, fixed10 contracts, multiplier1. Near entry100; near settles
and closes98 at date1. AFTER that settlement enter deferred maturity105 at zero
initial contract value. That same contract marks104 at2 and settles112 at3.
Variation cash[-20,-10,80]. The new notional1050 is an exposure measure, not a
cash purchase. Initial cash equals initial notional; later leverage can drift.
At each observed date credit1% interest on all opening cash including reserved
margin, settle variation, pay1% of opening NAV as management, then20% of positive
after-management NAV above old NET high-water mark. HWM initially1000; update
it to max(oldHWM,endingNAVafterfee). No external fund flows; no share adjustments.
Only after those cash flows, test the stipulated200 cash reserve. The reserve
is part of cash, not another cost. The date3 test precedes final closure;
release of margin at closure is not income. These are discrete fictional test
points, not real-world margin frequency or proof of intraperiod feasibility.

Ending cash980/970/1040, HWM1000/1000/1040, total interest29.5, management29.5,
performance10, variation50. Net total return4%; spot100 to112 gives12%. The
complete-path gap between10-unit spot price gain120 and futures variation50
is70; rolling at98 versus105 did not itself cause an immediate70 cash loss.
No physical storage or execution costs are included; they require a new cash term.

Separate first-period stress: settlement15 gives variation-850 and ending
cash150, hence50 margin shortfall despite positive NAV. No later strategy is
assumed funded in that stress. If edited main-path inputs breach margin, the
main ledger stops at the first failure, terminal_cash/return become null and
completed_periods counts only passed tests. The failed row includes its required
shortfall. Baseline spot comparison and new-contract quote are input diagnostics,
not evidence that a stopped strategy traded through those later dates.
Inputs use nonnegative quoted commodity prices (negative-price contracts are
outside this deliberately bounded fixture), positive initial/entry/spot basis,
positive units, margin within initial cash, cash yield[0,1] and fee rates[0,1).

LEARNING INTERVENTIONS AND LIMITS
In copied inputs, raise the property exit cap rate to .084, set theta0, set the
first-distribution delay to zero or change futures management rate to .02.
Predict each effect, then inspect all affected cash rows. The chapter's eighth
exercise has a reasoned committee rubric; no program can grade mandate judgment
by matching one opinion. Private-debt exercise payoffs are solved independently
in the checker; this lab does not predict default probabilities or fair prices.
All four cases remain conditional synthetic models, not empirical estimates of
illiquidity premiums, reliable expected performance or individually suitable
investment recommendations. Source proposals record actual inspected primary
bodies and their narrow use; no historical numbers are passed off as current.
