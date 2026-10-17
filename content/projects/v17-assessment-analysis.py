"""Exact synthetic teaching evidence audit; standard library, no external data."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

NAMES = ('v17-assessment-inputs.json', 'v17-assessment-analysis.py',
         'v17-assessment-README.txt', 'v17-assessment-manifest.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_loads(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('nonfinite JSON value')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


def number(value):
    require(type(value) in (int, str), 'exact numbers must be integers or rational strings')
    if isinstance(value, str):
        parts = value.split('/')
        require(1 <= len(parts) <= 2 and all(p.lstrip('-').isdigit() for p in parts), 'invalid rational')
    return Fraction(value)


def packed(value):
    if isinstance(value, Fraction):
        return value.numerator if value.denominator == 1 else str(value)
    if isinstance(value, (tuple, list)):
        return [packed(x) for x in value]
    if isinstance(value, dict):
        return {k: packed(v) for k, v in value.items()}
    return value


def model(case):
    require(set(case) == {'id', 'values', 'unit_cost', 'budget', 'transfer', 'transfer_authorized'}, 'model fields')
    require(isinstance(case['id'], str) and case['id'], 'model id')
    require(isinstance(case['values'], list) and len(case['values']) == 2, 'two households')
    a = tuple(number(x) for x in case['values'])
    c, budget, transfer = (number(case[k]) for k in ('unit_cost', 'budget', 'transfer'))
    require(min(a) >= 0 and c > 0 and budget >= 0 and transfer >= 0, 'economic domain')
    require(type(case['transfer_authorized']) is bool, 'transfer authority flag')
    total = max(Fraction(0), max(a)-c)
    if a[0] == a[1]:
        contributions = (total/2, total/2)
        unique = total == 0
    elif a[0] > a[1]:
        contributions = (total, Fraction(0))
        unique = True
    else:
        contributions = (Fraction(0), total)
        unique = True
    benefit = lambda value, g: value*g-g*g/2
    private_utilities = tuple(benefit(x, total)-c*q for x, q in zip(a, contributions))
    efficient = max(Fraction(0), (sum(a)-c)/2)
    prices = tuple(x-efficient for x in a)
    payments = tuple(x*efficient for x in prices)
    utilities = tuple(benefit(x, efficient)-payment for x, payment in zip(a, payments))
    after_transfer = (utilities[0]-transfer, utilities[1]+transfer)
    gains = tuple(new-old for new, old in zip(after_transfer, private_utilities))
    welfare = lambda g: (sum(a)-c)*g-g*g
    constrained = min(efficient, budget/c)
    reasons = []
    if c*efficient > budget:
        reasons.append('efficient_quantity_exceeds_procurement_budget')
    if min(prices) < 0:
        reasons.append('negative_personalized_price_not_allowed_by_proposed_scheme')
    if transfer and not case['transfer_authorized']:
        reasons.append('compensating_transfer_has_no_assumed_authority')
    if min(gains) < 0:
        reasons.append('at_least_one_household_fails_participation_relative_to_selected_private_equilibrium')
    return {'id': case['id'], 'private_total': total, 'private_contributions': contributions,
            'private_equilibrium_unique': unique,
            'equal_value_equilibrium_interval': [0, total] if not unique else None,
            'private_utilities': private_utilities, 'private_welfare': welfare(total),
            'efficient_quantity': efficient, 'efficient_cost': c*efficient,
            'efficient_welfare': welfare(efficient), 'welfare_gain': welfare(efficient)-welfare(total),
            'personalized_prices': prices, 'payments': payments,
            'payment_minus_cost': sum(payments)-c*efficient,
            'utilities_before_transfer': utilities, 'utilities_after_transfer': after_transfer,
            'participation_gains': gains, 'transfer_interval_for_weak_participation':
                [private_utilities[1]-utilities[1], utilities[0]-private_utilities[0]],
            'budget_shortfall': max(Fraction(0), c*efficient-budget),
            'budget_constrained_quantity': constrained, 'budget_constrained_welfare': welfare(constrained),
            'proposed_scheme_feasible': not reasons, 'diagnostics': reasons}


def run(data):
    require(isinstance(data, dict) and data.get('schema') == 'v17-teaching-rehearsal-1', 'schema')
    roster = data['roster']
    require(isinstance(roster, list) and roster and all(isinstance(x, str) and x for x in roster), 'roster')
    require(len(set(roster)) == len(roster), 'duplicate learner')
    models = [model(x) for x in data['models']]
    model_ids = [x['id'] for x in models]
    require(len(model_ids) == len(set(model_ids)) and models, 'duplicate/empty models')
    criteria = data['criteria']
    require(criteria == ['private_scale', 'planner_scale', 'welfare', 'individual_interpretation'], 'rubric criteria')
    require(type(data['points_per_criterion']) is int and data['points_per_criterion'] == 2, 'rubric points')
    stages = data['stages']; stage_ids = [x['id'] for x in stages]
    require(stage_ids == ['baseline', 'immediate', 'delayed'], 'ordered stages')
    require(all(x['model'] in model_ids and isinstance(x['timing'], str) and x['timing'] for x in stages), 'stage model/timing')
    responses = {}
    for row in data['responses']:
        require(set(row) == {'stage', 'learner', 'status', 'criterion_credit', 'text'}, 'response fields')
        key = (row['stage'], row['learner'])
        require(key[0] in stage_ids and key[1] in roster and key not in responses, 'response key')
        require(row['status'] in ('independent', 'assisted', 'missing'), 'response status')
        points = row['criterion_credit']
        require(isinstance(points, list) and len(points) == 4 and all(type(x) is int and x in (0, 2) for x in points), 'criterion credit')
        require(isinstance(row['text'], str), 'response text')
        if row['status'] == 'missing':
            require(not row['text'] and sum(points) == 0, 'missing response must have no work/credit')
        else:
            require(bool(row['text'].strip()), 'submitted response has no text')
        responses[key] = row
    require(set(responses) == {(s, learner) for s in stage_ids for learner in roster}, 'explicit complete roster-stage grid required')
    versions = data['grading_versions']
    require(versions['old'] != versions['corrected'], 'distinct rubric versions')
    overrides = {}
    corrections = []
    for change in versions['corrections']:
        key = (change['stage'], change['learner'])
        require(key in responses and responses[key]['status'] != 'missing', 'correction target')
        require(change['criterion'] in criteria, 'correction criterion')
        index = criteria.index(change['criterion']); target = key+(index,)
        require(target not in overrides and change['old_credit'] in (0, 2) and type(change['old_credit']) is int, 'correction unique/credit')
        require(type(change['corrected_credit']) is int and change['corrected_credit'] == responses[key]['criterion_credit'][index], 'correction agrees with annotated evidence')
        require(change['old_credit'] != change['corrected_credit'] and change['reason'], 'substantive version change')
        overrides[target] = change['old_credit']
        corrections.append({'stage': key[0], 'learner': key[1], 'criterion': change['criterion'],
                            'old_credit': change['old_credit'], 'corrected_credit': change['corrected_credit'],
                            'change': change['corrected_credit']-change['old_credit'], 'reason': change['reason']})
    outputs = {}
    for version in ('old', 'corrected'):
        stage_outputs = []
        for stage in stage_ids:
            rows = []
            for learner in roster:
                row = responses[stage, learner]; points = list(row['criterion_credit'])
                if version == 'old':
                    points = [overrides.get((stage, learner, i), value) for i, value in enumerate(points)]
                score = sum(points)
                rows.append({'learner': learner, 'status': row['status'], 'criterion_credit': points,
                             'score': None if row['status'] == 'missing' else score,
                             'recorded_assessment_credit': score})
            submitted = [x for x in rows if x['score'] is not None]
            independent = [x for x in rows if x['status'] == 'independent']
            total_credit = sum(x['recorded_assessment_credit'] for x in rows)
            mean = lambda rows: Fraction(sum(x['score'] for x in rows), len(rows)) if rows else None
            complete = lambda rows: sum(x['score'] == 8 for x in rows)
            stage_outputs.append({'stage': stage, 'rows': rows, 'roster_n': len(roster),
                'submitted_n': len(submitted), 'independent_n': len(independent),
                'assisted_n': sum(x['status'] == 'assisted' for x in rows),
                'missing_n': len(roster)-len(submitted), 'total_recorded_credit': total_credit,
                'full_roster_mean_recorded_credit': Fraction(total_credit, len(roster)),
                'submitted_mean': mean(submitted), 'independent_mean': mean(independent),
                'submitted_complete_n': complete(submitted), 'independent_complete_n': complete(independent),
                'independent_complete_share': Fraction(complete(independent), len(independent)) if independent else None})
        outputs[versions[version]] = stage_outputs
    before, after = data['paired_stages']
    require(before in stage_ids and after in stage_ids and before != after, 'paired stages')
    pairs = []
    for learner in roster:
        left, right = responses[before, learner], responses[after, learner]
        if left['status'] == right['status'] == 'independent':
            b, a = sum(left['criterion_credit']), sum(right['criterion_credit'])
            pairs.append({'learner': learner, 'before': b, 'after': a, 'difference': a-b})
    domain_ids = ['alignment_explanation', 'course_seminar_design', 'assessment_feedback', 'communication_supervision', 'observation_portfolio']
    domains = data['project_domains']
    require([x['id'] for x in domains] == domain_ids, 'architecture domains')
    tasks = {}
    for domain in domains:
        require(type(domain['points']) is int and domain['points'] == 20, 'twenty-point domain')
        require(all(k in set(map(str, range(1, 8))) and type(v) is int and v > 0 for k, v in domain['tasks'].items()), 'task allocations')
        require(sum(domain['tasks'].values()) == 20, 'domain sum')
        for key, value in domain['tasks'].items():
            require(key not in tasks, 'task has one domain'); tasks[key] = value
    require(set(tasks) == set(map(str, range(1, 8))), 'seven mapped tasks')
    require(data['observation']['status'] == 'synthetic_stipulated' and data['observation']['revision_status'] == 'prepared_not_delivered' and data['observation']['followup_observation'] == 'absent', 'evidence status boundary')
    result = {'schema': data['schema'], 'models': models, 'grading': outputs, 'corrections': corrections,
              'paired_independent': {'stages': [before, after], 'rows': pairs, 'n': len(pairs),
                    'mean_difference': Fraction(sum(x['difference'] for x in pairs), len(pairs)) if pairs else None,
                    'interpretation': 'Descriptive same-learner score contrast across changed tasks; no causal teaching-effect identification.'},
              'project_scoring': {'domains': domains, 'tasks': tasks, 'total': sum(tasks.values())},
              'evidence_status': {'observations': 'synthetic only', 'revision': 'prepared, not delivered', 'actual_learner_evaluation': 'not supplied'}}
    result = packed(result)
    json.dumps(result, allow_nan=False)
    return result


def guard_output(input_path, output_path):
    script = Path(__file__).resolve()
    protected = {script, input_path.resolve()}
    for directory in (script.parent, input_path.resolve().parent):
        protected.update(directory/name for name in NAMES)
    resolved = output_path.resolve()
    for path in protected:
        require(resolved != path.resolve(), 'output aliases a protected payload')
        if output_path.exists() and path.exists():
            require(not output_path.samefile(path), 'output hardlinks a protected payload')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path, default=Path(__file__).resolve().with_name(NAMES[0]))
    parser.add_argument('output', nargs='?', type=Path, default=Path(__file__).resolve().with_name('v17-assessment-output.json'))
    args = parser.parse_args()
    guard_output(args.input, args.output)
    result = run(strict_loads(args.input.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
