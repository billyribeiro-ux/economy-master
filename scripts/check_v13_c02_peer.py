"""Independent six-file peer audit of consumer and producer duality.

Exact closed-form derivatives, coordinate integrals and global branch bounds
are reconstructed without importing the author's differentiation engine.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import ast
import json
import math
import sys

AUTHOR=('content/chapters/v13-c02.html','scripts/check_v13_c02.py',
        'content/reviews/v13-c02-sources.json','content/reviews/v13-c02-author.json')
SELF='scripts/check_v13_c02_peer.py'
RECORD='content/reviews/v13-c02-peer.json'
SOURCE_IDS={'v05-c02-consumer','v05-c03-condie-supply'}


def require(ok,label):
    if not ok:raise ValueError('C02 peer: '+label)


class Audit:
    def __init__(self):self.comparisons=0;self.rejections=0;self.interventions=0
    def equal(self,a,b,label):
        require(a==b,label+': '+repr(a)[:120]);self.comparisons+=1
    def reject(self,fn,label):
        try:fn()
        except (ValueError,SyntaxError,ZeroDivisionError):self.rejections+=1
        else:raise ValueError('accepted invalid '+label)


def strict_json(text):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def fail(v):raise ValueError('nonfinite JSON '+v)
    value=json.loads(text,object_pairs_hook=pairs,parse_constant=fail)
    def scan(x):
        if isinstance(x,float):require(math.isfinite(x),'overflowed JSON number')
        elif isinstance(x,dict):
            for v in x.values():scan(v)
        elif isinstance(x,list):
            for v in x:scan(v)
    scan(value);return value


def number(x):
    require(type(x) in (int,F),'exact scalar, not bool/float/string')
    x=F(x);require(abs(x)<=100000 and x.denominator<=1000000,'bounded rational')
    return x


def vec(x,n,positive=False):
    require(type(x) in (tuple,list) and len(x)==n,'vector dimensions')
    x=tuple(map(number,x))
    if positive:require(min(x)>0,'strictly positive prices')
    return x


def sqrt(x):
    x=number(x);require(x>=0,'nonnegative square root')
    n,d=math.isqrt(x.numerator),math.isqrt(x.denominator)
    require(n*n==x.numerator and d*d==x.denominator,'rational-square arithmetic scope')
    return F(n,d)


def dot(a,b):
    require(len(a)==len(b),'dot dimensions')
    return sum((x*y for x,y in zip(a,b)),F(0))


def outer(a,b):return tuple(tuple(x*y for y in b) for x in a)
def mv(a,x):return tuple(dot(row,x) for row in a)
def transpose(a):return tuple(zip(*a))
def add(a,b):return tuple(tuple(x+y for x,y in zip(c,d)) for c,d in zip(a,b))


def numeric(text):
    require(type(text) is str and len(text)<=1500,'bounded marker text')
    tree=ast.parse(text.strip().replace('−','-'),mode='eval').body
    def visit(n):
        if isinstance(n,ast.Constant):return number(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):
            require(len(n.elts)<=20,'bounded marker tuple');return tuple(visit(z) for z in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):
            value=visit(n.operand);require(type(value) is F,'negative scalar');return -value
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            a,b=visit(n.left),visit(n.right)
            require(type(a) is F and type(b) is F and b!=0,'rational marker')
            return number(a/b)
        raise ValueError('numeric marker grammar')
    return visit(tree)


def stone(p,m,g=(1,2)):
    p=vec(p,2,True);g=vec(g,2);m=number(m)
    require(min(g)>=0 and m>=dot(p,g),'nonempty shifted domain')
    # Equal spending follows from the AM-GM global bound, not a local FOC.
    residual=m-dot(p,g);z=tuple(residual/(2*v) for v in p)
    x=tuple(a+b for a,b in zip(g,z));u=sqrt(z[0]*z[1])
    # Differentiate the simplified rational demands at fixed nominal income.
    J=((- (m-g[1]*p[1])/(2*p[0]**2),-g[1]/(2*p[0])),
       (-g[0]/(2*p[1]),- (m-g[0]*p[0])/(2*p[1]**2)))
    xm=tuple(1/(2*v) for v in p)
    return x,u,J,xm


def expenditure(p,u,g=(1,2)):
    p=vec(p,2,True);g=vec(g,2);u=number(u)
    require(u>=0 and min(g)>=0,'target and subsistence')
    h=(g[0]+u*sqrt(p[1]/p[0]),g[1]+u*sqrt(p[0]/p[1]))
    return dot(p,h),h


def kink(p,target):
    p=vec(p,2,True);target=number(target);require(target>=0,'nonnegative target')
    endpoints=((target,F(0)),(F(0),target/2))
    values=tuple(dot(p,h) for h in endpoints)
    return min(values),tuple(h for h,v in zip(endpoints,values) if v==min(values))


def homothetic(p,u,alpha=2):
    p=vec(p,3,True);u=number(u);alpha=number(alpha)
    require(u>=0 and alpha>0,'constructive target/alpha domain')
    unit=alpha*sqrt(p[0]*p[1])+p[2]
    gradient=(alpha*sqrt(p[1]/p[0])/2,alpha*sqrt(p[0]/p[1])/2,F(1))
    h=tuple(u*v for v in gradient)
    return unit,h,u*unit


def direct(x,alpha=2):
    x=vec(x,3);alpha=number(alpha)
    require(min(x)>=0 and alpha>0,'direct index domain')
    return min(2*sqrt(x[0]*x[1])/alpha,x[2])


def integral_coordinate(fixed_price,start,end,target,alpha=2):
    # Integral of (alpha*u/2)*sqrt(fixed_price)*p^(-1/2) dp.
    return number(alpha)*number(target)*sqrt(fixed_price)*(sqrt(end)-sqrt(start))


def production(w,r):
    w=vec(w,2,True);r=number(r);require(r>=0,'nonnegative output price')
    s=sqrt(w[0]*w[1]);q=r/(4*s)
    k=q*q*sqrt(w[1]/w[0]);l=q*q*sqrt(w[0]/w[1]);cost=dot(w,(k,l))
    return (q,k,l,cost,r*q-cost)


def cost_without_closedness(p):
    """Counterexample to omitting closedness from the cost envelope hypothesis."""
    p=vec(p,2,True)
    require(all(F(9,10)<=v<=F(11,10) for v in p),'local counterexample prices')
    if p[0]<=p[1]:point=(F(2),F(1))
    else:
        t=(p[0]-p[1])/(2*p[1])
        require(0<t<=F(1,2),'attained curve parameter')
        point=(1-t,2+t+t*t)
    return dot(p,point),point


def profit_derivatives(w,r):
    w=vec(w,2,True);r=number(r);require(r>=0,'nonnegative output price')
    s=sqrt(w[0]*w[1])
    if r==0:
        return (F(0),)*3,((F(0),F(0),F(0)),(F(0),F(0),F(0)),(F(0),F(0),1/(4*s)))
    value=r*r/(8*s);p=w+(r,);powers=(F(-1,2),F(-1,2),F(2))
    # Monomial differentiation, independent of automatic differentiation.
    gradient=tuple(value*a/v for a,v in zip(powers,p))
    hessian=tuple(tuple(value*powers[i]*(powers[j]-int(i==j))/(p[i]*p[j])
                        for j in range(3)) for i in range(3))
    return gradient,hessian


def entry(w,r):
    w,r=number(w),number(r);require(w>0 and r>0,'positive entry prices')
    a=r/w;q=min(a/2,F(3));active=r*q-w*(4+q*q)
    # Complete square bounds every active q in [0,3]; participation is separate.
    if active<0:return F(0),((F(0),F(0)),)
    active_plan=(-4-q*q,q)
    if active==0:return F(0),((F(0),F(0)),active_plan)
    return active,(active_plan,)


def original_feasible(y):
    n,q=vec(y,2);resources=-n
    if resources<0:return False
    if q<=0:return True
    return q<=3 and resources>=4+q*q


def hull_input(q):
    q=number(q);require(0<=q<=3,'hull output within capacity')
    # Tangency at q=2 joins inactivity to the convex active parabola.
    return 4*q if q<=2 else 4+q*q


def log_field(p,m):
    p=vec(p,3,True);m=number(m);require(m>0,'positive log-share income')
    logs=tuple(math.log(float(v)) for v in p)
    require(max(logs)-min(logs)<1,'stated logarithmic domain')
    s=tuple(1/3+(logs[(i+1)%3]-logs[(i+2)%3])/12 for i in range(3))
    x=tuple(float(m/v)*t for v,t in zip(p,s))
    return s,x


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.cases=[];self.prompts=[];self.solutions=[]
        self.inputs={};self.calcs={};self.links=[];self.sources={};self.branch_rows=[]
        self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'unique HTML attributes')
        ident=a.get('id');classes=a.get('class','').split()
        if ident:
            require(ident.startswith('v13-c02-') and ident not in self.ids,'unique prefixed ID')
            self.ids.append(ident)
        if 'worked' in classes:self.cases.append(ident)
        if tag=='li' and any('exercises' in n['attrs'].get('class','').split() for n in self.stack):self.prompts.append(ident)
        if 'data-solution-for' in a:
            require(any('solutions' in n['attrs'].get('class','').split() for n in self.stack),'recognized solution wrapper')
            self.solutions.append(a['data-solution-for'])
        if 'href' in a:self.links.append(a['href'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if tag=='table':self.table=a.get('id')
        if tag=='tr':self.row=[]
        if tag=='td':self.cell=''
        if tag not in ('br','hr','img','meta','input','link'):self.stack.append({'tag':tag,'attrs':a,'text':''})
    def handle_data(self,text):
        for n in self.stack:n['text']+=text
        if self.cell is not None:self.cell+=text
    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack[-1]['tag']==tag,'balanced HTML')
        node=self.stack.pop()
        for field,dest in (('data-input',self.inputs),('data-calc',self.calcs)):
            if field in node['attrs']:
                key=node['attrs'][field];require(key not in dest,'unique numerical marker')
                dest[key]=numeric(node['text'])
        if tag=='td':self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.table=='v13-c02-entry-branches' and self.row:self.branch_rows.append(self.row)
        if tag=='table':self.table=None
    def finish(self):
        self.close();require(not self.stack,'closed manuscript')
        require(self.cases==['v13-c02-case'+str(i) for i in range(1,7)],'six worked cases')
        sequence=['v13-c02-ex'+str(i) for i in range(1,13)]
        require(self.prompts==self.solutions==sequence,'all twelve prompt/solution pairs')
        require(set(self.sources)==SOURCE_IDS,'two method source IDs')
        require(not any(h.startswith(('chapters/','projects/','production/')) for h in self.links),'flat reader links')
        return self


def derive(audit):
    inputs={'subsistence':(1,2),'stone-prices':(4,1),'stone-income':14,'stone-new-prices':(9,1),
            'linear-target':6,'linear-prices':(2,4),'roy-point':(1,2,3),'share-coefficient':F(1,12),
            'share-prices':(1,1,1),'share-income':3,'construct-prices':(1,4,2),'construct-target':3,
            'construct-new-prices':(4,1,2),'producer-input-prices':(1,4),'producer-output-price':8,
            'entry-input-price':1,'entry-output-prices':(3,4,5,7)}
    result={};p=(F(4),F(1));m=F(14);x,u,J,xm=stone(p,m)
    S=add(J,outer(xm,x));result.update({'stone-choice':(x,u),'stone-jacobian':J,
            'stone-income-derivative':xm,'stone-slutsky':S})
    a,b=sqrt(p[1]/p[0]),sqrt(p[0]/p[1])
    compensated=((-u*a/(2*p[0]),u*a/(2*p[1])),(u*b/(2*p[0]),-u*b/(2*p[1])))
    audit.equal(S,compensated,'direct compensated derivatives versus chain rule')
    audit.equal(S,tuple(tuple(-v*w/8 for w in (F(1),F(-4))) for v in (F(1),F(-4))),'entire negative-square coefficient matrix')
    audit.equal((dot(p,x),mv(S,p)),(m,(0,0)),'budget and null price direction')
    newx,newu,_,_=stone((9,1),m);result['stone-new-choice']=(newx,newu)
    result['stone-losses']=(expenditure((9,1),u)[0]-m,m-expenditure(p,newu)[0])
    for target in (F(0),F(1,2),F(2)):
        e,h=expenditure(p,target)
        audit.equal(stone(p,e)[:2],(h,target),'both primal/dual witnesses including zero')
    audit.equal(stone((12,3),42)[:2],(x,u),'common money-unit scaling')
    audit.interventions+=1

    value,H=kink((2,4),6);result['linear-expenditure']=value;result['linear-endpoints']=H
    step=F(1,8)
    result['linear-slopes']=((value-kink((2-step,4),6)[0])/step,(kink((2+step,4),6)[0]-value)/step)
    for d in ((1,0),(-1,0),(0,1),(1,2),(2,-1)):
        moved=(2+step*d[0],4+step*d[1]);slope=(kink(moved,6)[0]-value)/step
        audit.equal(slope,min(dot(h,d) for h in H),'nonunique directional minimum')
        for t in (F(0),F(1,3),F(1)):
            h=tuple(t*a+(1-t)*b for a,b in zip(H[0],H[1]))
            audit.equal(kink(moved,6)[0]<=dot(moved,h),True,'every segment member supergradient')
    p1,p2,wealth=map(F,(1,2,3));z=wealth/p1-3
    result['roy-zero-derivatives']=(-3*wealth*z*z/(p1*p1),F(0),3*z*z/p1)
    result['roy-choice']=(wealth/p1,F(0));result['roy-valid-derivatives']=(-wealth/(p1*p1),F(0),1/p1)
    for wealth in (F(2),F(4)):
        z=wealth/p1-3;vm=3*z*z/p1;vp=-3*wealth*z*z/(p1*p1)
        audit.equal(-vp/vm,wealth/p1,'valid cube Roy division away from zero factor')
    audit.interventions+=1

    A=((0,1,-1),(-1,0,1),(1,-1,0));share=(F(1,3),)*3
    price_J=tuple(tuple(F(A[i][j],4)-int(i==j) for j in range(3)) for i in range(3))
    rotation=add(price_J,outer(share,(F(1),)*3))
    result['share-choice']=(F(1),)*3;result['share-slutsky']=rotation
    P=tuple(tuple(F(i==j)-F(1,3) for j in range(3)) for i in range(3))
    symmetric=tuple(tuple((rotation[i][j]+rotation[j][i])/2 for j in range(3)) for i in range(3))
    audit.equal(symmetric,tuple(tuple(-v for v in row) for row in P),'entire quadratic-form symmetric part')
    audit.equal(tuple(tuple(dot(row,col) for col in transpose(P)) for row in P),P,'orthogonal projection squared')
    audit.equal((mv(rotation,(1,1,1)),mv(transpose(rotation),(1,1,1))),((0,0,0),(0,0,0)),'both compensated price null directions')
    audit.equal(rotation[0][1]-rotation[1][0],F(1,2),'skew obstruction survives curvature checks')
    shares,demand=log_field((2,1,1),3);other=log_field((6,3,3),9)[1]
    audit.equal(all(1/4<v<5/12 for v in shares) and abs(sum(shares)-1)<1e-14,True,'log-domain positive shares and sum')
    audit.equal(abs(dot((2,1,1),demand)-3)<1e-13 and max(abs(a-b) for a,b in zip(demand,other))<1e-13,True,'off-anchor budget and scaling')
    audit.interventions+=1

    c,h,e=homothetic((1,4,2),3);result['construct-choice']=(c,h,e)
    result['construct-new-choice']=homothetic((4,1,2),3)[1]
    paths=((integral_coordinate(4,1,4,3),integral_coordinate(4,4,1,3)),
           (integral_coordinate(1,4,1,3),integral_coordinate(1,1,4,3)))
    result['construct-paths']=paths
    audit.equal(tuple(map(sum,paths)),(0,0),'antiderivative route gives equal compensated totals')
    audit.equal((dot((1,4,2),h),direct(h)),(e,F(3)),'constructive attainment')
    _,h2,e2=homothetic((9,1,2),4,1);result['alpha-transfer']=(h2,e2,direct(h2,1))
    audit.equal(dot((9,1,2),h2),e2,'alpha transfer expenditure')
    audit.equal(homothetic((1,4,2),0)[1:],((0,0,0),0),'zero target unique positive-price minimum')
    cscale=homothetic((3,12,6),3)[0]
    audit.equal(cscale,3*c,'degree-one primitive')
    audit.equal(cscale+1==3*(c+1),False,'constant cannot remain an expenditure primitive')
    # Positive price sequences illustrate each independently proved boundary case.
    for bundle,kind in (((4,9,20),'balanced'),((4,9,3),'third'),((0,9,3),'one_zero'),((0,0,3),'both_zero')):
        target=direct(bundle);errors=[]
        for n in (2,10,100):
            q=(F(9),F(4),F(1,n)) if kind=='balanced' else (F(1),F(1),F(n)) if kind=='third' else (F(n*n),F(1),F(1)) if kind=='one_zero' else (F(1),F(1),F(1,n))
            quotient=dot(q,bundle)/(2*sqrt(q[0]*q[1])+q[2])
            audit.equal(quotient>=target,True,'infimum lower bound at positive witness')
            errors.append(quotient-target)
        audit.equal(errors[0]>errors[1]>errors[2]>=0,True,'exact boundary witness error decreases')
    audit.interventions+=1

    output=production((1,4),8);gradient,Hess=profit_derivatives((1,4),8)
    result.update({'producer-choice':output,'producer-gradient':gradient,'producer-hessian':Hess,
                   'producer-swapped':production((4,1),8)})
    value=output[-1];prices=(F(1),F(4),F(8))
    audit.equal(gradient,(-output[1],-output[2],output[0]),'Hotelling net-input signs')
    audit.equal((dot(prices,gradient),mv(Hess,prices)),(value,(0,0,0)),'profit Euler and null direction')
    first=(-1/(2*prices[0]),-1/(2*prices[1]),1/prices[2]);second=(1/prices[0],-1/prices[1],F(0))
    squares=tuple(tuple(2*value*first[i]*first[j]+value*second[i]*second[j]/4 for j in range(3)) for i in range(3))
    audit.equal(Hess,squares,'every coefficient in full PSD square certificate')
    for q in (F(0),F(1,2),F(2)):
        k,l=2*q*q,q*q/2;cost=k+4*l
        audit.equal((k*l,cost),(q**4,4*q*q),'global conditional equality witness')
        audit.equal(8*q-cost,value-4*(q-output[0])**2,'completed-square global output certificate')
    audit.equal(production((1,4),0),(0,0,0,0,0),'zero output-price optimum')
    zerograd,zeroH=profit_derivatives((1,4),0)
    audit.equal((zerograd,zeroH[2][2]),((0,0,0),F(1,8)),'explicit boundary derivatives without dividing by r')
    step=F(1,8)
    audit.equal(2*production((1,4),step)[-1]/step**2,zeroH[2][2],'one-sided quadratic coefficient')
    scaled=production((3,12),24)
    audit.equal((scaled[:3],scaled[-1]),(output[:3],3*value),'producer quantities and profit units')
    audit.interventions+=1

    # Attainment/local boundedness/unique choice at p do not replace closedness.
    audit.equal(cost_without_closedness((1,1)),(F(3),(F(2),F(1))),'unique minimum at the counterexample price')
    for step in (F(1,20),F(1,100)):
        left=(3-cost_without_closedness((1-step,1))[0])/step
        right=(cost_without_closedness((1+step,1))[0]-3)/step
        audit.equal((left,right+step/4),(F(2),F(1)),'unequal limiting cost slopes despite attained nearby minima')
    for n in (2,10,100):
        t=F(1,n);point=(1-t,2+t+t*t)
        audit.equal(sum(point)-3,t*t,'omitted limit has the same base cost while every curve point costs more')
    audit.interventions+=1

    branches=[entry(1,r) for r in (3,4,5,7)]
    result['entry-profits']=tuple(v for v,_ in branches)
    result['entry-quantities']=tuple(tuple(y[1] for y in plans) if len(plans)>1 else plans[0][1] for _,plans in branches)
    q=F(3,2);result['entry-rejected-candidate']=(q,3*q-4-q*q)
    tied=entry(1,4)[1];result['entry-tied-supplies']=tied;result['entry-slopes']=tuple(y[1] for y in tied)
    result['capacity-gradient']=entry(1,6)[1][0]
    hole=tuple((a+b)/2 for a,b in zip(*tied));result['technology-hole']=hole;result['one-output-input']=4+hole[1]**2
    audit.equal(original_feasible(hole),False,'missing original feasible plan')
    audit.equal((-hole[0],hull_input(hole[1])),(F(4),F(4)),'mixture attains convexified input frontier')
    audit.equal(original_feasible((-5,1)),True,'one-output original minimum')
    for ratio in (F(3),F(39,10),F(4),F(41,10),F(5),F(59,10),F(6),F(61,10),F(7)):
        value,plans=entry(1,ratio)
        # Maximize the hull's two pieces independently: linear on [0,2],
        # then a completed-square parabola on [2,3].
        q2=max(F(2),min(F(3),ratio/2))
        support=max(F(0),2*ratio-8,ratio*q2-4-q2*q2)
        audit.equal(value,support,'original/hull support equality across every branch')
        audit.equal(all(dot((1,ratio),y)==value and original_feasible(y) for y in plans),True,'all original maximizing plans feasible')
        audit.equal(dot((1,ratio),hole)<=value,True,'positive-price inequality cannot detect hole')
    for t in (F(0),F(1,4),F(1,2),F(3,4),F(1)):
        plan=(-8*t,2*t)
        audit.equal(dot((1,4),plan),F(0),'entire convexified tied segment value')
        audit.equal(original_feasible(plan),t in (0,1),'original tied supply only endpoints')
    audit.equal(entry(3,12)[1],tied,'entry tie scale invariance')
    # Analytic first/second derivative behavior at the two boundaries.
    step=F(1,10)
    for dw,dr in ((F(0),F(1)),(F(0),F(-1)),(F(1),F(4))):
        kappa=dr-4*dw;actual=entry(1+step*dw,4+step*dr)[0]/step
        expected=F(0) if kappa<=0 else 2*kappa+step*kappa*kappa/(4*(1+step*dw))
        audit.equal(actual,expected,'entry directional support plus exact remainder')
    left=((6-step)**2/F(4)-4-5+3*step)/(step*step)
    right=(entry(1,6+step)[0]-5-3*step)/(step*step)
    audit.equal((left,right),(F(1,4),F(0)),'capacity matching gradient but unequal curvature')
    audit.interventions+=1
    return inputs,result


def rejection_checks(audit,html):
    for v in (True,False,None,'1',0.5,float('nan'),float('inf'),100001):audit.reject(lambda v=v:number(v),'exact scalar')
    for action in (lambda:sqrt(-1),lambda:sqrt(2),lambda:stone((0,1),14),lambda:stone((4,),14),
                   lambda:stone((4,1),5),lambda:expenditure((4,1),-1),lambda:kink((2,4),-1),
                   lambda:homothetic((1,4,2),1,0),lambda:homothetic((1,4,0),1),lambda:direct((-1,2,3)),
                   lambda:production((1,4),-1),lambda:entry(0,4),lambda:entry(1,0),lambda:hull_input(4),
                   lambda:log_field((3,1,1),3),lambda:log_field((1,1,1),0)):
        audit.reject(action,'bounded mathematical domain')
    for text in ('True','1/0','1+2','__import__("os")'):
        audit.reject(lambda text=text:numeric(text),'numeric grammar')
    for text in ('{"x":1,"x":2}','{"x":NaN}','{"x":1e999}'):
        audit.reject(lambda text=text:strict_json(text),'strict JSON')
    for a,b in [('id="v13-c02-ex1"','id="v13-c02-ex2"'),
                ('data-solution-for="v13-c02-ex1"','data-solution-for="v13-c02-ex2"'),
                ('class="solutions"','class="other"')]:
        def bad(a=a,b=b):
            doc=Page();doc.feed(html.replace(a,b,1));doc.finish()
        audit.reject(bad,'reader identity/pairing')
    audit.interventions+=1


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    paths=AUTHOR+(SELF,RECORD);before={p:(root/p).read_bytes() for p in paths};audit=Audit()
    peer=strict_json(before[RECORD].decode());bindings=peer['payload_bindings']
    audit.equal(len(bindings),5,'five nonself peer bindings')
    audit.equal({r['path'] for r in bindings},set(AUTHOR+(SELF,)),'exact binding scope')
    for row in bindings:
        blob=before[row['path']];audit.equal((len(blob),sha256(blob).hexdigest()),(row['bytes'],row['sha256']),'final bound payload')
    html=before[AUTHOR[0]].decode();doc=Page();doc.feed(html);doc.finish()
    inputs,expected=derive(audit)
    audit.equal(doc.inputs,inputs,'every original primitive input')
    audit.equal(set(doc.calcs),set(expected),'complete result marker inventory')
    for key,value in expected.items():audit.equal(doc.calcs[key],value,'visible '+key)
    audit.equal([row[0] for row in doc.branch_rows],['0<a<4','a=4','4<a<6','a≥6'],'every entry and capacity table region')
    for phrase in ('local nonsatiation','v<sub>m</sub>&gt;0','strictly positive prices suffice',
                   'no general boundary-continuity theorem','not a general global Marshallian-integrability theorem',
                   'a closed feasible input set'):
        audit.equal(phrase.lower() in html.lower(),True,'proof qualification '+phrase)
    for anchor in ('teach-answer','retention-answer','sources'):
        audit.equal('v13-c02-'+anchor in doc.ids,True,'answered instructional component')
    rejection_checks(audit,html)
    sources=strict_json(before[AUTHOR[2]].decode());audit.equal({s['id'] for s in sources['sources']},SOURCE_IDS,'source scopes')
    for source in sources['sources']:
        audit.equal(source['actual_primary_inspector'],'root','prior actual body inspector')
        audit.equal(doc.sources[source['id']],source['url'],'actual source hyperlink')
    author=strict_json(before[AUTHOR[3]].decode());ab=author['payload_bindings']
    audit.equal({r['path'] for r in ab},set(AUTHOR)-{AUTHOR[3]},'three author bindings')
    for row in ab:
        blob=before[row['path']];audit.equal((len(blob),sha256(blob).hexdigest()),(row['bytes'],row['sha256']),'author final bound payload')
    audit.equal({r['prompt'] for r in author['exercise_audit']},{'v13-c02-ex'+str(i) for i in range(1,13)},'all exact solution judgments')
    for path,blob in before.items():audit.equal((root/path).read_bytes(),blob,'unchanged six-file payload')
    summary={'chapter':'v13-c02','status':'separate peer checks passed','comparisons':audit.comparisons,
             'domain_rejections':audit.rejections,'intervention_groups':audit.interventions,
             'worked_cases':6,'solved_exercises':12,'primitive_inputs':len(inputs),'visible_results':len(expected),
             'runtime_payloads':6,'author_checker_imported':False,
             'limit':'Exact finite arithmetic complements separately reviewed global proofs, not empirical identification or statistical confidence.'}
    strict_json(json.dumps(summary,allow_nan=False));return summary


if __name__=='__main__':
    require(len(sys.argv)==1,'no CLI arguments')
    check()
