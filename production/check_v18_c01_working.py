"""V18C01 strategy artifact and numerical gates; substantive author review is separate."""
from pathlib import Path
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product, combinations
import hashlib,json,sys
FILES=('production/v18-c01-working.html','production/check_v18_c01_working.py','production/v18-c01-sources-working.json','production/v18-c01-author-review-working.json')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(p):
    b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def values(text):return tuple(F(t.strip().replace('−','-')) for t in text.strip().strip('()').split(',') if t.strip())
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.h1=False;self.worked=[];self.exercises=[];self.answers=[];self.sources=[];self.inputs={};self.results={};self.marker=None;self.details=0;self.in_ex=False;self.tables={};self.table=None;self.row=None;self.cell=None;self.points={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1=True
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='ol' and 'exercises' in a.get('class','').split():self.in_ex=True
        if tag=='li' and self.in_ex:self.exercises.append(a['id'])
        if tag=='details' and 'solutions' in a.get('class','').split():self.details+=1
        if 'data-solution-for' in a:need(self.details>0,'answer outside solution wrapper');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.append((a['data-source'],a['href']))
        for k,d in [('data-input',self.inputs),('data-result',self.results)]:
            if k in a:need(a[k] not in d,'duplicate marker');d[a[k]]='';self.marker=(d,a[k])
        if tag=='table':self.table=a.get('id');self.tables[self.table]=[]
        if tag=='tr' and self.table:self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=''
        if 'data-points' in a:self.points.setdefault(self.table,[]).append(int(a['data-points']))
    def handle_endtag(self,tag):
        if tag=='span':self.marker=None
        if tag=='ol':self.in_ex=False
        if tag=='details' and self.details:self.details-=1
        if tag in ('th','td') and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:self.tables[self.table].append(self.row);self.row=None
        if tag=='table':self.table=None
    def handle_data(self,text):
        if self.marker:self.marker[0][self.marker[1]]+=text
        if self.cell is not None:self.cell+=text


def exact(data,n):
    need(type(data) is tuple and len(data)==n and all(type(x) in (int,F) for x in data),'exact tuple domain')
    return tuple(F(x) for x in data)

def academic(rows,resources,research_min=0):
    cash,reserve,hours,priority=exact(resources,4)
    need(min(cash,reserve,hours,priority)>=0 and reserve<=cash,'academic resource domain')
    need(type(research_min) in (int,F) and research_min>=0,'research domain')
    need(len(rows)==3 and len(set(rows))==3,'three distinct modules')
    for row in rows.values():
        c,h,n,a,s=exact(row,5);need(min(c,h,n,a,s)>=0 and max(a,s)<=n and all(x.denominator==1 for x in (n,a,s)),'module domain')
    out={}
    for n in range(4):
        for names in combinations(rows,n):
            totals=tuple(sum((rows[k][j] for k in names),F(0)) for j in range(5))
            c,h,places,a,s=totals
            fits=c<=cash-reserve and h<=hours and a>=priority and s>=research_min
            out[names]=(totals,fits)
    eligible={k:v[0] for k,v in out.items() if v[1]}
    maximum=max((v[2] for v in eligible.values()),default=None)
    return out,tuple(k for k,v in eligible.items() if v[2]==maximum)

def bank(plan,resources):
    c,w,l,total,priority,income=exact(plan,6)
    cash,loans,deposits,equity,cf,ef,pf=exact(resources,7)
    need(min(cash,loans,deposits,equity,cf,ef,pf)>=0 and cash+loans==deposits+equity,'opening balance domain')
    need(min(c,w,l,total,priority)>=0 and priority<=total and w<=deposits and l<=loans and total.denominator==priority.denominator==1,'plan domain')
    # Apply three transactions to a four-entry ledger, not a combined risk buffer.
    ledger=[cash,loans,deposits,equity]
    for change in ((-c,0,0,-c),(-w,0,-w,0),(0,-l,0,-l)):
        ledger=[v+d for v,d in zip(ledger,change)]
        need(ledger[0]+ledger[1]==ledger[2]+ledger[3],'transaction balance')
    passed=ledger[0]>=cf and ledger[3]>=ef and priority>=pf and income>0
    return tuple(ledger),passed

def bank_choice(plans,resources):
    eligible={k:p[4] for k,p in plans.items() if bank(p,resources)[1]}
    top=max(eligible.values(),default=None)
    return tuple(k for k,v in eligible.items() if v==top)

def alter(rows,key,index,value):
    changed=dict(rows);p=list(rows[key]);p[index]=F(value);changed[key]=tuple(p);return changed

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    original={p:digest(root/p) for p in FILES};review=json.loads((root/FILES[3]).read_text())
    need(set(review['payloads'])==set(FILES[:3]),'three nonself bindings')
    for path,binding in review['payloads'].items():need(original[path]==binding,'binding '+path)
    page=Page();page.feed((root/FILES[0]).read_text());sources=json.loads((root/FILES[2]).read_text())
    need(not page.h1 and len(set(page.ids))==len(page.ids),'HTML/unique IDs')
    tasks=['v18-c01-ex'+str(i) for i in range(1,9)]
    need(page.exercises==page.answers==tasks,'eight matched solutions')
    need(page.worked==['v18-c01-case1','v18-c01-case2'],'two strategy artifacts')
    need(set(page.sources)=={(s['id'],s['url']) for s in sources['sources']},'source URLs')
    inputs={k:values(v) for k,v in page.inputs.items()};shown={k:values(v) for k,v in page.results.items()}
    need(set(inputs)=={'academic-resources','bank-resources'},'all resource primitives')
    modules={row[0].split(' — ')[0]:tuple(F(x) for x in row[1:]) for row in page.tables['v18-c01-modules'][1:]}
    plans={row[0].split(' — ')[0]:tuple(F(x) for x in row[1:]) for row in page.tables['v18-c01-bank-plans'][1:]}
    need(tuple(modules)==('B','R','E') and tuple(plans)==('O','R','D','B'),'complete menus')
    ar=inputs['academic-resources'];br=inputs['bank-resources'];out,choice=academic(modules,ar);count=0
    need(choice==(('B','E'),),'academic optimum');count+=1
    table=page.tables['v18-c01-portfolios'][1:];need(len(table)==8,'complete visible enumeration')
    for row,(names,(totals,fits)) in zip(table,out.items()):
        label='+'.join(names) if names else 'None'
        need(row[0]==label and tuple(F(x) for x in row[1:5])==totals[:4],'portfolio table')
        need(row[5].startswith('Eligible')==fits,'visible eligibility');count+=6
    c,h,n,a,s=out[choice[0]][0]
    expected={'academic-choice':(c,h,n,a,ar[0]-c,ar[0]-ar[1]-c),'academic-evidence':(F(30,37),F(30,42),F(35,42))}
    need(bank_choice(plans,br)==('R',),'bank optimum');count+=1
    for row in page.tables['v18-c01-bank-balances'][1:]:
        balance,ok=bank(plans[row[0]],br);need(tuple(F(x) for x in row[1:5])==balance,'displayed bank balance');count+=4
    need(len(page.tables['v18-c01-bank-balances'])==5,'four visible balances')
    b,_=bank(plans['R'],br)
    expected['bank-choice']=(b[0],b[3],b[0]-br[4],b[3]-br[5],plans['R'][4])
    rw=br[0]-plans['R'][0]-br[4];rl=br[3]-plans['R'][0]-br[5];bw=br[0]-plans['B'][0]-br[4]
    expected['bank-thresholds']=(rw,rl,bw,bank(alter(plans,'B',1,bw)['B'],br)[0][0],bank(alter(plans,'B',1,bw-1)['B'],br)[0][0])
    changed=alter(modules,'B',0,51);new,ch=academic(changed,ar);need(ch==(('B',),),'cost revision choice');count+=1
    c,h,n,a,s=new[ch[0]][0];expected['academic-cost-change']=(c,h,n,a,ar[0]-c,ar[0]-ar[1]-c,ar[2]-h)
    need(academic(modules,ar,12)[1]==(),'research infeasible');count+=1
    expanded=(F(100),ar[1],F(700),ar[3]);ex,ch=academic(modules,expanded,12);need(ch==(('B','R'),),'expanded choice');count+=1
    c,h,n,a,s=ex[ch[0]][0];expected['academic-expanded']=(c,h,n,a,s,expanded[0]-c)
    for resource in [(F(100),ar[1],ar[2],ar[3]),(ar[0],ar[1],F(700),ar[3])]:need(academic(modules,resource,12)[1]==(),'both resources needed');count+=1
    expected['academic-rate-set']=tuple(F(30+k,42) for k in range(6))
    revised=alter(plans,'B',1,45);b,ok=bank(revised['B'],br);need(ok and bank_choice(revised,br)==('B',),'broker evidence-conditional choice');count+=1
    expected['broker-revision']=b+(b[0]+b[1],revised['B'][4])
    expensive=alter(plans,'R',0,12);b,ok=bank(expensive['R'],br);need(not ok and bank_choice(expensive,br)==(),'no expansion');count+=1
    expected['relationship-cost-change']=(b[0],b[3],b[0]-br[4],b[3]-br[5])
    revision,ch=academic(alter(modules,'B',0,49),ar);c=revision[ch[0]][0][0];expected['academic-review']=(c,ar[0]-c,ar[0]-ar[1]-c)
    boundary,ch=academic(alter(modules,'B',0,50),ar);c=boundary[ch[0]][0][0]
    l12=bank(alter(plans,'R',2,12)['R'],br);l13=bank(alter(plans,'R',2,13)['R'],br)
    expected['retention-boundaries']=(c,ar[0]-c,l12[0][0],l12[0][3],l13[0][3]);need(l12[1] and not l13[1],'loss boundary');count+=1
    need(set(shown)==set(expected),'all displayed result groups')
    for k,v in expected.items():need(shown[k]==v,'displayed '+k);count+=len(v)
    # Independently exhaust binary primitive selections to check resource/choice transitions.
    academic_worlds=0
    for bc,opening,time in product((40,50,51),(90,100),(600,700)):
        m=alter(modules,'B',0,bc);rs=(F(opening),ar[1],F(time),ar[3]);enumerated,choices=academic(m,rs);scores={}
        for bits in product((0,1),repeat=3):
            names=tuple(k for k,bit in zip(m,bits) if bit)
            money=sum(m[k][0] for k in names);hours=sum(m[k][1] for k in names);access=sum(m[k][3] for k in names)
            if opening-money>=ar[1] and hours<=time and access>=ar[3]:scores[names]=sum(m[k][2] for k in names)
        highest=max(scores.values(),default=None);need(set(choices)=={k for k,v in scores.items() if v==highest},'binary-choice oracle');count+=1;academic_worlds+=1
    bank_worlds=0
    for setup,withdrawal,loss in product((6,11,12),(35,44,45),(7,12,13)):
        row=(F(setup),F(withdrawal),F(loss))+plans['R'][3:];bal,ok=bank(row,br)
        need(ok==(setup+withdrawal<=50 and setup+loss<=18),'two separate screens');count+=1
        need(bal[0]<=br[0]-setup<=br[0] and bal[3]<=br[3]-setup<=br[3],'minimum across stages');count+=2;bank_worlds+=1
    # No sum-of-buffers shortcut; D has greater earnings yet lower priority capacity.
    d=bank(plans['D'],br)[0];need(d[0]+d[3]==34 and d[0]+d[1]==d[2]+d[3] and plans['D'][5]>plans['R'][5] and plans['D'][4]<plans['R'][4],'nondominance/double count');count+=4
    need(br[0]-plans['R'][1]-br[4]==15 and br[3]-plans['R'][2]-br[5]==11,'setup bound');count+=2
    invalid=0
    bad=[lambda:academic(modules,(90,91,600,12)),lambda:academic(modules,(90,10,-1,12)),lambda:academic(modules,(90,10,True,12)),lambda:academic(modules,ar,-1),lambda:academic(alter(modules,'B',0,-1),ar),lambda:academic(alter(modules,'B',3,25),ar),lambda:academic(alter(modules,'B',2,F(1,2)),ar),lambda:bank(plans['R'],(60,140,170,31,10,12,40)),lambda:bank(alter(plans,'R',1,-1)['R'],br),lambda:bank(alter(plans,'R',1,171)['R'],br),lambda:bank(alter(plans,'R',2,141)['R'],br),lambda:bank(alter(plans,'R',4,81)['R'],br),lambda:bank((True,35,7,80,48,4),br)]
    for f in bad:
        try:f()
        except ValueError:invalid+=1
        else:raise ValueError('invalid domain accepted')
    need(original=={p:digest(root/p) for p in FILES},'runtime mutation')
    result={'chapter':'v18-c01','status':'passed','runtime_files':4,'worked_cases':2,'exercises':8,'result_groups':len(shown),'comparisons':count,'academic_worlds':academic_worlds,'bank_worlds':bank_worlds,'invalid_domains':invalid,'scope':'Original fictional strategy cases; arithmetic gates supplement full author artifact/proof review. No real leadership or regulatory certification.'}
    json.dumps(result,allow_nan=False);return result
if __name__=='__main__':
    need(len(sys.argv)<=2,'usage: check_v18_c01_working.py [book-root]');check(sys.argv[1] if len(sys.argv)==2 else None)
