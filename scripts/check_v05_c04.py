"""Exact independent accounting checks for the original partial-equilibrium cases.

Finite calculations supplement the manuscript's proofs and domain conditions.
No empirical identification or universal equilibrium claim is certified here.
"""
from fractions import Fraction as F
import json


def check():
    # Solve using inverse schedules, independently of the price equations in text.
    demand = lambda q: 30 - q / F(6)
    supply = lambda q: 6 + q / F(3)
    benefit = lambda q: 30*q - q*q/F(12)
    cost = lambda q: 6*q + q*q/F(6)
    q0 = F(24) / (F(1, 6) + F(1, 3))
    assert q0 == 48 and demand(q0) == supply(q0) == 22
    assert (120-4*22, 60-2*22, 22-6, 2*22-12) == (32,16,16,32)
    assert benefit(q0)-22*q0 == 192
    assert 22*q0-cost(q0) == 384
    assert benefit(q0)-cost(q0) == 576
    assert 384-60 == 324
    cases = {}
    for tax, expected in ((6,(36,24,18,108,216,216,36)),
                          (9,(30,25,16,75,150,270,81)),
                          (12,(24,26,14,48,96,288,144)),
                          (24,(0,30,6,0,0,0,576))):
        q = (F(24)-tax)/(F(1,6)+F(1,3))
        pb, ps = demand(q), supply(q)
        cs, surplus = benefit(q)-pb*q, ps*q-cost(q)
        revenue = tax*q
        loss = benefit(q0)-cost(q0)-(benefit(q)-cost(q))
        assert (q,pb,ps,cs,surplus,revenue,loss) == expected
        assert cs+surplus+revenue == benefit(q)-cost(q)
        assert loss == tax*(q0-q)/2
        assert max(0,180-6*pb) == max(0,3*ps-18) == q
        cases[str(tax)] = {"quantity": str(q),"buyer_price":str(pb),
                           "seller_price":str(ps),"loss":str(loss)}
    # No-trade supporting quotes at t=27, rather than a negative interior output.
    for ps in (F(3),F(4),F(6)):
        assert max(0,180-6*(ps+27)) == max(0,3*ps-18) == 0
    # Independent per-firm cost minimization and market clearing at fixed n.
    for intercept,n,p,q,profit in ((120,15,F(12),F(4),F(0)),
                                  (144,15,F(348,25),F(124,25),F(5376,625)),
                                  (144,21,F(12),F(4),F(0)),
                                  (122,15,F(304,25),F(102,25),F(404,625)),
                                  (122,16,F(154,13),F(51,13),F(-103,169))):
        assert p == (F(intercept)+2*n)/(5+F(n,2))
        assert p == 4+2*q and intercept-5*p == n*q
        assert p*q-(16+4*q+q*q) == profit
        # Completing the square certifies conditional global output optimum.
        for candidate in (F(1,10),F(2),F(4),F(6),F(10)):
            candidate_profit = p*candidate-(16+4*candidate+candidate*candidate)
            assert profit-candidate_profit == (candidate-q)**2
    # AC(q)-12=(q-4)^2/q globally verifies the long-run minimum.
    for q in (F(1,10),F(1),F(4),F(11,2),F(100)):
        assert 16/q+4+q-12 == (q-4)**2/q >= 0
    # Exercise 1: actual truncated individual schedules, including the second branch.
    d1 = lambda p: max(F(0),40-2*p)
    d2 = lambda p: max(F(0),30-p)
    assert d1(F(16)) == 8 and d2(F(16)) == 14
    assert d1(F(16))+d2(F(16)) == 2*16-10 == 22
    assert F(4*8,2)+F(14*14,2) == 114
    assert F(11*22,2) == 121
    p = F(80,3)
    assert d1(p) == 0 and d2(p) == max(0,2*p-50) == F(10,3)
    assert (30-p)*d2(p)/2 == F(50,9)
    assert (p-25)*d2(p)/2 == F(25,9)
    assert F(50,9)+F(25,9) == F(25,3)
    assert d1(F(24))+d2(F(24)) != max(0,2*24-50)
    # Exercise 2: branch characterization supplemented by representative boundaries.
    for p in (F(0),F(11),F(12),F(25,2),F(15),F(16)):
        assert (max(0,12-p)==max(0,p-15)) == (12<=p<=15)
    # Exercise 4: derivatives reconstructed independently from stated elasticities.
    dp,sp = -F(1,2)*100/20,F(3,2)*100/20
    pbchange = 2*sp/(sp-dp)
    pschange = 2*dp/(sp-dp)
    assert pbchange == F(3,2) and pschange == -F(1,2)
    assert dp*pbchange == sp*pschange == -F(15,4)
    # Exercise 5: cost/revenue identities and a global AC certificate.
    for fixed,q,p,n,Q in ((25,5,12,10,50),(36,6,14,5,30)):
        assert fixed+2*q+q*q == p*q and p == 2+2*q
        assert 170-10*p == n*q == Q
        for other in (F(1),F(5,2),F(8),F(20)):
            assert fixed/other+2+other-p == (other-q)**2/other >= 0
    # Exercise 6: integrate reservation values, then apply selection probabilities.
    assert 180-6*18 == 72 and 3*18-18 == 36
    assert benefit(F(36)) == 972 and cost(F(36)) == 432
    lottery_benefit = benefit(F(72))*F(36,72)
    assert lottery_benefit == 864
    assert benefit(F(36))-cost(F(36)) == 540
    assert lottery_benefit-cost(F(36)) == 432
    assert benefit(F(36))-lottery_benefit == 108
    assert 576-432 == (576-540)+108 == 144
    # Exercise 7 observational equivalence, not an estimator performance claim.
    assert 100-2*20 == 3*20 == 60
    assert 110-2*22 == 3*22 == 66
    assert F(6,60)/F(2,20) == 1
    # Exercise 8: all feasible compensation endpoints and weighted alternatives.
    for transfer in (F(60),F(75),F(90)):
        assert 90-transfer >= 0 and transfer-60 >= 0
        assert (90-transfer)+(transfer-60) == 30
    assert 90-2*60 == -30 and 90-60-40 == -10
    # Delayed check uses distinct inverse schedules and directly computed totals.
    b = lambda q: 30*q-q*q/F(4)
    c = lambda q: 6*q+q*q/F(2)
    assert 60-2*22 == 22-6 == 16
    assert 60-2*23 == 20-6 == 14
    assert b(F(16))-22*16 == 64 and 22*16-c(F(16)) == 128
    assert b(F(14))-23*14 == 49 and 20*14-c(F(14)) == 98
    assert b(F(16))-c(F(16))-(b(F(14))-c(F(14))) == 3
    assert 49+98+3*14 == 189
    return {"status":"passed", "checks":[
        "Exact inverse-schedule solutions and independent welfare ledgers for four taxes",
        "Truncated no-trade boundary and kinked aggregation",
        "Conditional firm profit square certificate and long-run AC global minima",
        "Short-run, free-entry and finite-integer firm configurations",
        "Local incidence reconstructed from elasticities, not assumed finite nonlinear effects",
        "Rationing benefit integration and allocation-versus-quantity loss",
        "Observational-equivalence construction, compensation criteria and distinct delayed check"],
        "tax_cases":cases,
        "limitations":["Finite checks supplement written proofs and assumptions; no empirical, general-equilibrium or external academic certification."]}


if __name__ == "__main__":
    print(json.dumps(check(),indent=2))
