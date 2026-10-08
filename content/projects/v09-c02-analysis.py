"""Oriel portfolio mathematics: exact finite-state and common-date calculations.

Run with Python 3. An optional argument supplies a bounded case-copy path.
No network, dependencies, random simulation or file writes.
"""
from fractions import Fraction as F
from math import sqrt
from pathlib import Path
import json
import sys


def exact(value):
    if isinstance(value, (bool, float)) or value is None:
        raise ValueError("Use an exact integer or rational string")
    return F(value)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    return value


def dot(a, b):
    need(len(a) == len(b), "Exposure dimension mismatch")
    return sum((x * y for x, y in zip(a, b)), F(0))


def quadratic(w, matrix):
    return dot(w, [dot(row, w) for row in matrix])


def matrix_rows(raw, columns):
    need(bool(raw) and all(len(row) == columns for row in raw), "Rectangular nonempty return table required")
    rows = [[exact(x) for x in row] for row in raw]
    need(all(x >= -1 for row in rows for x in row), "Unlevered limited-liability asset return below -100%")
    return rows


def rank(matrix):
    rows = [list(row) for row in matrix]
    pivot_row = 0
    for column in range(len(rows[0])):
        pivot = next((i for i in range(pivot_row, len(rows)) if rows[i][column]), None)
        if pivot is None:
            continue
        rows[pivot_row], rows[pivot] = rows[pivot], rows[pivot_row]
        divisor = rows[pivot_row][column]
        rows[pivot_row] = [x / divisor for x in rows[pivot_row]]
        for i in range(len(rows)):
            if i != pivot_row:
                multiplier = rows[i][column]
                rows[i] = [x - multiplier * y for x, y in zip(rows[i], rows[pivot_row])]
        pivot_row += 1
        if pivot_row == len(rows):
            break
    return pivot_row


def correlations(cov):
    return [[None if cov[i][i] == 0 or cov[j][j] == 0
             else float(cov[i][j]) / sqrt(float(cov[i][i] * cov[j][j]))
             for j in range(len(cov))] for i in range(len(cov))]


def population_moments(rows, probabilities):
    need(len(rows) == len(probabilities), "Each state requires one probability")
    p = [exact(x) for x in probabilities]
    need(all(x > 0 for x in p) and sum(p) == 1, "Positive physical probabilities must sum exactly to one")
    k = len(rows[0])
    mu = [sum((p[s] * rows[s][i] for s in range(len(rows))), F(0)) for i in range(k)]
    centered = [[row[i] - mu[i] for i in range(k)] for row in rows]
    cov = [[sum((p[s] * centered[s][i] * centered[s][j] for s in range(len(rows))), F(0))
            for j in range(k)] for i in range(k)]
    return {"mean": mu, "covariance": cov, "correlation": correlations(cov),
            "centered_rank": rank(centered)}


def portfolio(rows, probabilities, moments, raw_weights):
    w = list(map(exact, raw_weights))
    need(len(w) == len(rows[0]) and sum(w) == 1, "Fully invested weights must match assets and sum to one")
    returns = [dot(w, row) for row in rows]
    mean = dot(w, moments["mean"])
    variance = quadratic(w, moments["covariance"])
    p = list(map(exact, probabilities))
    return {"weights": w, "state_returns": returns, "mean": mean,
            "variance": variance, "standard_deviation": sqrt(float(variance)),
            "negative_return_probability": sum((p[i] for i, r in enumerate(returns) if r < 0), F(0)),
            "minimum_return": min(returns)}


def common_risk(data):
    factor = exact(data["factor_variance"])
    residual = exact(data["residual_variance"])
    loading = exact(data["common_loading"])
    need(factor >= 0 and residual >= 0, "Variance components must be nonnegative")
    counts = data["equal_weight_counts"]
    need(all(isinstance(n, int) and not isinstance(n, bool) and n >= 1 for n in counts), "Positive integer name counts required")
    common = loading * loading * factor
    equal = [{"names": n, "concentration": F(1, n), "variance": common + residual / n,
              "standard_deviation": sqrt(float(common + residual / n))} for n in counts]
    w = list(map(exact, data["concentrated_weights"]))
    need(bool(w) and all(x >= 0 for x in w) and sum(w) == 1, "Concentration comparison uses fully invested long-only weights")
    H = sum(x * x for x in w)
    return {"mean": exact(data["mean"]), "equal_weight": equal, "common_variance_floor": common,
            "concentrated": {"weights": w, "H": H, "effective_names_for_residual_component": 1 / H,
                             "variance": common + residual * H}}


def financed_plan(rows, probabilities, moments, risky_weights, cash_weight, terms):
    x = list(map(exact, risky_weights))
    cash = exact(cash_weight)
    need(len(x) == len(rows[0]) and sum(x) + cash == 1, "Risky and financing weights must exhaust initial wealth")
    wealth = exact(terms["initial_wealth"])
    lending, borrowing = exact(terms["lending_rate"]), exact(terms["borrowing_rate"])
    fee_rate = exact(terms["stock_borrow_fee"])
    need(wealth > 0 and 0 <= lending <= borrowing and fee_rate >= 0, "Invalid initial wealth or deterministic funding inputs")
    need(terms["short_proceeds_reusable"] is True and terms["interim_margin_calls"] is False
         and terms["full_recourse"] is True, "This fixed-exposure model requires the stated short-proceeds, no-interim-call and recourse contract")
    short_notional = sum((-w for w in x if w < 0), F(0))
    funding_return = cash * (lending if cash >= 0 else borrowing)
    fee = fee_rate * short_notional
    constant = funding_return - fee
    values = [dot(x, row) + constant for row in rows]
    mu = dot(x, moments["mean"]) + constant
    variance = quadratic(x, moments["covariance"])
    terminal_wealth = [wealth * (1 + r) for r in values]
    return {"risky_weights": x, "cash_or_loan_weight": cash,
            "gross_risky_exposure": sum(abs(w) for w in x), "net_risky_exposure": sum(x),
            "funding_return_contribution": funding_return, "fee_per_initial_wealth": fee,
            "mean": mu, "variance": variance, "standard_deviation": sqrt(float(variance)),
            "state_returns": values, "terminal_wealth": terminal_wealth,
            "negative_equity_state_indices": [i for i, w in enumerate(terminal_wealth) if w < 0]}


def sample_moments(raw, asset_count):
    rows = matrix_rows(raw, asset_count)
    n = len(rows)
    need(n >= 2, "At least two complete common-date observations required")
    mean = [sum((row[i] for row in rows), F(0)) / n for i in range(asset_count)]
    centered = [[row[i] - mean[i] for i in range(asset_count)] for row in rows]
    S = [[sum((row[i] * row[j] for row in centered), F(0)) / (n - 1)
          for j in range(asset_count)] for i in range(asset_count)]
    return {"observations": n, "sample_mean": mean, "sample_covariance": S,
            "correlation": correlations(S), "centered_rank": rank(centered)}


def sample_report(data):
    dates = data["period_ends"]
    need(len(dates) == len(data["returns"]) and len(set(dates)) == len(dates)
         and dates == sorted(dates), "Unique ordered common dates must match every row")
    k = len(data["assets"])
    need(k >= 1 and len(set(data["assets"])) == k, "Unique nonempty sample asset labels required")
    stats = sample_moments(data["returns"], k)
    w = list(map(exact, data["weights"]))
    need(len(w) == k and sum(w) == 1, "Sample portfolio weights must match and sum to one")
    var = quadratic(w, stats["sample_covariance"])
    n = stats["observations"]
    stats["fixed_weight_portfolio"] = {
        "weights": w, "sample_mean": dot(w, stats["sample_mean"]),
        "sample_variance": var, "sample_standard_deviation": sqrt(float(var)),
        "iid_mean_variance_estimate": var / n,
        "iid_mean_standard_error_estimate": sqrt(float(var / n)),
        "empirical_equal_probability_variance": var * F(n - 1, n)}
    return stats


def missing_pair_demo(data):
    k = len(data["assets"])
    need(k == 3 and len(data["row_ids"]) == len(data["returns"]), "Three-variable bounded missing-pair demonstration required")
    need(len(set(data["assets"])) == k, "Missing-panel asset labels must be unique")
    need(len(set(data["row_ids"])) == len(data["row_ids"]), "Unique missing-panel row IDs required")
    raw = data["returns"]
    need(all(len(row) == k for row in raw), "Missing panel must be rectangular")
    matrix = [[F(int(i == j)) for j in range(k)] for i in range(k)]
    pairs = []
    for i in range(k):
        for j in range(i + 1, k):
            pair = [[row[i], row[j]] for row in raw if row[i] is not None and row[j] is not None]
            need(len(pair) == 2, "This counterexample requires two matched rows per pair")
            moments = sample_moments(pair, 2)
            v1, cross, v2 = moments["sample_covariance"][0][0], moments["sample_covariance"][0][1], moments["sample_covariance"][1][1]
            need(v1 == v2 and v1 > 0 and abs(cross) == v1, "This counterexample requires perfect signed pairs with equal positive variance")
            rho = cross / v1
            matrix[i][j] = matrix[j][i] = rho
            pairs.append({"assets": [data["assets"][i], data["assets"][j]], "matched_rows": 2,
                          "sample_covariance": cross, "pair_variances": [v1, v2], "correlation": rho})
    witness = list(map(exact, data["witness_weights"]))
    need(len(witness) == k and sum(witness) == 1, "Counterexample witness must have full-investment weights")
    impossible = quadratic(witness, matrix)
    need(impossible < 0, "This named demonstration requires a negative quadratic-form witness")
    return {"pairs": pairs, "assembled_correlation": matrix, "witness": witness,
            "impossible_unit_volatility_variance": impossible,
            "complete_rows": sum(all(x is not None for x in row) for row in raw),
            "interpretation": "Incompatible pair estimates: this is not a covariance law or a usable risk estimate."}


def run(data):
    pop = data["population"]
    k = len(pop["assets"])
    need(k >= 1 and len(set(pop["assets"])) == k, "Unique nonempty asset labels required")
    rows = matrix_rows(pop["returns"], k)
    need(len(pop["states"]) == len(rows) and len(set(pop["states"])) == len(rows), "Unique state labels must match rows")
    moments = population_moments(rows, pop["probabilities"])
    ids = [p["id"] for p in pop["portfolios"]]
    need(len(ids) == len(set(ids)), "Portfolio IDs must be unique")
    plans = {p["id"]: portfolio(rows, pop["probabilities"], moments, p["weights"]) for p in pop["portfolios"]}
    finance = data["finance"]
    base = list(map(exact, finance["levered_base_weights"]))
    scale = exact(finance["risky_scale"])
    need(len(base) == k and sum(base) == 1 and all(w >= 0 for w in base) and scale >= 0,
         "Levered experiment scales a fully invested long-only underlying")
    levered = financed_plan(rows, pop["probabilities"], moments, [scale * w for w in base], 1 - scale, finance)
    short = financed_plan(rows, pop["probabilities"], moments, finance["short_risky_weights"], finance["short_cash_weight"], finance)
    return encode({"case": data["case"], "population": moments, "portfolios": plans,
                   "common_risk": common_risk(data["common_risk"]),
                   "financing": {"scaled_underlying": levered, "long_short": short},
                   "sample": sample_report(data["sample"]), "missing_pair_counterexample": missing_pair_demo(data["missing_data"]),
                   "format": "Exact rational strings for arithmetic; decimal approximations only for standard deviations and general correlations. Null correlation means zero marginal variance."})


if __name__ == "__main__":
    need(len(sys.argv) <= 2, "Usage: python3 v09-c02-analysis.py [inputs.json]")
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v09-c02-inputs.json")
    print(json.dumps(run(json.loads(path.read_text(encoding="utf-8"))), indent=2, allow_nan=False))

