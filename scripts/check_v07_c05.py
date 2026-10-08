#!/usr/bin/env python3
"""Independent exact financial checks for v07-c05; intentionally bounded."""
from fractions import Fraction as Q
from html.parser import HTMLParser
from pathlib import Path
import contextlib
import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects/v07-c05-analysis.py"
INPUT = PROJECT.with_name("v07-c05-inputs.json")
CHAPTER = ROOT / "content/chapters/v07-c05.html"


def need(condition, message):
    if not condition: raise AssertionError(message)


def eq(actual, expected, label):
    need(Q(actual) == Q(expected), f"{label}: {actual} != {expected}")


def fields(obj, expected, label):
    for key, value in expected.items(): eq(obj[key], value, label + "." + key)


def reference(report):
    fields(report["commencement"], {"cash": 120, "owned_carrying": 80, "rou_carrying": 120,
        "note_liability": 100, "lease_liability": 120, "assets": 320, "liabilities": 220,
        "equity": 100, "retained_earnings": 0, "balance_residual": 0}, "commencement")
    fields(report["commencement"]["cash_flows"], {"owner_financing": 100, "gross_note_financing": 102,
        "issue_fee_financing": -2, "owned_asset_investing": -80, "lease_prepayment_financing": 0,
        "noncash_lease_addition": 120}, "initial gross cash and noncash")
    for index, row in enumerate(report["note_schedule"]):
        expected = [(100, 10, 8, -2, 102), (102, Q(51, 5), Q(561, 5), 102, 0)][index]
        fields(row, dict(zip(("opening", "effective_interest", "payment", "liability_reduction", "closing"), expected)), "note")
    for index, row in enumerate(report["lease_schedule"]):
        expected = [(120, 12, 66, 54, 66), (66, Q(33, 5), Q(363, 5), 66, 0)][index]
        fields(row, dict(zip(("opening", "effective_interest", "payment", "liability_reduction", "closing"), expected)), "lease")
    for index, annual in enumerate(report["annual_reports"]):
        values = [(166, 60, 60, 168, 118, 286, 18, 100, -54, 2),
                  (Q(406, 5), 40, 0, 0, Q(606, 5), Q(606, 5), Q(16, 5), Q(427, 5), Q(-851, 5), Q(11, 5))][index]
        cash, owned, rou, debt, equity, assets, profit, cfo, cff, accretion = values
        fields(annual["position"], {"cash": cash, "owned_carrying": owned, "rou_carrying": rou,
            "liabilities": debt, "equity": equity, "assets": assets, "balance_residual": 0}, "annual position")
        eq(annual["income"]["profit"], profit, "profit")
        fields(annual["cash_flow"], {"operating": cfo, "indirect_operating": cfo, "financing": cff,
            "investing": 0, "note_non_cash_accretion": accretion}, "annual cash")
        fields(annual["full_calendar_year_cash_flow"], {"opening_cash": 0 if index == 0 else 166,
            "operating": cfo, "investing": -80 if index == 0 else 0,
            "financing": cff + (200 if index == 0 else 0), "closing_cash": cash}, "full calendar year including commencement")
    covenant = report["annual_reports"][0]["covenant"]
    fields(covenant, {"ratio": Q(84, 59), "headroom": 9}, "covenant")
    need(covenant["compliant"] is True, "base covenant passes")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.links=[]; self.ids=[]
        self.h1=self.worked=self.exercises=self.solutions=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs); classes=attrs.get("class", "").split()
        if tag=="h1": self.h1+=1
        if tag=="aside" and "worked" in classes: self.worked+=1
        if tag=="a": self.links.append(attrs.get("href", ""))
        if "id" in attrs: self.ids.append(attrs["id"])
        if tag=="li":
            if any(t=="ol" and "exercises" in c for t,c in self.stack): self.exercises+=1
            if any(t=="details" and "solutions" in c for t,c in self.stack): self.solutions+=1
        if tag not in ("br", "hr", "img", "meta", "input", "link"): self.stack.append((tag,classes))
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0]==tag, "HTML nesting: "+tag); self.stack.pop()


def check():
    checks=[]; stdout,stderr=io.StringIO(),io.StringIO()
    with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
        spec=importlib.util.spec_from_file_location("c05lab",PROJECT); lab=importlib.util.module_from_spec(spec); spec.loader.exec_module(lab)
        data=lab.load_inputs(INPUT); report=lab.build_report(data)
    need(not stdout.getvalue() and not stderr.getvalue(), "quiet import and API")
    json.dumps(report,allow_nan=False); reference(report)
    # Independent backward discounting, separate from the forward benchmark helper.
    for key, payments, initial in (("note_schedule",[Q(8),Q("112.2")],Q(100)),("lease_schedule",[Q(66),Q("72.6")],Q(120))):
        value=Q(0); backward=[]
        for payment in reversed(payments): value=(value+payment)/Q("1.1"); backward.append(value)
        eq(value,initial,"backward PV")
        for row in report[key]:
            eq(Q(row["opening"])+Q(row["effective_interest"])-Q(row["payment"]),row["closing"],"rollforward")
            eq(row["closing"],row["remaining_payment_pv"],"remaining PV")
        eq(sum(Q(r["effective_interest"]) for r in report[key]),sum(payments)-initial,"lifetime interest")
    checks.append("Independent baseline balances, gross commencement cash/noncash addition, full first-year cash bridge, backward PVs and terminal/lifetime schedules")

    # Manual events are independent of the benchmark's generated journal values.
    events=[{"cash":Q(100),"capital":Q(-100)}, {"cash":Q(102),"note_liability":Q(-102)},
        {"note_liability":Q(2),"cash":Q(-2)}, {"owned_asset_cost":Q(80),"cash":Q(-80)},
        {"rou_asset_cost":Q(120),"lease_liability":Q(-120),"cash":Q(0)}]
    for index,(revenue,ni,li,np,lp) in enumerate([(260,Q(10),Q(12),Q(8),Q(66)),(240,Q("10.2"),Q("6.6"),Q("112.2"),Q("72.6"))]):
        events.extend([{"cash":Q(revenue),"revenue":-Q(revenue)}, {"operating_expense":Q(140),"cash":Q(-140)},
            {"depreciation_expense":Q(20),"owned_accumulated_depreciation":Q(-20)},
            {"depreciation_expense":Q(60),"rou_accumulated_depreciation":Q(-60)},
            {"interest_expense":ni,"note_liability":-ni}, {"note_liability":np,"cash":-np},
            {"interest_expense":li,"lease_liability":-li}, {"lease_liability":lp,"cash":-lp},
            {"revenue":Q(revenue),"retained_earnings":-Q(revenue)},
            {"operating_expense":Q(-140),"retained_earnings":Q(140)},
            {"depreciation_expense":Q(-80),"retained_earnings":Q(80)},
            {"interest_expense":-ni-li,"retained_earnings":ni+li}])
    need(len(events)==len(report["journal"])==29,"journal count")
    balances={key:Q(0) for key in report["postclosing_debit_balances"]}
    for event,actual,cash in zip(events,report["journal"],report["cash_path"]):
        need(set(event)==set(actual["debit_changes"]),"journal accounts"); fields(actual["debit_changes"],event,"journal amount")
        eq(sum(event.values()),0,"independent entry balance")
        for account,amount in event.items(): balances[account]+=amount
        eq(balances["cash"],cash["cash"],"every cash prefix"); eq(sum(balances.values()),0,"trial balance")
    fields(report["postclosing_debit_balances"],balances,"closed balances")
    checks.append("Manual independent posting of 29 commencement/annual/closing entries and every modeled cash prefix")

    for revenue, equity, headroom, passes in [(260,118,9,True),(254,112,0,True),(230,88,-36,False),(141,-1,Q(-339,2),False)]:
        changed=copy.deepcopy(data); changed["cash_revenues"][0]=str(revenue)
        if equity<=0: changed["cash_revenues"][1]="300"  # keep terminal payments funded while isolating covenant domain
        result=lab.build_report(changed)["annual_reports"][0]
        eq(result["position"]["equity"],equity,"covenant equity"); eq(result["covenant"]["headroom"],headroom,"covenant headroom")
        need(result["covenant"]["compliant"] is passes,"covenant branch")
        if equity<=0: need(result["covenant"]["ratio"] is None,"nonpositive equity ratio undefined")
    premium=copy.deepcopy(data); premium["note"].update(annual_coupon="12",face_at_maturity="95.8")
    pr=lab.build_report(premium)
    for row,opening,interest,closing in zip(pr["note_schedule"],[100,98],[10,Q("9.8")],[98,0]):
        fields(row,{"opening":opening,"effective_interest":interest,"closing":closing},"premium")
    eq(pr["annual_reports"][1]["position"]["cash"],Q("81.6"),"premium final cash")
    prepay=copy.deepcopy(data); prepay["lease"].update(commencement_prepayment="55",end_year_payments=["60.5","66.55"])
    pp=lab.build_report(prepay)
    fields(pp["commencement"],{"lease_liability":110,"rou_carrying":165,"cash":65},"prepaid lease")
    for row,interest,closing in zip(pp["lease_schedule"],[11,Q("6.05")],[Q("60.5"),0]):
        fields(row,{"effective_interest":interest,"closing":closing},"prepaid schedule")
    eq(pp["annual_reports"][1]["position"]["cash"],Q("37.75"),"prepaid final cash")
    zero=copy.deepcopy(data); zero["note"].update(gross_proceeds="122.2",effective_annual_rate="0"); zero["lease"]["annual_rate"]="0"
    zr=lab.build_report(zero)
    need(all(Q(r["effective_interest"])==0 for k in ("note_schedule","lease_schedule") for r in zr[k]),"zero rate")
    eq(zr["annual_reports"][1]["position"]["cash"],Q("101.4"),"zero-rate cash")
    checks.append("Covenant pass/equality/breach/nonpositive-equity cases, premium reversal, prepaid lease and coherent zero-rate boundary")

    # Complete exercise and retention targets, calculated without benchmark helpers.
    e1=60*Q(8,100)*Q(1,4); eq(e1,Q("1.2"),"E1 accrual"); eq(60+e1-e1,60,"E1 A=L+E change")
    eq(12/Q("1.1")+Q("107.8")/Q("1.1")**2,100,"E2 premium PV")
    eq(12+Q("107.8")-100,Q("19.8"),"E2 lifetime")
    net=120-Q("7.5"); eq(126/net-1,Q("0.12"),"E3 net yield"); eq(Q(126,120)-1,Q("0.05"),"E3 gross yield")
    eq(126-net,Q("13.5"),"E3 cost"); eq(Q("7.5")+Q("13.5")-(126-net),Q("7.5"),"E3 duplicated fee")
    eq(Q("60.5")/Q("1.1")+Q("66.55")/Q("1.1")**2,110,"E4 PV")
    eq(2*Q("82.5")+11+Q("6.05"),55+Q("60.5")+Q("66.55"),"E4 lifetime cash=expense")
    eq(18+80+22,120,"E5 indirect year1"); eq(Q("3.2")+80+Q("16.8"),100,"E5 indirect year2")
    eq(120-74,46,"E5 cash1"); eq(100-Q("184.8"),Q("-84.8"),"E5 cash2")
    injection=Q(168)/Q("1.5")-88; retirement=168-Q("1.5")*88
    eq(injection,24,"E6 injection"); eq(retirement,36,"E6 retirement")
    eq(256+injection,168+88+injection,"E6 injection balance"); eq(256-retirement,168-retirement+88,"E6 retirement balance")
    cash7=166+20-Q("184.8"); ni7=20-20-60-Q("10.2")-Q("6.6")
    eq(cash7,Q("1.2"),"E7 cash"); eq(ni7,Q("-76.8"),"E7 profit"); eq(10-cash7,Q("8.8"),"E7 funding")
    eq(10+40,(10-cash7)+118+ni7,"E7 refinanced balance")
    eq(Q("112.2")/Q("1.2"),Q("93.5"),"E8 market price"); eq(102-97,5,"E8 book gain")
    eq(166-97+60+60,66+118+5,"E8 balance"); eq(23+80+2-5,100,"E8 indirect CFO")
    eq(Q("112.2")-97,5+Q("10.2"),"E8 unaccrued interest distinction")
    eq(174+60+60,110+66+118,"retention balance"); eq(18+80+10,108,"retention CFO")
    eq(Q("1.5")*118-176,1,"retention ratio headroom is not payment compliance")
    checks.append("All eight solved exercises and delayed missed-coupon case independently recomputed, including classification, repairs and extinguishment")

    invalid=[]
    for path,value in [(("note","effective_annual_rate"),"0.2"),(("note","direct_issue_fee"),"102"),
        (("lease","end_year_payments"),["0","138.6"]),(("lease","annual_rate"),float('inf')),
        (("lease","commencement_prepayment"),"121"),(("owned_asset_life_years",),1),
        (("cash_revenues",),["260","140"]),(("covenant","test_year_number"),3),(("start_year",),True)]:
        changed=copy.deepcopy(data); obj=changed
        for key in path[:-1]:obj=obj[key]
        obj[path[-1]]=value;invalid.append(changed)
    for changed in invalid:
        try:lab.build_report(changed)
        except ValueError:pass
        else:raise AssertionError("meaningful invalid contract accepted")
    with tempfile.TemporaryDirectory() as directory:
        for flags in ([],["-O"]):
            run=subprocess.run([sys.executable,*flags,str(PROJECT)],cwd=directory,capture_output=True,text=True,timeout=10)
            need(run.returncode==0 and not run.stderr and json.loads(run.stdout)==report,"portable normal/optimized CLI")
        bad=Path(directory)/"bad.json";bad.write_text(json.dumps(invalid[0]),encoding="utf-8")
        run=subprocess.run([sys.executable,"-O",str(PROJECT),str(bad)],cwd=directory,capture_output=True,text=True,timeout=10)
        need(run.returncode==2 and not run.stderr and json.loads(run.stdout)["status"]=="invalid_input","inconsistent PV rejected under optimization")
    mutations=[("commencement","cash","122"),("commencement","lease_liability","0")]
    for section,key,value in mutations:
        broken=copy.deepcopy(report);broken[section][key]=value
        try:reference(broken)
        except AssertionError:pass
        else:raise AssertionError("independent reference missed commencement mutation")
    broken=copy.deepcopy(report);broken["annual_reports"][0]["cash_flow"]["operating"]="98"
    try:reference(broken)
    except AssertionError:pass
    else:raise AssertionError("independent reference missed coupon/expense mutation")
    checks.append("Nine consequential invalid contract/funding cases and three report mutations caught; quiet API and portable normal/-O CLI verified")

    text=CHAPTER.read_text(encoding="utf-8");p=Fragment();p.feed(text)
    need(not p.stack and p.h1==0 and p.worked==3 and p.exercises==p.solutions==8,"fragment structure and complete solutions")
    need(len(p.ids)==len(set(p.ids)),"unique ids")
    for name in (PROJECT.name,INPUT.name,"v07-c05-README.txt"):
        need(name in p.links and PROJECT.with_name(name).exists(),"flat artifact "+name)
    sources=json.loads((ROOT/"content/reviews/v07-c05-sources.json").read_text())
    need(len(sources)==5 and all(set(s)=={"id","title","url","use","checked","verification"} for s in sources),"source proposal schema")
    need({"sources.html#"+s["id"] for s in sources}<=set(p.links),"source routes")
    need({"v07-c04.html","v07-c02.html","v01-c05.html","curriculum.html#v07"}<=set(p.links),"taught prerequisite and extension routes")
    need("Delayed-check answer" in text and "Teach-back guide" in text,"answered self-study prompts")
    checks.append("Three worked cases, eight matching solutions, answered teach-back/retention and all owned artifact/source routes checked structurally")
    return {"status":"passed","checks":checks,"counts":{"journals":29,"liability_schedules":2,"covenant_cases":4,
        "other_financial_boundary_cases":3,"invalid_contracts":len(invalid),"report_mutations_caught":3,"exercises":8,"worked_examples":3},
        "limitations":["Bounded author numerical/structural audit, not documentary assurance or current standards-compliance certification.",
            "Annual cash order and recognition/classification assumptions are supplied; fine-date liquidity and remedies need actual contracts.",
            "Exact rational amounts omit actual currency rounding policy, options, taxes, FX and lease/debt remeasurement.",
            "Visual/mobile/print UI QA remains pending; no visual claim."]}


if __name__=="__main__":
    print(json.dumps(check(),indent=2,sort_keys=True,allow_nan=False))
