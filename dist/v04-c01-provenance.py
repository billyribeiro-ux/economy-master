"""Offline vintage/provenance laboratory. See v04-c01-readme.txt.

Original synthetic teaching case; no live economic data or network requests.
"""
from datetime import date
from calendar import monthrange
from fractions import Fraction
from pathlib import Path
import argparse
import hashlib
import json
import platform

HERE = Path(__file__).resolve().parent
INPUT = HERE / 'v04-c01-releases.json'


def iso_date(value):
    if not isinstance(value, str):
        raise ValueError('Date must be an ISO YYYY-MM-DD string')
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('Date must be canonical YYYY-MM-DD')
    return parsed


def validate(data):
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        raise ValueError('Expected schema version 1')
    if data.get('units') != {'nominal_spending': 'USD', 'price_index': 'base=100'}:
        raise ValueError('Unexpected units')
    periods = data.get('expected_periods')
    if not isinstance(periods, list) or not periods or len(set(periods)) != len(periods):
        raise ValueError('Expected distinct monthly periods')
    for period in periods:
        if not isinstance(period, str) or iso_date(period + '-01').strftime('%Y-%m') != period:
            raise ValueError('Period must be canonical YYYY-MM')
    rows = data.get('rows')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Nonempty release rows required')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'period', 'available_on', 'nominal_spending', 'price_index'}:
            raise ValueError('Unexpected row schema')
        if row['period'] not in periods:
            raise ValueError('Period outside declared coverage')
        iso_date(row['available_on'])
        first_day = iso_date(row['period'] + '-01')
        month_end = first_day.replace(day=monthrange(first_day.year, first_day.month)[1])
        if iso_date(row['available_on']) < month_end:
            raise ValueError('A realized monthly flow cannot be released before month-end in this case')
        key = (row['period'], row['available_on'])
        if key in seen:
            raise ValueError('Duplicate period/availability key')
        seen.add(key)
        for name in ('nominal_spending', 'price_index'):
            # Integer-valued inputs by design; bool is an int subclass in Python.
            if type(row[name]) is not int:
                raise ValueError(name + ' must be an integer in this schema')
        if row['nominal_spending'] < 0 or row['price_index'] <= 0:
            raise ValueError('Spending must be nonnegative and price index positive')
    return data


def snapshot(data, cutoff):
    validate(data)
    iso_date(cutoff)
    chosen = {}
    for row in data['rows']:
        period = row['period']
        if row['available_on'] <= cutoff:
            if period not in chosen or row['available_on'] > chosen[period]['available_on']:
                chosen[period] = row.copy()
    missing = set(data['expected_periods']) - set(chosen)
    if missing:
        raise ValueError('Unavailable required periods at cutoff: ' + ', '.join(sorted(missing)))
    return [chosen[period] for period in sorted(chosen)]


def summarize(rows):
    real = [Fraction(100 * row['nominal_spending'], row['price_index']) for row in rows]
    if rows[0]['nominal_spending'] == 0:
        raise ValueError('Endpoint growth is undefined with zero initial spending')
    return {
        'nominal_total_usd': sum(row['nominal_spending'] for row in rows),
        'real_total_base_usd': sum(real),
        'real_endpoint_growth': real[-1] / real[0] - 1,
        'nominal_endpoint_growth': Fraction(rows[-1]['nominal_spending'], rows[0]['nominal_spending']) - 1,
        'real_by_period': dict(zip((row['period'] for row in rows), real)),
    }


def encode(value):
    if isinstance(value, Fraction):
        return {'exact': str(value), 'decimal': float(value)}
    raise TypeError('Unsupported output value')


def run(path, cutoff):
    raw = Path(path).read_bytes()
    data = json.loads(raw.decode('utf-8'))
    rows = snapshot(data, cutoff)
    return {
        'synthetic': True, 'cutoff_inclusive': cutoff,
        'input_sha256': hashlib.sha256(raw).hexdigest(),
        'runtime': {'implementation': platform.python_implementation(), 'python': platform.python_version()},
        'selected_rows': rows, 'results': summarize(rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cutoff', required=True, help='Inclusive YYYY-MM-DD cutoff')
    parser.add_argument('--input', type=Path, default=INPUT)
    args = parser.parse_args()
    try:
        output = run(args.input, args.cutoff)
    except (ValueError, TypeError, OSError, KeyError) as error:
        parser.exit(2, 'Input rejected: ' + str(error) + '\n')
    print(json.dumps(output, default=encode, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
