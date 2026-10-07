"""Independent descriptive statistics, contrast and actual SVG coordinate audit."""
from fractions import Fraction as F
from pathlib import Path
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

PROJECTS=Path(__file__).resolve().parents[1]/'content/projects'
SVG='{http://www.w3.org/2000/svg}'


def near(a,b,tol=1e-9):
    assert math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol),(a,b)


def check():
    spec=importlib.util.spec_from_file_location('descriptive_lab',PROJECTS/'v04-c05-charts.py')
    lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)
    data=json.loads((PROJECTS/'v04-c05-data.json').read_text())
    result=lab.report(data);checks=[]
    vals=data['income']['values']; n=len(vals)
    assert sum(vals)==200 and F(sum(vals),n)==25
    assert sorted(vals)[3:5]==[18,20] and result['income']['median']==19
    assert (result['income']['q1'],result['income']['q3'],result['income']['iqr'])==(13.5,23.5,10)
    assert result['income']['upper_fence']==38.5 and F(sum(x<=20 for x in vals),n)==F(5,8)
    rows=result['income']['bins']
    assert [r['count'] for r in rows]==[4,3,1]
    assert [r['density'] for r in rows]==[F(1,40),F(3,160),F(1,320)]
    assert sum(r['density']*(r['right']-r['left']) for r in rows)==1
    assert F(78,sum(vals))==F(39,100) and F(sum(vals)-78,n-1)==F(122,7)
    for reordered in [vals[::-1],vals[3:]+vals[:3]]:
        assert lab.histogram(reordered,[0,20,40,80])==rows
    assert [r['count'] for r in lab.histogram(vals,[0,20,40,60,80])]==[4,3,0,1]
    edges=lab.histogram([0,20,40,80],[0,20,40,80])
    assert [r['count'] for r in edges]==[1,1,2]
    scaled=lab.histogram([v*1000 for v in vals],[0,20000,40000,80000])
    for original,converted in zip(rows,scaled):
        assert converted['share']==original['share']
        assert converted['density']==original['density']/1000
    ex=[0,0,2,4,4,8,8,14]
    assert F(sum(ex),len(ex))==5 and lab.quartiles(ex)==(1,4,8)
    assert F(sum(x<=4 for x in ex),8)==F(5,8)
    assert [r['density'] for r in lab.histogram(ex,[0,4,8,16])]==[F(3,32),F(1,16),F(3,64)]
    wrong_areas=[r['share']*(r['right']-r['left']) for r in rows]
    assert wrong_areas==[F(10),F(15,2),F(5)]
    assert wrong_areas[-1]/sum(wrong_areas)==F(2,9)
    for v,e in [([],[0,1]),([1],[0,0,2]),([3],[0,2]),([math.nan],[0,2])]:
        try:lab.histogram(v,e)
        except ValueError:pass
        else:raise AssertionError('Invalid histogram accepted')
    checks.append('Exact income/order statistics, ECDF and median convention; unequal-bin areas, edges, empty bin, order invariance, unit conversion, outlier sensitivity and both distribution exercises')

    for name,g in [('A',F(1,5)),('B',F(1,10))]:
        assert result['annual_growth'][name]==[g]*3
        assert result['indexed_revenue'][name]==[100*(1+g)**t for t in range(4)]
    assert F(1728,1200)*100==144 and F(13310,11000)*100==121
    assert F(1000,1200)*100==F(250,3) and F(10000,11000)*100==F(1000,11)
    assert 1728-1200==528 and 13310-11000==2310
    assert F(1728,1000)-1==F(91,125) and F(13310,10000)-1==F(331,1000)
    assert F(220-200,200)==F(1,10) and F(220-180,200-180)==2
    assert F(40,2000)*1000==20 and F(80,10000)*1000==8
    assert F(100+121,2)==F(221,2)
    assert F(221,200)-1==F(21,200) and F(121)/F(221,2)-1==F(21,221)
    assert F(11,10)**2==F(121,100)
    near(math.log(1.2),.1823215567939546)
    checks.append('Exact growth and rebasing; nominal-level versus index gains, misleading bar-length ratio, incident denominators, log change and distinct linear/geometric missing-month interpolations')

    rows=data['scatter']['rows'];n=len(rows)
    # Raw-sum identities are independent of lab's centered sum implementation.
    sx=sum(r['x'] for r in rows);sy=sum(r['y'] for r in rows)
    xx=sum(r['x']**2 for r in rows)-F(sx*sx,n)
    yy=sum(r['y']**2 for r in rows)-F(sy*sy,n)
    xy=sum(r['x']*r['y'] for r in rows)-F(sx*sy,n)
    assert (xx,yy,xy)==(58,154,86)
    assert result['scatter']['pooled']['xy']==xy
    near(result['scatter']['pooled']['correlation'],float(xy)/math.sqrt(float(xx*yy)))
    assert 3*(-3)*(-5)+3*3*5==90 and -2-2+90==86
    for group in result['scatter']['groups'].values():
        assert (group['xx'],group['yy'],group['xy'],group['correlation'])==(2,2,-2,-1)
    curve=[{'x':x,'y':x*x} for x in range(-2,3)]
    assert sum(r['x']*(r['y']-2) for r in curve)==0
    assert lab.centered_sums(curve)['correlation']==0
    checks.append('Raw-sum and group-decomposition cross-check of positive pooled/negative within-group correlation; nonlinear zero-correlation exercise')

    intervals=result['uncertainty']['marginal_intervals']
    assert [(e['lower'],e['upper']) for e in intervals]==[(92.16,107.84),(104.16,119.84)]
    assert max(e['lower'] for e in intervals)<min(e['upper'] for e in intervals)
    low,high=result['uncertainty']['difference_interval']
    near(low,12-1.96*math.sqrt(32));near(high,12+1.96*math.sqrt(32));assert low>0
    covariance=F(-3,4)*4*4;assert covariance==-12 and 16+16-2*covariance==56
    near(12-1.96*math.sqrt(56),-2.66729695615385)
    near(12+1.96*math.sqrt(56),26.66729695615385)
    assert (12-1.96*math.sqrt(56))<0
    # Standard normal CDF via erf confirms the declared approximately-95% level.
    near(math.erf(1.96/math.sqrt(2)),.9500042097035591)
    checks.append('Marginal overlap versus direct independent contrast interval; negative-dependence covariance and changed conclusion with unchanged marginals; approximate normal coverage')

    generated=lab.figures(data,result)
    for name,body in generated.items():
        assert (PROJECTS/name).read_text()==body,name
        element=ET.fromstring(body)
        assert element.tag==SVG+'svg' and element.attrib['viewBox']=='0 0 640 380'
        assert element.find(SVG+'title').text and element.find(SVG+'desc').text
        assert not element.findall('.//'+SVG+'script')
    histogram=ET.fromstring(generated['v04-c05-histogram.svg'])
    bars=[e for e in histogram.iter(SVG+'rect') if 'data-count' in e.attrib]
    expected=[(80,100,130,200),(210,150,130,150),(340,275,260,25)]
    areas=[]
    for e,coords in zip(bars,expected):
        assert tuple(float(e.attrib[k]) for k in ['x','y','width','height'])==coords
        areas.append(F(e.attrib['width'])*F(e.attrib['height']))
    assert len(bars)==3 and [a/sum(areas) for a in areas]==[F(1,2),F(3,8),F(1,8)]
    index=ET.fromstring(generated['v04-c05-index.svg'])
    for path in index.iter(SVG+'polyline'):
        name=path.attrib['data-series'];coords=[tuple(map(float,p.split(','))) for p in path.attrib['points'].split()]
        for t,(x,y) in enumerate(coords):
            near(x,80+520*t/3,tol=1e-5)
            near(y,300-(float(result['indexed_revenue'][name][t])-80)*2.4,tol=1e-5)
    scatter=ET.fromstring(generated['v04-c05-scatter.svg'])
    marks=[e for e in scatter.iter() if 'data-group' in e.attrib]
    assert len(marks)==6
    for e in marks:
        a=e.attrib;x=80+52*float(a['data-x']);y=300-12*float(a['data-y'])
        if e.tag==SVG+'circle':near(a['cx'],x);near(a['cy'],y)
        else:near(float(a['x'])+6,x);near(float(a['y'])+6,y)
    interval=ET.fromstring(generated['v04-c05-intervals.svg'])
    spans=[e for e in interval.iter(SVG+'line') if e.attrib['stroke-width']=='4']
    assert len(spans)==2
    for e,values in zip(spans,intervals):
        near(e.attrib['x1'],80+10.4*(values['lower']-80))
        near(e.attrib['x2'],80+10.4*(values['upper']-80))
    checks.append('Actual delivered SVGs regenerate exactly; XML titles/descriptions, histogram pixel-area shares, revenue-line coordinates, all six scatter marks and marginal interval endpoints independently verified')

    with tempfile.TemporaryDirectory(prefix='mastery-v04-c05-') as temporary:
        folder=Path(temporary)
        for name in ['v04-c05-charts.py','v04-c05-data.json']:shutil.copy2(PROJECTS/name,folder/name)
        command=[sys.executable,str(folder/'v04-c05-charts.py'),'--write-figures',str(folder/'figures')]
        run=subprocess.run(command,cwd=folder.parent,text=True,capture_output=True,check=True)
        parsed=json.loads(run.stdout)
        assert parsed['income']['mean']['exact']=='25'
        assert parsed['scatter']['pooled']['xy']['exact']=='86'
        for name,body in generated.items():assert (folder/'figures'/name).read_text()==body
    checks.append('Clean copied input/program executes offline from another directory and generates the same four vector artifacts and numerical report')
    return {'status':'passed','checks':checks,'limitations':['Synthetic descriptive fixtures and explicitly stipulated normal estimator model; no empirical or causal claim.','Numerical/SVG-coordinate and XML checks are separate from browser visual/mobile/print QA, which remains pending.','Finite behavior checks and internal author review are not independent human academic validation.']}


if __name__=='__main__':print(json.dumps(check(),indent=2))
