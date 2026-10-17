"""C06 exact author oracle: actual vote ledgers, raw research rows and dated supplier costs."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import ast
import json
FILES=('content/chapters/v18-c06.html','scripts/check_v18_c06.py','content/reviews/v18-c06-sources.json','content/reviews/v18-c06-author.json')
def require(ok,message):
    if not ok: raise ValueError(message)


def numeric(text):
    text=text.rsplit('=',1)[-1].strip().replace('−','-')
    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return F(str(node.value))
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('restricted rational syntax')
    return walk(ast.parse(text,mode='eval').body)


class BaseManuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.inputs={};self.results={};self.prompts={};self.solutions={};self.sources={};self.worked=[];self.rows=[];self.row=None;self.cell=None;self.links=set();self.guides=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':raise ValueError('chapter fragment cannot contain h1')
        for attr,dest in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:require(a[attr] not in dest,'duplicate marker');dest[a[attr]]=''
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in x.get('class','').split() for t,x in self.stack):self.prompts[a['id']]=''
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack),'solution disclosure')
            require(a['data-solution-for'] not in self.solutions,'unique solution');self.solutions[a['data-solution-for']]=''
        if 'data-source' in a:require(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if tag=='a':self.links.add(a['href'])
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.cell is not None:self.cell+=text
        for tag,a in self.stack:
            if 'data-input' in a:self.inputs[a['data-input']]+=text
            if 'data-result' in a:self.results[a['data-result']]+=text
            if tag=='li' and a.get('id') in self.prompts:self.prompts[a['id']]+=text
            if 'data-solution-for' in a:self.solutions[a['data-solution-for']]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting')
        if tag in ('td','th'):self.row.append(self.cell);self.cell=None
        if tag=='tr':self.rows.append(self.row);self.row=None
        self.stack.pop()


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(v):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)



def vote(eligible,present,yes,quorum):
    require(all(type(v) is int for v in (eligible,present,yes,quorum)) and eligible>0 and quorum>0 and 0<=yes<=present<=eligible,'valid declared committee counts')
    needed=eligible//2+1
    return needed,present>=quorum and yes>=needed


def pv_cost(price,maintenance,rate=F(1,10),extra1=0):
    price,maintenance,rate,extra1=map(F,(price,maintenance,rate,extra1))
    require(price>=0 and maintenance>=0 and extra1>=0 and rate>-1,'nonnegative dated supplier costs')
    return price+maintenance/(1+rate)+maintenance/(1+rate)**2+extra1/(1+rate)


def contrast(t,c,drop=()):
    require(len(t)>0 and len(c)>0 and all(type(v) is int and v in (0,1) for v in (*t,*c)),'complete binary research rows')
    require(len(set(drop))==len(drop) and all(type(i) is int and 0<=i<len(t) for i in drop),'valid unique omitted row positions')
    retained=[v for i,v in enumerate(t) if i not in drop];require(retained,'nonempty retained group')
    mt=F(sum(retained),len(retained));mc=F(sum(c),len(c))
    return mt,mc,mt-mc


def budget(cash,committed,reserve,price,cap):
    cash,committed,reserve,price,cap=map(F,(cash,committed,reserve,price,cap))
    require(min(cash,committed,reserve,price,cap)>=0,'nonnegative restricted budget')
    return cash-committed-price,price<=cap and cash-committed-price>=reserve


def audit(d):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    inp={k:numeric(v) for k,v in d.inputs.items()}
    eq(inp,{'academic-budget':(120,90,10,20,12),'study':((1,1,1,0,0,0),(1,1,0,0,0,0)),'vendors':((40,6),(46,2))},'visible primitives')
    t,c=tuple(map(int,inp['study'][0])),tuple(map(int,inp['study'][1]))
    full=contrast(t,c);filtered=contrast(t,c,(3,4,5));one=contrast(t,c,(3,))
    related,independent=inp['vendors'];pr=pv_cost(*related);pn=pv_cost(*independent);revised=pv_cost(39,6);threshold=pn-pv_cost(0,6)
    arows=[r for r in d.rows if len(r)==4 and r[0] in 'ABCDEFG' and r[2] in ('Discloses, leaves','Present')]
    frows=[r for r in d.rows if len(r)==4 and r[0] in 'ABCDEFG' and r[1] in ('Owner; recused','Contingent fee; recused','Material employment relationship; recused','Disinterested; present')]
    eq(tuple(r[0] for r in arows),tuple('ABCDEFG'),'all seven academic records')
    eq(tuple(r[0] for r in frows),tuple('ABCDEFG'),'all seven financial records')
    eligible=[r for r in arows if r[2]=='Present'];ay=sum(r[3]=='Yes' for r in eligible)
    fe=[r for r in frows if r[1]=='Disinterested; present'];fy=sum(r[2]=='Yes' for r in fe);ly=sum(r[3]=='Yes' for r in fe)
    want={'academic-vote':(len(arows),len(arows)-len(eligible),len(eligible),len(eligible),ay,vote(len(eligible),len(eligible),ay,4)[0]),'academic-budget-result':(120-90-10,budget(120,90,10,20,20)[0],budget(120,90,10,12,20)[0],20-12),'study-summary':(*full,filtered[0],filtered[2],filtered[2]-full[2]),'financial-votes':(len(fe),len(fe),4,vote(len(fe),len(fe),fy,4)[0],fy,ly),'vendor-costs':(pr,pn,pr-pn,60-related[0],60-independent[0]),'revised-vendor':(revised,pn-revised,threshold,60-39),'e1':(5,vote(5,4,3,4)[0],4,3,3,3),'e2':(120-90-23,10-(120-90-23),23-20),'e3':(one[0],one[2],one[2]-full[2]),'e5':(vote(4,4,2,4)[0],fy,ly,3),'e6':(threshold,pv_cost(39,6,extra1=1),pv_cost(39,6,extra1=1)-pn),'e7':(3,vote(3,3,2,4)[0],3,4),'retention':(2,vote(5,4,2,4)[0],pv_cost(38,6,extra1=1),pn-pv_cost(38,6,extra1=1),60-38)}
    eq(set(want),set(d.results),'all numeric result groups')
    for k,v in want.items():eq(numeric(d.results[k]),v,'displayed '+k)
    eq(vote(len(eligible),len(eligible),ay,4),(3,True),'academic actual ledger approval')
    eq(vote(len(fe),len(fe),fy,4),(3,False),'financial actual initial ledger failure')
    eq(vote(len(fe),len(fe),ly,4),(3,True),'financial actual later ledger approval')
    eq(tuple(r[3] for r in eligible),('Yes','Yes','Yes','No','Abstain'),'abstention preserved')
    eq(tuple(r[2] for r in fe),('Yes','Yes','No','Abstain'),'initial financial denominator not votes cast')
    eq(budget(120,90,10,20,20),(10,True),'independent price fits both constraints')
    eq(budget(120,90,10,23,20),(7,False),'higher price fails both')
    eq(budget(120,90,10,12,20),(18,True),'cheap offer passes money only; qualitative independence gate separate')
    eq((3+17,20-12),(20,8),'complete independent scope allocation')
    worlds=0
    for n,q in ((5,4),(4,4),(3,4)):
        for present in range(n+1):
            for yes in range(present+1):
                needed,passed=vote(n,present,yes,q);worlds+=1
                eq(passed,present>=q and 2*yes>n,'majority inequality and quorum independently')
                eq(needed,n//2+1,'integer smallest majority')
    eq((vote(5,4,3,4)[1],vote(5,3,3,4)[1],vote(4,3,3,4)[1]),(True,False,False),'absence alternatives')
    eq(vote(3,3,3,4)[1],False,'even unanimous remaining eligible cannot satisfy quorum')
    deletion_worlds=0
    for mask in range(8):
        drop=tuple(i+3 for i in range(3) if mask>>i&1);got=contrast(t,c,drop);deletion_worlds+=1
        eq(got,(F(3,6-len(drop)),F(1,3),F(3,6-len(drop))-F(1,3)),'all failed-row omission sets')
    eq(contrast(t,c,(0,)),(F(2,5),F(1,3),F(1,15)),'omitting a success can lower contrast')
    eq(contrast(t,c,(0,1,2)),(0,F(1,3),F(-1,3)),'opposite selection changes sign')
    eq(contrast((1,),(0,)),(1,0,1),'binary endpoint')
    eq(contrast((0,),(1,)),(0,1,-1),'binary reverse endpoint')
    factor=sum((F(1)/(1+F(1,10))**year for year in (1,2)),F(0))
    eq(factor,F(210,121),'dated discount sum')
    for price in (F(0),F(38),F(39),threshold,F(40),F(50),F(51)):
        total=pv_cost(price,6)
        eq(total-pn,price-threshold,'affine global comparison identity')
        eq(total<=pn,price<=threshold,'cost threshold equivalence')
        eq(60-price>=10,price<=50,'cash feasibility threshold')
        eq(total<=pn and 60-price>=10,0<=price<=min(50,threshold),'intersection of constraints')
    eq(pv_cost(39,6,extra1=1)-pv_cost(39,6),F(10,11),'hidden first-year payment exact PV')
    eq(pv_cost(39,6,rate=0),51,'zero discount alternative')
    eq(pv_cost(46,2,rate=0),50,'undiscounted vendor comparison')
    eq(pv_cost(39,6,rate=F(1,2)),F(137,3),'higher discount alternative')
    invalid=[lambda:vote(0,0,0,1),lambda:vote(4,5,1,4),lambda:vote(4,4,5,4),lambda:vote(4,4,2,0),lambda:vote(4.0,4,2,4),lambda:contrast((),(1,)),lambda:contrast((2,),(1,)),lambda:contrast((1,),(0,),(0,)),lambda:contrast((1,0),(1,),(1,1)),lambda:contrast((1,),(0,),(2,)),lambda:pv_cost(-1,2),lambda:pv_cost(1,2,-1),lambda:budget(120,90,-1,20,20)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want),worlds,deletion_worlds


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself hashes')
    for f,v in review['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'changed frozen file '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and len(d.ids)==len(set(d.ids)),'balanced unique fragment')
    ids={f'v18-c06-e{i}' for i in range(1,9)}
    require(set(d.prompts)==set(d.solutions)==set(review['exact_prompt_review'])==ids,'eight exact exercise/answer pairs')
    require(d.worked==['v18-c06-case1','v18-c06-case2'],'two complete governance cases')
    for k,v in review['exact_prompt_review'].items():require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed pair changed')
    urls={'v18-c06-ma-duty':'https://malegislature.gov/Laws/GeneralLaws/PartI/TitleXXII/Chapter180/Section6C','v18-c06-delaware-board':'https://delcode.delaware.gov/title8/c001/sc04/index.html','v18-c06-phs-integrity':'https://www.ecfr.gov/current/title-42/chapter-I/subchapter-H/part-93','v18-c06-harvard-freedom':'https://officeofthesecretary.fas.harvard.edu/sites/g/files/omnuum2291/files/2024-11/Free_Speech_Guidelines%20(3).pdf'}
    require(d.sources==urls=={s['id']:s['url'] for s in sources['sources']},'fresh exact source routes')
    require(all(s['actual_inspector']=='v15_support_review' and s['checked']=='2026-10-17' for s in sources['sources']),'actual inspector/date')
    require({a for a in d.links if not a.startswith('https://')}=={'curriculum.html#v18-c05','v18-c02.html','v16-c07.html','v17-c09.html','curriculum.html#v18-c07'},'prerequisite and continuation routes')
    comparisons,invalid,groups,worlds,deletions=audit(d)
    return {'chapter':'v18-c06','status':'passed','runtime_files':4,'worked_cases':2,'prompts':8,'solutions':8,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'vote_worlds':worlds,'deletion_worlds':deletions,'source_routes':4,'scope':'Full jurisdiction/authority/conflict/disclosure records, actual voting tables, resource alternatives, integrity/freedom handoff and exact solutions read; numeric checks cannot establish legal compliance or culpability.'}


if __name__=='__main__':
    check()
