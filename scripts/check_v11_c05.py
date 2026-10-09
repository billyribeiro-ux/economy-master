"""Independent finite accounting/valuation checks for the C05 author package."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
CHAPTER = "v11-c05"
PAYLOADS = ["v11-c05-inputs.json", "v11-c05-analysis.py", "v11-c05-output.json", "v11-c05-README.txt"]
OWNED = ["content/chapters/v11-c05.html"] + ["content/projects/" + n for n in PAYLOADS[:3]] + ["content/projects/v11-c05-manifest.json", "content/projects/v11-c05-README.txt", "scripts/check_v11_c05.py", "content/reviews/v11-c05-sources.json"]


def _digest(path):
    b = path.read_bytes()
    return len(b), hashlib.sha256(b).hexdigest()


class _Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.solutions, self.sources, self.links = [], [], [], []
        self.exercise_lists = 0
        self.worked_containers = 0
        self.solution_wrapper = False
        self.reader_solution_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "worked" in a.get("class", "").split():
            self.worked_containers += 1
        if tag == "details" and "solutions" in a.get("class", "").split():
            self.solution_wrapper = True
        if tag == "li" and self.solution_wrapper:
            self.reader_solution_count += 1
        if "id" in a:
            self.ids.append(a["id"])
        if "data-solution-for" in a:
            self.solutions.append(a["data-solution-for"])
        if "data-source" in a:
            self.sources.append(a["data-source"])
        if "href" in a:
            self.links.append(a["href"])
        if tag == "ol" and "exercises" in a.get("class", "").split():
            self.exercise_lists += 1

    def handle_endtag(self, tag):
        if tag == "details":
            self.solution_wrapper = False


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    project = root / "content/projects"
    tally = {"comparisons": 0, "financial_interventions": 0, "api_rejections": 0, "cli_rejections": 0, "valid_cli_runs": 0, "journal_rows": 0, "cutoff_rows": 0, "author_bindings": 0}

    def require(condition, message):
        tally["comparisons"] += 1
        if not condition:
            raise RuntimeError(message)

    def same(actual, expected, message):
        require(actual == expected, message + ": " + str(actual) + " != " + str(expected))

    def qsame(actual, expected, message):
        same(F(actual), expected, message)

    data = json.loads((project / PAYLOADS[0]).read_text())
    spec = importlib.util.spec_from_file_location("v11_c05_checked", project / PAYLOADS[1])
    module = importlib.util.module_from_spec(spec)
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        spec.loader.exec_module(module)
    same(capture.getvalue(), "", "quiet import")

    def call(d):
        before = deepcopy(d)
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = module.run(d)
        same(output.getvalue(), "", "quiet API")
        same(d, before, "nonmutating API")
        return result

    report = call(data)
    same(report, json.loads((project / PAYLOADS[2]).read_text()), "saved report")

    # Independent stock equations, rather than replaying the implementation's
    # event loop, provide every cutoff's cash, principal, income and equity.
    def oracle(d, out, detailed=False):
        o = {k: F(v) for k, v in d["opening"].items()}
        p = {k: F(v) for k, v in d["policy"].items()}
        b = p["upfront_cash_equity"]
        units = o["eligible_units"] + o["already_pledged_units"] + o["inaccessible_units"]
        equity0 = o["cash"] + o["loans"] + units * o["security_book_per_unit"] + o["initial_margin"] - o["deposits"] - o["legacy_principal"] - o["legacy_interest_payable"] - o["other_liabilities"]
        qsame(out["opening_book_equity"], equity0, "opening equity")
        requirements = []
        all_headrooms = []
        same(len(out["scenarios"]), len(d["scenarios"]), "scenario count")
        for raw, result in zip(d["scenarios"], out["scenarios"]):
            values = {k: F(v) for k, v in raw.items() if isinstance(v, str) and k != "name"}
            vectors = {k: list(map(F, v)) for k, v in raw.items() if isinstance(v, list)}
            same(result["name"], raw["name"], "scenario order")
            cap0 = o["eligible_units"] * p["initial_security_price"] * (1 - p["initial_haircut"])
            initial = min(p["secured_target"], cap0) * values["secured_offer_fraction"]
            cap2 = o["eligible_units"] * values["maintenance_price"] * (1 - values["maintenance_haircut"])
            remaining = min(initial, cap2)
            term = o["legacy_principal"] * values["rollover_fraction"]
            int_sec = p["secured_interval_rate"] * (initial + 2 * remaining)
            int_term = 3 * term * p["rollover_interval_rate"]
            for key, expected in (("initial_secured_capacity", cap0), ("secured_draw", initial), ("maintenance_capacity", cap2), ("collateral_principal_paydown", initial - remaining), ("rollover_draw", term), ("secured_interest_total", int_sec), ("rollover_interest_total", int_term)):
                qsame(result[key], expected, raw["name"] + " " + key)
            headrooms = []
            same(len(result["rows"]), 4, "four cutoff rows")
            for index, row in enumerate(result["rows"], 1):
                line = values["customer_line_draw"] if index >= 2 else F(0)
                loan_received = sum(vectors["loan_principal_receipts"][:index])
                withdrawals = sum(vectors["deposit_withdrawals"][:index])
                other_paid = sum(vectors["other_liability_payments"][:index])
                variation = sum(vectors["variation_settlements"][:index])
                margin = vectors["initial_margin_targets"][index - 1]
                collateral_repaid = initial - remaining if index >= 2 else F(0)
                accrued = F(0) if index == 1 else p["secured_interval_rate"] * (initial + (index - 2) * remaining) + (index - 1) * term * p["rollover_interval_rate"]
                final_paid = remaining + term + int_sec + int_term if index == 4 else F(0)
                cash = o["cash"] + b + initial + term - o["legacy_principal"] - o["legacy_interest_payable"] + loan_received - withdrawals - other_paid + variation - (margin - o["initial_margin"]) - line - collateral_repaid - final_paid
                eq = equity0 + b + variation - accrued
                expected_state = {"cash": cash, "loans": o["loans"] - loan_received + line, "securities_book": units * o["security_book_per_unit"], "initial_margin": margin, "deposits": o["deposits"] - withdrawals, "legacy_principal": F(0), "legacy_interest_payable": F(0), "other_liabilities": o["other_liabilities"] - other_paid, "rollover_principal": term if index < 4 else F(0), "secured_principal": (initial if index == 1 else remaining) if index < 4 else F(0), "new_interest_payable": accrued if index < 4 else F(0), "equity": eq}
                same(set(row["state"]), set(expected_state), "state accounts")
                for key, expected in expected_state.items():
                    qsame(row["state"][key], expected, raw["name"] + " cutoff " + str(index) + " " + key)
                assets = cash + expected_state["loans"] + expected_state["securities_book"] + margin
                qsame(row["total_assets"], assets, "cutoff total assets")
                qsame(row["total_liabilities"], assets - eq, "cutoff total liabilities")
                head = cash - o["restricted_cash"]
                headrooms.append(head)
                qsame(row["available_cash"], head, "available cash")
                qsame(row["available_cash_without_buffer"], head - b, "independent reserve effect")
                qsame(row["cash_gap"], max(F(0), -head), "cash gap")
                price = p["initial_security_price"] if index == 1 else values["maintenance_price"]
                hair = p["initial_haircut"] if index == 1 else values["maintenance_haircut"]
                principal = expected_state["secured_principal"]
                pledged = principal / (price * (1 - hair))
                qsame(row["new_pledged_units"], pledged, "collateral amount")
                qsame(row["free_eligible_units"], o["eligible_units"] - pledged, "remaining deliverable inventory")
                qsame(row["already_pledged_units"], o["already_pledged_units"], "excluded encumbrance")
                qsame(row["inaccessible_units"], o["inaccessible_units"], "excluded custody")
                qsame(row["marked_equity"], eq + units * (price - o["security_book_per_unit"]), "conditional market mark")
                qsame(row["balance_error"], F(0), "cutoff conservation")
                if detailed:
                    tally["cutoff_rows"] += 1
            need = max([F(0)] + [b - x for x in headrooms])
            requirements.append(need)
            all_headrooms.append(headrooms)
            qsame(result["required_upfront_cash"], need, "scenario cash minimum")
            qsame(result["additional_cash_needed"], max(F(0), need - b), "scenario extra cash")
            same(result["first_failure_cutoff"], next((i for i, h in enumerate(headrooms, 1) if h < 0), None), "first deadline failure")
            same(result["feasible_under_fixed_policy"], all(h >= 0 for h in headrooms), "scenario feasibility")
            if detailed:
                # Journal conservation independently from successive totals.
                assets = o["cash"] + o["loans"] + units * o["security_book_per_unit"] + o["initial_margin"]
                liabilities = assets - equity0
                eq = equity0
                akeys = {"cash", "loans", "securities_book", "initial_margin"}
                for entry in result["journal"]:
                    changes = {k: F(v) for k, v in entry["changes"].items()}
                    assets += sum(v for k, v in changes.items() if k in akeys)
                    liabilities += sum(v for k, v in changes.items() if k not in akeys and k != "equity")
                    eq += changes.get("equity", F(0))
                    same(assets, liabilities + eq, "independent event conservation")
                    qsame(entry["cash_flow"], changes.get("cash", F(0)), "journal cash")
                    qsame(entry["equity_change"], changes.get("equity", F(0)), "journal income versus cash")
                    qsame(entry["assets_after"], assets, "journal assets")
                    qsame(entry["liabilities_after"], liabilities, "journal liabilities")
                    qsame(entry["equity_after"], eq, "journal equity")
                    qsame(entry["balance_error"], F(0), "journal reported balance")
                    if entry["event"] not in ("upfront_cash_equity", "variation_settlement", "funding_interest_accrual"):
                        qsame(entry["equity_change"], F(0), "principal and margin are not income")
                    tally["journal_rows"] += 1
                qsame(result["rows"][-1]["total_assets"], assets, "journal reaches cutoff assets")
                qsame(result["rows"][-1]["total_liabilities"], liabilities, "journal reaches cutoff liabilities")
                qsame(result["rows"][-1]["state"]["equity"], eq, "journal reaches cutoff equity")
        minimum = max(requirements)
        certificate = out["fixed_policy_certificate"]
        qsame(certificate["required_upfront_cash"], minimum, "common cash certificate")
        qsame(certificate["additional_cash_needed"], max(F(0), minimum - b), "common additional cash")
        same(certificate["all_scenarios_feasible"], all(h >= 0 for hs in all_headrooms for h in hs), "common feasibility")
        binding = [{"scenario": s["name"], "cutoff": j} for s, hs in zip(d["scenarios"], all_headrooms) for j, h in enumerate(hs, 1) if b - h == minimum and minimum > 0]
        same(certificate["binding_cutoffs"], binding, "binding prefix certificate")
        return all_headrooms

    oracle(data, report, True)
    expected_heads = [[F("33.6"), F("38.6"), F("48.6"), F("27.1")], [F("-6.4"), F("-1.4"), F("8.6"), F("27.7")], [F("-13.4"), F("-39.9"), F("-29.9"), F("3.81")]]
    for result, expected in zip(report["scenarios"], expected_heads):
        same([F(r["available_cash"]) for r in result["rows"]], expected, "worked cash ladder")

    # Backward discount recursion and its differentiated recursion are separate
    # oracles for the implementation's forward finite sums.
    def bond(face, coupon, years, y):
        value, derivative = face, F(0)
        for _ in range(years):
            derivative = derivative / (1 + y) - (value + coupon) / (1 + y)**2
            value = (value + coupon) / (1 + y)
        return value, derivative

    def alm_oracle(d, out):
        a = {k: F(v) for k, v in d["alm"].items()}
        for row, label in zip(out["alm"], ("base", "shock")):
            y = a[label + "_yield"]
            av, ad = bond(a["asset_face"], a["asset_face"] * a["asset_coupon_rate"], int(a["asset_years"]), y)
            lv, ld = bond(a["fixed_liability_face"], a["fixed_liability_face"] * a["fixed_liability_coupon_rate"], int(a["liability_years"]), y)
            for key, expected in (("asset_pv", av), ("fixed_liability_pv", lv), ("floating_liability_pv", a["floating_liability_face"]), ("economic_equity", a["cash"] + av - lv - a["floating_liability_face"]), ("asset_yield_derivative", ad), ("fixed_liability_yield_derivative", ld), ("economic_equity_yield_derivative", ad - ld), ("nii_yield_derivative", -a["floating_liability_face"]), ("next_year_interest_income_net", a["asset_face"] * a["asset_coupon_rate"] - a["fixed_liability_face"] * a["fixed_liability_coupon_rate"] - a["floating_liability_face"] * y)):
                qsame(row[key], expected, "ALM " + label + " " + key)
    alm_oracle(data, report)
    require(F(report["alm"][1]["economic_equity"]) > F(report["alm"][0]["economic_equity"]), "EVE rises")
    require(F(report["alm"][1]["next_year_interest_income_net"]) < F(report["alm"][0]["next_year_interest_income_net"]), "NII falls")
    same(report["currency_case"], {"potential_converted_cu": "10", "no_authorized_transfer_headroom": "-8", "authorized_timely_transfer_headroom": "2", "authorized_late_transfer_headroom_at_deadline": "-8", "authorized_late_transfer_headroom_after_receipt": "2"}, "FX rights and timing")

    def changed(path, value):
        x = deepcopy(data)
        target = x
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return x

    interventions = [
        ("binding equality", changed(("policy", "upfront_cash_equity"), "39.9")),
        ("one cent below boundary", changed(("policy", "upfront_cash_equity"), "39.89")),
        ("larger haircut", changed(("scenarios", 2, "maintenance_haircut"), "0.5")),
        ("higher price avoids paydown", changed(("scenarios", 2, "maintenance_price"), "0.9")),
        ("no secured access", changed(("scenarios", 2, "secured_offer_fraction"), "0")),
        ("full customer line", changed(("scenarios", 2, "customer_line_draw"), "15")),
        ("no customer draw", changed(("scenarios", 2, "customer_line_draw"), "0")),
        ("larger segregated margin", changed(("scenarios", 2, "initial_margin_targets"), ["5", "11", "11", "0"])),
        ("earlier margin return", changed(("scenarios", 2, "initial_margin_targets"), ["5", "9", "0", "0"])),
        ("late loan receipt", changed(("scenarios", 2, "loan_principal_receipts"), ["0", "0", "18", "52"])),
        ("all opening cash restricted", changed(("opening", "restricted_cash"), "20")),
        ("request exceeds initial capacity", changed(("policy", "secured_target"), "100")),
    ]
    late_pool = changed(("opening", "eligible_units"), "37.5")
    late_pool["opening"]["inaccessible_units"] = "22.5"
    interventions.append(("smaller deliverable pool", late_pool))
    no_assets = deepcopy(data)
    for k in no_assets["opening"]:
        no_assets["opening"][k] = "0"
    for s in no_assets["scenarios"]:
        s["customer_line_draw"] = "0"
        for k in ("loan_principal_receipts", "deposit_withdrawals", "other_liability_payments", "variation_settlements", "initial_margin_targets"):
            s[k] = ["0"] * 4
    interventions.append(("zero stock inventory", no_assets))
    for label, mutation in interventions:
        out = call(mutation)
        heads = oracle(mutation, out)
        if label == "binding equality":
            same(heads[2], list(map(F, ["26.5", "0", "10", "43.71"])), label)
            same(out["fixed_policy_certificate"]["all_scenarios_feasible"], True, label)
        elif label == "one cent below boundary":
            same(heads[2][1], F("-0.01"), label)
            same(out["scenarios"][2]["first_failure_cutoff"], 2, label)
        elif label == "late loan receipt":
            qsame(out["fixed_policy_certificate"]["required_upfront_cash"], F("51.9"), label)
            same(heads[2][-1], F("3.81"), "late receipt preserves terminal cash")
        elif label == "smaller deliverable pool":
            qsame(out["scenarios"][2]["collateral_principal_paydown"], F("11.625"), label)
        elif label == "zero stock inventory":
            same(out["fixed_policy_certificate"]["all_scenarios_feasible"], True, label)
        tally["financial_interventions"] += 1
    for y in ("-0.1", "0", "0.25"):
        mutation = changed(("alm", "shock_yield"), y)
        mutation["alm"]["asset_years"] = 1
        mutation["alm"]["liability_years"] = 10
        alm_oracle(mutation, call(mutation))
        tally["financial_interventions"] += 1
    fx = changed(("currency_case", "foreign_cash"), "7")
    fx["currency_case"]["cu_per_fu"] = "1.2"
    output = call(fx)["currency_case"]
    qsame(output["authorized_timely_transfer_headroom"], F("0.4"), "transfer exercise")
    qsame(output["authorized_late_transfer_headroom_at_deadline"], F(-8), "late transfer exercise")
    tally["financial_interventions"] += 1
    # Closed-form exercise boundaries, checked without the lab's cash certificate.
    same(1 - F(30) / (50 * F("0.7")), F(1, 7), "haircut threshold")
    early_minimum = max(-x for hs in expected_heads for x in hs[:3])
    terminal_minimum = min(hs[3] for hs in expected_heads)
    same(early_minimum, F("39.9"), "bridge early constraint")
    same(terminal_minimum / F("0.02"), F("190.5"), "bridge maturity ceiling")
    require(terminal_minimum / F("0.1") < early_minimum, "expensive bridge infeasible")
    same(terminal_minimum - F("0.02") * early_minimum, F("3.012"), "bridge endpoint remaining cash")

    # Deliberately invalid input families, not just examples of valid cases.
    invalid = [None, [], {}, changed(("schema_version",), True), changed(("schema_version",), 2)]
    for value in (1, 1.0, True, None, "NaN", "Infinity", "1e2", " 20", "+20", "020", "1/0", "0.0000000000001", "9" * 33, "1000001", "-1"):
        invalid.append(changed(("opening", "cash"), value))
    invalid += [changed(("opening", "restricted_cash"), "21"), changed(("opening", "security_book_per_unit"), "11"), changed(("opening", "eligible_units"), "1000000"), changed(("opening", "deposits"), "1000"), changed(("policy", "initial_security_price"), "0"), changed(("policy", "initial_haircut"), "0.96"), changed(("policy", "secured_interval_rate"), "-0.01"), changed(("policy", "rollover_interval_rate"), "0.11"), changed(("scenarios",), []), changed(("scenarios",), data["scenarios"] * 3), changed(("scenarios", 1, "name"), "base"), changed(("scenarios", 0, "name"), "Bad name"), changed(("scenarios", 0, "rollover_fraction"), "1.1"), changed(("scenarios", 0, "secured_offer_fraction"), "-0.1"), changed(("scenarios", 0, "maintenance_price"), "0"), changed(("scenarios", 0, "maintenance_haircut"), "1"), changed(("scenarios", 0, "loan_principal_receipts"), ["0"]), changed(("scenarios", 0, "loan_principal_receipts"), ["0", "0", "0", "151"]), changed(("scenarios", 0, "deposit_withdrawals"), ["0", "0", "0", "161"]), changed(("scenarios", 0, "other_liability_payments"), ["0", "0", "0", "31"]), changed(("scenarios", 0, "customer_line_draw"), "16"), changed(("scenarios", 0, "initial_margin_targets"), ["5", "5", "5", "1"]), changed(("scenarios", 0, "variation_settlements"), ["-1000001", "0", "0", "0"]), changed(("alm", "asset_years"), True), changed(("alm", "asset_years"), 0), changed(("alm", "liability_years"), 11), changed(("alm", "base_yield"), "-0.11"), changed(("alm", "shock_yield"), "0.26"), changed(("alm", "asset_coupon_rate"), "0.21"), changed(("currency_case", "cu_per_fu"), "0")]
    for section in (None, "opening", "policy", "alm", "currency_case"):
        mutation = deepcopy(data)
        target = mutation if section is None else mutation[section]
        target["unexpected"] = "1"
        invalid.append(mutation)
    missing = deepcopy(data)
    del missing["scenarios"][0]["customer_line_draw"]
    invalid.append(missing)
    for bad in invalid:
        before = deepcopy(bad)
        quiet = io.StringIO()
        try:
            with redirect_stdout(quiet), redirect_stderr(quiet):
                module.run(bad)
        except ValueError:
            tally["api_rejections"] += 1
        else:
            raise RuntimeError("invalid API input was accepted")
        same(quiet.getvalue(), "", "quiet rejection")
        same(bad, before, "nonmutating rejection")

    # Content structure and byte bindings; subject-matter reading is separately
    # recorded in the author audit, not inferred from these structural checks.
    markup = _Markup()
    markup.feed((root / "content/chapters/v11-c05.html").read_text())
    same(len(markup.ids), len(set(markup.ids)), "unique chapter IDs")
    same(markup.exercise_lists, 1, "reader exercise list")
    exercise_ids = [CHAPTER + "-e" + str(i) for i in range(1, 9)]
    same([x for x in markup.ids if x in exercise_ids], exercise_ids, "eight exact prompts")
    same(markup.solutions, exercise_ids, "eight exact full solutions")
    same(len([i for i in markup.ids if i.startswith("worked-")]), 4, "four worked cases")
    same(markup.worked_containers, 4, "four reader-counted worked containers")
    same(markup.reader_solution_count, 8, "eight reader-counted solutions")
    expected_assets = set(PAYLOADS + ["v11-c05-manifest.json"])
    same({h for h in markup.links if h.startswith("v11-c05-")}, expected_assets, "flat reader assets")
    require(not any(h.startswith("projects/") for h in markup.links), "no invalid reader asset prefix")
    sources = json.loads((root / "content/reviews/v11-c05-sources.json").read_text())
    same(set(markup.sources), {s["id"] for s in sources}, "exact source routes")
    manifest = json.loads((project / "v11-c05-manifest.json").read_text())
    same([r["file"] for r in manifest["files"]], PAYLOADS, "four manifest payloads")
    for item in manifest["files"]:
        same(_digest(project / item["file"]), (item["bytes"], item["sha256"]), "payload binding " + item["file"])
    author = json.loads((root / "content/reviews/v11-c05-author.json").read_text())
    same([r["path"] for r in author["reviewed_hashes"]], OWNED, "eight nonself author bindings")
    for item in author["reviewed_hashes"]:
        same(_digest(root / item["path"]), (item["bytes"], item["sha256"]), "author binding " + item["path"])
        tally["author_bindings"] += 1

    # Isolated model CLI and destructive-alias guards, tested in both modes.
    with tempfile.TemporaryDirectory(prefix="v11-c05-check-") as directory:
        tmp = Path(directory)
        implementation = tmp / PAYLOADS[1]
        input_file = tmp / PAYLOADS[0]
        shutil.copy2(project / PAYLOADS[1], implementation)
        shutil.copy2(project / PAYLOADS[0], input_file)
        for optimized in (False, True):
            prefix = [sys.executable] + (["-O"] if optimized else []) + [str(implementation)]
            output_file = tmp / ("out-opt.json" if optimized else "out-normal.json")
            process = subprocess.run(prefix + ["--input", str(input_file), "--output", str(output_file)], cwd=tmp, text=True, capture_output=True, timeout=20)
            same((process.returncode, process.stdout, process.stderr), (0, "", ""), "quiet portable CLI")
            same(output_file.read_bytes(), (project / PAYLOADS[2]).read_bytes(), "portable saved bytes")
            tally["valid_cli_runs"] += 1
            stdout_run = subprocess.run(prefix, cwd=tmp, text=True, capture_output=True, timeout=20)
            same((stdout_run.returncode, stdout_run.stderr), (0, ""), "default-input CLI")
            same(json.loads(stdout_run.stdout), report, "stdout JSON only")
            tally["valid_cli_runs"] += 1
            for protected in (input_file, implementation):
                for alias_kind in ("direct", "resolved", "symlink", "hardlink"):
                    alias = protected if alias_kind == "direct" else tmp / (protected.name + "." + alias_kind)
                    if alias_kind == "resolved":
                        (tmp / "nested").mkdir(exist_ok=True)
                        alias = tmp / "nested" / ".." / protected.name
                    elif alias != protected:
                        if alias.exists() or alias.is_symlink():
                            alias.unlink()
                        if alias_kind == "symlink":
                            alias.symlink_to(protected)
                        else:
                            os.link(protected, alias)
                    original = protected.read_bytes()
                    rejected = subprocess.run(prefix + ["--input", str(input_file), "--output", str(alias)], cwd=tmp, text=True, capture_output=True, timeout=20)
                    same(rejected.returncode, 2, "CLI alias rejected")
                    same(rejected.stdout, "", "CLI alias quiet stdout")
                    require(bool(rejected.stderr), "CLI alias explains rejection")
                    same(protected.read_bytes(), original, "CLI alias preserved bytes")
                    tally["cli_rejections"] += 1
            for raw in ('{"schema_version":1,"schema_version":1}', '{"x":NaN}', '{', json.dumps(invalid[4]), " " * 100001):
                bad_input = tmp / "bad.json"
                bad_input.write_text(raw)
                sentinel = tmp / "sentinel.json"
                sentinel.write_text("preserve me")
                rejected = subprocess.run(prefix + ["--input", str(bad_input), "--output", str(sentinel)], cwd=tmp, text=True, capture_output=True, timeout=20)
                same(rejected.returncode, 2, "strict CLI input rejection")
                same(rejected.stdout, "", "invalid CLI quiet stdout")
                require(bool(rejected.stderr), "invalid CLI stderr")
                same(sentinel.read_text(), "preserve me", "invalid CLI preserves destination")
                tally["cli_rejections"] += 1
    return {"chapter": CHAPTER, "status": "passed", **tally}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.root), sort_keys=True))


if __name__ == "__main__":
    main()
