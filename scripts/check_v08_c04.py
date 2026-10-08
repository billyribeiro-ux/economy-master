#!/usr/bin/env python3
"""Independent exact checks for v08-c04 and its original payoff contracts."""
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects/v08-c04-analysis.py'


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.links = []
        self.worked = 0
        self.exercises = 0
        self.solutions = 0
        self.mode = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a':
            self.links.append(a.get('href', ''))
        if 'worked' in a.get('class', '').split():
            self.worked += 1
        if tag == 'ol' and a.get('class') == 'exercises':
            self.mode = 'exercises'
        if tag == 'details' and a.get('class') == 'solutions':
            self.mode = 'solutions'
        if tag == 'li' and self.mode:
            setattr(self, self.mode, getattr(self, self.mode) + 1)
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack.pop() == tag, 'Unbalanced HTML fragment: ' + tag
        if (tag == 'ol' and self.mode == 'exercises') or (tag == 'details' and self.mode == 'solutions'):
            self.mode = None


def check():
    spec = importlib.util.spec_from_file_location('v08_c04_lab', PROJECT)
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    data = json.loads(PROJECT.with_name('v08-c04-inputs.json').read_text())
    result = lab.compute(data)
    checks = []

    # Recompute directly from a finite physical law, using raw centered cross products.
    m = list(map(F, ['-.10', '-.02', '.02', '.10']))
    e = list(map(F, ['.02', '-.02', '-.02', '.02']))
    x = [F(3, 2) * a + b for a, b in zip(m, e)]
    z = [a / 2 + 6 * b for a, b in zip(m, e)]
    vm = sum(a * a for a in m) / 4
    assert vm == F('.0052') and sum(a * b for a, b in zip(m, e)) == 0
    for name, states, beta, variance, required in (
            ('x', x, F('1.5'), F('.0121'), F('.105')),
            ('z', z, F('.5'), F('.0157'), F('.055'))):
        assert sum(states) == 0
        cov = sum(a * b for a, b in zip(states, m)) / 4
        assert cov / vm == beta and sum(a * a for a in states) / 4 == variance
        row = result['moment_case'][name]
        assert row['beta'] == beta and row['claim_variance'] == variance
        assert row['covariance'] == cov and row['required_return'] == required
    # A separate strictly positive state-price certificate establishes joint price compatibility.
    # These are risk-neutral weights, not the equal physical probabilities used for moments.
    pricing_weights = [F(19, 40), F(15, 40), F(5, 40), F(1, 40)]
    assert sum(pricing_weights) == 1 and all(p > 0 for p in pricing_weights)
    assert sum(p * a for p, a in zip(pricing_weights, m)) == F('-.05')
    assert sum(p * a for p, a in zip(pricing_weights, e)) == 0
    for states, mean in [(m, F('.08')), (x, F('.105')), (z, F('.055'))]:
        assert sum(p * (1 + mean + a) for p, a in zip(pricing_weights, states)) / F('1.03') == 1
    checks.append('Exact covariance/projection contrasts and positive joint pricing certificate')

    # Value the one-period cash state by state, without using the lab WACC/APV helpers.
    eq_payoff = [700 * (F('1.09') + F('1.2') * a) for a in m]
    debt_payoff = F(309)
    ts = F('2.25')
    operating_payoff = [a + debt_payoff - ts for a in eq_payoff]
    assert min(operating_payoff) == F('985.75')
    assert sum(operating_payoff) / 4 == F('1069.75')
    assert sum(eq_payoff) / 4 == 763
    operating_pv = sum(p * c for p, c in zip(pricing_weights, operating_payoff)) / F('1.03')
    shield_pv = ts / F('1.03')
    assert sum(p * c for p, c in zip(pricing_weights, eq_payoff)) / F('1.03') == 700
    assert operating_pv + shield_pv == 1000 and debt_payoff / F('1.03') == 300
    row = result['one_period']
    assert row['operating_value'] == row['apv_value'] == 1000
    assert row['state_operating_cash'] == operating_payoff
    assert row['unlevered_value'] == operating_pv and row['shield_value'] == shield_pv
    assert row['wacc'] == F(279, 4000) and row['equity_return'] == F('.09')
    assert row['book_weight_wacc'] == F('.05625')
    assert row['wrong_book_weight_value'] == F('1069.75') / F('1.05625')
    assert row['unlevered_beta'] == F(840) / operating_pv
    assert row['unlevered_return'] == F('1069.75') / operating_pv - 1
    checks.append('WACC, APV and debt/equity value agree with independent state-price valuation')

    c = result['no_tax_comparable']
    assert c['operating_beta'] == F(17, 15)
    assert c['target_equity_beta'] == F(41, 30)
    assert c['debt_to_equity'] == F(1, 4)
    assert c['equity_return'] == F(59, 600) and c['debt_return'] == F('.04')
    assert c['no_tax_wacc'] == c['unlevered_return'] == F(13, 150)
    # General beta identity under the fixed-perpetual-debt shield contract.
    beta_u = F('1.5') / (1 + F('.75') * F(2, 3))
    beta_target = beta_u * (1 + F('.75') / 4)
    assert beta_u == 1 and beta_target == F(19, 16)
    # Choose E300,D200: S50,VU450; claim beta exposure450 equals operating exposure450.
    assert F('1.5') * 300 == beta_u * (300 + 200 - F('.25') * 200)
    checks.append('No-tax comparable and policy-specific perpetual-debt beta identities')

    # Finite APV computed through independently constructed maturity discount factors.
    dfu = [F(10, 11) ** t for t in (1, 2, 3)]
    dfs = [F(25, 26) ** t for t in (1, 2, 3)]
    vu = sum(a * d for a, d in zip((48, 53, 58), dfu))
    s = sum(a * d for a, d in zip(map(F, ['.6', '.4', '.2']), dfs))
    apv = result['finite_apv']
    assert apv['unlevered_value'] == vu and apv['shield_value'] == s
    assert apv['apv_npv'] == vu + s - 125
    assert apv['debt_service'] == list(map(F, ['22.4', '21.6', '20.8']))
    assert sum(a * d for a, d in zip(apv['debt_service'], dfs)) == apv['debt_service_value'] == 60
    assert apv['equity_value'] - apv['equity_initial_contribution'] == apv['apv_npv']
    for policy, expected_shield in [('deferred_to_final', F('1.2') * dfs[-1]), ('none', F(0))]:
        changed = deepcopy(data)
        changed['finite_apv']['tax_use'] = policy
        trial = lab.compute(changed)['finite_apv']
        assert trial['shield_value'] == expected_shield
        assert trial['apv_npv'] == vu + expected_shield - 125
    assert F('.25') * 60 != s
    assert sum(a * d for a, d in zip(map(F, ['.6', '.4', '.2']), dfu)) != s
    checks.append('Finite debt schedule, current/deferred/unavailable tax cash and equity NPV')

    # Every determinate exercise, including two distinct financing policies and decision reversals.
    assert F('.03') / F('.04') == F('.75')
    assert F('.03') / (F('.3') * F('.2')) == F('.5')
    assert F('.03') + F('.75') * F('.06') == F('.075')
    assert F('.03') + F('.5') * F('.06') == F('.06')
    assert F('.6') * F('.105') + F('.4') * F('.04') * F('.75') == F('.075')
    assert F(860) / F('1.075') == 800 and F('530.4') + F('332.8') == 860 + F('3.2')
    assert F('.105') / 3 + F(2, 3) * F('.04') * F('.75') == F('.055')
    assert round(float(F(860) / F('1.055')), 6) == 815.165877
    assert round(float(F(104) / F('1.06')), 6) == 98.113208
    assert F('.9') * 108 + F('.1') * 60 == F('103.2')
    assert round(float((F(108) / 95 - 1) * 100), 6) == 13.684211
    assert round(float((F('103.2') / 95 - 1) * 100), 6) == 8.631579
    assert (500 * F('1.4') + 100 * F('.2')) / 600 == F('1.2')
    exercise_beta = (F('1.2') - F('.25') * F('.2')) / F('.75')
    assert exercise_beta == F(23, 15)
    assert F('.75') * (F('.03') + exercise_beta * F('.05')) + F('.25') * F('.04') == F('.09')
    u2 = 70 * F(10, 11) + 75 * F(10, 11) ** 2
    s2 = F('.4') * F(25, 26) + F('.2') * F(25, 26) ** 2
    sd2 = F('.6') * F(25, 26) ** 2
    assert 27 * F(25, 26) + 26 * F(25, 26) ** 2 == 50
    assert round(float(u2 + s2 - 120), 6) == 6.189361
    assert round(float(u2 + sd2 - 120), 6) == 6.174568
    nominal_cash = 200 * F('1.02') ** 2
    nominal_rate = F('1.05') * F('1.02') - 1
    assert nominal_cash == F('208.08') and nominal_rate == F('.071')
    assert nominal_cash / (1 + nominal_rate) ** 2 == 200 / F('1.05') ** 2
    for cash, rate, expected in [(112, '.09', 2.752294), (107, '.09', -1.834862),
                                 (112, '.13', -.884956), (107, '.06', .943396)]:
        assert round(float(F(cash) / (1 + F(rate)) - 100), 6) == expected
    low, high = F('.7') * F('.07') + F('.3') * F('.03') * F('.75'), F('.7') * F('.114') + F('.3') * F('.03') * F('.75')
    assert (low, high) == (F('.05575'), F('.08655'))
    assert round(float(F('1069.75') / (1 + low)), 4) == 1013.2607
    assert round(float(F('1069.75') / (1 + high)), 4) == 984.5382
    checks.append('Eight solved exercises, rate-basis matching and project/sensitivity decisions independently recomputed')

    # Meaningful domain failures: undefined beta, broken pricing, incompatible shield/loan contracts.
    for section, key, value in [('moment_case', 'market_shocks', ['0'] * 4),
                                ('moment_case', 'probabilities', ['1/2'] * 4),
                                ('one_period', 'expected_unlevered_cash', '1000'),
                                ('one_period', 'fully_usable_current_deduction', False),
                                ('one_period', 'debt_return', '.08'),
                                ('no_tax_comparable', 'target_debt_fraction', '1'),
                                ('finite_apv', 'debt_balances', ['60', '40', '20', '20']),
                                ('finite_apv', 'tax_use', 'unknown')]:
        invalid = deepcopy(data)
        invalid[section][key] = value
        try:
            lab.compute(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid contract was accepted: ' + key)
    html = (ROOT / 'content/chapters/v08-c04.html').read_text()
    fragment = Fragment()
    fragment.feed(html)
    assert not fragment.stack and len(fragment.ids) == len(set(fragment.ids))
    assert (fragment.worked, fragment.exercises, fragment.solutions) == (4, 8, 8)
    assert 'Teach-back benchmark' in html and 'Delayed-check answer' in html
    sources = json.loads((ROOT / 'content/reviews/v08-c04-sources.json').read_text())
    assert {s['id'] for s in sources} == {link.split('#')[1] for link in fragment.links if link.startswith('sources.html#')}
    for link in fragment.links:
        if link.startswith('v08-c04-'):
            assert (PROJECT.parent / link).is_file(), link
    expected_json = lab.serializable(result)
    assert json.loads(PROJECT.with_name('v08-c04-output.json').read_text()) == expected_json
    with tempfile.TemporaryDirectory(prefix='v08-c04-') as folder:
        cli = subprocess.run([sys.executable, str(PROJECT)], cwd=folder, capture_output=True, text=True, check=True)
    assert not cli.stderr and json.loads(cli.stdout) == expected_json
    checks.append('Eight meaningful contract failures, complete HTML/source/asset structure and portable strict JSON output')
    return dict(chapter='v08-c04', status='passed', checks=checks,
                limitations=['Exact fictional contracts do not validate real market/tax estimates or credit access.',
                             'CAPM is introduced conditionally; general equilibrium and state-price foundations are later topics.',
                             'Visual/mobile/print UI QA remains pending.'])


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
