"""Six original graduate oral defenses; exactly five portable author files."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from math import isfinite
import ast,json,itertools
FILES=('content/cross-assessments/parts/graduate-support-opening.html','content/cross-assessments/parts/graduate-support-closing.html','scripts/check_graduate_support.py','content/reviews/graduate-support-sources.json','content/reviews/graduate-support-author.json')
def need(x,msg):
    if not x:raise ValueError(msg)
def num(x):need(type(x)in(int,float,F)and isfinite(float(x)),'finite scalar');return F(str(x))
def sensitivity(delta,pi,bound):
    delta,pi,bound=map(num,(delta,pi,bound));need(pi!=0 and bound>=0,'sensitivity domain');v=((delta-bound)/pi,(delta+bound)/pi);return tuple(sorted(v))
def policy(means,cost,error):
    means=tuple(map(num,means));cost,error=map(num,(cost,error));need(len(means)==4 and all(0<=x<=1 for x in means) and cost>=0 and error>=0,'policy domain');th=means[0]-means[1];tl=means[2]-means[3];values=(F(0),(th-cost)/2,(th+tl)/2-cost);bounds=((F(0),F(0)),(values[1]-error,values[1]+error),(values[2]-2*error,values[2]+2*error));return values,bounds

def information(prior,accuracy,fee):
    prior,accuracy,fee=map(num,(prior,accuracy,fee));need(0<prior<1 and F(1,2)<=accuracy<=1 and fee>=0,'information domain');ps=prior*accuracy+(1-prior)*(1-accuracy);need(0<ps<1,'signal probability');post1=prior*accuracy/ps;post0=prior*(1-accuracy)/(1-ps);gross=ps*post1**2+(1-ps)*post0**2;return (post0,post1),gross,gross-fee-prior**2

def auctions(low,high,prob,cost,reserve,correlated=False):
    low,high,prob,cost,reserve=map(num,(low,high,prob,cost,reserve));need(0<=low<high and 0<prob<1 and cost>=0 and reserve>=0,'auction domain');rev=F(0);val=F(0)
    states=[((low,low),1-prob),((high,high),prob)] if correlated else [(v,(prob if v[0]==high else 1-prob)*(prob if v[1]==high else 1-prob))for v in itertools.product((low,high),repeat=2)]
    for (v1,v2),p in states:
        if max(v1,v2)>=reserve:rev+=p*max(reserve,min(v1,v2));val+=p*max(v1,v2)
    return rev,val-2*cost

def certificate(beta,reward,residual):
    beta,reward,residual=map(num,(beta,reward,residual));need(0<=beta<1 and min(reward,residual)>=0,'certificate domain');E=(reward+residual)/(1-beta);return E,2*(reward+beta*E)
def guarantee(prob,m0,m1,x0,x1,D):
    prob,m0,m1,x0,x1,D=map(num,(prob,m0,m1,x0,x1,D));need(0<prob<1 and min(m0,m1)>0 and min(x0,x1,D)>=0,'guarantee domain');need(prob*m0+(1-prob)*m1==1,'unit safe price');price=lambda v:prob*m0*v[0]+(1-prob)*m1*v[1];g=(max(F(0),D-x0),max(F(0),D-x1));eq=(max(F(0),x0-D),max(F(0),x1-D));reserve=max(g);gp=price(g);ic=reserve-gp;need(ic>=0,'funded insurer capital');return price((x0,x1)),gp,price(eq),ic

class Read(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.prompts={};self.solutions=[];self.markers={};self.sources={};self.links=set()
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:need(a['id']not in self.ids,'unique ID');self.ids.add(a['id'])
        if 'data-points'in a:self.prompts[a['id']]=int(a['data-points'])
        if 'data-solution-for'in a:
            need(any(k=='details'and 'solutions'in d.get('class','').split()for k,d in self.stack),'solution disclosure');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        if t=='a':self.links.add(a['href'])
        for k in('data-input','data-check'):
            if k in a:need(a[k]not in self.markers,'unique marker');self.markers[a[k]]=''
        if t not in('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_endtag(self,t):need(bool(self.stack)and self.stack.pop()[0]==t,'balanced HTML')
    def handle_data(self,s):
        for _,a in self.stack:
            for k in('data-input','data-check'):
                if k in a:self.markers[a[k]]+=s

def parse(s):
    def w(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(w(x)for x in n.elts)
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,ast.UnaryOp)and isinstance(n.op,ast.USub):return -w(n.operand)
        if isinstance(n,ast.BinOp)and isinstance(n.op,ast.Div):return w(n.left)/w(n.right)
        raise ValueError('numeric syntax')
    return w(ast.parse(s.split('=')[-1].strip(),mode='eval').body)
def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];p=Read()
    for x in FILES[:2]:p.feed((root/x).read_text())
    p.close();need(not p.stack and len(p.prompts)==6 and all(v==10 for v in p.prompts.values())and set(p.solutions)==set(p.prompts)and len(p.solutions)==6,'six scored solved tasks')
    for i in range(1,13):
        for v in ['v12','v13','v14']:need(f'{v}-c{i:02d}.html'in p.links,'complete remediation routes')
    r=json.loads((root/FILES[-1]).read_text());need(len(r['payload_bindings'])==4,'four bindings')
    for x in r['payload_bindings']:
        f=root/x['path'];need(f.stat().st_size==x['bytes']and sha256(f.read_bytes()).hexdigest()==x['sha256'],'frozen payload')
    need(set(x['path']for x in r['payload_bindings'])==set(FILES[:-1]),'nonself runtime binding')
    sources=json.loads((root/FILES[-2]).read_text());need(p.sources=={x['id']:x['url']for x in sources['sources']},'source routes')
    n=0
    def eq(x,y):
        nonlocal n
        if isinstance(y,(tuple,list)):
            need(isinstance(x,(tuple,list))and len(x)==len(y),'numeric shape')
            for a,b in zip(x,y):eq(a,b)
        else:need(abs(float(x)-float(y))<1e-11,'numeric result');n+=1
    i={k:parse(p.markers['oral-'+k+'-inputs'])for k in ('e1','e2','m1','m2','a1','a2')}
    expected_inputs={'e1':(F(1,50),F(1,10),F(1,200),F(-1,100),F(1,100)),'e2':((F(4,5),F(2,5),F(2,5),F(1,2)),F(3,10),F(1,25),F(3,50)),'m1':(F(1,2),F(1,10),F(3,4),F(1,20)),'m2':(1,3,F(1,2),F(2,5),1,2),'a1':(F(4,5),F(3,1000),F(1,500),F(3,100),F(1,20),F(1,2000)),'a2':(F(1,2),F(6,5),F(4,5),1,3,2)}
    for k,v in expected_inputs.items():eq(i[k],v)
    d,pi,g,pl,pu=i['e1'];means,cost,err,err2=i['e2'];pv,pb=policy(means,cost,err);prior,perfectfee,acc,noisefee=i['m1'];low,high,prob,acost,r1,r2=i['m2'];a=auctions(low,high,prob,acost,r1);bb=auctions(low,high,prob,acost,r2);ca=auctions(low,high,prob,acost,r1,True);cb=auctions(low,high,prob,acost,r2,True);beta,reward,residual,gap1,gap2,reward2=i['a1'];gg=guarantee(*i['a2'])
    vals={'oral-e1-set':sensitivity(d,pi,g),'oral-e1-threshold':d/pu,'oral-e2-values':pv,'oral-e2-bounds':pb,'oral-m1-perfect':information(prior,1,perfectfee)[2],'oral-m1-noisy':information(prior,acc,noisefee)[2],'oral-m2-iid':(a[0],bb[0],a[1],bb[1]),'oral-m2-correlated':(ca[0],cb[0],ca[1],cb[1]),'oral-a1-base':certificate(beta,reward,residual),'oral-a1-changed':certificate(beta,reward2,residual),'oral-a2-prices':gg,'oral-a2-subsidy':gg[1]}
    for k,v in vals.items():eq(parse(p.markers[k]),v)
    need(set(p.markers)==set(vals)|{'oral-'+k+'-inputs'for k in i},'all displayed results checked')
    # Sharp endpoints, joint value guarantees, full bid deviations and accounting.
    for gam in(-g,0,g):need(sensitivity(d,pi,g)[0]<=(d-gam)/pi<=sensitivity(d,pi,g)[1],'sensitivity endpoints');n+=1
    for pp in(pl,pl/2,pu/2,pu):need(abs(d/pp)>=d/pu,'unbounded set witness');n+=1
    for signs in itertools.product((-1,1),repeat=4):
        m=[x+err*s for x,s in zip(means,signs)];v,_=policy(m,cost,0)
        for value,(lo,hi)in zip(v,pb):need(lo<=value<=hi,'joint policy event');n+=1
    changed=policy(means,cost,err2)[1];need(changed[1][0]<0 and changed[2][1]<0,'changed policy certificate');n+=1
    for precision in(F(1,2),F(3,4),F(1)):
        posts,gross,gain=information(prior,precision,0);eq(gross-prior**2,gain)
        for post in posts:
            for action in(0,F(1,4),F(1,2),F(3,4),1):need(post**2>=2*post*action-action**2,'global information action');n+=1
    def payoff(value,bid,rival,reserve):
        wins=bid>=reserve and bid>=rival # fixed identity chooses this bidder in ties
        return value-max(reserve,rival)-acost if wins else -acost
    for value,reserve,rival in itertools.product((low,high),(r1,r2),(0,1,2,3,F(18,5))):
        for bid in(0,1,2,3,F(18,5)):need(payoff(value,value,rival,reserve)>=payoff(value,bid,rival,reserve),'truthful deviation');n+=1
    E,G=certificate(beta,reward,residual);eq(E,residual+reward+beta*E);need(gap1<G<gap2,'original gaps');n+=1
    E2,G2=certificate(beta,reward2,residual);need(G2<gap1,'refined gap');n+=1
    asset,gp,equity,capital=gg;eq(asset+gp,2+equity);eq(gp+capital,1);eq((2-asset)+equity,gp);eq(1-capital,gp)
    bad=[lambda:sensitivity(1,0,1),lambda:sensitivity(1,1,-1),lambda:policy((1,2,0,1),1,0),lambda:policy((1,0,0,1),1,-1),lambda:information(0,1,0),lambda:information(F(1,2),F(1,4),0),lambda:information(F(1,2),1,-1),lambda:auctions(3,1,F(1,2),0,1),lambda:auctions(1,3,1,0,1),lambda:auctions(1,3,F(1,2),-1,1),lambda:certificate(1,0,0),lambda:certificate(F(1,2),-1,0),lambda:certificate(F(1,2),0,-1),lambda:guarantee(F(1,2),1,2,1,3,2),lambda:guarantee(F(1,2),-1,3,1,3,2),lambda:guarantee(1,1,1,1,3,2),lambda:num(float('nan')),lambda:parse('1+2')]
    for f in bad:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    out={'assessment':'graduate-qualifying','component':'support','status':'passed','comparisons':n,'domain_rejections':len(bad),'oral_tasks':6,'fully_solved_changes':6,'points':60,'primitive_markers':6,'result_markers':len(vals),'remediation_chapters':36,'runtime_files':5};json.dumps(out,allow_nan=False);return out
if __name__=='__main__':check()
