"""Independent raw-table audit for C10; author checker is opaque hash input only."""
import ast
import json
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
FILES=('production/v16-c10-working.html','production/check_v16_c10_working.py','production/v16-c10-sources-working.json','production/v16-c10-author-review-working.json','production/check_v16_c10_peer_working.py','production/v16-c10-peer-review-working.json')
def need(ok,label):
    if not ok:raise ValueError(label)
def read_number(text):
    def walk(n):
        if isinstance(n,ast.Constant):
            need(type(n.value) is int,'exact integer');return F(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('rational literal expected')
    return walk(ast.parse(text,mode='eval').body)
class Read(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.active=[];self.inputs={};self.results={};self.soltext={};self.cases=[];self.ex=[];self.sol=[];self.ids=[];self.sources={};self.tables=[];self.table=None
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(t!='h1','fragment')
        if 'id' in a:need(a['id'] not in self.ids,'unique ID');self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.cases.append(a['id'])
        if t=='li' and a.get('id','').startswith('v16-c10-e'):
            need(any(x=='ol' and 'exercises' in y.get('class','').split() for x,y in self.stack),'exercise context');self.ex.append(a['id'])
        if 'data-solution-for' in a:
            need(any(x=='details' and 'solutions' in y.get('class','').split() for x,y in self.stack),'solution context');k=a['data-solution-for'];self.sol.append(k);self.soltext[k]='';self.active.append((self.soltext,k,len(self.stack)))
        if 'data-source' in a:need(a['data-source'] not in self.sources,'source unique');self.sources[a['data-source']]=a['href']
        for attr,d in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:k=a[attr];need(k not in d,'marker unique');d[k]='';self.active.append((d,k,len(self.stack)))
        if t=='table':self.table=[];self.tables.append(self.table)
        if t=='tr' and self.table is not None:self.table.append([])
        if t in ('td','th') and self.table is not None:
            row=self.table[-1];row.append('');self.active.append((row,len(row)-1,len(self.stack)))
        if t not in ('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_data(self,s):
        for d,k,_ in self.active:d[k]+=s
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');self.stack.pop();self.active=[x for x in self.active if x[2]<len(self.stack)]
        if t=='table':self.table=None

def calculate(rows):
    need(len(rows)>0,'nonempty data');ids=[];groups={'H':[],'L':[]}
    for row in rows:
        need(len(row)==4,'four data fields');name,share,start,end=row
        need(type(name) is str and name and name not in ids,'unique bank ID');ids.append(name)
        need(all(type(v) in (int,F) for v in (share,start,end)),'rational data')
        share,start,end=map(F,(share,start,end));need(0<=share<=1 and start>0 and end>=0,'stock/share domain')
        groups['H' if share>=F(1,2) else 'L'].append((name,start,end))
    need(all(groups.values()),'both groups present')
    result={}
    for group,data in groups.items():
        n=len(data);initial=sum(v[1] for v in data);final=sum(v[2] for v in data)
        changes=tuple(end-start for _,start,end in data);growth=tuple(change/start for change,(_,start,end) in zip(changes,data))
        weights=tuple(start/initial for _,start,_ in data)
        result[group]={'names':tuple(v[0] for v in data),'growth':growth,'weights':weights,'mean':sum(growth)/n,'total':sum(changes)/initial,'initial':initial,'final':final}
    result['contrasts']=(result['H']['mean']-result['L']['mean'],result['H']['total']-result['L']['total'])
    return result

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={p:(root/p).read_bytes() for p in FILES};review=json.loads(raw[FILES[5]]);sources=json.loads(raw[FILES[2]])
    bindings=review['payload_bindings'];need(len(bindings)==5 and {b['path'] for b in bindings}==set(FILES[:5]),'five nonself runtime hashes')
    for b in bindings:
        v=raw[b['path']];need((len(v),sha256(v).hexdigest())==(b['bytes'],b['sha256']),'frozen payload')
    doc=Read();doc.feed(raw[FILES[0]].decode());doc.close();need(not doc.stack,'closed manuscript')
    ex=['v16-c10-e'+str(i) for i in range(1,9)];need(doc.ex==doc.sol==ex and set(review['exact_prompt_review'])==set(ex),'eight full reviewed solutions')
    need(doc.cases==['v16-c10-case1','v16-c10-case2'] and len(doc.tables)==2,'complete paper and revision structure')
    need(doc.sources=={s['id']:s['url'] for s in sources['sources']} and len(doc.sources)==2,'bounded source mapping')
    rows=tuple((row[0],read_number(row[1]),read_number(row[2]),read_number(row[3])) for row in doc.tables[0][1:])
    need(rows==( ('H1',F(7,10),100,110),('H2',F(3,5),10,8),('L1',F(1,5),80,84),('L2',F(3,10),20,21)),'actual four-bank raw input')
    A=calculate(rows)
    need([row[4] for row in doc.tables[0][1:]]==['H','H','L','L'],'displayed fixed groups')
    inputs={k:read_number(v) for k,v in doc.inputs.items()};values={k:read_number(v) for k,v in doc.results.items()};need(inputs=={'revised-h2':F(12)},'sole version-B correction')
    B=calculate(tuple((name,share,start,inputs['revised-h2'] if name=='H2' else end) for name,share,start,end in rows))
    expected={'bank-growth':A['H']['growth']+A['L']['growth'],
              'mean-comparison':(A['H']['mean'],A['L']['mean'],A['contrasts'][0]),
              'total-comparison':(A['H']['total'],A['L']['total'],A['contrasts'][1]),
              'revised-comparisons':(B['H']['growth'][1],B['H']['mean'],B['contrasts'][0],B['H']['final'],B['H']['total'],B['contrasts'][1]),
              'equal-size-contrasts':(F(-1,10),F(-1,10)),'revised-points':tuple(100*v for v in B['contrasts'])}
    count=0
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
            need(isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:count+=1;need(a==b,label)
    need(set(values)==set(expected),'all actual result groups')
    for k,v in expected.items():eq(values[k],v,k)
    # Verify actual table cells and all decimal percentages, independently derived above.
    need(doc.tables[1][1][1:]==['−5%','5%','−10 percentage points'],'mean table row')
    need(doc.tables[1][2][1:]==['80/11% (about 7.27%)','5%','25/11 percentage points (about 2.27)'],'total table row')
    eq(100*A['H']['total'],F(80,11),'H percentage');eq(100*A['contrasts'][1],F(25,11),'contrast points')
    eq(tuple(format(float(100*v),'.2f') for v in (A['H']['total'],A['contrasts'][1],B['contrasts'][1])),('7.27','2.27','5.91'),'rounded reported figures')
    for group in ('H','L'):
        for version in (A,B):
            g=version[group];eq(sum(g['weights']),1,'normalized initial weights');eq(sum(w*r for w,r in zip(g['weights'],g['growth'])),g['total'],'independent weighting identity');eq((g['final']-g['initial'])/g['initial'],g['total'],'stock totals')
    eq(A['H']['weights'],(F(10,11),F(1,11)),'H weights');eq(A['L']['weights'],(F(4,5),F(1,5)),'L weights')
    abstract=doc.soltext['v16-c10-e1'].split('“',1)[1].split('”',1)[0];wordcount=len(abstract.split());need(wordcount<=90,'exact illustrative abstract word limit')
    # Meaningful alternative witnesses: consistent units, equal starts, fixed growth and splitting the bank unit.
    for scale in (F(1,1000),F(10),F(1000)):
        result=calculate(tuple((name,s,scale*a,scale*b) for name,s,a,b in rows));eq(result['contrasts'],A['contrasts'],'common money-unit scaling')
    for start in (F(1),F(50),F(200)):
        equal=calculate(tuple((name,s,start,start*(end/old)) for name,s,old,end in rows));eq(equal['contrasts'],values['equal-size-contrasts'],'equal starts preserve growth')
    split=(('H1a',F(7,10),F(50),F(55)),('H1b',F(7,10),F(50),F(55)))+rows[1:]
    result=calculate(split);eq(result['contrasts'],(F(-1,20),F(1,44)),'bank split changes equal-bank target only')
    for common_growth in (F(-1),F(0),F(1,20),F(1)):
        result=calculate(tuple((name,s,start,start*(1+common_growth)) for name,s,start,end in rows))
        eq(result['contrasts'],(F(0),F(0)),'common growth zero contrast')
        for group in ('H','L'):eq((result[group]['mean'],result[group]['total']),(common_growth,common_growth),'common growth identity')
    threshold_rows=(('threshold',F(1,2),F(2),F(0)),('below',F(49,100),F(1),F(1)))
    boundary=calculate(threshold_rows);eq(boundary['H']['names'],('threshold',),'inclusive funding threshold');eq(boundary['H']['growth'],(F(-1),),'observed zero final stock')
    invalid=[(),(('A',F(1,2),0,1),('B',F(0),1,1)),(('A',F(1,2),1,-1),('B',F(0),1,1)),(('A',F(2),1,1),('B',F(0),1,1)),(('A',F(-1),1,1),('B',F(1),1,1)),(('A',F(1),1,1),('A',F(0),1,1)),(('A',F(1),1,1),),(('A',True,1,1),('B',F(0),1,1)),(('A',.5,1,1),('B',F(0),1,1)),(('A',F(1),1),('B',F(0),1,1))]
    rejected=0
    for data in invalid:
        try:calculate(data)
        except ValueError:rejected+=1
        else:raise ValueError('invalid stock/domain fixture accepted')
    for p,v in raw.items():need((root/p).read_bytes()==v,'read-only runtime')
    return {'chapter':'v16-c10','status':'passed','runtime_files':6,'worked_cases':2,'solutions':8,'result_groups':len(values),'independent_comparisons':count,'invalid_domains_rejected':rejected,'abstract_words':wordcount,'qualitative_review':'Full independent paper/revision/solution/source reading separately recorded.'}
if __name__=='__main__':check()
