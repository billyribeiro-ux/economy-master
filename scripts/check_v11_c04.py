"""Independent finite-risk certificates, cash arithmetic and bounded lab checks."""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects'
MODEL = PROJECT / 'v11-c04-analysis.py'
COUNT = 0


def need(condition, label):
    global COUNT
    COUNT += 1
    if not condition:
        raise RuntimeError(label)


def eq(actual, expected, label):
    need(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))


def near(actual, expected, label, tolerance=1e-9):
    need(math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance), label)


def vertices(losses, probs, alpha):
    """Enumerate capped-simplex vertices: every coordinate but one is at a bound.

    Independent oracle, no sorting/tail-filling or model helpers. A linear
    maximum over this nonempty compact polytope is attained at such a vertex.
    Equal optima are allowed. Cases here have at most four states.
    """
    caps = [p / (1-alpha) for p in probs]
    values = []
    for free in range(len(losses)):
        fixed = [i for i in range(len(losses)) if i != free]
        for bits in product((0, 1), repeat=len(fixed)):
            weights = [F(0)] * len(losses)
            for i, bit in zip(fixed, bits):
                weights[i] = bit * caps[i]
            weights[free] = 1-sum(weights)
            if 0 <= weights[free] <= caps[free]:
                values.append(sum(w*l for w, l in zip(weights, losses)))
    need(bool(values), 'nonempty independent dual vertex set')
    return max(values)


def risk_oracle(result, losses, probs, alpha, names):
    levels = set(losses)
    q = min(level for level in levels if sum(p for p, l in zip(probs, losses) if l <= level) >= alpha)
    es = vertices(losses, probs, alpha)
    candidates = levels | {min(levels)-2, max(levels)+2}
    minimum = min(theta + sum(p * max(l-theta, 0) for p, l in zip(probs, losses))/(1-alpha) for theta in candidates)
    eq(es, minimum, 'dual vertex maximum equals convex threshold minimum')
    eq(F(result['var']), q, 'left CDF quantile')
    eq(F(result['es']), es, 'independent dual ES')
    eq(F(result['positive_part_objective_at_var']), es, 'reported threshold certificate')
    eq(F(result['mean']), sum(p*l for p, l in zip(probs, losses)), 'direct expectation')
    pair_variance = sum(p*r*(l-m)**2 for p, l in zip(probs, losses) for r, m in zip(probs, losses))/2
    eq(F(result['variance']), pair_variance, 'pair-difference variance')
    strict = sum(p for p, l in zip(probs, losses) if l > q)
    weak = sum(p for p, l in zip(probs, losses) if l >= q)
    eq(F(result['strict_exceedance_probability']), strict, 'strict tail probability')
    strict_mean = None if strict == 0 else str(sum(p*l for p, l in zip(probs, losses) if l > q)/strict)
    eq(result['strict_tail_mean'], strict_mean, 'strict conditional mean')
    eq(F(result['weak_tail_mean']), sum(p*l for p, l in zip(probs, losses) if l >= q)/weak, 'weak conditional mean')
    allocations = result['tail_allocation']
    eq([row['state'] for row in allocations], names, 'all original state IDs')
    for row, p, l in zip(allocations, probs, losses):
        eq((F(row['available_probability']), F(row['loss'])), (p, l), 'certificate original law')
        mass, weight = F(row['selected_probability']), F(row['dual_weight'])
        need(0 <= mass <= p and weight == mass/(1-alpha), 'dual capacity and mass relation')
        eq(F(row['es_contribution']), weight*l, 'weighted loss contribution')
    eq(sum(F(row['selected_probability']) for row in allocations), 1-alpha, 'tail mass exactly filled')
    eq(sum(F(row['dual_weight']) for row in allocations), 1, 'dual normalized')
    eq(sum(F(row['es_contribution']) for row in allocations), es, 'attaining certificate')


def case_oracle(case, result):
    probs = [F(row['probability']) for row in case['states']]
    names = [row['id'] for row in case['states']]
    holdings = list(map(F, case['holdings']))
    matrix = [list(map(F, row['losses'])) for row in case['states']]
    alpha = F(case['confidence'])
    components = []
    for j, (name, weight) in enumerate(zip(case['assets'], holdings)):
        loss = [weight * row[j] for row in matrix]
        item = result['held_components'][name]
        risk_oracle(item, loss, probs, alpha, names)
        components.append(item)
    portfolio = [sum(row[j]*holdings[j] for j in range(len(holdings))) for row in matrix]
    risk_oracle(result['portfolio'], portfolio, probs, alpha, names)
    eq(F(result['sum_component_var']), sum(F(x['var']) for x in components), 'component VaR sum')
    eq(F(result['sum_component_es']), sum(F(x['es']) for x in components), 'component ES sum')
    need(F(result['portfolio']['es']) <= F(result['sum_component_es']), 'common-law ES subadditivity')


def horizon_oracle(inp, out):
    h, rho = inp['days'], F(inp['lag_correlation'])
    # Full covariance matrix summation, not the model's lag-count formula.
    variance = F(inp['daily_sd_loss'])**2 * sum(rho**abs(i-j) for i in range(h) for j in range(h))
    mean = h * F(inp['daily_mean_loss'])
    eq(F(out['variance']), variance, 'full serial covariance matrix')
    eq(F(out['mean']), mean, 'additive expected loss')
    near(out['sd_approx']**2, float(variance), 'horizon standard deviation')
    alpha = float(F(inp['confidence']))
    # Invert erf by bisection independently of NormalDist.inv_cdf.
    low, high = -9., 9.
    for _ in range(80):
        middle = (low+high)/2
        if (1+math.erf(middle/math.sqrt(2)))/2 < alpha:
            low = middle
        else:
            high = middle
    z = (low+high)/2
    near(out['normal_var_approx'], float(mean)+math.sqrt(float(variance))*z, 'independent normal quantile')
    # Integral of x*phi(x) from z equals phi(z), proved in the manuscript.
    near(out['normal_es_approx'], float(mean)+math.sqrt(float(variance))*math.exp(-z*z/2)/math.sqrt(2*math.pi)/(1-alpha), 'normal tail integral')


def backtest_oracle(inp, out):
    n, p = inp['trials'], F(inp['exception_probability'])
    k = len(inp['exception_positions'])
    # Independent finite probability convolution, no binomial coefficient.
    law = [F(1)]
    for _ in range(n):
        nxt = [F(0)] * (len(law)+1)
        for j, value in enumerate(law):
            nxt[j] += value*(1-p)
            nxt[j+1] += value*p
        law = nxt
    eq(sum(law), 1, 'convolved count probability law')
    near(out['one_sided_count_probability_approx'], float(sum(law[k:])), 'independent binomial convolution')
    eq(F(out['expected_exceptions']), n*p, 'expected exception count')


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.examples=0; self.solutions=0; self.exercises=0; self.in_exercises=False; self.sources=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if a.get('class')=='worked':self.examples+=1
        if a.get('class')=='solution':self.solutions+=1
        if tag=='ol' and a.get('class')=='exercises':self.in_exercises=True
        if tag=='li' and self.in_exercises:self.exercises+=1
        if 'data-source' in a:self.sources.append(a['data-source'])
    def handle_endtag(self, tag):
        if tag=='ol':self.in_exercises=False


def check():
    global COUNT
    COUNT=0
    spec=importlib.util.spec_from_file_location('v11c04candidate', MODEL)
    model=importlib.util.module_from_spec(spec)
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):spec.loader.exec_module(model)
    eq(stream.getvalue(), '', 'quiet import')
    data=json.loads((PROJECT/'v11-c04-inputs.json').read_text())
    original=copy.deepcopy(data)
    with contextlib.redirect_stdout(stream):baseline=model.run(data)
    eq(stream.getvalue(), '', 'quiet API')
    eq(data, original, 'nonmutating API')
    eq(baseline, json.loads((PROJECT/'v11-c04-output.json').read_text()), 'exact saved output')
    json.dumps(baseline, allow_nan=False)
    for case, result in zip(data['cases'], baseline['cases']):case_oracle(case, result)
    horizon_oracle(data['horizon'], baseline['horizon'])
    backtest_oracle(data['backtest'], baseline['backtest'])
    eq([(x['portfolio']['var'],x['portfolio']['es']) for x in baseline['cases']], [('10','70'),('100','516/5'),('100','612/5'),('0','160')], 'independent published anchors')
    eq((baseline['backtest']['longest_exception_run'],baseline['backtest']['adjacent_exception_pairs']), (7,6), 'clustered history')

    variants=[]
    def one(case, label):
        d=copy.deepcopy(data);d['cases']=[case];variants.append((label,d))
    for alpha in ['0.9','0.95','0.9501']:
        case=copy.deepcopy(data['cases'][0]);case['confidence']=alpha;one(case,'CDF boundary '+alpha)
    case=copy.deepcopy(data['cases'][0]);case['confidence']='0.9'
    for row, p, loss in zip(case['states'],['0.8','0.15','0.05'],['-5','20','80']):row.update(probability=p,losses=[loss])
    one(case,'new signed loss atom')
    case=copy.deepcopy(data['cases'][0])
    for row in case['states']:row['losses']=[str(2*int(row['losses'][0])+7)]
    one(case,'positive affine loss')
    case=copy.deepcopy(data['cases'][0]);case['holdings']=['-1'];one(case,'short position')
    case=copy.deepcopy(data['cases'][0])
    for row in case['states']:row['losses']=['-5']
    one(case,'constant gain')
    case=copy.deepcopy(data['cases'][0]);case['states'][-1]['probability']='0.025';extra=copy.deepcopy(case['states'][-1]);extra['id']='severe_split';case['states'].append(extra);one(case,'split probability atom')
    case=copy.deepcopy(data['cases'][1]);case['states'].reverse();one(case,'reordered tied losses')
    case=copy.deepcopy(data['cases'][1]);case['holdings']=['1','-1'];one(case,'signed spread')
    case=copy.deepcopy(data['cases'][3]);case['holdings']=['1','-1'];one(case,'statewise exact offset')
    case=copy.deepcopy(data['cases'][2])
    for row,p in zip(case['states'],['0.9408','0.0192','0.0192','0.0208']):row['probability']=p
    one(case,'half common-event mixture')
    for label, variant in variants:
        result=model.run(variant)
        case_oracle(variant['cases'][0],result['cases'][0])
        eq(result['horizon'],baseline['horizon'],label+' leaves separate horizon diagnostic unchanged')
    for changes in [dict(days=1),dict(lag_correlation='0'),dict(days=3,lag_correlation='-0.5'),dict(days=3,daily_mean_loss='1',daily_sd_loss='0'),dict(days=3,lag_correlation='0.5',daily_mean_loss='1',confidence='0.975')]:
        variant=copy.deepcopy(data);variant['horizon'].update(changes);result=model.run(variant)
        horizon_oracle(variant['horizon'],result['horizon'])
        eq(result['cases'],baseline['cases'],'horizon does not modify stipulated finite laws')
    dispersed=copy.deepcopy(data);dispersed['backtest']['exception_positions']=[20,50,80,110,140,170,200];result=model.run(dispersed)
    eq(result['backtest']['one_sided_count_probability_approx'],baseline['backtest']['one_sided_count_probability_approx'],'same count different dates')
    eq((result['backtest']['longest_exception_run'],result['backtest']['adjacent_exception_pairs']),(1,0),'dispersed run diagnosis')
    for positions in [[],list(range(1,11))]:
        variant=copy.deepcopy(data);variant['backtest'].update(trials=10,exception_positions=positions)
        result=model.run(variant);backtest_oracle(variant['backtest'],result['backtest'])

    # Determinate manuscript examples and solution anchors, from exact cash laws.
    eq(F(100)/F('1.05')-F(100)/F('1.10'),F(1000,231),'worked bond funded loss')
    eq(F(100)/F('1.05')**2*F('.05'),F(2000,441),'worked bond approximation')
    exact=F(100)/F('1.05')-F(100)/F('1.02');linear=F(100)/F('1.05')**2*F('-.03')
    eq((exact,linear,exact-linear),(F(-1000,357),F(-400,147),F(-200,2499)),'exercise6 full dated revaluation')
    for theta in [F(-5),F(0),F(2),F(10),F(20),F(100),F(110)]:
        objective=theta+sum(p*max(l-theta,0) for p,l in zip(map(F,['.9','.05','.05']),map(F,[0,10,100])))/F('.1')
        piece=55-9*theta if theta<0 else 55 if theta<=10 else 50+theta/2 if theta<=100 else theta
        eq(objective,piece,'exercise2 full convex pieces')
    eq(sum(w*l for w,l in zip([F(0),F(1,3),F(2,3)],[0,10,100])),70,'dual attaining weights')
    eq((F('.0208')-F('.04')**2)/(F('.04')*F('.96')),F('.5'),'exercise4 mixture correlation')
    near(2*math.sqrt(20),8.94427190999916,'Pareto finite mean tail')
    near(float(F('.99')**100),.3660323412732295,'zero exceptions probability')
    eq(244*F('.01')**7,F('0.00000000000244'),'run union bound')

    invalid=[]
    def bad(label, change):
        d=copy.deepcopy(data);change(d);invalid.append((label,d))
    bad('unknown top field',lambda d:d.update(unknown=1))
    bad('schema Boolean',lambda d:d.update(schema=True))
    bad('empty cases',lambda d:d.update(cases=[]))
    bad('duplicate case',lambda d:d['cases'].append(copy.deepcopy(d['cases'][0])))
    bad('invalid ID',lambda d:d['cases'][0].update(id='../case'))
    bad('empty assets',lambda d:d['cases'][0].update(assets=[]))
    bad('duplicate asset',lambda d:d['cases'][1].update(assets=['A','A']))
    bad('holdings dimension',lambda d:d['cases'][0].update(holdings=[]))
    bad('holding bound',lambda d:d['cases'][0].update(holdings=['11']))
    bad('numeric float',lambda d:d['cases'][0].update(confidence=.95))
    bad('nonfinite input',lambda d:d['cases'][0].update(confidence='NaN'))
    bad('fraction literal',lambda d:d['cases'][0].update(confidence='19/20'))
    bad('confidence zero',lambda d:d['cases'][0].update(confidence='0'))
    bad('confidence one',lambda d:d['cases'][0].update(confidence='1'))
    bad('empty states',lambda d:d['cases'][0].update(states=[]))
    bad('duplicate state',lambda d:d['cases'][0]['states'][1].update(id='ordinary'))
    bad('negative probability',lambda d:d['cases'][0]['states'][0].update(probability='-0.1'))
    bad('zero probability',lambda d:d['cases'][0]['states'][0].update(probability='0'))
    bad('probability sum',lambda d:d['cases'][0]['states'][0].update(probability='0.8'))
    bad('loss dimension',lambda d:d['cases'][0]['states'][0].update(losses=['0','0']))
    bad('loss bound',lambda d:d['cases'][0]['states'][0].update(losses=['1000001']))
    bad('loss Boolean',lambda d:d['cases'][0]['states'][0].update(losses=[True]))
    bad('days Boolean',lambda d:d['horizon'].update(days=True))
    bad('day bound',lambda d:d['horizon'].update(days=251))
    bad('negative SD',lambda d:d['horizon'].update(daily_sd_loss='-1'))
    bad('correlation endpoint',lambda d:d['horizon'].update(lag_correlation='1'))
    bad('negative correlation endpoint',lambda d:d['horizon'].update(lag_correlation='-1'))
    bad('normal confidence bound',lambda d:d['horizon'].update(confidence='0.99999'))
    bad('trials bound',lambda d:d['backtest'].update(trials=501))
    bad('null probability endpoint',lambda d:d['backtest'].update(exception_probability='1'))
    bad('position order',lambda d:d['backtest'].update(exception_positions=[2,1]))
    bad('position duplicate',lambda d:d['backtest'].update(exception_positions=[1,1]))
    bad('position Boolean',lambda d:d['backtest'].update(exception_positions=[True]))
    bad('position bounds',lambda d:d['backtest'].update(exception_positions=[251]))
    for label, value in invalid:
        try:model.run(value)
        except ValueError:pass
        else:raise RuntimeError('Accepted invalid input: '+label)

    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);local=folder/MODEL.name;local.write_bytes(MODEL.read_bytes())
        source=folder/'v11-c04-inputs.json';source.write_text(json.dumps(data))
        destination=folder/'result.json'
        for flags in ([],['-O']):
            p=subprocess.run([sys.executable,*flags,str(local)],cwd='/',capture_output=True,text=True,check=True)
            eq(json.loads(p.stdout),baseline,'portable default CLI');eq(p.stderr,'','quiet successful stderr')
            subprocess.run([sys.executable,*flags,str(local),'--input',str(source),'--output',str(destination)],cwd='/',capture_output=True,text=True,check=True)
            eq(json.loads(destination.read_text()),baseline,'portable explicit CLI')
            for target in [source,local]:
                before=target.read_bytes()
                p=subprocess.run([sys.executable,*flags,str(local),'--output',str(target)],cwd='/',capture_output=True,text=True)
                eq(p.returncode,2,'reject protected overwrite');eq(target.read_bytes(),before,'protected original preserved')
                alias=folder/('alias-'+target.name)
                os.link(target,alias)
                p=subprocess.run([sys.executable,*flags,str(local),'--output',str(alias)],cwd='/',capture_output=True,text=True)
                eq(p.returncode,2,'reject hard-link overwrite');eq(target.read_bytes(),before,'aliased original preserved')
                alias.unlink()
            for content in ['{"schema":1,"schema":1}', '{"schema":NaN}', json.dumps(invalid[18][1])]:
                badfile=folder/'bad.json';badfile.write_text(content);destination.write_text('preserve me')
                p=subprocess.run([sys.executable,*flags,str(local),'--input',str(badfile),'--output',str(destination)],cwd='/',capture_output=True,text=True)
                eq(p.returncode,2,'strict malformed CLI rejection');eq(destination.read_text(),'preserve me','invalid input leaves prior output')

    chapter=Chapter();text=(ROOT/'content/chapters/v11-c04.html').read_text();chapter.feed(text)
    eq((chapter.examples,chapter.exercises),(5,10),'complete worked and exercise counts')
    need(chapter.solutions>=11,'all exercises plus delayed solution')
    eq(len(chapter.ids),len(set(chapter.ids)),'unique chapter anchors')
    eq(set(chapter.sources),{'v11-c04-rockafellar-uryasev'},'scoped source route')
    for marker in ['Teach-back','Delayed check','13.96527','2.44×10','−200/2499']:
        need(marker in text,'reviewed instructional/numerical anchor '+marker)
    manifest_path=PROJECT/'v11-c04-manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        for entry in manifest['files']:
            eq(hashlib.sha256((PROJECT/entry['file']).read_bytes()).hexdigest(),entry['sha256'],'manifest payload')
    author_path=ROOT/'content/reviews/v11-c04-author.json'
    bindings=0
    if author_path.exists():
        for entry in json.loads(author_path.read_text())['reviewed_hashes']:
            eq(hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest(),entry['sha256'],'author payload binding')
            bindings+=1
    return {'chapter':'v11-c04','status':'passed','comparisons':COUNT,'invalid_api_inputs_rejected':len(invalid),
            'financial_interventions':len(variants)+5+3,'worked_examples':5,'solved_exercises':10,
            'author_payload_hashes_verified':bindings,
            'independent_methods':['capped-simplex vertex maximization','piecewise convex threshold minimum','pair-difference variance','full serial covariance matrix and erf-bisection normal quantile','exact Bernoulli polynomial convolution','dated bond cash and finite proof/exercise anchors'],
            'limits':'Author independent calculation and finite domain checks; separate peer/coordinator acceptance, empirical law adequacy and whole-edition UI checks are distinct.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
