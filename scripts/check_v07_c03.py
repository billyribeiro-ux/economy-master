#!/usr/bin/env python3
"""Focused, exact, independent author checks for the working-capital chapter."""
from fractions import Fraction as Q
from html.parser import HTMLParser
from pathlib import Path
import contextlib
import copy
import importlib.util
import io
import itertools
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects/v07-c03-analysis.py"
INPUT = PROJECT.with_name("v07-c03-inputs.json")
CHAPTER = ROOT / "content/chapters/v07-c03.html"


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def eq(actual, expected, label):
    need(Q(actual) == Q(expected), f"{label}: {actual} != {expected}")


def fields(actual, expected, label):
    for key, value in expected.items():
        eq(actual[key], value, label + "." + key)


def reference(report):
    fields(report["income_kcu"], {"revenue": 230, "cost_of_sales": 144, "other_expense": 32,
        "credit_loss_expense": 7, "profit": 47}, "income")
    fields(report["balance_sheet_kcu"], {"cash": 32, "gross_receivables": 82, "allowance": 9,
        "net_receivables": 73, "inventory": 96, "payables": 40, "advances": 12,
        "capital": 80, "retained_earnings": 69, "assets": 201, "liabilities": 52, "equity": 149}, "balance")
    fields(report["cash_flow_kcu"], {"customer_receipts": 204, "supplier_payments": 170,
        "other_payments": 32, "operating": 2, "gross_indirect": 2, "net_indirect": 2,
        "investing": 0, "financing": 0}, "cash")
    fields(report["working_capital_kcu"], {"gross_opening": 80, "gross_closing": 126, "gross_change": 46,
        "net_opening": 72, "net_closing": 117, "net_change": 45, "pre_adjustment_allowance": 2}, "N")
    fields(report["days_ratios"], {"dso_gross_credit": Q(71, 2), "dio": 55,
        "dpo_credit_purchases": Q(135, 4), "ccc_credit_purchases": Q(227, 4),
        "dpo_total_purchases": Q(405, 16), "ccc_total_purchases": Q(1043, 16),
        "dpo_cost_of_sales": Q(225, 8), "ccc_cost_of_sales": Q(499, 8),
        "dso_total_revenue": Q(639, 23), "dso_net_credit": Q(125, 4)}, "ratios")
    fields(report["alternative_calendar"], {"minimum_facility_kcu": 8, "gross_draws_kcu": 8,
        "final_repayment_kcu": 8, "cash_after_repayment_kcu": 32, "closing_bridge_debt_kcu": 0}, "funding")
    need([Q(r["unfinanced_cash_kcu"]) for r in report["alternative_calendar"]["rows"]] == [8, -8, 32], "raw calendar")
    need([Q(r["conditional_cash_kcu"]) for r in report["alternative_calendar"]["rows"]] == [8, 0, 40], "funded calendar")
    need(len(report["zero_residuals_kcu"]) == 14 and all(Q(n) == 0 for n in report["zero_residuals_kcu"].values()), "14 residuals")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.links, self.ids = [], [], []
        self.worked = self.exercises = self.solutions = self.h1 = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get("class", "").split()
        if tag == "h1": self.h1 += 1
        if tag == "aside" and "worked" in classes: self.worked += 1
        if tag == "a": self.links.append(a.get("href", ""))
        if "id" in a: self.ids.append(a["id"])
        if tag == "li":
            if any(t == "ol" and "exercises" in c for t, c in self.stack): self.exercises += 1
            if any(t == "details" and "solutions" in c for t, c in self.stack): self.solutions += 1
        if tag not in ("br", "hr", "img", "input", "meta", "link"): self.stack.append((tag, classes))
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0] == tag, "HTML nesting: " + tag)
        self.stack.pop()


def single_calendar(data):
    f = {k: Q(v) for k, v in data["flows_kcu"].items()}
    # Scenario inputs here are whole kCU, so formatting the independent sums is exact.
    data["alternative_calendar"] = [{"date": data["end"],
        "receipts_kcu": str(f["cash_sales"] + f["ordinary_collections"] + f["advances_received"] + f["recoveries"]),
        "suppliers_kcu": str(f["cash_purchases"] + f["payables_paid"]),
        "other_kcu": str(f["other_expense_paid"])}]


def check():
    checks = []
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        spec = importlib.util.spec_from_file_location("v07_c03_lab", PROJECT)
        lab = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab)
        data = lab.load_inputs(INPUT)
        report = lab.build_report(data)
    need(not stdout.getvalue() and not stderr.getvalue(), "quiet import/API")
    json.dumps(report, allow_nan=False)
    reference(report)
    checks.append("Independent baseline statements, allowance, both CFO bridges, ten day ratios and 14 exact zero residuals")

    # Independently supplied postings, not the benchmark's generated journals/formulas.
    changes = [
        {"cash": 40, "revenue": -40}, {"gross_receivables": 180, "revenue": -180},
        {"cash": 150, "gross_receivables": -150}, {"cash": 12, "advances": -12},
        {"advances": 10, "revenue": -10}, {"inventory": 160, "cash": -40, "payables": -120},
        {"cost_of_sales": 144, "inventory": -144}, {"payables": 130, "cash": -130},
        {"other_expense": 32, "cash": -32}, {"allowance": 8, "gross_receivables": -8},
        {"gross_receivables": 2, "allowance": -2}, {"cash": 2, "gross_receivables": -2},
        {"credit_loss_expense": 7, "allowance": -7}]
    balances = {"cash": Q(30), "gross_receivables": Q(60), "allowance": Q(-8), "inventory": Q(80),
        "payables": Q(-50), "advances": Q(-10), "capital": Q(-80), "retained_earnings": Q(-22),
        "revenue": Q(0), "cost_of_sales": Q(0), "other_expense": Q(0), "credit_loss_expense": Q(0)}
    path = [balances["cash"]]
    for change, actual in zip(changes, report["journal"]):
        need(set(change) == set(actual["debit_changes_kcu"]), "journal account identity")
        fields(actual["debit_changes_kcu"], change, actual["id"])
        eq(sum(change.values()), 0, "balanced supplied journal")
        for a, n in change.items(): balances[a] += n
        eq(sum(balances.values()), 0, "independent trial balance")
        path.append(balances["cash"])
    need(len(report["journal"]) == 13 and path == [Q(p["cash_kcu"]) for p in report["cash_path"]], "13 journals and all cash prefixes")
    fields(report["adjusted_debit_balances_kcu"], balances, "adjusted ledger")
    for a in ("revenue", "cost_of_sales", "other_expense", "credit_loss_expense"):
        balances["retained_earnings"] += balances[a]
        balances[a] = 0
    fields(report["postclosing_debit_balances_kcu"], balances, "closed ledger")
    checks.append("Separate rational posting reference checks all 13 journals, every cash prefix and four income-account closures")

    # Expense reversal, zero target, base target and higher target: same cash.
    allowance_cases = 0
    for fraction in ("0", "1/82", "9/82", "15/82", "1"):
        changed = copy.deepcopy(data)
        changed["aging"] = [{"label": "Independently supplied scenario", "gross_kcu": "82", "loss_fraction": fraction}]
        result = lab.build_report(changed)
        z = 82 * Q(fraction)
        fields(result["income_kcu"], {"credit_loss_expense": z - 2, "profit": 56 - z}, "target change")
        fields(result["balance_sheet_kcu"], {"net_receivables": 82 - z, "cash": 32,
            "assets": 210 - z, "equity": 158 - z}, "target balance")
        fields(result["cash_flow_kcu"], {"operating": 2, "gross_indirect": 2, "net_indirect": 2}, "target cash")
        eq(result["days_ratios"]["dso_net_credit"], (134 - z) / 4, "estimate-driven DSO")
        allowance_cases += 1

    writeoff_cases = 0
    for w, h in ((0, 0), (8, 0), (8, 2), (10, 2)):
        changed = copy.deepcopy(data)
        changed["flows_kcu"].update(writeoffs=str(w), recoveries=str(h))
        gross = 90 - w
        changed["aging"] = [{"label": "Constant independently supplied target", "gross_kcu": str(gross), "loss_fraction": "9/" + str(gross)}]
        single_calendar(changed)
        result = lab.build_report(changed)
        fields(result["income_kcu"], {"credit_loss_expense": 1 + w - h, "profit": 53 - w + h}, "writeoff/recovery")
        fields(result["balance_sheet_kcu"], {"cash": 30 + h, "gross_receivables": gross, "allowance": 9,
            "net_receivables": 81 - w, "assets": 207 - w + h, "equity": 155 - w + h}, "writeoff balance")
        eq(result["cash_flow_kcu"]["operating"], h, "recovery cash")
        writeoff_cases += 1

    mix_cases = 0
    for cash_purchase in (0, 40, 160):
        changed = copy.deepcopy(data)
        changed["flows_kcu"].update(cash_purchases=str(cash_purchase), credit_purchases=str(160 - cash_purchase), payables_paid=str(170 - cash_purchase))
        result = lab.build_report(changed)
        fields(result["balance_sheet_kcu"], {"cash": 32, "inventory": 96, "payables": 40, "assets": 201}, "purchase mix")
        eq(result["cash_flow_kcu"]["operating"], 2, "same supplier cash")
        if cash_purchase == 160:
            need(result["days_ratios"]["dpo_credit_purchases"] is None and result["days_ratios"]["ccc_credit_purchases"] is None, "zero credit-purchase denominator")
        else:
            eq(result["days_ratios"]["dpo_credit_purchases"], Q(4050, 160 - cash_purchase), "credit mix DPO")
        mix_cases += 1
    checks.append("Five allowance targets including expense reversal, four writeoff/recovery cases including retention, and three cash-credit mixes including zero denominator")

    facilities = []
    for permutation in itertools.permutations(data["alternative_calendar"]):
        changed = copy.deepcopy(data)
        changed["alternative_calendar"] = [dict(row, date=data["alternative_calendar"][i]["date"]) for i, row in enumerate(permutation)]
        raw, lowest = Q(30), Q(30)
        for row in permutation:
            raw += Q(row["receipts_kcu"]) - Q(row["suppliers_kcu"]) - Q(row["other_kcu"])
            lowest = min(lowest, raw)
        result = lab.build_report(changed)
        facility = max(0, -lowest)
        fields(result["alternative_calendar"], {"minimum_facility_kcu": facility, "cash_after_repayment_kcu": 32}, "calendar order")
        need(result["days_ratios"] == report["days_ratios"], "ratios invariant to separate cash-calendar ordering")
        facilities.append(facility)
    need(set(facilities) == {0, 8}, "some calendar orders need credit, others do not")
    checks.append("All six calendar-bucket permutations preserve quarter totals/ratios but vary conditional facility between zero and eight")

    # Every exercise, recomputed directly from the stated inputs.
    eq(14 - 1 - Q(9, 2), 6 + Q(5, 2), "E1 balance changes")
    eq(3 + 4 - 2 - Q(5, 2), Q(5, 2), "E1 profit")
    g2, z2 = 50 + 100 - 90 - 5, 45 * Q(2, 100) + 10 * Q(36, 100)
    b2, inv2, ap2 = z2 - (4 - 5 + 1), 30 + 70 - 65, 20 + 70 - 60
    ni2, cfo2 = 126 - 65 - 15 - b2, 20 + 90 + 8 + 1 - 60 - 15
    eq(g2, 55, "E2 gross"); eq(b2, Q(9, 2), "E2 expense"); eq(ni2, Q(83, 2), "E2 profit"); eq(cfo2, 44, "E2 CFO")
    eq(10 + cfo2 + g2 - z2 + inv2, ap2 + 8 + 60 + ni2, "E2 closing balance")
    ng0, ng1 = 50 + 30 - 20 - 6, g2 + inv2 - ap2 - 8
    eq(ni2 + b2 - (ng1 - ng0) - 5 + 1, cfo2, "E2 gross bridge")
    eq(ni2 - ((ng1 - z2) - (ng0 - 4)), cfo2, "E2 net bridge")
    e3_states = [(40, 5, 0), (37, 2, 0), (38, 3, 0), (37, 3, 1), (37, 4, 1)]
    need([g - z for g, z, c in e3_states] == [35, 35, 35, 34, 33], "E3 each net balance")
    eq(4 - (5 - 3 + 1), 1, "E3 expense"); eq(4 - (5 - 3), 2, "E3 no recovery expense")
    eq(120 * Q(50, 200) + 120 * Q(50, 240) - 120 * Q(30, 180), 35, "E4 matched CCC")
    eq(30 + 25 - 120 * Q(30, 240), 40, "E4 COGS CCC")
    eq(120 * Q(50, 300) + 25 - 20, 25, "E4 total sales substitution")
    eq(80 + 20 + 180 - 40, 240, "E4 supplier cash")
    raw, e5 = 20, []
    for flow in (-80, 100, -70, 130, -20): raw += flow; e5.append(raw)
    need(e5 == [-60, 40, -30, 100, 80] and -min(e5) == 60 and raw - 20 == 60, "E5 calendar and facility")
    g6, i6, p6 = 5 * 10, 2 * 20, 2 * 35
    eq(g6 + i6 - p6, 20, "E6 N"); eq(20 + 10 - 35, -5, "E6 CCC")
    eq(Q(3, 2) * (g6 + i6 - p6) - 20, 10, "E6 growth funding")
    eq(20 - 2 * (-5), (5 - 2) * 10, "E6 margin wedge")
    interest = 98 * Q(12, 100) * Q(20, 360)
    eq(interest, Q(49, 75), "E7 interest"); eq(98 + interest, Q(7399, 75), "E7 repayment")
    eq(100 - 98 - interest, Q(101, 75), "E7 saving"); eq(Q(2, 98) * 18, Q(18, 49), "E7 simple annual rate")
    eq(230 - 144 - 32 - 13, 41, "E8 profit"); eq(67 + 96 - 40 - 12, 111, "E8 net N")
    eq(41 - (111 - 72), 2, "E8 CFO"); eq(Q(52 + 67, 4), Q(119, 4), "E8 net DSO")
    eq(3 * 20 + 2 * 30 - 2 * 40, 40, "steady worked counterexample N")
    eq(2 * (30 + 20 - 40), 20, "steady CCC cost proxy")
    checks.append("All eight exercise solutions, cutoff identity, supplier-discount comparison and steady-flow counterexample independently recomputed")

    invalid = []
    for path, value in [(("opening_kcu", "cash"), "31"), (("flows_kcu", "ordinary_collections"), "241"),
        (("flows_kcu", "recoveries"), "9"), (("flows_kcu", "writeoffs"), "91"),
        (("flows_kcu", "cost_of_sales"), "241"), (("flows_kcu", "payables_paid"), "171"),
        (("flows_kcu", "advances_earned"), "23"), (("flows_kcu", "other_expense_paid"), "63"),
        (("flows_kcu", "credit_sales"), 180.0), (("days",), True), (("days",), 89)]:
        changed = copy.deepcopy(data)
        obj = changed
        for key in path[:-1]: obj = obj[key]
        obj[path[-1]] = value
        invalid.append(changed)
    changed = copy.deepcopy(data); changed["aging"][0]["gross_kcu"] = "59"; invalid.append(changed)
    changed = copy.deepcopy(data); changed["aging"][0]["loss_fraction"] = "1.1"; invalid.append(changed)
    changed = copy.deepcopy(data); changed["aging"][0]["loss_fraction"] = "1/7"; invalid.append(changed)
    changed = copy.deepcopy(data); changed["alternative_calendar"][1]["date"] = "2025-01-31"; invalid.append(changed)
    changed = copy.deepcopy(data); changed["alternative_calendar"][0]["receipts_kcu"] = "71"; invalid.append(changed)
    for changed in invalid:
        try: lab.build_report(changed)
        except ValueError: pass
        else: raise AssertionError("invalid ledger/calendar contract accepted")
    with tempfile.TemporaryDirectory() as directory:
        for flags in ([], ["-O"]):
            run = subprocess.run([sys.executable, *flags, str(PROJECT)], cwd=directory, capture_output=True, text=True, timeout=10)
            need(run.returncode == 0 and not run.stderr and json.loads(run.stdout) == report, "portable CLI, with/without optimization")
        bad = Path(directory) / "bad.json"
        bad.write_text(json.dumps(invalid[7]), encoding="utf-8")
        run = subprocess.run([sys.executable, "-O", str(PROJECT), str(bad)], cwd=directory, capture_output=True, text=True, timeout=10)
        need(run.returncode == 2 and not run.stderr and json.loads(run.stdout)["status"] == "invalid_input", "unfunded ledger explicit CLI rejection under -O")
    checks.append("Sixteen meaningful unsupported/invalid ledger, precision and calendar contracts rejected; portable normal/optimized CLI equals quiet API")

    mutations = [("balance_sheet_kcu", "gross_receivables", "90"), ("income_kcu", "credit_loss_expense", "9"),
                 ("cash_flow_kcu", "net_indirect", "9"), ("alternative_calendar", "minimum_facility_kcu", "0")]
    for section, key, value in mutations:
        broken = copy.deepcopy(report); broken[section][key] = value
        try: reference(broken)
        except AssertionError: pass
        else: raise AssertionError("independent reference failed to catch report mutation")
    parser = Fragment(); text = CHAPTER.read_text(encoding="utf-8"); parser.feed(text)
    need(not parser.stack and parser.h1 == 0 and parser.worked >= 2 and parser.exercises == parser.solutions == 8, "chapter structure/counts")
    need(len(parser.ids) == len(set(parser.ids)), "unique HTML ids")
    for filename in (PROJECT.name, INPUT.name, "v07-c03-README.txt"):
        need(filename in parser.links and PROJECT.with_name(filename).is_file(), "flat artifact link: " + filename)
    proposals = json.loads((ROOT / "content/reviews/v07-c03-sources.json").read_text(encoding="utf-8"))
    need(len(proposals) == 5 and all(set(s) == {"id", "title", "url", "use", "checked", "verification"} for s in proposals), "source schema")
    need({"sources.html#" + s["id"] for s in proposals} <= set(parser.links), "all source routes")
    need("v07-c02.html" in parser.links and "curriculum.html#v07" in parser.links and "Delayed-check answer" in text and "Teach-back guide" in text, "prerequisite/extension and answered prompts")
    checks.append("Four economically consequential report mutations caught; chapter has three worked cases, eight matching solutions, answered prompts and flat source/artifact routes")
    return {"status": "passed", "checks": checks,
        "counts": {"generated_journals": 13, "zero_residuals": 14, "allowance_cases": allowance_cases,
            "writeoff_recovery_cases": writeoff_cases, "purchase_mix_cases": mix_cases, "calendar_permutations": len(facilities),
            "invalid_contracts": len(invalid), "report_mutations_caught": len(mutations), "exercises": parser.exercises, "worked_examples": parser.worked},
        "limitations": ["Bounded author numerical/structural audit; source scope and prompt interpretation require accompanying manuscript review.",
            "Recognition and loss fractions are supplied assumptions, not documentary evidence or current standards-compliance certification.",
            "Monthly conditional cash plans do not certify detailed subledger chronology or available credit.",
            "Visual, mobile and print UI QA remains pending; no visual claim."]}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True, allow_nan=False))
