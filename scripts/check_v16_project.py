"""Independent primitive reconstruction/model oracle and portable release audit for V16."""
from pathlib import Path
from fractions import Fraction as F
from itertools import product
from html.parser import HTMLParser
from hashlib import sha256
import ast,contextlib,copy,io,json,os,runpy,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
FILES=['content/assessments/parts/v16-project.html','content/projects/v16-assessment-inputs.json','content/projects/v16-assessment-analysis.py','content/projects/v16-assessment-output.json','content/projects/v16-assessment-manifest.json','content/projects/v16-assessment-README.txt','scripts/check_v16_project.py','content/reviews/v16-project-author.json','content/reviews/v16-project-sources.json']
CAPSULE=FILES[1:6]
DOMAINS=['question_literature_judgment','reproduction_data_ethics','model_identification_design','robustness_writing','defense_portfolio']

def need(ok,why):
    if not ok:raise ValueError('V16 project: '+why)

def encode(v):
    if isinstance(v,F):return v.numerator if v.denominator==1 else str(v)
    if isinstance(v,dict):return {k:encode(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [encode(x) for x in v]
    return v

def q(v):return F(str(v))

def oracle(data):
    """Primitive row sorting, signed contrasts and objective candidate comparison."""
    registry=data['banks'];raw=sorted(data['ledger'],key=lambda r:r['revision']);snapshots={};rest=[]
    for vintage in (0,1):
        cells={}
        for row in raw:
            if row['revision']<=vintage:cells[row['cohort'],row['date'],row['component']]=F(row['value_thousands'],1000)
        rows=[]
        for b in registry:
            r={k:b[k] for k in ('bank','pair','offer','cohort')}
            for component in ('own','other'):
                r[component+'_before']=cells[b['cohort'],0,component];r[component+'_after']=cells[b['cohort'],1,component];r[component+'_change']=r[component+'_after']-r[component+'_before']
            for t in ('before','after','change'):r['total_'+t]=r['own_'+t]+r['other_'+t]
            rows.append(r)
        contrasts=[]
        for pair in sorted({r['pair'] for r in rows}):
            contrasts.append({'pair':pair,**{component:sum((2*r['offer']-1)*r[component+'_change'] for r in rows if r['pair']==pair) for component in ('own','other','total')}})
        estimate={component:sum(r[component] for r in contrasts)/len(contrasts) for component in ('own','other','total')}
        ref=[]
        for mask in range(8):
            # First pair changes slowest, matching lexicographic sign-order output.
            ref.append(sum((1 if mask&(1<<(2-j)) else -1)*r['total'] for j,r in enumerate(contrasts))/3)
        tail=sum(v*v>=estimate['total']**2 for v in ref)
        snapshots[str(vintage)]={'analysis':rows,'paired_contrasts':contrasts,'estimate':estimate,'sharp_null':{'reference':ref,'tail':tail,'assignments':8,'p':F(tail,8)}}
    for b in registry:
        for component in ('own','other'):
            for date in (0,1):
                found=[r for r in raw if (r['cohort'],r['component'],r['date'])==(b['cohort'],component,date)]
                if any(r['revision']==1 for r in found):
                    before=F(next(r['value_thousands'] for r in found if r['revision']==0),1000);after=F(next(r['value_thousands'] for r in found if r['revision']==1),1000)
                    rest.append({'cohort':b['cohort'],'date':date,'component':component,'old':before,'new':after,'change':after-before})
    m=data['model'];a=q(m['a']);base=q(m['baseline_cost']);trans=q(data['sensitivity']['transport_displacement']);policies=[]
    def best(cost,h,k):
        candidates={F(0),k};stationary=(a-cost)/h
        if 0<=stationary<=k:candidates.add(stationary)
        return max(candidates,key=lambda x:(a-cost)*x-h*x*x/2)
    for policy in m['policies']:
        s=q(policy['subsidy']);budget=q(policy['budget']);details=[];other_levels=[]
        for typ in m['types']:
            h=q(typ['curvature']);k=q(typ['capacity']);lam=q(typ['displacement']);o=q(typ['other_baseline']);x0=best(base,h,k);x1=best(base-s,h,k);inc=x1-x0;other_levels.append(o)
            details.append({'pair':typ['pair'],'baseline':x0,'offer':x1,'bank_increment':inc,'other_increment':-lam*inc,'borrower_increment':inc-lam*inc,'other_after':o-lam*inc,'transport_borrower_increment':inc-trans*inc,'marginal_at_offer':a-base+s-h*x1,'capacity':k})
        spent=sum(s*r['offer'] for r in details);issues=[]
        if spent>budget:issues.append('subsidy_spending_exceeds_budget')
        if min(r['other_after'] for r in details)<0:issues.append('negative_other_lender_stock')
        if any(o-trans*r['bank_increment']<0 for o,r in zip(other_levels,details)):issues.append('negative_transport_other_stock')
        policies.append({'name':policy['name'],'subsidy':s,'budget':budget,'spending':spent,'feasible':not issues,'diagnostics':issues,'mean_bank_increment':sum(r['bank_increment'] for r in details)/3,'mean_borrower_increment':sum(r['borrower_increment'] for r in details)/3,'mean_transport_increment':sum(r['transport_borrower_increment'] for r in details)/3,'types':details})
    lo,hi=map(q,data['sensitivity']['unrecorded_contrast_bounds']);v=snapshots['1']['estimate']['total']
    return encode({'schema':'v16-research-results-1','status':'synthetic_rehearsal_only','raw_records':len(raw),'analysis_rows_per_snapshot':6,'snapshots':snapshots,'restatements':rest,'correction_delta':{c:snapshots['1']['estimate'][c]-snapshots['0']['estimate'][c] for c in ('own','other','total')},'measurement_sensitivity':{'unrecorded_contrast_bounds':[lo,hi],'compatible_observed_contrast':[v+lo,v+hi],'scope':'measurement scenario, not causal confidence interval'},'policies':policies,'limits':['Sharp-null p values concern the stipulated paired lottery and no interference, not a weak-average-effect null.','Structural parameters and displacement are assumed, not identified by fitting three contrasts.','Budget feasibility is not welfare approval; synthetic corrections are not a real-paper replication.']})

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.sources={};self.links=[];self.markers={};self.capture=None;self.rubric=[];self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','fragment without h1')
        if 'id' in a:self.ids.append(a['id']);need(a['id']=='project' or a['id'].startswith('project-'),'project-prefixed IDs')
        if t=='li' and any(x=='ol' and 'exercises' in d.get('class','').split() for x,d in self.stack):self.tasks.append(a.get('id'))
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in d.get('class','').split() for x,d in self.stack),'solutions disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if t=='a' and 'href' in a:self.links.append(a['href'])
        if 'data-result' in a:self.capture=a['data-result'];need(self.capture not in self.markers,'unique result marker');self.markers[self.capture]=''
        if 'data-rubric-domain' in a:self.rubric.append((a['data-rubric-domain'],int(a['data-points'])))
        if t=='table':self.table=a.get('id');self.tables[self.table]=[]
        if t=='tr':self.row=[]
        if t in ('th','td'):self.cell=''
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.capture:self.markers[self.capture]+=s
        if self.cell is not None:self.cell+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');_,a=self.stack.pop()
        if 'data-result' in a:self.capture=None
        if t in ('td','th'):self.row.append(self.cell.strip());self.cell=None
        if t=='tr':self.tables[self.table].append(self.row);self.row=None
        if t=='table':self.table=None

def parse_number(s):
    def visit(n):
        if isinstance(n,ast.Expression):return visit(n.body)
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        if isinstance(n,ast.Tuple):return tuple(visit(v) for v in n.elts)
        raise ValueError('bad numeric marker')
    return visit(ast.parse(s.replace('−','-'),mode='eval'))

def cli_gates(root,expected):
    """Actually run both interpreter modes and every alias class on disposable files."""
    tests=0
    with tempfile.TemporaryDirectory(prefix='v16-project-reader-') as tmp:
        p=Path(tmp)
        for file in CAPSULE:(p/Path(file).name).write_bytes((root/file).read_bytes())
        code=p/'v16-assessment-analysis.py';inp=p/'v16-assessment-inputs.json';out=p/'v16-assessment-output.json'
        protected=[inp,code,p/'v16-assessment-README.txt',p/'v16-assessment-manifest.json']
        frozen={f.name:f.read_bytes() for f in protected};initial={f.name for f in p.iterdir()};need(len(initial)==5,'five-file reader capsule')
        for optimized in (False,True):
            flags=['-I','-B']+(['-O'] if optimized else [])
            for explicit in (False,True):
                command=[sys.executable,*flags,str(code)]+([str(inp),str(out)] if explicit else [])
                proc=subprocess.run(command,cwd='/',capture_output=True,text=True);need(proc.returncode==0 and not proc.stdout and not proc.stderr,'quiet actual reader CLI');need(json.loads(out.read_text())==expected,'reader CLI result');need({f.name for f in p.iterdir()}==initial,'reader capsule membership');tests+=1
            for target in protected:
                for kind in ('direct','resolved','symlink','hardlink'):
                    alias=p/('alias-'+kind)
                    if kind=='direct':destination=target
                    elif kind=='resolved':
                        alias.mkdir();destination=alias/'..'/target.name
                    elif kind=='symlink':alias.symlink_to(target);destination=alias
                    else:os.link(target,alias);destination=alias
                    before={f.name:('dir' if f.is_dir() else f.read_bytes()) for f in p.iterdir()}
                    proc=subprocess.run([sys.executable,*flags,str(code),str(inp),str(destination)],cwd='/',capture_output=True,text=True)
                    need(proc.returncode!=0 and not proc.stdout and 'output ' in proc.stderr and 'protected research input' in proc.stderr,'actual protected alias rejected')
                    need(before=={f.name:('dir' if f.is_dir() else f.read_bytes()) for f in p.iterdir()},'alias rejection preserves every byte/member');need(frozen=={f.name:f.read_bytes() for f in protected},'all protected bytes unchanged');tests+=1
                    if kind=='resolved':alias.rmdir()
                    elif kind!='direct':alias.unlink()
        need({f.name for f in p.iterdir()}==initial,'final reader inventory')
    return tests

def check(root=None):
    root=Path(root) if root is not None else ROOT
    author=json.loads((root/FILES[7]).read_text());need(set(author['payloads'])==set(FILES)-{FILES[7]},'eight nonself author hashes')
    for file,record in author['payloads'].items():
        b=(root/file).read_bytes();need(record=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'author freeze '+file)
    need(not author['open_material_findings'] and author['full_reading_complete'],'full author review')
    manifest=json.loads((root/FILES[4]).read_text());expected_names={Path(f).name for f in CAPSULE if f!=FILES[4]};need(set(manifest['payloads'])==expected_names,'four nonself manifest payloads')
    for name,record in manifest['payloads'].items():
        b=(root/'content/projects'/name).read_bytes();need(record=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'capsule hash '+name)
    data=json.loads((root/FILES[1]).read_text());expected=oracle(data) # Independent primitives before reader API.
    scope=runpy.run_path(str(root/FILES[2]));reader=scope['run'];count=0
    def same(a,b,label):
        nonlocal count
        need(type(a)==type(b),label+' type')
        if isinstance(a,dict):
            need(set(a)==set(b),label+' keys')
            for k in a:same(a[k],b[k],label+'.'+k)
        elif isinstance(a,(tuple,list)):
            need(len(a)==len(b),label+' length')
            for i,(x,y) in enumerate(zip(a,b)):same(x,y,label+str(i))
        else:need(a==b,label);count+=1
    def call(d):
        before=copy.deepcopy(d);capture=io.StringIO()
        with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):result=reader(d)
        need(not capture.getvalue() and d==before,'pure quiet reader API');json.dumps(result,allow_nan=False);return result
    same(call(data),expected,'primitive reader output');same(json.loads((root/FILES[3]).read_text()),expected,'stored output')
    # Substantive alternative scenarios: changed ledger, baseline/interior/cap model,
    # changed displacement and spending budget; every output field compared.
    alternatives=[]
    d=copy.deepcopy(data);d['ledger'][-1]['value_thousands']=17000;alternatives.append(d)
    d=copy.deepcopy(data);d['model']['a']='8';d['model']['types'][1]['capacity']='5';alternatives.append(d)
    d=copy.deepcopy(data);d['model']['types'][0]['displacement']='4';d['model']['policies'][2]['budget']='10';alternatives.append(d)
    for i,d in enumerate(alternatives):same(call(d),oracle(d),'alternative'+str(i))
    # Independent optimality certificates and exact rank size under the sharp null.
    for policy in expected['policies']:
        for typ,row in zip(data['model']['types'],policy['types']):
            h=q(typ['curvature']);k=q(typ['capacity']);s=q(policy['subsidy']);a=q(data['model']['a']);r=q(data['model']['baseline_cost'])-s;x=q(row['offer']);objective=lambda y:(a-r)*y-h*y*y/2
            for test in (F(0),k,k/2,x):need(objective(x)>=objective(test),'global candidate value');count+=1
            derivative=a-r-h*x;need((x==0 and derivative<=0) or (x==k and derivative>=0) or (0<x<k and derivative==0),'global KKT regime');count+=1
    for version in ('0','1'):
        ref=list(map(q,expected['snapshots'][version]['sharp_null']['reference']));ps=[F(sum(abs(v)>=abs(x) for v in ref),8) for x in ref]
        for j in range(9):need(F(sum(p<=F(j,8) for p in ps),8)<=F(j,8),'finite rank size');count+=1
    page=Page();page.feed((root/FILES[0]).read_text());page.close();need(not page.stack and len(page.ids)==len(set(page.ids)),'complete HTML unique IDs')
    taskids=['project-task'+str(i) for i in range(1,8)];need(page.tasks==page.answers==taskids,'seven paired full task artifacts');need(page.rubric==[(d,20) for d in DOMAINS],'five20point domains')
    sources=json.loads((root/FILES[8]).read_text());need(page.sources=={s['id']:s['url'] for s in sources['sources']},'source map');need({link for link in page.links if not link.startswith(('http','#'))}=={Path(f).name for f in CAPSULE},'flat five downloads')
    snap0=expected['snapshots']['0'];snap1=expected['snapshots']['1'];vals={'project-records':(25,24,6),'project-own-pairs':tuple(q(r['own']) for r in snap1['paired_contrasts']),'project-other-v0':tuple(q(r['other']) for r in snap0['paired_contrasts']),'project-other-v1':tuple(q(r['other']) for r in snap1['paired_contrasts']),'project-total-v0':tuple(q(r['total']) for r in snap0['paired_contrasts']),'project-total-v1':tuple(q(r['total']) for r in snap1['paired_contrasts']),'project-means-v0':tuple(q(snap0['estimate'][c]) for c in ('own','other','total')),'project-means-v1':tuple(q(snap1['estimate'][c]) for c in ('own','other','total')),'project-correction':tuple(q(expected['correction_delta'][c]) for c in ('own','other','total')),'project-reference-v0':tuple(map(q,snap0['sharp_null']['reference'])),'project-reference-v1':tuple(map(q,snap1['sharp_null']['reference'])),'project-randomization':(F(2),F(8),F(1,4)),'project-measurement-range':tuple(map(q,expected['measurement_sensitivity']['compatible_observed_contrast'])),'project-transport':q(expected['policies'][2]['mean_transport_increment'])}
    need(set(vals)==set(page.markers),'all HTML markers covered')
    for k,v in vals.items():need(parse_number(page.markers[k])==v,'HTML '+k);count+=1
    # Reconstruct all numeric HTML tables, including complete input and policies.
    for html,b,r0,r1 in zip(page.tables['project-ledger'][1:],data['banks'],snap0['analysis'],snap1['analysis']):
        need(html[:3]==[b['bank']+'/'+b['cohort'],b['pair'],str(b['offer'])],'ledger identity');need(tuple(map(q,html[3:]))==tuple(q(v) for v in (r1['own_before'],r1['own_after'],r1['other_before'],r0['other_after'],r1['other_after'])),'all ledger inputs');count+=8
    for html,typ in zip(page.tables['project-model'][1:],data['model']['types']):
        need(html[0]==typ['pair'] and tuple(map(q,html[1:]))==tuple(q(typ[k]) for k in ('curvature','capacity','displacement','other_baseline')),'all model inputs');count+=5
    for html,r0,r1 in zip(page.tables['project-analysis'][1:],snap0['analysis'],snap1['analysis']):
        need(html[0]==r1['bank'],'analysis bank')
        for s,r in zip(html[1:3],(r0,r1)):need(parse_number(s)==tuple(q(r[c+'_change']) for c in ('own','other','total')),'all analysis changes');count+=3
        need(tuple(map(q,html[3:]))==(q(r1['total_before']),q(r1['total_after'])),'analysis levels');count+=2
    for html,row in zip(page.tables['project-policies'][1:],expected['policies']):
        need(html[0]==row['name'],'policy name');need(tuple(map(q,html[1:3]))==(q(row['subsidy']),q(row['budget'])),'policy inputs');need(parse_number(html[3])==tuple(q(r['offer']) for r in row['types']),'policy choices');need(tuple(map(q,html[4:7]))==tuple(q(row[k]) for k in ('mean_bank_increment','mean_borrower_increment','spending')),'policy outcomes');need(html[7]==('Yes' if row['feasible'] else 'No: budget'),'policy feasibility');count+=8
    for html,version in zip(page.tables['project-paper-results'][1:],('0','1')):
        snapshot=expected['snapshots'][version];need(html[0]=='v'+version and tuple(q(x.replace('−','-')) for x in html[1:])==tuple(q(snapshot['estimate'][c]) for c in ('own','other','total'))+(q(snapshot['sharp_null']['p']),),'paper table');count+=5
    invalid=[]
    def bad(fn):d=copy.deepcopy(data);fn(d);invalid.append(d)
    bad(lambda d:d['ledger'].append(copy.deepcopy(d['ledger'][0])))
    bad(lambda d:d['ledger'][0].update(cohort='UNKNOWN'))
    bad(lambda d:d['ledger'][0].update(value_thousands=None))
    bad(lambda d:d['ledger'][0].update(value_thousands=-1))
    bad(lambda d:d['ledger'][0].update(value_thousands=True))
    bad(lambda d:d['ledger'].pop(1))
    bad(lambda d:d['ledger'][0].update(date=2))
    bad(lambda d:d['ledger'][0].update(revision=2))
    bad(lambda d:d['banks'][0].update(offer=0))
    bad(lambda d:d['banks'][0].update(offer=True))
    bad(lambda d:d['banks'][0].update(borrowers=99))
    bad(lambda d:d['banks'][0].update(cohort='CB'))
    bad(lambda d:d['model']['types'][0].update(curvature='0'))
    bad(lambda d:d['model']['types'][0].update(capacity='-1'))
    bad(lambda d:d['model']['types'][0].update(displacement='-1'))
    bad(lambda d:d['model']['policies'][0].update(subsidy='11'))
    bad(lambda d:d['model']['policies'][0].update(budget='-1'))
    bad(lambda d:d['model'].update(a='NaN'))
    bad(lambda d:d['sensitivity'].update(unrecorded_contrast_bounds=['1','-1']))
    bad(lambda d:d['provenance'].update(raw_unit='million currency units'))
    for d in invalid:
        before=copy.deepcopy(d)
        try:reader(d)
        except ValueError:pass
        else:raise ValueError('V16 project: invalid input accepted')
        need(d==before,'invalid input not mutated')
    tests=cli_gates(root,expected)
    return {'volume':'v16','component':'project','status':'passed','runtime_files':9,'reader_files':5,'tasks':7,'domains':5,'points':100,'comparisons':count,'complete_primitive_scenarios':1+len(alternatives),'assignment_worlds_per_version':8,'invalid_domains':len(invalid),'actual_reader_CLI_runs':4,'actual_protected_alias_rejections':tests-4,'HTML_result_markers':len(vals),'qualitative_scope':'Full original notes/two reports/proposal/paper/release/defense/proofs read separately; no real-research achievement or human evaluation claimed.'}

if __name__=='__main__':
    need(len(sys.argv)<=2,'at most one root path');check(sys.argv[1] if len(sys.argv)==2 else None)
