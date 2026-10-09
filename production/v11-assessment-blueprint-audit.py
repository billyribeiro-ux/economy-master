"""Coordinator calculations from the original assessment design contracts.

This does not import author code, author results, or certify unfinished prompts.
Final manuscripts and all scoring still require complete separate review.
"""
from fractions import Fraction as F
import json
from pathlib import Path


def audit():
    checked = []

    def same(label, actual, expected):
        if actual != expected:
            raise ValueError(f'{label}: {actual} != {expected}')
        checked.append({'quantity': label, 'exact_value': str(actual)})

    # Form A: integrate applicant states before deciding on one funded loan.
    passed = F(2, 3) * F(3, 4) + F(1, 3) * F(1, 4)
    posterior = F(2, 3) * F(3, 4) / passed
    receipt = posterior * 24 + (1 - posterior) * 8
    same('A1 pass probability', passed, F(7, 12))
    same('A1 posterior good', posterior, F(6, 7))
    same('A1 conditional receipt', receipt, F(152, 7))
    same('A1 applicant net gain', passed * (receipt - 20) - F(2, 5), F(3, 5))
    same('A1 unscreened gain', F(2, 3) * 24 + F(1, 3) * 8 - 20, F(-4, 3))
    cash = 6 - F(2, 5) + F(32, 5) - 12
    deposits = 60 + 20 - 12
    debt, equity = 10 + F(32, 5), 10 - F(2, 5)
    same('A1 closing cash', cash, 0)
    same('A1 closing equity', cash + 54 + 20 + 20 - deposits - debt, equity)
    same('A1 outside provider cash', 7 - F(32, 5), F(3, 5))
    same('A2 ES75', (F(15, 100) * 24 + F(10, 100) * 4) / F(1, 4), 16)
    capacity = (12 - 4) * F(9, 10) * F(3, 4)
    borrowing = (6 - 2) / F(11, 10)
    contribution = 6 - borrowing
    same('A2 collateral capacity', capacity, F(27, 5))
    same('A2 interior borrowing', borrowing, F(40, 11))
    same('A2 minimum contribution', contribution, F(26, 11))
    same('A2 first cash prefix', 5 + 2 + borrowing + contribution - 13, 0)
    same('A2 final cash prefix', 5 + 2 + 10 + contribution - 13 - 6 - borrowing / 10, 0)
    same('A3 liabilities after actual discharge', 90 - 7 - 8, 75)
    same('A3 equity after collectible duplicate', 22 - 7 - 5 - 8 + 80 + 3 - 75, 10)
    same('A3 early omitted-obligation gap', 5 - (22 - 20), 3)
    same('A3 supported worst loss', max(0 + 1 + 0, 7 + 2 + 2, 2 + 8 + 0), 11)
    same('A3 incompatible component maximum', 7 + 8 + 2, 17)
    for label, probability, willingness in [('low', F(1, 10), F(99, 25)), ('high', F(2, 5), F(384, 25))]:
        eu = (1 - probability) * 10 + probability * 8
        same('A4 ' + label + ' willingness', 100 - eu * eu, willingness)
    same('A4 selected insurer margin', 10 - F(2, 5) * 36, F(-22, 5))
    same('A4 offshore payment gap', 24 - (4 + 12), 8)
    same('A5 unassisted sale proceeds', 8 * (1 - F(8, 16)), 4)
    same('A5 assisted sale proceeds', 4 * (1 - F(4, 16)), 3)
    same('A5 bad-state intervention principal loss', 1 - 4 * F(1, 5), F(1, 5))
    same('A5 funded escrow needed', F(1, 5) - F(3, 20), F(1, 20))

    # Form B: monitoring, timing, dependence inference, and retained arrears.
    same('B1 total monitoring gain', (F(15, 100) - F(5, 100)) * 20 - F(3, 2), F(1, 2))
    same('B1 lender gross monitoring benefit', F(3, 5) * F(1, 10) * 20, F(6, 5))
    same('B1 funded-fee monitoring surplus', F(6, 5) + F(2, 5) - F(3, 2), F(1, 10))
    service1, service2 = 18 + F(1, 25) * 48, 30 + F(1, 25) * 30
    carry = 4 + 18 - service1
    same('B1 first restructured service', service1, F(498, 25))
    same('B1 carried borrower cash', carry, F(52, 25))
    same('B1 final timed contribution', service2 - 26 - carry, F(78, 25))
    same('B1 allowance after provision and charge-off', 10 + 6 - 12, 4)
    same('B1 post-charge-off equity', 18 + 182 - 12 - 4 - 160 - 12, 12)
    for theta in (F(0), F(1, 10), F(1, 5), F(1, 4)):
        probs = [F(1, 2) + theta, F(1, 2) - 2 * theta, theta]
        same('B2 mean loss at theta=' + str(theta), sum(p * l for p, l in zip(probs, (0, 6, 12))), 3)
        mass12 = min(theta, F(1, 5))
        es = (12 * mass12 + 6 * (F(1, 5) - mass12)) / F(1, 5)
        same('B2 ES80 at theta=' + str(theta), es, min(6 + 30 * theta, 12))
    same('B2 approximate EVE change', -(120 * 4 - 100 * 2) * F(1, 100), F(-14, 5))
    same('B2 annual NII change', (80 - 50) * F(1, 100), F(3, 10))
    common = F(1, 25)
    residual1 = (F(2, 25) - common) / (1 - common)
    residual2 = (F(3, 25) - common) / (1 - common)
    joint = common + (1 - common) * residual1 * residual2
    same('B3 residual channel one', residual1, F(1, 24))
    same('B3 residual channel two', residual2, F(1, 12))
    same('B3 joint failure', joint, F(13, 300))
    same('B3 common cause posterior', common / joint, F(12, 13))
    same('B3 cash at attained failure point', 10 + 54 - 12 * F(3, 10) - 60 - 20 * F(3, 10), F(-28, 5))
    same('B3 minimum protection through x=.5', -(10 + 54 - 12 * F(1, 2) - 60 - 20 * F(1, 2)), 12)
    pension_unpaid = []
    for probability, lives, assets, reserve in [(F(3, 10), 1, 45, 20), (F(1, 2), 2, 55, 20), (F(1, 5), 2, 30, 8)]:
        due = 30 * lives
        topup = min(20, reserve, max(0, due - assets))
        pension_unpaid.append(probability * max(0, due - assets - topup))
    same('B4 expected unpaid pension benefit', sum(pension_unpaid), F(22, 5))
    grant, borrowing = F(6, 11), F(60, 11)
    carry = borrowing + grant - 6
    same('B4 first sovereign cash', carry, 0)
    same('B4 final sovereign cash including carry', 18 + carry - 12 - F(11, 10) * borrowing, 0)
    same('B5 maximum collectible expected sanction', F(1, 3) * 9, 3)
    same('B5 converted bank equity', 6 + 54 - 12 - (40 - 12), 20)
    adverse_receipt = F(57, 2) - (40 - 12)
    same('B5 adverse client receipt', adverse_receipt, F(1, 2))
    same('B5 impairment allocation', 5 + (1 - adverse_receipt), 6 - adverse_receipt)
    same('B5 public principal loss after funded grant', F(9, 10) - adverse_receipt, F(2, 5))

    # Portlight: selected fixed policy, computed only from its dated contracts.
    initial_assets = 20 + 2 * 6 + 20 + 20 + 60 + 2 * 20
    initial_equity = initial_assets - 90 - 2 * 25
    same('Project opening assets', initial_assets, 172)
    same('Project opening equity', initial_equity, 32)
    scenario_results = []
    for name, spot, price, haircut, first, last, foreign, cap, expected_equity in [
        ('normal', F(2), F(1), F(1, 10), 20, 40, 20, 20, F(52)),
        ('credit', F(5, 2), F(16, 25), F(1, 5), 12, 42, 18, 4, F(393, 10)),
        ('joint', F(3), F(4, 9), F(1, 4), 8, 40, 16, 5, F(1246, 45)),
    ]:
        home = 20 + 20 - 2 * 10 + first
        draw = max(F(0), 30 + 2 - home)
        if draw > 20 * price * (1 - haircut): raise ValueError('Unfunded selected draw')
        home += draw - 30
        foreign_cash = F(6 + 10 - 15 + foreign - 10)
        home += 20 + last
        repayment = F(21, 20) * draw
        conversion = max(F(0), (60 + repayment + 2 - home) / spot)
        if conversion > min(cap, foreign_cash): raise ValueError('Unfunded selected conversion')
        home += spot * conversion - 60 - repayment
        foreign_cash -= conversion
        equity = home + spot * foreign_cash + 20 * price
        same('Project ' + name + ' closing equity', equity, expected_equity)
        scenario_results.append({'scenario': name, 'draw': str(draw), 'final_H': str(home), 'final_F': str(foreign_cash), 'equity_H': str(equity)})
    losses = [initial_equity + 20 - F(x['equity_H']) for x in scenario_results]
    same('Project credit loss adjusted for contribution', losses[1], F(127, 10))
    same('Project joint loss adjusted for contribution', losses[2], F(1094, 45))
    same('Project ES75', (F(1, 6) * losses[2] + F(1, 12) * losses[1]) / F(1, 4), F(5519, 270))
    same('Project reverse collateral price floor', F(4, 1) / (20 * F(3, 4)), F(4, 15))
    same('Project reverse equity price floor', (20 - (2 + 3 * F(28, 5))) / 20, F(3, 50))
    same('Project boundary closing equity', 2 + 3 * F(28, 5) + 20 * F(4, 15), F(362, 15))
    # Full manuscript quantities added after independently reading both forms
    # and every project transfer. These still do not certify final frozen files.
    same('A1 recognized loss excludes unrecognized interest', 20 - 8, 12)
    same('A1 post-impairment equity', F(48, 5) - (20 - 8), F(-12, 5))
    same('A2 maximum-draw final funding gap', 2 + F(27, 50) - F(3, 5), F(97, 50))
    same('A2 wrong full-atom conditional mean', (F(3, 10) * 4 + F(3, 20) * 24) / F(9, 20), F(32, 3))
    same('A3 erroneous double-counted loss', (7 + 2) + 2 + 5, 16)
    same('A3 double-count overstatement', 16 - 11, 5)
    same('A4 shocked translated assets', 12 * 3 + 4, 40)
    same('A5 assisted larger sale is feasible, before minimum-sale restriction', 2 + 1 + 6 * (1 - F(6, 16)) - 6, F(3, 4))
    same('B4 expected promised benefits', F(3, 10) * 30 + F(7, 10) * 60, 51)
    same('B4 expected benefit receipts', F(3, 10) * 30 + F(1, 2) * 60 + F(1, 5) * 38, F(233, 5))
    same('B4 expected funded guaranty', F(1, 2) * 5 + F(1, 5) * 8, F(41, 10))
    same('B5 grant case single impairment allocation', 5 + F(1, 10) + F(2, 5), F(11, 2))
    same('Project mean selected loss', F(1, 3) * losses[1] + F(1, 6) * losses[2], F(2237, 270))
    same('Project new investor fraction', F(20, 32 + 20), F(5, 13))
    same('Project new investor joint stake', F(5, 13) * F(1246, 45), F(1246, 117))
    short_policy_draw = 20 * F(4, 9) * F(3, 4)
    short_pension_receipt = 10 + 8 + short_policy_draw - 18
    same('Project failed-policy pension receipt', short_pension_receipt, F(20, 3))
    same('Project failed-policy early benefit gap', 15 - (1 + 2 + short_pension_receipt), F(16, 3))
    short_late_fx = (F(21, 20) * short_policy_draw + 60 + (12 - short_pension_receipt) + 2 - (20 + 40)) / 3
    same('Project failed-policy late conversion', short_late_fx, F(43, 9))
    same('Project failed-policy final equity', 2 + 3 * (7 - short_late_fx) + F(80, 9), F(158, 9))
    same('Project T1 early foreign shortfall', 15 - 6, 9)
    same('Project T1 foreign cash before late conversion', 6 - 6 + 10 + 16 - (25 - 6), 7)
    same('Project T2 old-plan final home cash', 62 + 3 - F(21, 20) * 4 - 60, F(4, 5))
    delta = (F(21, 20) * 4 - 3) / F(21, 20)
    same('Project T2 minimum added equity', delta, F(8, 7))
    same('Project T2 repaired draw', 4 - delta, F(20, 7))
    same('Project T2 repaired final equity', F(1246, 45) + F(21, 20) * delta, F(260, 9))
    same('Project T2 b22 final equity', F(1246, 45) + F(21, 20) * 2, F(2681, 90))
    same('Project T2 b22 late conversion', F(21, 20) * 2 / 3, F(7, 10))
    same('Project T3 pension required contribution', 17 - 1 - 12, 4)
    same('Project T3 sponsor remaining cash', 30 - 20 - 4, 6)
    reduced_capacity = 10 * F(4, 9) * F(3, 4)
    same('Project T4 old-plan home cash', 28 + reduced_capacity - 30, F(4, 3))
    delta = 4 - reduced_capacity
    same('Project T4 minimum added equity', delta, F(2, 3))
    same('Project T4 repaired final equity', F(1246, 45) + F(21, 20) * delta, F(511, 18))
    same('Project T4 repaired late conversion', F(21, 20) * reduced_capacity / 3, F(7, 6))
    extra_credit_loss = 9 - 3
    same('Project T5 total nominal unpaid', 60 - (8 + 28 + 18 - 3 - 9), 18)
    same('Project T5 late conversion', (F(21, 20) * 4 + extra_credit_loss) / 3, F(17, 5))
    same('Project T5 final equity', F(1246, 45) - extra_credit_loss, F(976, 45))
    same('Project T5 capital price floor', (20 - (F(94, 5) - extra_credit_loss)) / 20, F(9, 25))
    same('Project T5 yield boundary price', 1 / (1 + F(2, 3)) ** 2, F(9, 25))
    same('Project T6 pension available cash', 1 + 2 + (12 - 10), 5)
    same('Project T6 additional contribution beyond remaining sponsor cash', (15 - 5) - (30 - 20 - 2), 2)
    return {'status': 'passed', 'scope': 'Original design contracts only; not acceptance of unfinished exam/project manuscripts.', 'comparisons': len(checked), 'checks': checked, 'project_selected_scenarios': scenario_results}


if __name__ == '__main__':
    result = audit()
    Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'comparisons': result['comparisons']}))
