"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v17-c09.html','scripts/check_v17_c09.py','content/reviews/v17-c09-sources.json','content/reviews/v17-c09-author.json','scripts/check_v17_c09_peer.py','content/reviews/v17-c09-peer.json')
def require(x,msg):
    if not x:raise ValueError('C09 peer: '+msg)
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
        if t=='table':self.table=a['id'];self.tables[self.table]=[]
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
def wage(data):
    a,b,c,d,s,t=exact(data,6);require(min(a,b,c,d)>0 and 0<=s<=1 and 0<=t<=1,'positive wage/share domain')
    mean0=s*a+(1-s)*b;mean1=t*c+(1-t)*d;fixed=s*c+(1-s)*d
    within=s*(c-a)+(1-s)*(d-b);composition=(t-s)*(c-d);alternative=t*(c-a)+(1-t)*(d-b);old=(t-s)*(a-b);interaction=(t-s)*((c-a)-(d-b))
    return (mean0,mean1,fixed,(mean1-mean0)/mean0,(fixed-mean0)/mean0,within,composition,alternative,old,interaction)
def firm(data):
    a,b,k,f=exact(data,4);require(a>=0 and b>0 and k>0 and f>=0,'firm domain')
    # Candidate set reconstructed from derivative sign and feasible endpoints.
    candidates={Q(0),k}
    if 0<a/b<k:candidates.add(a/b)
    gross=lambda q:a*q-b*q*q/2
    scale=max(candidates,key=gross);surplus=gross(scale);net=surplus-f
    payoff=lambda q:Q(0) if q==0 else gross(q)-f
    maximum=max(map(payoff,candidates));choices=tuple(sorted(q for q in candidates if payoff(q)==maximum))
    return scale,surplus,net,choices,maximum

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    review=strict((root/FILES[5]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'manual review');require(set(review['payloads'])==set(FILES[:5]),'five bindings')
    for name,d in review['payloads'].items():
        b=(root/name).read_bytes();require(d=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze '+name)
    author=strict((root/FILES[3]).read_text());sources=strict((root/FILES[2]).read_text())['sources'];require(not author['open_material_findings'],'author unresolved finding')
    p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'unique complete fragment');require(p.tasks==p.answers==['v17-c09-ex'+str(i) for i in range(1,9)],'all paired answers');require(p.worked==['v17-c09-case1','v17-c09-case2'],'complete cases');require(set(p.sources)=={(s['id'],s['url']) for s in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:comparisons+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,value):eq(read('result',key),value,key)
    data=read('input','wages');w=wage(data);result('wage-means',w[:5]);result('decomposition',(w[5],w[6],w[1]-w[0]));result('alternative-decomposition',(w[7],w[8],w[1]-w[0]));eq(w[9],Q(6,5),'interaction')
    table=p.tables['v17-c09-wages'][1:];a,b,c,d,s,t=data;eq(tuple(tuple(rational(x) for x in row[1:]) for row in table),((a,c,s,t),(b,d,1-s,1-t)),'actual input table')
    wt=read('input','wage-transfer');v=wage(wt);result('wage-transfer',v[1:5]+(v[5],v[6],v[1]-v[0]));z=wage(wt[:5]+(wt[4],));eq((z[1],z[3],z[6]),(Q(122,5),Q(1,60),0),'followup fixed shares')
    delay=wage((20,40,20,40,Q(4,5),Q(1,2)));result('delayed-wages',(delay[0],delay[1],delay[3],delay[5],delay[6]));eq((w[5]/w[0],w[6]/w[0]),(Q(1,10),Q(11,20)),'percentage contributions')
    base=read('input','firm');a,b,k,f=base;cases=(base,(a,b,k,Q(9)),(a,b,k,Q(10)),(a,b,Q(2),f));result('firm-cases',tuple(v for x in cases for v in firm(x)[:3]));eq(tuple(firm(x)[3] for x in cases),((Q(3),),(Q(0),Q(3)),(Q(0),),(Q(2),)),'global choices')
    transfer=read('input','firm-transfer');result('firm-transfer',firm(transfer)[:3]);eq(firm(transfer)[3],(Q(0),),'transfer nonentry')
    ex=read('input','firm-exercise');exc=tuple(ex[:3]+(ex[3]+j,) for j in range(3));result('firm-exercise',tuple(v for x in exc for v in firm(x)[:3]));eq(tuple(firm(x)[3] for x in exc),((Q(3),),(Q(0),Q(3)),(Q(0),)),'capacity global solutions')
    re=read('input','firm-retention');a,b,k,f=re;half=k/2;result('firm-retention',firm(re)[:3]+(a*half-b*half*half/2-f,));eq(firm(re)[3],(Q(0),Q(1)),'retention tie');eq(6*Q(3,2)-Q(3,2)**2-9,Q(-9,4),'tie midpoint');eq(firm((0,2,4,0))[3],(Q(0),),'zero demand boundary');eq(sum((2,2,2,2)),8,'rubric')
    wage_worlds=0
    for s,t in product((Q(0),Q(1,3),Q(1)),repeat=2):
        for values in ((2,5,3,4),(5,5,6,6),(3,7,3,7)):
            z=wage(values+(s,t));eq(z[5]+z[6],z[1]-z[0],'identity');eq(z[7]+z[8],z[1]-z[0],'alternative identity');eq(z[7]-z[5],z[9],'interaction allocation');eq(z[6]-z[8],z[9],'composition allocation');wage_worlds+=1
    firm_worlds=0
    for a,b,k in product((0,2,6),(1,2),(1,3)):
        q,S,_,_,_=firm((a,b,k,0))
        for f in sorted({Q(0),S,S+1}):
            scale,gross,net,choices,value=firm((a,b,k,f));qstar=min(Q(k),Q(a,b));eq(scale,qstar,'global operating candidate');eq(gross,Q(a)*qstar-Q(b)*qstar*qstar/2,'gross exact');eq(choices,(Q(0),) if a==0 or net<0 else ((Q(0),qstar) if net==0 else (qstar,)),'global outside comparison')
            for j in range(1,9):
                q=Q(k)*Q(j,8);g=Q(a)*q-Q(b)*q*q/2;eq(g<=gross,True,'global gross witness');eq(g-f<=value,True,'full payoff witness')
            # Strict gross increase at positive a, and weak scale increase, from old optimum argument.
            if a>0:
                upper=firm((a+1,b,k,f));eq(upper[1]>gross,True,'strict surplus comparative static');eq(upper[0]>=scale,True,'weak scale comparative static')
            firm_worlds+=1
    invalid=0
    bad=(lambda:wage((20,40,22,44,-1,0)),lambda:wage((20,40,22,44,0,2)),lambda:wage((0,40,22,44,0,0)),lambda:firm((-1,2,4,5)),lambda:firm((1,0,4,5)),lambda:firm((1,2,0,5)),lambda:firm((1,2,4,-1)),lambda:exact((True,),1),lambda:rational('open("x")'),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"x":NaN}'))
    for f in bad:
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid input accepted')
    require(set(marks)==used,'all marked quantities consumed')
    return {'chapter':'v17-c09','status':'passed','runtime_files':6,'numeric_results':sum(k[0]=='result' for k in marks),'comparisons':comparisons,'wage_worlds':wage_worlds,'firm_worlds':firm_worlds,'invalid_domains':invalid,'scope':'Full manuscript, two agreements/feedback/revisions, proofs, eight solutions/rubric and bounded source records independently read; author checker opaque.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage peer [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
