"""Independent C06 peer reconstruction: six read-only stdlib runtime files."""
import ast
from fractions import Fraction as F
from functools import lru_cache
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
from math import exp, isfinite, log
from pathlib import Path
AUTHOR=('production/v14-c06-working.html','production/check_v14_c06_working.py','production/v14-c06-sources-working.json','production/v14-c06-author-review-working.json')
FILES=AUTHOR+('production/check_v14_c06_peer_working.py','production/v14-c06-peer-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(not isinstance(x,bool) and isinstance(x,(int,float,F)) and isfinite(float(x)),'finite number required')
    return F(str(x)) if isinstance(x,float) else F(x)
def parsed(s):
    def read(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return read(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=read(n.right);need(d!=0,'zero marker denominator');return read(n.left)/d
        raise ValueError('invalid numeric marker')
    return read(ast.parse(s.strip(),mode='eval').body)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.mark={};self.pending=[];self.ids=[];self.ex=[];self.sol=[];self.worked=[];self.sources={};self.text=[]
    def handle_starttag(self,t,attrs):
        d=dict(attrs);cl=d.get('class','').split()
        if 'id' in d:need(d['id'] not in self.ids,'duplicate ID');self.ids.append(d['id'])
        if 'worked' in cl:self.worked.append(d.get('id'))
        if t=='li' and d.get('id','').startswith('v14-c06-e'):self.ex.append(d['id'])
        if 'data-solution-for' in d:
            need(any(tag=='details' and 'solutions' in a.get('class','').split() for tag,a in self.stack),'solution outside details');self.sol.append(d['data-solution-for'])
        if 'data-source' in d:self.sources[d['data-source']]=d.get('href')
        for typ in ('data-input','data-calc'):
            if typ in d:
                key=d[typ];need(key not in self.mark,'duplicate marker');self.mark[key]=[typ,''];self.pending.append((key,len(self.stack)))
        if t not in ('br','hr','img','input','link','meta'):self.stack.append((t,d))
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack[-1][0]==t,'unbalanced HTML');self.stack.pop();self.pending=[(k,n) for k,n in self.pending if n<len(self.stack)]
    def handle_data(self,s):
        self.text.append(s)
        for k,n in self.pending:self.mark[k][1]+=s

def tax(Y0,Y1,R,beta,D,H=None,cap=None,maxrate=None):
    Y0,Y1,R,beta,D=map(num,(Y0,Y1,R,beta,D));need(min(Y0,Y1,R,beta,D)>0,'tax primitives')
    lower=F(0);upper=D/Y0
    if cap is not None:
        need(H is not None,'current obligations needed');H,cap=map(num,(H,cap));need(H>=0 and cap>=0,'tax funding bounds');lower=max(lower,(H-cap)/Y0)
    if maxrate is not None:upper=min(upper,num(maxrate))
    need(lower<=upper,'infeasible tax funding')
    # Substitute the budget into the objective, differentiate its scalar quadratic.
    slope=-beta*R*R*D*Y0/Y1;curvature=Y0+beta*R*R*Y0*Y0/Y1
    t0=max(lower,min(upper,-slope/curvature));t1=R*(D-Y0*t0)/Y1
    loss=(Y0*t0*t0+beta*Y1*t1*t1)/2
    return (t0,t1),(Y0*t0,Y1*t1),loss

def nominal(L,R,s):
    L,R,s=map(num,(L,R,s));need(L>0 and R>1 and s>0,'positive finite backing domain')
    debt=s/(R-1);backing=s+debt;return backing,L/backing,debt

def joint(R,gamma,phi,bbar,x):
    R,gamma,phi,bbar,x=map(num,(R,gamma,phi,bbar,x));need(R>1 and 0<=gamma<=R and phi>=0 and bbar>0,'joint rule domain')
    a=R-gamma;need(a!=1 and phi!=1,'unit boundaries need separate treatment')
    if a<1 and phi>1:return 'monetary',F(0),a*x
    if a>1 and phi<1:return 'fiscal',a*x/(R*bbar),F(0)
    if a<1 and phi<1:return 'continuum',None,None
    return ('none' if x else 'zero'),None,None

def debt_path(initial,returns,surpluses):
    initial=num(initial);need(len(returns)==len(surpluses) and bool(returns),'finite matching debt path')
    debt=initial;Q=F(1);pv=F(0);rows=[]
    for r,s in zip(returns,surpluses):
        r,s=map(num,(r,s));need(r>0,'positive gross return');Q/=r;debt=r*debt-s;pv+=Q*s;rows.append((debt,Q,pv))
    return rows

class Economy:
    """Recursive finite tree evaluator; all off-path choices explicitly priced."""
    def __init__(self,T,Y,h,P,D,beta=F(9,10),Rf=F(21,20)):
        need(isinstance(T,int) and not isinstance(T,bool) and T>=0,'finite horizon')
        self.T=T;self.Y=tuple(map(num,Y));self.h=tuple(map(num,h));self.D=tuple(map(num,D));self.P=tuple(tuple(map(num,row)) for row in P);self.beta=num(beta);self.Rf=num(Rf)
        n=len(self.Y);need(n>0 and len(self.h)==n and min(self.Y)>0 and all(0<v<=y for v,y in zip(self.h,self.Y)),'positive exclusion resources')
        need(len(self.P)==n and all(len(row)==n and min(row)>=0 and sum(row)==1 for row in self.P),'stochastic kernel')
        need(bool(self.D) and self.D[0]==0 and tuple(sorted(set(self.D)))==self.D,'ordered nonnegative unique zero-containing menu')
        need(0<self.beta<1 and self.Rf>0,'preference/creditor domain')
    @lru_cache(None)
    def exclusion(self,t,j):
        return log(float(self.h[j]))+(float(self.beta)*sum(float(p)*self.exclusion(t+1,k) for k,p in enumerate(self.P[j])) if t<self.T else 0)
    @lru_cache(None)
    def price(self,t,d,j):
        need(t<self.T,'terminal borrowing prohibited')
        return sum(p*self.state(t+1,d,k)['repay'] for k,p in enumerate(self.P[j]))/self.Rf
    @lru_cache(None)
    def choices(self,t,d,j):
        rows=[]
        for nxt in (self.D if t<self.T else (F(0),)):
            q=self.price(t,nxt,j) if t<self.T else F(0);c=self.Y[j]-d+q*nxt
            if c>0:
                value=log(float(c))+(float(self.beta)*sum(float(p)*self.state(t+1,nxt,k)['value'] for k,p in enumerate(self.P[j])) if t<self.T else 0)
                rows.append((nxt,q,c,value))
        return tuple(rows)
    @lru_cache(None)
    def state(self,t,d,j):
        need(0<=t<=self.T and d in self.D and 0<=j<len(self.Y),'state domain')
        options=self.choices(t,d,j);outside=self.exclusion(t,j)
        if not options:return dict(value=outside,repay=0,issue=None,consumption=self.h[j])
        best=max(options,key=lambda row:(row[3],-row[0]))
        # Exact consumption comparison implements terminal ties without log roundoff.
        repay=(self.Y[j]-d>=self.h[j]) if t==self.T else best[3]>=outside
        return dict(value=best[3] if repay else outside,repay=int(repay),issue=best[0] if repay else None,consumption=best[2] if repay else self.h[j])

def example(high=F(1,2),extra=False,T=1):
    high=num(high);need(0<=high<=1,'probability domain')
    Y=(F(1,2),F(4,5),F(7,5));h=(F(2,5),F(13,20),F(4,5));row=(F(0),1-high,high)
    D=(F(0),F(3,20),F(1,5),F(1,2),F(4,5)) if extra else (F(0),F(1,5),F(1,2),F(4,5))
    return Economy(T,Y,h,(row,)*3,D)

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];payload={p:(base/p).read_bytes() for p in FILES}
    doc=Document();doc.feed(payload[AUTHOR[0]].decode());doc.close();need(not doc.stack and all(x.startswith('v14-c06-') for x in doc.ids),'closed prefixed HTML')
    ex=['v14-c06-e'+str(i) for i in range(1,13)];need(doc.ex==doc.sol==ex,'full prompts/solutions');need(doc.worked==['v14-c06-w'+str(i) for i in range(1,6)],'five cases')
    author=json.loads(payload[AUTHOR[3]]);peer=json.loads(payload[FILES[-1]]);source=json.loads(payload[AUTHOR[2]])
    need(set(peer['exact_prompt_solution_audit'])==set(ex),'peer complete prompt audit');need(doc.sources=={s['id']:s['url'] for s in source['sources']},'source routes')
    for record,paths in ((author,set(AUTHOR[:3])),(peer,set(FILES[:-1]))):
        bindings=record['payload_bindings'];need(len(bindings)==len(paths) and {b['path'] for b in bindings}==paths,'five nonself bindings')
        for b in bindings:need(len(payload[b['path']])==b['bytes'] and sha256(payload[b['path']]).hexdigest()==b['sha256'],'frozen payload changed')
    comparisons=0;rejects=0
    def near(a,b,tol=6e-10):
        nonlocal comparisons
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'comparison dimension')
            for x,y in zip(a,b):near(x,y,tol)
        else:need(isfinite(float(a)) and abs(float(a)-float(b))<=tol*max(1,abs(float(b))),str((a,b)));comparisons+=1
    inputs={k:parsed(v[1]) for k,v in doc.mark.items() if v[0]=='data-input'};values={k:parsed(v[1]) for k,v in doc.mark.items() if v[0]=='data-calc'}
    need(set(inputs)=={'debt-parameters','tax-parameters','nominal-parameters','default-grid'},'input set')
    near(inputs['debt-parameters'],(1.05,1.02,.8,.03));near(inputs['tax-parameters'],(100,120,1.05,F(20,21),40));near(inputs['nominal-parameters'],(100,1.05,3,2.4));near(inputs['default-grid'],(0,.2,.5,.8))
    R,G,d,s=inputs['debt-parameters'];Y0,Y1,rt,beta,D=inputs['tax-parameters'];ta=tax(Y0,Y1,rt,beta,D);cap=tax(Y0,Y1,rt,beta,D,40,10);zero=tax(Y0,Y1,rt,beta,D,40,0)
    L,r,s0,s1=inputs['nominal-parameters'];n0=nominal(L,r,s0);n1=nominal(L,r,s1);e6=nominal(120,F(11,10),4);e3=tax(100,100,1,F(1,2),30)
    economy=example();stress=example(F(1,4));expanded=example(extra=True);options=economy.choices(0,F(0),0);risk=options[2];new=next(row for row in expanded.choices(0,F(0),0) if row[0]==F(3,20))
    pi=F(21,20)*(60+F(3,5))/(F(21,20)*60+F(1,50)*F(3,5))
    results={'debt-ratio':R/G*d-s,'stabilizing-share':(R/G-1)*d,'stress-ratio':F(11,10)/G*d-s,'fiscal-root':R-F(1,10),'fiscal-five':10*(R-F(1,10))**5,
     'tax-rate':ta[0][0],'tax-receipts':ta[1],'tax-debt':40-ta[1][0],'tax-loss':ta[2],'tax-cap-rates':cap[0],'tax-cap-loss':cap[2],'tax-cap-gap':cap[2]-ta[2],
     'backing':n0[0],'price-original':n0[1],'backing-new':n1[0],'price-new':n1[1],'price-change':n1[1]/n0[1]-1,'real-debt-pair':(n0[2],n1[2]),
     'regime-passive-x0':joint(r,F(1,10),F(3,2),60,F(3,5))[2],'regime-selected-p':joint(r,F(1,50),F(1,2),60,F(3,5))[1],'regime-exact-inflation':pi,
     'default-prices':tuple(o[1] for o in options),'default-current-consumption':tuple(o[2] for o in options),'default-values':tuple(o[3] for o in options),'default-expected-repayment':risk[1]*economy.Rf*risk[0],'default-proceeds':risk[1]*risk[0],
     'default-stress-price':stress.price(0,F(1,2),0),'default-stress-values':tuple(o[3] for o in stress.choices(0,F(0),0)),
     'e2-debt':F(106,103)*F(7,10)-F(1,50),'e2-share':(F(106,103)-1)*F(7,10),'e2-root':F(106,100)-F(8,100),'e3-rates':e3[0],'e3-loss':e3[2],'e4-rates':zero[0],'e4-loss':zero[2],'e6-backing':e6[0],'e6-price':e6[1],'e6-debt':e6[2],
     'e9-price':new[1],'e9-consumption':new[2],'e9-value':new[3],'e10-price':(F(1,2)+F(1,2)*F(2,5))/economy.Rf,'e10-guarantee':F(1,2)*F(2,5)*F(1,2)}
    need(set(values)==set(results),'display coverage')
    for key,result in results.items():
        try:near(values[key],result)
        except ValueError as e:raise ValueError(key+': '+str(e)) from e
    # Arbitrary dated returns and exact accounting counterexample.
    for initial,rs,ss in ((10,(F(11,10),F(19,20),F(6,5)),(1,-2,3)),(1,(F(51,50),)*5,tuple((F(51,50)-F(26,25))*F(26,25)**t for t in range(5)))):
        for debt,Q,pv in debt_path(initial,rs,ss):near(initial,pv+Q*debt)
    counter=debt_path(1,(F(51,50),)*5,tuple((F(51,50)-F(26,25))*F(26,25)**t for t in range(5)))
    need(counter[-1][0]*counter[-1][1]>1,'bounded ratio not PV tail');comparisons+=1
    # Strict quadratic gap for every sampled feasible direction, and cap global minimizer.
    for primitives in ((100,120,F(21,20),F(20,21),40),(100,100,1,F(1,2),30),(60,90,F(9,10),F(4,5),25)):
        a,b,r,w,D=map(num,primitives);rates,_,loss=tax(*primitives)
        for t0 in (F(0),D/(3*a),D/a):
            t1=r*(D-a*t0)/b;h0=t0-rates[0];h1=t1-rates[1];actual=(a*t0*t0+w*b*t1*t1)/2-loss
            near(actual,(a*h0*h0+w*b*h1*h1)/2);need(actual>=0,'tax objective gap');comparisons+=1
    near(cap[1][1],rt*10);near(ta[1][0]+ta[1][1]/rt,inputs['tax-parameters'][4])
    # Household tax-timing allocations: first-order signs and full feasible scalar objective.
    for cash,future,expected in ((1,3,(1,3)),(F(3,2),F(5,2),(F(3,2),F(5,2)))):
        c=(cash+future)/2;near((c,c),(2,2));need(-1/float(cash)+1/float(future)<0,'binding liquidity sign');comparisons+=1
        for saved in (0,float(cash)/3,float(cash)/2):need(log(float(cash)-saved)+log(float(future)+saved)<=log(float(expected[0]))+log(float(expected[1]))+1e-12,'concave constrained household');comparisons+=1
    # Exact inherited surprise, then perfect-foresight Fisher cancellation for every later date.
    near(F(21,20)*(60+F(3,5))/pi-3-F(1,50)*F(3,5),60)
    inflation=float(pi);debt=60.;phi=.5
    for t in range(1,8):
        nominal_return=1.05*inflation**phi;next_inflation=inflation**phi;real_return=nominal_return/next_inflation
        debt=real_return*debt-3-.02*(debt-60);near(real_return,1.05);near(debt,60);inflation=next_inflation
    need(joint(F(21,20),F(1,10),F(1,2),60,F(3,5))[0]=='continuum','both stable');need(joint(F(21,20),F(1,50),F(3,2),60,F(3,5))[0]=='none','both unstable');comparisons+=2
    # Complete menu optimum, tie repricing, stress and foreign-creditor accounts.
    need(economy.state(0,F(0),0)['issue']==F(1,2) and stress.state(0,F(0),0)['issue']==0 and expanded.state(0,F(0),0)['issue']==F(3,20),'whole-menu policies');comparisons+=3
    need(expanded.state(1,F(3,20),1)['repay']==1,'terminal tie repays');comparisons+=1
    for e in (economy,stress,expanded,example(T=2)):
        for t in range(e.T+1):
            for j,due in product(range(3),e.D):
                selected=e.state(t,due,j);need(isfinite(selected['value']),'finite fallback');comparisons+=1
                need(selected['value']>=e.exclusion(t,j)-1e-12,'default available');comparisons+=1
                for face,q,c,v in e.choices(t,due,j):
                    near(c+due,e.Y[j]+q*face);need(selected['value']>=v-1e-12,'all deviations checked');comparisons+=1
                    if t<e.T:
                        repayment=sum(p*e.state(t+1,face,k)['repay']*face for k,p in enumerate(e.P[j]));near(repayment,e.Rf*q*face)
                if t==e.T:need(all(o[0]==0 for o in e.choices(t,due,j)),'no terminal debt issuance');comparisons+=1
    # Three dates: explicit independent combinations of date1 contingent choices against Bellman maximum.
    e=example(T=2)
    for j,due in product(range(3),e.D):
        best=e.state(0,due,j)['value']
        for face,q,c,v in e.choices(0,due,j):
            branches=[]
            for k in (1,2):branches.append([e.exclusion(1,k)]+[o[3] for o in e.choices(1,face,k)])
            for vl,vh in product(*branches):need(log(float(c))+.9*(float(e.P[j][1])*vl+float(e.P[j][2])*vh)<=best+1e-12,'history-contingent plan');comparisons+=1
    fallback=Economy(1,(F(1,2),),(F(2,5),),((1,),),(F(0),F(2)))
    need(not fallback.choices(0,F(2),0) and fallback.state(0,F(2),0)['repay']==0,'empty repayment fallback');comparisons+=1
    zero_cost=Economy(1,(1,),(1,),((1,),),(0,F(1,2)))
    need(zero_cost.state(0,F(0),0)['repay']==1 and zero_cost.state(0,F(0),0)['issue']==0,'repay/debt tie rule');comparisons+=1
    near(results['e10-price']*F(1,2)*economy.Rf,F(1,4)+results['e10-guarantee'])
    invalid=[(num,(True,)),(num,(float('inf'),)),(parsed,('1/0',)),(parsed,('sum((1,2))',)),(tax,(0,1,1,1,1)),(tax,(1,1,0,1,1)),(tax,(1,1,1,0,1)),(tax,(100,120,F(21,20),F(20,21),40,40,0,F(1,4))),
     (nominal,(100,1,3)),(nominal,(100,F(21,20),0)),(joint,(F(21,20),F(1,20),F(1,2),60,1)),(joint,(F(21,20),F(1,10),1,60,1)),(joint,(F(21,20),2,F(1,2),60,1)),(example,(2,)),
     (Economy,(-1,(1,),(.8,),((1,),),(0,))), (Economy,(1,(1,),(0,),((1,),),(0,))), (Economy,(1,(1,),(.8,),((.8,),),(0,))), (Economy,(1,(1,),(.8,),((1,),),(.2,))), (Economy,(1,(1,),(.8,),((1,),),(0,),1)),
     (economy.price,(1,F(0),0)),(debt_path,(1,(0,),(1,)))]
    for fn,args in invalid:
        try:fn(*args)
        except (ValueError,OverflowError):rejects+=1
        else:raise ValueError('invalid domain accepted '+str(fn))
    summary=dict(chapter='v14-c06',status='passed',review='separate peer',comparisons=comparisons,domain_rejections=rejects,worked_cases=5,solved_exercises=12,input_markers=len(inputs),result_markers=len(results),runtime_files=6,scope='Independent exact accounting and quadratic optimization, dated Fisher cancellation, finite default all-state/menu recursion and contingent-plan comparisons; no author code execution.')
    json.dumps(summary,allow_nan=False);return summary

if __name__=='__main__':check()
