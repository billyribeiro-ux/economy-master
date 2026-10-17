"""C05 independent peer oracle: primitive future surplus and finite completions."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import ast
import json
import re

FILES=('production/v17-c05-working.html','production/check_v17_c05_working.py','production/v17-c05-sources-working.json','production/v17-c05-author-review-working.json','production/check_v17_c05_peer_working.py','production/v17-c05-peer-review-working.json')
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
    def bad(value):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def worth(cost,payoff,rate):
    require(cost>0 and payoff>=0 and rate>-1,'project domain')
    # Compare terminal payoff with the terminal value of the forgone initial cost.
    return (payoff-cost*(1+rate))/(1+rate)


def choices(projects,rate,funding=None):
    require(funding is None or funding>=0,'funding domain')
    values={'outside':F(0)}
    for name,(cost,payoff) in projects.items():
        v=worth(cost,payoff,rate)
        if funding is None or cost<=funding:values[name]=v
    best=max(values.values())
    return tuple(sorted(k for k,v in values.items() if v==best))


def completions(n,s,m):
    require(all(type(z) is int for z in (n,s,m)) and n>0 and 0<=s and 0<=m and s+m<=n,'finite binary counts')
    return tuple(F(s+sum(bits),n) for bits in product((0,1),repeat=m))


def contrasts(t,c):
    return tuple(sorted(set(a-b for a,b in product(completions(*t),completions(*c)))))


def audit(d):
    x={k:numeric(v) for k,v in d.inputs.items()};count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    expected={'projects':(40,55,100,132,F(1,10),80,F(2,5)),'score-a':(4,0,2,4,4),'missing':(4,2,1,4,1,1),'score-b':(4,0,0,0,2),'exercise-projects':(60,75,120,150,F(1,10),90)}
    eq(x,expected,'actual primitive groups')
    ca,xa,cb,xb,r,funding,high=x['projects'];projects={'A':(ca,xa),'B':(cb,xb)}
    base=(worth(ca,xa,r),worth(cb,xb,r));returns=(xa/ca-1,xb/cb-1)
    cross=(xb-xa)/(cb-ca)-1;crossvalue=worth(ca,xa,cross)
    counts=tuple(int(z) for z in x['missing']);t=counts[:3];c=counts[3:]
    complete=F(t[1],t[0]-t[2])-F(c[1],c[0]-c[2]);full=contrasts(t,c)
    u1=contrasts((t[0],t[1]+1,t[2]-1),c);v1=contrasts(t,(c[0],c[1]+1,c[2]-1))
    ea,ex,eb,ey,er,ef=x['exercise-projects'];ep={'A':(ea,ex),'B':(eb,ey)}
    want={'base-npv':base,'returns':returns,'high-rate-npv':(worth(ca,xa,high),worth(cb,xb,high)),'crossover':cross,'cross-value':crossvalue,'score-a':sum(x['score-a']),'complete-case':complete,'missing-set':full,'verified-set':u1,'score-b':sum(x['score-b']),'exercise-npv':(worth(ea,ex,er),worth(eb,ey,er)),'exercise-returns':(ex/ea-1,ey/eb-1),'comparison-verified':v1,'exercise-score':(3,4,4,4,4,19)}
    eq(set(d.results),set(want),'every result group accounted')
    for k,v in want.items():eq(numeric(d.results[k]),v,'visible '+k)
    actualprojects={row[0]:tuple(numeric(z) for z in row[1:]) for row in d.rows if len(row)==5 and row[0] in ('A','B')}
    eq(actualprojects,{'A':(ca,xa/(1+r),base[0],returns[0]),'B':(cb,xb/(1+r),base[1],returns[1])},'all actual project table cells')
    missingrows=[tuple(numeric(z) for z in row) for row in d.rows if len(row)==5 and row[0] in ('0','1')]
    oracle=[]
    for u,v in product((0,1),repeat=2):
        mt=F(t[1]+u,t[0]);mc=F(c[1]+v,c[0]);oracle.append((u,v,mt,mc,mt-mc))
    eq(missingrows,oracle,'all four actual binary completion rows')
    amax=tuple(numeric(row[2]) for row in d.rows if len(row)==3 and re.match('A[1-5]:',row[0]))
    bmax=tuple(numeric(row[2]) for row in d.rows if len(row)==3 and re.match('B[1-5]:',row[0]))
    eq(amax,(4,4,4,4,4),'actual A rubric weights');eq(bmax,(4,6,4,4,2),'actual B rubric weights')
    eq((sum(amax),sum(bmax)),(20,20),'two rubric totals')
    for scores,maxima in ((x['score-a'],amax),(x['score-b'],bmax),((3,4,4,4,4),amax)):
        require(all(0<=a<=b for a,b in zip(scores,maxima)),'scored criterion range');count+=1
    # Discrete target: complete case lies in the interval hull but not its finite set.
    eq(min(full)<=complete<=max(full),True,'hull membership');eq(complete in full,False,'unattainable full-roster complete-case contrast')
    eq((oracle[1][-1],oracle[2][-1]),(min(full),max(full)),'endpoint witnesses')
    eq(oracle[0][-1],F(1,4),'both missing assumed failures')
    eq(u1,tuple(sorted(set(row[-1] for row in oracle if row[0]==1))),'verified offered coordinate restriction')
    eq(v1,tuple(sorted(set(row[-1] for row in oracle if row[1]==1))),'verified comparison coordinate restriction')
    eq(min(v1)>0,False,'verification does not imply strict positivity')
    # Full feasible maximizer sets, including ties and the outside option.
    eq(choices(projects,r),('B',),'base choice');eq(choices(projects,r,funding),('A',),'funding choice');eq(choices(projects,high),('outside',),'high rate choice')
    eq(choices(projects,cross),('A','B'),'positive crossing tie');eq(worth(cb,xb,cross),crossvalue,'both crossing values')
    eq(choices(projects,F(3,8)),('A','outside'),'A zero-value boundary')
    eq(worth(cb,xb,F(8,25)),0,'B zero-value boundary')
    eq(choices(projects,F(8,25)),('A',),'positive A at B zero')
    eq(choices(projects,r,F(39)),('outside',),'funding below both costs')
    eq(choices(projects,r,ca),('A',),'funding at A threshold')
    eq(choices(projects,r,cb),('B',),'funding at B threshold')
    eq(choices(ep,er),('B',),'exercise unrestricted');eq(choices(ep,er,ef),('A',),'exercise funding')
    tied={'A':(ca,F(66)),'B':(cb,xb)}
    eq(tuple(worth(*tied[k],r) for k in ('A','B')),(20,20),'exercise5/7 alternate solved form')
    eq(choices(tied,r),('A','B'),'all maxima of alternate form')
    eq((F(50)-ca,base[1]),(10,20),'exercise5 arithmetic repair')
    eq(tuple(100*v for v in returns),(F(75,2),F(32)),'displayed return percentages')
    eq((ex/(1+er),ey/(1+er)),(F(750,11),F(1500,11)),'exercise displayed present values')
    eq((1+1+1+1,2+2,F(2,4)),(4,4,F(1,2)),'exercise2/6 rubrics and partial response')
    eq(F(2,3)-F(1,3),complete,'observed denominator derivation')
    # Global ranking expression and useful nondefault witnesses; proof read separately.
    for rate in (F(-1,2),F(0),cross-F(1,100),cross,cross+F(1,100),F(1)):
        gap=worth(cb,xb,rate)-worth(ca,xa,rate)
        eq(gap,(xb-xa)/(1+rate)-(cb-ca),'ranking identity witness')
        eq((gap>0,gap==0,gap<0),(rate<cross,rate==cross,rate>cross),'crossover direction')
    for original_t,original_c in (((2,1,0),(3,0,0)),((1,0,1),(2,0,2)),((3,1,2),(2,1,1)),((4,0,0),(1,1,0))):
        vals=contrasts(original_t,original_c);nt,st,mt=original_t;nc,sc,mc=original_c
        eq((min(vals),max(vals)),(F(st,nt)-F(sc+mc,nc),F(st+mt,nt)-F(sc,nc)),'general finite support extrema')
        eq(all(-1<=z<=1 for z in vals),True,'binary difference support')
    invalid=[lambda:worth(0,1,F(0)),lambda:worth(1,-1,F(0)),lambda:worth(1,1,F(-1)),lambda:choices(projects,r,F(-1)),lambda:completions(0,0,0),lambda:completions(4,3,2),lambda:completions(4,-1,0),lambda:completions(4,0,-1),lambda:completions(F(4),2,1)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};peer=strict_json(raw[FILES[5]]);author=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(peer['payloads'])==set(FILES[:5]) and set(author['payloads'])==set(FILES[:3]),'nonself binding memberships')
    for record in (author,peer):
        for f,v in record['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen payload '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(set(d.ids))==len(d.ids),'unique balanced fragment')
    ids={f'v17-c05-ex{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(peer['exact_prompt_review'])==ids,'eight exact pairs')
    require(d.worked==['v17-c05-case1','v17-c05-case2'],'two worked packets')
    for k,v in peer['exact_prompt_review'].items():
        require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'read pair changed')
    routes={'v17-c05-ncme-glossary':'https://ncme.org/resources/professional-learning/glossary/','v17-c05-cmu-assessments':'https://www.cmu.edu/teaching/designteach/syllabus/newcourse/assessments.html','v17-c05-cmu-rubrics':'https://www.cmu.edu/teaching/assessment/assesslearning/rubrics.html','v17-c05-cmu-exams':'https://www.cmu.edu/teaching/online/assessinglearning/remoteassessment/studentlearning/exams.html'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'four actual source routes')
    require(all(s['actual_inspector']=='v16_c01_author' for s in sources['sources']),'preserved source attribution')
    require({z for z in d.links if not z.startswith('https://')}=={'v17-c01.html','v17-c02.html','curriculum.html#v17-c04','curriculum.html#v17-c06'},'prerequisite/next chapter routes')
    comparisons,invalid,groups=audit(d)
    return {'chapter':'v17-c05','status':'passed','review':'independent internal peer','runtime_files':6,'worked_artifacts':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'source_routes':4,'author_checker':'opaque hash only; never read as text/imported/executed','scope':'Complete prompts, solutions, rubrics and qualitative score-use/security arguments read separately. No actual learner or psychometric validation claimed.'}


if __name__=='__main__':
    check()
