"""Original bounded duration and immunization laboratory; standard library only.

Fixed cash flows, a precisely named yield coordinate, a flat baseline and a
declared continuous-zero interpolation basis. None of these shocks is assigned
a physical or pricing probability. Import and run(data) are quiet. Executing
the file writes strict JSON to stdout or the specified --output file.
"""
import argparse
import json
import math
from pathlib import Path


CONTRACT = "deterministic fixed cash flows; fixed settlement; no tax, credit loss, option or fee except named interventions"
CURVE_CONTRACT = "piecewise-linear continuous zero rates; no extrapolation; baseline flat at log(1+base_annual_yield)"
COUNTER_CONTRACT = "S(d)=scale*d*(d-1)^2*(cutoff-d), d=1/(1+y); baseline annual yield is zero"


def keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{name}: exact fields required: {', '.join(expected)}")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: a finite number is required")
    return float(value)


def vector(value, name, minimum=1):
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(f"{name}: a nonempty list is required")
    return [number(x, f"{name}[{i}]") for i, x in enumerate(value)]


def strictly_increasing(values, name):
    if not all(0 < t <= 50 for t in values) or any(a >= b for a, b in zip(values, values[1:])):
        raise ValueError(f"{name}: strictly increasing positive years, no later than 50")


def finite(value):
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    if isinstance(value, list):
        return all(finite(v) for v in value)
    return not isinstance(value, float) or math.isfinite(value)


def yield_metrics(times, cash, nominal_yield, frequency=1):
    """Derivatives with respect to decimal nominal annual y, not y/frequency."""
    q = 1 + nominal_yield / frequency
    if q <= 0:
        raise ValueError("Nonpositive periodic gross discount factor")
    pv = [c / q ** (frequency * t) for t, c in zip(times, cash)]
    price = sum(pv)
    dollar_duration = sum(t * v / q for t, v in zip(times, pv))
    dollar_convexity = sum(t * (t + 1 / frequency) * v / q ** 2 for t, v in zip(times, pv))
    return {"price": price, "cash_flow_pvs": pv,
            "macaulay_years": sum(t * v for t, v in zip(times, pv)) / price,
            "modified_duration": dollar_duration / price,
            "convexity": dollar_convexity / price,
            "dollar_duration": dollar_duration, "dollar_convexity": dollar_convexity,
            "dv01_positive_loss_for_upward_bp": dollar_duration * 0.0001}


def note_analysis(data):
    keys(data, ["times_years", "cash_flows", "frequency", "nominal_annual_yield",
                "accrued_interest", "yield_shifts", "finite_difference_step"], "note")
    times, cash = vector(data["times_years"], "note times"), vector(data["cash_flows"], "note cash")
    strictly_increasing(times, "note times")
    if len(times) != len(cash) or any(c < 0 for c in cash) or not any(c > 0 for c in cash):
        raise ValueError("Note needs aligned nonnegative cash flows, at least one positive")
    frequency = data["frequency"]
    if isinstance(frequency, bool) or not isinstance(frequency, int) or not 1 <= frequency <= 12:
        raise ValueError("Frequency must be an integer from 1 through 12")
    if any(abs(frequency * t - round(frequency * t)) > 1e-10 for t in times):
        raise ValueError("This note laboratory uses payment dates on the stated periodic grid")
    y = number(data["nominal_annual_yield"], "yield")
    ai = number(data["accrued_interest"], "accrued interest")
    shifts = vector(data["yield_shifts"], "yield shifts")
    step = number(data["finite_difference_step"], "finite-difference step")
    if step <= 0 or any(1 + (y + h) / frequency <= 0 for h in [0, -step, step] + shifts):
        raise ValueError("All base, shock and finite-difference periodic gross rates must be positive")
    metrics = yield_metrics(times, cash, y, frequency)
    if ai < 0 or ai >= metrics["price"]:
        raise ValueError("Illustrative accrued amount must be nonnegative and below dirty price")
    q = 1 + y / frequency
    scenarios = []
    for shift in shifts:
        actual = yield_metrics(times, cash, y + shift, frequency)["price"]
        linear = metrics["price"] - metrics["dollar_duration"] * shift
        quadratic = linear + metrics["dollar_convexity"] * shift ** 2 / 2
        q_min = min(q, 1 + (y + shift) / frequency)
        # |P'''| is maximized at the smallest q for these nonnegative cash flows.
        third_bound = sum(t * (t + 1 / frequency) * (t + 2 / frequency) * c /
                          q_min ** (frequency * t + 3) for t, c in zip(times, cash))
        scenarios.append({"yield_shift": shift, "exact_dirty_price": actual,
                          "linear_dirty_price": linear, "quadratic_dirty_price": quadratic,
                          "linear_error_estimate_minus_exact": linear - actual,
                          "quadratic_error_estimate_minus_exact": quadratic - actual,
                          "absolute_quadratic_remainder_bound": third_bound * abs(shift) ** 3 / 6})
    down = yield_metrics(times, cash, y - step, frequency)["price"]
    up = yield_metrics(times, cash, y + step, frequency)["price"]
    return {"coordinate": "decimal nominal annual yield, holding settlement and cash flows fixed",
            "frequency": frequency, "base_yield": y, "dirty": metrics,
            "accrued_interest_fixed": ai, "clean_price": metrics["price"] - ai,
            "clean_fractional_sensitivity": metrics["dollar_duration"] / (metrics["price"] - ai),
            "finite_difference": {"step": step,
                                  "duration": (down - up) / (2 * step * metrics["price"]),
                                  "convexity": (down - 2 * metrics["price"] + up) /
                                               (step ** 2 * metrics["price"])},
            "scenarios": scenarios}, times, cash


def immunization_analysis(data):
    keys(data, ["liability_time", "liability_amount", "asset_times", "base_annual_yield",
                "parallel_yield_shifts", "later_short_reinvestment_yield", "later_long_sale_yield",
                "entry_fee_rate", "changed_long_payoff_fraction"], "immunization")
    horizon = number(data["liability_time"], "liability time")
    amount = number(data["liability_amount"], "liability amount")
    times = vector(data["asset_times"], "asset times", 2)
    if len(times) != 2 or not 0 < times[0] < horizon < times[1] <= 50 or amount <= 0:
        raise ValueError("Positive liability must be strictly bracketed by exactly two positive maturities <=50")
    y = number(data["base_annual_yield"], "base annual yield")
    shifts = vector(data["parallel_yield_shifts"], "parallel shifts")
    reinvest = number(data["later_short_reinvestment_yield"], "later reinvestment yield")
    sell = number(data["later_long_sale_yield"], "later sale yield")
    fee = number(data["entry_fee_rate"], "entry fee")
    payoff_fraction = number(data["changed_long_payoff_fraction"], "changed payoff fraction")
    if min([1 + y, 1 + reinvest, 1 + sell] + [1 + y + h for h in shifts]) <= 0:
        raise ValueError("All annual effective gross rates must be positive")
    if not 0 <= fee < 1 or not 0 <= payoff_fraction <= 1:
        raise ValueError("Entry fee must lie in [0,1); changed payoff fraction in [0,1]")
    q = 1 + y
    liability_pv = amount / q ** horizon
    weights = [(times[1] - horizon) / (times[1] - times[0]),
               (horizon - times[0]) / (times[1] - times[0])]
    asset_values = [liability_pv * w for w in weights]
    faces = [v * q ** t for v, t in zip(asset_values, times)]
    assets = yield_metrics(times, faces, y)
    liability = yield_metrics([horizon], [amount], y)
    scenarios = []
    for shift in shifts:
        changed_q = q + shift
        asset_pv = sum(face / changed_q ** t for face, t in zip(faces, times))
        liability_now = amount / changed_q ** horizon
        early_accumulated = faces[0] * changed_q ** (horizon - times[0])
        late_sold = faces[1] / changed_q ** (times[1] - horizon)
        wealth = early_accumulated + late_sold
        scenarios.append({"annual_yield_shift": shift, "asset_pv": asset_pv,
                          "liability_pv": liability_now, "valuation_surplus": asset_pv - liability_now,
                          "early_cash_reinvested_to_horizon": early_accumulated,
                          "long_zero_sold_at_horizon": late_sold, "horizon_wealth": wealth,
                          "horizon_surplus": wealth - amount})
    altered_early = faces[0] * (1 + reinvest) ** (horizon - times[0])
    altered_late = faces[1] / (1 + sell) ** (times[1] - horizon)
    scaled = 1 / (1 + fee)
    changed_wealth = faces[0] * q ** (horizon - times[0]) + payoff_fraction * faces[1] / q ** (times[1] - horizon)
    result = {"initial_budget": liability_pv, "asset_pv_weights": weights,
              "asset_market_values": asset_values, "asset_zero_faces": faces,
              "asset_metrics": assets, "liability_metrics": liability,
              "initial_surplus": assets["price"] - liability["price"],
              "surplus_first_yield_derivative": -assets["dollar_duration"] + liability["dollar_duration"],
              "surplus_second_yield_derivative": assets["dollar_convexity"] - liability["dollar_convexity"],
              "single_shift_then_constant_rate_scenarios": scenarios,
              "later_path_intervention": {"early_reinvestment_yield": reinvest, "long_sale_yield": sell,
                                          "early_cash_at_horizon": altered_early, "long_sale_receipt": altered_late,
                                          "horizon_wealth": altered_early + altered_late,
                                          "horizon_surplus": altered_early + altered_late - amount},
              "entry_fee_intervention": {"fee_rate": fee,
                                         "extra_initial_cash_for_original_holdings": fee * liability_pv,
                                         "holdings_scale_on_unchanged_budget": scaled,
                                         "post_trade_security_value": scaled * liability_pv,
                                         "cash_fee_paid": fee * scaled * liability_pv,
                                         "base_horizon_wealth": scaled * amount,
                                         "base_horizon_funding_gap": amount - scaled * amount},
              "changed_cash_flow_intervention": {"long_payoff_fraction": payoff_fraction,
                                                 "base_horizon_wealth": changed_wealth,
                                                 "base_horizon_surplus": changed_wealth - amount}}
    return result, times, faces, horizon, amount, math.log1p(y)


def basis(time, key_times):
    if not key_times[0] <= time <= key_times[-1]:
        raise ValueError("Cash-flow date is outside the declared curve basis; no extrapolation")
    row = [0.0] * len(key_times)
    for j, key in enumerate(key_times):
        if time == key:
            row[j] = 1.0
            return row
    for j in range(len(key_times) - 1):
        lo, hi = key_times[j:j + 2]
        if lo < time < hi:
            row[j], row[j + 1] = (hi - time) / (hi - lo), (time - lo) / (hi - lo)
            return row
    raise ValueError("Could not locate the cash-flow interpolation interval")


def curve_metrics(times, cash, key_times, zero_rates):
    rows = [basis(t, key_times) for t in times]
    pv = [c * math.exp(-t * sum(b * z for b, z in zip(row, zero_rates)))
          for t, c, row in zip(times, cash, rows)]
    k = len(key_times)
    dollar_key = [sum(t * v * row[j] for t, v, row in zip(times, pv, rows)) for j in range(k)]
    hessian = [[sum(t * t * v * row[j] * row[l] for t, v, row in zip(times, pv, rows))
                for l in range(k)] for j in range(k)]
    return {"price": sum(pv), "basis_rows": rows, "cash_flow_pvs": pv,
            "dollar_key_durations": dollar_key,
            "key_durations": [x / sum(pv) for x in dollar_key],
            "dollar_hessian": hessian,
            "continuous_parallel_dollar_duration": sum(dollar_key),
            "continuous_parallel_dollar_convexity": sum(sum(row) for row in hessian)}


def curve_analysis(data, note_times, note_cash, asset_times, faces, horizon, amount, base_zero):
    keys(data, ["convention", "key_times", "scenarios"], "key-rate curve")
    if data["convention"] != CURVE_CONTRACT:
        raise ValueError("Curve convention cannot be silently changed")
    key_times = vector(data["key_times"], "key times", 2)
    strictly_increasing(key_times, "key times")
    zeros = [base_zero] * len(key_times)
    note = curve_metrics(note_times, note_cash, key_times, zeros)
    assets = curve_metrics(asset_times, faces, key_times, zeros)
    liability = curve_metrics([horizon], [amount], key_times, zeros)
    k = len(key_times)
    surplus_key = [a - l for a, l in zip(assets["dollar_key_durations"], liability["dollar_key_durations"])]
    surplus_hessian = [[assets["dollar_hessian"][i][j] - liability["dollar_hessian"][i][j]
                        for j in range(k)] for i in range(k)]
    base_surplus = assets["price"] - liability["price"]
    if not isinstance(data["scenarios"], list) or not data["scenarios"]:
        raise ValueError("At least one named key-rate scenario required")
    names, scenarios = set(), []
    for scenario in data["scenarios"]:
        keys(scenario, ["name", "bumps"], "key-rate scenario")
        name = scenario["name"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Scenario names must be distinct nonempty strings")
        names.add(name)
        bumps = vector(scenario["bumps"], "continuous zero bumps")
        if len(bumps) != k:
            raise ValueError("Every key-rate bump vector must match the stated key count")
        bumped = [z + h for z, h in zip(zeros, bumps)]
        pa = curve_metrics(asset_times, faces, key_times, bumped)["price"]
        pl = curve_metrics([horizon], [amount], key_times, bumped)["price"]
        linear = -sum(x * h for x, h in zip(surplus_key, bumps))
        second = sum(bumps[i] * surplus_hessian[i][j] * bumps[j] for i in range(k) for j in range(k)) / 2
        scenarios.append({"name": name, "continuous_zero_bumps": bumps,
                          "asset_price": pa, "liability_price": pl, "exact_surplus": pa - pl,
                          "linear_surplus": base_surplus + linear,
                          "quadratic_surplus": base_surplus + linear + second,
                          "exact_note_price": curve_metrics(note_times, note_cash, key_times, bumped)["price"]})
    return {"key_times": key_times, "baseline_continuous_zeros": zeros,
            "note": note, "assets": assets, "liability": liability,
            "surplus_dollar_key_durations": surplus_key,
            "surplus_dollar_hessian": surplus_hessian,
            "scenarios": scenarios}


def counterexample_analysis(data):
    keys(data, ["contract", "scale", "discount_cutoff", "stress_yield"], "local counterexample")
    if data["contract"] != COUNTER_CONTRACT:
        raise ValueError("The local counterexample is the stated fixed polynomial family")
    scale = number(data["scale"], "counterexample scale")
    cutoff = number(data["discount_cutoff"], "discount cutoff")
    y = number(data["stress_yield"], "counterexample stress yield")
    if scale <= 0 or cutoff <= 1 or y <= -1:
        raise ValueError("Counterexample needs positive scale, cutoff>1 and annual yield>-1")
    asset_times, asset_cash = [1, 3], [scale * cutoff, scale * (cutoff + 2)]
    liability_times, liability_cash = [2, 4], [scale * (2 * cutoff + 1), scale]
    assets = yield_metrics(asset_times, asset_cash, 0)
    liability = yield_metrics(liability_times, liability_cash, 0)
    d = 1 / (1 + y)
    changed_a = yield_metrics(asset_times, asset_cash, y)["price"]
    changed_l = yield_metrics(liability_times, liability_cash, y)["price"]
    return {"asset_times": asset_times, "asset_cash": asset_cash,
            "liability_times": liability_times, "liability_cash": liability_cash,
            "initial_asset_pv": assets["price"], "initial_liability_pv": liability["price"],
            "initial_surplus_first_derivative": -assets["dollar_duration"] + liability["dollar_duration"],
            "initial_surplus_second_derivative": assets["dollar_convexity"] - liability["dollar_convexity"],
            "stress_yield": y, "stress_discount_factor": d,
            "stress_asset_pv": changed_a, "stress_liability_pv": changed_l,
            "stress_surplus_direct": changed_a - changed_l,
            "stress_surplus_factored": scale * d * (d - 1) ** 2 * (cutoff - d),
            "negative_surplus_region": {"annual_yield_lower_exclusive": -1,
                                        "annual_yield_upper_exclusive": 1 / cutoff - 1}}


def run(data):
    keys(data, ["schema_version", "contract", "note", "immunization", "key_rate_curve", "local_counterexample"], "input")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or data["contract"] != CONTRACT:
        raise ValueError("Unsupported schema or financial contract")
    try:
        note, times, cash = note_analysis(data["note"])
        immunized, asset_times, faces, horizon, amount, base_zero = immunization_analysis(data["immunization"])
        curve = curve_analysis(data["key_rate_curve"], times, cash, asset_times, faces, horizon, amount, base_zero)
        counterexample = counterexample_analysis(data["local_counterexample"])
        result = {"schema_version": 1, "chapter": "v10-c02", "note": note,
                  "immunization": immunized, "key_rate_curve": curve,
                  "local_counterexample": counterexample,
                  "scope": "Deterministic fixed-settlement sensitivities and explicitly conditional cash ledgers; no rate probabilities, option model or guarantee against later shocks."}
        if not finite(result):
            raise ValueError("Input produces nonfinite output outside the numerical domain")
        json.dumps(result, allow_nan=False)
        return result
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("Input exceeds the bounded finite numerical domain") from exc


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError("Nonfinite JSON number: " + value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("v10-c02-inputs.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(), object_pairs_hook=unique_object, parse_constant=bad_constant)
    text = json.dumps(run(data), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
