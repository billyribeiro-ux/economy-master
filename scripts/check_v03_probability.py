"""Exact state/record enumeration independent of the manuscript shortcuts."""
from fractions import Fraction as F
from itertools import combinations, product, permutations
from pathlib import Path
import importlib.util
import math


def law_probability(law,predicate):
    return sum((weight for record,weight in law.items() if predicate(record)),F(0))


def conditional(law,event,given):
    denominator=law_probability(law,given)
    assert denominator>0
    return law_probability(law,lambda r:event(r) and given(r))/denominator


def rejects(function):
    try: function()
    except ValueError: return
    raise AssertionError('Expected rejection')


def check():
    # Weighted state model and coherent/intersection boundaries.
    states={(0,0):F(42,100),(0,1):F(18,100),(1,0):F(1,10),(1,1):F(3,10)}
    assert sum(states.values())==1
    pa=law_probability(states,lambda r:r[0]==1); pb=law_probability(states,lambda r:r[1]==1)
    joint=law_probability(states,lambda r:r==(1,1))
    union=law_probability(states,lambda r:bool(r[0] or r[1]))
    assert (pa,pb,joint,union)==(F(2,5),F(12,25),F(3,10),F(29,50))
    assert pa*pb==F(24,125) and pa+pb-pa*pb==F(86,125)
    # Enumerate both uniform mechanisms from distinct labels.
    samples=list(combinations(range(12),4)); counts=[0]*4
    for sample in samples: counts[sum(label<3 for label in sample)]+=1
    assert len(samples)==495 and counts==[126,252,108,9]
    replacement_counts=[0]*5
    for sample in product(range(12),repeat=4):
        replacement_counts[sum(label<3 for label in sample)]+=1
    assert F(replacement_counts[1],12**4)==F(27,64)
    assert F(replacement_counts[0],12**4)==F(81,256)
    # Exercise 1: arbitrary weights and set operations.
    weights=dict(zip('abcd',[F(1,10),F(1,5),F(3,10),F(2,5)]))
    A=set('ac'); B=set('bc')
    prob=lambda s:sum((weights[x] for x in s),F(0))
    assert [prob(s) for s in (A,B,A&B,A|B,set(weights)-A,A-B)]==[
        F(2,5),F(1,2),F(3,10),F(3,5),F(3,5),F(1,10)]
    p,q,r=F(7,10),F(3,5),F(1,5)
    assert 1-p-q+r<0 and max(0,p+q-1)==F(3,10)
    r=F(2,5); assert [r,p-r,q-r,1-p-q+r]==[F(2,5),F(3,10),F(1,5),F(1,10)]
    # Committee counts from actual labels, not factorial formula.
    committees=list(combinations(range(8),3)); ordered=list(permutations(range(8),3))
    assert len(committees)==56 and len(ordered)==336
    mixed=sum(any(i<4 for i in c) and any(i>=4 for i in c) for c in committees)
    assert F(mixed,len(committees))==F(6,7)
    small=list(combinations(range(10),3)); distribution=[0]*4
    for sample in small: distribution[sum(i<4 for i in sample)]+=1
    assert F(distribution[2],len(small))==F(3,10)
    assert 1-F(distribution[0],len(small))==F(5,6)
    repl=list(product(range(10),repeat=3))
    assert F(sum(sum(i<4 for i in s)==2 for s in repl),len(repl))==F(36,125)
    assert F(sum(any(i<4 for i in s) for s in repl),len(repl))==F(98,125)
    # Pairwise but not mutual independence, including complement calculations.
    bits={r:F(1,4) for r in product((0,1),repeat=2)}
    events=[lambda r:r[0]==1,lambda r:r[1]==1,lambda r:r[0]!=r[1]]
    for event in events: assert law_probability(bits,event)==F(1,2)
    for first,second in combinations(events,2):
        assert law_probability(bits,lambda r:first(r) and second(r))==F(1,4)
    assert law_probability(bits,lambda r:all(e(r) for e in events))==0
    # Reconstruct the three-fault model by disjoint atoms, then recover inputs.
    fault_weights={(1,0,0):F(9,100),(0,1,0):F(14,100),(0,0,1):F(12,100),
                   (1,1,0):F(6,100),(1,0,1):F(3,100),(0,1,1):F(8,100),
                   (1,1,1):F(2,100),(0,0,0):F(46,100)}
    assert sum(fault_weights.values())==1
    assert [law_probability(fault_weights,lambda r:sum(r)==j) for j in range(4)]==[
        F(46,100),F(35,100),F(17,100),F(2,100)]
    assert [law_probability(fault_weights,lambda r:r[j]==1) for j in range(3)]==[F(1,5),F(3,10),F(1,4)]
    assert [law_probability(fault_weights,lambda r:r[i] and r[j]) for i,j in combinations(range(3),2)]==[F(2,25),F(1,20),F(1,10)]
    assert (1-F(3,10))*(1-F(2,5))==F(21,50)
    # Finite geometric sums plus exact remainder, not a float tail claim.
    for n in (4,10,30):
        assert sum((F(1,2)**j for j in range(4,n+1)),F(0))+F(1,2)**n==F(1,8)
    for n in (1,5,20):
        assert sum((F(1,2)**(2*j+1) for j in range(n)),F(0))+F(2,3)*F(1,4)**n==F(2,3)

    # Conditional probabilities: census tables form a joint law independent
    # of directly substituting into the manuscript's Bayes formula.
    numbers={i:F(1,12) for i in range(1,13)}
    assert conditional(numbers,lambda i:i%2==0,lambda i:i%3==0)==F(1,2)
    assert conditional(numbers,lambda i:i%3==0,lambda i:i%2==0)==F(1,3)
    invoice={(1,1):F(170,10000),(1,0):F(30,10000),
             (0,1):F(392,10000),(0,0):F(9408,10000)}
    assert sum(invoice.values())==1
    posterior=conditional(invoice,lambda r:r[0]==1,lambda r:r[1]==1)
    negative=conditional(invoice,lambda r:r[0]==1,lambda r:r[1]==0)
    assert posterior==F(85,281) and negative==F(5,1573)
    assert law_probability(invoice,lambda r:r[0]==r[1])==F(4789,5000)
    assert F(1,49)*F(85,4)==posterior/(1-posterior)
    for prior,expected in ((F(1,10),F(85,121)),(F(1,1000),F(85,4081))):
        assert F(17,20)*prior/(F(17,20)*prior+F(1,25)*(1-prior))==expected
    assert F(1,25)/(F(17,20)+F(1,25))==F(4,89)
    # Poor/good lots and both observations are explicitly enumerated jointly.
    lot={}
    for quality,first,second in product((0,1),repeat=3):
        prior=F(1,4) if quality else F(3,4)
        rate=F(3,5) if quality else F(1,5)
        lot[(quality,first,second)]=prior*(rate if first else 1-rate)*(rate if second else 1-rate)
    assert sum(lot.values())==1
    two=lambda r:r[1]==r[2]==1
    one=lambda r:r[1]==1
    ordered=lambda r:r[1]==1 and r[2]==0
    assert law_probability(lot,two)==F(3,25)
    assert law_probability(lot,one)==F(3,10)
    assert conditional(lot,lambda r:r[0]==1,two)==F(3,4)
    assert conditional(lot,lambda r:r[0]==1,one)==F(1,2)
    assert conditional(lot,lambda r:r[0]==1,ordered)==F(1,3)
    assert conditional(lot,lambda r:r[0]==1,lambda r:r[1]+r[2]==1)==F(1,3)
    # Add a next test to the joint state table; recover prediction by enumeration.
    extended={}
    for r,weight in lot.items():
        rate=F(3,5) if r[0] else F(1,5)
        for third in (0,1): extended[r+(third,)]=weight*(rate if third else 1-rate)
    assert conditional(extended,lambda r:r[3]==1,two)==F(1,2)
    assert conditional(extended,lambda r:r[3]==1,ordered)==F(1,3)
    duplicate={}
    for quality,first in product((0,1),repeat=2):
        prior=F(1,4) if quality else F(3,4); rate=F(3,5) if quality else F(1,5)
        duplicate[(quality,first,first)]=prior*(rate if first else 1-rate)
    assert conditional(duplicate,lambda r:r[0]==1,two)==F(1,2)
    # Selection creates dependence in the originally independent bit law.
    retained=lambda r:r[0] or r[1]
    assert conditional(bits,lambda r:r[0]==1,retained)==F(2,3)
    assert conditional(bits,lambda r:r[1]==1,retained)==F(2,3)
    assert conditional(bits,lambda r:r==(1,1),retained)==F(1,3)
    # All exercise tables, including three-way normalization and uncertainty input.
    alternate={(1,1):F(270,10000),(1,0):F(30,10000),
               (0,1):F(582,10000),(0,0):F(9118,10000)}
    assert conditional(alternate,lambda r:r[0]==1,lambda r:r[1]==1)==F(45,142)
    assert conditional(alternate,lambda r:r[0]==1,lambda r:r[1]==0)==F(15,4574)
    assert law_probability(alternate,lambda r:r[0]==r[1])==F(2347,2500)
    prior=(F(1,2),F(1,3),F(1,6)); likelihood=(F(1,5),F(1,2),F(4,5))
    joint=[p*l for p,l in zip(prior,likelihood)]
    assert sum(joint)==F(2,5)
    assert [v/sum(joint) for v in joint]==[F(1,4),F(5,12),F(1,3)]
    for alpha,target in ((F(1,100),F(80,129)),(F(1,20),F(16,65))):
        assert F(2,125)/(F(2,125)+F(49,50)*alpha)==target
    assert F(2,125)/F(49,50)==F(4,245)
    # Stopping evidence: explicitly sum ordered paths of length three.
    stopping={}
    for high,record in product((0,1),product((0,1),repeat=3)):
        rate=F(2,5) if high else F(1,5)
        weight=F(1,2)
        for flag in record: weight*=rate if flag else 1-rate
        stopping[(high,)+record]=weight
    assert conditional(stopping,lambda r:r[0]==1,lambda r:r[1:]==(0,0,1))==F(9,17)
    assert conditional(stopping,lambda r:r[0]==1,lambda r:r[1]==1)==F(2,3)
    # Rate sensitivity derivative independently checked by centered differences.
    post=lambda pi:.85*pi/(.85*pi+.04*(1-pi))
    h=1e-6; pi=.02
    derivative=(post(pi+h)-post(pi-h))/(2*h)
    expected=.85*.04/(.04+(.85-.04)*pi)**2
    assert math.isclose(derivative,expected,rel_tol=1e-8)

    # Downloadable laboratory checked against separately enumerated results.
    path=Path(__file__).resolve().parents[1]/'content/projects/v03-probability-lab.py'
    spec=importlib.util.spec_from_file_location('probability_lab',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.archive_distribution(12,3,4)=={i:F(count,495) for i,count in enumerate(counts)}
    assert module.archive_distribution(12,3,4,True)=={i:F(count,12**4) for i,count in enumerate(replacement_counts)}
    result=module.bayes({'H':F(1,50),'other':F(49,50)},{'H':F(17,20),'other':F(1,25)})
    assert result['evidence']==F(281,5000) and result['posterior']['H']==posterior
    assert module.archive_distribution(10,4,0)=={0:F(1)}
    rejects(lambda:module.archive_distribution(10,4,11))
    rejects(lambda:module.bayes({'H':F(1,2),'other':F(1,2)},{'H':0,'other':0}))
    rejects(lambda:module.bayes({'H':F(1,2),'other':F(1,4)},{'H':1,'other':1}))
    return {'scope':'v03-c01 and v03-c02',
        'methods':['exact weighted event tables and coherent atom bounds',
                   'exhaustive labeled subset/ordered-record counts under both draw mechanisms',
                   'pairwise/mutual independence and three-event disjoint-atom reconstruction',
                   'exact geometric sums with remainder',
                   'joint-census Bayes and odds checks',
                   'latent-quality, sequential, duplicate, prediction and selection state enumeration',
                   'stopping-rule likelihoods and sensitivity derivative cross-check',
                   'downloadable lab compared against independent finite calculations'],
        'limitation':'Finite calculations check original problems; probability axioms, continuity and general conditional identities have separate analytic review.'}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
