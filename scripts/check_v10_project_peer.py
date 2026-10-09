"""Independent peer audit of the Alder project; standard library, quiet check()."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from functools import lru_cache
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import math
from pathlib import Path
import runpy
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "content/projects"
HTML = "content/assessments/parts/v10-project.html"
SELF = "scripts/check_v10_project_peer.py"
PEER = "content/reviews/v10-project-peer.json"
AUTHOR_PATHS = [HTML] + ["content/projects/v10-assessment-"+suffix for suffix in
    ("inputs.json", "analysis.py", "output.json", "manifest.json", "README.txt")] + [
    "scripts/check_v10_project.py", "content/reviews/v10-project-author.json",
    "content/reviews/v10-project-sources.json"]


class Audit:
    def __init__(self):
        self.comparisons, self.rejections = 0, 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def near(self, actual, expected, label, tolerance=2e-9):
        self.comparisons += 1
        if not math.isfinite(float(actual)) or abs(float(actual)-float(expected)) > tolerance:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")

    def vector(self, actual, expected, label, tolerance=2e-9):
        self.comparisons += 1
        if len(actual) != len(expected) or any(not math.isfinite(float(x)) or
                abs(float(x)-float(y)) > tolerance for x,y in zip(actual,expected)):
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")


def normal(z):
    return math.erfc(-z/math.sqrt(2))/2


def integrate(function, left, right, order=64):
    """Generated Gauss-Legendre rule, not the author/model Simpson integrator."""
    if right <= left:
        return 0.0
    answer = []
    for i in range(1,order+1):
        z = math.cos(math.pi*(i-.25)/(order+.5))
        for _ in range(30):
            previous, value = 1.0,z
            for n in range(2,order+1):
                previous,value = value,((2*n-1)*z*value-(n-1)*previous)/n
            derivative = order*(z*value-previous)/(z*z-1)
            change = value/derivative
            z -= change
            if abs(change) < 3e-16:
                break
        else:
            raise ArithmeticError("Legendre root failed")
        previous,value = 1.0,z
        for n in range(2,order+1):
            previous,value = value,((2*n-1)*z*value-(n-1)*previous)/n
        derivative = order*(z*value-previous)/(z*z-1)
        weight = 2/((1-z*z)*derivative*derivative)
        answer.append(weight*function((right+left)/2+(right-left)*z/2))
    return (right-left)*math.fsum(answer)/2


def payoff_integral(spot,strike,rate,sigma,time):
    drift,scale = (rate-sigma*sigma/2)*time,sigma*math.sqrt(time)
    cutoff = (math.log(strike/spot)-drift)/scale
    return integrate(lambda z: math.exp(-rate*time)*(strike-spot*math.exp(drift+scale*z))
                     *math.exp(-z*z/2)/math.sqrt(2*math.pi),-10,min(10,cutoff))


def delta(spot,strike,rate,sigma,time):
    cutoff = (math.log(strike/spot)-(rate-sigma*sigma/2)*time)/(sigma*math.sqrt(time))
    return -normal(cutoff-sigma*math.sqrt(time))


def ideal_moments(spot,strike,rate,sigma,time,beta):
    """Closed truncated-lognormal moments, independent of numerical integration."""
    m,v = (rate-sigma*sigma/2)*time,sigma*sigma*time
    a = math.sqrt(v)
    c = (math.log(strike/spot)-m)/a
    discount = math.exp(-rate*time)
    truncated = [spot**p*math.exp(p*m+p*p*v/2)*normal(c-p*a) for p in (0,1,2)]
    mean = discount*(strike*truncated[0]-truncated[1])
    second = discount*discount*(strike*strike*truncated[0]-2*strike*truncated[1]+truncated[2])
    covariance = discount*discount*(strike*truncated[1]-truncated[2])-spot*mean
    var_x = spot*spot*math.expm1(v)
    cross = 0.0
    if c > 0:
        probability = normal(c)-normal(-c)
        exponential = math.exp(v/2)*(normal(c-a)-normal(-c-a))
        cross = discount*discount*((strike*strike+spot*spot*math.exp(2*m))*probability
                                    -2*strike*spot*math.exp(m)*exponential)
    variance = second-mean*mean
    return {"mean":mean,"plain_variance":variance,"stock_variance":var_x,
            "covariance":covariance,"controlled_variance":variance+beta*beta*var_x-2*beta*covariance,
            "pair_variance":(second+cross)/2-mean*mean}


def seeded_samples(spot,strike,rate,sigma,time,count,seed,beta):
    plain,controlled,pairs,stocks = [],[],[],[]
    def observed(z):
        x = spot*math.exp(-sigma*sigma*time/2+sigma*math.sqrt(time)*z)
        return max(strike*math.exp(-rate*time)-x,0),x
    for i in range(count):
        bits = int(sha256(f"alder-project-v1|{seed}|{i}".encode("ascii")).hexdigest(),16)
        mask = (1<<52)-1
        u = math.ldexp(((bits>>204)&mask)+.5,-52)
        v = math.ldexp(((bits>>140)&mask)+.5,-52)
        radius,angle = math.sqrt(-2*math.log(u)),2*math.pi*v
        z,w = radius*math.cos(angle),radius*math.sin(angle)
        for value in (z,w):
            y,x = observed(value)
            plain.append(y); stocks.append(x); controlled.append(y-beta*(x-spot))
        pairs.append((observed(z)[0]+observed(-z)[0])/2)
    return {"plain":plain,"controlled":controlled,"antithetic":pairs,"discounted_stock":stocks}


def exercise_reference(spot,strike,rate,sigma,time,steps,allowed):
    """Top-down conditional value, independently evaluating reachable node cash."""
    dt = time/steps
    up = math.exp(sigma*math.sqrt(dt)); growth = math.exp(rate*dt)
    p = (growth-1/up)/(up-1/up)
    stops = {}
    @lru_cache(None)
    def value(i,j):
        stock = spot*math.exp((2*j-i)*sigma*math.sqrt(dt))
        exercise = max(strike-stock,0)
        if i == steps:
            return exercise
        continuation = ((1-p)*value(i+1,j)+p*value(i+1,j+1))/growth
        if i in allowed and exercise > continuation:
            stops[i,j] = (i*dt,stock,exercise,continuation)
            return exercise
        return continuation
    price = value(0,0)
    low,high = value(1,0),value(1,1)
    return price,stops,(low,high),up,growth,p


def hedge_reference(times,spots,strike,rate,sigma,premium,cost):
    """Accumulate discounted trade cash; do not repeat a financed bank recursion."""
    discounts = [math.exp(-rate*t) for t in times]
    holdings = [delta(s,strike,rate,sigma,times[-1]-t) for s,t in zip(spots[:-1],times[:-1])]+[0.0]
    old,spent,pv_fees,rows = 0.0,0.0,0.0,[]
    for t,s,d,h in zip(times,spots,discounts,holdings):
        before = (premium-spent-pv_fees)/d
        trade,fee = (h-old)*s,cost*abs(h-old)*s
        spent += d*trade; pv_fees += d*fee
        after = (premium-spent-pv_fees)/d
        rows.append((t,s,old,h,before,trade,fee,after,after+h*s))
        old = h
    payoff = max(strike-spots[-1],0)
    return rows,(premium-spent-pv_fees)/discounts[-1]-payoff,pv_fees


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.links=set(); self.points=[]; self.stack=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if "id" in d:self.ids.append(d["id"])
        if "href" in d:self.links.add(d["href"])
        if "data-points" in d:self.points.append(int(d["data-points"]))
        if tag in ("html","head","body","h1","script"):raise AssertionError("fragment only")
        if tag not in ("br","hr","img","meta","input","link"):self.stack.append(tag)
    def handle_endtag(self,tag):
        if not self.stack or self.stack.pop()!=tag:raise AssertionError("unbalanced fragment")


def check():
    a=Audit()
    data=json.loads((ASSETS/"v10-assessment-inputs.json").read_text())
    saved=deepcopy(data); stream=StringIO()
    with redirect_stdout(stream),redirect_stderr(stream):
        namespace=runpy.run_path(str(ASSETS/"v10-assessment-analysis.py"))
        run=namespace["run"]; output=run(data)
    a.eq(stream.getvalue(),"","quiet import/API")
    a.eq(data,saved,"nonmutating API")
    a.eq(output,json.loads((ASSETS/"v10-assessment-output.json").read_text()),"complete saved-output reproduction")
    json.dumps(output,allow_nan=False)
    legacy=deepcopy(output)
    for key in ("selected_reserve_pv","reserve_budget_pv","reserve_budget_rule"):
        del legacy["decision"][key]
    a.eq(sha256((json.dumps(legacy,indent=2,allow_nan=False)+"\n").encode()).hexdigest(),
         "6beda7672c89a06ae22de808503144b71b2328aed3fe1e0faccac217df49d947",
         "all pre-repair baseline fields preserved exactly")

    # Dated cash: direct algebra gives an independent exact solution.
    times=(F(1,2),F(1),F(3,2)); cash=(F(3),F(3),F(103))
    quotes=[F(row["price"]) for row in data["curve"]["instruments"]]
    ds=(quotes[0]/100,(quotes[1]-3*quotes[0]/100)/103,
        (quotes[2]-2*quotes[0]/100-2*(quotes[1]-3*quotes[0]/100)/103)/102)
    a.eq(ds,(F(49,50),F(19,20),F(91,100)),"three exact curve nodes")
    bond=output["bond"]; pv=sum(c*d for c,d in zip(cash,ds))
    exposure=tuple(t*c*d for t,c,d in zip(times,cash,ds))
    a.eq(tuple(map(F,bond["discounts"])),ds,"quoted curve output")
    a.eq(F(bond["pv"]),pv,"fixed promise PV")
    a.eq(tuple(map(F,bond["key_rate_dollar_exposures"])),exposure,"dated key exposures")
    a.eq(F(bond["parallel_dollar_duration"]),sum(exposure),"parallel first derivative")
    a.eq(F(bond["parallel_second_derivative"]),sum(t*x for t,x in zip(times,exposure)),"parallel second derivative")
    a.eq(F(bond["parallel_duration_years"]),sum(exposure)/pv,"normalized continuous duration")
    a.eq(tuple(map(F,bond["simple_forward_rates"])),(F(2,49),F(6,95),F(8,91)),"interval forward units")
    for row,actual in zip(data["curve"]["instruments"],bond["calibration"]):
        a.eq(sum(F(c)*d for c,d in zip(row["cash"],ds)),F(actual["reprice"]),"exact instrument cash")
        a.eq(F(actual["residual"]),0,"exact calibration residual")
    short_pv=(times[-1]*pv-sum(exposure))/(times[-1]-times[0])
    barbell=(short_pv/ds[0],F(0),(pv-short_pv)/ds[-1])
    a.eq(tuple(map(F,bond["barbell_zero_quantities"])),barbell,"barbell cash quantities")
    gaps=tuple((b-c)*d for b,c,d in zip(barbell,cash,ds))
    a.eq(sum(gaps),0,"barbell initial value match")
    a.eq(sum(t*g for t,g in zip(times,gaps)),0,"barbell parallel first-order match")
    for shock,actual in zip(data["curve"]["shocks"],bond["shocks"]):
        z=list(map(F,shock["zero_shifts"]))
        surplus=math.fsum(float(g)*math.expm1(-float(t*h)) for g,t,h in zip(gaps,times,z))
        approximation=sum(g*(-t*h+(t*h)**2/2) for g,t,h in zip(gaps,times,z))
        bound=sum(abs(float(g))*math.exp(abs(float(t*h)))*abs(float(t*h))**3/6 for g,t,h in zip(gaps,times,z))
        a.near(actual["barbell_minus_liability"],surplus,"direct finite surplus")
        a.near(actual["second_order_residual"],approximation,"second-order surplus")
        a.eq(abs(surplus-float(approximation))<=bound,True,"explicit finite exponential remainder")

    rate=-2*math.log(float(ds[0])); spot,strike,sigma,maturity=100,105,.25,.5
    option=output["option"]; analytic=option["analytic"]
    put=payoff_integral(spot,strike,rate,sigma,maturity)
    moments=ideal_moments(spot,strike,rate,sigma,maturity,-.5)
    a.near(analytic["put"],put,"independent Legendre put integral",3e-11)
    a.near(moments["mean"],put,"truncated moment and quadrature agree",3e-11)
    a.near(analytic["call"]-put,spot-strike*float(ds[0]),"call-put parity")
    h=.01
    plus=payoff_integral(spot+h,strike,rate,sigma,maturity)
    minus=payoff_integral(spot-h,strike,rate,sigma,maturity)
    a.near(analytic["put_delta"],(plus-minus)/(2*h),"payoff-integral spot derivative",2e-8)
    a.near(analytic["gamma"],(plus+minus-2*put)/(h*h),"payoff-integral second derivative",1e-8)
    vstep=1e-5
    a.near(analytic["vega"],(payoff_integral(spot,strike,rate,sigma+vstep,maturity)-
                             payoff_integral(spot,strike,rate,sigma-vstep,maturity))/(2*vstep),"payoff-integral vega",2e-8)
    a.near(option["quadrature"]["fine"]-put,1.82927e-8,"refinement is only a diagnostic",1e-11)
    a.near(option["quadrature"]["omitted_tail_upper_bound"],2*105*.98*normal(-10),"bounded-payoff omitted tails",1e-32)
    early_counts={}
    for grid in option["trees"]:
        n=grid["steps"]
        for rights,allowed in (("european",set()),("bermudan",{0,n//2}),("american",set(range(n)))):
            value,stops,successors,up,growth,p=exercise_reference(spot,strike,rate,sigma,maturity,n,allowed)
            actual=grid[rights]
            a.near(actual["price"],value,"top-down "+rights+" value")
            a.eq(actual["exercise_node_count"],len(stops),"complete optimal node count")
            if n==4:
                early_counts[rights]=len(stops)
                a.eq({(row["step"],row["up_moves"]) for row in actual["exercise_nodes"]},set(stops),"every coarsest exercise decision")
                for row in actual["exercise_nodes"]:
                    a.vector([row[k] for k in ("time","spot","exercise","continuation")],stops[row["step"],row["up_moves"]],"early decision cash")
                hedge=actual["root_continuation_hedge"]
                a.vector((hedge["stock_units"]*spot/up+hedge["initial_bank"]*growth,
                          hedge["stock_units"]*spot*up+hedge["initial_bank"]*growth),successors,"both funded root successor states")
        terminal=float(ds[0])*math.fsum(math.comb(n,j)*p**j*(1-p)**(n-j)*
                    max(strike-spot*up**(2*j-n),0) for j in range(n+1))
        a.near(grid["european"]["price"],terminal,"terminal binomial expectation")
        a.eq(grid["european"]["price"]<=grid["bermudan"]["price"]<=grid["american"]["price"],True,"same-law exercise-set order")

    a.vector([moments[k] for k in ("plain_variance","covariance","controlled_variance","pair_variance")],
             [106.463456912,-156.753973262,29.068002398,16.797720226],"analytic ideal moments",5e-8)
    samples=seeded_samples(spot,strike,rate,sigma,maturity,2048,271828,-.5)
    for kind,values in samples.items():
        actual=option["monte_carlo"][kind]
        mean=statistics.mean(values); variance=statistics.variance(values); se=math.sqrt(variance/len(values))
        a.eq(actual["units"],len(values),"independent sample units")
        a.vector([actual[k] for k in ("mean","sample_variance","estimated_se")],(mean,variance,se),"seeded moments via statistics",2e-8)
        a.vector(actual["approximate_95_interval"],(mean-1.96*se,mean+1.96*se),"fixed-sample approximate interval")
        if kind in ("plain","antithetic"):
            a.near(actual["ideal_iid_hoeffding_95_halfwidth"],105*.98*math.sqrt(math.log(40)/(2*len(values))),"ideal bounded iid guarantee")
    a.eq("ideal_iid_hoeffding_95_halfwidth" in option["monte_carlo"]["controlled"],False,"unbounded control has no borrowed Hoeffding claim")

    ht=list(map(lambda x:float(F(x)),data["hedge"]["times"]))
    hedge_rows=0; errors=[]
    for path,actual in zip(data["hedge"]["paths"],output["hedge"]["paths"]):
        levels=list(map(lambda x:float(F(x)),path["spots"]))
        for label,cost in (("frictionless",0),("with_costs",.001)):
            rows,error,pv_cost=hedge_reference(ht,levels,strike,rate,sigma,put,cost)
            for row,wanted in zip(actual[label]["ledger"],rows):
                a.vector(list(row.values()),wanted,"all dated trade/stock/bank fields "+path["id"])
                hedge_rows+=1
            a.near(actual[label]["terminal_error"],error,"discounted cash terminal error")
            a.near(actual[label]["present_transaction_costs"],pv_cost,"dated stock fees")
            a.near(actual[label]["terminalized_transaction_costs"],pv_cost/.98,"fee accumulation")
        errors.append(error)
    buffer=.98*max(0,-min(errors)-1)
    required=float(pv)+put+buffer
    a.near(output["decision"]["additional_initial_cash_for_tested_loss_budget"],buffer,"tested-path initial capital")
    a.near(output["decision"]["quote_with_tested_buffer"],required,"scenario-qualified quote threshold")
    credit=output["credit_reserve"]
    default=(F(3),F(0),F(40)); default_pv=sum(c*d for c,d in zip(default,ds))
    a.eq(F(credit["default_pv"]),default_pv,"default cash at actual dates")
    a.eq(F(credit["risky_reserve_pv"]),F(9,10)*pv+F(1,10)*default_pv,"pricing-law mixture")
    a.eq(F(credit["apparent_initial_saving"]),(pv-default_pv)/10,"expected loss versus state loss")
    a.eq((F(output["decision"]["selected_reserve_pv"]),F(output["decision"]["reserve_budget_pv"])),
         (F("93.502"),pv),"baseline saving does not lower conservative reserve floor")
    a.eq(output["decision"]["reserve_budget_rule"],"max(riskless fixed-liability PV, selected reserve purchase PV)","explicit reserve budget rule")
    for i,row in enumerate(credit["default_funding_ledger"]):
        before=sum((default[j]-cash[j])*ds[j] for j in range(i))/ds[i]
        a.eq(tuple(map(F,[row[k] for k in ("time","liability_cash","reserve_cash","bank_before_payment","bank_after_payment")])),
             (times[i],cash[i],default[i],before,before+default[i]-cash[i]),"complete default funding row")
    a.eq(F(credit["default_terminal_bank"]),F(-6018,91),"bridge-inclusive deficit")
    a.eq(output["decision"]["failed_gates"],["reserve_funds_all_declared_dates","quote_covers_tested_loss_budget"],"all baseline failures")

    # Every fresh transfer: preserve all unaffected baseline inputs.
    def changed(edit):
        variant=deepcopy(data); edit(variant); return run(variant)
    higher=changed(lambda x:x["curve"]["instruments"][2].update(price="96.70"))
    a.eq(F(higher["bond"]["discounts"][-1])-ds[-1],F(1,5100),"transfer1 curve propagation")
    a.eq(F(higher["bond"]["pv"])-pv,F(103,5100),"transfer1 fixed sleeve")
    a.eq(F(higher["credit_reserve"]["risky_reserve_pv"])-F(credit["risky_reserve_pv"]),F(967,51000),"transfer1 risky sleeve")
    a.eq(higher["option"],option,"transfer1 option tenor unchanged")
    calm=changed(lambda x:x["hedge"]["paths"][2].update(spots=["100","100","100","100","90"]))
    for label,cost,wanted in (("frictionless",0,1.806685410882),("with_costs",.001,1.677445349078)):
        result=hedge_reference(ht,[100,100,100,100,90],strike,rate,sigma,put,cost)[1]
        a.near(result,wanted,"transfer2 calm independently funded result")
        a.near(calm["hedge"]["paths"][2][label]["terminal_error"],result,"transfer2 model comparison")
        terminal=hedge_reference([0,.5],[100,90],strike,rate,sigma,put,cost)[1]
        a.near(terminal,.237938687906 if cost==0 else .136305514536,"transfer2 endpoint-only equality")
    immediate=changed(lambda x:x["credit_reserve"].update(settlement_index=1))
    a.eq(F(immediate["credit_reserve"]["risky_reserve_pv"]),F("93.662"),"transfer3 early recovery PV")
    a.eq(tuple(F(row["bank_after_payment"]) for row in immediate["credit_reserve"]["default_funding_ledger"]),
         (0,37,F(-5858,91)),"transfer3 complete funding dates")
    spread_cost=3*95/91*math.expm1(.02*.5)
    a.near(spread_cost,.031475798011,"transfer3 extra bridge spread")
    full=changed(lambda x:x["credit_reserve"].update(recovery_fraction="1"))
    a.eq(F(full["credit_reserve"]["default_terminal_bank"]),F(-558,91),"transfer4 face recovery omits coupons")
    a.eq((F("6.018")-(pv-default_pv))/ds[-1],F(-27081,455),"transfer4 saving cannot fund conditional loss")
    wrong=changed(lambda x:x["option"].update(control_beta="1"))
    bad_moments=ideal_moments(spot,strike,rate,sigma,maturity,1)
    a.near(bad_moments["controlled_variance"],737.405478428,"transfer5 wrong-sign ideal variance",5e-8)
    bad_samples=seeded_samples(spot,strike,rate,sigma,maturity,2048,271828,1)["controlled"]
    bad_mean=statistics.mean(bad_samples); bad_se=math.sqrt(statistics.variance(bad_samples)/len(bad_samples))
    a.vector([wrong["option"]["monte_carlo"]["controlled"][k] for k in ("mean","estimated_se")],(bad_mean,bad_se),"transfer5 unselected seeded experiment")
    rights=changed(lambda x:x["decision"].update(requested_exercise="american",requested_quote="119"))
    a.eq(rights["decision"]["gates"]["exercise_matches_european_reference"],False,"transfer5 larger quote does not change rights")
    repair=changed(lambda x:x["decision"].update(requested_reserve="matched_zeros",requested_quote="119"))
    a.eq(list(repair["decision"]["gates"].values()),[True]*5,"transfer6 all limited baseline gates")
    a.near(119-required,.055129909600,"transfer6 initial headroom")
    doubled=changed(lambda x:x["hedge"].update(cost_rate=".002"))
    for old,new in zip(output["hedge"]["paths"],doubled["hedge"]["paths"]):
        a.near(old["with_costs"]["terminal_error"]-new["with_costs"]["terminal_error"],
               old["with_costs"]["terminalized_transaction_costs"],"transfer6 exact fee decrement")
    a.near(doubled["hedge"]["paths"][2]["with_costs"]["terminal_error"],-12.130884682906,"transfer6 round-trip boundary")
    # Root finding: an early full-face recovery can cost MORE than the fixed
    # liability. Every selected asset must be paid for at inception; expected
    # reserve savings must still not lower the conservative riskless floor.
    expensive=deepcopy(data)
    expensive["liability"]["coupons"]=["0","0","0"]
    expensive["credit_reserve"].update(default_index=0,settlement_index=0,recovery_fraction="1")
    expensive["decision"].update(requested_reserve="risky_bond",requested_quote="110.5")
    expensive_out=run(expensive)
    reserve_cost=F(9,10)*100*ds[-1]+F(1,10)*100*ds[0]
    expensive_budget=float(max(100*ds[-1],reserve_cost))+put+buffer
    a.eq(reserve_cost,F("91.7"),"early-recovery selected reserve purchase cost")
    a.eq(F(expensive_out["credit_reserve"]["risky_reserve_pv"]),reserve_cost,"premium reserve independently priced")
    a.eq((F(expensive_out["decision"]["selected_reserve_pv"]),F(expensive_out["decision"]["reserve_budget_pv"])),
         (reserve_cost,reserve_cost),"premium reserve exact purchase and budget fields")
    a.near(expensive_out["decision"]["quote_with_tested_buffer"],expensive_budget,"selected reserve premium must be funded")
    a.near(expensive_budget-110.5,.624870090400,"previously omitted initial cash")
    a.eq(expensive_out["decision"]["failed_gates"],["quote_covers_tested_loss_budget"],"funding dates pass but initial purchase budget fails")
    for quoted,passes in (("111.12487009",False),("111.12487010",True),("111.125",True)):
        variant=deepcopy(expensive);variant["decision"]["requested_quote"]=quoted
        actual=run(variant)["decision"]
        a.eq(actual["gates"]["quote_covers_tested_loss_budget"],passes,"eight-decimal quote boundary "+quoted)
        a.eq(actual["recommendation"],"eligible_for_limited_demonstration" if passes else "revise_before_demo","premium reserve permission boundary")
    zero_selected=deepcopy(expensive);zero_selected["decision"]["requested_reserve"]="matched_zeros"
    zero_out=run(zero_selected)
    a.eq((F(zero_out["decision"]["selected_reserve_pv"]),F(zero_out["decision"]["reserve_budget_pv"])),
         (F(91),F(91)),"selected matched-zero purchase fields")
    a.near(zero_out["decision"]["quote_with_tested_buffer"],91+put+buffer,"only the selected reserve is purchased")
    a.eq(zero_out["decision"]["failed_gates"],[],"matched zeros cost less in this valid case")
    negative=deepcopy(data)
    for row,quote in zip(negative["curve"]["instruments"],("102","105.03","100.92")):row["price"]=quote
    negative["option"]["mc_pairs"]=64
    negative_out=run(negative); negative_rate=-2*math.log(1.02)
    a.near(negative_out["option"]["analytic"]["put"],payoff_integral(spot,strike,negative_rate,sigma,maturity),"valid negative-rate market")

    probes=[(("option","spot"),True),(("option","spot"),100.0),(("option","spot"),"1e2"),
            (("option","sigma"),"0"),(("option","seed"),True),(("option","mc_pairs"),4097),
            (("option","bermudan_fractions"),["1/3"]),(("curve","times"),["1/2","1/2","3/2"]),
            (("hedge","cost_rate"),"-.001"),(("hedge","paths",0,"spots"),["100","102"]),
            (("credit_reserve","settlement_index"),0),(("decision","requested_quote"),"-1")]
    for path,value in probes:
        invalid=deepcopy(data); node=invalid
        for key in path[:-1]:node=node[key]
        node[path[-1]]=value
        try:run(invalid)
        except ValueError:a.rejections+=1
        else:raise AssertionError("invalid input accepted: "+repr(path))
    invalid=deepcopy(data); invalid["unexpected"]=1
    try:run(invalid)
    except ValueError:a.rejections+=1
    else:raise AssertionError("unknown object key accepted")

    # Only model/input are necessary for the portable user-facing program.
    with tempfile.TemporaryDirectory(prefix="v10-project-peer-") as directory:
        folder=Path(directory); model=folder/"v10-assessment-analysis.py"; inputs=folder/"v10-assessment-inputs.json"
        shutil.copyfile(ASSETS/model.name,model); shutil.copyfile(ASSETS/inputs.name,inputs)
        for optimized in (False,True):
            prefix=[sys.executable]+(["-O"] if optimized else [])
            saved_result=folder/"result.json"
            process=subprocess.run(prefix+[str(model),"--input",str(inputs),"--output",str(saved_result)],cwd="/",text=True,capture_output=True,timeout=30)
            a.eq((process.returncode,process.stdout,process.stderr),(0,"",""),"portable quiet explicit CLI")
            a.eq(json.loads(saved_result.read_text()),output,"portable output all fields")
            process=subprocess.run(prefix+[str(model)],cwd="/",text=True,capture_output=True,timeout=30)
            a.eq((process.returncode,process.stderr),(0,""),"different-cwd script-relative default")
            a.eq(json.loads(process.stdout),output,"default CLI all fields")
            for malformed in ('{"schema":1,"schema":2}','{"schema":NaN}',json.dumps(invalid)):
                bad=folder/"bad.json";bad.write_text(malformed);saved_result.write_text("preserve")
                process=subprocess.run(prefix+[str(model),"--input",str(bad),"--output",str(saved_result)],cwd="/",text=True,capture_output=True,timeout=30)
                if process.returncode==0 or saved_result.read_text()!="preserve":raise AssertionError("invalid CLI mutated output")
                a.rejections+=1
            before=model.read_bytes()
            process=subprocess.run(prefix+[str(model),"--output",str(model)],cwd="/",text=True,capture_output=True,timeout=30)
            if process.returncode==0 or model.read_bytes()!=before:raise AssertionError("implementation overwrite permitted")
            a.rejections+=1

    doc=Fragment();doc.feed((ROOT/HTML).read_text())
    a.eq(doc.stack,[],"balanced project fragment")
    a.eq(doc.points,[20]*5,"five-domain100-point rubric")
    a.eq(len(set(doc.ids)),len(doc.ids),"unique identifiers")
    a.eq({f"v10-project-task-{i}" for i in range(1,9)}<=set(doc.ids),True,"eight learner work packages")
    for suffix in ("inputs.json","analysis.py","output.json","manifest.json","README.txt"):
        a.eq("v10-assessment-"+suffix in doc.links,True,"flat downloadable asset")
    sources=json.loads((ROOT/AUTHOR_PATHS[-1]).read_text())
    a.eq({s["id"] for s in sources},{h.split("#",1)[1] for h in doc.links if h.startswith("sources.html#")},"all six scoped source routes")
    manifest=json.loads((ASSETS/"v10-assessment-manifest.json").read_text())["files"]
    a.eq({row["file"] for row in manifest},{"v10-assessment-"+s for s in ("inputs.json","analysis.py","output.json","README.txt")},"manifest binds exact four payloads")
    for row in manifest:
        payload=(ASSETS/row["file"]).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row["bytes"],row["sha256"]),"portable payload binding")
    author=json.loads((ROOT/"content/reviews/v10-project-author.json").read_text())
    a.eq({row["path"] for row in author["reviewed_hashes"]},set(AUTHOR_PATHS)-{"content/reviews/v10-project-author.json"},"eight nonself author bindings")
    peer=json.loads((ROOT/PEER).read_text())
    a.eq({row["path"] for row in peer["reviewed_hashes"]},set(AUTHOR_PATHS),"nine final author bindings")
    a.eq({row["path"] for row in peer["reviewer_artifacts"]},{SELF},"peer checker binding")
    a.eq({row["task"] for row in peer["task_audit"]},set(range(1,9)),"complete task review")
    a.eq({row["transfer"] for row in peer["transfer_audit"]},set(range(1,7)),"complete transfer review")
    a.eq(peer["necessary_repairs"],[],"all material peer repairs closed")
    a.eq(all(row["status"]=="resolved" for row in peer["findings"]),True,"no unresolved peer finding")
    for row in author["reviewed_hashes"]+peer["reviewed_hashes"]+peer["reviewer_artifacts"]:
        payload=(ROOT/row["path"]).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row["bytes"],row["sha256"]),"frozen artifact "+row["path"])
    summary={"project":"v10","review":"independent-peer","status":"passed","comparisons":a.comparisons,
             "invalid_inputs_rejected":a.rejections,"transfers_checked":6,"funded_hedge_rows_checked":hedge_rows,
             "coarsest_positive_exercise_nodes":early_counts,"author_payload_hashes_checked":9,
             "independent_ideal_moments":moments,"wrong_sign_seeded_mean":bad_mean,"wrong_sign_seeded_se":bad_se,
             "limits":"Separate proof/prompt/source audit and deterministic comparisons; no empirical coverage, all-path hedge guarantee or external human certification."}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=="__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
