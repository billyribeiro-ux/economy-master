"""Original finite macro-finance project. Five-file, standard-library reader."""
import argparse
from copy import deepcopy
from fractions import Fraction as F
from functools import lru_cache
from math import gcd, isfinite, log
from pathlib import Path
import json

STEM='v14-assessment'
def need(ok,message):
    if not ok:raise ValueError(message)
def frac(x):
    need(isinstance(x,str),'rational input must be a string')
    try:q=F(x)
    except (ValueError,ZeroDivisionError):raise ValueError('invalid rational') from None
    need(len(x)<=100 and abs(q)<=10**6,'rational magnitude/length limit');return q
def integer(x,lo,hi):need(type(x) is int and lo<=x<=hi,'integer domain');return x
def stochastic(rows):
    need(isinstance(rows,list) and len(rows)==2 and all(isinstance(r,list) and len(r)==2 for r in rows),'two income states')
    P=[[frac(x) for x in r] for r in rows];need(all(min(r)>=0 and sum(r)==1 for r in P),'stochastic rows');return P
def solve(M,b):
    n=len(b);a=[list(r)+[x] for r,x in zip(M,b)]
    for j in range(n):
        piv=next((i for i in range(j,n) if a[i][j]),None);need(piv is not None,'singular linear system');a[j],a[piv]=a[piv],a[j];q=a[j][j];a[j]=[x/q for x in a[j]]
        for i in range(n):
            if i!=j:
                q=a[i][j];a[i]=[x-q*y for x,y in zip(a[i],a[j])]
    return [r[-1] for r in a]
@lru_cache(maxsize=512)
def log_bounds(x,N):
    need(x>0,'positive log argument');k=0;z=x
    while z>=2:z/=2;k+=1
    while z<1:z*=2;k-=1
    def series(z):
        t=(z-1)/(z+1);center=2*sum((t**(2*j+1)/F(2*j+1) for j in range(N)),F(0));tail=2*abs(t)**(2*N+1)/(F(2*N+1)*(1-t*t));return center,tail
    c,e=series(z);c2,e2=series(F(2));return c+k*c2,e+abs(k)*e2

def graph(Q):
    n=len(Q);reach=[[i==j or Q[i][j]>0 for j in range(n)] for i in range(n)]
    for k in range(n):
        for i in range(n):
            for j in range(n):reach[i][j]=reach[i][j] or (reach[i][k] and reach[k][j])
    groups=[];unused=set(range(n))
    while unused:
        i=min(unused);c=[j for j in sorted(unused) if reach[i][j] and reach[j][i]];groups.append(c);unused-=set(c)
    closed=[c for c in groups if all(not Q[i][j] for i in c for j in range(n) if j not in c)];laws=[];periods=[]
    for c in closed:
        d={c[0]:0};queue=[c[0]]
        for i in queue:
            for j in c:
                if Q[i][j] and j not in d:d[j]=d[i]+1;queue.append(j)
        per=0
        for i in c:
            for j in c:
                if Q[i][j]:per=gcd(per,abs(d[i]+1-d[j]))
        periods.append(per)
        m=len(c);M=[[Q[c[j]][c[i]]-int(i==j) for j in range(m)] for i in range(m-1)]+[[F(1)]*m];b=[F(0)]*(m-1)+[F(1)];w=solve(M,b);full=[F(0)]*n
        for i,x in zip(c,w):full[i]=x
        laws.append(full)
    return dict(classes=groups,closed_classes=closed,periods=periods,invariant_laws=laws,unique=len(closed)==1,converges_from_all_initial=len(closed)==1 and periods[0]==1)

def model(A,Y,P,beta,R,transfer,initial,W,payoff,tol,maxit,coarse,N):
    states=[(a,z) for a in A for z in range(2)];n=len(states);C=[[Y[z]+transfer[z]+R*a-ap for ap in A] for a,z in states];acts=[[j for j,c in enumerate(row) if c>0] for row in C]
    if any(not row for row in acts):return {'status':'not_certified','reason':'no positive-consumption action','states_without_action':[i for i,row in enumerate(acts) if not row]}
    rewards=[[log(float(c)) if c>0 else None for c in row] for row in C]
    def bell(v):return [max(rewards[i][j]+float(beta)*sum(float(P[z][zp])*v[2*j+zp] for zp in range(2)) for j in acts[i]) for i,(a,z) in enumerate(states)]
    v=[0.]*n;coarse_v=None
    for it in range(1,maxit+1):
        new=bell(v);step=max(abs(x-y) for x,y in zip(v,new));v=new
        if it==coarse:coarse_v=v[:]
        if step<=float(tol):break
    policy=[max(acts[i],key=lambda j:rewards[i][j]+float(beta)*sum(float(P[z][zp])*v[2*j+zp] for zp in range(2))) for i,(a,z) in enumerate(states)]
    Q=[[F(0)]*n for _ in states]
    for i,(a,z) in enumerate(states):
        for zp in range(2):Q[i][2*policy[i]+zp]=P[z][zp]
    lc=[log_bounds(C[i][policy[i]],N) for i in range(n)];M=[[F(int(i==j))-beta*Q[i][j] for j in range(n)] for i in range(n)];vc=solve(M,[p[0] for p in lc]);err=max(e for c,e in lc)/(1-beta);gaps=[]
    for i,(a,z) in enumerate(states):
        row=[]
        for j in range(len(A)):
            if j not in acts[i]:row.append(None);continue
            if j==policy[i]:row.append({'center':0.,'lower':0.});continue
            ac,ae=log_bounds(C[i][j],N);g=vc[i]-ac-beta*sum(P[z][zp]*vc[2*j+zp] for zp in range(2));lo=g-(1+beta)*err-ae;row.append({'center':float(g),'lower':float(lo)})
        gaps.append(row)
    lower=[r['lower'] for i,row in enumerate(gaps) for j,r in enumerate(row) if r is not None and j!=policy[i]];cert=all(g>0 for g in lower)
    gr=graph(Q);cons=[C[i][policy[i]] for i in range(n)];current_assets=[s[0] for s in states];next_assets=[A[j] for j in policy]
    # The conditional marginal-utility kernel prices a small auxiliary claim only.
    pricing=[]
    for i,(a,z) in enumerate(states):
        sdf=[beta*cons[i]/cons[2*policy[i]+zp] for zp in range(2)];q=sum(P[z][zp]*sdf[zp]*payoff[zp] for zp in range(2));bond=sum(P[z][zp]*sdf[zp] for zp in range(2));mean=sum(P[z][zp]*payoff[zp] for zp in range(2));cov=q-bond*mean
        pricing.append({'sdf':sdf,'payoff_price':q,'marginal_bond_price':bond,'market_bond_price':1/R,'covariance':cov,'expected_payoff':mean,'expected_return':mean/q})
    def account(w):
        a=sum(x*y for x,y in zip(w,current_assets));ap=sum(x*y for x,y in zip(w,next_assets));c=sum(x*y for x,y in zip(w,cons));y=sum(w[i]*Y[z] for i,(a,z) in enumerate(states));t=sum(w[i]*transfer[z] for i,(a,z) in enumerate(states));foreign=W-R*a+ap
        return {'mean_assets':a,'next_assets':ap,'consumption':c,'income':y,'net_transfer':t,'foreign_consumption':foreign,'world_residual':c+foreign-y-t-W,'funding_feasible':foreign>=0}
    initial_account=account(initial);stationary_accounts=[account(w) for w in gr['invariant_laws']];path=[];w=initial[:]
    for t in range(5):
        path.append({'date':t,'distribution':w[:],'account':account(w)});w=[sum(w[i]*Q[i][j] for i in range(n)) for j in range(n)]
    # Conservative funding for EVERY distribution over the declared finite states.
    funded=min(W-R*a+ap for a,ap in zip(current_assets,next_assets))>=0
    fine_res=max(abs(x-y) for x,y in zip(v,bell(v)))
    if coarse_v is None:coarse_v=v[:]
    coarse_res=max(abs(x-y) for x,y in zip(coarse_v,bell(coarse_v)))
    return {'status':'certified' if cert and funded and gr['converges_from_all_initial'] else 'not_certified','reason':None if cert and funded and gr['converges_from_all_initial'] else ('ambiguous policy gaps' if not cert else ('foreign funding shortfall' if not funded else 'nonunique or nonconvergent long-run law')),'assets':A,'transfer':transfer,'gross_return':R,'consumption_by_action':[[c if c>0 else None for c in row] for row in C],'feasible_actions':acts,'policy_indices':policy,'policy_assets':next_assets,'consumption':cons,'transition':Q,'value':[float(x) for x in vc],'value_error_bound':float(err),'action_gaps':gaps,'minimum_strict_gap_lower':min(lower) if lower else None,'iterations':it,'iteration_converged':step<=float(tol),'iteration_residual':fine_res,'iteration_value_bound':fine_res/float(1-beta),'coarse_residual':coarse_res,'coarse_value_bound':coarse_res/float(1-beta),'coarse_actual_distance':max(abs(float(x)-y) for x,y in zip(vc,coarse_v)),'graph':gr,'pricing':pricing,'initial_welfare':sum(float(w)*float(x) for w,x in zip(initial,vc)),'initial_account':initial_account,'stationary_accounts':stationary_accounts,'transition_path':path,'funded_all_states':funded}

def run(data):
    need(isinstance(data,dict),'object input');original=deepcopy(data)
    required={'model','provenance','discount','gross_return','income','assets','refined_assets','initial','training_counts','heldout_counts','alternative_transition','low_income_transfer','stress_return','foreign_endowment','payoff_by_next_income','iteration_tolerance','max_iterations','coarse_iterations','log_series_terms'}
    need(set(data)==required and data['model']=='finite-income-saving-v1' and isinstance(data['provenance'],str),'schema/model')
    beta=frac(data['discount']);R=frac(data['gross_return']);Rs=frac(data['stress_return']);need(0<beta<1 and R>0 and Rs>0,'discount/return domain')
    Y=[frac(x) for x in data['income']];need(len(Y)==2 and 0<Y[0]<Y[1],'ordered positive income')
    A=[frac(x) for x in data['assets']];Ar=[frac(x) for x in data['refined_assets']];need(2<=len(A)<=3 and 2<=len(Ar)<=4 and A==sorted(set(A)) and Ar==sorted(set(Ar)) and set(A)<=set(Ar) and (A[0],A[-1])==(Ar[0],Ar[-1]),'asset grids and fixed bounds')
    init=[frac(x) for x in data['initial']];need(len(init)==2*len(A) and min(init)>=0 and sum(init)==1,'initial probability law')
    def counts(name):
        c=data[name];need(isinstance(c,list) and len(c)==2 and all(isinstance(r,list) and len(r)==2 for r in c),'count matrix')
        for r in c:
            for x in r:integer(x,0,1000000)
            need(sum(r)>0,'positive row sample')
        return c
    train=counts('training_counts');held=counts('heldout_counts');P=[[F(x,sum(r)) for x in r] for r in train];need(all(min(r)>0 for r in P),'interior fitted income law');alt=stochastic(data['alternative_transition']);need(all(min(r)>0 for r in alt),'positive alternative likelihood')
    pi=[P[1][0]/(P[0][1]+P[1][0]),P[0][1]/(P[0][1]+P[1][0])];need([sum(init[2*i+z] for i in range(len(A))) for z in range(2)]==pi,'initial income marginal must be fitted stationary law')
    t=frac(data['low_income_transfer']);need(0<=t<Y[1]*pi[1]/pi[0],'funded transfer leaves high net income positive');transfer=[t,-t*pi[0]/pi[1]];W=frac(data['foreign_endowment']);need(W>=0,'foreign resource domain')
    payoff=[frac(x) for x in data['payoff_by_next_income']];need(len(payoff)==2 and min(payoff)>0,'positive payoff vector')
    tol=frac(data['iteration_tolerance']);need(F(1,10**14)<=tol<=F(1,100),'iteration tolerance');maxit=integer(data['max_iterations'],1,10000);coarse=integer(data['coarse_iterations'],1,maxit);N=integer(data['log_series_terms'],16,40)
    refined_init=[init[2*A.index(a)+z] if a in A else F(0) for a in Ar for z in range(2)]
    scenarios={}
    for name,grid,rate,tr,mu in [('baseline',A,R,[F(0),F(0)],init),('redistribution',A,R,transfer,init),('rate_stress',A,Rs,[F(0),F(0)],init),('refined_grid',Ar,R,[F(0),F(0)],refined_init)]:scenarios[name]=model(grid,Y,P,beta,rate,tr,mu,W,payoff,tol,maxit,coarse,N)
    def ll(c,p):return sum(c[i][j]*log(float(p[i][j])) for i in range(2) for j in range(2))
    base=scenarios['baseline'];comparisons={}
    for name,s in scenarios.items():
        if 'initial_welfare' in base and 'initial_welfare' in s:
            comparisons[name]={'common_initial_welfare_change':s['initial_welfare']-base['initial_welfare'],'normalized_change':float(1-beta)*(s['initial_welfare']-base['initial_welfare'])}
    result={'model':data['model'],'status':'certified' if all(s['status']=='certified' for s in scenarios.values()) else 'not_certified','synthetic':True,'fitted_transition':P,'income_stationary':pi,'estimation':{'training_log_likelihood':ll(train,P),'training_alternative_log_likelihood':ll(train,alt),'heldout_log_likelihood':ll(held,P),'heldout_alternative_log_likelihood':ll(held,alt),'heldout_empirical_transition':[[F(x,sum(r)) for x in r] for r in held],'training_row_counts':[sum(r) for r in train],'heldout_row_counts':[sum(r) for r in held]},'scenarios':scenarios,'comparisons':comparisons,'limits':['Finite asset actions; no continuous Euler equality or continuous approximation-error bound.','Exogenous foreign rate and income law; no endogenous world-rate or labor equilibrium.','Auxiliary marginal claim prices do not certify an expanded trading equilibrium.','Synthetic conditional count fit is not empirical identification of preferences or causal policy effects.']}
    need(data==original,'input mutation')
    def safe(x):
        if isinstance(x,F):return str(x)
        if isinstance(x,float):need(isfinite(x),'finite JSON output');return x
        if isinstance(x,dict):return {k:safe(v) for k,v in x.items()}
        if isinstance(x,list):return [safe(v) for v in x]
        return x
    return safe(result)

def load(path):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'duplicate JSON key');d[k]=v
        return d
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def main():
    here=Path(__file__).resolve().parent;parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=here/(STEM+'-inputs.json'));parser.add_argument('--output',type=Path,default=here/(STEM+'-output.json'));args=parser.parse_args();out=args.output
    protected=[args.input,Path(__file__),here/(STEM+'-inputs.json'),here/(STEM+'-README.txt'),here/(STEM+'-manifest.json')]
    for p in protected:
        need(out.resolve()!=p.resolve(),'protected output alias')
        if out.exists() and p.exists():need(not out.samefile(p),'protected hard-link output alias')
    result=run(load(args.input));text=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n';out.write_text(text)
if __name__=='__main__':main()
