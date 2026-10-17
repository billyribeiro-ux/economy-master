"""Read-only four-file Form A audit; scoring, raw events and original calculations."""
import ast
import json
import math
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import permutations
from pathlib import Path
FILES=('content/assessments/parts/v16-exam-a.html','scripts/check_v16_exam_a.py','content/reviews/v16-exam-a-sources.json','content/reviews/v16-exam-a-author.json')
DOMAINS=('question_literature_judgment','reproduction_data_ethics','model_identification_design','robustness_writing','defense_portfolio')
def need(ok,label):
    if not ok:raise ValueError(label)
def literal(text):
    def read(n):
        if isinstance(n,ast.Constant):
            need(type(n.value) in (int,float),'numeric literal');return F(str(n.value))
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return read(n.left)/read(n.right)
        raise ValueError('exact literal expected')
    return read(ast.parse(text,mode='eval').body)
class Exam(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.ids=[];self.inputs={};self.results={};self.questions=[];self.solutions=[];self.soltext={};self.rubrics={};self.domains=[];self.sources={};self.rows=[];self.headings=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(t!='h1','fragment')
        if 'id' in a:
            need(a['id'] in ('form-a','solutions-a') or a['id'].startswith('v16-exam-a-'),'namespaced ID');need(a['id'] not in self.ids,'unique ID');self.ids.append(a['id'])
        if t=='h2':self.headings.append(a.get('id'))
        if 'data-domain' in a:self.domains.append((a['data-domain'],int(a['data-domain-points'])))
        if 'data-points' in a:
            need(t=='li' and any(x=='ol' and 'exercises' in y.get('class','').split() for x,y in self.stack),'scored prompt list')
            domain=next(y['data-domain'] for x,y in reversed(self.stack) if 'data-domain' in y);self.questions.append((a['id'],int(a['data-points']),domain,a['data-chapters'].split()))
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in y.get('class','').split() for x,y in self.stack),'solution disclosure')
            k=a['data-solution-for'];self.solutions.append(k);self.soltext[k]='';self.rubrics[k]=[];self.active.append((self.soltext,k,len(self.stack)))
        if 'data-rubric-points' in a:
            k=next(y['data-solution-for'] for x,y in reversed(self.stack) if 'data-solution-for' in y);self.rubrics[k].append(int(a['data-rubric-points']))
        if 'data-source' in a:need(a['data-source'] not in self.sources,'source unique');self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:k=a[attr];need(k not in d,'marker unique');d[k]='';self.active.append((d,k,len(self.stack)))
        if t=='tr' and any(y.get('id')=='v16-exam-a-events' for x,y in self.stack):self.rows.append([])
        if t in ('th','td') and any(y.get('id')=='v16-exam-a-events' for x,y in self.stack):
            row=self.rows[-1];row.append('');self.active.append((row,len(row)-1,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]
def normalize(rows,deduplicate=True):
    need(type(deduplicate) is bool,'dedup mode');need(bool(rows),'nonempty event data')
    scale={'thousand':F(1,1000),'million':F(1)};mapping={'K7':'A','M4':'B','R2':'C'};seen={};raw_ids=set();events=[]
    for row in rows:
        need(len(row)==6,'six event fields');raw,event,code,kind,amount,unit=row
        need(type(raw) is str and raw and raw not in raw_ids,'raw row unique');raw_ids.add(raw)
        need(type(event) is str and bool(event),'event identifier');need(code in mapping and kind in ('advance','repayment') and unit in scale,'dictionary membership')
        need(type(amount) in (int,F) and amount>=0,'nonnegative exact amount');amount=F(amount)*scale[unit]
        normalized=(mapping[code],kind,amount)
        if event in seen:need(seen[event]==normalized,'conflicting repeated event')
        if not deduplicate or event not in seen:events.append((event,normalized[0],amount if kind=='advance' else -amount))
        seen[event]=normalized
    bank={k:sum(value for _,b,value in events if b==k) for k in ('A','B','C')}
    return tuple(events),bank,sum(bank.values())
def equilibrium(a,b,c,g,d):
    need(all(type(v) in (int,F) for v in (a,b,c,g,d)),'exact model primitives');a,b,c,g,d=map(F,(a,b,c,g,d))
    need(a>=0 and b>0 and c>=0 and g>0 and d>=0,'model domain')
    # Independent candidate maximization across the two quadratic regions.
    candidate={F(0),d,max(F(0),min(d,(a-c)/b)),max(d,(a-c+g*d)/(b+g))}
    welfare=lambda q:(a-c)*q-b*q*q/2-g*max(q-d,0)**2/2
    q=max(candidate,key=welfare);return q,a-b*q

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]])
    bindings=review['payload_bindings'];need(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three nonself hashes')
    for b in bindings:
        v=raw[b['path']];need((len(v),sha256(v).hexdigest())==(b['bytes'],b['sha256']),'freeze')
    doc=Exam();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'closed exam')
    qids=['v16-exam-a-q'+str(i) for i in range(1,21)];need([x[0] for x in doc.questions]==doc.solutions==qids,'twenty paired answers')
    need(doc.headings==['form-a','solutions-a'],'required heading anchors')
    need(doc.domains==[(d,20) for d in DOMAINS],'five domain totals')
    need(all(p==5 for _,p,_,_ in doc.questions) and sum(p for _,p,_,_ in doc.questions)==100,'100 point form')
    for d in DOMAINS:need(sum(p for _,p,domain,_ in doc.questions if domain==d)==20,'each domain20')
    need(all(doc.rubrics[q]==[1]*5 for q in qids),'five additive one-point criteria per answer')
    coverage={chapter for _,_,_,chapters in doc.questions for chapter in chapters};need(coverage=={'v16-c'+str(i).zfill(2) for i in range(1,13)},'all twelve chapter outcomes mapped')
    need(set(review['exact_prompt_review'])==set(qids),'full exact-prompt reading record')
    need(review['chapter_coverage']=={q:chapters for q,_,_,chapters in doc.questions},'review coverage mapping')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==4,'bounded source references')
    inputs={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.results.items()}
    expected_inputs={'cedar-offered':(3,4,5),'cedar-controls':(1,2,3),'maple-original':(-3,-2,-1),'maple-other':(2,2,1),'revised-repayment':350,'model-primitives':(12,1,3,2),'power-capacity':100,'power-primitives':(2,1,F(489991,250000)),'bias-primitives':(2,F(1,2),F(6,5),F(49,25)),'transport-effects':(3,1),'transport-source':(F(3,5),F(2,5)),'transport-target':(F(1,5),F(4,5))}
    need(inputs==expected_inputs,'all supplied numeric fixtures')
    rows=tuple(tuple(row[:4])+(literal(row[4]),row[5]) for row in doc.rows[1:]);need(len(rows)==7,'seven supplied reports')
    events,bank,total=normalize(rows);old=normalize(rows,False)[2]
    revised=tuple(row[:4]+(inputs['revised-repayment'],row[5]) if row[1]=='e02' else row for row in rows);_,bank2,total2=normalize(revised)
    model=inputs['model-primitives'];theta,se,B,z=inputs['bias-primitives'];effects,source,target=inputs['transport-effects'],inputs['transport-source'],inputs['transport-target']
    sigma,delta,critical=map(float,inputs['power-primitives']);n=float(inputs['power-capacity'])/2;shift=delta/(sigma*math.sqrt(2/n));cdf=lambda x:math.erfc(-x/math.sqrt(2))/2
    power=lambda nn:cdf(delta*math.sqrt(nn/2)/sigma-critical)+cdf(-delta*math.sqrt(nn/2)/sigma-critical)
    minimum=next(i for i in range(1,1000) if power(i)>=.8)
    expected={'event-contributions':tuple(v for _,_,v in events),'r1-banks':tuple(bank.values()),'r1-total':total,'old-benchmark':old,'r2-total':total2,'r2-banks':tuple(bank2.values()),'model-equilibria':tuple(equilibrium(*model,F(d)) for d in (1,10)),'power-feasible':power(n),'power-total':minimum*2,'base-ci':(theta-z*se,theta+z*se),'bias-ci':(theta-B-z*se,theta+z*se),'bias-tip':theta-z*se,'transport-means':tuple(sum(w*e for w,e in zip(p,effects)) for p in (source,target)),'transport-weights':tuple(t/s for s,t in zip(source,target)),'talk-seconds':(15,25,25,15,10)}
    count=0
    def eq(a,b,label,tol=0):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label,tol)
        else:count+=1;need(abs(float(a)-float(b))<=tol if tol else a==b,label)
    need(set(shown)==set(expected),'all answer numeric groups')
    for k,v in expected.items():eq(shown[k],v,k,5.01e-7 if k=='power-feasible' else 0)
    eq(sum(inputs['cedar-offered'])/3-sum(inputs['cedar-controls'])/3,2,'Cedar contrast')
    eq(tuple(x+y for x,y in zip(inputs['maple-original'],inputs['maple-other'])),(-1,0,0),'Maple borrower sums')
    eq(sum(inputs['maple-original'])/3,-2,'Maple lender mean');eq(sum(inputs['maple-other'])/3,F(5,3),'Maple other mean')
    eq(old-total,F(4,5),'duplicate discrepancy');eq(total2-total,F(-1,20),'authoritative source revision')
    eq((sum(v for _,_,v in events if v>0),-sum(v for _,_,v in events if v<0)),(F(12,5),F(4,5)),'gross and repayment accounts')
    eq((power(62),power(63)),(.795008,.801302),'supplied power boundary values',5.01e-7)
    eq(minimum*2-int(inputs['power-capacity']),26,'capacity shortfall')
    eq(sum(shown['talk-seconds']),90,'talk timing');eq(sum((10,25,15,10)),60,'initial scope hours');eq(sum((40,5,20,15,20,0)),100,'portfolio schedule');eq(15-5+10,20,'access time reallocation')
    abstract=doc.soltext['v16-exam-a-q15'].split('Abstract: “',1)[1].split('”',1)[0];words=len(abstract.split());need(words<=85,'complete abstract word cap')
    # Alternative order/unit/duplicate and conflict witnesses; reconstruction is not tied to row order.
    for order in (rows[::-1],rows[2:]+rows[:2],tuple(sorted(rows,key=lambda row:row[1]))):
        result=normalize(order);eq(result[1],bank,'row-order bank totals');eq(result[2],total,'row-order aggregate')
    common=tuple(row[:4]+(row[4]*(1000 if row[5]=='million' else 1),'thousand') for row in rows);eq(normalize(common)[2],total,'common-unit invariance')
    unique=tuple(row for row in rows if row[0]!='r04');eq(normalize(unique)[2],total,'verified duplicate removal')
    newzero=rows+(('r08','e07','K7','advance',F(0),'million'),);eq(normalize(newzero)[2],total,'observed zero additional event')
    for d in (F(0),F(1),F(2),F(9),F(10),F(100)):
        q,r=equilibrium(*model,d);eq(max(12-r,0),q,'borrower choice')
        if q>d:eq(r,3+2*(q-d),'binding supplier choice')
        else:eq(r,3,'slack supplier choice')
        need(q>=0 and r>=0,'model feasible')
    eq(equilibrium(*model,F(2))[0]-equilibrium(*model,F(1))[0],F(2,3),'binding derivative')
    for theta_true in (F(-2),F(0),F(3)):
        for bias in (F(0),F(3,5),B):
            tau=theta_true-bias
            for error in (-z*se,F(0),z*se):
                estimate=theta_true+error;need(estimate-B-z*se<=tau<=estimate+z*se,'uniform bias central event');count+=1
    eq(sum(s*w for s,w in zip(source,shown['transport-weights'])),1,'transport weights normalize')
    for desired in (F(-100),F(0),F(100)):
        supported=F(9,10)*shown['transport-means'][1];unknown=(desired-supported)/F(1,10);eq(supported+F(1,10)*unknown,desired,'unsupported type arbitrary mean')
    bad=[(),rows+(rows[0],),rows+(('r08','e03','M4','advance',F(9,10),'million'),),rows+(('r08','e08','X0','advance',F(1),'million'),),rows+(('r08','e08','K7','transfer',F(1),'million'),),rows+(('r08','e08','K7','advance',F(-1),'million'),),rows+(('r08','e08','K7','advance',True,'million'),),rows+(('r08','e08','K7','advance',F(1),'billion'),)]
    rejected=0
    for data in bad:
        try:normalize(data)
        except ValueError:rejected+=1
        else:raise ValueError('invalid event contract accepted')
    for args in ((12,0,3,2,1),(12,1,3,0,1),(12,1,3,2,-1)):
        try:equilibrium(*args)
        except ValueError:rejected+=1
        else:raise ValueError('invalid equilibrium domain accepted')
    for p,v in raw.items():need((root/p).read_bytes()==v,'unchanged runtime bytes')
    return {'component':'v16-exam-a','status':'passed','points':100,'domains':5,'scored_prompts':20,'solutions':20,'rubric_criteria':100,'chapters_covered':12,'raw_reports':len(rows),'unique_events':len(events),'result_groups':len(shown),'comparisons':count,'rejected_inputs':rejected,'abstract_words':words,'runtime_files':4,'qualitative_scope':'Full artifact and prompt/answer reading recorded; independent acceptance pending.'}
if __name__=='__main__':check()
