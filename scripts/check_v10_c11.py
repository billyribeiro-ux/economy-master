"""Independent exact finite-market and contract audit for v10-c11."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import math
from pathlib import Path
import runpy
import shutil
from statistics import NormalDist
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'content/projects'


def require(condition,message):
    if not condition:
        raise AssertionError(message)


class Audit:
    def __init__(self):
        self.comparisons=0
        self.rejections=0
        self.groups=[]
    def eq(self,a,b,label):
        self.comparisons+=1
        require(a==b,f'{label}: {a!r} != {b!r}')
    def true(self,condition,label):
        self.comparisons+=1
        require(condition,label)
    def near(self,a,b,label,tolerance=5e-9):
        self.comparisons+=1
        require(math.isfinite(float(a)) and abs(float(a)-float(b))<=tolerance,label)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack=[];self.ids=[];self.hrefs=[]
        self.worked=self.exercises=self.solutions=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        require(tag not in ('html','head','body','h1','script'),'static fragment required')
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.hrefs.append(a['href'])
        if 'worked' in a.get('class','').split():self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():self.exercises+=1
            if any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack):self.solutions+=1
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'unbalanced HTML '+tag)
        self.stack.pop()


def ledger_oracle(data):
    """Accrual-period walk, independently of model's scheduled-plus-accrued loops."""
    m=data['market'];c=data['contracts'];cr=c['credit']
    t=list(map(F,m['times']));d=list(map(F,m['discounts']))
    n=F(cr['notional']);rate=F(cr['premium_rate'])
    rows=[]
    for row in m['states']:
        tau=row['default_index'];last=0;annuity=F(0);cash=[]
        for end in cr['premium_indices']:
            if tau is not None and tau<=end:
                amount=t[tau]-t[last]
                annuity+=amount*d[tau]
                cash.append((tau,'accrued_premium',-n*rate*amount))
                break
            amount=t[end]-t[last]
            annuity+=amount*d[end]
            cash.append((end,'scheduled_premium',-n*rate*amount))
            last=end
        protection=F(0)
        if tau is not None:
            k=tau+cr['settlement_delay']
            amount=n*(1-F(row['recovery']))*F(row['protection_fraction'])
            protection=amount*d[k]
            cash.append((k,'protection',amount))
        cash.sort()
        pv=sum(d[k]*amount for k,kind,amount in cash)
        rows.append({'annuity':annuity,'protection':protection,'pv':pv,'cash':cash})
    return rows


def payoffs_oracle(data):
    c=data['contracts'];d=F(data['market']['discounts'][-1]);out={k:[] for k in ('call','up_out','terminal_only_up_out','asian','credit_net','stock')}
    ledgers=ledger_oracle(data)
    for row,ledger in zip(data['market']['states'],ledgers):
        path=list(map(F,row['stock_path']));s=path[-1]
        call=max(s-F(c['strike']),F(0))
        out['call'].append(call)
        out['up_out'].append(call*int(max(path[k] for k in c['monitor_indices'])<F(c['barrier'])))
        out['terminal_only_up_out'].append(call*int(s<F(c['barrier'])))
        out['asian'].append(max(sum(path[k] for k in c['average_indices'])/len(c['average_indices'])-F(c['average_strike']),F(0)))
        out['credit_net'].append(ledger['pv']/d)
        out['stock'].append(s)
    return out,ledgers


def verify_economics(a,data,out,label):
    d=F(data['market']['discounts'][-1]);spot=F(data['market']['spot'])
    stock=[F(r['stock_path'][-1]) for r in data['market']['states']]
    payoff,ledgers=payoffs_oracle(data)
    for name,h in payoff.items():
        row=out['claims'][name]
        a.eq(list(map(F,row['terminal_payoff'])),h,label+' '+name+' payoff')
        low,high=F(row['lower']),F(row['upper'])
        a.eq(row['replicable'],low==high,label+' replication flag')
        a.eq(row['endpoints_open'],low!=high,label+' endpoint flag')
        for which,inequality in [('subhedge',lambda x,y:x<=y),('superhedge',lambda x,y:x>=y)]:
            hedge=row[which];delta=F(hedge['stock_units']);cash=F(hedge['terminal_cash'])
            values=[cash+delta*s for s in stock]
            a.eq(list(map(F,hedge['terminal_values'])),values,label+' affine holdings')
            a.true(all(inequality(x,y) for x,y in zip(values,h)),label+' hedge feasible')
            a.eq(F(hedge['initial_cash']),d*cash,label+' cash financing')
            a.eq(F(hedge['cost']),d*cash+delta*spot,label+' cost')
            a.eq(F(hedge['cost']),low if which=='subhedge' else high,label+' optimum stated')
    for obs,want in zip(out['credit_state_ledgers'],ledgers):
        a.eq(F(obs['unit_annuity_pv']),want['annuity'],label+' accrual walk')
        a.eq(F(obs['protection_pv']),want['protection'],label+' protection date')
        a.eq(F(obs['net_pv']),want['pv'],label+' discounted signed payments')
        a.eq(sorted((x['index'],x['kind'],F(x['cash'])) for x in obs['payments']),want['cash'],label+' all cash entries')
    for source,quote in zip(data['measures'],out['quotes']):
        p=list(map(F,source['probabilities']))
        a.eq(sum(p),F(1),label+' probability mass')
        a.eq(sum(q*s for q,s in zip(p,stock)),spot/d,label+' stock calibration')
        a.eq(list(map(F,quote['state_prices'])),[d*q for q in p],label+' state prices')
        for name,h in payoff.items():
            value=d*sum(q*x for q,x in zip(p,h))
            a.eq(F(quote['prices'][name]),value,label+' chosen-measure price')
            lo,hi=F(out['claims'][name]['lower']),F(out['claims'][name]['upper'])
            a.true((lo<value<hi) if lo!=hi else value==lo,label+' strict equivalent-law bounds')
        prot=sum(q*r['protection'] for q,r in zip(p,ledgers));ann=sum(q*r['annuity'] for q,r in zip(p,ledgers))
        a.eq(F(quote['credit']['protection_pv']),prot,label+' protection expectation')
        a.eq(F(quote['credit']['unit_annuity_pv']),ann,label+' annuity expectation')
        a.eq(F(quote['credit']['fair_spread']),prot/(F(data['contracts']['credit']['notional'])*ann),label+' zero-upfront spread')
    return payoff,ledgers


def check():
    a=Audit();raw=json.loads((ASSETS/'v10-c11-inputs.json').read_text());before=deepcopy(raw)
    capture=StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        model=runpy.run_path(str(ASSETS/'v10-c11-analysis.py'))
        out=model['run'](raw)
    run=model['run']
    a.eq(capture.getvalue(),'','quiet API/import')
    a.eq(raw,before,'nonmutating API')
    a.eq(json.loads(json.dumps(out,allow_nan=False)),out,'strict JSON-safe output')
    a.eq(out,json.loads((ASSETS/'v10-c11-output.json').read_text()),'complete saved output')
    payoffs,ledgers=verify_economics(a,raw,out,'supplied market')
    a.groups.append('quiet strict API, signed dated cash ledger and self-financing affine-hedge oracle')

    # Independent integer-simplex grid contains all three true vertices (denominator20).
    # Its extrema are checked against the analytic triangle as well as model output.
    grid=[]
    for n0 in range(21):
        for n1 in range(21-n0):
            for n2 in range(21-n0-n1):
                n3=20-n0-n1-n2
                if 60*n0+100*n1+100*n2+140*n3==104*20:
                    grid.append([F(n,20) for n in (n0,n1,n2,n3)])
    expected_vertices=[[F(0),F(0),F(9,10),F(1,10)], [F(0),F(9,10),F(0),F(1,10)], [F(9,20),F(0),F(0),F(11,20)]]
    a.eq([[F(x) for x in p] for p in out['closed_pricing_vertices']],expected_vertices,'closed laws independent triangle')
    baseline=list(map(F,out['strict_positive_baseline']))
    a.eq(baseline,[F(3,20),F(3,10),F(3,10),F(1,4)],'strict baseline')
    for name,h in payoffs.items():
        values=[F(25,26)*sum(p*x for p,x in zip(q,h)) for q in grid]
        analytical=[F(25,26)*(9*h[2]+h[3])/10,F(25,26)*(9*h[1]+h[3])/10,F(25,26)*(9*h[0]+11*h[3])/20]
        a.eq((min(values),max(values)),(min(analytical),max(analytical)),'grid contains exact extrema '+name)
        a.eq((F(out['claims'][name]['lower']),F(out['claims'][name]['upper'])),(min(values),max(values)),'independent grid bounds '+name)
        vals=[F(25,26)*sum(q*x for q,x in zip(p,h)) for p in expected_vertices]
        a.eq(list(map(F,out['claims'][name]['closed_vertex_prices'])),vals,'all vertex price ordering '+name)
    ratios=[sum(p*r['protection'] for p,r in zip(q,ledgers))/(100*sum(p*r['annuity'] for p,r in zip(q,ledgers))) for q in grid]
    a.eq((F(out['fair_spread_bounds']['lower']),F(out['fair_spread_bounds']['upper'])),(min(ratios),max(ratios)),'independent ratio bounds')
    a.eq(max(ratios),F(47277,165362),'spread upper anchor')
    a.true(out['fair_spread_bounds']['endpoints_open'],'nonconstant ratio endpoints open')
    # Endpoint arbitrages and all 3-state worked/exercise costs are independent algebra.
    d=F(25,26);stocks=[60,100,140]
    for h,sub,sup,lo,hi in [([0,0,40],(-100,F(1)),(-30,F(1,2)),F(50,13),F(275,13)),([0,10,30],(-40,F(1,2)),(-F(45,2),F(3,8)),F(150,13),F(825,52))]:
        sl=[sub[0]+sub[1]*s for s in stocks];su=[sup[0]+sup[1]*s for s in stocks]
        a.eq(sub[0]*d+sub[1]*100,lo,'3-state lower cost')
        a.eq(sup[0]*d+sup[1]*100,hi,'3-state upper cost')
        a.true(all(x>=y for x,y in zip(h,sl)) and h!=sl,'lower endpoint free gain')
        a.true(all(x>=y for x,y in zip(su,h)) and h!=su,'upper endpoint free gain')
    a.eq([F(1,2)*s-30-20*e for s,e in zip(stocks,[0,1,0])],[0,0,40],'digital completion replication')
    a.eq(50-30*d-20*F(25,52),F(150,13),'digital funded cost')
    a.eq(F(7,2)*d-F(100,40),F(45,52),'stock-calibrated digital true upper bound')
    a.eq([F(140-s,40)-e for s,e in zip(stocks,[0,1,0])],[2,0,0],'true digital upper endpoint arbitrage')
    a.groups.append('integer-simplex exhaustive oracle, analytical triangle, exact bounds and endpoint arbitrage portfolios')

    # Economic interventions verify precise invariants and changed cash terms.
    x=deepcopy(raw);x['contracts']['strike']=0;o=run(x)
    a.eq(o['claims']['call']['terminal_payoff'],o['claims']['stock']['terminal_payoff'],'zero strike equals stock')
    a.eq((o['claims']['call']['lower'],o['claims']['call']['upper']),('100','100'),'affine unique price')
    a.true(not o['claims']['call']['endpoints_open'],'replicated singleton included')
    x=deepcopy(raw);x['contracts']['barrier']=10000;o=run(x)
    a.eq(o['claims']['up_out'],o['claims']['call'],'no knockout equals call including holdings')
    x['contracts']['barrier']='1/1000000';o=run(x)
    a.eq((o['claims']['up_out']['lower'],o['claims']['up_out']['upper']),('0','0'),'certain knockout singleton')
    x=deepcopy(raw);x['contracts']['monitor_indices']=[4];o=run(x)
    a.eq(o['claims']['up_out'],out['claims']['terminal_only_up_out'],'remove intermediate observation')
    a.true(all(F(q['prices']['up_out'])>=F(p['prices']['up_out']) for q,p in zip(o['quotes'],out['quotes'])),'same-law barrier ordering')
    x=deepcopy(raw);x['contracts']['barrier']=120;o=run(x)
    a.eq(o['claims']['up_out']['terminal_payoff'],['0','10','0','0'],'barrier equality knocks out')
    x=deepcopy(raw);x['contracts']['average_indices']=[4];x['contracts']['average_strike']=90;o=run(x)
    a.eq(o['claims']['asian'],o['claims']['call'],'single terminal fixing call')
    a.eq(out['quotes'][0]['prices']['call'],out['quotes'][1]['prices']['call'],'terminal calibration invariance')
    a.true(out['quotes'][0]['prices']['up_out']!=out['quotes'][1]['prices']['up_out'],'history nonidentification')
    x=deepcopy(raw);x['contracts']['credit']['settlement_delay']=0;o=run(x)
    _,rows=verify_economics(a,x,o,'immediate protection')
    p=list(map(F,x['measures'][0]['probabilities']));prot=sum(q*r['protection'] for q,r in zip(p,rows))
    a.eq(prot,F(279250,10403),'immediate protection anchor')
    a.eq(F(o['quotes'][0]['credit']['fair_spread']),F(740571,4033790),'immediate fair spread anchor')
    a.eq(o['quotes'][0]['credit']['unit_annuity_pv'],out['quotes'][0]['credit']['unit_annuity_pv'],'delay leaves accrual unchanged')
    x=deepcopy(raw);x['market']['states'][0]['protection_fraction']=1;o=run(x)
    a.eq(F(o['quotes'][0]['credit']['protection_pv'])-F(out['quotes'][0]['credit']['protection_pv']),F(125,17),'protection haircut intervention')
    a.eq(F(o['quotes'][0]['credit']['fair_spread'])-F(out['quotes'][0]['credit']['fair_spread']),F(405717,8067580),'spread increment anchor')
    x=deepcopy(raw);x['market']['states'][0]['default_index']=2;o=run(x)
    first=o['credit_state_ledgers'][0]
    a.eq([(z['kind'],z['cash']) for z in first['payments']],[('accrued_premium','-3'),('protection','75/2')],'default on coupon: full accrual once')
    a.eq(F(first['unit_annuity_pv']),F(50,51),'default-coupon annuity exact')
    x=deepcopy(raw)
    for row in x['market']['states']:row['recovery']=1
    o=run(x)
    a.eq((o['fair_spread_bounds']['lower'],o['fair_spread_bounds']['upper'],o['fair_spread_bounds']['endpoints_open']),('0','0',False),'zero loss ratio singleton')
    x=deepcopy(raw);x['contracts']['credit']['premium_rate']=0;o=run(x)
    a.true(all(z['premium_pv']=='0' for z in o['credit_state_ledgers']),'zero premium cash')
    a.eq([q['credit']['fair_spread'] for q in o['quotes']],[q['credit']['fair_spread'] for q in out['quotes']],'par spread independent of quoted coupon')
    a.groups.append('contract interventions: monitoring, barrier equality, Asian fixings, coupon/default collision, settlement, recovery and protection haircut')

    # Valid domain stress cases: complete binomial, duplicated states, at-forward
    # singletons, negative rates and maximum date count; all preserve exact oracles.
    x=deepcopy(raw);x['market']['states']=[x['market']['states'][0],x['market']['states'][3]];x['measures']=[{'id':'two','probabilities':['9/20','11/20']}];o=run(x)
    verify_economics(a,x,o,'complete two-state market')
    a.true(all(z['replicable'] and not z['endpoints_open'] for z in o['claims'].values()),'every 2-state payoff replicates')
    x=deepcopy(raw);x['market']['discounts'][-1]=1;x['measures']=[{'id':'forward_middle','probabilities':['1/5','3/10','3/10','1/5']}];o=run(x)
    verify_economics(a,x,o,'at-forward repeated states')
    a.true(['0','1','0','0'] in o['closed_pricing_vertices'] and ['0','0','1','0'] in o['closed_pricing_vertices'],'separate equal-stock singleton laws')
    x=deepcopy(raw);x['market']['discounts']=[1,'21/20','11/10','6/5','5/4'];x['measures']=[{'id':'negative_rates','probabilities':['3/5','1/5','1/10','1/10']}];o=run(x)
    verify_economics(a,x,o,'negative discount-curve rates')
    y=deepcopy(x);y['contracts']['credit']['settlement_delay']=0;oy=run(y)
    a.true(F(o['quotes'][0]['credit']['protection_pv'])>F(oy['quotes'][0]['credit']['protection_pv']),'delay increases PV on increasing discount curve')
    x=deepcopy(raw);x['market']['states']=[]
    for row in raw['market']['states']:
        for suffix in ('a','b'):
            r=deepcopy(row);r['id']+='_'+suffix;x['market']['states'].append(r)
    for q in x['measures']:q['probabilities']=[str(F(p)/2) for p in q['probabilities'] for unused in range(2)]
    o=run(x)
    a.eq([q['prices'] for q in o['quotes']],[q['prices'] for q in out['quotes']],'splitting states preserves chosen prices')
    a.eq([(q['lower'],q['upper']) for q in o['claims'].values()],[(q['lower'],q['upper']) for q in out['claims'].values()],'eight-state duplicate bounds')
    x=deepcopy(raw);old=x['market'];old['times']=[str(F(i,4)) for i in range(9)]
    old['discounts']=[1,1,'100/101',1,'50/51',1,'100/103',1,'25/26']
    for r in old['states']:
        p=list(map(F,r['stock_path']));r['stock_path']=[str(z) for i in range(4) for z in (p[i],(p[i]+p[i+1])/2)]+[str(p[-1])]
        if r['default_index'] is not None:r['default_index']*=2
    x['contracts']['monitor_indices']=[4,8];x['contracts']['average_indices']=[4,8]
    x['contracts']['credit']['premium_indices']=[4,8];x['contracts']['credit']['settlement_delay']=2;o=run(x)
    a.eq([q['prices'] for q in o['quotes']],[q['prices'] for q in out['quotes']],'nine-date observation expansion invariance')
    x=deepcopy(raw);x['jump_cases']=[{'id':'zero','spot':0,'jump':0,'scale':'1/1000000'},{'id':'to_zero','spot':10000,'jump':-10000,'scale':10000}];o=run(x)
    a.eq([z['claim_minus_hedge'] for z in o['jump_cases']],['0','10000'],'zero jump/spot and maximal permitted jump')
    a.groups.append('valid finite-domain boundaries: complete market, forward singletons, eight states, nine dates, negative rates and jump-to-zero')

    # Independent algebra for continuous-model worked examples and prompts.
    for vy,delta,variance,eta,stockholding in [(F(12),F(221,500),F(5184,625),F(2),F(1,20)),(-F(8),F(311,500),F(2304,625),-F(4,3),F(53,60))]:
        w1=20*F(11,20)-F(9,50)*vy;w2=F(6,25)*vy
        a.eq(w1/20,delta,'factor minimum-variance delta')
        a.eq(w2*w2,variance,'factor orthogonal variance')
        a.eq(vy/6,eta,'second instrument amount')
        a.eq(F(11,20)-eta/4,stockholding,'funded two-instrument stock')
    a.eq(20*F(3,10)*F(4,5)*6,F(144,5),'local exposure determinant')
    a.near(NormalDist().cdf(-1),.15865525393145707,'constant tilt digital probability',1e-15)
    for j,residual,approx in [(-20,F(56,5),F(12)),(50,F(175,2),F(75))]:
        exact=(F(100+j)**3-F(100)**3)/10000-3*j
        a.eq(exact,residual,'cubic jump exact remainder')
        a.eq(F(3,100)*j*j,approx,'gamma approximation distinguished')
    for source,row in zip(raw['jump_cases'],out['jump_cases']):
        s=F(source['spot']);j=F(source['jump']);scale=F(source['scale'])
        a.eq(F(row['claim_change']),((s+j)**2-s*s)/scale,'quadratic direct payoff difference')
        a.eq(F(row['claim_minus_hedge']),j*j/scale,'quadratic identity')
    a.eq(F(51,52)*100,F(1275,13),'conditional node calibration failure')
    a.groups.append('worked and exercise algebra: independent-driver exposures, constant normal tilt, jumps and conditional-martingale failure')

    invalid=[]
    def bad(path,value,label):
        x=deepcopy(raw);p=x
        for key in path[:-1]:p=p[key]
        p[path[-1]]=value
        invalid.append((label,x))
    invalid.extend([('null',None),('list root',[]),('empty root',{})])
    x=deepcopy(raw);x['extra']=0;invalid.append(('extra root key',x))
    x=deepcopy(raw);del x['market']['spot'];invalid.append(('missing field',x))
    for v in (True,None,float('nan'),float('inf'),float('-inf'),1e-100,10**100,'NaN','1/0','1/10000000000',' 100','+100','01','1.0','x'*30,10001,-1):bad(['market','spot'],v,'numeric/domain')
    for path,value in [(['schema'],'wrong'),(['market','times'],[0,0]),(['market','times'],[1,2]),(['market','times'],[0,11]),(['market','times'],[0]),(['market','times'],list(range(10))),(['market','discounts'],[1,1]),(['market','discounts',0],2),(['market','discounts',1],0),(['market','discounts',1],11),(['market','states'],[]),(['market','states'],raw['market']['states']*3),(['market','states',0,'stock_path'],[100]),(['market','states',0,'stock_path',0],99),(['market','states',0,'stock_path',1],-1),(['market','states',0,'id'],'UPPER'),(['market','states',1,'id'],'decline'),(['market','states',0,'default_index'],True),(['market','states',0,'default_index'],0),(['market','states',0,'default_index'],5),(['market','states',0,'recovery'],2),(['market','states',0,'protection_fraction'],-1),(['market','states',2,'recovery'],0),(['market','states',2,'protection_fraction'],0),(['contracts','monitor_indices'],[]),(['contracts','monitor_indices'],[4,2]),(['contracts','monitor_indices'],[2,2]),(['contracts','monitor_indices'],[0]),(['contracts','average_indices'],[True]),(['contracts','barrier'],0),(['contracts','strike'],-1),(['contracts','average_strike'],10001),(['contracts','credit','notional'],0),(['contracts','credit','premium_rate'],2),(['contracts','credit','premium_indices'],[2]),(['contracts','credit','settlement_delay'],True),(['contracts','credit','settlement_delay'],4),(['contracts','credit','settlement_delay'],2),(['measures'],[]),(['measures',0,'probabilities'],[0,'1/2','1/10','2/5']),(['measures',0,'probabilities'],['1/5','2/5','1/10','1/5']),(['measures',0,'probabilities'],['1/4','1/4','1/4','1/4']),(['measures',0,'probabilities'],[1]),(['measures',1,'id'],'quiet_weight'),(['jump_cases'],[]),(['jump_cases',0,'jump'],-101),(['jump_cases',0,'scale'],0),(['jump_cases',1,'id'],'down20')]:bad(path,value,'shape/financial invariant')
    for label,x in invalid:
        before=deepcopy(x)
        try:run(x)
        except (ValueError,TypeError):a.rejections+=1
        else:raise AssertionError('invalid accepted: '+label)
    a.groups.append('explicit malformed, bool/nonfinite, bounded-rational, timing, identification and calibration rejections')

    # Portable CLI does not require repo helpers; input errors cannot create outputs.
    with tempfile.TemporaryDirectory(prefix='v10-c11-check-') as td:
        td=Path(td);portable=td/'portable';portable.mkdir();cwd=td/'elsewhere';cwd.mkdir()
        for filename in ('v10-c11-analysis.py','v10-c11-inputs.json'):shutil.copy2(ASSETS/filename,portable/filename)
        script=portable/'v10-c11-analysis.py'
        for optimized in (False,True):
            prefix=[sys.executable]+(['-O'] if optimized else [])+[str(script)]
            p=subprocess.run(prefix,cwd=cwd,capture_output=True,text=True)
            a.eq((p.returncode,p.stderr),(0,''),'portable default CLI status')
            a.eq(json.loads(p.stdout),out,'portable default stdout')
            dest=td/('explicit-O.json' if optimized else 'explicit.json')
            p=subprocess.run(prefix+['--input',str(portable/'v10-c11-inputs.json'),'--output',str(dest)],cwd=cwd,capture_output=True,text=True)
            a.eq((p.returncode,p.stdout,p.stderr),(0,'',''),'portable explicit quiet output')
            a.eq(json.loads(dest.read_text()),out,'portable explicit result')
            for k,text in enumerate(['{"schema":"v10-c11-input-1","schema":"duplicate"}',json.dumps(raw).replace('"spot": 100','"spot": NaN',1),json.dumps(invalid[-1][1])]):
                source=td/f'bad-{optimized}-{k}.json';source.write_text(text);target=td/f'absent-{optimized}-{k}.json'
                p=subprocess.run(prefix+['--input',str(source),'--output',str(target)],cwd=cwd,capture_output=True,text=True)
                a.eq(p.returncode,2,'portable rejects invalid JSON/domain')
                a.eq(p.stdout,'','invalid stdout quiet')
                a.true(p.stderr.startswith('invalid input: '),'invalid diagnostic')
                a.true(not target.exists(),'invalid creates no output')
    a.groups.append('isolated normal/-O portable default/stdout and explicit/output CLI; duplicate/nonfinite/domain JSON rejection')

    manuscript=(ROOT/'content/chapters/v10-c11.html').read_text();fragment=Fragment();fragment.feed(manuscript)
    a.eq(fragment.stack,[],'balanced HTML')
    a.eq((fragment.worked,fragment.exercises,fragment.solutions),(5,12,12),'full graduate instructional package')
    a.eq(len(fragment.ids),len(set(fragment.ids)),'unique anchors')
    for filename in ('inputs.json','analysis.py','output.json','manifest.json','README.txt'):
        a.true('v10-c11-'+filename in fragment.hrefs,'flat asset link '+filename)
    a.true(all(not h.startswith('projects/') for h in fragment.hrefs),'no misresolved asset prefixes')
    a.true('Teach-back' in manuscript and 'delayed retention' in manuscript,'answered teaching and retention')
    # Display checks bind independently computed rounded answers to manuscript prose.
    for exact,display in [(F(3001950,135239),'22.197369'),(F(47277,165362),'.285900025'),(F(279250,10403),'26.843218302'),(F(51629775,2299063),'22.456876997'),(F(740571,4033790),'.183591858'),(F(405717,8067580),'.050289802')]:
        a.true(display in manuscript,'display present '+display)
        a.near(exact,float(display),'display arithmetic '+display,5.1e-7 if display=='22.197369' else 5.1e-10)
    sources=json.loads((ROOT/'content/reviews/v10-c11-sources.json').read_text())
    a.eq({x['id'] for x in sources['proposals']},{h.split('#')[1] for h in fragment.hrefs if h.startswith('sources.html#')},'scoped source proposals cover citations')
    for row in sources['proposals']:
        a.true(all(row.get(k) for k in ('title','url','use','checked','verification')),'source metadata')
    manifest=json.loads((ASSETS/'v10-c11-manifest.json').read_text())
    a.eq({x['file'] for x in manifest['files']},{'v10-c11-'+suffix for suffix in ('inputs.json','analysis.py','output.json','README.txt')},'four payload manifest')
    for row in manifest['files']:
        blob=(ASSETS/row['file']).read_bytes()
        a.eq((len(blob),sha256(blob).hexdigest()),(row['bytes'],row['sha256']),'manifest digest')
    author=json.loads((ROOT/'content/reviews/v10-c11-author.json').read_text())
    expected={'content/chapters/v10-c11.html','scripts/check_v10_c11.py','content/reviews/v10-c11-sources.json'}|{'content/projects/v10-c11-'+suffix for suffix in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')}
    a.eq({x['path'] for x in author['reviewed_hashes']},expected,'eight nonself author bindings')
    a.eq(len(author['reviewed_hashes']),8,'exact binding count')
    for row in author['reviewed_hashes']:
        blob=(ROOT/row['path']).read_bytes()
        a.eq((len(blob),sha256(blob).hexdigest()),(row['bytes'],row['sha256']),'author digest')
    a.groups.append('static manuscript, all 12 prompts/solutions, five worked cases, numerical displays, three scoped sources and exact payload hashes')
    return {'status':'passed','independent_comparisons':a.comparisons,'invalid_inputs_rejected':a.rejections,'worked_examples':5,'solved_exercises':12,'author_payload_hashes_verified':8,'groups':a.groups,
            'limits':'Author checks, not separate peer/human certification, empirical validation or browser/print QA. Exact finite-state bounds depend on explicitly restricted trading rights.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
