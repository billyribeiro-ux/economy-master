"""Independent C10 peer; no author-code import or execution."""
from fractions import Fraction as Q
from decimal import Decimal,localcontext
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

FILES=('production/v14-c10-working.html','production/check_v14_c10_working.py','production/v14-c10-sources-working.json','production/v14-c10-author-review-working.json','production/check_v14_c10_peer_working.py','production/v14-c10-peer-review-working.json')

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
            guard(a['id'] not in self.ids and a['id'].startswith('v14-c10-'),'duplicate/out-of-chapter ID'); self.ids.add(a['id'])
            if 'worked' in a.get('class','').split(): self.worked.append(a['id'])
            if re.fullmatch('v14-c10-e[0-9]+',a['id']): self.exercises.append(a['id'])
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
    guard(type(x) in (Q,int),'exact input');return Q(x)

def positive(x):
    x=rational(x);guard(x>0,'positive input');return x

def probability(x):
    x=rational(x);guard(0<x<1,'positive two-state probabilities');return x

def decimal(x):
    x=rational(x);return Decimal(x.numerator)/Decimal(x.denominator)

def ln(x):
    positive(x)
    with localcontext() as ctx:
        ctx.prec=50;return decimal(x).ln()

def average(v,pi):
    guard(len(v)==2,'two states');p=probability(pi);return p*v[0]+(1-p)*v[1]

def covariance(x,y,pi):
    guard(len(x)==len(y)==2,'two-state covariance');return average(tuple(a*b for a,b in zip(x,y)),pi)-average(x,pi)*average(y,pi)

def sharing(primitives):
    guard(len(primitives)==8,'sharing primitive shape')
    b,h0,f0,hl,hh,fl,fh,pi=map(positive,primitives);probability(pi)
    # The printed witness is symmetric; reconstruct equilibrium from equal shares.
    guard(h0==f0 and hl==fh and hh==fl and pi==Q(1,2),'symmetric witness domain')
    c0=(h0+f0)/2;future=((hl+fl)/2,(hh+fh)/2)
    arrows=(b*pi*c0/future[0],b*(1-pi)*c0/future[1]);bond=b*h0*average((1/hl,1/hh),pi)
    sdfs=((b*h0/hl,b*h0/hh),(b*f0/fl,b*f0/fh))
    with localcontext() as ctx:
        ctx.prec=50;gain=decimal(b)*(decimal(pi)*(ln(future[0])-ln(hl))+decimal(1-pi)*(ln(future[1])-ln(hh)))
    return dict(c0=c0,c=future,arrows=arrows,wealth=h0+arrows[0]*hl+arrows[1]*hh,bond=bond,sdfs=sdfs,gain=gain)

def currency(primitives):
    guard(len(primitives)==6,'currency primitive shape')
    E,m0,m1,x0,x1,pi=map(positive,primitives);probability(pi)
    m=(m0,m1);x=(x0,x1);mf=tuple(a*b for a,b in zip(m,x));rd=1/average(m,pi);rf=1/average(mf,pi)
    returns=tuple(rf*z for z in x)
    return dict(E=E,m=m,x=x,pi=pi,mf=mf,rd=rd,rf=rf,ex=average(x,pi),cov=covariance(m,x,pi),forward=E*rd/rf,spot=E*average(x,pi),returns=returns,premium=average(returns,pi)-rd)

def stop(primitives,kappa):
    guard(len(primitives)==9,'stop primitive shape')
    y0,y1,D,R,b,nu,n0,n1,W=map(rational,primitives);k=rational(kappa)
    guard(min(y0,y1,R,b,nu,n0,n1)>0 and 0<=D<y0 and W>=0 and 0<=k<1,'stop domain')
    a=y0-D
    # First construct the unconstrained optimum from the marginal utility ratio.
    c0=(a+y1/R)/(1+b);unconstrained=c0-a
    slack_at_u=k*(y0+nu*c0)-R*unconstrained
    if slack_at_u>=0:loan=unconstrained
    else:
        guard(R>k*nu,'binding branch has positive denominator')
        loan=k*(y0+nu*a)/(R-k*nu)
    c=(a+loan,y1-R*loan);prices=(nu*c[0]/n0,nu*c[1]/n1);mult=(1/c[0]-b*R/c[1])/R
    K=W+D-loan;guard(K>=0,'foreign dated financing')
    return dict(u=unconstrained,loan=loan,c=c,prices=prices,mult=mult,K=K,slack=k*(y0+prices[0]*n0)-R*loan,face=R*loan,net=loan-D)

def sovereign(primitives,menu,h0,m):
    guard(len(primitives)==7 and len(m)==2 and isinstance(menu,tuple) and len(menu)>0,'sovereign dimensions')
    y0,b,yL,yH,hL,hH,pi=map(positive,primitives);probability(pi);h0=positive(h0);m=tuple(map(positive,m))
    guard(hL<=yL and hH<=yH and h0<=y0,'resource loss domain')
    menu=tuple(map(rational,menu));guard(menu==tuple(sorted(set(menu))) and menu[0]==0,'ordered nonnegative full menu')
    y=(yL,yH);h=(hL,hH);indicators=[];prices=[];c0=[];values=[];continuation=[]
    with localcontext() as ctx:
        ctx.prec=50
        autarky=ln(h0)+decimal(b)*(decimal(pi)*ln(hL)+decimal(1-pi)*ln(hH))
        for debt in menu:
            repay=tuple(int(yi-debt>=hi) for yi,hi in zip(y,h))
            price=average(tuple(mi*H for mi,H in zip(m,repay)),pi);current=y0+price*debt
            future=tuple(yi-debt if H else hi for yi,hi,H in zip(y,h,repay))
            val=ln(current)+decimal(b)*(decimal(pi)*ln(future[0])+decimal(1-pi)*ln(future[1]))
            indicators.append(repay);prices.append(price);c0.append(current);values.append(val);continuation.append(future)
        best=max(range(len(menu)),key=lambda j:(values[j],-menu[j]));chosen=None if autarky>values[best] else best
    return dict(autarky=autarky,indicators=tuple(indicators),prices=tuple(prices),c0=tuple(c0),values=tuple(values),future=tuple(continuation),best=chosen,proceeds=0 if chosen is None else prices[chosen]*menu[chosen],safe=1/average(m,pi))

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
            count+=1;a=a if isinstance(a,Decimal) else decimal(a);b=b if isinstance(b,Decimal) else decimal(b)
            guard(a.is_finite() and b.is_finite() and abs(a-b)<Decimal('8e-11')*max(1,abs(b)),label)
    doc=Reader();doc.feed(raw[FILES[0]].decode());doc.close();eq(doc.stack,[],'HTML nesting')
    ids=[f'v14-c10-e{i}' for i in range(1,13)];eq(doc.exercises,ids,'twelve exact prompts');eq(list(doc.answers),ids,'twelve full paired solutions');eq(doc.worked,[f'v14-c10-w{i}' for i in range(1,5)],'four worked cases')
    for ans in doc.answers.values():eq(len(ans)>450,True,'complete solution length')
    for phrase in ('Benchmark.','One-week retrieval.','Ten-point rubric','price taking','terminal'):
        eq(phrase in ''.join(doc.text),True,'instruction/scope')
    q={k:parse(v) for k,v in doc.values['data-input'].items()};out={}
    s=sharing(q['sharing']);out.update({'sharing-arrows':s['arrows'],'sharing-wealth':s['wealth'],'sharing-complete-return':1/sum(s['arrows']),'sharing-bond-price':s['bond'],'sharing-bond-return':1/s['bond'],'sharing-incomplete-sdfs':s['sdfs'],'sharing-gain':s['gain']})
    b,h0,f0,hl,hh,fl,fh,pi=q['sharing'];eq(h0+sum(a*x for a,x in zip(s['arrows'],(hl,hh))),s['c0']+sum(a*x for a,x in zip(s['arrows'],s['c'])),'H endowment budget')
    eq(f0+sum(a*x for a,x in zip(s['arrows'],(fl,fh))),s['c0']+sum(a*x for a,x in zip(s['arrows'],s['c'])),'F endowment budget')
    for v in s['sdfs']:eq(average(v,pi),s['bond'],'both unspanned kernels price bond')
    for income,country0 in (((hl,hh),h0),((fl,fh),f0)):
        eq(-s['bond']/country0+b*average(tuple(1/x for x in income),pi),0,'bond-only individual derivative')
    cur=currency(q['currency'])
    for marker,field in [('rd','rd'),('mf','mf'),('rf','rf'),('ex','ex'),('cov','cov'),('forward','forward'),('spot-mean','spot'),('returns','returns'),('premium','premium')]:out['currency-'+marker]=cur[field]
    for c in (cur,currency((2,Q(4,5),Q(6,5),Q(9,10),Q(6,5),Q(1,2))),currency((3,Q(1,2),Q(3,2),Q(2),Q(1,2),Q(1,3)))):
        eq(average(tuple(m*r for m,r in zip(c['m'],c['returns'])),c['pi']),1,'domestic pricing of foreign bond')
        eq(c['premium'],-c['rd']*c['rf']*c['cov'],'uncovered risk covariance')
        eq(c['forward']/c['E'],c['rd']/c['rf'],'covered replication cost')
    basek,stressk=q['stop-kappas'];base=stop(q['stop'],basek);stress=stop(q['stop'],stressk)
    out.update({'stop-unconstrained':base['u'],'stop-base-loan':base['loan'],'stop-base-c':base['c'],'stop-base-mu':base['mult'],'stop-stress-loan':stress['loan'],'stop-stress-c':stress['c'],'stop-stress-mu':stress['mult'],'stop-net-flow':stress['net'],'stop-foreign-investment':stress['K']})
    y0,y1,D,R,bb,nu,n0,n1,W=q['stop'];out['stop-feedback-loss']=stressk*(y0+base['prices'][0]*n0)/R-stress['loan']
    with localcontext() as ctx:ctx.prec=50;out['stop-real-depreciation']=decimal(base['prices'][0]/stress['prices'][0]).sqrt()
    a=y0-D;M=y0+nu*a;den=R-basek*nu
    dk=M*R/(den*den);dD=-basek*nu/den
    out['e6-derivatives']=(dk,dD,-1+dD);out['e6-amplifier']=R/den
    altered=(y0,y1,D,Q(6,5),bb,nu,n0,n1,W);higher=stop(altered,basek)
    out.update({'e7-unconstrained':higher['u'],'e7-loan':higher['loan'],'e7-face':higher['face'],'e7-consumption':higher['c'],'e7-foreign-capital':higher['K']})
    zero=stop(q['stop'],0);out['e8-zero-cap']=(zero['loan'],*zero['c'],zero['net'])
    # Distinct economic branches, including saving and nonpositive substituted slope.
    extra=[(q['stop'],basek),(q['stop'],stressk),(q['stop'],0),(altered,basek),((y0,y1,D,R,bb,2,n0,n1,W),Q(3,4)),((y0,y1,D,R,bb,2,n0,n1,W),Q(1,2)),((2,1,0,1,2,1,1,1,3),Q(1,4)),(q['stop'],Q(4,5))]
    for primitives,k in extra:
        z=stop(primitives,k);yy0,yy1,dd,rr,be,nv,nn0,nn1,ww=map(Q,primitives)
        eq(z['slack']>=0 and z['mult']>=0,True,'KKT signs');eq(z['slack']*z['mult'],0,'cap complementarity');eq(min(z['c'])>0,True,'strict consumption')
        eq(z['c'][0]+z['K'],yy0+ww,'date-zero world goods');eq(z['c'][1]+rr*(ww+dd),yy1+rr*z['K'],'terminal world goods')
        eq(z['prices'],(nv*z['c'][0]/nn0,nv*z['c'][1]/nn1),'nontradable goods/price optimum')
    sv=q['sovereign'];menu=q['sovereign-menu'];m=q['global-sdf'];ms=q['global-stress-sdf'];hzero=q['sovereign-h0']
    original=sovereign(sv,menu,hzero,m);shock=sovereign(sv,menu,hzero,ms);reverse=sovereign(sv,menu,hzero,tuple(reversed(m)))
    out['sovereign-autarky']=original['autarky'];out['sovereign-prices']=original['prices'];out['sovereign-c0']=original['c0'];out['sovereign-values']=original['values'];out['sovereign-proceeds']=original['proceeds']
    choose=original['best'];repay=original['indicators'][choose];sp=sv[-1]
    out['sovereign-cov']=covariance(m,repay,sp);out['sovereign-mean-return']=average(repay,sp)/original['prices'][choose]
    out['sovereign-stress-safe']=shock['safe'];out['sovereign-stress-prices']=shock['prices'];out['sovereign-stress-values']=shock['values'];out['sovereign-stress-proceeds']=shock['proceeds']
    out['e10-prices']=reverse['prices'];out['e10-values']=reverse['values'];out['e10-cov']=covariance(tuple(reversed(m)),repay,sp);out['e10-return']=average(repay,sp)/reverse['prices'][choose]
    eq((menu[original['best']],menu[shock['best']],menu[reverse['best']]),(Q(3,5),Q(1,5),Q(1,5)),'exhaustive debt optima')
    for model,pricing in ((original,m),(shock,ms),(reverse,tuple(reversed(m)))):
        for j,debt in enumerate(menu):
            H=model['indicators'][j];price=model['prices'][j]
            eq(price*debt,average(tuple(pricing[z]*H[z]*debt for z in range(2)),sp),'funded discounted foreign receipts')
            eq(price,average(pricing,sp)*average(H,sp)+covariance(pricing,H,sp),'default covariance decomposition')
            for z,yy in enumerate(sv[2:4]):
                defaultloss=(yy-sv[4+z])*(1-H[z]);eq(model['future'][j][z]+debt*H[z]+defaultloss,yy,'terminal repayment/default resources')
    eq(original['indicators'][1],(1,1),'terminal equality repays');eq(original['prices'][-1],0,'zero repayment contract')
    # Transfer exercises reconstructed from their stated primitives.
    aold=Q(-2);r0=Q(11,10);yy0=Q(5);cc0=Q(4);a0=yy0+r0*aold-cc0;cc1=5+a0
    out['e1-assets']=a0;out['e1-ca0']=a0-aold;out['e1-c1']=cc1;eq((cc0-yy0+cc1-5)/r0,aold,'discounted external identity')
    changed=sharing((b,h0,f0,Q(7,4),Q(1,4),Q(1,4),Q(7,4),pi));out['e2-bond-price']=changed['bond'];out['e2-bond-return']=1/changed['bond'];out['e2-gain']=changed['gain']
    reversecur=currency((cur['E'],*cur['m'],*tuple(reversed(cur['x'])),cur['pi']))
    out['e4-mf']=reversecur['mf'];out['e4-rf']=reversecur['rf'];out['e4-forward']=reversecur['forward'];out['e4-premium']=reversecur['premium']
    equity0=150-2*40;equity1=150-Q(5,2)*40;out['e11-equity']=(equity0,equity1,equity0-equity1)
    eq(40*(Q(5,2)-2),equity0-equity1,'equal currency face hedge')
    eq(set(out),set(doc.values['data-calc']),'all printed output markers')
    approximate={'sharing-gain','stop-real-depreciation','sovereign-autarky','sovereign-values','sovereign-stress-values','e2-gain','e10-values'}
    for key,value in out.items():(near if key in approximate else eq)(parse(doc.values['data-calc'][key]),value,'display '+key)
    sources,author,peer=(strict_json(raw[FILES[i]]) for i in (2,3,5))
    eq(doc.sources,{x['id']:x['url'] for x in sources['sources']},'source route identities')
    eq(peer['status'],'passed','peer decision');eq(peer['unresolved_findings'],[],'no unresolved findings');eq(set(peer['exact_prompt_solution_audit']),set(ids),'every exact prompt audited')
    eq({x['path'] for x in peer['payload_bindings']},set(FILES)-{FILES[5]},'five nonself bindings')
    for record in (author,peer):
        bindings=record['payload_bindings']
        entries=([dict(path=p,**v) for p,v in bindings.items()] if isinstance(bindings,dict) else bindings)
        for item in entries:
            payload=raw[item['path']];eq((len(payload),sha256(payload).hexdigest()),(item['bytes'],item['sha256']),'frozen author/peer bytes')
    bad=[lambda:parse('1/0'),lambda:parse('True'),lambda:parse('(1,,2)'),lambda:parse('foo()'),lambda:positive(True),lambda:positive(0),lambda:probability(0),lambda:probability(1),lambda:ln(0),lambda:average((1,),Q(1,2)),lambda:sharing((b,h0,f0,hl,hh,fl,fh,Q(1,3))),lambda:currency((2,0,1,1,1,Q(1,2))),lambda:stop(q['stop'],-1),lambda:stop(q['stop'],1),lambda:stop((1,2,1,1,1,1,1,1,3),basek),lambda:stop((1,2,0,1,1,1,1,1,0),Q(4,5)),lambda:stop((1,2,0,0,1,1,1,1,3),basek),lambda:sovereign(sv,tuple(reversed(menu)),hzero,m),lambda:sovereign(sv,(1,2),hzero,m),lambda:sovereign(sv,menu,2,m),lambda:sovereign(sv,menu,hzero,(0,1)),lambda:strict_json('{"x":1,"x":2}'),lambda:strict_json('{"x":NaN}')]
    for fn in bad:
        try:fn()
        except (ValueError,TypeError):rejections+=1
        else:raise ValueError('invalid domain accepted')
    eq({p:(root/p).read_bytes() for p in FILES},raw,'six runtime payloads unchanged')
    return dict(chapter='v14-c10',component='peer',status='passed',comparisons=count,domain_rejections=rejections,worked_cases=4,solved_exercises=12,primitive_markers=len(q),result_markers=len(out),runtime_files=6,author_code_executed=False,scope='Independent rational budgets/pricing/cap KKT/funding reconstruction and 50-digit Decimal exhaustive debt menu; universal/source judgments recorded separately.')

if __name__=='__main__':
    guard(len(sys.argv)==1,'silent CLI takes no arguments');check()
