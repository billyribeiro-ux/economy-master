"""Quiet exact checks for the four-file V13-C09 author chapter.

Original finite constraints, active-set certificates, full two-date wage trees and
public-state deviation values are reconstructed independently of manuscript answers.
Successful check(root=None) and no-argument CLI read four payloads and write nothing.
"""
from __future__ import annotations
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
import json
import math
from pathlib import Path
import sys

FILES=('content/chapters/v13-c09.html','scripts/check_v13_c09.py',
       'content/reviews/v13-c09-sources.json','content/reviews/v13-c09-author.json')
URLS={
 'v05-c09-mit-contracts':'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/0a3d53590f17f81f1561eb7d7922329d_MIT14_124S17_Slide2.pdf',
 'v13-c09-stole-contracts1999':'https://ocw.mit.edu/courses/14-124-microeconomic-theory-iv-spring-2017/be21e9cc762231c50ab42bbf35ead5db_MIT14_124S17_LecNote1_2.pdf',
 'v13-c09-levin-relational2006':'https://web.stanford.edu/~jdlevin/Econ%20286/Relational%20Contracts.pdf'}
ROUTES={'v13-c02.html','v13-c03.html','v13-c07.html','v13-c08.html','v13-c10.html'}


def need(ok,label):
    if not ok:raise ValueError(label)


def number(x):
    need(type(x) in (int,float,F),'real numeric type; bool excluded')
    if type(x) is float:
        need(math.isfinite(x),'finite number');x=F(str(x))
    else:x=F(x)
    need(abs(x)<=10**6 and x.denominator<=10**12,'bounded magnitude and reduced denominator')
    return x


def vector(xs,n=None,limit=8):
    need(type(xs) in (tuple,list) and 1<=len(xs)<=limit,'bounded vector')
    need(n is None or len(xs)==n,'vector dimension')
    return tuple(number(x) for x in xs)


def law(xs,n=None):
    xs=vector(xs,n)
    need(all(x>0 for x in xs) and sum(xs)==1,'strictly positive finite probability law')
    return xs


def model(probabilities,costs):
    need(type(probabilities) in (list,tuple) and 1<=len(probabilities)<=4,'bounded action set')
    p=tuple(law(row) for row in probabilities)
    need(all(len(row)==len(p[0]) for row in p),'common signal set')
    c=vector(costs,len(p),4)
    need(all(x>=0 for x in c),'nonnegative effort costs')
    return p,c


def target_index(a,n):
    need(type(a) is int and 0<=a<n,'target action index');return a


def discount(x):
    x=number(x);need(0<x<1,'strictly discounted infinite horizon');return x


def dot(a,b):return sum(x*y for x,y in zip(a,b))


def fmt(x):
    if type(x) in (list,tuple):return '('+','.join(fmt(y) for y in x)+')'
    x=F(x);return str(x.numerator) if x.denominator==1 else str(x)


def solve(rows,rhs):
    n=len(rhs)
    need(1<=n<=8 and len(rows)==n and all(len(row)==n for row in rows),'square bounded linear system')
    a=[[F(x) for x in row]+[F(y)] for row,y in zip(rows,rhs)]
    for col in range(n):
        pivot=next((r for r in range(col,n) if a[r][col]),None)
        if pivot is None:return None
        a[col],a[pivot]=a[pivot],a[col]
        z=a[col][col];a[col]=[x/z for x in a[col]]
        for r in range(n):
            if r!=col:
                z=a[r][col];a[r]=[x-z*y for x,y in zip(a[r],a[col])]
    return tuple(row[-1] for row in a)


def quadratic_min(weights,rows,bounds):
    """Enumerate small independent active faces, accepting only global certificates."""
    p=vector(weights,limit=4);n=len(p)
    need(all(x>0 for x in p),'positive quadratic weights')
    need(type(rows) in (list,tuple) and 1<=len(rows)<=8,'at most eight constraints')
    rows=tuple(vector(row,n,4) for row in rows);bounds=vector(bounds,len(rows))
    for k in range(min(n,len(rows))+1):
        for active in combinations(range(len(rows)),k):
            a=[rows[i] for i in active]
            gram=[[sum(x*y/q for x,y,q in zip(r,s,p)) for s in a] for r in a]
            multipliers=solve(gram,[2*bounds[i] for i in active]) if k else ()
            if multipliers is None or any(x<0 for x in multipliers):continue
            v=tuple(sum(m*row[j] for m,row in zip(multipliers,a))/(2*p[j]) for j in range(n))
            if any(dot(row,v)<b for row,b in zip(rows,bounds)):continue
            full=tuple(multipliers[active.index(i)] if i in active else F(0) for i in range(len(rows)))
            return dot(p,tuple(x*x for x in v)),v,full
    return None


def static_min(probabilities,costs,target,reservation):
    p,c=model(probabilities,costs);a=target_index(target,len(p));r=number(reservation);n=len(p[0])
    need(n<=4,'quadratic example at most four signals')
    rows=[p[a]]+[tuple(x-y for x,y in zip(p[a],p[j])) for j in range(len(p)) if j!=a]
    rhs=[r+c[a]]+[c[a]-c[j] for j in range(len(p)) if j!=a]
    rows.extend(tuple(F(i==j) for j in range(n)) for i in range(n));rhs.extend([0]*n)
    return quadratic_min(p[a],rows,rhs),rows,rhs


def utilities(probabilities,costs,v):
    p,c=model(probabilities,costs);v=vector(v,len(p[0]))
    return tuple(dot(row,v)-cost for row,cost in zip(p,c))


def wealth_vertices(B):
    B=number(B);need(B>=0,'nonnegative enforceable wealth')
    p=F(4,5);q=F(1,5)
    rows=((1,0),(0,1),(1-p,p),(-(p-q),p-q));rhs=(-B,-B,3,3)
    candidates=[]
    for i,j in combinations(range(4),2):
        v=solve((rows[i],rows[j]),(rhs[i],rhs[j]))
        if v is not None and all(dot(row,v)>=b for row,b in zip(rows,rhs)):
            candidates.append((dot((1-p,p),v),v))
    need(bool(candidates),'nonempty original wealth model')
    best=min(x[0] for x in candidates)
    return best,tuple(sorted(set(v for value,v in candidates if value==best)))


def sufficient(probabilities,labels):
    p,_=model(probabilities,[0]*len(probabilities));n=len(p[0])
    need(type(labels) in (list,tuple) and len(labels)==n and
         all(type(x) is int and 0<=x<8 for x in labels),'bounded integer statistic labels')
    groups=tuple(tuple(i for i,x in enumerate(labels) if x==t) for t in sorted(set(labels)))
    for group in groups:
        conditionals=[tuple(row[i]/sum(row[j] for j in group) for i in group) for row in p]
        if any(q!=conditionals[0] for q in conditionals[1:]):return False
    return True


def condition(probabilities,labels,v):
    need(sufficient(probabilities,labels),'action-sufficient statistic required')
    p,_=model(probabilities,[0]*len(probabilities));v=vector(v,len(p[0]));out=list(v)
    for t in set(labels):
        group=[i for i,x in enumerate(labels) if x==t]
        mean=sum(p[0][i]*v[i] for i in group)/sum(p[0][i] for i in group)
        for i in group:out[i]=mean
    return tuple(out)


def branch_split(z,b):
    z=number(z);b=number(b);need(z>=0 and b>=0,'nonnegative consumption utility and outside option')
    if z<b:return None
    candidates=[b,z]
    if b<=z/2<=z:candidates.append(z/2)
    y=min(candidates,key=lambda y:(z-y)**2+y*y)
    return z-y,y,(z-y)**2+y*y


def two_date_min(target,b):
    a=target_index(target,2);b=number(b);need(b>=0,'nonnegative later outside utility')
    p=((F(2,3),F(1,3)),(F(1,3),F(2,3)));c=(F(1,2),F(0))
    weights=tuple(q for q in p[a] for _ in range(2))
    diff=tuple(p[a][s]-p[1-a][s] for s in range(2) for _ in range(2))
    rows=[weights,diff]+[tuple(F(i==j) for j in range(4)) for i in range(4)]
    rhs=[1+c[a],c[a]-c[1-a],0,0,0,0]
    rows.extend([(0,1,0,0),(0,0,0,1)]);rhs.extend([b,b])
    return quadratic_min(weights,rows,rhs),rows,rhs,weights


def tree_frontiers(exit_floor=None):
    """Two productive dates, binary wage utilities, full private-plan reconstruction.

    This is an exact discrete wage-grid check of the recursion, not an approximation
    certificate for the continuous theorem. H/L laws, costs and discount are explicit.
    """
    if exit_floor is not None:
        exit_floor=number(exit_floor);need(exit_floor>=0,'nonnegative finite exit bound')
    p=((F(2,3),F(1,3)),(F(1,3),F(2,3)));c=(F(1,4),F(0));d=F(1,2);Y=(2,0)
    wage_pairs=list(product((F(0),F(1)),repeat=2))
    single={}
    for w,a in product(wage_pairs,range(2)):
        u=dot(p[a],w)-c[a]
        if any(dot(p[j],w)-c[j]>u for j in range(2)):continue
        if exit_floor is not None and u<exit_floor:continue
        profit=dot(p[a],tuple(y-x*x for y,x in zip(Y,w)))
        single[u]=max(single.get(u,profit),profit)
    recursive={}
    for w,a,promises in product(wage_pairs,range(2),product(single,repeat=2)):
        total=tuple(x+d*z for x,z in zip(w,promises));U=dot(p[a],total)-c[a]
        if any(dot(p[j],total)-c[j]>U for j in range(2)):continue
        P=dot(p[a],tuple(Y[s]-w[s]**2+d*single[promises[s]] for s in range(2)))
        recursive[U]=max(recursive.get(U,P),P)
    direct={};private_plans=0;feasible_trees=0
    for w0,wS,wF in product(wage_pairs,repeat=3):
        branch=(wS,wF)
        private_values=[]
        for first in range(2):
            for tail in product(range(2),repeat=4):
                # Private last actions depend on the worker's own first action and output.
                private_plans+=1
                value=-c[first]
                for s in range(2):
                    a2=tail[2*first+s]
                    value+=p[first][s]*(w0[s]+d*(dot(p[a2],branch[s])-c[a2]))
                private_values.append(value)
        best_private=max(private_values)
        for actions in product(range(2),repeat=3):
            a0,aS,aF=actions;last=(aS,aF)
            cont=tuple(dot(p[last[s]],branch[s])-c[last[s]] for s in range(2))
            if any(dot(p[j],branch[s])-c[j]>cont[s] for s in range(2) for j in range(2)):continue
            if exit_floor is not None and any(x<exit_floor for x in cont):continue
            U=dot(p[a0],tuple(w0[s]+d*cont[s] for s in range(2)))-c[a0]
            if U<best_private:continue
            P=F(0)
            for s,t in product(range(2),repeat=2):
                mass=p[a0][s]*p[last[s]][t]
                P+=mass*(Y[s]-w0[s]**2+d*(Y[t]-branch[s][t]**2))
            feasible_trees+=1;direct[U]=max(direct.get(U,P),P)
    return recursive,direct,private_plans,feasible_trees


def relational_value(who,delta,bonus,policy,failure_trigger=False):
    d=discount(delta);b=number(bonus);need(b>=0,'nonnegative fixed bonus range')
    need(type(failure_trigger) is bool,'transition switch must be boolean')
    need(who in ('worker','firm') and type(who) is str,'actor name')
    if who=='worker':
        need(type(policy) in (list,tuple) and len(policy)==2 and
             all(type(x) is int and x in (0,1) for x in policy),'two binary effort decisions')
    else:
        policy=vector(policy,2);need(all(0<=x<=b for x in policy),'feasible success payments')
    rows=[];reward=[]
    for state in range(2):
        a=policy[state] if who=='worker' else state
        p=F(4,5) if a==0 else F(1,5)
        cost=3 if a==0 else 0
        paid=(b if state==0 else 0) if who=='worker' else policy[state]
        reward.append(p*paid-cost if who=='worker' else p*(15-paid))
        if state==1:q=F(0)
        else:q=(p if paid==b else F(0))+(F(0) if failure_trigger else 1-p)
        rows.append((q,1-q))
    values=solve(tuple(tuple(F(i==j)-d*rows[i][j] for j in range(2)) for i in range(2)),reward)
    need(values is not None,'discounted stochastic value system')
    return values


def unique_pairs(items):
    out={}
    for k,v in items:
        need(k not in out,'duplicate JSON key');out[k]=v
    return out


def reject_constant(x):raise ValueError('nonfinite JSON '+x)


def load_json(path):
    return json.loads(path.read_text(),object_pairs_hook=unique_pairs,parse_constant=reject_constant)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.sources={}
        self.links=[];self.worked=[];self.prompts=[];self.solutions=[];self.anchors={}
        self.exercises=None;self.answers=None;self.capture=None
    def handle_starttag(self,tag,attrs):
        d=dict(attrs);classes=d.get('class','').split()
        if 'id' in d:self.ids.append(d['id'])
        if 'data-source' in d:
            key=d['data-source'];need(key in URLS and d.get('href')==URLS[key],'source exact URL')
            self.sources[key]=d['href']
        if 'href' in d:self.links.append(d['href'])
        if tag=='article' and 'worked' in classes:self.worked.append(d.get('id'))
        if tag=='ol' and 'exercises' in classes:self.exercises=len(self.stack)
        if tag=='details' and 'solutions' in classes:self.answers=len(self.stack)
        if tag=='li' and self.exercises is not None:self.prompts.append(d.get('id'))
        if 'data-solution-for' in d:
            need(self.answers is not None,'solution disclosure');self.solutions.append(d['data-solution-for'])
        if 'data-calc' in d:
            need(self.capture is None and d['data-calc'] not in self.anchors,'unique numeric anchor')
            self.capture=d['data-calc'];self.anchors[self.capture]=''
        if tag not in {'br','hr','img','meta','link','input'}:self.stack.append(tag)
    def handle_endtag(self,tag):
        if tag=='span' and self.capture is not None:self.capture=None
        need(bool(self.stack) and self.stack[-1]==tag,'balanced HTML '+tag);self.stack.pop()
        if tag=='ol' and self.exercises==len(self.stack):self.exercises=None
        if tag=='details' and self.answers==len(self.stack):self.answers=None
    def handle_data(self,data):
        if self.capture is not None:self.anchors[self.capture]+=data


def check(root=None):
    need(root is None or isinstance(root,(str,Path)),'root path type')
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
    paths=tuple(root/name for name in FILES);before=tuple(path.read_bytes() for path in paths)
    counts={'comparisons':0,'rejections':0,'private_plans':0,'feasible_wage_trees':0,'stationary_policies':0}
    def eq(a,b,label):
        counts['comparisons']+=1;need(a==b,label+': '+repr(a)+' != '+repr(b))
    def yes(ok,label):counts['comparisons']+=1;need(ok,label)
    def rejects(call,label):
        try:call()
        except (ValueError,TypeError):counts['rejections']+=1
        else:raise ValueError('invalid domain accepted: '+label)
    def certificate(result,p,rows,rhs,label):
        yes(result is not None,label+' exists');cost,v,m=result
        eq(cost,dot(p,tuple(x*x for x in v)),label+' actual bill')
        yes(all(dot(row,v)>=b for row,b in zip(rows,rhs)),label+' every inequality')
        eq(tuple(2*q*x for q,x in zip(p,v)),
           tuple(sum(z*row[j] for z,row in zip(m,rows)) for j in range(len(p))),label+' gradient')
        yes(all(z>=0 for z in m),label+' nonnegative multipliers')
        eq(tuple(z*(dot(row,v)-b) for z,row,b in zip(m,rows,rhs)),(0,)*len(m),label+' complementarity')
    reader=Reader();reader.feed(before[0].decode());reader.close()
    yes(not reader.stack,'balanced fragment');eq(len(reader.ids),len(set(reader.ids)),'unique IDs')
    eq(reader.worked,['v13-c09-case'+str(i) for i in range(1,7)],'six complete cases')
    prompts=['v13-c09-ex'+str(i) for i in range(1,13)]
    eq(reader.prompts,prompts,'twelve prompts');eq(reader.solutions,prompts,'twelve paired answers')
    eq(reader.sources,URLS,'three scoped references')
    eq({x for x in reader.links if not x.startswith('https://')},ROUTES,'flat prerequisite/successor syntax')
    sources,author=load_json(paths[2]),load_json(paths[3])
    eq({x['id']:x['url'] for x in sources['proposals']},URLS,'exact source proposals')
    for source in sources['proposals']:yes(bool(source['limits']),'source restrictions')
    bindings={x['path']:x for x in author['bindings']}
    eq(set(bindings),set(FILES[:3]),'three nonself runtime bindings')
    for name,raw in zip(FILES[:3],before[:3]):
        eq((bindings[name]['bytes'],bindings[name]['sha256']),(len(raw),sha256(raw).hexdigest()),'bound '+name)
    eq([x['id'] for x in author['exercise_audit']],prompts,'all exact prompts audited')
    eq(author['open_findings'],[],'author finding status')
    anchors={}

    # Wealth: finite halfplane intersections, plus direct objective along all IR-binding spreads.
    for B in (F(0),F(2,5),F(1,2),F(1),F(2)):
        best,vertices=wealth_vertices(B)
        eq(best,max(3,4-B),'global floor/IR bound attained')
        for wf,ws in vertices:
            yes(wf>=-B and ws>=-B,'both wealth floors')
            eq(F(4,5)*ws+F(1,5)*wf,best,'statewise wage bill')
            yes(F(3,5)*(ws-wf)>=3,'global two-action IC')
        if B==2:
            eq(vertices,((F(-2),F(17,4)),(F(-1),F(4))),'all optimal face endpoints')
            for spread in (F(5),F(11,2),F(25,4)):
                wf=3-F(4,5)*spread;ws=3+F(1,5)*spread
                eq(F(4,5)*ws+F(1,5)*wf,3,'constant-cost full face')
                yes(wf>=-2 and ws>=-2 and spread>=5,'complete face feasible')
    anchors['wealth-baseline']=fmt(F(4,5)*15-wealth_vertices(0)[0])
    anchors['wealth-threshold']=fmt(wealth_vertices(0)[0]/F(3,5))
    anchors['wealth-six']=fmt((F(4,5)*6-3,F(1,5)*6))
    anchors['wealth-spreads']='d∈[5,25/4]'
    anchors['wealth-transfer-boundary']=fmt(4-F(3,5)*6)
    anchors['wealth-half-profits']=fmt((F(4,5)*6-wealth_vertices(F(1,2))[0],F(1,5)*6,0))
    for eps in (F(1,10),F(1,100)):
        yes(F(3,5)*(5+eps)>3,'strict H transfer')
        eq(F(4,5)*(5+eps)-4,F(4,5)*eps,'strict selection cost increment')
    eq(3/F(3,5),5,'first-best output threshold')

    # Weighted quadratic active faces derive, rather than assume, the optimum and multipliers.
    p=((F(2,3),F(1,3)),(F(1,3),F(2,3)));c=(F(1,2),F(0))
    result,rows,rhs=static_min(p,c,0,1);certificate(result,p[0],rows,rhs,'risk H')
    cost,v,m=result;eq(v,(2,F(1,2)),'derived utility payments');eq(m[:2],(3,2),'derived dual weights')
    eq(utilities(p,c,v),(1,1),'every baseline action utility')
    anchors['risk-cost']=fmt(cost);anchors['risk-dual']=fmt(m[:2]);anchors['risk-profit']=fmt(12*p[0][0]-cost)
    low,lr,lb=static_min(p,c,1,1);certificate(low,p[1],lr,lb,'risk L')
    eq(low[:2],(1,(1,1)),'derived constant L payment')
    known,kr,kb=static_min((p[0],),(c[0],),0,1);certificate(known,p[0],kr,kb,'verifiable H')
    eq(known[:2],(F(9,4),(F(3,2),F(3,2))),'full insurance')
    eq(cost-known[0],F(1,2),'risk bill increment')
    eq(((cost-low[0])/F(1,3),(known[0]-low[0])/F(1,3)),(F(21,4),F(15,4)),'selection regimes')
    middle_p=p+((F(1,2),F(1,2)),);middle_c=c+(F(1,8),)
    old=utilities(middle_p,middle_c,v);anchors['middle-old-utility']=fmt(old[2]);yes(old[2]>old[0],'missing M violates IC')
    new,nr,nb=static_min(middle_p,middle_c,0,1);certificate(new,p[0],nr,nb,'all-three-action H')
    eq(new[1],(F(9,4),0),'new all-action optimum');eq(new[2][:3],(3,0,6),'active M certificate')
    anchors['middle-new-cost']=fmt(new[0]);us=utilities(middle_p,middle_c,new[1]);anchors['middle-utilities']=fmt((us[0],us[2],us[1]))
    eq(us,(1,F(3,4),1),'all three actual action utilities')

    # Joint law comes from conditional products, with all-action sufficiency and fee accounting.
    joint=tuple(tuple(row[i]*row[j] for i,j in product(range(2),repeat=2)) for row in p)
    eq(joint,((F(4,9),F(2,9),F(2,9),F(1,9)),(F(1,9),F(2,9),F(2,9),F(4,9))),'joint primitive law')
    result,rows,rhs=static_min(joint,c,0,1);certificate(result,joint[0],rows,rhs,'four-state H')
    cost4,v4,m4=result;eq(v4,(F(9,5),F(3,2),F(3,2),F(3,10)),'derived four-state utility')
    eq(m4[:2],(3,F(4,5)),'four-state dual weights');eq(utilities(joint,c,v4),(1,1),'joint IC/IR')
    anchors['signal-cost']=fmt(cost4);anchors['signal-gain']=fmt(cost-cost4)
    ratios=tuple(y/x for x,y in zip(*joint));eq(ratios,(F(1,4),1,1,4),'all likelihood ratios')
    yes(sufficient(joint,(2,1,1,0)),'count sufficient');yes(not sufficient(joint,(1,1,0,0)),'Y alone not sufficient')
    yes(not sufficient(joint,(1,0,1,0)),'Z alone not sufficient')
    eq(condition(joint,(2,1,1,0),v4),v4,'optimal contract uses statistic only')
    ancillary=tuple(tuple(q/2 for q in row for _ in range(2)) for row in p)
    noisy=(F(9,4),F(7,4),F(3,4),F(1,4));averaged=condition(ancillary,(1,1,0,0),noisy)
    eq(averaged,(2,2,F(1,2),F(1,2)),'ancillary conditional utility')
    eq(utilities(ancillary,c,noisy),utilities(ancillary,c,averaged),'preserve all action values')
    waste=dot(ancillary[0],tuple(x*x for x in noisy))-dot(ancillary[0],tuple(x*x for x in averaged))
    anchors['ancillary-waste']=fmt(waste);eq(waste,F(1,16),'strict Jensen variance waste')
    eq(dot(ancillary[0],tuple(x*x for x in noisy)),F(45,16),'reported ancillary bill')
    for fee,expected in ((F(1,4),F(1,20)),(F(1,2),F(-1,5)),(F(3,10),F(0))):
        gain=cost-cost4-fee;eq(gain,expected,'measurement fee alters actual net value')
        if fee==F(1,4):anchors['fee-net-saving']=fmt(gain)
    z_only,zr,zb=static_min(p,c,0,1);eq(z_only[0],cost,'Z-only same likelihood experiment')

    # Global continuous identities and spread signs; finite checks support the printed proof.
    for e in (F(0),F(1,4),F(1,2),F(3,4),F(1)):
        original=F(1,4)+e*e/2-e/2;changed=F(1,4)+e-e*e/2-e/2
        eq(original,F(1,8)+(e-F(1,2))**2/2,'stationary minimum identity')
        eq(changed,F(3,8)-(e-F(1,2))**2/2,'changed global maximum identity')
        if e==F(1,2):anchors['foa-minimum']=fmt(original);anchors['foa-maximum']=fmt(changed)
        for spread in (F(-2),F(0),F(1),F(3)):
            value=spread*(F(1,4)+e*e/2)-e/2
            ends=(spread/4,3*spread/4-F(1,2))
            yes(value<=max(ends),'endpoint global bound across spread signs')

    # Two-date QP solves all four consumption-utility coordinates, not a guessed equal split.
    for b in (F(0),F(1,4),F(3,4)):
        high,hr,hb,weights=two_date_min(0,b);certificate(high,weights,hr,hb,'two-date H '+str(b))
        low,lr,lb,lweights=two_date_min(1,b);certificate(low,lweights,lr,lb,'two-date L '+str(b))
        for s in range(2):
            x,y=high[1][2*s:2*s+2];split=branch_split(x+y,b)
            eq(split,(x,y,x*x+y*y),'independent branch projection')
        if b in (0,F(1,4)):
            eq(high[:2],(F(11,8),(1,1,F(1,4),F(1,4))),'original optimum and nonbinding exit transfer')
            eq(low[0],F(1,2),'L two-date insurance')
            anchors['two-date-cost']=fmt(high[0])
        else:
            eq(high[:2],(F(15,8),(F(9,8),F(9,8),0,F(3,4))),'exit reoptimized four coordinates')
            totals=(sum(high[1][:2]),sum(high[1][2:]));u=dot(p[0],totals)-F(1,2)
            eq(totals,(F(9,4),F(3,4)),'actual branch totals');eq(u,F(5,4),'initial IR slack')
            eq(low[:2],(F(5,8),(F(1,4),F(3,4),F(1,4),F(3,4))),'L constrained smoothing')
            anchors['exit-worker']=fmt(u);anchors['exit-cost']=fmt(high[0])
            anchors['exit-profits']=fmt((8-high[0],4-low[0],0))
    eq(2*F(3,4)**2,F(9,8),'known H two-date insurance')
    eq(F(11,8)-F(9,8),F(1,4),'two-date agency cost')
    for z,b in ((0,0),(F(3,4),F(3,4)),(F(3,2),F(3,4)),(F(9,4),F(3,4))):
        x,y,costb=branch_split(z,b)
        eq(costb,z*z/2 if z>=2*b else (z-b)**2+b*b,'branch piecewise boundary')
        yes(y>=b and x>=0 and x+y==z,'actual dated exit bound')
    eq(branch_split(F(1,2),F(3,4)),None,'valid infeasible promise reported')
    eq((1+0,F(1,4)+F(1,4)),(1,F(1,2)),'credit transfer total resources differ')
    eq((2*1,2*F(1,2)),(2,1),'squared optimized saving utilities')
    for floor in (None,F(1,4)):
        recursive,direct,plans,trees=tree_frontiers(floor)
        eq(recursive,direct,'full finite wage-tree frontier equals promise recursion')
        yes(bool(direct),'nonempty attainable finite promise set')
        counts['private_plans']+=plans;counts['feasible_wage_trees']+=trees

    # Exact two-state linear systems versus every bounded stationary deviation policy.
    for delta,bonus in ((F(1,2),F(5)),(F(3,5),F(6)),(F(2,5),F(5)),
                        (F(3,5),F(7)),(F(3,5),F(4)),(F(2,3),F(7))):
        worker=relational_value('worker',delta,bonus,(0,1))
        firm=relational_value('firm',delta,bonus,(bonus,0))
        workers=[relational_value('worker',delta,bonus,p) for p in product((0,1),repeat=2)]
        firms=[relational_value('firm',delta,bonus,p) for p in product((0,bonus/2,bonus),repeat=2)]
        counts['stationary_policies']+=len(workers)+len(firms)
        effort_ok=all(worker[s]>=v[s] for v in workers for s in range(2))
        pay_ok=all(firm[s]>=v[s] for v in firms for s in range(2))
        eq(effort_ok,F(3,5)*bonus>=3,'full worker policies agree with effort IC')
        margin=delta*(firm[0]-firm[1])-bonus
        eq(pay_ok,margin>=0,'full firm policies agree with ex-post payment IC')
        eq(effort_ok and pay_ok,5<=bonus<=45*delta/(5-delta),'exact declared bonus interval')
        eq(firm[1],3/(1-delta),'credible fallback continuation')
        eq(worker[1],0,'fallback worker value')
        if delta==F(3,5) and bonus==6:
            eq((worker[0]*(1-delta),firm[0]*(1-delta)),(F(9,5),F(36,5)),'cooperative per-period payoffs')
            eq(delta*(firm[0]-firm[1]),F(63,10),'actual lost continuation profit')
            anchors['bonus-upper']=fmt(45*delta/(5-delta));anchors['bonus-margin']=fmt(margin)
            anchors['bonus-payoffs']=fmt((worker[0]*(1-delta),firm[0]*(1-delta)))
    anchors['bonus-patience']=fmt(F(5,1)/(9+F(5,5)))
    anchors['fixed-bonus-patience']=fmt(F(6,1)/(9+F(6,5)))
    anchors['impatient-bonus-upper']=fmt(45*F(2,5)/(5-F(2,5)))
    yes(F(5)>45*F(2,5)/(5-F(2,5)),'impatient class infeasible')
    d=F(3,5);b=F(6)
    changedP=relational_value('firm',d,b,(b,0),True);changedW=relational_value('worker',d,b,(0,1),True)
    eq(changedP,(F(405,26),F(15,2)),'failure-trigger firm system')
    eq(changedW,(F(45,13),0),'failure-trigger worker system')
    gain=F(3,5)*(b+d*(changedW[0]-changedW[1]))-3
    margin=d*(changedP[0]-changedP[1])-b
    eq((gain,margin),(F(24,13),F(-15,13)),'changed effort and payment separately')
    yes(relational_value('firm',d,b,(0,0),True)[0]>changedP[0],'actual profitable underpayment policy')
    anchors['failure-firm-value']=fmt(changedP[0]);anchors['failure-worker-value']=fmt(changedW[0])
    anchors['failure-effort-gain']=fmt(gain);anchors['failure-payment-margin']=fmt(margin).replace('-','−')

    # Reject malformed domains; valid but unprofitable contracts above are still evaluated.
    for bad in (True,'1',None,complex(1,0),float('nan'),float('inf'),10**7,F(1,10**13)):
        rejects(lambda bad=bad:number(bad),'numeric domain')
    for bad in ([],[1,0],[F(1,2),F(1,4)],[-1,2],[1]*9):
        rejects(lambda bad=bad:law(bad),'strict probability law')
    for bad in (0,1,-1,2,True):rejects(lambda bad=bad:discount(bad),'discount domain')
    rejects(lambda:model([],[]),'empty actions')
    rejects(lambda:model([p[0]],[0,1]),'cost dimension')
    rejects(lambda:model([p[0],(1,)],[0,0]),'common signal set')
    rejects(lambda:model([p[0]],[-1]),'negative cost')
    rejects(lambda:static_min(p,c,True,1),'boolean target')
    rejects(lambda:static_min(p,c,2,1),'missing action')
    rejects(lambda:wealth_vertices(-1),'negative wealth')
    rejects(lambda:sufficient(joint,(0,1)),'partition length')
    rejects(lambda:sufficient(joint,(True,1,1,0)),'boolean statistic')
    rejects(lambda:condition(joint,(1,1,0,0),v4),'nonsufficient compression')
    rejects(lambda:condition(joint,(2,1,1,0),(1,2)),'utility dimension')
    rejects(lambda:quadratic_min((0,1),[(1,1)],[1]),'nonpositive quadratic weight')
    rejects(lambda:quadratic_min((1,1),[(1,)],[1]),'constraint dimension')
    rejects(lambda:quadratic_min((1,),[(1,)]*9,[1]*9),'constraint budget')
    rejects(lambda:branch_split(-1,0),'negative branch utility')
    rejects(lambda:branch_split(1,-1),'negative outside option')
    rejects(lambda:two_date_min(2,0),'unknown two-date target')
    rejects(lambda:tree_frontiers(-1),'negative exit bound')
    rejects(lambda:relational_value('worker',d,b,(True,1)),'boolean effort policy')
    rejects(lambda:relational_value('worker',d,b,(0,2)),'unknown effort action')
    rejects(lambda:relational_value('firm',d,b,(b+1,0)),'over-range transfer')
    rejects(lambda:relational_value('firm',d,b,(0,-1)),'negative transfer')
    rejects(lambda:relational_value('firm',d,b,(b,0),1),'nonboolean transition rule')
    rejects(lambda:relational_value('firm',d,-1,(0,0)),'negative bonus class')
    rejects(lambda:check(True),'root type')
    for raw in ('{"a":NaN}','{"a":Infinity}','{"a":1,"a":2}'):
        rejects(lambda raw=raw:json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant),'strict JSON')
    eq(reader.anchors,anchors,'every printed numeric anchor independently reconstructed')
    eq(tuple(path.read_bytes() for path in paths),before,'four runtime payloads unchanged')
    result={'chapter':'v13-c09','status':'passed','worked_cases':6,'solved_exercises':12,
            'numeric_anchors':len(anchors),**counts,'runtime_payloads':list(FILES),'writes':0,
            'scope':'Exact finite constraints, wage trees, public-state policies and bindings; general proofs audited separately.'}
    json.dumps(result,allow_nan=False)
    return result


if __name__=='__main__':
    need(len(sys.argv)==1,'CLI accepts no arguments and writes nothing')
    check()
