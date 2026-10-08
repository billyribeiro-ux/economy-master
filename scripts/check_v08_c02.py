"""Independent exact cash-claim, valuation and instructional checks for v08-c02."""
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


class Ledger:
    """Separate signed journal: assets positive, claims negative."""
    def __init__(self):
        self.accounts = dict(cash=F(0), receivables=F(17, 2), ppe=F(40), debt=F(-40), equity=F(-17, 2))
        self.cash = {}; self.entries = 0
    def post(self, period, kind, **delta):
        delta = {k: F(v) for k, v in delta.items()}
        need(sum(delta.values()) == 0, "unbalanced independent entry")
        for key, value in delta.items():
            self.accounts[key] += value
        self.cash[period, kind] = self.cash.get((period, kind), F(0)) + delta.get("cash", F(0))
        need(sum(self.accounts.values()) == 0, "unbalanced journal prefix")
        self.entries += 1


def independent_journal():
    ledger = Ledger(); endings = []
    for t, sales, receipts, costs, dep, interest, tax, capex, repayment, dividend in [
        (1, 322, 325, 175, 25, 2, 30, 10, 20, 88),
        (2, 249, F(509, 2), 125, 25, 1, F(49, 2), 0, 20, 84)
    ]:
        ledger.post(t, None, receivables=sales, equity=-sales)
        ledger.post(t, "cfo", cash=receipts, receivables=-receipts)
        ledger.post(t, "cfo", cash=-costs, equity=costs)
        ledger.post(t, None, ppe=-dep, equity=dep)
        ledger.post(t, "cfo", cash=-interest, equity=interest)
        ledger.post(t, "cfo", cash=-tax, equity=tax)
        ledger.post(t, "cfi", cash=-capex, ppe=capex)
        ledger.post(t, "cff", cash=-repayment, debt=repayment)
        ledger.post(t, "cff", cash=-dividend, equity=dividend)
        endings.append(dict(ledger.accounts))
    return ledger, endings


def check_identities(result):
    r = result["runoff"]; q = F
    for row in r["periods"]:
        o, b = row["opening"], row["closing"]
        need(q(row["receipts"]) == q(row["sales"]) + q(o["receivables"]) - q(b["receivables"]), "collection identity")
        need(q(row["cfo"]) == q(row["receipts"]) - q(row["cash_operating_costs"]) - q(row["interest"]) - q(row["levered_cash_tax"]), "direct CFO")
        need(q(row["cfo"]) == q(row["net_income"]) + q(row["depreciation"]) - q(row["delta_wc"]) == q(row["indirect_cfo"]), "indirect CFO")
        need(q(row["fcfe"]) == q(row["cfo"]) - q(row["capex"]) + q(row["net_borrowing"]), "cash-to-equity identity")
        need(q(row["fcfe"]) == q(row["fcff"]) - q(row["interest"]) + q(row["tax_shield"]) + q(row["net_borrowing"]), "actual tax-shield bridge")
        need(q(row["fcfe"]) + q(row["debt_cash"]) == q(row["fcff"]) + q(row["tax_shield"]) == q(row["all_investor_cash"]), "all investor cash convention")
        need(q(b["cash"]) - q(o["cash"]) == q(row["cfo"]) + q(row["cfi"]) + q(row["cff"]), "cash rollforward")
        need(q(b["ppe"]) == q(o["ppe"]) + q(row["capex"]) - q(row["depreciation"]), "asset rollforward")
        need(q(b["book_equity"]) == q(o["book_equity"]) + q(row["net_income"]) - q(row["fcfe"]), "book equity rollforward")
        need(q(b["debt"]) == q(o["debt"]) + q(row["net_borrowing"]), "debt rollforward")
        need(q(b["ppe"]) + q(b["receivables"]) - q(o["ppe"]) - q(o["receivables"]) == q(row["net_reinvestment"]), "reinvestment stock/flow")
        need(q(row["opening_operating_value"]) == (q(row["fcff"]) + q(row["closing_operating_value"])) / (1 + q(row["wacc"])), "period FCFF value recursion")
        need(q(row["opening_operating_value"]) - q(o["debt"]) == q(row["opening_equity_value"]), "same-date market claims")
    need(q(r["fcff_value"]) == q(r["unlevered_value"]) + q(r["shield_value"]) == q(r["operating_values"][0]), "no duplicate financing benefit")
    need(q(r["fcfe_value"]) == q(r["fcff_value"]) - q(r["debt_cash_value"]), "two equity value routes")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ids=[]; self.links=[]; self.sources=[]; self.examples=0
        self.exercises=0; self.answers=0; self.ol_depth=0; self.exercise_depth=0; self.in_answers=False; self.h1=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if "id" in a:self.ids.append(a["id"])
        if tag=="h1":self.h1+=1
        if tag=="a":self.links.append(a.get("href", ""))
        if "data-source" in a:self.sources.append(a["data-source"])
        if "worked" in a.get("class", "").split():self.examples+=1
        if tag=="ol":
            self.ol_depth+=1
            if "exercises" in a.get("class", "").split():self.exercise_depth=self.ol_depth
        if tag=="details" and "solutions" in a.get("class", "").split():self.in_answers=True
        if tag=="li" and self.exercise_depth==self.ol_depth and self.exercise_depth:self.exercises+=1
        if tag=="li" and self.in_answers:self.answers+=1
        if tag not in {"br", "hr", "img", "input", "meta", "link"}:self.stack.append(tag)
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1]==tag, "HTML nesting "+tag); self.stack.pop()
        if tag=="ol":
            if self.exercise_depth==self.ol_depth:self.exercise_depth=0
            self.ol_depth-=1
        if tag=="details":self.in_answers=False


def check():
    spec=importlib.util.spec_from_file_location("free_cash_flow_lab", PROJECT/"v08-c02-analysis.py")
    lab=importlib.util.module_from_spec(spec)
    data=json.loads((PROJECT/"v08-c02-inputs.json").read_text())
    capture=io.StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        spec.loader.exec_module(lab); result=lab.run(data)
    need(not capture.getvalue(), "quiet import/run")
    json.dumps(result,allow_nan=False)
    groups=[]; r=result["runoff"]
    ledger,endings=independent_journal()
    for t,(row,end) in enumerate(zip(r["periods"],endings),1):
        for key,value in end.items():
            name="book_equity" if key=="equity" else key
            need(F(row["closing"][name]) == (-value if key in {"debt","equity"} else value), "independent closing journal "+name)
        for kind in ("cfo","cfi","cff"):
            need(F(row[kind])==ledger.cash[t,kind], "independent cash class "+kind)
    need(r["operating_values"]==["200","100","0"] and r["equity_values"]==["160","80","0"], "value anchors")
    need([row["fcff"] for row in r["periods"]]==["219/2","419/4"] and [row["fcfe"] for row in r["periods"]]==["88","84"], "cash claim anchors")
    check_identities(result)
    groups.append({"name":"Independent eighteen-entry journal, cash/capital/tax/claim identities and both equity valuations","status":"pass","entries":ledger.entries})

    # Rebuild prices from directly dated investor receipts, not lab recursion.
    zero1,zero2=F(20,21),F(400,441)
    equity=88*zero1+84*zero2; debt=22*zero1+21*zero2
    unlevered=F(219,2)*zero1+F(419,4)*zero2
    shields=F(1,2)*zero1+F(1,4)*zero2
    need(equity==160 and debt==40 and unlevered+shields==200, "independent discounted claims")
    need(r["unlevered_value"]==str(unlevered) and r["shield_value"]==str(shields), "separate financing-benefit values")
    need(r["waccs"]==["19/400","19/400"], "market-weight compatible rate")
    debt_change=deepcopy(data);debt_change["periods"][0]["closing_debt"]=40
    dr=lab.run(debt_change);check_identities(dr); d=dr["runoff"]
    need(d["fcfe_value"]==str(108*zero1+F(253,4)*zero2)=="70660/441", "changed debt direct shareholder value")
    need(d["operating_values"]==["88300/441","2105/21","0"] and d["waccs"]==["8389/176600","379/8420"], "changed debt prices/rates")
    need([row["fcff"] for row in d["periods"]]==["219/2","419/4"], "debt does not enter operating FCFF")
    delayed=deepcopy(data);delayed["periods"][0]["closing_receivables"]="21/2"
    delay=lab.run(delayed);check_identities(delay)
    need(delay["runoff"]["fcfe_value"]=="70460/441" and F(r["fcfe_value"])-F(delay["runoff"]["fcfe_value"])==5*zero1-5*zero2, "retention timing loss")
    need([row["fcfe"] for row in delay["runoff"]["periods"]]==["83","89"], "retention cash amounts")
    scaled=deepcopy(data)
    scaled["opening"]={k:str(F(v)*7) for k,v in scaled["opening"].items()}
    scaled["periods"]=[{k:str(F(v)*7) for k,v in row.items()} for row in scaled["periods"]]
    sr=lab.run(scaled);check_identities(sr)
    need(sr["runoff"]["fcfe_value"]=="1120" and sr["runoff"]["waccs"]==r["waccs"], "money scale preserves returns")
    zero_tax=deepcopy(data);zero_tax["tax_rate"]=0
    zr=lab.run(zero_tax);check_identities(zr)
    need(zr["runoff"]["shield_value"]=="0" and zr["runoff"]["waccs"]==["1/20","1/20"], "no-tax valuation boundary")
    groups.append({"name":"Independent dated pricing, debt-policy and collection transfers, money scaling and zero-tax boundary","status":"pass"})

    nom=result["real_nominal"];cur=result["currency"];term=result["continuation"]
    need(nom["nominal_rate"]=="23/250" and nom["nominal_cash"]==["312/5","12168/125"], "nominal translation")
    real_value=F(60)*zero1+F(90)*zero2
    need(nom["real_pv"]==nom["nominal_pv"]==str(real_value)=="6800/49", "real/nominal independent PV")
    for t,(fc,hc,fx) in enumerate(zip([F(105),F(441,4)],cur["home_cash"],cur["home_per_foreign_path"]),1):
        need(F(hc)==fc*F(fx), "currency amount units")
        need(F(hc)/(F(27,25)**t)==2*fc/(F(21,20)**t), "each converted discounted payment")
    need(cur["foreign_pv"]=="200" and cur["home_pv"]==cur["spot_converted_foreign_pv"]=="400", "currency value anchors")
    # Sum 100 geometric terms and bound the exact remaining tail independently.
    q=F(51,55)
    partial=sum((F(400,11)*q**j for j in range(100)),F(0))
    remainder=F(400,11)*q**100/(1-q)
    need(partial+remainder==500 and remainder < F(1,2), "geometric continuation proof and finite-tail bound")
    need(term["terminal_at_horizon"]=="500" and term["value"]=="56900/121", "terminal date and next-cash anchors")
    need(F(term["value"])==F(300,11)+(36+partial+remainder)*F(100,121), "independent finite-plus-tail valuation")
    groups.append({"name":"Nominal/real cancellation, each currency payment and independent geometric continuation tail","status":"pass"})

    # Original exercise benchmarks independent of the lab's runoff calculation.
    ebit=F(240-150-20);interest=F(8);tax=(ebit-interest)/4;ni=ebit-interest-tax
    receipts=F(240+10-18);cfo=receipts-150-interest-tax;fcff=ebit*F(3,4)+20-35-8;fcfe=cfo-35+12
    need([ebit,ebit*F(3,4),ni,receipts,cfo,fcff,fcfe]==list(map(F,[70,"52.5","46.5",232,"58.5","29.5","35.5"])), "exercise2 cash derivation")
    need(95+18==92+F(10)+ni-fcfe and cfo-35==F(47,2), "exercise2 closing accounts/no borrowing")
    f=F(80-18+20-30-5);n=F(80-10-17);c=n+20-5
    need(f==47 and n==53 and c==68 and c-30-8==f-10+(18-17)-8==30, "exercise3 cash tax")
    need(f-10*F(3,4)-8-30==F(3,2), "exercise3 overstated deduction")
    bridge=650+35+25-180-40-30-20
    need(bridge==440 and F(bridge,22)==20, "exercise4 claims and per-share units")
    value=100*zero1+100*zero2;wrong=102*zero1+F("104.04")*zero2
    need(value==F(82000,441) and wrong-value==F(2456,441), "exercise5 mismatch magnitude")
    need(102/F("1.071")+F("104.04")/F("1.071")**2==value, "exercise5 nominal route")
    fx=[3*(F(26,25)/F(11,10))**t for t in (1,2)]
    home=[F(110)*fx[0],F(121)*fx[1]]
    need(fx==[F(156,55),F(8112,3025)] and home==[F(312),F("324.48")], "exercise6 dated currency path")
    need(home[0]/F("1.04")+home[1]/F("1.04")**2==600, "exercise6 home PV")
    tv=F(18)/(F(2,25)-F(1,50));v=F(12)/F("1.08")+(15+tv)/F("1.08")**2
    need(tv==300 and v==F(22775,81), "exercise7 continuation")
    need(F(d["operating_values"][0])-200==F(1,4)*zero2 and F(40)/F(d["operating_values"][1])==F(168,421), "exercise8 extra shield and market weight")
    groups.append({"name":"All eight prompt/solution pairs: algebra audit and exact numerical exercises2–8, with answered retention","status":"pass"})

    failures=[("units",lambda x:x.update(units="USD")),("book balance",lambda x:x["opening"].update(book_equity=9)),
              ("floating input",lambda x:x["periods"][0].update(sales=322.0)),("cash tax loss",lambda x:x["periods"][0].update(sales=100)),
              ("new capex depreciation timing",lambda x:x["periods"][0].update(depreciation=45)),
              ("nonzero runoff tail",lambda x:x["periods"][1].update(closing_receivables=1)),
              ("unfunded shareholder cash",lambda x:x["periods"][0].update(closing_receivables=200)),
              ("currency rate/path mismatch",lambda x:x["currency"].update(home_rate="1/10")),
              ("nonconvergent continuation",lambda x:x["continuation"].update(growth="1/10"))]
    for name,change in failures:
        bad=deepcopy(data);change(bad)
        try:lab.run(bad)
        except ValueError:pass
        else:raise AssertionError("unsupported contract accepted: "+name)
    for field,value in [("fcff","110"),("fcfe","108")]:
        bad=deepcopy(result);bad["runoff"]["periods"][0][field]=value
        try:check_identities(bad)
        except AssertionError:pass
        else:raise AssertionError("missed wrong cash claim: "+field)
    need(F(110)/F("1.0475")+F(105)/F("1.0475")**2 > 200, "double shield creates overvaluation")
    need(F(30)/F("1.10")+F(36)/F("1.10")**2+F(500)/F("1.10")**3 != F(term["value"]), "terminal one-date error is consequential")
    groups.append({"name":"Nine meaningful domain failures and four consequential claim/shield/timing error detections","status":"pass"})

    html=(BOOK/"content/chapters/v08-c02.html").read_text()
    doc=Fragment();doc.feed(html);doc.close()
    need(not doc.stack and doc.h1==0 and len(doc.ids)==len(set(doc.ids)), "balanced unique fragment")
    need(doc.examples==4 and doc.exercises==doc.answers==8, "complete instructional counts")
    need("Teach-back" in html and "Delayed check" in html, "answered teaching structure")
    sources=json.loads((BOOK/"content/reviews/v08-c02-sources.json").read_text())
    source_ids={s["id"] for s in sources}
    need(source_ids==set(doc.sources)=={h.split("#")[1] for h in doc.links if h.startswith("sources.html#")}, "matching inspected source proposals")
    for suffix in ("inputs.json","analysis.py","README.txt"):
        path="v08-c02-"+suffix
        need(path in doc.links and (PROJECT/path).is_file(), "offline asset "+path)
    for link in doc.links:
        if link.startswith("v") and link.endswith(".html"):
            need(any(c["id"]+".html"==link for v in json.loads((BOOK/"content/curriculum.json").read_text())["volumes"] for c in v["chapters"]), "canonical chapter route "+link)
    with tempfile.TemporaryDirectory(prefix="v08-c02-check-") as name:
        tmp=Path(name)
        for filename in ("v08-c02-inputs.json","v08-c02-analysis.py"):
            shutil.copy2(PROJECT/filename,tmp/filename)
        for flags in ([],["-O"]):
            cli=subprocess.run([sys.executable,*flags,str(tmp/"v08-c02-analysis.py")],cwd=tmp.parent,text=True,capture_output=True,check=False)
            need(cli.returncode==0 and not cli.stderr and json.loads(cli.stdout)==result,"portable normal/optimized benchmark")
        bad=deepcopy(data);bad["units"]="wrong";bad_path=tmp/"bad.json";bad_path.write_text(json.dumps(bad))
        cli=subprocess.run([sys.executable,str(tmp/"v08-c02-analysis.py"),str(bad_path)],text=True,capture_output=True,check=False)
        need(cli.returncode==2 and not cli.stdout and "Invalid free-cash-flow contract" in cli.stderr, "failing CLI has no result payload")
    groups.append({"name":"Four worked cases/eight full pairs, flat assets/sources, strict quiet JSON and portable normal/optimized CLI","status":"pass"})
    result={"chapter":"v08-c02","status":"passed","checks":groups,"limitations":["Supplied fictional cash, certainty, taxes and rates; not a real-company value or financing approval.","Manual instructional/source review and coordinator acceptance remain separate; visual QA is not supplied by arithmetic."]}
    json.dumps(result,allow_nan=False)
    return result


if __name__=="__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
