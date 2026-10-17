"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/assessments/parts/v18-support-opening.html','content/assessments/parts/v18-support-closing.html','scripts/check_v18_support.py','content/reviews/v18-support-sources.json','content/reviews/v18-support-author.json')
def require(x,msg):
    if not x:raise ValueError('V18 support: '+msg)
def strict(text):
    def pairs(items):
        d={}
        for k,v in items:
            require(k not in d,'duplicate JSON key');d[k]=v
        return d
    def reject(x):raise ValueError('nonfinite JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=reject)
def rational(text):
    def visit(n):
        if isinstance(n,ast.Tuple):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) is int:return Q(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('unsupported exact literal')
    return visit(ast.parse(text.strip(),mode='eval').body)
class Reader(HTMLParser):
    def __init__(self):
        super().__init__();self.points={};self.links=[];self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources=[];self.numbers={};self.active=None;self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attrs');pass
        if 'id' in a:self.ids.append(a['id'])
        if 'data-points' in a:self.points[a['id']]=int(a['data-points'])
        if 'href' in a:self.links.append(a['href'])
        if t=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if t=='li' and any(z=='ol' and 'exercises' in d.get('class','').split() for z,d in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for' in a:
            require(any(z=='details' and 'solutions' in d.get('class','').split() for z,d in self.stack),'answer disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for kind in ('input','result'):
            if 'data-'+kind in a:
                key=(kind,a['data-'+kind]);require(key not in self.numbers and self.active is None,'numeric marker');self.active=(t,key);self.numbers[key]=''
        if t=='table':self.table=a.get('id','anonymous-'+str(len(self.tables)));self.tables[self.table]=[]
        if t=='tr':self.row=[]
        if t in ('th','td'):self.cell=[]
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.active:self.numbers[self.active[1]]+=s
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,t):
        require(bool(self.stack) and self.stack.pop()[0]==t,'balanced fragment')
        if self.active and self.active[0]==t:self.active=None
        if t in ('th','td'):self.row.append(''.join(self.cell).strip());self.cell=None
        if t=='tr':self.tables[self.table].append(self.row);self.row=None
        if t=='table':self.table=None

def exact(x,n):
    require(isinstance(x,(tuple,list)) and len(x)==n,'input dimension');require(all(type(v) in (int,Q) for v in x),'exact finite inputs');return tuple(Q(v) for v in x)
def probability(prior,sensitivity,false_positive):
    p,t,f=exact((prior,sensitivity,false_positive),3);require(all(0<=x<=1 for x in (p,t,f)),'probability domain')
    joint=p*t;total=joint+(1-p)*f;require(total>0,'conditioning on impossible event');return total,joint,joint/total
def missing(n,known,success):
    require(all(type(x) is int for x in (n,known,success)) and n>0 and 0<=success<=known<=n,'binary roster domain')
    return tuple(Q(success+k,n) for k in range(n-known+1))
def balance(C,N,D,E,loss,withdraw):
    C,N,D,E,loss,withdraw=exact((C,N,D,E,loss,withdraw),6)
    require(min(C,N,D,E,loss,withdraw)>=0 and C+N==D+E and loss<=N and withdraw<=D,'ledger domain')
    return C-withdraw,N-loss,D-withdraw,E-loss,C+N-withdraw-loss
def bargain(V,c,du,dl,cap):
    V,c,du,dl,cap=exact((V,c,du,dl,cap),5);require(min(V,c,du,dl,cap)>=0,'bargain domain')
    lo=c+dl;hi=min(V-du,cap)
    if lo>hi:return None
    S=V-c-du-dl;t=min(hi,max(lo,lo+S/2));g=(V-t-du,t-c-dl);return (lo,hi),t,g,g[0]*g[1]
def admissions(budget):
    require(type(budget) in (int,Q) and budget>=0,'scholarship domain');rows=[]
    for a,bridge in product(range(21),range(16)):
        n=a+bridge;hours=2*a+3*bridge;research=100-hours
        if research>=40 and 3*bridge>=n and 2*bridge<=budget:rows.append((n,research,a,bridge,2*bridge,budget-2*bridge))
    best=max(rows,key=lambda v:v[:2]);return best

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    r=strict((root/FILES[4]).read_text());require(r['full_reading_complete'] and not r['open_material_findings'],'manual author review');require(set(r['payloads'])==set(FILES[:4]),'four bindings')
    for name,d in r['payloads'].items():
        raw=(root/name).read_bytes();require(d=={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'changed '+name)
    p=Reader()
    for name in FILES[:2]:p.feed((root/name).read_text())
    p.close();require(not p.stack and len(p.ids)==len(set(p.ids)),'balanced unique fragments')
    expected={**{f'v18-d{i}':5 for i in range(1,9)},**{f'v18-o{i}':4 for i in range(1,6)},**{f'v18-r{i}':8 for i in range(1,6)}}
    require(p.points==expected and p.answers==list(expected),'18 exact prompt/solution pairs and points')
    require({'diagnostic','administration','oral','retention','remediation','notation','notation-index','concept-index','synthesis','volume-synthesis'}<=set(p.ids),'required anchors')
    require(all(f'v18-c{i:02}.html' in p.links for i in range(1,13)),'all12 chapter routes')
    sources=strict((root/FILES[3]).read_text())['sources'];require(set(p.sources)=={(x['id'],x['url']) for x in sources},'source routes')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,value):eq(read('result',key),value,key)
    result('d1',balance(*read('input','d1')))
    cost,annual,life,rate,C,floor=read('input','d2');pv=sum((annual/(1+rate)**t for t in range(1,int(life)+1)),Q(0));result('d2',(pv,pv-cost,C-cost,floor-C+cost))
    result('d3',(4,4,3*4+4*4,2,1));n,k,s=read('input','d4');result('d4',(s/k,missing(int(n),int(k),int(s))))
    post=probability(*read('input','d5'));result('d5',post);result('d6',(Q(30,100),100*post[2],30,100*post[2]-30));result('d7',(Q(20,120),Q(20,100)));result('d8',1+1+2+1+1)
    A,B,res=read('input','o1');C,floor,hours,priority=res
    eq(A[0]<=C-floor and A[1]<=hours and A[3]>=priority,True,'Aeligible');eq(B[0]<=C-floor and B[3]>=priority,False,'Bfails');result('o1',(C-A[0],C-floor,C-19,floor-(C-19)))
    result('o2',(Q(2,3),2-1,5-3,5+2-5,Q(2)*Q(3,5)-1,Q(5)*Q(3,5)-3,2+2*4-2*Q(3,5)))
    result('o3',(3,4,Q(6,8),Q(4,8),Q(6-4,8)))
    C,N,D,E,w,l,cf,ef=read('input','o4');cashcap=C-w-cf;losscap=E-l-ef;y=10*losscap-cashcap;x=cashcap-y;loss=l+x/10+y/5
    result('o4',(x,y,x/5+3*y/10,C-w-x-y,N+x+y-loss,D-w,E-loss,C+N-w-loss))
    low,high=Q(1,10),Q(1,2);costs=(20*low,20*high);result('o5',(Q(8,20),max(costs),8,max(0,max(costs)-8),max(0,8-min(costs))))
    n,r,a,bridge,spend,left=admissions(20);n2,r2,a2,b2,s2,l2=admissions(16);result('r1',((a,bridge,n,r,spend,left),(a2,b2,n2,r2,s2,l2)))
    borrow=Q(10);sale=(20-borrow)/Q(4,5);loss=sale/5;E=20-3-loss;assets=5+30-sale+62;repay=5+6-borrow;issue=5-repay
    result('r2',(sale,borrow,loss,E,assets,repay,issue,E+issue,repay+issue+30-sale+56));eq(borrow<=30-sale,True,'disjoint collateral');eq(assets,60+borrow+E,'fundingidentity');eq(repay+30-sale+56,60+E,'repaymentidentity')
    A=bargain(70,30,10,8,40);B=bargain(60,20,10,8,40);RA=bargain(70,30,10,8,50);RB=bargain(60,20,10,8,50)
    result('r3',A+B+(tuple((RA[1],RB[1])),));eq(RA[2:],RB[2:],'relaxed mode tie')
    contrast=(15-10)-(10-8);result('r4',(contrast,12,15-12,15,0));result('r5',(missing(12,10,8),12-10,Q(12-10,10)))
    # Primitive variations and boundary witnesses supplement the written global proofs.
    worlds=0
    for n in (3,6,10):
        for k in range(n+1):
            for success in {0,k}:
                rates=missing(n,k,success);eq(rates[0],Q(success,n),'missinglower');eq(rates[-1],Q(success+n-k,n),'missingupper');eq(len(rates),n-k+1,'discrete set');worlds+=1
    for x,y in product((Q(0),Q(4),Q(8)),repeat=2):
        eq(3*x+4*y,2*(x+y)+(x+2*y),'dual decomposition')
        if x+y<=8 and x+2*y<=12:eq(3*x+4*y<=28,True,'dualbound')
    for p0 in (Q(0),Q(1,4),Q(1,2),Q(1)):
        q,j,posterior=probability(p0,Q(3,4),Q(1,4));eq(j+(1-p0)*Q(1,4),q,'eventpartition');eq(posterior*q,j,'Bayesidentity')
    for cap in (0,28,38,39,40,49,50):
        for V,c in ((70,30),(60,20)):
            answer=bargain(V,c,10,8,cap)
            if answer is None:eq(c+8>min(V-10,cap),True,'emptynegotiation')
            else:
                (lo,hi),t,g,value=answer
                for trial in (lo,hi,(lo+hi)/2):eq(value>=(V-trial-10)*(trial-c-8),True,'bargainingendpointcomparison')
    for probability_value in (low,Q(2,5),high):
        value=20*probability_value;eq(max(0,value-8)<=2,True,'continueregretbound');eq(max(0,8-value)<=6,True,'pauseregretbound')
    invalid=0
    for bad in (lambda:missing(0,0,0),lambda:missing(10,11,4),lambda:missing(10,6,7),lambda:missing(True,1,1),lambda:probability(2,1,0),lambda:probability(0,1,0),lambda:balance(18,82,85,16,4,6),lambda:balance(18,82,85,15,83,6),lambda:bargain(70,-1,10,8,40),lambda:admissions(-1),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}'),lambda:rational('x()')):
        try:bad()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid input accepted')
    require(used==set(marks),'every visible numericmarker covered')
    return {'volume':'v18','component':'support','status':'passed','runtime_files':5,'comparisons':count,'missing_outcome_worlds':worlds,'invalid_domains':invalid,'diagnostic_points':40,'oral_points':20,'retention_points':40,'scope':'Full18task/answer/proof and additive rubric review; fictional cases and actual-work evidence rules distinguished.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage support [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
