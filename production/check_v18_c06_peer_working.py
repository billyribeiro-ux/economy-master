"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('production/v18-c06-working.html','production/check_v18_c06_working.py','production/v18-c06-sources-working.json','production/v18-c06-author-review-working.json','production/check_v18_c06_peer_working.py','production/v18-c06-peer-review-working.json')
def require(x,msg):
    if not x:raise ValueError('C06 peer: '+msg)
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
def vote(total,excluded,present,yes,quorum):
    values=(total,excluded,present,yes,quorum);require(all(type(x) is int and x>=0 for x in values),'integer vote domain');require(excluded<=total and present<=total-excluded and yes<=present and quorum>0,'vote consistency');eligible=total-excluded
    # Find the smallest integer affirmative count satisfying the strict inequality.
    required=next(y for y in range(eligible+2) if 2*y>eligible)
    return eligible,required,present>=quorum and yes>=required

def present_cost(stream,rate):
    stream=exact(stream,len(stream));rate,=exact((rate,),1);require(len(stream)>0 and min(stream)>=0 and rate>=0,'cost domain');T=len(stream)-1
    future=sum(amount*(1+rate)**(T-date) for date,amount in enumerate(stream));return future/(1+rate)**T

def means(T,C,omitted=()):
    T=exact(T,len(T));C=exact(C,len(C));require(T and C and all(x in (0,1) for x in T+C),'binary study domain');require(all(type(i) is int and 0<=i<len(T) for i in omitted) and len(set(omitted))==len(omitted),'omission IDs')
    retained=tuple(x for i,x in enumerate(T) if i not in omitted);require(retained,'empty retained group');mt=sum(T)/len(T);mc=sum(C)/len(C);filtered=sum(retained)/len(retained)
    return mt,mc,mt-mc,filtered,filtered-mc,filtered-mt

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];review=strict((root/FILES[5]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'manual review');require(set(review['payloads'])==set(FILES[:5]),'five bindings')
    for name,d in review['payloads'].items():
        b=(root/name).read_bytes();require(d=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze '+name)
    author=strict((root/FILES[3]).read_text());sources=strict((root/FILES[2]).read_text())['sources'];require(not author['open_material_findings'],'author findings')
    p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment');require(p.tasks==p.answers==['v18-c06-e'+str(i) for i in range(1,9)],'eight paired solutions');require(p.worked==['v18-c06-case1','v18-c06-case2'],'two cases');require(set(p.sources)=={(s['id'],s['url']) for s in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,v):eq(read('result',key),v,key)
    rows=p.tables['v18-c06-academic-board'][1:];require([r[0] for r in rows]==list('ABCDEFG'),'complete trustee roster');excluded=sum(r[2]=='Discloses, leaves' for r in rows);present=sum(r[2]=='Present' for r in rows);yes=sum(r[3]=='Yes' for r in rows);eligible,required,passed=vote(len(rows),excluded,present,yes,4);eq(passed,True,'academic base internal rule');result('academic-vote',(len(rows),excluded,eligible,present,yes,required))
    e,r,ok=vote(7,2,4,3,4);eq(ok,True,'G absent');e2,r2,ok2=vote(7,2,3,3,4);eq(ok2,False,'F G absent');result('e1',(e,r,4,3,3,3));eq(vote(7,2,4,2,4)[2],False,'retention quorum passes approval fails')
    cash,committed,reserve,independent,related=read('input','academic-budget');ceiling=cash-committed-reserve;result('academic-budget-result',(ceiling,cash-committed-independent,cash-committed-related,independent-related));result('e2',(cash-committed-23,reserve-(cash-committed-23),23-20));eq(independent,3+17,'independent scope components')
    T,C=read('input','study');summary=means(T,C,(3,4,5));result('study-summary',summary);single=means(T,C,(3,));result('e3',(single[3],single[4],single[5]));eq(len(T)+len(C),12,'twelve original records')
    rows=p.tables['v18-c06-finance-board'][1:];require([r[0] for r in rows]==list('ABCDEFG'),'complete director roster');ex=sum('recused' in r[1] for r in rows);pr=sum('present' in r[1] for r in rows);initial=sum(r[2]=='Yes' for r in rows);later=sum(r[3]=='Yes' for r in rows);e,r,first=vote(7,ex,pr,initial,4);eq(first,False,'initial internal vote');eq(vote(7,ex,pr,later,4)[2],True,'later internal vote');result('financial-votes',(e,pr,4,r,initial,later));eq(vote(7,3,3,3,4)[2],False,'three attendees cannot satisfy four');result('e5',(r,initial,later,3));ne,nr,ok=vote(7,4,3,3,4);eq(ok,False,'new relationship');result('e7',(ne,nr,ne,4))
    (rp,rm),(np,nm)=read('input','vendors');rate=Q(1,10);R=present_cost((rp,rm,rm),rate);N=present_cost((np,nm,nm),rate);result('vendor-costs',(R,N,R-N,60-rp,60-np));revised=present_cost((39,rm,rm),rate);threshold=N-present_cost((0,rm,rm),rate);result('revised-vendor',(revised,N-revised,threshold,21));eq(present_cost((threshold,rm,rm),rate),N,'global price tie');eq(threshold<50,True,'economic ceiling tighter than cash');hidden=present_cost((39,rm+1,rm),rate);result('e6',(threshold,hidden,hidden-N));ret=present_cost((38,rm+1,rm),rate);result('retention',(2,3,ret,N-ret,22))
    # Strict majority and quorum tested independently over both actual eligible rosters and a new singleton/empty roster.
    vote_worlds=0
    for total,ex in ((7,2),(7,3),(7,4),(1,0),(1,1)):
        for present in range(total-ex+1):
            for yes in range(present+1):
                eligible,required,ok=vote(total,ex,present,yes,4)
                eq(required,eligible//2+1,'minimum integer majority');eq(ok,present>=4 and 2*yes>eligible,'separate gates');eq(required*2>eligible and 2*(required-1)<=eligible,True,'minimality proof witness');vote_worlds+=1
    omission_worlds=0
    # Every nonempty retained subset, not only the convenient failed-outcome deletions.
    for bits in product((0,1),repeat=len(T)):
        if not any(bits):continue
        omitted=tuple(i for i,b in enumerate(bits) if not b);out=means(T,C,omitted);den=sum(bits);num=sum(value for value,b in zip(T,bits) if b)
        eq(out[3],num/den,'retained numerator/denominator');eq(out[5],out[4]-out[2],'distortion identity');eq(0<=out[3]<=1,True,'binary support');omission_worlds+=1
    eq(means(T,C,(0,))[5]<0,True,'dropping a success reverses distortion')
    valuation_worlds=0
    for rate in (Q(0),Q(1,10),Q(1,2)):
        benchmark=present_cost((np,nm,nm),rate);bound=benchmark-present_cost((0,rm,rm),rate)
        for price in (Q(0),bound-Q(1,100),bound,bound+Q(1,100),Q(50)):
            cost=present_cost((price,rm,rm),rate);eq(cost-benchmark,price-bound,'affine global proof');eq(cost<=benchmark,price<=bound,'global economic screen');eq(60-price>=10,price<=50,'immediate cash');eq(present_cost((price,rm+1,rm),rate)-cost,1/(1+rate),'dated extra fee');valuation_worlds+=1
    invalid=0
    for f in (lambda:vote(7,8,0,0,4),lambda:vote(7,2,6,3,4),lambda:vote(7,2,4,5,4),lambda:vote(7,2,4,3,0),lambda:vote(True,0,1,1,1),lambda:present_cost((1,-1),0),lambda:present_cost((1,2),-1),lambda:means((),C),lambda:means(T,C,(6,)),lambda:means(T,C,(0,0)),lambda:means(T,C,tuple(range(6))),lambda:means((2,),C),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":NaN}'),lambda:rational('x()')):
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid accepted')
    require(used==set(marks),'all numerical markers consumed')
    return {'chapter':'v18-c06','status':'passed','runtime_files':6,'comparisons':count,'vote_worlds':vote_worlds,'retained_record_worlds':omission_worlds,'valuation_worlds':valuation_worlds,'invalid_domains':invalid,'scope':'Both full governance artifacts/eight answers/proofs and jurisdiction-dated source limits independently reviewed; author checker opaque.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage peer [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
