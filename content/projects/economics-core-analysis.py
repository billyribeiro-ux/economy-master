#!/usr/bin/env python3
"""Original synthetic economics-core laboratory; Python standard library only.
All monetary outputs are HC and all fractions are serialized exactly as strings.
The documented fixed model is not an estimator or a forecast.
"""
from copy import deepcopy
from datetime import date
from fractions import Fraction as F
from itertools import combinations
import argparse
import json
from pathlib import Path

UNITS = {"currency": "HC", "energy": "energy units per period", "numeraire": "goods per period at 1 HC each", "exchange": "HC per FU", "pilot": "energy units per community per month"}
MODEL = {"benefit_A": "20", "benefit_B": "12", "cost_coefficient": "1/2", "damage_coefficient": "1/4", "foreign_energy_price": "8", "numeraire_output": "200", "government_consumption": "20", "private_investment": "10", "numeraire_exports": "20", "opening_public_debt": "50", "public_interest": "2", "lump_tax_each": "8", "foreign_secondary_transfer_B": "1", "opening_foreign_assets_FU": "20", "opening_private_foreign_liabilities_FU": "15", "exchange_open": "2", "exchange_close": "11/5", "terminal_endowment_each": "100", "terminal_investment_payoff_A": "10", "terminal_claim_gross_return": "1"}

def fraction(value):
    if not isinstance(value, str):
        raise ValueError("Exact numbers must be rational strings, never bool/float/int")
    try:
        answer = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid rational number") from exc
    return answer

def iso(value):
    if not isinstance(value, str):
        raise ValueError("Date must be an ISO string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError("Date must use YYYY-MM-DD")
    return parsed

def require_keys(obj, keys, label):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ValueError(label + " has missing or unknown fields")

def validate(data):
    require_keys(data, ("schema", "provenance", "units", "model", "policies", "pilot"), "input")
    if data["schema"] != "economics-core-1" or data["provenance"] != "Original synthetic teaching economy and hypothetical release history; no observed country data":
        raise ValueError("Unsupported schema or provenance")
    if data["units"] != UNITS or data["model"] != MODEL:
        raise ValueError("This benchmark supports only the documented fixed unit/model contract")
    policies = data["policies"]
    if not isinstance(policies, list) or not policies:
        raise ValueError("At least one policy is required")
    names = set()
    for p in policies:
        if not isinstance(p, dict) or p.get("kind") not in ("tax", "quota"):
            raise ValueError("Policy kind must be tax or quota")
        require_keys(p, ("id", "kind", "tariff", "carbon") if p["kind"] == "tax" else ("id", "kind", "cap"), "policy")
        if not isinstance(p["id"], str) or not p["id"] or p["id"] in names:
            raise ValueError("Unique nonempty policy ids required")
        names.add(p["id"])
        if p["kind"] == "tax":
            t, tau = fraction(p["tariff"]), fraction(p["carbon"])
            if not 0 <= t <= 2 or not 0 <= tau <= 10:
                raise ValueError("Supported tax domain: tariff [0,2], carbon [0,10]")
        elif not 0 <= fraction(p["cap"]) <= 8:
            raise ValueError("Supported quota domain [0,8]")
    pilot = data["pilot"]
    require_keys(pilot, ("cutoff", "baseline_period", "followup_period", "communities", "treated", "assignment", "assignment_date", "records"), "pilot")
    cutoff = iso(pilot["cutoff"])
    if pilot["assignment_date"] != "2024-05-01":
        raise ValueError("This fixture assigns after April baseline on 2024-05-01")
    if (pilot["baseline_period"], pilot["followup_period"]) != ("2024-04", "2024-05"):
        raise ValueError("This fixture uses April baseline and May followup only")
    if pilot["communities"] != list("ABCDEF") or pilot["assignment"] != "uniform-exactly-3-of-6":
        raise ValueError("Unsupported population or lottery")
    if not isinstance(pilot["treated"], list) or len(pilot["treated"]) != 3 or len(set(pilot["treated"])) != 3 or not set(pilot["treated"]) <= set(pilot["communities"]):
        raise ValueError("Exactly three distinct known treated communities required")
    if not isinstance(pilot["records"], list):
        raise ValueError("Pilot records must be a list")
    seen = set()
    eligible = set()
    for r in pilot["records"]:
        require_keys(r, ("community", "period", "released", "usage"), "release")
        if r["community"] not in pilot["communities"] or r["period"] not in ("2024-04", "2024-05"):
            raise ValueError("Unknown community or period")
        release = iso(r["released"])
        period_end = date(2024, 4, 30) if r["period"] == "2024-04" else date(2024, 5, 31)
        if release <= period_end:
            raise ValueError("Usage is released after its complete measurement month")
        key = (r["community"], r["period"], r["released"])
        if key in seen:
            raise ValueError("Duplicate release key")
        seen.add(key)
        if fraction(r["usage"]) < 0:
            raise ValueError("Usage cannot be negative")
        if release <= cutoff:
            eligible.add(key[:2])
    expected = {(c, p) for c in pilot["communities"] for p in ("2024-04", "2024-05")}
    if eligible != expected:
        raise ValueError("Missing historical-cutoff coverage")
    return data

def policy_result(policy):
    if policy["kind"] == "tax":
        tariff, carbon = fraction(policy["tariff"]), fraction(policy["carbon"])
        price = 8 + tariff
        q = max(price-carbon, F(0))
        shadow = F(0)
    else:
        tariff = carbon = F(0)
        price = F(8)
        q = fraction(policy["cap"])
        shadow = price-q
    x, y = max(20-price, F(0)), max(12-price, F(0))
    demand, imports = x+y, x+y-q
    if imports < 0:
        raise ValueError("Import-price branch infeasible")
    cost, damage = q*q/2, q*q/4
    carbon_revenue, tariff_revenue, permit_revenue = carbon*q, tariff*imports, shadow*q
    revenue = carbon_revenue+tariff_revenue+permit_revenue
    profit = price*q-cost-carbon_revenue-permit_revenue
    csa, csb = x*x/2, y*y/2
    wa, wb = csa+profit, csb+revenue-damage
    welfare = wa+wb
    private_borrowing = 8*imports-25
    household_borrowing = private_borrowing/2
    za = 82+profit+household_borrowing-price*x
    zb = 93+revenue+household_borrowing-price*y
    if min(za, zb) < 0:
        raise ValueError("Household numeraire feasibility fails")
    consumption = za+zb+price*demand
    nx = 20-8*imports
    gdp = 200+price*q-cost+tariff_revenue
    real_gdp = 200+8*q-cost
    gni, gndi = gdp-2, gdp-1
    saving = gndi-consumption-20
    ca = nx-1
    public_new_borrowing = F(6)
    terminal_a = F(175,2)-household_borrowing
    terminal_b = F(155,2)-household_borrowing
    external_asset_acquisition = max(-private_borrowing, F(0))
    external_liability_incurrence = public_new_borrowing+max(private_borrowing,F(0))
    fa = external_asset_acquisition-external_liability_incurrence
    output = dict(id=policy["id"], kind=policy["kind"], price=price, x=x, y=y, domestic_q=q, demand=demand, imports=imports, resource_cost=cost, damage=damage, carbon=carbon, tariff=tariff, permit_shadow=shadow, carbon_revenue=carbon_revenue, tariff_revenue=tariff_revenue, permit_revenue=permit_revenue, revenue=revenue, profit_A=profit, consumer_surplus_A=csa, consumer_surplus_B=csb, sector_welfare_A=wa, sector_welfare_B=wb, sector_welfare=welfare, private_net_borrowing=private_borrowing, household_net_borrowing=household_borrowing, z_A=za, z_B=zb, consumption=consumption, investment=F(10), government_consumption=F(20), net_exports=nx, nominal_gdp=gdp, base_price_gdp=real_gdp, gdp_deflator=gdp/real_gdp, gni=gni, gndi=gndi, national_saving=saving, current_account=ca, capital_account=F(0), external_asset_acquisition=external_asset_acquisition, external_liability_incurrence=external_liability_incurrence, financial_account=fa, public_interest=F(2), public_primary_surplus=F(-4), public_end_debt=F(56), public_gross_issuance=F(31), public_debt_gdp=56/gdp, nfa_open=F(-40), nfa_valuation=F(1), nfa_close=-39+ca, terminal_numeraire_A=terminal_a, terminal_numeraire_B=terminal_b, full_utility_A=F(339,2)+wa, full_utility_B=F(341,2)+wb, adjusted_utility_A=89+wa, adjusted_utility_B=90+wb, adjusted_utility_total=179+welfare, global_welfare_gap=F(304,3)-welfare)
    return output

def pilot_result(pilot):
    selected = {}
    for row in pilot["records"]:
        key = (row["community"], row["period"])
        if row["released"] <= pilot["cutoff"] and (key not in selected or row["released"] > selected[key]["released"]):
            selected[key] = row
    changes = {c: fraction(selected[c,"2024-05"]["usage"])-fraction(selected[c,"2024-04"]["usage"]) for c in pilot["communities"]}
    def contrast(treated):
        return sum((changes[c] for c in treated),F(0))/3-sum((changes[c] for c in changes if c not in treated),F(0))/3
    observed = contrast(pilot["treated"])
    distribution = [contrast(t) for t in combinations(pilot["communities"],3)]
    tail = sum(abs(v) >= abs(observed) for v in distribution)
    return {"cutoff":pilot["cutoff"],"changes":changes,"contrast":observed,"assignments":len(distribution),"two_sided_tail":tail,"sharp_null_p":F(tail,len(distribution)),"assignment_contrasts":distribution,"selected_release_keys":[[c,p,selected[c,p]["released"]] for c in pilot["communities"] for p in ("2024-04","2024-05")]}

def encode(value):
    if isinstance(value,F):
        return str(value)
    if isinstance(value,dict):
        return {k:encode(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [encode(v) for v in value]
    return value

def analyze(data):
    validate(data)
    return encode({"schema":"economics-core-results-1", "units":deepcopy(UNITS), "scope":"Fixed synthetic model; all monetary results are HC; base-price GDP is a declared teaching index, not welfare", "policies":[policy_result(p) for p in data["policies"]], "pilot":pilot_result(data["pilot"])})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",nargs="?",type=Path,default=Path(__file__).with_name("economics-core-inputs.json"))
    args=parser.parse_args()
    try:
        result=analyze(json.loads(args.input.read_text()))
    except (ValueError,OSError,TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__ == "__main__":
    main()
