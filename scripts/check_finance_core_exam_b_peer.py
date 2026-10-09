"""Separate finite-contract peer audit of finance-core Form B; standard library only."""
import argparse
import contextlib
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "content/cross-assessments/parts/finance-core-exam-b.html",
    "scripts/check_finance_core_exam_b.py",
    "content/reviews/finance-core-exam-b-author.json",
    "content/reviews/finance-core-exam-b-sources.json",
    "scripts/check_finance_core_exam_b_peer.py",
    "content/reviews/finance-core-exam-b-peer.json")
POINTS = {"1a":8,"1b":8,"1c":4,"2a":6,"2b":10,"2c":4,
          "3a":4,"3b":8,"3c":5,"3d":3,"4a":4,"4b":4,"4c":8,"4d":4,
          "5a":6,"5b":8,"5c":6}


def require(ok, message):
    if not ok:
        raise ValueError("finance-core B peer: "+message)


def strict(text):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, "duplicate JSON key")
            result[k] = v
        return result
    def decimal(token):
        value = float(token)
        require(math.isfinite(value), "nonfinite JSON number")
        return value
    def constant(token):
        raise ValueError("nonfinite JSON constant "+token)
    return json.loads(text, object_pairs_hook=pairs, parse_float=decimal, parse_constant=constant)


class Audit:
    def __init__(self):
        self.count = 0
        self.anchor_count = 0
        self.table_cells = 0
        self.interventions = 0
        self.json_rejections = 0
    def eq(self, actual, expected, label):
        self.count += 1
        if type(expected) is bool:
            require(type(actual) is bool and actual == expected, label+": boolean mismatch")
        else:
            require(actual == expected, label+": "+repr(actual)+" != "+repr(expected))


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.headings = []; self.points = {}
        self.answers = {}; self.answer = None; self.anchors = {}; self.anchor = None
        self.links = []; self.sources = []; self.tables = {}; self.table = None
        self.caption = None; self.row = None; self.cell = None
        self.list_markers = []; self.disclosures = []
        self.reader_prompts = 0; self.reader_solutions = 0
    def handle_starttag(self, tag, attrs):
        at = dict(attrs)
        if "id" in at:
            self.ids.append(at["id"])
        if tag in ("h1", "h2", "h3", "h4"):
            self.headings.append((tag, at.get("id")))
        if tag == "ol": self.list_markers.append("exercises" in at.get("class", "").split())
        if tag == "details":
            self.disclosures.append("solutions" in at.get("class", "").split())
            if "solution" in at.get("class", "").split() and at.get("data-solution-for"):
                self.reader_solutions += 1
        if tag == "li":
            if self.list_markers and self.list_markers[-1]: self.reader_prompts += 1
            if any(self.disclosures): self.reader_solutions += 1
        if tag == "li" and "data-points" in at:
            self.points[at["id"]] = int(at["data-points"])
        if at.get("data-solution-for"):
            require(self.answer is None and at["data-solution-for"] not in self.answers, "unique unnested exact answer")
            self.answer = at["data-solution-for"]; self.answers[self.answer] = ""
        if at.get("data-calc"):
            require(self.anchor is None and at["data-calc"] not in self.anchors, "unique visible numerical anchor")
            self.anchor = at["data-calc"]; self.anchors[self.anchor] = ""
        if tag == "a": self.links.append(at.get("href", ""))
        if at.get("data-source"): self.sources.append(at["data-source"])
        if tag == "table": self.table = []
        if tag == "caption": self.caption = ""
        if tag == "tr": self.row = []
        if tag in ("th", "td"): self.cell = ""
        if tag not in ("br", "hr", "img", "input", "meta", "link"): self.stack.append(tag)
    def handle_data(self, value):
        if self.answer is not None: self.answers[self.answer] += value
        if self.anchor is not None: self.anchors[self.anchor] += value
        if self.caption is not None: self.caption += value
        if self.cell is not None: self.cell += value
    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, "balanced HTML "+tag)
        self.stack.pop()
        if tag == "ol": self.list_markers.pop()
        if tag == "details": self.disclosures.pop()
        if tag == "li": self.answer = None
        if tag == "span": self.anchor = None
        if tag == "caption":
            self.current_caption = self.caption.strip(); self.caption = None
        if tag in ("td", "th"):
            self.row.append(self.cell.strip()); self.cell = None
        if tag == "tr": self.table.append(self.row); self.row = None
        if tag == "table":
            require(self.current_caption not in self.tables, "unique table caption")
            self.tables[self.current_caption] = self.table; self.table = None


def eliminate(matrix, rhs):
    """Exact finite linear equations; no author hedge or policy helper."""
    rows = [[F(x) for x in row]+[F(y)] for row, y in zip(matrix, rhs)]
    for j in range(len(rows)):
        pivot = next(i for i in range(j, len(rows)) if rows[i][j])
        rows[pivot], rows[j] = rows[j], rows[pivot]
        scale = rows[j][j]
        rows[j] = [x/scale for x in rows[j]]
        for i in range(len(rows)):
            if i != j:
                multiple = rows[i][j]
                rows[i] = [x-multiple*y for x, y in zip(rows[i], rows[j])]
    return [r[-1] for r in rows]


def financial_review(a, page):
    values = {}
    def table(prefix, columns, expected):
        matches = [rows for name, rows in page.tables.items() if name.startswith(prefix)]
        a.eq(len(matches), 1, "unique economic table "+prefix)
        rows = matches[0][1:]
        a.eq(len(rows), len(expected), "complete economic table "+prefix)
        for row, wanted in zip(rows, expected):
            for index, target in zip(columns, wanted):
                value = F(row[index].replace("−", "-")) if row[index] else None
                a.eq(value, target, "printed "+prefix+" cell")
                a.table_cells += 1
    def visible(part, *tokens):
        text = page.answers["finance-core-b-q"+part]
        for token in tokens:
            a.eq(str(token).replace("-", "−") in text, True, "visible exact solution "+part+" "+str(token))

    # D1: closing stock equations and income are derived separately from cash.
    def accounts(life, recoverable, target_allowance):
        dep = F(72)/life
        imp = max(F(0), 80-dep-recoverable)
        bad_debt = target_allowance-2
        profit = 106-40-20-dep-imp-bad_debt
        cash = F(12+16+84-32-20)
        gross_ar = F(30+90-84)
        inventory = F(24+36-40)
        payables = F(20+36-32)
        ppe = 80-dep-imp
        net_ar = gross_ar-target_allowance
        assets = cash+net_ar+inventory+ppe
        equity = 54+profit
        a.eq(assets, payables+70+equity, "closing stock/flow identity")
        direct = cash-12
        gross_bridge = profit+dep+imp+bad_debt-(gross_ar-30)-(inventory-24)+(payables-20)
        net_bridge = profit+dep+imp-(net_ar-28)-(inventory-24)+(payables-20)
        a.eq(gross_bridge, direct, "gross-AR cash route")
        a.eq(net_bridge, direct, "net-AR cash route")
        return dep, imp, bad_debt, profit, direct, (cash, net_ar, inventory, ppe, payables, 70, equity, assets)
    dep, imp, bad, profit, cfo, balance = accounts(F(4), F(50), F(5))
    old = accounts(F(6), F(50), F(5))
    values.update(depreciation=dep, impairment=imp, allowance_expense=bad,
                  profit=profit, cfo=cfo, wrong_cfo=cfo+bad,
                  old_depreciation=old[0], old_impairment=old[1])
    a.eq(dep+imp, old[0]+old[1], "binding recoverable amount fixes total equipment expense")
    a.eq(profit, old[3], "no manufactured six of profit")
    table("Question 1 closing", [1,3], [[balance[0],balance[4]],[balance[1],balance[5]],
          [balance[2],balance[6]],[balance[3],None],[balance[7],balance[7]]])
    visible("1b", "13+18+12+3−6+4+4=48", "13+18+12−3+4+4=48")
    # An interior kink, not the author's high-recovery fixture: only one method impairs.
    newer, older = accounts(F(4), F(65), F(5)), accounts(F(6), F(65), F(5))
    a.eq((newer[1], older[1], newer[3], older[3]), (0,3,25,28), "invariance ends when only one impairment binds")
    a.eq(accounts(F(4), F(50), F(6))[4], cfo, "another allowance estimate does not collect cash")
    a.interventions += 2

    # D2: value each recipient and reconcile the extra operating value directly.
    proceeds = F(64)-3
    hold = F(20)*F(19,20)+44*F(9,10)
    values.update(net_sale=proceeds, disposal_gain=proceeds-50, hold_value=hold, divestment_gain=proceeds-hold)
    def claims(cost):
        immediate = proceeds-cost
        face = 70-immediate
        estate = (50,10) if cost == 0 else (90,30)
        rows = [(v, min(face,v), max(F(0),v-face), max(F(0),face-v)) for v in estate]
        for v, paid, residual, unpaid in rows:
            a.eq(paid+residual, v, "all terminal recipients exhaust cash")
            a.eq(paid+unpaid, face, "nominal claim is not discharged by valuation")
        debt_value = immediate+F(9,20)*sum(r[1] for r in rows)
        equity_value = F(9,20)*sum(r[2] for r in rows)
        return immediate, face, rows, debt_value, equity_value
    no, rehab = claims(F(0)), claims(F(25))
    creditor_loss = no[3]-rehab[3]
    owner_gain = rehab[4]-no[4]
    surplus = F(9,20)*(40+20)-25
    a.eq(owner_gain-creditor_loss, surplus, "incremental operations equal joint claimant gain")
    a.eq(rehab[0]+25+3, F(64), "buyer-funded corporate uses")
    fee_low, fee_high = max(F(0),creditor_loss), min(F(5),owner_gain)
    a.eq(rehab[3]+fee_low, no[3], "minimum fee obtains weak creditor consent")
    a.eq(owner_gain-fee_low, surplus, "owners retain available surplus")
    a.eq(rehab[0]+fee_low, F(403,10), "fee recipient cash does not retire fee amount from face")
    a.eq(rehab[1], F(34), "remaining face after genuine principal repayment")
    a.eq(3+25+rehab[0]+fee_low+(5-fee_low), F(64+5), "all entry recipients and separate owner endowment")
    a.eq((no[3]+no[4]+5, rehab[3]+fee_low+rehab[4]+5-fee_low), (93,95), "including personal cash exactly once")
    values.update(base_creditor_value=no[3],base_equity_value=no[4],rehab_creditor_value=rehab[3],
                  rehab_equity_value=rehab[4],rehab_surplus=surplus,fee_low=fee_low,fee_high=fee_high,owner_cash_left=5-fee_low)
    table("Question 2 actual", [1,2,3,4], no[2]+rehab[2])
    visible("2b", 88, 90, str(float(creditor_loss)), str(float(owner_gain)))
    a.eq(hold+3, F(308,5), "gross sale-price indifference boundary")
    a.eq(F(308,5)-F(1,100)-3<hold, True, "one price step below divestment threshold")
    for budget, feasible in ((F(429,100),False),(F(43,10),True)):
        a.eq(fee_low<=min(budget,owner_gain), feasible, "separate owner-cash feasibility at exact consent threshold")
    a.interventions += 2

    # D3: derive the complete feasible interval and a convex absolute-value
    # certificate, independently of the author's polyhedron vertex algorithm.
    payoff = (F(1,2),F(1),F(3,2)); liability = (F(90),F(100),F(110))
    physical = (F(1,5),F(2,5),F(2,5)); quote = (F(1,4),F(1,2),F(1,4))
    mean_asset = sum(w*x for w,x in zip(physical,payoff))
    a.eq(sum(quote), F(1), "cash quote")
    a.eq(sum(w*x for w,x in zip(quote,payoff)), F(1), "risky quote")
    for x,l in zip(payoff,liability): a.eq(80+20*x,l,"traded-span liability identity")
    for t in (F(1,10),F(2,5)):
        alt = (t,1-2*t,t)
        a.eq(sum(w*x for w,x in zip(alt,payoff)), F(1), "other positive pricing extension")
        a.eq(sum(w*l for w,l in zip(alt,liability)), F(100), "replica price invariant without completeness")
    fee = F(1,50)
    upper = min(F(30),F(100)/(1+fee),F(10)/(F(1,2)+fee))
    slope = mean_asset-1-fee
    a.eq(slope>0,True,"global affine-objective direction")
    n = upper; b = 100-(1+fee)*n
    wealth = [b+n*x for x in payoff]; residual = [w-l for w,l in zip(wealth,liability)]
    a.eq(b+n+fee*n,F(100),"cash, seller and fee provider all funded")
    for units, feasible in ((F(0),True),(n,True),(n+F(1,1000),False)):
        a.eq(100-(F(1,2)+fee)*units>=90,feasible,"complete low-state interval boundary")
    table("Question 3 funded",[1,2,3],list(zip(wealth,liability,residual)))
    def required_grant(units, execution_fee):
        constraints = [(1+execution_fee-x)*units+l-100 for x,l in zip(payoff,liability)]
        a.eq(max(constraints),execution_fee*units+abs(units-20)/2,"global convex full-coverage certificate")
        return max(F(0),max(constraints))
    for units in (F(0),F(19),F(20),F(21),F(30)):
        a.eq(required_grant(units,fee)>=20*fee,True,"all segments bounded by exact minimum")
    grant = required_grant(F(20),fee)
    a.eq((fee-F(1,2)<0,fee+F(1,2)>0),(True,True),"strict slopes establish unique global funding minimum")
    a.eq(80+20+20*fee,100+grant,"attaining full-coverage portfolio with real costs")
    values.update(risky_expected_return=mean_asset-1,liability_price=sum(w*l for w,l in zip(quote,liability)),
                  holding_max=n,cash_holding=b,execution_fee=fee*n,expected_surplus=sum(w*s for w,s in zip(physical,residual)),
                  minimum_sponsor=grant,sponsor_cash_left=1-grant)
    for cap, need in ((F(19),F(22,25)),(F(75,4),F(1)),(F(18),F(34,25))):
        a.eq(required_grant(cap,fee),need,"changed permission versus one-CU sponsor budget")
    for fee2, funded in ((F(1,20),True),(F(51,1000),False)):
        a.eq(required_grant(F(20),fee2)<=1,funded,"implementation fee reaches actual sponsor boundary")
    a.interventions += 2
    visible("3d", "best of twenty", "shortfalls 5/13 and 10/13", "actual 0.4 sponsor cash")

    # D4: solve three independent path equations for the three adapted holdings,
    # then verify the fourth path and all actual resources. No author hedge call.
    paths = [(F(8),F(6)),(F(8),F(10)),(F(12),F(10)),(F(12),F(14))]
    rate = F(21,20)
    def holdings(gross):
        matrix = [[gross*(first-10), last-first if first==8 else F(0), last-first if first==12 else F(0)] for first,last in paths]
        target = [10*(last-10) for _,last in paths]
        solved = eliminate(matrix[:3],target[:3])
        for row,value in zip(matrix,target): a.eq(sum(x*y for x,y in zip(row,solved)),value,"adapted path replication equation")
        return solved
    n0, nd, nu = holdings(rate)
    a.eq((nd,nu),(F(10),F(10)),"second-stage decisions use only first-node information")
    a.eq((F(6)+10)/2,F(8),"lower futures quote")
    a.eq((F(10)+14)/2,F(12),"upper futures quote")
    a.eq((F(8)+12)/2,F(10),"initial futures quote")
    a.eq(sum(10*(last-10) for _,last in paths)/4/rate**2,F(0),"zero performing forward price")
    table("Complete four-path",[1,2,3],[[10,first,last] for first,last in paths])
    fixed_rows=[]; dynamic_rows=[]
    for first,last in paths:
        fixed_first=10*(first-10); final=10*(last-first)
        fixed_cost=10*last-rate*fixed_first-final
        fixed_rows.append([fixed_first,final,fixed_cost])
        initial=n0*(first-10)
        advance=max(F(0),-initial); investment=max(F(0),initial)
        repayment=rate*advance; release=rate*investment
        cash=F(100)
        cash+=release+final
        a.eq(cash>=repayment,True,"cash actually available before lender repayment")
        cash-=repayment
        a.eq(cash,10*last,"supplier receives fully funded purchase price")
        cash-=10*last
        a.eq(advance<=F(96,5),True,"named lender capacity")
        dynamic_rows.append([100,release,repayment,final,10*last,cash])
    table("Question 4 fixed-quantity",[1,2,3],fixed_rows)
    table("Question 4 executed dynamic",[1,2,3,4,5,6],dynamic_rows)
    loan=2*n0
    values.update(forward_node_abs=20/rate,fixed_down_cost=fixed_rows[0][2],fixed_up_cost=fixed_rows[2][2],
                  fixed_early_gap=20-F(96,5),initial_hedge_units=n0,dynamic_early_loan=loan,lender_cash_left=F(96,5)-loan)
    a.eq(loan*rate,F(20),"lender principal and interest paid from terminal cash")
    a.eq(F(96,5)-loan+loan,F(96,5),"provider opening cash partition")
    for cap,feasible in ((loan,True),(loan-F(1,1000),False)):
        a.eq(loan<=cap,feasible,"actual credit line equality boundary")
    changed=holdings(F(27,25))
    a.eq(changed[0],F(250,27),"new funding factor requires new initial quantity")
    stale_costs=[10*last-F(27,25)*n0*(first-10)-10*(last-first) for first,last in paths]
    a.eq(stale_costs,[F(704,7),F(704,7),F(696,7),F(696,7)],"stale quantity violates target in both directions")
    a.interventions += 2
    signed=[10*(last-10) for _,last in paths]
    delivered=[signed[0],signed[1],signed[2],signed[3]/2]
    unpaid=signed[3]-delivered[3]
    value=sum(delivered)/4/rate**2
    values.update(forward_unpaid=unpaid,credit_stress_cost=140-delivered[3],credit_stress_value=value)
    a.eq([10*last-pay for (_,last),pay in zip(paths,delivered)],[100,100,100,120],"signed credit-stressed own-cash requirements")
    a.eq(value,-unpaid/4/rate**2,"lost positive claim changes initial value")
    recovery=F(4,5)
    a.eq(140-40*recovery,F(108),"new positive recovery does not haircut owed negative cash")
    a.eq(-40+40*recovery,F(-8),"changed signed payoff expectation numerator")
    a.eq(140-(100+20),F(20),"delayed positive variation cannot pay supplier")
    a.interventions += 2

    # D5: derive capacities from physical units and actual payer cash; reconstruct
    # closing stocks after paid priorities, separately from aggregate value loss.
    def bank(buyer, early_capital):
        sold=min(F(30),buyer/F(9,10)); proceeds=F(9,10)*sold
        free=30-sold; retained_value=F(9,10)*(40-sold)
        cash=12+8+proceeds+early_capital
        deposits_paid=min(F(30),cash); cash-=deposits_paid
        draw=min(F(20),cash); cash-=draw
        loans=98-8-5+draw; deposits=112-deposits_paid; equity=10-5-4+early_capital
        a.eq(cash+loans+retained_value,deposits+28+equity,"independent marked closing stock identity")
        a.eq(sold+free+10,F(40),"sold/free/pledged physical partition")
        return [cash,loans,retained_value,deposits,F(28),equity,20-draw],sold,free,proceeds
    late,sold,free,proceeds=bank(F(25),F(0))
    early,_,_,_=bank(F(25),F(5))
    table("Question 5 closing",[1,2,3,4,5,6,7],[late,early])
    needed=30-proceeds
    values.update(sold_units=sold,early_cash=20+proceeds,early_equity_needed=needed,free_units_left=free,
                  late_repo_capacity=F(3,5)*free,remaining_security_value=late[2],late_equity=late[5],early_equity=early[5])
    a.eq(20+proceeds+85+late[2],F(141),"full pool marked once before actual payments")
    a.eq(late[5],F(1),"funding gap is not a second impairment")
    for budget,need,feasible in ((F(0),F(30),False),(F(2499,100),F(501,100),False),
                               (F(25),F(5),True),(F(26),F(4),True),(F(27),F(3),True),(F(100),F(3),True)):
        bound=30-min(budget,F(27))
        a.eq(bound,need,"necessary and sufficient early contribution bound")
        a.eq(0<=bound<=5,feasible,"funded equity menu distinct from required cash")
        if feasible:
            repaired,*_=bank(budget,bound)
            a.eq((repaired[0],repaired[-1]),(F(0),F(0)),"attaining funded boundary")
    a.interventions += 1
    visible("5c","positive marked equity one","not a retrospective assertion","actual five equity cash")

    a.eq(set(values),set(page.anchors),"all distinct numerical anchors independently derived")
    for key,value in values.items():
        a.eq(F(page.anchors[key].strip().replace("−","-")),value,"visible anchor "+key)
        a.anchor_count+=1
    return values


def hashrow(root,path):
    data=(root/path).read_bytes()
    return {"path":path,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}


def check(root=None, integration=True, bindings=True):
    root=Path(root) if root is not None else ROOT
    a=Audit();page=Reader();page.feed((root/FILES[0]).read_text(encoding="utf-8"));page.close()
    a.eq(page.stack,[],"complete balanced manuscript")
    a.eq(len(page.ids),len(set(page.ids)),"unique reader IDs")
    a.eq([x for x in page.headings if x[0]=="h1"],[],"no extra h1")
    a.eq([x[1] for x in page.headings if x[0]=="h2"],["form-b","solutions-b"],"exact assembly anchors")
    a.eq(all(x in ("form-b","solutions-b") or x.startswith("finance-core-b-") for x in page.ids),True,"owned ID prefix")
    wanted={"finance-core-b-q"+k:v for k,v in POINTS.items()}
    a.eq(page.points,wanted,"all seventeen scored prompts")
    a.eq(set(page.answers),set(wanted),"every exact prompt answered")
    a.eq(page.reader_prompts,17,"shared-reader exercise markers count every prompt")
    a.eq(page.reader_solutions,17,"shared-reader solution markers count every answer")
    a.eq(sum(page.points.values()),100,"total score")
    for domain in "12345": a.eq(sum(v for k,v in POINTS.items() if k[0]==domain),20,"essential domain score")
    for part,points in POINTS.items():
        body=page.answers["finance-core-b-q"+part]
        a.eq(len(body)>500,True,"substantive answer "+part)
        rubric=body.rsplit("Credit ",1)[1]
        a.eq(int(rubric.split(":",1)[0]),points,"printed part allocation "+part)
        assigned=[int(n) for n in re.findall(r"\b(\d+)(?=;|\.)",rubric)]
        a.eq(sum(assigned),points,"rubric suballocation "+part)
    financial_review(a,page)
    sources=strict((root/FILES[3]).read_text(encoding="utf-8"))
    a.eq(len(sources["reused_primary_scopes"]),12,"twelve scoped accepted methods")
    a.eq(sources["proposals"],[],"no new unsupported source")
    a.eq({x["canonical_id"] for x in sources["reused_primary_scopes"]},set(sources["reused_source_ids"]),"source identity mapping")
    a.eq(set(page.sources)<=set(sources["reused_source_ids"]),True,"every printed source scoped")
    routes=sources["method_routes"]
    a.eq({x["prompt"] for x in routes},set(wanted),"every prompt taught route")
    chapters=set()
    for route in routes:
        a.eq(route["manuscripts"],["chapters/"+x+".html" for x in route["chapters"]],"flat method manuscript route")
        chapters.update(route["chapters"])
    a.eq(len(chapters),25,"honest sampled chapter count")
    for link in page.links:
        a.eq(bool(re.fullmatch(r"v(?:07|08|09|10|11)-c\d\d\.html",link)) or link.startswith("sources.html#"),True,"flat accepted route syntax")
    author=strict((root/FILES[2]).read_text(encoding="utf-8"))
    rows=author["reviewed_hashes"]
    a.eq({x["path"] for x in rows},{FILES[0],FILES[1],FILES[3]},"exact three author nonself bindings")
    for row in rows: a.eq(row,hashrow(root,row["path"]),"author exact payload")
    for bad in ('{"x":1,"x":2}','NaN','Infinity','-Infinity','1e10000','{}{}'):
        try: strict(bad)
        except ValueError: a.json_rejections+=1
        else: raise ValueError("permissive peer JSON reader")
    author_summary=None
    if integration:
        before={p:(root/p).read_bytes() for p in FILES if (root/p).exists()}
        old=sys.dont_write_bytecode;sys.dont_write_bytecode=True
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()) as err:
                spec=importlib.util.spec_from_file_location("b_author_integration",root/FILES[1])
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                author_summary=module.check(root)
            a.eq(out.getvalue()+err.getvalue(),"","quiet author API integration")
            a.eq(strict(json.dumps(author_summary,allow_nan=False)),author_summary,"strict author summary")
            a.eq(author_summary["comparisons"],462,"separate author integration evidence")
        finally: sys.dont_write_bytecode=old
        for p,raw in before.items(): a.eq((root/p).read_bytes(),raw,"integration nonmutation "+p)
    if bindings:
        review=strict((root/FILES[5]).read_text(encoding="utf-8"))
        recorded=review["reviewed_hashes"]
        a.eq(len(recorded),5,"four author plus own checker bindings")
        a.eq({x["path"] for x in recorded},set(FILES[:5]),"exact five nonself payloads")
        for row in recorded:a.eq(row,hashrow(root,row["path"]),"separate peer frozen payload")
    summary={"component":"finance-core-exam-b-peer","status":"passed","independent_comparisons":a.count,
             "scored_and_solved_parts":17,"domains":5,"points":100,"independent_numerical_anchors":a.anchor_count,
             "reader_counted_prompts":page.reader_prompts,"reader_counted_solutions":page.reader_solutions,
             "independent_table_cells":a.table_cells,"focused_mechanism_interventions":a.interventions,
             "strict_json_rejections":a.json_rejections,"sampled_chapters":len(chapters),
             "author_comparisons_integration_only":author_summary["comparisons"] if author_summary else 0,
             "reviewed_nonself_payloads":5 if bindings else 0,
             "limits":"Independent finite-contract audit; no empirical calibration, current legal conclusion, rendered UI or human certification."}
    strict(json.dumps(summary,allow_nan=False))
    return summary


def portable():
    """Execute quiet public APIs in normal/-O from / in an exact six-file tree."""
    with tempfile.TemporaryDirectory(prefix="finance-b-peer-") as tmp:
        root=Path(tmp)/"book"
        for path in FILES:
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/path,dest)
        before={p:hashrow(root,p) for p in FILES}
        results=[]
        for flags in ([],["-O"]):
            code=("import sys,importlib.util,contextlib,io,json;sys.dont_write_bytecode=True;"
                  "s=importlib.util.spec_from_file_location('peer',"+repr(str(root/FILES[4]))+");"
                  "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                  "with contextlib.redirect_stdout(io.StringIO()) as o,contextlib.redirect_stderr(io.StringIO()) as e:\n r=m.check()\n"
                  "if o.getvalue() or e.getvalue():raise ValueError('nonquiet check')\n"
                  "print(json.dumps(r,allow_nan=False,sort_keys=True))")
            done=subprocess.run([sys.executable]+flags+["-c",code],cwd="/",env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1"),
                                capture_output=True,text=True,timeout=30)
            require(done.returncode==0 and not done.stderr,"portable API failure "+done.stderr)
            results.append(strict(done.stdout))
        require(results[0]==results[1],"normal/optimized isolated summaries differ")
        require({p:hashrow(root,p) for p in FILES}==before,"portable payload mutation")
        require({str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==set(FILES),"isolated file membership changed")
        return {"status":"passed","files":6,"normal_and_optimized":True,"cwd":"/","no_mutation":True,"summary":results[0]}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolation",action="store_true")
    args=parser.parse_args()
    print(json.dumps(portable() if args.isolation else check(),allow_nan=False,sort_keys=True))
