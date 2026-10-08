V08-C09 — original acquisition economics lab

Save v08-c09-analysis.py, v08-c09-inputs.json, v08-c09-output.json and this file
in one directory. Run:
  python3 v08-c09-analysis.py
An optional first argument names another JSON input file. No network, packages,
market data, credentials or file writes are needed. The printed result matches
the supplied output. Importing the module is quiet; analyze(data) returns a
strict JSON-compatible dictionary. Decimal/fraction strings are exact, and
financial output is expressed as exact rational strings. The manuscript alone
rounds displayed decimals. Share counts are thousands, money is kCU, and price
is CU per share. Ratios and probabilities are fractions of one.

All firms, contracts, values, receipts and probabilities are author-created
teaching inputs. They are not October 2026 market observations. Main-case T0 is
simultaneous closing, and T1/T2/T3 are subsequent year-ends. Both cash balances
are accessible excess cash. Target debt is retired at its supplied market value;
buyer debt and both preferred claims remain at unchanged fair values. Target
common shares are exchanged and canceled in the stock case. The initial-capital,
integration and fee outlays occur once, in closing uses. Only future integration
remains in postfunding operating value. The same net value is also reconstructed
from the pre-closing surplus and standalone equity, without double counting.

Cash taxes are supplied directly. There is no extra capital deduction, interest
tax shield, NCI, lease, nonoperating investment or omitted working-capital cost.
Dedicated capital and incremental benefits have no residual after the finite
opportunity. A one-year delay scenario moves only combination benefits and their
taxes; it does not move control gains, investment or integration payments.

The realization experiment scales only buyer-specific gross benefits and their
cash taxes from zero to full realization. Fixed costs remain payable. Borrowing
proceeds equal the new debt's value, with zero incremental financing side effects
beyond the stated fee. Operating values and remaining old claims are supplied
as unchanged across these funding alternatives. Debt-commitment feasibility is
reported separately from positive economic NPV. These assumptions are not an
argument that real funding, creditor prices or taxes are invariant.

The EPS and signing illustrations are separate cases. EPS uses a beginning-year
close, full-year supplied common income and no additional accounting adjustment.
Signing uses a stipulated linear owner criterion with physical probabilities
and a 5% discount, not a market-pricing theorem. Failure costs go to outsiders;
interparty transfers would cancel in the combined investor reconciliation.

Domain of this intentionally small lab:
- Positive standalone common equity and shares; nonnegative supplied asset,
  claim and cost levels; rates greater than -1; chronological, unique positive
  integer cash dates; nonnegative net control/combination receipts.
- All listed cash is used at closing. Non-consideration uses must be at least
  available cash, so the stock case has nonnegative borrowing and zero remaining
  excess cash. Cases with unused cash need an amended closing model.
- Positive combined common equity and buyer standalone equity plus S, and
  nonnegative cash-deal common equity. Distress/claim repricing is not modeled.
- The fixed-value equivalent requires 0 <= consideration < combined equity.
- Realization fractions and signing probability lie in [0,1]; endpoints are
  valid. The signing buyer success/failure spread must be positive for its
  displayed probability threshold. A threshold above one is allowed and means
  no probability in [0,1] meets the buyer criterion.
- Negative S is permitted within those claim domains. It yields no mutually
  acceptable stock interval and need not be hidden by a forced positive result.
- The borrowing commitment can bind: infeasibility is an output, not a reason
  to alter the supplied cash offer or assume missing financing into existence.

Meaningful uses: change the cash offer, fixed exchange ratio, commitment,
realization fraction or signing probability and reconcile sources/uses, all
surviving claims and both shareholder gains. Values, cash-flow evidence and
contract enforceability still require independent substantive judgment.
The associated repository checker independently reconstructs exact balances,
derivations and all eight determinate exercise answers; it is not external
academic certification, empirical due diligence or UI/print validation.
