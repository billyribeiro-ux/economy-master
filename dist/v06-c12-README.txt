V06-C12: Crisis accounts and conditional policy feasibility
Original synthetic instructional cases; no observed-country calibration.
Edition boundary: 2026-10-06. Package authored: 2026-10-08.

FILES AND RUNNING
Keep v06-c12-analysis.py and v06-c12-inputs.json together.
Run: python3 v06-c12-analysis.py
Or:  python3 /absolute/path/v06-c12-analysis.py
The default input path is relative to the script, not the current directory.
Optional input: python3 v06-c12-analysis.py path/to/revised-inputs.json
Standard-library Python 3 only. No network, installations, random draws or
writes to the input. Success prints one JSON object and exits 0. Contract errors
print one JSON error object and exit 2. Python -O preserves explicit validation.
Importing the module is quiet; run(raw) validates and returns JSON-compatible
results. Low-level calculation functions take already-validated Fractions.

INPUT CONTRACT
Exact keys shown in the supplied input are required; no extra fields. Numeric
values must be JSON integers (not booleans) or finite decimal strings, with at
most 9 places, at most 32 characters and absolute magnitude <= 1000000. Binary
JSON floats, exponent notation, NaN and Infinity are rejected, not rounded.
This lexical contract makes decimal-to-rational conversion unambiguous. Each
collateral list has 1 to 20 unique simple IDs. Input files are <= 100000 bytes;
duplicate JSON keys are errors. All input constraints appear in validate().
Bank: 0 <= cash < withdrawal <= deposits, face > 0, opening book equity >= 0;
0 < sale price <= 1 and enough face units to meet withdrawals; recovery between
0 and face, with cash + recovery <= deposits; nonnegative injection. Fixed sale price is used ONLY in full-pay
state. Bridge and deposit interest are zero. Bridge has first priority.
Collateral: positive units, nonnegative debt and impact, 0 < LTV < 1, price
intercept > impact*units (strictly positive price throughout the sale domain).
All units sell at one clearing price. Sale proceeds immediately repay debt;
negative debt is forbidden. This is a separate asset holder, not the bank.
FX: nonnegative quantities/rate and positive H/F quotes. All flows take place
after the opening positions are revalued at the new quote. Old principal all
matures; no other assets, liabilities, income, transfers, capital account,
other volume changes or statistical discrepancy. Cash availability is pooled
by assumption; actual sector access is not inferred from national totals.
Fiscal: gross rate at least 1, nonnegative debt/cash/private cap, signed primary
surpluses allowed. Baseline issuance must be nonnegative in this borrowing-only
lab. Cash earns zero until date 1; it is then exhausted. All old debt matures at
1; all new debt at 2. No further borrowing at 2. No fiscal behavioral response.

OUTPUTS AND ORIGINAL BENCHMARKS
Every rational value is a JSON string, e.g. "400/9" or "-73/10". A negative
terminal residual stays negative. Booleans report feasibility separately.
Bank: gap 30; face sold 40; sale equity 10; full-pay bridge equity 20;
bad-state equity -10; bad creditor shortfall 10; public injection 15 gives
terminal residual/public recovery 5 and no creditor shortfall. Cancelling old
shares does not remove the -10 asset-minus-liability deficit.
Collateral: minimum sales 400/9 and 100; third branch has no repair because
its exact global maximum is 289/4 at x=25, below debt 80. Positive price and
nonnegative debt must both hold at a transaction. A non-exact crossing is
bracketed using 80 bisections on the increasing part of the exact quadratic.
H(lower)<debt<=H(upper), width <= units/2^80; an exact equality may stop early.
The upper endpoint separately reports its debt check: a numerical bracket
is not authorization to over-repay a debt. No-repair results have null minimum.
FX: official funding required 27/2 F; closing reserves 4 F, debt 27/2 F;
CA=FA=51/2 H; valuation=-18 H; NFA -36 -> -57/2 H; residual zero.
Sovereign baseline: issuance 78, immediate gap 8, terminal cash 21/5.
Linked support: issuance 93, gap 23, terminal cash -73/10 (shortfall 73/10).
Date-1 claim value 50/11; transfer 115/11; primary surplus -71/11;
stock-flow adjustment -16/11. Statistical classification is an illustrative
fair-value/transfer split of a certain payoff, not a claim every real rescue
uses that split. Valuation and the full cash financing are kept separate.

LINKED STRESS TASK
Copy inputs; change FX private_new to 8, bank bad_recovery to 65, fiscal
primary_2 to 100. Required official FX becomes 11/2 F. Bank recovery after
support becomes zero. Fiscal rescue recovery is automatically taken from
that bank residual, so it is 0 rather than the stale 5; terminal fiscal cash
is -23/10 H. Baseline fiscal cash is 71/5. These are separate scenarios with
one explicit bank-to-government link, not four overlapping losses to add.
If a changed bank still cannot pay creditors after injection, the package
reports its shortfall and fiscal.supported_bank_pays_creditors_in_full=false.
A public recovery of zero must not be read as successful creditor protection.

INTERPRETATION AND REVIEW
No official loan, private sale, legal power or tax change is guaranteed merely
because an amount is calculated. No probability or welfare ranking is supplied.
The chapter's eight exercises include separate exact references and uncertainty
criteria. Independent repository checker: python3 scripts/check_v06_c12.py
from the book directory. It recomputes identities, global certificates, all
exercise arithmetic, portable CLI/optimization behavior and malformed-input
rejection; it is not external empirical or legal validation. Visual/mobile/print
browser QA is pending. Source records separately scope historical inspection.
