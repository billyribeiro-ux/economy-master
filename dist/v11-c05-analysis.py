"""Original, bounded four-cutoff funding ledger; standard library only.

run(data) is quiet, deterministic and nonmutating. Monetary/rate inputs are
bounded rational strings. All arithmetic, including ALM values, is exact.
Financial infeasibility is an output, not a malformed-input exception.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re
import sys

LIMIT = Fraction(10**6)
RATIONAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+|/[1-9][0-9]*)?\Z")


def _keys(value, expected, where):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(where + ": exact object keys required")


def _q(value, where, lo=Fraction(0), hi=LIMIT):
    if type(value) is not str or len(value) > 32 or not RATIONAL.fullmatch(value):
        raise ValueError(where + ": bounded rational string required")
    x = Fraction(value)
    if abs(x.numerator) > 10**12 or x.denominator > 10**12 or not lo <= x <= hi:
        raise ValueError(where + ": outside the declared finite domain")
    return x


def _integer(value, where, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(where + ": bounded integer required")
    return value


def _vector(value, where, signed=False):
    if type(value) is not list or len(value) != 4:
        raise ValueError(where + ": exactly four cutoffs required")
    return [_q(v, where, -LIMIT if signed else Fraction(0)) for v in value]


def _validated(data):
    _keys(data, ("schema_version", "opening", "policy", "scenarios", "alm", "currency_case"), "root")
    _integer(data["schema_version"], "schema_version", 1, 1)
    opening_keys = ("cash", "restricted_cash", "loans", "security_book_per_unit", "eligible_units", "already_pledged_units", "inaccessible_units", "initial_margin", "deposits", "legacy_principal", "legacy_interest_payable", "other_liabilities")
    _keys(data["opening"], opening_keys, "opening")
    o = {k: _q(data["opening"][k], "opening." + k) for k in opening_keys}
    if o["restricted_cash"] > o["cash"]:
        raise ValueError("restricted cash exceeds cash")
    if o["security_book_per_unit"] > 10:
        raise ValueError("book amount per security unit exceeds 10")
    units = o["eligible_units"] + o["already_pledged_units"] + o["inaccessible_units"]
    if units > LIMIT:
        raise ValueError("total security units exceed bound")
    equity = o["cash"] + o["loans"] + units * o["security_book_per_unit"] + o["initial_margin"] - o["deposits"] - o["legacy_principal"] - o["legacy_interest_payable"] - o["other_liabilities"]
    if equity < 0:
        raise ValueError("opening book equity must be nonnegative in this lab family")
    policy_keys = ("upfront_cash_equity", "secured_target", "initial_security_price", "initial_haircut", "secured_interval_rate", "rollover_interval_rate", "customer_line_limit")
    _keys(data["policy"], policy_keys, "policy")
    p = {k: _q(data["policy"][k], "policy." + k) for k in policy_keys}
    if not Fraction(1, 100) <= p["initial_security_price"] <= 10:
        raise ValueError("initial security price must be in [0.01,10]")
    if p["initial_haircut"] > Fraction(19, 20):
        raise ValueError("initial haircut must be in [0,0.95]")
    for k in ("secured_interval_rate", "rollover_interval_rate"):
        if p[k] > Fraction(1, 10):
            raise ValueError("interval rate must be in [0,0.1]")
    raw = data["scenarios"]
    if type(raw) is not list or not 1 <= len(raw) <= 8:
        raise ValueError("one to eight scenarios required")
    scenario_keys = ("name", "rollover_fraction", "secured_offer_fraction", "maintenance_price", "maintenance_haircut", "loan_principal_receipts", "deposit_withdrawals", "other_liability_payments", "customer_line_draw", "variation_settlements", "initial_margin_targets")
    scenarios, names = [], set()
    for s in raw:
        _keys(s, scenario_keys, "scenario")
        name = s["name"]
        if type(name) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name) or name in names:
            raise ValueError("scenario names must be unique bounded lowercase identifiers")
        names.add(name)
        z = {"name": name}
        for k in ("rollover_fraction", "secured_offer_fraction"):
            z[k] = _q(s[k], k, Fraction(0), Fraction(1))
        z["maintenance_price"] = _q(s["maintenance_price"], "maintenance_price", Fraction(1, 100), Fraction(10))
        z["maintenance_haircut"] = _q(s["maintenance_haircut"], "maintenance_haircut", Fraction(0), Fraction(19, 20))
        z["customer_line_draw"] = _q(s["customer_line_draw"], "customer_line_draw", Fraction(0), p["customer_line_limit"])
        for k in ("loan_principal_receipts", "deposit_withdrawals", "other_liability_payments", "variation_settlements", "initial_margin_targets"):
            z[k] = _vector(s[k], k, k == "variation_settlements")
        for k, balance in (("loan_principal_receipts", o["loans"]), ("deposit_withdrawals", o["deposits"]), ("other_liability_payments", o["other_liabilities"])):
            if sum(z[k]) > balance:
                raise ValueError(k + ": payments exceed opening stock")
        if z["initial_margin_targets"][-1] != 0:
            raise ValueError("initial margin must be released at final closeout")
        scenarios.append(z)
    alm_keys = ("asset_face", "asset_coupon_rate", "asset_years", "fixed_liability_face", "fixed_liability_coupon_rate", "liability_years", "floating_liability_face", "cash", "base_yield", "shock_yield")
    _keys(data["alm"], alm_keys, "alm")
    a = {}
    for k in alm_keys:
        if k.endswith("years"):
            a[k] = _integer(data["alm"][k], k, 1, 10)
        elif k.endswith("yield"):
            a[k] = _q(data["alm"][k], k, Fraction(-1, 10), Fraction(1, 4))
        elif k.endswith("rate"):
            a[k] = _q(data["alm"][k], k, Fraction(0), Fraction(1, 5))
        else:
            a[k] = _q(data["alm"][k], k)
    fx_keys = ("local_cash", "payment_due", "foreign_cash", "cu_per_fu")
    _keys(data["currency_case"], fx_keys, "currency_case")
    fx = {k: _q(data["currency_case"][k], k) for k in fx_keys}
    if not Fraction(1, 100) <= fx["cu_per_fu"] <= 100:
        raise ValueError("CU per FU must be in [0.01,100]")
    return o, p, scenarios, a, fx, equity


def _serial(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {k: _serial(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serial(v) for v in value]
    return value


def _balance(state):
    assets = sum(state[k] for k in ("cash", "loans", "securities_book", "initial_margin"))
    liabilities = sum(state[k] for k in ("deposits", "legacy_principal", "legacy_interest_payable", "other_liabilities", "rollover_principal", "secured_principal", "new_interest_payable"))
    return assets, liabilities, assets - liabilities - state["equity"]


def _scenario(o, p, s, opening_equity):
    total_units = o["eligible_units"] + o["already_pledged_units"] + o["inaccessible_units"]
    state = {k: o[k] for k in ("cash", "loans", "initial_margin", "deposits", "legacy_principal", "legacy_interest_payable", "other_liabilities")}
    state.update(securities_book=total_units * o["security_book_per_unit"], rollover_principal=Fraction(0), secured_principal=Fraction(0), new_interest_payable=Fraction(0), equity=opening_equity)
    journal, rows = [], []

    def post(cutoff, label, changes):
        for k, v in changes.items():
            state[k] += v
        assets, liabilities, error = _balance(state)
        if error != 0:
            raise ArithmeticError("internal book conservation failure")
        journal.append({"cutoff": cutoff, "event": label, "changes": changes, "cash_flow": changes.get("cash", Fraction(0)), "equity_change": changes.get("equity", Fraction(0)), "assets_after": assets, "liabilities_after": liabilities, "equity_after": state["equity"], "balance_error": error})

    buffer = p["upfront_cash_equity"]
    post(0, "upfront_cash_equity", {"cash": buffer, "equity": buffer})
    advance0 = p["initial_security_price"] * (1 - p["initial_haircut"])
    advance2 = s["maintenance_price"] * (1 - s["maintenance_haircut"])
    initial_capacity = o["eligible_units"] * advance0
    draw = min(p["secured_target"], initial_capacity) * s["secured_offer_fraction"]
    maintenance_capacity = o["eligible_units"] * advance2
    maintained_principal = min(draw, maintenance_capacity)
    paydown = draw - maintained_principal
    rollover = o["legacy_principal"] * s["rollover_fraction"]
    secured_interest_total = p["secured_interval_rate"] * (draw + 2 * maintained_principal)
    rollover_interest_total = 3 * p["rollover_interval_rate"] * rollover
    for j in range(1, 5):
        events = []
        def add(label, **changes):
            events.append((label, changes))
        if j > 1:
            secured_opening = draw if j == 2 else maintained_principal
            interest = p["secured_interval_rate"] * secured_opening + p["rollover_interval_rate"] * rollover
            post(j, "funding_interest_accrual", {"new_interest_payable": interest, "equity": -interest})
        if j == 1:
            add("secured_draw", cash=draw, secured_principal=draw)
            add("new_rollover_draw", cash=rollover, rollover_principal=rollover)
            add("legacy_principal_repayment", cash=-o["legacy_principal"], legacy_principal=-o["legacy_principal"])
            add("legacy_accrued_interest_payment", cash=-o["legacy_interest_payable"], legacy_interest_payable=-o["legacy_interest_payable"])
        repayment = s["loan_principal_receipts"][j - 1]
        add("loan_principal_receipt", cash=repayment, loans=-repayment)
        withdrawal = s["deposit_withdrawals"][j - 1]
        add("deposit_withdrawal", cash=-withdrawal, deposits=-withdrawal)
        other = s["other_liability_payments"][j - 1]
        add("other_liability_payment", cash=-other, other_liabilities=-other)
        vm = s["variation_settlements"][j - 1]
        add("variation_settlement", cash=vm, equity=vm)
        im_change = s["initial_margin_targets"][j - 1] - state["initial_margin"]
        add("initial_margin_transfer", cash=-im_change, initial_margin=im_change)
        if j == 2:
            add("customer_line_advance", cash=-s["customer_line_draw"], loans=s["customer_line_draw"])
            add("collateral_principal_paydown", cash=-paydown, secured_principal=-paydown)
        if j == 4:
            add("secured_maturity_repayment", cash=-maintained_principal, secured_principal=-maintained_principal)
            add("rollover_maturity_repayment", cash=-rollover, rollover_principal=-rollover)
            add("funding_interest_payment", cash=-state["new_interest_payable"], new_interest_payable=-state["new_interest_payable"])
        # Contract: all listed external receipts at a cutoff precede payments.
        # No payment-dependent receipt, unpledged-sale or collateral recycling.
        events.sort(key=lambda item: item[1].get("cash", Fraction(0)) < 0)
        for label, changes in events:
            post(j, label, changes)
        pledged = draw / advance0 if j == 1 else (maintained_principal / advance2 if j < 4 else Fraction(0))
        price = p["initial_security_price"] if j == 1 else s["maintenance_price"]
        assets, liabilities, error = _balance(state)
        usable = state["cash"] - o["restricted_cash"]
        rows.append({"cutoff": j, "available_cash": usable, "available_cash_without_buffer": usable - buffer, "cash_gap": max(Fraction(0), -usable), "state": dict(state), "total_assets": assets, "total_liabilities": liabilities, "balance_error": error, "marked_equity": state["equity"] + total_units * (price - o["security_book_per_unit"]), "new_pledged_units": pledged, "free_eligible_units": o["eligible_units"] - pledged, "already_pledged_units": o["already_pledged_units"], "inaccessible_units": o["inaccessible_units"]})
    required = max([Fraction(0)] + [-r["available_cash_without_buffer"] for r in rows])
    first_failure = next((r["cutoff"] for r in rows if r["available_cash"] < 0), None)
    return {"name": s["name"], "initial_secured_capacity": initial_capacity, "secured_draw": draw, "maintenance_capacity": maintenance_capacity, "collateral_principal_paydown": paydown, "rollover_draw": rollover, "secured_interest_total": secured_interest_total, "rollover_interest_total": rollover_interest_total, "required_upfront_cash": required, "additional_cash_needed": max(Fraction(0), required - buffer), "first_failure_cutoff": first_failure, "feasible_under_fixed_policy": first_failure is None, "rows": rows, "journal": journal}


def _bond(face, coupon_rate, years, y):
    flows = [face * coupon_rate] * years
    flows[-1] += face
    pv = sum(cf / (1 + y) ** t for t, cf in enumerate(flows, 1))
    slope = -sum(t * cf / (1 + y) ** (t + 1) for t, cf in enumerate(flows, 1))
    return pv, slope


def _alm(a):
    rows = []
    for label in ("base", "shock"):
        y = a[label + "_yield"]
        asset, da = _bond(a["asset_face"], a["asset_coupon_rate"], a["asset_years"], y)
        fixed, dl = _bond(a["fixed_liability_face"], a["fixed_liability_coupon_rate"], a["liability_years"], y)
        floating = sum(a["floating_liability_face"] * y / (1 + y) ** t for t in range(1, a["liability_years"] + 1)) + a["floating_liability_face"] / (1 + y) ** a["liability_years"]
        nii = a["asset_face"] * a["asset_coupon_rate"] - a["fixed_liability_face"] * a["fixed_liability_coupon_rate"] - a["floating_liability_face"] * y
        rows.append({"case": label, "yield": y, "asset_pv": asset, "fixed_liability_pv": fixed, "floating_liability_pv": floating, "economic_equity": a["cash"] + asset - fixed - floating, "next_year_interest_income_net": nii, "asset_yield_derivative": da, "fixed_liability_yield_derivative": dl, "economic_equity_yield_derivative": da - dl, "nii_yield_derivative": -a["floating_liability_face"]})
    return rows


def run(data):
    """Return an exact JSON-compatible report; reject malformed inputs explicitly."""
    o, p, scenarios, alm, fx, equity = _validated(data)
    results = [_scenario(o, p, s, equity) for s in scenarios]
    required = max(r["required_upfront_cash"] for r in results)
    binding = [{"scenario": r["name"], "cutoff": row["cutoff"]} for r in results for row in r["rows"] if -row["available_cash_without_buffer"] == required and required > 0]
    conversion = fx["foreign_cash"] * fx["cu_per_fu"]
    ordinary = fx["local_cash"] - fx["payment_due"]
    return _serial({"schema_version": 1, "units": "CU except security units, FU and rates explicitly named", "opening_book_equity": equity, "upfront_cash_equity": p["upfront_cash_equity"], "scenarios": results, "fixed_policy_certificate": {"required_upfront_cash": required, "additional_cash_needed": max(Fraction(0), required - p["upfront_cash_equity"]), "binding_cutoffs": binding, "all_scenarios_feasible": all(r["feasible_under_fixed_policy"] for r in results)}, "alm": _alm(alm), "currency_case": {"potential_converted_cu": conversion, "no_authorized_transfer_headroom": ordinary, "authorized_timely_transfer_headroom": ordinary + conversion, "authorized_late_transfer_headroom_at_deadline": ordinary, "authorized_late_transfer_headroom_after_receipt": ordinary + conversion}})


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def _protect_output(output_path, input_path):
    for protected in (input_path, Path(__file__)):
        if output_path.resolve() == protected.resolve():
            raise ValueError("output cannot overwrite input or implementation")
        if output_path.exists() and protected.exists() and output_path.samefile(protected):
            raise ValueError("output cannot alias input or implementation")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("v11-c05-inputs.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output is not None:
            _protect_output(args.output, args.input)
        if args.input.stat().st_size > 100000:
            raise ValueError("input file exceeds 100000 bytes")
        data = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=_unique_object, parse_constant=_bad_constant)
        output = json.dumps(run(data), indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is None:
            sys.stdout.write(output)
        else:
            args.output.write_text(output, encoding="utf-8")
    except (ValueError, OSError, TypeError, ArithmeticError, RecursionError) as exc:
        parser.exit(2, "v11-c05: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
