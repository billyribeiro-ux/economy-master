"""Independent environmental chapter reconstruction, no author-code execution."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import log,isfinite
import ast,json
FILES=('production/v15-c11-working.html','production/check_v15_c11_working.py','production/v15-c11-sources-working.json','production/v15-c11-author-review-working.json','production/check_v15_c11_peer_working.py','production/v15-c11-peer-review-working.json')
def need(v,msg):
    if not v:raise ValueError(msg)
def num(v):
    need(type(v)in(int,float,F)and isfinite(float(v)),'finite scalar');return F(str(v))
def line(N,w,t,rA):
    N,w,t,rA=map(num,(N,w,t,rA));need(N>0 and w>0 and t>0 and rA>=0 and w-rA-t*N>0,'line domain');u=w-rA-t*N;comm=t*N*N/2;rent=rA*N+comm;workers=N*u;return u,comm,rent,workers,comm,N*w-comm-rA*N

def allocate(N,wA,wB,c,s,cap=None):
    N,wA,wB,c,s=map(num,(N,wA,wB,c,s));cap=N if cap is None else num(cap);need(N>0 and min(wA,wB)>0 and c>=0 and s>0 and 0<=cap<=N,'city domain');return min(cap,max(0,(wA-wB+s*N)/(2*s)))

def cities(N,wA,wB,c,s,cap=None):
    N,wA,wB,c,s=map(num,(N,wA,wB,c,s));n=allocate(N,wA,wB,c,s,cap);b=N-n;need(0<n<N,'both occupied domain');rB=c+s*b;u=wB-rB;rA=wA-u;need(u>0 and rA>=c+s*n,'positive consumption and supply');cost=c*N+s*(n*n+b*b)/2;out=wA*n+wB*b;owner=rA*n+rB*b-cost;return n,b,rA,rB,u,out,cost,out-cost,owner

def sorting(w,r,H,L,prem):
    w,r,H,L,prem=map(num,(w,r,H,L,prem));need(w>r>=0 and H>=L>=0 and L<=prem<=H and w>=r+prem,'sorting domain');return L,H,r+prem,w-r-prem+H,w-r,2*r+prem,2*w-2*r+H

def gini(y):
    y=tuple(map(num,y));need(y and min(y)>=0 and sum(y)>0,'income domain');return sum(abs(x-z)for i,x in enumerate(y)for z in y[i+1:])/(len(y)*sum(y))

def mobility(shares,base,gains,direct=0,assignment=F(1,2)):
    shares,base,gains=tuple(map(num,shares)),tuple(map(num,base)),tuple(map(num,gains));direct,assignment=map(num,(direct,assignment));need(len(shares)==len(base)==len(gains)==3 and min(shares)>=0 and sum(shares)==1 and shares[0]>0 and 0<assignment<1,'mobility domain');rows=[]
    for typ,(mass,y,gain)in enumerate(zip(shares,base,gains)):
        for z in (0,1):
            d=z if typ==0 else int(typ==1);prob=mass*(assignment if z else 1-assignment);rows.append((prob,z,d,y+d*gain+z*direct))
    means=tuple(sum(prob*y for prob,zz,d,y in rows if zz==z)/(assignment if z else 1-assignment)for z in(0,1));rates=tuple(sum(prob*d for prob,zz,d,y in rows if zz==z)/(assignment if z else 1-assignment)for z in(0,1));itt=means[1]-means[0];fs=rates[1]-rates[0];moved=tuple(sum(prob*y for prob,z,dd,y in rows if dd==d)/sum(prob for prob,z,dd,y in rows if dd==d)for d in(0,1));ate=sum(p*g for p,g in zip(shares,gains));return(*means,itt,fs,itt/fs,ate),moved,rows

class Read(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.cases=[];self.prompts=[];self.solutions=[];self.markers={};self.stack=[];self.sources={}
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if 'worked'in a.get('class','').split():self.cases.append(a['id'])
        if t=='li'and any(tag=='ol'and 'exercises'in d.get('class','').split()for tag,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for'in a:
            need(any(tag=='details'and 'solutions'in d.get('class','').split()for tag,d in self.stack),'disclosed solution');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for k in ('data-input','data-result'):
            if k in a:need(a[k]not in self.markers,'unique markers');self.markers[a[k]]=''
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_endtag(self,t):need(self.stack and self.stack.pop()[0]==t,'balanced HTML')
    def handle_data(self,s):
        for _,a in self.stack:
            for k in ('data-input','data-result'):
                if k in a:self.markers[a[k]]+=s

def parse(s):
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x)for x in n.elts)
        if isinstance(n,ast.Constant)and type(n.value)in(int,float):return num(n.value)
        if isinstance(n,ast.UnaryOp)and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp)and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('literal syntax')
    return walk(ast.parse(s.split('=')[-1].strip().replace('−','-'),mode='eval').body)

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];r=Read();r.feed((root/FILES[0]).read_text());r.close();need(not r.stack and len(r.ids)==len(set(r.ids)),'structure');need(len(r.cases)==5 and len(r.prompts)==10 and r.prompts==r.solutions,'five cases ten solutions');sources=json.loads((root/FILES[2]).read_text());need(r.sources=={s['id']:s['url']for s in sources['sources']},'citations');review=json.loads((root/FILES[5]).read_text());need(set(review['payload_bindings'])==set(FILES[:5]),'five nonself bindings')
    for path,b in review['payload_bindings'].items():
        raw=(root/path).read_bytes();need(len(raw)==b['bytes']and sha256(raw).hexdigest()==b['sha256'],'peer freeze')
    author=json.loads((root/FILES[3]).read_text());need(len(author['payload_bindings'])==3 and {s['path']for s in author['payload_bindings']}==set(FILES[:3]),'author binding set')
    for b in author['payload_bindings']:
        raw=(root/b['path']).read_bytes();need(len(raw)==b['bytes']and sha256(raw).hexdigest()==b['sha256'],'author freeze')
    count=0
    def eq(a,b):
        nonlocal count
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list))and len(a)==len(b),'shape')
            for x,y in zip(a,b):eq(x,y)
        else:need(abs(float(a)-float(b))<1e-11,'mismatch '+str((a,b)));count+=1
    def truth(ok,msg):
        nonlocal count
        need(ok,msg);count+=1
    inputs={'line':(4,20,2,1),'cities':(10,20,16,2,1),'sorting':(10,2,4,1,2),'incomes':(2,4,8,10),'mobility':(F(2,5),F(1,5),F(2,5),20,30,10,6,4,2)}
    for key,value in inputs.items():eq(parse(r.markers[key]),value)
    N,w,t,rA=parse(r.markers['line']);lb=line(N,w,t,rA);li=line(N,w,1,rA);le=line(N,w,F(3,2),rA);pop=(w-rA-lb[0])/F(4,3);lo=line(pop,w,F(4,3),rA);CN,wa,wb,c,s=parse(r.markers['cities']);cb=cities(CN,wa,wb,c,s);cc=cities(CN,wa,wb,c,s,6);ce3=cities(CN,22,wb,c,s);ce4=cities(CN,wa,wb,c,s,5);sw,sr,sh,sl,sp=parse(r.markers['sorting']);sort=sorting(sw,sr,sh,sl,sp);sort5=sorting(sw,sr,6,sl,3);y=parse(r.markers['incomes']);den=len(y)*sum(y)
    def pairparts(groups):
        within=sum(abs(a-b)for g in groups for i,a in enumerate(g)for b in g[i+1:]);allgaps=sum(abs(a-b)for i,a in enumerate(y)for b in y[i+1:]);means=tuple(sum(g)/len(g)for g in groups for _ in g);return gini(means),within/den,(allgaps-within)/den
    initial=pairparts((y[:2],y[2:]));reshuffle=pairparts(((y[0],y[3]),(y[1],y[2])));m=parse(r.markers['mobility']);mr,moves,rows=mobility(m[:3],m[3:6],m[6:]);direct,_,_=mobility(m[:3],m[3:6],m[6:],1);theta=F(8-2,14-8);disrupt=theta*(18-8)-8
    outputs={'line-base':lb[:5],'line-improved':(*li[:3],li[3]-lb[3],li[2]-lb[2],li[5]-lb[5]),'cities-base':cb[:8],'cities-cap':(*cc[:5],cc[8],cc[7]),'sorting-result':sort,'gini-results':(gini(y),initial[0],reshuffle[0],initial[1],initial[2],reshuffle[1],reshuffle[2]),'mobility-result':mr,'e1':(*le[:3],le[5],le[3]-lb[3],le[2]-lb[2]),'e2':(pop,lo[2],lo[4]),'e3':(*ce3[:5],CN*ce3[4],ce3[8],ce3[7]),'e4':(ce4[2],ce4[3],ce4[4],ce4[8],ce4[7],cc[7]-ce4[7],2*(cb[0]-5)),'e5':(sort5[0],sort5[1],sort5[3],sort5[4]),'e6':(F(0),1-F(1,2),F(1),-F(1,2),1-F(1,2)),'e7':(gini((4,4,8,8)),gini(tuple(2*x for x in y))),'e8':(direct[1],direct[2],direct[4],m[6]),'e9':(moves[1],moves[0],moves[1]-moves[0],theta,disrupt)}
    for key,value in outputs.items():eq(parse(r.markers[key]),value)
    need(set(r.markers)==set(inputs)|set(outputs),'all markers independently reconstructed')
    for cost in(F(1),F(3,2),2,3):
        u,comm,rent,worker,diff,net=line(N,w,cost,rA);eq(worker+rent,N*w-comm);eq(net,worker+rent-rA*N);eq(rent-rA*N,diff)
        for x in(0,1,2,4):eq(w-(rA+cost*(N-x))-cost*x,u)
        radius=(w-rA-lb[0])/cost;opened=line(radius,w,cost,rA);eq(opened[0],lb[0]);eq(opened[4],cost*radius*radius/2)
    for wa2 in (1,16,20,22,40):
        n=allocate(CN,wa2,wb,c,s);W=lambda x:wa2*x+wb*(CN-x)-c*CN-s*(x*x+(CN-x)**2)/2
        for candidate in(0,2,5,7,8,10):truth(W(n)>=W(candidate),'global concave allocation')
    for cap in (1,5,6,7,9):
        row=cities(CN,wa,wb,c,s,cap);n,b,ra,rb,u,out,cost,total,owner=row;eq(CN*u+owner,total);truth(n<=cap,'cap feasible');eq(total,cb[7]-(n-cb[0])**2);eq(ra-(c+s*n),max(0,2*(cb[0]-cap)));truth(min(wa-ra,wb-rb)>0,'funded workers')
    for H,L in((4,1),(6,1),(5,2),(3,3)):
        for premium in(L,(H+L)/2,H):
            row=sorting(sw,sr,H,L,premium);truth(H-premium>=0 and L-premium<=0,'full supported choices');eq(row[3]+row[4]+row[5]-2*sr,row[6]);eq(row[6],2*sw-2*sr+H)
    for premium in(2,3,5):
        improved=sorting(sw,sr,sh+1,sl+1,premium);housegain=improved[3]-sort[3];ownergain=premium-sp-F(1,2);eq(housegain+ownergain,F(1,2))
    eq(gini((1,1,1)),0);eq(gini((0,0,0,4)),F(3,4));eq(initial[1]+initial[2],gini(y));eq(reshuffle[1]+reshuffle[2],gini(y));truth(reshuffle[2]>0 and reshuffle[0]==0,'mean aggregation overlap');eq(gini(y),gini(tuple(7*x for x in y)))
    for assign in(F(1,4),F(1,2),F(3,4)):
        result,selected,detail=mobility(m[:3],m[3:6],m[6:],assignment=assign);eq(result,mr);eq(sum(p for p,z,d,y in detail),1)
    eq(mr[2],m[0]*m[6]);eq(direct[4]-mr[4],1/m[0]);truth(mr[4]!=mr[5],'LATE differs from ATE');eq(sum(p*y for p,z,d,y in rows),F(1,2)*(mr[0]+mr[1]))
    for age,gain in((8,8),(14,2)):eq(theta*(18-age)-disrupt,gain);eq(0*(18-age)+gain,gain)
    bad=[lambda:num(True),lambda:num(float('nan')),lambda:line(0,20,2,1),lambda:line(4,20,0,1),lambda:line(4,5,2,1),lambda:allocate(10,20,16,2,0),lambda:allocate(10,20,16,2,1,11),lambda:allocate(10,20,16,2,1,-1),lambda:cities(10,40,16,2,1),lambda:sorting(10,2,1,4,2),lambda:sorting(10,2,4,1,5),lambda:sorting(4,2,4,1,3),lambda:gini((0,0)),lambda:gini((-1,2)),lambda:mobility((0,F(1,2),F(1,2)),(20,30,10),(6,4,2)),lambda:mobility((1,1,1),(20,30,10),(6,4,2)),lambda:mobility(m[:3],m[3:6],m[6:],assignment=0),lambda:parse('1+1')]
    for fn in bad:
        try:fn()
        except(ValueError,TypeError,ZeroDivisionError):pass
        else:raise ValueError('invalid accepted')
    return {'chapter':'v15-c11','role':'separate-peer','status':'pass','comparisons':count,'domain_rejections':len(bad),'worked_cases':5,'solutions':10,'input_groups':len(inputs),'output_groups':len(outputs),'runtime_files':6}
if __name__=='__main__':check()
