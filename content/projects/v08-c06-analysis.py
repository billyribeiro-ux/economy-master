"""Exact original payout/treasury lab; standard library, no files written."""
from fractions import Fraction as F
import json
from pathlib import Path
import sys


def need(condition, message):
    if not condition:
        raise ValueError(message)


def num(value):
    need(type(value) in (int, str), "use integer or exact decimal/fraction strings")
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("finite rational input required") from exc


def nn(value):
    x = num(value)
    need(x >= 0, "nonnegative input required")
    return x


def encode(value):
    if isinstance(value, F): return str(value)
    if isinstance(value, dict): return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list): return [encode(v) for v in value]
    return value


def payout(p):
    e, cash, n, q, income, yield_, holder = [nn(p[k]) for k in (
        "equity_value", "available_excess_cash", "shares", "distribution",
        "forecast_income_before", "cash_income_rate", "holder_shares")]
    need(n > 0 and e > 0 and q < e and q <= cash <= e and holder <= n, "equity/share/cash domain")
    price = e / n; after = e - q; new_income = income - yield_ * q
    need(new_income >= 0, "negative-income EPS comparison outside this lab")
    need(isinstance(p["repurchase_prices"], list) and p["repurchase_prices"], "at least one execution price required")
    rows = []
    for raw in p["repurchase_prices"]:
        execution = nn(raw)
        need(execution > 0, "repurchase price must be positive")
        retired = q / execution
        need(retired < n, "repurchase cannot retire every share in this model")
        remaining = n - retired; after_price = after / remaining
        gain = after - remaining * price
        holder_sold = holder * retired / n
        rows.append({"execution_price": execution, "retired_shares": retired, "remaining_shares": remaining,
                     "equity_after": after, "value_per_remaining_share": after_price,
                     "remaining_group_transfer": gain, "selling_group_transfer": q - retired * price,
                     "forecast_eps": new_income / remaining, "pro_rata_holder_cash": holder_sold * execution,
                     "pro_rata_holder_shares": holder - holder_sold,
                     "pro_rata_holder_wealth": holder_sold * execution + (holder - holder_sold) * after_price})
    return {"fair_price_before": price, "equity_before": e, "income_before": income,
            "eps_before": income / n, "income_after": new_income,
            "dividend_per_share": q / n, "ex_dividend_price": after / n,
            "dividend_eps": new_income / n,
            "dividend_holder_cash": holder * q / n,
            "dividend_holder_wealth": holder * (q / n + after / n), "repurchases": rows}


def treasury(p, scenario, q):
    q = nn(q)
    c, minimum, term, amort, rate, limit, cap, payout_cap, cost, receipt = [nn(p[k]) for k in (
        "opening_cash", "minimum_cash", "term_debt", "term_repayment_at_two", "quarter_rate",
        "line_limit", "total_debt_cap", "date_zero_payout_cap", "project_cost_at_one", "project_receipt_at_two")]
    need(amort <= term <= cap and minimum <= c, "opening term/cash constraints")
    receipts = [nn(x) for x in p["base_receipts"]]; payments = [nn(x) for x in p["base_operating_payments"]]
    need(len(receipts) == len(payments) == 2, "two-period planning contract")
    lag, prepay = [nn(scenario[k]) for k in ("delayed_collection", "supplier_prepayment")]
    need(lag <= receipts[0] and prepay <= payments[1], "timing transfer exceeds originating cash")
    op = [receipts[0] - lag - payments[0] - prepay,
          receipts[1] + lag - payments[1] + prepay]
    effective = min(limit, cap - term); interest = term * rate
    cash0 = c - q
    if q > payout_cap or cash0 < minimum:
        return {"status": "payout-not-permitted-at-date-zero", "payout": q, "closing": None}
    before1 = cash0 + op[0] - interest - cost
    required = max(F(0), minimum - before1)
    available_cash = before1 + effective
    common = {"payout": q, "operating_cash": op, "cash_after_payout": cash0,
              "effective_line_at_one": effective, "cash_before_draw": before1,
              "required_draw": required, "term_interest_each_quarter": interest}
    if required > effective:
        return dict(common, status="funding-failure-at-date-one", gap=required-effective,
                    cash_after_maximum_draw=available_cash, closing=None,
                    explanation="No compliant funded project or date 2 close is asserted.")
    cash1 = before1 + required; revolver_interest = required * rate
    cash2 = cash1 + op[1] + receipt - interest - revolver_interest - amort - required
    row = dict(common, cash_at_one=cash1, revolver_at_one=required, line_headroom=limit-required,
               covenant_headroom=cap-term-required, usable_debt_headroom=effective-required,
               revolver_interest=revolver_interest, cash_after_all_date_two_payments=cash2)
    if cash2 < minimum:
        return dict(row, status="funding-failure-at-date-two", gap=minimum-cash2, closing=None,
                    explanation="Maturing revolver cannot be rolled over; no compliant closing balance asserted.")
    return dict(row, status="funded", closing={"cash": cash2, "term_debt": term-amort, "revolver": F(0)})


def limits(p):
    c, m, term, amort, rate, line, cap, qcap, cost, receipt = [nn(p[k]) for k in (
        "opening_cash", "minimum_cash", "term_debt", "term_repayment_at_two", "quarter_rate",
        "line_limit", "total_debt_cap", "date_zero_payout_cap", "project_cost_at_one", "project_receipt_at_two")]
    rows = {}
    for name, s in p["scenarios"].items():
        baseline = treasury(p, s, 0)
        op = baseline["operating_cash"]
        # Date1 cash without payout/borrowing is A; draw=max(0,q-(A-m)).
        a = c + op[0] - term*rate - cost; h = a-m
        first = h + min(line,cap-term)
        # Date2 cash = S-q-rate*max(0,q-h), with all line principal repaid.
        total = c + sum(op) + receipt - cost - 2*term*rate - amort
        budget = total-m
        second = budget if budget <= h else (budget+rate*h)/(1+rate)
        state_limit = min(c-m, qcap, first, second)
        rows[name] = {"date_one_bound": first, "date_two_bound": second,
                      "maximum_initial_payout": state_limit if state_limit >= 0 else None}
    values = [row["maximum_initial_payout"] for row in rows.values()]
    maximum = min(values) if values and all(v is not None for v in values) else None
    return {"scenario_bounds": rows, "maximum_across_supplied_states": maximum}


def personal_tax(p, t):
    e, n, q, holder = [nn(p[k]) for k in ("equity_value", "shares", "distribution", "holder_shares")]
    basis, td, tg = [nn(t[k]) for k in ("basis_per_share", "dividend_tax", "capital_gain_tax")]
    need(td <= 1 and tg <= 1 and n > 0 and e > q, "tax/share domain")
    price=e/n; ex=(e-q)/n
    need(basis <= ex, "negative capital gains outside tax exercise")
    dividend=holder*q/n; sold=dividend/price; remain=holder-sold
    div_event=dividend*(1-td); rep_event=dividend-sold*(price-basis)*tg
    div_liquidation=holder*ex-holder*(ex-basis)*tg
    rep_liquidation=remain*price-remain*(price-basis)*tg
    return {"dividend_event_net_cash": div_event, "repurchase_event_net_cash": rep_event,
            "dividend_remaining_sale_net": div_liquidation, "repurchase_remaining_sale_net": rep_liquidation,
            "dividend_total_after_liquidation": div_event+div_liquidation,
            "repurchase_total_after_liquidation": rep_event+rep_liquidation}


def run(data):
    need(data["case"] == "Portico Instruments and Dunlin Packaging: original payout and liquidity cases", "fixed case")
    need(data["units"] == "money kCU; shares thousands; share prices CU; stated period rates", "units contract")
    p = data["liquidity"]
    need(p["dates"] == ["2027-01-01","2027-04-01","2027-07-01"], "quarterly dates contract")
    need(set(p["scenarios"]) == {"normal","slow_collection","combined"}, "three scenario labels required")
    bound=limits(p)
    paths={str(nn(q)): {name:treasury(p,s,q) for name,s in p["scenarios"].items()} for q in p["candidate_payouts"]}
    if bound["maximum_across_supplied_states"] is not None:
        need(all(treasury(p,s,str(bound["maximum_across_supplied_states"]))["status"]=="funded" for s in p["scenarios"].values()), "calculated payout limit is not feasible")
    kept=data["retained_cash"]; cash,inside,outside=[nn(kept[k]) for k in ("cash","inside_rate","outside_rate")]
    periods=kept["periods"];need(type(periods) is int and periods > 0, "positive integer retention periods")
    retained_value=cash*((1+inside)/(1+outside))**periods
    discount=nn(p["project_discount_rate"])
    return encode({"payout":payout(data["payout"]), "personal_tax":personal_tax(data["payout"],data["personal_tax_exercise"]),
                   "retained_cash":{"value":retained_value,"loss_against_immediate_distribution":cash-retained_value},
                   "liquidity":{"limits":bound,"paths":paths,
                                "project_npv_at_date_one":nn(p["project_receipt_at_two"])/(1+discount)-nn(p["project_cost_at_one"])},
                   "limitation":"Original conditional payout and dated cash planning; no estimated fair value, real tax/covenant permission, state probability or optimal-risk guarantee."})


if __name__ == "__main__":
    try:
        need(len(sys.argv) <= 2, "usage: python3 v08-c06-analysis.py [inputs.json]")
        source=Path(sys.argv[1]) if len(sys.argv)==2 else Path(__file__).with_name("v08-c06-inputs.json")
        print(json.dumps(run(json.loads(source.read_text(encoding="utf-8"))),indent=2,allow_nan=False))
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print("Invalid payout/liquidity contract: "+str(exc),file=sys.stderr)
        sys.exit(2)
