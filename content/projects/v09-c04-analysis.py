"""Caldera CAPM lab. Exact standard-library arithmetic; no network or writes.

The run function evaluates candidate prices, not an endogenous price solver.
All output fractions are strings; no square-root approximation is required.
"""
from fractions import Fraction
import json
from pathlib import Path
import sys


def F(value):
    if isinstance(value, (bool, float)):
        raise ValueError("Use exact rational strings or integers")
    return Fraction(value)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def dot(left, right):
    need(len(left) == len(right), "Mismatched vector dimensions")
    return sum((x * y for x, y in zip(left, right)), F(0))


def solve(matrix, rhs):
    """Exact Gaussian elimination with row pivoting; small teaching systems."""
    n = len(rhs)
    need(len(matrix) == n and all(len(row) == n for row in matrix), "Square linear system required")
    aug = [[F(x) for x in row] + [F(y)] for row, y in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if aug[i][col] != 0), None)
        need(pivot is not None, "Singular linear system")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [x / scale for x in aug[col]]
        for i in range(n):
            if i != col:
                scale = aug[i][col]
                aug[i] = [x - scale * y for x, y in zip(aug[i], aug[col])]
    return [row[-1] for row in aug]


def determinant3(a):
    return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))


def moments(columns, probabilities):
    need(all(len(column) == len(probabilities) for column in columns), "State lengths must match")
    need(all(p > 0 for p in probabilities) and sum(probabilities) == 1, "Positive physical probabilities must sum to one")
    means = [dot(column, probabilities) for column in columns]
    centered = [[x - mean for x in column] for column, mean in zip(columns, means)]
    covariance = [[sum(p * x * y for p, x, y in zip(probabilities, left, right))
                   for right in centered] for left in centered]
    return means, covariance


def projection(asset, benchmark, probabilities, rf):
    means, cov = moments([asset, benchmark], probabilities)
    need(cov[1][1] > 0, "Beta is undefined for a constant benchmark")
    beta = cov[0][1] / cov[1][1]
    alpha = means[0] - rf - beta * (means[1] - rf)
    residuals = [y - rf - alpha - beta * (x - rf) for y, x in zip(asset, benchmark)]
    return {"beta": beta, "alpha": alpha, "asset_mean": means[0], "benchmark_mean": means[1],
            "residuals": residuals, "residual_variance": dot(probabilities, [e * e for e in residuals]),
            "residual_mean": dot(probabilities, residuals),
            "residual_benchmark_covariance": dot(probabilities, [e * (x - means[1]) for e, x in zip(residuals, benchmark)])}


def validate(data):
    need(data["regime"] == "unconstrained_common_rate_zero_net_cash", "Unsupported funding/choice regime; do not silently change the theorem")
    need(len(data["assets"]) == 3 and len(data["states"]) == 4, "This bounded lab has three risky claims and four states")
    need(len(set(data["states"])) == 4, "Distinct state labels required")
    need(F(data["risk_free_return"]) > -1, "Positive risk-free gross return required")
    p = list(map(F, data["physical_probabilities"]))
    need(len(p) == 4 and all(x > 0 for x in p) and sum(p) == 1, "Four positive physical probabilities summing to one required")
    ids = [asset["id"] for asset in data["assets"]]
    need(len(set(ids)) == 3, "Distinct asset IDs required")
    for asset in data["assets"]:
        need(F(asset["price"]) > 0 and F(asset["shares_outstanding"]) > 0, "Positive claim prices and net supplies required")
        need(len(asset["final_payoffs"]) == 4 and all(F(x) >= 0 for x in asset["final_payoffs"]), "Four nonnegative final cash payoffs required")
    investors = data["investors"]
    need(len(investors) >= 1 and len({h["id"] for h in investors}) == len(investors), "Distinct investors required")
    need(all(F(h["wealth"]) > 0 and F(h["gamma"]) > 0 for h in investors), "Positive initial wealth and risk aversion required")
    aggregate = sum(F(h["wealth"]) for h in investors)
    market = sum(F(a["price"]) * F(a["shares_outstanding"]) for a in data["assets"])
    need(aggregate == market, "Zero-net-cash economy requires investor wealth equal total risky market value")
    need(data["proxy_asset_id"] in ids and data["mean_shift_experiment"]["asset_id"] in ids, "Unknown asset selector")
    need(data["borrowing_limit_investor_id"] in [h["id"] for h in investors], "Unknown constrained investor")
    indices = data["sample_state_indices"]
    need(len(indices) >= 2 and all(type(i) is int and 0 <= i < 4 for i in indices), "Sample indices must select supplied states")
    portfolio = data["zero_beta_portfolio"]
    need(len(portfolio["risky_weights"]) == 3, "Three portfolio exposures required")
    need(sum(map(F, portfolio["risky_weights"])) + F(portfolio["cash_weight"]) == 1, "Portfolio risky and cash weights must sum to one")


def demand(data, columns, constrained_id=None):
    """Demand at given prices, optionally with one investor's cash >= 0."""
    p = list(map(F, data["physical_probabilities"]))
    rf = F(data["risk_free_return"])
    mu, sigma = moments(columns, p)
    minors = [sigma[0][0], sigma[0][0] * sigma[1][1] - sigma[0][1] ** 2, determinant3(sigma)]
    need(all(x > 0 for x in minors), "Risky covariance must be symmetric positive definite")
    excess = [x - rf for x in mu]
    direction = solve(sigma, excess)
    inverse_one = solve(sigma, [F(1)] * 3)
    total_wealth = sum(F(h["wealth"]) for h in data["investors"])
    market_weights = [F(a["price"]) * F(a["shares_outstanding"]) / total_wealth for a in data["assets"]]
    aggregate = [F(0)] * 3
    cash_net, A, investors = F(0), F(0), []
    for h in data["investors"]:
        wealth, gamma = F(h["wealth"]), F(h["gamma"])
        share = wealth / total_wealth
        A += share / gamma
        eta = F(0)
        if h["id"] == constrained_id and sum(direction) > gamma:
            eta = (sum(direction) - gamma) / sum(inverse_one)
        risky = [(x - eta * y) / gamma for x, y in zip(direction, inverse_one)]
        cash = 1 - sum(risky)
        mean = rf + dot(risky, excess)
        variance = dot(risky, [dot(row, risky) for row in sigma])
        state_returns = [cash * rf + sum(risky[i] * columns[i][s] for i in range(3)) for s in range(4)]
        gradient = [q - gamma * dot(row, risky) for q, row in zip(excess, sigma)]
        investors.append({"id": h["id"], "wealth_share": share, "gamma": gamma, "risky_weights": risky,
                          "cash_weight": cash, "risky_shares": [wealth * x / F(a["price"]) for x, a in zip(risky, data["assets"])],
                          "cash_amount": wealth * cash, "mean_return": mean, "return_variance": variance,
                          "state_returns": state_returns, "final_wealth": [wealth * (1 + r) for r in state_returns],
                          "objective": mean - gamma * variance / 2, "gradient": gradient,
                          "borrowing_multiplier": eta})
        aggregate = [old + share * x for old, x in zip(aggregate, risky)]
        cash_net += share * cash
    gap = [x - supplied for x, supplied in zip(aggregate, market_weights)]
    return {"means": mu, "covariance": sigma, "leading_principal_minors": minors,
            "market_weights": market_weights, "inverse_covariance_excess": direction,
            "aggregate_risk_tolerance": A, "lambda_from_preferences": 1 / A,
            "investors": investors, "aggregate_risky_weights": aggregate, "aggregate_cash_weight": cash_net,
            "risky_excess_demand_weights": gap,
            "market_clearing": all(x == 0 for x in gap) and cash_net == 0}


def encode(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    return value


def run(data):
    validate(data)
    p, rf = list(map(F, data["physical_probabilities"])), F(data["risk_free_return"])
    ids = [a["id"] for a in data["assets"]]
    columns = [[F(x) / F(a["price"]) - 1 for x in a["final_payoffs"]] for a in data["assets"]]
    equilibrium = demand(data, columns)
    weights = equilibrium["market_weights"]
    market = [sum(w * column[s] for w, column in zip(weights, columns)) for s in range(4)]
    mu_m, var_m = moments([market], p)
    mu_m, var_m = mu_m[0], var_m[0][0]
    need(var_m > 0, "Market beta requires positive market variance")
    projections = {asset: projection(column, market, p, rf) for asset, column in zip(ids, columns)}
    market_is_positive_tangency = mu_m > rf and all(row["alpha"] == 0 for row in projections.values())
    proxy = columns[ids.index(data["proxy_asset_id"])]
    proxy_results = {asset: projection(column, proxy, p, rf) for asset, column in zip(ids, columns)}
    allocations = []
    for value in data["market_allocations"]:
        y = F(value)
        allocations.append({"market_weight": y, "cash_weight": 1 - y, "mean": rf + y * (mu_m - rf),
                            "variance": y * y * var_m, "beta": y,
                            "on_positive_premium_cml_ray": y >= 0 and market_is_positive_tangency})
    z = data["zero_beta_portfolio"]
    z_returns = [F(z["cash_weight"]) * rf + sum(F(w) * c[s] for w, c in zip(z["risky_weights"], columns)) for s in range(4)]
    z_mu, z_cov = moments([z_returns], p)
    z_projection = projection(z_returns, market, p, rf)
    # A candidate linear pricing checksum. It is NOT asserted valid until checked.
    price_of_covariance = (mu_m - rf) / var_m
    kernel = [(1 - price_of_covariance * (r - mu_m)) / (1 + rf) for r in market]
    candidate_q = [prob * m * (1 + rf) for prob, m in zip(p, kernel)]
    price_residuals = {a["id"]: dot(p, [m * F(x) for m, x in zip(kernel, a["final_payoffs"])]) - F(a["price"]) for a in data["assets"]}
    bond_residual = dot(p, kernel) * (1 + rf) - 1
    valid_pricing = all(m > 0 for m in kernel) and bond_residual == 0 and all(x == 0 for x in price_residuals.values())
    sample = data["sample_state_indices"]
    empirical_p = [F(1) / len(sample)] * len(sample)
    sample_market = [market[i] for i in sample]
    sample_results = {asset: projection([column[i] for i in sample], sample_market, empirical_p, rf)
                      for asset, column in zip(ids, columns)}
    shifted = [column[:] for column in columns]
    shift = data["mean_shift_experiment"]
    selected = ids.index(shift["asset_id"])
    shifted[selected] = [r + F(shift["return_increment_each_state"]) for r in shifted[selected]]
    constrained = demand(data, columns, data["borrowing_limit_investor_id"])
    return encode({"case": data["case"], "format": "Exact rational strings; variances are squared decimal returns, not percent units",
                   "state_returns_by_asset": dict(zip(ids, columns)), "candidate_economy": equilibrium,
                   "market": {"state_returns": market, "mean": mu_m, "variance": var_m,
                              "expected_excess_return": mu_m - rf, "covariance_price_from_market": price_of_covariance},
                   "true_market_projections": projections, "proxy_id": data["proxy_asset_id"], "proxy_projections": proxy_results,
                   "market_cash_allocations": allocations,
                   "supplied_zero_beta_portfolio": {"state_returns": z_returns, "mean": z_mu[0], "variance": z_cov[0][0],
                                                    "projection": z_projection, "actually_zero_beta": z_projection["beta"] == 0},
                   "pricing_checksum": {"candidate_kernel": kernel, "candidate_normalized_weights": candidate_q,
                                        "physical_probabilities": p, "bond_price_residual": bond_residual,
                                        "asset_price_residuals": price_residuals, "strictly_positive_and_prices_all_claims": valid_pricing,
                                        "physical_expected_payoffs_discounted_at_rf": {a["id"]: dot(p, list(map(F, a["final_payoffs"]))) / (1 + rf) for a in data["assets"]}},
                   "finite_sample": {"observations": len(sample), "state_indices": sample, "projections": sample_results,
                                     "scope": "Selected toy observations; coefficients are sample estimates, not population prices or inference about actual markets"},
                   "fixed_price_mean_shift": {"asset_id": shift["asset_id"], "return_increment": F(shift["return_increment_each_state"]),
                                             "demand": demand(data, shifted), "status": "Candidate prices and supplies held fixed; inspect clearing flag"},
                   "borrowing_limit_experiment": {"constrained_investor": data["borrowing_limit_investor_id"], "demand": constrained,
                                                  "status": "Optimal constrained individual demands at old prices need not clear the economy"}})


if __name__ == "__main__":
    need(len(sys.argv) <= 2, "Usage: python3 v09-c04-analysis.py [inputs.json]")
    source = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v09-c04-inputs.json")
    print(json.dumps(run(json.loads(source.read_text(encoding="utf-8"))), indent=2, ensure_ascii=False, allow_nan=False))
