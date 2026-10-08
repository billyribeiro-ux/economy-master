ORIEL PORTFOLIO MATHEMATICS LABORATORY
Original synthetic teaching package, 8 October 2026.

PURPOSE
Reconstruct a portfolio budget and its population or sample covariance before
interpreting diversification. This is a bounded one-period teaching model, not
an optimizer, a market data service or a recommendation. Every asset, observation,
probability and financing permission is invented and declared in the inputs.

FILES
v09-c02-inputs.json   Complete original state, allocation, financing and sample inputs.
v09-c02-analysis.py   Standard-library benchmark with quiet import and run(data).
v09-c02-output.json  Complete preserved reference result.
v09-c02-README.txt   This execution and scope guide.
v09-c02-manifest.json SHA-256/byte manifest for the other four distributed assets.

RUN OFFLINE
Keep the five files together. Python 3 requires no added package or network.
Run from any working directory:

    python3 /path/to/v09-c02-analysis.py

Or supply the input path as its one argument:

    python3 v09-c02-analysis.py v09-c02-inputs.json

The default input path is beside the script. Both forms print strict JSON and
write no file. Use normal shell redirection to a NEW filename if desired; do not
overwrite the preserved reference to conceal a discrepancy. The repository has
a separate scripts/check_v09_c02.py with independent numerical reconstructions.

FORMAT
All probabilities, returns, covariance entries, means, exposures, fees and
wealth calculations use fractions. "17/2500" means exactly 17 divided by 2500.
Standard deviations and general correlations are floating approximations,
because their square roots need not be rational. JSON null means that a
correlation is undefined because a marginal variance is zero; it does not mean
a zero correlation. The perfect-pair missing-data counterexample is rational.
Integers used as observation counts and booleans remain normal JSON types.

The module's population_moments, portfolio, common_risk, financed_plan,
sample_moments, sample_report and missing_pair_demo functions retain Fraction
objects internally. run(data) returns their JSON-compatible encoded results.
Pure numeric helpers do not fetch data or estimate unknown population parameters.

CONVENTIONS
R is a simple total return and G=1+R. Returns within a calculation have a common
currency and horizon. Rates are decimals, not percent-number inputs. A variance
of .01 corresponds to a standard deviation .10, or 10 percentage points.
All exposures are measured against positive BEGINNING net wealth. Risky
weights plus signed cash/loan weight equal one. Physical state probabilities
are positive and sum to one; they are not state prices or risk-neutral weights.

The annual supplied population law and the five monthly sample observations
are DISTINCT experiments. The sample is not a draw claimed to be representative
of the Oriel annual distribution. Do not annualize or merge them silently.

POPULATION AND REDUNDANCY
Four equally probable annual states arise from independent F,E signs:
RA=.08+.12F+.04E; RB=.06+.04F-.08E; C holds half A and half B.
The actual input rows, in A/B/C order, are:

F+ E+    .24    .02    .13
F+ E-    .16    .18    .17
F- E+    .00   -.06   -.03
F- E-   -.08    .10    .01

Means are .08, .06, .07. Covariance in squared decimal returns is:
[ .016   .0016  .0088 ]
[ .0016  .008   .0048 ]
[ .0088  .0048  .0068 ]

Rank is two; (1,1,-2) is a zero-mean zero-payoff exposure. C is a redundant fund,
so all matrices need not be invertible. There is no invented inverse or ridge.
P1 weights (.25,.75,0) give state returns .075,.175,-.045,.055,
mean .065 and variance .0061. Its loss probability is 1/4.
P2=(.5,.5,0), P3=(0,0,1) and P4=(.25,.25,.5) have exactly the same state
returns, mean .07 and variance .0068. More labels do not change their exposure.

The model forms covariance from weighted centered outer products. For every
exposure a, a' Sigma a is a weighted sum of squared centered portfolio returns.
Its positive-semidefinite property follows from that construction rather than
a numerical search over arbitrary test weights. rank() uses exact elimination.

COMMON RISK AND CONCENTRATION
A separate family has mean .06, common loading one, factor variance .01 and
pairwise uncorrelated residual variance .04; residuals are uncorrelated with
the factor. Independent signs with amplitudes .10 and .20 give one exact
finite-state realization. Equal weighting yields .01+.04/N:
N=1: .05; N=4: .02; N=25: .0116; N=100: .0104.
The common variance floor is .01. Weights (.7,.1,.1,.1) give H=.52,
effective residual name count 25/13 and variance .0308.
This name-count interpretation is limited to the stated long-only,
equal-residual-variance, uncorrelated-residual model. It is not a complete
measure of economic diversification or proof that every common risk is unhedgeable.

FINANCING CONTRACT AND EXACT CASH
Initial wealth is 100. Cash earns 3%, borrowing costs 6%, and a stock-borrow fee
of 2% of INITIAL short notional is paid at date 1. All short proceeds can be
reused under the expressly fictional contract. Asset total returns include
distributions owed by short sellers. Rates/fees are deterministic; there are
no taxes, other fees or interim margin calls. Loans have full recourse.

Scaled underlying: buy 150 of C, borrow 50, repay 53.
Rp=1.5 RC-.03; mean .075; variance .0153.
Terminal wealth is 116.5,122.5,92.5,98.5.
Using the lending rate for this loan would give a wrong mean .09.

Long-short: buy 120 A, short 40 B, retain 20 cash; initial net value is 100.
Pay a fee .8 at the horizon.
W1=120(1+RA)-40(1+RB)+20(1.03)-.8.
Rp=1.2 RA-.4 RB-.002; mean .07; variance .022784.
Terminal wealth is 127.8,111.8,102.2,86.2.
Gross risky exposure is 1.6, net risky exposure .8, cash weight .2.

The output shows every terminal wealth. A negative value in a stressed variation
is explicitly flagged as a recourse deficit; it is not floored at zero or
claimed to be funded by an available outside injection. Limited liability,
restricted short proceeds or interim liquidation need another payoff model.
The helper therefore rejects changes to those contract flags. Its documented
funding-rate domain is nonnegative lending no greater than borrowing.

SAMPLE ESTIMATION AND PRECISION
The five aligned monthly X/Y returns are:
(-.04,-.02),(.02,.04),(.08,.02),(-.02,0),(.06,.06).
Both means are .02. Using all rows and n-1=4 gives:
S=[[.0026,.0012],[.0012,.001]].
Fixed portfolio weights (.4,.6) give sample variance .001352
and standard deviation approximately .03676955262170047.
Under an explicitly hypothetical iid vector sampling model, estimated
mean variance is .0002704 and mean standard error .016443843832875574.
The observations themselves do not establish iid behavior or a future .02 mean.
Treating the five rows as an empirical distribution with probability 1/5 gives
variance .0010816, a different estimand from the n-1 sampling estimator.
Sample portfolio weights are fixed, not chosen to maximize an in-sample fit.
Serial dependence, selection and changing distributions require additional analysis.

MISSING-DATA COUNTEREXAMPLE
The six-row panel has no complete three-asset row. U/V observed pairs move
together, U/W pairs move together, and V/W pairs move oppositely. Each pair
contains exactly two observations, equal positive sample variances and perfect
signed correlation. The pairwise correlations are +1,+1,-1, giving:
C=[[1,1,1],[1,1,-1],[1,-1,1]].
For the fully invested witness (-1,1,1), a' C a=-3.
This cannot be a joint correlation law. Multiplying C by .01 as a proposed
covariance at common 10% volatility gives impossible variance -.03.
The routine deliberately verifies the perfect-pair demonstration's assumptions
and a negative witness. It is NOT a general pairwise estimator or imputation
algorithm. In particular, a case copy that no longer has these properties is
rejected rather than still called the same impossibility demonstration.
The normal sample routine requires complete common-date rows and rejects nulls.
Complete-case deletion preserves PSD but need not remove missingness bias.

SUPPORTED BOUNDARIES
Inputs are exact integers or rational strings; booleans, floats and missing
values are not silently accepted as ordinary returns. Unlevered asset returns
must be at least -1. Population probabilities must be positive and sum to one.
Weights must satisfy their stated budgets; sample dates and asset labels must
align; at least two complete sample rows are needed. Common-risk variances are
nonnegative; its concentration comparison has long-only weights summing to one.
A constant return is allowed and produces undefined correlation, not a crash.

The numeric routines recompute supported state/weight/funding variations and
always display the actual exposures. Portfolio identifiers P1-P4 do not encode
a fixed numeric policy in the implementation. Update the explanatory assumptions
and provenance when changing a case copy. Keep the same return horizon, payoff
rights and separate population/sample interpretations. This is not a general
brokerage engine, missing-data repair tool or portfolio optimizer.

REVIEW AND LIMITS
The focused checker independently uses factor loading products, pairwise
state/time differences, enumerated common/idiosyncratic shocks and dated
gross cash obligations. It checks the chapter's exercise anchors, documented
boundary failures, full reference agreement, manifest and portable execution.
Exact comparisons are used for rational results. Floating square-root outputs
are checked with 1e-12 absolute/relative tolerance, not decimal-string equality.

The chapter links inspected MIT portfolio and covariance teaching material and
official covariance documentation. Those references support methods, not these
invented observations or financing terms. A finite-state model, coherent sample
matrix and passing code checks do not certify real future risk, actual short
availability, learner mastery or external human review.

