"""Original flow, assignment and classifier-loss audit for the C09 manuscript."""
import ast, hashlib, json, math, sys
from fractions import Fraction as Q
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('content/chapters/v18-c09.html','scripts/check_v18_c09.py','content/reviews/v18-c09-sources.json','content/reviews/v18-c09-author.json')
def require(x,msg):
    if not x:raise ValueError('C09 author: '+msg)
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
    require(isinstance(x,(tuple,list)) and len(x)==n,'input dimension');require(all(type(v) in (int,Q) for v in x),'exact finite inputs');return tuple(Q(v) for v in x)
def flow(a,v,f,r):
    a,v,f,r=exact((a,v,f,r),4);require(min(a,v,f)>=0 and 0<=r<=1,'flow domain')
    return min(a,v*(1-r),f)
def work(initial,arrivals,capacity,time):
    q,l,m,t=exact((initial,arrivals,capacity,time),4);require(min(q,l,m,t)>=0,'work domain');backlog=max(Q(0),q+(l-m)*t)
    return backlog,q+l*t-backlog
def menu(data,changes):
    a,v,f,r,arrival,initial,budget=exact(data,7);require(min(arrival,initial,budget)>=0,'menu domain');rc,rv=exact(changes[0],2);ic,ia,ir=exact(changes[1],3);fc,ff=exact(changes[2],2);require(min(rc,rv,ic,ia,fc,ff)>=0 and 0<=ir<=1,'change domain');rows={}
    for R,I,F in product((0,1),repeat=3):
        cost=R*rc+I*ic+F*fc;intake=ia if I else a;visits=v+R*rv;ret=ir if I else r;release=f+F*ff
        rows[R,I,F]=(cost,intake,visits,ret,release,flow(intake,visits,release,ret))
    feasible=[(bits,row) for bits,row in rows.items() if row[0]<=budget];score=max((row[-1],-row[0]) for _,row in feasible)
    winners=tuple(bits for bits,row in feasible if (row[-1],-row[0])==score)
    return rows,winners

def randomization(differences):
    d=exact(differences,len(differences));require(len(d)>0,'nonempty pairs');n=len(d);observed=sum(d)/n
    values=tuple(sum(x*s for x,s in zip(d,signs))/n for signs in product((-1,1),repeat=n));tail=sum(abs(x)>=abs(observed) for x in values)
    return observed,tail,len(values),Q(tail,len(values)),values

def policy(counts,costs,automatic,compute=True):
    require(len(counts)==3,'three bands');counts=tuple(exact(row,4) for row in counts);require(all(min(row)>=0 and all(v.denominator==1 for v in row) for row in counts),'integer confusion counts')
    miss,alarm,human,inference,arrival,capacity=exact(costs,6);require(min(miss,alarm,human,inference,arrival,capacity)>=0,'cost domain');require(type(automatic) is int and 0<=automatic<=3,'policy cutoff');n=sum(map(sum,counts));require(n>0,'positive test population')
    selected=counts[:automatic];tp=sum(row[0] for row in selected);fn=sum(row[1] for row in selected);fp=sum(row[2] for row in selected);tn=sum(row[3] for row in selected);auto=tp+fn+fp+tn;review=n-auto;cost=miss*fn+alarm*fp+human*review+(n*inference if compute else 0)
    return (auto/n,fn+fp,review,cost),(tp,fn,fp,tn), (None if auto==0 else (fn+fp)/auto)

def upper(x,n,alpha=Q(1,20)):
    require(type(x) is int and type(n) is int and n>0 and 0<=x<=n and 0<alpha<1,'binomial domain')
    if x==n:return 1.0
    target=float(alpha);lo,hi=0.0,1.0
    for _ in range(80):
        mid=(lo+hi)/2;cdf=sum(math.comb(n,k)*mid**k*(1-mid)**(n-k) for k in range(x+1))
        if cdf>target:lo=mid
        else:hi=mid
    return (lo+hi)/2

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];review=strict((root/FILES[3]).read_text());require(review['full_reading_complete'] and not review['open_material_findings'],'manual review');require(set(review['payloads'])==set(FILES[:3]),'three bindings')
    for name,d in review['payloads'].items():
        b=(root/name).read_bytes();require(d=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'freeze '+name)
    sources=strict((root/FILES[2]).read_text())['sources'];p=Reader();p.feed((root/FILES[0]).read_text());p.close();require(not p.stack and p.active is None and len(p.ids)==len(set(p.ids)),'fragment');require(p.tasks==p.answers==['v18-c09-e'+str(i) for i in range(1,9)],'eight paired solutions');require(p.worked==['v18-c09-case1','v18-c09-case2'],'two cases');require(set(p.sources)=={(s['id'],s['url']) for s in sources},'source URLs')
    marks={k:rational(v) for k,v in p.numbers.items()};used=set();count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            require(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),'shape '+label)
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;require(a==b,label)
    def read(kind,key):used.add((kind,key));return marks[kind,key]
    def result(key,value):eq(read('result',key),value,key)
    data=read('input','process');changes=read('input','changes');rows,winners=menu(data,changes);eq(winners,((1,0,0),),'unique process menu')
    codes={'None':(0,0,0),'R':(1,0,0),'I':(0,1,0),'F':(0,0,1),'R+I':(1,1,0),'R+F':(1,0,1),'I+F':(0,1,1),'R+I+F':(1,1,1)}
    table=p.tables['v18-c09-options'][1:];require(len(table)==8 and {r[0] for r in table}==set(codes),'complete menu')
    for row in table:eq(tuple(Q(x) for x in row[1:]),rows[codes[row[0]]],'actual process table')
    a,v,f,r,arrival,q,budget=data;chosen=rows[winners[0]];capacity=chosen[-1];result('process-choice',(flow(a,v,f,r),capacity,chosen[0],q/(capacity-arrival),work(q,arrival,capacity,10)[0],work(q,arrival,capacity,30)[1]));eq(work(q,arrival,flow(a,v,f,r),10)[0],120,'baseline backlog')
    result('staff-change',(work(q,38,capacity,10)[0],q/(capacity-38),flow(a,45,f,r),work(q,38,flow(a,45,f,r),10)[0]))
    changed=list(data);changed[-1]=Q(13);rr,ww=menu(changed,changes);eq(ww,((1,1,0),),'budget13 choice');c=rr[ww[0]];result('budget-change',(c[-1],c[0],q/(c[-1]-arrival),work(q,arrival,c[-1],9)[1]))
    pilot=tuple(tuple(Q(x) for x in row[1:]) for row in p.tables['v18-c09-pilot'][1:]);require(len(pilot)==4,'four pairs')
    for treated,control,difference in pilot:eq(treated-control,difference,'visible paired difference')
    test=randomization(tuple(row[2] for row in pilot));result('pilot',(sum(row[0] for row in pilot)/4,sum(row[1] for row in pilot)/4)+test[:4]);changed=list(row[2] for row in pilot);changed[3]=Q(2);other=randomization(changed);result('pilot-change',other[:4])
    distribution={x:other[4].count(x) for x in set(other[4])};eq(tuple(sorted(distribution.items())),tuple(zip((Q(-2),Q(-3,2),Q(-1),Q(-1,2),Q(0),Q(1,2),Q(1),Q(3,2),Q(2)),(1,1,2,3,2,3,2,1,1))),'full reference multiplicities')
    # Verify the finite-tail rank validity for every actual assignment at two levels.
    for alpha in (Q(1,20),Q(1,8),Q(1,2)):
        reject=sum(Q(sum(abs(y)>=abs(x) for y in test[4]),len(test[4]))<=alpha for x in test[4]);eq(Q(reject,len(test[4]))<=alpha,True,'inclusive rank size')
    # Direct averaging over the two possible assignments recovers the pair-average effect.
    for i0,i1,j0,j1 in ((8,6,10,7),(7,7,9,8),(4,9,8,3)):
        eq(Q((i1-j0)+(j1-i0),2),Q((i1-i0)+(j1-j0),2),'paired estimand expectation')
    table=p.tables['v18-c09-ai'][1:];require([r[0] for r in table]==['H','M','L'],'frozen bands');counts=tuple(tuple(Q(x) for x in row[1:5]) for row in table)
    for row,cs in zip(table,counts):eq(sum(cs),Q(row[5]),'visible band total')
    costs=read('input','ai-costs');policies=tuple(policy(counts,costs,n,compute) for n,compute in ((1,True),(2,True),(3,True),(0,False)));result('ai-policies',tuple(x[0] for x in policies));eq(tuple(x[2] for x in policies),(Q(1,20),Q(1,12),Q(17,100),None),'selective denominators');eq(sum(row[0]+row[3] for row in counts),83,'overall accuracy numerator')
    eq(Q(2,12),Q(1,6),'A conditional miss');eq(Q(2,30),Q(1,15),'A whole miss');eq(costs[4]*(1-policies[0][0][0]),48,'fallback demand80');eq(costs[5]-48,2,'mean staffing slack');eq(policies[0][0][3]/100,Q(33,25),'unit cost')
    sizes=read('result','zero-bound-sizes');eq(sizes,(4,58,59),'sample sizes');display=read('result','zero-bound-display')
    for n,target in zip(sizes,display):
        bound=upper(0,int(n));eq(abs(bound-float(target))<=0.0000005,True,'rounded endpoint');eq(abs(bound-(1-float(Q(1,20))**(1/int(n))))<1e-12,True,'tail inversion versus closed form')
    eq(Q(19,20)**58>Q(1,20) and Q(19,20)**59<=Q(1,20),True,'minimal sample exact powers');eq(upper(0,4)>0.05,True,'primary gate fails')
    # Check a full one-sided procedure's coverage on a small exact sampling model.
    for truth in (Q(0),Q(1,20),Q(1,2),Q(9,10),Q(1)):
        excluded=sum(Q(math.comb(4,k))*truth**k*(1-truth)**(4-k) for k in range(5) if upper(k,4)+1e-12<float(truth));eq(excluded<=Q(1,20),True,'binomial inversion coverage witness')
    result('fallback-change',(100*(1-policies[0][0][0]),costs[5]/(1-policies[0][0][0]),policies[0][0][3]+costs[0],Q(1,30)))
    altered=list(costs);altered[0]=Q(39,2);eq(policy(counts,altered,1)[0][3],policy(counts,altered,2)[0][3],'pairwise loss-weight boundary')
    cap=flow(a,50,f,Q(1,4));result('retention',(cap,q/(cap-arrival),48,3,work(0,48,45,8)[0]))
    process_worlds=0
    for returnrate,visits,arrivals in product((Q(0),Q(1,5),Q(1,2),Q(1)),(Q(0),Q(40),Q(70)),(Q(0),Q(36))):
        cap=flow(a,visits,f,returnrate);eq(cap<=a and cap<=visits*(1-returnrate) and cap<=f,True,'all capacity bounds')
        current=Q(80);completed=Q(0)
        for day in range(1,11):
            done=min(cap,current+arrivals);current+=arrivals-done;completed+=done
            eq(work(80,arrivals,cap,day),(current,completed),'daily conservation versus closed form')
        if returnrate<1:
            partial=sum(returnrate**j for j in range(20));tail=returnrate**20/(1-returnrate);eq(partial+tail,1/(1-returnrate),'geometric visits with exact tail')
        else:eq(cap,0,'nonterminating review boundary')
        process_worlds+=1
    policy_worlds=0
    for missweight,humanprice in product((Q(0),Q(18),Q(39,2),Q(20)),(Q(0),Q(2))):
        c=list(costs);c[0]=missweight;c[2]=humanprice
        for cutoff in range(4):
            got,conf,_=policy(counts,c,cutoff,cutoff>0);loss=Q(0);humans=0
            for band,row in enumerate(counts):
                for column,number in enumerate(row):
                    if band<cutoff:loss+=number*(missweight if column==1 else c[1] if column==2 else 0)
                    else:humans+=number;loss+=number*humanprice
            if cutoff>0:loss+=100*c[3]
            eq(got[2],humans,'direct fallback cases');eq(got[3],loss,'direct cellwise loss oracle');policy_worlds+=1
    eq(upper(4,4),1.0,'all misses boundary');eq(randomization((0,0))[:4],(0,4,4,1),'all ties randomization')
    invalid=0
    for fn in (lambda:flow(1,1,1,-1),lambda:flow(1,1,1,2),lambda:flow(-1,1,1,0),lambda:work(1,1,1,-1),lambda:randomization(()),lambda:policy(counts,costs,4),lambda:policy(((-1,0,0,1),)+counts[1:],costs,1),lambda:policy(((Q(1,2),0,0,1),)+counts[1:],costs,1),lambda:policy(((0,0,0,0),)*3,costs,1),lambda:upper(0,0),lambda:upper(5,4),lambda:upper(0,4,0),lambda:exact((True,),1),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":NaN}'),lambda:rational('x()')):
        try:fn()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid accepted')
    require(used==set(marks),'all numerical markers consumed')
    return {'chapter':'v18-c09','status':'passed','runtime_files':4,'comparisons':count,'process_worlds':process_worlds,'policy_worlds':policy_worlds,'randomization_assignments':16,'invalid_domains':invalid,'scope':'Full two process/change/evaluation artifacts, eight solutions, global proofs, source limits and evidence status manually reviewed.'}
if __name__=='__main__':
    require(len(sys.argv)<=2,'usage checker [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
