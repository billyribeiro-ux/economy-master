V10-C03: FINITE TERM-STRUCTURE CALIBRATION AND MODEL RISK
Original synthetic teaching lab, version1, 9 October2026

Purpose and boundary
--------------------
Fit three supplied annual discount points with a finite short-rate model,
then separate that fit from physical expectations, pricing dynamics and
hedge robustness. This is not a real market dataset, a current term-premium
estimate or a general-purpose rate library. The three model cases share a
curve but choose different positive discount shapes. A separate additive
physical process illustrates finite mean reversion without stochastic
calculus. Every result is conditional on the supplied contracts.

Distributed files
-----------------
v10-c03-inputs.json    complete exact inputs and convention labels
v10-c03-analysis.py    Python3 standard-library implementation
v10-c03-output.json   complete preserved strict-JSON reference output
v10-c03-README.txt     this contract and reproducibility guide
v10-c03-manifest.json  byte counts and SHA256 of the preceding four files;
                      excludes itself

Run from any directory:
  python3 /path/to/v10-c03-analysis.py
The default input is resolved beside the program, not in the working
directory. The complete JSON result is printed. To write an explicit file:
  python3 /path/to/v10-c03-analysis.py --input /path/to/v10-c03-inputs.json \
    --output /path/to/result.json
A successful --output call prints nothing. A malformed or economically
unsupported input exits nonzero with an explanatory error. Importing the
program is quiet. run(data) validates a JSON-like object, returns a fresh
strict-JSON-compatible object and prints nothing; it does not mutate input.
No network, installed packages, random simulation or cached external state
is used. Python optimization (-O) does not disable validation.

Financial timing and trading contract
-------------------------------------
Dates are exactly0,1,2,3, separated by one year; currency is CU. Zero bonds
pay1 CU at maturity. cashflows[k] is paid at date k+1, with all principal
already included; the supplied5,5,105 payments contain no further principal.
Reported coupon_ex_payment_values[t] exclude payments already made at t;
its date3 continuation value is zero after the last105 payment.

At node(t,j), j is the number of previous high-rate branches. Its short
rate is known at the beginning of[t,t+1]. d(t,j)>0 is that interval's
discount, r(t,j)=1/d-1 its effective annual rate. Low keeps j; high adds1.
The rates recombine by node, but accumulated bank wealth generally does not.
A0=1 and A(t+1)=A(t)/d(t,j) along each full history. The last branch at date3
can distinguish states even though there are no later rates in this model.

All borrowing/lending uses the same node account rate. Signed bond/account
positions, finite holdings, self-financing rebalancing and bond liquidation
at the displayed node values are allowed. There are no taxes, default,
fees, collateral constraints or separate external costless storage rights.
Therefore rates may be negative but must have positive gross returns.
Adding an external cash-storage asset changes the no-arbitrage restriction;
it is not a label that can be changed while retaining these computations.

pricing_up[t][j]=q is the conditional high probability under Q; physical_up
is the corresponding P probability p. Every p and q is strictly between0
and1. They have the same positive support, not necessarily equal weights.
P governs forecasts; Q and discounting govern chosen model prices. A
positive Q supplies an internally arbitrage-free pricing extension under
the stated rights. This does not prove unique pricing of arbitrary
unspanned terminal claims or empirical adequacy of any probability.

Calibration
-----------
D0=1; D1,D2,D3 must all be positive, not necessarily decreasing. For model
parameter0<=s<1/2, set h(t,j)=1+s(t-2j), for t=0,1,2. Start a(0,0)=1.
At each date fit c(t)=D(t+1)/sum_j[a(t,j)h(t,j)], then d=c*h. Send each
Arrow weight a*d*(1-q) to the low child and a*d*q to the high child.
The total Arrow weight at T is D(T) exactly. Each c is unique conditional
on the chosen shapes, Q and earlier levels; neither shapes nor Q are
identified by this curve. s is a discount-shape parameter, not a volatility
expressed in annual rate units. Its upper bound is specific to this tree.

Backward zero prices have terminal value1 and current value d times the
conditional Q average of next prices. Coupon valuation adds the next
cashflow once, inside that next-period valuation. Arrow weights are prices,
not Q node probabilities. For a full path, state_price=Q(path)/A3 and
P_sdf=state_price/P(path). Distinct histories into the same rate node can
have distinct bank accounts and path prices.

The base curve is(1,.98,.95,.91). Model s values are .02(base),0(deterministic)
and .04(wide). All produce a5/5/105 bond price of105.2. The base levels are
49/50,95/98,45500/47519. Its date1 discounts are969/980 and19/20. The wide
model's low date1 discount247/245 gives a negative short rate-2/247, which
is allowed by the specified opportunity set.

Claim, holding returns and hedge error
-------------------------------------
The claim pays cash at date1: max(face*P(1;2)-strike,0). Its face is a
multiplier on the price of a unit-face date2 zero; it is not a further
payment at date2. The fixed claim dates1 and2 are not editable. At the
reference face100/strike96, prices are1.41(base),.92(deterministic),2.36(wide).
Replicate a date1 payment using units of the unit-face date2 zero and a
date0 bank position. A negative bank position is borrowing. The base hedge
is1410/19 zeros plus-69.09 CU cash; the69.09 debt becomes70.50 at date1.
It costs1.41 and matches both branch payments. The wide hedge costs2.36
and uses1180/19 zeros and-56.64 cash.

When successor bond values coincide, the coefficient system is singular.
For this payoff rule, identical bond values give identical claim payments;
the program chooses a bank-only replica with zero bonds. It does not
silently divide by zero or infer that differing branch claims are spanned.
Zero-payoff and both-positive-payoff strikes are valid boundaries.

frozen_base_hedge_model_risk retains the base holdings and initial bank
position, then values their date1 cash in each other model with the same
initial curve and Q. Errors are hedge cash minus that model's claim cash.
Against the wide tree they are-1/2 and-141/98; their Q-discounted value is
-.95=1.41-2.36. This is a comparison across model hypotheses, not two
simultaneously tradable inconsistent quotes in one declared economy.

holding_premiums covers each node t=0,1, holding the zero maturing at t+2
for ONE period. Divide its next sale value by the current purchase price
to obtain the gross return G. Expected excess is E_P[G]-1/d. Local physical
SDF branch values are d*q_branch/p_branch; covariance satisfies excess=
-Cov_P(m,G)/d. No maturity payment is added at the earlier sale date.
The base root premium is-2/245. With the supplied date1 physical high
probabilities(.4,.8), next conditional premiums are196/49419 and-12/931.

forward_vs_expectations reports f=D1/D2-1 and the Q/P means of the next
short rate. f=1/E_Q[1/(1+r1)]-1, not generally E_Q[r1]. Decompose f-E_P[r1]
into(f-E_Q[r1])+(E_Q[r1]-E_P[r1]); the first term is nonlinear averaging.
Changing P alone changes forecasts, physical path probabilities and SDFs,
not calibrated Q prices or their hedges. A forward gap is not automatically
a pure holding-return risk premium.

Curve scenarios
---------------
Each curve_scenarios item supplies a new entire positive discount curve.
The first model's s, Q, P and cash/claim contracts stay fixed. Recalibrate
all levels, then report discounts, fitted sums, prices and changes. These
are alternative date0 input curves, not future tree nodes and not physical
probabilities. lowering D2 to.94 gives coupon105.15 and claim.90; separately
lowering D3 to.905 gives coupon104.675 and claim1.41. Reducing D2 to.92 crosses
the claim's payoff boundary: exact value0, not a negative extrapolation.

Separate finite physical process
--------------------------------
mean_reversion specifies r_next=theta+phi*(r-theta)+sigma*epsilon, with
independent equiprobable epsilon in{-1,+1}. It is not used to price or fit
the curve. The program enumerates all2**steps paths, reports the terminal
mean/variance and checks them against the finite-sum formulas. For initial
.08,theta.02,phi.5,sigma.01 and steps2, terminal rates are(.02,.04,.03,.05),
mean.035 and variance1/8000. The non-recombining histories are intentional.
This case assumes0<=phi<1 and sigma>=0; phi1 is discussed analytically in
the chapter but is outside this mean-reversion input contract. Every initial
and future path rate must exceed-1. The law and rate units must be named
before interpreting moments. No continuous-time theorem is assumed.

Strict input domain
-------------------
The JSON schema is v10-c03-finite-tree-v1. Every object has exactly its
listed fields. Convention strings and dates match the input file exactly;
new time grids or trading rights require a different model. Numerical
quantities use integers or exact ASCII rational/decimal strings: "49/50",
"0.98" or1. Bare JSON floats, booleans, NaN/Infinity, exponent strings,
zero denominators and malformed values are rejected. Exact parsed input
magnitudes are limited to10**6, denominators to10**12, and strings to80
characters for this small teaching lab. Internal Fractions need not obey
those input bounds. Every computed rational is returned as a canonical
fraction string, including exact zero as"0". Indices/counts remain integers.
The CLI also rejects duplicate JSON fields and nonfinite JSON tokens.

- discount_curve: exactly four positive points, first exactly1.
- pricing_up/physical_up: exactly three rows of lengths1,2,3, strict(0,1).
- models: one through eight, unique names, first named base, each has name
  and dispersion only;0<=dispersion<1/2. Names begin with a lowercase ASCII
  letter, then up to31 letters/digits/underscores.
- cashflows: three nonnegative dated amounts, at least one positive.
- claim: integer payment_time1, integer bond_maturity2, positive face and
  nonnegative strike. Dates represented by booleans are rejected.
- curve_scenarios: zero through eight uniquely named scenarios; each has
  name and a full valid discount_curve, not an ambiguous unnamed bump.
- mean_reversion: exact initial,level,phi,innovation; integer steps1..6;
  0<=phi<1,innovation>=0, and positive gross rates on all enumerated paths.

Finite input validity means only that the contract is internally defined.
A large but admissible rate or a fitted claim price is not an empirical
recommendation. No extra storage, collateral rule or future timing can be
added silently. The program returns no partial fallback model on failure.

Meaningful checks and limits
----------------------------
The separately owned focused checker reconstructs calibration with full
prefix paths, prices zeros/coupons by enumerating suffix cash discounts,
recomputes all material worked/exercise results, tests P-only and Q changes,
payoff boundaries, increasing discount curves and mean-reversion boundaries,
checks genuine domain rejections, compares the complete preserved output,
verifies the four-file manifest and tests isolated normal/optimized CLI use.
It is quiet on import/check(). It is not needed to run the downloaded lab.
The manuscript separately supplies the no-arbitrage/calibration proofs and
research-critique evaluation criteria. The author record lists exact reviewed
payload hashes and honest limits; author checking is not external academic
certification or empirical validation.
