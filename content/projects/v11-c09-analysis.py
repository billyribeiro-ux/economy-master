"""Original finite currency, payment-location and sovereign-budget laboratory.

Synthetic contracts, not market data or current law. Python standard library only.
run(data) validates and returns a new exact JSON-compatible report, without I/O.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 150000
Q = re.compile(r"-?(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,8}|/[1-9][0-9]{0,8})?\Z")
ID = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")


def obj(value, keys, name):
    if type(value) is not dict or set(value) != set(keys.split()):
        raise ValueError(name + ": exact object keys required")
    return value


def seq(value, lo, hi, name):
    if type(value) is not list or not lo <= len(value) <= hi:
        raise ValueError(name + ": bounded list required")
    return value


def number(value, lo, hi, name):
    if type(value) is not str or not Q.fullmatch(value):
        raise ValueError(name + ": bounded decimal or rational string required")
    q = F(value)
    if not lo <= q <= hi:
        raise ValueError(name + ": outside supported interval")
    return q


def quantities(raw, keys, name, positive=()):
    obj(raw, keys, name)
    return {k: number(v, F(1, 100) if k in positive else 0, 10000, name + "." + k) for k, v in raw.items()}


def scenario_list(raw, keys, name):
    seq(raw, 1, 8, name)
    seen = set()
    for row in raw:
        obj(row, keys, name)
        name_id = row["id"]
        if type(name_id) is not str or not ID.fullmatch(name_id) or name_id in seen:
            raise ValueError(name + ": distinct short scenario ids required")
        seen.add(name_id)
    return seen


def validate(data):
    obj(data, "schema parity exporter export_scenarios hedge_design_scenarios sovereign sovereign_scenarios willingness rescheduling", "root")
    if type(data["schema"]) is not int or data["schema"] != 1:
        raise ValueError("schema: integer 1 required")
    p = quantities(data["parity"], "spot_H_per_F home_gross foreign_gross", "parity", ("spot_H_per_F", "home_gross", "foreign_gross"))
    for key in ("home_gross", "foreign_gross"):
        if not F(1, 2) <= p[key] <= 2: raise ValueError("parity: gross factors must lie in [1/2,2]")
    if p["spot_H_per_F"] > 100: raise ValueError("parity: spot at most100")
    e = quantities(data["exporter"], "offshore_cash_H net_receivable_F debt_H hedge_F", "exporter")
    if e["hedge_F"] > e["net_receivable_F"]: raise ValueError("exporter: hedge lies in [0,net receivable]")
    export_keys = "id spot_H_per_F fixing_H_per_F conversion_cap_F transfer_cap_H margin_H_per_hedged_F positive_settlement_fraction receipt_before_cutoff"
    export_ids = scenario_list(data["export_scenarios"], export_keys, "export_scenarios")
    scenarios = []
    for raw in data["export_scenarios"]:
        if type(raw["receipt_before_cutoff"]) is not bool: raise ValueError("receipt timing must be Boolean")
        s = dict(id=raw["id"], receipt_before_cutoff=raw["receipt_before_cutoff"])
        for key in export_keys.split()[1:-1]:
            lo = F(1, 100) if key in ("spot_H_per_F", "fixing_H_per_F") else 0
            hi = 100 if key in ("spot_H_per_F", "fixing_H_per_F") else 2 if key == "margin_H_per_hedged_F" else 1 if key == "positive_settlement_fraction" else 10000
            s[key] = number(raw[key], lo, hi, key)
        scenarios.append(s)
    selection = seq(data["hedge_design_scenarios"], 1, 4, "hedge_design_scenarios")
    if any(type(s) is not str for s in selection) or len(set(selection)) != len(selection) or not set(selection) <= export_ids:
        raise ValueError("hedge design requires distinct existing scenario ids")
    sov = quantities(data["sovereign"], "opening_spot_H_per_F reserves_F blocked_reserves_F reserve_floor_F cash_after_primary_spending_H local_due_H foreign_due_F other_foreign_principal_F new_loan_gross", "sovereign", ("opening_spot_H_per_F", "new_loan_gross"))
    if sov["opening_spot_H_per_F"] > 100 or not F(1, 2) <= sov["new_loan_gross"] <= 2:
        raise ValueError("sovereign: spot/gross factor bounds")
    if sov["blocked_reserves_F"]+sov["reserve_floor_F"] > sov["reserves_F"]:
        raise ValueError("sovereign: blocked reserves and floor exceed reserve inventory")
    sovereign_keys = "id spot_H_per_F export_fiscal_receipt_F essential_imports_F new_borrowing_F conversion_cap_F"
    scenario_list(data["sovereign_scenarios"], sovereign_keys, "sovereign_scenarios")
    sovereign_scenarios = []
    for raw in data["sovereign_scenarios"]:
        row = {"id": raw["id"]}
        for key in sovereign_keys.split()[1:]:
            row[key] = number(raw[key], F(1, 100) if key == "spot_H_per_F" else 0, 100 if key == "spot_H_per_F" else 10000, key)
        sovereign_scenarios.append(row)
    raw = obj(data["willingness"], "resources_H capacity_F promised_F default_cost_H spots_H_per_F", "willingness")
    w = {k: number(raw[k], 0, 10000, k) for k in ("resources_H", "capacity_F", "promised_F", "default_cost_H")}
    w["spots_H_per_F"] = [number(s, F(1, 100), 100, "willingness spot") for s in seq(raw["spots_H_per_F"], 1, 4, "willingness spots")]
    r = quantities(data["rescheduling"], "due_F replacement_F discount_one discount_two", "rescheduling")
    if not F(1, 100) <= r["discount_one"] <= 2 or not F(1, 100) <= r["discount_two"] <= 2:
        raise ValueError("rescheduling: positive bounded discount factors required")
    return p, e, scenarios, selection, sov, sovereign_scenarios, w, r


def encode(value):
    if isinstance(value, F): return str(value)
    if isinstance(value, dict): return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [encode(v) for v in value]
    return value


def export_state(e, s, K, hedge=None, injection=F(0)):
    h = e["hedge_F"] if hedge is None else hedge
    cash = e["offshore_cash_H"]+injection
    margin = h*s["margin_H_per_hedged_F"]
    posted = min(cash, margin)
    cash -= posted
    trail = [{"event": "early_collateral", "offshore_cash_H": cash, "segregated_collateral_H": posted}]
    arrived = e["net_receivable_F"] if s["receipt_before_cutoff"] else F(0)
    converted = min(arrived, s["conversion_cap_F"])
    onshore_H = converted*s["spot_H_per_F"]
    transferred = min(onshore_H, s["transfer_cap_H"])
    onshore_H -= transferred
    cash += transferred
    trail.append({"event": "receipt_conversion_transfer", "offshore_cash_H": cash, "onshore_H": onshore_H, "onshore_F": arrived-converted, "late_receivable_F": e["net_receivable_F"]-arrived})
    gross = h*(K-s["fixing_H_per_F"])
    received = max(gross, F(0))*s["positive_settlement_fraction"]
    owed = max(-gross, F(0))
    cash += received
    derivative_paid = min(cash, owed)
    cash -= derivative_paid
    trail.append({"event": "derivative_settles_before_debt", "offshore_cash_H": cash, "received_H": received, "paid_H": derivative_paid, "unpaid_H": owed-derivative_paid})
    paid = min(cash, e["debt_H"])
    cash -= paid
    trail.append({"event": "external_debt_cutoff", "offshore_cash_H": cash, "debt_paid_H": paid, "debt_unpaid_H": e["debt_H"]-paid})
    late_cash = cash+posted
    late_F = e["net_receivable_F"]-converted
    trail.append({"event": "later_collateral_and_receipt_release", "offshore_cash_H": late_cash, "onshore_F": late_F, "onshore_H": onshore_H})
    minimum = max(F(0), margin-e["offshore_cash_H"], margin+e["debt_H"]+owed-e["offshore_cash_H"]-transferred-received)
    economic_resources = e["offshore_cash_H"]+injection+e["net_receivable_F"]*s["spot_H_per_F"]+received-owed-e["debt_H"]
    closing = late_cash+onshore_H+late_F*s["spot_H_per_F"]-(owed-derivative_paid)-(e["debt_H"]-paid)
    return dict(id=s["id"], hedge_F=h, initial_injection_H=injection, margin_required_H=margin, margin_posted_H=posted, margin_unposted_H=margin-posted,
                converted_F=converted, transferred_H=transferred, derivative_contract_H=gross, derivative_received_H=received,
                derivative_positive_loss_H=max(gross,F(0))-received, derivative_paid_H=derivative_paid, derivative_unpaid_H=owed-derivative_paid,
                debt_paid_H=paid, debt_unpaid_H=e["debt_H"]-paid, cutoff_cash_H=cash, later_offshore_cash_H=late_cash,
                onshore_H=onshore_H, later_onshore_F=late_F, minimum_initial_injection_H=minimum,
                all_cutoffs_met=(posted==margin and derivative_paid==owed and paid==e["debt_H"]),
                terminal_account_value_H=closing, direct_terminal_value_H=economic_resources, value_residual_H=closing-economic_resources, cash_trail=trail)


def hedge_design(e, scenarios, selection, K):
    chosen = [s for s in scenarios if s["id"] in selection]
    lines = [{"label": "nonnegative_injection", "slope": F(0), "intercept": F(0)}]
    for s in chosen:
        arrived = e["net_receivable_F"] if s["receipt_before_cutoff"] else F(0)
        transfer = min(min(arrived,s["conversion_cap_F"])*s["spot_H_per_F"],s["transfer_cap_H"])
        rate = K-s["fixing_H_per_F"]
        m = s["margin_H_per_hedged_F"]
        lines += [{"label": s["id"]+":early", "slope": m, "intercept": -e["offshore_cash_H"]},
                  {"label": s["id"]+":late", "slope": m+max(-rate,F(0))-s["positive_settlement_fraction"]*max(rate,F(0)), "intercept": e["debt_H"]-e["offshore_cash_H"]-transfer}]
    candidates = {F(0),e["net_receivable_F"]}
    for j, a in enumerate(lines):
        for b in lines[j+1:]:
            if a["slope"] != b["slope"]:
                h = (b["intercept"]-a["intercept"])/(a["slope"]-b["slope"])
                if 0 <= h <= e["net_receivable_F"]: candidates.add(h)
    evaluated = [(max(line["slope"]*h+line["intercept"] for line in lines), h) for h in candidates]
    injection, h = min(evaluated)
    return dict(selected_scenarios=selection, hedge_interval_F=[F(0),e["net_receivable_F"]], hedge_F=h, minimum_common_injection_H=injection,
                tie_rule="smallest hedge among minimum-injection candidates", constraints=lines,
                candidate_count=len(candidates), active_constraints=[line["label"] for line in lines if line["slope"]*h+line["intercept"]==injection],
                funded_selected_scenarios=[export_state(e,s,K,h,injection) for s in chosen])


def sovereign_state(v, s):
    local_paid = min(v["cash_after_primary_spending_H"],v["local_due_H"])
    remaining_H = v["cash_after_primary_spending_H"]-local_paid
    bought_F = min(s["conversion_cap_F"],remaining_H/s["spot_H_per_F"])
    closing_H = remaining_H-bought_F*s["spot_H_per_F"]
    free = v["reserves_F"]-v["blocked_reserves_F"]+s["export_fiscal_receipt_F"]+s["new_borrowing_F"]+bought_F
    spendable = max(F(0),free-v["reserve_floor_F"])
    imports_paid = min(spendable,s["essential_imports_F"])
    spendable -= imports_paid
    debt_paid = min(spendable,v["foreign_due_F"])
    closing_free = free-imports_paid-debt_paid
    debt_close = v["foreign_due_F"]+v["other_foreign_principal_F"]+s["new_borrowing_F"]-debt_paid
    old = v["foreign_due_F"]+v["other_foreign_principal_F"]
    revaluation = old*(s["spot_H_per_F"]-v["opening_spot_H_per_F"])
    transactions = (s["new_borrowing_F"]-debt_paid)*s["spot_H_per_F"]
    minimum = max(F(0),v["reserve_floor_F"]+s["essential_imports_F"]+v["foreign_due_F"]-free)
    return dict(id=s["id"], policy="conditional capacity ledger: local service, conversion, essential imports, foreign debt; preserve floor",
                local_paid_H=local_paid, local_unpaid_H=v["local_due_H"]-local_paid, bought_F=bought_F, dealer_receipt_H=bought_F*s["spot_H_per_F"], closing_cash_H=closing_H,
                before_external_payments_F=free, imports_paid_F=imports_paid, imports_unpaid_F=s["essential_imports_F"]-imports_paid,
                debt_paid_F=debt_paid, debt_unpaid_F=v["foreign_due_F"]-debt_paid, closing_free_reserves_F=closing_free,
                blocked_released_only_later_F=v["blocked_reserves_F"], minimum_external_topup_F=minimum,
                closing_foreign_principal_F=debt_close, new_loan_later_due_F=s["new_borrowing_F"]*v["new_loan_gross"],
                foreign_debt_value_change_H=debt_close*s["spot_H_per_F"]-old*v["opening_spot_H_per_F"],
                foreign_debt_revaluation_H=revaluation, foreign_debt_transactions_H=transactions,
                cash_residual_F=free-imports_paid-debt_paid-closing_free,
                debt_value_residual_H=debt_close*s["spot_H_per_F"]-old*v["opening_spot_H_per_F"]-revaluation-transactions,
                all_current_payments_met=(local_paid==v["local_due_H"] and imports_paid==s["essential_imports_F"] and debt_paid==v["foreign_due_F"]))


def run(data):
    p,e,scenarios,selection,v,sovereign_scenarios,w,r = validate(data)
    K = p["spot_H_per_F"]*p["home_gross"]/p["foreign_gross"]
    willingness = []
    for s in w["spots_H_per_F"]:
        feasible = w["capacity_F"] >= w["promised_F"]
        repay = w["resources_H"]-s*w["promised_F"]
        default = w["resources_H"]-w["default_cost_H"]
        choice = "repay" if feasible and repay >= default else "default_or_restructure"
        willingness.append(dict(spot_H_per_F=s, full_payment_feasible=feasible, utility_repay_if_feasible=repay,
                                utility_default=default, choice=choice, equality_rule="repay on an exact feasible tie"))
    old_pv=r["due_F"]*r["discount_one"]; new_pv=r["replacement_F"]*r["discount_two"]
    return encode(dict(schema=1, scenario_scope="synthetic fixed contracts; no probabilities or current jurisdictional rights inferred",
                       parity=dict(forward_H_per_F=K, full_hedge_gross_H=e["net_receivable_F"]*K,
                                   hypotheses="same maturity and credit, executable two-way funding/spot/forward, no costs or restrictions"),
                       exporter=[export_state(e,s,K) for s in scenarios], hedge_design=hedge_design(e,scenarios,selection,K),
                       sovereign=[sovereign_state(v,s) for s in sovereign_scenarios], willingness=willingness,
                       rescheduling=dict(original_PV_F=old_pv,replacement_PV_F=new_pv,creditor_PV_change_F=new_pv-old_pv,
                                         first_date_cash_relief_F=r["due_F"],second_date_added_due_F=r["replacement_F"])))


def pairs(items):
    result={}
    for k,v in items:
        if k in result: raise ValueError("duplicate JSON key: "+k)
        result[k]=v
    return result


def constant(token):
    raise ValueError("nonfinite JSON constant: "+token)


def safe_output(output, input_path):
    for protected in (input_path,Path(__file__)):
        if output.resolve()==protected.resolve() or (output.exists() and protected.exists() and output.samefile(protected)):
            raise ValueError("output must not overwrite input or implementation, including aliases")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=Path(__file__).with_name("v11-c09-inputs.json"))
    parser.add_argument("--output",type=Path,default=Path(__file__).with_name("v11-c09-output.json"))
    args=parser.parse_args(argv)
    try:
        safe_output(args.output,args.input)
        if args.input.stat().st_size>MAX_BYTES: raise ValueError("input exceeds150000bytes")
        text=args.input.read_text(encoding="utf-8")
        report=run(json.loads(text,object_pairs_hook=pairs,parse_constant=constant))
        rendered=json.dumps(report,indent=2,sort_keys=True)+"\n"
        args.output.write_text(rendered,encoding="utf-8")
    except (ValueError,OSError,RecursionError) as exc:
        parser.exit(2,"error: "+str(exc)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
