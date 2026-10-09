VOLUME 10 CHAPTER 9 — ORIOLE GREEKS, VOLATILITY AND FUNDED HEDGES
Original synthetic teaching laboratory, 9 October 2026

Purpose
-------
Reproduce fixed-input vanilla Greeks, signed exposures, controlled spot Taylor
error, implied-volatility inversion, finite-strike price tests, a financed delta
hedge and a supplied-weight variance calculation. This is a deterministic model
worksheet. Inputs are authored illustrations, not observed quotes, a generated
diffusion sample, an execution strategy recommendation or empirical validation.
The complete derivations, five worked cases and ten solved exercises are in
v10-c09.html. All amounts are currency units (CU), stock prices CU per share,
times years, rates continuously compounded per year, volatility per square-root
year. A contract covers one share before the signed quantity and multiplier.

Run independently
-----------------
Requires Python 3.9 or newer and only its standard library. No network, package
installation, environment variables or repository-specific imports are used.
Copy all five files into any directory, including a directory containing spaces:

  python3 v10-c09-analysis.py --input v10-c09-inputs.json
  python3 v10-c09-analysis.py --input v10-c09-inputs.json --output result.json
  python3 -O v10-c09-analysis.py --input v10-c09-inputs.json --output result-O.json

The first command prints JSON only. File-output mode prints nothing. --input is
required; all paths are explicit. Input validation finishes before output is
opened, so invalid data do not overwrite an existing destination. File-system
write failures are operating errors, not financial-domain statuses. The model
does not validate its manifest at runtime; see the integrity instructions below.
Import with runpy.run_path or importlib and call run(data) for the quiet public
API. It returns a JSON-safe dictionary without changing data. Internal helpers
are implementation details and are not a separate validated public API.

Schema and bounded scope
------------------------
Every object must contain exactly the following named fields. Unknown or missing
fields fail. JSON booleans and strings are not numeric values; NaN, Infinity,
duplicate object keys, numeric overflow and values beyond the limits fail with
ValueError through the API or a nonzero CLI exit. There are no validation asserts,
so -O preserves the validation. schema must be integer 1; provenance is a string.
Bounds below are inclusive unless specified otherwise.

Root: schema, provenance, base, position, shock, iv, smile, hedge, variance_account.

base: spot [1,10000], strike [1,10000], tau [0.0001,5], rate [-0.2,0.2],
  dividend [0,0.2], sigma [0.0001,3]. Base and perturbed Greek calculations remain
  in this interior. Negative interest is supported. dividend is proportional
  continuous yield, not a fixed cash dividend. rate is the common funding rate.
  The chapter's mathematical inverse theorem also discusses boundary contracts;
  the public lab deliberately rejects base tau=0, spot=0 or sigma=0. Internally,
  boundary prices needed at maturity or at a bisection endpoint are computed as
  max(A-H,0) and its parity partner, with all smooth Greeks null.

position: contracts is an integer in [-10000,10000]; multiplier [1,10000];
  stock_units [-100000000,100000000]. Signed option units = contracts*multiplier.
  Positive quantities are long. Delta includes stock; gamma, vega and calendar
  theta do not include a funding account. Buying stock_trade_to_zero_delta shares
  offsets the current delta. Its cost still needs financing in a trading account.
  Vega is reported per unit sigma and per volatility point (0.01 sigma). Calendar
  theta is per year, with all other inputs held fixed; it is not expected profit.

shock: spot_change [-1000,1000], vol_change [-1,1], elapsed [0,1]. New spot,
  sigma and tau must still satisfy base limits. Approximate change = delta*dS +
  gamma*dS^2/2 + vega*dSigma + calendar_theta*elapsed. The full changed contract is
  independently repriced. The reported analytic third-derivative bound covers
  only the separate spot-only Taylor residual. Mixed/time/volatility second-order
  terms are omitted from the abbreviated approximation, so the spot-only bound
  is not claimed to bound that approximation's entire mixed residual.

iv: call_price [0,10000], sigma_cap [0.01,4]. The quote must also lie in its
  individual interval [L,A], A=spot*exp(-dividend*tau), H=strike*exp(-rate*tau),
  L=max(A-H,0). A quote outside that interval rejects the input. The cap is only
  an inversion search bound; it need not equal the base Greek-domain sigma cap.
  Price resolution is 1e-11*max(1,A,H). Report statuses:
  * zero_volatility_limit: exact quote L, sigma=0; not a positive solution.
  * upper_bound_has_no_finite_implied_volatility: exact quote A; sigma=null.
  * unresolved_near_price_boundary: a strict interior quote is within resolution
    of either endpoint; sigma=null. Mathematical uniqueness may still hold.
  * root_above_declared_sigma_cap: strict quote exceeds computed cap price;
    sigma=null, price_at_cap supplied. This is not a global nonexistence claim.
  * bracketed: bisection stops at volatility width <=1e-10, with at most 80
    iterations. Endpoints, endpoint prices, price residual and local inverse-vega
    scale are reported. If vega <=1e-12 the inverse scale is null. The bracket is
    numerical, not outward-rounded interval arithmetic or quote confidence.
  Bisection never declares convergence solely from a small price residual.

smile: spot, tau, rate, dividend obey the corresponding base bounds. strikes and
  call_prices are equal-length lists with 3 to 12 entries; strikes [1,10000] must
  be strictly increasing and prices lie in [0,10000] and individual quote bounds.
  Each quote is inverted using iv.sigma_cap. One unbracketed/cap status does not
  prevent the separate price tests. Adjacent slopes must lie in [-exp(-r*tau),0]
  and normalized weighted butterfly costs must be nonnegative. A floating-point
  tolerance of 1e-12 is allowed in these screens; a difference below this scale
  is not an economically certified equality. These are finite same-expiry
  necessary tests, not a complete full-surface or dynamic no-arbitrage theorem.

hedge: times and spots are lists of equal length 2 to 25; times in [0,5] strictly
  increase, first time is exactly 0, final time exactly base.tau, first spot
  exactly base.spot, all spots [1,10000]. At every interior reset the remaining
  tau must be >=0.0001. interior_fee lies in [0,0.05]. Begin with model premium C0,
  delta shares and bank C0-delta*S0. Between resets dividends are reinvested in
  shares continuously and without fees, growing shares by exp(q*dt); bank grows
  by exp(r*dt), including negative balances. At each interior date rebalance to
  fixed-model-sigma delta and finance the entire stock-trade cash through bank.
  The fee account additionally pays interior_fee*abs(stock_trade_cash), and
  those fees accrue at r thereafter. Initial purchase, reinvested dividends and
  terminal liquidation have no fees in this deliberately stated convention.
  The costless account and fee account use identical delta targets. At maturity
  liquidate and subtract the payoff. Wealth is never silently reset to the option
  mark. A finite reset strategy is not exact continuous-time replication.

variance_account: durations, discounted_cash_gammas and actual_sigmas are
  equal-length lists of 1 to 24 entries. Durations [0.0001,5], weights [0,1e6],
  actual sigmas [0,3] and model_sigma [0,3]. The supplied weight represents
  (1/2)*exp(-r*t)*Gamma*S^2; output sums duration*weight*(model_sigma^2-actual^2).
  It is exact algebra for the supplied piecewise-constant weights, not proof that
  those weights and variances arise from an actual joint diffusion path. The
  separate hedge ledger has discrete resets and cannot be equated to this sum.

Arithmetic, numerical evidence and limitations
----------------------------------------------
Prices and numerical Greeks use IEEE double precision. OTM prices are evaluated
first and their ITM partners obtained from parity. Normal probabilities use erfc.
Extreme tails can underflow to zero even when the mathematical price or vega is
strictly positive. The status string identifies this possibility; inverse-domain
branches do not manufacture a positive volatility from a numerically flat price.
Displayed precision is arithmetic precision, not market uncertainty.

The repository checker scripts/check_v10_c09.py uses an independent integral of
the terminal lognormal payoff, split at the strike, with composite Simpson
integration. It integrates normal z from -12 through max(12,sigma*sqrt(tau)+12);
the latter protects the tilted stock-payoff tail. Discounted omitted tails are
bounded by 2*(A+H)*Phi(-12), below 1e-25 CU across this bounded domain. Grid
doubling is a numerical diagnostic, not a rigorous global Simpson error proof.
Price comparisons use absolute tolerance 2e-6 for stress cases; typical prices
agree more closely. Finite-difference Greek comparisons use independent integral
prices and specified truncation tolerances, not saved output as their sole oracle.
Independent funded cash sums, parity/PDE identities, an ATM inverse anchor,
quote/fee/position/path interventions and exact rational worksheets give separate
checks. The saved output is an additional reproducibility check.

Representative expected results
-------------------------------
Call 8.288309863734; put 11.849649159553. Call delta 0.479279867451,
gamma 0.0158045335314, vega 40.965350913399 per unit sigma, calendar theta
-7.168510611644 CU/year. Short 1500 units need 718.919801176424 shares to neutralize
delta; vega per volatility point remains -614.480263700986 CU.
Spot-only 120->123: Taylor change 1.508960003244, exact change 1.508398766509,
analytic remainder bound 0.000822668633. Mixed change: approximate 2.094993796264,
exact 2.105551642381. Invented quote 11.05: sigma 0.307377471676.
Smile prices 14,11,5: vertical test passes; normalized butterfly cost -1.5 fails.
Funded hedge final 130: ideal error 2.237604281320, fee error 2.138138035124.
Final spot 95 only: ideal -0.696468323447, fee -0.795934569643.
Supplied variance weights: discounted error 1.5625; reversed variance order
produces -2.1875 with the same unweighted time-average variance 0.065.

Exercises for interventions
--------------------------
Reverse contracts and verify all option sensitivities reverse. Add the reported
stock trade and verify only delta changes. Set fees to zero or double them and
reconcile the dated cost independently. Change only the final stock price and
check that earlier trades remain identical. Lower the middle smile quote to 9,
then explain why passing the finite screen does not identify dynamics. Lower
the inversion cap to 0.2 and interpret its status. Test exact/near price endpoints.
Reverse the two actual variance values and explain the weighting distinction.

Integrity and review
--------------------
v10-c09-manifest.json records SHA256 and byte counts for the input, model, output
and this README. SHA256 detects changes; it does not prove the finance is correct.
These five files are sufficient for standalone execution. The repository author
record additionally binds the manuscript, checker, source proposals and manifest.
Author and machine-assisted peer/coordinator checks are distinct from independent
human academic certification, empirical validation or a guarantee of error-free
hedging. No external data, credentials, randomness or network is required.
