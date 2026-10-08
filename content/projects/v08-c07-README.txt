VOLUME 8 CHAPTER 7 — MORROW PROCESS COMPONENTS RELATIVE-VALUATION LAB

Original fictional inputs; no issuer, exchange, vendor or market observation.
All money is nominal kCU; prices and claim values are at T0 after distributions.
Y0 is the trailing twelve months and Y1 the next twelve months after T0.

FILES AND RUNNING
Keep v08-c07-inputs.json, v08-c07-analysis.py, v08-c07-output.json and this
README together. Run:
  python3 v08-c07-analysis.py
For an edited separate input file:
  python3 v08-c07-analysis.py my-inputs.json
The program prints JSON and writes no files. It uses only the Python standard
library, no network. Import is quiet; benchmark(data=None) returns strict
JSON-compatible data. None loads the adjacent input, independent of caller cwd.
Values are exact integer or rational/decimal strings. Round only for display.

CLAIM AND EARNINGS CONVENTION
Operating EV = ordinary equity + financial debt + leases + NCI - excess cash
- excluded holdings. Debt excludes leases; all supplied amounts are date-0
market values or stipulated estimates. All operating measures include 100% of
consolidated subsidiaries. Cash/holdings are excluded from their earnings.
There are no preference, option, pension or other omitted claims in this lab.

Normalize every operating subtotal to the basis before all lease payments;
the EV includes the lease financing claim. Add back a lease expense only when
the supplied subtotal deducted it. Net-income reconciliation and full audited
statements are outside this synthetic register; the inputs begin at supplied
management operating subtotals and explicitly are not GAAP EBITDA disclosures.

Normalized forward EBITDA = reported subtotal + included lease expense
+ settled isolated cost - transitory gain + cycle adjustment
+ forward capacity contribution. D&A is then deducted to obtain EBIT.
Qualifying transitory items were settled before T0; no remaining liability is
ignored, and related cash is already in the claim register. Regular warranty,
compensation and other recurring expenses remain costs. P4's additional
capacity was funded before T0; its forward depreciation includes that capacity.
The supplied cycle adjustments assume the stated Y1 normalization. They are
forecasts, not empirical proof that a business will recover or cool that quickly.

PEER RULE
The complete register contains P1-P6. Include industrial-component businesses
with supported normalization and positive forward EBITDA and EBIT, matching
the stipulated mature positive-profit target. No multiple or price cutoff.
P5 software licensing is kept visible but excluded for its operating model.
P6's unsupported loss/distress case remains visible with no meaningful positive
earnings multiple. Its downside evidence cannot be wished away for a similar
target. Normalization support flags are supplied assumptions, not software
authentication of the analyst's judgment.

ANCHORS
P1-P4 operating EV: 360, 480, 300, 720.
Normalized forward EBITDA: 60, 60, 50, 80.
Multiples: 6, 8, 6, 9; median 7; arithmetic mean 29/4; pooled ratio 186/25.
The pooled ratio weights by positive EBITDA, not company count or market cap.
Leave-one-out medians in P1-P4 order: 8, 6, 8, 6.
EBIT: 48, 36, 45, 60; median EV/EBIT = 39/4.

Morrow market EV = 385; net excluded claims = 85.
Raw subtotal 80 becomes normalized forward EBITDA 50 and EBIT 40.
Raw multiple 77/16 = 4.8125; matched multiple 77/10 = 7.7.
Median-relative EV = 350, common equity = 265, CU/share = 53/2.
Mean-relative EV = 725/2; pooled-relative EV = 372.
EBIT-median EV = 390, common equity = 305, CU/share = 61/2.
Applying 7 to unadjusted 80 gives EV 560, an overstatement of 210 versus
applying the same forward multiple to the matched normalized 50.

CONDITIONAL DCF
EBIT 40, tax 25%, R 15%, g 3%, r 9% give NOPAT 30, investment 6 and FCFF 24.
Opening productive capital is 200; closing capital 206 supports next NOPAT 30.9.
EV = 400, equity = 315, CU/share = 63/2; justified EV/EBITDA = 8.
D&A includes leased assets; replacement/reinvestment includes their renewal.
No second lease payment, interest or tax shield enters operating FCFF. The
supplied rate/claim convention is appropriate by assumption, not estimated.
At unchanged first FCFF/growth, peer-median EV 350 implies r = 69/700; quoted
EV 385 implies r = 711/7700. These are conditional reconciliations, not independent
risk estimates. The stable model requires old earnings maintained and investment
at year-end to fund the next year's growth. All projected cash includes that
investment; the first future NOPAT is held fixed when comparing policies.

EXPERIMENTS
1. Reverse or reorder the peer list. Median, pooled and target estimates must
   remain unchanged; the displayed register retains its input ordering.
2. Express P1's reported subtotal before lease payments: change reported basis
   to before_lease_payments, add 10 to reported_subtotal and set the included
   lease expense to zero. The economic normalization and all estimates agree.
3. Add the same amount to P1 ordinary equity and excess cash. Operating EV and
   every operating ratio stay unchanged because only excluded cash was added.
4. Change Morrow's cycle adjustment to -25, documenting the weaker Y1 scenario.
   Recompute the denominator, cash and claim bridge; do not freeze the old
   multiple and present the change as an independently estimated fair price.
5. Reclassify P5 only if you supply an economic argument that changes the
   selection rule. Report both selections and explain why price alone does not
   establish comparability. Do not delete the original candidate register.

BOUNDED CONTRACT AND LIMITS
Numerical inputs are exact integers or rational/decimal strings, not binary
floats or Booleans. Claim values, costs/gains in their stated directions and
depreciation are nonnegative; operating EV is positive. IDs must be unique; prices and forward periods
must match. Share count is positive. Stable DCF has 0 <= tax < 1, positive R/r,
0 <= g < r and g < R for positive cash in this implied-rate comparison.
There must be at least two included positive-profit
comparators; negative residual equity requires a separate distress model.
The original target has a positive reported subtotal and positive market EV.
There is no automated source verification, outlier deletion, regression,
confidence interval, transaction synergy estimate or default-risk model.
Price evidence, operating evidence and conditional DCF should be reconciled,
not represented as independent confirmations when they share assumptions.
