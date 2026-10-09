"""Separate C02 peer checks. Only candidate run/CLI are called, never helpers.

The independent oracle uses cumulative journal-kind totals and closed cash
budgets. check() is quiet; the command line emits one JSON summary.
"""
import contextlib
import copy
from fractions import Fraction as Q
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/"content/projects/v11-c02-analysis.py"
INPUT=MODEL.with_name("v11-c02-inputs.json")
OUTPUT=MODEL.with_name("v11-c02-output.json")
RECORD=ROOT/"content/reviews/v11-c02-peer.json"
AUTHOR_PATHS=["content/chapters/v11-c02.html","content/projects/v11-c02-inputs.json",
              "content/projects/v11-c02-analysis.py","content/projects/v11-c02-output.json",
              "content/projects/v11-c02-manifest.json","content/projects/v11-c02-README.txt",
              "scripts/check_v11_c02.py","content/reviews/v11-c02-author.json",
              "content/reviews/v11-c02-sources.json"]


class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.links=[];self.solutions=[];self.worked=0;self.sources=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if "id" in a:self.ids.append(a["id"])
        if "href" in a:self.links.append(a["href"])
        if "data-solution-for" in a:self.solutions.append(a["data-solution-for"])
        if "worked" in a.get("class","").split():self.worked+=1
        if "data-source" in a:self.sources.add(a["data-source"])


def check(bindings=True):
    count={"comparisons":0,"financial_interventions":0,"invalid_api_rejections":0,
           "cli_valid_runs":0,"cli_rejections":0,"journal_rows_reconstructed":0,
           "cash_rows_reconstructed":0,"bound_author_files":0}
    def need(value,label):
        count["comparisons"]+=1
        if not value:raise ValueError("C02 peer: "+label)
    def eq(got,want,label):
        need(got==want,label+": "+repr(got)+" != "+repr(want))
    def near(got,want,label):
        need(type(got) in (int,float) and math.isfinite(got) and math.isclose(got,float(want),rel_tol=1e-13,abs_tol=6e-12),label)
    def numbers(got,want,label):
        for key,value in want.items():near(got[key],value,label+"."+key)
    def q(value):return Q(str(value))
    quiet=io.StringIO()
    spec=importlib.util.spec_from_file_location("v11_c02_peer_subject",MODEL)
    model=importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(quiet),contextlib.redirect_stderr(quiet):spec.loader.exec_module(model)
    eq(quiet.getvalue(),"","quiet candidate import")
    data=json.loads(INPUT.read_text())

    def call(x):
        before=copy.deepcopy(x);log=io.StringIO()
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):out=model.run(x)
        eq(log.getvalue(),"","quiet public run")
        eq(x,before,"nonmutating public run")
        eq(json.loads(json.dumps(out,allow_nan=False)),out,"finite JSON output")
        return out

    def totals(s):
        net=s["gross_loans"]-s["allowance"]
        assets=sum(s[k] for k in ("cash","free_securities","pledged_securities","property","goodwill"))+net
        debt=sum(s[k] for k in ("deposits","wholesale","other_liabilities"))
        return {"net_loans":net,"assets":assets,"liabilities":debt,"equity":s["equity"],"identity_residual":assets-debt-s["equity"]}

    def ledger(x,out,all_rows=False):
        start={k:q(v) for k,v in x["opening"].items()}
        def accumulated(n):
            # Every balance follows independently from cumulative economic flows.
            t={k:sum((q(e["amount"]) for e in x["journal"][:n] if e["kind"]==k),Q(0)) for k in
               ("originate_deposit","external_payment","principal_collection","cash_interest","deposit_interest",
                "cash_expense","provision","chargeoff","recovery","dividend","allowance_release")}
            s=start.copy()
            s["cash"]+=t["cash_interest"]+t["principal_collection"]+t["recovery"]-t["external_payment"]-t["cash_expense"]-t["dividend"]
            s["gross_loans"]+=t["originate_deposit"]-t["principal_collection"]-t["chargeoff"]
            s["allowance"]+=t["provision"]+t["recovery"]-t["chargeoff"]-t["allowance_release"]
            s["deposits"]+=t["originate_deposit"]+t["deposit_interest"]-t["external_payment"]
            income=t["cash_interest"]+t["allowance_release"]-t["deposit_interest"]-t["cash_expense"]-t["provision"]
            s["equity"]+=income-t["dividend"]
            return s,income,t["dividend"]
        if all_rows:
            numbers(out["opening"],totals(start),"opening totals")
            eq(len(out["journal_states"]),len(x["journal"]),"every journal row")
            for i,row in enumerate(out["journal_states"],1):
                s,_,_=accumulated(i)
                numbers(row["accounts"],s,"prefix journal")
                numbers(row["totals"],totals(s),"journal totals")
                eq(row["id"],x["journal"][i-1]["id"],"journal ID")
                eq(row["kind"],x["journal"][i-1]["kind"],"journal kind")
                eq(totals(s)["identity_residual"],0,"journal conservation")
                count["journal_rows_reconstructed"]+=1
        s,income,dividends=accumulated(len(x["journal"]))
        numbers(out["closing_accounts"],s,"closing stocks")
        numbers(out["closing"],totals(s),"closing totals")
        near(out["net_income"],income,"income is not distributions")
        near(out["dividends"],dividends,"dividends")
        near(out["income_equity_residual"],0,"income-equity bridge")
        return s

    def capital(x,got,s):
        t=totals(s);p=x["instructional_capital"]
        k=s["equity"]-s["goodwill"];u=t["assets"]-s["goodwill"]
        rw=q(p["loan_weight"])*(s["gross_loans"]-s["allowance"])+q(p["security_weight"])*(s["free_securities"]+s["pledged_securities"])+q(p["property_weight"])*s["property"]
        risk=q(p["risk_ratio_floor"]);lev=q(p["leverage_floor"])
        numbers(got,{"adjusted_capital":k,"adjusted_exposure":u,"toy_rwa":rw,
                     "book_equity_to_assets":s["equity"]/t["assets"],"toy_risk_ratio":k/rw,"toy_leverage_ratio":k/u,
                     "minimum_cash_equity_for_ratios":max(0,risk*rw-k,(lev*u-k)/(1-lev)),
                     "minimum_deposit_conversion_for_ratios":max(0,risk*rw-k,lev*u-k)},"capital algebra")
        eq(got["risk_gate"],k-risk*rw>=0,"unrounded risk gate")
        eq(got["leverage_gate"],k-lev*u>=0,"unrounded leverage gate")

    def funding(x,out,s):
        repaired=s.copy();r=x["repair"];amount=q(r["amount"])
        adds_cash=r["kind"] in ("cash_equity","unsecured_borrow")
        adds_equity=r["kind"] in ("cash_equity","deposit_conversion")
        repaired["cash"]+=amount*adds_cash;repaired["equity"]+=amount*adds_equity
        repaired["deposits"]-=amount*(r["kind"]=="deposit_conversion")
        repaired["wholesale"]+=amount*(r["kind"]=="unsecured_borrow")
        numbers(out["post_repair_accounts"],repaired,"repair double entries")
        capital(x,out["base_capital"],s);capital(x,out["post_repair_capital"],repaired)
        marks=x["valuation"]
        ea=repaired["cash"]+sum(q(marks[k]) for k in ("free_security_value","pledged_security_value","loan_value","property_value","goodwill_value"))
        ee=ea-totals(repaired)["liabilities"]
        numbers(out["valuation"],{"book_equity":repaired["equity"],"economic_assets":ea,"economic_equity":ee,
                                  "severe_economic_equity":ee-q(marks["loan_value"])+q(marks["severe_loan_value"]),
                                  "book_to_economic_equity_change":ee-repaired["equity"]},"complete economic values")
        liq=x["liquidity"];advance=q(marks["free_security_value"])*(1-q(liq["haircut"]));repay=advance*q(liq["secured_gross"])
        near(out["liquidity"]["secured_capacity"],advance,"free collateral advance")
        near(out["liquidity"]["secured_interest"],repay-advance,"interest separate from principal")
        heads=[];rows=out["liquidity"]["forecast"]
        eq(len(rows),len(liq["events"]),"all cash cutoffs")
        for i,row in enumerate(rows):
            t=liq["events"][i]["cutoff"]
            received=sum(q(e["loan_principal_in"]) for e in liq["events"][:i+1])
            paid={k:sum(q(e[k]) for e in liq["events"][:i+1]) for k in ("deposits_out","wholesale_out","other_out")}
            drawn=t>=liq["draw_cutoff"];repaid=t>=liq["repay_cutoff"]
            cash=repaired["cash"]+received-sum(paid.values())+advance*drawn-repay*repaid
            head=cash-q(liq["restricted_cash"]);heads.append(head)
            expected=repaired.copy()
            expected.update(cash=cash,gross_loans=repaired["gross_loans"]-received,
                            deposits=repaired["deposits"]-paid["deposits_out"],
                            wholesale=repaired["wholesale"]-paid["wholesale_out"]+advance*(drawn-repaid),
                            other_liabilities=repaired["other_liabilities"]-paid["other_out"],
                            equity=repaired["equity"]-(repay-advance)*repaid)
            locked=drawn and not repaid
            expected["free_securities"]=repaired["free_securities"]*(not locked)
            expected["pledged_securities"]=repaired["pledged_securities"]+repaired["free_securities"]*locked
            numbers(row["projected_accounts_if_all_payments_made"],expected,"projected stocks")
            numbers(row["totals"],totals(expected),"projected totals")
            numbers(row,{"secured_draw":advance if t==liq["draw_cutoff"] else 0,
                         "secured_repayment":repay if t==liq["repay_cutoff"] else 0,
                         "cash_after_assumed_payments":cash,"unrestricted_headroom":head,"payment_shortfall":max(0,-head)},"cash budget")
            eq(row["executable_without_added_funding_through_here"],min(heads)>=0,"failure cannot be cured retrospectively")
            eq(totals(expected)["identity_residual"],0,"projected accounting conservation")
            count["cash_rows_reconstructed"]+=1
        failed=next((i for i,h in enumerate(heads) if h<0),None)
        eq(out["liquidity"]["first_failure_cutoff"],None if failed is None else liq["events"][failed]["cutoff"],"first failing cutoff")
        eq(out["liquidity"]["executable_prefix_cutoffs"],len(heads) if failed is None else failed,"executable prefix")
        eq(out["liquidity"]["feasible_through_horizon"],failed is None,"plan feasibility")
        near(out["liquidity"]["minimum_upfront_external_cash_for_this_fixed_plan"],max(0,-min(heads)),"cash injection certificate")
        return heads

    baseline=call(data);closing=ledger(data,baseline,True);funding(data,baseline,closing)
    eq(baseline,json.loads(OUTPUT.read_text()),"saved output after independent reconstruction")
    numbers(baseline["closing_accounts"],{"cash":Q(69,2),"gross_loans":242,"allowance":5,"deposits":266,"equity":Q(27,2)},"worked ledger anchors")
    eq([r["unrestricted_headroom"] for r in baseline["liquidity"]["forecast"]],[-1.2,5.8,1.712],"worked cash anchors")

    def changed(edit,full=False):
        x=copy.deepcopy(data);edit(x);out=call(x)
        s=ledger(x,out,full);funding(x,out,s)
        count["financial_interventions"]+=1
        return out

    for kind in ("cash_equity","deposit_conversion","unsecured_borrow"):
        out=changed(lambda x,k=kind:x.update(repair={"kind":k,"amount":3.8}))
        eq(out["post_repair_capital"]["risk_gate"],kind!="unsecured_borrow","repair capital contrast")
        eq(out["liquidity"]["feasible_through_horizon"],kind!="deposit_conversion","repair cash contrast")
    for amount in (3.7999999999999,1.2,1.1999999999999):
        out=changed(lambda x,a=amount:x.update(repair={"kind":"cash_equity","amount":a}))
        eq(out["post_repair_capital"]["risk_gate"],False,"strict capital boundary despite rounded display")
        eq(out["liquidity"]["feasible_through_horizon"],amount>=1.2,"exact cash gate near rounded zero")
    def later_failure(x):
        x["repair"]={"kind":"cash_equity","amount":3.8};x["liquidity"]["secured_gross"]=2
    out=changed(later_failure)
    eq(out["liquidity"]["first_failure_cutoff"],3,"secured repayment can create later first failure")
    near(out["liquidity"]["minimum_upfront_external_cash_for_this_fixed_plan"],23,"later gap includes principal repayment")
    def move_receipt(x):
        x["liquidity"]["events"][0]["loan_principal_in"]=22;x["liquidity"]["events"][1]["loan_principal_in"]=0
    out=changed(move_receipt)
    eq([r["unrestricted_headroom"] for r in out["liquidity"]["forecast"]],[10.8,5.8,1.712],"exercise5 contractual receipt timing")
    for kind in ("allowance_release","recovery","chargeoff"):
        out=changed(lambda x,k=kind:x["journal"].append({"id":"peer-"+k,"kind":k,"amount":1}))
        eq(out["net_income"],-3.5 if kind=="allowance_release" else -4.5,"separate allowance income")
    out=changed(lambda x:x["instructional_capital"].update(loan_weight=.7))
    near(out["base_capital"]["toy_rwa"],Q(1839,10),"exercise4 reweighting")
    eq(out["liquidity"],baseline["liquidity"],"weight changes no cash contract")
    out=changed(lambda x:x["liquidity"].update(secured_gross=.5))
    near(out["liquidity"]["secured_interest"],Q(-72,5),"negative financing-rate boundary")
    out=changed(lambda x:x["valuation"].update(loan_value=229.5))
    near(out["valuation"]["economic_equity"],0,"exercise3 economic threshold")
    eq(out["liquidity"],baseline["liquidity"],"a loan mark is not a cash receipt")

    # Exact exercise calculations outside the model's implemented secured plan.
    eq((Q(5)-6+8-1,(70-8)-5),(Q(6),Q(57)),"exercise2 allowance and net assets")
    eq((Q(69,2)-5,242+12,266+12-5,Q(679,2)+7),(Q(59,2),254,273,Q(693,2)),"exercise1 independent entries")
    eq(1-(Q(70)-30-10)/36,Q(1,6),"exercise5 exact haircut boundary")
    eq(max(Q(0),Q(3,50)*255-Q(23,2),(Q(1,25)*Q(675,2)-Q(23,2))/(1-Q(1,25)),Q(6,5)),Q(19,5),"exercise6 joint injection")
    eq((Q(27,2)-(40-34),Q(3,2)-(36-34)),(Q(15,2),Q(-1,2)),"exercise7 sale valuation bases")
    eq([30+34+10-70,30+34+10+12-70-5,30+34+10+12+25-70-5],[4,11,36],"exercise7 sale cash without extra borrowing")
    eq(Q(69,2)+5+10+Q(4,5)*56-70-(Q(9,2)+5+Q(4,5)*20),Q(-6,5),"exercise8 three distinct cash overstatements")

    def bad(edit,label):
        x=copy.deepcopy(data);edit(x);before=json.dumps(x,sort_keys=True)
        try: model.run(x)
        except ValueError:count["invalid_api_rejections"]+=1
        else:raise ValueError("C02 peer accepted invalid "+label)
        eq(json.dumps(x,sort_keys=True),before,"invalid input preserved")
    for value in (True,"40",float("nan"),float("inf"),-1,1000001):
        bad(lambda x,v=value:x["opening"].update(cash=v),"cash domain")
    for edit,label in [
        (lambda x:x.update(schema_version=True),"schema bool"),
        (lambda x:x["opening"].update(equity=21),"unbalanced opening"),
        (lambda x:x["journal"][7].update(amount=15),"uncovered chargeoff"),
        (lambda x:x["journal"].append({"id":"release","kind":"allowance_release","amount":6}),"negative allowance"),
        (lambda x:x["journal"][0].update(extra=1),"unknown journal key"),
        (lambda x:x["instructional_capital"].update(leverage_floor=1),"unit leverage floor"),
        (lambda x:x["instructional_capital"].update(loan_weight=0,security_weight=0,property_weight=0),"zero ratio denominator"),
        (lambda x:x["liquidity"].update(restricted_cash=35),"restricted stock"),
        (lambda x:x["liquidity"].update(draw_cutoff=3),"funding timing"),
        (lambda x:x["liquidity"]["events"][0].update(loan_principal_in=238),"loan cash inventory"),
        (lambda x:x.update(repair={"kind":"deposit_conversion","amount":212}),"scheduled deposits cannot convert"),
        (lambda x:x["liquidity"]["events"][0].update(other_out=11),"existing other-liability budget")]:bad(edit,label)
    for stock,mark in (("free_securities","free_security_value"),("pledged_securities","pledged_security_value"),("property","property_value"),("goodwill","goodwill_value")):
        def absent(x,s=stock,m=mark):
            x["opening"]["equity"]-=x["opening"][s];x["opening"][s]=0;x["valuation"][m]=1
        bad(absent,"absent asset mark")
    def absent_loans(x):
        x["opening"].update(gross_loans=0,allowance=0,equity=-212)
        x["journal"]=[{"id":"zero","kind":"cash_interest","amount":0}]
        for e in x["liquidity"]["events"]:e["loan_principal_in"]=0
    bad(absent_loans,"absent gross claims")
    def full_allowance(x):
        absent_loans(x);x["opening"].update(gross_loans=240,allowance=240)
    out=changed(full_allowance,True)
    near(out["valuation"]["economic_equity"],13,"surviving fully allowed claims can have value")

    page=Page();page.feed((ROOT/AUTHOR_PATHS[0]).read_text())
    eq(page.worked,3,"three worked cases")
    prompts=["v11-c02-e"+str(i) for i in range(1,9)]
    eq([p for p in page.ids if p in prompts],prompts,"all eight exact prompts")
    eq(page.solutions,prompts,"all eight matching solutions")
    eq(len(page.ids),len(set(page.ids)),"unique IDs")
    for suffix in ("README.txt","inputs.json","analysis.py","output.json","manifest.json"):
        target="v11-c02-"+suffix
        need(target in page.links and "projects/"+target not in page.links,"repaired flat download "+target)
    source=json.loads((ROOT/AUTHOR_PATHS[8]).read_text())
    eq(page.sources,{s["id"] for s in source},"source routes scoped correctly")
    manifest=json.loads((ROOT/AUTHOR_PATHS[4]).read_text())
    eq({r["file"] for r in manifest["files"]},{"v11-c02-"+s for s in ("inputs.json","analysis.py","output.json","README.txt")},"manifest membership")
    for row in manifest["files"]:
        raw=(MODEL.parent/row["file"]).read_bytes();eq((len(raw),hashlib.sha256(raw).hexdigest()),(row["bytes"],row["sha256"]),"manifest identity")
    author=json.loads((ROOT/AUTHOR_PATHS[7]).read_text())
    eq({r["path"] for r in author["reviewed_hashes"]},set(AUTHOR_PATHS)-{AUTHOR_PATHS[7]},"eight author bindings")
    for row in author["reviewed_hashes"]:
        raw=(ROOT/row["path"]).read_bytes();eq((len(raw),hashlib.sha256(raw).hexdigest()),(row["bytes"],row["sha256"]),"author identity")

    with tempfile.TemporaryDirectory(prefix="v11-c02-peer-") as td:
        temp=Path(td);folder=temp/"lab";folder.mkdir()
        subject=folder/MODEL.name;inp=folder/INPUT.name
        subject.write_bytes(MODEL.read_bytes());inp.write_bytes(INPUT.read_bytes())
        aliases=[]
        for protected in (inp,subject):
            sym=temp/(protected.name+".sym");sym.symlink_to(protected)
            hard=temp/(protected.name+".hard");os.link(protected,hard)
            aliases.extend([protected,sym,hard])
        for options in ([],["-O"]):
            prefix=[sys.executable]+options+[str(subject)]
            proc=subprocess.run(prefix,cwd=temp,capture_output=True,text=True,timeout=20)
            eq((proc.returncode,proc.stderr),(0,""),"portable default CLI")
            eq(json.loads(proc.stdout),baseline,"portable default output")
            count["cli_valid_runs"]+=1
            target=temp/"result.json"
            proc=subprocess.run(prefix+[str(inp),"--output",str(target)],cwd=temp,capture_output=True,text=True,timeout=20)
            eq((proc.returncode,proc.stdout,proc.stderr),(0,"",""),"quiet portable output CLI")
            eq(json.loads(target.read_text()),baseline,"portable explicit output")
            count["cli_valid_runs"]+=1
            for target in aliases:
                before=(inp.read_bytes(),subject.read_bytes())
                proc=subprocess.run(prefix+[str(inp),"--output",str(target)],cwd=temp,capture_output=True,text=True,timeout=20)
                need(proc.returncode==2 and not proc.stdout and "overwrite" in proc.stderr,"protected alias rejected")
                eq((inp.read_bytes(),subject.read_bytes()),before,"alias rejection preserves inputs/model")
                count["cli_rejections"]+=1
            for text in ('{"schema_version":1,"schema_version":1}','{"cash":NaN}'," "*200001):
                badfile=temp/"bad.json";badfile.write_text(text)
                target=temp/"unchanged.json";target.write_text("unchanged")
                proc=subprocess.run(prefix+[str(badfile),"--output",str(target)],cwd=temp,capture_output=True,text=True,timeout=20)
                need(proc.returncode==2 and not proc.stdout and bool(proc.stderr),"invalid serialized input rejected")
                eq(target.read_text(),"unchanged","invalid input preserves output")
                count["cli_rejections"]+=1

    if bindings:
        record=json.loads(RECORD.read_text())
        eq(record["status"],"peer-review-passed","peer verdict")
        eq({r["path"] for r in record["reviewed_hashes"]},set(AUTHOR_PATHS),"nine exact peer bindings")
        eq(len(record["reviewed_hashes"]),9,"no duplicate peer binding")
        for row in record["reviewed_hashes"]:
            raw=(ROOT/row["path"]).read_bytes();eq((len(raw),hashlib.sha256(raw).hexdigest()),(row["bytes"],row["sha256"]),"final author freeze identity")
            count["bound_author_files"]+=1
        own=record["peer_checker"]
        raw=Path(__file__).read_bytes()
        eq(own["path"],str(Path(__file__).resolve().relative_to(ROOT)),"peer checker path")
        eq((own["bytes"],own["sha256"]),(len(raw),hashlib.sha256(raw).hexdigest()),"peer checker identity")
    return {"chapter":"v11-c02","status":"passed",**count}


if __name__=="__main__":print(json.dumps(check(),sort_keys=True))
