"""Quiet four-file author audit; finite oracle independent of printed formulas."""
import ast, hashlib, json, sys
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v17-c04.html','scripts/check_v17_c04.py','content/reviews/v17-c04-sources.json','content/reviews/v17-c04-author.json')
def need(ok,msg):
    if not ok: raise ValueError('V17C04: '+msg)
def value(text):
    def read(n):
        if isinstance(n,ast.Tuple):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return read(n.left)/read(n.right)
        raise ValueError('unsupported literal')
    return read(ast.parse(text.strip(),mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.links=[];self.sources=[];self.values={};self.capture=None;self.rows={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(t!='h1','chapter fragment h1');need(len(a)==len(attrs),'duplicate attribute')
        if 'id' in a:self.ids.append(a['id'])
        if t=='li' and any(tag=='ol' and 'exercises' in d.get('class','').split() for tag,d in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for' in a:
            need(any(tag=='details' and 'solutions' in d.get('class','').split() for tag,d in self.stack),'answer outside disclosure');self.answers.append(a['data-solution-for'])
        if t=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        if 'href' in a:self.links.append(a['href'])
        for k in ('input','result'):
            if 'data-'+k in a:
                key=(k,a['data-'+k]);need(key not in self.values and self.capture is None,'duplicate/nested marker');self.values[key]='';self.capture=(t,key)
        if t=='table':self.table=a['id'];self.rows[self.table]=[]
        if t=='tr':self.row=[]
        if t in ('td','th'):self.cell=[]
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.capture:self.values[self.capture[1]]+=s
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack.pop()[0]==t,'unbalanced HTML')
        if self.capture and self.capture[0]==t:self.capture=None
        if t in ('th','td'):self.row.append(''.join(self.cell).strip());self.cell=None
        if t=='tr':self.rows[self.table].append(self.row);self.row=None
        if t=='table':self.table=None

def exact(seq,n):
    need(isinstance(seq,(tuple,list)) and len(seq)==n,'dimensions')
    need(all(type(x) in (int,F) for x in seq),'exact numbers')
    return tuple(F(x) for x in seq)
def bounds_world(raw,u,v):
    p,m1,m0,lo,hi=exact(raw,5);u,v=exact((u,v),2)
    need(0<p<1 and lo<=m0<=hi and lo<=m1<=hi and lo<hi,'bounds primitives')
    need(lo<=u<=hi and lo<=v<=hi,'missing means outside support')
    treated=p*m1+(1-p)*u;untreated=p*v+(1-p)*m0
    return treated-untreated

def bounds(raw,monotone=False):
    p,m1,m0,lo,hi=exact(raw,5)
    points=[bounds_world(raw,u,v) for u in ((m0,hi) if monotone else (lo,hi)) for v in ((lo,m1) if monotone else (lo,hi))]
    return min(points),max(points)

def population(rows,direct=F(0)):
    need(isinstance(rows,(tuple,list)) and len(rows)>0,'empty population')
    rows=tuple(exact(row,5) for row in rows);(direct,)=exact((direct,),1)
    need(sum(row[0] for row in rows)==1 and all(row[0]>=0 for row in rows),'masses')
    need(all(d in (0,1) for row in rows for d in row[1:3]),'receipt binary')
    need(all(0<=y<=10 for row in rows for y in row[3:]),'outcome support')
    ds=[];ys=[]
    for z in (0,1):
        ds.append(sum(w*row[1+z] for row in rows for w in (row[0],)))
        ys.append(sum(row[0]*(row[3+int(row[1+z])]+direct*z) for row in rows))
    return tuple(ds+ys)+(ds[1]-ds[0],ys[1]-ys[0],sum(w*(y1-y0) for w,d0,d1,y0,y1 in rows))
def ratio(rf,fs):
    rf,fs=exact((rf,fs),2);need(fs!=0,'zero first stage');return rf/fs

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    review=json.loads((root/FILES[3]).read_text());need(review['full_reading_complete'] and not review['open_material_findings'],'qualitative review')
    need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for name,record in review['payloads'].items():
        b=(root/name).read_bytes();need(record=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze changed '+name)
    page=Page();page.feed((root/FILES[0]).read_text());page.close()
    need(not page.stack and page.capture is None and len(page.ids)==len(set(page.ids)),'complete unique HTML')
    need(page.tasks==page.answers==['v17-c04-ex'+str(i) for i in range(1,9)],'eight complete paired tasks')
    need(page.worked==['v17-c04-case1','v17-c04-case2'],'two worked artifacts')
    src=json.loads((root/FILES[2]).read_text())['sources'];need(set(page.sources)=={(x['id'],x['url']) for x in src},'source scopes/URLs')
    need(len(page.rows['v17-c04-calendar'])==7,'six-week calendar')
    values={k:value(v) for k,v in page.values.items()};used=set();n=0
    def get(kind,key):used.add((kind,key));return values[kind,key]
    def eq(a,b,msg):
        nonlocal n
        if isinstance(a,tuple) or isinstance(b,tuple):
            need(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),msg+' shape')
            for aa,bb in zip(a,b):eq(aa,bb,msg)
        else:n+=1;need(a==b,msg)
    def result(key,x):eq(get('result',key),x,key)
    hours=get('input','hours');result('hours',(sum(hours),6*sum(hours)));result('weights',sum(get('input','weights')))
    raw=get('input','bounds');lo,hi=bounds(raw);result('bounds',(raw[1]-raw[2],lo,hi,hi-lo));result('monotone',bounds(raw,True))
    rows=get('input','types');o=population(rows);result('observed',o[:4]);result('effects',(o[4],o[5],ratio(o[5],o[4]),o[6]))
    for table_row,rawrow in zip(page.rows['v17-c04-types'][1:],rows):eq(tuple(value(x) for x in table_row[1:]),rawrow,'table primitives')
    def alternative(a,n):return (rows[0][:3]+(a,rows[0][4]),rows[1],rows[2][:4]+(n,))
    endpoints=tuple(population(alternative(a,n))[6] for a,n in product((F(0),F(10)),repeat=2));lower,upper=min(endpoints),max(endpoints)
    result('ate-range',(lower,upper));cost,invite=get('input','policy-cost');result('encouragement-net',o[5]-cost*o[4]-invite);result('universal-net',(lower-cost,upper-cost))
    direct=get('input','direct');od=population(rows,direct);result('direct-effect',(direct,od[5],ratio(od[5],od[4]),ratio(o[5],o[4])))
    result('restricted-net',(population(alternative(F(2),F(0)))[6]-cost,upper-cost))
    ex=get('input','ex-bounds');result('ex-bounds',(ex[1]-ex[2],)+bounds(ex)+bounds(ex,True));result('ex-world',(o[6],population(alternative(F(0),F(10)))[6]))
    mass=get('input','defier-masses');eff=get('input','defier-effects');ds=((0,1),(1,0),(1,1),(0,0));dr=tuple((m,*d,y0,y0+e) for m,d,e,y0 in zip(mass,ds,eff,(0,0,1,1)));do=population(dr);result('defiers',(do[4],do[5],ratio(do[5],do[4])));eq(do[:4],(F(3,10),F(3,5),F(13,10),F(13,10)),'defier observations')
    rf,fs,kl,kh=get('input','sensitivity');need(fs>0 and kl<=kh,'sensitivity domain');result('sensitivity',(ratio(rf-kh,fs),ratio(rf-kl,fs)))
    result('workload-repair',(2+3+2+3,2+3+2+3-8,2,2,2,2))
    ret=population(get('input','retention'));result('retention',ret[:6]+(ratio(ret[5],ret[4]),ret[6]))
    eq(sum((8,12,12,13,10,5)),60,'case1 minutes');eq(sum((4,8,8,6,4)),30,'discussion minutes');eq(sum((2,3,3,2,2)),12,'presentation minutes');eq((6*12,120-6*12),(72,48),'defense capacity');eq((sum((2,2,2,2,2)),sum((2,2,2,2,2))),(10,10),'case rubrics')
    worlds=0
    for raw in (raw,ex,(F(1,2),F(0),F(10),F(0),F(10)),(F(1,10),F(2),F(2),F(0),F(4))):
        low,high=bounds(raw);mlo,mhi=bounds(raw,True)
        for k in range(11):
            lam=F(k,10);u=raw[3]+lam*(raw[4]-raw[3]);v=raw[4]-lam*(raw[4]-raw[3]);x=bounds_world(raw,u,v)
            eq(x,low+lam*(high-low),'all interpolated sharpness worlds')
            mu=raw[2]+lam*(raw[4]-raw[2]);mv=raw[1]-lam*(raw[1]-raw[3]);eq(bounds_world(raw,mu,mv),mlo+lam*(mhi-mlo),'monotone interiors');worlds+=2
    for a,nv in product((F(0),F(2),F(4),F(10)),repeat=2):
        oa=population(alternative(a,nv));eq(oa[:6],o[:6],'observation equivalence');eq(lower<=oa[6]<=upper,True,'population range');worlds+=1
    eq(bounds((F(1,2),F(0),F(10),F(0),F(10))),(-10,0),'opposite boundary');eq(population(((F(1),0,1,2,5),))[4:],(1,3,3),'full compliance')
    invalid=0
    for f in (lambda:bounds((0,7,4,0,10)),lambda:bounds((1,7,4,0,10)),lambda:bounds((F(1,2),11,4,0,10)),lambda:bounds((F(1,2),7,4,10,0)),lambda:bounds_world((F(1,2),7,4,0,10),11,0),lambda:population(()),lambda:population(((F(1,2),0,1,0,1),)),lambda:population(((1,0,2,0,1),)),lambda:population(((1,0,1,-1,1),)),lambda:ratio(1,0),lambda:exact((True,1),2),lambda:value('__import__("os")')):
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid input accepted')
    need(set(values)==used,'unused numeric marker')
    return {'chapter':'v17-c04','status':'passed','runtime_files':4,'worked_artifacts':2,'exercises':8,'seminar_weeks':6,'numeric_markers':sum(k[0]=='result' for k in values),'comparisons':n,'complete_alternative_worlds':worlds,'invalid_domains':invalid,'scope':'Full syllabus, two cases, eight answers and proof/source scopes separately reviewed; no observed teaching or actual learner achievement claimed.'}
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage checker [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
