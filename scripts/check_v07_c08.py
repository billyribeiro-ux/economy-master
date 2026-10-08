"""Independent exact numerical/structural audit for v07-c08; quiet check()."""
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

BOOK=Path(__file__).resolve().parents[1]
PROJECT=BOOK/"content/projects"


def need(condition,message):
    if not condition: raise AssertionError(message)


def reference(products,hours,setups):
    """One-dimensional endpoint argument, unlike lab's full pair enumeration."""
    s,p=products["S"],products["P"]
    ms=s["price"]-s["variable"];mp=p["price"]-p["variable"]
    rows=[];count=0
    for x in range(s["demand"]+1):
        leftover_h=hours-x*s["hours"]
        leftover_b=setups-((x+s["batch_size"]-1)//s["batch_size"])
        if leftover_h < 0 or leftover_b < 0: continue
        upper=min(p["demand"],leftover_h//p["hours"],leftover_b*p["batch_size"])
        count+=upper+1
        ys=[upper] if mp > 0 else ([0] if mp < 0 else range(upper+1))
        rows.extend((ms*x+mp*y,x,y) for y in ys)
    best=max(r[0] for r in rows)
    return best,[(x,y) for value,x,y in rows if value==best],count


def accounting(plan,opening=F(20000)):
    q=lambda key:F(plan[key])
    need(q("revenue")-q("variable")==q("contribution"),"revenue/variable contribution")
    need(q("contribution")-q("fixed")==q("profit")==q("cash_change"),"profit and current cash")
    need(q("ending_cash")==q("ending_equity")==opening+q("profit"),"entity stock/flow closure")
    assigned=sum(F(v) for v in plan["abc_assigned"].values())
    remaining=q("unused_machine")+q("unused_setups")+q("common")
    need(assigned+remaining==q("fixed"),"all overhead supplied reconciles")
    need(sum(F(v) for v in plan["abc_product_margin"].values())-remaining==q("profit"),"ABC margins reconcile profit")
    if plan["traditional_allocation"] is not None:
        need(sum(F(v) for v in plan["traditional_allocation"].values())==q("fixed"),"traditional pool")
        need(sum(F(v) for v in plan["traditional_product_margin"].values())==q("profit"),"traditional profit")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ols=[];self.counts=[];self.links=[];self.worked=0;self.h1=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="aside" and "worked" in a.get("class","").split():self.worked+=1
        if tag=="h1":self.h1+=1
        if tag=="a":self.links.append(a.get("href",""))
        if tag=="ol":self.ols.append(0)
        if tag=="li" and self.ols:self.ols[-1]+=1
        if tag not in {"br","hr","img","input","meta","link"}:self.stack.append(tag)
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1]==tag,"balanced HTML fragment")
        self.stack.pop()
        if tag=="ol":self.counts.append(self.ols.pop())


def check():
    checks=[];buffer=io.StringIO()
    spec=importlib.util.spec_from_file_location("v07_c08_lab",PROJECT/"v07-c08-analysis.py")
    lab=importlib.util.module_from_spec(spec)
    with redirect_stdout(buffer),redirect_stderr(buffer):
        spec.loader.exec_module(lab)
        data=json.loads((PROJECT/"v07-c08-inputs.json").read_text())
        result=lab.run(data)
    need(not buffer.getvalue(),"quiet lab import/API")
    products,h,b,pools,base,mix,special,opening=lab.validate(data)
    baseline=result["baseline"];optimal=result["first_optimal_plan"]
    fields=["hours","setups","revenue","variable","contribution","fixed","profit","ending_cash"]
    need([F(baseline[k]) for k in fields]==list(map(F,[240,18,9840,6600,3240,3000,240,20240])),"baseline exact targets")
    need([F(optimal[k]) for k in fields]==list(map(F,[300,22,12480,8400,4080,3000,1080,21080])),"optimal exact targets")
    for plan in (baseline,optimal): accounting(plan)
    need(baseline["abc_assigned"]=={"S":"900","P":"1080"},"ABC driver targets")
    need(baseline["traditional_product_margin"]=={"S":"300","P":"-60"},"allocated P loss")
    need(optimal["abc_assigned"]=={"S":"1200","P":"1260"},"optimal assignments")
    # Independent signed trial balance: all costs and revenue are current cash.
    ledger={"cash":F(20000)+9840-6600-1800-900-300,"capital":F(-20000),"revenue":F(-9840),"variable":F(6600),"fixed":F(3000)}
    need(sum(ledger.values())==0 and ledger["cash"]==20240,"independent cash trial balance")
    need(F(result["break_even"]["continuous_bundles"])==F(100,9) and result["break_even"]["minimum_whole_bundles"]==12,"mix break-even")
    need(11*270-3000==-30 and 12*270-3000==240 and F(820)*F(100,9)==F(82000,9),"neighbor and revenue break-even")
    checks.append(dict(name="Exact baseline/optimum statements, pool allocations and fixed-mix break-even",status="pass"))

    cases=[(0,30),(1,30),(159,30),(160,30),(300,30),(301,30),(305,30),(310,30),(380,30),(400,30),(300,20),(300,0)]
    for hours,setups in cases:
        observed=lab.solve(products,hours,setups);value,choices,count=reference(products,hours,setups)
        need(observed["contribution"]==value and [(q["S"],q["P"]) for q in observed["choices"]]==choices and observed["feasible_pairs"]==count,"independent endpoint reference")
    need(result["optimum"]["choices"]==[{"S":80,"P":28}] and result["optimum"]["feasible_pairs"]==3493,"unique baseline/count")
    need(reference(products,301,30)[1]==[(78,29),(80,28)],"one-hour tie")
    need(reference(products,400,30)[:2]==(F(5040),[(80,44)]),"setup bound at expansion")
    # Verify the chapter's certificates over every admissible pair, independently.
    for x in range(81):
        for y in range(51):
            setups=(x+9)//10+(y+1)//2
            if setups<=30 and 2*x+5*y<=300:
                need(30*x+60*y==12*(2*x+5*y)+6*x<=4080,"machine/demand certificate")
            if setups<=30:
                need(F(x,10)+F(y,2)<=30 and 30*x+60*y<=3600+18*x<=5040,"setup/demand certificate")
    # A tiny counterexample establishes why the lab does not rely on greedy ranking.
    toy={"S":dict(price=5,variable=0,hours=3,batch_size=1,demand=2),"P":dict(price=3,variable=0,hours=2,batch_size=1,demand=2)}
    need(lab.solve(toy,4,10)["choices"]==[{"S":0,"P":2}],"integer greedy failure")
    tie=deepcopy(toy)
    for p in tie.values():p["variable"]=p["price"]
    tied=lab.solve(tie,4,10)
    need(tied["contribution"]==0 and len(tied["choices"])==4,"preserve all zero-margin ties")
    checks.append(dict(name="Global certificates, independently reduced optimization, integer ties and resource boundaries",status="pass",capacity_cases=len(cases)))

    order=result["special_order"]
    need([F(order[k]) for k in ["idle_incremental_profit","idle_break_even_quote"]]==[110,74],"idle order")
    busy=order["busy"]
    need([F(busy[k]) for k in ["opportunity_cost","incremental_profit","break_even_unit_quote"]]==[240,-130,98],"busy order")
    need(reference(products,280,29)[:2]==(F(3840),[(80,24)]),"reoptimized displacement")
    changed=deepcopy(data);changed["products"]["P"]["variable"]=110
    late=lab.run(changed)
    need(late["optimum"]["choices"]==[{"S":80,"P":28}] and F(late["optimum"]["contribution"])==3800,"retention optimum")
    need(F(late["first_optimal_plan"]["profit"])==800 and F(late["special_order"]["busy"]["opportunity_cost"])==200 and F(late["special_order"]["busy"]["incremental_profit"])==-90 and F(late["special_order"]["busy"]["break_even_unit_quote"])==94,"retention full targets")
    need(100*14+300==1700 and 100*17+100==1800 and 1700-1800+500==400 and F(1700+500-100,100)==21,"make/buy worked example")
    checks.append(dict(name="Opportunity-cost reoptimization, make/buy and answered delayed check",status="pass"))

    ex={}
    profits={q:10*q-(600+4*q+(300 if q>100 else 0)) for q in range(161)}
    ex["1"]={"break_even":[q for q,p in profits.items() if p==0],"demand120_best":max(range(121),key=profits.get)}
    need(ex["1"]=={"break_even":[100,150],"demand120_best":100} and profits[120]==-180,"exercise 1")
    ex["2"]=[F(2100,110),F(2100,130),F(20*110-2100),F(17*130-2100),F(20*30+40*50-2100)]
    need(ex["2"]==[F(210,11),F(210,13),F(100),F(110),F(500)],"exercise 2")
    ex["3"]=[F(300*2+2*30),F(450*2+12*30),F(150*2),F(6*30)]
    need(ex["3"]==list(map(F,[660,1260,300,180])) and sum(ex["3"])==2400,"exercise 3")
    ex["4"]=[F(80*30+30*60),F(80*30+30*60-4080-150),F(80*30+44*60)]
    need(ex["4"]==list(map(F,[4200,-30,5040])),"exercise 4")
    ex["5"]=[F(6*(45-18)-36-3*40),F(18)+F(36+120,6),F(6-20),F(18)+F(36+120+20,6),F(6*(45-18)-36)]
    need(ex["5"]==[F(6),F(44),F(-14),F(142,3),F(126)],"exercise 5")
    make=F(50*8+200);buy=F(50*13+100)
    ex["6"]=[make,buy,make-buy+180,(make+180-100)/50,make-buy+180+30,(make+180+30-100)/50]
    need(ex["6"]==list(map(F,[600,750,30,"13.6",60,"14.2"])),"exercise 6")
    revenue=F(90*50);abs_profit=revenue-90*30-90*4-300;var_profit=revenue-90*20-1200-90*4-300;cash=revenue-120*20-1200-90*4-300
    ex["7"]=[abs_profit,var_profit,F(30*30),F(30*20),cash]
    need(ex["7"]==list(map(F,[1140,840,900,600,240])) and abs_profit-900==var_profit-600==cash,"exercise 7")
    ex["8"]=[F(1200,4),F(400)-F(1200,4),F(400)-F(1200,4)-150]
    need(ex["8"]==list(map(F,[300,100,-50])),"exercise 8")
    checks.append(dict(name="All eight independent exact exercise calculations",status="pass",results={k:([str(x) for x in v] if isinstance(v,list) else v) for k,v in ex.items()}))

    abs_profit=F(80*60)-80*40-80*5-200;var_profit=F(80*60)-80*30-1000-80*5-200
    cash=F(80*60)-100*30-1000-80*5-200
    need(abs_profit==1000 and var_profit==800 and cash==200 and abs_profit-800==var_profit-600==cash,"worked inventory bridge")
    zero=deepcopy(data);zero["baseline"]={"S":0,"P":0}
    z=lab.run(zero)["baseline"];accounting(z)
    need(z["traditional_allocation"] is None and F(z["unused_machine"])+F(z["unused_setups"])+F(z["common"])==3000,"zero-output denominator boundary")
    no_margin=deepcopy(data)
    for p in no_margin["products"].values():p["price"]=p["variable"]
    need(lab.run(no_margin)["break_even"]["continuous_bundles"] is None,"no positive-fixed-cost break-even at zero margin")
    checks.append(dict(name="Inventory-profit/cash bridge and zero-output/zero-margin boundaries",status="pass"))

    invalid=[]
    for parent,key,value in [("units","money","kCU"),("capacity","machine_hours",0),("capacity","setup_batches",17),("baseline","S",81),(None,"opening_cash_and_equity",0)]:
        bad=deepcopy(data);(bad if parent is None else bad[parent])[key]=value;invalid.append(bad)
    for key,value in [("batch_size",0),("demand",201),("variable",70.0)]:
        bad=deepcopy(data);bad["products"]["S"][key]=value;invalid.append(bad)
    for bad in invalid:
        try:lab.run(bad)
        except ValueError:pass
        else:raise AssertionError("invalid case accepted")
    corrupted=deepcopy(baseline);corrupted["unused_machine"]="0"
    try:accounting(corrupted)
    except AssertionError:pass
    else:raise AssertionError("omitted unused pool not caught")
    need(10*(85-70)-40>0 and F(busy["incremental_profit"])<0,"omitted opportunity-cost decision reversal")
    checks.append(dict(name="Eight meaningful failures and two decision/accounting error detectors",status="pass",invalid_cases=len(invalid)))

    html=(BOOK/"content/chapters/v07-c08.html").read_text();parser=Fragment();parser.feed(html);parser.close()
    need(not parser.stack and parser.h1==0 and parser.worked>=3 and parser.counts==[8,8],"chapter structure")
    need("Teach-back benchmark" in html and "Delayed-check answer" in html,"answered retention")
    sources=json.loads((BOOK/"content/reviews/v07-c08-sources.json").read_text());ids={r["id"] for r in sources}
    need({x.split("#")[1] for x in parser.links if x.startswith("sources.html#")}==ids,"source link match")
    need(all(set(r)=={"id","title","url","use","checked","verification"} and r["id"].startswith("v07-c08-") for r in sources),"source schema")
    downloads=[x for x in parser.links if x.startswith("v07-c08-")]
    need(len(downloads)==3 and all("/" not in x and (PROJECT/x).is_file() for x in downloads),"flat downloads")
    checks.append(dict(name="Fragment, four worked cases, eight solved exercises and scoped primary links",status="pass",worked=parser.worked,sources=len(ids)))

    with tempfile.TemporaryDirectory(prefix="v07-c08-check-") as tmp:
        folder=Path(tmp)
        for name in ("v07-c08-analysis.py","v07-c08-inputs.json"):shutil.copyfile(PROJECT/name,folder/name)
        for flag in ([],["-O"]):
            proc=subprocess.run([sys.executable,*flag,str(folder/"v07-c08-analysis.py")],cwd=folder,capture_output=True,text=True,check=False)
            need(proc.returncode==0 and not proc.stderr and json.loads(proc.stdout)==result,"portable CLI")
        bad=deepcopy(data);bad["units"]["money"]="USD";path=folder/"invalid.json";path.write_text(json.dumps(bad))
        proc=subprocess.run([sys.executable,"-O",str(folder/"v07-c08-analysis.py"),str(path)],capture_output=True,text=True,check=False)
        need(proc.returncode!=0 and not proc.stdout and "units" in proc.stderr,"unit error CLI")
    checks.append(dict(name="Portable normal/optimized CLI and quiet exact JSON API",status="pass"))
    report=dict(chapter="v07-c08",status="pass",checks=checks,limitations=[
        "Original finite synthetic decisions; input demand, avoidability, driver validity, quality and probabilities require evidence.",
        "Global enumeration covers the stated integer set; algebraic bounds separately prove the specified optima, not arbitrary large production problems.",
        "Internal before-tax teaching conventions, not current reporting compliance or an assertion that allocated cost is avoidable.",
        "No browser, mobile or print visual QA."])
    json.dumps(report,allow_nan=False)
    return report


if __name__=="__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
