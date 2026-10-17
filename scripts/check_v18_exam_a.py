"""V18 Form A independent author arithmetic and structural gates."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations,product
import ast,hashlib,json,re,sys
FILES=('content/assessments/parts/v18-exam-a.html','scripts/check_v18_exam_a.py','content/reviews/v18-exam-a-sources.json','content/reviews/v18-exam-a-author.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(path):
    b=path.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def literal(text):
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.Tuple):return tuple(visit(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('exact rational marker')
    return visit(ast.parse(text.strip(),mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.active=[];self.ids=[];self.inputs={};self.results={};self.tasks=[];self.answers=[];self.answertext={};self.sources={};self.hrefs=[];self.h1=0;self.tables=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if t=='h1':self.h1+=1
        if 'id' in a:need(a['id'] not in self.ids,'unique IDs');self.ids.append(a['id'])
        if 'href' in a:self.hrefs.append(a['href'])
        if 'data-points' in a:self.tasks.append((a['id'],int(a['data-points'])))
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in v.get('class','').split() for x,v in self.stack),'solution disclosure');k=a['data-solution-for'];self.answers.append(k);self.answertext[k]='';self.active.append((self.answertext,k,len(self.stack)))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for k,d in [('data-input',self.inputs),('data-result',self.results)]:
            if k in a:need(a[k] not in d,'unique markers');d[a[k]]='';self.active.append((d,a[k],len(self.stack)))
        if t=='table':self.tables.append([])
        if t=='tr':self.tables[-1].append([])
        if t in ('td','th'):
            row=self.tables[-1][-1];row.append('');self.active.append((row,len(row)-1,len(self.stack)))
        if t not in ('br','hr','img','input','link','meta'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[v for v in self.active if v[2]<len(self.stack)]
def vec(values,n=None):
    need(type(values) is tuple and (n is None or len(values)==n) and all(type(x) in (int,F) for x in values),'exact vector');return tuple(F(x) for x in values)
def clinic(values):
    px,py,hx,hy,cx,cy,mx,my,hours,cash=vec(values,10)
    need(min(px,py,hx,hy,cx,cy)>0 and min(mx,my,hours,cash)>=0 and mx.denominator==my.denominator==1,'clinic domain')
    feasible={}
    for x in range(int(mx)+1):
        for y in range(int(my)+1):
            seats=px*x+py*y;priority=py*y;used=hx*x+hy*y;cost=cx*x+cy*y
            if used<=hours and cost<=cash and 3*priority>=seats:feasible[(x,y)]=(seats,used,cost,priority)
    best=max((v[0],-v[1]) for v in feasible.values());chosen=tuple(k for k,v in feasible.items() if (v[0],-v[1])==best)
    return chosen,feasible

def change(values,index,new):
    out=list(values);out[index]=F(new);return tuple(out)
def bargain(mode,outside):
    value,cost=vec(mode,2);du,dl,cash=vec(outside,3);need(min(value,cost,du,dl,cash)>=0,'bargain domain');lo=cost+dl;hi=min(value-du,cash)
    if lo>hi:return None
    center=(value-du+cost+dl)/2;t=min(hi,max(lo,center));gains=(value-t-du,t-cost-dl)
    return (lo,hi),t,gains,gains[0]*gains[1],center

def incentive(s,values):
    ecap,scap,value,mult=vec(values,4);s,=vec((s,),1);need(min(ecap,scap,value,mult)>0 and 0<=s<=scap,'incentive domain')
    e=min(s,ecap);return e,value*e-mult*s*e,s*e-e*e/2

def posterior(p,hit,false):
    p,hit,false=vec((p,hit,false));need(all(0<=x<=1 for x in (p,hit,false)),'probability domain');joint=p*hit;mass=joint+(1-p)*false;need(mass>0,'impossible signal');return mass,joint/mass

def credit(data,rates):
    c,n,d,e,w,loss,cf,ef=vec(data,8);rx,ry=vec(rates[0],2);px,py=vec(rates[1],2)
    need(min(c,n,d,e,w,loss,cf,ef)>=0 and c+n==d+e and w<=min(c,d) and loss<=n and min(rx,ry,px,py)>0 and rx!=ry,'credit domain')
    cashcap=c-w-cf;riskcap=e-loss-ef
    if min(cashcap,riskcap)<0:return None
    xmax=min(cashcap,riskcap/rx);candidates={F(0),xmax,(ry*cashcap-riskcap)/(ry-rx)};scores={}
    for x in candidates:
        if 0<=x<=xmax:
            y=min(cashcap-x,(riskcap-rx*x)/ry)
            if y>=0:scores[(x,y)]=px*x+py*y
    best=max(scores.values());choices=tuple(k for k,v in scores.items() if v==best)
    return choices,best,cashcap,riskcap

def credit_ledger(data,rates,x,y,extra=0,issue=0):
    c,n,d,e,w,loss,cf,ef=vec(data,8);rx,ry=vec(rates[0],2);x,y,extra,issue=vec((x,y,extra,issue));need(min(x,y,extra,issue)>=0,'transaction domain');newloss=rx*x+ry*y
    cash=c-w-x-y+issue;loans=n+x+y-loss-newloss-extra;dep=d-w;eq=e-loss-newloss-extra+issue;need(cash+loans==dep+eq,'balance identity');return cash,loans,dep,eq,cash+loans

def queue(values):
    pool,intake,review,newintake,validation,arrival,backlog=vec(values,7);need(pool>0 and intake+review>0 and newintake+validation+review>0 and min(intake,review,newintake,validation,arrival,backlog)>=0,'queue domain')
    old=pool/(intake+review);new=pool/(newintake+validation+review);return old,new,max(F(0),backlog+(arrival-old)*5),(backlog/(new-arrival) if new>arrival else None)
def pilot(pairs):
    need(type(pairs) is tuple and len(pairs)>0,'pilot domain');pairs=tuple(vec(p,2) for p in pairs);m=len(pairs);observed=sum(a-b for a,b in pairs)/m
    dist=tuple(sorted(sum(pair[flip]-pair[1-flip] for pair,flip in zip(pairs,flips))/m for flips in product((0,1),repeat=m)));return observed,dist,F(sum(abs(x)>=abs(observed) for x in dist),len(dist))
def crisis(values,cash,equity,cf,ef):
    p,hit,false,fee,bad,backup,release,setup,deadline=vec(values,9);cash,equity,cf,ef=vec((cash,equity,cf,ef));need(all(0<=x<=1 for x in (p,hit,false)) and min(fee,bad,backup,release,setup,deadline,cash,equity,cf,ef)>=0,'crisis domain')
    available={'W':(F(0),bad,F(0))}
    if release+setup<=deadline and cash-fee-backup>=cf and equity-fee-backup>=ef:available['B']=(backup,backup,backup)
    need(cash-fee>=cf and equity-fee>=ef,'unfunded diagnostic')
    joint=((p*hit,(1-p)*false),(p*(1-hit),(1-p)*(1-false)));mass=tuple(sum(x) for x in joint);post=tuple(x[0]/m if m else None for x,m in zip(joint,mass));scores={}
    for acts in product(available,repeat=2):
        score=fee+sum(j[0]*available[a][1]+j[1]*available[a][0] for j,a in zip(joint,acts));scores[''.join(acts)]=score
    best=min(scores.values());choice=tuple(k for k,v in scores.items() if v==best)
    expenses={k:fee+max(available[a][2] for a,m in zip(k,mass) if m) for k in choice}
    return mass,post,scores,choice,expenses

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];start={p:digest(root/p) for p in FILES};review=json.loads((root/FILES[3]).read_text());need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for path,binding in review['payloads'].items():need(start[path]==binding,'binding '+path)
    page=Page();page.feed((root/FILES[0]).read_text());need(not page.stack and page.h1==0,'fragment structure')
    tasks=[('v18-exam-a-q'+str(i),5) for i in range(1,21)];need(page.tasks==tasks and page.answers==[k for k,v in tasks],'20 complete tasks')
    need('form-a' in page.ids and 'solutions-a' in page.ids and all(x in ('form-a','solutions-a') or x.startswith('v18-exam-a-') for x in page.ids),'scoped identifiers')
    for k,_ in tasks:
        match=re.search(r'Rubric5:(.*?)\.$',page.answertext[k],re.S);need(match is not None,'rubric '+k);points=[int(x) for x in re.findall(r'(\d+)\s*(?:;|\.|$)',match.group(1))];need(sum(points)==5,'additive5 '+k)
    need(all('v18-c'+str(i).zfill(2)+'.html' in page.hrefs for i in range(1,13)),'all12 coverage')
    sources=json.loads((root/FILES[2]).read_text());need(page.sources=={s['id']:s['url'] for s in sources['sources']},'scoped source URLs')
    inp={k:literal(v) for k,v in page.inputs.items()};shown={k:literal(v) for k,v in page.results.items()};need(set(inp)=={'clinic','cash','bundles','incentives','hiring','lender','lending-rates','workflow','crisis'},'primitive inputs');count=0
    data=inp['clinic'];chosen,options=clinic(data);need(chosen==((1,4),),'unique clinic');x,y=chosen[0];base=options[(x,y)];expected={'q1':(F(x),F(y))+base};count+=1
    local,remote,outside=inp['bundles'];bl=bargain(local,outside);br=bargain(remote,outside);need(br[3]>bl[3],'current bundle ranking');count+=1
    opening,launch,ceiling,floor,tuition=inp['cash'];day0=opening-launch-br[1]-base[2]/2;day30=day0-base[2]/2
    expected['q2']=(day0,day30,day30+tuition,day30,day30-floor);expected['q3']=bl[:2]+(bl[3],)+br[:2]+(br[3],)
    relaxed=outside[:2]+(F(9),);need(bargain(local,relaxed)[1:4]==(9,(3,3),9) and bargain(remote,relaxed)[3]==br[3],'funded ceiling9 ranking');count+=2
    less=change(data,8,15);cc,oo=clinic(less);need(cc==((1,3),),'reduced staff unique');xx,yy=cc[0];row=oo[cc[0]];expected['q4']=(F(xx),F(yy))+row[:3]+(opening-launch-br[1]-row[2],);count+=1
    ic=inp['incentives'];star=ic[2]/(2*ic[3]);e,iv,av=incentive(star,ic);expected['q5']=(star,e,iv,av)
    hc,hpay,hfloor,hprior,hhit,hfalse=inp['hiring'];hm,hpost=posterior(hprior,hhit,hfalse);expected['q6']=(hm,hpost,F(7),F(5));need(hc-hpay<hfloor and hpost!=hhit,'sample essential gates');count+=2
    expected['q7']=((F(4),F(6-4)),(F(6),F(6-6)))
    limited=change(data,7,3);cc,oo=clinic(limited);need(cc==((2,2),),'teaching transfer unique');expected['q11']=tuple(F(x) for x in cc[0])+oo[cc[0]];count+=1
    ld=inp['lender'];lr=inp['lending-rates'];cr=credit(ld,lr);need(cr[0]==((8,4),),'credit unique');xx,yy=cr[0][0];ledger=credit_ledger(ld,lr,xx,yy);expected['q13']=(xx,yy,cr[1])+ledger;count+=1
    altered=change(ld,5,ld[5]+1);before=credit(altered,lr);bx,by=before[0][0];blg=credit_ledger(altered,lr,bx,by);after=credit_ledger(ld,lr,xx,yy,extra=1);issue=max(F(0),ld[6]-after[0],ld[7]-after[3]);repaired=credit_ledger(ld,lr,xx,yy,extra=1,issue=issue)
    expected['q14']=((bx,by,before[1])+blg[:4],repaired[:4]+(issue,));expected['q15']=queue(inp['workflow'])
    pilotrows=next(rows for rows in page.tables if rows and rows[0]==['Pair','Assigned software','Assigned original']);pairs=tuple(tuple(F(x) for x in row[1:]) for row in pilotrows[1:]);expected['q16']=pilot(pairs)
    cash,equity=ledger[0]+5,ledger[3]+5;cv=inp['crisis'];mass,post,scores,choices,expenses=crisis(cv,cash,equity,ld[6],ld[7]);need(choices==('BW',),'crisis unique policy');net=scores['BW'];immediate=min(cv[0]*cv[4],cv[5]);expected['q17']=(cash,equity,mass[0])+post+(net-cv[3],net,immediate-net);count+=1
    _,_,late,lc,le=crisis(change(cv,6,8),cash,equity,ld[6],ld[7]);expense=expenses['BW'];expected['q18']=(min(late.values()),immediate,expense,cash-expense,equity-expense)
    rates=tuple(sorted(set(F(16+sum(bits),22) for bits in product((0,1),repeat=2))));expected['q19']=(rates,F(16,20),day30,day30+tuition,F(18-17))
    need(set(expected)==set(shown),'every numerical key')
    def leaves(v):return sum(leaves(x) for x in v) if isinstance(v,tuple) else 1
    for key,value in expected.items():need(value==shown[key],'displayed '+key);count+=leaves(value)
    # Integer alternatives test resource/access screens and both explicit global-bound certificates.
    clinicworlds=0
    for staff,cashcap,maxy in product((F(12),F(15),F(18)),(F(10),F(13),F(16)),(F(3),F(4))):
        d=change(change(change(data,8,staff),9,cashcap),7,maxy);ch,ops=clinic(d);clinicworlds+=1
        for (a,b),v in ops.items():need(v[0]<=F(6,5)*staff+F(2,5)*maxy and v[0]%2==0 and 3*v[3]>=v[0],'cohort bound and access');count+=3
    for s in (F(0),F(1),F(3,2),F(2),F(4)):
        effort,val,agent=incentive(s,ic);need(val==F(9,2)-2*(s-F(3,2))**2 and val<=iv,'recognition global certificate');count+=2
        for candidate in (F(0),F(1),F(3,2),F(4)):need(s*candidate-candidate*candidate/2<=agent,'agent global response');count+=1
    bargainingworlds=0
    for mode,budget in product((local,remote),(F(3),F(4),F(6),F(7),F(9),F(12))):
        out=outside[:2]+(budget,);b=bargain(mode,out);bargainingworlds+=1
        if b is None:need(mode[1]+out[1]>min(mode[0]-out[0],budget),'empty participation');count+=1;continue
        (low,high),transfer,gains,maximum,center=b;surplus=mode[0]-mode[1]-out[0]-out[1]
        for j in range(5):
            t=low+(high-low)*j/4;productvalue=(mode[0]-t-out[0])*(t-mode[1]-out[1]);need(productvalue==surplus**2/4-(t-center)**2 and productvalue<=maximum,'bargain global certificate');count+=2
    creditworlds=0
    for loss,cf in product((F(0),F(2),F(3),F(6)),(F(6),F(8),F(12))):
        d=change(change(ld,5,loss),6,cf);z=credit(d,lr);creditworlds+=1
        if z is None:continue
        for a,b in z[0]:
            leg=credit_ledger(d,lr,a,b);need(leg[0]>=d[6] and leg[3]>=d[7] and leg[0]+leg[1]==leg[2]+leg[3],'alternative credit ledger');count+=3
    # Exact randomization size under the known sharp-null law, including ties at zero.
    dist=expected['q16'][1]
    for alpha in (F(1,20),F(1,4),F(1,2),F(1)):
        pv=[F(sum(abs(y)>=abs(x) for y in dist),len(dist)) for x in dist];need(F(sum(p<=alpha for p in pv),len(dist))<=alpha,'randomization size');count+=1
    crisisworlds=0
    for prior,release,fee in product((F(1,10),F(1,4),F(1,2)),(F(5),F(6),F(8)),(F(0),F(1,2),F(1))):
        d=change(change(change(cv,0,prior),6,release),3,fee);m,p,sc,ch,ex=crisis(d,cash,equity,ld[6],ld[7]);crisisworlds+=1
        expectedbranch=fee
        for prob,postprob in zip(m,p):
            options=[postprob*d[4]]
            if release+d[7]<=d[8] and cash-fee-d[5]>=ld[6] and equity-fee-d[5]>=ld[7]:options.append(d[5])
            expectedbranch+=prob*min(options)
        need(expectedbranch==min(sc.values()) and all(ex[k]<=min(cash-ld[6],equity-ld[7]) for k in ch),'branch optimum and hard funding');count+=2
    invalid=0
    bad=[lambda:clinic(change(data,0,0)),lambda:clinic(change(data,6,F(1,2))),lambda:bargain((-1,4),outside),lambda:incentive(-1,ic),lambda:incentive(5,ic),lambda:posterior(0,1,0),lambda:posterior(2,1,1),lambda:credit(change(ld,3,11),lr),lambda:credit(change(ld,4,27),lr),lambda:queue(change(inp['workflow'],0,0)),lambda:pilot(()),lambda:crisis(change(cv,3,6),cash,equity,ld[6],ld[7]),lambda:crisis(change(cv,0,-1),cash,equity,ld[6],ld[7]),lambda:literal('(1,0.5)')]
    for f in bad:
        try:f()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(start=={p:digest(root/p) for p in FILES},'runtime mutation')
    out={'volume':'v18','component':'exam_a','status':'passed','runtime_files':4,'prompts':20,'points':100,'domains':5,'chapters':12,'result_groups':len(shown),'comparisons':count,'clinic_worlds':clinicworlds,'bargaining_worlds':bargainingworlds,'credit_worlds':creditworlds,'crisis_worlds':crisisworlds,'randomized_assignments':8,'invalid_domains':invalid,'scope':'Original construction form, full artifact/proof judgment separate from numerical gates; no actual learner leadership or human certification.'}
    json.dumps(out,allow_nan=False);return out
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_exam_a.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
