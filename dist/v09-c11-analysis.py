#!/usr/bin/env python3
"""Original finite execution cases. Standard library, exact fractions, no network."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re


CONVENTIONS = {
    "currency": "CU", "quantity": "whole shares", "interest": "zero over all case dates",
    "book": "independent atomic snapshots; price priority; IOC remainder cancelled; FOK all or none",
    "queue": "price-time priority; stated sell volume reaches this queue; no cancellations or new orders ahead",
    "shortfall": "paper minus actual terminal wealth; original target retained",
    "impact": "monotone buy; within-block average persistent impact; shock between blocks",
    "objective": "expected cost plus lambda times cost variance",
    "capacity": "quantity choice separately authorized; gross benefit excludes own-price marking",
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def keys(obj, names):
    need(isinstance(obj, dict) and set(obj) == set(names.split()), "incorrect object fields")


def num(value, low=None, strict=False):
    need(type(value) is int or (type(value) is str and len(value) <= 60 and
         re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\d+/[1-9]\d*)", value)),
         "numbers must be integers or finite decimal/rational strings")
    result = F(value)
    need(abs(result) <= 10**9 and result.denominator <= 10**9, "number outside teaching domain")
    if low is not None:
        need(result > low if strict else result >= low, "numeric domain violation")
    return result


def integer(value, low=0, high=10000):
    need(type(value) is int and low <= value <= high, "whole-number domain violation")
    return value


def side(value):
    need(value in ("buy", "sell"), "side must be buy or sell")
    return 1 if value == "buy" else -1


def sequence(value, low=1, high=100):
    need(type(value) is list and low <= len(value) <= high, "invalid list size")
    return value


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    return value


def spreads(direction, price, mid, future):
    es = 2 * direction * (price - mid)
    rs = 2 * direction * (price - future)
    movement = 2 * direction * (future - mid)
    return {"effective": es, "realized": rs, "midpoint_component": movement,
            "effective_bps": 10000 * es / mid, "realized_bps": 10000 * rs / mid,
            "midpoint_component_bps": 10000 * movement / mid}


def book_case(c):
    keys(c, "quote_time arrival_time mark_time bids asks future_mid fee_per_share cash initial_shares orders")
    t0, t1, th = [integer(c[x]) for x in ("quote_time", "arrival_time", "mark_time")]
    need(t0 <= t1 < th, "quote must precede arrival and future mark must follow it")
    levels = {}
    for label, ascending in (("bids", False), ("asks", True)):
        rows = sequence(c[label])
        parsed = []
        for row in rows:
            need(type(row) is list and len(row) == 2, "price-size pair required")
            parsed.append((num(row[0], 0, True), integer(row[1], 1)))
        prices = [p for p, q in parsed]
        need(prices == sorted(set(prices), reverse=not ascending), "book prices must be strictly sorted")
        levels[label] = parsed
    bid, ask = levels["bids"][0][0], levels["asks"][0][0]
    need(bid < ask, "snapshot book must be uncrossed and unlocked")
    mid = (bid + ask) / 2
    future, fee, cash = num(c["future_mid"], 0, True), num(c["fee_per_share"], 0), num(c["cash"], 0)
    shares = integer(c["initial_shares"])
    results, ids = [], set()
    for order in sequence(c["orders"]):
        keys(order, "id side quantity limit instruction")
        name = order["id"]
        need(type(name) is str and name and name not in ids, "unique order IDs required")
        ids.add(name)
        d, quantity = side(order["side"]), integer(order["quantity"], 1)
        need(order["instruction"] in ("IOC", "FOK"), "only IOC or FOK modeled")
        limit = None if order["limit"] is None else num(order["limit"], 0, True)
        eligible = [(p, q) for p, q in levels["asks" if d == 1 else "bids"]
                    if limit is None or d * (p - limit) <= 0]
        fills, remaining = [], quantity
        if order["instruction"] != "FOK" or sum(q for p, q in eligible) >= quantity:
            for price, available in eligible:
                filled = min(remaining, available)
                if filled:
                    fills.append({"quantity": filled, "price": price})
                remaining -= filled
                if not remaining:
                    break
        filled = quantity - remaining
        gross = sum((x["quantity"] * x["price"] for x in fills), F(0))
        fees = filled * fee
        need(cash - d * gross - fees >= 0, "insufficient cash for snapshot execution")
        need(d != -1 or shares >= quantity, "sell target exceeds initial inventory")
        average = gross / filled if filled else None
        results.append({"id": name, "side": order["side"], "filled": filled,
                        "cancelled": remaining, "fills": fills, "gross": gross, "fees": fees,
                        "cash_change": -d * gross - fees, "average": average,
                        "spreads": spreads(d, average, mid, future) if filled else None})
    return {"arrival_mid": mid, "quoted_spread": ask - bid,
            "quoted_spread_bps": 10000 * (ask - bid) / mid, "orders": results}


def dealer_case(c):
    keys(c, "mid_value value_half_range informed_probability")
    m, delta, theta = num(c["mid_value"], 0, True), num(c["value_half_range"], 0, True), num(c["informed_probability"], 0)
    need(m > delta and theta < 1, "positive values and informed probability below one required")
    ask, bid = m + delta * theta, m - delta * theta
    loss, gain = delta * (1 - theta), delta * theta
    return {"buy_probability": F(1, 2), "high_given_buy": (1 + theta) / 2,
            "high_given_sell": (1 - theta) / 2, "ask": ask, "bid": bid, "spread": ask - bid,
            "informed_gain_per_trade": loss, "dealer_gain_per_uninformed_trade": gain,
            "weighted_informed_loss": -theta * loss, "weighted_uninformed_gain": (1 - theta) * gain,
            "expected_dealer_profit": -theta * loss + (1 - theta) * gain}


def queue_case(c):
    keys(c, "quantity ahead decision_mid immediate_ask limit fee_per_share cash states")
    quantity, ahead = integer(c["quantity"], 1), integer(c["ahead"])
    pd, immediate, limit = [num(c[x], 0, True) for x in ("decision_mid", "immediate_ask", "limit")]
    fee, cash = num(c["fee_per_share"], 0), num(c["cash"], 0)
    need(limit < immediate and immediate >= pd, "passive limit and arrival ask inconsistent")
    immediate_cash = quantity * (immediate + fee)
    need(cash >= immediate_cash, "insufficient immediate cash")
    rows, ids = [], set()
    for state in sequence(c["states"], 2, 10):
        keys(state, "id probability sell_volume deadline_mid deadline_ask")
        name = state["id"]
        need(type(name) is str and name and name not in ids, "unique state IDs required")
        ids.add(name)
        prob = num(state["probability"], 0)
        need(prob <= 1, "invalid probability")
        volume = integer(state["sell_volume"])
        mid, ask = num(state["deadline_mid"], 0, True), num(state["deadline_ask"], 0, True)
        need(ask >= mid, "deadline ask below midpoint")
        fill = min(quantity, max(0, volume - ahead))
        remainder = quantity - fill
        entry_cash = fill * (limit + fee)
        deadline_cash = remainder * (ask + fee)
        complete_cash = entry_cash + deadline_cash
        need(cash >= complete_cash, "insufficient cash for deadline completion")
        paper = cash + quantity * (mid - pd)
        completed = cash - complete_cash + quantity * mid
        cancelled = cash - entry_cash + fill * mid
        rows.append({"id": name, "probability": prob, "passive_fill": fill, "deadline_fill": remainder,
                     "entry_cash": entry_cash, "deadline_cash": deadline_cash, "complete_cash": complete_cash,
                     "paper_wealth": paper, "complete_wealth": completed, "cancel_wealth": cancelled,
                     "complete_shortfall": paper - completed, "cancel_shortfall": paper - cancelled,
                     "conditional_passive_mark_gain": fill * (mid - limit)})
    need(sum(x["probability"] for x in rows) == 1, "probabilities must sum to one")
    expected = lambda key: sum((x["probability"] * x[key] for x in rows), F(0))
    return {"immediate_cash": immediate_cash, "immediate_shortfall": immediate_cash - quantity * pd,
            "states": rows, "expected_complete_cash": expected("complete_cash"),
            "expected_complete_shortfall": expected("complete_shortfall"),
            "expected_cancel_shortfall": expected("cancel_shortfall")}


def shortfall_case(c):
    keys(c, "side quantity decision_time arrival_time terminal_time decision_price arrival_price terminal_price fee_per_share initial_cash initial_shares fills external_trades")
    d, quantity = side(c["side"]), integer(c["quantity"], 1)
    td, ta, tt = [integer(c[x]) for x in ("decision_time", "arrival_time", "terminal_time")]
    need(td < ta < tt, "decision, arrival and terminal dates must be ordered")
    pd, pa, pt = [num(c[x], 0, True) for x in ("decision_price", "arrival_price", "terminal_price")]
    fee, cash = num(c["fee_per_share"], 0), num(c["initial_cash"], 0)
    initial_shares = integer(c["initial_shares"])
    if d == 1:
        need(cash >= quantity * pd, "paper target requires sufficient initial cash")
    else:
        need(initial_shares >= quantity, "sell target exceeds initial inventory")
    def trades(values, allow_empty):
        result, last = [], ta
        for row in sequence(values, 0 if allow_empty else 1):
            keys(row, "time quantity price")
            time = integer(row["time"])
            need(last <= time <= tt, "trade outside arrival-terminal interval or unordered")
            last = time
            result.append((integer(row["quantity"], 1), num(row["price"], 0, True)))
        return result
    fills, external = trades(c["fills"], True), trades(c["external_trades"], False)
    filled = sum(q for q, p in fills)
    need(filled <= quantity, "fills exceed original target")
    gross = sum((q * p for q, p in fills), F(0))
    fees, remainder = filled * fee, quantity - filled
    running_cash = cash
    for q, p in fills:
        running_cash -= d * q * p + q * fee
        need(running_cash >= 0, "insufficient cash at an intermediate fill")
    cash_actual = cash - d * gross - fees
    need(cash_actual >= 0, "actual execution cannot borrow cash")
    paper = cash - d * quantity * pd + (initial_shares + d * quantity) * pt
    actual = cash_actual + (initial_shares + d * filled) * pt
    delay = d * quantity * (pa - pd)
    execution = d * sum((q * (p - pa) for q, p in fills), F(0))
    opportunity = d * remainder * (pt - pa)
    direct = d * (gross - filled * pd + remainder * (pt - pd)) + fees
    benchmark = sum(q * p for q, p in external) / sum(q for q, p in external)
    return {"filled": filled, "unfilled": remainder, "gross": gross, "fees": fees,
            "cash_after_fills": cash_actual, "paper_wealth": paper, "actual_wealth": actual,
            "paper_gain": d * quantity * (pt - pd),
            "actual_gain": d * sum((q * (pt - p) for q, p in fills), F(0)) - fees,
            "delay": delay, "execution": execution, "opportunity": opportunity,
            "shortfall": direct, "wealth_shortfall": paper - actual,
            "shortfall_bps": 10000 * direct / (quantity * pd),
            "average_fill_price": gross / filled if filled else None,
            "external_vwap": benchmark, "filled_vwap_cost": d * (gross - filled * benchmark),
            "filled_vwap_cost_with_fees": d * (gross - filled * benchmark) + fees}


def impact_case(c):
    keys(c, "quantity initial_mid shock_magnitude persistent_k temporary_eta1 temporary_eta2 half_spread_and_fee lambda capacity1 capacity2 cash gross_benefit_per_share")
    quantity = integer(c["quantity"], 0, 201)
    m, shock, k, e1, e2, h, lam, cash, benefit = [num(c[x], 0, x in ("initial_mid", "temporary_eta1", "temporary_eta2"))
        for x in ("initial_mid", "shock_magnitude", "persistent_k", "temporary_eta1", "temporary_eta2", "half_spread_and_fee", "lambda", "cash", "gross_benefit_per_share")]
    u1, u2 = integer(c["capacity1"], 0, 100), integer(c["capacity2"], 0, 100)
    need(m > shock, "unaffected price must be positive in both states")
    variance = shock * shock
    def candidates(q):
        result = []
        for a in range(max(0, q - u2), min(q, u1) + 1):
            b = q - a
            p1 = m + k * a / 2 + e1 * a + h
            p2 = m + k * a + k * b / 2 + e2 * b + h
            mean = k * q * q / 2 + h * q + e1 * a * a + e2 * b * b
            var = b * b * variance
            low_cash, high_cash = a * p1 + b * (p2 - shock), a * p1 + b * (p2 + shock)
            need(cash >= high_cash, "prefunded domain requires cash for every allowed schedule")
            result.append({"q1": a, "q2": b, "expected_cost": mean, "variance": var,
                           "objective": mean + lam * var, "block1_price": p1 if a else None,
                           "block2_prices": [p2 - shock, p2 + shock] if b else [],
                           "state_costs": [low_cash - q * m, high_cash - q * m],
                           "state_cash": [low_cash, high_cash]})
        return result
    rows = candidates(quantity)
    def best(items):
        return min(items, key=lambda x: (x["objective"], x["q1"])) if items else None
    grid = []
    for q in range(u1 + u2 + 1):
        items = candidates(q)
        selected = best(items)
        ties = [[x["q1"], x["q2"]] for x in items if x["objective"] == selected["objective"]]
        grid.append({"quantity": q, "q1": selected["q1"], "q2": selected["q2"],
                     "objective": selected["objective"], "gross_benefit": benefit * q,
                     "net_score": benefit * q - selected["objective"], "optimal_schedules": ties})
    max_score = max(x["net_score"] for x in grid)
    chosen_quantity = min(x["quantity"] for x in grid if x["net_score"] == max_score)
    continuous = quantity * (e2 + lam * variance) / (e1 + e2 + lam * variance)
    projected = min(max(continuous, max(0, quantity - u2)), min(quantity, u1)) if rows else None
    return {"objective_convention": "E[cost] + lambda Var(cost)", "feasible": bool(rows),
            "continuous_unconstrained_q1": continuous, "continuous_feasible_q1": projected,
            "candidates": rows, "selected": best(rows), "capacity_grid": grid,
            "tie_rule": "smaller first block; then smaller total quantity for equal net scores",
            "physical_capacity": u1 + u2, "optimal_quantity": chosen_quantity,
            "largest_nonnegative_score_quantity": max(x["quantity"] for x in grid if x["net_score"] >= 0)}


def run(data):
    """Validate and return strict-JSON-compatible exact output; no I/O."""
    keys(data, "case_id provenance conventions book dealer queue shortfall impact")
    need(data["case_id"] == "v09-c11-execution-1", "unknown case ID")
    need(data["provenance"] == "Original synthetic teaching contracts; no observed prices or calibrated trading estimates.", "synthetic provenance must remain explicit")
    need(data["conventions"] == CONVENTIONS, "contradictory convention label")
    return encode({"case_id": data["case_id"], "book": book_case(data["book"]),
                   "dealer": dealer_case(data["dealer"]), "queue": queue_case(data["queue"]),
                   "shortfall": shortfall_case(data["shortfall"]), "impact": impact_case(data["impact"])})


def load_json(path):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, "duplicate JSON field")
            result[k] = v
        return result
    def invalid(value):
        raise ValueError("non-finite JSON number")
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("v09-c11-inputs.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = run(load_json(args.input))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
