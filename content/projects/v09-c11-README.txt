V09-C11 — Execution, trading costs and market microstructure

This package contains original synthetic teaching contracts, not observations,
backtest results, venue rules or calibrated impact estimates. Each case is an
independent market. Currency is CU; prices are CU/share and quantities are whole
shares. Interest is zero. No library, network connection or installation is needed.

RUN
Place v09-c11-inputs.json and v09-c11-analysis.py in the same directory:
  python3 -B v09-c11-analysis.py
  python3 -B v09-c11-analysis.py --input v09-c11-inputs.json --output reproduced.json
The first command prints JSON. With --output, success produces no stdout/stderr.
The default input is resolved next to the script, independently of the working
directory. Importing the module and calling run(data) performs no I/O or printing.
The return value is strict JSON compatible. All fractional calculated quantities
are canonical rational strings; integers used as counts remain integers. A missing
fill average is null, never zero. JSON formatting ends with one newline.

FILES
inputs: complete original contracts and assumptions.
analysis: strict validation and exact calculations, using fractions.Fraction.
output: entire frozen baseline result, including every capacity-grid point.
README: this document.
manifest: byte counts and SHA256 of these four files, excluding the manifest itself.
Within the library, scripts/check_v09_c11.py supplies independent focused checks.
The separate author review hashes the four assets, manifest, chapter, checker and
source proposals. Source excerpts are not redistributed with this offline package.

INPUT REPRESENTATION
Object keys are exact. Unknown, missing or duplicate JSON keys are rejected.
Numeric inputs must be JSON integers or decimal/rational strings, such as "0.05"
or "1/20". Booleans, binary floats, NaN, infinity and exponential notation are
rejected. Magnitude and rational denominator must be at most one billion; numeric
strings at most60 characters. The bounds are transparent teaching-domain limits.
Lists are finite and bounded. General quantities/times are integers0..10000;
strictly positive quantities are required for orders, trades and queue targets.
Snapshot levels and order/fill lists have at most100 entries. Queue has2..10 states.
The impact grid caps each block at100; requested quantity is0..201, allowing an
infeasible request to be represented explicitly. No numerical optimization package
or unconstrained optimizer is hidden behind the results.

The case_id, provenance sentence and entire conventions object are fixed labels.
They prevent an intervention from claiming a different matching rule, financing
rule, fee convention or objective while still executing the old equations. Change
the model and its checks explicitly if a different contract is required.

1. SNAPSHOT ORDER BOOK
Quote time <= arrival time < future mark time. Levels are positive-price/positive-
integer-size pairs, bids strictly descending and asks strictly ascending; best
bid < best ask. No hidden liquidity, cancellation, new quote or other routing occurs
during the atomic match. Each alternative order starts from the SAME snapshot and
account, so outputs do not consume depth for the next alternative.

Orders have unique IDs, side buy/sell, positive quantity, null (market) or positive
limit, and IOC/FOK instruction. Buy limits admit asks <= limit; sell limits admit
bids >= limit. Match best prices first. IOC cancels all residual. FOK cancels the
whole order unless eligible depth covers the entire target. No order is left resting.
Finite depth can leave a market IOC partly unfilled. Gross execution value and fees
are positive amounts; signed cash_change is negative for buys and positive proceeds
less fees for sells. No short selling: the sell target cannot exceed initial_shares.
Both signs require nonnegative final cash: cash - d*gross - fees >=0. Thus a buy
needs its full payment plus fees, and a sell whose fee exceeds proceeds requires
enough initial cash for the difference. A sell of1 at99.9 with fee100 needs0.1
initial cash exactly; zero initial cash is rejected. Fee >=0; cash >=0.

Spread definitions use aggressor sign d=+1 buy/-1 sell, fixed midpoint immediately
before arrival and the supplied future midpoint. The order's average fill price
gives an aggregate arrival-reference effective spread, not a per-child measure
against quotes changing during its internal match. ES=2d(P-m0), RS=2d(P-mh),
MC=2d(mh-m0); ES=RS+MC. All bps use10000/m0. Fees are separate. Future_mid is a
positive mark, not an executable unwind. No fills => null average and spread object.

Baseline: market300 fills300, gross30060, fees3, cash_change-30063, average100.2;
ES/RS/MC .4/.1/.3. Limit100.2 fills250, cancels50, gross25040, fees2.5. FOK fills0.

2. ONE-ARRIVAL INFORMATION MODEL
mid_value=m > value_half_range=delta >0; informed probability0<=theta<1. Value is
m+delta or m-delta with equal probability. Trader type is independent of value.
Informed trader buys in high and sells in low; uninformed trader buys/sells equally
and independently. Competitive risk-neutral dealer has zero conditional profit,
no other costs and a one-share commitment for one arrival. There is no unlimited
trading at a stale quote. Uninformed participation is supplied, not derived.

Bayes gives high|buy=(1+theta)/2, high|sell=(1-theta)/2; ask=m+delta*theta and
bid=m-delta*theta. Informed gain per trade is delta*(1-theta); dealer gain per
uninformed arrival is delta*theta. Type-weighted dealer profit is zero. Theta0 is
allowed and gives zero spread from this mechanism. Theta1 would make informed
participation indifferent and is excluded rather than settled silently.
Baseline: posterior.7/.3; quotes100.8/99.2; spread1.6; weighted profits-.48/+.48.

3. PASSIVE QUEUE AND DEADLINE
The passive limit is below immediate ask; immediate ask >= decision midpoint.
There are no cancellations/new orders ahead. The stated incoming sell volume
actually reaches this queue. Own fill=min(Q,max(0,volume-ahead)). States have unique
IDs, nonnegative probabilities summing exactly to1, positive deadline mid/ask with
ask>=mid, and nonnegative whole sell volume. Probability endpoints are permitted;
the complete stated contract must remain fundable even in a zero-weight row.

At the decision time choose either immediate completion, passive then compulsory
deadline completion, or passive then cancel residual. The last policy changes
the completion mandate. Supplied depth covers every required deadline purchase.
All policies pay the same nonnegative fee per executed share. Fees are paid with
fills. Cash must cover immediate execution AND both dated passive-completion cash
uses in every named state; no borrowing. Price/volume dependence is retained.

Paper wealth=cash+Q*(deadline_mid-decision_mid). Actual wealth is remaining cash
plus actual shares at the deadline midpoint. Report both completion and cancellation
wealth and paper-minus-actual shortfall, not a selected average over passive fills.
Baseline cash6000 suffices. Passive fills100/0; total completion payments4991/5061;
expected5033 versus immediate5011. Expected complete IS33 versus immediate11 and
passive-cancel IS132/5. Cancel policy's rising-state miss is worth50, not zero.

4. DATED WHOLE-TARGET SHORTFALL
Decision time < arrival time < terminal time; fills and external trades are ordered
within the arrival-terminal interval (including endpoints). Equal trade timestamps
are permitted in listed sequence. Positive prices/quantities; fees >=0. Fills may
be empty, but total filled cannot exceed original target. External trades are a
nonempty supplied market comparison sample, excluding own fills; the reference
sample is not used to determine target or decision prices.

Paper and actual start with identical inventory/cash; interest and distributions
are zero. Buys require enough starting cash for the paper target AND enough cash
at every actual fill including fees. Sells require owned shares covering the full
target and nonnegative cash after every fill, including unusually large fees.

Let f=sum fills and d=+1/-1. IS=d[sum q*(p-pD)+(Q-f)*(pT-pD)]+fees. Our components
are full-target delay dQ*(pA-pD), execution d sum q*(p-pA), opportunity d(Q-f)*(pT-pA)
and fees. Do not combine full-target delay with opportunity from pD. Target basis
points use10000/(Q*pD). Cash and terminal inventory supply an independent wealth
identity. External VWAP comparison covers executed quantity only. No fills => null
own average but valid opportunity IS. All fills => zero opportunity.
Baseline: filled350, missed150, gross7102.5, fees7, cash2890.5; paper/actual wealth
10250/10065.5; components100,32.5,45,7; IS184.5. External VWAP20.3, own average
2841/140; filled-only VWAP cost-2.5 before fees,4.5 after fees.

5. TWO-BLOCK IMPACT AND AUTHORIZED SIZE GRID
Monotone buy only. Choose first-block q1 before the symmetric shock epsilon=+s/-s,
each probability1/2. The second-block q2 is the committed remainder Q-q1. Initial
unaffected mid m>s>=0. Persistent coefficient k>=0; temporary eta1,eta2>0; all-in
one-way half-spread-plus-fee h>=0; lambda>=0 and gross benefit b>=0. Lambda has
inverse-CU units because objective J=E[C]+lambda*Var(C), NOT E[C]+lambda/2*Var(C).

Within-block persistent price is the quantity-path average. P1=m+k*q1/2+eta1*q1+h.
After block1 its persistent midpoint is m+k*q1; then epsilon arrives. Thus
P2=m+epsilon+k*q1+k*q2/2+eta2*q2+h. Temporary effects do not carry into block2.
Persistent means through this execution horizon, not a theorem about final value.
Fees are already in h. Do not add them again. Total C=q1*P1+q2*P2-Q*m, whose
persistent component is integral0..Q k*z dz=kQ^2/2, not kQ^2.

The lab enumerates each allowed integer schedule and both shock-state cash paths.
Funding domain is deliberately prefunded: cash must cover the worst total payment
for EVERY allowed schedule in the whole capacity grid, not merely the selected one.
This keeps the optimizer's only trading constraints the stated block capacities;
it does not purport to solve a further cash-constrained scheduling problem. Positive
execution prices ensure cumulative payment increases, so worst total prefunding
covers the first block too. Baseline cash1000 covers all schedules and Q0..14.

Fixed-Q output reports all candidates, continuous unrestricted and projected q1,
and selected integer schedule. Empty feasible interval returns feasible=false,
selected=null and no candidates. It never shrinks a required quantity silently.
Quantity0 and zero block capacities are valid. Ties select smaller q1; the capacity
grid also reports every optimal schedule. Equal total-quantity net scores select
smaller total Q. Baseline fixedQ12 selects5/7: mean14.7,var12.25,J19.6, actual costs
11.2/18.2 and cash611.2/618.2. Continuous unconstrained q1=6, feasible q1=5.

The independent grid allows Q0..u1+u2 ONLY under separately authorized size choice.
Gross benefit bQ is supplied before execution costs and excludes marking one's
own induced price movement as profit. Net score bQ-minJ(Q) includes a chosen risk
penalty, not a forecast cash profit or general expected-utility theorem. Baseline
b1.5 yields optimalQ6, largest nonnegative-scoreQ11 and physicalcap14. Benefit2
yields optimalQ8, largest nonnegative14 and physical14. These are conditional.

SUGGESTED INTERVENTIONS AND LIMITS
Set lambda0: fixedQ12 selects4/8. Lambda2/25 ties4/8 and5/7. Raise capacity1 to6:
fixedQ12 selects6/6 with J19.2, provided prefunding still covers the enlarged grid.
Set ahead100: expected passive completion cash5030.6 and IS30.6. Set theta0:
information component of spread becomes0. Request impactQ15: infeasible fixed
mandate, but the authorized0..14 grid still exists. Remove all shortfall fills:
average=null and original target opportunity remains. Change only b2 for exercise8.

Delayed retention completion at20.6 for the final150 shares plus fees needs total
cash10202.5; the original cash10000 input is rejected. A funded intervention may
increase initial_cash to10202.5 (stronger than funding at the final date, equivalent
for the zero-interest wealth comparison). IS then202.5; added cash is common to
both paper and actual portfolios and is not a trading gain.

Checks verify conditional arithmetic, strict domains, portability and unchanged
payloads. They do not authenticate market probabilities, queue priority, impact
estimates, future depth, investable alpha or venue compliance. See chapter source
scope for dated educational and research references. No research-paper tables or
proprietary data are distributed here.
