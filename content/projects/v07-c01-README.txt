V07-C01 — Transactions and double-entry accounting
Original synthetic Harbor Calibration Services case
Created 8 October 2026; library edition boundary 6 October 2026

FILES AND RUN
Keep these four flat files together:
  v07-c01-transactions.json   documented chart, opening balances and events
  v07-c01-ledger.py           Python 3 standard-library benchmark
  v07-c01-output.json         preserved benchmark result
  v07-c01-README.txt          this guide
Run: python3 v07-c01-ledger.py
Optional input: python3 v07-c01-ledger.py path/to/other-input.json
The default file resolves beside the script, independent of working directory.
Output is JSON on stdout; redirect it to a new file to preserve an experiment.
No network, installation, spreadsheet engine or random seed is required.
Importing the module is quiet; run(parsed_input) returns a dictionary. The CLI
returns status 2 and a JSON error object for rejected input. The checker's quiet
check() independently audits the package; it is not needed to run the download.

PROVENANCE, UNITS AND RECOGNITION
Every company, document, transaction, date and amount is invented by the author
for this chapter. The input contains no empirical data or real customer records.
Source-method references are listed in the chapter and v07-c01-sources.json;
the input and benchmark are original library material.

All input/output amounts are integer US dollar CENTS, not dollar floats.
Divide by 100 to compare with the manuscript's whole-dollar tables.
Positive signed account balance = net debit; negative = net credit.
Entry amounts themselves are strictly positive with a separate Dr/Cr side.
The reporting entity is one fictional corporation. The January 2025 period
starts with zero balances. A normal debit increases assets/expenses/dividends;
a normal credit increases liabilities/capital/revenue. Accumulated depreciation
is a credit contra asset, not debt. Retained earnings can have a debit deficit.

The numerical conventions are stated assumptions, not a conclusion of current
IFRS, US GAAP or any jurisdiction's compliance: historical equipment cost,
straight-line allocation from availability, certain service collectibility,
separately priced completed sessions, equal monthly insurance coverage, supplied
wage evidence and monthly loan interest. No tax, FX, OCI, impairment, inventory
sales, group reporting or lease issue is modeled. The dividend is assumed
permitted and declared/paid on one day; there is no dividend-payable interval.
No overdraft facility is supplied. Correct recognition, legal authority,
completeness, valuation and funding must be evaluated outside arithmetic posting.

TIMING AND INPUT CONTRACT
Each journal entry preserves source, explanation, effective date and recorded
date. Transaction dates run from January 1 through January 29. Six adjustments
have January 31 effective dates and February 2 preparation/recorded dates. The
completion document for A06 is January 30: January 31 is its close-adjustment
effective date, not a claim that the session occurred on that date.

The CLI accepts one optional JSON path (maximum 300000 bytes). Duplicate JSON
keys and nonfinite constants are rejected. The schema must equal
v07-c01-ledger-v1 and synthetic must be true. Metadata requires USD/cent and
ordered ISO calendar reporting dates. The chart contains 1–100 known account
objects, each with a nonempty label and a recognized type, and exactly one
retained account. Opening signed integer balances cover the exact chart, sum to
zero and give temporary accounts zero starting balances. Integer magnitudes are
bounded by 10^12 cents; booleans and floats are not monetary amounts.

Each of transactions and adjustments is a list of at most 200 entries. IDs are
unique across both lists; source/explanation are nonempty. Effective dates are
ordered within each list and lie inside the period; adjustments are effective
at period end. Recorded dates cannot precede effective dates. Each entry has
at least two distinct known accounts and exactly account/side/cents in each
line; sides are Dr or Cr; amounts are positive; total debit equals total credit.
The selected wage followup uses asset/payable/expense accounts of the declared
types. Its reversal is after the reporting period, no later than payment.
Payment must cover the entire nonnegative prior wage accrual; partial settlement
is outside this helper's contract. The supported chart types are asset,
contra_asset, liability, capital, retained, revenue, expense and distribution.
Malformed API inputs can raise ValueError, KeyError or TypeError. The CLI turns
these into a bounded error message; no successful report is emitted for them.

CLOSING AND SELECTED FOLLOWUP
The benchmark posts 11 ordinary entries, six adjustments and three derived
closing entries; it saves all 20 cumulative balance vectors. It transfers each
revenue/expense/distribution balance directly to Retained earnings. An Income
summary intermediate account is not required for this instructional convention.
Assets, liabilities, total equity and cash do not change on closing. The saved
adjusted snapshot contains January profit; post-closing open_profit_cents = 0
means only that temporary period accumulators have reset.

The February illustration contains ONLY selected wage entries, not a full
February income statement or a claim of no other activity. The original 250 USD
accrual is included in a 600 USD payment on February 5. The direct route debits
Payable 250 and current Expense 350. The optional route reverses on February 1
and records the full 600 payroll expense on payment. The reversal can be prepared
on February 2 with the January close; its recorded date is not backdated to
February 1. Derived entries' recorded dates are the later of effective date and
close preparation date. Both completed routes produce the same account vector.
A reversal never discharges the actual obligation; an interim report before
payment must restore the unpaid accrual as appropriate. Do not mix both routes.

EXPECTED TARGETS (USD, unlike stored cents)
Unadjusted: Cash 5300; Receivables 1500; Payables 400; Supplies 900;
  Prepaid insurance 1200; Equipment cost 3600; Customer advances 1000;
  Loan 2400; Capital 6000; Revenue 4200; Wages expense 1100; Dividends 400.
  Trial balance 14000 on each side; assets 12500; liabilities 3800;
  provisional profit 3100; equity including open profit/distribution 8700.
Adjusted: Revenue 4450; expenses 2274 = 1350 + 600 + 200 + 100 + 24;
  January profit 2176; Cash 5300; Receivables 1500; Supplies 300;
  Prepaid insurance 1000; Equipment cost 3600; Accumulated depreciation 100;
  Trade payables 400; Customer advances 750; Wages payable 250;
  Interest payable 24; Loan 2400. Trial balance 14374 on each side.
  Total assets after depreciation 11600 = liabilities 3824 + equity 7776.
Post-closing: all temporary accounts zero; Retained earnings credit 1776;
  total equity 7776 unchanged; trial balance 11700 each side.
  The difference from total assets 11600 is the separate contra asset 100.
Selected wage followup: Cash 4700; Wages payable zero; new wage expense 350;
  both completed routes identical. Retained earnings is not a cash fund.

WHAT THE PROGRAM DOES NOT VALIDATE
The benchmark checks arithmetic and supplied classifications, not evidence of
an actual economic event. J01's capital credit can be changed to a revenue credit
and still balance; profit then rises incorrectly by 6000 USD while total equity
is unchanged. Omitting a whole balanced entry also passes balance tests. The
independent checker deliberately demonstrates these limits, and demonstrates a
correction of a receivable collection wrongly credited to revenue.

Opposite-normal-balance flags require investigation, not automatic rejection.
Retained deficits are allowed. In particular, negative Cash remains possible in
a proposed balanced input and is flagged; it is NOT accepted funding under the
case's no-overdraft assumption. Actual cash availability must be checked before
payment. Generated entry metadata does not establish authorization or occurrence.
Source labels, account names and a balanced equation cannot certify recognition.

EXPERIMENTS
Work on a copy. Compare the two wage routes with payments of 250, 600 and 1000
USD (all settle the 250 prior accrual). Inspect what closes and what persists.
Then try a balanced wrong capital/revenue classification and a wholly omitted
dividend. Explain which source evidence detects each error. Finally increase
cash-paid wages enough to make Cash negative: explain why balance survives
while the proposed payment plan becomes infeasible. Restore the original input
before comparing with the preserved output. No experiment estimates an empirical
relationship, current legal rule or forecast of a real business.
