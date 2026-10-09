"""Separate C08 reconstruction; stdlib, six read-only payloads, no author execution."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from math import isfinite, sqrt
from pathlib import Path

AUTHOR=('content/chapters/v14-c08.html','scripts/check_v14_c08.py','content/reviews/v14-c08-sources.json','content/reviews/v14-c08-author.json')
FILES=AUTHOR+('scripts/check_v14_c08_peer.py','content/reviews/v14-c08-peer.json')
def need(ok,msg):
    if not ok: raise ValueError(msg)
def num(x):
    need(not isinstance(x,bool) and isinstance(x,(int,float,F)) and isfinite(float(x)),'finite number required')
    return F(str(x)) if isinstance(x,float) else F(x)
def parsed(s):
    def read(n):
        if isinstance(n,ast.Constant): return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)): return tuple(read(a) for a in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return read(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=read(n.right);need(d!=0,'zero denominator');return read(n.left)/d
        raise ValueError('numeric marker syntax')
    return read(ast.parse(s.strip(),mode='eval').body)

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.mark={};self.pending=[];self.ids=[];self.ex=[];self.sol=[];self.worked=[];self.sources={};self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        d=dict(attrs)
        if 'id' in d:need(d['id'] not in self.ids,'duplicate id');self.ids.append(d['id'])
        if 'worked' in d.get('class','').split():self.worked.append(d.get('id'))
        if t=='li' and d.get('id','').startswith('v14-c08-e'):self.ex.append(d['id'])
        if 'data-solution-for' in d:
            need(any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.stack),'solution details');self.sol.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d.get('href')
        if 'data-calc' in d:
            k=d['data-calc'];need(k not in self.mark,'duplicate marker');self.mark[k]='';self.pending.append((k,len(self.stack)))
        if t=='tr':need(self.row is None,'nested row');self.row=[]
        if t in ('td','th'):self.cell=''
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,d))
    def handle_data(self,s):
        for k,n in self.pending:self.mark[k]+=s
        if self.cell is not None:self.cell+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'unbalanced html');self.stack.pop();self.pending=[(k,n) for k,n in self.pending if n<len(self.stack)]
        if t in ('td','th'):self.row.append(self.cell.strip());self.cell=None
        if t=='tr':self.rows.append(self.row);self.row=None

def qcase(a=3,cap=2,R=F(21,20),delta=F(1,10),k0=1):
    a,cap,R,delta,k0=map(num,(a,cap,R,delta,k0))
    need(cap>=0 and R>0 and 0<=delta<=1 and k0>=0,'investment domain')
    inherited=(1-delta)*k0
    # Differentiate the whole original scalar objective, then compare with dated q.
    root=(a-inherited-R)/(2*R+1);i=max(F(0),min(cap,root));k=inherited+i
    return i,k,(a-k)/R,((a-k/2)/R if k>0 else None)

def agency(I=100,Y=180,h=F(4,5),l=F(2,5),benefit=20,R=F(11,10),n=10):
    I,Y,h,l,benefit,R,n=map(num,(I,Y,h,l,benefit,R,n))
    need(I>0 and Y>0 and 0<=l<h<=1 and benefit>0 and R>0 and 0<=n<=I,'agency domain')
    floor=benefit/(h-l);need(floor<=Y,'high effort impossible')
    pledge=h*(Y-floor);debt=R*(I-n)/h;y=Y-debt
    return dict(floor=floor,pledge=pledge,threshold=I-pledge/R,surplus=h*Y-R*I,debt=debt,y=y,slack=(h-l)*y-benefit,loan=I-n)

def collateral(A,theta,n):
    A,theta,n=map(num,(A,theta,n));need(A>0 and 0<=theta<1 and n>=0,'collateral domain')
    # Bracket the positive root of the primitive financing inequality, no quadratic-formula oracle.
    lo=0.;hi=max(1.,float(theta*A)+sqrt(float(n))+1.)
    for _ in range(100):
        z=(lo+hi)/2
        if z*z-float(theta*A)*z-float(n)>0:hi=z
        else:lo=z
    cap=((lo+hi)/2)**2;i=min(float(A*A/4),cap);out=float(A)*sqrt(i);b=max(0,i-float(n))
    return dict(i=i,cap=cap,b=b,output=out,wealth=float(n)+out-i,threshold=A*A/4-theta*A*A/2)

def overhang(X,D,J,Z):
    X,D,J,Z=map(num,(X,D,J,Z));need(min(X,D,J,Z)>=0,'nonnegative overhang primitives')
    reservation=min(D,X);old=max(X-D,0);equity=max(X+Z-D,0)-old-J
    lo=reservation;hi=X+Z-old-J
    return equity,Z-J,(lo,hi),(lo+hi)/2,min(D,X+Z)-reservation

def path(A,n=1,W=10,R=1,lam=F(1,2),s=F(3,4)):
    need(isinstance(A,(tuple,list)) and len(A)>0,'nonempty finite path')
    A=tuple(map(num,A));n,W,R,lam,s=map(num,(n,W,R,lam,s))
    need(n>0 and W>=0 and R>0 and 0<=lam<1 and 0<s<1 and min(A)>R,'dynamic domain')
    rows=[]
    for t,a in enumerate(A):
        b=lam*n/(1-lam);i=n+b;need(b<=W,'outside lender funding exhausted')
        output=a*i;repay=R*b;cash=output-repay
        retained=s*cash if t<len(A)-1 else F(0);dividend=cash-retained
        outside=R*(W-b);nextW=outside+repay
        rows.append(dict(n=n,i=i,b=b,E=cash,retained=retained,dividend=dividend,total=output+outside,W=W,nextW=nextW,output=output,repay=repay,outside=outside))
        n,W=retained,nextW
    return rows

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(base/p).read_bytes() for p in FILES};doc=Document();doc.feed(payload[AUTHOR[0]].decode());doc.close()
    need(not doc.stack and all(i.startswith('v14-c08-') for i in doc.ids),'closed prefixed html')
    exercises=['v14-c08-e'+str(i) for i in range(1,13)]
    need(doc.ex==doc.sol==exercises,'all exact prompts and solutions');need(doc.worked==['v14-c08-w'+str(i) for i in range(1,6)],'five worked cases')
    source=json.loads(payload[AUTHOR[2]]);author=json.loads(payload[AUTHOR[3]]);peer=json.loads(payload[FILES[-1]])
    need(doc.sources=={s['id']:s['url'] for s in source['sources']},'source routing');need(set(peer['exact_prompt_solution_audit'])==set(exercises),'peer prompt coverage')
    for record,paths in ((author,set(AUTHOR[:3])),(peer,set(FILES[:-1]))):
        bindings=record['payload_bindings'];need(len(bindings)==len(paths) and {b['path'] for b in bindings}==paths,'nonself bindings')
        for b in bindings:need(len(payload[b['path']])==b['bytes'] and sha256(payload[b['path']]).hexdigest()==b['sha256'],'frozen bytes changed')
    comparisons=0;rejects=0
    def near(a,b,tol=1e-10):
        nonlocal comparisons
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'dimensions')
            for x,y in zip(a,b):near(x,y,tol)
        else:need(isfinite(float(a)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),str((a,b)));comparisons+=1
    q=qcase();e2=qcase(2);ag=agency();e4=agency(benefit=24);col=collateral(4,F(1,5),F(1,5));newcol=collateral(4,F(1,5),F(32,25));e6=collateral(4,F(1,4),F(3,4));ov=overhang(80,100,15,25);e8=overhang(80,100,15,20)
    normal=path((F(6,5),)*3);stress=path((F(11,10),F(6,5),F(6,5)));un=path((F(6,5),)*3,lam=0);us=path((F(11,10),F(6,5),F(6,5)),lam=0);low=path((F(6,5),)*3,s=F(1,2));relax=path((F(6,5),)*3,lam=F(3,4))
    fp=4/(2*sqrt(col['i']));di=1/(1-.2*fp);mu=(fp-1)*di
    results={'q-investment':q[0],'q-capital':q[1],'q-marginal':q[2],'q-average':q[3],
      'agency-reward':ag['floor'],'agency-pledge':ag['pledge'],'agency-min-n':ag['threshold'],'agency-surplus':ag['surplus'],'agency-success-debt':ag['debt'],'agency-success-equity':ag['y'],'agency-ic-slack':ag['slack'],
      'collateral-i':col['i'],'collateral-b':col['b'],'collateral-wealth':col['wealth'],'collateral-derivative':di,'collateral-shadow':mu,'collateral-new-i':newcol['i'],'collateral-threshold':col['threshold'],
      'overhang-equity':ov[0],'overhang-surplus':ov[1],'overhang-interval':ov[2],
      'dynamic-growth':normal[1]['n']/normal[0]['n'],'dynamic-shock-growth':stress[1]['n']/stress[0]['n'],'dynamic-investment-gaps':tuple(normal[t]['i']-stress[t]['i'] for t in (1,2)),'dynamic-unlevered-cash-gap':un[1]['n']-us[1]['n'],
      'e2-i':e2[0],'e2-k':e2[1],'e2-q':e2[2],'e2-cap-q':qcase(2,F(1,100))[2],
      'e4-reward':e4['floor'],'e4-pledge':e4['pledge'],'e4-n':e4['threshold'],
      'e5-surplus':F(4,5)*180-F(11,10)*(100+8),'e5-debt':F(11,10)*(100+8-5)/F(4,5),
      'e6-i':e6['i'],'e6-b':e6['b'],'e6-wealth':e6['wealth'],'e6-threshold':e6['threshold'],
      'e8-interval':e8[2],'e8-face':e8[3],'e9-growth':low[1]['n']/low[0]['n'],'e9-cash':tuple(low[t]['n'] for t in (1,2)),
      'e10-normal-output':normal[1]['total'],'e10-stress-output':stress[1]['total'],'e11-i':relax[0]['i'],'e11-b':relax[0]['b'],'e11-equity':relax[0]['E'],'e11-cash':relax[0]['retained']}
    need(set(doc.mark)==set(results),'all displayed markers independently reconstructed')
    for k,v in results.items():
        try:near(parsed(doc.mark[k]),v)
        except ValueError as e:raise ValueError(k+': '+str(e)) from e
    need(len(doc.rows)==9 and doc.rows[0]==['Path and quantity','Round0','Round1','Round2'],'table structure')
    j=1
    for name,rows in (('Normal',normal),('Stressed',stress)):
        for label,key in (('initial cash','n'),('investment','i'),('loan','b'),('owner dividend','dividend')):
            cells=doc.rows[j];need(cells[0]==name+' '+label and len(cells)==4,'table quantity and dates');near(tuple(parsed(c) for c in cells[1:]),tuple(r[key] for r in rows));j+=1
    # Exact scalar objective differences certify interior and both investment boundaries.
    for a,cap in ((3,2),(2,2),(2,F(1,100)),(1,2),(3,F(1,5))):
        i,k,marg,avg=qcase(a,cap);grad=marg-1-2*i
        need((i==0 and grad<=0) or (i==cap and grad>=0) or (0<i<cap and grad==0),'investment KKT signs')
        def objective(x):
            kt=F(9,10)+x;return -x-x*x+(a*kt-kt*kt/2)/F(21,20)
        for x in (F(0),F(cap)/3,F(cap),i):need(objective(x)<=objective(i),'global scalar optimum');comparisons+=1
    # Two-period exact tangent cancellation uses explicit future-capital derivatives.
    beta=F(20,21);d=F(9,10);i0,i1=F(1,3),F(1,4);k1=d+i0;k2=d*k1+i1
    q1=beta*(3-k2);q0=beta*(2-k1+d*q1)
    direct=( -1-2*i0+beta*(2-k1)+beta**2*d*(3-k2), beta*(-1-2*i1)+beta**2*(3-k2))
    near(direct,(q0-1-2*i0,beta*(q1-1-2*i1)))
    def two(x,y):
        a=d+x;b=d*a+y;return -x-x*x+beta*(2*a-a*a/2-y-y*y)+beta**2*(3*b-b*b/2)
    for x,y in product((F(0),F(1,2),F(2)),repeat=2):need(two(x,y)-two(i0,i1)<=direct[0]*(x-i0)+direct[1]*(y-i1),'concavity tangent');comparisons+=1
    # Contract budgets, incentives, participation, changed reward and exact tie boundary.
    near(F(4,5)*(ag['debt']+ag['y']),144);near(F(4,5)*ag['y']-11,ag['surplus']);near(e4['slack'],F(-3,2))
    tie=agency(n=ag['threshold']);near(tie['slack'],0);need(agency(n=5)['slack']<0 and F(2,5)*180+20<110,'low wealth exclusion');comparisons+=1
    monitoring_debt=results['e5-debt'];near(F(4,5)*(180-monitoring_debt)-F(11,10)*5,results['e5-surplus'])
    # Feasibility and clipped optimum, including zero pledge, zero cash and unconstrained regions.
    for theta,n in ((0,0),(0,1),(F(1,5),0),(F(1,5),F(12,5)),(F(1,2),0),(F(3,4),0),(F(1,5),10)):
        c=collateral(4,theta,n);need(c['i']<=float(n)+float(theta)*c['output']+1e-10,'collateral feasibility');comparisons+=1
        for x in (0,c['cap']/2,c['cap']):need(4*sqrt(x)-x<=c['output']-c['i']+1e-10,'collateral global optimum');comparisons+=1
    eps=F(1,1000000);cp=collateral(4,F(1,5),F(1,5)+eps);cm=collateral(4,F(1,5),F(1,5)-eps)
    near((cp['i']-cm['i'])/float(2*eps),di,1e-8);near((cp['wealth']-cm['wealth'])/float(2*eps),1+mu,1e-8)
    for args in ((80,100,15,25),(80,100,15,20),(120,100,15,25),(80,0,15,25)):
        o=overhang(*args);near(o[1]-o[0],o[4])
    for z in (20,25):
        o=overhang(80,100,15,z)
        for face in (o[2][0],o[3],o[2][1]):need(face>=80 and 80+z-face-15>=0,'inclusive bargaining domain');comparisons+=1
    # Every branch of the finite shock tree, not just displayed normal/stressed histories.
    for As in product((F(11,10),F(6,5)),repeat=3):
        rows=path(As)
        for t,r in enumerate(rows):
            near(r['i'],r['n']+r['b']);near(r['b'],F(1,2)*r['i']);near(r['E']+r['nextW'],r['total']);near(r['dividend']+r['retained'],r['E']);near(r['nextW'],10)
            need(r['b']<=F(441,400) and r['output']>r['repay'],'all-history funding and repayment');comparisons+=1
        near(rows[-1]['retained'],0);near(rows[-1]['dividend'],rows[-1]['E'])
    near(normal[2]['n']-stress[2]['n'],(normal[1]['n']-stress[1]['n'])*F(21,20))
    alternate=path((F(6,5),)*3,R=F(19,20),lam=F(1,4),s=F(1,2));near(alternate[2]['nextW'],10*F(19,20)**3)
    invalid=[(num,(True,)),(num,(float('inf'),)),(parsed,('1/0',)),(parsed,('sum((1,2))',)),(qcase,(3,-1)),(qcase,(3,2,0)),(qcase,(3,2,1,2)),
      (agency,(100,180,.4,.8,20,1,10)),(agency,(100,180,.8,.4,100,1,10)),(agency,(100,180,.8,.4,20,1,101)),(agency,(100,180,.8,.4,20,1,-1)),
      (collateral,(0,.2,1)),(collateral,(4,1,1)),(collateral,(4,.2,-1)),(overhang,(80,100,-1,25)),
      (path,((),)),(path,((1,),)),(path,((1.2,),0)),(path,((1.2,),1,10,1,1)),(path,((1.2,),1,10,1,.5,0)),(path,((1.2,),1,10,1,.99))]
    for fn,args in invalid:
        try:fn(*args)
        except (ValueError,OverflowError):rejects+=1
        else:raise ValueError('invalid domain accepted '+fn.__name__)
    summary=dict(chapter='v14-c08',status='passed',review='separate peer',comparisons=comparisons,domain_rejections=rejects,worked_cases=5,solved_exercises=12,result_markers=len(results),table_cells=24,shock_histories=8,runtime_files=6,scope='Independent original-objective and exact-contract reconstruction; collateral bisection; finite all-history goods/funding and terminal audit. No author code executed.')
    json.dumps(summary,allow_nan=False);return summary

if __name__=='__main__':check()
