V07-C11 — original accounting-comparability laboratory
Edition boundary 2026-10-06; authored/source-checked 2026-10-08.

FILES AND EXECUTION
Keep v07-c11-analysis.py and v07-c11-inputs.json together. Run from any directory:
  python3 /path/to/v07-c11-analysis.py
An optional explicit input JSON path may follow. Standard output is strict JSON;
invalid teaching contracts exit 2. There are no packages or network requests.
v07-c11-output.json preserves the baseline output. In the source repository:
  python3 book/scripts/check_v07_c11.py
The checker exposes quiet check() returning a JSON-serializable dictionary.

PROVENANCE AND UNITS
All entities, transactions and numerical evidence are original and invented.
X1/X2 are fictional years, not observations from 2026. Money is kCU (thousands
of currency units), inventory quantities are thousands, and unit costs/prices
are CU per unit. 100 thousand units at 3 CU cost 300 kCU. Values are rational
strings; "80/3" preserves an exact third. Asset lives are positive integer
years. Each case is separate; do not add the three fictional entities together.

CASE 1 — ORION: TWO MEASUREMENT BASES, ONE CASH HISTORY
Opening cash500 + inventory200 = liabilities100 + capital600; RE0. Opening
inventory is 100 units at2. X1 purchases100 at3, sells120 at5, operating cash80.
X2 purchases100 at4, sells90 at6, operating cash90. In each year cash purchases
precede cash sales, which precede operating payment. The model checks each
cash prefix; an expected later receipt cannot fund an earlier purchase.

Cost formulas are annual periodic FIFO and simple unit LIFO. Beginning layers
and purchases remain in chronological order. No taxes, impairment, inventory
write-down, FX, credit, acquisitions, interest, dividends or other assets occur.
There is no dollar-value LIFO, tax-conformity analysis or issuer policy election.
The chapter expressly states that LIFO is not an IAS2 formula for interchangeable
inventory. These are analyst counterfactuals applied to the same transactions.

                    X1 FIFO  X1 LIFO  X2 FIFO  X2 LIFO
COGS                    260      340      280      360
Inventory               240      160      360      200
Profit                  260      180      170       90
Inventory change         40      -40      120       40
CFO                     220      220       50       50
Cash                    720      720      770      770
Assets                  960      880     1130      970
Equity                  860      780     1030      870

R = FIFO inventory minus LIFO inventory rises0->80->160. R adjusts the
inventory/equity stock; change in R adjusts period profit. Profit change and
inventory-change adjustment cancel in indirect CFO. Opening and closing
equity both require the corresponding reserve; never add the closing reserve
to every year's profit. The benchmark returns actual retained layers.

Exercise3 liquidation appends X3: no purchases, all90 units sold at5, other
payments50. FIFO/LIFO profits40/200, reserve change-160, CFO400 both; cash1170,
inventory0, assets1170/liabilities100/equity1070 both. Total profit470 both.

CASE 2 — SEPARATE MACHINE: NEW EVIDENCE VERSUS ORIGINAL ERROR
Machine120/residual0, original6-year straight-line schedule. Revision is at the
start of X3 after two completed years; original carrying80. In new-estimate
history the earlier estimate was reasonable; three remaining years give annual
depreciation80/3 without revising X1/X2. In the alternative error history,
reliable original information required a4-year life; material error is fully
reconstructible. Corrected carrying60, cumulative prior asset/equity correction
-20, earliest X2 comparative opening correction-10 plus X2 profit correction-10.
X3 corrected depreciation30. No prior correction enters discovery-year profit.
Cash operating profit before depreciation100 gives CFO100 in each period under
all histories, with no other accruals. Machine purchase was cash at start X1.

The program reports full original/revised/corrected schedules and stops each at
residual value. It does not judge real useful-life evidence, materiality or
practicability. It excludes changes after the asset was fully depreciated,
impairment, tax effects, disposals and later capex. Earliest comparative is the
last completed year in this model; earlier errors go to its opening equity.

CASE 3 — VECTOR: SEGMENT MEASURES ARE NOT GROUP NET INCOME
Hardware/Services external revenue300/200; Hardware internal transfer40 is
included in Services expenses. All transferred items are consumed/sold outside,
with no unrealized margin. Reported segment profits54/36 sum90. Corporate
operating20, share compensation10, interest8 and tax13 are outside the segment
measure: group operating profit60, PBT52, NI39. Segment revenues540 minus
internal40 give external500. Segment assets180+120, corporate assets50 and
internal receivable20 give group assets330. This is not a complete balance
sheet or cash-flow statement. CFO is JSON null, explicitly unavailable.

A matched transfer-price increase10 adds10 to seller profit and buyer expense:
profits64/26, group profit unchanged. Do not subtract internal sales again from
the already net segment-profit sum. Different cost allocations can impair
segment comparability even when consolidated totals agree.

SOURCE AND REVIEW LIMITS
The chapter/source proposals record actual inspected IFRS public summaries,
dated Australian AASB108/AASB8 text, actual FASB2015-11/2023-07 amendments and
SEC staff manual section6310. IFRS18's2027 effective date and the renamed IAS8
webpage are treated separately from an issuer's actual adoption. Complete
current FASB Codification and gated IFRS standards were not inspected.
No current framework equivalence, actual policy election, tax result, filing
compliance, audit assurance or legal judgment follows from this arithmetic.
Review and checks cover the stated synthetic cases; no visual/browser/print
QA is asserted by this laboratory.
