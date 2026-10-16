"""Original V15 diagnostic, oral and retention exact five-file audit."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast,json,math
FILES=('content/assessments/parts/v15-support-opening.html','content/assessments/parts/v15-support-closing.html','scripts/check_v15_support.py','content/reviews/v15-support-sources.json','content/reviews/v15-support-author.json')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    require(type(x)in(int,float,F) and math.isfinite(float(x)),'finite scalar');return F(str(x))
def market(A,c,t):
    A,c,t=map(num,(A,c,t));require(A>c>=0 and 0<=t<=A-c,'market domain');q=(A-c-t)/2;pb=A-q;ps=pb-t;cs=q*q/2;profit=ps*q-(c*q+q*q/2);rev=t*q;return q,pb,ps,rev,cs,profit,cs+profit+rev

def poverty(y,z):
    y=tuple(map(num,y));z=num(z);require(y and min(y)>=0 and z>0,'poverty domain');g=tuple(max(F(0),1-v/z) for v in y);return F(sum(x>0 for x in g),len(g)),sum(g)/len(g),sum(x*x for x in g)/len(g)
def gini(y):
    y=tuple(map(num,y));require(y and min(y)>=0 and sum(y)>0,'Gini domain');return sum(abs(x-v) for i,x in enumerate(y) for v in y[i+1:])/(len(y)*sum(y))
def cournot(n,A=20,c=4,fixed=9):
    require(type(n)is int and n>=1,'positive integer firms');A,c,fixed=map(num,(A,c,fixed));require(A>c>=0 and fixed>=0,'firm domain');q=(A-c)/(n+1);Q=n*q;p=A-Q;pi=(p-c)*q-fixed;W=(A-c)*Q-Q*Q/2-n*fixed;return q,Q,p,pi,W

def bayes(prior,like,other):
    prior,like,other=map(num,(prior,like,other));require(0<=prior<=1 and 0<=like<=1 and 0<=other<=1,'Bayes domain');prob=prior*like+(1-prior)*other;require(prob>0,'positive evidence');return prob,prior*like/prob

def pilot(reserve,fee=1,accuracy=F(3,4)):
    reserve,fee,accuracy=map(num,(reserve,fee,accuracy));require(reserve>=0 and 0<=fee<=reserve and F(1,2)<=accuracy<=1,'pilot domain');pay=((0,0),(8,-2),(3,4));cost=(0,4,2);base=[i for i in range(3) if cost[i]<=reserve];B=max(sum(pay[i])/2 for i in base);available=[i for i in range(3) if cost[i]<=reserve-fee];posts=(accuracy,1-accuracy);choices=[];values=[]
    for p in posts:
        vals={i:p*pay[i][0]+(1-p)*pay[i][1] for i in available};v=max(vals.values());choices.append(tuple(i for i,x in vals.items()if x==v));values.append(v)
    return B,tuple(choices),tuple(values),sum(values)/2-fee
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
    b=Path(root)if root else Path(__file__).resolve().parents[1];raw={x:(b/x).read_bytes()for x in FILES};doc=Read();doc.feed(raw[FILES[0]].decode()+'\n'+raw[FILES[1]].decode());require(not doc.stack and len(set(doc.ids))==len(doc.ids),'balanced unique HTML');targets={**{f'v15-d{i}':5 for i in range(1,9)},**{f'v15-o{i}':4 for i in range(1,6)},**{f'v15-r{i}':10 for i in range(1,6)}};require(doc.prompts==targets and len(doc.solutions)==18 and set(doc.solutions)==set(targets),'18 exact scored pairs');require({'diagnostic','exam-rules','oral-transfer','retention','remediation','notation-index','concept-index','volume-synthesis','assessment-source-scope'}<=set(doc.ids),'support anchors');require(all(f'v15-c{i:02}.html'in doc.links for i in range(1,13)),'all12routes');sources=json.loads(raw[FILES[3]]);require(doc.sources=={x['id']:x['url']for x in sources['sources']},'source routes');record=json.loads(raw[FILES[4]]);require(set(record['exact_prompt_audit'])==set(targets),'full prompt audit');require({x['path']for x in record['payload_bindings']}==set(FILES[:4]),'nonself bindings')
    for x in record['payload_bindings']:require((len(raw[x['path']]),sha256(raw[x['path']]).hexdigest())==(x['bytes'],x['sha256']),'hash')
    n=0
    def eq(a,z):
        nonlocal n
        if isinstance(z,(tuple,list)):
            require(isinstance(a,(tuple,list))and len(a)==len(z),'shape')
            for x,y in zip(a,z):eq(x,y)
        else:require(a==z,'numeric '+str((a,z)));n+=1
    m=market(12,2,2);free=market(12,2,0);prob,post=bayes(F(1,3),F(3,4),F(1,4));pop=poverty((1,3,6),4);low=9-F(13,5)**2;high=9-F(7,5)**2;sub=4-low;pol=pilot(5);tight=pilot(4);c4=cournot(4)
    expected={'d1-market':m[:4],'d1-welfare':(*m[4:],free[-1]-m[-1]),'d2':(2,8,2),'d3':(prob,post),'d4':(F(2)/F(2,5),F(3,2)/F(2,5)),'d5':pop,'d6':(F(4,5)*5,F(4,5)*5+F(1,5)*10),'d7':(10-6+3,-3,10-6,7,-F(18,5),F(17,5)),'d8':(gini((1,3,5)),gini((3,5,7)),gini((2,6,10))),'o1':(2,F(8,3),8*2-F(3,2)*4,F(32,3),F(2,3)),'o2':(6,2,4,5,3,2,20,19,1),'o3':(bayes(F(1,2),F(3,5),F(1,5))[1],F(3,4),bayes(F(3,4),F(3,5),F(1,5))[1]),'o4':(1-F(4,5)*F(1,5),F(3,4),F(9,100),F(4,5)/(F(4,5)+2*F(1,5))),'o5':(6-2-3,2-2,3,6+2-4,2*(6-2-3)+2-2+3),'r1':(2,6,3,1,18,2,15,7),'r2-welfare':tuple(cournot(k)[-1]for k in(1,2,4)),'r2-entry':(4,c4[1],c4[3]),'r2-planner':(1,16,16*16-16**2/2-9),'r3-poverty':(2,poverty((3,3),4)[2],1,poverty((2,4),4)[0],poverty((3,3),4)[1]),'r3-bounds':(3-F(1,2),3+F(1,2)+1),'r4-insurance':(low,high,F(32,5),F(1,2),sub),'r4-care':(F(9,2),4,F(63,8),8,F(1,8),F(9,4),F(9,4)),'r5-basic':(0,3,F(7,2),8,6,5),'r5-pilot':(F(6,11),F(3,4),F(1,4),pol[3]+1,pol[3],pol[3]-pol[0],6,6-F(7,2),pol[3]+1-pol[0]),'r5-reserve':(tight[3],tight[0])}
    require(set(expected)==set(doc.markers),'every displayed result');
    for k,v in expected.items():eq(parse(doc.markers[k]),v)
    # Quantity and true welfare accounts under alternative tax wedges.
    for t in(0,1,2,4,8,10):
        q,pb,ps,rev,cs,profit,W=market(12,2,t);eq(pb*q,ps*q+rev);eq(profit,ps*q-(2*q+q*q/2));eq(W,10*q-q*q);eq(free[-1]-W,F(t*t,4))
    for j in range(21):
        x=F(j,10);require(6*x-x*x<=8,'global upper boundary');n+=1
    # Individual and aggregate voting objectives and every challenger side.
    for j in range(33):
        G=F(j,4);require(8*G-F(3,2)*G*G<=F(32,3),'planner concavity');n+=1
        if G!=2:require(sum(a*2-F(4,2)>a*G-G*G/2 for a in(1,2,5))>=2,'majority');n+=1
    for y in((1,3,5),(0,0,3),(2,2,2)):
        eq(gini(tuple(3*x for x in y)),gini(y));require(gini(tuple(x+2 for x in y))<=gini(y),'positive uniform income');n+=1
    for j in range(41):
        q=F(j,40);p=F(4,5);score=p*(1-(1-q)**2)+(1-p)*(1-q*q);eq(score,1-p*(1-p)-(q-p)**2);require(score<=F(21,25),'global scoring');weighted=p*(1-(1-q)**2)+2*(1-p)*(1-q*q);best=p*(1-F(1,3)**2)+2*(1-p)*(1-F(2,3)**2);require(weighted<=best,'state-weighted scoring');n+=2
    for t in(2,6):
        L=F(8-t,2);eq(t*L,6);eq((8-t)*L+6,8*L);eq((8-t)*L-L*L+6,8*L-L*L)
        for j in range(33):
            x=F(j,4);require((8-t)*x-x*x<=(8-t)*L-L*L,'global labor');n+=1
    entrants=[]
    for k in range(1,11):
        q,Q,p,pi,W=cournot(k);eq(W,Q*Q/2+k*pi);eq(q,max(F(0),(16-(k-1)*q)/2))
        if pi>=0 and cournot(k+1)[3]<=0:entrants.append(k)
        require(128-9*k<=119,'planner plant count');n+=1
    eq(entrants,[4]);eq(poverty((3,3),4)[1],poverty((2,4),4)[1])
    for j in range(21):
        x=1+F(j,20);vals=poverty((1+x,5-x),4);require(vals[2]>=F(1,16)and vals[0]>=F(1,2),'global poverty objectives');n+=1
    corners=[3-d+s for d in(-F(1,2),F(1,2))for s in(0,1)];eq((min(corners),max(corners)),(F(5,2),F(9,2)))
    eq(sub/3,F(44,75));eq(sum(F(v)>sub/3 for v in(0,F(1,2),2)),1)
    for premium in(0,low,F(4),F(32,5),high,F(8)):
        mass=F(premium<=low,2)+F(premium<=high,2);claims=F(4,5)*(premium<=low)+F(16,5)*(premium<=high)
        if 0<mass and premium<F(32,5):require(premium*mass-claims<0,'no profitable undercut');n+=1
        if premium==F(32,5):eq(premium*mass,claims)
    for j in range(21):
        q=F(j,4);benefit=5*q-q*q/2;require(benefit-q<=8 and benefit-q/2<=F(81,8),'care global');n+=2
    eq(pol[1],((1,),(2,)));eq(tight[1],((2,),(2,)));eq(pol[2],(F(11,2),F(15,4)));eq(pilot(5,1,F(1,2))[3],F(5,2));eq(pilot(5,1,1)[3],5)
    for p in(F(0),F(1,4),F(6,11),F(3,4),F(1)):
        a=10*p-2;bb=4-p;require((a>=bb)==(p>=F(6,11)),'complete contingent comparison');n+=1
    # Exhaust all fixed mappings from two signals to three actions, respecting cash.
    for reserve in(4,5):
        candidates=[]
        for positive in range(3):
            for negative in range(3):
                costs=(0,4,2);pay=((0,0),(8,-2),(3,4))
                if max(costs[positive],costs[negative])+1<=reserve:candidates.append((F(3,4)*pay[positive][0]+F(1,4)*pay[positive][1]+F(1,4)*pay[negative][0]+F(3,4)*pay[negative][1])/2-1)
        eq(max(candidates),pilot(reserve)[3])
    invalid=[lambda:num(True),lambda:num(float('nan')),lambda:num(float('inf')),lambda:market(2,3,1),lambda:market(12,2,-1),lambda:market(12,2,11),lambda:poverty((),4),lambda:poverty((-1,3),4),lambda:poverty((1,3),0),lambda:gini((0,0)),lambda:gini((-1,3)),lambda:cournot(0),lambda:cournot(True),lambda:cournot(2,fixed=-1),lambda:bayes(2,1,1),lambda:bayes(0,1,0),lambda:pilot(-1),lambda:pilot(1,2),lambda:pilot(5,1,F(1,4)),lambda:parse('__import__("os")')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'volume':'v15','component':'support','status':'passed','comparisons':n,'domain_rejections':len(invalid),'diagnostic_tasks':8,'oral_tasks':5,'retention_tasks':5,'score_totals':[40,20,50],'visible_result_markers':len(doc.markers),'runtime_files':5,'scope':'Original finite choices, all displayed outputs, global witnesses and all pilot policies; analytical proofs and qualitative answers reviewed separately.'}
if __name__=='__main__':check()
