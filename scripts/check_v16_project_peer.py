"""Independent V16 project review. Author checker is an opaque bound payload only."""
from pathlib import Path
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
import contextlib, copy, hashlib, io, json, sys

AUTHOR = ['content/assessments/parts/v16-project.html'] + ['content/projects/v16-assessment-'+s for s in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')] + ['scripts/check_v16_project.py','content/reviews/v16-project-author.json','content/reviews/v16-project-sources.json']
SELF = 'scripts/check_v16_project_peer.py'
REVIEW = 'content/reviews/v16-project-peer.json'
RUNTIME = AUTHOR + [SELF, REVIEW]
COMPONENTS = ('own','other','total')

def demand(ok, message):
    if not ok: raise ValueError(message)

def pack(x):
    if isinstance(x,Q): return x.numerator if x.denominator==1 else str(x)
    if isinstance(x,dict): return {k:pack(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)): return [pack(v) for v in x]
    return x

def digest(path):
    b=path.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def oracle(d):
    """Reconstruct cells; enumerate offer vectors; solve by derivative boundary signs."""
    cells={}
    for r in d['ledger']:
        cells.setdefault((r['cohort'],r['date'],r['component']),{})[r['revision']]=Q(r['value_thousands'],1000)
    snapshots={}; changes=[]
    pairs=sorted({b['pair'] for b in d['banks']})
    for version in (0,1):
        rows=[]
        for b in d['banks']:
            row={k:b[k] for k in ('bank','pair','offer','cohort')}
            for c in ('own','other'):
                for t,label in ((0,'before'),(1,'after')):
                    history=cells[(b['cohort'],t,c)]
                    row[c+'_'+label]=history[1] if version==1 and 1 in history else history[0]
                    if version==1 and 1 in history:
                        changes.append({'cohort':b['cohort'],'date':t,'component':c,'old':history[0],'new':history[1],'change':history[1]-history[0]})
            for label in ('before','after'): row['total_'+label]=sum(row[c+'_'+label] for c in ('own','other'))
            for c in COMPONENTS: row[c+'_change']=row[c+'_after']-row[c+'_before']
            rows.append(row)
        groups=[[r for r in rows if r['pair']==p] for p in pairs]
        contrasts=[{'pair':p,**{c:sum((2*r['offer']-1)*r[c+'_change'] for r in g) for c in COMPONENTS}} for p,g in zip(pairs,groups)]
        estimates={c:sum(r[c] for r in contrasts)/len(groups) for c in COMPONENTS}
        # Bit zero chooses the currently non-offered unit, bit one the offered unit.
        reference=[]
        for bits in product((0,1),repeat=len(groups)):
            assignments=[]
            for bit,g in zip(bits,groups):
                assignments.extend((r, int(r['offer']==bit)) for r in g)
            reference.append(sum((2*z-1)*r['total_change'] for r,z in assignments)/len(groups))
        tail=sum(abs(v)>=abs(estimates['total']) for v in reference)
        snapshots[str(version)]={'analysis':rows,'paired_contrasts':contrasts,'estimate':estimates,'sharp_null':{'reference':reference,'tail':tail,'assignments':len(reference),'p':Q(tail,len(reference))}}
    def solve(a,r,h,k):
        if a-r<=0:return Q(0)
        if a-r-h*k>=0:return k
        return (a-r)/h
    model=d['model']; a=Q(model['a']);r0=Q(model['baseline_cost']);transport=Q(d['sensitivity']['transport_displacement']);policies=[]
    for p in model['policies']:
        s=Q(p['subsidy']);budget=Q(p['budget']);details=[];transportstocks=[]
        for t in model['types']:
            h,k,lam,other=map(Q,(t['curvature'],t['capacity'],t['displacement'],t['other_baseline']))
            x0=solve(a,r0,h,k);x1=solve(a,r0-s,h,k);dx=x1-x0
            details.append({'pair':t['pair'],'baseline':x0,'offer':x1,'bank_increment':dx,'other_increment':-lam*dx,'borrower_increment':dx-lam*dx,'other_after':other-lam*dx,'transport_borrower_increment':dx-transport*dx,'marginal_at_offer':a-r0+s-h*x1,'capacity':k})
            transportstocks.append(other-transport*dx)
        spend=sum(s*t['offer'] for t in details);diagnostics=[]
        if spend>budget:diagnostics.append('subsidy_spending_exceeds_budget')
        if min(t['other_after'] for t in details)<0:diagnostics.append('negative_other_lender_stock')
        if min(transportstocks)<0:diagnostics.append('negative_transport_other_stock')
        policies.append({'name':p['name'],'subsidy':s,'budget':budget,'spending':spend,'feasible':len(diagnostics)==0,'diagnostics':diagnostics,'mean_bank_increment':sum(t['bank_increment'] for t in details)/3,'mean_borrower_increment':sum(t['borrower_increment'] for t in details)/3,'mean_transport_increment':sum(t['transport_borrower_increment'] for t in details)/3,'types':details})
    lo,hi=map(Q,d['sensitivity']['unrecorded_contrast_bounds']);estimate=snapshots['1']['estimate']['total']
    return pack({'schema':'v16-research-results-1','status':'synthetic_rehearsal_only','raw_records':len(d['ledger']),'analysis_rows_per_snapshot':len(d['banks']),'snapshots':snapshots,'restatements':changes,'correction_delta':{c:snapshots['1']['estimate'][c]-snapshots['0']['estimate'][c] for c in COMPONENTS},'measurement_sensitivity':{'unrecorded_contrast_bounds':[lo,hi],'compatible_observed_contrast':[estimate+lo,estimate+hi],'scope':'measurement scenario, not causal confidence interval'},'policies':policies,'limits':['Sharp-null p values concern the stipulated paired lottery and no interference, not a weak-average-effect null.','Structural parameters and displacement are assumed, not identified by fitting three contrasts.','Budget feasibility is not welfare approval; synthetic corrections are not a real-paper replication.']})

class Markup(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.solutions=[];self.domains={};self.sources=[];self.results={};self.active=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'data-solution-for' in a:self.solutions.append(a['data-solution-for'])
        if 'data-rubric-domain' in a:self.domains[a['data-rubric-domain']]=int(a['data-points'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        if 'data-result' in a:self.active=a['data-result'];self.results[self.active]=''
    def handle_endtag(self,tag):
        if tag=='span':self.active=None
    def handle_data(self,s):
        if self.active:self.results[self.active]+=s

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    before={p:digest(root/p) for p in RUNTIME}
    review=json.loads((root/REVIEW).read_text());demand(set(review['payloads'])==set(RUNTIME)-{REVIEW},'ten nonself bindings')
    for p,b in review['payloads'].items():demand(before[p]==b,'peer binding '+p)
    author=json.loads((root/AUTHOR[-2]).read_text())
    for p,b in author['payloads'].items():demand(digest(root/p)==b,'author binding '+p)
    source=json.loads((root/AUTHOR[-1]).read_text());h=Markup();h.feed((root/AUTHOR[0]).read_text())
    demand(len(h.ids)==len(set(h.ids)),'duplicate HTML id')
    demand(set(h.solutions)=={'project-task'+str(i) for i in range(1,8)},'seven full answers')
    demand(h.domains=={k:20 for k in ('question_literature_judgment','reproduction_data_ethics','model_identification_design','robustness_writing','defense_portfolio')},'domain coverage')
    demand(set(h.sources)=={(s['id'],s['url']) for s in source['sources']},'scoped source links')
    manifest=json.loads((root/'content/projects/v16-assessment-manifest.json').read_text())
    demand(len(manifest['payloads'])==4,'four manifest payloads')
    for p,b in manifest['payloads'].items():demand(digest(root/'content/projects'/p)==b,'reader binding '+p)
    d=json.loads((root/'content/projects/v16-assessment-inputs.json').read_text());expected=oracle(d)
    count=0
    def same(x,y,path='result'):
        nonlocal count
        demand(type(x)==type(y),'type '+path)
        if isinstance(x,dict):
            demand(set(x)==set(y),'keys '+path)
            for k in x:same(x[k],y[k],path+'.'+k)
        elif isinstance(x,list):
            demand(len(x)==len(y),'length '+path)
            for i,(a,b) in enumerate(zip(x,y)):same(a,b,path+'.'+str(i))
        else:demand(x==y,'value '+path);count+=1
    same(expected,json.loads((root/'content/projects/v16-assessment-output.json').read_text()))
    # Only the distributed reader is executed; the author checker remains opaque.
    namespace={'__name__':'v16_project_peer_reader','__file__':str(root/'content/projects/v16-assessment-analysis.py')}
    quiet=io.StringIO()
    with contextlib.redirect_stdout(quiet),contextlib.redirect_stderr(quiet):
        exec(compile((root/'content/projects/v16-assessment-analysis.py').read_text(),namespace['__file__'],'exec'),namespace)
        cases=[d]
        x=copy.deepcopy(d);x['ledger'].reverse();x['banks'].reverse();x['banks'][0]['offer']=1;x['banks'][1]['offer']=0;cases.append(x)
        x=copy.deepcopy(d);x['model']['a']='12';x['model']['types'][0]['capacity']='0';x['model']['policies'][2]['budget']='0';cases.append(x)
        x=copy.deepcopy(d);x['model']['types'][1]['displacement']='2';x['model']['types'][1]['other_baseline']='1';x['sensitivity']['transport_displacement']='3';cases.append(x)
        for x in cases:
            original=copy.deepcopy(x);actual=namespace['run'](x);same(oracle(x),actual);demand(x==original,'mutated input');json.dumps(actual,allow_nan=False)
        # Twelve substantive input-contract failures, not altered expected outputs.
        invalid=[]
        def bad(fn):
            x=copy.deepcopy(d);fn(x);invalid.append(x)
        bad(lambda x:x['ledger'].append(copy.deepcopy(x['ledger'][0])))
        bad(lambda x:x['ledger'].pop(0))
        bad(lambda x:x['ledger'][0].update(cohort='unmatched'))
        bad(lambda x:x['ledger'][0].update(value_thousands=None))
        bad(lambda x:x['ledger'][0].update(value_thousands=-1))
        bad(lambda x:x['banks'][0].update(offer=True))
        bad(lambda x:x['banks'][0].update(offer=0))
        bad(lambda x:x['banks'][0].update(borrowers=101))
        bad(lambda x:x['model']['types'][0].update(curvature='0'))
        bad(lambda x:x['model']['policies'][0].update(subsidy='11'))
        bad(lambda x:x['sensitivity'].update(unrecorded_contrast_bounds=['1','-3']))
        bad(lambda x:x['model'].update(a=float('nan')))
        for x in invalid:
            original=copy.deepcopy(x)
            try:namespace['run'](x)
            except ValueError:pass
            else:raise ValueError('invalid input accepted')
            demand(repr(x)==repr(original),'invalid input mutated')
    demand(quiet.getvalue()=='','noisy reader API')
    markers={'project-records':[25,24,6],'project-own-pairs':[8,12,16],'project-other-v0':[6,-10,-14],'project-other-v1':[-6,-10,-14],'project-total-v0':[14,2,2],'project-total-v1':[2,2,2],'project-means-v0':[12,-6,6],'project-means-v1':[12,-10,2],'project-correction':[0,-4,-4],'project-reference-v0':[-6,Q(-14,3),Q(-14,3),Q(-10,3),Q(10,3),Q(14,3),Q(14,3),6],'project-reference-v1':[-2,Q(-2,3),Q(-2,3),Q(2,3),Q(-2,3),Q(2,3),Q(2,3),2],'project-randomization':[2,8,Q(1,4)],'project-measurement-range':[-1,3],'project-transport':[-3]}
    demand(set(markers)==set(h.results),'all marked results')
    for k,values in markers.items():
        parsed=[Q(v) for v in h.results[k].strip('()').split(',')];same(list(map(Q,values)),parsed,k)
    # Exact size with ties for every attainable alpha; both compatible PO schedules.
    for snapshot in expected['snapshots'].values():
        vals=list(map(Q,snapshot['sharp_null']['reference']))
        p=[Q(sum(abs(w)>=abs(v) for w in vals),8) for v in vals]
        for alpha in [Q(i,8) for i in range(9)]:demand(Q(sum(v<=alpha for v in p),8)<=alpha,'exact test size');count+=1
    for i,b in enumerate(d['banks']):
        observed=Q(expected['snapshots']['1']['analysis'][i]['total_change'])
        demand(observed==2+2*b['offer'],'constant effect witness')
        demand(observed==(4 if b['bank'] in ('A','C','E') else 2),'zero effect witness');count+=2
    demand(before=={p:digest(root/p) for p in RUNTIME},'runtime mutation')
    summary={'volume':'v16','component':'project','status':'passed','runtime_files':11,'reader_files':5,'tasks':7,'domains':5,'points':100,'comparisons':count,'primitive_scenarios':4,'invalid_inputs':len(invalid),'result_markers':len(markers),'scope':'Independent internal prose/proof review and primitive oracle; no real research or external human certification.'}
    json.dumps(summary,allow_nan=False);return summary

if __name__=='__main__':
    demand(len(sys.argv)<=2,'usage: check_v16_project_peer.py [root]')
    check(sys.argv[1] if len(sys.argv)==2 else None)
