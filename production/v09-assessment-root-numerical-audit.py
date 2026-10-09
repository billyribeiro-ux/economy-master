"""Coordinator reconstruction; never imports specialist models or checkers."""
from fractions import Fraction as F
from itertools import product
from math import comb, sqrt, isclose
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


class Audit:
    def __init__(self):
        self.comparisons = 0

    def equal(self, actual, expected, name):
        self.comparisons += 1
        if actual != expected:
            raise AssertionError(f'{name}: {actual!r} != {expected!r}')

    def true(self, condition, name):
        self.equal(bool(condition), True, name)


def avg(xs):
    return sum(xs)/len(xs)


def covariance(xs, ys, sample=False):
    return sum((x-avg(xs))*(y-avg(ys)) for x, y in zip(xs, ys))/(len(xs)-sample)


def exam_a():
    a = Audit()
    end = (110+90)*F(11, 10)-2
    a.equal((end, F(110, 100)*end/200-1, end-190), (218, F(199, 1000), 28), 'A1 flows')
    ra = tuple(map(F, ('.32', '.32', '-.08', '-.08')))
    rb = tuple(map(F, ('.26', '.06', '.06', '-.14')))
    a.equal((avg(ra), avg(rb), covariance(ra, ra), covariance(ra, rb), covariance(rb, rb)),
            (F(3, 25), F(3, 50), F(1, 25), F(1, 50), F(1, 50)), 'A1 population covariance')
    scores = {}
    for w in (F(3, 5), F(1, 2)):
        returns = tuple(w*x+(1-w)*y for x, y in zip(ra, rb))
        mean, var = avg(returns), covariance(returns, returns)
        scores[w] = (mean, var, mean-2*var)
    a.equal(scores[F(3, 5)], (F(12, 125), F(17, 625), F(26, 625)), 'A1 constrained score')
    for i in range(61):
        w = F(i, 100)
        nominal = F(1, 50)+F(3, 50)*w-F(1, 25)*w*w
        robust = F(1, 50)+F(1, 25)*w-F(1, 25)*w*w
        a.true(nominal <= F(26, 625) and robust <= F(3, 100), 'A1 distinct optimality certificates')
    coefficient = 1/(F(1, 2)/2+F(1, 2)/6)
    premium = coefficient*F(1, 25)
    beta = F(3, 50)/F(1, 25)
    a.equal((coefficient, premium, F(1, 50)+beta*premium,
             F(18, 100)-F(1, 50)-beta*(F(14, 100)-F(1, 50))),
            (3, F(3, 25), F(1, 5), F(-1, 50)), 'A2 risk-tolerance aggregation')
    q = (F(1, 5), F(1, 2), F(3, 10))
    payoffs = ((1, 2, 0), (1, 1, 1), (1, 0, 3))
    a.equal(tuple(sum(q[i]*payoffs[i][j] for i in range(3)) for j in range(3)),
            (1, F(9, 10), F(7, 5)), 'A2 all traded prices')
    a.equal(tuple(sum(row[j]*(-5, 4, 3)[j] for j in range(3)) for row in payoffs),
            (3, 2, 4), 'A2 contingent replica')
    a.equal(sum(x*y for x, y in zip((-5, 4, 3), (F(1), F(9, 10), F(7, 5)))),
            F(14, 5), 'A2 replica cost')
    a.equal(tuple(-z+4*x+3*y-F(47, 10) for z, (_, x, y) in zip((3, 2, 4), payoffs)),
            (F(3, 10),)*3, 'A2 financed arbitrage')
    t = tuple(map(F, (-1, 0, 1)))
    h = tuple(x*x-F(2, 3) for x in t)
    m = tuple(1-F(3, 10)*x-F(9, 20)*y for x, y in zip(t, h))
    f = tuple(F(1, 5)+x for x in t)
    w = tuple(F(9, 20)+2*x+F(1, 2)*y for x, y in zip(t, h))
    g = tuple(F(1, 10)+x for x in h)
    a.equal(m, (F(23, 20), F(13, 10), F(11, 20)), 'A3 positive SDF support')
    a.equal((covariance(w, f)/covariance(f, f), avg(w)-2*avg(f)),
            (2, F(1, 20)), 'A3 nonlinear residual projection')
    a.equal((avg(tuple(x*y for x, y in zip(m, f))),
             avg(tuple(x*y for x, y in zip(m, w))),
             avg(tuple(x*y for x, y in zip(m, g)))), (0, 0, 0), 'A3 zero-cost prices')
    a.equal(tuple(y-2*x for x, y in zip(f, w)),
            (F(13, 60), F(-17, 60), F(13, 60)), 'A3 F-only residual loses in middle state')
    a.true(all(y == 2*x+z/2 for x, y, z in zip(f, w, g)), 'A3 exact complete factor hedge')
    histories = list(product((-1, 1), repeat=11))
    fixed = sum(sum(x == 1 for x in row) >= 9 for row in histories)
    selected = sum(max(sum(x == 1 for x in row), sum(x == -1 for x in row)) >= 9
                   for row in histories)
    a.equal((fixed, selected, F(fixed, len(histories)), F(selected, len(histories))),
            (67, 134, F(67, 2048), F(67, 1024)), 'A3 exhaustive dependent orientation search')
    active = tuple(x-y-F(1, 500) for x, y in zip(
        map(F, ('.03', '-.005', '.015', '-.01')), map(F, ('.02', '-.01', '.01', '0'))))
    a.equal((avg(active), covariance(active, active, sample=True)),
            (F(1, 2000), F(3, 40000)), 'A3 net sample active moments')
    a.true(isclose(float(avg(active))/sqrt(float(covariance(active, active, sample=True))),
                   .05773502691896258, rel_tol=1e-12), 'A3 historical IR')
    joint = []
    conditional_scores = []
    for mean, holding in ((F(1, 25), F(60)), (F(-1, 50), F(45))):
        states = tuple(100+holding*(mean+F(1, 5)*u)-(30+10*u) for u in (-1, 1))
        joint.extend(states)
        conditional_scores.append(avg(states)-F(1, 20)*covariance(states, states))
        a.equal(mean-F(1, 50)*(F(1, 5)*holding-10), 0, 'A4 conditional FOC')
    joint = tuple(joint)
    a.equal((avg(joint), covariance(joint, joint), avg(conditional_scores),
             avg(joint)-F(1, 20)*covariance(joint, joint)),
            (F(283, 4), F(2089, 400), F(565, 8), F(563911, 8000)),
            'A4 independent joint-state variance')
    a.equal(-40-F(12)/F(11, 10)+F(308, 5)/F(11, 10)**2, 0, 'A4 IRR equation')
    a.equal(F(308, 5)-40*F(21, 20)**2-12*F(21, 20), F(49, 10), 'A4 terminal excess')
    a.equal(40+20/F(21, 20), F(1240, 21), 'A4 minimum gross-call funding')
    paper_cash, paper_shares = 1000+80*10, 200-80
    actual_cash, actual_shares = 1000+50*F(49, 5)-1, 150
    mark = F(48, 5)
    a.equal(paper_cash+paper_shares*mark-actual_cash-actual_shares*mark, 23, 'A5 target cash reconciliation')
    a.equal(((actual_shares-paper_shares)*mark)**2/F(100), F(20736, 25), 'A5 active CU variance')
    repair = []
    for n in range(31):
        c = actual_cash+n*F(237, 25)
        v = ((30-n)*mark)**2/100
        if c >= 1600 and v <= 400:
            repair.append(n)
    a.equal(min(repair), 12, 'A5 constrained smallest integer repair')
    a.equal((actual_cash+12*F(237, 25), (18*mark)**2/100),
            (F(40069, 25), F(186624, 625)), 'A5 temporary cash and risk')
    a.equal(paper_cash-(actual_cash+30*F(237, 25)), F(133, 5), 'A5 full completion retains cash shortfall')
    return {'status': 'passed', 'comparisons': a.comparisons, 'groups': 5}


def exam_b():
    a = Audit()
    a.equal(F(240, 200)*F(110, 120)-1, F(1, 10), 'B1 flow-separated TWR')
    a.true(isclose(sqrt(1.1)-1, .04880884817015163, rel_tol=1e-12), 'B1 annualized horizon')
    a.true(all(200*g*g-120*g-110 == 0 for g in (F(11, 10), F(-1, 2))), 'B1 annual IRR roots')
    ra = tuple(map(F, ('-.02', '.02', '.04', '.08')))
    rb = tuple(map(F, ('-.01', '.07', '.01', '.09')))
    a.equal((avg(ra), avg(rb), covariance(ra, ra, True), covariance(ra, rb, True), covariance(rb, rb, True)),
            (F(3, 100), F(1, 25), F(13, 7500), F(11, 7500), F(17, 7500)), 'B1 raw sample moments')
    raw = lambda w: (8*w*w-12*w+17)/7500
    shrunk = lambda w: (19*w*w-23*w+17)/7500
    a.equal((raw(F(2, 3)), shrunk(F(23, 38))), (F(113, 67500), F(763, 570000)), 'B1 two covariance-specific minima')
    for i in range(201):
        w = F(i, 300)
        a.true(raw(w) >= raw(F(2, 3)) and shrunk(w) >= shrunk(F(23, 38)), 'B1 feasible risk comparisons')
    lower, upper = F(3, 40), F(11, 30)
    a.equal((7*lower-F(3, 10), 7*upper-F(3, 10)),
            (F(9, 40), F(34, 15)), 'B2 incomplete bounds')
    for i in range(1, 101):
        t = lower+(upper-lower)*F(i, 101)
        q = (2*t-F(3, 20), F(11, 10)-3*t, t)
        a.true(min(q) > 0 and sum(q) == F(19, 20) and sum(x*y for x, y in zip(q, (1, 2, 4))) == F(41, 20),
               'B2 admissible full family')
    a.equal(-F(12, 5)+F(41, 20)/3+F(103, 57)*F(19, 20), 0, 'B2 arbitrage initial budget')
    a.equal(tuple(-x+F(s, 3)+F(103, 57) for x, s in zip((2, 0, 3), (1, 2, 4))),
            (F(8, 57), F(47, 19), F(8, 57)), 'B2 every terminal arbitrage payoff')
    a.equal(F(9, 100)-F(1, 50)-F(3, 2)*(F(3, 50)-F(1, 50)), F(1, 100), 'B2 proxy alpha')
    mean_m, mean_z = F(1, 250), F(3, 500)
    slope = F(3, 5)+F(2, 5)*F(3, 10000)/F(1, 2500)
    mean_y = F(1, 1000)+F(3, 5)*mean_m+F(2, 5)*mean_z
    alpha = mean_y-slope*mean_m
    a.equal((slope, mean_y, alpha, alpha-F(1, 500)),
            (F(9, 10), F(29, 5000), F(11, 5000), F(1, 5000)), 'B3 omitted exposure and fee')
    a.equal((F(1, 1000)-F(1, 500))/F(1, 100), F(-1, 10), 'B3 matched net IR')
    gain = 100*F(1, 250)-F(3, 20)-F(7, 20)
    a.equal((gain, gain/20), (F(-1, 10), F(-1, 200)), 'B3 funded zero-cost legs')
    a.equal((F(215, 300)-1, F(215, 200)-1), (F(-17, 60), F(3, 40)), 'B3 membership-conditioned returns')
    rz, h = (F(3, 10), F(-1, 10)), (F(34), F(26))
    a.equal((avg(rz), covariance(rz, rz), avg(h), covariance(h, h), covariance(rz, h)),
            (F(1, 10), F(1, 25), 30, 16, F(4, 5)), 'B4 endowment covariance')
    def obj(x, with_cost):
        fee = F(1, 50)*abs(x-45) if with_cost else 0
        terminal = tuple(60-22+x*r+v-fee for r, v in zip(rz, h))
        return avg(terminal)-F(1, 40)*covariance(terminal, terminal)
    a.equal((obj(F(40), True), obj(F(30), True)), (F(683, 10), F(341, 5)), 'B4 changed optimal trade after fee')
    chosen = F(265, 7)
    fee = F(1, 50)*abs(chosen-45)
    a.equal((45-chosen, fee, 60-chosen-fee), (F(50, 7), F(1, 7), 22), 'B4 exact funded boundary')
    for i in range(601):
        x = F(i, 10)
        cash = 60-x-F(1, 50)*abs(x-45)
        a.true(obj(x, False) <= obj(F(30), False), 'B4 costless global grid')
        if cash >= 0:
            a.true(obj(x, True) <= obj(F(40), True), 'B4 post-trade funded relaxed optimum')
        if cash >= 22:
            a.true(obj(x, True) <= obj(chosen, True), 'B4 calendar-funded optimum')
    variation = 2*(40-50)
    a.equal((variation, 22+variation, 22+5-(22+variation)), (-20, 2, 25), 'B4 shared collateral account')
    # Each of the200 equally likely state/target-share pairs is inspected.
    outcomes = [(state, k, k < filled) for state, filled in (('Up', 20), ('Down', 80)) for k in range(100)]
    fills = [x for x in outcomes if x[2]]
    up = sum(state == 'Up' for state, _, _ in fills)
    conditional_mark = F(up*22+(len(fills)-up)*18, len(fills))
    a.equal((F(len(fills), len(outcomes)), F(up, len(fills)), conditional_mark-F(498, 25)),
            (F(1, 2), F(1, 5), F(-28, 25)), 'B5 conditional passive-fill selection')
    shortfalls = []
    for count, mark in ((20, 22), (80, 18)):
        paper = 1000+100*mark
        actual = 3000-count*F(498, 25)+count*mark
        shortfalls.append(paper-actual)
    a.equal(shortfalls, [F(792, 5), F(-232, 5)], 'B5 branch whole-target results')
    a.equal(avg(shortfalls), F(56), 'B5 expected total shortfall')
    cash0 = 3000-80*F(498, 25)
    sale = F(899, 50)
    cash_feasible = [n for n in range(81) if cash0+n*sale >= 1450]
    risk_feasible = [n for n in range(81) if F(9, 5)*(20+n) <= 40]
    a.equal((min(cash_feasible), max(risk_feasible), set(cash_feasible)&set(risk_feasible)),
            (3, 2, set()), 'B5 infeasible intersection')
    contributions = [(max(F(0), 1450-cash0-n*sale), n) for n in risk_feasible]
    a.equal(min(contributions), (F(191, 25), 2), 'B5 smallest sponsor remedy')
    a.equal((cash0+3*sale, F(9, 5)*23), (F(73017, 50), F(207, 5)), 'B5 smallest prospective waiver')
    return {'status': 'passed', 'comparisons': a.comparisons, 'groups': 5}


def project_grid():
    """Independent scalar risk expansion and entire feasible lot-grid ranking."""
    a = Audit()
    data = json.loads((ROOT/'content/projects/v09-assessment-inputs.json').read_text())
    r = data['research']; p = data['portfolio']; forecast = p['forecast']
    cutoff = r['decision_cutoff']
    latest = {}
    for row in r['series_records']:
        key = (row['asset'], row['period'])
        if row['released_on'] <= cutoff and row['observation_end'] <= cutoff:
            if key not in latest or (row['released_on'], row['version']) > (
                    latest[key]['released_on'], latest[key]['version']):
                latest[key] = row
    def net(asset, periods):
        return tuple(F(latest[(asset, t)]['gross_return'])-
                     F(latest[(asset, t)]['fee_on_beginning_nav']) for t in periods)
    er = net('E', r['training_periods']); br = net('B', r['training_periods'])
    empirical = ((covariance(er, er, True), covariance(er, br, True)),
                 (covariance(br, er, True), covariance(br, br, True)))
    a.equal(empirical, ((F(13, 7500), F(-7, 15000)),
                        (F(-7, 15000), F(1, 6000))), 'Project quarterly sample covariance')
    weight = F(forecast['sample_weight']); periods = F(forecast['additive_periods_per_year'])
    cov = tuple(tuple(weight*periods*empirical[i][j]+(1-weight)*F(forecast['prior_covariance'][i][j])
                      for j in range(2)) for i in range(2))
    a.equal(cov, ((F(44, 1875), F(2, 1875)), (F(2, 1875), F(2, 375))), 'Project planning blend')
    a.true(cov[0][0] > 0 and cov[0][0]*cov[1][1]-cov[0][1]**2 > 0, 'Project SPD covariance')
    factor4 = lambda v, matrix: v[0]*v[0]*matrix[0][0]+2*v[0]*v[1]*matrix[0][1]+v[1]*v[1]*matrix[1][1]
    initial = p['initial_liquid']; benchmark = p['benchmark']; policy = p['policy']
    cash_factor = F(p['cash_half_year_factor'])
    W = F(p['initial_wealth']); liquid = W-F(p['private_initial_value'])
    planning = p['planning_flows']
    load_m = (F(forecast['manager_equity_loading']), F(forecast['manager_bond_loading']))
    residual_m = F(forecast['manager_residual_variance'])
    private_load = (F(forecast['private_equity_loading']), F(forecast['private_bond_loading']))
    def ledger(e, b, m, overlay):
        positions = {'E': e, 'B': b, 'manager': m}
        fees = sum(abs(positions[k]-F(initial[k]))*F(p['entry_cost_rates'][k]) for k in positions)
        cash = liquid-e-b-m-fees
        risk_load = (e+load_m[0]*m+private_load[0], b+load_m[1]*m+private_load[1])
        risk = factor4(risk_load, cov)+m*m*residual_m+F(forecast['private_residual_variance'])
        active_load = (e+load_m[0]*m-F(benchmark['E']), b+load_m[1]*m-F(benchmark['B']))
        active = factor4(active_load, cov)+m*m*residual_m
        mean_manager = load_m[0]*F(forecast['equity_mean'])+load_m[1]*F(forecast['bond_mean'])+overlay-F(forecast['manager_annual_fee'])
        t1 = cash*cash_factor-F(planning['call_t1'])-F(planning['grant_t1'])
        mean = (e*(1+F(forecast['equity_mean']))+b*(1+F(forecast['bond_mean']))+
                m*(1+mean_manager)+t1*cash_factor+F(forecast['private_distribution_mean'])-F(planning['grant_t2']))
        stress_pairs = []
        for stress in p['design_stresses']:
            cash1 = cash*cash_factor-F(stress['call_t1'])-F(stress['grant_t1'])
            terminal = (e*(1+F(stress['equity_return']))+b*(1+F(stress['bond_return']))+
                        m*(1+F(stress['manager_return']))+cash1*cash_factor+
                        F(stress['private_distribution'])-F(stress['grant_t2']))
            stress_pairs.append((cash1, terminal))
        feasible = (cash >= F(policy['cash_buffer']) and t1 >= F(policy['cash_buffer'])
                    and risk <= F(policy['total_variance_limit']) and active <= F(policy['active_variance_limit'])
                    and all(x >= F(policy['cash_buffer']) and y >= F(policy['terminal_floor'])
                            for x, y in stress_pairs))
        return {'positions': (e, b, m), 'fees': fees, 'cash': cash, 'risk': risk,
                'active': active, 'mean': mean, 'score': mean-F(policy['gamma'])/(2*W)*risk,
                'stress': stress_pairs, 'feasible': feasible}
    rows = []
    step = int(F(p['lot']))
    for e, b, m in product(range(0, int(F(p['caps']['E']))+1, step),
                           range(0, int(F(p['caps']['B']))+1, step),
                           range(0, int(F(p['caps']['manager']))+1, step)):
        row = ledger(F(e), F(b), F(m), F(forecast['manager_overlay_lower']))
        rows.append(row)
    feasible = [x for x in rows if x['feasible']]
    a.equal((len(rows), len(feasible)), (2499, 670), 'Project enumerate full feasible set')
    chosen = max(feasible, key=lambda row: (row['score'], tuple(-x for x in row['positions'])))
    a.equal(chosen['positions'], (325, 250, 0), 'Project robust maximum')
    a.equal((chosen['fees'], chosen['cash'], chosen['risk']),
            (F(23, 40), F(8977, 40), F(931544, 150)), 'Project robust costs and full risk')
    nominal_rows = [ledger(*x['positions'], F(forecast['manager_overlay_upper'])) for x in feasible]
    nominal = max(nominal_rows, key=lambda row: (row['score'], tuple(-x for x in row['positions'])))
    a.equal(nominal['positions'], (325, 225, 25), 'Project tentative-premium maximum')
    robust_gamma6 = max(feasible, key=lambda row: row['mean']-F(3, 1000)*row['risk'])
    nominal_gamma6 = max(nominal_rows, key=lambda row: row['mean']-F(3, 1000)*row['risk'])
    a.equal((robust_gamma6['positions'],nominal_gamma6['positions']),
            ((250,325,0),(250,300,25)), 'Project preference intervention at gamma6')
    # Directly realize the disclosed four orthogonal shocks, without model code.
    se = sqrt(float(cov[0][0])); cross = float(cov[0][1])/se
    sb = sqrt(float(cov[1][1])-cross*cross)
    witness = []
    for u1,u2,um,up in product((-1,1), repeat=4):
        de,db = se*u1,cross*u1+sb*u2
        witness.append((de,db,.4*de+.6*db+.04*um,140*de+40*db+20*up))
    for row in witness:
        a.true(1.08+row[0] > 0 and 1.03+row[1] > 0 and 1.042+row[2] > 0
               and 320+row[3] > 0, 'Project bounded law positive baseline payoffs')
    loading = ((1,0),(0,1),(.4,.6),(140,40))
    for i,j in product(range(4), repeat=2):
        empirical_cov = sum(row[i]*row[j] for row in witness)/16
        expected_cov = sum(loading[i][k]*loading[j][l]*float(cov[k][l]) for k,l in product(range(2), repeat=2))
        if i == j:
            expected_cov += (0,0,.0016,400)[i]
        a.true(isclose(empirical_cov,expected_cov,rel_tol=1e-12,abs_tol=1e-12),
               'Project full claim covariance from all16 physical states')
    for row in feasible:
        a.true(row['score'] <= chosen['score'], 'Project independent robust score ranking')
    fallback = max((x for x in feasible if x['positions'][1] == 275), key=lambda row: row['score'])
    a.equal(fallback['positions'], (300, 275, 0), 'Project partial-sale feasible fallback')
    stored = json.loads((ROOT/'content/projects/v09-assessment-output.json').read_text())
    ranked = sorted(feasible, key=lambda x: (-x['score'], x['risk'], x['fees'], *x['positions']))
    a.equal(len(stored['optimization']['robust_ranked']), len(ranked), 'Project saved complete ranking length')
    for i, (row, actual) in enumerate(zip(ranked, stored['optimization']['robust_ranked'])):
        high = ledger(*row['positions'], F(forecast['manager_overlay_upper']))
        fields = {'E': row['positions'][0], 'B': row['positions'][1], 'manager': row['positions'][2],
                  'fee': row['fees'], 'cash': row['cash'], 'variance': row['risk'], 'active_variance': row['active'],
                  'lower_mean_reserve': row['mean'], 'upper_mean_reserve': high['mean'],
                  'robust_score': row['score'], 'nominal_score': high['score']}
        for key, value in fields.items():
            a.equal(F(actual[key]), value, f'Project ranking[{i}].{key}')
    return {'status': 'passed', 'comparisons': a.comparisons, 'candidates': len(rows),
            'feasible': len(feasible),
            'robust': {k: str(v) for k, v in chosen.items() if k not in ('stress', 'feasible')},
            'nominal': {k: str(v) for k, v in nominal.items() if k not in ('stress', 'feasible')}}


def project_research_and_ledgers():
    a = Audit()
    data = json.loads((ROOT/'content/projects/v09-assessment-inputs.json').read_text())
    output = json.loads((ROOT/'content/projects/v09-assessment-output.json').read_text())
    r, p = data['research'], data['portfolio']
    o = output['research']
    def observations(asset, periods, cutoff):
        answer = []
        for t in periods:
            c = r['closures'].get(asset)
            if c and c['announced_on'] <= cutoff and t > c['last_period']:
                answer.append(F(0)); continue
            rows = [row for row in r['series_records'] if row['asset'] == asset and row['period'] == t
                    and row['observation_end'] < row['released_on'] <= cutoff]
            latest = sorted(rows, key=lambda row: (row['released_on'], row['version']))[-1]
            answer.append(F(latest['gross_return'])-F(latest['fee_on_beginning_nav']))
        return tuple(answer)
    def grow(series):
        result = F(1)
        for x in series:
            result *= 1+x
        return result
    def match_stats(series, comparison, record, label):
        active = tuple(x-y for x, y in zip(series, comparison))
        slope = covariance(series, comparison, True)/covariance(comparison, comparison, True)
        intercept = avg(series)-slope*avg(comparison)
        residual = tuple(x-intercept-slope*y for x, y in zip(series, comparison))
        values = {'mean_net_active': avg(active), 'sample_active_variance': covariance(active, active, True),
                  'net_growth_factor': grow(series), 'benchmark_growth_factor': grow(comparison),
                  'compound_relative_wealth': grow(series)/grow(comparison)-1,
                  'terminal_factor_difference': grow(series)-grow(comparison), 'last_net_active': active[-1],
                  'benchmark_slope': slope, 'sample_intercept': intercept,
                  'sample_residual_squared_sum': sum(x*x for x in residual)}
        a.equal(tuple(map(F, record['net_returns'])), series, label+' net series')
        for key, expected in values.items():
            a.equal(F(record[key]), expected, label+' '+key)
        te = sqrt(float(covariance(active, active, True)))
        a.true(isclose(record['tracking_error_per_period_approx'], te, rel_tol=1e-12, abs_tol=1e-14), label+' TE')
        if te:
            a.true(isclose(record['sample_information_ratio_approx'], float(avg(active))/te,
                           rel_tol=1e-12, abs_tol=1e-14), label+' IR')
        else:
            a.equal(record['sample_information_ratio_approx'], None, label+' undefined zero-TE ratio')
    train, held = r['training_periods'], r['holdout_periods']
    c0, c1 = r['decision_cutoff'], r['evaluation_cutoff']
    et, bt = observations('E', train, c0), observations('B', train, c0)
    bm = tuple(F(2, 5)*x+F(3, 5)*y for x, y in zip(et, bt))
    eligible = [asset for asset in r['manager_ids'] if r['admitted_on'][asset] <= c0
                and not (asset in r['closures'] and r['closures'][asset]['announced_on'] <= c0)]
    ranked = sorted(eligible, key=lambda asset: (-avg(tuple(x-y for x, y in zip(observations(asset, train, c0), bm))), asset))
    a.equal(ranked, ['K', 'M'], 'Project point-in-time eligibility and ranking')
    a.equal(o['selected_manager'], ranked[0], 'Project selection frozen before holdout')
    for row in o['eligible_ranked']:
        match_stats(observations(row['asset'], train, c0), bm, row['statistics'], 'training '+row['asset'])
    all_factors = [grow(observations(asset, train, c0)) for asset in r['initial_cohort']]
    survivor_factors = [grow(observations(asset, train, c0)) for asset in r['initial_cohort'] if asset not in r['closures']]
    a.equal(F(o['training_full_cohort_return']), avg(all_factors)-1, 'Project original cohort includes liquidation')
    a.equal(F(o['training_survivor_only_return']), avg(survivor_factors)-1, 'Project survivor distortion')
    a.equal(grow(observations('CX', train+held, c1)), F(1911, 2500), 'Project closure wealth then cash')
    revised_bm = tuple(F(2, 5)*x+F(3, 5)*y for x, y in zip(observations('E', train, c1), observations('B', train, c1)))
    revised_rank = sorted(eligible, key=lambda asset: (-avg(tuple(x-y for x, y in zip(observations(asset, train, c1), revised_bm))), asset))
    a.equal(revised_rank, ['M', 'K'], 'Project late revision changes hindsight winner')
    for row in o['retrospective_same_eligible_ranked']:
        match_stats(observations(row['asset'], train, c1), revised_bm, row['statistics'], 'revised '+row['asset'])
    a.equal(o['late_backfilled_ranked'][0]['asset'], 'N', 'Project backfilled winner was not eligible at decision')
    for row in o['late_backfilled_ranked']:
        match_stats(observations(row['asset'], train, c1), revised_bm, row['statistics'], 'backfilled '+row['asset'])
    eh, bh = observations('E', held, c1), observations('B', held, c1)
    hb = tuple(F(2, 5)*x+F(3, 5)*y for x, y in zip(eh, bh))
    for asset in eligible:
        match_stats(observations(asset, held, c1), hb, o['holdout_statistics'][asset], 'holdout '+asset)
    full_factors = {asset: grow(observations(asset, train+held, c1)) for asset in r['initial_cohort']}
    for asset, expected in full_factors.items():
        a.equal(F(o['final_restated_cohort_growth_factors'][asset]), expected, 'Project restated final wealth '+asset)
    a.equal(F(o['final_restated_full_cohort_return']), avg(list(full_factors.values()))-1, 'Project final cohort vintage')
    a.equal(F(o['final_restated_survivor_only_return']), avg([v for k, v in full_factors.items() if k not in r['closures']])-1,
            'Project final survivor vintage')
    factors = (grow(eh), grow(bh), grow(observations(ranked[0], held, c1)))
    for name, value in zip(('E', 'B', 'manager'), factors):
        a.equal(F(output['realized_report']['realized_liquid_factors'][name]), value, 'Project held-out capital factor '+name)
    g = F(p['cash_half_year_factor'])
    def audit_cash(positions, cash, scenario, record, label, sale=F(0), sale_price=F(0), realized=False):
        before = cash*g
        proceeds = sale*sale_price
        after = before+proceeds-F(scenario['call_t1'])-F(scenario['grant_t1'])
        growth = factors if realized else tuple(1+F(scenario[k]) for k in ('equity_return','bond_return','manager_return'))
        liquid = positions[0]*growth[0]+(positions[1]-sale)*growth[1]+positions[2]*growth[2]
        cash2 = after*g
        reserve = liquid+cash2+F(scenario['private_distribution'])-F(scenario['grant_t2'])
        expected = {'cash_before_t1':before,'bond_original_units_sold_t1':sale,'net_sale_proceeds_t1':proceeds,
                    'capital_call_t1':F(scenario['call_t1']),'grant_t1':F(scenario['grant_t1']),
                    'payment_gap_t1':max(F(0),-after),'buffer_gap_t1':max(F(0),F(p['policy']['cash_buffer'])-after),
                    'cash_after_t1':after,'cash_t2':cash2,'remaining_liquid_proceeds_t2':liquid,
                    'private_distribution_t2':F(scenario['private_distribution']),'grant_t2':F(scenario['grant_t2']),
                    'payment_gap_t2':max(F(0),-reserve),'terminal_reserve':reserve,
                    'floor_gap':max(F(0),F(p['policy']['terminal_floor'])-reserve)}
        for key, value in expected.items():
            a.equal(F(record[key]), value, label+' '+key)
        a.equal(record['payments_funded'], after >= 0 and reserve >= 0, label+' settled payments')
        a.equal(record['cash_and_floor_pass'], after >= F(p['policy']['cash_buffer']) and reserve >= F(p['policy']['terminal_floor']),
                label+' reserve policy')
        return reserve
    holdings = {'target': output['optimization']['robust'], 'nominal_counterfactual': output['optimization']['nominal'],
                'actual':output['implementation']['authorized_fallback'], 'benchmark':output['benchmark']}
    realized_reserve = {}
    for name, holding in holdings.items():
        positions = tuple(F(holding[k]) for k in ('E','B','manager'))
        cash = 1000-200-sum(positions)-sum(abs(q-F(p['initial_liquid'][k]))*F(p['entry_cost_rates'][k])
                                            for k, q in zip(('E','B','manager'), positions))
        a.equal(cash, F(holding['cash']), name+' independent entry ledger')
        realized_reserve[name] = audit_cash(positions,cash,p['realized_private'],output['realized_report']['cash_ledgers'][name],name,realized=True)
        for stress in p['design_stresses']:
            audit_cash(positions,cash,stress,holding['stresses'][stress['name']],name+' '+stress['name'])
    d = output['realized_report']['reserve_gap_decomposition']
    a.equal(F(d['policy_selection']), realized_reserve['target']-realized_reserve['benchmark'], 'Project policy-selection dollars')
    a.equal(F(d['implementation']), realized_reserve['actual']-realized_reserve['target'], 'Project implementation dollars')
    a.equal(F(d['total']), realized_reserve['actual']-realized_reserve['benchmark'], 'Project total active dollars')
    target, actual = holdings['target'], holdings['actual']
    differences = tuple(F(target[k])-F(actual[k]) for k in ('E','B','manager'))
    opportunity = sum(x*(f-1) for x, f in zip(differences,factors))
    fee_effect = (F(actual['fee'])-F(target['fee']))*g*g
    principal_effect = sum(differences)*(1-g*g)
    for key, expected in [('target_minus_actual_opportunity_component',opportunity),('fee_difference_at_terminal',fee_effect),
                          ('cash_principal_timing_adjustment',principal_effect),('target_minus_actual_reserve',opportunity+fee_effect+principal_effect)]:
        a.equal(F(d[key]), expected, 'Project decomposition '+key)
    a.equal(opportunity+fee_effect+principal_effect, realized_reserve['target']-realized_reserve['actual'], 'Project whole-target decomposition closes')
    stress = p['outside_stress']; h = holdings['target']; report = output['outside_design']
    net = F(stress['bond_t1_mark'])-F(stress['bond_spread_per_original_unit'])-F(stress['bond_fee_per_original_unit'])
    needed = max(F(0),(F(stress['call_t1'])+F(stress['grant_t1'])+F(p['policy']['cash_buffer'])-F(h['cash'])*g)/net)
    sale = min(needed,F(h['B']),F(stress['bond_sale_capacity']))
    a.equal(F(report['required_original_units_for_buffer']),needed,'Project outside-design required sale')
    a.equal(F(report['actual_original_units_sold']),sale,'Project outside-design capacity')
    reserve = audit_cash(tuple(F(h[k]) for k in ('E','B','manager')),F(h['cash']),stress,report['ledger'],'outside-design',sale,net)
    a.equal(F(report['external_funding_at_terminal_to_restore_floor']),700-reserve,'Project unfilled terminal policy gap remains visible')
    nominal = holdings['nominal_counterfactual']
    a.equal(realized_reserve['nominal_counterfactual']+25*(grow(observations('M',held,c1))-factors[2]),
            F(7543884431,8000000),'Project early-revision manager-identity transfer')
    edited_k = list(observations('K',held,c1));edited_k[0] += F(1,10)
    a.equal(realized_reserve['nominal_counterfactual']+25*(grow(edited_k)-factors[2]),
            F(7545697583,8000000),'Project held-out-only counterfactual ledger')
    after_limited = F(h['cash'])*g+20*net-F(stress['call_t1'])-F(stress['grant_t1'])
    limited_reserve = 325*F(7,10)+230*F(17,20)+after_limited*g+180-60
    a.equal((after_limited,20-after_limited,limited_reserve),
            (F(37657,8000),F(122343,8000),F(876369057,1600000)),
            'Project capacity20 pays obligations but fails buffer/floor')
    a.equal(240-F(h['cash'])*g,F(115623,8000),'Project zero capacity creates payment failure')
    return {'status':'passed','comparisons':a.comparisons,'scope':'All training/revised/held-out manager statistics, cohort vintages, four realized and eight design-stress ledgers, original-target decomposition and outside-design forced-sale funding.'}


if __name__ == '__main__':
    report = {'status': 'passed', 'form_a': exam_a(), 'form_b': exam_b(), 'project_grid': project_grid(),
              'project_data_and_ledgers':project_research_and_ledgers(),
              'scope': 'Both exam forms, all670 feasible portfolio ranks, research vintages/cohorts, target/actual/benchmark and stress ledgers independently reconstructed without importing author models or checkers.'}
    print(json.dumps(report, indent=2))
