"""Independent V17 project peer arithmetic and frozen-payload audit."""
import ast
import copy
from fractions import Fraction as F
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import hashlib
import sys


def need(x,msg):
    if not x: raise ValueError(msg)

def strict(s):
    def pairs(xs):
        out={}
        for k,v in xs:
            need(k not in out,'duplicate key');out[k]=v
        return out
    return json.loads(s,object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite')))

def pack(x):
    if isinstance(x,F): return x.numerator if x.denominator==1 else str(x)
    if isinstance(x,(tuple,list)): return [pack(v) for v in x]
    if isinstance(x,dict): return {k:pack(v) for k,v in x.items()}
    return x

def literal(s):
    def go(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,(ast.Tuple,ast.List)):return [go(v) for v in n.elts]
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -go(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return go(n.left)/go(n.right)
        raise ValueError('numeric literal')
    return pack(go(ast.parse(s.strip(),mode='eval').body))

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.values={};self.active=None;self.buf=[];self.tasks={};self.solutions=[];self.sources=set()
    def handle_starttag(self,t,a):
        d=dict(a)
        if 'data-result' in d or 'data-input' in d:
            k=d.get('data-result',d.get('data-input'));need(k not in self.values,'duplicate marker');self.active=k;self.buf=[]
        if t=='li' and d.get('id','').startswith('project-task'):self.tasks[d['id']]=int(d['data-points'])
        if 'data-solution-for' in d:self.solutions.append(d['data-solution-for'])
        if 'data-source' in d:self.sources.add(d['data-source'])
    def handle_data(self,s):
        if self.active:self.buf.append(s)
    def handle_endtag(self,t):
        if t=='span' and self.active:self.values[self.active]=literal(''.join(self.buf));self.active=None

def economy(case):
    a,b=map(F,case['values']);c=F(case['unit_cost']);B=F(case['budget']);T=F(case['transfer'])
    need(min(a,b,B,T)>=0 and c>0,'economic domain')
    # Candidate active sets: no contributors, one contributor, or equal-type split.
    if max(a,b)<=c:q=(F(0),F(0));unique=True
    elif a==b:q=((a-c)/2,(a-c)/2);unique=False
    elif a>b:q=(a-c,F(0));unique=True
    else:q=(F(0),b-c);unique=True
    g=sum(q);values=(a,b)
    for i in range(2):need(q[i]==max(F(0),values[i]-c-q[1-i]),'Nash residual')
    benefits=lambda x:[v*x-x*x/2 for v in values]
    pu=[v-c*z for v,z in zip(benefits(g),q)]
    # Compare feasible boundary with stationary candidate using the objective itself.
    objective=lambda x:sum(benefits(x))-c*x
    candidates=[F(0)]
    if a+b>=c:candidates.append((a+b-c)/2)
    star=max(candidates,key=objective);prices=[a-star,b-star];payments=[p*star for p in prices]
    cu=[v-w for v,w in zip(benefits(star),payments)];after=[cu[0]-T,cu[1]+T];gains=[v-u for v,u in zip(after,pu)]
    constrained=max([F(0),min(star,B/c)],key=objective)
    reasons=[]
    if c*star>B:reasons.append('efficient_quantity_exceeds_procurement_budget')
    if any(p<0 for p in prices):reasons.append('negative_personalized_price_not_allowed_by_proposed_scheme')
    if T>0 and not case['transfer_authorized']:reasons.append('compensating_transfer_has_no_assumed_authority')
    if any(x<0 for x in gains):reasons.append('at_least_one_household_fails_participation_relative_to_selected_private_equilibrium')
    return pack(dict(id=case['id'],private_total=g,private_contributions=q,private_equilibrium_unique=unique,
      equal_value_equilibrium_interval=None if unique else [0,g],private_utilities=pu,private_welfare=sum(pu),
      efficient_quantity=star,efficient_cost=c*star,efficient_welfare=objective(star),welfare_gain=objective(star)-sum(pu),
      personalized_prices=prices,payments=payments,payment_minus_cost=sum(payments)-c*star,utilities_before_transfer=cu,
      utilities_after_transfer=after,participation_gains=gains,transfer_interval_for_weak_participation=[pu[1]-cu[1],cu[0]-pu[0]],
      budget_shortfall=max(F(0),c*star-B),budget_constrained_quantity=constrained,budget_constrained_welfare=objective(constrained),
      proposed_scheme_feasible=len(reasons)==0,diagnostics=reasons))

def grading(data,old=False):
    results=[]
    for stage in data['stages']:
        rows=[]
        for name in data['roster']:
            raw=next(x for x in data['responses'] if x['stage']==stage['id'] and x['learner']==name)
            credits=raw['criterion_credit'][:]
            if old:
                for fix in data['grading_versions']['corrections']:
                    if (fix['stage'],fix['learner'])==(stage['id'],name):credits[data['criteria'].index(fix['criterion'])]=fix['old_credit']
            rows.append(dict(learner=name,status=raw['status'],criterion_credit=credits,score=None if raw['status']=='missing' else sum(credits),recorded_assessment_credit=sum(credits)))
        submitted=[r for r in rows if r['score'] is not None];ind=[r for r in rows if r['status']=='independent']
        mean=lambda rs:F(sum(r['score'] for r in rs),len(rs)) if rs else None
        total=sum(r['recorded_assessment_credit'] for r in rows);full=lambda rs:sum(r['score']==8 for r in rs)
        results.append(dict(stage=stage['id'],rows=rows,roster_n=len(rows),submitted_n=len(submitted),independent_n=len(ind),assisted_n=sum(r['status']=='assisted' for r in rows),missing_n=len(rows)-len(submitted),total_recorded_credit=total,full_roster_mean_recorded_credit=F(total,len(rows)),submitted_mean=mean(submitted),independent_mean=mean(ind),submitted_complete_n=full(submitted),independent_complete_n=full(ind),independent_complete_share=F(full(ind),len(ind)) if ind else None))
    return pack(results)

def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    review=strict((root/'content/reviews/v17-project-peer.json').read_text());n=0
    def eq(a,b,label):
        nonlocal n
        need(a==b,label);n+=1
    for rel,meta in review['payloads'].items():
        raw=(root/rel).read_bytes();eq(len(raw),meta['bytes'],rel+' bytes');eq(hashlib.sha256(raw).hexdigest(),meta['sha256'],rel+' hash')
    page=Page();page.feed((root/'content/assessments/parts/v17-project.html').read_text())
    expected={'base':[6,4,4,12,2],'delayed':[7,5,4,16,3],'base-model':[2,3,8,9,3,1,'9/2','9/2'],'base-transfer-interval':['3/2','5/2'],'base-after-transfer':['5/2','13/2'],'cost-transfer':[0,2,0,4,4,2],'ug-hours':'17/2','grad-hours':9,'equal-values':[1,3,5,9,'5/2','9/2'],'baseline-scores':[6,8,2,0,8,6],'immediate-scores':[8,8,6,0,8,8],'delayed-scores':[8,8,6,0,0,6],'old-baseline-scores':[8,8,2,0,8,6],'summaries':[[30,5,6,'11/2'],[38,'19/3','38/5',8],[28,'14/3',7,7]],'fresh-feedback-task':[2,3,8,9,5,1,2,6,'9/2','9/2'],'paired-changes':[2,0,4,0],'paired-mean':'3/2','budget-case':[12,2,'5/2','35/4'],'negative-price':[4,6,-2],'supervision-transfer':[0,1,0,1,2,2],'revision-exit':['7/2','11/2','3/2','5/2'],'task-points':[20,20,12,8,20,10,10]}
    eq(page.values,expected,'every visible numeric marker')
    eq(page.tasks,{f'project-task{i}':p for i,p in enumerate([20,20,12,8,20,10,10],1)},'seven tasks')
    eq(set(page.solutions),set(page.tasks),'full solution identities')
    sources=strict((root/'content/reviews/v17-project-sources.json').read_text());eq(page.sources,{s['id'] for s in sources['sources']},'source scope')
    p=root/'content/projects';data=strict((p/'v17-assessment-inputs.json').read_text());reference=strict((p/'v17-assessment-output.json').read_text())
    manifest=strict((p/'v17-assessment-manifest.json').read_text())
    for name,meta in manifest['payloads'].items():
        raw=(p/name).read_bytes();eq({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},meta,'reader manifest')
    # Construct primitive oracle before loading reader, with author checker never imported.
    econ=[economy(c) for c in data['models']];grades={data['grading_versions'][v]:grading(data,v=='old') for v in ('old','corrected')}
    eq(reference['models'],econ,'all economic output fields');eq(reference['grading'],grades,'every response and denominator')
    changes=[]
    for name in data['roster']:
        rr=[next(r for r in data['responses'] if r['learner']==name and r['stage']==s) for s in data['paired_stages']]
        if all(r['status']=='independent' for r in rr):
            b,a=[sum(r['criterion_credit']) for r in rr];changes.append(dict(learner=name,before=b,after=a,difference=a-b))
    eq(reference['paired_independent']['rows'],changes,'paired raw reconstruction');eq(reference['paired_independent']['mean_difference'],pack(F(sum(r['difference'] for r in changes),len(changes))),'paired mean')
    eq(reference['project_scoring']['total'],100,'points');eq(reference['project_scoring']['tasks'],{str(i):v for i,v in enumerate([20,20,12,8,20,10,10],1)},'allocations')
    eq(reference['evidence_status'],{'observations':'synthetic only','revision':'prepared, not delivered','actual_learner_evaluation':'not supplied','stipulated_observation_minutes':20},'evidence boundary')
    spec=importlib.util.spec_from_file_location('v17_peer_reader',p/'v17-assessment-analysis.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    before=copy.deepcopy(data);eq(reader.run(data),reference,'actual entire reader output');eq(data,before,'no input mutation')
    worlds=0
    for a in range(0,8,2):
      for b in range(0,8,2):
       for c in (1,4,8):
        case={'id':'peer','values':[a,b],'unit_cost':c,'budget':7,'transfer':1,'transfer_authorized':True}
        want=economy(case);eq(pack(reader.model(case)),want,'alternative economic world');worlds+=1
        # Direct global comparisons to grid alternatives, separate from vertex formula.
        optimum=F(want['efficient_quantity']);w=lambda g:(a+b-c)*g-g*g
        for j in range(25):need(w(optimum)>=w(F(j,2)),'global planner witness');n+=1
        q=list(map(F,want['private_contributions']))
        for i,v in enumerate((a,b)):
         u=lambda x:v*(x+q[1-i])-(x+q[1-i])**2/2-c*x
         for j in range(17):need(u(q[i])>=u(F(j,2)),'best response witness');n+=1
    for mode in ('all_missing','all_assisted','reverse_roster'):
        d=copy.deepcopy(data)
        if mode=='reverse_roster':d['roster'].reverse()
        else:
            d['grading_versions']['corrections']=[]
            for r in d['responses']:
                r['status']='missing' if mode=='all_missing' else 'assisted'
                if mode=='all_missing':r['text']='';r['criterion_credit']=[0]*4
                elif not r['text']:r['text']='Synthetic altered test response.'
        out=reader.run(d)
        for v in ('old','corrected'):eq(out['grading'][d['grading_versions'][v]],grading(d,v=='old'),'empty/support world')
        eq(out['paired_independent']['n'],4 if mode=='reverse_roster' else 0,'paired eligibility')
    invalid=[]
    for kind in range(12):
        d=copy.deepcopy(data)
        if kind==0:d['models'][0]['unit_cost']=0
        elif kind==1:d['models'][0]['values'][0]=-1
        elif kind==2:d['models'][0]['transfer']=-1
        elif kind==3:d['models'][0]['budget']=-1
        elif kind==4:d['models'][0]['transfer_authorized']=1
        elif kind==5:d['responses'].pop()
        elif kind==6:d['responses'].append(d['responses'][0])
        elif kind==7:d['responses'][0]['criterion_credit'][0]=1
        elif kind==8:d['responses'][3]['text']='Missing contradiction'
        elif kind==9:d['grading_versions']['corrections'][0]['corrected_credit']=2
        elif kind==10:d['observation']['revision_status']='delivered'
        else:d['project_domains'][0]['points']=21
        try:reader.run(d)
        except (ValueError,TypeError,KeyError,ZeroDivisionError):invalid.append(kind)
        else:raise ValueError('invalid domain accepted')
    return {'status':'passed','independent_comparisons':n,'economic_worlds':worlds,'altered_evidence_worlds':3,'invalid_domains':len(invalid),'tasks':7,'learner_texts_manually_reviewed':18,'author_checker':'not imported or consulted'}

if __name__=='__main__':
    sys.dont_write_bytecode=True
    check(Path(sys.argv[1]) if len(sys.argv)>1 else None)
