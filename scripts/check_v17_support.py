"""V17 support independent author arithmetic/structure gates; full prose audit separate."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from itertools import combinations
import ast,json
FILES=('content/assessments/parts/v17-support-opening.html','content/assessments/parts/v17-support-closing.html','scripts/check_v17_support.py','content/reviews/v17-support-sources.json','content/reviews/v17-support-author.json')
def require(ok, message):
    if not ok:
        raise ValueError(message)

def number(text):
    def walk(n):
        if isinstance(n, ast.Constant) and type(n.value) is int: return F(n.value)
        if isinstance(n, (ast.Tuple, ast.List)): return tuple(walk(x) for x in n.elts)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -walk(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div): return walk(n.left)/walk(n.right)
        raise ValueError('numeric grammar')
    return walk(ast.parse(text, mode='eval').body)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__();self.inputs={};self.results={};self.active=None;self.ids=[];self.points={};self.solutions=[];self.sources={}
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if 'data-points' in d:self.points[d['id']]=int(d['data-points'])
        if 'data-solution-for' in d:self.solutions.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d['href']
        for key,target in [('data-input',self.inputs),('data-result',self.results)]:
            if key in d:
                require(d[key] not in target,'duplicate marker');target[d[key]]='';self.active=(target,d[key])
    def handle_data(self,text):
        if self.active:self.active[0][self.active[1]]+=text
    def handle_endtag(self,tag):
        if tag=='span':self.active=None

def bounds(n,known,total,low,high):
    require(n>0 and 0<=known<=n and low<=high and known*low<=total<=known*high,'score domain')
    return (total+(n-known)*low)/n,(total+(n-known)*high)/n

def conditional(n,defaults,hit,false):
    require(n>0 and 0<defaults<=n and 0<=hit<=defaults and 0<=false<=n-defaults and hit+false>0,'cohort domain')
    return hit/defaults,hit/(hit+false)

def present(cost,receipt,r):
    require(cost>=0 and r>-1,'PV domain');p=receipt/(1+r);return p,p-cost

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    rec=json.loads((root/FILES[4]).read_text());require(set(rec['payloads'])==set(FILES[:4]),'four nonself hashes')
    for name,v in rec['payloads'].items():
        raw=(root/name).read_bytes();require(len(raw)==v['bytes'] and sha256(raw).hexdigest()==v['sha256'],'changed '+name)
    reader=Reader()
    for name in FILES[:2]:reader.feed((root/name).read_text())
    i={k:number(v) for k,v in reader.inputs.items()};o={k:number(v) for k,v in reader.results.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    expected={**{f'v17-d{n}':5 for n in range(1,9)},**{f'v17-o{n}':4 for n in range(1,6)},**{f'v17-r{n}':8 for n in range(1,6)}}
    eq(reader.points,expected,'18 prompt weights');eq(set(reader.solutions),set(expected),'18 exact answers');eq(len(reader.solutions),18,'no repeated solutions');eq(len(reader.ids),len(set(reader.ids)),'unique IDs');eq(reader.sources,{s['id']:s['url'] for s in json.loads((root/FILES[3]).read_text())['sources']},'scoped source link')
    a,z,p0,p1=i['d1'];g=z/a-1;infl=p1/p0-1;real=(z/p1)/(a/p0)-1;approx=g-infl;eq((g,infl,real,approx,real-approx),o['d1'],'exact real growth')
    cost,receipt,r,cash,floor=i['d2'];pv,npv=present(cost,receipt,r);eq((pv,npv,cash-cost,floor-(cash-cost)),o['d2'],'value cash')
    n,d,hit,false=i['d3'];eq((d-hit,n-d-false,hit+false,n-hit-false,*conditional(n,d,hit,false)),o['d3'],'cohort')
    eq((F(2),F(4)*2-F(2)**2-5,F(0)),o['d4'],'outside option')
    (pre,post),(cp,cpost)=i['d5'];counter=pre+cpost-cp;eq(((post-pre)-(cpost-cp),counter,post-counter,post,F(0)),o['d5'],'DID worlds')
    n,k,total,lo,hi,prior=i['d6'];bb=bounds(n,k,total,lo,hi);eq((*bb,*(x-prior for x in bb)),o['d6'],'missing scores')
    eq((F(10,110),F(10,100)),o['d7'],'denominator correction');cap,*hours=i['d8'];eq((sum(hours),sum(hours)-cap,F(10),F(12),F(8),F(10),F(40)),o['d8'],'scope budget')
    a,z,p0,p1=i['o1'];eq((z/p1)/(a/p0)-1,o['o1'],'oral real');eq((F(40),F(-4),F(-4)*10/40,F(2),F(60),F(-4)*5/60),o['o2'],'response grading and transfer')
    treatment,control=i['o3'];ate=sum(a-b for a,b in zip(treatment,control))/4;contrasts=[]
    for chosen in combinations(range(4),2):contrasts.append(sum(treatment[j] for j in chosen)/2-sum(control[j] for j in range(4) if j not in chosen)/2)
    eq((contrasts[0],ate,sum(contrasts)/6),o['o3'],'six assignment expectation');eq((F(4),F(32),F(-1),F(0),F(4),F(1)),o['o4'],'capacity global entry')
    eq((*present(*i['r1']),*present(F(70),F(77),F(1,10))),o['r1'],'new assessment');eq((F(520,60),F(6),F(8),F(36),F(35),F(1)),o['r2'],'course compression and transfer')
    n,scores,lo,hi=i['r3'];bb=bounds(n,F(len(scores)),sum(scores),lo,hi);passed=sum(s>=3 for s in scores);eq((sum(scores)/len(scores),*bb,F(passed)/n,F(passed+n-len(scores))/n),o['r3'],'denominator audit')
    (good,bad),(low,high)=i['r4'];value=lambda p:p*good+(1-p)*bad;threshold=-bad/(good-bad);eq((threshold,value(low),value(high),max(0,value(low),value(high)),max(0,-value(low),-value(high))),o['r4'],'criterion-sensitive choice')
    eq((*present(F(70),F(88),F(1,10)),F(80)-70,F(20),F(6)),o['r5'],'new counterexample and plan')
    for q in [F(n,4) for n in range(17)]:
        eq(12*q-q*q,36-(q-6)**2,'capacity square identity');eq(12*q-q*q<=32,True,'global feasible bound')
    for n in (2,6,10):
        for known in range(n+1):
            for score in (F(0),F(2),F(4)):
                low,high=bounds(F(n),F(known),known*score,F(0),F(4));eq(low,F(known)*score/n,'all missing zero');eq(high,(known*score+(n-known)*4)/n,'all missing four')
    for p in [F(j,20) for j in range(5,16)]:eq(value(p)>=F(-3,2) and value(p)<=F(15,2),True,'range endpoints')
    invalid=[lambda:bounds(F(0),F(0),F(0),F(0),F(4)),lambda:bounds(F(4),F(5),F(0),F(0),F(4)),lambda:bounds(F(4),F(2),F(9),F(0),F(4)),lambda:bounds(F(4),F(2),F(0),F(4),F(0)),lambda:conditional(F(0),F(0),F(0),F(0)),lambda:conditional(F(10),F(0),F(0),F(1)),lambda:conditional(F(10),F(2),F(3),F(0)),lambda:conditional(F(10),F(2),F(1),F(9)),lambda:conditional(F(10),F(2),F(0),F(0)),lambda:present(F(10),F(20),F(-1)),lambda:present(F(-1),F(20),F(0))]
    for f in invalid:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid input accepted')
    return {'volume':'v17','component':'support','status':'passed','runtime_files':5,'prompts':18,'numeric_results':len(o),'comparisons':count,'random_assignments':6,'invalid_domains':len(invalid),'scope':'Full diagnostic/oral/retention prompts, complete answers/rubrics and all12chapter map manually read; actual human observation remains required.'}
if __name__=='__main__':check()
