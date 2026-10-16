"""Independent Form A peer reconstruction; never imports author checker."""
from fractions import Fraction as F
from pathlib import Path
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite,sqrt
import ast,json
FILES=('content/assessments/parts/v15-exam-a.html','scripts/check_v15_exam_a.py','content/reviews/v15-exam-a-sources.json','content/reviews/v15-exam-a-author.json','scripts/check_v15_exam_a_peer.py','content/reviews/v15-exam-a-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):need(type(x)in(int,float,F)and isfinite(float(x)),'finite numeric');return F(str(x))
def labor(w,t):
    w,t=map(num,(w,t));need(w>0 and 0<=t<=1,'labor domain');n=w*(1-t);return n,w*n*t,(1-t)*w*n-n*n/2

def financing(w,c):
    w,c=map(num,(w,c));need(w>0 and 0<=c<=w*w/4,'feasible funding');r=F(str(sqrt(float(1-4*c/(w*w)))));return((1-r)/2,(1+r)/2)

def channel(A,c,z):
    A,c,z=map(num,(A,c,z));need(A>c>=0 and z>=0,'channel domain')
    if z>=A-c:return(F(0),None,None,F(0),F(0),F(0),F(0),F(0))
    q=(A-c-z)/4;v=A-z-2*q;p=A-q;retail=(p-v-z)*q;foreign=(v-c)*q;tariff=z*q;H=q*q/2+retail+tariff;world=A*q-q*q/2-c*q;return q,v,p,retail,foreign,tariff,H,world

def ownership(A,c,alpha):
    A,c,alpha=map(num,(A,c,alpha));need(A>c>=0 and 0<=alpha<=1,'ownership domain');q=min((A-c)/4,(A-c)/(5-4*alpha));return A-c-4*q,q

def credit(wealth,cost,output,tax,pledge):
    wealth,cost,output,tax,pledge=map(num,(wealth,cost,output,tax,pledge));need(min(wealth,cost,output,tax)>=0 and tax<=output and 0<=pledge<=1,'credit domain');loan=max(0,cost-wealth);private=pledge*(output-tax);payment=max(0,loan-private);return loan,private,payment,output-tax-min(loan,private)

def contract(beta,cost,benefit,q,f,b,admin,spill,otherbeta):
    beta,cost,benefit,q,f,b,admin,spill,otherbeta=map(num,(beta,cost,benefit,q,f,b,admin,spill,otherbeta));need(0<beta<=1 and 0<otherbeta<=1 and 0<=q<=1 and min(cost,benefit,f,b,admin,spill)>=0,'contract domain');incentive=beta*benefit-cost+q*(f+b);tax=q*(admin+b)/3;votes=(beta*(benefit-cost+q*b)-tax,otherbeta*spill-tax,-tax);resource=benefit+spill-cost-admin*q;return incentive,tax,votes,resource

def spatial(N,wa,wb,h,c,d,cap=None):
    N,wa,wb,h,c,d=map(num,(N,wa,wb,h,c,d));cap=N if cap is None else num(cap);need(N>0 and min(wa,wb)>0 and min(h,c,d)>0 and 0<=cap<=N,'spatial domain');A=wa-wb+h*N
    def clamp(x,lo,hi):return min(hi,max(lo,x))
    candidates=[(clamp(A/(2*h+d),0,N),F(0)),(clamp(A/(2*h+c),0,min(N,cap)),clamp(A/(2*h+c),0,min(N,cap))),(N,clamp(d*N/(c+d),0,min(N,cap))),(clamp((A+d*cap)/(2*h+d),cap,N),cap)]
    det=(2*h+d)*(c+d)-d*d;n=A*(c+d)/det;k=A*d/det
    if 0<=k<=min(n,cap)and n<=N:candidates.append((n,k))
    def W(n,k):return wa*n+wb*(N-n)-h*(n*n+(N-n)**2)/2-c*k*k/2-d*(n-k)**2/2
    n,k=max(candidates,key=lambda x:W(*x));return n,k,W(n,k),W
class Read(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.solutions=[];self.points=[];self.rubrics=[];self.domains={};self.markers={};self.sources={};self.chapters=set()
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if 'data-domain'in a:self.domains[a['data-domain']]=int(a['data-domain-points'])
        if 'data-chapters'in a:self.chapters.update(a['data-chapters'].split())
        if t=='li'and 'data-points'in a:self.tasks.append(a['id']);self.points.append(int(a['data-points']))
        if 'data-solution-for'in a:
            need(any(t=='details'and 'solutions'in b.get('class','').split()for t,b in self.stack),'disclosed solutions');self.solutions.append(a['data-solution-for'])
        if 'data-rubric-points'in a:self.rubrics.append(tuple(map(int,a['data-rubric-points'].split(','))))
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for k in('data-input','data-result'):
            if k in a:need(a[k]not in self.markers,'unique marker');self.markers[a[k]]=''
        if t not in('br','hr','img','link','meta','input'):self.stack.append((t,a))
    def handle_endtag(self,t):need(self.stack and self.stack.pop()[0]==t,'balanced HTML')
    def handle_data(self,s):
        for t,a in self.stack:
            for k in('data-input','data-result'):
                if k in a:self.markers[a[k]]+=s

def literal(s):
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x)for x in n.elts)
        if isinstance(n,ast.Constant)and type(n.value)in(int,float):return num(n.value)
        if isinstance(n,ast.UnaryOp)and isinstance(n.op,ast.USub):return-walk(n.operand)
        if isinstance(n,ast.BinOp)and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('literal syntax')
    return walk(ast.parse(s.split('=')[-1].strip(),mode='eval').body)

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];before={p:(root/p).read_bytes()for p in FILES};record=json.loads(before[FILES[5]]);need(set(record['payload_bindings'])==set(FILES[:5]),'five nonself bindings')
    for p,b in record['payload_bindings'].items():need(len(before[p])==b['bytes']and sha256(before[p]).hexdigest()==b['sha256'],'peer freeze')
    ar=json.loads(before[FILES[3]]);need(set(ar['payload_bindings'])==set(FILES[:3]),'author nonself paths')
    for p,b in ar['payload_bindings'].items():need(len(before[p])==b['bytes']and sha256(before[p]).hexdigest()==b['sha256'],'author freeze')
    r=Read();r.feed(before[FILES[0]].decode());r.close();need(not r.stack and len(r.ids)==len(set(r.ids)),'structure');need(r.tasks==[f'v15-exam-a-q{i:02}'for i in range(1,21)]and r.solutions==r.tasks,'twenty exact pairs');need(r.points==[5]*20 and len(r.rubrics)==20 and all(sum(p)==5 and min(p)>0 for p in r.rubrics),'additive100');need(len(r.domains)==5 and set(r.domains.values())=={20},'five domains');need(r.chapters=={f'v15-c{i:02}'for i in range(1,13)},'all chapter routes');sources=json.loads(before[FILES[2]]);need(r.sources=={x['id']:x['url']for x in sources['sources']},'source routes')
    count=0
    def eq(a,b):
        nonlocal count
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list))and len(a)==len(b),'shape')
            for x,y in zip(a,b):eq(x,y)
        else:need(abs(float(a)-float(b))<=1e-10,'mismatch '+str((a,b)));count+=1
    def truth(ok,msg):
        nonlocal count
        need(ok,msg);count+=1
    inp={'labor':(4,3,5,2,5),'vertical':(10,2),'grid':(2,2,8,5,6,4,9,5,F(1,2)),'archive':(100,40,12,100,50,8,0,20),'politics':(F(1,4),F(1,2),3,8,4,2,2,6),'spatial':(6,12,10,1,1,1)}
    for key,value in inp.items():eq(literal(r.markers[key]),value)
    w,cost,benefit,training,trained=literal(r.markers['labor']);tl,th=financing(w,cost);nl,rl,vl=labor(w,tl);nh,rh,vh=labor(w,th);n0,_,v0=labor(w,0);nt,rt,vt=labor(trained,tl);private=vt-vl-training;fiscal=rt-rl;trainresource=trained*nt-nt*nt/2-training-(w*nl-nl*nl/2);grant=training-F(1,2)-1
    A,c=literal(r.markers['vertical']);free=channel(A,c,0);zt,qt=ownership(A,c,0);tariff=channel(A,c,zt);qcontract=(A-c)/2;vcontract=A-2*qcontract;fee=qcontract*qcontract
    ng,wealth,banks,treasury,mach,grid,Y,Yno,pledge=literal(r.markers['grid']);loan,capacity,payment,retained=credit(wealth,mach,Y,2,pledge);lowbound,highbound=pledge*Yno,pledge*Y;remaining=treasury-grid-ng*payment+2*ng;entgain=ng*(retained-wealth);treasgain=remaining-treasury
    NT,nT,mT,NC,nC,mC,lower,upper=literal(r.markers['archive']);bounds=((nT*mT+(NT-nT)*lower)/NT,(nT*mT+(NT-nT)*upper)/NT,(nC*mC+(NC-nC)*lower)/NC,(nC*mC+(NC-nC)*upper)/NC)
    ba,bb,C,B,spill,fmax,bmax,admin=literal(r.markers['politics']);gap=C-ba*B;qmin=gap/(fmax+bmax);p14=contract(ba,C,B,F(1,2),fmax,0,admin,spill,bb);p15=contract(ba,C,B,qmin,fmax,bmax,admin,spill,bb)
    N,wa,wb,hs,cs,ds=literal(r.markers['spatial']);ns,ks,Ws,W=spatial(N,wa,wb,hs,cs,ds);base=(wa-wb+hs*N)/(2*hs);W0=W(base,0);tau=ds*(ns-ks);receipt=tau*ns;bill=cs*ks*ks/2;rebate=(receipt-bill)/N;own=hs*(ns*ns+(N-ns)**2)/2;worker=N*(wb-hs*(N-ns)+rebate)-ds*(ns-ks)**2/2;nc,kc,Wc,_=spatial(N,wa,wb,hs,cs,ds,1);tc=ds*(nc-kc);rc=tc*nc;bc=cs*kc*kc/2
    def netgain(theta):return wa*nc+wb*(N-nc)-hs*(nc*nc+(N-nc)**2)/2-bc-theta*(nc-kc)**2/2-1-(wa*base+wb*(N-base)-hs*(base*base+(N-base)**2)/2-theta*base*base/2)
    out={'q01':(tl,nl,th,nh),'q02':(v0,w*nl-nl*nl/2-cost+benefit,w*nh-nh*nh/2-cost+benefit,v0-cost+benefit),'q03':(nt,private,fiscal,trainresource),'q04':(grant,private+grant,fiscal-grant,trainresource),'q05':(free[1],free[0],free[2],free[3],free[4],free[5]),'q06':(zt,qt,tariff[6],tariff[6]-free[6],tariff[7],free[7]-tariff[7]),'q07':(vcontract,fee,qcontract,A-qcontract,qcontract*qcontract/2,(vcontract-c)*qcontract+fee,A*qcontract-qcontract*qcontract/2-c*qcontract),'q08':tuple(ownership(A,c,alpha)[0]for alpha in(0,F(1,8),F(1,4),1)),'q09':(lowbound,highbound,mach-wealth,mach,mach-highbound),'q10':(payment,retained,banks,remaining,ng*retained+banks+remaining),'q11':(entgain,0,treasgain,entgain+treasgain,-entgain/treasgain),'q12':(*bounds,bounds[0]-bounds[3],bounds[1]-bounds[2]),'q13':(ba*B-C,bb*B-C,gap,ba*(B-C)),'q14':(p14[1],*p14[2],p14[3]),'q15':(qmin,fmax,bmax,qmin*bmax,p15[1],*p15[2],p15[3]),'q16':(ba*(B-C),B-9,B-9,B-9+F(1,2)*fmax),'q17':(base,W0,ns,ks,Ws,Ws-W0),'q18':(tau,receipt,bill,rebate,worker,own,worker+own),'q19':(nc,kc,Wc,tc,rc,(rc-bc)/N,Ws-Wc,Ws-F(2,5)-Wc),'q20':(netgain(F(1,2)),netgain(F(3,2)),rc-bc-1,(rc-bc-1)/N,F(1,20)/2)}
    for key,value in out.items():eq(literal(r.markers[key]),value)
    need(set(r.markers)==set(inp)|set(out),'all26 input/result groups')
    for wage,t in product((2,4,5),(0,F(1,4),F(1,2),F(3,4),1)):
        n,rev,val=labor(wage,t)
        for test in(0,1,3,6):eq(val-((1-t)*wage*test-F(test*test,2)),(test-n)**2/2)
    eq(private+fiscal,trainresource);eq(private+grant+fiscal-grant,trainresource);eq(F(1,2)+1+grant,training)
    for z in(0,1,F(8,5),4,7,8,9):
        q,v,p,ret,foreign,revenue,H,world=channel(A,c,z)
        if q==0:
            for price in(2,5,20):eq(max(0,(A-price-z)/2),0)
        else:
            eq(p*q,ret+v*q+revenue);eq(v*q,c*q+foreign);eq(q*q/2+ret+foreign+revenue,world)
            for price in(2,3,5,6,8,10):truth(foreign>=(price-c)*max(0,(A-price-z)/2),'upstream global deviation')
    for alpha in(0,F(1,8),F(1,4),F(1,2),1):
        zz,qq=ownership(A,c,alpha);val=(A-c)*qq-(F(5,2)-2*alpha)*qq*qq
        for q in(0,F(1,2),1,F(3,2),2):truth(val>=(A-c)*q-(F(5,2)-2*alpha)*q*q,'global ownership tariff')
    for q in(0,1,2,3,4,5):eq((A-c)*qcontract-qcontract*qcontract-((A-c)*q-q*q),(q-qcontract)**2)
    eq(ng*wealth+banks+treasury,ng*mach+grid+treasury-grid);eq(ng*Y+treasury-grid,ng*retained+banks+remaining);eq(ng*payment,treasury-grid);truth(lowbound<loan and highbound>=loan,'credit switches')
    for a,b in product((lower,upper),repeat=2):
        diff=(nT*mT+(NT-nT)*a)/NT-(nC*mC+(NC-nC)*b)/NC;truth(bounds[0]-bounds[3]<=diff<=bounds[1]-bounds[2],'sharp archival bound')
    for q,f,b in product((F(0),F(1,4),F(1,2),F(3,4),F(1)),(0,1,2),(0,1,2)):
        incentive,tax,votes,res=contract(ba,C,B,q,f,b,admin,spill,bb)
        if incentive>=0:truth(q>=qmin and res<=p15[3],'global capped incentive');eq(3*tax,admin*q+q*b)
    eq(sum(p14[2]),F(1,4));eq(p15[3]-p14[3],F(3,2));truth(sum(v>=0 for v in p15[2])>=2,'majority');eq(p15[0],0)
    for cap in(0,1,F(8,5),3,6):
        n,k,value,objective=spatial(N,wa,wb,hs,cs,ds,cap)
        for nn,kk in product((0,1,2,3,4,5,6),(0,F(1,2),1,F(3,2),2,3)):
            if 0<=kk<=min(nn,cap):truth(value>=objective(nn,kk),'global spatial boundary witnesses')
    for nn,kk in((0,0),(6,0),(6,6),(3,1),(4,2)):
        dn=nn-ns;dk=kk-ks;eq(Ws-W(nn,kk),F(5,4)*dn*dn+(dk-dn/2)**2)
    eq(worker+own,Ws);eq(N*rebate+bill,receipt);eq(wa-hs*ns-tau,wb-hs*(N-ns));eq(wa-hs*nc-tc,wb-hs*(N-nc))
    for delivered in(0,F(1,2),1,ks,2,3):
        profit=(bill if delivered>=ks else 0)-cs*delivered*delivered/2;truth(profit<=0,'global provider choice')
    eq(2*F(1,40),F(1,20))
    bad=[lambda:num(True),lambda:num(float('inf')),lambda:labor(0,0),lambda:labor(4,-1),lambda:labor(4,2),lambda:financing(4,5),lambda:financing(4,-1),lambda:channel(2,2,0),lambda:channel(10,2,-1),lambda:ownership(10,2,-1),lambda:ownership(10,2,2),lambda:credit(2,6,9,10,F(1,2)),lambda:credit(2,6,9,2,2),lambda:contract(0,3,8,F(1,2),2,0,6,4,F(1,2)),lambda:contract(F(1,4),3,8,2,2,0,6,4,F(1,2)),lambda:spatial(0,12,10,1,1,1),lambda:spatial(6,12,10,0,1,1),lambda:spatial(6,12,10,1,1,1,-1),lambda:spatial(6,12,10,1,1,1,7),lambda:literal('1+1')]
    for fn in bad:
        try:fn()
        except(ValueError,TypeError,ZeroDivisionError):pass
        else:raise ValueError('invalid accepted')
    need(all((root/p).read_bytes()==raw for p,raw in before.items()),'files changed')
    return {'volume':'v15','component':'exam_a','role':'separate-peer','status':'pass','comparisons':count,'domain_rejections':len(bad),'parts':20,'points':100,'input_groups':len(inp),'output_groups':len(out),'runtime_files':6}
if __name__=='__main__':check()
