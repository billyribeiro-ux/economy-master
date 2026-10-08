V04-C10 — TIME-SERIES AND PANEL DATA: EXACT OFFLINE LABORATORY

Save v04-c10-panel.py, v04-c10-data.json and this README together.
Using an existing Python 3 installation, run:
    python3 v04-c10-panel.py
On Windows with the Python launcher: py -3 v04-c10-panel.py
To analyze a modified COPY of the JSON document:
    python3 v04-c10-panel.py my-data.json
The program finds the default input next to itself regardless of the terminal's
current directory. It reads without writing any file and prints a JSON report.
Fraction values print as exact strings (e.g., "710/3"); null means unavailable
or undefined as indicated by status fields. No network or package is needed.

PROVENANCE AND ECONOMIC CONTRACT
All observations, firm rosters, prices and shock laws are original synthetic
teaching constructions created 2026-10-07 for edition boundary 2026-10-06.
They are not empirical estimates or October market observations.
- Monthly sales are nonnegative integer USD flows over disjoint calendar months.
- One homogeneous good has base price 1 USD and monthly price P/100. Deflated
  amounts 100*N/P are exact constant-base-dollar flows under this stipulation.
- Entity IDs identify the same operation throughout. Active_from and
  active_through are inclusive monthly operating intervals from a trusted
  hypothetical roster. Outside them, no sales occur for this closed-roster
  total-sales target; that convention is not appropriate for every variable.
- Missing ACTIVE reports remain unknown, never zero. Individual grid entries
  outside operating intervals retain not_operating status, not a fake report.
- Month-end inventory is a stock; deliveries/defects are flows. A defective unit
  must be included in deliveries. Monthly returns are in basis points and assume
  a fully reinvested account without external cash flows.
- The stochastic laws are stipulated separately from the panel; the program
  does not estimate stationarity, autocorrelation or causal effects from it.

EXPECTED RESULTS
Panel real values: A 100,110,120; B 200,unknown,180; C inactive,300,300;
D 400,300,inactive. B's March calendar lag and growth are unavailable.
Monthly active counts 3,4,3; observed counts 3,3,3; observed means 700/3,710/3,200.
Complete whole-roster totals 700,unknown,600: February subtotal710 is incomplete.
Observed-mean endpoint growth -1/7; endpoint cohort A/B means150/150, growth0;
complete-window cohort A means100/120, growth1/5.
Endpoint total change: continuing0 + entry300 - exit400 = -100.

Quarter nominal sales700; matched-period real sales620; using the simple mean
index instead gives7000/11, which is a different result. Consistent aggregate
index3500/31. Quarter-end inventory9, three-endpoint mean35/3 (not an identified
time average). Pooled defect share11/60, equally weighted monthly rate1/5.
Compounded return47/250 =18.8%. Annualized quarter flow480 corresponds to120.

For iid shocks +/-2 with equal probability, Y_t=10+eps_t+eps_(t-1)/2:
mean10, gamma0=5, gamma1=2, gamma2=0, rho1=2/5;
variance of four-observation average2 versus independent approximation5/4.
The separately defined random walk from zero has variance20 at horizon5.

VALIDATION AND LIMITS
Supported windows span 3..24 consecutive months and must include January2024,
whose price index must equal100. The base and the exact supplied unit labels are
frozen: this program does not support changing currency, monthly units, or price
base by relabeling input. Dates use YYYY-MM in years1900..2100;
1..16 entities; at most384 observed sales rows. Each price month is unique and
must cover the window exactly. Price levels are positive integers up to1,000,000.
Amounts/counts are nonnegative integers up to1,000,000,000. Booleans/floats/null
amounts, duplicate/unknown entity-month keys, observed nonoperating rows, invalid
months and contradictory delivery counts are rejected. Absent active sales rows
are allowed and explicitly reported. The exact supported units metadata is required. Its economic truth still
cannot be verified by syntax. Quarterly input must contain all three distinct
months of one calendar quarter. Return basis points range from-10,000 to1,000,000.
The <=100% loss bound enforces nonnegative gross returns under this contract.
The moment-law parameters have small explicit bounds documented in the code.

No conditional-stationarity, panel regression, inference or missingness model is
fitted. A true zero has a valid level difference, but percentage growth from zero
is undefined. A zero-delivery month has no monthly defect rate; all-zero exposure
makes the pooled rate undefined. When all quarter sales are zero, a deflator
inferred from their ratio is undefined. A degenerate zero-variance shock law has
no defined autocorrelation. The program reports null for these boundaries.
This is a bounded local teaching tool, not an external-data validation service.

EXPERIMENTS / DELIVERABLE
1. Shuffle sales, roster and price rows. All report values and status meanings
   should remain identical because keys and dates determine the calculation.
2. Remove B's March observation from a copy. The March whole-roster total and
   its endpoint decomposition become unknown; explain the cohort changes.
3. Insert a duplicate A/2024-01 row. The program must refuse it rather than
   multiplying a count or silently choosing a record.
4. Set A's January sales to zero: distinguish its defined February difference
   from undefined percentage growth.
5. Explain each quarter operation and why 100*sum(N)/mean(P) fails to reproduce
   the matched-period real total here. The manuscript
   rebasing exercise is a separate hand calculation: the supplied program keeps
   January2024=100 and rejects alternate bases. Supporting another base would
   require a reviewed change to the program, input labels and base validation.

Submit the exact reconciliations, active/observed denominators, inclusion target,
lag statuses, one boundary experiment and a short explanation of why none of
these invented cases establishes stationarity or a causal effect empirically.
