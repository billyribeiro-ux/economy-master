"""Exact original Volume7 FormB audit; check() is quiet and JSON serializable."""
from fractions import Fraction as F
from html.parser import HTMLParser
import json
import re
from pathlib import Path

BOOK=Path(__file__).resolve().parents[1]
FRAGMENT=BOOK/'content/assessments/parts/v07-exam-b.html'


def need(ok,message):
    if not ok:raise AssertionError(message)


class Exam(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.prompts={};self.solutions={};self.rubrics=0;self.h2=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        need(tag not in {'html','body','h1'},'assessment is a fragment')
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h2':self.h2.append(a.get('id'))
        if 'data-points' in a:
            need(tag=='li' and a.get('id'),'point item requires prompt ID')
            self.prompts[a['id']]=int(a['data-points'])
        if 'data-solution-for' in a:self.solutions[a['data-solution-for']]=a.get('id')
        if tag not in {'br','hr','img','meta','link','input'}:self.stack.append(tag)
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1]==tag,'balanced assessment HTML')
        self.stack.pop()
    def handle_data(self,data):
        self.rubrics+=data.count('5-point rubric:')


def check():
    checks=[];targets={}
    # Q1: close actual signed transactions, not merely a copied income bridge.
    book=dict(cash=F(70),ar=F(30),allowance=F(-3),prepaid=F(12),ppe=F(60),ap=F(-20),advance=F(-24),capital=F(-125))
    def entry(**legs):
        need(sum(legs.values())==0,'unbalanced independent journal')
        for k,v in legs.items():book[k]=book.get(k,F(0))+F(v)
    entry(cash=48,advance=-48);entry(advance=60,revenue=-60)
    entry(cash=40,revenue=-40);entry(ar=50,revenue=-50);entry(cash=44,ar=-44)
    entry(allowance=4,ar=-4)
    need(book['allowance']==1,'temporary debit allowance')
    provision=book['allowance']+6
    entry(bad_debt=provision,allowance=-provision)
    entry(prepaid=18,cash=-18);entry(supplies=20,prepaid=-20)
    entry(other_expense=85,cash=-85);entry(other_expense=8,ap=-8)
    entry(ap=15,cash=-15);entry(depreciation=6,ppe=-6);entry(dividend=5,cash=-5)
    need(sum(book.values())==0,'Q1 unclosed trial balance')
    expenses=sum(book[k] for k in ('bad_debt','supplies','other_expense','depreciation'))
    profit=-book['revenue']-expenses;equity=-book['capital']+profit-book['dividend']
    arnet=book['ar']+book['allowance'];liabilities=-book['ap']-book['advance']
    assets=book['cash']+arnet+book['prepaid']+book['ppe']
    cfo_direct=48+40+44-18-85-15
    cfo_indirect=profit+6-(arnet-27)-(book['prepaid']-12)+(-book['ap']-20)+(-book['advance']-24)
    need([-book['revenue'],-book['advance'],provision,book['ar'],arnet,expenses,profit,equity,book['cash'],assets,liabilities]==list(map(F,[150,12,7,32,26,126,24,144,79,169,25])),'Q1 exact closed targets')
    need(cfo_direct==cfo_indirect==14 and assets==liabilities+equity,'Q1 cash and claims closure')
    need(cfo_indirect+provision!=cfo_direct,'Q1 detects allowance double-counting')
    targets.update({'1a':['150','12','132'],'1b':['32','7','26'],'1c':['126','24','144','10','54','13'],'1d':['14','79','169']})
    checks.append(dict(name='D1 complete signed ledger, allowance roll-forward and independent direct/indirect cash',status='pass'))

    # Q2: independent lifecycle amounts, PV and total cash/expense identities.
    dep1=F(120,3);impairment=120-dep1-70;dep2=F(70,2)
    ceiling=120-2*dep1;reverse=min(F(90),ceiling)-(70-dep2)
    need((dep1,impairment,dep2,ceiling,reverse)==tuple(map(F,[40,10,35,40,5])),'Q2 impairment recovery ceiling')
    need(dep1+dep2+impairment-reverse==120-ceiling,'Q2 impaired asset expense closure')
    interest=F(104,20);after_coupon=104+interest-6;gain=after_coupon-101
    net_profit=-interest+gain;premium=104-after_coupon
    need((interest,after_coupon,gain,net_profit,premium)==tuple(map(F,['5.2','103.2','2.2',-3,'0.8'])),'Q2 premium amortization/retirement')
    need(net_profit-gain-premium==-6 and 6+101-104==-net_profit,'Q2 note cash/lifetime gain bridge')
    liab=F(44)/F('1.1')+F('48.4')/F('1.1')**2;rou=liab+12
    int1=liab/10;l1=liab+int1-44;int2=l1/10
    need((liab,rou,int1,l1,rou/2)==tuple(map(F,[80,92,8,44,46])),'Q2 prepaid lease')
    need(l1+int2-F('48.4')==0 and rou+int1+int2==12+44+F('48.4'),'Q2 lease lifetime closure')
    disposal_gain=74-70
    need(40+10-disposal_gain==120-74==46,'Q2 alternative disposal closure')
    targets.update({'2a':['40','10','70','35','5','40'],'2b':['26/5','516/5','11/5','-6','-101'],'2c':['80','92','8','44','46','46'],'2d':['4','74','46']})
    checks.append(dict(name='D2 impairment/reversal limit, premium retirement, prepaid lease and alternative disposal',status='pass'))

    # Q3: use equity/cash and separate group attribution paths as cross-checks.
    repurchase=20*3;reissue_cash=8*F('2.5');reissue_cost=8*3
    shortfall=reissue_cost-reissue_cash;used_premium=min(F(2),shortfall);re_reduction=shortfall-used_premium
    treasury=repurchase-reissue_cost;closing_equity=120+78+(2-used_premium)+(40-re_reduction)-treasury
    need((120-20+8,treasury,re_reduction,closing_equity)==tuple(map(F,[108,36,2,200])),'Q3 treasury equity components')
    need(closing_equity==240-repurchase+reissue_cash,'Q3 equity cash closure')
    identifiable=140-40;full_nci=60;goodwill=90+full_nci-identifiable
    proportionate_nci=F(2,5)*identifiable;partial=90+proportionate_nci-identifiable
    unrealized=F(30-18,3);adjusted_sub=50-unrealized
    group=25+adjusted_sub;nci_profit=F(2,5)*adjusted_sub;parent_profit=group-nci_profit
    closing_nci=full_nci+nci_profit-F(2,5)*10
    need((goodwill,partial,unrealized,group,nci_profit,parent_profit,closing_nci)==tuple(map(F,[50,30,4,71,'18.4','52.6','74.4'])),'Q3 full-value upstream targets')
    need(parent_profit==25+F(3,5)*adjusted_sub and closing_nci==F(2,5)*(100+50-10-4)+20,'Q3 independent attribution and NCI premium bridge')
    taxable=80+5+12-(35-20);current=F(taxable,4);dtl=F((100-20)-(100-35),4);dta=F(12,4)
    deferred=dtl-dta;total=current+deferred;net=80-total;payable=current-18
    need((taxable,current,payable,dtl,dta,deferred,total,net)==tuple(map(F,[82,'20.5','2.5','3.75',3,'0.75','21.25','58.75'])),'Q3 tax targets')
    need(total==F(80+5,4) and total-18==payable+deferred,'Q3 permanent-item and expense/cash checks')
    targets.update({'3a':['108','36','0','38','200'],'3b':['100','60','50','40','30'],'3c':['4','71','92/5','263/5','372/5'],'3d':['82','41/2','5/2','15/4','3','3/4','85/4','235/4']})
    checks.append(dict(name='D3 treasury cash/equity, full-NCI upstream consolidation and complete current/deferred tax',status='pass'))

    # Q4: exhaust the small integer set rather than invoke a divisible ranking.
    def solve(hours):
        possible=[(11*a+7*b,a,b) for a in range(3) for b in range(3) if 3*a+2*b<=hours]
        top=max(x[0] for x in possible)
        return top,[(a,b) for v,a,b in possible if v==top],possible
    baseline=solve(4);expanded=solve(6);reserved=solve(2)
    need(baseline[:2]==(14,[(0,2)]) and len(baseline[2])==4,'Q4 original exhaustive set')
    need(expanded[:2]==(22,[(2,0)]) and expanded[0]-baseline[0]-7==1,'Q4 expansion transfer')
    opportunity=baseline[0]-reserved[0]
    need(opportunity==7 and 16-4-3-opportunity==2 and 4+3+opportunity==14,'Q4 special order reoptimization')
    before_current=F(90,45);after_current=F(80,35);before_quick=F(30,45);after_quick=F(20,35)
    need((before_current,after_current,before_quick,after_quick)==(F(2),F(16,7),F(2,3),F(4,7)),'Q4 liquidity ratios')
    need(55-12==45-2==43 and 2+18+60+60==15+45+80,'Q4 net debt and closing equation')
    margin=F(24,240);turnover=F(240,160);multiplier=F(160,80)
    invested=140-20;nopat=40*F(4,5)
    need(margin*turnover*multiplier==F(24,80)==F(3,10),'Q4 DuPont cancellation')
    need(invested==60+80-20==120 and nopat/invested==F(4,15),'Q4 NOPAT and matching capital')
    targets.update({'4a':['14','22','1'],'4b':['7','2','14'],'4c':['2','16/7','2/3','4/7','2','43'],'4d':['1/10','3/2','2','3/10','120','32','4/15']})
    checks.append(dict(name='D4 complete integer feasible sets, opportunity cost, liquidity paradox and matched return denominators',status='pass'))

    # Q5: derive financing and independently close both constrained and repaired forecasts.
    K=10+24-40-10-2;needed=F(10-K)/F('0.9')
    capped_interest=F(30,10);capped_cash=K+30-capped_interest
    need((K,needed,capped_interest,capped_cash)==(-18,F(280,9),F(3),F(9)),'Q5 borrowing fixed point')
    need(needed>30 and 10-capped_cash==1 and K+28-F('2.8')==F('7.2'),'Q5 cap and omitted own interest')
    repaired_draw=F(26)/F('0.9');repaired_interest=repaired_draw/10
    profit=18-repaired_interest;cfo=24-repaired_interest;cfi=-40;cff=repaired_draw-10
    cash=10+cfo+cfi+cff;ppe=90+40-6;debt=30+repaired_draw;equity=60+profit
    need((repaired_draw,repaired_interest,profit,cfo,cff,debt,equity)==(F(260,9),F(26,9),F(136,9),F(190,9),F(170,9),F(530,9),F(676,9)),'Q5 repaired forecast anchors')
    need(cash==10 and cash+ppe==debt+equity==134 and repaired_draw<=30,'Q5 complete repaired statement closure')
    # An independent capped draft also closes, while failing only the specified cash minimum.
    need(9+124==(40-10+30)+(60+(18-3)-2)==133,'Q5 infeasible-buffer draft still balances')
    sum_segment=(180+30-160)+(120-100);revenue=180+120
    aggregate_profit=(180+30+120-30)-(160+100-30)
    ebit=sum_segment-12;pretax=ebit-6;ni=pretax-10
    need((revenue,sum_segment,ebit,pretax,ni)==(300,70,58,52,42) and aggregate_profit==sum_segment,'Q5 segment elimination and group bridge')
    need(58+5+4==67 and 58+4-3==59 and 67-59==8,'Q5 symmetric recurrence')
    targets.update({'5a':['280/9','3','9','1'],'5b':['260/9','26/9','136/9','190/9','170/9','10','124','530/9','676/9','134'],'5c':['300','70','58','52','42'],'5d':['67','59','8']})
    checks.append(dict(name='D5 full-year interest funding, hard cap, feasible distribution policy, closed statements and segment/normalization bridges',status='pass'))

    html=FRAGMENT.read_text();parser=Exam();parser.feed(html);parser.close()
    expected={f'v07-b-q{q}{part}' for q in range(1,6) for part in 'abcd'}
    need(not parser.stack and len(parser.ids)==len(set(parser.ids)),'HTML/ID uniqueness')
    need(parser.h2==['form-b','solutions-b'],'required section anchors')
    need(set(parser.prompts)==expected and set(parser.solutions)==expected,'twenty matched prompt/solution pairs')
    need(all(v==5 for v in parser.prompts.values()) and sum(parser.prompts.values())==100 and parser.rubrics==20,'points and explicit rubrics')
    rubric_blocks=re.findall(r'<p><strong>5-point rubric:</strong>(.*?)</p>',html,re.S)
    need(len(rubric_blocks)==20 and all(sum(int(v) for v in re.findall(r':\s*(\d+)\s+points?\b',block))==5 for block in rubric_blocks),'each explicit rubric allocates exactly five points')
    need(all(sum(v for k,v in parser.prompts.items() if k.startswith(f'v07-b-q{q}'))==20 for q in range(1,6)),'five equal domains')
    need('180 minutes' in html and 'closed notes' in html and 'calculator permitted' in html,'exam conditions')
    need(set(targets)=={f'{q}{a}' for q in range(1,6) for a in 'abcd'},'all-part numerical coverage')
    need(json.loads((BOOK/'content/reviews/v07-exam-b-sources.json').read_text())==[],'no new source proposals; reuse ledger is in author record')
    checks.append(dict(name='Twenty unique 5-point prompts, twenty solutions/rubrics, five 20-point domains and required fragment anchors',status='pass'))
    report=dict(assessment='v07-exam-b',status='pass',points=100,minutes=180,parts=20,checks=checks,exact_targets=targets,
                limitations=['Original stipulated cases; no current reporting/legal compliance or fraud determination.',
                             'Numerical closure does not replace the complete prose/condition/rubric review.',
                             'Timing is an author estimate; no external exam calibration or learner-performance claim.',
                             'No browser/mobile/print visual QA performed.'])
    json.dumps(report,allow_nan=False)
    return report


if __name__=='__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
