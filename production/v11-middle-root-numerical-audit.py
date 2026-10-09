"""Coordinator's original arithmetic oracle; no author implementation imports."""
from fractions import Fraction as F
import json
import math

COUNT=0
def equal(a,b,label):
    global COUNT
    COUNT+=1
    if a!=b:raise RuntimeError(label+': '+repr(a)+' != '+repr(b))
def near(a,b,label,tol=1e-9):
    global COUNT
    COUNT+=1
    if not math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol):raise RuntimeError(label)

def check():
    base_net=[F('17.6'),F(5),F(10),F('-21.5')]
    joint_net=[F('-29.4'),F('-26.5'),F(10),F('33.71')]
    def prefix(net):return [F(16)+sum(net[:t]) for t in range(1,5)]
    equal(prefix(base_net),list(map(F,['33.6','38.6','48.6','27.1'])),'c05 base cash')
    rollover=base_net.copy();rollover[0]-=40;rollover[-1]+=F('40.6')
    equal(prefix(rollover),list(map(F,['-6.4','-1.4','8.6','27.7'])),'c05 rollover cash')
    equal(prefix(joint_net),list(map(F,['-13.4','-39.9','-29.9','3.81'])),'c05 joint cash')
    equal(max(-x for rows in [prefix(base_net),prefix(rollover),prefix(joint_net)] for x in rows),F('39.9'),'c05 robust cash minimum')
    equal(F('.01')*(30+F('24.5')+F('24.5')),F('.79'),'c05 interval interest')
    equal(30-50*F('.7')*F('.7'),F('5.5'),'c05 collateral paydown')
    equal(30-F('37.5')*F('.7')*F('.7'),F('11.625'),'c05 unavailable collateral transfer')
    equal(F('3.81')/F('.02'),F('190.5'),'c05 bridge upper bound')
    equal(F('3.81')/F('.1'),F('38.1'),'c05 impossible bridge upper bound')
    equal(F('7.81')+92+80-129-24,F('26.81'),'c05 closing book equity')
    equal(F('26.81')-80*F('.3'),F('2.81'),'c05 conditional marked equity')
    def alm(y):
        asset=5/(1+y)+105/(1+y)**2
        fixed=sum(4/(1+y)**t for t in range(1,6))+80/(1+y)**5
        floating=sum(20*y/(1+y)**t for t in range(1,6))+20/(1+y)**5
        equal(floating,20,'c05 reset par telescoping')
        return 10+asset-fixed-floating,1-20*y
    equal(alm(F('.05')),(F(10),F(0)),'c05 reference ALM')
    e,n=alm(F('.07'));near(e,F('12.9442795625'),'c05 increased EVE');equal(n,F('-.4'),'c05 lower NII')
    alm(F(0))
    derivative=-5/F('1.05')**2-210/F('1.05')**3+sum(4*t/F('1.05')**(t+1) for t in range(1,6))+400/F('1.05')**6
    near(derivative,F('160.417091'),'c05 derivative',1e-8)

    # The deadline cut proves the minimum independently of a scheduling loop.
    equal(12-(2+2+4),4,'c06 deadline3 unavoidable misses')
    corrected={1:['A01','A02'],2:['A03','A04'],3:['B01','B02','B03','B04','B05','C01','C02','C03'],4:['D01','D02']}
    equal(sum(map(len,corrected.values())),14,'c06 correction preserves jobs')
    for time,ids in corrected.items():
        for key in ids:
            release,deadline={'A':(1,2),'B':(2,3),'C':(3,3),'D':(4,4)}[key[0]]
            equal(release<=time<=deadline,True,'c06 constructive feasible allocation')
    observed=['A01','A02','A03','A04','B01','B02','B03','B04','B05','C01','C02','B02','D01','D02']
    equal(len(observed),14,'c06 aggregate debit count');equal(len(set(observed)),13,'c06 distinct discharges')
    equal((200-10*len(observed),140-10*len(set(observed)),60-10*(len(observed)-len(set(observed)))),(60,10,50),'c06 observed accounts')
    c,q1,q2,f=map(F,['.05','.1','.2','.8'])
    # Enumerate independent noncommon failure/coverage branches plus common event.
    escape=c
    for first,prob1 in [(False,1-q1),(True,q1)]:
        for second,prob2 in [(False,1-q2),(True,q2)]:
            for covered,probf in [(False,1-f),(True,f)]:
                if first and (not covered or second):escape+=(1-c)*prob1*prob2*probf
    equal(escape,F('.0842'),'c06 branch-enumerated escape')
    equal(1000*F('.02')*25*escape,F('42.1'),'c06 expected loss')
    equal((F('.04')-F('.02'))/F('.98'),F(1,49),'c06 common cause boundary')
    equal((F('.1')-F('.04'))/F('.08'),F('.75'),'c06 coverage boundary')
    equal(F('42.1')-10-12,F('20.1'),'c06 net intervention benefit')
    equal(F(1*2+2*4+4*8,1+4+16),2,'c06 fitted through-origin rate')

    # Direct substitution on the two partial-payment equations.
    for b,c,pb,pc in [(2,8,8,12),(F(4),F(6),F(28,3),F(32,3))]:
        equal((pb,pc),(min(20,b+pc/2),min(20,c+pb/2)),'c07 clearing equations')
        equal(b+c,(pb+pc)/2,'c07 external conservation, both partial')
    P=F('110.25')/F('1.15')**2;Q=F('67.2')/F('1.15')
    E=P+Q+4-F(145)-2
    equal(P,F(44100,529),'c07 nonlinear bond')
    equal(E,F(-635,529),'c07 joint equity')
    margin=20-P/8;cap=3*P/8; paid=14+20-margin
    equal(margin,F(10135,1058),'c07 old margin')
    equal(paid,F(25837,1058),'c07 actual withdrawal payment')
    equal(40-paid,F(16483,1058),'c07 unpaid withdrawals')
    equal(137-paid,F(119109,1058),'c07 remaining deposit liability')
    equal((137-paid)+(20-margin)+20,F(143),'c07 closing liability ledger')
    equal(P+Q-F(143),E,'c07 independent closing equity')
    equal(40-(14+cap-margin),F(2284,529),'c07 facility beyond collateral')
    maximum=F(8800,529)+F(520,17)+6+2
    equal(maximum,F(496624,8993),'c07 standalone sum')
    equal(maximum-F(24440,529),F(3528,391),'c07 incompatible maxima gap')
    equal(80*F('.2')-84*F('.2')/F('1.15'),F(32,23),'c07 credit attribution interaction')
    def boundary(kind,extra_cash=F(0),extra_equity=F(0),floor=F(2)):
        def polynomial(x):
            z=F('1.05')+F('.1')*x
            if kind=='capital':return F('110.25')+84*(1-F('.2')*x)*z-(143+10*x-extra_equity)*z*z
            return (4-floor+extra_cash-30*x)*z*z+F('110.25')*(F('.2')-F('.075')*x)
        lo,hi=F(1,3),F(1)
        equal(polynomial(lo)>0 and polynomial(hi)<0,True,'c07 unique relevant interval')
        for _ in range(50):
            mid=(lo+hi)/2
            if polynomial(mid)>0:lo=mid
            else:hi=mid
        return float((lo+hi)/2)
    baseline_f=boundary('funding');baseline_k=boundary('capital')
    near(baseline_f,.545784230258,'c07 funding root')
    near(baseline_k,.751688814506,'c07 capital root')
    near(boundary('funding',floor=F(0)),.596675093210,'c07 zero-cash threshold')
    near(boundary('funding',extra_cash=F(5)),.673395979956,'c07 cash-injection boundary')
    near(boundary('capital',extra_equity=F(5)),.861274373503,'c07 equity-injection boundary')
    z=1.05+.1*baseline_f
    near(110.25/z**2+84*(1-.2*baseline_f)/z-133-10*baseline_f,19.650135,'c07 equity at first trigger',1e-7)
    return {'status':'passed','comparisons':COUNT,'scope':'Independent coordinator recomputation of all central c05–c07 worked anchors and numerical transfer/proof boundaries; no author code imports. Full manuscript reading recorded separately; source, code, peer and final payload gates remain separate.','chapters':['v11-c05','v11-c06','v11-c07'],'roots':{'funding':baseline_f,'capital':baseline_k}}

if __name__=='__main__':print(json.dumps(check(),indent=2))
