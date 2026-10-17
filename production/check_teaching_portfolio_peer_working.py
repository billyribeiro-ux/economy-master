"""Independent teaching portfolio peer; author checker intentionally opaque."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
import ast,json
def strict(s):
    def pairs(xs):
        out={}
        for k,v in xs:
            if k in out:raise ValueError("duplicate JSON key")
            out[k]=v
        return out
    return json.loads(s,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError("nonfinite")))
FILES=('production/teaching-portfolio-working.html','production/check_teaching_portfolio_working.py','production/teaching-portfolio-sources-working.json','production/teaching-portfolio-author-review-working.json','production/check_teaching_portfolio_peer_working.py','production/teaching-portfolio-peer-review-working.json')
def require(ok, message):
    if not ok:
        raise ValueError(message)

def number(text):
    def walk(n):
        if isinstance(n, ast.Constant) and type(n.value) is int: return F(n.value)
        if isinstance(n, (ast.Tuple, ast.List)): return tuple(walk(x) for x in n.elts)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -walk(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div): return walk(n.left)/walk(n.right)
        raise ValueError('numeric grammar')
    return walk(ast.parse(text, mode='eval').body)

class Reader(HTMLParser):
    def __init__(self):
        super().__init__(); self.markers={}; self.active=None; self.ids=[]; self.solutions=[]; self.sources={}; self.maps={k:[] for k in ('data-artifact','data-prerequisite','data-chapter')}
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if 'data-solution-for' in d:self.solutions.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d['href']
        for k in self.maps:
            if k in d:self.maps[k].append(d[k])
        for kind in ('data-input','data-result'):
            if kind in d:
                require(d[kind] not in self.markers,'duplicate numeric marker');self.active=d[kind];self.markers[self.active]=''
    def handle_data(self, data):
        if self.active:self.markers[self.active]+=data
    def handle_endtag(self, tag):
        if tag=='span':self.active=None



def frontier(cap,C):
    aw,ac,bw,bc=map(F,cap);C=F(C);require(min(aw,ac,bw,bc)>0 and 0<=C<=ac+bc,'production domain')
    lo=max(F(0),C-bc);hi=min(ac,C)
    candidates=[(a,C-a,aw*(1-a/ac)+bw*(1-(C-a)/bc)) for a in (lo,hi)]
    return max(candidates,key=lambda x:x[2])

def lottery(a,b,p,offer):
    a,b,p,offer=map(F,(a,b,p,offer));require(min(a,b,offer)>=0 and 0<=p<=1,'utility domain')
    ew=p*a*a+(1-p)*b*b;eu=p*a+(1-p)*b;ce=eu*eu
    return ew,eu,ce,(offer-ce if offer>=ce else None)

def moments(x,z,y,weights=None):
    require(len(x)==len(z)==len(y) and len(x)>0,'same nonempty arrays')
    x,z,y=[tuple(map(F,v)) for v in (x,z,y)];w=tuple(map(F,weights)) if weights is not None else (F(1,len(x)),)*len(x)
    require(len(w)==len(x) and min(w)>=0 and sum(w)==1,'weight domain')
    avg=lambda v:sum(a*b for a,b in zip(w,v));means=tuple(avg(v) for v in (x,z,y));xc,zc,yc=[tuple(a-m for a in v) for v,m in zip((x,z,y),means)]
    cov=lambda v,u:sum(a*b*c for a,b,c in zip(w,v,u))
    vx,vz,cxz,cxy,cyz=cov(xc,xc),cov(zc,zc),cov(xc,zc),cov(xc,yc),cov(zc,yc)
    require(vx>0,'short variance');short=cxy/vx;inter=means[2]-short*means[0];det=vx*vz-cxz*cxz
    require(vz>0 and det>0,'full rank')
    bx=(cxy*vz-cyz*cxz)/det;bz=(cyz*vx-cxy*cxz)/det;alpha=means[2]-bx*means[0]-bz*means[1]
    xr=tuple(a-cxz/vz*b for a,b in zip(xc,zc));rv,rc=cov(xr,xr),cov(xr,yc)
    return means,(vx,vz,cxz,cxy),(short,inter),xr,(rv,rc),(bx,bz,alpha)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    rec=strict((root/FILES[-1]).read_text());require(set(rec['payloads'])==set(FILES[:-1]),'five nonself bindings')
    for p,v in rec['payloads'].items():
        raw=(root/p).read_bytes();require(len(raw)==v['bytes'] and sha256(raw).hexdigest()==v['sha256'],'changed '+p)
    page=Reader();page.feed((root/FILES[0]).read_text());m={k:number(v) for k,v in page.markers.items()};n=0
    def eq(a,b,label):
        nonlocal n
        require(a==b,label);n+=1
    eq(len(page.ids),len(set(page.ids)),'uniqueids');eq(page.solutions,[f'teaching-case-task-{i}' for i in range(1,4)]+[f'teaching-defense-{i}' for i in range(1,7)],'nine full answer pairs')
    eq(set(page.maps['data-artifact']),{'syllabi','lessons_assessment','learner_work','observation','supervision','reflection_defense'},'six artifacts')
    eq(page.sources,{s['id']:s['url'] for s in strict((root/FILES[2]).read_text())['sources']},'source routes')
    eq(m['production'],(12,6,8,8),'production primitives');a,bb,w=frontier(m['production'],m['cloth']);eq((a,bb,w,a/6,w/12,bb/8,*[frontier(m['production'],C)[2] for C in (0,8,14)]),m['production-key'],'frontier and resource key')
    eq(m['production-scores'],((1,1,1,1,1),(1,1,0,0,0),5,2,F(4,3)),'actual anticipated-response grading')
    a,bb,w=frontier(m['production'],9);eq((a,bb,w,a/6,w/12),m['defense-production'],'production transfer')
    eq(m['utility'],(64,144,F(1,2),104),'lottery primitive');eq(lottery(8,12,F(1,2),104),m['utility-key'],'utility not wealth')
    ew,eu,ce,_=lottery(8,12,F(1,4),104);eq((ew,eu,ce,ew-ce),m['utility-alternative'],'changed probabilities');eq(lottery(8,12,F(1,4),104)[-1],None,'fixed offer rejected')
    eq(m['fresh-utility'],(36,100,F(1,2),68),'fresh primitive');eq(lottery(6,10,F(1,2),68),m['utility-fresh'],'fresh CE')
    eq(m['utility-scores'],((1,0,0,0,0),(1,1,1,1,1),(1,1,0,1,0),(1,5,3)),'each complete criterion judgment')
    x,z,y=m['regression'];eq(moments(x,z,y),m['regression-key'],'all raw-row fullregression quantities')
    znew=m['fresh-z'];ynew=tuple(2*a+b for a,b in zip(x,znew));mnew=moments(x,znew,ynew);eq((ynew,*mnew[0],*mnew[1],*mnew[-1]),m['regression-fresh'],'fresh full moments')
    yres=tuple(3*a+b for a,b in zip(x,znew));mr=moments(x,znew,yres);eq((yres,F(1),mr[2][0]),m['regression-residual'],'omitted residual term')
    ydef=tuple(4*a+b for a,b in zip(x,znew));md=moments(x,znew,ydef);eq((ydef,F(2),md[2][0]),m['defense-residual'],'fresh residual term')
    eq(m['regression-scores'],((1,1,1,0,0),(1,1,1,1,1),3,5),'actual R and S work')
    N,initial,response,success=map(int,m['defense-roster']);eq((F(initial,N),F(success,response),F(success,N),F(success+N-response,N),F(success-initial,N),F(success+N-response-initial,N)),m['defense-evidence'],'sharp binary missing endpoints')
    production_worlds=0
    for C in range(15):
        ca,cb,best=frontier(m['production'],C)
        for j in range(25):
            aa=F(j,4);bb=F(C)-aa
            if 0<=aa<=6 and 0<=bb<=8:eq(best>=20-2*aa-bb,True,'all quarter-unit allocations')
        eq(best,20-C if C<=8 else 28-2*C,'both frontier regimes');production_worlds+=1
    utility_worlds=0
    for a in (0,2,8):
      for bb in (0,4,12):
       for j in range(9):
        p=F(j,8);ew,eu,ce,_=lottery(a,bb,p,200);eq(ew-ce,p*(1-p)*(a-bb)**2,'global algebra witness');eq(ew>=ce,True,'risk premium nonnegative');utility_worlds+=1
    regression_worlds=0
    for a in (F(-2),F(0),F(2)):
      for bb in (F(-1),F(1)):
       for k in (F(-1),F(0),F(2)):
        for zz in (z,znew):
         yy=tuple((a+k)*xx+bb*zi for xx,zi in zip(x,zz));out=moments(x,zz,yy);vx,vz,cxz,cxy=out[1]
         eq(out[2][0],a+bb*cxz/vx+k,'full omitted identity');eq(out[-1],(a+k,bb,0),'normal equations');regression_worlds+=1
    for scale,total in ((1,3),(2,4)):
        for s in range(-5,6):eq(tuple((total-scale*s)*xx+s*scale*xx for xx in x),tuple(total*xx for xx in x),'entire family finite witnesses')
    bad=[lambda:frontier((12,0,8,8),10),lambda:frontier((12,6,8,8),-1),lambda:frontier((12,6,8,8),15),lambda:lottery(-1,2,F(1,2),3),lambda:lottery(1,2,-1,3),lambda:lottery(1,2,2,3),lambda:lottery(1,2,F(1,2),-1),lambda:moments((1,1),(-1,1),(2,3)),lambda:moments(x,x,y),lambda:moments(x,z,y,(1,1,1,1)),lambda:moments(x,z,y,(-1,0,1,1)),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":Infinity}')]
    for f in bad:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'assessment':'teaching-portfolio','status':'passed','comparisons':n,'production_worlds':production_worlds,'utility_worlds':utility_worlds,'regression_worlds':regression_worlds,'invalid_domains':len(bad),'runtime_files':6,'full_manuscript_and_nine_answers_read':True,'author_checker':'opaque; not imported','scope':'Internal peer validates complete protocol and fictional calibration judgments; no learner-specific human observation certified.'}
if __name__=='__main__':check()
