"""Check structure, dependencies, links, chapter packages and original arithmetic."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import json
import math
import re

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT/'dist'

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []; self.links = []; self.examples = 0
        self.exercise_depth = 0; self.exercise_count = 0; self.ol_depth = 0
        self.solution_depth = 0; self.solution_count = 0; self.detail_depth = 0
        self.sources = []; self.headings = []; self.lang = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if tag == 'html': self.lang = a.get('lang')
        if tag in ('a', 'link') and 'href' in a: self.links.append(a['href'])
        if tag in ('script','img') and 'src' in a: self.links.append(a['src'])
        if 'worked' in a.get('class','').split(): self.examples += 1
        if 'data-source' in a: self.sources.append(a['data-source'])
        if tag == 'ol':
            self.ol_depth += 1
            if 'exercises' in a.get('class','').split(): self.exercise_depth = self.ol_depth
        if tag == 'details':
            self.detail_depth += 1
            if 'solutions' in a.get('class','').split(): self.solution_depth = self.detail_depth
        if tag == 'li' and self.exercise_depth and self.ol_depth == self.exercise_depth:
            self.exercise_count += 1
        if tag == 'li' and self.solution_depth:
            self.solution_count += 1
        if tag in ('h1','h2','h3','h4'): self.headings.append(tag)
    def handle_endtag(self, tag):
        if tag == 'ol':
            if self.ol_depth == self.exercise_depth: self.exercise_depth = 0
            self.ol_depth -= 1
        if tag == 'details':
            if self.detail_depth == self.solution_depth: self.solution_depth = 0
            self.detail_depth -= 1

def check_arithmetic():
    near = lambda a,b: math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10)
    # Recompute every determinate result in the first two chapter packages.
    assert 4*25-10 == 90 and 130-90 == 40
    assert 45-10 == 35 and 35-40 == -5 and 35-(40+20) == -25
    assert 5*18-15 == 75 and 95-75 == 20
    assert 900+150 == 1050
    assert 90-20-80 == -10 and 90-20-(80+30) == -40
    assert 2700-2000 == 700 and 2700-8000-2000 == -7300
    assert 160-120 == 40
    net = [b-c for b,c in zip([30,25,18,10],[12,15,17,20])]
    totals = [sum(net[:n]) for n in range(5)]
    assert totals == [0,18,28,29,19] and totals.index(max(totals)) == 3
    assert near((100-80)/80,.25) and near((80-100)/100,-.2)
    assert near(1.25*.8,1) and near(1.1*1.2,1.32)
    assert near((4.25-4)/4,.0625)
    assert near((20+45)/(100+900),.065)
    assert near(.1*.2+.9*.05,.065)
    assert near((1.01**12-1)*100,12.682503013196978)
    assert near((23-20)/20,.15) and near((20-23)/23,-3/23)
    assert near(4.1-3.5,.6) and near((4.1-3.5)/3.5,6/35)
    assert near(200*.7*1.3,182) and near(.3/.7,3/7)
    assert near((40+120)/(400+600),.16)
    assert near(300*1.1+700*.95,995) and near(.3*.1+.7*(-.05),-.005)
    assert near(2400*1000/(3*1000000),.8)
    assert near(100/1000,.1) and near(108/1200,.09) and near((108-100)/100,.08)
    assert near((10-(-5))/(-5),-3) and near(1.1*.9,.99)
    # Chapter 3: solutions, slope units and original systems.
    assert 4+2*7 == 18 and 5*2+2*5 == 20
    assert 120-2*20 == 20+3*20 == 80
    assert (120-2*10)-(20+3*10) == 50
    assert [10+q*q for q in (1,2,3)] == [11,14,19]
    assert 6+3*4 == 18 and 6+3*7 == 27
    assert 10*4+5*5 == 65 and 7+4*6 == 31
    assert 150-3*24 == 30+2*24 == 78
    assert (150-3*20)-(30+2*20) == 20
    assert [20+2*q+q*q for q in range(4)] == [20,23,28,35]
    assert near(100*1.1**2,121)
    # Chapter 4: transaction and stock-flow reconciliations.
    assert 1000+300+20-150 == 1170
    assert 1000+600-500-300+450 == 1250
    assert 1250+500 == 600+(1000+450-300)
    assert (450-300)-500+(1000+600) == 1250
    assert 80+50-90-5 == 35
    assert 2000+8000-3000 == 3000+8000-4000 == 2500+8000-3500 == 7000
    assert 1200-700 == 500
    assert 100+(900-600)-200+(300-150) == 350
    assert (500+200)+(300-200) == 500+300 == 800
    # Chapter 5: cash-flow schedules independently verify formula results.
    assert near(500*1.08**3,629.856)
    assert near(500*(1+3*.08),620)
    assert near((2000/1.05**3)*1.05**3,2000)
    assert near(-1000+600/1.1+600/1.1**2,50/1.1**2)
    assert near(-1000+600/1.2+600/1.2**2,-250/3)
    loan_payment = 1200*.01/(1-1.01**-12)
    assert near(loan_payment,106.618546414010)
    loan_balance = 1200.
    for _ in range(12): loan_balance = loan_balance*1.01-loan_payment
    assert abs(loan_balance)<1e-8
    assert near(sum(200/1.1**t for t in range(1,4)),200*(1-1.1**-3)/.1)
    assert near(sum(100/1.1**t for t in range(3)),273.553719008264)
    assert near(-900+500/1.1+500/1.1**2,-32.231404958678)
    assert round((1.005**12-1)*100,2)==6.17
    assert round((1.08/1.03-1)*100,2)==4.85
    discount_base=(600+math.sqrt(2760000))/2000
    assert near(600/discount_base+600/discount_base**2,1000)
    # Chapter 6: marginal choices and economic incidence equations.
    assert sum([20-8,20-12,20-18])==22
    assert sum([15-8,15-12])==10
    assert near(120-2*22.4,20+3*18.4)
    assert near(4*75.2,300.8)
    assert sum([12-4,12-8,12-11])==13
    assert sum([9-4,9-8])==6
    assert 100-2*30==10+30==40
    assert 130-2*40==10+40==50
    assert 100-2*32==10+26==36 and 6*36==216
    assert 100-2*20==60 and 10+20==30
    assert near(((45-50)/50)/((12-10)/10),-.5)

def main():
    plan = json.loads((ROOT/'content/curriculum.json').read_text())
    source_ids = {s['id'] for s in json.loads((ROOT/'content/sources.json').read_text())}
    volumes = {v['id']: v for v in plan['volumes']}
    chapters = {c['id']: c for v in plan['volumes'] for c in v['chapters']}
    errors = []
    require = lambda condition,message: errors.append(message) if not condition else None
    require(len(volumes)==18 and len(chapters)==216,'Curriculum scope differs from contract')
    all_ids = set(volumes)|set(chapters)
    graph = {v['id']:v['prerequisites'] for v in volumes.values()}
    graph.update({c['id']:c['prerequisites'] for c in chapters.values()})
    for name,deps in graph.items():
        require(all(dep in all_ids for dep in deps),f'{name}: unknown prerequisite')
    visiting,done = set(),set()
    def visit(name):
        if name in visiting: raise ValueError(f'Prerequisite cycle at {name}')
        if name in done: return
        visiting.add(name)
        for dep in graph[name]:
            if dep in graph: visit(dep)
        visiting.remove(name); done.add(name)
    try:
        for name in graph: visit(name)
    except ValueError as exc: errors.append(str(exc))
    available = 0
    for c in chapters.values():
        path = ROOT/'content'/c['manuscript']
        require(set(c['sources']) <= source_ids,f'{c["id"]}: missing source entry')
        if not path.exists():
            require(c['status']=='planned',f'{c["id"]}: non-planned status without manuscript')
            continue
        available += 1; text = path.read_text(); parsed = Document(); parsed.feed(text)
        require(c['status'] in ('draft','review','accepted'),f'{c["id"]}: manuscript still labeled planned')
        require(parsed.examples >= c['required_worked_examples'],f'{c["id"]}: too few worked examples')
        require(parsed.exercise_count >= c['required_exercises'],f'{c["id"]}: too few exercises')
        require(parsed.solution_count >= parsed.exercise_count,f'{c["id"]}: missing solutions/evaluation criteria')
        require(set(parsed.sources) <= source_ids,f'{c["id"]}: unknown citation')
        require('Teach-back' in text and 'Delayed check' in text,f'{c["id"]}: missing teaching/retention check')
        if c['status']=='accepted':
            require(all(c['review'].values()),f'{c["id"]}: acceptance without complete review record')
    pages = {}
    for path in DIST.glob('*.html'):
        doc = Document(); doc.feed(path.read_text()); pages[path.name]=doc
        require(len(doc.ids)==len(set(doc.ids)),f'{path.name}: duplicate IDs')
        require(doc.lang=='en',f'{path.name}: missing language')
        require(doc.headings.count('h1')==1 or path.name=='print.html',f'{path.name}: missing/duplicate primary heading')
    for name,doc in pages.items():
        for href in doc.links:
            url = urlsplit(href)
            if url.scheme or url.netloc: continue
            target = (DIST/url.path) if url.path else DIST/name
            require(target.is_file(),f'{name}: missing local target {href}')
            if url.fragment and target.name in pages:
                require(unquote(url.fragment) in pages[target.name].ids,f'{name}: missing anchor {href}')
    check_arithmetic()
    report = {'status':'failed' if errors else 'passed','chapter_packages_available':available,
              'html_pages_checked':len(pages),'curriculum_chapters':len(chapters),
              'checks':['curriculum scope','acyclic prerequisites','chapter package structure','local links and anchors','source IDs','Volume 1 chapters 1–6 worked-example and solution arithmetic'],
              'errors':errors,'limitations':['These checks do not certify all subject-matter claims or externally assess learner competence.']}
    (ROOT/'verification-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
    if errors: raise SystemExit(1)

if __name__=='__main__':
    main()
