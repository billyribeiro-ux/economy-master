"""Exact finite Meridian Components benchmark; Python standard library only."""
from fractions import Fraction as F
from pathlib import Path
import json
import sys

UNITS = {"money":"CU", "output":"whole units", "machine":"hours", "setup":"batches", "period":"one month"}


def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,str)):
        raise ValueError("use integer or exact string inputs")
    try:
        x=F(value)
    except (ValueError,ZeroDivisionError) as exc:
        raise ValueError("invalid exact amount") from exc
    if x < 0:
        raise ValueError("negative input")
    return x


def whole(value, maximum, positive=False):
    x=number(value)
    if x.denominator != 1 or x > maximum or (positive and x == 0):
        raise ValueError("integer outside this finite teaching-model domain")
    return int(x)


def batches(units, size):
    return (units+size-1)//size


def validate(data):
    if data.get("case") != "Meridian Components one-month teaching model" or data.get("units") != UNITS:
        raise ValueError("unsupported case or units")
    if set(data["products"]) != {"S","P"}:
        raise ValueError("exactly products S and P required")
    products={}
    for key,p in data["products"].items():
        products[key]=dict(price=number(p["price"]),variable=number(p["variable"]),
                           hours=whole(p["hours"],100,True),batch_size=whole(p["batch_size"],200,True),
                           demand=whole(p["demand"],200))
    h=whole(data["capacity"]["machine_hours"],2000,True)
    b=whole(data["capacity"]["setup_batches"],200,True)
    pools={k:number(data["pools"][k]) for k in ("machine","setups","common")}
    if sum(pools.values()) <= 0:
        raise ValueError("this fixture requires positive total committed fixed cost")
    baseline={k:whole(data["baseline"][k],200) for k in ("S","P")}
    mix={k:whole(data["mix"][k],200,True) for k in ("S","P")}
    order=data["special_order"]
    special=dict(quantity=whole(order["quantity"],200,True),price=number(order["price"]),
                 variable=number(order["variable"]),hours=whole(order["hours"],100,True),
                 batch_size=whole(order["batch_size"],200,True),extra_cash=number(order["extra_cash"]))
    opening=number(data["opening_cash_and_equity"])
    if opening < sum(products[k]["variable"]*products[k]["demand"] for k in products)+sum(pools.values()):
        raise ValueError("opening cash must fund all regular demand before collections in this fixture")
    return products,h,b,pools,baseline,mix,special,opening


def feasible(products, quantities, hours, setups):
    return (all(0 <= quantities[k] <= p["demand"] for k,p in products.items()) and
            sum(quantities[k]*p["hours"] for k,p in products.items()) <= hours and
            sum(batches(quantities[k],p["batch_size"]) for k,p in products.items()) <= setups)


def solve(products, hours, setups):
    """Enumerate every admissible pair, retaining all exact maximizers."""
    if hours < 0 or setups < 0:
        raise ValueError("negative remaining capacity")
    best=None; choices=[]; count=0
    for s in range(products["S"]["demand"]+1):
        for p in range(products["P"]["demand"]+1):
            q={"S":s,"P":p}
            if not feasible(products,q,hours,setups):
                continue
            count+=1
            value=sum(q[k]*(v["price"]-v["variable"]) for k,v in products.items())
            if best is None or value > best:
                best=value;choices=[q]
            elif value == best:
                choices.append(q)
    return dict(contribution=best,choices=choices,feasible_pairs=count)


def allocate(products,q,h,b,pools,opening):
    if not feasible(products,q,h,b):
        raise ValueError("infeasible operating plan")
    used_h={k:q[k]*p["hours"] for k,p in products.items()}
    used_b={k:batches(q[k],p["batch_size"]) for k,p in products.items()}
    total_h=sum(used_h.values());total_b=sum(used_b.values())
    fixed=sum(pools.values()); revenue=sum(q[k]*p["price"] for k,p in products.items())
    variable=sum(q[k]*p["variable"] for k,p in products.items());cm=revenue-variable
    machine_rate=pools["machine"]/h;setup_rate=pools["setups"]/b
    assigned={k:machine_rate*used_h[k]+setup_rate*used_b[k] for k in products}
    unused_machine=pools["machine"]-machine_rate*total_h
    unused_setup=pools["setups"]-setup_rate*total_b
    # At zero production the retrospective actual-hours allocation is undefined.
    traditional={k:fixed*used_h[k]/total_h for k in products} if total_h else None
    product_cm={k:q[k]*(p["price"]-p["variable"]) for k,p in products.items()}
    return dict(quantities=q,hours=total_h,setups=total_b,revenue=revenue,variable=variable,
                contribution=cm,fixed=fixed,profit=cm-fixed,cash_change=cm-fixed,
                ending_cash=opening+cm-fixed,ending_equity=opening+cm-fixed,
                machine_rate=machine_rate,setup_rate=setup_rate,abc_assigned=assigned,
                abc_product_margin={k:product_cm[k]-assigned[k] for k in products},
                unused_machine=unused_machine,unused_setups=unused_setup,common=pools["common"],
                traditional_allocation=traditional,
                traditional_product_margin={k:product_cm[k]-traditional[k] for k in products} if traditional else None)


def json_exact(x):
    if isinstance(x,F): return str(x)
    if isinstance(x,dict): return {k:json_exact(v) for k,v in x.items()}
    if isinstance(x,list): return [json_exact(v) for v in x]
    return x


def run(data):
    products,h,b,pools,base,mix,special,opening=validate(data)
    baseline=allocate(products,base,h,b,pools,opening)
    optimum=solve(products,h,b)
    first_plan=allocate(products,optimum["choices"][0],h,b,pools,opening)
    bundle_cm=sum(mix[k]*(p["price"]-p["variable"]) for k,p in products.items())
    if bundle_cm > 0:
        continuous=sum(pools.values())/bundle_cm
        integral=(continuous.numerator+continuous.denominator-1)//continuous.denominator
        breakeven=dict(bundle_contribution=bundle_cm,continuous_bundles=continuous,
                       minimum_whole_bundles=integral,
                       minimum_plan_feasible=feasible(products,{k:integral*mix[k] for k in mix},h,b))
    else:
        breakeven=dict(bundle_contribution=bundle_cm,continuous_bundles=None,
                       minimum_whole_bundles=None,minimum_plan_feasible=False)
    qty=special["quantity"];reserve_h=qty*special["hours"];reserve_b=batches(qty,special["batch_size"])
    direct=qty*(special["price"]-special["variable"])-special["extra_cash"]
    idle_feasible=feasible(products,base,h-reserve_h,b-reserve_b)
    if reserve_h <= h and reserve_b <= b:
        displaced=solve(products,h-reserve_h,b-reserve_b)
        opportunity=optimum["contribution"]-displaced["contribution"]
        busy=dict(remaining_regular_choices=displaced["choices"],opportunity_cost=opportunity,
                  incremental_profit=direct-opportunity,
                  break_even_unit_quote=special["variable"]+(special["extra_cash"]+opportunity)/qty)
    else:
        busy=None
    return json_exact(dict(case=data["case"],units=UNITS,baseline=baseline,optimum=optimum,
                           first_optimal_plan=first_plan,break_even=breakeven,
                           special_order=dict(idle_plan_feasible=idle_feasible,
                                              idle_incremental_profit=direct if idle_feasible else None,
                                              idle_break_even_quote=special["variable"]+special["extra_cash"]/qty,
                                              busy=busy)))


def main():
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name("v07-c08-inputs.json")
    try:
        result=run(json.loads(path.read_text()))
    except (ValueError,KeyError,TypeError) as exc:
        raise SystemExit(f"Invalid teaching-case input: {exc}") from exc
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
