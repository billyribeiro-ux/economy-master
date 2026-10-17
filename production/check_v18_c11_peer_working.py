"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('production/v18-c11-working.html','production/check_v18_c11_working.py','production/v18-c11-sources-working.json','production/v18-c11-author-review-working.json','production/check_v18_c11_peer_working.py','production/v18-c11-peer-review-working.json')
def require(x,msg):
    if not x:raise ValueError('C11 peer: '+msg)
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

def exact(values,n):
    require(isinstance(values,(tuple,list)) and len(values)==n,'dimension');require(all(type(v) in (int,Q) for v in values),'finite exact values');return tuple(Q(v) for v in values)
def project(budgets,scheduled,accepted,costs):
    n=len(budgets);require(n>0,'nonempty tasks');b=exact(budgets,n);z=exact(scheduled,n);a=exact(accepted,n);c=exact(costs,n)
    require(min(b+c)>=0 and all(v in (0,1) for v in z+a),'project domain')
    # Partition the whole register into accepted/rejected and due/not due sets.
    BAC=sum(b);unearned=sum(v for v,ok in zip(b,a) if not ok);future=sum(v for v,due in zip(b,z) if not due);EV=BAC-unearned;PV=BAC-future;AC=sum(c)
    return (BAC,PV,EV,AC,EV-AC,EV-PV,None if not AC else EV/AC,None if not PV else EV/PV),None if not BAC else EV/BAC

def forecast(BAC,EV,AC):
    BAC,EV,AC=exact((BAC,EV,AC),3);require(BAC>=EV>0 and AC>0,'forecast domain');unitcost=AC/EV;remaining=(BAC-EV)*unitcost;return remaining,AC+remaining

def portfolio(p,b,r,s,W,F):
    n=len(p);require(n>0,'sectors');p,b,r,s=(exact(v,n) for v in (p,b,r,s));W,F=exact((W,F),2)
    require(min(p+b)>=0 and sum(p)==sum(b)==1 and min(r+s)>=-1 and W>0 and F>=0,'portfolio domain')
    # Four wealth counterfactuals form a two-factor rectangle; mixed second difference isolates interaction.
    value=lambda weights,returns:sum(W*w*(1+ret) for w,ret in zip(weights,returns))
    bb=value(b,s);pb=value(p,s);br=value(b,r);pr=value(p,r);A=(pb-bb)/W;S=(br-bb)/W;I=(pr-pb-br+bb)/W
    gross=(pr-W)/W;net=(pr-F-W)/W;benchmark=(bb-W)/W
    return (pr,pr-F,gross,net,benchmark,net-benchmark),(A,S,I,gross-benchmark,F/W,net-benchmark)

def bounds(y,lo,hi):
    y,lo,hi=exact((y,lo,hi),3);require(lo<=hi,'ordered sensitivity bounds');return y-hi,y-lo

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];review=strict((root/FILES[5]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'manual review');require(set(review['payloads'])==set(FILES[:5]),'five nonself bindings')
    for name,d in review['payloads'].items():
        raw=(root/name).read_bytes();require(d=={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'binding '+name)
    sources=strict((root/FILES[2]).read_text())['sources'];author=strict((root/FILES[3]).read_text());p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment');require(p.tasks==p.answers==['v18-c11-e'+str(i) for i in range(1,9)],'eight pairs');require(p.worked==['v18-c11-case1','v18-c11-case2'],'two cases');require(set(p.sources)=={(s['id'],s['url']) for s in sources},'actual source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label+': '+str(a)+' != '+str(b))
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,v):eq(read('result',key),v,key)
    rows=p.tables['v18-c11-project-table'][1:];eq(tuple(row[0] for row in rows),tuple('ABCDEF'),'task identifiers');numeric=tuple(tuple(Q(x) for x in row[1:6]) for row in rows);weight,b,z,a,c=tuple(zip(*numeric))
    for w,budget in zip(weight,b):eq(budget,2*w,'budget weight link')
    cp,share=project(b,z,a,c);result('checkpoint',cp);BAC,PV,EV,AC,CV,SV,CPI,SPI=cp
    remaining,total=forecast(BAC,EV,AC);result('forecast',(total,4+8+8,AC+4+8+8,BAC+4,AC+4+8+8-(BAC+4)))
    finalcost,due,actual=read('input','project-final');final,finalshare=project(b,(1,)*6,(1,)*6,finalcost);result('project-final',(final[2],final[3],final[3]-BAC,(final[3]-BAC)/BAC,final[6],final[7],actual-due));eq(finalshare,1,'all accepted');eq(finalcost[2],c[2]+4,'retained rejected cost')
    result('e1',((CV,SV),(CPI,SPI),share,Q(sum(a),len(a))))
    false=list(a);false[2]=Q(1);fp,fshare=project(b,z,tuple(false),c);result('e2',(fp[2],fp[4],fp[5],fp[6],fp[7],fshare,fp[2]-EV,fshare-share))
    result('e3',(remaining,total,AC+4+8+8,AC+4+7+7,AC+4+8+7,AC+4+8+7-(BAC+4),BAC+4-AC-4))
    pr=p.tables['v18-c11-portfolio-table'][1:];eq(tuple(row[0] for row in pr),('C','D'),'sector IDs');pp,bb,rr,ss=tuple(zip(*(tuple(Q(x) for x in row[1:]) for row in pr)));W,F=read('input','portfolio-cash');wealth,attribution=portfolio(pp,bb,rr,ss,W,F);result('wealth',wealth);result('attribution',attribution);A,S,I,grossactive,feerate,netactive=attribution
    result('causal-bounds',bounds(W*wealth[3],8,14));result('e5',(S+I,A+S+2*I,I));new,_=portfolio(pp,pp,rr,ss,W,F);result('e6',(new[4],new[-1],new[-1]-netactive));result('e7',(bounds(W*wealth[3],8,14),bounds(W*wealth[3],9,11)))
    highercost=list(finalcost);highercost[4]+=1;late,_=project(b,(1,)*6,(1,)*6,tuple(highercost));retw,reta=portfolio(pp,bb,(rr[0],Q(1,4)),ss,W,1);result('retention',(late[3],late[3]-(BAC+4),late[6],retw[2],retw[3],reta[0],reta[1],reta[2],reta[-1]))
    project_worlds=0
    for acceptance in product((0,1),repeat=6):
        witness,wshare=project(b,z,acceptance,c);ev=sum(x*y for x,y in zip(b,acceptance));eq(witness[2],ev,'direct earned sum');eq(witness[4]+AC,ev,'variance bridge');eq(wshare*BAC,ev,'weighted progress');project_worlds+=1
        if ev:rem,forecasted=forecast(BAC,ev,AC);eq(forecasted,BAC/(ev/AC),'forecast equivalence')
    zero,zero_share=project((0,),(0,),(0,),(0,));eq(zero,(0,0,0,0,0,0,None,None),'zero denominators');eq(zero_share,None,'zero total scope');zero2,_=project((4,),(0,),(1,),(0,));eq(zero2[6:],(None,None),'earned with zero denominator')
    portfolio_worlds=0
    for pa,ba,ra,rb in product((Q(0),Q(1,2),Q(1)),(Q(0),Q(1,3),Q(1)),(Q(-1),Q(1,10)),(Q(-1,5),Q(1,4))):
        ww,at=portfolio((pa,1-pa),(ba,1-ba),(ra,rb),ss,W,F);allocation=sum((x-y)*s for x,y,s in zip((pa,1-pa),(ba,1-ba),ss));selection=sum(x*(r-s) for x,r,s in zip((ba,1-ba),(ra,rb),ss));interaction=sum((x-y)*(r-s) for x,y,r,s in zip((pa,1-pa),(ba,1-ba),(ra,rb),ss));eq(at[:3],(allocation,selection,interaction),'product expansion');eq(sum(at[:3]),ww[2]-ww[4],'rectangle identity');eq(sum((x-y)*(s-ww[4]) for x,y,s in zip((pa,1-pa),(ba,1-ba),ss)),allocation,'centered allocation');portfolio_worlds+=1
    sensitivity_worlds=0
    for low,high in ((8,14),(9,11),(10,10),(-2,8)):
        lower,upper=bounds(10,low,high)
        for i in range(11):
            counter=Q(low)+Q(i,10)*(high-low);effect=10-counter;eq(lower<=effect<=upper,True,'sharp compatible world');sensitivity_worlds+=1
        eq((10-high,10-low),(lower,upper),'endpoints attain');eq(lower>0,high<10,'strict positive condition')
    for fee in (0,1,2,10,120):
        ww,at=portfolio(pp,bb,rr,ss,W,fee);eq(ww[-1],grossactive-Q(fee,W),'fee counterfactual');eq(ww[-1]<0,True,'no fee rescues negative grossactive')
    invalid=0
    bad=[lambda:project((),(),(),()),lambda:project((1,),(2,),(0,),(0,)),lambda:project((1,),(0,),(Q(1,2),),(0,)),lambda:project((-1,),(0,),(0,),(0,)),lambda:project((1,),(0,),(0,),(-1,)),lambda:project((1.,),(0,),(0,),(0,)),lambda:forecast(32,0,18),lambda:forecast(32,12,0),lambda:forecast(10,12,18),lambda:portfolio(pp,bb,rr,ss,0,F),lambda:portfolio(pp,bb,rr,ss,W,-1),lambda:portfolio((1,1),bb,rr,ss,W,F),lambda:portfolio(pp,bb,(-2,0),ss,W,F),lambda:bounds(10,14,8),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":Infinity}')]
    for call in bad:
        try:call()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    require(used==set(marks),'all markers consumed')
    return {'status':'passed','comparisons':count,'project_acceptance_worlds':project_worlds,'portfolio_worlds':portfolio_worlds,'sensitivity_worlds':sensitivity_worlds,'invalid_domains':invalid,'worked_cases':2,'solutions':8}
if __name__=='__main__':
    if len(sys.argv)>2:raise ValueError('at most one root')
    check(sys.argv[1] if len(sys.argv)==2 else None)
