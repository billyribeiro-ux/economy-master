"""Coordinator's independent numerical audit of the duration chapter.

Expected answers are rebuilt here from original cash contracts, without
importing the author's checker. The analysis module is the system under test.
Proof and prompt reviews are recorded separately in the root review notes.
"""
from fractions import Fraction as F
import copy
import contextlib
import io
import json
import math
from pathlib import Path
import runpy

BOOK = Path(__file__).resolve().parents[1]


def check():
    checks = []

    def close(actual, expected, label, tol=2e-10):
        if not math.isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol):
            raise ValueError(f"{label}: {actual} != {expected}")
        checks.append(label)

    def exact(actual, expected, label):
        if actual != expected:
            raise ValueError(f"{label}: {actual} != {expected}")
        checks.append(label)

    with contextlib.redirect_stdout(io.StringIO()) as quiet:
        model = runpy.run_path(str(BOOK / 'content/projects/v10-c02-analysis.py'))
        data = json.loads((BOOK / 'content/projects/v10-c02-inputs.json').read_text())
        out = model['run'](data)
    exact(quiet.getvalue(), '', 'import and run are quiet')

    # Rational discount-polynomial derivatives, all original payments.
    cash = [(1,F(4)),(2,F(4)),(3,F(4)),(4,F(104))]
    q = F(21,20)
    price = sum(c/q**t for t,c in cash)
    k = sum(t*c/q**(t+1) for t,c in cash)
    g = sum(t*(t+1)*c/q**(t+2) for t,c in cash)
    first_moment = sum(t*c/q**t for t,c in cash)/price
    variance = sum((t-first_moment)**2*c/q**t for t,c in cash)/price
    for key,value in {'price':price,'macaulay_years':first_moment,
                      'modified_duration':k/price,'convexity':g/price,
                      'dollar_duration':k,'dollar_convexity':g,
                      'dv01_positive_loss_for_upward_bp':k/10000}.items():
        close(out['note']['dirty'][key],value,'W1 '+key)
    exact(g/price,(variance+first_moment**2+first_moment)/q**2,'E2 variance decomposition')
    for row in out['note']['scenarios']:
        h=F(str(row['yield_shift']))
        actual=sum(c/(q+h)**t for t,c in cash)
        linear=price-k*h
        second=linear+g*h*h/2
        third=sum(t*(t+1)*(t+2)*c/min(q,q+h)**(t+3) for t,c in cash)
        close(row['exact_dirty_price'],actual,'W1 exact '+str(h))
        close(row['linear_dirty_price'],linear,'W1 tangent '+str(h))
        close(row['quadratic_dirty_price'],second,'W1 quadratic '+str(h))
        close(row['absolute_quadratic_remainder_bound'],third*abs(h)**3/6,'W1 remainder bound '+str(h))
        exact(abs(second-actual)<=third*abs(h)**3/6,True,'W1 remainder inequality '+str(h))

    # Solve funded hedge by eliminating the budget equation.
    v=F(125)/q**3
    weight5=(F(3)-1)/(5-1)
    face1=v*(1-weight5)*q
    face5=v*weight5*q**5
    imm=out['immunization']
    close(imm['initial_budget'],v,'W2 dirty cash budget')
    close(imm['asset_zero_faces'][0],face1,'W2 short face')
    close(imm['asset_zero_faces'][1],face5,'W2 long face')
    close(imm['surplus_first_yield_derivative'],0,'W2 first derivative')
    close(imm['surplus_second_yield_derivative'],4*v/q**2,'W2 positive surplus curvature')
    for row in imm['single_shift_then_constant_rate_scenarios']:
        altered=q+F(str(row['annual_yield_shift']))
        wealth=face1*altered**2+face5/altered**2
        close(row['horizon_wealth'],wealth,'W2 horizon '+str(altered))
        close(row['valuation_surplus'],(wealth-125)/altered**3,'W2 valuation-horizon bridge '+str(altered))
        exact(wealth>=125,True,'W2 global constant-rate bound '+str(altered))
    close(imm['later_path_intervention']['horizon_wealth'],face1+face5/F(11,10)**2,'W2 changed cash operations')
    close(imm['entry_fee_intervention']['base_horizon_funding_gap'],F(125)-F(125)/F(501,500),'W2 fee funding gap')
    close(imm['changed_cash_flow_intervention']['base_horizon_surplus'],F(-25,4),'W2 changed promise')

    # Direct exponential valuation verifies the curve derivatives/scenarios.
    curve=out['key_rate_curve']
    expected_keys=[v/2,-3*v,5*v/2]
    for got,want in zip(curve['surplus_dollar_key_durations'],expected_keys):
        close(got,want,'W3 signed key exposure')
    z=math.log(1.05)
    for row in curve['scenarios']:
        bumps=row['continuous_zero_bumps']
        exact_surplus=float(face1)*math.exp(-(z+bumps[0]))+float(face5)*math.exp(-5*(z+bumps[2]))-125*math.exp(-3*(z+bumps[1]))
        close(row['exact_surplus'],exact_surplus,'W3 exact '+row['name'])
    close(float(v)*(.5*math.exp(.01)+.5*math.exp(-.05)-1),-2.090509038717073,'W3 manuscript adverse twist')
    d=F(5,4)
    direct=120*d-340*d*d+320*d**3-100*d**4
    exact(direct,F(-25,64),'W4 factored/direct large-move failure')
    close(out['local_counterexample']['stress_surplus_direct'],direct,'W4 model stress')
    exact(120*2+320*12-340*6-100*20,40,'W4 local curvature')

    # Independently solve all determinate exercise quantities.
    p=F(100)/F(103,100)**6
    close(p,83.74842567,'E1 price',1e-9)
    close(3/F(103,100),2.91262136,'E1 nominal duration',1e-9)
    close(F(21,2)/F(103,100)**2,9.89725705,'E1 nominal convexity',1e-9)
    close(p*3/F(103,100)/10000,.02439275,'E1 DV01',5e-9)
    exact(F(103,100)**2-1,F(609,10000),'E1 equivalent annual rate')
    close(3/F(103,100)**2,2.82778773,'E1 annual-coordinate duration',2e-9)
    exact(F(103)*4*F(25,10000),F(103,100),'E3 dirty dollar loss')
    exact(F(103)*4/F(100),F(103,25),'E3 clean normalization')
    exact((F(103)-100)*4*F(25,10000),F(3,100),'E3 normalization error')
    exact(100-1000*F(1,5),-100,'E4 first-order price')
    exact(100-1000*F(1,5)+F(11000,2)*F(1,5)**2,120,'E4 quadratic price')
    close(F(100)/F(6,5)**10,16.15055829,'E4 exact repricing',1e-9)
    exact(F(132000,6)*F(1,5)**3,176,'E4 valid absolute remainder bound')
    b=(F(600)-240)/3; a=240-b
    exact((a,b),(F(120),F(120)),'E5 full budget and dollar match')
    exact((a+4*b)/240,F(5,2),'E5 different normalized duration')
    exact(a*2+b*20-150*20,F(-360),'E5 negative surplus convexity')
    exact(F(-360,2)*F(1,100)**2,F(-9,500),'E5 second order change')
    p=100*math.exp(-.06)
    close(p,94.17645336,'E6 interpolated price',1e-9)
    close(100*math.exp(-2*((.02+.01)/2+(.04-.01)/2)),p,'E6 exact offset bump')
    exact([2*F(1,2),2*F(1,2)],[F(1),F(1)],'E6 normalized key exposures')
    exact([[4*F(1,2)**2]*2]*2,[[1,1],[1,1]],'E6 Hessian divided by price')
    w5=F(8-2,5-2); w2=1-w5
    exact((w2,w5),(F(-1),F(2)),'E7 signed weights expose infeasibility')
    for yy,sign in ((F(1,100),-1),(F(-1,100),1)):
        dd=1/(1+yy); s=300*dd**2+100*dd**4-100*dd-300*dd**3
        exact(s,100*dd*(dd-1)**3,'E8 cubic factor '+str(yy))
        exact(s*sign>0,True,'E8 sign '+str(yy))
    exact(300*6+100*20-100*2-300*12,0,'E8 equal curvature')
    exact(F(125)-F(125)/F(101,100),F(125,101),'E9 fee gap')
    exact(F(125)-F(125,2)*(1+F(4,5)),F(25,2),'E9 claim-change gap')
    close(v/100,1.07979700,'E9 initial contribution',5e-9)
    # E10 critique is qualitative; W3 and altered cash path supply its required
    # determinate counterexamples. Root notes separately assess all rubric items.
    close(125-float(face1+face5/F(11,10)**2),11.36334355,'E10 cash failure',1e-9)
    close(F(6)/F(26,25)**2,5.54733728,'retention convexity',1e-9)
    exact(F(80)*3/100,F(12,5),'retention dollar match')
    exact(-(20*F(1,100)+30*F(-1,100)),F(1,10),'retention signed twist')

    # Separate scale intervention, preserving the note/curve contract.
    changed=copy.deepcopy(data)
    changed['immunization']['liability_amount']*=2
    revised=model['run'](changed)
    close(revised['immunization']['initial_budget'],2*v,'intervention doubled liability budget')
    close(revised['immunization']['asset_zero_faces'][0],2*face1,'intervention doubled short face')
    close(revised['immunization']['asset_zero_faces'][1],2*face5,'intervention doubled long face')
    exact(revised['note'],out['note'],'intervention leaves separate note unchanged')
    return {'chapter':'v10-c02','status':'passed','independence':'No author checker imported; rational cash contracts, direct exponential valuation and independently solved exercises. Model used only as system under test.','comparisons':len(checks),'checks':checks}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
