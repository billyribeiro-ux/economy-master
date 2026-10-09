"""Rowan alternatives: exact cash ledgers, assumed smoothing, no external data.

Import and run() are quiet. CLI: --input PATH [--output NEW_PATH].
Rational economic amounts serialize as strings; IRRs and square roots as finite
JSON numbers. Negative diagnostic liquidity is explicitly unfunded.
"""
from __future__ import annotations

import argparse
from fractions import Fraction as F
import json
import math
from pathlib import Path

CONVENTIONS = {
    "property": "Annual dates 0,1,2,3; no tax; quoted par debt; interest on opening principal; full repayment without refinancing or default; sale after date-3 operations uses date-4 NOI.",
    "smoothing": "Population moments assume stationary geometric filter and jointly iid latent/market returns; finite path has separately fixed initial appraisal return; simple returns, not log returns.",
    "private": "Commitment covers investment capital only; annual fees at dates 1,2,3 on original commitment; terminal-only carry on positive gross distributions less investment capital, excluding management fees; remaining commitment released at 3.",
    "liquidity": "No interest, borrowing or sale of gated NAV; initial call at 0; each year income then spending then contribution before distribution; negative diagnostic balances are unfunded, not loans.",
    "futures": "Three model periods, not annualized; fixed units and multiplier 1; interest on all opening cash then variation settlement then opening-NAV management fee then performance fee then margin test; roll after date-1 settlement; final positions close after date-3 test.",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, float, str), "number must be a finite number or rational string, not a boolean")
    require(not isinstance(value, str) or len(value) <= 100, "numeric string too long")
    try:
        result = F(str(value))
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        raise ValueError("invalid finite rational") from error
    require(abs(result) <= 10**9, "input magnitude exceeds teaching domain 1e9")
    return result


def object_keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected.split()), label + " has missing or unknown fields")


def vector(value, length, label):
    require(isinstance(value, list) and len(value) == length, label + " has wrong length")
    return [number(x) for x in value]


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    if isinstance(value, float):
        require(math.isfinite(value), "nonfinite output")
    return value


def irr(cash):
    """Unique gross root for a negative-prefix/positive-suffix cash sequence.

    No claim for multiple-sign-change cash. Zeros do not count as sign changes.
    Evaluate the terminal-value polynomial in x=1+r; its single positive root
    is bracketed by zero and a doubled upper bound. Return a numerical root.
    """
    nonzero = [x for x in cash if x]
    require(len(cash) >= 2 and cash[0] < 0 and cash[-1] > 0, "IRR needs negative initial and positive final cash")
    require(sum((a > 0) != (b > 0) for a, b in zip(nonzero, nonzero[1:])) == 1, "IRR requires exactly one negative-to-positive sign change")
    def polynomial(x):
        total = 0.0
        for item in cash:
            total = total*x + float(item)
        return total
    lo, hi = 0.0, 1.0
    for _ in range(100):
        if polynomial(hi) <= 0:
            break
        hi *= 2
    else:
        raise ValueError("IRR exceeds numerical bracketing domain")
    for _ in range(180):
        middle = (lo+hi)/2
        if polynomial(middle) > 0:
            lo = middle
        else:
            hi = middle
    answer = (lo+hi)/2-1
    require(answer > -1 and math.isfinite(answer), "IRR root outside representable domain")
    return answer


def property_case(raw):
    object_keys(raw, "purchase entry_cost loan loan_rate principal_payments noi capex forward_noi exit_cap_rate sale_cost_rate asset_discount_rate stress_forward_noi stress_exit_cap_rate", "property")
    p = {key: number(value) for key, value in raw.items() if key not in ("principal_payments", "noi", "capex")}
    principal = vector(raw["principal_payments"], 3, "principal payments")
    noi = vector(raw["noi"], 3, "NOI")
    capex = vector(raw["capex"], 3, "capex")
    require(all(x >= 0 for x in p.values()) and p["purchase"] > 0, "nonnegative property quantities required")
    require(p["exit_cap_rate"] > 0 and p["stress_exit_cap_rate"] > 0, "exit cap rates must be positive")
    require(p["sale_cost_rate"] < 1, "selling cost must be below full proceeds")
    require(all(x >= 0 for x in principal+noi+capex), "negative property cash component")
    require(sum(principal) == p["loan"], "principal must fully amortize quoted loan by date 3")
    initial = p["purchase"]+p["entry_cost"]
    require(p["loan"] < initial, "positive initial equity required")
    rows, debt, operating = [], [-p["loan"]], []
    balance = p["loan"]
    for t in range(3):
        require(principal[t] <= balance, "principal payment exceeds opening balance")
        interest = balance*p["loan_rate"]
        payment = principal[t]+interest
        available = noi[t]-capex[t]
        require(available >= 0, "nonnegative operating cash required in this fixture")
        if t < 2:
            require(available >= payment, "interim debt service needs an unmodeled equity injection/default")
        rows.append({"date": t+1, "opening_debt": balance, "noi": noi[t], "capex": capex[t], "operating_cash": available, "interest": interest, "principal": principal[t], "debt_service": payment, "closing_debt": balance-principal[t]})
        balance -= principal[t]
        debt.append(payment)
        operating.append(available)
    def sale_case(forward_noi, cap_rate):
        gross = forward_noi/cap_rate
        cost = gross*p["sale_cost_rate"]
        asset = [-initial, *operating]
        asset[-1] += gross-cost
        equity = [a-d for a, d in zip(asset, debt)]
        require(asset[-1] > 0 and equity[-1] > 0, "exit cannot fully repay debt with positive residual; default is outside fixture")
        npv = sum(a/(1+p["asset_discount_rate"])**t for t, a in enumerate(asset))
        return {"forward_noi": forward_noi, "cap_rate": cap_rate, "gross_sale": gross, "sale_cost": cost, "net_sale": gross-cost, "asset_cash": asset, "equity_cash": equity, "asset_npv_at_supplied_rate": npv, "asset_irr": irr(asset), "equity_irr": irr(equity)}
    return {"initial_uses": initial, "initial_debt": p["loan"], "initial_equity": initial-p["loan"], "operations": rows, "lender_cash": debt, "lender_irr": irr(debt) if p["loan"] else None, "base": sale_case(p["forward_noi"], p["exit_cap_rate"]), "stress": sale_case(p["stress_forward_noi"], p["stress_exit_cap_rate"])}


def smoothing_case(raw):
    object_keys(raw, "theta latent_mean latent_sigma market_sigma latent_market_correlation safe_simple_return initial_appraisal_return latent_path sum_horizon", "smoothing")
    p = {k: number(v) for k, v in raw.items() if k not in ("latent_path", "sum_horizon")}
    path = vector(raw["latent_path"], 4, "latent path")
    theta = p["theta"]
    horizon = raw["sum_horizon"]
    require(type(horizon) is int and 1 <= horizon <= 100, "sum horizon must be an integer 1 through 100")
    require(0 <= theta < 1, "smoothing theta must lie in [0,1)")
    require(p["latent_sigma"] > 0 and p["market_sigma"] > 0, "positive sigmas needed for beta/correlation/Sharpe")
    require(-1 <= p["latent_market_correlation"] <= 1, "correlation outside [-1,1]")
    require(all(x > -1 for x in path+[p["initial_appraisal_return"], p["safe_simple_return"], p["latent_mean"]]), "simple return must exceed -1 in positive-wealth illustration")
    latent_var = p["latent_sigma"]**2
    variance = (1-theta)/(1+theta)*latent_var
    latent_cov = p["latent_market_correlation"]*p["latent_sigma"]*p["market_sigma"]
    covariance = (1-theta)*latent_cov
    market_var = p["market_sigma"]**2
    reported, recovered, indices = [], [], []
    previous = p["initial_appraisal_return"]
    true_wealth = report_wealth = F(1)
    for t, true in enumerate(path, 1):
        appraised = theta*previous+(1-theta)*true
        unsmoothed = (appraised-theta*previous)/(1-theta)
        true_wealth *= 1+true
        report_wealth *= 1+appraised
        reported.append(appraised)
        recovered.append(unsmoothed)
        indices.append({"date": t, "latent_index": true_wealth, "appraisal_index": report_wealth})
        previous = appraised
    sigma = math.sqrt(float(variance))
    return {"population": {"mean": p["latent_mean"], "latent_variance": latent_var, "reported_variance": variance, "reported_sigma": sigma, "lag_one_correlation": theta, "latent_market_covariance": latent_cov, "reported_market_covariance": covariance, "latent_beta": latent_cov/market_var, "reported_beta": covariance/market_var, "reported_market_correlation": float(covariance)/(sigma*float(p["market_sigma"])), "latent_sharpe": (p["latent_mean"]-p["safe_simple_return"])/p["latent_sigma"], "reported_sharpe": float(p["latent_mean"]-p["safe_simple_return"])/sigma, "sum_horizon": horizon, "variance_of_sum": variance*(horizon+2*sum((horizon-k)*theta**k for k in range(1, horizon))), "long_run_variance_per_period": latent_var}, "finite_path": {"initial_appraisal_return": p["initial_appraisal_return"], "latent_returns": path, "reported_returns": reported, "unsmoothed_returns": recovered, "wealth_indices": indices, "interpretation": "Fixed-initial-value finite illustration; not a sample estimate of stationary population moments or realizable reported NAV."}}


def liquidity_ledger(initial, contributions, distributions, income, spending):
    balance = initial-contributions[0]+distributions[0]
    minimum = min(initial-contributions[0], balance)
    rows = [{"date": 0, "income": F(0), "spending": F(0), "contribution": contributions[0], "before_distribution": initial-contributions[0], "distribution": distributions[0], "after_distribution": balance}]
    for t in range(1, 4):
        before = balance+income[t-1]-spending[t-1]-contributions[t]
        balance = before+distributions[t]
        minimum = min(minimum, before, balance)
        rows.append({"date": t, "income": income[t-1], "spending": spending[t-1], "contribution": contributions[t], "before_distribution": before, "distribution": distributions[t], "after_distribution": balance})
    return {"initial_cash": initial, "ledger": rows, "minimum_cash": minimum, "feasible": minimum >= 0, "additional_initial_reserve_needed": max(F(0), -minimum), "terminal_cash": balance if minimum >= 0 else None, "unfunded_diagnostic_terminal_balance": balance if minimum < 0 else None, "status": "funded through all stipulated deadlines" if minimum >= 0 else "unfunded diagnostic only; no implicit borrowing or completed investment path"}


def private_case(raw, liquid):
    object_keys(raw, "commitment investment_calls annual_fee_rate carry_rate gross_distributions benchmark_gross_returns delay_first_distribution", "private")
    object_keys(liquid, "initial_cash gated_nav income spending", "liquidity")
    commitment, fee_rate, carry_rate, delay = (number(raw[k]) for k in ("commitment", "annual_fee_rate", "carry_rate", "delay_first_distribution"))
    calls = vector(raw["investment_calls"], 4, "investment calls")
    gross = vector(raw["gross_distributions"], 4, "gross distributions")
    benchmark = vector(raw["benchmark_gross_returns"], 3, "benchmark gross returns")
    initial, gated = number(liquid["initial_cash"]), number(liquid["gated_nav"])
    income, spending = vector(liquid["income"], 3, "income"), vector(liquid["spending"], 3, "spending")
    require(commitment > 0 and 0 <= fee_rate < 1 and 0 <= carry_rate < 1, "invalid private commitment or fee rate")
    require(all(x >= 0 for x in calls+gross+income+spending+[initial, gated, delay]), "negative private/liquidity cash component")
    require(calls[0] > 0 and calls[3] == 0 and gross[0] == 0 and gross[3] > 0, "fixed four-date private liquidation convention violated")
    invested = sum(calls)
    require(invested <= commitment, "investment calls exceed commitment")
    require(all(x > 0 for x in benchmark), "benchmark gross returns must be positive")
    fees = [F(0)]+[commitment*fee_rate]*3
    contributions = [a+b for a, b in zip(calls, fees)]
    carry = carry_rate*max(F(0), sum(gross)-invested)
    require(carry <= gross[-1], "terminal-only carry exceeds available terminal distribution")
    net_dist = list(gross)
    net_dist[-1] -= carry
    net_cash = [d-c for d, c in zip(net_dist, contributions)]
    require(net_cash[1] <= 0 and net_cash[2] <= 0 and net_cash[3] > 0, "private fixture requires negative net calls before positive liquidation for unique IRR")
    require(delay <= net_dist[1], "cannot delay more than first net distribution")
    delayed = list(net_dist)
    delayed[1] -= delay
    delayed[3] += delay
    delayed_cash = [d-c for d, c in zip(delayed, contributions)]
    multipliers = [F(1)]*4
    for t in range(2, -1, -1):
        multipliers[t] = multipliers[t+1]*benchmark[t]
    fv_calls = sum(c*m for c, m in zip(contributions, multipliers))
    fv_dist = sum(d*m for d, m in zip(net_dist, multipliers))
    base = liquidity_ledger(initial, contributions, net_dist, income, spending)
    stress = liquidity_ledger(initial, contributions, delayed, income, spending)
    additional = stress["additional_initial_reserve_needed"]
    repair_possible = additional <= gated
    repair = liquidity_ledger(initial+additional, contributions, delayed, income, spending) if repair_possible else None
    return {"investment_capital": invested, "unused_commitment_released_at_3": commitment-invested, "fees": fees, "carry_paid_at_3": carry, "gross_distributions": gross, "lp_contributions": contributions, "lp_net_distributions": net_dist, "lp_net_cash": net_cash, "lp_net_irr": irr(net_cash), "gross_investment_multiple": sum(gross)/invested, "lp_net_tvpi": sum(net_dist)/sum(contributions), "lp_net_dpi": sum(net_dist)/sum(contributions), "lp_rvpi": F(0), "gp_management_plus_carry": sum(fees)+carry, "lp_net_profit": sum(net_cash), "benchmark": {"terminal_multipliers": multipliers, "fv_contributions": fv_calls, "fv_net_distributions": fv_dist, "cash_flow_matched_ratio": fv_dist/fv_calls, "terminal_relative_excess": fv_dist-fv_calls, "scope": "Dated cash comparison to supplied synthetic benchmark, not risk-adjusted alpha or a guaranteed self-financing benchmark replica."}, "liquidity_base": base, "delayed_net_distributions": delayed, "delayed_net_cash": delayed_cash, "delayed_lp_irr_if_funded": irr(delayed_cash), "liquidity_delayed": stress, "repair_by_reducing_initial_gated_allocation": {"feasible": repair_possible, "liquid_reserve_increase": additional, "gated_allocation_after": gated-additional if repair_possible else None, "ledger": repair}}


def futures_case(raw):
    object_keys(raw, "initial_cash units near_entry near_settlement deferred_entry deferred_marks spot_start spot_end cash_yield management_rate performance_rate margin_reserve stress_first_settlement", "futures")
    p = {k: number(v) for k, v in raw.items() if k != "deferred_marks"}
    marks = vector(raw["deferred_marks"], 2, "deferred marks")
    require(all(x >= 0 for x in p.values()) and all(x >= 0 for x in marks), "nonnegative futures fixture inputs required")
    require(p["initial_cash"] > 0 and p["units"] > 0 and p["near_entry"] > 0 and p["deferred_entry"] > 0 and p["spot_start"] > 0, "positive initial cash, quantity and entry/spot prices required")
    require(0 <= p["management_rate"] < 1 and 0 <= p["performance_rate"] < 1, "fee rates must lie in [0,1)")
    require(0 <= p["cash_yield"] <= 1, "cash yield outside teaching range [0,1]")
    require(p["margin_reserve"] <= p["initial_cash"], "initial margin exceeds cash")
    entries = [p["near_entry"], p["deferred_entry"], marks[0]]
    settlements = [p["near_settlement"], *marks]
    def step(opening, high_water, entry, settlement, date):
        interest = opening*p["cash_yield"]
        pnl = p["units"]*(settlement-entry)
        management = opening*p["management_rate"]
        pre_performance = opening+interest+pnl-management
        performance = p["performance_rate"]*max(F(0), pre_performance-high_water)
        close = pre_performance-performance
        shortfall = max(F(0), p["margin_reserve"]-close)
        return {"date": date, "opening_cash": opening, "opening_high_water": high_water, "interest": interest, "entry_or_previous_mark": entry, "settlement": settlement, "variation_cash": pnl, "management_fee": management, "pre_performance_cash": pre_performance, "performance_fee": performance, "ending_cash": close, "ending_high_water": max(high_water, close), "margin_reserve": p["margin_reserve"], "free_cash_above_margin": close-p["margin_reserve"], "margin_shortfall": shortfall, "feasible": shortfall == 0}
    cash = high_water = p["initial_cash"]
    rows = []
    for date, (entry, settlement) in enumerate(zip(entries, settlements), 1):
        row = step(cash, high_water, entry, settlement, date)
        rows.append(row)
        if not row["feasible"]:
            break
        cash, high_water = row["ending_cash"], row["ending_high_water"]
    feasible = len(rows) == 3 and rows[-1]["feasible"]
    stress = step(p["initial_cash"], p["initial_cash"], p["near_entry"], p["stress_first_settlement"], 1)
    return {"ledger": rows, "feasible": feasible, "completed_periods": sum(row["feasible"] for row in rows), "terminal_cash": cash if feasible else None, "net_total_return": cash/p["initial_cash"]-1 if feasible else None, "total_variation_cash_through_observed_rows": sum(r["variation_cash"] for r in rows), "total_interest_through_observed_rows": sum(r["interest"] for r in rows), "total_management_through_observed_rows": sum(r["management_fee"] for r in rows), "total_performance_through_observed_rows": sum(r["performance_fee"] for r in rows), "spot_total_return": p["spot_end"]/p["spot_start"]-1, "new_contract_notional_at_roll": p["units"]*p["deferred_entry"], "new_contract_initial_cash_price": F(0), "stress_first_period": stress, "status": "All stipulated marks funded; final margin release is not income." if feasible else "Stopped at first unfunded margin test; future marks and returns are not implemented."}


def run(data):
    object_keys(data, "case provenance conventions property smoothing private liquidity futures", "root")
    require(data["case"] == "Rowan alternatives desk", "unknown case identity")
    require(isinstance(data["provenance"], str) and bool(data["provenance"].strip()), "provenance missing")
    require(data["conventions"] == CONVENTIONS, "unsupported timing/claim convention")
    return encode({"chapter": "v09-c10", "case": data["case"], "provenance": data["provenance"], "units": "CU and explicitly labeled simple returns; property/private annual, futures model periods", "property": property_case(data["property"]), "smoothing": smoothing_case(data["smoothing"]), "private": private_case(data["private"], data["liquidity"]), "futures": futures_case(data["futures"]), "limits": ["Synthetic conditional cases, not current data, expected outperformance or investment advice.", "Property model admits only fully performing debt with specified capital; default/workout and taxes are outside its domain.", "Smoothing moments require the stated population assumptions; known-theta inversion is not an empirical estimate.", "Private debt/strategy-comparison exercises are independently solved in the checker and text, not forecast by the four-case lab.", "A negative cash diagnostic is an unfunded policy, not an implicit borrowing facility; benchmark ratio is not risk adjustment.", "Futures cash chronology and margin observations are stipulated; no intraperiod price path or financing facility is invented."]})


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: "+value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: "+key)
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_constant, object_pairs_hook=unique_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("v09-c10-inputs.json"))
    parser.add_argument("--output", type=Path, help="New file only; existing files are never overwritten")
    args = parser.parse_args()
    try:
        result = json.dumps(run(load(args.input)), indent=2, allow_nan=False)+"\n"
        if args.output is None:
            print(result, end="")
        else:
            require(args.output.resolve() != args.input.resolve(), "output cannot overwrite input")
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(result)
    except (ValueError, OSError) as error:
        parser.exit(2, "error: "+str(error)+"\n")


if __name__ == "__main__":
    main()
