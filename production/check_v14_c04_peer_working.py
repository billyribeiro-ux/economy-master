"""Independent C04 peer: linear-system values, bracketed entry and direct reward integrals."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from math import exp, isfinite, log, sqrt
from pathlib import Path
AUTHOR=('production/v14-c04-working.html','production/check_v14_c04_working.py','production/v14-c04-sources-working.json','production/v14-c04-author-review-working.json')
FILES=AUTHOR+('production/check_v14_c04_peer_working.py','production/v14-c04-peer-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(not isinstance(x,bool) and isinstance(x,(int,float,F)) and isfinite(float(x)),'finite scalar required');return float(x)
def parsed(s):
    def read(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return read(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=read(n.right);need(d!=0,'zero marker denominator');return read(n.left)/d
        raise ValueError('invalid numeric marker')
    return read(ast.parse(s.rsplit('=',1)[-1].strip(),mode='eval').body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.mark={};self.pending=[];self.ids=[];self.ex=[];self.sol=[];self.worked=[];self.sources={};self.text=[]
    def handle_starttag(self,t,attrs):
        d=dict(attrs);cl=d.get('class','').split()
        if 'id' in d:need(d['id'] not in self.ids,'duplicate ID');self.ids.append(d['id'])
        if 'worked' in cl:self.worked.append(d.get('id'))
        if t=='li' and d.get('id','').startswith('v14-c04-e'):self.ex.append(d['id'])
        if 'data-solution-for' in d:
            need(any(tag=='details' and 'solutions' in a.get('class','').split() for tag,a in self.stack),'solution outside details');self.sol.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d.get('href')
        for typ in ('data-input','data-calc'):
            if typ in d:
                key=d[typ];need(key not in self.mark,'duplicate marker');self.mark[key]=[typ,''];self.pending.append((key,len(self.stack)))
        if t not in ('br','hr','img','input','link','meta'):self.stack.append((t,d))
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack[-1][0]==t,'unbalanced HTML');self.stack.pop();self.pending=[(k,n) for k,n in self.pending if n<len(self.stack)]
    def handle_data(self,s):
        self.text.append(s)
        for k,n in self.pending:self.mark[k][1]+=s

def solve(A,b):
    n=len(b);need(n>0 and len(A)==n and all(len(row)==n for row in A),'square linear system')
    M=[list(map(num,row))+[num(rhs)] for row,rhs in zip(A,b)]
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(M[j][i]));need(abs(M[pivot][i])>1e-15,'singular system');M[i],M[pivot]=M[pivot],M[i]
        d=M[i][i];M[i]=[x/d for x in M[i]]
        for j in range(n):
            if j!=i:
                factor=M[j][i];M[j]=[a-factor*b for a,b in zip(M[j],M[i])]
    return tuple(row[-1] for row in M)

def primitives(p):
    need(len(p)==8,'eight primitives');A,alpha,eta,r,s,k,b,y=map(num,p)
    need(min(A,r,s,k,y)>0 and b>=0 and 0<alpha<1 and 0<eta<1,'matching primitive domain')
    return A,alpha,eta,r,s,k,b,y

def at_theta(theta,p):
    A,alpha,eta,r,s,k,b,y=primitives(p);theta=num(theta);need(theta>0,'positive active tightness')
    f=A*theta**(1-alpha);q=f/theta
    # Original worker/firm flow equations and Nash share, solved as a four-variable system.
    U,E,J,w=solve(((r+f,-f,0,0),(-s,r+s,0,-1),(0,0,r+s,1),(-(1-eta),1-eta,-eta,0)),(b,0,y,0))
    return dict(theta=theta,f=f,q=q,U=U,E=E,J=J,w=w,X=E-U,S=E-U+J,u=s/(s+f),v=theta*s/(s+f),m=f*s/(s+f),entry=q*J-k)

def market(p):
    A,alpha,eta,r,s,k,b,y=primitives(p)
    if y<=b:return dict(theta=0.,u=1.,v=0.,m=0.,U=b/r,active=False)
    lo=0.;hi=1.
    for _ in range(1000):
        if at_theta(hi,p)['entry']<=0:break
        hi*=2
    else:raise ValueError('no finite bracket')
    for _ in range(85):
        mid=(lo+hi)/2
        if at_theta(mid,p)['entry']>0:lo=mid
        else:hi=mid
    row=at_theta((lo+hi)/2,p);row.update(active=True,bracket=(lo,hi));return row

def transition(f,s,u0,t):
    f,s,u0,t=map(num,(f,s,u0,t));need(f>=0 and s>=0 and f+s>0 and 0<=u0<=1 and t>=0,'transition domain')
    steady=s/(f+s);return steady+(u0-steady)*exp(-(s+f)*t)

def reward_integral(theta,u0,p,T=None):
    A,alpha,eta,r,s,k,b,y=primitives(p);theta=num(theta);u0=num(u0);need(theta>=0 and 0<=u0<=1,'policy/state domain')
    f=A*theta**(1-alpha);steady=s/(s+f);C=y-b+k*theta;flow=y-C*steady
    if T is None:return flow/r-C*(u0-steady)/(r+s+f)
    T=num(T);need(T>=0,'nonnegative horizon')
    return flow*(1-exp(-r*T))/r-C*(u0-steady)*(1-exp(-(r+s+f)*T))/(r+s+f)

def fixed_coefficients(theta,p):
    # Evaluate integrated resource flows at two initial states; no HJB coefficient oracle.
    a=reward_integral(theta,0,p);return a,a-reward_integral(theta,1,p)

def planner(p):
    p=list(primitives(p));need(p[7]>p[6],'positive-surplus planner domain');p[2]=p[1]
    eq=market(p);a,D=fixed_coefficients(eq['theta'],p);return eq['theta'],a,D

def entry_limit_value(q,p):
    A,alpha,eta,r,s,k,b,y=primitives(p);q=num(q);need(q>0,'positive filling hazard')
    # Unknown vacancy outside option V; fixed worker U=b/r, Nash X/(J−V)=eta/(1−eta).
    V,J,E,w=solve(((r+q,-q,0,0),(-s,r+s,0,1),(0,0,r+s,-1),(eta,-eta,1-eta,0)),(-k,y,s*b/r,(1-eta)*b/r))
    return V

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];payload={p:(base/p).read_bytes() for p in FILES}
    doc=Document();doc.feed(payload[AUTHOR[0]].decode());doc.close();need(not doc.stack and all(i.startswith('v14-c04-') for i in doc.ids),'closed prefixed html')
    ex=['v14-c04-e'+str(i) for i in range(1,11)];need(doc.ex==doc.sol==ex,'ten prompt/solution pairs');need(doc.worked==['v14-c04-w'+str(i) for i in range(1,5)],'four worked cases')
    author=json.loads(payload[AUTHOR[3]]);peer=json.loads(payload[FILES[-1]]);sources=json.loads(payload[AUTHOR[2]])
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']},'source binding');need(set(peer['exact_prompt_solution_audit'])==set(ex),'full peer prompt audit')
    for record,key,paths in ((author,'bindings',set(AUTHOR[:3])),(peer,'payload_bindings',set(FILES[:-1]))):
        records=record[key];need(len(records)==len(paths) and {b['path'] for b in records}==paths,'nonself bindings')
        for b in records:need(len(payload[b['path']])==b['bytes'] and sha256(payload[b['path']]).hexdigest()==b['sha256'],'frozen payload changed')
    inputs={k:parsed(v[1]) for k,v in doc.mark.items() if v[0]=='data-input'};values={k:parsed(v[1]) for k,v in doc.mark.items() if v[0]=='data-calc'}
    comparisons=0;rejects=0
    def near(a,b,tol=2e-9):
        nonlocal comparisons
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'comparison dimensions')
            for x,y in zip(a,b):near(x,y,tol)
        else:need(isfinite(float(a)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),str((a,b)));comparisons+=1
    need(set(inputs)=={'hazards','survival','baseline','shock-productivity','low-bargaining','candidate-theta'},'input coverage')
    near(inputs['hazards'],(1,.1));near(inputs['survival'],.5);near(inputs['baseline'],(1,.5,.5,.1,.1,.5,.2,.9));near(inputs['shock-productivity'],2.6);near(inputs['low-bargaining'],1/3);near(inputs['candidate-theta'],1.21)
    p=inputs['baseline'];A,alpha,eta,r,s,k,b,y=p;eq=market(p);ps=list(p);ps[7]=inputs['shock-productivity'];shock=market(ps);pd=list(p);pd[2]=inputs['low-bargaining'];dist=market(pd)
    thetaP,aP,DP=planner(p);ad,Dd=fixed_coefficients(dist['theta'],p);u0=eq['u'];half=transition(shock['f'],s,u0,log(2)/(s+shock['f']));shock_drift=s-(s+shock['f'])*half
    f0,s0=inputs['hazards'];dt=-log(inputs['survival'])/(f0+s0);UE=1-transition(f0,s0,1,dt);EU=transition(f0,s0,0,dt)
    Hprime=k*((r+s)*alpha*eq['theta']**(alpha-1)/A+eta);ty=(1-eta)/Hprime;fy=(1-alpha)*eq['f']/eq['theta']*ty;uy=-s*fy/(s+eq['f'])**2;wy=eta+eta*k*ty
    candidate=inputs['candidate-theta'];cand=at_theta(candidate,p);residual=k*(r+s+eta*cand['f'])/cand['q']-(1-eta)*(y-b)
    recruiting=k*shock['theta']*(shock['u']/r+(u0-shock['u'])/(r+s+shock['f']))
    Wp=aP-DP*u0;Wd=ad-Dd*u0
    results={'transition-pair':(UE,EU),'hazard-u':EU/(EU+UE),'base-rates':tuple(eq[z] for z in ('theta','f','q')),'base-surplus':tuple(eq[z] for z in ('S','X','J')),'base-values':tuple(eq[z] for z in ('w','U','E')),'base-flows':tuple(eq[z] for z in ('u','v','m')),
      'base-reserve':k*eq['v']/r,'base-welfare-flow':y*(1-u0)+b*u0-k*eq['v'],'base-welfare-value':u0*eq['U']+(1-u0)*(eq['E']+eq['J']),
      'shock-market':tuple(shock[z] for z in ('theta','f','q','S','w','U','E','J')),'shock-u':shock['u'],'shock-v0':shock['theta']*u0,'shock-half':(half,shock['theta']*half,shock['f']*half,shock_drift),'shock-false-f':s*(1-half)/half,'shock-reserve':k*shock['theta']*u0/r,'shock-recruiting-pv':recruiting,
      'distorted-market':tuple(dist[z] for z in ('theta','f','u','w','S','J')),'distorted-coefficients':(ad,Dd),'welfare-comparison':(Wp,Wd,Wp-Wd),'baseline-derivatives':(ty,fy,uy,wy),'root-error':(residual,abs(residual)/(k*eta),abs(candidate-eq['theta']))}
    need(set(results)==set(values),'all displayed calculations')
    for key,result in results.items():
        try:near(values[key],result)
        except ValueError as e:raise ValueError(key+': '+str(e)) from e
    # Full equations checked beyond numerical cases, including elasticity other than one half.
    alternatives=[p,ps,pd,(1.3,.3,.6,.08,.2,.4,.1,1.2),(1,.7,.4,.2,.05,.8,.3,1.4)]
    for primitives_ in alternatives:
        A,al,et,r_,s_,k_,b_,y_=primitives_;e=market(primitives_);f,q,U,E,J,w=(e[z] for z in ('f','q','U','E','J','w'))
        near(r_*U,b_+f*(E-U));near(r_*E,w+s_*(U-E));near((r_+s_)*J,y_-w);near(q*J,k_);near((1-et)*(E-U),et*J);near(s_*(1-e['u']),e['m']);near(f,e['theta']*q)
        near(w,et*y_+(1-et)*b_+et*k_*e['theta']);need(b_<w<y_ and e['bracket'][0]<=e['theta']<=e['bracket'][1],'positive market and bracket');comparisons+=1
        near(reward_integral(e['theta'],e['u'],primitives_),(y_*(1-e['u'])+b_*e['u']-k_*e['v'])/r_)
    # Different elasticity gives identical observed baseline but different planner optimum.
    changed=list(p);changed[1]=1/3;observed=market(changed)
    for z in ('theta','f','q','U','E','J','w','u'):near(observed[z],eq[z])
    need(abs(planner(changed)[0]-observed['theta'])>1e-3,'observational equivalence does not imply efficiency');comparisons+=1
    # Finite differences independently confirm all seven comparative-static signs and four displayed derivatives.
    eps=1e-5;signs=(1,None,-1,-1,-1,-1,-1,1)
    for index,sign in enumerate(signs):
        if sign is None:continue
        plus=list(p);minus=list(p);plus[index]+=eps;minus[index]-=eps;ep=market(plus);em=market(minus);slope=(ep['theta']-em['theta'])/(2*eps)
        need(sign*slope>0,'comparative-static sign');comparisons+=1
        if index==7:
            near(tuple((ep[z]-em[z])/(2*eps) for z in ('theta','f','u','w')),(ty,fy,uy,wy),2e-7)
    # Endpoint probabilities/semigroup and first-hit distinction, including legitimate hazard>1.
    for f,s_,t in ((1,.1,1),(2,.1,1),(2,0,.7),(0,.2,2)):
        pu=transition(f,s_,1,t);pe=transition(f,s_,0,t)
        need(0<=pu<=1 and 0<=pe<=1,'transition probabilities');comparisons+=1
        near(transition(f,s_,1,2*t),pu*pu+(1-pu)*pe)
        if s_>0 and f>0:need(1-pu<1-exp(-f*t),'endpoint vs first finding');comparisons+=1
    # Planner HJB gap and exact finite-T verification along multiple switched controls.
    for primitive in (p,changed,alternatives[-1]):
        A,al,et,r_,s_,k_,b_,y_=primitive;opt,a,D=planner(primitive)
        near(k_,D*(1-al)*A*opt**(-al))
        for u,theta in product((0,.2,1),(0,opt/3,opt,opt*3)):
            f=A*theta**(1-al);reward=y_*(1-u)+b_*u-k_*theta*u;drift=s_-(s_+f)*u;gap=r_*(a-D*u)-reward+D*drift
            need(gap>=-1e-10,'global planner stage inequality');comparisons+=1
            if theta==opt or u==0:near(gap,0)
        for initial in (0,F(1,11),1):
            for controls in ((opt,opt),(0,opt*3),(opt*2,opt/4)):
                current=float(initial);value=0.;time=0.
                for theta,length in zip(controls,(.7,1.3)):
                    value+=exp(-r_*time)*reward_integral(theta,current,primitive,length);current=transition(A*theta**(1-al),s_,current,length);time+=length
                bound=a-D*float(initial)-exp(-r_*time)*(a-D*current)
                need(value<=bound+1e-10,'finite T integrated planner bound');comparisons+=1
                if controls==(opt,opt):near(value,bound)
                attained=value+exp(-r_*time)*reward_integral(opt,current,primitive)
                need(attained<=a-D*float(initial)+1e-10,'switched infinite policy');comparisons+=1
    # Zero vacancies: agreement boundary and independently solved entrant value at large filling hazard.
    for output in (.1,.2):
        no=list(p);no[7]=output;e=market(no);near((e['theta'],e['u'],e['v'],e['U']),(0,1,0,2));need(entry_limit_value(10000,no)<0,'no profitable inactive entry');comparisons+=1
    need(entry_limit_value(10000,p)>0,'positive-surplus inactive market admits entry');comparisons+=1
    near(r*entry_limit_value(10000,p),(10000*(1-eta)*(y-b)-k*(r+s))/(r+s+10000*(1-eta)))
    # Stationary Beveridge curve and exact nonstationary accounting witness.
    v=((s/A)**(1/(1-alpha))*(1-half)**(1/(1-alpha))*half**(-alpha/(1-alpha)))
    need(abs(v-shock['theta']*half)>1e-3,'transition not stationary curve');comparisons+=1
    near((s*(1-half)-shock_drift)/half,shock['f']);near(r*results['shock-reserve'],k*shock['theta']*u0);need(results['shock-reserve']>recruiting,'sufficient reserve exceeds recruiting PV');comparisons+=1
    invalid=[(num,(True,)),(num,(float('inf'),)),(parsed,('x=1/0',)),(parsed,('sum((1,2))',)),(solve,(((1,1),(2,2)),(1,2))),
      (at_theta,(0,p)),(transition,(-1,.1,.5,1)),(transition,(0,0,.5,1)),(transition,(1,.1,2,1)),(transition,(1,.1,.5,-1)),(reward_integral,(-1,.5,p)),(reward_integral,(1,.5,p,-1)),(entry_limit_value,(0,p))]
    for index,bad in ((0,0),(1,0),(1,1),(2,0),(2,1),(3,0),(4,0),(5,0),(6,-1),(7,0)):
        changedp=list(p);changedp[index]=bad;invalid.append((market,(changedp,)))
    nop=list(p);nop[7]=nop[6];invalid.append((planner,(nop,)))
    for fn,args in invalid:
        try:fn(*args)
        except (ValueError,OverflowError):rejects+=1
        else:raise ValueError('invalid domain accepted '+fn.__name__)
    summary=dict(chapter='v14-c04',status='passed',review='separate peer',comparisons=comparisons,domain_rejections=rejects,worked_cases=4,solved_exercises=10,input_markers=len(inputs),result_markers=len(results),runtime_files=6,scope='Independent four-value linear-system and bracketed-entry solver; direct discounted resource integrals, switched controls, entry boundaries and finite differences. No author code executed.')
    json.dumps(summary,allow_nan=False);return summary

if __name__=='__main__':check()
