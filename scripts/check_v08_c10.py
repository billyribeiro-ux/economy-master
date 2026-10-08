"""Focused independent cash/claim checks for v08-c10. check() is quiet strict JSON."""
from copy import deepcopy
from fractions import Fraction as F
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content" / "projects"


def equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: {actual!r} != {expected!r}")


def near(actual, expected, label, tolerance=1e-9):
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{label}: {actual!r} != {expected!r}")


def root_check(flows, rate, label):
    if rate <= -1:
        raise AssertionError(f"{label}: rate outside domain")
    residual = sum(float(cash) / (1 + rate) ** t for t, cash in enumerate(flows))
    near(residual, 0, label)


def rejection(action, label):
    try:
        action()
    except ValueError:
        return label
    raise AssertionError(f"{label}: invalid input was not rejected")


def check():
    spec = importlib.util.spec_from_file_location("v08_c10_benchmark", PROJECT / "v08-c10-analysis.py")
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    data = json.loads((PROJECT / "v08-c10-inputs.json").read_text())
    got = model.run(data)
    groups = []

    # Direct EBITDA-cash bridge, not the model's FCFF-minus-after-tax-interest route.
    b = got["lbo"]
    equal((b["seller_equity"], b["entry_uses"], b["entry_sources"], b["sponsor_initial"]),
          (F(300), F(394), F(394), F(164)), "entry funds")
    debt = F(210)
    expected_debt = [F("190.6"), F("170.036"), F("148.23816")]
    expected_tax = [F("8.8"), F("10.188"), F("11.59928")]
    for t, (ebitda, capex, nwc) in enumerate([(64, 16, 3), (68, 18, 4), (72, 20, 5)]):
        row = b["annual"][t]
        interest = debt * F(2, 25)
        tax = (ebitda - 12 - interest) / 4
        principal = ebitda - tax - interest - capex - nwc
        equal(row["opening_debt"], debt, "opening debt")
        equal(row["interest"], interest, "opening-balance interest")
        equal(row["cash_tax"], expected_tax[t], "cash tax")
        equal(row["principal"], principal, "direct cash sweep")
        equal(row["fcff"], F(32), "unlevered operating cash")
        debt -= principal
        equal(debt, expected_debt[t], "independent closing debt")
        equal(row["closing_debt"], debt, "reported closing debt")
    equal(b["exit_equity"], F(432) - 8 - debt, "single subtraction of final debt")
    equal(b["sponsor_flows"], [F(-164), F(0), F(0), F("275.76184")], "sponsor dates")
    equal(sum(b["decomposition"].values()), F("111.76184"), "attribution closure")
    equal(sum(c / F(27, 25) ** t for t, c in enumerate(b["lender_flows"])), 0,
          "lender path contractual present value")
    near(b["sponsor_irr"], (275.76184 / 164) ** (1 / 3) - 1, "one-receipt IRR")
    groups.append({"group": "buyout_cash_debt_and_claims", "passed": True,
                   "closing_debt": "148.23816", "sponsor_exit": "275.76184"})

    # Exercises 1–2: same output price, changed purchase price; explicit timed repair.
    expensive = deepcopy(data["lbo"])
    expensive["entry_ev"] = "390"
    e = model.buyout(expensive)
    equal((e["seller_equity"], e["entry_uses"], e["sponsor_initial"]),
          (F(330), F(424), F(194)), "exercise 1 closing")
    equal(e["exit_equity"], b["exit_equity"], "unchanged exit path")
    equal(e["decomposition"], {"operating_change": F(78), "multiple_change": F(-36),
          "debt_reduction": F("61.76184"), "entry_and_exit_fees": F(-22),
          "later_sponsor_contributions": F(0)}, "exercise 1 attribution")
    equal(e["sponsor_moic"], F("275.76184") / 194, "exercise 1 multiple")
    root_check(e["sponsor_flows"], e["sponsor_irr"], "exercise 1 IRR")
    downside = deepcopy(data["lbo"])
    downside["ebitda"][0] = "50"
    failed = model.buyout(downside)
    equal(failed["feasible"], False, "unfunded scenario not successful")
    equal(failed["annual"][0]["cash_tax"], F("5.3"), "downside tax")
    equal(failed["annual"][0]["cash_before_principal"], F("8.9"), "downside cash")
    equal(failed["annual"][0]["funding_gap"], F("6.1"), "explicit funding gap")
    equal("exit_equity" in failed, False, "no unfunded successful-exit claim")
    downside["sponsor_topups"][0] = "6.1"
    repaired = model.buyout(downside)
    equal([row["closing_debt"] for row in repaired["annual"]],
          [F(195), F("174.7"), F("153.182")], "repaired debt")
    equal([row["cash_tax"] for row in repaired["annual"]],
          [F("5.3"), F("10.1"), F("11.506")], "repaired tax")
    equal(repaired["sponsor_flows"], [F(-164), F("-6.1"), F(0), F("270.818")], "repair dates")
    equal(repaired["sponsor_moic"], F("270.818") / F("170.1"), "repaired multiple")
    equal(sum(repaired["decomposition"].values()), sum(repaired["sponsor_flows"]), "repair attribution")
    near(repaired["sponsor_irr"], 0.16971375771066288, "repaired IRR anchor")
    root_check(repaired["sponsor_flows"], repaired["sponsor_irr"], "repaired IRR residual")
    groups.append({"group": "entry_price_and_funding_repair", "passed": True, "exercises": [1, 2]})

    # Round fractions independently imply share denominators and investment cash.
    a, c = got["round_a"], got["round_b"]
    equal(a["fractions"], {"founders": F(21, 40), "team": F(7, 40), "pool": F(1, 10), "A": F(1, 5)},
          "post-A fractions")
    equal(c["fractions"], {"founders": F(21, 50), "team": F(7, 50), "pool": F(2, 25),
                          "A": F(4, 25), "B": F(1, 5)}, "post-B fractions")
    for round_, capital, label in [(a, F(4000), "A"), (c, F(6000), "B")]:
        equal(sum(round_["shares"].values()), round_["total"], "share sum")
        equal(sum(round_["fractions"].values()), 1, "ownership sum")
        equal(round_["price"] * round_["shares"][label], capital, "primary cash")
    equal(a["pool_added"], F(8000, 7), "new pool shares")
    equal((a["price"], c["price"]), (F(7, 4), F(21, 10)), "round prices")
    alt = model.first_round(4000, 1000, 12000, 3000, F(3, 20))
    equal((alt["pool_added"], alt["price"], alt["shares"]["A"], alt["total"]),
          (F(15000, 13), F(39, 20), F(20000, 13), F(100000, 13)), "exercise 3 counts")
    equal(alt["fractions"], {"founders": F(13, 25), "team": F(13, 100),
                            "pool": F(3, 20), "A": F(1, 5)}, "exercise 3 fractions")
    down = model.next_round(a, 12000, 6000)
    equal((down["price"], down["shares"]["B"], down["total"]),
          (F(21, 20), F(40000, 7), F(120000, 7)), "exercise 4 counts")
    equal(down["fractions"], {"founders": F(7, 20), "team": F(7, 60), "pool": F(1, 15),
                             "A": F(2, 15), "B": F(1, 3)}, "exercise 4 fractions")
    groups.append({"group": "venture_round_denominators", "passed": True, "exercises": [3, 4]})

    # Analytical piecewise schedule independently checks model conversion enumeration.
    def analytical(x):
        x = F(x)
        if x <= 6000:
            return {"B": x, "A": F(0), "common": F(0)}
        if x <= 10000:
            return {"B": F(6000), "A": x - 6000, "common": F(0)}
        if x <= 26000:
            return {"B": F(6000), "A": F(4000), "common": x - 10000}
        if x <= 30000:
            return {"B": F(6000), "A": (x - 6000) / 5, "common": 4 * (x - 6000) / 5}
        return {"B": x / 5, "A": x * F(4, 25), "common": x * F(16, 25)}

    exits = [0, 4000, 6000, 8000, 9000, 10000, 18000, 25999, 26000,
             26001, 27000, 28000, 29200, 29999, 30000, 30001, 40000, 45000]
    for x in exits:
        w = model.joint_waterfall(x)
        equal(w["payoffs"], analytical(x), f"joint payoff at {x}")
        equal(sum(w["payoffs"].values()), F(x), "equity cash conservation")
        equal(sum(w["common_split"].values()), w["payoffs"]["common"], "common cash conservation")
    equal(model.joint_waterfall(27000)["common_split"]["founders"], F(11025), "exercise 5 founder")
    equal(model.joint_waterfall(28000)["common_split"],
          {"founders": F(11550), "team": F(3850), "pool": F(2200)}, "all common holders")
    equal((F(4000) / F(1, 5) + 6000, F(6000) / F(1, 5)),
          (F(26000), F(30000)), "conversion thresholds")
    equal((F(6000) / F(5, 21) + 4000, F(4000) / F(4, 25)),
          (F(29200), F(25000)), "B-only incompatible thresholds")
    equal(max(F(4000), F(4, 25) * 28000) - model.joint_waterfall(28000)["payoffs"]["A"],
          F(80), "detect independent-max error")
    groups.append({"group": "joint_preferred_and_low_exits", "passed": True,
                   "analytical_cash_points": len(exits), "exercise": 5})

    expected_pref = {2000: (2000, 2000, 2000), 12000: (4000, 6000, 6000),
                     24000: (6000, 9000, 8000), 40000: (10000, 13000, 10000)}
    for x, expected in expected_pref.items():
        p = model.single_preferred(x, 4000, F(1, 4), 2)
        equal(tuple(p.values()), tuple(F(v) for v in expected), "exercise 6 preferred")
        for payment in p.values():
            if not 0 <= payment <= x:
                raise AssertionError("Single-class payment does not conserve nonnegative common cash")
    equal(F(4000) / F(1, 4), 16000, "nonparticipating conversion")
    equal(4000 + (8000 - 4000) / F(1, 4), 20000, "participation reaches cap")
    equal(F(8000) / F(1, 4), 32000, "conversion beats cap")
    for x in (20000, 32000):
        equal(model.single_preferred(x, 4000, F(1, 4), 2)["capped_with_conversion"],
              F(8000), "cap boundaries")
    groups.append({"group": "single_preferred_contracts", "passed": True, "exercise": 6})

    f = got["fund"]
    equal(f["gross_flows"], list(map(F, [-90, -45, 60, 135])), "gross portfolio dates")
    equal(f["lp_flows"], list(map(F, [-100, -50, 60, 126])), "net LP dates")
    equal((f["fees_paid"], f["carry_paid"], f["unused_commitment_released"]), (F(15), F(9), F(50)),
          "fund claims and unused commitment")
    for row in f["annual"]:
        equal(row["lp_call"], row["investment"] + row["fee"], "called capital uses")
        equal(row["gross_receipt"], row["lp_distribution"] + row["carry_paid"], "receipt allocation")
    equal((f["gross_moic"], f["net_moic"]), (F(13, 9), F(31, 25)), "gross/net multiples")
    for name in ("gross", "net"):
        flows = f["gross_flows"] if name == "gross" else f["lp_flows"]
        root_check(flows, f[f"{name}_irr"], f"base fund {name} IRR")
    equal(f["interim"], {"date": 2, "gross_mark": F(100), "carry_accrual": F(2),
                        "lp_nav": F(98), "net_dpi": F(2, 5), "net_rvpi": F(49, 75),
                        "net_tvpi": F(79, 75)}, "interim net mark and ratios")
    weak = deepcopy(data["fund"])
    weak["gross_distributions"][-1] = "105"
    w = model.fund(weak)
    equal((w["carry_paid"], w["lp_flows"][-1], w["gross_moic"], w["net_moic"]),
          (F(3), F(102), F(11, 9), F(27, 25)), "exercise 7 final allocation")
    equal((w["final_net_dpi"], w["final_net_rvpi"], w["final_net_tvpi"]),
          (F(27, 25), F(0), F(27, 25)), "exercise 7 final ratios")
    near(w["gross_irr"], 0.09106580752345117, "weak gross IRR")
    near(w["net_irr"], 0.03408641270571655, "weak net IRR")
    root_check(w["gross_flows"], w["gross_irr"], "weak gross root")
    root_check(w["lp_flows"], w["net_irr"], "weak net root")
    equal(F(165) - 135, F(162) - 150 + 15 + 3, "weak fund cash-gain closure")
    equal(F(195 - 135) / 5 - f["carry_paid"], F(3), "detect fee-excluding carry error")
    groups.append({"group": "fund_capital_fees_carry_and_nav", "passed": True, "exercise": 7})

    direct = list(map(F, [-100, 0, 144]))
    delayed = list(map(F, [0, -108, 144]))
    equal(F(100) * F(27, 25), F(108), "line debt service")
    equal(F(144) / F(100), F(36, 25), "underlying multiple")
    equal(F(144) / F(108), F(4, 3), "LP line multiple")
    near(model.block_irr(direct), 0.2, "direct investment return")
    near(model.block_irr(delayed), 1 / 3, "shifted LP return")
    root_check(delayed, 1 / 3, "line LP root")
    equal(F(250) + 20 - 40 - 180, F(50), "founder opportunity-cost example")
    groups.append({"group": "funding_timing_and_personal_opportunity_cost", "passed": True, "exercise": 8})

    # Small targeted domain set; no broad scenario matrix.
    bad_tax = deepcopy(data["lbo"])
    bad_tax["ebitda"][0] = "20"
    bad_sweep = deepcopy(data["lbo"])
    bad_sweep["ebitda"][0] = "1000"
    late_topup = deepcopy(data["lbo"])
    late_topup["sponsor_topups"][-1] = "1"
    bad_fees = deepcopy(data["fund"])
    bad_fees["fees"][0] = "101"
    bad_commitment = deepcopy(data["fund"])
    bad_commitment["commitment"] = "149"
    mismatched = deepcopy(data)
    mismatched["venture"]["b_pre_money"] = "12000"
    changed_common = deepcopy(data)
    changed_common["venture"]["founder_shares"] = "5000"
    changed_common["venture"]["team_shares"] = "3000"
    rejected = [
        rejection(lambda: model.buyout(bad_tax), "unsupported tax loss"),
        rejection(lambda: model.buyout(bad_sweep), "unsupported early full debt repayment"),
        rejection(lambda: model.buyout(late_topup), "final-date netted contribution"),
        rejection(lambda: model.first_round(4000, 1000, 12000, 3000, F(4, 5)), "infeasible pool denominator"),
        rejection(lambda: model.joint_waterfall(-1), "negative equity cash"),
        rejection(lambda: model.single_preferred(100, 50, F(1, 4), F(1, 2)), "cap below preference"),
        rejection(lambda: model.fund(bad_fees), "fee exceeds call"),
        rejection(lambda: model.fund(bad_commitment), "call exceeds commitment"),
        rejection(lambda: model.run(mismatched), "waterfall contract/cap-table mismatch"),
        rejection(lambda: model.run(changed_common), "changed founder/team split with unchanged preferred fractions"),
        rejection(lambda: model.block_irr([-100, 230, -132]), "interleaved IRR signs")
    ]
    expected = json.loads((PROJECT / "v08-c10-output.json").read_text())
    equal(model.wire(got), expected, "reference output reproducibility")
    with tempfile.TemporaryDirectory(prefix="v08-c10-") as folder:
        task_dir = Path(folder)
        for name in ("v08-c10-analysis.py", "v08-c10-inputs.json"):
            shutil.copyfile(PROJECT / name, task_dir / name)
        completed = subprocess.run([sys.executable, "v08-c10-analysis.py"], cwd=task_dir,
                                   capture_output=True, text=True, check=True)
        equal(completed.stderr, "", "offline command stderr")
        equal(json.loads(completed.stdout), expected, "copied offline command")
    groups.append({"group": "domain_and_offline_reproducibility", "passed": True,
                   "domain_rejections": rejected, "copied_cli": "passed"})
    result = {"chapter": "v08-c10", "passed": True, "groups": groups,
              "limits": "Original bounded cases; mathematical cash/claim checks do not certify empirical performance or actual contracts."}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
