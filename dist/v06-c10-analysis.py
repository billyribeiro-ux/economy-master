#!/usr/bin/env python3
"""Exact synthetic tariff and conditional-export lab; Python standard library only."""
from fractions import Fraction
import json
from pathlib import Path
import re
import sys

UNITS = {
    "quantity": "physical units in one period",
    "price": "numeraire dollars per physical unit",
    "welfare": "numeraire dollars in one period",
    "iceberg": "produced units per delivered unit",
}


def rational(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(label + " must be an integer or rational string")
    if isinstance(value, str) and (len(value) > 32 or not re.fullmatch(r"-?\d+(?:/\d+)?", value)):
        raise ValueError(label + " must use integer or numerator/denominator syntax")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(label + " has an invalid rational value") from exc
    if abs(result.numerator) > 10**9 or result.denominator > 10**6 or abs(result) > 10**6:
        raise ValueError(label + " exceeds this finite lab's magnitude bounds")
    return result


def fields(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError(label + " has missing or unknown fields")


def validate(data):
    fields(data, ("schema", "provenance", "units", "tariffs", "firms"), "input")
    if data["schema"] != "v06-c10-synthetic-v1" or data["provenance"] != "original synthetic teaching inputs":
        raise ValueError("unsupported schema or provenance")
    if data["units"] != UNITS:
        raise ValueError("unsupported units; use the exact documented numeraire/period contract")
    for kind in ("tariffs", "firms"):
        rows = data[kind]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
            raise ValueError(kind + " must contain 1 to 100 cases")
        names = set()
        for row in rows:
            required = ("name", "market", "t") if kind == "tariffs" else ("name", "A", "b", "F", "c", "tau")
            fields(row, required, kind + " case")
            name = row["name"]
            if not isinstance(name, str) or not name.strip() or len(name) > 80 or name in names:
                raise ValueError(kind + " case names must be nonempty, short and unique")
            names.add(name)
            if kind == "tariffs":
                if row["market"] not in ("small", "large"):
                    raise ValueError("unknown tariff market")
                if rational(row["t"], "t") < 0:
                    raise ValueError("t must be nonnegative")
            else:
                for key in ("A", "b", "F", "c"):
                    if rational(row[key], key) <= 0:
                        raise ValueError(key + " must be strictly positive")
                if rational(row["tau"], "tau") < 1:
                    raise ValueError("tau must be at least one")


def tariff(market, t):
    """Fixed chapter demand/supply schedules; t is a nonnegative Fraction."""
    if market not in ("small", "large") or t < 0:
        raise ValueError("unsupported tariff regime or negative tariff")
    if market == "small":
        pd = min(Fraction(35), 20 + t)
        pf = Fraction(20)
    else:
        pd = min(Fraction(35), 20 + Fraction(3, 5) * t)
        pf = 10 + max(Fraction(0), 140 - 4 * pd) / 6
    demand, supply = 120 - 2 * pd, 2 * pd - 20
    imports = demand - supply
    cs, ps, revenue = (60 - pd)**2, (pd - 10)**2, t * imports
    benefit, home_cost = 60 * demand - demand**2 / 4, 10 * supply + supply**2 / 4
    home = cs + ps + revenue
    out = {
        "regime": "imports" if imports > 0 else "prohibitive",
        "t": t, "domestic_price": pd, "foreign_offer_price": pf,
        "border_transaction_price": pf if imports > 0 else None,
        "consumption": demand, "production": supply, "imports": imports,
        "consumer_surplus": cs, "producer_surplus": ps, "revenue": revenue,
        "foreign_payment": pf * imports,
        "home_welfare": home, "home_change": home - 1700,
        "home_resource_ledger": benefit - home_cost - pf * imports,
    }
    if market == "large":
        foreign = imports**2 / 12
        out.update(foreign_surplus=foreign, foreign_change=foreign - 300,
                   world_change=home - 1700 + foreign - 300)
    return out


def exporter(A, b, F, c, tau):
    """Conditional destination choice; F is avoidable; every optimum is retained."""
    if min(A, b, F, c) <= 0 or tau < 1:
        raise ValueError("invalid conditional export parameters")
    margin = A - tau * c
    candidate = max(Fraction(0), margin / (2 * b))
    contribution = max(Fraction(0), margin) ** 2 / (4 * b)
    net = contribution - F
    quantities = [candidate] if net > 0 else [Fraction(0)]
    if net == 0:
        quantities.append(candidate)
    return {
        "delivered_marginal_cost": tau * c,
        "positive_branch_candidate": candidate,
        "maximum_contribution": contribution,
        "maximum_net_profit": max(Fraction(0), net),
        "choice_status": "export" if net > 0 else ("indifferent" if net == 0 else "stay_out"),
        "optimal_choices": [{
            "delivered": q, "produced": tau * q,
            "price": A - b * q if q > 0 else None,
        } for q in quantities],
    }


def encode(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def analyze(data):
    validate(data)
    tariffs = [{"name": row["name"], "market": row["market"],
                **tariff(row["market"], rational(row["t"], "t"))} for row in data["tariffs"]]
    firms = [{"name": row["name"], **exporter(*(rational(row[k], k) for k in ("A", "b", "F", "c", "tau")))}
             for row in data["firms"]]
    return encode({"schema": data["schema"], "units": UNITS, "tariffs": tariffs, "firms": firms})


def main():
    if len(sys.argv) > 2:
        raise ValueError("usage: python3 v06-c10-analysis.py [input.json]")
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v06-c10-inputs.json")
    return analyze(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    try:
        print(json.dumps(main(), indent=2, allow_nan=False))
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
