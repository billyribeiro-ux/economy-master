V11 C02 — Alder Bank ledger, capital and dated liquidity
Edition: 9 October 2026. Original synthetic teaching case; amounts in CU.

Purpose
-------
Reconcile double-entry book accounts, income and the allowance; compare a
separately stipulated economic valuation; compute precisely defined toy capital
ratios; and test whether cash is available at every payment cutoff. Positive
equity, an allowance balance and a later receipt are not interchangeable with
cash usable now. This is not a regulatory return, loan-loss estimation model,
legal solvency opinion or real bank forecast.

Files and reproducibility
-------------------------
v11-c02-inputs.json is the original synthetic input. No external data, network,
packages, credentials or prices are needed. v11-c02-analysis.py uses only the
Python 3 standard library. v11-c02-output.json is the saved BASE case with no
repair. The manifest binds the input, model, output and this guide by SHA256 and
bytes. Those hashes establish file identity, not economic validity.

From this downloaded directory:
  python3 v11-c02-analysis.py v11-c02-inputs.json
  python3 -O v11-c02-analysis.py v11-c02-inputs.json
  python3 v11-c02-analysis.py v11-c02-inputs.json --output my-result.json

With no input argument, the model uses the input beside its own file, regardless
of the current working directory. The positional input and --output can also be
absolute paths. The CLI prints only strict JSON on success unless --output was
specified. Invalid input returns code 2 with an error on stderr.
Output paths may not overwrite the input or implementation, including resolved
symbolic links and existing hard-link aliases. Import the
hyphenated filename using importlib.util.spec_from_file_location; run(data)
returns a JSON-safe dict quietly and does not mutate the supplied dict. Financial
validation raises ValueError and remains active under python3 -O. Monetary
arithmetic uses exact Fraction values parsed from decimal spellings. Output
numbers are rounded to twelve decimal places, so extremely small differences
can be hidden by output rounding. Gate booleans use unrounded exact values.
An extreme ratio outside finite float output range is rejected with ValueError
rather than returned as a nonfinite JSON value.

The source-tree author checker scripts/check_v11_c02.py supplies a quiet check()
API. It independently reconstructs journal entries as account-change vectors,
values balances directly and computes cash headrooms from cumulative flows;
it does not call the model's arithmetic helpers as its oracle. It also changes
financial assumptions, rejects invalid inputs and verifies payload identities.
The checker needs all nine chapter-owned files in their original relative paths.
The model itself requires only its .py and input .json files.

Input contract
--------------
Unknown or missing fields are rejected at every object level. JSON booleans are
not numbers. Numbers must be finite int/float values; numeric strings, NaN and
Infinity are rejected. The CLI also rejects duplicate JSON keys and files over
200,000 bytes. Monetary fields are in [0,1,000,000], except opening equity may
be in [-1,000,000,1,000,000]. Bounds concern individual input fields, not a
calibration of realistic bank size. No accounting amount may become negative
in the posted journal except equity. Gross loans must cover the nonnegative
allowance throughout; this excludes negative-allowance and negative-net-loan
cases. Negative economic equity and projected payment gaps are valid results.

Top-level exact fields:
  schema_version: integer 1.
  provenance: nonempty text of at most 1,000 characters.
  opening: the eleven book accounts listed below.
  journal: 1–40 entries, each {id, kind, amount}; unique nonempty text IDs.
  valuation: six common-date marks listed below.
  instructional_capital: five toy policy parameters listed below.
  liquidity: six dated-funding fields listed below.
  repair: {kind, amount}, applied after the journal but before all cash cutoffs.

Opening accounts are cash, free_securities, pledged_securities, gross_loans,
allowance, property, goodwill, deposits, wholesale, other_liabilities, equity.
Securities are carried at stipulated book amounts. Assets equal cash plus both
security pools plus gross loans minus allowance plus property plus goodwill.
Liabilities equal deposits plus wholesale plus other_liabilities. The opening
identity and every posted journal identity must balance exactly.

Journal kinds and their counter-entries for nonnegative amount a:
  originate_deposit: gross_loans +a, deposits +a.
  external_payment: cash -a, deposits -a.
  principal_collection: cash +a, gross_loans -a.
  cash_interest: cash +a, equity/income +a.
  deposit_interest: deposits +a, equity/income -a; credited, not paid externally.
  cash_expense: cash -a, equity/income -a.
  provision: allowance +a, equity/income -a; no cash movement.
  chargeoff: gross_loans -a, allowance -a; requires sufficient prior allowance.
  recovery: cash +a, allowance +a; no current recovery income in this ledger.
  dividend: cash -a, equity -a; a distribution, not income expense.
  allowance_release: allowance -a, equity/income +a; a separate reassessment.

Recoveries concern previously written-off claims whose legitimacy is stipulated;
the bounded model does not reconstruct their historical off-balance-sheet pool.
All cash collections cross the bank boundary. A transfer between two customers
of this same bank needs no aggregate journal entry. Taxes, OCI, accrued interest,
off-balance-sheet commitments, new default probabilities and accounting-standard
classification decisions are not implemented. The allowance is not set-aside
cash. The nonnegative-allowance boundary is not a universal accounting claim.

valuation fields: free_security_value, pledged_security_value, loan_value,
severe_loan_value, property_value, goodwill_value. Each value is stipulated at
the post-journal date. The complete loan-portfolio PV includes its own credit
assumptions: the book allowance is not deducted again. In this bounded asset
inventory, zero security-pool, property or goodwill book stock means that asset
is absent and cannot have a positive mark. Zero gross loans requires both loan
marks to be zero; zero net loans with surviving gross claims does not. A real
fully depreciated physical asset would need an expanded inventory. Liabilities
retain book values; there is no own-
credit gain or unrecorded franchise value. The severe case changes only the
loan mark, not book accounts or cash. The model does not infer these marks.

instructional_capital fields: loan_weight, security_weight and property_weight
each in [0,3]; risk_ratio_floor in [0,1]; leverage_floor in [0,1). Capital K is
equity minus goodwill, exposure U is total book assets minus goodwill, and toy
RWA is loan_weight*(gross_loans-allowance) + security_weight*(both security book
amounts) + property_weight*property. Cash has zero toy risk weight; goodwill is
deducted, not also weighted. K may be negative. All denominators must be positive.
The base weights 1/.2/1 and gates .06/.04 are fictional, not current regulatory
requirements. Minimum conversion amounts solve ratio inequalities only: actual
conversion also needs sufficient deposits excluded from the scheduled outflows.

liquidity fields: restricted_cash, haircut, draw_cutoff, repay_cutoff,
secured_gross, events. The restricted cash is unavailable for this entire
horizon and cannot exceed closing cash. Haircut is in [0,1]. The secured gross
repayment factor is in [.5,2], allowing an explicitly stipulated negative
financing rate. Draw and repay cutoffs are integers 1–12 with draw < repay; both
must appear among the 1–12 strictly increasing events. Event exact fields are
cutoff, loan_principal_in, deposits_out, wholesale_out, other_out. Each receipt
settles before that cutoff's payments. Aggregate scheduled principal cannot
exceed opening-of-forecast net loans; each liability repayment stream cannot
exceed the respective post-journal liability. No intra-cutoff timing is modeled.

The single committed secured facility draws its full (1-haircut) times the free
pool's market value. The entire free book pool is pledged from the draw through
repayment. It cannot simultaneously be sold or pledged again. The old pledged
pool is unavailable and remains pledged. New principal adds both cash and
wholesale debt; its repayment removes both. Only the financing interest changes
equity. Repayment releases the newly pledged pool. There are no intervening
margin calls, valuation changes or partial collateral releases in this plan.

repair kinds: none (amount must be zero), cash_equity (cash and equity rise),
deposit_conversion (deposits fall and equity rises; no cash), unsecured_borrow
(cash and wholesale debt rise; equity unchanged). Conversion is limited to
deposits NOT in the scheduled outflows. Any new unsecured repair matures after
the final modeled cutoff, with no in-horizon interest payment; later obligations
still exist. Every repair takes place before all cutoffs. These operations are
assumed authorized and available for illustration, not verified in practice.

Output interpretation and anchors
---------------------------------
Opening assets/liabilities/equity: 340/320/20.
Closing cash/gross loans/allowance/deposits/equity: 34.5/242/5/266/13.5.
Closing assets/liabilities: 339.5/326. Income -4.5, dividends 2.
Allowance roll-forward: 8+6-10+1=5. Cash change: -5.5.
Complete economic assets/equity: 327.5/1.5; severe equity: -6.5.
Toy K/U/RWA: 11.5/337.5/255; risk ratio 4.509804%, leverage 3.407407%.
Minimum cash issue for both ratios: 3.8, with cash entering U as well as K.

The cash plan has usable initial cash 30, excluding restricted 4.5. Cutoff 1
principal10 and secured draw28.8 confront deposits50 + wholesale15 + other5
=70 ACTUAL due payments. That other5 already belongs to the opening/closing
other-liability balance10; it is not a new liability or a desired cash floor.
Base projected unrestricted headrooms: -1.2, 5.8, 1.712. Secured repayment at
cutoff3 is 29.088, including interest .288. First failure is cutoff1; the
executable prefix has zero cutoffs. Later positive projections cannot cure it.
Minimum up-front external cash for this fixed plan alone: 1.2.

Every forecast row gives projected_accounts_if_all_payments_made. After a first
failure, these are conditional diagnostic accounts, not records of executed
transactions. A negative unrestricted remainder means the stated payments
cannot all occur without extra funding or impermissibly using restricted cash.
The output does not treat a positive management target as a payment obligation.
If external cash arrives before every cutoff without changing other cash flows,
max(0, maximum prefix deficit) is necessary and sufficient within this model.

Cash equity3.8 gives ratios6% and4.4828597%; all headrooms2.6/9.6/5.512. After
all payments, cash10.012, gross loans195, allowance5, deposits211, wholesale35,
other liabilities5 and equity17.012 reconcile assets268.012 to liabilities251.
Stable-deposit conversion3.8 passes the toy ratios but leaves the cash failure.
New borrowing3.8 cures the three cash cutoffs but leaves both toy capital gates
failed. Neither action alone proves resilience outside the displayed horizon.

Suggested interventions
-----------------------
Change only the loan risk weight to .7: RWA183.9 and risk ratio6.2534%, with no
cash or economic-equity change and the leverage gate still failed. Move the
cutoff2 receipt12 into cutoff1: headrooms10.8/5.8/1.712, now feasible. Change the
haircut: cutoff1 requires h<=1/6, but the changed loan principal also changes
its later repayment. Test an additional supported allowance release, a fully
covered charge-off, a recovery and each repair separately. Account for every
counter-entry instead of altering output numbers. The chapter's alternative
sale exercise is solved separately; this bounded lab implements the secured-
facility plan, not a sale optimizer.

Evidence and limits
-------------------
Source records link the scoped 2013 Bank of England conceptual primer, US2020
interagency allowance statement and BCBS2008 liquidity principles. Their dates,
jurisdictions and inspection limits are in the chapter source proposals. The
synthetic figures do not come from those publications. Historical accounting
and regulatory thresholds are not represented as current law. Independent
calculation and machine-assisted review do not certify actual loan recovery,
market prices, legal collateral rights, investor access or human expertise.
