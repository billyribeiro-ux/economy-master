V06-C09: FINITE FISCAL PATHS
Original synthetic teaching cases; prepared 8 October 2026.

Run python3 v06-c09-fiscal.py from any working directory, or pass an alternative
JSON input path. Keep the default inputs beside the program. Standard library
only, no network, installation or file writes. Success prints exact rational
results in JSON. Invalid input prints a JSON error to stderr and returns 1.
Imports are quiet and validation remains active under python3 -O.

B is end-period domestic-currency principal at par. Interest is paid on opening
debt. GDP grows by (1+inflation)(1+real_growth); primary surplus and adjustments
are shares of CURRENT GDP. Positive surplus lowers debt. Adjustment raises debt
and in this lab is a financing cash flow such as acquiring a financial asset.
It is NOT an unrecorded extra primary expense or a noncash valuation gain.

Requested surplus ratio = primary_base + feedback*(opening_debt/opening_GDP-target).
If supplied, surplus_cap truncates this request from above. Output records both
requested and implemented ratios and whether the cap changed the request.
No lower bound on the deficit ratio is imposed beyond bounded input parameters.
An unconstrained rule's convergence formula does not apply in a capped period.

Issuance = maturing principal + interest - primary surplus + adjustment.
Ending debt = opening debt - maturing principal + issuance.
The maturity fraction applies to opening principal. The model rejects negative
issuance or debt: it contains neither a buyback rule nor a net-asset regime.
All issuances are assumed fundable at par; the output is not evidence of access.
There is no valuation, currency, yield-curve or refinancing-risk model.

The discounted identity sums (surplus-adjustment)/product(gross interest factors)
and includes the discounted terminal debt. Its residual must be exactly zero.
When assets are acquired, this is a FINITE CASH/DEBT IDENTITY, not a complete
resource-solvency test: acquired assets' payoffs and terminal values would matter.
A positive terminal debt means the supplied finite path has not repaid everything;
it is not by itself a finding of insolvency. No infinite continuation is inferred.

Cases: fixed-target surplus, stable uncapped feedback, capped feedback, the two
exercise-8 stress paths, and the worked asset-acquisition/partial-maturity case.
Benchmark stores the complete exact output. All numerical inputs are authored,
with no country data or probabilities. Their equal inclusion supplies no weights.

Validation requires exact field sets, unique case names, 1..20 cases, 1..60 dates,
finite rational inputs of absolute value <= 1,000,000, gross growth/interest factors
positive with net rates <= 1, initial debt >= 0, GDP > 0, feedback in [0,3], target
ratio in [0,5], primary_base/adjustments in [-1,1], maturity in [0,1], and any surplus
cap in [0,1]. Booleans are not numbers. These are computational domain bounds,
not empirical plausibility estimates. Output remains exact through Fraction.

The repository checker independently accumulates nominal debt and discounts,
checks the fixed-rule closed form and uncapped feedback eigenvalue, recomputes
all worked/exercise anchors, verifies benchmark consistency and portable CLI
execution, and rejects representative invalid inputs. Review of derivations,
accounting meaning and evidence scope remains separate from computation.
