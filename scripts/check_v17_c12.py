"""C12 author arithmetic and artifact gates; substantive reading separate."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
import ast,json
FILES=('content/chapters/v17-c12.html','scripts/check_v17_c12.py','content/reviews/v17-c12-sources.json','content/reviews/v17-c12-author.json')
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


def market(a,b,c,cap):
    require(a>0 and b>0 and c>0 and cap>=0,'market domain')
    p=a/(b+c);q=c*p;require(cap<=p,'binding or equal cap domain');s=c*cap;d=a-b*cap
    gross=a*s/b-s*s/(2*b);cost=s*s/(2*c);cs=gross-cap*s;ps=cap*s-cost
    baseline=a*q/b-q*q/(2*b)-q*q/(2*c)
    return p,q,d,s,d-s,cs,ps,cs+ps,baseline-cs-ps

def auction(v,m,bid,alpha=F(1,2),first=False):
    require(v>=0 and m>=0 and bid>=0 and 0<=alpha<=1,'auction domain')
    probability=F(1) if bid>m else F(0) if bid<m else alpha
    return probability*(v-(bid if first else m))

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    rec=json.loads((root/FILES[3]).read_text());require(set(rec['payloads'])==set(FILES[:3]),'three nonself bindings')
    for name,v in rec['payloads'].items():
        raw=(root/name).read_bytes();require(len(raw)==v['bytes'] and sha256(raw).hexdigest()==v['sha256'],'changed '+name)
    reader=Reader();reader.feed((root/FILES[0]).read_text());m={k:number(v) for k,v in reader.markers.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    eq(len(reader.ids),len(set(reader.ids)),'unique IDs');eq(reader.solutions,[f'v17-c12-e{i}' for i in range(1,9)],'eight answer pairs');eq(reader.sources,{s['id']:s['url'] for s in json.loads((root/FILES[2]).read_text())['sources']},'sources')
    a,b,c,cap=m['market'];eq(market(a,b,c,cap),m['ceiling'],'ceiling economics');eq(F(3*50+3*120,60),m['unit-hours'],'unit workload');eq(F(2*90+2*180,60),m['seminar-hours'],'seminar workload');eq(F(120+360,60),m['revised-hours'],'shorter unit')
    # Integrate actual alternative buyers' inverse demand; producer costs unchanged.
    integrate=lambda lo,hi:a*(hi-lo)/b-(hi*hi-lo*lo)/(2*b)
    gross=integrate(F(20),F(60));cs=gross-cap*40;ps=cap*40-F(40)**2/(2*c);base=market(a,b,c,F(25))[7]
    eq((gross,cs,ps,cs+ps,base-cs-ps),m['rationing'],'allocation counterexample')
    scores=(2,6,1,0);eq(scores,m['exit-scores'],'exact response scores');eq((F(sum(scores),3),F(sum(scores),4),F(sum(scores),24),F(1,3),F(1,4)),m['score-summary'],'denominators')
    alt=market(a,b,c,F(15));eq((alt[3],alt[4],*alt[5:]),m['cap15'],'changed cap');eq(market(a,b,c,F(25))[4:],(0,625,625,1250,0),'equal cap retention')
    v,other=m['auction'];eq(tuple(auction(*map(F,z)) for z in [(6,4,6),(6,4,5),(6,4,3),(6,8,6),(6,8,9),(6,6,6)]),m['auction-witnesses'],'second price witnesses');eq(tuple(auction(v,other,bid,first=True) for bid in (F(6),F(5))),m['first-price'],'changed payment rule');eq(tuple(auction(F(5),F(7),bid) for bid in (F(5),F(8),F(7))),m['auction-transfer'],'changed value opponent')
    worlds=0
    for v in map(F,[0,1,4,6]):
        for other in map(F,[0,2,4,7]):
            for alpha in (F(0),F(1,2),F(1)):
                truth=auction(v,other,v,alpha);eq(all(truth>=auction(v,other,F(bid),alpha) for bid in range(10)),True,'weak dominance grid');worlds+=1
    for bid in range(10):
        eq(auction(F(6),F(4),F(bid))<=2,True,'player one NE deviation');eq(auction(F(4),F(5),F(bid))<=0,True,'player two NE deviation')
    for ceiling in map(F,range(26)):
        out=market(a,b,c,ceiling);q=out[3];eq(out[8],(F(50)-q)**2/2,'lost trade area');eq(out[7]+out[8],F(1250),'surplus reconciliation')
    bad=[lambda:market(0,2,2,20),lambda:market(100,0,2,20),lambda:market(100,2,0,20),lambda:market(100,2,2,-1),lambda:market(100,2,2,26),lambda:auction(-1,4,6),lambda:auction(6,-1,6),lambda:auction(6,4,-1),lambda:auction(6,4,6,F(-1)),lambda:auction(6,4,6,F(2))]
    for f in bad:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v17-c12','status':'passed','runtime_files':4,'numeric_markers':len(m),'comparisons':count,'auction_worlds':worlds,'invalid_domains':len(bad),'scope':'Full two evidence dossiers, all eight complete answers, observation/supervision reports and proof limits manually reviewed; no actual teaching certified.'}
if __name__=='__main__':check()
