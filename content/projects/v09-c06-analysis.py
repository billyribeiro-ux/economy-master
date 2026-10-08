"""Ilex factor research desk: original finite, exact teaching cases.

Standard-library only. Import/run are quiet; CLI emits strict JSON and never
writes a file. Cases are separate economies, samples and trading ledgers.
"""
from fractions import Fraction as F
from itertools import product
import json
import math
from pathlib import Path
import sys


def need(condition, message):
    if not condition:
        raise ValueError(message)


def q(value):
    need(isinstance(value, (int, str)) and not isinstance(value, bool),
         "Use integer or rational/decimal strings, not binary floats or booleans")
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("Invalid rational input") from error


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    return value


def average(values):
    need(len(values) > 0, "An empty sample has no mean")
    return sum(values, F(0)) / len(values)


def dot(a, b):
    need(len(a) == len(b), "Vector lengths must agree")
    return sum((x*y for x, y in zip(a, b)), F(0))


def solve(matrix, rhs):
    """Small exact Gaussian elimination, rejecting deficient rank."""
    n = len(rhs)
    need(n > 0 and len(matrix) == n and all(len(row) == n for row in matrix),
         "Square matched system required")
    aug = [list(row) + [v] for row, v in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if aug[i][col] != 0), None)
        need(pivot is not None, "Rank-deficient design: coefficients are not identified")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [x/scale for x in aug[col]]
        for i in range(n):
            if i != col:
                scale = aug[i][col]
                aug[i] = [a-scale*b for a, b in zip(aug[i], aug[col])]
    return [row[-1] for row in aug]


def fit(design, y, intercept):
    n = len(y)
    need(n > 0 and len(design) == n and len(design[0]) > 0,
         "Nonempty matched design and response required")
    k = len(design[0])
    need(n > k and all(len(row) == k for row in design),
         "Matched rows and positive residual degrees of freedom required")
    need(not intercept or all(row[0] == 1 for row in design),
         "Intercept specification needs an explicit first column of ones")
    gram = [[sum(row[i]*row[j] for row in design) for j in range(k)] for i in range(k)]
    cross = [sum(row[i]*v for row, v in zip(design, y)) for i in range(k)]
    coef = solve(gram, cross)
    fitted = [dot(row, coef) for row in design]
    residuals = [v-pred for v, pred in zip(y, fitted)]
    sse = dot(residuals, residuals)
    center = average(y)
    sst = sum((v-center)**2 for v in y)
    return {"coefficients": coef, "fitted": fitted, "residuals": residuals,
            "normal_equation_residuals": [sum(row[i]*e for row, e in zip(design, residuals)) for i in range(k)],
            "sse": sse, "centered_sst": sst, "residual_degrees_of_freedom": n-k,
            "residual_mean_square_df": sse/(n-k),
            "r_squared_with_intercept": 1-sse/sst if intercept and sst > 0 else None}


def pricing_case(data):
    rf = q(data["safe_gross"])
    coefficients = [q(x) for x in data["kernel_sign_coefficients"]]
    scales = [q(x) for x in data["factor_shock_scales"]]
    beta = [q(x) for x in data["replica_factor_exposures"]]
    residual_scale, quote = q(data["priced_residual_scale"]), q(data["clone_quote"])
    need(rf > 0 and len(coefficients) == 3 and len(scales) == len(beta) == 2,
         "Positive safe gross and the stated three-sign/two-factor dimensions required")
    need(sum(abs(x) for x in coefficients) < 1 and all(x > 0 for x in scales),
         "Affine kernel must be strictly positive in every sign state; factor scales positive")
    need(residual_scale >= 0 and 0 < quote < 1,
         "Nonnegative residual scale and an underpriced positive clone quote below its fair unit price required")
    premiums = [a*s for a, s in zip(coefficients[:2], scales)]
    alpha = coefficients[2]*residual_scale
    rows = []
    for u, v, e in product((-1, 1), repeat=3):
        signs = [F(u), F(v), F(e)]
        kernel = (1-dot(coefficients, signs))/rf
        factors = [mu+s*z for mu, s, z in zip(premiums, scales, signs)]
        exact_excess = dot(beta, factors)
        residual = residual_scale*e
        priced_excess = exact_excess+alpha+residual
        need(all(rf+x >= 0 for x in factors+[exact_excess, priced_excess]),
             "This fixture's fully paid long claims require nonnegative terminal payoffs")
        # Long clone, short its factor-fund/cash replica, invest initial saving.
        safe_position = sum(beta)-1+(1-quote)
        arbitrage_payoff = (rf+exact_excess)-dot(beta, [rf+x for x in factors])+safe_position*rf
        rows.append({"signs": signs, "physical_probability": F(1, 8), "sdf": kernel,
                     "state_price": kernel/8, "factor_excess_payoffs": factors,
                     "replicated_gross_payoff": rf+exact_excess,
                     "priced_residual_gross_payoff": rf+priced_excess,
                     "residual": residual, "clone_arbitrage_payoff": arbitrage_payoff})
    em = average([row["sdf"] for row in rows])
    variance_m = average([(row["sdf"]-em)**2 for row in rows])
    cov_m_e = average([row["sdf"]*row["residual"] for row in rows])
    return {"states": rows, "factor_expected_excess_payoffs": premiums,
            "replica_safe_weight": 1-sum(beta), "replica_expected_excess_return": dot(beta, premiums),
            "priced_residual_alpha": alpha, "priced_residual_mean_excess": dot(beta, premiums)+alpha,
            "sdf_mean": em, "sdf_variance": variance_m, "sdf_residual_covariance": cov_m_e,
            "residual_alpha_bound": math.sqrt(float(variance_m))/float(em)*float(residual_scale),
            "factor_prices": [average([row["sdf"]*row["factor_excess_payoffs"][j] for row in rows]) for j in range(2)],
            "replicated_claim_price": average([row["sdf"]*row["replicated_gross_payoff"] for row in rows]),
            "priced_residual_claim_price": average([row["sdf"]*row["priced_residual_gross_payoff"] for row in rows]),
            "clone_arbitrage_initial_cost": quote-sum(beta)+(sum(beta)-quote),
            "clone_arbitrage_safe_position": sum(beta)-quote,
            "clone_arbitrage_sure_payoff": (1-quote)*rf}


def diversification_case(data):
    scale, tilt, rf, bound = [q(data[k]) for k in
                             ("residual_scale", "pricing_tilt", "safe_gross", "hypothetical_uniform_sdf_cv_bound")]
    counts = data["asset_counts"]
    need(scale > 0 and 0 < tilt < 1 and rf > 0 and bound > 0,
         "Positive scale/rate/bound and a strictly positive product-kernel tilt in (0,1) required")
    need(counts and all(type(n) is int and 1 <= n <= 100 for n in counts) and len(set(counts)) == len(counts),
         "Use distinct integer asset counts from 1 through 100 in this bounded lab")
    rows = []
    for n in counts:
        loss_count = sum(math.comb(n, k) for k in range(n+1) if tilt+F(2*k, n)-1 < 0)
        cv_squared = (1+tilt**2)**n-1
        rows.append({"assets": n, "average_expected_payoff": tilt*scale,
                     "average_residual_variance": scale**2/n,
                     "worst_average_payoff": scale*(tilt-1),
                     "physical_probability_of_loss": F(loss_count, 2**n),
                     "product_sdf_cv_squared": cv_squared,
                     "product_sdf_minimum": (1-tilt)**n/rf,
                     "hypothetical_uniform_bound_on_mean": float(bound*scale)/math.sqrt(n)})
    return {"rows": rows, "pricing_formula": "m_N=(1/Rf)*product(1-a*E_i); z_i=sigma*(a+E_i), independent equiprobable signs",
            "zero_cost_pricing_identity": "E[m_N*z_i]=sigma/Rf*(a-a)=0; not a sure finite arbitrage",
            "scope": "No uniform SDF variation bound is imposed on this product-kernel sequence; the supplied separate bound is a hypothetical additional restriction"}


def empirical_case(data):
    observations = data["observations"]
    need(len(observations) >= 4, "At least four matched observations for two factors and an intercept")
    dates = [row["period"] for row in observations]
    need(all(type(x) is int for x in dates) and dates == sorted(set(dates)), "Sample periods must be distinct increasing integers")
    f1 = [q(row["factor_1"]) for row in observations]
    f2 = [q(row["factor_2"]) for row in observations]
    y = [q(row["asset_excess"]) for row in observations]
    full = fit([[F(1), a, b] for a, b in zip(f1, f2)], y, True)
    short = fit([[F(1), a] for a in f1], y, True)
    mean1, mean2 = average(f1), average(f2)
    var1 = sum((a-mean1)**2 for a in f1)
    need(var1 > 0, "Omitted-factor comparison needs variation in factor one")
    projection_slope = sum((a-mean1)*(b-mean2) for a, b in zip(f1, f2))/var1
    beta = [[q(x) for x in row] for row in data["cross_section_betas"]]
    means = [q(x) for x in data["cross_section_mean_excess"]]
    need(all(len(row) == 2 for row in beta), "Cross-section has two supplied prior-window beta estimates")
    cross = fit(beta, means, False)
    return {"sample_factor_means": [mean1, mean2], "sample_asset_excess_mean": average(y),
            "two_factor_ols": full, "one_factor_ols": short,
            "omitted_factor_projection_slope": projection_slope,
            "cross_section_no_free_intercept": cross,
            "cross_section_lambda_minus_sample_factor_means": [a-b for a, b in zip(cross["coefficients"], [mean1, mean2])],
            "scope": "Descriptive synthetic samples and supplied prior-window beta estimates; no population-pricing, causal, confidence-level or investable-premium claim"}


def construction_case(data):
    names, observations = data["assets"], data["observations"]
    need(len(names) == 4 and len(set(names)) == 4 and len(observations) == 4,
         "This ranking fixture uses four distinct assets and four one-period records")
    notional, cash, trading_rate, borrow_rate = [q(data[k]) for k in
                                                ("fixed_long_notional", "initial_collateral", "one_way_trading_cost", "short_borrow_cost_per_period")]
    need(notional > 0 and cash > 0 and 0 <= trading_rate < 1 and 0 <= borrow_rate < 1,
         "Positive fixed notional/collateral and cost fractions in [0,1) required")
    initial = cash
    prices, shares = [F(100)]*4, [F(0)]*4
    records = []
    gross_sum = trading_sum = borrow_sum = F(0)
    for period, item in enumerate(observations, 1):
        start, end, available = item["start"], item["end"], item["signal_available"]
        need(all(type(x) is int for x in (start, end, available)) and (start, end) == (period-1, period) and available <= start,
             "Sequential model periods and information available no later than the trade required")
        signals, returns = [q(x) for x in item["signals"]], [q(x) for x in item["simple_returns"]]
        need(len(signals) == len(returns) == 4 and len(set(signals)) == 4 and all(r > -1 for r in returns),
             "Four distinct signals, matched returns and strictly positive closing asset prices required")
        rank = sorted(range(4), key=lambda i: signals[i])
        weights = [F(1, 2) if i in rank[2:] else F(-1, 2) for i in range(4)]
        opening = cash+dot(shares, prices)
        target = [notional*w/p for w, p in zip(weights, prices)]
        change = [a-b for a, b in zip(target, shares)]
        volume = sum(abs(d)*p for d, p in zip(change, prices))
        trading_cost = volume*trading_rate
        cash -= dot(change, prices)+trading_cost
        need(cash >= 0, "Fixture would require an unmodeled cash loan at rebalancing")
        shares = target
        gross = dot([notional*w for w in weights], returns)
        prices = [p*(1+r) for p, r in zip(prices, returns)]
        close_values = [s*p for s, p in zip(shares, prices)]
        borrow = notional*borrow_rate
        cash -= borrow
        closing_volume = F(0)
        if period == len(observations):
            closing_volume = sum(abs(v) for v in close_values)
            closing_cost = closing_volume*trading_rate
            cash += sum(close_values)-closing_cost
            shares = [F(0)]*4
            trading_cost += closing_cost
        wealth = cash+dot(shares, prices)
        need(cash >= 0 and opening > 0 and wealth > 0, "Fixture needs nonnegative cash and positive observed equity; no margin/insolvency engine")
        need(wealth == opening+gross-trading_cost-borrow, "Dated cash ledger does not reconcile")
        hindsight = sorted(returns)
        hindsight_payoff = (sum(hindsight[2:])-sum(hindsight[:2]))/2
        records.append({"period": period, "beginning_factor_weights": weights,
                        "opening_equity": opening, "rebalance_dollar_volume": volume,
                        "liquidation_dollar_volume": closing_volume, "trading_cost": trading_cost,
                        "borrow_cost": borrow, "gross_factor_payoff_per_notional": gross/notional,
                        "gross_cash_profit": gross, "end_values_before_liquidation": close_values,
                        "cash_after_events": cash, "ending_equity": wealth,
                        "account_simple_return": wealth/opening-1,
                        "unavailable_hindsight_gross_factor": hindsight_payoff})
        gross_sum += gross
        trading_sum += trading_cost
        borrow_sum += borrow
    return {"periods": records, "gross_cash_profit": gross_sum,
            "total_trading_cost": trading_sum, "total_borrow_cost": borrow_sum,
            "final_cash": cash, "final_positions": shares, "investor_cumulative_return": cash/initial-1,
            "mean_gross_factor_per_notional": average([row["gross_factor_payoff_per_notional"] for row in records]),
            "mean_unavailable_hindsight_gross_factor": average([row["unavailable_hindsight_gross_factor"] for row in records]),
            "scope": "Fixed long100%/short100% of stated notional, not of changing equity; zero cash interest, reusable short proceeds, no interim margin calls, all final positions closed"}


def run(data):
    expected = {"pricing": "one period, eight equiprobable independent sign states; safe and factor funds initially cost one; unrestricted frictionless positions",
                "factor_units": "zero-cost terminal payoff per one CU reference notional, not a return on zero initial equity",
                "sample": "eight synthetic equal monthly excess-return observations; cross-section betas are supplied prior-window estimates; no empirical inference",
                "trading": "four model months; lagged signals; no distributions, taxes or cash interest; short proceeds reusable; fixed long/short notional; fees paid in cash; no interim margin calls; final liquidation"}
    need(all(data["conventions"].get(k) == v for k, v in expected.items()),
         "Preserve the documented factor normalization, probability law, sample and trading contract")
    need(len(data["empirical"]["observations"]) == 8, "The documented synthetic sample has eight observations")
    return encode({"case": data["case"], "pricing": pricing_case(data["pricing"]),
                   "diversification": diversification_case(data["diversification"]),
                   "empirical": empirical_case(data["empirical"]),
                   "construction": construction_case(data["construction"])})


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("v09-c06-inputs.json")
    print(json.dumps(run(json.loads(path.read_text())), indent=2, allow_nan=False))
