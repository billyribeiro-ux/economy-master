"""Separate primitive reconstruction and portable reader review; no author checker execution."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
from html.parser import HTMLParser
from copy import deepcopy
from contextlib import redirect_stdout, redirect_stderr
import hashlib, importlib.util, io, json, math, os, re, subprocess, sys, tempfile

FILES=['content/assessments/parts/v14-project.html']+['content/projects/v14-assessment-'+s for s in ['inputs.json','analysis.py','output.json','manifest.json','README.txt']]+['scripts/check_v14_project.py','content/reviews/v14-project-sources.json','content/reviews/v14-project-author.json','scripts/check_v14_project_peer.py','content/reviews/v14-project-peer.json']
def need(x,why):
    if not x:raise ValueError(why)
def strict(s):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate JSON key');out[k]=v
        return out
    return json.loads(s,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def dec(q):
    q=F(q);return D(q.numerator)/D(q.denominator)
def solve(a,b):
    # Forward elimination and back substitution, independently of reader Gauss-Jordan.
    m=[list(row)+[v] for row,v in zip(a,b)];n=len(m)
    for k in range(n):
        p=max(range(k,n),key=lambda i:abs(m[i][k]));need(m[p][k]!=0,'singular system');m[k],m[p]=m[p],m[k]
        for i in range(k+1,n):
            scale=m[i][k]/m[k][k]
            for j in range(k,n+1):m[i][j]-=scale*m[k][j]
    v=[b[0]*0]*n
    for i in reversed(range(n)):v[i]=(m[i][-1]-sum(m[i][j]*v[j] for j in range(i+1,n)))/m[i][i]
    return v
def log_interval(c,terms):
    need(c>0 and type(terms)is int and terms>=1,'log domain')
    exponent=0
    while c<1:c*=2;exponent-=1
    while c>=2:c/=2;exponent+=1
    def series(t):
        power=t;total=F(0)
        for j in range(terms):total+=2*power/F(2*j+1);power*=t*t
        return total,2*abs(power)/((2*terms+1)*(1-t*t))
    a,e=series((c-1)/(c+1));b,f=series(F(1,3));return a+exponent*b,e+abs(exponent)*f

def classify(q):
    n=len(q)
    def visit(i):
        seen={i};front=[i]
        while front:
            k=front.pop()
            for j in range(n):
                if q[k][j]>0 and j not in seen:seen.add(j);front.append(j)
        return seen
    reachable=[visit(i) for i in range(n)];groups=[];remaining=set(range(n))
    while remaining:
        i=min(remaining);group=sorted(j for j in remaining if j in reachable[i] and i in reachable[j]);groups.append(group);remaining-=set(group)
    closed=[c for c in groups if all(not q[i][j] for i in c for j in set(range(n))-set(c))];laws=[];periods=[]
    for c in closed:
        # Positive return lengths up to 2*n suffice here; each supplied recurrent class has a self-loop.
        support={c[0]};period=0
        for t in range(1,2*n+1):
            support={j for i in support for j in c if q[i][j]>0}
            if c[0] in support:period=math.gcd(period,t)
        periods.append(period);m=len(c)
        a=[[F(int(i==j))-q[c[j]][c[i]] for j in range(m)] for i in range(m)];a[-1]=[F(1)]*m
        w=solve(a,[F(0)]*(m-1)+[F(1)]);full=[F(0)]*n
        for i,x in zip(c,w):full[i]=x
        need(all(sum(full[i]*q[i][j] for i in range(n))==full[j] for j in range(n)),'invariant equation');laws.append(full)
    return dict(classes=groups,closed_classes=closed,periods=periods,invariant_laws=laws,unique=len(closed)==1,converges_from_all_initial=len(closed)==1 and periods==[1])

def scenario(A,Y,P,beta,R,tr,mu,W,payoff,tol,maxit,coarse,terms):
    n=2*len(A);c=[[Y[i%2]+tr[i%2]+R*A[i//2]-ap for ap in A] for i in range(n)];acts=[[j for j,x in enumerate(row) if x>0] for row in c]
    need(all(acts),'empty action set');reward=[[dec(x).ln() if x>0 else None for x in row] for row in c];bd=dec(beta);pd=[[dec(x) for x in row] for row in P]
    policy=[row[0] for row in acts]
    # Howard policy improvement with 60-digit true logs, rather than author enumeration or reader value iteration.
    for _ in range(100):
        q=[[F(0)]*n for i in range(n)]
        for i,j in enumerate(policy):q[i][2*j:2*j+2]=P[i%2]
        M=[[F(int(i==j))-beta*q[i][j] for j in range(n)] for i in range(n)]
        value=solve([[dec(x) for x in row] for row in M],[reward[i][policy[i]] for i in range(n)])
        scores=[[reward[i][j]+bd*sum(pd[i%2][z]*value[2*j+z] for z in range(2)) if j in acts[i] else None for j in range(len(A))] for i in range(n)]
        improved=[max(acts[i],key=lambda j:scores[i][j]) for i in range(n)]
        if improved==policy:break
        policy=improved
    else:raise ValueError('policy iteration failed')
    need(all(value[i]>=scores[i][j]-D('1e-50') for i in range(n) for j in acts[i]),'global Bellman deviations')
    intervals=[[log_interval(x,terms) if x>0 else None for x in row] for row in c]
    center=solve(M,[intervals[i][policy[i]][0] for i in range(n)]);err=max(intervals[i][policy[i]][1] for i in range(n))/(1-beta)
    need(all(abs(value[i]-dec(center[i]))<=dec(err)+D('1e-50') for i in range(n)),'true logarithm enclosure')
    gaps=[]
    for i in range(n):
        row=[]
        for j in range(len(A)):
            if j not in acts[i]:row.append(None)
            elif j==policy[i]:row.append(dict(center=0.,lower=0.))
            else:
                ac,ae=intervals[i][j];gap=center[i]-ac-beta*sum(P[i%2][z]*center[2*j+z] for z in range(2));lower=gap-(1+beta)*err-ae
                need(lower>0,'non-strict finite optimum');row.append(dict(center=float(gap),lower=float(lower)))
        gaps.append(row)
    minimum=min(x['lower'] for i,row in enumerate(gaps) for j,x in enumerate(row) if x is not None and j!=policy[i]);cons=[c[i][j] for i,j in enumerate(policy)];ap=[A[j] for j in policy];graph=classify(q)
    def account(w):
        a=sum(w[i]*A[i//2] for i in range(n));nxt=sum(w[i]*ap[i] for i in range(n));C=sum(w[i]*cons[i] for i in range(n));y=sum(w[i]*Y[i%2] for i in range(n));t=sum(w[i]*tr[i%2] for i in range(n));foreign=W-R*a+nxt
        need(C+foreign==y+t+W,'world resources')
        return dict(mean_assets=a,next_assets=nxt,consumption=C,income=y,net_transfer=t,foreign_consumption=foreign,world_residual=C+foreign-y-t-W,funding_feasible=foreign>=0)
    pricing=[]
    for i,j in enumerate(policy):
        m=[beta*cons[i]/cons[2*j+z] for z in range(2)];p=P[i%2];unit=sum(p[z]*m[z] for z in range(2));risky=sum(p[z]*m[z]*payoff[z] for z in range(2));mean=sum(p[z]*payoff[z] for z in range(2))
        pricing.append(dict(sdf=m,payoff_price=risky,marginal_bond_price=unit,market_bond_price=1/R,covariance=risky-unit*mean,expected_payoff=mean,expected_return=mean/risky))
    def bell(v):return [max(reward[i][j]+bd*sum(pd[i%2][z]*v[2*j+z] for z in range(2)) for j in acts[i]) for i in range(n)]
    v=[D(0)]*n;cv=None
    for it in range(1,maxit+1):
        nv=bell(v);step=max(abs(a-b) for a,b in zip(v,nv));v=nv
        if it==coarse:cv=v[:]
        if step<=dec(tol):break
    if cv is None:cv=v[:]
    resid=max(abs(a-b) for a,b in zip(v,bell(v)));cr=max(abs(a-b) for a,b in zip(cv,bell(cv)));distance=max(abs(a-b) for a,b in zip(cv,value));need(distance<=cr/(1-bd),'residual bound')
    path=[];w=mu[:]
    for date in range(5):path.append(dict(date=date,distribution=w[:],account=account(w)));w=[sum(w[i]*q[i][j] for i in range(n)) for j in range(n)]
    funded=min(W-R*A[i//2]+ap[i] for i in range(n))>=0
    return dict(status='certified' if funded and graph['converges_from_all_initial'] else 'not_certified',reason=None if funded else 'foreign funding shortfall',assets=A,transfer=tr,gross_return=R,consumption_by_action=[[x if x>0 else None for x in row] for row in c],feasible_actions=acts,policy_indices=policy,policy_assets=ap,consumption=cons,transition=q,value=[float(x) for x in value],value_error_bound=float(err),action_gaps=gaps,minimum_strict_gap_lower=minimum,iterations=it,iteration_converged=step<=dec(tol),iteration_residual=float(resid),iteration_value_bound=float(resid/(1-bd)),coarse_residual=float(cr),coarse_value_bound=float(cr/(1-bd)),coarse_actual_distance=float(distance),graph=graph,pricing=pricing,initial_welfare=float(sum(dec(w)*v for w,v in zip(mu,value))),initial_account=account(mu),stationary_accounts=[account(w) for w in graph['invariant_laws']],transition_path=path,funded_all_states=funded)

def oracle(d):
    with localcontext() as ctx:
        ctx.prec=60
        beta,R,Rs,W,t,tol=[F(d[k]) for k in ['discount','gross_return','stress_return','foreign_endowment','low_income_transfer','iteration_tolerance']];Y=list(map(F,d['income']));A=list(map(F,d['assets']));Ar=list(map(F,d['refined_assets']));mu=list(map(F,d['initial']));payoff=list(map(F,d['payoff_by_next_income']));train=d['training_counts'];held=d['heldout_counts'];P=[[F(x,sum(row)) for x in row] for row in train];alt=[list(map(F,row)) for row in d['alternative_transition']];pi=[P[1][0]/(P[0][1]+P[1][0]),P[0][1]/(P[0][1]+P[1][0])];refmu=[mu[2*A.index(a)+z] if a in A else F(0) for a in Ar for z in range(2)]
        scenarios={}
        for name,grid,rate,tr,initial in [('baseline',A,R,[F(0),F(0)],mu),('redistribution',A,R,[t,-t*pi[0]/pi[1]],mu),('rate_stress',A,Rs,[F(0),F(0)],mu),('refined_grid',Ar,R,[F(0),F(0)],refmu)]:scenarios[name]=scenario(grid,Y,P,beta,rate,tr,initial,W,payoff,tol,d['max_iterations'],d['coarse_iterations'],d['log_series_terms'])
        def ll(c,p):return float(sum(D(c[i][j])*dec(p[i][j]).ln() for i in range(2) for j in range(2)))
        estimation=dict(training_log_likelihood=ll(train,P),training_alternative_log_likelihood=ll(train,alt),heldout_log_likelihood=ll(held,P),heldout_alternative_log_likelihood=ll(held,alt),heldout_empirical_transition=[[F(x,sum(row)) for x in row] for row in held],training_row_counts=list(map(sum,train)),heldout_row_counts=list(map(sum,held)))
        comparisons={name:dict(common_initial_welfare_change=s['initial_welfare']-scenarios['baseline']['initial_welfare'],normalized_change=float(1-beta)*(s['initial_welfare']-scenarios['baseline']['initial_welfare'])) for name,s in scenarios.items()}
        return dict(model=d['model'],status='certified',synthetic=True,fitted_transition=P,income_stationary=pi,estimation=estimation,scenarios=scenarios,comparisons=comparisons)

class Markup(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.prompts={};self.solutions=[];self.domains={};self.sources={};self.inputs={};self.outputs={};self.capture=None;self.parts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id'in a:self.ids.append(a['id'])
        if tag=='li' and 'data-points'in a:self.prompts[a['id']]=int(a['data-points'])
        if 'data-solution-for'in a:self.solutions.append(a['data-solution-for'])
        if 'data-domain'in a:self.domains[a['data-domain']]=int(a['data-points'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for k in ['data-input','data-check']:
            if k in a:need(self.capture is None,'nested marker');self.capture=(tag,k,a[k]);self.parts=[]
    def handle_data(self,s):
        if self.capture:self.parts.append(s)
    def handle_endtag(self,tag):
        if self.capture and tag==self.capture[0]:
            _,kind,key=self.capture;target=self.inputs if kind=='data-input' else self.outputs;need(key not in target,'duplicate marker');target[key]=''.join(self.parts).strip();self.capture=None

def visible(text):
    tokens=re.findall(r'[-+]?\d+(?:/\d+|\.\d+)?|[(),]',text);need(''.join(tokens)==re.sub(r'\s','',text),'visible numeric grammar');pos=0
    def parse():
        nonlocal pos
        if tokens[pos]=='(':
            pos+=1;out=[parse()]
            while tokens[pos]==',':pos+=1;out.append(parse())
            need(tokens[pos]==')','close tuple');pos+=1;return out
        v=F(tokens[pos]);pos+=1;return v
    result=parse();need(pos==len(tokens),'trailing tokens');return result

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];before={p:(root/p).read_bytes() for p in FILES};count=0;rejects=0;cli_runs=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,dict):
            need(isinstance(b,dict) and set(a)==set(b),label+' keys')
            for k in a:eq(a[k],b[k],label+'.'+k)
        elif isinstance(a,list):
            need(isinstance(b,list) and len(a)==len(b),label+' length')
            for i,(x,y) in enumerate(zip(a,b)):eq(x,y,label+'.'+str(i))
        elif isinstance(a,F):need(F(b)==a,label+' rational');count+=1
        elif isinstance(a,float):
            need(isinstance(b,(float,int,F)) and math.isfinite(float(b)),label+' finite')
            tolerance=1e-12*abs(a) if label.endswith('value_error_bound') else 1e-10
            need(abs(a-float(b))<=tolerance,label+' numeric');count+=1
        else:need(type(a)is type(b) and a==b,label+' equality');count+=1
    def reject(fn):
        nonlocal rejects
        try:fn()
        except (ValueError,TypeError,KeyError,ZeroDivisionError,json.JSONDecodeError):rejects+=1
        else:raise ValueError('invalid domain accepted')
    data=strict(before[FILES[1]]);reference=strict(before[FILES[3]]);expected=oracle(data)
    need(set(reference)==set(expected)|{'limits'},'output schema');eq(expected,{k:v for k,v in reference.items() if k!='limits'},'independent')
    need(len(reference['limits'])==4 and all(isinstance(x,str) and x for x in reference['limits']),'scope limits')
    markup=Markup();markup.feed(before[FILES[0]].decode());need(len(markup.ids)==len(set(markup.ids)) and all(x=='project' or x.startswith('v14-project-') for x in markup.ids),'ID scope')
    need(list(markup.prompts)==['v14-project-p'+str(i) for i in range(1,8)] and list(markup.prompts.values())==[10,20,10,20,20,10,10] and sorted(markup.solutions)==sorted(markup.prompts),'seven solved prompts')
    need(len(markup.domains)==5 and set(markup.domains.values())=={20},'five domains')
    def numeric(x):
        if isinstance(x,list):return [numeric(v) for v in x]
        return F(x)
    for k,v in markup.inputs.items():eq(numeric(data[k]),visible(v),'input.'+k)
    for path,v in markup.outputs.items():
        value=reference
        for part in path.split('.'):value=value[int(part)] if isinstance(value,list) else value[part]
        eq(visible(v),numeric(value),'visible.'+path) if '/' in v and '.' not in v else None
        # Displayed decimal rounding receives its declared ten-decimal tolerance.
        def rounded(a,b):
            nonlocal count
            if isinstance(a,list):need(isinstance(b,list) and len(a)==len(b),'display shape');[rounded(x,y) for x,y in zip(a,b)]
            else:need(abs(float(a)-float(F(b)))<=5.01e-11,'display '+path);count+=1
        rounded(visible(v),value)
    sources=strict(before[FILES[7]]);eq({s['id']:s['url'] for s in sources['sources']},markup.sources,'source URLs')
    manifest=strict(before[FILES[4]])
    for name,binding in manifest['payloads'].items():
        blob=(root/'content/projects'/name).read_bytes();need(len(blob)==binding['bytes'] and hashlib.sha256(blob).hexdigest()==binding['sha256'],'manifest binding')
    for rec in [strict(before[FILES[8]]),strict(before[FILES[10]])]:
        for name,binding in rec['payload_bindings'].items():
            blob=(root/name).read_bytes();need(len(blob)==binding['bytes'] and hashlib.sha256(blob).hexdigest()==binding['sha256'],'review binding '+name)
    peer=strict(before[FILES[10]]);need(set(peer['payload_bindings'])==set(FILES[:-1]),'complete peer bindings')
    # Only now, after reconstruction, execute the independently reviewed READER; never the author checker.
    spec=importlib.util.spec_from_file_location('v14_project_peer_reader',root/FILES[2]);module=importlib.util.module_from_spec(spec);out=io.StringIO();err=io.StringIO();sys.dont_write_bytecode=True
    with redirect_stdout(out),redirect_stderr(err):spec.loader.exec_module(module);arg=deepcopy(data);actual=module.run(arg)
    need(not out.getvalue() and not err.getvalue() and arg==data,'quiet immutable reader');eq(reference,actual,'reader reference')
    for key,bad in [('discount','1'),('discount','0'),('discount',True),('gross_return','0'),('stress_return','-1'),('income',['1','1']),('assets',['1/4','-1/4']),('refined_assets',['-1/4','0','1/2']),('initial',['1','0','0','0']),('training_counts',[[True,20],[20,80]]),('training_counts',[[0,0],[20,80]]),('heldout_counts',[[1,-1],[20,80]]),('alternative_transition',[['0','1'],['1/5','4/5']]),('low_income_transfer','3/2'),('foreign_endowment','-1'),('payoff_by_next_income',['0','1']),('iteration_tolerance','0'),('max_iterations',False),('coarse_iterations',2001),('log_series_terms',15)]:
        arg=deepcopy(data);arg[key]=bad;reject(lambda arg=arg:module.run(arg))
    reject(lambda:strict('{"a":1,"a":2}'));reject(lambda:strict('{"a":NaN}'));reject(lambda:log_interval(F(0),24));reject(lambda:solve([[F(0)]],[F(1)]))
    eq(dict(classes=[[0],[1]],closed_classes=[[0],[1]],periods=[1,1],invariant_laws=[[F(1),F(0)],[F(0),F(1)]],unique=False,converges_from_all_initial=False),module.graph([[F(1),F(0)],[F(0),F(1)]]),'absorbing boundary')
    eq(dict(classes=[[0,1]],closed_classes=[[0,1]],periods=[2],invariant_laws=[[F(1,2),F(1,2)]],unique=True,converges_from_all_initial=False),module.graph([[F(0),F(1)],[F(1),F(0)]]),'periodic boundary')
    # Real five-file portable CLIs and protected aliases, in both Python modes.
    for optimized in [False,True]:
        with tempfile.TemporaryDirectory(prefix='v14-project-peer-reader-') as td:
            folder=Path(td)
            for p in FILES[1:6]:(folder/Path(p).name).write_bytes(before[p])
            implementation=folder/Path(FILES[2]).name;inp=folder/Path(FILES[1]).name;output=folder/Path(FILES[3]).name
            prefix=[sys.executable]+(['-O'] if optimized else [])+['-B',str(implementation)]
            def execute(args,ok):
                nonlocal cli_runs
                result=subprocess.run(prefix+args,cwd='/',capture_output=True,text=True);cli_runs+=1;need((result.returncode==0)==ok,'CLI status');need(not result.stdout,'CLI stdout')
                if ok:need(not result.stderr,'CLI stderr')
            execute([],True);eq(reference,strict(output.read_text()),'default CLI')
            custom=folder/'custom-input.json';custom.write_bytes(before[FILES[1]]);target=folder/'result.json';execute(['--input',str(custom),'--output',str(target)],True);eq(reference,strict(target.read_text()),'explicit CLI')
            protected=[inp,implementation,folder/'v14-assessment-README.txt',folder/'v14-assessment-manifest.json',custom];snap={str(p):p.read_bytes() for p in protected};sub=folder/'normalizer';sub.mkdir()
            for i,p in enumerate(protected):
                symlink=folder/('symlink-'+str(i));symlink.symlink_to(p);hard=folder/('hardlink-'+str(i));os.link(p,hard)
                for alias in [p,sub/'..'/p.name,symlink,hard]:
                    execute(['--input',str(custom),'--output',str(alias)],False);rejects+=1
                    need(all(Path(k).read_bytes()==v for k,v in snap.items()),'protected bytes changed')
            bad=folder/'bad.json';invalid=deepcopy(data);invalid['discount']='1';bad.write_text(json.dumps(invalid));absent=folder/'absent.json';execute(['--input',str(bad),'--output',str(absent)],False);rejects+=1;need(not absent.exists(),'malformed output written')
            failure=deepcopy(data);failure['foreign_endowment']='0';bad.write_text(json.dumps(failure));execute(['--input',str(bad),'--output',str(absent)],True);failed=strict(absent.read_text());need(failed['status']=='not_certified' and any(s['reason']=='foreign funding shortfall' for s in failed['scenarios'].values()),'honest funding failure')
            need(all(Path(k).read_bytes()==v for k,v in snap.items()),'final protected bytes')
    need({p:(root/p).read_bytes() for p in FILES}==before,'runtime mutation')
    result=dict(status='passed',component='v14-project-peer',comparisons=count,domain_rejections=rejects,solved_tasks=7,points=100,domains=5,input_markers=len(markup.inputs),output_markers=len(markup.outputs),reader_cli_runs=cli_runs,runtime_files=len(FILES),unresolved_findings=0)
    json.dumps(result,allow_nan=False);return result

if __name__=='__main__':check()
