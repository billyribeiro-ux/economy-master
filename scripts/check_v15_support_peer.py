"""Independent V15 support oracle. Author checker is never imported or executed."""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import combinations, product
from pathlib import Path
import json
import re

AUTHOR_PATHS = (
    'content/assessments/parts/v15-support-opening.html',
    'content/assessments/parts/v15-support-closing.html',
    'scripts/check_v15_support.py',
    'content/reviews/v15-support-sources.json',
    'content/reviews/v15-support-author.json',
)
PEER_PATH = 'content/reviews/v15-support-peer.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def interval_mean(rate, mean, low, high):
    require(0 <= rate <= 1 and low <= mean <= high, 'mean domain')
    return (rate * mean + (1-rate)*low, rate*mean + (1-rate)*high)


def bayes(prior, lh, ll):
    require(all(0 <= p <= 1 for p in (prior, lh, ll)), 'probability domain')
    mass = prior*lh + (1-prior)*ll
    require(mass > 0, 'zero probability observation')
    return mass, prior*lh/mass


def poverty(incomes, line, power):
    require(line > 0 and incomes and power in (0, 1, 2), 'poverty domain')
    return sum(((F(1) if power == 0 else ((line-y)/line)**power) for y in incomes if y < line), F(0))/len(incomes)


def gini(incomes):
    require(incomes and all(y >= 0 for y in incomes) and sum(incomes) > 0, 'gini domain')
    return sum(abs(a-b) for a,b in combinations(incomes,2))/(len(incomes)*sum(incomes))


def peak(linear, curvature, lower, upper):
    require(curvature > 0 and lower <= upper, 'concave domain')
    return max(lower, min(upper, linear/curvature))


def oracle():
    """Computed from prompt primitives; alternative checks use different identities."""
    out = {}
    # Tax market: integrate inverse demand and cost rather than triangle formula.
    q = F(12-2-2, 2); buyer = 12-q; seller = 2+q
    benefit = 12*q-q*q/2; cost = 2*q+q*q/2
    cs, ps, revenue = benefit-buyer*q, seller*q-cost, 2*q
    q0 = F(12-2,2); total0 = (12-2)*q0-q0*q0
    out['d1-market'] = q,buyer,seller,revenue
    out['d1-welfare'] = cs,ps,cs+ps+revenue,total0-cs-ps-revenue
    require(buyer*q <= 50 and buyer*q == seller*q+revenue, 'market funding')
    x = peak(F(6),F(2),F(0),F(2))
    out['d2'] = x,6*x-x*x,6-2*x
    out['d3'] = bayes(F(1,3),F(3,4),F(1,4))
    out['d4'] = F(2)/F(2,5),(2-F(1,2))/F(2,5)
    out['d5'] = tuple(poverty(tuple(map(F,(1,3,6))),F(4),a) for a in range(3))
    out['d6'] = interval_mean(F(4,5),F(5),F(0),F(10))
    gain = F(10-6+3); levy = F(3); collection = levy/5
    out['d7'] = gain,-levy,gain-levy,gain,-levy-collection,gain-levy-collection
    income = tuple(map(F,(1,3,5)))
    out['d8'] = gini(income),gini(tuple(y+2 for y in income)),gini(tuple(2*y for y in income))
    ideals = tuple(map(F,(1,2,5))); median = sorted(ideals)[1]
    planner = sum(ideals)/len(ideals)
    welfare = lambda g: sum(a*g-g*g/2 for a in ideals)
    out['o1'] = median,planner,welfare(median),welfare(planner),welfare(planner)-welfare(median)
    # Pairwise majority checked on either side, including distant nonnegative proposals.
    for alternative in (F(0),F(1),F(3,2),F(5,2),F(3),F(10)):
        require(sum(a*median-median**2/2 > a*alternative-alternative**2/2 for a in ideals) >= 2, 'majority')
    trade = []
    for t in (F(0),F(1)):
        p=4+t; d=10-p; s=p-2; imports=d-s
        c=(10-p)*d/2; producer=(p-2)*s/2; receipts=t*imports
        require(p*d == p*s + 4*imports + receipts,'trade accounts')
        trade.append((d,s,imports,c,producer,receipts,c+producer+receipts))
    a,b=trade
    out['o2'] = a[:3]+b[:3]+(a[-1],b[-1],a[-1]-b[-1])
    posterior=bayes(F(1,2),F(3,5),F(1,5))[1]
    out['o3'] = posterior,bayes(posterior,F(1),F(1))[1],bayes(posterior,F(3,5),F(1,5))[1]
    p=F(4,5)
    score=lambda q: p*(1-(q-1)**2)+(1-p)*(1-q*q)
    distorted=p/(p+2*(1-p))
    out['o4'] = score(p),score(F(1,2)),score(p)-score(F(1,2)),distorted
    gains=(F(6-2-3),F(2-2),F(3))
    out['o5'] = gains+(sum(gains),2*gains[0]+sum(gains[1:]))
    # Enumerate all integer roots after rational factorization: roots 2 and 6,
    # and validate the identity for arbitrary rational tax points.
    roots=tuple(F(t) for t in range(9) if F(t)*(8-t)/2 == 6)
    require(roots == (F(2),F(6)), 'tax roots')
    for t in (F(0),F(1,3),F(2),F(4),F(6),F(8)):
        require(t*t-8*t+12 == (t-2)*(t-6),'exhaustive tax factorization')
    labor=tuple((8-t)/2 for t in roots)
    consumption=tuple((8-t)*l for t,l in zip(roots,labor))
    welfare=tuple(c-l*l+6 for c,l in zip(consumption,labor))
    out['r1']=roots+labor+consumption+welfare
    profit=lambda n: (F(16,n+1))**2-9
    viable=[n for n in range(1,20) if profit(n)>=0 and profit(n+1)<=0]
    require(viable==[4], 'integer entry')
    def cournot(n):
        q=F(16,n+1); total=n*q
        require(q == peak(16-(n-1)*q,F(2),F(0),F(20)), 'global response')
        return total,16*total-total*total/2-9*n
    out['r2-welfare']=tuple(cournot(n)[1] for n in (1,2,4))
    out['r2-entry']=F(viable[0]),cournot(4)[0],profit(4)
    optimal_output=peak(F(16),F(1),F(0),F(20))
    out['r2-planner']=F(1),optimal_output,16*optimal_output-optimal_output**2/2-9
    # Scarce transfer budget; feasibility x in [1,2]. Square completion is global.
    for x in (F(1),F(5,4),F(3,2),F(2)):
        actual=poverty((1+x,5-x),F(4),2)
        require(actual == F(1,16)+(x-2)**2/16,'poverty square completion')
    out['r3-poverty']=F(2),poverty((F(3),F(3)),F(4),2),F(1),poverty((F(2),F(4)),F(4),0),poverty((F(3),F(3)),F(4),1)
    sensitivity=[3-d+s for d,s in product((F(-1,2),F(1,2)),(F(0),F(1)))]
    out['r3-bounds']=min(sensitivity),max(sensitivity)
    risk=(F(1,5),F(4,5)); utility=tuple((1-p)*3+p for p in risk)
    willingness=tuple(9-u*u for u in utility); claim=tuple(8*p for p in risk)
    pool=sum(claim)/2; premium=claim[1]; subsidy=pool-willingness[0]
    out['r4-insurance']=willingness+(premium,F(1,2),subsidy)
    require(willingness[0]<premium<=willingness[1], 'high-only participation')
    for price in (F(0),willingness[0],F(3),premium,willingness[1],F(8)):
        participants=[i for i in range(2) if price<=willingness[i]]
        earnings=sum((price-claim[i])/2 for i in participants)
        require(not participants or price==premium or earnings != 0,'unique positive zero-profit coverage')
    require(sum(b>=subsidy/3 for b in (F(0),F(1,2),F(2)))==1,'outside majority')
    private=peak(F(5)-F(1,2),F(1),F(0),F(5)); social=peak(F(4),F(1),F(0),F(5))
    surplus=lambda q: 4*q-q*q/2
    out['r4-care']=private,social,surplus(private),surplus(social),surplus(social)-surplus(private),private/2,private/2
    payoffs=((F(0),F(0)),(F(8),F(-2)),(F(3),F(4))); cash=(0,4,2)
    no_signal=tuple(sum(row)/2 for row in payoffs)
    best_state=tuple(max(row[s] for row in payoffs) for s in range(2))
    regrets=tuple(max(best_state[s]-row[s] for s in range(2)) for row in payoffs)
    out['r5-basic']=no_signal+regrets
    joint=((F(3,8),F(1,8)),(F(1,8),F(3,8))) # signal, state
    def policies(reserve):
        feasible=[i for i,c in enumerate(cash) if c+1<=reserve]
        return [(sum(joint[z][s]*payoffs[rule[z]][s] for z,s in product(range(2),repeat=2))-1,rule) for rule in product(feasible,repeat=2)]
    best,rule=max(policies(5)); require(rule==(1,2) and len(policies(5))==9,'pilot enumeration')
    perfect=sum(best_state)/2; baseline=max(no_signal)
    threshold=F(payoffs[2][1]-payoffs[1][1],(payoffs[1][0]-payoffs[1][1])-(payoffs[2][0]-payoffs[2][1]))
    post=tuple(row[0]/sum(row) for row in joint)
    out['r5-pilot']=threshold,*post,best+1,best,best-baseline,perfect,perfect-baseline,best+1-baseline
    restricted,rule4=max(policies(4)); require(rule4==(2,2) and len(policies(4))==4,'cash-restricted enumeration')
    out['r5-reserve']=restricted,baseline
    require(5*F(1,100)==F(5,100),'union bound')
    # Alternative primitives and invalid-domain rejection, not copied displayed outputs.
    require(bayes(F(0),F(1),F(1,2))[1]==0 and bayes(F(1),F(1,2),F(1))[1]==1,'prior endpoints')
    require(interval_mean(F(0),F(5),F(0),F(10))==(0,10) and interval_mean(F(1),F(5),F(0),F(10))==(5,5),'missingness endpoints')
    require(peak(F(-1),F(2),F(0),F(2))==0 and peak(F(10),F(2),F(0),F(2))==2,'optimization boundaries')
    require(gini((F(2),F(2)))==0 and poverty((F(4),F(5)),F(4),0)==0,'equality/poverty threshold')
    require(peak(F(5),F(1),F(0),F(5))==5 and peak(F(4),F(1),F(0),F(5))==4,'care cost-share endpoints')
    for fn,args in ((bayes,(F(2),F(1),F(1))), (bayes,(F(1),F(0),F(1))), (interval_mean,(F(2),F(5),F(0),F(10))), (gini,((F(0),F(0)),)), (poverty,((F(1),),F(0),1)), (peak,(F(1),F(0),F(0),F(1)))):
        try: fn(*args)
        except ValueError: pass
        else: raise ValueError('invalid domain accepted')
    return {key:tuple(map(F,value)) for key,value in out.items()}


class Manuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=[]; self.prompts={}; self.solutions={}; self.markers={}; self.sources={}; self.links=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if 'data-points' in a:
            require(a['id'] not in self.prompts,'duplicate prompt')
            self.prompts[a['id']]={'points':int(a['data-points']),'text':''}
        if 'data-solution-for' in a:
            key=a['data-solution-for']; require(key not in self.solutions,'duplicate solution')
            require(any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack),'solution disclosure')
            self.solutions[key]=''
        if 'data-check' in a:
            key=a['data-check']; require(key not in self.markers,'duplicate marker'); self.markers[key]=''
        if 'data-source' in a:
            require(a['data-source'] not in self.sources,'duplicate source'); self.sources[a['data-source']]=a['href']
        if tag=='a': self.links.add(a['href'])
        if tag not in ('br','hr','img','meta','link','input'): self.stack.append((tag,a))
    def handle_data(self,data):
        for _,a in self.stack:
            if 'data-points' in a: self.prompts[a['id']]['text']+=data
            if 'data-solution-for' in a: self.solutions[a['data-solution-for']]+=data
            if 'data-check' in a: self.markers[a['data-check']]+=data
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting')
        self.stack.pop()


def parse_numbers(text):
    text=text.strip().replace('−','-')
    require(text.startswith('(') and text.endswith(')'), 'numeric tuple')
    values=text[1:-1].split(',')
    require(all(re.fullmatch(r'\s*-?\d+(?:/[1-9]\d*)?\s*', v) for v in values),'numeric grammar')
    return tuple(F(v.strip()) for v in values)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    files=AUTHOR_PATHS+('scripts/check_v15_support_peer.py',PEER_PATH)
    raw={path:(root/path).read_bytes() for path in files}
    peer=json.loads(raw[PEER_PATH]); author=json.loads(raw[AUTHOR_PATHS[4]])
    for record,expected in ((author,set(AUTHOR_PATHS[:4])),(peer,set(files)-{PEER_PATH})):
        bindings=record['payload_bindings']
        require(len(bindings)==len(expected) and {b['path'] for b in bindings}==expected,'complete nonself bindings')
        for b in bindings:
            data=raw[b['path']]
            require(len(data)==b['bytes'] and sha256(data).hexdigest()==b['sha256'],'binding mismatch: '+b['path'])
    doc=Manuscript(); doc.feed(raw[AUTHOR_PATHS[0]].decode()+'\n'+raw[AUTHOR_PATHS[1]].decode())
    require(not doc.stack and len(doc.ids)==len(set(doc.ids)),'balanced unique HTML')
    points={**{f'v15-d{i}':5 for i in range(1,9)},**{f'v15-o{i}':4 for i in range(1,6)},**{f'v15-r{i}':10 for i in range(1,6)}}
    require({k:v['points'] for k,v in doc.prompts.items()}==points and set(doc.solutions)==set(points),'18 paired scored prompts')
    require(set(peer['exact_prompt_audit'])==set(points) and set(author['exact_prompt_audit'])==set(points),'18 prompt reviews')
    for key,points_value in points.items():
        solution=doc.solutions[key]
        require(f'Rubric ({points_value} points).' in solution,'rubric total')
        rubric=solution.split(f'Rubric ({points_value} points).',1)[1].split('Study route:',1)[0]
        terms=re.findall(r'(\d+)\s*(?:;|\.)',rubric)
        require(sum(map(int,terms))==points_value,'additive rubric: '+key)
        binding=peer['exact_prompt_audit'][key]
        require(sha256(doc.prompts[key]['text'].encode()).hexdigest()==binding['prompt_sha256'],'exact prompt binding')
        require(sha256(solution.encode()).hexdigest()==binding['solution_sha256'],'full solution/rubric binding')
    expected=oracle()
    require(set(expected)==set(doc.markers),'all visible numerical markers')
    for key,value in expected.items(): require(parse_numbers(doc.markers[key])==value,'displayed result: '+key)
    require({'diagnostic','exam-rules','oral-transfer','retention','remediation','notation-index','concept-index','volume-synthesis','assessment-source-scope'} <= set(doc.ids),'support anchors')
    require(all(f'v15-c{i:02}.html' in doc.links for i in range(1,13)) and 'curriculum.html#v16-c01' in doc.links,'chapter/successor routes')
    sources=json.loads(raw[AUTHOR_PATHS[3]])['sources']
    require(len(sources)==3 and doc.sources=={s['id']:s['url'] for s in sources},'source route equality')
    require(all(s.get('verification') and s.get('limits') and s.get('reuse_scope') for s in sources),'bounded source evidence')
    require(peer['open_findings']==[],'unresolved peer finding')
    return {'volume':'v15','component':'support','review':'independent-peer','status':'passed','runtime_files':7,'diagnostic_tasks':8,'oral_tasks':5,'retention_tasks':5,'score_totals':[40,20,50],'visible_result_markers':len(expected),'displayed_scalar_results':sum(map(len,expected.values())),'pilot_policies_enumerated':[9,4],'invalid_domain_rejections':6,'source_routes':3,'scope':'Exact primitive reconstruction plus global proofs, complete prompts and additive rubrics; no external human or UI certification.'}


if __name__=='__main__':
    check()
