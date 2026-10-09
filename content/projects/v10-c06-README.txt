LINDEN FINITE OPTIONS LABORATORY — Volume 10, Chapter 6

Purpose and provenance
All contracts, numerical inputs and problems are original synthetic teaching
cases. No input is an observed price, empirical estimate, exchange specification,
or licensed dataset. Values are in fictional currency units (CU); one option
covers one share. Period lengths are unspecified: gross_rate is per model
period, not an annualized rate. The lab implements a finite exercise grid.
It does not calibrate a continuous market or determine an optimal hedge with
transaction costs. Read the chapter's assumptions and proofs with the output.

Files and execution
Download these five files into one folder:
  v10-c06-inputs.json       exact contracts and parameters
  v10-c06-analysis.py       standard-library Python implementation
  v10-c06-output.json       complete reference result for supplied inputs
  v10-c06-README.txt        this contract and run guide
  v10-c06-manifest.json     SHA256 and byte lengths for the other four files

No installation, network, credentials, random generator or external dataset is
required. Use Python 3.9 or later. From that folder:
  python3 v10-c06-analysis.py
  python3 v10-c06-analysis.py --input v10-c06-inputs.json --output result.json

The input default is relative to the script, so an absolute script path also
works from another working directory. Explicit relative --input/--output paths
are relative to the current working directory. --output overwrites that chosen
file only after input validation and computation succeed. It produces no stdout
on success. Without --output, the result goes to stdout. Invalid input raises
an error and the process exits nonzero; do not use a preexisting output after a
failed run. Optimized Python (-O) retains validation. API users may load the
module and call run(data); importing and run are quiet, do not mutate data, and
return a JSON-safe dictionary. The main script is not imported by the independent
checker for its pricing formula: the checker constructs its own cash equations.

Review scope
The source repository also contains scripts/check_v10_c06.py and separate review
records. The downloadable five-file package runs without them. A matching digest
detects changes relative to the manifest; it is not mathematical certification
or proof of provenance. Exact fractions avoid rounding of this finite model,
but do not remove modeling error, missing rights or incorrect exercise timing.

Strict input schema
The top-level object has exactly these fields: schema, contract, tree,
negative_rate_call, dividend_call. schema is the JSON integer 1 (not true or 1.0).
The supplied contract string must remain byte-for-byte unchanged. Extra or
missing fields are rejected. Duplicate JSON keys and nonfinite JSON tokens
(NaN, Infinity, -Infinity) are rejected by the command-line loader.

Financial numbers are strings, never JSON numbers or booleans. Accepted syntax:
an optional minus sign; one to eight digits; optionally either a decimal point
with one to eight fractional digits or a slash and a positive denominator of
one to eight digits beginning 1–9. Examples: "80", "1.05", "21/20", "-0.02".
No exponent, whitespace, plus sign, leading decimal point or zero denominator.
After syntax validation each value is converted to fractions.Fraction exactly.
Domain bounds below apply in addition to those syntax limits. Dates, period
counts and path indices in outputs are integers. Financial outputs, including
zero, are rational strings; a fraction with denominator one prints as "0" or
another integer string. Labels and action strings are not numeric fields.

tree has exactly:
  spot: positive, at most 10000 CU
  strike: from 0 to 10000 CU inclusive
  down, gross_rate, up: 1/10 <= down < gross_rate < up <= 3
  steps: a JSON integer from 1 to 6 inclusive; booleans/floats rejected
  physical_up: strictly between 0 and 1
  interior_rebalance_fee: from 0 to 1/10 inclusive

Both physical branches have positive support. Fractional shares, signed cash
and stock positions, short sales and common borrowing/lending rates are allowed.
Stock has no dividends in tree. down < gross_rate < up makes both state prices
strictly positive. Endpoints are deliberately rejected because with two distinct
possible branches they allow arbitrage. The collinear case up=down=gross_rate
needs a different spanning analysis. Clipping q is never used as a repair.
physical_up describes independent physical branch weights only; it does not
enter claim prices when stock/cash parameters are fixed. Changing it leaves
the Q prices, portfolios and exercise decisions unchanged.

negative_rate_call has exactly spot, strike, up, down, gross_rate with the
same one-period stock/strike/branch bounds, and additionally gross_rate < 1.
It is a separate one-period no-dividend market. The output includes puts as
well as calls to check parity and the exercise comparison. A negative rate
alone does not imply immediate call exercise for every possible strike/state.

dividend_call has exactly contract, spot, strike, ex_up, ex_down, cash_dividend,
gross_rate. Its supplied contract string must remain unchanged. Bounds:
  0 < spot <= 10000; 0 <= strike <= 10000; 0 <= cash_dividend <= 10000
  0 < ex_down < ex_up <= 30000; 1/10 <= gross_rate <= 3
  ex_down + cash_dividend < gross_rate*spot < ex_up + cash_dividend
This is one period. A stockholder receives the known dividend immediately before
the terminal ex-dividend stock/option settlement. An option holder may exercise
now or after that dividend; there is no intervening pre-dividend exercise date.
Stock hedge receipts include both ex-dividend stock and the dividend. Option
terminal payoffs depend on the ex-dividend stock alone. Changing this clock
changes the claim and requires another model; it is not a hidden input switch.

Output map
single_step uses tree parameters but one period, matching Worked example 1.
tree uses the declared number of periods. negative_rate_case uses its own
one-period parameters. Each of these objects includes:
  q_up = (gross_rate-down)/(up-down)
  stock: rows by date, each ordered by increasing number of up moves
  contracts: call_european, put_european, call_american_grid, put_american_grid
  european_parity_lhs, european_parity_rhs, american_put_premium

At nonterminal date t, row index j denotes j up moves and stock
spot*up**j*down**(t-j). For these plain options that state suffices; a
path-dependent contract might require more history. Each contract node reports
stock, intrinsic, continuation, value, action, continuation_delta,
continuation_bank, exercise_value_less_continuation, cash_above_continuation_cost,
down_replication_residual and up_replication_residual. delta is shares held;
bank is CU in cash now (negative means debt). Continuation portfolios pay the
next node's option value in either state; both residuals should be exactly zero.
European value equals continuation. Grid-exercise value is the larger of
intrinsic and continuation. Strictly greater intrinsic triggers "exercise";
ties choose "continue" without changing value. At terminal nodes action is
"settle" and stock, intrinsic and value are the only numerical fields.
Cash above continuation cost is a surplus available if the holder continues
at a node where exercising would be better. It is not a cash injection.

path_reports.paths enumerates all 2**steps ordered D/U histories, including
different histories ending at the same terminal stock. pricing_probability
uses q; physical_probability uses physical_up. Each european_call_ledger row
shows the date, stock, inherited shares, inherited cash after interest,
pre_trade_wealth and model call_value. At an interior node it also reports
the new ideal delta/bank, stock_trade_cash, bank_change, external_cash_required
and intervention_fee. The ideal stock trade plus cash change is zero. At
maturity, payoff and exact_hedge_error reconcile the costless strategy.

The fee intervention follows the SAME ideal shares with a separate cash
account. At interior dates only, it charges interior_rebalance_fee times the
absolute stock_trade_cash. Fees are borrowed or reduce cash and accumulate
at the model cash return. There are no opening/closing fees, no cash-trade fee,
and no external injections. fee_intervention_hedge_error at maturity is minus
the sum of all interior fees accumulated from each payment date. This is a
funded experiment on a fixed strategy, not a frictional option-price formula.

american_grid_optimal_stopping gives each call/put policy's first exercise
date, stock, receipt and discounted_receipt along the full path (or terminal
settlement). Decisions use observed history only. The displayed paths retain
future labels for audit; those labels are not known by the exercise policy.
optimal_stopping_discounted_pricing_expectations must equal the root grid
prices. european_call_physical_expected_payoff is an UNDISCOUNTED physical
expectation, not a price. Divide it by gross_rate**steps only if making the
particular physical discounted-expectation comparison in Exercise 6.

dividend_case reports q_up_total_gain, dividend_pv, prepaid_terminal_stock,
European parity and call/put contracts. Those contracts contain down/up
payoffs, delta/bank, european_value, immediate_exercise, american_grid_value,
action and both hedge residuals. Delta stock receipts include the known
dividend; the bank is financed at the stated one-period gross rate. The
exercise comparison is only for the two authorized decision dates.

Reference anchors and transfer work
The supplied one-step call costs 72/7 with delta9/20 and bank-180/7; the
two-period European call costs 688/49, delta43/70 and bank-1720/49. Its put
costs 3712/441; the grid put costs 208/21 and exercises after a first down
move. The two-period call's fee errors are -387/1000 after D and -129/500
after U. The negative-rate call costs 900/49 European and 20 on its exercise
grid. The dividend call costs 2000/153 European and 20 on its exercise grid.

Make one financial intervention at a time, save it under a new input filename,
predict which cash equations change, and explain the output:
1. Change physical_up to "1/4": physical expectation changes but hedges do not.
2. Change interior_rebalance_fee to "0": every fee error becomes exactly zero.
3. Change tree strike to "88": solve the put exercise policy independently.
4. Change steps to 1: no interior rebalancing exists, so this fee is never paid.
5. Set strike to "0" or a value above all terminal stock prices; explain
   boundary payoffs rather than assume every option price is strictly positive.
6. Set tree gross_rate equal to down: confirm rejection, then construct the
   stock/loan arbitrage. Do not alter the code to admit or clip this case.

Limits
The model is finite and complete only for its stated trading rights and
histories. It omits random volatility, jumps between dates, funding asymmetry,
default, taxes, bid/ask spreads, integer positions, exercise frictions and
liquidity limits. A successful hedge on supplied paths establishes an algebraic
property of those paths, not a real-market guarantee. The code's finite domain
is an instructional resource bound, not a production resource-exhaustion audit.
The chapter's primary source notes document further reading on finite option
replication and stopping; they are not the source of these synthetic numbers.
