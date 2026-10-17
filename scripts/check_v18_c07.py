"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v18-c07.html','scripts/check_v18_c07.py','content/reviews/v18-c07-sources.json','content/reviews/v18-c07-author.json')
def require(x,msg):
    if not x:raise ValueError('C07 author: '+msg)
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
def cohort(inputs,share=Q(1,4)):
    T,fixed,floor,core,extra,ready,bridge,scholarship,budget=exact(inputs,9)
    require(min(T,fixed,floor,extra,ready,bridge,scholarship,budget)>=0 and core>0 and 0<=share<=1,'cohort domain')
    require(ready.denominator==bridge.denominator==1,'integer applicant counts')
    feasible=[]
    for a,b in product(range(int(ready)+1),range(int(bridge)+1)):
        n=a+b;instruction=fixed+core*n+extra*b;r=T-instruction
        if r>=floor and b>=share*n and scholarship*b<=budget:feasible.append((Q(n),r,Q(a),Q(b),instruction,scholarship*b,budget-scholarship*b))
    if not feasible:return None,()
    best=max((x[0],x[1]) for x in feasible);choices=tuple(x for x in feasible if x[:2]==best)
    return choices,tuple(feasible)
def draw_bound(E,worst=-Q(1,20),inflation=Q(1,50),fraction=Q(9,10)):
    E,worst,inflation,fraction=exact((E,worst,inflation,fraction),4)
    require(E>0 and worst>=-1 and inflation>-1 and 0<=fraction<=1,'pool domain')
    return E*(1+worst-fraction*(1+inflation))
def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    review=strict((root/FILES[3]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'author review')
    require(set(review['payloads'])==set(FILES[:3]),'three bindings')
    for name,d in review['payloads'].items():
        data=(root/name).read_bytes();require(d=={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},'freeze '+name)
    sources=strict((root/FILES[2]).read_text())['sources'];p=Reader();p.feed((root/FILES[0]).read_text());p.close()
    require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment')
    require(p.tasks==p.answers==['v18-c07-e'+str(i) for i in range(1,9)],'paired eight answers');require(p.worked==['v18-c07-case1','v18-c07-case2'],'two cases')
    require(set(p.sources)=={(x['id'],x['url']) for x in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,v):eq(read('result',key),v,key)
    inputs=read('input','cohort');eq(inputs,(100,20,40,Q(1,2),1,40,30,3,60),'cohort primitives')
    def selected(data,share=Q(1,4)):
        opt,allrows=cohort(data,share);require(opt is not None and len(opt)==1,'unique lexicographic solution');n,r,a,bridge,i,cash,left=opt[0];return (a,bridge,n,i,r,cash,left),allrows
    chosen,rows=selected(inputs);result('cohort-optimum',chosen)
    eq(tuple(sorted((v[3],v[1]) for v in rows if v[0]==52)),((13,41),(14,40)),'two size maximizers')
    eq(Q(53,2)+14>40,True,'rounded bound infeasible')
    lower=list(inputs);lower[2]=Q(39);more=list(inputs);more[0]=Q(101)
    x,_=selected(lower);y,_=selected(more);result('cohort-changes',((100,39,x[0],x[1],x[2],x[4]),(101,40,y[0],y[1],y[2],y[4])))
    result('e2',(x,y));tight=list(inputs);tight[8]=Q(36);z,_=selected(tight);result('e3',z)
    expanded=list(inputs);expanded[0]=Q(102);expanded[5]=Q(44);z,_=selected(expanded);result('e4',(102,z[0],z[1],z[2],z[3],z[4],z[5]))
    E,lab,center,gift,reserve,pi,q,worst=read('input','endowment');eq((E,lab,center,gift,reserve,pi,q,worst),(100,3,2,20,1,Q(1,50),Q(9,10),-Q(1,20)),'endowment primitives')
    rate=draw_bound(1,worst,pi,q);result('draw-rate',rate);base=draw_bound(E,worst,pi,q);donor=draw_bound(gift,worst,pi,q);available=base-lab+donor;gap=center-available
    result('gift-budget',(base,donor,base+donor,available,gap));minimum=(lab+center-base)/rate
    result('minimum-gift',(minimum,base-lab,rate*minimum,lab+center));result('e5',(gap,gap-reserve,minimum))
    eq(tuple(tuple(Q(v) for v in row[1:]) for row in p.tables['v18-c07-funding'][1:]),((E,base,lab,base-lab),(gift,donor,0,donor),(E+gift,base+donor,lab,available)),'separate fund table')
    smaller=Q(3,2);bridge=lab+smaller-base-donor;eq((bridge,reserve-bridge),(Q(33,50),Q(17,50)),'temporary smaller scope')
    first=E*(1+worst)-base;second=first*(1+worst)-base;target=q*E*(1+pi)**2;zero=first*(1+worst)
    result('two-period',(first,second,target,target-second,zero));result('e7',(target-second,target-zero))
    newrate=draw_bound(1,worst=-Q(1,25));newdraw=(E+gift)*newrate;negative=draw_bound(1,fraction=Q(19,20));result('e6',(newrate,newdraw,newdraw-lab-center,negative))
    ret,_=selected(inputs,Q(1,3));total=draw_bound(150);result('retention',(ret[0],ret[1],ret[2],ret[4],ret[5],ret[6],total,lab+center-total))
    cohort_worlds=0
    for T,floor,budget,share in product((99,100,101,102),(39,40),(36,60),(Q(1,4),Q(1,3))):
        data=(T,20,floor,Q(1,2),1,40,30,3,budget);opts,feasible=cohort(data,share);require(opts is not None,'nonempty test menu')
        best=opts[0]
        # Independent necessary upper bound for every enumerated row, including the optimal row.
        eq(best[0]<=(T-20-floor)/(Q(1,2)+share),True,'continuous global bound')
        for n,r,a,bridge,ins,cost,left in opts:
            eq(ins+r,T,'hours');eq(cost+left,budget,'scholarships');eq(n,a+bridge,'people');eq(n>=max(v[0] for v in feasible),True,'global first objective');eq(r>=max(v[1] for v in feasible if v[0]==n),True,'global secondary objective')
        cohort_worlds+=1
    funding_worlds=0
    for pool,w,inf,fraction in product((20,100,150),(-Q(1,20),-Q(1,25),Q(1,20)),(0,Q(1,50)),(Q(9,10),Q(19,20))):
        bound=draw_bound(pool,w,inf,fraction)
        for payout in (0,max(Q(0),bound),max(Q(0),bound)+1):eq(pool*(1+w)-payout>=fraction*pool*(1+inf),payout<=bound,'floor iff')
        if bound>=0:
            for r in (w,w+Q(1,10),w+Q(1,5)):eq(pool*(1+r)-bound>=fraction*pool*(1+inf),True,'worst scenario suffices')
        else:eq(pool*(1+w)<fraction*pool*(1+inf),True,'zero payout impossible')
        funding_worlds+=1
    empty=list(inputs);empty[0]=Q(10);eq(cohort(empty)[0],None,'empty cohort constraints')
    invalid=0
    badready=list(inputs);badready[5]=Q(3,2);badcore=list(inputs);badcore[3]=0
    for f in (lambda:cohort(badready),lambda:cohort(badcore),lambda:cohort(inputs,Q(5,4)),lambda:draw_bound(0),lambda:draw_bound(100,worst=-2),lambda:draw_bound(100,inflation=-1),lambda:draw_bound(100,fraction=2),lambda:exact((True,),1),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}'),lambda:rational('f()')):
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid domain accepted')
    require(used==set(marks),'all markers covered')
    return {'chapter':'v18-c07','status':'passed','runtime_files':4,'comparisons':count,'cohort_worlds':cohort_worlds,'funding_worlds':funding_worlds,'invalid_domains':invalid,'scope':'Complete original academic models, all eight full solutions, global integer and one-period spending proofs plus two-period counterexample; no real academic authority or outcome certified.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage author [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
