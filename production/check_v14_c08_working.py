"""Finite investment and financing laboratory; four files, quiet API/CLI."""
import ast
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from html import unescape
import json,re
from math import isfinite,sqrt
from pathlib import Path
FILES=('production/v14-c08-working.html','production/check_v14_c08_working.py','production/v14-c08-sources-working.json','production/v14-c08-author-review-working.json')
def require(ok,message):
    if not ok:raise ValueError(message)
def scalar(x):
    require(type(x) in (int,float,F) and isfinite(float(x)),'finite numeric scalar');return float(x)
def investment(a,b,R,phi,K0,delta,cap):
    a,b,R,phi,K0,delta,cap=map(scalar,(a,b,R,phi,K0,delta,cap))
    require(a>0 and b>0 and R>0 and phi>0 and K0>=0 and 0<=delta<=1 and cap>=0,'investment domain')
    i=min(cap,max(0,(a-b*(1-delta)*K0-R)/(R*phi+b)));k=(1-delta)*K0+i
    return i,k,(a-b*k)/R,(a-b*k/2)/R

def agency(I,Y,ph,pl,benefit,R):
    I,Y,ph,pl,benefit,R=map(scalar,(I,Y,ph,pl,benefit,R))
    require(I>0 and Y>0 and 0<=pl<ph<=1 and benefit>=0 and R>0,'agency domain')
    reward=benefit/(ph-pl);require(reward<=Y,'effort infeasible')
    pledge=ph*(Y-reward);return reward,pledge,max(0,I-pledge/R)
def collateral(A,theta,n):
    A,theta,n=map(scalar,(A,theta,n));require(A>0 and 0<=theta<1 and n>=0,'collateral domain')
    cap=((theta*A+sqrt(theta*theta*A*A+4*n))/2)**2;i=min(A*A/4,cap);out=A*sqrt(i);loan=max(i-n,0);saved=max(n-i,0)
    return i,out,loan,out-loan+saved,cap

def dynamic(n,W,R,lam,s,As):
    n,W,R,lam,s=map(scalar,(n,W,R,lam,s));As=tuple(map(scalar,As));require(n>0 and W>=0 and R>0 and 0<=lam<1 and 0<s<1 and len(As)>0 and min(As)>R,'dynamic domain')
    rows=[]
    for t,A in enumerate(As):
        i=n/(1-lam);loan=i-n;require(loan<=W+1e-12,'outside funding insufficient');e=A*i-R*loan;div=e if t==len(As)-1 else (1-s)*e;nn=0 if t==len(As)-1 else s*e;output=A*i+R*(W-loan)
        rows.append((n,i,loan,e,div,nn,output,R*W));n=nn;W*=R
    return rows

class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.worked=[];self.prompts=[];self.solutions=[];self.markers={};self.sources={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in q.get('class','').split() for t,q in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in q.get('class','').split() for t,q in self.stack),'undisclosed answer');self.solutions.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for attr in ('data-calc','data-input'):
            if attr in a:
                require(a[attr] not in self.markers,'duplicate marker');self.markers[a[attr]]=[attr,'']
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,text):
        for _,a in self.stack:
            for attr in ('data-calc','data-input'):
                if attr in a:self.markers[a[attr]][1]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting');self.stack.pop()
def parse(s):
    def walk(n):
        if isinstance(n,ast.Constant):return scalar(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric marker syntax')
    return walk(ast.parse(s.strip(),mode='eval').body)

def check(root=None):
    b=Path(root) if root is not None else Path(__file__).resolve().parents[1];payload={p:(b/p).read_bytes() for p in FILES};html=payload[FILES[0]].decode();doc=Read();doc.feed(html)
    require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'HTML structure');require(all(x.startswith('v14-c08-') for x in doc.ids),'scoped IDs')
    target=[f'v14-c08-e{i}' for i in range(1,13)];require(doc.prompts==doc.solutions==target,'12 exact pairs');require(doc.worked==[f'v14-c08-w{i}' for i in range(1,6)],'five cases')
    sources=json.loads(payload[FILES[2]]);require(doc.sources=={s['id']:s['url'] for s in sources['sources']},'source routes');rev=json.loads(payload[FILES[3]])
    require(set(rev['exact_prompt_solution_audit'])==set(target),'every prompt reviewed');require(len(rev['payload_bindings'])==3 and {x['path'] for x in rev['payload_bindings']}==set(FILES[:3]),'three author bindings')
    for item in rev['payload_bindings']:require((len(payload[item['path']]),sha256(payload[item['path']]).hexdigest())==(item['bytes'],item['sha256']),'bound author payload')
    values={k:parse(v[1]) for k,v in doc.markers.items()};count=0;rejections=0
    def near(x,y,label='comparison',tol=6e-11):
        nonlocal count
        if isinstance(y,(tuple,list)):
            require(isinstance(x,(tuple,list)) and len(x)==len(y),label+' shape')
            for xx,yy in zip(x,y):near(xx,yy,label,tol)
        else:
            require(isfinite(float(x)) and abs(float(x)-float(y))<tol*max(1,abs(float(y))),f'{label}: {x} != {y}');count+=1
    q=investment(3,1,1.05,2,1,.1,2);aq=agency(100,180,.8,.4,20,1.1);col=collateral(4,.2,.2);colnew=collateral(4,.2,1.28);q2=investment(2,1,1.05,2,1,.1,2);cap2=investment(2,1,1.05,2,1,.1,.01);a4=agency(100,180,.8,.4,24,1.1);c6=collateral(4,.25,.75)
    normal=dynamic(1,10,1,.5,.75,(1.2,1.2,1.2));shock=dynamic(1,10,1,.5,.75,(1.1,1.2,1.2));unlevered=dynamic(1,10,1,0,.75,(1.2,1.2,1.2));unleveredshock=dynamic(1,10,1,0,.75,(1.1,1.2,1.2));d9=dynamic(1,10,1,.5,.5,(1.2,1.2,1.2));d11=dynamic(1,10,1,.75,.75,(1.2,1.2))
    expected={'q-investment':q[0],'q-capital':q[1],'q-marginal':q[2],'q-average':q[3],
              'agency-reward':aq[0],'agency-pledge':aq[1],'agency-min-n':aq[2],'agency-surplus':.8*180-1.1*100,'agency-success-debt':1.1*90/.8,'agency-success-equity':180-1.1*90/.8,'agency-ic-slack':.4*(180-1.1*90/.8)-20,
              'collateral-i':col[0],'collateral-b':col[2],'collateral-wealth':col[3],'collateral-derivative':1/(1-.2*2),'collateral-shadow':(2-1)/(1-.2*2),'collateral-new-i':colnew[0],'collateral-threshold':4-.2*4*2,
              'overhang-equity':max(80+25-100,0)-max(80-100,0)-15,'overhang-surplus':25-15,'overhang-interval':(80,80+25-15),
              'dynamic-growth':normal[0][5],'dynamic-shock-growth':shock[0][5],'dynamic-investment-gaps':tuple(normal[j][1]-shock[j][1] for j in (1,2)),'dynamic-unlevered-cash-gap':unlevered[0][5]-unleveredshock[0][5],
              'e2-i':q2[0],'e2-k':q2[1],'e2-q':q2[2],'e2-cap-q':cap2[2],'e4-reward':a4[0],'e4-pledge':a4[1],'e4-n':a4[2],'e5-surplus':.8*180-1.1*108,'e5-debt':1.1*103/.8,
              'e6-i':c6[0],'e6-b':c6[2],'e6-wealth':c6[3],'e6-threshold':4-.25*4*2,'e8-interval':(80,80+20-15),'e8-face':(80+85)/2,'e9-growth':d9[0][5],'e9-cash':(d9[0][5],d9[1][5]),
              'e10-normal-output':normal[1][6],'e10-stress-output':shock[1][6],'e11-i':d11[0][1],'e11-b':d11[0][2],'e11-equity':d11[0][3],'e11-cash':d11[0][5]}
    require(set(values)==set(expected),'all displayed results')
    for key,value in expected.items():near(values[key],value,key)
    # Parse the actual visible table cells, not a copied output dictionary.
    table=re.search(r'<tbody>(.*?)</tbody>',html,re.S).group(1);rows=re.findall(r'<tr>(.*?)</tr>',table,re.S)
    labels=('Normal initial cash','Normal investment','Normal loan','Normal owner dividend','Stressed initial cash','Stressed investment','Stressed loan','Stressed owner dividend')
    require(len(rows)==len(labels),'dynamic table rows')
    for j,(row,label) in enumerate(zip(rows,labels)):
        heading=re.search(r'<th>(.*?)</th>',row,re.S).group(1);require(heading==label,'table row heading');cells=[float(x) for x in re.findall(r'<td>(.*?)</td>',row,re.S)];path=normal if j<4 else shock;column=(0,1,2,4)[j%4];near(cells,[r[column] for r in path],label)
    # Exact rational checks and global concavity with lower/interior/upper investment regimes.
    near(q,(F(21,62),F(192,155),F(52,31),F(492,217)));near(q2[:3],(F(1,62),F(142,155),F(32,31)))
    for a,cap in ((1,2),(2,2),(3,2),(3,.2),(10,2)):
        i,k,marg,avg=investment(a,1,1.05,2,1,.1,cap)
        def obj(x):kk=.9+x;return -x-x*x+(a*kk-kk*kk/2)/1.05
        for f in (0,.1,.4,.9,1):require(obj(i)>=obj(cap*f)-1e-12,'global investment optimum');count+=1
        der=marg-1-2*i
        require((abs(der)<1e-12) or (i==0 and der<=0) or (i==cap and der>=0),'KKT direction');count+=1
    # Entire incentive-feasible contract boundary, not just surplus arithmetic.
    for benefit in (10,20,24,40):
        reward,pledge,nmin=agency(100,180,.8,.4,benefit,1.1)
        near(.4*reward,benefit)
        if nmin>0:near(1.1*(100-nmin),pledge)
        for rewardplus in (reward,min(180,reward+10)):
            require(.8*(180-rewardplus)<=pledge+1e-12,'max pledge over incentive contracts');count+=1
    # Collateral feasibility, cap equation, global optimum and wealth resource budget over regimes.
    for A,theta,n in ((4,.2,0),(4,.2,.2),(4,.2,1.28),(4,.2,2.4),(4,.2,5),(4,0,0),(4,0,1),(4,.75,0),(3,.1,.5)):
        i,out,loan,wealth,cap=collateral(A,theta,n);near(cap,n+theta*A*sqrt(cap));require(loan<=theta*out+1e-12,'pledgeable loan');count+=1
        near(wealth+loan,out+max(n-i,0))
        for fraction in (0,.2,.5,1):
            alt=fraction*cap;require(out-i>=A*sqrt(alt)-alt-1e-11,'global collateral optimum');count+=1
    h=1e-6;cp=collateral(4,.2,.2+h);cm=collateral(4,.2,.2-h);near((cp[0]-cm[0])/(2*h),5/3,tol=1e-8);near((cp[3]-cm[3])/(2*h),8/3,tol=1e-8)
    # Old creditor/owner gains sum to project surplus at all feasible renegotiated faces.
    for z in (20,25):
        for face in (80,(80+80+z-15)/2,80+z-15):
            creditor=face-80;owner=80+z-face-15;require(min(creditor,owner)>=0,'bargaining participation');near(creditor+owner,z-15)
    # Both-sector goods and finance at every date, including terminal liquidation.
    for path in (normal,shock,unlevered,unleveredshock,d9,d11):
        for j,row in enumerate(path):
            n,i,loan,e,div,nn,out,lender=row;near(n+loan,i);near(div+nn,e);near(e+lender,out)
            if j<len(path)-1:near(nn,path[j+1][0])
            else:near(nn,0);near(div,e)
    bad=(lambda:investment(3,1,0,2,1,.1,2),lambda:investment(3,1,1,0,1,.1,2),lambda:investment(3,1,1,2,1,2,2),lambda:agency(100,180,.4,.8,20,1),lambda:agency(100,180,.8,.4,100,1),lambda:collateral(0,.2,1),lambda:collateral(4,1,1),lambda:collateral(4,.2,-1),lambda:dynamic(1,10,1,1,.75,(1.2,)),lambda:dynamic(1,.5,1,.5,.75,(1.2,)),lambda:dynamic(1,10,1,.5,.75,(.9,)),lambda:dynamic(1,10,1,.5,0,(1.2,)),lambda:scalar(True),lambda:scalar(float('inf')))
    for fn in bad:
        try:fn()
        except ValueError:rejections+=1
        else:raise ValueError('invalid domain accepted')
    return {'chapter':'v14-c08','status':'passed','comparisons':count,'domain_rejections':rejections,'worked_examples':5,'solutions':12,'result_markers':len(values),'table_cells':24,'runtime_files':4}

if __name__=='__main__':
    check()

