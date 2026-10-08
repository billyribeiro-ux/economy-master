COMPUTATIONAL RELIABILITY AND NUMERICAL AUDITS
Chapter v04-c11. Original synthetic stress inputs; no measured institution data.
Created 2026-10-07 for the edition boundary 2026-10-06.

RUN OFFLINE
Keep v04-c11-audit.py and v04-c11-case.json together. Use an existing Python 3
installation with ordinary binary64 round-to-nearest floating arithmetic:
  python3 v04-c11-audit.py
  python3 -O v04-c11-audit.py
Windows with the Python launcher: use py -3 in place of python3.
No third-party packages, installation, network or credentials are needed.
The script reads beside itself, even when launched from another directory.
It prints a JSON report without writing or changing the input file. Errors
produce a diagnostic on stderr, exit status 1 and no numeric report. Normal
completion has status 0. Importing the module does not read inputs or print.

THE CLAIM BEING AUDITED
ledger_transactions_cents: signed same-day receipts/payments; receipt positive.
The exact net is the sum of the specified integer cents. No interest, prices,
foreign-exchange conversion or inter-day discounting enters this sum.
conversion_probe_cents: a separate stress list testing information lost when
integers are first converted to binary floating point.
margin_observations_cents: the complete supplied list of daily margin amounts.
The target is the descriptive population variance of that list, divisor n,
in cents^2. It is not an iid unbiased sample variance or a standard error.
Every quantity has one day's horizon. This is not a live settlement service.

SCHEMA AND BOUNDS
The root JSON object must have exactly these fields:
  case_id, provenance: nonblank strings.
  currency: USD; money_unit: cent; period: day.
  ledger_transactions_cents, conversion_probe_cents:
      lists of 1-200 integer amounts, each within +/-10^18 cents.
  margin_observations_cents:
      list of 1-200 integer amounts, each within +/-10^12 cents.
Booleans, floats, numeric strings, nulls, nonfinite constants, duplicate JSON
fields, missing/extra fields and unsupported units fail explicitly. Lists may
contain repeated values and negative values; those have defined meanings.
An empty list fails; one margin has population variance zero. The relative
sum condition number is null for an exact zero net because its denominator
vanishes. The program still reports absolute arithmetic error bounds.
The finite bounds keep arithmetic away from overflow/underflow and cap the
quadratic-cost pairwise reference. They are computational choices, not a
general economic restriction. The program checks binary64 format and the
runtime's reported nearest-rounding mode; exotic floating environments are
outside this demonstration's supported contract.

REFERENCE METHODS
Ledger: integer addition preserves exact cents.
Representation audit: Fraction.from_float recovers the exact rational value
of a stored binary float. It cannot recover a different original number.
Sequential addition: an explicit left-to-right loop, not built-in sum, makes
the demonstration independent of improvements to Python's float sum routine.
Let u=2^-53 and k=n-1. On these normal-range integer-valued terms, sequential
sum roundoff is bounded by k*u/(1-k*u) times the sum of absolute represented
terms. Net representation error is measured separately using the original
integers. The report stores the bound as an exact rational string and also
as an approximate float. The bound's meaning depends on the arithmetic model.
Variance reference: sum_{i<j}(xi-xj)^2/n^2, using integer differences and exact
fractions. The candidate variance centers integer values before floating
arithmetic, then averages centered squared deviations. No large raw squared
level is subtracted from another. The mean is an exact integer total followed
by one float division; its bounded total is below 2^53 and its error is checked
against u times the exact mean's magnitude.
The variance comparison budget is max(1e-9 cents^2, 1e-12 times exact variance).
This is a declared engineering check budget, not a general theorem or economic
materiality threshold. Actual variance error is separately measured exactly.
Both exact reference and candidate are checked after translation, scaling and
reversal. The candidate is also checked against the independent reference.

BASELINE RESULTS (RECORDED CPYTHON 3.14.6)
First ledger [10^16,1,-10^16]:
  exact net 1 cent; represented-input net 1 cent; conversion error 0;
  left-to-right float sum 0.0; accumulation error 1 cent;
  math.fsum on converted values 1.0;
  relative condition number 20000000000000001;
  arithmetic bound approximately 4.440892098500627 cents.
Conversion probe [2^53+1,-2^53]:
  exact net 1 cent; represented-input net 0; conversion error 1 cent;
  left-to-right float sum and math.fsum both 0.0;
  accumulation error 0, total error 1 cent.
Margins [100000001,100000002,100000003]:
  exact mean 100000002 cents;
  exact population variance 2/3 cents^2 = 1/15000 dollars^2;
  centered approximate variance 0.6666666666666666 cents^2;
  exact centered variance error 1/27021597764222976 cents^2;
  raw second-moment variance 0.0 on the recorded runtime.
All six deliberately broken variants should be detected by their fixed tests.
Ordinary and optimized runs must have identical numerical results; the
assert_statements_enabled metadata changes. Runtime metadata may differ on
another machine. Exact reference fields and rational bounds are strings.

THE SIX BROKEN VARIANTS
1. left_float_ledger: float accumulation loses a cent; compare integer sum.
2. early_float_conversion: fsum cannot restore a cent lost during conversion.
3. raw_second_moment_variance: subtracting large rounded moments loses spread.
4. sample_denominator_for_population_target: wrong n-1 divisor gives 1 instead
   of 2/3 on [1,2,3]. Transformation identities alone do not catch it.
5. linear_conversion_of_squared_units: dividing cents^2 by 100 instead of
   10000 gives 2/75 rather than 1/3750 for a variance of 8/3 cents^2.
6. input_mutation: reversing the caller's list leaves its sum correct but
   violates the contract. Compare saved inputs as well as the scalar answer.
These challenge functions are labeled broken_* and are never used as the
authoritative ledger or variance reference. The detectors use fixed fixtures,
so modifying a valid case does not silently remove the challenge cases.

LEARNER AUDIT PROJECT
Preserve the baseline, report and command/runtime record. Make a separate
scenario folder containing the same program and input filenames before edits.
1. Independently reproduce both one-cent sums and the variance 2/3.
2. Run ordinary and -O modes. Required validation and gates remain active.
3. Change margins to [7,7,7]: mean 7 and population variance 0.
4. Change margins to [100000002,100000004,100000006]: mean 100000004 and
   variance 8/3. Translate down by 100000000 and scale by -3; variance 24.
5. Reorder the first ledger to [10^16,-10^16,1]. Exact net remains one; the
   left-to-right result now retains it. Explain why the original order still
   provides an important regression fixture.
6. In a disposable input copy use a boolean amount, empty list or dollar unit
   label. Require an explicit failure, including under -O.
7. Ask a peer to run the package from another working directory and independently
   derive one reference. Exchange target definitions, not only screenshots.
The report fingerprints the exact input and program bytes with SHA-256. These
identify the files used. They do not prove source completeness or truthfulness.

Suggested rubric (100 points): targets, units and input contract 20; independent
sum/variance references 25; error/conditioning distinctions 20; six faulty
variants and meaningful transformations 15; reproducible package/peer memo 20.
Repair before passing: accepting invalid inputs as zero, using an unjustified
looser tolerance to hide a failure, confusing n with n-1, converting variance
units linearly, or claiming exact arithmetic proves the economic model.

LIMITS
These are numerical stress cases, not source-reconciled real ledger records.
Amounts alone cannot detect duplicate identifiers, omitted accounts or wrong
cutoff dates. No measured economic uncertainty is inferred. Finite tests do
not prove every modified implementation, arbitrary floating environment or
economic decision correct. The report's passed status concerns the listed
checks and fixtures. Exact arithmetic can calculate a wrong economic target
exactly. Whole-library visual, mobile and print QA is a separate task.
