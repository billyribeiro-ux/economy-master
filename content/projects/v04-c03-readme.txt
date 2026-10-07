PYTHON FUNDAMENTALS: OFFLINE CASH-FLOW LAB

Files: v04-c03-cashflow.py and v04-c03-case.json must be in the same folder.
This file documents them. Use an existing Python 3 installation; the examples
use longstanding Python 3 syntax and were executed with Python 3.14.6.
No third-party packages, network, account, credentials or installation commands.

From that folder, the complete one-command run is:
    python3 v04-c03-cashflow.py
On Windows installations using the Python launcher:
    py -3 v04-c03-cashflow.py
From a different folder, pass the quoted full path to the script. The script
locates the JSON beside its own resolved path, not beside the terminal's
current directory. Keep real copies of both files together if using symlinks.

OUTPUT
The script prints a JSON report to standard output; it writes no files.
Expected undiscounted_net_cents: 30000.
Expected npv_cents_approx: approximately 3553.71900826446.
Expected npv_dollars_display: "35.54" (a display string, not exact arithmetic).
Last period: 3. The exact rational NPV is 430000/121 cents, or 4300/121 USD.
An input error prints a diagnostic to standard error and exits with status 1.
Success exits with status 0. Importing the program defines functions without
reading files or printing. The entry-point guard ensures that behavior.

DATA CONTRACT AND PROVENANCE
All data are original synthetic teaching assumptions, created 2026-10-07 for
the library's 2026-10-06 edition boundary. No observations, market quotations,
outside licenses, access accounts or private data are involved. These inputs
are supplied for use and modification with the library's exercises. Preserve
the original file and record modifications as new scenarios.

JSON object: exactly case_id, currency, period, timing, provenance,
cash_flows_cents, discount_rate_bps. Field names must be unique.
case_id and provenance: nonblank strings; they label rather than independently
prove provenance. currency must be "USD", period "year", and timing
"t0_then_year_end". The restriction avoids silently mixing units or timelines.
Cash flows: a list of 1 to 101 integers; first is today (t=0), later entries
are annual year-end flows. Negative means payment, positive receipt. Every
entry has magnitude at most 10**12 cents. Integers are exact input cents.
Rate: integer basis points from -5000 to 10000 inclusive (-50% to +100%).
Divide by 10000 to obtain the annual effective rate; 1000 bps means 10%.
Quoted numbers, booleans, fractional numbers and missing values are rejected
in both numeric fields. Missing/extra fields and duplicate JSON names fail.
The supported bounds keep this small demonstration away from floating
overflow; they are implementation limits, not universal economic restrictions.

MODEL
NPV in cents = sum of cash_flow_cents[t] / (1 + rate)**t, starting at t=0.
No taxes, risk adjustment, uncertainty, irregular dates or rate term structure
are inferred. The supplied rate must match the annual timing and the analyst's
stated valuation assumptions. Original input cents and their undiscounted sum
are exact integers; discounting uses approximate binary floats and math.fsum.
Rounding to two dollar decimals is for display. A tiny displayed difference
is not evidence of economically material value; inspect assumptions and
independent error/sensitivity checks. This is not a payment-settlement engine.

REPRODUCIBLE PRACTICE
1. Preserve the baseline, then change only discount_rate_bps to 0. The NPV
   becomes exactly 30000 cents (300 USD).
2. Restore 1000 bps; use flows [-10000, 5500, 6050]. NPV is mathematically
   zero. A tiny float residual is possible; use an absolute tolerance.
3. Try a quoted rate "1000", an empty flow list, or a repeated JSON field.
   Each should fail explicitly. Restore the baseline after the experiment.
4. Run python3 -O v04-c03-cashflow.py. Validation remains active because it
   uses exceptions and never relies on assert statements.

The file reader is for small local teaching inputs, not a hostile-input server
or a security sandbox. Numerical tests check calculations, not the economic
credibility of the assumptions or every possible future modification.
