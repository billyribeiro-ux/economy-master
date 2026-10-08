#!/usr/bin/env python3
"""Finite synthetic consumption/investment lab; exact rational ledgers, stdlib only."""
import argparse
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(record, key, *, minimum=None, strictly_positive=False):
    value = record.get(key)
    require(type(value) in (int, float, Decimal), key + " must be numeric, not bool or text")
    decimal = Decimal(str(value))
    require(decimal.is_finite(), key + " must be finite")
    require(len(decimal.as_tuple().digits) <= 30 and abs(decimal.as_tuple().exponent) <= 100,
            key + " exceeds the lab's decimal precision/exponent bounds")
    require(abs(decimal) <= 1000000, key + " exceeds the lab's magnitude bound")
    value = Fraction(decimal)
    if minimum is not None:
        require(value >= minimum, key + " is below its permitted minimum")
    if strictly_positive:
        require(value > 0, key + " must be positive")
    return value


def household(record):
    x0 = number(record, "x0", strictly_positive=True)
    y1 = number(record, "y1", minimum=0)
    gross = number(record, "R", strictly_positive=True)
    beta = number(record, "beta", strictly_positive=True)
    limit = number(record, "B", minimum=0)
    wealth = x0 + y1/gross
    unrestricted = (beta*x0-y1/gross)/(1+beta)
    saving = max(-limit, unrestricted)
    c0, c1 = x0-saving, y1+gross*saving
    require(c0 > 0 and c1 > 0, "positive log consumption feasibility")
    multiplier = 1/c0-beta*gross/c1
    require(multiplier >= 0 and multiplier*(saving+limit) == 0, "household KKT certificate")
    require(c0+c1/gross == wealth, "present-value resource reconciliation")
    return {"saving": saving, "c0": c0, "c1": c1, "wealth": wealth,
            "unrestricted_saving": unrestricted, "credit_at_bound": saving == -limit,
            "credit_multiplier": multiplier}


def firm(record):
    k0 = number(record, "K0", minimum=0)
    delta = number(record, "delta", minimum=0)
    require(delta <= 1, "delta must not exceed one")
    gross = number(record, "R", strictly_positive=True)
    p0 = number(record, "p0", strictly_positive=True)
    p1 = number(record, "p1", minimum=0)
    phi = number(record, "phi", minimum=0)
    alpha = number(record, "alpha")
    gamma = number(record, "gamma", strictly_positive=True)
    cap = number(record, "Ibar", strictly_positive=True)
    inherited = (1-delta)*k0
    unrestricted = (alpha-gamma*inherited+p1*(1-delta)-gross*p0)/(gamma+gross*phi)
    investment = min(cap, max(Fraction(0), unrestricted))
    capital = inherited+investment
    equipment = p0*investment
    installation = phi*investment*investment/2
    operating = alpha*capital-gamma*capital*capital/2
    salvage = p1*(1-delta)*capital
    value = -equipment-installation+(operating+salvage)/gross
    baseline = (alpha*inherited-gamma*inherited*inherited/2+p1*(1-delta)*inherited)/gross
    slope = -p0-phi*investment+(alpha-gamma*capital+p1*(1-delta))/gross
    require((investment == 0 and slope <= 0) or
            (investment == cap and slope >= 0) or
            (0 < investment < cap and slope == 0), "firm boundary derivative certificate")
    return {"investment": investment, "unrestricted_investment": unrestricted,
            "K1": capital, "date0_equipment": equipment,
            "date0_installation": installation, "date1_operating": operating,
            "date1_salvage": salvage, "present_value": value,
            "present_value_without_installation": baseline, "incremental_present_value": value-baseline,
            "date1_user_cost": gross*p0-p1*(1-delta), "slope_at_choice": slope}


def encode(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    return value


def analyze(payload):
    require(isinstance(payload, dict), "top level must be an object")
    require(type(payload.get("version")) is int and payload["version"] == 1, "version must be integer one")
    require(payload.get("synthetic") is True, "synthetic flag must be true")
    result = {"status": "computed", "synthetic": True, "number_format": "exact rational strings"}
    for group, solver in (("households", household), ("firms", firm)):
        records = payload.get(group)
        require(isinstance(records, list) and 1 <= len(records) <= 50, group + " must contain 1 to 50 cases")
        names = set()
        output = {}
        for record in records:
            require(isinstance(record, dict), "each case must be an object")
            name = record.get("name")
            require(isinstance(name, str) and 0 < len(name) <= 80, "case name must be short nonempty text")
            require(name not in names, "case names must be unique within each group")
            names.add(name)
            output[name] = solver(record)
        result[group] = output
    return encode(result)


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def load(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 100000, "input exceeds the lab's 100 KB bound")
    return json.loads(raw, parse_float=Decimal, parse_constant=reject_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path,
                        default=Path(__file__).resolve().with_name("v06-c04-inputs.json"))
    args = parser.parse_args()
    try:
        result = analyze(load(args.input))
    except (OSError, ValueError, TypeError, ArithmeticError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
