#!/usr/bin/env python3
"""Independent exact contract and instruction checks for v08-c05."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects/v08-c05-analysis.py'


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links = [], [], []
        self.worked = self.exercises = self.solutions = 0
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
        assert self.stack and self.stack.pop() == tag, 'Unbalanced fragment: ' + tag
        if (tag == 'ol' and self.mode == 'exercises') or (tag == 'details' and self.mode == 'solutions'):
            self.mode = None


def check():
    out, err = io.StringIO(), io.StringIO()
    spec = importlib.util.spec_from_file_location('v08_c05_lab', PROJECT)
    lab = importlib.util.module_from_spec(spec)
    with redirect_stdout(out), redirect_stderr(err):
        spec.loader.exec_module(lab)
    assert not out.getvalue() and not err.getvalue(), 'Lab import must be quiet.'
    data = json.loads(PROJECT.with_name('v08-c05-inputs.json').read_text())
    r = lab.compute(data)
    checks = []

    # Independent state prices from a replicating portfolio in the two primitive claims.
    pi = [F(4, 7), F(8, 21)]
    assert min(pi) > 0 and sum(pi) == F(20, 21)
    value = lambda cash: sum(a * b for a, b in zip(pi, cash))
    assert value([84, 168]) == r['unlevered_value'] == 112
    assert r['unlevered_expected_return'] == F(1, 8)
    expected = [([63, 63], [21, 105], 60, 52, F(1, 20), F(11, 52)),
                ([84, 105], [0, 63], 88, 24, F(13, 176), F(5, 16))]
    for row, (dc, ec, d, e, rd, re) in zip(r['mm'], expected):
        assert row['debt_cash'] == dc and row['equity_cash'] == ec
        assert value(dc) == row['debt_value'] == d
        assert value(ec) == row['equity_value'] == e
        assert d + e == row['total_value'] == 112
        assert row['debt_expected_return'] == rd and row['equity_expected_return'] == re
        assert row['equity_return_from_leverage'] == re
        assert row['weighted_return'] == (d * rd + e * re) / 112 == F(1, 8)
        # Independently replicate debt with a units of the operating asset and a bond.
        a = F(dc[1] - dc[0], 84)
        b = dc[0] - 84 * a
        assert a * 112 + b / F('1.05') == d
    assert r['mm'][1]['debt_promised_yield'] == F(17, 88) != F(13, 176)
    checks.append('Exact MM payoff/replication proof anchors and expected-return leverage identities')

    # Read cash directly from the hypothetical contract, without calling model helpers.
    policies = {row['name']: row for row in r['financing_policies']}
    plain, moderate, high = (policies[k] for k in ('no_debt', 'moderate', 'high'))
    assert plain['owner_wealth'] == 112
    assert moderate['debt_value'] == 60 and moderate['promised_interest'] == 3
    assert moderate['shield_cash'] == [F(3, 4)] * 2
    assert moderate['shield_value'] == F(5, 7) and moderate['distress_value'] == 0
    assert moderate['owner_wealth'] == F(3149, 28)
    assert high['debt_cash'] == [69, F(531, 4)] and high['debt_value'] == 90
    assert high['promised_interest'] == F(171, 4)
    assert high['shield_cash'] == [0, F(171, 16)]
    assert high['equity_cash'] == [0, F(735, 16)]
    assert high['shield_value'] == F(57, 14) and high['distress_value'] == F(60, 7)
    assert high['equity_value'] == F(35, 2) and high['total_value'] == F(215, 2)
    assert high['owner_wealth'] == F(213, 2)
    for row in policies.values():
        assert row['total_value'] == 112 + row['shield_value'] - row['distress_value']
        assert row['debt_value'] + row['equity_value'] - row['issue_fee'] == row['owner_wealth']
    assert r['best_menu_policies'] == ['moderate']
    changed = deepcopy(data)
    changed['pricing_case']['tax_rate'] = '0'
    no_tax = lab.compute(changed)
    assert [v['owner_wealth'] for v in no_tax['financing_policies']] == [112, F(447, 4), F(717, 7)]
    assert [v['debt_value'] for v in no_tax['financing_policies']] == [0, 60, 90]
    assert no_tax['best_menu_policies'] == ['no_debt']
    changed = deepcopy(data)
    changed['pricing_case']['distress_cost'] = '0'
    no_cost = lab.compute(changed)
    zero_loss_high = no_cost['financing_policies'][2]
    assert zero_loss_high['debt_value'] == F(690, 7)
    assert zero_loss_high['promised_interest'] == F(957, 28)
    assert zero_loss_high['shield_value'] == F(319, 98)
    assert zero_loss_high['owner_wealth'] == F(11197, 98)
    assert no_cost['best_menu_policies'] == ['high']
    checks.append('Finite refund/default sequencing, rational debt prices, resource losses and two decision-changing variations')

    # Solve creditor break-even and shareholder incentives independently for the new issue.
    a = r['risk_shifting']
    assert a['old_claims']['prudent']['debt_value'] == 80
    assert a['old_claims']['prudent']['equity_value'] == 20
    assert a['old_claims']['gamble']['debt_value'] == 60
    assert a['old_claims']['gamble']['equity_value'] == 35
    assert (a['debt_value_change'], a['equity_value_change'], a['net_value_change']) == (-20, 15, -5)
    assert len(a['new_debt_equilibria']) == 1
    eq = a['new_debt_equilibria'][0]
    face = 2 * 80 - 40
    assert 40 < face < 150 and F(40 + face, 2) == 80
    assert eq['policy'] == 'gamble' and eq['face'] == face
    assert eq['all_choice_equity_values'] == {'prudent': 0, 'gamble': 15}
    assert eq['owner_wealth'] == 95 and a['covenant_owner_wealth'] == 98
    changed = deepcopy(data)
    changed['risk_shifting']['covenant_fee'] = '6'
    assert lab.compute(changed)['risk_shifting']['covenant_owner_wealth'] == 94 < eq['owner_wealth']
    checks.append('Old-claim gain/loss reconciliation, rational new-loan terms and subsequent policy incentives')

    h = r['overhang']
    assert h['before']['debt_value'] == 65 and h['before']['equity_value'] == 15
    assert h['after']['debt_value'] == 73 and h['after']['equity_value'] == 23
    assert h['project_npv'] == 6 and h['equity_funded_npv'] == -2
    assert h['mutually_acceptable_contribution_min'] == 2 and h['mutually_acceptable_contribution_max'] == 8
    assert h['repaired_equity_gain'] == 2 and h['repaired_creditor_gain'] == 4
    assert h['repair_individually_acceptable']
    assert h['junior_face'] == 20 and h['junior_price'] == 10
    assert h['equity_after_junior'] == F(46 - 20, 2) == 13
    assert h['consented_senior_price'] == 10
    assert h['old_debt_after_senior'] == F(46 + 90, 2) == 68
    assert h['equity_after_senior'] == F(136 - 10 - 90, 2) == 18
    assert (68 - 65) + (18 - 15) == 6
    for contribution in ('1', '9'):
        changed = deepcopy(data)
        changed['overhang']['creditor_contribution'] = contribution
        trial = lab.compute(changed)['overhang']
        assert not trial['repair_individually_acceptable']
        assert trial['repaired_equity_gain'] + trial['repaired_creditor_gain'] == 6
    checks.append('Debt-overhang funding incentives, bilateral participation and junior/consented-senior pricing')

    i = r['information']
    assert i['pooling_fraction'] == F(5, 36)
    assert i['pooling_old_owner_gains'] == {'low': F(86, 9), 'high': F(-14, 9)}
    assert not i['pooling_incentive_compatible']
    assert i['low_only_fraction'] == F(5, 26)
    assert i['low_old_owner_value'] == 84 and i['high_old_owner_value_without_issue'] == 160
    assert i['high_deviation_value'] == F(1932, 13) < 160
    assert F(5, 26) * 104 == 20 and i['low_only_equilibrium_valid']
    assert i['expected_project_npv_lost'] == 2
    assert i['safe_debt_price'] == i['safe_debt_face'] == 20
    assert i['safe_debt_old_owner_values'] == {'low': 84, 'high': 164}
    checks.append('Information-sensitive issue prices, endogenous issuing types and conditional belief/incentive consistency')

    # Independent arithmetic for every exercise; qualitative proof/criteria are author-audited.
    assert 60 + 55 - 112 == 3 and (84 - 63 - 21, 168 - 63 - 105) == (0, 0)
    vu2, d2, e2 = value([63, 147]), value([63, 84]), value([0, 63])
    assert (vu2, d2, e2) == (92, 68, 24)
    ru2, rd2, re2 = F(105, 92) - 1, F(147, 136) - 1, F(63, 48) - 1
    assert (ru2, rd2, re2) == (F(13, 92), F(11, 136), F(5, 16))
    assert ru2 + (ru2 - rd2) * d2 / e2 == re2 and F(84, 68) - 1 == F(4, 17)
    d3 = (F('.7') * 50 + F('.3') * 100) / F('1.05')
    interest3 = 100 - d3
    shield3 = F('.3') * F('.2') * interest3 / F('1.05')
    loss3 = F('.7') * 10 / F('1.05')
    assert (d3, interest3, shield3, loss3) == (F(1300, 21), F(800, 21), F(320, 147), F(20, 3))
    assert (F('.7') * 60 + F('.3') * 140) / F('1.05') == 80
    assert 80 + shield3 - loss3 == F(3700, 49)
    assert 80 + shield3 - loss3 - F('.5') == F(7351, 98)
    for cash, debt, equity, total in [([80, 120, 160], F('87.5'), F('32.5'), 120),
                                     ([20, 100, 220], F('72.5'), F('37.5'), 110)]:
        assert F(cash[0] + 2 * cash[1] + cash[2], 4) == total
        assert F(min(cash[0], 90) + 2 * min(cash[1], 90) + min(cash[2], 90), 4) == debt
        assert total - debt == equity
    assert F(20 + 2 * 100 + 130, 4) == F('87.5')
    assert F(220 - 130, 4) == F('22.5') > F(160 - 130, 4) == F('7.5')
    assert 24 - 15 == 9 and F(44 + 100, 2) - F(20 + 100, 2) == 12
    assert F(174 - 100, 2) - F(150 - 100, 2) - 15 == -3
    assert (12 - 6, 12 - (15 - 6)) == (6, 3)
    assert F(30, 2) == 15 and F(174 - 100 - 30, 2) == 22 < 25
    mean_type = F('.6') * 100 + F('.4') * 200
    pool = F(30) / (mean_type + 36)
    low_only = F(30, 136)
    assert pool == F(15, 88)
    assert (1 - pool) * 136 == F(1241, 11)
    assert (1 - pool) * 236 == F(4307, 22) < 200
    assert low_only == F(15, 68) and (1 - low_only) * 136 == 106
    assert (1 - low_only) * 236 == F(3127, 17) < 200
    assert F('.4') * 6 == F('2.4') and (136 - 30, 236 - 30) == (106, 206)
    assert 100 - 2 - (95 + 8 * F(1, 4)) == 1
    assert 100 - 2 - (95 + 8 * F(1, 2)) == -1 and F(98 - 95, 8) == F(3, 8)
    assert 200 + 10 - 2 - 1 - 1 == 206 and 200 + 18 - 7 - 6 - 2 == 203
    assert (206 - 78, 203 - 74) == (128, 129)
    assert (128 - 120 - (80 - 78), 129 - 120 - (80 - 74)) == (6, 3)
    # The answered delayed check is a distinct project, not just copied output.
    assert 18 - 12 == 6 and 18 - 9 - 12 == -3 and (12 - (18 - 9), 9) == (3, 9)
    checks.append('All eight original exercise calculations and answered retention transfer independently recomputed')

    failures = [
        (['units'], 'CU'),
        (['pricing_case', 'valuation_weights'], ['1/2', '1/4']),
        (['pricing_case', 'physical_probabilities'], ['0', '1']),
        (['pricing_case', 'risk_free_rate'], '-0.05'),
        (['pricing_case', 'tax_rate'], '1'),
        (['pricing_case', 'distress_cost'], '85'),
        (['pricing_case', 'tax_rule'], 'Immediate usable refund in default'),
        (['agency_pricing', 'risk_neutral'], False),
        (['risk_shifting', 'new_funding'], '101'),
        (['overhang', 'creditor_contribution'], '11'),
        (['information', 'high_type_prior'], '1')
    ]
    for path, value_bad in failures:
        changed = deepcopy(data)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value_bad
        try:
            lab.compute(changed)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid contract accepted: ' + '.'.join(path))
    checks.append('Eleven consequential probability, tax/default, funding, unit and information-domain failures rejected')

    html = (ROOT / 'content/chapters/v08-c05.html').read_text()
    fragment = Fragment()
    fragment.feed(html)
    assert not fragment.stack and len(fragment.ids) == len(set(fragment.ids))
    assert (fragment.worked, fragment.exercises, fragment.solutions) == (5, 8, 8)
    assert 'Teach-back benchmark' in html and 'Delayed-check answer' in html
    sources = json.loads((ROOT / 'content/reviews/v08-c05-sources.json').read_text())
    assert {s['id'] for s in sources} == {link.split('#')[1] for link in fragment.links if link.startswith('sources.html#')}
    for link in fragment.links:
        if link.startswith('v08-c05-'):
            assert (PROJECT.parent / link).is_file(), link
    for line in html.splitlines():
        assert line.rstrip() == line
    expected_json = lab.serializable(r)
    assert json.loads(PROJECT.with_name('v08-c05-output.json').read_text()) == expected_json
    with tempfile.TemporaryDirectory(prefix='v08-c05-') as folder:
        destination = Path(folder)
        shutil.copy2(PROJECT, destination / PROJECT.name)
        shutil.copy2(PROJECT.with_name('v08-c05-inputs.json'), destination / 'v08-c05-inputs.json')
        cli = subprocess.run([sys.executable, str(destination / PROJECT.name)],
                             cwd=destination.parent, capture_output=True, text=True, check=True)
    assert not cli.stderr and json.loads(cli.stdout) == expected_json
    checks.append('Complete HTML/solutions/source/assets, stored exact-contract output and isolated portable CLI')
    report = dict(chapter='v08-c05', status='passed', checks=checks,
                  limitations=['Original hypothetical contracts and explicit valuation laws, not empirical estimates or legal advice.',
                               'Checks do not search all financing policies or all information equilibria.',
                               'Visual/mobile/print UI QA remains pending.'])
    json.dumps(report, allow_nan=False)
    return report


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
