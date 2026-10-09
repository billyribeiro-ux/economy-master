ALDER–BEACON: RUNS, ASSET SALES AND FUNDED INTERVENTIONS
Volume 11 Chapter 11. Original synthetic teaching file, 9 October 2026.
Amounts: CU. Asset quantities: units. Dates: cutoff 1 and cutoff 2.

PURPOSE AND FILES
The lab closes a small funding/price mechanism and a two-player run game, then
follows a contracted creditor's dated payments. It compares separately funded
public line caps with a stipulated resolution stay and continuity bridge.
No actual institution, intervention, national legal power, empirical probability,
asset-pricing equilibrium or universally optimal policy is asserted.

v11-c11-inputs.json    Original positions, auction law, policies and payoff states.
v11-c11-analysis.py    Portable Python 3 standard-library implementation.
v11-c11-output.json   Complete saved output, including all three runner counts.
v11-c11-manifest.json Exact byte/hash bindings of input, model, output and README.
v11-c11-README.txt    This domain, timing and execution contract.

Copy the model and input together to any directory. No library installation,
network, credentials or other chapter is needed:
  python3 v11-c11-analysis.py
  python3 -O v11-c11-analysis.py
  python3 v11-c11-analysis.py --input v11-c11-inputs.json --output result.json

Default input and output are beside the script, regardless of the current working
directory. Without --output, the CLI quietly writes v11-c11-output.json there.
With --output, success quietly writes the selected file. Invalid data returns a
nonzero status and a short stderr error; existing output is preserved. Output may
not overwrite input or implementation through direct/resolved paths, symbolic
links or hard links, including the default output path. Successful CLI calls emit
no stdout or stderr; the written file contains the strict JSON result.

The public API is quiet run(data), which does not mutate its argument:
  import json, runpy
  model = runpy.run_path('v11-c11-analysis.py')
  with open('v11-c11-inputs.json', encoding='utf-8') as stream:
      data = json.load(stream)
  result = model['run'](data)

Import and run print/write nothing. Results contain ordinary dictionaries, lists,
strings, integers, booleans and null, and round-trip through strict JSON.
Validation does not rely on assert and remains active under -O. CLI JSON rejects
duplicate keys and nonfinite constants. API callers must reject duplicate keys
when parsing untrusted text; a dictionary cannot preserve duplicate-key evidence.

ECONOMIC TIMING AND RIGHTS
One currency, fully usable cash, no fees, taxes, recovery expense or interest on
stored cash. Each asset produces only the declared cutoff-2 unit payoff. The
benchmark game assumes its named payoff is known; stress states change that
payoff on the SAME already executed cutoff-1 history. No probability weights are
assigned. A known changed payoff requires a new game calculation and a defense
of whether the auction law should also change.

Alder opens cash + N*p0 = retail + 2*funder_principal + network + equity.
The two equal large funders simultaneously choose R (principal at cutoff 1) or
W (principal times wait_multiplier at cutoff 2). They maximize expected total
cutoff-2 consumption with linear utility, storing early money one-for-one. Retail
is an exogenous early obligation. The lab does not treat the players as nonatomic.

After any public drawing and asset sale, cutoff-1 payment order is retail,
requesting funders pro rata, then Beacon. Opening cash must already cover retail.
Unpaid runner and network amounts remain claims, never erased. At cutoff 2 the
public loan is senior on all retained estate; waiting promises and unpaid private
claims share the residual estate pro rata, then shareholders receive any surplus.
Waiting interest is recognized as a contractual expense at this later horizon;
the reported principal marked equity at cutoff 1 excludes that waiting premium.

Beacon opens cash + network claim = customer obligation + equity. It pays its
customer at cutoff 1 only from cash and ACTUAL receipts, carries any unpaid
obligation, and applies later receipts to it. A later payment does not reverse
the earlier missed cutoff. The ordinary line scenarios do not give Beacon a
second hidden facility. There is no automatic bankruptcy acceleration or new
funding following a miss; those mechanisms would need extra rules.

Uniform auction price: p(s)=p0-impact*s. Every sold unit trades at this price, so
proceeds equal s*p(s), not an integral of the inverse-demand curve. Buyers retain
the purchased assets. Their terminal gain is unit_payoff*s - proceeds. The
inverse-demand curve is stipulated absorption capacity, not a derived equilibrium
of optimally investing buyers. Its shape cannot be assumed invariant in real
fundamental shocks without additional evidence.
Buyers start with a separate cash endowment p0*N, sufficient for every allowed
auction quantity. Unsold cash remains theirs. Their terminal wealth is that cash
endowment minus sale proceeds plus the payoff of purchased units. This cash is
not simultaneously included in Alder's opening cash or the public funding budget.

PUBLIC LIQUIDITY ALTERNATIVES
Each line cap is a separate policy backed by the declared prepositioned taxpayer
cash. Policies are never executed together. Each actual drawing is
  min(max(retail + runners*funder_principal + network - cash, 0),
      line_cap, advance_fraction*p0*N).
The appraisal p0 is frozen for this window. A loan locks loan/(advance_fraction*p0)
asset units; those units may not also be sold. The rest are free auction supply.
The public loan has zero interest and senior estate recourse, not recovery limited
to the minimum initially earmarked collateral. There is no additional margin call.
These are explicit hypothetical rights, not statements of lender-of-last-resort
law. No current rule or public institution is inferred from the fiction.

The remaining cash target determines the smallest sufficient sale. Revenue is
continuous and strictly increasing on [0,free_inventory] in the allowed domain
2*impact*N <= p0. If target exceeds the maximum, all free units are sold and the
waterfall uses only resulting cash. Equality is a fully sold, exactly funded
boundary. Zero target needs no sale; zero impact uses linear receipts. The domain
excludes nonmonotone curves, where full liquidation need not maximize funding.

The public balance ends with initial public_cash - loan + repayment. Its loss is
loan - repayment, not the full unused commitment or even necessarily the amount
drawn. This is a taxpayer-cash vehicle, not an undocumented central-bank money
creation operation. Support's funding, risk and incentive effects are separate.

RESOLUTION ALTERNATIVE
Assume actual authority and implementation before cutoff 1. Alder pays retail
from cash, makes no sale and no public borrowing, and stays funder/network claims
until cutoff 2. Those restructured claims are principal only (2*f+network), pari
passu; the waiting premium is explicitly cancelled. All retained assets and cash
form the estate. This intentionally replaces the original game and rights.

Beacon gets no cutoff-1 network receipt. A separate public bridge draws
min(max(customer_due - Beacon cash,0), resolution_bridge_cap) from the same funded
vehicle, under an ALTERNATIVE plan. Its claim is senior at cutoff 2 and backed by
Beacon's estate/network recovery, with no second pledge. Customer cash comes from
the actual bridge, not from the stay. If bridge capacity is insufficient, the
customer payment still misses its cutoff. A future network recovery can repay
the bridge, complete late customer payment and only then reach Beacon shareholders.

INPUT DOMAIN
Every object has exactly the listed fields. No optional/unknown keys. All
financial quantities are unsigned plain decimal strings, not JSON numbers,
booleans, fractions or exponential notation. At most six integer digits and six
fractional digits; no signs, spaces, leading zeroes other than zero, NaN or Infinity.
Examples accepted by grammar: "20", "0.005", "0.8". Ranges and identities below
further restrict them. Identifiers are one ASCII letter followed by at most 39
ASCII letters/digits/underscores/hyphens. CLI input is at most 1,000,000 bytes.

Top-level exact fields:
  schema provenance bank beacon market policy terminal_states
schema is v11-c11-alder-beacon-1; provenance must match the supplied synthetic
sentence exactly. These labels do not turn modified data into observed evidence.

bank exact fields and ranges:
  cash                    [0,10000]
  asset_units             [1,1000]
  retail_due              [0,1000], no greater than usable cash
  funder_principal        [0.01,1000], same for exactly two funders
  wait_multiplier         [1,1.5]
  network_due             [0,1000]
  opening_equity          [0,20000]
The opening principal balance sheet must reconcile exactly. Thus the supported
case starts with nonnegative equity and funded retail; it does not silently
borrow at opening or accept an independently inconsistent equity label.

beacon exact fields:
  cash [0,10000], customer_due [0,10000], opening_equity [0,20000].
Cash + Alder's network principal must exactly equal customer_due + equity.

market exact fields:
  intercept [0.01,10], impact [0,1], benchmark_terminal_value [0,10].
Require 2*impact*asset_units <= intercept. The benchmark payoff is the one used
to evaluate the game, whether or not a terminal stress row repeats it. It is not
automatically a probability-weighted expectation of the declared stress states.

policy exact fields:
  public_cash             [0,10000]
  advance_fraction        [0.01,1]
  line_caps               list of one to four distinct decimal amounts in
                          [0,public_cash], in the desired reporting order
  resolution_bridge_cap   [0,public_cash]
Numerically equal cap strings (for example "20" and "20.0") are duplicates.

terminal_states is a list of one to four objects {label,unit_payoff}. Labels are
unique identifiers; payoffs lie in [0,10]. They are conditional stress values,
not observed outcomes, fitted frequencies or risk-neutral state prices.

NUMERICAL AND GAME OUTPUT
Financial regime comparisons use exact Fraction arithmetic on validated inputs.
Square roots and downstream arithmetic use Decimal precision 80; output rounds
to 40 places after the decimal point and strips trailing zeroes. Thus serialized
arithmetic can have a tiny rounding residual; displayed zero is not proof of an
exact symbolic identity. Internal sale and loss identities reject residuals above
1e-60. Independent rational bisection tests the original roots and cash flows.

For each alternative, line_alternatives contains all three profiles, their
cutoff1 amounts and each terminal state's full estate/waterfall/Beacon report.
null runner/waiter payoff means that this type is absent in that profile. Marked
assets/equity leverage is withheld when marked equity is <=1e-24; a tiny positive
number inside that numerical guard is not treated as a reliable ratio. Negative
equity is not reported as a meaningful positive leverage ratio.

The benchmark_game compares a unilateral run with waiting against the other
player's W and R. A 1e-24 band prevents tiny numeric differences from being
declared strict incentives. strict_pure_equilibria are separated from
weak_pure_candidates_with_numeric_band. near_indifference_unresolved flags a
payoff difference within the band; a weak candidate is NOT a certificate of
exact indifference. Opposite resolved signs yield the interior symmetric mixed
probability; otherwise that field is null, not a claim that degenerate games
have no mixed equilibria. A fully indifferent continuum is not enumerated.
The baseline's WW/RR/mixed statements have exact analytical proofs in the chapter.

No equilibrium is selected as the forecast. Policies can change the game; the
same requested-payment pattern can still be evaluated as an explicitly labeled
off-equilibrium contingency. Neither an equilibrium mixing probability nor a
list of stress states estimates the likelihood of a financial crisis.

BASELINE ANCHORS AND TRANSFERS
No line: targets 18,49,80 against maximum auction receipts 50. Sales are
20, 100-10*sqrt(2), 100; prices .9, .5+sqrt(2)/20, .5. Waiting payoff against W is
34.1; running against W is 31; waiting against R is 10*sqrt(2); running against R
is 26. Strict pure equilibria WW and RR coexist. Symmetric mixed run probability
is 3.1/(29.1-10*sqrt(2)) = approximately .20724883726838785, without selection.

At q=.9, prepayment equity 10 and assets 110 imply leverage 11; retirement of 38
principal leaves marked assets 72, debt 62, equity 10 and leverage 7.2. Fundamental
retained value 80 minus remaining principal 62 gives 18 before waiting interest;
the 6.2 premium leaves terminal shareholder value 11.8. Zero marked equity at
q=.8 corresponds to sale 40 and receipts 32 in this calibration.

Cap 20/RR: loan 20, pledge 25, free sale 75, price 5/8, proceeds 375/8. Retail 18 and
funders 62 are paid before Beacon's 55/8; Beacon misses 25/8 at cutoff1. Terminal
payoff 25 at v1 repays public 20 and delivers 5 more to Beacon. Network total 95/8,
Beacon terminal equity 15/8, network impairment 65/8. Buyer gain 225/8 equals Alder
equity loss 20 plus the network impairment. Do not add Beacon's equity loss again.
Under benchmark incentives cap 20 has W strictly dominant, so RR here is a stress
contingency, not a predicted Nash outcome.

Cap 80 draws18/49/80 without sales. Both cap 20 and cap 80 have benchmark WW with
actual draw 18. Cap 80 additionally meets all initial cutoff1 payments in all three
action profiles, but is not proved minimal or welfare optimal. Fixed RR with v.6
repays public 60 of 80, leaves public loss 20/cash 60 and zero Alder shareholder value.

Resolution: retail 18 now; cash 2 and 100 assets retained. Claims62+20=82 at cutoff2.
At v1 estate 102 pays all principal and equity 20. At v.6 estate 62 gives fraction
31/41; funders 1922/41, Beacon 620/41, private principal loss 20. Bridge 10 funds Beacon's
customer on time, is repaid in full, and leaves Beacon equity 210/41. At v.1 estate 12
gives funders 372/41, Beacon 120/41 and bridge loss 290/41; Beacon equity is zero.
Cancelled WW premium is 6.2. A zero bridge cap at v1 leaves a cutoff1 customer miss
of 10 even though the eventual recovery is complete.

Other informative changes: flat auction impact (waiting dominates without a
line); wait_multiplier 1 (near-indifference is reported, not falsely called a
strict result); funded extra cash/equity; Beacon's own early cash; lower advance
fraction; zero terminal assets; a zero public budget; a known downside benchmark.
Each change must retain all opening identities and actual policy funding limits.

CONSERVATION AND INTERPRETATION
For Alder: opening equity minus final shareholder payment plus final private and
public claim losses equals the fundamental asset decline plus promised waiting
interest plus buyer gain. It follows by adding both dated recipient budgets.
For Beacon: network asset loss equals lost opening equity plus remaining customer
loss plus public bridge loss. These describe allocations at different layers,
not additive independent system losses. Cheap sales are transfers to buyers in
this model; output destruction and general welfare costs are not specified.
The consolidated output adds external recipients once: retail, funders, both
shareholders, Beacon customers, public terminal cash and buyer terminal wealth.
It equals initial Alder/Beacon/public/buyer cash plus the total asset payoff v*N.
The internal network transfer cancels. All terminal states and alternatives check
this resource identity; unpaid nominal claims are not added as realized wealth.

REVIEW AND SOURCE SCOPE
scripts/check_v11_c11.py is the separate author checker in the full source layout.
It uses exact rational funding branches and 160-step root brackets, independent
recipient ledgers and four-profile deviations; it does not call model helpers.
It checks all tagged printed exact/rounded results, meaningful financial transfers,
strict API/CLI/domain cases and output alias protection. The author record binds
the eight nonself payloads; the manifest binds the four portable payloads. These
bind bytes and reported evidence, not correctness under every unmodeled assumption.

Reused Diamond–Dybvig 1983 is scoped to the already inspected run/liquidity context;
no optimal contract, general suspension or government-insurance theorem is imported.
The actual official Bernanke 2 September 2010 testimony was reopened for the dated
trigger/funding/leverage/forced-sale and crisis-management passages. It is a
participant retrospective, not causal identification or current legal authority.
All parameters, contracts, interventions and proofs here are original.

Separate peer review, coordinator dependency acceptance and whole-edition rendered
UI checks remain distinct. A successful computation does not authorize a real
payment, confer resolution powers or establish empirical policy effectiveness.
