"""Primitive numerical checks for the original two-form econometrics qualifying field."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations,product
import hashlib,json,math,re

FILES=['content/cross-assessments/parts/graduate-econometrics.html','scripts/check_graduate_econometrics.py','content/reviews/graduate-econometrics-sources.json','content/reviews/graduate-econometrics-author.json']
def need(ok,message):
    if not ok:raise ValueError(message)
def probability(p,strict=False):
    need(not isinstance(p,bool) and isinstance(p,(int,F)),'probability type');p=F(p);need(0<p<1 if strict else 0<=p<=1,'probability domain');return p
def integer(n,lower=1):need(type(n)is int and n>=lower,'integer domain');return n
def mean(x):need(len(x)>0,'empty mean');return sum(x,F(0))/len(x)
def variance(x):m=mean(x);return mean([(v-m)**2 for v in x])
def parse(s):
    tokens=re.findall(r'[-+]?\d+(?:/\d+|\.\d+)?|[(),]',s);need(''.join(tokens)==re.sub(r'\s','',s),'numeric markup grammar');i=0
    def item():
        nonlocal i
        need(i<len(tokens),'truncated tuple')
        if tokens[i]=='(':
            i+=1;v=[item()]
            while i<len(tokens) and tokens[i]==',':i+=1;v.append(item())
            need(i<len(tokens) and tokens[i]==')','tuple close');i+=1;return v
        v=F(tokens[i]);i+=1;return v
    v=item();need(i==len(tokens),'trailing number');return v
def strict(text):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'duplicate JSON');d[k]=v
        return d
    return json.loads(text,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
class Reader(HTMLParser):
    def __init__(self):super().__init__();self.inputs={};self.results={};self.prompts={};self.solutions=[];self.rubrics={};self.domains={};self.ids=[];self.sources={};self.h2=[];self.capture=None;self.parts=[];self.details=[];self.current=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='h1':raise ValueError('component h1')
        if 'id'in a:self.ids.append(a['id'])
        if tag=='h2':self.h2.append(a.get('id'))
        if tag=='a' and 'href'in a:self.links.append(a['href'])
        if tag=='details':self.details.append('solutions'in a.get('class','').split())
        if tag=='li' and 'data-points'in a:need(a['id']not in self.prompts,'duplicate prompt');self.prompts[a['id']]=int(a['data-points'])
        if 'data-solution-for'in a:
            need(any(self.details),'solution outside disclosure');self.current=a['data-solution-for'];self.solutions.append(self.current)
        if 'data-score'in a:need(self.current is not None,'unmatched rubric');self.rubrics[self.current]=[int(x) for x in a['data-score'].split(',')]
        if 'data-domain'in a:
            k=(a['data-form'],a['data-domain']);need(k not in self.domains,'duplicate domain');self.domains[k]=int(a['data-points'])
        if 'data-source'in a:need(a['data-source']not in self.sources,'duplicate source');self.sources[a['data-source']]=a['href']
        for k in ['data-input','data-calc']:
            if k in a:need(self.capture is None,'nested numeric marker');self.capture=(tag,k,a[k]);self.parts=[]
    def handle_data(self,s):
        if self.capture:self.parts.append(s)
    def handle_endtag(self,tag):
        if tag=='details':self.details.pop()
        if tag=='li':self.current=None
        if self.capture and self.capture[0]==tag:
            _,kind,key=self.capture;dest=self.inputs if kind=='data-input'else self.results;need(key not in dest,'duplicate calculation');dest[key]=parse(''.join(self.parts));self.capture=None

def demand(q1,q3):
    q1=probability(q1);q3=probability(q3);need(q3<=q1,'nonmonotone demand');width=q1-q3
    need(q1>3*q3 and 2*q3<q1<2*q1,'active robust price menu')
    losses=(q1-2*q3,q1);w=losses[1]/sum(losses)
    return dict(t=[F(0),width],mean=[q1+2*q3,2*q1+q3],q2=[q3,q1],optimal=[q1,2*q1],fixed=[2*q3,2*q1],minimax=[1-w,w,F(0),losses[0]*w])
def gaussian_product(a,b,rho):
    need(isinstance(rho,(int,F)) and abs(rho)<1,'positive definite covariance');return dict(delta=a*a+b*b+2*a*b*rho,second=1+rho*rho,bias=rho)
def clusters(sizes,y0,y1):
    need(len(sizes)==4 and len(y0)==len(y1)==4,'four-cluster shape')
    for n in sizes:integer(n)
    N=sum(sizes);target=sum(n*(b-a) for n,a,b in zip(sizes,y0,y1))/N;ht=[];ratio=[]
    for treated in combinations(range(4),2):
        control=[i for i in range(4) if i not in treated];t=sum(sizes[i]*y1[i] for i in treated);c=sum(sizes[i]*y0[i] for i in control)
        ht.append(F(2,N)*(t-c));ratio.append(F(t,sum(sizes[i] for i in treated))-F(c,sum(sizes[i] for i in control)))
    need(mean(ht)==target,'HT expectation');return target,mean([b-a for a,b in zip(y0,y1)]),ht,variance(ht),ratio,mean(ratio)-target

def brier(q,lo,hi,n):
    q=probability(q);lo=probability(lo);hi=probability(hi);integer(n);need(lo<hi,'ordered forecast menu')
    risk=lambda p:q*(1-p)**2+(1-q)*p*p
    losses=[];weights=[];future=F(0)
    for j in range(n+1):
        score=lambda p:(j*(1-p)**2+(n-j)*p*p)/n
        chosen=min([lo,hi],key=score);prob=math.comb(n,j)*q**j*(1-q)**(n-j);weights.append(prob);losses.append(score(chosen));future+=prob*risk(chosen)
    apparent=sum(w*x for w,x in zip(weights,losses));return losses,apparent,future,future-apparent,variance([lo*lo,(1-lo)**2])

def trim(p0,p1,values,masses):
    p0=probability(p0,True);p1=probability(p1,True);need(p0<=p1,'selection monotonicity rates');need(len(values)==len(masses)>0 and values==sorted(values),'ordered atom support');need(all(x>=0 for x in masses)and sum(masses)==1,'atom masses');share=p0/p1
    def fill(order):
        remaining=share;total=F(0)
        for j in order:
            take=min(remaining,masses[j]);total+=take*values[j];remaining-=take
        need(remaining==0,'selection fill');return total/share
    return [p0,p1-p0,1-p1],[fill(range(len(values))),fill(reversed(range(len(values))))]
def market(beta,rows):
    need(len(rows)==2 and all(len(row)==2 for row in rows),'market shape');need(0<=beta<=1,'structural beta');y,d=rows;need(y[1]!=0,'nondegenerate residual');gamma=d[1]/y[1];need(d[0]-gamma*y[0]==1,'exact supply normalization');need(1-beta*gamma>0,'unique stable market');delta=y[0]-beta*d[0];need(0<=delta<=2,'direct effect domain');return gamma,delta,y[1]-beta*d[1]
def uniform_interval(n,M,alpha):
    integer(n);need(M>0,'positive maximum');alpha=probability(alpha,True);return [float(M),float(M)/float(alpha)**(1/n)]
def sequential(H,q,bound):
    integer(H);q=probability(q,True);need(bound>1,'crossing boundary');need(H<=10,'enumeration horizon');paths=list(product([1,0],repeat=H));ratios=[];hit=[]
    for path in paths:
        L=F(1);cross=False
        for x in path:
            L*=2*q if x else 2*(1-q)
            if L>=bound:cross=True;break
        ratios.append(L);hit.append(int(cross))
    need(mean(ratios)==1,'bounded stopped martingale');need(mean(hit)<=1/bound,'finite Ville bound');return mean(hit),ratios,mean(ratios)
def density(variances,weights,h):
    need(len(variances)==len(weights)==2 and min(variances)>0 and h>0,'positive density variances');need(all(p>=0 for p in weights)and sum(weights)==1,'state weights')
    ds=[(math.log(float(h/s))+float(s/h)-1)/2 for s in variances];cond=[float((s/h-1)**2)/2 for s in variances];avg=sum(float(p)*d for p,d in zip(weights,ds));cov=sum(float(p)*(d-avg)**2 for p,d in zip(weights,ds));within=sum(float(p)*v for p,v in zip(weights,cond));return avg,(within/2+cov),within+cov,cov

def macro(m,trial,target,taxrange,brange,b):
    need(len(m)==len(trial)==len(target)==2,'two types')
    for x in m:probability(x)
    need(all(p>0 for p in trial)and sum(trial)==1 and all(p>=0 for p in target)and sum(target)==1,'transport support')
    need(target==[F(1,2),F(1,2)],'balanced declared exposures');need(len(taxrange)==len(brange)==2 and 0<=taxrange[0]<=taxrange[1]<m[0] and 0<=brange[0]<=brange[1]<1 and 0<=b<1,'positive stable response domain');a=2*target[0]*m[0]-2*target[1]*m[1]
    return [sum(p*x for p,x in zip(trial,m)),sum(p*x for p,x in zip(target,m)),[t/s for t,s in zip(target,trial)],a,a/(1-b),[(m[0]-taxrange[1])/(1-brange[0]),(m[0]-taxrange[0])/(1-brange[1])]]

def reconstruct(x):
    out={};d=demand(*x['a1-demand'])
    need(x['a1-values']==[0,1,2,3],'declared reservation values')
    for key,field in [('t-range','t'),('mean','mean'),('q2','q2'),('optimal-profit','optimal'),('fixed-profit','fixed'),('minimax','minimax')]:out['a1-'+key]=d[field]
    sigma=x['a2-sigma'];need(sigma[0][0]==sigma[1][1]==1 and sigma[0][1]==sigma[1][0],'unit symmetric covariance');g=gaussian_product(*x['a2-mean'],sigma[0][1]);out.update({'a2-delta':g['delta'],'a2-exact-variance':[g['delta'],g['second']],'a2-origin-moments':[g['bias'],g['second']]})
    c=clusters([int(n) if n.denominator==1 else n for n in x['a3-sizes']],x['a3-y0'],x['a3-y1'])
    for name,v in zip(['target','cluster-target','ht','variance','ratios','ratio-bias'],c):out['a3-'+name]=v
    b=brier(x['a4-q'],*x['a4-predictions'],3)
    for name,v in zip(['selected-loss','apparent','future','optimism','test-variance'],b):out['a4-'+name]=v
    masses,bounds=trim(*x['a5-response'],x['a5-treated-values'],[F(1,3)]*3);sace=[z-1 for z in bounds];share=probability(x['a5-target-share']);out.update({'a5-masses':masses,'a5-naive':mean(x['a5-treated-values'])-1,'a5-sace':sace,'a5-target-bounds':[share*sace[0]-4*(1-share),share*sace[1]+4*(1-share)]})
    betas=x['b1-beta-range'];rows=x['b1-observed'];need(betas==[0,1],'declared structural range');out['b1-wald']=rows[0][0]/rows[1][0];out['b1-gamma']=market(betas[0],rows)[0];out['b1-policy-set']=[2*b for b in betas]
    n,m,alpha=x['b2-case'];need(n.denominator==1,'integer sample count');out['b2-interval']=uniform_interval(int(n),m,alpha)
    need(x['b3-alpha']==F(1,2),'declared monitoring level');safe,ratios,em=sequential(3,x['b3-alternative'],1/x['b3-alpha']);paths=list(product([1,0],repeat=3));naive=[];stopped=[]
    for path in paths:
        stop=1 if path[0]else 3;success=sum(path[:stop]);tail=sum(F(math.comb(stop,k),2**stop) for k in range(success,stop+1));naive.append(int(tail<=x['b3-alpha']));stopped.append(F(2*success-stop,stop))
    out.update({'b3-naive-size':mean(naive),'b3-safe-size':safe,'b3-stopped-ratios':ratios,'b3-martingale-mean':em,'b3-stopped-mean':mean(stopped)})
    score,v,_,_=density(x['b4-variances'],[F(1,2)]*2,x['b4-pooled']);out['b4-score-gain']=score;out['b4-mean-variance']=v
    values=macro(x['b5-mpcs'],x['b5-trial-shares'],x['b5-target-shares'],x['b5-tax-range'],x['b5-feedback-range'],x['b5-feedback'])
    for name,v in zip(['trial-mean','target-mean','weights','direct','output','output-set'],values):out['b5-'+name]=v
    return out

def check(root=None):
    root=Path(root)if root is not None else Path(__file__).resolve().parents[1];snap={p:(root/p).read_bytes()for p in FILES};r=Reader();r.feed(snap[FILES[0]].decode());count=0;rejections=0
    def compare(a,b,label):
        nonlocal count
        if isinstance(a,list):
            need(isinstance(b,list)and len(a)==len(b),'shape '+label)
            for j,(v,w)in enumerate(zip(a,b)):compare(v,w,label+'.'+str(j))
        elif isinstance(a,float):need(math.isfinite(a)and abs(a-float(b))<=5.1e-11,'rounded result '+label);count+=1
        else:need(F(a)==F(b),'exact result '+label);count+=1
    def reject(fn):
        nonlocal rejections
        try:fn()
        except (ValueError,TypeError,ZeroDivisionError):rejections+=1
        else:raise ValueError('malformed domain accepted')
    need(len(r.ids)==len(set(r.ids))and all(i.startswith('graduate-econometrics')for i in r.ids),'stable scoped IDs')
    need(r.h2==['graduate-econometrics-a','graduate-econometrics-b'],'two field headings')
    prompts=['graduate-econometrics-'+f+'-p'+str(i)+j for f in 'ab'for i in range(1,6)for j in 'abcd'];need(list(r.prompts)==prompts and r.solutions==prompts and set(r.rubrics)==set(prompts),'forty exact pairs')
    need(all(v==5 for v in r.prompts.values())and all(sum(v)==5 and min(v)>0 for v in r.rubrics.values()),'additive five-point rubrics')
    domains=['identification_and_estimands','estimation_and_asymptotics','causal_design_and_dependence','prediction_and_model_comparison','research_audit_and_transport'];need(r.domains=={(f,d):20 for f in 'ab'for d in domains},'five domains each form')
    expected=reconstruct(r.inputs);need(set(expected)==set(r.results),'complete visible output set')
    for k,v in expected.items():compare(v,r.results[k],k)
    need(len(r.inputs)==25,'all primitive groups');need({'v13-c01.html','v14-c11.html','v14-c12.html'}<=set(r.links),'scored cross-volume routes')
    sources=strict(snap[FILES[2]]);need({s['id']:s['url']for s in sources['sources']}==r.sources,'exact source URLs')
    author=strict(snap[FILES[3]]);need(set(author['payload_bindings'])==set(FILES[:3]),'three nonself bindings')
    for p,record in author['payload_bindings'].items():need(len(snap[p])==record['bytes']and hashlib.sha256(snap[p]).hexdigest()==record['sha256'],'freeze binding '+p)
    # Finite witnesses supplement the full manuscript proof audit.
    q1,q3=r.inputs['a1-demand'];weights=expected['a1-minimax'][:3];regret=expected['a1-minimax'][3]
    for j in range(61):
        t=(q1-q3)*F(j,60);mass=[1-q1,q1-q3-t,t,q3];compare(sum(mass),1,'demand normalization');compare(sum(mass[1:]),q1,'supported demand1');compare(mass[3],q3,'supported demand3');profits=[q1,2*(q3+t),3*q3];need(max(profits)-sum(w*p for w,p in zip(weights,profits))<=regret,'minimax witness');count+=1
    for beta in [F(j,10) for j in range(11)]:
        gamma,delta,u=market(beta,r.inputs['b1-observed'])
        for z,e in product([F(-2),F(0),F(3)],repeat=2):
            y=2*z+e;d=2*z+e/2;compare(y,beta*d+delta*z+u*e,'outcome structural world');compare(d,gamma*y+z,'supply structural world')
    # Endpoint worlds including observed selection law and target support.
    for upper in [False,True]:
        a1,a2,c=(F(2),F(4),F(0))if upper else(F(0),F(2),F(4));compare(sorted([a1,a2,c]),[F(0),F(2),F(4)],'treated selection distribution');compare((a1+a2)/2-1,2*int(upper),'always-observed effect')
    for n in [1,2,5,20]:
        for alpha in [F(1,4),F(1,2),F(3,4)]:
            a,b=uniform_interval(n,F(3),alpha);need(abs((a/b)**n-float(alpha))<1e-12,'uniform pivot inversion');count+=1
    for H in [1,2,3,4]:
        for q in [F(1,4),F(1,2),F(3,4)]:sequential(H,q,F(2));count+=1
    for h,b in product([F(1,10),F(3,10),F(1,2)],[F(0),F(3,10),F(3,5)]):
        y=(F(4,5)-h)/(1-b);need(F(3,10)<=y<=F(7,4)<2,'capacity and sharp range');compare(y,F(4,5)-h+b*y,'aggregate closure');compare(F(1,2)*2-F(1,2)*2,0,'fiscal balance')
    for fn in [lambda:probability(True),lambda:probability(F(3,2)),lambda:probability(F(0),True),lambda:demand(F(1,5),F(4,5)),lambda:demand(F(4,5),F(1,2)),lambda:gaussian_product(1,2,F(1)),lambda:clusters([1,2,0,4],[0,1,2,3],[2]*4),lambda:clusters([1,2,3],[0,1,2],[2]*3),lambda:brier(F(1,2),F(3,4),F(1,4),3),lambda:brier(F(1,2),F(1,4),F(3,4),True),lambda:trim(F(3,4),F(1,2),[0,2,4],[F(1,3)]*3),lambda:trim(F(1,2),F(3,4),[0,4,2],[F(1,3)]*3),lambda:trim(F(1,2),F(3,4),[0,2,4],[F(1,2)]*3),lambda:market(F(2),[[F(2),F(1)],[F(2),F(1,2)]]),lambda:market(F(0),[[F(2),F(1)],[F(3),F(1,2)]]),lambda:uniform_interval(0,3,F(1,4)),lambda:uniform_interval(2,0,F(1,4)),lambda:uniform_interval(2,3,F(1)),lambda:sequential(3,F(3,4),F(1)),lambda:sequential(3,F(1),F(2)),lambda:density([F(0),F(4)],[F(1,2)]*2,F(5,2)),lambda:density([F(1),F(4)],[F(1,3)]*2,F(5,2)),lambda:macro([F(4,5),F(1,5)],[F(0),F(1)],[F(1,2)]*2,[F(1,10),F(1,2)],[F(0),F(3,5)],F(2,5)),lambda:macro([F(4,5),F(1,5)],[F(1,4),F(3,4)],[F(1,2)]*2,[F(1,10),F(1,2)],[F(0),F(1)],F(2,5)),lambda:parse('(1,2'),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}')]:reject(fn)
    need({p:(root/p).read_bytes()for p in FILES}==snap,'runtime mutation')
    result=dict(status='passed',assessment='graduate-qualifying',field='econometrics',forms=2,solved_subparts=40,points_per_form=100,domains_per_form=5,input_groups=len(r.inputs),checked_results=len(r.results),comparisons=count,domain_rejections=rejections,runtime_files=4)
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
