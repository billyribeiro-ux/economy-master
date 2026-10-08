VOLUME 8 CHAPTER 3 — MARINER CALIBRATION SERVICES CAPITAL-PATH VALUATION LAB

This is an original fictional teaching case in nominal kCU, with annual periods.
There is no market data, API, package installation or network dependency.

FILES
  v08-c03-inputs.json   Exact original inputs and maintained assumptions.
  v08-c03-analysis.py   Standard-library Python benchmark.
  v08-c03-output.json   Preserved exact default result.
  v08-c03-README.txt    This guide.

RUN
Keep all files together. Run:
  python3 v08-c03-analysis.py
For a separate edited assumptions file:
  python3 v08-c03-analysis.py my-inputs.json
The program prints JSON and never overwrites inputs or output. Monetary and
ratio values use exact rational strings. Convert to decimals only for display.
Importing the module is quiet. benchmark(data=None) returns JSON-compatible data;
None loads the adjacent input file. No caller working-directory assumption is made.

TIMING AND ECONOMICS
Capital K at each opening produces that year's NOPAT at the supplied ROIC.
Reinvestment occurs at year-end and earns its first return in the next year.
The return applies to all opening capital, so competitive decline reduces the
earnings of old assets as well as the return earned on the latest additions.
The final explicit ROIC must already equal stable ROIC, and its reinvestment_rate
must be the word "terminal". The program then sets that rate to g/stable_ROIC.
The same rule applies in the first continuing year. It therefore recomputes
final explicit FCFF and invested capital whenever terminal g changes.

Net PPE and operating NWC are 80%/20% of capital in the base case. Depreciation
is 5% of opening net PPE; capex equals that amount plus 80% of net investment.
This is an assumed replacement policy, not an estimate from real asset records.
Sales equal beginning capital; EBIT is NOPAT/(1-tax rate); cash operating cost
is sales minus EBIT minus depreciation. This field means operating cost excluding
D&A before working-capital settlement adjustments, not an independently observed
supplier payment. The NWC bridge supplies those timing adjustments. Operating
tax is fully paid/usable.
The output reconstructs FCFF both as NOPAT minus net investment and through
cash operating cost, paid tax, NWC and capex. No financing interest enters FCFF.

BASE BENCHMARK
Opening capital: 500. Explicit returns: 20%, 16%, 12%, 10%.
Explicit reinvestment: 50%, 25%, 25%, then terminal 30%.
NOPAT: 100, 88, 68.64, 58.916.
FCFF: 50, 66, 51.48, 41.2412.
Closing capital: 550, 572, 589.16, 606.8348.
Year-5 NOPAT: 60.68348; year-5 FCFF: 42.478436.
Terminal value at date 4: 606.8348.
Operating value: 70340/121, approximately 581.322314 kCU.
An independent economic-profit identity adds the PV of 50, 33, 11.44 and zero
to opening capital 500. Terminal ROIC equals r, leaving no terminal premium to K.
Equity value adds separately valued excess cash 30 and nonoperating assets 15,
then subtracts the supplied debt market claim 200 once: 51585/121 kCU.
At 20 thousand shares, per-share value is 10317/484 CU.

EXPERIMENTS
1. Compare all nine grid cells. Rates are 8%, 10%, 12%; growth rates 0%, 3%, 6%.
   Stable ROIC remains 10%. Find the growth-neutral row and explain why the
   terminal share changes within that row although total value is constant.
2. Extend the horizon to six without changing economics: change year 4's
   reinvestment_rate from "terminal" to "3/10"; add year 5 with ROIC "1/10"
   and reinvestment_rate "3/10"; add year 6 with ROIC "1/10" and rate "terminal".
   The base-case operating value must remain 70340/121; terminal share falls.
   When making a terminal-g sensitivity on this six-year input, the added
   fixed year-4/year-5 policies stay at 30%, so it is a different date of policy
   change than the original four-year sensitivity. Compare horizons at the
   same actual policy path, not merely with the same final growth label.
3. Change early ROIC while preserving valid operating margins. Separate the
   resulting change in old-capital earnings from earnings on new investment.
4. Deliberately set g equal to r, or make final explicit ROIC differ from stable
   ROIC. Read the error; do not replace it with a clipped denominator or a
   hidden terminal capital jump. Restore an explicit admissible transition.

BOUNDED INPUT CONTRACT
Inputs are exact integer values or rational/decimal strings; binary floats,
Booleans as numerical parameters, undefined ratios and zero denominators are
rejected. K, NOPAT, ROIC, turnover and share count are positive. Tax lies in
[0,1); depreciation and PPE share lie in [0,1]. Reinvestment lies in [0,1].
Stable growth is nonnegative, below r and no greater than stable ROIC. Every
period must have nonnegative implied cash operating cost. Excess cash, other
asset values and debt claim values are nonnegative; residual equity must be
nonnegative because no distress/limited-liability model is implemented.
The model excludes acquisitions, currency/capital revaluations, impairment,
deferred tax, negative-profit turnarounds, externally funded reinvestment above
NOPAT, liquidation, debt schedules and all intra-year funding calendars.
Those exclusions define this lab, not the valuation possibilities of real firms.

INTERPRETATION
All discount rates and operating/tax inputs are hypothetical. A sensitivity
table is not an uncertainty distribution and a closed equation does not verify
customer demand, future returns, current law or an appropriate discount rate.
The terminal share is a horizon statistic, not a probability of model failure
or a measure of the fraction of value created by permanent competitive advantage.
