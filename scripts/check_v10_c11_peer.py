"""Separate c11 peer audit: exact certificates, event ledger and Gaussian integrals."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import combinations
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'content/projects'
REVIEWS=ROOT/'content/reviews'


def require(condition,message):
    if not condition:
        raise AssertionError(message)


def rational(x):
    return F(str(x))


class Audit:
    def __init__(self):
        self.comparisons=0;self.rejections=0;self.interventions=0;self.groups=[]
    def eq(self,actual,expected,label):
        self.comparisons+=1
        require(actual==expected,label+': '+repr(actual)+' != '+repr(expected))
    def true(self,condition,label):
        self.comparisons+=1
        require(condition,label)
    def near(self,actual,expected,label,tolerance=2e-10):
        self.comparisons+=1
        require(math.isfinite(float(actual)) and abs(float(actual)-float(expected))<=tolerance,label)


def solve(matrix,rhs):
    """Independent generic exact row reduction; unique consistent solutions only."""
    columns=len(matrix[0]);rows=len(matrix)
    a=[[rational(v) for v in row]+[rational(b)] for row,b in zip(matrix,rhs)]
    rank=0;pivots=[]
    for col in range(columns):
        candidates=[i for i in range(rank,rows) if a[i][col]]
        if not candidates:
            continue
        index=candidates[0];a[rank],a[index]=a[index],a[rank]
        factor=a[rank][col];a[rank]=[v/factor for v in a[rank]]
        for i in range(rows):
            if i!=rank:
                factor=a[i][col];a[i]=[x-factor*y for x,y in zip(a[i],a[rank])]
        pivots.append(col);rank+=1
    if rank<columns or any(not any(row[:-1]) and row[-1] for row in a):
        return None
    answer=[F(0)]*columns
    for i,col in enumerate(pivots):
        answer[col]=a[i][-1]
    return answer


def basic_laws(stock,forward):
    laws=set()
    for size in (1,2):
        for selected in combinations(range(len(stock)),size):
            solution=solve([[1]*size,[stock[i] for i in selected]],[1,forward])
            if solution is not None and min(solution)>=0:
                p=[F(0)]*len(stock)
                for i,v in zip(selected,solution):p[i]=v
                laws.add(tuple(p))
    return sorted(laws)


def cash_automaton(data,state):
    """Accrue on EVERY date interval, then process default-before-coupon events."""
    m=data['market'];c=data['contracts']['credit']
    times=list(map(rational,m['times']));discounts=list(map(rational,m['discounts']))
    notional,rate=rational(c['notional']),rational(c['premium_rate'])
    pending=F(0);alive=True;cash=[];annuity=F(0);protection=F(0)
    for date in range(1,len(times)):
        if alive:
            pending+=times[date]-times[date-1]
            if state['default_index']==date:
                cash.append((date,'accrued_premium',-notional*rate*pending))
                annuity+=discounts[date]*pending
                settlement=date+c['settlement_delay']
                receipt=notional*(1-rational(state['recovery']))*rational(state['protection_fraction'])
                cash.append((settlement,'protection',receipt))
                protection=discounts[settlement]*receipt
                pending=F(0);alive=False
            elif date in c['premium_indices']:
                cash.append((date,'scheduled_premium',-notional*rate*pending))
                annuity+=discounts[date]*pending;pending=F(0)
    cash.sort()
    net=sum((discounts[date]*value for date,kind,value in cash),F(0))
    return {'payments':cash,'annuity':annuity,'protection':protection,'net':net}


def evaluate(a,data,out,label):
    m=data['market'];c=data['contracts'];d=rational(m['discounts'][-1]);spot=rational(m['spot'])
    stock=[rational(x['stock_path'][-1]) for x in m['states']]
    vertices=basic_laws(stock,spot/d)
    a.eq([tuple(map(F,p)) for p in out['closed_pricing_vertices']],vertices,label+' exact constraint vertices')
    a.eq(list(map(F,out['strict_positive_baseline'])),[sum(v[i] for v in vertices)/len(vertices) for i in range(len(stock))],label+' positive baseline')
    a.true(all(F(x)>0 for x in out['strict_positive_baseline']),label+' all possible states retained')
    a.eq(F(out['forward']),spot/d,label+' forward')
    ledgers=[cash_automaton(data,state) for state in m['states']]
    payoffs={key:[] for key in ('call','up_out','terminal_only_up_out','asian','credit_net','stock')}
    for state,ledger in zip(m['states'],ledgers):
        path=list(map(rational,state['stock_path']));vanilla=max(path[-1]-rational(c['strike']),F(0))
        payoffs['call'].append(vanilla)
        payoffs['up_out'].append(vanilla if max(path[i] for i in c['monitor_indices'])<rational(c['barrier']) else F(0))
        payoffs['terminal_only_up_out'].append(vanilla if path[-1]<rational(c['barrier']) else F(0))
        avg=sum(path[i] for i in c['average_indices'])/len(c['average_indices'])
        payoffs['asian'].append(max(avg-rational(c['average_strike']),F(0)))
        payoffs['credit_net'].append(ledger['net']/d);payoffs['stock'].append(path[-1])
    for actual,ledger in zip(out['credit_state_ledgers'],ledgers):
        a.eq([(p['index'],p['kind'],F(p['cash'])) for p in actual['payments']],ledger['payments'],label+' event-by-event dated payments')
        for field,key in (('unit_annuity_pv','annuity'),('protection_pv','protection'),('net_pv','net')):
            a.eq(F(actual[field]),ledger[key],label+' cash oracle '+field)
        a.eq(F(actual['premium_pv']),rational(c['credit']['notional'])*rational(c['credit']['premium_rate'])*ledger['annuity'],label+' premium amount')
        a.true(ledger['annuity']>0,label+' denominator domain')
    for key,h in payoffs.items():
        actual=out['claims'][key]
        prices=[d*sum(p*x for p,x in zip(v,h)) for v in vertices]
        lo,hi=min(prices),max(prices)
        a.eq(list(map(F,actual['terminal_payoff'])),h,label+' independently reconstructed payoff '+key)
        a.eq(list(map(F,actual['closed_vertex_prices'])),prices,label+' extreme expectations '+key)
        a.eq((F(actual['lower']),F(actual['upper'])),(lo,hi),label+' bounds '+key)
        a.eq(actual['replicable'],lo==hi,label+' singleton classification '+key)
        a.eq(actual['endpoints_open'],lo!=hi,label+' endpoint qualification '+key)
        for which,target,sign in (('subhedge',lo,1),('superhedge',hi,-1)):
            hedge=actual[which];delta,terminal=F(hedge['stock_units']),F(hedge['terminal_cash'])
            values=[terminal+delta*x for x in stock]
            a.eq(list(map(F,hedge['terminal_values'])),values,label+' hedge cash vector')
            a.true(all(sign*(y-v)>=0 for y,v in zip(h,values)),label+' statewise hedge certificate')
            a.eq(F(hedge['initial_cash']),d*terminal,label+' bank funding')
            a.eq(F(hedge['cost']),spot*delta+d*terminal,label+' portfolio cost')
            a.eq(F(hedge['cost']),target,label+' primal-dual certificate')
            # Attainment under a feasible closed law plus hedge inequality certifies optimum.
            a.true(any(price==target for price in prices),label+' extremal-law witness')
    notional=rational(c['credit']['notional'])
    vertex_ratios=[sum(p*row['protection'] for p,row in zip(v,ledgers))/(notional*sum(p*row['annuity'] for p,row in zip(v,ledgers))) for v in vertices]
    ratios=out['fair_spread_bounds']
    a.eq(list(map(F,ratios['closed_vertex_spreads'])),vertex_ratios,label+' positive-denominator ratio vertices')
    a.eq((F(ratios['lower']),F(ratios['upper'])),(min(vertex_ratios),max(vertex_ratios)),label+' exact ratio bounds')
    a.eq(ratios['endpoints_open'],min(vertex_ratios)!=max(vertex_ratios),label+' ratio endpoints')
    for measure,quote in zip(data['measures'],out['quotes']):
        p=list(map(rational,measure['probabilities']))
        a.eq(list(map(F,quote['state_prices'])),[d*x for x in p],label+' positive state prices')
        for key,h in payoffs.items():
            a.eq(F(quote['prices'][key]),d*sum(x*y for x,y in zip(p,h)),label+' chosen-law price '+key)
        ann=sum(prob*row['annuity'] for prob,row in zip(p,ledgers));loss=sum(prob*row['protection'] for prob,row in zip(p,ledgers))
        for field,value in (('protection_pv',loss),('unit_annuity_pv',ann),('premium_pv',notional*rational(c['credit']['premium_rate'])*ann),('fair_spread',loss/(notional*ann))):
            a.eq(F(quote['credit'][field]),value,label+' quote cash '+field)
    for case,actual in zip(data['jump_cases'],out['jump_cases']):
        s,j,scale=(rational(case[k]) for k in ('spot','jump','scale'))
        expected={'before':s*s/scale,'after':(s+j)**2/scale,'delta_before':2*s/scale,
                  'stock_hedge_gain':2*s*j/scale,'claim_change':((s+j)**2-s*s)/scale,
                  'claim_minus_hedge':j*j/scale,'identity_jump_squared_over_scale':j*j/scale}
        for key,value in expected.items():a.eq(F(actual[key]),value,label+' exact jump '+key)
    return payoffs,ledgers,vertices


def simpson(f,left,right,n=8192):
    h=(right-left)/n
    return h/3*(f(left)+f(right)+4*math.fsum(f(left+i*h) for i in range(1,n,2))+2*math.fsum(f(left+i*h) for i in range(2,n,2)))


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.hrefs=[];self.worked=0;self.prompts=0;self.solutions=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        require(tag not in ('html','head','body','script','h1'),'static fragment only')
        if 'href' in attrs:self.hrefs.append(attrs['href'])
        if 'worked' in attrs.get('class','').split():self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():self.prompts+=1
            if any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.stack):self.solutions+=1
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,attrs))
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'unbalanced HTML '+tag);self.stack.pop()


def check():
    a=Audit();data=json.loads((ASSETS/'v10-c11-inputs.json').read_text());old=deepcopy(data)
    buffer=StringIO()
    with redirect_stdout(buffer),redirect_stderr(buffer):
        model=runpy.run_path(str(ASSETS/'v10-c11-analysis.py'));result=model['run'](data)
    a.eq(buffer.getvalue(),'','quiet import/run');a.eq(data,old,'input preserved')
    a.eq(result,json.loads((ASSETS/'v10-c11-output.json').read_text()),'regenerated complete output')
    json.dumps(result,allow_nan=False)
    payoff,ledgers,vertices=evaluate(a,data,result,'base')
    # A different oracle for this market: p4=p1+.1, p3=.9-2p1-p2.
    lattice=[]
    for i in range(19):
        for j in range(37-2*i):
            lattice.append((F(i,40),F(j,40),F(36-2*i-j,40),F(i+4,40)))
    a.eq(len(lattice),361,'independent exact calibrated simplex grid')
    for key,h in payoff.items():
        prices=[F(25,26)*sum(p*x for p,x in zip(v,h)) for v in lattice]
        a.eq((min(prices),max(prices)),(F(result['claims'][key]['lower']),F(result['claims'][key]['upper'])),'grid extrema '+key)
    a.groups.append('exact row-reduced probability laws, independent accrual automaton, affine hedge certificates and 361-law grid')

    variants=[]
    def change(label,modify):
        altered=deepcopy(data);modify(altered);variants.append((label,altered))
    change('barrier equality',lambda x:x['contracts'].update(barrier=120))
    change('terminal monitoring',lambda x:x['contracts'].update(monitor_indices=[4]))
    change('non-nested early-only observation',lambda x:x['contracts'].update(monitor_indices=[1]))
    change('new Asian fixing',lambda x:x['contracts'].update(average_indices=[1]))
    change('immediate protection',lambda x:x['contracts']['credit'].update(settlement_delay=0))
    change('seller full performance',lambda x:x['market']['states'][0].update(protection_fraction=1))
    change('seller zero performance',lambda x:x['market']['states'][0].update(protection_fraction=0))
    change('default on coupon',lambda x:x['market']['states'][0].update(default_index=2))
    change('zero coupon',lambda x:x['contracts']['credit'].update(premium_rate=0))
    change('notional scaling',lambda x:x['contracts']['credit'].update(notional=200))
    change('irregular dates',lambda x:x['market'].update(times=[0,'1/5','4/5','6/5',2]))
    change('zero and complete-loss jumps',lambda x:x.update(jump_cases=[{'id':'zero','spot':100,'jump':0,'scale':100},{'id':'wiped','spot':100,'jump':-100,'scale':100}]))
    def negative(x):
        x['market']['discounts']=[1,'101/100','51/50','103/100','25/24']
        x['measures']=[{'id':'negative_rates','probabilities':['3/10','2/5','1/10','1/5']}]
    change('negative rates',negative)
    def singleton(x):
        x['market']['states'].append({'id':'forward_state','stock_path':[100,101,102,103,104],
                                     'default_index':None,'recovery':1,'protection_fraction':1})
        for law in x['measures']:law['probabilities']=[str(F(p)/2) for p in law['probabilities']]+['1/2']
    change('singleton at forward',singleton)
    def split(x):
        states=[]
        for state in x['market']['states']:
            for suffix in ('_one','_two'):
                new=deepcopy(state);new['id']+=suffix;states.append(new)
        x['market']['states']=states
        for law in x['measures']:law['probabilities']=[str(F(p)/2) for p in law['probabilities'] for _ in (0,1)]
    change('eight duplicate-terminal states',split)
    def complete(x):
        x['market']['states']=[x['market']['states'][0],x['market']['states'][3]]
        x['measures']=[{'id':'complete','probabilities':['9/20','11/20']}]
    change('two-state complete market',complete)
    results={}
    for label,altered in variants:
        out=model['run'](altered);evaluate(a,altered,out,label);results[label]=out;a.interventions+=1
    a.eq(results['terminal monitoring']['claims']['up_out']['terminal_payoff'],result['claims']['terminal_only_up_out']['terminal_payoff'],'terminal monitoring correspondence')
    a.true(F(results['non-nested early-only observation']['quotes'][0]['prices']['up_out'])>F(result['quotes'][0]['prices']['terminal_only_up_out']),
           'no invalid nested ordering for early-only monitoring')
    a.eq(results['zero coupon']['fair_spread_bounds'],result['fair_spread_bounds'],'fair rate independent of quoted coupon')
    a.eq(results['notional scaling']['fair_spread_bounds'],result['fair_spread_bounds'],'fair rate independent of notional scale')
    a.true(all(v['replicable'] for v in results['two-state complete market']['claims'].values()),'two-state claims all replicated')
    a.eq(results['eight duplicate-terminal states']['fair_spread_bounds']['upper'],result['fair_spread_bounds']['upper'],'duplicate split preserves spread extreme')
    for key in payoff:
        a.eq(results['eight duplicate-terminal states']['claims'][key]['lower'],result['claims'][key]['lower'],'split-state lower-bound invariance')
        a.eq(results['eight duplicate-terminal states']['claims'][key]['upper'],result['claims'][key]['upper'],'split-state upper-bound invariance')
    a.eq(F(results['immediate protection']['quotes'][0]['credit']['protection_pv']),F(279250,10403),'exercise9 immediate loss PV')
    a.eq(F(results['immediate protection']['quotes'][0]['prices']['credit_net']),F(51629775,2299063),'exercise9 immediate net')
    a.eq(F(results['immediate protection']['quotes'][0]['credit']['fair_spread']),F(740571,4033790),'exercise9 immediate rate')
    a.eq(F(results['seller full performance']['quotes'][0]['credit']['protection_pv'])-F(result['quotes'][0]['credit']['protection_pv']),F(125,17),'exercise9 seller loss increment')
    a.eq(F(results['seller full performance']['quotes'][0]['credit']['fair_spread'])-F(result['quotes'][0]['credit']['fair_spread']),F(405717,8067580),'exercise9 seller rate increment')
    a.groups.append('sixteen financial and contractual interventions: monitoring, accrual collision, settlement, recovery, negative rates and market completeness')

    # All remaining worked and exercise arithmetic; proofs are audited in the peer record.
    stock=[F(60),F(100),F(140)];disc=F(25,26)
    probabilities=solve([[1,1,1],stock,[0,1,0]],[1,104,F(1,2)])
    a.eq(probabilities,[F(1,5),F(1,2),F(3,10)],'digital instrument selects measure')
    holdings=solve([[x,1,d] for x,d in zip(stock,[0,1,0])],[0,0,40])
    a.eq(holdings,[F(1,2),F(-30),F(-20)],'digital completes call replication')
    a.eq(holdings[0]*100+holdings[1]*disc+holdings[2]*F(25,52),F(150,13),'digital financed hedge cost')
    upper=[(140-x)/40 for x in stock]
    a.eq(upper,[F(2),F(1),F(0)],'repaired digital upper hedge')
    a.eq(F(7,2)*disc-F(100,40),F(45,52),'repaired exact upper endpoint')
    a.eq([x-y for x,y in zip(upper,[0,1,0])],[F(2),F(0),F(0)],'repaired endpoint arbitrage witness')
    for h,lower,upper,line_lo,line_hi in (([0,0,40],F(50,13),F(275,13),(1,-100),(F(1,2),-30)),
                                         ([0,10,30],F(150,13),F(825,52),(F(1,2),-40),(F(3,8),F(-45,2)))):
        extremes=basic_laws(stock,F(104));values=[disc*sum(p*y for p,y in zip(v,h)) for v in extremes]
        a.eq((min(values),max(values)),(lower,upper),'three-state exercise exact interval')
        for (delta,cash),value,sign in ((line_lo,lower,1),(line_hi,upper,-1)):
            a.eq(delta*100+disc*cash,value,'three-state extremal hedge cost')
            a.true(all(sign*(y-(delta*x+cash))>=0 for x,y in zip(stock,h)),'three-state hedge domination')
    for vy,expected_delta,expected_var in ((12,F(221,500),F(5184,625)),(-8,F(311,500),F(2304,625))):
        c1=20*F(11,20)-F(9,50)*vy;c2=F(6,25)*vy
        a.eq(c1/20,expected_delta,'factor minimum-variance delta')
        a.eq(c2*c2,expected_var,'orthogonal variance')
        option_units=F(vy,6);stock_units=F(11,20)-option_units*F(1,4)
        a.eq(20*stock_units+option_units*(20*F(1,4)-F(9,50)*6),c1,'two-instrument first driver')
        a.eq(option_units*F(6,25)*6,c2,'two-instrument second driver')
    a.eq(20*F(6,25)*6,F(144,5),'nonzero exposure determinant')
    for jump,truth,gamma in ((-20,F(56,5),12),(50,F(175,2),75)):
        residual=F((100+jump)**3-100**3,10000)-3*jump
        a.eq(residual,truth,'exact cubic jump residual')
        a.eq(F(3,100)*jump*jump,gamma,'cubic gamma approximation')
    a.eq(F(25,26)/F(50,51)*100,F(1275,13),'changed-trading conditional failure')
    a.eq((F(2,5)*5)**2,4,'retention orthogonal variance')
    a.eq(F(900,100),9,'retention quadratic jump')
    a.eq(F(6,100)/F(3,2),F(1,25),'retention fair spread')
    # Direct density integrals rather than a normal CDF for the constant tilt.
    for horizon,lam in ((1,0),(1,1),(4,F(1,2))):
        lam=float(lam);root=math.sqrt(horizon)
        def density(z):return math.exp(-z*z/2-lam*root*z-lam*lam*horizon/2)/math.sqrt(2*math.pi)
        a.near(simpson(density,-12,12),1,'tilted normal density normalization')
        a.near(simpson(lambda z:root*z*density(z),-12,12),-lam*horizon,'tilted factor mean')
        a.near(simpson(lambda z:horizon*z*z*density(z),-12,12),horizon+lam*lam*horizon*horizon,'tilted factor second moment')
        digital=simpson(density,0,12)
        a.near(digital,.5 if lam==0 else .15865525393145707,'factor digital direct integral')
        a.near(digital,simpson(density,0,12,4096),'digital quadrature refinement')
    a.groups.append('repaired digital interval and residual, all worked/exercise algebra, factor exposures, exact jumps and independent tilted-Gaussian quadrature')

    invalid=[]
    def bad(path,value):
        x=deepcopy(data);target=x
        for key in path[:-1]:target=target[key]
        target[path[-1]]=value;invalid.append(x)
    for value in (True,None,float('nan'),float('inf'),-float('inf'),10**1000,'1/0','1/1000000001','01','+1',' 1','1/01',1e-12):
        bad(('market','spot'),value)
    bad(('schema',),'wrong')
    bad(('market','times'),[0,1,1,2,3]);bad(('market','times'),[0,1])
    bad(('market','discounts'),[1,1,1,1,0]);bad(('market','discounts'),[2,1,1,1,1])
    for path,value in ((('market','states',0,'id'),'Bad Name'),(('market','states',0,'stock_path'),[99,90,80,70,60]),
                       (('market','states',0,'default_index'),True),(('market','states',0,'default_index'),0),
                       (('market','states',0,'recovery'),2),(('market','states',0,'protection_fraction'),-1),
                       (('market','states',2,'recovery'),0),(('contracts','barrier'),0),
                       (('contracts','monitor_indices'),[4,2]),(('contracts','monitor_indices'),[2,2]),
                       (('contracts','average_indices'),[]),(('contracts','average_indices'),[True]),
                       (('contracts','credit','premium_indices'),[2]),(('contracts','credit','notional'),0),
                       (('contracts','credit','premium_rate'),2),(('contracts','credit','settlement_delay'),2),
                       (('measures',0,'probabilities'),[0,'1/2','1/5','3/10']),
                       (('measures',0,'probabilities'),['1/4','1/4','1/4','1/4']),
                       (('measures',0,'probabilities'),['1/5','2/5','1/10','1/5']),
                       (('jump_cases',0,'jump'),-101),(('jump_cases',0,'scale'),0)):
        bad(path,value)
    x=deepcopy(data);x['contracts']['extra']=0;invalid.append(x)
    x=deepcopy(data);del x['jump_cases'];invalid.append(x)
    x=deepcopy(data);x['market']['states'][1]['id']=x['market']['states'][0]['id'];invalid.append(x)
    x=deepcopy(data);x['measures'][1]['id']=x['measures'][0]['id'];invalid.append(x)
    x=deepcopy(data);x['jump_cases'][1]['id']=x['jump_cases'][0]['id'];invalid.append(x)
    invalid.extend((None,[],True))
    for index,x in enumerate(invalid):
        try:model['run'](x)
        except ValueError:a.rejections+=1
        else:raise AssertionError('accepted invalid case '+str(index))
    a.groups.append('independent exact-domain, malformed rational, Boolean/nonfinite, calibration and date-order rejections')

    with tempfile.TemporaryDirectory(prefix='v10-c11-peer-') as temporary:
        dest=Path(temporary)
        for name in ('v10-c11-analysis.py','v10-c11-inputs.json'):shutil.copy2(ASSETS/name,dest/name)
        for optimized in (False,True):
            command=[sys.executable]+(['-O'] if optimized else [])
            explicit=subprocess.run(command+[str(dest/'v10-c11-analysis.py'),'--input',str(dest/'v10-c11-inputs.json'),'--output',str(dest/'result.json')],cwd=dest,capture_output=True,text=True,timeout=20)
            a.eq(explicit.returncode,0,'isolated explicit CLI status');a.eq((explicit.stdout,explicit.stderr),('',''),'explicit CLI quiet')
            a.eq(json.loads((dest/'result.json').read_text()),result,'explicit portable payload')
            default=subprocess.run(command+[str(dest/'v10-c11-analysis.py')],cwd=dest,capture_output=True,text=True,timeout=20)
            a.eq(default.returncode,0,'default portable CLI status');a.eq(default.stderr,'','default stderr')
            a.eq(json.loads(default.stdout),result,'default script-adjacent inputs')
            code="import contextlib,io,json,runpy; b=io.StringIO();\nwith contextlib.redirect_stdout(b),contextlib.redirect_stderr(b):\n m=runpy.run_path('v10-c11-analysis.py'); d=json.load(open('v10-c11-inputs.json')); old=json.dumps(d,sort_keys=True); r=m['run'](d)\nif b.getvalue() or old!=json.dumps(d,sort_keys=True):raise RuntimeError('noise/mutation')\nprint(json.dumps(r,allow_nan=False))"
            api=subprocess.run(command+['-c',code],cwd=dest,capture_output=True,text=True,timeout=20)
            a.eq(api.returncode,0,'portable quiet API status');a.eq(api.stderr,'','portable API stderr');a.eq(json.loads(api.stdout),result,'portable API result')
            for bad_json in ('{"schema":1,"schema":2}','{"schema":NaN}','{"schema":Infinity}','{"schema":-Infinity}','{'):
                (dest/'invalid.json').write_text(bad_json)
                failure=subprocess.run(command+[str(dest/'v10-c11-analysis.py'),'--input',str(dest/'invalid.json'),'--output',str(dest/'absent.json')],cwd=dest,capture_output=True,text=True,timeout=5)
                require(failure.returncode!=0 and not (dest/'absent.json').exists(),'malformed JSON accepted/wrote output')
                a.rejections+=1
    a.groups.append('isolated normal/optimized quiet API, explicit and default CLI, duplicate/nonfinite strict JSON rejection')

    chapter=(ROOT/'content/chapters/v10-c11.html').read_text();fragment=Fragment();fragment.feed(chapter)
    a.eq(fragment.stack,[],'balanced static HTML');a.eq((fragment.worked,fragment.prompts,fragment.solutions),(5,12,12),'five cases and twelve full solutions')
    a.true('(0,45/52)' in chapter and '(2,0,0)' in chapter,'digital repair retained in final manuscript')
    for name in ('v10-c11-inputs.json','v10-c11-analysis.py','v10-c11-output.json','v10-c11-manifest.json','v10-c11-README.txt'):
        a.true(name in fragment.hrefs,'flat download '+name)
    proposals=json.loads((REVIEWS/'v10-c11-sources.json').read_text())['proposals']
    a.eq({h.split('#')[1] for h in fragment.hrefs if h.startswith('sources.html#')},{p['id'] for p in proposals},'source scope links')
    author=json.loads((REVIEWS/'v10-c11-author.json').read_text())
    require(len(author['reviewed_hashes'])==8,'author binds eight payloads')
    for entry in author['reviewed_hashes']:
        payload=(ROOT/entry['path']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(entry['bytes'],entry['sha256']),'author file binding')
    manifest=json.loads((REVIEWS/'v10-c11-peer-manifest.json').read_text())
    expected={entry['path'] for entry in author['reviewed_hashes']}|{'content/reviews/v10-c11-author.json'}
    a.eq({entry['path'] for entry in manifest['reviewed_hashes']},expected,'peer must bind all nine author files')
    a.eq(len(manifest['reviewed_hashes']),9,'nine distinct reviewed files')
    for entry in manifest['reviewed_hashes']:
        payload=(ROOT/entry['path']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(entry['bytes'],entry['sha256']),'peer author-payload binding')
    peer=REVIEWS/'v10-c11-peer.json'
    if peer.exists():
        record=json.loads(peer.read_text());a.eq(record['reviewed_hashes'],manifest['reviewed_hashes'],'review and manifest bindings agree')
        for entry in record['reviewer_artifacts']:
            payload=(ROOT/entry['path']).read_bytes()
            require((len(payload),sha256(payload).hexdigest())==(entry['bytes'],entry['sha256']),'stale peer reviewer artifact')
    a.groups.append('complete manuscript/solutions, repaired digital endpoint, scoped source links and all nine frozen author files')
    return {'chapter':'v10-c11','status':'passed','peer_comparisons':a.comparisons,
            'invalid_inputs_rejected':a.rejections,'financial_interventions':a.interventions,
            'independent_calibrated_grid_laws':len(lattice),'author_files_bound':9,
            'worked_examples_reviewed':5,'solved_exercises_reviewed':12,'groups':a.groups,
            'limits':'Separate machine-assisted peer review, not external human certification, empirical validation or a proof by numerical experiment.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
