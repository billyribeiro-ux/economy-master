VOLUME 8 CHAPTER 11 — DISTRESS, RESTRUCTURING AND GOVERNANCE
Original Brindle Ceramics and Rillstone Services cases.
Edition boundary: 6 October 2026. Authored/checked: 8 October 2026.

EXECUTION
Keep v08-c11-inputs.json and v08-c11-analysis.py together and run:
  python3 v08-c11-analysis.py
An optional argument selects another input file. Standard library only;
no network, installations or file writes. Imports and run(data) are quiet.
JSON numeric results are exact rational strings, such as "520/7".
Use integers or exact fraction/decimal strings as inputs, not floats/bools.
Unsupported inputs raise ValueError; CLI errors return exit 2 with stderr
and no result JSON. The library's focused checker exposes quiet check()
in book/scripts/check_v08_c11.py, returning a strict JSON-serializable record.

SCOPE AND PROVENANCE
Every business, value, date, probability, rate and contract is fictional.
Money is kCU; conversion shares are thousands; per-share prices are CU.
No actual issuer, dataset, legal priority, insolvency test or tax rule is
represented. All numerical examples, problems and implementation are original.
Source proposals identify the specific passages actually inspected.

The model supports a small finite liquidation/continuation contract, plus
a separate one-quarter refinancing schedule. It does not estimate fair
values, consent probabilities or legal enforceability. Old faces include
every allowed payment in the model; no unlisted claimant, tax, guarantee,
employee obligation, lease or subsequent operating outlay is hidden.
The lab requires strictly positive secured, bond and trade faces; it rejects
zero faces rather than dividing by an empty eligible pool. In the chapter's
general formula, a pool with no eligible unsecured claims goes to equity
and needs no pro-rata recovery rate.

BRINDLE LIQUIDATION — DATE 0, 1 JANUARY 2027
Collateral sells for 70 less its own cost 10, leaving 60 for secured face 90.
The secured deficiency 30 joins bonds 45 and trade 30 at equal rank per
face unit. Other assets sell for 45 less separate cost 5; cash is 10.
General pool = 45 - 5 + 10 = 50; eligible face = 30 + 45 + 30 = 105.
General recovery fraction = 50/105 = 10/21.
Receipts: secured 520/7, bonds 150/7, trade 100/7, common equity 0.
Sum = 110, also 70 + 45 + 10 - 10 - 5. Secured face recovery = 52/63;
bond and trade recovery = 10/21. Collateral excess, if any, enters the
general pool; no double recovery or double deduction of costs is permitted.

The bond was hypothetically bought six months earlier for 18 while recovery
was uncertain. A current receipt 150/7 gives a realized holding return 4/21,
despite recovering only 10/21 of face. Historical cost is not a claim of a
current arbitrage price. No annualized or risk-adjusted performance is implied.

BRINDLE CERTAIN CONTINUATION — DATE 1, 1 JANUARY 2028
Immediate restart 24 + workout cost 6 = 30, funded by internal cash 10 and
external proceeds 20. This batch exhausts opening cash. The restart budget
covers the interval; no intermediate funding is missing. Final cash 154
is certain and net of all future operating, tax, investment and disposal
payments, before financial claims. There is no further continuation value.
The compatible annual return for certain cash is 5%.

A unanimous agreement replaces collateral rights with priority for new money,
then old secured face 90, then bonds/trade in ratio 45:30, then old common.
The old faces earn no additional interest under this agreement. All unpaid
claims are discharged at final settlement. Computing favorable class values
does not itself obtain consent or an executed loan.

Fair new face = 20 * 1.05 = 21; its price is 20.
Final cash: new 21, old secured 90, bonds 25.8, trade 17.2, equity 0.
Present values: new 20, secured 600/7, bonds 172/7, trade 344/21, equity 0.
Old-claim value = 380/3 = 126.6667; gross final-cash PV = 440/3.
Old gains over liquidation: 80/7, 22/7, 44/21 and 0; sum = 50/3.
Compare PV(final cash) - new contribution = 154/1.05 - 20 with liquidation 110.
Do not subtract the contribution again after discounting old residual 133.

Certain final cash for aggregate break-even = (110 + 20) * 1.05 = 136.5.
At that cash the original priority pays old secured 90, bonds 15.3 and trade
10.2: secured gains while both unsecured classes lose against liquidation.
A consenting repair pays secured 78, bonds 22.5 and trade 15, plus new 21.
Discounted old payments exactly equal their liquidation receipts. Changing
that allocation does not change the total operating value.

DEBT-TO-EQUITY ALTERNATIVE
Keep the original 154 cash and new loan 21. Cancel all old debt and common
claims by agreement, giving old secured/bond/trade claimants 65/21/14 thousand
equal-rights common shares, respectively. Residual value remains 380/3.
100 thousand shares imply price 19/15 CU. Class values are 247/3, 133/5
and 266/15, summing to 380/3. Old common receives zero. This is a different
allocation and control arrangement, not an automatic addition to cash.

RISKY REVISION — EXERCISE 7
The alternative final cash is 18/174 with probabilities 1/4 and 3/4.
This scenario explicitly assumes risk-neutral investors and the same 5%
time return, so those physical probabilities are also valuation weights.
The lab does not assert this pricing convention for a general risky firm.

New money 20 requires [18/4 + 3F/4]/1.05 = 20, hence fair face F = 22.
State receipts (new, secured, bonds, trade, equity):
  low:  (18, 0, 0, 0, 0)
  high: (22, 90, 37.2, 24.8, 0)
Present values: 20, 450/7, 186/7, 124/7, 0. Old value = 760/7.
Old surplus against liquidation = -10/7; secured loses 10 while bonds and
trade gain 36/7 and 24/7. Their combined gain cannot compensate that loss.
Promised lender yield is 10%, but expected receipt 21 on price 20 gives 5%.
Face 21 would raise only 135/7, leaving immediate gap 5/7.
The exact solver inverts min(face, cash) at each state-cash breakpoint.
If all final cash is worth less than the new money required, the output
reports new-money-unfundable and supplies no asserted closing claims.

RILLSTONE — 1 APRIL TO 1 JULY 2027, ONE STATED QUARTER
Opening cash 18; reserve 8 retained until date 1, earning zero and then
released; old note 50 due now. New lender commits proceeds 32 subject to
signed agreement. An independent arranger receives issuance fee 2; the
lender advances the full 32, receives none of that fee, and earns 2% on it.
Final net operating cash 56 is certain and includes all other obligations.

Conditional current old payment = 18 + 32 - 2 - 8 = 40; extension needed 10.
Five old creditors each own face 10. The specified amendment needs all five
signatures: each takes 8 now and a certain 2.04 later. That stream is worth
the same as 10 paid immediately; the actual no-agreement outside option is
not supplied and must not automatically be assigned full face value.
The new lender is paid first, then the extended note, then old common.
Date 0: sources 18 + 32 = 50; uses 40 + 2 + 8 = 50.
Date 1: sources 8 + 56 = 64; payments 32.64 + 10.20 + 21.16 = 64.
Final cash and both debts are zero. Old-note value is 50; old-equity value
is 1058/51. The zero-yield reserve is dated cash, not an additional free asset.

Without consent, the new loan is conditional and unexecuted. The output
labels quoted sources/uses as "if_signed", returns consent-missing and
closing=null. It does not assert that cash from an unsigned loan arrived.
The separate holdout scenario stipulates an extra 1 at date 1 as a signing
condition: old deferred cash becomes 11.20; common cash falls to 20.16.
PV 50/51 moves from common to the requesting creditor. This is a transfer,
not an extra destruction of operating resources. Other fees or delays would
be separate costs requiring their own evidence and cash entries.

TRANSFER ANCHORS AND LIMITS
Brindle workout cost 10: external funds 24, new face 25.2, old cash 128.8,
old PV 368/3 and surplus 38/3; the extra current cost reduces old PV by 4.
Rillstone new commitment 28: current old payment 36, extension 14, final
new/old debt 28.56/14.28 and old common 21.16. If extension is capped at 12,
new equity 2 fills the remaining immediate gap. Final common cash 23.20
allocates 2.04 to new common and 21.16 to old common; new fraction 51/580.
Brindle other liquidation proceeds 66: general pool 71; receipts 562/7,
213/7, 142/7, sum 131. Original continuation is worse by 13/3; certain
final cash needed to match the revised alternative is 158.55.

The model does not solve a bargaining equilibrium or force parties to sign.
Scenario values, projected recoveries and promised interest are different
objects. A quoted refinancing that fails at maturity is reported as a funding
failure, without pretending its full-payment promise is fairly financed.
Source and author review do not replace coordinator acceptance, applicable
professional advice, independent human evaluation or visual reading QA.
