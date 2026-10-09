"""Bounded independent author checks for the original Alder-Beacon chapter.

Only public run(data) and CLI execute. Rational root brackets, full dated
recipient budgets and finite deviations provide independent numerical oracles.
No assert-dependent checks. check() is quiet and returns a strict JSON summary.
"""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from math import isqrt
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects'
MODEL = PROJECT/'v11-c11-analysis.py'
INPUT = PROJECT/'v11-c11-inputs.json'
OWNED = ['content/chapters/v11-c11.html','content/projects/v11-c11-inputs.json',
         'content/projects/v11-c11-analysis.py','content/projects/v11-c11-output.json',
         'content/projects/v11-c11-manifest.json','content/projects/v11-c11-README.txt',
         'scripts/check_v11_c11.py','content/reviews/v11-c11-author.json','content/reviews/v11-c11-sources.json']


def require(condition, label):
    if not condition: raise ValueError('C11 check: '+label)


def strict(text):
    def unique(pairs):
        out={}
        for key,value in pairs:
            require(key not in out,'duplicate key');out[key]=value
        return out
    def invalid(value): raise ValueError('nonfinite '+value)
    return json.loads(text,object_pairs_hook=unique,parse_constant=invalid)


class Audit:
    def __init__(self):
        self.comparisons=0;self.cases=0;self.api_rejections=0;self.cli_rejections=0
        self.alias_rejections=0;self.portable_successes=0;self.printed_results=0
    def eq(self,actual,expected,label):
        self.comparisons+=1
        require(actual==expected,label+': '+repr(actual)+' != '+repr(expected))
    def near(self,actual,expected,label):
        self.comparisons+=1
        require(abs(F(actual)-expected)<=F(1,10**29)*max(1,abs(expected)),label)
    def values(self,actual,expected,label):
        for key,value in expected.items():
            if type(value) is dict:self.values(actual[key],value,label+'/'+key)
            elif isinstance(value,F):self.near(actual[key],value,label+'/'+key)
            else:self.eq(actual[key],value,label+'/'+key)
    def call(self,run,data):
        before=deepcopy(data);stream=StringIO()
        with redirect_stdout(stream),redirect_stderr(stream):out=run(data)
        self.eq(stream.getvalue(),'','quiet run');self.eq(data,before,'nonmutating run')
        self.eq(strict(json.dumps(out,allow_nan=False)),out,'strict output')
        self.cases+=1
        return out


def changed(base,path,value):
    data=deepcopy(base);target=data
    for key in path[:-1]:target=target[key]
    target[path[-1]]=value
    return data


def root_sale(p0,impact,maximum,target):
    revenue=lambda s:p0*s-impact*s*s
    if target>=revenue(maximum):return maximum,revenue(maximum)
    if target==0:return F(0),F(0)
    if impact==0:return target/p0,target
    # Exact square discriminants have rational roots, verified in the budget.
    disc=p0*p0-4*impact*target
    a,b=isqrt(disc.numerator),isqrt(disc.denominator)
    if a*a==disc.numerator and b*b==disc.denominator:
        candidate=(p0-F(a,b))/(2*impact)
        require(0<=candidate<=maximum and revenue(candidate)==target,'rational root certificate')
        return candidate,target
    low,high=F(0),maximum
    for _ in range(160):
        middle=(low+high)/2
        if revenue(middle)<target:low=middle
        else:high=middle
    require(revenue(low)<=target<=revenue(high),'sale root bracket')
    return (low+high)/2,target


def b_oracle(data,p1,p2,bridge=F(0)):
    cash=F(data['beacon']['cash']);debt=F(data['beacon']['customer_due'])
    first=min(debt,cash+p1+bridge);cash+=p1+bridge-first
    missed=debt-first;cash+=p2
    public=min(cash,bridge);cash-=public
    last=min(missed,cash);cash-=last
    network_loss=F(data['bank']['network_due'])-p1-p2
    return dict(receipt_cutoff1=p1,receipt_cutoff2=p2,bridge_draw=bridge,
                customer_paid_cutoff1=first,customer_missed_cutoff1=missed,
                customer_paid_cutoff2=last,customer_terminal_loss=missed-last,
                bridge_repayment=public,public_bridge_loss=bridge-public,equity_terminal=cash,
                network_asset_loss=network_loss,
                loss_attribution_residual=F(data['beacon']['opening_equity'])-cash+missed-last+bridge-public-network_loss)


def profile_oracle(data,cap,m,value):
    bank={k:F(v) for k,v in data['bank'].items()}
    market={k:F(v) for k,v in data['market'].items()}
    c,n,e,f,k=(bank[x] for x in ('cash','asset_units','retail_due','funder_principal','network_due'))
    p0,impact=market['intercept'],market['impact']
    target=max(e+m*f+k-c,F(0))
    loan=min(F(cap),target,F(data['policy']['advance_fraction'])*p0*n)
    pledge=loan/(F(data['policy']['advance_fraction'])*p0)
    sale,proceeds=root_sale(p0,impact,n-pledge,max(target-loan,F(0)))
    price=p0-impact*sale
    # Explicit date1 ledger, using only actual receipts and sequential rights.
    cash=c+loan+proceeds
    retail=e;cash-=retail
    runners=min(m*f,cash);cash-=runners
    network=min(k,cash);cash-=network
    runner_unpaid=m*f-runners;network_unpaid=k-network
    principal=(2-m)*f+runner_unpaid+network_unpaid
    assets=cash+price*(n-sale)
    equity=assets-principal-loan
    first=dict(runners=m,loan=loan,pledged_units=pledge,free_units=n-pledge,sale_units=sale,
               sale_price=price,sale_proceeds=proceeds,retail_paid=retail,runners_paid=runners,
               runner_unpaid=runner_unpaid,network_paid=network,network_unpaid=network_unpaid,
               cash_remaining=cash,retained_units=n-sale,marked_assets=assets,
               principal_marked_equity=equity,assets_to_equity=assets/equity if equity>F(1,10**24) else None,
               cash_residual=F(0),sale_residual=price*sale-proceeds)
    estate=cash+F(value)*(n-sale)
    public=min(loan,estate);left=estate-public
    wait_due=(2-m)*f*bank['wait_multiplier']
    claims={'waiters_paid':wait_due,'runners_paid_late':runner_unpaid,'network_paid_late':network_unpaid}
    due=sum(claims.values());paid={key:(claim*min(F(1),left/due) if due else F(0)) for key,claim in claims.items()}
    residual=left-sum(paid.values())
    loss=due-sum(paid.values());public_loss=loan-public
    buyer=F(value)*sale-proceeds;interest=(2-m)*f*(bank['wait_multiplier']-1)
    fundamental=n*(p0-F(value))
    beacon=b_oracle(data,network,paid['network_paid_late'])
    buyer_cash=n*p0;buyer_terminal=buyer_cash+buyer
    resources=c+F(data['beacon']['cash'])+F(data['policy']['public_cash'])+buyer_cash+F(value)*n
    recipients=retail+runners+paid['runners_paid_late']+paid['waiters_paid']+residual+beacon['customer_paid_cutoff1']+beacon['customer_paid_cutoff2']+beacon['equity_terminal']+F(data['policy']['public_cash'])-public_loss+buyer_terminal
    require(recipients==resources,'independent consolidated normal resources')
    last=dict(unit_payoff=F(value),estate_available=estate,public_repayment=public,public_loss=public_loss,
              public_cash_terminal=F(data['policy']['public_cash'])-public_loss,private_due=due,
              private_recovery_fraction=min(F(1),left/due) if due else F(1),**paid,
              private_claim_loss=loss,Alder_equity_terminal=residual,
              runner_payoff_each=(runners+paid['runners_paid_late'])/m if m else None,
              waiter_payoff_each=paid['waiters_paid']/(2-m) if m<2 else None,
              buyer_gain=buyer,waiting_interest_due=interest,fundamental_asset_loss=fundamental,
              buyer_initial_cash=buyer_cash,buyer_cash_after_sale=buyer_cash-proceeds,buyer_terminal_wealth=buyer_terminal,
              loss_attribution_residual=bank['opening_equity']-residual+loss+public_loss-fundamental-interest-buyer,
              estate_residual=F(0),consolidated_resources=resources,consolidated_recipient_wealth=recipients,
              consolidated_resource_residual=F(0),beacon=beacon)
    return first,last


def resolve_oracle(data,value):
    b=data['bank'];f=F(b['funder_principal']);k=F(b['network_due']);e=F(b['retail_due'])
    cash=F(b['cash'])-e;estate=cash+F(b['asset_units'])*F(value);claims=2*f+k
    recovery=min(F(1),estate/claims);funders=2*f*recovery;network=k*recovery
    bridge=min(max(F(data['beacon']['customer_due'])-F(data['beacon']['cash']),F(0)),F(data['policy']['resolution_bridge_cap']))
    beacon=b_oracle(data,F(0),network,bridge)
    buyer_cash=F(b['asset_units'])*F(data['market']['intercept'])
    public=F(data['policy']['public_cash'])-beacon['public_bridge_loss']
    resources=F(b['cash'])+F(data['beacon']['cash'])+F(data['policy']['public_cash'])+buyer_cash+F(value)*F(b['asset_units'])
    recipients=e+funders+estate-funders-network+beacon['customer_paid_cutoff1']+beacon['customer_paid_cutoff2']+beacon['equity_terminal']+public+buyer_cash
    require(recipients==resources,'independent consolidated resolution resources')
    return dict(unit_payoff=F(value),retail_paid_cutoff1=e,retained_cash=cash,assets_sold=F(0),Alder_estate_cutoff2=estate,
                restructured_principal_claims=claims,pari_passu_fraction=recovery,funders_paid_cutoff2=funders,
                network_paid_cutoff2=network,private_principal_loss=claims-funders-network,Alder_equity_terminal=estate-funders-network,
                cancelled_wait_premium_relative_to_WW=2*f*(F(b['wait_multiplier'])-1),estate_residual=F(0),beacon=beacon,
                public_cash_terminal=public,buyer_unused_cash=buyer_cash,
                consolidated_resources=resources,consolidated_recipient_wealth=recipients,consolidated_resource_residual=F(0))


def certify(a,data,out):
    a.eq(len(out['line_alternatives']),len(data['policy']['line_caps']),'all line alternatives')
    for cap,alternative in zip(data['policy']['line_caps'],out['line_alternatives']):
        a.near(alternative['line_cap'],F(cap),'declared funded cap')
        a.eq(len(alternative['profiles']),3,'three runner counts')
        benchmark=[]
        for m,profile in enumerate(alternative['profiles']):
            expected,gamepay=profile_oracle(data,cap,m,data['market']['benchmark_terminal_value']);benchmark.append(gamepay)
            a.values(profile['cutoff1'],expected,'cutoff1')
            a.eq(len(profile['terminal_states']),len(data['terminal_states']),'frozen-history state count')
            for state,result in zip(data['terminal_states'],profile['terminal_states']):
                a.eq(result['label'],state['label'],'state identity')
                _,last=profile_oracle(data,cap,m,state['unit_payoff'])
                a.values(result,last,'cutoff2')
        # Enumerate all four pure profiles and their unilateral alternatives.
        d0=benchmark[1]['runner_payoff_each']-benchmark[0]['waiter_payoff_each']
        d1=benchmark[2]['runner_payoff_each']-benchmark[1]['waiter_payoff_each']
        strict=[];weak=[];band=F(1,10**24)
        for label,choices in [('WW',(0,0)),('RR',(1,1)),('RW',(1,0)),('WR',(0,1))]:
            gains=[]
            for who,action in enumerate(choices):
                difference=d1 if choices[1-who] else d0
                gains.append(difference if not action else -difference)
            if max(gains)<-band:strict.append(label)
            if max(gains)<=band:weak.append(label)
        game=alternative['benchmark_game']
        a.eq(game['strict_pure_equilibria'],strict,'finite unilateral deviations')
        a.eq(game['weak_pure_candidates_with_numeric_band'],weak,'bounded near-indifference candidates')
        a.eq(game['near_indifference_unresolved'],abs(d0)<=band or abs(d1)<=band,'numerical uncertainty declared')
        a.near(game['run_minus_wait_if_other_waits'],d0,'deviation against W')
        a.near(game['run_minus_wait_if_other_runs'],d1,'deviation against R')
        if d0*d1<0 and abs(d0)>band and abs(d1)>band:
            x=F(game['symmetric_mixed_run_probability'])
            a.near(x,-d0/(d1-d0),'affine indifference probability')
            a.near((1-x)*d0+x*d1,F(0),'mixed payoff equality')
        else:a.eq(game['symmetric_mixed_run_probability'],None,'no manufactured isolated mixed equilibrium')
    for state,result in zip(data['terminal_states'],out['resolution_alternative']):
        a.eq(result['label'],state['label'],'resolution state identity')
        a.values(result,resolve_oracle(data,state['unit_payoff']),'resolution')


def interventions(a,run,base):
    # Each transfer uses one line/state unless two are needed for the comparison.
    slim=deepcopy(base);slim['policy']['line_caps']=['0'];slim['terminal_states']=[base['terminal_states'][0]]
    variants=[]
    variants.append(('flat auction',changed(slim,['market','impact'],'0')))
    variants.append(('no waiting premium',changed(slim,['bank','wait_multiplier'],'1')))
    variants.append(('no timely bridge',changed(slim,['policy','resolution_bridge_cap'],'0')))
    v=deepcopy(slim);v['market']['benchmark_terminal_value']='0.6';variants.append(('known downside game',v))
    v=deepcopy(slim);v['policy']['line_caps']=['80'];v['policy']['advance_fraction']='0.5';variants.append(('lower collateral advance',v))
    v=deepcopy(slim);v['bank'].update(cash='30',opening_equity='30');variants.append(('funded equity cash',v))
    v=deepcopy(slim);v['beacon'].update(cash='10',opening_equity='20');variants.append(('Beacon prefunded liquidity',v))
    v=deepcopy(slim);v['terminal_states']=[{'label':'zero_assets','unit_payoff':'0'}];variants.append(('zero terminal assets',v))
    v=deepcopy(slim);v['policy'].update(public_cash='0',line_caps=['0'],resolution_bridge_cap='0');variants.append(('zero public budget',v))
    for label,data in variants:
        out=a.call(run,data);certify(a,data,out)
        game=out['line_alternatives'][0]['benchmark_game']
        if label=='flat auction':a.eq(game['strict_pure_equilibria'],['WW'],'retention changed market capacity')
        if label=='no waiting premium':a.eq(game['near_indifference_unresolved'],True,'equality is not falsely certified strict')
        if label=='no timely bridge':a.near(out['resolution_alternative'][0]['beacon']['customer_missed_cutoff1'],F(10),'stay adds no cash')
        if label=='Beacon prefunded liquidity':a.near(out['line_alternatives'][0]['profiles'][2]['terminal_states'][0]['beacon']['customer_missed_cutoff1'],F(0),'independent liquidity blocks early transmission')
        if label=='lower collateral advance':a.near(out['line_alternatives'][0]['profiles'][2]['cutoff1']['loan'],F(50),'public cash alone cannot bypass collateral cap')


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.worked=0;self.exercises=0;self.solutions=0
        self.anchors=[];self.capture=None;self.hrefs=[];self.sources=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);classes=attrs.get('class','').split()
        if 'id' in attrs:self.ids.append(attrs['id'])
        if 'href' in attrs:self.hrefs.append(attrs['href'])
        if 'data-source' in attrs:self.sources.append(attrs['data-source'])
        if 'data-calc' in attrs:self.capture=(attrs['data-calc'],[])
        if tag=='aside' and 'worked' in classes:self.worked+=1
        if tag=='li':
            if any(t=='ol' and 'exercises' in c for t,c in self.stack):self.exercises+=1
            if any(t=='details' and 'solutions' in c for t,c in self.stack):self.solutions+=1
        if tag not in ('br','hr','img','input','meta','link','wbr'):self.stack.append((tag,classes))
    def handle_data(self,data):
        if self.capture:self.capture[1].append(data)
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'balanced manuscript '+tag);self.stack.pop()
        if tag=='span' and self.capture:
            self.anchors.append((self.capture[0],''.join(self.capture[1])));self.capture=None


def printed(a,base):
    parser=Manuscript();text=(ROOT/OWNED[0]).read_text();parser.feed(text);parser.close()
    a.eq(parser.stack,[],'closed HTML fragment');a.eq(len(parser.ids),len(set(parser.ids)),'unique chapter IDs')
    a.eq((parser.worked,parser.exercises,parser.solutions),(4,8,8),'four worked and eight exact solved exercises')
    a.eq(set(parser.sources),{'v11-c01-diamond-dybvig','v06-c12-us-crisis'},'scoped existing primary sources')
    a.eq({h for h in parser.hrefs if h.startswith('v11-c11-')},{'v11-c11'+s for s in ('-inputs.json','-analysis.py','-output.json','-manifest.json','-README.txt')},'five flat reader links')
    t0,s0=profile_oracle(base,'0',0,'1');t1,s1=profile_oracle(base,'0',1,'1');t2,s2=profile_oracle(base,'0',2,'1')
    tp,sp=profile_oracle(base,'20',2,'1');_,sf=profile_oracle(base,'80',2,'0.6')
    r0,rd,rx=(resolve_oracle(base,v) for v in ('1','0.6','0.1'))
    def rounded(value):
        with localcontext() as c:
            c.prec=70
            return format(Decimal(value.numerator)/Decimal(value.denominator),'.6f').replace('-','−')
    d0=s1['runner_payoff_each']-s0['waiter_payoff_each'];d1=s2['runner_payoff_each']-s1['waiter_payoff_each']
    bank={k:F(v) for k,v in base['bank'].items()}
    n=bank['asset_units'];cash=bank['cash'];p0=F(base['market']['intercept']);impact=F(base['market']['impact'])
    debt=bank['retail_due']+2*bank['funder_principal']+bank['network_due']
    qcrit=(debt-cash)/n;scrit=(p0-qcrit)/impact
    # The excluded nonmonotone example's two roots use an independent sqrt bracket.
    low,high=F(2),F(3)
    for _ in range(160):
        middle=(low+high)/2
        if middle*middle<5:low=middle
        else:high=middle
    root5=(low+high)/2
    exact={
        'maximum_receipts':t2['sale_proceeds'],'sale_zero':t0['sale_units'],'price_zero':t0['sale_price'],
        'wait_wait':s0['waiter_payoff_each'],'sale_two':t2['sale_units'],'price_two':t2['sale_price'],
        'equity_wait':s0['Alder_equity_terminal'],'run_run':s2['runner_payoff_each'],
        'belief_run':F(9,10)*s1['runner_payoff_each']+F(1,10)*s2['runner_payoff_each'],
        'initial_leverage':(cash+n*p0)/bank['opening_equity'],'marked_equity_wait':t0['principal_marked_equity'],
        'prepayment_leverage':(cash+n*t0['sale_price'])/t0['principal_marked_equity'],
        'retained_mark':t0['marked_assets'],'postpayment_leverage':t0['assets_to_equity'],
        'zero_equity_price':qcrit,'zero_equity_sale':scrit,'zero_equity_receipts':scrit*qcrit,
        'private_advance':F(base['policy']['advance_fraction'])*n*t0['sale_price'],
        'pledged_partial':tp['pledged_units'],'sale_partial':tp['sale_units'],
        'price_partial':tp['sale_price'],'receipts_partial':tp['sale_proceeds'],'network_partial_early':tp['network_paid'],
        'beacon_partial_miss':sp['beacon']['customer_missed_cutoff1'],'network_partial_late':sp['network_paid_late'],
        'network_partial_total':tp['network_paid']+sp['network_paid_late'],'beacon_partial_equity':sp['beacon']['equity_terminal'],
        'buyer_partial_gain':sp['buyer_gain'],'network_partial_loss':sp['beacon']['network_asset_loss'],
        'public_full_loss':sf['public_loss'],'public_full_cash':sf['public_cash_terminal'],
        'resolution_estate_good':r0['Alder_estate_cutoff2'],'resolution_claims':r0['restructured_principal_claims'],
        'resolution_estate_down':rd['Alder_estate_cutoff2'],'resolution_recovery':rd['pari_passu_fraction'],
        'resolution_funders_down':rd['funders_paid_cutoff2'],'resolution_network_down':rd['network_paid_cutoff2'],
        'resolution_private_loss':rd['private_principal_loss'],'resolution_beacon_equity':rd['beacon']['equity_terminal'],
        'resolution_network_deep':rx['network_paid_cutoff2'],'resolution_bridge_deep_loss':rx['beacon']['public_bridge_loss'],
        'cancelled_premium':r0['cancelled_wait_premium_relative_to_WW'],'resolution_estate_deep':rx['Alder_estate_cutoff2'],
        'resolution_recovery_deep':rx['pari_passu_fraction'],'resolution_funders_deep':rx['funders_paid_cutoff2'],
        'nonmonotone_max':F(50)-F(1,100)*50*50}
    strings={
        'sale_one_rounded':rounded(t1['sale_units']),'price_one_rounded':rounded(t1['sale_price']),
        'wait_run_rounded':rounded(s1['waiter_payoff_each']),'mixed_rounded':rounded(-d0/(d1-d0)),
        'belief_wait_rounded':rounded(F(9,10)*s0['waiter_payoff_each']+F(1,10)*s1['waiter_payoff_each']),
        'marked_equity_one_rounded':rounded(t1['principal_marked_equity']),
        'nonmonotone_low_rounded':rounded(50-10*root5),'nonmonotone_high_rounded':rounded(50+10*root5),
        'full_line_draws':', '.join(str(profile_oracle(base,'80',m,'1')[0]['loan']) for m in range(3))}
    a.eq({key for key,value in parser.anchors},set(exact)|set(strings),'every declared printed numerical result covered')
    for key,text in parser.anchors:
        if key in exact:a.eq(F(text),exact[key],'printed exact arithmetic '+key)
        else:a.eq(text,strings[key],'printed rounded or vector result '+key)
        a.printed_results+=1
    a.near((100-t1['sale_units'])**2,F(200),'printed radical sale equation')
    a.near((sp['buyer_gain']-20),sp['beacon']['network_asset_loss'],'printed no-double-count loss allocation')
    return parser


def invalid_cases(a,run,base):
    changes=[(['schema'],'wrong'),(['bank','cash'],20),(['bank','cash'],'020'),(['bank','cash'],'2e1'),
             (['bank','cash'],'20.0000001'),(['bank','cash'],'-1'),(['bank','asset_units'],'0'),
             (['bank','funder_principal'],'0'),(['bank','wait_multiplier'],'0.9'),(['bank','opening_equity'],'21'),
             (['beacon','opening_equity'],'11'),(['market','impact'],'0.01'),(['market','intercept'],'0'),
             (['market','benchmark_terminal_value'],'NaN'),(['policy','advance_fraction'],'0'),
             (['policy','line_caps'],['81']),(['policy','line_caps'],['20','20.0']),(['policy','line_caps'],[]),
             (['policy','resolution_bridge_cap'],'81'),(['terminal_states'],[]),
             (['terminal_states',0,'label'],'bad label'),(['terminal_states',1,'label'],'benchmark'),
             (['terminal_states',0,'unit_payoff'],True),(['terminal_states',0,'unit_payoff'],'-0.1')]
    cases=[changed(base,path,value) for path,value in changes]
    d=deepcopy(base);d['extra']=0;cases.append(d)
    d=deepcopy(base);del d['beacon'];cases.append(d)
    d=deepcopy(base);d['bank'].update(cash='17',opening_equity='17');cases.append(d)
    d=deepcopy(base);d['policy']['line_caps']=['0','1','2','3','4'];cases.append(d)
    for data in cases:
        before=deepcopy(data);stream=StringIO()
        with redirect_stdout(stream),redirect_stderr(stream):
            try:run(data)
            except ValueError:a.api_rejections+=1
            else:raise ValueError('invalid domain accepted')
        a.eq(stream.getvalue(),'','invalid run quiet');a.eq(data,before,'invalid input preserved')


def portable(a,base,expected):
    with tempfile.TemporaryDirectory(prefix='v11-c11-portable-') as temporary:
        folder=Path(temporary);model=folder/MODEL.name;source=folder/INPUT.name
        shutil.copy2(MODEL,model);shutil.copy2(INPUT,source);original=(model.read_bytes(),source.read_bytes())
        for optimized in (False,True):
            python=[sys.executable,'-I']+(['-O'] if optimized else [])
            def invoke(args):return subprocess.run(python+[str(model)]+args,cwd='/',capture_output=True,text=True,timeout=20)
            result=invoke([]);a.eq((result.returncode,result.stdout,result.stderr),(0,'',''),'portable default CLI quiet')
            default_output=folder/'v11-c11-output.json'
            a.eq(strict(default_output.read_text()),expected,'default sibling input and output');a.portable_successes+=1
            default_output.unlink();default_output.symlink_to(source)
            result=invoke([]);a.eq(result.returncode,2,'default output alias rejected')
            a.eq((model.read_bytes(),source.read_bytes()),original,'default alias preserves protected bytes')
            default_output.unlink();a.alias_rejections+=1
            output=folder/'result.json';result=invoke(['--input',str(source),'--output',str(output)])
            a.eq((result.returncode,result.stdout,result.stderr),(0,'',''),'explicit CLI quiet')
            a.eq(strict(output.read_text()),expected,'full explicit output');a.portable_successes+=1
            api='import runpy,json,sys,contextlib,io; b=io.StringIO()\nwith contextlib.redirect_stdout(b),contextlib.redirect_stderr(b):\n m=runpy.run_path(sys.argv[1]);d=json.load(open(sys.argv[2]));before=json.dumps(d,sort_keys=True);r=m["run"](d)\nif b.getvalue() or before!=json.dumps(d,sort_keys=True):raise ValueError("API contract")\nprint(json.dumps(r,allow_nan=False))'
            result=subprocess.run(python+['-c',api,str(model),str(source)],cwd='/',capture_output=True,text=True,timeout=20)
            a.eq((result.returncode,result.stderr),(0,''),'isolated quiet API');a.eq(strict(result.stdout),expected,'isolated API result');a.portable_successes+=1
            for protected in (source,model):
                for kind in ('direct','symlink','hardlink'):
                    alias=protected if kind=='direct' else folder/('alias-'+protected.name)
                    if kind=='symlink':alias.symlink_to(protected)
                    if kind=='hardlink':os.link(protected,alias)
                    result=invoke(['--input',str(source),'--output',str(alias)])
                    a.eq(result.returncode,2,'protected alias rejected '+kind);a.eq(result.stdout,'','rejection stdout quiet')
                    a.eq((model.read_bytes(),source.read_bytes()),original,'protected payloads unchanged');a.alias_rejections+=1
                    if kind!='direct':alias.unlink()
            for text in ('{"schema":1,"schema":2}',json.dumps(base).replace('"cash": "20"','"cash": NaN'),json.dumps(changed(base,['market','impact'],'0.01')),' '*1000001):
                bad=folder/'bad.json';bad.write_text(text);output.write_text('PRESERVE\n')
                result=invoke(['--input',str(bad),'--output',str(output)])
                a.eq(result.returncode,2,'strict/domain CLI error');a.eq(result.stdout,'','invalid CLI stdout quiet')
                a.eq(output.read_text(),'PRESERVE\n','existing output preserved');a.cli_rejections+=1


def bindings(a):
    manifest=strict((PROJECT/'v11-c11-manifest.json').read_text())
    wanted={'v11-c11'+s for s in ('-inputs.json','-analysis.py','-output.json','-README.txt')}
    a.eq({r['file'] for r in manifest['files']},wanted,'exact four manifest payloads');a.eq(len(manifest['files']),4,'unique manifest')
    for item in manifest['files']:
        payload=(PROJECT/item['file']).read_bytes();a.eq((item['bytes'],item['sha256']),(len(payload),sha256(payload).hexdigest()),'manifest binding')
    review=strict((ROOT/'content/reviews/v11-c11-author.json').read_text())
    a.eq({r['path'] for r in review['reviewed_hashes']},set(OWNED)-{'content/reviews/v11-c11-author.json'},'eight nonself author payloads')
    a.eq(len(review['reviewed_hashes']),8,'unique author bindings')
    for item in review['reviewed_hashes']:
        payload=(ROOT/item['path']).read_bytes();a.eq((item['bytes'],item['sha256']),(len(payload),sha256(payload).hexdigest()),'author binding')
    a.eq(len(review['exercise_audit']),8,'all exact prompts reviewed')


def check():
    a=Audit();stream=StringIO()
    with redirect_stdout(stream),redirect_stderr(stream):model=runpy.run_path(str(MODEL))
    a.eq(stream.getvalue(),'','quiet import')
    base=strict(INPUT.read_text());out=a.call(model['run'],base);certify(a,base,out)
    a.eq(out,strict((PROJECT/'v11-c11-output.json').read_text()),'saved output reproduced after independent certificates')
    interventions(a,model['run'],base);invalid_cases(a,model['run'],base);printed(a,base)
    portable(a,base,out);bindings(a)
    result=dict(chapter='v11-c11',status='author-check-passed',**vars(a),worked_examples=4,solved_exercises=8,
                methods=['exact rational sale regimes and independent 160-step root brackets','dated recipient budgets and loss allocation',
                         'four pure unilateral deviations and affine mixed indifference','all tagged exact/rounded manuscript calculations'],
                limits='Original finite model; no empirical crisis frequency, universal policy optimum, national authority or independent human certification.')
    json.dumps(result,allow_nan=False);return result


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
