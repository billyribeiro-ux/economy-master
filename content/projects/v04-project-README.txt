VOLUME 4 INTEGRATIVE EMPIRICAL PROJECT
Created/source inspection: 2026-10-07. Edition boundary: 2026-10-06.
Actual historical public BLS aggregate estimates; original analysis and code.

PURPOSE AND FILES
Reconstruct three labor-force measures, describe six published unemployment
rates by intercept OLS, and evaluate a fixed pedagogical forecasting protocol.
v04-project-source-extract.txt: manually inspected source values and full headers.
v04-project-data.json: six ordered monthly records and exact metadata.
v04-project-manifest.json: two source URLs, per-protocol metadata and local hashes.
v04-project-analysis.py: read-only standard-library analysis.
v04-project-benchmark.json: preserved complete reference output.
v04-project-README.txt: commands, provenance, methods, targets and rubric.
The assessment page provides complete learner instructions and instructor guide.

RUN OFFLINE
Keep the program and all three input files (data, extract, manifest) together.
Python 3.10+; checked on CPython 3.14.6. No packages, install or network calls.
  python3 v04-project-analysis.py
  python3 -O v04-project-analysis.py
Optional explicit directory containing the inputs:
  python3 v04-project-analysis.py /path/to/package
To preserve a new report without overwriting the supplied benchmark:
  python3 v04-project-analysis.py > my-project-report.json
Default inputs are beside the script regardless of current working directory.
Import is quiet and does not read files. Inputs are never rewritten.
Exit 0: local source/display/identity checks pass. Exit 1: invalid/missing input
or computational failure. Exit 2: usage error. Exit 3: structurally valid inputs
with numerical source-display or component-identity mismatch. Errors go to stderr;
successful and numerical-mismatch reports are JSON on stdout. -O retains gates.
Reproduction metadata includes Python version, implementation, two input hashes
and program hash. Runtime metadata may differ; exact fraction results must agree.

SOURCE CONTRACT: TWO RELEASES, NOT ONE
Table A-1 TOTAL, U.S. Bureau of Labor Statistics, Employment Situation:
February 2024 from the release of 2024-07-05 at 08:30 EDT, USDL-24-1270:
https://www.bls.gov/news.release/archives/empsit_07052024.htm
March-July 2024 from the release of 2024-08-02 at 08:30 EDT, USDL-24-1571:
https://www.bls.gov/news.release/archives/empsit_08022024.htm
The latter table has SA July2023 and March-July2024; NO February2024 column.
The earlier table has SA June2023 and February-June2024. Both full nine-column
headers and selected TOTAL rows were inspected before manual transcription.
Overlapping March-June values agree across these two releases, but earlier
first-release values were not reconstructed. Preserve per-row source_release.
Do not call this a single-release vintage or a real-time forecast backtest.

Access: both archived HTML releases retrieved through the web retrieval service
without account/payment. Local text is a manual numeric extract, not downloaded
original HTML bytes; no original-source-byte hash is claimed. The two local
files derive from one documented transcription, not independent observations.
SHA-256 identifies their local bytes relative to the manifest, not authenticity.
No invented balancing value, imputed month or synthetic worker was added.

Official BLS public-use statement, inspected in the earlier c12 source review:
https://www.bls.gov/opub/copyright-information.htm
BLS publications are public domain except previously copyrighted photographs
and illustrations; attribution is requested and supplied. No photos, artwork
or BLS emblem are included. Definitions route:
https://www.bls.gov/cps/definitions.htm
Archived technical notes separately describe definitions, seasonal adjustment,
revisions and sampling/nonsampling error. Their survey estimation is not rebuilt.

SCHEMA AND UNITS
One record per consecutive month February-July2024 in that order, exactly six.
month: YYYY-MM label; source_release: date of chosen archived release.
population_thousands (P): civilian noninstitutional people age16+.
labor_force_thousands (L), employed_thousands (E), unemployed_thousands (U),
not_in_labor_force_thousands (N): integer thousands of persons, not sample sizes.
published_unemployment_percent, published_participation_percent,
published_employment_population_percent: exact one-decimal source strings.
Geography: 50 states and District of Columbia. Adjustment: SA column block.
Population itself is not seasonally adjusted (Table A-1 footnote1).
The household reference week generally contains the12th. These estimates are
not cumulative monthly flows or establishment-survey payroll job counts.
Dataset metadata fixes population, geography, units, adjustment and schema.
Levels must be nonnegative integer types (not bool or float), <=1000000 thousand,
with positive L<=P and E,U<=L. Published percent strings are in [0.0,100.0].
Duplicate fields/months, missing/extra fields, reordered or missing months,
wrong per-row release, nonfinite values and unsupported units fail explicitly.

RECONSTRUCTION
Unemployment u=100U/L; participation p=100L/P; employment/population e=100E/P.
Exact Fraction calculation; keep original counts and source displays. Use
nearest-tenth display, ties away from zero (none of these ratios is a tie).
This is a reconstruction display rule, not recovery of undisplayed BLS numbers.
All18 rate displays match. Identities tested: L-E-U and P-L-N in thousands.
Three nonzero residuals: April L-E-U=-1; April P-L-N=+1; June L-E-U=-1.
All other nine residuals are zero. Under exact underlying count identities
and <=0.5-thousand rounding of each component, integer residual magnitude<=1.
This is compatibility, not proof of unseen exact counts or a universal rule
for all independently adjusted subgroups. Reconstructed rate identity:
e-p*(1-u/100)=100*(E-L+U)/P. Nonzero gaps occur only in April and June.

Rounding sensitivity for ratio100A/B uses
  lower=100*(A-0.5)/(B+0.5); upper=100*(A+0.5)/(B-0.5),
clipped to[0,100] as needed. The denominator is safely positive here. For change,
lower=later_lower-earlier_upper; upper=later_upper-earlier_lower.
This conservative box bound may include incompatible joint corners but covers
the feasible ones. No probabilistic independence or confidence level is assumed.
Survey sampling error, measurement and revisions require separate information.

FIXED MODEL TARGET AND OLS
The model outcome is the PUBLISHED one-decimal unemployment rate:
  y=[3.9,3.8,3.9,4.0,4.1,4.3] percent; t=[1,2,3,4,5,6].
It is intentionally distinct from the reconstructed rounded-level ratio.
Descriptive equal-weight intercept OLS uses all six observations. No SE, causal
effect or out-of-sample forecast performance is inferred from this fit.
  ybar=4; tbar=3.5; Stt=35/2; Sty=3/2.
  intercept=37/10=3.7 percent; slope=3/35 pp/month.
  fitted=[53/14,271/70,277/70,283/70,289/70,59/14] percent.
  residual=[4/35,-1/14,-2/35,-3/70,-1/35,3/35] pp.
  sum(residual)=sum(t*residual)=0.
  SSE=11/350 pp^2; TSS=4/25 pp^2; explainedSS=9/70 pp^2.
  R^2=45/56. A high in-sample fit is not identification or validation.
The full-sample OLS fit is never used to choose a forecast rule.

FIXED FORECAST PROTOCOL
Historical answers were known when the teaching design was chosen. This is not
a preregistration or a contemporaneous backtest. Within the frozen vector:
Train February-April (first3); validate May (one); test June-July (two).
Naive forecast after history1..k: last value y[k].
Endpoint-drift forecast: y[k]+(y[k]-y[1])/(k-1), k>=2.
Loss=(actual-forecast)^2 in percentage points squared.
Exact validation tie selects naive. Freeze rule before test.
Predict June using February-May, then reveal June and predict July using
February-June. These are updating one-step forecasts, not two fixed-origin
forecasts. Report both rules' test scores; no reselection from test results.
All source releases and outcomes are inspected retrospectively; simply slicing
earlier months does not establish availability at real historical origins.

EXPECTED FORECAST TABLE
Target   Rule    Forecast%    Actual%  Error pp  Squared error pp^2
May      naive   39/10        4.0      1/10      1/100
May      drift   39/10        4.0      1/10      1/100
June     naive   4            4.1      1/10      1/100
June     drift   121/30       4.1      1/15      1/225
July     naive   41/10        4.3      1/5       1/25
July     drift   83/20        4.3      3/20      9/400
Selected naive test MSE=1/40=0.025 pp^2.
Unselected drift diagnostic MSE=97/7200=0.0134722222222 pp^2.
Do not replace the selected rule because the final diagnostic loss is lower.
One validation outcome and two dependent monthly test errors establish neither
stable ranking, calibrated uncertainty nor general predictive accuracy.

ADDITIONAL BENCHMARKS
Reconstructed unemployment percentages, chronological:
3.857226476,3.829178951,3.864699789,3.964061718,4.053949491,4.252830570.
Participation:
62.539828397,62.674515835,62.664418464,62.528704781,62.587636624,62.695984277.
Employment/population:
60.127525578,60.274596467,60.242999858,60.050028332,60.050737973,60.029630291.
Displayed February-to-July unemployment change=0.4 pp.
Reconstructed change=0.3956040933829503 pp.
Conditional rounding-change envelope=[0.3949844487916876,0.3962237379591878] pp.
July unemployment rounding envelope=[4.252521084489356,4.253140056463129] percent.
Each exact rate/envelope endpoint and comparison appears in the JSON output.

CHART TASK AND INSTRUCTOR CRITERIA
Panel1: equally spaced February-July month axis; unemployment (%) vertical axis
from3.5 to4.5, ticks every0.25 pp, clearly showing nonzero origin. Plot six source
points/solid line and six full-sample OLS fits/dashed line, labeled descriptive.
Mark training, validation and test regions. No bars, dual axes or hidden scale.
Panel2: same scale, selected forecasts at TARGET months May3.9, June4.0, July4.1
with actuals May4.0, June4.1, July4.3. Do not shift forecasts back to origin or
draw an evaluated forecast for the training months. Submit underlying values.
Caption must identify two source releases, population, SA block and historical
teaching scope. Any magnification of rounding envelopes needs separate labeling.
Accept reproducible software output or a readable faithful hand-drawn chart.

RELIABILITY CHALLENGES AND EXPECTED FAILURES
Keep frozen files intact; work in a separately named temporary/scenario copy.
Invented June L=168109 (not real data) yields L-E-U=99 and P-L-N=-100 thousand,
although its unemployment ratio4.051537990% still displays4.1. Original hashes
reject changed bytes. If only JSON is changed and its hash renewed, text/JSON
comparison fails. If both copies/hashes change, identities still expose this
case; passing hashes never authenticates origin. Duplicate April, bool level,
unsupported unit and zero denominator fail in normal and -O modes.
For forecast timing, change July in an in-memory copy: selection and the June
forecasts must stay identical. June may affect July's predeclared updating
forecast, but July itself must not affect that forecast. A target-in-history
candidate is leakage even if it achieves zero observed errors.

DELIVERABLES AND 100-POINT RUBRIC
Report/executive paragraph + technical appendix, original input/source/manifest,
code/output/runtime record, two charts and values, protocol/specification ledger,
discrepancy log, deliberate-failure records, one independent reconstruction and
one independent forecast calculation. Five essential domains,20 points each:
D1: two-source provenance5; keys/units/dictionary5; eighteen ratios5; identities5.
D2: offline reproducibility5; independent reference5; validation/failure tests5;
    immutable originals, hashes and discrepancy records5.
D3: OLS coefficients/units5; residual/SS/R2 checks5; chart values/axes/regions5;
    descriptive fit and honest source/scale caption5.
D4: rounding envelopes5; survey-uncertainty distinction5; identification/control
    critique5; explicit proposed intervention/design/assumptions5.
D5: prefix/May scores5; fixed tie/selection/updating5; all test scores/MSEs5;
    known-result, archive-availability, small-test and reporting limits5.
Suggested threshold85 total and15 in each domain. Critical false-vintage claims,
data corruption, test-driven reselection or mislabeled sampling inference must
be repaired even above the threshold. Equivalent valid calculations earn credit.

CAUSAL AND INFERENCE BENCHMARK
The slope is not an effect of time, policy or a treatment. Six aggregate rows
have no counterfactual identification design. A proposed job-counseling offer
study could specify eligible job seekers, a June offer intervention, employment
in July reference week, consistency/no-interference scope and randomized offer
assignment with complete follow-up. Observational adjustment needs justified
exchangeability and overlap. Post-offer search effort may be a mediator, so
adjusting for it can change the total-effect target. Other clear proposals are
acceptable if their data and assumptions are explicit. This project supplies
none of the necessary individual treatment/outcome data for that future study.
Population-estimate counts are not iid sample sizes. No survey confidence
interval, statistical significance, real-time forecast guarantee or causal
effect is established. Numerical validation is not source completeness or truth.
Visual/mobile/print UI quality assurance of the library remains a separate task.
