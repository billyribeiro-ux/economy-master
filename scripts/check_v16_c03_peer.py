"""Independent six-file audit of the displayed reproduction experiment."""
from fractions import Fraction as Q
from pathlib import Path
from html.parser import HTMLParser
from hashlib import sha256
from copy import deepcopy
import ast,json,subprocess,sys,types
ROOT=Path(__file__).resolve().parents[1]
FILES=['content/chapters/v16-c03.html','scripts/check_v16_c03.py','content/reviews/v16-c03-sources.json','content/reviews/v16-c03-author.json','scripts/check_v16_c03_peer.py','content/reviews/v16-c03-peer.json']

def guard(ok,message):
    if not ok:raise ValueError('C03 peer: '+message)

def parse_numbers(text):
    def visit(n):
        if isinstance(n,ast.Expression):return visit(n.body)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(visit(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value) is int:return Q(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('unexpected numeric annotation')
    return visit(ast.parse(text.strip(),mode='eval'))

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.sources={};self.markers={};self.capture=None;self.code={};self.code_id=None;self.tables=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);guard(len(a)==len(attrs),'duplicate HTML attributes')
        guard(tag!='h1','chapter fragment must have no h1')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a.get('id'))
        if tag=='li' and any(t=='ol' and 'exercises' in d.get('class','').split() for t,d in self.stack):self.tasks.append(a.get('id'))
        if 'data-solution-for' in a:
            guard(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'solutions disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        for k in ('input','result'):
            if 'data-'+k in a:
                self.capture=(k,a['data-'+k]);guard(self.capture not in self.markers,'duplicate number');self.markers[self.capture]=''
        if tag=='code' and 'id' in a:self.code_id=a['id'];self.code[self.code_id]=''
        if tag=='table':self.tables.append([])
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('img','br','hr','meta','link','input'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.capture:self.markers[self.capture]+=text
        if self.code_id:self.code[self.code_id]+=text
        if self.cell is not None:self.cell+=text
    def handle_endtag(self,tag):
        guard(bool(self.stack) and self.stack[-1][0]==tag,'HTML balance')
        _,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.capture=None
        if tag=='code':self.code_id=None
        if tag in ('td','th'):self.row.append(self.cell.strip());self.cell=None
        if tag=='tr':self.tables[-1].append(self.row);self.row=None

def independent(rows):
    """Reconstruct in common thousand-units, then derive the million-unit output."""
    accounts={}
    for bank,unit,start,end in rows:
        multiplier={'million':1000,'thousand':1}[unit]
        accounts[bank]=(None if start is None else start*multiplier,None if end is None else end*multiplier)
    keys=sorted(accounts);matched=[k for k in keys if accounts[k][0] is not None and accounts[k][0]>0 and accounts[k][1] is not None]
    guard(matched,'oracle has matched accounts')
    start=sum(accounts[k][0] for k in matched);end=sum(accounts[k][1] for k in matched)
    allstart=sum(v[0] for v in accounts.values() if v[0] is not None);allend=sum(v[1] for v in accounts.values() if v[1] is not None)
    excluded=[]
    for k in keys:
        if k not in matched:
            a,b=accounts[k]
            reason='missing start' if a is None else ('missing end' if b is None else 'zero start')
            excluded.append(k+': '+reason)
    report={'matched':matched,'excluded':excluded,'matched_start_million':str(Q(start,1000)),'matched_end_million':str(Q(end,1000)),'matched_growth':str(Q(end-start,start)),'mean_bank_growth':str(sum(Q(accounts[k][1]-accounts[k][0],accounts[k][0]) for k in matched)/len(matched)),'observed_file_growth':str(Q(allend-allstart,allstart))}
    return report,(Q(allstart,1000),Q(allend,1000))

def check(root=None):
    root=Path(root) if root is not None else ROOT
    record=json.loads((root/FILES[-1]).read_text());guard(set(record['payloads'])==set(FILES[:-1]),'five frozen payloads')
    for name,rec in record['payloads'].items():
        raw=(root/name).read_bytes();guard(rec=={'bytes':len(raw),'sha256':sha256(raw).hexdigest()},'freeze '+name)
    guard(all(record['review'].values()) and not record['open_material_findings'],'peer full review')
    page=Page();page.feed((root/FILES[0]).read_text());page.close()
    guard(not page.stack and len(page.ids)==len(set(page.ids)),'full unique fragment')
    expected=[f'v16-c03-e{i}' for i in range(1,9)]
    guard(page.tasks==expected and page.answers==expected,'eight exact answer pairs')
    guard(page.worked==['v16-c03-case1','v16-c03-case2'],'two worked artifacts')
    sources=json.loads((root/FILES[2]).read_text());guard(page.sources=={s['id']:s['url'] for s in sources['sources']},'source routes')
    numbers={k:parse_numbers(v) for k,v in page.markers.items()}
    comparisons=0
    def equal(a,b,label):
        nonlocal comparisons
        if isinstance(b,dict):
            guard(set(a)==set(b),label+' keys')
            for k,v in b.items():equal(a[k],v,label+'/'+k)
        elif isinstance(b,(list,tuple)):
            guard(len(a)==len(b),label+' count')
            for x,y in zip(a,b):equal(x,y,label)
        else:guard(a==b,label);comparisons+=1
    def marker(name,value):equal(numbers[('result',name)],value,name)
    # Derive actual primitives from the visible input table, before executing reader.
    table=page.tables[0];equal(table[0],['Bank','Reported unit','Date 0','Date 1'],'raw headings')
    rows=[]
    for bank,unit,a,b in table[1:]:rows.append((bank,unit,None if a=='None' else int(a),None if b=='None' else int(b)))
    equal(rows,[('A','million',40,36),('B','thousand',60000,66000),('C','million',20,None),('D','million',None,50)],'visible primitive specification')
    baseline,totals=independent(rows);revision=int(numbers[('input','revision')]);v2=[(b,u,s,revision if b=='B' else e) for b,u,s,e in rows];updated,_=independent(v2)
    expected_output={'toy-v1':baseline,'toy-v2':updated};shown=json.loads(page.code['v16-c03-output']);equal(shown,expected_output,'transcript independent reconstruction')
    code=page.code['v16-c03-program']
    tree=ast.parse(code);imports=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
        if isinstance(n,ast.ImportFrom):imports.append(n.module)
    guard(set(imports)=={'fractions','json'},'stdlib inline program boundary')
    proc=subprocess.run([sys.executable,'-I','-B','-O','-'],input=code,text=True,cwd='/',capture_output=True)
    guard(proc.returncode==0 and not proc.stderr,'actual inline execution')
    guard(proc.stdout==page.code['v16-c03-output']+'\n','exact displayed transcript bytes')
    equal(json.loads(proc.stdout),expected_output,'actual execution independent output')
    module=types.ModuleType('c03_peer_reader');exec(compile(code,'<displayed-c03>','exec'),module.__dict__)
    equal(module.V1,rows,'program actual V1 matches table');equal(module.V2,v2,'program actual V2 matches revision')
    equal(numbers[('input','target')],Q(baseline['matched_growth']),'target')
    marker('matched',(Q(baseline['matched_start_million']),Q(baseline['matched_end_million']),Q(baseline['matched_growth'])))
    marker('mean',Q(baseline['mean_bank_growth']));marker('observed',(*totals,Q(baseline['observed_file_growth'])))
    wrongstart=rows[0][2]+rows[1][2];wrongend=rows[0][3]+rows[1][3]
    marker('wrong-totals',(wrongstart,wrongend));marker('wrong-growth',Q(wrongend-wrongstart,wrongstart))
    third=int(numbers[('input','exercise-revision')]);v3=[(b,u,s,third if b=='B' else e) for b,u,s,e in rows];r3,_=independent(v3)
    marker('e2-total',(Q(r3['matched_start_million']),Q(r3['matched_end_million']),Q(r3['matched_growth'])));marker('e2-mean',Q(r3['mean_bank_growth']))
    zero=[(b,u,0 if s is None else s,0 if e is None else e) for b,u,s,e in rows];rz,_=independent(zero)
    marker('e3-total',(Q(rz['matched_start_million']),Q(rz['matched_end_million']),Q(rz['matched_growth'])));marker('e3-mean',Q(rz['mean_bank_growth']));equal(rz['matched'],['A','B','C'],'imputation population')
    changes=(Q(updated['matched_growth'])-Q(baseline['matched_growth']),Q(updated['mean_bank_growth'])-Q(baseline['mean_bank_growth']))
    marker('e4-changes',changes);marker('e4-points',tuple(100*x for x in changes));marker('e5-table',(Q(baseline['matched_growth']),Q(updated['matched_growth']),Q(baseline['mean_bank_growth']),Q(updated['mean_bank_growth'])))
    guard(len(numbers)==15,'all numeric annotations checked')
    # Actual reader function compared with independently derived accounts on changed populations.
    variants=[rows,v2,v3,zero,list(reversed(rows)),[('A','thousand',40000,36000),('B','million',60,66),*rows[2:]],rows+[('E','million',10,0)],rows+[('E','million',0,5)],rows+[('E','million',None,None)]]
    for final_c,initial_d in [(20,50),(0,100)]:
        variants.append([(b,u,initial_d if b=='D' else s,final_c if b=='C' else e) for b,u,s,e in rows])
    for data in variants:
        before=deepcopy(data);want,_=independent(data);equal(module.analyze(data),want,'changed-data oracle');equal(data,before,'reader no input mutation')
    plus,_=independent(variants[-2]);minus,_=independent(variants[-1]);guard(Q(plus['matched_growth'])>0 and Q(minus['matched_growth'])<0,'same observed cells permit opposite full-population signs')
    # An observed end of zero is eligible, whereas missing end is not.
    guard('E' in module.analyze(variants[6])['matched'] and 'E' not in module.analyze(variants[8])['matched'],'zero versus missing')
    rejected=0
    invalid=[[],[('A','million',0,1)],[('A','million',None,None)],rows+[rows[0]],[('', 'million',1,2)],[('A','billion',1,2)],[('A','million',True,2)],[('A','million',1,False)],[('A','million',1.0,2)],[('A','million',1,-1)],[('A','million',-1,2)],[('A','million',1,'2')],[('A',[],1,2)],[('A','million',1)]]
    for data in invalid:
        try:module.analyze(data)
        except ValueError:rejected+=1
        else:raise ValueError('displayed program accepted invalid input')
    return {'status':'passed','runtime_files':6,'exact_comparisons':comparisons,'numeric_annotations':len(numbers),'independent_data_scenarios':len(variants),'invalid_domains_rejected':rejected,'actual_inline_optimized_executions':1,'exact_transcript_matched':True,'worked_cases':2,'exercises_and_solutions':8}

if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
