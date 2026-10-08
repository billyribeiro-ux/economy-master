"""Independent numerical, contract and instructional checks for v04-c11."""

import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import itertools
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "content/projects/v04-c11-audit.py"
CASE = ROOT / "content/projects/v04-c11-case.json"
CHAPTER = ROOT / "content/chapters/v04-c11.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def rejected(function, value):
    try:
        function(value)
    except (TypeError, ValueError):
        return
    raise AssertionError("expected invalid-input rejection")


def rational_moments(values):
    """Raw-moment identity in exact arithmetic, not the program's pair sums."""
    mean = F(sum(values), len(values))
    return mean, F(sum(value * value for value in values), len(values)) - mean * mean


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = 0
        self.exercise_depth = 0
        self.exercises = 0
        self.in_solutions = False
        self.solutions = 0
        self.pre = False
        self.blocks = []
        self.buffer = []
        self.links = []
        self.sources = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        require(tag not in {"html", "body", "h1", "script"}, "fragment format")
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.exercise_depth = 1
        elif tag == "ol" and self.exercise_depth:
            self.exercise_depth += 1
        if tag == "details" and attrs.get("class") == "solutions":
            self.in_solutions = True
        if tag == "li" and self.exercise_depth == 1:
            self.exercises += 1
        if tag == "li" and self.in_solutions:
            self.solutions += 1
        if tag == "pre":
            self.pre = True
            self.buffer = []
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])

    def handle_endtag(self, tag):
        if tag == "ol" and self.exercise_depth:
            self.exercise_depth -= 1
        if tag == "details":
            self.in_solutions = False
        if tag == "pre":
            self.blocks.append("".join(self.buffer))
            self.pre = False

    def handle_data(self, text):
        if self.pre:
            self.buffer.append(text)


def check():
    checks = []
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        module = runpy.run_path(str(PROGRAM), run_name="v04_c11_check")
    require(not captured.getvalue(), "quiet import")
    original_bytes = CASE.read_bytes()
    case = module["load_case"](CASE)
    original_case = copy.deepcopy(case)
    report = module["build_report"](case)
    require(case == original_case and CASE.read_bytes() == original_bytes, "nonmutation")
    require(report["audit_status"] == "passed", "baseline status")
    require(report["ledger"]["exact_net_cents"] == "1"
            and report["ledger"]["left_sum_cents"] == 0
            and report["ledger"]["fsum_of_converted_cents"] == 1,
            "first sum example")
    require(report["conversion_probe"]["exact_net_cents"] == "1"
            and report["conversion_probe"]["conversion_error_cents"] == "1"
            and report["conversion_probe"]["left_accumulation_error_cents"] == "0"
            and report["conversion_probe"]["fsum_of_converted_cents"] == 0,
            "early-conversion example")
    require(F(report["margins"]["exact_variance_cents2"]) == F(2, 3)
            and F(report["margins"]["exact_variance_dollars2"]) == F(1, 15000),
            "baseline variance units")
    require(F(report["margins"]["centered_variance_error_cents2_exact"])
            == F(1, 27021597764222976), "observed variance rounding error")
    require(report["margins"]["raw_variance_cents2_approx"] == 0,
            "raw-moment failure demonstrated")
    require(len(report["deliberately_broken_variants"]) == 6
            and all(item["detected"] for item in report["deliberately_broken_variants"]),
            "six deliberate variants detected")
    checks.append("Quiet import, nonmutation, exact baseline sums/variance/units and all six detected broken variants")

    # Independent integer/rational analysis of representation and rounding.
    u = F(1, 2**53)
    sum_cases = list(itertools.permutations([10**16, 1, -10**16]))
    sum_cases += [(0,), (7,), (100, -100), (10**18, 3, -10**18),
                  (2**53+1, -2**53), (10**16, 3, -10**16)]
    for values in sum_cases:
        values = list(values)
        terms = [F.from_float(float(value)) for value in values]
        exact = sum(values)
        stored_sum = sum(terms, F(0))
        actual = module["sum_audit"](values)
        sequential = F.from_float(actual["left_sum_cents"])
        k = len(values) - 1
        bound = F(k, 2**53-k) * sum(abs(value) for value in terms)
        require(F(actual["roundoff_bound_cents_exact"]) == bound, "rational gamma bound")
        require(abs(sequential-stored_sum) <= bound, "actual summation error versus bound")
        require(abs(sequential-exact) <= abs(stored_sum-exact)+bound, "separated total bound")
        require(F(actual["exact_net_cents"]) == exact, "exact sum reference")
    gamma_bound = (2*u/(1-2*u)) * (2*10**16+1)
    require(math.isclose(float(gamma_bound), 4.440892098500627, rel_tol=0, abs_tol=1e-14),
            "worked bound number")
    require(module["sum_audit"]([100, -100])["relative_condition_number"] is None,
            "zero-net conditioning boundary")
    require(module["broken_left_sum"]([10**16, 3, -10**16]) == 4,
            "delayed-check ties-to-even result")
    checks.append("Twelve sum/permutation/boundary cases with rational represented-value, conversion-error and gamma-bound checks; delayed sum exact3 versus float4")

    moment_cases = [[0], [7, 7, 7], [0, 2], [1, 2, 3], [8, 10, 12],
                    [10**12, -10**12], [10**12, -10**12, 1]]
    for base in [0, 10**8, 10**10, -10**12 + 100]:
        for offsets in [[1, 2, 3], [2, 4, 6], [0, 0, 0], [-3, 0, 2, 9]]:
            moment_cases.append([base + value for value in offsets])
    moment_cases.append([i*i-300 for i in range(200)])
    for values in moment_cases:
        ref_mean, ref_var = rational_moments(values)
        require(module["reference_moments"](values) == (ref_mean, ref_var),
                "pairwise reference versus exact raw moments")
        value_mean, value_var = module["centered_moments"](values)
        require(abs(F.from_float(value_mean)-ref_mean) <= u*abs(ref_mean),
                "single mean-division bound")
        require(module["within_variance_budget"](value_var, ref_var),
                "centered variance versus independent exact moments")
        require(module["within_variance_budget"](module["centered_moments"](list(reversed(values)))[1], ref_var),
                "candidate permutation property")
    require(module["broken_raw_variance"]([10**10+1, 10**10+2, 10**10+3]) < 0,
            "negative raw-moment example for reviewer")
    checks.append(str(len(moment_cases)) + " moment cases with an independent exact raw-moment oracle, integer mean-division bound and candidate permutation checks")

    # Every numerical exercise, including finite perturbation checks of the
    # proved variance input-sensitivity bound (not just algorithm outputs).
    values = [1000000, -999990, 5]
    require(sum(values) == 15 and F(sum(abs(x) for x in values), 15) == 133333,
            "exercise 2 conditioning")
    require(F(1999995, 10**6) == F(399999, 200000), "relative input error budget")
    require(15-F(1999995,10**6) > 0 and 15-3 > 0, "exercise 2 sign certificates")
    require(rational_moments([100000002, 100000004, 100000006]) == (F(100000004), F(8,3)),
            "exercise 4 moments")
    require(rational_moments([2,4,6]) == (4,F(8,3))
            and rational_moments([-6,-12,-18]) == (-12,24), "exercise 4 transformations")
    require(F(8,3)/10000 == F(1,3750), "exercise 4 squared units")
    for values, eta in [([1,2,3], F(1,10)), ([2,4,6], F(1,4)), ([7,7,7],F(1,4))]:
        base_var = rational_moments(values)[1]
        bound = 2*float(eta)*math.sqrt(float(base_var))+float(eta*eta)
        for changes in itertools.product([-eta,F(0),eta],repeat=3):
            perturbed = [F(x)+dx for x,dx in zip(values,changes)]
            new_var = rational_moments(perturbed)[1]
            require(float(abs(new_var-base_var)) <= bound+1e-15, "variance input-error bound")
    require(math.isclose(.2*math.sqrt(2/3)+.01, .173299316185545, rel_tol=0, abs_tol=1e-14),
            "worked example 2 sensitivity")
    require(math.isclose(.5*math.sqrt(8/3)+1/16, .878996580927726, rel_tol=0, abs_tol=1e-14),
            "exercise 5 sensitivity")
    require(math.isclose(0, 1e-9, rel_tol=1e-12, abs_tol=1e-8)
            and not math.isclose(0, 1e-7, rel_tol=1e-12, abs_tol=1e-8), "exercise 7 tolerance")
    require(rational_moments([8,10,12]) == (10,F(8,3)), "delayed variance")
    checks.append("All determinate exercises and delayed answers; 81 exact perturbation scenarios for the derived variance-input bound")

    invalid = []
    for key,value in [("money_unit","dollar"),("currency","EUR"),("period","month"),
                      ("case_id",""),("provenance",False),
                      ("ledger_transactions_cents",[]),("ledger_transactions_cents",[True]),
                      ("ledger_transactions_cents",[1.0]),("ledger_transactions_cents",["1"]),
                      ("ledger_transactions_cents",[10**18+1]),
                      ("conversion_probe_cents",[float("inf")]),
                      ("margin_observations_cents",[float("nan")]),
                      ("margin_observations_cents",[10**12+1]),
                      ("margin_observations_cents",[1]*201),
                      ("margin_observations_cents",None)]:
        item=copy.deepcopy(case)
        item[key]=value
        invalid.append(item)
    missing=copy.deepcopy(case);del missing["period"]
    extra=copy.deepcopy(case);extra["unused"]=1
    invalid.extend([missing,extra,[],None])
    for item in invalid:
        rejected(module["validate_case"],item)
    documents=[json.dumps(item) for item in invalid]
    documents.extend([original_bytes.decode().replace('"money_unit": "cent"',
                     '"money_unit": "cent", "money_unit": "cent"'), "{",
                     original_bytes.decode().replace('100000001,','1e10000,')])
    with tempfile.TemporaryDirectory(prefix="v04-c11-") as temporary:
        folder=Path(temporary)
        program_dir=folder/"package";program_dir.mkdir()
        other_dir=folder/"other";other_dir.mkdir()
        script=program_dir/PROGRAM.name
        data=program_dir/CASE.name
        shutil.copyfile(PROGRAM,script)
        valid_reports=[]
        for optimized in [False,True]:
            command=[sys.executable]+(["-O"] if optimized else [])+[str(script)]
            data.write_bytes(original_bytes)
            result=subprocess.run(command,cwd=other_dir,text=True,capture_output=True,check=False)
            require(result.returncode==0 and not result.stderr,"portable ordinary/optimized CLI")
            parsed=json.loads(result.stdout)
            require(parsed.pop("input_sha256")==hashlib.sha256(original_bytes).hexdigest(),"input fingerprint")
            require(parsed.pop("program_sha256")==hashlib.sha256(PROGRAM.read_bytes()).hexdigest(),"program fingerprint")
            require(parsed.pop("assert_statements_enabled") is (not optimized),"assert metadata")
            valid_reports.append(parsed)
            require(data.read_bytes()==original_bytes,"CLI input unchanged")
            for document in documents:
                data.write_text(document,encoding="utf-8")
                failed=subprocess.run(command,cwd=other_dir,text=True,capture_output=True,check=False)
                require(failed.returncode==1 and not failed.stdout
                        and failed.stderr.startswith("Cannot complete numerical audit:"),"invalid CLI rejection")
        require(valid_reports[0]==valid_reports[1],"numeric/gate parity under optimization")
        data.write_bytes(b"\xff")
        failed=subprocess.run([sys.executable,str(script)],cwd=other_dir,text=True,capture_output=True)
        require(failed.returncode==1 and not failed.stdout,"invalid encoding")
        data.unlink()
        failed=subprocess.run([sys.executable,str(script)],cwd=other_dir,text=True,capture_output=True)
        require(failed.returncode==1 and not failed.stdout,"missing input")
    for optimized in [0,1]:
        scope={}
        source="def unsafe(value):\n    assert type(value) is int\n    return value\n"
        exec(compile(source,"assert-demonstration","exec",optimize=optimized),scope)
        if optimized:
            require(scope["unsafe"](True) is True,"assert omission demonstration")
        else:
            try: scope["unsafe"](True)
            except AssertionError: pass
            else: raise AssertionError("ordinary assertion failed to run")
    checks.append(str(len(invalid))+" invalid contracts and "+str(len(documents))+" bad CLI documents rejected normally and under -O; file errors, portable run, hashes and retained gates checked")

    parser=Manuscript();text=CHAPTER.read_text(encoding="utf-8");parser.feed(text)
    require(parser.worked==2 and parser.exercises==8 and parser.solutions==8,"chapter package")
    require(len(parser.blocks)==5,"displayed blocks")
    scope={}
    exec(compile(parser.blocks[0],"validation-snippet","exec"),scope)
    scope["validate_cents"]([3,-1,2])
    for item in [[],[True],[1.0],["1"],[10**18+1]]:
        rejected(scope["validate_cents"],item)
    exec(compile(parser.blocks[1],"variance-snippet","exec"),scope)
    require(module["within_variance_budget"](scope["centered_population_variance"]([100000001,100000002,100000003]),F(2,3)),"variance instructional code")
    require(parser.blocks[2].strip().splitlines()==["python3 v04-c11-audit.py","python3 -O v04-c11-audit.py"],"shell run instructions")
    scope["candidate_total"]=sum
    exec(compile(parser.blocks[3],"mutation-check","exec"),scope)
    def mutating(values):
        values.sort()
        return sum(values)
    scope["candidate_total"]=mutating
    try: exec(compile(parser.blocks[3],"mutation-check","exec"),scope)
    except AssertionError: pass
    else: raise AssertionError("displayed mutation test did not detect sorting")
    exec(compile(parser.blocks[4],"amount-validation","exec"),scope)
    for item in [True,1.0,"1",10**18+1]: rejected(scope["validate_amount"],item)
    scope["validate_amount"](-10**18)
    sources=json.loads((ROOT/"content/reviews/v04-c11-sources.json").read_text())
    require(parser.sources=={item["id"] for item in sources},"source ID alignment")
    for link in parser.links:
        if link.startswith("v04-c11-"):
            require("/" not in link and (ROOT/"content/projects"/link).is_file(),"flat download target")
    require("Teach-back:" in text and "Delayed-check answers" in text,"retention closure")
    checks.append("Two worked examples, eight matched solutions, four executable Python blocks and two shell commands; mutation snippet catches fault; citations/downloads/retention checked")

    return {"status":"passed","checks":checks,"limitations":[
        "Finite references and tests verify stated computations/fixtures, not input source completeness or economic validity.",
        "Roundoff bounds assume the stated binary64 normal-range model; the variance comparison budget is an engineering criterion, not a global proof.",
        "Author review is distinct from root review and independent human assessment; no visual/mobile/print QA was performed.",
        "Whole-library links, prerequisite-order acceptance, build and publication remain root responsibilities."
    ]}


if __name__=="__main__":
    print(json.dumps(check(),indent=2))
