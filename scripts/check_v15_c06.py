"""Political economy: complete finite-account and incentive checks, four payloads."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from hashlib import sha256
from math import log,sqrt,isfinite
import ast,json
FILES=('content/chapters/v15-c06.html','scripts/check_v15_c06.py','content/reviews/v15-c06-sources.json','content/reviews/v15-c06-author.json')
def need(x,m):
    if not x:raise ValueError(m)
def num(x):
    need(type(x)in(int,float,F)and isfinite(float(x)),'finite nonboolean');return F(str(x))
def election(alpha,k=F(1,10)):
    alpha,k=map(num,(alpha,k));need(F(1,2)<alpha<=1 and k>=0,'election domain');qh=1-alpha+(2*alpha-1)*F(4,5);ql=1-alpha+(2*alpha-1)*F(2,5);margin=F(3,4)*(qh-ql)-k;high=F(3,4)if margin>=0 else F(1,4);good=high*qh+(1-high)*ql;postg=qh/(4*good);postb=(1-qh)/(4*(1-good));nextgood=F(2,5)+F(2,5)*postg;final=good*nextgood+(1-good)*F(1,2)
    return qh,ql,good,postg,postb,margin,high*F(4,5)+(1-high)*F(2,5),nextgood,final

def lobby(B,loss,e):
    B,loss,e=map(num,(B,loss,e));need(B>0 and loss>=0 and e>=0,'influence domain');l=max(sqrt(float(B*(1+e)))-float(1+e),0);p=l/(float(1+e)+l);private=float(B)*p-l;welfare=float(B-loss)*p-l-float(e);return l,p,private,welfare

def capacity(B,c):
    B,c=map(num,(B,c));need(B>0 and c>0,'capacity positive');k=max(sqrt(float(B/(4*c)))-1,0);rho=k/(1+k);T=float(B)*rho/4;return k,float(c)*k,rho,T,T-float(c)*k

class Read(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.cases=[];self.prompts=[];self.solutions=[];self.markers={};self.stack=[];self.sources={}
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if 'worked'in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and any(tag=='ol' and 'exercises'in d.get('class','').split() for tag,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for'in a:
            need(any(tag=='details' and 'solutions'in d.get('class','').split() for tag,d in self.stack),'disclosed solution');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        for k in ('data-input','data-result'):
            if k in a:need(a[k] not in self.markers,'duplicate marker');self.markers[a[k]]=''
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_endtag(self,t):need(bool(self.stack) and self.stack.pop()[0]==t,'balanced HTML')
    def handle_data(self,s):
        for _,a in self.stack:
            for k in ('data-input','data-result'):
                if k in a:self.markers[a[k]]+=s

def parse(s):
    s=s.split('=')[-1].strip()
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x)for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value)in(int,float):return num(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('numeric display syntax')
    return walk(ast.parse(s,mode='eval').body)

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];p=Read();p.feed((root/FILES[0]).read_text());p.close();need(not p.stack and len(p.ids)==len(set(p.ids)),'HTML/IDs');need(len(p.cases)==5 and len(p.prompts)==10 and p.prompts==p.solutions,'complete5cases10solutions');s=json.loads((root/FILES[2]).read_text());need(p.sources=={x['id']:x['url']for x in s['sources']},'source URLs');r=json.loads((root/FILES[3]).read_text());need({x['path']for x in r['payload_bindings']}==set(FILES[:3]),'three nonself bindings')
    for x in r['payload_bindings']:
        f=root/x['path'];need(f.stat().st_size==x['bytes']and sha256(f.read_bytes()).hexdigest()==x['sha256'],'freeze')
    n=0
    def eq(a,b):
        nonlocal n
        if isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list))and len(a)==len(b),'shape')
            for x,y in zip(a,b):eq(x,y)
        else:n+=1;need(abs(float(a)-float(b))<2e-10*max(1,abs(float(b))),'numeric '+str((a,b)))
    inputs={'voting':(1,2,4),'agency':(F(4,5),F(2,5),F(3,4),1,F(1,10),F(3,4)),'lobby':(9,12),'capacity':(100,1,1)}
    for k,v in inputs.items():eq(parse(p.markers[k]),v)
    high=election(F(3,4));low=election(F(3,5));out={'voting-choice':(3*sorted(inputs['voting'])[1]-1,sum(inputs['voting'])-1),'agency-high':high[:6],'lobby-base':lobby(9,12,0),'bureaucracy':(1,0,F(1,2),1,2,F(5,2),5-F(5,2)-F(2,5)),'capacity-result':(capacity(100,1)[0],F(1,2),*capacity(100,1)[2:]),'e1':(2,5,20,5,9),'e3':election(F(2,3))[:6],'e4':(high[7],high[8],low[7],low[8]),'e5':(*lobby(9,12,3),8,-8),'e7':(F(1,2),F(1,2),F(1,4),F(1,8),F(1,4),F(3,8)),'e8':(5-F(5,2)-3,F(1,2)),'e9':capacity(100,4)}
    for k,v in out.items():eq(parse(p.markers[k]),v)
    need(set(p.markers)==set(inputs)|set(out),'all displayed markers checked')
    # Median choices against all enumerated alternatives supplement the universal proof.
    for tastes in((1,2,4),(1,2,7)):
        peaks=[3*a-1 for a in tastes];med=sorted(peaks)[1];opt=sum(tastes)-1
        for g in range(31):
            wins=sum(-med/3+a*log(1+med)>-g/3+a*log(1+g)+1e-12 for a in tastes);need(g==med or wins>=2,'majority witness');need(-opt+sum(tastes)*log(1+opt)>=-g+sum(tastes)*log(1+g)-1e-12,'welfare optimum witness');n+=2
    for alpha in(F(3,5),F(2,3),F(3,4),F(1)):
        qh,ql,g,postg,postb,margin,current,ng,final=election(alpha);eq(g*postg+(1-g)*postb,F(1,4));need(postg>F(1,4)>postb,'credible election');n+=1
        h=F(3,4)if margin>=0 else F(1,4);eq(current,h*F(4,5)+(1-h)*F(2,5));eq(final,F(1,2)+F(1,10)*(qh-g))
    eq(low[5],F(-1,25));eq((high[6],low[6]),(F(7,10),F(1,2)));eq(lobby(9,12,1)[3],-2-2*sqrt(2))
    for B,e in((9,0),(9,1),(9,3),(9,8),(F(1,4),0)):
        l,prob,private,welfare=lobby(B,12,e);eq(welfare,private-12*prob-e)
        for candidate in(0,.5,1,2,4,8,l+.1,max(0,l-.1)):
            need(private>=float(B)*candidate/(1+float(e)+candidate)-candidate-1e-12,'global lobby witness');n+=1
    # Salary expectations, global effort comparison and all-state reserves.
    for bcoef,dcoef,A,expected in((1,0,F(-1,2),F(1,2)),(1,2,F(-5,2),F(5,2)),(F(1,2),0,0,F(1,4))):
        chosen=(bcoef,dcoef);mean=A+bcoef*bcoef+dcoef*dcoef;eq(mean,expected);utility=mean-(bcoef*bcoef+dcoef*dcoef)/2
        for q in(0,F(1,2),1,2,3):
            for e in(0,1,2,3):need(utility>=A+bcoef*q+dcoef*e-(q*q+e*e)/2,'global effort witness');n+=1
    wages=[F(-5,2)+q+2*(e+noise)for q in(0,3)for e in(0,3)for noise in(-1,1)];eq((min(wages),max(wages)),(F(-9,2),F(17,2)));need(min(wages)+10>=0 and max(wages)+F(2,5)<=20,'salary resources');n+=1;eq(sum(F(-5,2)+1+2*(2+noise)for noise in(-1,1))/2,F(5,2))
    for B,c in((100,1),(100,4),(4,1),(1,1),(36,1)):
        k,bill,rho,T,G=capacity(B,c);eq(T,bill+G);need(G>=-1e-12,'repayable optimum');n+=1
        for trial in(0,1,2,4,8,k+.1,max(0,k-.1)):
            for tax in(F(0),F(1,4),F(1,2),F(3,4),F(1)):
                objective=float(B)*trial/(1+trial)*float(tax*(1-tax))-float(c)*trial;need(G>=objective-1e-10,'global capacity witness');n+=1
    invalid=[lambda:num(True),lambda:num(float('nan')),lambda:num(float('inf')),lambda:election(F(1,2)),lambda:election(0),lambda:election(F(11,10)),lambda:election(F(3,4),-1),lambda:lobby(0,12,0),lambda:lobby(9,-1,0),lambda:lobby(9,12,-1),lambda:capacity(0,1),lambda:capacity(100,0),lambda:capacity(-1,1),lambda:capacity(100,-1),lambda:parse('bool(1)')]
    for fn in invalid:
        try:fn()
        except(ValueError,ZeroDivisionError):pass
        else:raise ValueError('malformed accepted')
    result={'chapter':'v15-c06','status':'passed','comparisons':n,'domain_rejections':len(invalid),'worked_cases':5,'solved_exercises':10,'primitive_markers':len(inputs),'result_markers':len(out),'runtime_files':4,'scope':'Full finite budgets, posterior/election incentives, global choice and salary/capacity witnesses; universal proofs reviewed separately.'};json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()
