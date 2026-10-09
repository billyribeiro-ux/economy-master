VOLUME 10, CHAPTER 2 — DURATION, CONVEXITY AND IMMUNIZATION
Original deterministic teaching laboratory; 9 October 2026

REPRODUCE
Keep these five files in one directory:
  v10-c02-inputs.json
  v10-c02-analysis.py
  v10-c02-output.json
  v10-c02-README.txt
  v10-c02-manifest.json
Run with Python 3, using only its standard library:
  python3 v10-c02-analysis.py
  python3 v10-c02-analysis.py --input v10-c02-inputs.json --output result.json
The default input resolves beside the script, independently of the working
directory. Stdout is complete strict JSON; --output writes that JSON without
printing it. Import and run(data) are quiet. No network, installation, plotting
package or random seed is required. Preserve the supplied input/output before
editing. The manifest hashes the four companion files and excludes itself.

Within the source repository, the independent focused review is:
  python3 book/scripts/check_v10_c02.py
Its check() is quiet and returns a strict-JSON review summary. It reconstructs
material baseline prices, derivatives, cash ledgers and exercise numbers,
checks selected interventions and invalid domains, compares every preserved
output field, and executes the portable CLI normally and with optimization.
Passing this check is not proof of every prose argument, real-world liquidity,
or external academic certification. The coordinator reviews the manuscript.

CONTRACT AND UNITS
All data are original synthetic contracts, in currency units (CU); no market
observations are supplied. Time is in years from a fixed settlement date.
Inputs are decimal rates: 0.01 means a one-percentage-point change, or 100 bp.
Payments are fixed, nonnegative, default-free and in one currency, without
options, taxes or transaction costs except in named independent interventions.
Asset quantities stay fixed during a valuation shock. There are no scenario
probabilities, forecast estimates, stochastic paths or automatic rebalancing.
Each explicit contract/convention string is part of the schema. Changing its
words does not change the economics implemented by the code and is rejected.

The note module uses nominal annual yield y compounded m times a year:
  P = sum C_t * (1+y/m)^(-m*t).
Its derivatives are with respect to y, not y/m. Dollar duration K=-P', dollar
convexity G=P'', Macaulay duration=sum(t*PV)/P, modified duration=K/P,
convexity=G/P; convexity itself has no extra one-half. DV01 is the positive
estimated CU loss for a one-basis-point increase: 0.0001*K. The Taylor price
change is -K*h + G*h*h/2. Errors are estimate minus exact price. The stated
third-derivative absolute remainder bound is valid over the entire segment
between the base and shocked yield in the positive-gross-factor domain.
Accrued interest is a fixed same-date amount: clean=dirty-AI. Dollar sensitivity
uses the actual dirty settlement price. This is not a day-count/accrual engine.

The hedge module uses annual effective yields and a flat common curve. Its
liability of 125 at year 3 costs V=125/1.05^3. Half V buys a year-1 zero, and
half buys a year-5 zero: faces 56.68934240362812 and 68.90625. The two market
values sum to the available budget. Quantities and faces are never confused
with present-value weights. Equal value and dollar duration yield zero local
first derivative; higher asset dollar convexity gives the stated local result.

CASH CLOCKS AND SEPARATE INTERVENTIONS
The single-shift scenarios assume a rate change immediately after purchase,
followed by a constant annual rate. Receive the short zero at its maturity;
reinvest all its cash until the liability horizon at that same rate; then
receive that investment and sell the long zero at the price for its remaining
maturity. Pay the liability at that horizon. The output closes both the
instantaneous valuation surplus and the actual conditional horizon ledger.
This is stronger than an assumption about the initial discount curve alone.

The later-path intervention instead assumes no immediate shift: the actual
rate available when the short zero matures is 0%, and the actual remaining
yield when the long zero is sold at the horizon is 10%. Neither quote was
locked earlier. Horizon wealth is 113.6366564532149, below the 125 liability.

The entry-fee intervention is independent. A fee f of security value is paid
at purchase from the unchanged original cash budget. Scale both holdings by
1/(1+f); security value plus fee equals the budget. The output also states the
extra initial contribution f*V that would fund the original unscaled hedge.
At f=0.002 the scaled hedge delivers 124.750499001996 at the base constant
rate. Unchanged normalized duration does not replace the missing cash.

The changed-cash-flow intervention is also independent: the long zero pays
the stated fraction of its original face, valued and sold at the original
constant rate. At fraction 0.9, horizon wealth is 118.75. This is a stipulated
claim change, not a probabilistic credit model. Do not add the three separate
losses into an unexplained combined strategy.

CURVE COORDINATE
The key-rate module uses continuously compounded zero-rate nodes, piecewise
linear between the stated key times. At an exact key the basis is one there;
between adjacent keys it consists of the two linear interpolation weights.
All basis weights sum to one. No extrapolation is supported. Its baseline is
flat at log(1+immunization.base_annual_yield), including the curve valuation of
the coupon note. This baseline is intentionally separate from the note's own
quoted nominal yield. Editing note.nominal_annual_yield does not change the
key-rate baseline; edit the hedge base yield to change that baseline.

Dollar key duration is -dP/dz_k. The Hessian contains all second derivatives,
including cross terms. Every scenario bumps the full named vector and exactly
reprices the asset, liability and note payments. A continuous-zero bump of
0.01 is not the same as an annual-effective-yield bump of 0.01. With flat
annual yield y, K_y=K_z/(1+y) and G_y=(G_z+K_z)/(1+y)^2. The (1,3,5) surplus
key vector is V*(0.5,-3,2.5); its zero sum removes the parallel first-order
component but not the twist. The named adverse twist gives -2.090509038717073
of valuation surplus. The output never divides by the zero initial surplus
to manufacture a surplus percentage duration.

LOCAL COUNTEREXAMPLE
A separate polynomial family has initial annual yield zero. At scale 100 and
cutoff 1.2, assets pay (120 at 1, 320 at 3); liabilities pay (340 at 2, 100 at 4).
Initial value and first derivative match, while S''=40>0. With d=1/(1+y):
  S=100*d*(d-1)^2*(1.2-d).
At y=-0.2, exact S=-25/64. The negative rate is an admitted synthetic stress,
with no assumed costless physical-currency storage facility. This is a date-0
valuation counterexample to a global claim, not a plan for interim payments.

SUPPORTED EDITS AND VALIDATION
Input objects require their exact named fields. JSON duplicate keys and NaN/
Infinity are rejected. Bool is not a number. Numeric inputs must be finite.
The public exercise interface is run(data) or the CLI; internal pricing helpers
assume the validated contract and are not a general-purpose finance API.

You may edit payment amounts/dates, nominal yield, frequency, accrued amount,
shocks and finite-difference step within the note contract: aligned arrays,
strictly increasing positive dates no later than 50 years, nonnegative payments
with at least one positive, integer frequency 1..12, and payment dates on that
periodic grid. Base, shock and both finite-difference periodic gross factors
must be positive. AI lies in [0,dirty price), and the bump step is positive.
The key range must also cover every changed note payment date. The declared
periodic grid is a simplifying lab boundary, not a universal pricing rule.

You may edit liability amount and horizon, exactly two asset maturities, base
annual yield, parallel shocks, later reinvestment/sale yields, fee and payoff
fraction. The positive liability date must be strictly between positive asset
maturities no later than 50. All relevant annual gross factors must be positive.
The fee lies in [0,1), the changed payoff fraction in [0,1]. Market values and
faces are rebuilt from the edited budget and duration equations, before shocks.
The horizon ledger permits fractional year powers as an explicitly defined
annual-effective compounding convention. Each edited cash date must also lie
within the declared curve keys.

You may edit positive, strictly increasing key times (at least two, <=50), and
nonempty named scenarios with one finite continuous-zero bump per key. Names
must be distinct. Continuous zero rates need not be positive; exp(-t*z)>0.
You may edit the counterexample's positive scale, cutoff>1 and stress yield>-1;
its baseline stays zero and its cash-flow family is rebuilt from that contract.

Examples of meaningful experiments: double the liability and verify every
hedge face/exposure/funding gap doubles; set fee=0 and close the unchanged
budget without a fee; restore payoff fraction=1; reverse a key twist and compare
exact repricing rather than assuming perfectly symmetric gains/losses. A change
in annual yield, a curve-node shift, a later cash quote and a changed claim are
different experiments and should receive different interpretations.

This floating-point program rejects overflow, division by zero and nonfinite
results; extreme finite inputs that exceed its numerical range are unsupported.
It preserves tiny roundoff residuals. Smaller finite-difference steps eventually
lose accuracy through subtraction; the supplied step is not an empirical rule.
No grid covers all possible curve movements. The program does not validate
liquidity, market execution, quote availability, optional payments, default
probabilities, collateral, changing settlements or a real reserve mandate.
