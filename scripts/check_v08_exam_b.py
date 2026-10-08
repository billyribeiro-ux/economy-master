"""Independent exact anchors and assessment contract for Volume 8 Form B.

No model under test supplies the answers: reconstruct the actual cash and claims
from the original examination inputs. check() is quiet and returns strict JSON.
"""
from fractions import Fraction as F
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: {actual!r} != {expected!r}")


def near(actual, expected, label, tolerance=1e-10):
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{label}: {actual!r} != {expected!r}")


def pv(cash, gross_rate):
    return sum(F(c) / gross_rate ** t for t, c in enumerate(cash))


def stable_value(nopat, growth, roic, rate):
    if not (nopat > 0 and roic > 0 and 0 <= growth < rate and growth <= roic):
        raise ValueError("Inadmissible positive stable-growth case")
    return nopat * (1 - growth / roic) / (rate - growth)


class Exam(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = {}
        self.answers = []
        self.ids = []
        self.stack = []
        self.in_solutions = False
        self.answer_texts = {}
        self.active_answer = None
        self.words = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if attrs.get("class") == "solutions":
            self.in_solutions = True
        if "data-points" in attrs:
            if self.in_solutions:
                raise AssertionError("Prompt points occur inside solutions")
            key = attrs["id"]
            if key in self.parts:
                raise AssertionError("Duplicate scored part")
            self.parts[key] = int(attrs["data-points"])
        if "data-solution-for" in attrs:
            if not self.in_solutions:
                raise AssertionError("Answer outside solution block")
            self.active_answer = attrs["data-solution-for"]
            self.answers.append(self.active_answer)
            self.answer_texts[self.active_answer] = []
        if tag not in {"br", "hr", "img", "input", "meta", "link"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in {"br", "hr", "img", "input", "meta", "link"}:
            return
        if not self.stack or self.stack[-1] != tag:
            raise AssertionError(f"Malformed exam HTML at {tag}")
        self.stack.pop()
        if tag == "li":
            self.active_answer = None

    def handle_data(self, value):
        self.words.append(value)
        if self.active_answer:
            self.answer_texts[self.active_answer].append(value)


def check():
    groups = []
    tenth = F(11, 10)
    twentieth = F(21, 20)

    # Q1a: construct costs from spending and sacrificed sale, excluding sunk study.
    costs = [F(32) + 8, F(72) + 8]
    receipts = [F(60), F(112)]
    npvs = [receipt / tenth ** 2 - cost for receipt, cost in zip(receipts, costs)]
    equal(npvs, [F(1160, 121), F(1520, 121)], "Q1a NPVs")
    equal(npvs[1] - npvs[0], F(360, 121), "Q1a incremental Large gain")
    irrs = [math.sqrt(float(receipt / cost)) - 1 for receipt, cost in zip(receipts, costs)]
    if not irrs[0] > irrs[1] > 0 or not npvs[1] > npvs[0] > 0:
        raise AssertionError("Q1a ranking conflict missing")
    for receipt, cost, irr in zip(receipts, costs, irrs):
        near(-float(cost) + float(receipt) / (1 + irr) ** 2, 0, "Q1a IRR root")
    # Q1b: tax and claim ledger reconstructed directly.
    ebit = F(220 - 136 - 24)
    tax_u, tax_l = ebit / 4, (ebit - 10) / 4
    ni = ebit - 10 - tax_l
    net_borrowing = F(5 - 18)
    fcff = ebit - tax_u + 24 - 30 - 12
    fcfe = ni + 24 - 30 - 12 + net_borrowing
    equal((ebit, ni, fcff, fcfe), (F(60), F(75, 2), F(27), F(13, 2)), "Q1b cash")
    equal(fcfe, fcff - 10 + tax_u - tax_l + net_borrowing, "Q1b alternate cash bridge")
    equal(fcfe + 10 - net_borrowing, fcff + tax_u - tax_l, "Q1b lender/shareholder closure")
    # Q1c reverse equation uses fixed first continuing NOPAT; Q1d no-solution proof.
    n, quoted, roic, rate = F(60), F(800), F(3, 20), F(1, 10)
    growth = (quoted * rate - n) / (quoted - n / roic)
    reinvestment = n * growth / roic
    equal((growth, reinvestment, n - reinvestment), (F(1, 20), F(20), F(40)), "Q1c reverse growth")
    equal(stable_value(n, growth, roic, rate), quoted, "Q1c continuation")
    for g in (F(0), F(1, 20), F(9, 100)):
        equal(stable_value(n, g, rate, rate), F(600), "Q1d zero excess return")
    # Exactly at g=r is rejected, not a fabricated reverse solution.
    try:
        stable_value(n, rate, rate, rate)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid terminal boundary accepted")
    groups.append({"domain": "D1", "parts": ["q1a", "q1b", "q1c", "q1d"],
                   "passed": True, "large_npv": str(npvs[1]), "fcfe": str(fcfe), "growth": str(growth)})

    # Q2 APV and declining market weights. Each loan is also priced from debt receipts.
    unlevered = pv([0, 60, 60], twentieth)
    debt_service = [F(-40), F(22), F(21)]
    equal(pv(debt_service, twentieth), F(0), "Q2a loan proceeds match claim")
    shield = pv([0, F(1, 2), F(1, 4)], twentieth)
    base_npv = unlevered + shield - 100 - 1
    equal((unlevered, shield, base_npv), (F(16400, 147), F(310, 441), F(4969, 441)), "Q2a APV")
    continuation = F(60) / twentieth + F(1, 4) / twentieth
    debt_weight = 20 / continuation
    last_rate = F(60) / continuation - 1
    equal((continuation, debt_weight, last_rate), (F(1205, 21), F(84, 241), F(11, 241)), "Q2b market rates")
    equal(last_rate, F(1, 20) * (1 - debt_weight / 4), "Q2b compatible WACC")
    if last_rate == F(9, 200) or debt_weight == F(2, 5):
        raise AssertionError("Q2b assumed constant weights accidentally hold")
    high_shield = pv([0, F(3, 4), F(3, 8)], twentieth)
    monitoring_pv = F(21, 25) / twentieth
    high_npv = unlevered + high_shield - monitoring_pv - 100 - 1
    equal((high_shield, monitoring_pv, high_npv), (F(155, 147), F(4, 5), F(1136, 105)), "Q2c alternative")
    equal(high_npv - base_npv, F(-989, 2205), "Q2c net financing difference")
    equal(pv([-60, 33, F(63, 2)], twentieth), F(0), "Q2c larger loan fair claim")
    # Direct equity route verifies APV NPV without separately adding shield benefits again.
    base_equity_cf = [F(-61), F(60) + F(1, 2) - 22, F(60) + F(1, 4) - 21]
    high_equity_cf = [F(-41), F(60) - F(21, 25) + F(3, 4) - 33, F(60) + F(3, 8) - F(63, 2)]
    equal(pv(base_equity_cf, twentieth), base_npv, "Q2a equity funding route")
    equal(pv(high_equity_cf, twentieth), high_npv, "Q2c equity funding route")
    repurchase = F(50 - 25 - 8 - 10)
    equity, shares = F(230), F(20)
    price = equity / shares
    retired = repurchase / price
    equal((repurchase, price, retired, shares - retired),
          (F(7), F(23, 2), F(14, 23), F(446, 23)), "Q2d repurchase")
    equal((equity - repurchase) / (shares - retired), price, "Q2d unchanged fair price")
    equal(F(50) - repurchase - 25 - 8, F(10), "Q2d dated liquidity")
    if F(50) - (repurchase + 1) - 25 - 8 >= 10:
        raise AssertionError("Q2d payout cap not binding")
    groups.append({"domain": "D2", "parts": ["q2a", "q2b", "q2c", "q2d"],
                   "passed": True, "apv_npv": str(base_npv), "alternative_npv": str(high_npv)})

    # Q3 normalize claim perimeter and cycle; independently enumerate dated action menus.
    peer_ev = [F(160 + 60 + 20 - 20), F(240 + 90 - 30)]
    peer_normal = [F(30 + 40 + 50, 3), F(40 + 50 + 60, 3)]
    ratios = [ev / earnings for ev, earnings in zip(peer_ev, peer_normal)]
    equal(ratios, [F(11, 2), F(6)], "Q3a multiples")
    target_normal = F(30 + 50 + 70, 3)
    ev_band = [multiple * target_normal for multiple in ratios]
    common_band = [ev + 15 - 80 - 10 for ev in ev_band]
    equal((ev_band, common_band), ([F(275), F(300)], [F(200), F(225)]), "Q3b claim values")
    equal(sum(ev_band) / 2, F(575, 2), "Q3b median operating")
    equal(sum(common_band) / 2, F(425, 2), "Q3b median equity")
    quoted_ev = F(270 + 80 + 10 - 15)
    equal((quoted_ev / target_normal, quoted_ev / 70), (F(69, 10), F(69, 14)), "Q3b normalization effect")
    q = [F(2, 5), F(3, 5)]
    continuing = [F(110) / tenth, F(22) / tenth]
    abandon = F(40)
    fixed = (50 + sum(weight * value for weight, value in zip(q, continuing))) / tenth
    optimized = [max(value, abandon) for value in continuing]
    flexible = (50 + sum(weight * value for weight, value in zip(q, optimized))) / tenth
    equal((fixed, flexible, flexible - fixed), (F(1020, 11), F(1140, 11), F(120, 11)), "Q3c option values")
    upgrade = [F(55) / tenth - 30, F(22) / tenth - 30]
    equal(upgrade, [F(20), F(-10)], "Q3d upgrade incremental NPV")
    jointly = [max(value, value + extra, abandon) for value, extra in zip(continuing, upgrade)]
    both = (50 + sum(weight * value for weight, value in zip(q, jointly))) / tenth
    equal((jointly, both, both - flexible), ([F(120), F(40)], F(1220, 11), F(80, 11)), "Q3d joint choices")
    # Dated good: cash50-invest30, then110+55. Bad: cash50+salvage40 now.
    from_cash = q[0] * (F(20) / tenth + F(165) / tenth ** 2) + q[1] * F(90) / tenth
    equal(from_cash, both, "Q3d funding and two-date cash")
    physical_shortcut = (50 + F(7, 10) * 100 + F(3, 10) * 40) / tenth
    equal(physical_shortcut - flexible, F(180, 11), "Q3c detect changed pricing law")
    groups.append({"domain": "D3", "parts": ["q3a", "q3b", "q3c", "q3d"],
                   "passed": True, "median_common": "212.5", "joint_flexibility_value": str(both)})

    # Q4 cash acquisition owner-gain identity independent of earnings bridge.
    price_paid, integration, target_value, synergy = F(140), F(8), F(120), F(18)
    spent = price_paid + integration
    seller_gain = price_paid - target_value
    buyer_gain = target_value + synergy - spent
    equal((F(160) - spent, seller_gain, buyer_gain), (F(12), F(20), F(-10)), "Q4a cash and gains")
    equal(seller_gain + buyer_gain, synergy - integration, "Q4a total gain")
    equal((400 + buyer_gain, target_value + synergy - integration), (F(390), F(130)), "Q4a value ceiling")
    earnings_loss = spent / 20
    ni_after = F(20 + 10 + 2) - earnings_loss
    equal((earnings_loss, ni_after, ni_after / 20), (F(37, 5), F(123, 5), F(123, 100)), "Q4b EPS")
    if not buyer_gain < 0 < ni_after / 20 - 1:
        raise AssertionError("Q4b accretion/value counterexample lost")
    seller = F(150 + 10 - 30)
    uses = seller + 30 + 4
    sponsor = uses - 80 - 10
    equal((seller, uses, sponsor), (F(130), F(164), F(74)), "Q4c closing")
    debt = F(80)
    rows = []
    lender = [F(-80)]
    for _ in range(2):
        interest = debt / 10
        principal = 30 - interest
        debt -= principal
        rows.append((interest, principal, debt))
        lender.append(interest + principal)
    equal(rows, [(F(8), F(22), F(58)), (F(29, 5), F(121, 5), F(169, 5))], "Q4c debt")
    lender[-1] += debt
    equal(pv(lender, tenth), F(0), "Q4c lender contractual path")
    sponsor_exit = F(140 - 6) - debt
    equal(sponsor_exit, F(501, 5), "Q4c sponsor exit")
    sponsor_moic = sponsor_exit / sponsor
    equal(sponsor_moic, F(501, 370), "Q4c sponsor multiple")
    sponsor_irr = math.sqrt(float(sponsor_moic)) - 1
    near(sponsor_irr, 0.16363828316794993, "Q4c sponsor IRR")
    lp_paid = sponsor + 6
    carry = (sponsor_exit - lp_paid) / 5
    lp_exit = sponsor_exit - carry
    equal((lp_paid, carry, lp_exit, lp_exit / lp_paid), (F(80), F(101, 25), F(2404, 25), F(601, 500)), "Q4d fund")
    equal(sponsor_exit - sponsor, lp_exit - lp_paid + 6 + carry, "Q4d economic-profit closure")
    lp_irr = math.sqrt(float(lp_exit / lp_paid)) - 1
    near(lp_irr, 0.09635760589325959, "Q4d LP IRR")
    equal((sponsor_exit - sponsor) / 5 - carry, F(6, 5), "Q4d detect fee-excluding carry")
    groups.append({"domain": "D4", "parts": ["q4a", "q4b", "q4c", "q4d"],
                   "passed": True, "buyer_gain": str(buyer_gain), "sponsor_exit": str(sponsor_exit), "lp_exit": str(lp_exit)})

    # Q5 new/old loan closure, endogenous risk-shift incentive and covenant funding.
    payment_now = F(14 + 40 - 2 - 6)
    gap = 50 - payment_now
    old_final, new_final = gap * twentieth, 40 * twentieth
    service = old_final + new_final
    prudent_total = F(60 + 6)
    prudent_equity = prudent_total - service
    equal((payment_now, gap, old_final, new_final, prudent_equity),
          (F(46), F(4), F(21, 5), F(42), F(99, 5)), "Q5a claims")
    equal(payment_now + old_final / twentieth, F(50), "Q5a old claim value")
    gamble = []
    for cash in (F(106), F(16)):
        new = min(new_final, cash)
        old = min(old_final, max(cash - new, 0))
        equity = cash - new - old
        gamble.append((new, old, equity))
        equal(new + old + equity, cash, "Q5b state cash")
    equal(gamble, [(F(42), F(21, 5), F(299, 5)), (F(16), F(0), F(0))], "Q5b priority")
    expected_equity = sum(row[2] for row in gamble) / 2
    lender_value = sum(row[0] for row in gamble) / 2 / twentieth
    old_extension_value = sum(row[1] for row in gamble) / 2 / twentieth
    equal((expected_equity, lender_value, old_extension_value), (F(299, 10), F(580, 21), F(2)), "Q5b priced claims")
    total_loss = (prudent_total - F(106 + 16, 2)) / twentieth
    equal(total_loss, F(100, 21), "Q5b resource/value loss")
    equal((expected_equity - prudent_equity) / twentieth + (lender_value - 40)
          + (old_extension_value - gap), -total_loss, "Q5b old-claim transfers plus value change")
    base_cash, stress_cash = F(64), F(50)
    equal((base_cash / service, base_cash - service), (F(320, 231), F(89, 5)), "Q5c base")
    equal(stress_cash / service, F(250, 231), "Q5c stress coverage")
    compliance_gap = F(11, 10) * service - stress_cash
    equal(compliance_gap, F(41, 50), "Q5c covenant cash gap")
    if not (stress_cash > service and stress_cash / service < F(11, 10)):
        raise AssertionError("Q5c payment versus covenant distinction failed")
    waiver_cash = stress_cash - 1
    waiver_coverage = waiver_cash / service
    equity_one, equity_two = waiver_cash - service, F(14)
    waiver_equity = equity_one / twentieth + equity_two / twentieth ** 2
    equal((waiver_coverage, equity_one, equity_two, waiver_equity),
          (F(35, 33), F(14, 5), F(14), F(968, 63)), "Q5d waiver")
    if waiver_coverage < F(21, 20):
        raise AssertionError("Q5d waiver does not pass")
    # Same gain via timing loss and external fee from monitored base equity.
    equal(F(89, 5) / twentieth - (14 / twentieth - 14 / twentieth ** 2) - 1 / twentieth,
          waiver_equity, "Q5d full reforecast versus timing decomposition")
    # Retaining the old 1.10 floor while adding the waiver fee does not pass.
    if waiver_coverage >= F(11, 10):
        raise AssertionError("Q5d must need actual covenant amendment")
    groups.append({"domain": "D5", "parts": ["q5a", "q5b", "q5c", "q5d"],
                   "passed": True, "lender_under_gamble": str(lender_value), "waiver_equity": str(waiver_equity)})

    exam_path = ROOT / "content" / "assessments" / "parts" / "v08-exam-b.html"
    text = exam_path.read_text()
    parsed = Exam()
    parsed.feed(text)
    equal(parsed.stack, [], "HTML nesting")
    expected_ids = [f"v08-b-q{q}{part}" for q in range(1, 6) for part in "abcd"]
    equal(list(parsed.parts), expected_ids, "twenty ordered question parts")
    equal(parsed.answers, expected_ids, "one-to-one ordered complete answers")
    equal(list(parsed.parts.values()), [5] * 20, "equal analytic part weights")
    equal(sum(parsed.parts.values()), 100, "exam total")
    equal(len(parsed.ids), len(set(parsed.ids)), "unique HTML ids")
    for q in range(1, 6):
        equal(sum(parsed.parts[f"v08-b-q{q}{p}"] for p in "abcd"), 20, "domain score")
    for key, values in parsed.answer_texts.items():
        if "5 points:" not in "".join(values):
            raise AssertionError(f"Missing analytic allocation in {key}")
    for token in ("240 minutes", "nonprogrammable calculator", "85/100", "15/20", "form-b", "solutions-b"):
        if token not in text:
            raise AssertionError(f"Missing assessment contract token {token}")
    for chapter in range(1, 13):
        if f'v08-c{chapter:02}.html' not in text:
            raise AssertionError("Missing accepted method/remediation link")
    if "projects/" in text or any(line != line.rstrip() for line in text.splitlines()):
        raise AssertionError("Bad flattened asset path or trailing whitespace")
    groups.append({"group": "assessment_structure", "passed": True, "points": 100,
                   "parts": 20, "solutions": 20, "visible_words": len(re.findall(r"\S+", " ".join(parsed.words)))})
    result = {"assessment": "v08-exam-b", "passed": True, "groups": groups,
              "limits": "Exact original case checks plus structural rubric mapping; manual reasoning/source review remains separate. No external exam calibration or UI certification."}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
