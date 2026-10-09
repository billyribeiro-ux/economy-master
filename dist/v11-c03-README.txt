MORROW COMPONENTS: CREDIT ANALYSIS AND LENDING DECISIONS
Volume11 Chapter03; original synthetic teaching case, 9October2026

PURPOSE AND STATUS
This package compares two proposed loans against explicit cash, covenant,
leverage, collateral, scenario-return and evidence assumptions. It is a
bounded teaching implementation, not a current borrower file or lending
authorization. Author completion and separate peer/coordinator acceptance are
different gates; the chapter remains a draft until accepted in the curriculum.

The borrower purchases a130CU plant. Requested loan120 plus sponsor20 leaves
10CU cash; proposed loan80 plus sponsor60 also leaves10. All monetary amounts
are fictional CU. Years1,2,3 are annual end dates, not calendar observations.
Operating cash arrives before the payment at each date. Cash earns no interest,
there are no dividends or automatic new loans, and no intra-year liquidity
claim is made. Sources must actually arrive; evidence flags are declarations
in the synthetic file, not authentication of real documents.

FILES
v11-c03-inputs.json: original scenario, contract, asset and policy inputs.
v11-c03-analysis.py: standalone standard-library implementation.
v11-c03-output.json: complete reference output, including each dated row.
v11-c03-manifest.json: SHA256 and byte length of inputs, code, output, README.
v11-c03-README.txt: this execution/model/domain contract.

The chapter HTML gives four worked examples, eight original exercises with
complete solutions, the cash-feasibility proof, incentive calculations and
answered teach-back/retention. The author checker is a separate repository
file, scripts/check_v11_c03.py. It is not required to run the portable lab.

EXECUTION
From any working directory, with paths adjusted to the copied files:
  python3 v11-c03-analysis.py --input v11-c03-inputs.json --output result.json
  python3 -O v11-c03-analysis.py --input v11-c03-inputs.json --output result-O.json

With no --input, the program loads v11-c03-inputs.json beside its own script.
With no --output, it prints one JSON document to stdout. With --output it
writes that JSON document and produces no successful stdout/stderr. Validation
errors give a nonzero exit, including under optimized Python. The output may
not overwrite the input file or implementation, including existing symbolic
or hard-link aliases. Invalid inputs do not replace
an existing output. No dependency installation, network or other chapter code
is used. Copying the implementation and inputs together is sufficient.

QUIET API
  import json, runpy
  model = runpy.run_path("v11-c03-analysis.py")
  with open("v11-c03-inputs.json", encoding="utf-8") as source:
      data = json.load(source)
  result = model["run"](data)

Import and run(data) print nothing and write nothing; run does not mutate data.
It returns a fresh dictionary/list structure that can be serialized with
json.dumps(result, allow_nan=False). Checks do not rely on assert statements.

INPUT GRAMMAR AND BOUNDS
All financial quantities are JSON strings, not JSON numbers or booleans.
Accepted forms are an optional minus followed by a plain integer, decimal or
rational fraction. Integer parts have1-6digits and no leading zeros except0;
decimals have1-8digits after the point; positive fraction numerators and
denominators each have1-6digits with no leading zeros. Examples: "0", "0.08",
"-5", "1/10". Negative fractions are allowed by grammar. Zero is written"0",
not"0/2". Maximum length is24characters. A leading decimal point, plus sign,
whitespace, exponent, negative/zero denominator or nonfinite token is rejected.
The CLI also rejects duplicate JSON keys and NaN/Infinity/-Infinity constants;
input files are bounded to1,000,000bytes. A parsed API dictionary cannot retain
duplicate keys, so callers must enforce duplicate rejection when parsing
untrusted JSON before run(data).

Only documented keys are accepted at every object level. Lists must really
be lists. IDs are unique within their collection and match a lower-case ASCII
letter followed by up to31lower-case letters, digits or underscores. Three
annual entries are required in every financial vector. Default dates/counts
must be genuine JSON integers, excluding booleans. Evidence values must be
genuine booleans. Financial inequalities and thresholds use exact rationals.

Top-level keys: schema, provenance, business, scenarios, proposals, collateral,
policy. Schema is"v11-c03-morrow-1"; provenance must exactly equal the supplied
synthetic provenance sentence. These fixed labels keep observed and invented
inputs from being silently interchanged.

business:
  capital_purchase: [1,999999].
  depreciation: three values in[0,999999].
  valuation_hurdle: [0,.5], annual compound assessment for the illustrative
    enterprise calculation, separate from loan coupons and recovery assessment.
  terminal_operating_value: [0,999999], conditional going-concern value atyear3.

scenarios:2-4rows, exactly one ID"base". Each has id and three-entry vectors:
  ebitda in[-999999,999999]; cash_taxes and maintenance_capex in[0,999999];
  working_capital_increase in[-999999,999999]. A negative increase releases cash.
Scenarios are unweighted operating stresses. They are not the two exhaustive
states used in the separate default-branch comparison.

proposals:1-4rows, each with:
  id; advance in[1,999999]; sponsor_cash in[0,999999]; rate in[0,.5];
  principal: three nonnegative amounts in[0,999999] summing exactly to advance.
  Every year's interest plus principal must be positive. A positive-coupon
  bullet schedule is supported; a schedule leaving a zero-service year is not.
  evidence: exactly sponsor_cash_verified, cash_forecast_verified,
    priority_verified, all booleans.
An economically underfunded sources/uses combination is accepted as data and
reported as a financial failure, not rejected as malformed. Every proposal's
opening cash is recomputed from advance+sponsor_cash-capital_purchase.

collateral:
  default_year: integer1-3, immediately BEFORE that year's scheduled payment.
  recovery_delay_years: integer0-3; receipt is at default_year+delay, including
    dates beyond the original maturity. No postdefault interest is added.
  assets:1-6rows, each with id, gross_value in[0,999999], eligible_fraction and
    realization_fraction in[0,1]. Fractions apply successively to gross value.
  workout_cost, prior_claim: each[0,999999]. Costs rank first, prior claim next,
    this lender next, then juniors. Prior claim is a stipulated workout claim,
    not an omitted scheduled interest-bearing debt in the operating forecast.
  assessment_rate: [0,.5], chosen annual compound discount for the branch cash.
  physical_default_weight: [0,1], stipulated weight on the one default branch.

policy:
  minimum_cash:[0,999999]; minimum_base_dscr:[1,3];
  maximum_initial_debt_ebitda:[.25,10]; minimum_scenario_margin:[0,999999].
These are invented teaching thresholds, not present regulatory requirements.
The base threshold is also the proposed contract's annual DSCR warning level
in the chapter. Downside breaches are reported even when cash remains adequate.

OPERATING AND FUNDING IDENTITIES
CFADS=EBITDA-cash taxes-maintenance capex-working-capital increase. It is before
interest and principal. The displayed net-income example assumes tax expense
equals cash tax and subtracts depreciation and cash interest from EBITDA.
The tax vectors are scenario assumptions held fixed when financing changes;
the code does not infer an actual interest tax shield or tax regime.

Opening principal is advance minus earlier principal repayments. Interest is
rate times that opening principal; service is interest plus scheduled principal.
Cash is initial sources less the capital purchase, plus cumulative CFADS less
cumulative debt service. No liquidation proceeds enter this operating ledger.
Negative full-contract projected balances identify missing finance. They do
not establish an authorized negative account, actual payment after a failure,
or a workout policy. First_payment_shortfall_year0 means closing itself cannot
be funded; later positive year labels mark the first scheduled shortage.

The minimal initial addition needed for a cash floor is
max(0, minimum_cash-minimum of opening and all end-date projected cash).
This follows because a fixed initial addition shifts every balance equally.
It assumes the same debt schedule, no cash interest and no additional spending
of the injection. DSCR does not include opening cash. A DSCR below1 can coexist
with funded debt service, and an acceptable DSCR can coexist with an unfunded
plant purchase or unavailable cash before an annual date.

The illustrative enterprise PV distributes base CFADS each year and returns
minimum_cash plus terminal_operating_value atyear3; initial uses are purchase
plus minimum_cash. It uses its separate chosen valuation hurdle. It is not
the retained-cash loan ledger, a traded price or a guaranteed primary repayment
source. Working capital and maintenance are already deducted in CFADS.

DEFAULT WATERFALL AND SCENARIO COMPARISON
The separate default branch assumes earlier scheduled instalments were paid,
current payment has not occurred, no other estate cash is available, and later
operating cash ceases. It is a distinct hypothetical state, not a continuation
of a cash projection after its first failure. Current claim is opening principal
plus that year's coupon; all future unearned coupons are excluded.

Gross sale cash sums gross*eligible*realization. Pay costs capped at gross, then
prior claim capped at what remains, then this lender capped at both its claim
and remaining cash. Residual belongs to juniors. Unpaid higher-ranking items
are reported separately. Costs+prior+lender+residual equals gross cash. Changing
claim, rate, default date or sale assumptions recomputes the entire waterfall.

Discount recovery from its actual receipt date. Discounted recovery at default
differs from a time-zero PV and from nominal claim recovery. A delayed receipt
does not fund a previous payment date. The branch discount rate is an assumed
assessment rate; no state prices or Q law are inferred.

Promised receipt PV includes all scheduled debt service. Default-branch PV
includes prior payments and the sole delayed recovery, with no double counting
of future operating receipts or going-concern terminal value. The weighted PV
is (1-p)*promisedPV+p*defaultPV. Margin subtracts the actual advance. Additional
origination, servicing, funding or capital costs beyond the chosen hurdle are
not supplied; any separately assessed costs reduce this margin. The physical
weight is invented, not estimated from two stress paths or from the coupon.

DECISION, REPRODUCTION ANCHORS AND LIMITATIONS
Six gates must all pass: funded initial sources/uses; base DSCR floor; positive-
EBITDA leverage limit; every scenario's cash floor; assumed scenario margin;
all three evidence flags. Nonpositive base year1 EBITDA gives a null leverage
ratio and a failed leverage gate. Any quantitative failure returns
"restructure_or_refuse". Passing quantities but missing evidence gives
"hold_for_evidence". All gates passing gives
"eligible_for_credit_committee_review", never actual loan approval.

Baseline CFADS40/42/44; downturn30/34/38. Requested service52/48/44 gives base
closing cash-2/-8/-8 and downside-12/-26/-32. Initial leverage2 and base DSCRs
10/13,7/8,1 fail the stated gates. A positive conditional enterprise NPV
31.750563486 or requested assumed lender margin4.701599307 does not cure them.

Revised service26.4/34.8/32.4; base cash23.6/30.8/42.4; downside13.6/12.8/18.4.
Base DSCRs50/33,35/29,110/81 and initial leverage4/3 meet their limits.
Year2 downside DSCR85/87 is below1, while cash remains12.8. Increasing only that
year's working-capital use by2.8 leaves exactly10;2.80000001 fails the cash floor.
All downside annual ratios are below1.2: monitor and address covenant rights;
no automatic acceleration or waiver is modeled by the cash projection.

At year2 default, revised claim64.8; sale proceeds54+24=78; costs8 and prior15
leave55, paid atyear3. Nominal loss9.8; recovery discounted to default at6% is
51.886792453, giving timing-adjusted shortfall12.913207547. At p=.12, promised
PV83.081201260 and default PV71.084720944 imply weighted PV81.641623622 and
margin1.641623622. Revised sponsor funds and priority are not verified, so the
baseline revised recommendation is hold_for_evidence. The chapter supplies
the proposed evidence, covenant response, monitoring and refusal conditions.

Verification uses independent cumulative cash identities, direct dated branch
streams, waterfall conservation/caps and boundary interventions. Normal and
optimized isolated API/CLI checks target noise, mutation and invalid domains.
Hashes bind bytes, not economic truth. A false financial assumption can be
implemented exactly. No sampled default frequency, market pricing accuracy,
jurisdictional enforceability or actual borrower approval follows.

SOURCE SCOPE
The chapter cites the historical OCC Commercial Loans Section206 booklet,
narrative March1990/procedures March1998, with its March2025 removal notice,
only for repayment/collateral/documentation methods. All Morrow values,
thresholds, proofs, incentives and code are original. The exact inspected
primary sections and source limits are in the chapter's author source record.
