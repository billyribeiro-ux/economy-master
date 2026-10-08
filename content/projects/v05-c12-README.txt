V05-C12: exact randomization, synthetic truth and observed evidence

Files
  v05-c12-experiment.json: original synthetic input and complete design metadata
  v05-c12-randomization.py: standard-library Python enumeration program
  v05-c12-output.json: preserved baseline report

Download all three files into one directory. Run:
  python3 v05-c12-randomization.py
On Windows, py -3 may replace python3. The default input is resolved beside the
program, so the terminal's working directory does not matter. An optional local
variant can be read with --data PATH. The program reads files but writes none;
it prints one JSON report to standard output. No network, package installation,
random-number generator or seed is used. Do not overwrite the baseline input
when exploring a variant.

Provenance and timing
All participants, interfaces and outcomes are author-created hypothetical
objects. They are not empirical observations. File creation is dated 8 October
2026; the textbook evidence boundary remains 6 October 2026. Relative days 0/7
describe the toy protocol, not actual calendar observations. Assignment occurs
on day 0, before treatment delivery; every completion is observed by the same
rule at the end of day 7. Values are binary 0/1. A mean difference 0.75 means 75
percentage points, not a 75% relative change. Assignment is at person level;
there are eight units, not sixteen potential-outcome observations.

Protocol and benchmark
Exactly four of eight people receive a preselected booking interface, uniformly
over the 70 possible subsets. Final available choices, stated prices and
information are fixed. The target is the assignment effect on session completion
within these eight people. Subsequent voluntary adoption is not the randomized
variable. No interference, delivery failure or missing outcome is present.

The prespecified statistic is treatment mean minus control mean; the test uses
its absolute value and includes ties. The observed rates are 1 and 1/4, difference
3/4. Under the individual sharp null, the five observed ones and three zeros
remain fixed. The difference distribution is:
  -3/4:5 assignments; -1/4:30; 1/4:30; 3/4:5.
The two-sided p-value is 10/70 = 1/7. The positive tail is 5/70 = 1/14, reported only
to explain what a genuinely predeclared one-sided test would calculate. It is
not a direction chosen after looking at the result. Neither rejects at 5%.

The separate synthetic oracle supplies both potential outcomes solely for an
instructional audit. Its individual effects are 1,1,0,0,0,1,1,0, averaging 1/2.
Reassigning treatment now requires changing observed outcomes according to
those potential outcomes. The mean of all 70 contrasts is 1/2 and their assignment
variance is 1/16. This distribution is different from the fixed-outcome null
distribution. The observed-only function never reads the oracle. Removing it
leaves the observed analysis unchanged. Replacing it with the compatible
all-zero-effect schedule changes synthetic truth but not the observed test.

Limits and input checks
The program supports complete uniform assignment with 2 through 16 units and
nonempty arms. It rejects missing or nonbinary outcomes, booleans posing as
numeric fields, duplicate IDs, changed/unsupported assignment or test rules,
inconsistent treatment counts and inconsistent oracle values. It does not
invent a missingness rule or treat other assignment designs as permutations.
The sharp null means no effect for every person, not merely an average of zero.
This is not an average-effect confidence-interval routine. Exact enumeration
has no Monte Carlo error; it does not remove the experiment's uncertainty.

No empirical effect, psychological mechanism, welfare benefit or transport to
another population is inferred from these fictional inputs. Rerunning this
calculation establishes same-data reproducibility. New-data replication and
validation of actual assignment/measurement require additional work.
