#!/usr/bin/env python3
"""Independent exact contracts, policy enumeration and solution checks for c08."""
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects/v08-c08-analysis.py'


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids = [], []
        self.examples = self.exercises = self.solutions = 0
        self.mode = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'worked' in a.get('class', '').split():
            self.examples += 1
        if tag == 'ol' and a.get('class') == 'exercises':
            self.mode = 'exercises'
        if tag == 'details' and a.get('class') == 'solutions':
            self.mode = 'solutions'
        if tag == 'li' and self.mode:
            setattr(self, self.mode, getattr(self, self.mode) + 1)
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack.pop() == tag, 'Unbalanced chapter HTML: ' + tag
        if (tag == 'ol' and self.mode == 'exercises') or (tag == 'details' and self.mode == 'solutions'):
            self.mode = None


def check():
    spec = importlib.util.spec_from_file_location('v08_c08_lab', PROJECT)
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    data = json.loads(PROJECT.with_name('v08-c08-inputs.json').read_text())
    result = lab.compute(data)
    checks = []

    # Direct state prices and separately constructed holdings price every payoff.
    prices = [F(4, 9), F(32, 63)]
    assert sum(prices) == F(20, 21)
    assert sum(pi * x for pi, x in zip(prices, [145, 70])) == 100
    c = sum(pi * x for pi, x in zip(prices, [55, 0]))
    delta, borrowing = F(11, 15), F(440, 9)
    assert [delta*x - F('1.05')*borrowing for x in [145,70]] == [55, 0]
    assert c == delta*100-borrowing == F(220, 9) == result['delay']['value']
    assert result['delay']['pricing_up'] == F(7, 15)
    assert result['delay']['option_expected_return'] == F('0.35')
    assert result['delay']['underlying_expected_return'] == F('0.15')
    assert result['delay']['interim_receipt_switch'] == F(91, 6)
    assert result['delay']['immediate_npv_with_receipt'] == F(610, 21)
    changed = deepcopy(data)
    changed['delay']['physical_up'] = '0.2'
    assert lab.compute(changed)['delay']['value'] == c
    checks.append('State-price certificate, exact replication, physical-return separation and lost-interim-cash threshold')

    # Enumerate all nine state-contingent feasible action policies independently.
    values = [[F(120), F(145), F(65)], [F(40), F(17), F(65)]]
    policy_values = [(F(2,5)*values[0][a]+F(3,5)*values[1][b])/F('1.05')
                     for a, b in itertools.product(range(3), repeat=2)]
    operations = result['operations']
    assert max(policy_values) == F(1940,21) == operations['flexible_value']
    assert operations['flexible_npv'] == F(470,21)
    assert operations['base_npv'] == -F(10,7)
    assert operations['flexibility_gain'] == F(500,21)
    assert [row['action'] for row in operations['states']] == ['expand', 'abandon']
    changed = deepcopy(data)
    changed['operations']['expansion_cash_available'] = '30'
    constrained = lab.compute(changed)['operations']
    assert constrained['flexible_value'] == F(580,7)
    assert constrained['flexible_npv']-3 == F(69,7)
    changed = deepcopy(data)
    changed['operations']['states'][1].update(expansion_gross='50', expansion_cost='20')
    interaction = lab.compute(changed)['operations']
    assert interaction['states'][1]['optimal'] == 70
    assert interaction['expansion_only_gain']+interaction['abandonment_only_gain']-interaction['flexibility_gain'] == F(100,7)
    checks.append('All feasible operating policies, funding restriction and mutually exclusive option interaction')

    # Expand each policy as dated net cash, rather than using continuation helpers.
    staged = -12-F(3,5)*30/F('1.1')+F(3,5)*80/F('1.1')**2
    forced = -12-30/F('1.1')+F(3,5)*80/F('1.1')**2
    assert staged == F(1368,121) == result['stage']['staged_npv']
    assert forced == F(48,121) == result['stage']['forced_npv']
    assert staged-forced == F(120,11) == result['stage']['stopping_gain']
    assert result['stage']['minimum_validation_probability'] == F(363,1175)
    changed = deepcopy(data)
    changed['stage']['validation_probability'] = '363/1175'
    assert lab.compute(changed)['stage']['staged_npv'] == 0
    checks.append('Independent dated-cash stage and mandatory-completion comparison, exact pilot threshold')

    # Joint physical probabilities: rows are signals, columns good/bad true demand.
    joint = [[F(3,10), F(3,20)], [F(1,10), F(9,20)]]
    net = [F(940,11), -F(260,11)]
    policy_values = []
    for policy in itertools.product([0,1], repeat=2):
        policy_values.append(sum(policy[y]*joint[y][s]*net[s]
                                 for y in range(2) for s in range(2))/F('1.1'))
    informed = max(policy_values)
    base = max(F(0), sum(sum(row[s] for row in joint)*net[s] for s in range(2)))/F('1.1')
    perfect = sum(sum(row[s] for row in joint)*max(F(0),net[s]) for s in range(2))/F('1.1')
    info = result['information']
    assert informed == F(2430,121) == info['gross_report_value']
    assert base == F(200,11) == info['no_report_value']
    assert perfect-base == F(1560,121) == info['evpi']
    assert informed-base == F(230,121) == info['evsi']
    assert 0 < info['evsi'] < info['evpi']
    assert info['posterior_threshold'] == F(13,60)
    assert [row['posterior_good'] for row in info['signals']] == [F(2,3), F(2,11)]
    assert info['signals'][1]['launch_npv'] == -F(460,121)
    assert info['buy_report'] is True and info['net_report_value'] == F(2309,121)
    for likelihood in ('0.5','0','1'):
        changed = deepcopy(data)
        changed['information'].update(positive_if_good=likelihood, positive_if_bad=likelihood)
        row = lab.compute(changed)['information']
        assert row['evsi'] == 0 and row['buy_report'] is False
    changed = deepcopy(data)
    changed['information']['report_fee_now'] = '3'
    assert lab.compute(changed)['information']['buy_report'] is False
    checks.append('Four signal policies from joint probabilities, Bayes decisions, EVSI/EVPI, fees and unreachable signals')

    # Independent exercise anchors not copied from a computed reference output.
    q1 = (F('1.05')*80-60)/(120-60)
    c1 = q1*30/F('1.05')
    assert q1 == F(2,5) and c1 == F(80,7)
    assert F(15)/c1-1 == F(5,16)
    assert 100+10/F('1.05')-90 == F(410,21)
    assert c-4 == F(184,9)
    assert max(40,40+50-20,65) == 70
    ex5_staged = -15-F(1,2)*40/F('1.1')+F(1,2)*90/F('1.1')**2
    ex5_forced = -15-40/F('1.1')+F(1,2)*90/F('1.1')**2
    assert ex5_staged == F(485,121) and ex5_forced == -F(1715,121)
    assert 15*F('1.1')/(90/F('1.1')-40) == F(363,920)
    assert F('0.3')*55/F('1.05') == F(110,7)
    assert F('0.7')*55/F('1.05') == F(110,3)
    assert max(policy_values) != perfect  # Imperfect report does not reveal true demand.
    checks.append('All numerical exercise anchors, information timing, non-identification and rights-fee comparisons')

    for section, key, value in [('delay','spot','200'), ('delay','physical_up','0'),
                                ('delay','physical_up','1'), ('information','good_prior','1.2'),
                                ('operations','valuation','market_value'), ('stage','rate','-1')]:
        changed = deepcopy(data)
        changed[section][key] = value
        try:
            lab.compute(changed)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid model accepted: ' + section + '/' + key)
    fragment = Fragment()
    text = (ROOT/'content/chapters/v08-c08.html').read_text()
    fragment.feed(text)
    assert not fragment.stack and len(fragment.ids) == len(set(fragment.ids))
    assert (fragment.examples, fragment.exercises, fragment.solutions) == (4,8,8)
    assert 'Teach-back' in text and 'Delayed check' in text
    reference = json.loads(PROJECT.with_name('v08-c08-output.json').read_text())
    assert reference == lab.serial(result)
    cli = subprocess.run([sys.executable,str(PROJECT)], capture_output=True,text=True,check=True)
    assert json.loads(cli.stdout) == reference
    checks.append('Meaningful invalid-model guards, four worked cases/eight full solutions, exact reference and standalone CLI')
    return {'status':'passed','checks':checks,'worked_examples':4,'exercises':8,
            'limitations':'Fictional contracts; owner decision criterion is explicit, not verified market pricing; no visual UI review claimed.'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
