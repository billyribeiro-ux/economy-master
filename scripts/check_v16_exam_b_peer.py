"""Independent exact/normal-tail Form B peer audit; author checker is hash-bound only."""
from pathlib import Path
from html.parser import HTMLParser
from fractions import Fraction as F
from hashlib import sha256
from itertools import product
import ast,json,math,re,sys
ROOT=Path(__file__).resolve().parents[1]
FILES=['content/assessments/parts/v16-exam-b.html','scripts/check_v16_exam_b.py','content/reviews/v16-exam-b-sources.json','content/reviews/v16-exam-b-author.json','scripts/check_v16_exam_b_peer.py','content/reviews/v16-exam-b-peer.json']

def need(ok,msg):
    if not ok:raise ValueError('V16 B peer: '+msg)

def parse(text):
    if '=' in text:text=text.split('=',1)[1]
    def visit(node):
        if isinstance(node,ast.Expression):return visit(node.body)
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return F(str(node.value))
        if isinstance(node,ast.Tuple):return tuple(visit(v) for v in node.elts)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -visit(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return visit(node.left)/visit(node.right)
        raise ValueError('numeric syntax')
    return visit(ast.parse(text.strip().replace('−','-'),mode='eval'))

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.questions=[];self.answers=[];self.points=[];self.domains=[];self.rubrics={};self.solution=None;self.markers={};self.capture=None;self.tables=[];self.row=None;self.cell=None;self.sources={};self.alltext=''
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attrs');need(t!='h1','no h1')
        if 'id' in a:self.ids.append(a['id'])
        if 'data-domain' in a:self.domains.append((a['data-domain'],[]))
        if t=='li' and any(z=='ol' and 'exercises' in d.get('class','').split() for z,d in self.stack):
            self.questions.append(a['id']);self.points.append(int(a['data-points']));self.domains[-1][1].append(a['id'])
        if 'data-solution-for' in a:
            need(any(z=='details' and 'solutions' in d.get('class','').split() for z,d in self.stack),'solutions inside disclosure');self.solution=a['data-solution-for'];self.answers.append(self.solution);self.rubrics[self.solution]=[]
        if 'data-rubric-points' in a:need(self.solution is not None,'rubric in solution');self.rubrics[self.solution].append(int(a['data-rubric-points']))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for kind in ('input','result'):
            if 'data-'+kind in a:self.capture=(kind,a['data-'+kind]);need(self.capture not in self.markers,'unique number');self.markers[self.capture]=''
        if t=='table':self.tables.append([])
        if t=='tr':self.row=[]
        if t in ('td','th'):self.cell=''
        if t not in ('br','hr','img','meta','input','link'):self.stack.append((t,a))
    def handle_data(self,s):
        self.alltext+=s+' '
        if self.capture:self.markers[self.capture]+=s
        if self.cell is not None:self.cell+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');_,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.capture=None
        if 'data-solution-for' in a:self.solution=None
        if t in ('td','th'):self.row.append(self.cell.strip());self.cell=None
        if t=='tr':self.tables[-1].append(self.row);self.row=None

def deduplicate(rows):
    events={}
    for r in rows:
        need(len(r)==6,'six raw fields');event,bank,z,receipt,base,final=r
        need(event and bank and z in ('0','1') and receipt in ('0','1'),'valid raw identifiers/indicators')
        need(F(base)>=0 and (final=='Unknown' or F(final)>=0),'valid stock or missing state')
        need(event not in events or events[event]==r,'conflicting duplicate needs source query');events[event]=r
    vals=list(events.values());need(len({r[1] for r in vals})==len(vals),'one bank record after event deduplication');return vals

def available(rows):
    means=[]
    for z in ('1','0'):
        group=[r for r in rows if r[2]==z and r[5]!='Unknown'];need(group,'nonempty observed arm');means.append(F(sum(F(r[5])>=F(r[4]) for r in group),len(group)))
    return tuple(means)+(means[0]-means[1],)

def optimum(gap,capacity):
    need(type(gap) in (int,F) and type(capacity) in (int,F) and capacity>=0,'valid model domain')
    candidates={F(0),F(capacity)}
    if 0<=gap<=capacity:candidates.add(F(gap))
    return max(candidates,key=lambda x:gap*x-x*x/2)

def power(n,sigma,delta):
    need(type(n) is int and n>0 and math.isfinite(sigma) and sigma>0 and math.isfinite(delta),'power domain')
    se=sigma*math.sqrt(2/n);shift=delta/se
    return math.erfc((1.96-shift)/math.sqrt(2))/2+math.erfc((1.96+shift)/math.sqrt(2))/2

def check(root=None):
    root=Path(root) if root is not None else ROOT
    record=json.loads((root/FILES[-1]).read_text());need(set(record['payloads'])==set(FILES[:-1]),'five nonself runtime hashes')
    for f,r in record['payloads'].items():
        data=(root/f).read_bytes();need(r=={'bytes':len(data),'sha256':sha256(data).hexdigest()},'frozen '+f)
    need(record['full_reading_complete'] and not record['open_material_findings'],'full qualitative review')
    html=(root/FILES[0]).read_text();p=Page();p.feed(html);p.close();need(not p.stack and len(p.ids)==len(set(p.ids)),'complete unique structure')
    ids=[f'v16-exam-b-q{i:02}' for i in range(1,21)];need(p.questions==p.answers==ids,'twenty prompt/answer pairs');need(p.points==[5]*20 and all(p.rubrics[i]==[1]*5 for i in ids),'all additive5point rubrics')
    domains=['question_literature_judgment','reproduction_data_ethics','model_identification_design','robustness_writing','defense_portfolio'];need([d for d,_ in p.domains]==domains and all(qs==ids[4*i:4*i+4] for i,(_,qs) in enumerate(p.domains)),'five20point domains')
    sources=json.loads((root/FILES[2]).read_text());need(p.sources=={s['id']:s['url'] for s in sources['sources']},'bounded source links')
    values={k:parse(v) for k,v in p.markers.items()};used=set();comparisons=0
    def get(kind,key):used.add((kind,key));return values[kind,key]
    def eq(a,b,msg,tol=0):
        nonlocal comparisons
        if isinstance(a,tuple) or isinstance(b,tuple):
            need(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),msg+' shape')
            for x,y in zip(a,b):eq(x,y,msg,tol)
        else:need(abs(a-b)<=tol,msg);comparisons+=1
    def out(key,v,tol=0):eq(get('result',key),v,key,tol)
    raw=p.tables[0][1:];rows=deduplicate(raw);observed=sum(r[5]!='Unknown' for r in rows)
    out('record-counts',(len(raw),len(rows),observed));fault=available(raw);correct=available(rows);out('faulty-gap',fault[2]);out('complete-case',correct)
    eq(correct,(F(2,3),F(1,3),F(1,3)),'primitive available case')
    completions=[]
    for u,v in product((0,1),repeat=2):
        filled=[r[:] for r in rows]
        for r in filled:
            if r[5]=='Unknown':r[5]=r[4] if (u if r[2]=='1' else v) else str(F(r[4])-1)
        completions.append(available(filled)[2])
    out('missing-grid',tuple(completions));out('missing-bounds',(min(completions),max(completions)));eq(tuple(sorted(set(completions))),(F(0),F(1,4),F(1,2)),'sharp finite grid')
    old=[r[:] for r in rows]
    for r in old:
        if r[0]=='e6':r[5]='11'
    oldgap=available(old)[2];out('version-gap',(oldgap,correct[2],correct[2]-oldgap));eq(100*(correct[2]-oldgap),F(100,3),'percentage points')
    borrowers=re.search(r"borrower U's main-bank credit changes from (\d+) to (\d+) and outside-bank credit changes from (\d+) to (\d+); borrower V's main-bank credit changes from (\d+) to (\d+) and outside-bank credit changes from (\d+) to (\d+)",p.alltext)
    need(borrowers is not None,'actual Note P primitives');a,b,c,d,e,f,g,h=map(F,borrowers.groups());out('p-total-changes',(b+d-a-c,f+h-e-g))
    worlds=(((1,1),(0,0)),((0,1),(0,1)))
    out('receipt-worlds',tuple(F(sum(y1-y0 for y0,y1 in world),2) for world in worlds))
    for world in worlds:eq((world[0][1],world[1][0]),(1,0),'same receipt observations')
    high=get('input','model-high');low=get('input','model-low');k0=get('input','cap-low');k1=get('input','cap-high');hi=(optimum(high,k0),optimum(high,k1));lo=(optimum(low,k0),optimum(low,k1));out('cap-model',hi+(hi[1]-hi[0],)+lo+(lo[1]-lo[0],))
    for gap in (-2,0,2,3,5,6):
        for cap in (0,2,3,5):
            opt=optimum(gap,cap)
            for point in (F(0),F(cap,2),F(cap)):need(gap*opt-opt*opt/2>=gap*point-point*point/2,'global objective witness');comparisons+=1
    sigma=get('input','sigma');effect=get('input','effect');ns=get('input','sample-sizes');capacity=get('input','capacity');powers=tuple(power(int(n),float(sigma),float(effect)) for n in ns);out('power',powers,1e-8)
    eq(sigma*sigma*2/ns[0],F(1,100),'first SE squared');eq(sigma*sigma*2/ns[1],F(1,200),'second SE squared');need(powers[0]<.8<=powers[1] and 2*ns[1]==capacity,'candidate feasibility')
    for delta in (0.,.1,.2):eq(power(32,.4,delta),power(32,.4,-delta),'power sign symmetry',1e-14)
    ps=get('input','p-values');out('adjusted-p',tuple(min(F(1),2*v) for v in ps));need(ps[0]<=F(1,40)<ps[1],'family decision')
    zero=[r[:] for r in rows]
    for r in zero:
        if r[5]=='Unknown':r[5]='0'
    attendees=[r for r in rows if r[3]=='1'];attend=F(sum(F(r[5])>=F(r[4]) for r in attendees),len(attendees))-correct[1]
    spec=(correct[2],available(zero)[2],attend,fault[2]);out('spec-display',spec)
    need(tuple(parse(r[2]) for r in p.tables[-1][1:])==spec,'actual specification table contrasts')
    estimate=get('input','bias-estimate');se=get('input','bias-se');radius=get('input','bias-radius');critical=F(49,25);out('bias-interval',(estimate-critical*se-radius,estimate+critical*se+radius));out('bias-threshold',estimate-critical*se)
    nominal=math.erf(1.96/math.sqrt(2))
    for b in (-radius,F(0),radius):
        upper=float((radius-b)/se)+1.96;lower=float((-radius-b)/se)-1.96;cov=(math.erf(upper/math.sqrt(2))-math.erf(lower/math.sqrt(2)))/2;need(cov>=nominal-1e-14,'union coverage witness');comparisons+=1
    effects=get('input','stratum-effects');ss=get('input','source-shares');ts=get('input','target-shares');oshares=get('input','overlap-shares');need(sum(ss)==sum(ts)==sum(oshares)==1,'shares normalize');out('transport',(sum(a*b for a,b in zip(effects,ss)),sum(a*b for a,b in zip(effects,ts))));known=sum(a*b for a,b in zip(effects,oshares));out('transport-bounds',(known-oshares[2],known+oshares[2]))
    for y0,y1 in ((1,0),(0,0),(0,1)):
        effect3=y1-y0;actual=known+oshares[2]*effect3;need(known-oshares[2]<=actual<=known+oshares[2],'binary endpoint witness');comparisons+=1
    scores=get('input','domain-scores');out('exam-total',sum(scores));need(sum(scores)>=85 and min(scores)<15,'domain floor fails')
    agenda=get('input','original-agenda');new=(agenda[0],F(0),agenda[2],agenda[1],agenda[3]);out('agenda',new);eq(sum(new),sum(agenda),'agenda conservation');eq(new[3],F(25),'access required')
    need(used==set(values),'all visible numeric markers covered')
    abstract=re.search(r'<strong>Abstract\.</strong> “(.*?)”',html,re.S);need(abstract is not None,'actual abstract');word_count=len(abstract.group(1).split());need(word_count<=120,'abstract maximum words')
    bad=[lambda:deduplicate([['x','A','1','0','10','11'],['x','A','1','0','10','12']]),lambda:deduplicate([['x','A','2','0','10','11']]),lambda:deduplicate([['x','A','1','0','10','-1']]),lambda:deduplicate([['x','A','1','0','10','11'],['y','A','1','0','10','11']]),lambda:available([['x','A','1','0','10','Unknown']]),lambda:optimum(2,-1),lambda:optimum(True,2),lambda:power(0,.4,.2),lambda:power(True,.4,.2),lambda:power(32,0,.2),lambda:power(32,.4,float('nan'))]
    for fn in bad:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'volume':'v16','component':'exam_b_peer','status':'passed','runtime_files':6,'prompts':20,'solutions':20,'rubric_points':100,'domains':5,'comparisons':comparisons,'numeric_markers':len(values),'missingness_completions':4,'constrained_model_worlds':24,'invalid_domains':len(bad),'abstract_words':word_count,'author_checker':'hash-bound only; no template read/import/execution','review_scope':'Every prompt, full written answer, proof and additive rubric read separately; q19 runnable/executed distinction verified.'}

if __name__=='__main__':
    need(len(sys.argv)<=2,'at most one root path');check(sys.argv[1] if len(sys.argv)==2 else None)
