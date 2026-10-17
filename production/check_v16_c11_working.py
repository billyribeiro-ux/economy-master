"""Quiet, portable audit of C11's actual synthetic inputs and claim-boundary arithmetic."""
from pathlib import Path
from html.parser import HTMLParser
from fractions import Fraction as F
from hashlib import sha256
import ast,json,sys
ROOT=Path(__file__).resolve().parents[1]
FILES=['production/v16-c11-working.html','production/check_v16_c11_working.py','production/v16-c11-sources-working.json','production/v16-c11-author-review-working.json']

def need(ok,message):
    if not ok:raise ValueError('C11: '+message)

def number(text):
    def visit(n):
        if isinstance(n,ast.Expression):return visit(n.body)
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(visit(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('unsupported numeric syntax')
    return visit(ast.parse(text.strip().replace('−','-'),mode='eval'))

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.worked=[];self.exercises=[];self.answers=[];self.sources={};self.links=[];self.markers={};self.capture=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'duplicate attribute');need(tag!='h1','fragment h1')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a.get('id'))
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack):self.exercises.append(a.get('id'))
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'solution disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if a.get('href','').startswith('#'):self.links.append(a['href'][1:])
        for kind in ('input','result'):
            if 'data-'+kind in a:
                key=(kind,a['data-'+kind]);need(key not in self.markers,'duplicate number marker');need(self.capture is None,'nested marker');self.capture=key;self.markers[key]=''
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.capture:self.markers[self.capture]+=text
    def handle_endtag(self,tag):
        need(bool(self.stack) and self.stack[-1][0]==tag,'balanced HTML');_,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.capture=None

def contrasts(rows):
    need(isinstance(rows,tuple) and len(rows)==4,'four bank rows')
    need(all(isinstance(r,tuple) and len(r)==2 for r in rows),'two dates')
    need(all(type(v) in (int,F) and v>=0 for r in rows for v in r),'nonnegative exact stocks')
    e=tuple(sum(r[t] for r in rows[:2])/F(2) for t in (0,1));c=tuple(sum(r[t] for r in rows[2:])/F(2) for t in (0,1))
    need(e[0]>0,'positive exposed baseline for normalization')
    changes=tuple(y-x for x,y in rows);g=(e[1]-e[0],c[1]-c[0]);return e,c,changes,g,g[0]-g[1]

def compatible(e,c,bounds):
    need(isinstance(bounds,tuple) and len(bounds)==2,'two bound endpoints')
    need(all(type(v) in (int,F) for v in bounds),'exact bound endpoints')
    lo,hi=bounds;need(lo<=hi,'ordered bounds');base=e[0]+c[1]-c[0]
    need(base+lo>=0,'entire untreated range nonnegative')
    return (e[1]-base-hi,e[1]-base-lo),(base+lo,base+hi)

def check(root=None):
    root=Path(root) if root is not None else ROOT
    review=json.loads((root/FILES[3]).read_text());need(set(review['payloads'])==set(FILES[:3]),'exact nonself bindings')
    for name,record in review['payloads'].items():
        b=(root/name).read_bytes();need(record=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'frozen '+name)
    need(all(review['review'].values()) and not review['open_material_findings'],'full qualitative author review')
    p=Page();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and len(p.ids)==len(set(p.ids)),'complete unique fragment')
    ex=[f'v16-c11-e{i}' for i in range(1,9)];need(p.exercises==ex and p.answers==ex,'eight exact solution pairs')
    need(p.worked==['v16-c11-talk','v16-c11-dossier'],'two complete artifacts');need(set(p.links)<=set(p.ids),'local links')
    sources=json.loads((root/FILES[2]).read_text());need(p.sources=={s['id']:s['url'] for s in sources['sources']},'source mapping')
    values={k:number(v) for k,v in p.markers.items()};used=set();count=0
    def get(kind,key):used.add((kind,key));return values[kind,key]
    def eq(actual,expected,label):
        nonlocal count
        need(actual==expected,label);count+=1
    def output(key,expected):eq(get('result',key),expected,key)
    output('total_minutes',sum(get('input','minutes')))
    rows=tuple(tuple(get('input',bank+str(t)) for t in (0,1)) for bank in 'abcd')
    e,c,ch,g,d=contrasts(rows)
    for key,val in [('changes',ch),('exposed_means',e),('comparator_means',c),('group_changes',g),('contrast',d),('growth',g[0]/e[0]),('normalized',d/e[0])]:output(key,val)
    eq(d,F(-6),'independent raw-row contrast');eq(g[0]/e[0]-d/e[0],F(1,50),'two percentage point distinction')
    for name in ('world_a','world_b'):
        vals=get('input',name);m=sum(vals)/2;t=e[1]-m;b=m-e[0]-(c[1]-c[0]);output(name+'_effect_trend',(t,b));eq(t+b,d,name+' identity')
    for name in ('initial','defense','reassessment'):
        bounds=get('input',name+'_bounds');effects,means=compatible(e,c,bounds)
        output(name+'_effect_bounds',effects)
        output(name+('_means' if name=='reassessment' else '_untreated_means'),means)
        pairs=tuple((m-10,m+10) for m in means)
        output(name+('_pairs' if name=='reassessment' else '_endpoint_pairs'),pairs)
        # Endpoint and interior counterfactual constructions independently re-add
        # untreated changes and effects to recover the observed contrast.
        for i in range(5):
            b=bounds[0]+(bounds[1]-bounds[0])*F(i,4);m=e[0]+c[1]-c[0]+b;effect=e[1]-m
            eq(effect+b,d,name+' reconstructed contrast');need(effects[0]<=effect<=effects[1] and m>=0,'feasible interval witness')
        for pair,m in zip(pairs,means):eq(sum(pair)/2,m,name+' attainable mean');need(min(pair)>=0,'nonnegative endpoint stock')
    output('zero_effect_b',d);eq(compatible(e,c,(d,d))[0],(F(0),F(0)),'zero world attainable')
    need(used==set(values),'every actual input/result audited')
    # Alternative tables test the underlying arithmetic, not just the frozen answer.
    alternatives=[(((10,12),(30,34),(20,21),(20,23)),F(1)),(((10,10),(10,10),(10,10),(10,10)),F(0)),(((20,30),(40,50),(10,9),(30,29)),F(11))]
    for rows,want in alternatives:
        ae,ac,_,_,ad=contrasts(rows);eq(ad,want,'alternative contrast')
        for b in (-3,0,4):
            interval,means=compatible(ae,ac,(b,b));eq(interval,(ad-b,ad-b),'alternative point bound');eq(ae[1]-means[0]+b,ad,'alternative identity')
    bad=[lambda:contrasts(()),lambda:contrasts(((1,2),)*3),lambda:contrasts(((1,2,3),)*4),lambda:contrasts(((-1,2),)*4),lambda:contrasts(((0,2),)*4),lambda:contrasts(((True,2),)*4),lambda:compatible(e,c,(1,-1)),lambda:compatible(e,c,(-52,0)),lambda:compatible(e,c,(0,)),lambda:compatible(e,c,(0.,1))]
    rejected=0
    for f in bad:
        try:f()
        except ValueError:rejected+=1
        else:raise ValueError('C11: accepted invalid domain')
    return {'status':'passed','runtime_files':4,'worked_cases':2,'exercises_and_solutions':8,'numeric_markers':len(values),'comparisons':count,'alternative_tables':len(alternatives),'interval_witnesses':15,'invalid_domains':rejected,'qualitative_review':'Complete talk, response memo, all eight solutions and human-assessment limits separately read; arithmetic does not certify those judgments.'}

if __name__=='__main__':
    need(len(sys.argv)<=2,'at most one root argument');check(sys.argv[1] if len(sys.argv)==2 else None)
