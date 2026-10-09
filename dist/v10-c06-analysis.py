"""Exact, bounded Linden option replication and finite exercise-grid laboratory."""
import argparse
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import re


CONTRACT = "Original Linden finite options market; unrestricted signed stock and cash trading; common borrowing/lending gross rate; no default or fees except the named rebalance intervention"
DIVIDEND_CONTRACT = "One period: choose exercise now or after the next dividend; stockholders receive the known cash dividend immediately before terminal ex-dividend option settlement; no intervening exercise date"
NUMBER = re.compile(r"-?\d{1,8}(?:\.\d{1,8}|/[1-9]\d{0,7})?\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, names):
    require(isinstance(value, dict) and set(value) == set(names.split()), "Unexpected or missing contract fields")


def number(value):
    require(isinstance(value, str) and NUMBER.fullmatch(value), "Finite bounded decimal/rational strings required")
    return F(value)


def payoff(spot, strike, kind):
    return max(spot-strike if kind == "call" else strike-spot, F(0))


def parameters(data, extended=False):
    keys(data, "spot strike up down gross_rate" + (" steps physical_up interior_rebalance_fee" if extended else ""))
    s, k, u, d, r = (number(data[x]) for x in ("spot", "strike", "up", "down", "gross_rate"))
    require(0 < s <= 10000 and 0 <= k <= 10000, "Positive bounded stock price and nonnegative strike required")
    require(F(1, 10) <= d < r < u <= 3, "Strictly positive two-state prices require 0<down<gross_rate<up")
    if extended:
        require(type(data["steps"]) is int and 1 <= data["steps"] <= 6, "One to six finite exercise periods required")
        p, fee = number(data["physical_up"]), number(data["interior_rebalance_fee"])
        require(0 < p < 1, "Both physical branches must have positive support")
        require(0 <= fee <= F(1, 10), "Interior rebalance fee must lie between zero and ten percent")
    return s, k, u, d, r


def price_tree(s, k, u, d, r, n):
    q = (r-d)/(u-d)
    stock = [[s*u**j*d**(t-j) for j in range(t+1)] for t in range(n+1)]
    contracts = {}
    for kind in ("call", "put"):
        for style in ("european", "american_grid"):
            rows = [None]*(n+1)
            rows[n] = [{"stock": st, "intrinsic": payoff(st, k, kind), "value": payoff(st, k, kind),
                        "action": "settle"} for st in stock[n]]
            for t in range(n-1, -1, -1):
                rows[t] = []
                for j, st in enumerate(stock[t]):
                    vd, vu = rows[t+1][j]["value"], rows[t+1][j+1]["value"]
                    delta = (vu-vd)/(st*(u-d))
                    bank = (vd-delta*st*d)/r
                    continuation = delta*st+bank
                    intrinsic = payoff(st, k, kind)
                    exercise = style == "american_grid" and intrinsic > continuation
                    value = intrinsic if exercise else continuation
                    rows[t].append({"stock": st, "intrinsic": intrinsic, "continuation": continuation,
                                    "value": value, "action": "exercise" if exercise else "continue",
                                    "continuation_delta": delta, "continuation_bank": bank,
                                    "exercise_value_less_continuation": intrinsic-continuation,
                                    "cash_above_continuation_cost": value-continuation,
                                    "down_replication_residual": delta*st*d+r*bank-vd,
                                    "up_replication_residual": delta*st*u+r*bank-vu})
            contracts[kind+"_"+style] = rows
    return {"q_up": q, "stock": stock, "contracts": contracts,
            "european_parity_lhs": contracts["call_european"][0][0]["value"]-contracts["put_european"][0][0]["value"],
            "european_parity_rhs": s-k/r**n,
            "american_put_premium": contracts["put_american_grid"][0][0]["value"]-contracts["put_european"][0][0]["value"]}


def path_reports(tree, s, k, u, d, r, n, p, fee):
    q = tree["q_up"]
    paths = []
    for bits in product((0, 1), repeat=n):
        qprob = q**sum(bits)*(1-q)**(n-sum(bits))
        pprob = p**sum(bits)*(1-p)**(n-sum(bits))
        st, j = s, 0
        call = tree["contracts"]["call_european"]
        delta, bank = call[0][0]["continuation_delta"], call[0][0]["continuation_bank"]
        fee_bank = bank
        ledger = []
        for t, bit in enumerate(bits, 1):
            st *= u if bit else d
            j += bit
            wealth = delta*st+r*bank
            fee_wealth = delta*st+r*fee_bank
            row = {"date": t, "stock": st, "inherited_delta": delta,
                   "inherited_bank_after_interest": r*bank, "pre_trade_wealth": wealth,
                   "call_value": call[t][j]["value"]}
            if t < n:
                new_delta, new_bank = call[t][j]["continuation_delta"], call[t][j]["continuation_bank"]
                stock_trade = (new_delta-delta)*st
                trading_fee = abs(stock_trade)*fee
                row.update({"new_delta": new_delta, "new_bank": new_bank,
                            "stock_trade_cash": stock_trade, "bank_change": new_bank-r*bank,
                            "external_cash_required": new_delta*st+new_bank-wealth,
                            "intervention_fee": trading_fee})
                fee_bank = fee_wealth-new_delta*st-trading_fee
                delta, bank = new_delta, new_bank
            else:
                row.update({"payoff": payoff(st, k, "call"),
                            "exact_hedge_error": wealth-payoff(st, k, "call"),
                            "fee_intervention_hedge_error": fee_wealth-payoff(st, k, "call")})
            ledger.append(row)
        stopping = {}
        for kind in ("call", "put"):
            rows = tree["contracts"][kind+"_american_grid"]
            index = 0
            for t in range(n+1):
                node = rows[t][index]
                if t == n or node["action"] == "exercise":
                    stopping[kind] = {"date": t, "stock": node["stock"], "receipt": node["intrinsic"],
                                      "discounted_receipt": node["intrinsic"]/r**t}
                    break
                index += bits[t]
        paths.append({"path": "".join("U" if b else "D" for b in bits), "pricing_probability": qprob,
                      "physical_probability": pprob, "european_call_ledger": ledger,
                      "american_grid_optimal_stopping": stopping})
    return {"paths": paths,
            "optimal_stopping_discounted_pricing_expectations": {
                kind: sum(row["pricing_probability"]*row["american_grid_optimal_stopping"][kind]["discounted_receipt"] for row in paths)
                for kind in ("call", "put")},
            "european_call_physical_expected_payoff": sum(row["physical_probability"]*row["european_call_ledger"][-1]["payoff"] for row in paths)}


def dividend_case(data):
    keys(data, "contract spot strike ex_up ex_down cash_dividend gross_rate")
    require(data["contract"] == DIVIDEND_CONTRACT, "Dividend entitlement/exercise clock must remain explicit")
    s, k, su, sd, cash, r = (number(data[x]) for x in ("spot", "strike", "ex_up", "ex_down", "cash_dividend", "gross_rate"))
    require(0 < s <= 10000 and 0 <= k <= 10000 and 0 <= cash <= 10000, "Bounded spot, strike and known dividend required")
    require(0 < sd < su <= 30000 and F(1, 10) <= r <= 3, "Positive ex-dividend prices and gross rate required")
    require(sd+cash < r*s < su+cash, "Stock total gain, including dividend, must admit positive state prices")
    q = (r*s-sd-cash)/(su-sd)
    results = {}
    for kind in ("call", "put"):
        vd, vu = payoff(sd, k, kind), payoff(su, k, kind)
        delta = (vu-vd)/(su-sd)
        bank = (vd-delta*(sd+cash))/r
        european = delta*s+bank
        intrinsic = payoff(s, k, kind)
        results[kind] = {"down_payoff": vd, "up_payoff": vu, "delta": delta, "bank": bank,
                         "european_value": european, "immediate_exercise": intrinsic,
                         "american_grid_value": max(intrinsic, european),
                         "action": "exercise" if intrinsic > european else "continue",
                         "down_hedge_residual": delta*(sd+cash)+r*bank-vd,
                         "up_hedge_residual": delta*(su+cash)+r*bank-vu}
    return {"q_up_total_gain": q, "dividend_pv": cash/r, "prepaid_terminal_stock": s-cash/r,
            "contracts": results, "european_parity_lhs": results["call"]["european_value"]-results["put"]["european_value"],
            "european_parity_rhs": s-cash/r-k/r,
            "scope": "Exercise only now or after the terminal dividend; adding a pre-dividend exercise opportunity changes the contract."}


def serial(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serial(v) for v in value]
    return value


def run(data):
    keys(data, "schema contract tree negative_rate_call dividend_call")
    require(type(data["schema"]) is int and data["schema"] == 1 and data["contract"] == CONTRACT, "Unsupported schema or market contract")
    s, k, u, d, r = parameters(data["tree"], True)
    n = data["tree"]["steps"]
    p, fee = number(data["tree"]["physical_up"]), number(data["tree"]["interior_rebalance_fee"])
    tree = price_tree(s, k, u, d, r, n)
    negative = parameters(data["negative_rate_call"])
    require(negative[4] < 1, "The named negative-rate counterexample requires gross_rate<1")
    result = {"case": "Linden finite option market", "single_step": price_tree(s, k, u, d, r, 1),
              "tree": tree, "path_reports": path_reports(tree, s, k, u, d, r, n, p, fee),
              "negative_rate_case": price_tree(*negative, 1), "dividend_case": dividend_case(data["dividend_call"]),
              "scope": "Exact finite exercise-grid prices conditional on stated trading rights; physical probabilities do not set replication values; no continuous-time or real-market hedge guarantee."}
    result = serial(result)
    json.dumps(result, allow_nan=False)
    return result


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "Duplicate JSON key")
        out[key] = value
    return out


def bad_constant(value):
    raise ValueError("Nonfinite JSON token: " + value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("v10-c06-inputs.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(), object_pairs_hook=unique_object, parse_constant=bad_constant)
    report = json.dumps(run(data), indent=2, allow_nan=False)+"\n"
    if args.output:
        args.output.write_text(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
