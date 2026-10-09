#!/usr/bin/env python3
"""Exact finite-state incomplete-market laboratory; standard library only.

run(data) is quiet, nonmutating and performs complete validation. Stock trades
only at 0 and T; deterministic bank borrowing/reinvestment is available on all
listed dates. Interior path marks determine contracts, not tradable node quotes.
All rational outputs are canonical strings. See the standalone README.
"""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import re

SCHEMA = "v10-c11-input-1"


def _keys(x, keys, where):
    if type(x) is not dict or set(x) != set(keys):
        raise ValueError(where + ": exact keys required: " + ", ".join(keys))


def _seq(x, lo, hi, where):
    if type(x) is not list or not lo <= len(x) <= hi:
        raise ValueError(where + ": invalid list length/type")
    return x


def _num(x, lo, hi, where):
    if type(x) is int:
        if abs(x) > 10**9:
            raise ValueError(where + ": integer too large")
        q = Fraction(x)
    elif type(x) is float:
        if not math.isfinite(x) or abs(x) > 10**9:
            raise ValueError(where + ": finite bounded number required")
        q = Fraction(str(x))
    elif type(x) is str and len(x) <= 24 and re.fullmatch(r"-?(0|[1-9][0-9]{0,9})(/[1-9][0-9]{0,9})?", x):
        q = Fraction(x)
    else:
        raise ValueError(where + ": integer, finite decimal or rational string required")
    if abs(q.numerator) > 10**9 or q.denominator > 10**9 or not lo <= q <= hi:
        raise ValueError(where + ": rational size/domain exceeded")
    return q


def _integer(x, lo, hi, where):
    if type(x) is not int or not lo <= x <= hi:
        raise ValueError(where + ": bounded integer required")
    return x


def _name(x, where):
    if type(x) is not str or re.fullmatch(r"[a-z][a-z0-9_]{0,39}", x) is None:
        raise ValueError(where + ": invalid identifier")
    return x


def _indices(x, n, where):
    _seq(x, 1, n - 1, where)
    out = [_integer(v, 1, n - 1, where) for v in x]
    if out != sorted(set(out)):
        raise ValueError(where + ": indices must be strictly increasing")
    return out


def _validate(data):
    _keys(data, ("schema", "market", "contracts", "measures", "jump_cases"), "input")
    if data["schema"] != SCHEMA:
        raise ValueError("unsupported schema")
    m = data["market"]
    _keys(m, ("spot", "times", "discounts", "states"), "market")
    spot = _num(m["spot"], 0, 10000, "spot")
    times = [_num(x, 0, 10, "time") for x in _seq(m["times"], 2, 9, "times")]
    if times[0] != 0 or any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("times start at zero and strictly increase")
    n = len(times)
    discounts = [_num(x, Fraction(1, 10), 10, "discount") for x in _seq(m["discounts"], n, n, "discounts")]
    if discounts[0] != 1:
        raise ValueError("discount at zero must be one")
    states = []
    for row in _seq(m["states"], 2, 8, "states"):
        _keys(row, ("id", "stock_path", "default_index", "recovery", "protection_fraction"), "state")
        sid = _name(row["id"], "state id")
        path = [_num(x, 0, 10000, "stock mark") for x in _seq(row["stock_path"], n, n, "stock path")]
        if path[0] != spot:
            raise ValueError("all paths must start at spot")
        default = row["default_index"]
        if default is not None:
            default = _integer(default, 1, n - 1, "default index")
        recovery = _num(row["recovery"], 0, 1, "recovery")
        fraction = _num(row["protection_fraction"], 0, 1, "protection fraction")
        if default is None and (recovery != 1 or fraction != 1):
            raise ValueError("no-default states require neutral recovery/fraction placeholders")
        states.append((sid, path, default, recovery, fraction))
    if len({r[0] for r in states}) != len(states):
        raise ValueError("duplicate state id")
    terminal = [r[1][-1] for r in states]
    forward = spot / discounts[-1]
    if not min(terminal) < forward < max(terminal):
        raise ValueError("forward must be strictly inside terminal stock range")
    c = data["contracts"]
    _keys(c, ("strike", "barrier", "monitor_indices", "average_indices", "average_strike", "credit"), "contracts")
    strike = _num(c["strike"], 0, 10000, "strike")
    barrier = _num(c["barrier"], Fraction(1, 1000000), 10000, "barrier")
    monitors = _indices(c["monitor_indices"], n, "monitor indices")
    averages = _indices(c["average_indices"], n, "average indices")
    average_strike = _num(c["average_strike"], 0, 10000, "average strike")
    cr = c["credit"]
    _keys(cr, ("premium_indices", "notional", "premium_rate", "settlement_delay"), "credit")
    premiums = _indices(cr["premium_indices"], n, "premium indices")
    if premiums[-1] != n - 1:
        raise ValueError("last premium must be at maturity")
    notional = _num(cr["notional"], Fraction(1, 1000000), 1000000, "notional")
    rate = _num(cr["premium_rate"], 0, 1, "premium rate")
    delay = _integer(cr["settlement_delay"], 0, n - 2, "settlement delay")
    if any(r[2] is not None and r[2] + delay >= n for r in states):
        raise ValueError("default settlement must be on listed horizon")
    measures = []
    for row in _seq(data["measures"], 1, 8, "measures"):
        _keys(row, ("id", "probabilities"), "measure")
        mid = _name(row["id"], "measure id")
        probs = [_num(x, 0, 1, "probability") for x in _seq(row["probabilities"], len(states), len(states), "probabilities")]
        if any(x <= 0 for x in probs) or sum(probs) != 1 or sum(p*s for p,s in zip(probs,terminal)) != forward:
            raise ValueError("pricing probabilities must be strictly positive, normalized and stock-calibrated")
        measures.append((mid, probs))
    if len({r[0] for r in measures}) != len(measures):
        raise ValueError("duplicate measure id")
    jumps = []
    for row in _seq(data["jump_cases"], 1, 8, "jump cases"):
        _keys(row, ("id", "spot", "jump", "scale"), "jump case")
        jid = _name(row["id"], "jump id")
        s = _num(row["spot"], 0, 10000, "jump spot")
        j = _num(row["jump"], -10000, 10000, "jump amount")
        scale = _num(row["scale"], Fraction(1, 1000000), 10000, "scale")
        if not 0 <= s+j <= 10000:
            raise ValueError("post-jump spot outside range")
        jumps.append((jid,s,j,scale))
    if len({r[0] for r in jumps}) != len(jumps):
        raise ValueError("duplicate jump id")
    return spot,times,discounts,states,terminal,forward,strike,barrier,monitors,averages,average_strike,premiums,notional,rate,delay,measures,jumps


def _vertices(stock, forward):
    n = len(stock)
    found = set()
    for i in range(n):
        if stock[i] == forward:
            found.add(tuple(Fraction(int(k == i)) for k in range(n)))
        for j in range(i+1,n):
            if stock[i] == stock[j]:
                continue
            p = (stock[j]-forward)/(stock[j]-stock[i])
            if 0 <= p <= 1:
                v = [Fraction(0)]*n
                v[i],v[j] = p,1-p
                found.add(tuple(v))
    return sorted(found)


def _bounds(stock, payoff, spot, discount, vertices):
    candidates = []
    for i in range(len(stock)):
        for j in range(i+1,len(stock)):
            if stock[i] == stock[j]:
                continue
            delta = (payoff[j]-payoff[i])/(stock[j]-stock[i])
            intercept = payoff[i]-delta*stock[i]
            values = [intercept+delta*s for s in stock]
            cost = discount*intercept+delta*spot
            candidates.append((cost,delta,intercept,values))
    lower = max((x for x in candidates if all(v <= h for v,h in zip(x[3],payoff))),key=lambda x:(x[0],x[1],x[2]))
    upper = min((x for x in candidates if all(v >= h for v,h in zip(x[3],payoff))),key=lambda x:(x[0],x[1],x[2]))
    prices = [discount*sum(p*h for p,h in zip(v,payoff)) for v in vertices]
    # These explicit checks are internal consistency guards, not the independent oracle.
    if lower[0] != min(prices) or upper[0] != max(prices):
        raise ArithmeticError("finite primal/dual disagreement")
    def hedge(x):
        return {"cost":x[0],"stock_units":x[1],"terminal_cash":x[2],"initial_cash":discount*x[2],"terminal_values":x[3]}
    return {"terminal_payoff":payoff,"lower":lower[0],"upper":upper[0],"replicable":lower[0]==upper[0],
            "endpoints_open":lower[0]!=upper[0],"subhedge":hedge(lower),"superhedge":hedge(upper),
            "closed_vertex_prices":prices}


def _encode(x):
    if isinstance(x,Fraction):
        return str(x)
    if isinstance(x,dict):
        return {k:_encode(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):
        return [_encode(v) for v in x]
    return x


def run(data):
    """Validate and evaluate one original exact finite-state market, without I/O."""
    (spot,times,discounts,states,stock,forward,strike,barrier,monitors,averages,
     average_strike,premiums,notional,rate,delay,measures,jumps) = _validate(data)
    vertices = _vertices(stock,forward)
    baseline = [sum(v[i] for v in vertices)/len(vertices) for i in range(len(states))]
    claims = {"call":[],"up_out":[],"terminal_only_up_out":[],"asian":[],"credit_net":[],"stock":[]}
    credit_rows = []
    for sid,path,default,recovery,fraction in states:
        call = max(path[-1]-strike,Fraction(0))
        claims["call"].append(call)
        claims["up_out"].append(call if all(path[k] < barrier for k in monitors) else Fraction(0))
        claims["terminal_only_up_out"].append(call if path[-1] < barrier else Fraction(0))
        claims["asian"].append(max(sum(path[k] for k in averages)/len(averages)-average_strike,Fraction(0)))
        claims["stock"].append(path[-1])
        annuity = Fraction(0)
        payments = []
        previous = 0
        for k in premiums:
            if default is None or default > k:
                accrual = times[k]-times[previous]
                annuity += discounts[k]*accrual
                payments.append({"index":k,"kind":"scheduled_premium","cash":-notional*rate*accrual})
            previous = k
        if default is not None:
            previous = max([0]+[k for k in premiums if k < default])
            accrual = times[default]-times[previous]
            annuity += discounts[default]*accrual
            payments.append({"index":default,"kind":"accrued_premium","cash":-notional*rate*accrual})
            settlement = default+delay
            protection = notional*(1-recovery)*fraction
            payments.append({"index":settlement,"kind":"protection","cash":protection})
            protection_pv = discounts[settlement]*protection
        else:
            settlement = None
            protection_pv = Fraction(0)
        net_pv = protection_pv-notional*rate*annuity
        if annuity <= 0:
            raise ArithmeticError("positive horizon/accrual must give positive annuity")
        payments.sort(key=lambda x:(x["index"],x["kind"]))
        claims["credit_net"].append(net_pv/discounts[-1])
        credit_rows.append({"state":sid,"default_index":default,"settlement_index":settlement,
                            "unit_annuity_pv":annuity,"protection_pv":protection_pv,
                            "premium_pv":notional*rate*annuity,"net_pv":net_pv,"payments":payments})
    bounded = {name:_bounds(stock,h,spot,discounts[-1],vertices) for name,h in claims.items()}
    quotes=[]
    for mid,p in measures:
        protection=sum(p[i]*row["protection_pv"] for i,row in enumerate(credit_rows))
        annuity=sum(p[i]*row["unit_annuity_pv"] for i,row in enumerate(credit_rows))
        quotes.append({"id":mid,"probabilities":p,"state_prices":[discounts[-1]*q for q in p],
                       "prices":{name:discounts[-1]*sum(q*h for q,h in zip(p,payoff)) for name,payoff in claims.items()},
                       "credit":{"protection_pv":protection,"unit_annuity_pv":annuity,
                                  "premium_pv":notional*rate*annuity,"fair_spread":protection/(notional*annuity)}})
    spread_vertices=[]
    for p in vertices:
        protection=sum(p[i]*row["protection_pv"] for i,row in enumerate(credit_rows))
        annuity=sum(p[i]*row["unit_annuity_pv"] for i,row in enumerate(credit_rows))
        spread_vertices.append(protection/(notional*annuity))
    low,high=min(spread_vertices),max(spread_vertices)
    jump_rows=[]
    for jid,s,j,scale in jumps:
        before=s*s/scale
        after=(s+j)*(s+j)/scale
        delta=2*s/scale
        jump_rows.append({"id":jid,"before":before,"after":after,"delta_before":delta,
                          "stock_hedge_gain":delta*j,"claim_change":after-before,
                          "claim_minus_hedge":after-before-delta*j,"identity_jump_squared_over_scale":j*j/scale})
    return _encode({"schema":"v10-c11-output-1","state_order":[r[0] for r in states],"forward":forward,
                    "closed_pricing_vertices":vertices,"strict_positive_baseline":baseline,
                    "claims":bounded,"quotes":quotes,"credit_state_ledgers":credit_rows,
                    "fair_spread_bounds":{"lower":low,"upper":high,"endpoints_open":low!=high,"closed_vertex_spreads":spread_vertices},
                    "jump_cases":jump_rows})


def _object(pairs):
    out={}
    for key,value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key: "+key)
        out[key]=value
    return out


def _constant(value):
    raise ValueError("nonstandard JSON constant: "+value)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=Path(__file__).with_name("v10-c11-inputs.json"))
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    try:
        data=json.loads(args.input.read_text(encoding="utf-8"),object_pairs_hook=_object,parse_constant=_constant)
        result=run(data)
        encoded=json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n"
    except (ValueError,TypeError,OSError,ArithmeticError,OverflowError) as exc:
        parser.exit(2,"invalid input: "+str(exc)+"\n")
    if args.output is None:
        print(encoded,end="")
    else:
        args.output.write_text(encoded,encoding="utf-8")


if __name__ == "__main__":
    main()
