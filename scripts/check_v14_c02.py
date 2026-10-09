"""Quiet standard-library audit; exactly four runtime payloads; no writes/network."""
import ast
from fractions import Fraction
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import exp, isfinite, log, sqrt
from pathlib import Path

FILES = ('content/chapters/v14-c02.html', 'scripts/check_v14_c02.py',
         'content/reviews/v14-c02-sources.json', 'content/reviews/v14-c02-author.json')


def require(test, message):
    if not test:
        raise ValueError(message)


def scalar(x):
    require(not isinstance(x, bool) and isinstance(x, (int, float, Fraction)), 'finite numeric scalar required')
    y = float(x)
    require(isfinite(y), 'nonfinite scalar')
    return y


def exact(alpha, beta, chi, k=1, z=1, cap=None):
    a,b,h,k,z = map(scalar, (alpha,beta,chi,k,z))
    require(0<a<1 and 0<b<1 and h>0 and k>0 and z>0, 'exact model domain')
    s=a*b; q=1-s; n=(1-a)/(1-a+h*q)
    if cap is not None:
        cap=scalar(cap)
        require(0<cap<1, 'positive hours cap below one')
        n=min(n,cap)
    y=z*k**a*n**(1-a)
    return dict(a=a,b=b,chi=h,s=s,q=q,n=n,k=k,z=z,y=y,c=q*y,kp=s*y,
                w=(1-a)*y/n,r=a*y/k)


def steady_exact(alpha,beta,chi,cap=None):
    t=exact(alpha,beta,chi,cap=cap)
    k=t['n']*t['s']**(1/(1-t['a']))
    return exact(alpha,beta,chi,k=k,cap=cap)


def local(alpha,beta,delta,n,rho):
    a,b,d,n,rho=map(scalar,(alpha,beta,delta,n,rho))
    require(0<a<1 and 0<b<1 and 0<d<=1 and 0<n<1 and abs(rho)<1, 'local model domain')
    r=1/b-1+d; m=r/a; k=n*(a/r)**(1/(1-a)); y=m*k; c=y-d*k
    require(c>0, 'positive steady consumption')
    chi=(1-a)*y*(1-n)/(n*c); dn=a+n/(1-n)
    U=1-d+m*a*(1+(1-a)/dn); V=m*(1+(1-a)/dn); W=c/k+m*(1-a)/dn
    A=1+b*r*(1-a)/dn; B=b*r*(1-a-(1-a)*a/dn)
    qa=W*A; qb=W*B+1-U*A; qc=-U*B
    disc=qb*qb-4*qa*qc
    require(disc>=0 and qa>0, 'real quadratic roots')
    roots=sorted(((-qb-sqrt(disc))/(2*qa),(-qb+sqrt(disc))/(2*qa)))
    stable=[p for p in roots if abs(U-W*p)<1]
    require(len(stable)==1,'one stable branch required')
    p=stable[0]; H=A*p+B
    den=1+H*W-rho*(1+b*r*(1-a)/dn)
    require(abs(den)>1e-12,'singular shock coefficient')
    q=(H*V-rho*b*r*(1+(1-a)/dn))/den
    K=U-W*p; L=V-W*q
    return dict(a=a,b=b,d=d,n=n,rho=rho,r=r,k=k,y=y,c=c,chi=chi,dn=dn,
                m=m,U=U,V=V,W=W,A=A,B=B,roots=roots,p=p,q=q,K=K,L=L)


def policy(t,x,a):
    x,a=map(scalar,(x,a))
    hc=t['p']*x+t['q']*a
    hn=((t['a']-t['p'])*x+(1-t['q'])*a)/t['dn']
    hkp=t['K']*x+t['L']*a
    k=t['k']*exp(x); n=t['n']*exp(hn); c=t['c']*exp(hc); kp=t['k']*exp(hkp)
    require(0<n<1 and k>0 and c>0 and kp>0,'approximate policy infeasible')
    y=exp(a)*k**t['a']*n**(1-t['a'])
    w=(1-t['a'])*y/n; r=t['a']*y/k
    return dict(k=k,n=n,c=c,kp=kp,y=y,w=w,r=r,hc=hc,hn=hn,hkp=hkp)


def audit(t,eps):
    eps=scalar(eps)
    require(eps>0,'positive shock amplitude')
    u=policy(t,0,eps); xp=u['hkp']; prob=(1+t['rho'])/2
    plus=policy(t,xp,eps); minus=policy(t,xp,-eps)
    goods=u['c']+u['kp']-u['y']-(1-t['d'])*u['k']
    labor=log(t['chi']*u['c']/((1-u['n'])*u['w']))
    euler=1-t['b']*u['c']*(prob*(plus['r']+1-t['d'])/plus['c']+(1-prob)*(minus['r']+1-t['d'])/minus['c'])
    return goods,labor,euler


def moments(alpha,rho,h):
    a,rho,h=map(scalar,(alpha,rho,h))
    require(0<a<1 and abs(rho)<1 and h>0,'stationary bounded-shock moment domain')
    v=h*h; C=rho*v/(1-a*rho); X=(v+2*a*C)/(1-a*a)
    Y=v+a*a*X+2*a*C
    lag=a*Y+rho*(v+a*C)
    return v,C,X,sqrt(Y),lag/Y


def fitted_h(alpha,rho,sigma):
    a,rho,sigma=map(scalar,(alpha,rho,sigma))
    require(0<a<1 and abs(rho)<1 and sigma>0,'calibration domain')
    return sigma*sqrt((1-a*rho)*(1-a*a)/(1+a*rho))


def utilization(alpha,baseline,change):
    a,u,b=map(scalar,(alpha,baseline,change))
    require(0<a<1 and 0<u<=1,'utilization input domain')
    out=u*exp(b/a)
    require(0<out<=1,'utilization exceeds feasible unit interval')
    return out


def mark_number(value):
    """Only numbers, tuples/lists, unary signs and rational division."""
    def walk(n):
        if isinstance(n,ast.Constant): return scalar(n.value)
        if isinstance(n,(ast.Tuple,ast.List)): return tuple(walk(i) for i in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=walk(n.right); require(d!=0,'zero marker denominator'); return walk(n.left)/d
        raise ValueError('invalid visible numeric marker')
    return walk(ast.parse(value.strip(),mode='eval').body)


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=[]; self.markers={}; self.pending=[]
        self.exercises=[]; self.solutions=[]; self.worked=[]; self.sources={}; self.links=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs); classes=d.get('class','').split()
        if 'id' in d:
            require(d['id'] not in self.ids,'duplicate ID'); self.ids.append(d['id'])
        if tag=='li' and d.get('id','').startswith('v14-c02-e'): self.exercises.append(d['id'])
        if 'worked' in classes: self.worked.append(d.get('id'))
        if 'data-solution-for' in d:
            require(any(t=='details' and 'solutions' in v.get('class','').split() for t,v in self.stack),'solution outside disclosure')
            self.solutions.append(d['data-solution-for'])
        if 'data-source' in d:
            self.sources[d['data-source']]=d.get('href')
        if tag=='a': self.links.append(d.get('href',''))
        for typ in ('data-input','data-calc'):
            if typ in d:
                key=d[typ]; require(key not in self.markers,'duplicate marker')
                self.markers[key]=[typ,'']; self.pending.append((key,len(self.stack)))
        if tag not in ('br','hr','img','meta','link','input'): self.stack.append((tag,d))
    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack[-1][0]==tag,'unbalanced HTML '+tag)
        self.stack.pop()
        self.pending=[(k,n) for k,n in self.pending if n<len(self.stack)]
    def handle_data(self,data):
        for k,_ in self.pending:self.markers[k][1]+=data


def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={p:(base/p).read_bytes() for p in FILES}
    doc=Manuscript(); doc.feed(payload[FILES[0]].decode()); doc.close()
    require(not doc.stack,'unclosed tags')
    require(all(i.startswith('v14-c02-') for i in doc.ids),'foreign chapter ID')
    require(doc.worked==['v14-c02-w'+str(i) for i in range(1,6)],'worked cases mismatch')
    required=['v14-c02-e'+str(i) for i in range(1,13)]
    require(doc.exercises==required and doc.solutions==required,'exact exercise pairing')
    require(all(h.startswith(('https://','v','curriculum.html#')) or h.startswith('#') for h in doc.links),'nonflat link')
    sources=json.loads(payload[FILES[2]])
    source_routes={s['id']:s['url'] for s in sources['sources']}
    require(doc.sources==source_routes,'source route mismatch')
    review=json.loads(payload[FILES[3]])
    require(set(review['exact_prompt_solution_audit'])==set(required),'incomplete prompt review')
    bindings=review['payload_bindings']
    require({b['path'] for b in bindings}==set(FILES[:3]) and len(bindings)==3,'nonself bindings')
    for b in bindings:
        require(len(payload[b['path']])==b['bytes'] and sha256(payload[b['path']]).hexdigest()==b['sha256'],'payload binding mismatch')
    inputs={k:mark_number(v[1]) for k,v in doc.markers.items() if v[0]=='data-input'}
    vals={k:mark_number(v[1]) for k,v in doc.markers.items() if v[0]=='data-calc'}
    expected_inputs={'exact-alpha':1/3,'exact-beta':3/4,'exact-chi':2,'impact-z':11/10,
      'shock-h':1/50,'shock-stay':4/5,'local-parameters':(.36,.96,.1,1/3,.8),'target-ratios':(.7,2.4,.8)}
    comparisons=0; rejections=0
    def near(got,want,tol=6e-11):
        nonlocal comparisons
        if isinstance(want,(tuple,list)):
            require(isinstance(got,(tuple,list)) and len(got)==len(want),'tuple shape')
            for g,w in zip(got,want):near(g,w,tol)
        else:
            require(isfinite(float(got)) and abs(float(got)-float(want))<=tol*max(1,abs(float(want))),f'numeric mismatch {got} versus {want}')
            comparisons+=1
    require(set(inputs)==set(expected_inputs),'primitive markers')
    for key,value in expected_inputs.items():near(inputs[key],value)
    a,b,h=inputs['exact-alpha'],inputs['exact-beta'],inputs['exact-chi']
    t=steady_exact(a,b,h); sh=exact(a,b,h,t['k'],inputs['impact-z'])
    rho=2*inputs['shock-stay']-1; amp=inputs['shock-h']
    m=moments(a,rho,amp); loc=local(*inputs['local-parameters']); imp=policy(loc,0,.01)
    cap=steady_exact(a,b,h,cap=.25); e2=steady_exact(.5,.8,3); e4=exact(a,b,h,t['k'],.8)
    im=moments(a,0,amp)
    D=1/(1-a*b)
    results={
      'exact-policy':(t['s'],t['q'],t['n']), 'exact-steady':(t['k'],t['y'],t['c']),
      'exact-prices':(t['r'],t['w']),'exact-impact':(sh['y'],sh['c'],sh['kp']),
      'shock-rho':rho,'value-shock':D/(1-b*rho),
      'shock-wage':sh['w'],'shock-rental':sh['r'],'shock-incomes':(sh['w']*sh['n'],sh['r']*sh['k']),
      'partial-labor':1-h*t['c']/sh['w'],
      'local-steady':tuple(loc[k] for k in ('k','y','c','chi')),
      'local-policy':tuple(loc[k] for k in ('p','q','K','L')),
      'local-impact':(imp['hc'],imp['hn'],.01+a*0+(1-loc['a'])*imp['hn'],imp['hkp']),
      'local-resource-error':audit(loc,.01)[0],'local-half-error':audit(loc,.005)[0],
      'moments-variance':m[:3],'moments-sd':m[3],'moments-ac':m[4],
      'moments-ratios':(1,1,0),'moment-gaps':tuple(x-y for x,y in zip((1,1,0),inputs['target-ratios'])),
      'utilization-pair':tuple(utilization(a,.8,x) for x in (-amp,amp)),
      'e2-values':tuple(e2[k] for k in ('s','n','k','y','c','r','w'))+(e2['kp']/e2['c'],),
      'e4-accounts':tuple(e4[k] for k in ('y','c','kp','w','r'))+(e4['w']*e4['n'],e4['r']*e4['k']),
      'e4-partial':1-h*t['c']/e4['w'],'e5-derivative':D*(1-a)/.25-h/.75,'e5-capital':cap['k'],
      'e6-roots':loc['roots'],'e6-stability':tuple(loc['U']-loc['W']*p for p in loc['roots']),
      'e7-full':audit(loc,.01),'e7-half':audit(loc,.005),'e8-var':im[2],'e8-sd':im[3],'e8-ac':im[4],
      'e8-fit-h':fitted_h(a,0,sqrt(m[2])),'e9-persistent-h':fitted_h(a,rho,.02),
      'e9-iid-h':fitted_h(a,0,.02),'e10-residual':1-a*b/.2,'e11-utilization':utilization(.4,.75,.04)}
    require(set(vals)==set(results),'result markers mismatch')
    for key,value in results.items():
        try:near(vals[key],value)
        except ValueError as err:raise ValueError(key+': '+str(err)) from err
    # Independent equilibrium identities and parameter interventions, including a binding cap.
    for aa,bb,cc,kk,zz in ((a,b,h,t['k'],1),(.2,.8,1,.4,.8),(.5,.9,3,1.2,1.2),(.7,.7,.5,.02,1.05)):
        u=exact(aa,bb,cc,kk,zz)
        near(u['c']+u['kp'],u['y']);near(u['w']*u['n']+u['r']*kk,u['y'])
        near(cc/(1-u['n']),u['w']/u['c'])
        for znext in (.8,1.2):
            nxt=exact(aa,bb,cc,u['kp'],znext)
            near(bb*nxt['r']/nxt['c'],1/u['c'])
        near(u['kp']/u['c'],aa*bb/(1-aa*bb))
        # Every finite allocation perturbation is dominated by the concavity tangent.
        for factor in (.8,1.2):
            nn=min(.95,u['n']*factor); yp=zz*kk**aa*nn**(1-aa); cp=.6*yp; kp=.4*yp
            du=log(cp/u['c'])+cc*log((1-nn)/(1-u['n']))
            bound=-(kp-u['kp'])/u['c']
            require(du<=bound+1e-12,'concavity tangent inequality');comparisons+=1
    for ncap in (.2,.4):
        u=exact(a,b,h,.1,1,cap=ncap)
        near(u['n'],min(t['n'],ncap))
        require(u['w']/u['c']-h/(1-u['n'])>=-1e-12,'cap multiplier sign');comparisons+=1
    # Finite-vector value solution and Bellman comparisons from scratch.
    B=a/(1-a*b); H=log(1-a*b)+b*B*log(a*b)+D*(1-a)*log(t['n'])+h*log(1-t['n'])
    def value(k,az):return B*log(k)+H/(1-b)+D*az/(1-b*rho)
    for az in (-amp,amp):
        u=exact(a,b,h,.13,exp(az)); prob=inputs['shock-stay']
        ev=prob*value(u['kp'],az)+(1-prob)*value(u['kp'],-az)
        near(value(.13,az),log(u['c'])+h*log(1-u['n'])+b*ev,2e-12)
        for nn,share in ((.2,.2),(.5,.4),(.7,.6)):
            yy=exp(az)*.13**a*nn**(1-a); kp=share*yy
            rhs=log((1-share)*yy)+h*log(1-nn)+b*(prob*value(kp,az)+(1-prob)*value(kp,-az))
            require(rhs<value(.13,az),'strict Bellman policy dominance');comparisons+=1
    # All linearized equations at independent state vectors and both polynomial roots.
    for p in loc['roots']:
        near(p,(loc['A']*p+loc['B'])*(loc['U']-loc['W']*p),1e-12)
    require(loc['U']-loc['W']*loc['roots'][0]>1 and abs(loc['K'])<1,'stable selection');comparisons+=1
    for x,az in ((.01,0),(0,.02),(-.04,.01),(.03,-.02)):
        hc=loc['p']*x+loc['q']*az; hn=((loc['a']-loc['p'])*x+(1-loc['q'])*az)/loc['dn']
        hy=az+loc['a']*x+(1-loc['a'])*hn; xp=loc['K']*x+loc['L']*az
        near(loc['c']*hc+loc['k']*xp,loc['y']*hy+(1-loc['d'])*loc['k']*x,1e-12)
        near(hc+hn/(1-loc['n']),hy,1e-12)
        ecp=loc['p']*xp+loc['q']*loc['rho']*az
        enp=((loc['a']-loc['p'])*xp+(1-loc['q'])*loc['rho']*az)/loc['dn']
        eyp=loc['rho']*az+loc['a']*xp+(1-loc['a'])*enp
        near(hc,ecp-loc['b']*loc['r']*(eyp-xp),1e-12)
    # Full depreciation is a separately solved exact derivative benchmark for local code.
    for aa,bb,cc in ((a,b,h),(.4,.85,1.5)):
        et=steady_exact(aa,bb,cc); lt=local(aa,bb,1,et['n'],.3)
        near((lt['p'],lt['q'],lt['K'],lt['L']),(aa,1,aa,1),1e-12)
    # Moment recursions and independent finite sums of the stationary representation.
    for rr in (-.6,0,.6,.8):
        v,C,X,sd,ac=moments(a,rr,amp)
        near(C,rr*(a*C+v),1e-12);near(X,a*a*X+v+2*a*C,1e-12)
        finite=sum(a**(i+j)*v*rr**abs(i-j) for i in range(70) for j in range(70))
        near(X,finite,1e-12)
        near(moments(a,rr,fitted_h(a,rr,.02))[3],.02,1e-12)
    for ee in (.01,.005):
        out=audit(loc,ee); require(all(abs(v)<1e-3 for v in out),'local residual too large');comparisons+=1
    for j in range(3):
        ratio=audit(loc,.01)[j]/audit(loc,.005)[j]
        require(3.9<ratio<4.1,'quadratic residual scaling');comparisons+=1
    # Guards are explicit and survive python -O; no assertions are used.
    invalid=[(exact,(0,b,h)),(exact,(1,b,h)),(exact,(a,0,h)),(exact,(a,1,h)),(exact,(a,b,0)),
      (exact,(a,b,h,0)),(exact,(a,b,h,1,0)),(exact,(True,b,h)),(exact,(float('nan'),b,h)),
      (exact,(a,b,h,1,1,0)),(exact,(a,b,h,1,1,1)),(local,(a,b,0,.3,.6)),
      (local,(a,b,1.1,.3,.6)),(local,(a,b,.1,0,.6)),(local,(a,b,.1,1,.6)),
      (local,(a,b,.1,.3,1)),(local,(a,b,.1,.3,-1)),(moments,(a,1,amp)),
      (moments,(a,-1,amp)),(moments,(a,.6,0)),(moments,(1,.6,amp)),(moments,(-.1,.6,amp)),
      (fitted_h,(a,.6,0)),(fitted_h,(a,.6,-1)),(fitted_h,(a,float('inf'),.02)),
      (utilization,(0,.8,.02)),(utilization,(1,.8,.02)),(utilization,(a,0,.02)),
      (utilization,(a,1.1,.02)),(utilization,(a,.99,.1)),(policy,(loc,0,10)),
      (audit,(loc,0)),(mark_number,('1/0',)),(mark_number,('__import__("os")',)),
      (mark_number,('True',)),(scalar,('0.2',))]
    for f,args in invalid:
        try:f(*args)
        except (ValueError,OverflowError):rejections+=1
        else:raise ValueError('invalid domain accepted: '+f.__name__)
    summary={'chapter':'v14-c02','status':'passed','comparisons':comparisons,'domain_rejections':rejections,
      'worked_cases':len(doc.worked),'solved_exercises':len(doc.solutions),'primitive_markers':len(inputs),
      'result_markers':len(vals),'runtime_files':len(FILES),'scope':'Original exact RBC proofs, equilibrium accounts, local linear system and synthetic population moments; no empirical replication or global nonlinear certificate.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':
    check()
