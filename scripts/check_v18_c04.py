"""Exact four-file author audit of hiring evidence and conditional economic models."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v18-c04.html','scripts/check_v18_c04.py','content/reviews/v18-c04-sources.json','content/reviews/v18-c04-author.json')
def require(x,msg):
    if not x:raise ValueError('C04 author: '+msg)
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
def attrition(data,u=None,v=None):
    p,a,r,b,lo,hi=exact(data,6);require(0<p<=1 and 0<r<=1 and lo<hi and lo<=a<=hi and lo<=b<=hi,'attrition domain')
    levels=tuple(p*a+(1-p)*x-r*b-(1-r)*y for x,y in product((lo,hi),repeat=2))
    if u is None:return a-b,min(levels),max(levels)
    u,v=exact((u,v),2);require(lo<=u<=hi and lo<=v<=hi,'missing mean support')
    t=p*a+(1-p)*u;c=r*b+(1-r)*v;return t,c,t-c

def moments(states):
    require(isinstance(states,tuple) and len(states)==2,'two state vectors');r,h=states;r=exact(r,len(r));h=exact(h,len(h));require(len(r)==len(h) and len(r)>0,'matched nonempty states');n=len(r);mr=sum(r)/n;mh=sum(h)/n;vr=sum((x-mr)**2 for x in r)/n;vh=sum((x-mh)**2 for x in h)/n;cov=sum((x-mr)*(y-mh) for x,y in zip(r,h))/n;return mr,mh,vr,vh,cov

def hedge(states,cash):
    opening,floor,margin,cap=exact(cash,4);require(opening>=0 and floor>=0 and margin>0 and cap>=0,'cash domain');mr,mh,vr,vh,cov=moments(states)
    if opening<floor:return {'feasible':False}
    limit=min(cap,(opening-floor)/margin);candidates={Q(0),limit}
    if vh and 0<=cov/vh<=limit:candidates.add(cov/vh)
    def risk(q):
        gains=tuple(x-q*y for x,y in zip(*states));m=sum(gains)/len(gains);return sum((x-m)**2 for x in gains)/len(gains)
    best=min(candidates,key=risk);bestvalue=risk(best);optimal=tuple(sorted(x for x in candidates if risk(x)==bestvalue));unique=vh>0 or limit==0
    return {'feasible':True,'h':best,'variance':bestvalue,'cash':opening-margin*best,'unique':unique,'optimal_interval':(optimal[0],optimal[-1])}

def ratings(rows):
    require(isinstance(rows,tuple) and rows,'rating rows');out=[]
    for row in rows:
        row=exact(row,3);require(all(0<=x<=4 and x.denominator==1 for x in row),'rating bounds');out.append(sum(row))
    return tuple(out)

def funnel(rows):
    result=[]
    for row in rows:
        n,s,a=exact(row,3);require(n>0 and 0<s<=n and 0<=a<=s and all(x.denominator==1 for x in (n,s,a)),'funnel domain');result.append((s/n,a/s,a/n))
    return tuple(x for i in range(3) for x in (result[0][i],result[1][i]))

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];review=strict((root/FILES[3]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'qualitative review');require(set(review['payloads'])==set(FILES[:3]),'three bindings')
    for name,d in review['payloads'].items():
        b=(root/name).read_bytes();require(d=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze '+name)
    p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment');require(p.tasks==p.answers==['v18-c04-e'+str(i) for i in range(1,9)],'eight answers');require(p.worked==['v18-c04-case1','v18-c04-case2'],'two complete cases');sources=strict((root/FILES[2]).read_text())['sources'];require(set(p.sources)=={(x['id'],x['url']) for x in sources},'source routes')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,value):eq(read('result',key),value,key)
    data=read('input','attrition');result('bounds',attrition(data));eqbounds=tuple(attrition(data,m,m)[2] for m in (data[4],data[5]));result('equal-missing-bounds',(min(eqbounds),max(eqbounds)));result('missing-means-example',attrition(data,4,8));changed=(Q(1,2),data[1],Q(1,2),data[3],data[4],data[5]);result('equal-retention-bounds',attrition(changed)[1:]);eq(attrition(changed,8,8)[2],1,'equal missing cancellation')
    r1,r2,calibrated=read('input','ratings');initial=tuple((x+y)/2 for x,y in zip(ratings(r1),ratings(r2)));result('initial-totals',initial);result('calibrated-totals',ratings(calibrated));eq(tuple(row[1]>=3 for row in calibrated),(False,True,True),'identification gate')
    for html,left,right,final,mean in zip(p.tables['v18-c04-academic-scores'][1:],r1,r2,calibrated,initial):
        eq(rational(html[1]),left,'rater1 table');eq(rational(html[2]),right,'rater2 table');eq(rational(html[3]),mean,'mean table');vector,total=html[4].split(' / ');eq(rational(vector),final,'calibrated table');eq(rational(total),sum(final),'total table')
    for w in (Q(0),Q(1,2),Q(1),Q(2)):
        scores=tuple(q+i+w*c for q,i,c in calibrated);eq(scores[1]-scores[2],w,'weight sensitivity')
    states=read('input','hedge-states');cash=read('input','cash');mo=moments(states);result('moments',mo);best=hedge(states,cash);h0=mo[4]/mo[3];unrisk=mo[2]-2*h0*mo[4]+h0*h0*mo[3];result('hedge-optimum',(h0,unrisk,best['h'],best['variance'],best['cash']));result('residuals',tuple(x-best['h']*y for x,y in zip(*states)));eq(cash[0]-cash[2]*h0,4,'unconstrained cash violation')
    finance=read('input','finance-ratings');result('finance-totals',ratings(finance));result('funnel-rates',funnel(read('input','funnel')))
    scenarios=tuple(hedge(states,(C,*cash[1:])) for C in (11,8));result('cash-changes',tuple((x['h'],x['variance'],x['cash']) for x in scenarios));eq(hedge(states,(4,*cash[1:]))['feasible'],False,'below-floor infeasibility')
    new=(states[0],tuple(x/2 for x in states[1]));mm=moments(new);opt=hedge(new,cash);result('changed-hedge',(mm[4],mm[3],mm[4]/mm[3],opt['h'],opt['variance']));late=hedge(states,(9,*cash[1:]));result('retention',(attrition(data,8,8)[2],late['h'],late['variance'],late['cash']))
    worlds=0
    for r,s in product((Q(1,4),Q(1,2),Q(1)),repeat=2):
        d=(r,8,s,6,0,10);gap,lo,hi=attrition(d)
        for u,v in product((0,5,10),repeat=2):eq(lo<=attrition(d,u,v)[2]<=hi,True,'support-bound witness')
        eq(attrition(d,0,10)[2],lo,'sharp lower');eq(attrition(d,10,0)[2],hi,'sharp upper');worlds+=1
    hedge_worlds=0
    for h in (states[1],tuple(-x for x in states[1]),new[1],(Q(1),)*4):
        st=(states[0],h)
        for opening in (4,5,8,9,10,11,14):
            out=hedge(st,(opening,*cash[1:]));hedge_worlds+=1
            if not out['feasible']:eq(opening<cash[1],True,'true empty feasible set');continue
            limit=min(cash[3],(opening-cash[1])/cash[2]);mr,mh,vr,vh,cov=moments(st)
            for j in range(5):
                q=limit*Q(j,4);risk=vr-2*q*cov+q*q*vh;eq(out['variance']<=risk,True,'global risk witness')
            eq(out['unique'],vh>0 or limit==0,'variance-zero uniqueness boundary')
    invalid=0
    for f in (lambda:attrition((0,8,Q(1,2),6,0,10)),lambda:attrition((2,8,Q(1,2),6,0,10)),lambda:attrition((Q(1,2),11,Q(1,2),6,0,10)),lambda:attrition(data,-1,0),lambda:hedge(states,(10,5,0,3)),lambda:hedge(states,(10,-1,3,3)),lambda:hedge(states,(10,5,3,-1)),lambda:moments(((1,2),(1,))),lambda:ratings(((5,0,1),)),lambda:funnel(((0,0,0),(1,1,0))),lambda:exact((True,),1),lambda:strict('{"x":NaN}')):
        try:f()
        except (ValueError,TypeError,ZeroDivisionError):invalid+=1
        else:raise ValueError('invalid accepted')
    require(used==set(marks),'all markers checked')
    return {'chapter':'v18-c04','status':'passed','runtime_files':4,'comparisons':count,'attrition_worlds':worlds,'hedge_worlds':hedge_worlds,'invalid_domains':invalid,'scope':'Full two role/candidate/calibration/decision/development cases, eight complete solutions, global proofs and source limits separately read.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage checker [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
