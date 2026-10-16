"""Labor economics: independently recomputed original cases, quiet four-file API."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from math import sqrt,isfinite
import ast,json
FILES=('production/v15-c02-working.html','production/check_v15_c02_working.py','production/v15-c02-sources-working.json','production/v15-c02-author-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite scalar');return F(str(x))
def school(cost,gain,R):
    cost,gain,R=map(num,(cost,gain,R));need(cost>0 and gain>0 and R>0,'school domain');return -cost+gain/R+gain/R**2

def iv(mu,y,tau):
    mu,y,tau=[tuple(map(num,x))for x in(mu,y,tau)];need(len(mu)==len(y)==len(tau)==3 and min(mu)>0 and sum(mu)==1,'IV domain');a,c,n=mu
    d0=a;d1=a+c;y0=a*(y[0]+tau[0])+c*y[1]+n*y[2];y1=y0+c*tau[1];tm=a+c/2;ym=a*(y[0]+tau[0])+c*(y[1]+tau[1])/2;un=c*y[1]/2+n*y[2]
    return (d0,d1,y0,y1),((y1-y0)/(d1-d0),sum(m*t for m,t in zip(mu,tau)),ym/tm-un/(1-tm))

def labor(m):
    m=num(m);need(m>=0,'nonnegative wage floor');L=F(6)if m<=8 else m-2 if m<=11 else 20-m if m<=20 else F(0);w=max(m,2+L);rev=20*L-L**2/2;profit=rev-w*L;worker=w*L-2*L-L**2/2;return L,w,profit,worker,profit+worker

def taste(d):
    d=num(d);need(d>=0,'taste cost');a=F(4);bb=max((8-d)/2,F(0));wa=4+a;wb=4+bb;money=(12-wa)*a+(12-wb)*bb;return a,wa,bb,wb,money,money-d*bb

def signal(prior,acc,high=True):
    prior,acc=map(num,(prior,acc));need(0<prior<1 and F(1,2)<=acc<=1 and type(high)is bool,'signal domain');ph=acc if high else 1-acc;pl=1-acc if high else acc;post=prior*ph/(prior*ph+(1-prior)*pl);return 8+8*post

def callback(na,nb,ca,cb):
    need(all(type(x)is int for x in (na,nb,ca,cb)) and min(na,nb)>0 and 0<=ca<=na and 0<cb<=nb,'callback counts');pa=F(ca,na);pb=F(cb,nb);se=sqrt(float(pa*(1-pa)/na+pb*(1-pb)/nb));delta=pa-pb;return pa/pb,se,float(delta)-1.96*se,float(delta)+1.96*se

def migration(k,subsidy=0):
    k,subsidy=map(num,(k,subsidy));need(k>=0 and 0<=subsidy<=1,'migration domain');m=F(1,2)if k==0 else min(F(1,2),(3+subsidy)/k);return m,2*m,8-k*m,16-k*m,subsidy*m

def mobility(rho,var,error):
    rho,var,error=map(num,(rho,var,error));need(abs(rho)<1 and var>0 and error>=0,'stationary domain');V=var/(1-rho*rho);return V,rho,rho*V/(V+error)

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
    root=Path(root)if root else Path(__file__).resolve().parents[1];p=Read();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and len(set(p.ids))==len(p.ids),'HTML/IDs');need(len(p.cases)==5 and len(p.prompts)==10 and p.prompts==p.solutions,'case/solution coverage')
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
    inputs={'school':(30,20,F(11,10)),'iv-shares':(F(1,5),F(2,5),F(2,5)),'iv-baseline':(30,20,10),'iv-effects':(5,10,20),'labor':(20,2,1),'signal':(F(3,4),F(1,4),F(3,4)),'callbacks':(1000,1000,120,80),'migration':(6,8,10,16,3),'mobility':(F(3,5),F(16,25),1)}
    for k,v in inputs.items():eq(parse(p.markers[k]),v)
    moments,returns=iv(*[parse(p.markers[k])for k in ('iv-shares','iv-baseline','iv-effects')]);l0= labor(0);l10=labor(10);l12=labor(12);pa,pb,acc=parse(p.markers['signal']);mig0=migration(12);mig1=migration(12,1)
    outputs={'school-npv':school(*parse(p.markers['school'])),'iv-moments':moments,'iv-returns':returns,'iv-net':moments[3]-moments[2]-6*(moments[1]-moments[0]),'labor-results':(*l0[:4],l10[0],l10[2],l10[3],l12[0],l12[2],l12[3]),'signal-wages':(signal(pa,acc),signal(pb,acc),signal(pa,acc,False),signal(pb,acc,False)),'mobility-results':mobility(*parse(p.markers['mobility'])),'e1':school(35,20,F(11,10)),'e2':(F(6)/F(2,5),F(4)/F(2,5),F(6)/F(2,5)),'e3':(4-11*F(2,5),10),'e4':(labor(14)[0],12,labor(14)[2],labor(14)[3],labor(14)[4],84-(10**2-4**2)/2-2*(10-4),102-(10**2-4**2)/2-2*(10-4)),'e5':(sqrt(16),sqrt(36)),'e6':taste(6),'e7':(signal(pa,F(1,2)),signal(pb,F(1,2)),signal(pa,1),signal(pb,1,False)),'e8':callback(*map(int,parse(p.markers['callbacks']))),'e9':(*mig0[:4],mig1[0],mig1[4]),'e10':mobility(F(3,5),F(16,25),F(1,2))[2]}
    for k,v in outputs.items():eq(parse(p.markers[k]),v)
    need(set(p.markers)==set(inputs)|set(outputs),'every numerical marker checked')
    # Distinct identity/global witnesses, including kinks and rationing.
    R=(1+sqrt(7))/3;eq(school(30,20,R),0);eq(F(33,10)/F(11,10),3)
    for m in (F(0),F(2),F(7),F(8),F(17,2),F(10),F(11),F(12),F(14),F(20),F(21)):
        L,w,profit,worker,total=labor(m);eq(profit+worker,18*L-L**2);eq(w*L,20*L-L*L/2-profit)
        for trial in {F(0),F(6),max(F(0),m-2),max(F(0),20-m),F(9),L-F(1,10)if L>=F(1,10)else F(0),L+F(1,10)}:
            alternative=20*trial-trial**2/2-max(m,2+trial)*trial;need(profit>=alternative,'global hiring witness');count+=1
    for d in (0,2,6,8,10):
        a,wa,bb,wb,money,obj=taste(d);eq(money-obj,num(d)*bb);eq(wa,4+a);eq(wb,4+bb)
        for candidate in (F(0),F(1),F(3),F(4),F(5)):
            need(obj>=16+(8-d)*candidate-candidate*candidate,'taste global witness');count+=1
    for k,sub in ((0,0),(4,0),(6,0),(8,0),(12,0),(12,1)):
        m,share,wl,wh,bill=migration(k,sub);gain=wh-10-3+sub;need(wl-6-3+sub<=0 and (gain==0 if m<F(1,2)else gain>=0),'migration equilibrium');eq(m,share/2);eq(bill,sub*m);count+=1
    for rho,var,err in ((F(3,5),F(16,25),1),(F(4,5),F(9,25),0),(F(-1,2),F(3,4),F(1,2))):
        V,r,beta=mobility(rho,var,err);eq(V,rho*rho*V+var);eq(beta*(V+err),rho*V)
    # Explicit latent population enumeration rather than only a Wald identity.
    cells=[]
    for mass,y,t,ds in zip(inputs['iv-shares'],inputs['iv-baseline'],inputs['iv-effects'],((1,1),(0,1),(0,0))):
        for z in (0,1):cells.append((mass/2,z,ds[z],y+t*ds[z]))
    for z in (0,1):
        eq(sum(m*y for m,zz,d,y in cells if zz==z)*2,moments[2+z]);eq(sum(m*d for m,zz,d,y in cells if zz==z)*2,moments[z])
    for accuracy in (F(1,2),F(3,4),F(1)):
        for prior in (F(1,4),F(3,4)):
            ph=prior*accuracy+(1-prior)*(1-accuracy);eq(ph*signal(prior,accuracy)+(1-ph)*signal(prior,accuracy,False),8+8*prior)
    invalid=[lambda:school(0,20,1),lambda:school(30,20,0),lambda:school(30,float('inf'),1),lambda:iv((1,1,1),(1,2,3),(1,2,3)),lambda:iv((F(1,2),0,F(1,2)),(1,2,3),(1,2,3)),lambda:labor(-1),lambda:labor(True),lambda:taste(-1),lambda:signal(0,F(3,4)),lambda:signal(F(1,2),F(1,4)),lambda:signal(F(1,2),1,1),lambda:callback(0,1,0,1),lambda:callback(10,10,11,1),lambda:callback(10,10,1,0),lambda:callback(10.0,10,1,1),lambda:migration(-1),lambda:migration(2,2),lambda:mobility(1,1,1),lambda:mobility(0,-1,1),lambda:mobility(0,1,-1),lambda:parse('bool(1)')]
    for fn in invalid:
        try:fn()
        except (ValueError,ZeroDivisionError):pass
        else:raise ValueError('accepted invalid domain')
    result={'chapter':'v15-c02','status':'passed','comparisons':count,'domain_rejections':len(invalid),'worked_cases':5,'solved_exercises':10,'primitive_markers':len(inputs),'result_markers':len(outputs),'runtime_files':4,'scope':'Exact population, budget, equilibrium, posterior and stationary calculations; global witnesses supplement full domain/proof review.'};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
