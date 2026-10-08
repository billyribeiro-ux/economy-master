"""Independent exact checks for v07-c04. Import and check() are quiet."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BOOK = Path(__file__).resolve().parents[1]
PROJECT = BOOK / "content/projects"


def need(condition, message):
    if not condition:
        raise AssertionError(message)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ordered = []
        self.counts = []
        self.links = []
        self.worked = 0
        self.h1 = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "aside" and "worked" in a.get("class", "").split():
            self.worked += 1
        if tag == "h1":
            self.h1 += 1
        if tag == "a":
            self.links.append(a.get("href", ""))
        if tag == "ol":
            self.ordered.append(0)
        if tag == "li" and self.ordered:
            self.ordered[-1] += 1
        if tag not in {"br", "hr", "img", "meta", "link", "input"}:
            self.stack.append(tag)
    def handle_endtag(self, tag):
        need(bool(self.stack) and self.stack[-1] == tag, f"HTML closing tag {tag}")
        self.stack.pop()
        if tag == "ol":
            self.counts.append(self.ordered.pop())


def ledger_reference():
    """Signed double-entry journal, independent of the lab's rollforward code."""
    accounts = {k:F(0) for k in ("cash", "machine", "ad", "imp", "capital", "income")}
    def post(**entry):
        values = {k:F(v) for k,v in entry.items()}
        need(sum(values.values()) == 0, "journal balances")
        for key, value in values.items():
            accounts[key] += value
    post(cash=200, capital=-200)
    post(machine=120, cash=-120)
    post(income=14, cash=-14)
    post(cash=45, income=-45)
    post(income=20, cash=-20)
    post(income="27/2", ad="-27/2")
    snapshots = [dict(accounts)]
    post(cash=60, income=-60)
    post(income=25, cash=-25)
    post(income=24, ad=-24)
    post(income=18, imp=-18)
    snapshots.append(dict(accounts))
    post(cash=30, income=-30)
    post(income=10, cash=-10)
    post(income=9, ad=-9)
    # Preserve the two actual sale settlements, rather than booking the gain as cash.
    post(cash=60, ad="93/2", imp=18, machine=-120, income="-9/2")
    post(cash="-3/2", income="3/2")
    snapshots.append(dict(accounts))
    return snapshots


def identities(report, opening=F(200)):
    previous_cash, previous_equity = opening, opening
    for row in report["rows"]:
        r = {k:F(v) for k,v in row.items() if k != "period"}
        need(r["carrying"] == r["gross"] - r["accumulated_depreciation"] - r["accumulated_impairment"], "gross/contra identity")
        need(r["cash"] + r["carrying"] == r["equity"], "assets equal equity")
        need(r["cfo"] == r["profit"] + r["depreciation"] + r["impairment_loss"] - r["disposal_gain"], "operating cash bridge")
        need(r["cash"] == previous_cash + r["cfo"] + r["cfi"], "cash rollforward")
        need(r["equity"] == previous_equity + r["profit"], "equity rollforward")
        previous_cash, previous_equity = r["cash"], r["equity"]
    s = {k:F(v) for k,v in report["disposal"].items()}
    need(s["gross_cash"] - s["cash_cost"] == s["net_cash"], "gross sale cash")
    need(s["depreciation_removed"] + s["impairment_removed"] - s["gain"] == s["gross_removed"] - s["net_cash"], "lifetime allocation")
    need(F(report["cumulative_profit"]) == F(report["cash_change"]) == previous_cash - opening, "terminal closure")


def check():
    checks = []
    capture = io.StringIO()
    spec = importlib.util.spec_from_file_location("v07_c04_lab", PROJECT / "v07-c04-analysis.py")
    lab = importlib.util.module_from_spec(spec)
    with redirect_stdout(capture), redirect_stderr(capture):
        spec.loader.exec_module(lab)
        data = json.loads((PROJECT / "v07-c04-inputs.json").read_text())
        output = lab.run(data)
    need(not capture.getvalue(), "quiet import/run")
    json.dumps(output, allow_nan=False)
    # Exact targets written from independent cash and debit/credit calculations.
    targets = [
        [120,"27/2",0,"213/2","27/2",0,0,11,-120,"-5/2",91,"395/2"],
        [120,"75/2",18,"129/2",24,18,0,35,0,-7,126,"381/2"],
        [0,0,0,0,9,0,3,20,"117/2",14,"409/2","409/2"]]
    fields = ["gross","accumulated_depreciation","accumulated_impairment","carrying",
              "depreciation","impairment_loss","disposal_gain","cfo","cfi","profit","cash","equity"]
    snapshots = ledger_reference()
    for row, expected, journal in zip(output["rows"], targets, snapshots):
        need([F(row[k]) for k in fields] == list(map(F, expected)), "independent 12-field period target")
        need(sum(journal.values()) == 0, "trial balance")
        need(F(row["cash"]) == journal["cash"] and F(row["gross"]) == journal["machine"], "journal cash/gross")
        need(F(row["accumulated_depreciation"]) == -journal["ad"] and F(row["accumulated_impairment"]) == -journal["imp"], "journal contra balances")
        need(F(row["equity"]) == -journal["capital"]-journal["income"], "journal equity")
    identities(output)
    checks.append(dict(name="Independent double-entry journal and all three statement bridges", status="pass", exact_period_fields=36))

    # Each variation targets a distinct accounting mechanism, not an exhaustive input grid.
    variants = []
    for parent, key, value in [("sale_2027","gross_receipt","53"),
                               ("impairment_2026","value_in_use","100"),
                               ("revision_2026","remaining_months",24),
                               ("revision_2026","remaining_months",18),
                               ("revision_2026","residual","110")]:
        changed = deepcopy(data); changed[parent][key] = value
        result = lab.run(changed); identities(result); variants.append(result)
    need([F(variants[0]["rows"][-1][k]) for k in ["disposal_gain","profit","cfo","cfi","cash"]] == list(map(F,[-4,7,20,"103/2","395/2"])), "delayed-check targets")
    need(F(variants[1]["rows"][1]["impairment_loss"]) == 0 and F(variants[1]["rows"][1]["carrying"]) == F(165,2), "no write-up when RA exceeds B")
    need(F(variants[4]["rows"][1]["depreciation"]) == F(variants[4]["rows"][2]["depreciation"]) == 0, "residual above B causes zero charge")
    for result in variants[1:]:
        need(F(result["cumulative_profit"]) == F(9,2), "timing cannot alter fixed-cash lifetime profit")
    checks.append(dict(name="Estimate, impairment and disposal transfer cases including answered retention", status="pass", changed_cases=len(variants)))

    need(lab.straight_line(120,12,72,9) == F(27,2), "first partial period")
    need(lab.straight_line(60,65,36,12) == 0, "zero depreciation boundary")
    need(lab.straight_line(60,6,36,36) == 54, "terminal residual")
    need(lab.straight_line(60,6,36,0) == 0, "zero elapsed")
    need(lab.usage(48,8,10000,[1500,0]) == [F(6),F(0)], "usage units and idle period")
    need(lab.impairment(80,45,50) == 30, "impairment uses larger recoverable route")
    need(lab.reversal("37.5",60,90,True) == F(45,2), "reversal ceiling")
    need(lab.reversal("37.5",60,90,False) == 0 and lab.reversal("37.5",60,35,True) == 0, "reversal evidence and downside boundary")
    checks.append(dict(name="Allocation domains, usage and capped reversal", status="pass"))

    # Independently reconstruct every exercise's arithmetic without the lab helpers.
    ex = {}
    c = F(90)-5+3+2+1; d=(c-11)*F(6,60); paid=c+12
    ex["1"]=[c,F(12),d,-12-d,F(-12),-c,150-paid,c-d,150-12-d]
    need(ex["1"] == list(map(F,[91,12,8,-20,-12,-91,47,83,130])), "exercise 1")
    rate=F(81,18000); charges=[rate*h for h in [5000,7000,6000]]
    carry=[F(90)-sum(charges[:i]) for i in [1,2,3]]
    ex["2"]=charges+carry
    need(ex["2"] == list(map(F,["22.5","31.5",27,"67.5",36,9])), "exercise 2")
    b=F(84)-2*F(84-12,6); revised=(b-6)/3
    ex["3"]=[b,revised,*[b-i*revised for i in [1,2,3]],F(84)-2*F(84-6,5)]
    need(ex["3"]==list(map(F,[60,18,42,24,6,"52.8"])), "exercise 3")
    imp=F(120)-2*20-50; next_d=F(50,4); b=50-next_d; ceiling=F(120)-3*20
    ex["4"]=[imp,next_d,b,ceiling-b,ceiling,ceiling/3]
    need(ex["4"]==list(map(F,[30,"12.5","37.5","22.5",60,20])), "exercise 4")
    dep=F(72-12,5); ad=dep*F(5,2); b=72-ad; net=F(46)-2; gain=net-b
    ex["5"]=[dep/2,ad,b,net,gain,-dep/2+gain]
    need(ex["5"]==list(map(F,[6,30,42,44,2,-4])) and net+ad==72+gain, "exercise 5 entry and targets")
    amort=F(6)*F(6,36)+F(33)*F(9,132); immediate=F(9+5+2)
    ex["6"]=[F(39),immediate,amort,immediate+amort,39-amort,F(55)]
    need(ex["6"]==list(map(F,[39,16,"3.25","19.25","35.75",55])), "exercise 6")
    prop_dep=F(72,24); fairgain=F(105-96); claim_i1=F(80,10); claim_i2=(80+claim_i1)/10
    ex["7"]=[96-prop_dep,8-2-prop_dep,F(105),8-2+fairgain,F(8-2-96),claim_i1,claim_i2,claim_i1+claim_i2]
    need(ex["7"]==list(map(F,[93,3,105,15,-90,8,"8.8","16.8"])), "exercise 7")
    ex["8"]=[F(4)-F(4,4),F(4)-F(4,4),F(0),F(4),F(-4)]
    need(ex["8"]==list(map(F,[3,3,0,4,-4])), "exercise 8")
    for c,d,j,s in [(F(120),F("46.5"),F(18),F("58.5")),(F(72),F(30),F(0),F(44)),(F(120),F(80),F(0),F(15))]:
        gain=s-(c-d-j)
        need(d+j-gain==c-s, "telescoping identity samples supplement algebraic proof")
    checks.append(dict(name="All eight exact exercise solutions and balanced disposal", status="pass", results={k:[str(x) for x in v] for k,v in ex.items()}))

    viu=F(30)/F("1.1")+F("36.3")/F("1.1")**2
    need(viu==F(630,11) and 60-viu==F(30,11), "value-in-use worked arithmetic")
    v0=F(55)/F("1.1")+F("60.5")/F("1.1")**2
    v1=F("60.5")/F("1.1")
    need(v0==100 and v1==55 and v0-v1==45, "economic depreciation")
    need(F(55)==v0/10+(v0-v1) and F("60.5")==v1/10+v1, "return/capital recovery")
    need(F(121)/F("1.1")==110 and F(100)*F("1.1")**2==121, "news and financial accretion")
    need(F(24)*F(6,24)==6 and F(60,30)==2 and 5-1+(86-80)==10, "software and property worked examples")
    checks.append(dict(name="Present value, economic depreciation, intangibles and investment examples", status="pass"))

    invalid = []
    for parent,key,value in [(None,"units","CU"),(None,"case","Different calendar"),
                              ("acquisition","invoice",120.0),("acquisition","freight",-1),
                              ("acquisition","residual",121),("revision_2026","remaining_months",17),
                              (None,"opening_cash_and_equity",0)]:
        bad=deepcopy(data)
        (bad if parent is None else bad[parent])[key]=value
        invalid.append(bad)
    for bad in invalid:
        try: lab.run(bad)
        except ValueError: pass
        else: raise AssertionError("unsupported input accepted")
    for fn,args in [(lab.straight_line,(10,0,0,0)),(lab.straight_line,(10,0,12,13)),(lab.usage,(90,9,18000,[18000,2000]))]:
        try: fn(*args)
        except ValueError: pass
        else: raise AssertionError("helper domain violation accepted")
    checks.append(dict(name="Meaningful unit, calendar, funding and depreciation-domain rejection", status="pass", cases=len(invalid)+3))

    damaged=deepcopy(output);damaged["rows"][-1]["cfo"]="23"
    damaged2=deepcopy(output);damaged2["rows"][-1]["accumulated_impairment"]="18"
    for mutant in [damaged,damaged2]:
        try: identities(mutant)
        except AssertionError: pass
        else: raise AssertionError("damaged output not detected")
    checks.append(dict(name="Independent checks reject double-counted gain and undeleted contra balance", status="pass", mutants_caught=2))

    html=(BOOK/"content/chapters/v07-c04.html").read_text(); parser=Fragment();parser.feed(html);parser.close()
    need(not parser.stack and not parser.h1 and parser.worked>=2 and parser.counts==[8,8], "complete chapter fragment structure")
    need("Teach-back benchmark" in html and "Delayed-check answer" in html, "answered instruction checks")
    sources=json.loads((BOOK/"content/reviews/v07-c04-sources.json").read_text())
    ids={s["id"] for s in sources}
    need({x.split("#",1)[1] for x in parser.links if x.startswith("sources.html#")}==ids, "source link coverage")
    need(all(set(s)=={"id","title","url","use","checked","verification"} and s["id"].startswith("v07-c04-") for s in sources), "source schema")
    downloads=[x for x in parser.links if x.startswith("v07-c04-")]
    need(len(downloads)==3 and all("/" not in x and (PROJECT/x).is_file() for x in downloads), "flat downloads")
    checks.append(dict(name="HTML, eight matched exercises, answered retention and seven scoped sources", status="pass", worked_examples=parser.worked, sources=len(ids)))

    with tempfile.TemporaryDirectory(prefix="v07-c04-check-") as temp:
        folder=Path(temp)
        for name in ["v07-c04-analysis.py","v07-c04-inputs.json"]:
            shutil.copyfile(PROJECT/name,folder/name)
        for options in [[],["-O"]]:
            proc=subprocess.run([sys.executable,*options,str(folder/"v07-c04-analysis.py")],cwd=folder,capture_output=True,text=True,check=False)
            need(proc.returncode==0 and not proc.stderr and json.loads(proc.stdout)==output, "portable normal and optimized lab")
        bad=deepcopy(data);bad["units"]="USD";path=folder/"invalid.json";path.write_text(json.dumps(bad))
        proc=subprocess.run([sys.executable,"-O",str(folder/"v07-c04-analysis.py"),str(path)],capture_output=True,text=True,check=False)
        need(proc.returncode!=0 and not proc.stdout and "unsupported unit" in proc.stderr, "invalid unit CLI failure")
    checks.append(dict(name="Portable standalone normal/optimized execution and quiet JSON API", status="pass"))
    report=dict(chapter="v07-c04",status="pass",checks=checks,limitations=[
        "Synthetic fixed-calendar cases; no empirical useful-life, fair-value or impairment estimate is validated.",
        "Exact identities and independent journals support, but do not replace, the written recognition and source-scope audit.",
        "Selected dated AASB/IAS method conventions, not a complete or universally current accounting standard.",
        "No browser, mobile or print visual QA."])
    json.dumps(report,allow_nan=False)
    return report


if __name__ == "__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
