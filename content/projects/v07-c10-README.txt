Lumen Instrument Supply — an original conditional two-year forecast

Place v07-c10-analysis.py and v07-c10-inputs.json together, then run:
  python3 v07-c10-analysis.py
An optional first argument supplies a modified input JSON. The program uses
only the standard library and prints exact JSON; it makes no network calls
and writes no files. Import forecast(data) for the same quiet API.

PROVENANCE AND UNITS
All observations, contracts, dates and policies are author-created synthetic
teaching inputs. No real company, market estimate, probability, bank approval
or current tax law is represented. Money is kCU, quantity thousands of units,
unit price/cost CU, and rates annual fractions. Strings such as "1/10" mean
exact fractions, not percentages. Exact integers and rational/decimal strings
are supported. Boolean and floating-point financial inputs are rejected.

MODEL CONTRACT
The fixed horizon is two illustrative annual periods. Opening cash20, AR40,
inventory30 and net equipment110 equal AP25, term debt50 and equity125.
The opening balance sheet must reconcile. Every sale/purchase is on credit;
the closing balances determine collections and supplier payments. No writeoff,
refund, foreign currency, acquisition, lease, impairment or disposal is modeled.
Cash operating overhead is paid as incurred. Purchases equal COGS plus the
inventory increase. The AP fraction uses purchases, NOT COGS.

Old assets consume20 in each year. Capex is paid at each final date and starts
service the following year, with zero residual and five-year straight-line life.
Tax depreciation equals book depreciation. There are no temporary differences
or tax-payment lags. The20% tax applies to nonnegative PBT; losses are rejected
because no refund/carryforward/recognition regime has been supplied.

Debt interest is10% of beginning balances. Term debt stays50 and does not mature
within the two-year horizon. Revolver changes happen at the final date after
the annual interest determination, coordinated with capital spending and the
dividend. They have no current-year interest under this supplied convention.
Interest and tax cash are operating; investment cash is capex; financing cash
is debt movement less dividend. This is not a framework-compliance claim.

Cash buffer20 is maintained at annual closes. Excess pays the revolver down to
zero, after which cash can exceed20. Maximum TOTAL revolver outstanding is60,
not60 of extra draws per year. No automatic share issue or term prepayment is
allowed. Annual feasibility does not check intrayear cash availability, real
covenants, legal payout restrictions or an actual bank's willingness to lend.

BASELINE ANCHORS (kCU)
Year1: revenue500, COGS325, purchases360, receipts480, supplier cash349,
depreciation20, EBIT55, interest5, tax10, NI40, change in operating WC44,
CFO16, CFI-50, revolver draw44, financing cash34. Closing cash20, AR60,
inventory65, PPE140, AP36, term50, revolver44, equity155; totals285.
Year2: revenue600, COGS390, purchases403, receipts588, supplier cash398.7,
depreciation30, EBIT70, interest9.4, tax12.12, NI48.48, change in WC20.7,
CFO57.78, CFI-30, revolver repayment17.78, financing cash-27.78.
Closing cash20, AR72, inventory78, PPE140, AP40.3, term50, revolver26.22,
equity193.48; totals310. Every printed residual is exactly zero.
Rational output such as "1311/50" represents26.22 exactly; it is not a count.

MEANINGFUL EXPERIMENTS
1. Set first-year receivables_sales to"1/5". NI remains40 but CFO falls to-24.
   Required revolver84 exceeds limit60 by24. The program returns an explicit
   funding-shortfall object and stops before asserting a feasible closing
   balance sheet or later forecast. Cash after maximum draw would be-4; the
   gap against the required20 is24. These two shortfall measures differ.
2. In that slow-collection case, set first-year dividend to0 and capex to36.
   Required revolver60 meets the limit, cash20, equipment126, equity165 and
   total assets311. Operating feasibility of the deferred investment remains
   an external assumption; subsequent depreciation/interest also change.
3. Return to baseline and set first-year receivables_sales to"1/10".
   Receipts490, CFO26, revolver34 and year1 assets275. The collection timing
   changes opening AR for year2 and reduces opening-debt interest by1.
4. Return to baseline and set first-year capex to40. Year1 profit/CFO do not
   change; revolver34/PPE130. Year2 depreciation28/interest8.4/NI50.88.

SEPARATE AVERAGE-DEBT EXAMPLE
average_debt_closure accepts six Fraction values (cash before revolver interest
and financing, opening debt, minimum cash, interest rate, tax rate, limit).
The first cash input can be negative. Its tax-benefit assumption REQUIRES
sufficient positive taxable profit; the helper does not establish that evidence.
The manuscript explicitly checks the positive-profit branch of both examples.
For(-8,10,20,1/10,1/5,50), required debt40, interest2.5, cash20. With limit35,
feasible=False and the cash gap at the limit is4.8. Returned required debt and
cash describe the unconstrained solution, not an authorized draw beyond a limit.

The checker independently reconstructs signed transactions and all determinate
exercise anchors, checks financing/cash identities and domain boundaries, and
detects economically meaningful errors. A passing test does not verify demand,
capacity, tax treatment, lender access or the absence of omitted obligations.
