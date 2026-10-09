V13 PROJECT: RESTORATION AFTER A NOISY WARNING
Original synthetic theory benchmark — 9 October 2026

PURPOSE AND FIVE-FILE RUNTIME
Keep v13-assessment-inputs.json, v13-assessment-analysis.py,
v13-assessment-output.json, v13-assessment-manifest.json and this README together.
Python 3 and its standard library suffice. No packages, network, source PDFs,
manuscript or editorial checker are required to execute the reader model.

From their directory:
  python3 v13-assessment-analysis.py
This silently writes the neighbouring v13-assessment-output.json. To preserve
the supplied benchmark, use an explicit new destination, for example:
  python3 v13-assessment-analysis.py --output my-result.json
From another directory, use an absolute or relative path to the implementation:
  python3 /path/to/v13-assessment-analysis.py --input /path/to/inputs.json --output /path/to/result.json
The same commands work with python3 -O. Parent output directories must exist.
Normal success has no stdout/stderr. Rejections produce a nonzero status and a
short stderr diagnostic. Use a disposable copy for invalid-output experiments.

API
Load the script with runpy.run_path or importlib without executing its main
block, then call run(data). It is quiet, deterministic, does not mutate data,
and performs no writes. It returns strict JSON-safe dictionaries/lists with
exact rational strings. strict_loads(text) rejects duplicate keys, fractional
JSON numbers, NaN/Infinity and overflow notation before economic validation.

EXACT INPUT FORMAT AND DOMAIN
schema_version must be integer 1, not bool. Every declared object has exact keys;
unknown or missing fields are rejected. Exact scalars are Python/JSON integers
or strings such as "4", "-1", "4/5". Strings have an optional leading minus and
integer numerator/positive integer denominator, with no whitespace, plus sign,
decimal or scientific notation. Rational equivalents are compared exactly.
Booleans and floats are not economic numbers in this implementation.

economy:
  discount: strictly between zero and one;
  benefit > collaboration_effort_cost > 0; review_effort_cost > 0;
  initial_state: exactly "G", the declared design objective;
  good_report_in_G: complete keys WW, WN, NW, NN and probabilities satisfying
    0 < NN <= WN = NW < WW < 1.
restoration_grid: a nonempty finite list of distinct exact rates in [0,1];
  input order may differ, but output is sorted by numerical rate.
garbling_values: a nonempty finite list of distinct rates in [0,1], also sorted.
active_repair.good_report_in_R: complete WW/WN/NW/NN probabilities in [0,1],
  with WN=NW. These need not satisfy monotonicity: failed incentives are valid
  economic outcomes, not malformed data.
counterfactual_one_worker_good_probability: any probability in [0,1], replacing
  both WN and NW in R while preserving WW and NN.
paper_case: exactly four vertices and the labeled undirected four-cycle
  {1,2},{2,3},{3,4},{1,4}, with no self-links or duplicate edges. Reversed edge
  endpoints are equivalent. Regular interaction must lie in (0,1/2), singular
  interaction must equal 1/2, and last_target_increase lies in (0,1].
Other graph/model families are deliberately unsupported, not approximated.

ECONOMIC TIMING AND REAL FLOWS
There are two indefinitely lived agents and public states G/R. At each date the
state is observed, simultaneous hidden actions W=1/N=0 are chosen, current real
payoffs accrue, and an authenticated public report determines the next state.
Good means G, bad means R. Conditional on current state and actions, report
draws have the supplied law and are independent over time. No persistent hidden
state, private type, manipulable report or wealth state is present.

In G, own payoff is benefit*other_action - collaboration_cost*own_action.
In R, own payoff is -review_cost*own_action. Fresh nonstorable capacity funds
the physical effort each period. Common cardinal utility-equivalent units and
interpersonal addition are assumptions. Costs are real consumed effort, not
payments credited to another account. There are no wages, fines, grants, loans
or cash balances in this model. It makes no cash-solvency claim.

BASELINE AND EXTENSIONS
Baseline recommendation is W in G and N in R. The R good-report probability is
r under every action pair. The design objective starts in G, but every R
continuation must also be incentive compatible. The fixed reference r=1/2 is
reported separately for the repair comparison even if a modified grid omits it.

Garbling affects G only: with probability eta replace the original report by
an independent fair coin. Each good probability p becomes (1-eta)*p+eta/2.
Active repair changes R technology to its four supplied probabilities and
recommends W in both states. The further counterfactual changes only the
one-worker R report rate. Off-path laws can change incentives while leaving
the entire compliant law unchanged.

VALUES, CERTIFICATION AND DESIGN BOUNDARIES
V is the unnormalized expected discounted sum. U=(1-discount)*V has stage-payoff
units. The model solves the actual two-by-two linear value equations, calculates
every state/action Bellman residual, and records profitable one-action-then-
return deviations. Nonnegative margins certify weak IC; zero margins are kept.
Strict alternative margins are separately labeled. A valid failed protocol
returns status "not_certified" with a witness and hypothetical-compliance V/U.
Those hypothetical values must not be reported as implemented equilibrium
welfare. The four own stationary policies use their own transition rows, not
the prescribed transition matrix. Their table is numerical evidence only.

The complete all-history proof in the project conditions at any public/private
history, averages pure-action bounds for private randomization, iterates the
Bellman inequality and removes the bounded discounted tail. A finite table of
stationary policies cannot replace that argument. It addresses unilateral
deviations, not coalitions, renegotiation or report manipulation.

The generalized raw restoration ceiling is
  alpha + (alpha-beta)*(benefit-cost)/cost - 1/discount,
using the actual garbled alpha/beta when relevant. Intersect it with [0,1].
A negative ceiling gives an empty cooperative class; zero gives a weak
singleton with no strictly certified member. For a ceiling in (0,1], the weak
optimum is attained and the corresponding strict supremum is unattained.
A ceiling above one permits the entire [0,1] class and a strict attained
optimum at one. The objective is strictly increasing on the supported domain.
The always-N profile is also an equilibrium, so an empty cooperative class is
not failure of equilibrium existence. No best-grid result claims an optimal
institution over arbitrary protocols or selects among repeated-game equilibria.

Stationary G shares and discounted G occupancies are both supplied. Initial-G
discounted welfare uses the latter. Active repair deducts review effort even
when a stationary or conditional value comparison is positive.

PAPER BENCHMARK AND SINGULARITY
The fixed four-cycle implements the quadratic best reply
  x_i = max(0, target_i - gamma*sum_{j linked to i} x_j).
All sixteen strict positive supports are inspected with exact row reduction.
Each row records unique, inconsistent or affine systems; unique candidates
must pass strict active positivity and all inactive inequalities. At gamma=1/2
and unit targets the complete equilibrium family is
  (a,1-a,a,1-a), 0<=a<=1.
The two finite rows are its endpoints, not a complete finite equilibrium list.
The supplied analytic family is supported by the complete opposite-reply proof;
it is not inferred from sampled parameter values. The potential is constant
on that family while aggregate welfare varies. Heterogeneous target 1+epsilon
at vertex 4 is a changed primitive proved separately and has a unique outcome.

SOURCE AND PROVENANCE BOUNDARY
All economic numbers are original synthetic teaching inputs. No empirical
collaborator data or estimated interaction coefficient is included.
Prior method context: Manea Noncooperative Game Theory (2017 cover), through
accepted C07; Stole Lectures on the Theory of Contracts (1999), through C09.
The current author does not claim fresh reading of those source bodies here.

Required primary dossier: Bramoulle, Kranton and D'Amours, "Strategic Interaction
and Networks", American Economic Review 104(3), 898-930, March 2014:
https://sites.duke.edu/rachelkranton/files/2016/09/strategic-interaction-and-networks-aer.pdf
This project actually inspected retained physical PDF pages 4-7 and 24-25
(printed 901-904 and 921-922) and the physical-6/printed-903 equation image.
Proposition 1, its proof and generic finiteness qualification have bounded scope.
The 2016 upload path is not the publication date; no whole-paper verification is
claimed. The source and original four-cycle construction are distinct.

The five-file manifest binds the other four reader payloads by bytes/SHA256.
It deliberately has no self-hash. Hash equality establishes identity, not
correctness or independence. Editorial author/peer records and provenance
artifacts are outside the reader runtime.

PROTECTED OUTPUT AND REPRODUCTION CHECKS
Before opening output, the CLI checks resolved paths and samefile identities
against the supplied input, neighbouring default input, implementation, README
and manifest. Existing symlink and hardlink aliases are rejected in normal and
optimized modes. The default output itself may be replaced. Invalid input is
fully checked before output is written. Use disposable isolated copies to test
these behaviors; preserve and compare all protected bytes after rejection.

LIMITATIONS AND LEARNER WORK
The supplied implementation and instructor proof are completed author work.
Your independent implementation, source reading, proof audit, referee report,
research originality and external professional evaluation are not completed by
downloading them. Synthetic exact arithmetic is not empirical validation.
No human academic certification or complete mastery claim is made.
