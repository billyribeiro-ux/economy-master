"""Historical inference: exact original numerical accounts; four runtime files."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from math import isfinite,ceil
import ast,json
FILES=('content/chapters/v15-c07.html','scripts/check_v15_c07.py','content/reviews/v15-c07-sources.json','content/reviews/v15-c07-author.json')
def need(x,m):
    if not x:raise ValueError(m)
def num(x):
    need(type(x)in(int,float,F)and isfinite(float(x)),'finite nonboolean');return F(str(x))
def bounds(r,observed,lo,hi):
    r,observed,lo,hi=map(num,(r,observed,lo,hi));need(0<=r<=1 and 0<=lo<=hi and observed>=0,'archive bounds domain');return r*observed+(1-r)*lo,r*observed+(1-r)*hi

def costs(w,e,L=4,E=5,K=12):
    w,e,L,E,K=map(num,(w,e,L,E,K));need(w>0 and e>0 and min(L,E,K)>=0,'cost domain');old=10*w+e;new=L*w+E*e+K;return old,new,old-new

def did(T,C,dlo,dhi,slo,shi):
    need(len(T)==len(C)==3,'three dates');T=tuple(map(num,T));C=tuple(map(num,C));dlo,dhi,slo,shi=map(num,(dlo,dhi,slo,shi));need(dlo<=dhi and slo<=shi,'ordered sensitivity');pre=(T[1]-T[0])-(C[1]-C[0]);D=(T[2]-T[1])-(C[2]-C[1]);return pre,D,D-dhi+slo,D-dlo+shi

def iv(rf,fs,glo,ghi):
    rf,fs,glo,ghi=map(num,(rf,fs,glo,ghi));need(fs!=0 and glo<=ghi,'IV domain');ends=sorted(((rf-glo)/fs,(rf-ghi)/fs));return rf/fs,*ends

def bank(cash,face,r,deposits,withdrawal,price,R):
    cash,face,r,deposits,withdrawal,price,R=map(num,(cash,face,r,deposits,withdrawal,price,R));need(cash>=0 and face>0 and 0<=r<=1 and deposits>=0 and cash<withdrawal<=deposits and price>0 and R>0,'bank domain');gap=withdrawal-cash;sold=gap/price;need(sold<=face,'sale feasible');initial=cash+r*face-deposits;sale=(face-sold)*r-(deposits-withdrawal);repay=gap*R;loan=face*r-(deposits-withdrawal)-repay;return initial,sold,sale,repay,loan,50*r

def posterior(prior,a,b,c,d):
    prior,a,b,c,d=map(num,(prior,a,b,c,d));need(0<prior<1 and all(0<x<=1 for x in(a,b,c,d)),'belief domain');joint1=a*c;joint2=b*d;p=prior*joint1/(prior*joint1+(1-prior)*joint2);dup=prior*joint1*a/(prior*joint1*a+(1-prior)*joint2*b);single=prior*a/(prior*a+(1-prior)*b);return joint1,joint2,p,dup,single

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
    inputs={'prices':(10,15,200,160,1,2,2,2,2,1,1,2),'tech':(10,1,4,5,12,4,1,2,2),'border':(4,5,9,3,4,6),'bank':(20,120,F(9,10),100,60,F(4,5),F(21,20)),'history-beliefs':(F(1,2),F(4,5),F(2,5),F(3,4),F(1,4))}
    for k,v in inputs.items():eq(parse(p.markers[k]),v)
    w0,w1,d0,d1,*v=inputs['prices'];p0=v[:2];p1=v[2:4];q0=v[4:6];q1=v[6:8];dot=lambda a,b:sum(x*y for x,y in zip(a,b));L=F(dot(p1,q0),dot(p0,q0));P=F(dot(p1,q1),dot(p0,q1));wratio=F(w1,w0);yratio=F(w1*d1,w0*d0)
    out={'price-results':(L,P,wratio/L,wratio/P,yratio/L,yratio/P),'archive-bounds':bounds(F(4,5),2400,0,3000),'tech-results':(*costs(4,1),*costs(2,2)),'border-results':did((4,5,9),(3,4,6),F(-1,2),F(1,2),0,1),'iv-bounds':iv(F(-3,5),F(-3,10),F(-3,20),F(3,20)),'bank-results':bank(*inputs['bank']),'history-results':posterior(*inputs['history-beliefs']),'e1':(w1*180,F(w1*180,w0*d0)/L,F(w1*180,w0*d0)/P),'e2':bounds(F(3,5),2400,1000,3000),'e3':(*costs(3,2),F(2,3)*2+2,*costs(2,2,3,3,8)[1:]),'e4':(ceil(F(80,4)),ceil(F(80,2))),'e5':did((4,5,9),(3,4,6),0,1,0,F(1,2))[2:],'e6':(*iv(F(-3,5),F(-1,10),F(-3,20),F(3,20))[1:],F(3,10)/F(1,10)),'e7':(F(40)/F(3,4),(120-F(40)/F(3,4))*F(9,10),20,F(108-40-20,40),F(45,40)),'e8':(bank(20,120,F(3,5),100,60,F(4,5),F(21,20))[0],50*F(3,5),42,40+42-120*F(3,5)),'e9':posterior(F(1,4),F(4,5),F(2,5),F(3,4),F(1,4))[2:4]}
    for k,v in out.items():eq(parse(p.markers[k]),v)
    need(set(p.markers)==set(inputs)|set(out),'all marked primitives/results checked')
    # Sharp completion endpoints and interiors, independent population totals.
    for count,lo,hi in((80,0,3000),(60,1000,3000)):
        low,high=bounds(F(count,100),2400,lo,hi)
        for missing in(lo,F(lo+hi,2),hi):
            mean=F(count*2400+(100-count)*missing,100);need(low<=mean<=high,'completion bound');n+=1
        eq(low,F(count*2400+(100-count)*lo,100));eq(high,F(count*2400+(100-count)*hi,100))
    for w in(F(1),F(2),F(3),F(10,3),F(4),F(8)):
        for e in(F(1),F(2),F(3)):
            old,new,saving=costs(w,e);eq(saving,6*w-4*e-12);need((saving>=0)==(w>=F(2,3)*e+2),'global adoption');n+=1
    for success in(F(1),F(1,2)):
        cutoff=ceil(80/(success*4));need(success*4*cutoff>=80 and success*4*(cutoff-1)<80,'integer invention threshold');n+=2
    for dlo,dhi,slo,shi in((F(-1,2),F(1,2),0,1),(0,1,0,F(1,2))):
        pre,D,lo,hi=did((4,5,9),(3,4,6),dlo,dhi,slo,shi)
        vals=[D-d+s for d in(dlo,dhi)for s in(slo,shi)];eq((min(vals),max(vals)),(lo,hi))
        for d in(dlo,(dlo+dhi)/2,dhi):
            for s in(slo,(slo+shi)/2,shi):
                tau=D-d+s;eq(tau+d-s,D);need(lo<=tau<=hi,'affine identified range');n+=1
    for fs in(F(-3,10),F(-1,10),F(1,10)):
        exc,lo,hi=iv(F(-3,5),fs,F(-3,20),F(3,20));eq(hi-lo,F(3,10)/abs(fs))
        for gamma in(F(-3,20),F(0),F(3,20)):
            beta=(F(-3,5)-gamma)/fs;eq(beta*fs+gamma,F(-3,5));need(lo<=beta<=hi,'signed IV endpoints');n+=1
    for recovery in(F(9,10),F(3,5)):
        for price in(F(4,5),F(3,4)):
            initial,sold,sale,repay,loan,coll=bank(20,120,recovery,100,60,price,F(21,20));eq(initial-sale,sold*(recovery-price));eq(initial-loan,repay-40);eq(sold*price,40);eq(20+40,60);eq(loan+40+repay,recovery*120)
    # Feasible collateral/private rate boundaries and selected nearby points.
    for R in(F(1),F(21,20),F(9,8),F(6,5),F(5,4)):
        equity=108-40-40*R;need((equity>=20)==(R<=F(6,5)),'private loan threshold');need((40*R<=45)==(R<=F(9,8)),'security threshold');n+=2
    for prior in(F(1,4),F(1,2),F(3,4)):
        a,b,c,d=F(4,5),F(2,5),F(3,4),F(1,4);j1,j2,post,dup,single=posterior(prior,a,b,c,d);odds=prior/(1-prior);eq(post/(1-post),odds*(a/b)*(c/d));eq(dup/(1-dup),odds*(a/b)**2*(c/d));eq(posterior(prior,a,b,F(1,2),F(1,2))[2],single);need(dup>post>single,'distinct evidence/copy');n+=1
    invalid=[lambda:num(True),lambda:num(float('nan')),lambda:num(float('inf')),lambda:bounds(-1,2400,0,3000),lambda:bounds(2,2400,0,3000),lambda:bounds(F(1,2),2400,2,1),lambda:costs(0,1),lambda:costs(1,-1),lambda:costs(1,1,K=-1),lambda:did((1,2),(1,2),0,1,0,1),lambda:did((1,2,3),(1,2,3),1,0,0,1),lambda:iv(1,0,0,1),lambda:iv(1,1,1,0),lambda:bank(20,120,2,100,60,1,1),lambda:bank(20,120,1,100,10,1,1),lambda:bank(20,120,1,100,101,1,1),lambda:bank(20,120,1,100,60,F(1,10),1),lambda:bank(20,120,1,100,60,1,0),lambda:posterior(0,1,1,1,1),lambda:posterior(F(1,2),0,1,1,1),lambda:posterior(F(1,2),2,1,1,1),lambda:parse('bool(1)')]
    for fn in invalid:
        try:fn()
        except(ValueError,ZeroDivisionError):pass
        else:raise ValueError('malformed accepted')
    return {'chapter':'v15-c07','status':'passed','comparisons':n,'domain_rejections':len(invalid),'worked_cases':5,'solved_exercises':10,'primitive_markers':len(inputs),'result_markers':len(out),'runtime_files':4,'scope':'Exact prices, missingness, adoption, sensitivity endpoints, bank balance sheets and dependent historical evidence; universal arguments reviewed separately.'}
if __name__=='__main__':check()
