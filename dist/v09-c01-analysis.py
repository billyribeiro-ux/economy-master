"""Serein: a bounded, original return-measurement teaching model.

No dependencies, network or writes. Rational money/returns remain exact;
logarithms and the unique annual money-weighted root are finite floats.
"""
from fractions import Fraction as F
import json
import math
from pathlib import Path
import sys


def need(condition, message):
    if not condition:
        raise ValueError(message)


def q(value):
    need(isinstance(value, (str, int)) and not isinstance(value, bool),
         "Use integer or rational/decimal-string inputs, not binary float inputs")
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("Invalid rational input") from error


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    return value


def log_return(gross):
    """Zero wealth has no finite real log return; negative wealth is out of scope."""
    need(gross >= 0, "Negative terminal wealth cannot be a positive-wealth log return")
    return math.log(float(gross)) if gross > 0 else None


def annualized(gross, years):
    need(gross >= 0 and years > 0, "Annualization requires nonnegative gross wealth and positive elapsed years")
    return float(gross) ** (1 / years) - 1


def dividend_path(data):
    start = q(data["opening_price"])
    need(start > 0, "Opening price must be positive")
    observations = data["observations"]
    need(len(observations) == 2, "This exercise has two annual intervals")
    price, shares, cash, factor = start, F(1), F(0), F(1)
    rows = []
    for year, item in enumerate(observations, 1):
        close, distribution = q(item["ex_dividend_price"]), q(item["cash_distribution"])
        need(close > 0 and distribution >= 0, "Reinvestment case needs positive ex prices and nonnegative distributions")
        gross = (close + distribution) / price
        factor *= gross
        cash += distribution  # Separate strategy: one unchanged share, zero-yield cash.
        shares *= (close + distribution) / close
        rows.append({"year": year, "simple_total_return": gross - 1,
                     "log_total_return": log_return(gross), "gross_factor": gross,
                     "reinvested_shares_after_distribution": shares,
                     "reinvested_wealth": shares * close,
                     "one_share_plus_retained_cash": close + cash})
        price = close
    return {"rows": rows, "price_return": price / start - 1,
            "reinvested_gross": factor, "reinvested_cumulative_return": factor - 1,
            "reinvested_annualized_return": annualized(factor, 2),
            "reinvested_log_return": log_return(factor),
            "retained_cash_cumulative_return": (price + cash) / start - 1}


def flow_account(data):
    need(data["dates"] == [0, 1, 2], "The closed-form root assumes exactly two equal one-year intervals")
    opening, at_flow, contribution, end = [q(data[k]) for k in
                                          ("opening", "before_contribution", "contribution", "terminal_liquidation")]
    alternate = q(data["alternative_before_contribution"])
    need(opening > 0 and at_flow > 0 and alternate > 0 and end > 0 and contribution >= 0,
         "Account case permits positive valuations, one nonnegative contribution and final liquidation")
    after = at_flow + contribution
    gross1, gross2 = at_flow / opening, end / after
    twr = gross1 * gross2
    # Solve opening*x^2 + contribution*x = end. This stable positive-root
    # expression avoids subtracting nearly equal positive quantities.
    discriminant = contribution * contribution + 4 * opening * end
    x = 2 * float(end) / (float(contribution) + math.sqrt(float(discriminant)))
    dietz_denominator = opening + contribution / 2
    return {"opening": opening, "before_contribution": at_flow,
            "after_contribution": after, "terminal_liquidation": end,
            "subperiod_simple_returns": [gross1 - 1, gross2 - 1],
            "twr_cumulative": twr - 1, "twr_annualized": annualized(twr, 2),
            "money_weighted_annual_return": x - 1,
            "mwr_terminal_equation_residual": float(opening) * x*x + float(contribution) * x - float(end),
            "investor_net_cash_gain": end - opening - contribution,
            "modified_dietz_cumulative": (end - opening - contribution) / dietz_denominator,
            "alternative_twr_cumulative": alternate / opening * end / (alternate + contribution) - 1,
            "root_scope": "Unique x>0 for positive opening/final values and one nonnegative date1 contribution; not a general mixed-sign IRR solver"}


def fee_account(data):
    initial = q(data["opening_cash"])
    entry, management, exit_cost = [q(data[k]) for k in
                                     ("entry_charge_fraction", "post_return_management_fraction", "exit_charge_fraction")]
    returns = [q(x) for x in data["pre_fee_simple_returns"]]
    need(initial > 0 and len(returns) == 2, "Positive investment and two annual observations required")
    need(all(0 <= v < 1 for v in (entry, management, exit_cost)), "Charge fractions must be in [0,1)")
    need(all(r > -1 for r in returns), "Fee example requires positive assets after each market return")
    wealth, pre_fee_factor, rows = initial * (1-entry), F(1), []
    for year, ret in enumerate(returns, 1):
        opening = wealth
        before_fee = opening * (1+ret)
        fee = before_fee * management
        wealth = before_fee - fee
        pre_fee_factor *= 1+ret
        rows.append({"year": year, "opening_invested_assets": opening,
                     "before_management_fee": before_fee, "management_fee": fee,
                     "closing_assets": wealth, "net_simple_return": wealth/opening-1})
    exit_fee = wealth * exit_cost
    receipt = wealth - exit_fee
    return {"entry_fee": initial * entry, "rows": rows, "exit_fee": exit_fee,
            "final_investor_receipt": receipt, "investor_cumulative_return": receipt/initial-1,
            "pre_fee_asset_cumulative_return": pre_fee_factor-1,
            "after_management_before_loads_cumulative_return": pre_fee_factor*(1-management)**2-1}


def currency_return(data):
    local = q(data["foreign_simple_total_return"])
    fx0, fx1 = q(data["opening_home_per_foreign"]), q(data["closing_home_per_foreign"])
    inflation = q(data["home_inflation"])
    need(local >= -1 and fx0 > 0 and fx1 > 0 and inflation > -1,
         "Require nonnegative foreign gross wealth, positive FX and positive price-level factor")
    home_gross = (1+local) * fx1/fx0
    real_gross = home_gross / (1+inflation)
    return {"fx_simple_return": fx1/fx0-1, "home_nominal_return": home_gross-1,
            "home_real_return": real_gross-1, "home_nominal_log_return": log_return(home_gross),
            "home_real_log_return": log_return(real_gross)}


def opportunity(data):
    states = data["states"]
    prob, a, b = ([q(x) for x in data[k]] for k in ("probabilities", "returns_a", "returns_b"))
    w, floor = q(data["selected_weight_a"]), q(data["minimum_state_return"])
    need(len(states) == 3 and len(set(states)) == 3 and len(prob) == len(a) == len(b) == 3,
         "Exactly three distinct named states and matched vectors required")
    need(all(p > 0 for p in prob) and sum(prob) == 1, "Physical probabilities must be positive and sum to one")
    need(all(r >= -1 for r in a+b) and 0 <= w <= 1 and floor >= -1,
         "Bounded fully invested long-only nonnegative-wealth model")
    chosen = [w*x+(1-w)*y for x,y in zip(a,b)]
    lower, upper = F(0), F(1)
    for x,y in zip(a,b):
        slope = x-y
        if slope > 0:
            lower = max(lower, (floor-y)/slope)
        elif slope < 0:
            upper = min(upper, (floor-y)/slope)
        else:
            need(y >= floor, "No feasible long-only mix meets the state floor")
    need(lower <= upper, "No feasible long-only mix meets the state floor")
    mean_a, mean_b = sum(p*x for p,x in zip(prob,a)), sum(p*x for p,x in zip(prob,b))
    best = upper if mean_a > mean_b else lower
    best_returns = [best*x+(1-best)*y for x,y in zip(a,b)]
    return {"asset_expected_returns": [mean_a, mean_b], "selected_state_returns": chosen,
            "selected_expected_return": sum(p*r for p,r in zip(prob,chosen)),
            "selected_meets_floor": all(r >= floor for r in chosen),
            "feasible_weight_a_interval": [lower, upper], "highest_mean_feasible_weight_a": best,
            "highest_mean_feasible_state_returns": best_returns,
            "highest_mean_feasible_expected_return": sum(p*r for p,r in zip(prob,best_returns)),
            "scope": "Highest supplied physical mean within this one-dimensional long-only state-floor mandate; no optimal-risk or pricing claim"}


def rebalancing(data):
    wealth = q(data["opening_wealth"])
    weights = [q(x) for x in data["initial_weights"]]
    returns = [[q(x) for x in row] for row in data["period_returns"]]
    need(wealth > 0 and len(weights) == 2 and sum(weights) == 1 and all(w >= 0 for w in weights),
         "Positive wealth and two fully invested long-only weights required")
    need(len(returns) == 2 and all(len(row) == 2 and all(r > -1 for r in row) for row in returns),
         "Two positive-wealth annual asset-return rows required")
    strategies = {}
    for name in ("buy_and_hold", "constant_weights"):
        assets, rows = [wealth*w for w in weights], []
        for year, rs in enumerate(returns, 1):
            opening = sum(assets)
            start_weights = [x/opening for x in assets]
            assets = [x*(1+r) for x,r in zip(assets,rs)]
            end = sum(assets)
            rows.append({"year": year, "beginning_weights": start_weights,
                         "before_rebalance_asset_values": list(assets),
                         "wealth": end, "portfolio_simple_return": end/opening-1,
                         "portfolio_log_return": log_return(end/opening)})
            if name == "constant_weights" and year < len(returns):
                assets = [end*w for w in weights]
        strategies[name] = {"rows": rows, "cumulative_return": sum(assets)/wealth-1}
    return strategies


def run(data):
    expected = {"period": "one year; dates 0, 1 and 2 are equally spaced model years",
                "dividends": "cash paid at each end date; prices are unadjusted ex-dividend prices; immediate reinvestment has no costs or tax",
                "cash_flow": "one nonnegative investor contribution immediately after the date-1 valuation; complete liquidation at date 2",
                "fees": "entry and exit charges on the cash entering and leaving respectively; management fee on post-market assets at each year end",
                "fx": "home CU per one foreign currency unit",
                "opportunity": "one common period; fractional fully invested long-only positions in A and B; no trading costs",
                "rebalancing": "two asset returns per annual interval, no external flows, no fees; rebalance after first-period returns"}
    need(all(data["conventions"].get(k) == value for k,value in expected.items()),
         "Preserve the documented timing, fee base, FX orientation and mandate; this is not a general performance engine")
    return encode({"case": data["case"], "dividends": dividend_path(data["dividends"]),
                   "cash_flow_account": flow_account(data["account"]), "fees": fee_account(data["fees"]),
                   "currency": currency_return(data["foreign"]), "opportunity": opportunity(data["opportunity"]),
                   "rebalancing": rebalancing(data["rebalancing"])})


if __name__ == "__main__":
    inputs = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("v09-c01-inputs.json")
    print(json.dumps(run(json.loads(inputs.read_text())), indent=2, allow_nan=False))
