VOLUME 8 CHAPTER 6 — PAYOUT, LIQUIDITY AND FINANCIAL POLICY
Original Portico Instruments and Dunlin Packaging cases.
Edition boundary 6 October 2026; authored and checked 8 October 2026.

EXECUTION
Keep v08-c06-inputs.json and v08-c06-analysis.py together; run:
  python3 v08-c06-analysis.py
One optional argument selects another input path. Python standard library
only; no installation, network or file writes. Imports and run(data) are
quiet. All numeric outputs are exact rational strings; "9/8" is 1.125.
Inputs use integers or exact decimal/fraction strings, not floats or bools.
Invalid supported contracts raise ValueError; CLI errors go to stderr with
exit 2 and no result JSON. The focused library checker is
book/scripts/check_v08_c06.py with a quiet JSON-serializable check().

ORIGINALITY AND SCOPE
All names, values, prices, dates, rates, tax rules and contracts are original
fictional teaching inputs. No external dataset or current law is represented.
Money is kCU, shares are thousands and share prices CU. Payout prices are
at the same instant before/after distribution. Forecast income is the next
full year, with the distribution before that year and no weighted-average
historical EPS claim. Quarterly rates in Dunlin are per stated quarter.

PORTICO BENCHMARK
Equity 1000 = operating value 800 + excess cash 200; shares 100; fair price 10.
Pay 200 without changing operations/investment. Dividend/share 2, ex price 8.
Fair repurchase at 10 retires 20; remaining 80 shares represent equity 800 at 10.
An initial owner of 10 shares (thousand) receives 20 and retains value 80 under
either dividend or pro-rata repurchase. A nonseller's 10 shares still value 100
after the fair repurchase. All these amounts refer to the stated kCU units.

Forecast income 100 includes cash income 10 at 5% on 200. After either payout,
income 90 remains. Old EPS 1; dividend EPS 0.90; fair-buyback EPS 1.125, up 12.5%.
No wealth is created by this denominator effect. General cash-funded EPS
rises if income / shares > cash-income-rate × execution price, with positive
remaining shares. This condition is not a value-creation criterion.

For execution at 8: retire 25, remain 75, intrinsic price 32/3. Remaining owners
gain 50 and sellers lose 50 against prior intrinsic claim values. At 12.5:
retire 16, remain 84, price 200/21; remaining owners lose 40, sellers gain 40,
despite EPS 15/14 exceeding original 1. Pro-rata participation shares both sides
of the transfer proportionately. Off-fair execution is hypothetical, not a
promise that informed unconstrained sellers would accept those prices.

PERSONAL-TAX EXERCISE (SEPARATE, FICTIONAL)
Holder 10, basis 6/share; dividend rate 30%, realized-gain rate 20%. A dividend
does not reduce basis; repurchase sells the proportional shares at fair 10.
Dividend event net 14; remaining immediate-sale net 76; total 90.
Repurchase event net 18.4; remaining immediate-sale net 73.6; total 92.
The comparison includes the different bases in the remaining holdings.
It is not an assertion about any jurisdiction's real treatment or rates.

RESTRICTED RETENTION EXAMPLE
40 is irreversibly retained one year at 1%, then paid, with no liquidity benefit
and no access meanwhile. Matching certain outside rate 5% gives value 808/21
and loss 32/21 relative to immediate 40. Freely withdrawable cash is not forced
into this discounted-delay model merely because management also holds it.

DUNLIN DATED CONTRACT
Dates: 2027-01-01 / 2027-04-01 / 2027-07-01, each interval one quarter.
These are hypothetical future dates. Initial cash 60, term principal 50,
minimum cash 20 after each synchronized batch, initial payout ceiling 25.
No revolver is drawn initially, and the line may not fund the initial payout.
State is learned at date 1
after payout. No probabilities are supplied: test all three named states.

Base receipts 100/120 and operating payments 95/105 give cash 5/15. The project
is excluded from those receipts. Collection delay 25 moves receipts to date 2,
giving operating cash −20/40. Combined supplier prepayment 8 paid at date 1 and
applied against date 2's payments produces operating cash −28/48. These timing
states all have cumulative operating cash 20; no bad debt or expense is
invented. Receipts/payments are gross inputs, not income forecasts.

Indivisible investment costs 30 at date 1 and pays certain 36 at date 2 if funded.
There are no further costs/payoffs. At supplied compatible quarterly 4%,
date 1 NPV=36/1.04-30=60/13. Positive value does not finance the earlier cost.
Corporate tax and cash yield are zero. Both debt types charge 4% of opening
principal per quarter. Term interest 2 occurs at each date; 10 term principal
is repaid after date 2 interest, leaving 40 beyond the planning horizon.
The committed line's nominal outstanding ceiling is 40, but total-debt cap 80
leaves effective date 1 capacity 30. No fees or other draw restrictions apply.
The line must be fully repaid at date 2 with no rollover. New date 1 draws have
no interest at date 1. There are no unlisted equity contributions or receipts.

MAXIMUM PAYOUT AND COMPLETE PATHS
Date 1 cash before draw = 60 − Q + O1 − 2 − 30, where O1 is operating cash.
Draw = max(0, 20 − cash before draw), permitted only if at most 30.
State date 1 payout upper bounds are 43, 18 and 10. Date 0 cash also caps payout 40,
and the separate payout permission caps it 25. Date 2 maturity is then checked.
Maximum across all supplied states and dates is 10.

At Q = 10, normal/slow/combined draws are 0/22/30; date 1 cash 23/20/20.
Usable further debt headroom is 30/8/0; nominal unused line is 40/18/10.
Date 2 cash after term interest, revolver interest, term repayment 10 and all
line principal is 62/61.12/60.80. Every path ends with term 40 and line 0.
At Q = 8, draws 0/20/28 and date 2 cash 64/63.20/62.88; combined usable headroom 2.
At Q = 18 the combined state needs 38 and fails by 8 against the required buffer.
At Q = 25, slow requires 37 (gap 7); combined requires 45 (gap 15). Combined cash
after maximum permitted draw is 5, not a valid closing minimum 20. Failed
paths return closing=null and do not assert a compliant project/date 2 close.

The program also derives a date 2 payout bound. If A is date 1 cash without
payout or borrowing, h=A-minimum, and S is cumulative cash before payout and
revolver interest, ending cash equals S-Q-rate*max(0,Q-h). It solves this
piecewise linear constraint exactly, then combines it with the earlier
constraints. Thus it does not silently extend a maturing credit line.

TRANSFER ANCHORS
Supplier prepayment bound 4: robust maximum payout 14; combined draw 30,
date 1 cash 20 and date 2 cash 56.80. Ignoring the debt cap would wrongly permit 24.
Debt covenant 75: effective line 25; robust maximum payout 5. If 10 is nevertheless
paid, combined shortfall 5. Separate gross equity 7 with fixed cash fee 2 supplies
net 5; draw 25, cash 20, total debt 75; date 2 cash 66. This outside contribution
also gives the new investors claims; extra firm cash is not all old-owner gain.
Prepayment bound 9: robust maximum payout 9; paying 10 fails at date 1 by 1.
At Q = 9, combined draw 30, cash 20, and date 2 cash 61.80.

LIMITS
The code values neither Dunlin's whole firm nor a probabilistic optimal payout.
The scenario maximum is a feasibility ceiling. A choice below it can purchase
headroom; its optimality needs objectives and evidence absent from this case.
Annual/quarterly dates do not verify every intraperiod payment in a real firm.
Primary sources support scoped methods and hypotheses, not this fictional
contract or any current legal/tax claim. The author and coordinator review
are separate from external human certification and visual reading QA.
