"""Quiet exact checks of the original integrated case; standard library only."""
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json, subprocess, sys, tempfile, types

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'integrated-case'
READERS = [f'content/projects/{PREFIX}-{s}' for s in
           ('inputs.json','analysis.py','output.json','README.txt','manifest.json')]
PAYLOADS = ['content/cross-assessments/integrated-case.html', *READERS,
            'content/reviews/integrated-case-sources.json', 'scripts/check_integrated_case.py']
RUNTIME = [*PAYLOADS, 'content/reviews/integrated-case-author.json']

def need(ok, msg):
    if not ok: raise ValueError(msg)

def load_module(path):
    m = types.ModuleType('integrated_reader'); m.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), m.__dict__)
    return m

class Document(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=set(); self.stack=[]; self.tasks={}; self.answers=[]
        self.sources={}; self.rubrics=[]; self.h1=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); need(len(a)==len(attrs),'duplicate attributes')
        if 'id' in a:
            need(a['id'] not in self.ids,'duplicate ID'); self.ids.add(a['id'])
        if 'data-points' in a:self.tasks[a['id']]=(int(a['data-points']),a['data-domain'])
        if 'data-solution-for' in a:
            need(any(t=='details' and 'solutions' in d.get('class','').split() for t,d in self.stack),'undisclosed solution')
            self.answers.append(a['data-solution-for'])
        if 'data-rubric' in a:self.rubrics.append(sum(map(int,a['data-rubric'].split(','))))
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if tag=='h1':self.h1+=1
        if tag not in ('br','hr','img','input','meta','link','wbr'):self.stack.append((tag,a))
    def handle_endtag(self, tag):
        need(self.stack and self.stack[-1][0]==tag,'unbalanced HTML');self.stack.pop()

def check(root=None):
    root=Path(root) if root is not None else ROOT
    author=json.loads((root/RUNTIME[-1]).read_text())
    need(set(author['payloads'])==set(PAYLOADS),'author inventory')
    for p, rec in author['payloads'].items():
        b=(root/p).read_bytes();need(rec=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'frozen payload '+p)
    need(author['open_material_findings']==[] and all(author['review'].values()),'author review incomplete')
    manifest=json.loads((root/READERS[-1]).read_text())
    need(set(manifest['files'])=={Path(p).name for p in READERS[:-1]},'reader manifest inventory')
    for name, rec in manifest['files'].items():
        b=(root/'content/projects'/name).read_bytes();need(rec=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'reader bytes')
    doc=Document();doc.feed((root/PAYLOADS[0]).read_text());doc.close()
    need(not doc.stack and doc.h1==1,'HTML completeness')
    need(doc.tasks=={f'{PREFIX}-t{i}':(p,d) for i,(p,d) in enumerate([(20,'D1'),(20,'D2'),(10,'D3'),(20,'D4'),(15,'D5'),(10,'D3'),(5,'D5')],1)},'task scoring')
    need(all(sum(p for p,d in doc.tasks.values() if d==domain)==20 for domain in ('D1','D2','D3','D4','D5')),'domain score')
    expected={f'{PREFIX}-{kind}{i}' for kind,count in [('t',7),('o',2),('r',5)] for i in range(1,count+1)}
    need(set(doc.answers)==expected and len(doc.answers)==len(expected) and expected<=doc.ids,'matched full solutions')
    need(doc.rubrics==[20,20,10,20,15,10,5],'rubric allocation')
    sources=json.loads((root/'content/reviews/integrated-case-sources.json').read_text())
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']},'source routes')
    reader=load_module(root/READERS[1]);data=json.loads((root/READERS[0]).read_text())
    result=reader.run(data);need(result==json.loads((root/READERS[2]).read_text()),'reference reproduction')
    comparisons=0
    def eq(a,b,label):
        nonlocal comparisons
        need(a==reader.pack(b),label);comparisons+=1
    eq(result['state_prices'],[F(2,5),F(1,2)],'state prices');eq(result['safe_price'],F(9,10),'bond')
    eq(result['safe_gross_return'],F(10,9),'safe');eq(result['causal_interval'],[1,3],'identification')
    eq(result['observationally_equivalent_endpoint_parameters'],[[1,2],[3,0]],'sharpness')
    for n,row in enumerate(result['policies']):
        eq(row['quantity'],n,'quantity');need(row['feasible'] and not row['failures'],'baseline feasibility')
        for key,val in {'installation':4*n,'grant':n,'grant_admin':F(n,10),'levy_each':F(11*n,20),
                        'developer_equity':n,'bank_loan':2*n,'debt_face':F(5*n,2),
                        'debt_payoffs':[F(5*n,2),2*n],'equity_payoffs':[F(5*n,2),0],
                        'debt_value':2*n,'equity_value':n,'private_npv':0,'bank_npv':0,
                        'bank_cash':4-2*n,'bank_final':[F(5*n,2)+F(10,9)*(4-2*n),2*n+F(10,9)*(4-2*n)],
                        'developer_final':[F(5*n,2)+F(10,9)*(2-n),F(10,9)*(2-n)],
                        'initial_resource_total':26,'initial_uses':26}.items():eq(row[key],val,key)
        vp=[F(3*n,4)+F(9,20)*(th*n-n*n) for th in (1,3)]
        vr=[-F(11*n,20)+F(9,20)*(th*n-n*n) for th in (1,3)]
        welfare=[F(n,5)+F(9,10)*(th*n-n*n) for th in (1,3)]
        for k,v in [('poor_values',vp),('rich_values',vr),('social_values',welfare),('direct_resource_values',welfare),('expected_value',sum(welfare)/2)]:eq(row[k],v,k)
        for j, account in enumerate(row['state_accounts']):
            bill=(6,3)[j]*n;total=60+F(10,9)*(6-3*n)
            for k,v in {'service_bill':bill,'operating_resources':n,'household_consumption':[30-bill,30],
                        'available_goods':total,'goods_total_including_operations':total,'debt_shortfall':F(n*j,2)}.items():eq(account[k],v,k)
    eq(result['expected_optimum'],{'value':F(11,10),'quantities':[1]},'prior choice')
    eq(result['minimax_regret'],{'value':F(1,5),'quantities':[1]},'minimax')
    eq(result['forecast_envelope'],[{'quantity':1,'high_weight_interval':[0,F(8,9)]},{'quantity':2,'high_weight_interval':[F(8,9),1]}],'prior envelope')
    comp=result['policies'][1]['robust_compensation']
    eq(comp,{'lower':F(11,20),'upper':F(15,22),'feasible':True,'transfer':F(11,20),'real_admin':F(11,200),'poor':[F(29,200),F(209,200)],'rich':[0,F(9,10)],'total':[F(29,200),F(389,200)]},'compensation')
    eq(result['policies'][2]['robust_compensation'],{'lower':2,'upper':F(6,11),'feasible':False},'impossible compensation')
    # Dense exact interior checks supplement (not replace) the manuscript proofs.
    for j in range(25):
        theta=1+F(j,12);w=[F(n,5)+F(9,10)*(theta*n-n*n) for n in range(3)]
        need(w[1]>w[0],'dominated zero');regret=max(w)-(8*w[1]+w[2])/9
        need(regret<=F(8,45),'lottery interval bound');comparisons+=2
    need(F(8,5)*F(1,9)==F(1,5)*(1-F(1,9))==F(8,45),'lottery crossing')
    # Changed institutions and evidence, plus exact boundary prior ties.
    for weight,choices in [('0',[1]),('8/9',[1,2]),('1',[2])]:
        d=deepcopy(data);d['high_endpoint_weight']=weight;eq(reader.run(d)['expected_optimum']['quantities'],choices,'prior boundary')
    d=deepcopy(data);d['bank_loan_cap']=3;stress=reader.run(d)
    eq([r['quantity'] for r in stress['policies'] if r['feasible']],[0,1],'cap stress')
    eq(stress['policies'][2]['failures'],['bank_funding'],'cap failure');eq(stress['minimax_regret'],{'quantities':[1],'value':0},'cap regret')
    d=deepcopy(data);d['selection_interval']=[0,1];tight=reader.run(d)
    eq(tight['causal_interval'],[2,3],'tight causal')
    eq(tight['forecast_envelope'],[{'quantity':1,'high_weight_interval':[0,F(7,9)]},{'quantity':2,'high_weight_interval':[F(7,9),1]}],'tight switch')
    eq(tight['policies'][1]['robust_compensation']['total'],[F(109,100),F(199,100)],'oral1 gain')
    eq(tight['policies'][2]['robust_compensation']['lower'],F(11,10),'oral1 lower')
    eq(tight['policies'][2]['robust_compensation']['upper'],F(15,11),'oral1 upper')
    d=deepcopy(data);d['transfer_admin_rate']=0;free=reader.run(d)
    eq(free['policies'][1]['robust_compensation']['upper'],F(3,4),'oral2 interval')
    eq(free['policies'][1]['robust_compensation']['total'],[F(1,5),2],'oral2 welfare')
    rejected=0
    for key,bad in [('quantities',[0,True]),('quantities',[0,1,1]),('quantities',[1]),('quantities',[0,11]),
        ('state_probabilities',['1/2','1/3']),('state_probabilities',[0,1]),('sdf',[0,1]),('sdf',[1,1,1]),
        ('installation_cost',0),('grant',4),('bank_loan_cap',True),('bank_loan_cap',1.5),
        ('bank_loan_cap','1e2'),('bank_loan_cap','1/0'),('bank_loan_cap',10001),
        ('high_endpoint_weight','11/10'),('selection_interval',[2,0]),('revenue_per_unit',[0,3]),('synthetic',False)]:
        d=deepcopy(data);d[key]=bad
        try:reader.run(d)
        except (ValueError,TypeError,KeyError):rejected+=1
        else:raise ValueError('invalid input accepted '+key)
    alias_rejections=0
    with tempfile.TemporaryDirectory(prefix='integrated-case-author-') as tmp:
        folder=Path(tmp)
        for p in READERS:(folder/Path(p).name).write_bytes((root/p).read_bytes())
        original={p.name:p.read_bytes() for p in folder.iterdir()}
        program=folder/'integrated-case-analysis.py'
        for name in ('inputs.json','analysis.py','README.txt','manifest.json'):
            target=folder/f'integrated-case-{name}'
            for mode in ('direct','symlink','hardlink'):
                alias=target if mode=='direct' else folder/('alias-'+mode)
                if mode=='symlink':alias.symlink_to(target)
                elif mode=='hardlink':alias.hardlink_to(target)
                proc=subprocess.run([sys.executable,'-I','-B','-O',str(program),'--output',str(alias)],cwd='/',capture_output=True)
                need(proc.returncode!=0,'protected alias accepted');alias_rejections+=1
                need(all((folder/n).read_bytes()==b for n,b in original.items()),'alias mutation')
                if mode!='direct':alias.unlink()
        out=folder/'own.json';proc=subprocess.run([sys.executable,'-I','-B','-O',str(program),'--output',str(out)],cwd='/',capture_output=True)
        need(proc.returncode==0 and not proc.stdout and not proc.stderr,'baseline CLI');need(json.loads(out.read_text())==result,'CLI result')
        changed=folder/'cap3.json';d=deepcopy(data);d['bank_loan_cap']=3;changed.write_text(json.dumps(d))
        proc=subprocess.run([sys.executable,'-I','-B','-O',str(program),'--input',str(changed),'--output',str(out)],cwd='/',capture_output=True)
        need(proc.returncode==0 and not proc.stdout and not proc.stderr,'stress CLI');need(json.loads(out.read_text())==stress,'CLI stress')
        proc=subprocess.run([sys.executable,'-I','-B','-O',str(program),'--input',str(changed),'--output',str(changed)],cwd='/',capture_output=True)
        need(proc.returncode!=0 and json.loads(changed.read_text())==d,'custom input alias');alias_rejections+=1
    return {'status':'passed','scalar_or_exact_object_comparisons':comparisons,'invalid_domains_rejected':rejected,
            'protected_alias_rejections':alias_rejections,'tasks':7,'oral_transfers':2,'retention_items':5,
            'score':100,'domains':5,'runtime_files':9,'review_scope':'Full author proof/solution reading recorded separately; no human certification.'}

if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
