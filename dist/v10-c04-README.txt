FENWICK CREDIT DESK — CREDIT RISK AND RECOVERY (V10-C04)

Run with Python 3 standard library only:
  python3 /path/to/v10-c04-analysis.py
A changed input copy and quiet output file are supported:
  python3 /path/to/v10-c04-analysis.py --input copy.json --output result.json
The default input is found beside the script, regardless of working directory.
Keep inputs.json, analysis.py, output.json and this README under their full
v10-c04- prefixed names. The separate manifest hashes those four distributed files.
No package installation, network, credentials, randomness or market-data retrieval
is used. Import and run(data) print nothing. run returns a new strict JSON-ready
result without altering the supplied dictionary. CLI prints JSON unless --output
is supplied. Exact rational answers are strings, including integers represented
as fractions; only named _approx outputs use floating point. Undefined values
are Python None internally and JSON null in the serialized output, never NaN.
The preserved output is complete, including state and cash rows and every
conditional calibration, not merely a set of selected prices.

SCOPE AND INFORMATION
Every contract, probability, recovery, quote and numerical input is original and
synthetic. Time is years after 1 January 2027, with date zero before all payments.
Money is CU, not thousands. No current market quote, legal insolvency test, tax rule
or empirical default estimate is asserted. Each block describes its own bounded
contract; the probability laws in different blocks are not silently identified.
The fixed conventions state the claim perimeter and payment sequence. There are
no additional senior claims, fees, taxes, collateral changes or optionality.
Recovery terminates all original remaining claims. A later recovery payment is
assumed enforceable without an extra counterparty risk only where explicitly given.

P describes physical outcomes; Q is the supplied pricing law. Deterministic dated
discount factors multiply Q-weighted cash. The model does not estimate Q from P
or claim that no arbitrage uniquely identifies the supplied Q. Structural state
probabilities are strictly positive. Scheduled and migration P/Q laws must share
support: a zero-probability event cannot acquire positive probability only by
changing to an equivalent pricing measure. Constant continuous P and Q intensities
must either both be zero or both be positive. The joint-default block expressly
stipulates Q=P for that separate risk-neutral-investor illustration only.

The chapter's three primary references were inspected for their specific scopes:
Merton's 1974 terminal structural allocation and indenture assumptions; Duffie's
preliminary 18 August 1998 recovery-of-par manuscript and recovery timing/base
qualifications; Han and Zhou's March 2008 manuscript on matching cash flows and
benchmark/model sensitivity in a dated empirical decomposition. No diffusion,
Ito or Black-Scholes result is assumed here. The elementary calculations and
exercise cases are original; the references do not supply these inputs.

1. FINITE STRUCTURAL CONTRACT
There is one nonrecourse zero-coupon face F=100 and no interim payout. Terminal
assets V are [70,110,160], P=[0.1,0.6,0.3], Q=[0.2,0.5,0.3] and D=0.96.
Default means V<F; equality is full payment and zero equity. Baseline workout
cost is zero. Debt gets min(V,F), equity max(V-F,0), so their sum is V in every
state. State prices are DQ=[0.192,0.48,0.288].

Baseline debt price=90.24; equity price=22.08; asset price=112.32.
Physical default probability=0.1, pricing default probability=0.2.
Physical expected debt receipt=97 and expected face loss=3 CU.
Expected simple debt return=97/90.24-1=0.0749113475177...
Promised simple yield=100/90.24-1=0.108156028369...
Safe simple return=1/0.96-1=1/24.
Continuous promised spread=-log(90.24/(100*0.96))=0.0618754037181... per year.
Promised yield uses face, while expected return uses P-weighted actual receipts.
A change of convention must not combine simple and continuous spread components.

The workout intervention consumes the supplied fraction of asset cash ONLY in
default states. Equity remains zero in those states; debt receives remaining
assets. Reported gross_asset_value includes those resources before the workout;
claim_value plus workout_cost_pv reconciles to it. With fraction 0.1 the cost PV
is 1.344, debt is 88.896 and equity remains 22.08. Treating the consumed amount as
an additional creditor payment would violate the resource identity. Fraction one
can create zero-payoff debt; return and spread are then null, not division by zero.

2. FINITE SURVIVAL AND SCHEDULED RECOVERY
The three-year note has face 100, coupon AMOUNT 6 at each listed date, recovery
fraction 0.4, times [1,2,3] and D_k=(25/26)^k (4% effective annual funding).
P conditional interval hazards are [0.01,0.02,0.03], Q hazards [0.02,0.03,0.04].
Start S_0=1; m_k=S_(k-1)h_k; S_k=S_(k-1)-m_k. These are first-default events.
Under Q:
  survival:       0.98, 0.9506, 0.912576
  first default:  0.02, 0.0294, 0.038024
Conditional hazards apply only to the surviving population. Marginal default
masses plus final survival sum to one. The price does not use P hazards.

Default is recognized at an interval end immediately BEFORE its coupon. A default
pays 40 there instead of coupon, principal and all later rights. Expected row cash
is 6*S_k+40*m_k, plus 100*S_3 in the final row. Price is
3519809/35152 = 100.131116294948... CU. A separate delayed-recovery contract pays
the same 40 only at year 3 after any first default. Coupons still stop on default.
Its price is 3516299/35152 = 100.031264223942..., and timing value is
135/1352 = 0.0998520710059.... Early recovery has greater PV for this positive-rate
curve. That sign need not survive negative-rate discount curves.

The model reports the equivalent constant within-interval Q intensity
-log(1-h_k)/(t_k-t_(k-1)). This is one interpolation of the same discrete survival,
not an identified intrainterval timing law. The scheduled module's hazards are
restricted to [0,1) to retain finite equivalent intensities. The general prose
explains certain default and exhausted survival; the migration module below
handles those boundaries directly. Coupon_amount is a cash amount per listed
payment, not an annual rate automatically adjusted for an edited interval.

3. CONSTANT INTENSITY AND THREE DISTINCT RECOVERY CONTRACTS
Inputs: F=100, T=5, r=0.03 per year continuously compounded, lambda_Q=0.06,
lambda_P=0.02, rho=0.4. Rates and intensities are deterministic and constant.
S_Q(T)=exp(-lambda_Q*T)=0.740818220682...
S_P(T)=exp(-lambda_P*T)=0.904837418036...
Default-time density under Q is lambda_Q*exp(-lambda_Q*t).

Immediate recovery of PAR pays rho*F at default and F at T only if alive:
  B_par=F*exp(-(r+lambda_Q)*T)
        +rho*F*lambda_Q*integral_0^T exp(-(r+lambda_Q)*t) dt
       =73.4260644522634...
Maturity-paid recovery pays rho*F at T following any earlier default:
  B_delayed=F*exp(-r*T)*(rho+(1-rho)*exp(-lambda_Q*T))
           =72.6860081543087...
Recovery of PRE-DEFAULT MARKET VALUE pays rho times that value at default:
  B_market=F*exp(-(r+lambda_Q*(1-rho))*T)=71.8923733431926...
These are different contracts, not three competing implementations of one claim.
The simple first-default integration needs no stochastic calculus. The market-value
formula is independently derived from a short-step conditional pricing equation
and its ordinary backward differential equation in the chapter.

The expression (1-exp(-k*T))/k uses -expm1(-k*T)/k for k != 0 and the exact limit
T for k=0. Thus r=-lambda is admitted. With lambda=0 both P/Q intensities must be
zero, and each price equals the safe zero. Negative rates are allowed within the
stated computational bounds and are not treated as arbitrage; no separate costless
cash-storage technology is assumed. Zero recovery makes all three contract prices
equal, but positive recovery generally does not. Recovery one makes the MARKET
VALUE contract default-free in value; immediate par repayment can be more valuable
than waiting to receive the same face at T. A negative promised spread then reflects
a different cash timing, not a free gain for an identical maturity-only payoff.

4. MIGRATION AND FIRST DEFAULT
States are ordered A,B,D, with D absorbing. The initial state is A.
P=[[0.90,0.09,0.01],[0.15,0.80,0.05],[0,0,1]].
Q=[[0.85,0.12,0.03],[0.10,0.80,0.10],[0,0,1]].
Each row applies for one year and the same matrix is used every year. The state
is assumed sufficient for the next transition. The initial live row distribution
is multiplied by the matrix; default increments are successive differences in
cumulative D mass. They are not repeated D occupancy payments.

Starting in A, Q cumulative defaults are [0.03,0.0675,0.109335]; marginal defaults
are [0.03,0.0375,0.041835]. Final physical default is 0.039385. A three-year zero
face 100 and recovery 40 at first default, using (25/26)^k discount factors, has
price 23399455/281216 = 83.2081211595357.... Physical weighted discounted cash is
24422785/281216 = 86.8470677344106..., explicitly NOT its supplied-Q price.

Rows contain both cumulative and marginal probabilities and the conditional hazard
when any names remain alive. If a valid edited matrix sends all live names to D
in year 1, recovery occurs once in year 1; later increments and principal are zero,
and later conditional hazards are null. An initial D state is rejected because
the input contract is an initially live note and its recovery has not already
been settled. All rows must be stochastic and both matrices share zero patterns.
The code makes no claim that a historical rating transition matrix is stable,
Markov, complete or automatically risk-neutral.

5. JOINT DEFAULTS AND TWO TRANCHES
Two separate notes each promise 100 at one year and return 40 if defaulted. Here,
and ONLY here, risk-neutral investors are explicitly stipulated so P=Q. Marginal
defaults are both 0.1; joint cases are 0.01 and 0.05. Probability cells in order
(neither,A only,B only,both) are (0.81,0.09,0.09,0.01) or (0.85,0.05,0.05,0.05).
General bounds are max(0,p_A+p_B-1)<=j<=min(p_A,p_B). A correlation target not
consistent with these bounds cannot be used. Degenerate marginals give a null
indicator correlation rather than zero or infinity.

Each default loses 60 CU. Junior principal 60 absorbs first losses; senior principal
140 absorbs the rest. State pool loss equals junior plus senior loss; receipts sum
to the pool's available assets. Expected pool loss remains 12. Variance is 648 or
936 CU squared. Junior expected loss is 11.4 or 9; senior expected loss 0.6 or 3.
At D=0.96, junior prices are 46.656 or 48.96, senior prices 133.824 or 131.52, and
both total 180.48. More clustering reduces the probability of any loss but raises
the chance of two defaults; it does not move all tranche values in one direction.
Changing marginals, recovery or tranche width recomputes the full four-state ledger.
The tail field means loss strictly ABOVE one name's loss, so at zero LGD its value
is zero even if joint default has positive probability.

6. CONDITIONAL CALIBRATION AND LIQUIDITY
Observed zero-note price is 85.5, F=100, T=2, D=0.9. Recovery is paid only at T
following default, with no subsequent recovery-counterparty risk. Let k be a
supplied observed-to-credit price multiplier. Then
  x=B/(F*D*k), q=(1-x)/(1-rho), lambda_Q=-log(1-q)/T.
A finite intensity requires 0<=q<1. Rho=1 with x=1 leaves hazard unidentified;
rho=1 with x!=1 is incompatible. Invalid combinations are reported as explicit
non-calibrations with null probability/intensity/repricing, not clipped to zero.
The default grid uses rho=[0,0.5,0.75] and k=[1,95/97]. All six combinations fit.
At k=1, q=[0.05,0.10,0.20]. At k=95/97, q=[0.03,0.06,0.12].
Every compatible row reprices exactly to 85.5. Intensities differ across rows;
none is a physical default estimate. The liquidity yield wedge is -log(k)/T,
a supplied accounting of this assumed multiplicative price difference. It is not
measured independently and is not a causal empirical decomposition.

The credit benchmark is a model value, or relevant frictions prevent its exact
unrestricted replication. This avoids claiming two executable frictionless prices
for identical dated payoffs. The code does not introduce a liquidity adjustment
into the other model blocks or assert that default and liquidity are independent.

EDITING AND FINANCIAL VALIDATION
Keep schema, case identity, provenance, conventions, matrix state order and the
explicit joint Q=P contract fixed. Numeric interventions may change faces, states,
P/Q probabilities, workout fraction, coupon amount, coherent dated schedules and
discount factors, constant rates/intensities, migration rows, marginals/joint masses,
tranche width and the calibration grid. Preserve the original before running.
Input objects require their exact documented fields; numbers must be integer or
rational strings, not floating JSON numbers or booleans. Vector length is bounded
at 12, joint cases at 10, time at 50 years, magnitudes at 10^6 and rational
denominators at 10^12. Faces are positive; asset states nonnegative and not all
zero. Discount factors are in (0,3]; decreasing factors are NOT required, so negative
rates remain possible. Recoveries and workout fractions lie in [0,1]. Scheduled
intervals are strictly increasing and aligned across all vectors. Constant short
rate is in [-0.2,1], intensities in [0,2], with common P/Q support. These guards
keep a transparent small model rather than a general credit library.

The focused checker reconstructs structural state cash, event-path pricing,
continuous recovery integration by an independent quadrature, full migration
paths and all four joint states. It independently solves the determinate exercises,
checks meaningful zero-recovery/zero-intensity/full-recovery/certain-default and
support boundaries, rejects contradictory inputs, verifies complete preserved
JSON and hashes, and reproduces isolated normal/-O CLI runs from another directory.
Proof and source scope are reviewed separately; no numerical test substitutes for
an assumption audit, empirical validity or external human certification.
