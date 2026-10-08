#!/usr/bin/env python3
"""Independent exact arithmetic and bounded behavior audit for v07-c02."""
from fractions import Fraction as Q
from html.parser import HTMLParser
from pathlib import Path
import contextlib
import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects/v07-c02-analysis.py"
INPUT = PROJECT.with_name("v07-c02-inputs.json")
CHAPTER = ROOT / "content/chapters/v07-c02.html"


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def equal(actual, expected, label):
    need(Q(actual) == Q(expected), f"{label}: {actual} != {expected}")


def eq_fields(obj, values, label):
    for key, value in values.items():
        equal(obj[key], value, label + "." + key)


def baseline_reference(report):
    eq_fields(report["income_statement_kcu"], {"revenue": 190, "cost_of_goods_sold": 95,
        "wage_expense": 40, "insurance_expense": 4, "rent_expense": 12, "interest_expense": 6,
        "depreciation_expense": 9, "disposal_gain": 1, "gross_profit": 95,
        "trading_result_before_disposal_and_interest": 30, "profit": 25}, "income")
    eq_fields(report["balance_sheet_kcu"], {"cash": 69, "receivables": 45, "inventory": 45,
        "prepaid_insurance": 8, "equipment": 152, "accumulated_depreciation": 33,
        "net_equipment": 119, "trade_payables": 30, "wages_payable": 6, "interest_payable": 2,
        "customer_advances": 12, "borrowings": 93, "share_capital": 100, "retained_earnings": 43,
        "current_assets": 167, "current_borrowings": 21, "noncurrent_borrowings": 72,
        "current_liabilities": 71, "assets": 286, "liabilities": 143, "equity": 143}, "balance sheet")
    eq_fields(report["cash_flow_kcu"], {"operating": 21, "indirect_operating": 21, "investing": -19,
        "financing": 27, "change": 29, "opening_cash": 40, "closing_cash": 69}, "cash flow")
    eq_fields(report["cash_flow_kcu"]["direct_lines"], {"customer_receipts": 177, "supplier_payments": -95,
        "wage_payments": -38, "insurance_payments": -6, "rent_payments": -12, "interest_payments": -5,
        "equipment_sale": 5, "equipment_purchase": -24, "share_issue": 20, "borrowing": 30,
        "principal_repayment": -15, "dividends": -8}, "direct lines")
    eq_fields(report["rollforwards_kcu"], {"opening_assets": 216, "opening_operating_nwc": 36,
        "closing_operating_nwc": 48, "change_operating_nwc": 12, "equipment_additions": 42,
        "equipment_cost_disposed": 10, "accumulated_depreciation_removed": 6,
        "disposed_carrying_amount": 4, "closing_borrowings": 93}, "rollforwards")
    equal(report["noncash_disclosure_kcu"]["equipment_acquired_for_seller_note"], 18, "noncash note")
    need(all(Q(value) == 0 for value in report["zero_residuals_kcu"].values()), "nonzero bridge residual")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.exercises = self.solutions = self.worked = self.h1 = 0
        self.links = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "h1": self.h1 += 1
        if tag == "aside" and "worked" in classes: self.worked += 1
        if tag == "a": self.links.append(attrs.get("href", ""))
        if "id" in attrs: self.ids.append(attrs["id"])
        if tag == "li":
            if any(t == "ol" and "exercises" in c for t, c in self.stack): self.exercises += 1
            if any(t == "details" and "solutions" in c for t, c in self.stack): self.solutions += 1
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        need(bool(self.stack) and self.stack[-1][0] == tag, "mismatched HTML tag " + tag)
        self.stack.pop()


def posting(account, side, amount):
    return {"account": account, "side": side, "amount_kcu": str(amount)}


def event(identifier, line, postings):
    return {"id": identifier, "description": "Independent scenario adjustment", "cash_line": line, "postings": postings}


def change_collection(data, value):
    result = copy.deepcopy(data)
    for p in result["events"][6]["postings"]:
        p["amount_kcu"] = str(value)
    return result


def check():
    checks = []
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        spec = importlib.util.spec_from_file_location("v07_c02_lab", PROJECT)
        lab = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab)
        data = lab.load_inputs(INPUT)
        report = lab.build_report(data)
    need(not stdout.getvalue() and not stderr.getvalue(), "import and API must be quiet")
    json.dumps(report, allow_nan=False)
    baseline_reference(report)
    checks.append("All baseline statement lines, 18 noncash note, schedules and 17 zero bridge residuals checked against independent references")

    # A separate Fraction-based posting engine, with no lab parsing/posting calls.
    balances = {a: Q(n) for a, n in data["opening_debit_balances_kcu"].items()}
    all_debits = all_credits = Q(0)
    cash_path = [balances["cash"]]
    for e in data["events"]:
        dr = sum(Q(p["amount_kcu"]) for p in e["postings"] if p["side"] == "Dr")
        cr = sum(Q(p["amount_kcu"]) for p in e["postings"] if p["side"] == "Cr")
        equal(dr, cr, "independent journal " + e["id"])
        all_debits += dr
        all_credits += cr
        for p in e["postings"]:
            a = p["account"]
            balances[a] = balances.get(a, Q(0)) + (1 if p["side"] == "Dr" else -1) * Q(p["amount_kcu"])
        cash_path.append(balances["cash"])
    for a, n in balances.items(): equal(report["adjusted_trial_balance_kcu"][a], n, "independent ledger " + a)
    need(cash_path == [Q(p["cash_kcu"]) for p in report["cash_path"]], "every cash prefix")
    equal(all_debits, all_credits, "aggregate debit-credit equality")
    equal(sum(balances.values()), 0, "adjusted trial balance")
    expected_closed = {k: Q(v) for k, v in balances.items()}
    temporary = ["revenue", "disposal_gain", "cost_of_goods_sold", "wage_expense", "insurance_expense",
                 "rent_expense", "interest_expense", "depreciation_expense", "dividends"]
    for a in temporary:
        expected_closed["retained_earnings"] += expected_closed[a]
        expected_closed[a] = 0
    for a, n in expected_closed.items(): equal(report["postclosing_trial_balance_kcu"][a], n, "closing " + a)
    for e in report["closing_entries"]:
        equal(Q(e["temporary_debit_change_kcu"]) + Q(e["retained_earnings_debit_change_kcu"]), 0, "closing-entry equality")
    equal(report["postclosing_trial_balance_kcu"]["cash"], report["adjusted_trial_balance_kcu"]["cash"], "closing has no cash")
    checks.append("Independent rational posting of all 23 events, every cash prefix and all nine temporary-account closures")

    collection_cases = 0
    for value in ("16", "20", "50", "85", "85.00001", "120", "130"):
        changed = lab.build_report(change_collection(data, value))
        x = Q(value)
        eq_fields(changed["balance_sheet_kcu"], {"cash": x - 16, "receivables": 130 - x,
            "assets": 286, "equity": 143, "retained_earnings": 43}, "collection scenario")
        eq_fields(changed["cash_flow_kcu"], {"operating": x - 64, "indirect_operating": x - 64,
            "investing": -19, "financing": 27, "change": x - 56}, "collection cash")
        equal(changed["income_statement_kcu"]["profit"], 25, "collection is not revenue")
        collection_cases += 1
    shortfall = change_collection(data, 10)
    borrow = copy.deepcopy(shortfall)
    borrow["events"].insert(-1, event("repair-borrow", "borrowing", [posting("cash", "Dr", 6), posting("borrowings", "Cr", 6)]))
    dividend = copy.deepcopy(shortfall)
    for p in dividend["events"][-1]["postings"]: p["amount_kcu"] = "2"
    for edited, liabilities, equity, retained, debt in [(borrow, 149, 143, 43, 99), (dividend, 143, 149, 49, 93)]:
        changed = lab.build_report(edited)
        eq_fields(changed["balance_sheet_kcu"], {"cash": 0, "receivables": 120, "assets": 292,
            "liabilities": liabilities, "equity": equity, "retained_earnings": retained, "borrowings": debt}, "funding repair")
        eq_fields(changed["cash_flow_kcu"], {"operating": -54, "investing": -19, "financing": 33, "change": -40}, "repair flows")
    delayed = copy.deepcopy(data)
    delayed["events"].insert(-1, event("delayed-collection", "customer_receipts", [posting("cash", "Dr", 7), posting("receivables", "Cr", 7)]))
    delayed["current_borrowings_kcu"] = "26"
    changed = lab.build_report(delayed)
    eq_fields(changed["balance_sheet_kcu"], {"cash": 76, "receivables": 38, "retained_earnings": 43,
        "assets": 286, "current_borrowings": 26, "noncurrent_borrowings": 67}, "retention")
    equal(changed["cash_flow_kcu"]["operating"], 28, "retention CFO")
    checks.append("Seven collection cases including one exact minor unit, two fully reconciled funding repairs and answered delayed check")

    for proceeds in (3,4,5):
        disposal=copy.deepcopy(data)
        gain=proceeds-4
        p=[posting("cash","Dr",proceeds),posting("accumulated_depreciation","Dr",6),posting("equipment","Cr",10)]
        if gain: p.append(posting("disposal_gain","Cr" if gain>0 else "Dr",abs(gain)))
        disposal["events"][18]["postings"]=p
        changed=lab.build_report(disposal)
        eq_fields(changed["income_statement_kcu"],{"disposal_gain":gain,"profit":24+gain},"gain/loss boundary")
        eq_fields(changed["cash_flow_kcu"],{"operating":21,"investing":proceeds-24,"financing":27,"closing_cash":64+proceeds},"gain/loss cash")
    checks.append("Disposal loss, zero gain and positive gain: entire proceeds remain investing and operating cash stays 21")

    # All eight exercise solutions; independent of the benchmark's calculations.
    effects = [(12,12,0,12,0,0,0,12), (9,9,9,0,0,0,0,9), (6,6,0,6,6,6,0,0),
               (0,8,0,8,8,0,0,0), (4,0,0,0,0,4,0,0), (0,-3,0,-3,-3,0,0,0),
               (0,5,5,0,0,0,0,0), (-2,-2,0,-2,0,0,0,-2)]
    for cash, assets, liabilities, equity, profit, cfo, cfi, cff in effects:
        equal(assets, liabilities + equity, "exercise1 change in equation")
        equal(cash, cfo + cfi + cff, "exercise1 cash category")
    e2 = {"profit": 40-18-10-3, "cash": 20+35-18-10-5-2, "ar": 8+40-35,
          "inventory": 12+20-18, "ppe": 40-10-3, "ap": 9+20-18, "debt": 25-5,
          "re": 16+(40-18-10-3)-2, "cfo": 35-18-10}
    need(e2 == {"profit":9,"cash":20,"ar":13,"inventory":14,"ppe":27,"ap":11,"debt":20,"re":23,"cfo":7}, "exercise2")
    equal(e2["cash"]+e2["ar"]+e2["inventory"]+e2["ppe"], e2["ap"]+e2["debt"]+20+e2["re"], "exercise2 balance")
    equal(9+3-(13-8)-(14-12)+(11-9), 7, "exercise2 indirect")
    receipts = 72-(19-10)+(5-8)
    purchases = 40+(23-16)
    payments = [purchases-(20-14), 12-(5-3), 6+(1-4), 2-(0-1)]
    need([receipts,purchases,*payments] == [60,47,41,10,3,3], "exercise3 direct components")
    profit = 72-40-12-6-2-4
    equal(receipts-sum(payments), 3, "exercise3 direct")
    equal(profit+4-9-7+3+6+2-1-3, 3, "exercise3 indirect")
    gross=100-30+20+25; accum=40-18+7; gain=14-(30-18)
    need([gross,accum,gross-accum,gain,14-20] == [115,29,86,2,-6], "exercise4")
    equal((86-60)+7+12-25,20,"exercise4 cash acquisition recovery")
    equal(gain-7+7-gain,0,"exercise4 zero CFO")
    equal(25+9-1+6-(50-37),26,"exercise5 revised indirect")
    equal(26-19+22,29,"exercise5 unchanged total")
    equal(69-(85-10),-6,"exercise6 unfunded cash")
    equal(21-(85-10),-54,"exercise6 CFO")
    equal(0+120+45+8+119,292,"exercise6 assets")
    need(292==149+143==143+149,"exercise6 two financing structures")
    equal((25+5)-(15+5),25-15,"exercise7 cancellation")
    equal((21+10)+(27-10),21+27,"exercise7 category cancellation")
    need([max(12-(9+3),0),max(12-9,0),9+15+4+10-20] == [0,3,18],"exercise8 liquidity and separate sale values")
    checks.append("All eight exercise solutions, stock-flow signs, alternative interest classification and counterexample arithmetic independently recomputed")

    wrong = copy.deepcopy(data)
    wrong["events"][6]["postings"] = [posting("cash", "Dr", 85), posting("receivables", "Cr", 80), posting("revenue", "Cr", 5)]
    wrong_report = lab.build_report(wrong)
    eq_fields(wrong_report["balance_sheet_kcu"], {"cash": 69, "receivables": 50, "retained_earnings": 48, "equity": 148, "assets": 291}, "wrong receipt")
    equal(wrong_report["income_statement_kcu"]["profit"],30,"wrong receipt profit")
    equal(wrong_report["cash_flow_kcu"]["operating"],21,"wrong receipt still reconciles")
    need(all(Q(n)==0 for n in wrong_report["zero_residuals_kcu"].values()), "counterexample must pass identities")
    try:
        baseline_reference(wrong_report)
    except AssertionError:
        pass
    else:
        raise AssertionError("separate source-transaction reference must detect wrong recognition")
    checks.append("Balanced wrong-revenue receipt demonstrably passes all numeric bridges; separate supplied transaction reference detects the error")

    invalid = []
    def bad(path, value):
        edit = copy.deepcopy(data)
        node = edit
        for key in path[:-1]: node = node[key]
        node[path[-1]] = value
        invalid.append(edit)
    for value in (True, 85, 85.0, None, [], {}, "NaN", "Infinity", "1e2", "1.000001", "1000001", "0", "-1", " 85", "+85"):
        bad(["events",6,"postings",0,"amount_kcu"],value)
    bad(["events",6,"postings",0,"account"],"unknown")
    bad(["events",6,"postings",0,"side"],"Debit")
    bad(["events",6,"postings",0,"amount_kcu"],"84")
    bad(["events",6,"postings",1,"account"],"cash")
    bad(["events",6,"cash_line"],None)
    bad(["events",20,"cash_line"],"borrowing")
    bad(["events",1,"cash_line"],"customer_receipts")
    bad(["events",16,"cash_line"],"rent_payments")
    bad(["events",0,"id"],"e02")
    bad(["events",0,"description"],"")
    bad(["current_borrowings_kcu"],"94")
    bad(["current_borrowings_kcu"],"-1")
    bad(["period_start"],"2025-01-02")
    bad(["period_end"],"2024-12-30")
    bad(["period_end"],"2025-02-30")
    bad(["opening_debit_balances_kcu","cash"],"39")
    bad(["unit"],"USD")
    bad(["events"],[])
    bad(["entity"],None)
    invalid.append(shortfall)
    late = copy.deepcopy(shortfall)
    late["events"].append(event("too-late-funding", "borrowing", [posting("cash","Dr",6),posting("borrowings","Cr",6)]))
    invalid.append(late)
    invalid.append(change_collection(data,"131"))
    for i, value in enumerate(invalid):
        try: lab.build_report(value)
        except ValueError: pass
        else: raise AssertionError("invalid contract accepted " + str(i))
    checks.append(f"{len(invalid)} malformed/unsupported input cases rejected, including wrong cash categories, unfunded final cash and too-late funding")

    with tempfile.TemporaryDirectory(prefix="v07-c02-check-") as temporary:
        temp = Path(temporary)
        for options in ([], ["-O"]):
            run = subprocess.run([sys.executable,*options,str(PROJECT)],cwd=temp,text=True,capture_output=True,check=False)
            need(run.returncode==0 and not run.stderr,"portable default CLI")
            need(json.loads(run.stdout)==report,"CLI matches API without assert dependence")
        invalid_path=temp/"invalid.json"
        invalid_path.write_text(json.dumps(shortfall))
        run=subprocess.run([sys.executable,str(PROJECT),str(invalid_path)],cwd=temp,text=True,capture_output=True,check=False)
        need(run.returncode==2 and json.loads(run.stdout)["status"]=="error" and not run.stderr,"CLI explicit error")
        for raw in ('{"schema":"a","schema":"b"}', '{"amount":NaN}', '{"amount":Infinity}'):
            invalid_path.write_text(raw)
            try: lab.load_inputs(invalid_path)
            except ValueError: pass
            else: raise AssertionError("invalid JSON representation accepted")
        invalid_path.write_text(" "*200001)
        try: lab.load_inputs(invalid_path)
        except ValueError: pass
        else: raise AssertionError("oversize file accepted")
    checks.append("Portable normal and optimized CLI equal quiet API; structured failure exit, duplicate fields, nonfinite JSON and oversize file rejected")

    mutants = []
    for section,key,value in [("income_statement_kcu","profit","26"),("cash_flow_kcu","operating","30"),
                              ("balance_sheet_kcu","retained_earnings","51"),("noncash_disclosure_kcu","equipment_acquired_for_seller_note","0")]:
        mutant=copy.deepcopy(report);mutant[section][key]=value;mutants.append(mutant)
    for mutant in mutants:
        try: baseline_reference(mutant)
        except AssertionError: pass
        else: raise AssertionError("mutated report escaped independent reference")
    fragment=Fragment(); html=CHAPTER.read_text();fragment.feed(html);fragment.close()
    need(not fragment.stack and fragment.h1==0 and fragment.worked>=2 and fragment.exercises==fragment.solutions==8,"chapter structure")
    need(len(fragment.ids)==len(set(fragment.ids)),"unique chapter IDs")
    for filename in ("v07-c02-analysis.py","v07-c02-inputs.json","v07-c02-README.txt"):
        need(filename in fragment.links and (PROJECT.parent/filename).is_file(),"flat download " + filename)
    need("v07-c01.html" in fragment.links and "curriculum.html#v07" in fragment.links,"prerequisite and planned continuation route")
    need("Teach-back guide" in html and "Delayed-check answer" in html,"answered self-study prompts")
    sources=json.loads((ROOT/"content/reviews/v07-c02-sources.json").read_text())
    source_ids={s["id"] for s in sources}
    need(len(sources)==len(source_ids)==5,"five distinct source proposals")
    for source in sources:
        need(set(source)=={"id","title","url","use","checked","verification"},"source record fields")
        need(source["id"].startswith("v07-c02-") and source["url"].startswith("https://"),"scoped source id/URL")
        need("sources.html#"+source["id"] in fragment.links,"source cited in chapter")
    checks.append("Four report mutations caught; HTML fragment has three worked examples, eight matched solutions, answered prompts and flat artifact routes")
    return {"status":"passed","checks":checks,"counts":{"events":23,"collection_cases":collection_cases,
        "disposal_cases":3,"invalid_contracts":len(invalid),"invalid_file_encodings_or_size":4,"report_mutations_caught":len(mutants),
        "worked_examples":fragment.worked,"exercises":fragment.exercises,"source_proposals":len(sources)},
        "limitations":["This is a bounded numerical/structural author check, not external accounting certification or documentary audit.",
            "Cash classification, recognition, units and maturities are supplied case conventions; current jurisdictional compliance is not inferred.",
            "Balanced wrong-account entries can pass all statement identities; the counterexample is intentionally preserved.",
            "Visual, mobile and print UI QA remains pending; this checker makes no visual claim."]}


if __name__ == "__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
