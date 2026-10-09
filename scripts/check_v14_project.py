"""Independent V14 project oracle and actual portable-reader execution checks."""
import ast
from contextlib import redirect_stdout,redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import gcd,isfinite,log
from pathlib import Path
import io,json,os,subprocess,sys,tempfile

FILES=('content/assessments/parts/v14-project.html','content/projects/v14-assessment-inputs.json','content/projects/v14-assessment-analysis.py','content/projects/v14-assessment-output.json','content/projects/v14-assessment-manifest.json','content/projects/v14-assessment-README.txt','scripts/check_v14_project.py','content/reviews/v14-project-author.json','content/reviews/v14-project-sources.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def numeric(s):
    def rec(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return n.value
        if isinstance(n,(ast.Tuple,ast.List)):return [rec(x) for x in n.elts]
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*rec(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return F(rec(n.left))/F(rec(n.right))
        raise ValueError('numeric HTML marker')
    return rec(ast.parse(s.strip(),mode='eval').body)
class HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.pending=[];self.inputs={};self.outputs={};self.ids=[];self.tasks=[];self.sol=[];self.domains=[];self.sources={};self.downloads=[]
    def handle_starttag(self,t,attrs):
        d=dict(attrs)
        if 'id' in d:need(d['id'] not in self.ids,'duplicate id');self.ids.append(d['id']);need(d['id']=='project' or d['id'].startswith('v14-project-'),'ID prefix')
        need(t!='h1','no new h1')
        if t=='li' and d.get('id','').startswith('v14-project-p'):self.tasks.append((d['id'],int(d['data-points'])))
        if 'data-solution-for' in d:
            need(any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.stack),'solution enclosure');self.sol.append(d['data-solution-for'])
        if 'data-domain' in d:self.domains.append((d['data-domain'],int(d['data-points'])))
        if 'data-source' in d:self.sources[d['data-source']]=d['href']
        if 'download' in d:self.downloads.append(d['href']);need('/' not in d['href'],'flat download')
        for key,target in (('data-input',self.inputs),('data-check',self.outputs)):
            if key in d:
                k=d[key];need(k not in target,'duplicate marker');target[k]='';self.pending.append((target,k,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,d))
    def handle_data(self,s):
        for dest,k,n in self.pending:dest[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'HTML balance');self.stack.pop();self.pending=[p for p in self.pending if p[2]<len(self.stack)]
def at(x,path):
    for p in path.split('.'):x=x[int(p)] if isinstance(x,list) else x[p]
    return x
def gauss(M,b):
    a=[list(row)+[x] for row,x in zip(M,b)];n=len(a)
    for j in range(n):
        k=max(range(j,n),key=lambda i:abs(a[i][j]));need(a[k][j]!=0,'oracle singular system');a[j],a[k]=a[k],a[j];q=a[j][j]
        for k in range(j,n+1):a[j][k]/=q
        for i in range(n):
            if i!=j:
                q=a[i][j]
                for k in range(j,n+1):a[i][k]-=q*a[j][k]
    return [r[-1] for r in a]
def independent_graph(Q):
    n=len(Q);closed=[]
    # Enumerate every subset; closed + internally mutually reachable defines recurrent classes.
    for bits in range(1,1<<n):
        S=[i for i in range(n) if bits>>i&1]
        if any(Q[i][j]>0 for i in S for j in range(n) if j not in S):continue
        good=True
        for i in S:
            seen={i}
            for _ in range(n):seen|={j for k in tuple(seen) for j in S if Q[k][j]>0}
            if seen!=set(S):good=False;break
        if good:closed.append(S)
    laws=[];periods=[]
    for S in closed:
        m=len(S);M=[[Q[S[j]][S[i]]-F(i==j) for j in range(m)] for i in range(m-1)]+[[F(1)]*m];b=[F(0)]*(m-1)+[F(1)];small=gauss(M,b);law=[F(0)]*n
        for i,x in zip(S,small):law[i]=x
        laws.append(law);reach={S[0]};period=0
        for k in range(1,2*n*n+1):
            reach={j for i in reach for j in S if Q[i][j]>0}
            if S[0] in reach:period=gcd(period,k)
        periods.append(period)
    return closed,laws,periods

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];payload={p:(root/p).read_bytes() for p in FILES};D=json.loads(payload[FILES[1]]);out=json.loads(payload[FILES[3]]);manifest=json.loads(payload[FILES[4]]);author=json.loads(payload[FILES[7]]);sources=json.loads(payload[FILES[8]]);count={'comparisons':0,'oracle_policies':0,'rejected_inputs':0,'actual_cli_alias_rejections':0,'actual_reader_cli_successes':0,'actual_malformed_cli_rejections':0,'actual_valid_failure_cli_diagnostics':0}
    def eq(x,y,label='independent equality',tol=8e-9):
        if isinstance(x,str):
            try:x=F(x)
            except (ValueError,ZeroDivisionError):pass
        if isinstance(y,str):
            try:y=F(y)
            except (ValueError,ZeroDivisionError):pass
        if isinstance(x,list) or isinstance(y,list):
            need(isinstance(x,list) and isinstance(y,list) and len(x)==len(y),label+' shape')
            for a,b in zip(x,y):eq(a,b,label,tol)
        elif isinstance(x,dict) or isinstance(y,dict):
            need(isinstance(x,dict) and isinstance(y,dict) and set(x)==set(y),label+' keys')
            for k in x:eq(x[k],y[k],label+'.'+k,tol)
        elif x is None or y is None or isinstance(x,(bool,str)) or isinstance(y,(bool,str)):
            count['comparisons']+=1;need(x==y,label)
        else:
            count['comparisons']+=1;need(isfinite(float(x)) and isfinite(float(y)) and abs(float(x)-float(y))<=tol*max(1,abs(float(y))),label+str((x,y)))
    bindings=author['payload_bindings'];need(set(bindings)==set(FILES)-{FILES[7]},'author binds other eight')
    for p,b in bindings.items():eq(b,{'bytes':len(payload[p]),'sha256':sha256(payload[p]).hexdigest()},'author binding')
    four=[FILES[i] for i in (1,2,3,5)];need(set(manifest['payloads'])=={Path(p).name for p in four},'manifest exact four')
    for p in four:eq(manifest['payloads'][Path(p).name],{'bytes':len(payload[p]),'sha256':sha256(payload[p]).hexdigest()},'manifest binding')
    doc=HTML();doc.feed(payload[FILES[0]].decode());need(not doc.stack,'unclosed HTML');ids=['v14-project-p'+str(i) for i in range(1,8)];eq([i for i,p in doc.tasks],ids);eq(doc.sol,ids);eq(sum(p for i,p in doc.tasks),100);eq([p for i,p in doc.domains],[20]*5);eq([i for i,p in doc.domains],['dynamic_distribution','labor_policy','pricing_investment','liquidity_international','quantitative_research']);need(set(doc.downloads)=={Path(FILES[i]).name for i in (1,2,3,4,5)},'five downloads')
    src={s['id']:s for s in sources['sources']};need(set(src)==set(doc.sources),'source routes')
    for k,url in doc.sources.items():eq(src[k]['url'],url);need(src[k]['prior_inspector'] and src[k]['verified_scope'] and src[k]['limits'],'scoped prior provenance')
    for k,s in doc.inputs.items():eq(numeric(s),at(D,k),'HTML primitive '+k)
    for k,s in doc.outputs.items():eq(numeric(s),at(out,k),'HTML output '+k)
    beta=F(D['discount']);Y=list(map(F,D['income']));W=F(D['foreign_endowment']);A=list(map(F,D['assets']));Ar=list(map(F,D['refined_assets']));train=D['training_counts'];held=D['heldout_counts'];P=[[F(x,sum(row)) for x in row] for row in train];alt=[[F(x) for x in row] for row in D['alternative_transition']];pi=[P[1][0]/(P[0][1]+P[1][0]),P[0][1]/(P[0][1]+P[1][0])];eq(out['fitted_transition'],P);eq(out['income_stationary'],pi)
    for sample,counts in [('training',train),('heldout',held)]:
        for suffix,pr in [('',P),('_alternative',alt)]:eq(out['estimation'][sample+suffix+'_log_likelihood'],sum(counts[i][j]*log(float(pr[i][j])) for i,j in product(range(2),repeat=2)))
        eq(out['estimation'][sample+'_row_counts'],[sum(row) for row in counts])
    eq(out['estimation']['heldout_empirical_transition'],[[F(x,sum(r)) for x in r] for r in held])
    t=F(D['low_income_transfer']);payoff=list(map(F,D['payoff_by_next_income']));initial=list(map(F,D['initial']));oracle_values={}
    for name in ('baseline','redistribution','rate_stress','refined_grid'):
        s=out['scenarios'][name];grid=Ar if name=='refined_grid' else A;R=F(D['stress_return'] if name=='rate_stress' else D['gross_return']);tr=[t,-t*pi[0]/pi[1]] if name=='redistribution' else [F(0),F(0)];states=list(product(grid,range(2)));n=len(states);mu=[initial[2*A.index(a)+z] if a in A else F(0) for a,z in states];C=[[Y[z]+tr[z]+R*a-b for b in grid] for a,z in states];acts=[[j for j,c in enumerate(row) if c>0] for row in C];certified=[]
        def transition(g):return [[P[z][zp] if grid[g[i]]==b else F(0) for b,zp in states] for i,(a,z) in enumerate(states)]
        def bell_values(v):return [[log(float(C[i][j]))+float(beta)*sum(float(P[z][zp])*v[2*j+zp] for zp in range(2)) if j in acts[i] else None for j in range(len(grid))] for i,(a,z) in enumerate(states)]
        # Exhaust every feasible deterministic policy, evaluate its own law, check all deviations.
        for g in product(*acts):
            count['oracle_policies']+=1;Q=transition(g);u=[log(float(C[i][j])) for i,j in enumerate(g)];M=[[float(i==j)-float(beta*Q[i][j]) for j in range(n)] for i in range(n)];v=gauss(M,u);bv=bell_values(v)
            if all(v[i]>=max(x for x in row if x is not None)-1e-10 for i,row in enumerate(bv)):certified.append((g,Q,v,bv))
        need(len(certified)==1,'unique oracle policy');g,Q,v,bv=certified[0];oracle_values[name]=sum(float(w)*vv for w,vv in zip(mu,v));eq(s['policy_indices'],list(g));eq(s['policy_assets'],[grid[j] for j in g]);eq(s['consumption_by_action'],[[c if c>0 else None for c in row] for row in C]);eq(s['feasible_actions'],acts);eq(s['transition'],Q);eq(s['value'],v);eq(s['assets'],grid);eq(s['transfer'],tr);eq(s['gross_return'],R);cons=[C[i][j] for i,j in enumerate(g)];eq(s['consumption'],cons)
        gaps=[]
        for i,row in enumerate(bv):
            for j,value in enumerate(row):
                actual=s['action_gaps'][i][j]
                if value is None:need(actual is None,'infeasible gap absent');continue
                center=v[i]-value;eq(actual['center'],center,'action gap');eq(actual['lower'],center,'interval lower',1e-10)
                if j!=g[i]:gaps.append(center)
        eq(s['minimum_strict_gap_lower'],min(gaps));need(0<=s['value_error_bound']<1e-20,'rational log value bound')
        bounds=[]
        for c in cons:
            exponent=0;scaled=c
            while scaled>=2:scaled/=2;exponent+=1
            while scaled<1:scaled*=2;exponent-=1
            N=D['log_series_terms'];u=(scaled-1)/(scaled+1);tail=lambda v:2*abs(v)**(2*N+1)/(F(2*N+1)*(1-v*v))
            bounds.append(tail(u)+abs(exponent)*tail(F(1,3)))
        exact_value_error=max(bounds)/(1-beta)
        eq(s['value_error_bound']*1e25,float(exact_value_error)*1e25,'independent logarithm error bound',1e-12)
        closed,laws,periods=independent_graph(Q);eq(s['graph']['closed_classes'],closed);eq(s['graph']['invariant_laws'],laws);eq(s['graph']['periods'],periods);eq(s['graph']['unique'],len(closed)==1);eq(s['graph']['converges_from_all_initial'],len(closed)==1 and periods[0]==1)
        reachable=[]
        for start in range(n):
            seen={start};front=[start]
            while front:
                i=front.pop()
                for j in range(n):
                    if Q[i][j]>0 and j not in seen:seen.add(j);front.append(j)
            reachable.append(seen)
        components=sorted({tuple(j for j in range(n) if j in reachable[i] and i in reachable[j]) for i in range(n)})
        eq(s['graph']['classes'],[list(c) for c in components],'all graph components')
        def account(w):
            a=sum(w[i]*states[i][0] for i in range(n));ap=sum(w[i]*grid[g[i]] for i in range(n));c=sum(w[i]*cons[i] for i in range(n));y=sum(w[i]*Y[states[i][1]] for i in range(n));T=sum(w[i]*tr[states[i][1]] for i in range(n));cf=W-R*a+ap
            return {'mean_assets':a,'next_assets':ap,'consumption':c,'income':y,'net_transfer':T,'foreign_consumption':cf,'world_residual':c+cf-y-T-W,'funding_feasible':cf>=0}
        eq(s['initial_account'],account(mu));eq(s['stationary_accounts'],[account(w) for w in laws]);w=mu[:]
        for step in s['transition_path']:
            eq(step['distribution'],w);eq(step['account'],account(w));eq(account(w)['net_transfer'],0,'transition tax funding');eq(account(w)['world_residual'],0);w=[sum(w[i]*Q[i][j] for i in range(n)) for j in range(n)]
        eq(s['funded_all_states'],all(W-R*a+grid[g[i]]>=0 for i,(a,z) in enumerate(states)))
        for i,(a,z) in enumerate(states):
            m=[beta*cons[i]/cons[2*g[i]+zp] for zp in range(2)];q=sum(P[z][zp]*m[zp]*payoff[zp] for zp in range(2));bond=sum(P[z][zp]*m[zp] for zp in range(2));ex=sum(P[z][zp]*payoff[zp] for zp in range(2));eq(s['pricing'][i],{'sdf':m,'payoff_price':q,'marginal_bond_price':bond,'market_bond_price':1/R,'covariance':q-bond*ex,'expected_payoff':ex,'expected_return':ex/q});eq(sum(P[z][zp]*m[zp]*payoff[zp]/q for zp in range(2)),1,'conditional payoff pricing')
        vv=[0.]*n
        for k in range(1,D['max_iterations']+1):
            new=[max(x for x in row if x is not None) for row in bell_values(vv)];diff=max(abs(a-b) for a,b in zip(vv,new));vv=new
            if k==D['coarse_iterations']:coarse=vv[:]
            if diff<=float(F(D['iteration_tolerance'])):break
        residual=max(abs(a-max(x for x in row if x is not None)) for a,row in zip(vv,bell_values(vv)));cres=max(abs(a-max(x for x in row if x is not None)) for a,row in zip(coarse,bell_values(coarse)));eq(s['iterations'],k);eq(s['iteration_converged'],True);eq(s['iteration_residual'],residual);eq(s['iteration_value_bound'],residual/float(1-beta));eq(s['coarse_residual'],cres);eq(s['coarse_value_bound'],cres/float(1-beta));distance=max(abs(a-b) for a,b in zip(coarse,v));eq(s['coarse_actual_distance'],distance);need(distance<=cres/float(1-beta)+1e-10,'actual error inside bound');eq(s['initial_welfare'],oracle_values[name]);eq(s['status'],'certified');eq(s['reason'],None)
    for name,value in oracle_values.items():change=value-oracle_values['baseline'];eq(out['comparisons'][name],{'common_initial_welfare_change':change,'normalized_change':float(1-beta)*change})
    need(oracle_values['refined_grid']>=oracle_values['baseline'],'nested opportunity gain');eq(out['status'],'certified');eq(out['synthetic'],True)
    # Execute the reader only AFTER independent economic reconstruction; not used as oracle.
    namespace={'__name__':'v14_reader_audit','__file__':str(root/FILES[2])};stdout=io.StringIO();stderr=io.StringIO();original=deepcopy(D)
    with redirect_stdout(stdout),redirect_stderr(stderr):exec(compile(payload[FILES[2]],str(root/FILES[2]),'exec'),namespace);actual=namespace['run'](D)
    need(not stdout.getvalue() and not stderr.getvalue() and D==original,'quiet immutable API');json.dumps(actual,allow_nan=False);eq(actual,out,'reader output')
    def reject(data):
        before=deepcopy(data)
        try:namespace['run'](data)
        except (ValueError,TypeError,KeyError):need(data==before,'rejection mutation');count['rejected_inputs']+=1;return
        raise ValueError('malformed input accepted')
    for key,value in [('discount','1'),('discount','0'),('gross_return','0'),('assets',['1/4','-1/4']),('initial',['1','0']),('max_iterations',True),('income',['0','1']),('payoff_by_next_income',['0','1']),('log_series_terms',3),('foreign_endowment','-1'),('model','other')]:
        bad=deepcopy(D);bad[key]=value;reject(bad)
    for key,value in [('training_counts',[[0,0],[1,1]]),('heldout_counts',[[True,1],[1,1]]),('alternative_transition',[['1/2','1/3'],['1/2','1/2']])]:bad=deepcopy(D);bad[key]=value;reject(bad)
    bad=deepcopy(D);bad['foreign_endowment']='0';failure=namespace['run'](bad);need(failure['status']=='not_certified' and any(s.get('reason')=='foreign funding shortfall' for s in failure['scenarios'].values()),'valid failed funding diagnostic')
    # Actual graph boundaries: two absorbing classes and one period-two class.
    for Q,unique,converges in [([[F(1),F(0)],[F(0),F(1)]],False,False),([[F(0),F(1)],[F(1),F(0)]],True,False)]:
        g=namespace['graph'](Q);closed,laws,periods=independent_graph(Q);eq(g['closed_classes'],closed);eq(g['invariant_laws'],laws);eq(g['periods'],periods);eq(g['unique'],unique);eq(g['converges_from_all_initial'],converges)
    # Run the real CLI in isolated reader-only directories under both interpreter modes.
    with tempfile.TemporaryDirectory(prefix='v14-project-reader-',dir='/private/tmp') as td:
        home=Path(td)
        for optimized in (False,True):
            r=home/('optimized' if optimized else 'normal');r.mkdir()
            for i in (1,2,3,4,5):(r/Path(FILES[i]).name).write_bytes(payload[FILES[i]])
            code=r/Path(FILES[2]).name;flags=[sys.executable,'-B']+(['-O'] if optimized else []);protected=[r/Path(FILES[i]).name for i in (1,2,4,5)];saved={str(p):p.read_bytes() for p in protected}
            def cli(args,success):
                proc=subprocess.run(flags+[str(code)]+args,cwd='/',capture_output=True,text=True)
                need((proc.returncode==0)==success,'actual CLI exit status')
                if success:need(not proc.stdout and not proc.stderr,'silent CLI');count['actual_reader_cli_successes']+=1
                else:need('protected' in proc.stderr,'actual protected refusal');count['actual_cli_alias_rejections']+=1
                need(all(Path(p).read_bytes()==b for p,b in saved.items()),'protected byte change')
            cli([],True);eq(json.loads((r/Path(FILES[3]).name).read_text()),out,'default isolated reader output')
            explicit=home/('explicit-'+str(optimized)+'.json');cli(['--input',str(protected[0]),'--output',str(explicit)],True);eq(json.loads(explicit.read_text()),out,'explicit output')
            for index,p in enumerate(protected):
                link=home/('sym-'+str(optimized)+'-'+str(index));link.symlink_to(p);hard=home/('hard-'+str(optimized)+'-'+str(index));os.link(p,hard)
                for target in (p,r/'..'/r.name/p.name,link,hard):cli(['--output',str(target)],False)
            bad_input=home/('bad-'+str(optimized)+'.json');bad_data=deepcopy(D);bad_data['discount']='1';bad_input.write_text(json.dumps(bad_data));bad_output=home/('bad-output-'+str(optimized)+'.json')
            proc=subprocess.run(flags+[str(code),'--input',str(bad_input),'--output',str(bad_output)],cwd='/',capture_output=True,text=True)
            need(proc.returncode!=0 and not bad_output.exists() and 'discount/return domain' in proc.stderr,'actual malformed CLI refusal');count['actual_malformed_cli_rejections']+=1
            fail_input=home/('failed-'+str(optimized)+'.json');fail_data=deepcopy(D);fail_data['foreign_endowment']='0';fail_input.write_text(json.dumps(fail_data));fail_output=home/('failed-output-'+str(optimized)+'.json')
            cli(['--input',str(fail_input),'--output',str(fail_output)],True);failed=json.loads(fail_output.read_text());need(failed['status']=='not_certified' and any(s.get('reason')=='foreign funding shortfall' for s in failed['scenarios'].values()),'actual valid-failure CLI diagnostic');count['actual_valid_failure_cli_diagnostics']+=1
            need(all(Path(p).read_bytes()==b for p,b in saved.items()),'protected bytes after malformed/failure tests')
            need({p.name for p in r.iterdir()}=={Path(FILES[i]).name for i in (1,2,3,4,5)},'reader exact five files')
    for p,b in payload.items():need((root/p).read_bytes()==b,'nine payload bytes unchanged')
    return {'volume':'v14','component':'project','status':'passed','tasks':7,'domains':5,'runtime_files':9,'reader_files':5,'HTML_inputs':len(doc.inputs),'HTML_outputs':len(doc.outputs),**count,'open_issues':[]}
if __name__=='__main__':check()
