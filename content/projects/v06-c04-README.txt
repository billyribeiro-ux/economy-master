Consumption, saving and finite investment — original synthetic lab
Edition boundary: 2026-10-06. Created/checked: 2026-10-08.

Place v06-c04-analysis.py and v06-c04-inputs.json in the same directory.
Run with Python 3, with no installation or network access:

    python3 v06-c04-analysis.py

An absolute path to the program works from any current directory. The default
input is resolved beside the program, not against the current directory.
You may pass a different JSON input as the sole command-line argument.

All cases are invented for the chapter; none are empirical estimates or dated
observations. Read the chapter's timing and restrictions before changing inputs.
The program solves only certain-income two-date log utility and the stated
finite quadratic investment problem. It does not solve a general uncertain
life-cycle model, estimate household expectations, or implement policy advice.

Household inputs: x0 is date-0 matured assets plus disposable income; y1 is
date-1 nonasset income; R is the positive gross real return; beta is positive;
B is the nonnegative maximum borrowing amount. Consumption is strictly positive.
The terminal asset has no utility, cannot be negative, and is exhausted. The
same R applies to borrowing and lending. Credit at its bound may have a zero
multiplier; that is distinguished from a strictly positive marginal value.

Firm inputs: K0 and delta determine inherited K1 before new installation.
Ibar is a positive physical installation cap. p0 and p1 are real-dollar prices
per capital unit; phi is dollars per squared capital unit. Date-1 net operating
return is alpha*K1-gamma*K1^2/2. It may include negative marginal returns on
part of the feasible domain; it is the stipulated net-return function there.
The firm pays p0*I+phi*I^2/2 now, receives operating proceeds next period, and
sells the remaining (1-delta)*K1 then. Both future proceeds are discounted once.
The firm cannot sell old capital at date 0 or choose negative installation.

Numeric JSON values must be finite numbers, not booleans or quoted text.
Inputs have magnitude <=1,000,000, at most 30 significant decimal digits and
absolute decimal exponent <=100; file size <=100,000 bytes; each group has
1 to 50 uniquely named cases. The program checks signs, delta<=1, positivity
and optimization certificates explicitly even when Python assertions are disabled.
JSON decimals are converted exactly to rational numbers, and result numbers
are rational strings such as "12/5", avoiding binary rounding in these ledgers.

Selected expected results:
- worked_unrestricted: saving -20, c0 60, c1 75, multiplier 0.
- worked_credit_limit: saving -8, c0 48, c1 90, multiplier 1/144.
- alternative_belief: saving -8, c0 48, c1 60, multiplier 0.
- zero_future_income: saving 6, c0 6, c1 6.
- worked_firm: I 2, K1 8, present value 216/5, incremental value 12/5.
- capacity_one: I 1, K1 7, present value 213/5, incremental value 9/5.
- higher_resale: I 5/2, incremental value 15/4.
- higher_resale_cap_two: I 2, incremental value 18/5.
- low_operating_return: I 0, incremental value 0.
- no_adjustment_cost: I 3, incremental value 18/5.

Try an anticipated resale-price revision separately from a physical cap change.
Explain every response using the derivative and the actual constraint. Do not
read a negative unconstrained candidate as an admissible investment decision.
Compare the date-0 resource costs to the discounted future proceeds. Existing
capital proceeds enter total project value; incremental value subtracts the
I=0 baseline. This is not a cash-flow statement for a whole operating business.

The library's separate check_v06_c04.py recomputes the manuscript and these
results using independent budgets, polynomial interpolation, derivative signs,
finite-state expectations and exact lifecycle ledgers. Computational checks
supplement the chapter's analytic proofs; they do not establish model realism.
