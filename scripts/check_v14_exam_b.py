"""V14 Form B original diagnosis/reconstruction audit; quiet four-file API."""
from fractions import Fraction as Q
from decimal import Decimal,localcontext
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

FILES=('content/assessments/parts/v14-exam-b.html','scripts/check_v14_exam_b.py','content/reviews/v14-exam-b-sources.json','content/reviews/v14-exam-b-author.json')

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
        self.values={k:{} for k in ('data-input','data-calc','data-formula')}; self.text=[]; self.points={}; self.domains={}; self.rubrics={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); guard(len(a)==len(attrs),'duplicate attribute')
        if 'data-points' in a:
            guard('id' in a and a['id'] not in self.points,'scored ID'); self.points[a['id']]=int(a['data-points'])
            ds=[b['data-domain'] for _,b in self.stack if 'data-domain' in b]; guard(len(ds)==1,'one score domain'); self.domains[a['id']]=ds[0]
        if 'id' in a:
            guard(a['id'] not in self.ids and (a['id'].startswith('v14-exam-b-') or a['id'] in ('form-b','solutions-b')),'duplicate/out-of-chapter ID'); self.ids.add(a['id'])
            if 'worked' in a.get('class','').split(): self.worked.append(a['id'])
            if re.fullmatch('v14-exam-b-q[0-9]+',a['id']): self.exercises.append(a['id'])
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
    guard(type(x) in (Q,int),'exact number');return Q(x)

def unit(x):
    x=rat(x);guard(0<x<1,'open unit interval');return x

def dec(x):
    x=rat(x);return Decimal(x.numerator)/Decimal(x.denominator)

def mean(v,p):
    guard(len(v)==len(p)>0,'mean dimensions');p=tuple(map(rat,p));guard(min(p)>=0 and sum(p)==1,'probabilities');return sum(a*b for a,b in zip(v,p))

def inverse2(m):
    guard(len(m)==2 and all(len(r)==2 for r in m),'square matrix');a,b,c,d=map(rat,(*m[0],*m[1]));det=a*d-b*c;guard(det!=0,'nonsingular');return ((d/det,-b/det),(-c/det,a/det))

def mv(m,v):
    guard(len(m)>0 and all(len(r)==len(v) for r in m),'matrix dimensions');return tuple(sum(a*b for a,b in zip(row,v)) for row in m)

def policy_value(beta,rewards,nexts,policy):
    b=unit(beta);guard(len(policy)==2 and all(type(a) is int and a in (0,1) for a in policy),'policy domain')
    guard(len(rewards)==len(nexts)==2 and all(len(r)==2 for r in rewards+nexts),'control dimensions')
    guard(all(x in (0,1) for row in nexts for x in row),'state index')
    M=tuple(tuple(Q(int(i==j))-b*int(nexts[i][policy[i]]==j) for j in range(2)) for i in range(2))
    return mv(inverse2(M),tuple(rewards[i][policy[i]] for i in range(2)))

def bellman(beta,rewards,nexts,v):
    b=unit(beta);guard(len(v)==2,'value shape');return tuple(max(rewards[i][a]+b*v[int(nexts[i][a])] for a in (0,1)) for i in (0,1))

def floor(beta,sigma,kappa,pp,px,rn):
    b=unit(beta);sigma,kappa,pp,px,rn=map(rat,(sigma,kappa,pp,px,rn));guard(sigma>0 and kappa>0 and pp>=0 and px>=0,'monotone floor domain')
    with localcontext() as ctx:
        ctx.prec=50;lo=dec(b).ln();slope=pp*kappa+px;x=dec(sigma*rn)/(dec(sigma+slope));rate=dec(slope)*x
        if rate<lo:x=dec(rn)-lo/dec(sigma);rate=lo
        return (x,dec(kappa)*x,rate),dec(slope)*x

def sale(k,D,L,p0,a,z):
    k,D,L,p0,a,z=map(rat,(k,D,L,p0,a,z));guard(k>0 and D>=0 and L>1 and p0>0 and a>0 and 0<=z<=k,'sale primitive domain')
    p=p0-a*z;equity=p*k-D;debt=D-p*z;assets=p*(k-z)
    guard(p>0 and equity>0 and debt>=0,'solvent feasible sale');return p,(assets,debt,equity),p*z,L*D*a/(p*p)

def stationary(p,q):
    p,q=unit(p),unit(q);mu=p/(p+q);return mu,(1-p-q)*mu*(1-mu)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};count=0;rejections=0
    def eq(a,b,label):
        nonlocal count
        count+=1;guard(a==b,label+': '+repr(a)+' != '+repr(b))
    def near(a,b,label):
        nonlocal count
        if isinstance(b,tuple):
            guard(isinstance(a,tuple) and len(a)==len(b),'numeric tuple shape')
            for x,y in zip(a,b):near(x,y,label)
        else:
            count+=1;a=a if isinstance(a,Decimal) else dec(a);b=b if isinstance(b,Decimal) else dec(b)
            guard(a.is_finite() and b.is_finite() and abs(a-b)<Decimal('2e-11')*max(1,abs(b)),label)
    doc=Reader();doc.feed(raw[FILES[0]].decode());doc.close();eq(doc.stack,[],'balanced HTML')
    ids=[f'v14-exam-b-q{i}' for i in range(1,21)];eq(doc.exercises,ids,'exact twenty prompts');eq(list(doc.answers),ids,'twenty complete paired solutions');eq(doc.points,dict.fromkeys(ids,5),'all explicit scores');eq(sum(doc.points.values()),100,'hundred points')
    domains=('dynamic_distribution','labor_policy','pricing_investment','liquidity_international','quantitative_research')
    for i,domain in enumerate(domains):eq([x for x in ids if doc.domains[x]==domain],ids[4*i:4*i+4],'four distinct prompts/domain')
    for key,ans in doc.answers.items():
        eq(len(ans)>500,True,'complete solution');rubric=ans.split('Rubric:')[-1];weights=[int(n) for n in re.findall(r'(?:^|;)\s*(\d)',rubric)];eq(sum(weights),5,'additive rubric '+key)
    text=''.join(doc.text)
    for phrase in ('uncalibrated','300minutes','85overall','15in every domain','no newly retrieved'):
        eq(phrase in text,True,'assessment administration/scope')
    q={k:parse(v) for k,v in doc.values['data-input'].items()};out={}
    beta=q['b1-beta'];r0,r1,n0,n1=q['b1-model'];rewards=(r0,r1);nexts=(n0,n1);proposed=policy_value(beta,rewards,nexts,(1,1));tv=bellman(beta,rewards,nexts,proposed);res=max(abs(a-b) for a,b in zip(tv,proposed));policies=[(i,j) for i in (0,1) for j in (0,1)];vals=[policy_value(beta,rewards,nexts,p) for p in policies];vstar=tuple(max(v[i] for v in vals) for i in (0,1))
    out.update({'b1-bellman':tv,'b1-residual':res,'b1-bound':res/(1-beta),'b1-optimum':vstar,'b1-losses':tuple(a-b for a,b in zip(vstar,proposed))});eq(bellman(beta,rewards,nexts,vstar),vstar,'full Bellman optimum')
    for v in vals:eq(all(a<=b for a,b in zip(v,vstar)),True,'all policy benchmark')
    P=q['b2-transition'];eq(len(P),4,'four distribution states')
    for row in P:eq(sum(row),1,'stochastic row')
    wealth=(0,0,2,2)
    for t in (Q(0),Q(1,5),Q(1,2),Q(1)):
        mu=((1-t)/2,(1-t)/2,t/2,t/2);nextmu=tuple(sum(mu[i]*P[i][j] for i in range(4)) for j in range(4));eq(nextmu,mu,'entire invariant family witness');eq(mean(wealth,mu),2*t,'mixture mean')
    for i in range(4):eq(tuple(sum(P[i][k]*P[k][j] for k in range(4)) for j in range(4)),P[i],'one-step projection')
    out['b2-clearing-distribution']=(Q(1,4),)*4
    alpha,b,Alo,Ahi,k0=q['b3-growth'];unit(alpha);unit(b);guard(Alo>0 and Ahi>0 and k0==1,'growth witness');reported=Q(1,2);y=Alo;cons=(1-reported)*y;kp=reported*y;lhs=1/cons;rhs=b*alpha/((1-reported)*kp)
    out['b3-proposed-allocation']=(cons,kp);out['b3-euler']=(lhs,rhs);out['b3-correct-share']=alpha*b;out['b3-correct-allocation']=((1-alpha*b)*y,alpha*b*y)
    for aa in (Alo,Ahi):
        with localcontext() as ctx:
            ctx.prec=50;power=dec(kp).sqrt();nextc=dec((1-reported)*aa)*power;mp=dec(alpha*aa)/power
            near(dec(b)*mp/nextc,rhs,'statewise Euler cancellation')
    assets,g,mu,nu,income=q['b4-distributions'];eq(mean(assets,mu),mean(assets,nu),'same initial mean');c=tuple(a+income-z for a,z in zip(assets,g));out['b4-next-means']=(mean(g,mu),mean(g,nu));out['b4-type-consumption']=c;out['b4-aggregate-consumption']=(mean(c,mu),mean(c,nu));eq(min(c)>0,True,'policy consumption feasible')
    for weights in (mu,nu):eq(mean(c,weights)+mean(g,weights),mean(assets,weights)+income,'aggregate household budget')
    A,al,eta,r,s,kappa,home,y=q['b5-matching'];unit(al);unit(eta);guard(A>0 and min(r,s,kappa)>0,'matching domain');theta=Q(1);f=A;vacq=A;naive=home+eta*(y-home);badJ=(y-naive)/(r+s);J=kappa/vacq;X=eta*J/(1-eta);w=home+(r+s+f)*X
    out['b5-wrong-job-value']=badJ;out['b5-correct-wage']=w;eq((r+s)*J,y-w,'correct firm Bellman');eq((r+s+f)*X,w-home,'worker surplus');eq(X/(X+J),eta,'Nash sharing');eq(vacq*J,kappa,'funded free entry')
    b,sigma,k,pp,px=q['b6-nk'];unit(b);guard(sigma>0 and k>0,'NK slopes');mat=((1+px/sigma+k/(sigma*b),(pp-1/b)/sigma),(-k/b,1/b));out['b6-forward']=mat;out['b6-roots']=(Q(1,2),Q(9,2));tr=mat[0][0]+mat[1][1];det=mat[0][0]*mat[1][1]-mat[0][1]*mat[1][0]
    for lam in out['b6-roots']:eq(lam*lam-tr*lam+det,0,'characteristic roots')
    vec=((1/b-Q(1,2))/(k/b),Q(1));eq(mv(mat,vec),tuple(Q(1,2)*x for x in vec),'stable eigenvector')
    for scale in (Q(-1,10),Q(1,5)):
        x,pi=(scale*v for v in vec);xn,pin=(Q(1,2)*scale*v for v in vec);rate=pp*pi+px*x;eq(x,xn-(rate-pin)/sigma,'bounded family IS');eq(pi,b*pin+k*x,'bounded family Phillips')
    R,G,debt,Y0=q['b7-fiscal'];guard(R>1 and G>R and debt>0 and Y0>0,'fiscal counterexample domain');out['b7-terminal']=debt;out['b7-repair-surplus']=(R-1)*debt
    for T in (0,1,5,20):
        bT=debt*R**(T+1);eq(bT/R**(T+1),debt,'retained fiscal terminal');eq(bT/(Y0*G**(T+1)),debt/Y0*(R/G)**(T+1),'falling ratio');eq(R*debt-out['b7-repair-surplus'],debt,'funded repair budget')
    sol,shadow=floor(*q['b8-floor']);out['b8-floor-solution']=sol;out['b8-shadow']=shadow
    bf,ss,kk,ip,ix,rn=q['b8-floor']
    with localcontext() as ctx:
        ctx.prec=50;near(sol[0],dec(rn)-sol[2]/dec(ss),'floor IS');near(sol[1],dec(kk)*sol[0],'floor Phillips');eq(shadow<dec(bf).ln(),True,'binding floor consistency')
    prob,safe,X,ps,px,m=q['b9-pricing'];out['b9-proposed-risky-price']=mean(tuple(a*b for a,b in zip(m,X)),prob);eq(mean(m,prob),ps,'safe restriction');eq(out['b9-proposed-risky-price']!=px,True,'wrong risky price');correct=mv(inverse2((prob,tuple(a*b for a,b in zip(prob,X)))),(ps,px));out['b9-correct-kernel']=correct
    prob,X,ps,px,zprice=q['b10-span'];out['b10-kernel-domain']=(Q(-1),Q(1));t=4*zprice-1;out['b10-identified-kernel']=(Q(1),1+t,1-t)
    for t in (Q(-1,2),Q(0),Q(1,2)):
        m=(Q(1),1+t,1-t);eq(mean(m,prob),ps,'null family safe');eq(mean(tuple(a*b for a,b in zip(m,X)),prob),px,'null family risky')
    eq(prob[1]*out['b10-identified-kernel'][1],zprice,'discriminating payoff')
    K0,F,R,Imax,cash=q['b11-q'];guard(K0>0 and R>0 and Imax>0 and cash>=0,'investment resources');I=(3-K0-R)/(1+R);K=K0+I;cost=I+I*I/2;guard(0<=I<=Imax and cost<=cash,'interior investment feasible');marginal=(3-K)/R;avg=(F+3*K-K*K/2)/(R*K)
    out['b11-optimum']=(I,K,marginal,cash-cost);out['b11-average-q']=avg;out['b11-new-average-q']=(40+3*K-K*K/2)/(R*K);eq(1+I,marginal,'marginal investment condition');eq(out['b11-new-average-q']-avg,(40-F)/(R*K),'fixed rent affects average only')
    X,D,J,Z=q['b12-overhang'];oldcredit=min(D,X);oldequity=max(0,X-D);newcredit=min(D,X+Z);newequity=max(0,X+Z-D);out['b12-old-equity-gain']=newequity-oldequity-J;out['b12-face-interval']=(oldcredit,X+Z-J-oldequity);newD=sum(out['b12-face-interval'])/2;gains=(newD-oldcredit,X+Z-newD-J-oldequity);out['b12-strict-gains']=gains;eq(sum(gains),Z-J,'renegotiation total surplus');eq(newD+(X+Z-newD),X+Z,'terminal output allocated')
    early,c1,R,shift,guarantee=q['b13-run'];unit(early);guard(c1>1 and R>1 and shift>0 and guarantee>c1,'run domain');storage=early*c1;guard(storage<1,'positive long investment');long=R*(1-storage);c2=long/(1-early);service=1/c1;u=lambda c:-1/(c+shift)
    out['b13-patient-consumption']=c2;out['b13-run-utility']=service*u(c1)+(1-service)*u(0)
    def shortfall(w):
        w=rat(w);guard(0<=w<=1,'withdrawal mass');resources=storage-c1*w+long if w<=early else R*max(Q(0),1-c1*w);return max(Q(0),guarantee*(1-w)-resources)
    reserve=max(shortfall(w) for w in (Q(0),early,service,Q(1)));out['b13-reserve']=reserve
    for w in (Q(0),early,Q(1,2),Q(3,4),service,Q(9,10),Q(1)):eq(shortfall(w)<=reserve,True,'all piecewise withdrawal branches');eq(out['b13-run-utility']>u(0),True,'finite-zero run incentive')
    eq(shortfall(service),reserve,'attained necessary reserve');eq(early*c1+(1-early)*c2/R,1,'deposit resource feasibility')
    K,D,L,p0,slope=q['b14-sales'];zroots=(Q(1,5),Q(4,5));sales=[sale(K,D,L,p0,slope,z) for z in zroots];out['b14-prices']=tuple(a[0] for a in sales);out['b14-balance-sheets']=tuple(a[1] for a in sales);out['b14-buyer-spending']=tuple(a[2] for a in sales);out['b14-iteration-slopes']=tuple(a[3] for a in sales)
    for z,(p,(asset,debt,equity),paid,der) in zip(zroots,sales):
        eq(asset,L*equity,'active leverage');eq(D-paid,debt,'sale repays debt');eq(asset-debt,equity,'equity identity');eq(paid<=1,True,'buyer funding');eq(L*D/p-(L-1)*K,z,'bank best response')
    pi,E,m0,m1,x0,x1=q['b15-currency'];unit(pi);probs=(pi,1-pi);m=(m0,m1);x=(x0,x1);mf=tuple(a*b for a,b in zip(m,x));rd=1/mean(m,probs);rf=1/mean(mf,probs);cov=mean(mf,probs)-mean(m,probs)*mean(x,probs)
    out['b15-foreign-kernel']=mf;out['b15-foreign-rate']=rf;out['b15-forward']=E*rd/rf;out['b15-premium']=rf*mean(x,probs)-rd;out['b15-covariance']=cov;eq(out['b15-premium'],-rd*rf*cov,'currency risk correction');eq(mean(tuple(mm*rf*xx for mm,xx in zip(m,x)),probs),1,'foreign payoff pricing');eq(mean(x,probs),1,'zero expected depreciation')
    y0,y1,D,R,b,nu,n0,n1,W,oldk,newk=q['b16-stop'];a=y0-D;unconstrained=(y1-b*R*a)/(R*(1+b));loan=newk*(y0+nu*a)/(R-newk*nu);guard(loan<unconstrained and W+D>=loan,'binding funded equilibrium');c=(a+loan,y1-R*loan);prices=(nu*c[0]/n0,nu*c[1]/n1);mult=(1/c[0]-b*R/c[1])/R;foreign=W+D-loan
    out['b16-loan']=loan;out['b16-consumptions']=c;out['b16-multiplier']=mult;out['b16-foreign-investment']=foreign;oldloan=oldk*(y0+nu*a)/(R-oldk*nu);oldprice=nu*(a+oldloan)/n0;out['b16-stale-error']=newk*(y0+oldprice*n0)/R-loan
    eq(R*loan,newk*(y0+prices[0]*n0),'new cap equality');eq(c[0]+foreign,y0+W,'foreign current funding');eq(c[1]+R*(W+D),y1+R*foreign,'world terminal resources')
    b=q['b17-beta'];unit(b);grid_reward=3-(0-1)**2;vgrid=grid_reward/(1-b);true_reward=Q(3);out['b17-residual']=true_reward+b*vgrid-vgrid;out['b17-bound']=out['b17-residual']/(1-b);out['b17-value']=true_reward/(1-b);eq(out['b17-value']-vgrid,out['b17-bound'],'sharp operator loss')
    mu,p,qq,pa,qa=q['b18-moments'];out['b18-scale-domain']=(Q(0),min(1/mu,1/(1-mu)));out['b18-lag-covariances']=(stationary(p,qq)[1],stationary(pa,qa)[1]);eq(stationary(p,qq)[0],mu,'first fitted mean');eq(stationary(pa,qa)[0],mu,'second fitted mean')
    masses,mpc,exposure=q['b19-exposure'];eq(mean(exposure,masses),1,'income incidence normalization');avg=mean(mpc,masses);K=mean(tuple(a*b for a,b in zip(mpc,exposure)),masses);transfers=(Q(1),-masses[0]/masses[1]);eq(mean(transfers,masses),0,'funded transfer budget');direct=mean(tuple(a*b for a,b in zip(mpc,transfers)),masses);out['b19-feedback']=(avg,K,K-avg,direct);out['b19-output-multipliers']=(direct/(1-K),direct/(1-avg));guard(abs(K)<1,'stable stated feedback')
    g1,g2,g3=q['b20-mechanisms'];eq(g2,3*g1,'redundant moment');matrix=((1,2),(1,-1));ab=mv(inverse2(matrix),(g1,g3));out['b20-identified']=ab;out['b20-determinant']=matrix[0][0]*matrix[1][1]-matrix[0][1]*matrix[1][0];out['b20-contrast-domain']=(-g1/2,g1);eq(mv(matrix,ab),(g1,g3),'new identifying contrast');eq(Q(3,20)>g1,True,'out-of-domain exact target')
    eq(set(out),set(doc.values['data-calc']),'exhaustive displayed result markers')
    for key,value in out.items():(near if key in {'b8-floor-solution','b8-shadow'} else eq)(parse(doc.values['data-calc'][key]),value,'display '+key)
    sources,author=(strict_json(raw[FILES[i]]) for i in (2,3));eq(doc.sources,{x['id']:x['url'] for x in sources['sources']},'source identity/URL');eq(author['unresolved_findings'],[],'no open author findings');eq(set(author['exact_prompt_solution_audit']),set(ids),'twenty exact proof audits');eq({x['path'] for x in author['payload_bindings']},set(FILES[:3]),'three nonself hashes')
    for item in author['payload_bindings']:
        payload=raw[item['path']];eq((len(payload),sha256(payload).hexdigest()),(item['bytes'],item['sha256']),'frozen payload')
    bad=[lambda:parse('True'),lambda:parse('1/0'),lambda:parse('(1,,2)'),lambda:parse('x()'),lambda:rat(True),lambda:unit(0),lambda:unit(1),lambda:mean((1,2),(Q(1,4),Q(1,4))),lambda:mean((1,),(Q(1,2),Q(1,2))),lambda:inverse2(((1,1),(1,1))),lambda:inverse2(((1,0),(0,1),(0,0))),lambda:policy_value(Q(1,2),rewards,nexts,(True,1)),lambda:floor(Q(9,10),0,1,1,0,0),lambda:floor(Q(9,10),1,1,-1,0,0),lambda:sale(1,1,3,1,Q(1,3),Q(1,2)),lambda:sale(1,1,1,1,1,0),lambda:stationary(0,Q(1,2)),lambda:stationary(Q(1,2),1),lambda:shortfall(-1),lambda:shortfall(2),lambda:strict_json('{"x":1,"x":2}'),lambda:strict_json('{"x":Infinity}')]
    for fn in bad:
        try:fn()
        except (ValueError,TypeError):rejections+=1
        else:raise ValueError('invalid domain accepted')
    eq({p:(root/p).read_bytes() for p in FILES},raw,'four runtime bytes unchanged')
    return dict(volume='v14',component='exam_b',status='passed',comparisons=count,domain_rejections=rejections,scored_prompts=20,points=100,domains=5,primitive_markers=len(q),result_markers=len(out),sources=len(doc.sources),runtime_files=4,scope='Exact rational model diagnostics plus 50-digit Decimal floor display; all twenty proofs/rubrics/source scopes separately reviewed.')

if __name__=='__main__':
    guard(len(sys.argv)==1,'silent checker has no CLI arguments');check()
