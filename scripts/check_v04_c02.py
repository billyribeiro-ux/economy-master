"""Independent exact-arithmetic checks for v04-c02 and its offline benchmark.

The sensitivity formula is read from the manuscript and evaluated with a small,
restricted arithmetic interpreter. No spreadsheet application is launched.
"""
import ast
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "content/chapters/v04-c02.html"
PROJECTS = ROOT / "content/projects"


def near(actual, expected, absolute=1e-8):
    if not math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=absolute):
        raise AssertionError(f"{actual} differs from {expected}")


def npv(cash, rate):
    """Independent exact direct powers, unlike benchmark's discount recurrence."""
    return sum(F(c) / (1 + rate)**t for t, c in enumerate(cash))


def move_reference(reference, columns, rows):
    match = re.fullmatch(r"(\$?)([A-Z]+)(\$?)([0-9]+)", reference)
    assert match, reference
    col_lock, letters, row_lock, row_text = match.groups()
    col = 0
    for letter in letters:
        col = 26*col+ord(letter)-ord("A")+1
    if not col_lock:
        col += columns
    row = int(row_text)+(0 if row_lock else rows)
    assert col > 0 and row > 0
    letters = ""
    while col:
        col, remainder = divmod(col-1, 26)
        letters = chr(ord("A")+remainder)+letters
    return f"{col_lock}{letters}{row_lock}{row}"


def move_formula(formula, columns, rows):
    return re.sub(r"\$?[A-Z]+\$?[0-9]+",
                  lambda match: move_reference(match.group(), columns, rows), formula)


def arithmetic(formula, cells):
    """Only numeric arithmetic and explicitly supplied cell names are permitted."""
    expression = re.sub(r"\s+", "", formula).lstrip("=").replace("$", "").replace("^", "**")
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return F(str(node.value))
        if isinstance(node, ast.Name):
            return cells[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand)*(1 if isinstance(node.op, ast.UAdd) else -1)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return left+right
            if isinstance(node.op, ast.Sub): return left-right
            if isinstance(node.op, ast.Mult): return left*right
            if isinstance(node.op, ast.Div): return left/right
            if isinstance(node.op, ast.Pow):
                assert right.denominator == 1
                return left**int(right)
        raise AssertionError(f"Unsupported expression: {ast.dump(node)}")
    return visit(ast.parse(expression, mode="eval"))


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = 0
        self.exercise_count = 0
        self.solution_count = 0
        self.exercise_depth = 0
        self.solution_depth = 0
        self.depth = 0
        self.in_pre = False
        self.formula = ""
        self.links = []
        self.sources = set()
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1": self.h1 += 1
        if tag == "aside" and attrs.get("class") == "worked": self.worked += 1
        if tag == "a": self.links.append(attrs.get("href", ""))
        if "data-source" in attrs: self.sources.add(attrs["data-source"])
        if tag == "pre": self.in_pre = True
        if tag == "ol":
            self.depth += 1
            if attrs.get("class") == "exercises": self.exercise_depth = self.depth
            elif self.solution_depth == -1: self.solution_depth = self.depth
        if tag == "details" and attrs.get("class") == "solutions": self.solution_depth = -1
        if tag == "li":
            if self.exercise_depth == self.depth: self.exercise_count += 1
            if self.solution_depth == self.depth: self.solution_count += 1

    def handle_endtag(self, tag):
        if tag == "ol":
            if self.exercise_depth == self.depth: self.exercise_depth = 0
            if self.solution_depth == self.depth: self.solution_depth = 0
            self.depth -= 1
        if tag == "pre": self.in_pre = False

    def handle_data(self, data):
        if self.in_pre: self.formula += data


def check():
    checks = []
    text = MANUSCRIPT.read_text(encoding="utf-8")
    html = Manuscript()
    html.feed(text)
    assert html.worked >= 2 and html.exercise_count == 8 and html.solution_count == 8
    assert html.h1 == 0 and "Teach-back:" in text and "Delayed check:" in text
    assert html.sources == {"v04-c02-references", "v04-c02-npv"}
    for link in html.links:
        if link.startswith("v04-c02-") and not link.endswith(".html"):
            assert (PROJECTS / link).is_file(), link
    checks.append("HTML fragment: two worked examples, eight exercises/eight solutions, retention prompts, source identifiers and existing project links")

    translations = {"B5": "D8", "$B$5": "$B$5", "B$5": "D$5", "$B5": "$B8"}
    for original, expected in translations.items():
        assert move_reference(original, 2, 3) == expected
    assert move_formula("=B5*$B$2+C$3+$A5", 2, 3) == "=D8*$B$2+E$3+$A8"
    assert move_formula("=C13*$B$9", 2, 0) == "=E13*$B$9"
    assert move_formula("=1/(1+$B$2)^B12", 3, 0) == "=1/(1+$B$2)^E12"
    checks.append("Exact relative, absolute and mixed address translations, including the exercise formula and terminal-column copy")

    cash = [-12000, 3500, 4500, 8500]
    r = F(1, 10)
    expected = npv(cash, r)
    assert expected == F(1713000, 1331)
    near(expected, 1287.0022539444028)
    displayed = [round(float(F(c)/(1+r)**t), 2) for t, c in enumerate(cash)]
    assert displayed == [-12000.0, 3181.82, 3719.01, 6386.18]
    near(sum(displayed), 1287.01)
    near(expected/(1+r), 1170.002049040366)
    assert sum(F(c) for c in cash) == 4500
    wc_pv = -2000+F(2000)/(1+r)**3
    assert wc_pv < 0
    checks.append("Exact four-date cash-flow sum, each discounted component, shifted-time-zero error, display-rounding discrepancy and working-capital timing")

    cells = {"B3": F(12), "B4": F(7), "B5": F(1500), "B6": F(10000),
             "B7": F(2000), "B8": F(1000), "C13": F(1000), "D13": F(1200),
             "E13": F(1400), "C12": F(1), "D12": F(2), "E12": F(3),
             "G3": F(4, 5), "G4": F(1), "G5": F(6, 5),
             "H2": F(1, 20), "I2": F(1, 10), "J2": F(3, 20)}
    grid = []
    displayed_grid = [[-492.60, -1665.66, -2662.45], [2757.59, 1287.00, 35.01],
                      [6007.77, 4239.67, 2732.47]]
    for down, multiplier in enumerate((F(4, 5), F(1), F(6, 5))):
        row = []
        for across, interest in enumerate((F(1, 20), F(1, 10), F(3, 20))):
            # Independent decomposition: discounted revenues minus all payments,
            # plus terminal recoveries; not the manuscript's net-flow formula.
            annual = sum((multiplier*12*q-multiplier*7*q-1500)/(1+interest)**t
                         for t, q in enumerate((1000, 1200, 1400), 1))
            exact = -10000-2000+annual+F(2000)/(1+interest)**3+F(1000)/(1+interest)**3
            copied = move_formula(html.formula, across, down)
            assert arithmetic(copied, cells) == exact
            near(round(float(exact), 2), displayed_grid[down][across])
            row.append(exact)
        assert row[0] > row[1] > row[2]
        grid.append(row)
    assert grid[1][1] == expected
    for across in range(3): assert grid[0][across] < grid[1][across] < grid[2][across]
    contribution = sum(F(5*q)/(1+r)**t for t, q in enumerate((1000, 1200, 1400), 1))
    constant = -12000-sum(F(1500)/(1+r)**t for t in (1, 2, 3))+F(3000)/(1+r)**3
    threshold = -constant/contribution
    near(contribution, 14763.335837716004)
    near(constant, -13476.3335837716)
    near(threshold, 0.9128244274809161)
    assert contribution*threshold+constant == 0
    near(contribution*F(9, 10)+constant, -189.3313298271976)
    near(contribution*F(11, 10)+constant, 2763.335837716003)
    checks.append("Manuscript sensitivity formula copied to all nine cells and evaluated exactly against separate revenue/payment components; directional checks and break-even derivation")

    assert 2500+8200-5400-2100-1800 == 1400
    assert 1175-1400 == -225
    assert 5400+225 == 5625 and 5625+2100+1800 == 9525
    assert 2500+8200-9525 == 1175
    assert 2500+8700-6125-2100-1800 == 1175
    assert 600+1250-720-450 == 680 and 650-680 == -30
    assert 600+1250-720-450-30 == 650
    assert 1250+120 == 1370 and 720+120+450+30 == 1320
    assert 600+1370-1320 == 650
    checks.append("Both bank reconciliations, gross payment sums, correction signs and two offsetting-error counterexamples")

    good = npv([-6000, 0, 2500, 4500], r)
    bad = npv([-6000, 2500, 4500], r)
    near(good, -552.9676934635612)
    near(bad, -8.264462809917354)
    near(bad-good, 544.703230653643)
    revised = npv([-12000, 3500, 4500, 7000], r)
    near(revised, 160.03005259203607)
    near(expected-revised, 1126.9722013523667)
    monthly = 1.12**(1/12)-1
    near(monthly, .009488792934583046)
    near(1200/(1+monthly)**12, F(1200)/F(112, 100))
    near(1200/1.12, 1071.4285714285713)
    near(1200/(1.01**12), 1064.9390703181843)
    near((1.01**12-1)*100, 12.682503013196978)
    near(npv([-12500, 3500, 4500, 8500], r), 787.0022539444028)
    delayed = npv([-12000, 0, 8000, 8500], r)
    near(delayed, 997.7460555972953)
    near(delayed-expected, -289.25619834710744)
    checks.append("All determinate exercise arithmetic: omitted zero year, reduced recoveries, sensitivity levels, annual/monthly rate convention and capex/delay/zero-rate perturbations")

    spec = importlib.util.spec_from_file_location("v04_c02_benchmark", PROJECTS / "v04-c02-benchmark.py")
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    inputs = json.loads((PROJECTS / "v04-c02-inputs.json").read_text(encoding="utf-8"))
    result = benchmark.run(inputs)
    assert [row["cash_flow"] for row in result["base_case"]["timeline"]] == cash
    near(result["base_case"]["npv"], expected)
    for j, row in enumerate(result["sensitivity"]):
        for k, case in enumerate(row["cases"]): near(case["npv"], grid[j][k])
    assert result["bank_reconciliation"] == {
        "recorded_total_payments": 9300.0, "predicted_closing_cash": 1400.0,
        "residual_before": -225.0, "corrected_closing_cash": 1175.0,
        "residual_after": 0.0}
    p = inputs["project"]
    for interest in (F(-1, 2), F(0), F(1, 10), F(1)):
        near(benchmark.project(p, float(interest))["npv"], npv(cash, interest))
    altered = deepcopy(p)
    altered["initial_equipment_outlay"] += 500
    near(benchmark.project(altered)["npv"], expected-500)
    altered = deepcopy(p)
    altered["terminal_working_capital_recovery"] = 1000
    altered["terminal_equipment_receipt"] = 500
    near(benchmark.project(altered)["npv"], revised)
    assert benchmark.project(altered)["working_capital_net_cash"] == -1000
    near(benchmark.project(p, quantity_multiplier=0)["npv"], constant)
    invalid = [("discount_rate", -1), ("discount_rate", -1.01), ("discount_rate", float("nan")),
               ("price_per_unit", True), ("price_per_unit", "12"), ("price_per_unit", None),
               ("variable_cost_per_unit", -1), ("quantity_multiplier", -1),
               ("base_annual_units", [1000, 1200]), ("base_annual_units", [1000, None, 1400])]
    for field, value in invalid:
        altered = deepcopy(p)
        altered[field] = value
        try:
            benchmark.project(altered)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid {field} was accepted")
    checks.append("Offline benchmark agrees with independent rational values for base/scenarios/changed recovery and boundaries; malformed, missing, boolean, negative and nonfinite inputs rejected")
    return {"status": "passed", "checks": checks,
            "limitations": ["Author's independent arithmetic routes, not external academic certification.",
                            "Formula translation/interpreting covers the chapter's arithmetic subset; no spreadsheet engine or GUI was tested.",
                            "Synthetic scenarios and accounting identities do not validate forecasts, discount rates or completeness of a real ledger.",
                            "Browser visual/mobile/print QA remains pending under the existing browser-policy restriction."]}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
