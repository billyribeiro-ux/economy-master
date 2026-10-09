"""Separate Form A peer: original-contract calculations, not author oracles.

Uses integer applicant cohorts, individual deposits and claims, ranked equiprobable
loss atoms, elimination of borrowing intervals, and complete recipient wallets.
check() is quiet, read-only, strict-JSON-safe and portable with six frozen files.
"""
import contextlib
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
from math import isqrt
from pathlib import Path
import re

AUTHOR = ['content/assessments/parts/v11-exam-a.html','scripts/check_v11_exam_a.py',
          'content/reviews/v11-exam-a-author.json','content/reviews/v11-exam-a-sources.json']
SELF = 'scripts/check_v11_exam_a_peer.py'
REVIEW = 'content/reviews/v11-exam-a-peer.json'
POINTS = {'1a':6,'1b':8,'1c':6,'2a':5,'2b':4,'2c':7,'2d':4,'3a':8,'3b':6,'3c':6,
          '4a':6,'4b':4,'4c':6,'4d':4,'5a':4,'5b':7,'5c':4,'5d':5}


def require(ok,label):
    if not ok: raise ValueError('V11 Form A peer: '+label)


class Audit:
    def __init__(self):
        self.comparisons=0;self.interventions=[];self.rejections=0;self.allocations=0
    def eq(self,actual,expected,label):
        self.comparisons+=1
        require(actual==expected,label+': '+repr(actual)+' != '+repr(expected))
    def ok(self,value,label):
        self.eq(bool(value),True,label)
    def reject(self,function,label):
        try: function()
        except ValueError: self.rejections+=1
        else: raise ValueError('expected rejection: '+label)
    def intervention(self,name):
        self.interventions.append(name)


def strict(text):
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'duplicate JSON key')
            result[k]=v
        return result
    def bad(v): raise ValueError('nonfinite JSON '+v)
    return json.loads(text,object_pairs_hook=pairs,parse_constant=bad)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids=[];self.points={};self.answers={};self.prompts={};self.targets=[]
        self.links=[];self.h1=0;self.active=None;self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        x=dict(attrs)
        if 'id' in x:self.ids.append(x['id'])
        if tag=='h1':self.h1+=1
        if tag=='a':self.links.append(x.get('href',''))
        if 'data-points' in x:
            require(tag=='li' and x['id'] not in self.points,'unique scored li')
            self.points[x['id']]=int(x['data-points']);self.prompts[x['id']]='';self.active=(self.prompts,x['id'])
        if 'data-solution-for' in x:
            target=x['data-solution-for'];self.targets.append(target);self.answers[target]='';self.active=(self.answers,target)
        if tag=='table':
            self.table=[];self.tables.append(self.table)
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append(tag)
    def handle_data(self,text):
        if self.active is not None:
            mapping,key=self.active;mapping[key]+=text
        if self.cell is not None:self.cell+=text
    def handle_endtag(self,tag):
        require(bool(self.stack) and self.stack[-1]==tag,'balanced fragment '+tag);self.stack.pop()
        if tag in ('th','td'):self.row.append(self.cell.strip());self.cell=None
        if tag=='tr':self.table.append(self.row);self.row=None
        if tag=='table':self.table=None
        if tag=='li':self.active=None


def screen(fee):
    require(fee>=0,'nonnegative testing cost')
    # Twelve applicants reproduce the exact population: six pass-G, one pass-B,
    # two fail-G, three fail-B. Cost is charged to every applicant exactly once.
    cohort=[('G',True)]*6+[('B',True)]+[('G',False)]*2+[('B',False)]*3
    payoff={'G':F(24),'B':F(8)}
    chosen=[kind for kind,passed in cohort if passed]
    return dict(pass_mass=F(len(chosen),len(cohort)),posterior=F(chosen.count('G'),len(chosen)),
                receipt=sum(payoff[k] for k in chosen)/len(chosen),
                screened=sum((payoff[k]-20 if passed else F(0))-fee for k,passed in cohort)/len(cohort),
                all_lend=sum(payoff[k]-20 for k,_ in cohort)/len(cohort))


def bank_ledger(a):
    assets=dict(cash=F(6),existing_loans=F(54),new_loan=F(0),securities=F(20))
    deposits=dict(other=F(60),borrower=F(0),input_seller=F(0))
    debt=dict(old=F(10),new=F(0));equity=F(10);investor_cash=F(7);rows=[]
    def snapshot():
        row=[assets['cash'],assets['existing_loans']+assets['new_loan'],assets['securities'],
             sum(deposits.values()),sum(debt.values()),equity]
        a.eq(sum(row[:3]),sum(row[3:]),'individual-account bank identity')
        return row
    assets['cash']-=F(2,5);equity-=F(2,5);rows.append(snapshot())
    assets['new_loan']+=20;deposits['borrower']+=20;rows.append(snapshot())
    advance=12-assets['cash'];investor_cash-=advance;assets['cash']+=advance;debt['new']+=advance
    a.ok(investor_cash>=0,'investor pays from actual endowment');rows.append(snapshot())
    assets['cash']-=12;deposits['borrower']-=12;rows.append(snapshot())
    a.eq((deposits['borrower'],sum(deposits.values()),assets['cash']),(F(8),F(68),F(0)),'retained borrower deposit exists')
    # The actual clarified purchase moves ownership inside the bank, not reserves.
    deposits['input_seller']+=deposits['borrower'];deposits['borrower']=F(0)
    a.eq((sum(deposits.values()),assets['cash']),(F(68),F(0)),'internal purchase preserves bank cash and deposits')
    impairment=assets['new_loan']-8;assets['new_loan']=F(8);equity-=impairment
    marked=snapshot()
    assets['cash']+=8;assets['new_loan']-=8
    recovered=snapshot()
    a.eq(marked[5],recovered[5],'external collection is not another income loss')
    a.eq((assets['cash'],sum(deposits.values()),deposits['borrower']),(F(8),F(68),F(0)),
         'external service collection cannot also cancel a spent borrower deposit')
    a.eq(investor_cash+debt['new'],F(7),'investor cash plus new claim reconciles')
    # Counterfactual repayment by canceling an unspent deposit would reduce the
    # bank liability and loan but supply no reserves; it is not this prompt.
    a.eq((F(0),F(68)-8),(F(0),F(60)),'hypothetical deposit setoff has different cash and deposits')
    a.intervention('distinguish external service receipt from a counterfactual deposit setoff')
    return rows,advance,marked,recovered


def ranked_tail(alpha):
    require(0<alpha<1 and (alpha*20).denominator==1,'supported finite replicated-tail boundary')
    atoms=[F(0)]*11+[F(4)]*6+[F(24)]*3
    k=int(alpha*20)
    return atoms[k-1],sum(atoms[k:])/len(atoms[k:])


def funding(x,b,late=False):
    require(x>=0 and b>=0,'nonnegative funding')
    first=F(5)+2+x+(F(0) if late else b)-13
    last=first+10+(b if late else F(0))-6-F(11,10)*b
    return first,last


def minimum_capital(cap,late=False):
    require(cap>=0,'nonnegative borrowing capacity')
    if late:return F(6),(F(0),min(cap,F(40)))
    # Eliminate b from max(0,6-x)<=b<=min(cap,10(x-2)). Every lower bound
    # must not exceed every upper bound; these finite pairwise conditions suffice.
    x=max(F(0),F(2),F(6)-cap,F(26,11))
    return x,(max(F(0),6-x),min(cap,10*(x-2)))


def incident(second_payee='r',recovery=F(3)):
    require(second_payee in ('r','s') and recovery>=0,'supported payment identities')
    outstanding={'r':F(7),'s':F(5),'t':F(8)}
    cash=F(22);discharged=F(0);mistaken=F(0)
    for ident,amount in [('r',F(7)),(second_payee,F(5)),('t',F(8))]:
        cash-=amount
        valid=min(amount,outstanding[ident]);outstanding[ident]-=valid
        discharged+=valid;mistaken+=amount-valid
    require(recovery<=mistaken,'recovery cannot exceed the actual mistaken transfer')
    liabilities=F(90)-discharged;assets=cash+80+recovery
    return dict(cash=cash,discharged=discharged,outstanding=outstanding,recovery=recovery,
                loss=mistaken-recovery,assets=assets,liabilities=liabilities,equity=assets-liabilities,
                gap=max(sum(outstanding.values())-cash,F(0)))


def insurance(probability,premium):
    require(0<=probability<=1 and 0<=premium<=100,'insurance probability and positive-wealth domain')
    uninsured=(1-probability)*10+probability*8
    # Squaring preserves the preference comparison because both sides are nonnegative.
    certainty_square=100-premium
    choices=['buy'] if certainty_square>uninsured**2 else (['decline'] if certainty_square<uninsured**2 else ['buy','decline'])
    return 100-uninsured**2,choices


def exporter(spot,conversion_cap=F(8),transfer_cap=F(12)):
    require(spot>0 and conversion_cap>=0 and transfer_cap>=0,'currency quotation and cap domain')
    on_F=F(12);on_H=F(0);off_H=F(4)
    converted=min(on_F,conversion_cap);on_F-=converted;on_H+=converted*spot
    moved=min(on_H,transfer_cap);on_H-=moved;off_H+=moved
    return dict(converted_F=converted,converted_H=converted*spot,transferred=moved,
                on_F=on_F,on_H=on_H,off_H=off_H,gap=max(F(24)-off_H,F(0)),
                translated=on_F*spot+on_H+off_H)


def square_root(x):
    require(x>=0,'nonnegative perfect-square teaching input')
    n,d=isqrt(x.numerator),isqrt(x.denominator)
    require(n*n==x.numerator and d*d==x.denominator,'exact-square domain for this bounded oracle')
    return F(n,d)


def sale_interval(advance):
    require(0<=advance<=4,'funded remaining auction target')
    # R(q)=4-(q-8)^2/16, so R(q)>=4-advance on 0<=q<=8 iff
    # q>=8-4sqrt(advance). This derives a feasible interval, not just a root.
    return max(F(0),8-4*square_root(advance)),F(8)


def intervention_wallet(value,escrow):
    require(value>=0 and escrow>=0,'nonnegative terminal payoff and actual escrow')
    pockets=dict(A=F(2),buyer=F(4),provider=F(1),private=escrow,creditor=F(0),owner=F(0))
    locked=F(0)
    def move(source,target,amount):
        require(0<=amount<=pockets[source],'funded transfer '+source)
        pockets[source]-=amount;pockets[target]+=amount
    move('provider','A',F(1));move('buyer','A',F(3));move('A','creditor',F(6))
    locked=escrow;pockets['private']-=escrow
    # The buyer owns four sold units; the pledge includes only four retained units.
    pockets['buyer']+=4*value;pockets['A']+=4*value
    collateral=pockets['A'];base=min(F(5,4),collateral)
    move('A','provider',base);owner=pockets['A'];move('A','owner',owner)
    topup=min(locked,F(5,4)-base);locked-=topup;pockets['provider']+=topup
    pockets['private']+=locked
    return dict(collateral=collateral,base=base,topup=topup,refund=locked,owner=owner,
                receipt=pockets['provider'],principal_loss=F(1)-pockets['provider'],
                contractual_shortfall=F(5,4)-base,buyer_wealth=pockets['buyer'],
                recipients=sum(pockets.values()),resources=F(7)+escrow+8*value)


def calculations(a,page):
    def said(part,*tokens):
        text=page.answers['v11-a-q'+part]
        for token in tokens:a.ok(token in text,'printed solution '+part+' '+token)
    result=screen(F(2,5))
    a.eq(result,dict(pass_mass=F(7,12),posterior=F(6,7),receipt=F(152,7),screened=F(3,5),all_lend=F(-4,3)),
         'integer applicant cohort versus exam values')
    a.eq(result['pass_mass']*(result['receipt']-20)-F(2,5),result['screened'],'conditional versus applicant margin')
    a.eq(screen(F(1))['screened'],F(0),'testing-cost indifference')
    a.ok(screen(F(11,10))['screened']<0,'more expensive testing changes policy value')
    a.intervention('test cost crosses the applicant-level break-even value')
    said('1a','7/12','6/7','152/7','3/5 CU','−4/3','rejecting without testing gives zero')
    rows,advance,marked,recovered=bank_ledger(a)
    ledger=next(t for t in page.tables if t[0][0]=='After event')
    a.eq([[F(x) for x in row[1:]] for row in ledger[1:]],rows,'every printed balance-sheet cell')
    a.eq((advance,marked[-1],sum(marked[:3])),(F(32,5),F(-12,5),F(82)),'actual funding and impairment')
    a.eq((F(8,24),24-8,20-8),(F(1,3),16,12),'service gap versus carrying-value loss')
    a.ok('changes deposit ownership but neither aggregate bank deposits nor cash' in page.prompts['v11-a-q1c'],
         'prior internal input purchase explicit')
    a.ok('service cash now arrives from outside this bank' in page.prompts['v11-a-q1c'],'external repayment route explicit')
    said('1b','32/5=6.4','422/5=84.4','due at date 3')
    said('1c','−12/5=−2.4','four-CU difference','remains a legal claim','not a second twelve-CU expense')
    a.eq(ranked_tail(F(3,4)),(F(4),F(16)),'twenty equally likely atoms; upper five observations')
    a.eq(F(6*4+3*24,9),F(32,3),'all-quantile-atom conditional mean is different')
    a.eq(ranked_tail(F(17,20)),(F(4),F(24)),'boundary alpha can leave VaR below worst tail')
    a.intervention('move quantile to the end of the middle atom')
    said('2a','ten of the thirty percentage points','one third','32/3')
    cap=min(F(12-4)*F(9,10)*(1-F(1,4)),F(6))
    a.eq(cap,F(27,5),'unpledged inventory and funded lender capacity')
    capital,interval=minimum_capital(cap)
    a.eq((capital,interval),(F(26,11),(F(40,11),F(40,11))),'borrowing interval collapses at unique minimum')
    a.eq(funding(capital,interval[0]),(F(0),F(0)),'both dated obligations actually funded')
    a.eq(F(11,10)*interval[0],F(4),'principal plus interest repaid')
    a.eq(funding(F(3,5),cap),(F(0),F(-97,50)),'maximum borrowing with early-only capital fails')
    a.eq(funding(F(127,50),cap)[1],F(0),'maximum draw needs more capital')
    lower=capital-F(1,100)
    a.ok(max(F(0),6-lower)>min(cap,10*(lower-2)),'lower capital has no feasible draw, not just a bad guessed draw')
    a.eq(minimum_capital(F(2)),(F(4),(F(2),F(2))),'lower funded loan capacity binds')
    a.intervention('reduce cash-backed borrowing capacity below the intersection')
    a.eq(minimum_capital(cap,True)[0],F(6),'delayed facility cannot cover the first cutoff')
    a.eq(funding(F(6),F(0),True),(F(0),F(4)),'minimum delayed-policy feasible ledger')
    a.eq(funding(F(6),F(1),True),(F(0),F(39,10)),'late same-cutoff draw pays stated interest and supplies no early cash')
    a.intervention('delay actual delivery while retaining repayment terms')
    said('2b','x+b−6','x−2−b/10')
    said('2c','40/11','26/11','−97/50','127/50','global minimality')
    said('2d','x≥6','zero, then four')
    operational=incident()
    a.eq(operational,dict(cash=F(2),discharged=F(15),outstanding={'r':F(0),'s':F(5),'t':F(0)},
         recovery=F(3),loss=F(2),assets=F(85),liabilities=F(75),equity=F(10),gap=F(3)),'individual claim discharge and recovery')
    corrected=incident('s',F(0))
    a.eq((corrected['equity'],corrected['gap'],corrected['liabilities']),(F(12),F(0),F(70)),
         'paying the right beneficiary changes discharge without changing aggregate cash sent')
    a.intervention('route the mistaken transfer to its actual unpaid obligation')
    a.eq((incident(recovery=F(0))['loss'],incident(recovery=F(5))['loss']),(F(5),F(0)),'recovery changes loss severity')
    a.eq((incident(recovery=F(0))['gap'],incident(recovery=F(5))['gap']),(F(3),F(3)),'late recovery value never closes the first gap')
    a.intervention('change recovery value while keeping the recovery date late')
    losses=[(0,1,0),(7,2,2),(2,8,0)]
    table=next(t for t in page.tables if t[0][0]=='State')
    a.eq([tuple(int(x) for x in row[1:]) for row in table[1:]],losses,'all supplied joint scenario rows')
    totals=[sum(row) for row in losses]
    a.eq((totals,12-max(totals),sum(max(r[j] for r in losses) for j in range(3))),([1,11,10],1,17),'joint-state maxima differ from component maxima')
    a.eq((7+2+2+5)-totals[1],5,'gross payment and net loss duplicated by five')
    a.eq(operational['equity']-7-2,1,'stress incident reconciliation')
    said('3a','Deleting s would overstate equity by five','Collecting three at cutoff 2')
    said('3b','overstatement of five','not another asset loss')
    said('3c','immutable obligation register','shared identity/authorization service','three achievements','trigger')
    low,choice_low=insurance(F(1,10),F(10));high,choice_high=insurance(F(2,5),F(10))
    a.eq((low,high,choice_low,choice_high),(F(99,25),F(384,25),['decline'],['buy']),'exact certainty equivalent and buyer choice')
    a.eq(insurance(F(1,10),low)[1],['buy','decline'],'participation indifference is not forced buying')
    a.eq(insurance(F(1,10),low-F(1,100))[1],['buy'],'lower premium changes pool participation')
    a.intervention('test exact participation tie and a premium just below it')
    profits=[]
    for claim in (F(0),F(36)):
        end=F(26)+10-claim
        a.ok(end>=0,'funded seller can perform either state')
        a.eq(end+claim,F(36),'insurance cash allocation')
        profits.append(end-26);a.allocations+=1
    a.eq(F(3,5)*profits[0]+F(2,5)*profits[1],F(-22,5),'issued-policy expectation over selected buyers')
    a.eq(F(10)-F(1,4)*36,F(1),'original mixed pool gives a different unimplemented profit')
    said('4a','40p−4p²','99/25=3.96','384/25=15.36','entry equilibrium')
    said('4b','−22/5=−4.4','profit one','36 cash','−26 or ten')
    for spot,wanted in [(F(2),(16,4,4,16,8,28)),(F(3),(24,4,12,16,8,40))]:
        f=exporter(spot)
        a.eq(tuple(f[k] for k in ('converted_H','on_F','on_H','off_H','gap','translated')),tuple(map(F,wanted)),'exporter currency pockets')
        a.eq(f['translated'],12*spot+4,'translation conservation before any payment')
        a.ok(f['translated']>24 and f['off_H']<24,'value solvency and execution access differ')
        a.allocations+=1
    partial=exporter(F(2),transfer_cap=F(20));full=exporter(F(2),F(12),F(20))
    a.eq((partial['gap'],full['gap']),(F(4),F(0)),'relaxing only one currency constraint can leave the other binding')
    a.intervention('relax transfer permission then conversion permission with actual currency conserved')
    said('4c','four H plus four F','28 H','No partial payment')
    said('4d','twelve H plus four F','forty H','gap is still eight H')
    routes=[('direct',F(4),F(8),F(8)),('routed',F(5),F(4),F(18))]
    for measure,choice in ((2,'routed'),(3,'direct')):
        admitted=[r for r in routes if r[measure]<=10]
        a.eq(max(admitted,key=lambda r:r[1])[0],choice,'private choice from real retained exposure screen')
    a.eq(sale_interval(F(0)),(F(8),F(8)),'unaided feasible set is singleton at maximum revenue')
    a.eq(sale_interval(F(1)),(F(4),F(8)),'assisted full feasible interval before minimum selection')
    for quantity in (F(399,100),F(4),F(6),F(8)):
        proceeds=quantity*(1-quantity/16)
        a.eq(proceeds,F(4)-(quantity-8)**2/16,'completed-square revenue identity')
        a.eq(proceeds>=3,quantity>=4,'payment feasibility does not mean every feasible quantity is minimum')
        a.ok(proceeds<=4,'announced sale fits buyer cash')
    a.ok('smallest quantity that covers' in (page.prompts['v11-a-q5b']+' '+page.raw), 'minimum-sale rule exists')
    a.ok('minimum is unique' in page.prompts['v11-a-q5b'],'exact prompt asks for unique minimum')
    for advance,sale,expected_margin,expected_gap in [(F(0),F(8),F(2),F(1)),(F(1),F(4),F(0),F(0))]:
        price=1-sale/16;proceeds=sale*price
        a.eq(2+advance+proceeds,F(6),'issuer creditor funded by named cash providers')
        call=max(F(6)-8*price,F(0));gap=max(call-F(1),F(0))
        a.eq((call,gap),(expected_margin,expected_gap),'distinct downstream collateral call')
        a.eq(sale+(8-sale),F(8),'sold and pledgeable inventory partition')
        a.allocations+=1
    said('5a','social welfare','anticipated continuing rescue')
    said('5b','payment-feasible set is [4,8]','four securities','buyer pays three','uncovered need is one')
    minimum=F(1)-4*F(1,5)-F(3,20)
    a.eq(minimum,F(1,20),'necessary external escrow for principal-loss limit')
    for value,expected in [(F(1),(F(5,4),F(-1,4),F(11,4),F(0))),
                           (F(1,5),(F(4,5),F(1,5),F(0),F(9,20)))]:
        row=intervention_wallet(value,F(0))
        a.eq(tuple(row[k] for k in ('receipt','principal_loss','owner','contractual_shortfall')),expected,'limited-recourse payout')
        a.eq(row['recipients'],row['resources'],'full creditor/buyer/provider/owner cash identity')
        funded=intervention_wallet(value,minimum)
        a.eq(funded['recipients'],funded['resources'],'separate private escrow also included in complete system')
        a.ok(funded['principal_loss']<=F(3,20),'funded escrow meets both specified states')
        a.allocations+=2
    a.eq(intervention_wallet(F(1),minimum)['refund'],minimum,'good-state escrow owner gets actual refund')
    a.eq(intervention_wallet(F(1,5),minimum)['receipt'],F(17,20),'bad-state receipt at the hard limit')
    a.ok(intervention_wallet(F(1,5),minimum-F(1,1000))['principal_loss']>F(3,20),'strictly underfunded escrow fails')
    a.intervention('move actual escrow just below its necessary threshold')
    oversized=intervention_wallet(F(1,5),F(3,5))
    a.eq((oversized['receipt'],oversized['refund']),(F(5,4),F(3,20)),'excess escrow is not an extra provider windfall')
    a.eq(oversized['recipients'],oversized['resources'],'excess escrow refunds preserve all recipients')
    a.intervention('fund excess escrow and apply promised-payment cap and refund')
    said('5c','9/20=0.45','principal shortfall 1/5','unpaid promised interest 1/4','deficiency is discharged')
    said('5d','δ*=1/20=0.05 CU','17/20=0.85','Do not execute','Without actual escrow','revision')
    a.reject(lambda:incident(recovery=F(6)),'recovery cannot exceed mistaken payment')
    a.reject(lambda:insurance(F(6,5),F(10)),'invalid probability')
    a.reject(lambda:exporter(F(0)),'zero currency quote')
    a.reject(lambda:minimum_capital(F(-1)),'negative commitment')
    a.reject(lambda:intervention_wallet(F(1,5),F(-1)),'negative escrow is not funding')


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    a=Audit();page=Page();page.raw=(root/AUTHOR[0]).read_text();page.feed(page.raw);page.close()
    wanted={'v11-a-q'+k:v for k,v in POINTS.items()}
    a.eq(page.points,wanted,'all eighteen unique scored prompts')
    a.eq(sorted(page.targets),sorted(wanted),'all eighteen exact prompts solved once')
    a.eq(len(page.ids),len(set(page.ids)),'unique IDs')
    a.eq((page.stack,page.h1),([],0),'complete fragment without extra h1')
    a.ok(all(i in ('form-a','solutions-a') or i.startswith('v11-a-') for i in page.ids),'owned ID scope')
    a.eq(sum(page.points.values()),100,'total points')
    for q in '12345':a.eq(sum(v for k,v in POINTS.items() if k.startswith(q)),20,'domain '+q+' points')
    for part,points in POINTS.items():
        answer=page.answers['v11-a-q'+part]
        rubric=answer.split('Credit ')[-1]
        a.ok(rubric.startswith(str(points)+':'),'advertised rubric total '+part)
        allocations=[int(x) for x in re.findall(r'\b(\d+)(?=;|\.)',rubric)]
        a.eq(sum(allocations),points,'actually printed rubric suballocations '+part)
    calculations(a,page)
    sources=strict((root/AUTHOR[3]).read_text())
    a.eq((sources['proposals'],sources['reused_source_ids']),([],[]),'original cases make no new external-source claim')
    a.eq([(r['chapter'],r['manuscript']) for r in sources['method_routes']],
         [('v11-c'+str(i).zfill(2),'chapters/v11-c'+str(i).zfill(2)+'.html') for i in range(1,13)],'all twelve exact taught method routes')
    author=strict((root/AUTHOR[2]).read_text())
    author_rows=author['artifact_bindings'];peer=strict((root/REVIEW).read_text());peer_rows=peer['reviewed_hashes']
    a.eq({r['path'] for r in author_rows},set(AUTHOR)-{AUTHOR[2]},'author exact three nonself payloads')
    a.eq(len(author_rows),3,'no duplicate author binding')
    a.eq({r['path'] for r in peer_rows},set(AUTHOR)|{SELF},'peer exact four author plus own checker')
    a.eq(len(peer_rows),5,'no duplicate peer binding')
    for row in author_rows+peer_rows:
        payload=(root/row['path']).read_bytes()
        a.eq((len(payload),hashlib.sha256(payload).hexdigest()),(row['bytes'],row['sha256']),'payload binding '+row['path'])
    summary=dict(component='v11-exam-a',review='separate machine-assisted peer',status='passed',
                 comparisons=a.comparisons,financial_interventions=len(a.interventions),
                 helper_domain_rejections=a.rejections,funded_state_allocations=a.allocations,
                 scored_subparts=18,solved_subparts=18,domains=5,points=100,chapter_outcomes=12,
                 author_bindings=4,peer_checker_bindings=1,
                 limits='Original finite contracts and focused boundaries; no author numerical oracle, empirical calibration, current legal authority, timing equating, rendered QA or human certification.')
    strict(json.dumps(summary,allow_nan=False))
    return summary


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
