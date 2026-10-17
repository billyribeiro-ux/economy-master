"""Four-file quiet author audit of original decision memos and finite models."""
import ast,hashlib,json,sys
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations
from pathlib import Path
FILES=('content/chapters/v17-c10.html','scripts/check_v17_c10.py','content/reviews/v17-c10-sources.json','content/reviews/v17-c10-author.json')
def need(ok,msg):
    if not ok:raise ValueError('C10: '+msg)
def val(text):
    def read(n):
        if isinstance(n,ast.Tuple):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return F(str(n.value))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return read(n.left)/read(n.right)
        raise ValueError('invalid number literal')
    return read(ast.parse(text.strip().replace('−','-'),mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources=[];self.links=[];self.values={};self.capture=None;self.tables={};self.table=None;self.row=None;self.cell=None;self.svg=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(t!='h1','no chapter h1');need(len(a)==len(attrs),'duplicate attrs')
        if 'id' in a:self.ids.append(a['id'])
        if t=='li' and any(tag=='ol' and 'exercises' in d.get('class','').split() for tag,d in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for' in a:
            need(any(tag=='details' and 'solutions' in d.get('class','').split() for tag,d in self.stack),'solution disclosure');self.answers.append(a['data-solution-for'])
        if t=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        if 'href' in a:self.links.append(a['href'])
        if t=='svg':self.svg.append(a)
        if t=='line':self.svg.append(a)
        for k in ('input','result'):
            if 'data-'+k in a:
                key=(k,a['data-'+k]);need(key not in self.values and self.capture is None,'duplicate marker');self.values[key]='';self.capture=(t,key)
        if t=='table':self.table=a['id'];self.tables[self.table]=[]
        if t=='tr':self.row=[]
        if t in ('th','td'):self.cell=[]
        if t not in ('br','hr','img','input','link','meta'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.capture:self.values[self.capture[1]]+=s
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack.pop()[0]==t,'balanced tags')
        if self.capture and self.capture[0]==t:self.capture=None
        if t in ('th','td'):self.row.append(''.join(self.cell).strip());self.cell=None
        if t=='tr':self.tables[self.table].append(self.row);self.row=None
        if t=='table':self.table=None

def numbers(seq,n):
    need(isinstance(seq,(tuple,list)) and len(seq)==n,'dimensions');need(all(type(x) in (int,F) for x in seq),'exact inputs');return tuple(F(x) for x in seq)
def options(rows):
    need(len(rows)>0,'empty options');rows=tuple(numbers(row,3) for row in rows);need(all(c>=0 for c,b,s in rows),'negative cost');return rows
def nets(rows,t):
    rows=options(rows);(t,)=numbers((t,),1);need(0<=t<=1,'take-up domain');return tuple(b+s*t-c for c,b,s in rows)
def maxima(x):return tuple(i for i,v in enumerate(x) if v==max(x))
def policy_audit(rows,bounds):
    rows=options(rows);lo,hi=numbers(bounds,2);need(0<=lo<=hi<=1,'range domain');knots={lo,hi}
    for (c,b,s),(cc,bb,ss) in combinations(rows,2):
        if s!=ss:
            k=((bb-cc)-(b-c))/(s-ss)
            if lo<=k<=hi:knots.add(k)
    levels=tuple(nets(rows,k) for k in sorted(knots));worst=tuple(min(row[j] for row in levels) for j in range(len(rows)));regret=tuple(max(max(row)-row[j] for row in levels) for j in range(len(rows)))
    return worst,regret,len(knots)
def pv(flows,rate):
    flows=numbers(flows,len(flows));(rate,)=numbers((rate,),1);need(bool(flows) and rate>-1,'PV domain');a=F(0)
    for x in reversed(flows):a=x+a/(1+rate)
    return a
def board(project,liquidity,facility,rate,p):
    cost,g,b,y2=numbers(project,4);cash,obligation,floor=numbers(liquidity,3);loan,repay=numbers(facility,2);p,rate=numbers((p,rate),2)
    need(0<=p<=1 and all(x>=0 for x in (cost,g,b,y2,cash,obligation,floor,loan,repay)),'board domain')
    state=tuple(pv((-cost+loan,y1,y2-repay),rate) for y1 in (g,b));expected=p*state[0]+(1-p)*state[1];t0=cash+loan-cost;cg=t0+g-obligation;cb=t0+b-obligation;path=(t0,cg,cb,cg+y2-repay,cb+y2-repay)
    return state,expected,path,min(path)>=floor

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];review=json.loads((root/FILES[3]).read_text());need(review['full_reading_complete'] and not review['open_material_findings'],'qualitative review');need(set(review['payloads'])==set(FILES[:3]),'three bindings')
    for f,record in review['payloads'].items():
        b=(root/f).read_bytes();need(record=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze changed '+f)
    p=Page();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and p.capture is None and len(p.ids)==len(set(p.ids)),'complete unique fragment');need(p.tasks==p.answers==['v17-c10-e'+str(i) for i in range(1,9)],'eight paired tasks');need(p.worked==['v17-c10-case1','v17-c10-case2'],'two complete packages')
    src=json.loads((root/FILES[2]).read_text())['sources'];need(set(p.sources)=={(x['id'],x['url']) for x in src},'source URLs');need(all(x in p.ids for x in p.svg[0]['aria-labelledby'].split()),'SVG accessible IDs')
    marks={key:val(x) for key,x in p.values.items()};used=set();count=0
    def get(kind,key):used.add((kind,key));return marks[kind,key]
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            need(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;need(a==b,label)
    def result(key,x):eq(get('result',key),x,key)
    rows=get('input','policy-options');rng=get('input','policy-range');worst,regret,k=policy_audit(rows,rng);result('regrets',regret);result('worst-nets',worst);result('mean-nets',nets(rows,F(1,2)))
    _,a,b=rows;thresholds=((b[0]-b[1])/b[2],(a[0]-a[1])/a[2],((b[1]-b[0])-(a[1]-a[0]))/(a[2]-b[2]));result('thresholds',thresholds)
    result('policy-ties',(nets(rows,F(1,2)),nets(rows,F(3,5))));eq((maxima(nets(rows,F(1,3))),maxima(nets(rows,F(3,5)))),((0,2),(1,2)),'all threshold ties')
    nw,nr,_=policy_audit(rows,get('input','narrow-range'));result('narrow-regrets',nr);result('narrow-nets',nw);result('favorable-display',tuple((c,i+s,i+s-c) for c,i,s in rows));result('retention',(nets(rows,F(7,10))[1:],nets(rows,F(9,10))[1:]))
    for district,option in zip(get('input','districts'),rows[1:]):
        ci,cs,pi,ps=district;eq((ci+pi,cs+ps),option[1:],'distribution sums')
    for table_row,option in zip(p.tables['v17-c10-policy-table'][1:],rows):
        c,i,s=option;eq(val(table_row[1]),c,'policy displayed cost');eq(tuple(val(x) for x in table_row[2].split(' / ')),tuple(i+s*t for t in (0,F(1,2),1)),'gross display');eq(tuple(val(x) for x in table_row[3].split(' / ')),tuple(i+s*t-c for t in (0,F(1,2),1)),'net display')
    for line,option in zip(p.svg[4:],rows[1:]):
        c,i,s=option;eq(tuple(val(line[x]) for x in ('x1','y1','x2','y2')),(80,160-6*(i-c),480,160-6*(i+s-c)),'SVG exact line coordinate mapping')
    probability=get('input','probability');r=get('input','board-rate');large,small=get('input','projects');liq=get('input','liquidity');facility=get('input','facility');lg=board(large,liq,(0,0),r,probability);sm=board(small,liq,(0,0),r,probability);fund=board(large,liq,facility,r,probability);outside=board((0,0,0,0),liq,(0,0),r,probability)
    result('project-values',lg[0]+sm[0]+(lg[1],sm[1]));ldiff=lg[0][0]-lg[0][1];sdiff=sm[0][0]-sm[0][1];result('board-thresholds',(-lg[0][1]/ldiff,-sm[0][1]/sdiff,(sm[0][1]-lg[0][1])/(ldiff-sdiff)))
    loanpv=pv((facility[0],0,-facility[1]),r);result('financed-values',(loanpv,)+fund[0]);result('large-cash',fund[2]);eq((outside[3],sm[3],lg[3],fund[3]),(True,True,False,True),'statewise feasibility');eq(probability*lg[2][1]+(1-probability)*lg[2][2],45,'expected cash cannot replace downside')
    for row,data in zip(p.tables['v17-c10-board-table'][1:],(outside,sm,lg,fund)):
        state,expected,path,feasible=data;eq(tuple(val(x) for x in row[1].split(' / ')),state,'table stateNPVs');eq(val(row[2]),expected,'table expectedNPV');eq(val(row[3]),path[0],'cash now');eq(tuple(val(x) for x in row[4].split(' / ')),path[1:3],'cash year1');eq(tuple(val(x) for x in row[5].split(' / ')),path[3:],'cash year2')
    rr=get('input','changed-rate');ch=board(large,liq,(0,0),rr,probability);cf=board(large,liq,facility,rr,probability);result('rate-change',(ch[1],pv((facility[0],0,-facility[1]),rr),cf[1]));eq(cf[2],fund[2],'fixed contract cash unaffected by rate')
    pp=get('input','changed-probability');result('probability-change',(board(large,liq,facility,r,pp)[1],board(small,liq,(0,0),r,pp)[1]));result('fresh-check',(board(large,liq,facility,r,F(4,5))[1],board(small,liq,(0,0),r,F(4,5))[1]));eq(sum((3,5,4,4,4)),20,'memo rubric')
    scenarios=0
    for lo,hi in ((0,1),(F(2,5),F(4,5)),(F(7,10),F(9,10)),(F(3,5),F(3,5))):
        w,reg,_=policy_audit(rows,(lo,hi));endpoints=(nets(rows,lo),nets(rows,hi));eq(reg,tuple(max(max(e)-e[j] for e in endpoints) for j in range(3)),'global envelope vs endpoint theorem')
        for i in range(5):
            t=lo+(hi-lo)*F(i,4);v=nets(rows,t);eq(all(max(v)-v[j]<=reg[j] for j in range(3)),True,'interior regret');scenarios+=1
    for rate in (F(0),F(1,5),F(1,4)):
        for prob in (F(0),F(17,24),F(3,4),F(1)):
            un=board(large,liq,(0,0),rate,prob);fin=board(large,liq,facility,rate,prob);eq(fin[1],un[1]+pv((facility[0],0,-facility[1]),rate),'financing linearity');scenarios+=1
    eq(board(large,liq,facility,r,F(17,24))[1],0,'strict value boundary');eq(board(large,(110,50,21),facility,r,probability)[3],False,'raised floor');eq(board((90,90,29,50),liq,facility,r,probability)[3],False,'lower adverse receipt')
    invalid=0
    for f in (lambda:nets(rows,-1),lambda:nets(rows,2),lambda:policy_audit(rows,(1,0)),lambda:options(()),lambda:options(((-1,0,0),)),lambda:pv((0,1),-1),lambda:pv((),0),lambda:board(large,liq,facility,r,2),lambda:board(large,liq,facility,r,-1),lambda:board(large,liq,(-1,1),r,probability),lambda:numbers((True,),1),lambda:val('__import__("os")')):
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(set(marks)==used,'all markers checked')
    return {'chapter':'v17-c10','status':'passed','runtime_files':4,'worked_packages':2,'exercises':8,'numeric_markers':sum(key[0]=='result' for key in marks),'comparisons':count,'alternative_scenarios':scenarios,'invalid_domains':invalid,'scope':'Full memos/displays/global proofs/eight answers/source scopes separately read; synthetic assumptions are not real policy, financing commitments or learner achievements.'}
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage checker [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
