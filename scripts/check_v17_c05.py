"""V17C05 arithmetic and artifact gates; teaching/score judgment recorded separately."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib,json,sys
FILES=('content/chapters/v17-c05.html','scripts/check_v17_c05.py','content/reviews/v17-c05-sources.json','content/reviews/v17-c05-author.json')
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

def project(cost,payoff,rate):
    need(all(type(x) in (int,F) for x in (cost,payoff,rate)),'exact inputs required')
    need(cost>0 and payoff>=0 and rate>-1,'project domain')
    # Date-one opportunity cost independently compares the terminal surplus.
    future_surplus=payoff-cost*(1+rate)
    return F(future_surplus)/(1+rate),F(payoff-cost)/cost

def missing(data):
    need(type(data) is tuple and len(data)==6 and all(type(x) is int for x in data),'six integer counts')
    n,s,m,k,t,l=data
    need(n>0 and k>0 and 0<=m<=n and 0<=l<=k and 0<=s<=n-m and 0<=t<=k-l,'valid roster counts')
    rows=[]
    for a,b in product(range(m+1),range(l+1)):
        left,right=F(s+a,n),F(t+b,k);rows.append((a,b,left,right,left-right))
    return rows,tuple(sorted({r[-1] for r in rows}))

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    original={p:digest(root/p) for p in FILES};review=json.loads((root/FILES[3]).read_text())
    need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for p,b in review['payloads'].items():need(original[p]==b,'payload '+p)
    p=Page();p.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text())
    need(not p.h1 and len(set(p.ids))==len(p.ids),'HTML headings and IDs');tasks=['v17-c05-ex'+str(i) for i in range(1,9)]
    need(p.exercises==p.answers==tasks,'eight exact solutions');need(p.worked==['v17-c05-case1','v17-c05-case2'],'two assessment sets')
    need(set(p.sources)=={(s['id'],s['url']) for s in sources['sources']},'source references')
    inputs={k:values(v) for k,v in p.inputs.items()};shown={k:values(v) for k,v in p.results.items()};count=0
    need(set(inputs)=={'projects','missing','score-a','score-b','exercise-projects'},'actual primitive groups')
    ca,xa,cb,xb,r,budget,high=inputs['projects'];va,ra=project(ca,xa,r);vb,rb=project(cb,xb,r);crossover=(xb-xa)/(cb-ca)-1
    expected={'base-npv':(va,vb),'returns':(ra,rb),'high-rate-npv':(project(ca,xa,high)[0],project(cb,xb,high)[0]),'crossover':(crossover,),'cross-value':(project(ca,xa,crossover)[0],)}
    need(vb>va>0 and ca<=budget<cb,'base and funding decisions');need(max(expected['high-rate-npv'])<0,'outside at high rate');count+=4
    need(project(ca,xa,crossover)[0]==project(cb,xb,crossover)[0],'crossover equality');count+=1
    for rate in (crossover-F(1,10),crossover+F(1,10)):
        diff=project(cb,xb,rate)[0]-project(ca,xa,rate)[0];need((diff>0)==(rate<crossover),'ranking boundary');count+=1
    raw=inputs['missing'];need(all(x.denominator==1 for x in raw),'integer missing primitives');data=tuple(int(x) for x in raw);rows,possible=missing(data);n,s,m,k,t,l=data
    expected.update({'complete-case':(F(s,n-m)-F(t,k-l),),'missing-set':possible,'verified-set':tuple(sorted({row[-1] for row in rows if row[0]==1})),'comparison-verified':tuple(sorted({row[-1] for row in rows if row[1]==1}))})
    need(expected['complete-case'][0] not in possible and min(possible)<expected['complete-case'][0]<max(possible),'discrete set versus containing interval');count+=1
    for name in ('a','b'):
        points=p.points['v17-c05-rubric-'+name];need(sum(points)==20 and len(points)==5,'additive rubric');earned=inputs['score-'+name];need(len(earned)==len(points) and all(0<=x<=limit for x,limit in zip(earned,points)),'criterion score domain');expected['score-'+name]=(sum(earned),);count+=5
    need(p.points['v17-c05-rubric-a']==[4,4,4,4,4] and p.points['v17-c05-rubric-b']==[4,6,4,4,2],'exact rubric weights')
    a,x,b,y,rate,cap=inputs['exercise-projects'];eva,era=project(a,x,rate);evb,erb=project(b,y,rate)
    expected.update({'exercise-npv':(eva,evb),'exercise-returns':(era,erb),'exercise-score':(F(3),F(4),F(4),F(4),F(4),F(19))})
    need(evb>eva>0 and a<=cap<b,'exercise choices');count+=2
    need(set(shown)==set(expected),'complete result coverage')
    for key,v in expected.items():need(shown[key]==v,'result '+key);count+=len(v)
    table=p.tables['v17-c05-project-table'][1:];expectrows=[('A',ca,va+ca,va,ra),('B',cb,vb+cb,vb,rb)]
    for row,w in zip(table,expectrows):need(row[0]==w[0] and tuple(F(x) for x in row[1:])==w[1:],'project table');count+=4
    need(len(table)==2,'complete project rows')
    displayed=p.tables['v17-c05-missing-table'][1:];need(len(displayed)==len(rows),'complete missing rows')
    for row,w in zip(displayed,rows):need(tuple(F(x) for x in row)==w,'missing table');count+=5
    # Assessments need outside, ties, all-missing and no-missing boundaries.
    need(project(40,66,F(1,10))[0]==project(100,132,F(1,10))[0]==20,'transfer tie');count+=2
    need(project(40,55,F(3,8))[0]==0,'outside tie');count+=1
    for d,lo,hi in [((4,2,0,4,1,0),F(1,4),F(1,4)),((2,0,2,2,0,2),F(-1),F(1)),((4,0,0,4,4,0),F(-1),F(-1))]:
        _,v=missing(d);need(min(v)==lo and max(v)==hi,'missing boundaries');count+=2
    invalid=0
    for args in [(0,10,0),(10,-1,0),(10,10,-1),(True,10,0),(10,10,0.1)]:
        try:project(*args)
        except ValueError:invalid+=1
        else:raise ValueError('project domain accepted')
    for d in ((0,0,0,4,1,0),(4,4,1,4,1,1),(4,1,-1,4,1,1),(4,1,1,4,True,1)):
        try:missing(d)
        except ValueError:invalid+=1
        else:raise ValueError('missing domain accepted')
    need(original=={f:digest(root/f) for f in FILES},'runtime mutation')
    summary={'chapter':'v17-c05','status':'passed','runtime_files':4,'worked_assessment_sets':2,'exercises':8,'rubric_points':[20,20],'input_groups':len(inputs),'result_groups':len(shown),'comparisons':count,'invalid_domains':invalid,'scope':'Arithmetic/artifact checks; complete qualitative assessment/scoring/proof review recorded separately, no empirical validation.'}
    json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v17_c05_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
