"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v18-c02.html','scripts/check_v18_c02.py','content/reviews/v18-c02-sources.json','content/reviews/v18-c02-author.json','scripts/check_v18_c02_peer.py','content/reviews/v18-c02-peer.json')
def require(x,msg):
    if not x:raise ValueError('C02 peer: '+msg)
def strict(text):
    def pairs(items):
        d={}
        for k,v in items:
            require(k not in d,'duplicate JSON key');d[k]=v
        return d
    def reject(x):raise ValueError('nonfinite JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=reject)
def rational(text):
    def visit(n):
        if isinstance(n,ast.Tuple):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) is int:return Q(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('unsupported exact literal')
    return visit(ast.parse(text.strip(),mode='eval').body)
class Reader(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources=[];self.numbers={};self.active=None;self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attrs');require(t!='h1','chapter h1')
        if 'id' in a:self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if t=='li' and any(z=='ol' and 'exercises' in d.get('class','').split() for z,d in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for' in a:
            require(any(z=='details' and 'solutions' in d.get('class','').split() for z,d in self.stack),'answer disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for kind in ('input','result'):
            if 'data-'+kind in a:
                key=(kind,a['data-'+kind]);require(key not in self.numbers and self.active is None,'numeric marker');self.active=(t,key);self.numbers[key]=''
        if t=='table':self.table=a.get('id','anonymous-'+str(len(self.tables)));self.tables[self.table]=[]
        if t=='tr':self.row=[]
        if t in ('th','td'):self.cell=[]
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.active:self.numbers[self.active[1]]+=s
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,t):
        require(bool(self.stack) and self.stack.pop()[0]==t,'balanced fragment')
        if self.active and self.active[0]==t:self.active=None
        if t in ('th','td'):self.row.append(''.join(self.cell).strip());self.cell=None
        if t=='tr':self.tables[self.table].append(self.row);self.row=None
        if t=='table':self.table=None

def exact(x,n):
    require(isinstance(x,(tuple,list)) and len(x)==n,'input dimension');require(all(type(v) in (int,Q) for v in x),'exact finite inputs');return tuple(Q(v) for v in x)
def npv(cost,annual,life,rate):
    cost,annual,rate=exact((cost,annual,rate),3)
    require(cost>=0 and type(life) is int and life>0 and rate>-1,'capital domain')
    return -cost+sum((annual/(1+rate)**t for t in range(1,life+1)),Q(0))
def academic(cost=24,gross=16,rent=2,early=40,investment_return=10,project=True):
    cost,gross,rent,early,investment_return=exact((cost,gross,rent,early,investment_return),5)
    require(min(cost,gross,rent,early)>=0 and early<=100 and investment_return>=-200,'academic domain')
    draw=min(Q(8),max(Q(0),200+investment_return-190))
    c0=60-cost;c1=c0+early-50;c2=c1+(100-early-rent+gross)+draw-50
    depreciation=8+(cost/2 if project else 0);equipment=40+cost-depreciation
    operating=100-rent+gross-124-depreciation;change=operating+investment_return
    pool=200+investment_return-draw;assets=c2+6+pool+equipment
    return (c0,c1,c2),draw,pool,equipment,operating,change,assets,c2+equipment

def lender(f=0,x=20,withdraw=25,provision=6,collected=16,system=True,early_principal=False):
    f,x,withdraw,provision,collected=exact((f,x,withdraw,provision,collected),5)
    require(f>=0 and 0<=x<=20 and 0<=withdraw<=180 and 0<=provision<=132 and 0<=collected<=20,'lender domain')
    # Reconstruct dated transaction effects on assets and funding, rather than accepting a closing formula.
    state={'cash':Q(50),'gross':Q(160),'allowance':Q(8),'equipment':Q(18),'receivable':Q(0),'deposits':Q(180),'equity':Q(40)}
    balances=[]
    def transact(changes):
        for k,v in changes.items():state[k]+=v
        assets=state['cash']+state['gross']-state['allowance']+state['equipment']+state['receivable']
        require(assets==state['deposits']+state['equity'],'transaction identity');balances.append(tuple(state.values()))
    transact({'cash':f,'equity':f})
    cost=12 if system else 0;opex=8 if system else 13;dep=6 if system else 2
    transact({'cash':-cost,'equipment':cost});cash=[state['cash']]
    if early_principal:
        transact({'cash':20,'gross':-20});cash.append(state['cash'])
    transact({'cash':-withdraw,'deposits':-withdraw});cash.append(state['cash'])
    if not early_principal:transact({'cash':20,'gross':-20})
    transact({'cash':-x,'gross':x});cash.append(state['cash'])
    transact({'cash':collected,'receivable':20-collected,'equity':20})
    transact({'cash':-5-opex,'equity':-5-opex});cash.append(state['cash'])
    transact({'allowance':provision,'equity':-provision});transact({'equipment':-dep,'equity':-dep})
    profit=20-5-opex-provision-dep
    assets=state['cash']+state['gross']-state['allowance']+state['equipment']+state['receivable']
    return tuple(cash),profit,state,assets,balances

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    review=strict((root/FILES[5]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'manual review')
    require(set(review['payloads'])==set(FILES[:5]),'bindings')
    for name,d in review['payloads'].items():
        data=(root/name).read_bytes();require(d=={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},'freeze '+name)
    sources=strict((root/FILES[2]).read_text())['sources'];strict((root/FILES[3]).read_text())
    p=Reader();p.feed((root/FILES[0]).read_text());p.close()
    require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment')
    require(p.tasks==p.answers==['v18-c02-e'+str(i) for i in range(1,9)],'paired answers')
    require(p.worked==['v18-c02-case1','v18-c02-case2'],'cases');require(set(p.sources)=={(x['id'],x['url']) for x in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,v):eq(read('result',key),v,key)
    eq(read('input','academic-opening'),(60,30,200,40,0),'opening')
    projects=read('input','academic-projects');eq(projects,((24,16,2,2),(36,22,2,2)),'projects')
    rate=Q(1,10);values=tuple(npv(c,g-r,int(l),rate) for c,g,r,l in projects)
    result('academic-npv',values);eq(values[0]>0>values[1],True,'global menu value')
    a=academic();cash,draw,pool,equipment,operating,change,assets,unrestricted=a
    result('academic-cash',cash+(6,));result('academic-position',(operating,change,equipment,pool,assets,unrestricted))
    eq(assets,330+change,'academic stock flow');eq((unrestricted-100)+(6-30)+(pool-200),change,'subfund reconciliation')
    eq(tuple(Q(row[2]) for row in p.tables['v18-c02-academic-cash'][1:]),(60,)+cash,'cash table')
    eq(tuple(Q(row[3]) for row in p.tables['v18-c02-academic-cash'][1:]),(30,30,18,6),'restricted table')
    for row,expected in zip(p.tables['v18-c02-academic-menu'][1:],((0,0,0,0,0),(24,16,2,14,12),(36,22,2,20,18))):eq(tuple(Q(v) for v in row[1:]),expected,'menu table')
    eq(min(academic(36,22)[0])<20,True,'Y timing fails')
    stress=academic(early=20,investment_return=-10);result('academic-stress',(stress[0][1],stress[0][2],stress[1],stress[2],20-stress[0][1]))
    fallback=academic(cost=0,gross=0,rent=0,early=20,investment_return=-10,project=False)
    result('academic-fallback',fallback[0]+(fallback[3],fallback[6],fallback[5]))
    real=200*(Q(5,100)-Q(2,100));target=200*(1+Q(2,100));result('endowment-real',(real,target,target-pool))
    eq(read('input','lender-opening'),(50,160,8,18,180,40),'lender opening')
    capital=read('input','lender-capital');eq(capital,(12,5,3,rate),'lender capital');result('lender-npv',npv(capital[0],capital[1],int(capital[2]),capital[3]))
    cash,profit,bank,total,_=lender();net=bank['gross']-bank['allowance']
    result('lender-base',(cash[0],cash[1],cash[-1],profit,bank['equity'],net,bank['equipment'],bank['receivable'],bank['deposits'],total))
    eq(tuple(Q(row[2]) for row in p.tables['v18-c02-lender-cash'][1:]),cash,'lender cash table')
    eq(50+profit+6+6-4-12-25+20-20,cash[-1],'indirect cash bridge')
    stressargs={'withdraw':35,'provision':10,'collected':12}
    sc,sp,sb,sa,_=lender(**stressargs);result('lender-stress',(sc[1],sc[-1],sp,sb['equity'],sb['gross']-sb['allowance'],sb['receivable'],sa))
    rc,rp,rb,ra,_=lender(f=7,x=19,**stressargs);result('lender-repair',(7,19)+rc+(rb['equity'],rb['gross']-rb['allowance'],ra))
    result('e1',(assets,assets+draw));pv=sum((14/(1+rate)**t for t in (1,2)),Q(0));rentpv=sum((2/(1+rate)**t for t in (1,2)),Q(0))
    result('e2',(npv(24,16,2,rate),rentpv,pv,min(60-20,50-20,82-20)))
    result('e3',(60+20-50-20,20-stress[0][1]));result('e4',tuple((academic(investment_return=r)[1],academic(investment_return=r)[2]) for r in (-20,-10,0,10)))
    nc,np,nb,na,_=lender(system=False);result('e5',(nc[-1],nb['equipment'],np,nb['equity'],na));eq(cash[-1]-nc[-1],-7,'first year cash delta');eq(profit-np,1,'first year profit delta')
    fc,fp,fb,fa,_=lender(f=1,x=13,**stressargs);result('e6-failed',fc+(fb['equity'],10-fc[1]))
    ec,ep,eb,ea,_=lender(f=1,x=13,early_principal=True,**stressargs);result('e7',(1,13)+ec+(eb['equity'],eb['gross']-eb['allowance'],ea))
    tc,tp,tb,ta,_=lender(f=8,x=20,**stressargs);result('retention',(academic(early=34)[0][1],academic(early=33)[0][1],academic(early=34)[0][2])+tc+(tb['equity'],))
    academic_worlds=0
    for c,early,ret in product((0,10,24,30,36),(20,33,34,40),(-20,-10,0,10)):
        ac,d,e,k,op,ch,assets,u=academic(cost=c,early=early,investment_return=ret)
        eq(assets,330+ch,'all academic stocks/flows');eq(e+d,200+ret,'draw cancellation');eq(min(ac)>=20,c<=min(40,early-10,62+d-8),'all date constraints');academic_worlds+=1
    funding_worlds=0
    for early,f,x in product((False,True),(0,1,6,Q(13,2),7,8),(0,12,13,19,20)):
        cc,pp,bb,aa,stages=lender(f=f,x=x,early_principal=early,**stressargs)
        eq(min(cc)>=10 and bb['equity']>=32,f>=(1 if early else 7) and x<=min(20,12+f),'global reduced feasible region')
        eq(aa,bb['deposits']+bb['equity'],'closing funding');eq(bb['equity'],40+f+pp,'equity bridge');funding_worlds+=1
    # Exact boundary witnesses support, but do not replace, the algebraic global proofs.
    for inflation,r in product((Q(0),Q(2,100)),(Q(-1,20),Q(0),Q(1,20))):
        bound=200*(r-inflation)
        for d in (0,6,8):eq(200*(1+r)-d>=200*(1+inflation),d<=bound,'real preservation iff')
    invalid=0
    for bad in (lambda:academic(cost=-1),lambda:academic(early=101),lambda:academic(investment_return=-201),lambda:lender(f=-1),lambda:lender(x=21),lambda:lender(withdraw=181),lambda:lender(provision=-1),lambda:lender(collected=21),lambda:npv(12,5,0,rate),lambda:npv(12,5,3,-1),lambda:exact((True,),1),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}'),lambda:rational('f()')):
        try:bad()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid domain accepted')
    require(used==set(marks),'every marker covered')
    return {'chapter':'v18-c02','status':'passed','runtime_files':6,'comparisons':count,'academic_worlds':academic_worlds,'funding_order_worlds':funding_worlds,'invalid_domains':invalid,'scope':'Independent transaction ledgers, full eight solutions and timing/real-preservation proofs; author checker opaque.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage peer [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
