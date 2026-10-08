FOUNDATION BASIC DATA-ANALYSIS PRACTICAL
Original SYNTHETIC repair-desk case; no real firm, market rate or measured data.
Created2026-10-07; edition boundary2026-10-06; fictional April2025 scenario dates.

FILES AND COMMANDS
foundation-practical-data.json: authoritative record-level authored snapshot.
foundation-practical-source.txt: complete source assumptions/data dictionary.
foundation-practical-manifest.json: local input-byte hashes and provenance.
foundation-practical-analysis.py: offline standard-library benchmark.
foundation-practical-benchmark.json: preserved complete output.
foundation-practical-README.txt: these commands, targets and assessment guide.
The foundation assessment page contains the full practical and20 solved parts.

Place the three inputs (data/source/manifest) beside the program. Use existing
Python3.10+; checked with CPython3.14.6. No installs/packages/network/credentials.
  python3 foundation-practical-analysis.py
  python3 -O foundation-practical-analysis.py
Optional scenario directory containing files with the same three names:
  python3 foundation-practical-analysis.py /path/to/scenario
To save a new report without overwriting the benchmark:
  python3 foundation-practical-analysis.py > my-foundation-report.json
The default input path is beside the script, independent of current directory.
Import is quiet; no input or source file is rewritten. Output is JSON on stdout.
Invalid inputs produce stderr diagnostic and exit1; usage error exits2; a valid
case whose calculated cash differs from the supplied bank cash exits3 with a
discrepancy report. Success exits0. Explicit validation survives Python -O.
The report includes input/program hashes, Python version and origin/snapshot.
Local hashes identify bytes; they do not prove source truth or real evidence.

CONTRACT AND TIMING
Read the source notes for every field and economic assumption. Input money is
bounded nonnegative integer USD cents, not bool/float/text. Model outputs use
USD exactly via Fraction division by100; squared errors/variances use USD^2.
The nine7April transactions use fixed IDs/classifications and opening balances.
The proposed machine is unexecuted and is not in that historical ledger.
Operations are selected days' variable consumables costs, not the whole firm's
operating expense and not additional entries in the7April ledger.
All six operating days are active; D1 has an observed zero, D6 is unreported.
Origin=8April2025 at12:00UTC; snapshot=12April2025 at12:00UTC.
Features must be available before their scheduled day and by the origin.
Cost versions must follow the observation day, increase in time/version, and
be in the snapshot. Training uses latest release no later than origin; scoring
uses target first release available by snapshot. No label means null error/loss.
Canonical dates, schema, record IDs, units and protocol are fixed. Missing/extra
fields, duplicate keys/records/versions, nonfinite inputs, bool/float amounts,
impossible release times and unsupported metadata fail explicitly. All four
training labels must be available; they are never dropped to force a fit.
Capital probabilities are positive rational strings summing to1; one state
persists through two year-end payments. One simulation draw is a whole project.

EXACT BASELINE TARGETS
Opening assets3300=liabilities800+equity2500 USD.
Operating cash flow300; financing330; cash change630; closing cash2630.
Profit350. Closing receivables400, equipment1000, payables250, loan1050,
equity2730. Closing assets4030=liabilities1300+equity2730.
Operating cash=profit350 minus receivables increase100 plus payables increase50.
Borrowing is not revenue; principal payment and owner withdrawal are not expense.

Training x=[0,1,2,3] jobs; origin costs y=[0,4,4,10] USD.
D3's4USD v1 is eligible; its8USD v2 released11April is not.
OLS intercept0, slope3USD/job. Fitted[0,3,6,9]; residuals[0,1,-2,1] USD.
Residual sum0; job-weighted residual sum0; SSE6USD^2; TSS51USD^2; R2=15/17.
Frozen D5/D6 forecasts12/15USD; both extend beyond observed x support0..3.
D5 first-release actual15 gives error3USD and loss9USD^2. D6 remains null.
Scored1, unscored1; available-outcome MSE9USD^2, not a two-target/population MSE.
Latest-snapshot diagnostic refit uses[0,4,8,10]: intercept2/5, slope17/5,
SSE6/5, TSS59, R2=289/295. D5 prediction14 has retrospective error1, but
cannot be substituted for the original8April forecast using future revision.

Discount factors4/5 and16/25; annuity36/25=1.44.
Each year's gross savings450(high)/250(low), minus forgone rent50, gives400/200.
Price500 -> state NPVs76/-212 USD. Expected NPV92/5=18.4USD, variance331776/25
=13271.04USD^2, SD576/5=115.2USD; loss probability1/5. Immediate cash2130
exceeds2000 reserve. Decision from exact risk-neutral model: buy.
High-state regret buy0/defer76; low-state regret buy212/defer0.
Expected regret buy212/5=42.4USD versus defer304/5=60.8USD.
These are UNCONSTRAINED payoff comparisons; apply cash feasibility separately.
The decision gate respects feasibility even if a changed case makes buy
inadmissible. Regret alone does not override the reserve rule.
Expected NPV(C)=2592/5-C; strictly decreasing with slope-1.
Break-even price518.4; cash ceiling630; economic bound is tighter. Tie defers.
High-state probability threshold at price500: p>53/72, with tie defer.
High-state year2 advantage118.75 discounted by1.25^2 recovers76USD.
Price520 transfer: cash2110, NPVs56/-232, expected-8/5=-1.6, action defer.

SIMULATION BENCHMARK AND INTERPRETATION
Initialize one rng=random.Random(40517), then make400 successive rng.randrange(5)
calls; tickets0..3 high,4 low. Do not reset the seed inside the loop.
One persistent state supplies both year's payments for each independent
replication. Recorded CPython3.14.6 counts: high327, low73.
Mean586/25=23.44USD; numerical error126/25=5.04USD versus exact expectation.
Estimated MCSE from sample variance with divisor399:5.56905305053734USD.
Theoretical MCSE from exact model variance:115.2/sqrt(400)=5.76USD.
The latter would be2.88USD for1600 independent complete-project replications.
Runtime-specific streams from higher-level random routines can vary; always
reconcile counts/payoffs and record version. Exact model values are invariant.
Do not select a seed/stopping time or let simulated sign replace exact decision.
MC error, project risk, parameter uncertainty, forecast error and causal
identification are distinct. Simulation supplies no measured population sample.

REQUIRED FAILURES AND TRANSFERS
Keep originals immutable; use a named temporary copy or in-memory deepcopy.
Change loan receipt500->510 without changing supplied bank cash: calculated
cash2640 versus2630, discrepancy10USD; the algebraic balance identity still
holds. Original input hash catches changed bytes first; explicitly renewed
hashes in a labeled scenario allow the independent cash check to be exercised.
Reject duplicate day/version, boolean amount and release before observation
in normal and -O execution. A matching updated hash never establishes truth.
Move only the late D3 revision's value in memory: origin fit/forecasts stay
unchanged; later diagnostic fit may change. A new hypothetical D6 release18USD
at12April09:00 raises scored count to2; its error3/loss9 leaves MSE9. Original
coefficients and capital assumptions remain frozen; baseline D6 stays missing.
Zero imputation would falsely create a D6 loss225 and a two-target MSE117.

DELIVERABLES AND SCORING
Open-resource planning estimate3-5hours, not empirically calibrated timing.
Submit memo, technical answers, original inputs/manifest, executable analysis,
saved output/runtime record, discrepancy/test log and independent calculations.
Four domains25points each; each has five5point parts fully solved on the page:
D1 opening stocks/units; cash flows; profit/closing identity; investment timing;
   reserve feasibility and unexecuted proposal.
D2 OLS derivation; residual/fit audit; price monotonicity/bounds; probability
   threshold and independent timing check;520USD sensitivity.
D3 moments/downside; regret choice; simulation; theoretical/estimated MCSE and
   replication unit; empirical/sampling/causal limits.
D4 version-aware input; frozen forecasts/missing scoring; later-refit leakage;
   failures/hashes; bounded recommendation and explicit missing-outcome transfer.
Threshold85/100 and at least19/25 in each, plus critical-error repair and separate
oral transfer. Method-equivalent derivations earn credit. Do not invent missing
values, use future revisions at origin, misclassify loan revenue, mix units or
claim causal/modeled-input validity from fit, simulation or exact arithmetic.
Accepted source methods are linked from the assessment; this original synthetic
case needs no new external source verification. No visual/mobile/print QA claim.
