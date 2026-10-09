ALDER DESK — VOLUME 10 PRICING AND RISK TOOLKIT

PURPOSE, CONTRACT AND PROVENANCE
This original synthetic project connects one desk obligation to its curve,
option valuation, numerical diagnostics, funded trading and reserve decision.
No input is a market observation, estimated default frequency, legal opinion
or real trading approval. All amounts are currency units (CU), dates are exact
years from issuance, volatility is per square-root year, and rates are per year.
The instrument is issued at a coupon boundary: no accrued interest is due.

The desk owes the stated coupons and face on the three curve dates, regardless
of the reserve issuer's default, plus ONE put payoff at the FIRST curve date.
Baseline dates are .5,1,1.5; fixed payments3,3,103; put payoff(105-S_.5)+.
The put has no dividends or interim payments. The baseline exercise right is
European. Separate finite-tree comparisons intentionally add Bermudan or all
node exercise, paid immediately at the chosen stopping time; fixed coupons
and face remain unchanged. Exercise uses information available at that node.

Riskless zero claims are assumed tradable at the bootstrapped discount factors.
Log-linear interpolation of discounts between0 and the first date gives one
constant continuously compounded rate for the entire option life. Other curve
segments do not enter that put. The later forward ratios fund the reserve cash
ledger. This is a deterministic curve assumption; quotes alone do not identify
physical rate expectations, term premiums or a stochastic short-rate model.

The equity reference is the constant-parameter, frictionless Black-Scholes
model. The discrete hedge permits fractional short stock, immediate settlement
and bank borrowing/lending at that first-segment rate; proportional stock costs
are then charged explicitly. Margin, haircuts, separate funding spreads, jumps,
taxes, market impact and real execution constraints are not silently included.
The five supplied stock paths are unweighted diagnostic scenarios, not random
observations or a complete stress set. No empirical hedge-loss distribution is
estimated from them.

FILES AND EXECUTION
Keep the five downloaded files together:
 v10-assessment-inputs.json   complete original synthetic input register
 v10-assessment-analysis.py   Python3.9+ standard-library reference implementation
 v10-assessment-output.json   complete baseline output, including dated ledgers
 v10-assessment-README.txt    this standalone contract and execution guide
 v10-assessment-manifest.json byte lengths and SHA256 of the other four payloads

No installation, network, database or chapter module is needed. Run:
 python3 v10-assessment-analysis.py
 python3 v10-assessment-analysis.py --input v10-assessment-inputs.json --output result.json
 python3 -O v10-assessment-analysis.py --input v10-assessment-inputs.json --output result-O.json

The default input is beside the script. Explicit relative paths are relative
to the caller's working directory; absolute paths work from any directory.
Without --output, strict JSON is printed. Explicit output is quiet on success.
Import and run(data) are quiet, preserve the supplied decoded dictionary and
return JSON-safe results. Validation uses explicit exceptions and survives -O.
The CLI rejects duplicate JSON keys and nonfinite constants. A decoded dict
cannot reveal duplicates discarded by an earlier permissive decoder.

Use a fresh output filename. Input or implementation overwrites are rejected.
The whole calculation and JSON serialization complete before output writing;
invalid inputs exit nonzero without replacing an existing output. Files larger
than one megabyte are rejected before JSON parsing. An operating-system I/O
failure during the final write is not promised to be atomic. Financially adverse
but valid inputs produce failed decision gates, not validation exceptions.
The repository checker scripts/check_v10_project.py is an independent oracle,
not a dependency of this portable download. Hashes bind bytes, not correctness.

STRICT INPUT DOMAIN
Every object has exactly its documented keys. Every financial number is a
STRING, never a JSON number or Boolean. Accepted forms are an optional minus,
an integer0 or1-8 digits without leading zeros, optionally followed by1-8 decimal
digits or a slash and a positive1-8-digit denominator. A leading decimal point
is also allowed: ".25" and "-.5". No whitespace, plus, exponent, negative/zero
or zero-padded denominator is allowed. Maximum string length24. Fraction parses
these numbers exactly. Integer counts/indices, names and enumerated labels have
separate type checks. Identifiers match [a-z][a-z0-9_]{0,39} and are distinct
within each list. Bounds below are inclusive unless expressly strict.

Top-level keys: schema,provenance,curve,liability,option,hedge,credit_reserve,
decision. Schema is "v10-assessment-alder-1"; provenance is exactly the supplied
sentence identifying the original synthetic case. These labels do not validate
outside observations or attest to a real authority.

CURVE AND LIABILITY
curve keys: times,instruments,shocks. times has exactly3 values in[.25,3] years;
first time<=1, and adjacent gaps>=.25. instruments has exactly3 objects with
id,cash,price. Each cash list has3 entries in[0,100000]. Row i has diagonal
cash>=1 and zero later entries; earlier coupons may be zero. Price is in
[.01,200000]. Bootstrap discounts must lie in[.25,1.5]. The first-segment
continuous rate must satisfy |r|<=.2. Discount increases/negative rates are valid;
no false universal decreasing-discount requirement is imposed.

shocks has1-6 objects, each id,zero_shifts; three shifts in[-.05,.05] change
continuous NODE zero rates independently: D'_j=D_j exp(-t_j shift_j).
These are immediate valuation scenarios, not a model of future random rates.
liability keys: face in[1,100000] and exactly3 coupons, each in[0,10000]. Face
is added to the last coupon. All these payments remain owed in the credit
reserve default state.

Bond output gives exact cash, discount factors, calibration residuals, dated
PV pieces, simple interval forwards(D_previous/D-1)/year_gap, key-rate dollar
exposures t*c*D, parallel first/second derivatives and duration. Logarithmic
spot rates and finite shocks use floating arithmetic. A two-zero barbell matches
PV and the parallel first derivative at inception. It is a sensitivity comparator,
not the actual cash reserve; the latter buys each stated payment-date zero.
The barbell may need future trading or borrowing to meet a missing middle-date
payment. Full key-rate residuals and finite shocked surplus expose its limits.
The second_order_residual includes both linear and quadratic Taylor terms for
the supplied vector of shifts; it is not an exact nonlinear price change.

OPTION, TREE AND NUMERICAL ANCHORS
option keys: spot,strike,sigma,tree_steps,bermudan_fractions,mc_pairs,seed,
control_beta,quadrature_steps. Spot in[50,200]; strike in[.75*spot,1.25*spot];
sigma in[.1,.6]. Maturity is the first curve time and discount its first node.
The script does not flatten the entire curve at a different maturity's yield.

Analytic output includes put/call, put delta, gamma, vega,d1,d2. Put-call parity
is checked independently. Floating erfc/exp arithmetic may round sufficiently
small tails to zero; no arbitrary-precision tail accuracy is asserted. The
bounded domain excludes extreme initial-contract tails and numerical overflow;
late-life scenario deltas may still round to their zero/one limits.

tree_steps is2-6 strictly increasing choices from4,8,16,32,64,128. CRR uses
u=exp(sigma*sqrt(T/n)),d=1/u,R=exp(r*T/n),p=(R-d)/(u-d); require d<R<u.
European continuation discounts one interval. Bermudan fractions has1-4 ordered
unique values in[0,.75], each landing exactly on EVERY selected tree grid.
Maturity exercise is implicit. American here means every node of that finite
grid, including time0, NOT arbitrary continuous stopping times. Ties continue.
The reference Bermudan fractions0,1/2 permit exercise at0 andT/2 beforeT.
Changing n changes the stock law as well as the available exercise dates, so
price differences across n are not a proof of monotone continuous-model
convergence. Within a fixed tree, adding dates cannot lower value.

All grids report European/Bermudan/American prices, risk-neutral probabilities,
root continuation stock/bank replication, and number of positive exercise
choices. The complete exercise-node list is retained only on the COARSEST grid;
exercise_nodes_complete records this fact. An empty list on a finer grid does
not mean there are no exercise decisions. The root_continuation_hedge is a hedge
for continuation; if root_exercise is true, the holder instead receives the
immediate payoff. It is not an instruction to continue after exercise.

Deterministic quadrature integrates the normal payoff on[-10,min(10,kink)]
using composite Simpson counts n and2n; n=quadrature_steps is even in[32,1024].
The kink is an integration endpoint. It reports both values, their difference,
comparison with analytic price and the omitted-tail bound2*K*D*Phi(-10).
That tail bound follows from the bounded put. The refinement difference alone
is NOT a certified discretization error bound. The separate checker uses
adaptive integration and independent terminal-binomial sums/exhaustive policies.

SIMULATION CONTRACT
mc_pairs is an integer64-4096; seed an integer0-(2^32-1); fixed control_beta
lies in[-2,2]. SHA256 of the ASCII string "alder-project-v1|seed|index", starting
index0, supplies two blocks of52 bits from its first16 bytes. The respective
open-cell midpoints (integer+.5)/2^52 are transformed by Box-Muller cosine/sine.
This finite, deterministic pseudo experiment is reproducible; the generator
is not asserted to supply mathematically exact independent continuous normals.
No global random state is read or modified.

For each ideal standard normal Z, S_T=S0 exp((r-sigma²/2)T+sigma sqrt(T)Z),
Y=D*(K-S_T)+, X=D*S_T and E_Q[X]=S0. Plain and fixed-control estimators use
BOTH Box-Muller normals:2*mc_pairs single-observation units. The control is
Y-beta*(X-S0), with beta fixed before evaluation; beta=-.5 in the baseline.
No in-sample regression or pilot fitting is hidden. Controlled observations
may be negative or unbounded; they are not clipped and receive no bounded-put
Hoeffding interval. A poor permitted beta can increase variance.

Antithetic estimation uses the cosine normal and its negative, averaged as ONE
unit; there are mc_pairs such pair units. Each of the three estimators therefore
uses2*mc_pairs payoff evaluations when run on its own; control and plain share
their computed payoffs. The three estimators overlap and are not independent
replications of one another. Antithetic variance-of-mean comparisons respect the
halved number of units. Reported sample variances use n-1, SE=sqrt(s²/n), and
approximate intervals use mean +/-1.96SE. Under the IDEAL iid normal experiment,
finite second moments justify the fixed-n CLT approximation asymptotically;
a particular seeded interval need not contain the analytic value.

Plain/pair put units lie in[0,KD]. The displayed ideal iid Hoeffding half-width
KD*sqrt(log(40)/(2n)) has at least95% coverage under THAT experiment and a
prespecified n. It does not certify finite pseudo-generator coverage, model
adequacy or an optional stopping rule. No seed search followed by selective
reporting is authorized. Analytic comparison, quadrature difference, sample SE,
contract uncertainty and scenario hedge losses remain separate quantities.

FUNDED HEDGE
hedge keys: times,cost_rate,paths. times has2-9 entries from0 to maturity,
strictly increasing with gaps>=T/16; cost_rate in[0,.01] is a proportional
charge on absolute traded stock notional. paths has1-8 id,spots objects.
Each path has one spot per hedge time, starts at S0, and stays in[.5*S0,1.5*S0].
No probabilities are supplied. Interior observations determine the newly held
analytic put delta at positive remaining life; the maturity holding is zero
because stock is liquidated before the option cash payment.

At entry bank=P0-delta0*S0-entry_cost. Between dates bank accrues at r. At each
date subtract (new_delta-old_delta)*S plus cost_rate*abs(delta_change)*S.
Liquidation is included as the final delta change, then subtract the put payoff.
Each path reports the complete zero-cost and with-cost ledger, terminal errors,
and time-value-adjusted transaction costs. Their difference equals terminalized
costs because delta does not depend on the account balance. A negative terminal
error is an issuer funding deficit. No cash is injected to reset wealth to the
option's marked value, and no maturity Greek is evaluated at zero remaining life.

CREDIT RESERVE AND DATED BORROWING
credit_reserve keys: pricing_default_probability in[.001,.999], default_index
and settlement_index integers0-2, settlement>=default, recovery_fraction in[0,1].
The finite state model has survival and default only. Default occurs immediately
BEFORE the coupon at the selected date: all earlier coupons pay, later coupons
and face do not. The sole recovery is face*recovery_fraction at settlement.
No coupon recovery, counterparty second default, collateral closeout, intensity
process or observed physical probability is inferred.

Risky PV is the stated Q-mixture of dated survival and default PVs. The default
funding account begins at zero and receives reserve cash minus required cash.
Between payment dates its balance accrues by D_previous/D_current. Negative
balances expose required borrowing; they do not establish that a credit line
exists. This benchmark borrowing uses the same deterministic riskless curve.
If such borrowing is unavailable, the first negative date is already a failure.
An added borrowing spread would further increase the displayed deficit and
must be budgeted separately. The project guide solves a200bp bridge-spread
transfer; that extension is not silently active in the baseline code.

DECISION AND BASELINE
Decision keys: requested_exercise in european/bermudan/american,
requested_reserve in matched_zeros/risky_bond, requested_quote in[0,500000],
max_tested_terminal_loss in[0,1000], max_mc_standard_error in[.0001,10], and
max_tree_abs_error in[.000001,10]. These are fictional teaching controls.

The frictionless model quote is riskless fixed-liability PV plus analytic put.
It excludes fees and scenario-loss capital. The actual selected reserve costs
that riskless PV for matched_zeros, or the risky reserve PV for risky_bond.
The reserve budget is max(riskless fixed-liability PV, selected purchase PV):
an expected saving cannot reduce the conservative floor, while any selected
reserve premium must be financed. Decision output selected_reserve_pv and
reserve_budget_pv are exact rational strings; reserve_budget_rule states this
maximum. The frictionless_model_quote remains the riskless reference.

Let e_min be the worst with-cost hedge error over supplied paths, and L the
allowed terminal loss. Additional initial cash b=D*max(0,-e_min-L) offsets the
tested deficit above L. The quote_with_tested_buffer threshold is
reserve_budget_pv+analytic_put+b. It funds the SAME delta policy; it is not a
bound on unsupplied paths or an optimal hedge/market price. Future/default-only
reserve excess cannot fund its initial purchase or a survival-state hedge loss.

All five gates must pass: European requested rights; every declared reserve
payment funded without injection (matched zeros always meet this by contract);
quote at least the tested-buffer threshold, with a1e-10CU floating comparison
allowance; controlled sample SE within the stated budget; and finest European
tree absolute difference from the analytic European price within its budget.
Gate thresholds on numerical diagnostics are case choices, not proof of a
specified future error probability. A requested early-exercise contract remains
outside the European MC/hedge reference even if its tree price is available.

Baseline fixed PV99.52, put8.688302035, frictionless quote108.208302035.
Credit reserve PV93.502 does not fund the same cash in default. The round-trip
hedge error is-11.955681689 with costs; allowing1CU tested terminal loss requires
10.736568055 additional initial cash and a118.944870090 quote. Requested108.5
fails reserve coverage and loss-budget gates. Matched zeros and quote119 pass
only the declared classroom demonstration gates, not real trade approval.

A focused boundary case sets coupons to zero, default_index=settlement_index=0
and recovery_fraction=1. Riskless PV is91; default PV is98, so selected risky
PV is.9*91+.1*98=91.7. apparent_initial_saving is signed and here equals-.7.
The reserve covers all declared dates, but the initial funding threshold is
111.124870090400. Quote110.5 fails funding alone;111.12487009 also fails, while
111.12487010 passes all five gates. Selecting matched_zeros costs91, lowers
the threshold to110.424870090400, and permits110.5 under the same limited rules.

LEARNER DELIVERABLES AND LIMITS
The accompanying project fragment supplies the contract register, eight linked
work packages,100-point five-domain rubric, complete instructor guide and new
transfer tasks. Submit independent code, a decision memo, full cash/evidence
ledgers, separate error categories, intervention outputs, limitations and an
oral defense. Preserve the baseline and record changes. All financial models
and distributions are assumptions; exact code and calibration do not prove
that they describe a real market or that a borrower can obtain funding.
