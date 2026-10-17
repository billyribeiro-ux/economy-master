"""Independent Form A peer: exact currency ledger and model objective oracle."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations
import ast
import json
import math
import re

FILES=('content/assessments/parts/v16-exam-a.html','scripts/check_v16_exam_a.py','content/reviews/v16-exam-a-sources.json','content/reviews/v16-exam-a-author.json','scripts/check_v16_exam_a_peer.py','content/reviews/v16-exam-a-peer.json')
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
        super().__init__();self.points={};self.domain={};self.rubrics={};self.chapters={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='li' and 'data-points' in a:
            self.points[a['id']]=int(a['data-points']);self.chapters[a['id']]=a.get('data-chapters','').split()
            self.domain[a['id']]=next(x['data-domain'] for t,x in reversed(self.stack) if 'data-domain' in x)
        if 'data-rubric-points' in a:
            target=next(x['data-solution-for'] for t,x in reversed(self.stack) if 'data-solution-for' in x)
            self.rubrics.setdefault(target,[]).append(int(a['data-rubric-points']))
        super().handle_starttag(tag,attrs)


def currency_ledger(deliveries,mapping):
    require(deliveries,'nonempty extract');events={};allrow=F(0)
    require(len(set(mapping.values()))==len(mapping),'one-to-one bank map')
    for row,event,bank,kind,amount,unit in deliveries:
        require(bank in mapping and kind in ('advance','repayment') and unit in ('thousand','million'),'known mapping/kind/unit')
        amount=F(amount);require(amount>=0,'nonnegative event amount')
        cash=amount*(1000 if unit=='thousand' else 1000000)
        key=(mapping[bank],kind,cash)
        if event in events:require(events[event]==key,'conflicting event reports')
        events[event]=key;allrow+=cash*(1 if kind=='advance' else -1)
    contributions=tuple(v[2]*(1 if v[1]=='advance' else -1) for k,v in sorted(events.items()))
    banks={b:F(0) for b in mapping.values()}
    for bank,kind,cash in events.values():banks[bank]+=cash*(1 if kind=='advance' else -1)
    return events,contributions,tuple(banks[k] for k in sorted(banks)),sum(contributions),allrow


def objective_equilibrium(a,b,c,g,D):
    require(a>=0 and c>=0 and b>0 and g>0 and D>=0,'model domain')
    # Optimize the actual piecewise quadratic over its region boundaries and
    # stationary candidates; this is separate from the supplied closed form.
    S=lambda q:(a-c)*q-b*q*q/2-g*max(q-D,0)**2/2
    candidates={F(0),D,max(F(0),F(a-c,b)),max(F(0),F(a-c+g*D,b+g))}
    q=max(candidates,key=S);return q,max(a-b*q,F(0))


def normal_power(n,sigma,effect,critical):
    require(type(n) is int and n>0 and sigma>0 and critical>0,'planning domain')
    se=float(sigma)*math.sqrt(2/n);u=float(effect)/se
    cdf=lambda z:math.erfc(-z/math.sqrt(2))/2
    return cdf(u-float(critical))+cdf(-u-float(critical))


def standardize(effects,shares):
    require(len(effects)==len(shares)>0 and all(x>=0 for x in shares) and sum(shares)==1,'population shares')
    return sum((e*w for e,w in zip(effects,shares)),F(0))


def audit(d,text):
    inputs={k:numeric(v) for k,v in d.inputs.items()};deliveries=[]
    for row in d.rows:
        if len(row)==6 and re.fullmatch('r0[1-7]',row[0]):deliveries.append(tuple(row))
    mapping={'K7':'A','M4':'B','R2':'C'}
    first=currency_ledger(deliveries,mapping);revised=[r[:4]+(str(inputs['revised-repayment']),r[5]) if r[1]=='e02' else r for r in deliveries];second=currency_ledger(revised,mapping)
    million=lambda seq:tuple(v/1000000 for v in seq)
    a,b,c,g=inputs['model-primitives'];sigma,effect,critical=inputs['power-primitives'];n=int(inputs['power-capacity']/2)
    p=normal_power(n,sigma,effect,critical)
    # Exact boundary verification plus monotonicity reviewed analytically; no
    # need to exhaust an arbitrary number of redundant sample sizes.
    require(normal_power(62,sigma,effect,critical)<.8<=normal_power(63,sigma,effect,critical),'minimum sample bracket')
    estimate,se,B,z=inputs['bias-primitives'];base=(estimate-z*se,estimate+z*se);union=(base[0]-B,base[1])
    effects=inputs['transport-effects'];src=inputs['transport-source'];dest=inputs['transport-target'];require(all(x>0 for x in src),'overlap for ratios')
    weights=tuple(t/s for t,s in zip(dest,src))
    timing=numeric(d.results['talk-seconds'])
    want={'event-contributions':million(first[1]),'r1-banks':million(first[2]),'r1-total':first[3]/1000000,'old-benchmark':first[4]/1000000,'r2-total':second[3]/1000000,'r2-banks':million(second[2]),'model-equilibria':(objective_equilibrium(a,b,c,g,F(1)),objective_equilibrium(a,b,c,g,F(10))),'power-feasible':p,'power-total':126,'base-ci':base,'bias-ci':union,'bias-tip':base[0],'transport-means':(standardize(effects,src),standardize(effects,dest)),'transport-weights':weights,'talk-seconds':timing}
    actual={k:numeric(v) for k,v in d.results.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    eq(set(actual),set(want),'all15 displayed result groups')
    for k,v in want.items():
        if k=='power-feasible':require(abs(float(actual[k])-v)<5e-7,'actual rounded two-tail power');count+=1
        else:eq(actual[k],v,'actual result '+k)
    eq((len(deliveries),len(first[0])),(7,6),'raw versus event counts')
    eq(first[0]['e06'][2],0,'observed zero retained')
    eq(sum(x for x in first[1] if x>0)/1000000,F(12,5),'r1grossadvances')
    eq(-sum(x for x in first[1] if x<0)/1000000,F(4,5),'r1repayments')
    eq((first[3]-second[3])/1000000,F(1,20),'revision change')
    eq(sum(inputs['cedar-offered'])/3-sum(inputs['cedar-controls'])/3,F(2),'Cedar difference')
    total=tuple(v+w for v,w in zip(inputs['maple-original'],inputs['maple-other']))
    eq(total,(F(-1),F(0),F(0)),'Maple borrower totals');eq(sum(total)/3,F(-1,3),'Maple mean')
    eq(sum(inputs['maple-original']),-6,'original lender total');eq(sum(inputs['maple-other']),5,'replacement total')
    eq(standardize(weights,src),1,'ratio weights normalized')
    eq(standardize(tuple(w*e for w,e in zip(weights,effects)),src),want['transport-means'][1],'weighted source equals target')
    eq((estimate-B,estimate),(F(4,5),F(2)),'adjusted point set')
    eq(2*63-int(inputs['power-capacity']),26,'capacity shortfall')
    require(len(timing)==5 and min(timing)>=0,'five nonnegative talk phases');eq(sum(timing),90,'ninety second talk')
    # Verify actual prose allocations and actual abstract constraint.
    initial=tuple(int(x) for x in re.findall(r'(?:spend|,)(\d+) (?:hours )?on',d.solutions['v16-exam-a-q1']))
    # Last item is introduced by and, so collect all time phrases explicitly.
    initial=tuple(int(x) for x in re.findall(r'(\d+) (?:hours )?on ',d.solutions['v16-exam-a-q1']))
    eq(initial,(10,25,15,10),'actual scope allocation');eq(sum(initial),60,'initial scope total')
    final=re.search(r'data(\d+),theory(\d+),paper(\d+),response(\d+),access(\d+),reserve(\d+)',d.solutions['v16-exam-a-q20']);require(final is not None,'actual100hourallocation');hours=tuple(map(int,final.groups()))
    eq(hours,(40,5,20,15,20,0),'protectedallocation');eq(sum(hours),100,'later total')
    abstract=re.search(r'Abstract: “(.*?)”',d.solutions['v16-exam-a-q15']).group(1);words=len(abstract.split());require(words<=85,'actual short abstract');count+=1
    # All assignments of a separate four-unit potential-outcome witness verify
    # the linear expectation proof without replacing it with simulation.
    y0=(F(0),F(1),F(2),F(4));y1=(F(2),F(1),F(5),F(3));estimates=[]
    for assignment in combinations(range(4),2):
        estimates.append(sum(y1[i] for i in assignment)/2-sum(y0[i] for i in range(4) if i not in assignment)/2)
    eq(sum(estimates)/len(estimates),sum(b-a for a,b in zip(y0,y1))/4,'exact assignment expectation')
    # Currency normalization before duplicate detection; permutations preserve totals.
    eq(currency_ledger(list(reversed(deliveries)),mapping),first,'delivery order invariance')
    converted=[r[:4]+(str(F(r[4])*(1000 if r[5]=='million' else 1)),'thousand') for r in deliveries]
    eq(currency_ledger(converted,mapping),first,'unit transformation invariance')
    unique_rows=[r for r in deliveries if r[0]!='r04'];eq(currency_ledger(unique_rows,mapping)[:4],first[:4],'removing verified duplicate preservescorrecttotals')
    for D in (F(0),F(1),F(9),F(10),F(100)):
        q,R=objective_equilibrium(a,b,c,g,D)
        eq(max(F(a-R,b),0),q,'borrower optimum')
        if R>c:eq(D+F(R-c,g),q,'supplier binding optimum')
        else:require(R==c and 0<=q<=D,'supplier slack correspondence');count+=1
        S=lambda u:(a-c)*u-b*u*u/2-g*max(u-D,0)**2/2
        for u in (F(0),D,q/2,q,q+1):require(S(q)>=S(u),'global objective witnesses');count+=1
    q0=objective_equilibrium(a,b,c,g,F(1))[0];q1=objective_equilibrium(a,b,c,g,F(11,10))[0]
    eq((q1-q0)/F(1,10),F(2,3),'binding derivative witness')
    eq(objective_equilibrium(a,b,c,g,F(10))[0],objective_equilibrium(a,b,c,g,F(11))[0],'slack derivative zero')
    for bias in (F(0),B/2,B):
        require(union[0]<=base[0]-bias<=base[1]-bias<=union[1],'true-bias normal interval containment');count+=1
    # Positive unsupported mass can realize every target mean without a bound.
    supported=F(9,10)*want['transport-means'][1]
    for desired in (F(-10),F(0),F(10)):
        unknown=(desired-supported)/F(1,10);eq(supported+F(1,10)*unknown,desired,'unsupported type construction')
    bad=[lambda:currency_ledger([],mapping),lambda:currency_ledger(deliveries+[('extra','e03','M4','advance','900','thousand')],mapping),lambda:currency_ledger([('x','e','K7','advance','-1','million')],mapping),lambda:currency_ledger(deliveries,{'K7':'A','M4':'A','R2':'C'}),lambda:currency_ledger([('x','e','unknown','advance','1','million')],mapping),lambda:objective_equilibrium(a,0,c,g,F(1)),lambda:objective_equilibrium(a,b,c,g,F(-1)),lambda:normal_power(0,sigma,effect,critical),lambda:normal_power(2,F(0),effect,critical),lambda:standardize((1,2),(F(1,4),F(1,4)))]
    for fn in bad:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(bad),words


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]])
    bindings=author['payload_bindings'];require({v['path'] for v in bindings}==set(FILES[:3]),'author frozen membership')
    for v in bindings:require(v['bytes']==len(raw[v['path']]) and v['sha256']==sha256(raw[v['path']]).hexdigest(),'author binding')
    require(set(peer['payloads'])==set(FILES[:5]),'peer five nonself bindings')
    for name,v in peer['payloads'].items():require(v['bytes']==len(raw[name]) and v['sha256']==sha256(raw[name]).hexdigest(),'peer binding '+name)
    text=raw[FILES[0]].decode();d=Manuscript();d.feed(text);require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v16-exam-a-q{i}' for i in range(1,21)};require(set(d.prompts)==set(d.solutions)==set(d.points)==set(peer['exact_prompt_review'])==ids,'twenty exact pairs')
    for k in ids:
        require(d.points[k]==5 and d.rubrics[k]==[1]*5,'five additivecriteria')
        record=peer['exact_prompt_review'][k]
        require(record['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and record['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'prompt/solution reading freeze')
    require({domain:sum(d.points[k] for k in ids if d.domain[k]==domain) for domain in DOMAINS}==dict.fromkeys(DOMAINS,20),'five20pointdomains')
    require({chapter for chapters in d.chapters.values() for chapter in chapters}=={f'v16-c{i:02}' for i in range(1,13)},'actual all12 coverage mapping')
    require({'form-a','solutions-a'}<=set(d.ids) and all(x.startswith('v16-exam-a-') or x in ('form-a','solutions-a') for x in d.ids),'owned anchors')
    sources=json.loads(raw[FILES[2]])['sources'];require(len(sources)==4 and d.sources=={s['id']:s['url'] for s in sources},'fourbounded sources')
    require(all(s.get('actual_primary_inspector') or s.get('inspection_attribution') for s in sources),'honest originalinspector attribution')
    require(peer['open_material_findings']==[],'no unresolvedfindings')
    count,bad,words=audit(d,text)
    return {'volume':'v16','component':'exam_a','review':'independent-peer','status':'passed','runtime_files':6,'prompts':20,'solutions':20,'points':100,'domains':5,'chapters_covered':12,'result_groups':15,'comparisons':count,'invalid_domain_rejections':bad,'abstract_words':words,'scope':'Full supplied artifacts/answers/rubrics read; independent raw currency ledger, model objective, assignment expectation and uncertainty audit; no author checker execution or external human certification.'}

if __name__=='__main__':check()
