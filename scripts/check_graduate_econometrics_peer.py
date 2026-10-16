"""Separate peer reconstruction; never imports or executes the author checker."""
from pathlib import Path
from fractions import Fraction as Q
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product,combinations
from math import isfinite,log,prod
import ast,json
FILES=('content/cross-assessments/parts/graduate-econometrics.html','scripts/check_graduate_econometrics.py','content/reviews/graduate-econometrics-sources.json','content/reviews/graduate-econometrics-author.json','scripts/check_graduate_econometrics_peer.py','content/reviews/graduate-econometrics-peer.json')
def require(ok,message):
    if not ok:raise ValueError(message)
def number(x):
    require(type(x) in (int,float,Q) and isfinite(x),'finite real');return Q(str(x))
def law(x):
    require(isinstance(x,(tuple,list)) and len(x)>0,'nonempty law');x=tuple(map(number,x));require(min(x)>=0 and sum(x)==1,'probability law');return x
def literal(text):
    def visit(n):
        if isinstance(n,ast.Constant):return number(n.value)
        if isinstance(n,(ast.List,ast.Tuple)):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('numeric literals only')
    return visit(ast.parse(text.strip(),mode='eval').body)
def record(raw):
    def pairs(items):
        d={}
        for k,v in items:require(k not in d,'duplicate JSON key');d[k]=v
        return d
    def fail(x):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=fail)
def average(values):require(len(values)>0,'nonempty average');return sum(values)/len(values)
def variance(values):m=average(values);return average([(v-m)**2 for v in values])
def solve(a,b):
    require(len(a)==len(b)>0 and all(len(row)==len(b) for row in a),'square linear system');n=len(b);a=[list(map(number,row))+[number(v)] for row,v in zip(a,b)]
    for j in range(n):
        p=next((i for i in range(j,n) if a[i][j]),None);require(p is not None,'nonsingular');a[j],a[p]=a[p],a[j];v=a[j][j];a[j]=[z/v for z in a[j]]
        for i in range(n):
            if i!=j:v=a[i][j];a[i]=[z-v*w for z,w in zip(a[i],a[j])]
    return tuple(row[-1] for row in a)
def wick(indices,cov):
    require(len(cov)==2 and all(len(r)==2 for r in cov) and cov[0][0]>0 and cov[1][1]>0 and cov[0][1]==cov[1][0] and cov[0][0]*cov[1][1]>cov[0][1]**2,'positive definite covariance')
    if not indices:return Q(1)
    if len(indices)%2:return Q(0)
    return sum(cov[indices[0]][indices[j]]*wick(indices[1:j]+indices[j+1:],cov) for j in range(1,len(indices)))
def allocation_vertices(bounds,total):
    require(len(bounds)>0 and all(number(b)>=0 for b in bounds) and 0<=total<=sum(bounds),'allocation constraints');out=set()
    for free in range(len(bounds)):
        other=[i for i in range(len(bounds)) if i!=free]
        for bits in product((0,1),repeat=len(other)):
            v=[Q(0)]*len(bounds)
            for i,b in zip(other,bits):v[i]=b*bounds[i]
            v[free]=total-sum(v)
            if 0<=v[free]<=bounds[free]:out.add(tuple(v))
    return sorted(out)
def paths(n):require(type(n)is int and 1<=n<=10,'finite horizon');return list(product((1,0),repeat=n))
def stopped_tree(n,q,bound):
    require(0<number(q)<1 and number(bound)>1,'likelihood boundary');rows=[]
    for path in paths(n):
        value=Q(1);hit=False
        for h in path:
            value*=2*(q if h else 1-q)
            if value>=bound:hit=True;break
        rows.append((value,int(hit)))
    return rows
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=set();self.prompts={};self.solutions={};self.rubrics={};self.domains={};self.mark={};self.links=[];self.sources={};self.headings=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'unique attributes')
        if 'id' in a:require(a['id'] not in self.ids and a['id'].startswith('graduate-econometrics-'),'scoped unique ID');self.ids.add(a['id'])
        require(t!='h1','component heading')
        if t=='h2':self.headings.append(a.get('id'))
        if 'href' in a:self.links.append(a['href'])
        if t=='li' and 'data-points' in a:self.prompts[a['id']]=int(a['data-points'])
        if 'data-solution-for' in a:
            k=a['data-solution-for'];require(k not in self.solutions and any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'unique disclosed solution');self.solutions[k]=''
        if 'data-score' in a:
            k=next(d['data-solution-for'] for t,d in reversed(self.stack) if 'data-solution-for' in d);require(k not in self.rubrics,'unique rubric');self.rubrics[k]=tuple(map(int,a['data-score'].split(',')))
        if 'data-domain' in a:
            k=(a['data-form'],a['data-domain']);require(k not in self.domains,'unique domain');self.domains[k]=int(a['data-points'])
        if 'data-source' in a:require(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        for name in ('data-input','data-calc'):
            if name in a:require(a[name] not in self.mark,'unique numerical marker');self.mark[a[name]]=[name,'']
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for t,a in self.stack:
            if 'data-solution-for' in a:self.solutions[a['data-solution-for']]+=s
            for name in ('data-input','data-calc'):
                if name in a:self.mark[a[name]][1]+=s
    def handle_endtag(self,t):require(self.stack and self.stack[-1][0]==t,'balanced tags');self.stack.pop()
def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(base/f).read_bytes() for f in FILES};p=Page();p.feed(raw[FILES[0]].decode());p.close();require(not p.stack,'closed page');peer=record(raw[FILES[5]]);author=record(raw[FILES[3]]);sources=record(raw[FILES[2]])
    expected=[f'graduate-econometrics-{f}-p{i}{j}' for f in 'ab' for i in range(1,6) for j in 'abcd'];require(list(p.prompts)==list(p.solutions)==expected and set(p.rubrics)==set(expected),'forty exact pairs');require(p.headings==['graduate-econometrics-a','graduate-econometrics-b'],'two forms')
    for k in expected:require(p.prompts[k]==5 and sum(p.rubrics[k])==5 and min(p.rubrics[k])>0 and len(p.solutions[k])>350,'complete scored solution')
    domains=('identification_and_estimands','estimation_and_asymptotics','causal_design_and_dependence','prediction_and_model_comparison','research_audit_and_transport');require(p.domains=={(f,d):20 for f in 'ab' for d in domains},'100 points in five domains');require(set(peer['exact_prompt_review'])==set(expected) and not peer['open_findings'] and not author['open_issues'],'complete audits');require(p.sources=={s['id']:s['url'] for s in sources['sources']},'source routes');require({'v13-c01.html','v14-c11.html','v14-c12.html'}<=set(p.links),'scored integration routes')
    for bindings,files in ((peer['payload_bindings'],FILES[:5]),(author['payload_bindings'],FILES[:3])):
        require(set(bindings)==set(files),'nonself binding set')
        for f,b in bindings.items():require(len(raw[f])==b['bytes'] and sha256(raw[f]).hexdigest()==b['sha256'],'bound byte identity')
    count=0;rejects=0;seen=set();x={k:literal(v[1]) for k,v in p.mark.items() if v[0]=='data-input'};require(len(x)==25,'primitive inventory')
    def eq(a,b):
        nonlocal count
        if isinstance(a,(tuple,list)):
            require(isinstance(b,(tuple,list)) and len(a)==len(b),'numeric shape')
            for v,w in zip(a,b):eq(v,w)
        else:require(isfinite(float(a)) and abs(float(a)-float(b))<5.1e-11,'numeric discrepancy '+str((a,b)));count+=1
    def result(k,v):eq(v,literal(p.mark[k][1]));seen.add(k)
    def witness(ok,label):
        nonlocal count
        require(ok,label);count+=1
    # Enumerate feasible demand-law endpoints from the observation equations.
    values=x['a1-values'];q1,q3=x['a1-demand'];eq(values,(0,1,2,3));laws=[(1-q1,q1-q3-t,t,q3) for t in (Q(0),q1-q3)];profits=[tuple(price*sum(m for v,m in zip(values,L) if v>=price) for price in (1,2,3)) for L in laws];means=[sum(v*m for v,m in zip(values,L)) for L in laws]
    result('a1-t-range',(0,q1-q3));result('a1-mean',(min(means),max(means)));result('a1-q2',(q3,q1));result('a1-optimal-profit',tuple(max(z) for z in profits));result('a1-fixed-profit',tuple(z[1] for z in profits));w1,w2,r=solve(((1,1,0),(profits[0][0],profits[0][1],1),(profits[1][0],profits[1][1],1)),(1,max(profits[0]),max(profits[1])));result('a1-minimax',(w1,w2,0,r))
    for j in range(41):
        t=(q1-q3)*Q(j,40);L=law((1-q1,q1-q3-t,t,q3));P=[price*sum(m for v,m in zip(values,L) if v>=price) for price in (1,2,3)];eq(sum(L[1:]),q1);witness(max(P)-w1*P[0]-w2*P[1]<=r,'interior regret')
    # Gaussian polynomial moments via recursive pairings, not a delta formula helper.
    cov=x['a2-sigma'];a,b=x['a2-mean'];terms=[(b,(0,)),(a,(1,))];v=sum(c*d*wick(i+j,cov) for c,i in terms for d,j in terms);bias=wick((0,1),cov);v2=wick((0,1,0,1),cov)-bias**2;result('a2-delta',v);result('a2-exact-variance',(v,v2));result('a2-origin-moments',(bias,v2))
    for n in (1,2,7,30):
        # Exact centered polynomial variance including the odd cross moments.
        terms2=[(b,(0,)),(a,(1,)),(Q(1,n),(0,1))];second=sum(c*d*wick(i+j,cov) for c,i in terms2 for d,j in terms2)-(bias/n)**2;eq(second,v+v2/n**2)
    sizes=x['a3-sizes'];y0=x['a3-y0'];y1=x['a3-y1'];N=sum(sizes);ht=[];ratio=[]
    for treated in combinations(range(4),2):
        T=sum(sizes[i]*y1[i] for i in treated);C=sum(sizes[i]*y0[i] for i in range(4) if i not in treated);nt=sum(sizes[i] for i in treated);ht.append(2*(T-C)/N);ratio.append(T/nt-C/(N-nt))
    target=sum(n*(b-a) for n,a,b in zip(sizes,y0,y1))/N
    for k,vv in [('target',target),('cluster-target',average([b-a for a,b in zip(y0,y1)])),('ht',ht),('variance',variance(ht)),('ratios',ratio),('ratio-bias',average(ratio)-target)]:result('a3-'+k,vv)
    eq(average(ht),target)
    lo,hi=x['a4-predictions'];q=x['a4-q'];validation=[];future=[];bycount={}
    for path in paths(3):
        losses={f:average([(z-f)**2 for z in path]) for f in (lo,hi)};f=min(losses,key=losses.get);weight=prod(q if z else 1-q for z in path);validation.append(weight*losses[f]);future.append(weight*(q*(1-f)**2+(1-q)*f*f));bycount[sum(path)]=losses[f]
    result('a4-selected-loss',tuple(bycount[j] for j in range(4)));result('a4-apparent',sum(validation));result('a4-future',sum(future));result('a4-optimism',sum(future)-sum(validation));result('a4-test-variance',variance((lo*lo,(1-lo)**2)))
    p0,p1=x['a5-response'];atoms=x['a5-treated-values'];vertices=allocation_vertices((p1/3,)*3,p0);effects=[sum(m*y for m,y in zip(v,atoms))/p0-1 for v in vertices];lo,hi=min(effects),max(effects);share=x['a5-target-share'];result('a5-masses',(p0,p1-p0,1-p1));result('a5-naive',average(atoms)-1);result('a5-sace',(lo,hi));result('a5-target-bounds',(share*lo-4*(1-share),share*hi+4*(1-share)))
    for vtx in vertices:eq(sum(vtx),p0);witness(all(0<=v<=p1/3 for v in vtx),'selection vertex')
    Y,D=x['b1-observed'];gamma=D[1]/Y[1];result('b1-wald',Y[0]/D[0]);result('b1-gamma',gamma);result('b1-policy-set',tuple(2*b for b in x['b1-beta-range']))
    for beta in [Q(j,8) for j in range(9)]:
        delta=Y[0]-beta*D[0];resid=Y[1]-beta*D[1]
        for z,e in product((-1,0,2),repeat=2):eq(solve(((1,-beta),(-gamma,1)),(delta*z+resid*e,z)),(Y[0]*z+Y[1]*e,D[0]*z+D[1]*e))
    n,M,alpha=x['b2-case'];result('b2-interval',(M,float(M)/float(alpha)**(1/float(n))))
    for n in (1,2,3,10):
        ev=Q(n,n+1);ev2=Q(n,n+2);eq(ev2-ev*ev,Q(n,(n+1)**2*(n+2)));eq((ev2-ev*ev)*Q((n+1)**2,n*n),Q(1,n*(n+2)));witness(1-(1-Q(1,n))**n>0,'empirical bootstrap atom')
    rows=stopped_tree(3,x['b3-alternative'],1/x['b3-alpha']);naive=[];means=[]
    for path in paths(3):
        obs=path[:1] if path[0] else path;null=paths(len(obs));tail=Q(sum(sum(z)>=sum(obs) for z in null),len(null));naive.append(int(tail<=x['b3-alpha']));means.append(average([2*z-1 for z in obs]))
    result('b3-naive-size',average(naive));result('b3-safe-size',average([z[1] for z in rows]));result('b3-stopped-ratios',[z[0] for z in rows]);result('b3-martingale-mean',average([z[0] for z in rows]));result('b3-stopped-mean',average(means))
    for n,q in product((1,2,4,5),(Q(1,4),Q(1,2),Q(4,5))):
        rows=stopped_tree(n,q,2);eq(average([z[0] for z in rows]),1);witness(average([z[1] for z in rows])<=Q(1,2),'bounded stopping inequality')
    states=x['b4-variances'];h=x['b4-pooled'];d=[];second=[]
    for s in states:
        A=log(float(h/s))/2;B=float(s/h-1)/2;d.append(A+B);second.append(A*A+2*A*B+3*B*B)
    mu=average(d);single=average(second)-mu*mu;cross=average([v*v for v in d])-mu*mu;result('b4-score-gain',mu);result('b4-mean-variance',(single+cross)/2);witness(cross>0,'shared-state covariance')
    m=x['b5-mpcs'];trial=law(x['b5-trial-shares']);target=law(x['b5-target-shares']);b=x['b5-feedback'];direct=2*target[0]*m[0]-2*target[1]*m[1];result('b5-trial-mean',sum(p*y for p,y in zip(trial,m)));result('b5-target-mean',sum(p*y for p,y in zip(target,m)));result('b5-weights',tuple(t/s for t,s in zip(target,trial)));result('b5-direct',direct);result('b5-output',solve(((1-b,),),(direct,))[0]);corners=[(m[0]-h)/(1-b) for h,b in product(x['b5-tax-range'],x['b5-feedback-range'])];result('b5-output-set',(min(corners),max(corners)))
    for h,b in product((Q(1,10),Q(1,4),Q(1,2)),(Q(0),Q(1,3),Q(3,5))):
        y=solve(((1-b,),),(m[0]-h,))[0];eq(y,m[0]-h+b*y);witness(min(corners)<=y<=max(corners)<2,'capacity bound')
    bad=(lambda:number(True),lambda:number(float('nan')),lambda:law(()),lambda:law((Q(1,2),)),lambda:law((-1,2)),lambda:literal('__import__("os")'),lambda:literal('1+2'),lambda:record('{"a":1,"a":2}'),lambda:record('{"a":NaN}'),lambda:solve(((1,), (2,)),(1,)),lambda:solve(((1,0),),(1,)),lambda:solve(((0,),),(1,)),lambda:wick((0,1),((1,1),(1,1))),lambda:allocation_vertices((1,1),3),lambda:allocation_vertices((-1,2),1),lambda:paths(True),lambda:paths(0),lambda:stopped_tree(3,1,2),lambda:stopped_tree(3,Q(1,2),1))
    for fn in bad:
        try:fn()
        except (ValueError,TypeError,ZeroDivisionError):rejects+=1
        else:raise ValueError('invalid domain accepted')
    require(seen=={k for k,v in p.mark.items() if v[0]=='data-calc'},'all result markers reconstructed');require(raw=={f:(base/f).read_bytes() for f in FILES},'unchanged runtime');summary=dict(status='passed',assessment='graduate-qualifying',field='econometrics',forms=2,solved_subparts=40,points_per_form=100,domains_per_form=5,comparisons=count,domain_rejections=rejects,input_groups=len(x),checked_results=len(seen),runtime_files=6);json.dumps(summary,allow_nan=False);return summary
if __name__=='__main__':check()
