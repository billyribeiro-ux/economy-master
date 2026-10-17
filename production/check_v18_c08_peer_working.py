"""V18C08 independent frontier/cash-elimination and transaction oracle."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product, combinations
import hashlib,json,sys,ast,math
FILES=('production/v18-c08-working.html','production/check_v18_c08_working.py','production/v18-c08-sources-working.json','production/v18-c08-author-review-working.json','production/check_v18_c08_peer_working.py','production/v18-c08-peer-review-working.json')
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

def replace(data,index,value):
    out=list(data);out[index]=F(value);return tuple(out)
def growth(data,books):
    c,n,d,e,w,loss,cf,ef,cap=vector(data,9);a,p=vector(books[0],2);b,q=vector(books[1],2)
    need(min(c,n,d,e,w,loss,cf,ef,cap)>=0 and c+n==d+e and w<=d and loss<=n,'growth balance domain')
    need(a>0 and b>0 and p>0 and q>0,'positive book rate domain')
    cashlimit=c-w-cf;risklimit=e-loss-ef
    if min(cashlimit,risklimit)<0:return None
    # For each x positive q makes the highest feasible y optimal. Check all frontier kinks.
    xmax=min(cap,cashlimit,risklimit/a)
    candidates={F(0),xmax,cap,cashlimit-cap,(risklimit-b*cap)/a}
    if b!=a:candidates.add((b*cashlimit-risklimit)/(b-a))
    scores={}
    for x in candidates:
        if 0<=x<=xmax:
            y=min(cap,cashlimit-x,(risklimit-a*x)/b)
            if y>=0:scores[(x,y)]=p*x+q*y
    maximum=max(scores.values());choices=tuple(sorted(k for k,v in scores.items() if v==maximum))
    return {'choices':choices,'value':maximum,'cashlimit':cashlimit,'risklimit':risklimit}

def growth_ledger(data,books,x,y):
    c,n,d,e,w,loss,cf,ef,cap=vector(data,9);amount=x+y;newloss=books[0][0]*x+books[1][0]*y
    rows=[(c,n,d,e)]
    for delta in ((0,amount,amount,0),(-amount,0,-amount,0),(-w,0,-w,0),(0,-loss-newloss,0,-loss-newloss)):
        rows.append(tuple(a+b for a,b in zip(rows[-1],delta)))
        need(rows[-1][0]+rows[-1][1]==rows[-1][2]+rows[-1][3],'growth transaction balance')
    return tuple(rows)

def funding(data):
    c,s,n,deposits,e,w,loss,cf,ef,cap,d,f,h=vector(data,13)
    need(min(c,s,n,deposits,e,w,loss,cf,ef,cap)>=0 and c+s+n==deposits+e and w<=deposits and loss<=n,'funding balance domain')
    need(0<=d<1 and 0<=f<1 and 0<=h<=1,'funding rate domain')
    required=cf+w-c;k=1-h;split=required/(1-f)
    candidates={}
    # Minimum required sale is affine in borrowing until zero; more sale only costs/encumbers more.
    for left,right,intercept,slope in [(F(0),min(cap,split),required/(1-d),-(1-f)/(1-d)),(max(F(0),split),cap,F(0),F(0))]:
        low=max(F(0),left);high=min(cap,right)
        # Enforce sale nonnegative, available stock and collateral using scalar half-intervals.
        for const,coef in ((intercept,slope),(s-intercept,-slope),(k*(s-intercept),-1-k*slope)):
            if coef>0:low=max(low,-const/coef)
            elif coef<0:high=min(high,-const/coef)
            elif const<0:low=high+1
        if low<=high:
            for borrow in (low,high):
                sale=intercept+slope*borrow;erosion=d*sale+f*borrow
                candidates[(sale,borrow)]=erosion
    if not candidates:return {'cash_only':None,'joint':False}
    best=min(candidates.values());choices=tuple(sorted(x for x,v in candidates.items() if v==best))
    return {'cash_only':choices,'erosion':best,'joint':e-loss-best>=ef,'lossbudget':e-loss-ef,'required':required}

def funding_ledger(data,sale,borrow):
    c,s,n,deposits,e,w,loss,cf,ef,cap,d,f,h=data
    # Six entries: cash, securities, net loans, deposits, borrowing, equity.
    rows=[(c,s,n,deposits,F(0),e)]
    for delta in ((0,0,-loss,0,0,-loss),((1-d)*sale,-sale,0,0,0,-d*sale),(borrow,0,0,0,borrow,0),(-f*borrow,0,0,0,0,-f*borrow),(-w,0,0,-w,0,0)):
        row=tuple(a+b for a,b in zip(rows[-1],delta));need(sum(row[:3])==sum(row[3:]),'funding transaction balance');rows.append(row)
    return tuple(rows)

def repay(row,collection,principal,equity_issue=F(0)):
    c,s,n,d,b,e=row;need(0<=collection<=n and 0<=principal<=b and equity_issue>=0,'repayment domain')
    new=(c+collection-principal+equity_issue,s,n-collection,d,b-principal,e+equity_issue)
    need(sum(new[:3])==sum(new[3:]),'repayment/equity identity');return new

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    start={f:digest(root/f) for f in FILES};review=json.loads((root/FILES[-1]).read_text());need(set(review['payloads'])==set(FILES[:-1]),'five nonself bindings')
    for f,b in review['payloads'].items():need(start[f]==b,'payload '+f)
    page=Page();page.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text())
    need(not page.h1 and len(page.ids)==len(set(page.ids)),'unique IDs/no h1')
    tasks=['v18-c08-e'+str(i) for i in range(1,9)];need(page.exercises==page.answers==tasks,'eight matched answers')
    need(page.worked==['v18-c08-case1','v18-c08-case2'],'two complete cases')
    need(set(page.sources)=={(s['id'],s['url']) for s in sources['sources']},'source URLs')
    inputs={k:parse(v) for k,v in page.inputs.items()};shown={k:parse(v) for k,v in page.results.items()};need(set(inputs)=={'growth','books','funding'},'all primitives')
    g=inputs['growth'];books=inputs['books'];f=inputs['funding'];count=0
    initial=growth(g,books);need(len(initial['choices'])==1,'unique growth');x,y=initial['choices'][0];seq=growth_ledger(g,books,x,y);last=seq[-1]
    expected={'growth-optimum':(x,y,initial['value']),'growth-ledger':last+(sum(last[:2]),),'pay':(F(9,10)-F(3,10),(F(9,10)-F(3,10))/10)}
    independent_stages=((30,170,180,20),(30,185,195,20),(15,185,180,20),(10,185,175,20),(10,178,175,13))
    need(seq==independent_stages,'all exact origination/settlement/loss stages');count+=20
    result=funding(f);need(result['joint'] and len(result['cash_only'])==1,'unique funded optimum');sale,borrow=result['cash_only'][0];fseq=funding_ledger(f,sale,borrow);fl=fseq[-1]
    expected['funding-optimum']=(sale,borrow,result['erosion'],(1-f[-1])*(f[1]-sale));expected['funding-ledger']=fl+(sum(fl[:3]),)
    date2=repay(fl,F(25),borrow);expected['repayment']=(date2[0],date2[2],date2[4],date2[5],sum(date2[:3]))
    lossdata=replace(g,5,5);z=growth(lossdata,books);need(len(z['choices'])==1,'unique changed loss');xx,yy=z['choices'][0];row=growth_ledger(lossdata,books,xx,yy)[-1]
    expected['growth-loss-optimum']=(xx,yy,z['value']);expected['growth-loss-change']=row+(sum(row[:2]),)
    floordata=replace(g,6,9);z=growth(floordata,books);need(len(z['choices'])==1,'unique changed floor');xx,yy=z['choices'][0];row=growth_ledger(floordata,books,xx,yy)[-1]
    expected['growth-floor-optimum']=(xx,yy,z['value'],z['value']-initial['value']);expected['growth-floor-change']=row+(sum(row[:2]),)
    capdata=replace(f,9,10);z=funding(capdata);need(z['joint'] and len(z['cash_only'])==1,'unique cap revision');ss,bb=z['cash_only'][0];row=funding_ledger(capdata,ss,bb)[-1]
    expected['funding-cap-change']=(ss,bb,z['erosion'],(1-capdata[-1])*(capdata[1]-ss));expected['funding-cap-ledger']=row+(sum(row[:3]),)
    discountdata=replace(f,10,F(1,5));z=funding(discountdata);ss,bb=z['cash_only'][0];row=funding_ledger(discountdata,ss,bb)[-1];need(not z['joint'],'discount joint infeasible');count+=1
    expected['funding-discount-change']=(ss,bb,z['erosion'],row[-1],discountdata[8]-row[-1])
    short=repay(fl,F(15),borrow);restored=repay(fl,F(15),borrow,f[7]-short[0]);expected['repayment-equity']=(restored[0],restored[2],restored[4],restored[5],sum(restored[:3]))
    need(short[0]==3 and short[2]==87 and short[4]==0 and sum(short[:3])==sum(date2[:3]),'collection changes composition');count+=4
    rows=[]
    for runoff in (56,57):
        revised=replace(f,5,runoff);z=funding(revised);ss,bb=z['cash_only'][0];row=funding_ledger(revised,ss,bb)[-1];rows.extend((ss,z['erosion'],row[-1]));need(z['joint']==(runoff==56),'runoff feasibility boundary');count+=1
    expected['retention']=tuple(rows)
    need(set(expected)==set(shown),'every result marker')
    def leaves(x):return sum(leaves(v) for v in x) if isinstance(x,tuple) else 1
    for key,value in expected.items():need(shown[key]==value,'displayed '+key);count+=leaves(value)
    # Verify printed global certificates algebraically, including unique binding equations.
    for xx,yy in ((F(0),F(10)),(F(12),F(3)),(x,y),(F(12),F(8,3))):
        p=books[0][1]*xx+books[1][1]*yy;l=books[0][0]*xx+books[1][0]*yy
        need(p==F(3,50)*(xx+yy)+F(1,5)*l==xx/25+F(2,5)*l,'both dual identities');count+=2
    growth_worlds=0
    for oldloss,floor in product((3,4,5,7),(8,9,10,20,25)):
        data=replace(replace(g,5,oldloss),6,floor);opt=growth(data,books);growth_worlds+=1
        if opt is None:continue
        for xx,yy in product(range(13),repeat=2):
            if xx+yy<=opt['cashlimit'] and books[0][0]*xx+books[1][0]*yy<=opt['risklimit']:
                need(books[0][1]*xx+books[1][1]*yy<=opt['value'],'independent integer feasible witness');count+=1
        for xx,yy in opt['choices']:
            row=growth_ledger(data,books,xx,yy)[-1];need(row[0]>=data[6] and row[3]>=data[7],'growth ledger floors');count+=2
    funding_worlds=0
    for discount,fee,cap in product((F(0),F(1,10),F(1,5)),(F(0),F(1,50),F(1,10)),(10,20)):
        data=replace(replace(replace(f,10,discount),11,fee),9,cap);opt=funding(data);funding_worlds+=1
        if opt['cash_only'] is None:continue
        for sale0,borrow0 in product(range(0,81,4),range(0,cap+1,2)):
            if data[0]+(1-discount)*sale0+(1-fee)*borrow0-data[5]>=data[7] and borrow0<=(1-data[12])*(data[1]-sale0):
                need(discount*sale0+fee*borrow0>=opt['erosion'],'independent feasible funding witness');count+=1
        for sale0,borrow0 in opt['cash_only']:
            ledger=funding_ledger(data,sale0,borrow0)[-1];need(ledger[0]>=data[7] and borrow0<=(1-data[12])*ledger[1],'cash/collateral candidate');count+=2
    boundary=funding(replace(f,10,F(9,50)));need(boundary['joint'] and boundary['erosion']==4 and boundary['cash_only']==((20,20),),'exact adverse discount threshold');count+=3
    worse=funding(replace(f,10,F(181,1000)));need(not worse['joint'],'above threshold');count+=1
    tie=funding(replace(f,11,F(1,10)));need(len(tie['cash_only'])>1,'equal costs genuine nonunique witness');count+=1
    no_need=funding(replace(f,5,0));need(no_need['erosion']==0 and (0,0) in no_need['cash_only'],'zero funding need');count+=2
    no_equity=funding(replace(f,8,15));need(not no_equity['joint'],'existing loss breaches equity before funding');count+=1
    need(len(page.tables['v18-c08-growth-controls'])==6,'five substantive operating rows')
    invalid=0
    bad=[lambda:growth(replace(g,3,21),books),lambda:growth(replace(g,4,181),books),lambda:growth(replace(g,5,171),books),lambda:growth(g,((0,F(2,25)),books[1])),lambda:funding(replace(f,10,1)),lambda:funding(replace(f,11,-1)),lambda:funding(replace(f,12,F(3,2))),lambda:funding(replace(f,9,-1)),lambda:funding(replace(f,4,21)),lambda:funding(replace(f,6,109)),lambda:repay(fl,F(103),20),lambda:repay(fl,25,21),lambda:parse('(1,0.5)'),lambda:vector((True,2))]
    for fn in bad:
        try:fn()
        except ValueError:invalid+=1
        else:raise ValueError('invalid accepted')
    need(start=={f:digest(root/f) for f in FILES},'runtime mutation')
    answer={'chapter':'v18-c08','status':'passed','runtime_files':6,'worked_cases':2,'exercises':8,'result_groups':len(shown),'comparisons':count,'growth_worlds':growth_worlds,'funding_worlds':funding_worlds,'invalid_domains':invalid,'scope':'Independent one-dimensional frontier/funding elimination and transaction records; full proof/artifact review separate; author checker opaque.'}
    json.dumps(answer,allow_nan=False);return answer
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_c08_peer_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
