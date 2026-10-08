Exchange rates and external balances — original synthetic lab (v06-c11)
Created 2026-10-08; textbook edition boundary 2026-10-06.

FILES AND RUNNING
Keep these four files together:
  v06-c11-cases.json       exact, documented synthetic inputs
  v06-c11-external.py      standard-library benchmark, Python 3
  v06-c11-output.json      preserved output from the default input
  v06-c11-README.txt       this file
Run from any working directory:
  python3 /path/to/v06-c11-external.py
Or provide a changed JSON input:
  python3 /path/to/v06-c11-external.py /path/to/changed.json
The default path resolves relative to the program, not the shell directory.
The program writes JSON to stdout; it does not modify input files or use a
network, framework, external package or random seed. Invalid input exits 2.

PROVENANCE AND CONVENTIONS
Every amount, probability and coefficient is author-created. These are not
observed releases, empirical estimates, trading recommendations or forecasts.
All numeric inputs are integer/rational strings, such as "2" and "21/20".
Floating-point JSON numbers and booleans in numeric fields are rejected.
Output preserves exact rational strings rather than rounded displayed values.
H means home currency, F foreign currency. Quotes are H per F; a rise means
home depreciation. Ledger totals/positions are million H, while the separately
normalized currency, parity and central-bank cases use H and F units.

Accounting follows the specifically inspected March 2025 white-cover,
pre-edited IMF BPM7, not a claim about implementation in any observed dataset.
BPM7 calls the older primary/secondary income accounts earned/transfer income,
and calls net errors and omissions the statistical discrepancy. Financial
account FA = asset acquisition - liability incurrence. Thus CA + KA = FA in
consistent records, and SD = FA - CA - KA in a measured presentation.
Source records and exact inspected passages are in the chapter source catalogue.
The file copies no official numeric observations or source worked examples.

TIMING AND MODEL CONTRACTS
The ledger records transactions at event-date valuations. Each row must balance;
GDP and the current-income bridge are separate checks. Opening gross positions
and closing gross positions must remain nonnegative. Its emigration example
removes one external asset from the resident reporting boundary; it is neither
a current transfer nor a financial transaction. Principal, valuation and other
volume changes are distinct.

Currency cases: first revalue unchanged foreign principal from e0 to e1; then
accrue all stated interest at e1 and capitalize it. There are no repayments,
other asset-price changes or flows. Changing this timing changes the split:
the benchmark is not an automatic general-purpose IIP compiler. Interest
amounts may be negative if closing foreign positions remain nonnegative.

PPP cases use priced baskets, not arbitrarily rebased CPI levels. Constant-q
relative PPP is a conditional restriction, not a prediction. The actual quote
can violate it. Exact finite growth and reciprocal-quote changes are reported.

Covered strategies assume comparable default-free instruments, matching
maturity and unrestricted borrowing/lending at the supplied rates, unless the
bid/ask case explicitly separates those rates. All foreign maturity proceeds
or repayments are hedged. An expected unhedged excess return is not an
arbitrage. The two bid/ask inequalities assess those two funded strategies;
they do not certify the absence of every possible market opportunity.

Regime cases are instantaneous, before interest accrues. Commercial banks are
absent: H is directly held base/currency, with no broad-money multiplier.
Domestic securities have a fixed price over the adjustment. The linear demand
H/P = a - chi*i_H is maintained. Since currency is freely storable at zero
nominal return here, only H > 0 and i_H >= 0 are admissible. Foreign net rates
are nonnegative in this regime lab. No reserve borrowing is allowed.
Under the peg the quote is credible through the deposit maturity. Under the
float the future mean quote is SUPPLIED; it is not derived from today's OMO.
The expected foreign excess return is imposed to be zero. Reserve valuation
changes central-bank equity K, not H. No equity distribution is assumed.
There is no claim of dynamic credibility, infinite-horizon determinacy, welfare
optimality, a general lower-bound model, or causal empirical validation.

OUTPUT TARGETS
Ledger: CA -12; KA +2; private asset transactions +5; reserves -3; total asset
transactions +2; liability transactions +12; FA -10; SD 0. Opening NFA -50,
valuation +15, other volume -1, closing NFA -46. Assets close at 170 and
liabilities at 216. GNDI is 208, saving 28, investment 40, saving-investment -12.

Currency mismatch: NFA -60 to -75 H, valuation -15 with CA=FA=0.
Debt interest case: liability 200 to 315 H; valuation 100 and transaction 15;
CA=FA=-15. No double-counted interest.

PPP worked case: required next quote 55/26, depreciation 3/52. With actual fixed
quote 2 the next q is 52/55. Exercise: q1 = 21/20, PPP quote 44/21, PPP
depreciation 1/21, nominal depreciation 1/10, reciprocal quote change -1/11.

Covered benchmark: fair forward 35/17, hedge 200 H into 210 H. At the supplied
forward of 2.1, borrowing 200 H and investing abroad yields profit 21/5 H.
Exercise forward 27/17; high-quote profit 81/25 H and reverse profit 72/25 H.
Uncovered mean future spot 21/10; expected foreign gross home return 1071/1000;
expected excess 21/1000; E[1/e_next] = 35/72 versus 1/E[e_next] = 10/21.
Bid/ask profits: -226/5025 H per 1 H borrowed and -261/5000 H per 1 F borrowed.

Domestic purchase: D rises from 55 to 57. Peg H = 95, R = 19, e = 2, K = 0.
Float H = 97, i_H = 3/100, R = 20, e = 210/103, K = 80/103.
Peg D = 95 is the zero-reserve boundary; D = 96 requires negative reserves
and is INFEASIBLE. Float D = 60 reaches zero interest; D = 61 is outside the
currency-rate domain. A candidate violating these conditions is reported with
feasible=false, not silently clipped or represented as an equilibrium.
Foreign rate of 8%: peg H = 92, R = 37/2; float H = 95, i_H = 1/20,
e = 72/35, K = 8/7.

LEARNER CHANGES
Change one complete, balanced external transaction and the related GDP/income
inputs if needed. Explain why changing just one leg must fail the ledger check.
Change both domestic and foreign inflation and distinguish actual q changes
from the conditional PPP quote. Replace a forward quote by its parity value
and verify both funded profits become zero. Vary the supplied future mean,
keeping today's policy unchanged. Find each regime's global reserve/money
boundary and explain what additional assumption would be needed beyond it.

VERIFICATION
The separate scripts/check_v06_c11.py chapter checker uses independent exact
cash-flow arithmetic, stock bridges, parameter variations and original equation
residuals; it checks preserved output, strict JSON/quiet callability, arbitrary
working-directory CLI behavior and invalid inputs. Prose, proofs and all eight
solutions also require editorial review. Structural/numerical checks are not
visual, mobile or print QA, and are not external academic certification.
