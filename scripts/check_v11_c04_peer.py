"""Separate peer certificates for c04; no author helper or checker is an oracle."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import math
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'content/projects'
REVIEW = ROOT/'content/reviews/v11-c04-peer.json'


def require(condition, label):
    if not condition:
        raise AssertionError(label)


class Audit:
    def __init__(self):
        self.comparisons=0; self.rejections=0; self.interventions=0

    def eq(self, actual, expected, label):
        self.comparisons+=1
        require(actual==expected,label+': '+repr(actual)+' != '+repr(expected))

    def near(self, actual, expected, label, tolerance=2e-9):
        self.comparisons+=1
        require(math.isfinite(actual) and math.isclose(actual,expected,rel_tol=tolerance,abs_tol=tolerance),label)


class SolutionPairs(HTMLParser):
    """Check semantic prompt/answer pairs without depending on the shared parser."""
    def __init__(self):
        super().__init__()
        self.ids=[];self.lists=[];self.prompts=[];self.answers=[]
        self.current=None;self.summary=False

    def handle_starttag(self,tag,attributes):
        attrs=dict(attributes);classes=attrs.get('class','').split()
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='ol':self.lists.append('exercises' in classes)
        if tag=='li' and self.lists and self.lists[-1]:self.prompts.append(attrs.get('id'))
        if tag=='details' and 'solution' in classes:
            self.current={'target':attrs.get('data-solution-for'),'summary':''}
            self.answers.append(self.current)
        if tag=='summary' and self.current is not None:self.summary=True

    def handle_data(self,data):
        if self.summary:self.current['summary']+=data

    def handle_endtag(self,tag):
        if tag=='ol' and self.lists:self.lists.pop()
        if tag=='summary':self.summary=False
        if tag=='details':self.current=None


def paired_solutions(a,record):
    raw=(ROOT/'content/chapters/v11-c04.html').read_bytes()
    parser=SolutionPairs();parser.feed(raw.decode('utf-8'))
    expected=['v11-c04-e'+str(i) for i in range(1,11)]
    paired=[answer for answer in parser.answers if answer['target'] is not None]
    a.eq(parser.prompts,expected,'ten uniquely identified exact exercise prompts')
    a.eq([answer['target'] for answer in paired],expected,'ten answers paired one-to-one in prompt order')
    a.eq([answer['summary'].split('.',1)[0] for answer in paired],
         [str(i) for i in range(1,11)],'numbered disclosure summaries match paired exercise')
    a.eq([answer['summary'] for answer in parser.answers if answer['target'] is None],
         ['Delayed-check answer'],'retention disclosure is not counted as a chapter exercise')
    a.eq(len(parser.ids),len(set(parser.ids)),'all manuscript IDs are unique')
    restored=raw
    for identifier in expected:
        restored=restored.replace((' id="'+identifier+'"').encode(),b'')
        restored=restored.replace((' data-solution-for="'+identifier+'"').encode(),b'')
    previous=record['resolved_integration_finding']['previous_manuscript']
    a.eq((len(restored),sha256(restored).hexdigest()),(previous['bytes'],previous['sha256']),
         'removing only semantic pairing attributes exactly restores reviewed prose and math')


def quantile_intervals(losses, probabilities, alpha):
    """Integrate the inverse CDF over probability intervals, not greedy state filling."""
    law={}
    for loss,p in zip(losses,probabilities):law[loss]=law.get(loss,F(0))+p
    cumulative=F(0); integral=F(0); quantile=None
    for loss,p in sorted(law.items()):
        end=cumulative+p
        if quantile is None and end>=alpha:quantile=loss
        integral+=loss*max(F(0),end-max(alpha,cumulative))
        cumulative=end
    return quantile,integral/(1-alpha),law


def risk_certificate(a, result, losses, probabilities, alpha, names):
    q,es,law=quantile_intervals(losses,probabilities,alpha)
    mean=sum(x*p for x,p in law.items())
    strict=sum(p for x,p in law.items() if x>q)
    weak=sum(p for x,p in law.items() if x>=q)
    strict_mean=None if strict==0 else str(sum(x*p for x,p in law.items() if x>q)/strict)
    a.eq((F(result['var']),F(result['es'])),(q,es),'inverse-CDF probability intervals')
    a.eq(F(result['mean']),mean,'independent aggregated expectation')
    a.eq(F(result['variance']),sum(p*x*x for x,p in law.items())-mean*mean,'second moment minus squared mean')
    a.eq((F(result['strict_exceedance_probability']),result['strict_tail_mean'],F(result['weak_tail_mean'])),
         (strict,strict_mean,sum(x*p for x,p in law.items() if x>=q)/weak),'strict/weak atom diagnostics')
    objective=q+sum(p*max(x-q,0) for x,p in law.items())/(1-alpha)
    a.eq(F(result['positive_part_objective_at_var']),objective,'threshold positive-part objective')
    a.eq(objective,es,'primal objective equals integrated quantile tail')
    rows=result['tail_allocation']
    a.eq([row['state'] for row in rows],names,'certificate retains every original state')
    weights=[];selected=[]
    for row,x,p in zip(rows,losses,probabilities):
        w,mass=F(row['dual_weight']),F(row['selected_probability'])
        a.eq((F(row['loss']),F(row['available_probability'])),(x,p),'certificate source law')
        a.eq(0<=mass<=p and 0<=w<=p/(1-alpha),True,'feasible state mass and density cap')
        a.eq((w,F(row['es_contribution'])),(mass/(1-alpha),w*x),'tail mass and contribution conversion')
        weights.append(w);selected.append(mass)
    a.eq((sum(weights),sum(selected),sum(w*x for w,x in zip(weights,losses))),
         (F(1),1-alpha,es),'attaining normalized dual certificate')
    # The exact weak-duality slack is nonnegative term by term; this checks
    # the mathematical bound for both an attaining optimizer and original P.
    for candidate in (weights,probabilities):
        slack=sum((p/(1-alpha)-w)*(x-q) if x>q else w*(q-x) if x<q else F(0)
                  for x,p,w in zip(losses,probabilities,candidate))
        a.eq(objective-sum(w*x for w,x in zip(candidate,losses)),slack,'weak-duality slack identity')
        a.eq(slack>=0,True,'feasible weights cannot exceed primal bound')
    return q,es


def finite_case(a, data, result):
    probs=[F(row['probability']) for row in data['states']]
    names=[row['id'] for row in data['states']]
    holdings=list(map(F,data['holdings']))
    matrix=[list(map(F,row['losses'])) for row in data['states']]
    alpha=F(data['confidence'])
    a.eq((result['id'],F(result['confidence'])),(data['id'],alpha),'case identity and exact confidence')
    a.eq(set(result['held_components']),set(data['assets']),'all held components returned')
    values=[]
    for j,asset in enumerate(data['assets']):
        values.append(risk_certificate(a,result['held_components'][asset],
                       [holdings[j]*row[j] for row in matrix],probs,alpha,names))
    combined=[sum(row[j]*holdings[j] for j in range(len(holdings))) for row in matrix]
    q,es=risk_certificate(a,result['portfolio'],combined,probs,alpha,names)
    a.eq((F(result['sum_component_var']),F(result['sum_component_es'])),
         (sum(x[0] for x in values),sum(x[1] for x in values)),'same-law component risk sums')
    a.eq(es<=sum(x[1] for x in values),True,'same-law finite subadditivity')
    return q,es


def normal_quantile(alpha):
    # Newton iteration on the upper tail avoids cancellation near confidence1.
    target=float(1-F(alpha));z=0.0
    for _ in range(40):
        density=math.exp(-z*z/2)/math.sqrt(2*math.pi)
        step=(math.erfc(z/math.sqrt(2))/2-target)/density
        z+=step
        if abs(step)<1e-14:break
    return z


def horizon_certificate(a, data, result):
    n,rho=data['days'],F(data['lag_correlation'])
    sd,mu=F(data['daily_sd_loss']),F(data['daily_mean_loss'])
    # Stationary AR1 represented by independent unit-variance innovations:
    # sum X has loading g_n on its stationary start and sqrt(1-rho^2) g_m
    # on each later innovation. Squares sum to variance, independently of
    # both the candidate's lag-count and author's full-matrix formulas.
    geometric=lambda m:(1-rho**m)/(1-rho)
    factor=geometric(n)**2+(1-rho*rho)*sum(geometric(m)**2 for m in range(1,n))
    variance=sd*sd*factor;mean=n*mu
    a.eq((F(result['mean']),F(result['variance']),F(result['variance_factor'])),(mean,variance,factor),'independent innovation-loading variance')
    a.eq(F(result['iid_variance']),n*sd*sd,'uncorrelated variance comparator')
    z=normal_quantile(data['confidence']);sigma=math.sqrt(float(variance))
    a.near(result['sd_approx'],sigma,'horizon standard deviation')
    a.near(result['normal_var_approx'],float(mean)+sigma*z,'normal tail inversion')
    a.near(result['normal_es_approx'],float(mean)+sigma*math.exp(-z*z/2)/math.sqrt(2*math.pi)/float(1-F(data['confidence'])),'normal first-tail moment')


def count_tail(n,p,k):
    """High-precision positive term recurrence; no binomial coefficients or convolution."""
    with localcontext() as ctx:
        ctx.prec=90
        p=Decimal(p);q=1-p
        term=q**n;answer=term if k==0 else Decimal(0)
        for j in range(n):
            term=term*Decimal(n-j)*p/(Decimal(j+1)*q)
            if j+1>=k:answer+=term
        return +answer


def backtest_certificate(a, data, result):
    positions=data['exception_positions'];n=data['trials'];k=len(positions)
    probability=count_tail(n,data['exception_probability'],k)
    a.eq((result['trials'],result['exceptions'],F(result['expected_exceptions'])),
         (n,k,n*F(data['exception_probability'])),'count and expectation')
    a.near(result['one_sided_count_probability_approx'],float(probability),'independent count recurrence',2e-14)
    groups={}
    for index,day in enumerate(positions):groups[day-index]=groups.get(day-index,0)+1
    a.eq((result['longest_exception_run'],result['adjacent_exception_pairs']),
         (max(groups.values(),default=0),sum(length-1 for length in groups.values())),'run groups from exception-date gaps')
    return probability


def decimal(value):
    value=F(value)
    with localcontext() as ctx:
        ctx.prec=30
        return format(Decimal(value.numerator)/Decimal(value.denominator),'f')


def check():
    a=Audit();data=json.loads((ASSETS/'v11-c04-inputs.json').read_text())
    capture=StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        # Only this public candidate API is executed. The author checker and
        # all candidate helpers are excluded from every independent oracle.
        namespace=runpy.run_path(str(ASSETS/'v11-c04-analysis.py'))
        original=deepcopy(data);out=namespace['run'](data)
    a.eq(capture.getvalue(),'','quiet import/run API')
    a.eq(data,original,'candidate does not mutate input')
    a.eq(out,json.loads((ASSETS/'v11-c04-output.json').read_text()),'entire saved output')
    json.dumps(out,allow_nan=False)
    a.eq(len(out['cases']),len(data['cases']),'all baseline cases')
    baseline=[finite_case(a,c,r) for c,r in zip(data['cases'],out['cases'])]
    a.eq(baseline,[(F(10),F(70)),(F(100),F(516,5)),(F(100),F(612,5)),(F(0),F(160))],'reconstructed worked tails')
    horizon_certificate(a,data['horizon'],out['horizon'])
    backtest_certificate(a,data['backtest'],out['backtest'])
    changed=[]
    def add(case,label):case['id']=label;changed.append(case)
    case=deepcopy(data['cases'][0]);case['confidence']='0.9'
    for row,loss,p in zip(case['states'],('-5','20','80'),('0.8','0.15','0.05')):row.update(losses=[loss],probability=p)
    add(case,'exercise_atom')
    for alpha,label in (('0.9499999999','below_boundary'),('0.95','at_boundary'),('0.9500000001','above_boundary')):
        case=deepcopy(data['cases'][0]);case['confidence']=alpha;add(case,label)
    case=deepcopy(data['cases'][0])
    for row in case['states']:row['losses']=[str(2*int(row['losses'][0])+7)]
    add(case,'affine_loss')
    case=deepcopy(data['cases'][0]);case['holdings']=['-1'];add(case,'short_loss')
    case=deepcopy(data['cases'][1]);case['holdings']=['1.25','-0.75'];add(case,'signed_holdings')
    case=deepcopy(data['cases'][0]);case['states'][-1]['probability']='0.02'
    extra=deepcopy(case['states'][-1]);extra.update(id='split_severe',probability='0.03')
    case['states'].insert(0,extra);add(case,'split_and_reorder_atom')
    # Evaluate a batch within the candidate's eight-case limit.
    variant=deepcopy(data);variant['cases']=changed;result=namespace['run'](variant)
    new={}
    for case,item in zip(changed,result['cases']):new[case['id']]=finite_case(a,case,item);a.interventions+=1
    a.eq(new['exercise_atom'],(F(20),F(50)),'fresh signed atom exercise')
    a.eq([new[name][0] for name in ('below_boundary','at_boundary','above_boundary')],[F(10),F(10),F(100)],'ten-decimal quantile jump')
    a.eq((new['affine_loss'],new['short_loss'],new['split_and_reorder_atom']),
         ((F(27),F(147)),(F(0),F(0)),(F(10),F(70))),'affine/sign/atom splitting transfer')
    half=deepcopy(data['cases'][1]);half['id']='half_common';p=F(1,25);lam=F(1,2)
    law=[lam*(1-p)+(1-lam)*(1-p)**2,(1-lam)*p*(1-p),(1-lam)*p*(1-p),lam*p+(1-lam)*p*p]
    for row,prob in zip(half['states'],law):row['probability']=decimal(prob)
    offset=deepcopy(data['cases'][3]);offset['id']='exact_offset';offset['holdings']=['1','-1']
    gain=deepcopy(data['cases'][0]);gain['id']='constant_gain'
    for row in gain['states']:row['losses']=['-7']
    variant=deepcopy(data);variant['cases']=[half,offset,gain];result=namespace['run'](variant)
    risks=[finite_case(a,c,r) for c,r in zip(variant['cases'],result['cases'])];a.interventions+=3
    a.eq(risks,[(F(100),F(708,5)),(F(0),F(0)),(F(-7),F(-7))],'same marginals, hedged and all-gain laws')
    a.eq((sum(law),law[1]+law[3],law[2]+law[3],(law[3]-p*p)/(p*(1-p))),
         (F(1),p,p,lam),'mixture keeps marginal law and stipulated correlation')
    horizon_changes=[{'days':3,'daily_mean_loss':'1','lag_correlation':'0.5','confidence':'0.975'},
                     {'days':4,'daily_mean_loss':'-0.25','daily_sd_loss':'3','lag_correlation':'-0.5','confidence':'0.9'},
                     {'days':7,'daily_mean_loss':'-0.25','daily_sd_loss':'0','confidence':'0.9999'},
                     {'days':1,'daily_mean_loss':'1','lag_correlation':'0.9'},
                     {'lag_correlation':'0'}]
    for change in horizon_changes:
        variant=deepcopy(data);variant['horizon'].update(change);result=namespace['run'](variant)
        horizon_certificate(a,variant['horizon'],result['horizon']);a.interventions+=1
    backtest_changes=[{'exception_positions':[20,50,80,110,140,170,200]},
                      {'trials':100,'exception_positions':[]},
                      {'trials':8,'exception_probability':'0.2','exception_positions':[2,3,7]},
                      {'trials':500,'exception_probability':'0.0000000001','exception_positions':list(range(1,501))}]
    for change in backtest_changes:
        variant=deepcopy(data);variant['backtest'].update(change);result=namespace['run'](variant)
        positive=backtest_certificate(a,variant['backtest'],result['backtest']);a.interventions+=1
        if variant['backtest']['trials']==500:
            a.eq(positive>0,True,'underflow event remains mathematically possible')
            a.eq(result['backtest']['one_sided_count_probability_approx'],0.0,'documented floating underflow, not impossibility')
    # Exact manuscript arithmetic independent of the candidate's risk routine.
    for shock in (F(1,20),F(-3,100),F(-1,20)):
        full=F(100)/F(21,20)-F(100)/(F(21,20)+shock)
        linear=100*shock/F(21,20)**2
        a.eq(full-linear,-100*shock*shock/(F(21,20)**2*(F(21,20)+shock)),'dated bond nonlinear remainder')
    a.eq((F(100)/F(21,20)-F(100)/F(11,10),F(100)/F(21,20)-F(100)/F(51,50)),
         (F(1000,231),F(-1000,357)),'worked and new exercise bond cash')
    for theta in (F(-2),F(0),F(7),F(10),F(33),F(100),F(120)):
        f=theta+sum(p*max(x-theta,0) for p,x in ((F(9,10),0),(F(1,20),10),(F(1,20),100)))/F(1,10)
        expected=55-9*theta if theta<0 else F(55) if theta<=10 else 50+theta/2 if theta<=100 else theta
        a.eq(f,expected,'all four threshold-function pieces')
    a.eq(sum(w*x for w,x in zip((F(0),F(1,2),F(1,2)),(0,10,100))),55,'suboptimal feasible dual vector')
    a.eq(F(99,100)**100>F(36,100),True,'zero exceptions are compatible with null')
    a.near(float(F(99,100)**100),0.3660323412732295,'zero-count event probability')
    a.eq((250-7+1)*F(1,100)**7,F(244,10**14),'predeclared run union bound')
    a.near(3+1.959963985*math.sqrt(22),12.19305,'exercise rounded normal VaR',1e-6)
    a.near(3+math.sqrt(22)*0.058445070/0.025,13.96527,'exercise corrected rounded ES',1e-6)
    a.near(2*math.sqrt(20),8.94427190999916,'finite Pareto mean-tail anchor')
    # The positive coefficient multiplies a growing cutoff power R^(1/5)
    # for kappa=.8; the limiting argument is reviewed in the peer proof record.
    a.eq(F(4,5)/(1-F(4,5)),F(4),'Pareto divergent-power coefficient')
    invalid=[]
    def bad(path,value):
        item=deepcopy(data);target=item
        for part in path[:-1]:target=target[part]
        target[path[-1]]=value;invalid.append(item)
    for value in (0.95,True,'NaN','1/2','1e-1','0.95000000001',' 0.95','1','0'):
        bad(('cases',0,'confidence'),value)
    for path,value in ((('schema',),True),(('cases',),[]),(('cases',1,'id'),'atom'),
                       (('cases',0,'holdings'),['11']),(('cases',0,'states',0,'probability'),'0'),
                       (('cases',0,'states',0,'probability'),'0.8'),(('cases',0,'states',0,'losses'),[False]),
                       (('horizon','days'),True),(('horizon','lag_correlation'),'-1'),(('horizon','daily_sd_loss'),'-1'),
                       (('backtest','exception_probability'),'1'),(('backtest','exception_positions'),[2,1]),
                       (('backtest','exception_positions'),[40,40]),(('backtest','exception_positions'),[251])):
        bad(path,value)
    for item in invalid:
        try:namespace['run'](item)
        except ValueError:a.rejections+=1
        else:raise AssertionError('Invalid public API input accepted')
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary);script=folder/'v11-c04-analysis.py';source=folder/'v11-c04-inputs.json'
        shutil.copy2(ASSETS/script.name,script);source.write_text(json.dumps(data))
        for flag in ([],['-O']):
            command=[sys.executable,*flag]
            ordinary=subprocess.run(command+[str(script)],cwd='/',capture_output=True,text=True,timeout=20)
            a.eq((ordinary.returncode,ordinary.stderr),(0,''),'isolated default CLI')
            a.eq(json.loads(ordinary.stdout),out,'isolated complete default result')
            destination=folder/'result.json'
            explicit=subprocess.run(command+[str(script),'--input',str(source),'--output',str(destination)],cwd='/',capture_output=True,text=True,timeout=20)
            a.eq((explicit.returncode,explicit.stdout,explicit.stderr),(0,'',''),'isolated explicit quiet CLI')
            a.eq(json.loads(destination.read_text()),out,'isolated complete explicit result')
            api="import contextlib,io,json,runpy; capture=io.StringIO();\nwith contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):\n model=runpy.run_path('v11-c04-analysis.py');data=json.load(open('v11-c04-inputs.json'));before=json.dumps(data,sort_keys=True);result=model['run'](data)\nif capture.getvalue() or json.dumps(data,sort_keys=True)!=before:raise RuntimeError('noise or mutation')\nprint(json.dumps(result,allow_nan=False))"
            process=subprocess.run(command+['-c',api],cwd=folder,capture_output=True,text=True,timeout=20)
            a.eq((process.returncode,process.stderr),(0,''),'isolated quiet nonmutating API')
            a.eq(json.loads(process.stdout),out,'isolated API strict JSON result')
            for malformed in ('{','{"schema":1,"schema":1}','{"schema":NaN}','{"schema":Infinity}',json.dumps(invalid[0])):
                badpath=folder/'bad.json';badpath.write_text(malformed);destination.write_text('keep')
                process=subprocess.run(command+[str(script),'--input',str(badpath),'--output',str(destination)],cwd='/',capture_output=True,text=True,timeout=20)
                require(process.returncode==2 and destination.read_text()=='keep','invalid CLI changed existing output');a.rejections+=1
            for target in (source,script):
                before=target.read_bytes();alias=folder/('hardlink_'+target.name);os.link(target,alias)
                try:
                    for output in (target,alias):
                        process=subprocess.run(command+[str(script),'--output',str(output)],cwd='/',capture_output=True,text=True,timeout=20)
                        a.eq((process.returncode,target.read_bytes()==before),(2,True),'samefile protection preserves original bytes')
                finally:alias.unlink()
    record=json.loads(REVIEW.read_text())
    paired_solutions(a,record)
    a.eq(len(record['reviewed_hashes']),9,'nine frozen author payloads')
    for row in record['reviewed_hashes']+[record['checker']]:
        payload=(ROOT/row['path']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'exact peer payload binding')
    manifest=json.loads((ASSETS/'v11-c04-manifest.json').read_text())
    a.eq(len(manifest['files']),4,'four portable payloads')
    for row in manifest['files']:
        payload=(ASSETS/row['file']).read_bytes()
        a.eq((len(payload),sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'author manifest independently bound')
    return {'chapter':'v11-c04','status':'passed','comparisons':a.comparisons,
            'financial_interventions':a.interventions,'invalid_inputs_rejected':a.rejections,
            'author_payloads_bound':9,'worked_examples_reviewed':5,'exact_exercises_reviewed':10,
            'limits':'Independent finite mathematics and bounded implementation audit; no empirical law, liquidity guarantee or actual risk permission. Canonical acceptance remains with the coordinator.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
