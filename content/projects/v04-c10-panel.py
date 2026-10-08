#!/usr/bin/env python3
"""Synthetic monthly panel, aggregation and exact moment teaching laboratory.

Only main reads external files/prints. All numerical results use Fraction.
The inactive-sales zero convention applies only to this closed-roster flow
accounting target. Unknown active reports never become zero.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import re
import sys


SUPPORTED_UNITS = {
    "nominal_sales": "USD per calendar month",
    "real_sales": "January 2024 price USD per calendar month",
    "price_index": "January 2024=100, one good with base price 1 USD",
    "inventory": "units at month end",
    "return": "basis points per month, fully reinvested without external cash flows",
}
BASE_MONTH = "2024-01"


def month_number(text):
    if type(text) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}", text) is None:
        raise ValueError("month must have exact YYYY-MM form")
    year, month = map(int, text.split("-"))
    if not 1900 <= year <= 2100 or not 1 <= month <= 12:
        raise ValueError("month outside supported calendar range")
    return 12 * year + month - 1


def month_text(number):
    year, zero_month = divmod(number, 12)
    return f"{year:04d}-{zero_month + 1:02d}"


def keys(obj, expected, label):
    if type(obj) is not dict or set(obj) != set(expected):
        raise ValueError(label + " has missing or unknown fields")


def integer(value, minimum=0, maximum=1000000000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("unsupported integer value")
    return value


def text(value):
    if type(value) is not str or not value.strip():
        raise ValueError("require nonempty text")
    return value


def validate(data):
    keys(data, ["schema_version", "provenance", "units", "window", "roster", "prices", "sales",
                "quarter", "annualized_quarter_flow_usd", "law"], "document")
    if integer(data["schema_version"], 1, 1) != 1:
        raise ValueError("unsupported schema")
    text(data["provenance"])
    keys(data["units"], ["nominal_sales", "real_sales", "price_index", "inventory", "return"], "units")
    if data["units"] != SUPPORTED_UNITS:
        raise ValueError("units must match the supported USD/month and January-2024 price-base contract")
    keys(data["window"], ["start", "end"], "window")
    first = month_number(data["window"]["start"])
    last = month_number(data["window"]["end"])
    if not 3 <= last - first + 1 <= 24:
        raise ValueError("window must contain 3 through 24 consecutive months")
    if not first <= month_number(BASE_MONTH) <= last:
        raise ValueError("this fixed-base lab requires January 2024 in the analysis window")
    roster = {}
    if type(data["roster"]) is not list or not 1 <= len(data["roster"]) <= 16:
        raise ValueError("require 1 through 16 roster entities")
    for row in data["roster"]:
        keys(row, ["entity", "active_from", "active_through"], "roster row")
        entity = text(row["entity"])
        begin, end = month_number(row["active_from"]), month_number(row["active_through"])
        if entity in roster or begin > end:
            raise ValueError("duplicate entity or reversed active interval")
        roster[entity] = (begin, end)
    prices = {}
    if type(data["prices"]) is not list or len(data["prices"]) != last-first+1:
        raise ValueError("one price per window month required")
    for row in data["prices"]:
        keys(row, ["month", "index"], "price row")
        period = month_number(row["month"])
        if period in prices or not first <= period <= last:
            raise ValueError("duplicate/out-of-window price month")
        prices[period] = integer(row["index"], 1, 1000000)
    if prices[month_number(BASE_MONTH)] != 100:
        raise ValueError("January 2024 price index must equal 100 for the supported base")
    sales = {}
    if type(data["sales"]) is not list or len(data["sales"]) > 384:
        raise ValueError("unsupported sales row count")
    for row in data["sales"]:
        keys(row, ["entity", "month", "nominal_usd"], "sales row")
        entity = text(row["entity"]); period = month_number(row["month"])
        if entity not in roster or not first <= period <= last:
            raise ValueError("unknown entity or out-of-window observation")
        if not roster[entity][0] <= period <= roster[entity][1]:
            raise ValueError("observed sales outside operation")
        key = (entity, period)
        if key in sales:
            raise ValueError("duplicate entity-month key")
        sales[key] = integer(row["nominal_usd"])
    if type(data["quarter"]) is not list or len(data["quarter"]) != 3:
        raise ValueError("quarter requires three complete monthly records")
    quarter_months = []
    for row in data["quarter"]:
        keys(row, ["month", "nominal_usd", "end_inventory", "defects", "deliveries", "return_bps"], "quarter row")
        period = month_number(row["month"])
        quarter_months.append(period)
        if period not in prices:
            raise ValueError("quarter month lacks matching index")
        for name in ["nominal_usd", "end_inventory", "defects", "deliveries"]:
            integer(row[name])
        if row["defects"] > row["deliveries"]:
            raise ValueError("defects cannot exceed deliveries")
        integer(row["return_bps"], -10000, 1000000)
    ordered = sorted(quarter_months)
    if ordered[0] % 3 != 0 or ordered != list(range(ordered[0], ordered[0] + 3)):
        raise ValueError("quarter must contain each month of one calendar quarter")
    integer(data["annualized_quarter_flow_usd"])
    keys(data["law"], ["mean", "shock_magnitude", "ma_numerator", "ma_denominator", "average_length", "random_walk_horizon"], "law")
    law = data["law"]
    integer(law["mean"], -1000000, 1000000)
    integer(law["shock_magnitude"], 0, 10000)
    integer(law["ma_numerator"], -100, 100)
    integer(law["ma_denominator"], 1, 100)
    integer(law["average_length"], 1, 1000)
    integer(law["random_walk_horizon"], 1, 1000)
    return first, last, roster, prices, sales


def average(values):
    return sum(values, F(0)) / len(values) if values else None


def proportional_change(current, previous):
    if current is None or previous is None or previous == 0:
        return None
    return current / previous - 1


def make_report(data):
    first, last, roster, prices, sales = validate(data)
    real = {key: F(100 * nominal, prices[key[1]]) for key, nominal in sales.items()}
    def status(entity, period):
        if not first <= period <= last:
            return "outside_analysis_window"
        if not roster[entity][0] <= period <= roster[entity][1]:
            return "not_operating"
        return "observed" if (entity, period) in real else "active_unreported"
    grid = []
    for entity in sorted(roster):
        for period in range(first, last + 1):
            value = real.get((entity, period)); lag = real.get((entity, period - 1))
            grid.append({"entity": entity, "month": month_text(period), "status": status(entity, period),
                         "real_usd": value, "lag_status": status(entity, period-1), "lag_real_usd": lag,
                         "real_difference": value-lag if value is not None and lag is not None else None,
                         "real_growth": proportional_change(value, lag)})
    monthly = []
    for period in range(first, last + 1):
        observed = [real[(entity, period)] for entity in sorted(roster) if (entity, period) in real]
        active = [entity for entity,(begin,end) in roster.items() if begin <= period <= end]
        total = sum(observed, F(0))
        monthly.append({"month":month_text(period), "active_count":len(active), "observed_count":len(observed),
                        "observed_subtotal_real_usd":total, "observed_mean_real_usd":average(observed),
                        "whole_roster_total_real_usd":total if len(observed) == len(active) else None})
    endpoint_entities = [entity for entity in sorted(roster) if (entity,first) in real and (entity,last) in real]
    complete_entities = [entity for entity in sorted(roster) if all((entity,t) in real for t in range(first,last+1))]
    def cohort(entities):
        begin=average([real[(entity,first)] for entity in entities])
        end=average([real[(entity,last)] for entity in entities])
        return {"entities":entities,"first_mean":begin,"last_mean":end,"growth":proportional_change(end,begin)}
    # Endpoint total decomposition is reported only if all active endpoint values
    # are known. Inactive sales flow is zero for this explicitly defined roster.
    decomposition = None
    if monthly[0]["whole_roster_total_real_usd"] is not None and monthly[-1]["whole_roster_total_real_usd"] is not None:
        continuing = entering = exiting = F(0)
        for entity,(begin,end) in roster.items():
            active_first = begin <= first <= end
            active_last = begin <= last <= end
            if active_first and active_last:
                continuing += real[(entity,last)]-real[(entity,first)]
            elif active_last:
                entering += real[(entity,last)]
            elif active_first:
                exiting -= real[(entity,first)]
        decomposition = {"continuing_change":continuing,"entry_contribution":entering,
                         "exit_contribution":exiting,"total_change":continuing+entering+exiting}
    q = sorted(data["quarter"], key=lambda row: month_number(row["month"]))
    nominal = sum(row["nominal_usd"] for row in q)
    qreal = sum((F(100*row["nominal_usd"],prices[month_number(row["month"])]) for row in q),F(0))
    mean_index = F(sum(prices[month_number(row["month"])] for row in q),3)
    defects = sum(row["defects"] for row in q); deliveries=sum(row["deliveries"] for row in q)
    rates = [F(row["defects"],row["deliveries"]) if row["deliveries"] else None for row in q]
    gross = F(1)
    for row in q:
        gross *= 1+F(row["return_bps"],10000)
    law=data["law"]; variance=F(law["shock_magnitude"]**2)
    theta=F(law["ma_numerator"],law["ma_denominator"]); n=law["average_length"]
    gamma0=variance*(1+theta**2); gamma1=theta*variance
    return {"data_kind":"synthetic", "grid":grid, "monthly":monthly,
            "endpoint_cohort":cohort(endpoint_entities), "complete_window_cohort":cohort(complete_entities),
            "observed_endpoint_mean_growth":proportional_change(monthly[-1]["observed_mean_real_usd"],monthly[0]["observed_mean_real_usd"]),
            "endpoint_total_decomposition":decomposition,
            "quarter":{"nominal_sales_usd":nominal,"real_sales_base_usd":qreal,
                       "incorrect_mean_index_deflation":F(100*nominal)/mean_index,
                       "consistent_aggregate_index":F(100*nominal)/qreal if qreal else None,
                       "quarter_end_inventory":q[-1]["end_inventory"],
                       "mean_observed_endpoint_inventory":F(sum(row["end_inventory"] for row in q),3),
                       "defects":defects,"deliveries":deliveries,
                       "pooled_defect_rate":F(defects,deliveries) if deliveries else None,
                       "mean_monthly_defect_rate":average(rates) if all(v is not None for v in rates) else None,
                       "compounded_return":gross-1,"quarter_flow_usd":F(data["annualized_quarter_flow_usd"],4)},
            "stipulated_law_moments":{"mean":law["mean"],"gamma0":gamma0,"gamma1":gamma1,"gamma2":F(0),
                                      "rho1":gamma1/gamma0 if gamma0 else None,
                                      "average_variance":(n*gamma0+2*(n-1)*gamma1)/n**2,
                                      "iid_average_variance":gamma0/n,
                                      "random_walk_variance_at_horizon":law["random_walk_horizon"]*variance}}


def encode(value):
    if isinstance(value,F):
        return str(value)
    raise TypeError("unsupported report type")


def unique_fields(pairs):
    obj={}
    for key,value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON name: "+key)
        obj[key]=value
    return obj


def reject_constant(value):
    raise ValueError("nonfinite JSON constant: "+value)


def load_data(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle,object_pairs_hook=unique_fields,parse_constant=reject_constant)


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if len(args)>1:
        print("usage: python3 v04-c10-panel.py [data.json]",file=sys.stderr)
        return 2
    path=Path(args[0]) if args else Path(__file__).resolve().with_name("v04-c10-data.json")
    try:
        result=make_report(load_data(path))
    except (ValueError,OSError) as error:
        print("longitudinal input error: "+str(error),file=sys.stderr)
        return 2
    print(json.dumps(result,default=encode,indent=2,allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
