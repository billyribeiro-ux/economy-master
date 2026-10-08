v09-c07 — Information, pricing, selection, beliefs and funding
============================================================

These are original synthetic teaching cases. None of the numbers is an observed
return, a historical anomaly replication, an estimated belief, or October 2026
market information. The twenty sign sequences are authored finite data, not a
claim of random sampling. The cited research supplies methodological context,
not any of the examples' numerical inputs.

Offline use
-----------
Keep these four files together:
  v09-c07-inputs.json
  v09-c07-analysis.py
  v09-c07-output.json
  v09-c07-README.txt
The separate v09-c07-manifest.json records their byte sizes and SHA256 hashes.
Python 3 with its standard library is sufficient. From any working directory:
  python3 /path/to/v09-c07-analysis.py
prints the complete reference calculation as strict JSON. To save a comparison:
  python3 /path/to/v09-c07-analysis.py --output /path/to/recomputed.json
Use --input /path/to/changed-inputs.json for a copy with documented changes.

Importing the module is quiet. run(data) returns the complete JSON-compatible
dictionary without printing or writing. run() reads the adjacent baseline input
and is also quiet. The CLI writes a file only when --output is supplied.

Conventions and timing
----------------------
All payoffs and profits use CU; returns are simple total decimal returns. Safe
gross return is one, so cash has zero interest between the stated dates. Taxes
are excluded. Costs and admissible rights are CASE SPECIFIC: do not transfer the
frictionless pricing/behavior rights to the collateral-constrained pair.

All exact numbers use Fraction internally and are preserved as JSON strings.
Counts/minutes are integers; boolean flags and null have their usual JSON types.
Only independent_family_tail_approx is a floating approximation; the exact same
probability is also preserved. The focused checker allows 1e-12 absolute and
relative error on that explicitly named approximation, using exact rational
identities elsewhere. Strict JSON rejects NaN and infinity.

Cases and what the calculation establishes
------------------------------------------
1. Conditional pricing. At each public date-0 regime the claim pays 120 or 80 at
date 1, with physical probabilities 1/2,1/2. State prices are (.45,.55) or
(.35,.65), summing to one under the zero safe rate. Prices are 98 and 94;
physical expected returns 1/49 and 3/47. SDF equals q/pi, not q itself. The
calculation verifies E[m]=1, E[mG]=1, and mean return=-Cov(m,R) separately in
each regime. Positive state prices establish compatibility with frictionless
no-arbitrage, not a proof that an observed market is informationally efficient.

2. Search. All twenty candidate strategies have twelve training and eight
later gross signs. Each completed trade wins or loses exactly 1 CU; its cost
is 0.1 CU. The rule with the most TRAINING wins is chosen, breaking ties by the
identifier. Holdout signs never enter selection. A01 wins ten training trades,
with gross 8 and net 6.8; its frozen holdout has four wins, gross 0 and net −0.8.

The one-sided sign test assumes a rule fixed in advance and independent fair
signs. Its tail is 79/4096. The family probability 1-(4017/4096)^20 additionally
assumes independent candidate tests. It is NOT a dependence-robust equality.
The min(1,20p) Bonferroni bound does not require test independence but still
requires valid individual tests and an honestly disclosed family. This is a
probability experiment, not an estimate of skill, alpha or real profitability.

3. Event execution. The old midquote 100 occurs at 08:00, information at 08:30,
entry at 09:00 and exit at 16:00 on one fictional day. All four times are minutes
after midnight. Entry mid 108 is not the ask 109; exit mid 111 is not the bid 110.
Entry and exit fees are 0.25 each and information processing costs 1 at entry.
Total entry cash 110.25, final cash 109.75 and profit −0.5 produce return −2/441.
The old-to-new midprice 11% cannot be executed using the later signal. This is a
realized single trade, not an expected-return or pricing-model assessment.

4. Beliefs. The prior high-payoff probability is 1/2; payoff is 140 or 60. Actual
good-signal likelihoods (0.75, 0.25) imply true posterior 0.75; investor N uses wrong
likelihoods (0.9, 0.1) and posterior 0.9. Investors explicitly choose their subjective
mean terminal CU wealth minus(a/2)*subjective variance, with a=1/100 and 1/288.
This stipulated bounded-payoff criterion is not described as normal utility.
Each starts with half the total supply and 500 CU cash. Short and fractional
positions and equal-rate cash trading are allowed, with no fees/interim calls.

The subjective means 120/132 and variances 1200/576 imply curvatures 12/2. Supply 2
clears at price 888/7 and holdings (−4/7, 18/7). Budgets, holdings and statewise
terminal resources reconcile. The counterfactual corrects N's beliefs only:
both means become 120 and variances 1200, but the risk-aversion coefficients stay
different. Counterfactual price 11040/97 is a defined model comparison, not an
observable unique fundamental value. Positive supporting state prices coexist
with the erroneous beliefs. The one-share short can lose 92/7 despite its
positive physical expected gain 48/7; no sure arbitrage is being claimed.

5. Information option. The investor can buy zero or one ticket at a fixed 3-CU
quote. The payoff is 0 or 6 with equal physical probabilities. A perfect signal
costs 1 before the decision. The limited quote contract is assumed to remain
available after the private signal; sufficient cash is available and shorts
are excluded. Gross information value 1.5 minus fee 1 leaves 0.5. If public signal
revelation reprices the quote to the known payoff first, the information's
incremental payoff is minus the fee. This fixed opportunity is not an equilibrium model.

6. Funding. One indivisible pair buys a claim at 95 and shorts an otherwise
identical dated claim at 105. Their date-2 payments match in both common payoff
states 90/110, so no probability of those states is needed for pair cancellation.
The two date-1 quote paths have physical probabilities 3/4 and 1/4. Their common
terminal distribution is not being inferred or priced by those probabilities.

Short proceeds 105 are locked. The trader separately funds the long 95 and an
additional 20% of the CURRENT short value in cash. There is no other credit,
capital injection, borrowing against the long, partial pair liquidation, or
short recall except the contractual full liquidation on failure to post margin.
At entry collateral 126 consists of locked proceeds 105 plus own cash 21. With
wealth 125, free cash is 9 and entry own-capital need 116.

At date 1 convergence closes both legs at 100. In divergence the long mark is 80
and the short mark 120; collateral required 144 means a further 18 cash call.
Nine free CU cannot meet it even though marked equity is 95. Both legs close,
releasing 126+9+80-120=95 before fees. THE TOTAL 2-CU PAIR FEE IS PAYABLE ONLY
AFTER CLOSING CASH RELEASE. There are no entry/interim fees. Thus final wealth
is 133 on convergence and 93 on forced closing, expected gain −2.

Initial wealth 134 exactly supplies 116+18, allowing survival. Zero free cash
then remains, but terminal long/short payments cancel and 144 collateral is
released; after the 2 fee final wealth 142 is an 8 gain. Quotes beyond the named
stress, different collateral eligibility, early fees or recall invalidate that
threshold. This quote/contract case intentionally need not satisfy the
unrestricted law of one price; capital-constrained opportunities are analyzed.

Edits supported by the small fixture
------------------------------------
Change only a COPY. Rational strings or integer numbers are accepted; binary
floats and booleans are rejected as economic numeric inputs. The case identity,
convention dictionary and named policies are checked. Relabeling returns as
logs, fee timing as entry, or the long as pledgeable does not activate a new
model. Implementing those changes requires a different calculation.

Pricing: two positive high/low payoffs; positive physical probabilities sum to 1;
both named q vectors are positive and sum to 1. Changing probabilities or q is
allowed within these domains, with prices/moments recomputed.
Search: keep all twenty ordered IDs, twelve training and eight holdout signs
per rule, each '+' or '-'. Costs are nonnegative. Training changes may change
selection; changing holdout signs alone cannot. Do not call such an edited
holdout untouched empirical evidence.
Event: same-day integer times must satisfy prior<release<=entry<exit; quotes
are positive, ask>=entry mid, exit bid<=exit mid, fees nonnegative and net sale
proceeds positive. The baseline is an invented quoted opportunity, not a fill
guarantee for real markets.
Beliefs: prior and signal likelihoods strictly inside (0,1), ordered positive
payoffs, positive risk aversions/supply, nonnegative initial cash. Prices in
both belief cases must remain strictly between payoffs. This restricted domain
allows the reported positive state-price demonstration; an outside price is
rejected rather than quietly contradicting it.
Information: keep the one-unit fixed-quote contract; positive probabilities
sum to 1, nonnegative payoffs, price strictly between them and nonnegative fee.
Funding: nonnegative integer pair count and wealth; positive prices/payoffs;
entry dear>cheap; margin in [0,1]; divergence probability in [0,1]; nonnegative
closing fee; divergence dear quote above entry dear and above divergence cheap;
convergence quote no higher than entry dear. Entering too many pairs produces
status=entry_infeasible, not a fictitious financed trade. Within entered cases,
insolvency or fees exceeding released cash are outside scope and rejected.

Evidence limits
----------------
Exact cash/probability calculations and source-scope checks do not establish
real informational efficiency, rationality, empirical anomaly persistence or
investment suitability. No prices, signal likelihoods, research costs, margin
rights or security borrow have been authenticated for a real account. No tax,
market-impact, general strategic price response or dynamic funding model is
implemented. The independent-sign test is deliberately small and does not
replace dependence-aware empirical econometrics. Author/automated review is
not independent human certification or browser/print QA.
