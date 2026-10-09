"""Independent bounded peer certificates for V11 C05.

The frozen author checker is read and byte-bound, never called as an oracle.
check() is quiet and uses exact transaction vectors, collateral complementarity,
closed annuity formulas and dated resource constraints. No assert-only gates.
"""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'content/projects'
AUTHOR_PATHS=[
 'content/chapters/v11-c05.html','content/projects/v11-c05-inputs.json',
 'content/projects/v11-c05-analysis.py','content/projects/v11-c05-output.json',
 'content/projects/v11-c05-manifest.json','content/projects/v11-c05-README.txt',
 'scripts/check_v11_c05.py','content/reviews/v11-c05-author.json',
 'content/reviews/v11-c05-sources.json']
FROZEN=[
 '7fb3bb32372308aa082d42deafe0b5ca8cfefd5443bae4d86d34b7333941fbc3',
 'ec341c6854b710420ed768071e1455e2e5101f080f805111df7cf951eed44444',
 '5b13f378124a8be5d895ca74b5ad0d6b9121fac8e2d7e496418de0507afc4c8a',
 'cc803c4c9809c6ec4bfaa73eef9bb2c4f32cf244f66287dabae3af5067c1671a',
 '81423b0c3b3088256d172dd039e89add34da21ae8ba5359aac65e9e60239c920',
 '8f60863428caec4f123a9f10a6d61b738924837e0ce1a0ba3d946a745f048253',
 'b88b658863e1ceb5a3d8b2b3cd4395ac6e6f9c81c0e2157210e5f90f6367aec8',
 'f6b720937e2618bb82ca36b1880238923572a8867603bccc69bbca67cdbc86af',
 '612c9a871557a5057ddb0a89936d2966823421ea002820f389f1414025c503c2']
ASSETS={'cash','loans','securities_book','initial_margin'}
LIABILITIES={'deposits','legacy_principal','legacy_interest_payable','other_liabilities','rollover_principal','secured_principal','new_interest_payable'}
COUNT={}


def need(condition,label):
    COUNT['comparisons']+=1
    if not condition:raise ValueError('c05 peer: '+label)


def eq(a,b,label):
    need(a==b,label+': '+repr(a)+' != '+repr(b))


def strict(text):
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('duplicate JSON key')
            out[k]=v
        return out
    def invalid(s):raise ValueError('nonfinite JSON constant '+s)
    return json.loads(text,object_pairs_hook=unique,parse_constant=invalid)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def fractions(row):return {k:F(v) for k,v in row.items()}


def opening_accounts(data):
    o=fractions(data['opening'])
    units=sum(o[k] for k in ('eligible_units','already_pledged_units','inaccessible_units'))
    state={k:o[k] for k in ('cash','loans','initial_margin','deposits','legacy_principal','legacy_interest_payable','other_liabilities')}
    state.update(securities_book=units*o['security_book_per_unit'],rollover_principal=F(0),secured_principal=F(0),new_interest_payable=F(0))
    state['equity']=sum(state[k] for k in ASSETS)-sum(state[k] for k in LIABILITIES)
    return state


def funding_certificate(data,out):
    """Every expected posting is independently specified by the contract.

    Complementarity certifies principal amounts without trusting a shared min()
    helper. Transaction-vector sums reconstruct complete accounts and cash cuts;
    reported entries must have the correct semantic account pair, not just net0.
    """
    o=fractions(data['opening']);p=fractions(data['policy']);initial=opening_accounts(data)
    eq(F(out['opening_book_equity']),initial['equity'],'independent opening residual equity')
    eq(F(out['upfront_cash_equity']),p['upfront_cash_equity'],'explicit capital cash source')
    eq(len(out['scenarios']),len(data['scenarios']),'every scenario reported once')
    no_buffer=[];headrooms=[];requirements=[]
    for s,result in zip(data['scenarios'],out['scenarios']):
        eq(result['name'],s['name'],'scenario identity/order')
        offer=F(s['secured_offer_fraction']);a0=p['initial_security_price']*(1-p['initial_haircut'])
        a2=F(s['maintenance_price'])*(1-F(s['maintenance_haircut']))
        cap0=o['eligible_units']*a0;cap2=o['eligible_units']*a2
        d=F(result['secured_draw']);paydown=F(result['collateral_principal_paydown']);m=d-paydown
        if offer==0:eq(d,0,'no offer supplies no cash')
        else:
            unscaled=d/offer
            need(0<=unscaled<=p['secured_target'] and unscaled<=cap0,'initial advance respects both finite bounds')
            eq((p['secured_target']-unscaled)*(cap0-unscaled),0,'initial draw saturates target or collateral capacity')
        need(0<=m<=d and m<=cap2,'remaining principal feasible')
        eq((d-m)*(cap2-m),0,'maintenance keeps maximal covered principal')
        term=o['legacy_principal']*F(s['rollover_fraction'])
        interest=[p['secured_interval_rate']*z+p['rollover_interval_rate']*term for z in [d,m,m]]
        eq(tuple(F(result[k]) for k in ('initial_secured_capacity','maintenance_capacity','rollover_draw','secured_interest_total','rollover_interest_total')),
           (cap0,cap2,term,p['secured_interval_rate']*sum([d,m,m]),p['rollover_interval_rate']*term*3),'capacity and principal-time interest integrals')
        expected={}
        def pair(t,label,left,right,amount):
            expected[t,label]={left:amount,right:amount}
        expected[0,'upfront_cash_equity']={'cash':p['upfront_cash_equity'],'equity':p['upfront_cash_equity']}
        pair(1,'secured_draw','cash','secured_principal',d)
        pair(1,'new_rollover_draw','cash','rollover_principal',term)
        pair(1,'legacy_principal_repayment','cash','legacy_principal',-o['legacy_principal'])
        pair(1,'legacy_accrued_interest_payment','cash','legacy_interest_payable',-o['legacy_interest_payable'])
        margins=[o['initial_margin']]+list(map(F,s['initial_margin_targets']))
        for t in range(1,5):
            z=F(s['loan_principal_receipts'][t-1]);expected[t,'loan_principal_receipt']={'cash':z,'loans':-z}
            pair(t,'deposit_withdrawal','cash','deposits',-F(s['deposit_withdrawals'][t-1]))
            pair(t,'other_liability_payment','cash','other_liabilities',-F(s['other_liability_payments'][t-1]))
            pair(t,'variation_settlement','cash','equity',F(s['variation_settlements'][t-1]))
            change=margins[t]-margins[t-1];expected[t,'initial_margin_transfer']={'cash':-change,'initial_margin':change}
            if t>=2:expected[t,'funding_interest_accrual']={'equity':-interest[t-2],'new_interest_payable':interest[t-2]}
        expected[2,'customer_line_advance']={'cash':-F(s['customer_line_draw']),'loans':F(s['customer_line_draw'])}
        pair(2,'collateral_principal_paydown','cash','secured_principal',-paydown)
        pair(4,'secured_maturity_repayment','cash','secured_principal',-m)
        pair(4,'rollover_maturity_repayment','cash','rollover_principal',-term)
        pair(4,'funding_interest_payment','cash','new_interest_payable',-sum(interest))
        journal=result['journal'];keys=[(e['cutoff'],e['event']) for e in journal]
        eq((len(keys),set(keys)),(len(expected),set(expected)),'complete unique transaction population')
        eq([e['cutoff'] for e in journal],sorted(e['cutoff'] for e in journal),'chronological journal')
        state=dict(initial);cash_paths={t:[] for t in range(5)}
        for entry,key in zip(journal,keys):
            changes=fractions(entry['changes']);eq(changes,expected[key],'correct contract accounts and amount '+key[1])
            for account,value in changes.items():state[account]+=value
            assets=sum(state[k] for k in ASSETS);liabilities=sum(state[k] for k in LIABILITIES)
            eq(tuple(F(entry[k]) for k in ('cash_flow','equity_change','assets_after','liabilities_after','equity_after','balance_error')),
               (changes.get('cash',F(0)),changes.get('equity',F(0)),assets,liabilities,state['equity'],assets-liabilities-state['equity']),'journal accounting and reports')
            eq(assets-liabilities-state['equity'],0,'each economic posting conserves balance')
            cash_paths[key[0]].append(state['cash']-o['restricted_cash'])
        hs=[];zeros=[]
        eq(len(result['rows']),4,'four actual cutoff rows')
        for t,row in enumerate(result['rows'],1):
            # Batch linear account projection is insensitive to within-bucket
            # event ordering; this differs from the implementation's state loop.
            projected={k:initial[k]+sum(v.get(k,F(0)) for (date,_),v in expected.items() if date<=t) for k in initial}
            eq(fractions(row['state']),projected,'independent dated account-vector sum')
            h=projected['cash']-o['restricted_cash'];z=h-p['upfront_cash_equity'];hs.append(h);zeros.append(z)
            eq((row['cutoff'],F(row['available_cash']),F(row['available_cash_without_buffer']),F(row['cash_gap'])),(t,h,z,max(F(0),-h)),'timely cash and missing funding')
            assets=sum(projected[k] for k in ASSETS);liabilities=sum(projected[k] for k in LIABILITIES)
            eq(tuple(F(row[k]) for k in ('total_assets','total_liabilities','balance_error')),(assets,liabilities,assets-liabilities-projected['equity']),'row totals reconcile')
            pledge=F(row['new_pledged_units']);free=F(row['free_eligible_units'])
            eq(pledge*(a0 if t==1 else a2),projected['secured_principal'],'each new principal unit has specified support')
            need(pledge>=0 and free>=0,'no negative collateral inventory')
            eq((pledge+free,F(row['already_pledged_units']),F(row['inaccessible_units'])),(o['eligible_units'],o['already_pledged_units'],o['inaccessible_units']),'same security unit never belongs to two pools')
            price=p['initial_security_price'] if t==1 else F(s['maintenance_price'])
            units=o['eligible_units']+o['already_pledged_units']+o['inaccessible_units']
            eq(F(row['marked_equity']),projected['equity']+units*(price-o['security_book_per_unit']),'book-to-market proxy is a separate valuation')
            # No positive external receipt is placed after a cash payment.
            flows=[F(e['cash_flow']) for e in journal if e['cutoff']==t]
            saw_payment=False
            for flow in flows:
                if flow<0:saw_payment=True
                if flow>0:need(not saw_payment,'receipt-before-payment execution assumption')
            if all(q>=0 for q in hs):need(min(cash_paths[t])>=0,'feasible cutoff plan has no hidden transient shortfall')
        minimum=max(F(0),-min(zeros));requirements.append(minimum);no_buffer.append(zeros);headrooms.append(hs)
        eq((F(result['required_upfront_cash']),F(result['additional_cash_needed']),result['first_failure_cutoff'],result['feasible_under_fixed_policy']),
           (minimum,max(F(0),minimum-p['upfront_cash_equity']),next((i for i,x in enumerate(hs,1) if x<0),None),min(hs)>=0),'finite prefix certificate and first failure')
    required=max(requirements);cert=out['fixed_policy_certificate']
    binding=[{'scenario':s['name'],'cutoff':i} for s,hs in zip(data['scenarios'],no_buffer) for i,h in enumerate(hs,1) if required>0 and -h==required]
    eq(cert,{'required_upfront_cash':str(required),'additional_cash_needed':str(max(F(0),required-p['upfront_cash_equity'])),'binding_cutoffs':binding,'all_scenarios_feasible':all(min(hs)>=0 for hs in headrooms)},'common maximum deficit is conditional fixed-policy cash minimum')
    return no_buffer


def annuity(face,coupon,n,y):
    """Geometric closed form, including its removable zero-yield singularity."""
    cash_coupon=face*coupon
    if y==0:return face+n*cash_coupon,-n*face-cash_coupon*n*(n+1)/2
    discount=(1+y)**(-n);ds=-n*discount/(1+y)
    value=cash_coupon*(1-discount)/y+face*discount
    slope=cash_coupon*(-ds*y-(1-discount))/y**2+face*ds
    return value,slope


def alm_certificate(data,out):
    a=data['alm'];f=lambda k:F(a[k])
    eq(len(out['alm']),2,'two explicit ALM curve cases')
    for row,label in zip(out['alm'],['base','shock']):
        y=f(label+'_yield');av,ad=annuity(f('asset_face'),f('asset_coupon_rate'),a['asset_years'],y)
        lv,ld=annuity(f('fixed_liability_face'),f('fixed_liability_coupon_rate'),a['liability_years'],y)
        floatpv=annuity(f('floating_liability_face'),y,a['liability_years'],y)[0]
        eq(floatpv,f('floating_liability_face'),'coupled floating reset and discount telescope to par')
        eq(row['case'],label,'ALM scenario identity')
        values={'yield':y,'asset_pv':av,'fixed_liability_pv':lv,'floating_liability_pv':floatpv,'economic_equity':f('cash')+av-lv-floatpv,'next_year_interest_income_net':f('asset_face')*f('asset_coupon_rate')-f('fixed_liability_face')*f('fixed_liability_coupon_rate')-f('floating_liability_face')*y,'asset_yield_derivative':ad,'fixed_liability_yield_derivative':ld,'economic_equity_yield_derivative':ad-ld,'nii_yield_derivative':-f('floating_liability_face')}
        eq({k:F(row[k]) for k in values},values,'geometric annuity values and derivative, separate NII horizon')
    fx=fractions(data['currency_case']);conversion=fx['foreign_cash']*fx['cu_per_fu'];gap=fx['local_cash']-fx['payment_due']
    eq(fractions(out['currency_case']),{'potential_converted_cu':conversion,'no_authorized_transfer_headroom':gap,'authorized_timely_transfer_headroom':gap+conversion,'authorized_late_transfer_headroom_at_deadline':gap,'authorized_late_transfer_headroom_after_receipt':gap+conversion},'FX dimensional conversion does not imply authority or timely delivery')


def run_case(run,data,label,funding=True):
    before=copy.deepcopy(data);capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):out=run(data)
    eq(capture.getvalue(),'','quiet run '+label);eq(data,before,'no input mutation '+label)
    eq(strict(json.dumps(out,allow_nan=False)),out,'strict JSON result '+label)
    if funding:funding_certificate(data,out)
    alm_certificate(data,out);COUNT['cases']+=1
    return out


def changed(base,path,value):
    data=copy.deepcopy(base);target=data
    for key in path[:-1]:target=target[key]
    target[path[-1]]=value
    return data


def interventions(run,base,baseline):
    heads=[[F(r['available_cash']) for r in s['rows']] for s in baseline['scenarios']]
    eq(heads,[list(map(F,h)) for h in [['33.6','38.6','48.6','27.1'],['-6.4','-1.4','8.6','27.7'],['-13.4','-39.9','-29.9','3.81']]],'all original worked cash anchors')
    joint=copy.deepcopy(base);joint['scenarios']=[joint['scenarios'][2]]
    def test(data,label,funding=True):
        COUNT['financial_interventions']+=1
        return run_case(run,data,label,funding)
    for b,okay in [('39.9',True),('39.899',False)]:
        out=test(changed(base,['policy','upfront_cash_equity'],b),'reserve at/just below proven minimum')
        eq(out['fixed_policy_certificate']['all_scenarios_feasible'],okay,'exact threshold, no numerical tolerance')
        eq(F(out['scenarios'][2]['rows'][1]['available_cash']),F(b)-F('39.9'),'binding dated cash boundary')
    half=changed(joint,['scenarios',0,'secured_offer_fraction'],'0.5')
    out=test(half,'partial funding access, earlier cash versus final interest')
    eq([F(r['available_cash']) for r in out['scenarios'][0]['rows']],list(map(F,['-28.4','-49.4','-39.4','4.15'])),'partial offer has greater initial deficit despite greater final cash')
    high=changed(half,['policy','secured_target'],'100')
    out=test(high,'offer fraction applies after capacity-limited target')
    eq(F(out['scenarios'][0]['secured_draw']),20,'contract draw scales capacity-limited amount')
    out=test(changed(joint,['scenarios',0,'variation_settlements'],['-3','0','-4','10']),'same net derivative gain, later loss timing')
    eq([F(r['available_cash']) for r in out['scenarios'][0]['rows']],list(map(F,['-13.4','-30.9','-29.9','3.81'])),'dated derivative loss changes reserve but not final income')
    haircut=changed(joint,['scenarios',0,'maintenance_haircut'],'1/7')
    out=test(haircut,'exact maintenance no-paydown boundary')
    eq(F(out['scenarios'][0]['collateral_principal_paydown']),0,'exercise2 rational haircut equality')
    eq(F(out['scenarios'][0]['rows'][1]['marked_equity']),F('-11.7'),'haircut alone is not a security-price mark')
    late=changed(joint,['opening','eligible_units'],'37.5');late['opening']['inaccessible_units']='22.5'
    out=test(late,'deliverable inventory reduced without removing owned assets')
    eq((F(out['scenarios'][0]['collateral_principal_paydown']),F(out['scenarios'][0]['rows'][1]['available_cash'])),(F('11.625'),F('-46.025')),'late collateral changes maintenance cash burden')
    out=test(changed(joint,['scenarios',0,'loan_principal_receipts'],['0','0','30','40']),'loan receipt delayed beyond binding cutoff')
    eq((F(out['fixed_policy_certificate']['required_upfront_cash']),F(out['scenarios'][0]['rows'][-1]['available_cash'])),(F('51.9'),F('3.81')),'unchanged final collection cannot fund past deficit')
    out=test(changed(joint,['scenarios',0,'initial_margin_targets'],['0','9','9','0']),'release opening margin then repost at cutoff2')
    eq([F(r['available_cash']) for r in out['scenarios'][0]['rows']],list(map(F,['-8.4','-39.9','-29.9','3.81'])),'temporary margin release does not create income or lasting funds')
    out=test(changed(joint,['opening','legacy_interest_payable'],'1.4'),'larger already-accrued old interest')
    eq(F(out['scenarios'][0]['rows'][-1]['state']['equity']),F('25.81'),'old accrued expense enters opening equity, not a second new expense')
    for y in ['-0.1','0','0.25']:
        a=changed(joint,['alm','shock_yield'],y);a['alm']['asset_years']=1;a['alm']['liability_years']=10
        out=test(a,'negative/zero/upper yield and maturity endpoints',False)
        eq(F(out['alm'][1]['floating_liability_pv']),20,'floating par includes negative and zero coupons')
    fx=changed(joint,['currency_case','foreign_cash'],'7');fx['currency_case']['cu_per_fu']='1.2'
    out=test(fx,'exercise6 new currency amounts',False)
    eq(F(out['currency_case']['authorized_timely_transfer_headroom']),F('.4'),'transferred exercise currency amount')
    # Independent exercise anchors and complete bridge feasibility certificate.
    eq(1-F(30)/(50*F('.7')),F(1,7),'maximum haircut proof boundary')
    eq(F('11.625')-F('5.5'),F('6.125'),'lost delivery funding capacity')
    state=baseline['scenarios'][2]['rows'][1]['state']
    eq(tuple(F(state[k]) for k in ['equity','cash','loans','initial_margin']),tuple(map(F,['12.3','-35.9','150','9'])),'exercise3 journal assets and equity')
    eq(F('-35.9')+150+80+9,F('190.8')+F('12.3'),'exercise3 balance identity with diagnostic missing cash')
    lower=max(F(0),max(-h for hs in heads for h in hs[:3]));terminal=min(hs[-1] for hs in heads)
    eq((lower,terminal/F('.02')),(F('39.9'),F('190.5')),'bridge exact feasible interval')
    for amount,expected in [('39.89',False),('39.9',True),('190.5',True),('190.51',False)]:
        b=F(amount);dates=[x+b for hs in heads for x in hs[:3]]+[hs[-1]-F('.02')*b for hs in heads]
        eq(min(dates)>=0,expected,'bridge independently tests all dates at interval edges')
    eq(terminal-F('.02')*lower,F('3.012'),'bridge lower endpoint final cash')
    need(terminal/F('.1')<lower,'ten-percent bridge infeasible for every amount')
    eq(F(baseline['scenarios'][1]['rows'][-1]['state']['equity']),F('25.7'),'exercise1 unbuffered ending equity')
    eq(F('25.7')+F('6.4'),F('32.1'),'exercise1 cash-equity injection changes both accounts')
    a=base['alm'];slope=F(baseline['alm'][0]['economic_equity_yield_derivative'])
    need(abs(float(slope)-160.41709056656532)<1e-10,'exercise5 derivative stated decimal')
    eq(F(baseline['alm'][1]['next_year_interest_income_net']),F('-.4'),'exercise5 opposite NII')
    eq(F('5.4')-F('.2'),F('5.2'),'morning coupon requires actual usable cash')
    step=F(1,10000000);y=F('.05')
    def eve(rate):
        return F(a['cash'])+annuity(F(a['asset_face']),F(a['asset_coupon_rate']),a['asset_years'],rate)[0]-annuity(F(a['fixed_liability_face']),F(a['fixed_liability_coupon_rate']),a['liability_years'],rate)[0]-F(a['floating_liability_face'])
    need(abs((eve(y+step)-eve(y-step))/(2*step)-slope)<F(1,1000000),'symmetric price perturbation confirms local yield sensitivity')
    need(abs(float(eve(F('.07'))-eve(y))-2.944279562465054)<1e-11,'exact two-percentage-point gain distinct from tangent')
    eq((max(0,-min([-4,5,-3])),15-25*F('.8')*F('.6'),-30*F('.015')),(4,3,F('-.45')),'all delayed retention transferred calculations')


def invalid_data(run,base):
    alternatives=[(['schema_version'],True),(['opening','cash'],20),(['opening','cash'],'NaN'),(['opening','cash'],'1e2'),(['opening','cash'],'1/0'),(['opening','cash'],'1/10000000000000'),(['opening','restricted_cash'],'21'),(['opening','deposits'],'1000'),(['policy','initial_security_price'],'0'),(['policy','initial_haircut'],'1'),(['policy','secured_interval_rate'],'-0.01'),(['scenarios'],[]),(['scenarios',1,'name'],'base'),(['scenarios',0,'secured_offer_fraction'],'1.01'),(['scenarios',0,'maintenance_haircut'],'0.96'),(['scenarios',0,'loan_principal_receipts'],['0','0','0','151']),(['scenarios',0,'customer_line_draw'],'16'),(['scenarios',0,'deposit_withdrawals'],['0']),(['scenarios',0,'initial_margin_targets'],['5','5','5','1']),(['alm','liability_years'],True),(['alm','base_yield'],'-0.11'),(['currency_case','cu_per_fu'],'0')]
    invalid=[changed(base,path,value) for path,value in alternatives]
    extra=copy.deepcopy(base);extra['opening']['unlisted_overdraft']='10';invalid.append(extra)
    missing=copy.deepcopy(base);del missing['scenarios'][0]['rollover_fraction'];invalid.append(missing)
    for data in invalid:
        before=copy.deepcopy(data);capture=io.StringIO()
        with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
            try:run(data)
            except ValueError:COUNT['api_rejections']+=1
            else:raise ValueError('invalid domain accepted')
        eq((capture.getvalue(),data),('',before),'invalid API quiet and nonmutating')


class Markup(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.ids=[];self.pairs=[];self.sources=set();self.links=[];self.worked=0;self.exercises=0;self.solutions=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);c=a.get('class','').split()
        if 'id' in a:self.ids.append(a['id'])
        if 'data-solution-for' in a:self.pairs.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.add(a['data-source'])
        if 'href' in a:self.links.append(a['href'])
        if 'worked' in c:self.worked+=1
        if tag=='li':
            if any(t=='ol' and 'exercises' in classes for t,classes in self.stack):self.exercises+=1
            if any(t=='details' and 'solutions' in classes for t,classes in self.stack):self.solutions+=1
        if tag not in ('br','hr','img','meta','link','input','wbr'):self.stack.append((tag,c))
    def handle_endtag(self,tag):
        if not self.stack or self.stack[-1][0]!=tag:raise ValueError('unbalanced HTML '+tag)
        self.stack.pop()


def bindings():
    for name,expected in zip(AUTHOR_PATHS,FROZEN):eq(digest(ROOT/name),expected,'exact final assigned author SHA256 '+name)
    manifest=strict((PROJECT/'v11-c05-manifest.json').read_text())
    names=['v11-c05-inputs.json','v11-c05-analysis.py','v11-c05-output.json','v11-c05-README.txt']
    eq([r['file'] for r in manifest['files']],names,'four exact portable manifest members')
    for row in manifest['files']:
        path=PROJECT/row['file'];eq((row['bytes'],row['sha256']),(path.stat().st_size,digest(path)),'manifest binding')
    author=strict((ROOT/'content/reviews/v11-c05-author.json').read_text())
    eq((len(author['reviewed_hashes']),{r['path'] for r in author['reviewed_hashes']}),(8,set(AUTHOR_PATHS)-{'content/reviews/v11-c05-author.json'}),'eight nonself author paths')
    for row in author['reviewed_hashes']:
        path=ROOT/row['path'];eq((row['bytes'],row['sha256']),(path.stat().st_size,digest(path)),'author nonself binding')
    peer=strict((ROOT/'content/reviews/v11-c05-peer.json').read_text())
    eq((len(peer['reviewed_hashes']),{r['path'] for r in peer['reviewed_hashes']}),(9,set(AUTHOR_PATHS)),'peer nine exact author paths')
    eq(peer['checker_binding']['path'],'scripts/check_v11_c05_peer.py','own exact peer checker')
    for row in peer['reviewed_hashes']+[peer['checker_binding']]:
        path=ROOT/row['path'];eq((row['bytes'],row['sha256']),(path.stat().st_size,digest(path)),'peer author/checker byte binding')
    eq(len(peer['exercise_audit']),8,'all exact solution/proof audits recorded')
    parser=Markup();parser.feed((ROOT/'content/chapters/v11-c05.html').read_text());parser.close()
    eq(parser.stack,[],'balanced manuscript fragment')
    eq((parser.worked,parser.exercises,parser.solutions),(4,8,8),'worked/prompt/full-solution reader counts')
    eq(len(parser.ids),len(set(parser.ids)),'unique manuscript IDs')
    eq(parser.pairs,['v11-c05-e'+str(i) for i in range(1,9)],'all exact paired solutions')
    eq({h for h in parser.links if h.startswith('v11-c05-')},set(names+['v11-c05-manifest.json']),'five flat portable assets')
    need(not any(h.startswith('projects/') for h in parser.links),'no reader attachment prefix mismatch')
    sources=strict((ROOT/'content/reviews/v11-c05-sources.json').read_text())
    eq(parser.sources,{s['id'] for s in sources},'two precisely scoped citation routes')
    eq(parser.sources,{'v11-c02-bcbs-liquidity2008','v08-c06-credit-lines'},'accepted historical method sources reused')


def portable(base,expected):
    with tempfile.TemporaryDirectory(prefix='c05-peer-portable-') as name:
        folder=Path(name);model=folder/'v11-c05-analysis.py';inp=folder/'v11-c05-inputs.json';out=folder/'report.json'
        shutil.copy2(PROJECT/model.name,model);shutil.copy2(PROJECT/inp.name,inp)
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        for optimized in (False,True):
            command=[sys.executable]+(['-O'] if optimized else [])+[str(model)]
            def execute(args):return subprocess.run(command+args,cwd='/',env=env,text=True,capture_output=True,timeout=20)
            r=execute([]);eq((r.returncode,r.stderr),(0,''),'portable CLI from unrelated cwd')
            eq(strict(r.stdout),expected,'default sibling input and complete stdout JSON')
            r=execute(['--input',str(inp),'--output',str(out)])
            eq((r.returncode,r.stdout,r.stderr),(0,'',''),'quiet output-file execution')
            eq(out.read_bytes(),(PROJECT/'v11-c05-output.json').read_bytes(),'full saved output bytes reproduced')
            for protected in (inp,model):
                for kind in ('direct','resolved','symbolic','hard'):
                    alias=protected
                    if kind=='resolved':
                        (folder/'subdir').mkdir(exist_ok=True);alias=folder/'subdir'/Path('..')/protected.name
                    elif kind in ('symbolic','hard'):
                        alias=folder/(protected.name+'.'+kind)
                        if alias.exists() or alias.is_symlink():alias.unlink()
                        if kind=='symbolic':alias.symlink_to(protected)
                        else:os.link(protected,alias)
                    before=(inp.read_bytes(),model.read_bytes());r=execute(['--output',str(alias)])
                    need(r.returncode==2 and not r.stdout and bool(r.stderr),'output alias explicitly rejected')
                    eq((inp.read_bytes(),model.read_bytes()),before,'input and implementation bytes preserved')
                    COUNT['protected_output_rejections']+=1
            for payload in ['{"schema_version":1,"schema_version":1}','{"x":NaN}',json.dumps(changed(base,['schema_version'],True)),' '*100001]:
                bad=folder/'bad.json';bad.write_text(payload);out.write_text('PRESERVE\n')
                r=execute(['--input',str(bad),'--output',str(out)])
                need(r.returncode==2 and not r.stdout and bool(r.stderr),'invalid CLI rejected')
                eq(out.read_text(),'PRESERVE\n','failed parse/domain input does not replace destination')
                COUNT['cli_data_rejections']+=1


def check():
    global COUNT
    COUNT={'comparisons':0,'cases':0,'financial_interventions':0,'api_rejections':0,'cli_data_rejections':0,'protected_output_rejections':0}
    capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):model=runpy.run_path(str(PROJECT/'v11-c05-analysis.py'))
    eq(capture.getvalue(),'','quiet implementation import')
    base=strict((PROJECT/'v11-c05-inputs.json').read_text());out=run_case(model['run'],base,'complete baseline')
    eq(out,strict((PROJECT/'v11-c05-output.json').read_text()),'saved output after independent contract tests')
    interventions(model['run'],base,out);invalid_data(model['run'],base);portable(base,out);bindings()
    result={'chapter':'v11-c05','status':'passed',**COUNT,'worked_cases':4,'exact_solved_exercises':8,'frozen_author_bindings':9,'checker_binding':1,
            'independent_methods':['contract transaction-vector and dated-resource certificates','collateral capacity/complementarity and inventory identities','closed geometric annuity valuation and yield derivatives','bridge interval and exact financial timing interventions'],
            'normal_and_optimized_portable_model':True,'limits':'Machine-assisted separate peer audit of bounded synthetic claims; no empirical calibration, actual-law conclusion, human certification or whole-edition UI acceptance.'}
    json.dumps(result,allow_nan=False);return result


if __name__=='__main__':print(json.dumps(check(),indent=2,allow_nan=False))
