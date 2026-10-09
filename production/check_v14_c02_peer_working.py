"""Independent read-only C02 peer reconstruction, exactly six runtime payloads.

No author checker is imported or executed. The local solution uses eigenvectors
of the capital/consumption transition system; moments use distributed-shock sums.
Universal optimality and source judgments live in the separately bound review.
"""
import ast
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import exp, isfinite, log, sqrt
from pathlib import Path

FILES = ('production/v14-c02-working.html',
         'production/check_v14_c02_working.py',
         'production/v14-c02-sources-working.json',
         'production/v14-c02-author-review-working.json',
         'production/check_v14_c02_peer_working.py',
         'production/v14-c02-peer-review-working.json')


def real(x):
    if isinstance(x,bool) or not isinstance(x,(int,float,Q)) or not isfinite(float(x)):
        raise ValueError('finite numeric scalar required')
    return float(x)


def primitives(alpha,beta,chi):
    alpha,beta,chi = map(real,(alpha,beta,chi))
    if not 0 < alpha < 1 or not 0 < beta < 1 or chi <= 0:
        raise ValueError('interior discounted log-Cobb preference domain')
    return alpha,beta,chi


def allocation(alpha,beta,chi,capital,technology,ceiling=1):
    a,b,h = primitives(alpha,beta,chi)
    k,z,ceiling = map(real,(capital,technology,ceiling))
    if k <= 0 or z <= 0 or not 0 < ceiling <= 1:
        raise ValueError('positive state and hours ceiling required')
    # Solve the two static first-order equations; s follows from Euler coefficient.
    B = a/(1-a*b)
    s = b*B/(1+b*B)
    hours = min(ceiling,(1+b*B)*(1-a)/((1+b*B)*(1-a)+h))
    y = z*k**a*hours**(1-a)
    return {'k':k,'n':hours,'y':y,'c':(1-s)*y,'kp':s*y,
            'w':(1-a)*y/hours,'r':a*y/k,'s':s,'B':B}


def equilibrium(alpha,beta,chi,ceiling=1):
    a,b,h = primitives(alpha,beta,chi)
    f = allocation(a,b,h,1,1,ceiling)
    # k/n = s^(1/(1-alpha)) from k=s*k^alpha*n^(1-alpha).
    k = f['n']*exp(log(f['s'])/(1-a))
    return allocation(a,b,h,k,1,ceiling)


def branch(alpha,beta,delta,hours,persistence):
    a,b,_ = primitives(alpha,beta,1)
    d,n,rho = map(real,(delta,hours,persistence))
    if not 0 < d <= 1 or not 0 < n < 1 or not abs(rho) < 1:
        raise ValueError('interior steady and stable exogenous state required')
    rent = 1/b-1+d
    k = n*exp(log(a/rent)/(1-a))
    y = k**a*n**(1-a)
    c = y-d*k
    h = (1-a)*y*(1-n)/(n*c)
    # Eliminate labor: output = E*x + F*z - G*chat.
    dn = 1/(1-n)-(1-a)
    E = a+(1-a)*a/dn
    F = 1+(1-a)/dn
    G = (1-a)/dn
    u = 1-d+(y/k)*E
    v = (y/k)*F
    w = c/k+(y/k)*G
    denominator = 1+b*rent*G
    # Conditional transition [x', E chat'] = M [x,chat] + force*z.
    t = b*rent*(E-1)
    M = ((u,-w),(t*u/denominator,(1-t*w)/denominator))
    force = (v,(t*v+b*rent*F*rho)/denominator)
    trace = M[0][0]+M[1][1]
    det = M[0][0]*M[1][1]-M[0][1]*M[1][0]
    disc = trace*trace-4*det
    if disc < 0:
        raise ValueError('nonreal local eigenvalues')
    eigen = ((trace-sqrt(disc))/2,(trace+sqrt(disc))/2)
    stable = [x for x in eigen if abs(x) < 1]
    if len(stable) != 1:
        raise ValueError('unique stable eigenvector required')
    K = stable[0]
    p = (u-K)/w
    qden = rho-p*w-M[1][1]
    if abs(qden) < 1e-12:
        raise ValueError('singular response to exogenous innovation')
    q = (force[1]-p*v)/qden
    L = v-w*q
    return {'a':a,'b':b,'d':d,'n':n,'rho':rho,'r':rent,'k':k,'y':y,'c':c,
            'chi':h,'dn':dn,'p':p,'q':q,'K':K,'L':L,'M':M,'force':force,
            'p_roots':tuple(sorted((u-z)/w for z in eigen)),
            'K_by_p':tuple(reversed(eigen))}


def levels(t,x,z):
    x,z = map(real,(x,z))
    hc = t['p']*x+t['q']*z
    hn = (z+t['a']*x-hc)/t['dn']
    xp = t['K']*x+t['L']*z
    n = t['n']*exp(hn)
    if not 0 < n < 1:
        raise ValueError('hours violate positive-leisure domain')
    k,c,kp = t['k']*exp(x),t['c']*exp(hc),t['k']*exp(xp)
    y = exp(z)*k**t['a']*n**(1-t['a'])
    return {'k':k,'c':c,'n':n,'kp':kp,'y':y,'w':(1-t['a'])*y/n,
            'R':t['a']*y/k+1-t['d'],'hc':hc,'hn':hn,'xp':xp}


def nonlinear(t,amplitude):
    amplitude = real(amplitude)
    if amplitude <= 0:
        raise ValueError('positive two-state amplitude required')
    now = levels(t,0,amplitude)
    expectation = 0
    for sign,prob in ((1,(1+t['rho'])/2),(-1,(1-t['rho'])/2)):
        nxt = levels(t,now['xp'],sign*amplitude)
        expectation += prob*nxt['R']/nxt['c']
    return (now['c']+now['kp']-now['y']-(1-t['d'])*now['k'],
            log(t['chi']*now['c']/((1-now['n'])*now['w'])),
            1-t['b']*now['c']*expectation)


def stationary(alpha,rho,h,terms=90):
    a,rho,h = map(real,(alpha,rho,h))
    if not 0 < a < 1 or not abs(rho) < 1 or h <= 0:
        raise ValueError('bounded stable stationary domain')
    if isinstance(terms,bool) or not isinstance(terms,int) or terms < 1:
        raise ValueError('positive integer truncation')
    # Cov(a_t,a_{t-j})=h^2*rho^j. x_t contains lagged shocks.
    v = h*h
    C = sum(a**j*v*rho**(j+1) for j in range(terms))
    X = sum(a**(i+j)*v*rho**abs(i-j) for i in range(terms) for j in range(terms))
    # y_t=x_(t+1); covariance with its next observation shifts the shock lag by one.
    lag = sum(a**(i+j)*v*rho**abs(1+i-j) for i in range(terms) for j in range(terms))
    return v,C,X,sqrt(X),lag/X


def identify_utilization(alpha,u,change):
    a,u,change = map(real,(alpha,u,change))
    if not 0 < a < 1 or not 0 < u <= 1:
        raise ValueError('input utilization domain')
    result = u*exp(change/a)
    if not 0 < result <= 1:
        raise ValueError('utilization explanation infeasible')
    return result


def read_numeric(text):
    def node(x):
        if isinstance(x,ast.Constant):
            if isinstance(x.value,bool) or not isinstance(x.value,(int,float)):
                raise ValueError('numeric marker constant required')
            return Q(str(x.value))
        if isinstance(x,(ast.Tuple,ast.List)):
            return tuple(node(y) for y in x.elts)
        if isinstance(x,ast.UnaryOp) and isinstance(x.op,(ast.USub,ast.UAdd)):
            return (-1 if isinstance(x.op,ast.USub) else 1)*node(x.operand)
        if isinstance(x,ast.BinOp) and isinstance(x.op,ast.Div):
            return node(x.left)/node(x.right)
        raise ValueError('unsafe marker expression')
    return node(ast.parse(text.strip(),mode='eval').body)


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.inputs={};self.results={};self.worked=[]
        self.questions=[];self.answers=[];self.links=[];self.source_routes={};self.body=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.worked.append(a.get('id'))
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack):
            self.questions.append(a.get('id'))
        if 'data-solution-for' in a:
            if not any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack):
                raise ValueError('undisclosed solution')
            self.answers.append(a['data-solution-for'])
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.source_routes[a['data-source']]=a.get('href')
        for attribute,destination in (('data-input',self.inputs),('data-calc',self.results)):
            if attribute in a:
                if a[attribute] in destination:raise ValueError('duplicate marker')
                destination[a[attribute]]=''
        if tag not in ('br','hr','img','meta','input','link'):self.stack.append((tag,a))
    def handle_endtag(self,tag):
        if not self.stack or self.stack[-1][0]!=tag:raise ValueError('HTML nesting mismatch')
        self.stack.pop()
    def handle_data(self,text):
        self.body.append(text)
        for _,a in self.stack:
            if 'data-input' in a:self.inputs[a['data-input']]+=text
            if 'data-calc' in a:self.results[a['data-calc']]+=text


def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(base/p).read_bytes() for p in FILES}
    total=0;rejected=0
    def guard(condition,message):
        nonlocal total
        total+=1
        if not condition:raise ValueError(message)
    def eq(a,b,message):guard(a==b,message)
    def near(a,b,message,tolerance=6e-11):
        if isinstance(b,(tuple,list)):
            guard(isinstance(a,(tuple,list)) and len(a)==len(b),message+' shape')
            for x,y in zip(a,b):near(x,y,message,tolerance)
        else:
            guard(isfinite(float(a)) and isfinite(float(b)) and abs(float(a)-float(b))<=tolerance*max(1,abs(float(b))),message)
    doc=Chapter();doc.feed(payload[FILES[0]].decode())
    guard(not doc.stack,'unclosed chapter fragment')
    eq(len(doc.ids),len(set(doc.ids)),'unique IDs')
    guard(all(i.startswith('v14-c02-') for i in doc.ids),'prefixed IDs')
    exercises=['v14-c02-e'+str(i) for i in range(1,13)]
    eq(doc.questions,exercises,'exact prompts');eq(doc.answers,exercises,'exact disclosed answers')
    eq(doc.worked,['v14-c02-w'+str(i) for i in range(1,6)],'five original cases')
    guard(all(h.startswith('https://') or ('/' not in h and '.html' in h) for h in doc.links),'flat source and reader links')
    body=''.join(doc.body)
    for phrase in ('Benchmark answer.','Answer key.','one week','ten-point','planned successor','Every fixed-length recent shock block'):
        guard(phrase in body,'instruction or review repair: '+phrase)
    sources=json.loads(payload[FILES[2]])
    eq(doc.source_routes,{s['id']:s['url'] for s in sources['sources']},'scoped source routes')
    ins={k:read_numeric(v) for k,v in doc.inputs.items()}
    out={k:read_numeric(v) for k,v in doc.results.items()}
    eq(set(ins),{'exact-alpha','exact-beta','exact-chi','impact-z','shock-h','shock-stay','local-parameters','target-ratios'},'all eight primitives')
    alpha,beta,chi=(ins[z] for z in ('exact-alpha','exact-beta','exact-chi'))
    a,b,h=map(float,(alpha,beta,chi))
    eq((alpha,beta,chi),(Q(1,3),Q(3,4),Q(2)),'declared exact-case calibration')
    st=equilibrium(a,b,h)
    impact=allocation(a,b,h,st['k'],ins['impact-z'])
    rho=2*ins['shock-stay']-1
    amp=ins['shock-h']
    loc=branch(*ins['local-parameters'])
    im=levels(loc,0,.01)
    pop=stationary(alpha,rho,amp)
    iid=stationary(alpha,0,amp)
    new=equilibrium(.5,.8,3)
    lower=allocation(a,b,h,st['k'],.8)
    cap=equilibrium(a,b,h,.25)
    # Calibrate h by rescaling the independently summed variance, not a fitted formula.
    fit=lambda persistence,sigma:float(sigma)/stationary(alpha,persistence,1)[3]
    expected={
        'exact-policy':(st['s'],1-st['s'],st['n']),
        'exact-steady':(st['k'],st['y'],st['c']),
        'exact-prices':(st['r'],st['w']),
        'exact-impact':(impact['y'],impact['c'],impact['kp']),
        'shock-rho':rho,'value-shock':1/((1-alpha*beta)*(1-beta*rho)),
        'shock-wage':impact['w'],'shock-rental':impact['r'],
        'shock-incomes':(impact['w']*impact['n'],impact['r']*impact['k']),
        'partial-labor':1-h*st['c']/impact['w'],
        'local-steady':tuple(loc[k] for k in ('k','y','c','chi')),
        'local-policy':tuple(loc[k] for k in ('p','q','K','L')),
        'local-impact':(im['hc'],im['hn'],.01+(1-loc['a'])*im['hn'],im['xp']),
        'local-resource-error':nonlinear(loc,.01)[0],
        'local-half-error':nonlinear(loc,.005)[0],
        'moments-variance':pop[:3],'moments-sd':pop[3],'moments-ac':pop[4],
        'moments-ratios':(1,1,0),
        'moment-gaps':tuple(x-y for x,y in zip((1,1,0),ins['target-ratios'])),
        'utilization-pair':tuple(identify_utilization(alpha,.8,z) for z in (-amp,amp)),
        'e2-values':tuple(new[k] for k in ('s','n','k','y','c','r','w'))+(new['kp']/new['c'],),
        'e4-accounts':tuple(lower[k] for k in ('y','c','kp','w','r'))+(lower['w']*lower['n'],lower['r']*lower['k']),
        'e4-partial':1-h*st['c']/lower['w'],
        'e5-derivative':(1+beta*st['B'])*(1-alpha)/Q(1,4)-chi/Q(3,4),
        'e5-capital':cap['k'],'e6-roots':loc['p_roots'],'e6-stability':loc['K_by_p'],
        'e7-full':nonlinear(loc,.01),'e7-half':nonlinear(loc,.005),
        'e8-var':iid[2],'e8-sd':iid[3],'e8-ac':iid[4],
        'e8-fit-h':fit(0,sqrt(pop[2])),
        'e9-persistent-h':fit(rho,.02),'e9-iid-h':fit(0,.02),
        'e10-residual':1-alpha*beta/Q(1,5),'e11-utilization':identify_utilization(Q(2,5),Q(3,4),Q(1,25))}
    eq(set(out),set(expected),'all visible outputs reconstructed independently')
    for name,want in expected.items():near(out[name],want,name)
    # Algebraic rational anchors supplement floating levels with exact accounts.
    s=alpha*beta;q=1-s;n=(1-alpha)/(1-alpha+chi*q)
    eq((s,q,n),out['exact-policy'],'rational policy anchors')
    kb,yb,cb=out['exact-steady']
    eq(kb**2,n**2*s**3,'exact steady capital without irrational evaluation')
    eq((kb,s*yb,q*yb),(kb,kb,cb),'exact steady saving and consumption accounts')
    eq(sum(out['shock-incomes']),out['exact-impact'][0],'exact shock factor shares exhaust output')
    eq(sum(out['exact-impact'][1:]),out['exact-impact'][0],'exact shock goods uses')
    eq(out['e4-accounts'][5]+out['e4-accounts'][6],out['e4-accounts'][0],'negative shock factor accounts')
    eq(out['e4-accounts'][1]+out['e4-accounts'][2],out['e4-accounts'][0],'negative shock goods uses')
    # Exact stochastic equilibrium conditions at unrelated primitives/states.
    for aa,bb,hh,kk,zz in ((a,b,h,.17,.8),(.5,.8,3,.4,1.2),(.2,.9,.5,.1,.7)):
        al=allocation(aa,bb,hh,kk,zz)
        near(al['c']+al['kp'],al['y'],'exact resource clearing',1e-12)
        near(al['w']*al['n']+al['r']*kk,al['y'],'zero firm profits',1e-12)
        near(al['w']/al['c'],hh/(1-al['n']),'exact intratemporal equality',1e-12)
        for znext in (.6,1.3):
            nx=allocation(aa,bb,hh,al['kp'],znext)
            near(bb*nx['r']/nx['c'],1/al['c'],'statewise Euler before expectation',1e-12)
        for T in (0,1,20):
            near(bb**T*al['kp']/al['c'],bb**T*aa*bb/(1-aa*bb),'candidate shadow tail',1e-12)
    # Independently evaluate the finite-vector value solution by actual iteration.
    B=a/(1-a*b);D=1/(1-a*b)
    H=log(1-a*b)+b*B*log(a*b)+D*(1-a)*log(st['n'])+h*log(1-st['n'])
    P=((float(ins['shock-stay']),1-float(ins['shock-stay'])),(1-float(ins['shock-stay']),float(ins['shock-stay'])))
    innovations=(-float(amp),float(amp))
    A=[0.,0.]
    for _ in range(180):A=[H+D*z+b*sum(P[i][j]*A[j] for j in range(2)) for i,z in enumerate(innovations)]
    for i,z in enumerate(innovations):
        near(A[i],H/(1-b)+D*z/(1-b*float(rho)),'finite-vector resolvent independently iterated',1e-12)
        cur=allocation(a,b,h,.2,exp(z))
        cont=sum(P[i][j]*(B*log(cur['kp'])+A[j]) for j in range(2))
        value=B*log(.2)+A[i]
        near(log(cur['c'])+h*log(1-cur['n'])+b*cont,value,'candidate attained Bellman equation',1e-12)
        for ns,share in ((.1,.4),(.5,.1),(.7,.7)):
            output=exp(z)*.2**a*ns**(1-a);cp=(1-share)*output;kp=share*output
            alternative=log(cp)+h*log(1-ns)+b*sum(P[i][j]*(B*log(kp)+A[j]) for j in range(2))
            guard(alternative<value,'strict original stage comparison')
    # Labor cap adds a multiplier; its feasible direction has the opposite sign.
    capped=allocation(a,b,h,.3,1,.25)
    multiplier=capped['w']/capped['c']-h/(1-capped['n'])
    guard(multiplier>0,'binding cap positive multiplier')
    for alternative_hours in (0,.1,.25):
        guard(multiplier*(alternative_hours-capped['n'])<=0,'cap contribution nonpositive')
    # Local eigenvector selection and all four first-order equations.
    for slope,lam in zip(loc['p_roots'],loc['K_by_p']):
        M=loc['M']
        near(M[0][0]+M[0][1]*slope,lam,'capital eigenvector equation',1e-12)
        near(M[1][0]+M[1][1]*slope,lam*slope,'consumption eigenvector equation',1e-12)
    guard(loc['K_by_p'][0]>1 and abs(loc['K'])<1,'stable root distinct from algebraic root')
    for x,z in ((.02,0),(0,.01),(-.03,.02),(.02,-.03)):
        hc=loc['p']*x+loc['q']*z;hn=(z+loc['a']*x-hc)/loc['dn'];hy=z+loc['a']*x+(1-loc['a'])*hn
        xp=loc['K']*x+loc['L']*z
        near(loc['c']*hc+loc['k']*xp,loc['y']*hy+(1-loc['d'])*loc['k']*x,'linear resource equation',1e-12)
        near(hc+hn/(1-loc['n']),hy,'linear labor equation',1e-12)
        cn=loc['p']*xp+loc['q']*loc['rho']*z
        nn=(loc['rho']*z+loc['a']*xp-cn)/loc['dn']
        yn=loc['rho']*z+loc['a']*xp+(1-loc['a'])*nn
        near(hc,cn-loc['b']*loc['r']*(yn-xp),'linear conditional Euler equation',1e-12)
    for aa,bb,hh in ((a,b,h),(.4,.85,1.5)):
        ss=equilibrium(aa,bb,hh);ll=branch(aa,bb,1,ss['n'],.3)
        near((ll['p'],ll['q'],ll['K'],ll['L']),(aa,1,aa,1),'exact-model derivative as independent local benchmark',1e-12)
    for full,half in zip(nonlinear(loc,.01),nonlinear(loc,.005)):
        guard(3.9<full/half<4.1,'conditional nonlinear quadratic diagnostic')
    # Stationary sums independently imply covariance recursions for positive/negative persistence.
    for persistence in (-.6,0,.6,.8):
        v,C,X,sd,ac=stationary(alpha,persistence,amp)
        near(C,persistence*(float(alpha)*C+v),'stationary cross-covariance identity',1e-12)
        near(X,float(alpha)**2*X+2*float(alpha)*C+v,'stationary variance identity',1e-12)
        near(ac,(float(alpha)*X+persistence*(v+float(alpha)*C))/X,'stationary lag identity',1e-12)
        near(stationary(alpha,persistence,fit(persistence,.02))[3],.02,'fitted population variance',1e-12)
    # Finite Markov forgetting and same-shock initial state differences.
    prob=1.
    for t in range(12):
        near(prob-.5,float(rho)**t/2,'two-state initial distribution forgetting',1e-12)
        prob=prob*float(ins['shock-stay'])+(1-prob)*(1-float(ins['shock-stay']))
    first,second=2.,-1.
    for t in range(12):
        near(first-second,float(alpha)**t*3,'initial capital log difference',1e-12)
        shock=float(amp)*(1 if t%2 else -1)
        first=float(alpha)*first+shock;second=float(alpha)*second+shock
    # A wrong savings share clears resources/labor while violating Euler.
    theta=.2;nh=(1-a)/(1-a+h*(1-theta));kk=.12;zz=.9
    yy=zz*kk**a*nh**(1-a);cc=(1-theta)*yy;kp=theta*yy
    near(cc+kp,yy,'wrong policy can clear resources',1e-12)
    near((1-a)*yy/(nh*cc),h/(1-nh),'wrong policy can satisfy labor',1e-12)
    lhs=0
    for zn,pn in ((.8,.3),(1.2,.7)):
        yn=zn*kp**a*nh**(1-a)
        lhs+=pn*(a*yn/kp)/((1-theta)*yn)
    near(1-b*cc*lhs,out['e10-residual'],'actual conditional wrong-share Euler residual',1e-12)
    for changed in (-float(amp),float(amp)):
        u=identify_utilization(alpha,.8,changed)
        near(float(alpha)*log(u/.8),changed,'utilization measurement decomposition',1e-12)
    invalid=[
        (lambda:real(True),'Boolean'),(lambda:real('1'),'numeric string'),
        (lambda:real(float('nan')),'NaN'),(lambda:real(float('inf')),'infinity'),
        (lambda:primitives(0,b,h),'zero capital exponent'),(lambda:primitives(1,b,h),'unit capital exponent'),
        (lambda:primitives(a,1,h),'undiscounted'),(lambda:primitives(a,0,h),'zero discount'),
        (lambda:primitives(a,b,0),'zero leisure weight'),
        (lambda:allocation(a,b,h,0,1),'zero log capital'),(lambda:allocation(a,b,h,1,0),'zero productivity'),
        (lambda:allocation(a,b,h,1,1,0),'zero hours cap'),(lambda:allocation(a,b,h,1,1,2),'cap exceeds endowment'),
        (lambda:branch(a,b,0,.3,.5),'excluded zero depreciation'),(lambda:branch(a,b,2,.3,.5),'excess depreciation'),
        (lambda:branch(a,b,.1,0,.5),'zero steady hours'),(lambda:branch(a,b,.1,1,.5),'zero steady leisure'),
        (lambda:branch(a,b,.1,.3,1),'unit root shock'),(lambda:branch(a,b,.1,.3,-1),'periodic shock boundary'),
        (lambda:levels(loc,0,10),'hours ceiling failure'),(lambda:nonlinear(loc,0),'zero audit amplitude'),
        (lambda:stationary(a,1,.02),'nonstable moments'),(lambda:stationary(a,0,0),'undefined zero-variance ratio'),
        (lambda:stationary(a,0,.02,True),'Boolean truncation'),(lambda:stationary(a,0,.02,0),'empty sum'),
        (lambda:identify_utilization(a,0,.02),'zero service baseline'),
        (lambda:identify_utilization(a,1,.1),'infeasible utilization explanation'),
        (lambda:read_numeric('True'),'Boolean marker'),(lambda:read_numeric('1/0'),'zero denominator'),
        (lambda:read_numeric('__import__("os")'),'unsafe expression')]
    for fn,label in invalid:
        try:fn()
        except (ValueError,ZeroDivisionError,OverflowError):rejected+=1
        else:raise ValueError('invalid domain accepted: '+label)
    author=json.loads(payload[FILES[3]])
    eq(set(author['exact_prompt_solution_audit']),set(exercises),'author exact prompt scope')
    for item in author['payload_bindings']:
        data=payload[item['path']]
        eq((len(data),sha256(data).hexdigest()),(item['bytes'],item['sha256']),'author bindings')
    review=json.loads(payload[FILES[5]])
    eq({x['path'] for x in review['payload_bindings']},set(FILES[:5]),'five nonself peer bindings')
    eq(len(review['payload_bindings']),5,'exact binding count')
    for item in review['payload_bindings']:
        data=payload[item['path']]
        eq((len(data),sha256(data).hexdigest()),(item['bytes'],item['sha256']),'peer bound payload')
    eq(set(review['exact_prompt_solution_audit']),set(exercises),'complete independent prompt review')
    eq(review['unresolved_findings'],[],'no unresolved peer issue')
    summary={'chapter':'v14-c02','reviewer':'v14_c01','status':'passed','comparisons':total,
             'domain_rejections':rejected,'worked_cases':5,'solved_exercises':12,
             'primitive_markers':len(ins),'result_markers':len(out),'runtime_files':6,
             'independent_methods':['capital-consumption transition eigenvectors','discounted finite-vector iteration','distributed-shock covariance sums','statewise budgets and Euler comparisons'],
             'scope':'Independent calculations corroborate the complete recorded proof/source/solution review; no author executable reuse or global nonlinear numerical certificate.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':
    check()
