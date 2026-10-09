"""Coordinator's independent finite-contract and printed-table reconstruction."""
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'content/cross-assessments/parts/finance-core-project.html'


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.active, self.row, self.cell = {}, None, None, None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.active = a.get('id')
            if self.active:
                self.tables[self.active] = []
        if self.active and tag == 'tr':
            self.row = []
        if self.active and tag in ('td', 'th'):
            self.cell = ''
    def handle_data(self, text):
        if self.cell is not None:
            self.cell += text
    def handle_endtag(self, tag):
        if self.active and tag in ('td', 'th'):
            self.row.append(self.cell.strip())
            self.cell = None
        if self.active and tag == 'tr':
            self.tables[self.active].append(self.row)
        if tag == 'table':
            self.active = None


def audit():
    comparisons = 0
    def equal(actual, expected, label):
        nonlocal comparisons
        comparisons += 1
        if actual != expected:
            raise ValueError(label + ': ' + repr(actual) + ' != ' + repr(expected))

    def policies(loss=F(0), before=False, pd=F(1,20), late=False, senior=F(0)):
        rows = []
        note_price = F(41) - loss/5 if before else F(41)
        for x in (F(1,2), F(3,4), F(1)):
            for kind, h in [('none', F(0)), ('credit', x/2), ('credit', x),
                            ('escrow', x/2), ('escrow', x)]:
                premium = h * {'none':F(0), 'credit':F(12,5), 'escrow':F(4)}[kind]
                bills = 64 - x*note_price - premium - x/10 - (2*h/5 if kind=='escrow' else 0)
                at09 = bills*F(10,9)-20
                before_noon_payment = [at09+x*(30-loss), at09+50*x]
                if kind == 'escrow' and not late:
                    before_noon_payment[0] += h*(20-senior)
                net = [before_noon_payment[0]-44, before_noon_payment[1]-44]
                if kind == 'credit':
                    net[0] += 12*h
                elif kind == 'escrow' and late:
                    net[0] += h*(20-senior)
                ok = at09 >= 0 and min(before_noon_payment) >= 44 and min(net) >= 2
                mean = pd*net[0]+(1-pd)*net[1]
                rows.append(dict(x=x, kind=kind, h=h, bills=bills, net=net, mean=mean,
                                 noon=before_noon_payment, eligible=ok))
        return rows

    def winner(rows):
        good = [r for r in rows if r['eligible']]
        return min(good, key=lambda r:(-r['mean'],r['x'],r['h'],r['kind'])) if good else None

    def locate(rows, x, kind, h):
        return next(r for r in rows if (r['x'],r['kind'],r['h']) == (x,kind,h))

    page=Tables();page.feed(HTML.read_text())
    base=policies()
    printed=page.tables['finance-core-project-policy-table'][1:]
    equal(len(printed),15,'complete printed policy menu')
    for shown, r in zip(printed,base):
        values=[F(v.replace('−','-')) for v in [shown[0], *shown[2:7]]]
        equal(values,[r['x'],r['h'],r['bills'],*r['net'],r['mean']], 'printed row '+str((r['x'],r['kind'],r['h'])))
        equal(shown[1],r['kind'],'protection label')
        equal(shown[7], 'Yes' if r['eligible'] else 'No','full deadline-and-capital decision')
    chosen=winner(base)
    equal((chosen['x'],chosen['h']),(F(1,2),F(1,4)),'unique baseline optimum')
    equal(sum(r['eligible'] for r in base),4,'complete feasible set')
    equal(chosen['mean'],F(281,36),'physical chosen mean')
    # Reconstruct the printed event table from separate cash receipts.
    cash0=chosen['bills']*F(10,9)
    cash09=cash0-20
    cash12=[cash09+15,cash09+25]
    after_hedge=[cash12[0]+5,cash12[1]]
    final=[v-44 for v in after_hedge]
    expected=[[cash0]*2,[cash09]*2,cash12,after_hedge,final,final]
    actual=[[F(v) for v in row[1:]] for row in page.tables['finance-core-project-cash-table'][1:]]
    equal(actual,expected,'all printed reserve event balances')
    equal(sum((F(60),F(10),F(50),F(20),F(100),F(20),F(12))),272,'listed endowed entry cash')
    equal(F(1,5)*final[0]+F(7,10)*final[1],F(25,4),'residual price is sponsor capital less real fees')
    benchmark=F(64,9)
    losses=[benchmark-v for v in final]
    equal(losses,[F(73,18),-F(17,18)],'selected benchmark losses')
    equal((losses[0]+losses[1])/2,F(14,9),'atom-correct worst ten percent')
    equal(F(1,20)*losses[0]+F(19,20)*losses[1],-F(25,36),'physical mean loss')
    equal((80-55-20,10+80-55-20-15),(5,0),'collection transfer preserves income and fails parent cash gate')
    shocked=policies(F(5,2))
    old=locate(shocked,F(1,2),'escrow',F(1,4))
    equal(old['net'][0],F(65,36),'actual original position after revenue shock')
    comparative=winner(shocked)
    equal((comparative['x'],comparative['h'],comparative['mean']),
          (F(1,2),F(1,2),F(325,48)),'historical-entry counterfactual winner, not an executable rebalance')
    before=policies(F(5,2),before=True)
    prospect=winner(before)
    equal((prospect['x'],prospect['h'],prospect['bills'],prospect['net'],prospect['mean']),
          (F(1,2),F(1,4),F(213,5),[F(25,12),F(25,3)],F(385,48)),'funded before-trade reprice')
    equal((F(55,18)-2)/F(1,2),F(19,9),'historical fixed-position capital boundary')
    equal((F(55,18)-2)/F(7,18),F(19,7),'repriced fixed-position capital boundary')
    for before_trade,boundary in ((False,F(19,9)),(True,F(19,7))):
        for delta,ok in ((boundary-F(1,100),True),(boundary,True),(boundary+F(1,100),False)):
            candidate=locate(policies(delta,before=before_trade),F(1,2),'escrow',F(1,4))
            equal(candidate['eligible'],ok,'inclusive capital-boundary sides')
    changed=policies(pd=F(3,10))
    equal(locate(changed,F(1,2),'escrow',F(1,4))['mean'],F(59,9),'changed physical law, unchanged prices')
    equal(winner(changed)['mean'],F(41,6),'changed prospective mandate choice')
    equal((F(145,18)-F(41,6))/5,F(11,45),'physical preference switch')
    equal(winner(policies(pd=F(11,45)))['h'],F(1,4),'exact tie rule')
    delayed=policies(late=True)
    equal(winner(delayed),None,'late escrow admits no original menu policy')
    old_late=locate(delayed,F(1,2),'escrow',F(1,4))
    bridge=44-old_late['noon'][0]
    equal((bridge,2-bridge,old_late['net'][0]),(F(35,18),F(1,18),F(55,18)),'separately funded bridge, retained provider cash and final capital')
    prior=policies(senior=F(5))
    prior_old=locate(prior,F(1,2),'escrow',F(1,4))
    equal((prior_old['net'][0],prior_old['mean']),(F(65,36),F(1115,144)),'original holding after senior claim discovery')
    prior_best=winner(prior)
    equal((prior_best['h'],prior_best['net'][0],prior_best['mean']),
          (F(1,2),F(13,3),F(161,24)),'counterfactual original-entry alternative under priority stress')
    # Affine coefficient identities establish the price family on the whole interval.
    constants=[F(0),F(1,5),F(3,10),F(2,5)]
    slopes=[F(1),F(-2),F(4,3),-F(1,3)]
    for payoffs,price in [([1,1,1,1],F(9,10)),([10,30,50,50],F(41)),([0,0,10,40],F(19))]:
        equal(sum(a*b for a,b in zip(constants,payoffs)),price,'four-state family constant')
        equal(sum(a*b for a,b in zip(slopes,payoffs)),0,'four-state family zero slope')
    lower=[25-F(n,2) for n in (10,30,50,50)]
    upper=[50-n for n in (10,30,50,50)]
    equal(lower,[20,10,0,0],'constructive subhedge')
    equal(upper,[40,20,0,0],'constructive superhedge')
    equal((25*F(9,10)-F(41,2),50*F(9,10)-41),(F(2),F(4)),'endpoint hedge prices')
    raw=HTML.read_bytes()
    return {'component':'finance-core-project','status':'printed financial tables and focused independent transfers passed',
            'comparisons':comparisons,'printed_policy_rows':15,'printed_event_rows':6,
            'manuscript':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
            'limits':'Coordinator equations use no author model/output. Does not replace full prose/proof/API/source/peer review; post-trade alternative policies are counterfactual original entries.'}


if __name__=='__main__':
    result=audit()
    (ROOT/'production/finance-core-project-printed-root-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
