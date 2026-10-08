"""Nacre teaching benchmark: exact arithmetic, standard library, no network.

Run with Python 3 from any directory. An optional path supplies a case copy.
This is a deliberately bounded three-year operating and financing model.
"""
from fractions import Fraction
import json
from pathlib import Path
import sys


def F(value):
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Use exact integers or rational strings, not booleans/floats")
    return Fraction(value)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    return value


def validate(data):
    op, opening, finance = data["operations"], data["opening"], data["finance"]
    policy = data["benchmark_policy"]
    need(policy["sell_nonoperating_asset"] is True and F(policy["initial_payout"]) == 0
         and F(policy["new_equity"]) == 70,
         "The canonical benchmark requires asset sale, equity70 and payout0; use treasury arguments for explicit alternatives")
    need(F(data["offer"]["management_initial_payout"]) == 20
         and F(data["sensitivities"]["intervention_extra_downside_nwc_year1"]) == 10,
         "Named reference experiments require payout20 and delay10; use treasury arguments for other experiments")
    need(op["interest_deductible"] is False, "This model has no interest tax shields")
    need(0 <= F(op["tax_rate"]) < 1, "Operating tax rate must be in [0,1)")
    need(len(data["dates"]) == 4, "Exactly three explicit annual periods required")
    need(set(data["scenarios"]) == {"base", "downside"}, "Two named forecasts required")
    for key in ("operating_nwc", "ppe", "cash", "nonoperating_asset_sale_value", "term_principal", "term_market_value"):
        need(F(opening[key]) >= 0, "Opening balance must be nonnegative: " + key)
    need(F(opening["old_shares"]) > 0, "Positive old share count required")
    need(F(op["unit_price"]) > 0 and F(op["fixed_cash_cost"]) >= 0, "Invalid operating prices/costs")
    for key in ("depreciation", "capex"):
        need(len(op[key]) == 3 and all(F(v) >= 0 for v in op[key]), "Three nonnegative asset amounts required")
    for case in data["scenarios"].values():
        need(len(case["quantity"]) == len(case["closing_nwc_sales_ratio"]) == 3, "Three operating observations required")
        need(all(F(q) > 0 for q in case["quantity"]), "Positive quantities required")
        need(F(case["variable_unit_cost"]) >= 0, "Variable cost must be nonnegative")
        need(all(0 <= F(v) <= 1 for v in case["closing_nwc_sales_ratio"]), "NWC ratio outside modeled domain")
    for key in ("minimum_cash", "term_coupon", "revolver_coupon", "revolver_commitment", "gross_debt_ebitda_cap", "replacement_note_cap", "replacement_note_coupon"):
        need(F(finance[key]) >= 0, "Negative financing input: " + key)
    principal = list(map(F, finance["term_repayments"]))
    need(len(principal) == 3 and all(v >= 0 for v in principal), "Three nonnegative principal payments required")
    need(sum(principal) == F(opening["term_principal"]), "Term debt must fully amortize by date3")
    need(finance["revolver_maturity_year"] == 3, "Revolver maturity must be modeled at date3")
    for key in ("seller_equity_price", "outside_buyer_fee", "maximum_new_equity", "management_initial_payout"):
        need(F(data["offer"][key]) >= 0, "Negative offer/policy input")
    pricing, term = data["pricing"], data["terminal"]
    need(F(pricing["cash_after_tax_return"]) >= 0, "Cash return must be nonnegative here")
    need(F(term["revenue_opening_capital_turnover"]) > 0, "Positive terminal turnover required")
    need(0 <= F(term["depreciation_sales_ratio"]) < F(term["normalized_ebitda_margin"]) <= 1, "Positive terminal EBIT margin required")
    need(0 <= F(term["nwc_sales_ratio"]) <= 1, "Invalid terminal NWC ratio")
    need(F(pricing["risk_free_rate"]) + F(pricing["asset_beta"]) * F(pricing["equity_risk_premium"]) == F(pricing["operating_required_return"]), "Supplied capital-cost inputs do not reconcile")
    ids = [p["id"] for p in data["peers"]["candidates"]]
    need(len(ids) == len(set(ids)), "Peer IDs must be unique")


def forecast(data, scenario, extra_nwc_year1=0):
    """Cash-free operating capital; a collection delay releases at end2."""
    need(scenario in data["scenarios"], "Unknown forecast")
    extra = F(extra_nwc_year1)
    need(extra >= 0, "Additional collection delay cannot be negative")
    op, case = data["operations"], data["scenarios"][scenario]
    nwc, ppe = F(data["opening"]["operating_nwc"]), F(data["opening"]["ppe"])
    rows = []
    for index in range(3):
        quantity = F(case["quantity"][index])
        revenue = quantity * F(op["unit_price"])
        variable_cost = quantity * F(case["variable_unit_cost"])
        ebitda = revenue - variable_cost - F(op["fixed_cash_cost"])
        depreciation, capex = F(op["depreciation"][index]), F(op["capex"][index])
        ebit = ebitda - depreciation
        need(ebit > 0, "Loss-tax treatment is outside this positive-EBIT model")
        tax = ebit * F(op["tax_rate"])
        closing_nwc = revenue * F(case["closing_nwc_sales_ratio"][index]) + (extra if index == 0 else 0)
        closing_ppe = ppe + capex - depreciation
        need(closing_ppe >= 0, "PPE cannot be negative")
        opening_capital, closing_capital = ppe + nwc, closing_ppe + closing_nwc
        nopat = ebit - tax
        row = {"year": index + 1, "date": data["dates"][index + 1], "quantity": quantity,
               "revenue": revenue, "variable_cost": variable_cost, "fixed_cash_cost": F(op["fixed_cash_cost"]),
               "ebitda": ebitda, "depreciation": depreciation, "ebit": ebit, "operating_tax": tax,
               "nopat": nopat, "capex": capex, "opening_nwc": nwc, "closing_nwc": closing_nwc,
               "delta_nwc": closing_nwc - nwc, "opening_ppe": ppe, "closing_ppe": closing_ppe,
               "opening_capital": opening_capital, "closing_capital": closing_capital,
               "net_reinvestment": closing_capital - opening_capital,
               "fcff": nopat + depreciation - capex - (closing_nwc - nwc)}
        rows.append(row)
        nwc, ppe = closing_nwc, closing_ppe
    return rows


def terminal(data, rows, required_return=None, growth=None, roic=None):
    """Normalize ALL capital at date3; first continuing distribution is date4."""
    term = data["terminal"]
    r = F(data["pricing"]["operating_required_return"]) if required_return is None else F(required_return)
    g = F(term["nominal_growth"]) if growth is None else F(growth)
    turnover, tax = F(term["revenue_opening_capital_turnover"]), F(data["operations"]["tax_rate"])
    dep_ratio = F(term["depreciation_sales_ratio"])
    R = turnover * (F(term["normalized_ebitda_margin"]) - dep_ratio) * (1 - tax) if roic is None else F(roic)
    need(0 <= g < r and g < R, "This growing positive-cash tail requires 0 <= g < min(r, ROIC)")
    margin = dep_ratio + R / (turnover * (1 - tax))
    need(dep_ratio < margin <= 1, "ROIC sensitivity implies invalid terminal margin")
    capital = rows[-1]["closing_capital"]
    revenue = turnover * capital
    nwc = F(term["nwc_sales_ratio"]) * revenue
    dep = dep_ratio * revenue
    reinvestment = g * capital
    capex = dep + reinvestment - (nwc - rows[-1]["closing_nwc"])
    need(capex >= 0, "Tail requires an unmodeled asset disposal")
    nopat = R * capital
    return {"payment_year": 4, "value_date_year": 3, "required_return": r, "growth": g,
            "roic": R, "normalized_ebitda_margin": margin, "opening_capital": capital,
            "revenue": revenue, "ebitda": margin * revenue, "depreciation": dep,
            "nopat": nopat, "net_reinvestment": reinvestment, "reinvestment_fraction": g / R,
            "closing_nwc": nwc, "delta_nwc": nwc - rows[-1]["closing_nwc"], "capex": capex,
            "closing_ppe": rows[-1]["closing_ppe"] + capex - dep,
            "closing_capital": (1 + g) * capital, "fcff": nopat - reinvestment,
            "terminal_value": (nopat - reinvestment) / (r - g)}


def valuation(data, scenario, required_return=None, growth=None, roic=None):
    rows = forecast(data, scenario)
    tail = terminal(data, rows, required_return, growth, roic)
    r = tail["required_return"]
    explicit_pv = sum(row["fcff"] / (1 + r) ** row["year"] for row in rows)
    terminal_pv = tail["terminal_value"] / (1 + r) ** 3
    enterprise = explicit_pv + terminal_pv
    opening, offer = data["opening"], data["offer"]
    excluded_assets = F(opening["cash"]) + F(opening["nonoperating_asset_sale_value"])
    old_equity = enterprise + excluded_assets - F(opening["term_market_value"])
    new_equity = F(data["benchmark_policy"]["new_equity"])
    buyer_outlay = F(offer["seller_equity_price"]) + F(offer["outside_buyer_fee"]) + new_equity
    required_ev = F(offer["seller_equity_price"]) + F(offer["outside_buyer_fee"]) - excluded_assets + F(opening["term_market_value"])
    roic_break_even = tail["growth"] + (required_ev - explicit_pv) * (1 + r) ** 3 * (r - tail["growth"]) / tail["opening_capital"]
    return {"operating_rows": rows, "terminal": tail, "explicit_pv": explicit_pv,
            "terminal_pv": terminal_pv, "operating_enterprise_value": enterprise,
            "pre_action_equity_value": old_equity, "pre_action_value_per_old_share": old_equity / F(opening["old_shares"]),
            "post_subscription_equity_value": old_equity + new_equity, "buyer_total_outlay": buyer_outlay,
            "buyer_npv": old_equity + new_equity - buyer_outlay,
            "maximum_seller_price_after_fee": old_equity - F(offer["outside_buyer_fee"]),
            "break_even_terminal_roic": roic_break_even,
            "value_overstatement_if_reinvestment_omitted": tail["net_reinvestment"] / (r - tail["growth"]) / (1 + r) ** 3}


def treasury(data, scenario, new_equity=None, initial_payout=0, sell_asset=True, extra_nwc_year1=0):
    """Return a funded dated path, or a failure with no invented future cash."""
    opening, finance, offer = data["opening"], data["finance"], data["offer"]
    J = F(data["benchmark_policy"]["new_equity"]) if new_equity is None else F(new_equity)
    Q = F(initial_payout)
    need(0 <= J <= F(offer["maximum_new_equity"]), "New equity exceeds authorized date0 cap")
    need(Q >= 0, "Payout cannot be negative")
    need(isinstance(sell_asset, bool), "Asset-sale policy must be boolean")
    cash = F(opening["cash"]) + (F(opening["nonoperating_asset_sale_value"]) if sell_asset else 0) + J - Q
    cash_floor = F(finance["minimum_cash"])
    result = {"scenario": scenario, "new_equity": J, "initial_payout": Q, "sell_asset": sell_asset,
              "initial_cash": cash, "funded": False, "rows": []}
    if cash < cash_floor:
        result.update({"failure_year": 0, "cash_gap": cash_floor - cash, "reason": "Initial cash minimum fails"})
        return result
    op_rows = forecast(data, scenario, extra_nwc_year1)
    tail = terminal(data, op_rows)
    term, revolver = F(opening["term_principal"]), F(0)
    for index, operating in enumerate(op_rows):
        cash_interest = cash * F(data["pricing"]["cash_after_tax_return"])
        term_interest, line_interest = term * F(finance["term_coupon"]), revolver * F(finance["revolver_coupon"])
        term_repayment = F(finance["term_repayments"][index])
        closing_term = term - term_repayment
        before_financing = cash + cash_interest + operating["fcff"] - term_interest - line_interest - term_repayment
        row = {"year": index + 1, "date": data["dates"][index + 1], "opening_cash": cash,
               "cash_interest": cash_interest, "fcff": operating["fcff"], "opening_term": term,
               "opening_revolver": revolver, "term_interest": term_interest, "revolver_interest": line_interest,
               "term_repayment": term_repayment, "cash_before_line_or_takeout": before_financing,
               "closing_term": closing_term, "ebitda": operating["ebitda"]}
        if index < 2:
            covenant_limit = F(finance["gross_debt_ebitda_cap"]) * operating["ebitda"]
            line_limit = min(F(finance["revolver_commitment"]), covenant_limit - closing_term)
            required_line = max(F(0), revolver + cash_floor - before_financing)
            row.update({"gross_debt_limit": covenant_limit, "revolver_limit": line_limit,
                        "required_closing_revolver": required_line})
            if line_limit < 0 or required_line > line_limit:
                gap = required_line - max(F(0), line_limit)
                row.update({"funded": False, "cash_at_maximum_permitted_line": before_financing + max(F(0), line_limit) - revolver,
                            "cash_gap": gap, "reason": "Term debt or required revolving debt exceeds the supplied covenant/commitment"})
                result["rows"].append(row)
                result.update({"failure_year": index + 1, "cash_gap": gap, "reason": row["reason"]})
                return result
            closing_revolver, new_note = required_line, F(0)
            line_change = closing_revolver - revolver
            closing_cash = before_financing + line_change
            row.update({"revolver_net_draw": line_change, "revolver_maturity_repayment": F(0),
                        "closing_revolver": closing_revolver, "new_note_proceeds": new_note})
        else:
            before_takeout = before_financing - revolver
            note_limit = min(F(finance["replacement_note_cap"]), F(finance["gross_debt_ebitda_cap"]) * tail["ebitda"])
            required_note = max(F(0), cash_floor - before_takeout)
            row.update({"cash_after_old_debt_maturity": before_takeout, "replacement_note_limit": note_limit,
                        "required_replacement_note": required_note, "revolver_maturity_repayment": revolver})
            if required_note > note_limit:
                gap = required_note - note_limit
                row.update({"funded": False, "cash_at_maximum_permitted_note": before_takeout + note_limit,
                            "cash_gap": gap, "reason": "Explicit replacement commitment cannot fund old-debt maturity"})
                result["rows"].append(row)
                result.update({"failure_year": 3, "cash_gap": gap, "reason": row["reason"]})
                return result
            closing_revolver, new_note = F(0), required_note
            closing_cash = before_takeout + new_note
            row.update({"revolver_net_draw": F(0), "closing_revolver": closing_revolver, "new_note_proceeds": new_note})
        row.update({"funded": True, "closing_cash": closing_cash, "closing_total_debt": closing_term + closing_revolver + new_note})
        result["rows"].append(row)
        cash, term, revolver = closing_cash, closing_term, closing_revolver
    note = result["rows"][-1]["new_note_proceeds"]
    annual_coupon = note * F(finance["replacement_note_coupon"])
    # Pay any date3 cash above the floor before computing the steady cash account.
    steady_cash_income = cash_floor * F(data["pricing"]["cash_after_tax_return"])
    terminal_distribution = tail["fcff"] + steady_cash_income - annual_coupon
    need(terminal_distribution >= 0, "Replacement coupon fails the modeled continuing cash test")
    result.update({"funded": True, "date3_optional_cash_payout": cash - cash_floor,
                   "continuing_note_face": note, "continuing_annual_coupon": annual_coupon,
                   "year4_fcff": tail["fcff"], "steady_cash_interest": steady_cash_income,
                   "year4_cash_available_after_coupon": terminal_distribution,
                   "tail_test": "With nonnegative growth, fixed note coupons, cash kept at its minimum and no principal maturity, year4 is the smallest continuing operating cash flow."})
    return result


def peer_comparison(data):
    peers, qualified = [], []
    for p in data["peers"]["candidates"]:
        ev = F(p["equity"]) + F(p["debt"]) + F(p["nci"]) - F(p["cash"]) - F(p["nonoperating_asset"])
        normalized = F(p["reported_ebitda"]) + F(p["normalization_adjustment"])
        row = {"id": p["id"], "name": p["name"], "operating_ev": ev, "normalized_ebitda": normalized,
               "positive_profit_multiple": ev / normalized if normalized > 0 else None,
               "eligible": p["eligible"], "reason": p["reason"]}
        peers.append(row)
        if p["eligible"]:
            need(normalized > 0, "Eligible peer has nonpositive earnings")
            qualified.append(row)
    need(len(qualified) == 3, "Benchmark defines exactly three qualified peers")
    multiples = sorted(row["positive_profit_multiple"] for row in qualified)
    opening = data["opening"]
    bridge = F(opening["cash"]) + F(opening["nonoperating_asset_sale_value"]) - F(opening["term_market_value"])
    targets = {}
    for scenario in data["scenarios"]:
        ebitda = forecast(data, scenario)[0]["revenue"] * F(data["terminal"]["normalized_ebitda_margin"])
        evs = [m * ebitda for m in multiples]
        targets[scenario] = {"normalized_forward_year1_ebitda": ebitda, "operating_ev_low_median_high": evs,
                             "pre_action_equity_low_median_high": [v + bridge for v in evs],
                             "dcf_ev_to_matched_ebitda": valuation(data, scenario)["operating_enterprise_value"] / ebitda}
    return {"candidates": peers, "qualified_ids": [p["id"] for p in qualified],
            "low_median_high_multiples": multiples,
            "aggregate_ev_over_aggregate_ebitda": sum(p["operating_ev"] for p in qualified) / sum(p["normalized_ebitda"] for p in qualified),
            "targets": targets}


def thresholds(data):
    """First-year candidates; later-date feasibility is checked before use."""
    opening, finance = data["opening"], data["finance"]
    down = forecast(data, "downside")[0]
    J = F(data["benchmark_policy"]["new_equity"])
    accumulated = 1 + F(data["pricing"]["cash_after_tax_return"])
    terminal_term = F(opening["term_principal"]) - F(finance["term_repayments"][0])
    line_limit = min(F(finance["revolver_commitment"]), F(finance["gross_debt_ebitda_cap"]) * down["ebitda"] - terminal_term)
    need(line_limit >= 0, "Term debt alone violates the date1 cap")
    operating_after_debt = down["fcff"] - F(opening["term_principal"]) * F(finance["term_coupon"]) - F(finance["term_repayments"][0])
    required_opening_cash = (F(finance["minimum_cash"]) - operating_after_debt - line_limit) / accumulated
    with_sale = F(opening["cash"]) + F(opening["nonoperating_asset_sale_value"])
    min_equity = max(F(0), required_opening_cash - with_sale)
    payout = with_sale + J - required_opening_cash
    need(payout >= 0, "Benchmark has no initial payout capacity")
    need(all(treasury(data, s, new_equity=min_equity)["funded"] for s in data["scenarios"]), "Later date invalidates candidate equity threshold")
    need(all(treasury(data, s, initial_payout=payout)["funded"] for s in data["scenarios"]), "Later date invalidates candidate payout threshold")
    baseline = treasury(data, "downside")
    delay_limit = line_limit - baseline["rows"][0]["closing_revolver"]
    need(treasury(data, "downside", extra_nwc_year1=delay_limit)["funded"], "Later date invalidates collection-delay threshold")
    return {"downside_date1_line_limit": line_limit, "minimum_equity_with_asset_sale": min_equity,
            "minimum_equity_without_asset_sale": required_opening_cash - F(opening["cash"]),
            "maximum_initial_payout_with_equity70_and_sale": payout,
            "maximum_extra_downside_nwc_year1": delay_limit,
            "maximum_downside_nwc_year1": down["closing_nwc"] + delay_limit,
            "maximum_downside_nwc_sales_ratio_year1": (down["closing_nwc"] + delay_limit) / down["revenue"],
            "price_cap_nonnegative_in_both_forecasts": min(valuation(data, s)["maximum_seller_price_after_fee"] for s in data["scenarios"])}


def run(data):
    validate(data)
    values = {s: valuation(data, s) for s in data["scenarios"]}
    plans = {s: treasury(data, s) for s in data["scenarios"]}
    boundary = thresholds(data)
    rejected = {"no_sale_no_subscription": treasury(data, "downside", new_equity=0, sell_asset=False),
                "sale_only": treasury(data, "downside", new_equity=0),
                "equity70_without_asset_sale": treasury(data, "downside", sell_asset=False),
                "proposed_initial_payout20": treasury(data, "downside", initial_payout=F(data["offer"]["management_initial_payout"])),
                "collection_delay10": treasury(data, "downside", extra_nwc_year1=F(data["sensitivities"]["intervention_extra_downside_nwc_year1"]))}
    exact_boundaries = {"minimum_equity": {s: treasury(data, s, new_equity=boundary["minimum_equity_with_asset_sale"]) for s in data["scenarios"]},
                        "maximum_payout": {s: treasury(data, s, initial_payout=boundary["maximum_initial_payout_with_equity70_and_sale"]) for s in data["scenarios"]},
                        "maximum_collection_delay": treasury(data, "downside", extra_nwc_year1=boundary["maximum_extra_downside_nwc_year1"])}
    grids = {}
    for scenario in data["scenarios"]:
        grids[scenario] = [{"r": F(r), "g": F(g), "buyer_npv": valuation(data, scenario, r, g)["buyer_npv"]}
                           for r in data["sensitivities"]["operating_returns"] for g in data["sensitivities"]["terminal_growth"]]
    intervention_R = F(data["sensitivities"]["intervention_terminal_roic"])
    return encode({"case": data["case"], "amount_format": "Exact rational strings in kCU unless labeled as rates, shares or multiples",
                   "valuation": values, "funded_benchmark_policies": plans, "peers": peer_comparison(data),
                   "thresholds": boundary, "threshold_policies": exact_boundaries, "rejected_policies": rejected,
                   "r_g_sensitivity": grids, "terminal_roic_intervention": {s: valuation(data, s, roic=intervention_R)["buyer_npv"] for s in data["scenarios"]},
                   "decision_scope": "No probabilities supplied. A rule requiring nonnegative value in both listed forecasts uses the lower price cap; funded does not mean valuable, and two forecasts do not exhaust risk."})


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v08-assessment-inputs.json")
    need(len(sys.argv) <= 2, "Usage: python3 v08-assessment-analysis.py [inputs.json]")
    data = json.loads(source.read_text(encoding="utf-8"))
    print(json.dumps(run(data), indent=2, ensure_ascii=False, allow_nan=False))
