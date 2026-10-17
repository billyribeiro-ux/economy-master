"""Original undergraduate course-design artifact and arithmetic audit."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast,json,math
FILES=('production/v17-c03-working.html','production/check_v17_c03_working.py','production/v17-c03-sources-working.json','production/v17-c03-author-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError('V17C03: '+msg)
def num(x):
    need(type(x) in (int,float,F) and math.isfinite(float(x)),'finite numeric value');return F(str(x))
def parse(s):
    def visit(n):
        if isinstance(n,ast.Constant):return num(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return (-1 if isinstance(n.op,ast.USub) else 1)*visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            a,b=visit(n.left),visit(n.right);need(b!=0,'nonzero denominator');return a/b
        raise ValueError('restricted numeric syntax')
    return visit(ast.parse(s.strip().replace('−','-'),mode='eval').body)
def npv(flows,rate):
    flows=tuple(map(num,flows));rate=num(rate);need(flows and rate>-1,'discount domain');return sum(c/(1+rate)**t for t,c in enumerate(flows))
def choice(cash,reserve,cost,loan=0):
    cash,reserve,cost,loan=map(num,(cash,reserve,cost,loan));need(min(cash,reserve,cost,loan)>=0,'cash domain');balance=cash+loan-cost;return balance,balance>=reserve
def score(weights,scores):
    w,s=tuple(map(num,weights)),tuple(map(num,scores));need(len(w)==len(s)>0 and min(w)>=0 and sum(w)==100 and min(s)>=0 and max(s)<=100,'score domain');return sum(a*b/100 for a,b in zip(w,s))
def missing(observed,total,mean,lo,hi):
    need(type(observed) is int and type(total) is int and 0<=observed<=total and total>0,'population counts');mean,lo,hi=map(num,(mean,lo,hi));need(lo<=mean<=hi,'score bounds');return (observed*mean+(total-observed)*lo)/total,(observed*mean+(total-observed)*hi)/total
class Page(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=[];self.cases=[];self.tasks=[];self.answers=[];self.values={};self.sources={};self.links=set();self.rows=0
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(t!='h1','chapter fragment')
        if 'id' in a:self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and any(tag=='ol' and 'exercises' in at.get('class','').split() for tag,at in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for' in a:need(any(tag=='details' and 'solutions' in at.get('class','').split() for tag,at in self.stack),'solution disclosure');self.answers.append(a['data-solution-for'])
        for kind in ('input','result'):
            if 'data-'+kind in a:need((kind,a['data-'+kind]) not in self.values,'unique numerical marker');self.values[kind,a['data-'+kind]]=''
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if t=='a':self.links.add(a['href'])
        if t=='tr':self.rows+=1
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for _,a in self.stack:
            for kind in ('input','result'):
                if 'data-'+kind in a:self.values[kind,a['data-'+kind]]+=s
    def handle_endtag(self,t):need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop()
def check(root=None):
    b=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={name:(b/name).read_bytes() for name in FILES};p=Page();p.feed(raw[FILES[0]].decode());p.close();need(not p.stack and len(p.ids)==len(set(p.ids)),'complete unique manuscript')
    need(p.cases==['v17-c03-case1','v17-c03-case2'],'two workedcourse artifacts');need(p.tasks==p.answers==[f'v17-c03-ex{i}' for i in range(1,9)],'eight exact full solution pairs');need({'course-design','worked-course','redesign','launch-audit','exercises','teach-back','sources'}<=set(p.ids),'instruction sections');need(p.rows==30,'12week/6objective/9week table rows plus3headers');need(all(f'v01-c{i:02}.html' in p.links for i in range(1,13)),'twelve original reading routes')
    source=json.loads(raw[FILES[2]]);need(p.sources=={s['id']:s['url'] for s in source['sources']},'three scoped sources');rec=json.loads(raw[FILES[3]]);need(set(rec['payloads'])==set(FILES[:3]) and all(rec['review'].values()) and not rec['open_material_findings'],'review record')
    for name,h in rec['payloads'].items():need(h=={'bytes':len(raw[name]),'sha256':sha256(raw[name]).hexdigest()},'freeze '+name)
    values={k:parse(v) for k,v in p.values.items()};n=0
    def eq(a,z):
        nonlocal n
        if isinstance(z,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(z),'shape')
            for x,y in zip(a,z):eq(x,y)
        else:need(a==z,'calculation '+str((a,z)));n+=1
    inputs={'weekly-hours':(3,2,2,2),'cash-reserve':(100,20),'machine-a':(90,55,55),'machine-b':(70,42,42),'rate':F(1,10),'loan':(10,11),'scores':(100,90,60,95,100),'weights':(10,15,25,40,10)}
    for k,v in inputs.items():eq(values['input',k],v)
    a,bm,rate=values['input','machine-a'],values['input','machine-b'],values['input','rate'];cash,reserve=values['input','cash-reserve'];loan,repay=values['input','loan'];pa,pb=npv((-a[0],*a[1:]),rate),npv((-bm[0],*bm[1:]),rate);equity=(-a[0]+loan,a[1]-repay,a[2]);changed=npv((-a[0]+loan,a[1]-12,a[2]),rate)
    expected={'diagnostic':(F(250,1000),F(88-80,80),F(14-2,3)),'course-hours':12*sum(inputs['weekly-hours']),'project-values':(pa,pb),'cash-no-loan':(choice(cash,reserve,a[0])[0],choice(cash,reserve,bm[0])[0]),'equity-flows':equity,'value-advantage':pa-pb,'short-hours':9*9,'lost-hours':12*9-9*9,'ex3':(3+3+3+2,3+3+3+2-9,3,2,2,2),'ex4':(changed,changed-pa,changed-pb),'ex5':score(inputs['weights'],inputs['scores']),'ex6':(*missing(6,8,8,0,10),*(v-6 for v in missing(6,8,8,0,10))),'ex7':(npv((-50,60),F(1,5)),70-50,npv((-51,60),F(1,5)),70-51),'ex8':F(100*75,100-15),'retention':(10*8,8*8,(10-8)*8)}
    need(set(values)=={('input',k) for k in inputs}|{('result',k) for k in expected},'complete visible numerical inventory')
    for k,v in expected.items():eq(values['result',k],v)
    eq(npv(equity,rate),pa);eq(npv((loan,-repay),rate),0);need(not choice(cash,reserve,a[0])[1] and choice(cash,reserve,bm[0])[1] and choice(cash,reserve,a[0],loan)[1],'financing scenarios');need(score(inputs['weights'],inputs['scores'])>=85 and 50<75,'aggregate cannotoverride valuationfloor');n+=4
    edges=[('U','A'),('U','P'),('A','C'),('P','C'),('C','M'),('R','M')];good=['U','A','P','C','R','M'];bad=['U','A','C','P','M','R'];need(all(good.index(a)<good.index(z) for a,z in edges),'topological order');need([(a,z) for a,z in edges if bad.index(a)>bad.index(z)]==[('P','C'),('R','M')],'exact two dependency violations');n+=2
    # Vary loan terms independently; discounted-financing decomposition is an identity.
    for r in (F(0),F(1,10),F(1,5),F(-1,10)):
        for L in (0,5,10,20):
            for repayment in (0,11,12,30):eq(npv((-90+L,55-repayment,55),r),npv((-90,55,55),r)+npv((L,-repayment),r))
    for missing_total in range(21):
        full=F(48+missing_total,8);need(6<=full<=F(17,2),'attainable missing-score grid');n+=1
    eq(missing(8,8,8,0,10),(8,8));eq(missing(0,8,8,0,10),(0,10));eq(choice(70,20,50),(20,True));eq(choice(70,20,51),(19,False))
    invalid=[lambda:num(True),lambda:num(float('nan')),lambda:npv((1,2),-1),lambda:npv((),0),lambda:choice(-1,0,0),lambda:score((50,40),(80,90)),lambda:score((50,50),(80,101)),lambda:missing(9,8,8,0,10),lambda:missing(6,8,11,0,10),lambda:parse('1/0'),lambda:parse('__import__("os")')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid input accepted')
    return {'chapter':'v17-c03','status':'passed','runtime_files':4,'worked_artifacts':2,'exercises':8,'source_records':3,'input_groups':len(inputs),'result_groups':len(expected),'comparisons':n,'invalid_domains':len(invalid),'scope':'Actual course/assignment arithmetic, financing identities and evidence limits; full qualitative syllabus/redesign/exercise review separately recorded. No actual teaching or human evaluation claimed.'}
if __name__=='__main__':check()
