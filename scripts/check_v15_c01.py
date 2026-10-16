"""Original public-economics cases: quiet four-file portable verification."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from math import log,isfinite,sqrt
import ast,json
FILES=('content/chapters/v15-c01.html','scripts/check_v15_c01.py','content/reviews/v15-c01-sources.json','content/reviews/v15-c01-author.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite scalar');return F(str(x))
def incidence(a,d,s,t):
    a,d,s,t=map(num,(a,d,s,t));need(a>0 and d>0 and s>0 and 0<=t<=a/d,'incidence domain')
    pp=(a-d*t)/(d+s);pc=pp+t;q=s*pp;q0=s*a/(d+s)
    return pp,pc,q,t*q,t*(q0-q)/2

def linear(a,mu,g):
    a,mu,g=[tuple(map(num,x)) for x in (a,mu,g)];need(len(a)==len(mu)==len(g)>0,'linear shape');need(min(a)>0 and min(mu)>0 and min(g)>=0 and sum(mu)==1 and sum(x*y for x,y in zip(mu,g))==1,'linear weights')
    A=sum(m*x*x for m,x in zip(mu,a));H=sum(m*w*x*x for m,w,x in zip(mu,g,a));t=(A-H)/(2*A-H) if H<A else F(0);B=t*(1-t)*A;W=H*(1-t)**2/2+B
    return t,B,W,A,H

def menu(a,z):
    a,z=[tuple(map(num,x)) for x in (a,z)];need(len(a)==len(z)==2 and 0<a[0]<a[1] and 0<=z[0]<=z[1],'menu domain')
    dz=z[1]**2-z[0]**2;lo=dz/(2*a[1]**2);hi=dz/(2*a[0]**2);c0=(sum(z)-lo)/2;c1=c0+lo;need(c0>=0,'nonnegative low consumption');u0=c0-z[0]**2/(2*a[0]**2);u1=c1-z[1]**2/(2*a[1]**2)
    return lo,hi,c0,c1,u0,u1

def public(a1,a2,cost):
    a1,a2,cost=map(num,(a1,a2,cost));need(a1>a2>0 and cost>0,'public strict values/cost');gn=max(F(0),a1/cost-1);go=max(F(0),(a1+a2)/cost-1);return gn,go,cost*go

def insurance(w,L,p0,p1,r):
    w,L,p0,p1,r=map(num,(w,L,p0,p1,r));need(w>L>0 and 0<p1<p0<1 and 1<=r<=w/(w-L),'insurance domain')
    b=min(L,(w-r*(w-L))/(p1+r*(1-p1)));prem=p1*b;good=w-prem;bad=w-L-prem+b;k=float(p0-p1)*log(float(r));uh=float(1-p1)*log(float(good))+float(p1)*log(float(bad))-k;ul=log(float(w-p0*L));return b,prem,good,bad,uh-ul

def evidence(tp,ta,cp,ca,t0,t1):
    tp,ta,cp,ca,t0,t1=map(num,(tp,ta,cp,ca,t0,t1));cf=tp+ca-cp;need(min(tp,ta,cp,ca,cf)>0 and 0<=t0<t1<1,'evidence domain');effect=ta-cf;elas=log(float(ta/cf))/log(float((1-t1)/(1-t0)));return cf,effect,elas,t1*ta-t0*cf

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
    s=s.split('=')[-1].strip()
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x)for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value)in(int,float):return num(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric display syntax')
    return walk(ast.parse(s,mode='eval').body)

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];p=Read();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and len(set(p.ids))==len(p.ids),'HTML/IDs');need(len(p.cases)==6 and len(p.prompts)==12 and p.prompts==p.solutions,'case/solution coverage')
    source=json.loads((root/FILES[2]).read_text());need(p.sources=={x['id']:x['url']for x in source['sources']},'source URLs');review=json.loads((root/FILES[3]).read_text())
    for x in review['payload_bindings']:
        f=root/x['path'];need(f.stat().st_size==x['bytes'] and sha256(f.read_bytes()).hexdigest()==x['sha256'],'payload freeze')
    need(set(x['path']for x in review['payload_bindings'])==set(FILES[:3]),'three nonself bindings')
    count=0
    def eq(x,y):
        nonlocal count
        if isinstance(y,(tuple,list)):
            need(isinstance(x,(tuple,list)) and len(x)==len(y),'shape')
            for a,b in zip(x,y):eq(a,b)
        else:need(abs(float(x)-float(y))<=2e-10*max(1,abs(float(y))),'numeric mismatch '+str((x,y)));count+=1
    inputs={'incidence':(120,2,3,10),'linear-tax':(F(1,2),F(1,2),1,3,F(3,2),F(1,2)),'menu-abilities':(1,2),'menu-earnings':(1,2),'public-values':(2,1,1),'insurance':(10,6,F(1,2),F(1,4)),'tax-evidence':(100,90,80,84,F(1,5),F(3,10))}
    for k,v in inputs.items():eq(parse(p.markers[k]),v)
    inc=incidence(*parse(p.markers['incidence']));ml,mh,al,ah,gl,gh=parse(p.markers['linear-tax']);tax=linear((al,ah),(ml,mh),(gl,gh));mn=menu(parse(p.markers['menu-abilities']),parse(p.markers['menu-earnings']));pub=public(*parse(p.markers['public-values']));ins=insurance(*parse(p.markers['insurance']),F(3,2));ev=evidence(*parse(p.markers['tax-evidence']))
    outputs={'incidence-result':inc[:4],'incidence-dwl':inc[4],'linear-optimum':tax[:2],'linear-welfare':tax[2],'menu-consumption':mn[2:4],'public-private':(pub[0],0,pub[0]),'public-optimum':pub[1],'public-gains':(-.7+2*log(1.5),-.3+log(1.5)),'insurance-effort':ins[:4],'insurance-gain':ins[4],'tax-elasticity':ev[2],'tax-revenue-change':ev[3],'e1':incidence(120,2,3,5),'e2':(20,60,F(35,2),65,F(1,2)),'e2-surplus-loss':80*(20-F(35,2))-(20**2-F(35,2)**2),'e3':linear((1,3),(F(1,2),F(1,2)),(F(7,4),F(1,4)))[:3],'e4':menu((1,2),(1,3))[2:],'e5':public(2,1,2),'e6-payments':(F(5,3),F(1,3)),'e6-gains':(-2/3+2*log(1.5),-1/3+log(1.5)),'e7':(F(17,2),7),'e8-effort':insurance(10,6,F(1,2),F(1,4),2)[:4],'e9':(F(3,10)*84-F(1,5)*104,F(3,10)*96-F(1,5)*104),'e11-welfare':F(3,2)*10-F(1,2)*12}
    for k,v in outputs.items():eq(parse(p.markers[k]),v)
    need(set(p.markers)==set(inputs)|set(outputs),'all displays checked')
    # Independent budget, FOC, IC, resource and global comparison witnesses.
    for t in (F(0),F(5),F(10),F(20),F(60)):
        pp,pc,q,R,D=incidence(120,2,3,t);eq(pc-pp,t);eq(120-2*pc,3*pp);eq(q,3*pp);eq(R,t*q)
        CS=(60-pc)*q/2;PS=pp*q/2;eq(2160-CS-PS-R,D)
    for weights in [(F(3,2),F(1,2)),(F(7,4),F(1,4)),(1,1),(F(1,2),F(3,2))]:
        t,B,W,A,H=linear((1,3),(F(1,2),F(1,2)),weights);l=[(1-t)*a for a in (1,3)];c=[(1-t)*a*x+B for a,x in zip((1,3),l)];eq(sum(c)/2,sum(a*x for a,x in zip((1,3),l))/2);eq(W,sum(g*(ci-x*x/2)/2 for g,ci,x in zip(weights,c,l)))
        for j in range(21):
            tj=F(j,20);need(W>=H*(1-tj)**2/2+A*tj*(1-tj),'global linear witness');count+=1
    for z in [(1,2),(1,3)]:
        lo,hi,c0,c1,u0,u1=menu((1,2),z);eq(c0+c1,sum(z));eq(u1,c0-F(z[0])**2/8);need(u0>=c1-F(z[1])**2/2,'low IC');count+=1
    for r in (F(3,2),F(2)):
        b,pr,cg,cb,gain=insurance(10,6,F(1,2),F(1,4),r);eq(cg/cb,r);eq(pr,b/4);eq(F(3,4)*cg+cb/4,F(17,2));eq(F(1,4)*log(float(cg/cb)),F(1,4)*log(float(r)))
    need(ins[4]>0 and insurance(10,6,F(1,2),F(1,4),2)[4]<0,'regime comparison');count+=2
    eq(ev[3],F(1,10)*ev[0]+F(3,10)*ev[1]);eq(ev[0],104)
    invalid=[lambda:incidence(120,0,3,10),lambda:incidence(120,2,-3,10),lambda:incidence(120,2,3,61),lambda:incidence(120,2,3,-1),lambda:incidence(float('nan'),2,3,1),lambda:linear((1,3),(1,1),(1,1)),lambda:linear((1,3),(F(1,2),F(1,2)),(-1,3)),lambda:linear((1,3),(F(1,2),F(1,2)),(1,2)),lambda:menu((2,1),(1,2)),lambda:menu((1,2),(3,1)),lambda:public(1,2,1),lambda:public(2,1,0),lambda:insurance(5,6,F(1,2),F(1,4),2),lambda:insurance(10,6,F(1,2),F(3,4),2),lambda:insurance(10,6,F(1,2),F(1,4),3),lambda:evidence(100,90,80,84,F(3,10),F(1,5)),lambda:evidence(100,-1,80,84,F(1,5),F(3,10)),lambda:parse('bool(1)')]
    for fn in invalid:
        try:fn()
        except (ValueError,ZeroDivisionError):pass
        else:raise ValueError('accepted invalid input')
    out={'chapter':'v15-c01','status':'passed','comparisons':count,'domain_rejections':len(invalid),'worked_cases':6,'solved_exercises':12,'primitive_markers':len(inputs),'result_markers':len(outputs),'runtime_files':4,'scope':'Finite calculations and global witnesses supplement full proofs, instruction and source review.'};json.dumps(out,allow_nan=False);return out
if __name__=='__main__':check()
