"""Independent exact active-set/KKT audit; no author-checker dependency."""
from fractions import Fraction as F
from pathlib import Path
from hashlib import sha256
from html.parser import HTMLParser
import ast,json,sys
ROOT=Path(__file__).resolve().parents[1]
FILES=['content/chapters/v16-c06.html','scripts/check_v16_c06.py','content/reviews/v16-c06-sources.json','content/reviews/v16-c06-author.json','scripts/check_v16_c06_peer.py','content/reviews/v16-c06-peer.json']

def need(ok,msg):
    if not ok:raise ValueError('C06 peer: '+msg)

def numbers(s):
    def visit(n):
        if isinstance(n,ast.Expression):return visit(n.body)
        if isinstance(n,(ast.List,ast.Tuple)):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('unexpected numeric annotation')
    return visit(ast.parse(s,mode='eval'))

def params(v):
    need(len(v)==5 and all(type(x) in (int,F) for x in v),'five exact parameters')
    a,b,c,g,d=map(F,v);need(min(a,c,d)>=0 and b>0 and g>0,'economic domains')
    return a,b,c,g,d

def solve2(a,b,c,d,u,v):
    determinant=a*d-b*c;need(determinant!=0,'nonsingular choices')
    return (u*d-b*v)/determinant,(a*v-u*c)/determinant

def competitive(v):
    a,b,c,g,d=params(v)
    if a<=c:return F(0),(a+c)/2,F(0),(a,c)
    internal=(a-c)/b
    if internal<=d:return internal,c,F(0),(c,c)
    # Borrower marginal willingness = price; incumbent external marginal cost = price.
    q,r=solve2(b,1,-g,1,a,c-g*d)
    need(q>d and r>c,'active-set certification')
    return q,r,q-d,(r,r)

def monopoly(v):
    a,b,c,g,d=params(v)
    if a<=c:return F(0),a,F(0)
    # Locate zero of a continuous strictly decreasing marginal-profit map.
    slope0=-2*b;value0=a-c
    if value0+slope0*d<=0:q=-value0/slope0
    else:q=d+(value0+slope0*d)/(2*b+g)
    need(0<q<a/b,'monopoly feasible root')
    return q,a-b*q,max(F(0),q-d)

def two_lenders(v,h,k):
    a,b,c,g,d=params(v);need(type(h) in (int,F) and type(k) in (int,F),'exact extension primitives');h,k=F(h),F(k);need(h>=c and k>0,'extension domain')
    q,r,e,interval=competitive(v)
    if r<=h:return r,q,F(0),q
    # Solve separate marginal-benefit/marginal-cost equations in x,z, rather than author H formula.
    x,z=solve2(b+g,b,b,b+1/k,a-c+g*d,a-h)
    r=a-b*(x+z);need(x>d and z>0 and r>h,'both active supplier domains')
    return r,x,z,x+z

def account(v,q,r):
    a,b,c,g,d=params(v);benefit=a*q-b*q*q/2;cost=c*q+g*max(F(0),q-d)**2/2
    return benefit,cost,benefit-r*q,r*q-cost,benefit-cost

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources={};self.markers={};self.capture=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'duplicate attrs');need(tag!='h1','fragment')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a.get('id'))
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack):self.tasks.append(a.get('id'))
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'disclosed solution');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for kind in ('input','result'):
            if 'data-'+kind in a:
                self.capture=(kind,a['data-'+kind]);need(self.capture not in self.markers,'duplicate numeric group');self.markers[self.capture]=''
        if tag not in ('br','hr','img','link','meta','input'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.capture:self.markers[self.capture]+=text
    def handle_endtag(self,tag):
        need(bool(self.stack) and self.stack[-1][0]==tag,'HTML balance');_,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.capture=None

def check(root=None):
    root=Path(root) if root is not None else ROOT
    rec=json.loads((root/FILES[-1]).read_text());need(set(rec['payloads'])==set(FILES[:-1]),'five nonself payloads')
    for name,binding in rec['payloads'].items():
        b=(root/name).read_bytes();need(binding=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'frozen '+name)
    need(all(rec['review'].values()) and not rec['open_material_findings'],'full peer review')
    page=Page();page.feed((root/FILES[0]).read_text());page.close()
    need(not page.stack and len(set(page.ids))==len(page.ids),'unique complete fragment')
    ids=[f'v16-c06-ex{i}' for i in range(1,11)];need(page.tasks==ids and page.answers==ids,'ten matched full solutions')
    need(page.worked==[f'v16-c06-case{i}' for i in range(1,4)],'three complete cases')
    sources=json.loads((root/FILES[2]).read_text());need(page.sources=={s['id']:s['url'] for s in sources['sources']},'source routes')
    values={k:numbers(s) for k,s in page.markers.items()};comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        if isinstance(b,(list,tuple)):
            need(len(a)==len(b),label+' count')
            for x,y in zip(a,b):eq(x,y,label)
        else:need(a==b,label);comparisons+=1
    def shown(name,value):eq(values[('result',name)],value,name)
    base=values[('input','baseline')];eq(base,(10,1,2,1,2),'baseline primitives')
    a,b,c,g,d=base;q,r,e,_=competitive(base);shown('baseline',(q,r,e));shown('accounts',account(base,q,r))
    capacity=[base[:4]+(F(k),) for k in (0,8,10)];shown('capacity-rows',tuple(competitive(v)[:3] for v in capacity))
    h,k=values[('input','alternative')];eq((h,k),(2,1),'alternative primitives');before=two_lenders(base,h,k);after=two_lenders(base[:4]+(F(0),),h,k)
    shown('alternative-before',before);shown('alternative-after',after);shown('replacement-changes',tuple(after[i]-before[i] for i in (1,2,3)))
    step=F(1,10);shifted=two_lenders(base[:4]+(d+step,),h,k);slopes=tuple((shifted[i]-before[i])/step for i in range(4));shown('replacement-slopes',slopes)
    shown('alternative-inactive',two_lenders(base,6,1))
    qm,rm,em=monopoly(base);shown('monopoly',(qm,rm,em));ba,co,cs,profit,surplus=account(base,qm,rm);shown('monopoly-accounts',(profit,cs,surplus,account(base,q,r)[4]-surplus))
    rival=values[('input','rival')];eq(rival,(6,F(1,5),1,1,2),'rival primitives');shown('rival',monopoly(rival))
    rivalstep=rival[:4]+(rival[4]+step,);mslope=(monopoly(rivalstep)[0]-monopoly(rival)[0])/step;cslope=(competitive(base[:4]+(d+step,))[0]-q)/step;shown('rival-slopes',(mslope,cslope))
    need(len(values)==15,'complete marker inventory')
    # Explicit solution-only arithmetic and boundary witnesses, separate from annotations.
    eq(competitive(base[:4]+(F(1),))[:2],(F(9,2),F(11,2)),'ex3 funding change')
    eq(competitive((9,b,c,g,d))[:2],(F(9,2),F(9,2)),'ex3 demand change')
    eq(competitive((a,b,c,3,d))[:2],(F(7,2),F(13,2)),'ex4 higher friction')
    eq(two_lenders(base,6,1),(5,5,0,5),'ex6 feasible corner')
    # Unconstrained candidate at h6 has z<0 and is not an equilibrium.
    badx,badz=solve2(b+g,b,b,b+1,a-c+g*d,a-6);badr=a-b*(badx+badz)
    eq((badr,badx,badz,badx+badz),(F(16,3),F(16,3),F(-2,3),F(14,3)),'ex6 rejected candidate')
    eq((6-1)/(2*F(1,5)),F(25,2),'ex8 monopoly threshold')
    eq(competitive((1,1,2,1,2))[3],(1,2),'ex9 all prices');eq(competitive((2,1,2,1,2))[3],(2,2),'ex9 singleton')
    eq((b+g)*(q-qm)**2/2,account(base,q,r)[4]-surplus,'independent quadratic welfare loss')
    # A finite collection covers no-trade, kink, slack, active external finance and conduct-crossing regimes.
    worlds=[]
    for aa,cc in [(0,0),(1,2),(2,2),(3,0),(10,2)]:
        for bb,gg in [(F(1,2),F(3)),(F(2),F(1))]:
            for dd in (F(0),F(2),F(9)):worlds.append((F(aa),bb,F(cc),gg,dd))
    for v in worlds:
        aa,bb,cc,gg,dd=v;qq,rr,ee,interval=competitive(v);mm,mr,me=monopoly(v)
        # Global concavity certificate: KKT slopes suffice; these checks do not replace manuscript proof.
        sp=aa-cc-bb*qq-gg*max(qq-dd,0)
        need((qq==0 and sp<=0) or (qq>0 and sp==0),'competitive global KKT')
        mp=aa-cc-2*bb*mm-gg*max(mm-dd,0)
        need((mm==0 and mp<=0) or (mm>0 and mp==0),'monopoly global KKT')
        eq(max((aa-rr)/bb,0),qq,'borrower optimum')
        if rr>cc:eq(dd+(rr-cc)/gg,qq,'active supplier optimum')
        elif rr==cc:need(0<=qq<=dd,'supplier correspondence at c')
        else:eq(qq,0,'zero supplier')
        if aa>cc:need(mm<qq and mr>rr,'global conduct order across funding regimes')
        else:
            for price in (interval[0],sum(interval)/2,interval[1]):
                eq(max((aa-price)/bb,0),0,'zero-trade interval borrower');need(price<=cc,'zero-trade interval lender')
        eq(sum(account(v,qq,rr)[2:4]),account(v,qq,rr)[4],'payment cancellation')
        for hh,kk in [(cc,F(1,2)),(cc+2,F(2)),(cc+10,F(1))]:
            price,x,z,total=two_lenders(v,hh,kk);eq(x+z,total,'extension clearing');eq(max((aa-price)/bb,0),total,'extension demand');eq(kk*max(price-hh,0),z,'alternative optimum')
            if price>cc:eq(dd+(price-cc)/gg,x,'extension active incumbent')
            elif price==cc:need(0<=x<=dd,'extension flat incumbent')
            else:eq(x,0,'extension zero incumbent')
    # Exact secants inside each affine regime validate each displayed derivative direction.
    qbase,rbase=competitive(base)[:2]
    for coordinate,expected in [(4,(F(1,2),F(-1,2))),(0,(F(1,2),F(1,2)))]:
        v=list(base);v[coordinate]+=step;qq,rr=competitive(v)[:2];eq(((qq-qbase)/step,(rr-rbase)/step),expected,'binding derivatives')
    eq((competitive((a,b,c,g,8))[0]-competitive((a,b,c,g,8-step))[0])/step,F(1,2),'left kink slope')
    eq((competitive((a,b,c,g,8+step))[0]-competitive((a,b,c,g,8))[0])/step,0,'right kink slope')
    # Gamma secant has an explicit denominator correction; limit is the printed quotient derivative.
    newq=competitive((a,b,c,g+step,d))[0];eq((newq-qbase)/step,(b*d-(a-c))/((b+g)*(b+g+step)),'gamma finite quotient identity')
    rejected=0
    for bad in [(-1,1,2,1,2),(10,0,2,1,2),(10,1,-1,1,2),(10,1,2,0,2),(10,1,2,1,-1),(10,True,2,1,2),(10,1.,2,1,2),(10,1,2,1)]:
        try:competitive(bad)
        except ValueError:rejected+=1
        else:raise ValueError('invalid primitive accepted')
    for hh,kk in [(1,1),(2,0),(2,-1),(True,1),(2,1.)]:
        try:two_lenders(base,hh,kk)
        except ValueError:rejected+=1
        else:raise ValueError('invalid extension accepted')
    return {'status':'passed','runtime_files':6,'exact_comparisons':comparisons,'numeric_groups':len(values),'alternative_primitive_worlds':len(worlds),'alternative_lender_regimes_checked':3*len(worlds),'domain_rejections':rejected,'worked_cases':3,'full_solutions':10,'scope':'Global proofs reviewed independently in full; finite KKT witnesses supplement, not replace, those arguments.'}

if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
