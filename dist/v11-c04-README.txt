Merrow Risk Office: finite loss distributions and diagnostic limits
Volume11 chapter04 — original synthetic teaching laboratory

All probabilities and losses are stipulated physical cases, not observations,
pricing probabilities, empirical forecasts or regulatory capital definitions.
Positive numbers mean losses; negatives mean gains. Each case uses one common
horizon and currency unit CU. The horizon and backtest sections are separate
illustrations, not time-series estimates inferred from the finite cases.

RUN
Keep v11-c04-analysis.py and v11-c04-inputs.json together. Python3 with only its
standard library is sufficient. From any working directory:

python3 /path/to/v11-c04-analysis.py
python3 /path/to/v11-c04-analysis.py --input /path/to/copy.json --output /path/to/result.json

Without --output, JSON is printed. Importing the module writes nothing.
run(data) is quiet and does not change data. Validation is active under python3 -O.
Output cannot replace the selected input or model itself. Invalid input fails
before replacing an existing output; a file-system write failure is reported.
This is a bounded classroom tool, not a hostile-input or settlement service.

INPUT CONTRACT
Exact top-level keys: schema, provenance, units, cases, horizon, backtest.
schema is integer1. provenance/units are nonempty descriptive strings of at most
1000 characters. They label the user's assumptions; software does not verify
their truth. A decimal input is a string with at most10 integer digits and10
fractional digits. No exponent, fraction literal, float, Boolean or infinity.

There are1–8 cases. Each has id, confidence, assets, holdings, states.
Case/asset/state IDs start with a letter, contain only letters/digits/underscore,
and have at most40 characters. IDs are unique within their respective scopes.
Each case has1–8 assets, matching signed holdings in[-10,10], and1–64 states.
Each state has id, probability and matching losses per asset in[-1000000,1000000].
Each probability is strictly positive; probabilities sum exactly to1. Omit
zero-mass rows. Confidence is strictly between0 and1. Losses already reflect
whatever date/cash/valuation convention the user chose; the code does not
generate prices or calculate financing. The joint rows, not just marginals,
define the dependence of held component losses.

horizon has days (integer1–250), daily_mean_loss[-1000000,1000000],
daily_sd_loss[0,1000000], lag_correlation strictly between-1 and1, and confidence
in[.5,.9999]. Its covariance law is SD^2*rho^lag. Daily loss is additive and
stationary; the normal VaR/ES additionally assumes joint normality. A zero SD
means deterministic loss. This block is an assumption calculation, not a fit.

backtest has trials (integer1–500), exception_probability strictly between0 and1,
and exception_positions: a sorted unique list of integer days from1 to trials.
This means forecast-before-observation strict exceptions under a predeclared
definition. The count calculation assumes independent Bernoulli trials with
the known constant probability. Probability atoms, overlapping horizons,
model estimation and selected windows can invalidate that interpretation.
The program has no realized loss magnitudes and cannot assess severity.

CALCULATION AND OUTPUT
Finite cases use Fraction arithmetic. Outputs are exact rational strings,
including integers; e.g.516/5 is103.2. Input decimal strings define exact decimal
fractions rather than rounded binary values. Floating transcendental diagnostics
are explicitly named *_approx; their final bits can vary across platforms.

VaR is inf{x:F(x)>=alpha}, implemented by sorting losses and accumulating mass.
ES fills exactly1-alpha mass from the greatest losses down. At the boundary,
only the needed part of a tied loss is included. Each selected mass is divided
by1-alpha to give a feasible dual weight; the resulting loss average equals ES.
The positive-part objective at VaR is an independent mathematical certificate,
though this model's two implementations are not a substitute for outside review.

tail_allocation records every supplied state's loss, available and selected
mass, dual weight and ES contribution. Tied states are filled in reverse input
order. Reordering rows may choose a different optimizer at equal losses but
does not change VaR/ES. Strict/weak conditional tail means are diagnostics:
neither generally equals ES at an atom. The strict mean is null if its event
has zero probability. Negative holdings trigger complete loss reordering;
the program does not negate a previously calculated positive-position risk.

The horizon block expands the full covariance sum, then applies the stipulated
normal formula. Its mean/variance/factor are exact fractions; SD and normal
VaR/ES use standard-library floating arithmetic. The backtest computes the
exact binomial upper tail with rational arithmetic then converts to float.
At extreme parameter values the displayed probability can underflow to0;
that floating0 is not a proof that an event is impossible. Longest run and
adjacent pairs are descriptive; no independence test or selection correction
is implemented. See the chapter for a separately proved seven-run union bound.

BASELINE ANCHORS
atom: losses0/.90,10/.05,100/.05; alpha.925; VaR10,ES70.
Its strict conditional tail mean is100 and weak mean55. At alpha.95, left VaR
is10 and ES100. Fractional boundary inclusion matters.
independent: each sleeve loses100 with probability.04; sum VaR95=100,ES95=103.2.
common_mixture: one quarter common mechanism; same marginals; sumVaR100,ES122.4.
comonotone: both lose together; sumVaR0,ES160. VaR can fall as tail severity rises.
Every individual sleeve in those three cases hasVaR0,ES80 under its common law.

Ten-day covariance case: mean0, dailySD2, rho.3, alpha.99.
Variance69.387784024; SD8.329933014; normalVaR19.378321959; normalES22.201055924.
Ignoring dependence instead gives variance40, not69.387784024.
250 trials atp.01 with exceptions on days40–46: count7, expected2.5,
one-sided count probability about.0137014478552, longest run7, adjacent pairs6.
Moving the same exceptions apart leaves the count probability unchanged.

MEANINGFUL NEW CASES
1. Change alpha around an exact cumulative boundary. Check the left quantile
   separately from the tail mean and all minimizing threshold values.
2. Add a certain loss or multiply all losses by a positive factor; verify the
   corresponding translation or scaling. Short the position and re-sort.
3. Change dependence while preserving marginals; verify both joint probabilities
   and marginal totals before comparing portfolio tails.
4. Change serial covariance, mean, horizon or the null exception probability.
   State which formulas still follow from those new assumptions.
5. Reorder tied rows and verify risk invariance without requiring identical tail
   allocations. Check zero SD and all-gain or constant-loss cases.

The manifest binds input/model/reference-output/README bytes. Integrity detects
changed files; it does not establish the assumptions or forecast performance.
The chapter's solutions and checker independently derive risk quantities,
tail certificates, covariance sums, count probabilities and changed cases.
No empirical calibration, all-state loss bound, actual liquidity, regulatory
compliance or commercial approval follows from any numerical result here.
