ECONOMICS CORE — ORIGINAL SYNTHETIC POLICY PRACTICAL
Edition boundary: 2026-10-06. Authored: 2026-10-08.

Purpose and provenance
All coefficients, households, transactions and community releases are invented
teaching inputs. There are no observed national data, confidential records or
claims about current tariffs, monetary regimes or tax law. The four policies are
counterfactuals in one fixed model. The separate information-offer lottery does
not identify that model's structural parameters. Methods are taught in Volumes
1–6; this package transfers them to a new combined problem.

Files (keep together)
economics-core-inputs.json       Fixed model, four policies, 13 release records.
economics-core-analysis.py       Pure-standard-library reference implementation.
economics-core-benchmark.json    Frozen full results, including 20 assignments.
economics-core-README.txt        This model and reproducibility record.
The complete prompts, derivations, scoring and instructor guide are in the
library's economics-core-assessment.html. The source verifier is separately
book/scripts/check_economics_core.py. No network, package installation or random
seed is used. Python 3.9+ is sufficient. Work in a fresh directory containing
these files, then run:

python3 economics-core-analysis.py
python3 economics-core-analysis.py economics-core-inputs.json > my-results.json

The script prints only JSON on success. Compare parsed JSON, not whitespace.
The importable analyze(data) returns JSON-serializable output without printing.
It does not mutate the input. The CLI does not overwrite input or benchmark.
Do your own implementation/analysis first; running the reference is not evidence
of mastery. Inspect the complete argument and explain any discrepancy.

Schema and units
Top-level fields: schema, provenance, units, model, policies, pilot.
Schema is economics-core-1. Every numerical economic input is a rational string,
for example "8/3". No float/bool shorthand. Exact outputs are fraction strings;
counts and the assignment count remain JSON integers. No NaN/Infinity values.
Currency HC; energy flows energy units per period; numeraire good costs 1 HC;
exchange is HC per foreign currency FU. Pilot outcomes are energy units per
community per month. Do not label these USD or resident-weighted observations.
The model dictionary and units must match the supported contract exactly. This
intentional restriction prevents changed constants silently keeping old income,
base-price, welfare or terminal labels. To change them, derive a new model and
update implementation, metadata and independent checks together.

Policies have unique id and kind. A tax policy additionally has tariff in [0,2]
and carbon in [0,10]. A quota policy instead has cap in [0,8]. No unknown fields.
These intervals keep the importing branch valid; the implementation also checks
imports and current numeraire balances. Boundary carbon >= consumer price gives
zero domestic output. At cap=0 the shadow value 8 is a marginal scarcity value,
not an observed price on positive permit trades. Policy rows may be added,
removed or reordered within this supported model. The four supplied rows are
baseline (0,0), carbon (0,8/3), tariff_carbon (2,10/3), and quota cap4.

Sector model
BA(x)=20x-x^2/2; BB(y)=12y-y^2/2. Utilities add numeraire; B also bears q^2/4.
A owns all energy industry profit. Industry uses q^2/2 numeraire intermediate
input. Foreign energy price is fixed8 with no retaliation. p=8+t,
x=max(20-p,0), y=max(12-p,0), D=x+y. Under production tax tau,
q=max(p-tau,0); under auctioned quota q=cap, p=8, permit shadow=8-q.
M=D-q>=0. Tax receipts=tau*q+t*M. Quota receipts=(8-q)*q instead.
All policy receipts R go to B. Firm profit=p*q-q^2/2 minus carbon/permit fees;
there is no simultaneous permit fee and carbon tax in this contract.
Auction payments are stipulated current production levies for a one-period
permission, with no opening or closing permit asset. This is the case
classification, not a claim about every real permit auction.
Consumer surplus is x^2/2 and y^2/2. Sector ownership welfare components:
WA=CSA+profit, WB=CSB+R-q^2/4. W=WA+WB also equals
BA+BB-q^2/2-8*M-q^2/4. W*=304/3 at (x,y,q)=(12,4,16/3).
The global certificate is
W*-W=(x-12)^2/2+(y-4)^2/2+3*(q-16/3)^2/4.
It holds for the whole feasible resource domain, not just the policy grid.

Domestic current resource and household capital accounts
Each household owns 100 of current numeraire output (total200). Government
consumes20, A invests10 and owns its terminal payoff10, exports of numeraire=20.
The rest is household numeraire and energy industry intermediate input.
Government opening debt50 is foreign held, HC denominated. Current interest2
is paid abroad once, and is the same net primary income -2 in country accounts.
The two households each pay current lump tax8. All R is rebated to B. B also
receives a foreign secondary transfer1. Net private external borrowing is 8M-25,
split equally as b=(8M-25)/2. Negative borrowing means foreign asset acquisition.
A's current numeraire zA=100+profit-8+b-p*x-10.
B's current numeraire zB=100+R+1-8+b-p*y.
Their sum is 150-q^2/2, so all200 numeraire resources are used exactly once.
Borrowing settles at period end in HC. Private borrowers repay b at terminal
date, gross return1, and negative b pays them -b. All ending public debt56
is repaid at terminal date with no further interest, funded by tax28 each; 25
repays common old principal and3 repays net new borrowing. These future terms
differ from the coupon paid this period on opening debt. Each household owns
half of the opening private FU assets/liabilities; they settle with no further
interest at unchanged e=11/5, giving each net receipt11/2HC. A also receives
investment payoff10. Both receive terminal numeraire endowment100. Zero time
discount and linear terminal numeraire utility are assumed. Terminal numeraire
is175/2-b for A and155/2-b for B, both positive on the supported domain. Their
sum equals210+closing NFA: terminal output200+investment output10 plus net
foreign claim settlement. All public/private claims then close. The common
100+11/2-25=161/2 per household and fixed government services cancel in policy
comparisons; subtract that161/2 to obtain reported adjusted utility.
Adjusted utility A=BA+zA-b-3+10=89+WA; B=BB+zB-damage-b-3=90+WB.
Thus differences equal the welfare changes; import borrowing is not free wealth.
Transfers T from B to A raise zA and adjusted UA by T and lower B by T, leaving
country accounts unchanged. Verify individual nonnegative consumption after T.

National, public and foreign accounts
C=pD+zA+zB; G=20; I=10; NX=20-8M.
Nominal GDP=200+p*q-q^2/2+t*M = C+G+I+NX.
Carbon/permit receipts are already within domestic output valued at p; do not
add them again. Tariffs are net import product taxes. Declared base-price GDP
uses energy price8 and tariff tax rate0: 200+8*q-q^2/2. Deflator=nominal/base.
This is a fixed-base teaching convention, not an official chain-volume method
and not welfare. GNI=GDP-2; GNDI=GDP-1; S=GNDI-C-G; CA=NX-1=S-I.
Public primary surplus=16+R-(20+R)=-4. End debt=50+2+4=56.
Opening principal maturing25; gross issuance=25+2+4=31. Net borrowing=6.
Public cash sources16+R+31 equal uses20+R+2+25. Debt ratio=56/GDP.
Private net borrowing8M-25 plus public6 equals -CA. Gross external liability
incurrence is6+max(private borrowing,0), asset acquisition=max(-private borrowing,0).
FA=assets acquired-liabilities incurred=CA, with KA=0 and no discrepancy.
Rollover25 offsets matured claims25; do not treat31 as new net foreign funds.
Opening NFA=2*(20FU-15FU)-50HC=-40HC.
FX valuation=(11/5-2)*(20-15)=1HC. Existing HC debt is not translated again.
All new flows settle after the FX movement, in HC. End NFA=-40+1+FA.
No further valuation, writeoff or capital transfer is assumed.

Release keys and empirical design
communities must be A...F; baseline April2024, followup May2024. Assignment is
on May1 (assignment_date=2024-05-01), after baseline measurement with no
anticipation and before May outcomes. treated is a
three-element distinct subset; assignment is uniform-exactly-3-of-6. The target
weights each community equally, not each resident. Complete baseline/followup
coverage at the chosen cutoff is mandatory. Each record contains community,
period YYYY-MM, released YYYY-MM-DD, and usage (nonnegative rational string).
The unique key is community/period/released. A release must be after its complete
measurement month. Select latest released<=cutoff independently for each unit/month.
The 12 initial rows are released May10 for April and June10 for May; the 13th
row revises A's May usage8 to9 on July1. Original cutoff is June15. Later cutoff
is allowed for an explicit revision exercise, and outputs carry the changed date.
Rows can be reordered without altering results; duplicate releases are rejected.
Original changes=(-2,-2,0,0,1,1), observed offer contrast=-2. Enumerate all20
three-of-six assignments under the sharp null that the offer changes no unit's
outcome, with no interference. Two-sided tail includes equality: 4/20=1/5.
Later revision changes contrast to -5/3 while p happens to stay1/5. A zero average
null alone does not justify the sharp-null distribution. Randomization identifies
the design's offer effect under its assumptions, not structural national demand,
pollution damage or universal carbon-policy welfare. Do not fit those parameters
from this six-community pilot.

Audit and grading
Use the page's five20-point practical domains and full instructor guide. Required
checks include two independent GDP routes, household and government cash closure,
resource versus ownership welfare, terminal repayment, CA=S-I=FA, NFA stock-flow
reconciliation, exact assignment enumeration, historical availability, and wrong-
unit/duplicate/missing-data rejection. Compare a quota16/3 with carbon8/3, carbon
at/beyond shutdown, and a damaged output identity; finite grids do not replace
the analytic global certificate. The source checker additionally checks both
written forms using exact fractions and independent constructions. It does not
certify visual layout or a learner's independent performance. No external human
certification, empirical parameter validation or national policy forecast is claimed.
