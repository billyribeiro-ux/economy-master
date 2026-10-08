VOLUME 8 CHAPTER 10 — PRIVATE CAPITAL CASH AND CLAIMS

Purpose
Trace four original fictional teaching cases through dated cash, debt, share
counts, preferred rights and fund distributions. This is a bounded instructional
model, not an empirical return study or actual financing/valuation advice.

Files
  v08-c10-inputs.json    Original case assumptions; money in kCU.
  v08-c10-analysis.py    Python 3 standard library only.
  v08-c10-output.json    Exact reference output from the supplied inputs.

Run these three files together, without installing anything:
  python3 v08-c10-analysis.py
For a separate edited input file:
  python3 v08-c10-analysis.py my-inputs.json
The command writes strict JSON to stdout and changes no files. It needs neither
network access nor a browser. Fractions serialize as exact rational strings
(for example 31/25); IRRs are approximate annual decimal numbers. Do not round
the debt balances before calculating the next year's interest.

Original inputs and dates
All businesses, fund terms and tax arrangements were invented for this chapter.
Dates 0, 1, 2 and 3 are exactly one year apart, not historical observations.
Venture share counts are thousands of shares; kCU divided by those counts gives
CU per share. Legal enforceability and tax treatment are case assumptions.
No downloaded market data, source numerical exercises or source code is used.

Mistral buyout
Entry EV 360 plus acquired excess cash 20 less old debt 80 gives seller equity
300. Closing uses 394 include seller 300, debt retirement 80 and third-party
fees 14. New debt 210, acquired cash 20 and sponsor equity 164 fund them.
Necessary operating cash remains within operating working capital and is not
part of the 20. No fee deduction or acquisition tax basis step-up is assumed.
Annual interest is 8% of opening debt. Taxes at 25% of positive EBIT less
interest are paid currently, and no deduction limit or tax loss is modeled.
EBITDA 64/68/72, depreciation 12/12/12, capex 16/18/20 and increases in NWC
3/4/5 give FCFF 32 each year. Principal receives all available cash, at least
15 per year. Base closing debt is 190.6, 170.036, 148.23816. Exit occurs after
year-3 cash service. EV 432 less exit fee 8 and debt leaves equity 275.76184.
Sponsor flows (-164, 0, 0, 275.76184) give MOIC 1.6814746341 and IRR
0.1891321107. Loan principal is never counted as an operating expense.

The model accepts nonnegative three-year operating inputs, nonnegative fees,
an interest rate >= 0, tax in [0,1), positive entry EBITDA/debt/sponsor capital,
and nonnegative taxable profit each year. It deliberately requires positive
remaining debt after each annual sweep: early full repayment and subsequent
dividend schedules are outside this lab. A principal shortfall returns
feasible=false with failure date and gap, without inventing exit performance.
An exit insufficient to repay debt and leave positive equity also returns a
failure, rather than claiming that this success-path model resolves default.
Use the restructuring chapter for explicitly modeled default recovery.

Supported useful changes
* Raise entry EV to 390: sponsor 194; same exit; MOIC 1.4214527835, IRR
  0.1243740474. This changes entry price, not operating outcomes.
* Set year-1 EBITDA to 50: cash 8.9 cannot fund minimum principal 15; gap 6.1.
* With that downside, explicitly set sponsor_topups[0] to 6.1 at date 1.
  Debt becomes 195, 174.7, 153.182; exit equity 270.818. Sponsor flows
  (-164,-6.1,0,270.818) give MOIC 1.5921105232, IRR 0.1697137577.
Repairs must precede the final exit date; final-date top-ups are rejected so
the displayed multiple never nets a same-date contribution against a receipt.
No automatic refinancing, principal forgiveness or additional share issuance
is supplied. Annual feasibility does not establish within-year liquidity.

Saffron cap table
Founders 6,000 and team 2,000 thousand common shares; Series A raises 4,000
at pre-money 16,000 including a new pool targeted at 10% of post-A shares.
Pool = 8,000/7, issue price 7/4, A shares 16,000/7; total 80,000/7.
Post-A fractions: 52.5%, 17.5%, 10%, 20%.
Series B raises 6,000 at pre-money 24,000, price 21/10, adding 20,000/7 shares.
Final fractions: founders 42%, team 14%, pool 8%, A 16%, B 20%.
No anti-dilution protection, additional pool or secondary sale is assumed.
The first_round and next_round functions support the separate exercise
inputs. first_round rejects infeasible pool targets h(1+cash/pre) >= 1.
The full run() function requires all five exact base Saffron fractions
(42%, 14%, 8%, 16%, 20%) and investment amounts before applying its specific
two-class waterfall. This includes the internal founder/team/pool split,
not only the preferred fractions. An edited cap table cannot silently reuse
a mismatched preferred or common-holder cash function.

Preferred waterfall
Before exit all pool awards are granted, vested and exercised for zero cash.
The 64% common block is therefore issued common at exit, not an unallocated
reserve receiving money. Series B has senior 1x preference 6,000; Series A
junior 1x preference 4,000. Both are nonparticipating and can convert 1:1;
each class chooses its own action without side payments. X is equity cash
already net of all debt and exit fees. There are no other senior claims or
dividends. joint_waterfall enumerates four conversion profiles and checks each
class's unilateral alternative. At indifference, multiple profiles must yield
the same cash allocation. It is not a general multi-class contract solver.
Regime boundaries are X=6,000, 10,000, 26,000 and 30,000. With B retaining,
converted A receives 16/(64+16)=20% of cash remaining after B, not 16% of X.
At X=28,000: B 6,000; A 4,400; common 17,600, split founders 11,550, team
3,850, award holders 2,200. The naive independent max would pay A 4,480.
The single_preferred helper separately implements the explicitly stated
one-class participation/cap contracts from exercise 6. Negative exit cash,
nonpositive/non-interior participation shares and caps below 1 are rejected.

Northpass fund
LP commitment 200; date-0 call 100 invests 90 and pays fee 10; date-1 call 50
invests 45 and pays fee 5. Gross receipts 60 at date 2 and 135 at date 3.
Fees are inside commitment. Whole-fund carry is 20% only after all 150 LP
contributions, including fees, are returned. No hurdle, catch-up, GP capital,
borrowing, later fees, recycling or other claims. Final liquidated portfolio
has zero NAV. LP distributions are 60 and 126, GP carry 9, fees 15; uncalled
commitment 50 is released, not distributed as cash.
Gross portfolio flows (-90,-45,60,135) give multiple 13/9 and IRR
0.1686833176. Net LP flows (-100,-50,60,126) give multiple 31/25 and IRR
0.0961120136. Investor paid-in capital includes fees; gross portfolio capital
does not. Fees plus carry are manager receipts, not manager net profits.
At date 2 after distribution, hypothetical net disposal mark 100 yields carry
accrual 2 and LP NAV 98. DPI=2/5, RVPI=49/75, TVPI=79/75; this is an explicit
liquidation-mark convention, not a universal fair-value method. Nothing marked
is treated as received cash in the realized final fund return.

The fund helper requires all calls before all distributions, fees no greater
than same-date calls, calls within commitment, nonnegative gross receipts and
carry in [0,1). Its interim date is 2, after all calls. Final gross receipt
105 instead of 135 gives carry 3, final LP distribution 102, gross multiple
11/9, net multiple 27/25, gross IRR 0.0910658075 and net IRR 0.0340864127.
It does not implement early deal carry, clawbacks, irregular dates, recycling
or a full ILPA template. All such features need additional contract inputs.

IRR domain and verification
block_irr requires all negative cash flows to precede all positive cash flows,
at least one of each, and an admissible numerical bracket for x=1+r > 0.
Accumulating contributions and discounting receipts to the last contribution
date gives a monotone root equation. All base and exercise sequences meet
this uniqueness domain. Interleaved flows are deliberately rejected; merely
returning a root would not resolve multiple-root economics.

In the source repository, run:
  python3 scripts/check_v08_c10.py
from book/. Its importable check() is quiet and returns a strict JSON object.
Checks independently reconstruct acquisition budgets, debt cash taxes and
lender present value, repaired funding/entry-price alternatives, cap tables,
the analytical joint preferred payoff regions, single-class participation,
the whole-fund ledger, net NAV and subscription timing. Every exercise has
numeric anchors. Targeted invalid-domain and consequential-error checks
complement written review; they do not replace source, pedagogy or contract
review and do not certify real investment outcomes.
