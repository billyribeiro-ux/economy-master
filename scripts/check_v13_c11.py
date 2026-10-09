"""Quiet, bounded, standard-library audit of the four-file V13-C11 package.

check(root=None) reads only FILES, writes nothing, and returns a JSON-safe summary.
Finite enumeration is an arithmetic oracle, not a substitute for the prose proofs.
"""
from __future__ import annotations
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, permutations, product
import json
import math
from pathlib import Path
import re
import sys

FILES=('content/chapters/v13-c11.html','scripts/check_v13_c11.py',
       'content/reviews/v13-c11-sources.json','content/reviews/v13-c11-author.json')
URLS={
 'v05-c11-manea-matching':'https://ocw.mit.edu/courses/14-16-strategy-and-information-spring-2016/53dbe8d681978367f9c04182aa3c9b97_MIT14_16S16_Matching.pdf',
 'v13-c11-ght-menu2026':'https://arxiv.org/pdf/2209.13148v4',
 'v13-c11-pass-assignment':'https://www.cs.cornell.edu/~rafael/networks-html/chapter8.html',
 'v13-c11-bkd-networks2014':'https://sites.duke.edu/rachelkranton/files/2016/09/strategic-interaction-and-networks-aer.pdf',
 'v13-c11-jackson-network-formation':'https://web.stanford.edu/~jacksonm/netsurv.pdf'}
ROUTES={'v05-c11.html','v13-c06.html','v13-c10.html','v13-c12.html'}


def need(ok,label):
    if not ok:raise ValueError(label)


def number(value):
    need(type(value) in (int,float,F),'real numeric type; bool excluded')
    if type(value) is float:
        need(math.isfinite(value),'finite number');value=F(str(value))
    else:value=F(value)
    need(abs(value)<=10**6 and value.denominator<=10**12,'bounded magnitude and reduced denominator')
    return value


def vector(value,n=None,maximum=4):
    need(type(value) in (list,tuple) and 1<=len(value)<=maximum,'bounded nonempty vector')
    need(n is None or len(value)==n,'vector dimension')
    return tuple(number(x) for x in value)


def strict_json(text):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate JSON key');out[k]=v
        return out
    def constant(_):raise ValueError('nonfinite JSON constant')
    data=json.loads(text,object_pairs_hook=pairs,parse_constant=constant)
    def walk(x):
        if type(x) is float:need(math.isfinite(x),'finite JSON number')
        elif type(x) is list:
            for v in x:walk(v)
        elif type(x) is dict:
            for v in x.values():walk(v)
    walk(data);return data


def fmt(x):
    if type(x) in (list,tuple):return '('+','.join(fmt(v) for v in x)+')'
    x=F(x);return str(x.numerator) if x.denominator==1 else str(x)


def instance(P,R):
    need(type(P) is dict and type(R) is dict and len(P)<=4 and len(R)<=4,'at most four names per side')
    need(not set(P).intersection(R),'disjoint agent names')
    for side,other in [(P,R),(R,P)]:
        for i,order in side.items():
            need(type(i) is str and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,11}',i) is not None,'bounded string agent name')
            need(type(order) in (list,tuple),'ordered list report')
            need(all(type(j) is str and j in other for j in order),'known opposite-side name')
            need(len(order)==len(set(order)),'strict list without duplicate names')
    return {i:tuple(r) for i,r in P.items()},{j:tuple(r) for j,r in R.items()}


def deferred(P,R):
    """Simultaneous rounds, independent of the preparation's one-proposal queue."""
    P,R=instance(P,R);positions={i:0 for i in P};held={j:None for j in R};trace=[]
    while True:
        matched={i for i in held.values() if i is not None}
        offers={j:[] for j in R}
        for i in P:
            if i not in matched and positions[i]<len(P[i]):
                j=P[i][positions[i]];positions[i]+=1;offers[j].append(i);trace.append((i,j))
        if not any(offers.values()):break
        for j in R:
            candidates=offers[j]+([] if held[j] is None else [held[j]])
            candidates=[i for i in candidates if i in R[j]]
            held[j]=min(candidates,key=R[j].index) if candidates else None
    out={i:None for i in P}
    for j,i in held.items():
        if i is not None:out[i]=j
    return out,tuple(trace)


def ir_matchings(P,R):
    P,R=instance(P,R)
    choices=[(None,)+tuple(j for j in P[i] if i in R[j]) for i in P]
    for values in product(*choices):
        assigned=[j for j in values if j is not None]
        if len(set(assigned))==len(assigned):yield dict(zip(P,values))


def blocking(P,R,mu):
    P,R=instance(P,R)
    need(type(mu) is dict and set(mu)==set(P),'matching has exact proposer domain')
    assigned=[j for j in mu.values() if j is not None]
    need(all(type(j) is str and j in R for j in assigned) and len(assigned)==len(set(assigned)),'feasible one-to-one matching')
    need(all(j is None or j in P[i] and i in R[j] for i,j in mu.items()),'individual rationality of supplied matching')
    holder={j:i for i,j in mu.items() if j is not None};out=[]
    for i in P:
        for j in P[i]:
            if i not in R[j]:continue
            i_wants=mu[i] is None or P[i].index(j)<P[i].index(mu[i])
            j_wants=j not in holder or R[j].index(i)<R[j].index(holder[j])
            if i_wants and j_wants:out.append((i,j))
    return tuple(out)


def stable_set(P,R):return tuple(m for m in ir_matchings(P,R) if not blocking(P,R,m))


def all_reports(names):
    return tuple(r for k in range(len(names)+1) for r in permutations(names,k))


def menu(P,R,i):
    P,R=instance(P,R);need(type(i) is str and i in P,'menu applicant')
    without={a:r for a,r in P.items() if a!=i}
    priorities={h:tuple(a for a in r if a!=i) for h,r in R.items()}
    smaller,_=deferred(priorities,without)
    return frozenset([None]+[h for h,r in R.items() if i in r and (smaller[h] is None or r.index(i)<r.index(smaller[h]))]),smaller


def matrix(values):
    need(type(values) in (list,tuple) and 1<=len(values)<=4,'bounded matrix rows')
    rows=tuple(vector(row) for row in values)
    need(all(len(row)==len(rows[0]) for row in rows),'rectangular matrix')
    return rows


def assignment_problem(values,allowed=None):
    values=matrix(values);n=len(values);m=len(values[0])
    if allowed is None:allowed=tuple(tuple(True for _ in range(m)) for _ in range(n))
    need(type(allowed) in (list,tuple) and len(allowed)==n,'allowed-edge row count')
    need(all(type(row) in (list,tuple) and len(row)==m and all(type(v) is bool for v in row) for row in allowed),'Boolean allowed-edge matrix')
    return values,tuple(tuple(r) for r in allowed)


def allocations(values,allowed=None):
    v,a=assignment_problem(values,allowed);n=len(v);m=len(v[0]);out=[]
    for row in product((None,)+tuple(range(m)),repeat=n):
        used=[j for j in row if j is not None]
        if len(set(used))!=len(used):continue
        if any(j is not None and not a[i][j] for i,j in enumerate(row)):continue
        out.append((row,sum((v[i][j] for i,j in enumerate(row) if j is not None),F(0))))
    return tuple(out)


def certificate(values,allowed,utilities,prices,chosen):
    v,a=assignment_problem(values,allowed);n=len(v);m=len(v[0]);u=vector(utilities,n);p=vector(prices,m)
    need(all(z>=0 for z in u+p),'nonnegative certificate utilities and prices')
    need(type(chosen) in (list,tuple) and len(chosen)==n,'chosen assignment dimension')
    need(all(j is None or type(j) is int and 0<=j<m for j in chosen),'assignment object indices')
    used=[j for j in chosen if j is not None]
    need(len(used)==len(set(used)) and all(j is None or a[i][j] for i,j in enumerate(chosen)),'feasible chosen assignment')
    feasible=all(u[i]+p[j]>=v[i][j] for i in range(n) for j in range(m) if a[i][j])
    tight=all(u[i]==0 if j is None else u[i]+p[j]==v[i][j] for i,j in enumerate(chosen))
    tight=tight and all(p[j]==0 for j in range(m) if j not in used)
    return feasible and tight,sum(u)+sum(p)


def solve(A,b):
    n=len(b);need(1<=n<=4 and len(A)==n and all(len(r)==n for r in A),'small square linear system')
    rows=[[F(x) for x in row]+[F(y)] for row,y in zip(A,b)]
    for j in range(n):
        k=next((k for k in range(j,n) if rows[k][j]),None)
        if k is None:return None
        rows[j],rows[k]=rows[k],rows[j];scale=rows[j][j];rows[j]=[z/scale for z in rows[j]]
        for k in range(n):
            if k!=j:
                scale=rows[k][j];rows[k]=[x-scale*y for x,y in zip(rows[k],rows[j])]
    return tuple(row[-1] for row in rows)


def game(a,B,cap=None):
    a=vector(a,maximum=3);n=len(a);B=matrix(B)
    need(len(B)==n and all(len(r)==n for r in B) and all(B[i][i]==0 for i in range(n)),'network game dimension and zero diagonal')
    if cap is not None:
        cap=number(cap);need(cap>0,'positive action cap')
    return a,B,cap


def best_reply(a,B,x,cap=None):
    a,B,cap=game(a,B,cap);x=vector(x,len(a),3)
    need(all(z>=0 and (cap is None or z<=cap) for z in x),'feasible action profile')
    out=tuple(max(F(0),a[i]+sum(B[i][j]*x[j] for j in range(len(a)))) for i in range(len(a)))
    return out if cap is None else tuple(min(z,cap) for z in out)


def payoffs(a,B,x):
    a,B,_=game(a,B);x=vector(x,len(a),3);need(all(z>=0 for z in x),'nonnegative actions')
    return tuple(a[i]*x[i]-x[i]**2/2+x[i]*sum(B[i][j]*x[j] for j in range(len(a))) for i in range(len(a)))


def equilibrium_faces(a,B,cap=None):
    """All nonsingular active faces; singular faces reported, never silently discarded."""
    a,B,cap=game(a,B,cap);n=len(a);points=set();singular=[]
    labels=(0,1) if cap is None else (0,1,2)  # zero, interior, upper
    for state in product(labels,repeat=n):
        free=[i for i,s in enumerate(state) if s==1]
        x=[F(0) if s!=2 else cap for s in state]
        if free:
            A=[[F(i==j)-B[i][j] for j in free] for i in free]
            rhs=[a[i]+sum(B[i][j]*x[j] for j in range(n) if j not in free) for i in free]
            y=solve(A,rhs)
            if y is None:singular.append(state);continue
            for i,z in zip(free,y):x[i]=z
        if any(z<0 or cap is not None and z>cap for z in x):continue
        if best_reply(a,B,x,cap)==tuple(x):points.add(tuple(x))
    return tuple(sorted(points)),tuple(singular)


def funded_effort(x):
    x=vector(x,3,3);need(all(0<=z<=4 for z in x),'funded effort action cap')
    s=(F(1),F(3,2),F(1));sub=tuple(si*xi for si,xi in zip(s,x))
    fee=tuple(sum(sub[j] for j in range(3) if j!=i)/2 for i in range(3))
    cash=tuple(10-fee[i]+sub[i] for i in range(3))
    return sub,fee,cash


EDGES=((0,1),(0,2),(1,2))
GRAPHS=tuple(frozenset(e for k,e in enumerate(EDGES) if bits>>k&1) for bits in range(8))


def network(g,r,c,t=0):
    need(type(g) in (list,tuple,set,frozenset) and len(g)<=3,'at most three undirected edges')
    edges=[]
    for e in g:
        need(type(e) in (list,tuple) and len(e)==2 and all(type(i) is int and 0<=i<3 for i in e),'three-node integer endpoints')
        need(e[0]<e[1],'sorted nonloop edge');edges.append(tuple(e))
    need(len(edges)==len(set(edges)),'no duplicate edge')
    r=number(r);c=number(c);t=number(t)
    need(0<r<1 and c>=0 and t>=0,'discounted positive link benefit and nonnegative costs/transfers')
    g=frozenset(edges)
    # With three nodes, the only possible indirect route uses the remaining node.
    gross=[];cost=[];payment=[F(0)]*3
    for i in range(3):
        benefit=F(0)
        for j in range(3):
            if i==j:continue
            e=tuple(sorted((i,j)))
            if e in g:benefit+=r
            else:
                k=3-i-j
                if tuple(sorted((i,k))) in g and tuple(sorted((k,j))) in g:benefit+=r*r
        gross.append(benefit);cost.append(c*sum(i in e for e in g))
    for leaf in (0,2):
        if tuple(sorted((leaf,1))) in g:payment[leaf]-=t;payment[1]+=t
    utility=tuple(gross[i]-cost[i]+payment[i] for i in range(3))
    cash=tuple(2-cost[i]+payment[i] for i in range(3))
    prefunded=all(2>=cost[i]+max(F(0),-payment[i]) for i in range(3))
    return utility,tuple(gross),tuple(cost),tuple(payment),cash,prefunded


def pairwise(g,r,c,t=0):
    u=network(g,r,c,t)[0];g=frozenset(tuple(e) for e in g)
    for e in EDGES:
        changed=g-{e} if e in g else g|{e};v=network(changed,r,c,t)[0]
        gains=tuple(v[i]-u[i] for i in e)
        if e in g and any(z>0 for z in gains):return False
        if e not in g and all(z>=0 for z in gains) and any(z>0 for z in gains):return False
    return True


class Audit:
    def __init__(self):self.comparisons=0;self.rejections=0
    def equal(self,x,y,label):
        self.comparisons+=1;need(x==y,label)
    def reject(self,call,label):
        try:call()
        except (ValueError,TypeError,json.JSONDecodeError):self.rejections+=1;return
        raise ValueError('expected rejection: '+label)


def numerical(audit):
    A=audit;anchors={}
    def anchor(name,value):anchors[name]=fmt(value)
    P1={'A':('X','Y'),'B':('Y','X'),'C':('Z',),'D':('Z',)}
    R1={'X':('B','A'),'Y':('A','B'),'Z':('C','D')}
    P2={'A':('X','Y','Z','W'),'B':('Y','Z','X','W'),'C':('Z','X','Y','W'),'D':('X','W','Y','Z')}
    R2={'X':('C','A','D','B'),'Y':('A','B','C','D'),'Z':('B','C','A','D'),'W':('D','A','B','C')}
    total_reports=0;total_stable_profiles=0
    for case,P,R,ir_count in [(1,P1,R1,21),(2,P2,R2,209)]:
        ir=tuple(ir_matchings(P,R));ss=stable_set(P,R);mu,_=deferred(P,R)
        A.equal(len(ir),ir_count,'IR matching count');A.equal(len(ss),2,'complete stable set count')
        expected=(('X','Y','Z',None),('Y','X','Z',None)) if case==1 else (('X','Y','Z','W'),('Y','Z','X','W'))
        A.equal({tuple(m[i] for i in P) for m in ss},set(expected),'all stable partners')
        A.equal(tuple(mu.values()),expected[0],'applicant-proposing outcome')
        ip,_=deferred(R,P);inv={i:None for i in P}
        for h,i in ip.items():
            if i is not None:inv[i]=h
        A.equal(tuple(inv.values()),expected[1],'institution-proposing outcome')
        anchor(f'w{case}-ir',ir_count)
        reports=0
        for i in P:
            S,smaller=menu(P,R,i);reject=dict(P);reject[i]=()
            _,offers=deferred(R,reject)
            A.equal(S,frozenset([None]+[h for h,who in offers if who==i]),'removed-market and reject-all menus')
            reachable=set();truth=list(P[i])+[None]+[h for h in R if h not in P[i]]
            for report in all_reports(tuple(R)):
                changed=dict(P);changed[i]=report;out,_=deferred(changed,R);reachable.add(out[i])
                expected_best=next((h for h in report if h in S),None)
                A.equal(out[i],expected_best,'fixed menu for complete report domain')
                A.equal(truth.index(mu[i])<=truth.index(out[i]),True,'truth weakly dominates report')
                feasible_stable=stable_set(changed,R);total_stable_profiles+=1
                A.equal(out in feasible_stable,True,'DA outcome independently stable after report')
                for m in feasible_stable:
                    for who in P:
                        ranking=list(changed[who])+[None]
                        A.equal(ranking.index(out[who])<=ranking.index(m[who]),True,'proposer optimality against exhaustive stable set')
                reports+=1
            A.equal(reachable,S,'every menu element attainable')
        A.equal(reports,64 if case==1 else 260,'complete ordered-subset report count')
        anchor(f'w{case}-reports',reports);total_reports+=reports
    anchor('w1-stable',2)
    A.equal(menu(P1,R1,'A')[1],{'X':None,'Y':'B','Z':'C'},'peer-repaired removed-A IPDA trace')
    A.equal(menu(P1,R1,'B')[1],{'X':'A','Y':None,'Z':'C'},'removed-B IPDA trace')
    A.equal(menu(P1,R1,'C')[1],{'X':'B','Y':'A','Z':'D'},'removed-C IPDA trace')
    A.equal(menu(P1,R1,'D')[1],{'X':'B','Y':'A','Z':'C'},'removed-D IPDA trace')
    smallP={i:r for i,r in P1.items() if i!='C'};smallR={h:tuple(i for i in r if i!='C') for h,r in R1.items()}
    A.equal(deferred(smallP,smallR)[0],{'A':'X','B':'Y','D':'Z'},'removed participant intervention')
    reverse=dict(R1);reverse['Z']=('D','C')
    A.equal(deferred(P1,reverse)[0],{'A':'X','B':'Y','C':None,'D':'Z'},'priority intervention')
    for P,R in [({},{}),({'A':()},{}),({},{'X':()}),({'A':()},{'X':('A',)})]:
        A.equal(deferred(P,R)[0],{i:None for i in P},'empty market/outside')
    A.equal(deferred({'A':('X',)},{'X':('A',)})[0],{'A':'X'},'falsely acceptable report can harm true empty type')
    lie=dict(R2);lie['X']=('C','D','A','B')
    A.equal(deferred(P2,lie)[0],{'A':'Y','B':'Z','C':'X','D':'W'},'recipient deviation')
    cap={i:r[:1] for i,r in P2.items()};A.equal(deferred(cap,R2)[0]['D'],None,'sincere one-name cap')
    cap['D']=('W',);A.equal(deferred(cap,R2)[0]['D'],'W','capped strategic report')
    A.equal(deferred({i:r[:2] for i,r in P2.items()},R2)[0],deferred(P2,R2)[0],'two-name cap')
    for tail,witness in [('XZY',('C','X')),('YXZ',('B','Z')),('ZXY',('A','X')),('ZYX',('A','Y'))]:
        m=dict(zip('ABC',tail));m['D']='W';A.equal(witness in blocking(P2,R2,m),True,'explicit W2 blocking pair')

    v=((12,8,2),(10,6,5),(4,9,7));all_edges=((True,)*3,)*3
    rows=allocations(v);A.equal(len(rows),34,'all partial assignments')
    best=max(z for _,z in rows);A.equal(best,F(26),'assignment max')
    A.equal([m for m,z in rows if z==best],[(0,2,1)],'unique full optimum')
    A.equal(certificate(v,all_edges,(7,5,7),(5,2,0),(0,2,1)),(True,F(26)),'baseline price certificate')
    full={m:z for m,z in rows if None not in m}
    A.equal(tuple(full[m] for m in permutations(range(3))),(25,26,25,17,21,12),'six complete assignment values')
    restricted=((True,True,True),(True,True,False),(True,True,True));rr=allocations(v,restricted)
    A.equal(len(rr),27,'all forbidden-edge partial assignments')
    val=max(z for _,z in rr);A.equal(val,F(25),'forbidden-edge optimum')
    A.equal({m for m,z in rr if z==val},{(0,1,2),(1,0,2)},'all restricted optima')
    for m in [(0,1,2),(1,0,2)]:A.equal(certificate(v,restricted,(6,4,7),(6,2,0),m),(True,F(25)),'restricted price certificate')
    A.equal(certificate(v,all_edges,(6,4,7),(6,2,0),(0,1,2))[0],False,'certificate fails when removed edge restored')
    A.equal(certificate(((0,),),((True,),),(0,),(0,),(None,)),(True,F(0)),'zero unassigned certificate')
    A.equal(certificate(((-2,),),((True,),),(0,),(0,),(None,)),(True,F(0)),'negative value may be left unsold')
    A.equal(certificate(((1,),),((True,),),(1,),(1,),(None,))[0],False,'unused positive terms prevent attainment')
    A.equal(sum((15,20,18,5,2,0)),60,'owned cash conservation')
    A.equal(tuple(row.index(max(row)) for row in v),(0,0,1),'zero-price excess demand')
    anchor('assignment-value',best);anchor('assignment-restricted',val);anchor('assignment-cash',60)

    G=((0,1,0),(1,0,1),(0,1,0));base=(1,1,1)
    B=tuple(tuple(F(g,4) for g in r) for r in G)
    points,sing=equilibrium_faces(base,B);x=(F(10,7),F(12,7),F(10,7))
    A.equal((points,sing),((x,),()),'all complement active patterns')
    u=payoffs(base,B,x);A.equal(u,(F(50,49),F(72,49),F(50,49)),'Nash utility by primitive payoff')
    anchor('complement-ne',x);anchor('complement-welfare',sum(u))
    Q=tuple(tuple(F(i==j)-F(G[i][j],2) for j in range(3)) for i in range(3))
    target=solve(Q,base);A.equal(target,(F(3),F(4),F(3)),'planner linear system')
    # Independently expand the printed weighted-square representation.
    L=((F(1),F(-1,2),F(0)),(F(0),F(-1,2),F(1)),(F(0),F(1),F(0)))
    weights=(F(1),F(1),F(1,2))
    expansion=tuple(tuple(sum(weights[k]*L[k][i]*L[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    A.equal(expansion,Q,'global square-completion coefficient identity')
    A.equal(solve(L,(0,0,0)),(F(0),)*3,'sum of squares vanishes only at zero')
    gross=payoffs(base,B,target);A.equal(gross,(F(3,2),F(2),F(3,2)),'planner gross utilities')
    A.equal(sum(gross)-sum(u),F(73,49),'welfare gap')
    anchor('planner-actions',target);anchor('planner-welfare',sum(gross))
    sub,fee,cash=funded_effort(target);A.equal(sub,(F(3),F(6),F(3)),'actual subsidy payments')
    A.equal(fee,(F(9,2),F(3),F(9,2)),'actual own-independent fees')
    A.equal(cash,(F(17,2),F(13),F(17,2)),'funded cash ledger')
    net=tuple(gross[i]+cash[i]-10 for i in range(3));A.equal(net,(F(0),F(5),F(0)),'net incidence')
    A.equal(net[0]<u[0] and net[2]<u[2],True,'endpoint losses')
    for profile in product((0,4),repeat=3):
        ss,ff,cc=funded_effort(profile)
        A.equal(sum(ss),sum(ff),'every-vertex linear budget identity')
        A.equal(all(0<=z<=m for z,m in zip(ff,(5,4,5))),True,'cash charge bounds')
        A.equal(sum(cc),F(30),'cash conserved away from equilibrium')
    augmented=(F(2),F(5,2),F(2))
    A.equal(equilibrium_faces(augmented,B,4)[0],(target,),'all funded clipped active patterns')
    anchor('funded-charges',fee);anchor('funded-cash',cash);anchor('funded-utilities',net)
    for beta,expected in [(F(3,5),(F(40,7),F(55,7),F(40,7))),(F(3,4),None)]:
        BB=tuple(tuple(beta*g for g in row) for row in G)
        got,deg=equilibrium_faces(base,BB)
        A.equal(got,() if expected is None else (expected,),'global feedback intervention')
        A.equal(deg,(),'nonsingular intervention faces')
        linear=solve(tuple(tuple(F(i==j)-BB[i][j] for j in range(3)) for i in range(3)),base)
        if beta==F(3,5):anchor('beta-three-fifths',linear)
        else:
            A.equal(linear,(F(-14),F(-20),F(-14)),'formal negative inverse is infeasible')
            anchor('beta-three-quarters-formal',linear)
            A.equal(equilibrium_faces(base,BB,2)[0],((F(2),)*3,),'unique capped equilibrium')
    anchor('cap-two',(2,2,2))
    for gamma in (F(0),F(1,2),F(1),F(2)):
        BB=((F(0),-gamma),(-gamma,F(0)));pts,deg=equilibrium_faces((1,1),BB)
        if gamma<1:A.equal(pts,((1/(1+gamma),)*2,),'weak substitute unique NE')
        elif gamma>1:A.equal(set(pts),{(F(1),F(0)),(F(0),F(1)),(1/(1+gamma),)*2},'strong substitute all NE')
        else:
            A.equal(pts,((F(0),F(1)),(F(1),F(0))),'gamma1 nonsingular endpoint faces')
            A.equal(deg,((1,1),),'gamma1 singular interior face retained')
            # For x=(z,1-z), both response equations hold as polynomial identities.
            origin=(F(0),F(1));direction=(F(1),F(-1))
            for i in range(2):
                A.equal(origin[i]+origin[1-i],F(1),'continuum constant coefficient')
                A.equal(direction[i]+direction[1-i],F(0),'continuum linear coefficient')
            A.equal(tuple(origin[i]+direction[i] for i in range(2)),(F(1),F(0)),'continuum endpoint bounds')
        if gamma==F(1,2):
            xx=pts[0];anchor('substitute-small',xx);A.equal(sum(payoffs((1,1),BB,xx)),F(4,9),'substitute NE welfare')
        if gamma==2:anchor('substitute-interior-welfare',sum(payoffs((1,1),BB,(F(1,3),F(1,3)))))
    anchor('substitute-planner',F(1,2))

    rho=F(3,5);lo=rho-rho*rho;hi=rho+rho*rho/2;path=frozenset({(0,1),(1,2)})
    for cost in (F(0),lo,F(1,2),rho,F(7,10),hi,F(2)):
        values={g:sum(network(g,rho,cost)[0]) for g in GRAPHS}
        expected_stable=set();expected_best=set()
        for g in GRAPHS:
            k=len(g)
            classified=(k==0 and cost>=rho) or (k==2 and lo<=cost<=rho) or (k==3 and cost<=lo)
            if classified:expected_stable.add(g)
            class_welfare=(0,2*rho-2*cost,4*rho+2*rho*rho-4*cost,6*rho-6*cost)[k]
            A.equal(values[g],class_welfare,'each graph welfare from paths')
            if (k==3 and cost<=lo) or (k==2 and lo<=cost<=hi) or (k==0 and cost>=hi):expected_best.add(g)
        A.equal({g for g in GRAPHS if pairwise(g,rho,cost)},expected_stable,'complete pairwise classification including ties')
        best=max(values.values());A.equal({g for g in GRAPHS if values[g]==best},expected_best,'complete efficient classification including ties')
    anchor('network-baseline-welfare',sum(network(path,rho,F(1,2))[0]))
    anchor('network-changed-welfare',sum(network(path,rho,F(7,10))[0]))
    anchor('network-thresholds',(lo,rho,hi))
    t=F(3,20);cost=F(7,10);u,gross,costs,transfers,cash,funded=network(path,rho,cost,t)
    A.equal(u,(F(11,100),F(1,10),F(11,100)),'funded path payoffs')
    A.equal(cash,(F(23,20),F(9,10),F(23,20)),'actual pre-benefit cash close')
    A.equal(sum(costs),F(14,5),'real resource cost not canceled transfer')
    A.equal(sum(cash),F(16,5),'cash after resource costs')
    A.equal({g for g in GRAPHS if pairwise(g,rho,cost,t)},{frozenset(),path},'all contracted stable graphs')
    for g in GRAPHS:
        _,_,_,tt,_,ff=network(g,rho,cost,t)
        A.equal(sum(tt),F(0),'balanced transfers at all graphs');A.equal(ff,True,'prefunded costs at all graphs')
    cut=network(path-{(0,1)},rho,cost,t)[0];add=network(path|{(0,2)},rho,cost,t)[0]
    A.equal(u[1]-cut[1],F(1,20),'center keep incentive');A.equal(u[0]-cut[0],F(11,100),'leaf keep incentive')
    A.equal(add[0]-u[0],F(-23,50),'leaf addition loss')
    A.equal(network({(0,1)},rho,cost,t)[0],(F(-1,4),F(1,20),F(0)),'first designated edge')
    A.equal(sum(network({(0,1)},rho,cost,t)[0]),F(-1,5),'balanced first-edge deficit')
    A.equal(network(path,rho,cost,3)[-1],False,'valid transfer can be financially infeasible')
    anchor('network-funded-payoffs',u);anchor('network-center-margin',u[1]-cut[1]);anchor('network-leaf-addition',add[0]-u[0]);anchor('network-first-link',2*rho-2*cost)
    return anchors,{'complete_unilateral_reports':total_reports,'exhaustive_stable_profile_checks':total_stable_profiles,'graph_cases':8,'assignment_partial_counts':[34,27]}


def domain_checks(audit):
    cases=[
      (lambda:number(True),'bool is not a real input'),(lambda:number('1/2'),'unparsed numeric string'),
      (lambda:number(float('nan')),'nan'),(lambda:number(float('inf')),'infinity'),
      (lambda:number(F(1,10**13)),'reduced denominator cap'),(lambda:number(10**7),'numeric magnitude cap'),
      (lambda:vector([]),'empty vector'),(lambda:vector([1,2],3),'dimension mismatch'),
      (lambda:instance({'A':['X','X']},{'X':['A']}),'duplicate preference'),
      (lambda:instance({'A':['Y']},{'X':['A']}),'unknown preference'),
      (lambda:instance({'A':{'X'}},{'X':['A']}),'unordered report'),
      (lambda:instance({'A':['A']},{'A':['A']}),'overlapping sides'),
      (lambda:instance({str(i):[] for i in range(5)},{}),'matching size bound'),
      (lambda:instance({1:[]},{}),'nonstrings as agents'),
      (lambda:menu({'A':[]},{'X':['A']},'B'),'unknown menu applicant'),
      (lambda:blocking({'A':['X'],'B':['X']},{'X':['A','B']},{'A':'X','B':'X'}),'duplicated seat'),
      (lambda:blocking({'A':[]},{'X':['A']},{'A':'X'}),'unacceptable assignment'),
      (lambda:assignment_problem(((1,2),(3,))),'ragged values'),
      (lambda:assignment_problem(((1,),),((1,),)),'nonboolean eligibility'),
      (lambda:certificate(((1,),),((True,),),(-1,),(0,),(0,)),'negative certificate utility'),
      (lambda:certificate(((1,),),((True,),),(1,),(0,),(True,)),'bool object index'),
      (lambda:certificate(((1,),),((False,),),(1,),(0,),(0,)),'forbidden chosen edge'),
      (lambda:game((1,1),((1,0),(0,0))),'self interaction'),
      (lambda:game((1,1),((0,1),)),'game matrix shape'),
      (lambda:game((1,),((0,),),0),'zero cap'),
      (lambda:best_reply((1,),((0,),),(-1,)),'negative action'),
      (lambda:best_reply((1,),((0,),),(3,),2),'over-cap action'),
      (lambda:funded_effort((0,0,5)),'funding profile outside supported cap'),
      (lambda:network([(0,1),(0,1)],F(3,5),F(1,2)),'duplicate edge'),
      (lambda:network([(0,0)],F(3,5),F(1,2)),'self loop'),
      (lambda:network([(1,0)],F(3,5),F(1,2)),'edge order'),
      (lambda:network([(0,3)],F(3,5),F(1,2)),'unknown vertex'),
      (lambda:network([(False,1)],F(3,5),F(1,2)),'bool endpoint'),
      (lambda:network([],0,0),'zero benefit discount'),(lambda:network([],1,0),'unit benefit discount'),
      (lambda:network([],F(1,2),-1),'negative cost'),(lambda:network([],F(1,2),0,-1),'negative transfer'),
      (lambda:strict_json('{"x":1,"x":2}'),'duplicate JSON'),(lambda:strict_json('{"x":NaN}'),'nonfinite JSON token'),
      (lambda:strict_json('{"x":1e999}'),'JSON float overflow')]
    for call,label in cases:audit.reject(call,label)


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=set();self.calcs={};self.questions={};self.solutions={};self.worked={};self.links=[];self.sources={};self.headings=[]
    def handle_starttag(self,tag,pairs):
        attrs=dict(pairs);need(len(attrs)==len(pairs),'no duplicate HTML attribute')
        need(tag not in {'script','iframe','object','style'},'static manuscript without active embedded code')
        if 'id' in attrs:
            ident=attrs['id'];need(ident.startswith('v13-c11-') and ident not in self.ids,'unique chapter-prefixed ID');self.ids.add(ident)
        if tag=='a':
            href=attrs.get('href','');self.links.append(href)
            if 'data-source' in attrs:
                ident=attrs['data-source'];need(ident in URLS and href==URLS[ident],'exact source URL identity');self.sources[ident]=href
        if tag not in {'br','hr','img','meta','link','input','wbr'}:
            self.stack.append({'tag':tag,'attrs':attrs,'chunks':[]})
    def handle_endtag(self,tag):
        need(bool(self.stack) and self.stack[-1]['tag']==tag,'balanced explicit HTML tags: '+tag)
        node=self.stack.pop();attrs=node['attrs'];text=''.join(node['chunks']).strip();classes=set(attrs.get('class','').split())
        if 'data-calc' in attrs:
            key=attrs['data-calc'];need(key not in self.calcs,'unique numeric anchor');self.calcs[key]=text
        if tag=='li' and any(x['tag']=='ol' and 'exercises' in x['attrs'].get('class','').split() for x in self.stack):
            key=attrs.get('id');need(key is not None and key not in self.questions,'exercise ID');self.questions[key]=text
        if 'data-solution-for' in attrs:
            key=attrs['data-solution-for'];need(key not in self.solutions,'unique solution pairing')
            need(any(x['tag']=='details' and 'solutions' in x['attrs'].get('class','').split() for x in self.stack),'standard grouped solution disclosure')
            self.solutions[key]=text
        if tag=='article' and 'worked' in classes:
            key=attrs.get('id');need(key is not None,'worked ID');self.worked[key]=text
        if tag in {'h2','h3'}:self.headings.append(text)
    def handle_data(self,data):
        for node in self.stack:node['chunks'].append(data)


def normalized(text):return re.sub(r'\s+','',text).replace('−','-')


def check(root=None):
    need(root is None or type(root) is str or isinstance(root,Path),'root path type')
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payloads={name:(root/name).read_bytes() for name in FILES}
    audit=Audit();anchors,counts=numerical(audit);domain_checks(audit)
    doc=Manuscript();doc.feed(payloads[FILES[0]].decode('utf-8'));doc.close()
    audit.equal(doc.stack,[],'all HTML tags closed')
    audit.equal(set(doc.calcs),set(anchors),'complete numeric anchor inventory')
    for name,value in anchors.items():audit.equal(normalized(doc.calcs[name]),normalized(value),'printed numerical result: '+name)
    qids={f'v13-c11-ex{i}' for i in range(1,13)}
    audit.equal(set(doc.questions),qids,'all twelve exact exercises')
    audit.equal(set(doc.solutions),qids,'all twelve paired solutions')
    audit.equal(set(doc.worked),{f'v13-c11-case{i}' for i in range(1,7)},'six literal worked articles')
    audit.equal(all(len(text)>900 for text in doc.worked.values()),True,'substantive worked case bodies')
    audit.equal(all(len(text)>400 for text in doc.solutions.values()),True,'substantive complete answer bodies')
    audit.equal(any('delayed retention' in h.lower() or 'delayed recall' in h.lower() for h in doc.headings),True,'delayed retention heading')
    audit.equal({'v13-c11-teachback-answer','v13-c11-retention-answer'}<=doc.ids,True,'answered teach-back and retention')
    local={h for h in doc.links if not h.startswith('https://')}
    audit.equal(local,ROUTES,'exact flat prerequisite/successor routes')
    audit.equal(set(doc.sources),set(URLS),'all method sources cited')
    for href in local:need(re.fullmatch(r'v\d{2}-c\d{2}\.html',href) is not None,'portable flat chapter link')
    sources=strict_json(payloads[FILES[2]].decode());author=strict_json(payloads[FILES[3]].decode())
    audit.equal(sources['chapter'],'v13-c11','source chapter')
    proposals=sources['proposals'];audit.equal(len(proposals),5,'five scoped source proposals')
    audit.equal({s['id']:s['url'] for s in proposals},URLS,'source IDs and exact URLs')
    audit.equal(all(s.get('inspection',{}).get('actual_inspector')=='ito_author' and s.get('limits') for s in proposals),True,'actual inspector and source limits')
    audit.equal(author['chapter'],'v13-c11','author chapter')
    audit.equal(author['package']['runtime_payloads'],list(FILES),'exact four portable runtime payloads')
    bindings=author['bindings'];audit.equal({b['path'] for b in bindings},set(FILES[:3]),'all three nonself runtime bindings')
    for b in bindings:
        raw=payloads[b['path']];audit.equal((b['bytes'],b['sha256']),(len(raw),sha256(raw).hexdigest()),'runtime byte binding: '+b['path'])
    audit.equal({r['id'] for r in author['exercise_audit']},qids,'all exact prompt/solution audits')
    expected_proofs={'v13-c11-matching','v13-c11-menu-proof','v13-c11-assignment','v13-c11-network-games','v13-c11-substitutes','v13-c11-formation'}
    audit.equal({r['id'] for r in author['proof_audit']},expected_proofs,'complete proof-scope audits')
    # Provenance is deliberately metadata-only: no PDF, seed or preparation is a runtime dependency.
    prov={b['path']:b for b in author['provenance_only']}
    audit.equal(set(prov),{'production/v13-c11-source-preparation.json','production/v13-c11-blueprint-proposal.json'},'separate preparation provenance')
    audit.equal(sources['evidence'],prov['production/v13-c11-source-preparation.json'],'source evidence and author provenance agree')
    audit.equal(author['open_findings'],[],'no unresolved author finding')
    out={'chapter':'v13-c11','status':'passed','comparisons':audit.comparisons,'domain_rejections':audit.rejections,
         'numeric_anchors':len(anchors),'worked_cases':len(doc.worked),'solved_exercises':len(doc.solutions),
         'runtime_payloads':4,'counts':counts,'limits':'Finite arithmetic and reader/binding checks; universal proof review and dependency acceptance remain separate.'}
    json.dumps(out,allow_nan=False)
    return out


if __name__=='__main__':
    need(len(sys.argv)==1,'CLI takes no arguments')
    check()
