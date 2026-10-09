"""Quiet independent arithmetic/structure audit of the original Finance Core A.

No textbook model or author output is used as an oracle. Journal postings,
dated claim strips, cash-flow equations, finite payoff replication and clearing
regime enumeration independently check the exact prompts and printed answers.
Four owned files suffice from any working directory, normally or under -O.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = 'content/cross-assessments/parts/finance-core-exam-a.html'
SOURCES = 'content/reviews/finance-core-exam-a-sources.json'
AUTHOR = 'content/reviews/finance-core-exam-a-author.json'
SELF = 'scripts/check_finance_core_exam_a.py'
ZERO = F(0)


def require(ok, message):
    if not ok:
        raise ValueError('Finance Core A: ' + message)


def strict(text):
    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, 'duplicate JSON key')
            obj[key] = value
        return obj
    def bad(value):
        raise ValueError('nonfinite JSON constant ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.stack, self.links = [], [], []
        self.points, self.solutions, self.rubric = {}, {}, []
        self.sources, self.h1 = set(), 0
        self.current = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'h1':
            self.h1 += 1
        if tag == 'a':
            self.links.append(a.get('href', ''))
            if 'data-source' in a:
                self.sources.add(a['data-source'])
        if tag == 'li' and 'data-points' in a:
            require(a.get('id') not in self.points, 'duplicate scored prompt')
            self.points[a['id']] = int(a['data-points'])
        if tag == 'li' and 'data-solution-for' in a:
            self.current = a['data-solution-for']
            require(self.current not in self.solutions, 'duplicate solution')
            self.solutions[self.current] = []
        if tag == 'tr' and 'data-domain' in a:
            self.rubric.append((a['data-domain'], int(a['data-points'])))
        if tag not in {'br','hr','img','input','link','meta','wbr','col','source','area','base','embed','param','track'}:
            self.stack.append(tag)
    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack.pop() == tag, 'unbalanced explicit HTML: ' + tag)
        if tag == 'li':
            self.current = None
    def handle_data(self, data):
        if self.current:
            self.solutions[self.current].append(data)


class Audit:
    def __init__(self, parser):
        self.parser = parser
        self.comparisons = self.anchors = self.approximations = self.interventions = self.journal_rows = 0
    def eq(self, actual, expected, label):
        self.comparisons += 1
        require(actual == expected, label + ': ' + repr(actual) + ' != ' + repr(expected))
    def yes(self, condition, label):
        self.eq(bool(condition), True, label)
    def anchor(self, actual, literal, part):
        self.eq(F(actual), F(literal), 'exact result in ' + part)
        text = re.sub(r'\s+', ' ', ''.join(self.parser.solutions['finance-core-a-' + part]))
        self.yes(literal in text, 'printed exact result present: ' + part + ' ' + literal)
        self.anchors += 1
    def approximate(self, actual, literal, places, part):
        self.yes(abs(F(actual)-F(literal)) <= F(1,2*10**places), 'labeled decimal rounding in '+part)
        text=''.join(self.parser.solutions['finance-core-a-'+part])
        self.yes(literal in text and 'approximately' in text, 'printed decimal is explicitly approximate')
        self.approximations += 1


def accounting(a, write_down=F(6)):
    balances = dict(cash=F(15), ar=F(20), inventory=F(30), ppe=F(80),
                    ap=F(18), advances=F(10), debt=F(40), equity=F(77))
    # Each row gives the actual double-entry account movement and cash class.
    rows = [
        ('operating', {'ar':F(160), 'equity':F(160)}),
        ('operating', {'cash':F(150), 'ar':F(-150)}),
        ('operating', {'cash':F(12), 'advances':F(12)}),
        ('operating', {'advances':F(-8), 'equity':F(8)}),
        ('operating', {'inventory':F(100), 'ap':F(100)}),
        ('operating', {'inventory':F(-90), 'equity':F(-90)}),
        ('operating', {'inventory':-write_down, 'equity':-write_down}),
        ('operating', {'cash':F(-95), 'ap':F(-95)}),
        ('operating', {'cash':F(-30), 'equity':F(-30)}),
        ('operating', {'ppe':F(-12), 'equity':F(-12)}),
        ('operating', {'cash':F(-4), 'equity':F(-4)}),
        ('financing', {'cash':F(-5), 'debt':F(-5)}),
        ('financing', {'cash':F(-6), 'equity':F(-6)}),
    ]
    cfo, income = ZERO, ZERO
    for classification, movement in rows:
        for key, value in movement.items():
            balances[key] += value
        assets = sum(balances[k] for k in ('cash','ar','inventory','ppe'))
        claims = sum(balances[k] for k in ('ap','advances','debt','equity'))
        a.eq(assets, claims, 'each journal entry preserves A=L+E')
        a.yes(all(v >= 0 for v in balances.values()), 'actual funded ledger positions')
        if classification == 'operating':
            cfo += movement.get('cash', ZERO)
            income += movement.get('equity', ZERO)
        a.journal_rows += 1
    return balances, income, cfo


def case1(a):
    b, income, cfo = accounting(a)
    for key, printed in [('ar','30'),('inventory','34'),('ap','23'),('advances','14')]:
        a.anchor(b[key], printed, '1a')
    for value, printed in [(income,'26'),(cfo,'33'),(b['cash'],'37'),(b['ppe'],'68'),
                           (b['debt'],'35'),(b['equity'],'97'),
                           (sum(b[k] for k in ('cash','ar','inventory','ppe')),'169'),
                           (sum(b[k] for k in ('ap','advances','debt')),'72')]:
        a.anchor(value, printed, '1b')
    a.eq(cfo, income + 12 + 6 - (30-20) - (40-30) + (23-18) + (14-10), 'gross inventory indirect cash')
    a.eq(cfo, income + 12 - (30-20) - (34-30) + (23-18) + (14-10), 'net inventory indirect cash')
    a.anchor(12 + 6, '18', '1c')
    a.anchor(income + 12 + 6, '44', '1c')
    a.anchor(b['equity'] + 18, '115', '1c')
    alternate, alternate_income, alternate_cfo = accounting(a, ZERO)
    a.eq(alternate_income-income, F(6), 'a different inventory estimate changes income')
    a.eq(alternate_cfo, cfo, 'inventory estimate creates no operating cash')
    a.eq(alternate['cash'], b['cash'], 'cash independent of noncash estimate')
    a.eq((alternate['inventory']-b['inventory'], alternate['equity']-b['equity']), (F(6),F(6)), 'inventory and equity revision match')
    a.interventions += 2


def cashflows(final_cost=F(70)):
    # Tax is explicitly on positive EBIT. The three tested cases remain within
    # that regime; the returned value contains neither interest nor a terminal perpetuity.
    ebits = [F(100)-60-30, F(120)-final_cost-30]
    taxes = [max(ZERO, x) / 4 for x in ebits]
    flows = [F(100)-60-taxes[0]-5, F(120)-final_cost-taxes[1]+15]
    return flows, taxes


def case2(a):
    flows, taxes = cashflows()
    pv = sum(d*c for d,c in zip([F(9,10),F(4,5)], flows))
    a.anchor(flows[0], '65/2', '2a'); a.anchor(flows[1], '60', '2a')
    a.anchor(pv, '309/4', '2a'); a.anchor(pv-70, '29/4', '2a')
    a.eq(taxes, [F(5,2),F(5)], 'dated cash taxes')
    a.eq(pv, F(4,5)*(flows[0]*F(9,8)+flows[1]), 'date2 accumulation and date0 discounting agree')
    rejected = F(100)+20-30
    total_operating = 100 + pv
    post = total_operating-30
    new_fraction = F(50)/post
    old_value = post-50
    shares = F(100)*50/old_value
    for value, text in [(rejected,'90'),(post,'589/4'),(new_fraction,'200/589'),
                        (shares,'20000/389'),(old_value,'389/4'),(total_operating,'709/4')]:
        a.anchor(value,text,'2b')
    a.eq(shares/(100+shares),new_fraction,'share count implements fair fraction')
    a.approximate(shares,'51.414',3,'2b')
    a.eq(old_value-rejected,pv-70,'owners gain exactly project NPV under fair funding')
    a.eq(20+50,60+10,'all named investment-cash recipients funded')
    a.eq(30+50+old_value,total_operating,'every resulting claim reconciles to assets')
    a.eq(F(60)-50,F(10),'new investor endowed cash is sufficient')
    issued = F(50)/F(9,10)
    fraction = issued/(100+issued)
    newcomer, old = post*fraction, post*(1-fraction)
    for value,text in [(issued,'500/9'),(fraction,'5/14'),(newcomer,'2945/56'),
                       (old,'5301/56'),(newcomer-50,'145/56'),(old-rejected,'261/56'),(old_value/100,'389/400')]:
        a.anchor(value,text,'2c')
    a.eq(newcomer-50+old-rejected,pv-70,'stale issuance reallocates but does not create NPV')
    a.eq((old_value-old),(newcomer-50),'exact old-to-new transfer')
    a.approximate(newcomer,'52.589286',6,'2c')
    a.approximate(old,'94.660714',6,'2c')
    # A meaningful investment-choice boundary within the stated positive-tax regime.
    breakeven_cost=F(985,12)
    for shift, sign in [(-1,1),(0,0),(1,-1)]:
        f,t=cashflows(breakeven_cost+shift)
        value=F(9,10)*f[0]+F(4,5)*f[1]-70
        a.eq(value,F(-3,5)*shift,'cost sensitivity on supported EBIT segment')
        a.eq((value>0)-(value<0),sign,'investment boundary changes the recommendation')
        a.yes(t[1]>0,'tax-regime hypothesis preserved')
    a.interventions += 2


def utility_derivative(w,p):
    return p*F(4,5)/(1+F(4,5)*w) - (1-p)*F(2,5)/(1-F(2,5)*w)


def case3(a):
    w=F(5,8)
    a.anchor(w,'5/8','3a')
    a.eq(utility_derivative(w,F(1,2)),ZERO,'interior utility stationarity')
    for weight in (F(0),w,F(1)):
        up,down=1+F(4,5)*weight,1-F(2,5)*weight
        curvature=-F(8,25)/up**2-F(2,25)/down**2
        a.yes(min(up,down)>=F(3,5),'wealth/log domain over endpoints and optimum')
        a.yes(curvature<0,'strict concavity at representative exact points')
    a.yes(utility_derivative(ZERO,F(1,2))>0 and utility_derivative(F(1),F(1,2))<0,'root lies between one-sided endpoint slopes')
    risky,cash=100*w,100*(1-w)
    units=risky/10
    wealth=[18*units+cash,6*units+cash]
    for value,text in [(risky,'125/2'),(cash,'75/2'),(units,'25/4'),(wealth[0],'150'),(wealth[1],'75'),(sum(wealth)/2,'225/2')]:
        a.anchor(value,text,'3a')
    state_up=(F(10)-6)/(18-6)
    state_down=1-state_up
    a.anchor(state_up,'1/3','3b');a.anchor(state_down,'2/3','3b')
    a.anchor(state_up*wealth[0]+state_down*wealth[1],'100','3b')
    a.eq(18*state_up+6*state_down,F(10),'quoted growth asset priced exactly')
    a.eq((F(18)+6)/2,F(12),'physical expectation differs from quoted stock price')
    for p,optimum in [(F(1,4),ZERO),(F(1,3),ZERO),(F(1,2),w),(F(3,5),F(1)),(F(3,4),F(1))]:
        raw=(15*p-5)/4
        clipped=min(F(1),max(ZERO,raw))
        a.eq(clipped,optimum,'changed physical forecast changes the funded optimum')
        slope=utility_derivative(clipped,p)
        a.yes(slope<=0 if clipped==0 else slope>=0 if clipped==1 else slope==0,'global boundary or interior certificate')
        a.eq(state_up+state_down,F(1),'unchanged market discount factor')
    a.interventions += 2
    r1=F(120,100)-1;r2=F(180,200)-1
    twr=(1+r1)*(1+r2)-1
    a.eq((r1,r2,twr),(F(1,5),F(-1,10),F(2,25)),'dated contribution-adjusted return chain')
    a.anchor(twr,'2/25','3c')
    for g in (F(1,2),F(1),F(3,2)):
        a.eq(100*g*g+80*g-180,20*(g-1)*(5*g+9),'IRR factorization, not numerical root guess')
    a.eq(100+80,F(180),'IRR zero fully accounts for both contributions')
    a.yes(F(-9,5)<0,'second gross-factor root outside economic domain')
    a.eq(F(180,100)-1,F(4,5),'unadjusted NAV growth includes the new capital')
    a.interventions += 1


def one_step(up,down,pay_up,pay_down,gross):
    delta=(pay_up-pay_down)/(up-down)
    bank=(pay_down-delta*down)/gross
    return delta,bank


def case4(a):
    gross=F(11,10)
    prob=(gross-F(4,5))/(F(6,5)-F(4,5))
    delta_up,bank_up=one_step(F(144),F(96),F(30),ZERO,gross)
    value_up=120*delta_up+bank_up
    delta0,bank0=one_step(F(120),F(80),value_up,ZERO,gross)
    value0=100*delta0+bank0
    a.approximate(value0,'13.946281',6,'4a')
    for value,text in [(prob,'3/4'),(delta_up,'5/8'),(bank_up,'-600/11'),
                       (value_up,'225/11'),(delta0,'45/88'),(bank0,'-4500/121'),(value0,'3375/242')]:
        # The manuscript uses the mathematical minus glyph in the bank positions.
        if text.startswith('-'):
            a.eq(value,F(text),'signed bank position '+text)
            solution=''.join(a.parser.solutions['finance-core-a-4a'])
            a.yes(('−'+text[1:]) in solution,'negative loan position printed')
            a.anchors+=1
        else:a.anchor(value,text,'4a')
    # Independent pricing by positive path state prices.
    prices=[(prob/gross)**2,prob*(1-prob)/gross**2,(1-prob)*prob/gross**2,((1-prob)/gross)**2]
    payoffs=[F(30),ZERO,ZERO,ZERO]
    a.eq(sum(p*x for p,x in zip(prices,payoffs)),value0,'path-state price valuation')
    a.eq(sum(prices),1/gross**2,'sure terminal CU discount factor')
    a.yes(all(p>0 for p in prices),'all path prices strictly positive')
    a.eq([delta_up*s+bank_up*gross for s in (F(144),F(96))],[F(30),ZERO],'up-path terminal hedge')
    a.eq(80*delta0+bank0*gross,ZERO,'down node closes both positions')
    a.yes(value0<=20,'buyer premium actually funded')
    additional_shares=delta_up-delta0
    cost=120*additional_shares
    grown_debt=-bank0*gross
    new_debt=-bank_up
    idle=60+bank0-cost
    for value,text in [(additional_shares,'5/44'),(cost,'150/11'),(grown_debt,'450/11'),(new_debt,'600/11'),(idle,'1110/121')]:
        a.anchor(value,text,'4b')
    a.eq(new_debt-grown_debt,cost,'self-financed up rebalance')
    a.eq(80*delta0,grown_debt,'down sale repays actual grown debt')
    ratios=[(-bank0)/(100*delta0),new_debt/(120*delta_up)]
    a.eq(ratios,[F(8,11),F(8,11)],'same monitored debt/collateral ratio')
    bound=1-max(ratios)
    a.anchor(bound,'3/11','4b')
    for haircut,ok in [(F(1,4),True),(bound,True),(bound+F(1,10000),False)]:
        a.eq(all(r<=1-haircut for r in ratios),ok,'sharp haircut feasibility boundary')
    a.interventions += 1
    cap=120*delta_up*F(2,3)
    injection=new_debt-cap
    for value,text in [(cap,'50'),(injection,'50/11'),(cap-grown_debt,'100/11'),(gross*cap,'55')]:
        a.anchor(value,text,'4c')
    a.eq((cap-grown_debt)+injection,cost,'new debt plus actual new equity fund the stock trade')
    residuals=[delta_up*s-cap*gross-x for s,x in [(F(144),F(30)),(F(96),ZERO)]]
    a.eq(residuals,[F(5),F(5)],'both terminal residuals assigned to the new investor')
    a.eq(residuals[0]/gross,injection,'new residual claim fairly funds the injection')
    a.yes(injection<=5 and 60+bank0-(cap-grown_debt)>=0,'both changed-policy providers have enough cash')
    a.yes(new_debt-(injection-F(1,10000))>cap,'every smaller candidate injection violates debt cap')
    a.eq((ZERO+new_debt)-cap,injection,'an unfunded intention cannot close the gap')
    a.interventions += 1


def clearing(cash_a,cash_b):
    """Enumerate capped/uncapped regimes; do not iterate the supplied formula."""
    cap_a,cap_b,alpha,beta=F(12),F(16),F(1,2),F(1,4)
    candidates=[(cap_a,cap_b),(cap_a,cash_b+beta*cap_a),
                (cash_a+alpha*cap_b,cap_b),
                ((cash_a+alpha*cash_b)/(1-alpha*beta),(cash_b+beta*cash_a)/(1-alpha*beta))]
    good={p for p in candidates if 0<=p[0]<=cap_a and 0<=p[1]<=cap_b
          and p==(min(cap_a,cash_a+alpha*p[1]),min(cap_b,cash_b+beta*p[0]))}
    require(len(good)==1,'original clearing regimes have one payment vector')
    return next(iter(good))


def case5(a):
    pa,pb=clearing(F(2),F(3))
    a.eq((pa,pb),(F(4),F(4)),'original simultaneous clearing')
    outside_a,outside_b=F(3,4)*pa,F(1,2)*pb
    a.eq(outside_a+outside_b,F(5),'internal network payments cancel')
    a.eq((12-pa,16-pb),(F(8),F(12)),'remaining nominal batch debt')
    a.eq((F(1,4)*(12-pa),F(3,4)*(12-pa),F(1,2)*(16-pb)),(F(2),F(6),F(6)),'remaining creditor-specific faces')
    marked_assets=2+outside_a+18
    equity=marked_assets-20
    cash=2+outside_a
    paid=min(F(8),cash)
    left_deposits=20-paid
    for value,text in [(equity,'three'),(paid,'five')]:
        a.eq(value,{'three':F(3),'five':F(5)}[text],'bank marked equity/payment')
    for value,text in [(marked_assets,'23'),(left_deposits,'15'),(18,'18')]:
        a.anchor(value,text,'5b')
    a.eq(18,left_deposits+equity,'post-payment balance sheet with arrears')
    a.eq(F(8)-paid,F(3),'missed deposit is retained')
    a.eq(F(9)-outside_a,F(6),'written-down but surviving nominal bank claim')
    # An affine maximum on the simplex is attained at a vertex. Check every
    # vertex, then use exact regime enumeration at the meaningful response points.
    vertices=[(ZERO,ZERO),(F(6),ZERO),(ZERO,F(6))]
    max_a=max(4+(8*x+4*y)/7 for x,y in vertices)
    max_b=max(4+(2*x+8*y)/7 for x,y in vertices)
    a.anchor(max_a,'76/7','5c');a.eq(max_b,max_a,'separate affine maximum for B')
    a.yes(max_a<12 and max_b<16,'both caps slack on the whole grant simplex')
    for x,y in vertices+[(F(7,2),ZERO),(F(1),F(5)),(F(7,2)-F(1,10000),ZERO)]:
        payments=clearing(2+x,3+y)
        expected=(4+(8*x+4*y)/7,4+(2*x+8*y)/7)
        a.eq(payments,expected,'independent regime enumeration equals original grant formula')
        a.eq(F(3,4)*payments[0]+F(1,2)*payments[1],5+x+y,'outside receipts equal funded external resources')
        a.eq(2+F(3,4)*payments[0]>=8,2*x+y>=7,'exact bank-deadline inequality')
    # Vertices of the feasible grant polygon under x+y<=6 and 2x+y>=7.
    feasible_vertices=[(F(7,2),ZERO),(F(6),ZERO),(F(1),F(5))]
    best=min(feasible_vertices,key=lambda xy:sum(xy))
    a.eq(best,(F(7,2),ZERO),'unique upstream minimum and allocation')
    a.anchor(sum(best),'7/2','5c')
    pa,pb=clearing(2+best[0],3+best[1])
    a.eq((pa,pb),(F(8),F(5)),'funded minimum batch payments')
    a.anchor(F(1,2)*pb,'5/2','5c')
    a.anchor(F(3,4)*pa+F(1,2)*pb,'17/2','5c')
    direct=F(8)-(2+outside_a)
    a.eq(direct,F(3),'sharp direct bank grant')
    a.eq(sum(best)-direct,F(1,2),'extra donor cost equals additional other-creditor receipt')
    a.eq(2+F(3,4)*pa,F(8),'upstream bank payment funded')
    a.eq(2+outside_a+direct,F(8),'direct bank payment funded')
    a.eq(8+F(1,2)*pb+(6-sum(best)),F(13),'all outside cash recipients under upstream route')
    a.eq(8+outside_b+(6-direct),F(13),'all outside cash recipients under direct route')
    a.eq((18-12,18-12),(F(6),F(6)),'same bank capital after both funded responses')
    a.eq((9-F(3,4)*pa,9-outside_a),(F(3),F(6)),'policy-specific surviving bank nominal claims')
    a.interventions += 3


def structure(a, parser, bound):
    expected={}
    for i,points in enumerate([[6,8,6],[7,8,5],[8,5,7],[8,6,6],[6,6,8]],1):
        for suffix,value in zip('abc',points):
            expected['finance-core-a-'+str(i)+suffix]=value
    a.eq(parser.points,expected,'all exact scored subparts')
    a.eq(set(parser.solutions),set(expected),'every prompt has exactly one solution')
    a.eq(sum(parser.points.values()),100,'100-point exam')
    a.eq(parser.rubric,[('D'+str(i),20) for i in range(1,6)],'five equal essential domains')
    a.eq(parser.h1,0,'fragment does not duplicate root h1')
    a.eq(parser.stack,[],'all explicit tags close')
    a.eq(len(parser.ids),len(set(parser.ids)),'unique IDs')
    a.yes({'form-a','solutions-a'}<=set(parser.ids),'shared form and solution anchors')
    a.yes(all(x in {'form-a','solutions-a'} or x.startswith('finance-core-a-') for x in parser.ids),'owned anchor namespace')
    source=strict((ROOT/SOURCES).read_text())
    a.eq(source['proposals'],[],'no new external source proposal')
    a.eq(parser.sources,{row['id'] for row in source['reuse']},'every citation has a scoped inherited record')
    a.eq(len(source['reuse']),6,'six scoped inherited source records')
    a.eq({r['domain'] for r in source['chapter_method_routes']},{'D1','D2','D3','D4','D5'},'all five volume domains mapped')
    a.eq(len(source['chapter_method_routes']),25,'25 sampled chapter-method routes')
    for row in source['chapter_method_routes']:
        a.eq(row['status'],'accepted','method taught in accepted prerequisite')
        a.yes(row['reader_url'] in parser.links,'actual flat method link')
    for pid,parts in parser.solutions.items():
        text=''.join(parts)
        a.yes('points:' in text,'explicit per-solution rubric '+pid)
        a.yes(len(text)>400,'substantive full solution '+pid)
    if bound:
        review=strict((ROOT/AUTHOR).read_text())
        records=review['reviewed_hashes']
        a.eq(len(records),3,'three nonself author payloads')
        a.eq({r['path'] for r in records},{HTML,SOURCES,SELF},'exact author binding set')
        for row in records:
            raw=(ROOT/row['path']).read_bytes()
            a.eq((len(raw),sha256(raw).hexdigest()),(row['bytes'],row['sha256']),'final payload byte identity')


def check(verify_bindings=True):
    parser=Markup();parser.feed((ROOT/HTML).read_text());parser.close()
    a=Audit(parser)
    structure(a,parser,verify_bindings)
    for f in (case1,case2,case3,case4,case5):
        f(a)
    return dict(component='finance-core-exam-a',status='passed',comparisons=a.comparisons,
                cases=5,scored_subparts=15,points=100,exact_printed_anchors=a.anchors,
                labeled_decimal_approximations=a.approximations,
                financial_intervention_groups=a.interventions,independent_journal_rows=a.journal_rows,
                inherited_source_scopes=6,sampled_chapter_routes=25,
                author_nonself_hashes=3 if verify_bindings else 0)


if __name__=='__main__':
    print(json.dumps(check(),sort_keys=True,allow_nan=False))
