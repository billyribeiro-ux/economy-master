"""C08 author oracle: full count/account tables and learning-evidence arithmetic."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product,combinations
import ast
import json
import re
FILES=('production/v17-c08-working.html','production/check_v17_c08_working.py','production/v17-c08-sources-working.json','production/v17-c08-author-review-working.json')
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


def screen(n,defaults,tp,fp):
    require(all(type(v) is int for v in (n,defaults,tp,fp)) and n>0 and 0<=defaults<=n and 0<=tp<=defaults and 0<=fp<=n-defaults,'complete integer screening counts')
    flags=tp+fp
    table=((tp,defaults-tp,defaults),(fp,n-defaults-fp,n-defaults),(flags,n-flags,n))
    return table,(F(tp,defaults) if defaults else None,F(tp,flags) if flags else None)


def posterior(a,b,f):
    require(all(0<=v<=1 for v in (a,b,f)),'conditional-rate domain')
    mass=a*b+f*(1-b);require(mass>0,'nonempty flagged reference')
    return a*b/mass


def growth(accounts):
    require(len(accounts)>0 and all(len(v)==2 and v[0]>=0 and v[1]>=-1 for v in accounts),'account domain')
    start=sum((v for v,r in accounts),F(0));require(start>0,'positive initial total')
    ends=tuple(v*(1+r) for v,r in accounts);end=sum(ends,F(0))
    return ends,start,end,(end-start)/start


def bounds(total,m,n,lo,hi):
    require(type(m) is int and type(n) is int and 0<=m<=n and n>0 and lo<=hi and m*lo<=total<=m*hi,'bounded score roster')
    return ((total+(n-m)*lo)/n,(total+(n-m)*hi)/n)


def assignment_mean(potential):
    require(len(potential)==8 and all(len(v)==2 for v in potential),'eight complete potential pairs')
    diffs=[]
    for treated in combinations(range(8),4):
        diffs.append(sum((F(potential[i][1]) for i in treated),F(0))/4-sum((F(potential[i][0]) for i in range(8) if i not in treated),F(0))/4)
    return sum(diffs,F(0))/len(diffs),diffs


def audit(d):
    x={k:numeric(v) for k,v in d.inputs.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    expected={'screen':(1000,50,40,95),'screen-fresh':(400,40,30,18),'screen-delayed':(200,20,16,18),'accounts':((100,F(1,5)),(900,0)),'accounts-fresh':((250,F(-1,5)),(750,F(1,5))),'accounts-delayed':((300,F(1,10)),(100,F(-1,10))),'retrieval-scores':(2,2,1,1),'restudy-scores':(2,1,1,0)}
    eq(x,expected,'all actual primitive input groups')
    table,rates=screen(*(int(z) for z in x['screen']));fresh,frates=screen(*(int(z) for z in x['screen-fresh']));delayed,drates=screen(*(int(z) for z in x['screen-delayed']))
    actualtable=tuple(tuple(numeric(v) for v in row[1:]) for row in d.rows if len(row)==4 and row[0] in ('Default','No default','Total'))
    eq(actualtable,table,'all original count table cells')
    ends,start,end,g=growth(x['accounts']);fends,fs,fe,fg=growth(x['accounts-fresh']);dends,ds,de,dg=growth(x['accounts-delayed'])
    record={row[0]:tuple(None if z=='—' else numeric(z) for z in row[1:]) for row in d.rows if len(row)==4 and row[0] in tuple('ABCDEF')}
    expected_record={'A':(0,2,2),'B':(1,2,1),'C':(0,2,None),'D':(1,2,0),'E':(0,1,2),'F':(0,2,None)}
    eq(record,expected_record,'actual six-learner register')
    initial=sum((v[0] for v in record.values()),F(0));assisted=sum((v[1] for v in record.values()),F(0));responders=[v for v in record.values() if v[2] is not None];observed=sum((v[2] for v in responders),F(0));initialmean=initial/len(record)
    low,high=bounds(observed,len(responders),len(record),F(0),F(2));updated=bounds(observed+1,5,6,F(0),F(2))
    pairedinitial=sum((v[0] for v in responders),F(0))/len(responders);pairedlater=observed/len(responders)
    retrieval=sum(x['retrieval-scores'])/4;restudy=sum(x['restudy-scores'])/4
    r_ends,r_start,r_end,r_growth=growth(((F(100),F(1,10)),(F(300),F(-1,10))))
    want={'conditionals':rates,'fresh-conditionals':frates,'transfer-posterior':posterior(F(4,5),F(1,5),F(1,10)),'delayed-conditionals':drates,'account-values':ends+(start,end,g),'fresh-account-values':fends+(fg,F(0)),'flow-transfer':((end+100-start)/start,(end+100-100-start)/start),'delayed-account-values':dends+(dg,),'record-means':(initialmean,assisted/6,pairedlater),'record-bounds':(low,high,low-initialmean,high-initialmean),'next-flow':(200*(1+F(1,10))+30,F(1,4),F(1,10)),'e2':(posterior(F(4,5),F(1,20),F(1,10)),posterior(F(4,5),F(1,2),F(1,10))),'e3-changed':screen(100,10,1,0)[1],'e4':(growth(((F(250),F(1,5)),(F(250),F(0))))[-1],growth(((F(200),F(1,5)),(F(800),F(0))))[-1]),'e5':updated+tuple(z-initialmean for z in updated)+((observed+1)/5,),'e6':(pairedinitial,pairedlater,pairedlater-pairedinitial),'e7':(retrieval,restudy,retrieval-restudy),'e8':screen(500,50,40,45)[1]+screen(400,80,64,32)[1],'retention':(r_ends[0]-100,r_ends[1]-300,r_end-r_start,r_start,r_growth)}
    eq(set(d.results),set(want),'all visible result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'visible '+k)
    eq(round(100*rates[1],2),F(2963,100),'29.63 displayed approximation')
    eq((F(50,1000),F(95,950)),(F(1,20),F(1,10)),'base and false-flag rates')
    eq(posterior(rates[0],F(1,20),F(1,10)),rates[1],'count versus probability derivation')
    eq(screen(1000,50,40,160)[1][1],F(1,5),'changed false flags diagnostic')
    eq(fresh,((30,10,40),(18,342,360),(48,352,400)),'full fresh count key')
    eq(delayed,((16,4,20),(18,162,180),(34,166,200)),'full delayed count key')
    eq(screen(1000,200,160,80)[1][1],F(2,3),'changed population full counts')
    eq(screen(100,10,0,0)[1],(0,None),'empty reference differs from zero rate')
    eq((sum((1,1,1,1)),1+1),(4,2),'diagnostic evidence maxima')
    eq(growth(((F(500),F(1,5)),(F(500),F(0))))[:3],((600,500),1000,1100),'equal balance boundary key')
    eq((F(100)*F(1,5),F(900)*0),(20,0),'diagnostic monetary gains')
    eq(sum((r for v,r in x['accounts-fresh']),F(0))/2,0,'opposing rates unweighted mean')
    eq((initial,assisted,observed,len(responders)),(2,11,5,4),'record totals and count')
    fullmeans=[(observed+a+b)/6 for a,b in product((0,1,2),repeat=2)]
    eq((min(fullmeans),max(fullmeans)),(low,high),'attainable missing endpoints')
    eq(tuple(sorted(set(fullmeans))),(F(5,6),F(1),F(7,6),F(4,3),F(3,2)),'integer attainable grid')
    eq(((observed+1)/6,(observed+1+2)/6),updated,'updated endpoint witnesses')
    eq((observed+1+1)/6,F(7,6),'unverified F1 assumption')
    # Mathematical alternatives: conditional reference sets, weights, score support.
    for a,b,f in ((F(1),F(1),F(0)),(F(0),F(1,2),F(1,5)),(F(1,2),F(0),F(1,4)),(F(1,2),F(1,3),F(1,2))):
        q=posterior(a,b,f);require(0<=q<=1,'posterior range');count+=1
        eq(q*(a*b+f*(1-b)),a*b,'conditional mass identity')
    eq(posterior(F(1,2),F(1,3),F(1,2)),F(1,3),'uninformative flag preserves prevalence')
    for accounts in (((F(1),F(-1)),(F(3),F(0))),((F(0),F(1)),(F(10),F(1,5))),((F(2),F(1,2)),(F(2),F(-1,2)))):
        e,s,total,v=growth(accounts)
        eq(v,sum((capital/s*r for capital,r in accounts),F(0)),'general weighted identity')
        eq(min(r for capital,r in accounts)<=v<=max(r for capital,r in accounts),True,'convex-weight bound')
    eq(bounds(F(5),4,4,F(0),F(2)),(F(5,4),F(5,4)),'no missing score collapse')
    eq(bounds(F(0),0,6,F(0),F(2)),(0,2),'all missing support')
    # Full fixed-size random assignment expectation, including a world consistent with supplied observed scores.
    schedule=((0,2),(1,2),(0,1),(1,1),(2,2),(1,1),(1,0),(0,0))
    for potential in (schedule,tuple((i%3,i%3) for i in range(8)),tuple((0,1) for i in range(8))):
        avg,diffs=assignment_mean(potential)
        true=sum((F(y1-y0) for y0,y1 in potential),F(0))/8
        eq(avg,true,'all70 assignment expectation')
        eq(len(diffs),70,'complete assignment worlds')
    eq(tuple(v[1] for v in schedule[:4]),x['retrieval-scores'],'compatible treated observations')
    eq(tuple(v[0] for v in schedule[4:]),x['restudy-scores'],'compatible restudy observations')
    eq(assignment_mean(schedule)[0],F(3,8),'compatible truth differs from realized half-point')
    invalid=[lambda:screen(0,0,0,0),lambda:screen(10,11,0,0),lambda:screen(10,2,3,0),lambda:screen(10,2,0,9),lambda:posterior(F(2),F(1,2),F(0)),lambda:posterior(F(0),F(1,2),F(0)),lambda:growth(()),lambda:growth(((F(0),F(0)),)),lambda:growth(((F(-1),F(0)),)),lambda:growth(((F(1),F(-2)),)),lambda:bounds(F(5),7,6,F(0),F(2)),lambda:bounds(F(9),4,6,F(0),F(2))]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for f,v in review['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed payload '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v17-c08-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(review['exact_prompt_review'])==ids and d.worked==['v17-c08-case1','v17-c08-case2'],'eight exact pairs/two worked packets')
    for k,v in review['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed pair changed')
    routes={'v17-c08-cmu-diagnostic':'https://www.cmu.edu/teaching/assessment/priorknowledge/performancebased.html','v17-c08-ies-retrieval':'https://ies.ed.gov/ncee/wwc/PracticeGuide/1'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'two scoped source routes')
    require({a for a in d.links if not a.startswith('https://')}=={'v17-c07.html','v17-c06.html','v17-c09.html'},'chapter routes')
    comparisons,invalid,groups=audit(d)
    return {'chapter':'v17-c08','status':'passed','runtime_files':4,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'assignment_worlds_per_witness':70,'source_routes':2,'scope':'Full diagnostic responses, rival explanations, protocols, exact solutions and evidence claims separately read; no actual learner outcomes or causal instructional results claimed.'}


if __name__=='__main__':
    check()
