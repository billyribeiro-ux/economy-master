"""Independent C05 six-file peer: direct coefficient algebra and Decimal floor.

No author checker execution or imports. Universal proofs are reviewed separately.
"""
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import isqrt
from pathlib import Path
import re
import sys

FILES=('content/chapters/v14-c05.html','scripts/check_v14_c05.py',
       'content/reviews/v14-c05-sources.json','content/reviews/v14-c05-author.json',
       'scripts/check_v14_c05_peer.py','content/reviews/v14-c05-peer.json')

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
            guard(a['id'] not in self.ids and a['id'].startswith('v14-c05-'),'duplicate/out-of-chapter ID'); self.ids.add(a['id'])
            if 'worked' in a.get('class','').split(): self.worked.append(a['id'])
            if re.fullmatch('v14-c05-e[0-9]+',a['id']): self.exercises.append(a['id'])
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


def rational(x):
    guard(type(x) in (int,Q),'exact rational required')
    return Q(x)


def unit(x):
    x=rational(x); guard(0<x<1,'open unit domain'); return x


def dec(x):
    x=Q(x); return Decimal(x.numerator)/Decimal(x.denominator)


def forward(beta,sigma,k,pp,px):
    b=unit(beta); sigma,k,pp,px=map(rational,(sigma,k,pp,px))
    guard(sigma>0 and k>0,'positive slopes')
    return ((1+px/sigma+k/(sigma*b),(pp-1/b)/sigma),(-k/b,1/b))


def inverse(m):
    guard(len(m)==2 and all(len(row)==2 for row in m),'square matrix')
    a,b=m[0]; c,d=m[1]; det=a*d-b*c
    guard(det!=0,'nonsingular matrix'); return ((d/det,-b/det),(-c/det,a/det))


def multiply(m,n):
    guard(len(m)==len(n)==2 and all(len(row)==2 for row in m+n),'matrix dimensions')
    return tuple(tuple(sum(m[i][k]*n[k][j] for k in range(2)) for j in range(2)) for i in range(2))


def eigenvalues(m):
    trace=m[0][0]+m[1][1]; det=m[0][0]*m[1][1]-m[0][1]*m[1][0]
    d=trace*trace-4*det; guard(d>=0,'real exact root witness')
    a,b=isqrt(d.numerator),isqrt(d.denominator)
    guard(a*a==d.numerator and b*b==d.denominator,'rational root witness')
    return (trace-Q(a,b))/2,(trace+Q(a,b))/2


def shock(beta,sigma,k,pp,px,rho,nu,natural=0):
    unit(beta); guard(sigma>0 and k>0 and -1<rho<1,'shock domain')
    ratio=k/(1-beta*rho)
    denom=sigma*(1-rho)+px+(pp-rho)*ratio
    guard(denom!=0,'no resonant forcing')
    x=(natural-nu)/denom; pi=ratio*x; rate=pp*pi+px*x+nu
    return x,pi,rate


def calvo(beta,theta,sigma,phi):
    b,t=unit(beta),unit(theta)
    guard(sigma>0 and phi>0,'positive preference curvature')
    lam=(1-t)*(1-b*t)/t
    return lam,lam*(sigma+phi)


def floor_solution(beta,sigma,k,pp,px,rn,xnext=Decimal(0),pinext=Decimal(0)):
    unit(beta); guard(sigma>0 and k>0 and pp>=0 and px>=0,'monotone floor domain')
    # Compare at the kink, then solve the appropriate linear branch.
    with localcontext() as ctx:
        ctx.prec=50
        b,sigma,k,pp,px,rn=map(dec,(beta,sigma,k,pp,px,rn))
        lower=b.ln(); slope=px+pp*k; constant=pp*b*pinext
        rhs=sigma*xnext+pinext+rn
        xfloor=(rhs-lower)/sigma
        if constant+slope*xfloor<=lower: x=xfloor; rate=lower
        else: x=(rhs-constant)/(sigma+slope); rate=constant+slope*x
        return x,b*pinext+k*x,rate


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES}; count=0; rejections=0
    def eq(a,b,label):
        nonlocal count
        count+=1; guard(a==b,label+': '+repr(a)+' != '+repr(b))
    def near(a,b,label):
        nonlocal count
        if isinstance(b,tuple):
            guard(isinstance(a,tuple) and len(a)==len(b),'numeric shape')
            for x,y in zip(a,b): near(x,y,label)
        else:
            count+=1; a=a if isinstance(a,Decimal) else dec(a); b=b if isinstance(b,Decimal) else dec(b)
            guard(a.is_finite() and b.is_finite() and abs(a-b)<Decimal('3e-14')*max(1,abs(b)),label)
    doc=Reader(); doc.feed(raw[FILES[0]].decode()); doc.close(); eq(doc.stack,[],'balanced reader')
    ids=[f'v14-c05-e{i}' for i in range(1,13)]; eq(doc.exercises,ids,'all twelve prompts'); eq(list(doc.answers),ids,'all twelve complete solutions')
    eq(doc.worked,[f'v14-c05-w{i}' for i in range(1,6)],'five worked cases')
    for phrase in ('Benchmark answer.','Answer key.','Ten-point rubric.','uniformly bounded adapted'):
        eq(phrase in ''.join(doc.text),True,'instruction/scope phrase')
    q={k:parse(v) for k,v in doc.values['data-input'].items()}; out={}
    t,eps,old,new,Y,A=q['dispersion-primitives']; guard(eps==2,'exact CES witness')
    P=old*new/(t*new+(1-t)*old); demands=tuple(Y*P*P/(p*p) for p in (old,new))
    out['dispersion-price']=P; out['dispersion-demands']=demands; out['dispersion-labor']=(t*demands[0]+(1-t)*demands[1])/A
    eq(t*old*demands[0]+(1-t)*new*demands[1],P*Y,'nominal expenditure')
    eq(t*(P/old)+(1-t)/(new/P),1,'exact index recursion')
    eq(t*(P/old)**2+(1-t)/(new/P)**2,out['dispersion-labor']*A/Y,'exact dispersion recursion')
    b,t,eps,c0,c1=q['reset-primitives']; z=b*t
    s0=1/(1-z); s1=c0+z*c1/(1-z); price=eps/(eps-1)*s1/s0
    out.update({'reset-s0':s0,'reset-s1':s1,'reset-price':price,'reset-profit':s0/price-s1/(price*price),'reset-myopic-profit':s0/(eps*c0/(eps-1))-s1/(eps*c0/(eps-1))**2,'e2-tail-sums':(z*z/(1-z),c1*z*z/(1-z))})
    eq(eps*(c0+z*c1)/((eps-1)*(1+z)),Q(32,35),'genuine two-date reset')
    for factor in (Q(1,2),Q(1),Q(2)):
        candidate=factor*price; derivative=eps*s1-(eps-1)*s0*candidate
        eq((derivative>0)-(derivative<0),(factor<1)-(factor>1),'full reset derivative sign')
    b,t,sigma,phi=q['linear-primitives']; lam,k=calvo(b,t,sigma,phi)
    out['linear-lambda']=lam; out['linear-kappa']=k
    pp,px=q['active-rule']; mat=forward(b,sigma,k,pp,px); inv=inverse(mat)
    out['active-matrix']=mat; out['active-inverse']=inv
    out['active-trace-det']=(mat[0][0]+mat[1][1],mat[0][0]*mat[1][1]-mat[0][1]*mat[1][0])
    out['active-roots']=eigenvalues(mat)
    passive=forward(b,sigma,k,*q['passive-rule']); boundary=forward(b,sigma,k,Q(1),Q(0))
    out['passive-roots']=eigenvalues(passive); out['boundary-roots']=eigenvalues(boundary)
    for m,v,l in ((passive,(Q(1,2),Q(1)),Q(1,2)),(boundary,(Q(1,6),Q(1)),Q(1))):
        eq(tuple(sum(a*z for a,z in zip(row,v)) for row in m),tuple(l*z for z in v),'bounded homogeneous family')
    rho,nu=q['shock-primitives']; resp=shock(b,sigma,k,pp,px,rho,nu)
    strong=shock(b,sigma,k,q['stronger-inflation'],px,rho,nu); iid=shock(b,sigma,k,pp,px,Q(0),nu)
    out['persistent-response']=resp; out['persistent-real']=resp[2]-rho*resp[1]
    out['stronger-response']=strong; out['iid-response']=iid
    out['e8-strong-real']=strong[2]-rho*strong[1]; out['e8-iid-real']=iid[2]
    for inflation,persist,shocksize,natural in ((pp,rho,nu,Q(0)),(q['stronger-inflation'],rho,nu,Q(0)),(pp,Q(0),nu,Q(0)),(pp,Q(-1,2),Q(1,50),Q(1,100)),(pp,rho,nu,nu)):
        x,pi,rate=shock(b,sigma,k,inflation,px,persist,shocksize,natural)
        eq(pi,b*persist*pi+k*x,'Phillips equation')
        eq(x,persist*x-(rate-persist*pi-natural)/sigma,'IS equation')
        eq(rate,inflation*pi+px*x+shocksize,'feedback rule')
    s,f,persistence,tech=q['e4-productivity']; yn=(1+f)/(s+f)*tech
    out['e4-natural-output']=yn; out['e4-natural-rate']=s*(persistence-1)*yn
    lnew,knew=calvo(b,q['e5-stickiness'],sigma,phi); out['e5-lambda']=lnew; out['e5-kappa']=knew; out['e5-slope-ratio']=knew/k
    negative=forward(b,sigma,k,pp,q['e7-gap-feedback']); out['e7-matrix']=negative; out['e7-roots']=eigenvalues(negative)
    S=((Q(1),Q(1)),(Q(-1),Q(-6))); Sinv=inverse(S)
    out['e11-inverse-basis']=Sinv; tol=q['e11-tolerance']; out['e11-coordinate-bounds']=(6*tol,21*tol)
    eq(multiply(mat,inv),((1,0),(0,1)),'matrix inverse')
    eq(multiply(multiply(Sinv,inv),S),((Q(4,11),0),(0,Q(2,3))),'norm eigenbasis')
    eq(max(sum(abs(x) for x in row) for row in inv),Q(12,11),'ordinary norm not contraction')
    eq(1/(1-Q(2,3)),3,'bounded residual multiplier')
    # Trace/determinant certificate algebra for different primitive regimes.
    for beta,ss,kk in ((b,sigma,k),(Q(9,10),Q(2),Q(1,4))):
        for ip,ix in ((Q(0),Q(0)),(Q(1),Q(0)),(Q(9,10),Q(1)),(Q(2),Q(1))):
            m=forward(beta,ss,kk,ip,ix); tr=m[0][0]+m[1][1]; det=m[0][0]*m[1][1]-m[0][1]*m[1][0]
            eq(1-tr+det,(kk*(ip-1)+(1-beta)*ix)/(ss*beta),'root condition polynomial')
            eq(tr>2 and det>1,True,'maintained positive feedback root restrictions')
    for stick in (Q(1,4),Q(1,2),Q(3,4)):
        inflation=Q(1,100); resetgap=stick*inflation/(1-stick)
        eq(stick*2*inflation-(1-stick)*2*resetgap,0,'first-order dispersion cancellation')
    for tau,wage,hours,price,output in ((Q(1,2),Q(2),Q(3),Q(1),Q(8)),(Q(1,3),Q(5,4),Q(2),Q(2),Q(3))):
        taxes=tau*wage*hours; dividends=price*output-(1-tau)*wage*hours
        eq(wage*hours+dividends-taxes,price*output,'funded subsidy consolidation')
    fb,fs,fk,fpp,fpx,fr=q['floor-primitives']
    with localcontext() as ctx:
        ctx.prec=50
        steady=-dec(fb).ln(); one=floor_solution(fb,fs,fk,fpp,fpx,fr); zero=floor_solution(fb,fs,fk,fpp,fpx,fr,one[0],one[1])
        out['floor-steady-rate']=steady; out['floor-date1']=one; out['floor-date0']=zero
        slope=fpx+fpp*fk; out['e10-floor-threshold']=-steady*dec((fs+slope)/slope)
        for rn in (fr,Q(-1,100),Q(0),Q(1,100)):
            x,pi,rate=floor_solution(fb,fs,fk,fpp,fpx,rn)
            near(x,-(rate-dec(rn))/dec(fs),'floor IS'); near(pi,dec(fk)*x,'floor Phillips')
            near(rate,max(-steady,dec(fpp)*pi+dec(fpx)*x),'floor rule')
        for solution in (one,zero): eq(dec(fpp)*solution[1]+dec(fpx)*solution[0]<-steady,True,'both dates bind')
        near(zero[0],one[0]-(zero[2]-one[1]-dec(fr))/dec(fs),'backward date-zero IS')
        near(zero[1],dec(fb)*one[1]+dec(fk)*zero[0],'backward date-zero Phillips')
    eq(set(out),set(doc.values['data-calc']),'all thirty-six visible results')
    approx={'floor-steady-rate','floor-date1','floor-date0','e10-floor-threshold'}
    for name,value in out.items(): (near if name in approx else eq)(parse(doc.values['data-calc'][name]),value,'visible '+name)
    sources,author,peer=(strict_json(raw[FILES[i]]) for i in (2,3,5))
    eq(doc.sources,{s['id']:s['url'] for s in sources['sources']},'primary method identity')
    eq(peer['status'],'passed','peer decision'); eq(peer['unresolved_findings'],[],'no open findings')
    eq(set(peer['exact_prompt_solution_audit']),set(ids),'all twelve written proof judgments')
    eq({x['path'] for x in peer['payload_bindings']},set(FILES)-{FILES[5]},'five nonself bindings')
    for record in (author,peer):
        for item in record['payload_bindings']:
            payload=raw[item['path']]; eq((len(payload),sha256(payload).hexdigest()),(item['bytes'],item['sha256']),'frozen payload')
    bad=[lambda:parse('True'),lambda:parse('1/0'),lambda:parse('x()'),lambda:parse('(1,,2)'),lambda:unit(True),lambda:unit(0),lambda:unit(1),lambda:forward(b,0,k,pp,px),lambda:inverse(((1,1),(1,1))),lambda:inverse(((1,0),(0,1),(0,0))),lambda:calvo(b,0,1,1),lambda:calvo(b,1,1,1),lambda:calvo(b,t,0,1),lambda:shock(b,sigma,k,pp,px,1,nu),lambda:shock(b,sigma,k,*q['passive-rule'],Q(1,2),nu),lambda:floor_solution(fb,fs,fk,fpp,-1,fr),lambda:strict_json('{"a":1,"a":2}'),lambda:strict_json('{"a":NaN}')]
    for fn in bad:
        try: fn()
        except (ValueError,TypeError): rejections+=1
        else: raise ValueError('invalid domain accepted')
    eq({p:(root/p).read_bytes() for p in FILES},raw,'all six runtime bytes unchanged')
    return {'chapter':'v14-c05','component':'peer','status':'passed','comparisons':count,'domain_rejections':rejections,'worked_cases':5,'solved_exercises':12,'primitive_markers':len(q),'result_markers':len(out),'runtime_files':6,'author_code_executed':False,'scope':'Independent direct coefficient/eigenbasis rational algebra and 50-digit Decimal floor branches; universal and source-scope judgments separately recorded.'}


if __name__=='__main__':
    guard(len(sys.argv)==1,'silent checker takes no arguments')
    check()
