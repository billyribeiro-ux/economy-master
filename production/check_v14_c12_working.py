"""Independent original frontier cases; four portable payloads, quiet API/CLI."""
from pathlib import Path
from hashlib import sha256
from html.parser import HTMLParser
from fractions import Fraction as F
from math import isfinite
import ast,json,itertools
FILES=('production/v14-c12-working.html','production/check_v14_c12_working.py','production/v14-c12-sources-working.json','production/v14-c12-author-review-working.json')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def number(x):
    require(type(x) in (int,float,F) and isfinite(float(x)),'finite scalar');return F(str(x)) if isinstance(x,float) else F(x)
def solve(A,b):
    n=len(b);require(n>0 and len(A)==n and all(len(r)==n for r in A),'square system');m=[[number(x) for x in row]+[number(bi)] for row,bi in zip(A,b)]
    for k in range(n):
        pivot=next((i for i in range(k,n) if m[i][k]),None);require(pivot is not None,'singular system');m[k],m[pivot]=m[pivot],m[k];a=m[k][k];m[k]=[x/a for x in m[k]]
        for i in range(n):
            if i!=k:
                a=m[i][k];m[i]=[x-a*y for x,y in zip(m[i],m[k])]
    return tuple(row[-1] for row in m)
def household(y,yp,R,beta):
    y,yp,R,beta=map(number,(y,yp,R,beta));require(min(y,yp,R,beta)>0,'household domain');a=max(F(0),(beta*R*y-yp)/(R*(1+beta)));return a,y-a,yp+R*a

def feedback(m,e,weights,d):
    m,e,weights=tuple(map(number,m)),tuple(map(number,e)),tuple(map(number,weights));d=number(d)
    require(len(m)==len(e)==len(weights)>0 and min(weights)>0 and sum(weights)==1,'weights');require(all(0<=x<=1 for x in m) and min(e)>=0 and sum(w*x for w,x in zip(weights,e))==1,'MPC/exposures')
    K=sum(w*x*z for w,x,z in zip(weights,m,e));require(abs(K)<1,'feedback contraction');mean=sum(w*x for w,x in zip(weights,m));return K,mean,K-mean,d/(1-K)

def linear(K,d):
    n=len(d);require(n>0 and len(K)==n and all(len(r)==n for r in K),'sequence shape');K=tuple(tuple(number(x) for x in r) for r in K);d=tuple(map(number,d));rho=max(sum(abs(x) for x in r) for r in K);require(rho<1,'sequence contraction');return solve([[F(i==j)-K[i][j] for j in range(n)] for i in range(n)],d),rho

def network(A,b,e):
    b,e=tuple(map(number,b)),tuple(map(number,e));n=len(b);require(n>0 and len(e)==n and len(A)==n and all(len(r)==n for r in A),'network shape');A=tuple(tuple(number(x) for x in r) for r in A);require(min(b)>0 and min(e)>=0 and all(x>=0 for r in A for x in r),'network positivity');require(all(A[i][i]==0 for i in range(n)),'no self obligation');rho=max(map(sum,A));require(rho<1,'strict outside leakage')
    candidates=[]
    for bits in itertools.product((False,True),repeat=n):
        M=[[F(i==j)-(A[j][i] if bits[i] else 0) for j in range(n)] for i in range(n)];v=[e[i] if bits[i] else b[i] for i in range(n)];p=solve(M,v);res=tuple(e[i]+sum(A[j][i]*p[j] for j in range(n)) for i in range(n))
        if all(p[i]==min(b[i],res[i]) for i in range(n)) and p not in candidates:candidates.append(p)
    require(len(candidates)==1,'unique feasible clearing');p=candidates[0];q=tuple(e[i]+sum(A[j][i]*p[j] for j in range(n))-p[i] for i in range(n));outside=sum((1-sum(A[i]))*p[i] for i in range(n));return p,q,outside

def kernel(a):
    a=number(a);require(-1<a<F(1,2),'positive kernel');return (1+a,1-2*a,1+a)
def mechanisms(g1,g3):
    g1,g3=map(number,(g1,g3));require(g1>=abs(g3),'nonnegative components');return ((g1+g3)/2,(g1-g3)/2)
class Read(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.prompts=[];self.solutions=[];self.cases=[];self.markers={};self.links=set()
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='a':self.links.add(a.get('href',''))
        if t=='li' and any(k=='ol' and 'exercises' in d.get('class','').split() for k,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            require(any(k=='details' and 'solutions' in d.get('class','').split() for k,d in self.stack),'solution disclosure');self.solutions.append(a['data-solution-for'])
        for key in ('data-input','data-result'):
            if key in a:require(a[key] not in self.markers,'duplicate marker');self.markers[a[key]]=[key,'']
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for _,a in self.stack:
            for key in ('data-input','data-result'):
                if key in a:self.markers[a[key]][1]+=s
    def handle_endtag(self,t):require(self.stack and self.stack[-1][0]==t,'HTML nesting');self.stack.pop()
def parse(s):
    s=s.split('=')[-1].strip().replace('−','-')
    def run(n):
        if isinstance(n,ast.Constant):return number(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(run(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return (-1 if isinstance(n.op,ast.USub) else 1)*run(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return run(n.left)/run(n.right)
        raise ValueError('numeric syntax')
    return run(ast.parse(s,mode='eval').body)
def check(root=None):
    b=Path(root) if root is not None else Path(__file__).resolve().parents[1];payload={f:(b/f).read_bytes() for f in FILES};doc=Read();doc.feed(payload[FILES[0]].decode());require(not doc.stack and len(set(doc.ids))==len(doc.ids),'valid HTML');require(all(x.startswith('v14-c12-') for x in doc.ids),'stable ids');targets=[f'v14-c12-e{i}' for i in range(1,13)];require(doc.prompts==doc.solutions==targets,'exact solutions');require(doc.cases==[f'v14-c12-case{i}' for i in range(1,6)],'five cases')
    src=json.loads(payload[FILES[2]]);require({x['url'] for x in src['sources']}=={u for u in doc.links if u.startswith('https:')},'source routes');r=json.loads(payload[FILES[3]]);require(set(r['exact_prompt_solution_audit'])==set(targets),'prompt audit');require(len(r['payload_bindings'])==3 and {x['path'] for x in r['payload_bindings']}==set(FILES[:3]),'bindings')
    for x in r['payload_bindings']:require((len(payload[x['path']]),sha256(payload[x['path']]).hexdigest())==(x['bytes'],x['sha256']),'hash')
    count=rejects=0
    def equal(x,y,label='comparison'):
        nonlocal count
        require(x==y,label+': '+str(x)+' != '+str(y));count+=1
    val={k:parse(v[1]) for k,v in doc.markers.items() if k not in ('sdf_family','sdf_domain')};equal(doc.markers['sdf_family'][1],'m(a)=(1+a,1−2a,1+a)','SDF displayed formula');equal(doc.markers['sdf_domain'][1],'−1<a<1/2','positive domain')
    betas=val['betas'];mpcs=tuple(1/(1+x) for x in betas);K,mean,cov,Y=feedback(mpcs,val['exposures'],(F(1,2),F(1,2)),val['direct']);same=feedback(mpcs,(1,1),(F(1,2),F(1,2)),val['direct'])
    ys,rho=linear(val['sequence_k'],(F(3,100),0));p,q,out=network(val['network_a'],val['network_b'],val['network_shock']);base,_,_=network(val['network_a'],val['network_b'],(6,6));pert,_,outpert=network(val['network_a'],val['network_b'],(F(9,10),6));a=3*val['extra_price']-1;m=kernel(a);ma,mb=mechanisms(F(3,50),F(1,50));variance=sum((x-1)**2 for x in m)/3
    expected={'mean_mpc':mean,'income_feedback':K,'mpc_covariance':cov,'output':Y,'induced':K*Y,'equal_exposure_output':same[-1],'sequence_norm':rho,'sequence_y0':ys[0],'sequence_y1':ys[1],'sequence_cross':ys[1]/F(3,100),'sequence_bound':F(3,5000)/(1-rho),'network_p1':p[0],'network_p2':p[1],'network_outside':out,'network_gross_loss':sum(base)-sum(p),'network_dp1':p[0]-pert[0],'network_dp2':p[1]-pert[1],'sdf_vector':m,'sdf_variance':variance,'identified_a':a,'mechanism_a':ma,'mechanism_b':mb,'moment_determinant':F(-2),'mechanism_variance':(F(1,2500)+F(1,10000))/4,'mechanism_covariance':(F(1,2500)-F(1,10000))/4}
    require(set(expected)=={k for k,v in doc.markers.items() if v[0]=='data-result'}-{'sdf_domain'},'all result coverage')
    for k,v in expected.items():equal(val[k],v,k)
    equal(val['moments'],((F(1),F(1)),(F(2),F(2))))
    equal(household(10,1,1,betas[0]),(F(6,5),F(44,5),F(11,5)));equal(household(10,1,1,betas[1]),(F(39,5),F(11,5),F(44,5)));equal(household(1,4,1,1),(0,1,4))
    rev=feedback(mpcs,(F(1,2),F(3,2)),(F(1,2),F(1,2)),F(1,50));equal(rev,(F(7,20),F(1,2),F(-3,20),F(2,65)));equal(F(3,100)/(1-K),F(3,35));equal(K*F(3,35),F(39,700))
    two,_=linear(val['sequence_k'],(F(3,100),F(3,100)));equal(two,(F(1,20),F(1,15)));equal(sum(two),F(7,60));equal((F(1,1000)+F(2,100)*F(5,100))/(1-F(62,100)),F(1,190))
    for e,ep,eq,eo in [((2,6),(F(20,3),F(28,3)),(0,0),8),((2,8),(7,10),(0,F(3,2)),F(17,2)),((1,7),(6,10),(0,0),8)]:
        z=network(val['network_a'],val['network_b'],e);equal(z,(ep,eq,eo));equal(sum(e),sum(z[1])+z[2])
    equal(out-outpert,F(1,10));equal(sum(p)-sum(pert),F(1,5))
    # Alternative networks: primitive accounts, monotonicity and one-step residual certificates.
    A=val['network_a'];B=val['network_b']
    for i in range(5):
        for j in range(5):
            E=(F(i,2),F(j+2));P,Q,O=network(A,B,E);equal(sum(E),sum(Q)+O);equal(P,tuple(min(B[k],E[k]+sum(A[l][k]*P[l] for l in range(2))) for k in range(2)))
            P2,_,_=network(A,B,(E[0]+F(1,10),E[1]));require(all(x>=y for x,y in zip(P2,P)),'cash monotonicity');count+=1
            approx=(min(B[0],P[0]+F(1,20)),max(F(0),P[1]-F(1,20)));res=sum(abs(approx[k]-min(B[k],E[k]+sum(A[l][k]*approx[l] for l in range(2)))) for k in range(2));require(sum(abs(x-y) for x,y in zip(approx,P))<=2*res,'residual certificate');count+=1
    for a in (F(-9,10),F(-1,10),F(0),F(1,5),F(49,100)):
        M=kernel(a);equal(sum(M)/3,1);equal((M[1]+2*M[2])/3,1);equal(sum((x-1)**2 for x in M)/3,2*a*a)
    equal(kernel(F(-1,10)),(F(9,10),F(6,5),F(9,10)))
    for n in range(7):
        aa=F(n,100);bb=F(6-n,100);equal(aa+bb,F(3,50));equal(2*aa+2*bb,F(3,25))
    v1,v3=F(1,2500),F(1,10000)
    for c in (F(-1,10000),0,F(1,10000)):
        va=(v1+v3+2*c)/4;vb=(v1+v3-2*c)/4;cab=(v1-v3)/4;require(va>=0 and vb>=0 and va*vb>=cab*cab,'covariance PSD');count+=1
    equal(sum(x*x for x in (F(4,100),F(-4,100),F(4,100),F(-4,100)))/4,F(1,625));equal(sum(x*x for x in (F(1,100),F(1,100),F(-1,100),F(-1,100)))/4,F(1,10000))
    invalid=[lambda:number(float('nan')),lambda:number(True),lambda:household(0,1,1,1),lambda:household(1,1,0,1),lambda:household(1,1,1,-1),lambda:feedback((1,),(1,),(1,),1),lambda:feedback((F(1,2),),(2,),(1,),1),lambda:feedback((F(1,2),),(1,),(F(1,2),),1),lambda:linear(((1,),),(1,)),lambda:linear(((0,0),),(1,)),lambda:solve(((1,1),(2,2)),(1,2)),lambda:network(((0,1),(1,0)),(10,10),(0,0)),lambda:network(((0,F(1,2)),(F(1,2),0)),(0,10),(1,1)),lambda:network(((0,-1),(0,0)),(10,10),(1,1)),lambda:network(((0,F(1,2)),(F(1,2),0)),(10,10),(-1,1)),lambda:kernel(-1),lambda:kernel(F(1,2)),lambda:mechanisms(F(1,10),F(1,5)),lambda:parse('__import__("os")')]
    for f in invalid:
        try:f()
        except (ValueError,ZeroDivisionError):rejects+=1
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v14-c12','status':'passed','comparisons':count,'domain_rejections':rejects,'worked_cases':5,'solved_exercises':12,'input_markers':sum(v[0]=='data-input' for v in doc.markers.values()),'result_markers':sum(v[0]=='data-result' for v in doc.markers.values()),'runtime_files':4,'scope':'Exact original finite transmission, sequence, network, SDF and identification cases; universal proof/source review separate. No empirical replication.'}
if __name__=='__main__':check()
