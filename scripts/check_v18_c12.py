"""Original resource-polytope and contingent-ledger audit for the C12 manuscript."""
import ast, hashlib, json, math, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product, combinations
from pathlib import Path
FILES=('content/chapters/v18-c12.html','scripts/check_v18_c12.py','content/reviews/v18-c12-sources.json','content/reviews/v18-c12-author.json')
def require(x,msg):
    if not x:raise ValueError('C12 author: '+msg)
def strict(text):
    def pairs(items):
        d={}
        for k,v in items:
            require(k not in d,'duplicate JSON key');d[k]=v
        return d
    def reject(x):raise ValueError('nonfinite JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=reject)
def rational(text):
    def visit(n):
        if isinstance(n,ast.Tuple):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return Q(str(n.value))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('unsupported exact literal')
    return visit(ast.parse(text.strip(),mode='eval').body)
class Reader(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources=[];self.numbers={};self.active=None;self.tables={};self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'duplicate attrs');require(t!='h1','chapter h1')
        if 'id' in a:self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if t=='li' and any(z=='ol' and 'exercises' in d.get('class','').split() for z,d in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for' in a:
            require(any(z=='details' and 'solutions' in d.get('class','').split() for z,d in self.stack),'answer disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for kind in ('input','result'):
            if 'data-'+kind in a:
                key=(kind,a['data-'+kind]);require(key not in self.numbers and self.active is None,'numeric marker');self.active=(t,key);self.numbers[key]=''
        if t=='table':self.table=a.get('id','anonymous-'+str(len(self.tables)));self.tables[self.table]=[]
        if t=='tr':self.row=[]
        if t in ('th','td'):self.cell=[]
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.active:self.numbers[self.active[1]]+=s
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,t):
        require(bool(self.stack) and self.stack.pop()[0]==t,'balanced fragment')
        if self.active and self.active[0]==t:self.active=None
        if t in ('th','td'):self.row.append(''.join(self.cell).strip());self.cell=None
        if t=='tr':self.tables[self.table].append(self.row);self.row=None
        if t=='table':self.table=None

def exact(x,n):
    require(isinstance(x,(tuple,list)) and len(x)==n,'dimension');require(all(type(v) in (int,Q) for v in x),'exact finite inputs');return tuple(Q(v) for v in x)
def solve3(rows):
    m=[list(row) for row in rows]
    for i in range(3):
        pivot=next((j for j in range(i,3) if m[j][i]),None)
        if pivot is None:return None
        m[i],m[pivot]=m[pivot],m[i];scale=m[i][i];m[i]=[v/scale for v in m[i]]
        for j in range(3):
            if j!=i:
                k=m[j][i];m[j]=[a-k*b for a,b in zip(m[j],m[i])]
    return tuple(row[3] for row in m)
def allocation(a,b,H,B,g):
    a,b,H,B,g=exact((a,b,H,B,g),5);require(a>0 and b>0 and min(H,B,g)>=0,'allocation domain')
    # Variables x,y,u. Grant elimination gives y<=B and x+y<=B+g.
    planes=((-1,0,a,0),(0,-1,b,0),(0,0,-1,0),(1,1,0,H),(0,1,0,B),(1,1,0,B+g))
    planes=tuple(tuple(Q(v) for v in r) for r in planes);vertices=set()
    for rows in combinations(planes,3):
        v=solve3(rows)
        if v is not None and all(sum(c*t for c,t in zip(r[:3],v))<=r[3] for r in planes):vertices.add(v)
    require(vertices,'nonempty compact polytope');u=max(v[2] for v in vertices);best=[v for v in vertices if v[2]==u];chosen=min(best,key=lambda v:v[0]+v[1]);return chosen,tuple(sorted(best)),tuple(sorted(vertices))
def funds(U,g,floor,fixed,H,a,b):
    U,g,floor,fixed,H,a,b=exact((U,g,floor,fixed,H,a,b),7);require(min(U,g,floor,fixed,H)>=0,'funds domain');B=U-floor-fixed;require(B>=0,'fixed obligations infeasible')
    (x,y,u),best,vertices=allocation(a,b,H,B,g);restricted=g-min(x,g);unrestricted=U-fixed-max(x-g,0)-y
    return (u,x,y,unrestricted,restricted,unrestricted+restricted,H-x-y),best,vertices

def finance(data,signal,actions):
    cash,other,liab,equity,training,cf,ef=exact(data,7);p,pg,pb,fee=exact(signal,4)
    require(min(cash,other,liab,equity,training,cf,ef,fee)>=0 and cash+other==liab+equity,'opening ledger');require(0<=p<=1 and 0<=pg<=1 and 0<=pb<=1,'signal domain')
    require(cash-training>=cf and equity-training>=ef,'training infeasible');require(set(actions)=={'H','C','F'},'actions')
    for row in actions.values():
        setup,gain,loss=exact(row,3);require(setup>=0,'setup domain')
    joints=(p*pg,(1-p)*pb,p*(1-pg),(1-p)*(1-pb));masses=(joints[0]+joints[1],joints[2]+joints[3]);posterior=tuple(None if m==0 else joints[2*i]/m for i,m in enumerate(masses))
    def ledger(action,state,test):
        setup,gain,loss=actions[action];c=cash-training;e=equity-training;track=[(c,e)]
        if test:c-=fee;e-=fee;track.append((c,e))
        c-=setup;e-=setup;track.append((c,e));receipt=gain if state==0 else loss;c+=receipt;e+=receipt;track.append((c,e))
        require(c+other==liab+e,'transaction identity');return (c,c+other,e),all(c>=cf and e>=ef for c,e in track)
    policies={};ledgers={}
    for policy in product('HCF',repeat=2):
        result=tuple(ledger(policy[i//2],i%2,True) for i in range(4));valid=all(ok or weight==0 for (_,ok),weight in zip(result,joints))
        if valid:policies[''.join(policy)]=sum(weight*(r[0][2]-(equity-training)) for weight,r in zip(joints,result));ledgers[''.join(policy)]=tuple(r[0] for r in result)
    skip={}
    for action in 'HCF':
        rr=tuple(ledger(action,state,False) for state in (0,1));weights=(p,1-p)
        if all(r[1] or w==0 for r,w in zip(rr,weights)):skip[action]=sum(w*(r[0][2]-(equity-training)) for w,r in zip(weights,rr))
    return joints,masses,posterior,policies,skip,ledgers

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];review=strict((root/FILES[3]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'manual review');require(set(review['payloads'])==set(FILES[:3]),'three bindings')
    for name,d in review['payloads'].items():
        raw=(root/name).read_bytes();require(d=={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'binding '+name)
    sources=strict((root/FILES[2]).read_text())['sources'];p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment');require(p.tasks==p.answers==['v18-c12-e'+str(i) for i in range(1,9)],'eight full pairs');require(p.worked==['v18-c12-case1','v18-c12-case2'],'two cases');require(set(p.sources)=={(s['id'],s['url']) for s in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label+': '+str(a)+' != '+str(b))
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,v):eq(read('result',key),v,key)
    U,g,fixed,floor,H,alpha,beta,R0,T0=read('input','academic');a=(R0/alpha)**2;b=(T0/beta)**2;B=U-fixed-floor
    base,ends,vertices=funds(U,g,floor,fixed,H,a,b);u,x,y,ur,gr,total,unused=base
    result('academic-choice',(B,a,b,u,x,y,R0,T0));eq((x,y),(4,9),'baseline allocation');eq(len(ends),1,'baseline primary uniqueness')
    rows=p.tables['v18-c12-academic-ledger'][1:];require([r[0] for r in rows]==['Unrestricted','Restricted research','Total'],'fund rows')
    expected=((U,fixed,max(x-g,0),y,ur),(g,0,min(x,g),0,gr),(U+g,fixed,x,y,total))
    for row,exp in zip(rows,expected):eq(tuple(Q(s) for s in row[1:]),exp,'actual fund ledger');eq(Q(row[1])-sum(Q(s) for s in row[2:5]),Q(row[5]),'fund conservation')
    extra,end,_=funds(U,g,floor,fixed,16,a,b);result('extra-staff',(extra[0],min(v[0] for v in end),max(v[0] for v in end),extra[2],extra[-1]))
    no_grant,_,_=funds(U,0,floor,fixed,H,a,b);higher_floor,_,_=funds(U,g,12,fixed,H,a,b);result('resource-changes',(no_grant,higher_floor))
    target,_,_=funds(U,g,floor,fixed,H,9,b);result('new-target',target[:6]);eq(target[1],target[2],'new target balance')
    # Vertex oracle against displayed bound over original and boundary resource worlds.
    worlds=0
    for aa,bb in ((4,9),(9,9),(1,3)):
        for HH,BB,gg in product((0,7,16),(0,5,12),(0,6)):
            v,ends,verts=allocation(aa,bb,HH,BB,gg);uu=min(Q(HH,aa+bb),Q(BB,bb),Q(BB+gg,aa+bb));eq(v,(aa*uu,bb*uu,uu),'global certificate');worlds+=1
            for xx,yy,zz in verts:eq(zz<=uu,True,'all vertices bounded');eq(max(xx-gg,0)+yy<=BB,True,'original grant feasibility')
    actions={}
    for row in p.tables['v18-c12-actions'][1:]:
        code=row[0][0];setup,G,Bad,netG,netB=tuple(Q(s) for s in row[1:]);actions[code]=(setup,G,Bad);eq((G-setup,Bad-setup),(netG,netB),'actual action net')
    data=read('input','finance');sig=read('input','signal');j,m,post,policies,skip,ledgers=finance(data,sig,actions)
    result('joint',j);eq(post,(Q(4,5),Q(1,5)),'Bayes');eq(set(policies),{'HH','CH','HC','CC'},'four policies');eq(len(policies),4,'nine minus five');eq(skip,{'H':Q(0),'C':Q(-1)},'no diagnostic')
    result('policy-value',policies['CH']);result('policy-menu',tuple(policies[k] for k in ('HH','CH','HC','CC')));eq(max(policies,key=policies.get),'CH','diagnostic policy');eq(max(policies.values())>max(skip.values()),True,'acquire')
    terminal=p.tables['v18-c12-terminal'][1:];eq(tuple(r[0] for r in terminal),('G+','B+','G-','B-'),'states')
    for i,row in enumerate(terminal):eq(Q(row[1]),j[i],'joint cell');eq(row[2],'C' if i<2 else 'H','actual policy');eq(tuple(Q(s) for s in row[3:]),ledgers['CH'][i],'actual terminal row')
    avg=tuple(sum(w*row[k] for w,row in zip(j,ledgers['CH'])) for k in range(3));result('finance-ledger',(avg[0],avg[2],avg[1],min(row[0] for row in ledgers['CH']),min(row[2] for row in ledgers['CH'])))
    result('fee-boundary',(Q(7,10),data[3]-data[4]-Q(7,10)-5,data[0]-data[4]-Q(7,10)-5))
    changed=finance(data,(sig[0],Q(1,2),Q(1,2),sig[3]),actions);tight=finance(data[:-1]+(Q(12),),sig,actions)
    result('changed-decisions',changed[2]+(max(changed[3].values()),max(changed[4].values()),data[3]-data[4]-5,data[3]-data[4]-sig[3]-5));eq(set(tight[3]),{'HH'},'tightened capital');eq(tight[4],{'H':Q(0),'C':Q(-1)},'no-fee boundary')
    ret,_,_=funds(U+3,g,floor,fixed,H,a,b);result('retention',(ret[0],ret[1],ret[2],Q(12)-max(ret[1]-g,0)-ret[2],ledgers['CH'][1][0],ledgers['CH'][1][2]))
    finance_worlds=0
    for fee in (Q(0),Q(1,2),Q(7,10),Q(1),Q(2)):
        jj,mm,qq,pp,ss,ll=finance(data,sig[:3]+(fee,),actions);eq(set(pp),{'HH','CH','HC','CC'},'fee interval feasible');eq(pp['CH'],Q(7,10)-fee,'fee value');eq(max(pp.values()),pp['CH'],'fee branch optimum');eq(min(row[2] for row in ll['CH']),12-fee,'fee minimum');finance_worlds+=1
    # Direct state-weighted policy payoffs, including posterior boundary and absent signal.
    for prior,good,bad in product((Q(0),Q(1,2),Q(1)),(Q(0),Q(4,5)),(Q(0),Q(1,5))):
        jj,mm,qq,pp,ss,ll=finance(data,(prior,good,bad,Q(1,2)),actions);finance_worlds+=1
        for code,value in pp.items():
            cell=sum(weight*(actions[code[i//2]][1 if i%2==0 else 2]-actions[code[i//2]][0]) for i,weight in enumerate(jj))-Q(1,2);eq(value,cell,'direct policy payoff')
        eq(sum(jj),1,'joint total')
        for i in range(2):
            if mm[i]:eq(qq[i]*mm[i],jj[2*i],'posterior reconstruction')
            else:eq(qq[i],None,'zero mass undefined')
    invalid=0
    badcalls=[lambda:allocation(0,9,13,9,6),lambda:allocation(4,-1,13,9,6),lambda:allocation(4,9,-1,9,6),lambda:allocation(4,9,13,-1,6),lambda:allocation(4,9,13,9,-1),lambda:allocation(4.,9,13,9,6),lambda:allocation(True,9,13,9,6),lambda:funds(10,6,10,5,13,4,9),lambda:finance(data,(-1,Q(4,5),Q(1,5),Q(1,2)),actions),lambda:finance(data,(Q(1,2),2,Q(1,5),Q(1,2)),actions),lambda:finance(data,(Q(1,2),Q(4,5),-1,Q(1,2)),actions),lambda:finance(data,sig[:3]+(-1,),actions),lambda:finance((31,)+data[1:],sig,actions),lambda:finance(data[:4]+(30,)+data[5:],sig,actions),lambda:strict('{"x":1,"x":2}'),lambda:strict('{"x":NaN}')]
    for call in badcalls:
        try:call()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    require(used==set(marks),'every numeric marker consumed')
    return {'status':'passed','comparisons':count,'resource_worlds':worlds,'finance_worlds':finance_worlds,'invalid_domains':invalid,'worked_cases':2,'solutions':8}
if __name__=='__main__':
    if len(sys.argv)>2:raise ValueError('at most one root')
    check(sys.argv[1] if len(sys.argv)==2 else None)
