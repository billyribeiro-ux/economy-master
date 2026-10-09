"""Original finite consumption-pricing laboratory; four files, no writes/network."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import isfinite,exp,log,sqrt
from pathlib import Path
FILES=('production/v14-c07-working.html','production/check_v14_c07_working.py','production/v14-c07-sources-working.json','production/v14-c07-author-review-working.json')
def require(ok,message):
    if not ok:raise ValueError(message)
def scalar(x):
    require(type(x) in (int,float,F) and isfinite(float(x)),'finite numeric scalar');return float(x)
def crra(beta,gamma,c0,cs,probs):
    beta,gamma,c0=map(scalar,(beta,gamma,c0));cs=tuple(map(scalar,cs));probs=tuple(map(scalar,probs))
    require(0<beta<1 and gamma>0 and c0>0,'preference domain')
    require(len(cs)==len(probs)>0 and min(cs)>0,'positive states')
    require(min(probs)>0 and abs(sum(probs)-1)<1e-12,'probability domain')
    m=tuple(beta*(c/c0)**(-gamma) for c in cs);em=sum(p*z for p,z in zip(probs,m))
    return m,em,1/em

def mean(xs,ws,r):
    xs=tuple(map(scalar,xs));ws=tuple(map(scalar,ws));r=scalar(r)
    require(len(xs)==len(ws)>0 and min(xs)>0 and min(ws)>0 and abs(sum(ws)-1)<1e-12,'power mean domain')
    require(r<1 and r!=0,'power order')
    return sum(w*x**r for w,x in zip(ws,xs))**(1/r)
def recursive(beta,gamma,psi,c0,cs,ends):
    beta,gamma,psi,c0=map(scalar,(beta,gamma,psi,c0));cs=tuple(map(scalar,cs));ends=tuple(map(scalar,ends))
    require(0<beta<1 and gamma>0 and gamma!=1 and psi>0 and psi!=1 and c0>0,'recursive parameter domain')
    require(len(cs)==len(ends)==2 and min(cs+ends)>0,'recursive consumption domain')
    rho=1-1/psi;k=(1-beta)**(1/rho)
    us=tuple(mean((c,k*d),(1-beta,beta),rho) for c,d in zip(cs,ends))
    ce=mean(us,(.5,.5),1-gamma);u0=mean((c0,ce),(1-beta,beta),rho)
    m=tuple(beta*(c/c0)**(-1/psi)*(u/ce)**(1/psi-gamma) for c,u in zip(cs,us))
    return u0,us,ce,m

class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.worked=[];self.prompts=[];self.solutions=[];self.markers={};self.sources={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in q.get('class','').split() for t,q in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in q.get('class','').split() for t,q in self.stack),'undisclosed answer');self.solutions.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for attr in ('data-calc','data-input'):
            if attr in a:
                require(a[attr] not in self.markers,'duplicate marker');self.markers[a[attr]]=[attr,'']
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,text):
        for _,a in self.stack:
            for attr in ('data-calc','data-input'):
                if attr in a:self.markers[a[attr]][1]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting');self.stack.pop()
def parse(s):
    def walk(n):
        if isinstance(n,ast.Constant):return scalar(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric marker syntax')
    return walk(ast.parse(s.strip(),mode='eval').body)

def check(root=None):
    b=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(b/p).read_bytes() for p in FILES};doc=Read();doc.feed(payload[FILES[0]].decode());require(not doc.stack,'unclosed HTML')
    require(len(doc.ids)==len(set(doc.ids)) and all(x.startswith('v14-c07-') for x in doc.ids),'IDs')
    target=[f'v14-c07-e{i}' for i in range(1,13)]
    require(doc.prompts==doc.solutions==target,'12 exact solution pairs');require(doc.worked==[f'v14-c07-w{i}' for i in range(1,6)],'five cases')
    src=json.loads(payload[FILES[2]]);require(doc.sources=={s['id']:s['url'] for s in src['sources']},'source routes')
    rev=json.loads(payload[FILES[3]]);require(set(rev['exact_prompt_solution_audit'])==set(target),'prompt audits')
    require({x['path'] for x in rev['payload_bindings']}==set(FILES[:3]) and len(rev['payload_bindings'])==3,'three bindings')
    for x in rev['payload_bindings']:require((len(payload[x['path']]),sha256(payload[x['path']]).hexdigest())==(x['bytes'],x['sha256']),'binding mismatch')
    inputs={k:parse(v[1]) for k,v in doc.markers.items() if v[0]=='data-input'};values={k:parse(v[1]) for k,v in doc.markers.items() if v[0]=='data-calc'};count=0;rejections=0
    def near(a,b,label='comparison',tol=6e-11):
        nonlocal count
        if isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):near(x,y,label,tol)
        else:
            require(isfinite(float(a)) and abs(float(a)-float(b))<tol*max(1,abs(float(b))),f'{label}: {a} != {b}');count+=1
    require(set(inputs)=={'base','lognormal'},'all input markers');near(inputs['base'],(.96,2,1,.9,1.1,.5));near(inputs['lognormal'],(.99,.02,.02,.4))
    beta,gamma,c0,cl,ch,pl=inputs['base'];m,em,rf=crra(beta,gamma,c0,(cl,ch),(pl,1-pl));price=(m[0]*cl+m[1]*ch)/2;er=(cl+ch)/(2*price);sdr=(ch-cl)/(2*price);hj=abs(m[0]-m[1])/(2*em)
    bb,mu,sigma,sharpe=inputs['lognormal'];risk=sqrt(log(1+sharpe**2))/sigma;lrf=-log(bb)+risk*mu-risk*risk*sigma*sigma/2
    A=((F(38,49),F(19,104)),(F(57,196),F(133,208)));rows=list(map(sum,A));det=(1-A[0][0])*(1-A[1][1])-A[0][1]*A[1][0]
    v=((rows[0]*(1-A[1][1])+A[0][1]*rows[1])/det,((1-A[0][0])*rows[1]+A[1][0]*rows[0])/det)
    hm,he,hr=crra(.96,2,.2,(.15,.25),(.5,.5));u0,us,ce,ezm=recursive(.9,4,2,1,(1,1),(.8,1.2));e2,e2mean,e2rf=crra(.95,2,1,(.8,1.2),(.5,.5));e7,e7mean,e7rf=crra(.96,2,.2,(.05,.15),(.5,.5))
    expected={'base-m':m,'base-em':em,'base-price':price,'base-rf':rf,'base-er':er,'base-premium':er-rf,'base-sdr':sdr,'base-hj':hj,
              'puzzle-gamma':risk,'puzzle-logrf':lrf,'puzzle-rf':exp(lrf),'tree-a':max(rows),'tree-v':v,
              'habit-m':hm,'habit-rf':hr,'habit-rra':2/.2,'habit-hj':abs(hm[0]-hm[1])/(2*he),
              'ez-u':us,'ez-ce':ce,'ez-m':ezm,'ez-q':tuple(x/2 for x in ezm),'ez-rf':2/sum(ezm),
              'e2-m':e2,'e2-q':tuple(x/2 for x in e2),'e2-rf':e2rf,'e4-gamma':sqrt(log(1.04))/.02,'e4-rf':1/(.99*sqrt(1.04)),
              'e7-m':e7,'e7-rf':e7rf,'e8-lambda':1-.9*.2,'e8-price':.9/(1-.9*.2),'e11-news':(.001/(1-.5),.001/(1-.95))}
    require(set(expected)==set(values),'all displayed numerical results')
    for k,x in expected.items():near(values[k],x,k)
    # Exact rational pricing, covariance identity and every Markov equation.
    exactm=(F(24,25)/F(9,10)**2,F(24,25)/F(11,10)**2);near(m,exactm)
    returns=(cl/price,ch/price);cov=sum((mi-em)*(ri-er)/2 for mi,ri in zip(m,returns));near(er-rf,-cov/em);near((er-rf)/sdr,hj)
    near(sum(mi*ri/2 for mi,ri in zip(m,returns)),1);near(em*rf,1)
    insurance=sum(mi*x/2 for mi,x in zip(m,(ch,cl)));near(insurance-price,.1*(m[0]-m[1]));require(insurance>price,'insurance sign');count+=1
    for i in range(2):near(v[i],sum(A[i][j]*(1+v[j]) for j in range(2)))
    guess=(0.,0.)
    for _ in range(500):guess=tuple(sum(float(A[i][j])*(1+guess[j]) for j in range(2)) for i in range(2))
    near(guess,v,tol=1e-9)
    for perturb in ((.1,0),(-.2,.3),(2,-1)):
        candidate=tuple(float(x)+d for x,d in zip(v,perturb));res=max(abs(candidate[i]-sum(float(A[i][j])*(1+candidate[j]) for j in range(2))) for i in range(2))
        require(max(map(abs,perturb))<=res/(1-float(max(rows)))+1e-12,'certified norm error');count+=1
    near(F(19,20)/(1-F(19,20)),19);near((F(19,20)/F(9,10))/(1-F(19,20)/F(9,10)),-19)
    # Global finite CRRA tangent support over both signs of feasible state trades.
    q=tuple(x/2 for x in m);baseu=-1+.96*sum(-1/x/2 for x in (cl,ch))
    for h0 in (-.2,0,.2):
        for h1 in (-.2,0,.2):
            now=1-q[0]*h0-q[1]*h1;future=(cl+h0,ch+h1)
            alt=-1/now+.96*sum(-1/x/2 for x in future)
            require(alt<=baseu+1e-12,'global portfolio support');count+=1
    # Recursive derivatives: independent finite differences of utility levels, varied parameters.
    for bta,ga,ps in ((.9,4,2),(.8,2,.5),(.95,.5,2),(.7,3,1/3)):
        params=(bta,ga,ps);h=1e-5;_,uu,cc,mm=recursive(*params,1,(1,1),(.8,1.2))
        dc0=(recursive(*params,1+h,(1,1),(.8,1.2))[0]-recursive(*params,1-h,(1,1),(.8,1.2))[0])/(2*h)
        for j in range(2):
            plus=[1,1];minus=[1,1];plus[j]+=h;minus[j]-=h
            dcs=(recursive(*params,1,plus,(.8,1.2))[0]-recursive(*params,1,minus,(.8,1.2))[0])/(2*h)
            near(dcs/(.5*dc0),mm[j],tol=2e-7)
        if abs(ga-1/ps)<1e-12:near(mm,(bta,bta))
        # Concavity along full consumption-tree chords (analytic universal proof is in manuscript).
        left=(.9,(.8,1.1),(.7,1.3));right=(1.2,(1.3,.9),(1.4,.8));weight=.37
        lc=recursive(*params,*left)[0];rc=recursive(*params,*right)[0]
        mixed=(weight*left[0]+(1-weight)*right[0],tuple(weight*x+(1-weight)*y for x,y in zip(left[1],right[1])),tuple(weight*x+(1-weight)*y for x,y in zip(left[2],right[2])))
        require(recursive(*params,*mixed)[0]>=weight*lc+(1-weight)*rc-1e-12,'recursive concavity');count+=1
    # Last-transition normalization and internal-habit derivative independently differenced.
    for ps in (.5,2,3):
        rho=1-1/ps;k=.1**(1/rho);near(.1*k**(1-rho),k)
    h=1e-6
    def ih(c,d):return log(c)+.9*log(d-.2*c)
    d0=(ih(1+h,1.2)-ih(1-h,1.2))/(2*h);d1=(ih(1,1.2+h)-ih(1,1.2-h))/(2*h)
    near(d0,.82,tol=1e-8);near(d1/d0,.9/.82,tol=1e-8)
    swapped=recursive(.9,4,2,1,(1,1),(1.2,.8));near(swapped[2],ce);near(swapped[3],tuple(reversed(ezm)))
    # Normal-mgf analytic checks, geometric finite sums and bubble terminal term.
    near(sqrt(exp(risk*risk*sigma*sigma)-1),sharpe)
    for persistence in (.5,.95,-.4):
        n=30;near(sum(.001*persistence**j for j in range(n)),.001*(1-persistence**n)/(1-persistence))
    for t in (0,1,10,100):near(.9**t*(2*.9**(-t)),2)
    bad=(lambda:crra(1,2,1,(1,2),(.5,.5)),lambda:crra(.9,0,1,(1,2),(.5,.5)),lambda:crra(.9,2,0,(1,2),(.5,.5)),lambda:crra(.9,2,1,(0,2),(.5,.5)),lambda:crra(.9,2,1,(1,2),(.5,.4)),lambda:crra(.9,2,1,(1,2),(1,0)),lambda:recursive(.9,1,2,1,(1,1),(1,1)),lambda:recursive(.9,2,1,1,(1,1),(1,1)),lambda:recursive(.9,2,2,1,(1,1),(-1,1)),lambda:mean((1,2),(.5,.5),0),lambda:mean((1,2),(.5,.5),2),lambda:scalar(float('nan')),lambda:scalar(True))
    for fn in bad:
        try:fn()
        except ValueError:rejections+=1
        else:raise ValueError('invalid input accepted')
    require(rejections==len(bad),'all domain rejections')
    return {'chapter':'v14-c07','comparisons':count,'domain_rejections':rejections,'worked_examples':len(doc.worked),'solutions':len(doc.solutions),'input_markers':len(inputs),'result_markers':len(values),'runtime_files':len(FILES),'status':'passed'}

if __name__=='__main__':
    check()
