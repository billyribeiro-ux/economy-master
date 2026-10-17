"""Original exact vertex and transaction audit for the C08 manuscript."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v18-c08.html','scripts/check_v18_c08.py','content/reviews/v18-c08-sources.json','content/reviews/v18-c08-author.json')
def require(x,msg):
    if not x:raise ValueError('C08 author: '+msg)
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
def vertices(constraints):
    points=set()
    for i,(a,b,c) in enumerate(constraints):
        for d,e,f in constraints[i+1:]:
            determinant=a*e-b*d
            if determinant:
                x=(c*e-b*f)/determinant;y=(a*f-c*d)/determinant
                if all(u*x+v*y<=w for u,v,w in constraints):points.add((x,y))
    return sorted(points)
def optimize(constraints,objective,maximize):
    points=vertices(constraints)
    if not points:return None,()
    values=[sum(a*b for a,b in zip(point,objective)) for point in points];value=(max if maximize else min)(values)
    return value,tuple(p for p,v in zip(points,values) if v==value)
def growth(data,books):
    C,N,D,E,w,loss,cf,ef,cap=exact(data,9);require(min(C,N,D,E,w,loss,cf,ef,cap)>=0 and C+N==D+E and w<=D and loss<=N,'growth domain');require(len(books)==2,'two books')
    (a,p),(b,q)=(exact(x,2) for x in books);require(0<=a<=1 and 0<=b<=1 and min(p,q)>=0,'book rates')
    constraints=tuple(tuple(map(Q,row)) for row in ((-1,0,0),(0,-1,0),(1,0,cap),(0,1,cap),(1,1,C-w-cf),(a,b,E-loss-ef)))
    value,points=optimize(constraints,(p,q),True)
    return value,points,constraints
def growth_ledger(data,books,x,y):
    C,N,D,E,w,loss,cf,ef,cap=map(Q,data);a,p=books[0];b,q=books[1];z=x+y
    rows=[(C,N,D,E),(C,N+z,D+z,E),(C-z,N+z,D,E),(C-z-w,N+z,D-w,E),(C-z-w,N+z-loss-a*x-b*y,D-w,E-loss-a*x-b*y)]
    return rows

def funding(data,capital=True):
    C,S,N,D,E,w,loss,cf,ef,cap,d,f,h=exact(data,13);require(min(C,S,N,D,E,w,loss,cf,ef,cap)>=0 and C+S+N==D+E and w<=D and loss<=N,'funding amounts');require(0<=d<1 and 0<=f<1 and 0<=h<=1,'funding rates')
    constraints=[(-1,0,0),(0,-1,0),(1,0,S),(0,1,cap),(1-h,1,(1-h)*S),(-(1-d),-(1-f),C-w-cf)]
    if capital:constraints.append((d,f,E-loss-ef))
    constraints=tuple(tuple(map(Q,row)) for row in constraints);value,points=optimize(constraints,(d,f),False)
    return value,points,constraints

def funding_ledger(data,s,b):
    C,S,N,D,E,w,loss,cf,ef,cap,d,f,h=map(Q,data)
    rows=[(C,S,N,D,0,E)]
    # Loan loss, security sale, borrowing principal, cash fee, runoff in order.
    deltas=((0,0,-loss,0,0,-loss),((1-d)*s,-s,0,0,0,-d*s),(b,0,0,0,b,0),(-f*b,0,0,0,0,-f*b),(-w,0,0,-w,0,0))
    for delta in deltas:rows.append(tuple(a+x for a,x in zip(rows[-1],delta)))
    return rows

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];review=strict((root/FILES[3]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'manual review');require(set(review['payloads'])==set(FILES[:3]),'three bindings')
    for name,d in review['payloads'].items():
        b=(root/name).read_bytes();require(d=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze '+name)
    sources=strict((root/FILES[2]).read_text())['sources'];p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment');require(p.tasks==p.answers==['v18-c08-e'+str(i) for i in range(1,9)],'eight paired solutions');require(p.worked==['v18-c08-case1','v18-c08-case2'],'two cases');require(set(p.sources)=={(s['id'],s['url']) for s in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,value):eq(read('result',key),value,key)
    def gcalc(data,books):
        value,points,constraints=growth(data,books);require(len(points)==1,'unique growth solution');x,y=points[0];rows=growth_ledger(data,books,x,y)
        for C,N,D,E in rows:eq(C+N,D+E,'growth stage identity')
        C,N,D,E=rows[-1];eq(C>=data[6] and E>=data[7],True,'growth floors');return (x,y,value),(C,N,D,E,C+N)
    def fcalc(data):
        value,points,constraints=funding(data);require(len(points)==1,'unique funding solution');s,b=points[0];rows=funding_ledger(data,s,b)
        for C,S,N,D,B,E in rows:eq(C+S+N,D+B+E,'funding stage identity')
        C,S,N,D,B,E=rows[-1];eq(C>=data[7] and E>=data[8],True,'funding floors');eq(b<=(1-data[12])*(data[1]-s),True,'disjoint collateral');return (s,b,value,(1-data[12])*(data[1]-s)),(C,S,N,D,B,E,C+S+N)
    data=read('input','growth');books=read('input','books');out,ledger=gcalc(data,books);result('growth-optimum',out);result('growth-ledger',ledger);eq(ledger[3]/ledger[-1],Q(13,188),'book ratio')
    result('pay',(Q(9,10)-Q(3,10),(Q(9,10)-Q(3,10))/10))
    changed=list(data);changed[5]=Q(5);out,ledger=gcalc(changed,books);result('growth-loss-optimum',out);result('growth-loss-change',ledger)
    changed=list(data);changed[6]=Q(9);out,ledger=gcalc(changed,books);result('growth-floor-optimum',out+(out[2]-Q(3,2),));result('growth-floor-change',ledger)
    fdata=read('input','funding');out,ledger=fcalc(fdata);result('funding-optimum',out);result('funding-ledger',ledger)
    C,S,N,D,B,E,total=ledger
    repay=(C+25-B,N-25,Q(0),E,total-B);result('repayment',repay);eq(repay[0]+S+repay[1],D+E,'repayment balance')
    collection=Q(15);short=fdata[7]-(C+collection-B);eq(short,5,'repayment shortfall');result('repayment-equity',(C+collection-B+short,N-collection,0,E+short,total-B+short))
    changed=list(fdata);changed[9]=Q(10);out,ledger=fcalc(changed);result('funding-cap-change',out);result('funding-cap-ledger',ledger)
    changed=list(fdata);changed[10]=Q(1,5);cost,points,_=funding(changed,False);eq(len(points),1,'cash-only unique solution');s,b=points[0];equity=fdata[4]-fdata[6]-cost;result('funding-discount-change',(s,b,cost,equity,fdata[8]-equity));eq(funding(changed)[:2],(None,()),'capital cash joint infeasible')
    changed=list(fdata);changed[10]=Q(9,50);out,ledger=fcalc(changed);eq(out[:3],(20,20,4),'discount boundary');eq(ledger[5],10,'capital at boundary')
    changed=list(fdata);changed[5]=Q(56);a,al=fcalc(changed);changed[5]=Q(57);cost,points,_=funding(changed,False);s,b=points[0];result('retention',(a[0],a[2],al[5],s,cost,changed[4]-changed[6]-cost));eq(funding(changed)[:2],(None,()),'runoff boundary failure')
    growth_worlds=0
    for existing,cf,cap in product((Q(3),Q(4),Q(5)),(Q(9),Q(10),Q(12)),(Q(8),Q(12))):
        d=list(data);d[5]=existing;d[6]=cf;d[8]=cap;value,points,cons=growth(d,books)
        require(points,'growth witness feasible')
        for x,y in points:
            eq(all(a*x+b*y<=c for a,b,c in cons),True,'growth feasible vertex')
            eq(value,Q(2,25)*x+Q(3,25)*y,'growth objective')
            # Upper bounds from combinations of actual constraints; select the sharp certificate.
            bounds=(Q(3,50)*(d[0]-d[4]-cf)+Q(1,5)*(d[3]-existing-d[7]),Q(1,25)*cap+Q(2,5)*(d[3]-existing-d[7]),Q(1,5)*cap,Q(2,25)*(d[0]-d[4]-cf)+Q(1,25)*cap)
            eq(value<=min(bounds),True,'independent analytical upper bounds')
        growth_worlds+=1
    funding_worlds=0
    for discount,borrowcap,runoff in product((Q(1,10),Q(9,50),Q(1,5)),(Q(0),Q(10),Q(20)),(Q(35),Q(40),Q(56))):
        d=list(fdata);d[10]=discount;d[9]=borrowcap;d[5]=runoff;value,points,cons=funding(d);gap=d[7]-d[0]+runoff
        # These worlds all need positive sales; full cap meets collateral, so direct cash elimination is independent certificate.
        s=(gap-(1-d[11])*borrowcap)/(1-discount);cost=discount*s+d[11]*borrowcap;eq(s>=0 and borrowcap<=(1-d[12])*(d[1]-s),True,'certificate applicability')
        if cost>d[4]-d[6]-d[8]:eq((value,points),(None,()),'infeasible analytical loss budget')
        else:
            eq(value,cost,'vertex versus eliminated cash certificate');eq(points,((s,borrowcap),),'unique exact funding allocation')
        funding_worlds+=1
    # Equal-cost funding creates multiple minimizers; no required proceeds makes the zero plan feasible.
    d=list(fdata);d[11]=d[10];value,points,_=funding(d);eq(value,4,'equal-ratio cost');eq(len(points)>1,True,'nonunique boundary');d=list(fdata);d[5]=0;value,points,_=funding(d);eq((value,points),(0,((Q(0),Q(0)),)),'no proceeds needed')
    d=list(data);d[5]=Q(8);eq(growth(d,books)[:2],(None,()),'existing losses exceed floor capacity')
    invalid=0
    bad=[]
    for i,v in ((0,-1),(3,21),(4,181),(5,171),(6,-1)):
        d=list(data);d[i]=v;bad.append(lambda d=d:growth(d,books))
    for i,v in ((10,1),(11,-1),(12,2),(6,109),(5,181)):
        d=list(fdata);d[i]=v;bad.append(lambda d=d:funding(d))
    bad += [lambda:growth(data,((Q(2),Q(1)),books[1])),lambda:exact((True,),1),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":Infinity}'),lambda:rational('f()')]
    for f in bad:
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid domain accepted')
    require(used==set(marks),'all numerical markers consumed')
    return {'chapter':'v18-c08','status':'passed','runtime_files':4,'comparisons':count,'growth_worlds':growth_worlds,'funding_worlds':funding_worlds,'invalid_domains':invalid,'scope':'Full original committee/control/compensation/reporting artifacts and eight complete solutions manually read; vertex oracle and transaction ledgers independently recomputed.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage checker [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
