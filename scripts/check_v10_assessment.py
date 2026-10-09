"""Independent support arithmetic and final assembly gates for Volume 10."""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PARTS=('v10-support-opening.html','v10-exam-a.html','v10-exam-b.html','v10-project.html','v10-support-closing.html')


def need(condition,label):
    if not condition:raise RuntimeError(label)


class SupportHTML(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.points={};self.solutions=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if 'data-points' in d and tag=='li':
            need('id' in d,'scored semantic list prompt')
            need(d['id'] not in self.points,'unique scored prompt')
            self.points[d['id']]=int(d['data-points'])
        if 'data-solution-for' in d:self.solutions.append(d['data-solution-for'])
        if tag=='a':self.links.append(d.get('href',''))
        if tag not in ('br','hr','img','input','meta','link'):self.stack.append(tag)
    def handle_endtag(self,tag):
        need(self.stack and self.stack[-1]==tag,'balanced support '+tag);self.stack.pop()


def support_check():
    count=0
    def eq(got,want,label):
        nonlocal count
        count+=1
        need(got==want,label+': '+repr(got)+' != '+repr(want))
    def near(got,want,label,tol=2e-9):
        nonlocal count
        count+=1
        need(math.isclose(got,want,rel_tol=tol,abs_tol=tol),label)
    # Diagnostic exact cash, covariance and replication, independent of project.
    eq(12*F('.97')+112*F('.92'),F('114.68'),'D1 dated strip cost')
    eq(12*(F('.97')-F('.92')),F('.6'),'D1 moved receipt')
    near(100*math.expm1(-.02),-1.98013266932447,'D2 finite rate change')
    eq(-200*F('.01')+F(400,2)*F('.01')**2,F('-1.98'),'D2 Taylor')
    eq(9*F('.04')+4*F('.09'),F('.72'),'D3 independent variance')
    eq(9*F('.04')+4*F('.09')-12*F('.03'),F('.36'),'D3 covariance')
    eq(F('.5')*60-30,F(0),'D4 down replica');eq(F('.5')*120-30,F(30),'D4 up replica')
    eq(F('.5')*90-30*F('.95'),F('16.5'),'D4 price')
    eq(F('.4')+F('.55'),F('.95'),'D4 bank state prices');eq(F('.4')*60+F('.55')*120,F(90),'D4 stock state prices')
    eq((F('-.1')-F('1.96')*F('.2'),F('-.1')+F('1.96')*F('.2')),(F('-.492'),F('.292')),'D5 interval')
    eq((F(23**2-20**2,50),F('0.8')*3+F('0.04')*9/2),(F('2.58'),F('2.58')),'D6 quadratic identity')
    eq((3*35-100*F('1.02'),2*35-(100*F('1.02')-35)),(F(3),F(3)),'D7 financed rebalancing')
    eq(F(5)-(3*35-100*F('1.02')),F(2),'D7 external transfer')

    # Oral transfers; the drift proof is checked algebraically, not by simulation.
    eq(F(300-500,2)*F('.01')**2,F('-.01'),'O1 unmatched curvature')
    eq(3+4-5,2,'O2 actual due-date cash gap')
    eq(2*F('.02')+F('.3')**2,F('.13'),'O3 Ito drift')
    eq(2*F('.02')+F('.3')**2-F('.02'),F('.11'),'O3 discounted drift')
    near(100*math.exp(.11),111.62780704588713,'O3 squared-stock expectation')
    eq((F(14+5,2)-9,F(14+5,2)-10),(F('.5'),F('-.5')),'O4 butterfly prices')
    eq((98+2*F('-.25'),98+2*F('.25')),(F('97.5'),F('98.5')),'O5 null direction range')

    # Retention1–2: original curve, independently dated carry and credit legs.
    d1=F(97,100);d2=(F('99.35')-5*d1)/105
    eq(d2,F('.9'),'R1 bootstrap');eq(d1/d2-1,F(7,90),'R1 forward')
    eq(150*d2,F(135),'R1 liability PV');eq(-2*150*d2*F('.002'),F('-.54'),'R1 local zero-rate change')
    near(135*math.expm1(-.004),-.53892143856115,'R1 exact key-rate change')
    prepaid=48-2*F('.99');eq(prepaid,F('46.02'),'R2 dividend strip')
    eq(prepaid/F('.94'),F(2301,47),'R2 forward');eq(prepaid-49*F('.94'),F('-.04'),'R2 existing forward')
    receipt=F('.92')*100+F('.08')*35
    eq(receipt,F('94.8'),'R2 contingent cash');eq(receipt*F('.94'),F('89.112'),'R2 note PV')
    eq(F('.94')*(100-receipt),F('4.888'),'R2 loss PV')
    spread=F('.08')*65/(100*F('.92'));eq(spread,F(13,230),'R2 hypothetical survival-only premium')
    eq(100*spread*F('.92')*F('.94'),65*F('.08')*F('.94'),'R2 zero upfront identity')

    # Retention3: statewise replica and finite normal-density square completion.
    delta=F(18,30);cash=-40*delta
    eq((40*delta+cash,70*delta+cash),(F(0),F(18)),'R3 matched contingent payoffs')
    eq(50*delta+cash/F('1.05'),F(50,7),'R3 replica price')
    eq((F('1.05')*50-40)/30,F(5,12),'R3 pricing up probability')
    eq(F('.08')-F('.2')**2/2,F('.06'),'R3 physical log drift')
    tilt=(F('.08')+F('.01')-F('.03'))/F('.2');eq(tilt,F('.3'),'R3 constant tilt')
    eq(F('.08')-F('.2')*tilt-F('.2')**2/2,F(0),'R3 pricing log drift')
    # Coefficients in -(w+lambda*t)^2/(2t) agree with likelihood times normal density.
    for time in (F(1,4),F(1),F(3)):
        for w in (F(-2),F(0),F(3)):
            eq(-w*w/(2*time)-tilt*w-tilt*tilt*time/2,-(w+tilt*time)**2/(2*time),'R3 completed Gaussian exponent')

    # Retention4: signed local mark and correct independent sampling units.
    change=F('.45')*2+F('.02')*4/2+30*F('.01')-5*F(1,250)
    eq(change,F('1.22'),'R4 Greek mark');eq(-200*change+90*2,F(-64),'R4 share-offset mark')
    eq(F(6**2,400),F('.09'),'R4 raw mean variance');eq(F(3**2,200),F('.045'),'R4 pair mean variance')
    near(1.96*6/math.sqrt(400),.588,'R4 raw half-width')
    near(1.96*3/math.sqrt(200),.41577878733769,'R4 pair half-width')

    # Retention5: null family and two statewise hedge certificates.
    disc=F('.95');forward=50/disc
    for a in (F(0),F(1,57),F(5,19),F(25,57),F(26,57)):
        law=(a,F(52,57)-2*a,a+F(5,57))
        eq(sum(law),1,'R5 normalized law');eq(sum(p*x for p,x in zip(law,(20,50,80))),forward,'R5 stock calibration')
        eq(disc*30*law[2],F(5,2)+F(57,2)*a,'R5 price family')
    eq((50-50*disc,F(50,2)-10*disc),(F('2.5'),F('15.5')),'R5 endpoint costs')
    eq([h-(s-50) for s,h in zip((20,50,80),(0,0,30))],[30,0,0],'R5 lower arbitrage')
    eq([F(s,2)-10-h for s,h in zip((20,50,80),(0,0,30))],[0,15,0],'R5 upper arbitrage')
    eq((F('.02')*600,F('.02')*400),(F(12),F(8)),'R5 aggregated unit comparison')

    parser=SupportHTML()
    for name in (PARTS[0],PARTS[-1]):
        parser.feed((ROOT/'content/assessments/parts'/name).read_text());need(not parser.stack,'closed support fragment')
    eq(len(parser.ids),len(set(parser.ids)),'unique support anchors')
    for prefix,n,points in [('v10-d',8,5),('v10-o',5,4),('v10-r',5,20)]:
        wanted={prefix+str(i):points for i in range(1,n+1)}
        actual={k:v for k,v in parser.points.items() if k.startswith(prefix)}
        eq(actual,wanted,'complete scored '+prefix)
    eq(set(parser.solutions),set(parser.points),'every support prompt has an answer')
    eq(len(parser.solutions),len(parser.points),'no duplicate support answer')
    curriculum=json.loads((ROOT/'content/curriculum.json').read_text())
    chapterids={c['id'] for volume in curriculum['volumes'] for c in volume['chapters']}
    for link in parser.links:
        base=link.split('#')[0]
        if base.endswith('.html') and base[:-5] in chapterids:
            need((ROOT/'content/chapters'/base).is_file() or base.startswith('v11-'),'valid authored or explicitly planned extension route')
    path=ROOT/'content/reviews/v10-support-author.json'
    bindings=0
    if path.exists():
        for item in json.loads(path.read_text())['reviewed_hashes']:
            payload=(ROOT/item['path']).read_bytes();eq(hashlib.sha256(payload).hexdigest(),item['sha256'],'support author binding');bindings+=1
    return {'status':'passed','comparisons':count,'diagnostic_items':8,'diagnostic_points':40,'oral_transfers':5,'oral_points':20,
            'retention_items':5,'retention_points':100,'author_payload_hashes_verified':bindings,
            'count_definition':'Actual support arithmetic, probability-law/cash identities, prompt/answer structure and artifact-binding comparisons.',
            'limits':'Authored assessment design, not empirically equated timings/thresholds, demonstrated learner competence, external certification or UI QA.'}


def check():
    result=support_check()
    parts=[(ROOT/'content/assessments/parts'/name).read_text().strip() for name in PARTS]
    actual=(ROOT/'content/assessments/v10.html').read_text()
    need(actual=='\n\n'.join(parts)+'\n','assessment exactly assembles five frozen parts')
    parser=SupportHTML();parser.feed(actual);need(not parser.stack,'balanced full assessment')
    need(len(parser.ids)==len(set(parser.ids)),'unique full assessment anchors')
    for anchor in ('diagnostic','exam-rules','form-a','solutions-a','form-b','solutions-b','project','oral-transfer','retention','notation-index','concept-index','volume-synthesis'):
        need(anchor in parser.ids,'required assessment section '+anchor)
    result['assembly_parts']=list(PARTS)
    from check_v10_exam_a import check as exam_a
    from check_v10_exam_b import check as exam_b
    from check_v10_project import check as project
    from check_v10_exam_a_peer import check as peer_a
    from check_v10_exam_b_peer import check as peer_b
    from check_v10_project_peer import check as peer_project
    from check_v10_support_peer import check as peer_support
    result['component_checks']={name:checker() for name,checker in (
        ('exam_a_author',exam_a),('exam_b_author',exam_b),('project_author',project),
        ('exam_a_peer',peer_a),('exam_b_peer',peer_b),('project_peer',peer_project),('support_peer',peer_support))}
    json.dumps(result,allow_nan=False)
    return result


if __name__=='__main__':
    print(json.dumps(support_check() if '--support-only' in sys.argv else check(),indent=2))
