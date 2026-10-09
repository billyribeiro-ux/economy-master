"""Quiet four-file NK audit: exact rational roots/accounts and finite-floor regimes.

No network, source artifact, import of another chapter, or filesystem write.
Printed universal proofs are audited in the author record, not inferred from grids.
"""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import isfinite, isqrt, log, sqrt
from pathlib import Path

FILES=('content/chapters/v14-c05.html','scripts/check_v14_c05.py',
       'content/reviews/v14-c05-sources.json','content/reviews/v14-c05-author.json')


def number(x):
    if isinstance(x,bool) or not isinstance(x,(int,float,F)) or not isfinite(float(x)):
        raise ValueError('finite numeric scalar required')
    return F(x)


def discount(x):
    x=number(x)
    if not 0<x<1:raise ValueError('discount in open unit interval')
    return x


def numbers(xs,size=None):
    if not isinstance(xs,(tuple,list)) or not xs or (size is not None and len(xs)!=size):
        raise ValueError('nonempty vector with specified dimension')
    return tuple(number(x) for x in xs)


def visible_number(s):
    if '=' in s:s=s.split('=',1)[1]
    def read(n):
        if isinstance(n,ast.Constant):
            if isinstance(n.value,bool) or not isinstance(n.value,(int,float)):
                raise ValueError('numeric constant required')
            return F(str(n.value))
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return read(n.left)/read(n.right)
        raise ValueError('only rational numbers and tuples are allowed')
    return read(ast.parse(s.strip(),mode='eval').body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.inputs={};self.results={};self.questions=[]
        self.answers=[];self.worked=[];self.sources={};self.links=[];self.body=[]
    def handle_starttag(self,t,attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if 'worked' in d.get('class','').split():self.worked.append(d.get('id'))
        if t=='li' and any(a=='ol' and 'exercises' in b.get('class','').split() for a,b in self.stack):
            self.questions.append(d.get('id'))
        if 'data-solution-for' in d:
            if not any(a=='details' and 'solutions' in b.get('class','').split() for a,b in self.stack):
                raise ValueError('solution not disclosed')
            self.answers.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d.get('href')
        if 'href' in d:self.links.append(d['href'])
        for key,dst in (('data-input',self.inputs),('data-calc',self.results)):
            if key in d:
                if d[key] in dst:raise ValueError('duplicate numerical marker')
                dst[d[key]]=''
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,d))
    def handle_endtag(self,t):
        if not self.stack or self.stack[-1][0]!=t:raise ValueError('unbalanced HTML')
        self.stack.pop()
    def handle_data(self,s):
        self.body.append(s)
        for _,d in self.stack:
            if 'data-input' in d:self.inputs[d['data-input']]+=s
            if 'data-calc' in d:self.results[d['data-calc']]+=s


def ces(theta,elasticity,old,new,output,technology):
    theta=discount(theta)
    e,old,new,y,a=map(number,(elasticity,old,new,output,technology))
    if e<=1 or min(old,new,y,a)<=0:raise ValueError('positive CES prices/resources and elasticity above one')
    if e==2:
        P=1/(theta/old+(1-theta)/new)
        demand=(y*(old/P)**(-2),y*(new/P)**(-2))
    else:
        P=float(theta*old**(1-e)+(1-theta)*new**(1-e))**(1/float(1-e))
        demand=tuple(float(y)*(float(p)/P)**(-float(e)) for p in (old,new))
    dispersion=(theta*demand[0]+(1-theta)*demand[1])/y
    spending=theta*old*demand[0]+(1-theta)*new*demand[1]
    return P,demand,dispersion,y*dispersion/a,spending


def reset(beta,theta,elasticity,current,future,horizon=None):
    beta,theta=discount(beta),discount(theta)
    e,c0,c1=map(number,(elasticity,current,future))
    if e<=1 or min(c0,c1)<=0:raise ValueError('positive cost and elasticity above one')
    w=beta*theta
    if horizon is None:s0=1/(1-w)
    elif isinstance(horizon,bool) or not isinstance(horizon,int) or horizon<1:
        raise ValueError('positive integer finite horizon')
    else:s0=sum((w**j for j in range(horizon)),F(0))
    s1=c0+c1*(s0-1)
    p=e*s1/((e-1)*s0)
    return s0,s1,p


def coefficients(beta,theta,sigma,phi):
    b,t=discount(beta),discount(theta)
    s,f=number(sigma),number(phi)
    if min(s,f)<=0:raise ValueError('positive utility curvatures')
    lam=(1-t)*(1-b*t)/t
    return lam,lam*(s+f)


def matrix(beta,sigma,kappa,pi_feedback,gap_feedback):
    b=discount(beta);s,k,pp,px=map(number,(sigma,kappa,pi_feedback,gap_feedback))
    if min(s,k)<=0:raise ValueError('positive IS and Phillips slopes')
    return ((1+px/s+k/(s*b),(pp-1/b)/s),(-k/b,1/b))


def invert(A):
    if not isinstance(A,(tuple,list)) or len(A)!=2:raise ValueError('two matrix rows required')
    r0,r1=(numbers(row,2) for row in A)
    a,b=r0;c,d=r1;det=a*d-b*c
    if det==0:raise ValueError('singular two by two matrix')
    return ((d/det,-b/det),(-c/det,a/det))


def mv(A,v):
    v=numbers(v,2)
    if len(A)!=2:raise ValueError('two matrix rows required')
    return tuple(sum(x*y for x,y in zip(numbers(row,2),v)) for row in A)


def mm(A,B):
    if len(A)!=2 or len(B)!=2:raise ValueError('matrix dimensions')
    rows=tuple(numbers(row,2) for row in A)
    cols=tuple(zip(*(numbers(row,2) for row in B)))
    return tuple(tuple(sum(x*y for x,y in zip(row,col)) for col in cols) for row in rows)


def roots(A):
    a,b=A[0];c,d=A[1]
    tr=a+d;det=a*d-b*c;disc=tr*tr-4*det
    if disc<0:
        z=complex(float(tr)/2,sqrt(float(-disc))/2)
        return (z.conjugate(),z)
    top=isqrt(disc.numerator);bottom=isqrt(disc.denominator)
    rad=F(top,bottom) if top*top==disc.numerator and bottom*bottom==disc.denominator else sqrt(float(disc))
    return ((tr-rad)/2,(tr+rad)/2)


def response(beta,sigma,kappa,pp,px,rho,nu=0,natural=0):
    rho=number(rho);s=number(sigma);nu,natural=map(number,(nu,natural))
    if not -1<rho<1:raise ValueError('bounded persistence domain')
    A=matrix(beta,s,kappa,pp,px)
    C=((A[0][0]-rho,A[0][1]),(A[1][0],A[1][1]-rho))
    x,pi=mv(invert(C),((natural-nu)/s,0))
    rate=number(pp)*pi+number(px)*x+nu
    return x,pi,rate


def floor_step(beta,sigma,kappa,pp,px,natural,next_x=0,next_pi=0,nu=0):
    b=discount(beta);s,k,pp,px,r,xp,pip,nu=map(number,(sigma,kappa,pp,px,natural,next_x,next_pi,nu))
    if min(s,k)<=0 or min(pp,px)<0:raise ValueError('monotone floor regime requires nonnegative feedback')
    floor=log(float(b));a=pp*k+px;constant=pp*b*pip+nu
    rhs=s*xp+pip+r
    free_x=(rhs-constant)/(s+a)
    free_i=constant+a*free_x
    if free_i>=floor:
        x,rate,regime=free_x,free_i,'interior'
    else:
        x=(float(rhs)-floor)/float(s);rate=floor;regime='floor'
    pi=float(b)*float(pip)+float(k)*float(x)
    return float(x),pi,float(rate),regime


def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(base/p).read_bytes() for p in FILES}
    comparisons=0;rejections=0
    def req(t,message):
        nonlocal comparisons
        comparisons+=1
        if not t:raise ValueError(message)
    def eq(a,b,message):req(a==b,message+': '+repr(a)+' != '+repr(b))
    def close(a,b,message,tol=3e-13):
        if isinstance(b,(tuple,list)):
            req(isinstance(a,(tuple,list)) and len(a)==len(b),message+' dimensions')
            for x,y in zip(a,b):close(x,y,message,tol)
        else:req(isfinite(float(a)) and isfinite(float(b)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),message)
    doc=Document();doc.feed(raw[FILES[0]].decode())
    req(not doc.stack,'closed HTML fragment');eq(len(doc.ids),len(set(doc.ids)),'unique IDs')
    req(all(i.startswith('v14-c05-') for i in doc.ids),'chapter-prefixed IDs')
    questions=['v14-c05-e'+str(i) for i in range(1,13)]
    eq(doc.questions,questions,'exact questions');eq(doc.answers,questions,'complete paired disclosed solutions')
    eq(doc.worked,['v14-c05-w'+str(i) for i in range(1,6)],'five worked cases in order')
    eq([i for i in doc.ids if i in {'v14-c05-households','v14-c05-pricing','v14-c05-linear','v14-c05-determinacy','v14-c05-shocks','v14-c05-floor','v14-c05-exercises','v14-c05-retention'}],
       ['v14-c05-households','v14-c05-pricing','v14-c05-linear','v14-c05-determinacy','v14-c05-shocks','v14-c05-floor','v14-c05-exercises','v14-c05-retention'],'teaching dependency order')
    req(all(h.startswith('https://') or ('/' not in h and '.html' in h) for h in doc.links),'flat links')
    text=''.join(doc.body)
    for key in ('Benchmark answer.','Answer key.','After one week','Ten-point rubric.','uniformly bounded adapted','T=τWN'):
        req(key in text,'instruction/proof scope: '+key)
    src=json.loads(raw[FILES[2]])
    eq(doc.sources,{s['id']:s['url'] for s in src['sources']},'exact scoped source route')
    ins={k:visible_number(v) for k,v in doc.inputs.items()}
    out={k:visible_number(v) for k,v in doc.results.items()}
    used=set()
    def show(name,value,approx=False):
        used.add(name);(close if approx else eq)(out[name],value,'visible '+name)
    dp=ins['dispersion-primitives'];P,dem,disp,N,spending=ces(*dp)
    show('dispersion-price',P);show('dispersion-demands',dem);show('dispersion-labor',N)
    eq(spending,P*dp[4],'exact CES spending');eq(disp,F(26,25),'dispersion identity')
    theta,e,old,new,y,technology=dp
    eq(theta*(P/old)**(e-1)+(1-theta)*(new/P)**(1-e),1,'exact price recursion')
    eq(theta*(P/old)**e+(1-theta)*(new/P)**(-e),disp,'exact dispersion recursion')
    rp=ins['reset-primitives'];s0,s1,price=reset(*rp)
    show('reset-s0',s0);show('reset-s1',s1);show('reset-price',price)
    profit=lambda p:s0/p-s1/(p*p)
    show('reset-profit',profit(price));show('reset-myopic-profit',profit(F(4,5)))
    fs0,fs1,fp=reset(*rp,horizon=2)
    eq(fp,F(32,35),'true finite-horizon reset price');show('e2-tail-sums',(s0-fs0,s1-fs1))
    b,t,sigma,phi=ins['linear-primitives'];lam,kappa=coefficients(b,t,sigma,phi)
    show('linear-lambda',lam);show('linear-kappa',kappa)
    pp,px=ins['active-rule'];A=matrix(b,sigma,kappa,pp,px)
    show('active-matrix',A);show('active-trace-det',(A[0][0]+A[1][1],A[0][0]*A[1][1]-A[0][1]*A[1][0]))
    show('active-roots',roots(A));M=invert(A);show('active-inverse',M)
    passive=matrix(b,sigma,kappa,*ins['passive-rule'])
    show('passive-roots',roots(passive));boundary=matrix(b,sigma,kappa,1,0)
    show('boundary-roots',roots(boundary))
    eq(mv(passive,(F(1,2),1)),(F(1,4),F(1,2)),'passive bounded-eigenvector witness')
    eq(mv(boundary,(F(1,6),1)),(F(1,6),F(1)),'boundary continuum witness')
    rho,nu=ins['shock-primitives']
    persistent=response(b,sigma,kappa,pp,px,rho,nu)
    stronger=response(b,sigma,kappa,ins['stronger-inflation'],px,rho,nu)
    iid=response(b,sigma,kappa,pp,px,0,nu)
    show('persistent-response',persistent);show('persistent-real',persistent[2]-rho*persistent[1])
    show('stronger-response',stronger);show('iid-response',iid)
    show('e8-strong-real',stronger[2]-rho*stronger[1]);show('e8-iid-real',iid[2])
    fb,fs,fk,fpp,fpx,fr=ins['floor-primitives'];bar=-log(float(fb))
    one=floor_step(fb,fs,fk,fpp,fpx,fr)
    zero=floor_step(fb,fs,fk,fpp,fpx,fr,one[0],one[1])
    show('floor-steady-rate',bar,True);show('floor-date1',one[:3],True);show('floor-date0',zero[:3],True)
    eq((one[3],zero[3]),('floor','floor'),'both binding regimes')
    fa=fpx+fpp*fk
    threshold=-bar*float((fs+fa)/fa)
    show('e10-floor-threshold',threshold,True)
    us,uf,ur,ua=ins['e4-productivity'];yn=(1+uf)/(us+uf)*ua
    show('e4-natural-output',yn);show('e4-natural-rate',us*(ur-1)*yn)
    elam,ek=coefficients(b,ins['e5-stickiness'],sigma,phi)
    show('e5-lambda',elam);show('e5-kappa',ek);show('e5-slope-ratio',ek/kappa)
    badfeedback=matrix(b,sigma,kappa,pp,ins['e7-gap-feedback'])
    show('e7-matrix',badfeedback);show('e7-roots',roots(badfeedback))
    S=((F(1),F(1)),(F(-1),F(-6)));Sinv=invert(S)
    show('e11-inverse-basis',Sinv)
    tol=ins['e11-tolerance'];show('e11-coordinate-bounds',(6*tol,21*tol))
    eq(mm(A,M),((1,0),(0,1)),'inverse matrix identity')
    eq(mm(mm(Sinv,M),S),((F(4,11),0),(0,F(2,3))),'weighted norm diagonalization')
    eq(max(sum(abs(x) for x in row) for row in M),F(12,11),'ordinary infinity norm is not contraction')
    eq(mv(S,(3*tol,-3*tol)),(0,15*tol),'coordinate error example within certificate')
    # Stated policy-condition theorem checked against both real/complex numerical roots.
    for B,si,ka in ((b,sigma,kappa),(F(99,100),F(2),F(1,10)),(F(3,4),F(1,2),F(1,3))):
        for ip,ix in ((0,0),(F(1,4),0),(1,0),(F(9,10),1),(F(3,2),F(1,2)),(3,2)):
            mat=matrix(B,si,ka,ip,ix);tr=mat[0][0]+mat[1][1]
            det=mat[0][0]*mat[1][1]-mat[0][1]*mat[1][0]
            margin=ka*(ip-1)+(1-B)*ix
            eq(1-tr+det,margin/(si*B),'characteristic polynomial at one')
            req(tr>2 and det>1,'maintained trace/determinant restrictions')
            rr=roots(mat)
            counts=sum(abs(complex(r))>1+1e-10 for r in rr)
            eq(counts,2 if margin>0 else 1,'root classification matches strict criterion')
    req(all(abs(r)<1 for r in roots(badfeedback)),'negative output response defeats inflation-only shortcut')
    # Every printed response is substituted into all three equations with the true persistence.
    for iP,iX,rr in ((pp,px,0),(pp,px,rho),(2,px,rho),(F(3,2),F(1),F(-1,2))):
        for v,nr in ((nu,0),(0,nu),(nu,nu/2)):
            x,pi,rate=response(b,sigma,kappa,iP,iX,rr,v,nr)
            eq(pi,b*rr*pi+kappa*x,'Phillips equation substitution')
            eq(x,rr*x-(rate-rr*pi-nr)/sigma,'IS equation substitution')
            eq(rate,iP*pi+iX*x+v,'rule substitution')
            den=sigma*(1-rr)+iX+(iP-rr)*kappa/(1-b*rr)
            eq(x,(nr-v)/den,'closed response coefficient independently matched')
    # Natural-rate tracking eliminates the forcing, while natural output can move.
    eq(response(b,sigma,kappa,pp,px,rho,nu,nu),(0,0,nu),'observed-natural-rate tracking allocation')
    # Verify derivative signs of the entire reset objective from its linear numerator.
    for factor in (F(1,2),F(3,4),F(1),F(5,4),F(2)):
        p=price*factor;derivative_numerator=rp[2]*s1-(rp[2]-1)*s0*p
        req((factor<1 and derivative_numerator>0) or (factor==1 and derivative_numerator==0) or (factor>1 and derivative_numerator<0),'global reset derivative signs')
    for persistence in (F(1,4),F(1,2),F(3,4)):
        x0,x1,pr=reset(b,persistence,2,F(2,5),F(3,5))
        eq(pr,2*((1-b*persistence)*F(2,5)+b*persistence*F(3,5)),'future-cost weighting sensitivity')
    for stick in (F(1,4),F(1,2),F(3,4)):
        l,k=coefficients(b,stick,sigma,phi)
        reset_gap=stick/(1-stick)*F(1,100)
        eq(stick*2*F(1,100)-(1-stick)*2*reset_gap,0,'first-order dispersion forcing cancels')
        req(l>0 and k>0,'positive Phillips slopes')
    for prices in ((1,1),(1,F(3,2)),(F(3,4),F(5,4))):
        val=ces(F(1,2),2,*prices,1,1)
        req(val[2]>=1,'exact price dispersion Jensen witness')
        eq(val[4],val[0],'CES expenditure identity')
    # Exact tax/subsidy accounts at arbitrary financed wage bills.
    for tau,W,N,y,P in ((F(1,2),2,3,8,1),(F(1,3),F(5,4),2,3,2)):
        taxes=tau*W*N;profits=P*y-(1-tau)*W*N
        eq(W*N+profits-taxes,P*y,'funded subsidy household resources')
    # Piecewise floor consistency and exact equilibrium residuals, both sides and threshold.
    for shock in (fr,F(-1,100),0,F(1,100)):
        result=floor_step(fb,fs,fk,fpp,fpx,shock)
        x,pi,rate,regime=result
        close(x,-(rate-float(shock))/float(fs),'floor IS',1e-12)
        close(pi,float(fk)*x,'floor Phillips',1e-12)
        close(rate,max(-bar,float(fpp)*pi+float(fpx)*x),'floor rule',1e-12)
        eq(regime,'floor' if float(shock)<threshold else 'interior','correct floor regime')
    x,pi,rate,regime=zero
    close(x,one[0]-(rate-one[1]-float(fr))/float(fs),'two-date IS',1e-12)
    close(pi,float(fb)*one[1]+float(fk)*x,'two-date Phillips',1e-12)
    req(float(fpp)*pi+float(fpx)*x < -bar,'date-zero binding branch')
    req(float(fa*fr/(fs+fa)) < -bar,'unconstrained date-one policy violates floor')
    edge=floor_step(fb,fs,fk,fpp,fpx,threshold)
    close(edge[2],-bar,'regime boundary continuity',1e-12)
    # Small nearby feasible candidate errors obey the explicit eigenbasis residual certificate.
    for direction in ((tol,0),(0,tol),(tol,-tol)):
        dz=mv(S,direction)
        resid=tuple(x-y for x,y in zip(dz,mv(M,dz)))
        et=max(abs(x) for x in mv(Sinv,resid))
        req(max(abs(x) for x in direction)<=3*et,'stationary residual certificate witness')
    bad=[
        (lambda:number(True),'Boolean'),(lambda:number('1'),'numeric string'),
        (lambda:number(float('nan')),'NaN'),(lambda:number(float('inf')),'infinity'),
        (lambda:discount(0),'zero discount'),(lambda:discount(1),'unit discount'),
        (lambda:ces(F(1,2),1,1,2,1,1),'unit substitution elasticity'),
        (lambda:ces(F(1,2),2,0,2,1,1),'zero nominal price'),
        (lambda:ces(F(1,2),2,1,2,1,0),'zero productivity'),
        (lambda:reset(b,1,2,1,1),'no resetting'),(lambda:reset(b,0,2,1,1),'flexible endpoint outside reset helper'),
        (lambda:reset(b,t,1,1,1),'unit markup elasticity'),(lambda:reset(b,t,2,-1,1),'negative marginal cost'),
        (lambda:reset(b,t,2,1,1,0),'empty reset horizon'),(lambda:reset(b,t,2,1,1,True),'Boolean horizon'),
        (lambda:coefficients(b,t,0,1),'zero consumption curvature'),
        (lambda:coefficients(b,t,1,0),'zero labor curvature outside stated model'),
        (lambda:matrix(b,1,0,pp,px),'zero slope outside theorem'),
        (lambda:invert(((1,1),(1,1))),'singular matrix'),
        (lambda:invert(((1,0),(0,1),(1,1))),'excess matrix row'),
        (lambda:invert(((1,0,0),(0,1))),'excess matrix column'),
        (lambda:response(b,sigma,kappa,pp,px,1,nu),'unit root exogenous process'),
        (lambda:response(b,sigma,kappa,*ins['passive-rule'],F(1,2),nu),'resonant particular solution'),
        (lambda:floor_step(fb,fs,fk,fpp,-1,fr),'nonmonotone rule outside floor proof'),
        (lambda:visible_number('1/0'),'zero denominator'),
        (lambda:visible_number('__import__("os")'),'unsafe visible expression')]
    for fn,label in bad:
        try:fn()
        except (ValueError,ZeroDivisionError):rejections+=1
        else:raise ValueError('invalid input accepted: '+label)
    eq(used,set(out),'every visible result tested')
    author=json.loads(raw[FILES[3]])
    eq({x['path'] for x in author['payload_bindings']},set(FILES[:3]),'three nonself bindings')
    eq(len(author['payload_bindings']),3,'exact binding count')
    for item in author['payload_bindings']:
        data=raw[item['path']]
        eq((len(data),sha256(data).hexdigest()),(item['bytes'],item['sha256']),'bound bytes and hash')
    eq(set(author['exact_prompt_solution_audit']),set(questions),'every prompt author-reviewed')
    eq(author['unresolved_findings'],[],'no unresolved author issue')
    summary={'chapter':'v14-c05','status':'passed','comparisons':comparisons,'domain_rejections':rejections,
             'worked_cases':5,'solved_exercises':12,'primitive_markers':len(ins),'result_markers':len(out),
             'runtime_files':4,'scope':'Exact funded accounts, reset sums/global derivative signs, characteristic roots and bounded-linear certificates, shock responses and monotone finite-floor regimes; universal proof/source judgments recorded separately.'}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__=='__main__':
    check()
