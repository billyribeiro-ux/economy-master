"""C10 original-model audit. Standard library, four read-only payloads, quiet API/CLI."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
from math import isfinite, log, sqrt
from pathlib import Path

FILES=('production/v14-c10-working.html','production/check_v14_c10_working.py','production/v14-c10-sources-working.json','production/v14-c10-author-review-working.json')
def need(ok,msg):
    if not ok: raise ValueError(msg)
def num(x):
    need(not isinstance(x,bool) and isinstance(x,(int,float,F)) and isfinite(float(x)),'finite numeric primitive')
    return F(str(x)) if isinstance(x,float) else F(x)
def parsed(s):
    def rec(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.List,ast.Tuple)):return tuple(rec(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*rec(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=rec(n.right);need(d!=0,'zero divisor');return rec(n.left)/d
        raise ValueError('numeric syntax')
    return rec(ast.parse(s.rsplit('=',1)[-1].strip(),mode='eval').body)
class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.mark={};self.inputs={};self.ids=[];self.ex=[];self.sol=[];self.worked=[];self.sources={}
    def handle_starttag(self,t,attrs):
        d=dict(attrs)
        if 'id' in d:need(d['id'] not in self.ids,'duplicate id');self.ids.append(d['id'])
        if 'worked' in d.get('class','').split():self.worked.append(d.get('id'))
        if t=='li' and d.get('id','').startswith('v14-c10-e'):self.ex.append(d['id'])
        if 'data-solution-for' in d:
            need(any(t=='details' and 'solutions' in a.get('class','').split() for t,a in self.stack),'solution enclosure');self.sol.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d.get('href')
        for typ,dest in (('data-input',self.inputs),('data-calc',self.mark)):
            if typ in d:
                k=d[typ];need(k not in dest,'duplicate numeric marker');dest[k]='';self.active.append((dest,k,len(self.stack)))
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,d))
    def handle_data(self,s):
        for dest,k,n in self.active:dest[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'unbalanced markup');self.stack.pop();self.active=[a for a in self.active if a[2]<len(self.stack)]
def expectation(x,p):return sum(a*b for a,b in zip(x,p))
def probabilities(p):
    p=tuple(map(num,p));need(p and min(p)>0 and sum(p)==1,'positive exhaustive probabilities');return p
def currency(E,m,x,p):
    E=num(E);m=tuple(map(num,m));x=tuple(map(num,x));p=probabilities(p)
    need(E>0 and len(m)==len(x)==len(p) and min(m)>0 and min(x)>0,'currency domain')
    mf=tuple(a*b for a,b in zip(m,x));rd=1/expectation(m,p);rf=1/expectation(mf,p);ex=expectation(x,p);cov=expectation(mf,p)-expectation(m,p)*ex
    returns=tuple(rf*a for a in x)
    return dict(rd=rd,rf=rf,mf=mf,ex=ex,cov=cov,forward=E*rd/rf,spot=E*ex,returns=returns,premium=expectation(returns,p)-rd)
def stop(values,k):
    y0,y1,D,R,beta,nu,n0,n1,W=map(num,values);k=num(k)
    need(min(y0,y1,R,beta,nu,n0,n1)>0 and 0<=D<y0 and W>=0 and 0<=k<1,'collateral domain')
    a=y0-D;u=(y1-beta*R*a)/(R*(1+beta));cap=k*(y0+nu*a)/(R-k*nu) if R>k*nu else None;loan=min(u,cap) if cap is not None else u
    c=(a+loan,y1-R*loan);p=(nu*c[0]/n0,nu*c[1]/n1);mu=(1/c[0]-beta*R/c[1])/R;K=W+D-loan
    need(min(c)>0 and K>=0,'consumption or foreign funding infeasible')
    return dict(u=u,cap=cap,loan=loan,c=c,p=p,mu=mu,K=K,face=R*loan,net=loan-D)
def sovereign(values,menu,m,h0):
    y0,beta,yl,yh,hl,hh,pl=map(num,values);p=probabilities((pl,1-pl));m=tuple(map(num,m));menu=tuple(map(num,menu));h0=num(h0);y=(yl,yh);h=(hl,hh)
    need(y0>0 and beta>0 and 0<h0<=y0 and len(m)==2 and min(m)>0 and all(0<hh<=yy for yy,hh in zip(y,h)),'sovereign domain')
    need(menu and menu[0]==0 and tuple(sorted(set(menu)))==menu and min(menu)>=0,'finite ordered nonnegative menu including zero')
    rows=[]
    for d in menu:
        H=tuple(int(d<=yy-hh) for yy,hh in zip(y,h));q=expectation(tuple(mm*hh for mm,hh in zip(m,H)),p);c0=y0+q*d;c=tuple(yy-d if hh else loss for yy,hh,loss in zip(y,H,h));v=log(c0)+float(beta)*expectation(tuple(log(cc) for cc in c),p)
        rows.append(dict(d=d,H=H,q=q,c0=c0,c=c,v=v,proceeds=q*d))
    aut=log(h0)+float(beta)*expectation(tuple(log(a) for a in h),p);best=max(range(len(rows)),key=lambda i:(rows[i]['v'],-rows[i]['d']))
    return dict(rows=rows,aut=aut,best=best if rows[best]['v']>=aut else None,rf=1/expectation(m,p))
def mean_return(q,H,p):
    q=num(q);need(q>0,'zero-price gross return undefined');return expectation(H,p)/q

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    payload={f:(root/f).read_bytes() for f in FILES};review=json.loads(payload[FILES[3]]);sources=json.loads(payload[FILES[2]])
    for f in FILES[:3]:
        b=review['payload_bindings'][f];need(b=={'bytes':len(payload[f]),'sha256':sha256(payload[f]).hexdigest()},'author payload binding '+f)
    doc=Document();doc.feed(payload[FILES[0]].decode());need(not doc.stack,'unclosed markup')
    expected_ex=['v14-c10-e'+str(i) for i in range(1,13)]
    need(doc.ex==expected_ex and doc.sol==expected_ex and len(doc.worked)==4,'complete worked/exercise/solution pairing')
    catalogue={s['id']:s for s in sources['sources']};need(set(doc.sources)==set(catalogue),'source membership')
    for k,url in doc.sources.items():need(catalogue[k]['url']==url and catalogue[k]['checked'] and catalogue[k]['verification'],'source provenance')
    inputs={k:parsed(v) for k,v in doc.inputs.items()};shown={k:parsed(v) for k,v in doc.mark.items()};wanted={};counts={'comparisons':0,'rejected_inputs':0}
    def eq(a,b,label='identity',tol=7e-10):
        if isinstance(a,(list,tuple)) or isinstance(b,(list,tuple)):
            need(isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label,tol)
        else:
            counts['comparisons']+=1;need(isfinite(float(a)) and isfinite(float(b)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),label+': '+str((a,b)))
    def reject(fn):
        try:fn()
        except (ValueError,TypeError,ZeroDivisionError):counts['rejected_inputs']+=1;return
        raise ValueError('invalid primitive accepted')
    def out(k,v):wanted[k]=v
    beta,h0,f0,hl,hh,fl,fh,pl=inputs['sharing'];p=(pl,1-pl)
    eq((h0+f0,hl+fl,hh+fh),(2,2,2),'world endowment');arrows=tuple(beta*ps for ps in p);wealth=h0+expectation((hl,hh),arrows);q=beta*expectation((1/hl,1/hh),p)
    out('sharing-arrows',arrows);out('sharing-wealth',wealth);out('sharing-complete-return',1/sum(arrows));out('sharing-bond-price',q);out('sharing-bond-return',1/q);out('sharing-incomplete-sdfs',((beta/hl,beta/hh),(beta/fl,beta/fh)));out('sharing-gain',-float(beta)*expectation((log(hl),log(hh)),p))
    eq(wealth,1+sum(arrows),'complete budget');eq(expectation((beta/fl,beta/fh),p),q,'incomplete SDF same traded price')
    for ends in ((hl,hh),(F(7,4),F(1,4))):
        qb=beta*expectation(tuple(1/e for e in ends),p);u0=float(beta)*expectation(tuple(log(e) for e in ends),p)
        for i in range(-9,10):
            a=F(i,100);cs=(1-qb*a,ends[0]+a,ends[1]+a);need(min(cs)>0,'test feasible');u=log(cs[0])+float(beta)*expectation(tuple(log(c) for c in cs[1:]),p);need(u<=u0+1e-12,'bond global comparison');counts['comparisons']+=1
    qe=beta*expectation((F(4,7),F(4)),p);out('e2-bond-price',qe);out('e2-bond-return',1/qe);out('e2-gain',-float(beta)*expectation((log(F(7,4)),log(F(1,4))),p))
    E,ml,mh,xl,xh,pl=inputs['currency'];p=(pl,1-pl);cur=currency(E,(ml,mh),(xl,xh),p)
    for key,field in [('rd','rd'),('mf','mf'),('rf','rf'),('ex','ex'),('cov','cov'),('forward','forward'),('spot-mean','spot'),('returns','returns'),('premium','premium')]:out('currency-'+key,cur[field])
    rev=currency(E,(ml,mh),(xh,xl),p)
    for key in ('mf','rf','forward','premium'):out('e4-'+key,rev[key])
    for x in ((xl,xh),(xh,xl),(F(1),F(1))):
        c=currency(E,(ml,mh),x,p);eq(c['ex']-c['rd']/c['rf'],-c['rd']*c['cov'],'UIP covariance');eq(c['premium'],-c['rd']*c['rf']*c['cov']);eq(expectation(tuple(mm*r for mm,r in zip((ml,mh),c['returns'])),p),1,'Euler')
        for z in ((1,0),(0,1),(2,3)):
            eq(expectation(tuple(mm*E*xx*zz for mm,xx,zz in zip((ml,mh),x,z)),p)/E,expectation(tuple(mm*zz for mm,zz in zip(c['mf'],z)),p),'arbitrary foreign claim')
        eq(c['forward']/E,c['rd']/c['rf'],'covered parity')
    # Nominal-to-real conversion with distinct inflation rates and CRRA marginal utilities.
    mdreal=F(9,10);mfreal=F(6,5);inflD=F(11,10);inflF=F(21,20);X=(mfreal/inflF)/(mdreal/inflD)
    eq(X*inflF/inflD,mfreal/mdreal,'real numeraire conversion')
    vals=inputs['stop'];kb,ks=inputs['stop-kappas'];base=stop(vals,kb);stress=stop(vals,ks)
    for prefix,case in (('base',base),('stress',stress)):
        for key in ('loan','c','mu'):out('stop-'+prefix+'-'+key,case[key])
    out('stop-unconstrained',base['u']);out('stop-net-flow',stress['net']);out('stop-feedback-loss',ks*(vals[0]+base['p'][0]*vals[6])/vals[3]-stress['loan']);out('stop-real-depreciation',sqrt(base['p'][0]/stress['p'][0]));out('stop-foreign-investment',stress['K'])
    def audit_stop(v,k):
        c=stop(v,k);y0,y1,D,R,beta,nu,n0,n1,W=map(num,v);loan=c['loan'];p0,p1=c['p'];t0,t1=c['c'];A0=y0-D+p0*n0;A1=y1+p1*n1;individual_u=(A1-beta*R*A0)/(R*(1+beta));individual_cap=k*(y0+p0*n0)/R
        eq(loan,min(individual_u,individual_cap),'fixed-price individual optimum');eq(t0+p0*n0,A0+loan);eq(t1+p1*n1,A1-R*loan);eq(c['mu']*(k*(y0+p0*n0)-R*loan),0,'complementarity');need(c['mu']>=0 and R*loan<=k*(y0+p0*n0),'KKT signs')
        eq(t0+c['K'],y0+W,'date0 world goods');eq(t1+R*(W+D),y1+R*c['K'],'date1 world goods')
        u=log(t0)+float(nu)*log(n0)+float(beta)*(log(t1)+float(nu)*log(n1))
        # Vary individual loans at FIXED candidate prices and optimize both intradate allocations.
        lo=-A0;hi=min(A1/R,individual_cap)
        for j in range(1,20):
            ell=lo+(hi-lo)*F(j,20);z0=A0+ell;z1=A1-R*ell;ct0=z0/(1+nu);cn0=nu*z0/((1+nu)*p0);ct1=z1/(1+nu);cn1=nu*z1/((1+nu)*p1)
            alt=log(ct0)+float(nu)*log(cn0)+float(beta)*(log(ct1)+float(nu)*log(cn1));need(alt<=u+1e-11,'individual global utility witness');counts['comparisons']+=1
        return c
    for k in (F(0),ks,kb,F(2,5),F(4,5)):audit_stop(vals,k)
    boundary=list(vals);boundary[5]=2
    audit_stop(boundary,F(1,2));audit_stop(boundary,F(3,4))
    saving=list(vals);saving[0]=4;saving[1]=1;saving[2]=0;audit_stop(saving,F(0))
    y0,y1,D,R,beta,nu,n0,n1,W=vals;a=y0-D;M=y0+nu*a;den=R-kb*nu;dk=M*R/den**2;dD=-kb*nu/den
    out('e6-derivatives',(dk,dD,dD-1));out('e6-amplifier',R/den)
    eps=F(1,10000000);eq((stop(vals,kb+eps)['loan']-stop(vals,kb-eps)['loan'])/(2*eps),dk,'cap derivative',1e-7)
    vup=list(vals);vdn=list(vals);vup[2]+=eps;vdn[2]-=eps;eq((stop(vup,kb)['loan']-stop(vdn,kb)['loan'])/(2*eps),dD,'inherited debt derivative')
    rv=list(vals);rv[3]=F(6,5);raised=audit_stop(rv,kb)
    for suffix,key in (('unconstrained','u'),('loan','loan'),('face','face'),('consumption','c'),('foreign-capital','K')):out('e7-'+suffix,raised[key])
    zero=stop(vals,0);out('e8-zero-cap',(zero['loan'],*zero['c'],zero['net']))
    eq(raised['c'][1]+rv[3]*(W+D),F(544,95),'E7 future world total')
    for price in (base['p'][0],stress['p'][0]):
        ct=sqrt(price);cn=1/sqrt(price);eq(ct*cn,1,'unit composite');eq(ct+float(price)*cn,2*sqrt(price),'unit expenditure')
    sv=inputs['sovereign'];menu=inputs['sovereign-menu'];ms=inputs['global-sdf'];mt=inputs['global-stress-sdf'];hzero=inputs['sovereign-h0'];p=(sv[-1],1-sv[-1]);sov=sovereign(sv,menu,ms,hzero);st=sovereign(sv,menu,mt,hzero);rev=sovereign(sv,menu,ms[::-1],hzero)
    for label,case in (('sovereign',sov),('sovereign-stress',st),('e10',rev)):
        out(label+'-prices',tuple(r['q'] for r in case['rows']));out(label+'-values',tuple(r['v'] for r in case['rows']))
    out('sovereign-autarky',sov['aut']);out('sovereign-c0',tuple(r['c0'] for r in sov['rows']));out('sovereign-proceeds',sov['rows'][sov['best']]['proceeds']);out('sovereign-stress-proceeds',st['rows'][st['best']]['proceeds']);out('sovereign-stress-safe',st['rf'])
    for label,case,m in (('sovereign',sov,ms),('e10',rev,ms[::-1])):
        row=case['rows'][2];cov=row['q']-expectation(m,p)*expectation(row['H'],p);out(label+'-cov',cov);out(label+('-mean-return' if label=='sovereign' else '-return'),mean_return(row['q'],row['H'],p))
    eq((sov['best'],st['best'],rev['best']),(2,1,1),'whole-menu policies')
    for m in (ms,mt,ms[::-1],(F(1),F(1))):
        s=sovereign(sv,menu,m,hzero)
        for row in s['rows']:
            eq(row['proceeds'],expectation(tuple(mm*H*row['d'] for mm,H in zip(m,row['H'])),p),'creditor discounted receipts')
            for y,h,H,c in zip(sv[2:4],sv[4:6],row['H'],row['c']):
                eq(c+H*row['d']+(1-H)*(y-h),y,'terminal sovereign goods')
                need((H and y-row['d']>=h) or (not H and y-row['d']<h),'terminal best response including ties');counts['comparisons']+=1
            if row['q']>0:eq(expectation(tuple(mm*H/row['q'] for mm,H in zip(m,row['H'])),p),1,'SDF-priced return')
    eq(sov['rows'][1]['H'],(1,1),'threshold tie repays');eq(sov['rows'][3]['H'],(0,0),'zero-price menu')
    aold=F(-2);R0=F(11,10);asset=5-4+R0*aold;c1=5+asset;out('e1-assets',asset);out('e1-ca0',asset-aold);out('e1-c1',c1);eq((4-5+c1-5)/R0,aold,'external PV identity');eq(asset-aold,1+(R0-1)*aold,'CA interest')
    out('e11-equity',(150-2*40,150-F(5,2)*40,(F(5,2)-2)*40));eq((F(5,2)-2)*(40-40),0,'matched currency hedge')
    need(set(wanted)==set(shown),'exhaustive displayed output coverage: '+str(set(wanted)^set(shown)))
    for k,v in wanted.items():eq(shown[k],v,'display '+k)
    need(set(inputs)=={'sharing','currency','stop','stop-kappas','sovereign','sovereign-menu','sovereign-h0','global-sdf','global-stress-sdf'},'all displayed primitive groups')
    for bad in (True,float('nan'),float('inf')):reject(lambda bad=bad:num(bad))
    reject(lambda:parsed('1/0'));reject(lambda:parsed('__import__("os")'))
    for pp in ((0,1),(F(1,2),F(1,3))):reject(lambda pp=pp:probabilities(pp))
    reject(lambda:currency(0,(1,1),(1,1),(F(1,2),F(1,2))))
    reject(lambda:currency(1,(0,1),(1,1),(F(1,2),F(1,2))))
    reject(lambda:currency(1,(1,1),(-1,1),(F(1,2),F(1,2))))
    for idx,value in ((0,0),(2,1),(3,0),(4,0),(5,0),(6,0),(8,-1)):
        bad=list(vals);bad[idx]=value;reject(lambda bad=bad:stop(bad,kb))
    for k in (-1,1):reject(lambda k=k:stop(vals,k))
    bad=list(vals);bad[2]=0;bad[8]=0;reject(lambda:stop(bad,kb))
    reject(lambda:sovereign(sv,menu,(0,1),hzero));reject(lambda:sovereign(sv,(F(1,5),),ms,hzero));reject(lambda:sovereign(sv,menu,ms,0));reject(lambda:mean_return(0,(0,0),p))
    for f in FILES:need((root/f).read_bytes()==payload[f],'payload mutation')
    return {'chapter':'v14-c10','status':'passed','worked_cases':4,'solutions':12,'input_groups':len(inputs),'displayed_outputs':len(shown),**counts,'runtime_files':4,'open_issues':[]}
if __name__=='__main__':check()
