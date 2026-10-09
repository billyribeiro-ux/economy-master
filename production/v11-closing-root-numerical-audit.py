"""Coordinator original-contract recomputation; imports no chapter code/output."""
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
from pathlib import Path
import json


def main():
    rows=[]
    def eq(label,actual,expected):
        if actual!=expected:raise RuntimeError(label+': '+str(actual)+' != '+str(expected))
        rows.append({'claim':label,'verified_value':str(actual)})
    # C09: funded parity and two separate cash deadlines.
    K=F(6,5)*F(53,50)/F(51,50)
    eq('c09 covered rate',K,F(106,85));eq('c09 rich-forward funded profit',102*F(13,10)-120*F(53,50),F(27,5))
    eq('c09 cheap-forward funded profit',120*F(53,50)-102*F(6,5),F(24,5))
    mean=F(3,4)*80+F(1,4)*144
    eq('c09 physical mean',mean,F(96));eq('c09 physical variance',F(3,4)*(80-mean)**2+F(1,4)*(144-mean)**2,F(768))
    eq('c09 ideal receipt',80*K,F(1696,17));eq('c09 expected hedge difference',80*K-mean,F(64,17))
    for name,S,X,a,C,T,rho,arrived,expected_arrears,expected_injection,expected_net in [
        ('transfer',F(4,5),F(4,5),F(1,20),F(80),F(40),F(1),True,F(276,17),F(276,17),F(200,17)),
        ('conversion',F(4,5),F(4,5),F(1,20),F(50),F(200),F(1),True,F(276,17),F(276,17),F(200,17)),
        ('joint',F(4,5),F(9,10),F(3,40),F(50),F(32),F(1,2),True,F(818,17),F(818,17),F(-172,17)),
        ('margin',F(3,2),F(3,2),F(9,40),F(80),F(200),F(1),True,F(4,17),F(106,17),F(200,17)),
        ('delay',F(4,5),F(4,5),F(1,20),F(80),F(200),F(1),False,F(956,17),F(956,17),F(200,17))]:
        margin=80*a;posted=min(F(12),margin);transfer=min(S*min(F(80) if arrived else F(0),C),T);g=80*(K-X);positive=rho*max(g,0);negative=max(-g,0)
        cash=12-posted+transfer+positive;ndfpaid=min(cash,negative);cash-=ndfpaid;debtpaid=min(F(100),cash)
        injection=max(F(0),margin-12,margin+100+negative-12-transfer-positive)
        eq('c09 '+name+' actual debt arrears',100-debtpaid,expected_arrears)
        eq('c09 '+name+' full posting and payment injection',injection,expected_injection)
        eq('c09 '+name+' final translated net assets',12+80*S+positive-negative-100,expected_net)
    h=F(36)/(F(9,40)+F(27,68));injection=F(9,40)*h-12
    eq('c09 hedge notional',h,F(2720,47));eq('c09 common injection',injection,F(48,47));eq('c09 cancelling slope',F(30,47)*F(9,40)-F(17,47)*F(27,68),F(0))
    eq('c09 independent constant lower bound',F(30,47)*(-12)+F(17,47)*24,injection)
    eq('c09 residual notional',80-h,F(1040,47));eq('c09 inactive early bound',h/20-12,F(-428,47));eq('c09 inactive late bound',F(65,136)*h-32,F(-204,47))
    eq('c09 reference sovereign available F',30-8+10+20+12,64);eq('c09 stop sovereign paid F',30-8+8+6-12-4,20)
    eq('c09 stop remaining H',100-36-3*6,46);eq('c09 old-debt valuation bridge',(3-2)*100+3*(0-20),3*80-2*100)
    eq('c09 early release remaining gap',40-(20+8),12);eq('c09 restructured PV gain',44*F(9,10)-40*F(19,20),F(8,5));eq('c09 PV preserving face',40*F(19,20)/F(9,10),F(380,9))
    # C10: independent statewise stakeholder aggregation and changed financing.
    laws=[(108,108),(130,50),(129,49)]
    expectations={15:[(F(8),F(0),F(8)),(F(75,4),F(35,4),F(5)),(F(18),F(9),F(4))],20:[(F(8),F(0),F(8)),(F(35,2),F(15,2),F(5)),(F(67,4),F(31,4),F(4))],50:[(F(8),F(0),F(8)),(F(10),F(0),F(10)),(F(37,4),F(1,4),F(4))]}
    for capital,expected in expectations.items():
        deposits=100-capital
        for j,payoffs in enumerate(laws):
            profit=sum(w*max(a-deposits,0) for w,a in zip([F(3,4),F(1,4)],payoffs))-capital
            insurance=sum(w*max(deposits-a,0) for w,a in zip([F(3,4),F(1,4)],payoffs))
            surplus=sum(w*(a-100-20*(a<deposits)) for w,a in zip([F(3,4),F(1,4)],payoffs))
            eq(f'c10 K{capital} option{j} profit/transfer/surplus',(profit,insurance,surplus),expected[j])
            eq(f'c10 K{capital} option{j} resource bridge',profit-insurance,sum(w*a for w,a in zip([F(3,4),F(1,4)],payoffs))-100)
    eq('c10 capture boundary',F(1)/(F(75,4)-8),F(4,43));eq('c10 welfare harm boundary',4*(10-6),16)
    eq('c10 lambda.1 scores',(5+F(75,4)/10,F(7,2)+F(18,10),6+F(8,10)),(F('6.875'),F('5.3'),F('6.8')))
    eq('c10 conduct care surplus',12-2-F(3,2)-F(1,4),F(33,4));eq('c10 shortcut surplus',12-9-F(1,4),F(11,4))
    eq('c10 collection threshold',F(2,7),F(2)/min(100,7));eq('c10 boundary care surplus',12-2-F(3,2)-F(2,7),F(115,14))
    for rate,converted,finalsenior in [(F(1,20),F(26,5),F(49,5)),(F(3,20),F(28,5),F(47,5))]:
        eq('c10 funded capital conversion '+str(rate),5+4*rate,converted);eq('c10 old senior value '+str(rate),10-4*rate,finalsenior)
        eq('c10 aggregate surviving resources '+str(rate),60+finalsenior+4*rate,F(70))
    # C11: different exact algebra from the implementation's numerical square root.
    with localcontext() as context:
        context.prec=70;root2=D(2).sqrt();root42=D(42).sqrt();sale=D(100)-10*root2
        if abs(sale-sale*sale/200-49)>D('1e-60'):raise RuntimeError('c11 sale root residual')
        mixed=D('3.1')/(D('29.1')-10*root2)
        if not 0<mixed<1 or not D(26)>10*root2 or not 10*root42-20>D('34.1'):raise RuntimeError('c11 strategic inequalities')
        rows.append({'claim':'c11 independent radicals and strict game inequalities','sale_one_runner':str(sale),'mixed_probability':str(mixed),'sale_root_residual_below':'1e-60'})
    eq('c11 no-run retained shareholder value',80-2*F('34.1'),F('11.8'))
    eq('c11 RR partial-line auction proceeds',75*(1-F(75,200)),F(375,8))
    early=20+20+F(375,8)-18-62;late=25-20
    eq('c11 partial-line Beacon first receipt',early,F(55,8));eq('c11 partial-line customer missed',10-early,F(25,8));eq('c11 partial-line total claim',early+late,F(95,8))
    eq('c11 partial-line Beacon equity',early+late-10,F(15,8));eq('c11 buyer versus original loss',75-F(375,8),20+(20-early-late))
    eq('c11 full-line adverse taxpayer loss',80-100*F(3,5),F(20))
    for terminal,claim,loss in [(F(3,5),F(620,41),F(0)),(F(1,10),F(120,41),F(290,41))]:
        estate=2+100*terminal;recovery=min(F(1),estate/82);received=20*recovery
        eq('c11 resolution network '+str(terminal),received,claim);eq('c11 bridge loss '+str(terminal),max(F(0),10-received),loss)
    # C12 is coordinator-authored: this is a separate formula check, not a peer.
    eq('c12 minimum baseline first draw',5-(20+F('.97')*20-41-F('.3')*20),F('12.6'))
    eq('c12 last joint cash',5+45+3-22-F('1.03')*F('12.6')-F('.2')+20+2-11-F('20.2'),F('8.622'))
    eq('c12 concentration boundary',(116*F('.4')-36)/(1-F('.4')),F(52,3))
    eq('c12 all-event equity injection',20-(30+20-F('.02')*20-15-14-2),F('1.4'))
    eq('c12 false-positive threshold',(4+F('.05')*6)/10,F('.43'))
    out={'status':'passed','date':'2026-10-09','comparisons':len(rows),'method':'Fresh original-contract rational/Decimal arithmetic; imports no author code or saved output. Full manuscript proofs/exercises separately read. C12 is root-authored and requires separate peer.','results':rows}
    Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'status':'passed','comparisons':len(rows)}))


if __name__=='__main__':main()
