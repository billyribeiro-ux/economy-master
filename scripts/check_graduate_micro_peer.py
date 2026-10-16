"""Separate micro qualifying review: primitive reconstruction, no author code execution."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product,permutations
import hashlib,json,math,re
FILES=['content/cross-assessments/parts/graduate-micro.html','scripts/check_graduate_micro.py','content/reviews/graduate-micro-sources.json','content/reviews/graduate-micro-author.json','scripts/check_graduate_micro_peer.py','content/reviews/graduate-micro-peer.json']
def need(ok,why):
    if not ok:raise ValueError(why)
def strict(s):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'duplicate JSON');d[k]=v
        return d
    return json.loads(s,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def numeric(s):
    s=s.split('=',1)[-1].strip();tok=re.findall(r'[-+]?\d+(?:/\d+|\.\d+)?|[(),]',s);need(''.join(tok)==re.sub(r'\s','',s),'numeric grammar');i=0
    def item():
        nonlocal i
        need(i<len(tok),'incomplete number')
        if tok[i]=='(':
            i+=1;a=[item()]
            while i<len(tok)and tok[i]==',':i+=1;a.append(item())
            need(i<len(tok)and tok[i]==')','tuple closure');i+=1;return a
        x=F(tok[i]);i+=1;return x
    result=item();need(i==len(tok),'numeric trailing tokens');return result
class Read(HTMLParser):
    def __init__(self):super().__init__();self.inputs={};self.outputs={};self.ids=[];self.prompts={};self.solutions=[];self.rubrics={};self.domains=[];self.forms=[];self.sources={};self.links=[];self.capture=None;self.bits=[];self.details=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if t=='h1':raise ValueError('field h1')
        if'id'in a:self.ids.append(a['id'])
        if t=='h2':self.forms.append(a.get('id'))
        if t=='a'and'href'in a:self.links.append(a['href'])
        if t=='details':self.details.append('solutions'in a.get('class','').split())
        if'data-points'in a:need(a['id']not in self.prompts,'duplicate prompt');self.prompts[a['id']]=int(a['data-points'])
        if'data-solution-for'in a:need(any(self.details),'solution disclosure');self.solutions.append(a['data-solution-for'])
        if'data-rubric-for'in a:need(a['data-rubric-for']not in self.rubrics,'duplicate rubric');self.rubrics[a['data-rubric-for']]=[int(x)for x in a['data-rubric-points'].split(',')]
        if'data-domain'in a:self.domains.append((a['data-domain'],int(a['data-domain-points'])))
        if'data-source'in a:need(a['data-source']not in self.sources,'duplicate citation');self.sources[a['data-source']]=a['href']
        for k in ['data-input','data-result']:
            if k in a:need(self.capture is None,'nested marker');self.capture=(t,k,a[k]);self.bits=[]
    def handle_data(self,s):
        if self.capture:self.bits.append(s)
    def handle_endtag(self,t):
        if t=='details':self.details.pop()
        if self.capture and self.capture[0]==t:
            _,kind,k=self.capture;d=self.inputs if kind=='data-input'else self.outputs;need(k not in d,'duplicate marker');d[k]=numeric(''.join(self.bits));self.capture=None

def square_root(q):
    q=F(q);need(q>=0,'nonnegative radical');a=math.isqrt(q.numerator);b=math.isqrt(q.denominator)
    return F(a,b)if a*a==q.numerator and b*b==q.denominator else math.sqrt(float(q))
def consumer(p,q,m):
    need(p>0 and q>0 and m>=0,'consumer domain');r=square_root(p/q);y=m/(p/r+q);x=y/r;return [x,y,m/(square_root(p)+square_root(q))**2]
def utility(x,y):need(x>=0 and y>=0,'consumption domain');return x*y/(x+y)if x+y else F(0)
def expense(p,q,u):need(p>0 and q>0 and u>=0,'dual domain');return u*(p+q+2*square_root(p*q))
def cooperation(delta,epsilon):need(0<=delta<1 and 0<=epsilon<=1,'repeated domain');k=delta*(1-epsilon);return k,F(2)/(1-k)
def trade(v,c,buyer_report,seller_report):
    need(all(0<=x<=1 for x in [v,c,buyer_report,seller_report]),'trade type/report domain')
    if buyer_report>seller_report:return v-seller_report,buyer_report-c,buyer_report-seller_report
    return F(0),F(0),F(0)
def train(masses,gains,costs,subsidy):
    need(len(masses)==len(gains)==len(costs)>0 and all(x>=0 for x in masses)and sum(masses)==1,'type masses');need(subsidy>=0 and all(c>=0 for c in costs),'training costs');d=[int(g-c+subsidy>=0)for g,c in zip(gains,costs)];take=sum(p*x for p,x in zip(masses,d));earn=sum(p*x*g for p,x,g in zip(masses,d,gains));private=sum(p*x*(g-c+subsidy)for p,x,g,c in zip(masses,d,gains,costs));return d,take,earn,private,subsidy*take

def root_of_decreasing(fn,lo,hi):
    need(lo<hi and fn(lo)>0 and fn(hi)<0,'strict root bracket')
    for _ in range(100):
        mid=(lo+hi)/2
        if fn(mid)>0:lo=mid
        else:hi=mid
    return (lo+hi)/2

def plant(w,taste,fixed,k):
    need(w>fixed>0 and taste>0 and k>0,'plant domain');upper=math.sqrt(float((w-fixed)/k));x=root_of_decreasing(lambda z:float(taste)/(1+z)-2*float(k)*z,0.,upper);y=float(w-fixed)-float(k)*x*x;s=float(fixed)-float(k)*x*x;need(s>=0,'subsidy construction domain');return x,y,s

def solve(M,b):
    n=len(b);a=[list(row)+[v]for row,v in zip(M,b)]
    for j in range(n):
        p=next((i for i in range(j,n)if a[i][j]),None);need(p is not None,'singular');a[j],a[p]=a[p],a[j]
        for i in range(j+1,n):
            f=a[i][j]/a[j][j]
            for k in range(j,n+1):a[i][k]-=f*a[j][k]
    x=[F(0)]*n
    for i in reversed(range(n)):x[i]=(a[i][-1]-sum(a[i][j]*x[j]for j in range(i+1,n)))/a[i][i]
    return x

def cournot(A,lo,hi,pl,cap):
    need(A>0 and 0<=lo<hi and 0<pl<1 and cap>0 and 2*cap<=A,'Cournot domain');weights=[pl,1-pl];costs=[lo,hi];M=[[F(int(i==j))for j in range(4)]for i in range(4)]
    for i in range(4):
        rival=2 if i<2 else 0
        for z in range(2):M[i][rival+z]+=weights[z]/2
    q=solve(M,[(A-costs[i%2])/2 for i in range(4)]);need(all(0<x<cap for x in q),'interior Cournot construction');tot=[];profits=[];probs=[]
    for i,j in product(range(2),repeat=2):
        probs.append(weights[i]*weights[j]);tot.append(q[i]+q[2+j]);profits.append(q[i]*(A-q[i]-q[2+j]-costs[i]))
    mu=sum(p*t for p,t in zip(probs,tot));var=sum(p*(t-mu)**2 for p,t in zip(probs,tot));profit=sum(p*t for p,t in zip(probs,profits));corr=[(A-c)/3 for c in costs];corrmu=sum(p*2*z for p,z in zip(weights,corr));corrvar=sum(p*(2*z-corrmu)**2 for p,z in zip(weights,corr));corrprofit=sum(p*z*z for p,z in zip(weights,corr));wrong=[(A-c)/3 for c in costs];dev=(q[0]-wrong[0])**2
    return q,mu,profit,var,corrvar,corrprofit,dev

def core(S,u):
    need(len(S)==2 and all(len(row)==2 for row in S)and all(x>=0 for row in S for x in row),'assignment matrix');need(len(u)==4 and min(u)>=0,'payoff domain');a,b,A,B=u
    return a+B==S[0][1]and b+A==S[1][0]and a+A>=S[0][0]and b+B>=S[1][1]
def insurance(p,loss,benefit,a):
    need(0<p<1 and loss>0 and 0<=benefit<=loss and a>=0,'insurance domain')
    if a==0:return float(p*benefit)
    return (math.log1p(float(p)*math.expm1(a*float(loss)))-math.log1p(float(p)*math.expm1(a*float(loss-benefit))))/a

def oracle(x):
    o={};p,q,m,pn,qn=x['a1'];old=consumer(p,q,m);new=consumer(pn,qn,m);u=old[2];H=[[-u*square_root(q/p)/(2*p),u/(2*square_root(p*q))],[u/(2*square_root(p*q)),-u*square_root(p/q)/(2*q)]]
    o.update({'a1-old':old,'a1-new':new,'a1-hessian':H,'a1-money':[expense(pn,qn,u)-m,m-expense(p,q,new[2])]})
    w1,w2,t1,t2=x['a2'];total=t1+t2;privateX2=total/2;plannerX2=total/4;profit=privateX2;privatey=[w1+profit/2-t1,w2+profit/2-t2];tax=2*plannerX2;rebate=tax/2;newy=[w1+plannerX2/2+rebate-t1,w2+plannerX2/2+rebate-t2];gain=[float(n-y)+(float(privateX2-plannerX2))/2+float(t)*math.log(math.sqrt(float(plannerX2/privateX2)))for n,y,t in zip(newy,privatey,[t1,t2])]
    o.update({'a2-private':[profit]+privatey,'a2-efficient-output-square':plannerX2,'a2-tax-accounts':[tax,rebate,rebate]+newy,'a2-gains':gain})
    k,V=cooperation(*x['a3']);o.update({'a3-threshold':F(1,2),'a3-monitor':[k,V]})
    need(x['a4']==[0,1,0,1],'unit uniform support')
    # Integrate the polynomial (1-c)^2/2 term by term on [0,1].
    integral=sum(v/F(j+1)for j,v in enumerate([F(1,2),F(-1),F(1,2)]));posted=F(1,2)*F(1,2)/2
    o.update({'a4-firstbest':integral,'a4-subsidy':integral,'a4-reserve':F(1),'a4-posted':[posted,integral-posted]})
    mass,gains,costs=x['a5'];d0,take0,y0,u0,s0=train(mass,gains,costs,F(0));d1,take1,y1,u1,s1=train(mass,gains,costs,F(2));need(take1>take0,'positive first stage');o.update({'a5-experiment':[take0,take1,take1-take0,y1-y0],'a5-estimands':[(y1-y0)/(take1-take0),sum(p*g for p,g in zip(mass,gains))],'a5-welfare':[u1-u0,-s1,(u1-u0)-s1]})
    p,q,m,u=x['b1'];need(p>0 and q>0 and m>0 and u>0 and p==q/2,'nonconvex diagnostic tie');o.update({'b1-demand':[[m/p,F(0)],[F(0),m/q]],'b1-hicks':min(p*u,q*u/2),'b1-supergradient':[u/2,u/4],'b1-cv':min(F(3,2)*u,q*u/2)-m})
    w,t,f,k=x['b2'];X,Y,s=plant(w,t,f,k);o.update({'b2-optimum':[X,Y],'b2-subsidy':s,'b2-cost-comparison':[f+k/4,(f+k)/2]})
    q,mu,profit,var,cvar,cprofit,dev=cournot(*x['b3']);prob=x['b3'][3];o.update({'b3-independent':[q[0],q[1],prob*q[0]+(1-prob)*q[1]],'b3-independent-moments':[mu,profit,dev],'b3-correlation-comparison':[var,cvar,cprofit]})
    S=x['b4'];diag=S[0][0]+S[1][1];cross=S[0][1]+S[1][0];need(cross>max(diag,*sum(S,[])),'strict cross efficiency');divisions=[[F(3),F(1),S[1][0]-1,S[0][1]-3],[F(4),F(1),S[1][0]-1,S[0][1]-4]];need(all(core(S,u)for u in divisions),'core examples');o.update({'b4-surplus':cross,'b4-difference-domain':[S[0][0]-S[1][0],S[0][1]-S[1][1]],'b4-divisions':divisions,'b4-new-division':[F(4),F(1),F(4),F(2)]})
    wealth,loss,full,benefit,offer,pr=x['b5'];a=math.log((1-float(pr))/float(pr))/float(full);need(abs(insurance(pr,loss,loss,a)-float(full))<1e-12,'full WTP equation');o.update({'b5-partial-reservation':insurance(pr,loss,benefit,a),'b5-profit':offer-pr*benefit,'b5-mle':F(30,90)})
    return o

def check(root=None):
    root=Path(root)if root is not None else Path(__file__).resolve().parents[1];snap={p:(root/p).read_bytes()for p in FILES};r=Read();r.feed(snap[FILES[0]].decode());count=0;rejects=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,list):
            need(isinstance(b,list)and len(a)==len(b),'shape '+label)
            for j,(v,w)in enumerate(zip(a,b)):eq(v,w,label+str(j))
        elif isinstance(a,float):need(math.isfinite(a)and abs(a-float(b))<6e-12,'numeric '+label);count+=1
        else:need(F(a)==F(b),'exact '+label);count+=1
    def reject(fn):
        nonlocal rejects
        try:fn()
        except(ValueError,TypeError,ZeroDivisionError):rejects+=1
        else:raise ValueError('invalid domain accepted')
    ids=['graduate-micro-'+f+str(n)+s for f in 'ab'for n in range(1,6)for s in 'abcd'];need(list(r.prompts)==ids and r.solutions==ids and set(r.rubrics)==set(ids),'forty paired solutions');need(all(v==5 for v in r.prompts.values())and all(sum(v)==5 and min(v)>0 for v in r.rubrics.values()),'additive rubrics');need(len(r.ids)==len(set(r.ids))and all(s.startswith('graduate-micro-')for s in r.ids),'scoped unique IDs');need(r.forms==['graduate-micro-a','graduate-micro-b'],'two forms')
    domains=['choice_duality_and_welfare','equilibrium_and_distribution','strategic_incentives_and_information','mechanism_contracts_and_matching','theory_to_research_evidence'];need(r.domains==[(d,20)for d in domains]*2,'five20point domains');need(set(r.inputs)=={f+str(n)for f in 'ab'for n in range(1,6)},'ten input groups');o=oracle(r.inputs);need(set(o)==set(r.outputs),'complete visible reconstruction')
    for k,v in o.items():eq(v,r.outputs[k],k)
    sources=strict(snap[FILES[2]]);need({s['id']:s['url']for s in sources['sources']}==r.sources,'exact citation URLs');need('v12-c04.html'in r.links and 'v12-c03.html'in r.links,'scored V12 routes')
    for record in [strict(snap[FILES[3]]),strict(snap[FILES[5]])]:
        bindings=record['payload_bindings'];bindings=bindings if isinstance(bindings,list)else[dict(path=k,**v)for k,v in bindings.items()]
        for b in bindings:
            data=(root/b['path']).read_bytes();need(len(data)==b['bytes']and hashlib.sha256(data).hexdigest()==b['sha256'],'payload binding')
    peer=strict(snap[FILES[5]]);need(set(peer['payload_bindings'])==set(FILES[:-1]),'five nonself peer bindings')
    # Alternative feasible choices, compensation and funded implementation checks.
    for p,q,m in product([F(1),F(4)],[F(1),F(9)],[F(0),F(6)]):
        xx,yy,u=consumer(p,q,m);eq(p*xx+q*yy,m,'budget');eq(utility(xx,yy),u,'utility')
        for j in range(11):
            x=m/p*F(j,10);y=(m-p*x)/q;need(utility(x,y)<=u+1e-12,'global consumer witness');count+=1
        eq(expense(p,q,u),m,'dual recovery')
    H=o['a1-hessian'];p,q,*_=r.inputs['a1']
    for row in H:eq(row[0]*p+row[1]*q,0,'price null')
    for z in product([F(-2),F(0),F(3)],repeat=2):need(sum(z[i]*H[i][j]*z[j]for i in range(2)for j in range(2))<=0,'negative semidefinite');count+=1
    for v,c,report in product([F(j,4)for j in range(5)],repeat=3):
        truthful=trade(v,c,v,c);buyer=trade(v,c,report,c);seller=trade(v,c,v,report);need(truthful[0]>=buyer[0]and truthful[1]>=seller[1],'all-report finite IC witness');need(min(truthful)>=0 and truthful[2]<=1,'IR and reserve');count+=2
    for p in [F(j,20)for j in range(21)]:need(p*(1-p)/2<=F(1,8),'posted global witness');count+=1
    for delta,eps in product([F(0),F(1,2),F(3,4)],[F(0),F(1,5),F(1)]):
        k,v=cooperation(delta,eps);eq(v,F(2)+k*v,'cooperation fixed point');need((v>=4)==(k>=F(1,2)),'threshold equivalence');count+=1
    X,Y,s=plant(*r.inputs['b2']);price=2*X;eq(price*X+s,1+X*X,'plant funding');eq(10-s-price*X,Y,'household tax account');need(3*math.log1p(X)+Y>10,'beats shutdown');count+=1
    for candidate in [0.1,0.5,1.,2.,3.]:need(9-candidate*candidate+3*math.log1p(candidate)<=Y+3*math.log1p(X)+1e-12,'planner global witness');count+=1
    A,cl,ch,p,cap=r.inputs['b3'];q,*_=cournot(*r.inputs['b3']);meanr=p*q[2]+(1-p)*q[3]
    for i,c in enumerate([cl,ch]):
        v=q[i]*(A-c-meanr-q[i])
        for j in range(17):
            z=cap*F(j,16);need(z*(A-c-meanr-z)<=v,'Bayesian global deviation');count+=1
    for S in [r.inputs['b4'],[[F(8),F(6)],[F(5),F(1)]]]:
        for u1,u2 in product(range(7),range(8)):
            v=[F(u1),F(u2),S[1][0]-u2,S[0][1]-u1]
            if min(v)<0:continue
            valid=core(S,v);ineq=S[0][0]-S[1][0]<=u1-u2<=S[0][1]-S[1][1];need(valid==ineq,'complete core inequalities');count+=1
    wealth,L,full,benefit,premium,pr=r.inputs['b5'];need(insurance(F(1,2),L,benefit,0)<float(premium)<o['b5-partial-reservation'],'two insurance decisions');count+=1
    last=1.5
    for a in [0.01,0.1,0.3,1.,2.]:
        p=1/(1+math.exp(3*a));h=insurance(p,L,benefit,a);need(last<h<3,'strict reservation monotonicity');need(abs(insurance(p,L,L,a)-3)<1e-12,'CARA observational family');last=h;count+=2
    for fn in [lambda:consumer(0,1,1),lambda:consumer(1,-1,1),lambda:consumer(1,1,-1),lambda:expense(1,1,-1),lambda:utility(-1,1),lambda:square_root(-1),lambda:cooperation(F(1),0),lambda:cooperation(0,F(2)),lambda:trade(F(2),0,0,0),lambda:train([F(1,2)],[1],[1],0),lambda:train([F(1)],[1],[-1],0),lambda:plant(1,3,1,1),lambda:root_of_decreasing(lambda z:z,0.,1.),lambda:solve([[F(0)]],[F(1)]),lambda:cournot(8,0,2,1,4),lambda:cournot(8,0,2,F(1,2),5),lambda:core([[1,2]], [0]*4),lambda:core([[1,2],[3,4]],[-1,0,0,0]),lambda:insurance(0,6,3,1),lambda:insurance(F(1,3),6,7,1),lambda:insurance(F(1,3),6,3,-1),lambda:numeric('(1,2'),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":NaN}')]:reject(fn)
    need({p:(root/p).read_bytes()for p in FILES}==snap,'runtime mutation');result=dict(status='passed',assessment='graduate-qualifying',field='micro-peer',forms=2,solved_subparts=40,points_per_form=100,input_groups=len(r.inputs),checked_results=len(o),comparisons=count,domain_rejections=rejects,runtime_files=6,unresolved_findings=0);json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
