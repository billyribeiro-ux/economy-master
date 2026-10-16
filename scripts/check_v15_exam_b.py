"""V15 Form B independent primitive reconstruction and exact four-file audit."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from math import isfinite,log
from pathlib import Path
FILES=('content/assessments/parts/v15-exam-b.html','scripts/check_v15_exam_b.py','content/reviews/v15-exam-b-sources.json','content/reviews/v15-exam-b-author.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite nonboolean');return F(str(x)) if type(x) is float else F(x)
def literal(s):
    def walk(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=walk(n.right);need(d!=0,'nonzero divisor');return walk(n.left)/d
        raise ValueError('literal only')
    return walk(ast.parse(s.replace('−','-').rsplit('=',1)[-1].strip(),mode='eval').body)
def market(t):
    t=num(t);need(0<=t<8,'tax interior domain');q=(8-t)/2;p=10-q;s=2+q;return p,s,q,t*q,q*q/2,q*q/2,8*q-q*q

def trained(base,gain,cost,liquid,grant=False):
    base,gain,cost,liquid=map(num,(base,gain,cost,liquid));need(base>=0 and gain>=0 and cost>0 and liquid>=0 and type(grant) is bool,'training domain');return gain-cost, bool(gain>0 if grant else (gain>=cost and liquid>=cost))
def pricing(p,r,c=3):
    p,r,c=map(num,(p,r,c));need(0<=p<=12 and 0<=r<=12 and 0<=c<=12,'price domain');q=max(F(0),12-p)*(1 if p<r else (F(1,2) if p==r else 0));return q,(p-c)*q

def network(vf):
    vf=num(vf);need(vf>0,'primary cost positive');xh=F(7)/(1-F(1,8));xf=xh/2;ph=(2+vf/2)/(1-F(1,8));pf=vf+ph/4;ih=2*xh;iff=vf*xf;return xh,xf,ph,pf,ih,iff,ih/ph,iff/ph

def investment(own,other,covered):
    need(type(own) is int and type(other) is int and type(covered) is int and all(v in (0,1) for v in (own,other,covered)),'binary action')
    return 0 if not own else (4 if other else -2+3*covered)
def posterior(pr,h,l):
    pr,h,l=map(num,(pr,h,l));need(all(0<=v<=1 for v in (pr,h,l)),'probability domain');den=pr*h+(1-pr)*l;need(den>0,'possible signal');return pr*h/den

def report(p,H1,H0,d1,d0):
    p,H1,H0,d1,d0=map(num,(p,H1,H0,d1,d0));need(0<=p<=1 and min(H1,H0,d1,d0)>0,'reporting domain');a=H1/d1;b=H0/d0;q=p*a/(p*a+(1-p)*b);s1=1-(q-1)**2;s0=1-q*q;payment=p*H1*s1+(1-p)*H0*s0;return q,s1,s0,payment

def resource(tax):
    tax=num(tax);need(0<=tax<4,'resource domain');A=6-tax;B=8-tax;beta=F(1,2);q0=(A-beta*B+beta*4)/(1+beta);q1=4-q0;need(q0>0 and q1>0,'interior extraction');return q0,q1,8-q0,10-q1,A-q0,B-q1

def prevention(insured):
    need(type(insured) is bool,'insurance flag');p=(F(1,2),F(1,4));cost=(F(0),F(1));private=tuple(cost[e]+(0 if insured else 8*p[e]) for e in (0,1));e=0 if private[0]<=private[1] else 1;return e,p[e],cost[e]+8*p[e]
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.outputs={};self.prompts=[];self.solutions=[];self.cases=[];self.ids=[];self.sources={};self.links=set();self.disclosures=0;self.points={};self.h2=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','fragment heading')
        if 'id' in a:need((a['id'].startswith('v15-exam-b-') or a['id'] in ('form-b','solutions-b')) and a['id'] not in self.ids,'chapter unique IDs');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and 'data-points' in a:self.prompts.append(a['id']);self.points[a['id']]=int(a['data-points'])
        if t=='h2':self.h2.append(a.get('id'))
        if t=='details' and 'solutions' in a.get('class','').split():self.disclosures+=1
        if 'data-solution-for' in a:need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'solution enclosure');self.solutions.append(a['data-solution-for'])
        if t=='a':self.links.add(a.get('href'))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.outputs)):
            if attr in a:k=a[attr];need(k not in d,'unique data marker');d[k]='';self.active.append((d,k,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,n in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=Read();doc.feed(raw[FILES[0]].decode());need(not doc.stack,'complete HTML');review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]]);bb=review['payload_bindings'];need(len(bb)==3 and {b['path'] for b in bb}==set(FILES[:3]),'three nonself bindings')
    for b in bb:need((len(raw[b['path']]),sha256(raw[b['path']]).hexdigest())==(b['bytes'],b['sha256']),'frozen payload')
    ids=['v15-exam-b-'+str(i)+x for i in range(1,6) for x in 'abcd'];need(doc.prompts==doc.solutions==ids and set(review['exact_prompt_review'])==set(ids),'twenty exact matched solutions');need(doc.h2==['form-b','solutions-b'] and doc.disclosures==1,'exam headings/disclosure');need(doc.points==dict.fromkeys(ids,5) and sum(doc.points.values())==100,'twenty five-point parts');need(all(sum(doc.points['v15-exam-b-'+str(i)+x] for x in 'abcd')==20 for i in range(1,6)),'five domain scores');need(raw[FILES[0]].decode().count('<strong>Rubric:</strong>')==20,'twenty additive rubrics');need({'v15-c'+str(i).zfill(2)+'.html' for i in range(1,13)}<=doc.links,'all twelve remediation routes');need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==3,'source routes')
    inp={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.outputs.items()};expected={};count=0
    def eq(a,b,msg='identity'):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),msg+'shape')
            for x,y in zip(a,b):eq(x,y,msg)
        else:count+=1;need(a==b,msg+str((a,b)))
    primitives={'tax':(10,2,2),'training':(4,6,2,4,3,1),'bertrand':(12,3,7),'network':(7,F(1,4),F(1,2),2,1),'coordination':(4,4,8,2,3),'history':((8,10,16),(6,8,10)),'voting':((3,1,2),(2,3,1),(1,2,3),2),'reporting':(F(1,2),F(2,3),F(1,3),18,18,9),'resource':(4,F(1,2),2,8,10,1),'health':(20,F(1,2),F(1,4),8,1,8),'implementation':(-1,5,8,4,1,2,6,7,5,8,F(1,2),2)};need(set(inp)==set(primitives),'eleven primitive groups')
    for k,v in primitives.items():eq(inp[k],v,k)
    t=inp['tax'][-1];base=market(0);changed=market(t);p,s,q,G,CS,PS,W=changed;expected['b1a']=(base[0],base[2],p,s,q,G,base[-1],W);eq(CS+PS+G,W);eq(p*q,2*q+q*q/2+PS+G);need(p*q<=100,'consumer bill funded')
    bl,bh,gl,gh,cost,liquidity=inp['training'];rl,cl=trained(bl,gl,cost,liquidity);rh,ch=trained(bh,gh,cost,liquidity);need(not cl and not ch,'neither can self finance');need(trained(bl,gl,cost,liquidity,True)[1] and trained(bh,gh,cost,liquidity,True)[1],'both accept free');expected['b1b']=(rl,rh,gl,gh);dW=W-base[-1];expected['b1c']=(2*cost,gl+gh-2*cost,dW+gl+gh-2*cost,cost,G-cost,gh-cost,dW+gh-cost);eq(G,2*cost);eq(G,cost+(G-cost));eq((CS-base[4]+G-cost)+(PS-base[5])+gh,0);expected['b1d']=(bh+gh-bl,gh,(gl+gh)/2,bh-bl);eq(bh+gh-bl,gh+bh-bl)
    for tt in (0,1,2,4,6):
        pp,ss,qq,gg,cs,ps,ww=market(tt);eq(pp-ss,tt);eq(10-pp,ss-2);eq(cs+ps+gg,ww);eq(16-ww,F(tt*tt,4));need(pp*qq<=100,'alternative funding');count+=1
    A,c,pclaim=inp['bertrand'];oq,op=pricing(pclaim,pclaim,c);dq,dp=pricing(F(69,10),pclaim,c);expected['b2a']=(op,F(69,10),dq,dp);need(dp>op,'actual profitable deviation');eq(oq,F(5,2));expected['b2b']=(c,c,2*pricing(c,c)[0],pricing(c,c)[1],pricing(c,c)[1])
    for deviation in (F(0),F(2),F(29,10),F(3),F(31,10),F(7),F(12)):need(pricing(deviation,c)[1]<=0,'Bertrand equilibrium deviations');count+=1
    for common in (F(4),F(7),F(11),F(12)):
        profit=pricing(common,common)[1];under=common-F(1,100);need(pricing(under,common)[1]>profit,'above-cost tie undercut');count+=1
    n=network(inp['network'][-1]);xh,xf,ph,pf,ih,iff,hcons,fcons=n;expected['b2c']=(xh,xf,ph,pf,ih,iff,ph*7,xh*ph+xf*pf,xf*pf+xf*ph/4);n2=network(2);xh,xf,ph,pf,ih,iff,hcons,fcons=n2;expected['b2d']=(ph,pf,ih,iff,hcons,fcons,xf*pf,(xf/4+fcons)*ph)
    for vf in (F(1),F(2),F(3)):
        xh,xf,ph,pf,ih,iff,hc,fc=network(vf);eq(xh,7+xf/4);eq(xf,xh/2);eq(ph,2+pf/2);eq(pf,vf+ph/4);eq(hc+fc,7);eq(7*ph,ih+iff);eq(xf*pf,(xf/4+fc)*ph);eq(xh*ph+xf*pf-(xf*pf+xf*ph/4),ih+iff)
    pure=[]
    for a in (0,1):
        for b in (0,1):
            if investment(a,b,0)>=investment(1-a,b,0) and investment(b,a,0)>=investment(1-b,a,0):pure.append((a,b))
    need(pure==[(0,0),(1,1)],'full unprotected pure equilibria');mixed=F(2,6);eq(mixed*4+(1-mixed)*(-2),0);expected['b3a']=(mixed,8,0);expected['b3b']=(investment(1,0,1),3,0,investment(1,1,1)+investment(1,1,1))
    from itertools import product
    for coverage in ((1,1),(1,0),(0,1)):
        equilibria=[]
        for a,b in product((0,1),repeat=2):
            if investment(a,b,coverage[0])>=investment(1-a,b,coverage[0]) and investment(b,a,coverage[1])>=investment(1-b,a,coverage[1]):equilibria.append((a,b))
            claims=3*(coverage[0]*a*(1-b)+coverage[1]*b*(1-a));need(claims<=3,'worst contingent insurance funding');count+=1
        need(equilibria==[(1,1)],'unique insured equilibrium');count+=1
    T,C=inp['history'];DD=(T[2]-T[1])-(C[2]-C[1]);lead=(T[1]-T[0])-(C[1]-C[0]);cf1=T[1]+C[2]-C[1];cf2=T[2];expected['b3c']=(DD,lead,cf1,T[2]-cf1,cf2,T[2]-cf2);eq(cf1+4,T[2]);eq(cf2+0,T[2]);outcomes={(a,b):(4 if a or b else 0) for a,b in product((0,1),repeat=2)};covered=sum(outcomes[1,b] for b in (0,1))/F(2);uncovered=sum(outcomes[0,b] for b in (0,1))/F(2);expected['b3d']=(covered,uncovered,covered-uncovered,outcomes[1,1]-outcomes[0,0],2*(outcomes[1,1]-outcomes[0,0]))
    allocs=inp['voting'][:3];tax=inp['voting'][3];votes=lambda i,j:sum(allocs[i][v]>allocs[j][v] for v in range(3));winner=lambda i,j:i if votes(i,j)>=2 else j;expected['b4a']=(votes(0,1),votes(1,2),votes(2,0),sum(allocs[0]));eq(winner(winner(0,1),2),2);eq(winner(winner(1,2),0),0)
    for v in allocs:eq(sum(v),3*tax);need(tax<=10 and all(10-tax+z>=0 for z in v),'funded allocations');count+=1
    prior,h,l,H,d1,d0=inp['reporting'];post=posterior(prior,h,l);q,s1,s0,pay=report(post,H,H,d1,d0);expected['b4b']=(post,q);H0=H*d0/d1;q1,s11,s01,pay1=report(post,H,H0,d1,d0);expected['b4c']=(H0,q1,pay1,3*pay1,3*max(H,H0));eq(q1,post);eq((s11,s01),(F(8,9),F(5,9)))
    for pp in (F(0),F(1,4),F(2,3),F(1)):
        for HH0 in (H,H0):
            rr,_,_,_=report(pp,H,HH0,d1,d0);weight=pp*H/d1+(1-pp)*HH0/d0;U=lambda z:pp*(H/d1)*(1-(z-1)**2)+(1-pp)*(HH0/d0)*(1-z*z)
            for alt in (F(0),F(1,4),F(1,2),F(3,4),F(1)):eq(U(rr)-U(alt),weight*(rr-alt)**2)
    weighted=tuple(sum(w*(a-tax) for w,a in zip((2,1,1),v)) for v in allocs);expected['b4d']=(*weighted,F(0));need(allocs[0][1]-tax<0,'selected policy has a loser')
    before=resource(0);after=resource(inp['resource'][-1]);expected['b5a']=(*before[:4],*after[:4])
    for tt in (F(0),F(1),F(2)):
        q0,q1,p0,p1,r0,r1=resource(tt);eq(q0+q1,4);eq(r1,2*r0);eq(p0-2-tt,r0);eq(p1-2-tt,r1);need(r0>0 and q0>0 and q1>0,'resource KKT');count+=1
        obj=lambda x,y:(6-tt)*x-x*x/2+F(1,2)*((8-tt)*y-y*y/2);best=obj(q0,q1)
        for x in (F(0),F(1),F(2),F(3),F(4)):eq(best-obj(x,4-x),F(3,4)*(x-q0)**2)
        for z,pp in ((q0,p0),(q1,p1)):eq(100-pp*z+tt*z+(pp-2-tt)*z,100-2*z)
    e0,p0,real0=prevention(False);e1,p1,real1=prevention(True);premium=p1*8;expected['b5b']=(e0,e1,premium,real0,real1)
    for ill in (0,1):
        claim=8*ill;person=20-premium-8*ill+claim;insurer=8+premium-claim;eq(person,16);need(insurer>=0,'funded insurer');eq(person+insurer,28-8*ill);count+=1
    eq((8+premium)+(8+premium-8),16);expected['b5c']=((8+10)/F(2)-(2+8)/F(2),F(0),F(-2))
    al,ah,ac,aw,bl,bh,bc,bw,cap,budget,tc,extra=inp['implementation'];menu=[]
    for label,cost,work,low,high in (('none',0,0,0,0),('A',ac,aw,al,ah),('B',bc,bw,bl,bh)):
        for training in (0,1):
            total=cost+training*tc;available=cap+training*extra
            if total<=budget and work<=available:menu.append((low-training*tc,label,training,total,available-work))
    best=max(menu);need(best[1:3]==('B',1),'global funded robust menu');expected['b5d']=(best[0],best[3],budget-best[3],best[4]);need(bc<=budget and bw>cap and ac+tc>budget,'individual infeasibility reasons');count+=1
    need(set(expected)==set(shown),'all twenty numerical groups')
    for key,v in expected.items():eq(shown[key],v,'display '+key)
    invalid=(lambda:num(True),lambda:num(float('nan')),lambda:literal('1/0'),lambda:literal('f(1)'),lambda:market(8),lambda:market(-1),lambda:trained(4,2,0,1),lambda:trained(4,2,3,-1),lambda:trained(4,2,3,1,1),lambda:pricing(-1,3),lambda:pricing(13,3),lambda:network(0),lambda:investment(True,0,0),lambda:investment(1,2,0),lambda:posterior(0,1,0),lambda:posterior(2,1,0),lambda:report(F(1,2),0,1,1,1),lambda:report(F(1,2),1,1,0,1),lambda:resource(4),lambda:resource(-1),lambda:prevention(1));rejections=0
    for fn in invalid:
        try:fn()
        except ValueError:rejections+=1
        else:raise ValueError('invalid input accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'unchanged payload')
    result={'volume':'v15','component':'exam_b','status':'passed','points':100,'domains':5,'scored_parts':20,'solutions':20,'input_groups':len(inp),'result_groups':len(shown),'comparisons':count,'rejected_inputs':rejections,'runtime_files':4,'open_findings':[]};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
