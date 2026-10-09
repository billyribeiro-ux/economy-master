"""Alder Bank: an exact, bounded, synthetic ledger and liquidity feasibility lab.

All accounting conventions and capital thresholds are instructional. No current
GAAP, regulatory-capital, central-bank eligibility or insolvency-law decision is
implemented. run(data) is quiet, nonmutating and strict-JSON-safe. Monetary
arithmetic uses Fraction; JSON output is rounded to twelve decimal places.
"""
import argparse
from fractions import Fraction as F
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ACCOUNTS = {"cash", "free_securities", "pledged_securities", "gross_loans",
            "allowance", "property", "goodwill", "deposits", "wholesale",
            "other_liabilities", "equity"}
KINDS = {"originate_deposit", "external_payment", "principal_collection",
         "cash_interest", "deposit_interest", "cash_expense", "provision",
         "chargeoff", "recovery", "dividend", "allowance_release"}


def require(condition, label):
    if not condition:
        raise ValueError(label)


def fields(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), label+": exact fields required")


def number(value, label, low=0, high=1000000):
    require(type(value) in (int, float), label+": finite JSON number required")
    require(type(value) is int or math.isfinite(value), label+": finite JSON number required")
    require(low <= value <= high, label+": outside bounded domain")
    return F(str(value))


def integer(value, label, low, high):
    require(type(value) is int and low <= value <= high, label+": bounded integer required")
    return value


def text(value, label):
    require(type(value) is str and 0 < len(value) <= 1000, label+": bounded nonempty text required")
    return value


def measure(s):
    net = s["gross_loans"]-s["allowance"]
    assets = s["cash"]+s["free_securities"]+s["pledged_securities"]+net+s["property"]+s["goodwill"]
    liabilities = s["deposits"]+s["wholesale"]+s["other_liabilities"]
    return {"net_loans": net, "assets": assets, "liabilities": liabilities,
            "equity": s["equity"], "identity_residual": assets-liabilities-s["equity"]}


def valid_state(s, label):
    # Negative equity is meaningful; the accounting identity is still required.
    for key, value in s.items():
        require(key == "equity" or value >= 0, label+": negative "+key)
    require(s["allowance"] <= s["gross_loans"], label+": allowance exceeds loans in this simplified positive-net-loan class")
    require(measure(s)["identity_residual"] == 0, label+": ledger is not balanced")


def journal_step(s, kind, amount):
    if kind == "originate_deposit":
        s["gross_loans"] += amount; s["deposits"] += amount
    elif kind == "external_payment":
        s["cash"] -= amount; s["deposits"] -= amount
    elif kind == "principal_collection":
        s["cash"] += amount; s["gross_loans"] -= amount
    elif kind == "cash_interest":
        s["cash"] += amount; s["equity"] += amount
    elif kind == "deposit_interest":
        s["deposits"] += amount; s["equity"] -= amount
    elif kind == "cash_expense":
        s["cash"] -= amount; s["equity"] -= amount
    elif kind == "provision":
        s["allowance"] += amount; s["equity"] -= amount
    elif kind == "chargeoff":
        require(amount <= s["allowance"], "chargeoff: pre-existing allowance insufficient; recognize the additional loss first")
        s["gross_loans"] -= amount; s["allowance"] -= amount
    elif kind == "recovery":
        s["cash"] += amount; s["allowance"] += amount
    elif kind == "dividend":
        s["cash"] -= amount; s["equity"] -= amount
    elif kind == "allowance_release":
        s["allowance"] -= amount; s["equity"] += amount


def capital(s, rules):
    m = measure(s)
    k = s["equity"]-s["goodwill"]
    exposure = m["assets"]-s["goodwill"]
    rwa = (rules["loan_weight"]*m["net_loans"]
           + rules["security_weight"]*(s["free_securities"]+s["pledged_securities"])
           + rules["property_weight"]*s["property"])
    require(exposure > 0 and rwa > 0 and m["assets"] > 0, "capital: positive denominators required")
    risk_need = max(F(0), rules["risk_ratio_floor"]*rwa-k)
    ell = rules["leverage_floor"]
    # Cash proceeds enter the exposure denominator, but have zero toy risk weight.
    cash_leverage_need = max(F(0), (ell*exposure-k)/(1-ell))
    conversion_leverage_need = max(F(0), ell*exposure-k)
    return {"adjusted_capital": k, "adjusted_exposure": exposure, "toy_rwa": rwa,
            "book_equity_to_assets": s["equity"]/m["assets"],
            "toy_risk_ratio": k/rwa, "toy_leverage_ratio": k/exposure,
            "risk_gate": k >= rules["risk_ratio_floor"]*rwa,
            "leverage_gate": k >= ell*exposure,
            "minimum_cash_equity_for_ratios": max(risk_need,cash_leverage_need),
            "minimum_deposit_conversion_for_ratios": max(risk_need,conversion_leverage_need)}


def serial(value):
    if isinstance(value,F):
        try:
            approximate=float(value)
        except OverflowError as exc:
            raise ValueError("result exceeds the finite JSON-number representation") from exc
        require(math.isfinite(approximate),"result exceeds the finite JSON-number representation")
        return round(approximate,12)
    if isinstance(value,dict):
        return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):
        return [serial(v) for v in value]
    return value


def run(data):
    fields(data,{"schema_version","provenance","opening","journal","valuation",
                 "instructional_capital","liquidity","repair"},"input")
    require(type(data["schema_version"]) is int and data["schema_version"]==1,"schema_version must be1")
    text(data["provenance"],"provenance")
    fields(data["opening"],ACCOUNTS,"opening")
    opening={k:number(v,"opening."+k, -1000000 if k=="equity" else 0) for k,v in data["opening"].items()}
    valid_state(opening,"opening")
    entries=data["journal"]
    require(type(entries) is list and 1 <= len(entries) <= 40,"journal:1–40 entries required")
    s=opening.copy();states=[];ids=set();income=F(0);dividends=F(0)
    for item in entries:
        fields(item,{"id","kind","amount"},"journal entry")
        label=text(item["id"],"journal id")
        require(label not in ids,"journal ids must be unique");ids.add(label)
        kind=text(item["kind"],"journal kind");require(kind in KINDS,"unknown journal kind")
        amount=number(item["amount"],label+" amount")
        journal_step(s,kind,amount);valid_state(s,label)
        if kind in ("cash_interest","allowance_release"):income+=amount
        if kind in ("deposit_interest","cash_expense","provision"):income-=amount
        if kind=="dividend":dividends+=amount
        states.append({"id":label,"kind":kind,"accounts":s.copy(),"totals":measure(s)})
    closing=s.copy()
    require(closing["equity"]==opening["equity"]+income-dividends,"income-to-equity reconciliation failed")
    fields(data["valuation"],{"free_security_value","pledged_security_value","loan_value",
                             "severe_loan_value","property_value","goodwill_value"},"valuation")
    v={k:number(x,"valuation."+k) for k,x in data["valuation"].items()}
    require((closing["free_securities"]>0 or v["free_security_value"]==0)
            and (closing["pledged_securities"]>0 or v["pledged_security_value"]==0),"cannot value an absent securities pool")
    require(closing["gross_loans"]>0 or (v["loan_value"]==0 and v["severe_loan_value"]==0),
            "cannot value absent gross loan claims")
    require(closing["property"]>0 or v["property_value"]==0,"cannot value absent property in this lab")
    require(closing["goodwill"]>0 or v["goodwill_value"]==0,"cannot value absent goodwill in this lab")
    fields(data["instructional_capital"],{"loan_weight","security_weight","property_weight",
                                          "risk_ratio_floor","leverage_floor"},"instructional_capital")
    rules={k:number(x,"instructional_capital."+k,high=3 if k.endswith("weight") else 1)
           for k,x in data["instructional_capital"].items()}
    require(rules["leverage_floor"]<1,"toy leverage floor must be below1")
    base_capital=capital(closing,rules)
    fields(data["liquidity"],{"restricted_cash","haircut","draw_cutoff","repay_cutoff","secured_gross","events"},"liquidity")
    liquidity=data["liquidity"]
    restricted=number(liquidity["restricted_cash"],"restricted_cash")
    require(restricted<=closing["cash"],"restricted_cash exceeds closing cash")
    haircut=number(liquidity["haircut"],"haircut",high=1)
    gross=number(liquidity["secured_gross"],"secured_gross",low=.5,high=2)
    draw=integer(liquidity["draw_cutoff"],"draw_cutoff",1,12)
    repay=integer(liquidity["repay_cutoff"],"repay_cutoff",1,12)
    require(draw<repay,"secured cash must arrive before repayment")
    events=liquidity["events"]
    require(type(events) is list and 1 <= len(events) <= 12,"liquidity:1–12 dated events required")
    normalized=[];previous=0
    for event in events:
        fields(event,{"cutoff","loan_principal_in","deposits_out","wholesale_out","other_out"},"liquidity event")
        cutoff=integer(event["cutoff"],"cutoff",1,12)
        require(cutoff>previous,"liquidity cutoffs must be strictly increasing");previous=cutoff
        normalized.append({"cutoff":cutoff,**{k:number(event[k],k) for k in event if k!="cutoff"}})
    require(draw in [e["cutoff"] for e in normalized] and repay in [e["cutoff"] for e in normalized],
            "draw and repayment cutoffs must be in the forecast")
    require(sum(e["loan_principal_in"] for e in normalized)<=closing["gross_loans"]-closing["allowance"],
            "principal receipts exceed performing net loan stock in this lab")
    for flow,account in (("deposits_out","deposits"),("wholesale_out","wholesale"),("other_out","other_liabilities")):
        require(sum(e[flow] for e in normalized)<=closing[account],"scheduled repayment exceeds existing "+account)
    fields(data["repair"],{"kind","amount"},"repair")
    repair_kind=text(data["repair"]["kind"],"repair kind")
    require(repair_kind in ("none","cash_equity","deposit_conversion","unsecured_borrow"),"unknown repair")
    repair_amount=number(data["repair"]["amount"],"repair amount")
    require(repair_kind!="none" or repair_amount==0,"none repair must have zero amount")
    if repair_kind=="cash_equity":s["cash"]+=repair_amount;s["equity"]+=repair_amount
    if repair_kind=="deposit_conversion":
        stable=closing["deposits"]-sum(e["deposits_out"] for e in normalized)
        require(repair_amount<=stable,"conversion may use only deposits excluded from scheduled outflows")
        s["deposits"]-=repair_amount;s["equity"]+=repair_amount
    if repair_kind=="unsecured_borrow":s["cash"]+=repair_amount;s["wholesale"]+=repair_amount
    valid_state(s,"repair")
    post_repair=s.copy();post_capital=capital(s,rules)
    book=measure(s)
    economic_assets=s["cash"]+v["free_security_value"]+v["pledged_security_value"]+v["loan_value"]+v["property_value"]+v["goodwill_value"]
    economic_equity=economic_assets-book["liabilities"]
    severe_equity=economic_equity-v["loan_value"]+v["severe_loan_value"]
    # The new lender advances the stipulated capacity once; the existing pledged
    # pool is neither released nor reused, and a sale is not an additional source.
    capacity=(1-haircut)*v["free_security_value"]
    free_book=s["free_securities"]
    forecast=[];first_failure=None;prefix=0;peak_gap=F(0)
    for event in normalized:
        cutoff=event["cutoff"]
        draw_cash=capacity if cutoff==draw else F(0)
        repayment=capacity*gross if cutoff==repay else F(0)
        if cutoff==draw:
            s["cash"]+=capacity;s["wholesale"]+=capacity
            s["free_securities"]-=free_book;s["pledged_securities"]+=free_book
        s["cash"]+=event["loan_principal_in"];s["gross_loans"]-=event["loan_principal_in"]
        for flow,account in (("deposits_out","deposits"),("wholesale_out","wholesale"),("other_out","other_liabilities")):
            s["cash"]-=event[flow];s[account]-=event[flow]
        if cutoff==repay:
            s["cash"]-=repayment;s["wholesale"]-=capacity
            s["equity"]-=capacity*(gross-1)
            s["free_securities"]+=free_book;s["pledged_securities"]-=free_book
        # These are hypothetical full-payment accounts, not asserted executions.
        require(measure(s)["identity_residual"]==0,"projected stress ledger not balanced")
        headroom=s["cash"]-restricted
        peak_gap=max(peak_gap,-headroom)
        if headroom<0 and first_failure is None:first_failure=cutoff
        if first_failure is None:prefix+=1
        forecast.append({"cutoff":cutoff,"secured_draw":draw_cash,"secured_repayment":repayment,
                         "cash_after_assumed_payments":s["cash"],"unrestricted_headroom":headroom,
                         "payment_shortfall":max(F(0),-headroom),
                         "executable_without_added_funding_through_here":first_failure is None,
                         "projected_accounts_if_all_payments_made":s.copy(),"totals":measure(s)})
    result={"schema_version":1,"case":"Alder Bank, synthetic CU",
            "opening":measure(opening),"journal_states":states,"closing_accounts":closing,
            "closing":measure(closing),"net_income":income,"dividends":dividends,
            "income_equity_residual":closing["equity"]-opening["equity"]-income+dividends,
            "base_capital":base_capital,"repair":data["repair"].copy(),
            "post_repair_accounts":post_repair,"post_repair_capital":post_capital,
            "valuation":{"book_equity":book["equity"],"economic_assets":economic_assets,
                         "economic_equity":economic_equity,"severe_economic_equity":severe_equity,
                         "book_to_economic_equity_change":economic_equity-book["equity"]},
            "liquidity":{"restricted_cash":restricted,"secured_capacity":capacity,
                         "secured_interest":capacity*(gross-1),"forecast":forecast,
                         "first_failure_cutoff":first_failure,"executable_prefix_cutoffs":prefix,
                         "feasible_through_horizon":first_failure is None,
                         "minimum_upfront_external_cash_for_this_fixed_plan":peak_gap},
            "limits":"Forecast rows assume every scheduled payment for diagnosis. After the first negative unrestricted headroom they are not executable without extra funding. The new secured debt is repaid in-horizon; any optional unsecured repair matures after the displayed horizon. Capital ratios and thresholds are instructional, not regulatory compliance."}
    answer=serial(result);json.dumps(answer,allow_nan=False);return answer


def load(path):
    require(path.stat().st_size<=200000,"input file exceeds200000 bytes")
    def unique(pairs):
        out={}
        for key,value in pairs:
            require(key not in out,"duplicate JSON key: "+key);out[key]=value
        return out
    def invalid(token):
        raise ValueError("nonfinite JSON constant: "+token)
    return json.loads(path.read_text(),object_pairs_hook=unique,parse_constant=invalid)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",nargs="?",type=Path,default=HERE/"v11-c02-inputs.json")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    try:
        if args.output:
            for protected in (args.input,Path(__file__)):
                require(args.output.resolve()!=protected.resolve(),"output may not overwrite the input or implementation")
                require(not (args.output.exists() and protected.exists() and args.output.samefile(protected)),
                        "output may not overwrite an alias of the input or implementation")
        output=json.dumps(run(load(args.input)),indent=2,allow_nan=False)+"\n"
        if args.output:args.output.write_text(output)
        else:print(output,end="")
    except (ValueError,TypeError,KeyError,OSError,OverflowError,RecursionError) as exc:
        print("error: "+str(exc),file=sys.stderr);return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
