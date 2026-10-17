"""Independent V17 Form B review oracle; author checker remains opaque."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import ast,hashlib,json,sys
AUTHOR=('content/assessments/parts/v17-exam-b.html','scripts/check_v17_exam_b.py','content/reviews/v17-exam-b-sources.json','content/reviews/v17-exam-b-author.json')
SELF='scripts/check_v17_exam_b_peer.py';REVIEW='content/reviews/v17-exam-b-peer.json';FILES=AUTHOR+(SELF,REVIEW)
DOMAINS=('alignment_explanation','course_seminar_design','assessment_feedback','communication_supervision','observation_portfolio')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(p):
    b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def literal(s):
    def walk(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.Tuple):return tuple(walk(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('exact rational literal')
    return walk(ast.parse(s.strip(),mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.active=[];self.ids=[];self.inputs={};self.results={};self.questions=[];self.answers=[];self.rubrics={};self.domains=[];self.sources={};self.tables={};self.headings=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(t!='h1','no h1')
        if 'id' in a:need(a['id'] not in self.ids,'unique IDs');self.ids.append(a['id'])
        if t=='h2':self.headings.append(a.get('id'))
        if 'data-domain' in a:self.domains.append(a['data-domain'])
        if 'data-points' in a:
            domain=next(v['data-domain'] for _,v in reversed(self.stack) if 'data-domain' in v)
            self.questions.append((a['id'],int(a['data-points']),domain,a['data-chapters'].split()))
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in v.get('class','').split() for t,v in self.stack),'solution disclosure');k=a['data-solution-for'];self.answers.append(k);self.rubrics[k]=[]
        if 'data-rubric-points' in a:
            k=next(v['data-solution-for'] for _,v in reversed(self.stack) if 'data-solution-for' in v);self.rubrics[k].append(int(a['data-rubric-points']))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for key,container in [('data-input',self.inputs),('data-result',self.results)]:
            if key in a:need(a[key] not in container,'unique marker');container[a[key]]='';self.active.append((container,a[key],len(self.stack)))
        if t=='table' and a.get('id'):self.tables[a['id']]=[]
        table=next((v['id'] for x,v in reversed(self.stack) if x=='table' and v.get('id')),None)
        if t=='tr' and table:self.tables[table].append([])
        if t in ('th','td') and table:
            row=self.tables[table][-1];row.append('');self.active.append((row,len(row)-1,len(self.stack)))
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[a for a in self.active if a[2]<len(self.stack)]
def price(face,years,yield_rate):
    need(type(face) in (int,F) and type(years) in (int,F) and type(yield_rate) in (int,F),'exact price inputs')
    face,years,yield_rate=F(face),F(years),F(yield_rate);need(face>0 and years.denominator==1 and years>=0 and yield_rate>-1,'bond domain')
    amount=face
    for _ in range(int(years)):amount/=1+yield_rate
    return amount

def holding(purchase,sale):
    need(all(type(x) in (int,F) for x in (purchase,sale)) and purchase>0 and sale>=0,'holding domain')
    return (F(sale)-purchase)/purchase

def rate(success,total):
    need(all(type(x) is int for x in (success,total)) and total>0 and 0<=success<=total,'count domain');return F(success,total)

def standard(high,low,w):
    need(type(w) in (int,F) and 0<=w<=1,'weight domain');return F(w)*high+(1-F(w))*low

def missing_binary(values):
    need(type(values) is tuple and values and all(v is None or (type(v) is int and v in (0,1)) for v in values),'binary record domain')
    holes=[i for i,v in enumerate(values) if v is None];means=[]
    for fill in product((0,1),repeat=len(holes)):
        completed=list(values)
        for i,v in zip(holes,fill):completed[i]=v
        means.append(F(sum(completed),len(completed)))
    return tuple(means)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before={f:digest(root/f) for f in FILES};review=json.loads((root/REVIEW).read_text());need(set(review['payloads'])==set(FILES)-{REVIEW},'five nonself bindings')
    for f,b in review['payloads'].items():need(before[f]==b,'peer binding '+f)
    author=json.loads((root/AUTHOR[3]).read_text())
    for f,b in author['payloads'].items():need(before[f]==b,'author binding '+f)
    p=Page();p.feed((root/AUTHOR[0]).read_text());need(not p.stack,'complete markup')
    qids=['v17-exam-b-q'+str(i).zfill(2) for i in range(1,21)]
    need([q[0] for q in p.questions]==p.answers==qids,'twenty exact solutions');need(p.headings==['form-b','solutions-b'],'heading anchors');need(p.domains==list(DOMAINS),'five domains')
    need(all(i in ('form-b','solutions-b') or i.startswith('v17-exam-b-') for i in p.ids),'ID scope')
    need(sum(q[1] for q in p.questions)==100 and all(q[1]==5 for q in p.questions),'100 points')
    need(all(sum(q[1] for q in p.questions if q[2]==d)==20 for d in DOMAINS),'20 per domain')
    need(all(p.rubrics[q]==[1]*5 for q in qids),'additive rubrics');need(set(review['exact_prompt_review'])==set(qids),'all prompt judgments')
    need({c for q in p.questions for c in q[3]}=={'v17-c'+str(i).zfill(2) for i in range(1,13)},'all12 chapters')
    sources=json.loads((root/AUTHOR[2]).read_text());need(p.sources=={s['id']:s['url'] for s in sources['sources']},'source routes')
    inp={k:literal(v) for k,v in p.inputs.items()};shown={k:literal(v) for k,v in p.results.items()};count=0
    face,years,y0=inp['bond'];p0=price(face,years,y0);p1=price(face,years-1,inp['later-yield-percent']/100);h=holding(p0,p1)
    expected={'q1':(price(110,1,F(1,10)),holding(100,110)),'q2':(p0,p1,p1-p0,h),'q3':(face/p0-1,price(face,1,inp['q3-yield-percent']/100),holding(p0,price(face,1,inp['q3-yield-percent']/100)))}
    rows=p.tables['v17-exam-b-archive'][1:];need(len(rows)==4,'four archive cells');cells={(r[0],r[1]):(int(r[2]),int(r[3])) for r in rows}
    nh,nl,lh,ll=(rate(*cells[k]) for k in [('New','High'),('New','Low'),('Legacy','High'),('Legacy','Low')])
    aggregate={desk:rate(sum(cells[(desk,g)][0] for g in ('High','Low')),sum(cells[(desk,g)][1] for g in ('High','Low'))) for desk in ('New','Legacy')}
    sn,sl=standard(nh,nl,F(1,2)),standard(lh,ll,F(1,2));expected['q4']=(aggregate['New'],aggregate['Legacy'],aggregate['New']-aggregate['Legacy'],nh,lh,nl,ll,sn,sl,sn-sl)
    expected.update({'q5':(8,8,16),'q6':(10,30,20,40,100),'q7':(100,10,10,20,20,25,15),'q8':(standard(nh,nl,F(4,5)),standard(lh,ll,F(4,5)),F(1,10)),'q9':((1,0,0,0,0),(1,1,1,1,1),(1,1,0,1,1),(1,5,4))})
    fresh0=price(inp['q10-face'],2,inp['q10-purchase-yield-percent']/100);fresh1=price(inp['q10-face'],1,inp['q10-sale-yield-percent']/100);expected['q10']=(fresh0,fresh1,holding(fresh0,fresh1))
    register=p.tables['v17-exam-b-learning'][1:];need(len(register)==6 and [r[0] for r in register]==list('ABCDEF'),'six learner rows')
    initial=tuple(int(r[1]) for r in register);assisted=tuple(int(r[2]) for r in register);delayed=tuple(None if r[3]=='Missing' else int(r[3]) for r in register)
    im=rate(sum(initial),6);am=rate(sum(assisted),6);obs=tuple(x for x in delayed if x is not None);rm=rate(sum(obs),len(obs));completions=missing_binary(delayed)
    expected['q11']=(im,am,rm,min(completions),max(completions),min(completions)-im,max(completions)-im)
    diagnostic=price(inp['q12-face'],1,inp['q12-sale-yield-percent']/100);expected['q12']=(diagnostic,holding(inp['q12-purchase'],diagnostic));expected['q13']=(4,8,8,6,4,30)
    # Reconstruct complete Release2 binary records, preserving all borrowers and fixed strata.
    new_high=(1,)*cells[('New','High')][0]+(0,)*(cells[('New','High')][1]-cells[('New','High')][0])
    low_known=(1,)*27+(0,)*58;rawvalues=[];stdvalues=[]
    for fill in product((0,1),repeat=5):
        low=low_known+fill;need(len(low)==90 and len(new_high+low)==100,'preserved release2 roster')
        rawvalues.append(rate(sum(new_high+low),100));stdvalues.append((rate(sum(new_high),10)+rate(sum(low),90))/2);count+=2
    expected['q16']=((min(rawvalues),max(rawvalues)),(min(rawvalues)-aggregate['Legacy'],max(rawvalues)-aggregate['Legacy']),(min(stdvalues),max(stdvalues)),(min(stdvalues)-sl,max(stdvalues)-sl))
    expected['q18']=(3,3,4,10);j,k=inp['candidate-j'],inp['candidate-k'];expected['q20']=(sum(j),min(j),sum(k),min(k))
    need(set(shown)==set(expected),'all numerical answers')
    def nvalues(v):return sum(nvalues(x) for x in v) if isinstance(v,tuple) else 1
    for key,value in expected.items():need(shown[key]==value,'answer '+key);count+=nvalues(value)
    need(sum(j)>=inp['overall-gate'] and min(j)>=inp['domain-gate'] and sum(k)>=inp['overall-gate'] and min(k)<inp['domain-gate'],'advancement numeric gates');count+=4
    need((p1-p0)/p1==F(17,72) and 100*h==F(340,11),'N denominator and M percentage');count+=2
    zero=face/p0-1
    for y in (F(-1,2),F(0),y0,zero-F(1,100),zero,zero+F(1,100),F(3,5),F(2)):
        value=holding(p0,price(face,1,y));need((value>0)==(y<zero) and (value==0)==(y==zero),'global return sign');count+=2
    need(price(face,1,y0)==120 and holding(p0,120)==y0 and holding(p0,face)==F(11,25),'unchanged yield and maturity');count+=3
    # Affine identity tested over101 common weights and distinct-composition sign/zero witnesses.
    for i in range(101):
        w=F(i,100);need(standard(nh,nl,w)-standard(lh,ll,w)==F(1,10),'constant common-weight difference');count+=1
    for wn,wl in [(F(0),F(1)),(F(1),F(0)),(F(0),F(1,6)),(F(1,10),F(9,10)),(F(1,2),F(1,2))]:
        diff=standard(nh,nl,wn)-standard(lh,ll,wl);need(diff==F(1,10)+F(3,5)*(wn-wl),'different-weight identity');need((diff<0)==(wn-wl<F(-1,6)) and (diff==0)==(wn-wl==F(-1,6)),'sign boundary');count+=3
    need(tuple(sorted(set(completions)))==(F(1,2),F(2,3),F(5,6)) and len(set(rawvalues))==len(set(stdvalues))==6,'finite missing grids');count+=3
    need(holding(80,80)==0 and holding(90,80)==F(-1,9) and F(-10,80)==F(-1,8),'diagnostic contrasts');count+=3
    need(sum(expected['q6'][:-1])==100 and sum(expected['q7'][2:])==90 and sum(expected['q13'][:-1])==30 and sum(expected['q18'][:-1])==10,'weights and time budgets');count+=4
    invalid=0
    bad=[(price,(0,1,0)),(price,(100,-1,0)),(price,(100,F(1,2),0)),(price,(100,1,-1)),(price,(100,1,True)),(holding,(0,100)),(holding,(100,-1)),(rate,(2,1)),(rate,(0,0)),(rate,(True,1)),(standard,(nh,nl,-1)),(standard,(nh,nl,2)),(missing_binary,((1,2,None),)),(missing_binary,((True,None),))]
    for fn,args in bad:
        try:fn(*args)
        except ValueError:invalid+=1
        else:raise ValueError('invalid input accepted')
    need(before=={f:digest(root/f) for f in FILES},'no mutation')
    result={'volume':'v17','component':'exam_b','status':'passed','runtime_files':6,'prompts':20,'points':100,'domains':5,'chapters':12,'rubric_criteria':100,'result_groups':len(shown),'comparisons':count,'learning_completions':len(completions),'release2_completions':len(rawvalues),'invalid_domains':invalid,'scope':'Independent complete artifact/rubric/proof review and primitive reconstruction; no actual learner or external human evaluation.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v17_exam_b_peer.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
