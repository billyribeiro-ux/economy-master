"""V16 support: visible arithmetic and exact five-file author freeze.

Qualitative research judgment and global proof review are recorded separately.
"""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast, json, math

FILES=('content/assessments/parts/v16-support-opening.html','content/assessments/parts/v16-support-closing.html','scripts/check_v16_support.py','content/reviews/v16-support-sources.json','content/reviews/v16-support-author.json')
def need(ok,msg):
    if not ok:raise ValueError('V16 support: '+msg)
def number(x):
    need(type(x) in (int,float,F) and math.isfinite(float(x)),'finite real scalar')
    return F(str(x))
def numeric(s):
    def visit(n):
        if isinstance(n,ast.Constant):return number(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            a,b=visit(n.left),visit(n.right);need(b!=0,'nonzero divisor');return a/b
        raise ValueError('restricted numeric syntax')
    return visit(ast.parse(s.replace('−','-').strip(),mode='eval').body)
def growth(start,end):
    start,end=tuple(map(number,start)),tuple(map(number,end))
    need(bool(start) and len(start)==len(end) and min(start)>0 and min(end)>=0,'stock domain')
    rates=tuple(y/x-1 for x,y in zip(start,end))
    return rates,sum(rates)/len(rates),sum(end)/sum(start)-1
def did(exposed,comparison,m):
    need(len(exposed)==len(comparison)==2,'two periods');a,b,c,d=map(number,(*exposed,*comparison));m=number(m)
    return (b-a)-(d-c),b-m,(m-a)-(d-c)
def posterior(p,a,b):
    p,a,b=map(number,(p,a,b));need(all(0<=x<=1 for x in (p,a,b)),'probabilities');den=p*a+(1-p)*b;need(den>0,'positive event');return den,p*a/den
def bounds(p,mean,lo,hi):
    p,mean,lo,hi=map(number,(p,mean,lo,hi));need(0<=p<=1 and lo<=mean<=hi,'bounded mean domain');return p*mean+(1-p)*lo,p*mean+(1-p)*hi
def mixture(shares,effects):
    shares,effects=tuple(map(number,shares)),tuple(map(number,effects));need(bool(shares) and len(shares)==len(effects) and min(shares)>=0 and sum(shares)==1,'mixture domain');return sum(p*t for p,t in zip(shares,effects))
def planning(sigma,delta,zalpha,zpower):
    sigma,delta,zalpha,zpower=map(number,(sigma,delta,zalpha,zpower));need(min(sigma,delta,zalpha,zpower)>0,'planning domain');n=2*sigma*sigma*(zalpha+zpower)**2/delta**2;k=math.ceil(n);return n,k,2*k
def bias_interval(estimate,se,z,B):
    estimate,se,z,B=map(number,(estimate,se,z,B));need(se>0 and z>0 and B>=0,'interval domain');return estimate-z*se-B,estimate+z*se

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.ids=[];self.tasks={};self.answers=[];self.markers={};self.inputs={};self.sources={};self.links=set();self.headings=0;self.text={}
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attrs')
        if t=='h1':self.headings+=1
        if 'id' in a:self.ids.append(a['id'])
        if 'data-points' in a:self.tasks[a['id']]=int(a['data-points']);self.text[a['id']]=''
        if 'data-solution-for' in a:
            need(any(k=='details' and 'solutions' in x.get('class','').split() for k,x in self.stack),'disclosed answers');self.answers.append(a['data-solution-for']);self.text['answer-'+a['data-solution-for']]=''
        for attr,target in [('data-check',self.markers),('data-input',self.inputs)]:
            if attr in a:need(a[attr] not in target,'unique marker');target[a[attr]]=''
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if t=='a':self.links.add(a.get('href',''))
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for _,a in self.stack:
            if 'data-check' in a:self.markers[a['data-check']]+=s
            if 'data-input' in a:self.inputs[a['data-input']]+=s
            if 'data-points' in a:self.text[a['id']]+=s
            if 'data-solution-for' in a:self.text['answer-'+a['data-solution-for']]+=s
    def handle_endtag(self,t):need(bool(self.stack) and self.stack[-1][0]==t,'balanced nesting');self.stack.pop()

def strict_json(s):
    def reject(x):raise ValueError('nonfinite JSON '+x)
    return json.loads(s,parse_constant=reject)
def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(base/p).read_bytes() for p in FILES};p=Page();p.feed(raw[FILES[0]].decode()+'\n'+raw[FILES[1]].decode());p.close()
    need(not p.stack and len(p.ids)==len(set(p.ids)) and p.headings==1,'unique balanced support')
    tasks={**{f'v16-d{i}':5 for i in range(1,9)},**{f'v16-o{i}':4 for i in range(1,6)},**{f'v16-r{i}':8 for i in range(1,6)}}
    need(p.tasks==tasks and p.answers==list(tasks),'exact18 paired prompts');need(all(len(p.text['answer-'+k].split())>=80 for k in tasks),'substantive answer floor; not proof of correctness')
    need({'diagnostic','exam-rules','oral-transfer','retention','remediation','notation-index','concept-index','volume-synthesis','assessment-source-scope'}<=set(p.ids),'support sections')
    need(all(f'v16-c{i:02}.html' in p.links for i in range(1,13)),'all12chapter routes')
    src=strict_json(raw[FILES[3]]);need(p.sources=={s['id']:s['url'] for s in src['sources']},'source routes')
    rec=strict_json(raw[FILES[4]]);need(set(rec['exact_prompt_audit'])==set(tasks) and all(rec['review'].values()) and not rec['open_material_findings'],'actual author reading record')
    need(set(rec['payloads'])==set(FILES[:4]),'four nonself bindings')
    for name,h in rec['payloads'].items():need(h=={'bytes':len(raw[name]),'sha256':sha256(raw[name]).hexdigest()},'freeze '+name)
    inputs={k:numeric(v) for k,v in p.inputs.items()};outputs={k:numeric(v) for k,v in p.markers.items()};n=0
    def eq(a,b):
        nonlocal n
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and len(a)==len(b),'result width')
            for x,y in zip(a,b):eq(x,y)
        else:need(a==b,'arithmetic '+str((a,b)));n+=1
    fixed={'d1-open':(50,80),'d1-close':(55,72),'d2-exposed':(20,18),'d2-comparison':(30,33),'d3':(F(1,4),F(3,4),F(1,4)),'d5':(F(2,5),F(1,2),F(49,25)),'d6':(F(3,4),4,0,8),'d7':(100,120),'d8':(120,40,30,30,30),'o2':(80,96,88),'o3':(F(1,20),F(3,100),F(1,25)),'o4-source':(F(1,2),F(1,2)),'o4-effects':(1,3),'o4-target':(F(3,4),F(1,4)),'o4-changed':(-1,1),'r2-a':(F(6,5),F(13,10)),'r2-b':(400,440),'r3':(2,1,F(49,25),F(21,25)),'r4':(F(9,10),F(1,5))}
    need(set(inputs)==set(fixed),'input inventory')
    for k,v in fixed.items():eq(inputs[k],v)
    rates,mean,total=growth(inputs['d1-open'],inputs['d1-close']);e,c=inputs['d2-exposed'],inputs['d2-comparison'];m=e[0]+c[1]-c[0];D,tau,b=did(e,c,m);D2,tau2,b2=did(e,c,e[1]);est,se,z=inputs['d5'];start,end=inputs['d7'];hours=inputs['d8'];opening,old,new=inputs['o2'];alpha,p1,p2=inputs['o3'];a0,a1=inputs['r2-a'];b0,b1=(x/1000 for x in inputs['r2-b']);plan=planning(*inputs['r3']);v,sd=inputs['r4']
    expected={'d1':(*rates,mean,total),'d2':(D,m,tau,b,e[1],tau2,b2),'d3':posterior(*inputs['d3']),'d4':(4,5,16,15,1),'d5':(est-z*se,est+z*se),'d6':bounds(*inputs['d6']),'d7':((end-start)/end,(end-start)/start),'d8':(sum(hours[1:]),sum(hours[1:])-hours[0],40,20,30,30),'o2':((old-opening)/opening,(new-opening)/opening,100*(new-old)/opening),'o3':(alpha/2,min(1,2*p1),min(1,2*p2)),'o4':(mixture(inputs['o4-source'],inputs['o4-effects']),mixture(inputs['o4-target'],inputs['o4-effects']),mixture(inputs['o4-target'],inputs['o4-changed'])),'r1':(growth((10,)*4,(11,11,9,9))[1],growth((10,)*4,(11,11,9,9))[2]),'r2':(a0+b0,a1+b1,growth((a0,b0),(a1,b1))[2],growth((a0,b0),(a1,b1))[1]),'r3':(*plan,plan[2]-120),'r4':(*bias_interval(v,sd,F(49,25),F(2,5)),*bias_interval(v,sd,F(49,25),F(3,5))),'r5':(25,20,15,10,10,sum((25,20,15,10,10)))}
    need(set(expected)==set(outputs),'all16 numerical result groups')
    for k,expected_value in expected.items():eq(outputs[k],expected_value)
    # Alternative data and boundary witnesses, not only the displayed cases.
    for s,t in [((10,20),(12,18)),((1,1),(0,0)),((2,3),(8,9)),((1,4),(1,4))]:
        rates,mean,total=growth(s,t);eq(total,sum(F(a,sum(s))*r for a,r in zip(s,rates)));eq(growth(tuple(1000*x for x in s),tuple(1000*x for x in t)),(rates,mean,total))
    for m in range(-5,31):
        D,tau,b=did(e,c,m);eq(D,tau+b)
    for j in range(49):
        q=F(j,4);S=9*q-q*q/2-(q+q*q/2);eq(S,16-(q-4)**2);need(S<=16,'global maximum witness');n+=1
    for j in range(33):
        miss=F(j,4);mean=3+miss/4;need(3<=mean<=5,'missingness witness');eq(4*(mean-3),miss);n+=1
    eq(bounds(1,4,0,8),(4,4));eq(bounds(0,4,0,8),(0,8));eq(posterior(0,F(1,2),F(1,2)),(F(1,2),0));eq(posterior(1,F(1,2),F(1,2)),(F(1,2),1))
    for share in (0,F(1,4),F(1,2),1):eq(mixture((share,1-share),(1,3)),3-2*share)
    eq(planning(2,2,F(49,25),F(21,25))[0],plan[0]/4)
    # The entire permitted-bias union contains each conditional interval.
    for B in (0,F(2,5),F(3,5),2):
        lo,hi=bias_interval(v,sd,F(49,25),B)
        for k in range(11):
            b=F(B)*k/10;left=v-b-F(49,25)*sd;right=v-b+F(49,25)*sd;need(lo<=left<=right<=hi,'union coverage event');n+=1
    invalid=[lambda:number(True),lambda:number(float('nan')),lambda:number(float('inf')),lambda:growth((0,),(1,)),lambda:growth((1,),(-1,)),lambda:growth((),()),lambda:growth((1,2),(1,)),lambda:posterior(2,1,1),lambda:posterior(0,1,0),lambda:bounds(2,4,0,8),lambda:bounds(F(1,2),9,0,8),lambda:mixture((F(1,2),),(1,)),lambda:mixture((1,),(1,2)),lambda:planning(2,0,1,1),lambda:bias_interval(1,0,2,1),lambda:bias_interval(1,1,2,-1),lambda:numeric('__import__("os")'),lambda:numeric('1/0'),lambda:strict_json('{"x":NaN}')]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return {'volume':'v16','component':'support','status':'passed','runtime_files':5,'diagnostic_tasks':8,'oral_tasks':5,'retention_tasks':5,'score_totals':[40,20,40],'input_groups':len(inputs),'result_groups':len(outputs),'comparisons':n,'invalid_domains':len(invalid),'scope':'Visible inputs/outputs, identities, boundary witnesses and structural pairing; full qualitative judgment and analytical proofs separately read.'}
if __name__=='__main__':check()
