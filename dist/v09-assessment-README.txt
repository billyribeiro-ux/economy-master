TERN SCHOLARSHIP POOL — VOLUME 9 INTEGRATED PROJECT
Original synthetic teaching case. Money is CU, not thousands of CU.

RUN AND INSPECT
Python 3 standard library only. Put the four distributed files together:
  v09-assessment-inputs.json
  v09-assessment-analysis.py
  v09-assessment-output.json
  v09-assessment-README.txt
The separate v09-assessment-manifest.json records their SHA256 and byte sizes.
From any working directory, run:
  python3 /path/to/v09-assessment-analysis.py
For a deliberate input copy and quiet file output:
  python3 /path/to/v09-assessment-analysis.py --input /path/to/copy.json --output /path/to/result.json
There is no download, package installation, credential, network request or random
seed. Importing the module is quiet. run(data) validates and returns a new strict
JSON-serializable dictionary; it neither mutates data nor prints. All rational
answers are strings, usually reduced fractions. Only labeled square-root/ratio
approximations are floating point. Undefined statistics are Python None internally
and JSON null in the file. JSON booleans and counts remain booleans and integers.
The output is the complete result, including all 670 feasible ranked portfolios,
not just a digest. Its order is deterministic.

PURPOSE AND PROVENANCE
The committee has an existing private commitment, scholarship payments, a small
research database and an annual liquid-asset mandate. Audit which manager could
have been selected using information actually available; distinguish that research
selection from authorization to put money at risk; then fund and implement a
prospective portfolio and report what happened against the frozen benchmark.
Every identifier, observation, release/revision date, quote, fee and policy is
original synthetic data. No real fund, current tax rule or legal obligation is
represented. The case's agreed rights are fictional enforceable contracts.
No source supplies these numerical observations. The source proposals document
stable methods only. The program is a bounded case benchmark, not a production
backtesting platform, legal opinion, return-estimation service or universal IPS.

FOUR INFORMATION CATEGORIES
1. Research records carry observation_end, released_on, version, gross_return and
   fee_on_beginning_nav. They permit a genuine point-in-time audit.
2. The committee separately supplies prospective means, a covariance prior,
   residual risk, preference coefficient, limits and manager overlay interval.
   These are planning assumptions. The short research sample does not validate them.
3. Design and outside-design stresses have explicit joint cash/return outcomes
   without probabilities. They are not draws from the planning moment law.
4. Held-out returns and final private proceeds become available later. They evaluate
   the frozen policy and never feed the allocation, benchmark, factor risk or search.

DATES AND RESEARCH PERIMETER
The decision and selection cutoff is 3 January 2025. Portfolio dates t0, t1, t2 are
3 January 2025, 3 July 2025 and 3 January 2026. Research evaluation cutoff is
5 January 2026. Training periods 1–4 end 31 March, 30 June, 30 September and
31 December 2024. Their ordinary releases are 2 April, 2 July, 2 October 2024 and
2 January 2025. Held-out periods 5–8 end 3 April, 3 July, 3 October 2025 and
3 January 2026. Their ordinary releases are the next day, except late entrant N
whose first release waits until its 8 April 2025 admission. All research holdings
have stipulated zero net return during the short gap from training end to decision.
Historical closure proceeds park in a zero-return research cash account. That
account is distinct from the prospective treasury account earning 1.005 per half year.

For each asset/period, first filter released_on <= cutoff, then use the latest
(released_on, version). A higher version learned later was unavailable earlier.
Net return = gross_return - fee_on_beginning_nav: the fee is a fraction of opening
NAV charged within that period, not a percentage of the ending gross balance.
Indices E and B have zero fees; active manager records charge 0.002 per quarter.
There are no contributions to these research accounts. Compound each account's
net gross factors. Initial cohort comparisons invest an equal initial amount in
K, M and CX, then let each account run; they do not rebalance the cohort every quarter.

Training net returns, as known at decision, in period order:
E    0.020, -0.040,  0.060, 0.000
B    0.010,  0.020, -0.010, 0.000
K    0.020,  0.002,  0.024, 0.006
M    0.018, -0.004,  0.020, 0.002
CX   0.050,  0.040, -0.300, 0.000 (last entry is post-liquidation cash)
The manager comparison is a quarterly rebalanced 40% E / 60% B account with
stipulated zero benchmark trading/management fees: 0.014, -0.004, 0.018, 0.
K and M entered the database on 31 December 2023. CX also entered then, liquidates
at the third return boundary, and its -0.300 return includes all proceeds and exit
charges. Closure is announced 2 October 2024. The surviving capital, 0.7644 per
initial CU, stays in cash; it is neither erased nor reset to one.
N is admitted 8 April 2025. Its backfilled four training returns, each 0.198 net,
are released only then. It was not selectable in January.
A revision to M period 4 (gross 0.028, fee 0.002, net 0.026) is released
10 July 2025. Its first vintage, net 0.002, was the available January observation.

Selection requires admission by cutoff, an open manager and a complete available
training history. Highest arithmetic mean net active return wins; ties use asset ID.
The frozen choice is K: mean active 0.006 versus M 0.002. Using the later M revision
makes M's mean 0.008; admitting backfilled N makes N the naive winner. Neither is
an admissible January selection. CX remains in cohort research but cannot receive
a new mandate after liquidation. The disclosed four training trials are mean
active return, compound relative wealth, last active return and sample information
ratio. Their winners are K, K, K and M. K has zero sample tracking error, so its
IR is undefined, not infinite. Its regression on the comparison has intercept
0.006, slope 1 and residual SSE 0 by construction in four observations. This is
not evidence of a risk-free premium, significant skill or a stable pricing factor.
Sample covariance and tracking-error variance divide by n-1 = 3. Means divide by 4.
IR uses a quarter's arithmetic mean and quarterly sample standard deviation.
No annualized IR or significance test is claimed.

The training equal-initial-capital full-cohort return is -0.04882555104; excluding
CX gives +0.04456167344. Training labels are explicitly point-in-time. The final
restated eight-period cohort uses the latest records at the evaluation cutoff,
INCLUDING the M period-4 revision. Final restated full-cohort return is
-1161865820609163/39062500000000000, approximately -2.97437650076%.
The final restated survivor-only return is approximately +7.31843524886%.
These are distinct reporting vintages, not a revised selection history.

Held-out net returns are:
E  0.040, -0.020,  0.030,  0.010  -> growth 1.06027376
B  0.010,  0.000, -0.020,  0.015  -> growth 1.004647
K -0.040,  0.020,  0.010, -0.020  -> growth 0.96921216
M  0.030,  0.010,  0.020,  0.000  -> growth 1.061106
The comparison returns are 0.022, -0.008, 0, 0.013, growth 1.027003712.
K's mean active return is -0.01425 per quarter and its terminal-factor difference
from the comparison is -0.057791552. The K/M contrast evaluates the frozen choice;
it does not authorize selecting M retrospectively. N remains outside the cohort.

PROSPECTIVE BUDGET, RIGHTS AND TERMINAL AVAILABILITY
Initial total wealth is 1,000 CU: a private stake at supplied accounting value
200 CU, E 250 CU, B 350 CU and cash 200 CU. The private carrying value is a budget
reference, not an executable sale quote or a pricing claim. It cannot be sold,
pledged or used as cash. Liquid budget is 800 CU. Initial unit prices are 1 CU.
Choose x CU in E, y in B and z in the selected manager, in 25-CU lots, with caps
400, 500 and 150 CU. No short sales or borrowing. Entry cost is
  K(x,y,z) = 0.005 |x-250| + 0.002 |y-350| + 0.004 z.
Opening cash is c = 800-x-y-z-K. Fees are paid once from cash on actual turnover.
There are no ongoing E/B/cash account fees. Manager net annual forecast already
subtracts its separately stipulated 0.008 annual fee. It is a prospective annual
contract convention, not an exact compounding of four historical quarterly fees.
At t2 all liquid sleeve values are available at the stated net total-return
factors: zero additional exit fees or spread. Private final proceeds include all
capital and all exit costs. There are no remaining private rights after that payout.
No missing terminal transaction cost is assumed in the final grant payment.

At t1 cash earns g = 1.005, then the private capital call and scholarship grant
are paid. Residual cash must be at least 20 CU. At t2 residual cash earns g again,
liquid sleeves and the private claim pay, and the final grant is paid. Ordinary
flows are call 80 and grant 60 at t1, grant 40 at t2. The call is an INTERNAL
portfolio investment, reducing cash and adding to the rights already represented
by final private proceeds. It is not an external withdrawal from total wealth.
Scholarship grants are external uses. The model never subtracts the call a second
time from the private payout or counts the private opening 200 as terminal cash.
The fixed strategic benchmark is E 250, B 300, manager 0; it pays its own entry
fee 0.1, holds cash 249.9 and owns the same private claim, calls and grants. It is
feasible under its own costs and limits and stays fixed after observing results.
This total-pool benchmark is distinct from the 40/60 manager research comparison.

PLANNING MOMENTS AND AMBIGUITY
Annual means of E and B are supplied as 0.08 and 0.03. From the four training
observations, sample covariance (n-1) is
  S = [[13/7500, -7/15000], [-7/15000, 1/6000]].
The supplied annual prior is [[0.04,0.004],[0.004,0.01]]. The fixed 50:50 blend is
  Sigma = 0.5 * 4S + 0.5 * prior
        = [[44/1875, 2/1875], [2/1875, 2/375]].
Its determinant is 436/3515625 > 0. Four times a quarterly covariance is an
additive annual planning proxy under equal independent shock periods. It is NOT
the exact variance of a compounded annual return. The fixed intensity and prior
are committee choices, not an estimated optimum or proof of forecasting accuracy.

Let F_E and F_B be zero-mean annual planning return deviations with covariance
Sigma. Manager net return is 0.4*(0.08+F_E)+0.6*(0.03+F_B)+a-0.008+epsilon_M,
where a lies in [0,0.012] and Var(epsilon_M)=0.0016. Thus its conditional mean is
0.042+a. The overlay interval has no probability. Its upper endpoint is a tentative
gross forecast; neither endpoint is inferred by annualizing K's sample intercept.
Private whole-claim payoff is 320+140F_E+40F_B+epsilon_P, where
Var(epsilon_P)=400 CU squared. Both residuals are orthogonal to both factors AND
to each other. The original private accounting series supplies no risk estimate.
At ordinary fixed calls/grants total terminal variance is therefore
  V = (x+0.4z+140, y+0.6z+40) Sigma (same vector)' + 0.0016 z^2 + 400.
Active variance against the strategic benchmark is
  A = (x+0.4z-250, y+0.6z-300) Sigma (same vector)' + 0.0016 z^2.
Private risk cancels only in A because both portfolios own the SAME claim. It is
present in total V. Units are CU squared; total standard deviation divided by
1,000 is a fraction of opening pool wealth. Cash and fixed ordinary payments have
no variance in this stipulated moment model; conditional stress calls are separate.

A bounded 16-state witness establishes that the baseline moments are coherent.
Let four independent equiprobable signs U1,U2,UM,UP take values -1,+1. Put
  a1=sqrt(Sigma_EE), b1=Sigma_EB/a1,
  b2=sqrt(Sigma_BB-Sigma_EB^2/Sigma_EE),
  F_E=a1 U1, F_B=b1 U1+b2 U2,
  epsilon_M=0.04 UM, epsilon_P=20 UP.
The four factors' linear loading representation makes the complete claim
covariance positive semidefinite (indeed positive definite here). The largest
absolute manager deviation is about 0.149072, private deviation about 44.63277 CU;
all baseline gross payoffs are positive. This is an existence witness, not a fitted
probability model or a pricing kernel. Conditional stress states need not belong
to these 16 states. Validation conservatively checks positive payoffs for this
bounded witness after allowed numerical edits; it does not test CAPM or no-arbitrage.

The mean terminal reserve at overlay a is
  M(a) = 1.08x+1.03y+(1.042+a)z+g*(g*c-80-60)+320-40.
The committee scores M(a)-4V/(2*1000). This is its mean-variance preference in CU,
not a theorem about welfare. Risk limits V<=6400 and A<=400 mean total/active
standard deviations no greater than 80/20 CU (8%/2% of initial wealth). The robust
score uses the worst mean over the interval; since z>=0 it is attained at a=0.
Nominal score uses a=0.012. Both optimize the SAME feasible set.

DESIGN SCENARIOS AND ENUMERATION
Two joint scenarios are enforced along with all risk/budget/lot/cap limits:
- equity_drawdown: annual net E -0.25, B +0.04, manager -0.114; private 220;
  t1 call 80, grant 60; t2 grant 40.
- joint_call_inflation: E -0.15, B -0.10, manager -0.148; private 240;
  t1 call 120, grant 80; t2 grant 60.
Manager stress returns are stipulated factor exposure, annual fee and residual
combinations. They are not treated as empirical probabilities. Ordinary cash must
cover the largest design t1 bill (200) plus buffer without sales: g*c>=220.
Each design scenario must leave at least 700 CU terminal reserve after its grant.
Enumerate 17*21*7=2,499 positions. Exactly 670 are feasible. Rankings break ties by
lower total variance, lower entry fee, then E/B/manager holdings. Violation counts
are nonexclusive: one rejected portfolio can fail several conditions.

Canonical answers (fractions in output are authoritative):
Robust: (325,250,0); fee 0.575; cash 224.425; V=465772/75; A=412/3;
  mean 974.474860625; score 923572103/960000; t1 cash margin 5.547125.
  Design reserves 769.724860625 and 706.924860625.
Nominal: (325,225,25); fee 0.725; cash 224.275; V=95963/15; A=2683/15;
  lower/upper means 974.623356875 / 974.923356875;
  lower/upper scores 961.828290208333... / 962.128290208333....
Robust runner-up: (300,275,0), fee 0.4, cash 224.6; V=432602/75; A=178/3;
  mean 973.401615; score 577119337/600000.
Benchmark: mean 970.7052475; V=365152/75; A=0.
Selecting K for diligence does not force an allocation to K. With the policy's
uncertain overlay, the robust optimum gives no manager capital. The nominal choice
is close and nearly uses the total risk limit; state that sensitivity honestly.

STAGED EXECUTION AND MATCHED REPORT
Target orders sell 100 B units and buy 75 E units. Only 75 B can be sold at t0.
The bond sale settles FIRST. If all 75 E were then bought, holdings would be
(325,275,0), fee 0.525, cash 199.475. The high design t1 bill leaves only
0.472375 CU cash: payments are funded but the buffer is short by 19.527625 CU.
The preapproved continuation fixes actual B=275 and target manager holding, then
chooses the highest robust-score feasible grid portfolio with E between inherited
250 and intended 325. It buys only 50 E, giving actual (300,275,0). This is not an
after-the-fact change to the strategic benchmark or an uncharged buy-and-resell.
Unfilled B sale 25 and canceled E buy 25 remain in the implementation comparison.

Held-out total-return factors, actual private proceeds 300 and ordinary calls/
grants yield terminal reserve: target 941.725582625; actual 940.511668;
benchmark 938.1677875; nominal counterfactual 940.688207875 CU.
Target minus benchmark = 3.557795125 (policy selection).
Actual minus target = -1.213914625 (implementation).
Actual minus benchmark = 2.3438805 = sum of those two differences.
Target minus actual opportunity component is 25*(G_E-G_B)=1.390669.
Actual minus target initial fee is -0.175; at t2 this is -0.176754375.
Their sum is 1.213914625. Offset initial notional changes give zero cash-principal
timing adjustment here; the general report retains that term when edits require it.
Cash is compounded only until it leaves. No independent private value at the t1
external-flow boundary is supplied, so this is matched terminal-wealth reporting,
not an invented total-pool time-weighted return. The manager accounts have complete
net return series and can legitimately be compounded separately. A positive pool
benchmark gap on one path does not identify skill or establish a pricing premium.

OUTSIDE-DESIGN CALL AND FORCED SALE
Apply this scenario to the approved target (not the separate partial-fill path):
at t1 call 160, grant 80, required residual cash 20. Opening grown cash is
225.547125. The cash gap to the buffer is 34.452875. A specifically preauthorized
bond contingency sale may sell up to 100 original units (and no more than held).
Each unit is marked at 0.98 CU and realizes 0.98-0.020-0.002=0.958 net CU.
Continuous original units are allowed for this emergency sale only; the initial
25-CU lot restriction is not silently reused. Required sale = 275623/7664 units,
about 35.9633351. Marked value removed equals net cash raised plus spread and fee.
After sale, call and grant, cash is exactly 20. Original B units sold cannot also
produce terminal bond proceeds. At t2 E earns -0.30, B -0.15, manager -0.25;
private payout is 180 and final grant 60. Reserve is 84232137/153280,
about 549.5311652 CU. Floor gap is 23063863/153280, about 150.4688348 CU.
The contingency funds dated payments but fails the reserve floor. No hidden loan,
private resale or unapproved external contribution closes it. New funding at t2
would require that exact cash contribution with equal outside owner/donor outlay.
With capacity edited to 20 units, t1 payments are funded but the 20-CU buffer still
fails; with capacity zero, the call/grant payment itself fails. The latter branch
has JSON null for subsequent cash/reserve because the stipulated rights after
nonpayment have not been supplied. It does not invent a default continuation.

BOUNDED EDITS AND DOMAIN CHECKS
Keep the identity, conventions, original cohort, roles, 4+4 partition, four-trial
search log, 25-CU grid, 40/60 manager loading, 50:50 blend and multiplier fixed.
Numerical positions/caps, cost rates, means, overlay endpoints, residual risk,
positive-definite prior, risk/preferences/buffers, dated scenario amounts, permitted
execution capacity and properly dated record/release revisions may be varied.
The fixed strategic benchmark must remain feasible. Inputs must have the documented
exact keys, rational strings or integers (no numeric booleans/floats), matched
return boundaries, unique versions, complete required available histories, positive
net research wealth and positive bounded planning payoffs. Larger grids above
10,000 candidates are rejected. Returned portfolios can differ or an execution
fixture can explicitly be unavailable when a changed target no longer calls for
a bond sale/equity buy or no feasible authorized continuation exists. Do not treat
that diagnostic as permission to override the policy. A changed input/output is
a separate intervention and will not match the canonical output/manifest.

For sensitivity work, preserve the original file, record one changed assumption,
run the same model and compare complete output. Useful interventions: move the M
revision release before selection; alter only a held-out K return; set overlay
upper=lower=0; raise the available initial B sale to 100; reduce emergency sale
capacity to 20 and then zero. Explain the economic mechanism and what remains
unchanged. The focused checker reconstructs the original ledgers, data-vintage
selection, independent covariance and exhaustive grid, execution and wealth
identities, boundary interventions, strict validation and isolated normal/-O CLI
reproduction. It does not establish empirical truth or external certification.
