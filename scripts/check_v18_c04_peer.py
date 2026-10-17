"""V18C04 independent peer oracle; author checker opaque, full prose review separate."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product, combinations
import hashlib,json,sys,ast,math
FILES=('content/chapters/v18-c04.html','scripts/check_v18_c04.py','content/reviews/v18-c04-sources.json','content/reviews/v18-c04-author.json','scripts/check_v18_c04_peer.py','content/reviews/v18-c04-peer.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(p):
    b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def values(text):return tuple(F(t.strip().replace('−','-')) for t in text.strip().strip('()').split(',') if t.strip())
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.h1=False;self.worked=[];self.exercises=[];self.answers=[];self.sources=[];self.inputs={};self.results={};self.marker=None;self.details=0;self.in_ex=False;self.tables={};self.table=None;self.row=None;self.cell=None;self.points={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1=True
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='ol' and 'exercises' in a.get('class','').split():self.in_ex=True
        if tag=='li' and self.in_ex:self.exercises.append(a['id'])
        if tag=='details' and 'solutions' in a.get('class','').split():self.details+=1
        if 'data-solution-for' in a:need(self.details>0,'answer outside solution wrapper');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for k,d in [('data-input',self.inputs),('data-result',self.results)]:
            if k in a:need(a[k] not in d,'duplicate marker');d[a[k]]='';self.marker=(d,a[k])
        if tag=='table':self.table=a.get('id');self.tables[self.table]=[]
        if tag=='tr' and self.table:self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=''
        if 'data-points' in a:self.points.setdefault(self.table,[]).append(int(a['data-points']))
    def handle_endtag(self,tag):
        if tag=='span':self.marker=None
        if tag=='ol':self.in_ex=False
        if tag=='details' and self.details:self.details-=1
        if tag in ('th','td') and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:self.tables[self.table].append(self.row);self.row=None
        if tag=='table':self.table=None
    def handle_data(self,text):
        if self.marker:self.marker[0][self.marker[1]]+=text
        if self.cell is not None:self.cell+=text



def parse(text):
    def walk(node):
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.Constant) and type(node.value) is int:return F(node.value)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('unsupported exact literal')
    return walk(ast.parse(text.replace('−','-'),mode='eval').body)
def vector(x,n=None):
    need(type(x) is tuple and (n is None or len(x)==n) and len(x)>0 and all(type(t) in (int,F) for t in x),'exact nonempty vector')
    return tuple(F(t) for t in x)
def population(data,u,v):
    r,a,s,b,lo,hi=vector(data,6)
    need(0<r<=1 and 0<s<=1 and lo<=min(a,b,u,v)<=max(a,b,u,v)<=hi,'population domain')
    size=math.lcm(r.denominator,s.denominator)
    arm1=tuple((a,True) if i<int(size*r) else (F(u),False) for i in range(size))
    arm0=tuple((b,True) if i<int(size*s) else (F(v),False) for i in range(size))
    mu1=sum(z[0] for z in arm1)/size;mu0=sum(z[0] for z in arm0)/size
    # Every pair of potential arms is equally likely; assignment can be randomized independently.
    ate=sum(x[0]-y[0] for x,y in product(arm1,arm0))/(size*size)
    need(ate==mu1-mu0,'coupled potential records')
    need(sum(x[0] for x in arm1 if x[1])/sum(x[1] for x in arm1)==a,'retained arm1 unchanged')
    need(sum(x[0] for x in arm0 if x[1])/sum(x[1] for x in arm0)==b,'retained arm0 unchanged')
    return mu1,mu0,ate

def identified(data,equal=False):
    lo,hi=data[-2:]
    points=[population(data,u,v)[2] for u,v in ([(lo,lo),(hi,hi)] if equal else product((lo,hi),repeat=2))]
    return min(points),max(points)

def moments(x,y):
    x=vector(x);y=vector(y,len(x));n=len(x)
    vx=sum((a-b)**2 for a,b in product(x,x))/(2*n*n)
    vy=sum((a-b)**2 for a,b in product(y,y))/(2*n*n)
    cov=sum((x[i]-x[j])*(y[i]-y[j]) for i in range(n) for j in range(n))/(2*n*n)
    return sum(x)/n,sum(y)/n,vx,vy,cov

def residual(x,y,h):return tuple(a-h*b for a,b in zip(x,y))
def variance(x):return moments(x,x)[2]
def hedge(x,y,cash):
    x=vector(x);y=vector(y,len(x));c,f,m,cap=vector(cash,4)
    need(min(c,f,cap)>=0 and m>0,'cash domain')
    if c<f:return None
    bound=min(cap,(c-f)/m)
    # Fit the quadratic directly from three state-by-state residual dispersions.
    v0=variance(residual(x,y,F(0)));v1=variance(residual(x,y,F(1)));v2=variance(residual(x,y,F(2)))
    quadratic=(v2-2*v1+v0)/2;linear=v1-v0-quadratic
    need(quadratic>=0,'variance convexity')
    candidates={F(0),bound};center=None
    if quadratic:
        center=-linear/(2*quadratic)
        if 0<=center<=bound:candidates.add(center)
    else:need(linear==0,'constant hedge covariance zero')
    scores={h:variance(residual(x,y,h)) for h in candidates};best=min(scores.values());choices=tuple(sorted(h for h,v in scores.items() if v==best));h=choices[0]
    return {'h':h,'variance':best,'cash':c-m*h,'center':center,'center_variance':variance(residual(x,y,center)) if center is not None else v0,'bound':bound,'unique':bool(quadratic) or bound==0,'endpoints':choices}

def rates(row):
    applicants,assessed,advanced=vector(row,3)
    need(applicants>0 and assessed>0 and 0<=advanced<=assessed<=applicants and all(x.denominator==1 for x in row),'funnel domain')
    return assessed/applicants,advanced/assessed,advanced/applicants

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    start={f:digest(root/f) for f in FILES};review=json.loads((root/FILES[-1]).read_text());need(set(review['payloads'])==set(FILES[:-1]),'five nonself bindings')
    for f,b in review['payloads'].items():need(start[f]==b,'payload '+f)
    page=Page();page.feed((root/FILES[0]).read_text());source=json.loads((root/FILES[2]).read_text())
    need(not page.h1 and len(page.ids)==len(set(page.ids)),'unique IDs/no h1')
    tasks=['v18-c04-e'+str(i) for i in range(1,9)];need(page.exercises==page.answers==tasks,'eight matched complete tasks')
    need(page.worked==['v18-c04-case1','v18-c04-case2'],'two worked artifacts');need(set(page.sources)=={(s['id'],s['url']) for s in source['sources']},'sources')
    inputs={k:parse(v) for k,v in page.inputs.items()};shown={k:parse(v) for k,v in page.results.items()}
    need(set(inputs)=={'attrition','ratings','hedge-states','cash','finance-ratings','funnel'},'all visible primitives')
    attr=inputs['attrition'];x,y=inputs['hedge-states'];cash=inputs['cash'];z=hedge(x,y,cash);count=0
    expected={'bounds':(attr[1]-attr[3],)+identified(attr),'equal-missing-bounds':identified(attr,True),'moments':moments(x,y),'hedge-optimum':(z['center'],z['center_variance'],z['h'],z['variance'],z['cash']),'residuals':residual(x,y,z['h']),'missing-means-example':population(attr,F(4),F(8))}
    first,second,final=inputs['ratings'];need(len(first)==len(second)==len(final)==3,'three applicants')
    anchored=((4,0,1),(4,4,4),(4,4,3))
    need(final==anchored,'independently scored actual academic responses');count+=9
    for group in (first,second,final,inputs['finance-ratings']):
        for row in group:need(len(row)==3 and all(0<=v<=4 and v.denominator==1 for v in row),'rubric domains')
    expected['initial-totals']=tuple((sum(a)+sum(b))/2 for a,b in zip(first,second));expected['calibrated-totals']=tuple(sum(a) for a in final)
    table=page.tables['v18-c04-academic-scores'];need(len(table)==4,'actual calibration rows')
    for i,row in enumerate(table[1:]):
        rv,rt=row[4].rsplit(' / ',1)
        need(row[0]=='ABC'[i] and parse(row[1])==first[i] and parse(row[2])==second[i] and F(row[3])==expected['initial-totals'][i] and parse(rv)==final[i] and F(rt)==sum(final[i]),'visible calibration table');count+=6
    need(inputs['finance-ratings']==((4,1,1),(4,3,2),(4,4,4)),'independently scored exact financial responses');count+=9
    expected['finance-totals']=tuple(sum(v) for v in inputs['finance-ratings'])
    alternative=(F(1,2),attr[1],F(1,2),attr[3],attr[4],attr[5]);expected['equal-retention-bounds']=identified(alternative)
    rr=[rates(row) for row in inputs['funnel']];expected['funnel-rates']=tuple(rr[i][j] for j in range(3) for i in range(2))
    cash_cases=[hedge(x,y,(F(c),)+cash[1:]) for c in (11,8)];expected['cash-changes']=tuple((q['h'],q['variance'],q['cash']) for q in cash_cases)
    need(hedge(x,y,(F(4),)+cash[1:]) is None,'cash below floor empty');count+=1
    half=tuple(v/2 for v in y);mh=moments(x,half);zh=hedge(x,half,cash);expected['changed-hedge']=(mh[4],mh[3],zh['center'],zh['h'],zh['variance'])
    delay=hedge(x,y,(F(9),)+cash[1:]);expected['retention']=(population(attr,F(8),F(8))[2],delay['h'],delay['variance'],delay['cash'])
    need(set(shown)==set(expected),'every displayed numerical result')
    def leaves(v):return sum(leaves(t) for t in v) if isinstance(v,tuple) else 1
    for k,v in expected.items():need(shown[k]==v,'displayed '+k);count+=leaves(v)
    # Multiple observed-retention worlds; constructed potential records attain endpoints exactly.
    population_worlds=0
    for r,s in product((F(1,4),F(1,2),F(3,4)),repeat=2):
        data=(r,F(8),s,F(6),F(0),F(10));lo,hi=identified(data)
        for u,v in product((F(0),F(4),F(8),F(10)),repeat=2):
            value=population(data,u,v)[2];need(lo<=value<=hi,'constructed bounded effects');count+=1;population_worlds+=1
    for m in range(11):need(population(alternative,F(m),F(m))[2]==1,'equal retention/missing cancellation');count+=1
    for weight in (F(0),F(1,4),F(1),F(2)):
        scores=tuple(q+i+weight*c for q,i,c in final);need(scores[1]-scores[2]==weight,'weight boundary');count+=1
    need(final[0][1]<3 and final[1][1]>=3 and final[2][1]>=3,'identification gate');count+=3
    # Residual dispersion oracle checks positive, negative and zero covariance, two cash boundaries and cap binding.
    hedge_worlds=0
    for hstates,c,cap in product((y,tuple(-v for v in y),(F(2),)*4,half),(5,8,11),(0,1,3)):
        decision=hedge(x,hstates,(F(c),F(5),F(3),F(cap)));hedge_worlds+=1
        for j in range(9):
            candidate=decision['bound']*j/8;need(variance(residual(x,hstates,candidate))>=decision['variance'],'global finite witness');count+=1
        need(decision['cash']>=5,'cash feasible');count+=1
        if variance(hstates)==0:need(decision['unique']==(decision['bound']==0),'constant objective singleton exception');count+=1
    singleton=hedge(x,(F(2),)*4,(F(5),F(5),F(3),F(3)))
    interval=hedge(x,(F(2),)*4,cash)
    need(singleton['unique'] and singleton['h']==0 and not interval['unique'],'repaired zero variance wording witness');count+=2
    need(cash[0]-cash[2]*z['center']==4 and variance(residual(x,y,z['h']))>0,'infeasible unconstrained and residual risk');count+=2
    invalid=0
    bad=[lambda:population((0,8,F(1,2),6,0,10),0,0),lambda:population((F(3,2),8,F(1,2),6,0,10),0,0),lambda:population(attr,-1,0),lambda:population((F(3,4),11,F(1,2),6,0,10),0,0),lambda:hedge(x,y,(10,5,0,3)),lambda:hedge(x,y,(10,5,3,-1)),lambda:hedge(x,y,(True,5,3,3)),lambda:moments((),()),lambda:moments(x,y[:2]),lambda:rates((0,0,0)),lambda:rates((10,11,2)),lambda:rates((10,8,9)),lambda:rates((10,F(3,2),1)),lambda:parse('(1,0.5)')]
    for fn in bad:
        try:fn()
        except ValueError:invalid+=1
        else:raise ValueError('invalid input accepted')
    need(start=={f:digest(root/f) for f in FILES},'no runtime mutation')
    result={'chapter':'v18-c04','status':'passed','runtime_files':6,'worked_cases':2,'exercises':8,'result_groups':len(shown),'comparisons':count,'population_worlds':population_worlds,'hedge_worlds':hedge_worlds,'invalid_domains':invalid,'scope':'Independent primitive records and residual-dispersion oracle; full qualitative/proof review separate. Author checker opaque.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_c04_peer_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
