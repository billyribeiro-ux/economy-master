"""Independent cumulative-cash and balance-sheet audit of the Meridian lab."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


class Markup(HTMLParser):
    def __init__(self):
        super().__init__(); self.worked=0; self.exercises=0; self.solutions=0
        self.stack=[];self.context=[];self.ids=[];self.sources=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);classes=a.get('class','').split()
        if a.get('id'):self.ids.append(a['id'])
        if a.get('data-source'):self.sources.add(a['data-source'])
        if 'worked' in classes:self.worked+=1
        if tag=='details':self.context.append('solutions' in classes)
        if tag=='ol':self.stack.append('ex' if 'exercises' in classes else 'sol' if any(self.context) else '')
        if tag=='li' and self.stack:
            self.exercises+=self.stack[-1]=='ex';self.solutions+=self.stack[-1]=='sol'
    def handle_endtag(self,tag):
        if tag=='ol' and self.stack:self.stack.pop()
        if tag=='details' and self.context:self.context.pop()


def check(root=None):
    root=Path(root) if root else Path(__file__).resolve().parents[1]
    project=root/'content/projects';model=project/'v11-c12-analysis.py'
    data=json.loads((project/'v11-c12-inputs.json').read_text());saved=json.loads((project/'v11-c12-output.json').read_text())
    count={'comparisons':0,'financial_interventions':0,'invalid_api_cases':0,'invalid_cli_cases':0,'protected_alias_attempts':0,'portable_runs':0,'journal_rows':0}
    def need(ok,label):
        if not ok:raise RuntimeError(label)
    def eq(a,b,label):
        count['comparisons']+=1;need(a==b,label+': '+repr(a)+' != '+repr(b))
    capture=io.StringIO()
    with redirect_stdout(capture),redirect_stderr(capture):
        spec=importlib.util.spec_from_file_location('meridian_author_target',model)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    eq(capture.getvalue(),'','quiet import')
    def invoke(d):
        before=deepcopy(d);buf=io.StringIO()
        with redirect_stdout(buf),redirect_stderr(buf):out=module.run(d)
        eq(buf.getvalue(),'','quiet API');eq(d,before,'nonmutating API');return out
    def oracle(d,out):
        """Cumulative cash sums; derive equity from independently priced residual claims."""
        i={k:F(v) for k,v in d['institution'].items()};z={k:F(v) for k,v in d['terms'].items()};lim={k:F(v) for k,v in d['limits'].items()}
        policies=list(product(*(map(F,d['choices'][k]) for k in ('lending','cash_equity','term_replacement'))))
        eq(out['candidate_count'],len(policies),'complete candidate cardinality')
        eq({tuple(F(c['policy'][k]) for k in ('lending','cash_equity','term_replacement')) for c in out['candidates']},set(policies),'exact candidate set')
        good=[]
        for c in out['candidates']:
            x,b,t=(F(c['policy'][k]) for k in ('lending','cash_equity','term_replacement'))
            concentration=(i['cluster_loans']+x)/(i['loans']+x)
            eq(F(c['concentration']),concentration,'original gross concentration')
            score=z['equity_charge']*b+(z['term_fee']+3*z['term_coupon'])*t
            eq(F(c['ranking_cost']),score,'declared score')
            reasons=[]
            if concentration>lim['concentration']:reasons.append('concentration')
            eq([p['scenario'] for p in c['scenario_projections']],[s['id'] for s in d['scenarios']],'exact scenario coverage')
            for s,p in zip(d['scenarios'],c['scenario_projections']):
                price=F(s['security_price']);h=F(s['haircut']);loss=F(s['loan_loss_fixed'])+F(s['loan_loss_per_new'])*x
                receipts=list(map(F,s['principal_receipts']));interest=list(map(F,s['interest_receipts']));w=[F(a)+F(k)*x for a,k in zip(s['withdrawal_fixed'],s['withdrawal_per_new'])]
                opening=i['cash']+b-z['term_fee']*t-F(s['operating_loss']);short=i['short_debt']-t;roll=F(s['rollover'])*short
                available=opening+receipts[0]+interest[0]+roll;due=w[0]+short+z['term_coupon']*t
                pre=available-due;required=max(F(0),lim['cash_floor']-pre)
                cap=min(F(s['facility_ceiling']),i['eligible_units']*price*(1-h)) if s['facility_open'] else F(0)
                draw=min(cap,required)
                for k,val in [('cash_before_secured_draw',pre),('collateral_capacity',cap),('requested_minimum_draw',required),('secured_draw',draw),('pledged_units',draw/(price*(1-h)))]:eq(F(p[k]),val,'independent first funding '+k)
                eq(len(p['cutoffs']),3,'three cutoff certificates');cashpass=True;equitypass=True
                for j,r in enumerate(p['cutoffs'],1):
                    cash=opening+sum(receipts[:j])+sum(interest[:j])-sum(w[:j])-j*z['term_coupon']*t-short
                    cash+=roll+draw if j==1 else -z['roll_interest']*roll-z['secured_interest']*draw
                    if j==3:cash-=t
                    loans=i['loans']+x-loss-sum(receipts[:j]);deposits=i['deposits']+x-sum(w[:j])
                    assets=cash+i['security_units']*price+loans;liabilities=deposits+(roll+draw if j==1 else F(0))+(t if j<3 else F(0));equity=assets-liabilities
                    for k,val in [('cash_after_full_planned_payments',cash),('equity',equity),('loans',loans),('deposits',deposits),('assets',assets),('liabilities',liabilities),('rolled_debt',roll if j==1 else F(0)),('secured_debt',draw if j==1 else F(0)),('term_debt',t if j<3 else F(0)),('cash_short_of_floor',max(F(0),lim['cash_floor']-cash)),('unfinanced_payment_shortfall',max(F(0),-cash))]:eq(F(r[k]),val,'cumulative contract '+k)
                    eq(r['cutoff'],j,'cutoff order');cashpass &= cash>=lim['cash_floor'];equitypass &= equity>=lim['equity_floor']
                eq(p['cash_limits_met'],cashpass,'cash gates');eq(p['equity_limits_met'],equitypass,'equity gates')
                if not cashpass:reasons.append(s['id']+':cash')
                if not equitypass:reasons.append(s['id']+':equity')
            eq(c['failed_gates'],reasons,'all failure reasons');eq(c['feasible'],not reasons,'feasibility')
            if not reasons:good.append(((-x,score,b,t),c['policy']))
        good.sort(key=lambda a:a[0]);eq(out['feasible_count'],len(good),'exact feasible count');eq(out['selected_policy'],good[0][1] if good else None,'finite global selection')
        eq(out['selected_ranking_cost'],str(good[0][0][1]) if good else None,'selected score')
        if not good:eq(out['selected_execution'],[],'no unfunded execution')
        g,f,z0,d0,alpha=(F(d['incentives'][k]) for k in ('concealment_bonus','funded_penalty','common_audit_failure','conditional_detection','false_positive'))
        p=(1-z0)*d0;truth=-alpha*f;conceal=(1-p)*g-p*f
        for k,val in [('effective_detection',p),('truthful_expected_payoff',truth),('conceal_expected_payoff',conceal),('truthful_advantage',truth-conceal),('weak_truthful_threshold',(g+alpha*f)/(g+f))]:eq(F(out['incentive'][k]),val,'two action payoff '+k)
        eq(out['incentive']['truthful_weakly_preferred'],truth>=conceal,'weak incentive');eq(out['incentive']['truthful_strictly_preferred'],truth>conceal,'strict incentive')
        count['financial_interventions']+=1
    baseline=invoke(data);eq(baseline,saved,'saved output');oracle(data,baseline)
    eq(baseline['selected_policy'],{'lending':'20','cash_equity':'20','term_replacement':'20'},'baseline exact optimum')
    eq(baseline['feasible_count'],3,'baseline feasible plans')
    # Inspect the actual selected journal by accumulating declared account changes
    # and independently comparing every dated cash/equity endpoint to the oracle.
    selected=next(c for c in baseline['candidates'] if c['policy']==baseline['selected_policy'])
    eq(len(baseline['selected_execution']),3,'three selected executions')
    for execution,p in zip(baseline['selected_execution'],selected['scenario_projections']):
        prev=None;bydate={}
        for row in execution['rows']:
            accounts={k:F(v) for k,v in row['accounts'].items()}
            eq(set(accounts),{'cash','securities','loans','deposits','old_short','rolled','secured','term','equity'},'exact account population')
            if prev is not None:
                expected={k:prev[k]+F(row['changes'].get(k,'0')) for k in prev};eq(accounts,expected,'declared event deltas')
            assets=sum(accounts[k] for k in ('cash','securities','loans'));liabilities=sum(accounts[k] for k in ('deposits','old_short','rolled','secured','term'))
            eq(assets-liabilities,accounts['equity'],'event conservation');need(all(v>=0 for k,v in accounts.items() if k!='equity'),'executed negative asset/debt')
            need(F(0)<=F(row['pledged_units'])<=F(data['institution']['eligible_units']),'eligible pledge bound')
            prev=accounts;bydate[row['date']]=accounts;count['journal_rows']+=1
        for j,point in enumerate(p['cutoffs'],1):
            eq(bydate[j]['cash'],F(point['cash_after_full_planned_payments']),'executed final cash');eq(bydate[j]['equity'],F(point['equity']),'executed final equity')
        eq(F(execution['remaining_deposits']),prev['deposits'],'residual debt retained')
    joint=baseline['selected_execution'][2]
    eq(min(F(r['accounts']['equity']) for r in joint['rows']),F('18.6'),'intraday capital boundary')
    cases=[]
    def changed(path,value):
        d=deepcopy(data);o=d
        for k in path[:-1]:o=o[k]
        o[path[-1]]=value;return d
    cases.append((changed(('limits','concentration'),'0.4'),('10','20','20')))
    late=changed(('scenarios',2,'facility_open'),False);cases.append((late,None))
    expanded=deepcopy(late);expanded['choices']['cash_equity'].append('30');cases.append((expanded,('10','30','20')))
    expanded=deepcopy(data);expanded['choices']['cash_equity'].append('30');cases.append((expanded,('30','30','20')))
    early=changed(('scenarios',2,'withdrawal_fixed',0),'45');early['scenarios'][2]['withdrawal_fixed'][1]='15';cases.append((early,('0','20','20')))
    cases.append((changed(('terms','secured_interest'),'0.4'),('10','20','20')))
    cases.append((changed(('incentives','conditional_detection'),'0.75'),('20','20','20')))
    cases.append((changed(('limits','equity_floor'),'30'),None))
    intraday=deepcopy(data);intraday['choices']={'lending':['20'],'cash_equity':['21.4'],'term_replacement':['20']};cases.append((intraday,('20','107/5','20')))
    early_cash=deepcopy(early);early_cash['choices']={'lending':['20'],'cash_equity':['24.1'],'term_replacement':['20']};cases.append((early_cash,('20','241/10','20')))
    for d,expect in cases:
        out=invoke(d);oracle(d,out)
        eq(tuple(out['selected_policy'][k] for k in ('lending','cash_equity','term_replacement')) if out['selected_policy'] else None,expect,'financial intervention result')
        if d is intraday:
            eq(min(F(r['accounts']['equity']) for r in out['selected_execution'][2]['rows']),F(20),'all-event equity repair')
            eq(next(c for c in out['candidates'] if c['feasible'])['scenario_projections'][2]['secured_draw'],'56/5','repaired minimum borrowing')
        if d is early_cash:
            eq(next(c for c in out['candidates'] if c['feasible'])['scenario_projections'][2]['secured_draw'],'27/2','early-withdrawal funding boundary')
    for penalty,common,detect,false,expected_advantage in [('6','0.2','0.5','0.05',F('-0.3')),('3','0.5','1','0',F('-0.5')),('6','0.4','0.5','0.05',F('-1.3')),('6','0.2','0.75','0.05',F('1.7'))]:
        d=deepcopy(data);d['incentives'].update(funded_penalty=penalty,common_audit_failure=common,conditional_detection=detect,false_positive=false)
        result=invoke(d)['incentive'];eq(F(result['truthful_advantage']),expected_advantage,'exact incentive transfer')
    invalid=[(('schema',),True),(('institution','cash'),24),(('institution','cash'),'NaN'),(('institution','cash'),'1e2'),(('institution','eligible_units'),'61'),(('institution','cluster_loans'),'117'),(('choices','lending'),['0','0.0']),(('choices','term_replacement'),['31']),(('limits','concentration'),'1.1'),(('scenarios',2,'facility_open'),1),(('scenarios',2,'haircut'),'1'),(('scenarios',2,'principal_receipts'),['200','0','0']),(('scenarios',2,'withdrawal_fixed'),['200','0','0']),(('scenarios',1,'id'),'calm'),(('incentives','concealment_bonus'),'0')]
    for path,value in invalid:
        bad=changed(path,value);before=deepcopy(bad);buf=io.StringIO()
        try:
            with redirect_stdout(buf),redirect_stderr(buf):module.run(bad)
        except ValueError:count['invalid_api_cases']+=1
        else:raise RuntimeError('invalid input accepted '+repr(path))
        eq(bad,before,'invalid input not mutated');eq(buf.getvalue(),'','invalid API quiet')
    html=(root/'content/chapters/v11-c12.html').read_text();parsed=Markup();parsed.feed(html)
    eq((parsed.worked,parsed.exercises,parsed.solutions),(4,10,10),'full reader package');eq(len(parsed.ids),len(set(parsed.ids)),'unique anchors')
    eq(parsed.sources,{'v11-c12-bcbs-governance2015','v08-c11-oecd-board','v08-c11-oecd-scope'},'scoped source set')
    for value in ('8911/500','11411/500','4311/500','12311/500','52/3','43/80','3004/125','3583/250'):
        need(value in html,'missing exact solution anchor '+value)
    for phrase in ('Teach-back','Delayed check','unmodeled fourth','18.6','not total funding cost'):
        need(phrase in html,'missing substantive boundary '+phrase)
    manifest=json.loads((project/'v11-c12-manifest.json').read_text())
    expected={f'v11-c12-{s}' for s in ('inputs.json','analysis.py','output.json','README.txt')}
    eq({r['file'] for r in manifest['files']},expected,'four portable manifest payloads');eq(len(manifest['files']),4,'no duplicate manifest')
    for row in manifest['files']:
        raw=(project/row['file']).read_bytes();eq((len(raw),hashlib.sha256(raw).hexdigest()),(row['bytes'],row['sha256']),'manifest binding')
    author=json.loads((root/'content/reviews/v11-c12-author.json').read_text())
    paths=['content/chapters/v11-c12.html']+['content/projects/v11-c12-'+s for s in ('inputs.json','analysis.py','output.json','manifest.json','README.txt')]+['scripts/check_v11_c12.py','content/reviews/v11-c12-sources.json']
    eq({r['path'] for r in author['reviewed_hashes']},set(paths),'exact eight author bindings');eq(len(author['reviewed_hashes']),8,'nonduplicated author bindings')
    for row in author['reviewed_hashes']:
        raw=(root/row['path']).read_bytes();eq((len(raw),hashlib.sha256(raw).hexdigest()),(row['bytes'],row['sha256']),'author payload binding')
    with tempfile.TemporaryDirectory(prefix='v11-c12-author-') as td:
        temp=Path(td);m=temp/model.name;inp=temp/'v11-c12-inputs.json';shutil.copy2(model,m);shutil.copy2(project/inp.name,inp)
        for opt in (False,True):
            cmd=[sys.executable]+(['-O'] if opt else [])+[str(m)]
            for explicit in (False,True):
                dest=temp/('explicit.json' if explicit else 'v11-c12-output.json')
                p=subprocess.run(cmd+(['--input',str(inp),'--output',str(dest)] if explicit else []),cwd=temp.parent,capture_output=True,text=True,timeout=30)
                eq((p.returncode,p.stdout,p.stderr),(0,'',''),'portable quiet CLI');eq(dest.read_bytes(),(project/'v11-c12-output.json').read_bytes(),'exact portable output');count['portable_runs']+=1
            for protected in (inp,m):
                for kind in ('direct','resolved','symlink','hardlink'):
                    target=protected
                    if kind=='resolved':(temp/'nested').mkdir(exist_ok=True);target=temp/'nested'/'..'/protected.name
                    if kind in ('symlink','hardlink'):
                        target=temp/(protected.name+'.'+kind)
                        if target.exists() or target.is_symlink():target.unlink()
                        if kind=='symlink':target.symlink_to(protected)
                        else:os.link(protected,target)
                    old={f:f.read_bytes() for f in (inp,m)}
                    p=subprocess.run(cmd+['--output',str(target)],cwd=temp.parent,capture_output=True,text=True,timeout=30)
                    eq((p.returncode,p.stdout),(2,''),'protected alias rejection');need(bool(p.stderr),'missing alias diagnostic')
                    for f,b in old.items():eq(f.read_bytes(),b,'protected bytes preserved')
                    count['protected_alias_attempts']+=1
            for content in ('{"schema":1,"schema":1}','{"schema":NaN}','[]',' '*65537):
                bad=temp/'bad.json';bad.write_text(content);dest=temp/'preserve.json';dest.write_text('unchanged')
                p=subprocess.run(cmd+['--input',str(bad),'--output',str(dest)],cwd=temp.parent,capture_output=True,text=True,timeout=30)
                eq((p.returncode,p.stdout),(2,''),'invalid CLI rejection');eq(dest.read_text(),'unchanged','invalid output untouched');count['invalid_cli_cases']+=1
    return {'chapter':'v11-c12','status':'passed',**count,'author_payloads_bound':8,'worked_examples':4,'solved_exercises':10,'limits':'Original finite contract and mathematical tests; independent peer, factual applicability and actual authority remain distinct.'}


if __name__=='__main__':print(json.dumps(check(),sort_keys=True))
