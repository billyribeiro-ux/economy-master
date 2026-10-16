"""Health, education and demographic economics: four-file quiet author API."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from itertools import product
from math import sqrt,log,isfinite
import ast,json
FILES=('production/v15-c10-working.html','production/check_v15_c10_working.py','production/v15-c10-sources-working.json','production/v15-c10-author-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x)in(int,float,F)and isfinite(float(x)),'finite nonboolean scalar');return F(str(x))
def insurance(W,L,p):
    W,L,p=map(num,(W,L,p));need(0<L<W and 0<=p<=1,'insurance domain');u=(1-float(p))*sqrt(W)+float(p)*sqrt(W-L);return u,float(W)-u*u,p*L

def care(a,c,lam,prob,Q=6):
    a,c,lam,prob,Q=map(num,(a,c,lam,prob,Q));need(a>0 and c>0 and 0<=lam<=1 and 0<prob<=1 and Q>0,'care domain');q=min(Q,max(a-lam*c,0));benefit=a*q-q*q/2;patient=lam*c*q;insurer=(1-lam)*c*q;return q,patient,insurer,prob*insurer,benefit,c*q,benefit-c*q

def education(h,B):
    h,B=map(num,(h,B));need(h>0 and B>=0,'education domain');e=min(B,max((1+B-h)/2,0));l=B-e;return e,l,(h+e)*(1+l)
def fertility(beta,gamma,T,Y,f,tau,w):
    beta,gamma,T,Y,f,tau,w=map(num,(beta,gamma,T,Y,f,tau,w));need(beta>gamma>0 and min(T,f,tau,w)>0 and Y>=0,'fertility domain');I=w*T+Y;full=f+w*tau;n=min((beta-gamma)*I/((1+beta)*full),T/tau);remain=I-full*n;c=remain/(1+gamma);E=gamma*c;need(n>0 and c>0 and E>0,'positive allocation');return c,n,E/n,T-tau*n,E,full,I

def pension(prev,current,sigma,w,t):
    prev,current,sigma,w,t=map(num,(prev,current,sigma,w,t));need(min(prev,current,w)>0 and 0<sigma<=1 and 0<=t<=1,'pension domain');old=prev*sigma;receipts=t*w*current;return old,receipts,receipts/old

def annuity(w,beta,R,sigma):
    w,beta,R,sigma=map(num,(w,beta,R,sigma));need(min(w,beta,R)>0 and 0<sigma<=1,'annuity domain');s=beta*sigma*w/(1+beta*sigma);return s,w-s,R*s/sigma
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
            if k in a:need(a[k]not in self.markers,'unique marker');self.markers[a[k]]=''
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
    root=Path(root)if root else Path(__file__).resolve().parents[1];r=Read();r.feed((root/FILES[0]).read_text());r.close();need(not r.stack and len(r.ids)==len(set(r.ids)),'structure');need(len(r.cases)==5 and len(r.prompts)==10 and r.prompts==r.solutions,'five cases ten exact solutions');src=json.loads((root/FILES[2]).read_text());need(r.sources=={s['id']:s['url']for s in src['sources']},'source scope links');rev=json.loads((root/FILES[3]).read_text());bindings=rev['payload_bindings'];need(len(bindings)==3 and {x['path']for x in bindings}==set(FILES[:3]),'three nonself bindings')
    for x in bindings:
        raw=(root/x['path']).read_bytes();need(len(raw)==x['bytes']and sha256(raw).hexdigest()==x['sha256'],'freeze')
    comparisons=0
    def eq(x,y):
        nonlocal comparisons
        if isinstance(y,(tuple,list)):
            need(isinstance(x,(tuple,list))and len(x)==len(y),'shape')
            for a,b in zip(x,y):eq(a,b)
        else:need(abs(float(x)-float(y))<=2e-10*max(1,abs(float(y))),'numeric mismatch '+str((x,y)));comparisons+=1
    def truth(x,msg):
        nonlocal comparisons
        need(x,msg);comparisons+=1
    inputs={'insurance':(16,12,F(1,4),F(3,4),F(1,2)),'care':(6,2,F(1,2),F(1,4),20),'education':(1,4),'fertility':(2,1,1,12,2,F(1,4),4,8),'pension':(100,100,F(4,5),10,F(1,5)),'annuity':(10,F(1,2),F(11,10),F(4,5))}
    for k,v in inputs.items():eq(parse(r.markers[k]),v)
    W,L,pl,ph,share=parse(r.markers['insurance']);low=insurance(W,L,pl);high=insurance(W,L,ph);pooled=share*low[2]+(1-share)*high[2];sub=float(pooled)-low[1];a,c,prob,lam,wealth=parse(r.markers['care']);use=care(a,c,lam,prob);efficient=care(a,c,1,prob);h,B=parse(r.markers['education']);ed=education(h,B);beta,gamma,T,Y,f,tau,w0,w1=parse(r.markers['fertility']);fo=fertility(beta,gamma,T,Y,f,tau,w0);fn=fertility(beta,gamma,T,Y,f,tau,w1);Nprev,Ncur,sigma,w,tx=parse(r.markers['pension']);pens=pension(Nprev,Ncur,sigma,w,tx);smaller=pension(Nprev,80,sigma,w,tx);longer=pension(Nprev,80,1,w,tx);wa,be,R,sig=parse(r.markers['annuity']);an=annuity(wa,be,R,sig);anlong=annuity(wa,be,R,1);usehalf=care(a,c,F(1,2),prob);fx0=fertility(beta,gamma,T,0,f,tau,w0);fx1=fertility(beta,gamma,T,0,f,tau,w1);fcap=fertility(beta,gamma,T,50,f,tau,w0);newpool=F(3,4)*low[2]+F(1,4)*high[2];newan=annuity(wa,be,F(6,5),sig)
    out={'insurance-utility':(low[0],high[0]),'insurance-value':(low[1],high[1]),'insurance-cost':(low[2],high[2],pooled),'insurance-equilibrium':(high[2],1-share),'insurance-subsidy':(sub,float(pooled)-sub,sub),'care-use':use[:4],'care-surplus':(*use[4:],efficient[6]-use[6]),'provider-ffs':(6,3*6,(3-c)*6,a*6-6*6/2-c*6),'provider-standard':(4,8,8-c*4,a*4-4*4/2-c*4),'education-optimum':(*ed,(h+B),h*(1+B)),'education-causal':((3+2)*3-1*3,2*3,(3-1)*3),'fertility-old':fo[:4],'fertility-new':fn[:4],'pension-adjustment':(pens[2],smaller[2],pens[2]*smaller[0]/(w*80),longer[2],pens[2]*longer[0]/(w*80)),'annuity-old':an,'annuity-longer':anlong,'e1':(newpool,high[2],F(1,4),float(newpool)-low[1]),'e3':(*usehalf[:4],usehalf[6]),'e5':(*education(6,4),*education(F(1,4),F(1,4))),'e6':(1*3,(1+2)*3,3*3,(3+2)*3,(1*3+3*3)/2,((1+2)*3+(3+2)*3)/2),'e7':(fx0[1],fx0[2],fx0[0],fx1[1],fx1[2],fx1[0]),'e8':(fcap[1],fcap[0],fcap[4],fcap[2],fcap[3]),'e9':(longer[0]*pens[2]-F(1,4)*w*80,newan[0],newan[2])}
    for k,v in out.items():eq(parse(r.markers[k]),v)
    need(set(r.markers)==set(inputs)|set(out),'all numerical markers verified')
    # Participation regions and actuarial resource accounts, including p endpoints.
    for p in (0,F(1,4),F(1,2),F(3,4),1):
        u,value,cost=insurance(W,L,p);truth(value+1e-12>=cost,'Jensen risk premium');eq(sqrt(float(W)-value),u)
    for P in (0,3,F(15,4),6,9,F(39,4),10):
        buyers=tuple((mass,p)for mass,p,value in ((share,pl,low[1]),(1-share,ph,high[1]))if float(P)<=value);mass=sum(m for m,_ in buyers);profit=sum(m*(P-p*L)for m,p in buyers)
        if P==9:eq((mass,profit),(F(1,2),0))
        if P<9:truth(profit<=0,'no profitable lower premium entrant')
    eq(float(pooled)-sub,low[1]);eq((1-share)*float(pooled)+share*float(pooled),pooled);eq(float(pooled)-sub+sub,pooled)
    for lam0 in (0,F(1,4),F(1,2),1):
        U=care(a,c,lam0,prob);q,patient,reimb,premium,H,real,surplus=U;eq(prob*patient+premium,prob*real);eq(efficient[6]-surplus,(q-4)**2/2);truth(patient+premium<=wealth,'patient liquidity')
        for trial in (0,2,4,6):truth(H-lam0*c*q>=a*trial-F(trial*trial,2)-lam0*c*trial,'global patient utility')
    for fee in (1,2,3):
        opt=0 if fee<=c else 6;maximum=(fee-c)*opt
        for q in (0,2,4,6):truth(maximum>=(fee-c)*q,'linear provider global branch')
    for eps in (F(1,10),1,12):
        truth(8+eps<=20,'funded delivery rent')
        for q in (0,2,4,5,6):
            pi=(8+eps if q>=4 else 0)-c*q;truth(eps>=pi,'verified delivery unique maximizer')
        eq((a*4-4*4/2)-(8+eps)+eps,8)
    for hh,bb in ((1,4),(6,4),(F(1,4),F(1,4)),(2,0)):
        e,l,skill=education(hh,bb);eq(e+l,bb)
        for candidate in (F(0),bb/2,bb):truth(skill>=(hh+candidate)*(1+bb-candidate),'education global boundary')
    for yy,ww in ((12,4),(12,8),(0,4),(0,8),(50,4)):
        cc,nn,ss,work,EE,FF,II=fertility(beta,gamma,T,yy,f,tau,ww);eq(cc+nn*(f+ss),ww*work+yy);eq(cc+FF*nn+EE,II);truth(work>=0,'time feasibility');eq(EE,nn*ss)
        # Concave transformed objective gives a supporting-gradient certificate for all feasible alternatives.
        for scale in (F(1,2),1):
            ntry=nn*scale;remaining=II-FF*ntry;ctry=remaining/(1+gamma);Etry=gamma*ctry;gap=(ctry-cc)/cc+(beta-gamma)*(ntry-nn)/nn+gamma*(Etry-EE)/EE;truth(gap<=F(0),'supporting gradient global certificate')
    truth(T*f-tau*Y<0 and T*f>0,'wage sign switch');eq(fcap[1],T/tau)
    for previous,current,surv in ((100,100,F(4,5)),(100,80,F(4,5)),(100,80,1)):
        old,col,b=pension(previous,current,surv,w,tx);eq(b*old,tx*w*current);truth(old>0,'positive retiree denominator')
    for ss in (F(1,2),F(4,5),1):
        save,young,old=annuity(wa,be,R,ss);eq(young+save,wa);eq(ss*old,R*save);eq(1/young,be*ss/save)
        objective=log(young)+float(be*ss)*log(old)
        for trial in (1,2,5,9):truth(objective>=log(float(wa)-trial)+float(be*ss)*log(float(R)*trial/float(ss))-1e-12,'annuity global witness')
    eq(an[0],newan[0]);eq(pens[0]*pens[2],200)
    bad=[lambda:num(True),lambda:num(float('nan')),lambda:insurance(12,12,F(1,2)),lambda:insurance(16,0,F(1,2)),lambda:insurance(16,12,-1),lambda:insurance(16,12,2),lambda:care(6,2,-1,F(1,2)),lambda:care(6,2,2,F(1,2)),lambda:care(6,0,F(1,2),F(1,2)),lambda:education(0,4),lambda:education(1,-1),lambda:fertility(1,1,1,12,2,F(1,4),4),lambda:fertility(2,0,1,12,2,F(1,4),4),lambda:fertility(2,1,1,-1,2,F(1,4),4),lambda:fertility(2,1,1,12,2,0,4),lambda:fertility(2,1,1,12,2,F(1,4),0),lambda:pension(100,0,F(4,5),10,F(1,5)),lambda:pension(100,100,0,10,F(1,5)),lambda:pension(100,100,1,10,2),lambda:annuity(10,F(1,2),1,0),lambda:annuity(10,F(1,2),0,1),lambda:annuity(10,0,1,1),lambda:parse('1+1')]
    for fn in bad:
        try:fn()
        except(ValueError,TypeError,ZeroDivisionError):pass
        else:raise ValueError('invalid input accepted')
    return {'chapter':'v15-c10','status':'pass','comparisons':comparisons,'domain_rejections':len(bad),'worked_cases':5,'solutions':10,'input_groups':len(inputs),'output_groups':len(out),'runtime_files':4}
if __name__=='__main__':check()
