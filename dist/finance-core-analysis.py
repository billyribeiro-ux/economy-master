"""Cedar Reserve: an exact, finite, original teaching contract. Standard library only."""
import argparse
from fractions import Fraction as F
import json
import math
from pathlib import Path
import sys

MAX_BYTES = 32768
NAME = "finance-core"
HERE = Path(__file__).resolve().parent
FIXED = {
    "currency": "CU", "terminal_cutoffs": ["09:00", "12:00", "16:00"],
    "parent_opening": {"cash": 10, "receivables": 20, "inventory": 30, "ppe": 60,
                       "payables": 20, "debt": 40, "equity": 60},
    "parent_period": {"sales": 100, "purchases": 50, "supplier_cash": 55, "cogs": 60,
                      "other_cash_cost": 20, "depreciation": 10, "retained_cash_floor": 10},
    "project": {"ppe_cost": 30, "inventory_cost": 20, "depreciation": 20,
                "other_cash_cost": 30, "equipment_sale": 10, "sales": [50, 80, 110], "note_face": 50},
    "market": {"states": ["down", "normal", "up"], "state_prices": [.2, .3, .4],
               "bill_price": .9, "historical_note_quote": 41,
               "historical_escrow_quote": 4, "historical_credit_quote": 2.4},
    "reserve": {"client_prefunding": 57.6, "sponsor_cash": 6.4, "client_due": [20, 44],
                "terminal_capital_floor": 2, "note_fractions": [.5, .75, 1],
                "hedge_fractions_of_note": [.5, 1], "note_execution_fee": .1,
                "escrow_custody_fee": .4, "es_level": .9},
    "providers": {"client_payer_cash": 60, "sponsor_cash": 10,
                  "note_underwriter_cash": 50, "equity_subscriber_cash": 20,
                  "bill_issuer_cash": 100, "escrow_pool_cash": 20, "credit_pool_cash": 12,
                  "protection_face": 20, "dealer_units_each_claim": 1}}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, label, low, high):
    require(type(value) in (int, float), label + " must be a JSON number, not a boolean")
    require(type(value) is int or math.isfinite(value), label + " must be finite")
    result = F(str(value))
    require(low <= result <= high, label + " is outside the documented domain")
    require(result.denominator <= 10**12, label + " has a reduced denominator above 10^12")
    return result


def keys(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), label + " has wrong keys/type")


def fixed(actual, expected, label):
    if type(expected) is dict:
        keys(actual, expected, label)
        for key, value in expected.items():
            fixed(actual[key], value, label + "." + key)
    elif type(expected) is list:
        require(type(actual) is list and len(actual) == len(expected), label + " has wrong list length/type")
        for index, value in enumerate(expected):
            fixed(actual[index], value, label + "[" + str(index) + "]")
    elif type(expected) in (int, float):
        require(number(actual, label, -1000, 1000) == F(str(expected)), label + " is a fixed contract term")
    else:
        require(type(actual) is str and actual == expected, label + " is a fixed contract term")


def validate(data):
    keys(data, ("schema", "case", "provenance", "contract", "experiment"), "input")
    require(type(data["schema"]) is int and data["schema"] == 1, "schema must be integer 1")
    require(data["case"] == "Morrow Components and Cedar Reserve" and type(data["case"]) is str, "unknown case")
    require(type(data["provenance"]) is str and 1 <= len(data["provenance"]) <= 512, "provenance must be short text")
    fixed(data["contract"], FIXED, "contract")
    e = data["experiment"]
    keys(e, ("historical_collections", "down_revenue_loss", "information", "physical_probabilities",
             "escrow_settlement", "escrow_senior_claim"), "experiment")
    collections = number(e["historical_collections"], "historical_collections", 80, 90)
    loss = number(e["down_revenue_loss"], "down_revenue_loss", 0, 10)
    require(type(e["information"]) is str and e["information"] in ("before_trade", "after_trade"), "unknown information contract")
    p = e["physical_probabilities"]
    require(type(p) is list and len(p) == 3, "three physical probabilities required")
    probabilities = [number(x, "physical probability", 0, 1) for x in p]
    require(all(x > 0 for x in probabilities) and sum(probabilities) == 1,
            "physical probabilities must be strictly positive and sum exactly to one")
    require(type(e["escrow_settlement"]) is str and e["escrow_settlement"] in ("12:00", "16:00"), "unknown escrow cutoff")
    senior = number(e["escrow_senior_claim"], "escrow_senior_claim", 0, 5)
    require(e["information"] == "after_trade" or (senior == 0 and e["escrow_settlement"] == "12:00"),
            "before_trade reprices revenue only; discovered priority/delay are after_trade contracts")
    return collections, loss, probabilities, senior


def plain(value):
    if isinstance(value, F):
        return value.numerator if value.denominator == 1 else float(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def tail_risk(losses, probabilities, alpha):
    ordered = sorted(zip(losses, probabilities))
    cumulative = F(0)
    var = ordered[-1][0]
    for loss, mass in ordered:
        cumulative += mass
        if cumulative >= alpha:
            var = loss
            break
    remaining = 1 - alpha
    weighted = F(0)
    for loss, mass in reversed(ordered):
        taken = min(remaining, mass)
        weighted += taken * loss
        remaining -= taken
    return {"mean_loss": sum(p*l for p, l in zip(probabilities, losses)),
            "var": var, "es": weighted/(1-alpha), "loss_by_state": losses}


def run(data):
    """Return JSON-safe evidence, without stdout, input mutation or file access."""
    collections, shock, probabilities, senior = validate(data)
    c = data["contract"]
    e = data["experiment"]
    o, a, j, m, r, providers = (c[k] for k in
                              ("parent_opening", "parent_period", "project", "market", "reserve", "providers"))
    pi = [F(str(v)) for v in m["state_prices"]]
    discount = F(str(m["bill_price"]))
    present = lambda amounts: sum(w*x for w, x in zip(pi, amounts))
    parent_income = a["sales"] - a["cogs"] - a["other_cash_cost"] - a["depreciation"]
    parent_cfo = collections - a["supplier_cash"] - a["other_cash_cost"]
    end = {"cash": o["cash"]+parent_cfo, "receivables": o["receivables"]+a["sales"]-collections,
           "inventory": o["inventory"]+a["purchases"]-a["cogs"], "ppe": o["ppe"]-a["depreciation"],
           "payables": o["payables"]+a["purchases"]-a["supplier_cash"], "debt": o["debt"],
           "equity": o["equity"]+parent_income}
    parent_indirect = (parent_income+a["depreciation"]-(end["receivables"]-o["receivables"])
                       -(end["inventory"]-o["inventory"])+(end["payables"]-o["payables"]))
    post_ap_cash = end["cash"]-end["payables"]
    parent_ok = post_ap_cash >= a["retained_cash_floor"]
    parent = {"income": parent_income, "direct_cfo": parent_cfo, "indirect_cfo": parent_indirect,
              "closing": end, "assets": sum(end[k] for k in ("cash", "receivables", "inventory", "ppe")),
              "liabilities_and_equity": sum(end[k] for k in ("payables", "debt", "equity")),
              "cash_after_paying_all_ap": post_ap_cash, "operating_reserve_gap": max(F(0), a["retained_cash_floor"]-post_ap_cash),
              "parent_gate": parent_ok}
    sales = [F(j["sales"][0])-shock, F(j["sales"][1]), F(j["sales"][2])]
    assets = [s-j["other_cash_cost"]+j["equipment_sale"] for s in sales]
    note = [min(F(j["note_face"]), v) for v in assets]
    equity = [max(F(0), v-j["note_face"]) for v in assets]
    cost = j["ppe_cost"]+j["inventory_cost"]
    note_quote = present(note) if e["information"] == "before_trade" else F(m["historical_note_quote"])
    equity_cash = cost-note_quote
    equity_share = equity_cash/present(equity)
    require(0 <= equity_share <= 1 and equity_cash <= providers["equity_subscriber_cash"], "new equity is unfunded")
    escrow_pay = [F(providers["escrow_pool_cash"])-senior, F(0), F(0)]
    credit_pay = [F(providers["credit_pool_cash"]), F(0), F(0)]
    escrow_quote = F(m["historical_escrow_quote"])
    credit_quote = F(str(m["historical_credit_quote"]))
    wealth = F(str(r["client_prefunding"]))+F(str(r["sponsor_cash"]))
    due09, due12 = map(F, r["client_due"])
    face = providers["protection_face"]
    benchmark = wealth/discount-due09-due12
    project = {"sales_cash": sales, "operating_income": [s-j["inventory_cost"]-j["other_cash_cost"]-j["depreciation"] for s in sales],
               "estate": assets, "note_paid": note, "note_unpaid_nominal": [j["note_face"]-n for n in note],
               "equity_paid": equity, "current_asset_pv": present(assets), "current_note_pv": present(note),
               "equity_pv": present(equity), "current_unfunded_opportunity_npv": present(assets)-cost,
               "entry_note_proceeds": note_quote, "new_equity_cash": equity_cash,
               "new_equity_share": equity_share, "parent_equity_share": 1-equity_share,
               "entry_note_discount": j["note_face"]-note_quote,
               "pre_resolution_book_equity": [equity_cash+s-j["inventory_cost"]-j["other_cash_cost"]-j["depreciation"]-(j["note_face"]-note_quote) for s in sales],
               "protection_current_pvs": {"escrow": present(escrow_pay), "credit": present(credit_pay)}}
    policies, detail = [], {}
    for raw_x in r["note_fractions"]:
        x = F(str(raw_x))
        choices = [("none", F(0))]
        choices += [(kind, x*F(str(f))) for kind in ("credit", "escrow") for f in r["hedge_fractions_of_note"]]
        for kind, h in choices:
            policy_id = str(x)+"-"+kind+"-"+str(h)
            premium = h*(escrow_quote if kind == "escrow" else credit_quote if kind == "credit" else 0)
            fees = x*F(str(r["note_execution_fee"]))+(h*F(str(r["escrow_custody_fee"])) if kind == "escrow" else 0)
            bill_cash = wealth-x*note_quote-premium-fees
            require(bill_cash >= 0 and (1-x)*note_quote <= providers["note_underwriter_cash"], "policy has unfunded entry")
            terminal_bill = bill_cash/discount
            states = []
            for i, state in enumerate(m["states"]):
                cash = F(0)
                arrears = F(0)
                journal = []
                def post(cutoff, event, received=F(0), paid=F(0), nominal_due=F(0)):
                    nonlocal cash, arrears
                    cash += received-paid
                    arrears += nominal_due-paid if nominal_due else -paid if event == "late_client_cure" else 0
                    require(cash >= 0 and arrears >= 0, "negative executed cash or claims")
                    journal.append({"time": cutoff, "event": event, "receipt": received, "payment": paid,
                                    "new_client_due": nominal_due, "cash": cash, "client_arrears": arrears})
                post("09:00", "bill_redemption", received=terminal_bill)
                paid09 = min(cash, due09)
                post("09:00", "first_client_payment", paid=paid09, nominal_due=due09)
                post("12:00", "project_note_receipt", received=x*note[i])
                if kind == "escrow" and e["escrow_settlement"] == "12:00":
                    post("12:00", "escrow_receipt", received=h*escrow_pay[i])
                paid12 = min(cash, due12)
                post("12:00", "second_client_payment", paid=paid12, nominal_due=due12)
                # All supported policies meet 09:00. The retained earlier claim is
                # never erased; only a separate late receipt can fund an actual cure.
                late = h*credit_pay[i] if kind == "credit" else h*escrow_pay[i] if kind == "escrow" and e["escrow_settlement"] == "16:00" else F(0)
                if kind != "none":
                    post("16:00", "late_protection_receipt", received=late)
                cure = min(cash, arrears)
                post("16:00", "late_client_cure", paid=cure)
                net = cash-arrears
                states.append({"state": state, "paid09": paid09, "paid12": paid12,
                               "missed_at_deadline": (due09-paid09)+(due12-paid12),
                               "late_cure": cure, "terminal_cash": cash, "client_unpaid_nominal": arrears,
                               "terminal_net_capital": net, "journal": journal})
            nets = [v["terminal_net_capital"] for v in states]
            timely = all(v["missed_at_deadline"] == 0 for v in states)
            capital_ok = min(nets) >= r["terminal_capital_floor"]
            eligible = timely and capital_ok
            score = sum(p*n for p, n in zip(probabilities, nets))
            risk = tail_risk([benchmark-n for n in nets], probabilities, F(str(r["es_level"])))
            row = {"id": policy_id, "note_fraction": x, "kind": kind, "hedge_fraction": h,
                   "entry_fees": fees, "bill_purchase": bill_cash, "cash_after09": terminal_bill-due09,
                   "net_capital_by_state": nets, "missed_at_deadline_by_state": [v["missed_at_deadline"] for v in states],
                   "client_unpaid_by_state": [v["client_unpaid_nominal"] for v in states],
                   "physical_mean_capital": score, "timely": timely, "capital_floor_met": capital_ok,
                   "eligible": eligible, "risk": risk}
            policies.append(row)
            detail[policy_id] = states
    qualifying = [p for p in policies if p["eligible"]]
    ranked = sorted(qualifying, key=lambda p: (-p["physical_mean_capital"], p["note_fraction"], p["hedge_fraction"], p["kind"]))
    chosen = ranked[0] if ranked else None
    baseline_position = next(p for p in policies if p["id"] == "1/2-escrow-1/4")
    after_shock = e["information"] == "after_trade" and (shock > 0 or senior > 0 or e["escrow_settlement"] == "16:00")
    shown = chosen if chosen is not None else baseline_position
    x, h, kind = shown["note_fraction"], shown["hedge_fraction"], shown["kind"]
    premium = h*(escrow_quote if kind == "escrow" else credit_quote if kind == "credit" else 0)
    balances = {"reserve": F(0), "client_payer": F(providers["client_payer_cash"]), "sponsor": F(providers["sponsor_cash"]),
                "note_underwriter": F(providers["note_underwriter_cash"]), "equity_subscriber": F(providers["equity_subscriber_cash"]),
                "dealer": F(0), "fee_provider": F(0), "bill_issuer": F(providers["bill_issuer_cash"]),
                "spv": F(0), "equipment_seller": F(0), "inventory_supplier": F(0),
                "escrow_pool": F(providers["escrow_pool_cash"]), "credit_pool": F(providers["credit_pool_cash"])}
    initial_cash_sum = sum(balances.values())
    transfers = []
    def transfer(payer, recipient, amount, reason):
        balances[payer] -= amount
        balances[recipient] += amount
        require(balances[payer] >= 0, "unfunded modeled payer " + payer)
        transfers.append({"payer": payer, "recipient": recipient, "cash": amount, "reason": reason})
    transfer("client_payer", "reserve", F(str(r["client_prefunding"])), "fixed client subscription")
    transfer("sponsor", "reserve", F(str(r["sponsor_cash"])), "paid-in sponsor equity")
    transfer("reserve", "spv", x*note_quote, "note purchase")
    transfer("note_underwriter", "spv", (1-x)*note_quote, "remaining note purchase")
    transfer("equity_subscriber", "spv", equity_cash, "residual equity subscription")
    transfer("spv", "equipment_seller", F(j["ppe_cost"]), "initial equipment")
    transfer("spv", "inventory_supplier", F(j["inventory_cost"]), "initial inventory")
    transfer("reserve", "dealer", premium, "existing protection transferred; no pool contribution")
    transfer("reserve", "fee_provider", shown["entry_fees"], "execution and custody costs")
    transfer("reserve", "bill_issuer", shown["bill_purchase"], "bill purchase")
    terminal_allocations = []
    for i, state in enumerate(m["states"]):
        escrow_fraction = h if kind == "escrow" else F(0)
        credit_fraction = h if kind == "credit" else F(0)
        escrow_writer = providers["escrow_pool_cash"]-senior-escrow_pay[i]
        credit_writer = providers["credit_pool_cash"]-credit_pay[i]
        terminal_allocations.append({"state": state,
            "spv_cash": {"customer_receipt": sales[i], "equipment_buyer_receipt": j["equipment_sale"],
                         "operating_payee": j["other_cash_cost"], "cedar_note": x*note[i],
                         "underwriter_note": (1-x)*note[i], "new_equity_holder": equity_share*equity[i],
                         "parent_shareholder": (1-equity_share)*equity[i], "ending_cash": F(0),
                         "cedar_note_unpaid_nominal": x*(j["note_face"]-note[i]),
                         "underwriter_note_unpaid_nominal": (1-x)*(j["note_face"]-note[i])},
            "escrow_pool": {"settlement": e["escrow_settlement"], "senior_paid": senior,
                            "cedar_paid": escrow_fraction*escrow_pay[i], "dealer_paid": (1-escrow_fraction)*escrow_pay[i],
                            "writer_cash_return": escrow_writer,
                            "cedar_unpaid_nominal": escrow_fraction*(face-escrow_pay[i]) if i == 0 else F(0),
                            "dealer_unpaid_nominal": (1-escrow_fraction)*(face-escrow_pay[i]) if i == 0 else F(0)},
            "credit_pool": {"settlement": "16:00", "cedar_paid": credit_fraction*credit_pay[i],
                            "dealer_paid": (1-credit_fraction)*credit_pay[i], "writer_cash_return": credit_writer,
                            "cedar_unpaid_nominal": credit_fraction*(face-credit_pay[i]) if i == 0 else F(0),
                            "dealer_unpaid_nominal": (1-credit_fraction)*(face-credit_pay[i]) if i == 0 else F(0)},
            "bill_issuer_after_redemption": providers["bill_issuer_cash"]+shown["bill_purchase"]-shown["bill_purchase"]/discount})
    current_terminal_pv = present(shown["net_capital_by_state"])
    exact = {"selected_mean": str(chosen["physical_mean_capital"]) if chosen else None,
             "shown_net_capital": [str(v) for v in shown["net_capital_by_state"]],
             "shown_terminal_net_pv": str(current_terminal_pv), "shown_es90": str(shown["risk"]["es"])}
    # This certificate fixes the selected baseline position and varies one shock.
    # It is deliberately absent for compound changes rather than reusing a false boundary.
    certificate = None
    if senior == 0 and e["escrow_settlement"] == "12:00":
        slope = F(7, 18) if e["information"] == "before_trade" else F(1, 2)
        boundary = (F(55, 18)-r["terminal_capital_floor"])/slope
        certificate = {"position": "1/2-escrow-1/4", "information": e["information"],
                       "bad_capital_intercept": "55/18", "bad_capital_shock_slope": str(-slope),
                       "capital_floor_boundary": str(boundary), "boundary_is_inclusive": True,
                       "scope": "fixed position; total down-revenue loss from baseline, not distance from this experiment"}
    result = {"schema": 1, "project": NAME, "information": e["information"],
              "parent": parent, "project_claims": project,
              "physical_probabilities": probabilities, "state_prices": pi,
              "opening_reserve_cash": wealth, "client_full_performance_pv": discount*(due09+due12),
              "full_performance_pv_scope": "Performing supported policies only; not a fair-value statement for rejected portfolios.",
              "cash_only_terminal_benchmark": benchmark, "policies": policies,
              "eligible_policy_ids": [p["id"] for p in ranked], "selected_policy": chosen["id"] if chosen else None,
              "comparison_scope": "historical_entry_counterfactuals" if after_shock else "prospective_entry",
              "menu_has_feasible_policy": chosen is not None,
              "prospective_entry_approval": None if after_shock else parent_ok and chosen is not None,
              "actual_after_trade_position": {"id": baseline_position["id"], "eligible": baseline_position["eligible"],
                  "net_capital_by_state": baseline_position["net_capital_by_state"],
                  "missed_at_deadline_by_state": baseline_position["missed_at_deadline_by_state"]} if after_shock else None,
              "institution_approval": parent_ok and (baseline_position["eligible"] if after_shock else chosen is not None),
              "approval_scope": "Modeled gates for prospective selection, or unchanged baseline holdings after a shock; no executed switch or verified external authority.",
              "shown_policy": shown["id"],
              "shown_policy_reason": ("historical-entry counterfactual winner; no switch executed" if after_shock else "prospective selection") if chosen else "fixed baseline diagnostic; not approved",
              "entry": {"transfers": transfers, "remaining_cash": balances, "cash_sum_before": initial_cash_sum,
                        "cash_sum_after": sum(balances.values()), "dealer_escrow_units_retained": 1-(h if kind == "escrow" else 0),
                        "dealer_credit_units_retained": 1-(h if kind == "credit" else 0),
                        "dealer_original_reference_claim_value": escrow_quote+credit_quote,
                        "dealer_after_sale_cash_plus_reference_claim_value": premium+(1-(h if kind == "escrow" else 0))*escrow_quote+(1-(h if kind == "credit" else 0))*credit_quote},
              "shown_reserve_states": detail[shown["id"]], "shown_terminal_allocations": terminal_allocations,
              "shown_terminal_net_pv": current_terminal_pv, "exact": exact, "fixed_position_reverse_certificate": certificate,
              "limits": ["Finite 15-policy mandate, three stipulated states; no empirical frequency or general optimizer.",
                         "After-trade shocks compare hypothetical original-entry policies at historical tickets; actual holdings stay at the baseline position, with no refund or rebalance.",
                         "Same-day 09/12/16 timing with zero intraday carry; late cures preserve missed deadlines.",
                         "External customers/equipment buyer are stipulated funded payers; cash conservation covers listed accounts/transfers only.",
                         "Unpaid nominal project/protection claims survive with zero additional modeled recovery, not legal cancellation.",
                         "Provider idle cash returns at its stated settlement time and cannot fund Cedar's earlier obligations."]}
    return plain(result)


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def no_duplicates(items):
    out = {}
    for key, value in items:
        require(key not in out, "duplicate JSON key: " + key)
        out[key] = value
    return out


def load_input(path):
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES+1)
    require(len(raw) <= MAX_BYTES, "input exceeds 32768 bytes")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates, parse_constant=reject_constant)


def guard_output(output, input_path):
    book = HERE.parent.parent
    protected = [input_path, Path(__file__).resolve(), HERE/(NAME+"-inputs.json"),
                 HERE/(NAME+"-README.txt"), HERE/(NAME+"-manifest.json"),
                 book/"content/cross-assessments/parts/finance-core-project.html",
                 book/"scripts/check_finance_core_project.py",
                 book/"content/reviews/finance-core-project-author.json",
                 book/"content/reviews/finance-core-project-sources.json"]
    target = output.resolve()
    for path in protected:
        require(target != path.resolve(), "output aliases protected payload: " + path.name)
        if output.exists() and path.exists():
            require(not output.samefile(path), "output hardlink aliases protected payload: " + path.name)
    require(not output.exists() or output.is_file(), "output must be a regular file")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE/(NAME+"-inputs.json"))
    parser.add_argument("--output", type=Path, default=HERE/(NAME+"-output.json"))
    args = parser.parse_args()
    try:
        guard_output(args.output, args.input)
        report = run(load_input(args.input))
        payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+"\n"
        args.output.write_text(payload, encoding="utf-8")
    except (ValueError, TypeError, OverflowError, OSError, RecursionError) as exc:
        print("finance-core: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
