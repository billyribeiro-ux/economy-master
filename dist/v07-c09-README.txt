Financial ratios and business diagnosis — Aster Components
Original synthetic teaching case, authored 8 October 2026.
Library edition boundary: 6 October 2026. No market observation or filing.

FILES AND RUNNING
Keep v07-c09-inputs.json and v07-c09-analysis.py together. Run:
  python3 v07-c09-analysis.py
Or supply another input file:
  python3 v07-c09-analysis.py my-inputs.json
Only Python's standard library is required. No network, installation, file
writes or credentials are used. Importing the module and calling run(data)
prints nothing. run returns an ordinary JSON-serializable dictionary.
All calculations use fractions. A value such as "27/137" is an exact ratio;
multiply by 100 to display its percentage. Null means the denominator is
zero or negative under the lab's reporting convention. No infinity/NaN is
emitted. Near-zero positive denominators remain visible rather than being
silently discarded at an arbitrary threshold. Inspect the supplied averages.

UNITS, TIMING AND ENTITY
All monetary amounts are thousands of fictional currency units (kCU).
Each flow period lasts exactly 360 days, chosen to make comparisons simple;
these are illustrative years, not calendar observations. Opening, end-Y1,
and end-Y2 balance sheets share one standalone entity. All equity is common.
There are no preferred claims, NCI, acquisitions, disposal gains, FX,
receivable impairments, leases, restricted cash, investments or other items.
Only the stated interest-bearing debt and trade payables are liabilities,
apart from any explicitly computed deferred tax liability. Short/long debt
classification is supplied at each close; it does not determine current-year
interest. Interest is the stated incurred/paid flow, not inferred from a
closing-debt coupon. Net borrowing occurs as stated; repayments are separate.
All revenues arise from credit sales; all goods purchases use trade credit.
COGS is inventory expense only; depreciation is separately charged below
gross profit. No inventory write-down or production-cost absorption occurs.
Other operating expense, interest and current tax are paid in the period.
No unpaid tax or operating accrued expense exists. Cash interest and current
tax are operating, capex investing, debt and dividends financing. These are
declared teaching classifications, not universal reporting requirements.

STATEMENT BRIDGES
Collections = sales - increase in receivables.
Credit purchases = COGS + increase in inventory.
Supplier payments = purchases - increase in trade payables.
CFO = collections - suppliers - other opex - interest - current tax.
Closing PPE = opening PPE + capex - book depreciation.
Closing tax base = opening tax base + capex - tax depreciation.
Closing debt = opening debt + borrowing - repayments.
Closing equity = opening equity + net income - dividends.
Closing cash = opening cash + CFO - capex + borrowing - repayments - dividends.
Tax law is fictional: uniform 25% baseline rate, book/tax identical except
depreciation. Current tax is the tax rate times positive taxable profit and
is paid now. All depreciation differences are temporary, all consequences
enter profit, and the supplied full-deferred-tax-support flag is an assumption
requiring independent evidence in a real case. Net DTA = rate times
(tax base minus PPE); negative net DTA is shown as a DTL. Deferred tax expense
equals opening net DTA minus closing net DTA. It is added to NI in the
indirect CFO bridge. Baseline tax/base depreciation 30/40; comparison book
depreciation 50/20. No real jurisdiction's permission to choose either pattern
is asserted. The comparison isolates allocation, not a change in cash or
physical equipment. The identical two-period sum closes the measurement gap.

RATIO DEFINITIONS
Flow/stock performance measures use arithmetic mean opening/closing balances.
Endpoint means are proxies, not transaction-weighted amounts. No intra-year
observations were supplied. Snapshot liquidity and debt/equity use the same
closing date. Quick assets are unrestricted cash plus receivables. DTA is not
quick/current cash. Debt excludes AP; equity multiplier uses total assets,
including the assets financed by AP, so it is not one plus debt/equity.
Operating invested capital = AR + inventory + PPE + DTA - AP - DTL.
Financing reconciliation = debt + common equity - cash.
All cash is excluded in this particular analytical convention; do not treat
the exclusion as evidence that operations need zero minimum cash. A definition
retaining required operating cash would produce a different denominator.
NOPAT = EBIT*(1-rate); it is hypothetical after-tax operating profit, not
actual tax expense, cash flow or a general rule for businesses with tax losses.
ROIC = NOPAT/average invested capital. ROE = NI/average common equity.
Three-factor DuPont = NI/sales * sales/average assets * average assets/average
equity. Five-factor also splits NI/sales into NI/PBT * PBT/EBIT * EBIT/sales.
Days = 360*average balance/matched flow: credit sales for AR, COGS for inventory,
credit purchases for AP. Cash cycle = DSO + DIO - DPO. These aggregate ratios
are not observed invoice durations. Ending debt/EBITDA combines an endpoint
debt obligation with the year's earnings proxy and is labeled accordingly.
It is neither a debt-payoff forecast nor a universal covenant definition.

REPRODUCTION ANCHORS
Baseline Y1: EBIT90, NI56.25, CFO61.25, cash31.25, assets461.25,
debt160, equity236.25, operating capital365. ROE90/349; ROIC27/137.
Baseline Y2: EBIT68, NI36, CFO6, cash17.25, assets572.25,
debt250, equity242.25, operating capital475. ROE48/319; ROIC17/140.
Asset turnover is 960/689 in BOTH years. The comparison yields NI41.25/51,
DTA5/0, unchanged CFO/cash, ROE66/337 then68/309, and ROIC21/134 then4/25.
The terminal balance sheet and two-year net income92.25 agree exactly.

EXPERIMENTS TO EXPLAIN BEFORE RUNNING
1. Change only Y2 closing receivables120 to100: CFO26, cash37.25,
   operating capital455, ROIC51/410. NI, total assets, equity, ROE,
   current ratio and quick ratio stay unchanged. AR converts to cash.
2. Change only Y2 COGS468 to486: EBIT50, NI22.5, CFO-7.5, cash3.75,
   ROIC5/56. Negative CFO is allowed if the stated funding keeps cash >=0.
3. Y2 repay10 at close and current_debt70 to60, leaving supplied interest20:
   cash7.25, debt240, current ratio1129/560, ROIC unchanged. This is a
   closing-date transaction, not an assumption that interest ignores early
   repayments. The quick ratio falls even as the current ratio rises.
4. Change only Y2 sales720 to735 with the same ending AR, costs and finance:
   NI47.25, CFO17.25, cash28.5, equity253.5, ROIC83/560.
Do not change book depreciation without maintaining the comparison's equal
two-period total, unless also extending the model and its terminal contract.

DOMAIN AND LIMITS
Inputs use JSON integers or rational strings; floats, booleans as numbers and
nonfinite values are rejected. Exact field sets are required inside opening
and period records. The model requires two periods, nonnegative input amounts
(opening equity may be signed), nonnegative book/tax profit, valid short-debt
classification, nonnegative physical/book balances, collections, purchases,
supplier payments and ending cash. Unsupported units, tax rates, loss
carryforwards, undocumented tax recognition and implicit cash overdrafts fail.
A true flag does not verify tax evidence. Negative equity and zero denominators
are taught in the chapter and exercised separately by the checker's ratio
tests; a run's balance sheets must still reconcile. The checker independently
reconstructs direct cash, equity, asset and capital movements, ratio identities,
policy neutrality, transfer cases, all solved numerical exercises, invalid
inputs, portable CLI execution, HTML structure and source-ID agreement.
The output cannot decide invoice collectibility, covenant meaning, asset age,
minimum operating cash, peer suitability, fair value or the cause of a trend.
Author/agent verification is not independent human certification.
