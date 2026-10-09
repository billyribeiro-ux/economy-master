PORTLIGHT: A FINITE BANK, PENSION AND CROSS-BORDER PAYMENT PROJECT
Original Volume 11 assessment. Standard-library Python only.

Read the project and complete instructor guide in v11.html, section project.
The editable project fragment is content/assessments/parts/v11-project.html.
All institutions, contracts, priorities, scenarios, probabilities and amounts
are original synthetic teaching inputs. H and F are distinct fictional currencies.
No observed market data, current law, actual institutional mandate, deposit
insurance, sponsor guarantee or empirical control probability is represented.

REPRODUCTION
Keep these together in any directory:
  v11-assessment-analysis.py
  v11-assessment-inputs.json
Run:
  python3 v11-assessment-analysis.py
  python3 -O v11-assessment-analysis.py
Or specify paths:
  python3 v11-assessment-analysis.py --input altered.json --output altered-output.json
Success is silent. Default input/output resolve beside the actual model file,
independently of the working directory. The default output is
v11-assessment-output.json. Sorted, indented JSON ends in one newline.
No package installation, randomness, network, environment credentials or chapter
module is required. The input/model pair is sufficient to calculate the report.

Import with importlib.util or runpy and call run(data). Import and run are quiet.
run does not mutate data, write files or retain mutable results between calls.
Its result uses rational strings for financial numbers and genuine JSON booleans,
integers, lists, objects, strings and null. It serializes with allow_nan=False.
Invalid contracts raise ValueError, including under python3 -O. The model never
relies on assert for validation. Every original baseline result is exact, apart
from the interpretation of a displayed yield boundary: that boundary is reported
as an exact rational enclosing interval, not rounded into a claimed equality.

The four-file manifest binds input, model, output and this README. The author
record separately binds all eight nonself payloads in the nine-file assignment.
scripts/check_v11_project.py is the independent original-contract author checker;
it is not the learner implementation and is not an independent human certificate.
Its check() API is quiet and returns a strict-JSON-safe summary. The complete
nine-file author package supports its standalone normal/optimized checks.

OPENING INSTITUTIONS AND FINANCED SOURCES
Reference spot is 2 H per F. Portlight owns H cash 20; F cash 6; H bill 20;
20 long-bond units worth 20 H; domestic borrower face 60 H; foreign claim 20 F.
Thus assets=20+12+20+20+60+40=172 H. Liabilities are household deposits 78 H,
pension deposit 12 H and foreign deposits 25 F=50 H: total 140 H, equity 32 H.
The bank holds 20 separate eligible long-bond units, with no prior pledge.
The maturing bill is a distinct unpledged asset and cannot also secure this line.

Pension cash 1 H plus its bank claim 12 H is 13 H against due benefits 15 H:
an explicit 2 H opening funding deficit. The bank's pension liability and the
pension's bank asset cancel when consolidating this pair. Pension claims are
reconciled at face in the payment model; this is not a certified market recovery
valuation after a bank default. Do not infer economic pension solvency from that
nominal identity alone. Unpaid benefits remain liabilities.

The sponsor has 30 H cash, separately endowed. It can subscribe bank equity
b in {0,10,20} H and contribute pension cash z in {0,2} H before deadlines.
The bank can preposition f in {0,5,10} F, paying initial_spot*f H first.
Every combination must have sufficient opening H and the sponsor's funded
budget must cover b+z. A subscription gives the new investor b/(E0+b) of bank
residual equity, floored at zero if equity is negative. It is not debt and not
a cash guarantee. Its marked stake is not an asset the bank can spend again.
The pension grant is separate from the bank subscription. The gross commitment
b+z is a decision metric, not welfare or net investment cost.

The private secured lender has 20 H cash, separate from the sponsor. It may draw
down only that endowment. The FX dealer has 100 H and 40 F, separate from both.
It funds prepositioning and early F delivery; late conversion uses its actual H.
The supported commitments are validated against those endowments, without
relying on hoped-for unrelated receipts. The collateral buyer has 20 H; its cash
paid is allocated to costs, the stated prior creditor and Portlight. No gross
collateral amount is counted twice. Lender collateral is Portlight's long bonds;
borrower recovery collateral is the borrower's separate asset.

Three other external cash sources are stipulated, not endogenously generated:
the bill issuer pays its promised 20 H at the final home cutoff; the domestic
borrower supplies its specified post-operation cash; the offshore issuer pays
the state-specific F recovery. Their payer, currency and arrival date are
explicit assumptions requiring evidence in real use. This is not a closed
whole-economy endowment audit. Conservation checks cover the modeled bank and
pension accounts, actual sponsor/lender/dealer cash movements and the collateral
proceeds allocation. They do not invent missing external payer balance sheets.

CLOCKS, MARKS AND CREDIT
The early and final dates are contractual cutoffs, NOT years.
Early 09:00: foreign deposits 15 F are due in the foreign account.
Early 10:00: borrower first cash arrives; lender funding can then arrive;
household deposits 18 H are paid before the pension deposit 12 H.
Early 10:15: pension benefits 15 H are due.
Final 17:00: delayed prefunding and offshore recovery arrive; remaining F
deposits, including any earlier arrears, are paid.
Final 18:00: bill and final borrower cash arrive; secured interest is accrued;
limited F-to-H conversion is delivered; secured debt is paid before remaining
household deposits and then pension arrears.
Final 18:15: pension applies actual late bank receipts to retained benefits.
All specified receipts precede their funded payment. No later money retroactively
satisfies an earlier deadline. The secured lender at 10:00 cannot fund 09:00.

At the reference mark long-bond price is 1 H per unit. In each state price is
q=1/(1+y)^2, a specified two-discount-period zero-coupon mark. Remaining maturity
and this mark are held fixed over the payment horizon. Long bonds do not mature
or sell during this case. The bill matures separately at its stated 20 H.
Secured interest 5% is for this contract, not an asserted annual rate.

After the received funding and prefunding transactions, before early payments,
revalue FX and long bonds and recognize both loan impairments. Domestic carrying
value becomes the total stipulated actual receipts. Foreign carrying face
becomes the actual final recovery in F. Subsequent collections reduce the carried
asset and increase cash without another expense. Original legal arrears survive.
With foreign credit, first revalue original net F exposure at the new spot,
then deduct impaired F principal at that same spot. Do not charge it twice.

The borrower promises 20 H early and 40 H finally, with zero contractual interest
in this case. Normal operating cash 20/40 pays the whole 60. Credit operating
cash 12/32 plus collateral 14 minus cost 2 and prior claim 2 gives final 42, total 54:
first arrears 8 and terminal arrears 6. Joint operating 8/28 plus collateral 18
minus cost 3 and prior claim 3 gives final 40, total 48: first and terminal arrears 12.
These residual nominal claims have zero carrying asset after the stated full
writeoff/collection sequence. A writeoff does not erase legal rights.

ACTUAL PAYMENT RULE
At early 09, buy only the missing F for the 15 F call, bounded by the early F cap
and available H at current spot. Delivered F is usable immediately. Pay only
available F and retain any unpaid deposit. Baseline prefunding is already
delivered. If prefund_timely is false, the H payment still occurred, bought F is
a titled in-transit asset, and it becomes spendable F only at final 17.

After early borrower cash, ask for the minimum secured advance that would pay
households 18 and pension 12 and leave H reserve 2. Cap the draw by lender cash
and eligible_units*q*(1-haircut). Pledge draw/[q*(1-haircut)] units.
Then make actual payments in the declared priority. Reserve 2 is a monitoring
criterion, NOT a claimant or withheld payment. If funding is inadequate the
bank pays available cash, possibly closes below 2, and retains creditor arrears.
The pension spends available own cash, sponsor grant and actual bank receipts.

At the final date, F creditors receive first use of the F account. H resources
receive the bill and borrower cash. Interest adds to the secured claim and is
an expense whether or not paid. Late conversion is precisely:
  min(remaining F, late F cap,
      max(0, reserve + secured claim + all remaining H deposits - H cash)/spot).
The dealer delivers that H before the home waterfall. Pay secured claim,
household deposits, then pension arrears, each capped by cash and claim size.
Release the pledged pool only after the secured claim is completely repaid;
otherwise retain the pledge and remaining debt. No foreclosure is silently
executed. The pension's later receipt can cure arrears, never the missed deadline.

There is no deposit interest, late fee, sale of long bonds, extra borrowing,
government payment, automatic netting, implied transfer permission or ignored
claim. Contract priorities are fictional stipulated rights, not insolvency law.
Every candidate has actual nonnegative cash/asset/liability positions. Negative
equity is possible and is reported; the model does not invent a legal process.

DECISION, VALUATION AND REVERSE STRESS
All bank and pension obligations must be timely; H cash>=2 and bank marked
equity>=20 at the EARLY HOME and FINAL HOME closes. There is no additional F
buffer, no intraday equity 20 claim and no regulatory-ratio claim. The model
executes failed candidates too, retaining partial payments and arrears.
Only policies passing every stated scenario enter the finite ranking:
lowest b+z, then lowest f, then lower b and z for exact ties.

The baseline selects b 20 H, f 10 F, z 2 H, uniquely among 18 candidates.
Joint first F cash 16 pays 15, leaves 1. Home cash 20 receives 8, draws 4, pays 30,
leaves 2. Capacity 20/3; pledge 12 of 20 long-bond units. First equity 251/9 H.
Final F cash 1+16 pays 10, leaves 7 F. Home resources 2+20+40=62; secured 4.2,
deposits 60 and reserve 2 require 66.2. Convert 7/5 F, leaving 28/5 F and 2 H.
Final equity=2+3*(28/5)+80/9=1246/45 H. No bank/pension arrears remain.
Normal final equity 52 H; credit final equity 393/10 H. Sponsor cash remaining 8 H;
its joint closing marked bank stake is 1246/117 H, subject to the model's marks.

Loss for a policy is E0+b minus its final bank equity, not E0 minus equity after
an undisclosed contribution. Selected losses are 0,127/10,1094/45 H with stipulated
PHYSICAL probabilities 1/2,1/3,1/6. Mean 2237/270; VaR at 3/4 is 127/10;
ES at 3/4 is 5519/270, using all joint probability 1/6 plus only 1/12 from the credit
atom. The probabilities do not weight feasibility, price claims or estimate
frequencies. No sampling, historical calibration or backtest is claimed.

The reverse certificate fixes the selected policy and every selected-state
input except long-bond yield. It obtains the requested draw and intersects the
collateral price floor with the final-equity price floor. Other cash receipts,
conversion limits and contractual rights stay fixed. In baseline joint stress:
  required draw 4; collateral floor q>=4/15; capital floor q>=3/50.
Thus the first boundary is q=4/15, y=sqrt(15)/2-1, equality feasible with final
equity 362/15 H. The first reserve breach is distinct from a missed creditor:
actual early H payment remains full down to q=2/15. Below the reserve boundary,
do not continue using a fixed 4 draw that no longer fits collateral.
The model bounds supported yields to [0,4] and reports an exact bisection bracket
only when a positive derived boundary lies in that domain. For a boundary
outside the supported domain, equality/bracket evidence is null, not an invented
feasible q=0 or an asserted extrapolation. This is a one-factor conditional
certificate, not an estimate of crisis probability or an optimized reverse search.

OUTPUT MAP
candidates lists every policy and each state's actual payments, borrower claim
record, equity bridge, first/final shortfalls, pledge, conversion and close
snapshots. Each snapshot includes H/F and in-transit bank accounts, remaining
liabilities, marked H equity, pension cash/benefits/face reconciliation, and
the sponsor/lender/dealer cash budgets. No rejected policy is called approved.
selected contains the uniquely ranked feasible plan and its complete 23-event
journals for all three states, or null if the menu has no feasible policy.
selected_loss_measure contains the probability-weighted loss/tail computation
only for an actual selected plan. reverse_stress contains the conditional
certificate. Both are null when selection is null. Borrower collateral_allocation
shows buyer cash before/after and cost/prior-creditor/bank recipients explicitly.

Meaningful changes include delayed F arrival, a binding late conversion cap,
changed benefit promise, inaccessible collateral, increased prior borrower
seniority, zero secured interest and exact boundary capacities. All carry the
same dates and payment rights unless the input expressly changes them. The
instructor guide proves minimum extra equity 8/7 for late cap 1 and 2/3 for eligible
units 10. Debt-to-equity conversion of a pension deposit is a distinct oral
contract transfer, not an undisclosed switch in the baseline code.

INPUT DOMAIN AND FILE SAFEGUARDS
Top-level and nested objects have exact required keys. Schema is the integer 1,
not a boolean. Provenance is a nonempty string of at most 500 characters.
Financial values must be bounded strings matching signed decimal or rational
syntax: up to 8 integer digits and 8 fractional or positive-denominator digits,
maximum 22 characters. Floats, numeric JSON fields, booleans as numbers,
nonfinite/exponent strings, zero denominators and unexpected keys fail.
Resources and monetary claims are nonnegative and at most 1000; decision amounts
at most 100. Spot is in [1/4,4], yield in [0,4], haircut in [0,1), interest in [0,1],
and risk alpha strictly between 0 and 1. Initial reference bank equity, both loan
faces and long-bond inventory must be positive. First borrower due is strictly
inside its face so both operating service ratios have positive denominators.
Other first deposit calls cannot exceed their total claims.

There are 1..4 distinct numerical choices per decision (at most 64 policies) and
1..5 uniquely named scenarios. Every scenario has positive probability and their
exact rational sum is 1. The reverse scenario must exist. prefund_timely is a
genuine boolean. Each menu combination must be fundable before the early date;
these restrictions deliberately exclude unsupported opening overdrafts. The
sponsor budget covers max b+max z. Dealer endowments cover prefunding plus early
F commitments and each late H conversion commitment. Eligible units cannot
exceed owned long bonds. Collateral proceeds cover costs/prior claim and cannot
exceed the buyer's cash. Actual loan/foreign receipts cannot exceed face. The
first borrower receipt cannot exceed its first scheduled principal. These are
implementation boundaries of this original experiment, not financial laws.

The CLI caps the input file at 65536 bytes, rejects duplicate JSON keys and
nonfinite constants, and emits a concise stderr error with exit 2 for invalid
input or protected paths. Direct, resolved-parent, symbolic-link and hard-link
output aliases of input or model are refused before opening output, including
the default output location. Invalid input preserves an existing destination.
Ordinary output writing is not a crash-safe atomic filesystem transaction; no
broader guarantee is inferred from the validation/alias tests.

SCOPED SOURCES AND LIMITS
The project reuses accepted scoped readings: Rockafellar–Uryasev general-loss
definitions/atoms and the finite Chapter 4 derivation; BCBS 2008 liquidity
availability/collateral/contingency passages; final BCBS 2018 principles 1–8;
and BCBS 2015 governance glossary/selected board, risk, reporting and incentive
paragraphs. See v11-project-sources.json for exact inherited scope. There is no
new retrieval claim or imported national legal authority. All numbers, proofs,
contracts, exercise variants and institutional procedures here are original.

Finite scenario coverage, marked balances and byte integrity do not establish
all-path solvency, executable external receipts, true account ownership, legal
authority, pension adequacy over a lifetime or effective organizational controls.
Assessment authoring, separate-agent peer review and coordinator checks are not
external human certification or browser visual/mobile/keyboard/print approval.
