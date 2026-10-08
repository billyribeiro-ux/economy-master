VOLUME 8 CHAPTER 2 — FREE CASH FLOW AND DISCOUNTING
Original fictional Cedar Service Runoff and separate consistency examples.
Edition boundary: 6 October 2026. Authored and checked: 8 October 2026.

FILES AND EXECUTION
Keep v08-c02-inputs.json and v08-c02-analysis.py together. Run:
  python3 v08-c02-analysis.py
or supply another input path as the one optional argument. Python 3 standard
library only; no installs, network or file writes. JSON output uses exact
rational strings: "19/400" is 0.0475, which is 4.75%. Imports and run(data)
are quiet. A violated supported contract raises ValueError; the CLI reports
an input error to stderr and exits 2 without result JSON. The library checker
is book/scripts/check_v08_c02.py, whose quiet check() returns strict JSON.

PROVENANCE, UNITS AND DATES
All inputs, names and cases are original fictional teaching materials. There
is no external dataset, license-restricted company case or real market rate.
Date 0 is 2026-12-31; dates 1 and 2 are the following annual anniversaries.
They are hypothetical dates, not observed future results. Money is kCU.
All cash is at the annual end date, with effective annual compounding.
Each date's remaining claim value is after that date's distributions and
principal changes. The nominal/real, currency and continuation examples are
separate cash claims, not additional assets owned by Cedar.

CEDAR CONTRACT
Receivables are the only noncash operating working capital. All other costs
and taxes are paid currently. Opening cash 0, receivables 8.5 and net PPE 40
are financed by debt 40 and book equity 8.5. Old equipment's remaining
depreciation is 25 in year 1 and 15 in year 2. New capex 10 occurs at date 1,
serves only year 2 and is fully depreciated in year 2. Total depreciation is
therefore 25 in each year. Book/tax depreciation agrees. No tax losses,
credits, deferred balances, other assets, other claims, fees, acquisitions,
disposals or unlisted transactions are present.

Revenue is 322/249, cash operating costs 175/125, capex 10/0, and closing
receivables 5.5/0. EBIT is 122/99. Tax is 25%, with immediate full use of
interest deductions and payment. Interest is 5% of opening debt. Principal
40 -> 20 -> 0 changes at the final date after interest. All positive equity
cash is paid; no cash is accumulated and no new equity is raised. At date 2
all equipment has zero value, contracts end, receivables are collected and
debt is repaid. Zero book values alone would not establish zero continuation.

CORE BENCHMARK (YEAR 1 / YEAR 2; kCU)
Unlevered cash tax: 30.5 / 24.75; NOPAT: 91.5 / 74.25.
Change in working capital: -3 / -5.5.
Net reinvestment = capex - depreciation + change in WC: -18 / -30.5.
Operating capital: 48.5 opening -> 30.5 -> 0.
FCFF: 109.5 / 104.75.
Interest: 2 / 1; levered cash tax: 30 / 24.5; NI: 90 / 73.5.
Current tax shields: 0.5 / 0.25.
Receipts: 325 / 254.5; direct and indirect CFO: 118 / 104.
CFI: -10 / 0. Net borrowing: -20 / -20. FCFE/payout: 88 / 84.
CFF, after principal and shareholder payments: -108 / -104.
Net cash change: 0 / 0. Closing book equity: 10.5 / 0.
Net lender cash = interest - net borrowing: 22 / 21.
Actual combined investor cash: 110 / 105 = FCFF + current cash shield.

FCFF AND FINANCING CONVENTION
FCFF uses the cash tax of the operating business without interest deductions.
In the simple current-tax regime:
  FCFF = EBIT*(1-tax) + D&A - capex - delta_WC
  FCFE = NI + D&A - capex - delta_WC + net_borrowing
       = FCFF - interest*(1-tax) + net_borrowing.
More generally replace tax*interest with the actual unlevered-minus-levered
cash tax saving. Actual investor distributions sum to FCFF plus that saving.
This distinction prevents counting the interest shield twice.

VALUATION CONTRACT AND ANCHORS
All Cedar payments and shields are certain by assumption. Every investor
claim is freely priced at the supplied 5% annual certain rate. Thus debt and
equity rates coincide in this special case. This is not a general statement
about the risk of leveraged equity. The program first values actual total
investor cash backward at 5%, obtains equity as total less the par debt claim,
and then derives each period's compatible FCFF rate from market weights.

Remaining operating values: 200 -> 100 -> 0.
Debt values: 40 -> 20 -> 0. Equity values: 160 -> 80 -> 0.
Debt weight: 20% at the beginning of each modeled year.
WACC = 80%*5% + 20%*5%*(1-25%) = 4.75% = 19/400.
FCFF PV at the compatible rates: 200; FCFE PV at 5%: 160.
Debt payments PV at 5%: 40.
Unlevered value at 5%: 87890/441; shield value at 5%: 310/441.
Their sum: 200. Subtract debt once after FCFF valuation, never a second time
after valuing the already debt-adjusted FCFE.

If year-1 closing debt changes to 40, leaving repayment to date 2:
  FCFE: 108 / 63.25; operating values: 88300/441 -> 2105/21 -> 0.
  Equity PV: 70660/441; compatible rates: 8389/176600 and 379/8420.
The old constant 4.75% is no longer the compatible pair. If date-1 receivables
instead rise from 5.5 to 10.5 and date-2 receivables remain 0, FCFE becomes
83/89 and equity PV 70460/441. Waiting one additional year for 5 lowers PV
by 100/441. The program recomputes the market weights for changed inputs.

SEPARATE PURCHASING-POWER EXAMPLE
Real date-0-purchasing-power cash: 60/90. Known inflation: 4%.
Real rate: 5%; nominal rate: (1.05*1.04)-1 = 9.2%.
Nominal cash: 62.4/97.344. Both PVs: 6800/49.
This is exact for the stipulated known price path, not a generic formula for
uncertain inflation risk. Fixed nominal contracts do not inflate themselves.

SEPARATE CURRENCY EXAMPLE
Foreign payments: 105/110.25 kF. Foreign rate: 5%; home rate: 8%.
Spot: 2 H/F. Supplied known future rates: 72/35 and 2592/1225 H/F.
They equal spot*((1+home_rate)/(1+foreign_rate))**t.
Home payments: 216/233.28 kH. Foreign PV: 200 kF; home PV: 400 kH.
The model rejects a supplied path inconsistent with that known-conversion
contract. It does not forecast future spot exchange or equate a forward rate
with an uncertain expected spot. General risky currency valuation needs
the joint cash/exchange distribution and an appropriate pricing model.

SEPARATE CONTINUATION EXAMPLE
Explicit cash: 30/36; next cash at date 3: 40, already after reinvestment.
Compatible constant rate: 10%; perpetual growth after date 3: 2%.
TV at date 2 = 40/(0.10-0.02) = 500, excluding explicit date-2 cash.
Explicit PV: 6900/121; terminal PV: 50000/121; total: 56900/121.
The geometric tail requires -1 < growth < rate with rate > -1 and positive
next cash. This lab checks timing and convergence, not sustainable growth
economics; Chapter 3 develops the reinvestment and capital conditions.

SCOPE AND CHECKING
The runoff is deliberately small. Input numbers must be integers or exact
decimal/fraction strings; bools, floats and non-finite values are rejected.
Opening accounts must balance; the supported runoff needs nonnegative
operating/debt stocks, nonnegative taxable income, nonnegative shareholder
payout and completely zero terminal balances. Book equity can be negative
in a changed financing scenario; market residual coverage is checked apart
from book equity. A required new contribution or delayed tax shield needs
a different explicit contract. All rates are supplied, never estimated.

The focused checker reconstructs the original transactions with a separate
signed ledger, values investor claims independently, checks cash/capital/tax/
financing identities, all exercises and timing transfers, nominal/real and
currency transformations, the geometric tail, meaningful failure cases and
portable normal/optimized execution. Author and coordinator review remain
distinct from external human evaluation. The program is not a universal
reporting, tax, real-company valuation or legal-distribution engine.
