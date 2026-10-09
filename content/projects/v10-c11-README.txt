V10-C11: EXACT INCOMPLETE-MARKET, PATH AND CREDIT LABORATORY
Original synthetic teaching data; no observed quotes, rates or default frequencies.
Standard-library Python 3 only. No installation, network or random seed required.

RUN FROM ANY DIRECTORY
  python3 /path/to/v10-c11-analysis.py --input /path/to/v10-c11-inputs.json --output /path/to/result.json
  python3 -O /path/to/v10-c11-analysis.py --input /path/to/v10-c11-inputs.json --output /path/to/result-O.json
With no --input, the script reads the input beside itself, not the working directory.
With no --output, the CLI emits only strict JSON on stdout. A valid --output call
is quiet. Invalid input exits 2 with a short stderr message before creating an
output. Duplicate JSON keys and NaN/Infinity JSON extensions are rejected. The
output parent must already exist; permissions and other output I/O failures remain
ordinary operating-system errors. There is no overwrite prompt for an explicit
--output destination; choose a scratch result path rather than a source payload.

API
Import by runpy.run_path or importlib and call run(data). Both import and run are
quiet. run validates the entire input, does not mutate it, uses no filesystem or
clock, and returns JSON-safe deterministic output. Validation uses exceptions,
not assert statements, so optimized Python preserves all domain checks.
The schema and every object have exact keys: unknown/missing keys are errors.
Values named id must match [a-z][a-z0-9_]{0,39}, unique within their own collection.

ECONOMY AND UNITS
Time is in years, stock and cash in fictional currency units, stock quantities
in shares, recovery/protection fractions dimensionless and premium_rate per year.
The bank has deterministic positive price B(t)=1/D(t), B(0)=1. A time-t cash
receipt C can be reinvested to C D(t)/D(T) at T; a payment can be funded by bank
borrowing. Rates may be negative: discounts need not decrease with time.
Only stock trades at 0 and T are permitted. Intermediate stock_path values are
contractual observations, NOT prices at which the program permits stock trading.
The stock has no dividends. No short-sale, borrowing or intermediate-solvency
constraints, costs, bid-ask spread or collateral requirements are modeled.
Every listed state has positive physical probability, but P is deliberately not
an input. Pricing measures have strictly positive probabilities and must satisfy
sum p=1 and E_Q[S_T]=spot/D(T). No statistical probability is converted into Q.

NUMBERS AND BOUNDED DOMAIN
A numeric field accepts an integer (excluding bool), a finite float interpreted
by its shortest decimal string, or a rational string such as "25/26" or "-3".
Strings use an optional leading minus, nonnegative integer numerator and positive
integer denominator; each component has at most 10 digits, no whitespace/plus/
leading zeros except the single zero. Total string length is at most 24. Reduced
absolute numerator and positive denominator must each be <=1,000,000,000. Float
and integer input absolute magnitude must also be <=1,000,000,000. Thus a very
small nonzero float or an overprecise decimal can be rejected by the rational
size limit. There are no approximate equality tolerances: calibration is exact.
All rational result values are canonical strings, even integers such as "100".
Integer state/date indices remain JSON integers; flags remain bool; unavailable
settlement dates are null. No NaN, Infinity, floating result or underflow occurs.
The external rational-input bounds constrain computation; they are not a claim
that all financially possible markets lie inside this teaching domain.

market has spot, times, discounts, states.
- 2..9 dates. times start at zero, strictly increase and stay in [0,10].
- One discount per date, each in [1/10,10], and discount[0]=1.
- spot and every stock_path mark are in [0,10000]. Each path has one mark per date
  and begins at spot. There are 2..8 states.
- Each state has id, stock_path, default_index, recovery, protection_fraction.
  default_index is null, or an integer index in 1..last. Booleans are rejected.
  Recovery and protection_fraction are in [0,1]. A no-default state must use 1
  for both neutral placeholders. Terminal stock values may repeat or equal zero.
- The forward must lie STRICTLY between minimum and maximum terminal stock.
  A zero-spot nonnegative nontrivial market is consequently excluded, as is a
  one-outcome stock. The model does not assert those are all impossible markets;
  they require separate degenerate handling outside this lab's contract.

contracts has strike, barrier, monitor_indices, average_indices, average_strike,
and credit. The two strikes are in [0,10000]. Barrier is in [1/1000000,10000].
Each observation list is nonempty and contains unique strictly increasing integer
indices in 1..last. Initial stock is excluded as an observation in this contract.
The no-rebate up-and-out call is zero if ANY selected stock mark is >=barrier.
The terminal-only comparison checks the last date regardless of monitor_indices.
Therefore the comparison is a nested-grid ordering only if last is actually in
the main list; the supplied input includes it. The arithmetic Asian equally
weights average_indices and then applies its own strike. It is not geometric.

credit has premium_indices, notional, premium_rate, settlement_delay.
- Premium dates are nonempty increasing indices in 1..last and MUST include last.
- Notional is in [1/1000000,1000000], premium rate in [0,1].
- settlement_delay is an integer number of listed-date steps in 0..(date_count-2).
  Every actual default index plus this delay must be at most last. A date-step
  delay is not a fixed year fraction on irregular grids.
- Reference default at a coupon date occurs BEFORE that scheduled coupon. The
  accrued premium equals elapsed time since the last strictly earlier coupon;
  at an exact coupon date this is a whole coupon, paid once as accrued premium.
- Full scheduled premium is paid only when default_index > coupon_index or null.
  Default accrued premium is paid at default, never at protection settlement.
- Protection = N(1-recovery)*protection_fraction, paid at default_index+delay.
  No reference default means no protection and all scheduled premiums are paid.
- This is a defined toy protection-haircut contract. The buyer is default-free
  and its premium obligation is unaffected by the seller's paid fraction. It is
  NOT a bilateral CVA/closeout/collateral/netting algorithm or current ISDA rule.
- Default at zero is excluded. Full accrual and strictly positive dates guarantee
  positive state annuities, needed for finite ratio bounds. A zero-annuity
  contract needs separate treatment and cannot be handled by dropping states.

measures is a list of 1..8 objects {id, probabilities}. Each probability list
has exactly one rational per state and is strictly positive, normalized and
stock-calibrated. Zero-probability boundary laws are rejected as user measures.
The closed laws enumerated internally are solely limiting optimization tools.

jump_cases is a list of 1..8 objects {id, spot, jump, scale}. Spot and post-jump
spot must be in [0,10000], jump in [-10000,10000], scale in [1/1000000,10000].
Each case uses f(S)=S^2/scale and the PRE-event derivative 2S/scale. It reports
claim change, stock-hedge gain and their difference J^2/scale. A zero jump and a
jump to zero are valid. This is an exact pointwise identity, not a jump-clock
simulation, option pricing model, frequency estimate or continuously rebalanced
hedging proof. A short-claim hedge's jump error has the opposite residual sign.

ALGORITHM AND OUTPUT
closed_pricing_vertices lists all unique nonnegative one- or two-state laws with
mean equal to the forward, in lexicographic probability order. Singleton laws
are included for any terminal stock exactly at the forward. Pairs of equal
terminal prices never divide by zero; their feasible singleton laws suffice.
This list generates the closed feasible probability polytope. Its arithmetic
average is strict_positive_baseline, with each coordinate positive.

claims contains call, up_out, terminal_only_up_out, asian, credit_net and stock.
Each records terminal_payoff, lower, upper, replicable, endpoints_open,
subhedge, superhedge and closed_vertex_prices. A hedge has stock_units, terminal
cash, initial cash, cost and state terminal_values. The model independently
checks equality of extremal expectations and optimal feasible affine hedges.
For a nonreplicable payoff lower and upper are excluded NO-ARBITRAGE endpoints,
not prices achieved by equivalent measures. For a replicable payoff the interval
collapses to an included singleton. The proof depends on the stated trading and
positive-state assumptions. Hedging line ties use deterministic slope/intercept
ordering; different optimal holdings can have the same correct cost.

The stock/cash hedge costs apply to terminal accumulated credit_net. They do not
guarantee separately positive cash balances at every intermediate payment date.
credit_state_ledgers lists each actual dated payment, its type and cash sign
(positive for protection buyer receipts). It also gives unit_annuity_pv in years,
protection_pv in currency, premium_pv and net_pv. No aggregate date replaces a
cash payment's own discount factor. quotes gives each chosen Q, state prices,
all claim prices and credit fair_spread=protection_pv/(notional*unit_annuity_pv).
fair_spread_bounds uses the positive-annuity convex-combination proof, with
explicit endpoint flags; it does not identify a statistical hazard rate.

SUPPLIED BENCHMARK
The two measures (.2,.4,.1,.3) and (.2,.1,.4,.3) have identical terminal stock
probabilities, so every terminal-stock-only payoff agrees. Call K90 prices are
250/13. The fine barrier prices are 50/13 and 25/26; Asian prices 275/26 and
425/26. Closed pricing laws are (0,0,.9,.1), (0,.9,0,.1), (.45,0,0,.55).
Call interval: (175/13,1375/52). Fine barrier: (0,225/26). Asian: (75/26,525/26).
The stock's included singleton is 100. Credit spread range is
(0,47277/165362). The reference outputs preserve full exact rational arithmetic.
These extreme synthetic default weights are teaching devices, not market quotes.

VERIFICATION AND MANIFEST
The adjacent manifest binds exactly inputs, model, output and this README by
byte length and SHA256. Repository script scripts/check_v10_c11.py is the author
checker; it is not needed to run the standalone package. It compares independent
rational market and cash-ledger oracles, exhaustive rational families, known
analytical bounds, economic interventions and invalid domains, validates the
manuscript's numerical displays and structure, and checks isolated default/
explicit CLI execution under normal and -O Python. It also verifies eight
nonself author-review hashes. The checker is quiet through check(), printing
only a JSON summary when run as a script. Separate peer and coordinator review
are additional gates. These checks do not establish empirical adequacy, current
contract terms or external human certification; browser/print QA is separate.
