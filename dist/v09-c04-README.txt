CALDERA MARKET — CAPM EQUILIBRIUM LAB
Original synthetic teaching economy, 8 October 2026.

PURPOSE
Reconstruct investor optimality, market clearing, covariance pricing and the
difference between population pricing restrictions and sample/proxy regressions.
No data are observed security returns; no statistical or investment claim about
an actual market follows. The benchmark evaluates candidate prices. It does not
solve a general equilibrium price system or estimate an optimal investment policy.

FILES AND OFFLINE USE
Save these five files together:
  v09-c04-inputs.json    Prices, final payoffs, supplies, investors and experiments.
  v09-c04-analysis.py    Complete standard-library exact benchmark.
  v09-c04-output.json   Preserved full rational output.
  v09-c04-manifest.json SHA-256 and byte sizes of the other four assets.
  v09-c04-README.txt    This guide.

Run:
    python3 v09-c04-analysis.py
    python3 v09-c04-analysis.py v09-c04-inputs.json

The default input is located beside the script regardless of working directory.
The optional argument names a case copy. Both commands emit JSON only, write no
files and need no installation, network or credentials. Import is quiet; run(data)
returns a JSON-compatible object. Fractions such as "23/15" are exact strings.
Variance is in squared DECIMAL return units: "1/100" means variance 0.01, hence
10% standard deviation. The lab reports variances rather than rounded square roots.

MODEL AND TIMING
There are three risky claims A/B/C and four final states. All prices are 100 CU;
all final payoffs, including liquidation/distributions, arrive at date 1 exactly
one year after purchase. No interim cash, fees or taxes exist. Simple total
return is R=final payoff/price-1, with gross return G=1+R. The initial prices,
positive shares outstanding 3/2/1 and investor wealth 200/400 imply market value 600
and beginning market weights (1/2,1/3,1/6). Weights are fractions of beginning
wealth; signed cash/borrowing is included in every full investment budget.

Investors share physical state probabilities (1/4,1/4,1/4,1/4). Their objective is
E[R_p]-(gamma/2)Var(R_p), assumed directly for this model. Gamma 2 and 8 are
preferences over return variance, not dollar-wealth risk aversion coefficients.
All claims are divisible, short positions are allowed, and everyone can borrow
or lend any amount at the same risk-free rate 2%. The cash claims have zero net
aggregate supply; all modeled wealth is represented by the risky market claims.
No nontraded income, other assets, funding spread or outside wealth is present.

These assumptions are deliberately explicit. Mean-variance ranking is not
automatically an expected-utility representation for arbitrary distributions,
and zero net risk-free supply is a chosen economy, not a universal CAPM premise.
The covariance is SPD, giving a unique optimum under the strictly concave
quadratic objective. The fixture has a strictly positive pricing checksum too,
so the stated candidate prices do not conceal an arbitrage inconsistency.

BASELINE ANCHORS
Physical state returns:
     A        B        C       value-weighted market
   -12%      -9%      30%             -4%
    -2%       1%     -20%             -4%
    18%      21%       0%             16%
    28%      11%     -10%             16%

Means are 8%/6%/0%; the market mean is 6%, variance 1/100 and excess mean 4%.
The covariance matrix is:
  [ 1/40,   3/200, -3/200 ]
  [ 3/200,  1/80,  -1/100 ]
  [-3/200, -1/100,  7/200 ]
Its leading principal minors are 1/40, 7/80000 and 9/4000000, all positive.

With e = mu-rf*1, optimal risky exposures are x = Sigma^-1 e/gamma. Here
Sigma^-1 e = (2,4/3,2/3). Investor H1 holds risky weights (1,2/3,1/3) and cash -1;
H2 holds (1/4,1/6,1/12) and cash 1/2. Their risky share holdings sum to (3,2,1).
H1 borrows 200; H2 lends 200; they exchange 204 at date 1. Wealth shares are 1/3 and
2/3, so T = sum(wealth share/gamma) = 1/4 and aggregate covariance price lambda = 4.
The weighted risky demands equal the market weights; net cash weight is zero.

Beta relative to the TRUE market is (3/2,1,-1/2), and alpha is zero for all claims.
Residual variances are 1/400, 1/400 and 13/400. The high-variance claim C has a
negative expected risk premium because it offsets market exposure on average;
it does not pay more in every bad-market state. The residuals are orthogonal to
the market, not assumed mutually independent. Weighted residuals cancel exactly
in the market portfolio.

The supplied zero-beta portfolio is 1/4 A+3/4 C: returns (19.5%,-15.5%,4.5%,-0.5%),
mean 2%, variance 1/64, beta 0. It is risky despite earning the risk-free expected
return. Market/cash portfolios use their explicit risky allocation y and cash 1-y.
For y>=0, mean=2%+4%y and variance=.01y^2 describe the efficient positive-premium
capital-market-line ray in this unconstrained economy. A negative y lies on the
lower ray, not the efficient positive-premium CML. Asset A has mean 8% but variance
.025; 1.5 times the market plus cash -0.5 has the same mean and variance .0225.
For edited inputs, the CML flag also requires zero population alpha for every
available risky claim. A positive market premium alone does not make that ray
the efficient frontier. The market/cash mean and variance remain calculable when
the flag is false; their efficiency must not be inferred from those two numbers.

PHYSICAL PROBABILITIES AND PRICING CHECKSUM
All physical means and covariances use p=1/4. Separately, the lab constructs the
candidate m_s=[1-4(R_M,s-.06)]/1.02. For this fixture it equals 70/51, 70/51, 10/17,
10/17. The normalized candidate pricing weights q_s=p_s*m_s*1.02 are 7/20, 7/20,
3/20, 3/20. They are positive, sum to one, and their expected final payoff for
every 100-CU claim is 102. Hence each price equals E_q[payoff]/1.02=100.

These pricing weights are not physical probabilities. Using physical expected
payoffs 108/106/100 and discounting all three at 2% would give incorrect prices
105.882353/103.921569/98.039216. Under the CAPM the respective physical required
returns 8%/6%/0% instead reconcile their 100 prices. The full state-price and
discount-factor framework is taught in the next chapter; this positive check
merely verifies the consistency of our constructed finite economy.

The code calls the kernel and normalized weights CANDIDATES. An edited economy
may fail one or more claim-price identities; inspect the boolean validity flag
and exact residuals. Positive numbers that fail those identities are not a
valid pricing rule. They must never replace physical probabilities in covariance
estimation just because their label contains the word pricing.

PROXY AND SAMPLE DIFFERENCES
If B alone is called the market proxy, population betas become (6/5,1,-4/5) and
alphas become (3/250,0,3/250), or 1.2%/0%/1.2%. The true-market CAPM still holds.
The proxy is an inefficient benchmark. A zero intercept for B against itself is
an algebraic identity, not an independent test of equilibrium.

The selected eight-observation sequence uses state indices 0, 1, 2, 3, 0, 2, 2, 3.
It is a pedagogical sample, not a simulation or actual history. OLS against the
true market gives sample A beta 23/15 and alpha -11/750, B beta 17/15 and alpha
-13/1500, and C beta -13/15 and alpha 23/375. For A the sample mean is 10.5% and
market mean 8.5%, unlike their population means 8% and 6%. Sampling can therefore
produce an estimated intercept when the population CAPM holds exactly.

The OLS slope uses centered cross-products divided by centered market squares;
using the same n or n-1 covariance divisor cancels. The reported residual_variance
for the sample is the EMPIRICAL mean squared residual with divisor n. It is not
the residual variance estimator with divisor n-2, an alpha standard error, a
significance level or evidence of persistence. No p-value or automatic trading
signal is supplied. Population projections and empirical OLS coefficients have
different evidential status even when the numerical operations look similar.

TWO CONTROLLED FAILURES OF CLEARING
The mean-shift experiment adds 1 percentage point to every state return of the
selected claim A, keeping prices, supplies, wealth and preferences fixed.
Covariance is unchanged. Aggregate risky excess-demand weights become
(3/8,-5/12,1/24), so those candidate prices no longer clear. This is not a newly
solved equilibrium; the common return beliefs would require price adjustment.

The borrowing experiment imposes cash>=0 only on H1. All risky short rights and
other assumptions remain unchanged. A KKT multiplier eta>=0 gives
e-gamma*Sigma*x=eta*1, eta*(sum(x)-1)=0. The unique H1 optimum is (1,0,0), cash 0,
eta 1/100. H2 remains unchanged. Aggregate risky weights are (1/2,1/9,1/18), below
the B/C supplies, and net desired cash weight is 1/3 despite zero net cash supply.
At old prices this economy fails clearing. Merely scaling H1's former 2M position
down to 1M is feasible but not optimal: H1's objective is .055 for A versus .050
for M. The borrowing limit changes the risky mix and breaks the common-fund proof.

EDITING SCOPE AND CODE GUARDS
The input regime label must remain exactly the declared unrestricted/common-rate/
zero-net-cash model; unsupported regime labels are rejected. The borrowing limit
is a separately and explicitly computed experiment. Three assets/four states,
positive physical probabilities, valid payoffs/prices, positive investor wealth/
risk aversion, matching aggregate wealth, SPD covariance and valid selectors are
required. A constant benchmark makes beta undefined and is rejected.

Asset/proxy/constrained-investor selectors and the size of the common return shift
are used dynamically, not silently ignored. Candidate price/payoff/wealth edits
are permitted within the bounded domain, but may report market_clearing=false.
The input's named zero-beta portfolio has an actually_zero_beta check; if you
change its weights or the economy, do not retain the baseline conclusion without
that check. Mean-variance optimization is conditional on the edited opportunity
set; the script never changes prices to force an equilibrium or changes physical
probabilities to force a pricing equation.

SOURCES AND LIMITS
The chapter reuses the already inspected MIT 15.401 CAPM material within its
verified scope. Newly inspected primary sources are Sharpe's 1964 publisher full
text (individual choice and equilibrium/systematic-risk sections) and Fama and
French's 2004 author paper (regression restrictions, proxy testing and model/market
ambiguity). Historical assessments remain dated. No source case or empirical
dataset is copied. All Caldera examples and exercise calculations are original.

Finite-state moment identities and code checks do not establish actual market
efficiency, investment skill, borrowing access or future expected returns.
Nontraded wealth, constraints, differing beliefs, dynamic risks and costs require
different assumptions and sometimes different pricing restrictions. A model's
alpha is conditional on its benchmark; a statistically significant estimate would
still require a model/proxy, data and implementation audit.
