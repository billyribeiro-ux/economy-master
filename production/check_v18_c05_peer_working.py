"""Independent C05 peer oracle: gain-space optimization and rational half-plane core clipping."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('production/v18-c05-working.html','production/check_v18_c05_working.py','production/v18-c05-sources-working.json','production/v18-c05-author-review-working.json','production/check_v18_c05_peer_working.py','production/v18-c05-peer-review-working.json')
def require(ok,message):
    if not ok: raise ValueError(message)


def numeric(text):
    text=text.rsplit('=',1)[-1].strip().replace('−','-')
    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return F(str(node.value))
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('restricted rational syntax')
    return walk(ast.parse(text,mode='eval').body)


class BaseManuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.inputs={};self.results={};self.prompts={};self.solutions={};self.sources={};self.worked=[];self.rows=[];self.row=None;self.cell=None;self.links=set();self.guides=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':raise ValueError('chapter fragment cannot contain h1')
        for attr,dest in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:require(a[attr] not in dest,'duplicate marker');dest[a[attr]]=''
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in x.get('class','').split() for t,x in self.stack):self.prompts[a['id']]=''
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack),'solution disclosure')
            require(a['data-solution-for'] not in self.solutions,'unique solution');self.solutions[a['data-solution-for']]=''
        if 'data-source' in a:require(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if tag=='a':self.links.add(a['href'])
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.cell is not None:self.cell+=text
        for tag,a in self.stack:
            if 'data-input' in a:self.inputs[a['data-input']]+=text
            if 'data-result' in a:self.results[a['data-result']]+=text
            if tag=='li' and a.get('id') in self.prompts:self.prompts[a['id']]+=text
            if 'data-solution-for' in a:self.solutions[a['data-solution-for']]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting')
        if tag in ('td','th'):self.row.append(self.cell);self.cell=None
        if tag=='tr':self.rows.append(self.row);self.row=None
        self.stack.pop()


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(v):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)



def bargaining(V,c,du,dl,B,alpha=F(1,2)):
    V,c,du,dl,B,alpha=map(F,(V,c,du,dl,B,alpha))
    require(min(V,c,du,dl,B)>=0 and 0<alpha<1,'nonnegative primitives and interior weight')
    surplus=V-c-du-dl
    # Work in payer gain x. Provider gain is S-x; budget gives a LOWER bound on x.
    lo=max(F(0),V-du-B);hi=surplus
    if lo>hi:return None
    x=min(hi,max(lo,alpha*surplus));y=surplus-x;t=V-du-x
    return (c+dl,min(V-du,B),t,du+x,dl+y,x,y,x*y)


def core_polygon(values):
    require(set(values)==set(range(8)) and values[0]==0 and all(v>=0 for v in values.values()),'complete nonnegative three-agent game')
    G=values[7];poly=[(F(0),F(0)),(G,F(0)),(F(0),G)]
    # Intersect actual coalition half-planes after eliminating C=G-A-B.
    for mask in range(1,7):
        ac=F(bool(mask&1));bc=F(bool(mask&2));cc=F(bool(mask&4))
        a,b,k=ac-cc,bc-cc,values[mask]-cc*G
        out=[]
        for i,current in enumerate(poly):
            previous=poly[i-1];vp=a*previous[0]+b*previous[1]-k;vc=a*current[0]+b*current[1]-k
            if (vp>=0)!=(vc>=0):
                t=vp/(vp-vc);out.append(tuple(previous[j]+t*(current[j]-previous[j]) for j in (0,1)))
            if vc>=0:out.append(current)
        poly=[]
        for q in out:
            if q not in poly:poly.append(q)
        if not poly:break
    return tuple(sorted((x,y,G-x-y) for x,y in poly))


def margins(point,values):
    require(len(point)==3 and sum(point)==values[7],'feasible allocation exhausts total')
    return {mask:sum((point[i] for i in range(3) if mask>>i&1),F(0))-values[mask] for mask in range(8)}


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    def yes(ok,label):
        nonlocal count
        require(ok,label);count+=1
    eq({k:numeric(v) for k,v in d.inputs.items()},{'academic-outside':(20,10,70)},'visible outside primitive')
    modes={}
    for r in d.rows:
        if r[0] in ('S — standard schedule','H — hybrid schedule'):
            numbers=tuple(numeric(x) for x in r[1:]);modes[r[0][0]]=numbers
    eq(modes,{'S':(100,40,60,30),'H':(90,25,65,35)},'actual complete delivery rows')
    mask={'empty':0,'A':1,'B':2,'C':4,'AB':3,'AC':5,'BC':6,'ABC':7}
    game={mask[r[0]]:numeric(r[1]) for r in d.rows if len(r)==2 and r[0] in mask}
    eq(game,{0:0,1:4,2:3,4:2,3:14,5:12,6:10,7:20},'actual complete coalition table')
    du,dl,B=map(F,(20,10,70));s=bargaining(100,40,du,dl,B);h=bargaining(90,25,du,dl,B)
    ws=[bargaining(100,40,du,dl,B,w) for w in (F(2,3),F(1,4))]
    alt=[bargaining(V,c,20,25,70) for V,c in ((100,40),(90,25))]
    cash=bargaining(90,25,20,10,40);low=bargaining(70,25,20,10,70);hc=bargaining(90,45,20,10,70)
    original=core_polygon(game);point=tuple(map(F,(8,7,5)));m=margins(point,game)
    equalpairs=game|{3:F(15),5:F(15),6:F(15)};threshold=sum(equalpairs[i] for i in (3,5,6))/2
    repair=core_polygon(equalpairs|{7:threshold});changed=core_polygon(game|{3:F(17)});ret=bargaining(90,30,20,10,70);retcore=core_polygon(equalpairs|{7:F(23)})
    want={'academic-bargains':(s[:5],h[:5]),'academic-products':(s[7],h[7]),'core-vertices':original,'core-proposal':(point,tuple(m[i] for i in (1,2,4)),tuple(m[i] for i in (3,5,6)),sum(point)),'core-repair':(threshold,threshold-game[7],repair[0]),'weighted-standard':tuple((r[2],*r[3:7]) for r in ws),'outside-change':tuple((*r[:5],r[7]) for r in alt),'cash-constrained':cash,'low-state':(low[1],low[2],low[3:5],low[5:7]),'changed-core-vertices':changed,'hybrid-cost-change':(hc[0],hc[1],hc[2],hc[3:5],hc[7]),'retention':(ret[2],ret[3:5],ret[7],retcore)}
    eq(set(want),set(d.results),'every result group')
    for k,v in want.items():eq(numeric(d.results[k]),v,'displayed '+k)
    eq((s[3]+s[4],h[3]+h[4]),(60,65),'transfer cancellation')
    eq(tuple(h[j]-s[j] for j in (3,4)),(F(5,2),F(5,2)),'symmetric package gains')
    eq((100-50-20,50-40-10,100-70-20,70-40-10),(30,0,10,20),'opening demand endpoint net gains')
    eq((bargaining(100,40,20,46,70),bargaining(90,25,20,46,70)),(None,None),'outside46 both infeasible')
    eq((100-40-20-46,90-25-20-46),(-6,-1),'negative joint gains even without cash cap')
    eq(bargaining(100,40,20,10,40),None,'positive surplus but no funded standard')
    eq((70-F(105,2),F(105,2)-25),(F(35,2),F(55,2)),'old fee violates low-state payer participation')
    eq(F(105,2)-45,F(15,2),'old hybrid fee violates changed cost participation')
    eq(tuple(s[j]-hc[j] for j in (3,4)),(F(15,2),F(15,2)),'standard beats repriced hybrid both payoffs')
    # Exact integer powers evaluate weighted objectives without logarithms or floating powers.
    transfer_witnesses=0
    for V,c,odl,cap,alpha,powerx,powery in ((100,40,10,70,F(2,3),2,1),(100,40,10,70,F(1,4),1,3),(100,40,10,70,F(1,2),1,1),(90,25,10,40,F(1,2),1,1),(100,40,25,70,F(1,2),1,1),(90,25,25,70,F(1,2),1,1),(70,25,10,70,F(1,2),1,1)):
        r=bargaining(V,c,20,odl,cap,alpha);obj=r[5]**powerx*r[6]**powery
        for j in range(21):
            t=r[0]+(r[1]-r[0])*F(j,20);x=V-t-20;y=t-c-odl;transfer_witnesses+=1
            yes(x>=0 and y>=0 and t<=cap,'funded participation throughout interval')
            yes(x**powerx*y**powery<=obj,'actual weighted objective no higher at feasible witness')
            if alpha==F(1,2):eq(x*y,((x+y)/2)**2-(x-(x+y)/2)**2,'global completed square identity')
    eq(bargaining(50,20,20,10,30),(30,30,30,20,10,0,0,0),'zero surplus singleton')
    eq(bargaining(50,20,20,10,29),None,'zero surplus unfunded')
    eq(bargaining(60,20,20,10,30),(30,30,30,30,10,10,0,0),'positive surplus cash singleton no strict gain')
    eq((ret[3:5],ret[7]),(s[3:5],s[7]),'retention true mode tie')
    # Polygon vertices come from clipping raw coalition inequalities, not the author's simplex formula.
    for g,vertices in ((game,original),(game|{3:F(17)},changed),(equalpairs|{7:F(23)},retcore)):
        eq(len(vertices),3,'three nondegenerate vertices')
        for vertex in vertices:yes(all(v>=0 for v in margins(vertex,g).values()),'each vertex satisfies every coalition')
        for i in range(5):
            for j in range(5-i):
                weights=(F(i,4),F(j,4),1-F(i+j,4));z=tuple(sum(weights[k]*vertices[k][axis] for k in range(3)) for axis in range(3))
                yes(all(v>=0 for v in margins(z,g).values()),'convex combination satisfies all inequalities')
                upper=tuple(g[7]-g[7^(1<<k)] for k in range(3));slack=tuple(upper[k]-z[k] for k in range(3))
                yes(all(v>=0 for v in slack),'complement upper bounds')
                eq(sum(slack),sum(upper)-g[7],'slack sum characterization')
    equal=(F(20,3),)*3;eq(margins(equal,game)[3],F(-2,3),'equal split AB deficit')
    eq((7-equal[0],7-equal[1]),(F(1,3),F(1,3)),'strict equal split blocking witness')
    eq((9-point[0],8-point[1]),(1,1),'changed AB strict block')
    eq((9-point[0],6-point[2]),(1,1),'equalpairs AC strict block')
    eq(tuple(sum(point[k] for k in range(3) if mask>>k&1) for mask in (3,5,6)),(15,13,12),'allpair15 old proposal sums')
    eq(tuple(equalpairs[i]+equalpairs[7^i] for i in (3,5,6)),(17,18,19),'all disjoint pair partitions')
    eq(sum(equalpairs[i] for i in (1,2,4)),9,'singleton partition')
    for total in (F(20),F(22),F(45,2)):
        polygon=core_polygon(equalpairs|{7:total})
        eq(bool(polygon),2*total>=45,'global necessary threshold and equality witness')
    eq(repair,((F(15,2),)*3,),'unique threshold intersection')
    eq(tuple(sum(repair[0][k] for k in range(3) if mask>>k&1) for mask in (3,5,6)),(15,15,15),'every threshold pair binds')
    invalid=[lambda:bargaining(-1,2,1,1,4),lambda:bargaining(10,-1,1,1,4),lambda:bargaining(10,2,-1,1,4),lambda:bargaining(10,2,1,-1,4),lambda:bargaining(10,2,1,1,-1),lambda:bargaining(10,2,1,1,4,0),lambda:bargaining(10,2,1,1,4,1),lambda:core_polygon({0:0,7:20}),lambda:core_polygon(game|{0:1}),lambda:core_polygon(game|{1:-1}),lambda:margins((8,7,4),game)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want),transfer_witnesses


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'nonself bindings')
    for rec in (author,peer):
        for f,v in rec['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v18-c05-ex{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids and d.worked==['v18-c05-case1','v18-c05-case2'],'eight pairs/two complete cases')
    for k,v in peer['exact_prompt_review'].items():require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed exact pair changed')
    routes={'v18-c05-pon-batna':'https://www.pon.harvard.edu/tag/best-alternative-to-a-negotiated-agreement/','v18-c05-manea-cooperative':'https://ocw.mit.edu/courses/14-126-game-theory-spring-2016/25c82e8213fd23daa72c9382e921a2b0_MIT14_126S16_cooperative.pdf'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'exact scoped source routes')
    require(all(s['actual_inspector']=='v16_c01_author' for s in sources['sources']),'preserved actual source inspector')
    require({a for a in d.links if not a.startswith('https://')}=={'v18-c04.html','v05-c10.html','curriculum.html#v18-c06'},'chapter routes')
    comparisons,invalid,groups,witnesses=audit(d)
    return {'chapter':'v18-c05','status':'passed','review':'independent internal peer','runtime_files':6,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'weighted_transfer_witnesses':witnesses,'source_routes':2,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Full bargaining/core proofs, negotiation and conditional terms, authority/stakeholder records, exact solutions and bounded sources read; no executed negotiation or human leadership certified.'}


if __name__=='__main__':
    check()
