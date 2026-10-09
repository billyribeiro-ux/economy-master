V11 C05 — Liquidity, funding and asset-liability management
Original synthetic four-cutoff funding ledger and separate ALM/currency cases
Edition boundary: 6 October 2026. Package authored: 9 October 2026.

PURPOSE AND PROVENANCE

All inputs, institutions, event schedules and contract rates are original
teaching assumptions, not observed market data. The funding lab extends the
book's dated-cash and double-entry methods. The historical BCBS September 2008
liquidity principles supply method context, not current national law, facility
access, a regulatory liquidity ratio or a probability calibration. The April
2013 Acharya et al. credit-line manuscript is reused only for the established
point that access can depend on monitoring and conditions. Its optimal contract
is not implemented. See the chapter/source review for exact inspected scope.

REPRODUCTION

Place these four files in one directory:
  v11-c05-inputs.json
  v11-c05-analysis.py
  v11-c05-output.json
  v11-c05-README.txt
The companion v11-c05-manifest.json binds their bytes with SHA-256 hashes.

From that directory, with Python 3.9 or later and no external packages:
  python3 v11-c05-analysis.py --input v11-c05-inputs.json --output result.json
  python3 -O v11-c05-analysis.py --input v11-c05-inputs.json --output optimized.json

Both files must equal the saved output as parsed JSON (the implementation also
produces identical sorted, indented bytes). Input defaults to the sibling
v11-c05-inputs.json. Without --output the sole stdout content is the JSON report.
With --output successful execution is silent. Errors exit 2 with a short stderr
message and do not write the output. No network, clock, environment data, random
numbers, installation, import side effect or machine-specific path is used.

The quiet importable API is run(data), where data is a plain dictionary parsed
from JSON. It returns a fresh JSON-compatible object and never changes data.
All rational arithmetic uses fractions.Fraction, including present values and
derivatives. Output rationals are canonical strings such as "399/10" or "0".
Floats are not accepted as monetary/rate inputs. Rendering a decimal is the
reader's choice; the saved ledger does not round cash or boundary decisions.

CLI output is checked before reading/writing. It may not equal the input or
implementation by resolved path, a symbolic link or an existing hard-link alias.
Those rejection tests preserve all original bytes. Paths may otherwise point
outside the package. A successful --output explicitly replaces that destination.
The program does not claim protection against concurrent filesystem races.

In a repository checkout, the independent author checker is:
  python3 scripts/check_v11_c05.py
  python3 -O scripts/check_v11_c05.py
It also accepts --root PATH for an isolated copy of the exact nine author files
at their relative paths. check(root) is quiet and returns the summary object.
The checker independently calculates cutoff accounts from cumulative stock
equations, values bonds by discount recursion, checks numerical anchors and
targeted financial changes, and actually exercises API/CLI rejection cases.
It is not an independent human audit; separate peer/coordinator review follows.

UNITS, RIGHTS AND TIME

The main case is one legal entity and domestic CU, at exactly four ordered
cutoffs. Rates are explicitly per each interval 1→2, 2→3 and 3→4, not annual
market rates. At each cutoff all listed external receipts occur before payments.
There is no extra intra-bucket deadline, receipt requiring an unlisted payment,
automatic overdraft, collateral reuse, asset sale or emergency facility. A real
deadline inserted inside a bucket requires a finer grid and a new calculation.

Initial cash includes a fixed restricted amount. Securities have separate
eligible, already-pledged and inaccessible unit inventories. Only eligible units
secure the new loan. The latter two categories stay unavailable throughout the
window, even if a different liability is paid. All units remain owned and on the
book. A later mark values all units at the same stated scenario price; all other
accounts are explicitly valued at book for the reported marked-equity proxy.
This is not a complete loan credit/discount model or an accounting standard.

The optional upfront_cash_equity adds cash and equity before cutoff 1. It has no
interest, issuance cost, repayment, restriction or effect on any other policy.
The required minimum is for this lasting cash reserve and the fixed policy.
The chapter separately derives the changed constraints for a maturing bridge.

DETAILED FIXED POLICY AND ACCOUNTING

At cutoff 1:
* Take new term financing equal to old principal times rollover_fraction, even
  when a large upfront reserve would permit a smaller draw. The new financing
  matures at cutoff 4. Absence of refinancing never erases the old obligation.
* Initial secured advance per unit is initial_price*(1-initial_haircut).
  Draw min(secured_target, eligible_units*advance_per_unit), multiplied by the
  secured_offer_fraction. The fraction is amount available, not a probability.
  A target larger than capacity is a valid request with a capacity-limited draw.
* Repay old principal and its already-accrued interest payable. The latter
  payment is not recorded as a new expense.

At cutoff 2:
* Accrue one interval of secured interest on the principal outstanding before
  maintenance, plus one interval of new term interest.
* Reset collateral to the stated maintenance price and haircut. First use the
  eligible pool. Remaining principal is min(initial_draw, new_pool_capacity);
  pay down the difference. Pledged units become remaining_principal/new_advance.
  If capacity improves, excess collateral may be released under this contract.
  Only principal is collateral-tested; interest is separately payable.
* The customer draws customer_line_draw, up to the specified commitment limit.
  Cash falls and loans rise. This new loan repays after the modeled window.

At cutoffs 3 and 4 accrue interval interest on the remaining secured principal
and the unchanged new term principal. At cutoff 4 repay both principal amounts
and all new funding interest, close the derivative and receive all initial
margin back before debt repayment. New collateral is released after the secured
debt is paid; it is not reused to finance that payment.

At every cutoff:
* Contractual loan principal received reduces opening loans; it is not income.
  Receipts never include repayment of the new customer-line advance.
* Deposit withdrawal reduces cash and deposits. Other liability payment reduces
  cash and the corresponding liability.
* A signed variation_settlement changes cash and equity by that amount. This
  toy derivative resets its remaining value to zero after each cash settlement.
  No separate derivative mark remains to be added a second time.
* initial_margin_targets specifies the segregated asset AFTER the cutoff. The
  change is matched by opposite cash flow; neither posting nor return is profit.
  Margin earns no interest. It cannot be spent while segregated. Final target
  must be zero. Variation is settled from cash, not subtracted from that asset.

All events appear in journal with account changes, cash flow, equity change and
the exact assets = liabilities + equity check after each event. The rows give
cutoff snapshots and the inventory identity:
  total units = new pledged + free eligible + old pledged + inaccessible.

If a plan has a negative available-cash prefix, subsequent rows are a
FULL-PAYMENT DIAGNOSTIC, not an executable default/overdraft path. Even a negative
total cash account is possible in that diagnostic. It measures missing funds.
Provide the reported timely reserve before interpreting the whole path as
feasible. The model never supplies an unrecorded loan to hide the deficit.

FIXED-POLICY CERTIFICATE

For each scenario, cumulative usable cash equals initial cash minus restricted
cash plus all listed signed cash flows. Because the independent cash-equity
reserve b changes none of those flows, H_sj(b)=H_sj(0)+b. The exact common minimum
is max(0, max_sj(-H_sj(0))). Negative prefixes prove necessity; nonnegative prefixes
and the stipulated within-cutoff receipt order prove sufficiency. A zero
headroom is feasible in this model. No tolerance is used for that decision.

required_upfront_cash is the total reserve from the zero-reserve plan;
additional_cash_needed is max(0, required_upfront_cash - supplied_reserve).
binding_cutoffs lists the scenario/cutoff attaining a positive common minimum.
first_failure_cutoff and feasible_under_fixed_policy use the actually supplied
reserve. Financial failure is a valid result, not a malformed-data error.

This is a finite-scenario, fixed-policy cash minimum. It is not minimum funding
cost, a confidence level, a regulatory ratio, unlimited-horizon survival or
optimal contingent asset-liability management. Finite scenarios carry no
probabilities. Higher collateral marks do not make inaccessible units available.

INPUT CONTRACT — EXACT KEYS; NO OMITTED FIELDS OR SILENT COERCION

Root keys: schema_version (integer 1), opening, policy, scenarios, alm,
currency_case. Unknown/missing keys at every object level are rejected.

Rational fields must be strings matching an optional minus sign, an integer
without leading zeros, optionally a decimal fraction or /positive integer.
Scientific notation, whitespace, '+', booleans, JSON numbers, NaN and Infinity
are excluded. Maximum length is 32; reduced absolute numerator and denominator
are each <=10^12. Unless tightened below, nonnegative scalar monetary amounts
and units lie in [0,10^6]. Signed variation settlements lie in [-10^6,10^6].
These are computational bounds, not universal economic restrictions.

opening keys:
  cash, restricted_cash, loans, security_book_per_unit, eligible_units,
  already_pledged_units, inaccessible_units, initial_margin, deposits,
  legacy_principal, legacy_interest_payable, other_liabilities.
restricted_cash <= cash; security_book_per_unit is in [0,10]; total units <=10^6.
Derived opening book equity must be nonnegative in this lab family. This is an
input-family restriction, not a theorem that insolvent banks cannot have cash.
Zero units, principal, loans, deposits and margin are permitted when the related
flows satisfy the stated stock constraints. No nonexistent asset is invented.

policy keys:
  upfront_cash_equity, secured_target, initial_security_price, initial_haircut,
  secured_interval_rate, rollover_interval_rate, customer_line_limit.
initial_security_price in [0.01,10]; haircut in [0,0.95]; interval rates in
[0,0.1]. Funding negative-rate contracts are outside this particular ledger
family. Negative discount yields ARE supported in the separate ALM module.

scenarios: list of 1 to 8 plain objects with unique names, each matching
[a-z][a-z0-9_]{0,31}. Every scenario has exactly:
  name, rollover_fraction, secured_offer_fraction, maintenance_price,
  maintenance_haircut, loan_principal_receipts, deposit_withdrawals,
  other_liability_payments, customer_line_draw, variation_settlements,
  initial_margin_targets.
Both fractions are in [0,1]. Maintenance price is in [0.01,10], haircut in
[0,0.95]. The five vectors contain exactly four rational strings. All except
variation settlements are nonnegative. Total loan principal receipts <= opening
loans, total deposit withdrawals <= opening deposits and total other-liability
payments <= opening other liabilities. The customer-line draw is between zero
and its limit and occurs only at cutoff 2. Initial-margin targets are <=10^6
and the fourth is exactly zero. Other targets need not equal the initial margin:
a change at cutoff 1 generates the required posting or release.

alm keys:
  asset_face, asset_coupon_rate, asset_years, fixed_liability_face,
  fixed_liability_coupon_rate, liability_years, floating_liability_face, cash,
  base_yield, shock_yield.
Faces/cash in [0,10^6]; coupon rates in [0,0.2]; years are non-boolean integers
in [1,10]; annual yields in [-0.1,0.25]. Fixed bonds pay annual coupons and face
at maturity. The floating liability has the same maturity as the fixed
liability; all coupons reset to the scenario's flat annual yield with no floor,
spread or default. A negative yield therefore means a negative floating coupon.
Cash is unremunerated. The finite sums and derivatives use the same yield.
NII is next-year coupon interest only; face repayment is not interest income or
expense. This annual book is separate from the four-cutoff funding ledger.

currency_case keys:
  local_cash, payment_due, foreign_cash, cu_per_fu.
Amounts in [0,10^6]; conversion quote in [0.01,100] CU/FU. The output compares
three explicit contractual alternatives: no authorized transfer, authorized
timely transfer, and authorized late transfer. It does not infer a legal right
from the amount. A late receipt changes only the later balance, not the deadline
headroom. It is a separate entity/currency case, not main-ledger group netting.

CLI JSON files are limited to 100000 bytes. Duplicate JSON object keys and
nonfinite constants are rejected during parsing. Domain tests use explicit
exceptions, so Python -O cannot disable them. Ordinary I/O errors exit cleanly.

REFERENCE NUMBERS AND SELF-CHECKS

Opening equity: 24.6. Initial eligible pool: 50 units; capacity: 40; new draw:
30; pledged: 37.5; free: 12.5. The unavailable 20+10 units never supply new cash.

Scenario            Cutoff headrooms (CU)          Required reserve
base                 33.6, 38.6, 48.6, 27.1        0
rollover_failure     -6.4, -1.4,  8.6, 27.7        6.4
joint_stress        -13.4,-39.9,-29.9,  3.81      39.9

Joint collateral capacity: 24.5; paydown: 5.5; pledged units: 50; secured
interest: 0.79. Customer draw: new loan asset 12. Margin: extra posting 4,
final release 9. Net variation profit: 3. Closing unbuffered full-payment
diagnostic: cash 7.81, loans 92, securities 80; deposits 129, other liabilities
24, equity 26.81. Marking all securities at 0.7 gives marked equity 2.81.
Those diagnostic closing values do not cure the earlier cash failures.

With an upfront cash-equity reserve of 39.9, joint headrooms are 26.5,0,10,43.71;
all scenarios pass. An input of 39.89 fails joint cutoff 2 by exactly 0.01.
The bridge-loan exercise, which is not a separate run(data) input mode, gives
b in [39.9,190.5] for 2% horizon interest and no feasible b for 10%.

ALM at 5%: asset100, fixed liability80, floating20, EVE10, next-year NII0.
At 7%: asset96.3839636649, fixed liability73.4396841025, floating20,
EVE12.9442795625, NII-0.4. EVE derivative at5%:160.4170905666 CU/unit yield;
NII derivative:-20. Local 100bp EVE effect:1.6041709057 CU.
Currency case: potential converted cash10 CU; no/late transfer deadline
headroom-8; timely headroom2. Authorization and settlement are different facts.

MEANINGFUL EXTENSIONS

The supplied checker targets delayed receipts, restricted cash, collateral
delivery, haircuts, secured access, customer draws, margin, reserve equality,
capacity limits, zero stocks and negative/zero ALM yields. It verifies byte
preservation after direct/symbolic/hard-link overwrite rejection, strict JSON
parsing, quiet import/API, normal/-O equivalence and isolated execution.

This lab excludes endogenous bank runs, credit losses on the loan book,
intraday grids finer than the four cutoffs, rehypothecation, sale price impact,
multi-currency settlement mechanics, uncertain legal enforceability and optimal
funding choice. Such changes need specified rights and revised flows, not a new
label on the same scalar certificate. No empirical or regulatory claim follows
from passing this synthetic check.
