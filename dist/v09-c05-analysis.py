"""Exact Aster three-state pricing laboratory. Standard library, quiet run(data)."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path


FIXED = {
    "case": "Aster State Claims",
    "provenance": "Original synthetic one-period teaching market; no observed prices or investment recommendations.",
    "currency": "CU",
    "horizon": "date 0 to date 1",
    "policy": "frictionless unrestricted real holdings; no interim margin, default, tax or trading cost",
}
NUMERIC_KEYS = {
    "physical_probabilities", "alternative_probabilities", "bond_price",
    "stock_payoffs", "stock_price", "call_price", "claim_payoffs", "claim_quote",
    "diagnostic_call_quotes", "incomplete_digital_quotes", "utility_discount",
    "current_consumption",
}


def rational(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Use exact rational strings or integer JSON values, not booleans/floats")
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid rational") from exc


def vector(value, length=3):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"Expected list with {length} entries")
    return [rational(x) for x in value]


def dot(x, y):
    return sum((a*b for a, b in zip(x, y)), F(0))


def expectation(pi, x):
    return dot(pi, x)


def covariance(pi, x, y):
    ex, ey = expectation(pi, x), expectation(pi, y)
    return sum((p*(a-ex)*(b-ey) for p, a, b in zip(pi, x, y)), F(0))


def solve(matrix, rhs):
    """Square exact Gaussian elimination; singularity is a domain error."""
    n = len(rhs)
    a = [list(row) + [b] for row, b in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if a[r][col]), None)
        if pivot is None:
            raise ValueError("Singular payoff system")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [x/scale for x in a[col]]
        for r in range(n):
            if r != col:
                scale = a[r][col]
                a[r] = [x-scale*y for x, y in zip(a[r], a[col])]
    return [row[-1] for row in a]


def pack(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: pack(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [pack(v) for v in value]
    return value


def run(data):
    if not isinstance(data, dict) or set(data) != set(FIXED) | NUMERIC_KEYS | {"states"}:
        raise ValueError("Exact documented input schema required")
    if any(data[k] != v for k, v in FIXED.items()):
        raise ValueError("Contradictory named-case provenance, units, timing or trading policy")
    labels = data["states"]
    if (not isinstance(labels, list) or len(labels) != 3
            or any(not isinstance(s, str) or not s.strip() for s in labels)
            or len(set(labels)) != 3):
        raise ValueError("Three unique nonempty state names required")
    pi = vector(data["physical_probabilities"])
    alt = vector(data["alternative_probabilities"])
    for p in (pi, alt):
        if min(p) <= 0 or sum(p) != 1:
            raise ValueError("All physical states require positive probabilities summing to one")
    b, ps, pc, quote, delta, c0 = [rational(data[k]) for k in (
        "bond_price", "stock_price", "call_price", "claim_quote",
        "utility_discount", "current_consumption")]
    stock, claim = vector(data["stock_payoffs"]), vector(data["claim_payoffs"])
    gap = stock[1]-stock[0]
    if stock[0] <= 0 or gap <= 0 or stock[2]-stock[1] != gap:
        raise ValueError("Positive equally spaced increasing three-state stock payoffs required")
    if b <= 0 or ps <= 0 or delta <= 0 or c0 <= 0:
        raise ValueError("Positive bond/stock prices, utility discount and current consumption required")
    k = (ps-b*stock[0])/gap
    if not 0 < k < 2*b:
        raise ValueError("Bond/stock market must admit strictly positive state prices")
    calls = []
    digitals = []
    for key, dest in (("diagnostic_call_quotes", calls), ("incomplete_digital_quotes", digitals)):
        items = data[key]
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise ValueError("Each quote experiment needs 1 through 20 rational quotes")
        dest.extend(rational(x) for x in items)
    payoff = [[F(1), s, max(s-stock[1], F(0))] for s in stock]
    prices = [b, ps, pc]
    arrows = [solve(payoff, [F(i == j) for i in range(3)]) for j in range(3)]

    def state_prices(call_price):
        high = call_price/gap
        return [b-k+high, k-2*high, high]

    q = state_prices(pc)
    if min(q) <= 0:
        raise ValueError("Base complete market must have q>0; use diagnostic_call_quotes for arbitrage")
    rf = 1/b
    holdings = solve(payoff, claim)
    fair = dot(prices, holdings)
    # Position +1 means buy the quoted claim and short its replica.
    direction = F(1 if quote < fair else -1 if quote > fair else 0)
    initial = direction*(quote-fair)
    extra_bonds = -initial/b
    misquote = {
        "quote": quote, "fair_price": fair, "quoted_claim_units": direction,
        "replica_asset_units": [-direction*x for x in holdings],
        "initial_cost_before_banking": initial, "additional_bond_units": extra_bonds,
        "net_initial_cost": F(0), "terminal_payoffs": [extra_bonds]*3,
        "arbitrage": quote != fair,
    }
    diagnostics = []
    for cp in calls:
        candidate = state_prices(cp)
        record = {"call_quote": cp, "state_prices": candidate,
                  "no_arbitrage": min(candidate) > 0, "certificate": None}
        if min(candidate) <= 0:
            j = next(i for i, x in enumerate(candidate) if x <= 0)
            h = list(arrows[j])
            h[0] -= candidate[j]/b
            record["certificate"] = {
                "replicated_state": labels[j], "unbanked_arrow_price": candidate[j],
                "asset_units_after_banking": h,
                "initial_cost": dot([b, ps, cp], h),
                "terminal_payoffs": [dot(row, h) for row in payoff],
            }
        diagnostics.append(record)
    low, high = max(F(0), k-b), k/2
    lower_h = [F(0), F(0)] if k <= b else [-stock[1]/gap, 1/gap]
    upper_h = [-stock[0]/(2*gap), 1/(2*gap)]
    hpay = [F(0), F(0), F(1)]
    lower_pay = [lower_h[0]+lower_h[1]*s for s in stock]
    upper_pay = [upper_h[0]+upper_h[1]*s for s in stock]
    experiments = []
    for price in digitals:
        candidate = [b-k+price, k-2*price, price]
        record = {"digital_quote": price, "state_prices_after_listing": candidate,
                  "no_arbitrage": low < price < high, "certificate": None}
        if price <= low:
            # Long the digital, short its subhedge; invest receipts in the bond.
            gain, hsign, sign = low-price, F(-1), F(1)
            hedge = lower_h
        elif price >= high:
            gain, hsign, sign = price-high, F(1), F(-1)
            hedge = upper_h
        else:
            experiments.append(record)
            continue
        h = [hsign*hedge[0]+gain/b, hsign*hedge[1]]
        record["certificate"] = {
            "bond_stock_units": h, "digital_units": sign,
            "initial_cost": dot([b, ps], h)+sign*price,
            "terminal_payoffs": [h[0]+h[1]*s+sign*z for s, z in zip(stock, hpay)],
        }
        experiments.append(record)

    gross = [s/ps for s in stock]

    def sdf_report(probability):
        m = [x/p for x, p in zip(q, probability)]
        em = expectation(probability, m)
        var_m = covariance(probability, m, m)
        eg, var_g = expectation(probability, gross), covariance(probability, gross, gross)
        cov = covariance(probability, m, gross)
        premium = eg-rf
        # An exactly priced unit-cost payoff attaining the absolute SDF bound.
        shift = expectation(probability, [x*x for x in m])/em
        frontier = [rf+shift-x for x in m]
        return {
            "physical_probabilities": probability, "discount_factor": m,
            "mean_discount_factor": em, "variance_discount_factor": var_m,
            "risk_neutral_probabilities": [x/b for x in q],
            "stock_expected_payoff": expectation(probability, stock),
            "stock_expected_gross_return": eg, "stock_expected_simple_return": eg-1,
            "stock_excess_payoffs": [g-rf for g in gross],
            "stock_expected_excess_return": premium, "stock_return_variance": var_g,
            "discount_return_covariance": cov,
            "fundamental_prices": [expectation(probability, [m[i]*payoff[i][j] for i in range(3)]) for j in range(3)],
            "expected_discounted_stock_gross_return": expectation(probability, [m[i]*gross[i] for i in range(3)]),
            "stock_sharpe_squared": premium*premium/var_g,
            "sdf_bound_squared": var_m/(em*em),
            "cauchy_gap": var_m*var_g-cov*cov,
            "bound_attaining_payoff": frontier,
            "bound_attaining_price": dot(q, frontier),
            "bound_attaining_asset_units": solve(payoff, frontier),
            "bound_attaining_mean_excess": expectation(probability, frontier)-rf,
            "bound_attaining_variance": covariance(probability, frontier, frontier),
        }
    physical = sdf_report(pi)
    m = physical["discount_factor"]
    future_c = [delta*c0/x for x in m]
    result = {
        **FIXED, "states": labels, "arithmetic": "Exact rational strings; no simulated or historical observations",
        "complete_market": {
            "payoff_rows_bond_stock_call": payoff, "prices_bond_stock_call": prices,
            "call_strike": stock[1], "payoff_determinant": gap*gap,
            "complete": True, "no_arbitrage": True,
            "state_prices": q, "arrow_replication_asset_units": arrows,
            "gross_safe_return": rf, "simple_safe_return": rf-1,
            "claim_payoffs": claim, "claim_replication_asset_units": holdings,
            "claim_price": fair, "claim_price_by_state_prices": dot(q, claim),
            "quote_experiment": misquote, "call_quote_diagnostics": diagnostics,
        },
        "incomplete_bond_stock_market": {
            "rank": 2, "complete": False, "k": k,
            "state_price_family": "(bond_price-k+t, k-2*t, t)",
            "digital_price_lower_strict": low, "digital_price_upper_strict": high,
            "subhedge_bond_stock_units": lower_h, "subhedge_payoffs": lower_pay,
            "superhedge_bond_stock_units": upper_h, "superhedge_payoffs": upper_pay,
            "listed_digital_experiments": experiments,
        },
        "physical_pricing": physical, "alternative_physical_pricing": sdf_report(alt),
        "log_utility_euler": {
            "utility_discount": delta, "current_consumption": c0,
            "future_consumption": future_c,
            "marginal_rate_of_substitution": [delta*c0/c for c in future_c],
            "claim_price": expectation(pi, [delta*c0*claim[i]/future_c[i] for i in range(3)]),
            "claim_quote_utility_derivative_at_zero_trade": (fair-quote)/c0,
            "scope": "Constructed positive consumption/endowment and an interior marginal trade; no market-clearing equilibrium inferred",
        },
    }
    return pack(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("v09-c05-inputs.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(json.loads(args.input.read_text(encoding="utf-8")))
    text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+"\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
