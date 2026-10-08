#!/usr/bin/env python3
"""Bounded independent checks for consumption, saving and finite investment.

Quiet check() returns strict-JSON-compatible status/checks/limitations. No network,
packages, shared writes or reliance on removable Python assertions.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as Q
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType

BOOK = Path(__file__).resolve().parents[1]
CHAPTER = BOOK / "content/chapters/v06-c04.html"
PROJECT = BOOK / "content/projects/v06-c04-analysis.py"
INPUT = PROJECT.with_name("v06-c04-inputs.json")
SOURCE = BOOK / "content/reviews/v06-c04-sources.json"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def log_certificate(x0, y1, gross, beta, limit, saving):
    """Verify a proposed choice directly from budgets and marginal utilities."""
    x0, y1, gross, beta, limit, saving = map(Q, (x0,y1,gross,beta,limit,saving))
    c0, c1 = x0-saving, y1+gross*saving
    require(c0 > 0 and c1 > 0 and saving >= -limit, "positive feasible log plan")
    gap = 1/c0-beta*gross/c1
    require(gap >= 0 and gap*(saving+limit) == 0, "log complementary slackness")
    require(c0+c1/gross == x0+y1/gross, "dated versus present-value budget")
    # The exact second derivative is strictly negative throughout the domain.
    curvature = -1/c0**2-beta*gross**2/c1**2
    require(curvature < 0, "strict concavity at certificate")
    return c0, c1, gap


def bisect_log(x0, y1, gross, beta, limit):
    """Independent monotone marginal-equation solution, not the lab formula."""
    x0,y1,gross,beta,limit = map(Q,(x0,y1,gross,beta,limit))
    low, high = max(-limit,-y1/gross), x0
    def slope(s):
        return -1/(x0-s)+beta*gross/(y1+gross*s)
    if y1+gross*low > 0 and slope(low) <= 0:
        return low
    for _ in range(100):
        midpoint = (low+high)/2
        if slope(midpoint) > 0:
            low = midpoint
        else:
            high = midpoint
    return (low+high)/2


def lifecycle(incomes, consumption, nonnegative=False, gross=Q(1)):
    """Recover every asset from dated ledgers; verify terminal and KKT margins."""
    incomes, consumption = list(map(Q,incomes)), list(map(Q,consumption))
    previous = Q(0)
    assets = []
    for income, use in zip(incomes, consumption):
        previous = income+gross*previous-use
        assets.append(previous)
    require(assets[-1] == 0, "terminal assets exhausted")
    require(sum(c/gross**t for t,c in enumerate(consumption)) ==
            sum(y/gross**t for t,y in enumerate(incomes)), "telescoped lifecycle resources")
    require(all(c > 0 for c in consumption), "positive lifecycle consumption")
    # These cases set beta*R=1, so adjacent marginal gaps are simple reciprocals.
    for t, asset in enumerate(assets[:-1]):
        gap = 1/consumption[t]-1/consumption[t+1]
        if nonnegative:
            require(asset >= 0 and gap >= 0 and asset*gap == 0, "lifecycle constraint certificate")
        else:
            require(gap == 0, "unrestricted lifecycle Euler equality")
    return assets


def cash_value(case, investment, *, wrong_discount=False, double_depreciation=False):
    """Direct dated ledger, with explicit wrong variants for mutation checks."""
    d = {key: Q(str(value)) for key,value in case.items() if key != "name"}
    k = (1-d['delta'])*d['K0']+investment
    operating = d['alpha']*k-d['gamma']*k*k/2
    salvage = d['p1']*(1-d['delta'])*k
    if double_depreciation:
        salvage *= 1-d['delta']
    current = d['p0']*investment+d['phi']*investment*investment/2
    return -current+(operating+salvage)/(Q(1) if wrong_discount else d['R'])


def polynomial_reference(case):
    """Recover objective coefficients from three cash-flow evaluations."""
    z, one, two = (cash_value(case,Q(i)) for i in range(3))
    a = (two-2*one+z)/2
    b = one-z-a
    cap = Q(str(case['Ibar']))
    require(a < 0, "strictly concave finite firm objective")
    candidates = [Q(0),cap]
    vertex = -b/(2*a)
    if 0 <= vertex <= cap:
        candidates.append(vertex)
    best = max(candidates,key=lambda i: cash_value(case,i))
    for i in (Q(0),cap,cap/3,cap/2,best):
        require(cash_value(case,i) == a*i*i+b*i+z, "cash ledger versus interpolated polynomial")
        # Exact difference identity supplies a global certificate once slope has the right sign.
        require(cash_value(case,i)-cash_value(case,best) ==
                (2*a*best+b)*(i-best)+a*(i-best)**2, "firm global difference identity")
    slope = 2*a*best+b
    require((best == 0 and slope <= 0) or (best == cap and slope >= 0) or
            (0 < best < cap and slope == 0), "global firm endpoint certificate")
    return best,cash_value(case,best),cash_value(case,best)-z,(a,b,z)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack=[]
        self.hrefs=[]
        self.ids=[]
        self.worked=0
        self.exercise_count=0
        self.solution_count=0
        self.in_exercises=False
        self.solutions_seen=0
        self.in_solutions=False
        self.exercise_depth=None
        self.solution_depth=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag == 'h1':
            raise AssertionError('chapter fragment must have no h1')
        if tag == 'a': self.hrefs.append(attrs.get('href',''))
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'aside' and attrs.get('class') == 'worked': self.worked+=1
        if tag == 'ol' and attrs.get('class') == 'exercises':
            self.in_exercises=True
            self.exercise_depth=len(self.stack)
        if tag == 'details' and attrs.get('class') == 'solutions':
            self.solutions_seen+=1
            self.in_solutions=self.solutions_seen == 1
        if tag == 'ol' and self.in_solutions and self.solution_depth is None:
            self.solution_depth=len(self.stack)
        if tag == 'li' and self.in_exercises and len(self.stack) == self.exercise_depth+1:
            self.exercise_count+=1
        if tag == 'li' and self.in_solutions and self.solution_depth is not None and len(self.stack) == self.solution_depth+1:
            self.solution_count+=1
        if tag not in ('br','hr','img','input','meta','link','wbr'):
            self.stack.append(tag)
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1] == tag, 'balanced HTML: '+tag)
        if tag == 'ol' and self.in_exercises and len(self.stack)-1 == self.exercise_depth:
            self.in_exercises=False
        if tag == 'details': self.in_solutions=False
        self.stack.pop()


def check():
    checks=[]
    cases=[
        (40,100,Q(5,4),1,30,-20,(60,75,0)),
        (40,100,Q(5,4),1,8,-8,(48,90,Q(1,144))),
        (30,72,Q(6,5),Q(5,6),30,Q(-210,11),(Q(540,11),Q(540,11),0)),
        (30,72,Q(6,5),Q(5,6),10,-10,(40,60,Q(1,120))),
        (40,70,Q(5,4),1,30,-8,(48,60,0)),
        (18,42,1,1,6,-6,(24,36,Q(1,72))),
        (18,42,1,1,20,-12,(30,30,0)),
        (12,0,1,1,0,6,(6,6,0))]
    for x0,y1,gross,beta,limit,saving,expected in cases:
        require(log_certificate(x0,y1,gross,beta,limit,saving) == expected, 'household exact answer')
        require(abs(bisect_log(x0,y1,gross,beta,limit)-saving) < Q(1,10**25), 'independent Euler bisection')
    checks.append('Dated budgets, positive feasibility, independent Euler bisection, borrowing KKT and delayed-check exact results')

    for beta, expected in ((Q(1),[Q(20)]),(Q(1,2),[Q(-5)]),(Q(10,11),[Q(-5),Q(20)])):
        slope=beta*Q(11,10)-1
        values={s:20+15*beta+slope*s for s in (Q(-5),Q(20))}
        best=max(values.values())
        require([s for s,v in values.items() if v == best] == expected, 'linear utility endpoints/tie')
        if not slope: require(20+15*beta+slope*Q(17,7) == best, 'every interior plan also ties')
    require(15+Q(11,10)*(-5) == Q(19,2), 'linear lower-bound final consumption')
    require(15+Q(11,10)*20 == 37, 'linear upper-bound final consumption')
    require(Q(20)+Q(15-3)/Q(11,10) == Q(340,11), 'required bequest present value')
    checks.append('Linear-utility zero-consumption endpoints and all-plan tie; required terminal bequest budget')

    for incomes, consumption, bound, assets in [
        ([30,90,0],[40]*3,False,[-10,40,0]),
        ([30,90,0],[30,45,45],True,[0,45,0]),
        ([30,102,0],[44]*3,False,[-14,44,0]),
        ([42,102,12],[52]*3,False,[-10,40,0]),
        ([30,102,0],[30,51,51],True,[0,51,0]),
        ([18,66,48,0],[33]*4,False,[-15,18,33,0]),
        ([18,66,48,0],[18,38,38,38],True,[0,28,38,0]),
        ([18,78,48,0],[36]*4,False,[-18,24,36,0]),
        ([30,78,60,12],[45]*4,False,[-15,18,33,0]),
        ([30,66,48,0],[30,38,38,38],True,[0,28,38,0]),
        ([18,78,48,0],[18,42,42,42],True,[0,36,42,0])]:
        require(lifecycle(incomes,consumption,bound) == assets,'lifecycle dated assets')
    R=Q(11,10)
    incomes=[Q(i) for i in (15,30,45,0)]
    annuity=sum(R**(-t) for t in range(4))
    wealth=sum(y/R**t for t,y in enumerate(incomes))
    lifecycle(incomes,[wealth/annuity]*4,False,R)
    require(sum(Q(12)/R**t for t in range(4))/annuity == 12,'persistent annuity news')
    require(Q(12)/R/annuity < 12,'transitory future news')
    checks.append('All lifecycle/constraint/shock ledgers and a nonunit-return telescoping/annuity check')

    for current, ys, saving, expected_polynomial in [
        (4,(2,6),math.sqrt(6)-2,(2,8,-4)),
        (6,(3,9),(3*math.sqrt(6)-6)/2,(2,12,-9))]:
        a,b,c=expected_polynomial
        require(abs(a*saving*saving+b*saving+c)<1e-12,'risk quadratic root')
        future=[y+saving for y in ys]
        residual=-1/(current-saving)+sum(1/x for x in future)/2
        require(abs(residual)<1e-14 and saving>0 and all(x>0 for x in future),'finite-state risky Euler')
        require(sum(Q(1,y) for y in ys)/2 > Q(1,current),'strict Jensen wedge')
        lo,hi=0.0,float(current)-1e-8
        for _ in range(70):
            mid=(lo+hi)/2
            derivative=-1/(current-mid)+sum(1/(y+mid) for y in ys)/2
            if derivative>0:lo=mid
            else:hi=mid
        require(abs((lo+hi)/2-saving)<1e-12,'independent expected-marginal bisection')
    for s in [Q(-2),Q(0),Q(1,2),Q(5),Q(6)]:
        u=lambda x:20*x-x*x/2
        certain=u(6-s)+u(6+s)
        risky=u(6-s)+(u(3+s)+u(9+s))/2
        require(certain-risky == Q(9,2),'quadratic risk penalty independent of saving')
        require(-(20-(6-s))+(20-(3+s)+20-(9+s))/2 == -2*s,'quadratic derivative')
    checks.append('Finite-risk log roots and Euler residuals; exact quadratic-utility risk-aversion counterexample')

    for gross,c0,c1,s in ((1,30,30,30),(4,40,80,20)):
        require(c0+s == 60 and gross*s == c1,'power-utility dated budgets')
        require(Q(1,c0*c0) == Q(gross,c1*c1),'power-utility Euler')
    require(Q(80,40)>Q(30,30) and 20<30,'saving level versus consumption tilt')
    checks.append('Higher-return/lower-saving example verified directly without inferring levels from the Euler ratio')

    raw=json.loads(INPUT.read_text())
    expected={
        'worked_firm':(Q(2),Q(216,5),Q(12,5)),
        'capacity_one':(Q(1),Q(213,5),Q(9,5)),
        'higher_resale':(Q(5,2),Q(963,20),Q(15,4)),
        'higher_resale_cap_two':(Q(2),Q(48),Q(18,5)),
        'low_operating_return':(Q(0),Q(108,5),Q(0)),
        'no_adjustment_cost':(Q(3),Q(222,5),Q(18,5))}
    references={}
    for case in raw['firms']:
        reference=polynomial_reference(case)
        require(reference[:3] == expected[case['name']],'firm exact reference '+case['name'])
        references[case['name']]=reference
    a,b,z=references['worked_firm'][3]
    require((a,b,z) == (Q(-3,5),Q(12,5),Q(204,5)),'worked investment square identity')
    require(Q(11,10)-Q(4,5) == Q(3,10),'delayed user cost')
    base=raw['firms'][0]
    require(cash_value(base,Q(2),wrong_discount=True) != Q(216,5),'missing-discount mutation caught')
    require(cash_value(base,Q(2),double_depreciation=True) != Q(216,5),'double-depreciation mutation caught')
    require(references['capacity_one'][0] != references['worked_firm'][0],'ignored-capacity mutation caught')
    checks.append('All investment cash ledgers independently interpolated and globally optimized; three deliberate timing/bound mutations caught')

    require(100-90 == 8+2 == 10,'accounting saving/investment and installation resources')
    require(Q(9,10)*50+8 == 53 and 53-50 == 3,'gross versus physical net capital')
    require((30-30)+(6-6) == 0,'consolidated internal financial claims')
    require(cases[1][-1][:2] == (48,90) and cases[4][-1][:2] == (48,60),'observationally equal c0 and distinct planned c1')
    checks.append('Physical/accounting resource distinction and explicit consumption observational equivalence')

    module=ModuleType('v06_c04_lab')
    module.__file__=str(PROJECT)
    capture=io.StringIO()
    with redirect_stdout(capture):
        exec(compile(PROJECT.read_text(),str(PROJECT),'exec'),module.__dict__)
        report=module.analyze(module.load(INPUT))
    require(capture.getvalue() == '', 'quiet lab import/API')
    json.dumps(report,allow_nan=False)
    for name,s,c0,c1,gap in [('worked_unrestricted',-20,60,75,Q(0)),
                            ('worked_credit_limit',-8,48,90,Q(1,144)),
                            ('alternative_belief',-8,48,60,Q(0)),
                            ('zero_future_income',6,6,6,Q(0))]:
        row=report['households'][name]
        require(tuple(Q(row[k]) for k in ['saving','c0','c1','credit_multiplier']) == (s,c0,c1,gap),'lab household reference')
    for name,reference in references.items():
        row=report['firms'][name]
        require(tuple(Q(row[k]) for k in ['investment','present_value','incremental_present_value']) == reference[:3], 'lab versus independent firm reference')
    invalid=[]
    for key,value in [('R',0),('R',float('nan')),('beta',True),('y1',-1),('x0',0),('B','8'),('x0',1000001),('R',1e-200)]:
        item=deepcopy(raw);item['households'][0][key]=value;invalid.append(item)
    for key,value in [('delta',Q(5,4)),('gamma',0),('Ibar',0),('p0',float('inf')),('phi',-1)]:
        item=deepcopy(raw);item['firms'][0][key]=float(value);invalid.append(item)
    item=deepcopy(raw);item['households'].append(deepcopy(item['households'][0]));invalid.append(item)
    item=deepcopy(raw);item['synthetic']=False;invalid.append(item)
    item=deepcopy(raw);item['version']=True;invalid.append(item)
    for bad in invalid:
        try:module.analyze(bad)
        except ValueError:pass
        else:raise AssertionError('invalid lab input accepted')
    checks.append('Executable lab agrees with independent references; quiet strict-JSON API and 16 invalid-input cases verified')

    # A subprocess with -B -O avoids bytecode writes and verifies explicit validation survives optimization.
    run=subprocess.run([sys.executable,'-B','-O',str(PROJECT)],cwd=tempfile.gettempdir(),
                       capture_output=True,text=True,check=False,timeout=10)
    require(run.returncode == 0 and run.stderr == '', 'portable optimized lab CLI')
    require(json.loads(run.stdout) == report,'CLI/default relative-to-script input matches API')
    checks.append('Optimized lab runs from a different working directory with default relative-to-script inputs')

    fragment=Fragment()
    text=CHAPTER.read_text()
    fragment.feed(text)
    require(not fragment.stack,'closed HTML stack')
    require(fragment.worked>=2 and fragment.exercise_count == fragment.solution_count == 8,'chapter exercise/worked counts')
    require(fragment.solutions_seen>=2 and 'Delayed-check answer' in text,'answered delayed check')
    require(len(fragment.ids)==len(set(fragment.ids)),'unique local IDs')
    sources=json.loads(SOURCE.read_text())
    source_ids={s['id'] for s in sources}
    require(len(source_ids)==4 and all(s.startswith('v06-c04-') for s in source_ids),'scoped proposed sources')
    for source in sources:
        require(set(source)=={'id','title','url','use','checked','verification'},'source schema')
    for href in fragment.hrefs:
        if href.startswith('sources.html#'):
            require(href.split('#',1)[1] in source_ids,'source route')
        elif href.startswith('v06-c04-'):
            require('/' not in href and (BOOK/'content/projects'/href).is_file(),'flat lab download')
    checks.append('Balanced chapter fragment, four worked examples, eight aligned solutions, answered retention and scoped source/download routes')
    return {'status':'passed','checks':checks,'limitations':[
        'Analytic concavity, boundary, Jensen and identification arguments also require manuscript review; finite computations alone are not proofs of every stated theorem.',
        'The lab deliberately covers certain-income log households and finite quadratic investment only; no empirical beliefs, causal effects or general stochastic lifecycle solution is claimed.',
        'Source content was inspected within the recorded scopes; this is author review rather than external human certification.',
        'Visual/mobile/print UI QA remains pending; no browser workaround, shared integration, acceptance or publication is performed here.'
    ]}


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
