V07 C08 — Meridian Components: costs, allocation and capacity

An original one-month synthetic teaching case, not observed company data.
Run python3 v07-c08-analysis.py with this file's companion input JSON beside
the script, or pass another input path as the first argument. Python standard
library only; no network, installation or persistent output. Exact fractions
are printed as JSON strings; whole output quantities are JSON integers.

Units and scope
Money is CU (not kCU), quantities are whole saleable units, machine capacity
is hours and setup capacity is batches. S batches hold at most 10 units,
P batches at most 2, so partial batches require a full setup. No joint batches.
The model enumerates all S/P pairs within supplied finite demand caps, checks
both resources, and retains every tied maximizer; caps are at most 200 each.
Detailed cost allocation is shown for the first maximizer only; the complete
quantity-choice list preserves all ties. Fixed pools must sum to a positive
amount in this lab. Capacities and batch sizes must be positive whole numbers.
Prices and variable costs are constant across this relevant range. All normal
output is produced, sold and collected in the month; all costs are consumed
and paid. No opening/closing inventory, tax, debt, depreciation, receivables,
payables or owner flow. Monthly capacity services have fixed committed cash
costs. Opening cash/equity is 20000, sufficient to pre-fund all regular demand;
ending cash/equity equals opening plus monthly profit in this isolated case.

Cash fixed pools: machine support 1800, setup support 900, common facility 300.
They are committed inside the supplied capacity for this month. Driver-based
assignments do not become cash saved if a product is removed. Practical-capacity
ABC rates are 1800/300 = 6 per machine-hour and 900/30 = 30 per setup. Common 300 is
not assigned to products. Unused resource cost is shown and reconciled.
Traditional allocation here is a deliberately retrospective allocation of all
3000 by actual machine-hours. At zero hours it is undefined, not a zero rate.

Baseline benchmark
S = 60 / P = 24 uses 240 machine-hours and 18 setups. Revenue 9840, variable cost 6600,
contribution 3240 and profit/cash increase 240; cash/equity close at 20240.
Traditional costs 1500/1500 give product margins 300/-60.
ABC assigns 900/1080; unused machine 360, unused setups 360 and common 300.
ABC product margins 900/360 less 720 unused and 300 common give the same 240.
Fixed mix 5S:2P has contribution 270 per bundle. Continuous break-even is 100/9
bundles; first whole-bundle plan 12 produces 60/24 and profit 240. Feasibility
must still be checked. A changed mix is a new break-even calculation.

Capacity benchmark
Unique optimum S = 80 / P = 28 uses 300 hours and 22 setups, contribution 4080 and
profit 1080. Cash/equity close at 21080. ABC product assignments 1200/1260,
unused setups 240, common 300; these reconcile total fixed cost 3000.
Global certificate: 30S + 60P = 12(2S + 5P) + 6S <= 12*300 + 6*80 = 4080.
Feasible equality at 80/28 proves the result, independently of enumeration.

Special order: alternative contexts, not simultaneous scenarios
Ten special S-like units at 85, variable 70, take 20 hours and one separate
setup; additional external delivery/preparation cash 40 is outside the fixed
pools and the per-unit variable cost. No regular-price spillover or quality
change is assumed. In the idle context regular sales are fixed at 60/24 and
there are no additional regular orders that month: increment 110, quote 74.
In the busy context regular demand caps 80/50 are available: reoptimize regular
output with 280 hours/29 setups left. Best regular 80/24 contributes 3840;
opportunity cost 4080 - 3840 = 240. Special increment is -130, quote 98. The program
does not subtract an allocation as an additional cash cost.

Experiments
1. Raise P variable cost to 110. Derive the new optimum and busy special quote
   before execution: 80/28 remains optimal, profit 800; busy quote 94.
2. Set both regular prices equal to their variable costs. All feasible plans
   tie in contribution. The solver preserves ties and reports no positive-
   fixed-cost break-even under the supplied mix.
3. Change setup capacity to 20; enumeration now respects the tighter resource.
   Do not use a single-machine ranking as an unconditional proof.
4. Change the baseline to zero output: traditional actual-hour allocation is
   undefined; practical-capacity ABC still shows all supplied cost unassigned.

Changing capacity inputs supplies a different hypothetical resource budget,
not free real capacity. The script keeps the input pools as supplied and
recomputes their assignment rates; add any acquisition/overtime cost when
evaluating an actual expansion. Chapter sensitivity calculations instead
compute the gross value of extra hours before their separately quoted fee.

Make-or-buy and absorption/variable-costing examples are separate chapter
cases, not extra transactions in Meridian's main cash statement. Their exact
calculations are checked by the independent repository checker. Estimated
drivers, demand, quality, opportunity use and external effects require real
evidence; arithmetic alone does not validate their economic meaning.
