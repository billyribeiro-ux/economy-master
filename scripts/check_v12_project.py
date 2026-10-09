"""Independent Harbor Skills author checker; stdlib, quiet normal/-O portable API.

Expected values use original worker potential records, covariance/FWL formulas,
and quadratic crossing roots. Only the public model run(data)/CLI is executed.
"""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
from itertools import combinations
from math import isqrt
from pathlib import Path
import json
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects"
PREFIX = "v12-assessment-"
OWNED = (
    "content/assessments/parts/v12-project.html",
    "content/projects/v12-assessment-inputs.json",
    "content/projects/v12-assessment-analysis.py",
    "content/projects/v12-assessment-output.json",
    "content/projects/v12-assessment-manifest.json",
    "content/projects/v12-assessment-README.txt",
    "scripts/check_v12_project.py",
    "content/reviews/v12-project-author.json",
    "content/reviews/v12-project-sources.json",
)
# Centre, worker, baseline, type, untreated change, receipt effect.
PEOPLE = (
    (1,1,40,"C",-3,2),(1,2,42,"C",-1,4),
    (2,1,44,"C",0,6),(2,2,46,"N",2,1),
    (3,1,48,"A",2,3),(3,2,50,"C",4,2),
    (4,1,52,"N",-2,8),(4,2,54,"N",0,0),
    (5,1,56,"A",1,5),(5,2,58,"N",3,1),
    (6,1,60,"C",-1,4),(6,2,62,"C",1,6),
)
SETS = tuple(combinations(range(1, 7), 3))


def require(ok, label):
    if not ok:
        raise ValueError("Harbor independent check: " + label)


def strict(text):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            require(k not in out, "duplicate key")
            out[k] = v
        return out
    def fail(value):
        raise ValueError("nonfinite " + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=fail)


def dump(value):
    if isinstance(value, F): return str(value)
    if isinstance(value, (tuple, list)): return [dump(v) for v in value]
    if type(value) is dict: return {k: dump(v) for k, v in value.items()}
    return value


class Audit:
    def __init__(self):
        self.comparisons = self.cases = self.rejections = self.aliases = self.anchors = 0
    def eq(self, actual, expected, label):
        self.comparisons += 1
        actual = dump(actual)
        wanted = dump(expected)
        require(type(actual) is type(wanted) and actual == wanted,
                label + ": " + repr(actual)[:180] + " != " + repr(wanted)[:180])
    def yes(self, condition, label):
        self.eq(bool(condition), True, label)
    def call(self, run, data):
        before = deepcopy(data)
        stream = StringIO()
        with redirect_stdout(stream), redirect_stderr(stream):
            result = run(data)
        self.eq(stream.getvalue(), "", "quiet API")
        self.eq(data, before, "no input mutation")
        self.eq(strict(json.dumps(result, allow_nan=False)), result, "strict JSON result")
        self.cases += 1
        return result


def avg(values):
    return sum(values, F(0)) / len(values)


def variance(values):
    return (sum(v*v for v in values)-sum(values)**2/len(values))/(len(values)-1)


def population_rows(s, weak=False, common=None):
    result = []
    for j, r, b, kind, base, tau in PEOPLE:
        if weak and (j,r) == (2,1): kind = "N"
        if common is not None and kind == "C": tau = common
        z = int(j in s)
        received = int(kind == "A" or (kind == "C" and z == 1))
        change = base + tau*received
        result.append([j,r,z,received,b,b+change,change])
    return result


def centres(rows, col):
    return [F(rows[2*j][col]+rows[2*j+1][col],2) for j in range(6)]


def diff(v, s):
    return sum((1 if j in s else -1)*x for j,x in enumerate(v,1))/3


def fwl(w, b, s):
    z = [F(j in s)-F(1,2) for j in range(1,7)]
    x = [v-avg(b) for v in b]
    zz, xx = sum(v*v for v in z), sum(v*v for v in x)
    zx = sum(a*b for a,b in zip(z,x))
    zy, xy = sum(a*b for a,b in zip(z,w)), sum(a*b for a,b in zip(x,w))
    denominator = zz-zx*zx/xx
    require(denominator > 0, "positive residual assignment rank")
    beta = (zy-zx*xy/xx)/denominator
    slope = (xy-beta*zx)/xx
    return [avg(w)-beta/2, beta, slope], denominator, zy-zx*xy/xx


def vhat(w, s):
    return (variance([x for j,x in enumerate(w,1) if j in s])+
            variance([x for j,x in enumerate(w,1) if j not in s]))/3


def observable(rows, s):
    w,d,b,y = [centres(rows,c) for c in (6,3,4,5)]
    a,f = diff(w,s),diff(d,s)
    beta,_,_ = fwl(w,b,s)
    yes,no = [[F(r[6]) for r in rows if r[3] == value] for value in (1,0)]
    g1,g0 = [[F(r[6]) for r in rows if r[2] == value] for value in (1,0)]
    lines = [(diff(w,t),diff(d,t)) for t in SETS]
    expected = {
        "assignment":list(s),"centre_baseline":b,"centre_change":w,"centre_receipt":d,
        "change_ITT":a,"post_only_ITT":diff(y,s),"baseline_difference":diff(b,s),
        "first_stage":f,"Wald":a/f if f else None,
        "Wald_status":"defined" if f else "undefined_zero_first_stage",
        "receipt_OLS":avg(yes)-avg(no),"receipt_OLS_status":"descriptive",
        "ANCOVA_coefficients":beta,"ANCOVA_regressors":["intercept","Z","centre_B-mean_B"],
        "cluster_Neyman":vhat(w,s),"incorrect_individual_iid_variance":(variance(g1)+variance(g0))/6,
        "sharp_outcome_null_p_change":F(sum(abs(x)>=abs(a) for x,_ in lines),20),
        "sharp_outcome_null_p_ANCOVA":F(sum(abs(fwl(w,b,t)[0][1])>=abs(beta[1]) for t in SETS),20),
    }
    return expected,lines,(a,f)


def law(weak=False):
    observations = [population_rows(s,weak) for s in SETS]
    stats = [observable(rows,s)[0] for rows,s in zip(observations,SETS)]
    a0,a1 = population_rows((),weak),population_rows(range(1,7),weak)
    w0,w1,d0,d1 = centres(a0,6),centres(a1,6),centres(a0,3),centres(a1,3)
    effects = [b-a for a,b in zip(w0,w1)]
    truth,first = avg(effects),avg([b-a for a,b in zip(d0,d1)])
    undefined = sum(x["Wald"] is None for x in stats)
    vv = avg([(x["change_ITT"]-truth)**2 for x in stats])
    expected = {
        "assignment_count":20,"centre_change_z0":w0,"centre_change_z1":w1,
        "centre_encouragement_effects":effects,"encouragement_ATE":truth,"first_stage":first,
        "complier_receipt_ATE_under_exclusion":truth/first,
        "expected_change_ITT":avg([x["change_ITT"] for x in stats]),
        "expected_post_only_ITT":avg([x["post_only_ITT"] for x in stats]),
        "expected_first_stage":avg([x["first_stage"] for x in stats]),
        "expected_ANCOVA":avg([x["ANCOVA_coefficients"][1] for x in stats]),
        "expected_Wald":None if undefined else avg([x["Wald"] for x in stats]),
        "expected_Wald_status":"undefined_on_assignment_support" if undefined else "unconditional_defined",
        "zero_first_stage_assignments":undefined,
        "first_stage_range":[min(x["first_stage"] for x in stats),max(x["first_stage"] for x in stats)],
        "true_ITT_variance":vv,
        "variance_formula":(variance(w1)+variance(w0))/3-variance(effects)/6,
        "expected_Neyman":avg([x["cluster_Neyman"] for x in stats]),
        "centre_effect_sample_variance":variance(effects),
        "Neyman_expectation_gap":avg([x["cluster_Neyman"] for x in stats])-vv,
    }
    return expected,stats


def exact_sqrt(value):
    require(value >= 0, "nonnegative quadratic discriminant")
    n,d = isqrt(value.numerator),isqrt(value.denominator)
    require(n*n == value.numerator and d*d == value.denominator, "rational square discriminant")
    return F(n,d)


def inverse_oracle(lines, actual):
    """Quadratic coefficients/discriminants, independent of model's factor roots."""
    a0,b0 = actual
    roots = set()
    for a,b in lines:
        c2,c1,c0 = b*b-b0*b0,-2*(a*b-a0*b0),a*a-a0*a0
        if c2:
            root = exact_sqrt(c1*c1-4*c2*c0)
            roots.update(((-c1-root)/(2*c2),(-c1+root)/(2*c2)))
        elif c1:
            roots.add(-c0/c1)
    roots = sorted(roots)
    def p(tau):
        return F(sum((a-b*tau)**2 >= (a0-b0*tau)**2 for a,b in lines),20)
    bounds = [None]+roots+[None]
    samples = roots[:]
    for lower,upper in zip(bounds,bounds[1:]):
        samples.append((lower+upper)/2 if lower is not None and upper is not None
                       else upper-1 if upper is not None else lower+1 if lower is not None else F(0))
    return roots,samples,p


def check_inverse(a, actual, lines, observed, alpha, label):
    roots,samples,p = inverse_oracle(lines,observed)
    a.eq(actual["alpha"],alpha,label+" alpha")
    a.eq(actual["reject_if"],"p <= alpha",label+" tie rule")
    a.eq(actual["null"],"sharp_adjusted_outcome_invariance",label+" null")
    a.eq(actual["breakpoints"],roots,label+" all quadratic roots")
    parts = actual["intervals"]
    endpoints = []
    for k,part in enumerate(parts):
        a.eq(set(part),{"lower","upper","lower_unbounded","upper_unbounded","lower_closed","upper_closed"},label+" interval keys")
        l,u = (F(part[x]) if part[x] is not None else None for x in ("lower","upper"))
        a.eq(part["lower_unbounded"],l is None,label+" left infinity")
        a.eq(part["upper_unbounded"],u is None,label+" right infinity")
        a.yes(type(part["lower_closed"]) is bool and type(part["upper_closed"]) is bool,label+" closure booleans")
        a.yes((l is not None or not part["lower_closed"]) and (u is not None or not part["upper_closed"]),label+" infinity open")
        a.yes((l is None or l in roots) and (u is None or u in roots),label+" endpoints in complete roots")
        a.yes(l is None or u is None or l < u or (l==u and part["lower_closed"] and part["upper_closed"]),label+" nonempty piece")
        if endpoints:
            old_u,old_closed = endpoints[-1][1],endpoints[-1][3]
            a.yes(old_u is not None and l is not None and
                  (old_u < l or (old_u==l and not old_closed and not part["lower_closed"])),label+" sorted maximally merged")
        endpoints.append((l,u,part["lower_closed"],part["upper_closed"]))
    for t in samples:
        included = any((l is None or t>l or (t==l and lc)) and
                       (u is None or t<u or (t==u and uc)) for l,u,lc,uc in endpoints)
        a.eq(included,p(t)>alpha,label+" every full-real-line cell")
    for x,reported in actual["probe_p"].items():
        a.eq(reported,p(F(x)),label+" probability at "+x)
    a.yes("not a generic" in actual["scope"],label+" scope caveat")


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack=[]; self.ids=[]; self.values={}; self.tables={}; self.sources=set()
        self.capture=None; self.buffer=[]; self.table=None; self.row=None; self.cell=None
        self.rubric=[]; self.solutions=0; self.links=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if "id" in d:self.ids.append(d["id"])
        if tag=="details" and "solutions" in d.get("class","").split():self.solutions+=1
        if tag=="a":
            self.links.append(d.get("href",""))
            if "data-source" in d:self.sources.add(d["data-source"])
        if "data-value" in d:
            require(self.capture is None,"nested numeric capture")
            self.capture=d["data-value"];self.buffer=[]
        if tag=="table" and d.get("id") in ("v12-project-observed","v12-project-oracle"):
            self.table=d["id"];self.tables[self.table]=[]
        if self.table and tag=="tr":self.row=[]
        if self.table and tag=="td":self.cell=[]
        if "data-domain" in d:self.rubric.append((d["data-domain"],int(d["data-points"])))
        if tag not in {"br","hr","img","input","meta","link"}:self.stack.append(tag)
    def handle_data(self,data):
        if self.capture is not None:self.buffer.append(data)
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        require(self.stack and self.stack.pop()==tag,"balanced HTML "+tag)
        if tag=="span" and self.capture is not None:
            require(self.capture not in self.values,"unique numeric marker")
            self.values[self.capture]="".join(self.buffer).strip();self.capture=None
        if self.table and tag=="td":
            self.row.append("".join(self.cell).strip());self.cell=None
        if self.table and tag=="tr" and self.row:
            self.tables[self.table].append(self.row);self.row=None
        if tag=="table":self.table=None


def structure(a, base, truth, weak):
    html=(ROOT/OWNED[0]).read_text()
    doc=Document();doc.feed(html);doc.close()
    a.eq(doc.stack,[],"balanced manuscript")
    a.eq(len(doc.ids),len(set(doc.ids)),"unique IDs")
    a.yes(all(x=="project" or x.startswith("v12-project-") for x in doc.ids),"ID namespace")
    a.eq(sorted(x for x in doc.ids if x.startswith("v12-project-task-")),
         ["v12-project-task-"+str(i) for i in range(1,8)],"seven exact tasks")
    a.eq(sorted(x for x in doc.ids if x.startswith("v12-project-solution-")),
         ["v12-project-solution-"+str(i) for i in range(1,8)],"seven complete instructor sections")
    a.eq(doc.solutions,1,"standard solutions disclosure")
    a.eq(doc.tables["v12-project-observed"],[[str(v) for v in row] for row in population_rows((1,3,5))],"every observed HTML cell")
    oracle_table=[]
    for j in range(1,7):
        people=[r for r in PEOPLE if r[0]==j]
        oracle_table.append([str(j),str(people[0][4]+1),", ".join(r[3] for r in people),
                             ", ".join(str(r[5]) for r in people),", ".join(str(r[2]) for r in people)])
    a.eq(doc.tables["v12-project-oracle"],oracle_table,"every oracle HTML cell")
    a.eq(doc.rubric,[("D"+str(i),20) for i in range(1,6)],"five essential 20-point domains")
    a.yes("85/100" in html and "15/20" in html,"overall and domain floors")
    allowed={PREFIX+x for x in ("inputs.json","analysis.py","output.json","manifest.json","README.txt")}
    a.eq({h for h in doc.links if not h.startswith("sources.html#")},allowed,"flat download links")
    ids={"v12-c03-imbens-angrist1994","v12-c06-ding-experiments","asa-pvalues-2016","v04-c01-aea-data-faq"}
    a.eq(doc.sources,ids,"source scopes")
    values={
        "itt":base["change_ITT"],"baseline_difference":base["baseline_difference"],
        "post_itt":base["post_only_ITT"],"first":base["first_stage"],"wald":base["Wald"],
        "receipt":base["receipt_OLS"],"ancova":base["ANCOVA_coefficients"][1],
        "FWL_denominator":F(48,35),"FWL_numerator":F(191,35),
        "truth_first":truth["first_stage"],"truth_itt":truth["encouragement_ATE"],
        "truth_cace":truth["complier_receipt_ATE_under_exclusion"],
        "expected_wald":truth["expected_Wald"],"expected_ancova":truth["expected_ANCOVA"],
        "wald_bias":truth["expected_Wald"]-F(4),"ancova_bias":truth["expected_ANCOVA"]-F(2),
        "S0":variance(truth["centre_change_z0"]),"S1":variance(truth["centre_change_z1"]),
        "Seffect":truth["centre_effect_sample_variance"],"variance":truth["true_ITT_variance"],
        "expected_neyman":truth["expected_Neyman"],"variance_gap":truth["Neyman_expectation_gap"],
        "neyman":base["cluster_Neyman"],"iid":base["incorrect_individual_iid_variance"],
        "p_change":base["sharp_outcome_null_p_change"],"p_ancova":base["sharp_outcome_null_p_ANCOVA"],
        "weak_truth_itt":weak["encouragement_ATE"],"weak_truth_first":weak["first_stage"],
        "weak_truth_cace":weak["complier_receipt_ATE_under_exclusion"],"weak_itt":F(-8,3),"weak_first":F(0),
    }
    a.eq(set(doc.values),set(values),"all printed numeric anchors")
    for key,value in values.items():
        a.eq(doc.values[key],value,"printed "+key);a.anchors+=1
    for pattern,rows,s in (
        (r"The baseline distinct roots are ([^.]+)\.",population_rows((1,3,5)),(1,3,5)),
        (r"Its distinct crossing roots are ([^.]+)\.",population_rows((1,2,4),True),(1,2,4)),
    ):
        match=re.search(pattern,html)
        a.yes(match is not None,"printed complete root list exists")
        printed=[F(x.replace("−","-")) for x in match.group(1).split(", ")]
        _,lines,actual=observable(rows,s)
        roots,_,_=inverse_oracle(lines,actual)
        a.eq(printed,roots,"every printed exact comparison root")
    for phrase in ("not replication of an actual empirical paper","reproduction not executed",
                   "all of R","(−∞,1] ∪ [7,∞)","[3,5]","Constant nonzero factors",
                   "not pointwise","no random sampling or superpopulation law"):
        a.yes(phrase in html,"reader scope "+phrase)
    return ids


def bad_cases(data):
    cases=[]
    def changed(path,value):
        item=deepcopy(data);ref=item
        for k in path[:-1]:ref=ref[k]
        ref[path[-1]]=value;cases.append(item)
    for path,value in [
        (["schema"],True),(["schema"],2),(["project"],None),(["provenance"],"empirical"),
        (["design","centres"],True),(["design","workers_per_centre"],3),
        (["design","encouraged_count"],2),(["design","actual_encouraged_centres"],[1,1,5]),
        (["design","actual_encouraged_centres"],[5,3,1]),(["design","actual_encouraged_centres"],[1,3]),
        (["design","actual_encouraged_centres"],[1,3,7]),
        (["design","actual_encouraged_centres"],[True,3,5]),
        (["design","actual_encouraged_centres"],[1,2,3]),
        (["design","alpha"],"1/10"),(["design","alpha"],0.2),
        (["design","alpha"],"2/10"),(["design","alpha"],"1/0"),
        (["design","direct_effect_delta"],True),(["design","direct_effect_delta"],"0.5"),
        (["design","direct_effect_delta"],"1/1000001"),(["design","direct_effect_delta"],"2"),
        (["design","direct_effect_delta"],"-2"),(["design","direct_effect_delta"]," 0"),
        (["design","direct_effect_delta"],float("nan")),(["design","direct_effect_delta"],float("inf")),
        (["observed_rows",0,0],2),(["observed_rows",0,1],False),
        (["observed_rows",0,3],2),(["observed_rows",0,5],40),
        (["observed_columns"],["x"]*7),(["teaching_oracle","worker_offsets"],[-1,True]),
        (["teaching_oracle","centres",0,"types"],["N","C"]),
        (["teaching_oracle","centres",0,"tau"],[True,4]),
        (["teaching_oracle","weak_override","to"],"C"),
        (["teaching_oracle","weak_override","actual_encouraged_centres"],[1,3,5]),
    ]:changed(path,value)
    extra=deepcopy(data);extra["unused"]=0;cases.append(extra)
    missing=deepcopy(data);del missing["observed_rows"];cases.append(missing)
    unknown=deepcopy(data);unknown["teaching_oracle"]["centres"][0]["extra"]=0;cases.append(unknown)
    short=deepcopy(data);short["observed_rows"].pop();cases.append(short)
    short=deepcopy(data);short["observed_rows"][0].pop();cases.append(short)
    cases.extend((None,[],{}))
    return cases


def cli_checks(a,data,reference):
    flag=["-O"] if sys.flags.optimize else []
    with tempfile.TemporaryDirectory(prefix="harbor-cli-") as td:
        folder=Path(td)
        for name in ("inputs.json","analysis.py","output.json","manifest.json","README.txt"):
            shutil.copy2(PROJECT/(PREFIX+name),folder/(PREFIX+name))
        model=folder/(PREFIX+"analysis.py")
        original=folder/(PREFIX+"inputs.json")
        custom=folder/"custom.json";custom.write_text(json.dumps(data))
        def command(arguments):
            return subprocess.run([sys.executable]+flag+[str(model)]+arguments,cwd="/",capture_output=True,text=True,timeout=10)
        # Defaults must locate neighbouring files, not the working directory.
        result=command([])
        a.eq((result.returncode,result.stdout,result.stderr),(0,"",""),"quiet default CLI")
        a.eq(strict((folder/(PREFIX+"output.json")).read_text()),reference,"default CLI payload")
        target=folder/"explicit.json"
        result=command(["--input",str(custom),"--output",str(target)])
        a.eq((result.returncode,result.stdout,result.stderr),(0,"",""),"quiet explicit CLI")
        a.eq(strict(target.read_text()),reference,"explicit CLI payload")
        protected=[original,model,folder/(PREFIX+"README.txt"),folder/(PREFIX+"manifest.json"),custom]
        for source in protected:
            before=source.read_bytes()
            for kind in ("direct","symlink","hardlink"):
                alias=source if kind=="direct" else folder/("alias-"+kind)
                if kind=="symlink":alias.symlink_to(source)
                if kind=="hardlink":alias.hardlink_to(source)
                result=command(["--input",str(custom),"--output",str(alias)])
                a.yes(result.returncode!=0 and result.stdout=="","reject actual "+kind+" alias")
                a.eq(source.read_bytes(),before,"protected bytes retained")
                if kind!="direct":alias.unlink()
                a.aliases+=1
        text=original.read_text()
        invalid_texts=[
            '{"schema":1,"schema":1}',
            text.replace('"alpha": "1/5"','"alpha": NaN'),
            text.replace('"alpha": "1/5"','"alpha": Infinity'),
            text.replace('"alpha": "1/5"','"alpha": 0.2'),
            '{"broken":',
            " "*65537,
        ]
        for raw in invalid_texts:
            invalid=folder/"invalid.json";invalid.write_text(raw)
            target.write_text("retain this output")
            result=command(["--input",str(invalid),"--output",str(target)])
            a.yes(result.returncode!=0 and result.stdout=="","invalid CLI failure")
            a.eq(target.read_text(),"retain this output","invalid input cannot truncate output")
            a.rejections+=1


def check():
    a=Audit()
    before={name:(ROOT/name).read_bytes() for name in OWNED}
    data=strict((PROJECT/(PREFIX+"inputs.json")).read_text())
    stream=StringIO()
    with redirect_stdout(stream),redirect_stderr(stream):
        module=runpy.run_path(str(PROJECT/(PREFIX+"analysis.py")),run_name="harbor_model")
    a.eq(stream.getvalue(),"","quiet import")
    run=module["run"]
    true,stats=law(False); weak_true,_=law(True)
    a.eq(dump(true["true_ITT_variance"]),true["variance_formula"],"enumeration versus covariance formula")
    a.eq(dump(true["Neyman_expectation_gap"]),true["centre_effect_sample_variance"]/6,"Neyman expectation identity")
    a.eq(dump(true["expected_Wald"]),F(133,40),"independent finite ratio expectation")
    a.eq(dump(true["expected_ANCOVA"]),F(6057,4160),"all twenty FWL expectation")
    a.eq(dump(weak_true["zero_first_stage_assignments"]),3,"weak support failures")
    observed=population_rows((1,3,5));base,_,_=observable(observed,(1,3,5))
    ids=structure(a,base,true,weak_true)
    expected_manifest={PREFIX+x for x in ("inputs.json","analysis.py","output.json","README.txt")}
    manifest=strict((PROJECT/(PREFIX+"manifest.json")).read_text())
    a.eq({x["file"] for x in manifest["files"]},expected_manifest,"four manifest files")
    for entry in manifest["files"]:
        payload=(PROJECT/entry["file"]).read_bytes()
        a.eq(len(payload),entry["bytes"],"manifest bytes")
        a.eq(sha256(payload).hexdigest(),entry["sha256"],"manifest hash")
    sources=strict((ROOT/OWNED[-1]).read_text())
    a.eq({x["id"] for x in sources["reused"]},ids,"source record IDs")
    review=strict((ROOT/OWNED[-2]).read_text())
    expected_bound=set(OWNED)-{OWNED[-2]}
    a.eq({x["path"] for x in review["bindings"]},expected_bound,"eight author nonself files")
    for entry in review["bindings"]:
        payload=(ROOT/entry["path"]).read_bytes()
        a.eq(len(payload),entry["bytes"],"author-bound bytes")
        a.eq(sha256(payload).hexdigest(),entry["sha256"],"author-bound hash")
    cases=[data]
    for delta in ("-1","1","1/2"):
        item=deepcopy(data);item["design"]["direct_effect_delta"]=delta;cases.append(item)
    item=deepcopy(data);item["design"]["alpha"]="1/20";cases.append(item)
    for assignment in ((2,4,6),(1,2,3)):
        item=deepcopy(data);item["design"]["actual_encouraged_centres"]=list(assignment)
        item["observed_rows"]=population_rows(assignment);cases.append(item)
    reference=None
    for number,item in enumerate(cases):
        out=a.call(run,item)
        if number==0:reference=out
        s=tuple(item["design"]["actual_encouraged_centres"])
        alpha=F(item["design"]["alpha"]);delta=F(item["design"]["direct_effect_delta"])
        expected,lines,line=observable(item["observed_rows"],s)
        current=out["observed_analysis"]
        for key,value in expected.items():a.eq(current[key],value,"observed "+key)
        check_inverse(a,current["sharp_adjusted_outcome_inversion"],lines,line,alpha,"baseline")
        a.eq(out["teaching_oracle"],true,"entire baseline alternative law")
        weak_rows=population_rows((1,2,4),True)
        a.eq(out["weak_extension"]["observed_rows"],weak_rows,"weak actual records")
        expected,lines,line=observable(weak_rows,(1,2,4))
        for key,value in expected.items():a.eq(out["weak_extension"]["observed_analysis"][key],value,"weak "+key)
        check_inverse(a,out["weak_extension"]["observed_analysis"]["sharp_adjusted_outcome_inversion"],lines,line,alpha,"weak")
        a.eq(out["weak_extension"]["teaching_oracle"],weak_true,"entire weak alternative law")
        direct=out["direct_effect_extension"]
        a.eq(direct["delta"],delta,"direct parameter")
        a.eq(direct["complier_receipt_ATE_at_fixed_assignment"],F(4)-delta,"direct receipt effect")
        a.eq(direct["sharp_receipt_effect_bounds"],[F(3),F(5)],"attainable bound")
        a.eq([direct["assignment_ATE"],direct["first_stage"],direct["ratio_of_assignment_effects"]],[F(2),F(1,2),F(4)],"unchanged assignment effects")
        a.eq(direct["all_worker_assignment_observables_unchanged"],True,"equivalence summary")
        for _,_,_,kind,v,tau in PEOPLE:
            for z in (0,1):
                d=int(kind=="A" or (kind=="C" and z))
                new=F(v)+(F(tau)-delta)*d+delta*z if kind=="C" else F(v)+tau*d
                a.eq(dump(new),F(v)+tau*d,"worker-level observational equivalence")
    a.eq(strict((PROJECT/(PREFIX+"output.json")).read_text()),reference,"entire stored reference output")
    # Truth validation for sharp rank coverage, separate from heterogeneous data.
    for alpha,expected in ((F(1,5),F(1,5)),(F(1,20),F(0))):
        rejected=0
        for s in SETS:
            rows=population_rows(s,common=4)
            residual=centres([[*r[:6],r[6]-4*r[3]] for r in rows],6)
            actual=abs(diff(residual,s))
            probability=F(sum(abs(diff(residual,t))>=actual for t in SETS),20)
            rejected+=probability<=alpha
        a.eq(dump(F(rejected,20)),expected,"actual homogeneous-null size")
    for invalid in bad_cases(data):
        stream=StringIO()
        try:
            with redirect_stdout(stream),redirect_stderr(stream):run(invalid)
        except ValueError:pass
        else:raise ValueError("invalid API input accepted")
        a.eq(stream.getvalue(),"","quiet rejected API")
        a.rejections+=1
    cli_checks(a,data,reference)
    for name,payload in before.items():a.eq((ROOT/name).read_bytes(),payload,"no package mutation")
    return {"project":"v12-project","status":"passed","comparisons":a.comparisons,
            "valid_API_cases":a.cases,"rejections":a.rejections,
            "actual_output_alias_cases":a.aliases,"printed_anchors":a.anchors,
            "complete_assignment_law_size":20,"proofs_reviewed":7,
            "external_empirical_replication_performed":False}


if __name__=="__main__":
    check()

