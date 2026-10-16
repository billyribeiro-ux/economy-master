ALDER INTEGRATED POLICY AND INVESTMENT CASE
Original synthetic teaching model, 16 October 2026. No observed data.

Keep these five reader files together:
 integrated-case-inputs.json    exact stipulated primitives
 integrated-case-analysis.py    Python 3 standard-library reference
 integrated-case-output.json    generated baseline, not independent evidence
 integrated-case-README.txt     these instructions
 integrated-case-manifest.json SHA-256 and bytes for the other four files

Run from this directory:
 python3 integrated-case-analysis.py --output my-baseline.json
Compare parsed JSON objects with integrated-case-output.json. Rational strings
and integers are exact. Whitespace and object key order do not affect equality.
Running with no arguments regenerates integrated-case-output.json deliberately.
Use a separate path for your own work. Source, input, README and manifest aliases
(including resolved symlinks and existing hardlinks) cannot be output targets.

For the required stress, copy inputs to cap3-inputs.json and change only
bank_loan_cap from 4 to 3, then run:
 python3 integrated-case-analysis.py --input cap3-inputs.json --output cap3-output.json
Do not alter a hashed reference file to simulate an unchanged baseline.
The changed result must exclude n=2 from feasible optimizers. Rows describing
infeasible actions are hypothetical; negative unused cash in such rows does not
constitute authorized financing. No external borrowing or guarantee exists.

Two-state cash pricing, funding and exact endpoint social values are computed.
The causal interval is an identified set under an exact sensitivity restriction,
not a confidence interval or probability distribution. The high-endpoint weight
is a separately supplied two-point prior. The forecast envelope is valid only
for that endpoint prior family. Deterministic minimax regret uses the endpoint
maximum because affine payoffs yield convex regret. The randomized minimax
proof is in the assessment, not returned by this program. Compensation is fixed
at date 0 and evaluated for robust household participation, with real admin.

All rational input primitives must be integers or rational strings, never
floats or booleans, with magnitude at most 10000. Quantities are unique integers
0 through 10 including zero. Additional domain restrictions appear explicitly
in validate(). This is a finite two-state model, not a general economic solver.
Malformed inputs fail; no automatic fallback creates a plausible-looking result.

Provenance: original authored primitives, no third-party dataset, credentials,
network access, market estimates or legal authority. Record Python version,
commands, input changes, comparison method and discrepancies in your submission.
The manifest verifies unchanged bytes, not the assumptions or economic truth.
The library's internal review is not external human certification. Human grading
must inspect the reasoning, oral transfer and suitability of any real use.
