NACRE PROCESS CONTROLS — VOLUME 8 INVESTMENT-COMMITTEE PROJECT
Original synthetic case, 8 October 2026. Edition boundary: 6 October 2026.

PURPOSE AND FILES
Build an independent operating forecast, DCF, peer comparison, financing plan
and defended acquisition decision. This is a going-concern investment committee
case, not observed company data, investment advice or a general valuation engine.
Every number, company, contract and evidence card is an original teaching input.
There are no empirical probabilities, current market observations or legal claims.

v08-assessment-inputs.json   Complete synthetic operating/contract/peer register.
v08-assessment-analysis.py  Full standard-library Python benchmark.
v08-assessment-output.json  Preserved complete exact benchmark output.
v08-assessment-manifest.json SHA-256 and byte counts for the other four assets.
This README                 Execution, units, economic scope and benchmark guide.

The assessment HTML supplies the student brief, six deliverables, 100-point rubric,
full instructor explanation and transfer intervention. Freeze your independent
attempt before reading the code or reference output. Loading a supplied solution
does not demonstrate that you can construct or defend the model.

RUNNING OFFLINE
Put the five files together. No package installation, network, spreadsheet
application, environment variable or account is needed. From that directory:

    python3 v08-assessment-analysis.py
    python3 v08-assessment-analysis.py v08-assessment-inputs.json

The first command finds inputs beside the script, even from a different working
directory. The second accepts an explicit path to a case copy. Both write only
JSON to standard output; neither overwrites a file. To preserve a new run, use
your shell's normal output redirection to a NEW filename. Do not replace the
reference when checking whether an independent result matches it.

All computed amounts are exact reduced rational strings: "3195/52" means
3195 divided by 52. Integers may be strings; years and boolean flags retain their
JSON types. JSON null means an unsuitable positive-profit multiple, not zero;
the corresponding Python value is None. Convert
to decimals only for presentation. Monetary figures below are rounded for
readability; the preserved output retains exact fractions. Importing the module
is quiet. run(data) returns a strict JSON-compatible dictionary. Its forecast,
terminal, valuation, treasury, peer_comparison and thresholds functions retain
Fraction arithmetic internally. The canonical benchmark policy is fixed: asset
sale true, new equity 70 and initial payout 0. validate() rejects contradictory
policy fields, including an edited contribution. Explicit alternatives use
treasury(data, scenario, new_equity=..., initial_payout=..., sell_asset=...).
The named reference experiments likewise require proposed payout 20 and extra
collection delay 10; contradictory edits are rejected. The named benchmark
output and its equity 70 labels are intentionally fixed;
the CLI is not a general policy-optimization interface. Other input edits must
remain within the positive-EBIT, three-year contract documented here. The repository's separate
check_v08_project.py provides independent reconstructions; it is not needed to run the downloaded lab.

UNITS, DATES AND ECONOMIC PERIMETER
Money is kCU (thousands of fictional currency units), quantity and old shares
are thousands, and unit prices are CU. Thus 60 thousand units at 10 CU produce 600 kCU.
Date 0 is 1 January 2027; dates 1/2/3 are 1 January 2028/2029/2030. The first continuing
cash flow is at date 4, 1 January 2031. All years are discrete annual intervals;
there is no day-count convention or within-year seasonality in this case.

The committee buys all old common shares for 500, pays an outside deal fee 8,
and can subscribe up to 70 new equity at date 0. Purchase price goes to sellers;
the fee goes to an outside adviser; only the subscription enters company cash.
The target opens with cash 60, operating NWC 75, PPE 425, a separately excluded
asset that has a binding immediate cash offer 30, and term principal 250. The
market quote for that old debt is supplied as 250. No preferred, lease, pension,
noncontrolling or other target claims exist. The shareholder count 50 is supplied
only for per-old-share comparisons. After acquisition the buyer owns all shares;
there is no minority issuance-allocation problem.

Operating NWC excludes all financial cash and interest-bearing debt. Operating
capital K=NWC+PPE starts at 500. Financial cash is deliberately excluded from
operating NOPAT and FCFF, including the contractual 30 reserve. It is a separate
asset valued at par and earns its own 4% after-tax required return. This is an
explicit case assumption: retaining fair-return cash has no further agency or
transaction cost. The operating forecast contains no cash interest, reserve
investment or terminal release of that financial asset. Do not add a second
required-cash amount or cash already accumulated from forecast FCFF to the
date 0 bridge. In a case that included cash in operating capital, the bridge
would need to change.

Operating tax is 25% of positive EBIT; accounting and tax depreciation are equal.
Interest is nondeductible in this fictional contract/tax model. There is no
interest tax shield, APV tax addition or debt-weight tax adjustment. The after-
tax 4% cash return needs no second tax deduction. Both explicit forecasts have
positive EBIT; the code refuses loss-tax extensions rather than inventing refunds.

OPERATING FORECAST AND NORMALIZATION
Revenue=quantity x 10. Variable unit costs are 6 in base and 6.2 in downside; fixed
cash cost is 120 each explicit year. Depreciation is 30/33/36 and capex 50/60/24.75.
Year-end capex enters service next year; the supplied depreciation schedule is
the asset-register premise. Closing NWC is the supplied fraction of revenue.
The downside has an early collection burden that reverses by date 3.

                            BASE                         DOWNSIDE
Year                       1       2       3             1       2       3
Revenue                  600     660     720           540     600     660
EBITDA                   120     144     168          85.2     108   130.8
NOPAT                   67.5   83.25      99          41.4   56.25    71.1
Closing NWC               90      99     108           108     108      99
Closing PPE              445     472  460.75           445     472  460.75
FCFF                    32.5   47.25  101.25         -11.6   29.25   91.35

FCFF=NOPAT+depreciation-capex-change in NWC=NOPAT-change in K.
Do not subtract debt interest or principal in this operating cash flow.

At date 3 the cycle normalizes; year 4 replaces the explicit-period cost mix with
a supplied 18% EBITDA margin, revenue/opening-capital turnover 16/13, depreciation
equal to 5% of revenue and the same 25% operating tax. These imply ROIC 12% on ALL
opening capital, not a marginal return attached only to next year's investment.
The explicit year 3 NOPAT is not the stable base. The normalized margin also
serves as the target's separate normalized FORWARD YEAR 1 peer denominator.

K3=568.75 base or 559.75 downside. Revenue 4=(16/13)K3, NOPAT4=.12 K3;
growth g=.02 requires net investment 4=.02 K3=(g/ROIC)NOPAT4. Thus FCFF4=.10 K3.
The NWC ratio 15% and depreciation ratio 5% recover an actual year 4 capex amount:
capex 4=depreciation 4+net investment 4-change in NWC 4. After this first normalization,
capital, revenue, NWC, NOPAT and FCFF all grow at 2% with the same economics.

                              BASE                   DOWNSIDE
Revenue 4                       700             8956/13 =688.923077
EBITDA 4                        126           40302/325 =124.006154
Depreciation 4                   35             2239/65 =34.446154
NOPAT4                       68.25                       67.17
Net investment 4             11.375                      11.195
Change in NWC 4                  -3              282/65 =4.338462
Capex 4                      49.375         107387/2600 =41.302692
FCFF4                       56.875                      55.975
TV at date 3               710.9375                    699.6875

PRICING AND BUYER VALUE
The supplied illustrative asset-risk inputs 4%+1.2 x 5% give an operating required
return 10%, not a rate inferred from the 6% debt coupon. This is a nominal CU model.
Each operating path is a conditional expected forecast evaluated at stipulated
risk assumptions. Neither path is an exhaustive priced state; no physical or
risk-neutral probabilities are supplied. The debt's par quote is a separate
case input. Do not claim to derive its expected return, default price or a unique
probability-weighted acquisition value from this package.

TV3=FCFF4/(.10-.02). Discount it three years, and separately include FCFF3:
V0=FCFF1/1.1+FCFF2/1.1^2+(FCFF3+TV3)/1.1^3.
Total date 0 OPERATING DCF is 678.803531 base and 607.946281 downside.
These are NOT the date 3 terminal values shown above.

Before action, old equity=V0+60+30-250=V0-160. Selling the excluded asset simply
changes 30 of asset value into 30 of cash. Subscribing 70 adds 70 of cash and equity
value but also costs the buyer 70. The benchmark company opens with 160 cash;
post-subscription equity value=V0+160-250=V0-90. Total buyer outlay 500+8+70=578.
NPV=V0-668: +10.803531 base, -60.053719 downside. An immediate payout to the new
owner would subtract cash from company value and add the same owner receipt;
it creates no NPV under these assumptions and can impair funding.

The maximum seller price after the 8 fee is 510.803531 base and 439.946281 downside.
A stated rule requiring nonnegative NPV in both supplied forecasts uses 439.946281.
This is a conditional decision rule, not a probability-weighted optimal bid or a
claim that the two paths exhaust all risk. A lower seller price does not enter
company treasury automatically.

Terminal ROIC thresholds at fixed explicit cash, K3, r 10% and g 2% are 11.797739%
base and 13.142389% downside for seller price 500 and fee 8. Changing ROIC also
changes normalized EBITDA margin consistently through the turnover/tax identity.
When changing g, change net reinvestment AND the terminal denominator. The 9-cell
r/g grid for each scenario does both. Omitting growth investment overstates value.

DATED FUNDING
The benchmark sells the asset 30, subscribes 70 and cancels the proposed initial
payout 20. Start cash 160. Minimum cash is 30. The existing term debt pays 6% on
opening principal and repays 150/50/50 at ends 1/2/3. Revolver interest is 6% on its
opening balance; net year-end draws bear interest next year. Cash earns 4% on its
opening balance. At ends 1/2 the revolver limit is the smaller of 120 and
1.75 x current EBITDA minus remaining term debt. These are fictional commitments
with supplied change-of-control consent, no fees and no other acceleration.

For ends 1/2, first compute B=opening cash+cash interest+FCFF-term interest-
revolver interest-term principal repayment. Required closing revolver is
max(0,opening revolver+30-B). The net draw is its change from opening revolver.
If required debt exceeds the limit, report failure and the actual shortfall;
do not force cash to 30 or manufacture future periods from an unfunded balance.

At end 3 subtract the ENTIRE opening revolver as well as the final 50 term
principal. Only then use the explicit replacement note, if needed. It is issued
at par under an already-signed commitment with maximum face 80 and a second cap
of 1.75 x normalized year 4 EBITDA, conditional on prior compliance. It has NO
scheduled principal maturity, and 6% annual cash coupons begin at end 4. This
undated obligation remains outstanding; it has not disappeared. No future line
renewal, cash injection or waiver is assumed. The output shows its face, coupon
and year 4 cash after that coupon. With fixed coupon and growing FCFF, year 4 is
the lowest continuing operating cash in this bounded model.

                            BASE                         DOWNSIDE
End year                   1        2         3         1        2         3
Total debt interest       15        6   3.20964        15    8.412   7.08972
Closing cash            33.9       30  75.74636        30       30        30
Closing term             100       50         0       100       50         0
Closing revolver           0    3.494         0      40.2   68.162         0
Replacement note            0        0         0         0        0  32.70172

Base can distribute 45.74636 at date 3 and retain 30; downside cannot distribute
cash then. Its continuing note coupon is 1.9621032; year 4 cash after the coupon
and with 1.2 financial cash income is 55.2128968. Old term and revolver are zero.

Downside date 1 line capacity is 49.1, because 1.75 x 85.2-100=49.1, below 120.
With the asset sale and no initial payout, minimum date 0 equity is 3195/52
=61.442308. Without the sale it would be 91.442308, above the authorized 70.
With equity 70 and sale 30, maximum initial payout is 445/52=8.557692.
Extra downside year 1 NWC can be at most 8.9: closing NWC 116.9, or 21.648148%
of 540 sales. The delay releases at end 2; the later debt paths are also checked.
These are exact boundaries, not safe operating buffers.

The rejected branches show date 1 cash gaps: 95.1 without sale/subscription;
63.9 with sale only; 22.3 with equity 70 but no sale; 11.9 with the proposed
initial payout 20; 1.1 with additional year 1 collection delay 10. The last branch
would need extra date 0 equity 55/52=1.057692 but already uses the authorized 70.
Negotiating a lower purchase price alone cannot cure that corporate cash gap.

PEER CLAIMS AND NORMALIZATION
The entire five-candidate universe remains visible. Operating EV=market equity+
debt+NCI-financial cash-excluded nonoperating assets. Denominators are matched
normalized forward year 1 EBITDA, not trailing earnings or target year 4 EBITDA.
P1: EV 550, reported 90 plus documented 10 expense=100, multiple 5.5.
P2: EV 720, reported 144 minus temporary 24 bonus=120, multiple 6.
P3: EV 975 including 45 NCI, reported 160 minus 10 asset gain=150, multiple 6.5.
P4: EV 400/100=4; exclude the software business on economic comparability.
P5: EV 270 and EBITDA-5; no positive-profit multiple, retain distress evidence.
The three eligible multiples have median 6 and range 5.5-6.5. The ratio of summed
EV to summed EBITDA is 2245/370=449/74=6.067568; it is not the median.

Target normalized FORWARD YEAR 1 EBITDA is 108 base and 97.2 downside (18% of that
scenario's year 1 sales). Base implied EV 594/648/702 translates to old equity
434/488/542. Downside EV 534.6/583.2/631.8 translates to 374.6/423.2/471.8.
Base median equity 488 is below the seller's 500 before buyer fees. DCF and peers
are different conditional evidence; do not mechanically average them or treat
the narrow candidate range as a statistical confidence interval.

DECISION AND INTERVENTION
The illustrative committee rule is: the price must have nonnegative NPV in
both listed forecasts, every modeled funding date must be feasible, and any
departure needs an explicit approved premise. At 500 the benchmark is funded
but does not pass the valuation rule. Defer/negotiate a price no higher than
439.946281, obtain the specified commitments, preserve liquidity and investigate
terminal margins, customer collections and genuinely comparable peer economics.
An alternative risk preference may support a different decision, but must not
invent probabilities, waive the actual covenants or conceal the downside loss.

After independent submission, change downside year 1 NWC by +10 with release at
end 2 and terminal ROIC to 11.5%. The first change fails funding at date 1 by 1.1;
the second changes value to NPV -15.903362 base and -86.337998 downside, holding
the original explicit operating paths for that value sensitivity. Report them
as two distinct interventions. A funded combined model would also need to
price the collection-delay timing; the base benchmark does not assert that
terminal-only NPV includes it. The terminal-margin change leaves the 80 note
cap below the leverage limit. No automatic approval or extra equity follows.

LIMITATIONS AND SOURCES
This package prices operating forecasts at given risk assumptions; it does not
estimate betas, infer market probabilities, price defaulted claims or optimize a
general capital structure. Annual synchronized payments do not certify actual
daily liquidity. Terminal margins, growth and capital productivity are supplied
conditional economics, not forecasts established by evidence. Peer prices are
synthetic, and an excluded peer is not irrelevant to all risk questions.

Methods are taught in v08-c02, v08-c03, v08-c04, v08-c06, v08-c07, v08-c09,
v08-c11 and v08-c12. The assessment links
the existing verified primary methodological sources for growth/reinvestment,
terminal closure, project required returns and matched multiples. Their source
records are reused without claiming new market facts. All case data and code
are original. Author and coordinator computational reviews are not independent
human certification, financing approval or observed investment performance.
