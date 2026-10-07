"""Original descriptive-graphics lab; standard library, no live data.

Print numerical report: python3 v04-c05-charts.py
Write four vector figures: python3 v04-c05-charts.py --write-figures figures
Keep v04-c05-data.json beside this script. See v04-c05-readme.txt.
"""
from fractions import Fraction as F
from html import escape
from pathlib import Path
from statistics import median
import argparse
import json
import math

HERE = Path(__file__).resolve().parent


def histogram(values, edges):
    if not values or len(edges) < 2 or any(b <= a for a,b in zip(edges,edges[1:])):
        raise ValueError('Need observations and strictly increasing bin edges')
    if any(not math.isfinite(x) for x in [*values,*edges]):
        raise ValueError('Values and edges must be finite')
    counts = [0]*(len(edges)-1)
    for x in values:
        if x < edges[0] or x > edges[-1]:
            raise ValueError('Bins must cover all observations')
        for j,(a,b) in enumerate(zip(edges,edges[1:])):
            if a <= x < b or (j == len(counts)-1 and x == b):
                counts[j] += 1
                break
    return [{'left':a,'right':b,'count':n,'share':F(n,len(values)),
             'density':F(n,len(values))/F(str(b-a))}
            for a,b,n in zip(edges,edges[1:],counts)]


def quartiles(values):
    ordered=sorted(values)
    n=len(ordered)
    if n < 4:
        raise ValueError('At least four observations for this half-sample convention')
    lower=ordered[:n//2]; upper=ordered[(n+1)//2:]
    return median(lower), median(ordered), median(upper)


def centered_sums(rows):
    n=len(rows)
    xbar=sum(F(str(r['x'])) for r in rows)/n
    ybar=sum(F(str(r['y'])) for r in rows)/n
    xx=sum((F(str(r['x']))-xbar)**2 for r in rows)
    yy=sum((F(str(r['y']))-ybar)**2 for r in rows)
    xy=sum((F(str(r['x']))-xbar)*(F(str(r['y']))-ybar) for r in rows)
    return {'x_mean':xbar,'y_mean':ybar,'xx':xx,'yy':yy,'xy':xy,
            'correlation':float(xy)/math.sqrt(float(xx*yy)) if xx*yy else None}


def report(data):
    values=data['income']['values'];q1,m,q3=quartiles(values)
    bins=histogram(values,data['income']['bin_edges'])
    revenue=data['revenue'];years=revenue['years']
    if len(years) != len(set(years)) or years != sorted(years):
        raise ValueError('Years must be unique and chronological')
    indexed={};growth={}
    for name in ('A','B'):
        levels=revenue[name]
        if len(levels) != len(years) or any(type(x) is not int or x <= 0 for x in levels):
            raise ValueError('Revenue requires aligned positive integer levels')
        indexed[name]=[F(100*x,levels[0]) for x in levels]
        growth[name]=[F(b,a)-1 for a,b in zip(levels,levels[1:])]
    rows=data['scatter']['rows']
    estimates=data['uncertainty']['estimates'];z=data['uncertainty']['critical']
    if len(estimates)!=2 or any(e['se']<=0 for e in estimates):
        raise ValueError('Two estimates with positive SE required')
    intervals=[{'label':e['label'],'mean':e['mean'],'lower':e['mean']-z*e['se'],
                'upper':e['mean']+z*e['se']} for e in estimates]
    diff=estimates[1]['mean']-estimates[0]['mean']
    se=math.hypot(*(e['se'] for e in estimates))
    return {'synthetic':True,'income':{'n':len(values),'mean':F(sum(values),len(values)),
        'median':m,'q1':q1,'q3':q3,'iqr':q3-q1,'upper_fence':q3+1.5*(q3-q1),
        'ecdf_at_20':F(sum(x<=20 for x in values),len(values)), 'bins':bins},
        'indexed_revenue':indexed,'annual_growth':growth,
        'scatter':{'pooled':centered_sums(rows),
                   'groups':{g:centered_sums([r for r in rows if r['group']==g]) for g in ('A','B')}},
        'uncertainty':{'marginal_intervals':intervals,'difference':diff,'difference_se':se,
                       'difference_interval':[diff-z*se,diff+z*se]}}


def document(title, description, content):
    # All labels are text-escaped; this is a small fixed-fixture renderer.
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="380" '
            'viewBox="0 0 640 380" role="img" aria-labelledby="title desc">'
            '<title id="title">'+escape(title)+'</title><desc id="desc">'+escape(description)+'</desc>'
            '<rect width="640" height="380" fill="white"/>'
            '<g font-family="system-ui, sans-serif" font-size="16" fill="#17263b">'+content+'</g></svg>')


def text(x,y,value,anchor='middle'):
    return f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}">{escape(str(value))}</text>'


def line(x1,y1,x2,y2,color='#c9d1dd',width=1,extra=''):
    return f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{color}" stroke-width="{width}" {extra}/>'


def axes(xrange,yrange,xticks,yticks,xlabel,ylabel):
    x0,x1=xrange;y0,y1=yrange
    X=lambda x:80+(x-x0)*520/(x1-x0)
    Y=lambda y:300-(y-y0)*240/(y1-y0)
    out=text(80,28,ylabel,'start')
    for y in yticks:
        out+=line(80,Y(y),600,Y(y))+text(69,Y(y)+5,f'{y:g}','end')
    for x in xticks:
        out+=line(X(x),300,X(x),306,'#17263b')+text(X(x),330,f'{x:g}')
    out+=line(80,60,80,300,'#17263b')+line(80,300,600,300,'#17263b')+text(340,365,xlabel)
    return X,Y,out


def figures(data,results):
    output={}
    X,Y,out=axes((0,80),(0,.03),[0,20,40,60,80],[0,.01,.02,.03],
                 'Annual income (thousand USD)','Density per thousand USD')
    for row in results['income']['bins']:
        a,b,h=row['left'],row['right'],float(row['density'])
        out+=f'<rect data-count="{row["count"]}" data-density="{h}" x="{X(a):g}" y="{Y(h):g}" width="{X(b)-X(a):g}" height="{Y(0)-Y(h):g}" fill="#355d86" fill-opacity="0.8" stroke="white"/>'
        out+=text((X(a)+X(b))/2,Y(h)-10,f'n={row["count"]}')
    output['v04-c05-histogram.svg']=document('Income histogram: area represents share',
        'Eight synthetic annual household incomes. Bin counts 4,3,1 with widths 20,20,40. Heights .025,.01875,.003125; areas .5,.375,.125.',out)

    X,Y,out=axes((2021,2024),(80,180),[2021,2022,2023,2024],[80,100,120,140,160,180],
                 'Year (synthetic annual revenue)','Revenue index: 2021 = 100')
    for name,color,dash in [('A','#ad253c',''),('B','#355d86','stroke-dasharray="8 5"')]:
        values=results['indexed_revenue'][name]
        pts=' '.join(f'{X(t):g},{Y(float(v)):g}' for t,v in zip(data['revenue']['years'],values))
        out+=f'<polyline data-series="{name}" points="{pts}" fill="none" stroke="{color}" stroke-width="3" {dash}/>'
        for t,v in zip(data['revenue']['years'],values):
            out+=f'<circle cx="{X(t):g}" cy="{Y(float(v)):g}" r="4" fill="{color}"/>'
        out+=text(530,Y(float(values[-1]))-12,f'{name}: {float(values[-1]):g}')
    output['v04-c05-index.svg']=document('Indexed revenue: proportional growth differs from levels',
        'Synthetic nominal revenue, common 2021 base100. A indexes100,120,144,172.8; B100,110,121,133.1. Vertical range80 to180, not zero.',out)

    X,Y,out=axes((0,10),(0,20),[0,2,4,6,8,10],[0,5,10,15,20],
                 'Training hours','Output units per worker')
    for row in data['scatter']['rows']:
        x,y=X(row['x']),Y(row['y'])
        if row['group']=='A':
            out+=f'<circle data-group="A" data-x="{row["x"]}" data-y="{row["y"]}" cx="{x:g}" cy="{y:g}" r="6" fill="#ad253c"/>'
        else:
            out+=f'<rect data-group="B" data-x="{row["x"]}" data-y="{row["y"]}" x="{x-6:g}" y="{y-6:g}" width="12" height="12" fill="#355d86"/>'
    out+=text(245,53,'A: circles   B: squares')
    output['v04-c05-scatter.svg']=document('Pooled and within-group associations differ',
        'Group A points (1,8),(2,7),(3,6); group B (7,18),(8,17),(9,16). Each group slopes downward; pooled correlation is positive. Six synthetic workers.',out)

    X=lambda x:80+(x-80)*520/50
    out=text(80,28,'Means and approximate 95% normal intervals (USD)','start')
    for x in range(80,131,10):
        out+=line(X(x),60,X(x),290)+text(X(x),330,x)
    for y,e in zip([125,230],results['uncertainty']['marginal_intervals']):
        out+=text(55,y+5,e['label'],'end')
        out+=line(X(e['lower']),y,X(e['upper']),y,'#355d86',4)
        out+=line(X(e['lower']),y-10,X(e['lower']),y+10,'#355d86',2)
        out+=line(X(e['upper']),y-10,X(e['upper']),y+10,'#355d86',2)
        out+=f'<circle cx="{X(e["mean"]):g}" cy="{y}" r="6" fill="#ad253c"/>'
        out+=text(X(e['mean']),y-24,f'{e["mean"]:g} [{e["lower"]:.2f}, {e["upper"]:.2f}]')
    out+=text(340,365,'Mean level (USD); intervals are not a difference test')
    output['v04-c05-intervals.svg']=document('Overlapping marginal intervals do not test the difference',
        'Independent normal mean estimates A100 and B112 dollars, each SE4. Marginal intervals92.16 to107.84 and104.16 to119.84 overlap; B-minus-A interval is approximately .91 to23.09 dollars.',out)
    return output


def encode(value):
    if isinstance(value,F):return {'exact':str(value),'decimal':float(value)}
    raise TypeError('Unexpected report value')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-figures',type=Path)
    args=parser.parse_args()
    data=json.loads((HERE/'v04-c05-data.json').read_text(encoding='utf-8'))
    results=report(data)
    if args.write_figures is not None:
        args.write_figures.mkdir(parents=True,exist_ok=True)
        for name,svg in figures(data,results).items():
            (args.write_figures/name).write_text(svg,encoding='utf-8')
    print(json.dumps(results,default=encode,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
