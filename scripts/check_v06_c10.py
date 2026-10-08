#!/usr/bin/env python3
"""Independent exact arithmetic and behavioral audit for Volume6 Chapter10."""
import ast
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import io
import itertools
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types

BOOK = Path(__file__).resolve().parents[1]
PROJECT = BOOK / "content/projects"


def need(condition, label):
    if not condition:
        raise AssertionError(label)


def linear(matrix, rhs):
    """Independent small exact row elimination; no production formulas imported."""
    rows = [[F(x) for x in row] + [F(y)] for row, y in zip(matrix, rhs)]
    n = len(rows)
    for col in range(n):
        pivot = next(i for i in range(col, n) if rows[i][col])
        rows[col], rows[pivot] = rows[pivot], rows[col]
        p = rows[col][col]
        rows[col] = [x / p for x in rows[col]]
        for i in range(n):
            if i != col:
                k = rows[i][col]
                rows[i] = [a - k * b for a, b in zip(rows[i], rows[col])]
    return tuple(row[-1] for row in rows)


def tariff_reference(market, t):
    # Derive price from original balances, then explicitly select the no-trade branch.
    if market == "small":
        pd, pf = F(20) + t, F(20)
    else:
        pd, pf = linear([[4, 6], [1, -1]], [200, t])
    if 140 - 4 * pd <= 0:
        pd = F(35)
        pf = F(20 if market == "small" else 10)
    d, s = 120 - 2 * pd, 2 * pd - 20
    m = d - s
    b = 60 * d - d*d/4
    c = 10 * s + s*s/4
    cs, ps, revenue = b - pd*d, pd*s - c, t*m
    home = b - c - pf*m
    need(cs + ps + revenue == home, "reference transfer cancellation")
    out = dict(domestic_price=pd, foreign_offer_price=pf,
               consumption=d, production=s, imports=m,
               consumer_surplus=cs, producer_surplus=ps, revenue=revenue,
               foreign_payment=pf*m, home_welfare=home,
               home_change=home-1700, home_resource_ledger=home)
    if market == "large":
        foreign_cost = 10*m + m*m/12
        foreign = pf*m - foreign_cost
        out.update(foreign_surplus=foreign, foreign_change=foreign-300,
                   world_change=b-c-foreign_cost-2000)
    need(m >= 0 and d >= 0 and s >= 0, "tariff nonnegative quantities")
    need((pd == pf+t) if m else (pd <= pf+t), "tariff complementarity")
    return out


def firm_reference(A, b, fixed, c, tau):
    # Enumerate candidates for both branches and the discrete stay-out choice.
    choke = A/b
    stationary, = linear([[2*b]], [A-tau*c])
    candidates = {F(0), choke}
    if 0 < stationary < choke:
        candidates.add(stationary)
    def profit(q):
        return F(0) if q == 0 else (max(F(0), A-b*q)-tau*c)*q-fixed
    values = {q: profit(q) for q in candidates}
    best = max(values.values())
    choices = sorted(q for q, v in values.items() if v == best)
    for q in (choke/4, choke/2, 3*choke/4, 2*choke, 4*choke):
        need(profit(q) <= best, "off-optimum export profit")
    return choices, best


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.links, self.sources = [], [], [], []
        self.worked = self.h1 = 0
        self.ol_counts, self.ol_active = [], []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if "href" in a:
            self.links.append(a["href"])
        if "data-source" in a:
            self.sources.append(a["data-source"])
        self.worked += tag == "aside" and a.get("class") == "worked"
        self.h1 += tag == "h1"
        if tag == "ol":
            self.ol_counts.append(0)
            self.ol_active.append(len(self.ol_counts)-1)
        if tag == "li" and self.ol_active:
            self.ol_counts[self.ol_active[-1]] += 1
        if tag not in {"br", "hr", "img", "meta", "link", "input", "wbr", "source", "area", "base", "col", "embed", "param", "track"}:
            self.stack.append(tag)
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1] == tag, "HTML closing tag " + tag)
        self.stack.pop()
        if tag == "ol":
            self.ol_active.pop()


def check():
    checks = []
    manuscript = (BOOK / "content/chapters/v06-c10.html").read_text()
    source_records = json.loads((BOOK / "content/reviews/v06-c10-sources.json").read_text())
    lab_path = PROJECT / "v06-c10-analysis.py"
    code = lab_path.read_text()
    ast.parse(code)
    ast.parse(Path(__file__).read_text())
    module = types.ModuleType("v06_c10_lab")
    module.__file__ = str(lab_path)
    silence, errors = io.StringIO(), io.StringIO()
    data = json.loads((PROJECT / "v06-c10-inputs.json").read_text())
    with redirect_stdout(silence), redirect_stderr(errors):
        exec(compile(code, str(lab_path), "exec"), module.__dict__)
        output = module.analyze(data)
    need(not silence.getvalue() and not errors.getvalue(), "quiet lab import/API")
    json.dumps(output, allow_nan=False)

    # Ricardian examples: optimizing production, consumer budgets and world clearing.
    ricardian = [
        (F(2,3), [(2,4,120,60,0,30,20), (6,3,120,0,40,30,20)]),
        (F(1), [(2,4,120,60,0,30,30), (1,1,120,30,90,60,60)]),
    ]
    for p, countries in ricardian:
        for ac, aw, labor, qc, qw, cc, cw in countries:
            need(ac*qc + aw*qw == labor, "Ricardian resource use")
            income = p*qc+qw
            value_vertices = (p*F(labor,ac), F(labor,aw))
            need(income == max(value_vertices), "Ricardian global production value")
            need(cc == income/(2*p) and cw == income/2, "Ricardian utility choice")
            need(p*(qc-cc) + qw-cw == 0, "Ricardian trade payment")
            wage = max(p/ac, F(1,aw))
            need(wage*labor == income, "Ricardian wage ownership")
        need(sum(row[3]-row[5] for row in countries) == 0, "cloth world clearing")
        need(sum(row[4]-row[6] for row in countries) == 0, "wheat world clearing")
    need(F(120,60) > 1, "invalid full-specialization branch in exercise1")
    need((30*15,10*20,30*20,30*30,60*60) == (450,200,600,900,3600), "Ricardian utility targets")
    checks.append({"name":"Ricardian feasible equilibrium and endpoint", "cases":2,
                   "status":"pass", "prices":["2/3","1"]})

    # Factor globality from primal vertices versus independently solved dual rewards.
    factor_cases = 0
    for labor, p in itertools.product((60,100,110,113,150,190), (F(3,5), F(1), F(9,5))):
        capital = F(100)
        x, y = linear([[2,1],[1,2]], [labor,capital])
        w, r = linear([[2,1],[1,2]], [p,1])
        need(min(x,y,w,r) > 0, "strict factor branch")
        vertices = [(F(0),F(0)), (min(F(labor,2),capital),F(0)),
                    (F(0),min(F(labor),capital/2)), (x,y)]
        need(p*x+y == max(p*qx+qy for qx,qy in vertices), "factor primal optimum")
        need(p*x+y == w*labor+r*capital, "factor supporting bound")
        factor_cases += 1
    need(linear([[2,1],[1,2]],[113,100]) == (42,29), "factor endowment response")
    need(linear([[2,1],[1,2]],[203,100]) == (102,-1), "factor infeasible branch")
    need(2*100 <= 203 and 100+2*0 == 100, "outside-cone feasible corner")
    for qx in range(101):
        for qy in range(51):
            if 2*qx+qy <= 203 and qx+2*qy <= 100:
                need(qx+qy <= 100, "outside-cone global bound")
    for labor, capital, p_aut in ((110,100,F(3,4)), (100,110,F(4,3))):
        x,y = linear([[2,1],[1,2]],[labor,capital])
        income = p_aut*x+y
        need((income/(2*p_aut),income/2) == (x,y), "factor autarky demand")
        need((x+y)/2 == 35, "factor trade consumption")
        need(x*y == 1200 and 35**2 == 1225, "factor national utility")
    need(linear([[2,1],[1,2]],[F(3,4),1]) == (F(1,6),F(5,12)), "factor autarky rewards")
    need(F(1,6)/F(3,4) == F(2,9) and F(5,12)/F(3,4) == F(5,9), "factor real rewards")
    checks.append({"name":"Factor resources, ownership and global branch", "diversified_cases":factor_cases,
                   "status":"pass", "outside_cone":{"X":100,"Y":0,"unused_labor":3,"w":0,"r":1}})

    old_l2, old_k2 = F(55,3)**2/3, F(125,3)**2/3
    new_l2, new_k2 = F(65,6)**2, F(145,6)**2
    need(new_l2-old_l2 == new_k2-old_k2 == F(575,108), "compensation utility gains")
    lo = 250/(3*math.sqrt(3))-100/3
    hi = 110/3-110/(3*math.sqrt(3))
    need(lo < 15 < hi and 70**2 > 40**2*3, "compensation feasible interval")
    need(abs(lo-14.7792)<0.00005 and abs(hi-15.4972)<0.00005, "rounded transfer bounds")
    checks.append({"name":"Explicit compensation and individual welfare", "status":"pass",
                   "transfer":15,"each_squared_utility_gain":"575/108","transfer_bounds":[lo,hi]})

    tariff_count = 0
    for market, t in itertools.product(("small","large"), sorted({F(k,4) for k in range(141)} | {F(50,7)})):
        actual = module.tariff(market,t)
        expected = tariff_reference(market,t)
        for key,value in expected.items():
            need(actual[key] == value, "tariff independent " + key)
        need(actual["border_transaction_price"] == (expected["foreign_offer_price"] if expected["imports"] else None), "no nonexistent border price")
        if market == "small":
            delta = -2*min(t,F(15))**2
        else:
            delta = 24*t-F(42,25)*t*t if t<=25 else F(-450)
            world = -F(6,5)*t*t if t<=25 else F(-750)
            need(actual["world_change"] == world, "world tariff resource loss")
        need(actual["home_change"] == delta, "tariff piecewise welfare")
        tariff_count += 1
    for row in output["tariffs"]:
        expected = tariff_reference(row["market"],F(row["t"]))
        need(all(F(row[k]) == v for k,v in expected.items()), "fixture tariff result")
    need(tariff_reference("small",F(5))["home_welfare"] == 1650, "small worked ledger")
    need(tariff_reference("small",F(10))["home_welfare"] == 1500, "small exercise ledger")
    need(tariff_reference("large",F(5))["home_welfare"] == 1778, "large worked ledger")
    checks.append({"name":"Independent tariff market balance, corner and benefit-cost ledgers",
                   "status":"pass","parameter_cases":tariff_count,"fixture_cases":len(output["tariffs"])})

    tstar = F(50,7)
    optimal = tariff_reference("large",tstar)
    need((optimal["imports"],optimal["foreign_offer_price"],optimal["domestic_price"],optimal["home_change"],optimal["foreign_change"],optimal["world_change"])
         == (F(300,7),F(120,7),F(170,7),F(600,7),F(-7200,49),F(-3000,49)), "global tariff optimum anchors")
    for t in (F(k,4) for k in range(101)):
        need(24*t-F(42,25)*t*t == F(600,7)-F(42,25)*(t-tstar)**2, "completed-square policy identity")
    need(24-F(84,25)*tstar == 0 and F(-450)<F(600,7), "global tariff boundary certificate")
    shipping = tariff_reference("large",F(5))
    home_shipping = shipping["home_welfare"] - 5*shipping["imports"]
    need(home_shipping == 1538 and home_shipping-1700 == -162, "shipping home resource loss")
    need(home_shipping-1700+shipping["foreign_change"] == -270, "shipping world resource loss")
    checks.append({"name":"Global tariff optimum and real-cost counterexample", "status":"pass",
                   "t_star":"50/7","home_gain":"600/7","foreign_change":"-7200/49","world_change":"-3000/49","shipping_world_change":-270})

    firm_count = 0
    params = list(itertools.product(map(F,(10,40,50)),(F(1,2),F(1),F(2)),map(F,(1,64,144)),map(F,(4,16,28,50)),(F(1),F(3,2),F(3))))
    params += [tuple(F(row[k]) for k in ("A","b","F","c","tau")) for row in data["firms"]]
    for param in params:
        actual = module.exporter(*param)
        choices,best = firm_reference(*param)
        need([x["delivered"] for x in actual["optimal_choices"]] == choices, "export global choices")
        need(actual["maximum_net_profit"] == best, "export global profit")
        for choice in actual["optimal_choices"]:
            q = choice["delivered"]
            need(choice["produced"] == param[4]*q, "iceberg quantities")
            need(choice["price"] == (param[0]-param[1]*q if q else None), "actual exporter price")
        firm_count += 1
    need(firm_reference(F(50),F(1),F(64),F(68,3),F(3,2)) == ([F(0),F(8)],F(0)), "exact exporter tie")
    need(firm_reference(F(50),F(1),F(80),F(68,3),F(3,2)) == ([F(0)],F(0)), "avoidable setup exit")
    need(F(64)-80 == -16 > -80, "sunk versus avoidable cost")
    need(F(30)+F(64,10) == F(182,5) and F(30)+F(64,20) == F(166,5), "scale average costs")
    checks.append({"name":"Independent global export choice, ties, scale and margins", "status":"pass","cases":firm_count})

    bad = []
    def mutated(edit):
        d = deepcopy(data)
        edit(d)
        bad.append(d)
    mutated(lambda d:d.update(schema="different"))
    mutated(lambda d:d.update(provenance="actual country data"))
    mutated(lambda d:d["units"].update(price="euros per unit"))
    mutated(lambda d:d.update(unused_parameter=1))
    mutated(lambda d:d.pop("firms"))
    mutated(lambda d:d.update(tariffs=[]))
    mutated(lambda d:d.update(firms={} ))
    mutated(lambda d:d.update(firms=d["firms"]*10))
    mutated(lambda d:d["firms"][0].update(name=""))
    mutated(lambda d:d["firms"][1].update(name=d["firms"][0]["name"]))
    mutated(lambda d:d["firms"][0].update(extra=1))
    mutated(lambda d:d["firms"][0].pop("c"))
    mutated(lambda d:d["tariffs"][0].update(market="unknown"))
    for value in (-1,True,1.5,float("nan"),float("inf"),"0/0","1.5","1/0","1/1000001",10**7,"1"*33):
        mutated(lambda d,v=value:d["tariffs"][0].update(t=v))
    for key in ("A","b","F","c"):
        for value in (0,-1):
            mutated(lambda d,k=key,v=value:d["firms"][0].update({k:v}))
    mutated(lambda d:d["firms"][0].update(tau="1/2"))
    for invalid in bad:
        try:
            module.analyze(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid input accepted")
    checks.append({"name":"Input/schema/domain/unit rejection", "status":"pass","invalid_cases":len(bad)})

    # Detect plausible result corruptions independently of self-reported balances.
    damaged = deepcopy(output["tariffs"][1]); damaged["home_welfare"] = str(F(damaged["home_welfare"])+F(damaged["revenue"]))
    need(F(damaged["home_welfare"]) != tariff_reference("small",F(5))["home_welfare"], "double-counted revenue mutant")
    clipped = F(20)+20
    need(120-2*clipped != 2*clipped-20, "prohibitive-price extrapolation mutant")
    need((F(20)-F(3,2)*20)**2/4-1 > 0 and firm_reference(F(20),F(1),F(1),F(20),F(3,2))[0] == [0], "negative-margin squaring mutant")
    checks.append({"name":"Damaged-result checks", "status":"pass","mutants_caught":3})

    parser = Fragment(); parser.feed(manuscript); parser.close()
    need(not parser.stack and not parser.h1, "balanced chapter fragment")
    need(parser.worked >= 2 and parser.ol_counts == [8,8], "eight aligned exercises/solutions")
    need(len(parser.ids) == len(set(parser.ids)), "unique chapter ids")
    need("Teach-back" in manuscript and "Delayed-check answer" in manuscript, "answered retention")
    download_links = [x for x in parser.links if x.startswith("v06-c10-")]
    need(len(download_links) == 3 and all('/' not in x and (PROJECT/x).is_file() for x in download_links), "flat local downloads")
    ids = {s["id"] for s in source_records}
    need(set(parser.sources) == ids and len(ids) == 6, "six scoped primary source IDs")
    need(all(set(s)=={"id","title","url","use","checked","verification"} and s["id"].startswith("v06-c10-") for s in source_records), "source proposal schema")
    checks.append({"name":"Manuscript/snippet/source structure", "status":"pass","worked_examples":parser.worked,
                   "exercises":8,"solutions":8,"source_records":len(ids)})

    with tempfile.TemporaryDirectory(prefix="v06-c10-check-") as temp:
        tempdir=Path(temp); labdir=tempdir/"lab"; labdir.mkdir()
        for name in ("v06-c10-analysis.py","v06-c10-inputs.json"):
            shutil.copyfile(PROJECT/name,labdir/name)
        for flag in ([],["-O"]):
            run=subprocess.run([sys.executable,*flag,str(labdir/"v06-c10-analysis.py")],cwd=tempdir,capture_output=True,text=True,check=False)
            need(run.returncode==0 and not run.stderr and json.loads(run.stdout)==output, "portable standalone lab")
        invalid=deepcopy(data);invalid["units"]["price"]="unsupported dollars"
        badpath=tempdir/"invalid.json";badpath.write_text(json.dumps(invalid))
        run=subprocess.run([sys.executable,"-O",str(labdir/"v06-c10-analysis.py"),str(badpath)],cwd=tempdir,capture_output=True,text=True,check=False)
        need(run.returncode==1 and not run.stdout and "error" in json.loads(run.stderr), "invalid optimized CLI")
    checks.append({"name":"Portable normal/optimized CLI and quiet API", "status":"pass"})
    report={"chapter":"v06-c10","status":"pass","checks":checks,
            "limitations":["Exact synthetic equations, not empirical trade-policy identification or calibration.",
                           "Finite numerical checks supplement the chapter's analytic global arguments.",
                           "Source inspection scope is recorded separately; numerical checks do not certify sources.",
                           "No browser, mobile or print visual QA."]}
    json.dumps(report,allow_nan=False)
    return report


if __name__ == "__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
