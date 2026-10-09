#!/usr/bin/env python3
"""Independent exact checks for Larch; check() is silent and strict-JSON safe."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def check():
    root = Path(__file__).resolve().parents[1]
    projects = root/'content/projects'
    prefix = 'v09-c12-'
    comparisons = 0
    rejections = 0
    groups = []

    def eq(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if isinstance(expected,F):
            actual = F(actual)
        if actual != expected:
            raise AssertionError(f'{label}: {actual!r} != {expected!r}')

    def near(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if not math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12):
            raise AssertionError(label)

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        spec = importlib.util.spec_from_file_location('larch_checked',projects/(prefix+'analysis.py'))
        lab = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab)
        data = json.loads((projects/(prefix+'inputs.json')).read_text())
        before = copy.deepcopy(data)
        result = lab.run(data)
    eq(stream.getvalue(),'','silent import/run')
    eq(data,before,'input unchanged')
    eq(json.loads(json.dumps(result,allow_nan=False)),result,'strict JSON return')
    frozen = json.loads((projects/(prefix+'output.json')).read_text())
    eq(result,frozen,'entire reference output')
    groups.append('quiet public API and complete frozen-output regression')

    def independently_rank(d):
        """Price every terminal state directly, then take central moments of cash."""
        W,g,lot = F(d['wealth']),F(d['cash_half_year_factor']),F(d['lot'])
        states = [(F(s['probability']),F(s['equity_return']),F(s['bond_return'])) for s in d['moment_states']]
        p = d['policy']
        bx,by = (F(d['benchmark'][k]) for k in ('equity','bond'))
        def cost(x,y):
            return F(d['entry_fee']['equity'])*abs(x-F(d['initial']['equity'])) + \
                F(d['entry_fee']['bond'])*abs(y-F(d['initial']['bond']))
        bc = W-bx-by-cost(bx,by)
        L1,L2 = (F(d['planning_grants'][k]) for k in ('t1','t2'))
        bpay = [bx*(1+e)+by*(1+b)+(bc*g-L1)*g-L2 for _,e,b in states]
        bmean = sum(s[0]*r for s,r in zip(states,bpay))
        feasible = []
        all_count = 0
        for i in range(int(F(d['caps']['equity'])/lot)+1):
            for j in range(int(F(d['caps']['bond'])/lot)+1):
                all_count += 1
                x,y = i*lot,j*lot
                K = cost(x,y)
                c = W-x-y-K
                terminal = [x*(1+e)+y*(1+b)+(c*g-L1)*g-L2 for _,e,b in states]
                mean = sum(s[0]*r for s,r in zip(states,terminal))
                var = sum(s[0]*(r-mean)**2 for s,r in zip(states,terminal))
                avar = sum(s[0]*((r-br)-(mean-bmean))**2 for s,r,br in zip(states,terminal,bpay))
                minimum = max([L1]+[F(s['grant_t1']) for s in d['design_stresses']])+F(p['cash_buffer'])
                if c < 0 or g*c < minimum or var > F(p['variance_limit']) or avar > F(p['active_variance_limit']):
                    continue
                if any(x*(1+F(s['equity_return']))+y*(1+F(s['bond_return'])) +
                       (g*c-F(s['grant_t1']))*g-F(s['grant_t2']) < F(p['reserve_floor'])
                       for s in d['design_stresses']):
                    continue
                score = mean-F(p['gamma'])*var/(2*W)
                feasible.append({'equity':x,'bond':y,'fee':K,'cash':c,'expected_reserve':mean,
                                 'variance':var,'active_variance':avar,'criterion':score})
        feasible.sort(key=lambda p:(-p['criterion'],p['variance'],p['fee'],p['equity'],p['bond']))
        return all_count,feasible

    probabilities = [F(s['probability']) for s in data['moment_states']]
    returns = [[F(s[k]) for k in ('equity_return','bond_return')] for s in data['moment_states']]
    means = [sum(p*r[i] for p,r in zip(probabilities,returns)) for i in range(2)]
    cov = [[sum(p*r[i]*r[j] for p,r in zip(probabilities,returns))-means[i]*means[j]
            for j in range(2)] for i in range(2)]
    eq(sum(probabilities),F(1),'probability total')
    for i in range(2):
        eq(result['moment_witness']['mean'][i],means[i],'raw witness mean')
        for j in range(2):
            eq(result['moment_witness']['covariance'][i][j],cov[i][j],'raw cross moment')
    eq(means,[F('.1'),F('.06')],'exercise1 means')
    eq(cov,[[F('.04'),F('.006')],[F('.006'),F('.01')]],'exercise1 covariance')
    eq(result['moment_witness']['determinant'],F(91,250000),'SPD determinant')
    n,ranking = independently_rank(data)
    eq(n,3111,'finite candidate count')
    eq(len(ranking),28,'feasible count')
    eq(result['optimization']['candidates'],n,'enumerated count')
    eq(result['optimization']['feasible_count'],len(ranking),'feasible count returned')
    for expected,actual in zip(ranking,result['optimization']['feasible_ranked']):
        for key,value in expected.items():
            eq(actual[key],value,'independent complete ranking '+key)
    winner = ranking[0]
    eq((winner['equity'],winner['bond']),(F(370),F(430)),'global choice')
    eq(winner['criterion']-ranking[1]['criterion'],F('.089195'),'runner-up gap')
    groups.append('finite state law and all 3111 candidates / 28 feasible ranks')

    x,y,c = F(370),F(430),F('199.15')
    contribution = [x*(F('.04')*x+F('.006')*y),y*(F('.006')*x+F('.01')*y)]
    for got,want in zip(result['risk_decomposition']['variance_contributions'],contribution):
        eq(got,want,'Euler variance component')
    eq(sum(contribution),F('9234.2'),'variance sum')
    eq(result['risk_decomposition']['active_variance_contributions'],['153/5','18/5'],'active components')
    near(sum(result['risk_decomposition']['volatility_contributions_kCU_approx']),math.sqrt(9234.2),'Euler volatility sum')
    near(result['risk_decomposition']['active_volatility_kCU_approx'],math.sqrt(34.2),'active square root')
    bench = result['benchmark']
    for key,value in [('fee',F(1)),('cash',F(199)),('expected_reserve',F('865.4999')),
                      ('variance',F(9920)),('criterion',F('845.6599'))]:
        eq(bench[key],value,'exercise2 benchmark '+key)
    eq(bench['feasible'],True,'benchmark implements its mandate')
    eq(bench['stresses']['inflation_funding']['terminal_reserve'],F('653.1999'),'benchmark stressed cash')
    eq(F(200)*F('1.0201')-F(199)*F('1.0201'),F('1.0201'),'misstated fee cost')
    eq(result['inherited_position']['active_variance'],F(400),'inherited active breach')
    eq(result['inherited_position']['variance'],F(6640),'inherited total variance')
    eq(result['inherited_position']['violations'],['active_risk'],'inherited exact violation')
    eq(winner['criterion']-F(bench['criterion']),F('.324615'),'preference comparison')
    crossing = (ranking[0]['expected_reserve']-ranking[1]['expected_reserve'])*2000 / \
        (ranking[0]['variance']-ranking[1]['variance'])
    eq(crossing,F(69599,12940),'exercise3 pair crossing')
    eq(ranking[0]['expected_reserve']-crossing*ranking[0]['variance']/2000,
       ranking[1]['expected_reserve']-crossing*ranking[1]['variance']/2000,'pair tie')
    groups.append('cash benchmark, total/active risk and preference tradeoffs')

    selected = result['optimization']['selected']
    for name,want in [('equity_fall',F('712.152915')),('inflation_funding',F('654.252915'))]:
        eq(selected['stresses'][name]['terminal_reserve'],want,'design reserve')
        eq(selected['stresses'][name]['payments_funded'],True,'design payment feasibility')
    eq(F(selected['expected_reserve'])-F('654.252915'),F('92.5')+F('77.4')+F('40.3'),'stress difference ledger')
    for key,want in [('no_line_keep_buffer',F('181.1415')),('max_line_keep_buffer',F('206.1415')),
                     ('max_line_allow_zero_cash',F('226.1415'))]:
        eq(result['date1_bill_thresholds'][key],want,'bill threshold')
    g=F('1.01')
    scenario=copy.deepcopy(data['design_stresses'][1]);scenario['grant_t1']='200'
    p=lab.position(data,370,430)
    D=200+20-c*g
    mid=lab.ledger(data,p,scenario,D)
    eq(D,F('18.8585'),'exercise4 minimum draw')
    eq(mid['cash_after_t1'],F(20),'exercise4 buffer')
    eq(mid['loan_repayment_t2'],F('20.36718'),'exercise4 full repayment')
    eq(mid['terminal_reserve'],F('632.73282'),'exercise4 reserve')
    eq(mid['reserve_floor_gap'],F('17.26718'),'exercise4 floor gap')
    for bill,D,expect_buffer,expect_payment in [('181.1415','0',True,True),
        ('181.1416','0',False,True),('206.1415','25',True,True),
        ('206.1416','25',False,True),('226.1415','25',False,True),('226.1416','25',False,False)]:
        s=copy.deepcopy(scenario);s['grant_t1']=bill
        z=lab.ledger(data,p,s,F(D))
        eq(z['buffer_gap_t1']==0,expect_buffer,'exact/adjacent cash boundary')
        eq(z['payment_gap_t1']==0,expect_payment,'payment boundary')
        if not expect_payment:
            eq(z['cash_after_t1'],None,'unfunded cash unavailable')
            eq(z['terminal_reserve'],None,'unfunded terminal unavailable')
    groups.append('design stresses and adjacent dated cash/payment boundaries')

    reverse=result['reverse_stress']
    failed=reverse['no_external_funding_max_line']
    eq(failed['payment_gap_t1'],F('13.8585'),'reverse unpaid bill')
    eq(failed['buffer_gap_t1'],F('33.8585'),'reverse buffer gap')
    eq(failed['terminal_reserve'],None,'reverse no fictional terminal path')
    eq(reverse['buffer_only_external_funding_max_line']['terminal_reserve'],F('606.3'),'partial repair')
    eq(reverse['buffer_only_external_funding_max_line']['reserve_floor_gap'],F('43.7'),'remaining terminal gap')
    x0,x25=F(15229417,202000),F(15579417,202000)
    eq(reverse['both_constraints_no_line']['minimum_contribution'],x0,'exercise5 zero-line contribution')
    eq(reverse['both_constraints_max_line']['minimum_contribution'],x25,'exercise5 full-line contribution')
    eq(x25-x0,F(175,101),'borrowing spread cost')
    eq(reverse['minimum_external_funding']['draw'],F(0),'best repair draw')
    for D in [F(0),F(5),F(12),F(25)]:
        outside=(650-F('673.1')-(c*g-240)*g+60+(F('1.08')-g)*D)/g
        repaired=lab.repair(data,p,data['reverse_stress'],D)
        eq(repaired['minimum_contribution'],outside,'direct both-date funding')
        eq(repaired['ledger']['terminal_reserve'],F(650),'repaired reserve closure')
        eq(repaired['ledger']['policy_cash_and_floor_pass'],True,'repair all constraints')
        lower=lab.ledger(data,p,data['reverse_stress'],D,outside-F(1,1000))
        eq(lower['reserve_floor_gap'],F('0.00101'),'binding funding minus epsilon')
    # A transfer case where the optimal draw is an interior crossing, not zero.
    crossing_case={'name':'crossing','equity_return':'.10','bond_return':'.06','grant_t1':'220','grant_t2':'182'}
    # A=862.8, terminal requirement leaves cash (650+182-862.8)/1.01=-30.8/1.01:
    # this makes no external contribution necessary at sufficient draw only if
    # the buffer is affordable. Instead choose L2 so both constraints cross at D=10.
    crossing_case['grant_t2']=str(F('862.8')+g*20-650-F('1.08')*10)
    cross=lab.cheapest_repair(data,p,crossing_case)
    eq(cross['draw'],F(10),'repair kink draw')
    eq(cross['minimum_contribution'],F('28.8585'),'repair kink contribution')
    eq(cross['ledger']['cash_after_t1'],F(20),'kink interim equality')
    eq(cross['ledger']['terminal_reserve'],F(650),'kink terminal equality')
    for D in [F(0),F(9),F(11),F(25)]:
        eq(lab.repair(data,p,crossing_case,D)['minimum_contribution']>cross['minimum_contribution'],True,'kink beats neighbors')
    groups.append('reverse stress, minimum external funding and interior repair kink')

    report=result['execution_report']
    for key,val in [('fee',F('.75')),('cash',F('209.25')),('variance',F('8890.6')),('active_variance',F('58.6'))]:
        eq(report['actual_position'][key],val,'one-lot actual '+key)
    for key,val in [('target_ledger',F('850.352915')),('actual_ledger',F('849.455925')),('benchmark_ledger',F('853.4999'))]:
        eq(report[key]['terminal_reserve'],val,'matched report reserve')
    gaps=report['reserve_gap_decomposition']
    eq(gaps['policy_selection'],F('-3.146985'),'policy gap')
    eq(gaps['implementation'],F(101,10)*g*g-10*F('1.12'),'funded missed-fill gap')
    eq(F(gaps['policy_selection'])+F(gaps['implementation']),F(gaps['total_vs_benchmark']),'complete decomposition')
    two=copy.deepcopy(data);two['report_fixture']['unfilled_equity_lots']=2
    two_report=lab.run(two)['execution_report']
    for key,want in [('equity',F(350)),('fee',F('.65')),('cash',F('219.35')),('variance',F(8555)),('active_variance',F(91))]:
        eq(two_report['actual_position'][key],want,'exercise6 '+key)
    eq(two_report['actual_ledger']['terminal_reserve'],F('848.558935'),'exercise6 reserve')
    eq(two_report['reserve_gap_decomposition']['implementation'],F('-1.79398'),'exercise6 implementation')
    eq(two_report['reserve_gap_decomposition']['total_vs_benchmark'],F('-4.940965'),'exercise6 overall gap')
    eq(two_report['initial_active_budget_breach'],True,'exercise6 honest breach')
    # Missing interim valuations do not produce a claimed TWR in the interface.
    eq(any('twr' in key.lower() for key in report),False,'no invented interim-return report')
    groups.append('one/two unfilled lots, cash costs and matched outcome reports')

    interventions=[('gamma2',{'gamma':'2'},None,(400,400,F('855.5799'))),
                   ('gamma6',{'gamma':'6'},None,(370,400,F('836.85293'))),
                   ('zero_active',{'active_variance_limit':'0'},None,(400,400,F('845.6599'))),
                   ('mean_shift',{},F('-.02'),(370,430,F('838.584515')))]
    for name,policy,shift,anchor in interventions:
        d=copy.deepcopy(data);d['policy'].update(policy)
        if shift is not None:
            for state in d['moment_states']:
                state['equity_return']=str(F(state['equity_return'])+shift)
        r=lab.run(d)
        _,independent=independently_rank(d)
        eq(r['optimization']['feasible_count'],len(independent),name+' feasible count')
        for key,val in independent[0].items():
            eq(r['optimization']['selected'][key],val,name+' full independent optimum '+key)
        eq(independent[0]['equity'],F(anchor[0]),name+' equity anchor')
        eq(independent[0]['bond'],F(anchor[1]),name+' bond anchor')
        eq(independent[0]['criterion'],anchor[2],name+' score anchor')
        if shift is not None:
            eq(r['moment_witness']['covariance'],result['moment_witness']['covariance'],'exercise7 centered covariance')
            eq(r['optimization']['selected']['expected_reserve'],F('857.052915'),'exercise7 revised mean')
        if name=='zero_active':
            eq(len(independent),1,'SPD zero-active uniqueness')
    # Honest report boundaries when the supplied reporting branch is inapplicable/unfunded.
    invalid_report=copy.deepcopy(data);invalid_report['report_fixture']['unfilled_equity_lots']=100
    eq(lab.run(invalid_report)['execution_report']['available'],False,'inapplicable partial-buy branch')
    invalid_report=copy.deepcopy(data);invalid_report['report_fixture']['grant_t1']='500'
    eq(lab.run(invalid_report)['execution_report']['reserve_gap_decomposition'],None,'unfunded report no attribution')
    eq(F(660)-F('654.252915'),F('5.747085'),'retention revised floor gap')
    groups.append('preference, authority and forecast interventions with independent optima')

    def reject(edit,label):
        nonlocal rejections
        d=copy.deepcopy(data);edit(d)
        try:
            lab.run(d)
        except ValueError:
            rejections += 1
        else:
            raise AssertionError('accepted invalid input: '+label)
    reject(lambda d:d.update(wealth=True),'boolean')
    reject(lambda d:d.update(wealth=1000.0),'float')
    reject(lambda d:d.update(wealth='NaN'),'nonfinite')
    reject(lambda d:d.update(extra='ignored'),'unknown field')
    reject(lambda d:d['conventions'].update(unit='USD'),'currency contradiction')
    reject(lambda d:d['conventions'].update(line='initial borrowing permitted'),'financing contradiction')
    reject(lambda d:d.update(lot='0'),'zero lot')
    reject(lambda d:d.update(lot='0.01'),'oversized enumeration')
    reject(lambda d:d['benchmark'].update(equity='405'),'non-grid benchmark')
    reject(lambda d:d['initial'].update(equity='900'),'excess inherited assets')
    reject(lambda d:d['entry_fee'].update(equity='-0.01'),'negative fee')
    reject(lambda d:d.update(line_repayment_factor='1.00'),'loan below reinvestment factor')
    reject(lambda d:d.update(line_capacity='1001'),'unbounded line')
    reject(lambda d:d['policy'].update(gamma='0'),'zero gamma')
    reject(lambda d:d['policy'].update(active_variance_limit='-1'),'negative risk limit')
    reject(lambda d:d['planning_grants'].update(t1='-1'),'negative grant')
    reject(lambda d:d['moment_states'][0].update(probability='0'),'zero probability')
    reject(lambda d:d['moment_states'][0].update(probability='1/2'),'probability total')
    reject(lambda d:[s.update(equity_return='0') for s in d['moment_states']],'singular covariance')
    reject(lambda d:d['moment_states'][0].update(bond_return='-1.01'),'limited liability')
    reject(lambda d:d['design_stresses'][1].update(name='equity_fall'),'duplicate scenario')
    reject(lambda d:d['report_fixture'].update(unfilled_equity_lots=True),'boolean unfilled lots')
    reject(lambda d:d['policy'].update(reserve_floor='660'),'retention infeasible comparator')
    for D,X in [(F(26),F(0)),(F(-1),F(0)),(F(0),F(-1))]:
        try:
            lab.ledger(data,p,data['reverse_stress'],D,X)
        except ValueError:
            rejections += 1
        else:
            raise AssertionError('invalid funding helper accepted')
    groups.append('strict finite-domain and contradictory-contract rejection')

    class Fragment(HTMLParser):
        def __init__(self):
            super().__init__();self.ids=[];self.worked=0;self.h1=0;self.ex=0;self.words=[]
            self.in_solutions=False;self.solution_lists=0;self.list_depth=0
            self.solution_items=0;self.in_solution_item=False;self.solution_headings=[]
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if 'id' in a:self.ids.append(a['id'])
            if tag=='h1':self.h1+=1
            if tag=='aside' and 'worked' in a.get('class','').split():self.worked+=1
            if tag=='li' and a.get('id','').startswith('exercise-'):self.ex+=1
            if tag=='details' and 'solutions' in a.get('class','').split():self.in_solutions=True
            if self.in_solutions and tag=='ol':
                if self.list_depth==0:self.solution_lists+=1
                self.list_depth+=1
            if self.in_solutions and tag=='li' and self.list_depth==1:
                self.solution_items+=1;self.in_solution_item=True
            if tag=='h3' and a.get('id','').startswith('solution-'):
                self.solution_headings.append((a['id'],self.solution_items if self.in_solution_item else 0))
        def handle_endtag(self,tag):
            if self.in_solutions and tag=='li' and self.list_depth==1:self.in_solution_item=False
            if self.in_solutions and tag=='ol':self.list_depth-=1
            if self.in_solutions and tag=='details':self.in_solutions=False
        def handle_data(self,text):self.words.extend(text.split())
    fragment=Fragment();fragment.feed((root/'content/chapters/v09-c12.html').read_text())
    eq(fragment.h1,0,'fragment no duplicate builder h1')
    eq(fragment.worked,4,'four worked cases')
    eq(fragment.ex,8,'eight complete problem prompts')
    eq(len(fragment.ids),len(set(fragment.ids)),'unique chapter anchors')
    eq(all('solution-'+str(i) in fragment.ids for i in range(1,9)),True,'eight solution anchors')
    eq(fragment.solution_lists,1,'one ordered solution list')
    eq(fragment.solution_items,8,'eight ordered solution items')
    eq(fragment.solution_headings,[('solution-'+str(i),i) for i in range(1,9)],'each solution anchor inside its ordered item')
    refs=json.loads((root/'content/reviews/v09-c12-sources.json').read_text())
    canonical={s['id']:s for s in json.loads((root/'content/sources.json').read_text())}
    for source in refs:
        if source['id']!='v09-c12-cfa-ips':
            eq(source,canonical[source['id']],'exact reused source record')
    manifest=json.loads((projects/(prefix+'manifest.json')).read_text())
    eq({r['file'] for r in manifest['files']},{prefix+x for x in ['inputs.json','analysis.py','output.json','README.txt']},'four distributed payloads')
    for item in manifest['files']:
        blob=(projects/item['file']).read_bytes()
        eq(len(blob),item['bytes'],'manifest bytes')
        eq(hashlib.sha256(blob).hexdigest(),item['sha256'],'manifest SHA256')
    groups.append('chapter package, source reuse and distributed provenance hashes')

    with tempfile.TemporaryDirectory(prefix='larch-v09-c12-') as tmp:
        directory=Path(tmp)
        for item in manifest['files']:
            shutil.copyfile(projects/item['file'],directory/item['file'])
        for flags in [[],['-O']]:
            proc=subprocess.run([sys.executable,'-I']+flags+[str(directory/(prefix+'analysis.py')),
                                '--input',str(directory/(prefix+'inputs.json'))],
                                cwd=directory,text=True,capture_output=True,timeout=40)
            eq(proc.returncode,0,'portable process return')
            eq(proc.stderr,'','portable process stderr')
            eq(json.loads(proc.stdout),result,'portable whole report')
        out=directory/'separate-result.json'
        proc=subprocess.run([sys.executable,'-I',str(directory/(prefix+'analysis.py')),
                             '--input',str(directory/(prefix+'inputs.json')),'--output',str(out)],
                             cwd=directory,text=True,capture_output=True,timeout=40)
        eq(proc.returncode,0,'output CLI return')
        eq(proc.stdout+proc.stderr,'','output CLI quiet')
        eq(json.loads(out.read_text()),result,'output CLI full equality')
    groups.append('isolated offline normal/optimized and output-file CLI execution')
    return {'chapter':'v09-c12','status':'passed','groups':len(groups),
            'comparisons':comparisons,'domain_rejections':rejections,
            'details':groups,'chapter_words':len(fragment.words),
            'limits':'Exact synthetic finite model and source/package checks; no empirical, legal or human certification.'}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
