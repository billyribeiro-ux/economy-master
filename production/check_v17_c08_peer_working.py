"""Independent V17C08 primitive and assignment checks; opaque author checker."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
import ast,hashlib,json,sys
from itertools import product,combinations
AUTHOR=('production/v17-c08-working.html','production/check_v17_c08_working.py','production/v17-c08-sources-working.json','production/v17-c08-author-review-working.json')
SELF='production/check_v17_c08_peer_working.py';REVIEW='production/v17-c08-peer-review-working.json';FILES=AUTHOR+(SELF,REVIEW)
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(p):
    b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def parse(s):
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.Tuple):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('non-rational displayed primitive')
    return visit(ast.parse(s.strip(),mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.inputs={};self.results={};self.marker=None;self.sources=[];self.worked=[];self.tasks=[];self.answers=[];self.inside=False;self.details=0;self.h1=False;self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1=True
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='ol' and 'exercises' in a.get('class','').split():self.inside=True
        if tag=='li' and self.inside:self.tasks.append(a['id'])
        if tag=='details' and 'solutions' in a.get('class','').split():self.details+=1
        if 'data-solution-for' in a:need(self.details>0,'answer wrapper');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for k,d in [('data-input',self.inputs),('data-result',self.results)]:
            if k in a:need(a[k] not in d,'duplicate marker');d[a[k]]='';self.marker=(d,a[k])
        if tag=='table':self.table=a.get('id');self.tables[self.table]=[]
        if tag=='tr' and self.table:self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=''
    def handle_endtag(self,tag):
        if tag=='span':self.marker=None
        if tag=='ol':self.inside=False
        if tag=='details' and self.details:self.details-=1
        if tag in ('td','th') and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:self.tables[self.table].append(self.row);self.row=None
        if tag=='table':self.table=None
    def handle_data(self,text):
        if self.marker:self.marker[0][self.marker[1]]+=text
        if self.cell is not None:self.cell+=text

def screening(data):
    need(type(data) is tuple and len(data)==4 and all(type(x) in (int,F) and F(x).denominator==1 for x in data),'four integer counts')
    n,d,hit,false=map(int,data);need(n>0 and 0<=d<=n and 0<=hit<=d and 0<=false<=n-d,'count domain')
    # Build individual (default,flag) records rather than applying a stored Bayes formula.
    records=[(1,1)]*hit+[(1,0)]*(d-hit)+[(0,1)]*false+[(0,0)]*(n-d-false)
    cells=tuple(tuple(sum(x==o and z==f for x,z in records) for f in (1,0)) for o in (1,0))
    denom_d=sum(x for x,z in records);denom_f=sum(z for x,z in records);joint=sum(x*z for x,z in records)
    return cells,(F(joint,denom_d) if denom_d else None,F(joint,denom_f) if denom_f else None)

def accounts(rows):
    need(type(rows) is tuple and rows and all(type(r) is tuple and len(r)==2 for r in rows),'account pairs')
    need(all(type(x) in (int,F) for r in rows for x in r),'exact account inputs')
    rows=tuple(tuple(F(x) for x in r) for r in rows);need(all(v>=0 and rate>=-1 for v,rate in rows),'account domain')
    initial=sum(v for v,r in rows);need(initial>0,'positive total')
    gains=tuple(v*r for v,r in rows);ends=tuple(v+g for (v,r),g in zip(rows,gains))
    return ends,initial,sum(ends),sum(gains)/initial,sum(r for v,r in rows)/len(rows)

def completion_means(scores):
    need(type(scores) is tuple and scores and all(x is None or (type(x) is int and 0<=x<=2) for x in scores),'score domain')
    holes=[i for i,x in enumerate(scores) if x is None];means=[]
    for fill in product(range(3),repeat=len(holes)):
        full=list(scores)
        for i,x in zip(holes,fill):full[i]=x
        means.append(F(sum(full),len(full)))
    return tuple(sorted(set(means))),3**len(holes)

def assignment(y0,y1):
    need(type(y0) is tuple and type(y1) is tuple and len(y0)==len(y1)==8,'eight potentials')
    need(all(type(x) in (int,F) and 0<=x<=2 for x in y0+y1),'score support')
    outcomes=[];margins=[0]*8
    for treated in combinations(range(8),4):
        z=set(treated)
        outcomes.append(sum(F(y1[i],4) if i in z else -F(y0[i],4) for i in range(8)))
        for i in z:margins[i]+=1
    return tuple(outcomes),tuple(margins),sum(F(b-a,8) for a,b in zip(y0,y1))

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before={f:digest(root/f) for f in FILES};review=json.loads((root/REVIEW).read_text())
    need(set(review['payloads'])==set(FILES)-{REVIEW},'five nonself bindings')
    for path,binding in review['payloads'].items():need(before[path]==binding,'peer binding '+path)
    author=json.loads((root/AUTHOR[3]).read_text())
    for path,binding in author['payloads'].items():need(before[path]==binding,'author binding '+path)
    p=Page();p.feed((root/AUTHOR[0]).read_text());source=json.loads((root/AUTHOR[2]).read_text())
    need(not p.h1 and len(p.ids)==len(set(p.ids)),'unique HTML IDs')
    tasks=['v17-c08-e'+str(i) for i in range(1,9)];need(p.tasks==p.answers==tasks,'eight matched answers');need(p.worked==['v17-c08-case1','v17-c08-case2'],'two complete artifacts')
    need(set(p.sources)=={(s['id'],s['url']) for s in source['sources']},'exact source links')
    inp={k:parse(v) for k,v in p.inputs.items()};out={k:parse(v) for k,v in p.results.items()};count=0
    need(set(inp)=={'screen','screen-fresh','screen-delayed','accounts','accounts-fresh','accounts-delayed','retrieval-scores','restudy-scores'},'all primitive markers')
    expected={}
    for key,result in [('screen','conditionals'),('screen-fresh','fresh-conditionals'),('screen-delayed','delayed-conditionals')]:expected[result]=screening(inp[key])[1]
    expected['transfer-posterior']=screening((1000,200,160,80))[1][1]
    table=p.tables['v17-c08-screen-table'];cells,_=screening(inp['screen']);need(len(table)==4,'screen table length')
    tab=[cells[0]+(sum(cells[0]),),cells[1]+(sum(cells[1]),),tuple(cells[0][j]+cells[1][j] for j in range(2))+(sum(sum(r) for r in cells),)]
    for row,vals in zip(table[1:],tab):need(tuple(F(v) for v in row[1:])==vals,'count table');count+=3
    a=accounts(inp['accounts']);f=accounts(inp['accounts-fresh']);d=accounts(inp['accounts-delayed'])
    expected['account-values']=a[0]+a[1:4];expected['fresh-account-values']=f[0]+(f[3],f[4]);expected['delayed-account-values']=d[0]+(d[3],)
    contribution=F(100);expected['flow-transfer']=((a[2]+contribution-a[1])/a[1],(a[2]+contribution-contribution-a[1])/a[1])
    nexta=accounts(((200,F(1,10)),));expected['next-flow']=(nexta[2]+30,(nexta[2]+30-nexta[1])/nexta[1],nexta[3])
    rows=p.tables['v17-c08-register'][1:];need(len(rows)==6 and [r[0] for r in rows]==list('ABCDEF'),'exact register')
    initial=tuple(int(r[1]) for r in rows);assisted=tuple(int(r[2]) for r in rows);delayed=tuple(None if r[3]=='—' else int(r[3]) for r in rows)
    im=F(sum(initial),6);am=F(sum(assisted),6);observed=tuple(x for x in delayed if x is not None);rm=F(sum(observed),len(observed));means,completions=completion_means(delayed)
    expected['record-means']=(im,am,rm);expected['record-bounds']=(min(means),max(means),min(means)-im,max(means)-im)
    expected['e2']=(screening((1000,50,40,95))[1][1],screening((1000,500,400,50))[1][1])
    need(screening((100,10,0,0))[1]==(F(0),None),'empty flags undefined');count+=2
    expected['e3-changed']=screening((100,10,1,0))[1]
    expected['e4']=(accounts(((250,F(1,5)),(250,0)))[3],accounts(((200,F(1,5)),(800,0)))[3])
    updated=list(delayed);updated[2]=1;newmeans,_=completion_means(tuple(updated));observednew=[x for x in updated if x is not None]
    expected['e5']=(min(newmeans),max(newmeans),min(newmeans)-im,max(newmeans)-im,F(sum(observednew),len(observednew)))
    paired=[i for i,x in enumerate(delayed) if x is not None];pm=F(sum(initial[i] for i in paired),len(paired));expected['e6']=(pm,rm,rm-pm)
    t=inp['retrieval-scores'];c=inp['restudy-scores'];tm=sum(t)/4;cm=sum(c)/4;expected['e7']=(tm,cm,tm-cm)
    expected['e8']=screening((500,50,40,45))[1]+screening((400,80,64,32))[1]
    ret=accounts(((100,F(1,10)),(300,F(-1,10))));expected['retention']=(F(10),F(-30),ret[2]-ret[1],ret[1],ret[3])
    need(set(expected)==set(out),'every displayed result group')
    for key,v in expected.items():need(out[key]==v,'result '+key);count+=len(v) if isinstance(v,tuple) else 1
    # Two full potential schedules fit the observed first-four treated assignment yet differ in ATE.
    schedules=[((F(0),)*4+c,t+(F(0),)*4),(t+c,t+c),((0,2,1,0,2,1,0,2),(1,2,2,0,1,2,1,0))]
    assignment_worlds=0
    for index,(y0,y1) in enumerate(schedules):
        diffs,margins,ate=assignment(y0,y1);need(len(diffs)==70 and margins==(35,)*8,'uniform four-of-eight');need(sum(diffs)/len(diffs)==ate,'unbiased finite estimator');count+=10;assignment_worlds+=len(diffs)
        if index<2:need(diffs[0]==tm-cm and ate!=diffs[0],'same observation different average');count+=2
    need(assignment(*schedules[0])[2]==F(1,4) and assignment(*schedules[1])[2]==0,'distinct compatible effects');count+=2
    need(means==tuple(F(5+i,6) for i in range(5)) and completions==9,'integer support grid');count+=6
    need(completion_means((None,None))[0]==(F(0),F(1,2),F(1),F(3,2),F(2)),'all missing bounds');count+=5
    need(completion_means((0,2))[0]==(F(1),),'complete roster');count+=1
    need(screening((100,0,0,10))[1]==(None,F(0)) and screening((100,100,50,0))[1]==(F(1,2),F(1)),'absent outcome groups');count+=4
    need(screening((1000,50,40,160))[1][1]==F(1,5),'diagnostic changed flags');count+=1
    for data in [((0,F(2)),(100,F(-1))),((100,F(1,5)),(100,F(1,5))),((100,F(-1)),(900,F(-1)))]:
        result=accounts(data);need(result[3]==sum(F(v)*r for v,r in data)/sum(v for v,r in data),'weight boundaries');count+=1
    invalid=0
    bad=[(screening,(0,0,0,0)),(screening,(100,101,0,0)),(screening,(100,10,11,0)),(screening,(100,10,0,91)),(screening,(100,True,0,0)),(accounts,((0,0),(0,0))),(accounts,((-1,0),(100,0))),(accounts,((100,-2),)),(accounts,((100,0.1),)),(completion_means,(0,3)),(completion_means,(True,None)),(assignment,((0,)*7,(0,)*7))]
    for fn,data in bad:
        try:fn(*data) if fn is assignment else fn(data)
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(before=={f:digest(root/f) for f in FILES},'mutation')
    result={'chapter':'v17-c08','status':'passed','runtime_files':6,'worked_packets':2,'exercises':8,'result_groups':len(out),'comparisons':count,'integer_missing_completions':completions,'assignment_worlds':assignment_worlds,'invalid_domains':invalid,'scope':'Independent full qualitative/proof review plus primitive oracles; no actual learner evidence or human certification.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v17_c08_peer_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
