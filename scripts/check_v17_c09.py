"""V17C09 artifact and numerical gates; full supervision/proof review recorded separately."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib,json,sys
FILES=('content/chapters/v17-c09.html','scripts/check_v17_c09.py','content/reviews/v17-c09-sources.json','content/reviews/v17-c09-author.json')
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

def wage(data):
    need(type(data) is tuple and len(data)==6 and all(type(x) in (int,F) for x in data),'exact wage inputs')
    l0,h0,l1,h1,s0,s1=tuple(F(x) for x in data)
    need(min(l0,h0,l1,h1)>=0 and 0<=s0<=1 and 0<=s1<=1,'wage/share domain')
    start=s0*l0+(1-s0)*h0;end=s1*l1+(1-s1)*h1;fixed=s0*l1+(1-s0)*h1
    need(start>0,'positive baseline for growth')
    within=fixed-start;between=end-fixed
    alternate=s1*(l1-l0)+(1-s1)*(h1-h0)
    other=(s1-s0)*l0+(s0-s1)*h0
    return (start,end,fixed,(end-start)/start,(fixed-start)/start,within,between,end-start,alternate,other)

def firm(data):
    need(type(data) is tuple and len(data)==4 and all(type(x) in (int,F) for x in data),'exact firm inputs')
    a,b,k,f=tuple(F(x) for x in data);need(a>=0 and b>0 and k>0 and f>=0,'firm domain')
    # Independently compare feasible stationary point, capacity and the outside payoff.
    candidates={F(0):F(0),k:a*k-b*k*k/2-f}
    stationary=F(a)/b
    if 0<stationary<=k:candidates[stationary]=a*stationary-b*stationary*stationary/2-f
    best=max(candidates.values());choices=tuple(sorted(q for q,v in candidates.items() if v==best))
    q=min(k,stationary);gross=a*q-b*q*q/2
    return q,gross,gross-f,choices,best

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    original={p:digest(root/p) for p in FILES};review=json.loads((root/FILES[3]).read_text())
    need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for path,binding in review['payloads'].items():need(original[path]==binding,'binding '+path)
    page=Page();page.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text())
    need(not page.h1 and len(set(page.ids))==len(page.ids),'HTML/unique IDs')
    tasks=['v17-c09-ex'+str(i) for i in range(1,9)]
    need(page.exercises==page.answers==tasks,'eight matched full solutions')
    need(page.worked==['v17-c09-case1','v17-c09-case2'],'two supervision artifacts')
    need(set(page.sources)=={(s['id'],s['url']) for s in sources['sources']},'source URLs')
    inputs={k:values(v) for k,v in page.inputs.items()};shown={k:values(v) for k,v in page.results.items()}
    need(set(inputs)=={'wages','wage-transfer','firm','firm-transfer','firm-exercise','firm-retention'},'all primitives')
    count=0
    w=wage(inputs['wages']);t=wage(inputs['wage-transfer'])
    expected={'wage-means':w[:5],'decomposition':w[5:8],'alternative-decomposition':(w[8],w[9],w[7]),'wage-transfer':(t[1],t[2],t[3],t[4],t[5],t[6],t[7])}
    a,b,k,f=inputs['firm'];base=firm((a,b,k,f));tie=firm((a,b,k,F(9)));outside=firm((a,b,k,F(10)));cap=firm((a,b,F(2),f))
    expected['firm-cases']=base[:3]+tie[:3]+outside[:3]+cap[:3]
    expected['firm-transfer']=firm(inputs['firm-transfer'])[:3]
    a,b,k,f=inputs['firm-exercise'];rows=[firm((a,b,k,f+d)) for d in (0,1,2)]
    expected['firm-exercise']=sum((r[:3] for r in rows),())
    a,b,k,f=inputs['firm-retention'];r=firm((a,b,k,f));q=F(1,2)
    expected['firm-retention']=r[:3]+(a*q-b*q*q/2-f,)
    delayed=wage((F(20),F(40),F(20),F(40),F(4,5),F(1,2)))
    expected['delayed-wages']=(delayed[0],delayed[1],delayed[3],delayed[5],delayed[6])
    need(set(shown)==set(expected),'every numeric result group')
    for key,v in expected.items():need(shown[key]==v,'displayed result '+key);count+=len(v)
    for result,choice in [(base,(F(3),)),(tie,(F(0),F(3))),(outside,(F(0),)),(cap,(F(2),)),(firm(inputs['firm-transfer']),(F(0),)),(rows[0],(F(3),)),(rows[1],(F(0),F(3))),(rows[2],(F(0),)),(r,(F(0),F(1)))]:need(result[3]==choice,'global choice');count+=1
    table=page.tables['v17-c09-wages'];need(len(table)==3,'two wage rows')
    l0,h0,l1,h1,s0,s1=inputs['wages']
    for row,label,vals in [(table[1],'L',(l0,l1,s0,s1)),(table[2],'H',(h0,h1,1-s0,1-s1))]:
        need(row[0]==label and tuple(F(v) for v in row[1:])==vals,'visible wage table');count+=4
    milestone=page.tables['v17-c09-milestones-a'];need([r[0] for r in milestone[1:]]==['1','2','3','4'],'four full milestones')
    # Different accounting conventions share the same total, including zero share changes.
    for data in [(20,40,22,44,F(4,5),F(4,5)),(20,40,20,40,F(4,5),F(1,5)),(20,40,22,42,F(4,5),F(1,5)),(0,40,0,0,F(0),F(1))]:
        z=wage(tuple(F(v) for v in data));need(z[5]+z[6]==z[7]==z[8]+z[9],'decomposition identity');count+=2
    need(w[8]-w[5]==F(6,5) and w[6]-w[9]==F(6,5),'interaction');count+=2
    need(t[1]>t[0] and inputs['wage-transfer'][3]<inputs['wage-transfer'][1],'aggregate/group reversal');count+=2
    # Enumerate valid primitive variations and verify every candidate against a feasible grid.
    worlds=0
    for a in (F(0),F(2),F(6)):
        for b in (F(1),F(2)):
            for k in (F(1),F(3),F(4)):
                gross=firm((a,b,k,F(0)))[1]
                for fixed in (F(0),gross,gross+1):
                    out=firm((a,b,k,fixed));worlds+=1
                    for j in range(1,9):
                        q=k*j/8;value=a*q-b*q*q/2-fixed
                        need(value<=out[4],'global optimum beats grid');count+=1
                    need(out[4]>=0,'outside retained');count+=1
                    if a==0:need(out[3]==(F(0),),'zero-a unique outside');count+=1
    # At the primary tie the midpoint is strictly worse; equal capacity/stationary boundary agrees.
    need(F(6)*F(3,2)-F(3,2)**2-9==F(-9,4),'nonconvex optimal set');count+=1
    edge=firm((F(6),F(2),F(3),F(5)));need(edge[:3]==base[:3] and edge[3]==base[3],'stationary at capacity');count+=1
    invalid=0
    for data in [(0,0,1,1,F(1,2),F(1,2)),(20,40,22,44,-1,0),(20,40,-1,44,0,0),(20,40,22,44,True,0)]:
        try:wage(data)
        except ValueError:invalid+=1
        else:raise ValueError('invalid wage accepted')
    for data in [(-1,2,4,5),(6,0,4,5),(6,2,0,5),(6,2,4,-1),(True,2,4,5),(6,2,4,0.5)]:
        try:firm(data)
        except ValueError:invalid+=1
        else:raise ValueError('invalid firm accepted')
    need(original=={p:digest(root/p) for p in FILES},'runtime mutation')
    result={'chapter':'v17-c09','status':'passed','runtime_files':4,'worked_supervision_cases':2,'exercises':8,'input_groups':len(inputs),'result_groups':len(shown),'comparisons':count,'firm_worlds':worlds,'invalid_domains':invalid,'scope':'Artifact/numerical checks supplement full qualitative/proof review; no actual supervision or independence certified.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v17_c09_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
