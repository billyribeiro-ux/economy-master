V07-C03: MESA OPERATING CASH AND WORKING CAPITAL
Original synthetic teaching case. Edition boundary: 6 October 2026.
Prepared and checked: 8 October 2026. No observed company data.

RUN
Put v07-c03-analysis.py and v07-c03-inputs.json in one directory.
Run: python3 v07-c03-analysis.py
An optional first argument selects another JSON file. The default input is
relative to the script, not the working directory. Python standard library
only; no installation, network, random seed or environment configuration.
Importing the file prints nothing. build_report(data) returns ordinary JSON
types. The CLI prints a JSON report; invalid input prints a JSON error and
exits 2. Validation uses explicit exceptions and remains active with python -O.

UNITS, DATES AND SUPPLIED EVIDENCE
Mesa Component Supply is a fictional trading corporation. Its quarter is
1 January-31 March 2025, inclusive: 90 days. Every monetary input is a string
in kCU (thousands of CU). One CU has 100 minor units: 1 kCU = 100000 minor
units. At most five decimal kCU digits are allowed, e.g. "0.00001" is one
minor unit. Each input amount has absolute value at most 10000000 kCU.
Ordinary balances and flows are nonnegative; opening retained earnings may
be a signed deficit. Binary floats, bools, NaN, infinity, scientific notation
and silent monetary rounding are rejected. Day count must match the dates
and lie from 1 through 366. JSON objects require the exact documented fields;
duplicate fields and files over 200000 bytes are rejected.

Delivered goods generate the supplied revenue; valid credit sales create
unconditional receivables. Advances are earned only by performance. All
inventory costs, deliveries, collections and loss estimates are external
case evidence. The program proves no recognition or valuation claim. There
are no returns, contractual price changes, inventory losses, tax, interest,
depreciation, FX, acquisitions, owner flows or noninventory trade payables.
Other operating expense is paid currently. Temporary accounts open at zero.
This is not an assertion that every actual GAAP/IFRS contract follows these
conventions, nor an assurance engagement or a general accounting engine.

WHAT THE PROGRAM POSTS
opening_kcu supplies normal balances for cash, gross_receivables, allowance,
inventory, payables, advances, capital and retained_earnings. The allowance
is credit-normal and subtracts from gross receivables. The opening equation
must balance. Debit-positive generated journal entries use this fixed order:
1. Cash sales. 2. Credit sales. 3. Ordinary collections.
4. New customer advances. 5. Earned advances.
6. Cash and credit inventory purchases. 7. Cost of sales.
8. Payments against trade payables. 9. Other expense paid.
10. Writeoffs. 11. Reinstate recovery. 12. Collect recovery.
13. Adjust allowance to supplied target.
These are grouped quarter postings, not a claim about individual event
dates. Inventory purchases are assumed to precede the related deliveries;
their detailed dates and cost allocations are not supplied. Each generated entry balances. Cash, gross
receivables and inventory may not turn negative in that order; payments or
performance may not exceed the recorded payable/advance balances. An edited
scenario needing earlier financing is rejected, rather than treated as an
overdraft with no liability. Do not infer a complete operating calendar or cash feasibility at other dates.

Recoveries are a deliberately bounded subset: the amount recovered was
written off during this same reporting period, so recoveries <= writeoffs.
It is reinstated and collected immediately in the two specified entries.
Ordinary collections exclude recovery. Opening written-off claims or a
reinstatement uncollected at close require a different input model.

aging contains 1-100 uniquely labeled closing gross-balance groups. They
must cover gross closing receivables exactly. Each loss_fraction is a
nonnegative decimal or rational string, at most 32 characters, from 0 to 1.
Each group loss must be an exact minor-unit amount; choose an explicit
rounding policy before extending the model to other estimates. There is no
hidden rounding here. The target is the sum of group expected losses, not
the period expense. The adjustment is:
  expense = target - (opening allowance - writeoffs + recoveries).
Expense may be negative. The pre-adjustment allowance may be debit after
large writeoffs; the supplied closing target is always between zero and
gross claims. A target of 100% for a supplied remaining claim is not an
automatic modeled writeoff. The writeoff decision is a separate input.

Temporary revenue and three expense accounts close to retained earnings.
The report includes debit-positive adjusted and postclosing balances,
generated entries, all cash prefixes, closing statements and 14 exact zero
residuals. Money is reported as exact kCU decimal strings. Day ratios are
exact rational strings (e.g. "71/2"); a zero denominator is JSON null.
Any CCC needing an undefined component is also null. null is not zero.

BASELINE INDEPENDENT TARGETS (kCU UNLESS DAYS)
Opening A = 162; L = 60; E = 102.
Gross receivables = 60+180-150-8+2-2 = 82.
Pre-adjustment allowance = 8-8+2 = 2.
Target = 60*(.05)+20*(.20)+2*(1) = 9; expense = 7; net AR = 73.
Inventory = 80+160-144 = 96; AP = 50+120-130 = 40;
customer advances = 10+12-10 = 12.
Revenue = 230; profit = 47; retained earnings = 69.
Customer cash = 204; supplier cash = 170; other cash = 32; CFO = 2.
Cash = 32; A = 201; L = 52; E = 149.
Gross operating N: 80 to 126, change 46.
  CFO = profit 47 + lossExpense 7 - change 46 - writeoff 8 + recovery 2 = 2.
Net operating N: 72 to 117, change 45; CFO = profit 47 - change 45 = 2.
Do not add loss expense again to the raw net-N bridge.

Endpoint-mean day ratios for this 90-day interval:
gross AR / credit sales: 71/2; inventory / COGS: 55;
AP / credit purchases: 135/4; corresponding CCC: 227/4.
AP / total purchases: 405/16; corresponding CCC: 1043/16.
AP / COGS: 225/8; corresponding CCC: 499/8.
Gross AR / total revenue: 639/23; net AR / credit sales: 125/4.
All these values use interval-average flow, not annual totals. Mixed cash
and credit purchases, margin differences, growth, losses and endpoint
averaging prevent interpreting the chosen CCC as an exact physical elapsed
cash duration. The program does not observe customer-specific payment days.

SEPARATE ALTERNATIVE CASH CALENDAR
Each dated bucket receives all specified cash first, then pays suppliers,
then other expenses. Calendar amounts must sum to the same operating cash
components as the main ledger. Dates must increase within the period.
This is a separate conditional cash proposal, not a second completed ledger
and not a proof that every receivable/inventory cohort fits those dates.
Reconcile detailed operations separately before adopting a real plan.

From opening 30, January ends 8, February would end-8 and March ends 32.
The unfinanced February path is infeasible under no overdraft. With a
certain zero-fee, zero-interest facility available just before any shortfall,
the benchmark draws only what is needed and postpones all repayment to the
end. Minimum committed facility = max(0, minus the lowest raw cash prefix).
Here draw 8 in February, funded month-end cash 8/0/40, and repay 8 after March
payments: final cash 32 and bridge debt 0. Gross CFF+8 and-8 are additional
conditional flows; zero net CFF does not mean funding was unnecessary.
The main ledger's CFF 0 stays separate. Reordering within a monthly bucket
can increase peak need; fees, interest and uncertain receipts are omitted
assumptions, not free credit available in the world.

REPRODUCTION AND TRANSFER
First calculate the targets without opening the program, using the account
rollforwards in the chapter. Compare each account, not just A=L+E. Then:
* Replace the first aging fraction .05 with .15. Target becomes 15, expense 13,
  profit 41, net AR 67, A195, E143 and net N111. Cash and CFO stay 32 and 2.
  Gross DSO stays 35.5; net DSO falls to 29.75 without faster collection.
* To implement the retention case, change writeoffs 8 to 10 and reduce the
  first aging gross balance 60 to 58. To keep the target exactly 9, use its
  loss_fraction "3/58" (other group targets remain 4 and 2). Gross AR 80,
  expense 9, profit 45, net AR 71, A199, E147, CFO 2, gross DSO 35.
* Change the cash/credit purchase mix while keeping total purchases 160.
  A coherent experiment holds total supplier cash fixed too: with cash
  purchases k, use credit purchases 160-k and payable settlements 170-k.
  Inventory and closing AP stay 96 and 40, so CFO and profit stay 2 and 47.
  DPO based on credit purchases changes solely through the stated mix.
  At k=160, its denominator is zero: matched DPO and CCC are undefined.
  Other denominators still answer their own questions.
* Reorder the three alternative buckets' cash amounts (retaining increasing
  date labels and the same totals). Compare the facility requirement with
  unchanged endpoint ratios. Do not treat this as a full operations forecast.

The independent repository checker is scripts/check_v07_c03.py. It verifies
hand-derived balances, every exercise, both CFO bridges, all posting signs,
altered allowances/writeoffs/recoveries/purchase shares, funding calendars,
zero denominators, malformed input and deliberately corrupted reports. Its
scope is bounded arithmetic and behavior, not a visual or documentary audit.
