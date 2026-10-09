"""Separate bounded proof-support and finite-contract audit of V12-c02.

No author numerical helper is an oracle. General probability proofs are read
and assessed separately in the peer record; finite cases cannot prove them.
Public import/check() and the default CLI are quiet and read-only.
"""
import contextlib
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FILES=("content/chapters/v12-c02.html","scripts/check_v12_c02.py",
       "content/reviews/v12-c02-sources.json","content/reviews/v12-c02-author.json",
       "scripts/check_v12_c02_peer.py","content/reviews/v12-c02-peer.json")
SOURCES={"v12-c02-mit-linear2017","v12-c02-cameron-miller2015","v12-c02-mit-hac2017"}


def require(condition,label):
    if not condition:raise ValueError("v12-c02 peer: "+label)


def strict(text):
    def pairs(items):
        out={}
        for key,value in items:
            require(key not in out,"duplicate JSON key");out[key]=value
        return out
    def decimal(token):
        value=float(token);require(math.isfinite(value),"nonfinite JSON number");return value
    def constant(token):raise ValueError("nonfinite JSON constant "+token)
    return json.loads(text,object_pairs_hook=pairs,parse_float=decimal,parse_constant=constant)


class Audit:
    def __init__(self):self.count=0;self.rejections=0;self.printed=0
    def eq(self,actual,expected,label):
        self.count+=1
        if type(expected) is bool:require(type(actual) is bool and actual==expected,label)
        else:require(actual==expected,label+": "+repr(actual)+" != "+repr(expected))
    def reject(self,call,label):
        self.count+=1
        try:call()
        except ValueError:self.rejections+=1
        else:raise ValueError("missing rejection: "+label)


def compact(text):return "".join(text.split()).replace("−","-")


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.links=[];self.sources=[];self.headings=[]
        self.prompts={};self.answers={};self.active=None;self.text=[];self.worked=0
        self.lists=[];self.details=[];self.reader_prompts=0;self.reader_solutions=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs);classes=d.get('class','').split()
        if 'id' in d:self.ids.append(d['id'])
        if tag=='a':self.links.append(d.get('href',''))
        if 'data-source' in d:self.sources.append(d['data-source'])
        if tag in ('h1','h2','h3','h4'):self.headings.append(tag)
        if 'worked' in classes:self.worked+=1
        if tag=='ol':self.lists.append('exercises' in classes)
        if tag=='details':self.details.append('solutions' in classes)
        if tag=='li':
            require(self.active is None,'non-nested prompt and answer')
            if self.lists and self.lists[-1]:
                self.reader_prompts+=1;key=d.get('id')
                require(key and key not in self.prompts,'unique exact exercise ID')
                self.prompts[key]='';self.active=(self.prompts,key)
            if any(self.details):
                self.reader_solutions+=1;key=d.get('data-solution-for')
                require(key and key not in self.answers,'unique matched solution')
                self.answers[key]='';self.active=(self.answers,key)
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append(tag)
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1]==tag,'balanced markup '+tag);self.stack.pop()
        if tag=='ol':self.lists.pop()
        if tag=='details':self.details.pop()
        if tag=='li':self.active=None
    def handle_data(self,text):
        self.text.append(text)
        if self.active is not None:
            d,key=self.active;d[key]+=text


def transpose(a):return [list(col) for col in zip(*a)]


def multiply(a,b):
    require(bool(a) and bool(b) and len(a[0])==len(b),'matrix product dimensions')
    return [[sum(F(x)*F(y) for x,y in zip(row,col)) for col in transpose(b)] for row in a]


def identity(n):return [[F(int(i==j)) for j in range(n)] for i in range(n)]


def difference(a,b):return [[x-y for x,y in zip(r,s)] for r,s in zip(a,b)]


def determinant(a):
    require(1<=len(a)<=3 and all(len(r)==len(a) for r in a),'bounded square determinant')
    if len(a)==1:return F(a[0][0])
    return sum((-1)**j*F(a[0][j])*determinant([r[:j]+r[j+1:] for r in a[1:]]) for j in range(len(a)))


def inverse(a):
    """Small exact adjugate inverse, independent of author elimination code."""
    d=determinant(a);require(d!=0,'singular Gram')
    n=len(a)
    if n==1:return [[1/d]]
    cofactors=[[(-1)**(i+j)*determinant([row[:j]+row[j+1:] for row in a[:i]+a[i+1:]])
                for j in range(n)] for i in range(n)]
    return [[x/d for x in row] for row in transpose(cofactors)]


def regression(z,y,weights=None):
    require(len(z)==len(y)>1,'scalar regression data')
    weights=[F(1)]*len(z) if weights is None else list(map(F,weights))
    require(len(weights)==len(z) and min(weights)>0,'positive complete weights')
    sw=sum(weights);sx=sum(w*x for w,x in zip(weights,z));sy=sum(w*v for w,v in zip(weights,y))
    sxx=sum(w*x*x for w,x in zip(weights,z));sxy=sum(w*x*v for w,x,v in zip(weights,z,y))
    d=sw*sxx-sx*sx;require(d>0,'nonconstant regressor')
    beta=[(sxx*sy-sx*sxy)/d,(sw*sxy-sx*sy)/d]
    return beta,[F(v)-beta[0]-beta[1]*x for x,v in zip(z,y)]


def hc(z,y,power=0):
    require(type(power) is int and power in (0,1,2),'HC residual divisor power')
    beta,residual=regression(z,y);n=len(z);x=[[F(1),F(v)] for v in z]
    operator=multiply(inverse(multiply(transpose(x),x)),transpose(x))
    leverage=[sum(x[i][j]*operator[j][i] for j in range(2)) for i in range(n)]
    if power:require(n>2 and max(leverage)<1,'HC2/HC3 leverage domain')
    covariance=[[sum(operator[i][t]*operator[j][t]*residual[t]**2/(1-leverage[t])**power
                     for t in range(n)) for j in range(2)] for i in range(2)]
    return beta,residual,leverage,covariance


def kernel_covariance(scores,lag):
    """All-pairs triangular kernel, rather than author lag-sum implementation."""
    n=len(scores);p=len(scores[0])
    require(type(lag) is int and 0<=lag<n,'bounded integer bandwidth')
    kernel=[[max(F(),1-F(abs(t-s),lag+1)) for s in range(n)] for t in range(n)]
    covariance=[[sum(F(scores[t][i])*scores[s][j]*kernel[t][s] for t in range(n) for s in range(n))/n
                 for j in range(p)] for i in range(p)]
    return covariance,kernel


def derivative(poly):return [i*poly[i] for i in range(1,len(poly))]


def evaluate(poly,x):return sum(c*x**i for i,c in enumerate(poly))


def numerical(a,page):
    body=compact(' '.join(page.text))
    def shown(number,*values):
        answer=compact(page.answers['v12-c02-e'+str(number)])
        for value in values:
            a.eq(compact(str(value)) in answer,True,'paired solution '+str(number)+' '+str(value));a.printed+=1
    def present(*values):
        for value in values:a.eq(compact(str(value)) in body,True,'worked/retention value '+str(value))

    z=(-1,0,1);y=(2,2,4)
    beta,residual=regression(z,y);weighted,rw=regression(z,y,(1,4,1))
    a.eq((beta,weighted),([F(8,3),1],[F(7,3),1]),'different projection targets')
    loss=sum(e*e for e in residual)/3;changed=sum(e*e for e in rw)/3
    a.eq((loss,changed,changed-loss),(F(2,9),F(1,3),F(1,9)),'unweighted loss decomposition')
    a.eq((sum(residual),sum(x*e for x,e in zip(z,residual))),(0,0),'unweighted normal equations')
    a.eq((sum(w*e for w,e in zip((1,4,1),rw)),sum(w*x*e for w,x,e in zip((1,4,1),z,rw))),(0,0),'weighted normal equations')
    a.eq(any(e for e in residual),True,'conditional mean residual is not zero')
    # Distinct no-intercept law: x=(1,3), y=(2,2), each with probability half.
    slope=F(2+6,1+9);errors=[2-slope*x for x in (1,3)]
    cross=sum(x*e for x,e in zip((1,3),errors))/2;mean_error=sum(errors)/2
    a.eq((slope,cross,mean_error,cross-2*mean_error),(F(4,5),0,F(2,5),-F(4,5)),'cross moment is not covariance')
    shown(1,*beta,*weighted,loss,changed,changed-loss,'conditional mean','counterfactual')

    # Partial regression on a different finite design with nonorthogonal columns.
    t=(-2,0,1,3);w=(1,0,2,1);outcome=(4,-1,3,7)
    nuisance=[[F(1),F(v)] for v in t];full=[r+[F(s)] for r,s in zip(nuisance,w)]
    wr=regression(t,w)[1];yr=regression(t,outcome)[1]
    partial=sum(x*y for x,y in zip(wr,yr))/sum(x*x for x in wr)
    full_beta=multiply(inverse(multiply(transpose(full),full)),multiply(transpose(full),[[F(v)] for v in outcome]))
    a.eq(partial,full_beta[2][0],'FWL full versus residual regression')
    h=multiply(multiply(full,inverse(multiply(transpose(full),full))),transpose(full))
    residual_projector=difference(identity(4),h)
    a.eq(multiply(h,h),h,'fitted projector idempotent')
    a.eq(multiply(residual_projector,residual_projector),residual_projector,'residual projector idempotent')
    a.eq(multiply(h,residual_projector),[[0]*4 for _ in range(4)],'Gaussian coordinate subspaces orthogonal')
    a.eq(sum(residual_projector[i][i] for i in range(4)),1,'Gaussian residual degrees of freedom')

    variances=(F(1),F(4),F(9));readings=(2,4,8)
    precision=[1/v for v in variances];total_precision=sum(precision)
    weights=([F(1,3)]*3,[v/total_precision for v in precision],[v/sum(variances) for v in variances])
    estimates=[];covariances=[]
    for operator in weights:
        a.eq(sum(operator),1,'device weights are unbiased')
        estimates.append(sum(w*y for w,y in zip(operator,readings)))
        covariances.append(sum(w*w*v for w,v in zip(operator,variances)))
    a.eq(estimates,[F(14,3),F(20,7),F(45,7)],'device estimates')
    a.eq(covariances,[F(14,9),F(36,49),F(397,98)],'device true variances')
    a.eq(covariances[0]-covariances[1],F(362,441),'OLS GLS precision gap')
    a.eq(covariances[2]>covariances[0],True,'wrong weights can be worse')
    # Correlated true errors: exact comparator with contrast equality but a
    # strictly larger covariance for other contrasts, not just an intercept.
    x=[[F(1),F(-1)],[F(1),F(0)],[F(1),F(2)]]
    sigma=[[F(2),F(1),F(0)],[F(1),F(3),F(0)],[F(0),F(0),F(1)]]
    precision_matrix=inverse(sigma);xtw=multiply(transpose(x),precision_matrix)
    ag=multiply(inverse(multiply(xtw,x)),xtw)
    delta=[[F(k,10) for k in (2,-3,1)],[F(k,5) for k in (2,-3,1)]]
    alternative=[[u+v for u,v in zip(r,s)] for r,s in zip(ag,delta)]
    a.eq(multiply(ag,x),identity(2),'GLS unbiasedness')
    a.eq(multiply(alternative,x),identity(2),'comparator unbiasedness')
    cg=multiply(multiply(ag,sigma),transpose(ag));ca=multiply(multiply(alternative,sigma),transpose(alternative))
    gap=multiply(multiply(delta,sigma),transpose(delta))
    a.eq(difference(ca,cg),gap,'true-covariance BLUE difference')
    a.eq(multiply(multiply([[2,-1]],gap),[[2],[-1]]),[[0]],'contrast equality with nonzero estimator difference')
    a.eq(gap[0][0]>0,True,'another contrast strictly loses efficiency')
    shown(2,*estimates,*covariances,F(362,441),'D′c=0','need not vanish')

    z=(-2,-1,1,2);y=(0,2,2,8)
    beta,residual,leverage,hc0=hc(z,y);hc2=hc(z,y,1)[3];hc3=hc(z,y,2)[3]
    a.eq(beta,[3,F(8,5)],'four-row OLS')
    a.eq(residual,[F(k,5) for k in (1,3,-13,9)],'four-row residuals')
    sse=sum(e*e for e in residual)
    a.eq(sse,F(52,5),'residual squared norm')
    a.eq(leverage,[F(k,20) for k in (13,7,7,13)],'every leverage')
    a.eq(hc0,[[F(13,20),F(8,25)],[F(8,25),F(253,1250)]],'HC0 influence outer products')
    a.eq(hc2[1][1],F(1102,2275),'HC2 corrected slope variance')
    a.eq(hc3[1][1]>=hc2[1][1],True,'larger residual divisor correction on this design')
    scaled=hc(tuple(10*x for x in z),y)
    a.eq(scaled[0],[3,F(4,25)],'slope unit change')
    a.eq(scaled[1],residual,'unit change preserves fit')
    a.eq(scaled[3],[[F(13,20),F(4,125)],[F(4,125),F(253,125000)]],'covariance unit change')
    singleton=hc((0,0,1),(0,2,9))
    a.eq(singleton[2],[F(1,2),F(1,2),1],'unit leverage boundary')
    a.eq(singleton[1][2],0,'unit leverage zero residual')
    shown(3,sse,F(13,20),F(8,25),F(253,1250),hc2[1][1],F(4,25),F(253,125000),F(4,125))
    shown(4,'integrable','1/2,1/2,1','undefined')

    covers=F()
    for pair in itertools.product((-1,1),repeat=2):
        mean=F(sum(pair),2);squared=sum((F(x)-mean)**2 for x in pair)
        # These events establish the result for every finite positive k.
        a.eq((mean==0,squared==2),(pair[0]!=pair[1],pair[0]!=pair[1]),'two-sign interval event')
        covers+=F(int(mean==0),4)
    a.eq(covers,F(1,2),'non-Gaussian homoskedastic coverage')
    shown(5,covers,'independence','t²','non-Gaussian')

    for probability,magnitudes,expected in ((F(1,2),(1,3),(5,F(9,5))),
                                            (F(1,4),(2,4),(13,F(64,7)))):
        pv=(probability,1-probability)
        ols_variance=sum(p*mag*mag for p,mag in zip(pv,magnitudes))
        gram=sum(p/F(mag*mag) for p,mag in zip(pv,magnitudes))
        score_variance=sum(p/F(mag*mag) for p,mag in zip(pv,magnitudes))
        a.eq((ols_variance,score_variance/gram**2),expected,'independent finite-group influence variance')
        a.eq(sum(p*sign/F(mag) for p,mag in zip(pv,magnitudes) for sign in (-1,1))/2,0,'group-weighted score centered')
    # A possible four-observation sample proves finite feasible and oracle
    # estimates need not coincide, despite the valid first-order theorem.
    sample=(-1,1,3,3);center=F(sum(sample),4)
    va=sum((F(y)-center)**2 for y in sample[:2])/2;vb=sum((F(y)-center)**2 for y in sample[2:])/2
    feasible=(sum(sample[:2])/va+sum(sample[2:])/vb)/(2/va+2/vb)
    oracle=(sum(sample[:2])+F(sum(sample[2:]),9))/(2+F(2,9))
    a.eq((va,vb,feasible,oracle),(F(13,4),F(9,4),F(39,22),F(3,10)),'finite feasible versus oracle weighting')
    # Mean misspecification: category means zero and two with residual error
    # variances one and nine. Consistent OLS-residual weights target 1/3.
    a.eq((F(0+2,2),F(2,9)/(1+F(1,9)),F(2,10)/(F(1,2)+F(1,10))),
         (1,F(1,5),F(1,3)),'different misspecified weighting targets')
    for t in (2,4):
        weight_error=F(1,t);weighted_target=2*(1+weight_error)/(2+weight_error)
        a.eq(t*t*(weighted_target-1),F(t*t,2*t+1),'consistent weights need not have negligible root-n effect')
    shown(6,13,F(7,64),F(64,7),'centered','Mere weight consistency')

    # Collapse duplicate two-person shock realizations into six distinct team
    # means, then enumerate the complete 36-outcome two-team distribution.
    team=((F(-4),F(1,8)),(F(-3),F(1,4)),(F(-2),F(1,8)),
          (F(2),F(1,8)),(F(3),F(1,4)),(F(4),F(1,8)))
    a.eq(sum(p for y,p in team),1,'six-state team law')
    a.eq(sum(p*y*y for y,p in team),F(19,2),'team mean variance')
    mean_variance=cr_mean=F()
    for (u,pu),(v,pv) in itertools.product(team,repeat=2):
        average=(u+v)/2;prob=pu*pv
        mean_variance+=prob*average*average
        cr_mean+=prob*((u-average)**2+(v-average)**2)/4
    a.eq((mean_variance,cr_mean,2*cr_mean),(F(19,4),F(19,8),F(19,4)),'independent-cluster normalization and correction')
    a.eq((40-4*mean_variance)/16,F(21,16),'row HC0 expectation by covariance trace')
    observed=((4,2),(-2,-4),(4,4),(-4,-4))
    cr=sum(F(sum(row)**2,64) for row in observed);hh=sum(F(x*x,64) for row in observed for x in row)
    a.eq((cr,hh),(F(25,8),F(13,8)),'observed cluster and row meats')
    a.eq(((9+F(1,2))/20,(9+F(1,4))/10,F(10,40)),(F(19,40),F(37,40),F(1,4)),'equal row counts with different independent shocks')
    a.eq((F(12,4),F(4,2),F(9,4),F(4)),(3,2,F(9,4),4),'variable-size cluster targets and influence variances')
    for sign in (-1,1):a.eq(min(abs(3*sign+v) for v in (-1,1)),2,'one-team error bounded away from zero')
    shown(7,F(19,40),F(37,40),F(1,4),cr,hh,'unbiased','does not establish')
    shown(8,3,2,F(9,4),'variance 4','≥2','outside the theorem')

    serial={}
    for rho in (F(1,2),-F(1,2),F(-1),F(1,3)):
        gamma0=1+rho*rho;gamma1=rho;longrun=(1+rho)**2
        a.eq(gamma0+2*gamma1,longrun,'impulse covariance long-run identity')
        # Each independent innovation has its own coefficient in the mean.
        n=20;coefficients=[rho]+[1+rho]*(n-1)+[F(1)]
        finite=sum(c*c for c in coefficients)/n**2
        a.eq(finite,(n*gamma0+2*(n-1)*gamma1)/n**2,'innovation coefficients versus dated covariance sum')
        serial[rho]=(gamma0,gamma1,longrun,finite,gamma0+gamma1)
    a.eq(serial[F(1,2)],(F(5,4),F(1,2),F(9,4),F(11,100),F(7,4)),'positive serial covariance')
    a.eq(serial[-F(1,2)],(F(5,4),-F(1,2),F(1,4),F(3,200),F(3,4)),'negative serial covariance')
    a.eq(serial[F(-1)][2:4],(0,F(1,200)),'zero long-run variance still has endpoint risk')
    endpoint_error=[F(last-first,20) for first,last in itertools.product((-1,1),repeat=2)]
    a.eq(sum(x*x for x in endpoint_error)/4,F(2,400),'exact differenced-sign error variance')
    a.eq(sum(x!=0 for x in endpoint_error),2,'finite error is nonzero with probability half')
    shown(9,'2/n²','bₙ','deterministic','Taylor','CDF')
    shown(11,*serial[-F(1,2)],F(1,16),'too large','new dependence CLT')

    # Kernel entries count intersections of observation-window membership sets.
    vector_cases=0
    for scores in (((1,2),(-2,1),(1,-3)),((0,1),(2,-1),(-1,0),(1,2))):
        n=len(scores)
        for lag in (0,1,2):
            covariance,kernel=kernel_covariance(scores,lag)
            windows=[set(range(t,t+lag+1)) for t in range(n)]
            overlap=[[F(len(windows[t]&windows[s]),lag+1) for s in range(n)] for t in range(n)]
            a.eq(kernel,overlap,'all edge-window multiplicities')
            sums=[[sum(scores[t][k] for t in range(n) if j in windows[t]) for k in range(2)] for j in range(n+lag)]
            via_windows=[[sum(F(h[i]*h[j],n*(lag+1)) for h in sums) for j in range(2)] for i in range(2)]
            a.eq(covariance,via_windows,'vector Bartlett kernel equals Gram of windows')
            a.eq(covariance[0][0]>=0 and covariance[1][1]>=0 and determinant(covariance)>=0,True,'complete two-dimensional PSD test')
            vector_cases+=1
    residual=(1,-2,1);n=3
    gammas=[sum(F(residual[t]*residual[t-lag],n) for t in range(lag,n)) for lag in range(3)]
    untapered=gammas[0]+2*gammas[1]
    a.eq(gammas,[F(2),-F(4,3),F(1,3)],'residual lag moments')
    a.eq(untapered,-F(2,3),'negative untapered covariance')
    b1=kernel_covariance([[x] for x in residual],1)[0][0][0]
    b2=kernel_covariance([[x] for x in residual],2)[0][0][0]
    a.eq((b1,b2),(F(2,3),F(4,9)),'finite Bartlett positives')
    shown(10,*gammas,untapered,b1,b2,'0<a<1/3','does not prove inconsistency')

    # The C3 CDF transition is checked symbolically, not at a loose point grid.
    polynomial=[F(x) for x in (1,0,0,0,-35,84,-70,20)]
    a.eq((evaluate(polynomial,0),evaluate(polynomial,1)),(1,0),'smooth CDF transition endpoints')
    first=derivative(polynomial)
    a.eq(first,[0,0,0,-140,420,-420,140],'derivative is -140*s^3*(1-s)^3')
    for order in range(1,4):
        polynomial=derivative(polynomial)
        a.eq((evaluate(polynomial,0),evaluate(polynomial,1)),(0,0),'C3 extension derivative '+str(order))
    for n,ell,gap in ((125,5,2),(216,6,1)):
        blocks=[];start=0
        while start+ell<=n:
            blocks.append(set(range(start,start+ell)));start+=ell+gap
        kept=set().union(*blocks);omitted=set(range(n))-kept
        a.eq(len(kept)+len(omitted),n,'block partition conserves observation indices')
        a.eq(len(omitted)<=F(gap*n,ell)+ell+gap,True,'omitted-count deterministic bound')
        a.eq(all(min(after)-max(before)>gap for before,after in zip(blocks,blocks[1:])),True,'past/future separation for independent blocks')
    for t in (2,3):
        n=t**12;lag=t**3
        a.eq((F(lag**3,n),F(lag,t**6)),(F(1,t**3),F(1,t**3)),'concrete sufficient bandwidth rates')
        a.eq(F((t**4)**3,n),1,'boundary-rate bound is inconclusive')
    present('bₙ=Bℓₙ/√n','q′=−140s³(1−s)³','L³/n→0','same probability limit')
    shown(12,'12 points','six explicit distinctions','two changes','score centering','eight firms','selection')
    a.eq((F(5,4),F(4,5)**2+4*F(1,5)**2),(F(5,4),F(4,5)),'retention device variances')
    a.eq(serial[F(1,3)][:3]+(serial[F(1,3)][4],),(F(10,9),F(1,3),F(16,9),F(13,9)),'retention serial transfer')
    present('5/4','4/5','10/9','16/9','13/9','positive limiting variance','changing weights')
    for call,label in ((lambda:inverse([[1,1],[1,1]]),'singular matrix'),
                       (lambda:regression((1,1),(0,1)),'rank failure'),
                       (lambda:hc((0,0,1),(0,2,9),1),'HC2 unit leverage'),
                       (lambda:hc((0,0,1),(0,2,9),2),'HC3 unit leverage'),
                       (lambda:kernel_covariance([[1],[-1]],True),'boolean bandwidth'),
                       (lambda:kernel_covariance([[1],[-1]],2),'excess bandwidth')):
        a.reject(call,label)
    return {'paired_numeric_and_scope_anchors':a.printed,'six_state_team_pairs':36,
            'purposeful_vector_Bartlett_cases':vector_cases,'FWL_coefficient':str(partial),
            'finite_feasible_weight_estimate':str(feasible),'finite_oracle_estimate':str(oracle)}


def hashrow(root,path):
    data=(root/path).read_bytes();return {'path':path,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def check(root=None):
    root=Path(root) if root is not None else ROOT;a=Audit();page=Reader()
    page.feed((root/FILES[0]).read_text(encoding='utf-8'));page.close()
    a.eq(page.stack,[],'balanced complete fragment')
    a.eq((page.worked,page.reader_prompts,page.reader_solutions),(6,12,12),'actual reader markers')
    expected={'v12-c02-e'+str(i) for i in range(1,13)}
    a.eq(set(page.prompts),expected,'all twelve exact prompts')
    a.eq(set(page.answers),expected,'all twelve paired answers')
    a.eq(len(page.ids),len(set(page.ids)),'unique IDs')
    a.eq(page.headings.count('h1'),0,'no second book title')
    a.eq(set(page.sources),SOURCES,'three scoped primary citations')
    for href in page.links:
        a.eq(bool(re.fullmatch(r'v\d\d-c\d\d\.html',href)) or href.startswith('sources.html#'),True,'flat reader route')
    evidence=numerical(a,page)
    source=strict((root/FILES[2]).read_text(encoding='utf-8'))
    a.eq({row['id'] for row in source['sources']},SOURCES,'source record identity')
    a.eq(len(source['sources']),3,'exact source scope count')
    a.eq('not inspected' in source['unavailable_lead']['observed'],True,'unavailable primary body not claimed read')
    author=strict((root/FILES[3]).read_text(encoding='utf-8'))
    a.eq(set(author['payloads']),set(FILES[:3]),'three nonself author bindings')
    for path,binding in author['payloads'].items():
        row=hashrow(root,path);a.eq(binding,{k:v for k,v in row.items() if k!='path'},'author payload unchanged')
    json_rejections=0
    for bad in ('{"a":1,"a":2}','NaN','Infinity','-Infinity','1e10000','{}{}'):
        try:strict(bad)
        except ValueError:json_rejections+=1
        else:raise ValueError('permissive JSON parser')
    before={path:(root/path).read_bytes() for path in FILES};old=sys.dont_write_bytecode;sys.dont_write_bytecode=True
    try:
        with contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()) as err:
            spec=importlib.util.spec_from_file_location('c02_author_integration',root/FILES[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            author_summary=module.check()
        a.eq(out.getvalue()+err.getvalue(),'','quiet author import/check integration')
        a.eq(strict(json.dumps(author_summary,allow_nan=False)),author_summary,'strict author result')
        a.eq(author_summary['comparisons'],536,'separately labeled author integration')
    finally:sys.dont_write_bytecode=old
    for path,data in before.items():a.eq((root/path).read_bytes(),data,'integration no mutation')
    review=strict((root/FILES[5]).read_text(encoding='utf-8'))
    a.eq(len(review['reviewed_hashes']),5,'four authors plus peer checker bound')
    a.eq({row['path'] for row in review['reviewed_hashes']},set(FILES[:5]),'exact nonself peer membership')
    for row in review['reviewed_hashes']:a.eq(row,hashrow(root,row['path']),'peer final binding')
    summary={'chapter':'v12-c02','review':'separate peer','status':'passed','comparisons':a.count,
             'worked_cases':6,'exact_prompts_and_solutions':12,'primary_scopes':3,
             'independent_domain_rejections':a.rejections,'strict_JSON_rejections':json_rejections,
             'finite_evidence':evidence,'author_comparisons_integration_only':author_summary['comparisons'],
             'nonself_bindings':5,'limits':'Finite exact evidence plus separate analytic proof review; no general mixing/high-dimensional/uniform or exact robust coverage, rendered UI or human certification.'}
    strict(json.dumps(summary,allow_nan=False));return summary


def portable():
    with tempfile.TemporaryDirectory(prefix='v12-c02-peer-') as temporary:
        root=Path(temporary)/'book'
        for path in FILES:
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/path,dest)
        before={p:hashrow(root,p) for p in FILES};results=[]
        for flags in ([],['-O']):
            code=("import sys,importlib.util,contextlib,io,json;sys.dont_write_bytecode=True;"
                  "s=importlib.util.spec_from_file_location('peer',"+repr(str(root/FILES[4]))+");m=importlib.util.module_from_spec(s)\n"
                  "with contextlib.redirect_stdout(io.StringIO()) as o,contextlib.redirect_stderr(io.StringIO()) as e:\n s.loader.exec_module(m);r=m.check()\n"
                  "if o.getvalue() or e.getvalue():raise ValueError('nonquiet API')\n"
                  "print(json.dumps(r,allow_nan=False,sort_keys=True))")
            done=subprocess.run([sys.executable]+flags+['-c',code],cwd='/',capture_output=True,text=True,timeout=30,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            require(not done.returncode and not done.stderr,'isolated API failure '+done.stderr)
            results.append(strict(done.stdout))
        require(results[0]==results[1],'isolated normal/optimized mismatch')
        require({p:hashrow(root,p) for p in FILES}==before,'isolated payload mutation')
        require({str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==set(FILES),'exact six-file membership')
        return {'status':'passed','files':6,'cwd':'/','normal_and_optimized':True,'no_mutation':True,'summary':results[0]}


if __name__=='__main__':check()
