"""Independent accounting, ratio, exercise and portability checks; quiet check()."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BOOK = Path(__file__).resolve().parents[1]
PROJECT = BOOK / "content/projects"


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def load_lab():
    spec = importlib.util.spec_from_file_location("v07_c09_lab", PROJECT / "v07-c09-analysis.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ledger_reference(data, depreciation):
    """Signed journal rather than lab's closing-balance formula construction."""
    raw = {k: F(v) for k, v in data["opening"].items()}
    rate = F(data["tax_rate"])
    accounts = {k: raw[k] for k in ("cash", "receivables", "inventory", "ppe")}
    accounts.update({k: -raw[k] for k in ("payables", "debt", "equity")})
    accounts["net_deferred_tax"] = rate * (raw["tax_base_ppe"] - raw["ppe"])
    need(sum(accounts.values()) == 0, "reference opening trial balance")
    tax_base = raw["tax_base_ppe"]
    outputs = []
    for i, source in enumerate(data["periods"]):
        p = {k: F(v) for k, v in source.items()}
        opening = dict(accounts)
        entries = []
        def post(label, movements):
            need(sum(movements.values()) == 0, "unbalanced journal: " + label)
            for account, value in movements.items():
                accounts[account] = accounts.get(account, F(0)) + value
            entries.append((label, movements))
        post("credit sales", {"receivables": p["sales"], "revenue": -p["sales"]})
        collected = accounts["receivables"] - p["receivables"]
        post("collect invoices", {"cash": collected, "receivables": -collected})
        purchased = p["inventory"] - accounts["inventory"] + p["cogs"]
        post("buy on credit", {"inventory": purchased, "payables": -purchased})
        post("recognize sold units", {"goods_expense": p["cogs"], "inventory": -p["cogs"]})
        paid = -accounts["payables"] - p["payables"]
        post("pay suppliers", {"payables": paid, "cash": -paid})
        post("operating payment", {"other_expense": p["other_opex"], "cash": -p["other_opex"]})
        post("interest payment", {"interest_expense": p["interest"], "cash": -p["interest"]})
        post("invest in equipment", {"ppe": p["capex"], "cash": -p["capex"]})
        post("allocate equipment", {"depreciation_expense": F(depreciation[i]), "ppe": -F(depreciation[i])})
        post("new borrowing", {"cash": p["borrowing"], "debt": -p["borrowing"]})
        post("repay principal", {"debt": p["debt_repayment"], "cash": -p["debt_repayment"]})
        post("dividend distribution", {"equity": p["dividends"], "cash": -p["dividends"]})
        taxable = -accounts["revenue"] - accounts["goods_expense"] - accounts["other_expense"] - accounts["interest_expense"] - p["tax_depreciation"]
        post("current tax", {"tax_expense": taxable * rate, "cash": -taxable * rate})
        tax_base += p["capex"] - p["tax_depreciation"]
        deferred_change = rate * (tax_base - accounts["ppe"]) - accounts["net_deferred_tax"]
        post("deferred tax", {"net_deferred_tax": deferred_change, "tax_expense": -deferred_change})
        income_accounts = [k for k in accounts if k == "revenue" or k.endswith("_expense")]
        ni = -sum(accounts[k] for k in income_accounts)
        ebit = -accounts["revenue"] - sum(accounts[k] for k in ("goods_expense", "other_expense", "depreciation_expense"))
        closing_entry = {k: -accounts[k] for k in income_accounts}
        closing_entry["equity"] = -ni
        post("close income", closing_entry)
        cfo = sum(moves.get("cash", F(0)) for label, moves in entries if label in {"collect invoices", "pay suppliers", "operating payment", "interest payment", "current tax"})
        need(sum(accounts.values()) == 0, "reference closing trial balance")
        need(accounts["cash"] - opening["cash"] == cfo - p["capex"] + p["borrowing"] - p["debt_repayment"] - p["dividends"], "journal cash classes")
        outputs.append({"balances": dict(accounts), "ni": ni, "ebit": ebit, "cfo": cfo, "tax_base": tax_base, "journal_entries": len(entries)})
    return outputs


def compare_ledger(data, result):
    count = 0
    for name, dep in [("baseline", [p["depreciation"] for p in data["periods"]]), ("alternative_depreciation", data["comparison_book_depreciation"])]:
        for i, ref in enumerate(ledger_reference(data, dep)):
            end = result[name]["balances"][i + 1]
            row = result[name]["periods"][i]
            for key in ("cash", "receivables", "inventory", "ppe"):
                need(F(end[key]) == ref["balances"][key], "journal asset " + key)
            for key in ("payables", "debt", "equity"):
                need(F(end[key]) == -ref["balances"][key], "journal claim " + key)
            need(F(end["dta"]) - F(end["dtl"]) == ref["balances"]["net_deferred_tax"], "journal deferred tax")
            need(F(end["tax_base_ppe"]) == ref["tax_base"], "journal tax-base roll")
            need(F(row["income"]["net_income"]) == ref["ni"] and F(row["income"]["ebit"]) == ref["ebit"], "journal income")
            need(F(row["cash_flow"]["cfo"]) == ref["cfo"], "journal operating cash")
            count += ref["journal_entries"]
    return count


def identities(case):
    for i, row in enumerate(case["periods"]):
        a, b = case["balances"][i:i + 2]
        q = row["ratios"]
        mean_assets = (F(a["assets"]) + F(b["assets"])) / 2
        mean_equity = (F(a["equity"]) + F(b["equity"])) / 2
        need(F(q["averages"]["assets"]) == mean_assets and F(q["averages"]["equity"]) == mean_equity, "matched average denominators")
        need(F(q["roe"]) == F(row["income"]["net_income"]) / mean_equity, "direct ROE")
        for factor_key, product_key in [("dupont_three_factors", "dupont_three_product"), ("dupont_five_factors", "dupont_five_product")]:
            value = F(1)
            for factor in q[factor_key]:
                value *= F(factor)
            need(value == F(q[product_key]) == F(q["roe"]), "DuPont exact cancellation")
        need(F(q["nopat_margin"]) * F(q["capital_turnover"]) == F(q["roic"]), "ROIC margin-turnover identity")
        for b in (a, b):
            need(F(b["assets"]) == F(b["liabilities"]) + F(b["equity"]), "balance sheet")
            operating = sum(F(b[k]) for k in ("receivables", "inventory", "ppe", "dta")) - F(b["payables"]) - F(b["dtl"])
            need(operating == F(b["invested_capital"]) == F(b["debt"]) + F(b["equity"]) - F(b["cash"]), "two capital constructions")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []; self.ol = []; self.counts = []; self.worked = 0; self.links = []; self.h1 = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1": self.h1 += 1
        if tag == "aside" and "worked" in attrs.get("class", "").split(): self.worked += 1
        if tag == "a": self.links.append(attrs.get("href", ""))
        if tag == "ol": self.ol.append(0)
        if tag == "li" and self.ol: self.ol[-1] += 1
        if tag not in {"br", "hr", "img", "input", "meta", "link"}: self.stack.append(tag)
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1] == tag, "balanced HTML fragment: " + tag)
        self.stack.pop()
        if tag == "ol": self.counts.append(self.ol.pop())


def exercise_checks():
    answers = {}
    mean_a, mean_e = F(100 + 140, 2), F(50 + 70, 2)
    need(F(12, 120) * (120 / mean_a) * (mean_a / mean_e) == F(1, 5), "exercise1 DuPont")
    answers["1"] = [F(1, 10), F(1), F(2), F(1, 5), F(6, 35), F(2), F(2, 5)]
    before = [F(120, 60), F(50, 60)]
    after = [F(100, 40), F(30, 40)]
    need(after[0] > before[0] and after[1] < before[1] and 10 + 5 - 18 == -3, "exercise2 opposed ratios/cash")
    answers["2"] = before + after + [F(10), F(-3)]
    dso, dio, dpo = F(360 * 100, 720), F(360) * F(265, 2) / 468, F(360) * F(145, 2) / 513
    false_dpo = F(360) * F(145, 2) / 468
    need((dso, dio, dpo, dso + dio - dpo, false_dpo - dpo) == (F(50), F(1325, 13), F(2900, 57), F(74875, 741), F(3625, 741)), "exercise3 matched turnover")
    answers["3"] = [F(513), F(498), dso, dio, dpo, dso + dio - dpo, false_dpo, false_dpo - dpo]
    lev = []
    for ebit in (15, 5):
        for debt in (0, 60):
            equity = 100 - debt
            ni = ebit - F(debt, 10)
            value = ni / equity
            need(value == F(ebit, 100) + (F(ebit, 100) - F(1, 10)) * F(debt, equity), "exercise4 leverage identity")
            lev.extend([ni, value])
    answers["4"] = lev
    need(F(165, 4) + 50 - 5 - 20 - 20 + 15 == F(245, 4), "exercise5 benefit undone")
    need(F(51) + 20 + 5 - 40 - 45 + 15 == 6, "exercise5 reversal undone")
    answers["5"] = [F(5), F(-5), F(165, 4), F(51), F(245, 4), F(6), F(5), F(1745, 8)]
    answers["6"] = [F(26), F(149, 4), F(455), F(410), F(51, 410), F(45), F(149, 600)]
    need(F(-2, -10) == F(1, 5) and F(-4, 2) == -2, "exercise7 signed quotient")
    answers["7"] = [F(1, 5), None, F(-2), None, F(0), F(-20)]
    peer_nopat = (72 - 12) * F(3, 4)
    need(peer_nopat / 320 == F(9, 64) > F(17, 140), "exercise8 normalized comparison")
    answers["8"] = [F(60), F(1, 10), peer_nopat, F(9, 64)]
    return {k: [str(v) if v is not None else None for v in values] for k, values in answers.items()}


def check():
    checks = []
    captured = io.StringIO()
    with redirect_stdout(captured), redirect_stderr(captured):
        lab = load_lab()
        data = json.loads((PROJECT / "v07-c09-inputs.json").read_text())
        result = lab.run(data)
    need(not captured.getvalue(), "quiet import and run")
    json.dumps(result, allow_nan=False)
    baseline = result["baseline"]; alternative = result["alternative_depreciation"]
    need(compare_ledger(data, result) == 60, "all sixty signed journal entries reviewed")
    for case in (baseline, alternative): identities(case)
    checks.append({"name": "Independent sixty-entry signed journal, complete statements and capital identities", "status": "pass"})
    b1, b2 = baseline["balances"][1:]
    need([F(b1[k]) for k in ("cash", "assets", "debt", "equity", "invested_capital")] == list(map(F, ["31.25", "461.25", 160, "236.25", 365])), "Year1 exact anchors")
    need([F(b2[k]) for k in ("cash", "assets", "debt", "equity", "invested_capital")] == list(map(F, ["17.25", "572.25", 250, "242.25", 475])), "Year2 exact anchors")
    q1, q2 = [p["ratios"] for p in baseline["periods"]]
    need(q1["roe"] == "90/349" and q2["roe"] == "48/319" and q1["roic"] == "27/137" and q2["roic"] == "17/140", "baseline returns")
    need(q1["asset_turnover"] == q2["asset_turnover"] == "960/689", "same turnover with changing margin and multiplier")
    need(q1["current_ratio"] == "59/28" and q2["current_ratio"] == "1169/600" and q2["quick_ratio"] == "183/200", "liquidity targets")
    aq1, aq2 = [p["ratios"] for p in alternative["periods"]]
    need(aq1["roe"] == "66/337" and aq2["roe"] == "68/309" and aq1["roic"] == "21/134" and aq2["roic"] == "4/25", "policy return targets")
    need(F(q1["roe"]) > F(q2["roe"]) and F(aq1["roe"]) < F(aq2["roe"]), "false comparability counterexample")
    need(sum(F(p["income"]["net_income"]) for p in baseline["periods"]) == sum(F(p["income"]["net_income"]) for p in alternative["periods"]) == F(369, 4), "lifetime income")
    need(baseline["balances"][-1] == alternative["balances"][-1], "terminal measurement agreement")
    checks.append({"name": "Exact two-period ratio anchors and reversed-trend policy counterexample", "status": "pass"})

    scenarios = []
    collection = deepcopy(data); collection["periods"][1]["receivables"] = 100
    collected = lab.run(collection); cr = collected["baseline"]; compare_ledger(collection, collected)
    cq = cr["periods"][1]["ratios"]
    need(cr["periods"][1]["cash_flow"]["cfo"] == "26" and cr["balances"][2]["cash"] == "149/4", "collection cash transfer")
    need(cq["roic"] == "51/410" and cq["dso"] == "45", "collection operating capital")
    for key in ("roe", "current_ratio", "quick_ratio", "asset_turnover"):
        need(cq[key] == q2[key], "collection invariant " + key)
    for key in ("assets", "equity"):
        need(cr["balances"][2][key] == b2[key], "collection balance invariant")
    scenarios.append("collections")
    squeeze = deepcopy(data); squeeze["periods"][1]["cogs"] = 486
    sr = lab.run(squeeze); compare_ledger(squeeze, sr)
    need(sr["baseline"]["periods"][1]["cash_flow"]["cfo"] == "-15/2" and sr["baseline"]["balances"][2]["cash"] == "15/4", "margin squeeze cash")
    need(sr["baseline"]["periods"][1]["ratios"]["roic"] == "5/56", "margin squeeze return")
    scenarios.append("cost pressure")
    repayment = deepcopy(data); repayment["periods"][1].update({"debt_repayment": 10, "current_debt": 60})
    rr = lab.run(repayment); compare_ledger(repayment, rr)
    rq = rr["baseline"]["periods"][1]["ratios"]
    need(rr["baseline"]["balances"][2]["cash"] == "29/4" and rq["current_ratio"] == "1129/560", "closing repayment")
    need(F(rq["current_ratio"]) > F(q2["current_ratio"]) and F(rq["quick_ratio"]) < F(q2["quick_ratio"]), "repayment ratio direction")
    need(rq["roic"] == q2["roic"] and rq["roe"] == q2["roe"], "closing finance does not change profit/capital")
    scenarios.append("closing debt repayment")
    retention = deepcopy(data); retention["periods"][1]["sales"] = 735
    rt = lab.run(retention); compare_ledger(retention, rt)
    rtp = rt["baseline"]["periods"][1]; rtb = rt["baseline"]["balances"][2]
    need([rtp["income"]["ebit"], rtp["income"]["net_income"], rtp["cash_flow"]["cfo"], rtb["cash"], rtb["equity"], rtp["ratios"]["roic"], rtp["ratios"]["roe"]] == ["83", "189/4", "69/4", "57/2", "507/2", "83/560", "126/653"], "retention full path")
    scenarios.append("answered retention")
    for tax in ("0", "1/5", "1/3"):
        changed = deepcopy(data); changed["tax_rate"] = tax
        r = lab.run(changed); compare_ledger(changed, r)
        for case in (r["baseline"], r["alternative_depreciation"]): identities(case)
        scenarios.append("tax " + tax)
    changed = deepcopy(data); changed["comparison_book_depreciation"] = [20, 50]
    r = lab.run(changed); compare_ledger(changed, r)
    need(r["alternative_depreciation"]["balances"][1]["dtl"] == "5/2", "opposite timing yields DTL")
    scenarios.append("opposite depreciation timing")
    scaled = deepcopy(data)
    for key in scaled["opening"]: scaled["opening"][key] *= 37
    for p in scaled["periods"]:
        for key in p: p[key] *= 37
    scaled["comparison_book_depreciation"] = [x * 37 for x in scaled["comparison_book_depreciation"]]
    r = lab.run(scaled); compare_ledger(scaled, r)
    for name in ("baseline", "alternative_depreciation"):
        for i in range(2):
            ratios = r[name]["periods"][i]["ratios"]
            for key in ("current_ratio", "quick_ratio", "roe", "roic", "asset_turnover", "dso", "dio", "dpo"):
                need(ratios[key] == result[name]["periods"][i]["ratios"][key], "scale-free ratio " + key)
    scenarios.append("currency-size scaling")
    checks.append({"name": "Nine economic, accounting and scale transfers independently reconciled", "status": "pass", "scenarios": scenarios})

    for denominator in (F(0), F(-10)):
        need(lab.ratio(F(-2), denominator) is None, "nonpositive denominator suppressed")
    need(lab.ratio(F(-4), F(2)) == -2 and lab.ratio(F(2), F(1, 1000000)) == 2000000, "signed numerator and visible near-zero denominator")
    need(lab.product([F(1), None]) is None, "undefined factor not repaired")
    zero = deepcopy(data)
    zero["periods"][1]["sales"] = 672
    zero["periods"][1]["borrowing"] = 110
    zero["comparison_book_depreciation"] = [30, 40]
    zr = lab.run(zero)
    zq = zr["baseline"]["periods"][1]["ratios"]
    need(zq["roe"] == "0" and zq["dupont_three_product"] == "0" and zq["dupont_five_product"] is None, "zero PBT: five-factor fails while direct/three survive")
    checks.append({"name": "Negative, zero and near-zero ratio boundaries with valid zero-profit transaction case", "status": "pass"})

    mutations = [
        ("units", lambda x: x.update(units="CU")),
        ("zero days", lambda x: x.update(days_per_period=0)),
        ("tax rate one", lambda x: x.update(tax_rate=1)),
        ("unproven tax support", lambda x: x.update(full_deferred_tax_recognition_supported=False)),
        ("cash convention", lambda x: x.update(cash_excluded_from_operating_capital=False)),
        ("opening mismatch", lambda x: x["opening"].update(equity=201)),
        ("debt classification", lambda x: x["periods"][1].update(current_debt=251)),
        ("tax/book loss", lambda x: x["periods"][0].update(sales=100)),
        ("negative collections", lambda x: x["periods"][0].update(receivables=1000)),
        ("negative supplier payments", lambda x: x["periods"][0].update(payables=1000)),
        ("implicit overdraft", lambda x: x["periods"][1].update(borrowing=0)),
        ("floating input", lambda x: x["periods"][0].update(sales=600.0)),
        ("boolean input", lambda x: x["periods"][0].update(sales=True)),
        ("nonfinite input", lambda x: x["periods"][0].update(sales="NaN")),
        ("unequal comparison allocation", lambda x: x.update(comparison_book_depreciation=[50, 21])),
        ("missing period", lambda x: x["periods"].pop()),
        ("unknown period field", lambda x: x["periods"][0].update(other_asset=4))
    ]
    for name, change in mutations:
        bad = deepcopy(data); change(bad)
        try: lab.run(bad)
        except ValueError: pass
        else: raise AssertionError("accepted invalid input: " + name)
    bad = deepcopy(data)
    bad["opening"].update(ppe=10, tax_base_ppe=10, equity=-10)
    bad["periods"][0]["capex"] = 0
    try: lab.run(bad)
    except ValueError as exc: need("depreciation exceeds" in str(exc), "explicit asset boundary detected")
    else: raise AssertionError("accepted overdepreciated asset")
    for name in ("wrong cash sign", "income-only policy adjustment"):
        broken = deepcopy(result)
        if name == "wrong cash sign": broken["baseline"]["periods"][1]["cash_flow"]["cfo"] = "86"
        else: broken["alternative_depreciation"]["balances"][1]["equity"] = "945/4"
        try: compare_ledger(data, broken)
        except AssertionError: pass
        else: raise AssertionError("independent audit missed " + name)
    checks.append({"name": "Eighteen unsupported-input failures and two material accounting-error detectors", "status": "pass"})

    answers = exercise_checks()
    checks.append({"name": "Eight exact exercise benchmarks plus funding and leverage reasoning", "status": "pass", "answers": answers})
    html = (BOOK / "content/chapters/v07-c09.html").read_text()
    fragment = Fragment(); fragment.feed(html); fragment.close()
    need(not fragment.stack and fragment.h1 == 0 and fragment.worked == 4 and fragment.counts == [8, 8], "four worked/eight prompt/eight solution fragment")
    records = json.loads((BOOK / "content/reviews/v07-c09-sources.json").read_text())
    ids = {record["id"] for record in records}
    cited = {href.split("#", 1)[1] for href in fragment.links if href.startswith("sources.html#")}
    need(len(records) == len(ids) == 4 and ids == cited, "four source proposals match exact citations")
    for file in ("v07-c09-inputs.json", "v07-c09-analysis.py", "v07-c09-README.txt"):
        need(file in fragment.links and (PROJECT / file).is_file(), "offline asset link")
    need("Teach-back benchmark" in html and "Delayed-check answer" in html, "answered teaching and retention")
    checks.append({"name": "Balanced chapter fragment, full practice and scoped source/asset links", "status": "pass"})

    with tempfile.TemporaryDirectory(prefix="v07-c09-check-") as directory:
        temp = Path(directory)
        for file in ("v07-c09-analysis.py", "v07-c09-inputs.json"):
            shutil.copy2(PROJECT / file, temp / file)
        for flags in ([], ["-O"]):
            process = subprocess.run([sys.executable, *flags, str(temp / "v07-c09-analysis.py")], cwd=temp.parent, capture_output=True, text=True, check=False)
            need(process.returncode == 0 and not process.stderr and json.loads(process.stdout) == result, "portable normal/optimized CLI")
        bad = deepcopy(data); bad["units"] = "USD"
        (temp / "bad.json").write_text(json.dumps(bad))
        process = subprocess.run([sys.executable, str(temp / "v07-c09-analysis.py"), str(temp / "bad.json")], cwd=temp.parent, capture_output=True, text=True, check=False)
        need(process.returncode == 2 and not process.stdout and "units must be kCU" in process.stderr, "CLI explicit failure without result")
    checks.append({"name": "Portable no-install CLI, optimized execution, quiet API and strict JSON", "status": "pass"})
    outcome = {"chapter": "v07-c09", "status": "pass", "checks": checks}
    json.dumps(outcome, allow_nan=False)
    return outcome


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
