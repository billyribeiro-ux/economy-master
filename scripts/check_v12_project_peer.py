"""Independent Harbor Skills peer audit; eleven read-only package payloads."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import combinations
from math import isfinite, isqrt
from pathlib import Path
import json
import runpy
import shutil
import subprocess
import sys
import tempfile

AUTHOR = (
    'content/assessments/parts/v12-project.html',
    'content/projects/v12-assessment-inputs.json',
    'content/projects/v12-assessment-analysis.py',
    'content/projects/v12-assessment-output.json',
    'content/projects/v12-assessment-manifest.json',
    'content/projects/v12-assessment-README.txt',
    'scripts/check_v12_project.py',
    'content/reviews/v12-project-author.json',
    'content/reviews/v12-project-sources.json',
)
SELF='scripts/check_v12_project_peer.py'
REVIEW='content/reviews/v12-project-peer.json'
SETS=tuple(combinations(range(1,7),3))
# These are primitive centre/worker laws, reconstructed from the manuscript table.
GROUPS=((-2,('C','C'),(2,4),(40,42)),(1,('C','N'),(6,1),(44,46)),
        (3,('A','C'),(3,2),(48,50)),(-1,('N','N'),(8,0),(52,54)),
        (2,('A','N'),(5,1),(56,58)),(0,('C','C'),(4,6),(60,62)))


def require(ok,label):
    if not ok:raise ValueError('Harbor peer: '+label)


def strict(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def fail(x):raise ValueError('nonfinite JSON '+x)
    result=json.loads(raw,object_pairs_hook=pairs,parse_constant=fail)
    def scan(x):
        if isinstance(x,float):require(isfinite(x),'overflowed JSON number')
        elif isinstance(x,dict):
            for v in x.values():scan(v)
        elif isinstance(x,list):
            for v in x:scan(v)
    scan(result)
    return result


def encoded(x):
    if isinstance(x,F):return str(x)
    if isinstance(x,(list,tuple)):return [encoded(v) for v in x]
    if isinstance(x,dict):return {k:encoded(v) for k,v in x.items()}
    return x


class Audit:
    def __init__(self):
        self.comparisons=0;self.rejections=0;self.aliases=0;self.valid_calls=0;self.cells=0
    def same(self,a,b,label):
        a,b=encoded(a),encoded(b)
        require(type(a) is type(b) and a==b,label+': '+repr(a)[:160]+' != '+repr(b)[:160])
        self.comparisons+=1
    def reject(self,fn,label):
        try:fn()
        except ValueError:self.rejections+=1
        else:raise ValueError('accepted invalid case '+label)
    def call(self,fn,data):
        before=deepcopy(data);out=StringIO();err=StringIO()
        with redirect_stdout(out),redirect_stderr(err):result=fn(data)
        self.same((out.getvalue(),err.getvalue()),('',''),'quiet run')
        self.same(data,before,'no input mutation')
        self.same(strict(json.dumps(result,allow_nan=False)),result,'strict JSON result')
        self.valid_calls+=1
        return result


def avg(values):
    require(0<len(values)<=24,'bounded nonempty average')
    return sum(values,F(0))/len(values)


def sample_var(values):
    require(len(values)>1,'sample variance needs two values')
    return sum((x-avg(values))**2 for x in values)/(len(values)-1)


def generate(assignment,weak=False,common=None,delta=F(0)):
    rows=[]
    for j,(g,kinds,effects,baselines) in enumerate(GROUPS,1):
        for r,(kind,tau,b) in enumerate(zip(kinds,effects,baselines),1):
            if weak and (j,r)==(2,1):kind='N'
            if common is not None and kind=='C':tau=common
            z=int(j in assignment);d=int(kind=='A' or (kind=='C' and z))
            w=F(g+(2*r-3))+tau*d
            if kind=='C':w=F(g+(2*r-3))+(F(tau)-delta)*d+delta*z
            rows.append([j,r,z,d,b,F(b)+w,w])
    return rows


def centre(rows,column):
    return [avg([F(row[column]) for row in rows if row[0]==j]) for j in range(1,7)]


def contrast(values,assignment):
    return sum((1 if j in assignment else -1)*v for j,v in enumerate(values,1))/3


def determinant(a):
    return (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
            -a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
            +a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))


def regression(w,b,assignment,audit=None):
    x=[v-avg(b) for v in b];z=[F(j in assignment) for j in range(1,7)]
    columns=[[F(1)]*6,z,x]
    gram=[[sum(a*b for a,b in zip(c,d)) for d in columns] for c in columns]
    rhs=[sum(a*b for a,b in zip(c,w)) for c in columns]
    det=determinant(gram);require(det>0,'full-rank positive Gram matrix')
    # Cramer's rule is separate from model elimination and the projection check.
    coefficients=[]
    for k in range(3):
        replaced=[[rhs[i] if j==k else gram[i][j] for j in range(3)] for i in range(3)]
        coefficients.append(determinant(replaced)/det)
    zc=[v-avg(z) for v in z];xx=sum(v*v for v in x)
    zx=sum(a*b for a,b in zip(zc,x));residual=[a-zx*b/xx for a,b in zip(zc,x)]
    denominator=sum(v*v for v in residual);numerator=sum(v*y for v,y in zip(residual,w))
    if audit is not None:
        audit.same(coefficients[1],numerator/denominator,'Cramer versus separate FWL')
        audit.same([sum(v*y for v,y in zip(row,coefficients)) for row in gram],rhs,'all normal equations')
    return coefficients,denominator,numerator


def moments(rows,assignment,audit=None):
    w,d,b,y=[centre(rows,k) for k in (6,3,4,5)]
    itt,first=contrast(w,assignment),contrast(d,assignment)
    coef,den,num=regression(w,b,assignment,audit)
    vhat=sum(sample_var([v for j,v in enumerate(w,1) if (j in assignment)==flag])/3 for flag in (True,False))
    received=[[F(r[6]) for r in rows if r[3]==d] for d in (1,0)]
    iid=sum(sample_var([F(r[6]) for r in rows if r[2]==d])/6 for d in (1,0))
    return {'assignment':list(assignment),'centre_baseline':b,'centre_change':w,'centre_receipt':d,
            'change_ITT':itt,'post_only_ITT':contrast(y,assignment),'baseline_difference':contrast(b,assignment),
            'first_stage':first,'Wald':itt/first if first else None,
            'Wald_status':'defined' if first else 'undefined_zero_first_stage',
            'receipt_OLS':avg(received[0])-avg(received[1]),'receipt_OLS_status':'descriptive',
            'ANCOVA_coefficients':coef,'ANCOVA_regressors':['intercept','Z','centre_B-mean_B'],
            'cluster_Neyman':vhat,'incorrect_individual_iid_variance':iid},(den,num)


def complete_law(weak,audit):
    zero,one=generate((),weak),generate(range(1,7),weak)
    w0,w1,d0,d1=[centre(rows,k) for rows,k in ((zero,6),(one,6),(zero,3),(one,3))]
    effects=[b-a for a,b in zip(w0,w1)];truth=avg(effects);first=avg([b-a for a,b in zip(d0,d1)])
    stats=[moments(generate(s,weak),s,audit)[0] for s in SETS]
    actualvar=avg([(r['change_ITT']-truth)**2 for r in stats])
    suma=[a+b for a,b in zip(w0,w1)]
    covariancevar=sum((F(1,4) if i==j else F(-1,20))*suma[i]*suma[j] for i in range(6) for j in range(6))/9
    audit.same(actualvar,covariancevar,'complete indicator-covariance variance')
    formula=sample_var(w1)/3+sample_var(w0)/3-sample_var(effects)/6
    audit.same(actualvar,formula,'potential sample-variance identity')
    neyman_mean=avg([r['cluster_Neyman'] for r in stats])
    audit.same(neyman_mean,(sample_var(w1)+sample_var(w0))/3,'expected unbiased arm variances')
    undefined=sum(r['Wald'] is None for r in stats)
    return {'assignment_count':20,'centre_change_z0':w0,'centre_change_z1':w1,
            'centre_encouragement_effects':effects,'encouragement_ATE':truth,'first_stage':first,
            'complier_receipt_ATE_under_exclusion':truth/first,
            'expected_change_ITT':avg([r['change_ITT'] for r in stats]),
            'expected_post_only_ITT':avg([r['post_only_ITT'] for r in stats]),
            'expected_first_stage':avg([r['first_stage'] for r in stats]),
            'expected_ANCOVA':avg([r['ANCOVA_coefficients'][1] for r in stats]),
            'expected_Wald':None if undefined else avg([r['Wald'] for r in stats]),
            'expected_Wald_status':'undefined_on_assignment_support' if undefined else 'unconditional_defined',
            'zero_first_stage_assignments':undefined,
            'first_stage_range':[min(r['first_stage'] for r in stats),max(r['first_stage'] for r in stats)],
            'true_ITT_variance':actualvar,'variance_formula':formula,'expected_Neyman':neyman_mean,
            'centre_effect_sample_variance':sample_var(effects),'Neyman_expectation_gap':neyman_mean-actualvar}


def reference(rows,assignment,audit):
    values,_=moments(rows,assignment,audit)
    w,d,b=[centre(rows,k) for k in (6,3,4)]
    lines=[(contrast(w,s),contrast(d,s)) for s in SETS]
    observed=lines[SETS.index(tuple(assignment))]
    changes=[abs(v[0]) for v in lines]
    ancovas=[abs(regression(w,b,s)[0][1]) for s in SETS]
    values['sharp_outcome_null_p_change']=F(sum(v>=abs(observed[0]) for v in changes),20)
    values['sharp_outcome_null_p_ANCOVA']=F(sum(v>=abs(values['ANCOVA_coefficients'][1]) for v in ancovas),20)
    # Only fixed observed arrays enter; no potential regeneration in this reference.
    return values,lines,observed


def real_partition(lines,actual):
    """Independent quadratic roots, including degenerate polynomial handling."""
    a0,b0=actual;polynomials=[];roots=set()
    for a,b in lines:
        coefficients=(b*b-b0*b0,2*(a0*b0-a*b),a*a-a0*a0)
        A,B,C=coefficients;polynomials.append(coefficients)
        if A:
            D=B*B-4*A*C;require(D>=0,'squared-line discriminant nonnegative')
            n,d=isqrt(D.numerator),isqrt(D.denominator)
            require(n*n==D.numerator and d*d==D.denominator,'exact rational square root')
            r=F(n,d);roots.update(((-B-r)/(2*A),(-B+r)/(2*A)))
        elif B:roots.add(-C/B)
        # A=B=C=0 means this comparison is tied for every real tau: no root.
    cuts=sorted(roots)
    def probability(t):
        return F(sum(A*t*t+B*t+C>=0 for A,B,C in polynomials),len(polynomials))
    cells=[];bounds=[None]+cuts+[None]
    for lo,hi in zip(bounds,bounds[1:]):
        t=(lo+hi)/2 if lo is not None and hi is not None else hi-1 if hi is not None else lo+1 if lo is not None else F(0)
        cells.append(('open',lo,hi,t))
        if hi is not None:cells.append(('point',hi,hi,hi))
    return cuts,cells,probability


def check_inversion(actual,lines,line,alpha,audit,label):
    roots,cells,p=real_partition(lines,line)
    audit.same(actual['breakpoints'],roots,label+' genuine roots, no identity kink')
    audit.same(actual['alpha'],alpha,label+' alpha')
    audit.same(actual['reject_if'],'p <= alpha',label+' rejection ties')
    audit.same(actual['null'],'sharp_adjusted_outcome_invariance',label+' sharp null')
    segments=[]
    for row in actual['intervals']:
        audit.same(set(row),{'lower','upper','lower_unbounded','upper_unbounded','lower_closed','upper_closed'},label+' interval schema')
        lo=None if row['lower'] is None else F(row['lower']);hi=None if row['upper'] is None else F(row['upper'])
        lc,uc=row['lower_closed'],row['upper_closed']
        audit.same(type(lc) is bool and type(uc) is bool,True,label+' endpoint flags')
        audit.same((row['lower_unbounded'],row['upper_unbounded']),(lo is None,hi is None),label+' unbounded flags')
        audit.same((lo is not None or not lc) and (hi is not None or not uc),True,label+' infinity not closed')
        audit.same((lo is None or lo in roots) and (hi is None or hi in roots),True,label+' endpoints have crossing proof')
        audit.same(lo is None or hi is None or lo<hi or (lo==hi and lc and uc),True,label+' nonempty intervals')
        if segments:
            previous=segments[-1]
            audit.same(previous[1] is not None and lo is not None and (previous[1]<lo or (previous[1]==lo and not previous[3] and not lc)),True,label+' ordered maximally merged components')
        segments.append((lo,hi,lc,uc))
    for kind,lo,hi,t in cells:
        inside=any((l is None or t>l or (t==l and lc)) and (u is None or t<u or (t==u and uc)) for l,u,lc,uc in segments)
        audit.same(inside,p(t)>alpha,label+' complete cell '+kind)
        audit.cells+=1
    for tau,value in actual['probe_p'].items():audit.same(value,p(F(tau)),label+' printed probe')
    audit.same('not a generic' in actual['scope'],True,label+' heterogeneous-effect limit')
    return roots,p


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.values={};self.tables={};self.links=[];self.sources=set();self.domains=[];self.rubrics=[]
        self.table=None;self.row=None;self.cell=None;self.capture=None;self.parts=[];self.domain=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a':
            self.links.append(a.get('href',''))
            if 'data-source' in a:self.sources.add(a['data-source'])
        if 'data-value' in a:
            require(self.capture is None and a['data-value'] not in self.values,'unique value marker')
            self.capture=a['data-value'];self.parts=[]
        if tag=='table' and a.get('id') in ('v12-project-observed','v12-project-oracle'):
            self.table=a['id'];self.tables[self.table]=[]
        if 'data-domain' in a:
            self.domain=a['data-domain'];self.domains.append((self.domain,int(a['data-points'])))
        if tag=='tr':self.row=[]
        if tag=='td':self.cell=[]
        if tag not in ('br','hr','img','meta','input','link'):self.stack.append(tag)
    def handle_data(self,data):
        if self.capture is not None:self.parts.append(data)
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack.pop()==tag,'balanced manuscript')
        if tag=='span' and self.capture is not None:
            self.values[self.capture]=''.join(self.parts).strip();self.capture=None
        if tag=='td':self.row.append(''.join(self.cell).strip());self.cell=None
        if tag=='tr':
            if self.table and self.row:self.tables[self.table].append(self.row)
            if self.domain:self.rubrics.append((self.domain,self.row));self.domain=None
        if tag=='table':self.table=None


def manuscript(base,truth,weak,audit,root):
    text=(root/AUTHOR[0]).read_text();page=Page();page.feed(text);page.close()
    audit.same(page.stack,[],'closed manuscript')
    audit.same(len(page.ids),len(set(page.ids)),'unique project IDs')
    audit.same([i for i in page.ids if i.startswith('v12-project-task-')],['v12-project-task-'+str(i) for i in range(1,8)],'seven exact tasks')
    audit.same([i for i in page.ids if i.startswith('v12-project-solution-')],['v12-project-solution-'+str(i) for i in range(1,8)],'seven paired guide sections')
    audit.same(page.domains,[('D'+str(i),20) for i in range(1,6)],'five essential domains')
    import re
    for domain,cells in page.rubrics:
        allocated=[int(s) for s in re.findall(r'\b\d+\b',cells[2])]
        audit.same(sum(allocated),20,'actual rubric components '+domain)
    audit.same('85/100' in text and '15/20' in text,True,'overall and domain floors')
    original=generate((1,3,5))
    audit.same(page.tables['v12-project-observed'],[[str(v) for v in row] for row in original],'all observed reader cells')
    primitive=[]
    for j,(g,k,t,b) in enumerate(GROUPS,1):primitive.append([str(j),str(g),', '.join(k),', '.join(map(str,t)),', '.join(map(str,b))])
    audit.same(page.tables['v12-project-oracle'],primitive,'all primitive reader cells')
    sources={'v12-c03-imbens-angrist1994','v12-c06-ding-experiments','asa-pvalues-2016','v04-c01-aea-data-faq'}
    audit.same(page.sources,sources,'actual source routes')
    downloads={'v12-assessment-'+s for s in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')}
    audit.same(set(page.links),downloads|{'sources.html#'+s for s in sources},'flat offline links')
    den,num=regression(centre(original,6),centre(original,4),(1,3,5))[1:]
    weak_m=moments(generate((1,2,4),True),(1,2,4))[0]
    expected={'itt':base['change_ITT'],'baseline_difference':base['baseline_difference'],'post_itt':base['post_only_ITT'],
              'first':base['first_stage'],'wald':base['Wald'],'receipt':base['receipt_OLS'],'ancova':base['ANCOVA_coefficients'][1],
              'FWL_denominator':den,'FWL_numerator':num,'truth_first':truth['first_stage'],'truth_itt':truth['encouragement_ATE'],
              'truth_cace':truth['complier_receipt_ATE_under_exclusion'],'expected_wald':truth['expected_Wald'],
              'expected_ancova':truth['expected_ANCOVA'],'wald_bias':truth['expected_Wald']-truth['complier_receipt_ATE_under_exclusion'],
              'ancova_bias':truth['expected_ANCOVA']-truth['encouragement_ATE'],'S0':sample_var(truth['centre_change_z0']),
              'S1':sample_var(truth['centre_change_z1']),'Seffect':truth['centre_effect_sample_variance'],'variance':truth['true_ITT_variance'],
              'expected_neyman':truth['expected_Neyman'],'variance_gap':truth['Neyman_expectation_gap'],'neyman':base['cluster_Neyman'],
              'iid':base['incorrect_individual_iid_variance'],'p_change':base['sharp_outcome_null_p_change'],'p_ancova':base['sharp_outcome_null_p_ANCOVA'],
              'weak_truth_itt':weak['encouragement_ATE'],'weak_truth_first':weak['first_stage'],'weak_truth_cace':weak['complier_receipt_ATE_under_exclusion'],
              'weak_itt':weak_m['change_ITT'],'weak_first':weak_m['first_stage']}
    audit.same(set(page.values),set(expected),'complete numerical anchor inventory')
    for key,value in expected.items():audit.same(F(page.values[key]),value,'printed anchor '+key)
    for phrase in ('no random sampling or superpopulation law','reproduction not executed','not pointwise','(−∞,1] ∪ [7,∞)','[3,5]','all of R'):
        audit.same(phrase in text,True,'reader scope '+phrase)
    for prefix,rows,assignment in (('The baseline distinct roots are ',original,(1,3,5)),('Its distinct crossing roots are ',generate((1,2,4),True),(1,2,4))):
        begin=text.index(prefix)+len(prefix);end=text.index('.',begin)
        displayed=[F(x.strip().replace('−','-')) for x in text[begin:end].split(',')]
        w,d=centre(rows,6),centre(rows,3);lines=[(contrast(w,s),contrast(d,s)) for s in SETS]
        audit.same(displayed,real_partition(lines,(contrast(w,assignment),contrast(d,assignment)))[0],'entire printed root list')
    return len(expected),sources


def mutations(data):
    cases=[]
    for path,value in [
        (('schema',),True),(('design','alpha'),'2/10'),(('design','alpha'),0.2),
        (('design','direct_effect_delta'),'-0'),(('design','direct_effect_delta'),'1/1000001'),
        (('design','direct_effect_delta'),True),(('design','direct_effect_delta'),float('nan')),
        (('design','direct_effect_delta'),'2'),(('design','actual_encouraged_centres'),[1,1,5]),
        (('design','actual_encouraged_centres'),[1,2,3]),(('observed_rows',0,3),0),
        (('observed_rows',0,5),40),(('observed_rows',0,1),True),
        (('teaching_oracle','centres',0,'tau'),[3,4]),(('teaching_oracle','weak_override','to'),'C')]:
        d=deepcopy(data);ref=d
        for k in path[:-1]:ref=ref[k]
        ref[path[-1]]=value;cases.append(d)
    d=deepcopy(data);d['design']['unused']=0;cases.append(d)
    d=deepcopy(data);d['observed_rows']=d['observed_rows'][:-1];cases.append(d)
    d=deepcopy(data);del d['teaching_oracle'];cases.append(d)
    cases.extend(({},None,[]))
    return cases


def cli(root,data,expected,audit):
    with tempfile.TemporaryDirectory(prefix='harbor-peer-cli-') as tmp:
        folder=Path(tmp)
        for index in (1,2,3,4,5):shutil.copyfile(root/AUTHOR[index],folder/Path(AUTHOR[index]).name)
        model=folder/'v12-assessment-analysis.py';input_file=folder/'v12-assessment-inputs.json'
        custom=folder/'custom.json';custom.write_text(json.dumps(data))
        output=folder/'check-output.json'
        flags=['-B']+(['-O'] if sys.flags.optimize else [])
        def execute(args):return subprocess.run([sys.executable,*flags,str(model),*args],cwd='/',capture_output=True,text=True,timeout=15)
        result=execute([])
        audit.same((result.returncode,result.stdout,result.stderr),(0,'',''),'quiet default standalone CLI')
        audit.same(strict((folder/'v12-assessment-output.json').read_text()),expected,'default file-generation result')
        result=execute(['--input',str(custom),'--output',str(output)])
        audit.same((result.returncode,result.stdout,result.stderr),(0,'',''),'quiet explicit standalone CLI')
        audit.same(strict(output.read_text()),expected,'explicit file-generation result')
        protected=[model,input_file,custom,folder/'v12-assessment-README.txt',folder/'v12-assessment-manifest.json']
        for source in protected:
            saved=source.read_bytes()
            kinds=('direct','symlink','hardlink') if source in (model,input_file,custom) else ('direct',)
            for kind in kinds:
                destination=source if kind=='direct' else folder/('alias-'+kind)
                if kind=='symlink':destination.symlink_to(source)
                if kind=='hardlink':destination.hardlink_to(source)
                result=execute(['--input',str(custom),'--output',str(destination)])
                audit.same(result.returncode!=0 and result.stdout=='',True,'real '+kind+' output alias rejection')
                audit.same(source.read_bytes(),saved,'protected bytes retained')
                if kind!='direct':destination.unlink()
                audit.aliases+=1
        invalid=[input_file.read_text().replace('"schema": 1','"schema": 1,"schema": 1',1),
                 input_file.read_text().replace('"alpha": "1/5"','"alpha": NaN',1),' '*65537]
        for raw in invalid:
            bad=folder/'invalid.json';bad.write_text(raw);output.write_text('preserve existing output')
            result=execute(['--input',str(bad),'--output',str(output)])
            audit.same(result.returncode!=0 and result.stdout=='',True,'invalid CLI rejected')
            audit.same(output.read_text(),'preserve existing output','invalid input preserves destination')
            audit.rejections+=1


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    paths=AUTHOR+(SELF,REVIEW);before={p:(root/p).read_bytes() for p in paths};audit=Audit()
    peer=strict(before[REVIEW].decode());bindings=peer['payload_bindings']
    audit.same({b['path'] for b in bindings},set(AUTHOR+(SELF,)),'ten peer nonself bindings')
    audit.same(len(bindings),10,'peer binding count')
    for row in bindings:
        payload=before[row['path']]
        audit.same((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'peer-bound final payload')
    data=strict(before[AUTHOR[1]].decode());saved_output=strict(before[AUTHOR[3]].decode())
    stream=StringIO()
    with redirect_stdout(stream),redirect_stderr(stream):model=runpy.run_path(str(root/AUTHOR[2]),run_name='harbor_peer_model')
    audit.same(stream.getvalue(),'','quiet model import')
    truth=complete_law(False,audit);weak_truth=complete_law(True,audit)
    actual=(1,3,5);rows=generate(actual)
    audit.same(data['observed_rows'],[[int(x) for x in row] for row in rows],'independently regenerated original observations')
    baseline,lines,line=reference(rows,actual,audit)
    anchors,source_ids=manuscript(baseline,truth,weak_truth,audit,root)
    cases=[data]
    d=deepcopy(data);d['design']['alpha']='1/20';cases.append(d)
    for delta in ('-1','1','1/2'):
        d=deepcopy(data);d['design']['direct_effect_delta']=delta;cases.append(d)
    changed=(2,3,6);d=deepcopy(data);d['design']['actual_encouraged_centres']=list(changed)
    d['observed_rows']=[[int(x) for x in row] for row in generate(changed)];cases.append(d)
    first_result=None
    for number,item in enumerate(cases):
        result=audit.call(model['run'],item)
        if number==0:first_result=result
        assignment=tuple(item['design']['actual_encouraged_centres']);alpha=F(item['design']['alpha']);delta=F(item['design']['direct_effect_delta'])
        expected,lines,line=reference(item['observed_rows'],assignment,audit)
        for key,value in expected.items():audit.same(result['observed_analysis'][key],value,'observed implementation '+key)
        check_inversion(result['observed_analysis']['sharp_adjusted_outcome_inversion'],lines,line,alpha,audit,'baseline')
        audit.same(result['teaching_oracle'],truth,'entire alternative-law baseline')
        weak_rows=generate((1,2,4),True);weak,wl,wo=reference(weak_rows,(1,2,4),audit)
        audit.same(result['weak_extension']['observed_rows'],[[int(x) for x in row] for row in weak_rows],'separate weak-world records')
        for key,value in weak.items():audit.same(result['weak_extension']['observed_analysis'][key],value,'weak implementation '+key)
        check_inversion(result['weak_extension']['observed_analysis']['sharp_adjusted_outcome_inversion'],wl,wo,alpha,audit,'weak')
        audit.same(result['weak_extension']['teaching_oracle'],weak_truth,'entire weak alternative law')
        direct=result['direct_effect_extension']
        audit.same(direct['delta'],delta,'direct parameter')
        audit.same(direct['complier_receipt_ATE_at_fixed_assignment'],4-delta,'isolated receipt target')
        audit.same(direct['sharp_receipt_effect_bounds'],[F(3),F(5)],'class-specific sharp bounds')
        audit.same((direct['assignment_ATE'],direct['first_stage'],direct['ratio_of_assignment_effects']),[F(2),F(1,2),F(4)],'assignment targets unaffected')
        audit.same(direct['all_worker_assignment_observables_unchanged'],True,'reported equivalence')
        if delta:
            for s in SETS:audit.same(generate(s,delta=delta),generate(s),'every-assignment observable equivalence')
    audit.same(first_result,saved_output,'complete stored output equals executed model')
    # Access to primitive potential functions is actively denied for observed analysis.
    function=model['analyse_observed'];globals_=function.__globals__
    saved={k:globals_[k] for k in ('POPULATION','records','teaching_law')}
    def forbidden(*args,**kwargs):raise RuntimeError('oracle leakage into observed analysis')
    try:
        for k in saved:globals_[k]=forbidden
        capture=StringIO()
        with redirect_stdout(capture),redirect_stderr(capture):detached=function(deepcopy(data['observed_rows']),actual,F(1,5))
        audit.same(capture.getvalue(),'','quiet detached observed analysis')
        audit.same(detached,{k:unpack(v) for k,v in first_result['observed_analysis'].items()},'observed estimator survives denied oracle access')
    finally:
        for k,value in saved.items():globals_[k]=value
    # True-null validation is separate from the supplied heterogeneous alternative.
    pvalues=[]
    for s in SETS:
        homogeneous=generate(s,common=4)
        residual=[row[:6]+[row[6]-4*row[3]] for row in homogeneous]
        fixed=centre(residual,6);actualvalue=abs(contrast(fixed,s))
        pvalues.append(F(sum(abs(contrast(fixed,t))>=actualvalue for t in SETS),20))
    audit.same(F(sum(p<=F(1,5) for p in pvalues),20),F(1,5),'homogeneous true-null size')
    audit.same(F(sum(p<=F(1,20) for p in pvalues),20),F(0),'coarse-resolution true-null size')
    audit.same({tau for _,kinds,effects,_ in GROUPS for kind,tau in zip(kinds,effects) if kind=='C'},{2,4,6},'original heterogeneous null limitation')
    for invalid in mutations(data):
        capture=StringIO()
        def tested():
            with redirect_stdout(capture),redirect_stderr(capture):model['run'](invalid)
        audit.reject(tested,'strict model input')
        audit.same(capture.getvalue(),'','quiet invalid API')
    cli(root,data,first_result,audit)
    manifest=strict(before[AUTHOR[4]].decode())
    audit.same({r['file'] for r in manifest['files']},{Path(AUTHOR[i]).name for i in (1,2,3,5)},'four-payload manifest scope')
    for entry in manifest['files']:
        blob=(root/'content/projects'/entry['file']).read_bytes()
        audit.same((len(blob),sha256(blob).hexdigest()),(entry['bytes'],entry['sha256']),'manifest bytes')
    sources=strict(before[AUTHOR[8]].decode())
    audit.same({s['id'] for s in sources['reused']},source_ids,'scoped source record routes')
    author=strict(before[AUTHOR[7]].decode())
    audit.same({r['path'] for r in author['bindings']},set(AUTHOR)-{AUTHOR[7]},'eight author bindings')
    for entry in author['bindings']:
        blob=before[entry['path']]
        audit.same((len(blob),sha256(blob).hexdigest()),(entry['bytes'],entry['sha256']),'final author-bound payload')
    for path,blob in before.items():audit.same((root/path).read_bytes(),blob,'unchanged package payload')
    summary={'component':'v12-project-peer','status':'separate peer checks passed','comparisons':audit.comparisons,
             'rejections':audit.rejections,'actual_alias_rejections':audit.aliases,'valid_model_cases':audit.valid_calls,
             'printed_anchors':anchors,'real_line_cells_checked':audit.cells,'assignment_support':20,
             'paired_tasks_and_guide_sections':7,'runtime_payloads':11,'author_checker_used_as_oracle':False,
             'external_empirical_replication_performed':False}
    strict(json.dumps(summary,allow_nan=False));return summary


def unpack(value):
    """Convert canonical numeric output strings only, preserving scope text."""
    if isinstance(value,dict):return {k:unpack(v) for k,v in value.items()}
    if isinstance(value,list):return [unpack(v) for v in value]
    if isinstance(value,str):
        try:return F(value)
        except (ValueError,ZeroDivisionError):return value
    return value


if __name__=='__main__':check()
