"""Separate bounded Form A peer oracle; six read-only payloads, quiet API/CLI."""
from collections import Counter, defaultdict
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import hashlib
import json
import math
import re

AUTHORS = ('content/assessments/parts/v12-exam-a.html', 'scripts/check_v12_exam_a.py',
           'content/reviews/v12-exam-a-sources.json', 'content/reviews/v12-exam-a-author.json')
SELF = 'scripts/check_v12_exam_a_peer.py'
REVIEW = 'content/reviews/v12-exam-a-peer.json'
POINTS = ((4,6,6,4),(6,7,7),(5,7,8),(8,6,6),(5,8,7))
SOURCES = {'v12-c01-mit-limit-tools','v12-c04-counts1999','v12-c06-aronow-samii-interference',
           'v12-c07-callaway-santanna2020','v12-c08-cattaneo-titiunik2022','v12-c09-mit-vars',
           'v12-c11-dml-v7','v12-c11-bh1995','asa-pvalues-2016','v04-c01-aea-data-faq'}


def demand(condition, message):
    if not condition:
        raise ValueError('Form A peer: '+message)


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            demand(key not in result,'duplicate JSON key')
            result[key]=value
        return result
    def bad(value):
        raise ValueError('nonfinite JSON '+value)
    result=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    def scan(x):
        if isinstance(x,float):demand(math.isfinite(x),'overflowed JSON number')
        elif isinstance(x,dict):
            for y in x.values():scan(y)
        elif isinstance(x,list):
            for y in x:scan(y)
    scan(result)
    return result


def exact(x):
    demand(type(x) in (int,F),'exact scalar, not boolean/float')
    demand(abs(x)<=1000000,'bounded exact scalar')
    return F(x)


def ratio(a,b):
    a,b=exact(a),exact(b)
    demand(b!=0,'observed ratio denominator is zero')
    return a/b


def average(values):
    demand(0<len(values)<=64,'bounded nonempty mean')
    return sum(values,F(0))/len(values)


def variance(values):
    center=average(values)
    return average([(x-center)**2 for x in values])


def nested(x):
    return tuple(nested(y) for y in x) if isinstance(x,(tuple,list)) else x


def visible(raw):
    """Only integers, fractions and nested tuples; never eval or author parser."""
    demand(type(raw) is str and len(raw)<400,'bounded displayed expression')
    cleaned=''.join(raw.replace('−','-').split())
    tokens=re.findall(r'\d+|[-+/(),]',cleaned)
    demand(''.join(tokens)==cleaned and 0<len(tokens)<180,'display token grammar')
    pos=0
    def number():
        nonlocal pos
        sign=1
        if pos<len(tokens) and tokens[pos] in ('-','+'):
            sign=-1 if tokens[pos]=='-' else 1;pos+=1
        demand(pos<len(tokens) and tokens[pos].isdigit(),'integer display token')
        value=exact(sign*int(tokens[pos]));pos+=1
        return value
    def item():
        nonlocal pos
        demand(pos<len(tokens),'complete displayed item')
        if tokens[pos]=='(':
            pos+=1;items=[item()]
            while pos<len(tokens) and tokens[pos]==',':
                pos+=1;items.append(item())
            demand(pos<len(tokens) and tokens[pos]==')','closed displayed tuple')
            pos+=1;return tuple(items)
        value=number()
        if pos<len(tokens) and tokens[pos]=='/':
            pos+=1;value=ratio(value,number())
        return value
    result=item();demand(pos==len(tokens),'no trailing display tokens')
    return result


class Evidence:
    def __init__(self):
        self.comparisons=0;self.rejections=0
    def same(self,a,b,label):
        demand(nested(a)==nested(b),label+': '+repr(a)+' != '+repr(b))
        self.comparisons+=1
    def reject(self,fn,label):
        try:fn()
        except ValueError:self.rejections+=1
        else:raise ValueError('missing peer-domain rejection: '+label)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.points={};self.prompts={};self.solutions={}
        self.splits={};self.markers={};self.tables={};self.sources=[];self.links=[]
        self.captures=[];self.table=None;self.row=None;self.cell=None;self.solution=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        demand(tag not in ('h1','script','iframe'),'static peer fragment')
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources.append(a['data-source'])
        for attribute,store in (('data-calc',self.markers),('data-solution-for',self.solutions)):
            if attribute in a:
                key=a[attribute];demand(key not in store,'unique capture')
                store[key]='';self.captures.append((len(self.stack),store,key))
                if attribute=='data-solution-for':self.solution=key
        if 'data-points' in a:
            demand(tag=='li' and a.get('id') not in self.points,'scored prompt element')
            key=a['id'];self.points[key]=int(a['data-points']);self.prompts[key]=''
            self.captures.append((len(self.stack),self.prompts,key))
        if 'data-score' in a:
            demand(self.solution is not None and self.solution not in self.splits,'paired grading')
            self.splits[self.solution]=[int(v) for v in a['data-score'].split(',')]
        if tag=='table':
            demand(self.table is None and a.get('id') not in self.tables,'nonnested identified table')
            self.table=a['id'];self.tables[self.table]=[]
        if tag=='tr' and self.table:self.row=[]
        if tag=='td' and self.table:self.cell=[]
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append(tag)
    def handle_data(self,data):
        for _,store,key in self.captures:store[key]+=data
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        demand(bool(self.stack) and self.stack[-1]==tag,'balanced HTML fragment')
        if tag=='td':self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
        if tag=='tr' and self.row:self.tables[self.table].append(self.row);self.row=None
        if tag=='table':self.table=None
        self.stack.pop();self.captures=[x for x in self.captures if x[0]<len(self.stack)]
        if tag=='li':self.solution=None


def aipw(y,d,e,m0,m1):
    demand(type(d) is int and d in (0,1),'binary observed treatment')
    y,e,m0,m1=map(exact,(y,e,m0,m1))
    demand(0<e<1,'positive candidate overlap')
    return m1-m0+(y-m1)/e if d else m1-m0-(y-m0)/(1-e)


def complementary_scores(rows):
    demand(type(rows) in (list,tuple) and 2<=len(rows)<=16,'bounded fold record')
    for row in rows:
        demand(type(row) in (list,tuple) and len(row)==3,'fold row shape')
        k,d,y=row
        demand(type(k) is int and k in (0,1) and type(d) is int and d in (0,1),'fold and treatment labels')
        demand(abs(exact(y))<=7,'bounded regression outcome')
    demand({r[0] for r in rows}=={0,1},'both training complements exist')
    models={}
    for k in (0,1):
        train=[r for r in rows if r[0]==1-k]
        frequency=F(1+sum(r[1] for r in train),2+len(train))
        e=max(F(1,4),min(F(3,4),frequency))
        means=[]
        for d in (0,1):
            cell=[exact(r[2]) for r in train if r[1]==d]
            means.append(max(F(-7),min(F(7),average(cell))) if cell else F(0))
        models[k]=(e,*means)
    scores=[aipw(r[2],r[1],*models[r[0]]) for r in rows]
    return [models[k] for k in (0,1)],scores


def bh(values,q):
    demand(type(values) in (list,tuple) and 1<=len(values)<=8,'bounded nonempty family')
    p=[exact(x) for x in values];q=exact(q)
    demand(0<q<1 and all(0<=x<=1 for x in p),'probability domain')
    ordered=sorted(enumerate(p,1),key=lambda item:(item[1],item[0]))
    ranks=[r for r,(_,value) in enumerate(ordered,1) if value<=q*r/len(p)]
    last=max(ranks,default=0)
    return sorted(i for i,_ in ordered[:last])


def approved(raw):
    demand(type(raw) in (list,tuple) and 4<=len(raw)<=8,'bounded raw roster')
    selected={}
    for row in raw:
        demand(type(row) in (list,tuple) and len(row)==5,'raw record shape')
        i,version,ok,a,b=row
        demand(type(i) is int and i in range(1,5),'scientific key')
        demand(type(version) is str and bool(version) and type(ok) is bool,'explicit version/approval')
        a,b=exact(a),exact(b)
        demand(a.denominator==b.denominator==1,'integer raw tenths')
        if ok:
            demand(i not in selected,'duplicate approved key')
            selected[i]=(a/10,b/10)
    demand(set(selected)==set(range(1,5)),'complete approved roster')
    return [selected[i] for i in range(1,5)]


def difference(values,treated):
    demand(len(values)==4 and len(treated)==2 and len(set(treated))==2,'four-unit two-treated design')
    demand(all(type(i) is int and i in range(4) for i in treated),'assignment support')
    return sum((1 if i in treated else -1)*exact(v) for i,v in enumerate(values))/2


def roster(k):
    demand(type(k) is int and 3<=k<=9,'integer target information')
    potentials=[(1,0)]*(12-k)+[(0,3)]*k
    return potentials,average([b-a for a,b in potentials])


def finite_oracle(page,e):
    """Original finite-law derivations; never call the author checker."""
    tables={
        'v12-a-did-input':[['Treated','0','0','5','3/4'],['Treated','1','4','9','1/4'],['Comparison','0','1','2','1/4'],['Comparison','1','6','8','3/4']],
        'v12-a-cutoff-input':[['Always','1/5','(1,4)','(6,4)'],['Complier','3/5','(2,5)','(2,5)'],['Never','1/5','(5,8)','(5,12)']],
        'v12-a-fold-input':[['0','0','0'],['0','1','2'],['1','0','1'],['1','0','3'],['1','1','5'],['1','1','7']],
        'v12-a-raw-input':[['1','v1','true','60','60'],['2','v1','true','40','0'],['3','v1','true','20','40'],['4','draft','false','20','20'],['4','v2','true','0','20']]}
    for key,table in tables.items():e.same(page.tables[key],table,'primitive table '+key)
    out={}
    panel=[]
    for z,u,a,b in product((-1,1),repeat=4):
        x=z+u;y0=10+2*z+a;y1=10+2*z+2*x+u+b
        panel.append((F(z),F(x),F(y0),F(y1),F(y1-y0),F(u+b-a)))
        e.same(y1-y0-2*x,u+b-a,'unit differencing')
    moment=lambda fn:average([fn(row) for row in panel])
    xx=moment(lambda r:r[1]**2);xy=moment(lambda r:r[1]*r[4])
    out['panel-ols']=(xx,xy,ratio(xy,xx))
    zx=moment(lambda r:r[0]*r[1]);zy=moment(lambda r:r[0]*r[4])
    score=[r[0]*r[5] for r in panel]
    e.same(average(score),0,'IV mean-zero score')
    out['panel-iv']=(zx,zy,variance(score))
    marginal=[r[3] for r in panel];mu=average(marginal);v=variance(marginal)
    out['panel-count-moments']=(mu,v);out['panel-qml-variances']=(v/mu**2,1/mu)
    relevance=moment(lambda r:r[2]*r[1]);exclusion=moment(lambda r:r[2]*r[5])
    out['panel-lag']=(relevance,exclusion,ratio(moment(lambda r:r[2]*r[4]),relevance))
    e.same(min(marginal),2,'finite positive count maximum exists')
    e.same(set(z*x for z,x,_,_,_,_ in panel),{F(0),F(2)},'realized IV zero denominator can occur')
    # A genuine zero first stage is possible, without invalidating the population one.
    e.reject(lambda:ratio(1,(1)*(1-1)),'actual zero first stage')
    zero_truth=[(z*x,z*(dy-2*x),x*(dy-2*x),y0*(dy-2*x)) for z,x,y0,_,dy,_ in panel]
    e.same(average([r[1] for r in zero_truth])/zx,0,'changed truth valid target')
    e.same(average([r[2] for r in zero_truth])/xx,F(1,2),'changed truth projection bias')
    e.same(average([r[3] for r in zero_truth])/relevance,F(-1,2),'changed truth lag bias')
    assigned=[(0,0),(1,0),(0,1),(1,1)]
    potentials={z:(2+z[0]+2*z[1],4+3*z[1]+z[0]) for z in assigned}
    ht=[]
    for z in assigned:
        h=F(0)
        for i in (0,1):
            if z[1-i]==0:h+=2*(2*z[i]-1)*potentials[z][i]
        ht.append(h)
    direct=F((potentials[1,0][0]-potentials[0,0][0])+(potentials[0,1][1]-potentials[0,0][1]),2)
    e.same(average(ht),direct,'actual finite exposure unbiasedness')
    out['pilot-statistics']=ht;out['pilot-total-effect']=average([a-b for a,b in zip(potentials[1,1],potentials[0,0])])
    did=page.tables['v12-a-did-input']
    cells={(g,int(x)):(F(pre),F(post),F(w)) for g,x,pre,post,w in did}
    changes={key:post-pre for key,(pre,post,w) in cells.items()}
    raw=sum(cells['Treated',x][2]*changes['Treated',x]-cells['Comparison',x][2]*changes['Comparison',x] for x in (0,1))
    att=sum(cells['Treated',x][2]*(changes['Treated',x]-changes['Comparison',x]) for x in (0,1))
    def sensitivity(t):
        t=exact(t);demand(-1<=t<=1,'coupled sensitivity domain')
        departures=(t,-t)
        counter=[cells['Treated',x][0]+changes['Comparison',x]+departures[x] for x in (0,1)]
        return sum(cells['Treated',x][2]*(cells['Treated',x][1]-counter[x]) for x in (0,1))
    out['did-targets']=(raw,att);out['did-range']=(sensitivity(1),sensitivity(-1))
    for t in (F(-1),F(2,5),F(1)):e.same(sensitivity(t),att-t/2,'sensitivity witness')
    cutoff=page.tables['v12-a-cutoff-input'];laws=[];ates=[];means=[];receipts=[]
    for col in (2,3):
        law=defaultdict(F);ate=F(0);by_side=[];take=[]
        for side in (0,1):
            ymean=dmean=F(0)
            for j,row in enumerate(cutoff):
                mass=F(row[1]);y0,y1=visible(row[col]);d=(1,side,0)[j];y=(y0,y1)[d]
                law[side,d,y]+=mass/2;ymean+=mass*y;dmean+=mass*d
            by_side.append(ymean);take.append(dmean)
        for row in cutoff:
            y0,y1=visible(row[col]);ate+=F(row[1])*(y1-y0)
        laws.append(dict(law));ates.append(ate);means.append(by_side);receipts.append(take)
    e.same(laws[0],laws[1],'full observed half-score/type law')
    e.same(sum(laws[0].values()),1,'complete population mass')
    dy=means[0][1]-means[0][0];dd=receipts[0][1]-receipts[0][0]
    out['cutoff-local']=(*means[0],dd,dy,ratio(dy,dd));out['cutoff-global']=ates
    A=[[F(1,2),F(1,4)],[F(0),F(1,2)]];state=[4,2]
    def mv(matrix,vector):return [sum(a*b for a,b in zip(row,vector)) for row in matrix]
    first=mv(A,state);second=mv(A,first)
    out['input-var-A']=A;out['var-means']=(first,second)
    out['var-covariance']=[[F(i==j)+sum(A[i][k]*A[j][k] for k in (0,1)) for j in (0,1)] for i in (0,1)]
    # Dense linear operator on the ten independent coordinates at dates t+1,...,t+5.
    G=[[F(0)]*10 for _ in range(4)]
    for origin in range(4):
        G[origin][2*origin]=A[0][0];G[origin][2*origin+1]=A[0][1];G[origin][2*(origin+1)]=1
    covariance=[[sum(a*b for a,b in zip(u,v)) for v in G] for u in G]
    avg_coeff=[sum(G[i][j] for i in range(4))/4 for j in range(10)]
    avg_var=sum(x*x for x in avg_coeff)
    e.same(avg_var,sum(sum(row) for row in covariance)/16,'direct coefficient norm and covariance sum')
    out['overlap-covariance']=covariance;out['overlap-variances']=(avg_var,covariance[0][0]/4)
    def forecast(b):
        b=exact(b);demand(F(1,2)<=b<=1,'structural parameter interval')
        c=F(1,4)/b
        return c,F(1,2)*4+b*(c-F(1,4))*2
    endpoints=[forecast(b)[1] for b in (F(1,2),F(1))]
    out['policy-range']=(min(endpoints),max(endpoints))
    for m in (F(2),F(13,6),F(9,4)):
        b=5-2*m;c,value=forecast(b)
        e.same(b*c,F(1,4),'equivalent full transition matrix')
        e.same(value,m,'policy sharpness inverse witness')
        e.same(c>=F(1,4),True,'policy transition domain')
    observed=[tuple(map(int,row)) for row in page.tables['v12-a-fold-input']]
    models,values=complementary_scores(observed);theta=average(values);vhat=variance(values)
    foldmeans=[average([value for row,value in zip(observed,values) if row[0]==k]) for k in (0,1)]
    out['fold-fits']=models;out['fold-scores']=values
    out['fold-means']=(*foldmeans,theta,average(foldmeans));out['fold-variances']=(vhat,vhat/6)
    e.same(theta,sum(sum(row[0]==k for row in observed)*foldmeans[k] for k in (0,1))/6,'observation-weighted folds')
    e.same(complementary_scores(observed[::-1])[1],values[::-1],'row-order invariance with fixed folds')
    low=(F(0),F(1),F(3));high=(F(2),F(5),F(7));m0,m1=average(low),average(high)
    oracle=[aipw(y1 if d else y0,d,F(1,2),m0,m1) for y0,y1,d in product(low,high,(0,1))]
    e.same(average(oracle),m1-m0,'complete oracle ATE')
    e.same(variance(oracle),2*(variance(low)+variance(high)),'oracle conditional variance identity')
    out['oracle-moments']=(m0,m1,variance(low),variance(high));out['oracle-variances']=(variance(oracle),variance(oracle)/6)
    e.same(F(1,2)-F(1,6)-F(2,5),F(-1,15),'root-N product rate')
    for d,p in ((0,F(1,4)),(1,F(3,4))):
        changed=[(k,d if k==1 else old,y) for k,old,y in observed]
        model=complementary_scores(changed)[0][0]
        e.same(model[0],p,'active training propensity clipping')
        e.same(model[2-d],0,'empty training regression cell')
    ps=[F(2,125),F(23,1000),F(39,1000),F(1,5)];q=F(1,20)
    out['input-pvalues']=ps;out['bh-full']=bh(ps,q);out['bh-trimmed']=bh(ps[:-1],q)
    out['minimum-cdf']=1-(1-q)**4
    e.same(out['minimum-cdf']>q,True,'selected minimum fails super-uniformity')
    e.same(bh([F(1,40),F(1,40)],q),[1,2],'inclusive BH boundary tie')
    e.same(bh([F(1),F(1)],q),[],'no rejection boundary')
    raw=[]
    for school,version,ok,a,b in page.tables['v12-a-raw-input']:
        demand(ok in ('true','false'),'explicit approval text')
        raw.append((int(school),version,ok=='true',int(a),int(b)))
    kept=approved(raw);vectors=list(zip(*kept));pairs=list(combinations(range(4),2))
    orbit=[tuple(difference(v,pair) for v in vectors) for pair in pairs]
    out['approved-vectors']=vectors;out['approved-contrasts']=orbit[0]
    out['unfiltered-contrasts']=[average([F(r[j],10) for r in raw if r[0] in (1,2)])-average([F(r[j],10) for r in raw if r[0] in (3,4)]) for j in (3,4)]
    def choose(pair):return max(range(2),key=lambda j:(abs(pair[j]),-j))
    choices=[choose(pair) for pair in orbit];maxima=[abs(pair[j]) for pair,j in zip(orbit,choices)]
    whole=[F(sum(other>=value for other in maxima),6) for value in maxima]
    naive=[F(sum(abs(pair[j])>=value for pair in orbit),6) for value,j in zip(maxima,choices)]
    out['assignment-orbit']=orbit;out['selected-scores']=maxima
    out['selection-pvalues']=(naive[0],whole[0]);out['selection-sizes']=(F(sum(p<=F(1,3) for p in naive),6),F(sum(p<=F(1,3) for p in whole),6))
    e.same(choices,[0,1,1,1,1,0],'complete selected endpoint branch')
    e.same(choose((F(2),F(-2))),0,'predeclared endpoint tie rule')
    for threshold in sorted(set(whole+[F(0),F(1,3)])):
        e.same(F(sum(p<=threshold for p in whole),6)<=threshold,True,'inclusive tied rank mass')
    completions=[]
    for k in range(3,10):
        potentials,value=roster(k);completions.append(value)
        e.same(value,-1+F(k,3),'integer roster witness')
        shifted=[(a+5,b+5) for a,b in potentials]
        e.same(average([b-a for a,b in shifted]),value,'level shift preserves transported effects')
    out['target-lattice']=completions;out['target-envelope']=(min(completions),max(completions))
    e.same(F(1,6) in completions,False,'envelope is not the lattice')
    for invalid in (True,0.5,float('inf')):e.reject(lambda x=invalid:exact(x),'exact scalar domain')
    e.reject(lambda:sensitivity(F(3,2)),'sensitivity restriction')
    e.reject(lambda:forecast(F(1,4)),'policy curve restriction')
    e.reject(lambda:complementary_scores(observed[:2]),'missing training complement')
    e.reject(lambda:aipw(1,1,0,0,1),'overlap')
    e.reject(lambda:bh([],q),'empty family')
    e.reject(lambda:bh([F(3,2)],q),'invalid p-value')
    e.reject(lambda:approved(raw+[raw[0]]),'duplicate approved key')
    e.reject(lambda:approved(raw[:-1]),'missing approved key')
    e.reject(lambda:approved([(1,'v1',1,60,60)]+raw[1:]),'ambiguous approval')
    e.reject(lambda:difference(vectors[0],(0,0)),'duplicate treated school')
    for k in (True,F(7,2),10):e.reject(lambda k=k:roster(k),'target roster domain')
    for value in ('__import__("os")','1/0','1e400'):e.reject(lambda value=value:visible(value),'restricted numeric grammar')
    for raw_json in ('{"x":1,"x":2}','{"x":NaN}','{"x":1e400}'):
        e.reject(lambda raw_json=raw_json:strict_json(raw_json),'strict JSON')
    return out


def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    e=Evidence();review=strict_json((base/REVIEW).read_text())
    bindings=review['payload_bindings']
    e.same({row['path'] for row in bindings},set(AUTHORS+(SELF,)),'five nonself peer bindings')
    e.same(len(bindings),5,'peer binding cardinality')
    for row in bindings:
        blob=(base/row['path']).read_bytes()
        e.same((len(blob),hashlib.sha256(blob).hexdigest()),(row['bytes'],row['sha256']),'bound payload '+row['path'])
    raw=(base/AUTHORS[0]).read_text();page=Fragment();page.feed(raw);page.close()
    e.same(page.stack,[],'complete HTML fragment')
    e.same(len(page.ids),len(set(page.ids)),'unique IDs')
    e.same(all(i in ('form-a','solutions-a') or i.startswith('v12-a-') for i in page.ids),True,'component ID boundaries')
    parts={f'v12-a-q{q}{chr(97+j)}':points for q,row in enumerate(POINTS,1) for j,points in enumerate(row)}
    e.same(page.points,parts,'sixteen exact scored prompts')
    e.same(list(page.solutions),list(parts),'sixteen paired complete solutions')
    for key,points in parts.items():
        e.same(sum(page.splits[key]),points,'rubric total '+key)
        e.same(all(x>0 for x in page.splits[key]),True,'positive score components')
    for q in range(1,6):e.same(sum(p for key,p in parts.items() if key.startswith(f'v12-a-q{q}')),20,'domain score')
    e.same(sum(parts.values()),100,'total score')
    results=finite_oracle(page,e)
    e.same(set(page.markers),set(results),'all36 displayed results')
    for key,value in results.items():e.same(visible(page.markers[key]),value,'independent visible result '+key)
    for fragment in ('α=10+2Z','X₂=Z+U','Y₁=α+E₁','Y₂=α+βX₂+U+E₂','teaching truth for calculations is β=2',
                     'Y₁(z)=2+z₁+2z₂','Y₂(z)=4+3z₂+z₁','uniformly distributed on [−1,1], independent of principal type',
                     'uniform on {0,1,3} and {2,5,7}','before assignment and outcome access'):
        e.same(fragment.casefold() in raw.casefold(),True,'actual primitive law '+fragment)
    e.same(set(page.sources),SOURCES,'actual method-source IDs')
    e.same(set(page.links),{'sources.html#'+s for s in SOURCES},'flat source links')
    sources=strict_json((base/AUTHORS[2]).read_text())
    e.same({s['id'] for s in sources['reused_sources']},SOURCES,'source record coverage')
    e.same(sources['new_primary_retrieval'],False,'no fresh body-reading claim')
    author=strict_json((base/AUTHORS[3]).read_text())
    e.same({r['path'] for r in author['reviewed_hashes']},set(AUTHORS[:3]),'author own binding scope')
    for row in author['reviewed_hashes']:
        blob=(base/row['path']).read_bytes()
        e.same((len(blob),hashlib.sha256(blob).hexdigest()),(row['bytes'],row['sha256']),'author final binding')
    for row in author['part_audit']:
        normalized=' '.join(page.prompts[row['id']].split())
        e.same(hashlib.sha256(normalized.encode()).hexdigest(),row['prompt_sha256'],'exact author-audited prompt')
    e.same(author['open_findings'],[],'resolved author findings')
    result={'component':'v12-exam-a-peer','status':'separate peer checks passed','comparisons':e.comparisons,
            'executed_rejections':e.rejections,'scored_parts':16,'domains':5,'points':100,
            'input_tables':4,'displayed_markers':len(results),'panel_atoms':16,'pilot_assignments':4,
            'complete_cutoff_worlds':2,'oracle_atoms':18,'selection_assignments':6,'target_completions':7,
            'author_checker_executed_as_oracle':False,'runtime_payloads':6}
    strict_json(json.dumps(result,allow_nan=False))
    return result


if __name__=='__main__':
    check()
