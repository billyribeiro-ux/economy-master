"""Independent six-payload IO audit. Author executable is never imported or run."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite
from pathlib import Path
FILES=('content/chapters/v15-c03.html','scripts/check_v15_c03.py','content/reviews/v15-c03-sources.json','content/reviews/v15-c03-author.json','scripts/check_v15_c03_peer.py','content/reviews/v15-c03-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite nonboolean number');return F(str(x)) if type(x) is float else F(x)
def literal(s):
    s=s.replace('−','-').rsplit('=',1)[-1].strip()
    if ';' in s:s='['+','.join('['+r+']' for r in s.strip('[]').split(';'))+']'
    def rec(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(rec(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*rec(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=rec(n.right);need(d!=0,'nonzero denominator');return rec(n.left)/d
        raise ValueError('numeric literal grammar')
    return rec(ast.parse(s,mode='eval').body)
def solve2(A,b):
    need(len(A)==len(b)==2 and all(len(r)==2 for r in A),'two-dimensional system');a,c=map(num,A[0]);d,e=map(num,A[1]);u,v=map(num,b);det=a*e-c*d;need(det!=0,'full rank');return ((u*e-c*v)/det,(a*v-u*d)/det)
def covariance(x,y):
    x=tuple(map(num,x));y=tuple(map(num,y));need(len(x)==len(y) and len(x)>1,'covariance samples');mx=sum(x)/len(x);my=sum(y)/len(y);return sum((a-mx)*(b-my) for a,b in zip(x,y))/len(x)
def demand(a,g,p):
    a,g=num(a),num(g);p=tuple(map(num,p));need(a>0 and 0<=g<1 and len(p)==2 and min(p)>=0,'concave nonnegative-price demand');q=solve2(((1,g),(g,1)),(a-p[0],a-p[1]));candidates=[(F(0),F(0)),(max(F(0),a-p[0]),F(0)),(F(0),max(F(0),a-p[1]))]
    if min(q)>=0:candidates.append(q)
    utility=lambda q:a*sum(q)-(q[0]**2+q[1]**2+2*g*q[0]*q[1])/2-sum(x*y for x,y in zip(p,q));return max(candidates,key=utility)
def welfare(a,g,c,p):
    c=tuple(map(num,c));need(len(c)==2 and min(c)>=0,'cost vector');q=demand(a,g,p);benefit=a*sum(q)-(q[0]**2+q[1]**2+2*g*q[0]*q[1])/2;spending=sum(x*y for x,y in zip(p,q));cs=benefit-spending;profits=tuple((pp-cc)*qq for pp,cc,qq in zip(p,c,q));return q,cs,profits,benefit-sum(cc*qq for cc,qq in zip(c,q))
def separate(a,g,c):
    a,g=num(a),num(g);c=tuple(map(num,c));need(a>0 and 0<=g<1 and len(c)==2 and min(c)>=0,'separate domain');p=solve2(((2,-g),(-g,2)),tuple(a*(1-g)+cc for cc in c));q=demand(a,g,p);need(min(q)>0 and all(pp>cc for pp,cc in zip(p,c)),'positive-margin interior pricing candidate');return p,q

def cournot(a,c,n,fixed):
    a,c,fixed=map(num,(a,c,fixed));need(a>c>0 and fixed>0 and type(n) is int and n>=0,'entry/Cournot domain')
    if n==0:return {'q':F(0),'Q':F(0),'p':a,'operating':F(0),'net':F(0),'cs':F(0),'W':F(0)}
    q=(a-c)/(n+1);Q=n*q;p=a-Q;op=(p-c)*q;return {'q':q,'Q':Q,'p':p,'operating':op,'net':op-fixed,'cs':Q*Q/2,'W':Q*Q/2+n*(op-fixed)}
def entry_counts(a,c,N,fixed):
    need(type(N) is int and N>=1,'positive finite entry set');out=[]
    for n in range(N+1):
        incumbent=(n==0 or cournot(a,c,n,fixed)['net']>=0);outside=(n==N or cournot(a,c,n+1,fixed)['net']<=0)
        if incumbent and outside:out.append(n)
    return tuple(out)
def clip(x):return max(F(0),min(F(1),x))
def fixed_points(alpha,intercept,fees):
    alpha=tuple(map(num,alpha));intercept=tuple(map(num,intercept));fees=tuple(map(num,fees));need(len(alpha)==len(intercept)==len(fees)==2 and min(alpha)>=0,'platform shape/domain');solutions=set()
    for state in product(('low','interior','high'),repeat=2):
        M=[];rhs=[]
        for i in range(2):
            row=[F(0),F(0)];row[i]=1
            if state[i]=='interior':row[1-i]=-alpha[i];right=intercept[i]-fees[i]
            else:right=F(state[i]=='high')
            M.append(row);rhs.append(right)
        try:n=solve2(M,rhs)
        except ValueError:continue
        if all(0<=x<=1 for x in n) and n==tuple(clip(intercept[i]+alpha[i]*n[1-i]-fees[i]) for i in range(2)):solutions.add(n)
    return tuple(sorted(solutions))
def funded(fees,reserve):
    fees=tuple(map(num,fees));reserve=num(reserve);need(reserve>=0 and sum(max(F(0),-f) for f in fees)<=reserve,'prefunded subsidy contract');return True

def critical(p,c,t):
    p,c,t=map(num,(p,c,t));need(p>c>=0 and t>0,'positive initial margin and increase');return t/((p-c)/p+t)
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.outputs={};self.prompts=[];self.solutions=[];self.cases=[];self.ids=[];self.sources={};self.links=set()
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attrs');need(t!='h1','fragment')
        if 'id' in a:need(a['id'].startswith('v15-c03-') and a['id'] not in self.ids,'unique prefixed IDs');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and a.get('id','').startswith('v15-c03-e'):self.prompts.append(a['id'])
        if 'data-solution-for' in a:need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'solution disclosure');self.solutions.append(a['data-solution-for'])
        if t=='a':self.links.add(a.get('href'))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.outputs)):
            if attr in a:k=a[attr];need(k not in d,'unique numeric marker');d[k]='';self.active.append((d,k,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,n in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced markup');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]
def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=Read();html=raw[FILES[0]].decode();doc.feed(html);need(not doc.stack,'complete markup');author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]]);sources=json.loads(raw[FILES[2]])
    for record,paths in ((author,FILES[:3]),(peer,FILES[:5])):
        bindings=record['payload_bindings'];need(len(bindings)==len(paths) and {b['path'] for b in bindings}==set(paths),'exact nonself set')
        for b in bindings:need((b['bytes'],b['sha256'])==(len(raw[b['path']]),sha256(raw[b['path']]).hexdigest()),'byte binding')
    targets=['v15-c03-e'+str(i) for i in range(1,11)];need(doc.prompts==doc.solutions==targets and set(peer['exact_prompt_review'])==set(targets),'ten exact reviewed pairs');need(doc.cases==['v15-c03-case'+str(i) for i in range(1,6)],'five cases');need({'v15-c02.html','v12-c03.html','v13-c06.html'}<=doc.links,'prerequisite routes');need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==3,'three primary source identities');need(all(s['inspection'] and s['limits'] for s in sources['sources']),'inspection limits');need('Feasible contracts promise total gross subsidies' in html and 'constrained' in html,'prefunding and planner scope')
    inp={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.outputs.items()};expected={};count=0
    def eq(a,b,label='identity'):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;need(a==b,label+str((a,b)))
    primitives={'demand':(F(20,3),F(20,3),F(4,3),F(-2,3),F(-2,3),F(4,3),6,F(1,4)),'pricing':(10,F(1,2),4,100,2),'entry':(4,14,2,8),'platform':(F(1,4),F(3,4),1),'test':(6,F(1,10))};need(set(inp)==set(primitives),'five actual inputs')
    for k,v in primitives.items():eq(inp[k],v,k)
    a1,a2,d11,d12,d21,d22,pbar,s=inp['demand'];D=((d11,d12),(d21,d22));rows=[]
    for z1,z2,u1,u2 in product((-s,s),repeat=4):
        prices=(pbar+z1+u1,pbar+z2+u2);quant=(a1-d11*prices[0]-d12*prices[1]+u1,a2-d21*prices[0]-d22*prices[1]+u2);rows.append((prices,quant,(z1,z2),(u1,u2)))
    ps=tuple(tuple(r[0][i] for r in rows) for i in range(2));qs=tuple(tuple(r[1][i] for r in rows) for i in range(2));zs=tuple(tuple(r[2][i] for r in rows) for i in range(2));us=tuple(tuple(r[3][i] for r in rows) for i in range(2));VP=tuple(tuple(covariance(x,y) for y in ps) for x in ps);PZ=tuple(tuple(covariance(x,y) for y in zs) for x in ps);QP=tuple(tuple(covariance(x,y) for y in ps) for x in qs);QZ=tuple(tuple(covariance(x,y) for y in zs) for x in qs);expected['covariances']=(VP[0][0],covariance(us[0],ps[0]),PZ[0][0]);expected['ols']=tuple(solve2(VP,r) for r in QP);expected['iv']=tuple(solve2(PZ,r) for r in QZ);eq(tuple(min(q) for q in qs),(F(23,12),F(23,12)));eq(PZ,((s*s,0),(0,s*s)))
    for row in expected['iv']:eq(sum(row),F(-2,3))
    bias=F(3,16)/(F(3,16)+s*s);expected['s1']=tuple(tuple(-D[i][j]+(bias if i==j else 0) for j in range(2)) for i in range(2));expected['s2']=(-d11-F(1,5),-d11+F(1,5))
    for t in (F(-2),F(0),F(3)):
        for row in expected['iv']:eq((row[0]+t)*s*s+(row[1]-t)*s*s,sum(row)*s*s)
    a,g,c,M,ce=inp['pricing'];p,q=separate(a,g,(c,c));q,cs,profits,W=welfare(a,g,(c,c),p);expected['pre']=(*p,*q);expected['prew']=(cs,sum(profits),W);preprofit=sum(profits);eq(sum(pp*qq for pp,qq in zip(p,q))+cs,a*sum(q)-(q[0]**2+q[1]**2+2*g*q[0]*q[1])/2)
    for cost,key in ((c,'post'),(ce,'efficient'),(F(3),'s3')):
        mergedp=((a+cost)/2,)*2;mq,mcs,mprofit,mW=welfare(a,g,(cost,cost),mergedp);expected[key]=(*mergedp,*mq,mcs,sum(mprofit),mW)
        for candidate in product((F(0),F(1),F(2),F(4),F(8)),repeat=2):
            profit=(a-cost)*sum(candidate)-(candidate[0]**2+candidate[1]**2+2*g*candidate[0]*candidate[1]);need(profit<=sum(mprofit),'global merged quantity witness');count+=1
    ap,aq=separate(a,g,(4,2));expected['s4']=(*ap,*aq)
    for costs,prices in (((c,c),p),((F(4),F(2)),ap)):
        base=welfare(a,g,costs,prices)[2]
        for who in range(2):
            for dprice in (F(j,2) for j in range(29)):
                alt=list(prices);alt[who]=dprice;quantity,cs2,profit2,W2=welfare(a,g,costs,alt);need(profit2[who]<=base[who],'all sampled unilateral corners');need(sum(pp*qq for pp,qq in zip(alt,quantity))<=a*a/(2*(1+g))<M,'wealth slack');count+=2
    N,ea,ec,Fcost=inp['entry'];need(N.denominator==1,'integer potential firms');N=int(N);three=cournot(ea,ec,3,Fcost);two=cournot(ea,ec,2,Fcost);expected['cournot3']=tuple(three[k] for k in ('q','Q','p','operating'));counts=entry_counts(ea,ec,N,Fcost);need(len(counts)==1,'unique pure count');expected['entrycount']=counts[0];expected['entryw']=tuple(cournot(ea,ec,n,Fcost)['W'] for n in range(N+1));A=ea-ec;expected['fullplanner']=(A,A*A/2-Fcost);expected['entrydecomp']=(three['net'],2*(three['net']-two['net']),three['cs']-two['cs'],three['W']-two['W']);expected['s5counts']=entry_counts(ea,ec,N,9);expected['s5w']=tuple(cournot(ea,ec,n,9)['W'] for n in range(N+1))
    for n in range(1,N+1):
        cont=cournot(ea,ec,n,Fcost);rivals=(n-1)*cont['q']
        for x in (F(j) for j in range(18)):
            profit=(max(F(0),ea-rivals-x)-ec)*x;need(profit<=cont['operating'],'Cournot all-branch deviation');count+=1
        eq(cont['cs']+n*cont['net'],cont['W'])
    aa,ab,reserve=inp['platform'];na=F(1,3);nb=F(2,3);fa=aa*nb-na;fb=1+ab*na-nb;funded((fa,fb),reserve);eq(fixed_points((aa,ab),(0,1),(fa,fb)),((na,nb),));expected['platformopt']=(na,nb,fa,fb);profit=fa*na+fb*nb;expected['platformcash']=(-fa*na,fb*nb,profit);expected['platformw']=(na*na/2,nb*nb/2,na*na/2+nb*nb/2+profit);sfa=ab*nb-na;sfb=1+aa*na-nb;expected['s7']=(na,nb,sfa,sfb,sfa*na+sfb*nb);funded((sfa,sfb),reserve);eq(fixed_points((ab,aa),(0,1),(sfa,sfb)),((na,nb),));expected['s8']=fixed_points((2,2),(1,1),(F(3,2),F(3,2)));need(len(expected['s8'])==3,'all nine active-set regimes')
    for x,y in product((F(0),F(1,4),F(1,2),F(3,4),F(1)),repeat=2):
        P=y-x*x-y*y+x*y;da=x-na;db=y-nb;eq(P,F(1,3)-da*da-db*db+da*db);need(P<=profit,'global platform profit');social=y-(x-y)**2/2;need(social<=1,'global platform welfare');eq(-x*x/2+y-y*y/2+x*y,social);count+=2
    eq(fixed_points((aa,ab),(0,1),(F(-3,4),F(3,4))),((1,1),));funded((F(-3,4),F(3,4)),reserve)
    price,t=inp['test'];newprice=price*(1+t);sq,_,spr,_=welfare(a,g,(c,c),(newprice,price));jq,_,jpr,_=welfare(a,g,(c,c),(newprice,newprice));expected['single']=(*sq,spr[0]-profits[0]);expected['diversion']=(sq[1]-q[1])/(q[0]-sq[0]);expected['joint']=(sum(jpr),sum(jpr)-preprofit);expected['losses']=((q[0]-sq[0])/q[0],(sum(q)-sum(jq))/sum(q),critical(price,c,t));hp=F(7);hq,_,hpr,_=welfare(a,g,(c,c),(hp,hp));highq,_,highpr,_=welfare(a,g,(c,c),(hp*(1+t),hp*(1+t)));expected['highbaseline']=(sum(highpr),sum(highpr)-sum(hpr));expected['s9']=((sum(hq)-sum(highq))/sum(hq),critical(hp,c,t))
    for initial,oldq,newq in ((price,q,jq),(hp,hq,highq)):
        loss=(sum(oldq)-sum(newq))/sum(oldq);margin=(initial-c)/initial;delta=initial*sum(oldq)*((margin+t)*(1-loss)-margin);direct=sum((initial*(1+t)-c)*qq for qq in newq)-sum((initial-c)*qq for qq in oldq);eq(delta,direct)
    need(set(expected)==set(shown),'every actual displayed result group')
    for k,v in expected.items():eq(shown[k],v,'result '+k)
    invalid=(lambda:num(True),lambda:num(float('nan')),lambda:literal('1/0'),lambda:literal('x(1)'),lambda:solve2(((1,2),(2,4)),(1,2)),lambda:covariance((1,),(1,)),lambda:covariance((1,2),(1,)),lambda:demand(10,1,(4,4)),lambda:demand(10,F(1,2),(-1,4)),lambda:separate(10,F(1,2),(20,20)),lambda:cournot(14,2,True,8),lambda:cournot(14,0,2,8),lambda:cournot(14,2,2,0),lambda:entry_counts(14,2,0,8),lambda:fixed_points((-1,1),(0,1),(0,0)),lambda:funded((-2,0),1),lambda:funded((0,0),-1),lambda:critical(4,4,F(1,10)),lambda:critical(6,4,0));rejected=0
    for fn in invalid:
        try:fn()
        except ValueError:rejected+=1
        else:raise ValueError('invalid domain accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'payload immutable')
    out={'chapter':'v15-c03','status':'passed','review':'separate-peer','worked_cases':5,'solutions':10,'input_groups':len(inp),'result_groups':len(shown),'comparisons':count,'rejected_inputs':rejected,'runtime_files':6,'open_findings':[]};json.dumps(out,allow_nan=False);return out
if __name__=='__main__':check()
