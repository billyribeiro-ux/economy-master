Oriole Components: financing contracts and incentives
Volume 8, Chapter 5 — original fictional one-period lab

PURPOSE AND FILES
The packet reconstructs the five worked cases. It distinguishes a fixed
operating payoff from a financing-induced payoff change, new-debt pricing
from old-claim gains/losses, and an information model's candidate price
from a price that is consistent with the types actually issuing.

Save v08-c05-analysis.py and v08-c05-inputs.json in the same directory.
Run with standard-library Python 3:
    python3 v08-c05-analysis.py
Or supply a copy of the input packet:
    python3 v08-c05-analysis.py changed-inputs.json
The default input path is beside the script, independent of working directory.
The script reads one input file, writes no files, accesses no network and prints
strict JSON. v08-c05-output.json is the preserved default output. Rational
fractions are exact internally; conversion to decimal is only for JSON display.
Input numerical values are integers or strings such as "0.05" and "1/2".

UNITS, DATES AND VALUATION
All money is kCU. Financing, fees and investment occur at date 0; all operating
and claimant receipts occur at date 1. There is no terminal continuation.

The first two cases use physical probabilities (1/2,1/2), positive valuation
weights (3/5,2/5) and a 5% risk-free rate. Price a state cash pair C by
    P(C) = (0.6*C_low + 0.4*C_high)/1.05.
This is also the replicating price from the traded operating claim (84,168)
at price 112 and a risk-free claim. Physical probabilities compute expected
returns. They must not replace valuation weights when pricing risky cash.

The agency and information cases are SEPARATE hypothetical settings with
risk neutrality and zero interest. State means equal prices in those settings;
that assumption is explicit and is not a general way to value real corporate
risk. The information prior concerns a private asset type, not the first
cases' market-state law.

CONTRACT SEQUENCES
MM: operating investment and total state cash are fixed; no tax, default cost,
issue cost, agency choice or private information. Debt receives min(F,X) and
equity the residual. Both claims are priced consistently, including default.

Tax/distress: debt face is fixed for each of the three choices. If X >= F,
repay debt in full, then receive a fictional tax refund of tax_rate*(F-D).
If X < F, the resource cost is removed from X; debt receives the remainder;
equity receives zero and no tax refund/carryforward exists. There is no bridge
borrowing against a refund. D is the rational date-0 price of the resulting
creditor cash, not the face amount. Fees are paid from proceeds at date 0.
This is a deliberately explicit fictional tax rule, not a jurisdiction's law.

Risk shifting: shareholders choose the larger equity value after terms are
fixed. fair_face finds a face funding 80 at the price of each anticipated
policy; the code then checks whether that policy is optimal for equity at
those same terms. Only incentive-compatible policy/price pairs are reported.
It does not assume a lender pays for a prudent policy that will be abandoned.
A covenant makes the prudent policy enforceable and incurs the supplied fee.

Overhang: new cash increases the value of an unchanged old debt claim. A
creditor contribution is conditional on jointly funding the stated project.
The senior-loan alternative requires all affected creditors' consent; the
model does not grant unilateral power to change priority. The junior loan is
priced on what remains after old creditors. Neither loan is free wealth.

Information: no cash, debt, separate asset sale or other financing route is
available in the equity-only scenario. Managers know the type and maximize
eventual old-owner receipts, with no sale at a misleading temporary quote.
The model checks both types at the pooling price, then the explicit low-only
issuing candidate with conditional beliefs. It reports whether that candidate
is valid; it is not a general search for every possible signaling equilibrium.
The separate safe-debt alternative explicitly relaxes the financing menu.

DEFAULT ANCHORS
* Operating value 112 and expected return 12.5%. Faces 63/105 produce debt
  values 60/88 and equity 52/24. Expected equity returns are 21.153846%/31.25%.
* The tax/distress menu gives owner wealth 112, 112.464286 and 106.5.
  Moderate debt wins only among those three choices.
* Old face 80: prudent debt/equity 80/20 versus gamble 60/35; total loss 5.
  New funding 80 requires face 120 under the gamble; equity then equals 15.
  The gamble is optimal for equity at those terms. Covenant wealth is 98.
* Overhang: project NPV 6, old-debt gain 8 and equity-funded NPV -2.
  Creditor contribution 4 gives gains 4 to that creditor and 2 to equity.
  Feasible weak-gain contributions are [2,8]. Junior finance leaves equity
  13; a consented senior loan leaves old debt 68 and equity 18.
* Pooling fraction 5/36 fails the high-type incentive. Low-only fraction 5/26
  gives low owners 84 and a high-type deviation 148.615385 < 160. Expected
  project NPV forgone is 2. Safe debt permits owner values 84 and 164.

SUPPORTED CHALLENGES
1. Set pricing_case.tax_rate to "0". Debt receipts/prices are unchanged, but
   owner wealth is 112, 111.75 and 102.428571. The no-debt choice wins.
2. Restore tax "1/4" and set distress_cost to "0". Keep all faces fixed.
   The high debt's recovery rises and its price must be recomputed; its
   promised interest F-D and tax refund therefore change too. Explain the
   result before reading the JSON. Do not hold its price at 90.
3. Set risk_shifting.covenant_fee to "6". Its wealth becomes 94, below the
   unrestricted 95. This compares a specified commitment cost, not all
   possible governance mechanisms.
4. Change overhang.creditor_contribution to "1" or "9". Funding still sums
   to 10, but one old party loses, so repair_individually_acceptable is false.

LIMITS
Positive pricing weights and the cash rules define internally consistent
fictional finite contracts. They are not estimated market inputs, tax advice,
credit commitments or an insolvency process. The supported changes above
retain the stated operating/information structure. Arbitrary changes can
require new contracts or equilibria; the program's domain checks are not a
general proof of economic applicability. Repricing is distinct from obtaining
consent to change an existing creditor's rights. No bankruptcy probabilities,
announcement returns or industry leverage observations are imported.

In the source repository, python3 book/scripts/check_v08_c05.py (from the
repository root) performs the independent focused checks. Its check() function
is quiet and returns a JSON-serializable report. Whole-library integration and
visual/mobile/print inspection are separate review gates.
