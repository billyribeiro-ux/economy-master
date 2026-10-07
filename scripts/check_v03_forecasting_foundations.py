"""Independent finite-state/integral checks for v03-c11 and v03-c12.

General measure/projection/strong-law proofs are audited in the written review.
Finite calculations below verify the chapter's laws and counterexamples.
"""
from fractions import Fraction as F
from itertools import product
from math import log, sqrt
from check_v03_moments import moments, near, simpson


def signal_problem(prior,good,bad,sensitivity,false_positive):
    # Direct joint-state payoff enumeration, not posterior-value averaging.
    joint={(1,1):prior*sensitivity,(1,0):prior*(1-sensitivity),
           (0,1):(1-prior)*false_positive,(0,0):(1-prior)*(1-false_positive)}
    baseline=max(F(0),prior*good+(1-prior)*bad)
    conditional={}
    value=F(0)
    for z in (0,1):
        mass=sum(w for (theta,s),w in joint.items() if s==z)
        gain=sum(w*(good if theta else bad) for (theta,s),w in joint.items() if s==z)
        conditional[z]=(mass,joint[1,z]/mass,gain/mass)
        value+=max(F(0),gain)
    perfect=prior*max(F(0),good)+(1-prior)*max(F(0),bad)
    # All four deterministic policies, calculated independently from states.
    policy_values=[]
    for rule in product((0,1),repeat=2):
        policy_values.append(sum(w*rule[z]*(good if theta else bad)
                                 for (theta,z),w in joint.items()))
    assert value==max(policy_values) and baseline<=value<=perfect
    return baseline,value,perfect,conditional


def check():
    checks=[]
    p=F(3,10)
    for q,brier,logloss in [(F(1,10),F(1,4),.764527888858692),
                           (F(3,10),F(21,100),.6108643020548935),
                           (F(3,5),F(3,10),.7946511994417057)]:
        direct=sum(w*(q-y)**2 for y,w in ((0,1-p),(1,p)))
        assert direct==brier==p*(1-p)+(q-p)**2
        near(-float(p)*log(q)-float(1-p)*log(1-q),logloss)
    for p in (F(i,20) for i in range(21)):
        for q in (F(j,20) for j in range(21)):
            assert p*(1-q)**2+(1-p)*q*q-p*(1-p)==(p-q)**2
    truth=[F(1,5),F(3,10),F(1,2)]
    truthful=-sum(float(p)*log(p) for p in truth)
    for a in range(1,19):
        for b in range(1,20-a):
            q=[F(a,20),F(b,20),F(20-a-b,20)]
            excess=-sum(float(p)*log(v) for p,v in zip(truth,q))-truthful
            divergence=sum(float(p)*log(p/v) for p,v in zip(truth,q))
            near(excess,divergence);assert excess>=-1e-14
    checks.append('Exact binary Brier identities including endpoints, independently averaged log losses and finite categorical entropy/excess grid')

    joint=[(g,y,F(1,2)*(F(1,5) if g==0 else F(4,5)) if y else
            F(1,2)*(F(4,5) if g==0 else F(1,5)))
           for g,y in product((0,1),repeat=2)]
    assert sum(w for _,_,w in joint)==1
    for forecasts,expected,logloss,resolution,error in [
            ([F(1,2)]*2,F(1,4),.6931471805599453,F(0),F(0)),
            ([F(1,5),F(4,5)],F(4,25),.5004024235381879,F(9,100),F(0)),
            ([F(1,20),F(19,20)],F(73,400),.6401810902208387,F(9,100),F(9,400))]:
        direct=sum(w*(forecasts[g]-y)**2 for g,y,w in joint)
        ll=-sum(float(w)*log(forecasts[g] if y else 1-forecasts[g]) for g,y,w in joint)
        reports=set(forecasts);r={}
        mass={q:sum(w for g,y,w in joint if forecasts[g]==q) for q in reports}
        for q in reports:r[q]=sum(w*y for g,y,w in joint if forecasts[g]==q)/mass[q]
        R=sum(mass[q]*(r[q]-F(1,2))**2 for q in reports)
        C=sum(mass[q]*(q-r[q])**2 for q in reports)
        assert direct==expected==F(1,4)-R+C and R==resolution and C==error
        near(ll,logloss)
        accuracy=sum(w for g,y,w in joint if int(forecasts[g]>=F(1,2))==y)
        assert accuracy==(F(1,2) if len(reports)==1 else F(4,5))
    best=min(sum(w*(qs[g]-y)**2 for g,y,w in joint)
             for qs in product([F(i,10) for i in range(11)],repeat=2))
    assert best==F(4,25) and 1-best/F(1,4)==F(9,25)
    # An outcome-random normalization can change the optimum.
    p=F(1,2);baseline=F(1,5)
    skill=lambda q:sum(w*(1-(q-y)**2/(baseline-y)**2) for y,w in ((0,1-p),(1,p)))
    assert skill(F(1,17))>skill(p)
    checks.append('Exhaustive group/event calibration-resolution decomposition, proper conditional optimum, sharpness/accuracy counterexample and random-denominator incentive distortion')

    weighted=lambda q:F(9,10)*(1-q)**2+F(9,10)*q*q
    assert weighted(F(1,2))==F(9,20) and weighted(F(1,10))==F(369,500)
    assert all(weighted(F(i,100))>=weighted(F(1,2)) for i in range(101))
    values=[F(0),F(10),F(30)];weights=[F(1,5),F(1,2),F(3,10)]
    mean,second,var=moments(values,weights)
    assert (mean,second,var)==(14,320,124)
    squared=lambda a:sum(w*(y-a)**2 for y,w in zip(values,weights))
    absolute=lambda a:sum(w*abs(y-a) for y,w in zip(values,weights))
    pinball=lambda a:sum(w*(F(4,5)*(y-a) if y>=a else F(-1,5)*(y-a)) for y,w in zip(values,weights))
    assert squared(10)==140 and absolute(10)==8
    assert pinball(10)==F(26,5) and pinball(30)==F(16,5)
    for a in (F(i,10) for i in range(-100,401)):
        assert squared(a)>=124 and absolute(a)>=8 and pinball(a)>=F(16,5)
    checks.append('Weighted-Brier transformed optimum and exact point/median/asymmetric quantile losses against a dense action grid')

    b,v,pi,c=signal_problem(F(3,10),120,-40,F(4,5),F(1,5))
    assert (b,v,pi)==(8,F(116,5),36)
    assert c[1]==(F(19,50),F(12,19),F(1160,19))
    assert c[0]==(F(31,50),F(3,31),F(-760,31))
    assert v-b==F(76,5) and v-10-b==F(26,5)
    b,v,pi,c=signal_problem(F(1,5),100,-20,F(3,4),F(1,4))
    assert (b,v,pi)==(4,11,20)
    assert c[1]==(F(7,20),F(3,7),F(220,7))
    assert c[0]==(F(13,20),F(1,13),F(-140,13))
    assert v-8<b
    b,v,pi,c=signal_problem(F(9,10),50,-10,F(3,5),F(2,5))
    assert (b,v,pi)==(44,44,45)
    assert c[1][0:2]==(F(29,50),F(27,29))
    assert c[0][0:2]==(F(21,50),F(6,7))
    b,v,pi,c=signal_problem(F(1,5),100,-20,F(5,8),F(3,8))
    assert (b,v)==(4,F(13,2)) and c[1][1]==F(5,17) and c[0][1]==F(3,23)
    # Independent state -> original signal -> garbled signal enumeration.
    for flip in [F(i,20) for i in range(21)]:
        states=[]
        for theta,z,reverse in product((0,1),repeat=3):
            prior=F(1,5) if theta else F(4,5)
            likelihood=(F(3,4) if theta else F(1,4))
            weight=prior*(likelihood if z else 1-likelihood)*(flip if reverse else 1-flip)
            states.append((theta,z^reverse,weight))
        best=max(sum(w*rule[s]*(100 if theta else -20) for theta,s,w in states)
                 for rule in product((0,1),repeat=2))
        assert 4<=best<=11
    checks.append('Exact joint-state posterior and all-policy information values, fee comparisons, zero-value belief updates and enumerated garbling channels')

    for values,weights,conditional,mean,total,residual,explained in [
            ([0,2,6,8],[F(1,4)]*4,[1,1,7,7],4,10,1,9),
            ([-2,2,4,8],[F(1,8),F(3,8),F(1,4),F(1,4)],[1,1,6,6],F(7,2),F(39,4),F(7,2),F(25,4))]:
        m,_,v=moments(values,weights);assert (m,v)==(mean,total)
        assert sum(w*(x-c)**2 for x,c,w in zip(values,conditional,weights))==residual
        assert moments(conditional,weights)[2]==explained and residual+explained==total
        for cell in ([0,1],[2,3],[0,1,2,3],[]):
            assert sum(weights[i]*values[i] for i in cell)==sum(weights[i]*conditional[i] for i in cell)
        for a,b in product(range(-3,10),repeat=2):
            predictions=[a,a,b,b]
            direct=sum(w*(x-y)**2 for x,y,w in zip(values,predictions,weights))
            projection=residual+sum(w*(c-y)**2 for c,y,w in zip(conditional,predictions,weights))
            assert direct==projection>=residual
    for n in range(1,11):
        cells=2**n
        simple=sum((F(j,cells)*F(1,cells) for j in range(cells)),F(0))
        assert simple==F(1,2)*(1-F(1,cells))
        assert n*F(1,n)==1  # Spike law: magnitude n, mass 1/n.
    checks.append('Weighted information partitions, defining event identities, tower/projection/total variance and exact dyadic simple-integral versus spike laws')

    states=[(a,b,F(1,4)) for a,b in product((-1,1),repeat=2)]
    terminal=lambda a,b:3+2*a+a*b
    assert sum(w*terminal(a,b) for a,b,w in states)==3
    for a in (-1,1):
        assert sum(F(1,2)*terminal(a,b) for b in (-1,1))==3+2*a
    stopped=sum(w*(3+2*a if a==1 else terminal(a,b)) for a,b,w in states)
    hindsight=sum(w*max(3+2*a,terminal(a,b)) for a,b,w in states)
    assert stopped==3 and hindsight==F(7,2)
    for N in range(1,13):
        wealth=[]
        for bits in product((-1,1),repeat=N):
            gain=0
            for k,bit in enumerate(bits):
                gain+=2**k*bit
                if bit==1:break
            wealth.append(gain)
        assert sum(wealth)==0
        assert wealth.count(-(2**N-1))==1
        assert sum(abs(x) for x in wealth)*F(1,2**N)==2*(1-F(1,2**N))
        if N>=2:
            assert sum(abs(x) for x in wealth if abs(x)>F(3,2))*F(1,2**N)==1-F(1,2**N)
    checks.append('All two-sign forecast/stopping histories and hindsight bias; exhaustive doubling-game stopped expectations, absolute moments and persistent tails')

    # Independently integrate finite Pareto moments, avoiding sample-path claims.
    for cutoff in (1,2,4,9,25,100):
        near(simpson(lambda x:1.5*x**-1.5,1,cutoff,n=24000),3*(1-1/sqrt(cutoff)),tol=2e-8)
        near(simpson(lambda x:1.5*x**-.5,1,cutoff,n=24000),3*(sqrt(cutoff)-1),tol=2e-8)
        tail=simpson(lambda u:1.5*sqrt(u),0,1/cutoff,n=24000)
        near(tail,cutoff**-1.5,tol=4e-8)
    for r in [.001,.2,1,1.001,1.999,2,2.001,3,10,100]:
        partial=sum(1/i**2 for i in range(1,10001) if r<=i)
        assert r*r*partial<=2*r+1e-12
    # Exact finite summation-by-parts identity for unrelated sequences.
    for series in [[F((-1)**i,i) for i in range(1,80)],
                   [F(1,2**i) for i in range(1,80)]]:
        cumulative=[];s=F(0)
        for n,term in enumerate(series,1):
            s+=term;cumulative.append(s)
            lhs=sum(F(i)*series[i-1] for i in range(1,n+1))/n
            rhs=s-sum(cumulative[:-1],F(0))/n
            assert lhs==rhs
    # Unequal independent centered increments: full first-crossing partition.
    increments=[1,2,1,3,2,1];N=len(increments)
    for epsilon in [F(1,2),F(3,2),F(7,2),F(9,2)]:
        probability=F(0);cross_square=F(0);terminal_square=F(0)
        for signs in product((-1,1),repeat=N):
            partial=[];s=0
            for a,b in zip(increments,signs):s+=a*b;partial.append(s)
            weight=F(1,2**N);terminal_square+=weight*s*s
            first=next((k for k,v in enumerate(partial) if abs(v)>epsilon),None)
            if first is not None:
                probability+=weight;cross_square+=weight*partial[first]**2
        assert epsilon**2*probability<=cross_square<=terminal_square
        assert terminal_square==sum(i*i for i in increments)
    checks.append('Independent finite-cutoff heavy-tail integration, universal truncation bound diagnostics, exact Kronecker identities and exhaustive maximal first-crossing inequalities')
    return {'status':'passed','checks':checks,
            'limitations':['Finite-state/numerical diagnostics verify examples, not the general measure, conditional-expectation or integrable strong-law theorems. Those proofs receive a separate written author audit.']}


if __name__=='__main__':
    import json
    print(json.dumps(check(),indent=2))
