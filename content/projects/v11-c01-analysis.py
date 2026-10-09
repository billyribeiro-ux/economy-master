"""Exact finite teaching cases for v11-c01; Python standard library only.

Import and run(data) are quiet. Financial failure is an output where modeled;
malformed data and unsupported contracts raise ValueError under normal and -O.
No floating-point input, simulation, market quotes, or regulatory ratios.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re


_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+|/[1-9][0-9]*)?\Z")
_MAX_BYTES = 65536


def _object(value, keys, name):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(name + ": exact object keys required")


def _q(value, name, low=0, high=1000000):
    if type(value) is not str or len(value) > 32 or not _NUMBER.fullmatch(value):
        raise ValueError(name + ": bounded decimal or fraction string required")
    q = Fraction(value)
    if abs(q.numerator) > 10**9 or q.denominator > 10**9 or not low <= q <= high:
        raise ValueError(name + ": value or rational complexity out of bounds")
    return q


def _values(value, keys, name, high=1000000):
    _object(value, keys, name)
    return {key: _q(value[key], name + "." + key, high=high) for key in keys}


def _wire(value):
    if isinstance(value, Fraction) or type(value) is int:
        return str(value)
    if isinstance(value, dict):
        return {key: _wire(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_wire(item) for item in value]
    return value


def _ratio(a, b):
    return a / b if b > 0 else None


def _screening(data):
    keys = ("good_prior", "good_success", "bad_success", "good_pass", "bad_pass",
            "principal", "success_repayment", "failure_recovery", "test_cost")
    x = _values(data, keys, "screening", high=1000)
    for key in keys[:5]:
        if not 0 <= x[key] <= 1:
            raise ValueError("screening: probabilities must lie in [0,1]")
    if not 0 < x["principal"] or not x["failure_recovery"] < x["success_repayment"]:
        raise ValueError("screening: positive principal and recovery below repayment required")
    prior = x["good_prior"]
    pooled_p = prior*x["good_success"] + (1-prior)*x["bad_success"]
    loss, face, principal = x["failure_recovery"], x["success_repayment"], x["principal"]
    pooled_receipt = loss + (face-loss)*pooled_p
    branches = []
    gross_value = Fraction(0)
    funded_mass = Fraction(0)
    for label, g, b in (("pass", x["good_pass"], x["bad_pass"]),
                         ("fail", 1-x["good_pass"], 1-x["bad_pass"])):
        joint_good, joint_bad = prior*g, (1-prior)*b
        mass = joint_good + joint_bad
        if mass == 0:
            branches.append({"signal": label, "mass": mass, "good_posterior": None,
                             "success_probability": None, "expected_receipt": None,
                             "loan_margin": None, "fund": False})
            continue
        p = (joint_good*x["good_success"] + joint_bad*x["bad_success"])/mass
        receipt = loss + (face-loss)*p
        margin = receipt-principal
        fund = margin > 0  # Indifference is resolved by not lending.
        gross_value += mass*max(margin, 0)
        funded_mass += mass if fund else 0
        branches.append({"signal": label, "mass": mass, "good_posterior": joint_good/mass,
                         "success_probability": p, "expected_receipt": receipt,
                         "loan_margin": margin, "fund": fund})
    no_test = max(pooled_receipt-principal, 0)
    net_test = gross_value-x["test_cost"]
    return {"funding_threshold_probability": (principal-loss)/(face-loss),
            "pooled_success": pooled_p, "pooled_receipt": pooled_receipt,
            "pooled_loan_margin": pooled_receipt-principal, "branches": branches,
            "funded_mass_if_tested": funded_mass, "gross_test_policy_value": gross_value,
            "no_test_policy_value": no_test, "gross_information_value": gross_value-no_test,
            "net_test_policy_value": net_test, "optimal_value": max(no_test, net_test),
            "choose_test": net_test > no_test,
            "maximum_test_cost_against_no_test": gross_value-no_test}


def _monitoring(data):
    keys = ("principal", "success_cash", "debt", "prudent_success", "divert_success",
            "private_benefit", "audit_cost", "delegation_cost", "claimants")
    _object(data, keys, "monitoring")
    n = data["claimants"]
    if type(n) is not int or not 1 <= n <= 1000:
        raise ValueError("monitoring.claimants: integer in [1,1000] required")
    x = {k: _q(data[k], "monitoring."+k, high=1000) for k in keys if k != "claimants"}
    if not 0 < x["principal"] or not 0 <= x["debt"] < x["success_cash"]:
        raise ValueError("monitoring: positive principal and residual success cash required")
    if not 0 <= x["divert_success"] < x["prudent_success"] <= 1:
        raise ValueError("monitoring: ordered success probabilities required")
    residual = x["success_cash"]-x["debt"]
    prudent = x["prudent_success"]*residual
    divert = x["divert_success"]*residual+x["private_benefit"]
    unmonitored_action = "prudent" if prudent >= divert else "divert"
    pu = x["prudent_success"] if unmonitored_action == "prudent" else x["divert_success"]
    old_receipt, new_receipt = pu*x["debt"], x["prudent_success"]*x["debt"]
    gain = new_receipt-old_receipt
    expense = x["principal"]+x["audit_cost"]+x["delegation_cost"]
    return {"borrower_prudent_payoff": prudent, "borrower_divert_payoff": divert,
            "unmonitored_action": unmonitored_action,
            "borrower_divert_payoff_after_enforcement": x["divert_success"]*residual,
            "unmonitored_receipt": old_receipt, "monitored_receipt": new_receipt,
            "aggregate_audit_gain": gain, "one_claimant_audit_gain": gain/n,
            "no_audit_is_nash_given_loan": gain/n <= x["audit_cost"],
            "no_audit_is_strict_given_loan": gain/n < x["audit_cost"],
            "pooled_initial_funding": expense, "pooled_expected_surplus": new_receipt-expense,
            "pooled_funding_is_profitable": new_receipt > expense,
            "unmonitored_expected_surplus": old_receipt-x["principal"],
            "all_duplicate_expected_surplus": new_receipt-x["principal"]-n*x["audit_cost"],
            "largest_delegation_cost_for_nonnegative_surplus": new_receipt-x["principal"]-x["audit_cost"],
            "private_benefit_indifference": (x["prudent_success"]-x["divert_success"])*residual}


def _bank(data):
    keys = ("a_reserves", "a_loans", "a_deposits", "b_reserves", "b_loans", "b_deposits",
            "new_loan", "external_payment", "immediate_withdrawal_probe", "interest_received",
            "fees_received", "interest_paid", "operating_cash_cost", "direct_unprovided_loss")
    x = _values(data, keys, "bank")
    a = [x["a_reserves"], x["a_loans"], x["a_deposits"]]
    b = [x["b_reserves"], x["b_loans"], x["b_deposits"]]
    if any(z[0]+z[1] <= z[2] for z in (a,b)):
        raise ValueError("bank: each initial bank must have positive book equity")
    payment, loan = x["external_payment"], x["new_loan"]
    if payment > min(a[0],loan):
        raise ValueError("bank: payment cannot exceed available reserves or new borrower deposit")

    def snap(v):
        reserve, loans, deposit = v
        assets = reserve+loans
        equity = assets-deposit
        return {"reserves": reserve, "loans": loans, "assets": assets, "deposits": deposit,
                "equity": equity, "equity_assets": _ratio(equity, assets)}

    def both(label):
        return {"event": label, "A": snap(a), "B": snap(b),
                "consolidated": snap([a[i]+b[i] for i in range(3)])}

    ledger = [both("initial")]
    a[1] += loan
    a[2] += loan
    ledger.append(both("loan_credits_A_deposit"))
    a[0] -= payment
    a[2] -= payment
    b[0] += payment
    b[2] += payment
    ledger.append(both("external_settlement_to_B"))
    probe = x["immediate_withdrawal_probe"]
    if probe > a[2]:
        raise ValueError("bank: withdrawal probe cannot exceed outstanding A deposits")
    cash_gap = max(probe-a[0],0)
    opening = snap(a)
    if (opening["loans"] == 0 and x["interest_received"] != 0) or (opening["deposits"] == 0 and x["interest_paid"] != 0):
        raise ValueError("bank: interest requires a corresponding opening loan or deposit balance")
    loss = x["direct_unprovided_loss"]
    if loss > a[1]:
        raise ValueError("bank: uncovered direct loss cannot exceed recorded loans")
    cash_net = x["interest_received"]+x["fees_received"]-x["interest_paid"]-x["operating_cash_cost"]
    if a[0]+cash_net < 0:
        raise ValueError("bank: later payments require an unmodeled funding facility")
    income_ledger = [{"event": "opening_after_settlement", **opening}]
    for event, amount in (("external_loan_interest", x["interest_received"]),
                          ("external_fee_receipt", x["fees_received"]),
                          ("external_interest_payment", -x["interest_paid"]),
                          ("external_operating_payment", -x["operating_cash_cost"])):
        a[0] += amount
        income_ledger.append({"event": event, **snap(a)})
    a[1] -= loss
    closing = snap(a)
    income_ledger.append({"event": "confirmed_loss_without_prior_allowance", **closing})
    profit = cash_net-loss
    net_interest = x["interest_received"]-x["interest_paid"]
    mean_loans = (opening["loans"]+closing["loans"])/2
    mean_assets = (opening["assets"]+closing["assets"])/2
    mean_equity = (opening["equity"]+closing["equity"])/2
    return {"two_bank_ledger": ledger,
            "immediate_probe_before_income": {"requested": probe, "cash_available": opening["reserves"],
                                              "cash_gap": cash_gap, "executable": cash_gap == 0,
                                              "book_equity": opening["equity"]},
            "A_later_income_ledger": income_ledger,
            "net_interest_income": net_interest, "net_external_cash_receipts": cash_net,
            "direct_loss_without_prior_allowance": loss, "profit": profit,
            "average_earning_loans": mean_loans, "average_assets": mean_assets,
            "average_equity": mean_equity, "net_interest_margin": _ratio(net_interest,mean_loans),
            "return_on_assets": _ratio(profit,mean_assets), "return_on_equity": _ratio(profit,mean_equity),
            "gross_loan_yield": _ratio(x["interest_received"],mean_loans),
            "deposit_funding_rate": _ratio(x["interest_paid"],opening["deposits"]),
            "closing_book_insolvent": closing["equity"] < 0}


def _liquidity(data):
    keys = ("initial_fund", "early_fraction", "liquidation_return", "maturity_return", "early_claim",
            "utility_shift", "withdrawal_fractions")
    _object(data, keys, "liquidity")
    x = {k: _q(data[k], "liquidity."+k) for k in keys if k != "withdrawal_fractions"}
    fund, lam, ell, mature, c, shift = (x[k] for k in keys[:-1])
    if not 0 < fund <= 1000000 or not Fraction(1,100) <= lam <= Fraction(99,100):
        raise ValueError("liquidity: positive bounded fund and interior early fraction required")
    if not Fraction(1,10) <= ell <= 1 or not 1 < mature <= 3 or not ell < c < mature:
        raise ValueError("liquidity: 0.1<=liquidation<=1<maturity<=3 and liquidation<claim<maturity required")
    if not Fraction(1,1000) <= shift <= 1:
        raise ValueError("liquidity: utility shift must lie in [0.001,1]")
    fractions = data["withdrawal_fractions"]
    if type(fractions) is not list or not 1 <= len(fractions) <= 16:
        raise ValueError("liquidity: one to sixteen withdrawal fractions required")
    ws = [_q(v,"liquidity.withdrawal_fractions",low=lam,high=1) for v in fractions]
    if any(ws[i] >= ws[i+1] for i in range(len(ws)-1)):
        raise ValueError("liquidity: withdrawal fractions must be strictly increasing")

    def u(z):
        return -1/(z+shift)

    def row(w):
        claimant_mass = fund*w
        served_mass = min(claimant_mass, fund*ell/c)
        served_probability = served_mass/claimant_mass
        cash = served_mass*c
        liquidated = cash/ell
        held = fund-liquidated
        wait_mass = fund*(1-w)
        wait_cash = mature*held/wait_mass if wait_mass else None
        return {"withdrawal_fraction": w, "claimant_mass": claimant_mass, "served_mass": served_mass,
                "served_probability": served_probability, "date1_cash_paid": cash,
                "long_asset_liquidated": liquidated, "long_asset_held": held,
                "date2_cash_available": mature*held, "waiter_mass": wait_mass,
                "cash_per_waiter": wait_cash, "expected_cash_per_withdrawer": served_probability*c,
                "expected_utility_per_withdrawer": served_probability*u(c)+(1-served_probability)*u(Fraction(0))}

    normal = row(lam)
    normal_eu = lam*normal["expected_utility_per_withdrawer"]+(1-lam)*u(normal["cash_per_waiter"])
    direct = lam*u(ell)+(1-lam)*u(mature)
    full_run = row(Fraction(1))
    return {"candidate_no_run": normal, "full_run": full_run, "scenarios": [row(w) for w in ws],
            "withdrawal_capacity_fraction": ell/c,
            "late_indifference_withdrawal_fraction": (mature-c)/(c*(mature/ell-1)),
            "candidate_no_run_fully_pays_early": lam*c <= ell,
            "candidate_no_run_incentive_compatible": lam*c <= ell and normal["cash_per_waiter"] >= c,
            "candidate_no_run_expected_utility": normal_eu, "direct_all_long_expected_utility": direct,
            "candidate_utility_gain_over_all_long": normal_eu-direct,
            "full_run_wait_deviation_consumption": Fraction(0),
            "full_run_wait_deviation_utility": u(Fraction(0)),
            "full_run_withdrawal_is_strict_best_reply": full_run["expected_utility_per_withdrawer"] > u(Fraction(0))}


def run(data):
    """Return exact rational-string results without modifying input or doing I/O."""
    _object(data, ("schema","screening","monitoring","bank","liquidity"), "root")
    if type(data["schema"]) is not str or data["schema"] != "v11-c01-inputs-1":
        raise ValueError("unsupported schema")
    result = {"schema": "v11-c01-output-1", "screening": _screening(data["screening"]),
              "monitoring": _monitoring(data["monitoring"]), "bank": _bank(data["bank"]),
              "liquidity": _liquidity(data["liquidity"])}
    return _wire(result)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonfinite JSON token: " + value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=here/"v11-c01-inputs.json")
    parser.add_argument("--output", type=Path, default=here/"v11-c01-output.json")
    args = parser.parse_args(argv)
    try:
        resolved_output = args.output.resolve()
        for protected in (args.input, Path(__file__)):
            if resolved_output == protected.resolve() or (args.output.exists() and protected.exists() and args.output.samefile(protected)):
                raise ValueError("output must not overwrite the input or implementation")
        with args.input.open("rb") as stream:
            raw = stream.read(_MAX_BYTES+1)
        if len(raw) > _MAX_BYTES:
            raise ValueError("input exceeds 65536 bytes")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
        result = run(data)
        payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+"\n"
        args.output.write_text(payload, encoding="utf-8")
    except (ValueError, TypeError, RuntimeError, OSError) as exc:
        parser.exit(2, "v11-c01: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
