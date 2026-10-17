"""Independent primitive audit; author checker is an opaque hash-bound payload."""
import ast, hashlib, json, re, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/cross-assessments/leadership-portfolio.html','scripts/check_leadership_portfolio.py','content/reviews/leadership-portfolio-sources.json','content/reviews/leadership-portfolio-author.json','scripts/check_leadership_portfolio_peer.py','content/reviews/leadership-portfolio-peer.json')
def require(x,msg):
    if not x:raise ValueError('Leadership peer: '+msg)
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
        super().__init__();self.h1=0;self.artifacts=[];self.alltext=[];self.links=[];self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources=[];self.numbers={};self.active=None;self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attrs');self.h1+=int(t=='h1')
        if 'id' in a:self.ids.append(a['id'])
        if 'data-artifact' in a:self.artifacts.append(a['data-artifact'])
        if 'href' in a:self.links.append(a['href'])
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
        self.alltext.append(s)
        if self.active:self.numbers[self.active[1]]+=s
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,t):
        require(bool(self.stack) and self.stack.pop()[0]==t,'balanced fragment')
        if self.active and self.active[0]==t:self.active=None
        if t in ('th','td'):self.row.append(''.join(self.cell).strip());self.cell=None
        if t=='tr':self.tables[self.table].append(self.row);self.row=None
        if t=='table':self.table=None

def exact(values,n):
    require(isinstance(values,(tuple,list))and len(values)==n,'dimensions');require(all(type(x)in(int,Q)for x in values),'finite rational inputs');return tuple(Q(x)for x in values)
def selection(options,budget,hours,grant):
    budget,hours,grant=exact((budget,hours,grant),3);require(min(budget,hours,grant)>=0,'resource domain');require(len(options)==3,'three options');options=tuple(exact(r,3)for r in options);require(all(min(r)>=0 for r in options),'option domain');rows=[]
    for size in range(8):
        bits=tuple((size>>i)&1 for i in range(3));cost=sum(t*r[0]for t,r in zip(bits,options));restricted=min(grant,options[0][0])if bits[0]else Q(0);staff=sum(t*r[1]for t,r in zip(bits,options));score=sum(t*r[2]for t,r in zip(bits,options));rows.append((bits,cost-restricted,staff,score,cost-restricted<=budget and staff<=hours))
    feasible=[r for r in rows if r[-1]];best=max(r[3]for r in feasible);return tuple(r for r in feasible if r[3]==best),tuple(rows)

def journal(opening,events):
    opening=exact(opening,5);require(min(opening)>=0 and sum(opening[:3])==sum(opening[3:]),'opening balance');deltas=[(Q(0),)*5];states=[opening]
    for dc,dp,dl,de in events:
        dc,dp,dl,de=exact((dc,dp,dl,de),4);require(dc+dp==dl+de,'balanced event');deltas.append((dc,dp,Q(0),dl,de));state=tuple(opening[i]+sum(row[i]for row in deltas)for i in range(5));require(state[1]>=0,'prepaid consumption domain');states.append(state)
    return tuple(states)

def schedule(hours,targets,rates):
    HA,HB=exact(hours,2);TX,TY=exact(targets,2);a,b,c,d=exact(rates,4);require(min(HA,HB)>=0 and min(TX,TY,a,b,c,d)>0,'schedule domain')
    # On each side of the equal-ratio line objective is linear. Its rectangle/line vertices suffice.
    coef_t=TY*a+TX*b;coef_u=TY*c+TX*d;rhs=TX*(b*HA+d*HB);points={(t,u)for t in (Q(0),HA)for u in (Q(0),HB)}
    for t in (Q(0),HA):
        u=(rhs-coef_t*t)/coef_u
        if 0<=u<=HB:points.add((t,u))
    for u in (Q(0),HB):
        t=(rhs-coef_u*u)/coef_t
        if 0<=t<=HA:points.add((t,u))
    result=[]
    for t,u in points:
        X=a*t+c*u;Y=b*(HA-t)+d*(HB-u);z=min(X/TX,Y/TY);result.append((t,u,X,Y,z))
    best=max(row[-1]for row in result);return tuple(sorted(row for row in result if row[-1]==best)),tuple(sorted(result))

def check(root=None):
    root=Path(root).resolve()if root is not None else Path(__file__).resolve().parents[1];review=strict((root/FILES[5]).read_text());require(review['full_reading_complete']and not review['open_material_findings'],'full review');require(set(review['payloads'])==set(FILES[:5]),'five bindings')
    for name,binding in review['payloads'].items():
        raw=(root/name).read_bytes();require(binding=={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'binding '+name)
    sources=strict((root/FILES[2]).read_text())['sources'];strict((root/FILES[3]).read_text());p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids))and p.h1==1,'complete fragment with oneh1');ids=['leadership-task-'+str(i)for i in range(1,4)]+['leadership-d'+str(i)for i in range(1,7)];require(p.tasks==p.answers==ids,'nine complete answers');require(p.worked==['leadership-case-'+str(i)for i in range(1,4)],'three cases');require(p.artifacts==['strategy','resources','governance','people','crisis','retrospective'],'six artifacts');require(set(p.sources)=={(s['id'],s['url'])for s in sources},'scoped source URLs');require(all('v'+v+'-assessment.html'in p.links for v in ('07','08','11','16','17','18'))and all('v18-c'+str(i).zfill(2)+'.html'in p.links for i in range(1,13)),'all prerequisite/capability links')
    forms=['role','claim','resource','observer','response','defense'];require(all('leadership-form-'+f in p.tables for f in forms),'six forms');text=' '.join(p.alltext);marks={k:rational(v)for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple)or isinstance(b,tuple):
            require(isinstance(a,tuple)and isinstance(b,tuple)and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label+': '+str(a)+' != '+str(b))
    def result(key,value):used.add(('result',key));eq(marks['result',key],value,key)
    rows=p.tables['leadership-options'][1:];eq(tuple(r[0]for r in rows),('A','B','C'),'options');options=tuple(tuple(Q(s)for s in row[1:4])for row in rows)
    budget=Q(re.search(r'unrestricted budget is(\d+) kCU',text).group(1));hours=Q(re.search(r'available staff capacity is(\d+) blocks',text).group(1));grant=Q(re.search(r'A(\d+) kCU grant has been promised',text).group(1));base,allrows=selection(options,budget,hours,0);funded,_=selection(options,budget,hours,grant);eq(len(base),1,'baseunique');eq(len(funded),1,'fundedunique');result('case1',(base[0][1:4],funded[0][1:4]+(hours-funded[0][2],)))
    opening=tuple(Q(x)for x in re.search(r'Opening cash(\d+) plus other assets(\d+) equals liabilities(\d+) plus equity(\d+)',text).groups());opening=(opening[0],Q(0),opening[1],opening[2],opening[3]);eventrows=p.tables['leadership-finance-events'][1:];events=tuple(tuple(Q(x)for x in row[1:5])for row in eventrows);states=journal(opening,events);result('case2-ledgers',states[:5]);eq(states[-1],states[-2],'proposal not receipt');floor=Q(re.search(r'cash at least(\d+) at every recorded event',text).group(1));last=states[-1];needed=max(Q(0),floor-last[0]);repair=(last[0]+needed,)+last[1:4]+(last[4]+needed,);staged=list(events);staged[0]=(-Q(5),Q(5),Q(0),Q(0));stagedstates=journal(opening,tuple(staged));result('case2-repair',(needed,repair,stagedstates[-1],-events[0][0]-5));eq(tuple(max(Q(0),floor-s[0])for s in states),(0,0,1,1,3,3),'dated breaches')
    target=tuple(Q(x)for x in re.search(r'targets are(\d+) and(\d+) units',text).groups());rates=tuple(Q(x)for x in re.search(r'A produces(\d+) X or(\d+) Y per hour; B produces(\d+) X or(\d+) Y',text).groups());HA=Q(re.search(r'each limited to(\d+) paid hours',text).group(1));H=(HA,HA);best,candidates=schedule(H,target,rates);eq(len(best),1,'unique optimum');firstX=rates[0]*HA;firstY=rates[3]*HA;first=(firstX,firstY,firstX/target[0],firstY/target[1],min(firstX/target[0],firstY/target[1]));result('case3',(first,best[0],best[0][-1]-first[-1]));absence,_=schedule((HA,3),target,rates);transfer,_=schedule(H,(6,6),rates);result('case3-transfer',(absence[0]+(HA+3,),transfer[0]));changed,_=selection(options,11,hours,0);result('defense1',changed[0][1:4]+(hours-changed[0][2],));receipt2=(last[0]+2,)+last[1:4]+(last[4]+2,);result('defense2',(receipt2,max(Q(0),floor-receipt2[0])))
    selection_worlds=0
    for B,Hh,G in product((0,9,10,11,15),(0,7,8,12),(0,2)):
        winners,rr=selection(options,B,Hh,G);selection_worlds+=1
        for row in rr:
            bits,cost,staff,score,valid=row;full=sum(t*r[0]for t,r in zip(bits,options));eq(valid,full<=(B+min(G,options[0][0])if bits[0]else B)and staff<=Hh,'direct resource test')
            if valid:eq(score<=winners[0][3],True,'global finite bound')
    schedule_worlds=0
    for hA,hB,tx,ty in product((3,4),(0,3,4),(6,8),(6,9)):
        winners,rr=schedule((hA,hB),(tx,ty),rates);schedule_worlds+=1;z=winners[0][-1]
        # Explicit feasible-world values all respect the frontier optimum.
        for t,u in ((Q(0),Q(0)),(Q(hA,2),Q(hB,2)),(Q(hA),Q(hB)),(Q(hA),Q(0))):
            X=3*t+u;Y=hA-t+2*(hB-u);eq(min(X/tx,Y/ty)<=z,True,'feasible schedule witness')
        if winners[0][1]==0 and winners[0][0]<hA:eq(z,Q(3*hA+6*hB,tx+3*ty),'dual-bound attained')
    funding_worlds=0
    for receipt in (0,1,2,3,4,7):
        final=(last[0]+receipt,)+last[1:4]+(last[4]+receipt,);eq(sum(final[:3]),sum(final[3:]),'funding balances');eq(final[0]>=floor,receipt>=needed,'minimum actual equity');funding_worlds+=1
    invalid=0
    calls=[lambda:selection(options,-1,8,0),lambda:selection(options,10,-1,0),lambda:selection(options,10,8,-1),lambda:selection(options,10.,8,0),lambda:journal((18,0,82,85,14),events),lambda:journal(opening,((-8,7,0,0),)),lambda:journal(opening,((0,-1,0,-1),)),lambda:schedule((-1,4),target,rates),lambda:schedule(H,(0,6),rates),lambda:schedule(H,target,(0,1,1,2)),lambda:schedule(H,target,(True,1,1,2)),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}')]
    for call in calls:
        try:call()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    require(used==set(marks),'all numeric markers');return {'status':'passed','comparisons':count,'selection_worlds':selection_worlds,'schedule_worlds':schedule_worlds,'funding_worlds':funding_worlds,'invalid_domains':invalid,'worked_cases':3,'solutions':9}
if __name__=='__main__':
    if len(sys.argv)>2:raise ValueError('at most one root')
    check(sys.argv[1]if len(sys.argv)==2 else None)
