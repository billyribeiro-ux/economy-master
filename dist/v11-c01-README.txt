V11-C01: INFORMATION, INCENTIVES AND DATED BANK CASH
===================================================

This original synthetic teaching lab accompanies Financial intermediation and
bank economics. It contains four separate finite mechanisms: a screening
decision, a monitoring game, a two-bank origination/settlement ledger followed
by one bank's income ledger, and a three-date uninsured liquidity mutual.
They are not four simultaneous contracts of the same modeled bank.

No inputs are observed market data. All calibrations, utility choices, cases
and exercises were created for this chapter. No regulatory capital ratio,
deposit-insurance guarantee or accounting-standard compliance is claimed.

1. FILES AND REPRODUCTION

Keep these files in one directory:
  v11-c01-inputs.json       exact synthetic assumptions
  v11-c01-analysis.py       standard-library Python model
  v11-c01-output.json       saved exact result
  v11-c01-README.txt        this document
  v11-c01-manifest.json     SHA256 and byte count for the above four payloads

Use Python 3.9 or later. No packages, installation, network, randomness or
environment variables are required. From any working directory:

  python3 /path/v11-c01-analysis.py --input /path/v11-c01-inputs.json --output /path/result.json
  python3 -O /path/v11-c01-analysis.py --input /path/v11-c01-inputs.json --output /path/result-O.json

When arguments are omitted, input and output paths are resolved beside the
model file, not against the current working directory. Successful runs print
nothing. JSON output has a terminal newline. Invalid input exits with status
2 and a concise stderr message; validation is independent of Python asserts
and therefore remains active under -O. Input errors are detected before an
existing output is opened for writing. File-system failures can still prevent
a write; this small CLI is not a transactional database.
The output must not identify the input file or the executing implementation.
Resolved-path comparisons and existing-file identity checks reject direct,
relative, symbolic-link and hard-link aliases before reading or writing data.
Rejected calls preserve the input and implementation bytes.

API: load the module with importlib and call run(data). Import and run are
quiet, perform no file or network I/O, return a fresh JSON-compatible result,
and do not mutate data. Invalid API values raise ValueError. API callers
provide an already-decoded object; only the JSON loader can detect duplicate
keys in serialized JSON. Booleans are never accepted as numerical inputs.

The repository author checker is scripts/check_v11_c01.py. Its quiet check()
function returns a summary; executing that checker prints just the summary.
It independently reconstructs latent-state expectations, accounting journals,
monitoring action profiles and asset/liability/queue identities, and performs
portable normal/-O and input-domain checks. Passing it does not certify the
empirical assumptions or replace separate peer/coordinator review.

2. STRICT INPUT FORMAT AND GLOBAL LIMITS

The root object has exactly schema, screening, monitoring, bank and liquidity.
schema is exactly "v11-c01-inputs-1". Every nested object has exactly the keys
shown in the supplied input; unknown or missing keys are rejected. Every
financial quantity/probability is a string containing an ordinary decimal,
integer or rational fraction: "0.6", "3/5" and "100" are examples. Exponents,
leading/trailing spaces, plus signs, leading integer zeros (apart from zero
itself), negative denominators, empty strings and zero denominators are
rejected. A leading minus is syntactically possible but all input fields in
this lab have nonnegative economic domains, so negative values are rejected.
There is no floating-point input. The one exception to string numerics is
monitoring.claimants, an actual JSON integer.

Each numerical string has at most 32 characters. After rational reduction its
absolute numerator and denominator are each at most 1,000,000,000. All values
are at most 1,000,000 before any tighter field limits below. The input CLI
reads at most 65,537 bytes and rejects files larger than 65,536 bytes. JSON
duplicate keys, NaN and infinities are rejected. Output financial quantities
are reduced rational strings, not rounded numeric JSON tokens. Output flags
are booleans. Undefined conditional statistics and ratios are null.

These limits bound runtime: at most two screening branches, 1,000 conceptual
equal claimants (the model uses algebra, not simulation), fixed-length bank
journals and 16 requested withdrawal scenarios. No large integer or floating
point overflow is concealed as a financial result.

3. SCREENING DOMAIN AND TIMING

Fields good_prior, good_success, bad_success, good_pass and bad_pass are in
[0,1]. Signal and success are conditionally independent given quality.
The good/bad names label types; the model does not require one probability
ordering, and can handle an uninformative or reversed signal. principal is
strictly positive. failure_recovery is nonnegative and strictly below
success_repayment. principal, both repayments and test_cost are at most 1,000;
test_cost is nonnegative. No requirement that expected receipts cover principal
is imposed: loss-making lending policies are meaningful results.

All repayments occur at date 1; principal and the test cost are paid at date
0. Safe opportunity cost is zero; the decision maker is risk neutral and can
refuse finance for value zero. Testing is a pure information acquisition that
does not alter repayment/action laws. Every tested applicant incurs the cost,
including rejected applicants. Conditional lending is selected only for a
strictly positive margin; indifference means no loan. Choosing a test requires
a strictly higher net value than the best no-test policy; equal values choose
no test. This is a tie convention, not a theorem about unique choices.

Each branch reports its probability mass, good posterior, physical success
probability, expected receipt, margin and funding decision. For a zero-mass
branch the five conditional/funding fields are null except fund=false; no
posterior is invented. The reported funding threshold can lie outside [0,1]
when a principal/repayment configuration makes all loans attractive or none
attractive. Gross information value compares optimal conditional lending with
optimal untested lending/refusal; it is nonnegative. Net value can be negative.

Baseline: pooled receipt95, untested margin-5, pass mass14/25, posterior6/7,
pass receipt755/7, fail receipt865/11, fund only passes, gross conditional
value22/5, test cost3 and net7/5 per applicant. Cost22/5 gives indifference.

4. MONITORING DOMAIN AND THE COMMITMENT ASSUMPTION

principal is positive; success_cash is strictly greater than debt>=0.
0<=divert_success<prudent_success<=1. All these monetary fields and
private_benefit, audit_cost and delegation_cost lie in [0,1000], with the
stated strict inequalities. claimants is an integer from 1 through 1,000.
The project has zero recovery in failure. The borrower receives success_cash
minus debt on success; diversion adds private utility benefit, not creditor
cash. At an unmonitored borrower tie, prudence is selected.

One enforcement/audit purchase removes the private benefit before the action
choice. The low-success action then loses to prudence because the residual
is positive and prudent_success is strictly higher. This is a specified
enforcement power, not merely an information report. Its effects are public
to all equal claimants, and duplicates add no repayment benefit. The no-audit
Nash flag concerns the post-funding game given an existing loan. It does not
say the unmonitored project would be voluntarily financed initially.

The pooled vehicle raises principal+audit_cost+delegation_cost at date 0.
Completion is observable and payment conditional on it; this assumed
commitment technology is what makes enforcement credible. Expected debt cash
at date 1 is compared with the entire initial outlay at zero opportunity
cost. A negative largest_delegation_cost_for_nonnegative_surplus means even
zero delegation cost would be insufficient. The duplicate-audit comparison
assumes all N pay audit_cost and excludes the pooled completion-check cost.

Baseline: borrower18 versus20 without enforcement,18 versus12 after it;
loan receipt72 versus108. Each of12 claimants gains3 from paying5, so none
enforces. Pooled funding106 yields expected surplus2. Delegation cost3 is
the break-even threshold. Six claimants change the unilateral gain to6.

5. BANK DOMAIN, ACCOUNTING BOUNDARY AND PAYMENT CUTOFF

All bank fields are nonnegative rational strings <=1,000,000. Initial A and B
each require reserves+loans>deposits, so opening book equity is positive.
The external_payment is no larger than either A's opening reserves or the
new_loan: the modeled borrower spends only its new deposit, and settlement
has no implicit overdraft. immediate_withdrawal_probe cannot exceed A's
deposits after this settlement. direct_unprovided_loss cannot exceed its
then-recorded loans. During the later income continuation, available opening
cash plus the two external receipts must cover the two external payments.
With no opening loans after origination, interest_received must be zero; with
no opening deposits after settlement, interest_paid must be zero. No omitted
prior interest accrual is assumed to supply such a receipt or obligation.
An input requiring unmodeled later borrowing is rejected. By contrast, the
separate immediate probe may exceed cash; it reports the shortfall without
posting an impossible negative-reserve transaction.

Opening assets are reserves and loans only; liabilities are deposits only.
No taxes, securities, prior loan allowance or dividends are present. Loan
origination increases A loans/deposits. The external payment transfers
reserves from A to B and moves the same deposit amount. The first three
snapshots have an explicit two-bank consolidation; there are no other events
within that boundary. The immediate withdrawal probe occurs just after
external settlement, BEFORE every subsequent receipt and payment.

The next ledger is only for A, with outside counterparties. In order, it
records external interest receipt, external fee receipt, external interest
payment, external operating payment and a confirmed uncovered direct loan
loss. Cash amounts are recognized in income when paid/received in this toy
period. The final loss has NO prior allowance covering it and reduces loans
and equity without changing current cash. The model must not be used to
double-count an expense already provided through an allowance. B's earlier
ledger is not asserted to describe all counterparties to this continuation.

Closing equity may be zero or negative; this is reported, not rejected.
Ratios use explicitly chosen arithmetic means of opening/closing book
balances over the one-year continuation. NIM divides net interest income by
average loans; ROA divides profit by average assets; ROE divides profit by
average equity. A ratio with nonpositive denominator is null. Deposit funding
rate uses the unchanged opening deposit principal. Equity/assets is a simple
book ratio, not a risk-weighted regulatory capital measure. None of these
ratios proves that cash is available for a payment.

Baseline: A (R,L,D,E)=(24,126,132,18); after loan36 and payment24 it is
(0,162,144,18). System reserves stay40, while deposits rise204->240 on the
loan and are unchanged by the payment. The immediate request5 fails by5.
The later receipts10+2 and costs1.5+3.5 leave cash7. Direct loss5 leaves
loans157, equity20, profit2. NIM17/319, ROA2/163, ROE2/19. Final cash7 could
fund a NEW later5 request; it cannot settle the earlier missed deadline.

6. LIQUIDITY DOMAIN AND RIGHTS

initial_fund lies in (0,1000000]; it denotes both asset units invested and
the mass of one-unit initial depositors. early_fraction is in [.01,.99].
liquidation_return ell lies in [.1,1], maturity_return R in (1,3], and
ell<early_claim<R. utility_shift lies in [.001,1]. withdrawal_fractions is a
list of 1..16 strictly increasing rational strings between early_fraction
and1, inclusive. Fractions need not include the no-run or full-run points;
those are always evaluated separately. These are support limits for the
specified contract, not economic claims outside it.

The continuum population has exactly the specified early-type fraction;
types are private at date1. Early types consume only at1, late types only at2,
and late types can privately store an early withdrawal at gross return1.
There is no borrowing, asset resale, deposit insurance, suspension or partial
withdrawal choice. The long asset has a certain payoff: liquidate at1 for ell
or retain to2 for R. The mutual liquidates only to service early requests.
Requesters are placed in a type-blind random queue AFTER deciding to request;
each has a uniform rank in the requester mass. Full early claims are paid
sequentially until exhaustion, not pro rata to everyone. Waiting claimants
share remaining terminal proceeds. A single claimant is atomless and does
not change aggregate requests when deviating.

For requested fraction w, service probability is min(1,ell/(w*early_claim)).
Utility is u(c)=-1/(c+utility_shift), so utility at zero is finite. The output
computes the lottery's expected utility, not utility of expected cash.
Remaining long assets and waiter mass determine terminal payment per waiter.
At w=1 the average is null because there are no waiters; the separate
full_run_wait_deviation_consumption is zero because others exhaust the fund.

The output distinguishes whether the proposed early-only behavior can pay
all early claims from whether late types prefer to wait. Both are needed for
the candidate no-run equilibrium. The program permits parameter choices
failing either condition. The full-run equilibrium is conditional on deposits
already made and on the above rights; it is not a date0 participation or
equilibrium-selection theorem. direct_all_long_expected_utility is the direct
holding benchmark. At the baseline ell=1 it is an autarky optimum given the
stated no-trade alternatives. At ell<1 a date0 liquid-storage allocation must
also be optimized before describing a best available autarky option.

Baseline: fund100, early mass25, early claim1.1, ell1, R1.5, shift.1.
Early-only withdrawal liquidates27.5, retains72.5 and pays1.45 to each late
claimant. EU=-515/744 versus direct-all-long -245/352, gain125/32736.
Late indifference occurs at withdrawals8/11, capacity at10/11. Full-run
service probability10/11 gives EU=-5/3 versus -10 for a waiting deviation.

7. INTERPRETATION AND EVIDENCE

Screening uses physical repayment beliefs and risk-neutral choice, not
risk-neutral asset-pricing probabilities. The bank ledger is accounting with
dated cash, not an estimated solvency or liquidity forecast. The mutual's
run follows from the specified game, not a measured probability of a run.
All outputs are exact within finite rational assumptions; precision cannot
establish test validity, enforceability, asset recovery, funding availability
or actual depositor behavior. The chapter's source records state the exact
primary-body sections inspected and exclude contemporary policy claims.
