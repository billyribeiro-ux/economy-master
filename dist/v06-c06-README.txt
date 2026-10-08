Money, banking and monetary transmission — exact transaction fixture

Save v06-c06-ledger.py and this README in one folder. Run standard-library Python:

    python3 v06-c06-ledger.py

The script prints JSON. To save it, optionally run:

    python3 v06-c06-ledger.py > monetary-ledger.json

No internet, packages or input files are needed. Every quantity is an exact
fraction, represented as a JSON string: for example "49/5" means 9.8 currency
units. No currency conversion, annualization, interest accrual, fee, tax or
unlisted valuation change is implicit. The model is a fixed original synthetic
fixture, not a bank-data parser or a monetary-policy forecasting program.

Six sequential snapshots cover opening accounts, a loan of 40 at A, an interbank
reserve loan of 15 from B, the borrower's payment of 40 to B, a central-bank
advance of 15 to A, and repayment of A's interbank debt. The collateral rule for
the advance is a synthetic 25% haircut on A's securities worth 20. Collateral
remains A's pledged asset; the central bank records an advance, not an additional
copy of the collateral. Every journal has matching bank and central-bank reserve
accounts and matching interbank and central-bank loan counterparts.

Alternative branches DO NOT follow one another. Each starts from the final
sequential stage. They show principal repayment, a recognized credit loss, an
outright central-bank purchase from B, a purchase from a nonbank at B, and a
completed currency withdrawal. The two recapitalization alternatives each start
from the loss branch; neither is added to the other recapitalization.

The nonbank purchaser/subscriber has the required deposit or securities before
its transaction. Nonbank financial changes are described in the chapter;
nonbank and government complete balance sheets are outside this fixture.

Key references:
- Opening: bank deposits360, reserves50, public currency20; M380,H70.
- After new loan and payment: deposits400,reserves50; M420,H70.
- After central-bank advance/refinancing: deposits400,reserves65; M420,H85.
- Consolidated banks after refinancing: assets455 = deposits400+CBdebt15+equity40.
- Consolidated banks plus central bank: assets470 = deposits400+currency20+equity50.
- Repaying12 of principal: M408,H85; bank A equity remains20.
- Recognizing12 of loss without a payment: M420,H85; A equity falls to8.
- Buying20 from B: M420,H105; buying20 from its nonbank customer: M440,H105.

A and B separately satisfy assets=liabilities+equity. Consolidation of banks
cancels interbank claims. Adding the central bank also cancels reserves and its
advance. Government securities and public deposits remain because their
counterparties are outside this boundary. Equity is retained on the financing
side; it is not deleted as though it were a reserve account.

This fixture checks accounting consistency, not a behavioral optimum, current
regulatory compliance or economic solvency. Its positive equity balances do not
certify collectability of loans. Loss recognition and legal debt forgiveness are
different concepts. The current reserve quantity is not multiplied by a fixed
factor to predict new deposits or loans.
