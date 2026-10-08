"""Independent Moraine cash, attribution, factor and selection checks; quiet JSON."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
from itertools import combinations
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'content/projects'


def prod(values):
    result = F(1)
    for value in values:
        result *= value
    return result


def check():
    comparisons = rejected_count = 0
    groups = []

    def eq(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise AssertionError(f'{label}: {actual!r} != {expected!r}')

    def yes(condition, label):
        eq(bool(condition), True, label)

    def close(actual, expected, label, tolerance=1e-12):
        yes(math.isfinite(actual) and abs(actual - expected) <= tolerance, label)

    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        spec = importlib.util.spec_from_file_location('moraine_benchmark', PROJECT / 'v09-c08-analysis.py')
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        data = json.loads((PROJECT / 'v09-c08-inputs.json').read_text())
        out = model.run(data)
    eq(capture.getvalue(), '', 'quiet import and run')
    json.dumps(out, allow_nan=False)

    # Independent orthogonal contrasts reconstruct the returns, rather than OLS.
    market_sign = [-1] * 4 + [1] * 4
    style_sign = [-1, -1, 1, 1] * 2
    residual_sign = [-1, 1] * 4
    m = [F(5 + 20 * s, 1000) for s in market_sign]
    z = [F(4 + 10 * s, 1000) for s in style_sign]
    e = [F(3 * s, 1000) for s in residual_sign]
    gross = [F(3, 1000) + F(6, 5) * a + b / 2 + c for a, b, c in zip(m, z, e)]
    net = [x - F(1, 500) for x in gross]
    bench = [F(1, 500) + x for x in m]
    gross_a, net_a = [[x - y for x, y in zip(series, bench)] for series in (gross, net)]
    for key, values in [('gross', gross), ('net', net), ('benchmark', bench), ('gross_active', gross_a), ('net_active', net_a)]:
        eq([F(x) for x in out['monthly_returns'][key]], values, 'contrast reconstruction ' + key)
    eq([F(x) for x in data['monthly']['market_excess']], m, 'M construction')
    eq([F(x) for x in data['monthly']['style_factor']], z, 'Z construction')
    for left, right in combinations((market_sign, style_sign, residual_sign), 2):
        eq(sum(a * b for a, b in zip(left, right)), 0, 'orthogonal contrast columns')
    active_variance = F(8, 7) * (F(4, 1000) ** 2 + F(5, 1000) ** 2 + F(3, 1000) ** 2)
    eq(active_variance, F(1, 17500), 'independent active variance')
    for name, average in [('gross_information_ratio', F(1, 250)), ('net_information_ratio', F(1, 500))]:
        stats = out[name]
        eq(F(stats['mean']), average, name + ' mean')
        eq(F(stats['sample_variance_n_minus_1']), active_variance, name + ' variance')
        close(stats['sample_sd_approx'], math.sqrt(float(active_variance)), name + ' sd')
        close(stats['ratio_approx'], float(average) / math.sqrt(float(active_variance)), name + ' ratio')
        eq(F(stats['conditional_annual_arithmetic_mean']), 12 * average, 'conditional annual mean')
        eq(F(stats['conditional_annual_variance']), 12 * active_variance, 'conditional annual variance')
        close(stats['conditional_annual_ratio_approx'], math.sqrt(12) * stats['ratio_approx'], 'conditional annual ratio')
        close(stats['classic_mean_t_approx'], math.sqrt(8) * stats['ratio_approx'], 'conditional mean statistic')
    eq(F(out['net_sharpe_ratio']['mean']), F(7, 1000), 'Sharpe excess mean')
    eq(F(out['net_sharpe_ratio']['sample_variance_n_minus_1']), F(61, 87500), 'Sharpe excess variance')
    eq(F(out['benchmark_sample_variance']), F(2, 4375), 'benchmark variance')
    eq(F(out['active_benchmark_sample_covariance']), F(2, 21875), 'active benchmark covariance')
    eq(F(out['net_fund_sample_variance']), F(2, 4375) + active_variance + 2 * F(2, 21875), 'full variance identity')
    groups.append('Independent contrast returns, means, n-1 risks and conditional horizon ratios')

    for name, alpha in [('gross_two_factor', F(1, 1000)), ('net_two_factor', F(-1, 1000))]:
        fit = out[name]
        eq(F(fit['intercept']), alpha, name + ' alpha')
        eq([F(x) for x in fit['loadings']], [F(6, 5), F(1, 2)], name + ' slopes')
        eq([F(x) for x in fit['residuals']], e, name + ' residuals')
        eq(F(fit['residual_sum_squares']), F(9, 125000), name + ' SSE')
        eq(fit['residual_degrees_freedom'], 5, name + ' df')
        eq(F(fit['residual_variance_divisor_n_minus_k']), F(9, 625000), name + ' residual variance')
        # Orthogonal centered regressors give this independent intercept variance.
        alpha_variance = F(9, 625000) * (F(1, 8) + F(1, 200)**2 / F(2, 625) + F(1, 250)**2 / F(1, 1250))
        eq(F(fit['classic_alpha_variance']), alpha_variance, name + ' intercept variance')
        close(fit['classic_alpha_se_approx'], math.sqrt(float(alpha_variance)), name + ' classical se')
        close(fit['classic_alpha_t_approx'], float(alpha) / math.sqrt(float(alpha_variance)), name + ' conditional t')
        eq(sum(e), 0, 'intercept normal equation')
        eq(sum(x * r for x, r in zip(m, e)), 0, 'market normal equation')
        eq(sum(x * r for x, r in zip(z, e)), 0, 'style normal equation')
    eq(F(out['net_market_only']['intercept']), F(1, 1000), 'omitted style intercept')
    eq([F(x) for x in out['net_market_only']['loadings']], [F(6, 5)], 'omitted orthogonal slope')
    eq(F(out['net_market_only']['residual_sum_squares']), 8 * (F(5, 1000)**2 + F(3, 1000)**2), 'omitted factor residual variance')
    fee_edit = deepcopy(data)
    fee_edit['monthly']['fee_rate'] = '0.003'
    higher_fee = model.run(fee_edit)
    eq(F(higher_fee['net_information_ratio']['mean']), F(1, 1000), 'exercise 3 fee active mean')
    eq(F(higher_fee['net_two_factor']['intercept']), F(-1, 500), 'exercise 3 fee alpha')
    eq(F(higher_fee['net_market_only']['intercept']), 0, 'exercise 3 fee omitted alpha')
    eq(higher_fee['net_two_factor']['residuals'], out['net_two_factor']['residuals'], 'constant fee residual invariance')
    eq(higher_fee['net_information_ratio']['sample_variance_n_minus_1'], out['net_information_ratio']['sample_variance_n_minus_1'], 'constant fee TE invariance')
    close(higher_fee['net_information_ratio']['ratio_approx'], float(F(1, 1000)) / math.sqrt(float(active_variance)), 'exercise 3 fee IR')
    groups.append('Orthogonal-regressor coefficient/uncertainty oracle, omitted factor and constant-fee intervention')

    # Independent contribution lots avoid copying the benchmark's NAV recurrence.
    flows = [F(0), F(0), F(0), F(500), F(0), F(0), F(0), F(0)]
    def lots(t, returns, contributions):
        return F(1000) * prod(1 + x for x in returns[:t]) + sum(
            c * prod(1 + x for x in returns[k:t]) for k, c in enumerate(contributions[:t], 1))
    for label, returns, gross_series, fee in [('fund_ledger', net, gross, F(1, 500)), ('matched_benchmark_ledger', bench, bench, F(0))]:
        report = out[label]
        for t, row in enumerate(report['rows'], 1):
            begin = lots(t - 1, returns, flows)
            expected_end = lots(t, returns, flows)
            eq(F(row['beginning_nav']), begin, label + ' independent lot opening')
            eq(F(row['gross_profit']), begin * gross_series[t - 1], label + ' profit')
            eq(F(row['fee_cash']), begin * fee, label + ' fee')
            eq(F(row['end_contribution']), flows[t - 1], label + ' dated contribution')
            eq(F(row['after_return_and_fee']), expected_end - flows[t - 1], label + ' pre-flow')
            eq(F(row['next_nav']), expected_end, label + ' lot wealth closure')
        terminal = lots(8, returns, flows)
        eq(F(report['terminal_nav']), terminal, label + ' final')
        eq(F(report['time_weighted_return']), prod(1 + r for r in returns) - 1, label + ' TWR')
        eq(F(report['profit_after_external_contributions']), terminal - 1500, label + ' investment profit')
        # Solve the baseline's quadratic in G^4, independently of model bisection.
        root4 = (-500 + math.sqrt(500**2 + 4000 * float(terminal))) / 2000
        g = root4 ** 0.25
        close(report['monthly_money_weighted_return_approx'], g - 1, label + ' independent quadratic MWR')
        close(report['money_weighted_terminal_residual_cu_approx'], 0, label + ' root residual', 1e-8)
    eq(F(out['matched_flow_terminal_wealth_difference']), lots(8, net, flows) - lots(8, bench, flows), 'matched opportunity wealth')
    eq(F(out['fee_total_cu']), sum(lots(t, net, flows) / 500 for t in range(8)), 'all dated fee cash')
    eq(F(out['fund_ledger']['rows'][3]['fee_cash']), F(947905917, 1000000) / 500, 'flow is after month 4 fee')
    changed_flow = deepcopy(data)
    changed_flow['monthly']['end_contributions'][3] = '0'
    changed_flow['monthly']['end_contributions'][2] = '500'
    moved = model.run(changed_flow)
    new_flows = flows[:]
    new_flows[2], new_flows[3] = F(500), F(0)
    eq(moved['fund_ledger']['time_weighted_return'], out['fund_ledger']['time_weighted_return'], 'flow date does not alter TWR')
    eq(F(moved['fund_ledger']['terminal_nav']), lots(8, net, new_flows), 'edited fund date applied')
    eq(F(moved['matched_benchmark_ledger']['terminal_nav']), lots(8, bench, new_flows), 'edited benchmark date applied')
    eq(F(moved['fund_ledger']['rows'][3]['fee_cash']) - F(out['fund_ledger']['rows'][3]['fee_cash']), F(1), 'earlier contribution pays month 4 fee')
    g = 1 + moved['fund_ledger']['monthly_money_weighted_return_approx']
    close(1000*g**8 + 500*g**5, float(lots(8, net, new_flows)), 'edited MWR date applied', 1e-8)
    groups.append('All dated cash/fee rows from independent contribution lots, quadratic MWR and changed flow timestamp')

    a = out['attribution']
    expected_effects = [[F(1, 200), F(1, 125), F(3, 1000)], [F(1, 200), F(-1, 500), F(1, 500)]]
    expected_holdings = [([F(70), F(30)], [F(77), F(153, 5)], [F(60), F(40)], [F(324, 5), F(206, 5)]),
                         ([F(269, 5)] * 2, [F(26093, 500), F(6994, 125)], [F(318, 5), F(212, 5)], [F(7791, 125), F(5459, 125)])]
    for i, period in enumerate(a['periods']):
        raw = data['attribution']['periods'][i]
        w, W, r, b = [[F(x) for x in raw[key]] for key in ('portfolio_weights', 'benchmark_weights', 'portfolio_sector_returns', 'benchmark_sector_returns')]
        actual = sum(x*y for x, y in zip(w, r))
        policy = sum(x*y for x, y in zip(W, b))
        timing_only = sum(x*y for x, y in zip(w, b))
        selection_only = sum(x*y for x, y in zip(W, r))
        corner_effects = [timing_only-policy, selection_only-policy, actual-timing_only-selection_only+policy]
        eq(corner_effects, expected_effects[i], 'independent four-corner attribution')
        for key, amount in zip(('allocation', 'selection', 'interaction'), corner_effects):
            eq(F(period[key]), amount, 'aggregate ' + key)
        eq(F(period['active_return']), sum(corner_effects), 'all effects close active return')
        for field, holdings in zip(('portfolio_beginning_holding', 'portfolio_end_holding', 'benchmark_beginning_holding', 'benchmark_end_holding'), expected_holdings[i]):
            eq([F(row[field]) for row in period['sectors']], holdings, 'currency holding ledger ' + field)
        eq(sum(F(row['portfolio_end_holding']) for row in period['sectors']), F(period['portfolio_end_wealth']), 'sector portfolio wealth sum')
        eq(sum(F(row['benchmark_end_holding']) for row in period['sectors']), F(period['benchmark_end_wealth']), 'sector benchmark wealth sum')
    eq(F(a['compound_wealth_gap_per_initial_cu']), F(1069, 50000), 'independent terminal wealth gap')
    eq(F(a['relative_terminal_wealth_return']), F(1069, 53000), 'relative wealth denominator')
    eq([F(a['linked_effects'][k]) for k in ('allocation', 'selection', 'interaction')], [F(519, 50000), F(731, 125000), F(161, 31250)], 'linked effects')
    equal_weights = deepcopy(data)
    equal_weights['attribution']['periods'][0]['portfolio_weights'] = ['0.6', '0.4']
    equal = model.run(equal_weights)['attribution']['periods'][0]
    eq([F(equal[k]) for k in ('portfolio_return', 'allocation', 'selection', 'interaction')], [F(17, 250), F(0), F(1, 125), F(0)], 'exercise 4 equal weights')
    reverse = deepcopy(data)
    reverse['attribution']['periods'].reverse()
    rev = model.run(reverse)['attribution']
    eq([F(rev['linked_effects'][k]) for k in ('allocation', 'selection', 'interaction')], [F(413, 40000), F(37, 6250), F(1027, 200000)], 'exercise 7 reversed links')
    eq(rev['compound_wealth_gap_per_initial_cu'], a['compound_wealth_gap_per_initial_cu'], 'order-invariant total and different components')
    eq((1+F(2, 125))*(1+F(1, 200))-1, F(527, 25000), 'compounded active returns are not wealth gap')
    groups.append('Currency holdings, four-counterfactual attribution, exact chronological and reversed links')

    p = out['fund_panel']
    eligible = [list('ABCD'), list('ABCDF'), list('ABCDEF'), list('ABDEF')]
    entries = [list('ABCD'), ['F'], ['E'], []]
    exits = [[], [], ['C'], ['F']]
    year_returns = [F(1, 16), F(7, 100), F(-1, 20), F(0)]
    survivor_means = [F(1, 60), F(1, 60), F(1, 20), F(1, 20)]
    for t, row in enumerate(p['years']):
        eq(row['opening_eligible_ids'], eligible[t], 'all opening funds including future exits')
        eq(row['opening_entries'], entries[t], 'entry date visible')
        eq(row['closing_exits'], exits[t], 'exit date visible')
        eq(F(row['equal_weight_return']), year_returns[t], 'all-available period return')
        eq(F(row['hindsight_survivor_mean']), survivor_means[t], 'filtered survivor return')
        eq(sorted(row['eligible_fund_net_returns']), eligible[t], 'complete per-period returns in output')
    eq(F(p['all_available_equal_weight_compound_return']), F(2561, 32000), 'all-available strategy growth')
    eq(F(p['hindsight_survivor_only_compound_return']), F(22329, 160000), 'hindsight growth')
    eq(p['ranking_ids'], list('ACBD'), 'initial cohort date-2 ranking')
    eq(p['selected_ids'], list('AC'), 'selection frozen before holdout')
    terminal = {'A': F(361, 4), 'B': F(2916, 25), 'C': F(50), 'D': F(2601, 25)}
    for row in p['initial_cohort_records']:
        eq(F(row['outcome_return']), terminal[row['id']] / 100 - 1, 'independent buy-hold terminal wealth')
    c = next(row for row in p['initial_cohort_records'] if row['id'] == 'C')
    eq([F(x) for x in c['outcome_returns_with_cash_after_exit']], [F(-1, 2), F(0)], 'liquidation once then cash')
    eq(F(p['selected_outcome_return']), (terminal['A']+terminal['C'])/200-1, 'selected wealth closure')
    eq(F(p['other_initial_cohort_outcome_return']), F(517, 5000), 'unselected cohort')
    eq(F(p['all_initial_cohort_outcome_return']), F(-3907, 40000), 'complete initial cohort')
    eq(F(p['selected_survivor_only_outcome_return']) - F(p['selected_outcome_return']), F(161, 800), 'survivor distortion')
    eq(p['top_overlap_count'], 0, 'no top-two persistence')
    possible = list(combinations('ABCD', 2))
    eq(F(sum(not (set(v)&set('AC')) for v in possible), len(possible)), F(1, 6), 'exercise 6 explicit exchangeable reference')
    edit = deepcopy(data)
    edit['panel']['funds'][2]['net_returns'][2] = '-0.20'
    repair = model.run(edit)['fund_panel']
    eq(F(repair['selected_outcome_return']), F(-119, 800), 'changed liquidation selected outcome')
    eq(F(repair['all_initial_cohort_outcome_return']), F(-907, 40000), 'changed liquidation full cohort')
    eq(F(repair['all_available_equal_weight_compound_return']), F(219, 1600), 'changed liquidation dynamic strategy')
    eq(repair['hindsight_survivor_only_compound_return'], p['hindsight_survivor_only_compound_return'], 'filter conceals changed liquidation')
    groups.append('All entries/exits, independent selection and liquidation ledgers, survivor distortion and terminal-loss edit')

    # Remaining exercises are reconstructed from their stated cash/variance contracts.
    passive, X, Y = F(400), F(200), F(400)
    profits = [passive*F(2, 25), X*F(7, 50), Y*F(1, 20)]
    eq(sum(profits), F(80), 'exercise 1 market wealth')
    eq((profits[1]+profits[2])/(X+Y), F(2, 25), 'exercise 1 gross active dollars')
    fees = [passive/F(1000), X/F(100), Y/F(200)]
    eq((profits[1]+profits[2]-fees[1]-fees[2])/(X+Y), F(11, 150), 'exercise 1 net active')
    eq((profits[0]-fees[0])/passive, F(79, 1000), 'exercise 1 net passive')
    eq(sum(profits)-sum(fees), F(378, 5), 'exercise 1 all fees reconcile')
    eq((F(7, 50)+F(1, 20))/2, F(19, 200), 'exercise 1 equal-manager distortion')
    observations = [F(-1, 100), F(0), F(1, 100), F(1, 50)]
    average = sum(observations)/4
    variance = sum((x-average)**2 for x in observations)/3
    eq((average, variance), (F(1, 200), F(1, 6000)), 'exercise 2 moments')
    eq(12*variance+2*11*variance/F(4), F(7, 2400), 'exercise 2 serial covariance risk')
    close(float(12*average)/math.sqrt(float(F(7, 2400))), 1.1109841197270618, 'exercise 2 serial ratio')
    pre_flow = 100 * (1+F(1, 10)-F(1, 100))
    final = (pre_flow+100)*(1-F(1, 10)-F(1, 100))
    eq((pre_flow, final), (F(109), F(18601, 100)), 'exercise 5 beginning-fee ledger')
    eq((1+F(9, 100))*(1-F(11, 100))-1, F(-299, 10000), 'exercise 5 beginning-fee TWR')
    g = (-1+math.sqrt(8.4404))/2
    close(100*g*g+100*g, 186.01, 'exercise 5 MWR equation')
    alternate_end = (100*F(11, 10)*F(99, 100)+100)*F(9, 10)*F(99, 100)
    eq(alternate_end, F(1861299, 10000), 'exercise 5 ending-fee ledger')
    eq(F(11, 10)*F(99, 100)*F(9, 10)*F(99, 100)-1, F(-29701, 1000000), 'exercise 5 ending-fee TWR')
    alpha, se, fee = F(3, 1000), F(1, 500), F(3, 2000)
    eq(alpha-fee, F(3, 2000), 'exercise 8 net alpha')
    eq([alpha-F(49, 25)*se, alpha+F(49, 25)*se], [F(-23, 25000), F(173, 25000)], 'exercise 8 gross nominal interval')
    eq([alpha-fee-F(49, 25)*se, alpha-fee+F(49, 25)*se], [F(-121, 50000), F(271, 50000)], 'exercise 8 net nominal interval')
    groups.append('All remaining aggregate arithmetic, autocovariance, alternative fee and nominal interval exercise anchors')

    zero = deepcopy(data)
    zero['monthly']['fund_gross'] = [str(b+F(1, 500)+F(1, 1000)) for b in bench]
    constant = model.run(zero)
    eq(F(constant['net_information_ratio']['mean']), F(1, 1000), 'constant positive sample differential')
    eq(constant['net_information_ratio']['ratio_approx'], None, 'zero-risk ratio is undefined')
    eq(constant['net_information_ratio']['ratio_status'], 'undefined_zero_variance', 'undefined status explicit')
    eq(constant['net_two_factor']['classic_alpha_t_approx'], None, 'zero fitted residual variance does not invent a t statistic')
    full_loss = deepcopy(data)
    full_loss['panel']['funds'][2]['net_returns'][2] = '-1'
    wiped = model.run(full_loss)['fund_panel']
    eq(F(wiped['selected_outcome_return']), F(-439, 800), 'terminal complete loss then zero cash retained')
    groups.append('Positive constant differential has undefined ratio; explicit full liquidation remains in selected cohort')

    def reject_variant(edit, label):
        nonlocal rejected_count
        d = deepcopy(data)
        edit(d)
        try:
            model.run(d)
        except ValueError:
            rejected_count += 1
            return
        raise AssertionError('Expected domain rejection: '+label)
    bad_edits = [
        (lambda d: d['conventions'].__setitem__('fee_basis', 'ending_nav'), 'contradictory fee basis'),
        (lambda d: d['conventions'].__setitem__('benchmark_fee', '0.001'), 'ignored benchmark cost'),
        (lambda d: d['conventions'].__setitem__('post_exit_cash_return', '0.01'), 'ignored closure cash rate'),
        (lambda d: d['monthly']['end_contributions'].__setitem__(3, '-500'), 'withdrawal outside unique-root contract'),
        (lambda d: d['monthly']['end_contributions'].__setitem__(7, '100'), 'terminal subscription outside scope'),
        (lambda d: d['monthly']['dates'].__setitem__(2, '2027-03-30'), 'non-month-end timestamp'),
        (lambda d: d['monthly']['dates'].__setitem__(2, '2027-02-28'), 'duplicate month'),
        (lambda d: d['monthly'].__setitem__('style_factor', d['monthly']['market_excess'][:]), 'rank-deficient factors'),
        (lambda d: d['monthly'].__setitem__('fee_rate', True), 'boolean numeric input'),
        (lambda d: d['monthly']['fund_gross'].__setitem__(0, '-1'), 'nonpositive main wealth factor'),
        (lambda d: d['attribution']['periods'][0].__setitem__('portfolio_weights', ['0.8', '0.3']), 'invalid sector budget'),
        (lambda d: d['attribution']['periods'][0].__setitem__('portfolio_weights', ['1', '0']), 'undefined absent-sector return contract'),
        (lambda d: d['panel']['funds'][2]['net_returns'].__setitem__(2, None), 'missing liquidation return'),
        (lambda d: d['panel']['funds'][4]['net_returns'].__setitem__(0, '0'), 'pre-entry backfill'),
        (lambda d: d['panel']['funds'][2]['net_returns'].__setitem__(3, '0'), 'post-exit fund return'),
        (lambda d: d['panel']['funds'][0]['net_returns'].__setitem__(0, '-1'), 'nonterminal complete loss'),
        (lambda d: d['panel'].__setitem__('initial_cohort', ['A', 'B', 'D', 'F']), 'retrospective cohort switch'),
    ]
    for edit, label in bad_edits:
        reject_variant(edit, label)
    eq(rejected_count, 17, 'meaningful rejected contracts')
    groups.append('Seventeen contradictory policy, timing, rank, wealth, attribution and survivorship contracts rejected')

    reference = json.loads((PROJECT/'v09-c08-output.json').read_text())
    eq(out, reference, 'complete preserved result')
    manifest = json.loads((PROJECT/'v09-c08-manifest.json').read_text())
    eq({row['file'] for row in manifest['files']}, {'v09-c08-inputs.json', 'v09-c08-analysis.py', 'v09-c08-output.json', 'v09-c08-README.txt'}, 'manifest perimeter')
    for row in manifest['files']:
        raw = (PROJECT/row['file']).read_bytes()
        eq(len(raw), row['bytes'], 'manifest bytes')
        eq(hashlib.sha256(raw).hexdigest(), row['sha256'], 'manifest hash')
    class Structure(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids, self.hrefs, self.worked, self.solutions, self.h1 = [], [], 0, 0, 0
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            self.h1 += tag == 'h1'
            if 'id' in a: self.ids.append(a['id'])
            if 'href' in a: self.hrefs.append(a['href'])
            self.worked += 'worked' in a.get('class', '').split()
            self.solutions += tag == 'details' and 'solutions' in a.get('class', '').split()
    structure = Structure()
    structure.feed((ROOT/'content/chapters/v09-c08.html').read_text())
    eq(len(structure.ids), len(set(structure.ids)), 'unique fragment anchors')
    eq(structure.h1, 0, 'fragment leaves the chapter h1 to the shared builder')
    eq(structure.worked, 4, 'four complete worked cases')
    eq(structure.solutions, 1, 'complete solution container')
    for i in range(1, 9):
        yes('exercise-'+str(i) in structure.ids and 'solution-'+str(i) in structure.ids, 'eight matched anchored prompts and solutions')
    sources = json.loads((ROOT/'content/reviews/v09-c08-sources.json').read_text())
    eq(len(sources), 5, 'five scoped methodological sources')
    canonical = {s['id']: s for s in json.loads((ROOT/'content/sources.json').read_text())}
    eq(sources[-1], canonical['v09-c01-gips-methods'], 'reused method source exact canonical record')
    for source in sources:
        yes('sources.html#'+source['id'] in structure.hrefs, 'source has chapter citation')
        yes(all(source.get(k) for k in ('id','title','url','use','checked','verification')), 'source inspection scope complete')
    for filename in ['v09-c08-inputs.json','v09-c08-analysis.py','v09-c08-output.json','v09-c08-manifest.json','v09-c08-README.txt']:
        yes(filename in structure.hrefs, 'flat downloadable asset route')
    with tempfile.TemporaryDirectory(prefix='moraine-offline-') as directory:
        folder = Path(directory)
        for filename in ('v09-c08-inputs.json', 'v09-c08-analysis.py'):
            shutil.copyfile(PROJECT/filename, folder/filename)
        for optimized in (False, True):
            command = [sys.executable] + (['-O'] if optimized else []) + [str(folder/'v09-c08-analysis.py')]
            if optimized: command.append(str(folder/'v09-c08-inputs.json'))
            result = subprocess.run(command, cwd=ROOT.parent, text=True, capture_output=True, check=True)
            eq(result.stderr, '', 'portable CLI stderr')
            eq(json.loads(result.stdout), reference, 'portable normal/optimized result')
    groups.append('Complete reference, manifest, source/HTML structure and isolated normal/optimized offline execution')
    return {'chapter':'v09-c08','status':'pass','check_groups':len(groups),'comparisons':comparisons,'domain_rejections':rejected_count,
            'checks':[{'name':name,'status':'pass'} for name in groups],
            'limits':'Independent synthetic arithmetic checks do not validate statistical assumptions, real manager skill, standards compliance or visual UI.'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
