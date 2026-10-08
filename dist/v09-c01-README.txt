SEREIN RETURN-MEASUREMENT DESK — VOLUME 9, CHAPTER 1
Original synthetic teaching case, 8 October 2026.

Purpose
Reconstruct returns from actual wealth and dated cash, then audit the reported
measure against the investor, strategy and mandate it is supposed to describe.
The cases are separate examples sharing measurement conventions, not different
accounts of a single company's performance. No data are observed market records,
no tax rate is an actual jurisdiction's rule, and no probability is an estimate.

Files and offline operation
Keep these five files together:
  v09-c01-inputs.json    Complete fictional case inputs and conventions.
  v09-c01-analysis.py    Standard-library Python implementation.
  v09-c01-output.json    Complete preserved benchmark output.
  v09-c01-manifest.json  SHA-256/byte lengths of the other four files.
  v09-c01-README.txt     This execution and scope guide.

Run from any working directory:
  python3 /your/path/v09-c01-analysis.py

Or, from their directory, pass a separately edited case copy:
  python3 v09-c01-analysis.py /your/path/case-copy.json

The default input path is resolved beside the script. The program writes only
JSON to standard output and never replaces inputs/reference files. To save a
run, redirect output to a NEW file. No network, installed packages, account,
environment variable or application is required. Import is quiet; run(data)
returns a JSON-compatible dictionary. The repository's separate checker is not
needed to run this download.

Rational money and returns use exact reduced fraction strings: "89/520" is a
simple return, not 89.520 percent. Percent display requires multiplying by 100.
Logs, annualized roots and the money-weighted annual root are floating-point
values, not fractions. A comparison should allow about 1e-12 absolute/relative
rounding for these values and verify the independent defining equation. Integers
used as years and boolean flags preserve their JSON types. JSON null means no
finite log return at zero gross wealth; it is not a zero return.

Conventions and model bounds
There are exactly two equal annual intervals, dates 0/1/2. No irregular-day or
business-calendar convention is inferred. Amounts are fictional CU; underlying
wealth ratios are dimensionless. Whole-number or decimal/rational STRING inputs
are accepted; binary JSON float inputs are rejected so exact financial inputs
are not silently approximated. All economic inputs remain within the documented
positive-wealth, long-only fixture scope.

run() checks the behavior-defining convention strings, including dividend
reinvestment, cash-flow timing, fee base, currency quote and rebalancing policy.
Changing a convention requires changing the model as well, not merely editing
a narrative label. Numerical parameters may change within their stated domains.
The individual functions also enforce relevant economic boundaries. They are
small instructional functions, not universal IRR, tax or portfolio engines.

1. Distributions
One share opens at 80. Annual ex-dividend prices are 78 and 84; simultaneous
cash distributions are 6 and 3 per share. Fractional reinvestment is immediate,
without fees or tax. The first reinvestment gives 14/13 shares. Final wealth is
1218/13 = 93.6923076923, growth factor 609/520, cumulative return 89/520,
annual equivalent about 8.219861678%. The share count after reinvesting even
the final distribution is 29/26; reinvesting at the final instant changes no
endpoint wealth. Linked total return and actual share holdings agree.

A separate one-original-share policy retains each dividend in zero-yield cash:
final wealth is 93, return 13/80 = 16.25%. Price return alone is 5%. The retained
cash is not invested in later shares. Neither strategy dominates on every path.

2. External investor flows
The account starts at 100, grows to 120, receives 180 at date 1 immediately
AFTER valuation, and ends at 270. Subperiod returns are +20% and -10%; TWR is
8% cumulatively, or about 3.923048454% annually. Investor net cash gain is -10.
The annual money-weighted root solves 100*x^2+180*x=270 with x=1+r>0, giving
r about -2.650060048%. There is exactly one positive x because the left side
increases continuously from zero to infinity. The implementation uses the
algebraically equivalent positive-root expression 2*terminal/(contribution+
sqrt(contribution^2+4*opening*terminal)), avoiding avoidable cancellation.

The account function accepts one NONNEGATIVE date-1 contribution and positive
opening, intermediate and final valuations. It rejects withdrawals/mixed-sign
reinvestment obligations instead of returning an arbitrary IRR. Such cases are
analyzed separately in the chapter's multiple-root exercise. Zero contribution
is an allowed boundary; IRR then equals annualized endpoint growth.

Modified Dietz over both years is -10/(100+180/2) = -1/19, a cumulative measure.
It is not the annual IRR or true TWR. Holding investor flows/endpoints fixed but
changing the date-1 pre-flow value to 90 changes true TWR to -10%; IRR is unchanged.
Thus the endpoints/flows do not identify true TWR without boundary valuations.

3. Fees
Start with an investor payment of 1000; remove a 1% entry charge. Apply underlying
annual returns +12% and -5%. Charge 1% of post-return assets at each year end,
then charge 0.5% of final assets for redemption. Final receipt is 1027.23614532,
an investor cumulative return of 2.723614532%. Before all charges the underlying
return is 6.4%; after management fees but before entry/exit it is 4.28264%.
These levels have different economic perimeters and must not be relabeled.
There are no additional unrecorded trading costs, taxes or external flows.

4. Currency and purchasing power
In a separate one-year case, the foreign total return is 8%; home CU per foreign
unit falls from 1.25 to 1.1875. Home nominal return is 2.6%. Home inflation is
4%, so real return is -7/520, about -1.346153846%. Intermediate foreign income
has already been included in the specified foreign strategy. The case has no
currency hedge or earlier conversions. A reciprocal currency quote requires
a different ratio; the convention guard prevents silently mislabeling it.

5. Finite-state opportunity set
Three physical states have probabilities 1/4,1/2,1/4. Asset A returns are
-20%,10%,30%; B returns 12%,4%,-4%. Each one-period portfolio is fully invested
long-only in A/B, chosen before the state. Expected returns are 7.5% and 4%.
The selected A weight 0.6 gives returns -7.2%,7.6%,16.4% and mean 6.1%, but
violates the supplied -5% state floor. Intersect EVERY linear state inequality
with 0<=wA<=1: the feasible interval is [0,17/32]. Because expected return
increases with wA, its highest-mean point is 17/32 with state returns
-5%,7.1875%,14.0625% and mean 15/256 = 5.859375%.

Changing the floor to -2% also activates the up-state lower bound. The interval
becomes [1/17,7/16], not [0,7/16]. The highest-mean weight is 7/16, with state
returns -2%,6.625%,10.875% and mean 177/3200 = 5.53125%. The code rejects an
empty intersection; it does not invent a feasible allocation. This is a bounded
mean-with-state-floor calculation, not a variance optimizer or equilibrium model.
Physical probabilities are stipulated; they are not claim-pricing probabilities.

6. Rebalancing
Invest 100 equally in A/B. Period returns are (+40%,-10%) then (-25%,+20%).
After Year 1, assets are 70 and 45. Buy-and-hold uses next-period weights 14/23 and
9/23, ending with 106.5, a 6.5% cumulative return. Constant-weight rebalancing
resets holdings to 57.5 each and ends with 112.125, a 12.125% return. No external
flow is introduced by swapping holdings. Rebalancing has no costs in this
synthetic comparison and is not guaranteed to win on other paths. The chapter
exercise explicitly reverses the ranking with a different second-year return.

Suggested independent checks
- Reconcile every terminal wealth directly, not just against a preserved number.
- Verify IRR using its dated cash equation and prove the relevant root domain.
- Compare exact state-by-state returns with quantity-based terminal payoffs.
- Recompute both binding sides after changing a mandate constraint.
- Check that probability scaling, invalid dates, wrong fee conventions and
  unsupported cash-flow signs reject instead of being silently interpreted.
- Compare complete returned JSON, manifest hashes and normal/-O CLI runs.

Sources and limits
The HTML links scoped primary return-calculation and performance-method
references; all case data/code and derivations are original. Exact arithmetic
does not authenticate valuations, estimate probabilities, establish investor
skill or certify standards compliance. Annualization extrapolates a realized
growth factor for comparison and is not a forecast. No actual investment trade,
account connection, legal conclusion or tax recommendation is part of this lab.
