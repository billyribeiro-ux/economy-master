V07 C12 — Atlas Field Systems: accounting integration

Provenance and execution
This is an original synthetic teaching case, not observed company data or
authenticated evidence. Monetary units are kCU (thousands of fictional currency
units), not CU, dollars or millions. The period is one year. Keep the three
companion files together and run:
  python3 v07-c12-analysis.py
An optional first argument supplies another input JSON file. Standard library
only; no network, installation or files written. Exact rational amounts are
returned as JSON strings. The default input includes the demonstrated 40
service-revenue correction; it is not the uncorrected draft.

Model contract
One entity, no acquisitions, FX, leases, disposals, deferred tax, OCI or hidden
accounts. All interest and tax cash is operating under the stipulated display;
capex is investing, principal/dividends/equity financing. No actual accounting
framework or tax jurisdiction is represented. Fictional current tax is20% of
corrected positive book pretax profit. Tax cash16 is fixed; a correction changes
tax payable rather than inventing a cash refund. This fixture rejects current-
tax receivables, refunds and losses instead of silently modeling them.

The draft balance sheet opens at cash80, receivables120, inventory100, PPE300;
payables90, tax payable0, debt250, equity260. It reports revenue1000, COGS600,
gross operating cash costs215, cash settlement recovery15, depreciation40,
interest20, tax28 and NI112. Closing reported AR200/inventory150/AP120,
capex60, debt principal paid20 and dividends10 give CFO64, cash54, PPE320,
tax payable12, debt230, equity362; both sides equal724.

The gross cash215 comprises ordinary operations170, recurring marketing25 and
severance20. The separate favorable cash settlement15 is not an omitted bank
receipt. It reduces net operating expense from215 to200.

The case stipulates an unperformed January service erroneously in December
revenue/AR40, with no unconditional payment right, no receipt and no current
expense or inventory release. This establishes the accounting reversal under
the supplied recognition facts. It does not establish who intended what.
Optional capitalized-repair corrections concern a cash payment already in the
capex total, with no future benefit and no current depreciation on that item.
They reduce PPE and move cash classification from investing to operating.

Default corrected result
Revenue960, EBITDA160, EBIT120, PBT100, tax20, NI80. Closing AR160, tax payable4,
PPE320, cash54, debt230 and equity330 give A684=L354+E330. Customer cash920,
supplier cash620, net other cash200, interest20 and paid tax16 give CFO64.
The indirect bridge80+40-40-50+30+4 gives the same64.

Supplied loan test, not a universal definition
Eligible cash=total cash minus restricted cash.
Net debt=max(0,closing principal minus eligible cash).
Covenant EBITDA=corrected EBIT+depreciation+min(qualifying severance,10).
Pass requires positive covenant EBITDA, net debt/EBITDA<=1 and eligible cash>=40.
No other add-backs, projected earnings or management normalization enter.
Default net debt176 / covenant EBITDA170 fails leverage; numerator-equivalent
debt headroom is-6. Cash headroom14 passes. Both conditions must pass.
Normalization is separate: EBITDA160+severance20-settlement15=165, on stated
nonrecurrence assumptions. Marketing25 remains a recurring economic cost.

Experiments and expected results
1. corrections.premature_revenue=0 reproduces the uncorrected draft:
   NI112, CFO64, A724; covenant EBITDA210 and debt headroom34.
2. Keep default correction40; set actions.new_equity=6:
   cash60, equity336, debt230, net debt170; both tests pass at the boundary.
3. Instead set actions.extra_debt_payment=6 and equity=0:
   cash48, debt224, net debt176; leverage still fails, cash headroom8.
4. Set new_equity=6 and extra_debt_payment=6:
   cash54, debt224, net debt170; both tests pass.
5. Restore actions to zero and set corrections.capitalized_repair=15:
   EBIT105,tax17,NI68; CFO49,investing-45,financing-30,cash54;
   PPE305,tax payable1,equity318,A669=L351+E318;
   covenant EBITDA155,net debt176,debt headroom-21.
6. With repair0, set premature_revenue=30 and restricted_cash=10:
   NI88,AR170,tax payable6,CFO64,cash54; eligible cash44,net debt186,
   covenant EBITDA180,debt headroom-6,cash headroom4.
7. Set growth.receivables=72 instead of48:
   growth NI stays67.2; incremental CFO becomes-10.8,cash after investment-40.8.

The evidence_facts strings describe the original supplied case and are not
parsed as computational inputs. Changing the reversal amount is a hypothetical
change in established facts; it does not authorize selecting a preferred error
amount despite unchanged real evidence. State that scenario change explicitly.

All action fields represent hypothetical transactions completed before the
modeled measurement date. Do not recast a later receipt as historical cash or
claim a post-test cure without the agreement's authority. Intra-year funding,
waivers, notice/acceleration, lender discretion and other covenants are outside
this model. The minimum-cash test is a supplied year-end constraint.

Growth module
This is an incremental plan relative to an otherwise identical comparator,
not a complete second-year forecast. Twenty extra installations at12 with
unit COGS7.5 give EBITDA90. New capex30/depreciation6, tax16.8 paid in period,
AR48/inventory30/AP18 give NI67.2,CFO13.2 and cash change-16.8.
The balance change is cash-16.8+AR48+stock30+PPE24=85.2=AP18+equity67.2.
No extra fixed cash or interest is assumed. Positive earnings do not eliminate
the16.8 funding needed to preserve comparator cash. Payment dates may require
more temporary cash. These are supplied demand/capacity/cost assumptions.

Evidence requests and instructor reasoning criteria
The chapter's evidence table is an analysis plan, not a claim to have collected
records. Prioritize the service contract/acceptance/entry trail; bank restrictions
and executed loan agreement/test dates; then receivable cohorts, matched receipts,
inventory aging and the nature of capital/normalization items. Preserve versions
and contradictory evidence. Distinguish accounting misstatement from intent.
Credit a student for matching a request to a specific assertion and decision;
do not credit generic 'check the records' or unsupported fraud/solvency labels.
For normalization, require both gains and losses, recurrence evidence, a bridge
to corrected profit and separate covenant definitions. For any correction,
require the balance sheet, profit, tax, cash-flow classification and total-cash
consequences. For financing, require the source of cash and measurement date.
Open decisions can have several defensible answers; grade these reasons rather
than agreement with a single funding preference.

Validation boundaries
Exact nonnegative integer/string inputs only; no binary float amounts. Opening
accounts must balance. Corrections cannot exceed the relevant recorded amounts,
debt payments cannot exceed principal, and restricted cash cannot exceed cash.
The fixture rejects negative closing cash, impossible direct receipts/payments,
tax-loss/refund cases, invalid tax rates, nonwhole installation quantities and
inconsistent cost decomposition. It is deliberately not a general accounting
system, document authenticator, fraud classifier or standards-compliance engine.
