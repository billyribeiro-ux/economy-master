V08-C04 — Risk, cost of capital and WACC

Purpose and provenance
All cases and state distributions are original fictional teaching examples.
No actual company, market quote, date-specific tax law or external data is used.
Money is kCU. Rates are annual effective decimal strings. Cash occurs at each
year-end; the one-period case liquidates completely at date 1, and the finite
APV project ends after year 3 with no continuation. All case assumptions are
in the chapter; the small lab does not estimate real market parameters.

Run
Keep v08-c04-analysis.py and v08-c04-inputs.json in the same directory.
Run: python3 v08-c04-analysis.py
An optional first argument selects a modified input JSON file. Python's
standard library is sufficient. There are no packages, network calls,
environment variables or credentials. JSON output is written to stdout.
v08-c04-output.json is the reference output. The default input is resolved
relative to the script, so execution also works from another directory.

Four cases
1. The four equally probable market/residual shocks are centered deviations,
not observed returns. The script centers the constructed claims when computing
covariance. Claim x has beta 1.5 and variance 0.0121; z has beta 0.5 and
variance 0.0157. A supplied 3% risk-free rate and 5% equity premium imply
10.5% and 5.5% conditional CAPM returns. These rates are not estimated by
averaging the zero-mean shock columns.

2. The one-period case is jointly calibrated: E 700, D 300, required equity
return 9%, debt 3%, fully usable tax 25%, expected operating cash 1069.75.
WACC is 6.975%, giving value 1000. Investor cash is equity 763 plus debt 309,
funded by operating cash 1069.75 plus shield 2.25. State payoffs have equity
beta 1.2 and cover debt in every state. Tax capacity is separately stipulated;
coverage alone does not prove usable deductions. Invalid changes that break
the supplied cash/claim pricing relation are rejected. This is a reconciled
teaching model, not a solver for arbitrary observed prices.
The shield is worth 2.184466; unlevered value 997.815534 and beta 0.841839
give an unlevered rate 7.209195%. APV also equals 1000. Book weights give
5.625% and the incorrect value 1012.781065.

3. The no-tax comparable has peer equity 400, debt 200, betas 1.6 and 0.2.
Operating beta is 1.133333. Target D/V 20% and debt beta 0.2 give equity
beta 1.366667 and cost 9.833333%. Debt costs 4%; the no-tax WACC 8.666667%
equals the unlevered cost. No tax-adjusted perpetual-debt formula is used.

4. The finite APV project costs 125 and has expected FCFF 48, 53, 58 at a
compatible unlevered return 10%. Debt balances 60, 40, 20, 0 are contracted,
with interest 4% on opening balances and 20 principal paid each year.
Certain current tax savings at 25% are 0.6, 0.4, 0.2. Their certainty is a
stated payoff/tax-capacity assumption, not inferred from expected FCFF.
Operating value 131.014275 plus shield PV 1.124545 gives value 132.138820
and NPV 7.138820. Debt service 22.4, 21.6, 20.8 has PV 60 at 4%. Equity
value 72.138820 exceeds its initial 65 contribution by the same NPV.

Meaningful variation
Change only finite_apv.tax_use in a copy of the inputs:
- current: the baseline payments and NPV 7.138820.
- deferred_to_final: all credits are certain and paid at date 3, without
  expiry; shield PV 1.066796 and NPV 7.081071.
- none: permanently disallowed deductions; shield PV 0 and NPV 6.014275.
Compare payment dates, not just the sum of credits. Uncertain tax use requires
an additional state/risk model; this script does not silently approximate it.
The finite loan does not produce a perpetual shield worth tax times initial
debt. Borrowing proceeds are not added to APV without the debt obligation.

Numerics and scope
Inputs use integers or rational/decimal strings and are evaluated as exact
Fraction objects. Only final JSON serialization uses floating-point numbers.
The independent book checker recomputes results without calling these formula
helpers, audits the exercises, checks meaningful domain failures and compares
the portable CLI with the exact in-memory calculation. It does not validate
actual forecast assumptions, market efficiency, tax compliance, beta sampling
uncertainty or visual/mobile/print layout.
