"""Original, offline cash-flow teaching program for v04-c03.

Run: python3 v04-c03-cashflow.py
Keep v04-c03-case.json beside this script. Only the standard library is used.
Inputs are synthetic; see v04-c03-readme.txt for units and boundaries.
"""

import json
import math
from pathlib import Path
import sys


def validate_values(cash_flows_cents, discount_rate_bps):
    """Reject values outside this teaching tool's explicit contract."""
    if type(cash_flows_cents) is not list:
        raise TypeError("cash_flows_cents must be a list")
    if not 1 <= len(cash_flows_cents) <= 101:
        raise ValueError("supply t=0 and at most 100 annual future flows")
    for cents in cash_flows_cents:
        # Exact type rejects True/False, floats and quoted numbers.
        if type(cents) is not int:
            raise TypeError("each cash flow must be an integer number of cents")
        if abs(cents) > 10**12:
            raise ValueError("each cash flow must be within +/- 10**12 cents")
    if type(discount_rate_bps) is not int:
        raise TypeError("discount_rate_bps must be an integer")
    if not -5000 <= discount_rate_bps <= 10000:
        raise ValueError("this tool supports rates from -5000 to 10000 bps")


def npv_cents(cash_flows_cents, discount_rate_bps):
    """Return approximate NPV in cents; never mutate the input list.

    Entries are t=0, then year ends 1, 2, ... . The annual effective rate
    is an integer number of basis points. See validate_values for bounds.
    Raise TypeError/ValueError for invalid arguments. No files or printing.
    """
    validate_values(cash_flows_cents, discount_rate_bps)
    rate = discount_rate_bps / 10000
    terms = []
    for period, cents in enumerate(cash_flows_cents):
        terms.append(cents / (1 + rate)**period)
    return math.fsum(terms)


def unique_object(pairs):
    """JSON callback: form a dictionary, rejecting repeated field names."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field: " + key)
        result[key] = value
    return result


def load_case(path):
    """Read a small local UTF-8 JSON file and validate its schema and units."""
    with path.open("r", encoding="utf-8") as handle:
        case = json.load(handle, object_pairs_hook=unique_object)
    if type(case) is not dict:
        raise TypeError("the case must be a JSON object")
    required = ["case_id", "currency", "period", "timing", "provenance",
                "cash_flows_cents", "discount_rate_bps"]
    for key in required:
        if key not in case:
            raise ValueError("missing field: " + key)
    if len(case) != len(required):
        raise ValueError("unexpected field in case")
    for key in ["case_id", "provenance"]:
        if type(case[key]) is not str or not case[key].strip():
            raise ValueError(key + " must be nonblank text")
    if case["currency"] != "USD":
        raise ValueError("this teaching tool requires currency USD")
    if case["period"] != "year" or case["timing"] != "t0_then_year_end":
        raise ValueError("use year periods with timing t0_then_year_end")
    validate_values(case["cash_flows_cents"], case["discount_rate_bps"])
    return case


def make_report(case):
    """Calculate a report from a case returned by load_case; no side effects."""
    flows = case["cash_flows_cents"]
    value = npv_cents(flows, case["discount_rate_bps"])
    return {
        "case_id": case["case_id"],
        "currency": case["currency"],
        "period": case["period"],
        "timing": case["timing"],
        "provenance": case["provenance"],
        "discount_rate_bps": case["discount_rate_bps"],
        "last_period": len(flows) - 1,
        "undiscounted_net_cents": sum(flows),
        "npv_cents_approx": value,
        "npv_dollars_display": f"{value / 100:.2f}",
    }


def main():
    """Read beside the script; print JSON on success or an error on failure."""
    try:
        path = Path(__file__).resolve().parent / "v04-c03-case.json"
        case = load_case(path)
        report = make_report(case)
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        print("Input error: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
