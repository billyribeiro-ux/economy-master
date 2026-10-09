"""Independent finite-contract and reader audit of graduate identification tools.

The general probability proofs are reviewed in the peer record, not established
by finite tests. All arithmetic is reconstructed without author helper calls.
Author check() is additional integration evidence, never a numerical oracle.
"""
import argparse
import contextlib
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import itertools
import json
from math import erf, isfinite, sqrt
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "content/chapters/v12-c01.html",
    "scripts/check_v12_c01.py",
    "content/reviews/v12-c01-sources.json",
    "content/reviews/v12-c01-author.json",
    "scripts/check_v12_c01_peer.py",
    "content/reviews/v12-c01-peer.json")
SOURCES = {"v12-c01-mit-limit-tools", "v12-c01-mit-extremum",
           "v12-c01-mit-delta", "v12-c01-aldous-chewi-cw"}


def require(condition, label):
    if not condition:
        raise ValueError("v12-c01 peer: " + label)


def strict(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def decimal(token):
        value = float(token)
        require(isfinite(value), "nonfinite JSON number")
        return value
    def constant(token):
        raise ValueError("nonfinite JSON constant " + token)
    return json.loads(text, object_pairs_hook=pairs, parse_float=decimal,
                      parse_constant=constant)


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.displays = 0
    def eq(self, actual, expected, label):
        self.comparisons += 1
        if type(expected) is bool:
            require(type(actual) is bool and actual == expected, label)
        else:
            require(actual == expected, label + ": " + repr(actual) + " != " + repr(expected))
    def near(self, actual, expected, tolerance, label):
        self.comparisons += 1
        require(isfinite(actual) and abs(actual-expected) <= tolerance, label)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.lists = []; self.details = []
        self.ids = []; self.links = []; self.sources = []; self.headings = []
        self.worked = 0; self.prompts = []; self.answers = []; self.active = None
        self.text = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); classes = a.get("class", "").split()
        if "id" in a: self.ids.append(a["id"])
        if tag == "a": self.links.append(a.get("href", ""))
        if "data-source" in a: self.sources.append(a["data-source"])
        if tag in ("h1", "h2", "h3", "h4"): self.headings.append(tag)
        if "worked" in classes: self.worked += 1
        if tag == "ol": self.lists.append("exercises" in classes)
        if tag == "details": self.details.append("solutions" in classes)
        if tag == "li":
            require(self.active is None, "no nested scored problem/answer")
            if self.lists and self.lists[-1]:
                self.prompts.append(""); self.active = (self.prompts, len(self.prompts)-1)
            elif any(self.details):
                self.answers.append(""); self.active = (self.answers, len(self.answers)-1)
        if tag not in ("br", "hr", "img", "input", "meta", "link"):
            self.stack.append(tag)
    def handle_data(self, value):
        self.text.append(value)
        if self.active is not None:
            target, index = self.active; target[index] += value
    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1] == tag, "balanced markup " + tag)
        self.stack.pop()
        if tag == "ol": self.lists.pop()
        if tag == "details": self.details.pop()
        if tag == "li": self.active = None


def compact(text):
    return "".join(text.split())


def normal_quantile():
    """Numerical normal-CDF inversion independent of author's NormalDist call."""
    low, high = 1.0, 3.0
    for _ in range(70):
        mid = (low+high)/2
        if (1+erf(mid/sqrt(2)))/2 < .975: low = mid
        else: high = mid
    z = (low+high)/2
    # These are numerical tolerance endpoints, not interval-arithmetic claims.
    return z, F(str(round(z-1e-9, 12))), F(str(round(z+1e-9, 12)))


def count_law(n, p):
    """Rational adjacent-mass recurrence, without factorials or author code."""
    require(type(n) is int and 1 <= n <= 400, "bounded binomial count")
    require(isinstance(p, F) and 0 <= p <= 1, "rational Bernoulli probability")
    if p == 0: return [F(1)] + [F()] * n
    if p == 1: return [F()] * n + [F(1)]
    weights = [(1-p)**n]
    for k in range(n):
        weights.append(weights[-1] * F(n-k, k+1) * p/(1-p))
    return weights


def coverage(n, p, z_low, z_high):
    weights = count_law(n, p); accepted = []
    for k in range(n+1):
        estimate = F(k, n); variance = estimate*(1-estimate)/n
        error2 = (estimate-p)**2
        lower = error2 <= z_low*z_low*variance
        upper = error2 <= z_high*z_high*variance
        require(lower == upper, "count classification sensitive to quantile tolerance")
        if lower: accepted.append(k)
    return sum((weights[k] for k in accepted), F()), accepted, sum(weights)


def independent_arithmetic(a, page):
    text = compact(" ".join(page.text))
    def shown(number, *values):
        body = compact(page.answers[number-1])
        for value in values:
            a.eq(compact(value) in body, True, "solution %d anchor %s" % (number, value))
    def display(printed, value):
        a.eq(printed in text, True, "visible rounded result " + printed)
        a.near(float(printed), value, .50001*10**(-len(printed.split(".")[1])),
               "rounded result " + printed)
        a.displays += 1

    # Enumerate complete one-observation mechanisms by latent type and flag.
    worlds = []
    for theta, alpha, beta in ((F(5, 7), F(1, 10), F(1, 5)),
                               (F(4, 7), F(1, 5), F(1, 10))):
        law = {}
        for late in (0, 1):
            latent = theta if late else 1-theta
            flag_rate = 1-beta if late else alpha
            for flag in (0, 1):
                law[late, flag] = latent*(flag_rate if flag else 1-flag_rate)
        a.eq(sum(law.values()), 1, "normalized latent joint law")
        a.eq(min(law.values()) >= 0, True, "admissible joint cells")
        a.eq(sum(v for (late, flag), v in law.items() if late), theta, "latent estimand")
        a.eq(sum(v for (late, flag), v in law.items() if flag), F(3, 5), "observable flag")
        worlds.append(law)
    for flags in itertools.product((0, 1), repeat=3):
        probabilities = []
        for law in worlds:
            mass = F()
            for latents in itertools.product((0, 1), repeat=3):
                term = F(1)
                for late, flag in zip(latents, flags): term *= law[late, flag]
                mass += term
            probabilities.append(mass)
        a.eq(probabilities[0], probabilities[1], "complete three-flag observable support")
    for law, expected in zip(worlds, ((F(4,7),F(1,7),F(1,35),F(9,35)),
                                      (F(18,35),F(2,35),F(3,35),F(12,35)))):
        cells = tuple(law[x] for x in ((1,1),(1,0),(0,1),(0,0)))
        a.eq(cells, expected, "printed joint cell order")
        shown(1, "("+",".join(str(x) for x in cells)+")")
    # A single explicit path supplies every value of the claimed sharp set.
    p = F(3,5); low = F(9,14); high = F(11,14)
    for t in (F(0), F(1,3), F(2,3), F(1)):
        alpha = F(3,20)-t/10; beta = F(3,20)+t/10
        theta = low+t/7
        a.eq(alpha+(1-alpha-beta)*theta, p, "sharp-set path keeps observed law")
        a.eq(F(1,20) <= alpha <= F(3,20) and F(3,20) <= beta <= F(1,4),
             True, "sharp-set path stays admissible")
    a.eq(high-low, F(1,7), "irreducible identification width")
    a.eq((p+F(1,4)-1 < 0, p-F(3,20)>0, 1-F(3,20)-F(1,4)>0),
         (True,True,True), "entire-rectangle derivative and denominator signs")
    shown(1, "[9/14,11/14]", "not", "population")
    # Both completely uninformative and negative-slope kernels are valid laws.
    for theta in (F(0),F(2,7),F(1)):
        a.eq(F(2,5)+(1-F(2,5)-F(3,5))*theta, F(2,5), "uninformative kernel")
    theta=F(1,4); alpha=F(7,10); beta=F(1,2)
    recorded=alpha+(1-alpha-beta)*theta
    a.eq((recorded-alpha)/(1-alpha-beta),theta,"negative-slope inversion")

    # Integrate over the uniform tail interval; probability and moments differ.
    for n in (2,10,100):
        length=F(1,n); mean=n*length; second=n*n*length
        a.eq((mean,second,second-mean*mean),(1,n,n-1),"rare-tail integral moments")
        a.eq(n*length,1,"large-value tail mean does not vanish")
    shown(2,"E|Xₙ|=1","Var(Xₙ)=n−1","almost sure", "positive constant")
    # A bounded singular-limit matrix illustrates why entrywise Op is insufficient.
    for n in (2,20):
        matrix=((F(1),F(0)),(F(0),F(1,n)))
        inverse=((F(1),F(0)),(F(0),F(n)))
        product=tuple(tuple(sum(matrix[i][k]*inverse[k][j] for k in range(2))
                            for j in range(2)) for i in range(2))
        a.eq(product,((1,0),(0,1)),"exact singular-limit inverse counterexample")
    shown(3,"ε/2","Independence is not used","Aₙ=1/n","nonsingular")
    radius2=(2*F(2,1000)+F(1,1000))/4
    a.eq(radius2,F(1,800),"finite optimization-error bound")
    shown(4,"√2/40","≥.97","n−1/4","another argument")
    for n in (5,17):
        left=1-F(1,n);right=1-F(1,2*n)
        a.eq(0<left<right<1,True,"moving dip interval")
        a.eq(left*left-2<0,True,"sample minimum beats zero")
        for point in (F(0),F(1,4),F(1,2),F(3,4),F(1)):
            a.eq(left<=point<=right,False,"fixed grid misses the dip")
        a.eq(abs((left*left-2)-left*left),2,"uniform error at moving minimizer")
    shown(5,"1−1/n→1","supremum is2","missing uniform convergence")

    # Distinct finite quadratic law tests projection, including a constrained mean.
    outcomes=(-2,1,4);weights=(F(1,4),F(1,2),F(1,4))
    mean=sum(w*x for w,x in zip(weights,outcomes))
    second=sum(w*x*x for w,x in zip(weights,outcomes));var=second-mean*mean
    a.eq((mean,var),(1,F(9,2)),"quadratic criterion population moments")
    for bound in (F(1,2),F(2)):
        optimum=max(-bound,min(bound,mean))
        for theta in (-bound,F(0),bound,optimum):
            q=sum(w*(x-theta)**2 for w,x in zip(weights,outcomes))
            a.eq(q,var+(theta-mean)**2,"completed-square population criterion")
            a.eq(q-(var+(optimum-mean)**2)>=(theta-optimum)**2,True,"projection separation")
    shown(6,"2B+2|W|","q(W,0)=W²","max(−B,min(B,μ))","structural")

    # Sensitivity follows by differentiating the measurement identity, then
    # finite independent Bernoulli supports give the full influence variance.
    p,alpha,beta=F(3,5),F(1,10),F(1,5);d=1-alpha-beta;theta=(p-alpha)/d
    gradient=(1/d,-(1-theta)/d,theta/d)
    parts=tuple(g*g*r*(1-r) for g,r in zip(gradient,(p,alpha,beta)))
    a.eq(gradient,(F(10,7),-F(20,49),F(50,49)),"inverse measurement sensitivity")
    a.eq(parts,(F(24,49),F(36,2401),F(400,2401)),"three variance contributions")
    total=mean_psi=second_psi=F()
    for outcome in itertools.product((0,1),repeat=3):
        weight=F(1)
        for x,r in zip(outcome,(p,alpha,beta)):weight*=r if x else 1-r
        psi=sum(g*(x-r) for g,x,r in zip(gradient,outcome,(p,alpha,beta)))
        total+=weight;mean_psi+=weight*psi;second_psi+=weight*psi*psi
    a.eq((total,mean_psi,second_psi),(1,0,F(1612,2401)),"full validation influence distribution")
    unequal=parts[0]+parts[1]/F(1,2)+parts[2]/2
    a.eq(unequal,F(1448,2401),"unequal validation precision")
    # Concrete departure: false positives are nested in main positives, while
    # the false-negative stratum is still independent. Covariance now matters.
    overlapping=F()
    for main,fp,w in ((0,0,F(2,5)),(1,0,F(1,2)),(1,1,F(1,10))):
        for fn in (0,1):
            mass=w*(beta if fn else 1-beta)
            psi=sum(g*(x-r) for g,x,r in zip(gradient,(main,fp,fn),(p,alpha,beta)))
            overlapping+=mass*psi*psi
    a.eq(overlapping,F(1500,2401),"overlap changes validation variance")
    a.eq(overlapping,second_psi+2*gradient[0]*gradient[1]*F(1,25),"required overlap covariance")
    a.eq(F(1,10)*F(9,10)/d**2,F(9,49),"boundary preprojection variance")
    shown(7,"(10/7,−20/49,50/49)","1612/2401","1448/2401","trustworthy")

    # Conditional cost variance and usage probability provide a different ratio
    # oracle; a three-draw enumeration checks the exceptional denominator event.
    use=F(2,5);conditional_mean=F(5);conditional_var=F(9)
    ratio_var=conditional_var/use
    a.eq(ratio_var,F(45,2),"ratio influence via conditional variance")
    states=((0,0,F(3,5)),(2,1,F(1,5)),(8,1,F(1,5)))
    raw_a=sum(x*w for x,y,w in states);raw_d=sum(y*w for x,y,w in states)
    aa=sum(x*x*w for x,y,w in states);ad=sum(x*y*w for x,y,w in states)
    covariance=ad-raw_a*raw_d;avar=aa-raw_a**2;dvar=raw_d-raw_d**2
    a.eq((raw_a,raw_d,aa,covariance,avar,dvar),(2,F(2,5),F(68,5),F(6,5),F(48,5),F(6,25)),"ratio raw moments")
    wrong=avar/use**2+raw_a**2*dvar/use**4
    a.eq(wrong,F(195,2),"omitted covariance variance")
    a.eq(wrong-2*raw_a*covariance/use**3,ratio_var,"covariance restores correct variance")
    sample_mean=sample_second=empty=F()
    for observations in itertools.product(states,repeat=3):
        probability=F(1);sum_a=sum_d=F()
        for x,y,w in observations:probability*=w;sum_a+=x;sum_d+=y
        estimate=sum_a/sum_d if sum_d else F()
        sample_mean+=probability*estimate;sample_second+=probability*estimate**2
        if not sum_d:empty+=probability
    a.eq(empty,F(3,5)**3,"exact zero-user event")
    a.eq(sample_mean,5*(1-empty),"finite ratio convention is biased but asymptotically negligible")
    a.eq(sample_second-sample_mean**2,F(6006,625),"full 27-outcome finite ratio variance")
    a.eq(sum(F(count,500)*((x-5*y)/use)**2 for count,(x,y,w) in zip((300,100,100),states)),ratio_var,"observed influence variance")
    shown(8,"68/5","48/5","6/25","6/5","45/2","195/2","null event")

    # Coefficients of the exact polynomial in a standard normal draw.
    for root_n in (F(3),F(10)):
        mu=F(2);sigma=F(2)
        regular=(F(0),2*mu*sigma,sigma*sigma/root_n)
        a.eq(regular,(0,8,4/root_n),"regular scaled square polynomial")
        local_mu=2/root_n
        local=(root_n**2*local_mu**2/4,2*root_n*local_mu*sigma/4,sigma**2/4)
        a.eq(local,(1,2,1),"exact local noncentral square")
        a.eq((local[0]-1,local[1],local[2]),(0,2,1),"centered local square law")
    a.eq(8**2,64,"fixed nonzero-mean asymptotic variance")
    shown(9,"N(0,64)","χ²₁","(Z+1)²","Z²+2Z","remains random")
    for t in (2,3,10):
        n=t**4
        for exponent,wanted in ((1,F(1,t*t)),(2,F(1)),(3,F(t*t))):
            lam=F(1,t**exponent);variance=1/(n*lam**2)
            a.eq(variance,wanted,"weak-sequence exact error variance")
            a.eq((t*t*lam)**2*variance,1,"exact normalizing variance")
    shown(10,"n−1/2,1andn1/2","N(0,1)","→0","point identification")

    z,z_low,z_high=normal_quantile();coverage_rows=[]
    for n,printed in ((25,'.936246277'),(100,'.948117979'),(400,'.947392305')):
        probability,included,mass=coverage(n,p,z_low,z_high)
        a.eq(mass,1,"full rational count law")
        a.eq(included,list(range(min(included),max(included)+1)),"no omitted accepted count")
        display(printed,float(probability))
        coverage_rows.append({'n':n,'accepted_counts':[min(included),max(included)],'coverage':float(probability)})
    # Concrete uniform-coverage failure sequence: K=0 fails whenever p_n>0,
    # so coverage <= P(K>0) <= n*p_n = 1/n for p_n=1/n^2.
    for n in (25,100):
        small=F(1,n*n);probability,included,mass=coverage(n,small,z_low,z_high)
        a.eq(0 in included,False,"zero-width Wald interval misses positive rare probability")
        a.eq(probability<=1-(1-small)**n<=F(1,n),True,"rare-law coverage bound")
    for boundary in (F(0),F(1)):
        probability,included,mass=coverage(25,boundary,z_low,z_high)
        a.eq((probability,mass),(1,1),"degenerate-law coverage differs from interior target")
    shown(11,"including equality","no Monte Carlo","not","uniform")
    shown(12,"Define actual lateness","validation","criterion and tolerance","sampling units","causal","pre-specified")

    known_se=sqrt(float(parts[0]/400));ratio_se=sqrt(float(ratio_var/500))
    displays={'.714286':float(theta),'.642857':float(low),'.785714':float(high),
              '.034992711':known_se,'.645701262':float(theta)-z*known_se,
              '.782870167':float(theta)+z*known_se,'1.959963985':z,
              '.040969102':sqrt(float(second_psi/400)),'.038829179':sqrt(float(unequal/400)),
              '.212132034':ratio_se,'4.584228853':5-z*ratio_se,'5.415771147':5+z*ratio_se,
              '.035355339':sqrt(float(radius2)),'.024874686':sqrt(99)/400}
    for printed,value in displays.items():display(printed,value)
    retention=(F(11,20)-F(1,20))/(1-F(1,20)-F(3,20))
    a.eq(retention,F(5,8),"new retention target")
    a.eq(F(11,20)*F(9,20)/F(4,5)**2,F(99,256),"retention influence variance")
    for phrase in ('Cramér–Wold','invoked here, not newly proved','finite second moments suffice',
                   'estimated-influence error','scalar CLT','counterfactual restriction',
                   'positive-gap inequality','5/8','99/256'):
        a.eq(compact(phrase) in text,True,"explicit proof or retention scope "+phrase)
    return coverage_rows


def hashrow(root, path):
    raw=(root/path).read_bytes()
    return {'path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def check(root=None):
    root=Path(root) if root is not None else ROOT
    a=Audit();page=Reader();page.feed((root/FILES[0]).read_text(encoding='utf-8'));page.close()
    a.eq(page.stack,[],"balanced complete chapter")
    a.eq((page.worked,len(page.prompts),len(page.answers)),(5,12,12),"complete graduate package")
    a.eq(len(page.ids),len(set(page.ids)),"unique section anchors")
    a.eq(page.headings.count('h1'),0,"no repeated book title")
    a.eq(set(page.sources),SOURCES,"exact four inspected source scopes")
    for href in page.links:
        a.eq(bool(re.fullmatch(r'v\d\d-c\d\d\.html',href)) or href.startswith('sources.html#'),True,"flat reader route")
        if href.startswith('sources.html#'):a.eq(href.split('#',1)[1] in SOURCES,True,"scoped source route")
    coverage_rows=independent_arithmetic(a,page)
    sources=strict((root/FILES[2]).read_text(encoding='utf-8'))
    entries=sources.get('sources',sources.get('proposals'))
    require(isinstance(entries,list),"final source record entries")
    a.eq(len(entries),4,"four complete source records")
    a.eq({x.get('proposed_id',x.get('id')) for x in entries},SOURCES,"source identity mapping")
    for entry in entries:
        a.eq(entry['url'].startswith('https://'),True,"primary source URL")
    author=strict((root/FILES[3]).read_text(encoding='utf-8'))
    rows=author.get('reviewed_hashes',author.get('payloads'))
    a.eq({row['path'] for row in rows},set(FILES[:3]),"author exact three nonself payloads")
    for row in rows:a.eq(row,hashrow(root,row['path']),"author payload unchanged")
    rejected=0
    for invalid in ('{"a":1,"a":2}','NaN','Infinity','-Infinity','1e10000','{}{}'):
        try:strict(invalid)
        except ValueError:rejected+=1
        else:raise ValueError('permissive strict-JSON reader')
    before={path:(root/path).read_bytes() for path in FILES}
    old=sys.dont_write_bytecode;sys.dont_write_bytecode=True
    try:
        with contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()) as err:
            spec=importlib.util.spec_from_file_location('c01_author_integration',root/FILES[1])
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            author_summary=module.check()
        a.eq(out.getvalue()+err.getvalue(),'',"quiet author integration API")
        a.eq(strict(json.dumps(author_summary,allow_nan=False)),author_summary,"strict author summary")
        a.eq(author_summary['chapter'],'v12-c01',"author integration identity")
    finally:sys.dont_write_bytecode=old
    for path,raw in before.items():a.eq((root/path).read_bytes(),raw,"integration nonmutation")
    review=strict((root/FILES[5]).read_text(encoding='utf-8'))
    a.eq(len(review['reviewed_hashes']),5,"four final authors plus own checker")
    a.eq({x['path'] for x in review['reviewed_hashes']},set(FILES[:5]),"exact peer binding membership")
    for row in review['reviewed_hashes']:a.eq(row,hashrow(root,row['path']),"final peer payload")
    result={'chapter':'v12-c01','review':'separate peer','status':'passed',
            'comparisons':a.comparisons,'worked_examples':5,'exact_exercises_and_solutions':12,
            'rounded_displays_checked':a.displays,'primary_scopes':4,'strict_JSON_rejections':rejected,
            'coverage_recurrence':coverage_rows,'author_comparisons_integration_only':author_summary['comparisons'],
            'nonself_bindings':5,
            'limits':'Finite reconstruction plus separately documented proof reading; no general dependent/high-dimensional/uniform inference, rendered UI or external human certification.'}
    strict(json.dumps(result,allow_nan=False))
    return result


def portable():
    with tempfile.TemporaryDirectory(prefix='v12-c01-peer-') as temporary:
        root=Path(temporary)/'book'
        for path in FILES:
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/path,dest)
        before={path:hashrow(root,path) for path in FILES};summaries=[]
        for flags in ([],['-O']):
            code=("import sys,importlib.util,contextlib,io,json;sys.dont_write_bytecode=True;"
                  "s=importlib.util.spec_from_file_location('peer',"+repr(str(root/FILES[4]))+");"
                  "m=importlib.util.module_from_spec(s)\n"
                  "with contextlib.redirect_stdout(io.StringIO()) as o,contextlib.redirect_stderr(io.StringIO()) as e:\n s.loader.exec_module(m);r=m.check()\n"
                  "if o.getvalue() or e.getvalue():raise ValueError('nonquiet API')\n"
                  "print(json.dumps(r,allow_nan=False,sort_keys=True))")
            done=subprocess.run([sys.executable]+flags+['-c',code],cwd='/',capture_output=True,
                                text=True,timeout=30,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            require(not done.returncode and not done.stderr,'portable API failure '+done.stderr)
            summaries.append(strict(done.stdout))
        require(summaries[0]==summaries[1],'normal/optimized portable mismatch')
        require({path:hashrow(root,path) for path in FILES}==before,'portable payload mutation')
        require({str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==set(FILES),'portable file membership')
        return {'status':'passed','files':6,'cwd':'/','normal_and_optimized':True,
                'no_mutation':True,'summary':summaries[0]}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolation',action='store_true')
    args=parser.parse_args()
    print(json.dumps(portable() if args.isolation else check(),allow_nan=False,sort_keys=True))
