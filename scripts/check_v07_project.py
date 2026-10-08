"""Independent exact Rowan project audit; quiet check() returns strict JSON."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import hashlib
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


class Journal:
    """Signed assets/claims and cash classifications, independent of lab rollforwards."""
    def __init__(self, start):
        self.accounts = dict(start)
        self.cash = {k: F(0) for k in ("operating", "investing", "financing")}
        self.entries = 0
        need(sum(self.accounts.values()) == 0, "opening trial balance")
    def post(self, category, **movements):
        movements = {k: F(v) for k, v in movements.items()}
        need(sum(movements.values()) == 0, "journal entry fails")
        for k, v in movements.items(): self.accounts[k] = self.accounts.get(k, F(0)) + v
        if category is not None: self.cash[category] += movements.get("cash", F(0))
        need(sum(self.accounts.values()) == 0, "journal prefix fails")
        self.entries += 1


def historical_journal(corrected):
    j = Journal({k: F(v) for k, v in dict(cash=25, receivables=50, inventory=75, ppe=200,
        payables=-40, tax_payable=0, dtl=0, term_debt=-120, revolver=0,
        share_capital=-100, retained_earnings=-90).items()})
    j.post(None, receivables=800, retained_earnings=-800)
    j.post("operating", cash=760, receivables=-760)
    j.post(None, inventory=505, payables=-505)
    j.post("operating", cash=-480, payables=480)
    j.post(None, inventory=-480, retained_earnings=480)
    j.post("operating", cash=-170, retained_earnings=170)
    if corrected: j.post("operating", cash=-20, retained_earnings=20)
    else: j.post("investing", cash=-20, ppe=20)
    j.post(None, ppe=-40, retained_earnings=40)
    j.post("operating", cash=-12, retained_earnings=12)
    j.post(None, tax_payable=F(-39, 2), retained_earnings=F(39, 2))
    j.post("operating", cash=-15, tax_payable=15)
    if not corrected: j.post(None, dtl=-5, retained_earnings=5)
    j.post("investing", cash=-60, ppe=60)
    j.post("financing", cash=-10, term_debt=10)
    j.post("financing", cash=30, revolver=-30)
    j.post("financing", cash=-20, retained_earnings=20)
    return j


def forecast_journal(adverse):
    j = Journal(historical_journal(True).accounts)
    if adverse:
        sales, cogs, purchases, receipts, suppliers, tax, tax_cash = map(F, [840, 525, "582.5", 762, 531, 11, "15.5"])
        capex, draw, issue, dividend = map(F, [50, 45, "25.5", 0])
    else:
        sales, cogs, purchases, receipts, suppliers, tax, tax_cash = map(F, [900, 540, 575, 882, 525, "22.25", "26.75"])
        capex, draw, issue, dividend = map(F, [80, "5.75", 0, 20])
    j.post(None, receivables=sales, retained_earnings=-sales)
    j.post("operating", cash=receipts, receivables=-receipts)
    j.post(None, inventory=purchases, payables=-purchases)
    j.post("operating", cash=-suppliers, payables=suppliers)
    j.post(None, inventory=-cogs, retained_earnings=cogs)
    j.post("operating", cash=-185, retained_earnings=185)
    j.post("operating", cash=-20, retained_earnings=20)
    j.post(None, ppe=-52, retained_earnings=52)
    j.post("operating", cash=-14, retained_earnings=14)
    j.post(None, tax_payable=-tax, retained_earnings=tax)
    j.post("operating", cash=-tax_cash, tax_payable=tax_cash)
    j.post("investing", cash=-capex, ppe=capex)
    j.post("financing", cash=draw, revolver=-draw)
    j.post("financing", cash=-20, term_debt=20)
    j.post("financing", cash=issue, share_capital=-issue)
    j.post("financing", cash=-dividend, retained_earnings=dividend)
    return j


def compare_journal(row, journal):
    assets = {"cash", "receivables", "inventory", "ppe"}
    for key, value in journal.accounts.items():
        need(F(row["closing"][key]) == (value if key in assets else -value), "independent journal balance " + key)
    for kind, field in [("operating", "cfo"), ("investing", "cfi"), ("financing", "cff")]:
        need(F(row["cash_flow"][field]) == journal.cash[kind], "independent cash classification " + field)


def identities(row):
    o, b, income, cash = [row[k] for k in ("opening", "closing", "income", "cash_flow")]
    q = lambda data, key: F(data[key])
    need(q(b, "assets") == q(b, "liabilities") + q(b, "equity"), "A=L+E")
    direct = q(cash, "receipts") - sum(q(cash, k) for k in ("supplier_payments", "ordinary_opex_paid", "operating_maintenance_paid", "interest_paid", "tax_paid"))
    indirect = q(income, "net_income") + q(income, "depreciation") + q(income, "deferred_tax_expense") - q(cash, "nwc_increase") + q(b, "tax_payable") - q(o, "tax_payable")
    need(q(cash, "cfo") == direct == indirect == q(cash, "indirect_cfo"), "independent cash routes")
    cff = q(cash, "revolver_change") - q(cash, "term_repayment") + q(cash, "equity_issue") - q(cash, "dividend")
    need(cff == q(cash, "cff"), "financing excludes principal exactly once")
    need(q(b, "cash") - q(o, "cash") == direct + q(cash, "cfi") + cff == q(cash, "cash_change"), "cash rollforward")
    need(q(b, "equity") == q(o, "equity") + q(income, "net_income") + q(cash, "equity_issue") - q(cash, "dividend"), "owner claim rollforward")
    need(q(b, "debt") == q(o, "debt") + q(cash, "revolver_change") - q(cash, "term_repayment"), "total debt rollforward")
    need(q(b, "ppe") == q(o, "ppe") + q(cash, "genuine_capex") + q(cash, "invalid_capitalized_payment") - q(income, "depreciation"), "equipment rollforward")
    need(q(b, "tax_payable") == q(o, "tax_payable") + q(income, "current_tax") - q(cash, "tax_paid"), "current tax rollforward")
    need(q(b, "dtl") == q(o, "dtl") + q(income, "deferred_tax_expense"), "deferred tax rollforward")
    need(q(b, "invested_capital") == q(b, "debt") + q(b, "equity") - q(b, "cash"), "capital financing reconciliation")
    ratios = row["ratios"]
    need(F(ratios["net_margin"]) * F(ratios["asset_turnover"]) * F(ratios["equity_multiplier"]) == F(ratios["roe"]), "DuPont cancellation")
    need(F(ratios["roic"]) == F(ratios["nopat"]) / ((q(o, "invested_capital") + q(b, "invested_capital")) / 2), "matched ROIC")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ids=[]; self.links=[]; self.points=[]; self.h1=0; self.deliverables=0; self.in_deliverables=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if "id" in a:self.ids.append(a["id"])
        if tag=="h1":self.h1+=1
        if tag=="h2" and a.get("id")=="project":self.project=True
        if tag=="a":self.links.append(a.get("href",""))
        if tag=="tr" and "data-points" in a:self.points.append(int(a["data-points"]))
        if tag=="ol" and a.get("class")=="project-deliverables":self.in_deliverables=True
        if tag=="li" and self.in_deliverables:self.deliverables+=1
        if tag not in {"br","hr","img","input","meta","link"}:self.stack.append(tag)
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1]==tag,"HTML nesting "+tag);self.stack.pop()
        if tag=="ol":self.in_deliverables=False


def check():
    groups=[]; captured=io.StringIO()
    spec=importlib.util.spec_from_file_location("rowan_project",PROJECT/"v07-assessment-analysis.py")
    lab=importlib.util.module_from_spec(spec)
    data=json.loads((PROJECT/"v07-assessment-inputs.json").read_text())
    with redirect_stdout(captured),redirect_stderr(captured):
        spec.loader.exec_module(lab); result=lab.run(data)
    need(not captured.getvalue(),"quiet import/run")
    json.dumps(result,allow_nan=False)
    journal_entries=0
    for key,j in [("historical_draft",historical_journal(False)),("historical_corrected",historical_journal(True)),("base",forecast_journal(False)),("adverse_funded_repair",forecast_journal(True))]:
        compare_journal(result[key],j);identities(result[key]);journal_entries+=j.entries
    identities(result["adverse_full_subscription"])
    groups.append({"name":"Independent signed historical and forecast journals, all statements and rollforwards","status":"pass","balanced_entries":journal_entries})
    draft, corrected = result["historical_draft"], result["historical_corrected"]
    for key in ("cash","receivables","inventory","payables","tax_payable","debt","shares"):
        need(draft["closing"][key]==corrected["closing"][key],"correction invariant "+key)
    need(draft["income"]["current_tax"]==corrected["income"]["current_tax"]=="39/2","current tax unaffected")
    need([result["correction"][k] for k in ("net_income_change","cfo_change","cfi_change","cash_change")]==["-15","-20","20","0"],"correction four-way effects")
    need(draft["closing"]["assets"]=="458" and corrected["closing"]["assets"]=="438","historical total assets")
    need(draft["closing"]["dtl"]=="5" and corrected["closing"]["dtl"]=="0","reported DTL removed")
    for row in (draft,corrected): need(F(row["cash_flow"]["cfo"])+F(row["cash_flow"]["cfi"])==3,"same total operating/investing cash")
    groups.append({"name":"Documented correction preserves actual tax/cash and reclassifies CFO/CFI","status":"pass"})
    base=result["base"]; adverse=result["adverse"];repair=result["adverse_funded_repair"]
    need([base["income"]["net_income"],base["cash_flow"]["cfo"],base["closing"]["revolver"],base["closing"]["assets"]]==["267/4","445/4","143/4","516"],"base anchors")
    for name,required,gap,actual in [("adverse","301/2","151/2","-101/2"),("adverse_dividend_cut","261/2","111/2","-61/2"),("adverse_max_deferral","201/2","51/2","-1/2")]:
        row=result[name];need(row["status"]=="unfunded" and row["closing"] is None and "cff" not in row["cash_flow"],"rejected closing suppressed")
        need([row["funding"][k] for k in ("required_revolver","gap_to_minimum","cash_after_maximum_draw")]==[required,gap,actual],"funding sequence "+name)
        need(row["income"]["net_income"]=="33" and row["cash_flow"]["cfo"]=="-7/2","repair does not fabricate operating profit/cash")
    need([repair["closing"][k] for k in ("cash","revolver","ppe","equity","assets")]==["25","75","218","287","1137/2"],"repair full balance")
    need([repair["cash_flow"][k] for k in ("cfo","cfi","cff","cash_change")]==["-7/2","-50","101/2","-3"],"repair CFF is50.5 and total cash change-3")
    need(result["subscription"]["new_shares"]=="17/2" and result["subscription"]["new_investor_fraction"]=="17/217","post-money share count")
    need(result["adverse_full_subscription"]["closing"]["revolver"]=="141/2","full subscription retains4.5 borrowing room")
    groups.append({"name":"Funding limits, minimal repair, all cash classes and ownership","status":"pass"})
    targets={"historical_draft":["11/80","166/147","55/6","436/239","236/239","98/289","110/427"],
             "historical_corrected":["9/80","14/13","15/2","436/239","236/239","26/93","30/139"],
             "base":["103/900","5/3","103/14","1072/683","532/683","534/2015","309/1433"],
             "adverse_funded_repair":["29/420","-7/66","29/7","701/423","386/423","132/1031","174/1535"]}
    for name,values in targets.items():
        need([result[name]["ratios"][k] for k in ("operating_margin","cfo_to_income","interest_coverage","current_ratio","quick_ratio","roe","roic")]==values,"all printed ratio anchors "+name)
    groups.append({"name":"Twenty-eight diagnostic anchors with matched DuPont/capital denominators","status":"pass"})

    # Different approach: eliminate the cash identity to derive the AR boundary.
    # Max total sources are28 opening+762 receipts+45 loan+30 equity; fixed
    # payments are531 suppliers+205 operations+14 interest+15.5 tax+50capex+20term.
    cash_at_full_sources=F(28+762+45+30)-F(531+205+14)-F("15.5")-50-20
    maximum_ar=F(168)+cash_at_full_sources-25
    need(maximum_ar==F("172.5") and maximum_ar/840==F(23,112),"independent collection boundary")
    boundary=deepcopy(data);boundary["scenarios"]["adverse"]["receivables_sales"]=str(maximum_ar/840)
    br=lab.run(boundary)["adverse_full_subscription"]
    need(br["closing"]["cash"]=="25" and br["closing"]["revolver"]=="75" and br["cash_flow"]["cfo"]=="-8","boundary attains constraints")
    identities(br)
    boundary["scenarios"]["adverse"]["receivables_sales"]=str((maximum_ar+1)/840)
    beyond=lab.run(boundary)
    need(beyond["adverse_funded_repair"] is None and beyond["adverse_full_subscription"]["funding"]["gap_to_minimum"]=="1","one beyond boundary cannot be funded")
    need(beyond["adverse_full_subscription"]["funding"]["cash_after_maximum_draw"]=="24","beyond-boundary actual cash")
    short=deepcopy(data);short["forecast_policy"]["subscription_capacity"]=25
    sr=lab.run(short)
    need(sr["adverse_funded_repair"] is None and sr["adverse_full_subscription"]["funding"]["gap_to_minimum"]=="1/2","no invented owner capital")
    tax=deepcopy(data);tax["historical"]["current_tax_paid"]=16
    tr=lab.run(tax)
    need(tr["historical_corrected"]["closing"]["cash"]=="27" and tr["historical_corrected"]["closing"]["tax_payable"]=="7/2","historical tax timing")
    need(tr["base"]["cash_flow"]["cfo"]=="449/4" and tr["base"]["closing"]==base["closing"],"extra earlier tax is not paid twice")
    groups.append({"name":"Exact collection boundary, beyond-boundary refusal, equity-cap failure and tax-timing transfer","status":"pass"})

    failures=[("units",lambda d:d.update(units="USD")),("opening balance",lambda d:d["opening"].update(cash=26)),
              ("overdepreciation",lambda d:d["forecast_policy"].update(old_asset_depreciation=201)),
              ("unsupported loss",lambda d:d["scenarios"]["adverse"].update(price=1)),
              ("interest timing",lambda d:d["historical"].update(interest_paid=13)),
              ("floating input",lambda d:d["historical"].update(quantity=80.0)),
              ("subscription price",lambda d:d["forecast_policy"].update(subscription_price=0)),
              ("capex contradiction",lambda d:d["forecast_policy"].update(minimum_capex=81))]
    for name,change in failures:
        bad=deepcopy(data);change(bad)
        try:lab.run(bad)
        except ValueError:pass
        else:raise AssertionError("invalid project accepted: "+name)
    for name in ("financing double count","correction invented cash"):
        bad=deepcopy(repair if name=="financing double count" else corrected)
        if name=="financing double count":bad["cash_flow"]["cff"]="151/2"
        else:bad["closing"]["cash"]="13"
        try:identities(bad)
        except AssertionError:pass
        else:raise AssertionError("audit missed "+name)
    groups.append({"name":"Eight meaningful domain failures and two consequential wrong-result detectors","status":"pass"})

    html=(BOOK/"content/assessments/parts/v07-project.html").read_text()
    fragment=Fragment();fragment.feed(html);fragment.close()
    need(not fragment.stack and fragment.h1==0 and getattr(fragment,"project",False),"project fragment structure")
    need(len(fragment.ids)==len(set(fragment.ids)) and fragment.deliverables==6,"stable IDs and six deliverables")
    need(fragment.points==[20,20,25,15,10,10] and sum(fragment.points)==100,"100point rubric")
    records=json.loads((BOOK/"content/reviews/v07-project-sources.json").read_text())
    need({r["id"] for r in records}=={x.split("#")[1] for x in fragment.links if x.startswith("sources.html#")},"scoped source IDs")
    for name in ("inputs.json","analysis.py","output.json","README.txt","manifest.json"):
        full="v07-assessment-"+name
        need(full in fragment.links and (PROJECT/full).is_file(),"flat offline link "+full)
    need("<strong>50.5</strong>" in html and "CFI-50/CFF50.5" in (PROJECT/"v07-assessment-README.txt").read_text(),"reviewed repaired cash-flow labels")
    preserved=json.loads((PROJECT/"v07-assessment-output.json").read_text())
    need(preserved==result,"preserved output equals exact benchmark")
    manifest=json.loads((PROJECT/"v07-assessment-manifest.json").read_text())
    for item in manifest["files"]:
        payload=(PROJECT/item["file"]).read_bytes()
        need(len(payload)==item["bytes"] and hashlib.sha256(payload).hexdigest()==item["sha256"],"manifest payload "+item["file"])
    with tempfile.TemporaryDirectory(prefix="rowan-project-") as directory:
        temporary=Path(directory)
        for name in ("v07-assessment-inputs.json","v07-assessment-analysis.py"):
            shutil.copy2(PROJECT/name,temporary/name)
        for flags in ([],["-O"]):
            cli=subprocess.run([sys.executable,*flags,str(temporary/"v07-assessment-analysis.py")],cwd=temporary.parent,capture_output=True,text=True,check=False)
            need(cli.returncode==0 and not cli.stderr and json.loads(cli.stdout)==result,"portable normal/optimized CLI")
    groups.append({"name":"Full fragment/rubric, sources, preserved output, manifest and portable quiet JSON","status":"pass"})
    result={"project":"v07","status":"passed","checks":groups,"limitations":["Synthetic conditional evidence and annual financing; no current compliance, intent or intrayear-liquidity certification.","Browser/mobile/print visual QA remains separate."]}
    json.dumps(result,allow_nan=False)
    return result


if __name__=="__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
