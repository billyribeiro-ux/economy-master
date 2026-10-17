"""V17C07 author verification; full qualitative review recorded separately."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
import ast
import json

FILES = ('content/chapters/v17-c07.html','scripts/check_v17_c07.py','content/reviews/v17-c07-sources.json','content/reviews/v17-c07-author.json')

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

def means(rows,p):
    require(0<=p<=1 and rows and all(len(r)==2 for r in rows),'payoff domain')
    return tuple((1-p)*r[0]+p*r[1] for r in rows)

def signal_value(rows,p,tpr,fpr,fee):
    require(0<p<1 and 0<=tpr<=1 and 0<=fpr<=1 and fee>=0,'signal domain')
    ph=p*tpr+(1-p)*fpr
    require(0<ph<1,'both reports need positive support')
    posth=p*tpr/ph;postl=p*(1-tpr)/(1-ph)
    gross=ph*max(means(rows,posth))+(1-ph)*max(means(rows,postl))
    net=gross-fee
    return ph,posth,postl,gross,net,net-max(means(rows,p))

def programs(x,w):
    np,nr,a,b,c,d,cost=x
    require(np>0 and nr>0 and cost>=0 and w>=0,'program domain')
    tax=cost/(np+nr);net=((a-tax,b-tax),(c-tax,d-tax))
    return net,tuple(np*p+nr*r for p,r in net),tuple(np*w*p+nr*r for p,r in net)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    record=json.loads((root/FILES[3]).read_text())
    require(set(record['payloads'])==set(FILES[:3]),'payload inventory')
    for f,v in record['payloads'].items():
        raw=(root/f).read_bytes();require(len(raw)==v['bytes'] and sha256(raw).hexdigest()==v['sha256'],'changed '+f)
    r=Reader();r.feed((root/FILES[0]).read_text());m={k:number(v) for k,v in r.markers.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    eq(len(r.ids),len(set(r.ids)),'unique IDs');eq(r.solutions,[f'v17-c07-e{i}' for i in range(1,9)],'eight paired solutions')
    eq(r.sources,{s['id']:s['url'] for s in json.loads((root/FILES[2]).read_text())['sources']},'source routes')
    rows=m['capacity'];p=m['p-first'];lower,upper=m['p-range'];expected=means(rows,p)
    eq(expected,m['expected-first'],'original expected means');eq(tuple(min(x,y) for x,y in zip(means(rows,lower),means(rows,upper))),m['worst-expected'],'worst expected');eq(tuple(min(row) for row in rows),m['worst-state'],'worst state')
    signal=signal_value(rows,p,*m['signal'],m['signal-fee']);eq(signal,m['signal-result'],'full signal calculation');eq(signal[3]-max(expected),m['signal-fee-limit'],'fee limit')
    perfect=(1-p)*max(row[0] for row in rows)+p*max(row[1] for row in rows);eq(perfect-max(expected),m['perfect-information'],'perfect information')
    eq(means(rows,F(3,4)),m['exit-capacity'],'exit means');eq(means(rows,m['e1-p']),m['e1-means'],'changed p')
    eq(signal_value(rows,p,*m['signal'],m['e2-fee'])[4],m['e2-net'],'expensive information')
    regrets=tuple(max(max(means(rows,q))-means(rows,q)[i] for q in (lower,p,upper)) for i in range(3));eq(regrets,m['e3-regrets'],'maximum regret')
    x=m['programs'];net,total,weighted=programs(x,m['w-first']);eq(net,m['program-net'],'net benefits');eq(total,m['program-total'],'total values');eq(weighted,m['weighted-first'],'weighted values')
    lowb,highb=m['benefit-range'];lowx=(*x[:2],lowb,*x[3:]);highx=(*x[:2],highb,*x[3:]);lo=programs(lowx,m['w-first']);hi=programs(highx,m['w-first'])
    eq((lo[2][0],hi[2][0]),m['weighted-range'],'evidence interval');tax=x[6]/sum(x[:2]);threshold=tax+(weighted[1]-x[1]*(x[3]-tax))/(x[0]*m['w-first']);eq(threshold,m['benefit-threshold'],'policy threshold')
    eq(sum(v>=2 for v in (lo[0][0][0],lo[0][1][0],F(0))),m['robust-feasible-count'],'floor infeasibility')
    exitx=(*x[:2],F(5),*x[3:]);en,et,ew=programs(exitx,m['w-first']);eq((ew[0],ew[1],en[0][0]),m['exit-program'],'new lower bound')
    eq(programs(x,m['e4-w'])[2],m['e4-values'],'new welfare weight');eq(x[0]*m['w-first']*(4-tax)+x[1]*(4-tax),m['e5-value'],'new program')
    minutes,reserved,learners,turn=m['e6-minutes'];eq(learners*turn-(minutes-reserved),m['e6-shortfall'],'time conflict');eq(sum(m['e6-plan']),minutes,'feasible plan');eq(m['e6-plan'][-1],reserved,'synthesis preserved')
    # Global rankings on rational domain witnesses, including threshold equalities.
    for i in range(21):
        q=F(i,20);mu=means(rows,q);best=tuple(j for j,v in enumerate(mu) if v==max(mu));eq(best,(1,) if q<F(1,2) else (2,) if q>F(1,2) else (1,2),'capacity ranking')
        w=F(i,5);wv=programs(x,w)[2];eq(wv[0]-wv[1],60*(w-1),'weight comparison')
    for prior in (F(1,4),F(1,2),F(3,4)):
        # A noninformative signal cannot create value; a perfect one attains the statewise envelope.
        un=signal_value(rows,prior,F(1,2),F(1,2),F(0));eq(un[3],max(means(rows,prior)),'uninformative signal')
        pe=signal_value(rows,prior,F(1),F(0),F(0));eq(pe[3],(1-prior)*max(r[0] for r in rows)+prior*max(r[1] for r in rows),'perfect signal')
    bad=[lambda:means(rows,F(-1)),lambda:means(rows,F(2)),lambda:means((),F(1,2)),lambda:signal_value(rows,F(0),F(1),F(0),F(0)),lambda:signal_value(rows,p,F(2),F(0),F(0)),lambda:signal_value(rows,p,F(0),F(0),F(0)),lambda:signal_value(rows,p,F(1),F(1),F(0)),lambda:signal_value(rows,p,F(1),F(0),F(-1)),lambda:programs((0,*x[1:]),F(1)),lambda:programs(x,F(-1)),lambda:programs((*x[:6],F(-1)),F(1))]
    for f in bad:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid input accepted')
    return {'chapter':'v17-c07','status':'passed','runtime_files':4,'worked_cases':2,'exact_solutions':8,'numeric_markers':len(m),'comparisons':count,'invalid_domains':len(bad),'scope':'All case packets/questions/dialogues/board syntheses/proofs and answers read separately; original synthetic instruction, no observed teaching or actual policy evidence.'}

if __name__=='__main__':check()
