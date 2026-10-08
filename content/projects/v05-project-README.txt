VOLUME 5 PROJECT: CORRECTING A MARKET WITH TWO DISTORTIONS

Purpose and provenance
This is an original synthetic market, not empirical data or an estimated policy
effect. Creation date: 8 October 2026. Textbook evidence boundary: 6 October 2026.
All values, costs and probabilities are supplied assumptions. Model quantities
refer to one hypothetical operating period, not either calendar date. No source
dataset, private record, external API or current legal rule is embedded.

Files
  v05-project-data.json       Frozen model, timing, units and seven scenarios
  v05-project-analysis.py     Standard-library exact benchmark
  v05-project-output.json     Preserved complete JSON output
  v05-project-manifest.json   SHA-256 checks for those three files
  v05-project-README.txt      This guide
The HTML project supplies tasks, deliverables, a 100-point rubric and complete
instructor explanations. Existing chapter primary-method references are reused;
the market parameters and project calculations are original.

Run all files from one directory:
  python3 v05-project-analysis.py
  python3 -O v05-project-analysis.py
  python3 v05-project-analysis.py --data /path/to/variant.json
On Windows, py -3 can replace python3. The default input is resolved beside the
program, independent of working directory. The program reads input and prints
JSON but does not write files. It uses no network, package installation, seed or
random sampling. The frozen output was generated with standard-library Python;
record your own Python version in your reproduction log. Exact rational strings
avoid machine-dependent display rounding. Do not overwrite the baseline files.

Input schema and units
The top-level synthetic flag must be true. There are exactly two firms in each
scenario. The first scenario is baseline; all scenario and within-scenario firm
IDs are unique. Numeric fields use integers or strings such as "1/4". Floats and
booleans are rejected. Every scenario states:
  demand_intercept A, demand_slope b, damage_slope h;
  linear_cost c, quadratic_cost k and capacity u for each firm;
  tax_ceiling, standard_ceiling, tax_administration and standard_administration.
Prices, c and unit taxes are USD per output unit. Output is units per period.
The slopes have USD per squared output-unit scale in this fixed-period model.
Benefit, private cost, damage, profit, public cash and welfare are USD per period.

Demand: P = A - bQ; benefit: B = AQ - bQ^2/2.
Private cost: C_i = c_i*q_i + k_i*q_i^2/2.
Damage: D = hQ^2/2. One emission unit per output unit; no separate abatement.
The input requires A,b,k,u > 0, c,h and administrative costs >= 0, and
b*sum(capacities) <= A, preserving nonnegative price over the entire output box.
The standard ceiling includes the physical box. The supplied policy intervals
are 0 through 40. There is no private fixed operating cost or entry decision.

Timing and interpretation
Within a deterministic scenario the primitives are known before the regulator
chooses a policy. Firms then choose quantities simultaneously and buyers clear
the market. Competition is a price-taking comparison using the same production
technologies; two firms are not presumed empirically competitive. Cournot firms
internalize their own price effect. The number of firms stays fixed when a firm
operates at zero. Contracts, entry, collusion and dynamic adjustment are absent.

The uniform tax is nonnegative, with no subsidies or firm-specific rates. An
equal standard sets q_i <= min(u_i,s); it is nontradable, freely allocated and
produces no permit-auction revenue. Administration is a real fixed resource cost
for any deployed instrument, even a zero-rate tax or nonbinding standard. The
separate no-policy option costs zero. Government cash equals receipts minus
administration. Negative balances use an available lump-sum public numeraire
endowment; positive balances can be retained/rebated without another distortion.
This assumption supplies finance; it does not erase the real resource expense.

The welfare criterion is quasilinear unweighted dollar surplus including harm
to outsiders. It does not assert that every person benefits or choose an ethical
distribution. The identities checked are:
  W = B - sum(C_i) - D - K
    = consumer surplus + sum(after-tax firm profits) + government cash - D.
Count administration once, and do not add tax receipts to the direct resource
formula a second time.

How the benchmark establishes global results
For every lower/interior/upper firm-output state, solve the linear marginal
conditions and impose all bound/marginal inequalities. Under a scalar policy,
outputs are affine on each resulting valid interval. Welfare is quadratic on
that interval. Compare all endpoints and in-interval stationary points, then
compare the no-policy option. The chart's 41 points are not the optimizer.
Policy ties: prefer no policy, then tax, then standard; within tax ties select
the lower tax; within standard ties select the higher standard. Strict private
concavity and the Cournot clipped-response contraction ensure a unique output
equilibrium; overlapping active-set descriptions at boundaries must agree.

The report includes efficient_target_without_administration as a resource target,
not as an equilibrium claim. Each regime contains no_policy, both policy_search
objects with candidate_audit and affine_regions, and recommended_feasible_policy.
baseline_instrument_comparisons supplies complete ledgers for no policy, deployed
taxes 0/16/32/40 and standard 16. Exact outputs and welfare remain fraction strings.

Baseline instructor targets
P = 100 - Q; C_i = 20*q_i + q_i^2/2; u_i = 40; h = 1.
Competition without intervention: q_i = 80/3, Q = 160/3, W = 6400/9.
Cournot without intervention: q_i = 20, Q = 40, W = 1200.
Efficient target: q_i = 16, Q = 32, gross W = 1280.
Tax administration = 20; standard administration = 35.
Competition requires tax 32; Cournot requires tax 16. Both give net W = 1260.
The common standard 16 binds both firms and gives net W = 1245.
At that standard the unrestricted Cournot best response to rival output 16 is
64/3, above 16. This is implementation by a binding firm cap, not permit trade.
Applying tax 32 to Cournot instead gives Q = 24, gross W = 1200, net W = 1180.
Cournot deployed-tax net W = 1180 + 10*t - 5*t^2/16 on [0,40]. The tax curve
starts at 1180, while the distinct no-policy reference is 1200.

Complete recommended-policy targets (policy value; net welfare)
Scenario                  Competition                  Cournot
baseline                  tax 32; 1260                 tax 16; 1260
low_damage                tax 80/7; 12660/7             none; 1800
high_damage               standard 80/11; 6015/11       standard 80/11; 6015/11
tight_capacity            none; 1200                   none; 1200
costly_administration      tax 32; 1180                 none; 1200
asymmetric_cost           tax 136/5; 5244/5             tax 68/5; 5064/5
inactive_firm             tax 80/3; 3140/3              none; 3200/3

Low damage h = 1/4 has efficient Q = 320/7, greater than no-policy Cournot
output. Its implementing Cournot tax would be -80/7, outside the menu. At
h = 4, efficient Q = 160/11 needs a Cournot tax 560/11 > 40; best tax 40 has
net W = 480. Competition's best tax 40 has net W = 1420/9. The feasible standard
reaches the target and beats both. With capacities 12, both no-policy regimes
already produce the efficient feasible (12,12). A deployed nonbinding standard
still costs resources. With c_2 = 100, zero output for firm 2 is a verified
boundary; no negative quantity is admitted.

Asymmetric c_2 = 44: efficient q = (128/5,8/5), gross W = 5344/5. Cournot
uniform-tax quantities have q_1 - q_2 = 12, so no common tax attains that vector.
Best uniform tax 68/5 gives q = (98/5,38/5), the efficient total 136/5 but a real
cost-allocation loss of 36 before administration. Its net W is 5064/5. Cournot
standard branches are (s,s) for s in [0,14], (s,(56-s)/3) for s in [14,23], and
(23,11) for s in [23,40]. Best deployed standard s = 64/3 gives net 8485/9,
below no-policy 975. Discriminatory taxes (8/5,128/5) would implement the target
but are outside the available policy menu.

Fixed policies versus uncertain damage
fixed_baseline_policy_stress carries the baseline Cournot tax 16 and standard
16 into each scenario without reoptimizing their values. Scenario recommendations
are separately labeled. Under tight physical capacities 12, standard 16 changes
no output but still uses administration resources.

For damage_uncertainty, only h changes: 1/4, 1, 4 with probabilities 1/4,1/2,1/4.
The regulator commits before observing h and cannot revise the policy. Firm
private incentives do not depend on h. E[h] = 25/16 therefore reduces expected
welfare to the same quadratic with that damage slope. The globally best fixed
Cournot tax is 1360/49, giving Q = 1280/49 and expected net W = 50220/49.
The best fixed standard is 640/49 with expected net W = 49485/49. Original tax
16 gives expected 972, original standard 16 gives 957, and no policy gives 750.
The program reports state ledgers at the SAME ex ante chosen tax and checks their
weighted mean. These probabilities are assumptions, not estimated frequencies.

Limits and input failures
The program deliberately rejects unsupported dimensions, duplicate IDs, missing
or malformed numeric fields, negative costs/damage, nonconvex costs, inconsistent
price domains, out-of-range comparison policies and invalid uncertainty weights.
The uncertainty states must share every private/administrative parameter and
vary damage only. A variant must also leave the baseline stress-test policies
feasible in every scenario; infeasible values are rejected, not silently clipped.
When designing variants, update their descriptive metadata and analysis protocol.

Parameter sensitivity is not a standard error or confidence interval. No demand
curve, marginal cost, conduct parameter, harm function or policy effect has been
estimated from observations. Actual evidence would require measurement, credible
variation, an assignment/identification argument, source dates and missingness
records. A model-consistent price change alone does not identify why it happened.
