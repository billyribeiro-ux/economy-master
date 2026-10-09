BLACK–SCHOLES AND RISK-NEUTRAL VALUATION — ORIGINAL TEACHING LAB
Chapter v10-c08. Synthetic inputs; no market feed, randomness or dependencies.

PURPOSE AND FILES
The model evaluates European call/put prices, boundary branches, initial hedges,
P versus Q exercise probabilities, discounted dividend accounting, an explicit
constant-normal density tilt, and a funded finite-grid call hedge. Its formulas
are conditional on the model taught in the chapter; numerical checks are not
proofs of stochastic theorems or validation of empirical model adequacy.

Keep these four files together:
  v10-c08-inputs.json     Original eight-case inputs and two illustrative paths
  v10-c08-analysis.py     Standard-library Python 3 model and validation
  v10-c08-output.json     Reference output, full precision
  v10-c08-README.txt      This document
The companion v10-c08-manifest.json binds their SHA256 hashes. The manuscript,
independent checker and source proposals remain in the source book checkout.
All five original cases, original tilt increments and original hedge prices have
been preserved. The symmetric price, deterministic kink and extreme tail are
additional analytical/numerical anchors. All data and problems are original.

STANDALONE EXECUTION
From a folder containing those four files:
  python3 v10-c08-analysis.py --input v10-c08-inputs.json --output result.json
  python3 -O v10-c08-analysis.py --input v10-c08-inputs.json --output result-O.json
Omit --output to print strict JSON to stdout. Omit --input to use the input file
beside the script, not a file relative to the current working directory. Import
with runpy.run_path or importlib and call run(data) for a quiet API returning a
new JSON-safe dictionary. Neither import nor run(data) prints, writes files or
mutates its inputs. No validations depend on assert, so -O retains them. Bad
input raises ValueError before the CLI writes an output. CLI JSON decoding also
rejects duplicate object keys and NaN/Infinity constants. Python's direct API
cannot detect keys that a caller already discarded during its own JSON parse.

From the book checkout, the quiet independent check() is in:
  scripts/check_v10_c08.py
Run it with:
  python3 scripts/check_v10_c08.py
  python3 -O scripts/check_v10_c08.py
Its CLI prints the measured validation summary. check() itself returns the
summary without output or input mutation. It independently integrates payoff
expectations, reconstructs cash flows, tests economically meaningful changes,
checks bad input, verifies artifact hashes and exercises isolated portable CLIs.
It does not certify the source manuscript as accepted; root owns that decision.

UNITS, FINANCIAL CONVENTIONS AND DOMAIN
One European option delivers the payoff on one share, with no early exercise.
Spot, strike, option premium, bank value and dividends are currency units (CU).
Maturity and dates are years. rate, dividend_yield and physical_drift are annual
decimal rates; volatility is per square-root year. physical_drift is the physical
EX-DIVIDEND price drift mu. Expected total return is mu + dividend_yield.
rate is the constant bank borrowing AND lending rate. Dividend yield q is a
continuous proportion of ex-price and all payments can finance trading. This is
not a model of fixed cash dividends, fees, credit or position/funding constraints.

The input must have exactly keys schema, cases, tilt, hedge. schema must equal
"v10-c08-lab-1". cases is a list of 1 through 8 exact-key objects. Their keys are
id, spot, strike, rate, dividend_yield, volatility, maturity, physical_drift.
Unique ids match [a-z][a-z0-9_]{0,31}.

Numeric fields accept ordinary decimal strings, integers or floats whose str()
representation is an ordinary decimal. Booleans are invalid. The accepted
lexical form is an optional minus sign, 0 or 1–6 digits with no leading zero,
and optionally 1–8 fractional digits. No plus signs, exponent notation, spaces,
fractions, commas, NaN or infinity. Strings are preferred for exact decimal
constraints; for example, pass "0.00000001" rather than a float whose str() uses
scientific notation. This is a deliberately finite lab domain, not a universal
production option library. Fractions validate relationships before conversion
to floating point:
  spot:           zero OR [1,1000]
  strike:         [1,1000]
  rate:           [-0.10,0.30]
  dividend_yield:  [0,0.20]
  volatility:     zero OR [0.05,0.80]
  maturity:       zero OR [0.02,5]
  physical_drift:  [-0.30,0.40]
For positive spot and maturity with zero volatility, mu + q must equal r exactly
as a rational-decimal identity. Otherwise the deterministic stock and bank have
a sure return discrepancy under the chapter's reversible trading assumptions.
Changing probabilities cannot repair it. No drift condition is imposed at an
already expired contract or an absorbing zero-price stock.

The tilt object has exactly case_id, intervals, brownian_P_increments. It must
reference a case with positive spot, volatility and maturity. Its two lists have
2 through 8 equally many entries; each interval is in [0.02,5], each increment
is in [-5,5], and intervals sum exactly to that case's maturity. This vector is
an original density-evaluation example, not a random sample.

The hedge object has exactly case_id, dates, prices. It too references a positive
stock/diffusion/horizon case. Its lists have 2 through 20 equally many entries.
Dates are in [0,5], start at zero, increase by at least 0.02 and end exactly at
maturity. Prices are in [1,1000] and start exactly at the case's initial spot.
These original snapshots specify a cash ledger, not a probability distribution.
No claim about typical performance can be inferred from their selected outcome.

OUTPUT CASES
The schema is "v10-c08-output-1". cases maps each case id to:
  prepaid_stock = S exp(-q tau); discounted_strike = K exp(-r tau)
  call, put and their separate model lower/upper bounds
  d1, d2; delta_call, delta_put; gamma; theta_call, theta_put
  call_bank = call - delta_call*S, put_bank analogously
  pde_call_residual, pde_put_residual; put_call_parity_residual
  probability_Q_itm and probability_P_itm for the STRICT event S_T > K
  expected_terminal_stock_P = S exp(mu tau)
  expected_terminal_stock_Q = S exp((r-q) tau)
  expected_discounted_ex_price_Q = S exp(-q tau)
  expected_discounted_dividends_Q = S[1-exp(-q tau)]
  expected_discounted_total_gain_Q = S
  market_price_of_risk = (mu+q-r)/sigma when nondegenerate

Theta means the calendar-time derivative with fixed expiry T, not the derivative
with respect to remaining maturity tau. Gamma is common to the call and put.
All Greeks refer to this fixed-parameter mathematical function, not a calibrated
volatility surface response. probability_Q_itm is Phi(d2), NOT call delta.
No separate put-exercise field is reported: when the terminal law has an atom at
the strike, one minus the strict call-event probability is NOT a strict put-event
probability. In the positive-diffusion interior the equality event has zero mass.

Branch choices, in priority order:
1. expiry: exact intrinsic payoffs; all reported Greeks, hedge bank amounts and
   PDE residuals are null. Strict exercise probability is 1 if S > K, else 0.
2. absorbing_zero: call zero, put discounted strike. Reported spot derivatives
   are RIGHT-HAND LIMITS of the initial-spot value family (0 and -exp(-q tau));
   they do not identify unique holdings for an identically zero stock. gamma is
   0; calendar theta of the put is r times its value. lambda is null.
3. deterministic: intrinsic value of discounted carry amounts, no d1/d2 or
   lambda. At equality of the numerically evaluated carry amounts, all Greeks
   and hedge bank fields are null because of the spot kink. Otherwise delta and
   theta follow the corresponding affine branch; gamma is zero. PDE residuals
   are null to avoid portraying a degenerate first-order problem as the interior
   diffusion check. Exact r=q and S=K in the supplied case produces equality.
4. positive_diffusion: the normal formulas and interior derivatives apply.

Negative rates are allowed. The put upper bound is K exp(-r tau), which can
exceed K. Zero spot is absorbing, not a reason to evaluate log(0). Zero maturity
and zero volatility never divide by zero. The listed domain keeps intermediate
exponentials and outputs finite. JSON serialization with allow_nan=False is a
last check, not a substitute for input-domain validation.

NUMERICAL METHODS AND TOLERANCES
Normal CDF uses math.erfc; prices evaluate the out-of-the-money member of the
call/put pair directly and recover the other through parity. A negative direct
price is clipped only if its magnitude is at most 1e-12*(1+prepaid+strikePV);
a larger cancellation failure raises ValueError. run() separately checks bounds
and parity at the same scaled tolerance. Rare tails can underflow to zero. The
extreme_tail case is intentionally so far out of the money that relative error
of its call price is not a meaningful double-precision promise.

The independent checker integrates the positive payoff against standard-normal
density using composite Simpson quadrature, splitting at the payoff threshold.
It compares 4096 and 8192 panels and uses an absolute 2e-7 CU price tolerance,
including a tail cutoff at |z|=12. For the domain's a <= 0.8*sqrt(5), the normal
first-moment tail is shifted by at most 1.789; its cutoff tail times the bounded
prepaid amount is below 1e-18 CU. The quadrature grid difference is a diagnostic,
not a universal rigorous Simpson-error proof. Smooth formulas and structural
identities use tighter stated tolerances; finite-difference Greek checks use
2e-5 absolute/relative scales away from kinks and domain edges. Extreme prices
are checked against bounds and parity with absolute tolerances. Returned test
counts count actual comparisons, not editorial claims.

DENSITY TILT OUTPUT
lambda is the constant market price of risk. For the input P-increments x_i and
intervals h_i, log_density_Z = -lambda*sum(x_i)-lambda^2*T/2. density_Z is its
exponential when representable. If it underflows to zero in floating point,
density_Z is null and density_Z_underflow is true; the finite log is retained.
Otherwise density_Z_underflow is false. Mathematical Z remains strictly positive,
so a null numerical density does not invalidate measure equivalence.
Brownian_Q_increments_on_same_path are x_i + lambda*h_i.
log_joint_P_density and log_joint_Q_density_of_WP evaluate products of the
centered and shifted normal densities in log space. Their difference minus
log_density_Z should be roundoff. mean_WP_terminal_under_Q is -lambda*T and
variance_WP_terminal_under_Q is T. E_P_Z_analytic equals 1 and
log_E_P_Z_squared_analytic equals lambda^2*T by normal integration.
The expectation anchors are analytical, not estimated from the input vector.
A density at one vector is not the probability of a continuous path.

FUNDED HEDGE OUTPUT
At inception shares are model call delta; bank is premium minus share cost.
Between scheduled resets all proportional dividends are reinvested in stock,
so shares grow as n*exp(q*h); the signed bank grows as b*exp(r*h). This does NOT
hold the number of shares constant between resets. At a reset the marked wealth
is incoming_shares*S + bank_before_trade. A new model delta is purchased by
deducting rebalance_expenditure from that bank; no external contribution is
made. At expiry target shares are zero, so the stock is sold and all remaining
wealth is cash. terminal_error is wealth minus the long call payoff. A positive
error is a surplus of the hedge against that payoff; a negative error is debt or
a payoff shortfall. It is not an estimate of expected P&L or an arbitrage proof.
The short issuer plus this hedge has the same residual error before any costs.

REFERENCE ANCHORS
  dividend_call C=9.21485516196904, P=13.438194698606964
  call delta=0.4901411481384808, initial bank=-35.878130466771196
  Q exercise probability=0.38096710151340174; P=0.5061801068968993
  negative_rate C=10.89251885719689, P=10.173435672397531
  deterministic C=0, P=15.549084478966492
  absorbing put=102.02013400267558; expiry prices=0
  symmetric_zero_carry C=P=7.9655674554058 (roundoff differences possible)
  deterministic_kink prices=0; derivatives=null
  tilt lambda=0.26; log Z=-0.1027; Z=0.9023976521733346
  hedge terminal error=2.143362474277783 CU
The independent checker recomputes these from economic/mathematical inputs,
rather than treating this text or saved output as its sole numerical oracle.

INTERVENTIONS TO TRY
Change only physical_drift of dividend_call to "0.19": its option prices and Q
exercise probability stay fixed, but lambda becomes .66 and its physical
exercise probability becomes about .693357459. Change the final hedge price
from 110 to 40: all earlier cash is unchanged, and terminal_error becomes about
-7.902181202 CU. Set an inconsistent deterministic mu: validation must reject.
A successful run answers only the declared model question. Calibration,
empirical adequacy, actual dividend rights and executable financing require
separate evidence, as the chapter's research-critique exercise explains.
