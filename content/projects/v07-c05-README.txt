V07-C05 — RIDGEWAY BORROWER AND LESSEE LAB
Original synthetic case; kCU means thousands of currency units.
Edition boundary 6 October 2026; prepared 8 October 2026.

RUN
Save v07-c05-analysis.py and v07-c05-inputs.json together.
python3 v07-c05-analysis.py
An optional path selects another JSON input. The default is relative to the
script, so running from another working directory works. Standard library
only; no packages, network, randomness or installation. Import and API are
quiet. build_report(data) returns a strict-JSON-serializable report. The CLI
prints JSON; invalid input exits 2 with a JSON error. Explicit validation
remains active under python -O. Repository independent checker:
python3 book/scripts/check_v07_c05.py

SCOPE AND REPRESENTATION
The horizon contains 1-10 complete annual intervals, with commencement on
1 January and payment after each 31 December annual accrual. The integer
start_year is a calendar label; rates are effective rates per full annual
interval, not actual-day rates. Lease, note and operating arrays share the
same horizon. This intentionally bounded model excludes tax, working
capital, disposal, impairment, FX, modifications, floating rates, embedded
options and default. Recognition/classification eligibility is supplied,
not inferred. These conventions are not a current GAAP/IFRS compliance tool.

All money and rate inputs are nonnegative decimal or rational STRINGS, such
as "104.2", "0.10" or "3/2". Python Fraction stores exact model kCU. Outputs
are exact rational strings, for example "81/5" means 16.2 kCU. There is no
currency rounding hidden inside schedules. An actual minor-unit payment
contract needs an explicit rounding/last-payment policy before adaptation.
Input amounts are bounded by 10000000 kCU; rates by 1 per year; covenant
limit by 100. Floats, bools, NaN, infinity, unknown/missing/duplicate fields,
invalid horizons and inconsistent effective-rate/payment pairs are rejected.

NOTE CONTRACT AND JOURNAL
Gross lender cash is 102, an eligible directly attributable issue fee is 2,
net cash and initial amortized liability are 100. Contractual face is 104.2,
annual cash coupon is 8, with full face due alongside the final coupon.
Effective rate 10% is supplied and verified against the full net-proceeds PV.
Do not confuse gross discount 2.2 with total face-minus-net difference 4.2.
The fee reduces initial carrying amount under this convention; it is not
also expensed immediately. It remains an actual commencement cash payment.

Generated commencement entries: owner contribution 100; note proceeds 102;
fee 2 reducing note liability/cash; owned equipment purchase 80; noncash lease
recognition 120. Net financing cash =100+102-2=200, investing cash=-80, so
initial cash 120. Assets 320=liabilities 220+equity 100. The lease addition is
not an invented cash inflow/outflow.

Note year 1: opening 100, interest 10, coupon 8, closing 102.
Note year 2: opening 102, interest 10.2, coupon 8+face 104.2, closing 0.
Total expense 20.2 = total payments 120.2 - initial net 100.
Its effective rate is not automatically its coupon rate 8/104.2, or a later
market yield. If fee or cash terms are edited, choose a coherent new rate
or proceeds; the program refuses an unbalanced terminal plug.

LEASE AND ASSET CONTRACT
An identified asset is available from commencement, with the right-of-use
recognition conditions stipulated. Two end-year payments 66/72.6 at 10%
have PV 120. No incentive, restoration obligation, initial direct lease cost,
variable/indexed rent, purchase option, ownership transfer or renewal option.
ROU asset 120 is depreciated straight-line over its two-year term to zero.
Owned equipment 80 is available immediately, four-year life, zero residual:
depreciation 20/year. Lease schedules:
  year 1 opening 120 + interest 12 - cash 66 = closing 66; principal 54;
  year 2 opening 66 + interest 6.6 - cash 72.6 = closing 0; principal 66.
ROU carrying amounts after depreciation are 60 and 0, different from the
liability 66 and 0. The liability follows payment timing, not depreciation.

A commencement_prepayment is supported: it adds to the initial ROU asset
and reduces commencement cash, but is NOT included again in the liability
PV. It is treated as a financing cash outflow under this lab's declared
convention. For this simple cash-classification model every later lease
payment must cover that year's interest, so principal reduction is never
negative. Rent-free/negative-amortization cash allocation requires a more
general model. The note itself may accrete when coupon is below expense.

COMPLETE OPERATING AND CASH BRIDGES
Cash revenues 260/240 and cash operating expense 140/140 create operating
cash before financing costs 120/100. Cash receipts occur before operating
payments, then note payment, then lease payment in each annual bucket.
This annual ordering is supplied; it is not a finer cash forecast.
Both asset depreciation charges and effective interest expense enter profit.
Year 1: profit 18; closing cash 166, owned carrying 60, ROU carrying 60;
       assets 286 = note 102 + lease 66 + equity 118.
Year 2: profit 3.2; closing cash 81.2, owned carrying 40, ROU 0;
       assets 121.2 = liabilities 0 + equity 121.2.
There are no dividends or new contributions after commencement.

CASH CLASSIFICATION IS A STIPULATED CONVENTION:
Paid note coupon and lease interest are operating; contractual note face
and lease liability principal reductions are financing. Owned asset cash
purchase is investing. Note proceeds, issue fee and initial owner cash are
shown separately as financing at commencement. Do not infer universal
IFRS 18, US GAAP or transaction-fee treatment from this teaching convention.

Year 1 CFO=120-8-12=100; CFF=-54; cash change 46.
Indirect CFO=profit 18+ownedDep 20+ROUdep 60+noteAccretion 2=100.
Year 2 CFO=100-8-6.6=85.4; CFF=-104.2-66=-170.2; cash change-84.8.
Indirect CFO=profit 3.2+20+60+2.2=85.4.
These annual movement lines begin after the separately shown commencement.
For a full-calendar 2025 cash-flow statement starting before formation,
combine the blocks: CFO 100, CFI-80, CFF 200-54=146, cash 0 to 166. The report's
full_calendar_year_cash_flow does this explicitly. The ordinary cash_flow
field retains the after-commencement movement comparison. Year 2026 already
excludes no startup transactions, so its full-year categories are unchanged.
Report includes every debit-positive journal, closure and cash prefix,
liability PV/rollforwards, balance/retained earnings and both cash bridges.
Negative cash at a modeled prefix is rejected as an unfunded proposal;
there is no undeclared overdraft, rescue or refinancing.

COVENANT AND DISCLOSURE
The original contract tests only after year 1 payments/closing:
  carrying note + lease liability <= 1.5 * book equity; equity must be >0.
Base debt 168, equity 118, headroom 9, ratio 84/59: pass.
The program reports status only; no waiver or acceleration is invented.
Cash operating surplus divided by all note/lease payments is a separately
defined descriptive coverage measure: year 1 60/37, year 2 125/231. It is not
the leverage covenant and is not a universal financial-ratio definition.
Year 2 coverage below one can coexist with sufficient accumulated cash.

ALTERATIONS AND INDEPENDENT REPRODUCTION
1. Solve PVs and both schedules on paper before reading the implementation.
2. Replace first cash revenue 260 by 230 (cost 140 unchanged). Year 1 surplus 90,
   profit-12, cash 136, assets 256, liabilities 168, equity 88, headroom-36.
   Covenant fails despite positive cash. No remedial action is presumed.
3. Change the covenant limit to 84/59: equality passes. A nonpositive equity
   scenario fails explicitly rather than exploiting a negative ratio.
4. To study a zero rate, change the note rate to 0 and gross proceeds 122.2
   (fee 2 unchanged); its net 120.2 now equals total payments. Change lease
   rate to 0, giving liability 138.6. Recompute all asset/expense/cash effects.
5. For premium arithmetic alone, use the chapter's separate note example:
   net proceeds 100, coupons 12/12, face 95.8, rate 10%; balances 100/98/0.
6. A changed rate with unchanged net proceeds and promised payments is
   deliberately rejected. A market-price sensitivity calculation is a
   different question from recomputing fixed amortized carrying amounts.

Check the contract, recognition evidence, payment dates, rate convention,
cash-flow labels, rights/covenants and disclosures before interpreting a
balanced schedule. Exact arithmetic does not make an unavailable facility
available, an unenforceable promise collectible or a reporting rule current.
