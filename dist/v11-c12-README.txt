Meridian: risk governance and institutional integration
Original synthetic teaching case. Python standard library only.

Read v11-c12.html for the complete contract, proofs and solved exercises.
Units are CU and three specified contract cutoffs, not annual observations.
No real institution, current market data, legal power, regulatory ratio or
estimated probability is represented by the input.

REPRODUCE
Keep v11-c12-analysis.py and v11-c12-inputs.json in the same directory:
  python3 v11-c12-analysis.py
  python3 -O v11-c12-analysis.py --input v11-c12-inputs.json --output result.json
Both are silent on success; exact canonical output has sorted JSON keys and
a final newline. The defaults resolve beside the model, independent of cwd.
Import through importlib.util or runpy, then call run(data). It does not mutate
the input, print, write files, use a random generator or access the network.
Exact results are rational strings; JSON schema/count/cutoff fields are integers.

CONTRACT AND TIMING
Opening cash24, 60 securities at1, loans116; deposits140, short debt30, equity30.
Only30 owned security units are eligible for the new facility, with no prior
pledge. Actual growth deposits arrive before the equal new lending is paid.
Cash equity b arrives before the risk period. Term replacement t is received
then used to repay old principal; its fee.02t is paid/expensed. Remaining old
short30-t matures at cutoff1. Rollover rho*(30-t) is funded before that deadline
and due at2 with interest.02R. Term coupons.01t are due at all3 cutoffs; term
principal is due at3. Secured cash is available only at1, capped by both stated
facility ceiling and eligible units*price*(1-haircut); it is due at2 with.03g
interest. Repaid collateral is released. No later draw, sale, external support
or automatic netting is assumed. Scenario loan principal receipts never exceed
the remaining post-writeoff book. Deposit withdrawals never exceed deposits.
All receipts precede the payments of the same cutoff. Deposits pay no interest.
Security and loan marks occur once; later principal collections exchange assets.

The exact model allows bounded alternate inputs in this same contract, including
different scenario rates, grids and arrival availability. It does not add an
unmodeled contractual right. Decimal strings are required for financial inputs;
floats, booleans as numbers, nonfinite/exponent notation and unexpected keys are
rejected. Grid sizes are1..5, scenarios1..6, each dated vector exactly3; duplicate
choices/IDs, negative available resources and impossible claim collections fail.
See validate() for explicit range bounds; they are implementation scope, not
financial theory. JSON duplicates and nonfinite constants fail, and the input
file is capped at65536 bytes. Direct/resolved/symlink/hardlink output aliases of
the model or input are rejected before output is opened. Invalid input leaves
an existing destination intact. The manifest binds input, model, output, README;
it is an integrity record, not proof of authenticity or factual accuracy.

DECISION AND PROOF BOUNDARY
Cash>=5 and equity>=20 are closing limits at cutoffs1,2,3. Concentration is the
approval-time gross loan ratio(36+x)/(116+x), initially limited to.5. These are
board choices, not law or intraday capital rules. The selected execution has
nonnegative cash at every posted event. Its equity briefly reaches18.6 before
first interest, so an all-events20 requirement would require additional support.
Residual deposits and assets after cutoff3 remain; no complete runoff is proved.

For each fixed policy/scenario, A1 is cash after all planned first payments
excluding secured cash. Minimum draw g*=max(0,cash_floor-A1). If timely facility
capacity cannot cover it, the policy fails the first floor. Extra draw Delta
increases first cash but lowers later cash/equity by secured_interest*Delta;
nonnegative interest and no later reinvestment make the minimum draw sufficient
to test every available draw. The other cutoff and concentration limits remain
necessary. Increasing debt cannot be presumed to improve safety.

Selection maximizes lending, then minimizes the DECLARED COMMITMENT SCORE
equity_charge*b+(term_fee+3*term_coupon)*t. The equity charge is an opportunity
metric, not a cash dividend. The score excludes scenario-dependent rollover and
secured interest; these are still included in every actual cash/equity constraint.
It is not total funding cost, expected profit, welfare or a general market price.
Exact ties prefer lower equity then lower term choices. There are no scenario
probabilities in financial selection. The finite enumeration certifies only the
stated candidate set, joint scenarios, timing and board objective.

REJECTED PROJECTIONS VERSUS EXECUTION
Candidates contain signed cash_after_full_planned_payments. If negative, that
is missing financing under counterfactual full payments, NOT an executed cash
balance. Later rows of a rejected candidate remain conditional full-payment
projections; they do not model a default continuation or erase unpaid claims.
Only selected_execution posts actual nonnegative asset/debt accounts and dated
changes. It includes received cash equity, growth deposits/loans, funded term
replacement/fee, joint marks, operating expense, loan receipts, contracted
rollover, collateral draw, each principal/interest payment and withdrawals.
Each event checks assets-liabilities=equity. When no candidate is feasible, output
has null selection and no execution: a prompt for an actual new response, not an
approval.

BASELINE ANCHORS
36 candidate policies, exactly3 feasible: x0,10,20 with b20,t20. Select20,20,20;
score13/5. Joint A1=-38/5, capacity27/2, draw63/5 and pledge28 units. Joint
closing cash5,8911/500,4311/500; equity102/5,11411/500,12311/500. Final deposits81,
loans52, securities45. Calm cash36.4,72,62.8; equity51.4,54,55.8. Moderate
cash15.4,46.1,36.9; equity37.4,40.1,41.9. Mark and receipt timing are essential.
Concentration.4 selects10,20,20; late joint facility makes the original grid
infeasible. With extra equity choice30, late facility selects10,30,20; if timely,
it selects30,30,20. Advance5 withdrawals from joint cutoff2 to1 and the original
grid supports only x0. Secured interest.4 makes the old plan's last cash3.96 and
second equity18.16, selecting x10 instead. Each intervention changes the contract
explicitly, not merely a reported dashboard label.

INCENTIVES
Manager observes a reportable condition before choosing disclosure/concealment.
Bonus4 if concealment escapes; detection cancels it and collects escrowed penalty6.
Manager escrow is outside Meridian and cannot fund its obligations. Audit common
failure.2 and conditional detection.5 imply p.4. Truth and concealment both have
expected payoff0: weak preference, no strict deterrence or selection guarantee.
Conditional detection.75 gives p.6 and truthful advantage2. With false-positive
probability alpha, honest payoff=-alpha*f and concealment payoff=g-p*(g+f).
Truthful advantage=p*(g+f)-g-alpha*f; threshold(g+alpha*f)/(g+f). Probabilities,
collectibility and all behavioral assumptions are stipulated, not calibrated.

PROVENANCE AND LIMITS
All cases/proofs/problems are original. The chapter cites precisely scoped dated
BCBS2015 and OECD2023 governance guidance, distinguished from actual national law.
Author/coordinator/separate-agent checking is not external human certification.
Actual risk management also needs a justified scenario set, evidence and legal
rights, operational delivery, authority, independent challenge and supervision.
