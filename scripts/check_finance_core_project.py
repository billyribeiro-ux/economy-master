"""Independent original-contract checks for the Cedar Reserve finance-core project."""
import argparse
import contextlib
import copy
from fractions import Fraction as F
from html.parser import HTMLParser
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "finance-core"
OWNED = (
    "content/cross-assessments/parts/finance-core-project.html",
    "content/projects/finance-core-inputs.json",
    "content/projects/finance-core-analysis.py",
    "content/projects/finance-core-output.json",
    "content/projects/finance-core-manifest.json",
    "content/projects/finance-core-README.txt",
    "scripts/check_finance_core_project.py",
    "content/reviews/finance-core-project-author.json",
    "content/reviews/finance-core-project-sources.json")
PI = (F(1, 5), F(3, 10), F(2, 5))


def require(ok, label):
    if not ok:
        raise ValueError("finance-core project check: " + label)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0
        self.policy_rows = 0
        self.journal_rows = 0
        self.printed = 0
        self.alias_refusals = 0
        self.cli_rejections = 0
        self.portable_runs = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if type(expected) is bool:
            require(type(actual) is bool and actual == expected, label + ": boolean mismatch")
        elif isinstance(expected, F):
            require(type(actual) in (int, float, F) and math.isfinite(actual) and
                    math.isclose(actual, float(expected), rel_tol=2e-13, abs_tol=2e-13),
                    label + ": " + repr(actual) + " != " + str(expected))
        else:
            require(actual == expected, label + ": " + repr(actual) + " != " + repr(expected))

    def values(self, actual, expected, label):
        self.eq(len(actual), len(expected), label + " length")
        for index, (a, b) in enumerate(zip(actual, expected)):
            self.eq(a, b, label + "[" + str(index) + "]")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.points = {}
        self.sources = {}
        self.links = []
        self.solutions = {}
        self.active = None
        self.tables = {}
        self.table = None
        self.row = None
        self.cell = None
        self.headings = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag in ("h1", "h2", "h3", "h4"):
            self.headings.append((tag, a.get("id")))
        if tag == "li" and "data-points" in a:
            require(a.get("id") not in self.points, "unique scored prompt")
            self.points[a["id"]] = int(a["data-points"])
        if tag == "a":
            self.links.append(a.get("href", ""))
            if a.get("data-source"):
                self.sources[a["data-source"]] = a["href"]
        if tag == "details" and "solution" in a.get("class", "").split():
            require(self.active is None and a.get("data-solution-for"), "paired nonnested solution")
            self.active = a["data-solution-for"]
            require(self.active not in self.solutions, "one solution per prompt")
            self.solutions[self.active] = ""
        if tag == "table" and a.get("id"):
            self.table = a["id"]
            self.tables[self.table] = []
        if tag == "tr" and self.table:
            self.row = []
        if tag in ("td", "th") and self.table:
            self.cell = ""
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, "balanced HTML " + tag)
        self.stack.pop()
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        if tag == "tr" and self.table:
            self.tables[self.table].append(self.row)
            self.row = None
        if tag == "table":
            self.table = None
        if tag == "details":
            self.active = None

    def handle_data(self, data):
        self.text.append(data)
        if self.active:
            self.solutions[self.active] += data
        if self.cell is not None:
            self.cell += data


def price(values):
    return sum(p*x for p, x in zip(PI, values))


def loss_oracle(capital, p):
    losses = [F(64, 9)-x for x in capital]
    # Different algorithm from the model: convex threshold minimization.
    es = min(z + 10*sum(w*max(F(0), loss-z) for w, loss in zip(p, losses))
             for z in set(losses))
    var = min(z for z in set(losses) if sum(w for w, loss in zip(p, losses) if loss <= z) >= F(9, 10))
    return losses, sum(w*l for w, l in zip(p, losses)), var, es


def oracle(data):
    """Direct payoff/cutoff equations, independent of all author functions."""
    e = data["experiment"]
    delta = F(str(e["down_revenue_loss"]))
    senior = F(str(e["escrow_senior_claim"]))
    p = [F(str(x)) for x in e["physical_probabilities"]]
    pre = e["information"] == "before_trade"
    q = F(41)-delta/5 if pre else F(41)
    equity_cash = 50-q
    equity_share = equity_cash/19
    states = (30-delta, F(60), F(90))
    debt = [min(F(50), x) for x in states]
    equity = [max(F(0), x-50) for x in states]
    rows = []
    for x in (F(1, 2), F(3, 4), F(1)):
        for kind, h in (("none", F(0)), ("credit", x/2), ("credit", x), ("escrow", x/2), ("escrow", x)):
            fees = x/10+(2*h/5 if kind == "escrow" else 0)
            premium = (4 if kind == "escrow" else F(12, 5) if kind == "credit" else 0)*h
            b = 64-q*x-premium-fees
            cash09 = b*F(10, 9)-20
            require(cash09 >= 0, "all supported policies meet first payment")
            capitals, misses, arrears = [], [], []
            raw12s, lates, paid12s, cures, closes = [], [], [], [], []
            for i, n in enumerate(debt):
                payoff = (20-senior if kind == "escrow" else 12 if kind == "credit" else 0)*h if i == 0 else F(0)
                timely_hedge = payoff if kind == "escrow" and e["escrow_settlement"] == "12:00" else F(0)
                late = payoff-timely_hedge
                raw12 = cash09+x*n+timely_hedge
                paid12 = min(F(44), raw12)
                missed = 44-paid12
                final_resources = max(F(0), raw12-44)+late
                cure = min(missed, final_resources)
                unpaid = missed-cure
                closing = final_resources-cure
                # Algebraic terminal identity checked against actual payment/cure.
                capital = b*F(10, 9)+x*n+payoff-64
                require(capital == closing-unpaid, "payoff and actual-claim identity")
                capitals.append(capital); misses.append(missed); arrears.append(unpaid)
                raw12s.append(raw12); lates.append(late); paid12s.append(paid12)
                cures.append(cure); closes.append(closing)
            eligible = max(misses) == 0 and min(capitals) >= 2
            row = {"id": str(x)+"-"+kind+"-"+str(h), "x": x, "h": h, "kind": kind,
                   "b": b, "q": q, "fees": fees, "premium": premium, "cash09": cash09,
                   "capital": capitals, "misses": misses, "arrears": arrears,
                   "raw12": raw12s, "late": lates, "paid12": paid12s,
                   "cures": cures, "closes": closes, "eligible": eligible,
                   "mean": sum(w*z for w, z in zip(p, capitals)), "risk": loss_oracle(capitals, p)}
            rows.append(row)
    winners = sorted((r for r in rows if r["eligible"]), key=lambda r: (-r["mean"], r["x"], r["h"], r["kind"]))
    fixed = next(r for r in rows if r["id"] == "1/2-escrow-1/4")
    shown = winners[0] if winners else fixed
    after = not pre and (delta > 0 or senior > 0 or e["escrow_settlement"] == "16:00")
    return {"rows": rows, "winners": winners, "shown": shown, "fixed": fixed,
            "after": after, "q": q, "delta": delta, "senior": senior, "p": p,
            "debt": debt, "equity": equity, "states": states,
            "equity_cash": equity_cash, "equity_share": equity_share}


def load_model(path):
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("cedar_under_test", path)
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            spec.loader.exec_module(module)
        require(out.getvalue() == err.getvalue() == "", "quiet import")
        return module
    finally:
        sys.dont_write_bytecode = old


def call(a, module, data):
    before = copy.deepcopy(data)
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        result = module.run(data)
    a.eq(out.getvalue(), "", "quiet API stdout")
    a.eq(err.getvalue(), "", "quiet API stderr")
    a.eq(data, before, "API input nonmutation")
    a.eq(json.loads(json.dumps(result, allow_nan=False)), result, "strict JSON round trip")
    return result


def audit_result(a, data, result, label):
    expected = oracle(data)
    e = data["experiment"]
    collection = F(str(e["historical_collections"]))
    p = result["parent"]
    a.eq(p["income"], 10, label+" accrual income")
    for field in ("direct_cfo", "indirect_cfo"):
        a.eq(p[field], collection-75, label+" "+field)
    closes = {"cash": collection-65, "receivables": 120-collection, "inventory": 20,
              "ppe": 50, "payables": 15, "debt": 40, "equity": 70}
    for field, value in closes.items():
        a.eq(p["closing"][field], value, label+" closing "+field)
    a.eq(p["assets"], 125, label+" parent assets")
    a.eq(p["liabilities_and_equity"], 125, label+" parent balance")
    a.eq(p["cash_after_paying_all_ap"], collection-80, label+" AP settlement")
    a.eq(p["operating_reserve_gap"], 90-collection, label+" parent gap")
    parent_ok = collection == 90
    a.eq(p["parent_gate"], parent_ok, label+" parent gate")
    j = result["project_claims"]
    for key, values in {"sales_cash": [50-expected["delta"], 80, 110],
                        "operating_income": [-20-expected["delta"], 10, 40],
                        "estate": expected["states"], "note_paid": expected["debt"],
                        "note_unpaid_nominal": [50-x for x in expected["debt"]],
                        "equity_paid": expected["equity"],
                        "pre_resolution_book_equity": [-20-expected["delta"], 10, 40]}.items():
        a.values(j[key], values, label+" "+key)
    for key, value in {"current_asset_pv": price(expected["states"]), "current_note_pv": price(expected["debt"]),
                       "equity_pv": F(19), "current_unfunded_opportunity_npv": 10-expected["delta"]/5,
                       "entry_note_proceeds": expected["q"], "new_equity_cash": expected["equity_cash"],
                       "new_equity_share": expected["equity_share"], "parent_equity_share": 1-expected["equity_share"],
                       "entry_note_discount": 50-expected["q"]}.items():
        a.eq(j[key], value, label+" "+key)
    a.eq(j["protection_current_pvs"]["escrow"], (20-expected["senior"])/5, label+" current priority mark")
    a.eq(j["protection_current_pvs"]["credit"], F(12, 5), label+" delivered recovery price")
    a.eq(len(result["policies"]), 15, label+" complete menu")
    for got, want in zip(result["policies"], expected["rows"]):
        a.policy_rows += 1
        for key, target in (("id", "id"), ("note_fraction", "x"), ("kind", "kind"), ("hedge_fraction", "h"),
                            ("entry_fees", "fees"), ("bill_purchase", "b"), ("cash_after09", "cash09"),
                            ("physical_mean_capital", "mean"), ("eligible", "eligible")):
            a.eq(got[key], want[target], label+" "+want["id"]+" "+key)
        for key, target in (("net_capital_by_state", "capital"), ("missed_at_deadline_by_state", "misses"),
                            ("client_unpaid_by_state", "arrears")):
            a.values(got[key], want[target], label+" "+want["id"]+" "+key)
        a.eq(got["timely"], max(want["misses"]) == 0, label+" timed feasibility")
        a.eq(got["capital_floor_met"], min(want["capital"]) >= 2, label+" capital separately")
        risk = got["risk"]
        a.values(risk["loss_by_state"], want["risk"][0], label+" loss definition")
        for key, value in zip(("mean_loss", "var", "es"), want["risk"][1:]):
            a.eq(risk[key], value, label+" independent threshold "+key)
    best = expected["winners"][0] if expected["winners"] else None
    a.eq(result["eligible_policy_ids"], [r["id"] for r in expected["winners"]], label+" finite ranking")
    a.eq(result["selected_policy"], best["id"] if best else None, label+" finite optimum")
    a.eq(result["comparison_scope"], "historical_entry_counterfactuals" if expected["after"] else "prospective_entry", label+" information scope")
    a.eq(result["menu_has_feasible_policy"], best is not None, label+" counterfactual feasibility")
    a.eq(result["prospective_entry_approval"], None if expected["after"] else parent_ok and best is not None, label+" no invented post-trade authorization")
    a.eq(result["institution_approval"], parent_ok and (expected["fixed"]["eligible"] if expected["after"] else best is not None), label+" actual funded holdings")
    if expected["after"]:
        actual = result["actual_after_trade_position"]
        a.eq(actual["id"], expected["fixed"]["id"], label+" unchanged original position")
        a.eq(actual["eligible"], expected["fixed"]["eligible"], label+" original position gate")
        a.values(actual["net_capital_by_state"], expected["fixed"]["capital"], label+" no refund")
        a.values(actual["missed_at_deadline_by_state"], expected["fixed"]["misses"], label+" actual deadline failures")
    else:
        a.eq(result["actual_after_trade_position"], None, label+" prospective entry")
    shown = expected["shown"]
    a.eq(result["shown_policy"], shown["id"], label+" displayed contract")
    a.eq(result["exact"]["selected_mean"], str(best["mean"]) if best else None, label+" exact objective")
    a.eq(result["exact"]["shown_net_capital"], list(map(str, shown["capital"])), label+" exact capital fractions")
    a.eq(result["exact"]["shown_terminal_net_pv"], str(price(shown["capital"])), label+" exact residual value")
    a.eq(result["exact"]["shown_es90"], str(shown["risk"][3]), label+" exact ES")
    cert = result["fixed_position_reverse_certificate"]
    if expected["senior"] or e["escrow_settlement"] != "12:00":
        a.eq(cert, None, label+" compound shock has no one-variable certificate")
    else:
        slope = F(7, 18) if e["information"] == "before_trade" else F(1, 2)
        a.eq(cert["capital_floor_boundary"], str((F(55, 18)-2)/slope), label+" exact reverse boundary")
        a.eq(cert["bad_capital_shock_slope"], str(-slope), label+" information-specific slope")
        a.eq(cert["boundary_is_inclusive"], True, label+" weak floor equality")
    audit_allocations(a, data, result, expected, label)
    return expected


def audit_allocations(a, data, result, expected, label):
    r = expected["shown"]
    x, h, kind, q = r["x"], r["h"], r["kind"], expected["q"]
    # Reconstruct t0 recipient funding without importing the model's transfer helper.
    flows = [("client_payer", "reserve", F(288, 5)), ("sponsor", "reserve", F(32, 5)),
             ("reserve", "spv", x*q), ("note_underwriter", "spv", (1-x)*q),
             ("equity_subscriber", "spv", 50-q), ("spv", "equipment_seller", F(30)),
             ("spv", "inventory_supplier", F(20)), ("reserve", "dealer", r["premium"]),
             ("reserve", "fee_provider", r["fees"]), ("reserve", "bill_issuer", r["b"])]
    endowed = {"reserve": F(0), "client_payer": F(60), "sponsor": F(10), "note_underwriter": F(50),
               "equity_subscriber": F(20), "dealer": F(0), "fee_provider": F(0), "bill_issuer": F(100),
               "spv": F(0), "equipment_seller": F(0), "inventory_supplier": F(0), "escrow_pool": F(20), "credit_pool": F(12)}
    for got, (payer, recipient, cash) in zip(result["entry"]["transfers"], flows):
        a.eq((got["payer"], got["recipient"]), (payer, recipient), label+" actual payer/recipient")
        a.eq(got["cash"], cash, label+" actual entry cash")
        endowed[payer] -= cash; endowed[recipient] += cash
        a.eq(endowed[payer] >= 0, True, label+" funded payer prefix")
    a.eq(len(result["entry"]["transfers"]), len(flows), label+" complete entry transfer list")
    for name, cash in endowed.items():
        a.eq(result["entry"]["remaining_cash"][name], cash, label+" retained "+name)
    a.eq(result["entry"]["cash_sum_before"], 272, label+" modeled endowments")
    a.eq(result["entry"]["cash_sum_after"], 272, label+" modeled entry conservation")
    a.eq(result["entry"]["dealer_after_sale_cash_plus_reference_claim_value"], F(32, 5), label+" dealer claim transfer")
    for i, state in enumerate(("down", "normal", "up")):
        a.eq(result["shown_reserve_states"][i]["state"], state, label+" state order")
        actual = result["shown_reserve_states"][i]
        n = expected["debt"][i]
        escrow = h*(20-expected["senior"]) if kind == "escrow" and i == 0 else F(0)
        esctimely = escrow if data["experiment"]["escrow_settlement"] == "12:00" else F(0)
        events = [("09:00", "bill_redemption", r["b"]*F(10, 9), F(0), F(0)),
                  ("09:00", "first_client_payment", F(0), F(20), F(20)),
                  ("12:00", "project_note_receipt", x*n, F(0), F(0))]
        if kind == "escrow" and data["experiment"]["escrow_settlement"] == "12:00":
            events.append(("12:00", "escrow_receipt", esctimely, F(0), F(0)))
        events.append(("12:00", "second_client_payment", F(0), r["paid12"][i], F(44)))
        if kind != "none":
            events.append(("16:00", "late_protection_receipt", r["late"][i], F(0), F(0)))
        events.append(("16:00", "late_client_cure", F(0), r["cures"][i], F(0)))
        a.eq(len(actual["journal"]), len(events), label+" every event")
        cash = F(0); nominal = F(0)
        for got, (time, event, receipt, paid, new_due) in zip(actual["journal"], events):
            cash += receipt-paid
            nominal += new_due-paid
            a.journal_rows += 1
            a.eq((got["time"], got["event"]), (time, event), label+" execution order")
            for key, value in (("receipt", receipt), ("payment", paid), ("new_client_due", new_due), ("cash", cash), ("client_arrears", nominal)):
                a.eq(got[key], value, label+" event "+key)
        for field, value in {"paid09": F(20), "paid12": r["paid12"][i], "missed_at_deadline": r["misses"][i],
                             "late_cure": r["cures"][i], "terminal_cash": r["closes"][i],
                             "client_unpaid_nominal": r["arrears"][i], "terminal_net_capital": r["capital"][i]}.items():
            a.eq(actual[field], value, label+" actual "+field)
        allocations = result["shown_terminal_allocations"][i]
        spv = allocations["spv_cash"]
        customer = (50-expected["delta"], F(80), F(110))[i]
        for key, value in {"customer_receipt": customer, "equipment_buyer_receipt": F(10), "operating_payee": F(30),
                           "cedar_note": x*n, "underwriter_note": (1-x)*n,
                           "new_equity_holder": expected["equity_share"]*expected["equity"][i],
                           "parent_shareholder": (1-expected["equity_share"])*expected["equity"][i],
                           "ending_cash": F(0), "cedar_note_unpaid_nominal": x*(50-n),
                           "underwriter_note_unpaid_nominal": (1-x)*(50-n)}.items():
            a.eq(spv[key], value, label+" SPV recipient "+key)
        a.eq(sum(spv[k] for k in ("operating_payee", "cedar_note", "underwriter_note", "new_equity_holder", "parent_shareholder")), customer+10, label+" complete SPV resource identity")
        for pool_kind, endowment in (("escrow", F(20)), ("credit", F(12))):
            senior = expected["senior"] if pool_kind == "escrow" else F(0)
            fraction = h if kind == pool_kind else F(0)
            payoff = endowment-senior if i == 0 else F(0)
            row = allocations[pool_kind+"_pool"]
            a.eq(row["settlement"], data["experiment"]["escrow_settlement"] if pool_kind == "escrow" else "16:00", label+" pool release cutoff")
            if pool_kind == "escrow":
                a.eq(row["senior_paid"], senior, label+" senior paid in every state")
            for key, value in {"cedar_paid": fraction*payoff, "dealer_paid": (1-fraction)*payoff,
                               "writer_cash_return": endowment-senior-payoff,
                               "cedar_unpaid_nominal": fraction*(20-payoff) if i == 0 else F(0),
                               "dealer_unpaid_nominal": (1-fraction)*(20-payoff) if i == 0 else F(0)}.items():
                a.eq(row[key], value, label+" "+pool_kind+" "+key)
            a.eq(row["cedar_paid"]+row["dealer_paid"]+row["writer_cash_return"]+float(senior), endowment, label+" separate pool conservation")
        a.eq(allocations["bill_issuer_after_redemption"], 100+r["b"]-r["b"]*F(10, 9), label+" funded bill issuer")


def solve(matrix, rhs):
    rows = [[F(x) for x in row]+[F(y)] for row, y in zip(matrix, rhs)]
    n = len(rows)
    for col in range(n):
        pivot = next(i for i in range(col, n) if rows[i][col])
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [x/scale for x in rows[col]]
        for i in range(n):
            if i != col:
                multiple = rows[i][col]
                rows[i] = [x-multiple*y for x, y in zip(rows[i], rows[col])]
    return [row[-1] for row in rows]


def manuscript_and_proofs(a, data, page):
    a.eq(page.stack, [], "complete HTML fragment")
    a.eq(len(page.ids), len(set(page.ids)), "unique IDs")
    a.eq([p for p in page.headings if p[0] == "h1"], [], "fragment no h1")
    a.eq([p for p in page.headings if p[0] == "h2"], [("h2", "project")], "project root heading")
    a.eq(all(x == "project" or x.startswith("finance-core-project-") for x in page.ids), True, "owned ID prefix")
    targets = ["finance-core-project-d"+str(i) for i in range(1, 6)]+["finance-core-project-t"+str(i) for i in range(1, 7)]
    a.eq(set(page.solutions), set(targets), "all eleven exact tasks answered")
    a.eq(page.points, {x:20 for x in targets[:5]}, "five essential twenty-point tasks")
    for target in targets:
        a.eq(target in page.ids and len(page.solutions[target]) > 500, True, "substantial paired answer "+target)
    sources = json.loads((ROOT/OWNED[8]).read_text())
    a.eq(page.sources, {x["id"]:x["url"] for x in sources["reuse"]}, "scoped source links")
    a.eq(len(page.sources), 8, "eight reused primary scopes")
    for suffix in ("inputs.json", "analysis.py", "output.json", "manifest.json", "README.txt"):
        a.eq(PREFIX+"-"+suffix in page.links, True, "flat payload link "+suffix)
    a.eq(all(not link.startswith(("../", "content/", "dist/")) for link in page.links), True, "flat reader paths")

    def printed(section, *values):
        body = page.solutions["finance-core-project-"+section]
        for value in values:
            token = str(value).replace("-", "−")
            a.eq(token in body, True, "visible exact anchor "+section+" "+token)
            a.printed += 1

    base = oracle(data)
    policy_table = page.tables["finance-core-project-policy-table"][1:]
    a.eq(len(policy_table), 15, "all printed policy rows")
    for cells, row in zip(policy_table, base["rows"]):
        expected_cells = [str(row["x"]), row["kind"], str(row["h"]), str(row["b"]), str(row["capital"][0]),
                          str(row["capital"][1]), str(row["mean"]), "Yes" if row["eligible"] else "No"]
        a.eq([s.replace("−", "-") for s in cells], expected_cells, "every printed cell "+row["id"])
        a.printed += len(cells)
    winner = base["shown"]
    cash_table = page.tables["finance-core-project-cash-table"][1:]
    a.eq(len(cash_table), 6, "six printed cutoff rows")
    bad = [winner["b"]*F(10, 9), winner["cash09"], winner["cash09"]+15,
           winner["raw12"][0], winner["capital"][0], winner["capital"][0]]
    good = [winner["b"]*F(10, 9), winner["cash09"], winner["cash09"]+25,
            winner["raw12"][1], winner["capital"][1], winner["capital"][1]]
    for cells, b, g in zip(cash_table, bad, good):
        a.eq(cells[1:], [str(b), str(g)], "printed dated balances")
        a.printed += 2
    # Account and ownership identities, rather than a list copied from output.
    a.eq(10+90-55-20, 25, "historical cash")
    a.eq(10+10-(30-20)-(20-30)+(15-20), 15, "historical indirect cash")
    a.eq(F(9, 19)*19+F(10, 19)*19, 19, "equity ownership partition")
    a.eq(F(41)+9, 50, "actual issue cash")
    a.eq(50*F(9, 10)-41, 4, "escrow reference replication cost")
    for estate, debt, equity in zip(base["states"], base["debt"], base["equity"]):
        a.eq(debt+equity, estate, "state claim partition")
        a.eq(50-debt, 20 if estate == 30 else 0, "replication on exactly baseline support")
    a.eq(20*40-20*10, 600, "payoff basis determinant")
    printed("d2", F(9, 19), F(10, 19), F(41, 2), F(59, 2), F(90, 19), F(360, 19), F(100, 19), F(400, 19))
    printed("d3", F(46, 73), winner["mean"], winner["mean"]-F(41, 6), F(3, 20), F(1, 20), F(1, 10),
            F(32, 5), price(winner["capital"]), F(288, 5), F(64, 9), *winner["risk"][0][:2], *winner["risk"][1:])
    for x in (F(1, 2), F(3, 4), F(1)):
        by = {(r["kind"], r["h"]): r for r in base["rows"] if r["x"] == x}
        a.eq(by[("none", F(0))]["capital"][0], (64-141*x)/9, "unhedged impossibility formula")
        a.eq(by[("escrow", x/2)]["capital"][0], (64-73*x)/9, "half-escrow floor formula")
        a.eq(by[("escrow", x)]["capital"][0], (64-5*x)/9, "full-escrow monotonicity formula")
    reject = next(r for r in base["rows"] if r["id"] == "1/2-credit-1/2")
    printed("d4", reject["capital"][0], reject["raw12"][0], reject["misses"][0])
    # Exact reverse boundaries and the distinction between a floor and payment.
    after_boundary = (F(55, 18)-2)/F(1, 2)
    before_boundary = (F(55, 18)-2)/F(7, 18)
    a.eq(F(55, 18)-after_boundary/2, F(2), "after boundary equality")
    a.eq(F(55, 18)-F(7, 18)*before_boundary, F(2), "before boundary equality")
    a.eq(F(55, 18)-F(55, 9)/2, F(0), "payment boundary later than capital")
    a.eq(after_boundary < F(55, 9), True, "first binding constraint")
    printed("d4", after_boundary, F(55, 9))
    d = F(5, 2)
    old_after = F(55, 18)-d/2
    old_before = F(55, 18)-7*d/18
    after_full = F(41, 6)-d/2
    mean_full = after_full/20+F(19, 20)*F(41, 6)
    before_good = F(145, 18)+d/9
    before_mean = old_before/20+F(19, 20)*before_good
    printed("t2", after_boundary, old_after, after_full, F(41, 6), mean_full, before_boundary,
            41-d/5, 60-d/5, 9+d/5, F(1, 2), F(213, 5), F(82, 3), old_before, before_good, before_mean, 20+d)
    switch = (F(145, 18)-F(41, 6))/5
    a.eq(F(145, 18)-5*switch, F(41, 6), "physical tie exact algebra")
    a.eq(switch, F(11, 45), "exact physical switch")
    printed("t3", F(3, 10)*F(55, 18)+F(7, 10)*F(145, 18), F(41, 6), switch)
    bridge = 44-(winner["cash09"]+15)
    a.eq(bridge <= 2, True, "independently endowed bridge capacity")
    a.eq(5-bridge, F(55, 18), "late receipt funds bridge and leaves original residual")
    printed("t4", winner["cash09"]+15, bridge, 2-bridge, F(55, 18))
    priority_bad = F(55, 18)-F(5, 4)
    priority_mean = priority_bad/20+F(19, 20)*F(145, 18)
    full_bad = F(41, 6)-F(5, 2)
    full_mean = full_bad/20+F(19, 20)*F(41, 6)
    printed("t5", F(15, 4), F(45, 4), F(5, 4), priority_bad, priority_mean,
            full_bad, full_mean, F(59, 9)-5, F(15, 2), F(5, 2))
    a.eq(F(5)+F(15, 4)+F(45, 4), F(20), "actual senior-discovery pool")
    a.eq(F(5)+F(15, 2)+F(15, 2), F(20), "counterfactual half pool")

    # Independent elimination gives the entire affine four-state family.
    matrix = [[1, 1, 1], [30, 50, 50], [0, 10, 40]]
    intercept = solve(matrix, [F(9, 10), 41, 19])
    at_one = solve(matrix, [F(9, 10)-1, 41-10, 19])
    slope = [b-c for b, c in zip(at_one, intercept)]
    a.eq(intercept, [F(1, 5), F(3, 10), F(2, 5)], "four-state family intercept by elimination")
    a.eq(slope, [F(-2), F(4, 3), F(-1, 3)], "four-state family slope by elimination")
    a.eq(min(-v/s for v, s in zip(intercept, slope) if s < 0), F(1, 10), "strict positive upper endpoint")
    for t in (F(1, 100), F(1, 20), F(9, 100)):
        pi = [t]+[v+s*t for v, s in zip(intercept, slope)]
        for pay, cost in (([1, 1, 1, 1], F(9, 10)), ([10, 30, 50, 50], F(41)), ([0, 0, 10, 40], F(19))):
            a.eq(sum(w*y for w, y in zip(pi, pay)), cost, "complete four-state price constraints")
        a.eq(min(pi)>0, True, "strict positive extension")
        a.eq(20*(pi[0]+pi[1]), 4-20*t, "nonunique capped claim price")
    note = [10, 30, 50, 50]
    claim = [20, 20, 0, 0]
    lower = [25-F(n, 2) for n in note]
    upper = [50-n for n in note]
    a.eq([h-l for h, l in zip(claim, lower)], [0, 10, 0, 0], "excluded lower endpoint arbitrage")
    a.eq([u-h for u, h in zip(upper, claim)], [20, 0, 0, 0], "excluded upper endpoint arbitrage")
    a.eq(25*F(9, 10)-F(41, 2), F(2), "lower hedge price")
    a.eq(50*F(9, 10)-41, F(4), "upper hedge price")
    printed("t6", F(1, 10), F(1, 20), F(11, 30), F(23, 60))
    a.eq("(2,4)" in page.solutions["finance-core-project-t6"], True, "visible open endpoints")
    a.eq("(0,10,0,0)" in page.solutions["finance-core-project-t6"], True, "visible lower endpoint witness")
    a.eq("(20,0,0,0)" in page.solutions["finance-core-project-t6"], True, "visible upper endpoint witness")


def domain_checks(a, module, data):
    def reject(value, label):
        before = copy.deepcopy(value)
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            try:
                module.run(value)
            except ValueError:
                a.rejections += 1
            else:
                raise ValueError("accepted unsupported API input: "+label)
        a.eq(out.getvalue()+err.getvalue(), "", "quiet rejection "+label)
        # NaN does not compare equal to itself; identity shape is checked through repr.
        a.eq(repr(value), repr(before), "rejection nonmutation "+label)
    for value in (None, [], True, "{}"):
        reject(value, "root type")
    def change(path, value):
        d = copy.deepcopy(data)
        target = d
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return d
    invalid = [(("schema",), True), (("schema",), 2), (("case",), "other"),
               (("provenance",), ""), (("provenance",), "x"*513),
               (("contract", "project", "note_face"), 51),
               (("contract", "market", "state_prices"), [.2, .3, .5]),
               (("contract", "terminal_cutoffs"), ["09:00", "13:00", "16:00"]),
               (("contract", "reserve", "note_fractions"), [.25, .5, 1]),
               (("contract", "providers", "escrow_pool_cash"), True),
               (("experiment", "historical_collections"), 79.99),
               (("experiment", "historical_collections"), 90.01),
               (("experiment", "historical_collections"), "90"),
               (("experiment", "down_revenue_loss"), -1),
               (("experiment", "down_revenue_loss"), 10.01),
               (("experiment", "down_revenue_loss"), True),
               (("experiment", "down_revenue_loss"), float("nan")),
               (("experiment", "down_revenue_loss"), float("inf")),
               (("experiment", "down_revenue_loss"), 10**100),
               (("experiment", "down_revenue_loss"), 0.0000000000001),
               (("experiment", "information"), "same_quotes_but_new_cash"),
               (("experiment", "physical_probabilities"), [.1, .2, .6]),
               (("experiment", "physical_probabilities"), [0, .6, .4]),
               (("experiment", "physical_probabilities"), [True, 0, 0]),
               (("experiment", "physical_probabilities"), [.05, .55, .4, 0]),
               (("experiment", "physical_probabilities"), (.05, .55, .4)),
               (("experiment", "escrow_settlement"), "09:00"),
               (("experiment", "escrow_senior_claim"), -1),
               (("experiment", "escrow_senior_claim"), 5.01)]
    for path, value in invalid:
        reject(change(path, value), ".".join(path))
    for section in (None, "contract", "experiment"):
        d = copy.deepcopy(data); target = d if section is None else d[section]
        target["extra"] = 1
        reject(d, "undeclared field")
        d = copy.deepcopy(data); target = d if section is None else d[section]
        del target[next(iter(target))]
        reject(d, "missing field")
    for field, value in (("escrow_settlement", "16:00"), ("escrow_senior_claim", 1)):
        d = change(("experiment", "information"), "before_trade")
        d["experiment"][field] = value
        reject(d, "unsupported before-trade combined information")


def file_hash(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def binding_checks(a):
    manifest = json.loads((ROOT/OWNED[4]).read_text())
    files = {x["file"]:x for x in manifest["files"]}
    names = [Path(OWNED[i]).name for i in (1, 2, 3, 5)]
    a.eq(set(files), set(names), "exact four manifested payloads")
    for name in names:
        actual = file_hash(ROOT/"content/projects"/name)
        a.eq({k:files[name][k] for k in actual}, actual, "manifest "+name)
    author = json.loads((ROOT/OWNED[7]).read_text())
    binds = {x["path"]:x for x in author["reviewed_hashes"]}
    expected = set(OWNED)-{OWNED[7]}
    a.eq(len(author["reviewed_hashes"]), 8, "eight nonself author bindings")
    a.eq(set(binds), expected, "exact author payload set")
    for path in expected:
        actual = file_hash(ROOT/path)
        a.eq({k:binds[path][k] for k in actual}, actual, "author binding "+path)


def portable_and_safety(a, baseline):
    with tempfile.TemporaryDirectory(prefix="cedar-proof-") as raw:
        temp = Path(raw)
        package = temp/"book"
        for relative in OWNED:
            target = package/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/relative, target)
        working = temp/"unrelated"
        working.mkdir()
        model = package/OWNED[2]
        source_input = package/OWNED[1]
        script = package/OWNED[6]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for flags in ([], ["-O"]):
            # Real default and explicit file writes occur only in the disposable copy.
            for args, target in (([], package/OWNED[3]), (["--input", str(source_input), "--output", str(working/"explicit.json")], working/"explicit.json")):
                completed = subprocess.run([sys.executable]+flags+[str(model)]+args, cwd=working, env=env,
                                           capture_output=True, text=True, timeout=20)
                a.eq((completed.returncode, completed.stdout, completed.stderr), (0, "", ""), "quiet portable model CLI")
                a.eq(json.loads(target.read_text()), baseline, "portable CLI exact baseline")
                a.portable_runs += 1
            probe = ("import importlib.util,json;"
                     "s=importlib.util.spec_from_file_location('proof',"+repr(str(model))+");"
                     "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                     "d=json.load(open("+repr(str(source_input))+"));"
                     "r=m.run(d);"
                     "open("+repr(str(working/"api.json"))+",'w').write(json.dumps(r,allow_nan=False))")
            completed = subprocess.run([sys.executable]+flags+["-c", probe], cwd=working, env=env,
                                       capture_output=True, text=True, timeout=20)
            a.eq((completed.returncode, completed.stdout, completed.stderr), (0, "", ""), "quiet isolated API")
            a.eq(json.loads((working/"api.json").read_text()), baseline, "isolated API baseline")
            a.portable_runs += 1
            completed = subprocess.run([sys.executable]+flags+[str(script), "--no-isolation"], cwd=working, env=env,
                                       capture_output=True, text=True, timeout=30)
            a.eq(completed.returncode, 0, "exact nine-file checker isolation: "+completed.stderr)
            a.eq(completed.stderr, "", "isolated checker stderr")
            a.eq(json.loads(completed.stdout)["status"], "passed", "isolated checker strict summary")
            a.portable_runs += 1
        # Direct, normalized, symlink and hardlink attempts; hash every protected
        # payload before/after, including actual output aliases supplied to a process.
        protected = [package/p for p in OWNED if p != OWNED[3]]
        custom_input = working/"custom-input.json"
        shutil.copy2(source_input, custom_input)
        protected.append(custom_input)
        original = {p: p.read_bytes() for p in protected}
        attempts = [(p, source_input) for p in protected[:-1]]
        attempts.append((source_input.parent/".."/"projects"/source_input.name, source_input))
        attempts.append((custom_input, custom_input))
        for mode in ("symlink", "hardlink"):
            for index, target in enumerate((source_input, model, package/OWNED[5], package/OWNED[4], custom_input)):
                alias = working/(mode+str(index))
                if mode == "symlink":
                    alias.symlink_to(target)
                else:
                    os.link(target, alias)
                attempts.append((alias, custom_input if target == custom_input else source_input))
        for index, (output, input_path) in enumerate(attempts):
            flags = ["-O"] if index % 2 else []
            completed = subprocess.run([sys.executable]+flags+[str(model), "--input", str(input_path), "--output", str(output)],
                                       cwd=working, env=env, capture_output=True, text=True, timeout=20)
            a.eq(completed.returncode, 2, "real alias refusal")
            a.eq(completed.stdout, "", "alias failure has no stdout")
            a.eq("aliases protected payload" in completed.stderr, True, "explicit alias reason")
            a.alias_refusals += 1
        for path, raw_bytes in original.items():
            a.eq(path.read_bytes(), raw_bytes, "protected bytes unchanged")
        raw_good = source_input.read_bytes()
        payloads = [b'{"schema":1,"schema":1}', raw_good.replace(b'"historical_collections": 90', b'"historical_collections": NaN'),
                    raw_good.replace(b'"down_revenue_loss": 0', b'"down_revenue_loss": Infinity'),
                    raw_good.replace(b'"down_revenue_loss": 0', b'"down_revenue_loss": 1e10000'),
                    raw_good+b'{}', b'\xff', b' '*32769, b'[]',
                    raw_good.replace(b'"escrow_senior_claim": 0', b'"escrow_senior_claim": 6')]
        invalid = working/"bad.json"
        target = working/"do-not-replace.txt"
        for index, payload in enumerate(payloads):
            invalid.write_bytes(payload)
            target.write_text("preserve\n")
            flags = ["-O"] if index % 2 else []
            completed = subprocess.run([sys.executable]+flags+[str(model), "--input", str(invalid), "--output", str(target)],
                                       cwd=working, env=env, capture_output=True, text=True, timeout=20)
            a.eq(completed.returncode, 2, "CLI strict/domain rejection")
            a.eq(completed.stdout, "", "invalid CLI quiet stdout")
            a.eq(target.read_text(), "preserve\n", "invalid input cannot overwrite output")
            a.cli_rejections += 1


def check(include_isolation=True, require_bindings=True):
    a = Audit()
    data = json.loads((ROOT/OWNED[1]).read_text())
    module = load_model(ROOT/OWNED[2])
    baseline = call(a, module, data)
    audit_result(a, data, baseline, "baseline")
    a.eq(call(a, module, data), baseline, "repeat deterministic API")
    a.eq(json.loads((ROOT/OWNED[3]).read_text()), baseline, "saved output reproduces independently audited API")
    cases = [("collections", {"historical_collections":80}),
             ("after revenue", {"down_revenue_loss":2.5}),
             ("before revenue", {"down_revenue_loss":2.5, "information":"before_trade"}),
             ("physical law", {"physical_probabilities":[.3, .3, .4]}),
             ("late escrow", {"escrow_settlement":"16:00"}),
             ("senior discovery", {"escrow_senior_claim":5}),
             ("combined upper domain", {"down_revenue_loss":10, "escrow_senior_claim":5, "escrow_settlement":"16:00"})]
    for label, updates in cases:
        d = copy.deepcopy(data); d["experiment"].update(updates)
        result = call(a, module, d)
        audit_result(a, d, result, label)
    # Purposeful neighboring boundaries, not a broad grid of arbitrary numbers.
    boundaries = [("after_trade", 2.111111111111, True), ("after_trade", 2.111111111112, False),
                  ("before_trade", 2.714285714285, True), ("before_trade", 2.714285714286, False)]
    for info, delta, floor_pass in boundaries:
        d = copy.deepcopy(data); d["experiment"].update(information=info, down_revenue_loss=delta)
        result = call(a, module, d)
        original = next(r for r in result["policies"] if r["id"] == "1/2-escrow-1/4")
        a.eq(original["eligible"], floor_pass, "one decimal quantum around exact capital boundary")
        a.eq(oracle(d)["fixed"]["eligible"], floor_pass, "independent boundary sign")
    for p, normal, winner in ((.244444444444, .355555555556, "1/2-escrow-1/4"),
                              (.244444444445, .355555555555, "1/2-escrow-1/2")):
        d = copy.deepcopy(data); d["experiment"]["physical_probabilities"] = [p, normal, .4]
        a.eq(call(a, module, d)["selected_policy"], winner, "physical preference switch neighbors")
    d = copy.deepcopy(data); d["experiment"]["down_revenue_loss"] = .0001220703125
    small = call(a, module, d)
    a.eq(F(str(d["experiment"]["down_revenue_loss"])), F(1, 8192), "reduced denominator is not decimal scale")
    a.eq(small["actual_after_trade_position"]["net_capital_by_state"][0], F(55, 18)-F(1, 16384), "supported thirteen-place decimal")
    domain_checks(a, module, data)
    page = Page(); page.feed((ROOT/OWNED[0]).read_text())
    manuscript_and_proofs(a, data, page)
    if require_bindings:
        binding_checks(a)
    if include_isolation:
        portable_and_safety(a, baseline)
    result = {"component":"finance-core-project", "status":"passed", "comparisons":a.comparisons,
              "independently_reconstructed_policy_rows":a.policy_rows,
              "fully_reconstructed_journal_rows":a.journal_rows,
              "visible_exact_anchors_and_table_cells":a.printed,
              "focused_full_contracts":1+len(cases), "boundary_interventions":7,
              "api_domain_rejections":a.rejections, "cli_rejections":a.cli_rejections,
              "actual_alias_refusals":a.alias_refusals, "portable_normal_optimized_runs":a.portable_runs,
              "manifest_payloads":4 if require_bindings else 0, "author_nonself_bindings":8 if require_bindings else 0,
              "scope":"Original finite contract, six transfers, exact proofs and reader pairing; not actual settlement, empirical calibration or external certification."}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-isolation", action="store_true", help="internal exact-copy test; avoid recursive copying")
    args = parser.parse_args()
    print(json.dumps(check(include_isolation=not args.no_isolation), allow_nan=False, sort_keys=True))
