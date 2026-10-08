"""Exact small private-capital lab. No network, third-party packages or implicit finance.

Run: python3 v08-c10-analysis.py [inputs.json]
Fractions serialize as rational strings; only numerical IRRs use floats.
See the companion README for the deliberately bounded financial domains.
"""
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import sys


def q(value):
    return F(str(value))


def vector(values):
    return [q(value) for value in values]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def wire(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(item) for item in value]
    return value


def block_irr(flows):
    """Unique annual IRR when every contribution precedes every receipt.

    Compare receipts discounted to last contribution with contributions accumulated
    to that date. The former strictly decreases in x=1+r; the latter is nondecreasing.
    """
    flows = vector(flows)
    negative = [t for t, cash in enumerate(flows) if cash < 0]
    positive = [t for t, cash in enumerate(flows) if cash > 0]
    require(negative and positive, "IRR requires both contributions and receipts")
    k = max(negative)
    require(k < min(positive), "IRR domain requires all contributions before receipts")

    def balance(x):
        return sum(float(cash) * x ** (k - t) for t, cash in enumerate(flows))

    lo, hi = 1e-10, 2.0
    require(balance(lo) > 0, "IRR root lies outside the supported positive-x bracket")
    for _ in range(128):
        if balance(hi) < 0:
            break
        hi *= 2
    else:
        raise ValueError("IRR upper bracket unavailable")
    for _ in range(120):
        mid = (lo + hi) / 2
        if balance(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2 - 1


def multiple(flows):
    paid = -sum(cash for cash in flows if cash < 0)
    require(paid > 0, "Multiple requires positive paid-in capital")
    return sum(cash for cash in flows if cash > 0) / paid


def buyout(data):
    fields = ["entry_ev", "entry_ebitda", "excess_cash", "old_debt", "deal_fee",
              "financing_fee", "new_debt", "loan_rate", "tax_rate", "exit_multiple", "exit_fee"]
    a = {key: q(data[key]) for key in fields}
    require(all(value >= 0 for value in a.values()), "LBO scalar inputs must be nonnegative")
    require(a["entry_ebitda"] > 0 and a["new_debt"] > 0 and a["tax_rate"] < 1,
            "LBO requires positive entry EBITDA/debt and tax rate below one")
    names = ["ebitda", "depreciation", "capex", "nwc_increase", "minimum_principal", "sponsor_topups"]
    series = {name: vector(data[name]) for name in names}
    require(all(len(values) == 3 for values in series.values()), "LBO requires three annual periods")
    require(all(value >= 0 for values in series.values() for value in values),
            "LBO annual inputs must be nonnegative")
    require(series["sponsor_topups"][-1] == 0,
            "Lab allows sponsor repairs before, not at, the final exit date")
    seller = a["entry_ev"] + a["excess_cash"] - a["old_debt"]
    fees = a["deal_fee"] + a["financing_fee"]
    uses = seller + a["old_debt"] + fees
    sponsor = uses - a["new_debt"] - a["excess_cash"]
    require(seller >= 0 and sponsor > 0, "Entry seller/sponsor cash outside supported domain")
    debt = a["new_debt"]
    rows = []
    flows = [-sponsor]
    lender = [-debt]
    result = {"seller_equity": seller, "entry_uses": uses,
              "entry_sources": a["new_debt"] + a["excess_cash"] + sponsor,
              "sponsor_initial": sponsor, "annual": rows}
    for t in range(3):
        ebitda, da, capex, nwc, scheduled, topup = (series[name][t] for name in names)
        interest = debt * a["loan_rate"]
        taxable = ebitda - da - interest
        require(taxable >= 0, "LBO tax domain requires nonnegative taxable operating profit")
        tax = a["tax_rate"] * taxable
        fcff = (ebitda - da) * (1 - a["tax_rate"]) + da - capex - nwc
        cash = ebitda - tax - interest - capex - nwc
        row = {"date": t + 1, "opening_debt": debt, "interest": interest,
               "cash_tax": tax, "fcff": fcff, "cash_before_principal": cash,
               "sponsor_topup": topup, "minimum_principal": scheduled}
        rows.append(row)
        require(scheduled <= debt, "Scheduled principal exceeds opening debt")
        if cash + topup < scheduled:
            row["funding_gap"] = scheduled - cash - topup
            result.update(feasible=False, failure="annual debt service", failure_date=t + 1)
            return result
        repayment = cash + topup
        require(0 <= repayment < debt, "Lab requires positive remaining debt after each cash sweep")
        debt -= repayment
        row.update(principal=repayment, closing_debt=debt)
        flows.append(-topup)
        lender.append(interest + repayment)
    exit_ev = a["exit_multiple"] * series["ebitda"][-1]
    exit_pot = exit_ev - a["exit_fee"]
    if exit_pot <= debt:
        result.update(feasible=False, failure="exit cannot repay debt and leave positive equity",
                      failure_date=3, exit_ev=exit_ev, exit_debt=debt)
        return result
    equity = exit_pot - debt
    flows[-1] += equity
    lender[-1] += debt
    entry_multiple = a["entry_ev"] / a["entry_ebitda"]
    decomposition = {
        "operating_change": entry_multiple * (series["ebitda"][-1] - a["entry_ebitda"]),
        "multiple_change": (a["exit_multiple"] - entry_multiple) * series["ebitda"][-1],
        "debt_reduction": a["new_debt"] - debt,
        "entry_and_exit_fees": -fees - a["exit_fee"],
        "later_sponsor_contributions": -sum(series["sponsor_topups"])
    }
    result.update(feasible=True, exit_ev=exit_ev, exit_debt=debt, exit_equity=equity,
                  sponsor_flows=flows, sponsor_moic=multiple(flows), sponsor_irr=block_irr(flows),
                  lender_flows=lender, decomposition=decomposition,
                  sponsor_cash_gain=sum(flows))
    return result


def first_round(founders, team, pre, cash, pool_fraction):
    founders, team, pre, cash, p = map(q, (founders, team, pre, cash, pool_fraction))
    require(founders > 0 and team >= 0 and pre > 0 and cash > 0 and 0 <= p < 1,
            "Invalid round-one inputs")
    growth = 1 + cash / pre
    require(p * growth < 1, "Pool target leaves no feasible positive pre-round ownership")
    old = founders + team
    pool = p * growth * old / (1 - p * growth)
    price = pre / (old + pool)
    shares = {"founders": founders, "team": team, "pool": pool, "A": cash / price}
    total = sum(shares.values())
    return {"pool_added": pool, "price": price, "shares": shares, "total": total,
            "fractions": {key: value / total for key, value in shares.items()},
            "headline_post_money": pre + cash}


def next_round(first, pre, cash):
    pre, cash = q(pre), q(cash)
    require(pre > 0 and cash > 0, "Next-round pre-money and cash must be positive")
    price = pre / first["total"]
    shares = dict(first["shares"], B=cash / price)
    total = sum(shares.values())
    return {"price": price, "shares": shares, "total": total,
            "fractions": {key: value / total for key, value in shares.items()},
            "headline_post_money": pre + cash}


def strategy_payoff(exit_cash, convert_a, convert_b):
    """Saffron only: 4,000 junior A; 6,000 senior B; common/A/B weights 64/16/20."""
    exit_cash = q(exit_cash)
    require(exit_cash >= 0, "Equity exit cash cannot be negative")
    remaining = exit_cash
    paid = {"A": F(0), "B": F(0), "common": F(0)}
    for name, converted, preference in [("B", convert_b, F(6000)), ("A", convert_a, F(4000))]:
        if not converted:
            paid[name] = min(preference, remaining)
            remaining -= paid[name]
    denominator = 64 + 16 * convert_a + 20 * convert_b
    paid["common"] = remaining * 64 / denominator
    if convert_a:
        paid["A"] = remaining * 16 / denominator
    if convert_b:
        paid["B"] = remaining * 20 / denominator
    return paid


def joint_waterfall(exit_cash):
    # Each preferred class chooses its own single conversion action; no side payments.
    profiles = list(product((False, True), repeat=2))
    payoffs = {profile: strategy_payoff(exit_cash, *profile) for profile in profiles}
    stable = []
    for a, b in profiles:
        own = payoffs[a, b]
        if own["A"] >= payoffs[not a, b]["A"] and own["B"] >= payoffs[a, not b]["B"]:
            stable.append((a, b))
    require(stable, "No pure conversion profile in this contract")
    paid = payoffs[stable[0]]
    require(all(payoffs[p] == paid for p in stable), "Conversion profiles have different payoffs")
    return {"exit_cash": q(exit_cash), "payoffs": paid,
            "common_split": {"founders": paid["common"] * F(42, 64),
                             "team": paid["common"] * F(14, 64),
                             "pool": paid["common"] * F(8, 64)},
            "stable_conversions": [{"A": a, "B": b} for a, b in stable]}


def single_preferred(exit_cash, preference, share, cap):
    x, p, s, k = map(q, (exit_cash, preference, share, cap))
    require(x >= 0 and p >= 0 and 0 < s < 1 and k >= 1, "Invalid single-class contract")
    participating = min(p, x) + s * max(x - p, 0)
    return {"nonparticipating": max(min(p, x), s * x), "participating": participating,
            "capped_with_conversion": max(s * x, min(k * p, participating))}


def fund(data):
    calls, fees, gross = (vector(data[key]) for key in ("calls", "fees", "gross_distributions"))
    require(len(calls) == len(fees) == len(gross) == 4, "Fund requires four annual dates")
    commitment, carry = q(data["commitment"]), q(data["carry_fraction"])
    require(0 <= carry < 1 and all(c >= f >= 0 for c, f in zip(calls, fees))
            and all(g >= 0 for g in gross), "Invalid fund fees, calls, distributions or carry")
    require(commitment >= sum(calls) > 0, "Calls must be positive and within commitment")
    require(max(t for t, c in enumerate(calls) if c > 0)
            < min((t for t, g in enumerate(gross) if g > 0), default=-1),
            "Fund domain requires all calls before any distribution")
    investments = [c - f for c, f in zip(calls, fees)]
    capital = F(0)
    rows, lpflows, grossflows = [], [], []
    for t, (call, fee, receipt, investment) in enumerate(zip(calls, fees, gross, investments)):
        capital += call
        returned = min(capital, receipt)
        capital -= returned
        profit = receipt - returned
        carry_paid = carry * profit
        lp = receipt - carry_paid
        lpflows.append(lp - call)
        grossflows.append(receipt - investment)
        rows.append({"date": t, "lp_call": call, "investment": investment, "fee": fee,
                     "gross_receipt": receipt, "lp_capital_return": returned,
                     "lp_profit": profit - carry_paid, "carry_paid": carry_paid,
                     "lp_distribution": lp, "unreturned_lp_capital": capital})
    t = data["interim_date"]
    require(t == 2, "Lab's interim mark is after the date-2 distribution")
    mark = q(data["interim_gross_net_disposal_mark"])
    require(mark >= 0, "Interim mark must be nonnegative")
    capital_at_mark = rows[t]["unreturned_lp_capital"]
    accrued_carry = carry * max(mark - capital_at_mark, 0)
    lpnav = mark - accrued_carry
    interim_paid = sum(calls[:t + 1])
    require(interim_paid > 0, "Interim ratios need paid-in capital")
    interim_dist = sum(row["lp_distribution"] for row in rows[:t + 1])
    return {"annual": rows, "gross_flows": grossflows, "lp_flows": lpflows,
            "gross_moic": multiple(grossflows), "gross_irr": block_irr(grossflows),
            "net_moic": multiple(lpflows), "net_irr": block_irr(lpflows),
            "fees_paid": sum(fees), "carry_paid": sum(row["carry_paid"] for row in rows),
            "unused_commitment_released": commitment - sum(calls),
            "final_net_dpi": multiple(lpflows), "final_net_rvpi": F(0),
            "final_net_tvpi": multiple(lpflows),
            "interim": {"date": t, "gross_mark": mark, "carry_accrual": accrued_carry,
                        "lp_nav": lpnav, "net_dpi": interim_dist / interim_paid,
                        "net_rvpi": lpnav / interim_paid,
                        "net_tvpi": (interim_dist + lpnav) / interim_paid}}


def run(data):
    a = data["venture"]
    first = first_round(a["founder_shares"], a["team_shares"], a["a_pre_money"],
                        a["a_cash"], a["pool_post_a_fraction"])
    second = next_round(first, a["b_pre_money"], a["b_cash"])
    # Waterfall is deliberately tied to the base-case contract, not arbitrary cap tables.
    require(second["fractions"] == {"founders": F(21, 50), "team": F(7, 50),
                                     "pool": F(2, 25), "A": F(4, 25), "B": F(1, 5)}
            and q(a["a_cash"]) == 4000 and q(a["b_cash"]) == 6000,
            "run() waterfall requires the stated Saffron preferred contract")
    return {"chapter": "v08-c10", "units": "kCU; venture shares in thousands; share prices in CU",
            "lbo": buyout(data["lbo"]), "round_a": first, "round_b": second,
            "waterfalls": [joint_waterfall(x) for x in a["exits"]], "fund": fund(data["fund"])}


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("v08-c10-inputs.json")
    print(json.dumps(wire(run(json.loads(path.read_text()))), indent=2, allow_nan=False))
