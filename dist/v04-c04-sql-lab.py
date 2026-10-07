#!/usr/bin/env python3
"""Offline benchmark for v04-c04. Python 3.9+ with its bundled sqlite3.

Keep v04-c04-case.json beside this script. Run:
    python3 v04-c04-sql-lab.py
No network, third-party package, or persistent database is used.
"""
from array import array
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import sys


def load_case(path=None):
    path = Path(path) if path else Path(__file__).with_name("v04-c04-case.json")
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def require_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be nonempty text")


def require_integer(value, label):
    # bool is an int subclass in Python but is not a measurement here.
    if type(value) is not int or not -(2 ** 63) <= value < 2 ** 63:
        raise ValueError(label + " must be a signed 64-bit integer")


def normalize_time(value):
    """Require a declared offset and seconds; normalize without losing precision."""
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", value
    ):
        raise ValueError("event time requires seconds and an explicit numeric offset")
    if int(value[-5:-3]) > 23 or int(value[-2:]) > 59:
        raise ValueError("offset requires hours 00-23 and minutes 00-59")
    moment = datetime.fromisoformat(value)
    utc = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return utc.isoformat(sep=" ", timespec="seconds")


def validate_case(case):
    ids = set()
    for row in case["households"]:
        key = row["household_id"]
        require_text(key, "household_id")
        if key in ids:
            raise ValueError("duplicate household_id: " + key)
        ids.add(key)
        require_text(row["region"], "region")
        require_integer(row["weight"], "weight")
        if row["weight"] <= 0:
            raise ValueError("weight must be positive")
    seen_obs, seen_pairs = set(), set()
    for row in case["observations"]:
        require_text(row["obs_id"], "obs_id")
        if row["obs_id"] in seen_obs:
            raise ValueError("duplicate obs_id")
        seen_obs.add(row["obs_id"])
        require_text(row["household_id"], "observation household_id")
        if row["household_id"] not in ids:
            raise ValueError("observation household is absent from roster")
        require_text(row["month"], "month")
        parsed = date.fromisoformat(row["month"])
        if parsed.isoformat() != row["month"] or parsed.day != 1:
            raise ValueError("month must be canonical YYYY-MM-01")
        pair = (row["household_id"], row["month"])
        if pair in seen_pairs:
            raise ValueError("duplicate household-month")
        seen_pairs.add(pair)
        if row["income_cents"] is not None:
            require_integer(row["income_cents"], "income_cents")
    seen_events = set()
    for row in case["events"]:
        require_text(row["event_id"], "event_id")
        if row["event_id"] in seen_events:
            raise ValueError("duplicate event_id")
        seen_events.add(row["event_id"])
        require_integer(row["amount_cents"], "amount_cents")
        normalize_time(row["time_with_offset"])


def make_db(case):
    validate_case(case)
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("""
        CREATE TABLE households (
          household_id TEXT PRIMARY KEY NOT NULL,
          region TEXT NOT NULL,
          weight INTEGER NOT NULL CHECK(typeof(weight) = 'integer' AND weight > 0)
        );
        CREATE TABLE observations (
          obs_id TEXT PRIMARY KEY NOT NULL,
          household_id TEXT NOT NULL REFERENCES households(household_id),
          month TEXT NOT NULL,
          income_cents INTEGER CHECK(income_cents IS NULL OR typeof(income_cents) = 'integer'),
          UNIQUE(household_id, month)
        );
        CREATE TABLE raw_roster (household_id TEXT, region TEXT, weight INTEGER);
        CREATE TABLE events (
          event_id TEXT PRIMARY KEY NOT NULL,
          time_with_offset TEXT NOT NULL,
          time_utc TEXT NOT NULL,
          amount_cents INTEGER NOT NULL
        );
    """)
    con.executemany("INSERT INTO households VALUES (?, ?, ?)", [
        (r["household_id"], r["region"], r["weight"]) for r in case["households"]
    ])
    con.executemany("INSERT INTO observations VALUES (?, ?, ?, ?)", [
        (r["obs_id"], r["household_id"], r["month"], r["income_cents"])
        for r in case["observations"]
    ])
    # Intentionally unconstrained diagnostic input, kept apart from the roster.
    con.executemany("INSERT INTO raw_roster VALUES (?, ?, ?)", [
        (r["household_id"], r["region"], r["weight"]) for r in case["raw_roster"]
    ])
    con.executemany("INSERT INTO events VALUES (?, ?, ?, ?)", [
        (r["event_id"], r["time_with_offset"], normalize_time(r["time_with_offset"]),
         r["amount_cents"]) for r in case["events"]
    ])
    con.commit()
    return con


def rows(con, query, parameters=()):
    return [dict(row) for row in con.execute(query, parameters)]


def one(con, query, parameters=()):
    return dict(con.execute(query, parameters).fetchone())


def array_totals(products, quantities, prices):
    if len(set(products)) != len(products):
        raise ValueError("duplicate product label")
    if set(products) != set(prices):
        raise ValueError("price labels and quantity labels differ")
    aligned = array("q", [prices[name] for name in products])
    answer = []
    for row in quantities:
        if len(row) != len(products):
            raise ValueError("quantity matrix is not rectangular with the declared columns")
        answer.append(sum(row[j] * aligned[j] for j in range(len(products))))
    return answer


def report(case):
    con = make_db(case)
    try:
        monthly = {}
        for month in ("2024-01-01", "2024-02-01"):
            monthly[month] = one(con, """
                SELECT COUNT(*) AS roster_rows, COUNT(o.obs_id) AS report_rows,
                       COUNT(o.income_cents) AS observed_incomes,
                       SUM(o.income_cents) AS sum_cents,
                       AVG(o.income_cents) AS observed_mean_cents,
                       AVG(COALESCE(o.income_cents, 0)) AS zero_filled_mean_cents
                FROM households AS h LEFT JOIN observations AS o
                  ON h.household_id = o.household_id AND o.month = ?
            """, (month,))
            monthly[month]["weighted"] = one(con, """
                SELECT SUM(h.weight * o.income_cents) AS numerator_cents,
                       SUM(h.weight) AS observed_weight,
                       1.0 * SUM(h.weight * o.income_cents) / SUM(h.weight) AS mean_cents
                FROM households AS h JOIN observations AS o
                  ON h.household_id = o.household_id
                WHERE o.month = ? AND o.income_cents IS NOT NULL
            """, (month,))
        results = {
            "runtime": {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version},
            "worked_array_cents": array_totals(
                ["grain", "tools"], [[20, 3], [10, 4]], {"tools": 5000, "grain": 200}),
            "monthly": monthly,
            "raw_duplicate_keys": rows(con, """
                SELECT household_id, COUNT(*) AS copies FROM raw_roster
                GROUP BY household_id HAVING COUNT(*) > 1 ORDER BY household_id
            """),
            "inflated_january": one(con, """
                SELECT COUNT(*) AS rows, SUM(o.income_cents) AS sum_cents
                FROM observations AS o JOIN raw_roster AS h
                  ON o.household_id = h.household_id WHERE o.month = ?
            """, ("2024-01-01",)),
            "where_trap_ids": rows(con, """
                SELECT h.household_id FROM households AS h LEFT JOIN observations AS o
                  ON h.household_id = o.household_id
                WHERE o.month = ? ORDER BY h.household_id
            """, ("2024-02-01",)),
            "february_roster": rows(con, """
                SELECT h.household_id, o.obs_id, o.income_cents
                FROM households AS h LEFT JOIN observations AS o
                  ON h.household_id = o.household_id AND o.month = ?
                ORDER BY h.household_id
            """, ("2024-02-01",)),
            "january_regions": rows(con, """
                SELECT h.region, COUNT(o.income_cents) AS n,
                       SUM(o.income_cents) AS total_cents,
                       AVG(o.income_cents) AS mean_cents
                FROM households AS h LEFT JOIN observations AS o
                  ON h.household_id = o.household_id AND o.month = ?
                GROUP BY h.region ORDER BY h.region
            """, ("2024-01-01",)),
            "all_null": one(con, """
                SELECT COUNT(*) AS n, COUNT(income_cents) AS observed,
                       SUM(income_cents) AS total, AVG(income_cents) AS mean
                FROM observations WHERE obs_id = 'b2'
            """),
            "empty": one(con, """
                SELECT COUNT(*) AS n, COUNT(income_cents) AS observed,
                       SUM(income_cents) AS total, AVG(income_cents) AS mean
                FROM observations WHERE month = '1900-01-01'
            """),
            "utc_february": rows(con, """
                SELECT event_id, time_utc, amount_cents FROM events
                WHERE time_utc >= ? AND time_utc < ? ORDER BY event_id
            """, ("2024-02-01 00:00:00", "2024-03-01 00:00:00")),
            "all_normalized_events": rows(con, """
                SELECT event_id, time_utc, datetime(time_with_offset) AS sqlite_utc
                FROM events ORDER BY event_id
            """),
            "exercise_1_cents": array_totals(
                ["a", "b", "c"], [[2, 3, 1], [1, 0, 4]], {"c": 50, "a": 100, "b": 200}),
            "exercise_2_grain": one(con, """
                SELECT COUNT(*) AS rows, COUNT(DISTINCT household_id) AS households
                FROM observations
            """),
            "exercise_7_join": one(con, """
                WITH left_rows(k, amount) AS (VALUES ('x', 100), ('x', 50)),
                     right_rows(k, label) AS (VALUES ('x', 'p'), ('x', 'q'), ('x', 'r'))
                SELECT COUNT(*) AS rows, SUM(l.amount) AS repeated_amount
                FROM left_rows AS l JOIN right_rows AS r ON l.k = r.k
            """),
            "exercise_8_panel": one(con, """
                WITH months(month) AS (VALUES ('2024-01-01'), ('2024-02-01'))
                SELECT COUNT(*) AS cells, COUNT(o.obs_id) AS report_rows,
                       COUNT(o.income_cents) AS observed_incomes,
                       SUM(o.income_cents) AS sum_cents,
                       AVG(o.income_cents) AS observed_mean_cents,
                       AVG(COALESCE(o.income_cents, 0)) AS zero_filled_mean_cents
                FROM households AS h CROSS JOIN months AS m
                LEFT JOIN observations AS o
                  ON h.household_id = o.household_id AND m.month = o.month
            """),
        }
        return results
    finally:
        con.close()


if __name__ == "__main__":
    print(json.dumps(report(load_case()), indent=2, allow_nan=False))
