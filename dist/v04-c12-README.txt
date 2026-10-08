V04-C12: EMPIRICAL INTEGRATION AND REPLICATION
Edition boundary: 2026-10-06. Author/source inspection: 2026-10-07.

This package reconstructs actual published historical BLS aggregate estimates.
It is not a synthetic worker dataset or a microdata replication. The numerical
extract is a manual transcription, not original downloaded webpage bytes.

QUESTION AND FIXED TARGET
Reconstruct the July 2024 U.S. household-survey TOTAL seasonally adjusted (SA)
unemployment statistics in the 2 August 2024 Employment Situation release:
rate 4.3 percent, June-to-July increase 0.2 percentage point, and increase in
unemployed persons 352 thousand. Population: civilian noninstitutional people
age 16 and over, United States (50 states and District of Columbia).

SOURCE, VINTAGE, ACCESS AND USE
Source: U.S. Bureau of Labor Statistics (BLS), Employment Situation -- July
2024, USDL-24-1571, released 2024-08-02 08:30 EDT (12:30 UTC).
https://www.bls.gov/news.release/archives/empsit_08022024.htm
Table A-1 TOTAL; narrative Household Survey Data; technical note and footnote.
Observation months: 2023-07, 2024-06, 2024-07. Retrieved/checked 2026-10-07.
The full nine-column table header was inspected before selecting positions
1,2,3,4,8,9, covering three periods under NSA and SA. The text extract records
the complete column order. Thousands separators were removed; no values were
imputed or altered to force identities. Published rates keep one decimal.

The archived HTML was accessible through the web retrieval tool without an
account/payment. A separate direct curl download returned HTTP 403. This
package preserves a manually checked minimal numeric extract, not raw HTML.
The SHA-256 hashes cover local transcription bytes, not original website bytes.
They detect change relative to the manifest, not official authenticity.

BLS states its publications are public domain except previously copyrighted
photos/illustrations and requests source attribution. This attributed numeric
extract uses no images or emblem. Public-use statement inspected 2026-10-07:
https://www.bls.gov/opub/copyright-information.htm
Definitions inspected: https://www.bls.gov/cps/definitions.htm
These live explanatory pages were inspected for relevant sections; they are
not claimed as immutable 2024 versions. The archived release also defines the
rates and describes the relevant survey/seasonal-adjustment limitations.

FILES
v04-c12-source-extract.txt   Human-readable source metadata and delimited values.
v04-c12-data.json            Six structured empirical records with unit metadata.
v04-c12-manifest.json        Source/access/protocol fields and two local hashes.
v04-c12-replication.py       Original standard-library benchmark, offline/read-only.
v04-c12-benchmark.json       Preserved execution output for comparison.
v04-c12-README.txt           This instruction/provenance/rubric record.

RUN
Place the three input files (extract, data, manifest) beside the Python program.
Requires Python 3.10 or later; authored/checked with Python 3.14.6. No install,
network request or external package is required. Run:
  python3 v04-c12-replication.py
Optional explicit directory containing the inputs:
  python3 v04-c12-replication.py /path/to/package
The default path is relative to the script, not the shell's working directory.
To preserve the new report without replacing the supplied benchmark:
  python3 v04-c12-replication.py > my-replication-report.json
Exit codes: 0 passed all baseline checks; 1 invalid/missing inputs; 2 usage;
3 inputs valid but a numerical target/display/identity check fails.
Input files are never rewritten. Normal operation prints JSON to stdout;
invalid input prints its diagnostic to stderr. Import has no side effects.
Python version in the reproduction metadata may differ across environments;
the rational arithmetic and specified numerical outputs should agree.

DATA DICTIONARY AND ASSUMPTIONS
period: calendar month label, not release date. adjustment: SA or NSA.
population_thousands: civilian noninstitutional population age 16+.
labor_force_thousands: employed plus unemployed conceptually.
employed_thousands / unemployed_thousands: household-survey estimated persons.
not_in_labor_force_thousands: population outside that labor force.
published_rate_percent: one-decimal source text, e.g. "4.3".
Levels are integer thousands of persons, not a respondent sample size.
Population itself is not seasonally adjusted; source footnote1 explains its
identical values on both sides. The adjustment key labels the table's series
block, not a claim that the population denominator was seasonally adjusted.
Source source_release is 2024-08-02; replacing it with latest revised values
would define another task. No missing months or person observations invented.

CALCULATION AND ACCEPTANCE
Rate percent = 100 * unemployed / labor force. Exact Fraction arithmetic avoids
binary-rounding ambiguity. Displays use nearest tenth, ties away from zero;
none of the actual source ratios/change results are ties. This is the declared
reconstruction display rule, not a claim to recover BLS's undisplayed numbers.
Baseline passes when reconstructed rate is 4.3, monthly change is 0.2 pp, and
unemployed change is 352 thousand. All six reconstructed rate displays must
match their source displays. Also require absolute residual <=1 thousand for
L-E-U and P-L-N in these six rows. Under exact underlying identities and <=0.5
thousand rounding for each component, integer residual magnitude is <=1.
This is a narrow compatibility check, not a rule for every adjusted subgroup.

The program checks exact metadata/types/unique keys, positive labor force,
bounded nonnegative integer levels, file hashes and equality of independently
parsed text and JSON values. It reports every row's raw ratio, display match,
level-rounding envelope and identities. The envelope assumes levels vary by
at most half a thousand and bounds the numerator/denominator ratio. It is a
conservative rounding sensitivity bound, not any sampling confidence interval.

EXPECTED BENCHMARK
July SA ratio: 716300/168429 = 4.252830569557499% ->4.3%.
June SA ratio: 681100/168009 = 4.053949490801088% ->4.1%.
SA monthly difference: 0.198881078756411 pp ->0.2 pp; count change352 thousand.
July SA unemployed: 7.163 million ->7.2 million narrative display.
SA annual ratio difference: 0.719891779636906 pp ->0.7 pp.
SA annual difference of source displays: 4.3-3.5=0.8 pp.
NSA monthly ratio difference: 0.248261765677517 pp ->0.2 pp.
NSA annual ratio difference: 0.743084300530949 pp ->0.7 pp.
July SA rounding envelope: [4.252521084489356,4.253140056463129] percent.
Nonzero identity residuals: June2024 SA L-E-U=-1 thousand;
July2023 NSA P-L-N=-1 thousand. All other specified residuals are zero.
All primary outputs, six display matches and identity-compatibility checks pass.

PROTOCOL AND DISCREPANCIES
Baseline fixed as above. Secondary grid: SA/NSA x monthly/yearly July change;
report all four, both rounding orders, and level changes. Do not select a
favorable cell after calculation. This teaching protocol was designed with the
historical result known; it is not a retroactive preregistration claim.
D01: raw ratios differ from displays; nearest-tenth matching explains the gaps.
D02: annual SA 0.8 vs0.7 comes from different rounding order; report both.
D03: two -1-thousand identity residuals are compatible with component rounding;
retain source inputs, do not insert balancing values.
D04: survey weighting, population controls, seasonal adjustment estimation and
sampling uncertainty are outside reconstruction scope.
The report dynamically flags unresolved display or identity departures if
valid altered data are supplied; a mismatch is not automatically explained.

PROJECT AND EVALUATION (100 POINTS)
Submit the unchanged-package output, one independently computed baseline rate
and annual comparison, a one-page report, and a specification ledger.
20 source: exact source/table/header, vintage, access, transcription method,
   units/population, local hashes and public-use basis documented.
30 calculation: baseline all three targets correct (15), independent ratio
   and annual rounding-order reconstruction (10), identities/envelope (5).
20 comparison: all four declared cells with units (10), rationale for changed
   horizons/adjustment and transparent exploratory additions (10).
20 report: discrepancies retained/explained (10), published-aggregate scope,
   sampling/causal/predictive limits and date distinction (10).
10 reliability: run from a different working directory and demonstrate the
   deliberately altered denominator in a separate temporary copy.
The altered June SA L=168109 is an INVENTED ERROR, not a new observation:
L-E-U=99 thousand while rate=4.051537990% still rounds to4.1. The original
manifest rejects its changed bytes. To explore arithmetic alone, work on a
clearly labeled in-memory copy through calculate(); preserve original files.
Do not claim success with wrong vintage, units or an unsupported causal effect,
regardless of the numerical score. Remediate that critical interpretation error.

LIMITS AND NEXT STEPS
Agreement with aggregate displays does not validate BLS source measurement or
rebuild microdata weights, seasonal factors or standard errors. Denominator
counts are not independent sample sizes. Six overlapping series records are
not six independent replications. No significance test, forecast or identified
policy effect is supplied. Annual comparisons cross population-control updates.
The numeric extract is fixed; current online definitions/reuse pages may change.
Revised-vintage analysis should use newly named inputs and a separate report,
preserving this baseline and documenting all changes. Full microdata replication
requires further inputs/methods; an empirical extension requires a new design.
