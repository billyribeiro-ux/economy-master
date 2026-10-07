SIMULATION AND MONTE CARLO: DAILY INVENTORY COMPARISON
Original synthetic learning project; no observed firm or market data.
Created 2026-10-07 for the edition boundary 2026-10-06.

FILES AND OFFLINE RUN
Keep v04-c06-inventory.py and v04-c06-case.json in the same directory.
With an existing Python 3 installation, run:
  python3 v04-c06-inventory.py
On Windows with the Python launcher, use py -3 instead of python3.
The script reads its input relative to its own location, even if your terminal
has another working directory. It uses only the Python standard library,
makes no network requests, writes no input files and prints a JSON report.
Save output with ordinary terminal redirection if desired. Keep this README,
the input and the precise script version with that report. Importing the
script defines functions but does not run a simulation or read a file.

TARGET AND ECONOMIC ASSUMPTIONS
Estimate E[profit_B - profit_A] in USD cents per day under a fixed synthetic
demand law. Both inventories are selected before the day's demand is revealed.
Each unit sells for price_cents_per_unit; every stocked unit costs
cost_cents_per_unit; every unsold unit returns salvage_cents_per_unit.
Profit = price * min(demand, stock) + salvage * max(stock-demand, 0)
         - cost * stock.
No fixed costs, financing costs, taxes, demand responses, stock carryover or
multi-day dependence are included. These are assumptions, not estimates.
The project compares only the two supplied policies. A higher expected profit
does not establish risk preference, financing feasibility or real-world demand.

INPUT CONTRACT
The JSON object must have exactly the fields in the supplied case. Duplicate
names, nonfinite JSON constants, missing/extra fields and invalid UTF-8 fail.
case_id and provenance: nonblank strings.
currency: exactly USD. period: exactly day.
demand_units: 1-20 strictly increasing integer values from 0 to 1,000,000.
demand_weights: matching integer weights from 0 to 1,000,000, with positive
total. State probability is weight / total; zero-weight states are permitted.
stock_a_units and stock_b_units: integer quantities from 0 to 1,000,000.
price/cost/salvage_cents_per_unit: integer cents from 0 to 1,000,000, with
salvage <= cost <= price. These inequalities define this teaching model.
replications: integer from 2 to 200,000. seed: integer from 0 to 2**64 - 1.
Booleans, quoted numerals, fractional values, infinities and NaN are rejected
where integer values are required. The bounds control a small local teaching
run; this is not a hostile-input service or an unrestricted inventory engine.
Errors produce a diagnostic on stderr and exit status 1, with no numeric report.
Success has exit status 0. Validation stays active under Python's -O option.

SIMULATION DESIGN AND REPRODUCIBILITY
One serial random.Random(seed) generator is created before the loop. Each
replication consumes exactly three random() draws in this order:
  1. shared demand for the paired A/B comparison;
  2. demand for the independent A calculation;
  3. demand for the independent B calculation.
For both methods there are n comparisons and two profit evaluations per
comparison. The comparisons are iid in the ideal sampling model. Within
each shared-demand pair, A and B are deliberately dependent. Compute the
sample variance of differences, not separate marginal standard errors.
The report records seed, generator, draw order, runtime and replication count.
A changed draw order changes reproducible output even if the seed is unchanged.
Repeating an identical seeded run creates no new statistical evidence.
The pseudorandom sequence is deterministic; the usual statistical calculations
describe the ideal independent-uniform sampling experiment it approximates.
Python's random() draws have finite precision. The supplied quarter boundaries
are grid-compatible; arbitrary weights can incur tiny finite-grid/rounding
differences from exact rational probabilities. Versioned runtime records matter.

EXACT BENCHMARK AND DEFAULT OUTPUT
The program enumerates every demand state using fractions.Fraction, reporting
exact moments as rational strings. This avoids rounding those reference values.
For demands 60/90/120, A profits are 28000/48000/48000 cents and B profits are
20000/50000/60000 cents, so differences are -8000/2000/12000 cents.
Exact means: A 43000 cents, B 45000 cents, difference 2000 cents.
Exact variance of A: 75000000 cents^2; B: 225000000 cents^2.
Paired-difference variance: 50000000 cents^2.
Independent-difference variance: 300000000 cents^2 (six times paired).
Probability B earns less than A on the same demand: 1/4.
The true MCSEs for n=10000 are about 70.710678 cents paired and 173.205081
cents independent. These population quantities differ from estimated MCSEs.

Recorded CPython 3.14.6 run, seed 20261006, n=10000:
  shared counts, demand 60 / 90 / 120: 2423 / 5029 / 2548
  paired mean: 2125 cents; sample variance: 49699344.93449345 cents^2
  paired estimated MCSE: 70.49776232937714 cents
  paired approximate 95% MC interval: [1986.8243858344208,2263.175614165579]
  independent mean: 2112 cents; sample variance: 294516907.6907691 cents^2
  independent estimated MCSE: 171.6149491421913 cents
  independent approximate interval: [1775.634699681305,2448.365300318695]
Runtime metadata changes with the interpreter. Tiny printed float differences
can occur across environments. The report is not a real-data estimate.
Divide mean/MCSE/endpoints by 100 for dollars; variance by 10000 for dollars^2.
Pairing need not be closer in every realized run: it is farther in this run.
The normal intervals describe approximate Monte Carlo sampling error for the
fixed model. They do not include uncertainty in demand, costs or policy effects.

LEARNER PROJECT AND EVALUATION
1. Reproduce the baseline; preserve input, code, report and runtime details.
2. Independently reproduce the exact state profits, expected difference,
   covariance and paired/independent variances by hand or rational arithmetic.
3. Set A's stock equal to B's in a copy of the case. Explain why every paired
   difference must be zero, while independent differences need not be zero.
4. Restore the baseline stocks. Change weights to [2,1,1] in a labeled case
   copy. Before running, compute the new exact difference and variance.
   Expected results: mean -500 cents; paired variance 68750000 cents^2.
5. Report both sensitivity cases, a prespecified simulation budget, estimated
   MCSE and a qualified decision. Separate numerical precision from the
   evidence needed to decide which demand law is realistic.
6. Try invalid input in a disposable copy, such as a boolean replication count
   or all-zero weights. Require explicit failure rather than a zero result.
The command reads the fixed filename. Keep scenario copies in separate folders
with the same two filenames, or restore the original input before the next run.
Do not silently overwrite the only baseline record.

Suggested rubric (100 points): target, timing and units 15; reproducibility
record 15; independent exact arithmetic 25; correct paired replication/MCSE
reasoning 20; sensitivity and limits 15; invalid/edge-case tests 10.
Critical errors requiring repair: treating copies as independent, concealing
seed selection, equating a simulated interval with model validation, or mixing
cents and dollars. Alternative justified sensitivity cases are acceptable if
they retain valid marginals, document the changes and qualify their claims.

FURTHER STUDY
The chapter links official Python random/statistics documentation and Art
Owen's author-hosted variance-reduction notes. It derives elementary Monte
Carlo variance, common random numbers and antithetic pairs. This program does
not implement antithetic sampling, Markov-chain simulation, importance sampling,
sequentially valid stopping or data-based parameter uncertainty.
