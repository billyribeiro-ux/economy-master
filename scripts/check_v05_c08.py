"""Independent exact ledgers and incentive comparisons for information models.

Finite deviation grids supplement, rather than prove, the manuscript's
all-price/all-signal arguments. No empirical or equilibrium-refinement claim.
"""
from fractions import Fraction as F
import json


def check():
    def pool(alpha, price):
        masses = (1-alpha, alpha)
        participants = [(m,v) for m,c,v in zip(masses,(4,12),(6,18)) if price >= c]
        mass = sum(m for m,v in participants)
        if not mass:
            return F(0), None
        value = sum(m*v for m,v in participants)/mass
        return mass, value

    assert pool(F(1,3),10) == (F(2,3),F(6))
    assert pool(F(1,3),6) == (F(2,3),F(6))
    for p in (F(n,4) for n in range(25,101)):
        mass,value = pool(F(1,3),p)
        assert mass*(value-p) <= 0
    assert pool(F(3,4),13) == (F(1),F(15))
    assert pool(F(3,4),15) == (F(1),F(15))
    assert pool(F(1,2),12) == (F(1),F(12))
    full = F(2,3)*(6-4)+F(1,3)*(18-12)
    hidden = F(2,3)*(6-4)
    assert (full,hidden,full-hidden) == (F(10,3),F(4,3),F(2))
    assert full-1 == F(7,3) and full-1-hidden == 1
    listing_mass = F(1,3)*F(1,4)+F(2,3)*F(3,4)
    posterior = F(1,3)*F(1,4)/listing_mass
    assert listing_mass == F(7,12) and posterior == F(1,7)
    assert 18*posterior+6*(1-posterior) == F(54,7)
    # Uniform selection: integrate z over [0,p], then normalize by its mass.
    for a in (F(3,2),F(5,2)):
        assert (a-1)/2 == ({F(3,2):F(1,4),F(5,2):F(3,4)}[a])
        for p in (F(n,20) for n in range(1,61)):
            mass = min(p,F(1))
            value = a*(mass**2/2)/mass
            if a < 2:
                assert value-p < 0
        if a > 2:
            assert a/2 == F(5,4) >= 1

    # Signal checks use full payoff functions and include off-support actions.
    def signal_payoff(e, coefficient, high_signal):
        return (10 if e == high_signal else 4)-coefficient*e
    for s in (F(n,4) for n in range(1,33)):
        low_own,high_own = F(4),10-s
        admissible = low_own >= 10-3*s and high_own >= 4
        assert admissible == (2 <= s <= 6)
        if admissible:
            for e in [F(n,7) for n in range(71)]+[s]:
                assert signal_payoff(e,3,s) <= low_own
                assert signal_payoff(e,1,s) <= high_own
    assert (signal_payoff(F(1),3,F(1)),signal_payoff(F(7),1,F(7))) == (7,3)
    mean_productivity = F(2,3)*4+F(1,3)*10
    assert mean_productivity == 6
    for s,expected in ((F(2),F(16,3)),(F(3),F(5))):
        assert mean_productivity-F(1,3)*s == expected
    for e in (F(1,100),F(1,4),F(1),F(2),F(10)):
        assert 4-e < 6 and 4-3*e < 6
    assert 7-F(1,2) > 6 and 7-3*F(1,4) > 6
    assert 10-3*2 == 4 < 6 < 10-2 == 8

    def menu(a,b,lam):
        lo = max(F(0),a-lam*(b-a)/(1-lam))
        hi = b
        tl,th = a*lo,b*hi-(b-a)*lo
        utilities = ((a*lo-tl,a*hi-th),(b*lo-tl,b*hi-th))
        assert utilities[0][0] >= max(0,utilities[0][1])
        assert utilities[1][1] >= max(0,utilities[1][0])
        profit = (1-lam)*(tl-lo*lo/2)+lam*(th-hi*hi/2)
        rent = (1-lam)*utilities[0][0]+lam*utilities[1][1]
        welfare = (1-lam)*(a*lo-lo*lo/2)+lam*(b*hi-hi*hi/2)
        first = (1-lam)*a*a/2+lam*b*b/2
        assert profit+rent == welfare
        assert first-welfare == (1-lam)*(a-lo)**2/2
        # A completed-square/linear term certificate of global optimality.
        # For exclusion the low linear coefficient is nonpositive.
        low_coefficient = (1-lam)*a-lam*(b-a)
        for ql in (F(0),F(1),F(5,3),F(2),F(4),F(8)):
            for qh in (F(0),F(2),F(7),F(8),F(10)):
                if qh < ql:
                    continue
                pl,ph = a*ql,b*qh-(b-a)*ql
                other = (1-lam)*(pl-ql*ql/2)+lam*(ph-qh*qh/2)
                if lo > 0:
                    gap = (1-lam)*(ql-lo)**2/2+lam*(qh-hi)**2/2
                else:
                    gap = -low_coefficient*ql+(1-lam)*ql*ql/2+lam*(qh-hi)**2/2
                assert profit-other == gap >= 0
        return lo,hi,tl,th,profit,rent,welfare,first,utilities

    base = menu(F(4),F(8),F(1,3))
    assert base[:8] == (2,8,8,56,12,F(8,3),F(44,3),16)
    assert base[8] == ((0,-24),(8,8))
    assert F(1,3)*(64-32) == F(32,3) < 12
    assert 16-F(4**2,2) == 8 < 12
    transfer = menu(F(3),F(7),F(1,4))
    assert transfer[:8] == (F(5,3),7,5,F(127,3),F(43,6),F(5,3),F(53,6),F(19,2))
    assert transfer[8] == ((0,F(-64,3)),(F(20,3),F(20,3)))
    assert 5-F(25,18) == F(65,18)
    assert F(127,3)-F(49,2) == F(107,6)
    excluded = menu(F(4),F(8),F(2,3))
    assert excluded[:8] == (0,8,0,64,F(64,3),0,F(64,3),24)
    for lam in (F(1,10),F(1,3),F(1,2),F(2,3),F(9,10)):
        computed = menu(F(4),F(8),lam)
        assert (computed[0] == 0) == (lam >= F(1,2))
    assert 8*4-16 == 16 > 8*8-64 == 0
    for eps in (F(1,100),F(1,5),F(9,10)):
        tl,th = 8-eps,56-2*eps
        assert 4*2-tl > max(F(0),4*8-th)
        assert 8*8-th > max(F(0),8*2-tl)
        assert F(2,3)*(tl-2)+F(1,3)*(th-32) == 12-F(4,3)*eps
    assert (9-3)/F(2) == 3 and (9-3)/F(1) == 6
    assert (3,9-4,F(1,2)*4,F(1,2)*(3+9)-2) == (3,5,2,4)
    return {
        "status":"passed",
        "checks":["selected composition, offer deviations and boundary",
                  "inspection and continuous-quality resource ledgers",
                  "Bayes listing posterior and eight solved exercise targets",
                  "separating IC interval, global off-path bounds and pooling deviations",
                  "screening all IC/IR, completed-square certificate, exclusion and ties",
                  "profit-rent-welfare identities and delayed transfer case"],
        "limitations":["Finite arithmetic supplements the written global proofs.",
                       "No empirical validation, general PBE refinement or UI QA."]}


if __name__ == "__main__":
    print(json.dumps(check(),indent=2))
