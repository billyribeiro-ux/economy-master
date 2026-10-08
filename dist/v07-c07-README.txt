Northstar Calibration — original two-period tax and provision laboratory

Run python3 v07-c07-analysis.py with v07-c07-inputs.json beside it.
An optional first argument selects a modified JSON input. The program uses
only the Python standard library, writes exact JSON to stdout and makes no
network calls or persistent changes. Importing it produces no output.

All monetary inputs are kCU, thousands of fictional currency units. Rates are
fractions, not percentages: "1/5" means 20%. Use exact integer or fraction /
decimal string amounts. Floating-point and Boolean inputs are rejected.

The two annual periods are fictional. The rules are stipulated teaching tax
law, not the law of a real country. One company receives equity cash100 and
buys equipment60 at date0. Both book and tax schedules allocate the full cost
over two years with no residual or disposal. The default book charges30/30
and tax deductions50/10 create a temporary difference that fully reverses.
The current model accepts accelerated or equal first-year tax depreciation.

All service revenue is earned and collected in its listed period. Ordinary
expenses are consumed, paid and tax-deductible in that period. Fines are
consumed/paid book expenses but never deductible under the supplied law.
Completed service contracts create a year1 repair obligation; its supported
estimate is expensed then. The entire actual settlement occurs in year2 and
is tax-deductible only then. Any difference between the earlier estimate and
settlement is a year2 expense or release, not another payment.

Both tax rates are already enacted at year1 close. The second rate measures
the year1 deferred consequences reversing in year2. All tax movements belong
to profit in this case. Full deferred-tax-asset recognition is stipulated to
be supported by available future taxable resources, not established by this
program. The code requires supplied year2 taxable resources before repairs
to cover both the estimate and actual settlement. Forecast quality, legal
deductibility, separate tax categories, expiry and reporting exceptions need
evidence outside this numerical exercise. No loss carryforwards are modeled.

Year1 tax cash may settle at most its current charge. Year2 pays all opening
current tax payable plus its current charge. Overpayments and refunds are
outside this fixed case. DTA and DTL are shown gross; an arithmetic net does
not establish real presentation/offset rights. There are no acquisitions,
equity/OCI tax effects, financing, dividends or other working-capital items.
Cash is checked at date0 and reporting-period closes. Individual intra-year
receipt/payment dates are not supplied or certified as feasible.

Default benchmark (kCU)
Year1: PBT58, taxable55, current tax11, cash tax8/payable3, DTA2.4/DTL4,
deferred expense1.6, total tax12.6, NI45.4, CFO92, cash132.
Assets164.4 = liabilities19 + equity145.4.
Year2: PBT40, taxable48, current tax9.6, cash tax12.6/payable0,
DTA0/DTL0, deferred expense-1.6, total tax8, NI32, CFO45.4.
Closing cash177.4 is the only asset and equals equity; all liabilities settle.
Total tax cash/expense20.6; total NI77.4; total CFO137.4 less initial capex60
equals NI and the increase in cash over original contributed equity100.

Experiments to predict before running
1. Change year1_repair_estimate to20, leaving settlement12. NI becomes39/38.4,
   with unchanged cash. This shows a timing consequence, not evidence that20
   is an appropriate estimate. Whether a reserve is reasonable requires the
   information available when it was made.
2. Change book_depreciation to["40","20"]. NI becomes37.4/40 while CFO and
   terminal wealth are unchanged; total tax is still20.6.
3. Change year1_tax_cash_paid to11. CFO becomes89/48.4 and year1cash129;
   both NI figures and terminal cash177.4 are unchanged.
4. Change current_tax_rates to["1/5","1/4"]. The future rate was enacted
   by year1 close: DTL5/DTA3, year1NI45; year2NI30, cash tax15 and CFO43.
   Terminal cash/equity175 reflects a real lifetime cash-tax increase2.4.
5. Change year2_repair_settlement to16. Year2 expense4 accompanies settlement
   of the opening provision12; taxable profit falls4. Trace both tax and cash.

The chapter additionally teaches tax bases, limited DTA recognition,
discounted provisions, earnings/cash gaps and transparent normalization.
Those are separate supplied cases, not undisclosed Northstar transactions.
The repository checker tests exact financial identities and meaningful
changes. Neither code nor balanced accounts verifies occurrence, estimates,
recognition evidence, current reporting compliance or the absence of fraud.
