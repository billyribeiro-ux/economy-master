"""Independent counterfactual-state audit for C11; never imports author checker."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast,json,sys

ROOT=Path(__file__).resolve().parents[1]
FILES=['content/chapters/v16-c11.html','scripts/check_v16_c11.py','content/reviews/v16-c11-sources.json','content/reviews/v16-c11-author.json','scripts/check_v16_c11_peer.py','content/reviews/v16-c11-peer.json']
def need(ok,why):
    if not ok:raise ValueError('C11 independent peer: '+why)
def value(s):
    def parse(n):
        if isinstance(n,ast.Expression):return parse(n.body)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(parse(v) for v in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -parse(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return parse(n.left)/parse(n.right)
        raise ValueError('nonliteral numeric content')
    return parse(ast.parse(s.replace('−','-'),mode='eval'))

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.solutions=[];self.cases=[];self.sources={};self.groups={};self.capture=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','HTML fragment')
        if 'id' in a:self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a.get('id'))
        if t=='li' and any(tag=='ol' and 'exercises' in at.get('class','').split() for tag,at in self.stack):self.tasks.append(a.get('id'))
        if 'data-solution-for' in a:
            need(any(tag=='details' and 'solutions' in at.get('class','').split() for tag,at in self.stack),'full solution disclosure');self.solutions.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for k in ('input','result'):
            if 'data-'+k in a:
                self.capture=(k,a['data-'+k]);need(self.capture not in self.groups,'unique numeric group');self.groups[self.capture]=''
        if t not in ('br','hr','meta','link','img','input'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.capture:self.groups[self.capture]+=s
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack[-1][0]==t,'balanced HTML');_,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.capture=None

def rows(v):
    need(len(v)==8 and all(type(x) in (int,F) and x>=0 for x in v),'eight nonnegative exact stocks')
    v=tuple(map(F,v));return tuple(zip(v[::2],v[1::2]))
def summaries(v):
    r=rows(v);changes=tuple(b-a for a,b in r);pre=(sum(a for a,b in r[:2])/2,sum(a for a,b in r[2:])/2);post=(sum(b for a,b in r[:2])/2,sum(b for a,b in r[2:])/2)
    need(pre[0]>0,'positive exposed denominator');diff=(sum(changes[:2])/2,sum(changes[2:])/2);D=diff[0]-diff[1]
    return changes,pre,post,diff,D,diff[0]/pre[0],D/pre[0]
def world(v,untreated):
    need(len(untreated)==2 and all(type(x) in (int,F) and x>=0 for x in untreated),'two nonnegative untreated stocks')
    changes,pre,post,diff,D,_,_=summaries(v);m=sum(map(F,untreated))/2
    # Reconstruct a complete exposed counterfactual state before forming effects.
    treated=rows(v)[:2];effects=tuple(b-u for (a,b),u in zip(treated,untreated));tau=sum(effects)/2;bias=(m-pre[0])-diff[1]
    need(tau+bias==D,'potential-outcome accounting');return tau,bias,m
def support(v,interval):
    need(len(interval)==2 and all(type(x) in (int,F) for x in interval),'exact bound pair');low,high=map(F,interval);need(low<=high,'ordered bounds')
    _,pre,post,diff,D,_,_=summaries(v);means=(pre[0]+diff[1]+low,pre[0]+diff[1]+high);need(min(means)>=0,'counterfactual nonnegative means')
    effects=tuple(world(v,(m,m))[0] for m in means)
    return min(effects),max(effects),means

def check(root=None):
    root=Path(root) if root is not None else ROOT;r=json.loads((root/FILES[-1]).read_text());need(all(r['review'].values()) and not r['open_material_findings'],'full peer judgment')
    need(set(r['payloads'])==set(FILES[:-1]),'five frozen nonself payloads')
    for p,h in r['payloads'].items():
        data=(root/p).read_bytes();need(h=={'bytes':len(data),'sha256':sha256(data).hexdigest()},'hash '+p)
    p=Page();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and len(p.ids)==len(set(p.ids)),'complete unique HTML')
    need(p.tasks==p.solutions==[f'v16-c11-e{i}' for i in range(1,9)],'eight exact prompts/solutions');need(p.cases==['v16-c11-talk','v16-c11-dossier'],'two worked artifacts')
    sources=json.loads((root/FILES[2]).read_text());need(p.sources=={s['id']:s['url'] for s in sources['sources']},'source route equality')
    vals={k:value(v) for k,v in p.groups.items()};comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        if isinstance(b,(list,tuple)):
            need(len(a)==len(b),label+' dimensions')
            for x,y in zip(a,b):eq(x,y,label)
        else:need(a==b,label);comparisons+=1
    def shown(name,expected):eq(vals['result',name],expected,name)
    v=tuple(vals['input',k] for k in ('a0','a1','b0','b1','c0','c1','d0','d1'));eq(v,(40,36,60,54,50,50,50,52),'actual raw table')
    changes,pre,post,diff,D,growth,normalized=summaries(v)
    shown('changes',changes);shown('exposed_means',(pre[0],post[0]));shown('comparator_means',(pre[1],post[1]));shown('group_changes',diff);shown('contrast',D);shown('growth',growth);shown('normalized',normalized)
    shown('world_a_effect_trend',world(v,vals['input','world_a'])[:2]);shown('world_b_effect_trend',world(v,vals['input','world_b'])[:2]);eq(vals['input','world_a'],(41,61),'worldA');eq(vals['input','world_b'],(36,54),'worldB')
    for label,inp in [('initial','initial_bounds'),('defense','defense_bounds'),('reassessment','reassessment_bounds')]:
        lo,hi,means=support(v,vals['input',inp]);shown(label+'_effect_bounds',(lo,hi));shown(label+('_untreated_means' if label!='reassessment' else '_means'),means)
        # Printed witnesses preserve baseline deviations; independent equal-mean witnesses prove the same mean bounds.
        offsets=tuple(a-pre[0] for a,b in rows(v)[:2]);pairs=tuple(tuple(m+offset for offset in offsets) for m in means);shown(label+('_endpoint_pairs' if label!='reassessment' else '_pairs'),pairs)
        for pair,m,bias in zip(pairs,means,vals['input',inp]):
            tau,b,actualm=world(v,pair);eq((actualm,b),(m,bias),'printed feasible witness');need(lo<=tau<=hi,'endpoint inclusion')
        for j in range(11):
            m=means[0]+(means[1]-means[0])*F(j,10);tau,bias,mean=world(v,(m,m));need(lo<=tau<=hi,'interior realization');eq(tau+bias,D,'interior identity')
    shown('zero_effect_b',world(v,tuple(b for a,b in rows(v)[:2]))[1]);eq(vals['input','minutes'],(2,2,3,2,1),'planned minutes');shown('total_minutes',sum(vals['input','minutes']))
    eq(growth-normalized,F(1,50),'percentage point distinction')
    need(len(vals)==34,'full numerical inventory')
    # Alternative observed worlds preserve the decomposition without fixing the printed -6 result.
    worlds=[(2,3,4,7,5,6,5,4),(4,0,8,0,2,1,6,2),(10,12,20,24,4,4,6,6)]
    for data in worlds:
        dd=summaries(data)[4]
        for counter in [(0,0),(1,8),(10,20)]:
            tau,bias,m=world(data,counter);eq(tau+bias,dd,'alternative identity')
    rejected=0
    bad=[lambda:summaries((-1,36,60,54,50,50,50,52)),lambda:summaries((True,36,60,54,50,50,50,52)),lambda:summaries((40.,36,60,54,50,50,50,52)),lambda:summaries(v[:-1]),lambda:summaries((0,0,0,0,50,50,50,52)),lambda:world(v,(-1,3)),lambda:world(v,(1,)),lambda:support(v,(1,-2)),lambda:support(v,(-100,-90)),lambda:support(v,(False,1))]
    for fn in bad:
        try:fn()
        except ValueError:rejected+=1
        else:raise ValueError('invalid counterfactual accepted')
    return {'chapter':'v16-c11','status':'passed','runtime_files':6,'worked_artifacts':2,'full_solutions':8,'numeric_groups':len(vals),'exact_comparisons':comparisons,'interior_counterfactual_witnesses':33,'alternative_observed_worlds':len(worlds),'domain_rejections':rejected,'qualitative_review':'Complete script, seven answers, revised title/abstract/method/conclusion, three-comment memo, changed-assumption defense and full prompt/solution audit independently read; no observed human performance claimed.'}

if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
