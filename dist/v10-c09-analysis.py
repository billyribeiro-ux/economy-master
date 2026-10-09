"""Original Oriole sensitivities, implied volatility and funded hedging lab.

Standard library only. Parameters and scenarios are authored, not market data.
All rates are continuously compounded per year; sigma is per square-root year.
"""
import argparse
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, names, label):
    require(isinstance(value, dict) and set(value) == set(names.split()), label+": incorrect fields")


def number(value, low, high, label):
    require(type(value) in (int, float), label+": finite JSON number required")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(label+": invalid magnitude") from exc
    require(math.isfinite(result) and low <= result <= high, label+": outside finite bounds")
    return result


def cdf(x):
    return 0.5*math.erfc(-x/math.sqrt(2.0))


def density(x):
    return math.exp(-0.5*x*x)/math.sqrt(2.0*math.pi)


def parameters(data):
    keys(data, "spot strike tau rate dividend sigma", "base")
    return {
        "spot": number(data["spot"], 1, 10000, "spot"),
        "strike": number(data["strike"], 1, 10000, "strike"),
        "tau": number(data["tau"], 0.0001, 5, "tau"),
        "rate": number(data["rate"], -0.2, 0.2, "rate"),
        "dividend": number(data["dividend"], 0, 0.2, "dividend"),
        "sigma": number(data["sigma"], 0.0001, 3, "sigma"),
    }


def vanilla(spot, strike, tau, rate, dividend, sigma):
    """Internal bounded valuation primitive; boundary prices omit smooth Greeks."""
    a, h = spot*math.exp(-dividend*tau), strike*math.exp(-rate*tau)
    if spot == 0 or tau == 0 or sigma == 0:
        call, put = max(a-h, 0.0), max(h-a, 0.0)
        return {"call": call, "put": put, "prepaid_stock": a, "discounted_strike": h,
                "call_delta": None, "put_delta": None, "gamma": None, "vega": None,
                "call_theta": None, "put_theta": None,
                "derivative_status": "boundary price only; interior Greek formulas not applied"}
    scale = sigma*math.sqrt(tau)
    d1 = (math.log(spot/strike)+(rate-dividend+0.5*sigma*sigma)*tau)/scale
    d2 = d1-scale
    # Evaluate the out-of-money leg directly, then use parity for its partner.
    # This avoids subtracting two large intrinsic terms for the small leg.
    if a <= h:
        call = max(a*cdf(d1)-h*cdf(d2), 0.0)
        put = call+h-a
    else:
        put = max(h*cdf(-d2)-a*cdf(-d1), 0.0)
        call = put+a-h
    discount_dividend = math.exp(-dividend*tau)
    gamma = discount_dividend*density(d1)/(spot*scale)
    vega = a*density(d1)*math.sqrt(tau)
    theta = -a*density(d1)*sigma/(2*math.sqrt(tau))+dividend*a*cdf(d1)-rate*h*cdf(d2)
    return {"call": call, "put": put, "prepaid_stock": a, "discounted_strike": h,
            "d1": d1, "d2": d2, "call_delta": discount_dividend*cdf(d1),
            "put_delta": -discount_dividend*cdf(-d1), "gamma": gamma, "vega": vega,
            "call_theta": theta, "put_theta": theta-dividend*a+rate*h,
            "vega_per_volatility_point": vega*0.01,
            "derivative_status": "interior; floating-point vega may underflow in extreme tails"}


def implied_call(p, quote, cap):
    """Bracketed inversion with honest numerical boundary and cap statuses."""
    a = p["spot"]*math.exp(-p["dividend"]*p["tau"])
    h = p["strike"]*math.exp(-p["rate"]*p["tau"])
    lower, upper = max(a-h, 0.0), a
    require(lower <= quote <= upper, "call quote violates its individual model bounds")
    price_tolerance = 1e-11*max(1.0, a, h)
    report = {"quote": quote, "lower_price_bound": lower, "upper_price_bound": upper,
              "price_resolution": price_tolerance, "sigma_cap": cap, "sigma": None,
              "bracket": None, "price_residual": None, "iterations": 0}
    if quote == lower:
        report.update(status="zero_volatility_limit", sigma=0.0, price_residual=0.0)
        return report
    if quote == upper:
        report.update(status="upper_bound_has_no_finite_implied_volatility")
        return report
    if min(quote-lower, upper-quote) <= price_tolerance:
        report.update(status="unresolved_near_price_boundary")
        return report
    def value(sigma):
        return vanilla(**dict(p, sigma=sigma))["call"]
    lo, hi = 0.0, cap
    high_price = value(hi)
    if high_price < quote:
        report.update(status="root_above_declared_sigma_cap", price_at_cap=high_price)
        return report
    # A price-only stopping rule can pretend a flat-vega inverse is precise.
    # Retain the price bracket and stop on its volatility width instead.
    for iteration in range(1, 81):
        mid = (lo+hi)/2
        if mid == lo or mid == hi:
            break
        if value(mid) < quote:
            lo = mid
        else:
            hi = mid
        if hi-lo <= 1e-10:
            break
    sigma = (lo+hi)/2
    result = vanilla(**dict(p, sigma=sigma))
    report.update(status="bracketed", sigma=sigma, bracket=[lo, hi],
                  bracket_prices=[value(lo), value(hi)], price_residual=result["call"]-quote,
                  iterations=iteration, vega_at_solution=result["vega"],
                  local_sigma_change_per_price_unit=(1/result["vega"] if result["vega"] > 1e-12 else None))
    return report


def hedge(p, spec):
    keys(spec, "times spots interior_fee", "hedge")
    require(isinstance(spec["times"], list) and isinstance(spec["spots"], list)
            and 2 <= len(spec["times"]) <= 25 and len(spec["times"]) == len(spec["spots"]), "hedge path dimensions")
    times = [number(t, 0, 5, "hedge time") for t in spec["times"]]
    spots = [number(s, 1, 10000, "hedge spot") for s in spec["spots"]]
    require(times[0] == 0 and times[-1] == p["tau"] and spots[0] == p["spot"], "hedge initial and terminal contract match")
    require(all(a < b for a, b in zip(times, times[1:])), "strictly increasing hedge times")
    require(all(p["tau"]-t >= 0.0001 for t in times[:-1]), "interior hedge tau below declared Greek domain")
    fee_rate = number(spec["interior_fee"], 0, 0.05, "interior fee")
    initial = vanilla(**p)
    shares = initial["call_delta"]
    bank = initial["call"]-shares*spots[0]
    fee_bank = bank
    rows = []
    for i in range(1, len(times)):
        dt = times[i]-times[i-1]
        incoming_shares = shares*math.exp(p["dividend"]*dt)
        incoming_bank = bank*math.exp(p["rate"]*dt)
        incoming_fee_bank = fee_bank*math.exp(p["rate"]*dt)
        wealth = incoming_shares*spots[i]+incoming_bank
        marked = vanilla(**dict(p, spot=spots[i], tau=p["tau"]-times[i]))
        row = {"date": times[i], "spot": spots[i], "incoming_shares_after_dividends": incoming_shares,
               "incoming_bank": incoming_bank, "wealth_before_trade": wealth, "call_mark": marked["call"]}
        if i < len(times)-1:
            target = marked["call_delta"]
            trade = (target-incoming_shares)*spots[i]
            fee = abs(trade)*fee_rate
            bank = incoming_bank-trade
            fee_bank = incoming_fee_bank-trade-fee
            shares = target
            row.update(target_shares=target, stock_trade_cash=trade, ideal_bank_after_trade=bank,
                       fee=fee, bank_with_fees_after_trade=fee_bank,
                       self_financing_residual=target*spots[i]+bank-wealth,
                       unhedged_mark_difference=wealth-marked["call"])
        else:
            payoff = max(spots[i]-p["strike"], 0.0)
            row.update(payoff=payoff, ideal_terminal_error=wealth-payoff,
                       funded_fee_terminal_error=incoming_shares*spots[i]+incoming_fee_bank-payoff)
        rows.append(row)
    return {"initial_price": initial["call"], "initial_shares": initial["call_delta"],
            "initial_bank": initial["call"]-initial["call_delta"]*p["spot"], "ledger": rows,
            "scope": "Dividend reinvestment is continuous and frictionless between scheduled delta resets; only interior reset stock trades pay the stated fee. No external cash injection or terminal reset to the model mark."}


def run(data):
    keys(data, "schema provenance base position shock iv smile hedge variance_account", "root")
    require(type(data["schema"]) is int and data["schema"] == 1 and isinstance(data["provenance"], str), "schema/provenance")
    p = parameters(data["base"])
    values = vanilla(**p)
    pos = data["position"]
    keys(pos, "contracts multiplier stock_units", "position")
    require(type(pos["contracts"]) is int and abs(pos["contracts"]) <= 10000, "integer contract count")
    multiplier = number(pos["multiplier"], 1, 10000, "multiplier")
    stock_units = number(pos["stock_units"], -1e8, 1e8, "stock units")
    units = pos["contracts"]*multiplier
    portfolio = {"option_units": units, "call_market_value": units*values["call"],
                 "delta_shares": units*values["call_delta"]+stock_units,
                 "gamma": units*values["gamma"], "vega_per_unit_sigma": units*values["vega"],
                 "vega_per_volatility_point": units*values["vega"]*0.01,
                 "calendar_theta_per_year": units*values["call_theta"],
                 "stock_trade_to_zero_delta": -units*values["call_delta"]-stock_units}
    shock = data["shock"]
    keys(shock, "spot_change vol_change elapsed", "shock")
    ds = number(shock["spot_change"], -1000, 1000, "spot change")
    dv = number(shock["vol_change"], -1, 1, "vol change")
    elapsed = number(shock["elapsed"], 0, 1, "elapsed")
    moved = parameters(dict(p, spot=p["spot"]+ds, sigma=p["sigma"]+dv, tau=p["tau"]-elapsed))
    exact_change = vanilla(**moved)["call"]-values["call"]
    terms = {"delta": values["call_delta"]*ds, "gamma": 0.5*values["gamma"]*ds*ds,
             "vega": values["vega"]*dv, "theta": values["call_theta"]*elapsed}
    spot_only = vanilla(**dict(p, spot=p["spot"]+ds))["call"]-values["call"]
    smin, smax = sorted([p["spot"], p["spot"]+ds])
    scale = p["sigma"]*math.sqrt(p["tau"])
    max_d1 = max(abs((math.log(s/p["strike"])+(p["rate"]-p["dividend"]+p["sigma"]**2/2)*p["tau"])/scale) for s in (smin, smax))
    third_bound = math.exp(-p["dividend"]*p["tau"])/(math.sqrt(2*math.pi)*smin*smin*scale)*(1+max_d1/scale)
    approximation = sum(terms.values())
    shocks = {"terms": terms, "approximate_change": approximation, "exact_repriced_change": exact_change,
              "mixed_shock_residual": exact_change-approximation,
              "spot_only_exact_change": spot_only, "spot_only_taylor_change": terms["delta"]+terms["gamma"],
              "spot_only_remainder_bound": third_bound*abs(ds)**3/6,
              "bound_scope": "Certified analytic spot-only third-derivative bound; no claim this bounds the mixed time/volatility residual."}
    iv = data["iv"]
    keys(iv, "call_price sigma_cap", "iv")
    quote = number(iv["call_price"], 0, 10000, "IV call price")
    cap = number(iv["sigma_cap"], 0.01, 4, "IV sigma cap")
    inverse = implied_call(p, quote, cap)
    smile = data["smile"]
    keys(smile, "spot tau rate dividend strikes call_prices", "smile")
    require(isinstance(smile["strikes"], list) and isinstance(smile["call_prices"], list)
            and 3 <= len(smile["strikes"]) <= 12 and len(smile["strikes"]) == len(smile["call_prices"]), "smile dimensions")
    strikes = [number(k, 1, 10000, "smile strike") for k in smile["strikes"]]
    prices = [number(c, 0, 10000, "smile price") for c in smile["call_prices"]]
    require(all(a < b for a, b in zip(strikes, strikes[1:])), "strictly increasing smile strikes")
    market = parameters({key: smile[key] for key in ("spot", "tau", "rate", "dividend")} | {"strike": strikes[0], "sigma": p["sigma"]})
    inverses = [implied_call(dict(market, strike=k), c, cap) for k, c in zip(strikes, prices)]
    discount = math.exp(-market["rate"]*market["tau"])
    slopes = [(b-a)/(kb-ka) for a, b, ka, kb in zip(prices, prices[1:], strikes, strikes[1:])]
    convexity = [((strikes[i+1]-strikes[i])*prices[i-1]+(strikes[i]-strikes[i-1])*prices[i+1])/(strikes[i+1]-strikes[i-1])-prices[i] for i in range(1, len(strikes)-1)]
    surface = {"individual_implied_volatilities": inverses, "adjacent_price_slopes": slopes,
               "weighted_butterfly_costs": convexity,
               "vertical_spread_screen_passes": all(-discount-1e-12 <= slope <= 1e-12 for slope in slopes),
               "convexity_screen_passes": all(cost >= -1e-12 for cost in convexity),
               "scope": "Finite same-expiry quote tests only; passing does not construct an arbitrage-free dynamic surface."}
    variance = data["variance_account"]
    keys(variance, "durations discounted_cash_gammas model_sigma actual_sigmas", "variance account")
    require(all(isinstance(variance[key], list) for key in ("durations", "discounted_cash_gammas", "actual_sigmas")), "variance account arrays")
    size = len(variance["durations"])
    require(1 <= size <= 24 and len(variance["discounted_cash_gammas"]) == size and len(variance["actual_sigmas"]) == size, "variance account lengths")
    durations = [number(x, 0.0001, 5, "duration") for x in variance["durations"]]
    weights = [number(x, 0, 1e6, "discounted cash gamma") for x in variance["discounted_cash_gammas"]]
    actual = [number(x, 0, 3, "actual sigma") for x in variance["actual_sigmas"]]
    model_sigma = number(variance["model_sigma"], 0, 3, "model sigma")
    contributions = [dt*w*(model_sigma**2-a*a) for dt, w, a in zip(durations, weights, actual)]
    variance_result = {"contributions": contributions, "total_discounted_error": sum(contributions),
                       "time_average_actual_variance": sum(dt*a*a for dt, a in zip(durations, actual))/sum(durations),
                       "scope": "Exact accounting for supplied piecewise constant weights; not a generated diffusion or a discrete realized-variance hedge identity."}
    result = {"case": "Oriole authored risk cases", "base": values, "portfolio": portfolio,
              "shock": shocks, "implied_volatility": inverse, "smile": surface,
              "hedge": hedge(p, data["hedge"]), "variance_account": variance_result}
    json.dumps(result, allow_nan=False)
    return result


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError("nonfinite JSON token: "+value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(), object_pairs_hook=strict_object, parse_constant=bad_constant)
        text = json.dumps(run(data), indent=2, allow_nan=False)+"\n"
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
