V17 TEACHING REHEARSAL: SHARED SERVICE, EFFICIENCY AND PARTICIPATION

All household parameters, learner responses, scoring annotations, supervision
and observation records are authored synthetic calibration. No real teaching,
consent, human observation, learner improvement or policy approval is claimed.
The full seven tasks and complete instructor artifacts are in the volume's
assessment project. Actual teaching and human evaluation are separate work.

FIVE-FILE CAPSULE
Keep this README with v17-assessment-inputs.json, v17-assessment-analysis.py,
v17-assessment-output.json and v17-assessment-manifest.json. Only a Python3
standard-library interpreter is needed: no packages, network or credentials.
The manifest binds the other four files by byte count and SHA-256; it has no
self hash and does not authenticate scientific claims, consent or authorship.

RUN
  python3 -B v17-assessment-analysis.py
quietly writes the neighboring v17-assessment-output.json, using neighboring
inputs irrespective of working directory. Explicit paths are supported:
  python3 -B v17-assessment-analysis.py INPUT.json OUTPUT.json
Optimized Python (-O) preserves all domain and output-protection checks.
Success produces no stdout/stderr. Invalid inputs and protected output aliases
raise errors before writes. The API run(data) returns strict JSON-compatible
data, prints/writes nothing and does not mutate its argument. Exact fractions
are serialized as integers or rational strings such as "3/2"; undefined means
or shares are null, never NaN, infinity or invented zero understanding.

OUTPUT PROTECTION
The CLI rejects direct, resolved, symlink and existing-hardlink output aliases
of the selected input, code, README and manifest. Canonical protected names
beside both code and input are checked. Test aliases only in disposable copies;
verify every protected byte and file/directory membership after rejection.
The ordinary output is intentionally writable. The guard is not a privileged
concurrency/race-security service; it prevents these ordinary accidental
self-overwrites before analysis writes.

MODEL CONTRACT
Two households receive the same total g, with benefit ai*g-g*g/2 and real
provision cost c*g. Quantities are service units/period; benefits, costs and
payments are currency/period. Coefficients normalize the curvature in these
units. Benefits can decline at sufficiently high g: this is an explicit toy
preference, not an estimated public demand curve. Values are nonnegative,
cost strictly positive, and the procurement budget and proposed transfer are
nonnegative. Preferences are quasilinear; other parties/costs are omitted.

Private contribution qi pays c*qi and best responds with max(0,ai-c-qj).
Unequal values yield a unique positive contributor at the larger value minus
cost if positive; otherwise zero. Equal values above cost admit every split
of total a-c. The output reports this interval, a nonunique flag and the
explicit equal-split representative for individual participation comparisons.
It does not claim a unique equilibrium selected by strict own concavity.

The planner maximizes (a1+a2-c)*g-g*g, giving max(0,(a1+a2-c)/2). Prices ai-g
induce that common quantity when treated as fixed and cover cost at a positive
optimum. At zero quantity, no money is spent or collected. Negative prices
are economically meaningful subsidies but forbidden by the proposed scheme.
No reporting mechanism or truthfulness result is supplied. A transfer T moves
money from household1 to2; it is not another real resource cost.

Feasibility requires affordable efficient procurement, nonnegative personal
prices, assumed authority for a positive transfer and weak participation
relative to the stated private equilibrium. Valid but infeasible proposals
return reasons, not a domain error or a fake successful zero policy. The
budget-constrained quantity/welfare are a separate planner sensitivity; the
code does not pretend that the original personalized prices implement it.
The algebraic weak-participation transfer interval must be intersected with
the permitted nonnegative-transfer domain. Authority flags are assumptions in
synthetic cases, not observations of actual legal or institutional authority.

REFERENCE ECONOMICS
Base values6/4,cost4,budget12,transfer2: private total2 and welfare8; efficient
total3 and welfare9. Prices3/1 give payments9/3 and utilities4.5/4.5 versus
private2/6. Transfer interval[1.5,2.5]; transfer2 leaves utilities2.5/6.5.
Delayed values7/5,cost4,budget16,transfer3: private3,welfare15; efficient4,
welfare16; uncompensated utilities8/8 versus4.5/10.5. Transfer3 leaves5/11.
Budget10 cannot fund base efficient cost12; constrained quantity2.5 has8.75
welfare, requiring a separate financing proposal. Values10/2,cost4 need
prices6/-2 and fail the nonnegative-price rule (and uncompensated participation).
Equal values5/5,cost4: continuum of private splits totaling1; equal-split
utilities2.5/2.5, efficient3 gives4.5/4.5. Missing transfer authority makes the
base compensated proposal infeasible even when its arithmetic is unchanged.

ROSTER, RUBRIC AND EVIDENCE
Six labels A-F have exactly one explicit row at baseline, immediate and delayed
stages. Full texts, independent/assisted/missing statuses and four corrected
criterion credits are supplied. Each criterion awards0 or2: private scale,
planner scale, welfare, individual interpretation. This is an authored coarse
rubric, not a validated ability scale. Software adds annotated judgments; it
does not grade natural language or infer actual knowledge. Missing records
have empty text and zero recorded assessment credit but score:null. Assisted
work may be scored while remaining separate from independent evidence.

The original v1 marker wrongly credited baseline A's statement that a higher
total means everyone gains. V2 changes only that interpretation component2to0,
retaining the original response and all other scores. The correction ledger
identifies stage, learner, criterion, old/new credit and reason. Review all
texts under the corrected key; do not silently erase the old release.

Corrected score vectors in roster order (missing displayed as recorded zero):
baseline 6,8,2,0,8,6; immediate 8,8,6,0,8,8; delayed 8,8,6,0,0,6.
Baseline roster/submitted/independent counts6/5/4; means5,6,5.5; one independent
complete response of4. Immediate counts6/5/2; means19/3,38/5,8, with three
assisted submissions. Delayed counts6/4/4; means14/3,7,7, with two missing.
The same independent baseline/delayed learners A,B,C,F change2,0,4,0 points,
mean1.5. This is descriptive across changed tasks, not a causal teaching effect.
Response selection, assistance, practice and task difficulty remain unresolved.

OUTPUT MAP
models: all six cases, equilibrium/utility/welfare/payment/participation/budget
results and explicit proposed-scheme diagnostics.
grading: both versions, every scored row, full denominators, means and complete
counts, preserving missing score null versus recorded zero credit.
corrections: exact versioned component repair.
paired_independent: only same learners independent at both declared stages.
project_scoring: seven tasks mapped to five20-point domains, totaling100.
evidence_status: synthetic observation, prepared revision, absent actual learner
evaluation and the20 stipulated observation minutes.

CONTINUATION
Adapt the proposed undergraduate and graduate courses to an actual audience.
Obtain the relevant permission/access arrangements before collecting learner
work. Agree observation purpose, support conditions, data handling and reviewer
role with an independent qualified human. Deliver actual instruction, retain
full permitted responses and denominator/support records, obtain real observer
notes, reflect and revise. Later evidence must document implementation and
independent transfer appropriate to the claim. If access or observation is
unavailable, retain a pending status; this capsule cannot create those events.
