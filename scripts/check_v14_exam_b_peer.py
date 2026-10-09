"""Independent Form B peer: primitive reconstruction, no author execution."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product,permutations
from math import log,sqrt,isfinite
import ast,json,re
FILES=('content/assessments/parts/v14-exam-b.html','scripts/check_v14_exam_b.py','content/reviews/v14-exam-b-sources.json','content/reviews/v14-exam-b-author.json','scripts/check_v14_exam_b_peer.py','content/reviews/v14-exam-b-peer.json')
def need(ok,message):
    if not ok:raise ValueError(message)
def real(x):
    need(type(x) in (int,float,F) and isfinite(x),'finite number');return F(str(x)) if not isinstance(x,F) else x
def law(p):
    need(isinstance(p,(tuple,list)) and len(p)>0,'probability vector');p=tuple(map(real,p));need(min(p)>=0 and sum(p)==1,'unit probability');return p
def square(a):
    need(isinstance(a,(tuple,list)) and len(a)>0,'matrix');n=len(a);need(all(isinstance(row,(tuple,list)) and len(row)==n for row in a),'square matrix');return tuple(tuple(map(real,row)) for row in a)
def determinant(a):
    a=square(a);n=len(a);total=F(0)
    for perm in permutations(range(n)):
        sign=(-1)**sum(perm[i]>perm[j] for i in range(n) for j in range(i+1,n));term=F(sign)
        for i,j in enumerate(perm):term*=a[i][j]
        total+=term
    return total
def cramer(a,b):
    a=square(a);need(isinstance(b,(tuple,list)) and len(b)==len(a),'right-hand dimension');b=tuple(map(real,b));d=determinant(a);need(d!=0,'singular matrix');return tuple(determinant(tuple(tuple(b[i] if j==k else a[i][j] for j in range(len(a))) for i in range(len(a))))/d for k in range(len(a)))
def dot(x,y):
    need(len(x)==len(y),'dot dimension');return sum(a*b for a,b in zip(x,y))
def matvec(a,v):return tuple(dot(row,v) for row in a)
def literal(text):
    tree=ast.parse(text.replace('−','-').split('=',1)[-1].strip(),mode='eval')
    def read(n):
        if isinstance(n,ast.Constant):return real(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return read(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return read(n.left)/read(n.right)
        raise ValueError('numeric expression only')
    return read(tree.body)
def strict(raw):
    def pairs(items):
        result={}
        for k,v in items:need(k not in result,'duplicate JSON key');result[k]=v
        return result
    def invalid(x):raise ValueError('nonfinite JSON')
    result=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid);json.dumps(result,allow_nan=False);return result
def policy_value(rewards,successors,beta,policy):
    beta=real(beta);need(0<=beta<1,'discount');n=len(rewards);need(n>0 and len(successors)==len(policy)==n,'policy shape');need(all(type(j)==int and 0<=j<len(rewards[i]) and len(rewards[i])==len(successors[i]) for i,j in enumerate(policy)),'policy actions');need(all(type(x)==int and 0<=x<n for row in successors for x in row),'next states');A=tuple(tuple(F(i==j)-beta*F(successors[i][policy[i]]==j) for j in range(n)) for i in range(n));return cramer(A,tuple(rewards[i][policy[i]] for i in range(n)))
def golden(f,lo,hi):
    lo=float(real(lo));hi=float(real(hi));need(lo<hi,'optimization interval');ratio=(sqrt(5)-1)/2;x=hi-ratio*(hi-lo);y=lo+ratio*(hi-lo)
    for _ in range(100):
        if f(x)>f(y):hi,y=y,x;x=hi-ratio*(hi-lo)
        else:lo,x=x,y;y=lo+ratio*(hi-lo)
    return (lo+hi)/2

def liquidity(w,early,payment,R):
    w,early,payment,R=map(real,(w,early,payment,R));need(0<=w<=1 and 0<early<1 and payment>0 and early*payment<=1 and R>=1,'withdrawal domain');storage=early*payment;long=1-storage;withdraw=min(w*payment,1);usedstorage=min(storage,withdraw);liquidated=withdraw-usedstorage;return storage-usedstorage+R*(long-liquidated)
def stationary(p,q):
    p,q=map(real,(p,q));need(0<p<1 and 0<q<1,'interior transition');mean=p/(p+q);return mean,mean*(1-mean),(1-p-q)*mean*(1-mean)

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=set();self.headings=[];self.prompts={};self.answers={};self.domains={};self.markers={};self.urls={};self.links=[];self.text=''
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'repeated attribute')
        if 'id' in a:need(a['id'] not in self.ids,'repeated ID');self.ids.add(a['id'])
        if t=='h1':raise ValueError('unexpected h1')
        if t=='h2':self.headings.append(a.get('id'))
        if 'data-domain' in a:need(a['data-domain'] not in self.domains,'repeated domain');self.domains[a['data-domain']]=[]
        if 'data-points' in a:
            key=a['id'];domain=next(d['data-domain'] for tag,d in reversed(self.stack) if 'data-domain' in d);self.prompts[key]=(int(a['data-points']),domain);self.domains[domain].append(key)
        if 'data-solution-for' in a:
            key=a['data-solution-for'];need(key not in self.answers,'repeated answer');need(any(tag=='details' and 'solutions' in d.get('class','').split() for tag,d in self.stack),'answer outside solutions');self.answers[key]=''
        for attr in ('data-input','data-calc'):
            if attr in a:need(a[attr] not in self.markers,'repeated marker');self.markers[a[attr]]=[attr,'']
        if 'data-source' in a:need(a['data-source'] not in self.urls,'repeated source');self.urls[a['data-source']]=a['href']
        if 'href' in a:self.links.append(a['href'])
        if t not in ('br','hr','img','meta','input','link'):self.stack.append((t,a))
    def handle_data(self,s):
        self.text+=s
        for tag,a in self.stack:
            if 'data-solution-for' in a:self.answers[a['data-solution-for']]+=s
            for key in ('data-input','data-calc'):
                if key in a:self.markers[a[key]][1]+=s
    def handle_endtag(self,t):need(self.stack and self.stack[-1][0]==t,'unbalanced HTML');self.stack.pop()

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={p:(base/p).read_bytes() for p in FILES};doc=Document();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'open HTML');author=strict(raw[FILES[3]]);source=strict(raw[FILES[2]]);peer=strict(raw[FILES[5]])
    targets=[f'v14-exam-b-q{i}' for i in range(1,21)];need(list(doc.prompts)==list(doc.answers)==targets,'exact twenty paired answers');need(doc.headings==['form-b','solutions-b'],'headings');need(all(x.startswith('v14-exam-b-') or x in doc.headings for x in doc.ids),'IDs');need(tuple(doc.domains)==('dynamic_distribution','labor_policy','pricing_investment','liquidity_international','quantitative_research') and all(len(xs)==4 for xs in doc.domains.values()),'five domains');need(sum(x[0] for x in doc.prompts.values())==100 and all(x[0]==5 for x in doc.prompts.values()),'points')
    for key in targets:
        answer=doc.answers[key];need(len(answer)>500 and 'Rubric:' in answer,'complete scored answer');rubric=answer.split('Rubric:')[1].strip();parts=rubric.split(';');need(sum(int(re.match(r'\s*(\d+)',x).group(1)) for x in parts)==5,'rubric five points')
    need(all(f'v14-c{i:02d}.html' in doc.links for i in range(1,13)),'all chapter study routes');need(doc.urls=={x['id']:x['url'] for x in source['sources']} and len(doc.urls)==13,'exact source URLs');need(set(author['exact_prompt_solution_audit'])==set(peer['exact_prompt_solution_review'])==set(targets),'complete audits');need(author['unresolved_findings']==peer['unresolved_findings']==[],'open issue')
    for record,expected in ((author,set(FILES[:3])),(peer,set(FILES[:5]))):
        bindings=record['payload_bindings'];need(len(bindings)==len(expected) and {x['path'] for x in bindings}==expected,'nonself bindings')
        for x in bindings:need(len(raw[x['path']])==x['bytes'] and sha256(raw[x['path']]).hexdigest()==x['sha256'],'frozen bytes')
    comparisons=0;rejections=0;seen=set()
    def equal(a,b):
        nonlocal comparisons
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'result shape')
            for x,y in zip(a,b):equal(x,y)
        else:need(isfinite(float(a)) and abs(float(a)-float(b))<2e-9*max(1,abs(float(b))),f'{a} != {b}');comparisons+=1
    def truth(ok,label):
        nonlocal comparisons
        need(ok,label);comparisons+=1
    def result(key,value):equal(literal(doc.markers[key][1]),value);seen.add(key)
    inputs={k:literal(v[1]) for k,v in doc.markers.items() if v[0]=='data-input'}
    expected={'b1-beta':'1/2','b1-model':'((2,0),(1,4),(0,1),(1,0))','b2-transition':'((1/2,1/2,0,0),(1/2,1/2,0,0),(0,0,1/2,1/2),(0,0,1/2,1/2))','b3-growth':'(1/2,2/3,3,6,1)','b4-distributions':'((0,1,3),(0,0,3),(0,1,0),(2/3,0,1/3),2)','b5-matching':'(1,1/2,1/3,1/4,1/4,1,0,5/4)','b6-nk':'(1/2,1,1,1/8,0)','b7-fiscal':'(5/4,3/2,8,1)','b8-floor':'(9/10,1,1/2,2,1,-1/5)','b9-pricing':'((1/2,1/2),(1,1),(1/2,3/2),1,1,(1/2,3/2))','b10-span':'((1/2,1/4,1/4),(0,2,2),1,1,3/8)','b11-q':'(1,4,1,2,1)','b12-overhang':'(60,90,12,20)','b13-run':'(1/3,6/5,3/2,1/5,13/10)','b14-sales':'(1,154/225,3,1,1/3)','b15-currency':'(1/3,2,3/2,3/4,4/5,11/10)','b16-stop':'(2,4,1,1,1,1,1,1,2,1/4,1/5)','b17-beta':'3/4','b18-moments':'(2/5,1/5,3/10,2/5,3/5)','b19-exposure':'((1/3,2/3),(9/10,3/10),(2,1/2))','b20-mechanisms':'(1/10,3/10,-1/50)'}
    need(set(inputs)==set(expected),'primitive inventory')
    for k,v in expected.items():result(k,literal(v))
    beta=inputs['b1-beta'];model=inputs['b1-model'];rewards=model[:2];nxt=tuple(tuple(int(x) for x in row) for row in model[2:]);values={p:policy_value(rewards,nxt,beta,p) for p in product(range(2),repeat=2)};candidate=values[(1,1)];bellman=lambda v:tuple(max(rewards[i][j]+beta*v[nxt[i][j]] for j in range(2)) for i in range(2));tv=bellman(candidate);res=max(abs(x-y) for x,y in zip(tv,candidate));opt=tuple(max(v[i] for v in values.values()) for i in range(2));result('b1-bellman',tv);result('b1-residual',res);result('b1-bound',res/(1-beta));result('b1-optimum',opt);result('b1-losses',tuple(x-y for x,y in zip(opt,candidate)));equal(bellman(opt),opt)
    for v in values.values():truth(all(x<=y for x,y in zip(v,opt)),'all stationary policies bounded')
    Q=inputs['b2-transition'];wealth=(0,0,2,2);advance=lambda p:tuple(sum(p[i]*Q[i][j] for i in range(4)) for j in range(4))
    for initial in ((1,0,0,0),(0,0,0,1),(F(1,5),F(2,5),F(1,10),F(3,10))):
        p=advance(initial);equal(advance(p),p);equal(dot(p,wealth),dot(initial,wealth))
    mix=F(1,2);result('b2-clearing-distribution',((1-mix)/2,(1-mix)/2,mix/2,mix/2))
    alpha,beta,al,ah,k=inputs['b3-growth'];y=al*float(k)**float(alpha);bad=F(1,2);c=(1-bad)*y;kp=bad*y;rhs=sum(prob*beta/(float((1-bad)*a)*kp**float(alpha))*float(alpha*a)*kp**float(alpha-1) for prob,a in zip((F(3,4),F(1,4)),(al,ah)));result('b3-proposed-allocation',(c,kp));result('b3-euler',(1/c,rhs));s=alpha*beta;result('b3-correct-share',s);result('b3-correct-allocation',((1-s)*y,s*y))
    for state in (al,ah):
        for kval in (.1,1,10):
            out=float(state)*kval**float(alpha);cp=(1-float(s))*out;knew=float(s)*out
            for anext in (al,ah):equal(1/cp,float(beta)*float(alpha*anext)*knew**float(alpha-1)/((1-float(s))*float(anext)*knew**float(alpha)))
    wealth,g,mu,nu,endow=inputs['b4-distributions'];cons=tuple(a+endow-b for a,b in zip(wealth,g));result('b4-next-means',(dot(mu,g),dot(nu,g)));result('b4-type-consumption',cons);result('b4-aggregate-consumption',(dot(mu,cons),dot(nu,cons)));equal(dot(mu,wealth),dot(nu,wealth));truth(min(cons)>0,'all feasible types')
    A,alpha,eta,r,sep,cost,home,output=inputs['b5-matching'];theta=F(1);f=A;fill=A;wrong=home+eta*(output-home);result('b5-wrong-job-value',(output-wrong)/(r+sep));J=cost/fill;surplus=eta*J/(1-eta);w=home+(r+sep+f)*surplus;result('b5-correct-wage',w);equal((output-w)/(r+sep),J);truth(eta!=alpha,'Hosios mismatch')
    beta,sigma,kappa,phi,phix=inputs['b6-nk'];forward=((1+phix/sigma+kappa/(beta*sigma),(phi-1/beta)/sigma),(-kappa/beta,1/beta));trace=forward[0][0]+forward[1][1];det=determinant(forward);roots=((float(trace)-sqrt(float(trace*trace-4*det)))/2,(float(trace)+sqrt(float(trace*trace-4*det)))/2);result('b6-forward',forward);result('b6-roots',roots)
    for amplitude in (-2,F(1,10),3):
        for t in (0,1,4,10):
            x=amplitude*F(3,4)*F(1,2)**t;pi=amplitude*F(1,2)**t;xn=x/2;pn=pi/2;equal(x,xn-(phi*pi-pn)/sigma);equal(pi,beta*pn+kappa*x)
    R,G,old,Y0=inputs['b7-fiscal'];result('b7-terminal',old);sur=(R-1)*old;result('b7-repair-surplus',sur)
    for t in (0,1,10,30):equal(old*R**(t+1)/R**(t+1),old);truth(old*R**(t+1)/(Y0*G**(t+1))<old/Y0,'falling ratio');equal(sum(sur/R**(j+1) for j in range(t+1))+old/R**(t+1),old)
    beta,sigma,kappa,phi,phix,rn=inputs['b8-floor'];floor=log(float(beta));feedback=phi*kappa+phix;uncon=float(rn)/(1+float(feedback)/float(sigma));truth(float(feedback)*uncon<floor,'unconstrained floor violation');x=float(rn)-floor/float(sigma);pi=float(kappa)*x;shadow=float(feedback)*x;result('b8-floor-solution',(x,pi,floor));result('b8-shadow',shadow);truth(shadow<floor,'binding shadow');equal(x+max(floor,shadow)/float(sigma),rn)
    prob,safe,pay,ps,px,m=inputs['b9-pricing'];law(prob);price=lambda payoff,kernel:sum(p*x*z for p,x,z in zip(prob,payoff,kernel));result('b9-proposed-risky-price',price(pay,m));correct=cramer(tuple(tuple(p*x for p,x in zip(prob,row)) for row in (safe,pay)),(ps,px));result('b9-correct-kernel',correct);equal(price(safe,m),ps)
    prob,pay,ps,px,pz=inputs['b10-span'];law(prob);new=cramer((prob,tuple(p*x for p,x in zip(prob,pay)),(0,prob[1],0)),(ps,px,pz));result('b10-kernel-domain',(-1,1));result('b10-identified-kernel',new)
    for t in (F(-9,10),0,F(3,5),F(9,10)):
        ker=(1,1+t,1-t);equal(dot(prob,ker),ps);equal(sum(p*x*z for p,x,z in zip(prob,pay,ker)),px);truth(min(ker)>0,'positive unspanned kernel')
    k,F0,R,cap,cash=inputs['b11-q'];feasible=min(float(cap),sqrt(1+2*float(cash))-1);salvage=lambda I,F0:float(F0)+3*(float(k)+I)-(float(k)+I)**2/2;objective=lambda I:float(cash)-I-I*I/2+salvage(I,F0);I=golden(objective,0,feasible);exact=(3-k-R)/(1+R);equal(objective(I),objective(float(exact)));truth(abs(I-float(exact))<1e-6,"independent maximizer location");I=exact;K=k+I;cost=I+I*I/2;result('b11-optimum',(I,K,3-K,cash-cost));result('b11-average-q',(F0+3*K-K*K/2)/K);result('b11-new-average-q',(F0+36+3*K-K*K/2)/K)
    for trial in (0,F(1,4),F(3,5),F(7,10)):truth(objective(float(trial))<=objective(float(I))+1e-12,'funded global investment');equal(salvage(float(trial),F0+36)-salvage(float(trial),F0),36)
    assets,debt,J,Z=inputs['b12-overhang'];oldcred=min(assets,debt);oldeq=max(assets-debt,0);newcred=min(assets+Z,debt);neweq=max(assets+Z-debt,0);result('b12-old-equity-gain',neweq-oldeq-J);interval=(oldcred,assets+Z-oldeq-J);result('b12-face-interval',interval);face=sum(interval)/2;result('b12-strict-gains',(face-oldcred,assets+Z-face-oldeq-J));equal(neweq-oldeq-J+newcred-oldcred,Z-J)
    early,payment,R,shift,guarantee=inputs['b13-run'];storage=early*payment;c2=R*(1-storage)/(1-early);queue=(1/payment)*(-1/(payment+shift))+(1-1/payment)*(-1/shift);result('b13-patient-consumption',c2);result('b13-run-utility',queue);shortfall=lambda w:max(F(0),guarantee*(1-w)-liquidity(w,early,payment,R));breakpoints=(F(0),early,1/payment,F(1));reserve=max(map(shortfall,breakpoints));result('b13-reserve',reserve)
    for w in (F(i,120) for i in range(121)):truth(shortfall(w)<=reserve,'piecewise reserve witness');truth(liquidity(w,early,payment,R)>=0,'bank remaining resources')
    truth(guarantee>payment and queue>-1/shift,'credible patient incentive and run')
    K,D,L,p0,a=inputs['b14-sales'];aa=a;bb=a*(L-1)*K-p0;cc=L*D-p0*(L-1)*K;disc=bb*bb-4*aa*cc;zs=tuple((-float(bb)+sgn*sqrt(float(disc)))/(2*float(aa)) for sgn in (-1,1));prices=tuple(float(p0)-float(a)*z for z in zs);sheets=[];spending=[];slopes=[]
    for z,p in zip(zs,prices):
        ar=p*(float(K)-z);dr=float(D)-p*z;eq=ar-dr;sheets.append((ar,dr,eq));spending.append(p*z);slopes.append(float(L*D*a)/(p*p));truth(0<z<float(K) and eq>0 and dr>=0 and p*z<1,'sale feasibility');equal(ar,float(L)*eq);equal(z,float(L*D)/p-float((L-1)*K));smaller=max(0,z-.001);truth(p*(float(K)-smaller)>float(L)*eq,'less sale violates given-price cap')
    result('b14-prices',prices);result('b14-balance-sheets',sheets);result('b14-buyer-spending',spending);result('b14-iteration-slopes',slopes)
    pl,E0,ml,mh,xl,xh=inputs['b15-currency'];probs=(pl,1-pl);m=(ml,mh);X=(xl,xh);mf=tuple(a*b for a,b in zip(m,X));rd=1/dot(probs,m);rf=1/dot(probs,mf);EX=dot(probs,X);cov=dot(probs,mf)-dot(probs,m)*EX;result('b15-foreign-kernel',mf);result('b15-foreign-rate',rf);result('b15-forward',E0*rd/rf);result('b15-premium',rf*EX-rd);result('b15-covariance',cov);equal(-rd*rf*cov,rf*EX-rd);equal(E0*EX,2)
    y0,y1,D,R,beta,nu,n0,n1,W,kold,knew=inputs['b16-stop'];baseincome=y0-D;uncon=(y1-beta*R*baseincome)/(R*(1+beta));limit=knew*(y0+nu*baseincome)/(R-knew*nu);loan=min(uncon,limit);ct0=baseincome+loan;ct1=y1-R*loan;p0=nu*ct0/n0;p1=nu*ct1/n1;mult=(1/ct0-beta*R/ct1)/R;investment=W+D-loan;result('b16-loan',loan);result('b16-consumptions',(ct0,ct1));result('b16-multiplier',mult);result('b16-foreign-investment',investment);result('b16-stale-error',knew*(y0+2*n0)/R-loan);equal(R*loan,knew*(y0+p0*n0));truth(mult>0,'binding household multiplier');equal(ct0+investment,y0+W);equal(ct1+R*(W+D),y1+R*investment)
    beta=inputs['b17-beta'];reward=lambda a:3-(a-1)**2;coarse=reward(0)/(1-beta);fine=reward(1)/(1-beta);res=reward(1)+beta*coarse-coarse;result('b17-residual',res);result('b17-bound',res/(1-beta));result('b17-value',fine)
    for a in (F(i,10) for i in range(21)):truth(reward(a)<=reward(1),'continuous reward witness')
    mu,p,q,pa,qa=inputs['b18-moments'];result('b18-scale-domain',(0,min(1/mu,1/(1-mu))));covs=tuple(stationary(x,y)[2] for x,y in ((p,q),(pa,qa)));result('b18-lag-covariances',covs)
    for t in (F(1,10),F(1,2),1,F(3,2)):equal(stationary(mu*t,(1-mu)*t)[:2],(mu,mu*(1-mu)))
    masses,mpcs,exposures=inputs['b19-exposure'];law(masses);mean=dot(masses,mpcs);weighted=sum(p*m*e for p,m,e in zip(masses,mpcs,exposures));emean=dot(masses,exposures);direct=masses[0]*mpcs[0]-masses[1]*mpcs[1]/2;result('b19-feedback',(mean,weighted,weighted-mean*emean,direct));result('b19-output-multipliers',(direct/(1-weighted),direct/(1-mean)));equal(masses[0]-masses[1]/2,0);equal(emean,1);truth(abs(weighted)<1,'stable local feedback')
    g1,g2,g3=inputs['b20-mechanisms'];A=((1,2),(1,-1));ab=cramer(A,(g1,g3));result('b20-identified',ab);result('b20-determinant',determinant(A));interval=(-g1/2,g1);result('b20-contrast-domain',interval);equal(g2,3*g1);truth(F(3,20)>interval[1],'outside domain falsification')
    for b in (0,g1/4,g1/2):a=g1-2*b;truth(a>=0 and b>=0,'nonnegative equivalent family');equal((a+2*b,3*a+6*b),(g1,g2))
    need(seen==set(doc.markers),'all visible markers independently checked')
    malformed=[(real,(True,)),(real,(float('nan'),)),(law,((F(1,4),F(1,4)),)),(law,((-1,2),)),(square,(((1,2),),)),(cramer,(((1,0),(0,1)),(1,))), (cramer,(((1,2),(2,4)),(1,2))), (dot,((1,2),(1,))), (literal,('f(1)',)),(literal,('True',)),(literal,('1/0',)),(strict,('{"a":1,"a":2}',)),(strict,('{"a":Infinity}',)),(policy_value,(((1,),),((0,),),1,(0,))), (policy_value,(((1,),),((1,),),F(1,2),(0,))), (policy_value,(((1,),),((0,),),F(1,2),(2,))), (golden,(lambda x:x,2,1)),(liquidity,(-1,F(1,2),1,2)),(liquidity,(0,F(3,4),2,2)),(liquidity,(0,F(1,2),1,F(1,2))), (stationary,(0,F(1,2))), (stationary,(F(1,2),1))]
    for fn,args in malformed:
        try:fn(*args)
        except (ValueError,ZeroDivisionError):rejections+=1
        else:raise ValueError('accepted malformed '+fn.__name__)
    need({p:(base/p).read_bytes() for p in FILES}==raw,'read-only runtime')
    summary=dict(volume='v14',component='exam_b_peer',status='passed',comparisons=comparisons,domain_rejections=rejections,scored_prompts=20,solutions=20,points=100,domains=5,chapters=12,primitive_markers=len(inputs),result_markers=len(doc.markers)-len(inputs),runtime_files=6);json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':check()
