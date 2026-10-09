LARCH RESEARCH RESERVE — VOLUME 9, CHAPTER 12
Original synthetic investment-policy, finite decision and reporting laboratory.
All amounts are kCU (thousands of fictional currency units). No market data,
current legal rules, forecasts, institutional endorsements or universal limits.

RUN OFFLINE
Use Python 3 and its standard library. Keep the distributed files together:
  python3 v09-c12-analysis.py --input v09-c12-inputs.json
  python3 v09-c12-analysis.py --input v09-c12-inputs.json --output answer.json
The first command emits the entire JSON report; the second writes it and is
silent. Importing the module is silent. run(data) neither prints nor writes nor
mutates the input. Exact rational results are JSON strings, including integers;
only explicitly suffixed approximate volatility quantities are floating point.
JSON null means a quantity is unavailable, not zero; it is Python None before
serialization. The frozen output is the entire baseline report. The manifest
hashes the four other distributed assets, excluding itself.

WHAT IS FIXED
The schema, unit, two equal half-year periods, flow order and mandate conventions
are enforced. These are funded one-year equity/bond mandates with no interim
redemption or pledge. All their distributions arrive at t2; supplied terminal
returns already include terminal dealing/exit costs. They are not a description
of every ordinary equity or bond investment. There are no additional taxes,
fees, currency changes, collateral calls or off-balance-sheet commitments.
The fictional contract has no commitment fee and makes the contingent line
available at t1 only; borrowed cash may count toward the stated cash buffer.
Every draw is repaid in full at t2. Initial borrowing is excluded. These terms
are case assumptions, not statements about current borrowing law or practice.

DATES AND CASH
t0 is the pretrade decision boundary. Wealth is 1,000, inherited equity 300 and
bond 400, with cash 300. Holdings x and y are kCU positions, not share counts.
Choose x in {0,10,...,500} and y in {0,10,...,600}. The entry fee is
  K = .01 abs(x-300) + .005 abs(y-400).
The cash position is c = 1000-x-y-K; hence x+y+c+K=1000. Fee rates apply to
the absolute amount traded from inherited positions. The decision target and
benchmark each pay their own entry costs, exactly once, at t0.
At t1 cash first grows by 1.01. An external contribution X and contingent draw D
then arrive before grant L1 is paid. Residual cash is 1.01c+X+D-L1. At t2 this
cash grows by another 1.01, both funded mandates distribute, grant L2 and the
full loan repayment 1.08D are paid, and remaining cash is the reserve:
  R = x(1+rE)+y(1+rB)+1.01(1.01c+X+D-L1)-L2-1.08D.
The 8% loan cost is for this half-year borrowing period; it is not an annual
rate. Grant payments are external distributions for the mission, not fees or
investment losses. Contributions are financing, not returns.

MOMENTS VERSUS SCENARIOS
Six original witness states support the planning moments. Let Z be +/-1 with
equal probability and independently U be +.13 or -.13 with probability 7/26
each, or 0 with probability 6/13. Set rE=.10+.20Z and rB=.06+.03Z+U.
The file lists the six joint outcomes with probabilities 7/52, 3/13, 7/52 for
each Z. The code derives mu=(.10,.06) and Sigma=((.04,.006),(.006,.01)).
The determinant is .000364. This is an internally coherent synthetic moment
witness, not an estimated distribution or a claim that every future return
must be one of these six outcomes. The separately supplied design, reverse
stress and reporting cases are conditional scenarios without probabilities.
They are not extra equally likely observations in the moment calculation.

ORDINARY FEASIBILITY AND PREFERENCES
Planning grants are 150 at t1 and 50 at t2. Design stresses are:
  equity_fall: rE=-.30, rB=.05, L1=150, L2=50;
  inflation_funding: rE=-.15, rB=-.12, L1=180, L2=60.
Ordinary feasibility does not use the emergency line or contributions. Cash
after the largest planning/design t1 bill must be at least 20; final reserve
in every designated stress must be at least 650. These are finite-scenario
requirements, not probability-of-ruin or all-state guarantees.
Let v=(x,y) Sigma (x,y)' and a=(x-400,y-400). Required v<=10000 and a Sigma a'
<=36 correspond to standard deviations 100 and 6 kCU, or 10% and 0.6% of the
original 1,000 kCU. The denominator is original pretrade wealth, not net wealth
or the diminished post-grant fund. Cash and entry fees are deterministic in
this moment model and therefore affect the mean, not the variance.
The benchmark starts from the same inherited positions and invests 400/400,
pays fee 1 and retains cash 199. The shorthand 40/40/20 target is pre-cost;
claiming its implemented cash is 200 would invent one kCU. It satisfies its
own caps, costs, liquidity, total-risk and stress requirements. The inherited
300/400 portfolio breaches the newly adopted active-risk limit: the board is
authorizing a transition, not claiming that the starting portfolio complies.
The decision criterion is J=E[R]-gamma*v/(2W), with gamma=4, W=1000 and
E[R]=1.10x+1.06y+1.0201c-1.01*150-50. J has kCU units. This is a chosen
mean-variance score, not a guarantee of expected utility or a social welfare
function. Enumerating every grid point gives an exact finite global solution.
Tie-breaking uses lower variance, lower fee, then lower x and lower y.
Nonexclusive rejection counts overlap: one point can fail several constraints.

BASELINE BENCHMARKS
There are 3,111 candidate pairs and 28 feasible pairs. The unique winner is
x=370, y=430, K=.85, c=199.15. Its mean reserve is 864.452915, variance 9234.2,
active variance 34.2 and criterion 845.984515. The next score is 845.895320 at
370/420, a gap of .089195. A small score advantage does not imply precise
economic superiority given uncertain inputs. The policy benchmark has mean
865.4999, variance 9920 and score 845.6599. Lower mean can accompany a better
chosen score. Its difference from the selected score is .324615.
Selected variance contributions are 6430.6 and 2803.6, summing to 9234.2.
Divide them by total standard deviation 96.094744914 for volatility
contributions 66.919372186 and 29.175372727. Active variance contributions are
30.6 and 3.6. These are Euler accounting contributions, not causal forecasts.
The selected stress reserves are 712.152915 and 654.252915. At t1 its cash is
201.1415 before the grant; after a bill of 180 it retains 21.1415. The maximum
bill preserving buffer 20 is 181.1415 without the line or 206.1415 with its full
25. Allowing zero cash raises the payable bill to 226.1415 but violates policy.

REVERSE STRESS AND REAL FUNDING
The outside-design case has rE=-.25, rB=-.08 and grants 240/60. With the full
line but no new external contribution, the t1 payment gap is 13.8585 and the
buffer gap is 33.8585. The output refuses to compound hypothetical negative
cash: cash_after_t1 and terminal_reserve are null. The loan and gaps remain
visible. Providing 33.8585 at t1 restores cash 20, but leaves reserve 606.3 at
t2 after the loan repayment 27 and grant 60, short of the floor by 43.7.
For a specified D, the minimum external contribution satisfying both dates is
  X(D)=max(0, L1+20-1.01c-D,
    [650-A-1.0201c+1.01L1+L2+(.07)D]/1.01),
where A=x(1+rE)+y(1+rB). At D=25, X=15579417/202000, approximately 77.125826733.
At D=0, X=15229417/202000, approximately 75.393153465, and reserve is exactly
650. The latter is the minimum external funding across the permitted draws
because its binding floor bound rises with D. Borrowing moves cash across
dates but pays a spread; it does not create wealth. The code's general bounded
repair routine compares endpoints and the two affine bounds' crossing (plus
the cash bound's zero). This suffices for the maximum of a decreasing line,
an increasing line and zero; among equal contributions choose the smaller draw.
Funding is a conditional requirement, not an assertion that the contribution
exists. If no contributor commits it, the board must revisit grants or its
previous mandate; the manager may not fabricate an unapproved credit source.

FILLED REPORT AND IMPLEMENTATION
In a separate execution audit, one 10-kCU equity buy lot is unfilled. The target
370/430 becomes actual 360/430, fee .75 and cash 209.25. Actual total variance
8890.6 is lower, but active variance 58.6 breaches the limit 36. The report
records a breach; it does not approve this portfolio or silently reset policy.
Under realized rE=.12, rB=.01 and grants 150/50, final reserves are:
  actual 849.455925; intended decision 850.352915; policy benchmark 853.4999.
The actual-minus-benchmark gap -4.043975 decomposes into policy-selection gap
-3.146985 and implementation gap -.896990. The missed equity would deliver
11.2, versus retained cash 10.1 (including .10 saved fee) growing to 10.30301.
All three use the same initial wealth, dates and grants. This is a conditional
terminal-reserve attribution, not proof of skill or a time-weighted return.
Interim mandate values are absent, so the report does not invent TWR. A future
report would require reliable flow-boundary valuations to calculate it.

DOCUMENTED INTERVENTIONS AND DOMAINS
run() accepts copies with bounded rational numeric edits: wealth/lot/caps,
inherited positions/fees, gamma/limits, cash/line factors, positive witness
probabilities/returns, benchmark positions and scenario grants/returns. Every
edited case must retain the fixed conventions, positive-definite witness
covariance, valid probabilities and a benchmark that itself remains feasible.
This is an intentionally finite two-mandate contract, not a universal IPS,
liability engine or arbitrary trading simulator. Changing what an asset pays
or permits at t1 requires a different model, not a descriptive-text edit.
Baseline examples: gamma=2 selects 400/400; gamma=6 selects 370/400; active
variance limit=0 permits only the implemented benchmark. Subtracting .02 from
every equity witness return changes its mean to .08 but preserves covariance;
370/430 remains selected with mean 857.052915 and score 838.584515.
If an allowed decision edit makes the partial-fill buy example inapplicable
(target or remaining equity below inherited holdings), the execution report
explicitly says unavailable rather than interpreting a sale as an unfilled
buy. If an edited reporting grant is unfunded, terminal gap attribution is
null. The main stress functions still report the actual dated funding failure.
All numeric JSON inputs are integers or rational strings, not floating-point
numbers or booleans. NaN/Infinity, extra fields, contradictory conventions,
negative grants, invalid rates, non-grid fields, oversized enumeration,
singular covariance and an infeasible benchmark are rejected. Ledger/repair
helpers are used with validated inputs and positions produced by this module;
run(data) is the public complete-case validation boundary.

LEARNER TASK
Reconstruct the cash budget, witness moments and feasible set independently.
Explain why the benchmark is implementable, why the score winner is not a
universal optimum, and why the reverse stress invalidates a claim of guaranteed
grant funding. Change a preference and a forecast separately; preserve the
original record. Submit the filled policy, dated decision ledger, alternative
comparison, exception report and funding recommendation. Evaluate reasoning,
traceable assumptions and reconciliation, not conformity to a preferred risk
appetite. The chapter contains the full worked answers and exercise rubrics.

VALIDATION BOUNDARY
The repository checker independently reconstructs the state moments and full
finite feasible ranking, cash schedules, risk decomposition, exercise changes,
funding thresholds, partial-fill attribution, domain rejections, strict whole
JSON regression and distributed hashes. It also runs this bundle from an
isolated temporary directory in ordinary and optimized Python modes. Passing
these checks is reproducibility evidence; it does not validate real expected
returns, certify a legal mandate or supply independent human investment review.
