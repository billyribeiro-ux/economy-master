V15 FINITE POLICY LABORATORY — original synthetic teaching capsule
Edition 2026-10-09. No actual population, calibrated effect or policy recommendation.

Keep these five basenames together:
v15-assessment-inputs.json
v15-assessment-analysis.py
v15-assessment-output.json
v15-assessment-manifest.json
v15-assessment-README.txt

Requires only Python 3 standard library. From any directory:
python3 /path/to/v15-assessment-analysis.py
The successful CLI is silent and writes its neighboring output JSON.
Explicit paths: python3 v15-assessment-analysis.py INPUT.json OUTPUT.json
Existing output is replaced. Output aliases of input, code, README or manifest
(including resolved paths, symlinks and existing hardlinks) are rejected before
writing. This protects these payloads, not every unrelated file on a computer.

API: load the module, load input JSON, call run(data). The returned object is
strict JSON; no writes, printing or input mutation. Rational quantities use
integers or fraction strings, avoiding hidden float tie tolerances. If comparing
an independent floating implementation, use at most 1e-9 residual tolerance;
compare optimizer/tie sets against exact arithmetic.

MODEL: four atomless unit-mass groups in listed priority. Extra production is
real income; travel/public capacity/admin/abatement and environmental damage
consume resources. Fees, subsidies, equal upfront levies and final refunds are
transfers. Households take aggregate damage/refunds fixed when applying. At
zero private gain they apply; rationing follows priority. Nonparticipants can
lose to taxes and pollution. There is no market-clearing housing-rent model.
Capacity is chosen before effects/damage are known; no borrowing against fees.
All policy comparisons use the common uniformly feasible menu.

INPUTS: all supplied values original/synthetic. Four population means fit
causal effect plus selection, not causal effect separately. Selection bound is
a sensitivity restriction. Program transport/offsets/technology are structural
assumptions. Finite uncertainty support, forecast probabilities and social
weights are decision assumptions. Heldout prediction does not identify effects.

OUTPUT: 37 candidates, 31 uniformly feasible policies, six state accounts each;
reserve diagnostics for six unfunded policies; full state frontiers, expected
weighted/resource optima, minimax regret and exact forecast-support intervals.
Expected weighted: K1F0S1A1, value3/16, expected resources-5/4.
Expected resources: K0F0S0A0, value0.
Deterministic minimax regret: K2F0S1A1, value3, expected weighted-1/8.
Forecast effect-endpoint mixture switches at13/64 and21/64.
Policy IDs encode capacity K, fee F, subsidy S and abatement A. Report all ties
before choosing the lexicographically first ID. Robustness covers the supplied
six states and deterministic menu; lotteries or continuous support need a new
optimization problem. Economically valid infeasible policies return diagnostics;
malformed primitive domains raise errors. Changing primitives changes the model,
so the frozen supplied output and manifest no longer validate that variant.

Manifest binds inputs/code/output/README by bytes and SHA256, excludes itself.
It verifies payload consistency, not empirical validity or human expertise.
Full prompts, solutions, analytic proofs and five-domain100-point rubric are in
the V15 assessment project section. Suggested10–14hours,85total/15perdomain and
transfer/teachback rules are uncalibrated study design. Actual learning requires
independent work and human feedback. No paid service, download or remote data
is needed to run the capsule. Python bytecode caches are ordinary interpreter
behavior; use -B when requiring no extra files on import.
