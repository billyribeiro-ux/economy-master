"""Independent exact cash, priority, participation and pricing audit for v08-c11."""
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

BOOK=Path(__file__).resolve().parents[1]
PROJECT=BOOK/"content/projects"


def need(ok, message):
    if not ok: raise AssertionError(message)


def check_liquidation(b, r):
    p=b["liquidation"]; faces={k:F(v) for k,v in b["claims"].items()}
    assets=[F(p["collateral_gross"]),F(p["other_gross"]),F(b["cash"])]
    costs=[F(p["collateral_sale_cost"]),F(p["other_sale_cost"])]
    collateral=assets[0]-costs[0]; first=min(collateral,faces["secured"])
    unpaid=faces["secured"]-first
    general=assets[1]+assets[2]-costs[1]+collateral-first
    eligible={"secured":unpaid,"bonds":faces["bonds"],"trade":faces["trade"]}
    available=min(general,sum(eligible.values()))
    payouts={k:available*v/sum(eligible.values()) for k,v in eligible.items()}
    payouts["secured"] += first; payouts["equity"]=general-available
    need({k:F(v) for k,v in r["receipts"].items()} == payouts, "separate collateral/general allocations")
    need(F(r["net_total"]) == sum(assets)-sum(costs) == sum(payouts.values()), "net liquidation resources counted once")
    need(F(r["secured_deficiency"]) == unpaid and F(r["general_pool"]) == general, "deficiency and excess-collateral route")
    for k,face in faces.items():
        need(0 <= payouts[k] <= face and F(r["recovery_per_face"][k]) == payouts[k]/face, "face recovery " + k)
    need(F(r["bond_realized_holding_return"]) == payouts["bonds"]/F(b["bond_historical_cost"])-1, "return uses historical price")


def check_continuation(b, proposal, liquidation):
    need(proposal["status"] == "priced-proposal", "expected a priced finite proposal")
    cash=[F(x) for x in proposal["final_cash"]]; weights=[F(w) for w in proposal["weights"]]
    rate=F(b["continuation"]["rate"]); issue=F(proposal["new_money_required"])
    face=F(proposal["new_face"]); old={k:F(v) for k,v in b["claims"].items()}
    need(F(proposal["internal_cash_used"])+issue == F(proposal["immediate_uses"]), "fund all immediate uses")
    values={k:F(0) for k in ("new","secured","bonds","trade","equity")}
    for total,weight,row in zip(cash,weights,proposal["claims"]):
        # Claim intervals partition final cash; the unsecured interval is split pro rata.
        new=min(total,face)
        secured=max(F(0),min(total,face+old["secured"])-face)
        unsecured=max(F(0),min(total,face+sum(old.values()))-face-old["secured"])
        residual=max(F(0),total-face-sum(old.values()))
        expected={"new":new,"secured":secured,"bonds":unsecured*old["bonds"]/(old["bonds"]+old["trade"]),
                  "trade":unsecured*old["trade"]/(old["bonds"]+old["trade"]),"equity":residual}
        need({k:F(v) for k,v in row.items()} == expected, "independent state claim intervals")
        need(sum(expected.values()) == total, "no omitted old/new claim or double repayment")
        for k,v in expected.items(): values[k] += weight*v/(1+rate)
    need({k:F(v) for k,v in proposal["claim_values"].items()} == values, "dated value of every state claim")
    need(values["new"] == issue, "new-money actual-receipt price")
    total=sum(w*x for w,x in zip(weights,cash))/(1+rate)
    need(F(proposal["gross_final_cash_value"]) == total == sum(values.values()), "complete claim portfolio value")
    old_value=total-issue
    need(F(proposal["old_claim_value"]) == old_value and F(proposal["surplus_over_liquidation"]) == old_value-F(liquidation["net_total"]), "one external funding deduction")
    gains={k:values[k]-F(v) for k,v in liquidation["receipts"].items()}
    need({k:F(v) for k,v in proposal["old_class_gains"].items()} == gains, "old claimant outside options")
    need(proposal["all_old_classes_weakly_participate"] == all(v >= 0 for v in gains.values()), "class participation distinct from total surplus")
    conversion=proposal["conversion"]; shares={k:F(v) for k,v in conversion["shares"].items()}
    need(F(conversion["price_per_share"])*sum(shares.values()) == old_value, "share price and complete cap table")
    need(sum(F(v) for v in conversion["claim_values"].values()) == old_value and conversion["claim_values"]["old_common"] == "0", "no retained unlisted common claim")


def check_refinancing(p, r, premium=0):
    cash,new,fee,reserve,old,rate,operating=[F(p[k]) for k in (
        "cash","new_loan_proceeds","issue_fee","required_reserve","old_due_now","quarter_rate","final_net_operating_cash")]
    paid=cash+new-fee-reserve; extended=old-paid
    # Independently signed cash entries; no loan receipt appears without consent.
    date0=[cash,new,-fee,-paid]
    date1=[sum(date0),operating,-new*(1+rate),-extended*(1+rate),-F(premium)]
    equity=sum(date1)
    need(r["status"] == "funded", "signed maturity funding")
    need(F(r["date_zero_sources_if_signed"]) == cash+new == F(r["date_zero_uses_if_signed"]), "refinancing source/use equality")
    need(F(r["cash_after_initial_batch"]) == sum(date0) == reserve, "actual retained cash")
    need(F(r["new_loan_repayment"]) == new*(1+rate), "lender price excludes independent arranger fee")
    need(F(r["extended_old_repayment"]) == extended*(1+rate)+premium, "extension time compensation and separate transfer")
    need(F(r["equity_distribution"]) == equity and sum(date1+[-equity]) == 0, "complete maturity cash settlement")
    need(F(r["old_creditor_value"]) == paid+(extended*(1+rate)+premium)/(1+rate), "old debt value includes current payment")
    need(F(r["equity_value"]) == equity/(1+rate), "equity dated value")
    need(r["closing"] == {"cash":"0","old_debt":"0","new_debt":"0"}, "no hidden rollover or residual cash")


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ids=[]; self.links=[]; self.sources=[]; self.examples=0
        self.exercises=0; self.answers=0; self.ol_depth=0; self.exercise_depth=0; self.in_answers=False; self.h1=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if "id" in a: self.ids.append(a["id"])
        if tag == "h1": self.h1 += 1
        if tag == "a": self.links.append(a.get("href", ""))
        if "data-source" in a: self.sources.append(a["data-source"])
        if "worked" in a.get("class", "").split(): self.examples += 1
        if tag == "ol":
            self.ol_depth += 1
            if "exercises" in a.get("class", "").split(): self.exercise_depth=self.ol_depth
        if tag == "details" and "solutions" in a.get("class", "").split(): self.in_answers=True
        if tag == "li" and self.exercise_depth == self.ol_depth and self.exercise_depth: self.exercises += 1
        if tag == "li" and self.in_answers: self.answers += 1
        if tag not in {"br","hr","img","input","meta","link"}: self.stack.append(tag)
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1] == tag, "HTML nesting " + tag); self.stack.pop()
        if tag == "ol":
            if self.exercise_depth == self.ol_depth: self.exercise_depth=0
            self.ol_depth -= 1
        if tag == "details": self.in_answers=False


def check():
    spec=importlib.util.spec_from_file_location("finite_restructuring",PROJECT/"v08-c11-analysis.py")
    lab=importlib.util.module_from_spec(spec); capture=io.StringIO()
    data=json.loads((PROJECT/"v08-c11-inputs.json").read_text())
    with redirect_stdout(capture),redirect_stderr(capture):
        spec.loader.exec_module(lab); result=lab.run(data)
    need(not capture.getvalue(), "quiet lab import/calculation"); json.dumps(result,allow_nan=False)
    groups=[]; b=data["brindle"]; p=data["rillstone"]; liq=result["liquidation"]
    check_liquidation(b,liq)
    need(liq["receipts"] == {"secured":"520/7","bonds":"150/7","trade":"100/7","equity":"0"}, "Brindle liquidation anchors")
    need(liq["general_recovery_fraction"] == "10/21" and liq["bond_realized_holding_return"] == "4/21", "recovery versus historical return")
    excess=deepcopy(b); excess["liquidation"]["collateral_gross"]=130
    er=lab.encode(lab.liquidate(excess)); check_liquidation(excess,er)
    need(er["receipts"] == {"secured":"90","bonds":"45","trade":"30","equity":"5"}, "excess collateral and equity residual")
    empty=deepcopy(b); empty["cash"]=0; empty["liquidation"].update(collateral_gross=10,other_gross=5)
    zr=lab.encode(lab.liquidate(empty)); check_liquidation(empty,zr)
    need(zr["net_total"] == "0" and all(x == "0" for x in zr["receipts"].values()), "empty estate cannot pay a claim")
    groups.append({"name":"Independent collateral/deficiency/general-pool recoveries, investor returns, excess collateral and empty estate", "status":"pass"})

    base=result["continuation"]; risky=result["risky_revision"]
    check_continuation(b,base,liq); check_continuation(b,risky,liq)
    need(base["old_claim_value"] == "380/3" and base["surplus_over_liquidation"] == "50/3", "net continuation value")
    need(base["new_face"] == "21" and risky["new_face"] == "22", "new money reprices after default risk changes")
    need(risky["claim_values"] == {"new":"20","secured":"450/7","bonds":"186/7","trade":"124/7","equity":"0"}, "risky claim value anchors")
    need(risky["new_promised_yield"] == "1/10" and risky["new_expected_return"] == "1/20", "promise versus actual expected return")
    wrong_face_value=(F(18,4)+F(63,4))/F(21,20)
    need(wrong_face_value == F(135,7) and 20-wrong_face_value == F(5,7), "certainty-priced face fails to raise required cash")
    need(risky["old_class_gains"] == {"secured":"-10","bonds":"36/7","trade":"24/7","equity":"0"}, "negative total surplus cannot be cured solely by transfers")
    costly=deepcopy(b); costly["continuation"]["workout_cost"]=10
    cr=lab.encode(lab.continue_business(costly)); check_continuation(costly,cr,liq)
    need(cr["new_money_required"] == "24" and cr["new_face"] == "126/5" and cr["old_claim_value"] == "368/3", "higher immediate workout cost")
    need(cr["claims"][0] == {"new":"126/5","secured":"90","bonds":"582/25","trade":"388/25","equity":"0"}, "higher-cost final receipts")
    impossible=lab.encode(lab.continue_business(b,{"final_cash":[10],"weights":[1]}))
    need(impossible["status"] == "new-money-unfundable" and impossible["claims"] is None and impossible["new_money_shortfall"] == "220/21", "no face can raise more than total final value")
    groups.append({"name":"Complete finite claims, risk-priced new finance, changed costs and an unfundable new-money boundary", "status":"pass"})

    # Exercise 4 uses claimant-specific dated outside options, not just a total.
    threshold=(F(liq["net_total"])+20)*F(21,20)
    need(str(threshold) == result["certain_final_cash_for_total_break_even"] == "273/2", "same-date total break-even")
    boundary=lab.encode(lab.continue_business(b,{"final_cash":["273/2"],"weights":[1]}))
    check_continuation(b,boundary,liq)
    need(boundary["surplus_over_liquidation"] == "0" and not boundary["all_old_classes_weakly_participate"], "aggregate break-even is not class participation")
    repaired={k:F(v)*F(21,20) for k,v in liq["receipts"].items()}
    need(repaired == {"secured":F(78),"bonds":F(45,2),"trade":F(15),"equity":F(0)}, "consenting priority repair")
    need(sum(repaired.values())+21 == threshold and F(45,2)/15 == F(45,30), "repair closes cash and unsecured proportions")
    conv=base["conversion"]
    need(conv["price_per_share"] == "19/15" and conv["claim_values"] == {"secured":"247/3","bonds":"133/5","trade":"266/15","old_common":"0"}, "equal-rights equity conversion")
    differences=[F(conv["claim_values"][k])-F(base["claim_values"][k]) for k in ("secured","bonds","trade")]
    need(differences == [F(-71,21),F(71,35),F(142,105)] and sum(differences) == 0, "conversion is an old-owner redistribution")
    higher_sale=deepcopy(b); higher_sale["liquidation"]["other_gross"]=66
    hs=lab.encode(lab.liquidate(higher_sale)); check_liquidation(higher_sale,hs)
    need(hs["receipts"] == {"secured":"562/7","bonds":"213/7","trade":"142/7","equity":"0"}, "answered delayed liquidation check")
    need(F(base["old_claim_value"])-F(hs["net_total"]) == F(-13,3) and (F(hs["net_total"])+20)*F(21,20) == F(3171,20), "improved sale alternative reverses recommendation")
    groups.append({"name":"Class participation at aggregate break-even, consenting allocation repair, equity conversion and changed outside option", "status":"pass"})

    refinancing=result["refinancing"]; signed=refinancing["signed"]; premium=refinancing["extra_consent_payment"]
    check_refinancing(p,signed); check_refinancing(p,premium,F(1))
    need(signed["required_extension"] == "10" and signed["equity_distribution"] == "529/25", "complete original maturity gap")
    need(refinancing["unsigned"]["status"] == "consent-missing" and refinancing["unsigned"]["closing"] is None, "unsigned conditional loan is not funded")
    need(F(premium["old_creditor_value"])-F(signed["old_creditor_value"]) == F(signed["equity_value"])-F(premium["equity_value"]) == F(50,51), "holdout payment is a zero-sum old-claim transfer")
    lower=deepcopy(p); lower["new_loan_proceeds"]=28
    lr=lab.encode(lab.refinance(lower,True)); check_refinancing(lower,lr)
    need(lr["required_extension"] == "14" and lr["new_loan_repayment"] == "714/25" and lr["extended_old_repayment"] == "357/25" and lr["equity_distribution"] == "529/25", "lower commitment, fully compensated extension")
    # Independently close the capped-extension and fairly priced new-common repair.
    immediate_old=F(50-12); equity_in=immediate_old+2+8-18-28
    new_debt=28*F(51,50); old_debt=12*F(51,50); common=8+56-new_debt-old_debt
    new_common=equity_in*F(51,50); fraction=new_common/common
    need(equity_in == 2 and common == F(116,5) and fraction == F(51,580), "exercise six fair new common fraction")
    need(new_common == F(51,25) and common-new_common == F(529,25), "new/old common receipts")
    need(18+28+equity_in == immediate_old+2+8 and new_debt+old_debt+new_common+(common-new_common) == 64, "both repair dates close")
    failed=deepcopy(p); failed["final_net_operating_cash"]=20
    fr=lab.encode(lab.refinance(failed,True))
    need(fr["status"] == "maturity-funding-failure" and fr["gap"] == "371/25" and fr["closing"] is None, "failed future repayment is not a fair funded quote")
    groups.append({"name":"Independent refinancing cash entries, consent failure, holdout transfer, lower commitment and fair new-equity repair", "status":"pass"})

    # Exercise 1 diagnostic arithmetic and exercise 2 a new liquidation contract.
    need(140-165 == -25 and 30-10 == 20, "book and liquidity diagnoses")
    net_c=F(88-8); pool=F(44-4+10); rho=pool/(100-net_c+60+20)
    recourse=[net_c+(100-net_c)*rho,60*rho,20*rho]
    nonrecourse=[net_c,F(60,80)*pool,F(20,80)*pool]
    need(recourse == [90,30,10] and nonrecourse == [80,F(75,2),F(25,2)], "new recourse/nonrecourse example")
    need(sum(recourse) == sum(nonrecourse) == 130 and F(30,24)-1 == F(1,4), "new resources and historical-price return")
    failures=[("units",lambda x:x.update(units="USD")),
              ("float",lambda x:x["brindle"].update(cash=10.0)),
              ("negative sale",lambda x:x["brindle"]["liquidation"].update(other_gross=-1)),
              ("excess sale costs",lambda x:x["brindle"]["liquidation"].update(collateral_sale_cost=71)),
              ("weights",lambda x:x["brindle"]["risky_revision"].update(weights=[1,1])),
              ("zero probability",lambda x:x["brindle"]["risky_revision"].update(weights=[0,1])),
              ("hidden claim",lambda x:x["brindle"]["claims"].update(other=1)),
              ("date convention",lambda x:x["rillstone"]["dates"].__setitem__(1,"2028-07-01"))]
    for name,change in failures:
        bad=deepcopy(data); change(bad)
        try: lab.run(bad)
        except ValueError: pass
        else: raise AssertionError("unsupported contract accepted: " + name)
    bad=deepcopy(liq); bad["receipts"]["secured"]="100"
    try: check_liquidation(b,bad)
    except AssertionError: pass
    else: raise AssertionError("secured full-face double recovery not detected")
    bad=deepcopy(risky); bad["claim_values"]["new"]="21"
    try: check_continuation(b,bad,liq)
    except AssertionError: pass
    else: raise AssertionError("promised cash treated as new-money price not detected")
    bad=deepcopy(signed); bad["equity_distribution"]="1329/25"
    try: check_refinancing(p,bad)
    except AssertionError: pass
    else: raise AssertionError("uncancelled new principal not detected")
    groups.append({"name":"All numerical exercise anchors, eight domain failures and three consequential double-counting/pricing error detections", "status":"pass"})

    html=(BOOK/"content/chapters/v08-c11.html").read_text(); doc=Fragment(); doc.feed(html); doc.close()
    need(not doc.stack and doc.h1 == 0 and len(doc.ids) == len(set(doc.ids)), "balanced unique fragment")
    need(doc.examples == 3 and doc.exercises == doc.answers == 8, "complete worked/problem/answer counts")
    need("Teach-back" in html and "Delayed check" in html and html.count("<strong>Answer:</strong>") == 2, "answered teaching checks")
    sources=json.loads((BOOK/"content/reviews/v08-c11-sources.json").read_text())
    need({s["id"] for s in sources} == set(doc.sources) == {h.split("#")[1] for h in doc.links if h.startswith("sources.html#")}, "matching scoped source records")
    need(len(sources) == 3 and all(s["checked"] == "2026-10-08" and s["verification"] for s in sources), "dated source inspection")
    ids={c["id"] for v in json.loads((BOOK/"content/curriculum.json").read_text())["volumes"] for c in v["chapters"]}
    for suffix in ("inputs.json","analysis.py","README.txt"):
        name="v08-c11-"+suffix
        need(name in doc.links and (PROJECT/name).is_file(), "flat offline asset " + name)
    for link in doc.links:
        if link.startswith("v") and link.endswith(".html"):
            need(link[:-5] in ids and (BOOK/"content/chapters"/link).is_file(), "existing manuscript link " + link)
        if link.startswith("curriculum.html#"): need(link.split("#")[1] in ids, "canonical planned link")
    with tempfile.TemporaryDirectory(prefix="v08-c11-check-") as name:
        tmp=Path(name)
        for filename in ("v08-c11-inputs.json","v08-c11-analysis.py"): shutil.copy2(PROJECT/filename,tmp/filename)
        for flags in ([],["-O"]):
            cli=subprocess.run([sys.executable,*flags,str(tmp/"v08-c11-analysis.py")],cwd=tmp.parent,text=True,capture_output=True,check=False)
            need(cli.returncode == 0 and not cli.stderr and json.loads(cli.stdout) == result, "portable normal/optimized lab")
        bad=deepcopy(data); bad["units"]="wrong"; bad_path=tmp/"bad.json"; bad_path.write_text(json.dumps(bad))
        cli=subprocess.run([sys.executable,str(tmp/"v08-c11-analysis.py"),str(bad_path)],text=True,capture_output=True,check=False)
        need(cli.returncode == 2 and not cli.stdout and "Invalid restructuring contract" in cli.stderr, "invalid CLI has no result JSON")
    groups.append({"name":"Three worked cases/eight full solutions, answered checks, scoped sources/assets and portable quiet strict JSON", "status":"pass"})
    report={"chapter":"v08-c11","status":"passed","checks":groups,
            "limitations":["Finite fictional rights, probabilities and cash; no current legal insolvency or real-market valuation determination.",
                           "Class-value participation does not obtain signatures or unconditional financing.",
                           "Manual instructional/source audit, coordinator acceptance and visual QA remain separate."]}
    json.dumps(report,allow_nan=False)
    return report


if __name__ == "__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
