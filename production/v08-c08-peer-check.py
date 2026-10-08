"""Independent peer's exact recomputation; no author/shared payload edits.

Run from any working directory. Quiet check() returns strict JSON evidence.
The standalone calculations use manuscript inputs before comparing lab results.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
import importlib.util
import io
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check():
    # Solve the two price equations directly for state prices.
    gross = F(21,20)
    pi_up = (100-70/gross)/(145-70)
    pi_down = 1/gross-pi_up
    waiting = pi_up*55
    require((pi_up,pi_down,waiting) == (F(4,9),F(32,63),F(220,9)), 'State-price solution')
    require(pi_up > 0 and pi_down > 0 and 145*pi_up+70*pi_down == 100, 'Positive price certificate')
    require(F(11,15)*145-F(440,9)*gross == 55 and
            F(11,15)*70-F(440,9)*gross == 0, 'Independent replicating payoff match')
    require(F(3,5)*55/waiting-1 == F(7,20) and
            (F(3,5)*145+F(2,5)*70)/100-1 == F(3,20), 'Option versus clone physical return')
    require((waiting-10)*gross == F(91,6) and 10+20/gross == F(610,21), 'Interim-cash timing threshold')

    # Enumerate feasible complete operating policies from the manuscript menu.
    menus = [(120,145,65),(40,17,65)]
    policies = [(F(2,5)*a+F(3,5)*b)/gross-70 for a,b in itertools.product(*menus)]
    operating_npv = max(policies)
    base_npv = (F(2,5)*120+F(3,5)*40)/gross-70
    require((operating_npv,base_npv,operating_npv-base_npv) ==
            (F(470,21),-F(10,7),F(500,21)), 'Full menu and fixed policy')
    require(F(2,5)*25/gross+F(3,5)*25/gross == operating_npv-base_npv, 'Separate states permit additive gains here')
    interacting = max(40,40+50-20,65)
    require(interacting == 70 and 40+30+25-interacting == 25, 'Incompatible same-state rights cannot be added')
    require((F(2,5)*145+F(3,5)*70)/gross-70 == F(530,21), 'Exercise 4 changed menu')
    constrained_net_fee = max((F(2,5)*a+F(3,5)*b)/gross-73
                             for a,b in itertools.product((120,65),(40,65)))
    require(constrained_net_fee == F(69,7) and operating_npv-3 == F(407,21), 'Funding restriction and rights fee')

    # Sum each realized path's dated cash, including the pilot on failed paths.
    rate = F(11,10)
    good_path = -12-30/rate+80/rate**2
    bad_path = -12
    stage = F(3,5)*good_path+F(2,5)*bad_path
    forced = F(3,5)*good_path+F(2,5)*(-12-30/rate)
    require((stage,forced,stage-forced) == (F(1368,121),F(48,121),F(120,11)), 'Dated pilot path sum')
    threshold = -bad_path/(good_path-bad_path)
    require(threshold == F(363,1175), 'Pilot initiation probability')
    ex5_good, ex5_bad = -15-40/rate+90/rate**2, F(-15)
    ex5_stage = (ex5_good+ex5_bad)/2
    ex5_forced = (ex5_good+ex5_bad-40/rate)/2
    require((ex5_stage,ex5_forced,ex5_stage-ex5_forced) ==
            (F(485,121),-F(1715,121),F(200,11)), 'Exercise 5 complete dated paths')
    require(-ex5_bad/(ex5_good-ex5_bad) == F(363,920), 'Exercise 5 initiation threshold')

    # Price signal policies directly through joint paths; no posterior helper.
    joint = {(True,True):F(3,10),(True,False):F(3,20),
             (False,True):F(1,10),(False,False):F(9,20)}
    receipts = {True:F(160),False:F(40)}
    values = {}
    for launch_positive, launch_negative in itertools.product((False,True),repeat=2):
        policy = {True:launch_positive,False:launch_negative}
        values[(launch_positive,launch_negative)] = sum(prob*(-60/rate+receipts[state]/rate**2)
            for (signal,state),prob in joint.items() if policy[signal])
    informed = max(values.values())
    no_report = max(values[(False,False)],values[(True,True)])
    perfect = sum(prob*max(F(0),-60/rate+receipts[state]/rate**2)
                  for (signal,state),prob in joint.items())
    require(max(values,key=values.get) == (True,False), 'Signal information set determines policy')
    require((informed,no_report,perfect) == (F(2430,121),F(200,11),F(3760,121)), 'Independent joint cash paths')
    require((informed-no_report,perfect-no_report) == (F(230,121),F(1560,121)), 'EVSI and EVPI baselines')
    require(0 < informed-no_report < perfect-no_report and informed-1 > no_report > informed-3,
            'Information bounds and date-0 fee choices')
    require(joint[(True,True)]/(joint[(True,True)]+joint[(True,False)]) == F(2,3) and
            joint[(False,True)]/(joint[(False,True)]+joint[(False,False)]) == F(2,11), 'Both posterior probabilities')
    require((60*rate-40)/(160-40) == F(13,60), 'Posterior launch threshold')
    uninformative_value = sum(F(1,2)*max(F(0),-60/rate+(F(2,5)*160+F(3,5)*40)/rate**2) for _ in range(2))
    require(uninformative_value == no_report, 'Equal likelihoods cannot improve the policy')

    # Remaining distinct exercise and retention anchors.
    ex1_pi_up = (80-60/gross)/(120-60)
    ex1_value = ex1_pi_up*30
    require(ex1_value == F(80,7) and F(1,2)*80-F(200,7) == ex1_value and
            F(15)/ex1_value-1 == F(5,16), 'Exercise 1 value, holdings and return')
    require((F(1,2)*120+F(1,2)*60)/80-1 == F(1,8), 'Exercise 1 underlying return')
    require(100+10/gross == F(2300,21) and 10+10/gross == F(410,21) < waiting and
            waiting-4 == F(184,9), 'Exercise 2 acquired right and sunk-fee distinction')
    require(F(3,10)*55/gross == F(110,7) and F(7,10)*55/gross == F(110,3) and
            F(3,5)*55/gross == F(220,7), 'Exercise 7 positive but unidentified pricing weights')

    spec = importlib.util.spec_from_file_location('v08_c08_reviewed_lab',ROOT/'content/projects/v08-c08-analysis.py')
    lab = importlib.util.module_from_spec(spec)
    out = io.StringIO()
    with redirect_stdout(out):
        spec.loader.exec_module(lab)
        data = json.loads((ROOT/'content/projects/v08-c08-inputs.json').read_text())
        result = lab.compute(data)
    require(out.getvalue() == '', 'Reviewed lab import/compute are quiet')
    require(result['delay']['value'] == waiting and result['operations']['flexible_npv'] == operating_npv and
            result['stage']['staged_npv'] == stage and result['information']['gross_report_value'] == informed,
            'All four independently reconstructed cases match author implementation')
    require(lab.serial(result) == json.loads((ROOT/'content/projects/v08-c08-output.json').read_text()),
            'Preserved output matches exact computed values')
    for endpoint in ('0','1'):
        invalid = deepcopy(data)
        invalid['delay']['physical_up'] = endpoint
        try:
            lab.compute(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Impossible-state endpoint violates the traded two-state contract')
    certain_owner = deepcopy(data)
    certain_owner['stage']['validation_probability'] = '0'
    certain_owner['information'].update(positive_if_good='1',positive_if_bad='1')
    boundary = lab.compute(certain_owner)
    require(boundary['stage']['staged_npv'] == -12 and boundary['information']['evsi'] == 0,
            'Legitimate owner certainty and unreachable-signal boundaries remain allowed')
    report = {'status':'passed','independent_groups':[
        'Positive state prices, clone/bond replication and physical-return separation',
        'All feasible operating policies, mutually exclusive rights and financing limit',
        'Complete success/failure dated paths and both pilot initiation thresholds',
        'Joint signal paths, information-set policies, no-report baseline and information bounds',
        'Every exercise and answered teaching/retention interpretation checked',
        'Quiet reviewed lab, unchanged baseline output and corrected possible-state boundary'],
        'anchors':{'delay_value':str(waiting),'operating_npv':str(operating_npv),'staged_npv':str(stage),
                   'report_gross_value':str(informed),'EVSI':str(informed-no_report)},
        'limits':'Independent agent audit of fictional contracts; no market, legal-right, financing or visual-UI certification.'}
    json.dumps(report,allow_nan=False)
    return report


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
