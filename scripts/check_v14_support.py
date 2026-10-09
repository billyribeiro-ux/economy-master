"""Quiet five-payload numerical/structural audit of V14 support tasks."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast,json,math
FILES=('content/assessments/parts/v14-support-opening.html','content/assessments/parts/v14-support-closing.html','scripts/check_v14_support.py','content/reviews/v14-support-sources.json','content/reviews/v14-support-author.json')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    require(type(x) in (int,float,F) and math.isfinite(float(x)),'finite scalar');return F(str(x)) if isinstance(x,float) else F(x)
def twodate(y,yp,R,beta):
    y,yp,R,beta=map(num,(y,yp,R,beta));require(min(y,yp,R,beta)>0,'positive household primitives');wealth=y+yp/R;c=wealth/(1+beta);return c,R*(wealth-c),y-c

def markov(p,q):
    p,q=map(num,(p,q));require(0<p<1 and 0<q<1,'interior Markov');return p/(p+q),1-p-q

def price(prob,m,X):
    prob,m,X=tuple(map(num,prob)),tuple(map(num,m)),tuple(map(num,X));require(len(prob)==len(m)==len(X)>0 and min(prob)>0 and sum(prob)==1 and min(m)>0,'pricing domain');P=sum(p*a*x for p,a,x in zip(prob,m,X));require(P>0,'positive price');Em=sum(p*a for p,a in zip(prob,m));ex=sum(p*x for p,x in zip(prob,X));ret=tuple(x/P for x in X);er=ex/P;vm=sum(p*(a-Em)**2 for p,a in zip(prob,m));vr=sum(p*(r-er)**2 for p,r in zip(prob,ret));return P,1/Em,er,er-1/Em,vm,vr

def bank(A,D,loss,cap):
    A,D,loss,cap=map(num,(A,D,loss,cap));require(A>0 and D>=0 and loss>=0 and cap>1 and A-loss>D,'solvent bank');post=A-loss;n=post-D;sale=max(F(0),post-cap*n);require(sale<=D,'debt repayment capacity');return post/n,sale,(post-sale,D-sale,n)

def collateral(y,yp,D,R,beta,nu,kappa,W):
    y,yp,D,R,beta,nu,kappa,W=map(num,(y,yp,D,R,beta,nu,kappa,W));require(y>0 and yp>0 and 0<=D<y and min(R,beta,nu)>0 and 0<=kappa<1 and W>=0,'collateral domain');a=y-D;u=(yp-beta*R*a)/(R*(1+beta));l=u if R<=kappa*nu else min(u,kappa*(y+nu*a)/(R-kappa*nu));kf=W+D-l;require(kf>=0,'funded foreign account');return l,a+l,yp-R*l,kf
class Read(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.prompts={};self.solutions=[];self.markers={};self.sources={};self.links=set()
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'data-points' in a:self.prompts[a['id']]=int(a['data-points'])
        if 'data-solution-for' in a:
            require(any(k=='details' and 'solutions' in d.get('class','').split() for k,d in self.stack),'disclosed solution');self.solutions.append(a['data-solution-for'])
        if 'data-check' in a:require(a['data-check'] not in self.markers,'unique marker');self.markers[a['data-check']]=''
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if t=='a':self.links.add(a.get('href',''))
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for _,a in self.stack:
            if 'data-check' in a:self.markers[a['data-check']]+=s
    def handle_endtag(self,t):require(self.stack and self.stack[-1][0]==t,'HTML nesting');self.stack.pop()
def parse(s):
    def walk(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric grammar')
    return walk(ast.parse(s.replace('−','-').strip(),mode='eval').body)
def check(root=None):
    b=Path(root) if root else Path(__file__).resolve().parents[1];raw={x:(b/x).read_bytes() for x in FILES};doc=Read();doc.feed(raw[FILES[0]].decode()+'\n'+raw[FILES[1]].decode());require(not doc.stack and len(set(doc.ids))==len(doc.ids),'balanced unique HTML');targets={**{f'v14-d{i}':5 for i in range(1,9)},**{f'v14-o{i}':4 for i in range(1,6)},**{f'v14-r{i}':10 for i in range(1,6)}};require(doc.prompts==targets and len(doc.solutions)==18 and set(doc.solutions)==set(targets),'18 exact scored pairs');require({'diagnostic','exam-rules','oral-transfer','retention','remediation','notation-index','concept-index','volume-synthesis','assessment-source-scope'}<=set(doc.ids),'supportanchors');require(all(f'v14-c{i:02}.html' in doc.links for i in range(1,13)),'all12routes')
    sources=json.loads(raw[FILES[3]]);require(doc.sources=={x['id']:x['url'] for x in sources['sources']},'source routes');record=json.loads(raw[FILES[4]]);require(set(record['exact_prompt_audit'])==set(targets),'full promptaudit');require(len(record['payload_bindings'])==4 and {x['path'] for x in record['payload_bindings']}==set(FILES[:4]),'nonself bindings')
    for x in record['payload_bindings']:require((len(raw[x['path']]),sha256(raw[x['path']]).hexdigest())==(x['bytes'],x['sha256']),'hash')
    count=rejects=0
    def eq(x,y,msg='comparison'):
        nonlocal count
        require(x==y,msg+': '+str(x)+' != '+str(y));count+=1
    c0,c1,s=twodate(10,F(121,10),F(11,10),1);mu,rho=markov(F(1,5),F(3,10));P,rf,er,prem,vm,vr=price((F(1,2),F(1,2)),(F(4,5),F(6,5)),(3,1));lev,sale,fin=bank(120,100,10,5);Pr,Rf,Er,Prem,Vm,Vr=price((F(1,4),F(3,4)),(2,F(2,3)),(1,3));base=collateral(2,5,1,1,1,1,F(1,5),4);stress=collateral(2,5,1,1,1,1,F(1,10),4)
    expected={'d1-consumption':(c0,c1),'d1-saving':s,'d2-choice-value-multiplier':(F(1),F(3),F(2)),'d3-probabilities':(F(1,5),F(1,5)+rho*F(1,5),mu),'d3-income':1+2*mu,'d4-price':P,'d4-returns':(er,prem),'d4-cov':P-2,'d5-leverage':lev,'d5-sales':sale,'d5-final':fin,'d6-mle':F(3,10),'d6-var':F(3,10)*F(7,10)/10,'d7-debt-surplus':(F(11)-3,(F(11)-3)*F(11,10)),'d7-backing':3/F(11,10)+F(44,5)/F(11,10)**2,'d8-fixed':F(1,5)/(1-F(3,5)),'d8-residual':F(3,5)-(F(1,5)+F(3,5)**2),'d8-bound':F(1,25)/(1-F(3,5)),'o3-values':(F(1),F(3,2),F(10),F(2),F(5,2)),'r1-growth':(F(2,5),F(4,5),F(6,5)),'r1-distribution-bound':F(1,25)/F(1,4),'r2-market':(F(9,25),F(3,5),F(5,3),F(1,4),F(9,100)),'r2-flow':F(61,125)*F(3,4)+F(1,5)*F(1,4)-F(2,5)*F(9,100),'r3-price':Pr,'r3-variance-premium':(Vm,Vr,Prem),'r3-debt-interval':(F(50),F(70)-10),'r4-loans':(base[0],stress[0]),'r4-base-c':base[1:3],'r4-stress-c':stress[1:3],'r5-payments':(F(1),F(3,2),F(7,4)),'r5-residual-bound':F(1,100)/F(1,2),'r5-payment-losses':(F(1,5),F(1,10),F(1,20)),'r5-mechanisms':((F(1,10)+F(4,100))/2,(F(1,10)-F(4,100))/2)}
    require(set(expected)|{'o1-invariant','o2-path'}==set(doc.markers),'all displayed output markers');eq(doc.markers['o1-invariant'],'(t/2,t/2,(1−t)/2,(1−t)/2)');eq(doc.markers['o2-path'],'(0,(1/2)ᵗb)')
    for key,want in expected.items():eq(parse(doc.markers[key]),want,key)
    # Primitive objective comparisons and full bounds, not displayed values alone.
    for i in range(21):
        x=F(i,20);require(4*x-x*x<=3,'global bound optimum');count+=1
    for i in range(21):
        I=F(i,10)
        if I+I*I/2<=3:require(-I-I*I/2+(6*(1+I)-(1+I)**2/2)/2<=F(7,2),'investment global objective');count+=1
    for t in (0,F(1,4),F(1,2),1):
        row=(t/2,t/2,(1-t)/2,(1-t)/2);eq(sum(row),1);Q=((F(1,2),F(1,2),0,0),(F(1,2),F(1,2),0,0),(0,0,F(1,2),F(1,2)),(0,0,F(1,2),F(1,2)));eq(tuple(sum(row[i]*Q[i][j] for i in range(4)) for j in range(4)),row)
    x=F(3,5);kap=F(2,5);r=F(1,10);sep=F(1,5);eta=F(1,2);y=F(61,125);home=F(1,5);theta=x*x;eq(kap*((r+sep)*x+eta*theta),(1-eta)*(y-home));J=kap*x;X=J;w=y-(r+sep)*J;U=(home+x*X)/r;eq((J,X,w,U),(F(6,25),F(6,25),F(52,125),F(86,25)));eq(w,home+eta*(y-home+kap*theta));eq(Prem*Prem/Vr,Vm/(sum(p*m for p,m in zip((F(1,4),F(3,4)),(2,F(2,3)))))**2)
    for d in (50,55,60):require(d>=50 and 60-d>=0,'renegotiation gains');count+=1
    for z in (base,stress):
        l,now,later,kf=z;eq(now+kf,6);eq(later+5,5+kf);require(1/now-1/later>0,'binding Euler');count+=1
    p=(F(1),F(3,2),F(7,4));loss=(F(1,5),F(1,10),F(1,20));eq(p[0]/2+p[1]/2+p[2],3);eq(loss[0]/2+loss[1]/2+loss[2],F(1,5));eq(sum(loss),F(7,20))
    invalid=[lambda:num(True),lambda:num(float('inf')),lambda:twodate(0,1,1,1),lambda:twodate(1,1,-1,1),lambda:markov(0,F(1,2)),lambda:markov(F(1,2),1),lambda:price((F(1,2),),(1,),(1,)),lambda:price((1,),(-1,),(1,)),lambda:price((1,),(1,),(0,)),lambda:bank(10,10,1,5),lambda:bank(120,100,10,1),lambda:collateral(2,5,2,1,1,1,F(1,5),4),lambda:collateral(2,5,1,1,1,1,1,4),lambda:collateral(2,5,0,1,1,1,F(9,10),0),lambda:parse('__import__("os")')]
    for fn in invalid:
        try:fn()
        except ValueError:rejects+=1
        else:raise ValueError('invalid domain accepted')
    return {'volume':'v14','component':'support','status':'passed','comparisons':count,'domain_rejections':rejects,'diagnostic_tasks':8,'oral_tasks':5,'retention_tasks':5,'score_totals':[40,20,50],'visible_result_markers':len(doc.markers),'runtime_files':5,'scope':'Original finite calculations and stated model/domain witnesses; full18solution/proof review separately recorded.'}
if __name__=='__main__':check()
