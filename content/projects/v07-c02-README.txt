Harbor Instruments: three-statement ledger laboratory
Version: 2026-10-08. Original synthetic instructional transactions, not company data.

FILES AND EXECUTION
Keep v07-c02-analysis.py and v07-c02-inputs.json in the same directory.
Run: python3 v07-c02-analysis.py
An optional input path selects a modified case:
     python3 v07-c02-analysis.py my-harbor-case.json
The default input is resolved relative to the script, not the working directory.
Only Python's standard library is used. No installation, network, randomness,
environment variables or external data are needed. The command emits JSON and
returns zero on success; invalid cases emit a JSON error and return 2. Importing
the program prints nothing. build_report(data) returns a JSON-serializable dict.

ENTITY, DATES AND UNITS
One fictional trading corporation; opening date 2024-12-31 and quarter
2025-01-01 through 2025-03-31. Amount strings are kCU (thousands of currency
units). One CU contains 100 minor units; 1 kCU is exactly 100,000 minor units.
The program converts all amounts to integer minor units before posting; e.g.
"0.00001" kCU is one minor unit. Outputs are exact decimal strings in kCU.
They are not binary floating-point approximations. No rounding is performed.

INPUT CONTRACT
The top-level schema is v07-c02-1. All listed fields are required; unknown fields
are rejected. Opening_debit_balances_kcu supplies every permanent account.
Positive values mean debit balances; negative values mean credit balances.
Thus opening cash is "40" and borrowings "-60". Accumulated depreciation is
a credit-normal contra asset; it is not a liability. Retained earnings can
be a debit deficit. Other permanent balances must have their ordinary sign.
Temporary revenue/expense/gain/dividend accounts start at zero automatically.

Each ordered event contains an id, description, cash_line (or JSON null), and
2 to 20 postings. A posting has account, side (Dr or Cr), and positive
amount_kcu. An account can occur once per event; use a single net posting
for that account. Every entry must balance. Amounts must be decimal strings,
not JSON numbers, scientific notation, booleans, infinity or NaN. At most
five decimal places and 1,000,000 kCU per input amount are allowed. There
may be 1 to 200 events; input files may not exceed 200,000 bytes. Duplicate
JSON field names and event ids are rejected. Dates must be ISO calendar
dates; period_start is the day after opening_date, and end is not earlier.
Current_borrowings_kcu is a supplied maturity classification bounded by
closing borrowings, not a maturity prediction inferred from account names.

The script's fixed chart and cash-line map are readable at its beginning.
The operating lines are customer receipts, supplier payments, wage payments,
insurance payments, rent payments and interest payments. Investing lines
are equipment sale/purchase; financing lines are share issue, borrowing,
principal repayment and dividends. Receipts must be positive and payments
negative in the cash ledger. Every actual cash event requires a line;
an event with no cash must use null. Lines aggregate actual cash postings,
not accrual revenue, disposal gain or net equipment changes.

MAINTAINED ECONOMIC/ACCOUNTING CONVENTIONS
The chapter supplies delivery/expense recognition, cost of goods sold and
depreciation; all credit revenue is collectible. No tax, FX, OCI, cash
equivalents, restricted cash, writeoffs, overdraft, revaluation, merger,
unlisted income, expense, transaction or external adjustment is present.
All inventory payables concern inventory, and all rent expense is paid.
Interest cash is operating; dividends are financing. This is a stated
teaching convention, not a universal or current legal-compliance claim.
Alternative interest classification is taught in Exercise 5, but is not
an option in this fixed benchmark. Changes to those assumptions require
new reconciliation logic as well as changed input amounts.

Shares are issued for cash; dividends are declared and paid together;
there are no direct retained-earnings adjustments. Noncash equipment
additions are solely equipment exchanged directly for a seller note.
Equipment is cost less supplied depreciation; disposal gain can be a loss.
The listed order is the model's payment order. It is not an actual historical
bank calendar. No negative cash balance at any prefix is funded implicitly.
An infeasible path is rejected even if a subsequent loan would make its
ending balance positive. Accrual recognition evidence is supplied by the
case, not inferred solely from the journal's arithmetic.

BASELINE REFERENCE (kCU)
Opening: assets 216 = liabilities 110 + equity 106.
Profit: revenue 190 - COGS 95 - wages 40 - insurance 4 - rent 12
        - interest 6 - depreciation 9 + disposal gain 1 = 25.
Closing retained earnings: 26 + 25 - 8 = 43; share capital 100.
Closing cash 69; receivables 45; inventory 45; prepaid 8;
equipment cost 152, accumulated depreciation 33, net equipment 119.
Assets 286 = liabilities 143 + equity 143. Current assets 167;
current liabilities 71, including current debt 21; noncurrent debt 72.
Direct CFO: receipts 177 - suppliers 95 - wages 38 - insurance 6
            - rent 12 - interest 5 = 21.
Indirect CFO: 25 + 9 - 1 - 15 + 5 - 2 - 5 + 2 + 1 + 2 = 21.
CFI: 5 - 24 = -19. CFF: 20 + 30 - 15 - 8 = 27.
Cash bridge: 40 + 21 - 19 + 27 = 69.
Noncash equipment/seller note: 18, disclosed outside every cash-flow total.
Borrowings: 60 + 30 + 18 - 15 = 93.
Operating noncash working capital: 36 -> 48; increase 12.

PROJECT CHANGES AND EXPECTED RESULTS
Use copies of the input. In event e07, change both posting amounts from 85
to 20. Cash becomes 4; receivables 110; profit remains 25; CFO becomes -44;
CFI -19 and CFF 27; assets and equity remain 286 and 143. A late collection
is not a bad-debt writeoff under the maintained collectibility premise.

Change e07 to 10 instead. The unfunded plan ends at -6 and is rejected at
the final dividend. CFO would be -54, receivables 120 and profit still 25.
Either insert a balanced cash loan of 6 immediately before e23 (unique id,
cash_line borrowing, Dr cash/Cr borrowings), or reduce both e23 amounts to
2 before declaration. Do not do both in the same comparison. Retain the
supplied current debt 21 only if the new loan is stipulated noncurrent;
otherwise update the supplied maturity schedule explicitly.
Borrowing repair: cash 0, assets 292, liabilities 149, debt 99,
retained earnings 43, equity 143. Dividend repair: cash 0, assets 292,
liabilities 143, debt 93, retained earnings 49, equity 149.
Both: profit 25, CFO -54, CFI -19, CFF 33, cash change -40. Neither
repair creates a positive cash buffer or improves operating performance.

CHECKS AND LIMITS
The report preserves opening, adjusted and post-closing debit-positive
balances, all closing entries, the cash path, three statements, equity
bridge, debt/equipment schedules and noncash note disclosure. It checks
trial balances, the accounting equation, each direct operating line
against the relevant account roll-forward, direct/indirect CFO, equity,
cash, dividends, debt, additions, depreciation and disposal bridges.
These checks use explicit validation, not Python assert statements.

The independent repository checker is book/scripts/check_v07_c02.py.
Run it from the repository with python3 book/scripts/check_v07_c02.py.
It recomputes the chapter and all eight solutions with separate arithmetic,
checks several changed collections/funding plans, malformed inputs,
portable command behavior and report mutations. Its check() is quiet.

A WRONG JOURNAL CAN STILL RECONCILE. If a collection of 5 is incorrectly
credited to revenue instead of receivables, profit and receivables both
rise by 5 relative to the correct case. The indirect adjustments cancel;
cash and every numeric bridge can still agree. The checker demonstrates
this limitation and compares the result to the supplied source transaction.
Invoice, delivery and remittance evidence, completeness checks and a
customer subledger remain necessary. Neither exact arithmetic nor a
successful program certifies recognition, lawful distributions, market
value, collectibility, future liquidity or formal reporting compliance.
