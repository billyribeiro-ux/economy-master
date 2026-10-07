"""Check structure, dependencies, links, chapter packages and original arithmetic."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import json
import math
import re
import importlib.util
from check_v02_calculus import check as check_v02_calculus
from check_v02_linear import check as check_v02_linear
from check_v02_optimization import check as check_v02_optimization
from check_v02_duality import check as check_v02_duality
from check_v02_analysis import check as check_v02_analysis
from check_v02_dynamics import check as check_v02_dynamics
from check_v02_numerics import check as check_v02_numerics
from check_v02_assessment import check as check_v02_assessment
from check_v03_probability import check as check_v03_probability
from check_v03_moments import check as check_v03_moments
from check_v03_conditioning_limits import check as check_v03_conditioning_limits
from check_v03_estimation_inference import check as check_v03_estimation_inference
from check_v03_bayes_utility import check as check_v03_bayes_utility

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
    # Chapters 7–8: basket/deflator and conditional-count calculations.
    assert 2*2+3*10==34 and 2*3+3*11==39
    assert near((4/34)*.5+(30/34)*.1,39/34-1)
    assert near(3400/34,3900/39)
    assert near(53000/1.08,49074.07407407407)
    assert near(1.06/1.08-1,-.01851851851851849)
    assert near(100*1.08*1.03,111.24)
    assert near(4*6+22,46) and near(46/40,1.15)
    assert near(130/125-1,.04)
    assert near(60000/1.2,63000/1.26)
    assert round((1.12/1.07-1)*100,2)==4.67
    assert near(100*1.10*1.02,112.2)
    assert near(.8*.05+.2*.2,.08) and near(.2*.05+.8*.2,.17)
    assert near(.7*100+.3*(-50),55)
    assert near(150*.6-50,40)
    assert 100+9900==10000 and 90+990==1080 and near(90/1080,1/12)
    assert near(.4*200+.6*(-100),20)
    assert near(300*.3-100,-10) and near(300*.5-100,50)
    assert near(80/(80+90),8/17)
    assert near(.05*(-100),-5)
    assert near(.6*80-.4*40,32) and near(.6*80-32,16)
    # Chapters 9–10: paired balance sheets and descriptive effects.
    assert 100+400==450+50
    assert 100+450==500+50
    assert 60+450==460+50 and 60+440==450+50
    assert 20+400==370+50 and 20+340-370==-10
    assert 80+360==390+50
    assert 55+360==365+50 and 55+345==350+50
    assert 600-75-540==-15
    assert (1300-1000)-(1200-1000)==100
    assert near(40/200,.2) and near(60/200,.3)
    assert near((.3-.2)/.3,1/3)
    assert (650-500)-(500-400)==50
    # Chapters 11–12: consolidated margins and full integration case.
    assert near(-500+600/1.1,45.454545454545)
    assert near((50+40)/(200+800),.09)
    assert near(100*1.06*1.02,108.12)
    assert 1800+1200-1000-800+1200-60==2340
    assert 1200-800-60==340
    assert 2340+1000==1200+1800+340
    assert near(.6*1200+.4*700,1000)
    assert near(1000/1.1-800,109.090909090909)
    assert near(1200/1.1-800,290.90909090909)
    assert near(700/1.1-800,-163.636363636363)
    assert near((700+500*.36)/1.1,800)
    assert near(.6*870+.4*370,670)
    assert 870-550==320 and 370-550==-180
    assert 2240+1000==1100+2140
    assert 2340+900==1200+2040
    assert round((700+500*.3)/1.1-800,2)==-27.27
    assert round((700+500*.5)/1.1-800,2)==63.64
    assert near(.6*840+.4*340,640)
    assert near(370+500*.36,550)
    # Volume 1 exams are independently recalculated from their question inputs.
    assert near(100/80-1,.25) and near(90/100-1,-.1) and near(90/80-1,.125)
    assert near((3.6-3)/3,.2)
    assert 1500+900-700-500+750-45-100==1805
    assert 750-500-45==205 and 1805+700==800+1500+205
    assert round(-700+400/1.1+400/1.1**2,2)==-5.79
    assert near(.6*120+.4*(-80),40) and near(200*.5-80,20)
    assert near(1000*.02*.9,18) and near(1000*.98*.05,49)
    assert 90-2*25==15+25==40
    assert 90-2*26==15+23==38 and 3*38==114
    assert (1040-800)-(780-600)==60
    assert near(110/1250,.088) and near(1.2*.8-1,-.04)
    assert 2000+1000-1200-600+600-80-200==1520
    assert 1000-600-80==320 and 1520+1200+400==800+2000+320
    assert round(sum(220/1.1**t for t in (1,2,3))-600,2)==-52.89
    assert near(220-220/1.1,20) and -600+3*220==60
    assert near(.5*150+.5*(-50),50) and near(200*.4-50,30)
    assert near(.5*150-50,25)
    assert 140-2*20==20+4*20==100
    assert 140-2*24==20+4*18==92 and 6*92==552
    # Project benchmark runs against its documented synthetic fixture.
    spec=importlib.util.spec_from_file_location('v01_project',ROOT/'content/projects/v01-solution.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result=module.solve(json.loads((ROOT/'content/projects/v01-case.json').read_text()))
    assert [r['cash'] for r in result['months']]==[1300,1540,1852]
    assert [r['inventory_units'] for r in result['months']]==[18,13,3]
    assert [r['debt'] for r in result['months']]==[1000,900,800]
    assert result['cumulative_profit']==442 and result['closing_assets']==2742 and result['closing_equity']==1942
    assert result['expected_project_receipt']==690 and near(result['benchmark_npv'],690/1.1-600)
    assert result['cash_after_project']==1252 and result['cash_after_project_and_withdrawal']==852
    assert result['project_meets_buffer'] is True and result['project_and_withdrawal_meet_buffer'] is False
    assert near(result['closing_cash_in_initial_purchasing_power'],1852/1.1)

def main():
    plan = json.loads((ROOT/'content/curriculum.json').read_text())
    source_ids = {s['id'] for s in json.loads((ROOT/'content/sources.json').read_text())}
    volumes = {v['id']: v for v in plan['volumes']}
    chapters = {c['id']: c for v in plan['volumes'] for c in v['chapters']}
    errors = []
    require = lambda condition,message: errors.append(message) if not condition else None
    require(len(volumes)==18 and len(chapters)==216,'Curriculum scope differs from contract')
    all_ids = set(volumes)|set(chapters)
    graph = {v['id']:v['prerequisites']+[v['chapters'][-1]['id']] for v in volumes.values()}
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
            require(bool(c.get('review_record')) and (ROOT/'content'/c.get('review_record','')).is_file(),f'{c["id"]}: missing recorded editorial review')
    for v in volumes.values():
        package=ROOT/'content/assessments'/f'{v["id"]}.html'
        if package.exists():
            package_text=package.read_text()
            for component in ('diagnostic','Form A','Form B','project','retention','Rubric'):
                require(component.lower() in package_text.lower(),f'{v["id"]}: missing assessment component {component}')
        if v['status']=='accepted':
            require(package.exists(),f'{v["id"]}: accepted without assessment package')
            require(all(c['status']=='accepted' for c in v['chapters']),f'{v["id"]}: accepted with unfinished chapters')
            require(v.get('assessment_status')=='accepted-by-author',f'{v["id"]}: accepted without assessment review')
            require(bool(v.get('review_record')) and (ROOT/'content'/v.get('review_record','')).is_file(),f'{v["id"]}: missing volume review record')
            for component in ('project_inputs','project_benchmark'):
                require(bool(v.get(component)) and (ROOT/'content'/v.get(component,'')).is_file(),f'{v["id"]}: missing {component}')
            if package.exists():
                parsed_package=Document(); parsed_package.feed(package_text)
                for component in ('notation-index','concept-index','volume-synthesis'):
                    require(component in parsed_package.ids,f'{v["id"]}: missing volume reference component {component}')
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
    v02_check = check_v02_calculus()
    v02_linear_check = check_v02_linear()
    v02_optimization_check = check_v02_optimization()
    v02_duality_check = check_v02_duality()
    v02_analysis_check = check_v02_analysis()
    v02_dynamics_check = check_v02_dynamics()
    v02_numerics_check = check_v02_numerics()
    v02_assessment_check = check_v02_assessment()
    v03_probability_check = check_v03_probability()
    v03_moments_check = check_v03_moments()
    v03_conditioning_limits_check = check_v03_conditioning_limits()
    v03_estimation_inference_check = check_v03_estimation_inference()
    v03_bayes_utility_check = check_v03_bayes_utility()
    report = {'status':'failed' if errors else 'passed','chapter_packages_available':available,
              'html_pages_checked':len(pages),'curriculum_chapters':len(chapters),
              'checks':['curriculum scope','acyclic prerequisites including volume completion','chapter and assessment package structure','local links and anchors','source IDs','Volume 1 chapters 1–12 and exam arithmetic','Volume 1 project benchmark and reconciliations','Volume 2 chapters 1–4 numerical results, derivative cross-checks, quadrature and error bounds','Volume 2 chapters 5–6 exact systems, projection identities, eigenstructure, covariance, dynamics and QR reconstruction','Volume 2 chapters 7–8 derivative responses, nonlinear equilibrium roots, KKT residuals, value transitions and envelope calculations','Volume 2 chapter 9 dual certificates, separation, value subgradients and comparative statics','Accepted-volume notation/concept index and synthesis','Volume 2 chapter 10 uniform tails, fixed-point error certificates, counterexamples, spectral projectors and implicit roots','Volume 2 chapters 11–12 exact dynamics, independent ODE integration, roots/quadrature/error bounds and Bellman policy certificates','Volume 2 diagnostic, distinct exams, retention and constrained-allocation project with exact active-set/dual checks','Volume 3 chapters 1–2 weighted event laws, exhaustive sampling counts, conditional/odds updates, sequential/selected evidence and exact probability lab','Volume 3 chapters 3–4 count distributions, CDF endpoints, density quadrature and tail bounds, exact moments/covariance, portfolio and finite-population certificates, mixed laws and heavy-tail integrals','Volume 3 chapters 5–6 conditional forecast losses, triangular densities, random-sum/latent states, exact binomial tails, common-shock and convergence counterexamples, maximal-inequality terms and CLT smooth-transition checks','Volume 3 chapters 7–8 exhaustive sampling/bootstrap laws, likelihood/exposure boundaries, normal/t pivots, exact binomial tails/intervals and coverage diagnostics, power/sample-size calculations, Holm strong-control state checks and equivalence','Volume 3 chapters 9–10 exact Bayesian posterior/predictive laws, independent beta/gamma/normal integration, credible-coverage counterexample, losses/Bayes factors and prior sensitivity, insurance/utility/domain calculations, CARA-normal exposure and ambiguity/equal-moment counterexamples'],
              'volume_2_numerical_check': v02_check,
              'volume_2_linear_check': v02_linear_check,
              'volume_2_optimization_check': v02_optimization_check,
              'volume_2_duality_check': v02_duality_check,
              'volume_2_analysis_check': v02_analysis_check,
              'volume_2_dynamics_check': v02_dynamics_check,
              'volume_2_numerics_check': v02_numerics_check,
              'volume_2_assessment_check': v02_assessment_check,
              'volume_3_probability_check': v03_probability_check,
              'volume_3_distributions_moments_check': v03_moments_check,
              'volume_3_conditioning_limits_check': v03_conditioning_limits_check,
              'volume_3_estimation_inference_check': v03_estimation_inference_check,
              'volume_3_bayes_utility_check': v03_bayes_utility_check,
              'errors':errors,'limitations':['These checks do not certify all subject-matter claims or externally assess learner competence.']}
    (ROOT/'verification-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
    if errors: raise SystemExit(1)

if __name__=='__main__':
    main()
