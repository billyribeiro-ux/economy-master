"""Independent C12 audit: descending payment iteration with exact certification and finite Neumann sums."""
import ast,json,math
from fractions import Fraction as F
from itertools import product
from pathlib import Path
from hashlib import sha256
from html.parser import HTMLParser
FILES=('production/v14-c12-working.html','production/check_v14_c12_working.py','production/v14-c12-sources-working.json','production/v14-c12-author-review-working.json','production/check_v14_c12_peer_working.py','production/v14-c12-peer-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def real(x):
    need(type(x) in (int,float,F) and math.isfinite(float(x)),'finite scalar');return F(str(x))
def vec(x,n=None):
    need(isinstance(x,(list,tuple)) and len(x)>0,'nonempty vector');need(n is None or len(x)==n,'vector length');return tuple(map(real,x))
def solve(M,y):
    y=vec(y);n=len(y);need(len(M)==n,'square system')
    a=[list(vec(row,n))+[v] for row,v in zip(M,y)]
    for j in range(n):
        candidates=[i for i in range(j,n) if a[i][j]];need(candidates,'singular system')
        i=candidates[0];a[i],a[j]=a[j],a[i];pivot=a[j][j];a[j]=[v/pivot for v in a[j]]
        for i in range(j+1,n):
            factor=a[i][j];a[i]=[v-factor*w for v,w in zip(a[i],a[j])]
    x=[F(0)]*n
    for j in range(n-1,-1,-1):x[j]=a[j][-1]-sum(a[j][k]*x[k] for k in range(j+1,n))
    return tuple(x)
def mv(M,x):return tuple(sum(a*b for a,b in zip(row,x)) for row in M)
def neumann(K,d):
    d=vec(d);need(len(K)==len(d),'operator shape');K=tuple(vec(row,len(d)) for row in K)
    rho=max(sum(abs(x) for x in row) for row in K);need(rho<1,'contraction domain')
    y=[F(0)]*len(d);term=d
    for _ in range(160):y=[a+b for a,b in zip(y,term)];term=mv(K,term)
    return tuple(y),rho

def network(A,b,e):
    b=vec(b);n=len(b);e=vec(e,n);need(len(A)==n,'network size');A=tuple(vec(row,n) for row in A)
    need(min(b)>0 and min(e)>=0,'network resources')
    need(all(min(row)>=0 and row[i]==0 and sum(row)<1 for i,row in enumerate(A)),'outside leakage and diagonal')
    # Descend from full payment, then certify the inferred regime exactly.
    p=b
    for _ in range(90):p=tuple(min(b[i],e[i]+sum(A[j][i]*p[j] for j in range(n))) for i in range(n))
    default=tuple(p[i]<b[i] for i in range(n));M=[];rhs=[]
    for i in range(n):
        M.append(tuple((1 if i==j else 0)-(A[j][i] if default[i] else 0) for j in range(n)))
        rhs.append(e[i] if default[i] else b[i])
    p=solve(M,rhs);incoming=tuple(e[i]+sum(A[j][i]*p[j] for j in range(n)) for i in range(n))
    need(all(0<=p[i]<=b[i] and p[i]==min(b[i],incoming[i]) for i in range(n)),'exact clearing certificate')
    q=tuple(incoming[i]-p[i] for i in range(n));outside=sum((1-sum(row))*paid for row,paid in zip(A,p))
    return p,q,outside

def saving(y,yp,R,beta):
    y,yp,R,beta=map(float,map(real,(y,yp,R,beta)));need(min(y,yp,R,beta)>0,'saving domain')
    f=lambda a:-1/(y-a)+beta*R/(yp+R*a)
    if f(0)<=0:return 0.0
    lo=0.;hi=y*(1-1e-12)
    for _ in range(90):
        mid=(lo+hi)/2
        if f(mid)>0:lo=mid
        else:hi=mid
    return (lo+hi)/2

def literal(s):
    s=s.strip().replace('−','-')
    if '=' in s:s=s.split('=',1)[1]
    def walk(x):
        if isinstance(x,ast.Constant):return real(x.value)
        if isinstance(x,(ast.Tuple,ast.List)):return tuple(walk(y) for y in x.elts)
        if isinstance(x,ast.UnaryOp) and isinstance(x.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(x.op,ast.USub) else 1)*walk(x.operand)
        if isinstance(x,ast.BinOp) and isinstance(x.op,ast.Div):return walk(x.left)/walk(x.right)
        raise ValueError('literal numeric expression')
    return walk(ast.parse(s,mode='eval').body)

class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.mark={};self.active=None;self.ids=[];self.ex=[];self.sol=[];self.work=[];self.urls=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.work.append(a['id'])
        if t=='li' and a.get('id','').startswith('v14-c12-e'):self.ex.append(a['id'])
        if 'data-solution-for' in a:self.sol.append(a['data-solution-for'])
        if t=='a' and a.get('href','').startswith('https://'):self.urls.append(a['href'])
        for key in ('data-input','data-result'):
            if key in a:need(a[key] not in self.mark,'unique marker');self.active=a[key];self.mark[a[key]]=[key,'']
    def handle_data(self,s):
        if self.active:self.mark[self.active][1]+=s
    def handle_endtag(self,t):
        if t=='span':self.active=None

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={p:(root/p).read_bytes() for p in FILES}
    doc=Reader();doc.feed(raw[FILES[0]].decode());doc.close();ex=['v14-c12-e'+str(j) for j in range(1,13)]
    need(len(doc.ids)==len(set(doc.ids)),'unique IDs');need(doc.ex==doc.sol==ex,'exact prompt pairs');need(doc.work==['v14-c12-case'+str(j) for j in range(1,6)],'five cases')
    author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]]);sources=json.loads(raw[FILES[2]])
    need(set(peer['exact_prompt_review'])==set(ex),'complete peer review')
    for rec,paths in ((author,FILES[:3]),(peer,FILES[:5])):
        bs=rec['payload_bindings'];need(len(bs)==len(paths) and {b['path'] for b in bs}==set(paths),'hash membership')
        for b in bs:need(len(raw[b['path']])==b['bytes'] and sha256(raw[b['path']]).hexdigest()==b['sha256'],'payload bytes')
    need(set(doc.urls)=={s['url'] for s in sources['sources']},'all inspected external references')
    comparisons=0;rejections=0;seen=set()
    def close(a,b):
        nonlocal comparisons
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'comparison dimensions')
            for x,y in zip(a,b):close(x,y)
        else:need(abs(float(a)-float(b))<1e-9*max(1,abs(float(b))),str((a,b)));comparisons+=1
    def yes(b,msg):
        nonlocal comparisons
        need(b,msg);comparisons+=1
    def mark(k,x):close(literal(doc.mark[k][1]),x);seen.add(k)
    beta=(F(1,4),F(4));exp=(F(3,2),F(1,2));mark('betas',beta);mark('exposures',exp);mark('direct',F(1,50));mpcs=tuple(1/(1+b) for b in beta)
    avg=sum(mpcs)/2;feedback=sum(m*e for m,e in zip(mpcs,exp))/2;cov=sum((m-avg)*(e-1) for m,e in zip(mpcs,exp))/2
    mark('mean_mpc',avg);mark('income_feedback',feedback);mark('mpc_covariance',cov);y=F(1,50)/(1-feedback);mark('output',y);mark('induced',feedback*y);mark('equal_exposure_output',F(1,50)/(1-avg))
    for b,save,mpc in zip(beta,(F(6,5),F(39,5)),mpcs):
        close(saving(10,1,1,b),save)
        h=.0001;cplus=10+h-saving(10+h,1,1,b);cminus=10-h-saving(10-h,1,1,b);close((cplus-cminus)/(2*h),mpc)
    close(saving(1,3,1,.5),0);close(saving(2,1,1,.5),0)
    rev=sum(m*e for m,e in zip(mpcs,reversed(exp)))/2;close(rev,F(7,20));close(rev-avg,F(-3,20));close(F(1,50)/(1-rev),F(2,65));direct=(mpcs[0]-mpcs[1])*F(1,10)/2;close(direct,F(3,100));close(direct/(1-feedback),F(3,35))
    K=((F(2,5),0),(F(1,5),F(2,5)));d=(F(3,100),0);sol,rho=neumann(K,d);mark('sequence_k',K);mark('sequence_norm',rho);mark('sequence_y0',sol[0]);mark('sequence_y1',sol[1]);mark('sequence_cross',sol[1]/d[0]);mark('sequence_bound',F(3,5000)/(1-rho))
    close(sol,solve(((F(3,5),0),(F(-1,5),F(3,5))),d));added,_=neumann(K,(F(3,100),F(3,100)));close(added,(F(1,20),F(1,15)));close(sum(added),F(7,60));close((F(1,1000)+F(1,50)*F(1,20))/(1-F(31,50)),F(1,190))
    for trial in ((0,0),(F(1,20),F(1,60)),(.06,.01)):
        trial=vec(trial);r=tuple(a-b-c for a,b,c in zip(trial,d,mv(K,trial)));yes(max(abs(a-b) for a,b in zip(trial,sol))<=max(map(abs,r))/(1-rho)+F(1,10**20),'residual certificate')
    A=((0,F(1,2)),(F(1,2),0));b=(10,10)
    mark('network_b',b);mark('network_a',A);mark('network_shock',(1,6))
    base=network(A,b,(6,6));shock=network(A,b,(1,6));mark('network_p1',shock[0][0]);mark('network_p2',shock[0][1]);mark('network_outside',shock[2]);mark('network_gross_loss',sum(base[0])-sum(shock[0]));after=network(A,b,(F(9,10),6));diff=tuple(x-y for x,y in zip(shock[0],after[0]));mark('network_dp1',diff[0]);mark('network_dp2',diff[1]);close(sum(diff),F(1,5));close(shock[2]-after[2],F(1,10))
    for e,p,q,out in (((2,6),(F(20,3),F(28,3)),(0,0),8),((2,8),(7,10),(0,F(3,2)),F(17,2)),((1,7),(6,10),(0,0),8)):
        got=network(A,b,e);close(got,(p,q,out));close(sum(e),sum(got[1])+got[2])
    for e1 in (0,1,3,6,9):
        for e2 in (0,2,7,11):
            p,q,out=network(A,b,(e1,e2));close(e1+e2,sum(q)+out)
            raised=network(A,b,(e1+F(1,10),e2))[0];yes(all(v>=u for u,v in zip(p,raised)),'network monotonicity');yes(sum(v-u for u,v in zip(p,raised))<=F(1,5),'gross Lipschitz')
    # Asymmetric creditor orientation is independently tested against exact accounts.
    AA=((0,F(1,4)),(F(3,5),0));pp,qq,oo=network(AA,(4,7),(1,2));close(pp,(F(44,17),F(45,17)));close(3,sum(qq)+oo)
    for a in (0,3,10):close((min(10,a),min(10,a)),(a,a))
    yes(doc.mark['sdf_family'][1]=='m(a)=(1+a,1−2a,1+a)','SDF null direction');seen.add('sdf_family')
    yes(doc.mark['sdf_domain'][1]=='−1<a<1/2','strict positive kernel domain');seen.add('sdf_domain');mark('extra_price',F(2,5))
    pay=((F(1,3),F(1,3),F(1,3)),(0,F(1,3),F(2,3)),(F(1,3),0,0));m=solve(pay,(1,1,F(2,5)));a=m[0]-1;mark('identified_a',a);mark('sdf_vector',m);mark('sdf_variance',sum((v-1)**2 for v in m)/3)
    for a in (F(-9,10),F(-1,10),0,F(1,5),F(49,100)):
        m=(1+a,1-2*a,1+a);yes(min(m)>0,'positive family');close(sum(m)/3,1);close(sum(v*x for v,x in zip(m,(0,1,2)))/3,1);close(sum((v-1)**2 for v in m)/3,2*a*a)
    alternate=solve(pay,(1,1,F(3,10)));close(alternate,(F(9,10),F(6,5),F(9,10)));close(alternate[0]-1,F(-1,10))
    mark('moments',((1,1),(2,2)))
    identified=solve(((1,1),(1,-1)),(F(3,50),F(1,50)));mark('mechanism_a',identified[0]);mark('mechanism_b',identified[1]);mark('moment_determinant',1*(-1)-1*1)
    v1,v3=F(1,2500),F(1,10000);mark('mechanism_variance',(v1+v3)/4);mark('mechanism_covariance',(v1-v3)/4)
    for j in range(7):
        a=F(j,100);bb=F(3,50)-a;close((a+bb,2*a+2*bb),(F(3,50),F(3,25)))
    # Construct actual four-point mean-zero errors with valid covariance, then transform them.
    for corr in (-1,-.5,0,.5,1):
        obs=[]
        for u,v in product((-1,1),repeat=2):
            one=.02*u;three=.01*(corr*u+math.sqrt(1-corr*corr)*v);obs.append(((one+three)/2,(one-three)/2))
        c=corr*.02*.01
        close(sum(x*x for x,y in obs)/4,(float(v1+v3)+2*c)/4);close(sum(y*y for x,y in obs)/4,(float(v1+v3)-2*c)/4);close(sum(x*y for x,y in obs)/4,float(v1-v3)/4)
    close(sum(x*x for x in (.04,-.04,.04,-.04))/4,F(1,625));close(sum(x*x for x in (.01,.01,-.01,-.01))/4,F(1,10000))
    need(seen==set(doc.mark),'complete numeric and symbolic marker audit')
    bad=[(real,(True,)),(real,(float('nan'),)),(vec,([],)),(vec,((1,2),3)),(solve,(((1,0),(0,1),(0,0)),(1,2))),(solve,(((1,2),(2,4)),(1,2))),(solve,(((1,),),(1,2))),(neumann,(((1,0),(0,.5)),(1,1))),(neumann,(((.5,.2),),(1,))), (saving,(0,1,1,1)),(saving,(1,0,1,1)),(saving,(1,1,0,1)),(saving,(1,1,1,0)),(network,(((0,1),(1,0)),(10,10),(0,0))),(network,(((.1,.2),(.2,0)),(10,10),(1,1))),(network,(((0,-.2),(.2,0)),(10,10),(1,1))),(network,(A,(0,10),(1,1))),(network,(A,b,(-1,1))),(network,(A,b,(1,))), (literal,('sum([1])',)),(literal,('1/0',))]
    for fn,args in bad:
        try:fn(*args)
        except (ValueError,ZeroDivisionError):rejections+=1
        else:raise ValueError('invalid domain '+fn.__name__)
    result=dict(chapter='v14-c12',status='passed',comparisons=comparisons,domain_rejections=rejections,worked_examples=5,solutions=12,result_markers=sum(v[0]=='data-result' for v in doc.mark.values()),primitive_markers=sum(v[0]=='data-input' for v in doc.mark.values()),runtime_files=6,independence='Descending network iteration with exact certification, Neumann sums, derivative bisection and finite-support covariance; no author imports or execution')
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
