VOLUME 6 CHAPTER 10 — TRADE, TARIFFS AND EXPORT CHOICES

All inputs are original synthetic teaching laws, not actual trade data, current
tariff rules or an empirical calibration. One common period; no debt or growth.

Place v06-c10-analysis.py and v06-c10-inputs.json in the same directory.
Run from any working directory:
  python3 /path/to/v06-c10-analysis.py
Or supply a different supported input explicitly:
  python3 /path/to/v06-c10-analysis.py /path/to/input.json

Requires only the Python standard library. No network, packages or installs.
The program prints one JSON result to stdout. Invalid input exits with code1,
no success JSON, and one JSON error on stderr. Import/analyze is quiet.
The model validation also operates under python3 -O.

Exact input contract
--------------------
The root fields are schema, provenance, units, tariffs and firms, exactly.
Schema/provenance/units must match the supplied fixture. They describe a fixed
numeraire and single-period model, not currency conversion or real-data units.
Each list has1–100 cases with a unique nonempty name of at most80 characters.
Numbers are JSON integers or strings such as "50/7". Floats, booleans, decimal
strings and nonfinite values are rejected. Rational strings have at most32
characters. After reduction |numerator|<=10^9, denominator<=10^6 and
|value|<=10^6. These finite bounds are a lab interface, not economic theorems.
Unknown/missing fields are rejected to catch silently ignored assumptions.

Tariff case: name, market ("small" or "large"), t>=0, dollars/imported unit.
Domestic D(p)=max(120-2p,0), S(p)=max(2p-20,0), exactly as the chapter.
Small: foreign offer20; large: inverse export supply10+M/6. These schedules
are deliberately frozen. To change them requires changing and re-auditing the
model implementation, not adding unsupported JSON parameters.
The trade threshold is15 for small,25 for large. At/above it, imports and
revenue are zero, domestic price35, consumption=production=50. A large-case
foreign offer of10 is then a marginal supply reservation, not a transaction.
The border_transaction_price field is null when there are no imports.
Surplus requires the chapter's quasilinear numeraire, ownership and no-other-
wedge assumptions. Home totals count consumer/producer surplus and tariff
revenue once. The separate resource ledger subtracts foreign payments once.
Large-case foreign surplus uses the specified competitive export producers'
cost10M+M^2/12; small-case foreign welfare is not supplied by that model.
No retaliation, administration costs, taxes elsewhere or political weights.

Firm case: name,A,b,F,c,tau. A,b,F,c strictly positive; tau>=1.
Residual inverse demand is max(A-b*q,0). q is delivered units; tau*q units
are produced. A and c are dollar/unit quantities, b dollar/unit^2, F dollars.
F is an avoidable, real destination setup resource cost. Costs are known and
other domestic activity/market conditions held fixed; no industry free-entry
or wage equilibrium is inferred. Optimal choices retain both0 and q* at exact
indifference. A no-export choice has null actual price, not a sale at A.
Negative margins are checked before a square is used. Sunk-cost comparisons,
Ricardian world equilibrium, factor ownership transfers and real-shipping-cost
comparisons are taught and checked separately in the chapter/checker; this
small lab does not purport to implement those additional models.

Output exact rational quantities are strings (integers also appear as "20").
Names/statuses remain text and absent transaction prices remain null. This
avoids rounding away an exact cutoff or substituting a negative import value.

Suggested investigation
-----------------------
Predict the two tariff thresholds before running. Reconcile both expressions
for home welfare. Test t=50/7 in the large case, then raise t beyond25: explain
why the quadratic positive-trade formula no longer applies. For firms, vary
only tau, then vary demand too; distinguish conditional effects from an
economy-wide prediction. Compare F64 at the exact cutoff with F65. Do not
interpret the revenue ledger as resource creation or the exporter cutoff as
evidence that exporting caused learning.

Verification
------------
The repository's scripts/check_v06_c10.py independently solves tariff prices
from market balance, checks primitive benefit/cost ledgers, enumerates global
firm candidates, checks boundary/malformed cases and audits the chapter's
Ricardian, factor, compensation and exercise results. Finite computations
supplement the analytic proofs. Browser/mobile/print visual QA is separate.
