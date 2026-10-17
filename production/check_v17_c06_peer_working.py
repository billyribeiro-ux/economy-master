"""Independent six-file V17C06 oracle. Author checker is opaque bytes only."""
import ast,hashlib,json,sys
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
FILES=('production/v17-c06-working.html','production/check_v17_c06_working.py','production/v17-c06-sources-working.json','production/v17-c06-author-review-working.json','production/check_v17_c06_peer_working.py','production/v17-c06-peer-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError('C06 peer: '+msg)
def parse(s):
    def v(n):
        if isinstance(n,ast.Tuple):return tuple(v(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return F(str(n.value))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -v(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return v(n.left)/v(n.right)
        raise ValueError('invalid manuscript literal')
    return v(ast.parse(s.strip(),mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.prompts=[];self.answers=[];self.worked=[];self.sources=[];self.values={};self.capture=None;self.tables=[];self.row=None;self.cell=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(t!='h1','chapter h1')
        if 'id' in a:self.ids.append(a['id'])
        if t=='li' and any(tag=='ol' and 'exercises' in d.get('class','').split() for tag,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            need(any(tag=='details' and 'solutions' in d.get('class','').split() for tag,d in self.stack),'solutions disclosure');self.answers.append(a['data-solution-for'])
        if t=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for k in ('input','result'):
            if 'data-'+k in a:
                key=(k,a['data-'+k]);need(key not in self.values and self.capture is None,'duplicate marker');self.values[key]='';self.capture=(t,key)
        if t=='table':self.tables.append([])
        if t=='tr':self.row=[]
        if t in ('td','th'):self.cell=[]
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        if self.capture:self.values[self.capture[1]]+=s
        if self.cell is not None:self.cell.append(s)
    def handle_endtag(self,t):
        need(bool(self.stack) and self.stack.pop()[0]==t,'unbalanced HTML')
        if self.capture and self.capture[0]==t:self.capture=None
        if t in ('td','th'):self.row.append(''.join(self.cell).strip());self.cell=None
        if t=='tr':self.tables[-1].append(self.row);self.row=None

def nums(seq,n):
    need(isinstance(seq,(tuple,list)) and len(seq)==n,'dimensions');need(all(type(x) in (F,int) for x in seq),'exact numbers');return tuple(F(x) for x in seq)
def pv(flows,rate):
    flows=nums(flows,len(flows));(rate,)=nums((rate,),1);need(len(flows)>0 and rate>-1,'cash-flow domain')
    acc=F(0)
    for x in reversed(flows):acc=x+acc/(1+rate)
    return acc

def finance(raw):
    cost,y1,y2,rate,cash,reserve,loan,repay=nums(raw,8)
    need(all(x>=0 for x in (cost,cash,reserve,loan,repay)),'negative cash contract')
    vals=(pv((0,y1),rate),pv((0,0,y2),rate),pv((-cost,y1,y2),rate))
    equity=(-cost+loan,y1-repay,y2)
    return vals,(cash-cost,cash+loan-cost),equity,pv(equity,rate),pv((loan,-repay),rate)
def did(raw):
    t0,t1,c0,c1=nums(raw,4);need(all(0<=x<=100 for x in (t0,t1,c0,c1)),'percent support');return t1-t0,c1-c0,(t1-c1)-(t0-c0)
def world(raw,missing):
    t0,t1,c0,c1=nums(raw,4);(missing,)=nums((missing,),1);need(0<=missing<=100,'counterfactual percent');return t1-missing,(missing-t0)-(c1-c0)
def interval(raw,bounds):
    lo,hi=nums(bounds,2);need(lo<=hi,'unordered bounds');t0,t1,c0,c1=nums(raw,4)
    return world(raw,t0+(c1-c0)+hi)[0],world(raw,t0+(c1-c0)+lo)[0]
def agreement(a,b):
    need(len(a)==len(b) and len(a)>0,'rater pairs');a=nums(a,len(a));b=nums(b,len(b));diff=tuple(x-y for x,y in zip(a,b));n=len(a)
    return sum(diff)/n,sum(abs(d) for d in diff)/n,F(sum(x==0 for x in diff),n)
def missing_mean(total,observed,size,lo,hi):
    total,lo,hi=nums((total,lo,hi),3);need(type(observed) is int and type(size) is int and 0<=observed<=size and size>0 and lo<=hi,'roster domain');need(observed*lo<=total<=observed*hi,'observed total support')
    return ((total+(size-observed)*lo)/size,(total+(size-observed)*hi)/size)
def score(parts,maxima):
    parts=nums(parts,len(maxima));maxima=nums(maxima,len(maxima));need(all(0<=a<=b for a,b in zip(parts,maxima)) and sum(maxima)>0,'rubric points');return sum(parts),100*sum(parts)/sum(maxima)

def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1];payload={f:(root/f).read_bytes() for f in FILES};review=json.loads(payload[FILES[5]])
    need(set(review['payloads'])==set(FILES[:5]),'five nonself hashes')
    for f,record in review['payloads'].items():need(record=={'bytes':len(payload[f]),'sha256':hashlib.sha256(payload[f]).hexdigest()},'freeze changed '+f)
    p=Page();p.feed(payload[FILES[0]].decode());p.close();need(not p.stack and p.capture is None and len(p.ids)==len(set(p.ids)),'complete unique HTML')
    need(p.prompts==p.answers==['v17-c06-e'+str(i) for i in range(1,9)],'eight task/solution matches');need(p.worked==['v17-c06-case1','v17-c06-case2'],'two full artifacts')
    src=json.loads(payload[FILES[2]]);need(src['actual_inspector']=='v15_support_review','source inspector');need(set(p.sources)=={(x['id'],x['url']) for x in src['sources']},'source mapping')
    markers={key:parse(x) for key,x in p.values.items()};used=set();n=0
    def get(kind,key):used.add((kind,key));return markers[kind,key]
    def equal(x,y,label):
        nonlocal n
        if isinstance(x,tuple) or isinstance(y,tuple):
            need(isinstance(x,tuple) and isinstance(y,tuple) and len(x)==len(y),label+' shape')
            for a,b in zip(x,y):equal(a,b,label)
        else:n+=1;need(x==y,label)
    def result(key,x):equal(get('result',key),x,key)
    project=get('input','project');rate=get('input','rate');cash,reserve=get('input','cash-reserve');loan,repay=get('input','loan');original=(*project,rate,cash,reserve,loan,repay)
    vals,cashes,equity,ev,lv=finance(original);result('project-value',vals);result('equity',equity);result('finance-check',cashes+(ev,lv));equal((cashes[0]>=reserve,cashes[1]>=reserve),(False,True),'reserve regime')
    # Independently read criterion evidence is classified in peer record, not machine-inferred.
    fm=tuple(parse(row[1]) for row in p.tables[0][1:]);em=tuple(parse(row[1]) for row in p.tables[2][1:]);equal(fm,(2,4,4,4,4,2),'finance rubric');equal(em,(4,4,6,2,4),'evidence rubric')
    nvec=(2,4,1+0+2,2+2,2+2,1+1);kvec=(0,0,0+0+2,2+0,0,0);pvec=(2+2,2+2,0+2+2,0,0)
    for key,vec,maxima in (('n',nvec,fm),('k',kvec,fm),('p',pvec,em)):
        result(key+'-score',vec);result(key+'-total',score(vec,maxima)[0])
    equal((F(30)*(1+rate)**2,F(32)*(1+rate)**2),(F(375,8),50),'inverse compounding feedback')
    fresh=get('input','fresh-project');fv,fc,fe,fn,fl=finance(fresh);result('fresh-values',fv+fc+fe+(fn,));equal((fl,fc[1]>=31),(0,False),'fresh loan/raised reserve')
    table=p.tables[1];raw=tuple(parse(x) for row in table[1:] for x in row[1:]);result('did-values',did(raw));result('worlds',(47,)+world(raw,47)+(55,)+world(raw,55))
    fr=get('input','fresh-did');result('fresh-did-values',did(fr[:4])+interval(fr[:4],fr[4:]));equal((world(fr[:4],56)[0],world(fr[:4],53)[0]),(2,5),'fresh endpoint worlds')
    result('e1',(score(nvec,fm)[0],)+agreement(get('input','rater-a'),get('input','rater-b')));result('e2',(2,1+0+2,2+1+0+2,nvec[1]+nvec[2]))
    e3=pv((0,44),F(1,10));result('e3',(e3,e3-36,45-36));equal(score((4,4,6,2,4),em),(20,100),'fair full rubric')
    domains=get('input','domains');overall=sum(domains)/len(domains);result('e5-score',overall);equal((overall>=85,min(domains)>=75),(True,False),'aggregate/domain separation');result('e5-bound',(6-1,6-(-2)))
    result('e6',did((60,63,50,55)));mm=missing_mean(8*9,8,10,0,10);result('e7',mm+tuple(x-7 for x in mm));result('e8',(pv((-40,48),F(1,5)),pv((-40,47),F(1,5))));result('retention',(pv((0,90),F(1,4)),pv((-72,90),F(1,4)),100-72))
    equal(sum((4,4,6,2,4)),20,'fresh evidence rubric');equal(score((12,),(20,)),(12,60),'initial record');equal(score((20,),(20,)),(20,100),'assisted correction arithmetic only')
    worlds=0
    for price in (F(0),F(4),F(5)):
        changed=(*original[:7],price);v,c,e,ve,vl=finance(changed);equal(ve,v[2]+vl,'PV distributive identity alternative finance');worlds+=1
    for r in (F(-1,2),F(0),F(1,4)):
        equal(pv((5,-3,8),r),pv((2,-4,6),r)+pv((3,1,2),r),'global linearity witnesses');worlds+=1
    for missing in (0,40,47,50,55,100):
        tau,delta=world(raw,missing);equal(tau+delta,did(raw)[2],'DID identity boundary');worlds+=1
    for k in range(7):
        delta=F(-1)+F(k,2);missing=fr[0]+did(fr[:4])[1]+delta;tau,gap=world(fr[:4],missing);equal((tau+gap,2<=tau<=5),(4,True),'fresh interior sharpness');worlds+=1
    means=tuple(F(72+a+b,10) for a,b in product((0,5,10),repeat=2));equal((min(means),max(means)),mm,'missing score completion extrema');worlds+=len(means)
    equal(agreement((0,10),(10,0)),(0,10,0),'cancellation boundary');equal(agreement((4,4),(4,4)),(0,0,1),'perfect descriptive agreement');equal(missing_mean(18,2,2,0,10),(9,9),'complete roster');equal(missing_mean(0,0,2,0,10),(0,10),'none observed')
    invalid=0
    for f in (lambda:pv((0,1),-1),lambda:pv((),0),lambda:pv((True,1),0),lambda:finance((-1,2,3,0,3,1,0,0)),lambda:agreement((),()),lambda:agreement((1,),(1,2)),lambda:missing_mean(1,1,0,0,10),lambda:missing_mean(30,2,3,0,10),lambda:score((3,),(2,)),lambda:score((0,),(0,)),lambda:interval((40,55,30,37),(2,-1)),lambda:world((40,55,30,37),101),lambda:did((0,101,0,2)),lambda:parse('__import__("os")')):
        try:f()
        except (ValueError,TypeError):invalid+=1
        else:raise ValueError('invalid accepted')
    need(used==set(markers),'all numeric markers used')
    return {'chapter':'v17-c06','component':'independent_peer','status':'passed','runtime_files':6,'worked_artifacts':2,'exercises':8,'numeric_markers':sum(k[0]=='result' for k in markers),'comparisons':n,'alternative_worlds':worlds,'invalid_domains':invalid,'author_checker':'Opaque bytes/hash only; never read/imported/executed.','scope':'Full responses, rubrics, proofs, feedback and all eight solutions independently read; no actual learner outcome or reliability/efficacy claim.'}
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage checker [root]');check(sys.argv[1] if len(sys.argv)==2 else None)
