"""Independent finite-case checks for v11-c01. check() is quiet and -O safe."""
import contextlib
import copy
from fractions import Fraction as Q
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects"
MODEL = PROJECT / "v11-c01-analysis.py"
INPUT = PROJECT / "v11-c01-inputs.json"
OUTPUT = PROJECT / "v11-c01-output.json"
README = PROJECT / "v11-c01-README.txt"
MANIFEST = PROJECT / "v11-c01-manifest.json"
CHAPTER = ROOT / "content/chapters/v11-c01.html"
SOURCES = ROOT / "content/reviews/v11-c01-sources.json"
AUTHOR = ROOT / "content/reviews/v11-c01-author.json"


def _need(test, reason):
    if not test:
        raise ValueError("v11-c01 check: " + reason)


def _load():
    spec = importlib.util.spec_from_file_location("v11_c01_checked_model", MODEL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wire(x):
    if isinstance(x,Q) or type(x) is int:
        return str(x)
    if isinstance(x,dict):
        return {k:_wire(v) for k,v in x.items()}
    if isinstance(x,list):
        return [_wire(v) for v in x]
    return x


class _Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.worked = 0
        self.prompts = 0
        self.solutions = 0
        self.exercise_depth = 0
        self.solution_depth = 0
        self.sources = set()
        self.links = []

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        classes=a.get("class","").split()
        if tag=="aside" and "worked" in classes:
            self.worked+=1
        if tag=="ol" and "exercises" in classes:
            self.exercise_depth=1
        elif tag=="ol" and self.exercise_depth:
            self.exercise_depth+=1
        if tag=="details" and "solutions" in classes:
            self.solution_depth=1
        if tag=="li":
            self.prompts+=bool(self.exercise_depth)
            self.solutions+=bool(self.solution_depth)
        if "data-source" in a:
            self.sources.add(a["data-source"])
        if tag=="a":
            self.links.append(a.get("href"))

    def handle_endtag(self,tag):
        if tag=="ol" and self.exercise_depth:
            self.exercise_depth-=1
        if tag=="details":
            self.solution_depth=0


def check(require_bindings=True):
    counts={"comparisons":0,"invalid_inputs_rejected":0,"intervention_groups":0,
            "screening_joint_states":0,"bank_journal_snapshots":0,"liquidity_rows":0,
            "portable_model_runs":0,"cli_rejections":0,"bound_author_payloads":0}

    def equal(actual,expected,label):
        counts["comparisons"]+=1
        _need(actual==_wire(expected),label+": "+repr(actual)+" != "+repr(_wire(expected)))

    def truth(value,label):
        counts["comparisons"]+=1
        _need(value,label)

    quiet=io.StringIO()
    with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
        model=_load()
    truth(not quiet.getvalue(),"quiet import")
    base=json.loads(INPUT.read_text())

    def evaluate(data):
        saved=copy.deepcopy(data)
        log=io.StringIO()
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            got=model.run(data)
        truth(not log.getvalue(),"quiet run")
        truth(data==saved,"nonmutating run")
        json.dumps(got,allow_nan=False)
        return got

    result=evaluate(base)
    equal(result,json.loads(OUTPUT.read_text()),"saved exact output")

    def screen_oracle(data,got):
        x={k:Q(v) for k,v in data.items()}
        # Independently enumerate quality x signal x repayment outcomes.
        states=[]
        for good,prior,p,pass_rate in ((True,x["good_prior"],x["good_success"],x["good_pass"]),
                                      (False,1-x["good_prior"],x["bad_success"],x["bad_pass"])):
            for passed,signal_prob in ((True,pass_rate),(False,1-pass_rate)):
                for success,outcome_prob,payoff in ((True,p,x["success_repayment"]),
                                                    (False,1-p,x["failure_recovery"])):
                    states.append((good,passed,success,prior*signal_prob*outcome_prob,payoff))
        counts["screening_joint_states"]+=len(states)
        total=sum(s[3] for s in states)
        equal(str(total),Q(1),"joint probability normalization")
        whole_receipt=sum(s[3]*s[4] for s in states)
        whole_success=sum(s[3] for s in states if s[2])
        branches=[]
        positive=Q(0)
        funded=Q(0)
        for passed in (True,False):
            rows=[s for s in states if s[1]==passed]
            mass=sum(s[3] for s in rows)
            label="pass" if passed else "fail"
            if not mass:
                branches.append({"signal":label,"mass":Q(0),"good_posterior":None,
                                 "success_probability":None,"expected_receipt":None,
                                 "loan_margin":None,"fund":False})
            else:
                receipt=sum(s[3]*s[4] for s in rows)/mass
                margin=receipt-x["principal"]
                branches.append({"signal":label,"mass":mass,
                                 "good_posterior":sum(s[3] for s in rows if s[0])/mass,
                                 "success_probability":sum(s[3] for s in rows if s[2])/mass,
                                 "expected_receipt":receipt,"loan_margin":margin,"fund":margin>0})
                if margin>0:
                    positive+=mass*margin
                    funded+=mass
        no_test=max(Q(0),whole_receipt-x["principal"])
        net=positive-x["test_cost"]
        expected={"funding_threshold_probability":(x["principal"]-x["failure_recovery"])/(x["success_repayment"]-x["failure_recovery"]),
                  "pooled_success":whole_success,"pooled_receipt":whole_receipt,
                  "pooled_loan_margin":whole_receipt-x["principal"],"branches":branches,
                  "funded_mass_if_tested":funded,"gross_test_policy_value":positive,
                  "no_test_policy_value":no_test,"gross_information_value":positive-no_test,
                  "net_test_policy_value":net,"optimal_value":max(net,no_test),"choose_test":net>no_test,
                  "maximum_test_cost_against_no_test":positive-no_test}
        for key,value in expected.items():
            equal(got[key],value,"screening "+key)
        truth(positive>=no_test,"gross information cannot hurt in supported choice problem")

    def monitor_oracle(data,got):
        x={k:Q(v) for k,v in data.items() if k!="claimants"}
        n=data["claimants"]
        residual=x["success_cash"]-x["debt"]
        threshold=residual*(x["prudent_success"]-x["divert_success"])
        diverts=x["private_benefit"]>threshold
        old=(x["divert_success"] if diverts else x["prudent_success"])*x["debt"]
        new=x["prudent_success"]*x["debt"]
        equal(got["private_benefit_indifference"],threshold,"borrower IC boundary")
        equal(got["unmonitored_action"],"divert" if diverts else "prudent","borrower best reply")
        equal(got["borrower_prudent_payoff"],x["prudent_success"]*residual,"prudent borrower payoff")
        equal(got["borrower_divert_payoff"],x["divert_success"]*residual+x["private_benefit"],"divert borrower payoff")
        equal(got["borrower_divert_payoff_after_enforcement"],x["divert_success"]*residual,"enforced borrower payoff")
        equal(got["unmonitored_receipt"],old,"unmonitored debt receipt")
        equal(got["monitored_receipt"],new,"enforced debt receipt")
        equal(got["aggregate_audit_gain"],new-old,"enforcement receipt gain")
        equal(got["one_claimant_audit_gain"],(new-old)/n,"claimant share of gain")
        # Compare the exact two unilateral action payoffs rather than a stored flag.
        none=old/n
        alone=new/n-x["audit_cost"]
        equal(got["no_audit_is_nash_given_loan"],none>=alone,"no-audit Nash criterion")
        equal(got["no_audit_is_strict_given_loan"],none>alone,"strict no-audit criterion")
        outlay=x["principal"]+x["audit_cost"]+x["delegation_cost"]
        equal(got["pooled_initial_funding"],outlay,"all initial monitoring funding")
        equal(got["pooled_expected_surplus"],new-outlay,"pooled net surplus")
        equal(got["pooled_funding_is_profitable"],new>outlay,"pooled strict finance flag")
        equal(got["unmonitored_expected_surplus"],old-x["principal"],"unmonitored net surplus")
        equal(got["all_duplicate_expected_surplus"],new-x["principal"]-n*x["audit_cost"],"duplicate costs")
        equal(got["largest_delegation_cost_for_nonnegative_surplus"],new-x["principal"]-x["audit_cost"],"delegation cap")

    def bank_oracle(data,got):
        x={k:Q(v) for k,v in data.items()}
        # Journal vectors are (cash, loans, deposits, equity), including equity
        # independently instead of calculating it as the residual after every event.
        a=[x["a_reserves"],x["a_loans"],x["a_deposits"],x["a_reserves"]+x["a_loans"]-x["a_deposits"]]
        b=[x["b_reserves"],x["b_loans"],x["b_deposits"],x["b_reserves"]+x["b_loans"]-x["b_deposits"]]
        L,P=x["new_loan"],x["external_payment"]
        journal=[([0,0,0,0],[0,0,0,0]),([0,L,L,0],[0,0,0,0]),([-P,0,-P,0],[P,0,P,0])]

        def inspect(actual,v,label):
            counts["bank_journal_snapshots"]+=1
            for key,value in zip(("reserves","loans","deposits","equity"),v):
                equal(actual[key],value,label+" "+key)
            equal(actual["assets"],v[0]+v[1],label+" assets")
            truth(v[0]+v[1]==v[2]+v[3],label+" accounting identity")
            equal(actual["equity_assets"],v[3]/(v[0]+v[1]) if v[0]+v[1]>0 else None,label+" book ratio")

        for i,(da,db) in enumerate(journal):
            a=[v+d for v,d in zip(a,da)]
            b=[v+d for v,d in zip(b,db)]
            row=got["two_bank_ledger"][i]
            inspect(row["A"],a,"A journal")
            inspect(row["B"],b,"B journal")
            inspect(row["consolidated"],[u+v for u,v in zip(a,b)],"consolidation")
        opening=a[:]
        probe=got["immediate_probe_before_income"]
        gap=max(Q(0),x["immediate_withdrawal_probe"]-a[0])
        equal(probe,{"requested":x["immediate_withdrawal_probe"],"cash_available":a[0],"cash_gap":gap,
                     "executable":gap==0,"book_equity":a[3]},"dated probe")
        I,F,J,O,W=(x[k] for k in ("interest_received","fees_received","interest_paid","operating_cash_cost","direct_unprovided_loss"))
        for i,delta in enumerate(([0,0,0,0],[I,0,0,I],[F,0,0,F],[-J,0,0,-J],[-O,0,0,-O],[0,-W,0,-W])):
            a=[v+d for v,d in zip(a,delta)]
            inspect(got["A_later_income_ledger"][i],a,"income journal")
        profit=a[3]-opening[3]
        avgL=(a[1]+opening[1])/2
        avgA=(sum(a[:2])+sum(opening[:2]))/2
        avgE=(a[3]+opening[3])/2
        expected={"net_interest_income":I-J,"net_external_cash_receipts":a[0]-opening[0],
                  "direct_loss_without_prior_allowance":W,"profit":profit,
                  "average_earning_loans":avgL,"average_assets":avgA,"average_equity":avgE,
                  "net_interest_margin":(I-J)/avgL if avgL>0 else None,
                  "return_on_assets":profit/avgA if avgA>0 else None,
                  "return_on_equity":profit/avgE if avgE>0 else None,
                  "gross_loan_yield":I/avgL if avgL>0 else None,
                  "deposit_funding_rate":J/opening[2] if opening[2]>0 else None,
                  "closing_book_insolvent":a[3]<0}
        for key,value in expected.items():
            equal(got[key],value,"bank "+key)

    def liquidity_oracle(data,got):
        M,lam,ell,R,c,a=(Q(data[k]) for k in ("initial_fund","early_fraction","liquidation_return","maturity_return","early_claim","utility_shift"))
        utility=lambda z:-1/(z+a)

        def inspect(row,w):
            counts["liquidity_rows"]+=1
            cash=min(M*ell,M*w*c)
            sold=cash/ell
            survivors=M-sold
            served=cash/c
            prob=served/(M*w)
            waiters=M-M*w
            terminal=survivors*R
            waiting=terminal/waiters if waiters else None
            eu=prob*utility(c)+(1-prob)*utility(Q(0))
            expected={"withdrawal_fraction":w,"claimant_mass":M*w,"served_mass":served,
                      "served_probability":prob,"date1_cash_paid":cash,"long_asset_liquidated":sold,
                      "long_asset_held":survivors,"date2_cash_available":terminal,"waiter_mass":waiters,
                      "cash_per_waiter":waiting,"expected_cash_per_withdrawer":cash/(M*w),
                      "expected_utility_per_withdrawer":eu}
            for key,value in expected.items():
                equal(row[key],value,"liquidity row "+key)
            truth(sold+survivors==M,"long-asset conservation")
            truth(M*w*prob*c==cash,"queue total cash")
            truth(eu<=utility(cash/(M*w)),"concavity and service lottery")
            return waiting,eu

        waiting,normal_draw_eu=inspect(got["candidate_no_run"],lam)
        _,run_eu=inspect(got["full_run"],Q(1))
        for row,w in zip(got["scenarios"],data["withdrawal_fractions"]):
            inspect(row,Q(w))
        equal(str(len(got["scenarios"])),len(data["withdrawal_fractions"]),"scenario count")
        # Solve c(1-w)=R(1-w*c/ell) by independent line intersection.
        threshold=(c-R)/(c-R*c/ell)
        direct=lam*utility(ell)+(1-lam)*utility(R)
        normal=lam*normal_draw_eu+(1-lam)*utility(waiting)
        expected={"withdrawal_capacity_fraction":ell/c,"late_indifference_withdrawal_fraction":threshold,
                  "candidate_no_run_fully_pays_early":M*lam*c<=M*ell,
                  "candidate_no_run_incentive_compatible":M*lam*c<=M*ell and waiting>=c,
                  "candidate_no_run_expected_utility":normal,"direct_all_long_expected_utility":direct,
                  "candidate_utility_gain_over_all_long":normal-direct,
                  "full_run_wait_deviation_consumption":Q(0),"full_run_wait_deviation_utility":utility(Q(0)),
                  "full_run_withdrawal_is_strict_best_reply":run_eu>utility(Q(0))}
        for key,value in expected.items():
            equal(got[key],value,"liquidity "+key)
        truth(0<threshold<ell/c<1,"threshold/capacity ordering")

    screen_oracle(base["screening"],result["screening"])
    monitor_oracle(base["monitoring"],result["monitoring"])
    bank_oracle(base["bank"],result["bank"])
    liquidity_oracle(base["liquidity"],result["liquidity"])

    def intervene(section,changes,oracle):
        data=copy.deepcopy(base)
        data[section].update(changes)
        got=evaluate(data)
        oracle(data[section],got[section])
        counts["intervention_groups"]+=1
        return got[section]

    varied=intervene("screening",{"good_prior":"1/2"},screen_oracle)
    equal(varied["net_test_policy_value"],Q(-1,2),"exercise1 net value")
    equal(varied["maximum_test_cost_against_no_test"],Q(5,2),"exercise1 test cap")
    tied=intervene("screening",{"test_cost":"22/5"},screen_oracle)
    truth(not tied["choose_test"],"test-cost tie convention")
    expensive=intervene("screening",{"test_cost":"23/5"},screen_oracle)
    equal(expensive["optimal_value"],Q(0),"expensive-test refusal")
    no_information=intervene("screening",{"good_pass":"1/2","bad_pass":"1/2"},screen_oracle)
    equal(no_information["gross_information_value"],Q(0),"uninformative signal")
    reverse=intervene("screening",{"good_pass":"1/5","bad_pass":"4/5"},screen_oracle)
    equal(reverse["net_test_policy_value"],Q(7,5),"reversing labels preserves value")
    truth(reverse["branches"][1]["fund"] and not reverse["branches"][0]["fund"],"reversed screening branch funded")
    empty=intervene("screening",{"good_prior":"1","good_pass":"1"},screen_oracle)
    truth(empty["branches"][1]["good_posterior"] is None,"zero-probability signal")
    all_fund=intervene("screening",{"principal":"10"},screen_oracle)
    equal(all_fund["gross_information_value"],Q(0),"always-fundable loans give no information gain")
    six=intervene("monitoring",{"claimants":6},monitor_oracle)
    truth(not six["no_audit_is_nash_given_loan"],"six-claimant deviation")
    # Exactly one enforcer: enforcer gains1 by staying; other duplicates lose5.
    equal(str((Q(108,6)-5)-Q(72,6)),Q(1),"exercise3 sole enforcer incentive")
    equal(str((Q(108,6)-5)-Q(108,6)),Q(-5),"exercise3 duplicate incentive")
    b_tie=intervene("monitoring",{"private_benefit":"6"},monitor_oracle)
    equal(b_tie["unmonitored_expected_surplus"],Q(8),"borrower tie makes monitoring unnecessary")
    d_tie=intervene("monitoring",{"delegation_cost":"3"},monitor_oracle)
    equal(d_tie["pooled_expected_surplus"],Q(0),"delegation break even")
    bad_d=intervene("monitoring",{"delegation_cost":"4"},monitor_oracle)
    equal(bad_d["pooled_expected_surplus"],Q(-1),"delegation failure is valid data")
    smaller=intervene("bank",{"new_loan":"18","external_payment":"18"},bank_oracle)
    truth(smaller["immediate_probe_before_income"]["executable"],"exercise4 revised cash")
    equal(smaller["two_bank_ledger"][2]["A"]["equity_assets"],Q(3,25),"exercise4 book ratio")
    for loss,eq,profit in ((22,3,-15),(25,0,-18),(26,-1,-19),(43,-18,-36),(162,-137,-155)):
        changed=intervene("bank",{"direct_unprovided_loss":str(loss)},bank_oracle)
        equal(changed["A_later_income_ledger"][-1]["equity"],Q(eq),"loss capital boundary")
        equal(changed["profit"],Q(profit),"loss income boundary")
    zero_loans=intervene("bank",{"a_reserves":"200","a_loans":"0","new_loan":"0","external_payment":"0","direct_unprovided_loss":"0","interest_received":"0"},bank_oracle)
    truth(zero_loans["net_interest_margin"] is None,"zero average-loan denominator")
    exact=intervene("liquidity",{"early_fraction":"8/11","withdrawal_fractions":["8/11","10/11","1"]},liquidity_oracle)
    truth(exact["candidate_no_run_incentive_compatible"],"weak late IC at exact threshold")
    equal(exact["candidate_no_run"]["cash_per_waiter"],Q(11,10),"exact threshold consumption")
    late=intervene("liquidity",{"early_fraction":"4/5","withdrawal_fractions":["4/5","10/11","1"]},liquidity_oracle)
    truth(late["candidate_no_run_fully_pays_early"] and not late["candidate_no_run_incentive_compatible"],"feasible does not imply IC")
    over=intervene("liquidity",{"early_fraction":"19/20","withdrawal_fractions":["19/20","1"]},liquidity_oracle)
    truth(not over["candidate_no_run_fully_pays_early"],"early demand exhaustion is output")
    haircut=intervene("liquidity",{"liquidation_return":"4/5","withdrawal_fractions":["1/4","8/11","1"]},liquidity_oracle)
    equal(haircut["withdrawal_capacity_fraction"],Q(8,11),"haircut capacity")
    scaled=intervene("liquidity",{"initial_fund":"7/2"},liquidity_oracle)
    equal(scaled["full_run"]["expected_utility_per_withdrawer"],Q(-5,3),"population scale does not change individual payoff")

    # Exercise5 cash-capital and funding entries independently conserve each side.
    for label,v,extra_debt in (("equity before",[5,162,144,23],0),
                               ("equity after",[0,162,139,23],0),
                               ("borrowing before",[5,162,144,18],5),
                               ("borrowing after",[0,162,139,18],5),
                               ("deposit conversion",[0,162,139,23],0)):
        truth(v[0]+v[1]==v[2]+v[3]+extra_debt,label+" exercise balance")
    equal(str(Q(18,168)),Q(3,28),"same-bank payment ratio")
    equal(str(-Q(245,352)+Q(515,744)),Q(-125,32736),"exercise7 exact utility difference")
    equal(str(Q(10,11)*(-Q(5,6))+Q(1,11)*(-10)),Q(-5,3),"exercise7 run expected utility")

    def invalid(data,label):
        before=copy.deepcopy(data)
        try:
            with contextlib.redirect_stdout(quiet),contextlib.redirect_stderr(quiet):
                model.run(data)
        except ValueError:
            counts["invalid_inputs_rejected"]+=1
        else:
            raise ValueError("invalid input accepted: "+label)
        truth(data==before,"rejected input unchanged: "+label)

    for value in (None,[],True,{},dict(base,extra="x")):
        invalid(value,"root domain")
    for value in (1,1.0,True,None,[],{},"NaN","Infinity","1e0"," 1","+1","01","1/0","1/-2","1"*33,"1/1000000001","1000000001","-1"):
        bad=copy.deepcopy(base)
        bad["screening"]["principal"]=value
        invalid(bad,"strict rational principal")
    cases=[("screening",{"good_prior":"101/100"}),
           ("screening",{"good_success":"-1/100"}),
           ("screening",{"principal":"0"}),
           ("screening",{"failure_recovery":"120"}),
           ("screening",{"test_cost":"1001"}),
           ("monitoring",{"claimants":True}),("monitoring",{"claimants":"12"}),
           ("monitoring",{"claimants":0}),("monitoring",{"claimants":1001}),
           ("monitoring",{"debt":"140"}),("monitoring",{"prudent_success":"3/5"}),
           ("monitoring",{"prudent_success":"11/10"}),
           ("bank",{"a_deposits":"150"}),("bank",{"b_deposits":"80"}),
           ("bank",{"external_payment":"25"}),("bank",{"new_loan":"23"}),
           ("bank",{"immediate_withdrawal_probe":"145"}),
           ("bank",{"direct_unprovided_loss":"163"}),("bank",{"operating_cash_cost":"20"}),
           ("bank",{"a_reserves":"200","a_loans":"0","new_loan":"0","external_payment":"0","direct_unprovided_loss":"0"}),
           ("liquidity",{"initial_fund":"0"}),("liquidity",{"early_fraction":"0"}),
           ("liquidity",{"early_fraction":"1"}),("liquidity",{"liquidation_return":"1/20"}),
           ("liquidity",{"liquidation_return":"11/10"}),("liquidity",{"maturity_return":"1"}),
           ("liquidity",{"maturity_return":"4"}),("liquidity",{"early_claim":"1"}),
           ("liquidity",{"early_claim":"3/2"}),("liquidity",{"utility_shift":"0"}),
           ("liquidity",{"withdrawal_fractions":[]}),("liquidity",{"withdrawal_fractions":["1"]*17}),
           ("liquidity",{"withdrawal_fractions":["1/4","1/4"]}),
           ("liquidity",{"withdrawal_fractions":["1","1/2"]}),
           ("liquidity",{"withdrawal_fractions":["1/5"]}),
           ("liquidity",{"withdrawal_fractions":["101/100"]}),
           ("liquidity",{"withdrawal_fractions":("1/4","1")})]
    for section,changes in cases:
        bad=copy.deepcopy(base)
        bad[section].update(changes)
        invalid(bad,section+" contract bound")
    for section in ("screening","monitoring","bank","liquidity"):
        bad=copy.deepcopy(base)
        bad[section]["unknown"]="0"
        invalid(bad,section+" extra key")
        bad=copy.deepcopy(base)
        del bad[section][next(iter(bad[section]))]
        invalid(bad,section+" missing key")
    bad=copy.deepcopy(base)
    bad["schema"]="future-schema"
    invalid(bad,"schema version")

    structure=_Structure()
    html=CHAPTER.read_text()
    structure.feed(html)
    truth(structure.worked==4,"four complete worked cases")
    truth(structure.prompts==structure.solutions==8,"eight prompts and complete solutions")
    truth(len(structure.ids)==len(set(structure.ids)),"unique chapter IDs")
    truth({"screening","monitoring","creation","liquidity","lab","exercises","teach-back"}<=set(structure.ids),"required instructional sections")
    truth(structure.sources=={"v06-c06-boe-creation","v11-c01-diamond-monitoring","v11-c01-diamond-dybvig"},"exact scoped primary sources")
    payloads=[INPUT,MODEL,OUTPUT,README]
    for path in payloads+[MANIFEST]:
        truth(path.name in structure.links,"flat reader asset link "+path.name)
    source=json.loads(SOURCES.read_text())
    truth({r["id"] for r in source["proposals"]}=={"v11-c01-diamond-monitoring","v11-c01-diamond-dybvig"},"source proposals match usage")
    truth(source["reused_sources"][0]["id"]=="v06-c06-boe-creation","source reuse scope")
    manifest=json.loads(MANIFEST.read_text())
    truth(manifest["schema"]=="v11-c01-manifest-1","manifest schema")
    truth(len(manifest["files"])==4,"four payload manifest")
    truth({r["file"] for r in manifest["files"]}=={p.name for p in payloads},"manifest exact membership")
    for row in manifest["files"]:
        raw=(PROJECT/row["file"]).read_bytes()
        truth(row["bytes"]==len(raw) and row["sha256"]==hashlib.sha256(raw).hexdigest(),"manifest hash "+row["file"])

    with tempfile.TemporaryDirectory(prefix="v11-c01-check-") as td:
        temp=Path(td)
        isolated=temp/"lab"
        isolated.mkdir()
        for path in payloads+[MANIFEST]:
            (isolated/path.name).write_bytes(path.read_bytes())
        aliases=[]
        for path in (isolated/INPUT.name,isolated/MODEL.name):
            symbolic=temp/(path.name+".symlink")
            symbolic.symlink_to(path)
            hard=temp/(path.name+".hardlink")
            os.link(path,hard)
            aliases.extend([path,symbolic,hard])
        aliases.append(isolated/".."/"lab"/INPUT.name)
        for optimized in (False,True):
            options=[sys.executable]+(["-O"] if optimized else [])
            for default in (False,True):
                target=isolated/OUTPUT.name if default else temp/("explicit-O.json" if optimized else "explicit.json")
                args=[] if default else ["--input",str(isolated/INPUT.name),"--output",str(target)]
                proc=subprocess.run(options+[str(isolated/MODEL.name)]+args,cwd=temp,capture_output=True,timeout=20)
                truth(proc.returncode==0 and not proc.stdout and not proc.stderr,"quiet isolated CLI")
                truth(target.read_bytes()==OUTPUT.read_bytes(),"portable exact output")
                counts["portable_model_runs"]+=1
            invalid_texts=[INPUT.read_text().replace('"schema":','"schema":"duplicate","schema":',1),
                           INPUT.read_text().replace('"good_prior": "3/5"','"good_prior": NaN'),
                           INPUT.read_text().replace('"principal": "100"','"principal": true',1),
                           " "*65537]
            for number,raw in enumerate(invalid_texts):
                badfile=temp/"bad.json"
                badfile.write_text(raw)
                sentinel=temp/"sentinel.json"
                sentinel.write_bytes(b"unchanged\n")
                proc=subprocess.run(options+[str(isolated/MODEL.name),"--input",str(badfile),"--output",str(sentinel)],cwd=temp,capture_output=True,timeout=20)
                truth(proc.returncode==2 and not proc.stdout and bool(proc.stderr),"invalid CLI status "+str(number))
                truth(sentinel.read_bytes()==b"unchanged\n","invalid CLI preserves prior output")
                counts["cli_rejections"]+=1
            for target in aliases:
                protected_before=[(isolated/p.name).read_bytes() for p in (INPUT,MODEL)]
                proc=subprocess.run(options+[str(isolated/MODEL.name),"--input",str(isolated/INPUT.name),"--output",str(target)],cwd=temp,capture_output=True,timeout=20)
                truth(proc.returncode==2 and not proc.stdout and bool(proc.stderr),"protected CLI alias rejected")
                truth([(isolated/p.name).read_bytes() for p in (INPUT,MODEL)]==protected_before,"protected bytes unchanged")
                counts["cli_rejections"]+=1

    if require_bindings:
        record=json.loads(AUTHOR.read_text())
        wanted={str(p.relative_to(ROOT)) for p in [CHAPTER,INPUT,MODEL,OUTPUT,MANIFEST,README,Path(__file__).resolve(),SOURCES]}
        entries=record["reviewed_hashes"]
        truth(len(entries)==8 and {r["path"] for r in entries}==wanted,"eight nonself author bindings")
        for row in entries:
            raw=(ROOT/row["path"]).read_bytes()
            truth(row["bytes"]==len(raw) and row["sha256"]==hashlib.sha256(raw).hexdigest(),"author binding "+row["path"])
            counts["bound_author_payloads"]+=1
        truth(record["status"]=="author-review-complete; separate peer/coordinator acceptance pending","no self acceptance")
    return {"chapter":"v11-c01","status":"passed",**counts}


if __name__=="__main__":
    print(json.dumps(check(),sort_keys=True))
