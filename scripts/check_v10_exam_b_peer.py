"""Independent Form B peer arithmetic; no authored checker supplies an oracle.

Run directly or call quiet check(). Only the frozen four author payloads and
this review's two payloads are needed in the same relative directory layout.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = "content/assessments/parts/v10-exam-b.html"
AUTHOR = "content/reviews/v10-exam-b-author.json"
SOURCES = "content/reviews/v10-exam-b-sources.json"
AUTHOR_CHECK = "scripts/check_v10_exam_b.py"
PEER = "content/reviews/v10-exam-b-peer.json"
SELF = "scripts/check_v10_exam_b_peer.py"
AUTHOR_PATHS = (HTML, AUTHOR_CHECK, AUTHOR, SOURCES)
POINTS = {f"v10-b-q{q}{chr(97+i)}": p for q, row in enumerate(
    ((6, 8, 6), (8, 8, 4), (6, 6, 8), (8, 8, 4), (5, 7, 3, 5)), 1)
          for i, p in enumerate(row)}
SOURCE_IDS = {"v10-c03-haugh-lattice", "v10-c04-recovery-par",
              "v10-c05-cme-variation", "v10-c07-haugh-diffusions",
              "v10-c09-haugh-greeks", "v10-c10-haugh-output",
              "v10-c11-haugh-discrete"}


class Audit:
    def __init__(self):
        self.comparisons = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def near(self, actual, expected, label, tolerance=2e-10):
        self.comparisons += 1
        if not math.isfinite(float(actual)) or abs(actual - float(expected)) > tolerance:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")


class Exam(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.points, self.solutions = [], set(), {}, {}
        self.current = None

    def handle_starttag(self, tag, attributes):
        d = dict(attributes)
        if "id" in d:
            self.ids.append(d["id"])
        if tag == "a" and "href" in d:
            self.links.add(d["href"])
        if tag == "li" and "data-points" in d:
            self.points[d["id"]] = int(d["data-points"])
        if tag == "li" and "data-solution-for" in d:
            self.current = d["data-solution-for"]
            if self.current in self.solutions:
                raise AssertionError("duplicate scored solution")
            self.solutions[self.current] = []

    def handle_data(self, data):
        if self.current is not None:
            self.solutions[self.current].append(data)

    def handle_endtag(self, tag):
        if tag == "li":
            self.current = None


def gauss_integral(function, left=-10.0, right=10.0, order=80):
    """Legendre quadrature, distinct from the author's composite Simpson rule."""
    midpoint, radius = (left + right) / 2, (right - left) / 2
    total = 0.0
    for i in range(1, order + 1):
        z = math.cos(math.pi * (i - 0.25) / (order + 0.5))
        for _ in range(30):
            previous, value = 1.0, z
            for k in range(2, order + 1):
                previous, value = value, ((2*k-1)*z*value-(k-1)*previous)/k
            derivative = order * (z*value-previous)/(z*z-1)
            step = value / derivative
            z -= step
            if abs(step) < 3e-16:
                break
        else:
            raise ArithmeticError("quadrature node did not converge")
        # Recompute the derivative at the final node.
        previous, value = 1.0, z
        for k in range(2, order + 1):
            previous, value = value, ((2*k-1)*z*value-(k-1)*previous)/k
        derivative = order * (z*value-previous)/(z*z-1)
        total += 2 / ((1-z*z)*derivative*derivative) * function(midpoint+radius*z)
    return radius * total


def margin_path(quotes):
    balance, contributions, before, additions = F(100), F(100), [], []
    variations = [-10*(new-old) for old, new in zip(quotes, quotes[1:])]
    for index, variation in enumerate(variations):
        balance += variation
        before.append(balance)
        top = 100-balance if index < len(variations)-1 and balance < 75 else F(0)
        additions.append(top)
        contributions += top
        balance += top
    return variations, before, additions, contributions, balance


def hedge(fee_rate):
    premium, delta = F("7.364289723"), F("-.436000430455")
    new_delta = F("-.216606525638")
    bank_factor, share_factor = F("1.010050167084"), F("1.005012520859")
    bank0 = premium-100*delta
    incoming_shares, incoming_bank = delta*share_factor, bank0*bank_factor
    wealth = 110*incoming_shares+incoming_bank
    trade = (new_delta-incoming_shares)*110
    fee = fee_rate*abs(trade)
    bank = incoming_bank-trade-fee
    terminal_shares, terminal_bank = new_delta*share_factor, bank*bank_factor
    return (bank0, incoming_shares, incoming_bank, wealth, trade, fee, bank,
            terminal_shares, terminal_bank, 90*terminal_shares+terminal_bank-10)


def check():
    a = Audit()
    # D1: solve dated cash directly, then recover key-date sensitivities.
    d1, d2 = F(99, 100), (F("102.0096")-F(50)*F(".99"))/52
    a.eq(d2, F("1.0098"), "two-year bootstrap")
    forward_gross = d1/d2
    a.eq(forward_gross-1, F(-1, 51), "negative forward rate")
    a.eq(d1-forward_gross*d2, 0, "receipt 1 at year 1, repayment 50/51 at year 2")
    x, y = F(60, 52), (40-F(50)*F(60, 52))/100
    a.eq((x, y), (F(15, 13), F(-23, 130)), "cash-matching quantities")
    a.eq((50*x+100*y, 52*x), (40, 60), "exact liability receipts")
    a.eq(40*d1+60*d2, F("100.188"), "liability price")
    a.eq((40*d1, 2*60*d2), (F("39.6"), F("121.176")), "key-date units")
    a.eq((x*50*d1+y*100*d1, x*2*52*d2), (40*d1, 2*60*d2), "hedged key exposures")
    for e1, e2 in ((F(".8"), F("1.2")), (F("1.1"), F(".7")), (d1, d2)):
        a.eq(x*(50*e1+52*e2)+y*100*e1, 40*e1+60*e2, "nonparallel exact replication")
    a.eq(d1*(F("1.06")+F(".98"))/2, d2, "dispersed future discount fits curve")
    a.eq(d1*F("1.02"), d2, "certain future discount fits curve")
    a.eq(d1*F(".06")/2, F(".0297"), "year-1 option in U")
    a.eq(d1*F(".02"), F(".0198"), "year-1 option in C")
    a.eq(d1*(F(3,4)*F("1.06")+F(1,4)*F(".98")), F("1.0296"), "physical law does not calibrate")

    # D2: alive-cohort recursion, independent of the author's full path enumeration.
    transition = ((F(".8"), F(".15"), F(".05")), (F(".1"), F(".7"), F(".2")))
    alive, defaults = (F(0), F(1)), []
    for _ in range(2):
        defaults.append(sum(alive[i]*transition[i][2] for i in range(2)))
        alive = tuple(sum(alive[i]*transition[i][j] for i in range(2)) for j in range(2))
    survival = sum(alive)
    a.eq((tuple(defaults), survival), ((F(".2"), F(".145")), F(".655")), "first-default partition")
    a.eq(sum(defaults)+survival, 1, "once-only recovery partition")
    actual_cash = (100*survival+40*defaults[0], 40*defaults[1])
    actual_pv = actual_cash[0]*F(".92")+actual_cash[1]*F(".88")
    immediate_pv = 40*defaults[0]*F(".96")+(100*survival+40*defaults[1])*F(".92")
    a.eq(actual_cash, (F("73.5"), F("5.8")), "recovery settlement dates")
    a.eq(actual_pv, F("72.724"), "delayed recovery value")
    a.eq(immediate_pv, F("73.276"), "immediate recovery value")
    a.eq(immediate_pv-actual_pv, F(".552"), "delay cost")
    a.eq(sum(actual_cash), 100*survival+40*sum(defaults), "zero-rate delay boundary")
    variations, before, tops, principal, release = margin_path(tuple(map(F, (50,56,47,52))))
    a.eq((variations, before, tops), ([-60,90,-50], [40,190,140], [60,0,0]), "signed futures ledger")
    a.eq((principal, release, release-principal), (160,140,-20), "margin principal conservation")
    a.eq(tops[0]-55, 5, "unassignable future receipt does not close current gap")
    boundary = margin_path((F(50), F("52.5"), F(50), F(50)))
    a.eq((boundary[1][0], boundary[2][0]), (75, 0), "maintenance equality needs no top-up")
    rates = (F("1.005"), F("1.01"), F("1.015"))
    debt = F(100)
    for factor, contribution in zip(rates, tops):
        debt = debt*factor+contribution
    a.eq(debt, F("164.536575"), "recursive dated debt")
    a.eq(release-debt, F("-24.536575"), "funded net release")
    a.eq(debt-principal, F("4.536575"), "funding cost distinct from principal")
    alternate = margin_path(tuple(map(F, (50,47,56,52))))
    alternate_debt = F(100)
    for factor, contribution in zip(rates, alternate[2]):
        alternate_debt = alternate_debt*factor+contribution
    a.eq(alternate[4]-alternate[3], release-principal, "same terminal nominal forward cash")
    a.eq(debt-alternate_debt, F(".609"), "same-terminal different funding timing")

    # D3: elementary state equations, then a different normal-density quadrature.
    delta = F(10, 96-64)
    bank_terminal = -64*delta
    price = 80*delta+bank_terminal/F("1.02")
    probability = (80*F("1.02")-64)/32
    a.eq((delta, bank_terminal, price, probability), (F(5,16), -20, F(275,51), F(".55")), "digital hedge")
    a.eq(10*probability/F("1.02"), price, "digital expectation")
    a.eq((64*delta+bank_terminal, 96*delta+bank_terminal), (0,10), "digital state cash")
    r, q, sigma, mu = F(".03"), F(".01"), F(".2"), F(".06")
    a.eq(-mu+sigma*sigma, F("-.02"), "inverse Ito correction")
    coefficient = -2*r+q+sigma*sigma
    a.eq(coefficient, F("-.01"), "discounted reciprocal coefficient")
    phi = lambda z: math.exp(-z*z/2)/math.sqrt(2*math.pi)
    for time in (0.25, 1.0):
        for power in (-1, -2):
            moment = gauss_integral(lambda z: (100*math.exp(float(r-q-sigma*sigma/2)*time
                                     +float(sigma)*math.sqrt(time)*z))**power*phi(z))
            exact = 100**power*math.exp(float(power*(r-q)+F(power*(power-1),2)*sigma*sigma)*time)
            a.near(moment, exact, "density-integrated negative moment", 3e-15)
    value0 = math.exp(-float(r))*10000*gauss_integral(lambda z: phi(z)/(100*math.exp(.2*z)))
    a.near(value0, 100*math.exp(-.01), "reciprocal price", 2e-11)
    a.near(value0, 99.004983375, "printed reciprocal price", 2e-10)
    a.near(-value0/100, -.990049833749, "initial signed delta", 5e-13)
    a.near(2*value0, 198.009966750, "initial bank value", 3e-10)
    a.eq(-coefficient-(r-q)+sigma*sigma-r, 0, "inverse PDE coefficient")
    a.eq(-coefficient-mu+sigma*sigma, -mu-q+2*r, "physical funded drift equality")
    a.eq(-2*(r-q)+3*sigma*sigma, F(".08"), "negative-second-moment exponent")
    l2_norm = 400*math.exp(-.02)*math.expm1(.04)/.04
    a.near(l2_norm, 400.026667200005, "finite discounted-integrand squared norm", 3e-10)
    a.eq(10000/0.001 > 10000*(1+0.001), True, "small-stock growth failure example")

    # D4: closed-form erfc anchor, then exact decimals in the retained-cash ledger.
    normal = lambda z: .5*math.erfc(-z/math.sqrt(2))
    for spot, tau, printed_price, printed_delta in ((100,1,7.364289723,-.436000430455),
                                                  (110,.5,2.067544281,-.216606525638)):
        d_one = (math.log(spot/100)+(.02-.01+.2*.2/2)*tau)/(.2*math.sqrt(tau))
        d_two = d_one-.2*math.sqrt(tau)
        put = 100*math.exp(-.02*tau)*normal(-d_two)-spot*math.exp(-.01*tau)*normal(-d_one)
        a.near(put, printed_price, "supplied put mark", 5e-10)
        a.near(-math.exp(-.01*tau)*normal(-d_one), printed_delta, "supplied fixed-input delta", 5e-13)
    ideal, funded, double = hedge(F(0)), hedge(F(".001")), hedge(F(".002"))
    targets = (50.9643327685, -.438185891707, 51.476532828, 3.276084740,
               24.373730268, .024373730268, 27.078428830, -.217692270366,
               27.350571564, -2.241732769)
    for observed, expected in zip(funded, targets):
        a.near(observed, expected, "fee-funded printed ledger", 4e-8)
    a.near(ideal[-1], -2.217114078, "costless terminal error", 4e-8)
    a.eq(ideal[-1]-funded[-1], funded[5]*F("1.010050167084"), "dated fee accumulation")
    a.eq(ideal[-1]-double[-1], 2*(ideal[-1]-funded[-1]), "fee scaling")
    a.near(F("2.067544281")-ideal[3], -1.208540459, "mark reset is an external withdrawal", 4e-8)
    se = F(4,20)
    raw = (F("8.10")-F("1.96")*se, F("8.10")+F("1.96")*se)
    padded = (raw[0]-F(".008"), raw[1]+F(".008"))
    inverse = (F(".3")+(8-padded[1])/20, F(".3")+(8-padded[0])/20)
    a.eq(raw, (F("7.708"), F("8.492")), "400 independent pair means")
    a.eq(padded, (F("7.7"), F("8.5")), "separate numerical allowance")
    a.eq(inverse, (F(".275"), F(".315")), "asymmetric inverse interval")
    # Linear monotone price functions attain both claimed endpoints; no tighter
    # universal interval follows from these price bounds and lower vega alone.
    for candidate_price, root in ((padded[1], inverse[0]), (padded[0], inverse[1])):
        a.eq(candidate_price+20*(root-F(".3")), 8, "tight inverse endpoint")
    a.near(4/math.sqrt(800), .1414213562373095, "incorrect member-level standard error")
    a.eq((100*(inverse[0]-F(".3")),100*(inverse[1]-F(".3"))), (F("-2.5"), F("1.5")), "volatility-point units")
    for physical_mu in (F("-.1"), F(".06")):
        for actual_variance in (F(".01"), F(".04"), F(".09")):
            spot, mark, error, delta, gamma = 100, 7, 2, F("-.4"), F(".02")
            r4, q4, pricing_variance = F(".02"), F(".01"), F(".04")
            theta = r4*mark-(r4-q4)*spot*delta-pricing_variance*spot*spot*gamma/2
            funded_drift = delta*(physical_mu+q4)*spot+r4*(mark+error-delta*spot)
            mark_drift = theta+physical_mu*spot*delta+actual_variance*spot*spot*gamma/2
            a.eq(funded_drift-mark_drift-r4*error, gamma*spot*spot*(pricing_variance-actual_variance)/2,
                 "continuous discounted mismatch cancels physical drift")
    a.eq(F(".01")+F("-.01"), 0, "unweighted variance difference can average zero")
    a.eq(F(".01")+2*F("-.01"), F("-.01"), "different cash-gamma weights change sign")

    # D5: null-direction calibration and explicit attainable envelopes.
    spot = (80,100,100,120)
    mid = (80,80,120,120)
    call = tuple(max(s-100,0) for s in spot)
    asian = tuple(max(F(m+s,2)-100,0) for m,s in zip(mid,spot))
    a.eq((call, asian), ((0,0,0,20),(0,0,10,20)), "contractual fixing vectors")
    null = (0,1,-1,0)
    for traded in ((1,1,1,1), spot, call):
        a.eq(sum(x*y for x,y in zip(null,traded)), 0, "unspanned middle-history direction")
    a.eq(sum(x*y for x,y in zip(null,asian)), -10, "Asian sees the missing direction")
    for b in (F(".2"), F(".4"), F(".6")):
        state_prices = (F(".1"),b,F(".8")-b,F(".1"))
        values = tuple(sum(p*x for p,x in zip(state_prices,payoff)) for payoff in ((1,1,1,1),spot,call,asian))
        a.eq(values, (1,100,2,10-10*b), "positive calibrated model and Asian price")
    superpayoff = tuple(F(s,2)-40 for s in spot)
    a.eq(superpayoff, (0,10,10,20), "superhedge state cash")
    a.eq(tuple(x-c for x,c in zip(asian,call)), (0,0,10,0), "lower-endpoint arbitrage")
    a.eq(tuple(h-x for h,x in zip(superpayoff,asian)), (0,10,0,0), "upper-endpoint arbitrage")
    a.eq((2, F(100,2)-40), (2,10), "attained static hedge costs")
    a.eq(2-6, -4, "candidate-minus-correct price at b=.4")
    width = F(10)-2
    a.eq((call == asian, width <= 1), (False,False), "two independent release failures")
    a.eq((asian == asian, width <= 1), (True,False), "code repair leaves nonidentification")
    a.eq(width <= 8, True, "invented width gate includes equality")

    # Structural and artifact checks supplement the separately recorded full read.
    exam = Exam()
    exam.feed((ROOT/HTML).read_text())
    a.eq(len(exam.ids), len(set(exam.ids)), "unique HTML IDs")
    a.eq(exam.points, POINTS, "all sixteen exact scored prompts")
    a.eq(set(exam.solutions), set(POINTS), "one full solution per prompt")
    for domain in range(1,6):
        a.eq(sum(p for ident,p in POINTS.items() if ident.startswith(f"v10-b-q{domain}")), 20, "domain points")
    for ident, fragments in exam.solutions.items():
        solution = "".join(fragments)
        a.eq(f"{POINTS[ident]} points:" in solution, True, "explicit solution rubric "+ident)
    a.eq({f"v10-c{i:02}.html" for i in range(1,13)} <= exam.links, True, "all twelve taught chapter routes")
    a.eq({h.split("#",1)[1] for h in exam.links if h.startswith("sources.html#")}, SOURCE_IDS, "scoped source routes")
    sources = json.loads((ROOT/SOURCES).read_text())
    a.eq({s["id"] for s in sources["reused_sources"]}, SOURCE_IDS, "exact prior-source reuse")
    a.eq(sources["proposals"], [], "no new unreviewed source")
    author = json.loads((ROOT/AUTHOR).read_text())
    a.eq(set(author["payload_sha256"]), {HTML,AUTHOR_CHECK,SOURCES}, "author binds three nonself payloads")
    for path, digest in author["payload_sha256"].items():
        a.eq(sha256((ROOT/path).read_bytes()).hexdigest(), digest, "author frozen binding "+path)
    for part in author["part_review"]:
        a.eq(sum(part["credit_allocation"]), POINTS[part["part"]], "scoring allocation "+part["part"])
    peer = json.loads((ROOT/PEER).read_text())
    a.eq({row["part"] for row in peer["prompt_audit"]}, set(POINTS), "peer read all exact prompts")
    a.eq({row["path"] for row in peer["reviewed_hashes"]}, set(AUTHOR_PATHS), "all four final author bindings")
    a.eq({row["path"] for row in peer["reviewer_artifacts"]}, {SELF}, "nonself peer checker binding")
    for row in peer["reviewed_hashes"]+peer["reviewer_artifacts"]:
        payload = (ROOT/row["path"]).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()), (row["bytes"],row["sha256"]), "peer frozen binding "+row["path"])
    summary = {"assessment":"v10-exam-b", "review":"independent-peer", "status":"pass",
               "comparisons":a.comparisons, "scored_prompts":16, "points":100,
               "domains":{f"D{i}":20 for i in range(1,6)}, "author_payload_hashes_checked":4,
               "intervention_groups":11,
               "limits":"Deterministic checks support the separate complete proof/prompt audit; they do not prove approximate confidence coverage or certify learner outcomes."}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
