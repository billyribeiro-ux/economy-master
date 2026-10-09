VOLUME 11 CHAPTER 09 — CURRENCY, SOVEREIGN AND CROSS-BORDER RISK
Original synthetic laboratory; edition date 9 October 2026

PURPOSE AND PROVENANCE

This is one finite cash-and-claim laboratory, not a market feed, country rating,
current legal assessment, accounting standard or estimate of default probability.
All input numbers and contracts are original teaching assumptions. H and F are
different currencies. Spot and fixing quotes are H per F. Every amount uses the
same numerical scale (for example millions) within its own currency.

The package connects an ideal covered-forward price to a foreign-receivable
payment ladder, then separates that corporation from a sovereign resource ladder
and a deliberately separate sovereign willingness menu. No corporate cash is
available to the sovereign merely because the cases appear in the same report.
Every right, policy and deadline used by the calculations is stated below. The
manuscript supplies the proofs, independent examples and eight solved exercises.

FILES

v11-c09-inputs.json    Original bounded input contract.
v11-c09-analysis.py    Python 3 standard-library implementation; no dependencies.
v11-c09-output.json   Exact deterministic report for those inputs.
v11-c09-README.txt    This execution and interpretation contract.
v11-c09-manifest.json SHA256 and byte counts for exactly the four files above.

The chapter, independent checker and review/source records are separate review
artifacts. The author record binds eight nonself author files; a later independent
peer must bind all nine final author files. A hash proves identity, not correctness.

EXECUTION

From any working directory:
  python3 /path/to/v11-c09-analysis.py
  python3 -O /path/to/v11-c09-analysis.py

The default input and output are beside the implementation, independent of the
current working directory. Both commands quietly write v11-c09-output.json.
Explicit paths:
  python3 /path/to/v11-c09-analysis.py --input /path/to/input.json --output /path/to/result.json

Every successful model CLI run is quiet; the output's parent directory must
already exist. Validation occurs before any output write. Invalid data or I/O
errors produce exit status 2 and an error on stderr; no output report is written.
Output may replace an ordinary chosen report, but may not overwrite the selected
input or implementation through direct, resolved, symbolic-link or hard-link
aliases. Alias tests are actually executed by the checker in temporary directories
under both normal and optimized Python. These are single-process lab protections,
not a defense against an adversarial process racing filesystem changes.

For programmatic use, import the module by its file path with importlib.util and
call run(data). Import and run are quiet. run does not mutate data, access files,
use randomness or return Fraction objects: every rational output is a reduced
fraction string, including integers such as "0". Booleans remain JSON booleans.
No assertion controls validity, so python -O cannot remove a domain guard.

The independent checker in scripts/check_v11_c09.py provides a quiet check(root)
returning a bounded summary; its CLI prints that summary. It calculates its own
oracles from the input contract and never uses implementation helper functions as
an oracle. CLI validation and alias attempts run against temporary copies, leaving
the supplied files unchanged. The final package is also run in isolation with no
repository-relative import requirement.

EXACT INPUT DOMAIN

Objects require exactly their documented keys: missing and unknown keys reject.
The root keys are schema, parity, exporter, export_scenarios,
hedge_design_scenarios, sovereign, sovereign_scenarios, willingness, rescheduling.
schema is integer 1, not a Boolean. JSON duplicate keys and nonfinite constants
reject before run. CLI input is limited to 150000 bytes. Nested unsupported
containers and JSON numbers where rational strings are required reject.

All quantities are strings matching a bounded decimal/rational syntax: optional
leading minus, then 0 or at most nine integer digits with no leading zero; optional
decimal of one to eight digits OR a slash followed by one to nine positive integer
denominator digits, without leading zero. No exponent, plus sign, whitespace,
Infinity, NaN or zero denominator is allowed. Signs are parsed but all quantity
domains below are nonnegative. The grammar and intervals make the input domain
finite and the exact rational computation bounded. Zero and negative net interest
are supported through positive gross factors below one. This is deliberately not
an arbitrary-precision or general JSON interchange API.

Unless a narrower bound is specified, quantities lie in [0,10000]. All spot/fixing
quotes lie in [1/100,100] H/F. Gross funding factors lie in [1/2,2]. All tests use
explicit exceptions rather than optimization-sensitive assertions.

parity:
  spot_H_per_F, home_gross, foreign_gross.
  The last two are gross accumulation factors to one common ideal maturity.

exporter:
  offshore_cash_H, net_receivable_F, debt_H, hedge_F.
  All in [0,10000]; 0 <= hedge_F <= net_receivable_F. The net receivable is after
  an enforceably matched same-event F cost. The manuscript's 120F gross receipt
  and 40F cost produce the one 80F input; neither is added again by the model.

export_scenarios:
  List of 1 through 8 objects, each containing exactly:
  id, spot_H_per_F, fixing_H_per_F, conversion_cap_F, transfer_cap_H,
  margin_H_per_hedged_F, positive_settlement_fraction, receipt_before_cutoff.
  id is a distinct string: lowercase ASCII letter followed by up to39 lowercase
  letters, digits or underscores. Caps lie in [0,10000]. Margin rate lies in[0,2]
  H per hedged F. Realized positive payment fraction lies in[0,1]. Receipt timing
  is an actual Boolean, not 0/1 or a string. A false value means the entire net
  receivable arrives at the stated later release date; no intermediate fraction
  is supported. Spot and fixing may differ independently within their bounds.

hedge_design_scenarios:
  A list of 1 through 4 distinct existing exporter scenario ids. The hedge-design
  certificate covers only these selected states, not every supplied scenario.
  Its chosen h lies in [0,net_receivable_F], separate from the supplied hedge_F.

sovereign:
  opening_spot_H_per_F, reserves_F, blocked_reserves_F, reserve_floor_F,
  cash_after_primary_spending_H, local_due_H, foreign_due_F,
  other_foreign_principal_F, new_loan_gross.
  The two positive quote/gross fields have the bounds above; other fields are
  in [0,10000]. blocked_reserves_F + reserve_floor_F <= reserves_F. This ensures
  the opening usable floor is respected; the scenario may still miss payments.
  H cash is already net of primary spending; local_due_H is additional debt
  service, never primary spending counted again. No later interest accrues in
  the current principal bridge; new_loan_gross states a separate later obligation.

sovereign_scenarios:
  List of 1 through 8 objects with distinct ids under the same id syntax:
  id, spot_H_per_F, export_fiscal_receipt_F, essential_imports_F,
  new_borrowing_F, conversion_cap_F.
  Quotes have the bounds above; amounts lie in [0,10000]. The F fiscal receipt
  is already collected by the modeled fiscal authority, not national private
  export earnings it can automatically appropriate. Borrowing is actual settled
  new finance, not an assumed rollover of the old debt without a transaction.

willingness:
  resources_H, capacity_F, promised_F, default_cost_H, spots_H_per_F.
  The first four quantities are in [0,10000]; spots is a list of1 through4 quotes
  in the spot interval. resources_H and default_cost_H are H-equivalent linear
  welfare units. Scores can be negative; that is not negative cash. This menu
  is separate from the sovereign capacity ledger and does not execute its cash.

rescheduling:
  due_F, replacement_F, discount_one, discount_two.
  Face amounts in [0,10000]; discount factors in [1/100,2], not necessarily
  declining. They are supplied common deterministic valuation weights, not
  inferred risky bond prices. The first claim is due at date1, replacement at2.

EXPORTER RIGHTS AND CLOCK

One corporation, two account locations, two currencies. No subsidiary guarantee,
automatic legal netting or credit line is implicit. The ideal benchmark forward
K = spot0*home_gross/foreign_gross uses unrestricted same-credit two-way trades.
Its hypothetical arbitrage proof does not assert that Cedar's restricted and
counterparty-risky NDF is fairly priced under the later scenarios. The existing
NDF's stated strike is set to this numerical K by the synthetic input convention.

0. Existing offshore cash u and an optional externally supplied H cash-equity
   contribution x are available before the first modeled cutoff. There is no
   issue cost, repayment or interest on this cash inside the short cash ladder.
1. Early collateral requirement m=a*h. Post min(available offshore cash,m).
   Posted collateral remains segregated property of the firm, earns no interest
   in this ladder, cannot pay the loan now, and returns in full only at step5.
   Unposted collateral is a breach, separately reported; it is not loan proceeds.
2. Receive the net F amount if the timing Boolean permits it. Convert min(F
   arrived,conversion cap) at executable spot S. Transfer min(converted H,
   transfer cap). Preserve the remaining onshore H and F inventory.
3. Contractual NDF payoff G=h*(K-fixing). If G is positive, receive rho*G offshore
   and permanently write off the remainder. If G is negative, owe -G in full;
   pay as much as available, leaving any unpaid portion as a financial liability.
4. Pay offshore H debt from remaining cash, preserving any unpaid liability.
   The published cutoff result is here, before the collateral/late receipt.
5. Return actually posted collateral, and receive the delayed net F amount onshore
   if applicable. No additional conversion or automatic late debt repayment is
   modeled. Closing liabilities are still those left at the original cutoff.

If collateral is short, steps2-5 are explicitly a conditional continuation:
contracts are not terminated or accelerated, no penalties arise, and later
receipts remain enforceable. This is a stipulated diagnostic scenario, not a
prediction about an actual margin default. The all_cutoffs_met Boolean remains
false even if later wealth is positive. A real termination clause would require
new cash flows, rights and timing, not a relabeling of this report.

For fixed hedge h let t be the usable H transfer and let G+ and G- denote the
positive and negative parts of G. Full payment requires both prefix balances:
  u+x-m >=0;
  u+x-m+t+rho*G+-G--D >=0.
Thus the minimum total early cash-equity contribution is
  max(0,m-u,m+D+G--u-t-rho*G+).
This number is the required total contribution relative to original u; it is not
an extra residual contribution after a funded design's reported x is added.
For insufficient cash the actual-payment trail never posts negative cash.

After step5 the identity is:
  offshore H + onshore H + S*onshore F - unpaid NDF - unpaid debt
  = original u + injected x + net F*S + realized positive NDF receipt
    - full negative NDF amount owed - original debt D.
The output checks zero value_residual_H. It is a translated account identity with
the scenario S, no discounting or liquidation haircut. It is not an accessible
offshore cash valuation and not a current accounting classification opinion.

EXPORTER BASELINE ANCHORS

K=106/85H/F; ideal gross full-hedge receipt1696/17H. With u12 and D100,
later translated net value is200/17H in clear, weak, both lock, margin and delay
states. Key actual cutoff results, in H:
  clear/weak: post4, debt paid100, cutoff cash132/17, later cash200/17;
  transfer lock: transfer40, onshore24H, debt arrears276/17;
  conversion lock: transfer40, onshore30F at S4/5, debt arrears276/17;
  joint: post6, transfer32, onshore8H+30F, derivative claim472/17;
         actual derivative receipt236/17, debt arrears818/17,
         later net value-172/17;
  margin squeeze: required18, posted12, unposted6; NDF owed344/17;
         debt arrears4/17; complete early contribution106/17;
  receipt delay: no current conversion; NDF receipt608/17;
         debt arrears956/17 and same required early contribution.

HEDGE DESIGN

Only weak_currency and margin_squeeze enter the supplied design selection. With
0<=h<=80, the five constraints on a common early contribution x are:
  0, h/20-12, 24-27h/68, 9h/40-12, 65h/136-32.
The finite solver checks interval endpoints and all pairwise intersections within
the interval. This is a complete method for the maximum of finitely many affine
functions: the ordering cannot change between these points. Parallel or duplicate
lines need no intersection, and h=0=n is allowed. At most9 lines (four selected
states plus zero) give at most38 candidates before deduplication; no grid or
unbounded search is used. Exact ties choose the smallest h among minimizers.

For the supplied two states, h=2720/47F and x=48/47H. The active weak late and
squeeze early constraints both equal48/47. Their weighted lower bound uses17/47
and30/47 respectively; the h coefficients cancel. The two remaining nonzero
constraints equal-428/47 and-204/47 at the optimum. Zero is smaller. Residual
terminal spot exposure is1040/47F. By contrast no hedge needs24H and full80F hedge
needs106/17H. This is a cash-feasibility objective over a declared subset, not a
universal optimal hedge or a certificate for transfer, joint or receipt-delay
states. Funded selected-scenario trails are reported separately and must meet all
cutoffs. The contract assumes the same per-unit strike/margin rules for all h.

SOVEREIGN CAPACITY POLICY, SEPARATE FROM WILLINGNESS

The authority may deploy exactly reserves less blocked reserves; this is an
explicit fictional authority assumption. The blocked amount is released later,
never counted at the payment cutoff. It preserves an available F floor. It first
pays local H service as far as H cash allows, then purchases F using remaining H
subject to an executable F cap. The dealer receives the H paid for that F.
Collected F fiscal receipts and actual new F loan proceeds are received before
essential F imports, then maturing F debt. Pay each only from F above the reserve
floor; preserve any arrears. No cash, debt or account is silently consolidated
with Cedar or with private exporters. all_current_payments_met includes local,
import and foreign debt payments but does not certify future maturities.

If A is F before external payments, the necessary extra F receipt is
max(0,floor+imports+foreign_due-A). It is minimum_external_topup_F, not a universal
funding cure: an earlier local H shortfall cannot be repaired under the one-way
currency-purchase rule merely by this F amount. A loan and a grant can deliver the
same current F while creating different future obligations.

Foreign principal satisfies closing = old due + other old principal + new loan
- actual principal paid. No interest accrues within this snapshot. New loan's
later amount = new principal * new_loan_gross, separately dated and not paid now.
The H foreign-debt value change decomposes exactly into
  old F principal*(new spot-opening spot)
  + (new F borrowing-actual F principal paid)*new spot.
Remaining foreign principal includes arrears; the scalar closing stock does not
identify their maturity or legal consequences.

Reference: pay36H, buy12F for24H, keep40H. F before payments64, imports12,
debt40, usable reserves12 and blocked8. Closing foreign principal80, made of
60old future+20new; new loan later due22. Depreciation-only buys the same12F
for36H and keeps28H; F amounts are unchanged. Rollover stop buys6F for18H,
keeps46H, has36F, pays12imports and20debt, keeps4usable and8blocked F;
20F remains in arrears, with60F future principal. Closing foreign principal is
again80 but maturity composition differs. With opening spot2 and later3, H debt
value change40 = revaluation100 + transactions(-60). The reference value change
is-40H, all transactions. A20F timely grant clears the stop's current F gap and
leaves60foreign principal; a20F new loan clears it but leaves80 and later22due.

WILLINGNESS AND RESCHEDULING

The separate willingness menu compares resources_H-S*promised_F against
resources_H-default_cost_H. Full payment is eligible only if capacity_F is at
least promised_F. A feasible exact tie chooses repayment. Output may print the
hypothetical repayment score even if infeasible, but it is not selected. Scores
are linear welfare units, not cash balances. Two actions, exogenous default cost,
no bargaining or creditor response: none of these is an estimated sovereign
behavioral law. The sovereign capacity ledgers do not execute this menu's choices.
Baseline capacity50F/promised40F gives scores120vs110 atS2 (repay),80vs110 atS3
(default_or_restructure). A feasible tie occurs atS9/4.

The rescheduling comparison is independent again: original40F at date1 has
PV38F; replacement44F at date2 hasPV198/5F. Creditor PV rises8/5F while the first
cutoff's40F need disappears and44F appears later. PV-preserving replacement is
380/9F. These supplied deterministic discount factors do not price sovereign
default risk or establish all-creditor consent or future solvency.

INTERPRETATION AND EXTENSION LIMITS

The input domain supports zero balances/notional/caps/payment fractions, negative
net interest via gross factors below1, appreciation/depreciation, fixing basis,
full/zero recovery, late receipts, local and external payment failures, no new
borrowing, binding/nonbinding reserve floors and nonmonotone positive discount
factors. It deliberately excludes short negative hedge notionals, uncertain
receivable volume, costs/endogenous behavior, gross cross-entity netting, actual
legal enforcement, general sovereign bargaining, endogenous exchange rates,
fire sales and intraday events beyond the stipulated order. Adding any changes
requires a new model and proof, not merely a new label on this output.

No probability is assigned to exporter or sovereign scenarios. The physical
two-state probability calculation in Worked case1 is a separate teaching example.
The K benchmark is not that distribution's mean. No risk-neutral law, current
country control or observed market price is inferred. Primary references support
their narrowly described methods/definitions only; numerical results are original.

Review is reproducible author and separate-agent review, not independent human
professional certification or evidence of browser/mobile/print visual inspection.
