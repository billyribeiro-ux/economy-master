"""Original synthetic foundation practical; offline standard-library benchmark."""

from datetime import date, datetime, timezone
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import re
import sys

DATA = "foundation-practical-data.json"
SOURCE = "foundation-practical-source.txt"
MANIFEST = "foundation-practical-manifest.json"
BALANCES = ("cash", "receivables", "equipment", "payables", "loan", "equity")
KINDS = ("collect_opening_receivable", "invoice_current_services", "collect_current_receivable",
         "pay_current_operating", "expense_on_credit", "pay_opening_supplier", "borrow",
         "repay_principal", "owner_withdrawal")
PROTOCOL = {"training_ids": ["D1", "D2", "D3", "D4"], "target_ids": ["D5", "D6"],
    "fit": "intercept OLS on origin-available latest cost, in USD",
    "forecast_mode": "one frozen fit at the declared origin",
    "score_target": "first-release cost available by snapshot; missing stays unscored"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "invalid object fields")


def integer(value, lower=0, upper=10**9):
    require(type(value) is int and lower <= value <= upper, "bounded integer required; bool/float/text not accepted")


def timestamp(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value), "use canonical UTC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def rational(value):
    require(type(value) is str and re.fullmatch(r"-?\d+(?:/\d+)?", value), "exact rational string required")
    result = F(value)
    require(abs(result.numerator) <= 10000 and result.denominator <= 10000, "rational outside supported bound")
    return result


def validate(data):
    keys(data, ("schema_version", "case_id", "provenance", "currency", "money_unit", "snapshot_at",
        "forecast_origin", "ledger_date", "opening_balances_cents", "ledger", "reported_closing_cash_cents",
        "operations", "forecast_protocol", "investment", "simulation"))
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "schema version")
    require(data["case_id"] == "synthetic_repair_desk_foundation" and type(data["provenance"]) is str
            and "synthetic" in data["provenance"], "synthetic provenance required")
    require(data["currency"] == "USD" and data["money_unit"] == "cent", "USD integer-cent inputs required")
    require(data["snapshot_at"] == "2025-04-12T12:00:00Z" and data["forecast_origin"] == "2025-04-08T12:00:00Z"
            and data["ledger_date"] == "2025-04-07", "fixed scenario dates required")
    snapshot, origin = timestamp(data["snapshot_at"]), timestamp(data["forecast_origin"])
    keys(data["opening_balances_cents"], BALANCES)
    for value in data["opening_balances_cents"].values(): integer(value)
    integer(data["reported_closing_cash_cents"])
    require(type(data["ledger"]) is list and len(data["ledger"]) == 9, "nine ledger records required")
    for index, record in enumerate(data["ledger"]):
        keys(record, ("transaction_id", "kind", "amount_cents"))
        require(record["transaction_id"] == "L"+str(index+1) and record["kind"] == KINDS[index], "ledger key/classification contract")
        integer(record["amount_cents"])
    require(data["forecast_protocol"] == PROTOCOL, "forecast protocol differs from fixed task")
    require(type(data["operations"]) is list and len(data["operations"]) == 6, "six operating records required")
    dates = ("2025-04-01", "2025-04-02", "2025-04-03", "2025-04-04", "2025-04-09", "2025-04-10")
    for index, record in enumerate(data["operations"]):
        keys(record, ("record_id", "period", "active", "scheduled_jobs", "feature_available_at", "cost_releases", "missing_reason"))
        require(record["record_id"] == "D"+str(index+1) and record["period"] == dates[index], "unique ordered day keys required")
        require(record["active"] is True, "all supplied days are active")
        integer(record["scheduled_jobs"], 0, 1000)
        feature_time = timestamp(record["feature_available_at"])
        require(feature_time <= origin and feature_time.date() < date.fromisoformat(record["period"]), "feature unavailable at origin or before scheduled day")
        versions = record["cost_releases"]
        require(type(versions) is list and len(versions) <= 10, "invalid version list")
        require(record["missing_reason"] == (None if versions else "not_reported_by_snapshot"), "missingness must not be recoded as zero/inactive")
        previous = None
        for version, item in enumerate(versions, 1):
            keys(item, ("version", "released_at", "cost_cents"))
            require(type(item["version"]) is int and item["version"] == version, "unique consecutive versions required")
            released = timestamp(item["released_at"])
            require(released.date() > date.fromisoformat(record["period"]) and released <= snapshot,
                    "cost release must follow observation day and belong to snapshot")
            require(previous is None or previous < released, "release versions must be strictly ordered")
            previous = released
            integer(item["cost_cents"])
        if index < 4:
            require(any(timestamp(item["released_at"]) <= origin for item in versions), "required training label unavailable at origin")
    investment = data["investment"]
    keys(investment, ("price_cents", "minimum_cash_reserve_cents", "annual_effective_nominal_rate", "years",
                     "annual_foregone_rent_cents", "states", "persistence", "preference"))
    for field in ("price_cents", "minimum_cash_reserve_cents", "annual_foregone_rent_cents"): integer(investment[field])
    require(investment["years"] == [1,2] and all(type(v) is int for v in investment["years"]), "two year-end payments required")
    require(rational(investment["annual_effective_nominal_rate"]) > -1, "discount rate must exceed -1")
    require(investment["persistence"] == "one state determines both annual payments" and investment["preference"] == "risk neutral; maximize expected discounted incremental USD; tie defer", "capital-law assumptions changed")
    states = investment["states"]
    require(type(states) is list and len(states) == 2, "two states required")
    for state, label in zip(states, ("high", "low")):
        keys(state, ("state", "probability", "annual_gross_savings_cents"))
        require(state["state"] == label, "state labels/order")
        require(0 < rational(state["probability"]) < 1, "strictly positive state probabilities required")
        integer(state["annual_gross_savings_cents"])
    require(sum(rational(s["probability"]) for s in states) == 1, "probabilities must sum to one")
    require(states[0]["annual_gross_savings_cents"] > states[1]["annual_gross_savings_cents"], "high gross saving must exceed low")
    keys(data["simulation"], ("replications", "seed", "sampling"))
    integer(data["simulation"]["replications"], 2, 100000)
    integer(data["simulation"]["seed"], 0, 2**32-1)
    require(data["simulation"]["sampling"] == "one iid two-year project state per replication; exact integer tickets", "simulation unit changed")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: "+key)
        result[key] = value
    return result


def decode(raw):
    def bad(value): raise ValueError("nonfinite JSON constant: "+value)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=bad)


def load(directory):
    directory = Path(directory)
    manifest = decode((directory / MANIFEST).read_bytes())
    require(type(manifest) is dict and type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1
            and manifest.get("case_id") == "synthetic_repair_desk_foundation", "invalid manifest")
    hashes = manifest.get("sha256")
    require(type(hashes) is dict and set(hashes) == {DATA, SOURCE}, "manifest file set")
    for filename, expected in hashes.items():
        require(type(expected) is str and re.fullmatch("[0-9a-f]{64}", expected), "invalid hash")
        require(hashlib.sha256((directory/filename).read_bytes()).hexdigest() == expected, "frozen hash mismatch: "+filename)
    data = decode((directory/DATA).read_bytes())
    validate(data)
    return data, manifest


def packed(value):
    value = F(value)
    return {"exact": str(value), "approx": float(value)}


def ledger(data):
    balance = data["opening_balances_cents"].copy()
    def identity():
        return balance["cash"]+balance["receivables"]+balance["equipment"]-balance["payables"]-balance["loan"]-balance["equity"]
    require(identity() == 0, "opening balance sheet does not reconcile")
    revenue=expense=operating=financing=0
    for record in data["ledger"]:
        kind, amount = record["kind"], record["amount_cents"]
        if kind in ("collect_opening_receivable", "collect_current_receivable"):
            balance["cash"] += amount; balance["receivables"] -= amount; operating += amount
        elif kind == "invoice_current_services":
            balance["receivables"] += amount; balance["equity"] += amount; revenue += amount
        elif kind == "pay_current_operating":
            balance["cash"] -= amount; balance["equity"] -= amount; expense += amount; operating -= amount
        elif kind == "expense_on_credit":
            balance["payables"] += amount; balance["equity"] -= amount; expense += amount
        elif kind == "pay_opening_supplier":
            balance["cash"] -= amount; balance["payables"] -= amount; operating -= amount
        elif kind == "borrow":
            balance["cash"] += amount; balance["loan"] += amount; financing += amount
        elif kind == "repay_principal":
            balance["cash"] -= amount; balance["loan"] -= amount; financing -= amount
        else:
            balance["cash"] -= amount; balance["equity"] -= amount; financing -= amount
        require(identity() == 0, "transaction balance identity failed")
        require(all(balance[k] >= 0 for k in BALANCES if k != "equity"), "transaction overdraws a supplied stock")
    return {"closing_balances_cents": balance, "profit_cents": revenue-expense, "operating_cash_flow_cents": operating,
            "financing_cash_flow_cents": financing, "cash_change_cents": operating+financing,
            "reported_closing_cash_cents": data["reported_closing_cash_cents"],
            "reported_cash_matches": balance["cash"] == data["reported_closing_cash_cents"],
            "balance_sheet_residual_cents": identity()}


def eligible(record, cutoff, first=False):
    versions = [v for v in record["cost_releases"] if timestamp(v["released_at"]) <= timestamp(cutoff)]
    return (versions[0] if first else versions[-1]) if versions else None


def ols(x, y):
    x, y = list(map(F,x)), list(map(F,y))
    require(len(x) == len(y) and len(x) >= 2, "insufficient paired OLS values")
    n = len(x); xm=sum(x)/n; ym=sum(y)/n
    xx=sum((v-xm)**2 for v in x)
    require(xx > 0, "OLS rank deficiency")
    slope=sum((a-xm)*(b-ym) for a,b in zip(x,y))/xx; intercept=ym-slope*xm
    fits=[intercept+slope*v for v in x]; residuals=[v-f for v,f in zip(y,fits)]
    sse=sum(e*e for e in residuals); tss=sum((v-ym)**2 for v in y)
    require(sum(residuals) == sum(a*e for a,e in zip(x,residuals)) == 0, "projection identities failed")
    return {"intercept_usd":packed(intercept),"slope_usd_per_job":packed(slope),"fitted_usd":list(map(packed,fits)),
            "residuals_usd":list(map(packed,residuals)),"sse_usd2":packed(sse),"tss_usd2":packed(tss),
            "r_squared":packed(1-sse/tss) if tss else None,"sum_residuals":"0","sum_jobs_residuals":"0"}


def operational(data):
    training=data["operations"][:4]
    versions=[eligible(r,data["forecast_origin"]) for r in training]
    x=[r["scheduled_jobs"] for r in training]; y=[F(v["cost_cents"],100) for v in versions]
    fit=ols(x,y); a=F(fit["intercept_usd"]["exact"]); b=F(fit["slope_usd_per_job"]["exact"])
    targets=[]; losses=[]
    for record in data["operations"][4:]:
        forecast=a+b*record["scheduled_jobs"]
        outcome=eligible(record,data["snapshot_at"],first=True)
        value=F(outcome["cost_cents"],100) if outcome else None
        error=value-forecast if value is not None else None
        loss=error*error if error is not None else None
        if loss is not None: losses.append(loss)
        targets.append({"record_id":record["record_id"],"target_day":record["period"],"forecast_usd":packed(forecast),
                        "first_release_actual_usd":packed(value) if value is not None else None,
                        "outcome_release_at":outcome["released_at"] if outcome else None,
                        "error_usd":packed(error) if error is not None else None,
                        "squared_error_usd2":packed(loss) if loss is not None else None,
                        "scored":outcome is not None})
    latest_y=[F(eligible(r,data["snapshot_at"])["cost_cents"],100) for r in training]
    latest=ols(x,latest_y)
    return {"training_versions":[{"record_id":r["record_id"],**v} for r,v in zip(training,versions)],
            "frozen_origin_ols":fit,"forecasts":targets,"scored_count":len(losses),"unscored_count":len(targets)-len(losses),
            "available_outcome_mse_usd2":packed(sum(losses)/len(losses)) if losses else None,
            "latest_snapshot_training_refit_for_diagnostic_only":latest,
            "warning":"Later revision refit is not an admissible origin forecast. Available-outcome MSE describes only scored records, not missing targets or population performance."}


def capital(data, closing_cash):
    case=data["investment"]; price=F(case["price_cents"],100); rent=F(case["annual_foregone_rent_cents"],100)
    rate=F(case["annual_effective_nominal_rate"])
    factors=[1/(1+rate)**year for year in case["years"]]; annuity=sum(factors)
    probabilities=[F(s["probability"]) for s in case["states"]]
    benefits=[(F(s["annual_gross_savings_cents"],100)-rent)*annuity for s in case["states"]]
    payoffs=[benefit-price for benefit in benefits]; mean=sum(p*v for p,v in zip(probabilities,payoffs))
    variance=sum(p*(v-mean)**2 for p,v in zip(probabilities,payoffs))
    feasible=closing_cash-case["price_cents"] >= case["minimum_cash_reserve_cents"]
    choice="buy" if feasible and mean > 0 else "defer"
    best=[max(F(0),v) for v in payoffs]
    buy_loss=sum(p*(top-v) for p,top,v in zip(probabilities,best,payoffs)); defer_loss=sum(p*top for p,top in zip(probabilities,best))
    n=data["simulation"]["replications"]; rng=random.Random(data["simulation"]["seed"])
    denominator=math.lcm(*(p.denominator for p in probabilities)); cutoff=int(probabilities[0]*denominator)
    draws=[0 if rng.randrange(denominator) < cutoff else 1 for _ in range(n)]
    simulated=[payoffs[i] for i in draws]; simulated_mean=sum(simulated)/n
    sample_variance=sum((v-simulated_mean)**2 for v in simulated)/(n-1)
    return {"discount_factors":list(map(packed,factors)),"annuity_factor":packed(annuity),
            "state_npv_usd":{s["state"]:packed(v) for s,v in zip(case["states"],payoffs)},
            "expected_npv_usd":packed(mean),"payoff_variance_usd2":packed(variance),
            "expected_regret_usd":{"buy":packed(buy_loss),"defer":packed(defer_loss)},
            "regret_scope":"Unconstrained comparison of the two payoff alternatives; apply the cash-reserve feasibility rule separately.",
            "break_even_price_usd":packed(sum(p*v for p,v in zip(probabilities,benefits))),
            "break_even_high_probability":packed((price-benefits[1])/(benefits[0]-benefits[1])),
            "cash_price_ceiling_usd":packed(F(closing_cash-case["minimum_cash_reserve_cents"],100)),
            "immediate_reserve_feasible":feasible,"decision_from_exact_model":choice,
            "simulation":{"replications":n,"seed":data["simulation"]["seed"],"state_counts":{"high":draws.count(0),"low":draws.count(1)},
                "mean_npv_usd":packed(simulated_mean),"error_against_exact_mean_usd":packed(simulated_mean-mean),
                "estimated_mcse_usd":math.sqrt(float(sample_variance/n)),"theoretical_mcse_usd":math.sqrt(float(variance/n)),
                "unit":"one iid entire two-year project state; no real observations or estimated probabilities"}}


def analyze(data):
    validate(data)
    accounts=ledger(data)
    return {"status":"passed" if accounts["reported_cash_matches"] else "cash-reconciliation-failed",
            "ledger":accounts,"operations":operational(data),"capital":capital(data,accounts["closing_balances_cents"]["cash"]),
            "limits":["All records, probabilities and capital cash flows are synthetic assumptions.",
                      "Missing outcome remains unscored; a later revision does not enter the frozen forecast.",
                      "Simulation error is distinct from parameter uncertainty, prediction error and causal identification."]}


def main(arguments=None):
    args=sys.argv[1:] if arguments is None else arguments
    if len(args)>1:
        print("Usage: python3 foundation-practical-analysis.py [package-directory]",file=sys.stderr);return 2
    directory=Path(args[0]) if args else Path(__file__).resolve().parent
    try:
        data,manifest=load(directory); result=analyze(data)
        result["reproducibility"]={"python_version":platform.python_version(),"implementation":platform.python_implementation(),
            "input_sha256":manifest["sha256"],"program_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "network_required":False,"source_snapshot_at":data["snapshot_at"],"forecast_origin":data["forecast_origin"]}
        print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
    except (OSError,UnicodeError,ValueError,TypeError,KeyError,ZeroDivisionError) as error:
        print("Cannot complete foundation practical: "+str(error),file=sys.stderr);return 1
    return 0 if result["status"]=="passed" else 3


if __name__=="__main__":
    raise SystemExit(main())
