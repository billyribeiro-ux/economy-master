"""Separate peer certificates for the frozen C07 stress and funding package."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
AUTHOR = ["content/chapters/v11-c07.html"]+["content/projects/v11-c07-"+s for s in ("inputs.json", "analysis.py", "output.json", "manifest.json", "README.txt")]+["scripts/check_v11_c07.py", "content/reviews/v11-c07-author.json", "content/reviews/v11-c07-sources.json"]


def wire(x):
    if isinstance(x, F): return str(x)
    if isinstance(x, dict): return {k: wire(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [wire(v) for v in x]
    return x


def numbers(d):
    return {k: F(v) if type(v) is str and k != "id" else v for k, v in d.items()}


def network(T, a, b, c):
    # Eliminate C first; decide whether B is capped, then whether C is capped.
    c_if_b_full = min(T, c+a*T)
    if b+a*c_if_b_full >= T:
        p, q = T, c_if_b_full
    elif c+a*(b+a*T) >= T:
        p, q = b+a*T, T
    else:
        p = (b+a*c)/(1-a*a)
        q = c+a*p
    return p, q


def snapshot(data, s):
    i, n = numbers(data["institution"]), numbers(data["network"])
    P0 = i["bond_face"]/(1+i["base_yield"])**i["bond_years"]
    Q0 = i["loan_face"]/(1+i["base_yield"])
    N0 = (1-n["interbank_share"])*n["obligation"]
    E0 = i["cash"]+P0+Q0+N0-i["deposits"]-i["secured_old"]
    p, q = network(n["obligation"], n["interbank_share"], s["external_b"], s["external_c"])
    receipt = (1-n["interbank_share"])*p
    bond = i["bond_face"]/(1+s["yield"])**i["bond_years"]
    recovery = i["loan_face"]*(1-s["loan_loss_fraction"])
    loan = recovery/(1+s["yield"])
    losses = dict(bond=P0-bond, loan=Q0-loan, network=N0-receipt, operating=s["operating_cash_loss"])
    equity = E0-sum(losses.values())
    margin = max(F(0), i["secured_old"]-(1-s["haircut"])*i["pledged_fraction"]*bond)
    capacity = min(s["facility_limit"], (1-s["haircut"])*(1-i["pledged_fraction"])*bond)
    cash = i["cash"]-s["operating_cash_loss"]+receipt
    desired = max(F(0), margin+s["withdrawal"]+i["cash_floor"]-cash)
    draw = min(desired, capacity)
    old_paid = min(margin, cash+draw)
    deposit_paid = min(s["withdrawal"], cash+draw-old_paid)
    return locals()


def family(data, x):
    i, n, ref, r = [numbers(data[k]) for k in ("institution", "network", "reference", "reverse")]
    return dict(id="reverse", **{"yield": i["base_yield"]+r["yield_increase"]*x}, loan_loss_fraction=r["loan_loss_increase"]*x, external_b=n["external_b"]-r["b_resource_drop"]*x, external_c=n["external_c"]-r["c_resource_drop"]*x, haircut=ref["haircut"]+r["haircut_increase"]*x, withdrawal=ref["withdrawal"]+r["withdrawal_increase"]*x, operating_cash_loss=r["operating_loss_increase"]*x, facility_limit=i["facility_limit"])


class Markup(HTMLParser):
    def __init__(self):
        super().__init__(); self.worked = self.prompts = self.answers = 0
        self.ex = self.sol = False; self.ids = []; self.links = []; self.sources = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a: self.ids.append(a["id"])
        if "worked" in a.get("class", "").split(): self.worked += 1
        if tag == "ol" and "exercises" in a.get("class", "").split(): self.ex = True
        if tag == "details" and "solutions" in a.get("class", "").split(): self.sol = True
        if tag == "li": self.prompts += self.ex; self.answers += self.sol
        if "href" in a: self.links.append(a["href"])
        if "data-source" in a: self.sources.add(a["data-source"])
    def handle_endtag(self, tag):
        if tag == "ol": self.ex = False
        if tag == "details": self.sol = False


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    project = root / "content/projects"
    counts = dict(comparisons=0, financial_interventions=0, invalid_api_cases=0, invalid_cli_cases=0, protected_alias_attempts=0, portable_model_runs=0, journal_rows=0, reverse_certificates=0, author_files_bound=0)
    def need(ok, label):
        counts["comparisons"] += 1
        if not ok: raise RuntimeError(label)
    def eq(a, b, label): need(wire(a) == wire(b), label + ": " + repr(a) + " != " + repr(wire(b)))
    def qeq(a, b, label): eq(F(a), b, label)
    spec = importlib.util.spec_from_file_location("c07_peer_target", project / "v11-c07-analysis.py")
    module = importlib.util.module_from_spec(spec); log = io.StringIO()
    with redirect_stdout(log), redirect_stderr(log): spec.loader.exec_module(module)
    eq(log.getvalue(), "", "quiet import")
    data = json.loads((project / "v11-c07-inputs.json").read_text())
    def run(d):
        before = deepcopy(d); capture = io.StringIO()
        with redirect_stdout(capture), redirect_stderr(capture): result = module.run(d)
        eq(capture.getvalue(), "", "quiet API"); eq(d, before, "nonmutating API")
        return result
    result = run(data)
    eq(result, json.loads((project / "v11-c07-output.json").read_text()), "complete saved report")

    def audit_scenario(d, raw, row):
        z = snapshot(d, numbers(raw)); i, n, s = z["i"], z["n"], z["s"]
        p, q, a, T = z["p"], z["q"], n["interbank_share"], n["obligation"]
        receipt, bond, loan, equity = [z[k] for k in ("receipt", "bond", "loan", "equity")]
        ret_b, ret_c = s["external_b"]+a*q-p, s["external_c"]+a*p-q
        eq((p, q), (min(T, s["external_b"]+a*q), min(T, s["external_c"]+a*p)), "eliminated solution fixed point")
        need(0 <= p <= T and 0 <= q <= T and ret_b >= 0 and ret_c >= 0, "limited liability and retention")
        standalone = (1-a)*min(T, s["external_b"]+a*T)
        net = dict(payment_b=p, payment_c=q, interbank_b_receipt=a*q, interbank_c_receipt=a*p, institution_receipt=receipt, other_outside_receipt=(1-a)*q, retained_b=ret_b, retained_c=ret_c, unpaid_b=T-p, unpaid_c=T-q, external_resource_residual=F(0), standalone_institution_receipt=standalone, feedback_loss=standalone-receipt)
        eq(row["network"], net, "all network cash distributions")
        eq(s["external_b"]+s["external_c"], (1-a)*(p+q)+ret_b+ret_c, "external resources exclude internal double count")
        eq(row["loss_components"], z["losses"], "one loss per claim")
        qeq(row["total_loss"], sum(z["losses"].values()), "common-scenario total")
        qeq(row["equity"], equity, "mark and cash-incident equity")
        M, cap, cash, draw, mp, wp = [z[k] for k in ("margin", "capacity", "cash", "draw", "old_paid", "deposit_paid")]
        remaining = cash+draw-mp-wp
        maximum = cash+cap-M-s["withdrawal"]
        funding = dict(margin_required=M, margin_paid=mp, margin_unpaid=M-mp, facility_capacity=cap, draw_to_meet_cash_floor=z["desired"], actual_draw=draw, cash_capacity_after_full_payments=maximum, withdrawal_requested=s["withdrawal"], withdrawal_paid=wp, withdrawal_unpaid=s["withdrawal"]-wp, closing_cash=remaining, all_payments_met=mp==M and wp==s["withdrawal"], reserve_trigger=maximum <= i["cash_floor"], capital_trigger=equity <= i["equity_floor"])
        eq(row["funding"], funding, "partial payments and reserve-capacity policy")
        qeq(row["funding_slack"], maximum-i["cash_floor"], "funding slack is capacity")
        qeq(row["capital_slack"], equity-i["equity_floor"], "capital slack")
        new = draw/((1-s["haircut"])*bond)
        eq(row["collateral"], dict(original_fraction_reserved=i["pledged_fraction"], new_fraction_pledged=new, fraction_remaining_free=1-i["pledged_fraction"]-new, original_pool_capacity=(1-s["haircut"])*i["pledged_fraction"]*bond), "disjoint collateral stock")
        need(F(0) <= new <= 1-i["pledged_fraction"], "no rehypothecated old pool")
        # Each event is checked as an independent account delta, not against
        # the model's post() routine or its own residual alone.
        before = dict(cash=i["cash"], bond=z["P0"], loan=z["Q0"], network_claim=z["N0"], deposits=i["deposits"], secured_old=i["secured_old"], secured_new=F(0), equity=z["E0"])
        changes = [("opening", {}), ("joint_asset_marks", dict(bond=bond-z["P0"], loan=loan-z["Q0"], network_claim=receipt-z["N0"], equity=bond-z["P0"]+loan-z["Q0"]+receipt-z["N0"])), ("cash_incident", dict(cash=-s["operating_cash_loss"], equity=-s["operating_cash_loss"])), ("network_batch_settles", dict(cash=receipt, network_claim=-receipt)), ("new_secured_funding", dict(cash=draw, secured_new=draw)), ("old_secured_principal_paydown", dict(cash=-mp, secured_old=-mp)), ("deposit_payment", dict(cash=-wp, deposits=-wp))]
        eq(len(row["ledger"]), len(changes), "complete ordered event trail")
        for actual, (event, delta) in zip(row["ledger"], changes):
            for key, value in delta.items(): before[key] += value
            eq(actual["event"], event, "cutoff event order")
            eq({k: actual[k] for k in before}, before, "all independent journal accounts")
            assets = sum(before[k] for k in ("cash", "bond", "loan", "network_claim"))
            eq(assets, sum(before[k] for k in ("deposits", "secured_old", "secured_new", "equity")), "independent balance identity")
            qeq(actual["assets"], assets, "reported assets")
            qeq(actual["accounting_residual"], F(0), "reported account certificate")
            need(before["cash"] >= 0, "only executed funded payments posted")
            counts["journal_rows"] += 1
        principal = i["secured_old"]-mp+draw
        eq(row["later_cash"], dict(next_day_secured_principal=principal, next_day_secured_interest=principal*i["secured_daily_rate"], next_day_secured_total=principal*(1+i["secured_daily_rate"]), year_one_loan_receipt=z["recovery"], bond_maturity_year=i["bond_years"], bond_maturity_receipt=i["bond_face"]), "future obligations are not present funding")

    def slacks(d, x):
        z = snapshot(d, family(d, x)); i, s = z["i"], z["s"]
        return z["equity"]-i["equity_floor"], z["cash"]+z["capacity"]-z["margin"]-s["withdrawal"]-i["cash_floor"]

    def audit_reverse(d, out, cubic=False):
        for key, bound in out["reverse"].items():
            def value(x):
                k, h = slacks(d, x)
                return min(k, h) if key == "first" else k if key == "capital_slack" else h
            if value(F(0)) <= 0:
                eq(bound["status"], "triggered_at_reference", "closed reference trigger")
                eq((bound["lower"], bound["upper"], bound["width"]), (F(0), F(0), F(0)), "reference endpoints")
            elif value(F(1)) > 0:
                eq(bound["status"], "no_trigger_in_supported_interval", "absence on monotone compact family")
                eq((bound["lower"], bound["upper"], bound["width"]), (None, None, None), "no fictitious root")
                qeq(bound["reference_slack"], value(F(0)), "safe reference")
                qeq(bound["endpoint_slack"], value(F(1)), "safe endpoint")
            else:
                eq(bound["status"], "boundary_bracketed", "bracket status")
                lo, hi = F(bound["lower"]), F(bound["upper"])
                need(0 <= lo < hi <= 1 and value(lo) > 0 >= value(hi), "exact first-boundary signs")
                qeq(bound["lower_slack"], value(lo), "lower independent slack")
                qeq(bound["upper_slack"], value(hi), "upper independent slack")
                eq(hi-lo, F(1, 2**d["reverse"]["bisections"]), "dyadic width")
                qeq(bound["width"], hi-lo, "reported width")
                if cubic:
                    need(lo > F(1, 3), "polynomial is used in its proved regime")
                    # Expanded integer polynomials, independently from the
                    # model's rational marks and four-regime calculation.
                    poly = (lambda x: 16317-20118*x-2084*x*x-40*x**3) if key == "capital_slack" else (lambda x: 19404-32739*x-5024*x*x-240*x**3)
                    need(poly(lo) > 0 >= poly(hi), "expanded integer polynomial certificate")
                    for x in (lo, hi):
                        k, h = slacks(d, x); z = F(21, 20)+x/10
                        eq(poly(x), (400*k if key == "capital_slack" else 800*h)*z*z, "polynomial scaling identity")
            counts["reverse_certificates"] += 1

    for raw, row in zip(data["scenarios"], result["scenarios"]): audit_scenario(data, raw, row)
    audit_reverse(data, result, True)
    components = {k: max(F(r["loss_components"][k]) for r in result["scenarios"]) for k in ("bond", "loan", "network", "operating")}
    total_max = max(sum(F(v) for v in r["loss_components"].values()) for r in result["scenarios"])
    eq(result["aggregation"], dict(component_maxima=components, sum_component_maxima=sum(components.values()), largest_common_scenario_loss=total_max, overstatement=sum(components.values())-total_max, maximizing_scenarios=["joint"]), "state-consistent finite maximum")

    def variant(changes, rows=(3,), reverse=False):
        d = deepcopy(data)
        for path, value in changes:
            target = d
            for key in path[:-1]: target = target[key]
            target[path[-1]] = value
        out = run(d)
        for j in rows: audit_scenario(d, d["scenarios"][j], out["scenarios"][j])
        if reverse: audit_reverse(d, out)
        counts["financial_interventions"] += 1
        return out
    transfer = variant([(("scenarios", 3, "external_b"), "4"), (("scenarios", 3, "external_c"), "6")])
    eq((transfer["scenarios"][3]["network"]["payment_b"], transfer["scenarios"][3]["network"]["payment_c"]), (F(28, 3), F(32, 3)), "exercise clearing transfer")
    large = variant([(("institution", "facility_limit"), "40"), (("scenarios", 3, "facility_limit"), "40")], reverse=True)
    qeq(large["scenarios"][3]["funding"]["withdrawal_unpaid"], F(2284, 529), "larger line remains collateral limited")
    equity_cash = variant([(("institution", "cash"), "17")], reverse=True)
    deposit_cash = variant([(("institution", "cash"), "17"), (("institution", "deposits"), "142")], reverse=True)
    eq(equity_cash["reverse"]["funding_slack"], deposit_cash["reverse"]["funding_slack"], "same received cash with frozen withdrawals")
    eq(deposit_cash["reverse"]["capital_slack"], result["reverse"]["capital_slack"], "deposit funding is not equity")
    zero_floor = variant([(("institution", "cash_floor"), "0")], reverse=True)
    variant([(("institution", "equity_floor"), "45")], reverse=True)
    variant([(("institution", "cash"), "100")], reverse=True)
    variant([(("institution", "cash_floor"), "100")], reverse=True)
    variant([(("network", "interbank_share"), "3/4")], reverse=True)
    variant([(("scenarios", 3, "external_b"), "0"), (("scenarios", 3, "external_c"), "0"), (("scenarios", 3, "operating_cash_loss"), "12"), (("scenarios", 3, "facility_limit"), "0")])
    variant([(("scenarios", 1, "yield"), "-1/2"), (("scenarios", 1, "haircut"), "0")], rows=(1,))
    variant([(("institution", "secured_old"), "0"), (("institution", "pledged_fraction"), "0")], reverse=True)
    for out, capital, funding in ((result, .751688814506, .545784230258), (equity_cash, .861274373503, .673395979956), (deposit_cash, .751688814506, .673395979956), (zero_floor, .751688814506, .596675093210)):
        for key, anchor in (("capital_slack", capital), ("funding_slack", funding)):
            midpoint = (F(out["reverse"][key]["lower"])+F(out["reverse"][key]["upper"]))/2
            need(abs(float(midpoint)-anchor) < 2e-12, "printed reverse approximation")
    first_hi = F(result["reverse"]["first"]["upper"])
    first_equity = slacks(data, first_hi)[0]+10
    need(abs(float(first_equity)-19.650135) < 5e-7, "capital at first reserve intervention")

    # Every nontrivial printed exact fraction is recomputed from the contracts,
    # separate from the saved numerical report and the author checker.
    html = (root / AUTHOR[0]).read_text()
    P = F("110.25")/F("1.15")**2; Q = F(84)/F("1.15"); Qj = F("67.2")/F("1.15")
    M = 20-P/8; paid = 34-M; expanded = F(3, 8)*P; expanded_paid = 14+expanded-M
    net_b, net_c = network(F(20), F(1, 2), F(4), F(6))
    joint = 100-P+80-Qj+6+2
    maxima = 100-P+80-F("50.4")/F("1.02")+6+2
    printed = {"45/101": F(90, 202), "90/202": F(90, 202), "44100/529": P, "8800/529": 100-P, "1680/23": Q, "12480/529": 180-P-Q, "4000/21": F("220.5")/F("1.05")**3, "400/21": F("22.05")/F("1.05")**3, "1344/23": Qj, "496/23": 80-Qj, "160/23": 80-Q, "336/23": Q/5, "528/23": 96-Q, "32/23": 16-Q/5, "28/3": net_b, "32/3": net_c, "14/3": net_b/2, "16/3": 10-net_b/2, "7/3": 7-net_b/2, "10135/1058": M, "25837/1058": paid, "16483/1058": 40-paid, "119109/1058": 137-paid, "11025/1058": 20-M, "75012/529": P+Qj, "635/529": joint-45, "33075/1058": expanded, "18876/529": expanded_paid, "2284/529": 40-expanded_paid, "1058/2205": 40/P, "520/17": 80-F("50.4")/F("1.02"), "496624/8993": maxima, "24440/529": joint, "3528/391": maxima-joint}
    for text, value in printed.items():
        eq(F(text), value, "fresh printed fraction " + text)
        need(text in html, "printed result present " + text)
    # Avoid matching the integer substrings inside a decimal ratio such as84/1.15.
    numerical_fractions = set(re.findall(r"(?<![\d.])\d+/\d+(?!\d|\.\d)", html))
    eq(numerical_fractions-set(printed), {"1/2", "1/3", "1/5", "3/4"}, "complete exact-fraction coverage including regime/share constants")
    for wrong in ("12919/529", "8241/529", "59554/529", "529/1102"):
        need(wrong not in html, "resolved fraction must stay absent")
    eq(network(F(20), F(1, 2), F(10), F(10)), (F(20), F(20)), "clearing equality boundary")
    for x, expected in ((F(1, 5), (F(20), F(20))), (F(1, 3), (F(56, 3), F(20))), (F(1), (F(8), F(12)))):
        eq(network(F(20), F(1, 2), 12-10*x, 12-4*x), expected, "piecewise network joins")

    invalid = [(("schema",), True), (("institution", "cash"), 12), (("institution", "cash"), "NaN"), (("institution", "cash"), "1e2"), (("institution", "cash"), "1/0"), (("institution", "cash"), "1/1000000001"), (("institution", "bond_years"), True), (("institution", "bond_years"), 6), (("institution", "bond_face"), "0"), (("institution", "deposits"), "300"), (("institution", "secured_old"), "21"), (("network", "interbank_share"), "1"), (("network", "external_b"), "9"), (("reference", "withdrawal"), "138"), (("scenarios",), []), (("scenarios", 1, "id"), "reference"), (("scenarios", 0, "yield"), "-1"), (("scenarios", 0, "haircut"), "1"), (("scenarios", 0, "operating_cash_loss"), "13"), (("scenarios", 0, "facility_limit"), "21"), (("reverse", "b_resource_drop"), "13"), (("reverse", "operating_loss_increase"), "13"), (("reverse", "loan_loss_increase"), "2"), (("reverse", "bisections"), True), (("reverse", "bisections"), 49)]
    for path, value in invalid:
        bad = deepcopy(data); target = bad
        for key in path[:-1]: target = target[key]
        target[path[-1]] = value; old = deepcopy(bad); capture = io.StringIO()
        try:
            with redirect_stdout(capture), redirect_stderr(capture): module.run(bad)
        except ValueError: counts["invalid_api_cases"] += 1
        else: raise RuntimeError("invalid accepted: " + repr(path))
        eq(bad, old, "rejection nonmutating"); eq(capture.getvalue(), "", "rejection quiet")

    peer = json.loads((root / "content/reviews/v11-c07-peer.json").read_text())
    eq([r["path"] for r in peer["reviewed_hashes"]], AUTHOR, "nine exact author bindings")
    for r in peer["reviewed_hashes"]+[peer["peer_checker"]]:
        b = (root / r["path"]).read_bytes()
        eq((len(b), hashlib.sha256(b).hexdigest()), (r["bytes"], r["sha256"]), "frozen binding " + r["path"])
        if r["path"] in AUTHOR: counts["author_files_bound"] += 1
    author = json.loads((root / "content/reviews/v11-c07-author.json").read_text())
    eq({r["path"] for r in author["reviewed_hashes"]}, set(AUTHOR)-{"content/reviews/v11-c07-author.json"}, "author nonself scope")
    for r in author["reviewed_hashes"]:
        b = (root / r["path"]).read_bytes()
        eq((len(b), hashlib.sha256(b).hexdigest()), (r["bytes"], r["sha256"]), "author payload integrity")
    manifest = json.loads((project / "v11-c07-manifest.json").read_text())
    eq([r["file"] for r in manifest["files"]], ["v11-c07-"+s for s in ("inputs.json", "analysis.py", "output.json", "README.txt")], "four portable payloads")
    for r in manifest["files"]:
        b = (project / r["file"]).read_bytes()
        eq((len(b), hashlib.sha256(b).hexdigest()), (r["bytes"], r["sha256"]), "manifest payload integrity")
    parsed = Markup(); parsed.feed(html)
    eq((parsed.worked, parsed.prompts, parsed.answers), (4, 8, 8), "reader worked/prompt/solution structure")
    eq(len(parsed.ids), len(set(parsed.ids)), "unique anchors")
    need(not any(h.startswith("projects/") for h in parsed.links), "flat offline asset links")
    sources = json.loads((root / "content/reviews/v11-c07-sources.json").read_text())
    eq(parsed.sources, {s["id"] for s in sources["proposals"]}, "scoped primary source route")

    with tempfile.TemporaryDirectory(prefix="v11-c07-peer-") as td:
        temp = Path(td); model = temp / "v11-c07-analysis.py"; inp = temp / "v11-c07-inputs.json"
        shutil.copy2(project / model.name, model); shutil.copy2(project / inp.name, inp)
        for opt in (False, True):
            cmd = [sys.executable]+(["-O"] if opt else [])+[str(model)]
            for default in (False, True):
                dest = temp / ("v11-c07-output.json" if default else "explicit.json")
                args = [] if default else ["--input", str(inp), "--output", str(dest)]
                p = subprocess.run(cmd+args, cwd=temp.parent, text=True, capture_output=True, timeout=30)
                eq((p.returncode, p.stdout, p.stderr), (0, "", ""), "quiet portable CLI")
                eq(dest.read_bytes(), (project / "v11-c07-output.json").read_bytes(), "portable exact bytes")
                counts["portable_model_runs"] += 1
            for protected in (inp, model):
                for kind in ("direct", "resolved", "symlink", "hardlink"):
                    target = protected
                    if kind == "resolved":
                        (temp / "nested").mkdir(exist_ok=True); target = temp / "nested" / ".." / protected.name
                    elif kind in ("symlink", "hardlink"):
                        target = temp / (protected.name+"."+kind)
                        if target.exists() or target.is_symlink(): target.unlink()
                        if kind == "symlink": target.symlink_to(protected)
                        else: os.link(protected, target)
                    old = {p: p.read_bytes() for p in (inp, model)}
                    p = subprocess.run(cmd+["--output", str(target)], cwd=temp.parent, text=True, capture_output=True, timeout=30)
                    eq((p.returncode, p.stdout), (2, ""), "output alias rejected"); need(bool(p.stderr), "alias diagnostic")
                    for f, b in old.items(): eq(f.read_bytes(), b, "protected bytes intact")
                    counts["protected_alias_attempts"] += 1
            for content in ('{"schema":1,"schema":1}', '{"schema":NaN}', '[]', ' '*65537):
                bad = temp / "bad.json"; bad.write_text(content); dest = temp / "preserve.json"; dest.write_text("unchanged")
                p = subprocess.run(cmd+["--input", str(bad), "--output", str(dest)], cwd=temp.parent, text=True, capture_output=True, timeout=30)
                eq((p.returncode, p.stdout), (2, ""), "strict invalid CLI rejection")
                eq(dest.read_text(), "unchanged", "invalid output not opened")
                counts["invalid_cli_cases"] += 1
    return {"chapter": "v11-c07", "status": "passed", **counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--root", type=Path)
    args = parser.parse_args(); print(json.dumps(check(args.root), sort_keys=True))


if __name__ == "__main__": main()
