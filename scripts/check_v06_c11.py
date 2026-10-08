"""Independent exact cash-flow, stock-bridge and regime audit; quiet check()."""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from check_v06_c01 import Chapter

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects'
PROGRAM = PROJECT/'v06-c11-external.py'
INPUT = PROJECT/'v06-c11-cases.json'


def need(test, message):
    if not test:
        raise ValueError(message)


def load_program():
    spec = importlib.util.spec_from_file_location('v06_c11_lab', PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_equal(output, targets, label):
    for key,value in targets.items():
        need(F(output[key]) == F(value), label+' '+key)


def check():
    text = (ROOT/'content/chapters/v06-c11.html').read_text()
    doc = Chapter(); doc.feed(text)
    need(not doc.stack and len(doc.ids)==len(set(doc.ids)), 'HTML stack/ids')
    need((doc.worked,doc.exercises,doc.solutions)==(3,8,8), 'chapter package')
    sources=json.loads((ROOT/'content/reviews/v06-c11-sources.json').read_text())
    need(set(doc.sources)=={r['id'] for r in sources}, 'source coverage')
    for name in ('cases.json','external.py','output.json','README.txt'):
        need('href="v06-c11-'+name+'"' in text, 'flat download '+name)
        need((PROJECT/('v06-c11-'+name)).is_file(),'download exists '+name)
    for phrase in ('white-cover','statistical discrepancy','earned income','transfer income',
                   'resident','event-date','nonnegative-rate domain','supplied expectation'):
        need(phrase in text,'required accounting/model scope '+phrase)

    data=json.loads(INPUT.read_text())
    silence=io.StringIO()
    with redirect_stdout(silence):
        lab=load_program()
        result=lab.run(data)
    need(silence.getvalue()=='','quiet import/run')
    json.dumps(result,allow_nan=False)
    need(result==json.loads((PROJECT/'v06-c11-output.json').read_text()),'preserved output')

    # Direct source-and-use totals; income and finance checked independently.
    ca=100-120+8-5+7-2;ka=2
    private=100-117+8-5+7-2+2+12;reserves=-3;liabilities=12
    need(ca+ka==private+reserves-liabilities==-10,'double-entry target')
    exact_equal(result['ledger'],dict(FA=-10,statistical_discrepancy=0,assets_close=170,
                liabilities_close=216,NFA_open=-50,NFA_close=-46,net_valuation=15,
                net_other_volume=-1,GNDI=208,saving=28,saving_minus_investment=-12),'ledger')
    need(170-216 == 150-200+(private+reserves-liabilities)+(19-4)-1,'IIP bridge')
    # Exercises 1/2 independent of the benchmark's worked input.
    ex_ca=80-95+6-4+3-5;ex_ka=2-1
    need((ex_ca,ex_ka,-2-12,(-2-12)-ex_ca-ex_ka)==(-15,1,-14,0),'exercise1 accounts')
    need((-1-12)-ex_ca-ex_ka==1,'exercise1 discrepancy')
    need(200==150+30+35+80-95 and 200+2-2-150-30-35==ex_ca,'exercise1 saving')
    a1=180+6+8-2;l1=210+15-4+1
    need((a1,l1,a1-l1)==(192,222,-30),'exercise2 gross positions')
    need(a1-l1-(180-210)==(6-15)+(8+4)+(-2-1),'exercise2 NFA bridge')

    for row in data['currency_cases']:
        out=result['currency_cases'][row['id']]
        e0,e1,a,l,ai,li=[F(row[k]) for k in ('e0','e1','asset_F','liability_F','asset_interest_F','liability_interest_F')]
        # Reconstruct two chronological states and then append interest.
        initial=(e0*a,e0*l);revalued=(e1*a,e1*l)
        final=(revalued[0]+e1*ai,revalued[1]+e1*li)
        need(F(out['NFA_open'])==initial[0]-initial[1], 'currency opening')
        need(F(out['NFA_close'])==final[0]-final[1], 'currency closing')
        need(F(out['net_valuation'])==(revalued[0]-initial[0])-(revalued[1]-initial[1]),'currency valuation')
        need(F(out['NFA_close'])-F(out['NFA_open'])==F(out['FA'])+F(out['net_valuation']),'currency bridge')
    exact_equal(result['currency_cases']['interest_after_revaluation'],
                dict(liabilities_close=315,liability_transactions=15,CA=-15,FA=-15,net_valuation=-100),'interest timing')

    exact_equal(result['ppp_cases']['worked_fixed_quote'],
                dict(q0=1,q1='52/55',relative_PPP_quote='55/26',relative_PPP_depreciation='3/52'),'worked PPP')
    exact_equal(result['ppp_cases']['exercise_baskets'],
                dict(q0=1,q1='21/20',real_depreciation='1/20',nominal_depreciation='1/10',
                     inverse_quote_change='-1/11',relative_PPP_quote='44/21',relative_PPP_depreciation='1/21'),'exercise PPP')
    # Rebase either price index by a constant: changes survive, levels do not.
    ppp_data=deepcopy(data['ppp_cases'][1]);ppp_data['P0']='360';ppp_data['P1']='396'
    rebased=lab.ppp(ppp_data)
    need(rebased['q0']==F(1,3) and rebased['q1']==F(7,20),'rebased real levels')
    need(rebased['real_depreciation']==F(1,20) and rebased['relative_PPP_quote']==F(44,21),'rebase-invariant changes')

    # Explicit financed cash flows at each forward; no printed parity formula
    # reused for the expected profits below.
    direct_profits=[F(102)*F(21,10)-F(210),F(102)*F(81,50)-F(162),F(162)-F(102)*F(39,25)]
    need(direct_profits==[F(21,5),F(81,25),F(72,25)],'covered cash-flow targets')
    for name,field,target in [('worked_high_forward','borrow_H_profit','21/5'),
                              ('exercise_high_forward','borrow_H_profit','81/25'),
                              ('exercise_low_forward','borrow_F_profit','72/25')]:
        need(F(result['parity_cases'][name][field])==F(target),'covered strategy '+name)
    parity_cases=0
    for spot in (F(1,2),F(3,2),F(3)):
        for rh in (F(99,100),F(1),F(11,10)):
            for rf in (F(49,50),F(1),F(6,5)):
                # Choose contract quote by equating a 120H home payoff to a
                # fully hedged foreign deposit; perturb it both directions.
                foreign_units=F(120)/spot*rf
                fair=F(120)*rh/foreign_units
                for shift in (F(-1,100),F(0),F(1,100)):
                    case=dict(e=str(spot),RH=str(rh),RF=str(rf),forward=str(fair+shift),
                              home_principal='120',foreign_principal=str(F(120)/spot))
                    out=lab.parity(case)
                    need(out['borrow_H_profit']==foreign_units*shift,'covered perturbation')
                    need(out['borrow_F_profit']==-out['borrow_H_profit'],'reverse financing')
                    parity_cases+=1
    # Two equally likely terminal spot states, evaluated payoff by payoff.
    state_returns=[F(102)*F(9,5)/200,F(102)*F(12,5)/200]
    expected=sum(state_returns)/2
    u=result['uncovered']
    need([F(v) for v in u['state_gross_home_returns']]==state_returns,'uncovered states')
    exact_equal(u,dict(mean_spot='21/10',expected_depreciation='1/20',UIP_depreciation='1/34',
                      expected_gross_home_return=expected,expected_excess_foreign_return='21/1000',
                      expected_reciprocal='35/72',reciprocal_expectation='10/21'),'uncovered expectation')
    need(F(35,72)-F(10,21)==F(5,504),'reciprocal Jensen gap')
    need(F(200)*state_returns[0]-210==F(-132,5),'unhedged downside')
    first=F(1)/F(201,100)*F(101,100)*F(101,50)-F(53,50)
    second=F(199,100)*F(26,25)-F(103,100)*F(103,50)
    need((first,second)==(F(-226,5025),F(-261,5000)),'bid ask executable payoffs')
    exact_equal(result['bid_ask'],dict(profit_per_H_borrowed=first,profit_per_F_borrowed_in_H=second),'bid ask output')

    # Verify all ORIGINAL regime conditions, including mark-to-market equity;
    # derive feasibility independently from inequalities before API comparison.
    prim=data['regime_primitives'];regime_cases=0
    for kind in ('peg','float'):
        for d in (F(0),F(55),F(57),F(60),F(61),F(95),F(96)):
            for rf in (F(1),F(21,20),F(27,25),F(2)):
                out=lab.regime(prim,dict(regime=kind,D=str(d),RF=str(rf)))
                feasible=(0 < 100-100*(rf-1) and d<=100-100*(rf-1)) if kind=='peg' else (0<d+40<=100)
                need(out['feasible']==feasible,'regime boundary classification')
                if feasible:
                    h,i,r,e,k=[out[x] for x in ('H','i_H','R','e','K')]
                    need(h==100-100*i and d+e*r==h+k,'money and balance sheet')
                    need(r>=0 and i>=0,'regime admissibility')
                    if kind=='peg':
                        need(e==2 and k==0 and 1+i==rf,'credible peg parity')
                    else:
                        need(r==20 and k==(e-2)*20 and (1+i)*e==2*rf,'float equity and expectation')
                regime_cases+=1
    exact_equal(result['regime_cases']['purchase_float'],dict(H=97,i_H='3/100',R=20,e='210/103',K='80/103'),'worked float')
    exact_equal(result['regime_cases']['purchase_peg'],dict(H=95,R=19,e=2,K=0),'worked peg')
    exact_equal(result['regime_cases']['foreign_rate_peg'],dict(H=92,R='37/2',i_H='2/25'),'exercise peg')
    exact_equal(result['regime_cases']['foreign_rate_float'],dict(H=95,i_H='1/20',e='72/35',K='8/7'),'exercise float')
    need(not result['regime_cases']['reserve_failure']['feasible'],'reserve exhaustion')
    need(not result['regime_cases']['currency_bound_failure']['feasible'],'currency bound')
    need(-5-(-7+1)==1 and -20-5+4-1==-22 and F(3,2)*F(26,25)==F(39,25) and (95-91)/2==2,'retention')

    # Valid mutations must change the economically relevant output.
    changed=deepcopy(data);changed['ledger']['rows'][-1]['private_assets']='19';changed['ledger']['rows'][-1]['liabilities']='19'
    moved=lab.run(changed)['ledger']
    need(moved['FA']=='-10' and moved['NFA_close']=='-46' and moved['assets_close']=='177' and moved['liabilities_close']=='223','gross lending mutation')
    changed=deepcopy(data);changed['regime_primitives']['future_spot_mean']='21/10'
    moved=lab.run(changed)['regime_cases']['purchase_float']
    need(moved['e']=='441/206' and moved['H']=='97' and moved['K']!='80/103','expectations mutation')

    # API and CLI reject the same malformed inputs; no mutation of source data.
    alterations=[('schema',None,'wrong'),('synthetic',None,False),
                 ('currency_cases',('e1',0),'0'),('currency_cases',('asset_F',0),'-1'),
                 ('ppp_cases',('P1',0),'0'),('parity_cases',('RH',0),'0'),
                 ('parity_cases',('forward',0),'-1'),('parity_cases',('e',0),True),
                 ('parity_cases',('RF',0),1.02),('parity_cases',('RF',0),'1/0'),
                 ('regime_cases',('regime',0),'unknown'),('regime_cases',('RF',0),'9/10')]
    bad=[]
    for group,field,value in alterations:
        altered=deepcopy(data)
        if field is None:altered[group]=value
        else:altered[group][field[1]][field[0]]=value
        bad.append(altered)
    for group,key,value in [('bid_ask','spot_bid','3'),('bid_ask','RH_lend','2'),
                            ('regime_primitives','P','0'),('regime_primitives','chi','0'),
                            ('ledger','GDP','201'),('ledger','opening_assets','-1')]:
        altered=deepcopy(data);altered[group][key]=value;bad.append(altered)
    altered=deepcopy(data);altered['uncovered']['states'][0]['probability']='3/4';bad.append(altered)
    altered=deepcopy(data);altered['ledger']['rows'][0]['CA']='101';bad.append(altered)
    altered=deepcopy(data);altered['parity_cases'][1]['id']=altered['parity_cases'][0]['id'];bad.append(altered)
    for altered in bad:
        try:lab.run(altered)
        except ValueError:pass
        else:raise ValueError('invalid API input accepted')
    with tempfile.TemporaryDirectory(prefix='v06-c11-check-') as temporary:
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        proc=subprocess.run([sys.executable,str(PROGRAM)],cwd=temporary,env=env,capture_output=True,text=True)
        need(proc.returncode==0 and not proc.stderr and json.loads(proc.stdout)==result,'arbitrary-CWD CLI')
        target=Path(temporary)/'bad.json'
        for altered in bad:
            target.write_text(json.dumps(altered))
            proc=subprocess.run([sys.executable,str(PROGRAM),str(target)],env=env,capture_output=True,text=True)
            need(proc.returncode==2 and not proc.stdout and proc.stderr.startswith('input error:'),'invalid CLI contract')

    return {'chapter':'v06-c11','status':'passed','checks':[
        'Three worked examples, eight full solutions, answered retention, five scoped primary sources and four flat downloads',
        'Exact transaction rows, GDP/saving bridge, discrepancy signs, gross position and NFA reconciliations',
        'Principal revaluation before interest, exact PPP growth and quote inversion, independent exercise anchors',
        'Two funded covered strategies, exact expected uncovered returns, reciprocal expectation and executable bid/ask bounds',
        'Original money-demand, central-bank balance-sheet, equity, parity and regime-feasibility residuals',
        'Preserved output, quiet import/run, strict JSON, arbitrary-CWD CLI, valid gross-position/expectation mutations and invalid API/CLI rejection'],
        'covered_parameter_cases':parity_cases,'regime_parameter_cases':regime_cases,'invalid_cases':len(bad),
        'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        'limitations':['Checks concern original maintained synthetic models, not empirical identification, executable current market opportunities or a forecast.',
                       'The full prose and economic assumptions require editorial audit; the two spread inequalities are not a universal market completeness test.',
                       'No visual/mobile/print QA, external human certification, shared acceptance or publication is claimed.']}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
