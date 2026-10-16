"""Original IO cases: quiet portable four-file author check."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from itertools import product
from math import isfinite
import ast,json
FILES=('production/v15-c03-working.html','production/check_v15_c03_working.py','production/v15-c03-sources-working.json','production/v15-c03-author-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite real scalar');return F(str(x))
def demand(a,g,p):
    a,g=map(num,(a,g));p=tuple(map(num,p));need(a>0 and 0<=g<1 and len(p)==2 and min(p)>=0,'consumer domain')
    raw=tuple((a*(1-g)-p[i]+g*p[1-i])/(1-g*g) for i in range(2))
    if min(raw)>=0:return raw
    q=tuple(max(a-v,0) for v in p)
    if q[0]==0:return (F(0),q[1])
    if q[1]==0:return (q[0],F(0))
    if p[1]>=a-g*q[0]:return(q[0],F(0))
    return(F(0),q[1])
def merger(a,g,c):
    a,g,c=map(num,(a,g,c));need(a>0 and 0<=g<1 and 0<=c<a,'active merger domain');q=(a-c)/(2*(1+g));p=(a+c)/2;cs=(1+g)*q*q;pi=2*(p-c)*q;return(p,p,q,q,cs,pi,cs+pi)
def cournot(a,c,f,n):
    a,c,f=map(num,(a,c,f));need(a>c>=0 and f>=0 and type(n)is int and n>=1,'Cournot domain');q=(a-c)/(n+1);Q=n*q;P=a-Q;op=(P-c)*q;W=(a-c)*Q-Q*Q/2-n*f;return q,Q,P,op,W

def entrycounts(a,c,f,N):
    need(type(N)is int and N>=1,'potential count');a,c,f=map(num,(a,c,f));need(a>c>=0 and f>=0,'entry domain')
    return tuple(n for n in range(N+1) if(n==0 or cournot(a,c,f,n)[3]>=f)and(n==N or cournot(a,c,f,n+1)[3]<=f))
def platform(x,y):
    x,y=map(num,(x,y));need(0<=x<1 and 0<=y<1 and x+y<=1,'platform solved domain');s=x+y;b=2/(4-s*s);a=s*b/2;fa=x*b-a;fb=1+y*a-b;pi=fa*a+fb*b;return a,b,fa,fb,pi

def fixedpoint(x,y,fa,fb):
    x,y,fa,fb=map(num,(x,y,fa,fb));need(0<=x<1 and 0<=y<1,'contraction domain');a=b=0.0
    for _ in range(250):a,b=min(1,max(0,float(x)*b-float(fa))),min(1,max(0,1+float(y)*a-float(fb)))
    return a,b

def critical(m,t):
    m,t=map(num,(m,t));need(m>0 and t>0,'positive margin/increase');return t/(m+t)
class Read(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.cases=[];self.prompts=[];self.solutions=[];self.markers={};self.stack=[];self.sources={}
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if 'worked'in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and any(tag=='ol' and 'exercises'in d.get('class','').split() for tag,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for'in a:
            need(any(tag=='details' and 'solutions'in d.get('class','').split() for tag,d in self.stack),'disclosed solution');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for k in ('data-input','data-result'):
            if k in a:need(a[k] not in self.markers,'duplicate marker');self.markers[a[k]]=''
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_endtag(self,t):need(bool(self.stack) and self.stack.pop()[0]==t,'balanced HTML')
    def handle_data(self,s):
        for _,a in self.stack:
            for k in ('data-input','data-result'):
                if k in a:self.markers[a[k]]+=s

def parse(s):
    s=s.split('=')[-1].strip().replace('−','-')
    if ';'in s:s='['+s.replace(';','],[')+']'
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x)for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value)in(int,float):return num(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric display syntax')
    return walk(ast.parse(s,mode='eval').body)

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];r=Read();r.feed((root/FILES[0]).read_text());r.close();need(not r.stack and len(set(r.ids))==len(r.ids),'HTML/IDs');need(len(r.cases)==5 and len(r.prompts)==10 and r.prompts==r.solutions,'case/solution coverage')
    src=json.loads((root/FILES[2]).read_text());need(r.sources=={x['id']:x['url']for x in src['sources']},'source IDs/URLs');rev=json.loads((root/FILES[3]).read_text());bindings=rev['payload_bindings'];need(len(bindings)==3 and {x['path']for x in bindings}==set(FILES[:3]),'three exact nonself bindings')
    for x in bindings:
        b=(root/x['path']).read_bytes();need(len(b)==x['bytes']and sha256(b).hexdigest()==x['sha256'],'payload freeze')
    count=0
    def eq(x,y):
        nonlocal count
        if isinstance(y,(tuple,list)):
            need(isinstance(x,(tuple,list))and len(x)==len(y),'shape')
            for a,b in zip(x,y):eq(a,b)
        else:need(abs(float(x)-float(y))<=2e-10*max(1,abs(float(y))),'numeric mismatch '+str((x,y)));count+=1
    inputs={'demand':(F(20,3),F(20,3),F(4,3),F(-2,3),F(-2,3),F(4,3),6,F(1,4)),'pricing':(10,F(1,2),4,100,2),'entry':(4,14,2,8),'platform':(F(1,4),F(3,4),1),'test':(6,F(1,10))}
    for k,v in inputs.items():eq(parse(r.markers[k]),v)
    alpha1,alpha2,d11,d12,d21,d22,pbar,s=parse(r.markers['demand']);D=((d11,d12),(d21,d22));atoms=[]
    for z1,z2,u1,u2 in product((-s,s),repeat=4):
        p=(pbar+z1+u1,pbar+z2+u2);u=(u1,u2);q=tuple((alpha1,alpha2)[i]-sum(D[i][j]*p[j]for j in range(2))+u[i]for i in range(2));atoms.append((p,q,(z1,z2),u));need(min(q)>0,'uncensored atoms')
    def cov(k,i,l,j):
        n=len(atoms);m1=sum(t[k][i]for t in atoms)/n;m2=sum(t[l][j]for t in atoms)/n;return sum((t[k][i]-m1)*(t[l][j]-m2)for t in atoms)/n
    vp=cov(0,0,0,0);ols=tuple(tuple(cov(1,i,0,j)/vp for j in range(2))for i in range(2));iv=tuple(tuple(cov(1,i,2,j)/cov(0,j,2,j) for j in range(2))for i in range(2))
    a,g,c,M,ce=parse(r.markers['pricing']);p=(a*(1-g)+c)/(2-g);q=demand(a,g,(p,p));CS=(1+g)*q[0]**2;PI=2*(p-c)*q[0];pre=(p,p,*q);post=merger(a,g,c);eff=merger(a,g,ce)
    N,ae,cc,ff=map(int,parse(r.markers['entry']));W=(0,)+tuple(cournot(ae,cc,ff,n)[4]for n in range(1,N+1));co=cournot(ae,cc,ff,3);co2=cournot(ae,cc,ff,2)
    x,y,res=parse(r.markers['platform']);na,nb,fa,fb,pp=platform(x,y)
    base,t=parse(r.markers['test']);ps=base*(1+t);qs=demand(a,g,(ps,base));qj=demand(a,g,(ps,ps));basepi=(base-c)*q[0];singlepi=(ps-c)*qs[0];jointpi=2*(ps-c)*qj[0];hi=post[0];ph=hi*(1+t);qh=demand(a,g,(ph,ph));hipi=2*(ph-c)*qh[0]
    asymp=((2*(5+4)+g*(5+2))/(4-g*g),(2*(5+2)+g*(5+4))/(4-g*g));asymq=demand(a,g,asymp)
    outs={'covariances':(vp,cov(3,0,0,0),cov(0,0,2,0)),'ols':ols,'iv':iv,'pre':pre,'prew':(CS,PI,CS+PI),'post':post,'efficient':eff,'cournot3':co[:4],'entrycount':entrycounts(ae,cc,ff,N)[0],'entryw':W,'fullplanner':(ae-cc,(ae-cc)**2/2-ff),'entrydecomp':(co[3]-ff,2*(co[3]-co2[3]),(co[1]**2-co2[1]**2)/2,co[4]-co2[4]),'platformopt':(na,nb,fa,fb),'platformcash':(-fa*na,fb*nb,pp),'platformw':(na*na/2,nb*nb/2,na*na/2+nb*nb/2+pp),'single':(*qs,singlepi-basepi),'diversion':(qs[1]-q[1])/(q[0]-qs[0]),'joint':(jointpi,jointpi-PI),'losses':((q[0]-qs[0])/q[0],(q[0]-qj[0])/q[0],critical((base-c)/base,t)),'highbaseline':(hipi,hipi-post[5]),'s1':tuple(tuple(-D[i][j]+(F(3,4)if i==j else 0)for j in range(2))for i in range(2)),'s2':(-d11-F(1,5),-d11+F(1,5)),'s3':merger(a,g,3),'s4':(*asymp,*asymq),'s5counts':entrycounts(ae,cc,9,N),'s5w':(0,)+tuple(cournot(ae,cc,9,n)[4]for n in range(1,N+1)),'s7':platform(y,x),'s8':((0,0),(F(1,2),F(1,2)),(1,1)),'s9':((post[2]-qh[0])/post[2],critical((hi-c)/hi,t))}
    for k,v in outs.items():eq(parse(r.markers[k]),v)
    need(set(r.markers)==set(inputs)|set(outs),'all markers checked')
    # Exhaustive finite moments, plus KKT/corner and analytical difference certificates.
    eq(min(z[1][0]for z in atoms),F(23,12))
    for i,j in product(range(2),repeat=2):eq(cov(0,i,2,j),s*s if i==j else 0);eq(cov(3,i,2,j),0)
    for prices in ((0,0),(0,12),(12,0),(12,12),(2,8),(8,2),(6,6),asymp):
        qty=demand(a,g,prices)
        for i in range(2):
            gradient=a-qty[i]-g*qty[1-i]-prices[i];need(gradient<=0 if qty[i]==0 else gradient==0,'consumer KKT');count+=1
        spend=sum(prices[i]*qty[i]for i in range(2));need(spend<=a*a/(2*(1+g))<M,'wealth slack');count+=1
    for rival,own,cost in ((p,p,c),(asymp[1],asymp[0],4),(asymp[0],asymp[1],2)):
        optimum=(own-cost)*demand(a,g,(own,rival))[0]
        for trial in (0,cost,own,8,20):need((trial-cost)*demand(a,g,(trial,rival))[0]<=optimum,'global price witness');count+=1
    for cost in (2,3,4):
        opt=merger(a,g,cost);oq=opt[2]
        for trial in ((0,0),(1,0),(0,4),(3,2),(oq,oq)):
            h=(trial[0]-oq,trial[1]-oq);actual=(a-cost)*sum(trial)-trial[0]**2-trial[1]**2-2*g*trial[0]*trial[1];eq(opt[5]-actual,h[0]**2+h[1]**2+2*g*h[0]*h[1])
    for n in range(1,N+1):
        qi,Q,P,op,w=cournot(ae,cc,ff,n);eq(qi,(ae-cc-(n-1)*qi)/2);eq(w,Q*Q/2+n*(op-ff))
    eq(fixedpoint(x,y,fa,fb),(na,nb));eq(fixedpoint(x,y,-2,-2),(1,1));eq(fixedpoint(x,y,2,2),(0,0));need(res>=-fa,'prefunded subsidies');count+=1
    for aa,bb in ((0,0),(1,0),(0,1),(1,1),(na,nb)):
        h=aa-na;k=bb-nb;pi=bb-aa*aa-bb*bb+aa*bb;eq(pp-pi,h*h+k*k-h*k)
    for n in (0,F(1,2),1):eq(min(1,max(0,2*n-F(1,2))),n)
    bad=[lambda:num(True),lambda:num(float('nan')),lambda:demand(10,1,(6,6)),lambda:demand(10,-1,(6,6)),lambda:demand(10,g,(-1,6)),lambda:demand(10,g,(6,)),lambda:merger(10,g,10),lambda:merger(10,g,-1),lambda:cournot(2,2,8,3),lambda:cournot(14,2,-1,3),lambda:cournot(14,2,8,0),lambda:cournot(14,2,8,True),lambda:entrycounts(14,2,8,0),lambda:entrycounts(14,2,8,2.5),lambda:platform(1,0),lambda:platform(F(3,4),F(3,4)),lambda:platform(-1,0),lambda:fixedpoint(2,2,0,0),lambda:critical(0,t),lambda:critical(F(1,3),0),lambda:parse('__import__("os")')]
    rejected=0
    for f in bad:
        try:f()
        except(ValueError,TypeError,ZeroDivisionError):rejected+=1
        else:raise ValueError('invalid input accepted')
    return {'chapter':'v15-c03','comparisons':count,'domain_rejections':rejected,'worked_cases':5,'solutions':10,'input_groups':len(inputs),'output_groups':len(outs),'runtime_files':4,'status':'pass'}
if __name__=='__main__':check()
