V07-C06 — original equity and consolidation laboratory
Edition boundary: 2026-10-06. Created/checked: 2026-10-08.

FILES AND RUN
Keep v07-c06-analysis.py and v07-c06-inputs.json together. Python 3 standard
library only; no network, packages, or real company data. From any directory:
  python3 /path/to/v07-c06-analysis.py
Or supply an explicit input JSON path. Standard output is JSON; invalid teaching
contracts exit 2 with a short error. v07-c06-output.json preserves the baseline.
In the source repository run: python3 book/scripts/check_v07_c06.py
The independent checker also exposes quiet check() returning a serializable dict.

UNITS AND PROVENANCE
All numbers are invented for this chapter. Money is kCU; shares are thousands,
prices/par are CU per share. Thus 25 thousand shares at 2 CU raise 50 kCU.
Numeric JSON inputs/outputs are exact rational strings: "1/2" equals 0.5, not
one-half kCU unless the field is a money field. No floating-point rounding.
X1 denotes a fictional year; ordered dates are supplied, not historical claims.
The two companies/cases are unrelated. No real disclosure is reproduced.

SHARE CONVENTION
Juniper uses residual ordinary shares, par capital, issue APIC, retained earnings
and debit contra-equity treasury shares at repurchase cost. No retirement. A
reissue above cost credits separate treasury APIC, not income; a below-cost
reissue first uses that accumulated credit and then retained earnings. This is
a stipulated cost-method teaching convention, not universal allocation rules.
Average treasury cost is used if a learner adds a second repurchase lot. The
40-thousand-share observer never trades, so buybacks cannot remove her shares.
All cash-service proceeds are current revenue; no extra expense is omitted.
Contributions/distributions are kept outside profit. Baseline cash 80, A 230,
L 80, E 150; capital 62.5, total APIC 72.5, RE 60, treasury deduction 45;
issued 125, treasury 15, outstanding 110. Profit 30, net owner cash zero.
Every posted prefix balances and has nonnegative cash; closing entries do not
create cash. Legal distribution/authorization rules and taxes are not modeled.

GROUP CONVENTION AND TIMING
Cedar purchases existing Brook shares from outside sellers on 1 January X1.
Brook receives no purchase proceeds. Brook is expressly a business, not merely
an asset collection. Substantive control is stipulated independently of the
75% economic stake. Matching reporting dates/policies and no investment-entity
exception are assumed. Other percentages in sensitivity tests do not prove
control. Alpha is in (0,1], with control still separately stipulated.

Identifiable acquisition-date fair values equal the supplied balances. The
proportionate-NCI method recognizes NCI=(1-alpha)*identifiable net assets and
GW=consideration-alpha*net assets. This model excludes bargain purchases,
step acquisitions, deferred tax, acquisition costs, FX, OCI, preference claims,
new subsidiaries, changes of control and subsequent goodwill adjustments.
No goodwill amortization or impairment occurs in this stated case; no general
SME/GAAP/IFRS claim is made. Land is nondepreciable. Old receivables, old
inventory and external liabilities remain unchanged. External liabilities are
not interest-bearing in this case. Parent separate accounts retain investment
at cost and recognize the supplied dividend as income. Group dividends are
owner distributions, not expenses; NCI profit is attribution within equity.

The batch transfer is downstream (parent to subsidiary). All external sales
are for cash and recognized on delivery. Fraction z of the batch is sold at
fixed outside full-batch revenue 200*z. Parent external cost 40 and transfer
invoice 60 are for the entire batch; unpaid invoice remains intercompany.
The worksheet eliminates the entire transfer sale and internal balance, and
margin 20*(1-z) embedded in unsold inventory. No negative transfer margin or
inventory impairment is modeled. Company cash must fund the specified order.
Changing a dividend/settlement may fail that constraint despite group cash.

BASELINE TARGETS (kCU)
Acquisition: S net assets160; proportionate NCI40; goodwill30; group A580,
L140,parent E400,NCI40,cash190. Net acquisition outflow150-40=110 compared
with parent pre-acquisition cash300; S enters the reporting perimeter then.
Parent closing A542/L100/E442/cash177/profit62. Subsidiary closing
A249/L55/E194/cash59/profit50. Group A646/L140/parent E457.5/NCI48.5,
cash236/inventory60/revenue180/COGS20/other costs70/profit90. Profit attribution:
parent77.5,NCI12.5. Investment150, intercompany balance15, dividend income12,
intragroup sales60 and unsold margin10 require elimination. Group post-control
CFO70 and external distributions24 reconcile cash190 to236. Acquisition is
reported separately, not counted again in post-control CFO. NCI dividend4 is
a group cash outflow; parent receipt12 is internal. NCI is not a debt here.

LEARNER TASK
Rebuild company ledgers and acquisition/post-period worksheets before running.
Explain each eliminated item and independently reconstruct external cash.
Try zero/full internal settlement, zero dividends, full ownership with a
feasible consideration, and all/none of the batch sold with feasible cash.
Do not interpret a balanced worksheet as proof of actual control, fair values,
impairment, legal distributability, valuation, or conformity to a full standard.
The program checks stated arithmetic/contracts, not documents or legal rights.
Sources and scope are listed in the chapter; inputs and examples are original.
