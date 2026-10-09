"""Independent six-file C01 peer: exact two-state algebra and Decimal witnesses.

No author checker imports or execution. The associated record reviews the
universal proofs; numerical tests alone do not establish their quantifiers.
"""
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from pathlib import Path
import re
import sys

FILES = ('production/v14-c01-working.html',
         'production/check_v14_c01_working.py',
         'production/v14-c01-sources-working.json',
         'production/v14-c01-author-review-working.json',
         'production/check_v14_c01_peer_working.py',
         'production/v14-c01-peer-review-working.json')


def guard(ok, reason):
    if not ok:
        raise ValueError(reason)


def parse(s):
    guard(isinstance(s,str) and len(s)<=1200,'literal size/type')
    s=''.join(s.replace('−','-').split()).split('=',1)[-1]
    def read(t,depth=0):
        guard(bool(t) and depth<8,'empty/deep literal')
        if t.startswith('('):
            guard(t.endswith(')'),'tuple closing delimiter')
            start,level,parts=1,0,[]
            for i in range(1,len(t)-1):
                level+=(t[i]=='(')-(t[i]==')')
                guard(level>=0,'tuple nesting')
                if level==0 and t[i]==',': parts.append(read(t[start:i],depth+1)); start=i+1
            guard(level==0,'tuple nesting')
            parts.append(read(t[start:-1],depth+1)); guard(len(parts)<=16,'tuple length')
            return tuple(parts)
        guard(re.fullmatch(r'-?\d+(?:\.\d+|/[1-9]\d*)?',t) is not None,'numeric grammar')
        x=Q(t); guard(abs(x)<=10**9 and x.denominator<=10**20,'number bounds')
        return x
    return read(s)


def strict_json(raw):
    def unique(pairs):
        out={}
        for k,v in pairs:
            guard(k not in out,'duplicate JSON key'); out[k]=v
        return out
    def nonfinite(x): raise ValueError('nonfinite JSON '+x)
    data=json.loads(raw,object_pairs_hook=unique,parse_constant=nonfinite)
    json.dumps(data,allow_nan=False)
    return data


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=set(); self.worked=[]; self.exercises=[]; self.answers={}; self.sources={}
        self.values={k:{} for k in ('data-input','data-calc','data-formula')}; self.text=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); guard(len(a)==len(attrs),'duplicate attribute')
        if 'id' in a:
            guard(a['id'] not in self.ids and a['id'].startswith('v14-c01-'),'duplicate/out-of-chapter ID'); self.ids.add(a['id'])
            if 'worked' in a.get('class','').split(): self.worked.append(a['id'])
            if re.fullmatch('v14-c01-e[0-9]+',a['id']): self.exercises.append(a['id'])
        if 'data-solution-for' in a:
            key=a['data-solution-for']; guard(key not in self.answers,'duplicate solution')
            guard(any(t=='details' and 'solutions' in b.get('class','').split() for t,b in self.stack),'undisclosed solution')
            self.answers[key]=''
        if 'data-source' in a:
            guard(a['data-source'] not in self.sources,'duplicate source'); self.sources[a['data-source']]=a['href']
        for attr,dest in self.values.items():
            if attr in a:
                guard(a[attr] not in dest,'duplicate marker'); dest[a[attr]]=''
        if tag not in ('br','hr','img','input','meta','link'): self.stack.append((tag,a))
    def handle_data(self,text):
        self.text.append(text)
        for _,a in self.stack:
            for attr,dest in self.values.items():
                if attr in a: dest[a[attr]]+=text
            if 'data-solution-for' in a: self.answers[a['data-solution-for']]+=text
    def handle_endtag(self,tag):
        guard(self.stack and self.stack[-1][0]==tag,'unbalanced HTML'); self.stack.pop()


def discount(b):
    guard(type(b) in (int,Q) and 0<b<1,'strict discount domain')
    return Q(b)


def device(rewards,nexts,beta,success=Q(1)):
    beta=discount(beta)
    guard(type(success) in (int,Q) and 0<=success<=1,'repair probability')
    guard(len(rewards)==len(nexts)==2 and all(len(row)==2 for row in rewards+nexts),'two-state/two-action model')
    guard(all(x in (0,1) for row in nexts for x in row),'next-state domain')
    transitions=[[(1-Q(target),Q(target)) for target in row] for row in nexts]
    transitions[0][1]=(1-success,success)
    return rewards,transitions,beta


def returns(model,v):
    r,p,b=model; guard(len(v)==2,'two-state value')
    return tuple(tuple(r[i][j]+b*(p[i][j][0]*v[0]+p[i][j][1]*v[1]) for j in range(2)) for i in range(2))


def T(model,v): return tuple(max(row) for row in returns(model,v))


def evaluate(model,policy):
    guard(len(policy)==2 and all(type(a) is int and a in (0,1) for a in policy),'feasible deterministic policy')
    r,p,b=model
    # Cramer's rule, independently of the author's generic row elimination.
    A=1-b*p[0][policy[0]][0]; B=-b*p[0][policy[0]][1]
    C=-b*p[1][policy[1]][0]; D=1-b*p[1][policy[1]][1]
    y,z=r[0][policy[0]],r[1][policy[1]]; det=A*D-B*C
    guard(det!=0,'policy determinant')
    return (y*D-B*z)/det,(A*z-y*C)/det


def distance(x,y):
    guard(len(x)==len(y) and len(x)>0,'norm dimensions')
    return max(abs(a-b) for a,b in zip(x,y))


def decimal(x):
    x=Q(x); return Decimal(x.numerator)/Decimal(x.denominator)


def growth(A,alpha,beta,k):
    guard(type(A) in (int,Q) and A>0 and type(k) in (int,Q) and k>0,'positive growth primitives')
    guard(type(alpha) in (int,Q) and 0<alpha<1,'Cobb exponent'); beta=discount(beta)
    with localcontext() as ctx:
        ctx.prec=55
        s=alpha*beta; coefficient=alpha/(1-s)
        resources=decimal(A)*(decimal(alpha)*decimal(k).ln()).exp()
        constant=(decimal((1-s)*A).ln()+decimal(beta*coefficient)*decimal(s*A).ln())/decimal(1-beta)
        return s,coefficient,constant+decimal(coefficient)*decimal(k).ln(),decimal(s)*resources,decimal(1-s)*resources


def save_derivative(a,m,beta,R,income,prob):
    guard(type(a) in (int,Q) and type(m) in (int,Q) and 0<=a<m,'saving and wealth domain')
    guard(R>0 and len(income)==len(prob)>0 and min(income)>0 and min(prob)>=0 and sum(prob)==1,'income law/return')
    return -Q(1)/(m-a)+discount(beta)*R*sum(p/(R*a+y) for p,y in zip(prob,income))


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES}; comparisons=0; rejections=0
    def eq(a,b,label):
        nonlocal comparisons
        comparisons+=1; guard(a==b,label+': '+repr(a)+' != '+repr(b))
    def near(a,b,label):
        nonlocal comparisons
        comparisons+=1
        a=a if isinstance(a,Decimal) else decimal(a); b=b if isinstance(b,Decimal) else decimal(b)
        guard(a.is_finite() and b.is_finite() and abs(a-b)<=Decimal('2e-14')*max(1,abs(b)),label)
    doc=Reader(); doc.feed(raw[FILES[0]].decode()); doc.close(); eq(doc.stack,[],'balanced manuscript')
    ids=[f'v14-c01-e{i}' for i in range(1,13)]
    eq(doc.exercises,ids,'twelve prompts'); eq(list(doc.answers),ids,'twelve paired solutions')
    eq(doc.worked,[f'v14-c01-w{i}' for i in range(1,7)],'six worked cases')
    for phrase in ('Teach-back benchmark','Retention answers','Ten-point rubric','PolicyIteration','uncertified: iteration cap reached'):
        eq(phrase in ''.join(doc.text),True,'instructional requirement')
    q={k:parse(v) for k,v in doc.values['data-input'].items()}; out={}
    cash,receipt,cold,warm=q['readiness-amounts']; prob=q['readiness-probability']
    choices=[max([cash]+([cash-cost+receipt] if cash>=cost else [])) for cost in (cold,warm)]
    out.update({'readiness-cold':choices[0],'readiness-warm':choices[1],'readiness-observed':(1-prob)*choices[0]+prob*choices[1],'readiness-blind':cash})
    eq(cold>cash>=warm,True,'readiness financing distinction')
    b=q['device-beta']; model=device(q['device-rewards'],q['device-next'],b)
    policies=list(product(range(2),repeat=2)); values={s:evaluate(model,s) for s in policies}
    for s,v in values.items():
        out['device-policy'+''.join(map(str,s))]=v
        eq(tuple(row[a] for row,a in zip(returns(model,v),s)),v,'each policy equation')
    optimum=tuple(max(v[i] for v in values.values()) for i in range(2))
    eq(T(model,optimum),optimum,'global fixed point')
    improved=tuple(row.index(max(row)) for row in returns(model,values[(0,0)]))
    eq(improved,(1,1),'strict simultaneous policy improvement')
    v=(Q(0),Q(0)); iterates=[v]
    for n in range(1,16):
        v=T(model,v); iterates.append(v)
        if n<=3: out['device-v'+str(n)]=v
        if n>=2:
            eq(v,tuple(x-3*b**(n-2) for x in optimum),'complete VI formula sample')
            eq(distance(T(model,v),v)/(1-b),distance(optimum,v),'exact VI error certificate')
    out['device-residual2']=distance(iterates[3],iterates[2]); out['device-error2']=distance(optimum,iterates[2])
    switch=Q(2,3); out['device-beta-switch']=switch
    out['device-tie-value']=evaluate(device(q['device-rewards'],q['device-next'],switch),(0,0))
    for beta in (Q(1,5),Q(1,2),switch,Q(3,4),Q(4,5)):
        m=device(q['device-rewards'],q['device-next'],beta); vs={s:evaluate(m,s) for s in policies}
        best=tuple(max(v[i] for v in vs.values()) for i in range(2)); rows=returns(m,best)
        eq({s for s,v in vs.items() if v==best},set(policies) if beta==switch else {(0,0) if beta<switch else (1,1)},'all discount-regime policies')
        eq(tuple(max(row)-min(row) for row in rows),(abs(2-3*beta),)*2,'both state strict gaps/ties')
        for s,v in vs.items():
            if v==best:
                eq(tuple(old if row[old]==max(row) else row.index(max(row)) for row,old in zip(rows,s)),s,'retain every optimal tie')
    for p in (Q(0),Q(1,2),switch,q['e3-repair-success'],Q(1)):
        m=device(q['device-rewards'],q['device-next'],b,p); vs={s:evaluate(m,s) for s in policies}
        best=tuple(max(v[i] for v in vs.values()) for i in range(2))
        eq(T(m,best),best,'risky repair fixed point')
        eq({s for s,v in vs.items() if v==best},{(0,1)} if p<switch else ({(0,1),(1,1)} if p==switch else {(1,1)}),'all success-regime policies')
        if p==q['e3-repair-success']:
            out['e3-value']=best; out['e3-gaps']=tuple(row[1]-row[0] for row in returns(m,best))
    tolerance=q['e5-tolerance']; index=next(n for n,v in enumerate(iterates) if distance(T(model,v),v)/(1-b)<=tolerance)
    out['e5-first-index']=index
    for n in (13,14): out['e5-error'+str(n)]=distance(optimum,iterates[n])
    eq(index+1,15,'Bellman calls and returned index')
    for v in ((Q(0),Q(0)),(Q(7),Q(-3)),(Q(2),Q(5))):
        rows=returns(model,v); delta=distance(T(model,v),v)
        eq(distance(v,optimum)<=delta/(1-b),True,'value residual bound')
        for s in policies:
            own=tuple(row[a] for row,a in zip(rows,s)); eta=max(max(row)-row[a] for row,a in zip(rows,s))
            eq(distance(v,values[s])<=distance(own,v)/(1-b),True,'own-policy bound')
            eq(distance(optimum,values[s])<=(2*delta+eta)/(1-b),True,'eta-greedy policy loss')
    error=q['operator-offset']; offset=tuple(x+error/(1-b) for x in optimum)
    out['offset-fixed']=offset; out['offset-residual']=distance(T(model,offset),offset); out['offset-error']=distance(offset,optimum)
    eq(tuple(x+error for x in T(model,offset)),offset,'approximate fixed point')
    out['omitted-true-value']=max(q['omitted-rewards'])/(1-b); out['omitted-true-residual']=max(q['omitted-rewards'])
    A,alpha,beta,k0=q['growth-parameters']; s,coef,value,k1,c0=growth(A,alpha,beta,k0)
    out['growth-share']=s; out['growth-b']=coef; out['growth-first']=(Q(3),Q(5))
    near(k1,out['growth-first'][0],'first investment'); near(c0,out['growth-first'][1],'first consumption')
    eq(coef,alpha*(1+beta*coef),'log value slope identity')
    out['growth-steady']=((s*A)**2,(1-s)*A*(s*A)); out['growth-value16']=value
    with localcontext() as ctx:
        ctx.prec=55
        _,_,vnext,k2,c1=growth(A,alpha,beta,Q(3))
        near(k2,Decimal(3)*Decimal(3).sqrt()/4,'second investment')
        near(c1,Decimal(5)*Decimal(3).sqrt()/4,'second consumption')
        near(1/c0,decimal(beta*A*alpha)/Decimal(3).sqrt()/c1,'growth Euler')
        near(value,c0.ln()+decimal(beta)*vnext,'growth attained Bellman identity')
        # Independent closed log-state recurrence sums candidate utility with an explicit tail.
        qlog=decimal(s*A).ln()/(1-decimal(alpha)); logk=decimal(k0).ln(); total=Decimal(0)
        for t in range(120):
            z=decimal(alpha)**t*logk+(1-decimal(alpha)**t)*qlog
            logc=decimal((1-s)*A).ln()+decimal(alpha)*z
            total+=decimal(beta)**t*logc
        tail=(decimal(beta)**120)*(decimal((1-s)*A).ln()+decimal(alpha)*qlog)/(1-decimal(beta))
        tail+=(decimal(beta*alpha)**120)*decimal(alpha)*(logk-qlog)/(1-decimal(beta*alpha))
        near(total+tail,value,'discounted objective including exact analytic tail')
    sb,R,y,p=(q[k] for k in ('saving-beta','saving-return','saving-incomes','saving-probabilities'))
    m0,m1=q['saving-wealths']; rhs=sb*R*sum(pi/yi for pi,yi in zip(p,y))
    out['saving-corner']=Q(0); out['saving-corner-sides']=(1/m0,rhs); out['saving-threshold']=1/rhs
    eq(save_derivative(0,m0,sb,R,y,p)<0,True,'strict borrowing corner')
    with localcontext() as ctx:
        ctx.prec=55
        saving_root=(Decimal(385).sqrt()-17)/12; out['saving-root-decimal']=saving_root
        near(6*saving_root*saving_root+17*saving_root-4,Decimal(0),'saving polynomial root')
        near(-1/(decimal(m1)-saving_root)+Decimal(1)/4/(saving_root+1)+Decimal(1)/4/(saving_root+4),Decimal(0),'original marginal equation')
        for wealth in (Q(4),Q(6),Q(20)):
            m=decimal(wealth); a=(2*m-25+(4*m*m+20*m+241).sqrt())/12
            near(-1/(m-a)+Decimal(1)/4/(a+1)+Decimal(1)/4/(a+4),Decimal(0),'general saving root')
            eq(0<a<m,True,'root feasible')
    eq(save_derivative(0,out['saving-threshold'],sb,R,y,p),0,'threshold equality remains corner')
    mean=sum(pi*yi for pi,yi in zip(p,y)); out['e9-mean-threshold']=mean/(sb*R)
    eq(save_derivative(0,m1,sb,R,(mean,),(Q(1),))<0,True,'certain mean corner')
    for a in (Q(0),Q(1,3),Q(3)):
        eq(sum(pi/(a+yi) for pi,yi in zip(p,y))>1/(a+mean),True,'strict reciprocal Jensen witness')
    M=q['e8-terminal-resources']; x=max(Q(0),(sb*M-1)/(1+sb)); out['e8-terminal-choice']=(x,M-x); out['e8-terminal-marginal']=1/(M-x)
    for resource in (Q(1),Q(2),Q(5),Q(9)):
        choice=max(Q(0),(sb*resource-1)/(1+sb)); D=-1/(resource-choice)+sb/(1+choice)
        eq((choice==0 and D<=0) or (choice>0 and D==0),True,'terminal constrained sign')
    lb,R,k=q['linear-parameters']; out['linear-bad-value']=Q(0); out['linear-bad-tail']=2*(k-1)
    eq(lb*R,1,'constant Euler consumption')
    for C in (Q(1,2),Q(1),Q(2)):
        capital=k; pv=Q(0)
        for t in range(8):
            nextk=R*capital-C; pv+=C/R**(t+1)
            eq(nextk,C+(k-C)*R**(t+1),'constant path capital')
            eq(pv+nextk/R**(t+1),k,'finite budget telescope')
            eq(lb**t*nextk/C,lb**t+2*(k-C)/C,'shadow-tail decomposition')
            capital=nextk
    for eps in (Q(1,100),Q(1),Q(8)):
        d=min(Q(1,2),eps/4); eq(0<d<1 and 4*d<=eps,True,'open-domain epsilon policy')
    eq(Q(1)/(1-b),Q(4),'unattained value supremum')
    formula_expected={'device-vi':'v_n=(5,8)−3(3/4)^(n−2)(1,1).','saving-root':'(sqrt(385)−17)/12','linear-good-value':'2log(2)','e9-general-root':'a*(m)=[2m−25+sqrt(4m²+20m+241)]/12.'}
    eq(doc.values['data-formula'],formula_expected,'all four reviewed visible formulas')
    eq(set(out),set(doc.values['data-calc']),'every visible result covered')
    for key,result in out.items():
        actual=parse(doc.values['data-calc'][key])
        (near if isinstance(result,Decimal) else eq)(actual,result,'visible '+key)
    source,author,peer=(strict_json(raw[FILES[i]]) for i in (2,3,5))
    eq(doc.sources,{x['id']:x['url'] for x in source['proposals']},'four exact source routes')
    eq('currently absent' in source['resumption_evidence'],True,'honest historical evidence boundary')
    eq(peer['status'],'passed','peer decision'); eq(peer['unresolved_findings'],[],'no open findings')
    eq(set(peer['exact_prompt_solution_audit']),set(ids),'all written solution judgments')
    eq({x['path'] for x in peer['payload_bindings']},set(FILES)-{FILES[5]},'five nonself payloads')
    for record in (author,peer):
        for entry in record['payload_bindings']:
            actual=raw[entry['path']]
            eq((len(actual),sha256(actual).hexdigest()),(entry['bytes'],entry['sha256']),'immutable payload')
    invalid=[lambda:parse('1/0'),lambda:parse('True'),lambda:parse('x()'),lambda:parse('(1,,2)'),lambda:parse('1'*1300),lambda:discount(1),lambda:discount(0),lambda:discount(True),lambda:device(q['device-rewards'],q['device-next'],b,-1),lambda:evaluate(model,(True,0)),lambda:returns(model,(1,)),lambda:growth(0,alpha,beta,k0),lambda:growth(A,1,beta,k0),lambda:growth(A,alpha,beta,0),lambda:save_derivative(-1,m0,sb,R,y,p),lambda:save_derivative(m0,m0,sb,R,y,p),lambda:save_derivative(0,m0,sb,R,y,(1,1)),lambda:strict_json('{"a":1,"a":2}'),lambda:strict_json('{"a":NaN}')]
    for fn in invalid:
        try: fn()
        except (ValueError,TypeError): rejections+=1
        else: raise ValueError('invalid domain accepted')
    eq({p:(root/p).read_bytes() for p in FILES},raw,'all six bytes unchanged')
    return {'chapter':'v14-c01','component':'peer','status':'passed','comparisons':comparisons,'domain_rejections':rejections,'worked_cases':6,'solved_exercises':12,'primitive_markers':len(q),'result_markers':len(out),'formula_markers':4,'runtime_files':6,'author_code_executed':False,'scope':'Independent exact two-state policy/certificate algebra and 55-digit Decimal witnesses; universal proof judgments separately recorded; historical source artifacts unavailable.'}


if __name__=='__main__':
    guard(len(sys.argv)==1,'silent peer checker takes no arguments')
    check()
