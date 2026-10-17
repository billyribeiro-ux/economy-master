"""C11 exact author oracle: actual acceptance/cost rows and sector wealth reconciliation."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('content/chapters/v18-c11.html','scripts/check_v18_c11.py','content/reviews/v18-c11-sources.json','content/reviews/v18-c11-author.json')
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




def project(budgets,scheduled,accepted,costs):
    require(len(budgets)>0 and len(budgets)==len(scheduled)==len(accepted)==len(costs),'aligned nonempty task vectors')
    require(all(F(x)>=0 for x in (*budgets,*costs)) and sum(budgets)>0,'nonnegative costs and positive baseline')
    require(all(type(x) is int and x in (0,1) for x in (*scheduled,*accepted)),'binary task status')
    bac=sum(map(F,budgets));pv=sum(F(b)*z for b,z in zip(budgets,scheduled));ev=sum(F(b)*a for b,a in zip(budgets,accepted));ac=sum(map(F,costs))
    return bac,pv,ev,ac,ev-ac,ev-pv,ev/ac if ac else None,ev/pv if pv else None


def attribution(p,b,r,s,W=100,fee=2):
    require(len(p)>0 and len(p)==len(b)==len(r)==len(s),'aligned portfolio vectors')
    require(sum(p)==sum(b)==1 and min((*p,*b))>=0,'fully invested long-only weights')
    require(min((*r,*s))>=-1 and W>0 and fee>=0,'valid total returns/wealth/fee')
    p,b,r,s=tuple(map(F,p)),tuple(map(F,b)),tuple(map(F,r)),tuple(map(F,s));W,fee=F(W),F(fee)
    rp=sum(x*y for x,y in zip(p,r));rb=sum(x*y for x,y in zip(b,s))
    a=sum((x-y)*z for x,y,z in zip(p,b,s));sel=sum(y*(z-u) for y,z,u in zip(b,r,s));inter=sum((x-y)*(z-u) for x,y,z,u in zip(p,b,r,s))
    gross=W*(1+rp);require(fee<=gross,'fee payable from final account')
    return gross,gross-fee,rp,rp-fee/W,rb,rp-fee/W-rb,a,sel,inter


def contrast_bounds(observed,lo,hi):
    require(lo<=hi,'ordered counterfactual bounds')
    return F(observed)-F(hi),F(observed)-F(lo)


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    def yes(ok,label):
        nonlocal count
        require(ok,label);count+=1
    taskrows=[r for r in d.rows if len(r)==7 and r[0] in ('A','B','C','D','E','F')]
    task={r[0]:tuple(numeric(v) for v in r[1:6]) for r in taskrows}
    eq(task,{'A':(2,4,1,1,3),'B':(3,6,1,1,7),'C':(2,4,1,0,5),'D':(1,2,1,1,3),'E':(4,8,0,0,0),'F':(4,8,0,0,0)},'actual complete task rows')
    weights,budgets,scheduled,accepted,costs=zip(*task.values());scheduled=tuple(map(int,scheduled));accepted=tuple(map(int,accepted))
    eq(budgets,tuple(2*x for x in weights),'original weight budget relation')
    inp={k:numeric(v) for k,v in d.inputs.items()}
    eq(inp,{'project-final':((3,7,9,3,7,7),20,22),'portfolio-cash':(100,2)},'visible primitive inputs')
    finalcosts,deadline,actualday=inp['project-final'];W,fee=inp['portfolio-cash'];mid=project(budgets,scheduled,accepted,costs);final=project(budgets,(1,)*6,(1,)*6,finalcosts)
    false=project(budgets,scheduled,(1,1,1,1,0,0),costs)
    sectors={r[0]:tuple(numeric(v) for v in r[1:]) for r in d.rows if len(r)==5 and r[0] in ('C','D')}
    eq(sectors,{'C':(F(3,5),F(2,5),F(1,10),F(1,20)),'D':(F(2,5),F(3,5),F(3,20),F(1,5))},'actual sector weights and returns')
    p,b,r,s=zip(*sectors.values());got=attribution(p,b,r,s,W,fee);post=attribution(p,p,r,s,W,fee)
    changed=attribution(p,b,(F(1,10),F(1,4)),s,W,1)
    want={'checkpoint':mid,'forecast':(mid[0]/mid[6],4+8+8,mid[3]+4+8+8,36,mid[3]+4+8+8-36),'project-final':(final[2],final[3],final[3]-final[0],(final[3]-final[0])/final[0],final[6],final[7],actualday-deadline),'wealth':got[:6],'attribution':(*got[6:],got[2]-got[4],fee/W,got[5]),'causal-bounds':contrast_bounds(10,8,14),'e1':(mid[4:6],mid[6:8],mid[2]/mid[0],F(sum(accepted),len(accepted))),'e2':(false[2],false[4],false[5],false[6],false[7],false[2]/false[0],false[2]-mid[2],(false[2]-mid[2])/mid[0]),'e3':((mid[0]-mid[2])/mid[6],mid[0]/mid[6],38,36,18+4+8+7,18+4+8+7-36,36-18-4),'e5':(got[7]+got[8],sum(got[6:])+got[8],got[8]),'e6':(post[4],post[5],post[5]-got[5]),'e7':(contrast_bounds(10,8,14),contrast_bounds(10,9,11)),'retention':(sum(finalcosts)+1,sum(finalcosts)+1-36,F(32,sum(finalcosts)+1),changed[2],changed[3],*changed[6:],changed[5])}
    eq(set(want),set(d.results),'all displayed result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'displayed '+k)
    eq(tuple(finalcosts[i]-costs[i] for i in range(6)),(0,0,4,0,7,7),'actual additional approved work ledger')
    eq(sum(finalcosts)-sum(costs),18,'approved remaining actuals')
    eq((F(12,32),F(16,32)),(F(3,8),F(1,2)),'weighted completion versus scheduled share')
    completion_worlds=0
    for mask in range(64):
        a=tuple((mask>>i)&1 for i in range(6));res=project(budgets,scheduled,a,costs);completion_worlds+=1
        eq(res[2],2*sum(w for i,w in enumerate(weights) if mask>>i&1),'accepted weight oracle')
        eq(res[4]+res[3],res[2],'cost variance reconciliation')
        eq(res[5]+res[1],res[2],'schedule variance reconciliation')
    zero=project(budgets,(0,)*6,(0,)*6,(0,)*6)
    eq(zero,(32,0,0,0,0,0,None,None),'zero-denominator ratios undefined')
    eq(project(budgets,(0,)*6,(1,0,0,0,0,0),(1,0,0,0,0,0))[7],None,'early accepted work does not create planned denominator')
    for remaining in (0,13,14,15,20):eq(18+4+remaining<=36,remaining<=14,'global remaining-cost threshold')
    eq((W*p[0]*(1+r[0]),W*p[1]*(1+r[1])),(66,46),'direct sector gross wealth')
    portfolio_worlds=0
    for x in (F(0),F(2,5),F(3,5),F(1)):
        for y in (F(0),F(2,5),F(1)):
            for rc,rd in ((F(-1),F(0)),(F(-1,10),F(1,5)),(F(1,10),F(3,20)),(F(1,10),F(1,4))):
                pp=(x,1-x);bb=(y,1-y);rr=(rc,rd);v=attribution(pp,bb,rr,s,100,0);portfolio_worlds+=1
                eq(v[2]-v[4],sum(v[6:]),'general exact attribution identity')
                eq(v[7]+v[8],sum(pp[i]*(rr[i]-s[i]) for i in (0,1)),'combined selection identity')
                eq(v[6],sum((pp[i]-bb[i])*(s[i]-v[4]) for i in (0,1)),'centered allocation same total')
                eq(v[0],sum(100*pp[i]*(1+rr[i]) for i in (0,1)),'gross sector wealth consistency')
    for f in (0,1,2,10,112):
        v=attribution(p,b,r,s,100,f)
        eq(v[5],F(-1,50)-F(f,100),'global fee relation')
        yes(v[5]<0,'no feasible nonnegative fee yields original benchmark outperformance')
    bound_worlds=0
    for lo,hi in ((8,14),(9,11),(9,10),(8,9)):
        lower,upper=contrast_bounds(10,lo,hi)
        for j in range(5):
            y=F(lo)+F(j,4)*(hi-lo);theta=10-y;bound_worlds+=1
            yes(lower<=theta<=upper,'compatible counterfactual point')
            eq(theta,upper-F(j,4)*(upper-lower),'all intermediate contrasts attainable')
        eq(lower>0,hi<10,'strict positive boundary')
    eq(contrast_bounds(10,10,10),(0,0),'singleton null effect')
    invalid=[lambda:project((),(),(),()),lambda:project((1,),(1,),(1,),()),lambda:project((-1,),(1,),(1,),(1,)),lambda:project((1,),(1,),(2,),(1,)),lambda:project((1,),(1,),(1,),(-1,)),lambda:attribution((F(1,2),),b,r,s),lambda:attribution((1,1),b,r,s),lambda:attribution((-1,2),b,r,s),lambda:attribution(p,b,(-2,0),s),lambda:attribution(p,b,r,s,0),lambda:attribution(p,b,r,s,100,-1),lambda:attribution(p,b,r,s,100,113),lambda:contrast_bounds(10,11,9)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want),completion_worlds,portfolio_worlds,bound_worlds


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself hashes')
    for f,v in review['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v18-c11-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(review['exact_prompt_review'])==ids,'eight exact exercise/answer pairs')
    require(d.worked==['v18-c11-case1','v18-c11-case2'],'two complete executed-fiction evaluation cases')
    for k,v in review['exact_prompt_review'].items():require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed pair changed')
    urls={'v18-c11-doe-evm':'https://www.energy.gov/em/earned-value-management','v18-c11-cfa-evaluation':'https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/portfolio-performance-evaluation'}
    require(d.sources==urls=={s['id']:s['url'] for s in sources['sources']},'actual exact source routes')
    require(all(s['actual_inspector']=='v15_support_review' and s['checked']=='2026-10-17' for s in sources['sources']),'actual inspector/date')
    require({a for a in d.links if not a.startswith('https://')}=={'curriculum.html#v18-c10','v18-c04.html','v09-c01.html','v12-c06.html','curriculum.html#v18-c12'},'prerequisite and continuation routes')
    comparisons,invalid,groups,completions,portfolios,bounds=audit(d)
    return {'chapter':'v18-c11','status':'passed','runtime_files':4,'worked_cases':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'completion_worlds':completions,'portfolio_worlds':portfolios,'counterfactual_worlds':bounds,'source_routes':2,'scope':'Complete fictional dated execution, cost/acceptance/return records, external-to-owner feedback and bounded retrospective evaluations; actual learner responsibility and human assessment remain unobserved.'}


if __name__=='__main__':
    check()
