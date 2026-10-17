"""Independent C07 data-construction audit; never imports author checker."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
from html.parser import HTMLParser
import ast
import json
import re
import contextlib
import io

FILES=('content/chapters/v16-c07.html','scripts/check_v16_c07.py','content/reviews/v16-c07-sources.json','content/reviews/v16-c07-author.json','scripts/check_v16_c07_peer.py','content/reviews/v16-c07-peer.json')

def require(ok,message):
    if not ok: raise ValueError(message)


def numeric(text):
    text=text.rsplit('=',1)[-1].strip().replace('−','-')
    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) is int:return F(node.value)
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


class Manuscript(BaseManuscript):
    def __init__(self):
        super().__init__();self.code={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='code' and 'id' in a:self.code[a['id']]=''
        super().handle_starttag(tag,attrs)
    def handle_data(self,text):
        for tag,a in self.stack:
            if tag=='code' and a.get('id') in self.code:self.code[a['id']]+=text
        super().handle_data(text)


def currency_oracle(rows,mapping,coverage,roster):
    """Distinct reconstruction: partition exact raw rows, sum integer currency."""
    require(rows and roster and len(set(roster))==len(roster),'nonempty unique target')
    records={}
    for row in rows:
        loan,date,lender,account,unit,amount=row
        require(type(date) is int and date in (0,1),'date')
        require(unit in ('currency','thousand') and (amount is None or type(amount) is int and amount>=0),'amount/unit')
        require((lender,account) in mapping,'linkage')
        key=(lender,loan,date)
        if key in records:require(records[key]==row,'conflicting delivery')
        records[key]=row
    totals={slot:0 for slot in coverage}
    for row in records.values():
        loan,date,lender,account,unit,amount=row;slot=(mapping[lender,account],date)
        require(slot in coverage,'missing coverage slot')
        if amount is None:require(not coverage[slot],'unknown amount in complete slot')
        else:totals[slot]+=amount*(1000 if unit=='thousand' else 1)
    panel=[[b,t,str(F(totals[b,t],1000)) if coverage[b,t] else None,'complete' if coverage[b,t] else 'missing'] for b,t in sorted(coverage)]
    return {'baseline':list(roster),'duplicates_removed':len(rows)-len(records),'panel':panel,'unique_loan_dates':len(records)}


def roster_rates(total,responded,positive):
    require(all(type(x) is int for x in (total,responded,positive)) and total>0 and 0<=positive<=responded<=total,'binary roster domain')
    return tuple(F(positive+extra,total) for extra in range(total-responded+1))


def growth(initial,final):
    require(initial>0 and final>=0,'growth domain')
    return (final-initial)/initial


def numerical_audit(doc):
    raw=[]
    for row in doc.rows:
        if len(row)==6 and row[0] in ('L1','L2','L3','L4'):
            raw.append((row[0],int(row[1]),row[2],row[3],row[4],None if row[5]=='None' else int(row[5])))
    require(len(raw)==8,'eight actual delivered table rows')
    links=(('N','n1','B1'),('S','s7','B1'),('N','n2','B2'),('S','s9','B3'))
    mapping={(a,b):c for a,b,c in links};coverage={(b,t):(b,t)!=('B2',1) for b in ('B1','B2','B3') for t in (0,1)};roster=('B1','B2')
    oracle=currency_oracle(tuple(raw),mapping,coverage,roster)
    panel={(b,t):F(value) if value is not None else None for b,t,value,status in oracle['panel']}
    analysis={r[0]:r[1:3] for r in doc.rows if r and r[0] in ('B1','B2','B3')}
    require(analysis=={b:[str(panel[b,0]),'Unknown' if panel[b,1] is None else str(panel[b,1])] for b in ('B1','B2','B3')},'actual analysis table')
    base=panel['B1',0]+panel['B2',0];known_final=panel['B1',1]
    expected={'ingestion':(F(len(raw)),F(oracle['unique_loan_dates']),F(oracle['duplicates_removed']),F(len(panel)),F(sum(x is not None for x in panel.values())),F(sum(x is None for x in panel.values()))),'b1-growth':growth(panel['B1',0],panel['B1',1]),'baseline-total':base}
    # Derive errors from exact raw contributions, not from stored answers.
    duplicate=next(row for row in raw if raw.count(row)>1);extra=F(duplicate[5],1000 if duplicate[4]=='currency' else 1)
    bad_final=known_final+extra
    expected['e2-retransmission']=(bad_final,growth(panel['B1',0],bad_final))
    n_parts={t:sum((F(row[5],1000 if row[4]=='currency' else 1) for row in set(raw) if row[2:4]==('N','n1') and row[1]==t),F(0)) for t in (0,1)}
    bad0=panel['B1',0]+n_parts[0];bad1=panel['B1',1]+n_parts[1]
    expected['e2-crosswalk']=(bad0,bad1,growth(bad0,bad1))
    match=re.search(r'0≤x≤(\d+) thousand',doc.prompts['v16-c07-e3']);require(match is not None,'extra balance bound')
    high=F(match.group(1));expected['e3-bounds']=(growth(base,known_final),growth(base,known_final+high));expected['e4-growth']=growth(base,known_final)
    survey=numeric(doc.inputs['survey-counts']);require(len(survey)==4 and all(x.denominator==1 for x in survey),'integer survey counts')
    eligible,agreed,responded,positive=map(int,survey)
    require(0<responded<=agreed<=eligible,'nested survey denominators')
    expected['response-rate']=F(responded,agreed);expected['observed-rate']=F(positive,responded)
    for key,total in (('consenter-bounds',agreed),('eligible-bounds',eligible)):
        rates=roster_rates(total,responded,positive);expected[key]=(rates[0],rates[-1])
        require(len(rates)==total-responded+1 and all(b-a==F(1,total) for a,b in zip(rates,rates[1:])),'all sharp finite-grid rates')
    match=re.search(r'responses increase from(\d+) to(\d+) and late-payment reports from(\d+) to(\d+)',doc.prompts['v16-c07-e5']);require(match is not None,'changed survey premise')
    oldr,newr,oldp,newp=map(int,match.groups());require((oldr,oldp)==(responded,positive),'changed-count consistency')
    expected['e5-response']=F(newr,agreed);expected['e5-observed']=F(newp,newr)
    for key,total in (('e5-consenter',agreed),('e5-eligible',eligible)):
        rates=roster_rates(total,newr,newp);expected[key]=(rates[0],rates[-1])
    actual={k:numeric(v) for k,v in doc.results.items()};require(set(actual)==set(expected),'every displayed result')
    for key,value in expected.items():require(actual[key]==value,'computed manuscript result '+key)
    require(growth(base,known_final)<0<growth(base,known_final+100),'aggregate sign ambiguity')
    # Oracle persisted in checker before reader program execution. Code was fully
    # read and contains no filesystem/network operations; execute actual __main__.
    namespace={'__name__':'__main__'};out=io.StringIO();err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
        exec(compile(doc.code['v16-c07-program'],'<v16-c07-reader-inline>','exec'),namespace)
    require(err.getvalue()=='' and json.loads(out.getvalue())==oracle,'actual inline execution versus independent oracle')
    require(json.loads(doc.code['v16-c07-output'])==oracle,'displayed transcript')
    require(namespace['RAW']==tuple(raw) and namespace['LINKS']==links and namespace['COVERAGE']==coverage and namespace['ROSTER']==roster,'actual program primitives match table/prose')
    construct=namespace['construct']
    def run(rows,ln=links,cov=coverage,rs=roster):return construct(rows,ln,cov,rs)
    require(run(tuple(reversed(raw)))==oracle,'row-order invariance')
    # A common-currency alternative keeps economic amounts and output identical.
    converted=tuple((loan,t,lender,account,'currency',None if amount is None else amount*(1000 if unit=='thousand' else 1)) for loan,t,lender,account,unit,amount in raw)
    require(run(converted)==currency_oracle(converted,mapping,coverage,roster)==oracle,'unit-conversion invariance')
    verified=tuple(row[:-1]+(0,) if row[2:4]==('N','n2') and row[1]==1 else row for row in raw)
    require(run(verified)==oracle,'numeric zero with incomplete coverage stays unknown')
    complete=dict(coverage);complete['B2',1]=True
    corrected=run(verified,cov=complete);require(corrected==currency_oracle(verified,mapping,complete,roster),'new evidence complete zero')
    require(next(r[2] for r in corrected['panel'] if r[:2]==['B2',1])=='0','verified zero published')
    extra_row=('L5',1,'N','n1','currency',500)
    alternative=run(tuple(raw)+(extra_row,));require(alternative==currency_oracle(tuple(raw)+(extra_row,),mapping,coverage,roster),'legitimate extra loan not duplicate')
    require(roster_rates(5,3,1)==(F(1,5),F(2,5),F(3,5)) and roster_rates(4,4,2)==(F(1,2),),'alternative small/full-response roster')
    # Meaningful failures cover code promises and mathematical domains.
    invalid=[lambda:run(tuple(raw),ln=links+(('N','n1','B1'),)),lambda:run(tuple(raw),ln=links+(('N','n1','B3'),)),lambda:run(tuple(raw)+(raw[0][:-1]+(101,),)),lambda:run(tuple(raw),cov=complete),lambda:run(tuple(raw),ln=links[1:]),lambda:run(tuple(raw),rs=('B1','B1')),lambda:run((raw[0][:4]+('bad',100),)),lambda:run((raw[0][:-1]+(-1,),)),lambda:roster_rates(5,3,4),lambda:roster_rates(0,0,0),lambda:growth(F(0),F(1))]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return len(expected),len(invalid)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};author=json.loads(raw[FILES[3]]);peer=json.loads(raw[FILES[5]])
    for record,paths in ((author,set(FILES[:3])),(peer,set(FILES[:5]))):
        bindings=record['payload_bindings'];require(len(bindings)==len(paths) and {x['path'] for x in bindings}==paths,'nonself manifest')
        for item in bindings:
            b=raw[item['path']];require(len(b)==item['bytes'] and sha256(b).hexdigest()==item['sha256'],'payload binding '+item['path'])
    doc=Manuscript();doc.feed(raw[FILES[0]].decode());require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'balanced unique fragment')
    targets={f'v16-c07-e{i}' for i in range(1,9)}
    require(set(doc.prompts)==set(doc.solutions)==targets and len(doc.worked)==2,'two worked artifacts/eight exact solutions')
    require(set(peer['exact_prompt_review'])==targets,'full reading record')
    for key in targets:
        binding=peer['exact_prompt_review'][key]
        require(sha256(doc.prompts[key].encode()).hexdigest()==binding['prompt_sha256'] and sha256(doc.solutions[key].encode()).hexdigest()==binding['solution_sha256'],'exact prompt/solution freeze')
    sources=json.loads(raw[FILES[2]])['sources'];require(len(sources)==3 and doc.sources=={x['id']:x['url'] for x in sources},'three exact source routes')
    require(all(s.get('inspection') and s.get('limits') for s in sources),'bounded source scopes')
    require({'curriculum.html#v16-c06','v16-c05.html','v16-c03.html','curriculum.html#v16-c08'}<=doc.links,'dependencies/successor')
    require('v16-c07-teachback' in doc.ids and peer['open_findings']==[],'guides/findings')
    results,invalid=numerical_audit(doc)
    return {'chapter':'v16-c07','review':'independent-peer','status':'passed','worked_cases':2,'exact_solutions':8,'result_groups':results,'inline_execution':'actual __main__ matched independent currency oracle and transcript','invalid_domain_rejections':invalid,'source_routes':3,'runtime_files':6,'scope':'Full measurement/ethics/consent review separately recorded; exact raw-table currency reconstruction, genuine reader execution and sharp finite-roster grids.'}


if __name__=='__main__':check()
