#!/usr/bin/env python3
"""Independent exact checks for v06-c08; quiet import/API and JSON-only CLI."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType

BOOK = Path(__file__).resolve().parents[1]
CHAPTER = BOOK / "content/chapters/v06-c08.html"
PROJECT = BOOK / "content/projects/v06-c08-analysis.py"
INPUT = PROJECT.with_name("v06-c08-inputs.json")
SOURCES = BOOK / "content/reviews/v06-c08-sources.json"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_program(path):
    module = ModuleType("v06_c08_lab")
    module.__file__ = str(path)
    output, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    require(not output.getvalue() and not errors.getvalue(), "quiet program import")
    return module


def gauss(matrix, rhs):
    """Exact elimination, independent of the chapter's substitution formulas."""
    size = len(rhs)
    rows = [list(map(Q, row)) + [Q(value)] for row, value in zip(matrix, rhs)]
    require(all(len(row) == size+1 for row in rows), "square system")
    for col in range(size):
        pivot = next((r for r in range(col, size) if rows[r][col]), None)
        require(pivot is not None, "nonsingular reference system")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        denominator = rows[col][col]
        rows[col] = [entry/denominator for entry in rows[col]]
        for r in range(size):
            if r != col:
                multiple = rows[r][col]
                rows[r] = [a-multiple*b for a,b in zip(rows[r], rows[col])]
    return tuple(row[-1] for row in rows)


def enumerate_nk(p, case):
    """Solve all dates simultaneously for every floor/free regime, then filter."""
    sigma,beta,kappa,phi,psi = (Q(str(p[k])) for k in ("sigma","beta","kappa","phi_pi","phi_x"))
    length = len(case["n"])
    terminal_x,terminal_pi = Q(str(case["terminal_x"])),Q(str(case["terminal_pi"]))
    solutions = set()
    for floors in product((False,True), repeat=length):
        matrix, rhs = [], []
        for t in range(length):
            n,u,v = (Q(str(case[k][t])) for k in ("n","u","v"))
            row = [Q(0)]*(3*length)
            row[3*t],row[3*t+2] = Q(1),sigma
            value = sigma*n
            if t+1 < length:
                row[3*(t+1)],row[3*(t+1)+1] = Q(-1),-sigma
            else:
                value += terminal_x+sigma*terminal_pi
            matrix.append(row); rhs.append(value)
            row = [Q(0)]*(3*length)
            row[3*t],row[3*t+1] = -kappa,Q(1)
            value = u
            if t+1 < length:
                row[3*(t+1)+1] = -beta
            else:
                value += beta*terminal_pi
            matrix.append(row); rhs.append(value)
            row = [Q(0)]*(3*length)
            row[3*t+2] = Q(1)
            if floors[t]:
                value = Q(-2)
            else:
                row[3*t],row[3*t+1],value = -psi,-phi,v
            matrix.append(row); rhs.append(value)
        values = gauss(matrix, rhs)
        admissible = True
        for t in range(length):
            x,pi,j = values[3*t:3*t+3]
            requested = phi*pi+psi*x+Q(str(case["v"][t]))
            admissible &= j >= -2 and (requested <= -2 if floors[t] else requested >= -2)
        if admissible:
            solutions.add(values)
    require(len(solutions) == 1, "one distinct feasible finite path, including equality")
    return next(iter(solutions))


def validate_rows(parameters, case, rows):
    sigma,beta,kappa,phi,psi = (Q(str(parameters[k])) for k in ("sigma","beta","kappa","phi_pi","phi_x"))
    require(len(rows) == len(case["n"]), "one output row per date")
    for t,row in enumerate(rows):
        require(row["date"] == t, "chronological date labels")
        x,pi,j = (Q(row[k]) for k in ("x","pi","j"))
        next_x = Q(rows[t+1]["x"]) if t+1 < len(rows) else Q(str(case["terminal_x"]))
        next_pi = Q(rows[t+1]["pi"]) if t+1 < len(rows) else Q(str(case["terminal_pi"]))
        n,u,v = (Q(str(case[k][t])) for k in ("n","u","v"))
        require(x-next_x+sigma*(j-next_pi-n) == 0, "independent demand residual")
        require(pi-beta*next_pi-kappa*x-u == 0, "independent inflation residual")
        requested = phi*pi+psi*x+v
        require(j == max(Q(-2),requested), "independent policy and floor residual")
        require(Q(row["requested_j"]) == requested, "reported requested rate")
        require(Q(row["nominal_log_rate"]) == 2+j, "nominal baseline restored")
        require(row["strictly_floor_limited"] == (requested < -2), "floor equality semantics")
        require(all(Q(value) == 0 for value in row["residuals"].values()), "reported zero residuals")


def static_case(gov=20,tax=20,money=50,premium=0):
    gov,tax,money,premium = map(Q,(gov,tax,money,premium))
    # Direct original IS and LM equations, not the manuscript's closed form.
    y,rate = gauss([[Q(2,5),2],[Q(1,2),-5]], [50-Q(3,5)*tax+gov-2*premium,money])
    consumption = 20+Q(3,5)*(y-tax)
    investment = 30-2*(rate+premium)
    require(y == consumption+investment+gov, "goods resource ledger")
    require(money == y/2-5*rate, "money ledger")
    return y,rate,consumption,investment


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(); self.worked=0; self.exercises=0; self.solutions=0
        self.ols=[]; self.details=[]; self.links=[]; self.headers=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=="aside" and "worked" in attrs.get("class","").split(): self.worked+=1
        if tag=="details": self.details.append("solutions" in attrs.get("class","").split())
        if tag=="ol":
            self.ols.append("exercise" if "exercises" in attrs.get("class","").split() else
                            "solution" if self.details and self.details[-1] else "other")
        if tag=="li" and self.ols:
            if self.ols[-1]=="exercise": self.exercises+=1
            if self.ols[-1]=="solution": self.solutions+=1
        if tag=="a": self.links.append(attrs.get("href",""))
        if tag in ("h1","h2","h3"): self.headers.append(tag)
    def handle_endtag(self,tag):
        if tag=="ol": self.ols.pop()
        if tag=="details": self.details.pop()


def check():
    checks=[]
    limitations=[
        "Synthetic maintained models; no empirical estimation or external academic validation.",
        "Finite terminal conditions and bounded lab inputs; no infinite-horizon determinacy or approximation-accuracy proof.",
        "Source inspection supports scoped methods; original numerical results are independently checked here.",
        "Browser/mobile/print visual QA is pending; no restricted-preview workaround performed.",
        "Root integration, dependency acceptance and publication are separate from this author check."]
    try:
        lab=load_program(PROJECT)
        data=json.loads(INPUT.read_text())
        quiet=io.StringIO()
        with redirect_stdout(quiet): result=lab.analyze(data)
        require(not quiet.getvalue(), "quiet lab API")
        json.dumps(result,allow_nan=False)
        for case,output in zip(data["cases"],result["cases"]):
            reference=enumerate_nk(data["parameters"],case)
            values=tuple(Q(row[k]) for row in output["rows"] for k in ("x","pi","j"))
            require(values==reference,"simultaneous reference agrees for "+case["name"])
            validate_rows(data["parameters"],case,output["rows"])
        targets={
            "baseline": [(0,0,0),(0,0,0)],
            "one_date_demand": [(-1,Q(-1,2),-1)],
            "one_date_cost": [(-1,Q(1,2),1)],
            "deep_demand": [(-4,-2,-2)],
            "future_demand": [(Q(-1,2),Q(-1,2),-1),(-1,Q(-1,2),-1)],
            "future_cost": [(Q(-1,2),0,0),(-1,Q(1,2),1)],
            "persistent_floor": [(-10,-6,-2),(-4,-2,-2)],
            "floor_equality": [(-2,-1,-2)],
            "future_tightening": [(Q(-1,2),Q(-1,2),-1),(-1,Q(-1,2),1)],
            "nonzero_terminal": [(Q(1,4),Q(3,4),Q(3,2)),(Q(1,2),Q(5,4),Q(5,2))]}
        for output in result["cases"]:
            rows=[tuple(Q(row[k]) for k in ("x","pi","j")) for row in output["rows"]]
            require(rows==targets[output["name"]],"published NK target "+output["name"])
        checks.append({"name":"announced NK paths and eight-exercise dynamic answers","status":"pass","cases":10,
                       "method":"exact joint Gaussian elimination and exhaustive floor-regime inequalities"})

        variants=0
        for beta,phi,psi,shock in product((0,Q(3,4)),(0,3),(0,Q(1,2)),(-5,0,3)):
            sample={"description":"independent parameter transfer", "parameters":{"sigma":0.5,"beta":float(beta),
                    "kappa":0.75,"phi_pi":phi,"phi_x":float(psi)},
                    "cases":[{"name":"transfer","n":[shock,-2],"u":[1,-1],"v":[0,1],
                              "terminal_x":1,"terminal_pi":-0.5}]}
            output=lab.analyze(sample)["cases"][0]
            reference=enumerate_nk(sample["parameters"],sample["cases"][0])
            actual=tuple(Q(row[k]) for row in output["rows"] for k in ("x","pi","j"))
            require(actual==reference,"coefficient-transfer joint reference")
            validate_rows(sample["parameters"],sample["cases"][0],output["rows"])
            variants+=1
        checks.append({"name":"finite uniqueness across coefficients and branches","status":"pass","cases":variants})

        require(static_case()==(130,3,86,24),"baseline static targets")
        require(static_case(gov=26)==(140,4,92,22),"fixed-money fiscal shift")
        require(static_case(premium=3)==(120,2,80,20),"exercise 1 credit premium")
        require(static_case(gov=26,premium=3)==(130,3,86,18),"exercise 1 compensation")
        require(static_case(money=80)==(150,-1,98,32),"exercise 2 forbidden root")
        require(static_case(gov=26,tax=26)==(134,Q(17,5),Q(424,5),Q(116,5)),"retention")
        for gov,premium,rate,y,money in ((26,0,3,145,Q(115,2)),(20,3,3,115,Q(85,2)),(20,0,0,145,Q(145,2))):
            consumption=20+Q(3,5)*(y-20); investment=30-2*(rate+premium)
            require(y==consumption+investment+gov and money==Q(y,2)-5*rate,"rate-peg ledgers")
        require(150 != 20+Q(3,5)*130+30+20 and 80 != Q(150,2),"clipping violates both markets")
        delta=Q(1,10)
        base=static_case()
        require((static_case(gov=20+delta)[0]-base[0])/delta==Q(5,3),"fiscal multiplier")
        require((static_case(tax=20+delta)[0]-base[0])/delta==-1,"tax multiplier")
        require((static_case(money=50+delta)[0]-base[0])/delta==Q(2,3),"money output effect")
        require((static_case(money=50+delta)[1]-base[1])/delta==Q(-2,15),"money rate effect")
        checks.append({"name":"IS-LM ledgers, instruments, derivatives, exercises 1-2 and retention","status":"pass"})

        price=(23+math.sqrt(1729))/30
        negative=(23-math.sqrt(1729))/30
        require(price>0 and negative<0,"unique positive price root")
        require(abs(15*price**2-23*price-20)<1e-12,"AD-AS polynomial")
        outcomes=[]
        for gov,supply_shift in ((26,0),(20,0.2)):
            y=50*price+30-50*supply_shift
            a=38+gov
            rate=(a-0.4*y)/2
            require(abs(y-(a+40/price)/0.6)<1e-12,"AD original equation")
            require(abs(price-(2+(y-130)/50+supply_shift))<1e-12,"AS original equation")
            require(abs(100/price-(0.5*y-5*rate))<1e-12,"endogenous real balances")
            require(20<=y<=200 and 0<=rate<=15 and 30-2*rate>=0,"AD-AS admissibility")
            outcomes.append(y)
        require(abs(outcomes[0]-outcomes[1]-10)<1e-12,"exercise 3 exact symbolic difference")
        require(abs(100*math.log(price/2)-7.357949329954312)<1e-11,"price-level to dated inflation")
        require(math.log(price/price)==0,"no continuing inflation from constant level")
        checks.append({"name":"AD-AS positive root and exercise 3","status":"pass",
                       "price":price,"demand_output":outcomes[0],"supply_output":outcomes[1]})

        for y,beta,investment,current in ((12,1,4,8),(15,1,5,10),(15,Q(1,2),3,12)):
            y,beta,investment,current=map(Q,(y,beta,investment,current))
            require(current+investment==y and 0<investment<y,"RBC feasibility")
            require(-1/current+beta/(2*investment)==0,"RBC Euler certificate")
            # Clearing positive denominators: F'(I) has numerator beta*Y-(2+beta)*I.
            require(beta*y-(2+beta)*investment==0,"exact derivative numerator root")
            for trial in (investment/2,(investment+y)/2):
                numerator=beta*y-(2+beta)*trial
                require((numerator>0)==(trial<investment),"global derivative sign")
            require(-1/current**2-beta/(2*investment**2)<0,"strict curvature")
        for productivity in (4,8):
            i=Q(3); c0=Q(12)
            # MP/C1 = [A/(2 sqrt(I))]/[A sqrt(I)] = 1/(2I), exactly.
            require(Q(1,2)/(2*i)==1/c0,"exercise 4 productivity cancellation")
            require(productivity>0,"positive terminal output")
        require(6*math.sqrt(4)==12 and 9*math.sqrt(4)==18,"worked terminal consumption")
        checks.append({"name":"finite real resources, Euler/global certificate and exercise 4","status":"pass"})

        loss_targets=[(1,0,-1,Q(1,2),1,Q(1,2)),(0,-2,0,0,-2,0),
                      (0,-6,-4,-2,-2,8),(2,-1,-2,1,1,2),(1,-5,-3,Q(-1,2),-2,Q(5,2))]
        for u,n,x,pi,j,loss in loss_targets:
            u,n,x,pi,j,loss=map(Q,(u,n,x,pi,j,loss))
            require(pi==x/2+u and x==n-j and j>=-2,"policy optimum feasible")
            require(pi*pi+x*x/4==loss,"loss target")
            for trial in (Q(k,2) for k in range(-30,15)):
                direct=(trial/2+u)**2+trial**2/4
                require(direct==(trial+u)**2/2+u*u/2,"global completed-square identity")
                if trial<=n+2: require(direct>=loss,"feasible comparison certificate")
            derivative=x+u
            require((derivative==0 and x<=n+2) or (x==n+2 and derivative<=0),"convex boundary KKT")
        require(Q(0)**2+Q(-4)**2/4==4 and Q(2)**2==4,"exercise 7 full-stabilization alternatives")
        checks.append({"name":"one-date global loss certificates and exercise 7","status":"pass"})

        for n,v,j in ((-2,0,-1),(0,2,1)):
            x,pi,u=Q(-1),Q(-1,2),Q(0)
            require(x==n-j and pi==x/2+u and j==max(-2,2*pi+v),"exercise 8 equivalent observations")
        require(math.log(90/90)==0 and abs(100*math.log(90/100)+10.536051565782628)<1e-12,"distinct output references")
        nominal,growth=Q(103,100),Q(101,100)
        require(nominal/growth==Q(103,101),"exact Fisher gross relation")
        require(abs(100*math.log(float(nominal/growth))-(100*math.log(float(nominal))-100*math.log(float(growth))))<1e-12,"log rate identity")
        checks.append({"name":"observational equivalence, natural-output references and rate units","status":"pass"})

        bad=[]
        def changed(path,value):
            item=deepcopy(data); target=item
            for key in path[:-1]: target=target[key]
            target[path[-1]]=value
            bad.append(item)
        for value in (True,float('nan'),float('inf'),"1",None,-1,0,11): changed(("parameters","sigma"),value)
        for key,value in (("beta",1.1),("kappa",0),("phi_pi",-1),("phi_x",-1)):
            changed(("parameters",key),value)
        for value in ([],[0]*7,[True],[21],[float('-inf')],"0"):
            changed(("cases",0,"n"),value)
        changed(("cases",0,"u"),[0])
        changed(("cases",0,"terminal_pi"),float('nan'))
        changed(("cases",0,"terminal_x"),21)
        changed(("cases",1,"name"),"baseline")
        changed(("cases",0,"name"),"")
        changed(("cases",0,"unexpected"),1)
        changed(("unexpected",),1)
        changed(("cases",),[])
        changed(("cases",),data["cases"]*3)
        missing=deepcopy(data); del missing["parameters"]["kappa"]; bad.append(missing)
        for invalid in bad:
            try: lab.analyze(invalid)
            except ValueError: pass
            else: raise AssertionError("invalid input accepted")
        checks.append({"name":"explicit validation survives optimization","status":"pass","rejected_inputs":len(bad)})

        # Deliberately damaged paths; direct equations, not reported residuals, must catch them.
        mutants=[]
        deep=deepcopy(result["cases"][3]["rows"]); deep[0]["x"]="-3"; deep[0]["pi"]="-3/2"
        mutants.append((data["cases"][3],deep,"clip rate without resolving quantities"))
        future=deepcopy(result["cases"][4]["rows"])
        future[0].update(x="0",pi="0",j="0",requested_j="0",nominal_log_rate="2")
        mutants.append((data["cases"][4],future,"ignore announced future news"))
        wrong=deepcopy(result["cases"][5]["rows"]); wrong[0]["pi"]="-1/2"
        mutants.append((data["cases"][5],wrong,"reverse forward inflation sign"))
        for case,rows,label in mutants:
            try: validate_rows(data["parameters"],case,rows)
            except AssertionError: pass
            else: raise AssertionError("mutant escaped: "+label)
        checks.append({"name":"independent residual mutation checks","status":"pass","caught":[m[2] for m in mutants]})

        with tempfile.TemporaryDirectory(prefix="v06-c08-") as directory:
            directory=Path(directory)
            executable=directory/PROJECT.name; executable.write_text(PROJECT.read_text())
            (directory/INPUT.name).write_text(INPUT.read_text())
            for flags in ([],["-O"]):
                run=subprocess.run([sys.executable,*flags,str(executable)],cwd=directory.parent,capture_output=True,text=True,timeout=20)
                require(run.returncode==0 and not run.stderr,"portable quiet success CLI")
                require(json.loads(run.stdout)==result,"portable and -O targets")
            invalid_path=directory/"invalid.json"; invalid_path.write_text(json.dumps(bad[0]))
            run=subprocess.run([sys.executable,"-O",str(executable),str(invalid_path)],cwd=directory.parent,capture_output=True,text=True,timeout=20)
            require(run.returncode==1 and not run.stdout and json.loads(run.stderr)["status"]=="error","explicit invalid CLI")
        checks.append({"name":"portable script-relative inputs, quiet import and normal/-O CLI","status":"pass"})

        html=CHAPTER.read_text(); structure=Structure(); structure.feed(html)
        require(structure.worked>=4 and structure.exercises==8 and structure.solutions==8,"four worked/eight aligned solutions")
        require("h1" not in structure.headers and not structure.ols and not structure.details,"fragment structure")
        sources=json.loads(SOURCES.read_text())
        require(len(sources)==4 and len({s["id"] for s in sources})==4,"four unique primary methods")
        for source in sources:
            require(set(source)=={"id","title","url","use","checked","verification"},"source schema")
            require(source["id"].startswith("v06-c08-") and source["checked"]=="2026-10-08","source scope/date")
            require("sources.html#"+source["id"] in structure.links,"source route in chapter")
        for href in structure.links:
            if href.startswith("v06-c08-"):
                require("/" not in href and (PROJECT.parent/href).is_file(),"flat artifact link exists")
        require("Delayed-check answer" in html and "Teach-back checklist" in html,"self-study closure")
        require("curriculum.html#v06" in structure.links and "v06-c09.html" not in structure.links,"planned successor route")
        checks.append({"name":"fragment, complete exercise alignment, source and artifact routes","status":"pass",
                       "worked_examples":structure.worked,"exercises":structure.exercises,"solutions":structure.solutions})
        return {"status":"pass","checks":checks,"limitations":limitations}
    except Exception as error:
        return {"status":"fail","checks":checks,"error":type(error).__name__+": "+str(error),"limitations":limitations}


if __name__=="__main__":
    outcome=check()
    print(json.dumps(outcome,indent=2,allow_nan=False))
    sys.exit(0 if outcome["status"]=="pass" else 1)
