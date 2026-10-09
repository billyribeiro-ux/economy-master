"""Original finite Black–Scholes teaching lab. Standard library; no simulation.

run(data) is quiet, validates the complete input, and returns JSON-safe numbers.
This program illustrates stated formulae; the manuscript proves their conditions.
Amounts are currency units per option/share; times are years. Drift/rate/yield
are annual decimal rates, volatility is per square-root year. physical_drift
is the ex-dividend price drift, not the total expected return. theta_call/put
mean calendar-time derivatives with fixed maturity. No expiry Greek is reported.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,8})?\Z")
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
CASE_KEYS = {"id", "spot", "strike", "rate", "dividend_yield", "volatility", "maturity", "physical_drift"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == expected, label + ": exact keys required")


def number(value, lo, hi, label):
    require(type(value) in (int, float, str), label + ": finite decimal required; bool is invalid")
    raw = str(value)
    require(DECIMAL.fullmatch(raw) is not None, label + ": use ordinary decimals with at most 8 places")
    ans = Fraction(raw)
    require(Fraction(str(lo)) <= ans <= Fraction(str(hi)), label + ": outside bounded lab domain")
    return ans


def vector(value, lo, hi, label, minimum=2, maximum=20):
    require(isinstance(value, list) and minimum <= len(value) <= maximum, label + ": invalid list length")
    return [number(x, lo, hi, label) for x in value]


def cdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def price(s, k, r, d, v, tau):
    """Internal numerical evaluator; run() supplies the validated domain."""
    a, b = s * math.exp(-d * tau), k * math.exp(-r * tau)
    common = {"prepaid_stock": a, "discounted_strike": b,
              "call_lower_bound": max(a - b, 0.0), "put_lower_bound": max(b - a, 0.0),
              "call_upper_bound": a, "put_upper_bound": b}
    if tau == 0.0:
        return dict(common, branch="expiry", call=max(s-k, 0.0), put=max(k-s, 0.0),
                    d1=None, d2=None, delta_call=None, delta_put=None, gamma=None,
                    theta_call=None, theta_put=None, call_bank=None, put_bank=None,
                    probability_Q_itm=float(s > k), pde_call_residual=None, pde_put_residual=None)
    if s == 0.0:
        dc, dp = 0.0, -math.exp(-d * tau)
        return dict(common, branch="absorbing_zero", call=0.0, put=b,
                    d1=None, d2=None, delta_call=dc, delta_put=dp, gamma=0.0,
                    theta_call=0.0, theta_put=r*b, call_bank=0.0, put_bank=b,
                    probability_Q_itm=0.0, pde_call_residual=0.0, pde_put_residual=0.0)
    if v == 0.0:
        call, put = max(a-b, 0.0), max(b-a, 0.0)
        if a == b:
            dc = dp = gamma = tc = tp = bc = bp = None
        else:
            dc = math.exp(-d*tau) * float(a > b)
            dp = dc - math.exp(-d*tau)
            gamma = 0.0
            tc = d*a-r*b if a > b else 0.0
            tp = r*b-d*a if a < b else 0.0
            bc, bp = call-dc*s, put-dp*s
        return dict(common, branch="deterministic", call=call, put=put,
                    d1=None, d2=None, delta_call=dc, delta_put=dp, gamma=gamma,
                    theta_call=tc, theta_put=tp, call_bank=bc, put_bank=bp,
                    probability_Q_itm=float(a > b), pde_call_residual=None, pde_put_residual=None)
    width = v * math.sqrt(tau)
    z1 = (math.log(s/k) + (r-d+0.5*v*v)*tau) / width
    z2 = z1-width
    # Evaluate the out-of-the-money price directly, then use exact-model parity.
    # Only a negative floating roundoff of scale <=1e-12 is clipped.
    if a <= b:
        raw = a*cdf(z1)-b*cdf(z2)
        require(raw >= -1e-12 * (1+a+b), "call numerical cancellation exceeds tolerance")
        call = max(0.0, raw)
        put = call-a+b
    else:
        raw = b*cdf(-z2)-a*cdf(-z1)
        require(raw >= -1e-12 * (1+a+b), "put numerical cancellation exceeds tolerance")
        put = max(0.0, raw)
        call = put+a-b
    dc = math.exp(-d*tau)*cdf(z1)
    dp = -math.exp(-d*tau)*cdf(-z1)
    gamma = math.exp(-d*tau)*pdf(z1)/(s*width)
    tc = -a*pdf(z1)*v/(2*math.sqrt(tau)) + d*a*cdf(z1)-r*b*cdf(z2)
    tp = -a*pdf(z1)*v/(2*math.sqrt(tau)) - d*a*cdf(-z1)+r*b*cdf(-z2)
    return dict(common, branch="positive_diffusion", call=call, put=put,
                d1=z1, d2=z2, delta_call=dc, delta_put=dp, gamma=gamma,
                theta_call=tc, theta_put=tp, call_bank=call-dc*s, put_bank=put-dp*s,
                probability_Q_itm=cdf(z2),
                pde_call_residual=tc+(r-d)*s*dc+0.5*v*v*s*s*gamma-r*call,
                pde_put_residual=tp+(r-d)*s*dp+0.5*v*v*s*s*gamma-r*put)


def validate(data):
    keys(data, {"schema", "cases", "tilt", "hedge"}, "input")
    require(data["schema"] == "v10-c08-lab-1", "unknown schema")
    cases = data["cases"]
    require(isinstance(cases, list) and 1 <= len(cases) <= 8, "1 to 8 cases required")
    parsed = {}
    bounds = {"spot": (0,1000), "strike": (1,1000), "rate": (-0.1,0.3),
              "dividend_yield": (0,0.2), "volatility": (0,0.8),
              "maturity": (0,5), "physical_drift": (-0.3,0.4)}
    for c in cases:
        keys(c, CASE_KEYS, "case")
        ident = c["id"]
        require(isinstance(ident,str) and IDENTIFIER.fullmatch(ident) is not None, "invalid case id")
        require(ident not in parsed, "duplicate case id")
        q = {k:number(c[k],*lim,k) for k,lim in bounds.items()}
        require(q["spot"] == 0 or q["spot"] >= 1, "positive spot must be at least 1")
        require(q["volatility"] == 0 or q["volatility"] >= Fraction(1,20), "positive volatility must be at least .05")
        require(q["maturity"] == 0 or q["maturity"] >= Fraction(1,50), "positive maturity must be at least .02")
        if q["volatility"] == 0 and q["spot"] > 0 and q["maturity"] > 0:
            require(q["physical_drift"]+q["dividend_yield"] == q["rate"],
                    "positive deterministic stock must have mu+dividend_yield=rate exactly")
        parsed[ident] = q
    for section in ("tilt", "hedge"):
        keys(data[section], {"case_id", "intervals", "brownian_P_increments"} if section=="tilt"
             else {"case_id", "dates", "prices"}, section)
        ident = data[section]["case_id"]
        require(isinstance(ident,str) and ident in parsed, section+": unknown case")
        q = parsed[ident]
        require(q["spot"] > 0 and q["volatility"] > 0 and q["maturity"] > 0,
                section+": positive diffusion, spot and horizon required")
    t = data["tilt"]
    intervals = vector(t["intervals"], .02, 5, "tilt intervals", maximum=8)
    increments = vector(t["brownian_P_increments"], -5, 5, "Brownian increments", maximum=8)
    require(len(intervals)==len(increments), "tilt vectors differ in length")
    require(sum(intervals,Fraction(0))==parsed[t["case_id"]]["maturity"], "tilt intervals must span maturity")
    h = data["hedge"]
    dates = vector(h["dates"],0,5,"hedge dates")
    spots = vector(h["prices"],1,1000,"hedge prices")
    require(len(dates)==len(spots), "hedge vectors differ in length")
    require(dates[0]==0 and all(x<y for x,y in zip(dates,dates[1:])), "hedge dates must start at zero and increase")
    require(all(y-x >= Fraction(1,50) for x,y in zip(dates,dates[1:])), "hedge steps must be at least .02")
    require(dates[-1]==parsed[h["case_id"]]["maturity"], "hedge must end at maturity")
    require(spots[0]==parsed[h["case_id"]]["spot"], "hedge initial spot differs from case")
    return parsed, intervals, increments, dates, spots


def run(data):
    parsed, intervals, increments, dates, spots = validate(data)
    outputs = {}
    for ident, q in parsed.items():
        s,k,r,d,v,t,mu = (float(q[n]) for n in ("spot","strike","rate","dividend_yield","volatility","maturity","physical_drift"))
        ans = price(s,k,r,d,v,t)
        scale = 1.0 + ans["prepaid_stock"] + ans["discounted_strike"]
        require(ans["call_lower_bound"]-1e-12*scale <= ans["call"] <= ans["call_upper_bound"]+1e-12*scale,
                "numerical call price violates model bounds")
        require(ans["put_lower_bound"]-1e-12*scale <= ans["put"] <= ans["put_upper_bound"]+1e-12*scale,
                "numerical put price violates model bounds")
        parity = ans["call"]-ans["put"]-ans["prepaid_stock"]+ans["discounted_strike"]
        require(abs(parity) <= 1e-12*scale, "numerical put-call parity failed")
        if t==0 or s==0 or v==0:
            pp = ans["probability_Q_itm"]
        else:
            pp = cdf((math.log(s/k)+(mu-0.5*v*v)*t)/(v*math.sqrt(t)))
        ans.update(put_call_parity_residual=parity, probability_P_itm=pp, expected_terminal_stock_P=s*math.exp(mu*t),
                   expected_terminal_stock_Q=s*math.exp((r-d)*t),
                   expected_discounted_ex_price_Q=s*math.exp(-d*t),
                   expected_discounted_dividends_Q=s*(-math.expm1(-d*t)),
                   expected_discounted_total_gain_Q=s,
                   market_price_of_risk=(mu+d-r)/v if v>0 and t>0 and s>0 else None)
        outputs[ident] = ans
    tc = parsed[data["tilt"]["case_id"]]
    lam = float((tc["physical_drift"]+tc["dividend_yield"]-tc["rate"])/tc["volatility"])
    t = float(tc["maturity"])
    logz = -lam*float(sum(increments,Fraction(0)))-0.5*lam*lam*t
    qincr = [float(w)+lam*float(h) for h,w in zip(intervals,increments)]
    logp = sum(-0.5*math.log(2*math.pi*float(h))-float(w)**2/(2*float(h)) for h,w in zip(intervals,increments))
    logq = sum(-0.5*math.log(2*math.pi*float(h))-(float(w)+lam*float(h))**2/(2*float(h)) for h,w in zip(intervals,increments))
    density = math.exp(logz)
    tilt = {"case_id":data["tilt"]["case_id"], "lambda":lam, "log_density_Z":logz,
            "density_Z":density if density > 0 else None, "density_Z_underflow":density == 0,
            "Brownian_Q_increments_on_same_path":qincr,
            "mean_WP_terminal_under_Q":-lam*t, "variance_WP_terminal_under_Q":t,
            "log_joint_P_density":logp,"log_joint_Q_density_of_WP":logq,
            "log_density_factorization_residual":logq-logp-logz,
            "E_P_Z_analytic":1.0,"log_E_P_Z_squared_analytic":lam*lam*t}
    hc = parsed[data["hedge"]["case_id"]]
    k,r,d,v,t = (float(hc[n]) for n in ("strike","rate","dividend_yield","volatility","maturity"))
    first = outputs[data["hedge"]["case_id"]]
    shares, bank = first["delta_call"], first["call_bank"]
    rows = [{"time":0.0,"spot":float(spots[0]),"shares_after":shares,"bank_after":bank,
             "wealth":first["call"],"call_mark":first["call"],"hedge_error":0.0,
             "external_contribution":0.0}]
    for j in range(1,len(dates)):
        dt = float(dates[j]-dates[j-1])
        s = float(spots[j])
        incoming = shares*math.exp(d*dt)  # All dividends buy more shares immediately.
        grown_bank = bank*math.exp(r*dt)
        wealth = incoming*s+grown_bank
        remaining = float(hc["maturity"]-dates[j])
        mark = price(s,k,r,d,v,remaining)
        target = 0.0 if remaining==0 else mark["delta_call"]
        expenditure = (target-incoming)*s
        bank = grown_bank-expenditure
        shares = target
        rows.append({"time":float(dates[j]),"spot":s,"incoming_shares":incoming,
                     "bank_before_trade":grown_bank,"rebalance_expenditure":expenditure,
                     "shares_after":shares,"bank_after":bank,"wealth":wealth,
                     "call_mark":mark["call"],"hedge_error":wealth-mark["call"],
                     "external_contribution":0.0})
    result = {"schema":"v10-c08-output-1", "cases":outputs, "tilt":tilt,
              "hedge":{"case_id":data["hedge"]["case_id"],
                       "contract":"European call; all cash dividends reinvested in stock; signed bank at the same rate; no fees",
                       "ledger":rows,"terminal_error":rows[-1]["hedge_error"]}}
    # A strict serialization check also catches unexpected nonfinite output.
    json.dumps(result,allow_nan=False)
    return result


def unique_object(pairs):
    obj = {}
    for key,value in pairs:
        require(key not in obj,"duplicate JSON key: "+key)
        obj[key] = value
    return obj


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: "+value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=HERE/"v10-c08-inputs.json")
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    result = json.dumps(run(data),indent=2,sort_keys=True,allow_nan=False)+"\n"
    if args.output:
        args.output.write_text(result,encoding="utf-8")
    else:
        print(result,end="")


if __name__ == "__main__":
    main()
