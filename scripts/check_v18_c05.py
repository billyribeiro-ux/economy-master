"""V18C05 negotiation author checks; full artifact and proof review is separate."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product, combinations
import hashlib,json,sys,ast,math
FILES=('content/chapters/v18-c05.html','scripts/check_v18_c05.py','content/reviews/v18-c05-sources.json','content/reviews/v18-c05-author.json')
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

def bargain(mode,outside,alpha=F(1,2)):
    value,cost=vector(mode,2);du,dl,budget=vector(outside,3)
    need(min(value,cost,du,dl,budget)>=0 and type(alpha) in (int,F) and 0<alpha<1,'bargain domain')
    lower=cost+dl;upper=min(value-du,budget);surplus=value-cost-du-dl
    if lower>upper:return {'interval':None,'surplus':surplus}
    target=cost+dl+(1-alpha)*surplus;t=max(lower,min(upper,target));u=value-t;l=t-cost
    return {'interval':(lower,upper),'surplus':surplus,'target':target,'transfer':t,'payoffs':(u,l),'gains':(u-du,l-dl),'product':(u-du)*(l-dl)}

def coalition_game(vals):
    need(type(vals) is tuple and len(vals)==7 and all(type(v) in (int,F) and v>=0 for v in vals),'coalition values domain')
    keys=('A','B','C','AB','AC','BC','ABC')
    return {frozenset(k):F(v) for k,v in zip(keys,vals)}

def core_member(game,point):
    point=vector(point,3);alloc=dict(zip('ABC',point))
    return sum(point)==game[frozenset('ABC')] and all(sum(alloc[k] for k in coalition)>=worth for coalition,worth in game.items())

def core_vertices(game):
    total=game[frozenset('ABC')]
    lower=tuple(game[frozenset(k)] for k in 'ABC');upper=tuple(total-game[frozenset(set('ABC')-{k})] for k in 'ABC')
    vertices=set()
    # All intersections of the budget plane with two coordinate-boundary planes.
    for i,j in combinations(range(3),2):
        missing=3-i-j
        for a,b in product((lower[i],upper[i]),(lower[j],upper[j])):
            x=[F(0)]*3;x[i]=a;x[j]=b;x[missing]=total-a-b;x=tuple(x)
            if core_member(game,x):vertices.add(x)
    return tuple(sorted(vertices)),lower,upper

def summary_bargain(result):
    lo,hi=result['interval'];return (lo,hi,result['transfer'])+result['payoffs']

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    start={p:digest(root/p) for p in FILES};review=json.loads((root/FILES[3]).read_text())
    need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for p,b in review['payloads'].items():need(start[p]==b,'payload '+p)
    page=Page();page.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text())
    need(not page.h1 and len(page.ids)==len(set(page.ids)),'unique IDs/no h1')
    tasks=['v18-c05-ex'+str(i) for i in range(1,9)];need(page.exercises==page.answers==tasks,'eight matched exercises')
    need(page.worked==['v18-c05-case1','v18-c05-case2'],'two worked cases')
    need(set(page.sources)=={(s['id'],s['url']) for s in sources['sources']},'source URLs')
    inputs={k:parse(v) for k,v in page.inputs.items()};shown={k:parse(v) for k,v in page.results.items()}
    need(set(inputs)=={'academic-outside'},'resource primitives')
    outside=inputs['academic-outside'];rows=page.tables['v18-c05-modes'][1:];need(len(rows)==2,'two modes')
    modes={row[0].split(' — ')[0]:tuple(F(x) for x in row[1:3]) for row in rows};need(tuple(modes)==('S','H'),'delivery modes');count=0
    base={k:bargain(m,outside) for k,m in modes.items()}
    for row in rows:
        k=row[0].split(' — ')[0];value,cost=modes[k];need(tuple(F(x) for x in row[3:])==(value-cost,base[k]['surplus']),'visible value accounting');count+=2
    original_table=page.tables['v18-c05-coalition-values'][1:];need([r[0] for r in original_table]==['empty','A','B','C','AB','AC','BC','ABC'],'all eight coalitions')
    need(F(original_table[0][1])==0,'empty coalition zero')
    vals=tuple(F(row[1]) for row in original_table[1:]);game=coalition_game(vals);vertices,lower,upper=core_vertices(game)
    proposal=(F(8),F(7),F(5));single=tuple(p-d for p,d in zip(proposal,vals[:3]));pairs=tuple(sum(proposal['ABC'.index(k)] for k in names)-game[frozenset(names)] for names in ('AB','AC','BC'))
    expected={'academic-bargains':tuple(summary_bargain(base[k]) for k in ('S','H')),'academic-products':tuple(base[k]['product'] for k in ('S','H')),'core-vertices':vertices,'core-proposal':(proposal,single,pairs,sum(proposal))}
    need(base['H']['product']>base['S']['product'] and all(h-s==F(5,2) for h,s in zip(base['H']['payoffs'],base['S']['payoffs'])),'mode dominance under convention');count+=3
    weighted=[bargain(modes['S'],outside,a) for a in (F(2,3),F(1,4))]
    expected['weighted-standard']=tuple((z['transfer'],)+z['payoffs']+z['gains'] for z in weighted)
    need(weighted[1]['target']==F(145,2) and weighted[1]['transfer']==outside[2],'weight cash truncation');count+=2
    changedoutside=(outside[0],F(25),outside[2]);new=[bargain(modes[k],changedoutside) for k in ('S','H')]
    expected['outside-change']=tuple(summary_bargain(z)+(z['product'],) for z in new)
    for k in modes:need(bargain(modes[k],(outside[0],F(46),outside[2]))['interval'] is None,'strong outside no agreement');count+=1
    lowcash=outside[:2]+(F(40),);z=bargain(modes['H'],lowcash)
    need(bargain(modes['S'],lowcash)['interval'] is None,'standard funding failure');count+=1
    expected['cash-constrained']=z['interval']+(z['transfer'],)+z['payoffs']+z['gains']+(z['product'],)
    lowstate=bargain((F(70),modes['H'][1]),outside);expected['low-state']=(lowstate['interval'][1],lowstate['transfer'],lowstate['payoffs'],lowstate['gains'])
    need(F(70)-base['H']['transfer']<outside[0],'unconditional fee fails low state');count+=1
    repairvals=vals[:3]+(F(15),)*3+(F(45,2),);repair=coalition_game(repairvals);rv,_,_=core_vertices(repair)
    need(rv==((F(15,2),)*3,),'unique threshold core');count+=1
    expected['core-repair']=(repairvals[-1],repairvals[-1]-vals[-1],rv[0])
    stronger=coalition_game(vals[:3]+(F(17),)+vals[4:]);sv,_,_=core_vertices(stronger);expected['changed-core-vertices']=sv
    expensive=bargain((modes['H'][0],F(45)),outside);expected['hybrid-cost-change']=expensive['interval']+(expensive['transfer'],expensive['payoffs'],expensive['product'])
    tie=bargain((modes['H'][0],F(30)),outside);retentiongame=coalition_game(vals[:3]+(F(15),)*3+(F(23),));tv,_,_=core_vertices(retentiongame)
    expected['retention']=(tie['transfer'],tie['payoffs'],tie['product'],tv)
    need(tie['product']==base['S']['product'] and tie['payoffs']==base['S']['payoffs'],'delivery mode tie');count+=2
    need(set(expected)==set(shown),'all displayed results')
    def leaves(x):return sum(leaves(t) for t in x) if isinstance(x,tuple) else 1
    for k,v in expected.items():need(shown[k]==v,'displayed '+k);count+=leaves(v)
    # Independent square-completion checks symmetric optimum across dated cash and outside-option changes.
    bargaining_worlds=0
    for k,dl,budget in product(modes,(F(0),F(10),F(25),F(46)),(F(30),F(40),F(70))):
        result=bargain(modes[k],(outside[0],dl,budget));bargaining_worlds+=1
        if result['interval'] is None:continue
        lo,hi=result['interval'];center=(modes[k][0]-outside[0]+modes[k][1]+dl)/2
        for j in range(9):
            t=lo+(hi-lo)*j/8;gu=modes[k][0]-t-outside[0];gl=t-modes[k][1]-dl
            need(gu>=0 and gl>=0 and t<=budget,'candidate funded participation');count+=3
            productvalue=gu*gl;need(productvalue==result['surplus']**2/4-(t-center)**2 and productvalue<=result['product'],'independent squared-distance product');count+=2
    # Direct coalition inequalities versus convex-hull construction, including boundaries.
    core_worlds=0
    for candidate_game in (game,stronger,retentiongame):
        vv,_,_=core_vertices(candidate_game);need(len(vv)==3,'triangular cases')
        for i in range(5):
            for j in range(5-i):
                weights=(F(i,4),F(j,4),F(4-i-j,4));point=tuple(sum(w*v[t] for w,v in zip(weights,vv)) for t in range(3))
                need(core_member(candidate_game,point),'all convex-hull witnesses satisfy every coalition');count+=7;core_worlds+=1
    need(core_member(game,proposal),'proposed core member');count+=1
    equal=(vals[-1]/3,)*3;need(not core_member(game,equal) and 7>equal[0] and 7>equal[1] and 14==game[frozenset('AB')],'equal-split strict block');count+=4
    need(not core_member(stronger,proposal) and 9>proposal[0] and 8>proposal[1] and 9+8==stronger[frozenset('AB')],'changed-AB strict block');count+=4
    for total in (F(20),F(22),F(45,2),F(23)):
        g=coalition_game(vals[:3]+(F(15),)*3+(total,));vv,_,_=core_vertices(g)
        need(bool(vv)==(2*total>=45),'pair-sum necessary and sufficient on these cases');count+=1
    need(max(15+vals[2],15+vals[1],15+vals[0],sum(vals[:3]))==19<20,'grand payoff exceeds all partitions despite empty core');count+=1
    # Degenerate funded interval and no-surplus boundary are legitimate outcomes.
    zero=bargain((F(30),F(0)),outside);need(zero['surplus']==0 and zero['interval']==(10,10) and zero['gains']==(0,0),'zero surplus singleton');count+=3
    justfunded=bargain(modes['H'],outside[:2]+(F(35),));need(justfunded['interval']==(35,35) and justfunded['product']==0,'cash singleton');count+=2
    invalid=0
    bad=[lambda:bargain((-1,25),outside),lambda:bargain((90,-1),outside),lambda:bargain(modes['H'],(20,10,-1)),lambda:bargain(modes['H'],(True,10,70)),lambda:bargain(modes['H'],outside,F(0)),lambda:bargain(modes['H'],outside,F(1)),lambda:bargain(modes['H'],outside,0.5),lambda:coalition_game((4,3,2,14,12,10,-1)),lambda:coalition_game((4,3,2)),lambda:core_member(game,(8,7,True)),lambda:parse('(1,0.5)')]
    for f in bad:
        try:f()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(start=={p:digest(root/p) for p in FILES},'runtime mutation')
    result={'chapter':'v18-c05','status':'passed','runtime_files':4,'worked_cases':2,'exercises':8,'result_groups':len(shown),'comparisons':count,'bargaining_worlds':bargaining_worlds,'core_worlds':core_worlds,'invalid_domains':invalid,'scope':'Original fictional bargaining/coalition instruction; full proof and artifact review separate from arithmetic. No executed agreement or legal validation.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_c05_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
