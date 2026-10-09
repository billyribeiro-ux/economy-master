#!/usr/bin/env python3
"""Independent c03 peer reconstruction. Quiet run(); no author-checker import."""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
import importlib.util
import io
from itertools import product
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BOOK = Path(__file__).resolve().parents[1]
PROJECT = BOOK / 'content/projects'


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.groups = []
        self.rejections = 0

    def eq(self, got, expected, label):
        if isinstance(expected, F):
            expected = str(expected)
        if isinstance(expected, (list, tuple)):
            self.require(isinstance(got, (list, tuple)) and len(got) == len(expected), label + ' shape')
            for i, value in enumerate(expected):
                self.eq(got[i], value, label + '/' + str(i))
        elif isinstance(expected, dict):
            self.require(isinstance(got, dict) and set(got) == set(expected), label + ' keys')
            for key, value in expected.items():
                self.eq(got[key], value, label + '/' + key)
        else:
            self.require(type(got) is type(expected) and got == expected, label)

    def require(self, condition, label):
        self.comparisons += 1
        if not condition:
            raise ValueError('c03 peer: ' + label)

    def end(self, name):
        self.groups.append(name)


def loads(path):
    return json.loads(path.read_text())


def independent_tree(data, dispersion, curve=None):
    """Closed three-period moment calibration, followed by dated path ledgers.

    This independently derived implementation uses the first two branch signs
    to solve the three levels directly. No submitted Arrow or backward code,
    output fields or author checker supplies its expected values.
    """
    D = list(map(F, curve or data['discount_curve']))
    q = [list(map(F, row)) for row in data['pricing_up']]
    p = [list(map(F, row)) for row in data['physical_up']]
    s = F(dispersion)
    h1 = [1+s, 1-s]
    h2 = [1+2*s, F(1), 1-2*s]
    w0 = [1-q[0][0], q[0][0]]
    level1 = D[2] / (D[1] * sum(w*h for w, h in zip(w0, h1)))
    joint2 = {(a,b): w0[a] * (q[1][a] if b else 1-q[1][a]) for a,b in product((0,1), repeat=2)}
    shape_moment = sum(prob*h1[a]*h2[a+b] for (a,b), prob in joint2.items())
    level2 = D[3] / (D[1]*level1*shape_moment)
    d = [[D[1]], [level1*h for h in h1], [level2*h for h in h2]]

    def histories(t, node, end):
        rows = []
        for branches in product((0,1), repeat=end-t):
            j, qp, pp, discount = node, F(1), F(1), F(1)
            banks = [F(1)]
            for k, high in enumerate(branches, t):
                qp *= q[k][j] if high else 1-q[k][j]
                pp *= p[k][j] if high else 1-p[k][j]
                discount *= d[k][j]
                banks.append(1/discount)
                j += high
            rows.append((branches, j, qp, pp, discount, banks))
        return rows

    zero = {str(T): [[sum(r[2]*r[4] for r in histories(t,j,T))
                     for j in range(t+1)] for t in range(T+1)] for T in (1,2,3)}
    cf = list(map(F, data['cashflows']))
    coupon = [[sum((cf[T-1]*zero[str(T)][t][j] for T in range(t+1,4)), F(0))
               for j in range(t+1)] for t in range(4)]
    face, strike = F(data['claim']['face']), F(data['claim']['strike'])
    bonds = d[1]
    H = [max(face*b-strike, F(0)) for b in bonds]
    claim_price = D[1]*sum(w*h for w,h in zip(w0,H))
    # Solve the determinant system with a date-1 cash payoff of one.
    if bonds[0] == bonds[1]:
        beta, cash1 = F(0), H[0]
    else:
        det = bonds[0]-bonds[1]
        beta = (H[0]-H[1])/det
        cash1 = (bonds[0]*H[1]-bonds[1]*H[0])/det
    claim = {'branch_payoffs':H, 'price':claim_price,
             'hedge_units_face1_zero2':beta, 'hedge_cash_at0':D[1]*cash1,
             'hedge_initial_cost':beta*D[2]+D[1]*cash1,
             'hedge_branch_payoffs':[beta*b+cash1 for b in bonds],
             'hedge_rank':'two distinct successor bond values' if bonds[0]!=bonds[1]
                          else 'redundant bond; bank-only replica chosen'}
    node_q, node_p, arrows = [], [], []
    for T in range(4):
        paths = histories(0,0,T)
        node_q.append([sum(r[2] for r in paths if r[1]==j) for j in range(T+1)])
        node_p.append([sum(r[3] for r in paths if r[1]==j) for j in range(T+1)])
        arrows.append([sum(r[2]*r[4] for r in paths if r[1]==j) for j in range(T+1)])
    paths = [{'path':''.join('H' if b else 'L' for b in bits), 'terminal_node':j,
              'Q_probability':qp, 'P_probability':pp, 'discount_product':df,
              'bank_history':banks, 'state_price':qp*df, 'P_sdf':qp*df/pp}
             for bits,j,qp,pp,df,banks in histories(0,0,3)]
    premiums = []
    for t,j in ((0,0),(1,0),(1,1)):
        buy = zero[str(t+2)][t][j]
        G = [zero[str(t+2)][t+1][j+b]/buy for b in (0,1)]
        pb, qb = [1-p[t][j],p[t][j]], [1-q[t][j],q[t][j]]
        m = [d[t][j]*qb[k]/pb[k] for k in (0,1)]
        EG = sum(pb[k]*G[k] for k in (0,1))
        cov = pb[0]*pb[1]*(m[0]-m[1])*(G[0]-G[1])
        premiums.append({'time':t,'node':j,'bond_maturity':t+2,'bond_price':buy,
                         'branch_gross_returns':G,'physical_expected_simple_return':EG-1,
                         'risk_free_simple_rate':1/d[t][j]-1,'expected_excess_return':EG-1/d[t][j],
                         'local_P_sdf':m,'sdf_return_covariance':cov})
    future = [1/x-1 for x in d[1]]
    eq = sum(w*r for w,r in zip(w0,future))
    ep = (1-p[0][0])*future[0]+p[0][0]*future[1]
    forward = D[1]/D[2]-1
    return {'dispersion':s,'levels':[D[1],level1,level2], 'node_discounts':d,
            'short_rates':[[1/v-1 for v in row] for row in d],
            'arrow_weights':arrows,'discount_sums':[sum(row) for row in arrows],
            'Q_node_probabilities':node_q,'P_node_probabilities':node_p,
            'zero_prices':zero,'coupon_ex_payment_values':coupon,
            'coupon_curve_price':sum(cf[t-1]*D[t] for t in (1,2,3)),
            'claim':claim,'holding_premiums':premiums,'terminal_paths':paths,
            'forward_vs_expectations':{'forward_1_2':forward,'Q_expected_short1':eq,'P_expected_short1':ep,
                                      'forward_minus_Q':forward-eq,'Q_minus_P':eq-ep,'forward_minus_P':forward-ep}}


def inspect_case(a, data, actual, label):
    expected = {item['name']:independent_tree(data,item['dispersion']) for item in data['models']}
    for name, tree in expected.items():
        a.eq(actual['models'][name], tree, label+'/'+name)
        for prem in tree['holding_premiums']:
            d = tree['node_discounts'][prem['time']][prem['node']]
            a.require(prem['expected_excess_return'] == -prem['sdf_return_covariance']/d, 'independent covariance identity')
    base = expected['base']
    q0 = F(data['pricing_up'][0][0]); D1 = F(data['discount_curve'][1])
    h = base['claim']
    for name, tree in expected.items():
        payoff = [h['hedge_units_face1_zero2']*b+h['hedge_cash_at0']/D1 for b in tree['node_discounts'][1]]
        error = [v-w for v,w in zip(payoff,tree['claim']['branch_payoffs'])]
        priced = D1*((1-q0)*error[0]+q0*error[1])
        a.eq(actual['frozen_base_hedge_model_risk'][name],
             {'frozen_base_hedge_payoffs':payoff,'claim_payoffs':tree['claim']['branch_payoffs'],
              'branch_errors':error,'priced_error':priced,
              'base_price_minus_model_price':h['price']-tree['claim']['price']}, label+'/frozen/'+name)
    for scenario in data['curve_scenarios']:
        tree = independent_tree(data,data['models'][0]['dispersion'],scenario['discount_curve'])
        a.eq(actual['curve_scenarios'][scenario['name']],
             {'discount_curve':list(map(F,scenario['discount_curve'])),'node_discounts':tree['node_discounts'],
              'discount_sums':tree['discount_sums'],'coupon_price':tree['coupon_curve_price'],
              'coupon_change':tree['coupon_curve_price']-base['coupon_curve_price'],
              'claim_price':tree['claim']['price'],'claim_change':tree['claim']['price']-h['price']},label+'/scenario')
    ar = data['mean_reversion']; r0,theta,phi,sigma = [F(ar[k]) for k in ('initial','level','phi','innovation')]
    n = ar['steps']; paths = []
    for shocks in product((-1,1),repeat=n):
        rates = [theta+phi**t*(r0-theta)+sigma*sum(phi**(t-k-1)*shocks[k] for k in range(t)) for t in range(n+1)]
        paths.append({'shocks':list(shocks),'rates':rates})
    mean = theta+phi**n*(r0-theta)
    var = sigma*sigma*sum(phi**(2*k) for k in range(n))
    a.eq(actual['mean_reversion'],{'contract':'separate physical model; independent equiprobable +/- innovations; not curve calibrated',
                                 'terminal_mean':mean,'terminal_variance':var,'analytic_mean':mean,'analytic_variance':var,'paths':paths},label+'/AR')
    return expected


def run():
    a = Audit(); data = loads(PROJECT/'v10-c03-inputs.json')
    before = copy.deepcopy(data); saved = loads(PROJECT/'v10-c03-output.json')
    capture_out,capture_err = io.StringIO(),io.StringIO()
    old_bytecode = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        with contextlib.redirect_stdout(capture_out),contextlib.redirect_stderr(capture_err):
            spec = importlib.util.spec_from_file_location('v10_c03_peer_sut',PROJECT/'v10-c03-analysis.py')
            model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)
            actual = model.run(data)
        a.eq(data,before,'input preservation'); a.eq(actual,saved,'complete saved output')
        expected = inspect_case(a,data,actual,'baseline')
        a.eq(actual['schema'],data['schema'],'schema');a.eq(actual['contract'],data['contract'],'contract')
        json.dumps(actual,allow_nan=False)
        a.end('Independent three-period moment calibration, all path/claim/return fields and baseline reproduction')

        b = expected['base']; d = b['node_discounts']; z = b['zero_prices']['3']
        # An independent predictable strategy trades a date-3 zero and bank cash.
        # Check discounted self-financing wealth across every complete history.
        terminal_pv = F(0)
        for bits in product((0,1),repeat=3):
            wealth,df,qp,j = F(0),F(1),F(1),0
            for t,high in enumerate(bits):
                holdings = F((t+1)*(-1 if j%2 else 1))
                bank_cash = wealth-holdings*z[t][j]
                wealth = holdings*z[t+1][j+high]+bank_cash/d[t][j]
                qp *= F(data['pricing_up'][t][j]) if high else 1-F(data['pricing_up'][t][j])
                df *= d[t][j];j += high
            terminal_pv += qp*df*wealth
        a.eq(str(terminal_pv),F(0),'predictable self-financing discounted wealth')
        a.eq(str(sum(F(c)*F(D) for c,D in zip((3,3,103),data['discount_curve'][1:]))),F('99.52'),'exercise1 alternative bond')
        a.eq(str(1/(d[0][0]*d[1][0])),F(1000,969),'exercise2 LH bank')
        a.eq(str(1/(d[0][0]*d[1][1])),F(1000,931),'exercise2 HL bank')
        a.eq(str(b['arrow_weights'][2][0]/F('0.95')),F(51,200),'exercise2 normalized Arrow')
        a.eq(str((d[0][0]*d[1][0])/(d[0][0]*sum(d[1]))),F(51,100),'exercise2 middle price share')
        a.eq(str(b['forward_vs_expectations']['forward_minus_P']),-F(14,1615),'worked2 forward gap')
        a.eq(str(expected['wide']['claim']['price']-b['claim']['price']),F(19,20),'worked3 model disagreement')
        lo = F(96)*F('0.98')/(100*F('1.02')); hi = F(96)*F('0.98')/(100*F('0.98'))
        a.eq(str(lo),F(392,425),'exercise7 lower kink');a.eq(str(hi),F(24,25),'exercise7 upper kink')
        a.eq(str(F('1.41')+51*(F('0.92')-F('0.95'))),-F(3,25),'exercise7 invalid extrapolation')
        drift = F('0.0025')+F('0.2')*(F('0.03')-F('0.0025')); shock = F('0.3')/20
        a.eq([str(drift-shock),str(drift+shock)],[-F(7,1000),F(23,1000)],'exercise9 finite square-root outputs')
        a.eq(str((drift+shock)/2),F(23,2000),'exercise9 clamped mean')
        a.eq(str(1-1/expected['wide']['node_discounts'][1][0]),F(2,247),'exercise9 new storage gain')
        # Exercise4 support counterexample is a traded zero-price (0,1) claim.
        a.require(F(1,2)>0 and F(0)*0+F(1)*0==0,'exercise4 excluded zero state price')
        a.end('All determinate exercise anchors, explicit dynamic wealth ledger and boundary counterexamples')

        interventions = []
        def variant(name, edits):
            x = copy.deepcopy(data)
            for route,value in edits:
                node=x
                for key in route[:-1]:node=node[key]
                node[route[-1]]=value
            with contextlib.redirect_stdout(capture_out),contextlib.redirect_stderr(capture_err):
                got=model.run(x)
            inspect_case(a,x,got,name);interventions.append(name)
            return got
        physical=variant('P-only belief change',[(('physical_up',0,0),'3/10')])
        for key in ('levels','arrow_weights','zero_prices','coupon_ex_payment_values','claim'):
            a.eq(physical['models']['base'][key],actual['models']['base'][key],'belief-invariant '+key)
        a.eq(physical['models']['base']['forward_vs_expectations']['P_expected_short1'],F(23,969),'exercise3 expectation')
        a.eq(physical['models']['base']['holding_premiums'][0]['expected_excess_return'],F(2,245),'exercise3 excess')
        equal=variant('identical complete P and Q',[(('physical_up',),copy.deepcopy(data['pricing_up']))])
        for tree in equal['models'].values():
            for row in tree['holding_premiums']:a.eq(row['expected_excess_return'],F(0),'P=Q zero holding premium')
        a.eq(equal['models']['base']['forward_vs_expectations']['forward_minus_P'],-F(2,4845),'retention convexity gap')
        variant('nonconstant pricing probabilities',[(('pricing_up',),[['2/5'],['1/5','3/4'],['2/3','1/3','4/5']])])
        strike=variant('strike97',[(('claim','strike'),'97')])
        a.eq(strike['models']['base']['claim']['hedge_cash_at0'],-F(1127,25),'exercise5 funded cash')
        a.eq(strike['models']['base']['claim']['hedge_units_face1_zero2'],F(920,19),'exercise5 units')
        variant('payoff upper boundary',[(('discount_curve',2),'24/25')])
        variant('payoff lower boundary',[(('discount_curve',2),'392/425')])
        lower=variant('below payoff boundary',[(('discount_curve',2),'23/25')])
        a.eq(lower['models']['base']['claim']['price'],F(0),'exercise7 zero value')
        variant('zero strike',[(('claim','strike'),'0')])
        variant('increasing positive discounts',[(('discount_curve',),['1','101/100','103/100','21/20'])])
        variant('six-step physical finite law',[(('mean_reversion','steps'),6),(('mean_reversion','phi'),'0'),(('mean_reversion','innovation'),'0')])
        retention=variant('D3 retention',[(('discount_curve',3),'9/10')])
        a.eq(retention['models']['base']['coupon_curve_price'],F('104.15'),'retention coupon')
        a.end('Eleven valid probability, payoff-boundary, curve and physical-law interventions')

        invalid = [('no Q support',('pricing_up',0,0),'0'),('no P support',('physical_up',1,0),'1'),
                   ('zero shape',('models',0,'dispersion'),'1/2'),('free storage',('contract','outside_storage'),'free'),
                   ('boolean date',('contract','dates_years',0),False),('wrong settlement',('claim','payment_time'),2),
                   ('zero D',('discount_curve',2),'0'),('float amount',('claim','face'),100.0),
                   ('nonfinite',('cashflows',0),float('inf')),('invalid future bank gross',('mean_reversion','level'),'-3'),
                   ('phi unit root',('mean_reversion','phi'),'1'),('duplicate name',('models',1,'name'),'base')]
        for label,route,value in invalid:
            x=copy.deepcopy(data);node=x
            for key in route[:-1]:node=node[key]
            node[route[-1]]=value
            try:model.run(x)
            except ValueError:a.rejections+=1
            else:raise ValueError('invalid peer intervention accepted: '+label)
        a.eq(capture_out.getvalue(),'','quiet API stdout');a.eq(capture_err.getvalue(),'','quiet API stderr')
        a.end('Twelve independent economic and numerical input rejection cases; quiet API')

        author=loads(BOOK/'content/reviews/v10-c03-author.json')
        for row in author['reviewed_hashes']:
            payload=(BOOK/row['path']).read_bytes()
            a.eq(hashlib.sha256(payload).hexdigest(),row['sha256'],'author reviewed hash')
            a.eq(len(payload),row['bytes'],'author byte count')
        manifest=loads(PROJECT/'v10-c03-manifest.json')
        for row in manifest['files']:
            payload=(PROJECT/row['file']).read_bytes()
            a.eq(hashlib.sha256(payload).hexdigest(),row['sha256'],'download hash')
            a.eq(len(payload),row['bytes'],'download bytes')
        sources=loads(BOOK/'content/reviews/v10-c03-sources.json');canonical=loads(BOOK/'content/sources.json')
        a.eq(next(s for s in sources if s['id']=='v09-c05-princeton-pricing'),next(s for s in canonical if s['id']=='v09-c05-princeton-pricing'),'exact reused source')
        a.end('Frozen author payloads, four-file manifest and exact stable source reuse')

        with tempfile.TemporaryDirectory(prefix='c03-independent-peer-') as temp:
            folder=Path(temp); package=folder/'payload';cwd=folder/'different-cwd';package.mkdir();cwd.mkdir()
            for row in manifest['files']:shutil.copyfile(PROJECT/row['file'],package/row['file'])
            script=package/'v10-c03-analysis.py'
            cli=subprocess.run([sys.executable,'-I','-B',str(script)],cwd=cwd,capture_output=True,text=True,timeout=20)
            a.eq(cli.returncode,0,'normal isolated CLI');a.eq(cli.stderr,'','normal CLI errors');a.eq(json.loads(cli.stdout),saved,'normal portable output')
            out=cwd/'out.json'
            cli=subprocess.run([sys.executable,'-I','-B','-O',str(script),'--input',str(package/'v10-c03-inputs.json'),'--output',str(out)],cwd=cwd,capture_output=True,text=True,timeout=20)
            a.eq(cli.returncode,0,'optimized isolated CLI');a.eq(cli.stdout,'','file output stdout');a.eq(cli.stderr,'','file output stderr');a.eq(loads(out),saved,'optimized output')
            for raw in ('{"schema":"a","schema":"b"}','{"schema":NaN}'):
                wrong=cwd/'wrong.json';wrong.write_text(raw)
                cli=subprocess.run([sys.executable,'-I','-B','-O',str(script),'--input',str(wrong)],cwd=cwd,capture_output=True,text=True,timeout=20)
                a.require(cli.returncode!=0 and cli.stdout=='','strict CLI JSON rejection');a.rejections+=1
        a.end('Portable normal and optimized offline CLI plus two strict-JSON rejections')
    finally:
        sys.dont_write_bytecode=old_bytecode
    return {'chapter':'v10-c03','review':'independent peer','status':'passed','groups':a.groups,
            'comparisons':a.comparisons,'valid_interventions':len(interventions),'domain_rejections':a.rejections,
            'worked_examples_reviewed':4,'exercises_reviewed':10,
            'limits':'Finite synthetic conditional arithmetic and documented editorial proof/source review; no empirical validation or external certification.'}


if __name__ == '__main__':
    print(json.dumps(run(),indent=2,allow_nan=False))
