V06 C07 — Inflation, expectations and nominal rigidity
Original synthetic teaching lab, created 8 October 2026.

Files: v06-c07-models.json, v06-c07-inflation.py, v06-c07-output.json,
       v06-c07-README.txt
Place all four in one directory. Run with standard-library Python 3:
  python3 v06-c07-inflation.py
Optional changed input:
  python3 v06-c07-inflation.py my-models.json
To preserve a separate output:
  python3 v06-c07-inflation.py > my-v06-c07-output.json
Default input resolves beside the program, regardless of shell working directory.
Runtime has no network calls or external packages and never changes inputs.

All inputs are authored scenarios, not country data, estimates or calibrated
policy effects. Quantities use exact integer/rational strings; period counts
are JSON integers in [1,100]. JSON floats and booleans are not quantities.
The program returns exact fraction strings; it does not round them to rates.
Retain IDs demand_negative, demand_positive, pricing_negative and pricing_positive:
the descriptive-regression comparison uses those four named cases. Other case
IDs must remain nonempty and unique within their group.

UNITS AND TIMING
Pi = 100 ln(P_t/P_previous) is log inflation in log points per period.
Ordinary inflation is exp(Pi/100)-1, not Pi/100 exactly. The output gap is
x = 100 ln(Y/Ybar), measured against the chapter's supplied reference-output
path for baseline real conditions. A cost shock can move the flexible-price
allocation; x is not automatically a gap to that shock-specific allocation or
a welfare loss. Slopes a,b convert log-point quantities in the stated model.

Preset price: p_previous+e, with e formed using previous-period information.
Reset target: p+a*x+z, taking aggregate p as given at each small firm.
Geometric index implies s*(Pi-e)=(1-s)*(a*x+z). Demand is
x=d-b*(Pi-anchor). The solver uses these equations without division by s,
so s=0 (all reset) and s=1 (all preset) are handled explicitly. At s=0, kappa
and the scaled disturbance u are null because their divided definitions fail.
The all-preset unused reset target is reported only as a counterfactual price.
The program requires a,b>0. The chapter discusses b=0 as a separate boundary
outside this maintained demand-response domain, not an implemented case.

Each static case normalizes previous log price to zero (P_previous=1 in fixed
units). Adaptive paths begin with log price zero immediately before period0;
they sum realized Pi to obtain later log levels. Forecast updates happen after
each realization. Constant disturbances are held for the entire supplied path.
A null unique_forecast_fixed_point means the stated update does not pin down
one value; it does not mean the forecast converges to zero. Learning0 preserves
the initial forecast; fully preset prices cannot generate a forecast error here.
Infinite cumulative log-gap sums in the chapter use a geometric-series proof.
The program reports only the actual finite-horizon sum, clearly labeled.

Model-consistent cases specify finite positive probabilities summing to one,
known model parameters/regime and prior information about the distribution.
The forecast is the expectation of LOG inflation, not ordinary inflation.
Known demand is a one-state distribution; surprise demand has two states.
Model consistency does not provide perfect foresight for individual shocks.

The quantity block separately uses M average currency stock, V income velocity
per period and Y goods per period. P=MV/Y is currency per good. Income velocity
is defined using final output, not the volume of all financial transactions.
The return block uses ordinary fractional rates with positive gross factors.
Its expected real return averages the state-specific reciprocal price growth.

TARGETS
Quantity: constant V gives P1=18/17, ordinary inflation 1/17 and real loan net
return 1/50. Falling V=17/9 gives P1=1 with the same M and Y. Uncertain-return
example gives expected real gross 121/120, versus 1 when using mean inflation.
Baseline pricing: kappa = 1/2, Pi = 2, x = 0. Demand d = 3: Pi = 3, x = 2.
Pricing z = 6 (u = 3): Pi = 4, x = -2.
Pricing z = 3 gives Pi = 3, x = -1. The alternative forecast case gives Pi = 3,
x = 2 despite e = 1, u = 1, matching the e = 2, u = 0 demand case's observables.
Exercise 4: Pi = 7/2, x = 1.
All preset demand case: Pi = 2, x = 3. All reset d = 3, z = 0: Pi = 5, x = 0;
d = 0, z = 6: Pi = 8, x = -6.
Adaptive worked: rho = 5/6, first Pi = 10/3, x = -4/3, next e = 11/3,
next Pi = 28/9, x = -10/9.
The chapter's infinite log-gap sum is -8; the six-period output is a finite sum.
Exercise adaptive rho = 2/3; persistent d = 3 converges toward e = Pi = 5, x = 0.
Consistent surprise: e = 2, Pi = 1 or 3, x = -2 or 2. Known d = 3: e = Pi = 5, x = 0.
Synthetic descriptive OLS slopes: demand 1/2, pricing -1, mixture -1/4.

LIMITS
The pricing target, price index, demand rule, expectation law and reference
output are assumptions. This is neither a complete optimizing NK equilibrium
nor evidence that a named policy is exogenous, credible or optimal. Numerical
solutions outside a small local neighborhood should not be treated as forecasts.
Exact algebra does not validate empirical slopes or observed shock labels.
No source PDFs or copyrighted data are redistributed. Source inspection is
recorded separately, and visual/mobile/print QA is not claimed.
