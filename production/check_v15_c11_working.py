"""Urban equilibrium, housing incidence and mobility: original exact checks."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from math import isfinite
import ast,json,itertools
FILES=('production/v15-c11-working.html','production/check_v15_c11_working.py','production/v15-c11-sources-working.json','production/v15-c11-author-review-working.json')
def need(x,m):
    if not x:raise ValueError(m)
def num(x):
    need(type(x)in(int,float,F)and isfinite(float(x)),'finite nonboolean');return F(str(x))
def linear(N,w,t,r):
    N,w,t,r=map(num,(N,w,t,r));need(N>0 and w>0 and t>0 and r>=0 and w>=r+t*N,'line domain');u=w-r-t*N;comm=t*N*N/2;rent=r*N+comm;return u,comm,rent,N*u,comm

def cities(wA=20,wB=16,N=10,cap=None):
    wA,wB,N=map(num,(wA,wB,N));need(wA>0 and wB>0 and N>0,'city primitives');n=(wA-wB+N)/2;need(0<n<N,'two active cities')
    if cap is not None:
        cap=num(cap);need(0<cap<=N,'cap domain');n=min(n,cap)
    other=N-n;rb=2+other;u=wB-rb;ra=wA-u;need(u>=0,'worker consumption');output=wA*n+wB*other;cost=2*N+(n*n+other*other)/2;owners=ra*n+rb*other-cost;return n,other,ra,rb,u,output,cost,output-cost,N*u,owners

def sorting(w,r,h,l,delta):
    w,r,h,l,delta=map(num,(w,r,h,l,delta));need(w>=r+delta and r>=0 and h>l>=0 and l<=delta<=h,'sorting domain');return l,h,r+delta,w-r-delta+h,w-r,2*r+delta,2*w+h-2*r

def gini(y):
    y=tuple(map(num,y));need(len(y)>0 and min(y)>=0 and sum(y)>0,'income domain');return sum(abs(a-z)for i,a in enumerate(y)for z in y[i+1:])/(len(y)*sum(y))

def mobility(pc,pa,pn,yc,ya,yn,gc,ga,gn,direct=0):
    pc,pa,pn,yc,ya,yn,gc,ga,gn,direct=map(num,(pc,pa,pn,yc,ya,yn,gc,ga,gn,direct));need(pc>0 and min(pa,pn)>=0 and pc+pa+pn==1,'population domain');control=pc*yc+pa*(ya+ga)+pn*yn;offered=pc*(yc+gc)+pa*(ya+ga)+pn*yn+direct;itt=offered-control;ate=pc*gc+pa*ga+pn*gn;return control,offered,itt,pc,itt/pc,ate

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
    root=Path(root)if root else Path(__file__).resolve().parents[1];p=Read();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and len(p.ids)==len(set(p.ids)),'HTML/IDs');need(len(p.cases)==5 and len(p.prompts)==10 and p.prompts==p.solutions,'complete5cases10solutions');s=json.loads((root/FILES[2]).read_text());need(p.sources=={x['id']:x['url']for x in s['sources']},'source URLs');r=json.loads((root/FILES[3]).read_text());need({x['path']for x in r['payload_bindings']}==set(FILES[:3]),'three nonself bindings')
    for x in r['payload_bindings']:
        f=root/x['path'];need(f.stat().st_size==x['bytes']and sha256(f.read_bytes()).hexdigest()==x['sha256'],'freeze')
    n=0
    def eq(a,b):
        nonlocal n
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list))and len(a)==len(b),'shape')
            for x,y in zip(a,b):eq(x,y)
        else:n+=1;need(a==b,'exact numeric '+str((a,b)))
    inputs={'line':(4,20,2,1),'cities':(10,20,16,2,1),'sorting':(10,2,4,1,2),'incomes':(2,4,8,10),'mobility':(F(2,5),F(1,5),F(2,5),20,30,10,6,4,2)}
    for k,v in inputs.items():eq(parse(p.markers[k]),v)
    base=linear(*inputs['line']);improve=linear(4,20,1,1);city=cities();cap=cities(cap=6);quarter=linear(4,20,F(3,2),1);rise=cities(22);cap5=cities(cap=5);money=mobility(*inputs['mobility']);direct=mobility(*inputs['mobility'],direct=1);y=tuple(map(F,inputs['incomes']));denom=len(y)*sum(y)
    within0=abs(y[0]-y[1])+abs(y[2]-y[3]);within1=abs(y[0]-y[3])+abs(y[1]-y[2]);allpairs=gini(y)*denom
    out={'line-base':base,'line-improved':(*improve[:3],improve[3]-base[3],improve[2]-base[2],base[1]-improve[1]),'cities-base':city[:8],'cities-cap':(*cap[:5],cap[-1],cap[7]),'sorting-result':sorting(*inputs['sorting']),'gini-results':(gini(y),gini((3,3,9,9)),gini((6,6,6,6)),within0/denom,(allpairs-within0)/denom,within1/denom,(allpairs-within1)/denom),'mobility-result':money,'e1':(*quarter[:3],80-quarter[1]-4,quarter[3]-base[3],quarter[2]-base[2]),'e2':(6,30,24),'e3':(*rise[:5],rise[8],rise[9],rise[7]),'e4':(cap5[2],cap5[3],cap5[4],cap5[-1],cap5[7],cap[7]-cap5[7],2*(7-5)),'e5':sorting(10,2,6,1,3)[:2]+sorting(10,2,6,1,3)[3:5],'e6':(0,F(1,2),1,F(-1,2),F(1,2)),'e7':(gini((4,4,8,8)),gini(tuple(2*x for x in y))),'e8':(direct[1],direct[2],direct[4],inputs['mobility'][6]),'e9':(30,F(40,3),F(50,3),1,2)}
    for k,v in out.items():eq(parse(p.markers[k]),v)
    need(set(p.markers)==set(inputs)|set(out),'all numerical markers')
    for t in(F(1),F(4,3),F(3,2),F(2)):
        u,comm,rent,cons,diff=linear(4,20,t,1);eq(cons+rent+comm,80);eq(rent-diff,4)
        for x in(F(0),F(1),F(3),F(4)):eq(20-(1+t*(4-x))-t*x,u)
        N=8/t;u,c,r,co,di=linear(N,20,t,1);eq(u,11);eq(di,32/t);eq(r,8/t+32/t)
    for w in(20,22):
        free=cities(w);star=free[0]
        for k in(F(1),F(5),F(6),F(7),F(8),F(10)):
            nA,nB,ra,rb,u,Q,C,W,workers,owners=cities(w,cap=k);eq(nA+nB,10);eq(w-ra,16-rb);eq(workers+owners,W);eq(ra*nA+rb*nB,C+owners);eq(free[7]-W,(nA-star)**2)
            if k<star:need(ra>=2+nA,'scarcity price');n+=1
            for candidate in(F(0),min(k,F(3)),min(k,F(5)),min(k,F(7)),min(k,F(9)),k):
                objective=w*candidate+16*(10-candidate)-20-(candidate**2+(10-candidate)**2)/2;need(W>=objective,'global cap allocation');n+=1
    for delta in(F(1),F(2),F(3),F(4)):
        lo,hi,ra,uh,ul,receipts,W=sorting(10,2,4,1,delta);need(uh>=8 and ul>=10-ra+1,'sorting individual choice');eq(uh+ul+receipts-4,W);n+=1
    # Amenity-change incidence under both supported selections; real cost counted once.
    original=sorting(10,2,4,1,2)
    for newpremium in(F(2),F(3)):
        changed=sorting(10,2,5,2,newpremium);hg=changed[3]-original[3];lg=changed[4]-original[4];owner=changed[5]-original[5]-F(1,2);eq(hg+lg+owner,F(1,2))
    for perm in itertools.permutations(y):eq(gini(perm),gini(y))
    for scale in(F(1,2),F(2),F(5)):eq(gini(tuple(scale*x for x in y)),gini(y))
    # Enumerate type x randomized offer instead of relying on Wald algebra.
    pc,pa,pn,yc,ya,yn,gc,ga,gn=inputs['mobility'];move_mass=move_total=stay_mass=stay_total=F(0)
    for mass,y0,gain,kind in((pc,yc,gc,'c'),(pa,ya,ga,'a'),(pn,yn,gn,'n')):
        for z in(0,1):
            d=int(kind=='a' or(kind=='c'and z==1));prob=mass/2;outcome=y0+gain*d
            if d:move_mass+=prob;move_total+=prob*outcome
            else:stay_mass+=prob;stay_total+=prob*outcome
    eq((move_mass,move_total,stay_mass,stay_total),(F(2,5),12,F(3,5),8));eq(move_total/move_mass-stay_total/stay_mass,F(50,3));eq(money[2],pc*gc);eq(direct[2],pc*gc+1)
    for age,gain in((8,8),(14,2)):eq(18-age-2,gain)
    invalid=[lambda:num(True),lambda:num(float('nan')),lambda:linear(0,20,2,1),lambda:linear(4,20,0,1),lambda:linear(4,2,2,1),lambda:cities(N=0),lambda:cities(cap=0),lambda:cities(cap=11),lambda:cities(100),lambda:sorting(10,2,4,1,0),lambda:sorting(10,2,4,1,5),lambda:sorting(10,2,1,4,2),lambda:gini(()),lambda:gini((0,0)),lambda:gini((-1,2)),lambda:mobility(0,F(1,2),F(1,2),20,30,10,6,4,2),lambda:mobility(F(1,2),F(1,2),F(1,2),20,30,10,6,4,2),lambda:parse('bool(1)')]
    for fn in invalid:
        try:fn()
        except(ValueError,ZeroDivisionError):pass
        else:raise ValueError('malformed accepted')
    return {'chapter':'v15-c11','status':'passed','comparisons':n,'domain_rejections':len(invalid),'worked_cases':5,'solved_exercises':10,'primitive_markers':len(inputs),'result_markers':len(out),'runtime_files':4,'scope':'Exact equilibrium/funding, cap global witnesses, sorting support, individual/aggregated Gini and type-assignment enumeration; full proofs separately reviewed.'}
if __name__=='__main__':check()
