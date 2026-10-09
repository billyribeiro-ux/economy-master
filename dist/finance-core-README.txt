MORROW COMPONENTS AND CEDAR RESERVE
Finance-core integrated project | original synthetic contract | 9 October 2026

This package is an instructor benchmark for an independently submitted project.
It is not an investment recommendation, accounting standard, legal opinion,
observed dataset, regulatory calculation or proof of actual settlement. The
computation does not replace separate substantive peer and coordinator review.
The full learner brief, five-domain 100-point rubric, instructor guide and six
transfer solutions are in the finance-core assessment's project section.

FILES AND REPRODUCTION

Keep these files together in any directory:
  finance-core-inputs.json       original contract and six adjustable inputs
  finance-core-analysis.py       Python 3 standard-library model
  finance-core-output.json       saved baseline evidence
  finance-core-README.txt        this file
  finance-core-manifest.json     byte lengths/SHA256 of the four files above

From any working directory, use an absolute path to the downloaded code:
  python3 /absolute/path/finance-core-analysis.py
This is quiet on success and writes the neighboring finance-core-output.json.
It reads the neighboring inputs, independently of the current working directory.
For another input/output pair:
  python3 /absolute/path/finance-core-analysis.py --input /absolute/path/case.json --output /absolute/path/result.json
The same command prefixed with python3 -O has the same decisions and validation.
No package, network, credentials, browser or third-party module is required.
The output's parent directory must already exist. Invalid input or an unsafe
output target exits 2, explains the failure on stderr and does not write output.
The model does not offer an stdout-dump mode.

Quiet Python API, using only the standard library:
  import importlib.util, json
  spec = importlib.util.spec_from_file_location("cedar", "/absolute/path/finance-core-analysis.py")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  with open("/absolute/path/finance-core-inputs.json", encoding="utf-8") as handle:
      data = json.load(handle)
  result = module.run(data)
  encoded = json.dumps(result, allow_nan=False)

run(data) does not mutate data, read files, print, change the working directory
or write a result. It returns JSON-safe dictionaries, lists, finite numbers,
strings, booleans and null. Repeated calls are deterministic. Calculations and
decisions use exact Fraction arithmetic from the input numbers' decimal text;
ordinary output numbers are converted to finite Python integers/floats only at
the boundary. Selected exact fractions and the reverse certificate are also
reported as strings. Do not use rounded output to redo a close threshold test.

The entry point protects the actual input, model source, neighboring inputs,
README, manifest and, when present in the source tree, this project's HTML,
checker, source record and author record. It rejects direct paths, normalized
paths, symlinks and existing hardlinks to those files before writing. Protection
includes a custom --input outside the package. The intended output file itself
may be replaced. This is an input/source safety guard, not a filesystem sandbox.

The author's independent checker is scripts/check_finance_core_project.py in
the source edition. Its quiet check() API returns a strict JSON summary. Run:
  python3 /absolute/path/book/scripts/check_finance_core_project.py
  python3 -O /absolute/path/book/scripts/check_finance_core_project.py
The CLI emits only a compact JSON check summary. It reconstructs economics from
the original contract rather than treating the saved output as its oracle.
It includes focused transfers, actual alias refusals and temporary portable
copies. Its internal --no-isolation option avoids recursive copying when the
checker itself is tested in an exact nine-file temporary source package.

INFORMATION FLOW AND ORIGINAL DATA

Everything is original: the operating accounts, three states, contracts, prices,
physical probabilities, priorities, dates, budgets and policy menu. There is no
downloaded market series, estimated frequency or external data transformation.
Currency is CU throughout. t0 is entry; 09:00, 12:00 and 16:00 are three cutoffs
on one terminal day T. The bill discount factor from t0 to T is 9/10; intraday
carry is zero. A later receipt still cannot satisfy an earlier client deadline.

1. Historical parent, before the SPV investment:
   Opening cash/receivables/inventory/PPE = 10/20/30/60, total 120.
   Opening payables/debt/equity = 20/40/60, total 120.
   Recognize sales 100, purchases 50, COGS 60, cash operating cost 20,
   depreciation 10. Collect 90 from customers; pay suppliers 55.
   No tax, interest, distribution, new debt or other period transactions.
   Income 10; direct/indirect CFO 15; ending cash/AR/inventory/PPE
   = 25/30/20/50. Payables/debt/equity = 15/40/70; both totals 125.
   Pay all remaining AP 15 before investment, leaving exactly the parent's
   required operating reserve 10. This is a narrow dated gate. Later service
   on legacy debt 40 and the whole parent's valuation are outside this case.

2. Separate new production SPV:
   t0 equipment 30 plus inventory 20 needs actual cash 50. Inventory is fully
   consumed. Equipment depreciation is 20; its remaining book value is sold
   for 10 at T. Other operating cash cost is 30.
   Customer sales/cash are down/normal/up = 50/80/110. All are collected at
   12:00 before costs and claim payments. The equipment buyer pays 10 then.
   These named external payers are stipulated funded; their complete balance
   sheets are not modeled. Current-state cash estate is sales - 30 + 10.
   Terminal baseline estate 30/60/90; note face 50 pays 30/50/50;
   residual equity pays 0/10/40. Unpaid down note face 20 survives, with zero
   additional modeled recovery. It is not legally forgiven by a writeoff.

3. Prices and funding:
   Positive state prices are 1/5, 3/10, 2/5 and sum to the bill price 9/10.
   Prices of project/note/equity are 60/41/19. Initial investment 50 implies
   incremental opportunity NPV 10. Note proceeds 41 plus new equity 9 fund
   that investment. The new investor buys 9/19 of residual equity; the parent
   retains 10/19 for its pre-existing exclusive opportunity. The opportunity
   has zero book carrying amount and no cash contribution; do not spend it.
   Note book liability starts at proceeds 41 and accretes discount 9 before
   repayment. Pre-resolution book equity is -20/10/40. The down shareholder
   distribution is zero while unpaid creditor face survives.

4. Cedar's opening cash and ownership:
   The client payer starts with 60, pays 57.6, retains 2.4. The sponsor starts
   with 10, pays 6.4, retains 3.6. Cedar has exactly 64 actual cash. Client
   face is 20 due 09:00 and 44 due 12:00. The full-performance liability PV
   is 57.6 for performing supported policies. That is not a fair value for
   the defaulting liabilities of rejected portfolios. The fixed client
   subscription remains historical cash in all counterfactual comparisons.
   Sponsor equity starts at 6.4. No unmodeled contribution can fill a gap.

5. Other funded counterparties:
   A separate note underwriter starts with 50 and buys 1-x of the note.
   A separate equity subscriber starts with 20 and pays the new equity cash.
   The bill issuer starts with 100 plus Cedar's bill subscription, enough to
   redeem the purchased units. Initial equipment/inventory sellers receive
   30/20. An independent fee provider receives actual execution/custody fees.
   No provider's leftover cash belongs to Cedar or automatically finances it.

6. Existing protection and separate pools:
   The dealer initially owns one whole unit of EACH of two claims. It sells
   fraction h of the selected kind to Cedar and retains all other fractions.
   Purchase money goes to the dealer; it never enlarges a writer's pool.
   Escrow: down nominal claim capped at 20, against a pre-endowed cash pool
   20, available at 12:00. Other states have no triggered claim. At 12:00
   unused cash returns to that writer. Entry price 4 plus custody fee 0.4
   per unit. No baseline prior claim or collateral reuse.
   Credit-exposed: down nominal claim 20, against a distinct pre-endowed
   estate 12 available only at 16:00. Whole-unit actual down payment is 12,
   distributed pro rata to all holders. Unpaid nominal rights total 8, with
   no additional modeled recovery. In other states 12 returns to this writer
   at 16:00. Price 12/5, no additional custody fee.
   Idle provider cash stays unavailable until its stated release and belongs
   to its writer on release. It does not support earlier Cedar payments.
   The capped claim remains 20 when project down revenue deteriorates.

7. Finite mandate:
   x is 1/2, 3/4 or 1 of the note. For each x choose none, credit h=x/2 or x,
   or escrow h=x/2 or x: exactly 15 policies, no mixed protection or shorting.
   Pay note execution cost 0.1x plus escrow custody cost 0.4h if applicable.
   Put every remaining entry CU into bills. No borrowing is authorized.
   Require all client deadlines in each state and terminal cash minus any
   surviving client arrears at least 2. Maximize physical expected terminal
   net capital. Exact ties favor smaller x, then h, then claim label.
   Parent gate plus one qualifying reserve policy gives prospective approval.
   After a contractual shock, actual holdings stay at the original half-note,
   quarter-escrow position; actual approval uses that position's feasibility.
   These are original board choices, not regulatory or universal thresholds.

The modeled t0 transfer set has endowed cash 272 both before and after. At T,
each SPV/pool payment allocation reconciles to its particular resources. The
SPV customers and equipment buyer are external funded receipts by assumption;
this is not an audit of whole-economy cash endowments or real counterparties.

BASELINE EVIDENCE

Physical probabilities are 1/20, 11/20, 2/5, separately from state prices.
Four policies qualify: half note/quarter escrow; half note/half escrow;
three-quarter note/three-quarter escrow; whole note/whole escrow.
Unique optimum: x=1/2, escrow h=1/4. Purchases/fees are:
  note 41/2, execution 1/20, protection 1, custody 1/10, bills 847/20.
The bills pay 847/18 at 09:00. After paying clients 20 cash is 487/18.
At noon down note 15 and escrow 5 fund clients 44, leaving 55/18.
Normal/up note 25, no escrow payment, leave 145/18. There are no missed
client deadlines. Expected terminal capital is 281/36. Its current state-price
value is 25/4, equal to opening capital 32/5 less fees 3/20.

Cash-only net terminal benchmark is 64/9 (infeasible under the note mandate).
Selected losses relative to it are 73/18, -17/18, -17/18, mean -25/36.
Left VaR90 is -17/18. ES90 is 14/9: take down mass 1/20 and only 1/20 of
the large favorable-state atom. Tail risk does not prove cash timeliness.

The output summarizes all 15 policies, not every journal for every policy.
It gives the full entry ownership/funding record and three executed reserve
journals for the displayed policy. If no policy qualifies, selected_policy is
null; the shown ledger is explicitly the fixed baseline diagnostic position,
not an approved fallback. Shown terminal allocations include all SPV equity
and note recipients, both pools, idle returns and unpaid nominal rights.
After-trade revenue/priority/delivery shocks set comparison_scope to
historical_entry_counterfactuals. The selected_policy is then the best feasible
hypothetical ORIGINAL-ENTRY policy at historical tickets, not a switch that
can be executed now. Its shown entry/settlement ledger is counterfactual.
actual_after_trade_position separately reports the unchanged baseline holdings;
institution_approval tests those holdings and the parent gate. It may be false
while menu_has_feasible_policy is true. prospective_entry_approval is null.
There are no refund, unwind or post-shock rebalance prices in this contract.
Baseline and before-trade revenue information instead permit prospective entry
selection. A physical-probability-only change is a new prospective assessment.
Every approval field is a modeled gate, not verified external authority.

Entry dealer values are labeled reference quote values, not current marks
after a priority discovery. The project separately reports current claim PVs.

SUPPORTED INPUT DOMAIN AND TRANSFERS

Root keys are exactly schema, case, provenance, contract, experiment.
schema must be integer 1. case and every contract term are fixed as supplied.
provenance may be nonempty text of at most 512 characters. Unknown/missing
fields, changed structural terms and wrong JSON types are rejected. Numbers
must be actual int/float JSON values, not booleans or numeric strings. Their
finite decimal text is interpreted as an exact rational with REDUCED
denominator at most 10^12. This is not a decimal-place count: for example,
0.0001220703125 has 13 decimal places but denominator 8192 and is permitted.
The CLI input is capped at 32768 bytes, parsed as UTF-8 with duplicate-key,
nonfinite-constant and trailing-material rejection. Optimization does not
disable validation. No assertion statement is used for financial/domain gates.

The experiment has exactly these adjustable fields:
  historical_collections: number in [80,90]. Changes parent cash and AR only;
    recognized sales and income stay fixed. At 80 CFO is 5, post-AP cash zero,
    and integrated approval fails by the parent reserve gap of 10.
  down_revenue_loss: number in [0,10]. Reduces ONLY down-state project sales
    and cash. Actual project cash is 30-delta; protection stays capped at 20.
    Note unpaid face is 20+delta. The bound keeps all operating costs funded.
  information: "after_trade" or "before_trade". After_trade retains original
    ticket prices/issue proceeds and ownership; current claim marks and actual
    recovery change. The alternative-policy table compares hypothetical entry
    choices, not executable post-shock reallocations. Before_trade reprices
    ONLY the revenue change: note quote
    41-delta/5, new equity cash 9+delta/5, subscriber fraction (9+delta/5)/19.
    Bill purchases and every funding recipient are recomputed. Both are
    information contracts, not alternative labels on the same cash history.
  physical_probabilities: list of three finite, strictly positive numbers,
    exactly summing to one as decimal rationals. Prices remain fixed except
    for the explicitly supported before-trade note repricing. No inferred
    catastrophe probability or calibration is added.
  escrow_settlement: "12:00" or "16:00". The latter is an after-trade delay;
    the pool's senior payment, triggered claims and idle returns all move to
    that time. No original policy then meets the down noon obligation.
  escrow_senior_claim: number in [0,5], discovered after trade. The senior
    holder is paid this amount first from the fixed 20 pool in EVERY state at
    the escrow settlement time. Down residual pays the capped hedge pro rata;
    good-state residual returns to the writer. In down states unpaid hedge
    face equals the prior claim and remains split by actual claim ownership.
    The dealer's historical sale proceeds and other pool do not fill the gap.

Before_trade cannot be combined with escrow_senior_claim > 0 or a 16:00 escrow
settlement. Those are separate after-trade information failures; this model
does not silently price their new legal/timing contract. Valid after-trade
inputs may combine the permitted shocks and physical weights. The analytical
single-shock reverse certificate is omitted for any nonzero senior claim or
delayed delivery. Where present, it is about the fixed baseline half-note,
quarter-escrow position and TOTAL delta from baseline, not the currently
selected policy or a distance from the current input.

Focused solved interventions in the full guide:
  Revenue loss 5/2 after entry: the old partial position has 65/36 (<2).
    Full half-note escrow would have been the best qualifying entry policy,
    with down capital 67/12 and mean 325/48. Actual holdings do not switch,
    and actual post-trade approval fails pending a separately funded repair.
  Same loss known before entry: note 81/2, new equity cash 19/2, each equity
    owner holds one-half. The partial policy buys bills 213/5, retains 82/3
    after 09:00, and ends at 25/12 down, 25/3 otherwise; mean 385/48.
    Fixed-position floor boundaries are 19/9 after trade versus 19/7 before,
    inclusive. These exact fractions are analytical certificates, not JSON
    decimal approximations admitted as exact boundary inputs.
  Physical weights 3/10,3/10,2/5: choose full half-note protection, constant
    capital 41/6. Partial-policy mean is 59/9. Preference switch p=11/45;
    at equality the smaller-hedge tie rule selects the partial policy.
  Escrow at 16:00: baseline diagnostic pays 757/18 at noon, misses 35/18,
    cures it later and ends at 55/18. A new authorized bridge of 35/18 from
    an endowed provider with cash 2 would restore timing and be repaid from
    the late 5 receipt; provider interim cash is 1/18. This NEW action is
    solved separately, not inserted into the original 15-policy runtime menu.
  Senior claim 5: actual partial down capital 65/36, mean 1115/144; actual
    holdings fail the floor. The down pool pays senior 5, Cedar 15/4, dealer
    45/4, leaving hedge rights 5/4 and 15/4 unpaid. The best historical-entry
    counterfactual is full half-note escrow: down 13/3, other 41/6, mean
    161/24. Under that hypothetical holding the down pool pays senior 5,
    Cedar 15/2, dealer 15/2; hedge face 5 remains unpaid, split 5/2 each.
    Other states under either holding pay senior 5 and return 15 to the writer.

Transfer 6 is intentionally OUTSIDE run(data): add a fourth estate state 10
before the old 30/60/90, keep bill/note/equity prices 9/10,41,19, and solve
pi(t)=(t,1/5-2t,3/10+4t/3,2/5-t/3), 0<t<1/10. Capped protection has price
4-20t in OPEN interval (2,4). Subhedge 25 bills minus half a note costs 2;
superhedge 50 bills minus one note costs 4. Each endpoint permits a zero-cost
nonnegative, sometimes positive payoff under the stated reference-market
comparison rights. No catastrophe probability, continuum optimizer or new
empirical estimate is fabricated. Do not pass four states into the baseline.

SOURCES, VERIFICATION AND USE LIMITS

The guide/source record reuse already inspected primary scopes: SEC (2007)
statement connections; MIT (2003) debt face/proceeds/book-value distinctions;
Damodaran's FCFF/FCFE/working-capital definitions; Brunnermeier's one-period
pricing notes; CFA Institute's May 2010 institutional policy guide; Haugh's
2016 single-period completeness sections; Rockafellar-Uryasev's finite loss
atoms; BCBS September 2008 dated liquidity/collateral guidance. They establish
methodological context, not these original numbers, current national authority
or an observed model calibration. No new whole-document retrieval is claimed.

The independent checker recomputes accrual and cash, claim values/ownership,
every policy's objective and deadline results, selected cash/payment/pool
allocation, exact reverse/price-family proofs and the six transfer anchors.
It uses a threshold-minimization oracle for ES instead of the model's sorted
tail algorithm. Focused boundary inputs, supported-domain rejection, strict
JSON, API nonmutation/quietness, saved-output reproduction, actual alias guards
and portable normal/-O behavior complement those economic checks.

Hash bindings establish which bytes were reviewed; they do not prove theory,
actual payer solvency, legal priority, operating execution, empirical accuracy,
learner mastery or external academic certification. The decision is optimal
only in its stipulated menu and complete three-state table. A real institution
needs independent accounting, legal, operational and counterparty evidence.
Browser visual/mobile/keyboard/print checks are a separate library gate; this
standalone numerical package makes no claim that those UI checks were run.
