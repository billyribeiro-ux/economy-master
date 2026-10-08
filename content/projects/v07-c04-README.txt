V07 C04 — Original Alder Instruments asset lifecycle

Purpose
Reproduce the chapter's three reporting periods and independently reconcile
profit, cash and the gross-cost/contra-asset rollforward. This fixed synthetic
case is not a current filing, a valuation recommendation or a standards engine.

Files and execution
Keep v07-c04-analysis.py and v07-c04-inputs.json in the same directory.
Run: python3 v07-c04-analysis.py
Or:  python3 v07-c04-analysis.py path/to/modified-inputs.json
Only the Python standard library is required. The script reads one JSON file,
writes exact JSON to stdout, and makes no network calls or persistent changes.
All amounts are kCU (1 kCU = 1000 CU); values are exact integers or strings,
including decimal and fraction strings. Output fractions such as 27/2 mean
13.5 kCU, not CU cents. Binary floating-point inputs are rejected.

Fixed conventions
Opening cash/equity 200 is already funded. No tax, debt, foreign exchange,
inventory, working-capital balances, dividends, revaluation or held-for-sale
classification. Recognized services equal same-period cash receipts; ordinary
costs are consumed and paid in that period. All asset-related acquisition and
period costs are cash-paid. The machine is available 1 April 2025, with initial
life 72 months. The estimate changes on 1 January 2026, impairment is tested
after that year's 12 months' depreciation, and control passes to the buyer
on 30 June 2027 after six further months' depreciation. Calendar labels and
elapsed months are deliberately fixed, not inferred from arbitrary input dates.
The remaining-life input is the new life on 1 January 2026 and must cover at
least 18 whole months. The residual can exceed a later carrying amount; this
produces zero depreciation, not an asset write-up. Recoverability inputs are
nonnegative supplied values for an independently cash-generating asset. The
case includes evidence warranting the impairment test. Cash funding must
remain nonnegative; no implicit overdraft is supplied.

Direct readiness costs capitalized: invoice less discount, freight,
installation and required testing. Training, launch, general administration
and routine maintenance are period costs. The operations cash_costs exclude
these separately listed costs. Depreciation and impairment are period charges
in this service business; none is absorbed into another asset.

The sale cash receipt 60 and disposal cash cost 1.5 both settle on 30 June 2027.
The reported CFI contribution 58.5 is their arithmetic net, not a claim that
all real cash-flow statements may net gross asset sales and disposal payments.
The output preserves both gross flows. No gain is counted twice as cash.

Benchmark, all amounts kCU
2025: cost 120; depreciation 13.5; carrying 106.5; CFO 11; CFI -120;
      profit -2.5; cash 91; equity 197.5.
2026: depreciation 24; pre-impairment carrying 82.5; impairment 18;
      carrying 64.5; CFO 35; profit -7; cash 126; equity 190.5.
2027 H1: depreciation 9; pre-sale carrying 55.5; net proceeds 58.5;
      gain 3; CFO 20; CFI 58.5; profit 14; cash/equity 204.5.
At disposal remove gross cost 120, accumulated depreciation 46.5 and
accumulated impairment 18. Closing machine balances are all zero.
Cumulative profit and cash increase are both 4.5 after the asset is sold.

Learning experiments
1. Change gross sale receipt to 53; verify loss 4, profit 7 and cash 197.5.
2. Raise value_in_use to 100. There is no impairment and no write-up to 100;
   follow the changed depreciation and disposal gain through final profit.
3. Compare a new remaining life of 24 versus 48 months. Earlier expense
   changes, but total acquisition-to-disposal asset expense must equal
   cost less net proceeds when all machine balances are removed.
4. Explain why lowering the cash sale receipt changes lifetime profit,
   whereas moving depreciation between periods, holding cash fixed, does not.

The independent repository checker also evaluates usage depreciation,
prospective changes, a capped impairment reversal, finite-life intangibles,
investment property, a qualifying amortized-cost financial claim and economic
depreciation. Those are separate supplied teaching cases, not extra Alder
transactions. Source versions and their limited scope are in the chapter.
