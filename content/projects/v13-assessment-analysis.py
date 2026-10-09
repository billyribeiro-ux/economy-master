"""Exact reader model for V13's noisy-restoration theory project.

No dependencies beyond Python's standard library. run(data) is quiet and pure.
All numbers returned to JSON are exact rational strings, integers or booleans.
The all-history incentive theorem and exceptional network-family proof are in
the accompanying project; a finite policy table is only corroborating evidence.
"""
import argparse
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected, where):
    require(type(value) is dict and set(value) == set(expected), where + ': exact object keys required')


def fraction(value):
    if type(value) is int:
        return F(value)
    require(type(value) is str and re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?', value) is not None,
            'exact integer or integer/fraction string required; no bool/float/nonfinite value')
    return F(value)


def probability(value):
    number = fraction(value)
    require(0 <= number <= 1, 'probability outside [0,1]')
    return number


def strict_loads(text):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def reject_number(_):
        raise ValueError('JSON fractional/nonfinite numbers are unsupported; use exact strings')
    return json.loads(text, object_pairs_hook=object_pairs, parse_float=reject_number, parse_constant=reject_number)


ACTION_KEYS = ('WW', 'WN', 'NW', 'NN')
POLICIES = tuple(product((0, 1), repeat=2))
EDGE_SET = {(0, 1), (1, 2), (2, 3), (0, 3)}


def validate(data):
    keys(data, ('schema_version', 'economy', 'restoration_grid', 'garbling_values', 'active_repair', 'paper_case'), 'input')
    require(type(data['schema_version']) is int and data['schema_version'] == 1, 'schema version 1 required')
    e = data['economy']
    keys(e, ('discount', 'benefit', 'collaboration_effort_cost', 'review_effort_cost', 'initial_state', 'good_report_in_G'), 'economy')
    d, b, c, k = map(fraction, (e['discount'], e['benefit'], e['collaboration_effort_cost'], e['review_effort_cost']))
    require(0 < d < 1 and b > c > 0 and k > 0, 'need 0<discount<1, benefit>collaboration cost>0 and review cost>0')
    require(e['initial_state'] == 'G', 'this design objective starts in G')
    keys(e['good_report_in_G'], ACTION_KEYS, 'G signal law')
    g = {a: probability(e['good_report_in_G'][a]) for a in ACTION_KEYS}
    require(0 < g['NN'] <= g['WN'] == g['NW'] < g['WW'] < 1, 'supported symmetric informative G law required')
    lists = []
    for name in ('restoration_grid', 'garbling_values'):
        require(type(data[name]) is list and len(data[name]) > 0, name + ': nonempty finite list required')
        values = tuple(probability(x) for x in data[name])
        require(len(set(values)) == len(values), name + ': duplicate exact values')
        lists.append(tuple(sorted(values)))
    a = data['active_repair']
    keys(a, ('good_report_in_R', 'counterfactual_one_worker_good_probability'), 'active repair')
    keys(a['good_report_in_R'], ACTION_KEYS, 'R signal law')
    repair = {p: probability(a['good_report_in_R'][p]) for p in ACTION_KEYS}
    require(repair['WN'] == repair['NW'], 'supported symmetric R law required')
    changed = probability(a['counterfactual_one_worker_good_probability'])
    paper = data['paper_case']
    keys(paper, ('vertices', 'undirected_edges', 'regular_interaction', 'singular_interaction', 'last_target_increase'), 'paper case')
    require(type(paper['vertices']) is int and paper['vertices'] == 4, 'only the declared four-cycle is supported')
    edges = paper['undirected_edges']
    require(type(edges) is list and len(edges) == 4, 'four undirected edges required')
    normalized = []
    for edge in edges:
        require(type(edge) is list and len(edge) == 2 and all(type(x) is int and 1 <= x <= 4 for x in edge)
                and edge[0] != edge[1], 'invalid edge')
        normalized.append(tuple(sorted(x-1 for x in edge)))
    require(len(set(normalized)) == 4 and set(normalized) == EDGE_SET, 'unsupported graph; fixed labeled four-cycle required')
    gamma, critical, epsilon = map(fraction, (paper['regular_interaction'], paper['singular_interaction'], paper['last_target_increase']))
    require(0 < gamma < F(1, 2) and critical == F(1, 2) and 0 < epsilon <= 1, 'paper domain: 0<regular<1/2, critical=1/2, 0<epsilon<=1')
    return {'d': d, 'b': b, 'c': c, 'k': k, 'g': g, 'grid': lists[0], 'etas': lists[1],
            'repair': repair, 'changed': changed, 'gamma': gamma, 'epsilon': epsilon}


def linear_values(discount, good, flow):
    """Solve V=g+discount*P*V for the actual two row-stochastic rows."""
    p, q = good
    a, b = 1-discount*p, -discount*(1-p)
    c, d = -discount*q, 1-discount*(1-q)
    determinant = a*d-b*c
    require(determinant > 0, 'discounted stochastic value matrix must be invertible')
    return ((flow[0]*d-b*flow[1])/determinant, (a*flow[1]-c*flow[0])/determinant)


def action_key(own, other):
    return ('W' if own else 'N')+('W' if other else 'N')


def environment(parameters, restoration=None, eta=F(0), review_law=None):
    g = {a: (1-eta)*p+eta/2 for a, p in parameters['g'].items()}
    r = dict(review_law) if review_law is not None else {a: restoration for a in ACTION_KEYS}
    return (g, r)


def primitives(parameters, laws, state, own, other):
    payoff = parameters['b']*other-parameters['c']*own if state == 0 else -parameters['k']*own
    return payoff, laws[state][action_key(own, other)]


def protocol(parameters, laws, recommendation):
    discount = parameters['d']
    prescribed = [primitives(parameters, laws, s, recommendation[s], recommendation[s]) for s in (0, 1)]
    flow, good = tuple(x[0] for x in prescribed), tuple(x[1] for x in prescribed)
    value = linear_values(discount, good, flow)
    residuals, margins, failures = [], [], []
    for state, name in enumerate(('G', 'R')):
        for own in (0, 1):
            payoff, p = primitives(parameters, laws, state, own, recommendation[state])
            alternative = payoff+discount*(p*value[0]+(1-p)*value[1])
            margin = value[state]-alternative
            residuals.append({'state': name, 'own_action': own, 'recommended': own == recommendation[state], 'margin': margin})
            if own != recommendation[state]:
                margins.append(margin)
                if margin < 0:
                    failures.append({'state': name, 'own_action': own, 'one_action_then_return_gain': -margin})
    policies = []
    for own in POLICIES:
        pairs = [primitives(parameters, laws, s, own[s], recommendation[s]) for s in (0, 1)]
        v = linear_values(discount, tuple(z[1] for z in pairs), tuple(z[0] for z in pairs))
        policies.append({'actions_G_R': list(own), 'V': v, 'U': tuple((1-discount)*x for x in v)})
    p, q = good
    # Initial-state discounted occupancy differs from invariant long-run weights.
    denominator = 1-discount*p+discount*q
    weights = ((1-discount+discount*q)/denominator, discount*q/denominator)
    stationary_g = q/(1-p+q)
    normalized = tuple((1-discount)*x for x in value)
    return {'profile_G_R': list(recommendation), 'status': 'certified' if not failures else 'not_certified',
            'strict_alternative_margins': min(margins) > 0, 'V': value, 'U': normalized,
            'on_path_good_probabilities': good, 'current_per_agent_flow': flow, 'alternative_action_margins_G_R': margins,
            'state_action_bellman': residuals, 'profitable_one_action_return_witnesses': failures,
            'stationary_own_policies': policies,
            'best_stationary_U_by_start': tuple(max(row['U'][s] for row in policies) for s in (0, 1)),
            'occupancy': {'stationary_G': stationary_g,
                          'stationary_per_agent_flow': stationary_g*flow[0]+(1-stationary_g)*flow[1],
                          'discounted_G_by_start': weights,
                          'discounted_flow_by_start': tuple(w*flow[0]+(1-w)*flow[1] for w in weights)},
            'scope': 'All-history certification follows the stated Bellman/tail theorem; the four stationary rows are witnesses only.'}


def baseline(parameters, restoration, eta=F(0)):
    row = protocol(parameters, environment(parameters, restoration, eta), (1, 0))
    return {'restoration': restoration, 'garbling': eta, **row}


def continuous_class(parameters, eta):
    d, b, c = parameters['d'], parameters['b'], parameters['c']
    a, z = ((1-eta)*parameters['g'][key]+eta/2 for key in ('WW', 'NW'))
    ceiling = a+(a-z)*(b-c)/c-1/d
    if ceiling < 0:
        return {'raw_restoration_ceiling': ceiling, 'weak_interval': None, 'weak_optimum': None,
                'strict_interval': None, 'strict_supremum_U': None, 'strict_supremum_attained': False,
                'reason': 'The cooperative protocol class is empty; always-N remains an equilibrium.'}
    upper = min(F(1), ceiling)
    weak = baseline(parameters, upper, eta)
    strict_interval = None if ceiling == 0 else {'lower': F(0), 'upper': upper, 'lower_included': True, 'upper_included': ceiling > 1}
    return {'raw_restoration_ceiling': ceiling, 'weak_interval': [F(0), upper], 'weak_optimum': weak,
            'strict_interval': strict_interval, 'strict_supremum_U': weak['U'] if ceiling > 0 else None,
            'strict_supremum_attained': ceiling > 1,
            'reason': 'The increasing initial-G objective is optimized only within the declared restoration class.'}


def design(parameters, eta):
    rows = [baseline(parameters, r, eta) for r in parameters['grid']]
    eligible = [row for row in rows if row['status'] == 'certified']
    best = max(eligible, key=lambda row: row['U'][0]) if eligible else None
    laws = environment(parameters, F(1, 2), eta)
    return {'garbling': eta, 'G_law_after_garbling': laws[0], 'grid': rows,
            'feasible_restorations': [row['restoration'] for row in eligible],
            'best_grid': best, 'continuous': continuous_class(parameters, eta)}


def elimination(matrix, rhs):
    """RREF with an explicit affine null space, including singular cases."""
    n = len(rhs)
    a = [list(row)+[rhs[i]] for i, row in enumerate(matrix)]
    pivots, lead = [], 0
    for col in range(n):
        selected = next((i for i in range(lead, n) if a[i][col]), None)
        if selected is None:
            continue
        a[lead], a[selected] = a[selected], a[lead]
        z = a[lead][col]; a[lead] = [v/z for v in a[lead]]
        for row in range(n):
            if row != lead:
                z = a[row][col]; a[row] = [v-z*w for v, w in zip(a[row], a[lead])]
        pivots.append(col); lead += 1
    if any(all(x == 0 for x in row[:-1]) and row[-1] != 0 for row in a):
        return {'status': 'inconsistent'}
    particular = [F(0)]*n
    for row, col in enumerate(pivots): particular[col] = a[row][-1]
    free = [col for col in range(n) if col not in pivots]
    nullspace = []
    for col in free:
        v = [F(0)]*n; v[col] = F(1)
        for row, pivot in enumerate(pivots): v[pivot] = -a[row][col]
        nullspace.append(v)
    return {'status': 'affine' if free else 'unique', 'particular': particular, 'nullspace': nullspace}


def graph_case(gamma, targets):
    adjacency = [[F(int(tuple(sorted((i, j))) in EDGE_SET)) if i != j else F(0) for j in range(4)] for i in range(4)]
    audits, equilibria = [], []
    for mask in range(16):
        active = [i for i in range(4) if mask & (1 << i)]
        matrix = [[F(i == j)+gamma*adjacency[i][j] for j in active] for i in active]
        solved = elimination(matrix, [targets[i] for i in active])
        row = {'positive_support': [i+1 for i in active], 'linear_system': solved}
        if solved['status'] == 'unique':
            x = [F(0)]*4
            for i, number in zip(active, solved['particular']): x[i] = number
            inactive = [gamma*sum(adjacency[i][j]*x[j] for j in range(4))-targets[i] for i in range(4) if i not in active]
            valid = all(x[i] > 0 for i in active) and all(s >= 0 for s in inactive)
            row.update({'candidate': x, 'inactive_slacks': inactive, 'is_equilibrium': valid})
            if valid:
                utility = [targets[i]*x[i]-x[i]*x[i]/2-gamma*x[i]*sum(adjacency[i][j]*x[j] for j in range(4)) for i in range(4)]
                potential = sum(targets[i]*x[i]-x[i]*x[i]/2 for i in range(4))-gamma*sum(x[i]*x[j] for i, j in EDGE_SET)
                equilibria.append({'actions': x, 'utility': utility, 'welfare': sum(utility), 'potential': potential})
        else:
            row['is_equilibrium'] = None
        audits.append(row)
    family = None
    if gamma == F(1, 2) and targets == [F(1)]*4:
        family = {'parameter': 'a', 'interval': ['0', '1'], 'actions': ['a', '1-a', 'a', '1-a'],
                  'potential': F(1), 'welfare_polynomial_coefficients_constant_linear_quadratic': [F(1), F(-2), F(2)],
                  'welfare_range': [F(1, 2), F(1)], 'complete_by': 'Opposite-reply equality and a+b=1; the two finite rows are endpoints only.'}
    return {'interaction': gamma, 'targets': targets, 'support_audits': audits,
            'isolated_or_endpoint_equilibria': equilibria, 'complete_family': family,
            'equilibrium_set_kind': 'continuum' if family else 'finite',
            'scope': 'Fixed four-cycle only; singular normalized boundary is handled analytically, not skipped.'}


def jsonify(value):
    if isinstance(value, F): return str(value)
    if type(value) is dict: return {k: jsonify(v) for k, v in value.items()}
    if type(value) in (tuple, list): return [jsonify(v) for v in value]
    return value


def run(data):
    p = validate(data)
    base = design(p, F(0))
    reference = baseline(p, F(1, 2))
    active = protocol(p, environment(p, review_law=p['repair']), (1, 1))
    changed = dict(p['repair']); changed['WN'] = changed['NW'] = p['changed']
    counter = protocol(p, environment(p, review_law=changed), (1, 1))
    none = protocol(p, environment(p, F(1, 2)), (0, 0))
    result = {'schema_version': 1, 'exact_number_format': 'rational strings; never rounded probabilities',
              'baseline': base, 'reference_restoration_half': reference,
              'garbling': [design(p, eta) for eta in p['etas']],
              'active_repair': active, 'changed_off_path_repair': counter,
              'repair_gain_over_reference_U': tuple(a-b for a, b in zip(active['U'], reference['U'])),
              'always_N_equilibrium': none,
              'paper': {'regular': graph_case(p['gamma'], [F(1)]*4),
                        'critical': graph_case(F(1, 2), [F(1)]*4),
                        'changed_target': graph_case(F(1, 2), [F(1), F(1), F(1), 1+p['epsilon']])},
              'limitations': ['Synthetic laws and common cardinal utility units, not estimated effects or cash accounts.',
                              'Grid and continuous restoration optima are class-restricted; no equilibrium-selection or global institution claim.',
                              'All-history proof is analytic; finite stationary-policy tables alone do not establish it.',
                              'The paper characterization is generic for finite enumeration; the exceptional family is explicit.',
                              'The supplied dossier does not certify learner paper reading, research novelty or professional competence.']}
    result = jsonify(result)
    json.dumps(result, allow_nan=False)
    return result


def protect_output(destination, protected):
    resolved = destination.resolve()
    for source in protected:
        require(resolved != source.resolve(), 'output aliases a protected input or implementation/documentation file')
        if destination.exists() and source.exists():
            require(not destination.samefile(source), 'output hard-links a protected file')


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=here/'v13-assessment-inputs.json')
    parser.add_argument('--output', type=Path, default=here/'v13-assessment-output.json')
    args = parser.parse_args()
    protected = [args.input, here/'v13-assessment-inputs.json', Path(__file__),
                 here/'v13-assessment-README.txt', here/'v13-assessment-manifest.json']
    protect_output(args.output, protected)
    result = run(strict_loads(args.input.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
