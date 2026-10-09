"""Quiet, exact, four-payload author checks for Volume 12 Form B."""
from collections import Counter
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import hashlib
import json
import math

HTML_PATH = 'content/assessments/parts/v12-exam-b.html'
SOURCE_PATH = 'content/reviews/v12-exam-b-sources.json'
AUTHOR_PATH = 'content/reviews/v12-exam-b-author.json'
SELF_PATH = 'scripts/check_v12_exam_b.py'
POINTS = ((6,8,6),(6,6,8),(7,8,5),(6,5,3,6),(5,7,8))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _unique(pairs):
    obj = {}
    for key,value in pairs:
        require(key not in obj, 'duplicate JSON key')
        obj[key] = value
    return obj


def _nonfinite(value):
    raise ValueError('nonfinite JSON: '+value)


def strict_json(text):
    return json.loads(text, object_pairs_hook=_unique, parse_constant=_nonfinite)


def rational(value):
    require(type(value) in (int,F), 'exact integer or Fraction required; booleans/floats excluded')
    require(abs(value) <= 1000000, 'outside bounded arithmetic domain')
    return F(value)


def mean(values):
    require(bool(values), 'empty mean')
    return sum(values,F(0))/len(values)


def variance(values):
    m = mean(values)
    return mean([(x-m)**2 for x in values])


def twfe(d,y):
    require(type(d) in (list,tuple) and 2<=len(d)<=8, 'bounded cohort count')
    require(type(y) in (list,tuple) and len(y)==len(d), 'outcome row count')
    require(type(d[0]) in (list,tuple) and 2<=len(d[0])<=8, 'bounded date count')
    g,t = len(d),len(d[0])
    require(all(type(row) in (list,tuple) and len(row)==t for row in list(d)+list(y)), 'rectangular panel')
    d = [[rational(v) for v in row] for row in d]
    y = [[rational(v) for v in row] for row in y]
    require(all(v in (0,1) for row in d for v in row), 'binary treatment')
    grand = sum(map(sum,d),F(0))/(g*t)
    r = [[d[i][j]-mean(d[i])-mean([d[k][j] for k in range(g)])+grand for j in range(t)] for i in range(g)]
    den = sum(v*v for row in r for v in row)
    require(den>0,'no residual treatment variation')
    beta = sum(r[i][j]*y[i][j] for i in range(g) for j in range(t))/den
    return r,den,beta


def transition(p):
    p = rational(p)
    require(0<p<1, 'turnover probability must lie strictly between zero and one')
    return [[1-p,p],[p,1-p]]


def stop_values(p,discount):
    pmat = transition(p)
    discount = rational(discount)
    require(0<=discount<=1, 'finite-horizon discount in [0,1]')
    values = [[F(0),F(1)]]
    for _ in range(2):
        nxt=values[-1]
        values.append([max(F(0),F(2*i-1),discount*sum(pmat[i][j]*nxt[j] for j in range(2))) for i in range(2)])
    return list(reversed(values))


def bayes(theta,prior,data):
    require(len(theta)==len(prior)==2, 'two-point support')
    theta,prior = [rational(x) for x in theta],[rational(x) for x in prior]
    require(all(0<=x<=1 for x in theta), 'Bernoulli parameter domain')
    require(all(x>=0 for x in prior) and sum(prior)==1, 'proper prior')
    require(type(data) in (tuple,list) and 1<=len(data)<=12, 'bounded nonempty Bernoulli record')
    require(all(type(x) is int and x in (0,1) for x in data), 'binary observed outcomes')
    s=sum(data);f=len(data)-s
    likelihood=[t**s*(1-t)**f for t in theta]
    weights=[a*b for a,b in zip(prior,likelihood)]
    require(sum(weights)>0,'zero prior predictive probability')
    return likelihood,[w/sum(weights) for w in weights]


def mh(target,proposal):
    require(len(target)==2 and len(proposal)==2 and all(len(row)==2 for row in proposal), 'two-state chain')
    target=[rational(x) for x in target]
    proposal=[[rational(x) for x in row] for row in proposal]
    require(all(x>0 for x in target) and sum(target)==1,'strictly positive proper target')
    require(all(x>=0 for row in proposal for x in row) and all(sum(row)==1 for row in proposal),'stochastic proposal')
    p=[[F(0),F(0)],[F(0),F(0)]]
    for i in range(2):
        j=1-i
        p[i][j]=min(proposal[i][j],target[j]*proposal[j][i]/target[i])
        p[i][i]=1-p[i][j]
    return p


def tails(scores,probabilities):
    require(1<=len(scores)<=36 and len(scores)==len(probabilities),'bounded equal tail arrays')
    scores=[rational(x) for x in scores]
    probabilities=[rational(x) for x in probabilities]
    require(all(x>0 for x in probabilities) and sum(probabilities)==1,'positive normalized assignment probabilities')
    return [sum(prob for value,prob in zip(scores,probabilities) if abs(value)>=abs(s)) for s in scores]


def qadd(a,b):
    return a[0]+b[0],a[1]+b[1]


def qmul(a,b):
    return a[0]*b[0]+6*a[1]*b[1],a[0]*b[1]+a[1]*b[0]


def qscale(a,t):
    return a[0]*t,a[1]*t


def radical(a):
    den=math.lcm(a[0].denominator,a[1].denominator)
    whole=int(a[0]*den);root=int(a[1]*den)
    middle=('+' if root>=0 else '−')+str(abs(root))+'√6'
    return '('+str(whole).replace('-','−')+middle+')/'+str(den)


def fmt(value):
    if isinstance(value,(list,tuple)):
        return '('+','.join(fmt(x) for x in value)+')'
    return str(value).replace('-','−')


class Audit:
    def __init__(self):
        self.comparisons=0
        self.rejections=0

    def eq(self,a,b,label):
        require(a==b,'failed '+label+': '+repr(a)+' != '+repr(b))
        self.comparisons+=1

    def reject(self,fn,label):
        try:
            fn()
        except ValueError:
            self.rejections+=1
        else:
            raise ValueError('invalid domain accepted: '+label)


def derive(audit):
    """Independent primitive reconstruction; no exam, blueprint or saved outputs read."""
    inputs={
        'q1-clusters':[[1,0,1],[2,0,3],[3,1,4],[4,3,4]],
        'q2-panel':[['E',2,1,2,5,14],['L',3,3,4,5,10],['N','never',0,1,2,3]],
        'q2-donors':[['B',2,3,7],['C',1,2,4]],
        'q3-nodes':[[1,F(1,8),F(1,8)],[2,F(1,8),F(7,8)],[3,F(7,8),F(1,8)],[4,F(7,8),F(7,8)]],
        'q4-regression':[[1,1,1,3],[2,1,-1,1]],
        'q5-records':[[i+1,chr(65+i//2),int(i//2==3),1000*(0,1,2,7)[i//2]] for i in range(8)],
    }
    constants={'cluster-law':(4,2,4),'normal-cdf':'0.9772498680','turnover':F(1,4),'discount':F(1,2),
               'bayes-theta':(F(1,4),F(3,4)),'bayes-prior':(F(1,2),F(1,2)),
               'bernoulli-record':(1,1,0),'launch-utility':(-4,1),'lasso-lambda':F(1,2)}
    out={}
    xy=[row[1:] for row in inputs['q1-clusters']]
    rx,ry=[mean([F(r[j]) for r in xy]) for j in (0,1)]
    covariance=[[F(4) if i//2==j//2 else F(0) for j in range(8)] for i in range(8)]
    actual_var=sum(map(sum,covariance))/64
    false_var=sum(covariance[i][i] for i in range(8))/64
    audit.eq((actual_var,false_var),(F(1),F(1,2)),'cluster covariance versus row diagonal')
    out['cluster-means']=(rx,ry)
    out['cluster-variances']=(actual_var,false_var)
    coeff=(4-rx*rx,2*rx*ry,4-ry*ry)
    out['candidate-quadratic']=coeff
    roots=((F(-1),F(-2,3)),(F(-1),F(2,3)))
    for root in roots:
        audit.eq(qadd(qadd(qscale(qmul(root,root),coeff[0]),qscale(root,coeff[1])),(coeff[2],F(0))),(F(0),F(0)),'Q(sqrt6) exact roots')
    out['candidate-roots']='('+','.join(radical(x) for x in roots)+')'
    out['theta-bound']=radical(qmul(roots[1],roots[1]))
    for b,accepted in ((F(0),False),(F(3),True),(F(-4),True)):
        audit.eq((ry-b*rx)**2<=4*(1+b*b),accepted,'candidate contrast boundary')
    audit.eq(abs((1+math.erf(math.sqrt(2)))/2-float(constants['normal-cdf']))<1e-10,True,'supplied normal CDF approximation')
    out['confidence-percent']='95.4499736%'
    d=[[0,0,1,1],[0,0,0,1],[0,0,0,0]]
    y=[list(map(F,row[2:])) for row in inputs['q2-panel']]
    residual,norm,beta=twfe(d,y)
    out['twfe-residual']=residual;out['twfe-norm']=norm;out['twfe-estimate']=beta
    out['twfe-inner-products']=[sum(a*b for a,b in zip(r,row)) for r,row in zip(residual,y)]
    weights=[residual[g][t]/norm for g in range(3) for t in range(4) if d[g][t]]
    out['twfe-weights']=weights
    for row in residual:audit.eq(sum(row),0,'cohort orthogonality')
    for t in range(4):audit.eq(sum(residual[g][t] for g in range(3)),0,'date orthogonality')
    audit.eq(sum(weights),1,'treated effect weight sum')
    effects=[(y[0][2]-y[0][1])-(y[2][2]-y[2][1]),(y[0][3]-y[0][1])-(y[2][3]-y[2][1]),(y[1][3]-y[1][2])-(y[2][3]-y[2][2])]
    out['clean-effects']=effects;out['effect-targets']=(mean([effects[0],effects[2]]),mean(effects),beta)
    audit.eq(sum(w*e for w,e in zip(weights,effects)),beta,'FWL and clean effects')
    donor0=[0,2,1];donor1=[1,3,2];post=[3,7,4]
    endpoints=[]
    for t in (F(0),F(1,4),F(1,2)):
        w=(t,t,1-2*t)
        audit.eq(sum(w),1,'simplex sum')
        audit.eq((sum(a*b for a,b in zip(w,donor0)),sum(a*b for a,b in zip(w,donor1))),(F(1),F(2)),'all prefit witnesses')
        cf=sum(a*b for a,b in zip(w,post))
        audit.eq(cf,4+2*t,'post affine map')
        endpoints.append(cf)
    out['donor-cf-bounds']=(min(endpoints),max(endpoints));out['donor-effect-bounds']=(14-max(endpoints),14-min(endpoints))
    p=constants['turnover'];P=transition(p);stationary=(F(1,2),F(1,2))
    for j in range(2):audit.eq(sum(stationary[i]*P[i][j] for i in range(2)),stationary[j],'stationary spread')
    audit.eq(sum(stationary[i]*P[i][1-i] for i in range(2)),p,'population turnover')
    centered=(-1,1)
    for i in range(2):audit.eq(sum(P[i][j]*centered[j] for j in range(2)),(1-2*p)*centered[i],'spread eigenfunction')
    out['spread-moments']=(F(1),F(1),1-2*p)
    values=stop_values(p,constants['discount'])
    out['stopping-values']=values
    policy_mean=F(0)
    terminal_only=F(0)
    path_probs=[]
    for s1,s2 in product(range(2),repeat=2):
        prob=P[0][s1]*P[s1][s2]
        path_probs.append(prob)
        policy_mean+=prob*(F(1,2) if s1 else F(1,4) if s2 else 0)
        terminal_only+=prob*F(s2,4)
    audit.eq(policy_mean,values[0][0],'path enumeration versus Bellman')
    out['state-path-probabilities']=path_probs
    out['starting-values']=(policy_mean,terminal_only)
    node_pay=[]
    for _,u1,u2 in inputs['q3-nodes']:
        s1=int(u1<p);s2=1-s1 if u2<p else s1
        node_pay.append(F(1,2) if s1 else F(1,4) if s2 else F(0))
    out['node-payoffs']=node_pay;out['node-mean-error']=(mean(node_pay),mean(node_pay)-policy_mean)
    audit.eq(mean(node_pay*3),mean(node_pay),'replicated deterministic nodes')
    likelihood,posterior=bayes(constants['bayes-theta'],constants['bayes-prior'],constants['bernoulli-record'])
    out['likelihoods']=likelihood;out['posterior']=posterior
    out['continuous-mle']=F(sum(constants['bernoulli-record']),len(constants['bernoulli-record']))
    th=out['continuous-mle'];audit.eq(2/th-1/(1-th),0,'interior Bernoulli score')
    predictive=sum(a*b for a,b in zip(constants['bayes-theta'],posterior))
    out['posterior-predictive']=predictive
    out['launch-expected']=sum(a*b for a,b in zip(constants['launch-utility'],posterior))
    chain=mh(posterior,[[0,1],[1,0]])
    out['mh-transition']=chain
    audit.eq(posterior[0]*chain[0][1],posterior[1]*chain[1][0],'balanced edge flow')
    for j in range(2):audit.eq(sum(posterior[i]*chain[i][j] for i in range(2)),posterior[j],'MH invariant target')
    out['jump-chain-mean']=mean(list(constants['bayes-theta']))
    vh=posterior[1]*(1-posterior[1]);cov=posterior[1]*chain[1][1]-posterior[1]**2
    average_var=sum(posterior[i]*chain[i][j]*(F(i+j,2)-posterior[1])**2 for i,j in product(range(2),repeat=2))
    audit.eq(average_var,(2*vh+2*cov)/4,'stationary path versus covariance variance')
    out['chain-variances']=(vh,cov,average_var,vh/2)
    X=[list(map(F,row[1:3])) for row in inputs['q4-regression']]
    yreg=[F(row[3]) for row in inputs['q4-regression']]
    solutions=[]
    for scale,penw in ((1,(1,1)),(2,(1,1)),(2,(2,1))):
        design=[[scale*row[0],row[1]] for row in X]
        gram=[sum(row[j]**2 for row in design)/2 for j in range(2)]
        score=[sum(design[i][j]*yreg[i] for i in range(2))/2 for j in range(2)]
        b=[max(F(0),score[j]-constants['lasso-lambda']*penw[j])/gram[j] for j in range(2)]
        fit=[sum(a*z for a,z in zip(row,b)) for row in design]
        resid=[a-z for a,z in zip(yreg,fit)]
        kkt=[sum(design[i][j]*resid[i] for i in range(2))/2 for j in range(2)]
        audit.eq(kkt,[constants['lasso-lambda']*x for x in penw],'positive-coordinate weighted KKT')
        objective=sum(e*e for e in resid)/4+constants['lasso-lambda']*sum(w*abs(v) for w,v in zip(penw,b))
        solutions.append((b,fit,objective))
    for label,sol in zip(('original','rescaled','restored'),solutions):out['lasso-'+label]=sol
    audit.eq(solutions[0][1],solutions[2][1],'physical fit restored')
    b=[F(row[3],1000) for row in inputs['q5-records']]
    site_vals=[]
    for g in range(4):
        treated=[b[i] for i in range(8) if i//2==g]
        control=[b[i] for i in range(8) if i//2!=g]
        site_vals.append(mean(treated)-mean(control))
    false_vals=[]
    for pair in combinations(range(8),2):
        false_vals.append(mean([b[i] for i in pair])-mean([b[i] for i in range(8) if i not in pair]))
    site_p=tails(site_vals,[F(1,4)]*4)
    false_p=[F(sum(abs(t)>=abs(value) for t in false_vals),28) for value in site_vals]
    out['site-contrasts']=site_vals;out['site-pvalues']=site_p;out['false-pvalues']=false_p
    out['actual-pair-pvalues']=(site_p[-1],false_p[-1])
    out['reference-sizes']=(F(sum(p<=F(1,20) for p in site_p),4),F(sum(p<=F(1,20) for p in false_p),4))
    for level in sorted(set(site_p)):
        audit.eq(F(sum(p<=level for p in site_p),4)<=level,True,'actual-law inclusive validity')
    global_worlds=[]
    for z in product((0,1),repeat=4):
        w1=b[:];w2=[x+3*int(sum(z)==4) for x in b]
        audit.eq(all(0<=v<=10 for v in w1+w2),True,'complete bounded potential map')
        if sum(z)==1:audit.eq(w1,w2,'full experimental-law equivalence')
        global_worlds.append((z,w1,w2))
    zero=next(row for row in global_worlds if sum(row[0])==0)
    one=next(row for row in global_worlds if sum(row[0])==4)
    out['global-policy-effects']=(mean(one[1])-mean(zero[1]),mean(one[2])-mean(zero[2]))
    # Focused boundary/validation checks, not an arbitrary grid of new exercises.
    shifted=[[v+7 for v in row] for row in y]
    audit.eq(twfe(d,shifted)[2],beta,'common level leaves FWL unchanged')
    audit.eq(stop_values(p,F(0)),[[F(0),F(1)]]*3,'zero-discount finite-horizon boundary')
    uniform_target=[F(1,2),F(1,2)]
    audit.eq(mh(uniform_target,[[0,1],[1,0]]),[[F(0),F(1)],[F(1),F(0)]],'periodic invariant chain is possible')
    audit.eq(tails([F(1),F(-1)],[F(1,2)]*2),[F(1),F(1)],'inclusive equal-magnitude ties')
    for invalid in (True,0.5,float('nan')):audit.reject(lambda invalid=invalid:rational(invalid),'non-exact numeric input')
    audit.reject(lambda:twfe([[0]*4]*3,y),'unidentified FWL denominator')
    audit.reject(lambda:twfe([[0,1],[1,0]],[[1],[2]]),'ragged panel')
    audit.reject(lambda:twfe([[0,2],[1,0]],[[1,2],[3,4]]),'nonbinary treatment')
    for invalid in (F(0),F(1),F(-1,4)):audit.reject(lambda invalid=invalid:transition(invalid),'turnover model domain')
    audit.reject(lambda:stop_values(p,F(3,2)),'discount domain')
    audit.reject(lambda:bayes([F(1,4),F(3,4)],[F(1),F(1)],[1]),'prior normalization')
    audit.reject(lambda:bayes([F(0),F(0)],[F(1,2)]*2,[1]),'impossible data')
    audit.reject(lambda:bayes([F(1,4),F(3,4)],[F(1,2)]*2,[True]),'Boolean data')
    audit.reject(lambda:mh([F(0),F(1)],[[0,1],[1,0]]),'zero target probability outside declared chain')
    audit.reject(lambda:mh([F(1,2)]*2,[[0,F(1,2)],[1,0]]),'nonstochastic proposal')
    audit.reject(lambda:tails([F(1),F(2)],[F(1,4)]*2),'assignment probability mass')
    for bad in ('{"x":1,"x":2}','{"x":NaN}'):
        audit.reject(lambda bad=bad:strict_json(bad),'strict JSON')
    return inputs,constants,out


class Exam(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=[];self.points={};self.targets=[];self.scores={};self.headings={}
        self.tables={};self.inputs={};self.calcs={}
        self.table=None;self.row=None;self.cell=None;self.span=None;self.span_text=[];self.solution=None

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h2' and 'id' in a:self.headings[a['id']]=True
        if 'data-points' in a:
            require(tag=='li' and a.get('id') not in self.points,'scored prompt structure')
            self.points[a['id']]=int(a['data-points'])
        if 'data-solution-for' in a:
            self.solution=a['data-solution-for'];self.targets.append(self.solution)
        if 'data-score' in a:
            require(self.solution is not None and self.solution not in self.scores,'rubric pairing')
            self.scores[self.solution]=[int(x) for x in a['data-score'].split(',')]
        if tag=='table' and 'data-table' in a:
            require(self.table is None,'nested input tables')
            self.table=a['data-table'];require(self.table not in self.tables,'duplicate input table');self.tables[self.table]=[]
        if tag=='tr' and self.table:self.row=[]
        if tag=='td' and self.table:self.cell=[]
        for key,destination in (('data-input',self.inputs),('data-calc',self.calcs)):
            if key in a:
                require(tag=='span' and self.span is None and a[key] not in destination,'numeric span structure')
                self.span=(a[key],destination);self.span_text=[]

    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
        if self.span is not None:self.span_text.append(data)

    def handle_endtag(self,tag):
        if tag=='span' and self.span:
            key,dest=self.span;dest[key]=''.join(self.span_text).strip();self.span=None
        if tag=='td' and self.cell is not None:
            self.row.append(''.join(self.cell).strip());self.cell=None
        if tag=='tr' and self.table and self.row:
            self.tables[self.table].append(self.row);self.row=None
        if tag=='table':self.table=None
        if tag=='li' and self.solution:self.solution=None


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    audit=Audit()
    author=strict_json((root/AUTHOR_PATH).read_text(encoding='utf-8'))
    sources=strict_json((root/SOURCE_PATH).read_text(encoding='utf-8'))
    bindings=author['payload_bindings']
    audit.eq({b['path'] for b in bindings},{HTML_PATH,SELF_PATH,SOURCE_PATH},'three nonself bindings')
    audit.eq(len(bindings),3,'binding cardinality')
    for b in bindings:
        raw=(root/b['path']).read_bytes()
        audit.eq((len(raw),hashlib.sha256(raw).hexdigest()),(b['bytes'],b['sha256']),'bound payload '+b['path'])
    audit.eq(sources['component'],'v12-exam-b','source scope')
    audit.eq(sources['new_primary_body_reads_by_this_author'],0,'honest source attribution')
    inputs,constants,out=derive(audit)
    doc=Exam();doc.feed((root/HTML_PATH).read_text(encoding='utf-8'));doc.close()
    audit.eq(len(doc.ids),len(set(doc.ids)),'unique IDs')
    audit.eq(all(x in ('form-b','solutions-b') or x.startswith('v12-b-') for x in doc.ids),True,'component ID boundary')
    audit.eq(set(doc.headings),{'form-b','solutions-b'},'assembly headings')
    expected={f'v12-b-q{q}{chr(97+i)}':p for q,row in enumerate(POINTS,1) for i,p in enumerate(row)}
    audit.eq(doc.points,expected,'sixteen exact scored prompts')
    audit.eq(doc.targets,list(expected),'sixteen exact solution pairings')
    audit.eq(set(doc.scores),set(expected),'complete explicit rubrics')
    for key,p in expected.items():audit.eq(sum(doc.scores[key]),p,'subpart point sum')
    for q in range(1,6):audit.eq(sum(p for k,p in doc.points.items() if k.startswith(f'v12-b-q{q}')),20,'domain point total')
    audit.eq(sum(doc.points.values()),100,'full examination points')
    audit.eq(set(doc.tables),set(inputs),'input table inventory')
    for key,rows in inputs.items():audit.eq(doc.tables[key],[[fmt(x) for x in row] for row in rows],'primitive reader table '+key)
    audit.eq(doc.inputs,{k:fmt(v) for k,v in constants.items()},'actual supplied scalar/vector inputs')
    audit.eq(set(doc.calcs),set(out),'numerical anchor inventory')
    for key,value in out.items():audit.eq(doc.calcs[key],fmt(value),'visible result '+key)
    result={'component':'v12-exam-b','status':'author checks passed; separate peer pending',
            'comparisons':audit.comparisons,'domain_rejections':audit.rejections,'scored_parts':len(expected),
            'domains':5,'total_points':100,'input_tables':len(inputs),'input_constants':len(constants),
            'visible_result_anchors':len(out),'actual_site_assignments':4,'false_person_assignments':28,
            'complete_policy_maps_checked':16,'runtime_payloads':4}
    json.dumps(result,allow_nan=False)
    return result


if __name__=='__main__':
    check()
