ILEX FACTOR RESEARCH DESK — VOLUME 9, CHAPTER 6
Original synthetic teaching package, 8 October 2026.

Purpose and files
This is a small reproducible companion to factor models and empirical asset
pricing. It distinguishes statewise spanning, priced residual risk, conditional
diversification arguments, sample regression and an implementable cash ledger.
The four sections are SEPARATE constructions, not observations from one economy.
No market data, actual cost quote, return forecast or empirical evidence is used.

Keep these five files in one folder:
  v09-c06-inputs.json    Exact inputs, dates and behavioral conventions.
  v09-c06-analysis.py    Standard-library Python calculation.
  v09-c06-output.json    Complete preserved baseline output.
  v09-c06-manifest.json  SHA-256 and byte counts for the other four files.
  v09-c06-README.txt     This execution, method and boundary guide.

From any working directory run:
  python3 /your/path/v09-c06-analysis.py

Or pass a separately edited input copy:
  python3 /your/path/v09-c06-analysis.py /your/path/case-copy.json

The script resolves the default input beside itself. It prints strict JSON only
and performs no writes, network calls, installations or account operations.
To preserve a new result, redirect stdout to a NEW file. Import is quiet and
run(data) returns a JSON-compatible dictionary without printing. The repository
checker is separate; the downloadable model needs no repository infrastructure.

Units and representation
Money and most statistics are exact reduced rational strings. For example,
"1/250" means 0.004, or 0.4%, in a return field. It is not 1.250 percent.
Input economic numbers must be integers or decimal/rational STRINGS. Binary
JSON floats and booleans used as financial numbers reject. Dates and counts are
integer fields. The only approximate output numbers are explicitly named
square-root bounds. Compare them with 1e-12 absolute/relative tolerance.

JSON null for r_squared_with_intercept means the usual centered intercept-based
R-squared is not defined/reported for that specification. In particular, the
no-free-intercept cross-sectional fit reports residuals and SSE, not a misleading
ordinary intercept-based R-squared. Its residual mean square is descriptive and
does not supply the uncertainty of estimated risk prices.

One-period pricing case
Independent equiprobable signs U,V,E create all eight states. Rf=51/50 is the
SAFE GROSS RETURN. Each safe and factor fund initially costs one CU. An excess
factor f is a zero-cost terminal payoff per reference CU, not a rate on zero
initial equity. The factor funds pay G1=Rf+f1 and G2=Rf+f2.

The positive kernel is m=(1-U/4-V/5-E/10)/Rf. The factor premiums are DERIVED from
kernel coefficients and shock scales, not independently estimated:
  f1=3/100+(3/25)U; f2=1/50+(1/10)V.
The minimum kernel numerator is 9/20. E[m]=1/Rf and both E[m*f] equal zero.
Physical probabilities are 1/8; state prices are m/8 and are not probabilities.

Claim A pays the full gross X_A=Rf+(3/2)f1-(1/4)f2. Its safe replica weight is
-1/4 and its price is one. Expected excess return is 1/25. A clone of this SAME
PAYOFF is quoted at 49/50. Long the clone, short 3/2 Fund 1, long 1/4 Fund 2 and long
27/100 safe units costs zero and pays 51/2500 in every state. The example permits
unrestricted signed holdings with no frictions; the clone quote violates the
otherwise consistent pricing rule.

Claim B is separately fairly priced at one and has excess payoff
  1/250+(3/2)f1-(1/4)f2+(1/25)E.
Its residual is orthogonal to the two included factors but covaries with m.
The resulting alpha 1/250 is exactly -Rf*Cov(m,residual), not free arbitrage.
Hedging the factors leaves 11/250 or -9/250. The price of each full claim is one.
The code reports both statewise and expected pricing restrictions and a Cauchy
bound on the residual alpha.

Allowed pricing edits: safe gross, affine-kernel coefficients, positive factor
shock scales, exposures, nonnegative residual scale and a clone quote in (0,1).
Derived premiums/alpha move coherently with the kernel. The sum of absolute
kernel coefficients must be below one; all included fully paid long payoffs
must remain nonnegative. This is not a general market-calibration or arbitrary
state-probability engine. The eight-state law and frictionless contract are
guarded in the convention string.

Diversification case
For N independent equiprobable signs, zero-cost z_i=sigma*(a+E_i) with sigma=1/5
and a=1/10 have a positive pricing kernel
  m_N=(1/Rf)*product_i(1-a*E_i).
Independence gives E[m_N*z_i]=0 and E[m_N]=1/Rf. Their average has expected payoff
1/50, residual variance 1/(25N) and worst payoff -9/50 for every finite N. Loss
probabilities are computed by exact binomial counts, not simulation. At N=4 the
probability is 5/16. Small variance has not eliminated all loss states.

The squared SDF coefficient of variation is (1+a*a)^N-1. It grows with N, so this
family does NOT satisfy the separately supplied hypothetical UNIFORM bound K=1/2.
Were such a bound imposed, |alpha_N| could be at most K*sigma/sqrt(N). At N=100
that would be 1/100 and would exclude the mean 1/50. The program labels the bound
as hypothetical; it never asserts that these incompatible assumptions all hold.

Allowed edits: positive residual scale, safe gross and hypothetical bound,
tilt strictly between 0 and 1, distinct integer counts 1 through 100. Product formulas
avoid enumerating 2^N states. The lab does not prove an unrestricted infinite-market
APT theorem or turn a low-probability finite loss into sure arbitrage.

Empirical calculation case
The first eight monthly rows are all combinations of x,z,h in {-1,+1}. They were
constructed as f1=.01+.02x; f2=.015+.01x+.02z;
  y=.002+1.25f1-.5f2+.005h.
These are synthetic sample observations, not a time-series-generating claim.
The input contains actual factor/outcome rows; the estimator does not use the
generating coefficients. The two-factor OLS coefficient vector is
  [1/500,5/4,-1/2], SSE 1/5000, centered SST 21/5000, R-squared 20/21.
With only factor 1 it is [-3/1000,1], SSE 1/1000, R-squared 16/21.
The omitted-factor slope Cov(f1,f2)/Var(f1) is 1/2. Full-model residual mean square
with 5 degrees of freedom is 1/25000; it is not an alpha standard error.

A separate summary for four test assets supplies PRIOR-WINDOW beta estimates
[(1,0),(0,1),(1,1),(2,-1)] and mean excess returns [.014,.020,.028,.006] over the
SAME eight evaluation months. Their descriptive no-free-intercept second pass
has lambda [3/250,9/500] and residuals [1/500,1/500,-1/500,0]. The factor means
are [1/100,3/200]. Estimated second-pass slopes need not equal those sample means;
no population exact-spanning restriction or inference claim is imposed here.

OLS solves a small exact rational system and rejects deficient rank. All residual
normal equations are returned. Numerical observations, prior-window betas and
evaluation means may be edited, retaining eight increasing integer sample periods,
matched two-factor dimensions, full rank and positive residual degrees of freedom.
The cross-section has no freely estimated intercept. For a real floating-point
panel, use numerically stable methods plus a defensible inference design; this
script supplies neither empirical standard errors nor causal identification.

Factor-construction cash case
Four assets A-D start at prices 100. Over four model months, a signal known at
each trade ranks all four assets. Long the top two at 50 CU each and short the
bottom two at 50 CU each. The reference long/short notionals stay 100/100, rather
than growing with equity. Start collateral 100, cash interest zero, no distributions,
no taxes, short proceeds reusable, no intramonth margin calls. Charge 0.1% on every
CU actually bought or sold and 0.1% on each period's opening short notional.
Close every position at the final date and pay the liquidation cost.

The implementation carries actual SHARES and prices, calculates the traded
quantity changes, debits execution/borrow cash and reconciles equity at every
date. It rejects an input requiring a cash loan or nonpositive observed equity;
it is not a margin or insolvency simulator. Endogenous changes between observed
dates are outside this stipulated discrete contract.

Baseline gross factor payoffs per notional: [7/200,7/200,1/25,0]. Rebalance dollar
volumes: [200,405/2,405/2,205]; final closing volume 200. Total traded volume 1010,
trade cost 101/100 and borrow cost 2/5. Gross profit 11 produces final cash 10959/100
and investor cumulative return 959/10000. All final positions are zero.

Account returns divide each period's net profit by its opening equity. Their
growth factors multiply to 1.0959. Fixed-notional factor payoffs cannot simply be
treated as that account's compound return. Hindsight sorting by the return it
purports to earn gives gross spreads [.035,.035,.04,.03] and mean .035, versus the
valid lagged rule's mean .0275. Those hindsight positions are explicitly unavailable,
not another eligible strategy or evidence of predictability.

Allowed edits: unique asset names, distinct ranking signals, signal availability
no later than its integer start date, four matched return vectors above -1,
positive fixed notional/collateral and nonnegative cost rates below 1. The four
consecutive periods, final liquidation, cash terms and ranking contract are
guarded. Ties reject rather than silently applying an unstated tie breaker.
Changing the policy requires changing the model, not just relabeling a string.

Suggested independent reconstruction
- Price every gross claim using physical probabilities and the SDF, then verify
  its actual replicating quantities and initial budget separately.
- Derive the product-kernel expectation by independence. Check its N=4 pricing
  and loss probability by enumerating all 16 states, not by the binomial code.
- Estimate sample slopes from centered two-by-two covariance equations, and check
  orthogonality and omitted-factor identities independently of Gaussian elimination.
- Reconstruct the trading account from signed dollar holdings and drift; compare
  with the code's share/price bookkeeping, including all final liquidation fees.
- Distinguish unavailable signals, deficient rank and negative pricing weights
  from inconvenient results that still satisfy the stated economic domain.

Sources and limits
The manuscript links narrowly scoped primary teaching, factor-definition and
pricing-method references. All examples, laws, input rows, code and problems are
original. No external datasets, licenses, API keys or installations are needed.
The exact arithmetic does not authenticate inputs, establish an empirical premium,
certify skill, remove execution risk or guarantee future performance. This is a
bounded teaching package; broader econometric inference, human review and browser
layout/print review remain separate from its financial arithmetic checks.
