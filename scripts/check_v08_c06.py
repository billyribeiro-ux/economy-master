"""Independent exact shareholder-claim and dated cash checks for v08-c06."""
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


def shareholder_claims(data, result):
    """Value each sold/retained tranche independently of EPS."""
    p = data["payout"]; r = result["payout"]
    equity, shares, cash, owner, income, yield_ = [F(p[k]) for k in (
        "equity_value", "shares", "distribution", "holder_shares",
        "forecast_income_before", "cash_income_rate")]
    original = equity / shares
    need(F(r["dividend_holder_cash"]) == owner * cash / shares, "owner dividend cash")
    need(F(r["ex_dividend_price"]) * shares + cash == equity, "dividend conserves all claims")
    need(F(r["dividend_holder_wealth"]) == owner * original, "dividend wealth")
    need(F(r["income_after"]) == income - yield_ * cash, "foregone cash income")
    need(F(r["dividend_eps"]) == (income-yield_*cash)/shares, "dividend forward EPS")
    for row in r["repurchases"]:
        price = F(row["execution_price"])
        bought = cash / price; retained = shares - bought
        before_sold = bought * original; before_retained = retained * original
        need(F(row["retired_shares"]) == bought and F(row["remaining_shares"]) == retained, "share conservation")
        need(F(row["equity_after"]) == equity-cash, "aggregate remaining equity")
        need(F(row["value_per_remaining_share"]) * retained + cash == equity, "repurchase conserves all claims")
        need(F(row["selling_group_transfer"]) == cash-before_sold, "seller claim transfer")
        need(F(row["remaining_group_transfer"]) == equity-cash-before_retained, "continuing claim transfer")
        need(F(row["selling_group_transfer"])+F(row["remaining_group_transfer"]) == 0, "zero-sum owner transfers")
        need(F(row["forecast_eps"]) == (income-yield_*cash)/retained, "correct forward earnings denominator")
        need(F(row["pro_rata_holder_cash"]) == owner/shares*cash, "pro-rata owner cash")
        need(F(row["pro_rata_holder_shares"]) == owner/shares*retained, "pro-rata retained shares")
        need(F(row["pro_rata_holder_wealth"]) == owner*original, "owner's two tranches sum to original wealth")


def dated_ledger(p, scenario, payout):
    """Post gross cash transactions and contractual debt events date by date."""
    cash, term = F(p["opening_cash"]), F(p["term_debt"])
    minimum, rate, limit, cap = [F(p[k]) for k in ("minimum_cash", "quarter_rate", "line_limit", "total_debt_cap")]
    q = F(payout); lag = F(scenario["delayed_collection"]); prepay = F(scenario["supplier_prepayment"])
    events = []; lines = {}; closing = {}
    def post(date, label, amount):
        nonlocal cash
        amount = F(amount); cash += amount; events.append((date, label, amount))
    post(0, "owner payout", -q); closing[0] = cash
    for t in (1, 2):
        post(t, "customer receipts", F(p["base_receipts"][t-1]) + (-lag if t == 1 else lag))
        post(t, "supplier payments", -F(p["base_operating_payments"][t-1]) + (-prepay if t == 1 else prepay))
        post(t, "term interest on opening principal", -term*rate)
        if t == 1:
            post(t, "project purchase", -F(p["project_cost_at_one"]))
            lines["cash_before_draw"] = cash
            draw = max(F(0), minimum-cash)
            available = min(limit, cap-term)
            lines.update(required_draw=draw, effective_line=available)
            if draw > available:
                lines.update(status="funding-failure-at-date-one", gap=draw-available, available_cash=cash+available)
                return lines, closing, events
            post(t, "new revolver proceeds", draw)
            closing[t] = cash
        else:
            post(t, "additional project receipt", F(p["project_receipt_at_two"]))
            post(t, "revolver opening-principal interest", -draw*rate)
            amort = F(p["term_repayment_at_two"])
            post(t, "term principal repayment", -amort); term -= amort
            post(t, "complete revolver principal repayment", -draw)
            closing[t] = cash
    lines.update(status="funded" if cash >= minimum else "funding-failure-at-date-two", closing_term=term)
    if cash < minimum: lines["gap"] = minimum-cash
    return lines, closing, events


def treasury_claims(p, scenario, q, row):
    expected, close, events = dated_ledger(p, scenario, q)
    need(row["status"] == expected["status"], "cash calendar funding classification")
    for field in ("cash_before_draw", "required_draw"):
        need(F(row[field]) == expected[field], "gross-event ledger " + field)
    need(F(row["effective_line_at_one"]) == expected["effective_line"], "actual draw capacity")
    need(F(row["cash_after_payout"]) == close[0], "initial cash after irreversible payout")
    op = [F(p["base_receipts"][0])-F(scenario["delayed_collection"])-F(p["base_operating_payments"][0])-F(scenario["supplier_prepayment"]),
          F(p["base_receipts"][1])+F(scenario["delayed_collection"])-F(p["base_operating_payments"][1])+F(scenario["supplier_prepayment"])]
    need([F(x) for x in row["operating_cash"]] == op, "gross working-capital timing")
    if expected["status"] == "funding-failure-at-date-one":
        need(row["closing"] is None and F(row["gap"]) == expected["gap"], "unfunded project has no closing claim")
        need(F(row["cash_after_maximum_draw"]) == expected["available_cash"], "actual cash at maximum draw")
        return len(events)
    draw = expected["required_draw"]
    need(F(row["cash_at_one"]) == close[1] and F(row["revolver_at_one"]) == draw, "first cash and debt stock")
    need(F(row["line_headroom"]) == F(p["line_limit"])-draw, "headline unused line")
    need(F(row["covenant_headroom"]) == F(p["total_debt_cap"])-F(p["term_debt"])-draw, "debt covenant headroom")
    need(F(row["usable_debt_headroom"]) == expected["effective_line"]-draw, "usable headroom")
    need(F(row["revolver_interest"]) == draw*F(p["quarter_rate"]), "one quarter on new borrowing")
    need(F(row["cash_after_all_date_two_payments"]) == close[2], "maturity cash after all payments")
    need(close[2] == F(p["opening_cash"])+sum(x[2] for x in events), "whole-horizon signed cash ledger")
    if expected["status"] == "funded":
        need(F(row["closing"]["cash"]) == close[2] and F(row["closing"]["term_debt"]) == expected["closing_term"] and row["closing"]["revolver"] == "0", "all closing cash/debt claims")
    else:
        need(row["closing"] is None and F(row["gap"]) == expected["gap"], "no invented facility rollover")
    return len(events)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ids=[]; self.links=[]; self.sources=[]; self.examples=0
        self.exercises=0; self.answers=0; self.ol_depth=0; self.exercise_depth=0; self.in_answers=False; self.h1=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if "id" in a: self.ids.append(a["id"])
        if tag == "h1": self.h1 += 1
        if tag == "a": self.links.append(a.get("href", ""))
        if "data-source" in a: self.sources.append(a["data-source"])
        if "worked" in a.get("class", "").split(): self.examples += 1
        if tag == "ol":
            self.ol_depth += 1
            if "exercises" in a.get("class", "").split(): self.exercise_depth=self.ol_depth
        if tag == "details" and "solutions" in a.get("class", "").split(): self.in_answers=True
        if tag == "li" and self.exercise_depth == self.ol_depth and self.exercise_depth: self.exercises += 1
        if tag == "li" and self.in_answers: self.answers += 1
        if tag not in {"br", "hr", "img", "input", "meta", "link"}: self.stack.append(tag)
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1] == tag, "HTML nesting " + tag); self.stack.pop()
        if tag == "ol":
            if self.exercise_depth == self.ol_depth: self.exercise_depth=0
            self.ol_depth -= 1
        if tag == "details": self.in_answers=False


def check():
    spec = importlib.util.spec_from_file_location("payout_liquidity_lab", PROJECT/"v08-c06-analysis.py")
    lab = importlib.util.module_from_spec(spec)
    data = json.loads((PROJECT/"v08-c06-inputs.json").read_text())
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        spec.loader.exec_module(lab); result=lab.run(data)
    need(not capture.getvalue(), "quiet import and calculation"); json.dumps(result, allow_nan=False)
    groups=[]; shareholder_claims(data, result); r=result["payout"]
    need(r["fair_price_before"] == "10" and r["eps_before"] == "1" and r["dividend_eps"] == "9/10", "Portico initial and dividend anchors")
    prices = r["repurchases"]
    need([x["retired_shares"] for x in prices] == ["20", "25", "16"], "Portico retirement anchors")
    need([x["value_per_remaining_share"] for x in prices] == ["10", "32/3", "200/21"], "Portico claim price anchors")
    need([x["forecast_eps"] for x in prices] == ["9/8", "6/5", "15/14"], "Portico EPS anchors")
    need([x["remaining_group_transfer"] for x in prices] == ["0", "50", "-40"], "overprice loses value despite EPS accretion")
    need(F(prices[0]["forecast_eps"])/F(r["eps_before"])-1 == F(1, 8), "fair buyback EPS growth")
    need(10*F(prices[0]["value_per_remaining_share"]) == 100 and F(10, 80) == F(1, 8), "nonseller wealth and ownership")
    no_payout=deepcopy(data); no_payout["payout"]["distribution"]=0
    zero=lab.run(no_payout); shareholder_claims(no_payout, zero)
    need(all(x["remaining_group_transfer"] == "0" for x in zero["payout"]["repurchases"]), "zero payout boundary")
    groups.append({"name":"Independent sold/retained shareholder claims, conserved wealth, forward EPS and mispricing transfers", "status":"pass"})

    p=data["liquidity"]; paths=result["liquidity"]["paths"]; count=0
    for q, states in paths.items():
        for name, row in states.items(): count += treasury_claims(p, p["scenarios"][name], q, row)
    need([paths["10"][s]["required_draw"] for s in p["scenarios"]] == ["0", "22", "30"], "date-one draw anchors")
    need([paths["10"][s]["closing"]["cash"] for s in p["scenarios"]] == ["62", "1528/25", "304/5"], "date-two cash anchors")
    need(paths["8"]["combined"]["usable_debt_headroom"] == "2" and paths["8"]["combined"]["closing"]["cash"] == "1572/25", "payout eight margin")
    need(paths["25"]["slow_collection"]["gap"] == "7" and paths["25"]["combined"]["gap"] == "15", "permitted payout can fail funding")
    need(paths["25"]["combined"]["cash_after_maximum_draw"] == "5", "not a fictional closing buffer of twenty")
    need(result["liquidity"]["project_npv_at_date_one"] == "60/13", "dated incremental project NPV")
    groups.append({"name":"Fifteen state/payout paths independently reconstructed from gross cash and debt events", "status":"pass", "cash_events":count})

    bounds=result["liquidity"]["limits"]
    need([x["date_one_bound"] for x in bounds["scenario_bounds"].values()] == ["43", "18", "10"], "earliest-state payout bounds")
    need([x["date_two_bound"] for x in bounds["scenario_bounds"].values()] == ["101/2", "644/13", "640/13"], "complete maturity bounds")
    need(bounds["maximum_across_supplied_states"] == "10", "robust baseline maximum")
    # Independently test the boundary and the absence of hidden probabilities.
    for half in range(21):
        q=F(half, 2)
        need(all(dated_ledger(p, s, q)[0]["status"] == "funded" for s in p["scenarios"].values()), "feasible interval through ten")
    above=lab.encode(lab.treasury(p, p["scenarios"]["combined"], "1001/100"))
    treasury_claims(p, p["scenarios"]["combined"], "1001/100", above)
    need(above["gap"] == "1/100", "exact boundary breach")
    transfers=[]
    for prepayment, maximum, end in [(4,14,"284/5"), (9,9,"309/5")]:
        changed=deepcopy(data); changed["liquidity"]["scenarios"]["combined"]["supplier_prepayment"]=prepayment
        changed["liquidity"]["candidate_payouts"]=[maximum]
        output=lab.run(changed); cp=changed["liquidity"]; row=output["liquidity"]["paths"][str(maximum)]["combined"]
        need(output["liquidity"]["limits"]["maximum_across_supplied_states"] == str(maximum), "working-capital transfer maximum")
        treasury_claims(cp, cp["scenarios"]["combined"], maximum, row)
        need(row["closing"]["cash"] == end and row["required_draw"] == "30", "transfer closing cash")
        transfers.append(maximum)
    tight=deepcopy(data); tight["liquidity"]["total_debt_cap"]=75
    tr=lab.run(tight)
    need(tr["liquidity"]["limits"]["maximum_across_supplied_states"] == "5" and tr["liquidity"]["paths"]["10"]["combined"]["gap"] == "5", "tighter debt cap")
    maturity=deepcopy(data); maturity["liquidity"]["base_receipts"][1]=74; maturity["liquidity"]["candidate_payouts"]=[5,6]
    mr=lab.run(maturity); mp=maturity["liquidity"]
    need(mr["liquidity"]["limits"]["maximum_across_supplied_states"] == "5", "later repayment can bind first")
    for q in (5,6): treasury_claims(mp, mp["scenarios"]["combined"], q, mr["liquidity"]["paths"][str(q)]["combined"])
    need(mr["liquidity"]["paths"]["5"]["combined"]["closing"]["cash"] == "20", "maturity boundary cash")
    need(mr["liquidity"]["paths"]["6"]["combined"]["gap"] == "26/25", "no rollover at maturity shortfall")
    impossible=deepcopy(data); impossible["liquidity"]["scenarios"]["combined"]["supplier_prepayment"]=25
    ir=lab.run(impossible)
    need(ir["liquidity"]["limits"]["maximum_across_supplied_states"] is None and ir["liquidity"]["paths"]["0"]["combined"]["gap"] == "7", "zero payout need not be feasible")
    groups.append({"name":"Exact feasible payout boundary, working-capital/covenant transfers, binding maturity and no-feasible-payout case", "status":"pass"})

    # Independent full-tax liquidation uses distinct remaining bases.
    dividend_cash=20-20*F(3,10); dividend_sale=80-(80-60)*F(1,5)
    rep_cash=20-(20-12)*F(1,5); rep_sale=80-(80-48)*F(1,5)
    tax=result["personal_tax"]
    need([F(tax[k]) for k in ("dividend_event_net_cash","dividend_remaining_sale_net","repurchase_event_net_cash","repurchase_remaining_sale_net")] == [dividend_cash, dividend_sale, rep_cash, rep_sale], "distinct cost bases and tax realization")
    need(dividend_cash+dividend_sale == 90 and rep_cash+rep_sale == 92, "full after-tax proceeds")
    need(tax["dividend_total_after_liquidation"] == "90" and tax["repurchase_total_after_liquidation"] == "92", "tax output anchors")
    need(result["retained_cash"] == {"value":"808/21","loss_against_immediate_distribution":"32/21"}, "restricted-retention benchmark")
    # Exercise 1: both ownership routes; exercise 2: explicit lost income.
    need(F(720,60) == 12 and F(720-120,60) == 10 and F(120,12) == 10, "exercise one share prices")
    need(6*2+6*10 == 1*12+5*12 == 72, "exercise one owner wealth")
    post_income=72-180*F(1,50); eps=post_income/(90-18)
    need(post_income == F(342,5) and eps == F(19,20) and eps/F(4,5)-1 == F(3,16), "exercise two EPS and growth")
    need(F(10)/F(4,5)*eps == F(95,8) and F(900-180,90-18) == 10, "unchanged old multiple contradicts actual price")
    for price, bought, remaining_price, holder_gain in [(8,15,F(32,3),30),(12,10,F(48,5),-20)]:
        need(F(120,price) == bought and F(480,60-bought) == remaining_price and 480-(60-bought)*10 == holder_gain, "exercise three transfer")
    future=50*F(51,50)**2; value=future/F(21,20)**2
    need(future == F(2601,50) and value == F(2312,49) and 50-value == F(138,49), "exercise five restricted retention")
    need(60-24-2-30+40-20 == 24 and 50+40-80 == 10, "exercise six headline-line error")
    gross=F(20)-(60-10-28-2-30+25)+2
    repair_cash=20+48+36-2-F(25,25)-10-25
    need(gross == 7 and gross-2 == 5 and repair_cash == 66, "exercise seven gross equity, fee and full maturity cash")
    need(60-10+20-30+36-4-10+gross-2-1 == repair_cash, "independent repaired whole-horizon cash")
    need(F(40)*F(101,100)/F(21,20) == F(808,21), "retention matching certain rate")
    groups.append({"name":"All numerical exercises, fictional tax-basis liquidation, restricted retention and explicit emergency-equity repair", "status":"pass"})

    failures=[("units",lambda x:x.update(units="USD")),
              ("floating input",lambda x:x["payout"].update(distribution=200.0)),
              ("negative payout",lambda x:x["payout"].update(distribution=-1)),
              ("retire all shares",lambda x:x["payout"].update(repurchase_prices=[2])),
              ("excess cash unavailable",lambda x:x["payout"].update(available_excess_cash=100)),
              ("no supplied execution",lambda x:x["payout"].update(repurchase_prices=[])),
              ("opening covenant breach",lambda x:x["liquidity"].update(total_debt_cap=40)),
              ("nonexistent shifted collection",lambda x:x["liquidity"]["scenarios"]["combined"].update(delayed_collection=101)),
              ("timing contract",lambda x:x["liquidity"]["dates"].__setitem__(1,"2027-02-01"))]
    for name, change in failures:
        bad=deepcopy(data); change(bad)
        try: lab.run(bad)
        except ValueError: pass
        else: raise AssertionError("unsupported contract accepted: " + name)
    bad=deepcopy(result); bad["payout"]["repurchases"][0]["value_per_remaining_share"]="45/4"
    try: shareholder_claims(data,bad)
    except AssertionError: pass
    else: raise AssertionError("EPS-based fabricated price escaped claim conservation")
    bad=deepcopy(paths["10"]["combined"]); bad["closing"]["cash"]="454/5"
    try: treasury_claims(p,p["scenarios"]["combined"],10,bad)
    except AssertionError: pass
    else: raise AssertionError("omitted revolver principal escaped cash ledger")
    forbidden=lab.encode(lab.treasury(p,p["scenarios"]["normal"],26))
    need(forbidden["status"] == "payout-not-permitted-at-date-zero" and forbidden["closing"] is None, "initial distribution permission")
    groups.append({"name":"Nine input-domain failures, rejected payout permission and detection of fabricated EPS price/omitted principal", "status":"pass"})

    html=(BOOK/"content/chapters/v08-c06.html").read_text(); doc=Fragment(); doc.feed(html); doc.close()
    need(not doc.stack and doc.h1 == 0 and len(doc.ids) == len(set(doc.ids)), "balanced unique HTML fragment")
    need(doc.examples == 3 and doc.exercises == doc.answers == 8, "complete instructional counts")
    need("Teach-back" in html and "Delayed check" in html and html.count("<strong>Answer:</strong>") == 2, "answered teaching and retention")
    sources=json.loads((BOOK/"content/reviews/v08-c06-sources.json").read_text())
    need({s["id"] for s in sources} == set(doc.sources) == {h.split("#")[1] for h in doc.links if h.startswith("sources.html#")}, "matching inspected sources")
    need(len(sources) == 3 and all(s["checked"] == "2026-10-08" and s["verification"] for s in sources), "scoped source inspection records")
    curriculum=json.loads((BOOK/"content/curriculum.json").read_text())
    chapter_ids={c["id"] for v in curriculum["volumes"] for c in v["chapters"]}
    for suffix in ("inputs.json","analysis.py","README.txt"):
        name="v08-c06-"+suffix
        need(name in doc.links and (PROJECT/name).is_file(), "flat downloadable asset " + name)
    for link in doc.links:
        if link.startswith("v") and link.endswith(".html"):
            need(link[:-5] in chapter_ids and (BOOK/"content/chapters"/link).is_file(), "existing manuscript reference " + link)
        if link.startswith("curriculum.html#"):
            need(link.split("#")[1] in chapter_ids, "canonical planned reference " + link)
    with tempfile.TemporaryDirectory(prefix="v08-c06-check-") as name:
        tmp=Path(name)
        for filename in ("v08-c06-inputs.json","v08-c06-analysis.py"): shutil.copy2(PROJECT/filename,tmp/filename)
        for flags in ([],["-O"]):
            cli=subprocess.run([sys.executable,*flags,str(tmp/"v08-c06-analysis.py")],cwd=tmp.parent,text=True,capture_output=True,check=False)
            need(cli.returncode == 0 and not cli.stderr and json.loads(cli.stdout) == result, "portable normal/optimized benchmark")
        bad=deepcopy(data); bad["units"]="wrong"; bad_path=tmp/"bad.json"; bad_path.write_text(json.dumps(bad))
        cli=subprocess.run([sys.executable,str(tmp/"v08-c06-analysis.py"),str(bad_path)],text=True,capture_output=True,check=False)
        need(cli.returncode == 2 and not cli.stdout and "Invalid payout/liquidity contract" in cli.stderr, "invalid CLI has no result payload")
    groups.append({"name":"Three worked cases/eight full pairs, answered checks, assets/sources, strict quiet JSON and portable CLI", "status":"pass"})
    report={"chapter":"v08-c06", "status":"passed", "checks":groups,
            "limitations":["All prices, dates, tax rules and funding contracts are fictional supplied assumptions.",
                           "Feasibility across the named cash dates is not an optimal payout, real legal permission or daily liquidity guarantee.",
                           "Full instructional/source review, coordinator acceptance and visual QA are separate from arithmetic checks."]}
    json.dumps(report,allow_nan=False)
    return report


if __name__ == "__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
