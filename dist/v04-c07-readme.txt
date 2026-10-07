V04-C07: REGRESSION AS PROJECTION — EXACT OFFLINE LABORATORY

These records and programs are original synthetic teaching materials created on
7 October 2026 for the edition boundary of 6 October 2026. They are not market,
firm or labor observations. No external data or network connection is needed.

1. Save these three files in the same folder:
   v04-c07-regression.py
   v04-c07-cases.json
   v04-c07-readme.txt
2. Using an existing Python 3 installation, run:
   python3 v04-c07-regression.py
   On Windows with the Python launcher: py -3 v04-c07-regression.py
3. To use a modified copy of the JSON input, supply its path:
   python3 v04-c07-regression.py my-cases.json

All input files are read-only. Results print as JSON; exact fractions are encoded
as strings such as "7/10". The program writes no files. Importing it defines
functions without fitting data or printing. No third-party packages are needed.

EXPECTED RESULTS
- cost_line coefficients: 7/10, 6/5. SSE 9/5; SST 9; SSR 36/5;
  R-squared 4/5; training MSE 9/20; leverage 7/10,3/10,3/10,7/10.
  Evaluation predictions 11/2 and 67/10; evaluation MSE 17/100.
  Prediction at output 6 hundred units: 79/10 thousand USD.
- labor_groups coefficients: 10,2,4. SSE 12; SST 82; SSR 70;
  R-squared 35/41. Predicted labor at 2 batches is 14 hours for weekday,
  18 hours for weekend. These are fitted descriptive comparisons.
- cost_cubic coefficients: 1,17/6,-5/2,2/3. Training SSE 0 and R-squared 1;
  evaluation predictions 15,36 and MSE 461. At output 6: 72 thousand USD.

MODEL AND NUMERICAL CONTRACT
Each case has a complete design matrix (first column ones), integer outcomes,
matching named predictor units and outcome units. Training uses 1..32 rows and
1..8 columns; evaluation/prediction may have 0..32 rows. Integers must have
absolute value at most 1,000,000. Missing values, floats, booleans, unknown/missing
fields, duplicate JSON keys and duplicate case/predictor IDs are rejected.
The validator checks representation and dimensions, not the truth of units or
economic mechanisms. The rows supplied for a polynomial must already contain
the matching powers; the program does not infer this from their column names.

Fraction arithmetic forms exact normal equations. A square system is solved
by pivoted row elimination and back substitution, never by explicit inversion.
Deficient rank raises a clear error; it does not return an arbitrary coefficient
family. Exact arithmetic is useful for these tiny rational examples. It does
not make the method suitable for large datasets or prevent sensitivity to
changes in nearly redundant inputs. For general floating data, use appropriate
QR/SVD implementations and numerical rank diagnostics. No inferential standard
errors, confidence/prediction intervals or causal estimates are produced here.
The standalone file is a local teaching tool, not a hostile-input service.

EXPERIMENTS AND DELIVERABLE
A. Reconcile the cost line with centered sums; reconcile the labor slope by
   subtracting weekday/weekend means. Check X-transpose times residual = zero.
B. Append a column twice the output column to every cost_line design row and
   give it a distinct name/unit. Update training/evaluation/prediction matrices.
   Explain why the fit now refuses unique coefficients although the projection
   onto the training column space is still unique.
C. Change only the evaluation outcomes. The fitted coefficients, training SSE,
   residuals and leverage must stay fixed; only evaluation errors/MSE change.
D. Convert cost_line outcomes and evaluation outcomes to USD by multiplying
   them by 1,000 and updating outcome_unit. Check coefficients and residuals
   scale by 1,000, sums of squares by 1,000,000 and R-squared remains 4/5.
E. Explain why cost_cubic's perfect training fit does not choose it for budgeting.

Submit exact reconciliations, the rank diagnostic, one units check and a short
account of the distinction between in-sample fit, evaluation and causation.
A good report uses the same fixed training fit for evaluation, states the small
synthetic support, and avoids claims about real forecasting superiority.
