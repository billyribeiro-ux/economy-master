"""Quiet four-file author check of the actual displayed construction and results."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from html.parser import HTMLParser
import ast, contextlib, io, json, subprocess, sys
FILES=('content/chapters/v16-c07.html','scripts/check_v16_c07.py','content/reviews/v16-c07-sources.json','content/reviews/v16-c07-author.json')
def require(ok,message):
    if not ok:raise ValueError(message)
def numeric(text):
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('numeric literal required')
    return visit(ast.parse(text,mode='eval').body)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.capture=[];self.ids=[];self.inputs={};self.results={};self.code={};self.tables=[];self.row=None;self.cell=None;self.prompts=[];self.answers=[];self.worked=[];self.sources={};self.guides=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);require(len(a)==len(attrs),'attributes unique');require(tag!='h1','fragment')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'solutions enclosure');self.answers.append(a['data-solution-for'])
        if tag=='details' and 'solutions' in a.get('class','').split():self.guides+=1
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:
                k=a[attr];require(k not in d,'unique marker');d[k]='';self.capture.append((d,k,len(self.stack)))
        if tag=='code' and a.get('id') in ('v16-c07-program','v16-c07-output'):
            k=a['id'];self.code[k]='';self.capture.append((self.code,k,len(self.stack)))
        if tag=='table':self.tables.append([])
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.row.append('');self.capture.append((self.row,len(self.row)-1,len(self.stack)))
        if tag not in ('br','hr','img','input','link','meta'):self.stack.append((tag,a))
    def handle_data(self,text):
        for d,k,_ in self.capture:d[k]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML balance');self.stack.pop();self.capture=[x for x in self.capture if x[2]<len(self.stack)]
        if tag=='tr':self.tables[-1].append(self.row);self.row=None

def bounds(total,observed,positive):
    require(all(type(x) is int for x in (total,observed,positive)) and 0<=positive<=observed<=total and total>0,'binary count domain')
    return F(positive,total),F(positive+total-observed,total)

def oracle(rows,links,coverage,roster):
    mapping={(l,a):b for l,a,b in links};unique={};copies=0
    for loan,t,l,a,u,amount in rows:
        key=(l,loan,t);row=(loan,t,l,a,u,amount)
        if key in unique:require(unique[key]==row,'oracle conflict');copies+=1
        else:unique[key]=row
    totals={k:0 for k in coverage}
    for loan,t,l,a,u,amount in unique.values():
        if amount is not None:totals[mapping[l,a],t]+=amount*(1000 if u=='thousand' else 1)
    return {'baseline':list(roster),'duplicates_removed':copies,'panel':[[b,t,str(F(totals[b,t],1000)) if coverage[b,t] else None,'complete' if coverage[b,t] else 'missing'] for b,t in sorted(coverage)],'unique_loan_dates':len(unique)}

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=json.loads(raw[FILES[3]])
    bindings=review['payload_bindings'];require(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three hashes')
    for b in bindings:require((len(raw[b['path']]),sha256(raw[b['path']]).hexdigest())==(b['bytes'],b['sha256']),'freeze')
    page=Page();page.feed(raw[FILES[0]].decode());require(not page.stack and len(page.ids)==len(set(page.ids)),'complete unique HTML')
    ex=[f'v16-c07-e{i}' for i in range(1,9)];require(page.prompts==page.answers==ex and set(review['exact_prompt_review'])==set(ex),'eight exact solutions')
    require(page.worked==['v16-c07-case1','v16-c07-case2'] and page.guides==3,'cases and guides')
    sources=json.loads(raw[FILES[2]])['sources'];require(page.sources=={s['id']:s['url'] for s in sources},'source routes')
    code=page.code['v16-c07-program'];run=subprocess.run([sys.executable,'-I','-B','-O','-c',code],cwd='/',capture_output=True,text=True,timeout=20)
    require(run.returncode==0 and run.stderr=='' and run.stdout==page.code['v16-c07-output']+'\n','actual exact inline transcript')
    ns={'__name__':'reader'};out=io.StringIO();err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):exec(compile(code,'<reader>','exec'),ns)
    require(out.getvalue()==err.getvalue()=='','quiet reader import')
    rows=ns['RAW'];links=ns['LINKS'];cov=ns['COVERAGE'];roster=ns['ROSTER'];fn=ns['construct']
    expectedrows=(('L1',0,'N','n1','thousand',100),('L2',0,'S','s7','currency',40000),('L3',0,'N','n2','thousand',80),('L1',1,'N','n1','thousand',90),('L2',1,'S','s7','currency',60000),('L4',1,'S','s9','thousand',20),('L1',1,'N','n1','thousand',90),('L3',1,'N','n2','thousand',None))
    require(rows==expectedrows,'actual program inputs')
    require(page.tables[0][1:]==[[str(v) for v in row] for row in rows],'visible raw table equals actual program')
    require(links==( ('N','n1','B1'),('S','s7','B1'),('N','n2','B2'),('S','s9','B3')) and roster==('B1','B2'),'mapping and target')
    require(cov=={(b,t):not(b=='B2' and t==1) for b in ('B1','B2','B3') for t in (0,1)},'coverage primitive')
    want=oracle(rows,links,cov,roster);require(json.loads(run.stdout)==want,'independent common-currency oracle')
    require(page.tables[1][1:]==[['B1','140','150','Baseline; both complete.'],['B2','80','Unknown','Baseline; date-1 coverage incomplete.'],['B3','0','20','Outside baseline roster; both complete.']],'completed analysis table')
    inp={k:numeric(v) for k,v in page.inputs.items()};shown={k:numeric(v) for k,v in page.results.items()};require(inp=={'survey-counts':(100,60,48,18)},'survey primitive')
    eligible,consent,respond,positive=map(int,inp['survey-counts']);require(0<respond<=consent<=eligible,'nested denominators')
    expected={'ingestion':(len(rows),want['unique_loan_dates'],want['duplicates_removed'],len(want['panel']),sum(x[3]=='complete' for x in want['panel']),sum(x[3]=='missing' for x in want['panel'])),'b1-growth':F(150-140,140),'baseline-total':220,'response-rate':F(respond,consent),'observed-rate':F(positive,respond),'consenter-bounds':bounds(consent,respond,positive),'eligible-bounds':bounds(eligible,respond,positive),'e2-retransmission':(150+90,F(150+90-140,140)),'e2-crosswalk':(2*100+40,2*90+60,F(0)),'e3-bounds':(F(150-220,220),F(150+160-220,220)),'e4-growth':F(150-220,220),'e5-response':F(50,consent),'e5-observed':F(19,50),'e5-consenter':bounds(consent,50,19),'e5-eligible':bounds(eligible,50,19)}
    require(set(expected)==set(shown),'all displayed numeric results')
    comparisons=0
    def equal(a,b,label):
        nonlocal comparisons
        if isinstance(b,dict):
            require(set(a)==set(b),label+' keys')
            for k in b:equal(a[k],b[k],label)
        elif isinstance(b,(tuple,list)):
            require(isinstance(a,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):equal(x,y,label)
        else:comparisons+=1;require(a==b,label)
    for k,v in expected.items():equal(shown[k],v,'result '+k)
    for data in (rows,tuple(reversed(rows)),rows[:6]+rows[7:],rows+(rows[0],)):
        equal(fn(data,links,cov,roster),oracle(data,links,cov,roster),'construction oracle')
    for amount in (0,80000,100000,160000):
        data=rows[:-1]+(('L3',1,'N','n2','currency',amount),);complete=dict(cov);complete['B2',1]=True
        equal(fn(data,links,complete,roster),oracle(data,links,complete,roster),'documented coverage revision')
        equal(fn(data,links,cov,roster)['panel'][3][2],None,'incomplete remains missing')
    for n,r,s in ((60,48,18),(100,48,18),(60,50,19),(100,50,19),(3,0,0),(5,5,2)):
        low,high=bounds(n,r,s);rates=[F(s+k,n) for k in range(n-r+1)];equal(min(rates),low,'sharp minimum');equal(max(rates),high,'sharp maximum')
    invalid=[lambda:fn(rows,links+(links[0],),cov,roster),lambda:fn(rows,links+(('N','n1','B3'),),cov,roster),lambda:fn(rows+(('L1',0,'N','n1','thousand',101),),links,cov,roster),lambda:fn((('L5',0,'N','unknown','thousand',1),),links,cov,roster),lambda:fn((('L5',2,'N','n1','thousand',1),),links,cov,roster),lambda:fn((('L5',0,'N','n1','thousand',True),),links,cov,roster),lambda:fn((('L5',0,'N','n1','thousand',-1),),links,cov,roster),lambda:fn((('L5',0,'N','n1','thousand',None),),links,cov,roster),lambda:fn(rows,links,{},roster),lambda:fn(rows,links,cov,('B1','B1')),lambda:bounds(0,0,0),lambda:bounds(10,11,1),lambda:bounds(10,5,6),lambda:bounds(True,0,0)]
    for f in invalid:
        try:f()
        except ValueError:pass
        else:raise ValueError('invalid contract accepted')
    for path,data in raw.items():require((root/path).read_bytes()==data,'unchanged runtime files')
    return {'chapter':'v16-c07','status':'passed','worked_cases':2,'solutions':8,'comparisons':comparisons,'result_groups':len(shown),'invalid_domains':len(invalid),'inline_code_executed':True,'exact_transcript_matched':True,'runtime_files':4}
if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
