"""Moraine: exact bounded performance accounting, with named approximate statistics.

Standard library only. Import and run(data) are quiet; CLI prints JSON and writes no files.
"""
from calendar import monthrange
from datetime import date
from fractions import Fraction
import json
import math
from pathlib import Path
import sys


def F(value):
    if isinstance(value, (bool, float)):
        raise ValueError("Use exact decimal/fraction strings or integers, not booleans/floats")
    try:
        return Fraction(value)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError("Invalid exact number") from exc


def product(values):
    result = F(1)
    for value in values:
        result *= value
    return result


def mean(values):
    return sum(values, F(0)) / len(values)


def sample_cov(left, right):
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("Aligned sample of at least two observations required")
    lm, rm = mean(left), mean(right)
    return sum((x - lm) * (y - rm) for x, y in zip(left, right)) / (len(left) - 1)


def solve(matrix, rhs):
    n = len(rhs)
    a = [list(row) + [b] for row, b in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((row for row in range(col, n) if a[row][col]), None)
        if pivot is None:
            raise ValueError("Factor design lacks full column rank")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [x / scale for x in a[col]]
        for row in range(n):
            if row != col:
                multiple = a[row][col]
                a[row] = [x - multiple * y for x, y in zip(a[row], a[col])]
    return [row[-1] for row in a]


def regression(y, factors):
    x = [[F(1)] + list(row) for row in zip(*factors)]
    k, n = len(x[0]), len(y)
    if n <= k:
        raise ValueError("Positive residual degrees of freedom required")
    gram = [[sum(row[i] * row[j] for row in x) for j in range(k)] for i in range(k)]
    rhs = [sum(row[j] * v for row, v in zip(x, y)) for j in range(k)]
    coefficients = solve(gram, rhs)
    residuals = [v - sum(c * z for c, z in zip(coefficients, row)) for row, v in zip(x, y)]
    sse = sum(v * v for v in residuals)
    variance = sse / (n - k)
    alpha_variance = variance * solve(gram, [F(1)] + [F(0)] * (k - 1))[0]
    se = math.sqrt(float(alpha_variance))
    return {"intercept": coefficients[0], "loadings": coefficients[1:], "residuals": residuals,
            "residual_sum_squares": sse, "residual_degrees_freedom": n - k,
            "residual_variance_divisor_n_minus_k": variance,
            "classic_alpha_variance": alpha_variance, "classic_alpha_se_approx": se,
            "classic_alpha_t_approx": float(coefficients[0]) / se if se else None,
            "inference_scope": "Classic fixed-design homoskedastic uncorrelated-error formula only; its assumptions and selection validity are not established by this synthetic sequence."}


def differential_stats(values, periods_per_year):
    average = mean(values)
    variance = sample_cov(values, values)
    sd = math.sqrt(float(variance))
    ratio = float(average) / sd if sd else None
    return {"observations": len(values), "mean": average, "sample_variance_n_minus_1": variance,
            "sample_sd_approx": sd, "ratio_approx": ratio,
            "ratio_status": "defined" if sd else "undefined_zero_variance",
            "conditional_annual_arithmetic_mean": periods_per_year * average,
            "conditional_annual_variance": periods_per_year * variance,
            "conditional_annual_sd_approx": math.sqrt(periods_per_year) * sd,
            "conditional_annual_ratio_approx": math.sqrt(periods_per_year) * ratio if ratio is not None else None,
            "classic_mean_t_approx": math.sqrt(len(values)) * ratio if ratio is not None else None,
            "scaling_scope": "Additive horizon sums with stable moments and zero serial covariances; not an exact compounded-return risk or evidence that assumptions hold."}


def ledger(returns, initial, flows, gross=None, fee=F(0)):
    nav = initial
    rows = []
    for t, (r, flow) in enumerate(zip(returns, flows), 1):
        begin = nav
        gross_profit = begin * (gross[t - 1] if gross is not None else r)
        fee_cash = begin * fee if gross is not None else F(0)
        pre_flow = begin + gross_profit - fee_cash
        if pre_flow != begin * (1 + r):
            raise ValueError("Return and fee perimeter do not reconcile")
        nav = pre_flow + flow
        rows.append({"period": t, "beginning_nav": begin, "gross_profit": gross_profit,
                     "fee_cash": fee_cash, "after_return_and_fee": pre_flow,
                     "end_contribution": flow, "next_nav": nav})
    # Nonnegative contributions ensure a strictly increasing terminal-value polynomial.
    n = len(returns)
    def terminal_value(g):
        return float(initial) * g ** n + sum(float(c) * g ** (n - t) for t, c in enumerate(flows, 1))
    low, high = 0.0, 2.0
    while terminal_value(high) < float(nav):
        high *= 2
    for _ in range(120):
        middle = (low + high) / 2
        if terminal_value(middle) < float(nav):
            low = middle
        else:
            high = middle
    g = (low + high) / 2
    return {"rows": rows, "terminal_nav": nav, "total_contributions": initial + sum(flows),
            "profit_after_external_contributions": nav - initial - sum(flows),
            "time_weighted_return": product(1 + r for r in returns) - 1,
            "monthly_money_weighted_return_approx": g - 1,
            "money_weighted_terminal_residual_cu_approx": terminal_value(g) - float(nav),
            "root_domain": "Unique positive gross monthly root for positive initial capital and nonnegative intervening contributions; no annualized MWR claim."}


def attribution(data):
    rows = []
    wp = wb = F(data["initial_wealth"])
    for item in data["periods"]:
        w, W = map(lambda key: list(map(F, item[key])), ("portfolio_weights", "benchmark_weights"))
        r, b = map(lambda key: list(map(F, item[key])), ("portfolio_sector_returns", "benchmark_sector_returns"))
        rp, rb = sum(x * y for x, y in zip(w, r)), sum(x * y for x, y in zip(W, b))
        sectors = []
        for name, x, X, ret, bench in zip(data["sectors"], w, W, r, b):
            sectors.append({"sector": name, "allocation": (x - X) * (bench - rb),
                            "selection": X * (ret - bench), "interaction": (x - X) * (ret - bench),
                            "portfolio_beginning_holding": wp * x, "portfolio_end_holding": wp * x * (1 + ret),
                            "benchmark_beginning_holding": wb * X, "benchmark_end_holding": wb * X * (1 + bench)})
        row = {"label": item["label"], "portfolio_return": rp, "benchmark_return": rb,
               "active_return": rp - rb, "sectors": sectors}
        for effect in ("allocation", "selection", "interaction"):
            row[effect] = sum(sector[effect] for sector in sectors)
        wp, wb = wp * (1 + rp), wb * (1 + rb)
        row.update(portfolio_end_wealth=wp, benchmark_end_wealth=wb)
        rows.append(row)
    linked = {key: F(0) for key in ("allocation", "selection", "interaction")}
    for t, row in enumerate(rows):
        link = product(1 + v["portfolio_return"] for v in rows[:t]) * product(1 + v["benchmark_return"] for v in rows[t + 1:])
        row["chronological_link"] = link
        for effect in linked:
            linked[effect] += link * row[effect]
    start = F(data["initial_wealth"])
    return {"periods": rows, "linked_effects": linked, "sum_one_period_active_returns": sum(row["active_return"] for row in rows),
            "compound_wealth_gap_per_initial_cu": (wp - wb) / start,
            "relative_terminal_wealth_return": wp / wb - 1,
            "portfolio_terminal_wealth": wp, "benchmark_terminal_wealth": wb,
            "link_convention": "Each effect is carried by preceding portfolio gross returns and subsequent benchmark gross returns; a disclosed exact chronological identity, not a unique causal allocation."}


def panel_report(panel):
    funds = panel["funds"]
    survivors = [f for f in funds if f["exit_period"] is None]
    opening_series, filtered_series, years = [], [], []
    for t in range(4):
        eligible = [f for f in funds if f["net_returns"][t] is not None]
        kept = [f for f in survivors if f["net_returns"][t] is not None]
        ra = mean([F(f["net_returns"][t]) for f in eligible])
        rs = mean([F(f["net_returns"][t]) for f in kept]) if kept else None
        if rs is None:
            raise ValueError("Survivor-only comparison requires at least one observed final survivor each year")
        opening_series.append(ra)
        filtered_series.append(rs)
        years.append({"period": t + 1, "opening_eligible_ids": [f["id"] for f in eligible],
                      "opening_entries": [f["id"] for f in eligible if f["entry_period"] == t + 1],
                      "eligible_fund_net_returns": {f["id"]: F(f["net_returns"][t]) for f in eligible},
                      "closing_exits": [f["id"] for f in eligible if f["exit_period"] == t + 1],
                      "equal_weight_return": ra, "hindsight_survivor_ids": [f["id"] for f in kept],
                      "hindsight_survivor_mean": rs})
    cohort = [f for f in funds if f["id"] in panel["initial_cohort"]]
    records = []
    for fund in cohort:
        training = product(1 + F(x) for x in fund["net_returns"][:2]) - 1
        outcomes = [F(x) if x is not None else F(0) for x in fund["net_returns"][2:]]
        records.append({"id": fund["id"], "training_return": training, "outcome_returns_with_cash_after_exit": outcomes,
                        "outcome_return": product(1 + x for x in outcomes) - 1, "exit_period": fund["exit_period"]})
    ranked = sorted(records, key=lambda row: (-row["training_return"], row["id"]))
    selected = ranked[:panel["select_top"]]
    other = ranked[panel["select_top"]:]
    selected_survivors = [row for row in selected if row["exit_period"] is None]
    outcome_top = sorted(records, key=lambda row: (-row["outcome_return"], row["id"]))[:panel["select_top"]]
    intersection = sorted({row["id"] for row in selected} & {row["id"] for row in outcome_top})
    return {"years": years, "all_available_equal_weight_compound_return": product(1 + x for x in opening_series) - 1,
            "hindsight_survivor_only_compound_return": product(1 + x for x in filtered_series) - 1,
            "selection_time": "After Y2 return, before Y3; initial cohort fixed at date 0; ties resolved by ascending fund ID",
            "initial_cohort_records": records, "ranking_ids": [row["id"] for row in ranked],
            "selected_ids": [row["id"] for row in selected], "selected_outcome_return": mean([row["outcome_return"] for row in selected]),
            "other_initial_cohort_outcome_return": mean([row["outcome_return"] for row in other]),
            "all_initial_cohort_outcome_return": mean([row["outcome_return"] for row in records]),
            "selected_final_survivor_ids": [row["id"] for row in selected_survivors],
            "selected_survivor_only_outcome_return": mean([row["outcome_return"] for row in selected_survivors]) if selected_survivors else None,
            "outcome_top_ids": [row["id"] for row in outcome_top], "top_overlap_ids": intersection,
            "top_overlap_count": len(intersection),
            "scope": "Equal initial allocations with no rebalancing during Y3-Y4 for fixed cohorts; exits liquidate once and then earn specified zero cash return. Dynamic all-available strategy rebalances every opening. Neither descriptive comparison establishes skill."}


def validate(data):
    required = {"frequency": "monthly", "periods_per_year": 12, "currency": "CU",
                "fee_basis": "beginning_nav_charged_after_return_before_flow", "benchmark": "cash_plus_market_excess",
                "attribution": "two_sector_static_with_boundary_rebalance", "panel_policy": "all_entries_exits_inclusive_terminal_return"}
    if any(data["conventions"].get(k) != v for k, v in required.items()):
        raise ValueError("Unsupported measurement policy; this is a bounded monthly teaching case")
    if F(data["conventions"]["benchmark_fee"]) != 0 or F(data["conventions"]["post_exit_cash_return"]) != 0:
        raise ValueError("Benchmark fee and post-exit cash return are fixed at zero in this case")
    m = data["monthly"]
    for key in ("dates", "risk_free", "market_excess", "style_factor", "fund_gross", "end_contributions"):
        if len(m[key]) != 8:
            raise ValueError("Exactly eight aligned monthly observations required")
    try:
        dates = [date.fromisoformat(value) for value in m["dates"]]
    except (TypeError, ValueError) as exc:
        raise ValueError("ISO calendar month-end dates required") from exc
    if any(d.day != monthrange(d.year, d.month)[1] for d in dates) or any(
            b.year * 12 + b.month != a.year * 12 + a.month + 1 for a, b in zip(dates, dates[1:])):
        raise ValueError("Eight consecutive calendar month ends required")
    rf, market, gross = [list(map(F, m[k])) for k in ("risk_free", "market_excess", "fund_gross")]
    fee, initial = F(m["fee_rate"]), F(m["initial_nav"])
    flows = list(map(F, m["end_contributions"]))
    if fee < 0 or initial <= 0 or any(c < 0 for c in flows) or flows[-1] != 0:
        raise ValueError("Nonnegative fee/contributions, positive capital and no terminal contribution required")
    if any(1 + r <= 0 for r in rf) or any(1 + r + f <= 0 for r, f in zip(rf, market)) or any(1 + r - fee <= 0 for r in gross):
        raise ValueError("Strictly positive gross cash, benchmark and net fund factors required")
    a = data["attribution"]
    if F(a["initial_wealth"]) <= 0 or len(a["sectors"]) != 2 or len(set(a["sectors"])) != 2 or len(a["periods"]) != 2:
        raise ValueError("Positive-capital two-sector/two-period attribution required")
    for period in a["periods"]:
        for key in ("portfolio_weights", "benchmark_weights"):
            weights = list(map(F, period[key]))
            if len(weights) != 2 or sum(weights) != 1 or any(w <= 0 for w in weights):
                raise ValueError("Both sector weights must be positive and sum to one")
        for key in ("portfolio_sector_returns", "benchmark_sector_returns"):
            values = list(map(F, period[key]))
            if len(values) != 2 or any(v <= -1 for v in values):
                raise ValueError("Two sector returns above minus one required")
    panel = data["panel"]
    if panel["ranking_end_period"] != 2 or panel["select_top"] != 2 or len(panel["period_labels"]) != 4 or len(panel["funds"]) != 6:
        raise ValueError("Four-year/six-fund panel with Y2 ranking and top-two rule required")
    ids = [f["id"] for f in panel["funds"]]
    if len(set(ids)) != 6:
        raise ValueError("Unique fund identifiers required")
    initial_ids = []
    for fund in panel["funds"]:
        entry, end = fund["entry_period"], fund["exit_period"]
        if type(entry) is not int or not 1 <= entry <= 4 or (end is not None and (type(end) is not int or not entry <= end <= 4)):
            raise ValueError("Entry/exit dates outside panel")
        if entry == 1:
            initial_ids.append(fund["id"])
            if end is not None and end < 2:
                raise ValueError("This initial-cohort ranking requires two complete training years")
        if len(fund["net_returns"]) != 4:
            raise ValueError("Every fund needs four explicit values/nulls")
        for t, value in enumerate(fund["net_returns"], 1):
            eligible = t >= entry and (end is None or t <= end)
            if eligible != (value is not None):
                raise ValueError("Missing terminal/live return or forbidden pre-entry/post-exit backfill")
            if value is not None and (F(value) < -1 or (F(value) == -1 and end != t)):
                raise ValueError("Return cannot be below minus one; a complete loss must be an explicit terminal observation")
    if len(initial_ids) != 4 or sorted(panel["initial_cohort"]) != sorted(initial_ids):
        raise ValueError("Initial cohort must be exactly all four date-0 entrants")


def encode(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def run(data):
    validate(data)
    m = data["monthly"]
    rf, market, style, gross, flows = [list(map(F, m[k])) for k in ("risk_free", "market_excess", "style_factor", "fund_gross", "end_contributions")]
    fee, initial = F(m["fee_rate"]), F(m["initial_nav"])
    net = [x - fee for x in gross]
    benchmark = [x + y for x, y in zip(rf, market)]
    gross_active, net_active = [[x - y for x, y in zip(values, benchmark)] for values in (gross, net)]
    gross_excess, net_excess = [[x - y for x, y in zip(values, rf)] for values in (gross, net)]
    fund_ledger = ledger(net, initial, flows, gross, fee)
    benchmark_ledger = ledger(benchmark, initial, flows)
    result = {"case": data["case"], "frequency": "monthly", "dates": m["dates"],
              "monthly_returns": {"gross": gross, "net": net, "benchmark": benchmark, "gross_active": gross_active, "net_active": net_active},
              "gross_information_ratio": differential_stats(gross_active, 12), "net_information_ratio": differential_stats(net_active, 12),
              "net_sharpe_ratio": differential_stats(net_excess, 12),
              "gross_two_factor": regression(gross_excess, [market, style]), "net_two_factor": regression(net_excess, [market, style]),
              "net_market_only": regression(net_excess, [market]),
              "factor_sample_means": {"market_excess": mean(market), "style": mean(style)},
              "active_benchmark_sample_covariance": sample_cov(net_active, benchmark),
              "benchmark_sample_variance": sample_cov(benchmark, benchmark), "net_fund_sample_variance": sample_cov(net, net),
              "fund_ledger": fund_ledger, "matched_benchmark_ledger": benchmark_ledger,
              "matched_flow_terminal_wealth_difference": fund_ledger["terminal_nav"] - benchmark_ledger["terminal_nav"],
              "fee_total_cu": sum(row["fee_cash"] for row in fund_ledger["rows"]),
              "attribution": attribution(data["attribution"]), "fund_panel": panel_report(data["panel"]),
              "limits": "Exact accounting and disclosed sample statistics; no priced-factor-premium, significance, manager-skill, investability or future-return inference is established."}
    encoded = encode(result)
    json.dumps(encoded, allow_nan=False)
    return encoded


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("v09-c08-inputs.json")
    print(json.dumps(run(json.loads(path.read_text())), indent=2, allow_nan=False))
