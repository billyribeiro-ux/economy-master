"""Independent C10 peer oracle; author checker is opaque payload only."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
import ast,json
FILES=('production/v17-c10-working.html','production/check_v17_c10_working.py','production/v17-c10-sources-working.json','production/v17-c10-author-review-working.json','production/check_v17_c10_peer_working.py','production/v17-c10-peer-review-working.json')
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


def policy(rows,t):
    require(0<=t<=1 and len(rows)>0,'policy domain')
    return tuple(intercept+slope*t-cost for cost,intercept,slope in rows)
def envelope(rows,low,high):
    require(0<=low<=high<=1,'range domain')
    ends=[policy(rows,t) for t in (low,high)]
    return tuple(max(max(v)-v[j] for v in ends) for j in range(len(rows))),tuple(min(v[j] for v in ends) for j in range(len(rows)))
def pv(row,r):
    require(r>-1 and len(row)==4 and row[0]>=0,'PV domain')
    cost,g,b,end=row;return tuple(-cost+x/(1+r)+end/(1+r)**2 for x in (g,b))
def expected(pair,p):
    require(0<=p<=1 and len(pair)==2,'probability domain');return p*pair[0]+(1-p)*pair[1]
def cash(row,opening,payment,floor,loan=F(0),repay=F(0)):
    require(opening>=0 and payment>=0 and floor>=0 and loan>=0 and repay>=0,'cash domain')
    c,g,b,end=row;zero=opening+loan-c;one=(zero+g-payment,zero+b-payment);two=tuple(v+end-repay for v in one)
    return (zero,*one,*two),all(v>=floor for v in (zero,*one,*two))
def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    rec=json.loads((root/FILES[5]).read_text());require(set(rec['payloads'])==set(FILES[:5]),'exact five nonself bindings')
    for path,v in rec['payloads'].items():
        data=(root/path).read_bytes();require(len(data)==v['bytes'] and sha256(data).hexdigest()==v['sha256'],'changed '+path)
    reader=Reader();reader.feed((root/FILES[0]).read_text());m={k:number(v) for k,v in reader.markers.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    eq(len(reader.ids),len(set(reader.ids)),'IDs unique');eq(reader.solutions,[f'v17-c10-e{i}' for i in range(1,9)],'eight complete paired solutions');eq(reader.sources,{s['id']:s['url'] for s in json.loads((root/FILES[2]).read_text())['sources']},'source links')
    rows=m['policy-options'];low,high=m['policy-range'];regrets,worst=envelope(rows,low,high);eq(regrets,m['regrets'],'full worst regrets');eq(worst,m['worst-nets'],'full worst nets')
    eq(policy(rows,F(1,2)),m['mean-nets'],'assumed mean');eq(tuple(policy(rows,t) for t in (F(1,2),F(3,5))),m['policy-ties'],'exact ties');eq(m['thresholds'],(F(1,3),F(1,2),F(3,5)),'thresholds')
    rr,ww=envelope(rows,*m['narrow-range']);eq(rr,m['narrow-regrets'],'narrow regrets');eq(ww,m['narrow-nets'],'narrow nets');eq(tuple((c,a+s,a+s-c) for c,a,s in rows),m['favorable-display'],'display');eq(tuple(policy(rows,t)[1:] for t in (F(7,10),F(9,10))),m['retention'],'delayed')
    for t in [F(i,20) for i in range(21)]:
        values=policy(rows,t);br=max(values);eq(all(br-v<=r for v,r in zip(values,regrets)),True,'continuum endpoint witness')
        a,b=m['districts'];eq(a[0]+a[1]*t+a[2]+a[3]*t,rows[1][1]+rows[1][2]*t,'A district reconciliation');eq(b[2]+b[3]*t-a[2]-a[3]*t,F(20),'peripheral difference')
    L,S=m['projects'];r=m['board-rate'];p=m['probability'];lv=pv(L,r);sv=pv(S,r);eq((*lv,*sv,expected(lv,p),expected(sv,p)),m['project-values'],'state values')
    # Solve each affine crossing from independently discounted endpoint states.
    crossing=lambda pair:-pair[1]/(pair[0]-pair[1])
    eq((crossing(lv),crossing(sv),crossing(tuple(x-y for x,y in zip(lv,sv)))),m['board-thresholds'],'value thresholds')
    loan,repay=m['facility'];fp=(L[0]-loan,L[1],L[2],L[3]-repay);loanpv=loan-repay/(1+r)**2
    eq((loanpv,*pv(fp,r)),m['financed-values'],'dated financing');ledger,ok=cash(L,*m['liquidity'],loan,repay);eq(ledger,m['large-cash'],'actual cash path');eq(ok,True,'financed feasible');eq(cash(L,*m['liquidity'])[1],False,'unfinanced infeasible');eq(cash(S,*m['liquidity'])[1],True,'small feasible')
    nr=m['changed-rate'];base=expected(pv(L,nr),p);lf=loan-repay/(1+nr)**2;eq((base,lf,expected(pv(fp,nr),p)),m['rate-change'],'fixed contract new discount rate');eq(base+lf,expected(pv(fp,nr),p),'financing additive')
    eq(tuple(expected(pv(row,r),m['changed-probability']) for row in (L,S)),m['probability-change'],'changed probability');eq(tuple(expected(pv(row,r),F(4,5)) for row in (L,S)),m['fresh-check'],'fresh transfer')
    for pp in (F(0),F(1,3),F(17,24),F(3,4),F(4,5),F(1)):
        for rr in (F(0),F(1,5),F(1,4),F(1,2)):
            eq(expected(pv(fp,rr),pp)-expected(pv(L,rr),pp),loan-repay/(1+rr)**2,'rate/probability financing identity')
    # Endpoints and shared theta matter: incompatible independent range extrema cannot replace common-state differences.
    eq(max(policy(rows,t)[1]-policy(rows,t)[2] for t in (F(0),F(1))),F(10),'same theta difference');eq(F(20)-F(-5),F(25),'unattainable independent extreme difference')
    eq(cash(L,*m['liquidity'],loan,repay)[1],True,'equality feasible');eq(cash((90,90,29,50),*m['liquidity'],loan,repay)[1],False,'one less adverse receipt');eq(cash(L,110,50,21,loan,repay)[1],False,'larger floor')
    invalid=[lambda:policy(rows,F(-1)),lambda:policy(rows,F(2)),lambda:policy((),F(0)),lambda:envelope(rows,F(1),F(0)),lambda:envelope(rows,F(-1),F(1)),lambda:pv(L,F(-1)),lambda:pv((-1,1,1,1),F(0)),lambda:expected(lv,F(-1)),lambda:expected(lv,F(2)),lambda:cash(L,-1,50,20),lambda:cash(L,110,50,-1),lambda:cash(L,110,50,20,-1)]
    for f in invalid:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v17-c10','status':'passed','runtime_files':6,'comparisons':count,'invalid_domains':len(invalid),'numeric_markers':len(m),'independent_rate_probability_worlds':24,'scope':'Full prose/graph/table/memos/eight exact solutions/source scopes and global endpoint proof manually reviewed; author checker never used as oracle.'}
if __name__=='__main__':check()
