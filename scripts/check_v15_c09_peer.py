"""Independent environmental chapter reconstruction, no author-code execution."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import log,isfinite
import ast,json
FILES=('content/chapters/v15-c09.html','scripts/check_v15_c09.py','content/reviews/v15-c09-sources.json','content/reviews/v15-c09-author.json','scripts/check_v15_c09_peer.py','content/reviews/v15-c09-peer.json')
def need(v,msg):
    if not v:raise ValueError(msg)
def num(v):
    need(type(v)in(int,float,F)and isfinite(float(v)),'finite scalar');return F(str(v))
def abatement(b,k,d):
    b=tuple(map(num,b));k=tuple(map(num,k));d=num(d);need(len(b)==len(k)>0 and min(b)>=0 and min(k)>0 and d>0,'abatement domain');solutions=[]
    for state in product((-1,0,1),repeat=len(b)):
        fixed=sum(bi for bi,si in zip(b,state)if si==1);inv=sum(1/ki for ki,si in zip(k,state)if si==0);lam=d*(sum(b)-fixed)/(1+d*inv);a=tuple(0 if si==-1 else bi if si==1 else lam/ki for bi,ki,si in zip(b,k,state));grad=tuple(ki*ai-lam for ki,ai in zip(k,a))
        if all(0<=ai<=bi and (gi>=0 if si==-1 else gi<=0 if si==1 else gi==0)for ai,bi,gi,si in zip(a,b,grad,state)):solutions.append((a,lam))
    need(solutions,'KKT solution');a,lam=solutions[0];E=sum(b)-sum(a);cost=sum(ki*ai*ai/2 for ki,ai in zip(k,a));damage=d*E*E/2;return a,E,lam,cost,damage

def tightcap(b1,b2,k1,k2,cap):
    b1,b2,k1,k2,cap=map(num,(b1,b2,k1,k2,cap));need(min(b1,b2)>=0 and min(k1,k2)>0 and 0<=cap<=b1+b2,'cap domain');total=b1+b2-cap;lo=max(0,total-b2);hi=min(b1,total);a1=min(hi,max(lo,k2*total/(k1+k2)));a2=total-a1;price=k2*a2 if 0<a2<b2 else k1*a1;return a1,a2,price,k1*a1*a1/2+k2*a2*a2/2

def uncertainty(B,c,k,d,shocks,weights):
    B,c,k,d=map(num,(B,c,k,d));shocks=tuple(map(num,shocks));weights=tuple(map(num,weights));need(B>0 and min(k,d)>0 and len(shocks)==len(weights)>0 and min(weights)>0 and sum(weights)==1 and sum(s*p for s,p in zip(shocks,weights))==0 and min(c+s for s in shocks)>=0,'uncertainty domain');bar=(d*B-c)/(k+d);tax=d*(B-bar);rows=[]
    for shock in shocks:
        full=(d*B-c-shock)/(k+d);price=(tax-c-shock)/k;need(0<min(bar,full,price)and max(bar,full,price)<B,'interior instrument domain')
        def loss(a):return(c+shock)*a+k*a*a/2+d*(B-a)**2/2
        rows.append((full,price,loss(full),loss(bar),loss(price)))
    means=tuple(sum(p*row[j]for p,row in zip(weights,rows))for j in (2,3,4));return bar,tax,rows,means,(means[1]-means[0],means[2]-means[0])

def protection(C0,C1,beta,p,k,b):
    C0,C1,beta,p,k,b=map(num,(C0,C1,beta,p,k,b));need(C0>k>0 and C1>0 and beta>0 and 0<p<=1 and b>0,'positive project consumption');x=min(1,max(0,(beta*p*b*C0-k*C1)/(k*b*(1+beta*p))));delta=lambda t:log(float((C0-k*t)/C0))+float(beta*p)*log(float((C1+b*t)/C1));return x,C0-k*x,C1+b*x,delta(1),delta(x)

def extraction(S,beta,c,a0,a1,tax=0):
    S,beta,c,a0,a1,tax=map(num,(S,beta,c,a0,a1,tax));need(S>=0 and beta>0 and c>=0 and tax>=0 and min(a0,a1)>c+tax,'extraction domain');A=a0-c-tax;B=a1-c-tax
    if S==0:q0=q1=F(0);lam=max(A,beta*B)
    elif A+B<=S:q0,q1=A,B;lam=F(0)
    else:q0=min(S,max(0,(A-beta*B+beta*S)/(1+beta)));q1=S-q0;lam=A-q0 if q0>0 else beta*(B-q1)
    return q0,q1,a0-q0,a1-q1,lam,S-q0-q1

def energy(load,a1,a2,prob,c,h):
    load,a1,a2,prob,c,h=map(num,(load,a1,a2,prob,c,h));need(load>0 and a1>a2>0 and 0<prob<1 and min(c,h)>0,'energy domain');corners=(0,load/a1,load/a2)
    def thermal(K):return prob*max(load-a1*K,0)+(1-prob)*max(load-a2*K,0)
    values=tuple(c*K+h*thermal(K)for K in corners);best=min(values);opt=[K for K,J in zip(corners,values)if J==best];return(min(opt),max(opt)),best,thermal
class Read(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.cases=[];self.prompts=[];self.solutions=[];self.markers={};self.stack=[];self.sources={}
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if 'worked'in a.get('class','').split():self.cases.append(a['id'])
        if t=='li'and any(tag=='ol'and 'exercises'in d.get('class','').split()for tag,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for'in a:
            need(any(tag=='details'and 'solutions'in d.get('class','').split()for tag,d in self.stack),'disclosed solution');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for k in ('data-input','data-result'):
            if k in a:need(a[k]not in self.markers,'unique markers');self.markers[a[k]]=''
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_endtag(self,t):need(self.stack and self.stack.pop()[0]==t,'balanced HTML')
    def handle_data(self,s):
        for _,a in self.stack:
            for k in ('data-input','data-result'):
                if k in a:self.markers[a[k]]+=s

def parse(s):
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x)for x in n.elts)
        if isinstance(n,ast.Constant)and type(n.value)in(int,float):return num(n.value)
        if isinstance(n,ast.UnaryOp)and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp)and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('literal syntax')
    return walk(ast.parse(s.split('=')[-1].strip().replace('−','-'),mode='eval').body)

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];r=Read();r.feed((root/FILES[0]).read_text());r.close();need(not r.stack and len(r.ids)==len(set(r.ids)),'structure');need(len(r.cases)==5 and len(r.prompts)==10 and r.prompts==r.solutions,'five cases ten solutions');sources=json.loads((root/FILES[2]).read_text());need(r.sources=={s['id']:s['url']for s in sources['sources']},'citations');review=json.loads((root/FILES[5]).read_text());need(set(review['payload_bindings'])==set(FILES[:5]),'five nonself bindings')
    for path,b in review['payload_bindings'].items():
        raw=(root/path).read_bytes();need(len(raw)==b['bytes']and sha256(raw).hexdigest()==b['sha256'],'peer freeze')
    author=json.loads((root/FILES[3]).read_text());need(len(author['payload_bindings'])==3 and {s['path']for s in author['payload_bindings']}==set(FILES[:3]),'author binding set')
    for b in author['payload_bindings']:
        raw=(root/b['path']).read_bytes();need(len(raw)==b['bytes']and sha256(raw).hexdigest()==b['sha256'],'author freeze')
    count=0
    def eq(a,b):
        nonlocal count
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list))and len(a)==len(b),'shape')
            for x,y in zip(a,b):eq(x,y)
        else:need(abs(float(a)-float(b))<3e-10*max(1,abs(float(b))),'mismatch '+str((a,b)));count+=1
    def truth(ok,msg):
        nonlocal count
        need(ok,msg);count+=1
    inp={'abatement':(6,6,1,2,F(1,2),60),'uncertainty':(10,2,2,1,-1,1,F(1,2)),'protection':(100,50,150,F(9,10),F(1,2),9,20),'resource':(8,F(4,5),2,12,14),'energy':(10,1,F(1,2),F(1,2),4,5,2)}
    for k,v in inp.items():eq(parse(r.markers[k]),v)
    b1,b2,k1,k2,d,end=parse(r.markers['abatement']);aa,E,tax,cost,damage=abatement((b1,b2),(k1,k2),d);taxes=tuple(tax*(bi-ai)for bi,ai in zip((b1,b2),aa));receipt=sum(taxes);costs=tuple(ki*ai*ai/2 for ki,ai in zip((k1,k2),aa));utilities=tuple(end-ci-ti+receipt/2-damage/2 for ci,ti in zip(costs,taxes));B,c,k,dd,slo,shi,p=parse(r.markers['uncertainty']);unc=uncertainty(B,c,k,dd,(slo,shi),(p,1-p));steep=uncertainty(B,c,k,4,(slo,shi),(p,1-p));C0,Cbad,Cgood,beta,prob,price,benefit=parse(r.markers['protection']);pa=protection(C0,Cbad,beta,prob,price,benefit);pb=protection(C0,Cgood,beta,1-prob,price,benefit);mb=beta*C0/Cbad;mg=beta*C0/Cgood;S,disc,unit,A0,A1=parse(r.markers['resource']);res=extraction(S,disc,unit,A0,A1);q0,q1,p0,p1,lam,unused=res;CS=q0*q0/2+disc*q1*q1/2;rent=(p0-unit)*q0+disc*(p1-unit)*q1;load,av1,av2,pe,capital,thermal,dam=parse(r.markers['energy']);priv=energy(load,av1,av2,pe,capital,thermal);soc=energy(load,av1,av2,pe,capital,thermal+dam);K=soc[0][0];g=soc[2](K);bill=capital*K+(thermal+dam)*g;taxbill=dam*g
    tight=tightcap(b1,b2,k1,k2,2);unreb=(end-costs[0]-taxes[0]-damage/2,end-costs[1]-taxes[1]+receipt-damage/2);nopolicy=end-d*(b1+b2)**2/4
    mean_d=F(2);abar=(mean_d*B-c)/(k+mean_d);ta=mean_d*(B-abar)
    def L(a,d):return c*a+k*a*a/2+d*(B-a)**2/2
    fulls=tuple((dx*B-c)/(k+dx)for dx in (1,3));common=(L(abar,1)+L(abar,3))/2;fullmean=(L(fulls[0],1)+L(fulls[1],3))/2;newA=protection(C0,Cbad,beta,prob,15,benefit);newB=protection(C0,Cgood,beta,1-prob,15,benefit);gross=F(101,100)**3;small=extraction(F(1,5),disc,unit,A0,A1);large=extraction(25,disc,unit,A0,A1);taxed=extraction(S,disc,unit,A0,A1,1);choices=tuple((energy(load,av1,av2,pe,cc,thermal)[0],energy(load,av1,av2,pe,cc,thermal+dam)[0])for cc in (3,1,F(7,4)))
    outputs={'planner':(*aa,E,tax),'planner-loss':(cost,damage,cost+damage,d*(b1+b2)**2/2-cost-damage),'distribution':utilities,'regrets':unc[4],'expected-losses':unc[3],'shadow':(mb,mg,prob*mb*benefit,(1-prob)*mg*benefit,prob*mb+(1-prob)*mg),'utility-gains':(pa[3],pb[3]),'extraction':res[:5],'resource-welfare':(CS,rent,CS+rent),'capacity':(priv[0][0],K,(thermal+dam)*load,soc[1],(thermal+dam)*load-soc[1]),'energy-accounts':(taxbill,bill,bill-taxbill,dam*g),'e1':(*tight,d*F(2)**2/2,tight[2]*2),'e2':(*unreb,nopolicy-unreb[0]),'e3':(*steep[:2],*steep[4]),'e4':(abar,ta,common,common-fullmean),'e5':(newA[0],newB[0],newA[1],newA[2]),'e6':(gross,100/gross**30),'e7':(small[0],small[1],small[4],large[0],large[1],large[5]),'e8':(*taxed[:4],taxed[2]-unit-1,taxed[3]-unit-1,taxed[0]+disc*taxed[1]),'e9':(choices[0][0][0],choices[0][1][0],choices[1][0][0],choices[1][1][0],choices[2][0][0],*choices[2][1]),'e10':(4*F(9,10)+4*F(1,2)*F(9,10)**2,4*F(9,10)+4*F(9,10)**2)}
    for key,value in outputs.items():eq(parse(r.markers[key]),value)
    need(set(r.markers)==set(inp)|set(outputs),'all markers independently reconstructed')
    eq(sum(utilities),2*end-cost-damage);eq(sum(unreb),sum(utilities));truth(unreb[0]<nopolicy<unreb[1],'distributional loss despite aggregate gain');eq(tight[3]+1,35)
    for candidate in ((0,0),(6,0),(0,6),(6,6),(2,4)):
        diff=tuple(x-y for x,y in zip(candidate,aa));actual=sum(ki*x*x/2 for ki,x in zip((k1,k2),candidate))+d*(b1+b2-sum(candidate))**2/2-cost-damage;remainder=sum(ki*v*v/2 for ki,v in zip((k1,k2),diff))+d*sum(diff)**2/2;eq(actual,remainder)
    for shock,row in zip((slo,shi),unc[2]):
        af,at,lf,lc,lt=row;eq(lc-lf,(k+dd)*(unc[0]-af)**2/2);eq(lt-lf,(k+dd)*(at-af)**2/2);truth(unc[1]*(B-at)+(c+shock)*at+k*at*at/2<=200,'state cash funding')
    eq(tuple(row[4]for row in unc[2]),(F(877,24),F(1005,24)));eq(fullmean,F(832,15));eq((pa[0],pb[0]),(1,0))
    for target in (Cbad,Cgood):
        for kk in (9,15):
            x,now,later,_,gain=protection(C0,target,beta,prob,kk,benefit)
            for t in (F(0),F(1,4),F(1,2),F(3,4),1):truth(gain>=log(float((C0-kk*t)/C0))+float(beta*prob)*log(float((target+benefit*t)/target))-1e-12,'finite concave project')
    for stock in (0,F(1,5),F(2,5),8,22,25):
        x,y,px,py,la,left=extraction(stock,disc,unit,A0,A1);eq(x+y+left,stock);truth(left>=0 and la>=0,'resource feasibility');eq(la*left,0);truth(A0-unit-x<=la and disc*(A1-unit-y)<=la,'inactive KKT signs')
        if x>0:eq(A0-unit-x,la)
        if y>0:eq(disc*(A1-unit-y),la)
        for u,v in ((0,0),(stock,0),(0,stock)):
            objective=lambda a,b:(A0-unit)*a-a*a/2+disc*((A1-unit)*b-b*b/2);truth(objective(x,y)>=objective(u,v),'concave resource witness')
    eq((p1-unit)/(p0-unit),1/disc);eq(rent,lam*S)
    for x,p in ((q0,p0),(q1,p1)):
        truth(p*x<=100,'consumer resource bill');eq(100-p*x+(p-unit)*x,100-unit*x)
    for x,p in ((taxed[0],taxed[2]),(taxed[1],taxed[3])):eq(100-p*x+x+(p-unit-1)*x,100-unit*x)
    for cc,hh in product((1,F(5,4),F(7,4),3,F(15,4),4,F(21,4)),(thermal,thermal+dam)):
        optim,best,gen=energy(load,av1,av2,pe,cc,hh)
        for trial in (0,5,10,15,20):truth(cc*trial+hh*gen(trial)>=best,'piecewise convex global capacity')
        eq(cc*((optim[0]+optim[1])/2)+hh*gen((optim[0]+optim[1])/2),best)
    for av in (av1,av2):
        renewable=min(load,av*K);gas=max(load-av*K,0);eq(renewable+gas,load);truth((thermal+dam)*gas<=100 and capital*K<=100,'dated energy financing');eq((thermal+dam)*gas-dam*gas,thermal*gas)
    for rho in (F(1,2),1):
        baseline=(0,0,0);pulse=(0,1,rho);eq(sum(F(9,10)**j*4*(pulse[j]-baseline[j])for j in (1,2)),4*F(9,10)+4*rho*F(9,10)**2)
    bad=[lambda:num(True),lambda:num(float('nan')),lambda:abatement((6,6),(0,2),F(1,2)),lambda:abatement((6,6),(1,),F(1,2)),lambda:abatement((-1,6),(1,2),F(1,2)),lambda:tightcap(6,6,1,2,-1),lambda:tightcap(6,6,1,2,13),lambda:uncertainty(10,2,2,1,(-1,1),(F(1,4),F(1,4))),lambda:uncertainty(10,2,2,1,(1,2),(F(1,2),F(1,2))),lambda:uncertainty(10,2,2,1,(-20,20),(F(1,2),F(1,2))),lambda:protection(10,5,1,F(1,2),10,2),lambda:protection(10,0,1,F(1,2),1,2),lambda:extraction(-1,F(4,5),2,12,14),lambda:extraction(8,0,2,12,14),lambda:extraction(8,F(4,5),2,12,14,20),lambda:energy(10,F(1,2),1,F(1,2),4,7),lambda:energy(10,1,0,F(1,2),4,7),lambda:energy(10,1,F(1,2),0,4,7),lambda:energy(10,1,F(1,2),F(1,2),0,7),lambda:parse('1+1')]
    for fn in bad:
        try:fn()
        except(ValueError,TypeError,ZeroDivisionError):pass
        else:raise ValueError('invalid accepted')
    return {'chapter':'v15-c09','role':'separate-peer','status':'pass','comparisons':count,'domain_rejections':len(bad),'worked_cases':5,'solutions':10,'input_groups':len(inp),'output_groups':len(outputs),'runtime_files':6}
if __name__=='__main__':check()
