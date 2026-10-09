"""Quiet four-file audit of original continuous-time matching examples.

Exact rational witnesses accompany the separately recorded universal proofs.
No primary source, mutable fixture, third-party package or network dependency.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from math import isqrt
from pathlib import Path
import re
import sys

FILES=('content/chapters/v14-c04.html','scripts/check_v14_c04.py',
       'content/reviews/v14-c04-sources.json','content/reviews/v14-c04-author.json')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def scalar(x):
    need(type(x) in (int,F),'exact rational scalar required')
    x=F(x); need(abs(x)<=10**12 and x.denominator<=10**30,'bounded exact scalar')
    return x


def vector(x,n):
    need(type(x) in (tuple,list) and len(x)==n,'vector dimension')
    return tuple(scalar(v) for v in x)


def literal(s):
    need(type(s) is str and len(s)<=1500,'literal size/type')
    s=''.join(s.replace('−','-').split()).split('=',1)[-1]
    def read(t,depth=0):
        need(bool(t) and depth<8,'literal empty/depth')
        if t.startswith('('):
            need(t.endswith(')'),'tuple delimiter'); level=0; start=1; items=[]
            for i in range(1,len(t)-1):
                level+=(t[i]=='(')-(t[i]==')'); need(level>=0,'tuple nesting')
                if t[i]==',' and level==0: items.append(read(t[start:i],depth+1)); start=i+1
            need(level==0,'tuple nesting'); items.append(read(t[start:-1],depth+1))
            need(len(items)<=20,'tuple size'); return tuple(items)
        need(re.fullmatch(r'-?\d+(?:/[1-9]\d*)?',t) is not None,'literal fraction grammar')
        return scalar(F(t))
    return read(s)


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate JSON key'); out[k]=v
        return out
    def bad(s): raise ValueError('nonfinite JSON '+s)
    result=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    json.dumps(result,allow_nan=False)
    return result


def sqrtq(x):
    x=scalar(x); need(x>=0,'nonnegative square root')
    a,b=isqrt(x.numerator),isqrt(x.denominator)
    need(a*a==x.numerator and b*b==x.denominator,'witness requires rational square root')
    return F(a,b)


def params(p):
    A,alpha,eta,r,s,kappa,b,y=vector(p,8)
    need(A>0 and r>0 and s>0 and kappa>0 and y>0 and b>=0,'positive primitive domain')
    need(0<alpha<1 and 0<eta<1,'interior matching/bargaining elasticities')
    return A,alpha,eta,r,s,kappa,b,y


def half_entry(p, x):
    A,alpha,eta,r,s,kappa,b,y=params(p); x=scalar(x)
    need(alpha==F(1,2) and x>=0,'square-root tightness witness domain')
    return kappa*((r+s)*x/A+eta*x*x)-(1-eta)*(y-b)


def equilibrium(p):
    A,alpha,eta,r,s,kappa,b,y=params(p)
    need(alpha==F(1,2),'exact solver is square-root matching specialization')
    if y<=b:
        return {'active':False,'theta':F(0),'u':F(1),'v':F(0),'U':b/r}
    B=kappa*(r+s)/A; C=(1-eta)*(y-b); coefficient=kappa*eta
    x=(-B+sqrtq(B*B+4*coefficient*C))/(2*coefficient)
    theta=x*x; f=A*x; q=A/x
    S=(y-b)/(r+s+eta*f); X=eta*S; J=(1-eta)*S
    U=(b+f*X)/r; E=U+X; w=r*U+(r+s)*X
    u=s/(s+f); v=theta*u; m=f*u
    return dict(active=True,theta=theta,f=f,q=q,S=S,X=X,J=J,U=U,E=E,w=w,u=u,v=v,m=m,x=x)


def eval_rule(p,theta):
    A,alpha,eta,r,s,kappa,b,y=params(p); theta=scalar(theta)
    need(theta>=0 and alpha==F(1,2),'fixed-rule witness domain')
    f=A*sqrtq(theta); D=(y-b+kappa*theta)/(r+s+f)
    return (y-s*D)/r,D


def transition(s,f,u0,z):
    s,f,u0,z=map(scalar,(s,f,u0,z))
    need(s>0 and f>=0 and 0<=u0<=1 and 0<=z<=1,'flow/survival domain')
    stationary=s/(s+f)
    return stationary+(u0-stationary)*z


def bracket(p,tolerance,cap):
    params(p); tolerance=scalar(tolerance)
    need(tolerance>0 and type(cap) is int and cap>0,'positive root tolerance/cap')
    need(p[7]>p[6],'positive active-root regime')
    left,right=F(0),F(1)
    while half_entry(p,right)<0: right*=2
    for n in range(cap):
        if right-left<=tolerance: return left,right,n
        middle=(left+right)/2
        if half_entry(p,middle)<=0: left=middle
        else: right=middle
    return None


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=set(); self.inputs={}; self.results={}; self.worked=[]
        self.exercises=[]; self.answers={}; self.sources={}; self.links=[]; self.text=[]
    def handle_starttag(self,tag,pairs):
        a=dict(pairs); need(len(a)==len(pairs),'duplicate HTML attribute')
        if 'id' in a:
            key=a['id']; need(key not in self.ids and key.startswith('v14-c04-'),'reader ID'); self.ids.add(key)
            if 'worked' in a.get('class','').split(): self.worked.append(key)
            if re.fullmatch(r'v14-c04-e\d+',key): self.exercises.append(key)
        for attr,target in (('data-input',self.inputs),('data-calc',self.results)):
            if attr in a:
                need(a[attr] not in target,'duplicate visible marker'); target[a[attr]]=''
        if 'data-solution-for' in a:
            key=a['data-solution-for']; need(key not in self.answers,'duplicate solution')
            need(any(t=='details' and 'solutions' in b.get('class','').split() for t,b in self.stack),'paired solution disclosure')
            self.answers[key]=''
        if 'data-source' in a:
            need(a['data-source'] not in self.sources,'duplicate source'); self.sources[a['data-source']]=a['href']
        if 'href' in a: self.links.append(a['href'])
        if tag not in ('br','hr','img','input','meta','link'): self.stack.append((tag,a))
    def handle_data(self,text):
        self.text.append(text)
        for _,a in self.stack:
            for attr,target in (('data-input',self.inputs),('data-calc',self.results),('data-solution-for',self.answers)):
                if attr in a: target[a[attr]]+=text
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1][0]==tag,'unbalanced HTML'); self.stack.pop()


def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(base/p).read_bytes() for p in FILES}; comparisons=0; rejections=0
    def eq(a,b,label):
        nonlocal comparisons
        comparisons+=1; need(a==b,label+': '+repr(a)+' != '+repr(b))
    page=Page(); page.feed(raw[FILES[0]].decode()); page.close()
    eq(page.stack,[],'balanced full chapter')
    exercises=[f'v14-c04-e{i}' for i in range(1,11)]
    eq(page.exercises,exercises,'ten ordered prompts'); eq(list(page.answers),exercises,'ten paired complete solutions')
    eq(page.worked,[f'v14-c04-w{i}' for i in range(1,5)],'four substantive worked cases')
    for answer in page.answers.values(): eq(len(answer)>500,True,'substantial solved exercise')
    for label in ('Teach-back benchmark','Retention answers','Ten-point rubric'):
        eq(label in ''.join(page.text),True,'answered teaching/rubric')
    eq(all(link.startswith('https://') or ('/' not in link and '.html' in link) for link in page.links),True,'flat source/local routes')
    q={k:literal(v) for k,v in page.inputs.items()}; out={}
    f,s=q['hazards']; survival=q['survival']
    out['transition-pair']=(f*(1-survival)/(s+f),s*(1-survival)/(s+f))
    out['hazard-u']=s/(s+f)
    eq(out['transition-pair'][1]/sum(out['transition-pair']),out['hazard-u'],'exact interval invariant share')
    eq(transition(s,f,1,survival),1-out['transition-pair'][0],'initial unemployment probability')
    eq(transition(s,f,0,survival),out['transition-pair'][1],'initial employment probability')
    p=q['baseline']; A,alpha,eta,r,s,kappa,b,y=params(p); e=equilibrium(p)
    def original_equations(parameters,result):
        A,alpha,eta,r,s,kappa,b,y=params(parameters)
        eq(half_entry(parameters,result['x']),0,'primitive entry polynomial')
        eq(r*result['U'],b+result['f']*(result['E']-result['U']),'unemployed value')
        eq(r*result['E'],result['w']+s*(result['U']-result['E']),'employed value')
        eq(r*result['J'],y-result['w']-s*result['J'],'firm value')
        eq(kappa,result['q']*result['J'],'zero vacancy value with positive cost')
        eq(result['X'],eta*result['S'],'bargained worker surplus')
        eq(result['w'],eta*y+(1-eta)*b+eta*kappa*result['theta'],'outside-option wage')
        eq(s*(1-result['u']),result['m'],'stationary flow balance')
        eq(result['f'],result['theta']*result['q'],'hazard identities')
        eq(b<result['w']<y,True,'positive bilateral surplus')
    original_equations(p,e)
    trial_q=F(10)
    entry_value=(trial_q*(1-eta)*(y-b)-kappa*(r+s))/(r+s+trial_q*(1-eta))
    eq(entry_value>0,True,'positive-surplus inactive boundary fails entry test')
    out['base-rates']=tuple(e[k] for k in ('theta','f','q'))
    out['base-surplus']=tuple(e[k] for k in ('S','X','J'))
    out['base-values']=tuple(e[k] for k in ('w','U','E'))
    out['base-flows']=tuple(e[k] for k in ('u','v','m'))
    out['base-reserve']=kappa*e['v']/r
    flow=lambda parameters,result:parameters[7]*(1-result['u'])+parameters[6]*result['u']-parameters[5]*result['v']
    out['base-welfare-flow']=flow(p,e)
    out['base-welfare-value']=e['u']*e['U']+(1-e['u'])*(e['E']+e['J'])
    eq(r*out['base-welfare-value'],out['base-welfare-flow'],'consolidated wages/dividends/recruiting')
    eq(r*out['base-reserve'],kappa*e['v'],'owned reserve covers running costs')
    changed=p[:-1]+(q['shock-productivity'],); shock=equilibrium(changed); original_equations(changed,shock)
    out['shock-market']=tuple(shock[k] for k in ('theta','f','q','S','w','U','E','J'))
    out['shock-u']=shock['u']; out['shock-v0']=shock['theta']*e['u']
    half=transition(s,shock['f'],e['u'],survival); drift=s-(s+shock['f'])*half
    out['shock-half']=(half,shock['theta']*half,shock['f']*half,drift)
    out['shock-false-f']=s*(1-half)/half
    eq((s*(1-half)-drift)/half,shock['f'],'nonstationary inversion repair')
    out['shock-reserve']=kappa*shock['theta']*e['u']/r
    out['shock-recruiting-pv']=kappa*shock['theta']*(shock['u']/r+(e['u']-shock['u'])/(r+s+shock['f']))
    eq(out['shock-recruiting-pv']<out['shock-reserve'],True,'sufficient reserve exceeds actual PV cost')
    for z in (F(0),F(1,4),F(1,2),F(1)):
        ut=transition(s,shock['f'],e['u'],z)
        eq(shock['u']<=ut<=e['u'],True,'shock monotone feasible stock')
        eq(kappa*shock['theta']*ut<=r*out['shock-reserve'],True,'funding at each transition witness')
    distorted=p[:2]+(q['low-bargaining'],)+p[3:]; low=equilibrium(distorted); original_equations(distorted,low)
    out['distorted-market']=tuple(low[k] for k in ('theta','f','u','w','S','J'))
    a,D=eval_rule(p,low['theta']); out['distorted-coefficients']=(a,D)
    ap,Dp=eval_rule(p,e['theta']); u0=e['u']
    out['welfare-comparison']=(ap-Dp*u0,a-D*u0,(ap-Dp*u0)-(a-D*u0))
    eq(low['u']<e['u'] and out['welfare-comparison'][2]>0,True,'unemployment/welfare distinction')
    # Exact affine evaluation identity for both constant policies and several states.
    for theta in (e['theta'],low['theta'],F(0),F(4)):
        a,D=eval_rule(p,theta); f=A*sqrtq(theta)
        for u in (F(0),F(1,11),F(1,2),F(1)):
            reward=y*(1-u)+b*u-kappa*theta*u; du=s-(s+f)*u
            eq(r*(a-D*u),reward-D*du,'fixed-rule affine verification identity')
    # Planner pointwise inequality is a global completed square when alpha=1/2.
    # Dp*A*x-kappa*x^2 has loss kappa*(x-xP)^2 from its vertex.
    eq(kappa,(1-alpha)*e['q']*Dp,'planner marginal matching condition')
    for x in (F(0),F(1,2),F(1),F(7,5),F(2),F(10)):
        maximized=Dp*A*e['x']-kappa*e['theta']; actual=Dp*A*x-kappa*x*x
        eq(maximized-actual,kappa*(x-e['x'])**2,'global quadratic planner certificate')
    eq(((y-b)-kappa*(r+s)*e['x']/A)/((y-b)+kappa*e['theta']),alpha,'Hosios inversion')
    derivative=kappa*((r+s)*alpha/e['x']/A+eta)
    ty=(1-eta)/derivative; fy=(1-alpha)*e['f']/e['theta']*ty
    out['baseline-derivatives']=(ty,fy,-s*fy/(s+e['f'])**2,eta+eta*kappa*ty)
    candidate=q['candidate-theta']; residual=half_entry(p,sqrtq(candidate))
    out['root-error']=(residual,abs(residual)/(kappa*eta),abs(candidate-e['theta']))
    eq(out['root-error'][2]<=out['root-error'][1],True,'true tightness error certificate')
    interval=bracket(changed,F(1,1024),20)
    need(interval is not None,'bracket tolerance achieved')
    left,right,n=interval
    eq(left<=shock['x']<=right and right-left<=F(1,1024),True,'exact bracket containment')
    eq(half_entry(changed,left)<=0<=half_entry(changed,right),True,'bracket sign invariant')
    eq(bracket(changed,F(1,1024),1),None,'iteration cap is uncertified')
    # Matching-alpha identification at theta=1 requires no irrational arithmetic.
    for altalpha in (F(1,3),F(1,2),F(2,3)):
        eq(A,F(1),'unit tightness has unit power for every admissible exponent')
        eq(kappa*((r+s)/A+eta)-(1-eta)*(y-b),0,'same entry level under unobserved elasticity')
    for u in (F(1,11),F(1,5),F(1,2)):
        v=(s/A)**2*(1-u)**2/u
        eq(A*sqrtq(u*v),s*(1-u),'stationary Beveridge curve')
    for prod in (F(1,10),b):
        inactive=equilibrium(p[:-1]+(prod,))
        eq(inactive,{'active':False,'theta':F(0),'u':F(1),'v':F(0),'U':b/r},'no-surplus boundary without q0')
    eq(set(out),set(page.results),'every visible calculation reconstructed')
    for key,value in out.items(): eq(literal(page.results[key]),value,'visible '+key)
    sources,review=(strict_json(raw[FILES[i]]) for i in (2,3))
    eq(page.sources,{x['id']:x['url'] for x in sources['sources']},'exact accepted source identity')
    eq(set(review['exercise_audit']),set(exercises),'all exact exercise judgments')
    eq(review['open_findings'],[],'no unresolved author issue')
    eq({x['path'] for x in review['bindings']},set(FILES)-{FILES[3]},'three nonself author bindings')
    for entry in review['bindings']:
        data=raw[entry['path']]; eq((len(data),sha256(data).hexdigest()),(entry['bytes'],entry['sha256']),'frozen payload')
    bad=[lambda:scalar(True),lambda:scalar(float('nan')),lambda:scalar(.5),lambda:literal('1/0'),lambda:literal('True'),lambda:literal('x()'),lambda:literal('(1,,2)'),lambda:sqrtq(-1),lambda:sqrtq(2),lambda:params((1,2)),lambda:params((0,)+p[1:]),lambda:params(p[:1]+(F(1),)+p[2:]),lambda:params(p[:2]+(F(0),)+p[3:]),lambda:params(p[:3]+(F(0),)+p[4:]),lambda:params(p[:4]+(F(0),)+p[5:]),lambda:params(p[:5]+(F(-1),)+p[6:]),lambda:transition(s,-1,0,1),lambda:transition(s,1,2,1),lambda:transition(s,1,0,2),lambda:bracket(p,0,10),lambda:bracket(p,F(1,10),True),lambda:bracket(p[:-1]+(b,),F(1,10),10),lambda:strict_json('{"x":1,"x":2}'),lambda:strict_json('{"x":NaN}')]
    for fn in bad:
        try: fn()
        except (ValueError,TypeError): rejections+=1
        else: raise ValueError('invalid oracle domain accepted')
    eq({p:(base/p).read_bytes() for p in FILES},raw,'all four runtime bytes unchanged')
    return {'chapter':'v14-c04','status':'passed','comparisons':comparisons,'domain_rejections':rejections,'worked_cases':len(page.worked),'solved_exercises':len(page.exercises),'visible_inputs':len(q),'visible_results':len(out),'source_routes':len(page.sources),'runtime_files':4,'scope':'Exact original steady values, matching flows, shock transition, financing, planner certificates and identification witnesses; universal proofs separately audited. No empirical calibration claim.'}


if __name__=='__main__':
    need(len(sys.argv)==1,'silent checker takes no arguments')
    check()
