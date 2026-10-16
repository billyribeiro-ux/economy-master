"""Independent primitive audit for the Alder integrated case; quiet stdlib API."""
from fractions import Fraction as Q
from pathlib import Path
import json

def plain(v):
    if isinstance(v,Q): return str(v.numerator) if v.denominator==1 else str(v)
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    return v

def independent(d):
    """Built from prompts and primitive inputs before inspecting reader implementation."""
    probs=list(map(Q,d['state_probabilities'])); prices=[p*Q(m) for p,m in zip(probs,d['sdf'])]
    bond=sum(prices); lo=Q(d['observed_difference'])-Q(d['selection_interval'][1]); hi=Q(d['observed_difference'])-Q(d['selection_interval'][0])
    pv=lambda xs:sum(q*x for q,x in zip(prices,xs))
    rows=[]
    for n in sorted(d['quantities']):
        install=n*Q(d['installation_cost']); grant=n*Q(d['grant']); equity=n*Q(d['developer_equity_per_unit']); loan=install-grant-equity
        cash=[n*(Q(r)-Q(d['operating_cost'])) for r in d['revenue_per_unit']]
        # Enumerate every payoff region independently via which states have defaulted.
        faces=[]
        for mask in range(4):
            fixed=sum(prices[s]*cash[s] for s in range(2) if mask&(1<<s))
            slope=sum(prices[s] for s in range(2) if not mask&(1<<s))
            if slope:
                f=(loan-fixed)/slope
                if f>=0 and all((f>=cash[s]) if mask&(1<<s) else (f<=cash[s]) for s in range(2)): faces.append(f)
            elif loan==fixed: faces.append(max(cash))
        face=min(faces) if faces else None
        debt=[min(face,x) for x in cash] if face is not None else None
        eq=[x-y for x,y in zip(cash,debt)] if debt else None
        admin=grant*Q(d['grant_admin_rate']); levy=(grant+admin)/2
        banksafe=Q(d['bank_endowment'])-loan; devsafe=Q(d['developer_endowment'])-equity
        bp=[x+banksafe/bond for x in debt] if debt else None; dp=[x+devsafe/bond for x in eq] if eq else None
        netservice=pv([n*(Q(s)-Q(r)) for s,r in zip(d['service_value_per_unit'],d['revenue_per_unit'])])
        welfare=[]
        for theta in [lo,hi]:
            ext=n*theta-Q(d['external_congestion'])*n*n
            poor=netservice+bond*ext/2-levy; rich=bond*ext/2-levy
            direct=pv([n*(Q(s)-Q(d['operating_cost'])) for s in d['service_value_per_unit']])+bond*ext-install-admin
            welfare.append({'theta':theta,'poor':poor,'rich':rich,'total':poor+rich+(pv(eq)-equity if eq is not None else Q(0)),'direct':direct})
        lowpoor=min(x['poor'] for x in welfare); lowrich=min(x['rich'] for x in welfare)
        lower=max(Q(0),-lowrich); upper=min(lowpoor/(1+Q(d['transfer_admin_rate'])),(Q(d['household_current_cash'])-levy)/(1+Q(d['transfer_admin_rate'])))
        failures=[]
        if loan>min(Q(d['bank_loan_cap']),Q(d['bank_endowment'])): failures.append('bank_funding')
        if equity>Q(d['developer_endowment']): failures.append('developer_funding')
        if grant+admin>Q(d['treasury_limit']): failures.append('public_appropriation')
        if levy>Q(d['household_current_cash']): failures.append('initial_household_cash')
        if max(n*Q(r) for r in d['revenue_per_unit'])>Q(d['household_future_income']): failures.append('service_bill')
        if face is None: failures.append('pledgeable_value')
        elif pv(eq)<equity: failures.append('developer_participation')
        rows.append({'n':n,'loan':loan,'face':face,'cash':cash,'debt':debt,'equity_payoffs':eq,'debt_pv':None if debt is None else pv(debt),'equity_pv':None if eq is None else pv(eq),'bank_total':bp,'developer_total':dp,'levy':levy,'admin':admin,'initial_resource_uses':install+admin+banksafe+devsafe+2*(Q(d['household_current_cash'])-levy),'future_resource_supply':2*Q(d['household_future_income'])+(banksafe+devsafe)/bond,'welfare':welfare,'transfer_interval':[lower,upper],'feasible':not failures,'failures':failures})
    feasible=[r for r in rows if r['feasible']]
    if feasible:
        endpoint_best=[max(r['welfare'][s]['total'] for r in feasible) for s in range(2)]
        prior=Q(d['high_endpoint_weight'])
        for r in rows:
            r['prior_value']=(1-prior)*r['welfare'][0]['total']+prior*r['welfare'][1]['total']
            r['worst_regret']=max(endpoint_best[s]-r['welfare'][s]['total'] for s in range(2))
        bestprior=max(r['prior_value'] for r in feasible); bestregret=min(r['worst_regret'] for r in feasible)
        choices={'bayes':[r['n'] for r in feasible if r['prior_value']==bestprior],'minimax':[r['n'] for r in feasible if r['worst_regret']==bestregret]}
    else: choices={}
    return {'prices':prices,'bond':bond,'theta':[lo,hi],'rows':rows,'choices':choices}

from copy import deepcopy
from hashlib import sha256
from html.parser import HTMLParser
import contextlib, io, os, subprocess, sys, tempfile, types
ROOT=Path(__file__).resolve().parents[1]
READERS=['content/projects/integrated-case-'+x for x in ['inputs.json','analysis.py','output.json','README.txt','manifest.json']]
AUTHOR_FILES=['content/cross-assessments/integrated-case.html',*READERS,'content/reviews/integrated-case-sources.json','scripts/check_integrated_case.py','content/reviews/integrated-case-author.json']
RUNTIME=[*AUTHOR_FILES,'scripts/check_integrated_case_peer.py','content/reviews/integrated-case-peer.json']

def require(ok,message):
    if not ok: raise ValueError('integrated peer: '+message)

def load(path):
    m=types.ModuleType('independently_checked_reader');m.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__)
    return m

class Structure(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.answers=[];self.tasks=[];self.rubrics=[];self.sources={};self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'data-solution-for' in a:self.answers.append(a['data-solution-for'])
        if 'data-points' in a:self.tasks.append((a['id'],int(a['data-points']),a['data-domain']))
        if 'data-rubric' in a:self.rubrics.append(tuple(map(int,a['data-rubric'].split(','))))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if 'href' in a:self.links.append(a['href'])

def check(root=None):
    root=Path(root) if root is not None else ROOT
    record=json.loads((root/RUNTIME[-1]).read_text())
    require(set(record['payloads'])==set(RUNTIME[:-1]),'review inventory')
    for name,rec in record['payloads'].items():
        b=(root/name).read_bytes();require(rec=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'frozen payload '+name)
    require(record['open_material_findings']==[] and all(record['review'].values()),'review incomplete')
    manifest=json.loads((root/READERS[-1]).read_text())
    require(set(manifest['files'])=={Path(x).name for x in READERS[:-1]},'manifest inventory')
    for name,rec in manifest['files'].items():
        b=(root/'content/projects'/name).read_bytes();require(rec=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'manifest payload')
    doc=Structure();doc.feed((root/AUTHOR_FILES[0]).read_text());doc.close()
    require(len(doc.ids)==len(set(doc.ids)),'duplicate IDs')
    expected=[f'integrated-case-{k}{i}' for k,n in [('t',7),('o',2),('r',5)] for i in range(1,n+1)]
    require(sorted(doc.answers)==sorted(expected) and set(expected)<=set(doc.ids),'14 complete answer pairings')
    require([x[1] for x in doc.tasks]==[20,20,10,20,15,10,5],'task allocations')
    require([sum(x) for x in doc.rubrics]==[x[1] for x in doc.tasks],'rubric allocations')
    require(all(sum(p for _,p,d in doc.tasks if d==domain)==20 for domain in ['D1','D2','D3','D4','D5']),'five domain totals')
    require(all(x[1:] in doc.ids for x in doc.links if x.startswith('#')),'fragment route')
    require({Path(x).name for x in READERS}<={x for x in doc.links},'reader links')
    sources=json.loads((root/'content/reviews/integrated-case-sources.json').read_text())
    require(doc.sources=={x['id']:x['url'] for x in sources['sources']},'bounded source routes')
    reader=load(root/READERS[1]);data=json.loads((root/READERS[0]).read_text());original=deepcopy(data)
    count=0
    def compare(actual,expected,label):
        nonlocal count
        if isinstance(expected,dict):
            require(set(actual)==set(expected),label+' keys')
            for k,v in expected.items():compare(actual[k],v,label+'/'+str(k))
        elif isinstance(expected,(list,tuple)):
            require(len(actual)==len(expected),label+' length')
            for i,(a,b) in enumerate(zip(actual,expected)):compare(a,b,label+'/'+str(i))
        elif isinstance(expected,bool) or expected is None or isinstance(expected,str):
            require(actual==expected,label);count+=1
        else:
            require(type(actual) in (str,int) and Q(actual)==expected,label);count+=1
    def audit(d,out):
        ref=independent(d)
        compare(out['state_prices'],ref['prices'],'prices');compare(out['safe_price'],ref['bond'],'bond')
        compare(out['safe_gross_return'],1/ref['bond'],'return');compare(out['causal_interval'],ref['theta'],'interval')
        compare(out['observationally_equivalent_endpoint_parameters'],[[t,Q(d['observed_difference'])-t] for t in ref['theta']],'sharp endpoints')
        require(len(out['policies'])==len(ref['rows']),'policy rows')
        for a,b in zip(out['policies'],ref['rows']):
            n=b['n'];compare(a['quantity'],n,'quantity');compare(a['feasible'],b['feasible'],'feasible');compare(a['failures'],b['failures'],'failures')
            basics={'installation':n*Q(d['installation_cost']),'grant':n*Q(d['grant']),'developer_equity':n*Q(d['developer_equity_per_unit']),'bank_loan':b['loan'],'grant_admin':b['admin'],'levy_each':b['levy']}
            for k,v in basics.items():compare(a[k],v,k)
            if b['face'] is None:continue
            mapped={'debt_face':'face','debt_payoffs':'debt','equity_payoffs':'equity_payoffs','debt_value':'debt_pv','equity_value':'equity_pv','bank_final':'bank_total','developer_final':'developer_total','initial_uses':'initial_resource_uses'}
            for k,v in mapped.items():compare(a[k],b[v],k)
            compare(a['bank_cash'],Q(d['bank_endowment'])-b['loan'],'bank cash')
            compare(a['private_npv'],b['equity_pv']-n*Q(d['developer_equity_per_unit']),'private NPV');compare(a['bank_npv'],0,'bank NPV')
            compare(a['initial_resource_total'],Q(d['bank_endowment'])+Q(d['developer_endowment'])+2*Q(d['household_current_cash']),'initial resources')
            for key,sub in [('poor_values','poor'),('rich_values','rich'),('social_values','total'),('direct_resource_values','direct')]:compare(a[key],[x[sub] for x in b['welfare']],key)
            compare(a['expected_value'],b['prior_value'],'prior value')
            for s,account in enumerate(a['state_accounts']):
                bill=n*Q(d['revenue_per_unit'][s]);oper=n*Q(d['operating_cost']);income=Q(d['household_future_income'])
                compare(account,{'service_bill':bill,'operating_resources':oper,'household_consumption':[income-bill,income],'goods_total_including_operations':b['future_resource_supply'],'available_goods':b['future_resource_supply'],'debt_shortfall':b['face']-b['debt'][s]},'goods account')
            comp=a['robust_compensation'];low,up=b['transfer_interval'];good=b['feasible'] and low<=up
            want={'lower':low,'upper':up,'feasible':good}
            if good:
                cost=low*Q(d['transfer_admin_rate']);want.update(transfer=low,real_admin=cost,poor=[x['poor']-low-cost for x in b['welfare']],rich=[x['rich']+low for x in b['welfare']],total=[x['total']-cost for x in b['welfare']])
            compare(comp,want,'compensation')
            if b['feasible']:
                best=[max(r['welfare'][s]['total'] for r in ref['rows'] if r['feasible']) for s in range(2)]
                compare(a['regrets'],[best[s]-b['welfare'][s]['total'] for s in range(2)],'regrets');compare(a['max_regret'],b['worst_regret'],'worst regret')
        for name,k,field in [('expected_optimum','bayes','prior_value'),('minimax_regret','minimax','worst_regret')]:
            choices=ref['choices'][k];compare(out[name],{'quantities':choices,'value':next(r[field] for r in ref['rows'] if r['n']==choices[0])},name)
        compare(out['state_best_values'],[max(r['welfare'][s]['total'] for r in ref['rows'] if r['feasible']) for s in range(2)],'endpoint best')
        compare(out['robust_compensable_quantities'],[r['n'] for r in ref['rows'] if r['feasible'] and r['transfer_interval'][0]<=r['transfer_interval'][1]],'robust quantities')
        # Envelope independently verified by line intersections and midpoints of every segment.
        feasible=[r for r in ref['rows'] if r['feasible']];cuts={Q(0),Q(1)}
        for r in feasible:
            for s in feasible:
                a,b=[x['total'] for x in r['welfare']];c,e=[x['total'] for x in s['welfare']]
                if b-a!=e-c:
                    w=(c-a)/(b-a-e+c)
                    if 0<=w<=1:cuts.add(w)
        cuts=sorted(cuts);probes=cuts+[(a+b)/2 for a,b in zip(cuts,cuts[1:])]
        for w in probes:
            vals={r['n']:(1-w)*r['welfare'][0]['total']+w*r['welfare'][1]['total'] for r in feasible};best=max(vals.values())
            claimed=sorted(e['quantity'] for e in out['forecast_envelope'] if Q(e['high_weight_interval'][0])<=w<=Q(e['high_weight_interval'][1]))
            compare(claimed,sorted(n for n,v in vals.items() if v==best),'envelope boundary/interior')
    result=reader.run(data);require(data==original,'input mutation');require(result==json.loads((root/READERS[2]).read_text()),'reference exact JSON')
    variants=[{}, {'bank_loan_cap':3},{'bank_loan_cap':'399/100'},{'bank_loan_cap':0},{'selection_interval':[0,1]},{'transfer_admin_rate':0},{'high_endpoint_weight':'8/9'},{'high_endpoint_weight':'889/1000'},{'high_endpoint_weight':0},{'high_endpoint_weight':1},{'quantities':[2,0,1]},{'household_current_cash':'1/2'},{'treasury_limit':1},{'developer_endowment':0},{'revenue_per_unit':[5,3]}]
    for change in variants:
        d=deepcopy(data);d.update(change);audit(d,reader.run(d))
    # Independent mask solver at debt kinks, equal cash, zero cash and maximum pledgeability.
    debt_checks=0
    for cash in [(Q(2),Q(5)),(Q(0),Q(5)),(Q(3),Q(3))]:
        q=(Q(2,5),Q(1,2));cap=sum(a*b for a,b in zip(q,cash))
        for loan in [Q(0),cap/2,sum(q)*min(cash),cap]:
            f=reader.debt_face(q,cash,loan)
            require(f>=0 and sum(a*min(f,b) for a,b in zip(q,cash))==loan,'debt boundary price')
            if f:require(sum(a*min(f/2,b) for a,b in zip(q,cash))<loan,'smallest fair face')
            debt_checks+=1
        try:reader.debt_face(q,cash,cap+Q(1,100))
        except ValueError:debt_checks+=1
        else:raise ValueError('excess pledge accepted')
    rejected=0
    for key,bad in [('bank_loan_cap',True),('bank_loan_cap',0.5),('bank_loan_cap','1/0'),('bank_loan_cap','1e0'),('bank_loan_cap',-1),('bank_loan_cap',10001),('state_probabilities',[0,1]),('state_probabilities',['1/2','1/3']),('sdf',[1,0]),('selection_interval',[2,0]),('quantities',[0,1,True]),('quantities',[1]),('quantities',[0,1,1]),('quantities',[0,11]),('grant',3),('revenue_per_unit',[0,3]),('high_endpoint_weight','101/100'),('conventions',{}),('synthetic',1)]:
        d=deepcopy(data);d[key]=bad
        try:reader.run(d)
        except (ValueError,TypeError,KeyError):rejected+=1
        else:raise ValueError('invalid domain accepted: '+key)
    aliases=0;cli_runs=0
    with tempfile.TemporaryDirectory(prefix='integrated-peer-reader-') as td:
        folder=Path(td)
        for name in READERS:(folder/Path(name).name).write_bytes((root/name).read_bytes())
        program=folder/'integrated-case-analysis.py';saved={p.name:p.read_bytes() for p in folder.iterdir()}
        command=[sys.executable,'-I','-B','-O',str(program)]
        for mode in ['default','explicit','stress']:
            args=[]
            if mode=='explicit':args=['--output',str(folder/'own.json')]
            if mode=='stress':
                d=deepcopy(data);d['bank_loan_cap']=3;(folder/'stress.json').write_text(json.dumps(d));args=['--input',str(folder/'stress.json'),'--output',str(folder/'stress-out.json')]
            p=subprocess.run(command+args,cwd='/',capture_output=True);require(p.returncode==0 and not p.stdout and not p.stderr,'silent actual reader CLI');cli_runs+=1
            out=folder/({'default':'integrated-case-output.json','explicit':'own.json','stress':'stress-out.json'}[mode]);require(json.loads(out.read_text())==reader.run(d if mode=='stress' else data),'actual CLI values')
        targets=[folder/('integrated-case-'+s) for s in ['inputs.json','analysis.py','README.txt','manifest.json']]+[folder/'stress.json']
        for target in targets:
            for mode in ['direct','resolved','symlink','hardlink']:
                alias=target if mode=='direct' else (folder/'..'/folder.name/target.name if mode=='resolved' else folder/('protected-'+mode))
                if mode=='symlink':alias.symlink_to(target)
                if mode=='hardlink':os.link(target,alias)
                args=['--output',str(alias)]
                if target.name=='stress.json':args=['--input',str(target),*args]
                before=target.read_bytes();p=subprocess.run(command+args,cwd='/',capture_output=True)
                require(p.returncode!=0 and b'protected' in p.stderr and target.read_bytes()==before,'output alias rejection');aliases+=1
                if mode in ('symlink','hardlink'):alias.unlink()
        require(all((folder/n).read_bytes()==b for n,b in saved.items()),'reader frozen bytes unchanged')
    return {'status':'passed','runtime_files':11,'exact_scalar_comparisons':count,'independent_scenarios':len(variants),'debt_boundary_checks':debt_checks,'invalid_domains_rejected':rejected,'protected_alias_rejections':aliases,'actual_reader_cli_runs':cli_runs,'written_tasks':7,'oral_transfers':2,'retention_items':5}

if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
