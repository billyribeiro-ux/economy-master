"""Independent support oracle. Author checker is opaque hashed data only."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
import math
import re

FILES=('content/assessments/parts/v16-support-opening.html','content/assessments/parts/v16-support-closing.html','scripts/check_v16_support.py','content/reviews/v16-support-sources.json','content/reviews/v16-support-author.json','scripts/check_v16_support_peer.py','content/reviews/v16-support-peer.json')
def require(ok,message):
    if not ok: raise ValueError(message)


def numeric(text):
    text=text.rsplit('=',1)[-1].strip().replace('−','-')
    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return F(str(node.value))
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('restricted rational syntax')
    return walk(ast.parse(text,mode='eval').body)


class BaseManuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.inputs={};self.results={};self.prompts={};self.solutions={};self.sources={};self.worked=[];self.rows=[];self.row=None;self.cell=None;self.links=set();self.guides=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        # Opening support owns the sole assembled assessment h1.
        for attr,dest in (('data-input',self.inputs),('data-check',self.results)):
            if attr in a:require(a[attr] not in dest,'duplicate marker');dest[a[attr]]=''
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in x.get('class','').split() for t,x in self.stack):self.prompts[a['id']]=''
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack),'solution disclosure')
            require(a['data-solution-for'] not in self.solutions,'unique solution');self.solutions[a['data-solution-for']]=''
        if 'data-source' in a:require(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if tag=='a':self.links.add(a['href'])
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.cell is not None:self.cell+=text
        for tag,a in self.stack:
            if 'data-input' in a:self.inputs[a['data-input']]+=text
            if 'data-check' in a:self.results[a['data-check']]+=text
            if tag=='li' and a.get('id') in self.prompts:self.prompts[a['id']]+=text
            if 'data-solution-for' in a:self.solutions[a['data-solution-for']]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting')
        if tag in ('td','th'):self.row.append(self.cell);self.cell=None
        if tag=='tr':self.rows.append(self.row);self.row=None
        self.stack.pop()


class Manuscript(BaseManuscript):
    def __init__(self):
        super().__init__();self.points={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='li' and 'data-points' in a:
            self.points[a['id']]=int(a['data-points']);self.prompts[a['id']]=''
        super().handle_starttag(tag,attrs)


def growth(start,end):
    require(start>0 and end>=0,'positive opening/nonnegative closing')
    return F(end-start,start)


def bank_summary(start,end):
    require(len(start)==len(end)>0,'matching nonempty stocks')
    rates=tuple(growth(a,b) for a,b in zip(start,end))
    return rates+(sum(rates,F(0))/len(rates),growth(sum(start),sum(end)))


def posterior(p,h,l):
    require(all(0<=x<=1 for x in (p,h,l)),'probabilities')
    yes=p*h+(1-p)*l;require(yes>0,'nonzero conditioning event')
    return yes,p*h/yes


def missing_bounds(share,mean,lo,hi):
    require(0<=share<=1 and lo<=mean<=hi,'bounded population domain')
    return share*mean+(1-share)*lo,share*mean+(1-share)*hi


def one_sided_bias(est,se,critical,B):
    require(se>0 and critical>0 and B>=0,'uncertainty domain')
    return est-critical*se-B,est+critical*se


def weighted(values,weights):
    require(len(values)==len(weights)>0 and all(w>=0 for w in weights) and sum(weights)==1,'weights')
    return sum((v*w for v,w in zip(values,weights)),F(0))


def numeric_audit(d):
    x={k:numeric(v) for k,v in d.inputs.items()};want={};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    want['d1']=bank_summary(x['d1-open'],x['d1-close'])
    t0,t1=x['d2-exposed'];c0,c1=x['d2-comparison'];change=c1-c0;D=t1-t0-change
    worlds=tuple((m,t1-m,m-t0-change) for m in (t0+change,t1))
    want['d2']=(D,)+sum(worlds,())
    for m,tau,b in worlds:eq(tau+b,D,'D=tau+b');eq(m+tau,t1,'same observed exposed after')
    want['d3']=posterior(*x['d3'])
    prompt=d.prompts['v16-d4'];a=F(re.search(r'B\(q\)=(\d+)q',prompt).group(1));c=F(1)
    q=(a-c)/2;price=c+q;S=lambda z:(a-c)*z-z*z
    want['d4']=(q,price,S(q),S(F(3)),S(q)-S(F(3)))
    for z in (F(0),F(3),q,F(9),F(100)):eq(S(z),S(q)-(z-q)**2,'global completed square')
    est,se,z=x['d5'];want['d5']=(est-z*se,est+z*se)
    want['d6']=missing_bounds(*x['d6'])
    share,observed,lo,hi=x['d6']
    for missing in (lo,(lo+hi)/2,hi):
        mean=share*observed+(1-share)*missing
        require(want['d6'][0]<=mean<=want['d6'][1],'sharp continuum witness');count+=1
        eq((mean-share*observed)/(1-share),missing,'interior inversion')
    start,end=x['d7'];want['d7']=(F(end-start,end),growth(start,end))
    capacity,checks,analysis,writing,review=x['d8'];short=checks+analysis+writing+review-capacity
    want['d8']=(sum(x['d8'][1:]),short,checks,analysis-short,writing,review)
    a,b,c=x['o2'];old,new=growth(a,b),growth(a,c);want['o2']=(old,new,100*(new-old))
    alpha,*p=x['o3'];want['o3']=(alpha/len(p),)+tuple(min(1,len(p)*v) for v in p)
    want['o4']=(weighted(x['o4-effects'],x['o4-source']),weighted(x['o4-effects'],x['o4-target']),weighted(x['o4-changed'],x['o4-target']))
    r1=d.prompts['v16-r1'];base=F(re.search(r'opening stocks (\d+) each',r1).group(1));ends=numeric(re.search(r'closing stocks (\([^)]*\))',r1).group(1))
    want['r1']=bank_summary((base,)*len(ends),ends)[-2:]
    a0,a1=x['r2-a'];b0,b1=(v/1000 for v in x['r2-b']);summary=bank_summary((a0,b0),(a1,b1))
    want['r2']=(a0+b0,a1+b1,summary[-1],summary[-2])
    sigma,delta,za,zp=x['r3'];require(sigma>0 and delta!=0,'planning domain');n=2*sigma*sigma*(za+zp)**2/(delta*delta);ceil=-(-n.numerator//n.denominator)
    capacity=F(re.search(r'Capacity is only (\d+)',d.prompts['v16-r3']).group(1));want['r3']=(n,ceil,2*ceil,2*ceil-capacity)
    est,se=x['r4'];bounds=(F(2,5),F(3,5));want['r4']=sum((one_sided_bias(est,se,F(49,25),B) for B in bounds),())
    for B in bounds:
        outer=one_sided_bias(est,se,F(49,25),B)
        for b in (F(0),B/2,B):
            interval=(est-b-F(49,25)*se,est-b+F(49,25)*se)
            require(outer[0]<=interval[0]<=interval[1]<=outer[1],'true-bias interval containment');count+=1
    solution=d.solutions['v16-r5'];hours=tuple(F(v) for v in re.findall(r'(\d+) to ',solution));require(len(hours)==5,'five actual budget allocations');want['r5']=hours+(sum(hours),)
    actual={k:numeric(v) for k,v in d.results.items()};eq(set(actual),set(want),'all16 numeric groups')
    for k,v in want.items():eq(actual[k],v,'actual displayed '+k)
    # Meaningful different primitives, scale/unit invariance and boundaries.
    for opening,closing in (((F(10),F(30)),(F(11),F(27))),((F(10),F(10)),(F(0),F(20)))):
        s=bank_summary(opening,closing);weights=tuple(v/sum(opening) for v in opening)
        eq(weighted(s[:-2],weights),s[-1],'general growth weights')
        eq(bank_summary(tuple(v*1000 for v in opening),tuple(v*1000 for v in closing)),s,'currency-scale invariance')
    eq(missing_bounds(F(1),F(4),F(0),F(8)),(F(4),F(4)),'fully observed')
    eq(missing_bounds(F(0),F(4),F(0),F(8)),(F(0),F(8)),'unobserved bound')
    eq(posterior(F(1,4),F(1),F(1)),(F(1),F(1,4)),'uninformative signal')
    eq(posterior(F(1,4),F(1),F(0)),(F(1,4),F(1)),'perfect positive specificity')
    # State-selective retention can change the positive-record posterior.
    eq(posterior(F(1,4),F(3,4)*F(1,2),F(1,4)),(F(9,32),F(1,3)),'retained signal counterexample')
    eq(one_sided_bias(F(1),F(1,2),F(2),F(0)),(F(0),F(2)),'zero-bias interval')
    bad=[lambda:growth(0,1),lambda:growth(1,-1),lambda:bank_summary((),()),lambda:posterior(F(2),F(1),F(0)),lambda:posterior(F(1,2),F(0),F(0)),lambda:missing_bounds(F(2),F(4),F(0),F(8)),lambda:missing_bounds(F(1,2),F(9),F(0),F(8)),lambda:one_sided_bias(F(1),F(0),F(2),F(0)),lambda:one_sided_bias(F(1),F(1),F(2),F(-1)),lambda:weighted((1,2),(F(1,4),F(1,4)))]
    for fn in bad:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid mathematical domain accepted')
    return count,len(bad),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={name:(root/name).read_bytes() for name in FILES};author=json.loads(raw[FILES[4]]);peer=json.loads(raw[FILES[6]])
    for record,names in ((author,FILES[:4]),(peer,FILES[:6])):
        require(set(record['payloads'])==set(names),'nonself freeze membership')
        for name,item in record['payloads'].items():require(item['bytes']==len(raw[name]) and item['sha256']==sha256(raw[name]).hexdigest(),'freeze '+name)
    d=Manuscript();d.feed(raw[FILES[0]].decode());d.feed(raw[FILES[1]].decode())
    require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique support')
    ids={f'v16-{kind}{i}' for kind,n in (('d',8),('o',5),('r',5)) for i in range(1,n+1)}
    require(set(d.prompts)==set(d.solutions)==set(d.points)==set(peer['exact_prompt_review'])==ids,'all18 full pairs')
    for k in ids:
        expected={'d':5,'o':4,'r':8}[k[4]];require(d.points[k]==expected,'prompt points')
        solution=d.solutions[k];match=re.search(r'Rubric \((\d+) points\)\.(.*)',solution);require(match is not None,'actual rubric')
        pieces=[int(n) for n in re.findall(r'\b(\d+)(?=[;.])',match.group(2))]
        require(int(match.group(1))==sum(pieces)==expected,'additive rubric')
        record=peer['exact_prompt_review'][k]
        require(record['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and record['solution_sha256']==sha256(solution.encode()).hexdigest(),'full reading freeze')
    require(all(f'v16-c{i:02}.html' in d.links for i in range(1,13)) and 'assessments.html#research-portfolio' in d.links,'all12chapter routes and capstone')
    src=json.loads(raw[FILES[3]]);require(src['actual_inspector']=='root' and d.sources=={s['id']:s['url'] for s in src['sources']},'source attribution/routes')
    require(peer['open_material_findings']==[],'no open findings')
    count,bad,groups=numeric_audit(d)
    return {'volume':'v16','component':'support','review':'independent-peer','status':'passed','runtime_files':7,'exact_pairs':18,'diagnostic_points':40,'oral_points':20,'retention_points':40,'numeric_groups':groups,'comparisons':count,'invalid_domain_rejections':bad,'scope':'Full eighteen prompts/solutions/rubrics and qualitative guides read; independent exact primitive oracle, no author checker execution or external human certification.'}

if __name__=='__main__':check()
