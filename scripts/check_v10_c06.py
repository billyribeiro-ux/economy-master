"""Independent finite-state valuation, cash-ledger and portability audit for c06."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from functools import lru_cache
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import product
import json
from math import comb
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'content/projects'


def require(condition, label):
    if not condition:
        raise AssertionError(label)


class Audit:
    def __init__(self):
        self.comparisons = self.rejections = 0

    def eq(self, actual, expected, label):
        self.comparisons += 1
        if isinstance(expected, F):
            actual = F(actual)
        require(actual == expected, f'{label}: {actual!r} != {expected!r}')


def intrinsic(s, k, kind):
    return max(F(0), s-k if kind == 'call' else k-s)


def oracle_values(s, k, u, d, r, n, kind, american):
    """European terminal sums or all feasible policy values, not author recursion."""
    q = (r-d)/(u-d)

    @lru_cache(None)
    def policies(t, j):
        st = s*u**j*d**(t-j)
        immediate = intrinsic(st, k, kind)
        if t == n:
            return frozenset((immediate,))
        values = {immediate}
        # Every adapted policy can decide independently at the two successors.
        # Retain all possible values, including suboptimal policies, before max.
        for lo, hi in product(policies(t+1, j), policies(t+1, j+1)):
            values.add(((1-q)*lo+q*hi)/r)
        return frozenset(values)

    def value(t, j):
        st = s*u**j*d**(t-j)
        if american:
            require(n <= 3, 'exhaustive policy oracle is deliberately bounded')
            return max(policies(t, j))
        m = n-t
        return sum((F(comb(m, h))*q**h*(1-q)**(m-h)*
                    intrinsic(st*u**h*d**(m-h), k, kind)/r**m
                    for h in range(m+1)), F(0))
    return [[value(t, j) for j in range(t+1)] for t in range(n+1)]


def audit_tree(a, report, params, n):
    s,k,u,d,r = (F(params[x]) for x in ('spot','strike','up','down','gross_rate'))
    q = (r-d)/(u-d)
    a.eq(report['q_up'], q, 'pricing branch weight')
    for t, row in enumerate(report['stock']):
        for j, actual in enumerate(row):
            a.eq(actual,s*u**j*d**(t-j),'stock node')
    a.eq(len(report['stock']), n+1, 'date count')
    for kind, style in product(('call','put'),('european','american_grid')):
        expected = oracle_values(s,k,u,d,r,n,kind,style=='american_grid')
        rows = report['contracts'][kind+'_'+style]
        a.eq(len(rows),n+1,'contract date count')
        for t, row in enumerate(rows):
            a.eq(len(row),t+1,'contract row size')
            for j, node in enumerate(row):
                st=s*u**j*d**(t-j); h=intrinsic(st,k,kind)
                a.eq(node['stock'],st,'contract stock')
                a.eq(node['intrinsic'],h,'intrinsic')
                a.eq(node['value'],expected[t][j],'all-policy or terminal value')
                if t==n:
                    a.eq(node['action'],'settle','terminal action')
                    continue
                lo,hi=expected[t+1][j],expected[t+1][j+1]
                delta=(hi-lo)/(st*(u-d))
                bank=(u*lo-d*hi)/(r*(u-d))
                cont=(q*hi+(1-q)*lo)/r
                a.eq(node['continuation'],cont,'next-date continuation')
                a.eq(node['continuation_delta'],delta,'linear-system shares')
                a.eq(node['continuation_bank'],bank,'linear-system bank')
                a.eq(node['exercise_value_less_continuation'],h-cont,'exercise advantage')
                a.eq(node['cash_above_continuation_cost'],expected[t][j]-cont,'writer surplus')
                a.eq(node['action'],'exercise' if style=='american_grid' and h>cont else 'continue','tie convention')
                for side,price,pay in (('down',st*d,lo),('up',st*u,hi)):
                    a.eq(delta*price+r*bank,pay,'state payoff replication')
                    a.eq(node[side+'_replication_residual'],F(0),'reported hedge residual')
    a.eq(report['european_parity_lhs'],s-k/r**n,'European parity observed')
    a.eq(report['european_parity_rhs'],s-k/r**n,'European parity target')
    euro=oracle_values(s,k,u,d,r,n,'put',False)[0][0]
    amer=oracle_values(s,k,u,d,r,n,'put',True)[0][0]
    a.eq(report['american_put_premium'],amer-euro,'exercise premium')


def audit_paths(a, report, params):
    s,k,u,d,r,p,fee=(F(params[x]) for x in ('spot','strike','up','down','gross_rate','physical_up','interior_rebalance_fee'))
    n=params['steps'];q=(r-d)/(u-d)
    rows=oracle_values(s,k,u,d,r,n,'call',False)
    american={kind:oracle_values(s,k,u,d,r,n,kind,True) for kind in ('call','put')}
    def holding(t,j):
        st=s*u**j*d**(t-j); lo,hi=rows[t+1][j],rows[t+1][j+1]
        return (hi-lo)/(st*(u-d)),(u*lo-d*hi)/(r*(u-d))
    a.eq(len(report['paths']),2**n,'complete path enumeration')
    qsum=F(0); psum=F(0); ppay=F(0); stop_ev={'call':F(0),'put':F(0)}
    for bits,path in zip(product((0,1),repeat=n),report['paths']):
        ups=sum(bits); qp=q**ups*(1-q)**(n-ups); pp=p**ups*(1-p)**(n-ups)
        qsum+=qp;psum+=pp
        a.eq(path['path'],''.join('U' if bit else 'D' for bit in bits),'path order')
        a.eq(path['pricing_probability'],qp,'path Q probability')
        a.eq(path['physical_probability'],pp,'path P probability')
        delta,bank=holding(0,0);j=0;fee_terminal=F(0)
        a.eq(len(path['european_call_ledger']),n,'ledger dates')
        for t,(bit,entry) in enumerate(zip(bits,path['european_call_ledger']),1):
            j+=bit;st=s*u**j*d**(t-j);wealth=delta*st+bank*r
            for name,expected in (('date',t),('stock',st),('inherited_delta',delta),
                                  ('inherited_bank_after_interest',bank*r),
                                  ('pre_trade_wealth',wealth),('call_value',rows[t][j])):
                a.eq(entry[name],expected,'ledger '+name)
            a.eq(wealth,rows[t][j],'inherited replicating wealth')
            if t<n:
                nd,nb=holding(t,j); trade=(nd-delta)*st;cost=abs(trade)*fee
                fee_terminal+=cost*r**(n-t)
                for name,expected in (('new_delta',nd),('new_bank',nb),('stock_trade_cash',trade),
                                      ('bank_change',nb-bank*r),('external_cash_required',F(0)),
                                      ('intervention_fee',cost)):
                    a.eq(entry[name],expected,'interior '+name)
                a.eq(trade+nb-bank*r,F(0),'financed rebalance')
                delta,bank=nd,nb
            else:
                payoff=intrinsic(st,k,'call');ppay+=pp*payoff
                a.eq(entry['payoff'],payoff,'terminal call receipt')
                a.eq(entry['exact_hedge_error'],F(0),'ideal hedge error')
                a.eq(entry['fee_intervention_hedge_error'],-fee_terminal,'dated fee accumulation')
        for kind in ('call','put'):
            j=0
            for t in range(n+1):
                st=s*u**j*d**(t-j);h=intrinsic(st,k,kind)
                if t==n or h>(((1-q)*american[kind][t+1][j]+q*american[kind][t+1][j+1])/r):
                    expected={'date':t,'stock':str(st),'receipt':str(h),'discounted_receipt':str(h/r**t)}
                    a.eq(path['american_grid_optimal_stopping'][kind],expected,'feasible optimal stopping')
                    stop_ev[kind]+=qp*h/r**t
                    break
                j+=bits[t]
    a.eq(qsum,F(1),'Q probability normalization');a.eq(psum,F(1),'P probability normalization')
    a.eq(report['european_call_physical_expected_payoff'],ppay,'physical expected payoff')
    for kind in ('call','put'):
        a.eq(report['optimal_stopping_discounted_pricing_expectations'][kind],stop_ev[kind],'reported stopping expectation')
        a.eq(stop_ev[kind],american[kind][0][0],'optimal policy attains exhaustive maximum')


def audit_dividend(a, report, params):
    s,k,su,sd,cash,r=(F(params[x]) for x in ('spot','strike','ex_up','ex_down','cash_dividend','gross_rate'))
    # Solve stock TOTAL receipts and cash for two Arrow prices directly.
    au=(s-(sd+cash)/r)/(su-sd);ad=1/r-au
    a.eq(report['q_up_total_gain'],au*r,'dividend pricing probability')
    a.eq(report['dividend_pv'],cash/r,'dated dividend')
    a.eq(report['prepaid_terminal_stock'],s-cash/r,'prepaid ex-dividend share')
    for kind in ('call','put'):
        hi,lo=intrinsic(su,k,kind),intrinsic(sd,k,kind);v=au*hi+ad*lo
        delta=(hi-lo)/(su-sd);bank=(su*lo-sd*hi-cash*(hi-lo))/(r*(su-sd))
        h=intrinsic(s,k,kind);c=report['contracts'][kind]
        for name,expected in (('down_payoff',lo),('up_payoff',hi),('delta',delta),('bank',bank),
                              ('european_value',v),('immediate_exercise',h),('american_grid_value',max(h,v)),
                              ('down_hedge_residual',F(0)),('up_hedge_residual',F(0))):
            a.eq(c[name],expected,'dividend '+name)
        a.eq(c['action'],'exercise' if h>v else 'continue','dividend decision')
        a.eq(delta*(su+cash)+r*bank,hi,'stock dividend-funded up payoff')
        a.eq(delta*(sd+cash)+r*bank,lo,'stock dividend-funded down payoff')
    a.eq(report['european_parity_lhs'],s-(cash+k)/r,'dividend parity lhs')
    a.eq(report['european_parity_rhs'],s-(cash+k)/r,'dividend parity rhs')


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.worked=self.exercises=self.solutions=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        require(tag!='h1','no duplicate generated title')
        if 'id' in d:self.ids.append(d['id'])
        if tag=='aside' and 'worked' in d.get('class','').split():self.worked+=1
        if tag=='li' and self.stack and self.stack[-1][0]=='ol':
            if 'exercises' in self.stack[-1][1].get('class','').split():self.exercises+=1
            if any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack):self.solutions+=1
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append((tag,d))
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'balanced fragment '+tag);self.stack.pop()


def check():
    a=Audit();raw=json.loads((ASSETS/'v10-c06-inputs.json').read_text());original=deepcopy(raw)
    saved=json.loads((ASSETS/'v10-c06-output.json').read_text());capture=StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        model=runpy.run_path(str(ASSETS/'v10-c06-analysis.py'));run=model['run'];result=run(raw)
    a.eq(capture.getvalue(),'','quiet API');a.eq(raw,original,'nonmutating API');a.eq(result,saved,'reference regeneration')
    audit_tree(a,result['single_step'],raw['tree'],1)
    audit_tree(a,result['tree'],raw['tree'],raw['tree']['steps'])
    audit_tree(a,result['negative_rate_case'],raw['negative_rate_call'],1)
    audit_paths(a,result['path_reports'],raw['tree']);audit_dividend(a,result['dividend_case'],raw['dividend_call'])

    # Original independent numerical answers; proof/critique prompts audited in author record.
    s=F(62);su=F(80);sd=F(50);r=F(26,25);k=F(64)
    q=(r*s-sd)/(su-sd);cd=F(16)/(su-sd);cb=-cd*sd/r;pd=-F(14)/(su-sd);pb=(14-pd*sd)/r
    c=cd*s+cb;p=pd*s+pb
    for got,want in ((q,F(181,375)),(cd,F(8,15)),(cb,-F(1000,39)),(c,F(1448,195)),
                     (pd,-F(7,15)),(pb,F(1400,39)),(p,F(1358,195)),(c-p,F(6,13)),
                     (16-r*c,F(3104,375)),(-r*c,-F(2896,375))):a.eq(got,want,'exercise1')
    a.eq(F(70)*(F(6,5)-F(49,50)),F(77,5),'exercise2 up arbitrage')
    a.eq(F(70)*(1-F(49,50)),F(7,5),'exercise2 down arbitrage')
    a.eq(F(4)+52*F(24,25)-5-50+2*F(99,100),F(9,10),'exercise3 initial receipt')
    for terminal in (F(20),F(52),F(90)):
        a.eq(terminal+max(52-terminal,0)-max(terminal-52,0),F(52),'exercise3 all-strike regions')
    exercise4={'spot':'60','strike':'61','up':'4/3','down':'2/3','gross_rate':'1'}
    rows=oracle_values(F(60),F(61),F(4,3),F(2,3),F(1),2,'call',False)
    a.eq(rows[0][0],F(137,12),'exercise4 root');a.eq(rows[1][1],F(137,6),'exercise4 up')
    a.eq(rows[2],list(map(F,(0,0)))+[F(137,3)],'exercise4 terminal')
    a.eq(oracle_values(F(60),F(61),F(4,3),F(2,3),F(1),2,'put',False)[0][0],F(149,12),'exercise4 put')
    params=(F(80),F(88),F(5,4),F(3,4),F(21,20),2,'put')
    ae=oracle_values(*params,True);ee=oracle_values(*params,False)
    for got,want in ((ae[1][0],F(28)),(ee[1][0],F(500,21)),(ee[1][1],F(104,21)),
                     (ae[0][0],F(1984,147)),(ee[0][0],F(5248,441)),(ae[0][0]-ee[0][0],F(704,441))):a.eq(got,want,'exercise5')
    a.eq(F(1,4)**2*43/F(21,20)**2,F(1075,441),'exercise6 physical discount')
    a.eq(F(18)-2*14+8,F(-2),'exercise8 butterfly initial cost')
    for st in range(0,141):
        val=max(st-70,0)-2*max(st-80,0)+max(st-90,0)
        require(val>=0,'butterfly nonnegative state payoff')
    reserve=F(387,1000)/F(21,20)**2
    a.eq(reserve,F(86,245),'exercise9 funded reserve')
    a.eq(reserve*F(21,20)**2-F(129,500),F(129,1000),'exercise9 up residual')
    q=F(3,5);r=F(21,20)
    hindsight=(1-q)**2*37/r**2+(1-q)*q*22/r+q*(1-q)*7/r**2+q*q*2
    a.eq(hindsight,F(139378,11025),'worked3 hindsight')
    a.eq(hindsight-F(208,21),F(30178,11025),'hindsight excess')
    a.eq(oracle_values(F(50),F(52),F(6,5),F(4,5),F(1),1,'call',False)[0][0],F(4),'retention call')
    a.eq(F(12)-F(21,2),F(3,2),'retention writer surplus')

    interventions=[('physical probability',{'physical_up':'1/4'}),('zero fee',{'interior_rebalance_fee':'0'}),
                   ('one period',{'steps':1}),('three periods',{'steps':3}),('zero strike',{'strike':'0'}),
                   ('worthless call',{'strike':'10000'}),('put exercise transfer',{'strike':'88'}),
                   ('zero rate',{'gross_rate':'1'}),('negative rate tree',{'gross_rate':'9/10'}),
                   ('changed tree',dict(exercise4,steps=2))]
    for label,changes in interventions:
        changed=deepcopy(raw);changed['tree'].update(changes);out=run(changed)
        audit_tree(a,out['tree'],changed['tree'],changed['tree']['steps'])
        audit_paths(a,out['path_reports'],changed['tree'])
        a.eq(out['negative_rate_case'],result['negative_rate_case'],'isolated negative case '+label)
        a.eq(out['dividend_case'],result['dividend_case'],'isolated dividend case '+label)
        if label=='physical probability':
            a.eq(out['tree'],result['tree'],'P does not reprice attainable claims')
            a.eq(out['path_reports']['european_call_physical_expected_payoff'],F(43,16),'changed physical expectation')
    # Maximum period bound with a payoff whose entire price/policy is known.
    changed=deepcopy(raw);changed['tree'].update(steps=6,strike='0');out=run(changed)
    for style in ('european','american_grid'):
        for t,row in enumerate(out['tree']['contracts']['call_'+style]):
            for j,node in enumerate(row):a.eq(node['value'],F(80)*F(5,4)**j*F(3,4)**(t-j),'six-period zero-strike stock claim')
    a.eq(len(out['path_reports']['paths']),64,'six-period paths')
    for path in out['path_reports']['paths']:
        a.eq(path['european_call_ledger'][-1]['exact_hedge_error'],F(0),'six-period terminal hedge')
        a.eq(path['european_call_ledger'][-1]['fee_intervention_hedge_error'],F(0),'unchanged one-share holdings incur no fee')

    invalid=[]
    for field,values in {'spot':['0','10001',80,True,' 80','1e2','NaN','1/0','123456789','0.123456789'],
                         'strike':['-1','10001'],'up':['3.1','1.05'],'down':['0.09','1.05'],
                         'gross_rate':['3','0'],'steps':[0,7,True,2.0],
                         'physical_up':['0','1'],'interior_rebalance_fee':['-0.01','0.11']}.items():
        for value in values:
            bad=deepcopy(raw);bad['tree'][field]=value;invalid.append(bad)
    for field,value in [('schema',True),('schema',1.0),('contract','changed')]:
        bad=deepcopy(raw);bad[field]=value;invalid.append(bad)
    for block in ('tree','negative_rate_call','dividend_call'):
        bad=deepcopy(raw);bad[block]['extra']='1';invalid.append(bad)
        bad=deepcopy(raw);bad[block].pop('spot');invalid.append(bad)
    for field,value in [('gross_rate','1'),('up','0.98')]:
        bad=deepcopy(raw);bad['negative_rate_call'][field]=value;invalid.append(bad)
    for field,value in [('contract','wrong clock'),('cash_dividend','10001'),('ex_down','0'),
                        ('ex_up','30001'),('gross_rate','0.09'),('cash_dividend','50')]:
        bad=deepcopy(raw);bad['dividend_call'][field]=value;invalid.append(bad)
    for bad in invalid:
        try:run(bad)
        except ValueError:a.rejections+=1
        else:raise AssertionError('invalid contract accepted')

    manifest=json.loads((ASSETS/'v10-c06-manifest.json').read_text())
    names={'v10-c06-'+tail for tail in ('inputs.json','analysis.py','output.json','README.txt')}
    a.eq({x['file'] for x in manifest['files']},names,'manifest payload set')
    for entry in manifest['files']:
        payload=(ASSETS/entry['file']).read_bytes()
        a.eq(len(payload),entry['bytes'],'manifest bytes');a.eq(sha256(payload).hexdigest(),entry['sha256'],'manifest digest')
    with tempfile.TemporaryDirectory(prefix='v10-c06-') as tempdir:
        temp=Path(tempdir);folder=temp/'package';folder.mkdir();cwd=temp/'elsewhere';cwd.mkdir()
        for name in names|{'v10-c06-manifest.json'}:shutil.copyfile(ASSETS/name,folder/name)
        for flags in ([],['-O']):
            base=[sys.executable]+flags+[str(folder/'v10-c06-analysis.py')]
            process=subprocess.run(base,cwd=cwd,capture_output=True,text=True,check=True)
            a.eq(json.loads(process.stdout),result,'portable default input');a.eq(process.stderr,'','successful stderr')
            output=cwd/'result.json'
            process=subprocess.run(base+['--input',str(folder/'v10-c06-inputs.json'),'--output',str(output)],cwd=cwd,capture_output=True,text=True,check=True)
            a.eq(process.stdout,'','quiet file output');a.eq(json.loads(output.read_text()),result,'portable explicit paths')
            for badtext in ('{"schema":1,"schema":1}','{"tree":NaN}'):
                bad=folder/'bad.json';bad.write_text(badtext);before=output.read_bytes()
                process=subprocess.run(base+['--input',str(bad),'--output',str(output)],cwd=cwd,capture_output=True,text=True)
                require(process.returncode!=0,'strict JSON must fail');a.eq(output.read_bytes(),before,'failed run preserves output');a.rejections+=1
    body=(ROOT/'content/chapters/v10-c06.html').read_text();parser=Fragment();parser.feed(body)
    require(not parser.stack,'closed HTML fragment');a.eq(len(parser.ids),len(set(parser.ids)),'unique anchors')
    a.eq((parser.worked,parser.exercises,parser.solutions),(5,10,10),'complete chapter package')
    require('teach-back' in body.lower() and 'delayed retention' in body.lower(),'teaching checks')
    proposals=json.loads((ROOT/'content/reviews/v10-c06-sources.json').read_text())['proposals']
    canonical={s['id']:s for s in json.loads((ROOT/'content/sources.json').read_text())}
    for source in proposals:a.eq(canonical[source['id']],source,'source scope registration')
    for name in ('v10-c06-author.json','v10-c06.json'):
        path=ROOT/'content/reviews'/name
        if path.exists():
            for entry in json.loads(path.read_text()).get('reviewed_hashes',[]):
                payload=(ROOT/entry['path']).read_bytes()
                a.eq(sha256(payload).hexdigest(),entry['sha256'],'review binding '+entry['path'])
    return {'chapter':'v10-c06','status':'passed','comparisons':a.comparisons,
            'count_definition':'Executed equality checks of independent values, node/path fields, exercises, interventions, portability and integrity; qualitative require gates are not counted.',
            'invalid_inputs_rejected':a.rejections,'worked_examples':5,'solved_exercises':10,
            'groups':['terminal-payoff sums and exhaustive finite adapted-policy values',
                      'statewise hedge cash equations and all dated fee ledgers',
                      'negative rates, dividend entitlement, all determinate exercises and retention',
                      'ten financial interventions and six-period boundary',
                      'strict domains, quiet API, isolated normal/optimized CLI and bound artifacts'],
            'limits':'Author recomputation and analytic review; proofs and open critique reviewed separately. Not market authentication, independent human certification or visual UI QA.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
