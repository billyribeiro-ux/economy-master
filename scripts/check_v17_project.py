"""Independent primitive model/data oracle and exact-nine author package check."""
import ast
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import runpy
import sys

FILES = ('content/assessments/parts/v17-project.html',
         'content/projects/v17-assessment-inputs.json',
         'content/projects/v17-assessment-analysis.py',
         'content/projects/v17-assessment-output.json',
         'content/projects/v17-assessment-manifest.json',
         'content/projects/v17-assessment-README.txt',
         'scripts/check_v17_project.py',
         'content/reviews/v17-project-author.json',
         'content/reviews/v17-project-sources.json')


def need(ok, message):
    if not ok:
        raise ValueError('V17 project: '+message)


def strict(text):
    def pairs(items):
        d = {}
        for k, v in items:
            need(k not in d, 'duplicate JSON key'); d[k] = v
        return d
    def reject(value):
        raise ValueError('nonfinite JSON')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


def pack(x):
    if isinstance(x, F):
        return x.numerator if x.denominator == 1 else str(x)
    if isinstance(x, (tuple, list)):
        return [pack(v) for v in x]
    if isinstance(x, dict):
        return {k: pack(v) for k, v in x.items()}
    return x


def primitive_model(row):
    a, b = map(F, row['values']); c = F(row['unit_cost']); budget = F(row['budget']); transfer = F(row['transfer'])
    # Enumerate all boundary candidates and verify both best-response equations.
    candidates = {F(0), max(F(0), a-c), max(F(0), b-c)}
    equilibria = [(x, y) for x in candidates for y in candidates
                  if x == max(F(0), a-c-y) and y == max(F(0), b-c-x)]
    need(bool(equilibria), 'primitive equilibrium exists')
    if a == b and a > c:
        equilibrium = ((a-c)/2, (a-c)/2); unique = False
    else:
        need(len(equilibria) == 1, 'unique unequal/boundary equilibrium'); equilibrium = equilibria[0]; unique = True
    private = sum(equilibrium)
    benefit = lambda value, quantity: quantity*(value-quantity/2)
    resource = lambda quantity: c*quantity
    surplus = lambda quantity: benefit(a, quantity)+benefit(b, quantity)-resource(quantity)
    candidates_g = {F(0), max(F(0), (a+b-c)/2)}
    efficient = max(candidates_g, key=surplus)
    prices = (a-efficient, b-efficient)
    payments = tuple(price*efficient for price in prices)
    old = tuple(benefit(value, private)-resource(q) for value, q in zip((a, b), equilibrium))
    new = tuple(benefit(value, efficient)-payment for value, payment in zip((a, b), payments))
    after = (new[0]-transfer, new[1]+transfer)
    gains = tuple(x-y for x, y in zip(after, old))
    affordable = min(efficient, budget/c)
    reasons = []
    if resource(efficient) > budget: reasons.append('efficient_quantity_exceeds_procurement_budget')
    if any(price < 0 for price in prices): reasons.append('negative_personalized_price_not_allowed_by_proposed_scheme')
    if transfer != 0 and not row['transfer_authorized']: reasons.append('compensating_transfer_has_no_assumed_authority')
    if any(x < 0 for x in gains): reasons.append('at_least_one_household_fails_participation_relative_to_selected_private_equilibrium')
    return {'id': row['id'], 'private_total': private, 'private_contributions': equilibrium,
            'private_equilibrium_unique': unique, 'equal_value_equilibrium_interval': [0, private] if not unique else None,
            'private_utilities': old, 'private_welfare': sum(old),
            'efficient_quantity': efficient, 'efficient_cost': resource(efficient),
            'efficient_welfare': surplus(efficient), 'welfare_gain': surplus(efficient)-sum(old),
            'personalized_prices': prices, 'payments': payments, 'payment_minus_cost': sum(payments)-resource(efficient),
            'utilities_before_transfer': new, 'utilities_after_transfer': after, 'participation_gains': gains,
            'transfer_interval_for_weak_participation': [old[1]-new[1], new[0]-old[0]],
            'budget_shortfall': max(F(0), resource(efficient)-budget),
            'budget_constrained_quantity': affordable, 'budget_constrained_welfare': surplus(affordable),
            'proposed_scheme_feasible': len(reasons) == 0, 'diagnostics': reasons}


def oracle(data):
    model_rows = [primitive_model(x) for x in data['models']]
    corrected = {(r['stage'], r['learner']): tuple(r['criterion_credit']) for r in data['responses']}
    original = dict(corrected)
    corrections = []
    for change in data['grading_versions']['corrections']:
        key = (change['stage'], change['learner']); j = data['criteria'].index(change['criterion'])
        p = list(original[key]); p[j] = change['old_credit']; original[key] = tuple(p)
        corrections.append({k: change[k] for k in ('stage', 'learner', 'criterion', 'old_credit', 'corrected_credit')})
        corrections[-1].update(change=change['corrected_credit']-change['old_credit'], reason=change['reason'])
    lookup = {(r['stage'], r['learner']): r for r in data['responses']}
    releases = {}
    for label, points in ((data['grading_versions']['old'], original), (data['grading_versions']['corrected'], corrected)):
        summaries = []
        for stage_record in data['stages']:
            stage = stage_record['id']; rows = []
            for learner in data['roster']:
                row = lookup[stage, learner]; credits = points[stage, learner]; score = sum(credits)
                rows.append({'learner': learner, 'status': row['status'], 'criterion_credit': credits,
                             'score': None if row['status'] == 'missing' else score, 'recorded_assessment_credit': score})
            available = [x['score'] for x in rows if x['score'] is not None]
            independent = [x['score'] for x in rows if x['status'] == 'independent']
            total = sum(x['recorded_assessment_credit'] for x in rows)
            summaries.append({'stage': stage, 'rows': rows, 'roster_n': len(rows), 'submitted_n': len(available),
                              'independent_n': len(independent), 'assisted_n': sum(x['status'] == 'assisted' for x in rows),
                              'missing_n': len(rows)-len(available), 'total_recorded_credit': total,
                              'full_roster_mean_recorded_credit': F(total, len(rows)),
                              'submitted_mean': F(sum(available), len(available)) if available else None,
                              'independent_mean': F(sum(independent), len(independent)) if independent else None,
                              'submitted_complete_n': available.count(8), 'independent_complete_n': independent.count(8),
                              'independent_complete_share': F(independent.count(8), len(independent)) if independent else None})
        releases[label] = summaries
    before, after = data['paired_stages']; pairs = []
    for learner in data['roster']:
        if all(lookup[s, learner]['status'] == 'independent' for s in (before, after)):
            left, right = (sum(corrected[s, learner]) for s in (before, after))
            pairs.append({'learner': learner, 'before': left, 'after': right, 'difference': right-left})
    task_points = {k: v for domain in data['project_domains'] for k, v in domain['tasks'].items()}
    result = {'schema': data['schema'], 'models': model_rows, 'grading': releases, 'corrections': corrections,
              'paired_independent': {'stages': [before, after], 'rows': pairs, 'n': len(pairs),
                   'mean_difference': F(sum(x['difference'] for x in pairs), len(pairs)) if pairs else None,
                   'interpretation': 'Descriptive same-learner score contrast across changed tasks; no causal teaching-effect identification.'},
              'project_scoring': {'domains': data['project_domains'], 'tasks': task_points, 'total': sum(task_points.values())},
              'evidence_status': {'observations': 'synthetic only', 'revision': 'prepared, not delivered', 'actual_learner_evaluation': 'not supplied', 'stipulated_observation_minutes': sum(e['minutes'][1]-e['minutes'][0] for e in data['observation']['events'])}}
    return pack(result)


def literal(text):
    def visit(n):
        if isinstance(n, ast.Tuple): return tuple(visit(x) for x in n.elts)
        if isinstance(n, ast.Constant) and type(n.value) is int: return F(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -visit(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div): return visit(n.left)/visit(n.right)
        raise ValueError('unsupported numeric literal')
    return visit(ast.parse(text.strip(), mode='eval').body)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.ids=[]; self.tasks=[]; self.answers=[]; self.sources=[]; self.links=[]; self.markers={}; self.active=None; self.tables={}; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); need(len(a)==len(attrs), 'duplicate attrs'); need(tag!='h1', 'part h1')
        if 'id' in a:
            need(a['id']=='project' or a['id'].startswith('project-'), 'project prefix'); self.ids.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack): self.tasks.append((a['id'], a['data-domain'], int(a['data-points'])))
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack), 'solution disclosure'); self.answers.append(a['data-solution-for'])
        if 'data-source' in a: self.sources.append((a['data-source'],a['href']))
        if 'href' in a: self.links.append(a['href'])
        for kind in ('input','result'):
            if 'data-'+kind in a:
                key=(kind,a['data-'+kind]); need(key not in self.markers and self.active is None, 'unique markers'); self.markers[key]=''; self.active=(tag,key)
        if tag=='table': self.table=a['id']; self.tables[self.table]=[]
        if tag=='tr': self.row=[]
        if tag in ('th','td'): self.cell=[]
        if tag not in ('br','hr','img','input','meta','link'): self.stack.append((tag,a))
    def handle_data(self, text):
        if self.active: self.markers[self.active[1]]+=text
        if self.cell is not None: self.cell.append(text)
    def handle_endtag(self, tag):
        need(bool(self.stack) and self.stack.pop()[0]==tag, 'balanced fragment')
        if self.active and self.active[0]==tag: self.active=None
        if tag in ('th','td'): self.row.append(''.join(self.cell).strip()); self.cell=None
        if tag=='tr': self.tables[self.table].append(self.row); self.row=None
        if tag=='table': self.table=None


def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    blobs={name:(root/name).read_bytes() for name in FILES}
    review=strict(blobs[FILES[7]].decode()); need(review['full_reading_complete'] and not review['open_material_findings'], 'full author review')
    need(set(review['payloads'])==set(FILES)-{FILES[7]}, 'eight nonself hashes')
    for name, binding in review['payloads'].items(): need(binding=={'bytes':len(blobs[name]),'sha256':hashlib.sha256(blobs[name]).hexdigest()}, 'author binding '+name)
    manifest=strict(blobs[FILES[4]].decode()); downloadable=(FILES[1],FILES[2],FILES[3],FILES[5]); need(set(manifest['payloads'])=={Path(x).name for x in downloadable}, 'four manifest hashes')
    for name in downloadable: need(manifest['payloads'][Path(name).name]=={'bytes':len(blobs[name]),'sha256':hashlib.sha256(blobs[name]).hexdigest()}, 'download binding')
    data=strict(blobs[FILES[1]].decode()); expected=oracle(data)  # Construct independently BEFORE loading/executing reader.
    stream=io.StringIO(); original=copy.deepcopy(data)
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        reader=runpy.run_path(str(root/FILES[2])); actual=reader['run'](data)
    need(not stream.getvalue() and data==original, 'quiet immutable API')
    count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,dict) or isinstance(b,dict):
            need(isinstance(a,dict) and isinstance(b,dict) and set(a)==set(b),'keys '+label)
            for key in a:eq(a[key],b[key],label+'/'+str(key))
        elif isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),'shape '+label)
            for i,(x,y) in enumerate(zip(a,b)):eq(x,y,label+'/'+str(i))
        else: count+=1; need(type(a)==type(b) and a==b if isinstance(a,bool) or isinstance(b,bool) else a==b,label)
    eq(actual,expected,'full primitive oracle'); eq(strict(blobs[FILES[3]].decode()),expected,'retained output')
    page=Page(); page.feed(blobs[FILES[0]].decode()); page.close(); need(not page.stack and page.active is None and len(page.ids)==len(set(page.ids)), 'complete unique HTML')
    need(page.answers==['project-task'+str(i) for i in range(1,8)], 'seven answers'); need([x[0] for x in page.tasks]==page.answers,'task pairing')
    task_domain={int(k):(d['id'],v) for d in data['project_domains'] for k,v in d['tasks'].items()}
    need(page.tasks==[('project-task'+str(i),*task_domain[i]) for i in range(1,8)],'additive rubric mapping')
    sources=strict(blobs[FILES[8]].decode())['sources']; need(set(page.sources)=={(s['id'],s['url']) for s in sources}, 'source routes')
    need(set(x for x in page.links if x.startswith('v17-assessment-'))=={Path(x).name for x in FILES[1:6]},'flat downloads')
    numbers={k:literal(v) for k,v in page.markers.items()}; used=set()
    def marker(kind,key,value): used.add((kind,key)); eq(pack(numbers[kind,key]),pack(value),'HTML '+key)
    by_id={x['id']:primitive_model(x) for x in data['models']}; base=by_id['base']
    for key in ('base','delayed'):
        r=next(x for x in data['models'] if x['id']==key); marker('input',key,tuple(map(F,r['values']+[r['unit_cost'],r['budget'],r['transfer']])))
    marker('result','base-model',(base['private_total'],base['efficient_quantity'],base['private_welfare'],base['efficient_welfare'],*base['personalized_prices'],*base['utilities_before_transfer']))
    marker('result','base-transfer-interval',base['transfer_interval_for_weak_participation']); marker('result','base-after-transfer',base['utilities_after_transfer'])
    def extra(values,c,budget,transfer=0): return primitive_model({'id':'extra','values':values,'unit_cost':c,'budget':budget,'transfer':transfer,'transfer_authorized':True})
    cost=extra([6,4],6,12); marker('result','cost-transfer',(cost['private_total'],cost['efficient_quantity'],cost['private_welfare'],cost['efficient_welfare'],*cost['personalized_prices']))
    marker('result','ug-hours',F(150+360,60)); marker('result','grad-hours',F(180+360,60))
    tie=by_id['equal_values']; marker('result','equal-values',(tie['private_total'],tie['efficient_quantity'],tie['private_welfare'],tie['efficient_welfare'],tie['private_utilities'][0],tie['utilities_before_transfer'][0]))
    corrected=expected['grading'][data['grading_versions']['corrected']]; old=expected['grading'][data['grading_versions']['old']]
    for stage in corrected: marker('result',stage['stage']+'-scores',[r['recorded_assessment_credit'] for r in stage['rows']])
    marker('result','old-baseline-scores',[r['recorded_assessment_credit'] for r in old[0]['rows']]); marker('result','summaries',[[F(str(s[k])) for k in ('total_recorded_credit','full_roster_mean_recorded_credit','submitted_mean','independent_mean')] for s in corrected])
    new=extra([8,4],6,18); marker('result','fresh-feedback-task',(new['private_total'],new['efficient_quantity'],new['private_welfare'],new['efficient_welfare'],*new['personalized_prices'],*new['private_utilities'],*new['utilities_before_transfer']))
    marker('result','paired-changes',[r['difference'] for r in expected['paired_independent']['rows']]); marker('result','paired-mean',F(str(expected['paired_independent']['mean_difference'])))
    budget=by_id['low_budget']; marker('result','budget-case',(budget['efficient_cost'],budget['budget_shortfall'],budget['budget_constrained_quantity'],budget['budget_constrained_welfare']))
    asymmetric=by_id['negative_price']; marker('result','negative-price',(asymmetric['efficient_quantity'],*asymmetric['personalized_prices']))
    supervision=extra([3,3],4,4); marker('result','supervision-transfer',(supervision['private_total'],supervision['efficient_quantity'],supervision['private_welfare'],supervision['efficient_welfare'],*supervision['personalized_prices']))
    revision=extra([6,4],4,12,1); marker('result','revision-exit',(*revision['utilities_after_transfer'],*revision['transfer_interval_for_weak_participation']))
    marker('result','task-points',[expected['project_scoring']['tasks'][str(i)] for i in range(1,8)]); need(used==set(numbers),'all numeric markers checked')
    for row,source in zip(page.tables['project-responses'][1:],data['responses']):
        text=row[2]; literal_part=text[:text.index(')')+1]; eq(pack(literal(literal_part)),source['criterion_credit'],'actual response table credit')
    need(len(page.tables['project-responses'])==19,'all eighteen responses')
    alternatives=0
    for values,c,budget,T in (([0,0],4,0,0),([3,3],4,4,0),([6,4],6,12,0),([4,6],4,12,0),([5,5],4,12,0),([6,4],4,10,2)):
        variant=copy.deepcopy(data); variant['models'][0].update(values=values,unit_cost=c,budget=budget,transfer=T); want=oracle(variant); prior=copy.deepcopy(variant)
        with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):got=reader['run'](variant)
        need(variant==prior and not stream.getvalue(),'alternative purity');eq(got,want,'alternative complete output');alternatives+=1
    empty=copy.deepcopy(data)
    for row in empty['responses']:
        if row['stage']=='immediate':row.update(status='missing',criterion_credit=[0,0,0,0],text='')
    want=oracle(empty)
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):got=reader['run'](empty)
    eq(got,want,'empty submitted/independent denominators');alternatives+=1
    invalid=0
    mutations=[lambda d:d['roster'].append(d['roster'][0]),lambda d:d['responses'].pop(),lambda d:d['responses'].append(copy.deepcopy(d['responses'][0])),lambda d:d['responses'][0].update(status='unknown'),lambda d:d['responses'][0].update(criterion_credit=[2,2,2,3]),lambda d:d['responses'][3].update(text='fabricated missing work'),lambda d:d['models'][0].update(unit_cost=0),lambda d:d['models'][0].update(values=[-1,4]),lambda d:d['models'][0].update(budget=-1),lambda d:d['models'][0].update(transfer_authorized='yes'),lambda d:d['grading_versions']['corrections'][0].update(corrected_credit=2),lambda d:d['project_domains'][0].update(points=19),lambda d:d['observation']['events'][1].update(minutes=[6,11])]
    for change in mutations:
        bad=copy.deepcopy(data);change(bad)
        try: reader['run'](bad)
        except (ValueError,TypeError,KeyError,ZeroDivisionError):invalid+=1
        else:raise ValueError('invalid input accepted')
    need(not stream.getvalue(),'reader quiet throughout')
    return {'volume':'v17','component':'project','status':'passed','runtime_files':9,'comparisons':count,'economic_cases':len(data['models']),'responses':len(data['responses']),'alternative_data_worlds':alternatives,'invalid_domains':invalid,'scope':'Full seven instructor artifacts/global proofs/source scopes separately read; complete independent primitive oracle before reader execution.'}


if __name__=='__main__':
    need(len(sys.argv)<=2,'usage checker [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
