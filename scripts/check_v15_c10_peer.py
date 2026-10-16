"""Independent health/education/demography peer oracle. Never imports author code."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from math import isfinite,log,sqrt
import ast,json
FILES=('content/chapters/v15-c10.html','scripts/check_v15_c10.py','content/reviews/v15-c10-sources.json','content/reviews/v15-c10-author.json','scripts/check_v15_c10_peer.py','content/reviews/v15-c10-peer.json')
def need(x,m):
    if not x:raise ValueError(m)
def num(x):
    need(type(x)in(int,float,F)and isfinite(float(x)),'finite nonboolean');return F(str(x))
def insure(lowshare):
    lowshare=num(lowshare);need(0<lowshare<1,'both risk types');risks=(F(1,4),F(3,4));EU=tuple((1-p)*4+p*2 for p in risks);V=tuple(16-u*u for u in EU);cost=tuple(12*p for p in risks);pooled=lowshare*cost[0]+(1-lowshare)*cost[1];return EU,V,cost,pooled,max(F(0),pooled-V[0])
def care(a,c,p,lam,cap=6):
    a,c,p,lam,cap=map(num,(a,c,p,lam,cap));need(a>0 and c>0 and 0<=p<=1 and 0<=lam<=1 and cap>0,'care domain');q=min(cap,max(F(0),a-lam*c));bill=lam*c*q;reim=(1-lam)*c*q;premium=p*reim;benefit=a*q-q*q/2;return q,bill,reim,premium,benefit,c*q,benefit-c*q

def education(h,B):
    h,B=map(num,(h,B));need(h>0 and B>=0,'education domain');e=min(B,max(F(0),(1+B-h)/2));late=B-e;return e,late,(h+e)*(1+late)

def parent(beta,gamma,T,Y,f,tau,w):
    beta,gamma,T,Y,f,tau,w=map(num,(beta,gamma,T,Y,f,tau,w));need(beta>gamma>0 and T>0 and Y>=0 and f>0 and tau>0 and w>0,'parent domain');income=w*T+Y;full=f+w*tau;unc=(beta-gamma)*income/((1+beta)*full);n=min(T/tau,unc);res=income-full*n;need(res>0,'positive residual');c=res/(1+gamma);E=gamma*c;s=E/n;return c,n,s,T-tau*n,E

def pension(prev,now,sigma,w,t):
    prev,now,sigma,w,t=map(num,(prev,now,sigma,w,t));need(prev>0 and now>0 and 0<sigma<=1 and w>0 and 0<=t<=1,'pension domain');old=prev*sigma;tax=now*w*t;return old,tax,tax/old

def annuity(w,beta,R,sigma):
    w,beta,R,sigma=map(num,(w,beta,R,sigma));need(w>0 and beta>0 and R>0 and 0<sigma<=1,'annuity domain');s=beta*sigma*w/(1+beta*sigma);return s,w-s,R*s/sigma

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
    root=Path(root)if root else Path(__file__).resolve().parents[1];p=Read();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and len(p.ids)==len(set(p.ids)),'HTML/IDs');need(len(p.cases)==5 and len(p.prompts)==10 and p.prompts==p.solutions,'complete5cases10solutions');source=json.loads((root/FILES[2]).read_text());need(p.sources=={x['id']:x['url']for x in source['sources']},'exact source URLs')
    for file,count in((FILES[3],3),(FILES[5],5)):
        r=json.loads((root/file).read_text());bindings=r['payload_bindings'];need({x['path']for x in bindings}==set(FILES[:count]),'exact nonself binding set')
        for x in bindings:
            f=root/x['path'];need(f.stat().st_size==x['bytes']and sha256(f.read_bytes()).hexdigest()==x['sha256'],'freeze binding')
    n=0
    def eq(a,b):
        nonlocal n
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list))and len(a)==len(b),'shape')
            for x,y in zip(a,b):eq(x,y)
        else:n+=1;need(abs(float(a)-float(b))<1e-11,'numeric '+str((a,b)))
    inputs={'insurance':(16,12,F(1,4),F(3,4),F(1,2)),'care':(6,2,F(1,2),F(1,4),20),'education':(1,4),'fertility':(2,1,1,12,2,F(1,4),4,8),'pension':(100,100,F(4,5),10,F(1,5)),'annuity':(10,F(1,2),F(11,10),F(4,5))}
    for k,v in inputs.items():eq(parse(p.markers[k]),v)
    EU,V,cost,pool,subsidy=insure(F(1,2));uses=care(*inputs['care'][:4]);old=parent(2,1,1,12,2,F(1,4),4);new=parent(2,1,1,12,2,F(1,4),8);little=insure(F(3,4));half=care(6,2,F(1,2),F(1,2));zero0=parent(2,1,1,0,2,F(1,4),4);zero1=parent(2,1,1,0,2,F(1,4),8);cap=parent(2,1,1,50,2,F(1,4),4)
    out={'insurance-utility':EU,'insurance-value':V,'insurance-cost':(*cost,pool),'insurance-equilibrium':(cost[1],F(1,2)),'insurance-subsidy':(subsidy,pool-subsidy,subsidy),'care-use':uses[:4],'care-surplus':(*uses[4:],8-uses[-1]),'provider-ffs':(6,3*6,(3-2)*6,6*6-6*6/2-2*6),'provider-standard':(4,8,0,6*4-4*4/2-2*4),'education-optimum':(*education(1,4),(1+4)*(1+0),(1+0)*(1+4)),'education-causal':((3+2)*3-1*3,2*3,(3-1)*3),'fertility-old':old[:4],'fertility-new':new[:4],'pension-adjustment':(pension(*inputs['pension'])[2],pension(100,80,F(4,5),10,F(1,5))[2],F(5,2)*80/(10*80),pension(100,80,1,10,F(1,5))[2],F(5,2)*100/(10*80)),'annuity-old':annuity(*inputs['annuity']),'annuity-longer':annuity(10,F(1,2),F(11,10),1),'e1':(little[3],9,F(1,4),little[4]),'e3':(*half[:4],half[-1]),'e5':(*education(6,4),*education(F(1,4),F(1,4))),'e6':(1*3,(1+2)*3,3*3,(3+2)*3,F(3+9,2),F(9+15,2)),'e7':(zero0[1],zero0[2],zero0[0],zero1[1],zero1[2],zero1[0]),'e8':(cap[1],cap[0],cap[4],cap[2],cap[3]),'e9':(F(5,2)*100-F(1,4)*10*80,annuity(10,F(1,2),F(6,5),F(4,5))[0],annuity(10,F(1,2),F(6,5),F(4,5))[2])}
    for k,v in out.items():eq(parse(p.markers[k]),v)
    need(set(p.markers)==set(inputs)|set(out),'every actual displayed group')
    # Participation/endogenous pool reconstructed at every relevant price region.
    for share in(F(1,2),F(3,4)):
        EU,V,cost,pool,s=insure(share)
        for price in(F(0),V[0],(V[0]+9)/2,F(9),V[1],F(10)):
            mass=share*(price<=V[0])+(1-share)*(price<=V[1]);claims=share*cost[0]*(price<=V[0])+(1-share)*cost[1]*(price<=V[1]);profit=price*mass-claims
            if 0<mass and price<9:need(profit<0,'undercutting cannot profit');n+=1
            if price==9:eq(profit,0)
        eq(pool-s,V[0]);eq((pool-s)+s,pool);eq(pool,share*cost[0]+(1-share)*cost[1])
    for j in range(11):
        prob=F(j,10);EU=(1-prob)*4+prob*2;reserve=16-EU**2;eq(reserve-12*prob,4*prob*(1-prob));need(reserve>=12*prob,'risk premium');n+=1
    for lam in(F(0),F(1,4),F(1,2),F(3,4),F(1)):
        q,bill,reim,premium,H,C,S=care(6,2,F(1,2),lam);eq(bill+reim,C);eq(F(1,2)*bill+premium,F(1,2)*C);eq(8-S,2*(1-lam)**2);need(20>=premium+bill,'illness liquidity');n+=1
        for z in(F(0),F(1),F(4),F(5),F(6)):
            need(H-bill>=6*z-z*z/2-lam*2*z,'global patient');n+=1
    for fee in(F(1),F(2),F(3)):
        payoffs=[(fee-2)*q for q in range(7)];maxval=max(payoffs);arg=[q for q,val in enumerate(payoffs)if val==maxval];need(arg==([0]if fee==1 else list(range(7))if fee==2 else[6]),'all provider optimizer branches');n+=7
    for eps in(F(0),F(1,10),F(12)):
        for q in(F(0),F(1),F(3),F(4),F(5),F(6)):
            pay=(8+eps)if q>=4 else F(0);profit=pay-2*q;need(profit<=eps,'threshold provider');eq(6*q-q*q/2-pay+profit,6*q-q*q/2-2*q);n+=1
    for h,B in((F(1),F(4)),(F(6),F(4)),(F(1,4),F(1,4)),(F(2),F(0))):
        e,l,skill=education(h,B);eq(e+l,B)
        for candidate in(F(0),B/4,B/2,3*B/4,B):need(skill>=(h+candidate)*(1+B-candidate),'global education');n+=1
    # Parent global fixed-n value plus conditional c/E split, direct original cash accounts.
    for Y,w in((12,4),(12,8),(0,4),(0,8),(50,4)):
        c,nkids,per,work,E=parent(2,1,1,Y,2,F(1,4),w);eq(c+nkids*(2+per),w*work+Y);eq(E,nkids*per);need(work>=0,'time feasible');n+=1;value=log(float(c))+2*log(float(nkids))+log(float(per));I=w+Y;full=2+F(w,4)
        for candidate in(F(1,10),F(1,4),F(1,2),F(1),F(2),F(3),F(4)):
            if full*candidate>=I:continue
            residual=I-full*candidate;cc=residual/2;ss=cc/candidate;other=log(float(cc))+2*log(float(candidate))+log(float(ss));need(value>=other-1e-12,'parent global candidate');n+=1
    for now,sigma in((100,F(4,5)),(80,F(4,5)),(80,F(1))):
        old,tax,benefit=pension(100,now,sigma,10,F(1,5));eq(old*benefit,tax);required=F(5,2)*old/(10*now);eq(required*10*now,F(5,2)*old)
    for R,sigma in((F(11,10),F(4,5)),(F(11,10),F(1)),(F(6,5),F(4,5))):
        save,young,old=annuity(10,F(1,2),R,sigma);eq(young+save,10);eq(sigma*old,R*save);eq(1/young,F(1,2)*sigma/save);value=log(float(young))+float(sigma/2)*log(float(old))
        for alt in(F(1,10),F(1),F(2),F(4),F(6),F(9)):
            other=log(float(10-alt))+float(sigma/2)*log(float(R*alt/sigma));need(value>=other-1e-12,'global annuity');n+=1
    invalid=[lambda:num(True),lambda:num(float('inf')),lambda:num(float('nan')),lambda:insure(0),lambda:insure(1),lambda:care(6,2,F(1,2),-1),lambda:care(6,2,F(1,2),2),lambda:care(6,0,F(1,2),1),lambda:education(0,4),lambda:education(1,-1),lambda:parent(1,2,1,12,2,F(1,4),4),lambda:parent(2,1,1,-1,2,F(1,4),4),lambda:parent(2,1,1,12,2,0,4),lambda:parent(2,1,1,12,2,F(1,4),0),lambda:pension(100,0,1,10,F(1,5)),lambda:pension(100,80,0,10,F(1,5)),lambda:pension(100,80,1,10,2),lambda:annuity(10,F(1,2),0,1),lambda:annuity(10,F(1,2),1,0),lambda:annuity(10,F(1,2),1,2),lambda:parse('bool(1)')]
    for fn in invalid:
        try:fn()
        except(ValueError,ZeroDivisionError):pass
        else:raise ValueError('malformed accepted')
    return {'chapter':'v15-c10','role':'separate-peer','status':'passed','comparisons':n,'domain_rejections':len(invalid),'worked_cases':5,'solved_exercises':10,'input_groups':len(inputs),'result_groups':len(out),'runtime_files':6,'open_findings':[]}
if __name__=='__main__':check()
