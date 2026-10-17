"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v17-c12.html','scripts/check_v17_c12.py','content/reviews/v17-c12-sources.json','content/reviews/v17-c12-author.json','scripts/check_v17_c12_peer.py','content/reviews/v17-c12-peer.json')
def require(x,msg):
    if not x:raise ValueError('C12 peer: '+msg)
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
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources=[];self.numbers={};self.active=None;self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attrs');require(t!='h1','chapter h1')
        if 'id' in a:self.ids.append(a['id'])
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
def market(data):
    A,B,C,cap=exact(data,4);require(A>0 and B>0 and C>0 and 0<=cap<=A/B,'market domain')
    p=A/(B+C);q=C*p;actual=min(cap,p);qd=A-B*actual;qs=C*actual
    gross=A*qs/B-qs*qs/(2*B);cost=qs*qs/(2*C);cs=gross-actual*qs;ps=actual*qs-cost;benchmark=A*q/B-q*q/(2*B)-q*q/(2*C)
    return p,q,qd,qs,qd-qs,cs,ps,cs+ps,benchmark-cs-ps

def auction(v,m,b,alpha=Q(1,2),first=False):
    v,m,b,alpha=exact((v,m,b,alpha),4);require(min(v,m,b)>=0 and 0<=alpha<=1,'auction domain')
    probability=Q(1) if b>m else (alpha if b==m else Q(0));return probability*(v-(b if first else m))

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    review=strict((root/FILES[5]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'manual review');require(set(review['payloads'])==set(FILES[:5]),'five bindings')
    for name,d in review['payloads'].items():
        b=(root/name).read_bytes();require(d=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze '+name)
    author=strict((root/FILES[3]).read_text());sources=strict((root/FILES[2]).read_text())['sources'];require(not author['open_material_findings'],'author findings')
    p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment');require(p.tasks==p.answers==['v17-c12-e'+str(i) for i in range(1,9)],'eight paired solutions');require(p.worked==['v17-c12-case1','v17-c12-case2'],'two dossiers');require(set(p.sources)=={(s['id'],s['url']) for s in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,v):eq(read('result',key),v,key)
    data=read('input','market');m=market(data);result('ceiling',m);eq(m[:2],(25,50),'equilibrium')
    A,B,C,cap=data;start,end=Q(20),Q(60);gross=A*(end-start)/B-(end*end-start*start)/(2*B);quantity=end-start;revenue=cap*quantity;cost=quantity*quantity/(2*C);bench=m[7]+m[8]
    result('rationing',(gross,gross-revenue,revenue-cost,gross-cost,bench-gross+cost));eq(A/B-end/B,cap,'last rationed buyer voluntary');eq(quantity,m[3],'same quantity')
    changed=market((A,B,C,Q(15)));result('cap15',changed[3:]);unbound=market((A,B,C,Q(25)));eq((unbound[4],unbound[7],unbound[8]),(0,1250,0),'retention nonbinding')
    # Full response evidence is qualitatively read; reconstruct credit from the declared four criteria.
    rubric=(1,1,2,2);credit=((1,1,0,0),(1,1,2,2),(0,1,0,0),(0,0,0,0));scores=tuple(sum(row) for row in credit);result('exit-scores',scores);result('score-summary',(Q(sum(scores),3),Q(sum(scores),4),Q(sum(scores),4*sum(rubric)),Q(1,3),Q(1,4)));eq(sum(rubric),6,'full rubric')
    result('unit-hours',Q(3*50+3*120,60));result('seminar-hours',Q(2*90+2*180,60));result('revised-hours',Q(3*40+360,60));eq(tuple(map(sum,((5,10,15,10),(5,10,15,10),(5,10,15,10)))),(40,40,40),'revised session timing')
    v,m=read('input','auction');result('auction-witnesses',(auction(v,m,v),auction(v,m,5),auction(v,m,3),auction(v,8,v),auction(v,8,9),auction(v,v,v)));result('first-price',(auction(v,m,v,first=True),auction(v,m,5,first=True)));result('auction-transfer',(auction(5,7,5),auction(5,7,8),auction(5,7,7)))
    worlds=0
    for v,m,alpha in product((Q(0),Q(2),Q(6)),(Q(0),Q(4),Q(6),Q(8)),(Q(0),Q(1,2),Q(1))):
        truthful=auction(v,m,v,alpha)
        for b in sorted({Q(0),v,m,m+1,max(Q(0),m-1)}):eq(truthful>=auction(v,m,b,alpha),True,'exhaustive allocation witness')
        if v==m:eq(truthful,0,'equal value boundary')
        worlds+=1
    # Two complete-information equilibria, including every allocation-changing region and tie.
    for bids in ((5,4),(6,4)):
        for player,value in enumerate((6,4)):
            other=bids[1-player];own=bids[player];current=auction(value,other,own)
            for alt in (0,other-1,other,other+1,10):eq(auction(value,other,alt)<=current,True,'Nash witness')
    market_worlds=0
    for A,B,C in ((100,2,2),(60,1,2),(72,3,1)):
        A,B,C=map(Q,(A,B,C));pstar=A/(B+C)
        for f in (Q(0),Q(1,2),Q(1),Q(3,2)):
            cap=min(f*pstar,A/B);out=market((A,B,C,cap));q=out[3];missing=out[1]-q;gap=(A/B-q/B)-q/C
            eq(out[8],missing*gap/2,'triangle equals integral');eq(out[7]+out[8],A*out[1]/B-out[1]**2/(2*B)-out[1]**2/(2*C),'welfare reconciliation');eq(out[8]>=0,True,'nonnegative lost gains');market_worlds+=1
    invalid=0
    for f in (lambda:market((0,2,2,0)),lambda:market((100,0,2,20)),lambda:market((100,2,0,20)),lambda:market((100,2,2,-1)),lambda:market((100,2,2,51)),lambda:auction(-1,2,1),lambda:auction(1,2,-1),lambda:auction(1,2,1,2),lambda:exact((True,),1),lambda:strict('{"a":NaN}'),lambda:rational('x()')):
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid domain accepted')
    require(set(marks)==used,'all markers consumed')
    return {'chapter':'v17-c12','status':'passed','runtime_files':6,'comparisons':count,'auction_worlds':worlds,'market_worlds':market_worlds,'invalid_domains':invalid,'scope':'Both full dossiers, all eight solutions/rubrics/proofs and bounded source records independently read; author checker opaque.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage peer [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
