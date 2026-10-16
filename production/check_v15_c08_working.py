"""Portable four-file behavioral chapter author audit; no output or mutation."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import log,sqrt,isfinite
import ast,json
FILES=('production/v15-c08-working.html','production/check_v15_c08_working.py','production/v15-c08-sources-working.json','production/v15-c08-author-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):need(type(x) in (int,float,F) and isfinite(x),'finite nonboolean number');return F(str(x))
def prob(x):x=num(x);need(0<=x<=1,'probability');return x
def literal(text):
    def visit(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.List,ast.Tuple)):return tuple(visit(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('literal grammar')
    return visit(ast.parse(text.split('=',1)[-1].strip(),mode='eval').body)
def record(raw):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'duplicate JSON');d[k]=v
        return d
    def bad(x):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
def saving(E,R,beta,delta,floor=0):
    E,R,beta,delta,floor=map(num,(E,R,beta,delta,floor));need(E>0 and R>0 and 0<beta<=1 and 0<delta<=1 and 0<=floor<E,'saving domain');actual=beta*delta*E/(1+beta*delta);plan=delta*E/(1+delta);return actual,plan,max(actual,floor)
def dated(E,R,beta,delta,s):
    E,R,beta,delta,s=map(num,(E,R,beta,delta,s));need(E>0 and R>0 and 0<beta<=1 and 0<delta<=1 and 0<s<E,'dated utility domain');return float(beta*delta)*(log(E-s)+float(delta)*log(R*s)),log(E-s)+float(beta*delta)*log(R*s)
def refvalue(x,r,lam):
    x,r,lam=map(num,(x,r,lam));need(lam>=1,'loss slope');return (x-r)*(1 if x>=r else lam)
def social(x,y,alpha,gamma):
    x,y,alpha,gamma=map(num,(x,y,alpha,gamma));need(x>=0 and y>=0 and alpha>=gamma>=0 and gamma<1,'social utility domain');return x-alpha*max(y-x,0)-gamma*max(x-y,0)
def gifts(budget,alpha,gamma):
    budget,alpha,gamma=map(num,(budget,alpha,gamma));need(budget>0 and alpha>=gamma>=0 and gamma<1,'dictator domain');return (F(0),F(0)) if gamma<F(1,2) else (F(0),budget/2) if gamma==F(1,2) else (budget/2,budget/2)
def posterior(prior,hi,lo):
    p,h,l=map(prob,(prior,hi,lo));den=p*h+(1-p)*l;need(den>0,'possible signal');return p*h/den
def score(q,y):q=prob(q);need(type(y)is int and y in (0,1),'binary outcome');return 1-(q-y)**2
def cash_report(p):
    p=prob(p)
    if p in (0,1):return float(p)
    left,right=0.,1.
    for _ in range(70):
        q=(left+right)/2;v=float(p)*(1-q)/sqrt(2*q-q*q)-float(1-p)*q/sqrt(1-q*q)
        if v>0:left=q
        else:right=q
    return (left+right)/2
class Reader(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.worked=[];self.prompts=[];self.answers={};self.sources={};self.mark={};self.links=set()
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','chapter fragment heading')
        if 'id' in a:need(a['id'] not in self.ids and a['id'].startswith('v15-c08-'),'scoped IDs');self.ids.add(a['id'])
        if 'href' in a:self.links.add(a['href'])
        if 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if t=='li' and any('exercises' in d.get('class','').split() for k,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            k=a['data-solution-for'];need(k not in self.answers and any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'disclosed exact solution');self.answers[k]=''
        if 'data-source' in a:need(a['data-source'] not in self.sources,'source unique');self.sources[a['data-source']]=a['href']
        for kind in ('data-input','data-result'):
            if kind in a:need(a[kind] not in self.mark,'unique marker');self.mark[a[kind]]=[kind,'']
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for t,a in self.stack:
            if 'data-solution-for' in a:self.answers[a['data-solution-for']]+=s
            for kind in ('data-input','data-result'):
                if kind in a:self.mark[a[kind]][1]+=s
    def handle_endtag(self,t):need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop()
def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(base/f).read_bytes() for f in FILES};d=Reader();d.feed(raw[FILES[0]].decode());d.close();need(not d.stack,'complete HTML');author=record(raw[FILES[3]]);sources=record(raw[FILES[2]]);ids=[f'v15-c08-e{i}' for i in range(1,11)];need(d.prompts==list(d.answers)==ids and len(d.worked)==5 and all(len(v)>450 for v in d.answers.values()),'five cases ten full solutions');need(set(author['exact_solution_review'])==set(ids) and not author['open_findings'],'full author audit');need(d.sources=={s['id']:s['url'] for s in sources['sources']},'exact source routes');need({'v15-c07.html','curriculum.html#v15-c09'}<=d.links,'prerequisite and successor');need(set(author['payload_bindings'])==set(FILES[:3]),'nonself bindings')
    for f,b in author['payload_bindings'].items():need(b['bytes']==len(raw[f]) and b['sha256']==sha256(raw[f]).hexdigest(),'payload bytes')
    x={k:literal(v[1]) for k,v in d.mark.items() if v[0]=='data-input'};seen=set();count=0;rejected=0
    def eq(a,b):
        nonlocal count
        if isinstance(a,(tuple,list)):
            need(isinstance(b,(tuple,list)) and len(a)==len(b),'shape')
            for v,w in zip(a,b):eq(v,w)
        else:need(isfinite(float(a)) and abs(float(a)-float(b))<1e-9,str((a,b)));count+=1
    def result(k,v):eq(v,literal(d.mark[k][1]));seen.add(k)
    def truth(ok,msg):
        nonlocal count
        need(ok,msg);count+=1
    expected={'time':'(12,1,1/2,1)','time-fee':'1/20','reference':'(10,6,16,1/2,2)','reference-grid':'(0,8,10,12,20)','social':'(10,1,3/4)','belief':'(1/2,3/4,1/4,20,0)','factorial':'(10,2,3,-1)','replication':'(2,4/5,1,1)','multiplicity':'(4,1/20)'};need(set(x)==set(expected),'primitive groups')
    for k,v in expected.items():eq(x[k],literal(v))
    E,R,beta,delta=x['time'];actual,plan,_=saving(E,R,beta,delta);result('time-saving',(actual,plan));Vactual,Uactual=dated(E,R,beta,delta,actual);Vplan,Uplan=dated(E,R,beta,delta,plan);wtp=Vplan-Vactual;result('time-willingness',wtp);result('time-later-change',Uplan-Uactual);result('e1-saving',tuple(saving(E,R,beta,delta,L)[2] for L in (2,6,9)));result('e2-net',wtp-float(x['time-fee']));truth(wtp>x['time-fee'] and x['time-fee']<=1,'funded voluntary purchase')
    for b,delta0,return0 in product((F(1,3),F(1,2),1),(F(1,2),1),(F(1,2),2)):
        a,pl,_=saving(E,return0,b,delta0);Va,Ua=dated(E,return0,b,delta0,a);Vp,Up=dated(E,return0,b,delta0,pl)
        for j in (1,2,4,6,8,10,11):
            V,U=dated(E,return0,b,delta0,j);truth(V<=Vp+1e-12 and U<=Ua+1e-12,'global saving witness')
        eq((E-a)+a,E);truth(Vp>=Va-1e-12 and Ua>=Up-1e-12,'temporal rankings')
    safe,low,high,p,lam=x['reference'];gap=lambda r:p*refvalue(high,r,lam)+(1-p)*refvalue(low,r,lam)-refvalue(safe,r,lam);result('reference-values',tuple(gap(r) for r in x['reference-grid']));result('reference-log-gap',float(p)*log(high)+float(1-p)*log(low)-log(safe));threshold=lam*(safe-low)/((high-safe)+lam*(safe-low));result('e4-threshold',threshold)
    for r in range(-5,26):
        piece=1 if r<=6 else 4-F(r,2) if r<=10 else -6+F(r,2) if r<=16 else 2;eq(gap(r),piece);truth((gap(r)<0)==(8<r<12),'full reference rejection set')
    for pp in (0,F(1,2),threshold,F(3,4),1):
        value=pp*refvalue(high,safe,lam)+(1-pp)*refvalue(low,safe,lam);truth((value>0)==(pp>threshold) and (value==0)==(pp==threshold),'probability threshold')
    budget,alpha,gamma=x['social'];lo,hi=gifts(budget,alpha,gamma);eq(lo,hi);tstar=budget*alpha/(1+2*alpha);result('social-results',(hi,social(budget-hi,hi,alpha,gamma),social(budget,0,alpha,gamma),tstar,budget-tstar));accepted=[t for t in range(int(budget)+1) if social(t,budget-t,alpha,gamma)>0];result('e6-grid',min(accepted))
    for gamma0 in (F(1,4),F(1,2),F(3,4)):
        a,b=gifts(budget,1,gamma0);best=social(budget-a,a,1,gamma0)
        for j in range(21):
            t=F(j,2);U=social(budget-t,t,1,gamma0);truth(U<=best,'global social choice');truth((U==best)==(a<=t<=b),'complete dictator argmax')
    for j in range(31):
        t=F(j,3);U=social(t,budget-t,alpha,gamma);truth((U>=0)==(t>=tstar),'ultimatum full acceptance');truth((10-t+6*log(1+t))<=(5+6*log(6))+1e-12,'altruistic alternative optimum')
    for t in (F(7,2),4,5,9):
        improved=(t+tstar)/2;truth(improved>tstar and budget-improved>budget-t,'unattained continuous optimum')
    prior,lh,ll,H,L=x['belief'];p=posterior(prior,lh,ll);s1=score(p,1);s0=score(p,0);ES=p*s1+(1-p)*s0;result('belief-scores',(p,s1,s0,ES));cash=cash_report(p);result('belief-cash-report',cash);result('belief-payment',H*ES+L*(1-ES));result('e7-score-gain',ES-(p*score(F(1,2),1)+(1-p)*score(F(1,2),0)));weighted=2*p/(2*p+1-p);result('e8-distorted',weighted)
    for p0 in (0,F(1,4),F(1,2),F(3,4),1):
        qcash=cash_report(p0);ucash=float(p0)*sqrt(float(score(qcash,1)))+float(1-p0)*sqrt(float(score(qcash,0)))
        for j in range(21):
            q=F(j,20);es=p0*score(q,1)+(1-p0)*score(q,0);eq(es,1-p0*(1-p0)-(q-p0)**2);truth(es<=1-p0*(1-p0),'truthful score optimum');utility=float(p0)*sqrt(score(q,1))+float(1-p0)*sqrt(score(q,0));truth(ucash>=utility-1e-12,'cash global witness');eq(float(L)+(float(H)-float(L))*float(es),float(H)*float(es)+float(L)*float(1-es))
    for q in (0,F(1,4),F(1,2),F(3,4),weighted,1):truth(2*p*score(q,1)+(1-p)*score(q,0)<=2*p*score(weighted,1)+(1-p)*score(weighted,0),'state-dependent optimum')
    base0,tau,eta,psi=x['factorial'];Y=lambda z,m:base0+tau*z+eta*m+psi*z*m;cells=tuple(Y(z,m) for m in (0,1) for z in (0,1));result('factorial-cells',cells);neutral=Y(1,0)-Y(0,0);emphasis=Y(1,1)-Y(0,1);result('factorial-effects',(neutral,emphasis,(neutral+emphasis)/2,emphasis-neutral))
    for z,m in product((0,1),repeat=2):eq(sum(F(1,4)*int((a,b)==(z,m))*Y(a,b)/F(1,4) for a,b in product((0,1),repeat=2)),Y(z,m))
    est1,est2,se1,se2=x['replication'];variance1=se1*se1;variance2=se2*se2;precision=1/variance1+1/variance2;pooled=(est1/variance1+est2/variance2)/precision;result('replication-statistics',((est1-est2)/sqrt(variance1+variance2),pooled,1/sqrt(precision)));n,level=x['multiplicity'];need(n.denominator==1 and n>0,'positive count');n=int(n);result('multiplicity-error',1-(1-level)**n);eq(n*(level/n),level);truth(1-(1-level/n)**n<=level,'independent Bonferroni witness');result('e9-transport',(F(1,4)*4+F(3,4)*0,F(3,4)*4+F(1,4)*0))
    for fn in (lambda:num(True),lambda:num(float('nan')),lambda:saving(0,1,1,1),lambda:saving(12,0,1,1),lambda:saving(12,1,0,1),lambda:saving(12,1,1,0),lambda:saving(12,1,1,1,12),lambda:dated(12,1,1,1,0),lambda:refvalue(10,10,F(1,2)),lambda:social(1,2,0,1),lambda:social(1,2,F(1,4),F(1,2)),lambda:gifts(0,1,F(1,2)),lambda:posterior(0,1,0),lambda:posterior(2,1,0),lambda:score(F(-1,2),0),lambda:score(F(1,2),True),lambda:cash_report(2),lambda:literal('1+2'),lambda:record('{"x":1,"x":2}'),lambda:record('{"x":Infinity}')):
        try:fn()
        except (ValueError,TypeError,ZeroDivisionError):rejected+=1
        else:raise ValueError('invalid input accepted')
    need(seen=={k for k,v in d.mark.items() if v[0]=='data-result'},'all visible results');need(raw=={f:(base/f).read_bytes() for f in FILES},'runtime unchanged');result=dict(chapter='v15-c08',status='passed',worked_cases=5,solutions=10,comparisons=count,domain_rejections=rejected,input_groups=len(x),result_groups=len(seen),runtime_files=4);json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
