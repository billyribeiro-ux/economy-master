"""C11 original quantitative benchmarks; quiet four-file checker."""
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import sqrt,log,isfinite,isqrt
from pathlib import Path
import re
import sys

FILES=('production/v14-c11-working.html','production/check_v14_c11_working.py','production/v14-c11-sources-working.json','production/v14-c11-author-review-working.json')

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
            guard(a['id'] not in self.ids and a['id'].startswith('v14-c11-'),'duplicate/out-of-chapter ID'); self.ids.add(a['id'])
            if 'worked' in a.get('class','').split(): self.worked.append(a['id'])
            if re.fullmatch('v14-c11-e[0-9]+',a['id']): self.exercises.append(a['id'])
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

def rat(x):
    guard(type(x) in (int,Q),'exact input'); return Q(x)

def unit(x,closed=False):
    x=rat(x); guard(0<=x<=1 if closed else 0<x<1,'probability domain'); return x

def qsqrt(x):
    x=rat(x); guard(x>=0,'square root domain');a,b=isqrt(x.numerator),isqrt(x.denominator)
    guard(a*a==x.numerator and b*b==x.denominator,'exact square root');return Q(a,b)

def inverse(m):
    guard(len(m)==2 and all(len(x)==2 for x in m),'two-square matrix')
    a,b=m[0];c,d=m[1];a,b,c,d=map(rat,(a,b,c,d));det=a*d-b*c
    guard(det!=0,'singular');return ((d/det,-b/det),(-c/det,a/det))

def mv(m,v):
    guard(len(m)==2 and all(len(x)==2 for x in m) and len(v)==2,'matrix-vector dimensions')
    return tuple(sum(x*y for x,y in zip(row,v)) for row in m)

def growth(alpha,beta,A,k):
    a,b=unit(alpha),unit(beta);A,k=rat(A),rat(k);guard(A>0 and k>0,'positive growth resources')
    s=a*b;bar=float(s*A)**(1/float(1-a));B=a/(1-a*b);H=(log(float((1-s)*A))+float(b*B)*log(float(s*A)))/float(1-b)
    return s,bar,B,H,float(s*A)*float(k)**float(a)

def taylor(alpha,h,d):
    a=unit(alpha);h,d=rat(h),rat(d);guard(0<d<1 and abs(h)<=d,'Taylor compact neighborhood')
    first=1+a*h;second=first+a*(a-1)*h*h/2
    bound=float(a*(1-a)*(2-a)*abs(h)**3/6)/float(1-d)**float(3-a)
    return first,second,bound

def economy(beta,low,high,p,q,grid=False):
    b=unit(beta);lo,hi=rat(low),rat(high);p,q=unit(p,True),unit(q,True)
    guard(hi>=lo>4,'strictly feasible resource domain')
    P=((1-p,p),(q,1-q));expected=mv(P,(lo,hi))
    actions=tuple((4 if -3+b*e>0 else 1) if grid else min(Q(4),max(Q(1),(b*e/2)**2)) for e in expected)
    d=tuple(-a+b*e*qsqrt(a) for a,e in zip(actions,expected))
    inv=inverse(((1-b*P[0][0],-b*P[0][1]),(-b*P[1][0],1-b*P[1][1])))
    H=mv(inv,d);values=tuple(A*k+H[z] for z,A in enumerate((lo,hi)) for k in (1,2))
    return dict(P=P,e=expected,a=actions,d=d,H=H,V=values,inv=inv)

def panel(counts):
    guard(isinstance(counts,tuple) and len(counts)==4,'counts shape')
    n,m,h,j=map(rat,counts);guard(all(x.denominator==1 for x in (n,m,h,j)),'integer counts')
    guard(n>0 and h>0 and 0<=m<=n and 0<=j<=h,'observed panel rows')
    return (m/n,j/h),(sqrt(float(m/n*(1-m/n)/n)),sqrt(float(j/h*(1-j/h)/h)))

def stationary(p,q):
    p,q=unit(p),unit(q);mu=p/(p+q);rho=1-p-q;var=mu*(1-mu);return mu,rho,var,rho*var

def moment_inverse(mu,rho):
    mu=unit(mu);rho=rat(rho);p,q=mu*(1-rho),(1-mu)*(1-rho)
    unit(p);unit(q);return p,q

def scores(counts,probs):
    panel(counts);guard(len(probs)==2,'two forecasts');p,q=map(lambda x:unit(x,True),probs)
    n,m,h,j=counts;total=n+h;score=0.0;brier=Q(0)
    for size,switch,x in ((n,m,p),(h,j,q)):
        if (x==0 and switch>0) or (x==1 and switch<size):score=float('-inf')
        elif isfinite(score):
            if switch:score+=float(switch)*log(float(x))
            if size-switch:score+=float(size-switch)*log(float(1-x))
        brier+=switch*(1-x)**2+(size-switch)*x*x
    return score/float(total),brier/total

def certificate(beta,residual,operator=Q(0),greedy=Q(0)):
    b=unit(beta);r,e,g=map(rat,(residual,operator,greedy));guard(min(r,e,g)>=0,'nonnegative errors')
    return (r+e)/(1-b),(2*(r+e)+g)/(1-b)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};count=0;rejections=0
    def eq(a,b,label):
        nonlocal count
        count+=1;guard(a==b,label+': '+repr(a)+' != '+repr(b))
    def near(a,b,label):
        nonlocal count
        if isinstance(b,tuple):
            guard(isinstance(a,tuple) and len(a)==len(b),'numeric shape')
            for x,y in zip(a,b):near(x,y,label)
        else:
            count+=1;guard(isfinite(float(a)) and isfinite(float(b)) and abs(float(a)-float(b))<2e-10*max(1,abs(float(b))),label)
    doc=Reader();doc.feed(raw[FILES[0]].decode());doc.close();eq(doc.stack,[],'HTML nesting')
    ids=[f'v14-c11-e{i}' for i in range(1,13)];eq(doc.exercises,ids,'twelve exercises');eq(list(doc.answers),ids,'twelve paired complete solutions')
    eq(doc.worked,[f'v14-c11-w{i}' for i in range(1,6)],'five complete worked examples')
    for ans in doc.answers.values():eq(len(ans)>500,True,'substantive solution')
    text=''.join(doc.text)
    for phrase in ('Benchmark answer','Retention answer key','Twenty-point rubric','half-gap','independent','true residual','history policy'):
        eq(phrase in text,True,'instruction/domain coverage')
    q={k:parse(v) for k,v in doc.values['data-input'].items()};out={}
    alpha,beta,A=q['growth-primitives'];h,d=q['growth-local'];s,bar,B,H,exact=growth(alpha,beta,A,1+h);first,second,bound=taylor(alpha,h,d)
    out['growth-constants']=(s,bar,B);out['growth-local-values']=(exact,first,second);out['growth-local-errors']=(float(first)-exact,float(second)-exact);out['growth-second-bound']=bound
    far=q['growth-far'];out['growth-far-values']=(growth(alpha,beta,A,far)[4],1+alpha*(far-1),float(A)*float(far)**float(alpha))
    near(H,2*log(3),'growth value constant');eq(abs(float(second)-exact)<=bound,True,'actual error inside Taylor bound')
    for k in (Q(1,4),Q(3,4),Q(1),Q(5,4),Q(4)):
        kk=float(k);policy=growth(alpha,beta,A,k)[4];c=float(A)*kk**float(alpha)-policy;nextc=float((1-s)*A)*policy**float(alpha)
        near(1/c,float(beta*alpha*A)*policy**float(alpha-1)/nextc,'growth Euler')
        near(float(B)*log(kk)+H,log(c)+float(beta)*(float(B)*log(policy)+H),'growth Bellman')
    b,lo,hi,p,qq=q['global-primitives'];full=economy(b,lo,hi,p,qq);grid=economy(b,lo,hi,p,qq,True)
    out['global-actions']=full['a'];out['global-constants']=full['H'];out['global-values']=full['V'];out['grid-actions']=grid['a'];out['grid-rewards']=grid['d'];out['grid-constants']=grid['H']
    residual=tuple(a-c for a,c in zip(full['d'],grid['d']));loss=tuple(a-c for a,c in zip(full['H'],grid['H']))
    out['grid-residuals']=residual;out['grid-bound']=max(residual)/(1-b);out['grid-losses']=loss
    eq(loss,mv(full['inv'],residual),'exact propagated grid loss');eq(max(loss)<=out['grid-bound'],True,'true-operator certificate')
    for model in (full,grid):
        eq(model['H'],tuple(x+b*y for x,y in zip(model['d'],mv(model['P'],model['H']))),'policy constants')
        for k in (Q(1),Q(25,16),Q(9,4),Q(4)):
            for z,az in enumerate((lo,hi)):
                c=az*qsqrt(k)-model['a'][z];eq(c>0,True,'funded consumption')
                cont=sum(model['P'][z][j]*(aa*qsqrt(model['a'][z])+model['H'][j]) for j,aa in enumerate((lo,hi)))
                eq(az*qsqrt(k)+model['H'][z],c+b*cont,'policy value at off-node capital')
    for z,e in enumerate(full['e']):
        eq(-1+b*e/(2*qsqrt(full['a'][z])),0,'global action FOC')
        for a in (Q(1),Q(25,16),Q(9,4),Q(4)):
            eq(-a+b*e*qsqrt(a)<=full['d'][z],True,'alternative feasible action')
    gap=q['fine-grid-gap'];out['fine-grid-action-bound']=Q(7,64)*gap*gap;out['fine-grid-value-bound']=out['fine-grid-action-bound']/(1-b)
    shift=q['transition-perturbation'];out['primitive-value-bound']=b*(2*hi-1)*(2*shift)/(1-b)**2
    estimates,se=panel(q['training-counts']);out['panel-mle']=estimates;out['panel-se']=se;eq(estimates,(p,qq),'estimated transition primitive match')
    out['policy-derivatives']=(b*b*(lo+(hi-lo)*p)*(hi-lo)/2,-b*b*(hi-(hi-lo)*qq)*(hi-lo)/2)
    dp=q['p-scenario'];new=economy(b,lo,hi,p+dp,qq);out['policy-shift-choice']=new['a'][0];out['policy-shift-change']=new['a'][0]-full['a'][0];out['policy-shift-linear']=out['policy-derivatives'][0]*dp;out['policy-shift-remainder']=out['policy-shift-change']-out['policy-shift-linear']
    nL,nH,eps=q['coverage-design'];guard(nL>0 and nH>0 and eps>0,'coverage domain');out['coverage-failure-bound']=min(Q(1),(1/nL+1/nH)/(4*eps*eps))
    out['stationary-moments']=stationary(p,qq);ap,aq=q['moment-alternative'];out['alternative-moments']=stationary(ap,aq);out['alternative-actions']=economy(b,lo,hi,ap,aq)['a'];out['moment-jacobian-det']=-1/(p+qq)
    eq(moment_inverse(*out['stationary-moments'][:2]),(p,qq),'identified inverse');eq(out['stationary-moments'][0],out['alternative-moments'][0],'underidentified stationary mean')
    for label,counts in (('training',q['training-counts']),('validation',q['validation-counts'])):
        pair=[scores(counts,x) for x in ((p,qq),q['validation-comparator'])];out[label+'-log-scores']=tuple(v[0] for v in pair);out[label+'-brier']=tuple(v[1] for v in pair)
    out['e4-bounds']=certificate(b,Q(1,1000),Q(1,500),Q(1,200));out['e5-grid-bounds']=(Q(3,8)*gap/(1-b),Q(7,64)*gap*gap/(1-b));out['e6-tie-advantages']=tuple(-3+b*(hi-(hi-lo)*x) for x in (Q(49,100),Q(51,100),Q(1,2)));out['e9-infeasible-pair']=(Q(4,5)*(1+Q(1,2)),Q(1,5)*(1+Q(1,2)))
    for pp,qqq in ((Q(1,10),Q(3,5)),(Q(4,5),Q(1,5)),(Q(1,2),Q(1,2))):
        mu,rho,var,cov=stationary(pp,qqq);eq(moment_inverse(mu,rho),(pp,qqq),'alternative moment inverse');eq(mu,(1-mu)*pp+mu*(1-qqq),'stationary mass');eq(cov,rho*var,'autocovariance')
    # Boundaries change the policy or the likelihood; explicit equality is legal.
    eq(economy(Q(1,4),lo,hi,p,qq)['a'],(1,1),'lower capacity boundary');eq(economy(Q(9,10),lo,hi,p,qq)['a'],(4,4),'upper capacity boundary')
    eq(economy(b,lo,hi,Q(1,2),Q(1,2),True)['a'],(1,1),'coarse tie convention')
    eq(panel((Q(5),Q(0),Q(5),Q(5)))[0],(0,1),'closed likelihood boundary')
    eq(scores((Q(5),Q(1),Q(5),Q(2)),(Q(0),Q(1,2)))[0],float('-inf'),'zero-probability forecast failure')
    eq(set(out),set(doc.values['data-calc']),'all visible result markers')
    approximate={'growth-constants','growth-local-values','growth-local-errors','growth-second-bound','growth-far-values','panel-se','training-log-scores','validation-log-scores'}
    for key,value in out.items():(near if key in approximate else eq)(parse(doc.values['data-calc'][key]),value,'displayed '+key)
    sources,author=(strict_json(raw[FILES[i]]) for i in (2,3));eq(doc.sources,{x['id']:x['url'] for x in sources['sources']},'scoped source identity');eq(author['unresolved_findings'],[],'no open author issue');eq(set(author['exact_prompt_solution_audit']),set(ids),'full author audit')
    eq({x['path'] for x in author['payload_bindings']},set(FILES[:3]),'three nonself bindings')
    for item in author['payload_bindings']:
        data=raw[item['path']];eq((len(data),sha256(data).hexdigest()),(item['bytes'],item['sha256']),'frozen payload')
    bad=[lambda:parse('1/0'),lambda:parse('True'),lambda:parse('(1,,2)'),lambda:parse('x()'),lambda:unit(True),lambda:unit(0),lambda:unit(1),lambda:qsqrt(-1),lambda:qsqrt(Q(2)),lambda:inverse(((1,1),(1,1))),lambda:inverse(((1,0),(0,1),(0,0))),lambda:growth(0,b,4,1),lambda:growth(alpha,b,0,1),lambda:growth(alpha,b,4,0),lambda:taylor(alpha,Q(1,2),Q(1,4)),lambda:taylor(alpha,0,1),lambda:economy(b,4,7,p,qq),lambda:economy(b,lo,hi,-1,qq),lambda:panel((0,0,2,1)),lambda:panel((2,3,2,1)),lambda:panel((Q(3,2),1,2,1)),lambda:panel((True,0,2,1)),lambda:stationary(0,qq),lambda:moment_inverse(Q(4,5),Q(-1,2)),lambda:certificate(b,-1),lambda:certificate(1,1),lambda:strict_json('{"x":1,"x":2}'),lambda:strict_json('{"x":NaN}')]
    for fn in bad:
        try:fn()
        except (ValueError,TypeError):rejections+=1
        else:raise ValueError('invalid input accepted')
    eq({p:(root/p).read_bytes() for p in FILES},raw,'runtime bytes unchanged')
    return dict(chapter='v14-c11',component='author',status='passed',comparisons=count,domain_rejections=rejections,worked_cases=5,solved_exercises=12,primitive_markers=len(q),result_markers=len(out),runtime_files=4,scope='Primitive-derived exact rational compact model/policy certificates and panel/moment calculations; local transcendental displays checked to explicit numerical tolerance; universal proofs in manuscript.')

if __name__=='__main__':
    guard(len(sys.argv)==1,'silent checker takes no arguments');check()
