"""Independent V17C04 primitive and sharpness checks; opaque author checker."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
import ast,hashlib,json,sys
AUTHOR=('content/chapters/v17-c04.html','scripts/check_v17_c04.py','content/reviews/v17-c04-sources.json','content/reviews/v17-c04-author.json')
SELF='scripts/check_v17_c04_peer.py';REVIEW='content/reviews/v17-c04-peer.json';FILES=AUTHOR+(SELF,REVIEW)
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

def support(v):
    need(type(v) is tuple and len(v)==5 and all(type(x) in (int,F) for x in v),'support primitives')
    p,m1,m0,L,U=v;need(0<p<1 and L<U and L<=m0<=U and L<=m1<=U,'support domain')
    lower=(p*m1+(1-p)*L)-(p*U+(1-p)*m0)
    upper=(p*m1+(1-p)*U)-(p*L+(1-p)*m0)
    return m1-m0,lower,upper,upper-lower

def observed(rows):
    need(type(rows) is tuple and rows and all(type(r) is tuple and len(r)==5 for r in rows),'type rows')
    need(all(all(type(x) in (int,F) for x in row) for row in rows),'exact type primitives')
    need(sum(r[0] for r in rows)==1 and all(r[0]>=0 and r[1] in (0,1) and r[2] in (0,1) and 0<=r[3]<=10 and 0<=r[4]<=10 for r in rows),'population domain')
    d=[];y=[]
    for z in (0,1):
        d.append(sum(r[0]*r[z+1] for r in rows));y.append(sum(r[0]*r[3+int(r[z+1])] for r in rows))
    ate=sum(r[0]*(r[4]-r[3]) for r in rows)
    return tuple(d+y),d[1]-d[0],y[1]-y[0],ate

def late(rows):
    result,fs,rf,ate=observed(rows);need(all(r[2]>=r[1] for r in rows),'no defiers required');need(fs>0,'positive complier share required');return result,(fs,rf,rf/fs,ate)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before={f:digest(root/f) for f in FILES};review=json.loads((root/REVIEW).read_text());need(set(review['payloads'])==set(FILES)-{REVIEW},'five nonself bindings')
    for f,h in review['payloads'].items():need(before[f]==h,'peer binding '+f)
    author=json.loads((root/AUTHOR[3]).read_text())
    for f,h in author['payloads'].items():need(before[f]==h,'author binding '+f)
    p=Page();p.feed((root/AUTHOR[0]).read_text());source=json.loads((root/AUTHOR[2]).read_text())
    need(not p.h1 and len(p.ids)==len(set(p.ids)),'IDs/headings');tasks=['v17-c04-ex'+str(i) for i in range(1,9)];need(p.tasks==p.answers==tasks,'eight matched answers');need(p.worked==['v17-c04-case1','v17-c04-case2'],'two complete artifacts')
    need(set(p.sources)=={(s['id'],s['url']) for s in source['sources']},'bounded source links')
    inputs={k:parse(v) for k,v in p.inputs.items()};shown={k:parse(v) for k,v in p.results.items()};expected={};count=0
    need(len(inputs)==11 and len(shown)==17,'complete primitive/result set')
    expected['hours']=(sum(inputs['hours']),6*sum(inputs['hours']));expected['weights']=sum(inputs['weights']);need(expected['weights']==100,'course weights')
    need(len(p.tables['v17-c04-calendar'])==7,'six full calendar rows')
    b=support(inputs['bounds']);expected['bounds']=b;expected['monotone']=(F(0),b[2])
    typ=inputs['types'];obs,effects=late(typ);expected['observed']=obs;expected['effects']=effects
    rowtable=p.tables['v17-c04-types'][1:];need(len(rowtable)==len(typ),'type table rows')
    for row,w in zip(rowtable,typ):need(tuple(F(x) for x in row[1:])==w,'actual type table');count+=5
    worlds=[]
    for a in range(11):
        for n in range(11):
            changed=(typ[0][:3]+(F(a),typ[0][4]),typ[1],typ[2][:4]+(F(n),))
            new,fs,rf,ate=observed(changed);need(new==obs and rf/fs==effects[2],'same-observation world');worlds.append((a,n,ate));count+=5
    lo=min(w[2] for w in worlds);hi=max(w[2] for w in worlds);expected['ate-range']=(lo,hi)
    cost,extra=inputs['policy-cost'];expected['encouragement-net']=effects[1]-cost*effects[0]-extra;expected['universal-net']=(lo-cost,hi-cost)
    direct=inputs['direct'];expected['direct-effect']=(direct,effects[1]+direct,(effects[1]+direct)/effects[0],effects[2])
    restricted=[ate-cost for a,n,ate in worlds if a-n<=2];expected['restricted-net']=(min(restricted),max(restricted))
    changed=support(inputs['ex-bounds']);expected['ex-bounds']=changed[:3]+(F(0),changed[2]);expected['ex-world']=(effects[3],hi)
    masses=inputs['defier-masses'];treat=inputs['defier-effects'];defiers=((masses[0],0,1,0,treat[0]),(masses[1],1,0,0,treat[1]),(masses[2],1,1,1,1),(masses[3],0,0,1,1))
    dobs,dfs,drf,date=observed(defiers);expected['defiers']=(dfs,drf,drf/dfs);need(dobs==(F(3,10),F(3,5),F(13,10),F(13,10)),'defier observed means');count+=4
    rf,fs,klo,khi=inputs['sensitivity'];need(fs>0 and klo<=khi,'sensitivity domain');expected['sensitivity']=((rf-khi)/fs,(rf-klo)/fs)
    expected['workload-repair']=(F(10),F(2))+inputs['hours']
    robs,reffects=late(inputs['retention']);expected['retention']=robs+reffects
    need(set(expected)==set(shown),'all displayed values')
    for key,value in expected.items():need(shown[key]==value,'result '+key);count+=len(value) if isinstance(value,tuple) else 1
    # Independent attainable worlds check general affine constructions; manual proof covers every lambda.
    for sample in (inputs['bounds'],inputs['ex-bounds']):
        share,m1,m0,L,U=sample;diff,lower,upper,width=support(sample)
        for j in range(9):
            lam=F(j,8);u=L+lam*(U-L);v=U-lam*(U-L)
            actual=share*(m1-v)+(1-share)*(u-m0)
            need(actual==lower+lam*width,'every-interior witness')
            mono=share*(m1-((1-lam)*m1+lam*L))+(1-share)*(((1-lam)*m0+lam*U)-m0)
            need(mono==lam*upper,'monotone response mixture');count+=2
    # Mean independence is sufficient, not necessary, for equality to observed difference.
    need(F(2,5)*(7-F(11,2))+F(3,5)*(8-4)==3,'non-independent equality witness');count+=1
    # Restricted policy boundary is strict; zero is attained at a-n=3.
    zero=(typ[0][:3]+(F(3),typ[0][4]),typ[1],typ[2][:4]+(F(0),));need(observed(zero)[3]-cost==0,'policy sign boundary');count+=1
    invalid=0
    for v in ((0,7,4,0,10),(1,7,4,0,10),(F(1,2),11,4,0,10),(F(1,2),7,4,10,0)):
        try:support(v)
        except ValueError:invalid+=1
        else:raise ValueError('invalid support accepted')
    cases=[((F(1),1,1,4,6),),defiers,((F(1),0,1,0,11),),((F(1,2),0,1,0,1),)]
    for rows in cases:
        try:late(rows)
        except ValueError:invalid+=1
        else:raise ValueError('invalid LATE contract accepted')
    need(before=={f:digest(root/f) for f in FILES},'runtime mutation')
    result={'chapter':'v17-c04','status':'passed','runtime_files':6,'worked_artifacts':2,'exercises':8,'seminar_weeks':6,'numeric_markers':17,'comparisons':count,'same_observation_worlds':len(worlds),'invalid_domains':invalid,'scope':'Independent complete syllabus/proof/artifact/source review; primitive numeric checks supplement proofs, no actual learner or external human evidence.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v17_c04_peer_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
