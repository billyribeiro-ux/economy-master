Cedar allocation council — Volume 9, Chapter 9

These are authored synthetic teaching models. They contain no observed or
forecast market data. Different panels have different explicitly stated
preferences, cash dates and restrictions; their choices must not be pooled
into a single portfolio. Currency units are CU; gross returns include principal.

OFFLINE EXECUTION
Use Python 3 with its standard library; no installation or network is needed.
Keep the analysis and input file in the same folder. From any working directory:
  python3 /path/to/v09-c09-analysis.py
or
  python3 /path/to/v09-c09-analysis.py --input /path/to/v09-c09-inputs.json
Use --output /path/to/result.json to save output instead of printing it.
The default input path is resolved relative to the script, not the working
directory. A failed input contract exits with ValueError, including under
python3 -O. Every named policy convention is checked; changing its label is
not a way to change the model.

NUMBERS AND SCHEMA
Use JSON integers or exact rational/decimal strings, such as "1/3" or "0.02".
Booleans and binary JSON floats are rejected. Absolute rational inputs and
denominators may not exceed 10^9. These are finite-fixture guardrails, not
financial restrictions. Each object has exact required keys; unsupported
fields are rejected. Fractions in the output are reduced strings, or integers
when their denominator is one. Fields ending in _approx use finite floating
point for square roots, logarithms and the CRRA tree. A tiny residual near
10^-16 is floating-point rounding, not a materially nonzero first derivative.

PANELS
1. Liability surplus:
  Four independent equiprobable sign states. Nonnegative liability and income
  at date 1; positive financial wealth; a beginning cash reserve in [0,W].
  The safe gross return is in (0,10]; risky gross returns must be positive
  and lie on opposite sides of it. The nonzero sign loading and positive
  gamma give strict curvature. The objective is explicitly mean surplus
  minus gamma/2 times its variance, not general expected utility.
  Exact state cash flows, moment risks, a risky-demand decomposition and the
  active-constraint derivative are returned. The reserve is measured before
  the safe return; terminal surplus is distinct from asset wealth.

2. Lifecycle:
  One-period log terminal wealth, safe gross return one, no costs, borrowing
  or shorts. Up probability in [0.001,0.999], up gross in (1,10], down gross
  in [0.001,1). H=H0+h*(G-1) is a nontradable terminal endowment.
  Household wealth is positive, H0 nonnegative, endowment nonnegative in
  both states, and terminal resources positive throughout [0,W]. Supply
  1–20 uniquely named households. h may have either sign when those conditions
  hold. The formula solves this two-state spanned endowment only; no extra
  unspanned shock is silently converted into an exposure coefficient.
  These households are balance-sheet comparisons, not a saving simulation.

3. Dynamic policy:
  Exactly two periods; terminal utility -1/W (relative risk aversion 2), no
  flows/costs, safe gross return one, fractions in [0,1]. Each binary node
  satisfies the same probability and gross-return domain as panel 2. The
  initial realized return reveals which period-2 law applies. The investor
  knows all conditional laws at date 0 but cannot select a first trade after
  seeing that realization. The code solves the convex reciprocal problem
  analytically at child nodes, then at the initial node using their value
  coefficients. It returns every terminal path, its physical probability,
  funded intermediate positions and utility. The myopic comparison optimizes
  period 1 in isolation but still makes optimal conditional trades thereafter.
  The extreme (4,0.25) return pair is deliberately chosen for exact algebra;
  it is not a plausible market estimate or a promised opportunity.

4. Mechanical rebalancing:
  Nonnegative marked risky and cash values with positive total wealth.
  Target in [0,1], proportional fee in [0,1), paid from cash immediately
  on absolute risky CU traded. Target wealth is after paying the fee.
  No borrowing; no cash return during trading or the next reported period.
  Supply 1–20 positive next-period gross risky scenarios, each at most 10.
  These are alternative deterministic outcomes with no probabilities.

5. Mean-variance no-trade interval:
  Positive wealth, variance and gamma; mean excess greater than -1; existing
  risky CU in [0,W]; fee in [0,1). Safe gross return one and zero liability
  covariance. The supplied mean and variance define a stipulated one-period
  criterion, not an estimated distribution. The code derives the no-trade
  interval, then enforces cash funding including the fee. It does not solve
  a general multiperiod problem with transaction costs. Up to 20 existing
  positions can be evaluated under the same moments.

6. Mean uncertainty:
  Same funded objective, plus a nonnegative half-width about an estimated
  mean. The interval's lower mean must exceed -1. Because every feasible
  risky holding is nonnegative, the lower endpoint is the worst case.
  The point-forecast and worst-case choices are separately optimized and
  evaluated at that same adverse mean. Variance and gamma are held fixed.
  The interval carries no probability or confidence level. Permitting shorts
  or a coupled uncertainty set requires a different minimization.

7. Horizon identities:
  Independent identically distributed finite-variance log increments with
  supplied mean and nonnegative standard deviation. At 1–100 integer periods,
  cumulative variance is T*s^2 and average variance s^2/T. Up to 20 horizons.
  These are moment identities, not normality, shortfall probabilities or
  claims about real-world serial dependence.

8. Withdrawals:
  Positive initial wealth, nonnegative equal payment after each of two
  positive gross returns (each at most 10). Both return orderings must fund
  each payment; a shortfall is rejected rather than financed by a hidden loan.
  Exact ledgers and the no-payment comparison are reported.

SUPPORTED INVESTIGATIONS
Change income_u from4 to12 in panel1, and then gamma to"0.04". Compare the
hedge sign and risk exposure. Set reserve40 to see the binding cash cap.
Add a household with W40, H0=60, h80 to inspect a no-short boundary.
Exchange the two dynamic continuation objects without changing the initial
law: the initial hedge is then prohibited by the no-short constraint.
For an IID experiment use the original after_down law at all three nodes.
Use risky48/cash64 for the buy-side rebalancing calculation; check post-fee
weights. Increase a band fee, or use mean0.2, to expose no-trade or funding
boundaries. Narrow the uncertainty half-width to"0.005"; keeping50 becomes
optimal. Keep a copy of the original fixture for reference comparison.

EVIDENCE AND LIMITS
The full reference output is preserved, including all dated cash rows. The
manifest hashes this README, inputs, analysis and reference output; it does
not hash itself. The separate chapter checker uses state-by-state moments,
quadratic interpolation, bracketed derivatives, exhaustive coarse policy
comparisons, funding identities and allowed/invalid contract interventions.
These checks support arithmetic and reproducibility. They do not validate
forecast inputs, preference estimates, real-world liquidity or an investment
recommendation. Full proofs and all exercise solutions are in the chapter.
Neither author review nor computational checks are external human certification.
