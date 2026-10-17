"""Quiet four-file audit of the actual research-capstone artifacts and calibration math."""
from pathlib import Path
from html.parser import HTMLParser
from fractions import Fraction as F
from hashlib import sha256
from itertools import combinations_with_replacement
import ast,json,sys
ROOT=Path(__file__).resolve().parents[1]
FILES=['content/cross-assessments/research-portfolio.html','scripts/check_research_portfolio.py','content/reviews/research-portfolio-sources.json','content/reviews/research-portfolio-author.json']

def need(ok,msg):
    if not ok:raise ValueError('Research portfolio: '+msg)

def number(text):
    def visit(n):
        if isinstance(n,ast.Expression):return visit(n.body)
        if isinstance(n,ast.Constant) and type(n.value) is int:return F(n.value)
        if isinstance(n,ast.Tuple):return tuple(visit(v) for v in n.elts)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return visit(n.left)/visit(n.right)
        raise ValueError('invalid numeric syntax')
    return visit(ast.parse(text.strip().replace('−','-'),mode='eval'))

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.h1_count=0;self.ids=[];self.tasks=[];self.answers=[];self.worked=[];self.artifacts=[];self.prerequisites=[];self.chapters=[];self.domains=[];self.sources={};self.links=[];self.values={};self.capture=None;self.forms=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);need(len(a)==len(attrs),'unique attrs')
        if t=='h1':self.h1_count+=1
        if 'id' in a:self.ids.append(a['id'])
        if t=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if 'data-artifact' in a:self.artifacts.append(a['data-artifact'])
        if 'data-prerequisite' in a:self.prerequisites.append(a['data-prerequisite'])
        if 'data-chapter' in a:self.chapters.append(a['data-chapter'])
        if 'data-domain' in a:self.domains.append(a['data-domain'])
        if t=='pre' and a.get('id','').startswith('research-form-'):self.forms.append(a['id'])
        if t=='li' and any(z=='ol' and 'exercises' in d.get('class','').split() for z,d in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for' in a:
            need(any(z=='details' and 'solutions' in d.get('class','').split() for z,d in self.stack),'solutions disclosure');self.answers.append(a['data-solution-for'])
        if 'data-source' in a:self.sources[a['data-source']]=a['href']
        if 'href' in a:self.links.append(a['href'])
        for kind in ('input','result'):
            if 'data-'+kind in a:
                self.capture=(kind,a['data-'+kind]);need(self.capture not in self.values,'unique number marker');self.values[self.capture]=''
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,text):
        if self.capture:self.values[self.capture]+=text
    def handle_endtag(self,t):
        need(self.stack and self.stack[-1][0]==t,'balanced HTML');_,a=self.stack.pop()
        if 'data-input' in a or 'data-result' in a:self.capture=None

def loan(principal,payments,gross):
    need(type(principal) in (int,F) and principal>=0,'nonnegative principal')
    need(isinstance(payments,tuple) and len(payments)>0 and all(type(v) in (int,F) and v>=0 for v in payments),'nonnegative payment tuple')
    need(type(gross) in (int,F) and gross>0,'positive gross discount factor')
    # Discount by a recursively accumulated denominator, independently of the
    # manuscript's displayed powers and nominal saved-output calculation.
    denominator=F(1);pv=F(0)
    for payment in payments:denominator*=gross;pv+=payment/denominator
    return pv,pv-principal

def demand_world(rows,beta):
    need(type(beta) in (int,F) and beta>=0,'nonnegative demand slope')
    need(isinstance(rows,tuple) and len(rows)>0 and all(isinstance(r,tuple) and len(r)==3 for r in rows),'complete market rows')
    intercepts=[];observed=[];interventions=[]
    for cost,rate,quantity in rows:
        need(all(type(v) in (int,F) for v in (cost,rate,quantity)) and cost>=1 and rate==cost+1 and quantity>=0,'observed regime/domain')
        # Recover the latent intercept from each observed demand equation rather
        # than trusting the A_beta expression whose equivalence is being checked.
        intercept=quantity+beta*rate;intercepts.append(intercept);observed.append(intercept-beta*rate);interventions.append(intercept-beta*(rate-1))
    return tuple(intercepts),tuple(observed),tuple(interventions)

def robust_loss(a,p,losses):return p*losses[0]*(1-a)+(1-p)*losses[1]*a

def robust_oracle(bounds,losses):
    need(isinstance(bounds,tuple) and len(bounds)==2 and all(type(v) in (int,F) for v in bounds),'probability pair')
    lo,hi=bounds;need(0<=lo<=hi<=1,'ordered probabilities')
    need(isinstance(losses,tuple) and len(losses)==2 and all(type(v) in (int,F) and v>0 for v in losses),'positive state-loss coefficients')
    # Minimize an upper envelope by its feasible endpoints/intersection. This
    # independently recovers singleton and flat-segment argmin sets.
    b,c=losses;cross=b/(b+c);candidates=(F(0),cross,F(1));values=tuple(max(robust_loss(a,p,losses) for p in bounds) for a in candidates);best=min(values);minimizers=[a for a,v in zip(candidates,values) if v==best]
    return (min(minimizers),max(minimizers)),best

def check(root=None):
    root=Path(root) if root is not None else ROOT
    review=json.loads((root/FILES[3]).read_text());need(set(review['payloads'])==set(FILES[:3]),'three nonself payloads')
    for name,record in review['payloads'].items():
        b=(root/name).read_bytes();need(record=={'bytes':len(b),'sha256':sha256(b).hexdigest()},'frozen '+name)
    need(review['full_reading_complete'] and not review['open_material_findings'],'full substantive reading')
    page=Page();page.feed((root/FILES[0]).read_text());page.close();need(not page.stack and len(page.ids)==len(set(page.ids)),'complete unique fragment')
    need(page.h1_count==1,'one assessment h1')
    need(page.worked==['research-case1','research-case2','research-case3'],'three new cases');need(page.tasks==page.answers==['research-calibration1','research-calibration2','research-calibration3'],'three completed case solutions')
    need(page.artifacts==['reproduction','two_reports','proposal','original_paper','defense'],'five actual-work artifact contracts')
    need(page.forms==['research-form-'+n for n in ('contract','index','reproduction','reports','proposal','paper','defense','examiner')],'eight reusable operational forms')
    need(page.prerequisites==['v'+str(i) for i in range(12,17)],'all five prerequisites');need(page.chapters==[f'v16-c{i:02}' for i in range(1,13)],'all twelve chapter gates')
    need(page.domains==['contribution','correctness','reproducibility','ethics','defense'],'five noncompensating domains')
    sources=json.loads((root/FILES[2]).read_text());need(page.sources=={s['id']:s['url'] for s in sources['sources']},'bounded source mapping')
    need(all(link[1:] in page.ids for link in page.links if link.startswith('#')),'local fragment links')
    need({f'v16-c{i:02}.html' for i in range(1,13)}<=set(page.links),'chapter remediation routes');need({f'v{i}-assessment.html' for i in range(12,17)}<=set(page.links),'volume routes')
    values={k:number(v) for k,v in page.values.items()};used=set();count=0
    def get(kind,key):used.add((kind,key));return values[kind,key]
    def eq(a,b,label):
        nonlocal count
        if isinstance(a,tuple) or isinstance(b,tuple):
            need(isinstance(a,tuple) and isinstance(b,tuple) and len(a)==len(b),label+' shape')
            for x,y in zip(a,b):eq(x,y,label)
        else:need(a==b,label);count+=1
    def output(key,value):eq(get('result',key),value,key)
    times=get('input','defense-minutes');need(all(t>0 for t in times),'positive proposed allocation');output('defense-total',sum(times))
    principal=get('input','loan-principal');payments=get('input','loan-payments');gross=get('input','loan-gross');saved=get('input','loan-saved');pv,npv=loan(principal,payments,gross)
    output('loan-pv',pv);output('loan-npv',npv);output('loan-discrepancy',(pv-saved[0],npv-saved[1]));eq(saved,(sum(payments),sum(payments)-principal),'saved nominal meaning')
    rows=get('input','market-table');betas=get('input','demand-betas');worlds=[demand_world(rows,b) for b in betas]
    output('demand-intercepts',tuple(w[0] for w in worlds));output('demand-counterfactuals',tuple(w[2] for w in worlds));gains=tuple(w[2][0]-w[1][0] for w in worlds);output('demand-gains',gains)
    for beta,w in zip(betas,worlds):
        eq(w[1],tuple(r[2] for r in rows),'observational equivalence');eq(w[0],tuple(9+beta+(beta-1)*r[0] for r in rows),'latent intercept identity');eq(tuple(v-u for u,v in zip(w[1],w[2])),(beta,)*len(rows),'policy gain each state')
    # Exact fit and supplied prior-note specialization, separately from causality.
    for c,r,l in rows:eq(l,10-r,'observed affine fit');eq(l,9-c,'substituted prior fit')
    losses=get('input','risk-losses');initial=get('input','risk-initial');low=get('input','risk-low');high=get('input','risk-high');tie=get('input','risk-tie');boundary=get('input','risk-boundary-inputs')
    for name,bounds in [('initial',initial),('low',low),('high',high)]:
        interval,value=robust_oracle(bounds,losses);eq(interval[0],interval[1],name+' unique');output('risk-'+name+'-result',(interval[0],value))
    interval,value=robust_oracle((tie,tie),losses);eq(interval,(F(0),F(1)),'complete tie set');output('risk-tie-value',value)
    output('risk-boundary-sets',tuple(robust_oracle(bounds,losses)[0] for bounds in boundary))
    need(used==set(values),'every displayed input/result covered')
    # All six regimes, including probability extremes and flat optimizer sets.
    probability_grid=(F(0),F(1,10),F(1,5),F(3,5),F(7,10),F(4,5),F(1));interval_worlds=0
    for lo,hi in combinations_with_replacement(probability_grid,2):
        minimizers,best=robust_oracle((lo,hi),losses);threshold=losses[1]/sum(losses);cross=losses[0]/sum(losses)
        if hi<threshold:pred=(F(0),F(0))
        elif lo>threshold:pred=(F(1),F(1))
        elif lo<threshold<hi:pred=(cross,cross)
        elif lo<threshold==hi:pred=(F(0),cross)
        elif lo==threshold<hi:pred=(cross,F(1))
        else:pred=(F(0),F(1))
        eq(minimizers,pred,'global regime set');interval_worlds+=1
        for a in (F(0),F(1,5),F(2,5),F(3,5),F(4,5),F(1)):
            value=max(robust_loss(a,p,losses) for p in (lo,hi));need(value>=best,'global envelope certificate');need((value==best)==(minimizers[0]<=a<=minimizers[1]),'exact flat/singleton attainment');count+=2
    # Alternative coefficients make the intersection and probability threshold
    # differ, preventing a hardcoded2/5 or3/5 from passing all witnesses.
    eq(robust_oracle((F(0),F(1)),(F(3),F(1))),((F(3,4),F(3,4)),F(3,4)),'alternative losses')
    eq(loan(100,(60,60),1),(F(120),F(20)),'no discount case');eq(loan(0,(0,0),2),(F(0),F(0)),'zero cashflows')
    for beta in (F(0),F(5)):
        w=demand_world(rows,beta);eq(w[1],tuple(r[2] for r in rows),'extreme observational world');eq(tuple(v-u for u,v in zip(w[1],w[2])),(beta,)*3,'extreme response')
    invalid=[lambda:loan(-1,(1,),1),lambda:loan(1,(),1),lambda:loan(1,(None,),1),lambda:loan(1,(1,),0),lambda:loan(True,(1,),1),lambda:demand_world(rows,-1),lambda:demand_world(((0,1,9),),1),lambda:demand_world(((1,3,8),),1),lambda:robust_oracle((F(-1,10),F(1,2)),losses),lambda:robust_oracle((F(3,4),F(1,4)),losses),lambda:robust_oracle((F(0),F(2)),losses),lambda:robust_oracle((F(0),F(1)),(F(0),F(3))),lambda:robust_oracle((True,F(1)),losses)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    summary={'assessment':'research-portfolio','status':'passed','runtime_files':4,'actual_work_artifact_contracts':5,'operational_forms':8,'calibration_cases_and_solutions':3,'prerequisite_volumes':5,'V16_chapter_gates':12,'numeric_markers':len(values),'comparisons':count,'robust_interval_worlds':interval_worlds,'invalid_domains':len(invalid),'scope':'Full prose/proofs/decisions separately read; no candidate achievement, actual reviewer endorsement or completed human evaluation inferred.'};json.dumps(summary,allow_nan=False);return summary

if __name__=='__main__':
    need(len(sys.argv)<=2,'at most one root path');check(sys.argv[1] if len(sys.argv)==2 else None)
