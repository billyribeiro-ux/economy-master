"""Separate C08 peer: probabilities, dated resources and strict portable API."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
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

sys.dont_write_bytecode = True
AUTHOR_PATHS = ["content/chapters/v11-c08.html", "content/projects/v11-c08-inputs.json", "content/projects/v11-c08-analysis.py", "content/projects/v11-c08-output.json", "content/projects/v11-c08-manifest.json", "content/projects/v11-c08-README.txt", "scripts/check_v11_c08.py", "content/reviews/v11-c08-author.json", "content/reviews/v11-c08-sources.json"]


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.pairs, self.links, self.sources = [], [], [], set()
        self.worked = 0
        self.exercises = 0
        self.in_exercises = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a: self.ids.append(a["id"])
        if "worked" in a.get("class", "").split(): self.worked += 1
        if tag == "ol" and "exercises" in a.get("class", "").split(): self.in_exercises = True
        if tag == "li" and self.in_exercises: self.exercises += 1
        if tag == "details" and a.get("data-solution-for"): self.pairs.append(a["data-solution-for"])
        if "href" in a: self.links.append(a["href"])
        if "data-source" in a: self.sources.add(a["data-source"])

    def handle_endtag(self, tag):
        if tag == "ol": self.in_exercises = False


def check(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    project = root / "content/projects"
    counts = dict(comparisons=0, financial_interventions=0, invalid_api_cases=0, invalid_cli_cases=0, protected_alias_attempts=0, portable_model_runs=0, pension_rows=0, author_files_bound=0)

    def need(condition, label):
        counts["comparisons"] += 1
        if not condition: raise RuntimeError(label)

    def eq(a, b, label): need(a == b, label + ": " + repr(a) + " != " + repr(b))
    def qeq(a, b, label): eq(F(a), b, label)
    def near(a, b, label): need(math.isclose(float(a), float(b), rel_tol=2e-12, abs_tol=2e-12), label)

    spec = importlib.util.spec_from_file_location("c08_peer_target", project / "v11-c08-analysis.py")
    model = importlib.util.module_from_spec(spec)
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture): spec.loader.exec_module(model)
    eq(capture.getvalue(), "", "quiet import")
    data = json.loads((project / "v11-c08-inputs.json").read_text())

    def run(d):
        saved = deepcopy(d)
        quiet = io.StringIO()
        with redirect_stdout(quiet), redirect_stderr(quiet): result = model.run(d)
        eq(quiet.getvalue(), "", "quiet run")
        eq(d, saved, "nonmutating run")
        return result

    result = run(data)
    eq(result, json.loads((project / "v11-c08-output.json").read_text()), "saved output exact")

    def insurance(d, out):
        ins = d["insurance"]; w, loss = F(ins["wealth"]), F(ins["loss"])
        contracts = [{"id": "uninsured", "premium": "0", "indemnity": "0"}] + ins["contracts"]
        pooled = sum(F(t["probability"]) * F(t["share"]) for t in ins["types"])
        buyers = []
        for t, row in zip(ins["types"], out["insurance"]["types"]):
            p = F(t["probability"])
            base = (1-float(p))*math.sqrt(w) + float(p)*math.sqrt(w-loss)
            near(row["no_insurance_utility_approx"], base, "outside utility")
            near(row["full_insurance_max_premium_approx"], p*loss + float(p*(1-p))*(math.sqrt(w)-math.sqrt(w-loss))**2, "expanded risk premium")
            utilities = []
            for contract, offer in zip(contracts, row["offers"]):
                premium, indemnity = F(contract["premium"]), F(contract["indemnity"])
                eu = (1-float(p))*math.sqrt(w-premium) + float(p)*math.sqrt(w-premium-loss+indemnity)
                utilities.append(eu)
                eq(offer["id"], contract["id"], "menu identity")
                near(offer["expected_utility_approx"], eu, "menu state utilities")
                qeq(offer["premium_minus_expected_claim"], premium-p*indemnity, "menu margin conditional on buyer")
            # All tested menu choices are strict or exact zero-loss ties.
            chosen = [c["id"] for c, u in zip(contracts, utilities) if abs(u-max(utilities)) < 1e-12]
            eq(row["maximizing_contracts_approx"], chosen, "actual menu incentives")
            accepts = math.sqrt(w-pooled*loss) >= base-1e-12
            eq(row["accepts_pooled_full_insurance"], accepts, "pooled participation")
            if accepts: buyers.append(t)
        share = sum(F(t["share"]) for t in buyers)
        qeq(out["insurance"]["buyer_share"], share, "selected population mass")
        if share:
            selected = sum(F(t["share"])*F(t["probability"]) for t in buyers)/share
            qeq(out["insurance"]["selected_claim_probability"], selected, "posterior selected risk")
            qeq(out["insurance"]["margin_per_selected_policy"], loss*(pooled-selected), "selected margin")

    def count_law(n, probability):
        # Coefficients of repeated ((1-p)+p z), independent of the author's
        # combinatorial checker and the model's ratio recurrence.
        coefficients = [F(1)]
        for _ in range(n):
            nxt = [F(0)] * (len(coefficients)+1)
            for k, mass in enumerate(coefficients):
                nxt[k] += mass*(1-probability)
                nxt[k+1] += mass*probability
            coefficients = nxt
        return coefficients

    def pool(d, out):
        x = d["pool"]; n = x["members"]; benefit = F(x["benefit"])
        regimes = [(F(r["weight"]), F(r["claim_probability"])) for r in x["regimes"]]
        p = sum(w*q for w, q in regimes)
        cash = n*F(x["premium"])+F(x["capital"])
        independent = count_law(n, p)
        mixed = [F(0)]*(n+1)
        for weight, probability in regimes:
            for k, mass in enumerate(count_law(n, probability)): mixed[k] += weight*mass
        for name, law in (("independent", independent), ("common_regime", mixed)):
            eq(sum(law), F(1), "probability mass")
            eq(sum(k*q for k, q in enumerate(law)), n*p, "same expected claim count")
            tail = sum(q for k, q in enumerate(law) if k*benefit > cash)
            unpaid = sum(q*max(F(0), k*benefit-cash) for k, q in enumerate(law))
            variance = sum(q*(k*benefit/n)**2 for k, q in enumerate(law))-(p*benefit)**2
            row = out["pool"]["laws"][name]
            qeq(row["shortfall_probability"], tail, "strict shortfall probability")
            qeq(row["expected_unpaid_claims"], unpaid, "expected unpaid positive part")
            qeq(row["variance_average_claim"], variance, "variance from convolution law")
            surplus = sum(q*max(F(0), cash-k*benefit) for k, q in enumerate(law))
            eq(surplus-unpaid, cash-n*p*benefit, "signed surplus resource identity")
        qeq(out["pool"]["limiting_variance_average_claim"], benefit**2*(sum(w*q*q for w, q in regimes)-p*p), "persistent common component")

    def life_law(survival, discounts, benefit):
        # Sequential conditional survival hazards generate disjoint paths.
        alive, payout = F(1), F(0)
        states = []
        for target, discount in zip(survival, discounts):
            conditional = target/alive if alive else F(0)
            states.append((alive*(1-conditional), payout))
            alive *= conditional
            payout += benefit*discount
        states.append((alive, payout))
        return states

    def annuity(d, out):
        a = d["annuity"]; n = a["members"]; b = F(a["benefit"]); discounts = list(map(F, a["discounts"]))
        states = life_law(list(map(F, a["survival"])), discounts, b)
        mean = sum(p*x for p, x in states); second = sum(p*x*x for p, x in states)
        variance = second-mean*mean
        r = out["annuity"]
        qeq(r["mean_per_life"], mean, "life hazard mean")
        qeq(r["variance_per_life"], variance, "life hazard variance")
        qeq(r["iid_variance_average"], variance/n, "iid average units")
        qeq(r["iid_variance_total"], variance*n, "iid total units")
        pair_second = F(0)
        for reg, row in zip(a["regimes"], r["regimes"]):
            law = life_law(list(map(F, reg["survival"])), discounts, b)
            mu = sum(p*x for p, x in law)
            var = sum(p*x*x for p, x in law)-mu*mu
            qeq(row["mean"], mu, "regime mean")
            qeq(row["variance"], var, "regime variance")
            # Enumerate two distinct lives sharing the same regime.
            pair_second += F(reg["weight"])*sum(p*q*x*y for p, x in law for q, y in law)
        covariance = pair_second-mean*mean
        total_variance = n*second+n*(n-1)*pair_second-(n*mean)**2
        qeq(r["common_regime_variance_total"], total_variance, "two-life joint moment total variance")
        qeq(r["common_regime_variance_average"], total_variance/(n*n), "two-life joint moment average variance")
        qeq(r["between_regime_mean_variance"], covariance, "between-person common covariance")
        eq([(F(s["probability"]), F(s["present_value"])) for s in r["single_life_states"]], states, "all life-state atoms")
        death = sum(discount*p*F(a["death_benefit"]) for discount, (p, _) in zip(discounts, states[:-1]))
        qeq(r["temporary_death_benefit_pv"], death, "end-year death cash")
        qeq(r["stress_expected_cohort_liability"], n*b*sum(z*F(s) for z, s in zip(discounts, a["stress_survival"])), "planning-law revision")

    def pension(d, out):
        a, p = d["annuity"], d["pension"]
        discounts = list(map(F, a["discounts"])); faces = list(map(F, p["zero_faces"]))
        initial = F(p["money_account"])+sum(df*x for df, x in zip(discounts, faces))
        r = out["pension"]
        qeq(r["initial_asset_pv"], initial, "opening fund value")
        expected = [a["members"]*F(a["benefit"])*F(s) for s in a["survival"]]
        qeq(r["expected_liability_pv"], sum(df*x for df, x in zip(discounts, expected)), "physical expected pension liability")
        for path, answer in zip(p["paths"], r["paths"]):
            benefits = [F(a["benefit"])*k for k in path["survivors"]]
            cost = sum(df*x for df, x in zip(discounts, benefits)); minimum = max(F(0), cost-initial)
            qeq(answer["minimum_extra_initial_cash_with_stated_markets"], minimum, "funding necessity")
            for key, extra in (("without_support", F(0)), ("with_minimum_extra_cash", minimum)):
                report = answer[key]; inventory = faces[:]; prior_df = F(1); prior_cash = F(p["money_account"])+extra; paid_pv = F(0)
                for t, row in enumerate(report["rows"]):
                    df = discounts[t]
                    cash_before_pv = prior_cash*prior_df+inventory[t]*df
                    gap_pv = max(F(0), benefits[t]*df-cash_before_pv)
                    sold = {sale["maturity"]-1: F(sale["face_sold"]) for sale in row["sales"]}
                    eq(len(sold), len(row["sales"]), "no duplicate inventory sale")
                    expected_sales = {}
                    for j in range(len(inventory)-1, t, -1):
                        take = min(inventory[j], gap_pv/discounts[j])
                        if take: expected_sales[j] = take
                        gap_pv -= take*discounts[j]
                    eq(sold, expected_sales, "latest-maturity discounted allocation")
                    qeq(row["matured_face"], inventory[t], "only retained face matures")
                    qeq(row["accrued_cash"], prior_cash*prior_df/df, "dated money growth")
                    receipts_pv = sum(discounts[j]*q for j, q in sold.items())
                    available = (cash_before_pv+receipts_pv)/df
                    qeq(row["paid"], min(benefits[t], available), "maximum executable payment")
                    qeq(row["unpaid"], max(F(0), benefits[t]-available), "actual unpaid amount")
                    for sale in row["sales"]:
                        j = sale["maturity"]-1
                        qeq(sale["price_per_face"], discounts[j]/df, "sale quote")
                        qeq(sale["receipt"], discounts[j]*sold[j]/df, "sale cash")
                    inventory[t] = F(0)
                    for j, q in sold.items(): inventory[j] -= q
                    eq(list(map(F, row["remaining_faces"])), inventory, "one-use inventory")
                    closing = available-F(row["paid"])
                    qeq(row["closing_cash"], closing, "cash after payment")
                    paid_pv += df*F(row["paid"])
                    eq(paid_pv+df*closing+sum(z*q for z, q in zip(discounts, inventory)), initial+extra, "discounted resource conservation")
                    prior_cash, prior_df = closing, df
                    counts["pension_rows"] += 1
                if report["all_payments_met"]:
                    eq(len(report["rows"]), len(discounts), "whole paid path")
                    qeq(report["terminal_cash"], (initial+extra-cost)/discounts[-1], "terminal residual")
                else:
                    eq(report["first_unpaid_date"], len(report["rows"]), "stop on first failure")
                    need(F(report["rows"][-1]["unpaid"]) > 0, "unpaid failure witness")
                    eq(report["terminal_cash"], None, "no fabricated postdefault result")
                if key == "with_minimum_extra_cash": need(report["all_payments_met"], "explicit support sufficiency")
        shift = float(F(p["parallel_continuous_rate_shift"]))
        residual = F(p["money_account"])+sum(float(df)*math.exp(-(t+1)*shift)*float(face-benefit) for t, (df, face, benefit) in enumerate(zip(discounts, faces, expected)))
        near(r["shifted_surplus_approx"], residual, "net cash-vector curve repricing")
        qeq(r["surplus_derivative_per_unit_parallel_continuous_rate"], sum((t+1)*df*(benefit-face) for t, (df, face, benefit) in enumerate(zip(discounts, faces, expected))), "rate derivative")

    def guarantee(d, out):
        g = d["guarantee"]; due = F(g["promised_benefit"])
        totals = {k: F(0) for k in out["guarantee"]["expectations"]}
        for raw, row in zip(g["states"], out["guarantee"]["states"]):
            assets, cap1, cap2 = [F(raw[k]) for k in ("assets", "sponsor_capacity", "guarantor_capacity")]
            required = max(F(0), due-assets); support = min(required, cap1); second = min(required-support, cap2)
            expected = dict(assets=assets, required_sponsor_topup=required, actual_sponsor_payment=support, guarantor_payment=second, participant_payment=min(due, assets+support+second), participant_shortfall=max(F(0), due-assets-cap1-cap2), residual_assets=max(F(0), assets-due))
            for k, value in expected.items():
                qeq(row[k], value, "support waterfall " + k)
                totals[k] += F(raw["probability"])*value
            eq(assets+support+second, expected["participant_payment"]+expected["residual_assets"], "state resource conservation")
        for k, value in totals.items(): qeq(out["guarantee"]["expectations"][k], value, "physical support expectation")

    def household(d, out):
        h = d["household"]; returns = list(map(F, h["pension_gross_returns"])); q = list(map(F, h["contributions"]))
        for loan, answer in zip(h["loans"], out["household"]["loans"]):
            principal = list(map(F, loan["principal_payments"])); interest = [F(loan["rate"])*(F(h["debt"])-sum(principal[:t])) for t in range(len(principal))]
            balances = [F(h["initial_liquid"])]
            for t, row in enumerate(answer["rows"]):
                cash = F(h["initial_liquid"])+sum(F(h["income"][j])-F(h["consumption"][j])-q[j]-principal[j]-interest[j] for j in range(t+1))
                pension_value = F(h["initial_pension"])*math.prod(returns[:t+1])+sum(q[j]*math.prod(returns[j+1:t+1]) for j in range(t+1))
                qeq(row["projected_liquid"], cash, "household cumulative cash")
                qeq(row["pension_account"], pension_value, "contribution-vintage value")
                qeq(row["debt_service"], principal[t]+interest[t], "opening-principal interest")
                qeq(row["remaining_debt"], F(h["debt"])-sum(principal[:t+1]), "principal inventory")
                balances.append(cash)
            qeq(answer["total_interest"], sum(interest), "total funding expense")
            qeq(answer["minimum_extra_initial_cash_for_floor"], max(F(0), F(h["liquid_floor"])-min(balances)), "floor minimum includes date zero")
            eq(answer["first_negative_cash"], next((i for i, cash in enumerate(balances) if cash < 0), None), "cash failure date")
            eq(answer["first_floor_breach"], next((i for i, cash in enumerate(balances) if cash < F(h["liquid_floor"])), None), "reserve versus payment failure")

    for audit in (insurance, pool, annuity, pension, guarantee, household): audit(data, result)

    def tail_table(out, values):
        actual = []
        for field in ("shortfall_probability", "expected_unpaid_claims"):
            for law in ("independent", "common_regime"):
                actual.append(round(float(F(out["pool"]["laws"][law][field])), 6))
        eq(actual, values, "four rounded published tail entries")
    tail_table(result, [0.207539, 0.495784, 39.225150, 380.327304])

    def variant(changes, audit):
        d = deepcopy(data)
        for path, value in changes:
            target = d
            for key in path[:-1]: target = target[key]
            target[path[-1]] = value
        out = run(d); audit(d, out); counts["financial_interventions"] += 1
        return out

    altered = variant([(("insurance", "contracts", 0, "indemnity"), "10"), (("insurance", "contracts", 0, "premium"), "1")], insurance)
    eq([r["maximizing_contracts_approx"] for r in altered["insurance"]["types"]], [["partial"], ["partial"]], "menu transfer")
    variant([(("insurance", "wealth"), "144"), (("insurance", "loss"), "80"), (("insurance", "types"), [{"id": "one", "probability": "0.25", "share": "1"}]), (("insurance", "contracts"), [{"id": "full", "premium": "22", "indemnity": "80"}])], insurance)
    for capital, anchors in (("200", [0.069349, 0.480076, 10.280383, 282.148054]), ("600", [0.002746, 0.346595, 0.258531, 110.450931])):
        altered_pool = variant([(("pool", "capital"), capital)], pool)
        tail_table(altered_pool, anchors)
    small = variant([(("pool",), {"members": 2, "benefit": "10", "premium": "3", "capital": "0", "regimes": [{"id": "zero", "weight": "0.5", "claim_probability": "0"}, {"id": "half", "weight": "0.5", "claim_probability": "0.5"}]})], pool)
    eq([F(small["pool"]["laws"][k]["expected_unpaid_claims"]) for k in ("independent", "common_regime")], [F(19, 8), F(11, 4)], "exact two-member severity")
    eq([F(small["pool"]["laws"][k]["shortfall_probability"]) for k in ("independent", "common_regime")], [F(7, 16), F(3, 8)], "frequency reverses under dependence")
    variant([(("pool", "members"), 1), (("pool", "premium"), "64"), (("pool", "regimes"), [{"id": "sure", "weight": "1", "claim_probability": "1"}])], pool)
    # Exact 408 support versus one cent less; no inferred contribution commitment.
    fixed = variant([(("pension", "money_account"), "608")], pension)
    need(fixed["pension"]["paths"][1]["without_support"]["all_payments_met"], "exact minimum cash works")
    below = variant([(("pension", "money_account"), "607.99")], pension)
    qeq(below["pension"]["paths"][1]["without_support"]["rows"][-1]["unpaid"], F(1, 88), "one cent initial deficit grows to dated unpaid")
    variant([(("pension", "money_account"), "0"), (("pension", "zero_faces"), ["0", "0", "0"])], pension)
    variant([(("annuity", "discounts"), ["1.01", "1.04", "1.08"])], pension)
    for capacity in ("20", "35"):
        variant([(("guarantee", "states", 0, "guarantor_capacity"), capacity)], guarantee)
    variant([(("household", "income", 2), "34")], household)
    variant([(("household", "contributions", 0), "2")], household)
    variant([(("household", "liquid_floor"), "10")], household)
    # Boundary nested laws preserve regime marginals and remain distinct from
    # realized pension counts, which this call does not reinterpret.
    for s in ("0", "1"):
        variant([(("annuity", "survival"), [s]*3), (("annuity", "regimes"), [{"id": "sure", "weight": "1", "survival": [s]*3}])], annuity)

    # Exact exercise-only transfers outside the lab's member bound.
    eq(F(100)-(F(3, 4)*10+F(1, 4)*6)**2, F(19), "worked1 maximum premium")
    eq(F(144)-(F(3, 4)*12+F(1, 4)*8)**2, F(23), "exercise1 maximum premium")
    eq(64**2*F(3, 16)/400, F("1.92"), "exercise3 independent average")
    eq(64**2*(F("0.165")/400+F("0.0225")), F("93.8496"), "exercise3 common average")
    law = life_law([F("0.8"), F("0.5")], [F("0.95"), F("0.9")], F(10))
    mu = sum(p*x for p, x in law)
    eq(mu, F("12.1"), "exercise5 mean")
    eq(sum(p*x*x for p, x in law)-mu*mu, F("51.79"), "exercise5 nested variance")
    eq(2*F("9.5")*9*(F("0.5")-F("0.8")*F("0.5")), F("17.1"), "false-independent omission")
    eq(50*(F("0.95")*F("0.2")+F("0.9")*F("0.3")), F(23), "exercise5 death payout timing")
    eq(F("361.6944")/1000, F("0.3616944"), "exercise6 independent average")
    eq(F("332.1008")/1000+F("29.5936"), F("29.9257008"), "exercise6 common average")
    eq(1000*(F("47.08")-F("41.64")), F(5440), "exercise6 new-law mean")
    eq((1800-1000)*F("0.96")-200, F(568), "sale restriction initial timing minimum")
    high = lambda a: 0.6*math.sqrt(100-0.1*a)+0.4*math.sqrt(36+0.9*a)
    lo, hi = 0.0, 64.0
    for _ in range(50):
        mid = (lo+hi)/2
        if high(mid) < math.sqrt(74.4): lo = mid
        else: hi = mid
    need(abs((lo+hi)/2-8.846193408) < 1e-9, "unique menu boundary numeric anchor")
    eq(20*(F("0.96")*F("0.8")+F("0.92")*F("0.6")+F("0.88")*F("0.4")), F("33.44"), "retention expectation")

    invalid_changes = [(("schema",), True), (("insurance", "wealth"), 100), (("insurance", "loss"), "101"), (("insurance", "contracts", 0, "premium"), "60"), (("insurance", "types", 0, "share"), "0"), (("insurance", "contracts", 0, "id"), "uninsured"), (("pool", "members"), 201), (("pool", "members"), False), (("pool", "capital"), "NaN"), (("pool", "regimes", 0, "weight"), "0.6"), (("annuity", "discounts", 0), "0"), (("annuity", "survival"), ["0.5", "0.9", "0.4"]), (("annuity", "regimes", 0, "survival", 0), "0.8"), (("pension", "paths", 0, "survivors"), [90, 91, 60]), (("pension", "zero_faces", 0), "-1"), (("pension", "parallel_continuous_rate_shift"), "0.21"), (("guarantee", "states", 0, "guarantor_capacity"), "-1"), (("guarantee", "states", 0, "probability"), "0.2"), (("household", "income"), []), (("household", "pension_gross_returns", 0), "0"), (("household", "loans", 0, "principal_payments", 0), "7"), (("household", "initial_liquid"), "1/2"), (("household", "initial_pension"), "1e2"), (("units",), "x"*181)]
    for path, value in invalid_changes:
        bad = deepcopy(data); target = bad
        for key in path[:-1]: target = target[key]
        target[path[-1]] = value; original = deepcopy(bad); quiet = io.StringIO()
        try:
            with redirect_stdout(quiet), redirect_stderr(quiet): model.run(bad)
        except ValueError: counts["invalid_api_cases"] += 1
        else: raise RuntimeError("invalid API input accepted: " + repr(path))
        eq(bad, original, "invalid input unchanged")
        eq(quiet.getvalue(), "", "quiet rejection")

    peer = json.loads((root / "content/reviews/v11-c08-peer.json").read_text())
    eq([x["path"] for x in peer["reviewed_hashes"]], AUTHOR_PATHS, "exact nine author files")
    for record in peer["reviewed_hashes"]+[peer["peer_checker"]]:
        contents = (root / record["path"]).read_bytes()
        eq((len(contents), hashlib.sha256(contents).hexdigest()), (record["bytes"], record["sha256"]), "frozen binding " + record["path"])
        if record["path"] in AUTHOR_PATHS: counts["author_files_bound"] += 1
    author = json.loads((root / "content/reviews/v11-c08-author.json").read_text())
    eq({r["path"] for r in author["reviewed_hashes"]}, set(AUTHOR_PATHS)-{"content/reviews/v11-c08-author.json"}, "author eight nonself payloads")
    for record in author["reviewed_hashes"]:
        contents = (root / record["path"]).read_bytes()
        eq((len(contents), hashlib.sha256(contents).hexdigest()), (record["bytes"], record["sha256"]), "author binding still current")
    manifest = json.loads((project / "v11-c08-manifest.json").read_text())
    eq({r["file"] for r in manifest["files"]}, {"v11-c08-"+s for s in ("inputs.json", "analysis.py", "output.json", "README.txt")}, "four manifest payloads")
    for record in manifest["files"]:
        contents = (project / record["file"]).read_bytes()
        eq((len(contents), hashlib.sha256(contents).hexdigest()), (record["bytes"], record["sha256"]), "manifest binding")
    markup = Markup(); markup.feed((root / AUTHOR_PATHS[0]).read_text())
    eq(markup.worked, 6, "six reader worked cases")
    eq(markup.exercises, 10, "ten reader prompts")
    eq(markup.pairs, ["v11-c08-e"+str(i) for i in range(1, 11)], "ten exact paired solutions")
    eq(len(markup.ids), len(set(markup.ids)), "unique chapter anchors")
    eq(markup.sources, {r["id"] for r in json.loads((root / AUTHOR_PATHS[-1]).read_text())}, "scoped source routes")
    need(not any(h.startswith("projects/") for h in markup.links), "flat reader assets")

    with tempfile.TemporaryDirectory(prefix="v11-c08-peer-") as directory:
        temp = Path(directory); implementation = temp / "v11-c08-analysis.py"; inp = temp / "v11-c08-inputs.json"
        shutil.copy2(project / implementation.name, implementation); shutil.copy2(project / inp.name, inp)
        for optimized in (False, True):
            command = [sys.executable]+(["-O"] if optimized else [])+[str(implementation)]
            output = temp / "written.json"
            process = subprocess.run(command+["--input", str(inp), "--output", str(output)], cwd=temp.parent, capture_output=True, text=True, timeout=30)
            eq((process.returncode, process.stdout, process.stderr), (0, "", ""), "portable output CLI")
            eq(output.read_bytes(), (project / "v11-c08-output.json").read_bytes(), "portable exact output bytes")
            counts["portable_model_runs"] += 1
            process = subprocess.run(command, cwd=temp.parent, capture_output=True, text=True, timeout=30)
            eq((process.returncode, process.stderr), (0, ""), "portable default input")
            eq(json.loads(process.stdout), result, "stdout contains only report")
            counts["portable_model_runs"] += 1
            for protected in (inp, implementation):
                for kind in ("direct", "resolved", "symlink", "hardlink"):
                    alias = protected
                    if kind == "resolved":
                        (temp / "nested").mkdir(exist_ok=True); alias = temp / "nested" / ".." / protected.name
                    elif kind in ("symlink", "hardlink"):
                        alias = temp / (protected.name+"."+kind)
                        if alias.exists() or alias.is_symlink(): alias.unlink()
                        if kind == "symlink": alias.symlink_to(protected)
                        else: os.link(protected, alias)
                    before = {p: p.read_bytes() for p in (inp, implementation)}
                    process = subprocess.run(command+["--output", str(alias)], cwd=temp.parent, capture_output=True, text=True, timeout=30)
                    eq((process.returncode, process.stdout), (2, ""), "protected alias rejects")
                    need(bool(process.stderr), "alias rejection explanation")
                    for p, content in before.items(): eq(p.read_bytes(), content, "protected bytes remain intact")
                    counts["protected_alias_attempts"] += 1
            for payload in ('{"schema":1,"schema":1}', '{"schema":NaN}', '[]', '{'):
                bad = temp / "invalid.json"; bad.write_text(payload); output.write_text("retain this")
                process = subprocess.run(command+["--input", str(bad), "--output", str(output)], cwd=temp.parent, capture_output=True, text=True, timeout=30)
                eq((process.returncode, process.stdout), (2, ""), "strict CLI rejection")
                eq(output.read_text(), "retain this", "invalid CLI preserves destination")
                counts["invalid_cli_cases"] += 1
    return {"chapter": "v11-c08", "status": "passed", **counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.root), sort_keys=True))


if __name__ == "__main__": main()
