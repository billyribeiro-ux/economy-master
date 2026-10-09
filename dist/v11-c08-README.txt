V11-C08 — Insurance, pensions and household finance
Original finite contract and resource laboratory, 9 October 2026

Purpose
Reproduce fixed-menu insurance choices, independent versus common-regime claim
tails, nested life-contingent payments, pension funding through actual zero
sales, limited support and household cash/debt/retirement accounts. All input
values and institutions are synthetic. No external dataset, service, package,
credentials or network access is used. Python 3 standard library only.

Run
Keep v11-c08-analysis.py and v11-c08-inputs.json together:
  python3 v11-c08-analysis.py
  python3 v11-c08-analysis.py --input changed-inputs.json --output changed-output.json
The default input resolves beside the implementation, independent of working
directory. Without --output, one JSON document is written to standard output.
With --output, success is quiet. Errors go to standard error and return code 2;
validation finishes before an output is written. Do not choose an existing
valuable file as output. The program refuses direct, resolved, symlink and
hard-link aliases of its input or implementation. This is a local accidental
overwrite guard, not a concurrent adversarial filesystem security service.

Portable API
Import the implementation with importlib.util.spec_from_file_location and call
run(data). Import and run are quiet. The input is not mutated. Validation raises
ValueError with a domain message; it remains active under python3 -O. The report
contains JSON values only. Duplicate JSON keys and nonfinite JSON constants are
rejected by the CLI; callers must provide ordinary JSON-shaped objects.

Numeric and schema contract
schema is integer 1, not boolean. Objects have exactly the supplied keys;
unknown keys are errors rather than silently ignored assumptions. Decimal inputs
are strings with at most 12 digits before and after the decimal point, no
exponents, rational slash strings, leading plus, NaN or infinity. Most amounts
are nonnegative and no greater than 1e9. Probabilities lie in [0,1]; population
shares are strictly positive and sum exactly to one. Regime/state weights can
include zero but must sum exactly to one. IDs are unique within a collection,
begin with a lowercase letter and contain at most 40 lowercase letters, digits
or underscores. 'uninsured' is reserved in the insurance menu.

Members are integers 1..200. Time vectors have 1..12 periods; related vectors
must have equal lengths. Type, contract, regime, pension-path and loan lists
have at most 8 rows; guarantee states at most 12. These are teaching-program
limits, not restrictions on real economics. Most values are exact Fractions
internally and exact fraction strings in output. Forty-digit Decimal square
roots are labeled utility approximations; maximizing-menu comparisons use an
absolute 1e-30 tie tolerance. This numerical tolerance is not an economic
indifference theorem. Curve-shift values use floating exp and are labeled
approximations. The reader's rounded numbers are not the calculation inputs.

Insurance
wealth > 0, loss between zero and wealth, and each premium/indemnity must leave
nonnegative wealth in both states. Indemnity cannot exceed the fixed loss.
Claims are fully performed for the utility/menu calculation; this is separate
from the pool insolvency experiment. All types can choose every offered
contract or uninsured. Pool full premium is population mean probability times
loss. At that premium a type buys on weak preference (within stated tolerance).
Buyer composition is recomputed; if nobody buys, selected probability and
per-buyer margin are null. No expenses, endogenous effort or competition/entry
game is modeled. This is a fixed-menu IC/IR test, not market equilibrium.

Pool
One same-date benefit per claim. Resources = members*premium + capital; the
expected premium margin is not added a second time. An independent binomial
law uses the weighted regime-mean probability. The comparison is a mixture of
conditionally independent binomials with exactly that same marginal. The model
uses a finite exact recurrence, including p=0 and p=1. It reports P(claims >
resources), expected positive resource deficit, average-claim variance and its
common-regime limit. No guarantee, recovery priority, expenses or support is
assumed. Changes to capital alter resources, not claim probabilities.

Annuity
survival and stress_survival must be nonincreasing vectors in [0,1]. The weighted
regime vectors must reproduce baseline survival at each date; change both when
designing a new common-law experiment. Discounts are deterministic and lie
between 1e-6 and 100; they need not be decreasing, permitting negative forward
rates within this mathematical exercise. Payments occur at year-end only if
alive. The temporary contract stops after the final vector entry. Death benefit
pays at the end of the year of death within this horizon. Annual survival for
one life is nested, not independent; different lives are independent only
conditional on the common regime. Average and total variances have CU-squared
units and are separately named. No actual life table, infinite lifetime tail,
market risk price, inflation linkage or mortality estimation is supplied.

Pension fund
Uses the annuity's members, benefit and discounts. zero_faces are nonnegative
payments at each date; money_account is initially available. Survivor paths
are nonincreasing integers from 0 to members and are realized scenarios, not
guaranteed expected counts. Before each due date, cash grows by previous D/current
D and the current zero matures. The stated executable market quotes a remaining
zero j at D[j]/D[t]; the policy sells the latest maturity first, only as needed,
without short sales. There are no costs, haircuts, encumbrance or borrowing.
Sales finish before payout; subtract sold face from future inventory exactly
once. If all resources are exhausted, pay available cash, report unpaid benefit
and stop at that first failure; terminal_cash is null. A second path receives
the proven minimum extra initial cash max(path PV - initial assets,0), which is
sufficient ONLY with these deterministic rates and execution rights. It is not
an automatic contribution commitment or a solvency rule.

parallel_continuous_rate_shift is in [-0.2,0.2]. Repricing uses D[t]*exp(-t*shift)
for both asset faces and baseline expected benefits while initial cash is fixed.
The exact derivative is per unit rate; multiply by 0.01 for one percentage point.
This is a separate valuation sensitivity; it does not rewrite the reference
cash-path trading policy or estimate a joint rate/longevity law.

Guarantee
One terminal promised benefit. Resources are used in order: assets, separately
available sponsor capacity, separately available guarantor capacity. Neither
support capacity is already in assets. Payments cannot exceed remaining benefit
or capacity. Residual asset value belongs to the fictional sponsor. State
probabilities describe a physical law, not market pricing. No support premium,
statutory insurance, subrogation or jurisdiction-specific priority is assumed.

Household
Initial debt already exists after a financed purchase: no fresh proceeds are
added. Income is spendable before listed end-year obligations; liquid cash earns
zero, the pension return occurs before contribution, and the account cannot be
withdrawn until after the final date. Loan rate is fixed in [0,1] on opening debt.
Nonnegative scheduled principal repayments sum exactly to original debt.
The report gives projected cash for a fixed plan; negative values flag payment
failure, not borrowing. A floor breach can occur without negative cash. The
minimum extra initial cash for a fixed nonnegative floor includes date zero.
Taxes, fees, uncertain income, new borrowing and changing household decisions
are not modeled. No claim of optimality or personal recommendation is made.

Meaningful interventions
Increase pool capital to 200 or 600; change partial indemnity/premium to 10/1;
use a small two-member pool and enumerate its states by hand; change the annuity
benefit and check linear means/quadratic variances; zero pension assets and
inspect first failure plus explicitly funded repair; add weak-state guarantor
capacity 20 or 35; reduce final household income by 2; separately reduce the
first contribution by 1. Verify cash, inventory, probability mass and support
conservation. Original chapter exercises also remove the first-date sale right;
that scenario requires hand calculation because the lab deliberately fixes
sale access. It must not be represented by merely lowering an asset's mark.

Integrity and review
v11-c08-manifest.json binds the exact input, implementation, reference output and
this README. It is a byte-integrity record, not mathematical or empirical proof.
The source repository's independent author checker uses direct combinatorial
probabilities, nested covariance, discounted asset conservation, closed-form
household balances, statewise guarantee certificates and targeted domain/CLI
tests. Separate peer and coordinator review remain distinct acceptance gates.
