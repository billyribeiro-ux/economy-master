"""Original finite restructuring lab; exact arithmetic, no network or file writes."""
from fractions import Fraction as F
import json
from pathlib import Path
import sys


def need(condition, message):
    if not condition:
        raise ValueError(message)


def q(value):
    need(type(value) in (int, str), "use integers or exact rational/decimal strings")
    try:
        number = F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("finite rational input required") from exc
    need(number >= 0, "nonnegative input required")
    return number


def encode(x):
    if isinstance(x, F): return str(x)
    if isinstance(x, dict): return {k:encode(v) for k,v in x.items()}
    if isinstance(x, list): return [encode(v) for v in x]
    return x


def faces(b):
    need(set(b["claims"]) == {"secured", "bonds", "trade"}, "three old debt classes")
    result = {k:q(v) for k,v in b["claims"].items()}
    need(all(v > 0 for v in result.values()), "positive old face amounts required")
    return result


def liquidate(b):
    f=faces(b); p=b["liquidation"]; cash=q(b["cash"])
    collateral, c_cost, other, o_cost=[q(p[k]) for k in (
        "collateral_gross", "collateral_sale_cost", "other_gross", "other_sale_cost")]
    need(c_cost <= collateral and o_cost <= other, "sale costs cannot exceed their asset pool")
    net_collateral=collateral-c_cost
    collateral_paid=min(net_collateral, f["secured"])
    deficiency=f["secured"]-collateral_paid
    pool=other-o_cost+cash+net_collateral-collateral_paid
    eligible=deficiency+f["bonds"]+f["trade"]
    fraction=min(F(1),pool/eligible)
    receipts={"secured":collateral_paid+deficiency*fraction,
              "bonds":f["bonds"]*fraction,"trade":f["trade"]*fraction,
              "equity":max(F(0),pool-eligible)}
    total=net_collateral+other-o_cost+cash
    need(sum(receipts.values()) == total, "liquidation cash conservation")
    price=q(b["bond_historical_cost"]); need(price > 0, "positive historical purchase price")
    return {"net_collateral":net_collateral,"collateral_payment":collateral_paid,
            "secured_deficiency":deficiency,"general_pool":pool,"eligible_unsecured_face":eligible,
            "general_recovery_fraction":fraction,"receipts":receipts,"net_total":total,
            "recovery_per_face":{k:receipts[k]/v for k,v in f.items()},
            "bond_realized_holding_return":receipts["bonds"]/price-1}


def price(cash, weights, rate):
    return sum((w*x for w,x in zip(weights,cash)), F(0))/(1+rate)


def fair_senior_face(proceeds, cash, weights, rate):
    """Invert the piecewise price of min(face, state cash), using exact knots."""
    target=proceeds*(1+rate)
    if target > sum((w*x for w,x in zip(weights,cash)), F(0)): return None
    if target == 0: return F(0)
    fixed=F(0); active=F(1)
    for ceiling in sorted(set(cash)):
        candidate=(target-fixed)/active
        if candidate <= ceiling: return candidate
        for x,w in zip(cash,weights):
            if x == ceiling: fixed += w*x; active -= w
    raise ValueError("unreachable senior pricing interval")


def continue_business(b, revision=None):
    p=dict(b["continuation"])
    if revision is not None: p.update(revision)
    cash=[q(x) for x in p["final_cash"]]; weights=[q(x) for x in p["weights"]]
    need(cash and len(cash) == len(weights) and sum(weights) == 1 and all(w > 0 for w in weights), "matching positive probabilities summing to one")
    rate=q(p["rate"]); cost=q(p["restart_cost"])+q(p["workout_cost"]); opening=q(b["cash"])
    need(cost >= opening, "lab uses all opening cash and nonnegative new funding")
    funding=cost-opening; face=fair_senior_face(funding,cash,weights,rate)
    gross_value=price(cash,weights,rate); liq=liquidate(b)
    common={"immediate_uses":cost,"internal_cash_used":opening,"new_money_required":funding,
            "final_cash":cash,"weights":weights,"gross_final_cash_value":gross_value,
            "pricing_assumption":"Certain base; explicit risk-neutral probabilities for risky variants."}
    if face is None:
        return dict(common,status="new-money-unfundable",new_money_shortfall=funding-gross_value,claims=None)
    f=faces(b); outcomes=[]
    for total in cash:
        new=min(face,total); remaining=total-new
        senior=min(f["secured"],remaining); remaining -= senior
        unsecured=min(f["bonds"]+f["trade"],remaining); remaining -= unsecured
        row={"new":new,"secured":senior,"bonds":unsecured*f["bonds"]/(f["bonds"]+f["trade"]),
             "trade":unsecured*f["trade"]/(f["bonds"]+f["trade"]),"equity":remaining}
        need(sum(row.values()) == total, "continuation state cash conservation")
        outcomes.append(row)
    values={key:price([r[key] for r in outcomes],weights,rate) for key in outcomes[0]}
    need(values["new"] == funding, "new finance priced at actual receipts")
    old_value=sum(v for k,v in values.items() if k != "new")
    gains={k:values[k]-liq["receipts"][k] for k in liq["receipts"]}
    shares={k:q(v) for k,v in b["conversion_shares"].items()}
    need(set(shares) == {"secured","bonds","trade"} and sum(shares.values()) > 0, "conversion cap table")
    residual=[total-row["new"] for total,row in zip(cash,outcomes)]
    equity_price=price(residual,weights,rate)/sum(shares.values())
    conversion={k:shares[k]*equity_price for k in shares}; conversion["old_common"]=F(0)
    need(sum(conversion.values()) == old_value, "converted claims exhaust residual value")
    return dict(common,status="priced-proposal",new_face=face,claims=outcomes,claim_values=values,
                old_claim_value=old_value,surplus_over_liquidation=old_value-liq["net_total"],
                old_class_gains=gains,all_old_classes_weakly_participate=all(v >= 0 for v in gains.values()),
                new_promised_yield=(face/funding-1) if funding else None,
                new_expected_return=(sum(w*r["new"] for w,r in zip(weights,outcomes))/funding-1) if funding else None,
                conversion={"shares":shares,"total_shares":sum(shares.values()),"price_per_share":equity_price,
                            "claim_values":conversion},
                consent="Computed participation is not an executed unanimous agreement.")


def refinance(p, consent, premium=0):
    need(type(consent) is bool, "explicit consent state required")
    cash,reserve,old,new,fee,rate,op=[q(p[k]) for k in (
        "cash","required_reserve","old_due_now","new_loan_proceeds","issue_fee","quarter_rate","final_net_operating_cash")]
    bonus=q(premium); need(reserve <= cash and old > 0, "initial cash/note domain")
    available=cash+new-fee-reserve
    need(0 <= available <= old, "quoted financing must leave a nonnegative old-note shortfall")
    deferred=old-available
    common={"quoted_new_proceeds":new,"current_old_payment_if_signed":available,
            "required_extension":deferred,"date_zero_uses_if_signed":available+fee+reserve,
            "date_zero_sources_if_signed":cash+new}
    if not consent:
        return dict(common,status="consent-missing",closing=None,
                    explanation="The conditional new-money commitment and amendment are not executed; no funded close is asserted.")
    first=cash+new-fee-available
    final=first+op; new_face=new*(1+rate); old_face=deferred*(1+rate)+bonus
    if final < new_face+old_face:
        return dict(common,status="maturity-funding-failure",gap=new_face+old_face-final,closing=None,
                    explanation="Quoted full-repayment terms cannot be assumed funded; renegotiation and repricing would be needed.")
    equity=final-new_face-old_face
    return dict(common,status="funded",cash_after_initial_batch=first,final_cash_before_claims=final,
                new_loan_repayment=new_face,extended_old_repayment=old_face,equity_distribution=equity,
                old_creditor_value=available+old_face/(1+rate),equity_value=equity/(1+rate),
                transfer_to_old_creditor=bonus/(1+rate),closing={"cash":F(0),"old_debt":F(0),"new_debt":F(0)})


def run(data):
    need(data["case"] == "Brindle Ceramics and Rillstone Services: original finite restructuring cases", "fixed original cases")
    need(data["units"] == "money kCU; conversion shares thousands; per-share values CU; stated annual or quarterly rates", "unit contract")
    b=data["brindle"]; p=data["rillstone"]
    need(b["dates"] == ["2027-01-01","2028-01-01"] and p["dates"] == ["2027-04-01","2027-07-01"], "annual/quarterly date contracts")
    need(type(p["creditors"]) is int and p["creditors"] == 5, "five identical old creditors")
    liq=liquidate(b); base=continue_business(b); risky=continue_business(b,b["risky_revision"])
    need(len(b["continuation"]["final_cash"]) == 1, "base continuation is certain")
    required=q(b["continuation"]["restart_cost"])+q(b["continuation"]["workout_cost"])-q(b["cash"])
    threshold=(liq["net_total"]+required)*(1+q(b["continuation"]["rate"]))
    return encode({"liquidation":liq,"continuation":base,"risky_revision":risky,
                   "certain_final_cash_for_total_break_even":threshold,
                   "refinancing":{"signed":refinance(p,True),"unsigned":refinance(p,False),
                                  "extra_consent_payment":refinance(p,True,p["holdout_premium_at_one"])},
                   "limitation":"Finite fictional cash/claim contracts. No legal insolvency decision, universal priority, estimated market value or assumed consent."})


if __name__ == "__main__":
    try:
        need(len(sys.argv) <= 2, "usage: python3 v08-c11-analysis.py [inputs.json]")
        path=Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("v08-c11-inputs.json")
        print(json.dumps(run(json.loads(path.read_text(encoding="utf-8"))),indent=2,allow_nan=False))
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print("Invalid restructuring contract: "+str(exc),file=sys.stderr)
        sys.exit(2)
