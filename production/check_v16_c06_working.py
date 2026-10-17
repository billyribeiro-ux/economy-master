"""Quiet, read-only exact-four-file audit of the original C06 models."""
import ast
import json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from pathlib import Path

FILES=('production/v16-c06-working.html','production/check_v16_c06_working.py','production/v16-c06-sources-working.json','production/v16-c06-author-review-working.json')
def need(ok,message):
    if not ok: raise ValueError(message)
def literal(text):
    def read(n):
        if isinstance(n,ast.Constant):
            need(type(n.value) is int,'integer literal');return F(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            den=read(n.right);need(den!=0,'nonzero denominator');return read(n.left)/den
        raise ValueError('numeric literal required')
    return read(ast.parse(text,mode='eval').body)
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.active=[];self.inputs={};self.results={};self.ids=[]
        self.cases=[];self.exercises=[];self.solutions=[];self.sources={};self.links=set()
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','fragment')
        if 'id' in a:
            need(a['id'].startswith('v16-c06-') and a['id'] not in self.ids,'unique prefixed ID');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and a.get('id','').startswith('v16-c06-ex'):
            need(any(x=='ol' and 'exercises' in y.get('class','').split() for x,y in self.stack),'exercise list');self.exercises.append(a['id'])
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in y.get('class','').split() for x,y in self.stack),'solution disclosure');self.solutions.append(a['data-solution-for'])
        if t=='a':self.links.add(a.get('href'))
        if 'data-source' in a:
            need(a['data-source'] not in self.sources,'source uniqueness');self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:
                k=a[attr];need(k not in d,'marker unique');d[k]='';self.active.append((d,k,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def domain(p):
    need(len(p)==5,'five primitives')
    need(all(type(v) in (int,F) for v in p),'exact rational primitives')
    a,b,c,g,d=map(F,p);need(a>=0 and c>=0 and d>=0 and b>0 and g>0,'model domain');return a,b,c,g,d
def allocation(p,conduct=1):
    a,b,c,g,d=domain(p);need(conduct in (1,2),'conduct multiplier')
    q=max(F(0),min((a-c)/(conduct*b),(a-c+g*d)/(conduct*b+g)))
    return q,a-b*q,max(q-d,0)
def alternative(p,h,k):
    a,b,c,g,d=domain(p);h=F(h);k=F(k);need(h>=c and k>0,'alternative domain')
    q,r,e=allocation(p)
    if a<=c:return a,F(0),F(0),F(0)
    if r<=h:return r,q,F(0),q
    r=(a-b*d+b*c/g+b*k*h)/(1+b/g+b*k)
    x=d+(r-c)/g;z=k*(r-h);return r,x,z,x+z
def surplus(q,p):
    a,b,c,g,d=domain(p);return (a-c)*q-b*q*q/2-g*max(q-d,0)**2/2

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]])
    bindings=review['payload_bindings'];need(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three nonself bindings')
    for b in bindings:
        v=raw[b['path']];need((len(v),sha256(v).hexdigest())==(b['bytes'],b['sha256']),'payload freeze')
    doc=Read();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'closed fragment')
    ex=['v16-c06-ex'+str(i) for i in range(1,11)]
    need(doc.exercises==doc.solutions==ex and set(review['exact_prompt_review'])==set(ex),'ten reviewed exact solutions')
    need(doc.cases==['v16-c06-case'+str(i) for i in range(1,4)],'three cases')
    need('v16-c05.html' in doc.links,'prerequisite')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==2,'scoped sources')
    inputs={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.results.items()}
    need(inputs=={'baseline':tuple(map(F,(10,1,2,1,2))),'alternative':(F(2),F(1)),'rival':(F(6),F(1,5),F(1),F(1),F(2))},'displayed primitives')
    comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:comparisons+=1;need(a==b,label)
    p=inputs['baseline'];a,b,c,g,d=p;q,r,e=allocation(p)
    B=a*q-b*q*q/2;C=c*q+g*e*e/2
    pre=alternative(p,*inputs['alternative']);post=alternative(p[:4]+(F(0),),*inputs['alternative'])
    qm,rm,em=allocation(p,2);profit=rm*qm-c*qm-g*em*em/2;bs=b*qm*qm/2
    expected={'baseline':(q,r,e),'accounts':(B,C,B-r*q,r*q-C,B-C),
              'capacity-rows':tuple(allocation(p[:4]+(F(v),)) for v in (0,8,10)),
              'alternative-before':pre,'alternative-after':post,
              'replacement-changes':tuple(post[i]-pre[i] for i in (1,2,3)),
              'replacement-slopes':(F(-1,3),F(2,3),F(-1,3),F(1,3)),
              'alternative-inactive':alternative(p,6,1),'monopoly':(qm,rm,em),
              'monopoly-accounts':(profit,bs,profit+bs,surplus(q,p)-surplus(qm,p)),
              'rival':allocation(inputs['rival'],2),'rival-slopes':(F(5,7),F(1,2))}
    need(set(shown)==set(expected),'every displayed result group')
    for k,v in expected.items():eq(shown[k],v,'display '+k)
    eq((b+g)*(q-qm)**2/2,surplus(q,p)-surplus(qm,p),'independent quadratic loss')
    eq(allocation((10,1,2,1,1))[:2],(F(9,2),F(11,2)),'exercise3 capacity')
    eq(allocation((9,1,2,1,2))[:2],(F(9,2),F(9,2)),'exercise3 demand')
    eq(allocation((10,1,2,3,2))[:2],(F(7,2),F(13,2)),'exercise4 friction')
    wrongr=F(16,3);eq((wrongr,2+(wrongr-2),wrongr-6,10-wrongr),(F(16,3),F(16,3),F(-2,3),F(14,3)),'exercise6 rejected active candidate');need(wrongr<6,'wrong branch diagnosed')
    # Independently find maxima from both closed quadratic pieces and their endpoints.
    # Then test supporting prices, global profit inequalities and conduct ordering.
    worlds=0
    for a,b,c,g,d in product(map(F,(1,2,10)),map(F,(1,2)),map(F,(1,2)),map(F,(1,3)),map(F,(0,2,8))):
        pp=(a,b,c,g,d);worlds+=1
        for conduct in (1,2):
            q,r,e=allocation(pp,conduct)
            score=lambda x:(a-c)*x-conduct*b*x*x/2-g*max(x-d,0)**2/2
            candidates={F(0),d,max(F(0),min(d,(a-c)/(conduct*b))),max(d,(a-c+g*d)/(conduct*b+g))}
            optimum=max(candidates,key=score);eq(q,optimum,'independent piecewise maximization')
            eq(e,max(q-d,0),'external funding identity')
            need(q>=0 and r>=0,'allocation feasibility')
            if conduct==1:
                price=c if a>c and q<=d else r
                eq(max((a-price)/b,0),q,'borrower optimum')
                if q>0:eq(price,c+g*e,'competitive marginal cost')
                else:need(a<=price<=c,'no-trade supporting price')
                for trial in (F(0),q/2,q,q+1,d):
                    need(price*q-c*q-g*e*e/2>=price*trial-c*trial-g*max(trial-d,0)**2/2,'global supplier optimum')
                    comparisons+=1
            else:
                need(q<=a/b,'nonnegative inverse demand')
                if q>0:eq(a-2*b*q,c+g*e,'monopoly marginal revenue')
        qc=allocation(pp)[0];qm=allocation(pp,2)[0]
        need(qm<qc if a>c else qm==qc==0,'conduct quantity comparison');comparisons+=1
        for h in (c,c+4):
            rr,x,z,qq=alternative(pp,h,1)
            eq(x+z,qq,'replacement clearing');eq(max((a-rr)/b,0),qq,'replacement demand');eq(z,max(rr-h,0),'alternative individual optimum')
            if x>d:eq(rr,c+g*(x-d),'incumbent active optimum')
            elif x>0:eq(rr,c,'incumbent flat supply')
            else:need(rr<=c,'incumbent corner')
    # Exact finite differences stay within specified branches; gamma uses rational difference quotient.
    eps=F(1,100)
    for pp,conduct in ((p,1),(p,2),(inputs['rival'],2)):
        a,b,c,g,d=pp;q,r,_=allocation(pp,conduct)
        changed=allocation((a,b,c,g,d+eps),conduct)
        eq((changed[0]-q)/eps,g/(conduct*b+g),'binding capacity derivative')
        eq((changed[1]-r)/eps,-b*g/(conduct*b+g),'binding price derivative')
    changed=alternative(p[:4]+(d+eps,),2,1)
    for i,slope in enumerate(expected['replacement-slopes']):eq((changed[i]-pre[i])/eps,slope,'replacement derivative')
    for delta in (F(1,10),F(1),F(3)):
        qg=allocation((10,1,2,1+delta,2))[0]
        eq((qg-q)/delta,F(-6,1)/((2+delta)*2),'gamma exact secant')
    for a in (F(1),F(2)):
        for price in (a,(a+2)/2,F(2)):
            eq(max(a-price,0),0,'zero-trade demand');need(price<=2,'zero-trade supply')
    bad=[(-1,1,2,1,2),(10,0,2,1,2),(10,-1,2,1,2),(10,1,-1,1,2),(10,1,2,0,2),(10,1,2,1,-1),(10,1,2,True,2),(10,1,2,1.0,2),(1,2)]
    rejected=0
    for pp in bad:
        try:allocation(pp)
        except ValueError:rejected+=1
        else:raise ValueError('invalid primitive accepted')
    for h,k in ((1,1),(2,0),(2,-1)):
        try:alternative(p,h,k)
        except ValueError:rejected+=1
        else:raise ValueError('invalid alternative domain accepted')
    for f,v in raw.items():need((root/f).read_bytes()==v,'unchanged runtime bytes')
    return {'chapter':'v16-c06','status':'passed','worked_cases':3,'solutions':10,'input_groups':len(inputs),'result_groups':len(shown),'comparisons':comparisons,'alternative_worlds':worlds,'rejected_inputs':rejected,'runtime_files':4,'qualitative_scope':'Full author reading recorded; independent acceptance pending.'}
if __name__=='__main__':check()
