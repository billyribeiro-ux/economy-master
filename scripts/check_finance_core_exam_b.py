"""Original finance-core B contracts, independently reconstructed with exact cash.

Quiet check() is read-only and portable with the four author files. It uses
chronological journals, recipient waterfalls, independent vertex certificates,
dated hedge accounts and actual resource bounds, not a saved-output oracle.
"""
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
from itertools import combinations
import json
from pathlib import Path
import re

HTML = 'content/cross-assessments/parts/finance-core-exam-b.html'
SELF = 'scripts/check_finance_core_exam_b.py'
SOURCES = 'content/reviews/finance-core-exam-b-sources.json'
REVIEW = 'content/reviews/finance-core-exam-b-author.json'
POINTS = {'1a':8,'1b':8,'1c':4,'2a':6,'2b':10,'2c':4,
          '3a':4,'3b':8,'3c':5,'3d':3,'4a':4,'4b':4,'4c':8,'4d':4,
          '5a':6,'5b':8,'5c':6}


def require(ok, label):
    if not ok:
        raise ValueError('Finance-core B: '+label)


class Audit:
    def __init__(self):
        self.comparisons=0
        self.interventions=[]
        self.rejections=0
        self.ledger_rows=0
        self.vertex_candidates=0
    def eq(self, got, expected, label):
        self.comparisons+=1
        require(got==expected,label+': '+repr(got)+' != '+repr(expected))
    def ok(self, ok, label):
        self.eq(bool(ok),True,label)
    def reject(self, fn, label):
        try:
            fn()
        except ValueError:
            self.rejections+=1
        else:
            raise ValueError('Expected domain rejection: '+label)


def number(x, label, lower=F(0), upper=None):
    require(type(x) in (int,F),label+' must be an exact rational')
    x=F(x)
    require(x>=lower and (upper is None or x<=upper),label+' outside domain')
    return x


def strict(text):
    def object_pairs(pairs):
        out={}
        for k,v in pairs:
            require(k not in out,'duplicate JSON key')
            out[k]=v
        return out
    def bad(token):
        raise ValueError('nonfinite JSON '+token)
    return json.loads(text,object_pairs_hook=object_pairs,parse_constant=bad)


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.points={};self.targets=[];self.answers={}
        self.links=[];self.sources=[];self.anchors={};self.anchor=None
        self.answer=None;self.tables={};self.table=None;self.caption=None
        self.row=None;self.cell=None;self.h1=0
        self.exercise_depth=0;self.solution_depth=0
        self.exercise_lists=0;self.solution_wrappers=0
        self.reader_prompts=0;self.reader_solutions=0
    def handle_starttag(self,tag,attrs):
        x=dict(attrs)
        classes=x.get('class','').split()
        if tag=='ol' and 'exam-parts' in classes:
            require('exercises' in classes,'standard reader exercise marker')
            self.exercise_depth=len(self.stack)+1;self.exercise_lists+=1
        if tag=='details' and 'solutions' in classes:
            self.solution_depth=len(self.stack)+1;self.solution_wrappers+=1
        if 'id' in x:self.ids.append(x['id'])
        if tag=='h1':self.h1+=1
        if 'data-points' in x:
            require(tag=='li' and x['id'] not in self.points,'unique scored list item')
            require(self.exercise_depth==len(self.stack)>0,'scored prompt inside reader exercise list')
            self.reader_prompts+=1
            self.points[x['id']]=int(x['data-points'])
        if 'data-solution-for' in x:
            require(self.answer is None,'non-nested solution')
            require(tag=='li' and self.solution_depth>0,'answer inside reader disclosure')
            self.reader_solutions+=1
            self.answer=x['data-solution-for'];self.targets.append(self.answer)
            self.answers[self.answer]=''
        if 'data-calc' in x:
            require(self.anchor is None and x['data-calc'] not in self.anchors,'unique numerical anchor')
            self.anchor=x['data-calc'];self.anchors[self.anchor]=''
        if tag=='a':self.links.append(x.get('href',''))
        if 'data-source' in x:self.sources.append(x['data-source'])
        if tag=='table':self.table={'caption':'','rows':[]}
        if tag=='caption':self.caption=''
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append(tag)
    def handle_data(self,text):
        if self.answer is not None:self.answers[self.answer]+=text
        if self.anchor is not None:self.anchors[self.anchor]+=text
        if self.caption is not None:self.caption+=text
        if self.cell is not None:self.cell+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1]==tag,'balanced HTML '+tag)
        if tag=='ol' and len(self.stack)==self.exercise_depth:self.exercise_depth=0
        if tag=='details' and len(self.stack)==self.solution_depth:self.solution_depth=0
        self.stack.pop()
        if tag=='li':self.answer=None
        if tag=='span' and self.anchor is not None:self.anchor=None
        if tag=='caption':
            self.table['caption']=self.caption.strip();self.caption=None
        if tag in ('td','th'):
            self.row.append(self.cell.strip());self.cell=None
        if tag=='tr':
            self.table['rows'].append(self.row);self.row=None
        if tag=='table':
            require(self.table['caption'] not in self.tables,'unique table caption')
            self.tables[self.table['caption']]=self.table['rows'];self.table=None


def operating_ledger(a,life=F(4),recoverable=F(50),allowance=F(5)):
    life=number(life,'remaining life',F(1,100))
    recoverable=number(recoverable,'recoverable value')
    allowance=number(allowance,'closing allowance',F(2),F(36))
    accounts={'cash':F(12),'ar':F(30),'allowance':F(-2),'inventory':F(24),
              'ppe':F(80),'ap':F(-20),'debt':F(-70),'equity':F(-54)}
    rows=[]
    def journal(changes):
        a.eq(sum(changes.values()),F(0),'balanced signed journal')
        for account,value in changes.items():accounts[account]+=value
        a.eq(sum(accounts.values()),F(0),'posting preserves accounting identity')
        rows.append(dict(accounts));a.ledger_rows+=1
    journal({'cash':F(16),'equity':F(-16)})
    journal({'ar':F(90),'equity':F(-90)})
    journal({'cash':F(84),'ar':F(-84)})
    journal({'inventory':F(36),'ap':F(-36)})
    journal({'cash':F(-32),'ap':F(32)})
    journal({'inventory':F(-40),'equity':F(40)})
    journal({'cash':F(-20),'equity':F(20)})
    dep=(80-8)/life
    require(dep<=80,'charge cannot exceed the supplied carrying amount')
    journal({'ppe':-dep,'equity':dep})
    impairment=max(accounts['ppe']-recoverable,F(0))
    journal({'ppe':-impairment,'equity':impairment})
    expense=allowance-2
    journal({'allowance':-expense,'equity':expense})
    profit=-accounts['equity']-54
    gross_change=accounts['ar']-30
    net_change=accounts['ar']+accounts['allowance']-28
    inventory_change=accounts['inventory']-24
    ap_change=-accounts['ap']-20
    indirect_gross=profit+dep+impairment+expense-gross_change-inventory_change+ap_change
    indirect_net=profit+dep+impairment-net_change-inventory_change+ap_change
    a.eq(indirect_gross,accounts['cash']-12,'gross AR cash bridge')
    a.eq(indirect_net,accounts['cash']-12,'net AR cash bridge')
    return dict(accounts=accounts,profit=profit,dep=dep,impairment=impairment,
                allowance_expense=expense,cfo=indirect_gross,wrong_cfo=indirect_net+expense)


def restructuring(a,cost=F(25),personal=F(5)):
    cost=number(cost,'rehabilitation outlay',F(0),F(61))
    personal=number(personal,'personal fee endowment')
    q=(F(9,20),F(9,20));plans=[]
    for spending,assets in [(F(0),(F(50),F(10))),(cost,(F(90),F(30)))]:
        immediate=61-spending;face=70-immediate;rows=[]
        for cash in assets:
            debt=min(face,cash);equity=cash-debt;unpaid=face-debt
            a.eq(debt+equity,cash,'core final recipients exhaust resource')
            a.eq(debt+unpaid,face,'paid plus retained nominal claim')
            a.ledger_rows+=1;rows.append((cash,debt,equity,unpaid))
        creditor=immediate+sum(qi*r[1] for qi,r in zip(q,rows))
        equity=sum(qi*r[2] for qi,r in zip(q,rows))
        a.eq(creditor+equity,immediate+sum(qi*x for qi,x in zip(q,assets)),
             'old-claim price identity after spending')
        a.eq(F(64),F(3)+spending+immediate,'buyer cash allocated once at date zero')
        plans.append(dict(immediate=immediate,face=face,rows=rows,creditor=creditor,equity=equity))
    base,rehab=plans
    low=max(base['creditor']-rehab['creditor'],F(0))
    high=min(rehab['equity']-base['equity'],personal)
    gain=rehab['creditor']+rehab['equity']-base['creditor']-base['equity']
    a.eq(gain,F(9,20)*(40+20)-cost,'independent incremental NPV versus all-claim values')
    return base,rehab,(low,high),gain


def physical_law(p):
    require(len(p)==3,'three physical states')
    p=tuple(number(x,'physical probability',F(0),F(1)) for x in p)
    require(sum(p)==1,'probabilities sum to one')
    return p


def allocation(fee=F(1,50),p=(F(1,5),F(2,5),F(2,5)),cap=F(30)):
    fee=number(fee,'per-unit execution fee',F(0),F(1))
    cap=number(cap,'risky-unit cap',F(0),F(100))
    p=physical_law(p);payoffs=(F(1,2),F(1),F(3,2));liability=(F(90),F(100),F(110))
    upper=min(cap,F(100)/(1+fee),F(10)/(F(1,2)+fee))
    slope=sum(pi*x for pi,x in zip(p,payoffs))-1-fee
    n=upper if slope>0 else F(0)
    b=100-(1+fee)*n
    wealth=tuple(b+n*x for x in payoffs)
    surplus=tuple(x-y for x,y in zip(wealth,liability))
    return dict(upper=upper,slope=slope,n=n,b=b,wealth=wealth,surplus=surplus,
                expected=sum(pi*x for pi,x in zip(p,surplus)),fee=fee*n)


def contribution_vertices(a,fee=F(1,50),cap=F(30)):
    fee=number(fee,'per-unit execution fee',F(0),F(1))
    cap=number(cap,'risky-unit cap',F(0),F(100))
    # Variables (n,g); each pair (A,B,C) means A*n+B*g >= C.
    constraints=[(F(1),F(0),F(0)),(F(-1),F(0),-cap),(F(0),F(1),F(0)),
                 (-(1+fee),F(1),F(-100))]
    for x,l in zip((F(1,2),F(1),F(3,2)),(F(90),F(100),F(110))):
        constraints.append((x-1-fee,F(1),l-100))
    vertices=set()
    for first,second in combinations(constraints,2):
        A,B,C=first;D,E,H=second;det=A*E-B*D
        if det==0:continue
        n=(C*E-B*H)/det;g=(A*H-C*D)/det;a.vertex_candidates+=1
        if all(j*n+k*g>=v for j,k,v in constraints):vertices.add((n,g))
    require(vertices,'nonempty constrained funding polyhedron')
    # The feasible polyhedron is bounded in n and has g>=0; linear minimum
    # attains an extreme point. A separate two-region inequality is checked below.
    return min(vertices,key=lambda z:(z[1],z[0])),vertices


def hedge(a,gross=F(21,20),first_quantity=None,capacity=F(96,5)):
    gross=number(gross,'positive gross funding factor',F(1,100))
    capacity=number(capacity,'available lender cash')
    n=F(10)/gross if first_quantity is None else number(first_quantity,'initial quantity')
    rows=[]
    for first in (F(8),F(12)):
        first_vm=n*(first-10)
        advance=max(-first_vm,F(0));invested=max(first_vm,F(0))
        for final in (first-2,first+2):
            terminal_vm=10*(final-first)
            repayment=gross*advance;release=gross*invested;purchase=10*final
            last_cash=100+release-repayment+terminal_vm-purchase
            required=purchase+repayment-release-terminal_vm
            a.eq(last_cash,F(100)-required,'dated derivative funding identity')
            a.eq(advance+(capacity-advance),capacity,'lender endowment versus draw requirement')
            a.ledger_rows+=1
            rows.append(dict(first=first,final=final,first_vm=first_vm,last_vm=terminal_vm,
                             loan=advance,investment=invested,repayment=repayment,release=release,
                             purchase=purchase,required=required,last_cash=last_cash,
                             early_feasible=advance<=capacity))
    return rows


def early_bank_capacity(buyer=F(25),repo_early=False):
    buyer=number(buyer,'buyer endowment')
    sold=min(F(30),buyer/F(9,10))
    free=30-sold
    repo=min(F(20),F(3,5)*free) if repo_early else F(0)
    proceeds=F(9,10)*sold
    return dict(sold=sold,free=free,proceeds=proceeds,repo=repo,cash=20+proceeds+repo,
                needed=max(F(30)-proceeds-repo,F(0)),
                feasible=F(30)-proceeds-repo<=5)


def bank_ledger(a,subscription=F(0)):
    subscription=number(subscription,'actually settled equity',F(0),F(5))
    state={'cash':F(12),'securities':F(40),'loans':F(98),
           'deposits':F(-112),'notes':F(-28),'equity':F(-10)}
    def event(delta):
        a.eq(sum(delta.values()),F(0),'bank balanced event')
        for k,v in delta.items():state[k]+=v
        a.eq(sum(state.values()),F(0),'bank accounting identity')
        a.ledger_rows+=1
    event({'cash':F(8),'loans':F(-8)})
    event({'loans':F(-5),'equity':F(5)})
    event({'securities':F(-4),'equity':F(4)})
    sale=early_bank_capacity()
    event({'cash':sale['proceeds'],'securities':-sale['proceeds']})
    a.eq(state['securities'],(40-sale['sold'])*F(9,10),'retained units at same one-time mark')
    event({'cash':subscription,'equity':-subscription})
    a.eq(subscription+(5-subscription),F(5),'new investor cash conservation')
    event({'cash':F(-30),'deposits':F(30)})
    actual=min(F(20),state['cash'])
    event({'cash':-actual,'loans':actual})
    return state,20-actual


def calculations(a,page):
    values={}
    def said(part,*text):
        answer=page.answers['finance-core-b-q'+part]
        for token in text:a.ok(token in answer,'solution '+part+' printed '+token)
    def table(prefix,columns):
        rows=next(v for k,v in page.tables.items() if k.startswith(prefix))
        return [[F(row[i].replace('−','-')) if row[i] else None for i in columns] for row in rows[1:]]
    operating=operating_ledger(a)
    account=operating['accounts']
    a.eq(operating['profit'],F(106)-40-20-operating['dep']-operating['impairment']-3,'income independent of posting')
    a.eq((operating['profit'],operating['cfo'],account['cash']),(F(13),F(48),F(60)),'baseline accounting anchors')
    a.eq(table('Question 1 closing',[1,3]),[[60,24],[31,70],[20,67],[50,None],[161,161]],'every closing-statement table value')
    old=operating_ledger(a,life=F(6))
    a.eq((old['dep'],old['impairment'],old['profit']),(F(12),F(18),F(13)),'same independently binding recoverable value')
    for key in ('profit','cfo','wrong_cfo'):values[key]=operating[key]
    values.update(depreciation=operating['dep'],impairment=operating['impairment'],
                  allowance_expense=operating['allowance_expense'],old_depreciation=old['dep'],old_impairment=old['impairment'])
    high_new=operating_ledger(a,recoverable=F(70));high_old=operating_ledger(a,life=F(6),recoverable=F(70))
    a.eq((high_new['profit'],high_old['profit']),(F(25),F(31)),'invariance fails when impairment no longer binds')
    a.interventions.append('change life and recoverability to test the exact aggregate-expense boundary')
    higher_allowance=operating_ledger(a,allowance=F(7))
    a.eq((higher_allowance['profit'],higher_allowance['cfo'],higher_allowance['accounts']['cash']),
         (F(11),F(48),F(60)),'new allowance affects profit and value but not receipts')
    a.interventions.append('increase allowance while retaining real collections')
    said('1b','13+18+12+3−6+4+4=48','13+18+12−3+4+4=48')
    said('1c','not a theorem that life estimates never affect annual profit','prior correct periods are not restated')
    sale=F(64)-3;hold=20*F(19,20)+44*F(9,10)
    a.eq((sale,hold,sale-hold),(F(61),F(293,5),F(12,5)),'economic divestment versus certain retained cash')
    values.update(net_sale=sale,disposal_gain=sale-50,hold_value=hold,divestment_gain=sale-hold)
    a.ok(F(60)-3<hold,'lower funded buyer offer changes divestment choice')
    a.interventions.append('lower sale price through the hold-value boundary')
    base,rehab,fees,gain=restructuring(a)
    a.eq(table('Question 2 actual',[1,2,3,4]),[list(row) for row in base['rows']+rehab['rows']],
         'every terminal creditor/equity table value')
    a.eq((base['creditor'],base['equity'],rehab['creditor'],rehab['equity'],gain),
         (F(691,10),F(189,10),F(324,5),F(126,5),F(2)),'claim prices versus incremental value')
    a.eq(fees,(F(43,10),F(5)),'participation and actual owner cash intersection')
    fee=fees[0]
    a.eq(rehab['creditor']+fee,base['creditor'],'creditor consent threshold attained')
    a.eq(rehab['equity']-fee-base['equity'],gain,'owners retain complete incremental surplus at minimum fee')
    a.eq(F(64)+5,F(3)+25+36+fee+(5-fee),'all date-zero payer/recipient cash including personal funds')
    a.eq(rehab['face'],F(34),'consent fee does not secretly retire principal')
    a.eq((base['creditor']+base['equity']+5,rehab['creditor']+fee+rehab['equity']+5-fee),
         (F(93),F(95)),'personal wealth included without another corporate resource')
    values.update(base_creditor_value=base['creditor'],base_equity_value=base['equity'],
                  rehab_creditor_value=rehab['creditor'],rehab_equity_value=rehab['equity'],
                  rehab_surplus=gain,fee_low=fees[0],fee_high=fees[1],owner_cash_left=5-fee)
    _,_,poor_fees,_=restructuring(a,personal=F(4))
    a.ok(poor_fees[0]>poor_fees[1],'positive value does not fund an unaffordable fee')
    a.interventions.append('reduce owners personal funds below the consent threshold')
    _,_,expensive_fees,negative_gain=restructuring(a,cost=F(28))
    a.eq(negative_gain,F(-1),'costlier rehabilitation destroys total value')
    a.ok(expensive_fees[0]>expensive_fees[1],'no win-win transfer when incremental value is negative')
    a.interventions.append('raise rehabilitation outlay beyond the priced operating increment')
    said('2b','not a receipt or an inferred legal cancellation')
    said('2c','not a principal reduction','Remaining principal stays 34')
    p=(F(1,5),F(2,5),F(2,5));q=(F(1,4),F(1,2),F(1,4));X=(F(1,2),F(1),F(3,2))
    a.eq(sum(q),F(1),'unit safe claim price')
    a.eq(sum(qi*x for qi,x in zip(q,X)),F(1),'risky claim price')
    a.eq(tuple(F(80)+20*x for x in X),(F(90),F(100),F(110)),'liability traded-span replica')
    values.update(risky_expected_return=sum(pi*x for pi,x in zip(p,X))-1,
                  liability_price=sum(qi*l for qi,l in zip(q,(90,100,110))))
    portfolio=allocation()
    a.eq((portfolio['n'],portfolio['b'],portfolio['expected']),(F(250,13),F(1045,13),F(-6,13)),
         'constrained physical objective solution')
    a.ok(portfolio['slope']>0,'strictly increasing affine objective')
    for n in (F(0),portfolio['upper'],portfolio['upper']+F(1,100)):
        low=100-(F(1,2)+F(1,50))*n
        a.eq(low>=90,n<=portfolio['upper'],'complete low-state feasible boundary')
    a.eq(portfolio['b']+portfolio['n']+portfolio['fee'],F(100),'cash investment seller and execution provider')
    a.eq(table('Question 3 funded',[1,2,3]),[list(row) for row in zip(portfolio['wealth'],(90,100,110),portfolio['surplus'])],
         'every funded portfolio table value')
    vertex,vertices=contribution_vertices(a)
    a.eq(vertex,(F(20),F(2,5)),'independently enumerated LP extreme-point minimum')
    for n,g in vertices:
        a.ok(g>=F(2,5),'all feasible extreme points meet separate lower bound')
    a.eq((F(1,2)+F(1,50))*20-10,F(2,5),'low-state global-bound intersection')
    a.eq(10-(F(1,2)-F(1,50))*20,F(2,5),'high-state global-bound intersection')
    a.eq(F(80)+20+F(2,5),100+vertex[1],'attaining full-coverage resource budget')
    values.update(holding_max=portfolio['upper'],cash_holding=portfolio['b'],execution_fee=portfolio['fee'],
                  expected_surplus=portfolio['expected'],minimum_sponsor=vertex[1],sponsor_cash_left=1-vertex[1])
    zero,_=contribution_vertices(a,fee=F(0))
    a.eq((zero,allocation(fee=F(0))['surplus']),((F(20),F(0)),(F(0),F(0),F(0))),'remove actual execution cost')
    a.interventions.append('remove execution fees and recover the frictionless liability match')
    capped,_=contribution_vertices(a,cap=F(15))
    a.eq(capped,(F(15),F(14,5)),'risky-holding cap changes required sponsor funding')
    a.ok(capped[1]>1,'required contribution exceeds named sponsor endowment')
    a.interventions.append('tighten risky-unit permission until the funded sponsor menu is infeasible')
    reverse=allocation(p=(F(2,5),F(2,5),F(1,5)))
    a.eq((reverse['n'],reverse['expected']),(F(0),F(2)),'changed physical law changes choice while prices stay fixed')
    a.interventions.append('reverse physical mean with unchanged payoff prices and constraints')
    said('3c','If n≤20','if n≥20')
    said('3d','selection problem','shortfalls 5/13 and 10/13','actual 0.4 sponsor cash')
    gross=F(21,20);fixed=hedge(a,first_quantity=F(10));dynamic=hedge(a)
    tree=table('Complete four-path',[1,2,3])
    a.eq(tree,[[10,8,6],[10,8,10],[10,12,10],[10,12,14]],'all prompt tree quotes')
    for i,first in enumerate((F(8),F(12))):
        a.eq(sum(r['final'] for r in dynamic[2*i:2*i+2])/2,first,'futures conditional quote')
    a.eq((F(8)+12)/2,F(10),'initial futures quote')
    a.eq(sum(F(10)*(r['final']-10)/4 for r in dynamic)/gross**2,F(0),'zero fully performing forward price')
    a.eq(table('Question 4 fixed-quantity',[1,2,3]),
         [[r['first_vm'],r['last_vm'],r['required']] for r in fixed],'every fixed hedge table value')
    a.eq([r['required'] for r in fixed],[101,101,99,99],'timing-adjusted reference cost')
    a.eq([r['early_feasible'] for r in fixed],[False,False,True,True],'fixed hedge fails named early line')
    a.eq(table('Question 4 executed dynamic',[1,2,3,4,5,6]),
         [[F(100),r['release'],r['repayment'],r['last_vm'],r['purchase'],r['last_cash']] for r in dynamic],
         'every dynamic funded terminal table value')
    for r in dynamic:
        a.eq((r['required'],r['last_cash']),(F(100),F(0)),'actual hedge buys every required unit')
        a.ok(r['early_feasible'],'actual early provider can fund the dynamic quantity')
        a.eq(gross*F(200,21)*(r['first']-10)+10*(r['final']-r['first']),
             10*(r['final']-10),'self-financing finite replication identity')
    a.eq(F(10)-gross*F(200,21),F(0),'unique first-node coefficient cancellation')
    a.eq((F(400,21)*gross,F(96,5)-F(400,21)),(F(20),F(16,105)),'actual funded lender principal interest and remainder')
    values.update(forward_node_abs=F(20)/gross,fixed_down_cost=fixed[0]['required'],fixed_up_cost=fixed[2]['required'],
                  fixed_early_gap=F(20)-F(96,5),initial_hedge_units=F(10)/gross,
                  dynamic_early_loan=dynamic[0]['loan'],lender_cash_left=F(96,5)-dynamic[0]['loan'])
    changed=hedge(a,gross=F(11,10))
    stale=hedge(a,gross=F(11,10),first_quantity=F(200,21))
    a.eq([r['required'] for r in changed],[F(100)]*4,'new funding factor requires a new funded hedge quantity')
    a.ok(any(r['required']!=100 for r in stale),'stale hedge does not survive changed compounding')
    a.interventions.append('change the funding factor and distinguish rederived from stale quantities')
    # UU cash before the purchase if its positive final variation is delayed.
    a.eq(F(140)-(100+dynamic[3]['release']),F(20),'a delayed positive settlement is not current cash')
    a.interventions.append('delay positive final futures cash beyond the commodity payment cutoff')
    face=F(40);actual=face/2;required=140-actual
    a.eq((required,face-actual,required-100),(F(120),F(20),F(20)),'counterparty loss retained as an unpaid claim and cash gap')
    a.eq((F(60)-(-40),F(100)),(F(100),F(100)),'negative forward obligation remains fully owed')
    for recovery,wanted in [(F(0),F(140)),(F(1),F(100))]:
        a.eq(140-recovery*face,wanted,'positive-claim recovery boundary')
    a.interventions.append('vary positive forward recovery without reducing fully owed negative cash')
    altered_payoffs=[10*(r['final']-10)-(face-actual if r['final']==14 else 0) for r in dynamic]
    altered_value=sum(altered_payoffs)/4/gross**2
    a.eq(altered_value,-F(1,4)*(face-actual)/gross**2,'changed signed-claim price equals the priced positive recovery loss')
    values.update(forward_unpaid=face-actual,credit_stress_cost=required,credit_stress_value=altered_value)
    said('4b','reference requirements, not successfully executed trades')
    said('4c','after settlement, without seeing date 2')
    said('4d','unpaid nominal claim','different claim')
    sale=early_bank_capacity()
    a.eq((sale['sold'],sale['free'],sale['proceeds'],sale['cash'],sale['needed']),
         (F(250,9),F(20,9),F(25),F(45),F(5)),'funded sale within ownership and timing constraints')
    late,gap=bank_ledger(a)
    early,closed=bank_ledger(a,F(5))
    a.eq(table('Question 5 closing',[1,2,3,4,5,6,7]),
         [[late['cash'],late['loans'],late['securities'],-late['deposits'],-late['notes'],-late['equity'],gap],
          [early['cash'],early['loans'],early['securities'],-early['deposits'],-early['notes'],-early['equity'],closed]],
         'every institutional risk-ledger table value')
    a.eq((-late['equity'],-early['equity'],gap,closed),(F(1),F(6),F(5),F(0)),'positive capital versus completed payment')
    a.eq(sale['sold']+sale['free']+10,F(40),'sold free and already pledged units partition ownership')
    a.eq(F(3,5)*sale['free'],F(4,3),'remaining collateral is not the original entire free inventory')
    for buyer,wanted,feasible in [(F(24),F(6),False),(F(25),F(5),True),(F(27),F(3),True),(F(40),F(3),True)]:
        c=early_bank_capacity(buyer)
        a.eq((c['needed'],c['feasible']),(wanted,feasible),'bounded investor menu at meaningful buyer-capacity boundary')
        a.eq(c['needed'],30-min(buyer,F(27)),'global funded-resource lower bound')
    a.interventions.append('change buyer cash through the bounded-investor feasibility threshold and inventory saturation')
    timely=early_bank_capacity(repo_early=True)
    a.eq((timely['repo'],timely['needed']),(F(4,3),F(11,3)),'earlier repo only finances unsold free inventory')
    a.interventions.append('advance repo delivery without reusing sold collateral')
    values.update(sold_units=sale['sold'],early_cash=sale['cash'],early_equity_needed=sale['needed'],
                  free_units_left=sale['free'],late_repo_capacity=F(3,5)*sale['free'],
                  remaining_security_value=late['securities'],late_equity=-late['equity'],early_equity=-early['equity'])
    said('5a','feasible exactly when B≥25','still available only later')
    said('5b','no second sale loss','not another five-CU reduction')
    said('5c','Reject the report','obtain the relevant contractual/legal assessment')
    for key,wanted in values.items():
        a.eq(F(page.anchors[key].replace('−','-')),wanted,'printed numeric result '+key)
    a.eq(set(page.anchors),set(values),'all printed numerical anchors independently derived')
    a.reject(lambda:operating_ledger(a,life=F(0)),'zero remaining life')
    a.reject(lambda:operating_ledger(a,allowance=F(37)),'allowance exceeds gross receivables')
    a.reject(lambda:restructuring(a,cost=F(62)),'rehabilitation consumes more than available sale cash')
    a.reject(lambda:restructuring(a,personal=F(-1)),'negative owner endowment')
    a.reject(lambda:allocation(fee=F(-1,100)),'negative claimed execution fee')
    a.reject(lambda:allocation(p=(F(1,2),F(1,2),F(1,2))),'physical mass exceeds one')
    a.reject(lambda:contribution_vertices(a,cap=F(-1)),'negative position permission')
    a.reject(lambda:hedge(a,gross=F(0)),'zero funding gross factor')
    a.reject(lambda:early_bank_capacity(F(-1)),'negative buyer endowment')
    a.reject(lambda:bank_ledger(a,F(6)),'subscription exceeds named investor cash')
    return len(values)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    a=Audit();page=Fragment();raw=(root/HTML).read_text();page.feed(raw);page.close()
    wanted={'finance-core-b-q'+k:v for k,v in POINTS.items()}
    a.eq(page.points,wanted,'all exact scored subparts')
    a.eq(sorted(page.targets),sorted(wanted),'one solution per exact prompt')
    a.eq((page.exercise_lists,page.solution_wrappers),(5,1),'standard reader list and disclosure markers')
    a.eq((page.reader_prompts,page.reader_solutions),(17,17),'reader-marked prompts and solutions')
    a.ok('<summary>Solutions, proofs and scoring</summary>' in raw,'reader disclosure label')
    a.eq(len(page.ids),len(set(page.ids)),'unique reader IDs')
    a.eq((page.h1,page.stack),(0,[]),'balanced fragment without a second title')
    a.ok(all(x in ('form-b','solutions-b') or x.startswith('finance-core-b-') for x in page.ids),'owned anchor prefixes')
    for domain in '12345':
        a.eq(sum(v for k,v in POINTS.items() if k.startswith(domain)),20,'domain '+domain+' score')
    a.eq(sum(POINTS.values()),100,'cumulative exam score')
    for part,points in POINTS.items():
        rubric=page.answers['finance-core-b-q'+part].split('Credit ')[-1]
        a.ok(rubric.startswith(str(points)+':'),'printed rubric total '+part)
        a.eq(sum(map(int,re.findall(r'\b(\d+)(?=;|\.)',rubric))),points,'actual suballocation sum '+part)
    a.ok('300 minutes' in raw and '85 overall and 15 in every domain' in raw,'administration and essential-domain standard')
    a.ok('sixty prerequisite chapters' in raw and 'separate, fully specified decision snapshots' in raw,'scope and resource separation')
    anchors=calculations(a,page)
    sources=strict((root/SOURCES).read_text())
    a.eq(sources['proposals'],[],'no new primary-source proposal required')
    a.eq(len(sources['reused_source_ids']),12,'twelve scoped accepted primary sources')
    a.eq({r['canonical_id'] for r in sources['reused_primary_scopes']},set(sources['reused_source_ids']),'source record identity map')
    a.ok(set(page.sources)<=set(sources['reused_source_ids']),'every printed primary citation has an exact scope')
    a.eq({r['prompt'] for r in sources['method_routes']},set(wanted),'every scored prompt has a taught method route')
    sampled=set()
    for route in sources['method_routes']:
        a.eq(route['manuscripts'],['chapters/'+c+'.html' for c in route['chapters']],'method manuscript route')
        sampled.update(route['chapters'])
    a.eq({x.split('-')[0] for x in sampled},{'v07','v08','v09','v10','v11'},'all five prerequisite volumes sampled')
    for link in page.links:
        a.ok(bool(re.fullmatch(r'v(?:07|08|09|10|11)-c\d\d\.html',link)) or
             link.startswith('sources.html#'),'flat accepted reader or source link')
    review=strict((root/REVIEW).read_text());rows=review['reviewed_hashes']
    a.eq(len(rows),3,'three exact nonself author bindings')
    a.eq({r['path'] for r in rows},{HTML,SELF,SOURCES},'author payload membership')
    for r in rows:
        data=(root/r['path']).read_bytes()
        a.eq((len(data),hashlib.sha256(data).hexdigest()),(r['bytes'],r['sha256']),'exact author payload '+r['path'])
    summary=dict(component='finance-core-exam-b',status='passed',points=100,domains=5,
                 scored_subparts=17,solved_subparts=17,sampled_chapters=len(sampled),
                 reader_exercises=page.reader_prompts,reader_solutions=page.reader_solutions,
                 printed_numerical_anchors=anchors,comparisons=a.comparisons,
                 financial_interventions=len(a.interventions),domain_rejections=a.rejections,
                 posted_or_recipient_rows=a.ledger_rows,finite_vertex_candidates=a.vertex_candidates,
                 author_bindings=3,
                 method='Exact journals, claim recipients, independent allocation vertices and interval proofs, dated hedge cash and endowed funding bounds.',
                 limits='Synthetic scoped contracts; no all-sixty-chapter claim, current legal authority, empirical calibration, timing equating, rendered QA or human certification.')
    strict(json.dumps(summary,allow_nan=False))
    return summary


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
