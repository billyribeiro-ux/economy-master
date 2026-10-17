"""Form B author audit: actual raw records, exact arithmetic and full score map."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import ast
import json
import math
import re

FILES=('content/assessments/parts/v16-exam-b.html','scripts/check_v16_exam_b.py','content/reviews/v16-exam-b-sources.json','content/reviews/v16-exam-b-author.json')
DOMAINS=('question_literature_judgment','reproduction_data_ethics','model_identification_design','robustness_writing','defense_portfolio')

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
        if tag=='h1':raise ValueError('chapter fragment cannot contain h1')
        for attr,dest in (('data-input',self.inputs),('data-result',self.results)):
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
            if 'data-result' in a:self.results[a['data-result']]+=text
            if tag=='li' and a.get('id') in self.prompts:self.prompts[a['id']]+=text
            if 'data-solution-for' in a:self.solutions[a['data-solution-for']]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting')
        if tag in ('td','th'):self.row.append(self.cell);self.cell=None
        if tag=='tr':self.rows.append(self.row);self.row=None
        self.stack.pop()


class Manuscript(BaseManuscript):
    def __init__(self):
        super().__init__();self.points={};self.domain={};self.rubrics={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='li' and 'data-points' in a:
            self.points[a['id']]=int(a['data-points'])
            self.domain[a['id']]=next(x['data-domain'] for t,x in reversed(self.stack) if 'data-domain' in x)
        if 'data-rubric-points' in a:
            target=next(x['data-solution-for'] for t,x in reversed(self.stack) if 'data-solution-for' in x)
            self.rubrics.setdefault(target,[]).append(int(a['data-rubric-points']))
        super().handle_starttag(tag,attrs)


def construct(deliveries):
    require(deliveries,'nonempty records');events={}
    for row in deliveries:
        event,bank,z,r,base,final=row
        require(type(z) is int and z in (0,1) and type(r) is int and r in (0,1),'binary assignment/receipt')
        require(type(base) is int and base>0 and (final is None or type(final) is int and final>=0),'balance domain')
        if event in events:require(events[event]==row,'conflicting duplicate')
        events[event]=row
    rows=list(events.values());require(len({r[1] for r in rows})==len(rows),'one event per bank')
    counts=[sum(r[2]==z for r in rows) for z in (0,1)]
    require(all(counts),'two nonempty arms')
    known={z:[int(r[5]>=r[4]) for r in rows if r[2]==z and r[5] is not None] for z in (0,1)}
    require(all(known.values()),'observed outcome in both arms')
    means={z:F(sum(v),len(v)) for z,v in known.items()}
    missing={z:counts[z]-len(known[z]) for z in (0,1)}
    full=[F(sum(known[1])+u,counts[1])-F(sum(known[0])+v,counts[0]) for u in range(missing[1]+1) for v in range(missing[0]+1)]
    return rows,known,means,counts,missing,tuple(full)


def optimum(a,c,k):
    require(all(isinstance(x,(int,F)) and not isinstance(x,bool) and x>=0 for x in (a,c,k)),'model primitives')
    return min(max(a-c,0),k)


def power(n,sigma,effect):
    require(type(n) is int and n>0 and sigma>0,'normal planning domain')
    se=float(sigma)*math.sqrt(2/n);u=float(effect)/se
    phi=lambda x:(1+math.erf(x/math.sqrt(2)))/2
    return se,phi(u-1.96)+phi(-u-1.96)


def weighted(effects,shares):
    require(len(effects)==len(shares) and shares and all(w>=0 for w in shares) and sum(shares)==1,'probability shares')
    return sum((e*w for e,w in zip(effects,shares)),F(0))


def numerical_audit(doc,text):
    inp={k:numeric(v) for k,v in doc.inputs.items()};rows=[]
    for row in doc.rows:
        if len(row)==6 and re.fullmatch('e[1-8]',row[0]):rows.append((row[0],row[1],int(row[2]),int(row[3]),int(row[4]),None if row[5]=='Unknown' else int(row[5])))
    unique,known,means,counts,missing,grid=construct(rows)
    rawmeans={z:F(sum(int(r[5]>=r[4]) for r in rows if r[2]==z and r[5] is not None),sum(r[2]==z and r[5] is not None for r in rows)) for z in (0,1)}
    gap=means[1]-means[0]
    oldfinal=int(re.search(r"Release 1 had the same rows except e6's final balance was (\d+)",text).group(1))
    old=[r[:-1]+(oldfinal,) if r[0]=='e6' else r for r in rows];oldmeans=construct(old)[2];oldgap=oldmeans[1]-oldmeans[0]
    takers=[int(r[5]>=r[4]) for r in unique if r[3]==1 and r[5] is not None];receipt=F(sum(takers),len(takers))-means[0]
    balances=[tuple(map(int,m)) for m in re.findall(r'credit changes from (\d+) to (\d+)',text)]
    require(len(balances)==4,'complete note P source balances')
    changes=tuple(sum(b-a for a,b in balances[j:j+2]) for j in (0,2))
    high,low,k0,k1=(inp[k] for k in ('model-high','model-low','cap-low','cap-high'))
    mh=(optimum(high,0,k0),optimum(high,0,k1));ml=(optimum(low,0,k0),optimum(low,0,k1))
    powers=tuple(power(int(n),inp['sigma'],inp['effect'])[1] for n in inp['sample-sizes'])
    critical=F(49,25);estimate,se,radius=(inp[k] for k in ('bias-estimate','bias-se','bias-radius'))
    effects=inp['stratum-effects'];source=weighted(effects,inp['source-shares']);target=weighted(effects,inp['target-shares'])
    overlap=inp['overlap-shares'];require(sum(overlap)==1 and len(overlap)==3,'overlap branch');base=sum(e*w for e,w in zip(effects,overlap[:2]));missingweight=overlap[-1]
    original=inp['original-agenda'];agenda=(original[0],F(0),original[2],F(25),original[3])
    expected={'p-total-changes':changes,'faulty-gap':rawmeans[1]-rawmeans[0],'complete-case':(means[1],means[0],gap),'record-counts':(len(rows),len(unique),sum(map(len,known.values()))),'missing-bounds':(min(grid),max(grid)),'missing-grid':grid,'version-gap':(oldgap,gap,gap-oldgap),'receipt-worlds':(F(0),F(1)),'cap-model':mh+ml+(mh[1]-mh[0],ml[1]-ml[0]),'power':powers,'adjusted-p':tuple(min(1,2*p) for p in inp['p-values']),'spec-display':(gap,F(sum(known[1]),counts[1])-F(sum(known[0]),counts[0]),receipt,rawmeans[1]-rawmeans[0]),'bias-interval':(estimate-critical*se-radius,estimate+critical*se+radius),'bias-threshold':estimate-critical*se,'transport':(source,target),'transport-bounds':(base-missingweight,base+missingweight),'exam-total':sum(inp['domain-scores']),'agenda':agenda}
    actual={k:numeric(v) for k,v in doc.results.items()};require(set(actual)==set(expected),'all displayed numeric groups');comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        require(a==b,label);comparisons+=1
    for k,value in expected.items():
        if k=='power':
            require(len(actual[k])==len(value) and all(abs(float(a)-b)<=F(1,100000000) for a,b in zip(actual[k],value)),'normal powers rounded8');comparisons+=2
        else:eq(actual[k],value,'displayed '+k)
    audit_rows={r[0]:r for r in doc.rows if r and r[0] in ('Available cases','Zero-filled roster','Attendees versus controls','Duplicate-weighted rows')}
    labels=('Available cases','Zero-filled roster','Attendees versus controls','Duplicate-weighted rows')
    require(set(audit_rows)==set(labels),'actual four-row audit table')
    for label,result in zip(labels,expected['spec-display']):
        row=audit_rows[label];eq(numeric(row[2]),result,'actual table contrast')
        left,right=row[1].split('−');eq(numeric(left)-numeric(right),result,'actual table group means')
    require(all(0<=p<=1 for p in inp['p-values']) and se>0 and radius>=0,'p-value and bias domains')
    for b in (-radius,F(0),radius):
        lower,upper=estimate-critical*se-b,estimate+critical*se-b
        require(expected['bias-interval'][0]<=lower<=upper<=expected['bias-interval'][1],'true-bias interval contained in union');comparisons+=1
    eq(counts,[4,4],'fixed arm denominators');eq(missing,{0:1,1:1},'one missing each');eq(sum(original),100,'original budget');eq(sum(agenda),100,'revised budget')
    eq(min(inp['domain-scores'])<15,True,'domain floor fails');eq(max(inp['sample-sizes'])*2,inp['capacity'],'planned roster fits');eq(powers[0]<.8<powers[1],True,'power target bracket')
    # Independent potential-outcome schedules: factual outcomes equal, effects differ.
    worlds=(((1,1),(0,0)),((0,1),(0,1)))
    for schedule,target_effect in zip(worlds,(0,1)):
        eq((schedule[0][1],schedule[1][0]),(1,0),'same observed receipt data')
        eq(sum(F(y1-y0,2) for y0,y1 in schedule),target_effect,'different causal averages')
    # Direct objective witnesses, including caps, kinks and zero-demand boundaries.
    modelcases=[(0,2,0),(0,2,3),(2,2,4),(6,0,3),(6,0,6),(6,0,9),(2,0,5)]
    for a,c,k in modelcases:
        q=optimum(a,c,k);obj=lambda x:(a-c)*x-F(x*x,2)
        for j in range(2*k+1):
            x=F(j,2);require(obj(q)>=obj(x),'global objective witness');comparisons+=1
    # Same financial amounts under positive common scaling preserve indicators.
    scaled=[r[:4]+(7*r[4],None if r[5] is None else 7*r[5]) for r in rows]
    eq(construct(scaled)[1:],construct(rows)[1:],'common-unit scaling')
    eq(construct(list(reversed(rows)))[2:],construct(rows)[2:],'delivery order')
    for u,v in product((0,1),repeat=2):
        completed=[r[:-1]+((r[4] if (u if r[2] else v) else 0),) if r[5] is None else r for r in unique]
        cmp=construct(completed)
        eq(cmp[2][1]-cmp[2][0],F(1+u-v,4),'attainable missingness endpoint/grid')
    eq(power(32,inp['sigma'],0)[1]>0.049 and power(32,inp['sigma'],0)[1]<0.051,True,'null power equals size')
    require(abs(power(32,inp['sigma'],-inp['effect'])[1]-powers[0])<1e-14,'two-sided sign symmetry');comparisons+=1
    eq(weighted((F(1,5),F(1,5)),(F(1,7),F(6,7))),F(1,5),'constant effect transport invariant')
    bad=[lambda:construct([]),lambda:construct(rows+[rows[0][:-1]+(13,)]),lambda:construct([rows[0][:2]+(2,)+rows[0][3:]]),lambda:construct([rows[0][:4]+(0,12)]),lambda:construct([rows[0][:-1]+(-1,)]),lambda:optimum(1,0,-1),lambda:optimum(True,0,2),lambda:power(0,F(1),F(1)),lambda:power(4,F(0),F(1)),lambda:weighted((1,2),(F(1,4),F(1,4)))]
    for fn in bad:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return comparisons,len(bad),len(expected)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=json.loads(raw[FILES[3]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for name,item in review['payloads'].items():require(item['bytes']==len(raw[name]) and item['sha256']==sha256(raw[name]).hexdigest(),'frozen '+name)
    text=raw[FILES[0]].decode();doc=Manuscript();doc.feed(text)
    require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'balanced unique fragment')
    ids={f'v16-exam-b-q{i:02}' for i in range(1,21)}
    require(set(doc.prompts)==set(doc.solutions)==set(doc.points)==ids,'twenty exact prompt solution pairs')
    require(all(doc.points[k]==5 and sum(doc.rubrics[k])==5 and len(doc.rubrics[k])==5 for k in ids),'additive five-point scoring')
    require(sum(doc.points.values())==100 and {d:sum(doc.points[k] for k in ids if doc.domain[k]==d) for d in DOMAINS}==dict.fromkeys(DOMAINS,20),'five20point domains')
    require(set(doc.ids)-{'form-b','solutions-b'} and all(k in ('form-b','solutions-b') or k.startswith('v16-exam-b-') for k in doc.ids),'anchor ownership')
    require({'form-b','solutions-b'}<=set(doc.ids),'assembly anchors')
    require(set(review['exact_prompt_review'])==ids and set(review['chapter_coverage'])=={f'v16-c{i:02}' for i in range(1,13)},'full author coverage/readings')
    for k in ids:
        x=review['exact_prompt_review'][k];require(x['prompt_sha256']==sha256(doc.prompts[k].encode()).hexdigest() and x['solution_sha256']==sha256(doc.solutions[k].encode()).hexdigest(),'exact reading freeze')
    sources=json.loads(raw[FILES[2]])['sources'];require(len(sources)==4 and doc.sources=={s['id']:s['url'] for s in sources},'four bounded source routes')
    require(all(s['actual_primary_inspector'] and s['inspection'] and s['limits'] for s in sources),'source scope/attribution')
    require(review['open_material_findings']==[],'no unresolved author findings')
    count,bad,groups=numerical_audit(doc,text)
    return {'volume':'v16','component':'exam_b','status':'passed','runtime_files':4,'prompts':20,'solutions':20,'points':100,'domains':5,'chapters_covered':12,'numeric_groups':groups,'comparisons':count,'invalid_domain_rejections':bad,'scope':'Actual audit artifacts and full qualitative answers reviewed separately; no actual research novelty, external learner assessment or calibrated equivalence claimed.'}

if __name__=='__main__':check()
