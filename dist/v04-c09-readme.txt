Prediction and model validation: exact original synthetic laboratory

Files: v04-c09-validation.py and v04-c09-case.json in the same folder.
Run: python3 v04-c09-validation.py
An optional first argument supplies another case JSON. The default path is
relative to the program, so execution from another directory works. There are
no network calls, third-party dependencies, random seeds or file writes.

Data: original monthly business-demand teaching sequence, not empirical data.
Value units: units per month. Period is a consecutive calendar-month index,
not a date or a count of rows since the preceding observation. 'released' is
the index of the period at whose end that observation becomes available.
Release must be >= observed period. Forecast origin t is just after period t
ends and eligible releases arrive. Values are never revised in this small case.

The initial four records precede all evaluation. Validation targets are 5..8.
At each origin t-1 the program rebuilds each method from only then-released
records. Methods are latest available value, expanding mean, and endpoint drift
per elapsed month. Drift is not OLS regression and is not a fitted causal trend.
At end8 the candidate with least validation MSE is chosen, using the fixed
naive/mean/drift tie order. All validation target labels must be released by8;
otherwise selection at that date fails explicitly.

Final targets9..12 use the chosen procedure with prespecified refitting after
new releases. The report also provides the same untouched comparison methods
and a distinct fixed-origin8 multi-horizon experiment. These are different
deployment protocols. It never switches the selected method using test losses.
Scoring is retrospective after all required labels arrive; those labels are
not supplied to the earlier forecast functions.

Expected original-case output:
Selected: drift.
Validation MSE naive43/4, mean35109/400, drift5641/3600.
Updating final MSE naive7/4, mean147373547/1960200,
drift147393481/25401600. Drift final errors: -25/7,-25/8,2/9,-4/5.
Fixed-origin8 drift forecasts: 844/7,862/7,880/7,898/7;
their final MSE5133/98. Output fractions carry exact and decimal forms.
Squared losses have (units per month)^2; MAE/mean error use units per month.

Contract: exact fields shown in supplied JSON; 4..120 complete consecutive
periods; integer nonnegative demands <=1000000; release indices <=N+12;
at least2 initial training observations and at least1 validation/test target.
Booleans, missing/nonfinite/quoted numbers, duplicate fields/periods, unsupported
units and changed candidate order fail. Raw row order is irrelevant. An origin
without2 released records cannot support the complete comparison and fails.
The internal formula functions assume the validated contract; they are not a
general externally exposed forecasting API. Exact arithmetic removes roundoff,
not data uncertainty or poor economic assumptions.

Exercises: alter only period12's value; selection and all forecasts through12
must stay unchanged, while its score changes. Alter period9's value; selection
and the period9 forecasts stay unchanged, but prespecified updates for10..12
may change. Delay period8's release to9: validation selection at8 must fail.
Delay period9's release to10: forecasts at origin9 must exclude it; at origin10
it can join the history. Preserve the baseline file and name scenario copies.

Submission: original report, one mutation audit, a timing diagram, exact loss
reconciliation, and a short memo distinguishing validation choice from the
later baseline comparison. Full credit requires correct origins/releases,
honest test role, stated loss units, and recognition that this invented path
cannot establish future business performance or causal effects.
