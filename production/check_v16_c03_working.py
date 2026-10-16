"""Read-only exact-four-file audit; executes the actual displayed reader code."""
import ast
import contextlib
import io
import json
import subprocess
import sys
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import permutations
from pathlib import Path

FILES=('production/v16-c03-working.html','production/check_v16_c03_working.py',
       'production/v16-c03-sources-working.json','production/v16-c03-author-review-working.json')
def need(ok,message):
    if not ok:raise ValueError(message)
def literal(text):
    def read(n):
        if isinstance(n,ast.Constant):
            need(type(n.value) is int,'integer literals only');return F(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(read(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            return (-1 if isinstance(n.op,ast.USub) else 1)*read(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
            den=read(n.right);need(den!=0,'nonzero denominator');return read(n.left)/den
        raise ValueError('literal numeric expression required')
    return read(ast.parse(text,mode='eval').body)
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.active=[];self.inputs={};self.results={};self.blocks={};self.cells=[]
        self.ids=[];self.cases=[];self.exercises=[];self.solutions=[];self.guides=0;self.sources={};self.links=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attributes');need(tag!='h1','fragment headings')
        if 'id' in a:
            need(a['id'].startswith('v16-c03-') and a['id'] not in self.ids,'unique prefixed IDs');self.ids.append(a['id'])
        if tag=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if tag=='li' and a.get('id','').startswith('v16-c03-e'):
            need(any(t=='ol' and 'exercises' in b.get('class','').split() for t,b in self.stack),'exercise list')
            self.exercises.append(a['id'])
        if tag=='details' and 'solutions' in a.get('class','').split():self.guides+=1
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in b.get('class','').split() for t,b in self.stack),'solution disclosure')
            self.solutions.append(a['data-solution-for'])
        if tag=='a':self.links.add(a.get('href'))
        if 'data-source' in a:
            need(a['data-source'] not in self.sources,'source unique');self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:
                k=a[attr];need(k not in d,'marker unique');d[k]='';self.active.append((d,k,len(self.stack)))
        if tag=='code' and a.get('id') in ('v16-c03-program','v16-c03-output'):
            k=a['id'];self.blocks[k]='';self.active.append((self.blocks,k,len(self.stack)))
        if tag=='td' and any(b.get('id')=='v16-c03-case1' for _,b in self.stack):
            self.cells.append('');self.active.append((self.cells,len(self.cells)-1,len(self.stack)))
        if tag not in ('br','hr','img','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1][0]==tag,'balanced HTML');self.stack.pop()
        self.active=[x for x in self.active if x[2]<len(self.stack)]

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=json.loads(raw[FILES[3]]);sources=json.loads(raw[FILES[2]])
    bindings=review['payload_bindings'];need(len(bindings)==3 and {b['path'] for b in bindings}==set(FILES[:3]),'three nonself bindings')
    for b in bindings:
        payload=raw[b['path']];need((len(payload),sha256(payload).hexdigest())==(b['bytes'],b['sha256']),'frozen payload')
    doc=Read();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'closed HTML')
    ex=['v16-c03-e'+str(i) for i in range(1,9)]
    need(doc.exercises==doc.solutions==ex and set(review['exact_prompt_review'])==set(ex),'eight fully reviewed exact solutions')
    need(doc.cases==['v16-c03-case1','v16-c03-case2'] and doc.guides==3,'two cases and guides')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==2,'scoped sources')
    need({'v16-c02.html','curriculum.html#v16-c04'}<=doc.links,'prerequisite and successor')
    need(doc.cells==['million','40','36','thousand','60000','66000','million','20','None','million','None','50'],'raw table actual cells')
    need(set(doc.blocks)=={'v16-c03-program','v16-c03-output'},'actual runnable artifact and transcript')
    code=doc.blocks['v16-c03-program'];expected_text=doc.blocks['v16-c03-output']+'\n'
    run=subprocess.run([sys.executable,'-I','-B','-O','-c',code],cwd='/',capture_output=True,text=True,timeout=20)
    need(run.returncode==0 and run.stderr=='' and run.stdout==expected_text,'actual displayed code exact optimized transcript')
    reports=json.loads(run.stdout)
    # Independent exact target reconstruction, not values returned by analyze().
    base={'excluded':['C: missing end','D: missing start'],'matched':['A','B'],'matched_start_million':'100'}
    oracle={'toy-v1':dict(base,matched_end_million='102',matched_growth='1/50',mean_bank_growth='0',observed_file_growth='4/15'),
            'toy-v2':dict(base,matched_end_million='100',matched_growth='0',mean_bank_growth='-1/60',observed_file_growth='1/4')}
    need(reports==oracle,'independent report oracle')
    namespace={'__name__':'reader_api'};out=io.StringIO();err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):exec(compile(code,'<displayed-reader>','exec'),namespace)
    need(out.getvalue()==err.getvalue()=='','reader import is quiet')
    analyze=namespace['analyze'];v1=namespace['V1'];v2=namespace['V2']
    need(v1==(('A','million',40,36),('B','thousand',60000,66000),('C','million',20,None),('D','million',None,50)),'embedded actual inputs')
    need(v2==tuple((b,u,s,64000 if b=='B' else e) for b,u,s,e in v1),'one-cell version revision')
    inputs={k:literal(v) for k,v in doc.inputs.items()};shown={k:literal(v) for k,v in doc.results.items()}
    need(inputs=={'target':F(1,50),'revision':64000,'exercise-revision':63000},'displayed assumptions')
    comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:comparisons+=1;need(a==b,label)
    aggregate=lambda start,end:(end-start)/start
    a0,a1,b0,b1=map(F,(40,36,60,66));s=a0+b0;e=a1+b1
    g1=aggregate(s,e);m1=(aggregate(a0,a1)+aggregate(b0,b1))/2
    revised=inputs['revision']/1000;g2=aggregate(s,a1+revised);m2=(aggregate(a0,a1)+aggregate(b0,revised))/2
    e2=inputs['exercise-revision']/1000
    expected={'matched':(s,e,g1),'mean':m1,'observed':(s+20,e+50,aggregate(s+20,e+50)),
              'wrong-totals':(F(60040),F(66036)),'wrong-growth':F(66036-60040,60040),
              'e2-total':(s,a1+e2,aggregate(s,a1+e2)),'e2-mean':(aggregate(a0,a1)+aggregate(b0,e2))/2,
              'e3-total':(s+20,e,aggregate(s+20,e)),'e3-mean':(aggregate(a0,a1)+aggregate(b0,b1)-1)/3,
              'e4-changes':(g2-g1,m2-m1),'e4-points':(100*(g2-g1),100*(m2-m1)),
              'e5-table':(g1,g2,m1,m2)}
    need(set(expected)==set(shown),'all displayed results')
    for key,value in expected.items():eq(shown[key],value,'display '+key)
    for rows,expected_report in ((v1,oracle['toy-v1']),(v2,oracle['toy-v2'])):
        for perm in permutations(rows):eq(analyze(perm),expected_report,'row order invariance')
        thousands=tuple((b,'thousand',None if s is None else s*(1000 if u=='million' else 1),None if e is None else e*(1000 if u=='million' else 1)) for b,u,s,e in rows)
        eq(analyze(thousands),expected_report,'common-unit invariance')
    changed=tuple((b,u,s,int(inputs['exercise-revision']) if b=='B' else e) for b,u,s,e in v1)
    result=analyze(changed);eq(F(result['matched_growth']),expected['e2-total'][2],'exercise2 actual reader');eq(F(result['mean_bank_growth']),expected['e2-mean'],'exercise2 mean')
    zeroed=tuple((b,u,0 if s is None else s,0 if e is None else e) for b,u,s,e in v1);result=analyze(zeroed)
    eq(result['matched'],['A','B','C'],'exercise3 sample');eq(F(result['matched_growth']),expected['e3-total'][2],'exercise3 growth');eq(F(result['mean_bank_growth']),expected['e3-mean'],'exercise3 mean')
    # Positive-baseline / observed-zero boundary and exact weighting identity.
    eq(analyze((('Z','million',5,0),))['matched_growth'],'-1','observed zero end retained')
    for end_a in (0,36,40,80):
        for end_b in (0,60,66,120):
            result=analyze((('A','million',40,end_a),('B','million',60,end_b)))
            eq(F(result['matched_growth']),F(end_a+end_b-100,100),'aggregate alternatives')
            eq(F(result['mean_bank_growth']),(F(end_a-40,40)+F(end_b-60,60))/2,'mean alternatives')
            eq(F(result['matched_growth']),F(2,5)*F(end_a-40,40)+F(3,5)*F(end_b-60,60),'weights alternatives')
    bad=[(),(('A','million',0,5),),(('A','million',None,5),),(('A','million',1,None),),
         (('A','million',1,1),('A','million',2,2)),(('','million',1,1),),((True,'million',1,1),),
         (('A','billion',1,1),),(('A',[],1,1),),(('A','million',-1,2),),(('A','million',1,-2),),
         (('A','million',True,2),),(('A','million',1.0,2),),(('A','million',1,2,3),)]
    rejected=0
    for rows in bad:
        try:analyze(rows)
        except ValueError:rejected+=1
        else:raise ValueError('invalid reader domain accepted')
    for name,payload in raw.items():need((root/name).read_bytes()==payload,'unchanged runtime payload')
    return {'chapter':'v16-c03','status':'passed','worked_cases':2,'solutions':8,'input_groups':len(inputs),'result_groups':len(shown),'comparisons':comparisons,'rejected_inputs':rejected,'displayed_code_executed':True,'exact_transcript_matched':True,'runtime_files':4,'qualitative_scope':'Full author review recorded; independent root/peer acceptance pending.'}

if __name__=='__main__':check()
