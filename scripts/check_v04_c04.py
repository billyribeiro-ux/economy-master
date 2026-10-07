#!/usr/bin/env python3
"""Independent arithmetic and behavior checks for the v04-c04 SQL lab.

Run from any working directory: python3 /path/to/book/scripts/check_v04_c04.py
Uses only the standard library. check() raises AssertionError on a mismatch.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import sqlite3


def check():
    project = Path(__file__).resolve().parents[1] / "content" / "projects"
    spec = importlib.util.spec_from_file_location("v04_c04_lab", project / "v04-c04-sql-lab.py")
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    case = lab.load_case()
    result = lab.report(case)
    checks = []

    def equal(actual, expected, label):
        if isinstance(expected, Fraction):
            assert math.isclose(actual, float(expected), rel_tol=1e-12, abs_tol=1e-9), (label, actual, expected)
        else:
            assert actual == expected, (label, actual, expected)
        checks.append(label)

    # Compute labelled revenue independently, without calling the lab's array loop.
    prices = {"grain": 200, "tools": 5000}
    north, south = {"grain": 20, "tools": 3}, {"grain": 10, "tools": 4}
    revenues = [sum(amount * prices[key] for key, amount in row.items()) for row in (north, south)]
    equal(result["worked_array_cents"], revenues, "Worked 1 labelled dot products")
    equal(sum(revenues), 41000, "Worked 1 total 41000 cents")
    equal(20 * 5000 + 3 * 200, 100600, "Worked 1 positional error 100600 cents")
    equal(result["exercise_1_cents"], [850, 300], "Exercise 1 aligned rows")
    equal(sum(result["exercise_1_cents"]), 1150, "Exercise 1 total")
    equal([2 * 50 + 3 * 100 + 200, 50 + 4 * 200], [600, 850], "Exercise 1 misaligned rows")
    equal([1, 2] * 2, [1, 2, 1, 2], "Sequence multiplication is repetition")
    for products, quantities, prices_arg in [
        (["a", "b"], [[1]], {"a": 10, "b": 20}),
        (["a"], [[1]], {"b": 10}),
        (["a", "a"], [[1, 2]], {"a": 10}),
    ]:
        try:
            lab.array_totals(products, quantities, prices_arg)
        except ValueError:
            checks.append("Invalid array dimensions/labels rejected")
        else:
            raise AssertionError("Invalid array accepted")

    households = case["households"]
    reports = case["observations"]
    equal(result["exercise_2_grain"], {"rows": len(reports), "households": len({r['household_id'] for r in reports})}, "Exercise 2 grain counts")
    equal(len({r["obs_id"] for r in reports}), 7, "Observation IDs unique")
    equal(len({(r["household_id"], r["month"]) for r in reports}), 7, "Household-months unique")
    for month in ("2024-01-01", "2024-02-01"):
        month_reports = [r for r in reports if r["month"] == month]
        measured = [r for r in month_reports if r["income_cents"] is not None]
        weights = {h["household_id"]: h["weight"] for h in households}
        total = sum(r["income_cents"] for r in measured)
        numerator = sum(weights[r["household_id"]] * r["income_cents"] for r in measured)
        denominator = sum(weights[r["household_id"]] for r in measured)
        got = result["monthly"][month]
        for name, expected in {
            "roster_rows": len(households), "report_rows": len(month_reports),
            "observed_incomes": len(measured), "sum_cents": total,
            "observed_mean_cents": Fraction(total, len(measured)),
            "zero_filled_mean_cents": Fraction(total, len(households)),
        }.items():
            equal(got[name], expected, month + " " + name)
        for name, expected in {
            "numerator_cents": numerator, "observed_weight": denominator,
            "mean_cents": Fraction(numerator, denominator),
        }.items():
            equal(got["weighted"][name], expected, month + " weighted " + name)
    equal(result["monthly"]["2024-01-01"]["weighted"]["mean_cents"] / 100, Fraction(500, 3), "January weighted dollars")
    equal(result["monthly"]["2024-02-01"]["weighted"]["numerator_cents"] / 10 / 100, 24.0, "Wrong full-roster denominator gives 24 dollars")

    # Join enumeration is independent of SQLite and the benchmark query.
    duplicated_pairs = [(o, h) for o in reports for h in case["raw_roster"]
                        if o["month"] == "2024-01-01" and o["household_id"] == h["household_id"]]
    inflated = sum(o["income_cents"] for o, h in duplicated_pairs)
    equal(result["inflated_january"], {"rows": len(duplicated_pairs), "sum_cents": inflated}, "Exercise 3 duplicate join enumeration")
    equal(Fraction(inflated - 40000, 40000), Fraction(1, 4), "Exercise 3 25 percent inflation")
    duplicates = Counter(r["household_id"] for r in case["raw_roster"])
    equal(result["raw_duplicate_keys"], [{"household_id": k, "copies": n} for k, n in sorted(duplicates.items()) if n > 1], "Duplicate key query agrees with Counter")
    equal(result["where_trap_ids"], [{"household_id": h} for h in ["A", "B", "C"]], "Exercise 4 WHERE drops D")
    equal(result["february_roster"], [
        {"household_id": "A", "obs_id": "a2", "income_cents": 12000},
        {"household_id": "B", "obs_id": "b2", "income_cents": None},
        {"household_id": "C", "obs_id": "c2", "income_cents": 6000},
        {"household_id": "D", "obs_id": None, "income_cents": None},
    ], "Exercise 4 present missing and absent rows distinguished")
    equal(result["all_null"], {"n": 1, "observed": 0, "total": None, "mean": None}, "Exercise 4 all-NULL aggregate")
    equal(result["empty"], {"n": 0, "observed": 0, "total": None, "mean": None}, "Exercise 4 empty aggregate")
    equal(result["january_regions"], [
        {"region": "North", "n": 2, "total_cents": 40000, "mean_cents": 20000.0},
        {"region": "South", "n": 1, "total_cents": 0, "mean_cents": 0.0},
    ], "Exercise 5 regional summaries")
    equal(sum(r["mean_cents"] for r in result["january_regions"]) / 2, 10000, "Exercise 5 mean of region means")
    regrouped = sum(r["total_cents"] for r in result["january_regions"])
    equal(Fraction(regrouped, sum(r["n"] for r in result["january_regions"])), Fraction(40000, 3), "Exercise 5 regrouped mean")

    # Normalize offsets independently by subtracting their stated hours/minutes.
    normalized = {}
    for event in case["events"]:
        raw = event["time_with_offset"]
        base = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
        sign = 1 if raw[19] == "+" else -1
        offset = timedelta(hours=int(raw[20:22]), minutes=int(raw[23:25]))
        normalized[event["event_id"]] = (base - sign * offset).strftime("%Y-%m-%d %H:%M:%S")
    for r in result["all_normalized_events"]:
        equal(r["time_utc"], normalized[r["event_id"]], "Exercise 6 independent UTC " + r["event_id"])
        equal(r["sqlite_utc"], normalized[r["event_id"]], "SQLite UTC cross-check " + r["event_id"])
    equal([r["event_id"] for r in result["utc_february"]], ["e1", "e3", "e5"], "Exercise 6 UTC February membership")
    equal(sum(r["amount_cents"] for r in result["utc_february"]), 900, "Exercise 6 UTC total 900 cents")
    local = [r for r in case["events"] if r["time_with_offset"].startswith("2024-02")]
    equal([r["event_id"] for r in local], ["e2", "e3", "e5"], "Exercise 6 local membership differs")
    equal(sum(r["amount_cents"] for r in local), 1000, "Exercise 6 local total")
    equal(900 + 400, 1300, "Exercise 6 inclusive upper boundary error")

    pairs = [(x, label) for x in [100, 50] for label in ["p", "q", "r"]]
    equal(result["exercise_7_join"], {"rows": len(pairs), "repeated_amount": sum(x for x, label in pairs)}, "Exercise 7 multiplicative join")
    panel = [(h, month, next((r for r in reports if r["household_id"] == h["household_id"] and r["month"] == month), None))
             for h in households for month in ["2024-01-01", "2024-02-01"]]
    measured_panel = [r["income_cents"] for h, month, r in panel if r is not None and r["income_cents"] is not None]
    equal(result["exercise_8_panel"], {
        "cells": len(panel), "report_rows": sum(r is not None for h, month, r in panel),
        "observed_incomes": len(measured_panel), "sum_cents": sum(measured_panel),
        "observed_mean_cents": sum(measured_panel) / len(measured_panel),
        "zero_filled_mean_cents": sum(measured_panel) / len(panel),
    }, "Exercise 8 independently enumerated panel")
    equal(sum(r is None for h, month, r in panel), 2, "Exercise 8 two absent reports")
    equal(sum(r is not None and r['income_cents'] is None for h, month, r in panel), 1, "Exercise 8 one missing reported income")

    con = lab.make_db(case)
    try:
        equal(tuple(con.execute("SELECT NULL = NULL, NULL IS NULL, 0 * NULL, 5 / 2, 5 / 2.0").fetchone()), (None, 1, None, 2, 2.5), "NULL and division behavior")
        equal(con.execute("SELECT julianday('2024-03-01') - julianday('2024-02-01')").fetchone()[0], 29.0, "Exercise 6 February length")
        equal(con.execute("SELECT COUNT(*) FROM observations WHERE income_cents = NULL").fetchone()[0], 0, "Equality is not a NULL test")
        equal(con.execute("SELECT COUNT(*) FROM observations WHERE income_cents IS NULL").fetchone()[0], 1, "IS NULL finds missing measurement")
        query = """WITH l(k, amount) AS (VALUES ('x',100),('x',50)),
                         r(k) AS (VALUES ('x'),('x'),('x'))
                   SELECT SUM(l.amount) FROM l WHERE EXISTS (SELECT 1 FROM r WHERE r.k=l.k)"""
        equal(con.execute(query).fetchone()[0], 150, "Exercise 7 EXISTS preserves left grain")
        equal(tuple(con.execute("WITH x(amount) AS (VALUES (50),(50)) SELECT SUM(amount), SUM(DISTINCT amount) FROM x").fetchone()), (100, 50), "Exercise 7 equal amounts cannot be deduplicated")
        equal(con.execute("SELECT COUNT(*) FROM observations WHERE household_id = ?", ("A' OR 1=1 --",)).fetchone()[0], 0, "Bound values do not become SQL syntax")
        # An out-of-month-only household defeats WHERE ... OR month IS NULL too.
        con.execute("INSERT INTO households VALUES ('E', 'South', 1)")
        con.execute("INSERT INTO observations VALUES ('e3', 'E', '2024-03-01', 100)")
        faulty = [r[0] for r in con.execute("SELECT h.household_id FROM households h LEFT JOIN observations o ON h.household_id=o.household_id WHERE o.month='2024-02-01' OR o.month IS NULL ORDER BY h.household_id")]
        equal(faulty, ["A", "B", "C", "D"], "WHERE OR NULL still drops out-of-month-only E")
        preserved = [r[0] for r in con.execute("SELECT h.household_id FROM households h LEFT JOIN observations o ON h.household_id=o.household_id AND o.month='2024-02-01' ORDER BY h.household_id")]
        equal(preserved, ["A", "B", "C", "D", "E"], "ON preserves out-of-month-only E")
        for statement in [
            "INSERT INTO observations VALUES ('copy', 'A', '2024-02-01', 123)",
            "INSERT INTO observations VALUES ('orphan', 'Z', '2024-02-01', 123)",
            "INSERT INTO households VALUES (NULL, 'North', 1)",
        ]:
            try:
                con.execute(statement)
            except sqlite3.IntegrityError:
                checks.append("Database key/foreign-key constraint rejects invalid row")
            else:
                raise AssertionError("Database constraint failed")
    finally:
        con.close()

    invalid_cases = []
    def invalid(mutator, label):
        bad = deepcopy(case)
        mutator(bad)
        invalid_cases.append((bad, label))
    invalid(lambda d: d["households"].append(deepcopy(d["households"][0])), "duplicate household")
    invalid(lambda d: d["observations"].append(dict(d["observations"][1], obs_id="a2-copy")), "duplicate household-month")
    invalid(lambda d: d["observations"][0].update(household_id="Z"), "orphan report")
    invalid(lambda d: d["observations"][0].update(household_id=None), "NULL household key")
    invalid(lambda d: d["observations"][0].update(month="2024-02-30"), "impossible calendar date")
    invalid(lambda d: d["observations"][0].update(month="2024-01-02"), "noncanonical month label")
    invalid(lambda d: d["observations"][0].update(income_cents="10000"), "numeric string")
    invalid(lambda d: d["observations"][0].update(income_cents=True), "boolean measurement")
    invalid(lambda d: d["observations"][0].update(income_cents=10.25), "fractional cents")
    invalid(lambda d: d["households"][0].update(weight=0), "zero weight")
    invalid(lambda d: d["events"][0].update(time_with_offset="2024-02-01T00:00:00"), "missing time offset")
    invalid(lambda d: d["events"][0].update(time_with_offset="2024-02-01T00:00:00.5+00:00"), "unsupported subseconds")
    invalid(lambda d: d["events"][0].update(time_with_offset="2024-02-01T00:00:00+01:60"), "invalid offset minutes")
    invalid(lambda d: d["events"][0].update(time_with_offset="2024-02-01T00:00:00+24:00"), "invalid offset hours")
    for bad, label in invalid_cases:
        try:
            lab.validate_case(bad)
        except (ValueError, TypeError):
            checks.append("Input rejects " + label)
        else:
            raise AssertionError("Input accepted " + label)
    equal(lab.normalize_time("0001-01-01T00:00:00+00:00"), "0001-01-01 00:00:00", "UTC format preserves four-digit early year")
    changed = deepcopy(case)
    changed["observations"][3]["income_cents"] = 0
    changed_report = lab.report(changed)["monthly"]["2024-02-01"]
    equal(changed_report["observed_incomes"], 3, "Retention zero replaces missing: count rises")
    equal(changed_report["sum_cents"], 18000, "Retention zero replaces missing: sum unchanged")
    equal(changed_report["observed_mean_cents"], 6000.0, "Retention zero replaces missing: observed mean changes")
    equal(changed_report["weighted"]["observed_weight"], 6, "Retention zero replaces missing: B weight enters")
    equal(changed_report["weighted"]["mean_cents"], 4000.0, "Retention weighted mean becomes 40 dollars")
    return {
        "status": "passed", "checks": checks, "check_count": len(checks),
        "runtime": result["runtime"],
        "limitations": [
            "Synthetic data; no claim about real household populations or missingness mechanisms.",
            "Tests check specified calculations and failure cases, not arbitrary SQL programs or all numeric magnitudes.",
            "Visual/mobile/print browser QA remains pending; author review is not external academic validation."
        ],
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
