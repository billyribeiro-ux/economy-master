"""Four-payload trade chapter audit, exact primitives and quiet portable API."""
import ast,json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite,sqrt
from pathlib import Path
FILES=('content/chapters/v15-c05.html','scripts/check_v15_c05.py','content/reviews/v15-c05-sources.json','content/reviews/v15-c05-author.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def num(x):
    need(type(x) in (int,float,F) and isfinite(float(x)),'finite nonboolean number');return F(str(x)) if type(x) is float else F(x)
def literal(s):
    def walk(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            d=walk(n.right);need(d!=0,'nonzero divisor');return walk(n.left)/d
        raise ValueError('numeric literal only')
    return walk(ast.parse(s.replace('−','-').rsplit('=',1)[-1].strip(),mode='eval').body)
def exporter(B,w,setup,phi,tau,sunk=False):
    B,w,setup,phi,tau=map(num,(B,w,setup,phi,tau));need(min(B,w,setup,phi)>0 and tau>=1 and type(sunk) is bool,'export primitive domain');c=w*tau/phi;q=B/(4*c*c);contribution=B/(4*c);price=2*c;profit=contribution-setup
    if sunk or profit>0:choices=(q,)
    elif profit==0:choices=(F(0),q)
    else:choices=(F(0),)
    selected=choices[0];return {'choices':choices,'q':selected,'positive_q':q,'price':price,'contribution':contribution,'profit':profit if selected else (-setup if sunk else F(0)),'revenue':price*selected,'produced':tau*selected,'variable':tau*selected/phi,'labor':tau*selected/phi+(setup/w if selected or sunk else 0)}
def network(a,b,vh,vf,y,th=0,tf=0):
    a,b,vh,vf,y,th,tf=map(num,(a,b,vh,vf,y,th,tf));need(0<=a<1 and 0<=b<1 and min(vh,vf,y)>0 and min(th,tf)>=0,'contracted network domain');d=1-a*b;xh=y/d;xf=b*xh;ph=(vh+b*vf+b*th+a*b*tf)/d;pf=vf+a*(ph+tf);gh=th*xf;gf=tf*a*xf;vah=vh*xh;vaf=vf*xf;ch=(vah+gh)/ph;cf=(vaf+gf)/ph;return {'xh':xh,'xf':xf,'ph':ph,'pf':pf,'gh':gh,'gf':gf,'vah':vah,'vaf':vaf,'ch':ch,'cf':cf,'bill':ph*y}
def processing(ty,tm):
    ty,tm=map(num,(ty,tm));need(0<=ty<=4 and 0<=tm<=4,'maintained tariff rectangle');D=10-ty;q=max(F(0),2+ty-tm);M=D-q;need(M>=0,'nonnegative final imports');cost=2*q+q*q/2;profit=(10+ty-6-tm)*q-cost;gov=ty*M+tm*q;cs=D*D/2;W=cs+profit+gov;N=100+profit+gov-(10+ty)*D;need(N>=0,'household feasible numeraire');return {'D':D,'q':q,'M':M,'G':gov,'profit':profit,'W':W,'N':N,'cost':cost,'foreign':10*M+6*q,'ep':(ty-tm)/4}
def adjustment(old,new,slope,kmax,reduction=1,training=0,subsidy=0,fee=0):
    old,new,slope,kmax,reduction,training,subsidy,fee=map(num,(old,new,slope,kmax,reduction,training,subsidy,fee));need(new>old>=0 and slope>0 and kmax>0 and 0<reduction<=1 and min(training,subsidy,fee)>=0 and fee<=training,'adjustment domain');m=max(F(0),min(F(1),(new-old+subsidy-fee)/(slope+reduction*kmax)));w=new-slope*m;profit=slope*m*m/2;production=old*(1-m)+new*m-slope*m*m/2;move=reduction*kmax*m*m/2;train=training*m;tax=(training+subsidy-fee)*m;W=production-move-train;return {'m':m,'w':w,'profit':profit,'move':move,'training':train,'tax':tax,'W':W}
def slope(x,y):
    x=tuple(map(num,x));y=tuple(map(num,y));need(len(x)==len(y) and len(x)>1,'regression shape');mx=sum(x)/len(x);my=sum(y)/len(y);v=sum((a-mx)**2 for a in x);need(v>0,'positive regressor variation');return sum((a-mx)*(b-my) for a,b in zip(x,y))/v
def identified(reduced,first,glo,ghi):
    reduced,first,glo,ghi=map(num,(reduced,first,glo,ghi));need(first!=0 and glo<=ghi,'nonzero firststage and ordered direct-effect interval');return tuple(sorted(((reduced-glo)/first,(reduced-ghi)/first)))
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.outputs={};self.prompts=[];self.solutions=[];self.cases=[];self.ids=[];self.sources={};self.links=set();self.disclosures=0
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','fragment heading')
        if 'id' in a:need(a['id'].startswith('v15-c05-') and a['id'] not in self.ids,'chapter unique IDs');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and a.get('id','').startswith('v15-c05-e'):self.prompts.append(a['id'])
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
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(root/f).read_bytes() for f in FILES};doc=Read();doc.feed(raw[FILES[0]].decode());need(not doc.stack,'complete markup');review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]]);bind=review['payload_bindings'];need(len(bind)==3 and {b['path'] for b in bind}==set(FILES[:3]),'three nonself bindings')
    for b in bind:need((b['bytes'],b['sha256'])==(len(raw[b['path']]),sha256(raw[b['path']]).hexdigest()),'frozen bytes')
    ex=['v15-c05-e'+str(i) for i in range(1,11)];need(doc.prompts==doc.solutions==ex and set(review['exact_prompt_review'])==set(ex),'ten complete matched solutions');need(doc.cases==['v15-c05-case'+str(i) for i in range(1,6)] and doc.disclosures==3,'five cases and full teaching answers');need({'v15-c04.html','curriculum.html#v15-c06'}<=doc.links,'prerequisite and planned successor');need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==4,'four exact source identities');need(all(s['verification'] and s['limits'] for s in sources['sources']),'bounded source inspection')
    inp={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.outputs.items()};expected={};comparisons=0
    def eq(a,b,label='identity'):
        nonlocal comparisons
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:
            comparisons+=1
            if isinstance(a,float) or isinstance(b,float):need(abs(float(a)-float(b))<1e-9*max(1,abs(float(b))),label)
            else:need(a==b,label+str((a,b)))
    primitives={'firms':(36,1,9,(1,2,4)),'network':(F(1,4),F(1,2),3,2,70),'tariffs':(10,6,2,1),'workers':(6,12,4,12),'exposure':((0,F(1,2),1),2,-1,1)};need(set(inp)==set(primitives),'five literal input groups')
    for k,v in primitives.items():eq(inp[k],v,k)
    B,w,Fsetup,phis=inp['firms'];before=[exporter(B,w,Fsetup,p,2) for p in phis];after=[exporter(B,w,Fsetup,p,F(3,2)) for p in phis];tot=lambda group,key:sum(x[key] for x in group);expected['firm-after']=tuple(tot(after,k) for k in ('q','produced','variable','labor','revenue','profit'));chosen=lambda group:[p for p,x in zip(phis,group) if x['q']];pb,pa=chosen(before),chosen(after);expected['firm-selection']=(len(pb),len(pa),sum(pb)/len(pb),sum(pa)/len(pa),tot(before,'produced')/tot(before,'variable'),tot(after,'produced')/tot(after,'variable'));eq(before[1]['choices'],(0,9))
    for group in (before,after):
        labor=tot(group,'labor');rev=tot(group,'revenue');profit=tot(group,'profit');eq(rev,w*labor+profit);need(labor<=100 and rev<=200,'explicit world funding');home=100-labor+rev;foreign=200-rev;eq(home,100+profit);eq(home+foreign,200+100-labor)
    changed=[exporter(B,w,12,p,F(3,2)) for p in phis];sunk=[exporter(B,w,12,p,F(3,2),True) for p in phis];expected['e1-choices']=tuple(x['choices'] for x in changed);expected['e1-sunk']=tuple(x['profit'] for x in sunk);joint=[exporter(16,w,Fsetup,p,1) for p in phis];expected['e2']=(len(chosen(joint)),tot(joint,'q'),tot(joint,'revenue'),tot(joint,'profit'));need(all(exporter(8,w,Fsetup,p,1)['q']==0 for p in phis),'falling demand export counterexample')
    # Completed-square certificate for every positive-q deviation; ties and sunk alternatives separately retained.
    for p,tau in product(phis,(F(1),F(3,2),F(2))):
        f=exporter(B,w,Fsetup,p,tau);c=w*tau/p
        for z in (F(1,4),F(1),F(2),F(4),F(8),F(12)):
            contribution=6*z-c*z*z;bound=f['contribution'];eq(contribution,bound-c*(z-3/c)**2);need(contribution-Fsetup<=max(F(0),bound-Fsetup),'global export deviation');comparisons+=1
    a,b,vh,vf,y=inp['network'];base=network(a,b,vh,vf,y);one=network(a,b,vh,vf,y,1);expected['network-base']=tuple(base[k] for k in ('xh','xf','ph','pf','vah','vaf'));expected['network-tariff']=tuple(one[k] for k in ('ph','pf','gh','bill','ch','cf'));bigger=network(a,b,vh,vf,77);expected['e3']=tuple(bigger[k] for k in ('xh','xf','vah','vaf','ch','cf'));both=network(a,b,vh,vf,y,1,1);expected['e4']=tuple(both[k] for k in ('ph','pf','gh','gf','bill','ch','cf'))
    for orders,th,tf in ((y,0,0),(y,1,0),(77,0,0),(y,1,1),(14,2,3)):
        n=network(a,b,vh,vf,orders,th,tf);xh,xf,ph,pf=(n[k] for k in ('xh','xf','ph','pf'));eq(xh,orders+a*xf);eq(xf,b*xh);eq(ph,vh+b*(pf+th));eq(pf,vf+a*(ph+tf));eq(n['bill'],n['vah']+n['vaf']+n['gh']+n['gf']);eq(n['ch']+n['cf'],orders);eq(a*xf*ph+n['cf']*ph,xf*pf);eq(ph*xh-(pf+th)*xf,n['vah']);eq(pf*xf-(ph+tf)*a*xf,n['vaf'])
    eq(base['ph']*base['xh']+base['pf']*base['xf'],F(3440,7));eq(a*base['xf']*base['ph']+base['xf']*base['pf'],F(1200,7));eq((one['ph']-base['ph'],one['pf']-base['pf']),(F(4,7),F(1,7)))
    # Requirements from successive production rounds, with an exact residual and proven norm tail bound.
    total=(F(0),F(0));term=(y,F(0))
    for depth in range(9):
        total=tuple(x+z for x,z in zip(total,term));term=(a*term[1],b*term[0]);residual=(y+a*total[1]-total[0],b*total[0]-total[1]);eq(residual,term);need(sum(abs(v) for v in term)<=F(1,2)**(depth+1)*y,'input-output norm bound');comparisons+=1
    py,pm,ty,tm=inp['tariffs'];t=processing(ty,tm);expected['tariff-case']=(t['D'],t['q'],t['M'],t['G'],t['profit'],t['W'],52-t['W'],t['ep']);expected['e5']=tuple(tuple(processing(0,rate)[k] for k in ('q','M','q','G','ep','W')) for rate in (1,4));rates=(0,2,3);expected['e6']=(tuple(processing(2,r)['q'] for r in rates),tuple(52-processing(2,r)['W'] for r in rates))
    for ty,tm in product((0,1,2,3,4),repeat=2):
        t=processing(ty,tm);D,q=t['D'],t['q'];eq(t['W'],52-((D-10)**2+(q-2)**2)/2);eq(t['W'],20*D-D*D/2-t['cost']-t['foreign']);eq(t['N']+t['cost']+t['foreign'],100);eq((10+ty)*D+t['N'],100+t['profit']+t['G']);need(t['W']<=52,'global tariff bound');comparisons+=1
    workers=inp['workers'];base=adjustment(*workers);sub=adjustment(*workers,subsidy=1);free=adjustment(*workers,reduction=F(1,2),training=1);fee=adjustment(*workers,reduction=F(1,2),training=1,fee=1);expected['worker-subsidy']=(base['m'],base['w'],base['W'],sub['m'],sub['w'],sub['tax'],sub['W']);expected['worker-training']=(free['m'],free['W'],fee['m'],fee['W']);expected['e7']=sub['profit']-base['profit'];expected['e8']=(free['W'],fee['W'],fee['W']-free['W']);eq(base['W']-sub['W'],F(1,32));eq(free['W']-base['W'],F(3,40));eq((12-(sub['w']-6+1))/12,F(9,16));need(sub['tax']>0,'stayer loss from actual tax')
    for reduction,training,subsidy,charge in ((1,0,0,0),(1,0,1,0),(F(1,2),1,0,0),(F(1,2),1,0,1)):
        u=adjustment(*workers,reduction=reduction,training=training,subsidy=subsidy,fee=charge);m=u['m'];eq(reduction*12*m,u['w']-6+subsidy-charge);wages=6*(1-m)+u['w']*m;eq(wages+u['profit']-u['move']-u['training'],u['W']);eq((subsidy+training)*m,charge*m+u['tax']);need(reduction*12*m+charge+u['tax']<=12,'financeable marginal mover');comparisons+=1
    for f in (F(0),F(1,4),F(1,2),F(3,4),F(1)):
        u=adjustment(*workers,reduction=F(1,2),training=1,fee=f);eq(u['m'],(6-f)/10);eq(u['tax'],(1-f)*u['m']);eq(u['W'],F(29,4)-(1-f)**2/20)
    for m in (F(j,16) for j in range(17)):
        W=6+6*m-8*m*m;WT=6+5*m-5*m*m;eq(W,F(57,8)-8*(m-F(3,8))**2);eq(WT,F(29,4)-5*(m-F(1,2))**2);need(W<=base['W'] and WT<=fee['W'],'full-interval concavity witnesses');comparisons+=1
    shares,mult,theta,gamma=inp['exposure'];X=tuple(mult*s for s in shares);Y=tuple(100+theta*x+gamma*s for x,s in zip(X,shares));observed=slope(X,Y);reduced=slope(shares,Y);first=slope(shares,X);lo,hi=identified(reduced,first,0,1);expected['exposure-set']=(observed,lo,hi);expected['e9']=identified(reduced,first,-1,2);expected['e10']=F(-2)-F(-1,2);eq(Y,(100,F(199,2),99));eq((reduced,first),(-1,2))
    for tt in (F(-3,2),F(-1),F(-1,2),F(0)):
        gg=reduced-first*tt;eq(tuple(100+tt*x+gg*s for x,s in zip(X,shares)),Y);eq(tuple(x-first*s for x,s in zip(X,shares)),(0,0,0))
    need(set(expected)==set(shown),'all numerical result groups')
    for k,v in expected.items():eq(shown[k],v,'HTML result '+k)
    invalid=(lambda:num(True),lambda:num(float('inf')),lambda:literal('1/0'),lambda:literal('f(1)'),lambda:exporter(0,1,9,2,1),lambda:exporter(36,0,9,2,1),lambda:exporter(36,1,9,0,1),lambda:exporter(36,1,9,2,F(1,2)),lambda:exporter(36,1,9,2,1,1),lambda:network(1,F(1,2),3,2,70),lambda:network(F(1,4),F(1,2),3,2,0),lambda:network(F(1,4),F(1,2),3,2,70,-1),lambda:processing(5,0),lambda:processing(0,-1),lambda:adjustment(6,5,4,12),lambda:adjustment(6,12,4,12,reduction=0),lambda:adjustment(6,12,4,12,fee=1),lambda:slope((1,1),(2,3)),lambda:slope((1,2),(1,)),lambda:identified(1,0,0,1),lambda:identified(1,1,2,1));rejected=0
    for fn in invalid:
        try:fn()
        except ValueError:rejected+=1
        else:raise ValueError('invalid domain accepted')
    for f,b in raw.items():need((root/f).read_bytes()==b,'payload mutation')
    result={'chapter':'v15-c05','status':'passed','worked_cases':5,'solutions':10,'input_groups':len(inp),'result_groups':len(shown),'comparisons':comparisons,'rejected_inputs':rejected,'runtime_files':4,'open_findings':[]};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
