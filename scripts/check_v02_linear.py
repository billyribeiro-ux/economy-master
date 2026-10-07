"""Exact-system and geometric cross-checks for v02-c05 and v02-c06.

Printed answers are checked by rational elimination, direct products, residual
orthogonality, explicit synthetic states and independent recurrence iteration.
These numerical identities do not certify every quantified theorem or provide
statistical/causal validation; see the separate author review.
"""
from fractions import Fraction as F
import math


def dot(a,b):
    assert len(a)==len(b)
    return sum(x*y for x,y in zip(a,b))


def transpose(a):
    return [list(row) for row in zip(*a)]


def mv(a,x):
    return [dot(row,x) for row in a]


def mm(a,b):
    return [[dot(row,column) for column in transpose(b)] for row in a]


def rref(a):
    rows=[[F(value) for value in row] for row in a]
    pivots=[]; pivot_row=0
    for col in range(len(rows[0])):
        candidate=next((i for i in range(pivot_row,len(rows)) if rows[i][col]),None)
        if candidate is None: continue
        rows[pivot_row],rows[candidate]=rows[candidate],rows[pivot_row]
        divisor=rows[pivot_row][col]
        rows[pivot_row]=[value/divisor for value in rows[pivot_row]]
        for i in range(len(rows)):
            if i!=pivot_row:
                multiple=rows[i][col]
                rows[i]=[x-multiple*y for x,y in zip(rows[i],rows[pivot_row])]
        pivots.append(col); pivot_row+=1
        if pivot_row==len(rows): break
    return rows,pivots


def inverse(a):
    n=len(a)
    reduced,pivots=rref([list(row)+[int(i==j) for j in range(n)] for i,row in enumerate(a)])
    assert pivots[:n]==list(range(n))
    return [row[n:] for row in reduced]


def close(a,b,tolerance=1e-10):
    assert math.isclose(a,b,rel_tol=tolerance,abs_tol=tolerance),(a,b)


def check():
    # c05 worked systems and all determinate exercise results.
    a=[[2,1],[1,3]]; ainv=inverse(a)
    assert ainv==[[F(3,5),F(-1,5)],[F(-1,5),F(2,5)]]
    assert mv(ainv,[14,17])==[5,4] and mv(a,[5,4])==[14,17]
    assert mv(ainv,[1,10])==[F(-7,5),F(19,5)]
    b=[[1,2,3],[2,4,6]]
    reduced,pivots=rref(b)
    assert pivots==[0] and reduced==[[1,2,3],[0,0,0]]
    for s,t in ((0,0),(6,0),(0,4),(1,2),(-2,5)):
        assert mv(b,[12-2*s-3*t,s,t])==[12,24]
    assert mv(b,[-2,1,0])==mv(b,[-3,0,1])==[0,0]
    assert len(rref([[1,2,3,12],[2,4,6,25]])[1])==2
    assert dot([2,7,4],[3,2,5])==40 and dot([3,2,5],[3,2,5])==38
    assert [3+1,2+0,5-2]==[4,2,3]
    a2=[[1,2],[0,1]]; b2=[[2,0],[1,3]]
    assert mm(a2,b2)==[[4,6],[1,3]] and mm(b2,a2)==[[2,4],[1,5]]
    assert transpose(mm(a2,b2))==mm(transpose(b2),transpose(a2))
    a3=[[1,1,1],[2,1,3],[1,-1,1]]
    assert mv(a3,[1,2,3])==[6,13,2]
    assert mv(inverse(a3),[6,13,2])==[1,2,3]
    dependent=[[1,2,-1],[2,4,-2]]
    assert rref(dependent)[1]==[0]
    assert mv(dependent,[-2,1,0])==mv(dependent,[1,0,1])==[0,0]
    for s,t in ((0,0),(1,3),(-5,2)):
        assert mv(dependent,[6-2*s+t,s,t])==[6,12]
    assert len(rref([[1,2,-1,6],[2,4,-2,13]])[1])==2
    u=[1,1,0]; v=[0,1,1]
    assert [x+y for x,y in zip(u,v)]==[1,2,1]
    assert [2*x+y for x,y in zip(u,v)]==[2,3,1]
    assert len(rref(transpose([u,v]))[1])==2
    a4=[[3,1],[2,1]]; a4inv=inverse(a4)
    assert a4inv==[[1,-1],[-2,3]]
    assert mm(a4,a4inv)==mm(a4inv,a4)==[[1,0],[0,1]]
    assert mv(a4inv,[11,8])==[3,2]
    params=[[1,1],[2,2]]
    assert mv(params,[3,1])==[4,8] and mv(params,[1,-1])==[0,0]
    assert dot([1,-1],[3,1])==2
    for delta,expected in ((F(0),[F(1),F(1)]),(F(1,100),[F(-9),F(11)])):
        eps=F(1,1000)
        result=mv(inverse([[1,1],[1,1+eps]]),[2,2+eps+delta])
        assert result==expected

    # c06: projection and least squares from exact matrix computations.
    line=[F(1),F(2)]; observed=[F(3),F(0)]
    coefficient=dot(line,observed)/dot(line,line)
    projection=[coefficient*x for x in line]
    residual=[x-y for x,y in zip(observed,projection)]
    assert coefficient==F(3,5) and projection==[F(3,5),F(6,5)]
    assert residual==[F(12,5),F(-6,5)] and dot(line,residual)==0
    assert dot(projection,projection)==F(9,5) and dot(residual,residual)==F(36,5)
    assert dot(observed,observed)==dot(projection,projection)+dot(residual,residual)
    for design,obs,coeffs,fitted,errors in (
        ([[1,-1],[1,0],[1,1]],[1,2,4],[F(7,3),F(3,2)],
         [F(5,6),F(7,3),F(23,6)],[F(1,6),F(-1,3),F(1,6)]),
        ([[1,0],[1,1],[1,2]],[1,2,2],[F(7,6),F(1,2)],
         [F(7,6),F(5,3),F(13,6)],[F(-1,6),F(1,3),F(-1,6)])):
        at=transpose(design); gram=mm(at,design)
        computed=mv(inverse(gram),mv(at,obs))
        assert computed==coeffs and mv(design,computed)==fitted
        actual_errors=[x-y for x,y in zip(obs,fitted)]
        assert actual_errors==errors and mv(at,actual_errors)==[0,0]
        assert dot(actual_errors,actual_errors)==F(1,6)
        p=mm(mm(design,inverse(gram)),at)
        assert transpose(p)==p and mm(p,p)==p and mv(p,obs)==fitted
        if design[0][1]==-1:
            assert p==[[F(value,6) for value in row] for row in [[5,2,-1],[2,2,2],[-1,2,5]]]
            assert dot([1,2],computed)==F(16,3)
        else:
            assert gram==[[3,3],[3,5]] and mv(at,obs)==[5,6]

    # Eigenstructure reconstructed through products rather than a library solver.
    plus=[1,1]; minus=[1,-1]
    for symmetric,lp,lm in (([[4,2],[2,4]],6,2),([[3,1],[1,3]],4,2),
                            ([[2,1],[1,2]],3,1),([[1,1],[1,1]],2,0),
                            ([[1,2],[2,1]],3,-1)):
        assert mv(symmetric,plus)==[lp,lp] and mv(symmetric,minus)==[lm,-lm]
        for i in range(2):
            for j in range(2):
                assert F(lp,2)*plus[i]*plus[j]+F(lm,2)*minus[i]*minus[j]==symmetric[i][j]
    assert dot(minus,mv([[3,1],[1,3]],minus))==4
    assert dot(minus,mv([[1,1],[1,1]],minus))==0
    assert dot(plus,mv([[1,2],[2,1]],plus))==6
    assert dot(minus,mv([[1,2],[2,1]],minus))==-2
    jordan=[[1,1],[0,1]]; power=[[1,0],[0,1]]
    for t in range(1,6):
        power=mm(power,jordan)
        assert power==[[1,t],[0,1]]

    # Recompute covariance independently from the four stated joint outcomes.
    states=[[math.sqrt(6),math.sqrt(6)],[-math.sqrt(6),-math.sqrt(6)],
            [math.sqrt(2),-math.sqrt(2)],[-math.sqrt(2),math.sqrt(2)]]
    sigma=[[4,2],[2,4]]
    for i in range(2):
        close(sum(s[i] for s in states)/4,0)
        for j in range(2): close(sum(s[i]*s[j] for s in states)/4,sigma[i][j])
    for weights,expected in (([F(1,2),F(1,2)],F(3)),
                             ([F(3,4),F(1,4)],F(13,4)),([1,-1],F(4))):
        assert dot(weights,mv(sigma,weights))==expected
        close(sum(dot(weights,state)**2 for state in states)/4,float(expected))

    # Direct recurrence iteration against the derived eigenbasis expression.
    m=[[F(4,5),F(1,10)],[F(1,10),F(4,5)]]; x=[F(3),F(1)]
    for t in range(1,13):
        x=mv(m,x)
        common=2*F(9,10)**t; difference=F(7,10)**t
        assert x==[common+difference,common-difference]
        if t==1: assert x==[F(5,2),F(11,10)]
        if t==2: assert x==[F(211,100),F(113,100)]

    # Singular directions and Gram-Schmidt/QR reconstruction.
    rect=[[3,0],[0,1],[0,0]]
    assert mm(transpose(rect),rect)==[[9,0],[0,1]]
    assert mv(rect,[2,2])==[6,2,0] and dot([0,0,5],[0,0,5])==25
    weak=[[F(3),F(0)],[F(0),F(1,100)]]
    assert mm(transpose(weak),weak)==[[9,0],[0,F(1,10000)]]
    assert F(3)/F(1,100)==300
    assert mv(inverse(weak),[3,F(1,100)])==[1,1]
    assert mv(inverse(weak),[3,F(1,50)])==[1,2]
    q1=[1/math.sqrt(2),1/math.sqrt(2),0]
    q2=[-1/math.sqrt(6),1/math.sqrt(6),2/math.sqrt(6)]
    close(dot(q1,q1),1); close(dot(q2,q2),1); close(dot(q1,q2),0)
    q=transpose([q1,q2]); r=[[math.sqrt(2),1/math.sqrt(2)],[0,math.sqrt(3/2)]]
    reconstructed=mm(q,r)
    for actual,expected in zip(reconstructed,[[1,0],[1,1],[0,1]]):
        for x,y in zip(actual,expected): close(x,y)
    return {'scope':'v02-c05 and v02-c06',
            'methods':['exact rational row reduction and inverse products',
                       'solution families and null-space witnesses',
                       'residual orthogonality and projection identities',
                       'eigenfactor reconstruction and independent recurrence iteration',
                       'covariance recomputation from explicit joint states',
                       'singular-direction and QR reconstruction checks'],
            'limitation':'Finite numerical checks do not prove the general theorems or validate causal/statistical assumptions.'}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
