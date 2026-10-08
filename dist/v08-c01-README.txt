Volume 8 Chapter 1 — Value creation and capital budgeting
Original fictional finite-project lab, created 8 October 2026.

FILES AND OFFLINE RUN
Save v08-c01-analysis.py and v08-c01-inputs.json together. Python 3 standard
library only; no network, installation, spreadsheet or account is required.

  python3 v08-c01-analysis.py
  python3 v08-c01-analysis.py path/to/changed-inputs.json

The CLI prints strict JSON; v08-c01-results.json preserves the original result.
Imports and run(data) print nothing. No files are changed by the benchmark.
The repository checker is: python3 scripts/check_v08_c01.py, from book/.
The CLI resolves its default input beside the script, not against the working
directory, so the two files can be copied and used offline elsewhere.

NUMBERS AND DATES
All money is kCU. Time 0 is now; later array entries are annual end dates.
The discount rate is a supplied annual rate, not an estimate from market data.
Use JSON integers or quoted decimal/fraction strings. Unquoted JSON decimals
are converted to strings when read by the CLI to preserve decimal precision.
A direct Python run(data) caller should use integers or strings, not floats.
Exact fractions and display decimals are returned together. IRR brackets have
exact rational endpoints; the estimate is a rounded annual decimal rate.
0.13357868 means about 13.357868%, not 0.13357868%.

KESTREL INPUT CONTRACT
The main arrays share a 1–30 year horizon. Cash operating costs are operating
amounts before the separately modeled working-capital timing. Foregone rent
and lost existing contribution are incremental whole-firm consequences. All
operating amounts in those arrays are nonnegative inputs; their net margin can
be negative. Extra costs and tax settle at the respective supplied end dates.
Sunk study and unchanged allocated cost are descriptive excluded amounts: the
original study has no future refund/payment/tax consequence; total company
allocated costs do not change with the decision. Changing either input alone
must not alter the project valuation.

Equipment is purchased at time 0 and available for the entire first year. Its
initial tax basis equals its cash cost. Each depreciation entry is a supplied
tax deduction; cumulative tax depreciation cannot exceed that initial basis.
Book depreciation matches it only in the manuscript's main example. No
additional capex, interest, fees, principal flows or outside equity proceeds
are included in this operating investment stream.

The explicit fictional tax convention permits immediate full use of ALL
incremental tax effects against ample other taxable profit. Taxable operating
margin is cash margin minus tax depreciation. Negative incremental tax is an
immediate tax reduction under that convention. Disposal tax is tax rate times
sale proceeds minus remaining tax basis. This is not a universal tax rule or a
general deferred-loss engine. A different usability convention is rejected;
model its timing separately rather than relabeling a future deduction as cash.

Working-capital balances contain noncash operating assets net of operating
liabilities. The first is the time-0 requirement. Each subsequent change
alters cash with the opposite sign. The final balance must be zero because
this lab is a liquidated finite case: all balances are recovered/settled at
their stated amounts with no additional tax consequence. Changing the final
recovery assumptions requires an explicit new model, not an unsupported
perpetuity. Terminal equipment proceeds are separate from this recovery.

The main cash sequence is (-105, 30.25, 41.75, 66.75). At 10% its exact NPV is
19045/2662 = 7.154395191585274 kCU. Its conventional IRR is about 13.35786838%.
Committed time-0 funding 80 falls short of the 105 cash outlay by 25. This is
not a full funding schedule and does not authorize a negative cash asset.
The investment's relative cash changes may be negative while a fully funded
firm's actual balance is positive; distinguish those objects.

IRR SCOPE
conventional_irr requires one negative initial flow, nonnegative later flows
and at least one strictly positive later flow. It brackets the unique root on
r > -1, including negative roots. A positive root additionally requires a
positive undiscounted sum. Bisection uses 90 iterations in x=1+r and an explicit
128-doubling search cap; exceptional inputs outside that teaching range fail.
It does not silently apply that routine to later obligations.

For a three-date stream, two_period_roots solves C0*x^2+C1*x+C2=0 and retains
only real x>0. Perfect-square discriminants return exact roots; other roots
are labeled rounded. The original multiple-IRR case gives 10% and 30%; the
no-IRR case has a negative discriminant. The borrowing stream has a 20% root
but negative NPV at 10%, so cash orientation must be interpreted. For other
nonconventional horizons the program labels the root analysis as outside its
scope; it does not assert that a returned root is the only possible one.

EXCLUSIVE CHOICES, SERVICE AND CAPITAL BUDGET
Comparison streams are separate original examples, discounted at the common
rate solely because their cash-flow comparisons stipulate that compatibility.
Scale: Small (-40,56), Large (-100,130); at 10% Large has greater NPV despite
lower IRR. Timing: Early (-100,130,0), Late (-100,0,150); crossover is 2/13.
No unprovided reinvestment cash is added.

The service module requires an integer horizon divisible by each option's
life, identical replacement availability, the same service, and zero terminal
resale. Payments for replacement occur at the start of the new cycle, which
can coincide with the previous cycle's final operating payment. It computes
full matched-horizon costs and a one-cycle equivalent annual cost. In the
original two-year case, costs are Short (24,30,6) and Long (42,5,5); their
present costs are 56.23140496 and 50.67768595. Annual equivalents are 32.4 and
29.2. The model does not infer repeatability from an equipment life label.

The capital-budget module exhaustively enumerates up to 12 independent,
indivisible, additive one-year projects under a nonnegative date-0 cash cap.
Names must be unique. For Exercise 7, five of eight subsets are feasible and
B+C uniquely maximizes NPV at 38, using the full 100 budget. A highest-index
heuristic instead selects A with NPV 24. No interacting or contingent projects,
future funding limits or financing issuance effects are modeled here.

USEFUL INTERVENTIONS
1. Increase sunk_study or unchanged_allocated_cost: no financial change.
2. Set foregone_rent to zero: document why the alternative is no longer
   available, then check the resulting increase in after-tax operating cash.
3. Change working_capital_balances to [15,24,22,0]: cash becomes
   (-105,26.25,41.75,70.75), NPV 17365/2662 = 6.523290758827949.
4. Lower committed_time_0_funding: the cash gap changes; operating NPV does not.
5. Set tax_rate to zero or discount_rate to zero: these are new stated cases,
   useful for checking the tax bridge and undiscounted limit, not market claims.
6. Change a replacement flag to false: an explicit failure prevents an
   unsupported matched-service claim. Supply a new dated alternative instead.

REVIEW LIMITS
Financial identities and exact arithmetic do not authenticate forecasts,
establish financing commitments, calibrate investment risk or prove legal,
reporting, tax or operational compliance. No real company or current rate is
represented. See the chapter for full original solutions, timing proofs and
interpretation. Final source registration, whole-library integration, browser
and print checks, acceptance and publication are coordinator responsibilities.
