"""Bounded independent certificates for the c07 synthetic stress package."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'content/projects'
MODEL = PROJECT/'v11-c07-analysis.py'


def need(condition, label):
    if not condition: raise ValueError('c07 check: '+label)


def exact(value):
    if isinstance(value,F): return str(value)
    if isinstance(value,dict): return {k:exact(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [exact(v) for v in value]
    return value


class Audit:
    def __init__(self):
        self.comparisons=0;self.interventions=0;self.rejections=0;self.journal_rows=0

    def eq(self,actual,expected,label):
        self.comparisons+=1
        need(exact(actual)==exact(expected),label+': '+repr(actual)+' != '+repr(exact(expected)))


def quantities(data):
    return {k:F(v) if type(v) is str and k != 'id' else v for k,v in data.items()}


def network_certificate(a,n,s,got):
    T,share,b,c=n['obligation'],n['interbank_share'],s['external_b'],s['external_c']
    p,q=F(got['payment_b']),F(got['payment_c'])
    # Independent monotone lower/upper iterates bracket the unique solution.
    lower=(F(0),F(0));upper=(T,T)
    for unused in range(24):
        lower=(min(T,b+share*lower[1]),min(T,c+share*lower[0]))
        upper=(min(T,b+share*upper[1]),min(T,c+share*upper[0]))
    a.eq(lower[0]<=p<=upper[0] and lower[1]<=q<=upper[1],True,'monotone clearing bounds')
    a.eq(0<=p<=T and 0<=q<=T,True,'payment domain')
    # Capped resource complementarity plus proved uniqueness is an exact certificate.
    rb,rc=b+share*q-p,c+share*p-q
    a.eq(rb>=0 and rc>=0 and (p==T or rb==0) and (q==T or rc==0),True,
         'limited liability, full-payment cap and no withholding in default')
    expected=dict(payment_b=p,payment_c=q,interbank_b_receipt=share*q,interbank_c_receipt=share*p,
        institution_receipt=(1-share)*p,other_outside_receipt=(1-share)*q,
        retained_b=rb,retained_c=rc,unpaid_b=T-p,unpaid_c=T-q,
        external_resource_residual=F(0),
        standalone_institution_receipt=(1-share)*min(T,b+share*T),
        feedback_loss=(1-share)*(min(T,b+share*T)-p))
    a.eq(got,expected,'all network distributions and counterparty benchmark')
    a.eq(b+c,(1-share)*(p+q)+rb+rc,'external-resource conservation')
    return (1-share)*p


def scenario_certificate(a,raw,got):
    i,n,s=quantities(raw['institution']),quantities(raw['network']),quantities(got['scenario'])
    P0=i['bond_face']/(1+i['base_yield'])**i['bond_years']
    Q0=i['loan_face']/(1+i['base_yield'])
    N0=(1-n['interbank_share'])*n['obligation']
    E0=i['cash']+P0+Q0+N0-i['deposits']-i['secured_old']
    discount=1/(1+s['yield'])
    P=i['bond_face']
    for unused in range(i['bond_years']): P*=discount
    recovery=i['loan_face']*(1-s['loan_loss_fraction'])
    Q=recovery*discount
    N=network_certificate(a,n,s,got['network'])
    losses=dict(bond=P0-P,loan=Q0-Q,network=N0-N,operating=s['operating_cash_loss'])
    loss=sum(losses.values(),F(0));E=E0-loss
    a.eq(got['loss_components'],losses,'single joint mark for each contract')
    a.eq((got['total_loss'],got['equity'],got['capital_slack']),(loss,E,E-i['equity_floor']),
         'income and capital bridge')
    oldcap=(1-s['haircut'])*i['pledged_fraction']*P
    freecap=(1-s['haircut'])*(1-i['pledged_fraction'])*P
    M=max(F(0),i['secured_old']-oldcap)
    cap=min(s['facility_limit'],freecap)
    A=i['cash']-s['operating_cash_loss']+N
    required=max(F(0),M+s['withdrawal']+i['cash_floor']-A)
    draw=min(required,cap)
    paidM=min(A+draw,M);paidW=min(A+draw-paidM,s['withdrawal'])
    cash=A+draw-paidM-paidW
    budget=A+cap-M-s['withdrawal']
    a.eq(got['funding'],dict(margin_required=M,margin_paid=paidM,margin_unpaid=M-paidM,
        facility_capacity=cap,draw_to_meet_cash_floor=required,actual_draw=draw,
        cash_capacity_after_full_payments=budget,withdrawal_requested=s['withdrawal'],
        withdrawal_paid=paidW,withdrawal_unpaid=s['withdrawal']-paidW,closing_cash=cash,
        all_payments_met=paidM==M and paidW==s['withdrawal'],
        reserve_trigger=budget<=i['cash_floor'],capital_trigger=E<=i['equity_floor']),
        'funded priority and signed full-payment certificate')
    a.eq(got['funding_slack'],budget-i['cash_floor'],'capacity rather than chosen cash')
    fractions=got['collateral']
    new=draw/((1-s['haircut'])*P)
    a.eq(fractions,dict(original_fraction_reserved=i['pledged_fraction'],new_fraction_pledged=new,
        fraction_remaining_free=1-i['pledged_fraction']-new,original_pool_capacity=oldcap),
        'disjoint collateral pools')
    a.eq(0<=new<=1-i['pledged_fraction'],True,'no duplicated security units')
    markE=E+s['operating_cash_loss'];C=i['cash'];D=i['deposits'];B=i['secured_old']
    # Independent closed-form account vectors, not the model's posting helper.
    expected=[(C,P0,Q0,N0,D,B,F(0),E0),(C,P,Q,N,D,B,F(0),markE),
        (C-s['operating_cash_loss'],P,Q,N,D,B,F(0),E),
        (A,P,Q,F(0),D,B,F(0),E),(A+draw,P,Q,F(0),D,B,draw,E),
        (A+draw-paidM,P,Q,F(0),D,B-paidM,draw,E),
        (cash,P,Q,F(0),D-paidW,B-paidM,draw,E)]
    keys=('cash','bond','loan','network_claim','deposits','secured_old','secured_new','equity')
    events=('opening','joint_asset_marks','cash_incident','network_batch_settles',
            'new_secured_funding','old_secured_principal_paydown','deposit_payment')
    a.eq(len(got['ledger']),7,'seven exact dated stages')
    for row,values,event in zip(got['ledger'],expected,events):
        a.eq([row[k] for k in keys],values,'all accounts at '+event)
        a.eq(row['event'],event,'dated event order')
        a.eq((row['assets'],row['accounting_residual']),(sum(values[:4]),F(0)),'asset/resource certificate')
        a.eq(sum(values[:4]),sum(values[4:]),'independent capital balances each journal')
        a.eq(values[0]>=0,True,'no fictitious negative-cash execution')
        a.journal_rows+=1
    principal=B-paidM+draw
    a.eq(got['later_cash'],dict(next_day_secured_principal=principal,
        next_day_secured_interest=principal*i['secured_daily_rate'],
        next_day_secured_total=principal*(1+i['secured_daily_rate']),year_one_loan_receipt=recovery,
        bond_maturity_year=i['bond_years'],bond_maturity_receipt=i['bond_face']),
        'dated principal, interest and later asset receipts')


def path_slacks(data,x):
    """Independent scalar oracle for baseline-family financial transfers.

    The analytic network pieces below follow from hand-solved resource thresholds;
    this oracle is deliberately not advertised for arbitrary altered networks.
    """
    i=quantities(data['institution'])
    z=F(21,20)+x/10
    P=F(441,4)/(z*z);Q=84*(1-x/5)/z
    receipt=F(10) if x<=F(1,5) else 11-5*x if x<=F(1,3) else 12-8*x
    E0=i['cash']+190-i['deposits']-20
    E=E0+P-100+Q-80+receipt-10-2*x
    oldpay=20-(F(4,5)-3*x/10)*P/4
    available=i['cash']-2*x+receipt
    cap=min(i['facility_limit'],(F(4,5)-3*x/10)*P*F(3,4))
    return E-i['equity_floor'],available+cap-oldpay-(20+20*x)-i['cash_floor']


def reverse_certificates(a,data,got,polynomials=False):
    steps=data['reverse']['bisections']
    for name,bound in got.items():
        choose=lambda x: min(path_slacks(data,x)) if name=='first' else path_slacks(data,x)[0 if name=='capital_slack' else 1]
        if bound['status']=='boundary_bracketed':
            lo,hi=F(bound['lower']),F(bound['upper'])
            a.eq((F(bound['lower_slack']),F(bound['upper_slack'])),(choose(lo),choose(hi)),
                 'independent scalar endpoint certificate')
            a.eq(choose(lo)>0 and choose(hi)<=0,True,'safe and triggering endpoints')
            a.eq((hi-lo,F(bound['width'])),(F(1,2**steps),F(1,2**steps)),'exact bisection width')
            if polynomials:
                # Independently derived cubics, evaluated exactly at the reported bracket.
                def polynomial(x):
                    z=F(21,20)+x/10
                    return (F(441,4)+84*(1-x/5)*z-(143+10*x)*z*z) if name=='capital_slack' else \
                        (2-30*x)*z*z+F(441,4)*(F(1,5)-3*x/40)
                a.eq(lo>=F(1,3),True,'root is in derived polynomial regime')
                a.eq(polynomial(lo)>0 and polynomial(hi)<=0,True,'separate polynomial sign oracle')
        elif bound['status']=='triggered_at_reference':
            a.eq((bound['lower'],bound['upper']),('0','0'),'already-triggered reference')
            a.eq(choose(F(0))<=0,True,'reference really triggers')
        elif bound['status']=='no_trigger_in_supported_interval':
            a.eq((bound['lower'],bound['upper'],bound['width']),(None,None,None),'absent boundary is null')
            a.eq(choose(F(1))>0,True,'endpoint remains safe')
        else: raise ValueError('unknown reverse status')


def printed_fractions(a):
    """Bind every reported nontrivial exact numerical result to fresh arithmetic.

    These explicit printed anchors complement whole-model journal checks; a correct
    saved output alone cannot catch a manually mistyped manuscript fraction.
    """
    html=(ROOT/'content/chapters/v11-c07.html').read_text()
    P=F(441,4)/F(23,20)**2
    Q=F(84)/F(23,20)
    loan_joint=F(84)*F(4,5)/F(23,20)
    margin=20-P/8
    paid=34-margin
    larger=F(3,8)*P
    larger_paid=14+larger-margin
    maxima=(100-P)+(80-F(84)*F(3,5)/F(51,50))+6+2
    joint=100-P+80-loan_joint+6+2
    certificates={
        '45/101':F(90,202), '44100/529':P, '8800/529':100-P,
        '1680/23':Q, '12480/529':100-P+80-Q,
        '4000/21':F(441,2)/F(21,20)**3, '400/21':F(441,2)/F(21,20)**3/10,
        '1344/23':loan_joint, '496/23':80-loan_joint, '160/23':80-Q,
        '336/23':Q/5, '528/23':80-Q+16, '32/23':16-Q/5,
        '28/3':(F(4)+F(6,2))/F(3,4), '32/3':(F(6)+F(4,2))/F(3,4),
        '14/3':(F(4)+F(6,2))/F(3,4)/2,
        '16/3':10-(F(4)+F(6,2))/F(3,4)/2,
        '7/3':7-(F(4)+F(6,2))/F(3,4)/2,
        '10135/1058':margin, '25837/1058':paid, '16483/1058':40-paid,
        '119109/1058':137-paid, '11025/1058':20-margin,
        '75012/529':P+loan_joint, '635/529':joint-45,
        '33075/1058':larger, '18876/529':larger_paid, '2284/529':40-larger_paid,
        '1058/2205':20/(P/2), '520/17':80-F(84)*F(3,5)/F(51,50),
        '496624/8993':maxima, '24440/529':joint, '3528/391':maxima-joint}
    for printed,computed in certificates.items():
        a.eq(F(printed),computed,'independent printed fraction '+printed)
        a.eq(printed in html,True,'manuscript retains verified fraction '+printed)
    for incorrect in ('12919/529','8241/529','59554/529','529/1102'):
        a.eq(incorrect in html,False,'resolved exact-fraction typo absent')
    readme=(PROJECT/'v11-c07-README.txt').read_text()
    a.eq('16483/1058' in readme and '8241/529' not in readme,True,'README exact unpaid amount')


class Structure(HTMLParser):
    def __init__(self):
        super().__init__();self.worked=0;self.ex=False;self.sol=False;self.prompts=0;self.answers=0;self.ids=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        x=dict(attrs);classes=x.get('class','').split()
        if 'id' in x:self.ids.append(x['id'])
        if tag=='aside' and 'worked' in classes:self.worked+=1
        if tag=='ol' and 'exercises' in classes:self.ex=True
        if tag=='details' and 'solutions' in classes:self.sol=True
        if tag=='li':self.prompts+=self.ex;self.answers+=self.sol
        if tag=='a':self.links.append(x.get('href'))
    def handle_endtag(self,tag):
        if tag=='ol':self.ex=False
        if tag=='details':self.sol=False


def check(require_bindings=True):
    a=Audit();prior_bytecode=sys.dont_write_bytecode;sys.dont_write_bytecode=True
    try:
        log=StringIO()
        with redirect_stdout(log),redirect_stderr(log):candidate=runpy.run_path(str(MODEL))['run']
        a.eq(log.getvalue(),'','quiet import')
        data=json.loads((PROJECT/'v11-c07-inputs.json').read_text())
        def evaluate(raw):
            old=deepcopy(raw);quiet=StringIO()
            with redirect_stdout(quiet),redirect_stderr(quiet):result=candidate(raw)
            a.eq(raw,old,'nonmutating public API');a.eq(quiet.getvalue(),'','quiet public API')
            json.dumps(result,allow_nan=False)
            return result
        result=evaluate(data)
        a.eq(result,json.loads((PROJECT/'v11-c07-output.json').read_text()),'entire saved output')
        a.eq(result['opening'],dict(bond=F(100),loan=F(80),network_claim=F(10),assets=F(202),equity=F(45)),
             'independent opening balance sheet')
        for case in result['scenarios']:scenario_certificate(a,data,case)
        printed_fractions(a)
        reverse_certificates(a,data,result['reverse'],True)
        a.eq(result['aggregation'],dict(component_maxima=dict(bond=F(8800,529),loan=F(520,17),network=F(6),operating=F(2)),
            sum_component_maxima=F(496624,8993),largest_common_scenario_loss=F(24440,529),
            overstatement=F(3528,391),maximizing_scenarios=['joint']),'finite-menu extrema and incompatibility gap')

        def vary(updates, row_updates=None, reverse_check=False):
            raw=deepcopy(data)
            for section,changes in updates.items():raw[section].update(changes)
            if row_updates:
                for index,changes in row_updates.items():raw['scenarios'][index].update(changes)
            got=evaluate(raw)
            for index in (row_updates if row_updates else [3]):scenario_certificate(a,raw,got['scenarios'][index])
            if reverse_check:reverse_certificates(a,raw,got['reverse'])
            a.interventions+=1
            return got
        transferred=vary({}, {2:{'external_b':'4','external_c':'6'}})
        net=transferred['scenarios'][2]['network']
        a.eq((net['payment_b'],net['payment_c'],net['institution_receipt'],net['feedback_loss']),
             (F(28,3),F(32,3),F(14,3),F(7,3)),'exercise2 independently solved network')
        expanded=vary({'institution':{'facility_limit':'40'}},{3:{'facility_limit':'40'}},True)
        a.eq(expanded['scenarios'][3]['funding']['withdrawal_unpaid'],F(2284,529),'exercise3 collateral-limited larger line')
        for changes in ({'cash':'17'},{'cash':'17','deposits':'142'},{'cash_floor':'0'},
                        {'equity_floor':'45'},{'cash':'100'},{'cash_floor':'100'}):
            vary({'institution':changes},reverse_check=True)
        vary({'network':{'interbank_share':'0','external_b':'20','external_c':'20'}})
        vary({'network':{'interbank_share':'3/4'}})
        vary({'institution':{'pledged_fraction':'1/2'}})
        vary({}, {3:{'external_b':'0','external_c':'0','loan_loss_fraction':'1'}})
        vary({}, {3:{'external_b':'0','external_c':'0','operating_cash_loss':'12','facility_limit':'0'}})
        vary({}, {1:{'yield':'-1/2','haircut':'0','facility_limit':'0','withdrawal':'0'}})
        vary({'institution':{'secured_old':'0','pledged_fraction':'0'}})
        a.eq(F(400,21)-F(8800,529),F(26800,11109),'exercise1 convexity approximation gap')
        a.eq(F(160,23)+F(336,23),F(496,23),'exercise1 exact joint loan attribution')
        a.eq(F(160,23)+16-F(496,23),F(32,23),'exercise1 stale-denominator attribution error')
        a.eq(F(90,202),F(45,101),'exercise5 common-sector concentration')
        # At the unsupported a=1 boundary, distinct fixed points prove nonuniqueness.
        a.eq(all(p==min(20,p) for p in (0,7,20)),True,'exercise2 closed-cycle counterexample')

        def reject(raw,label):
            old=deepcopy(raw);quiet=StringIO()
            try:
                with redirect_stdout(quiet),redirect_stderr(quiet):candidate(raw)
            except ValueError:a.rejections+=1
            else:raise ValueError('accepted invalid input: '+label)
            a.eq(raw,old,'invalid input unchanged');a.eq(quiet.getvalue(),'','invalid API quiet')
        for raw in (None,[],True,{},dict(data,extra=1)):reject(raw,'root')
        for value in (True,12,12.0,None,'1e1','+1','01',' 1','1/0','1/-2','NaN','1'*33,'1/1000000001','-1'):
            raw=deepcopy(data);raw['institution']['cash']=value;reject(raw,'rational syntax')
        bads=[('institution',{'bond_years':True}),('institution',{'bond_years':6}),
            ('institution',{'bond_face':'0'}),('institution',{'base_yield':'3/4'}),
            ('institution',{'deposits':'300'}),('institution',{'secured_old':'21'}),
            ('institution',{'secured_daily_rate':'1/10'}),('network',{'obligation':'0'}),
            ('network',{'interbank_share':'1'}),('network',{'external_b':'9'}),
            ('reference',{'haircut':'1'}),('reference',{'withdrawal':'138'}),
            ('reverse',{'bisections':True}),('reverse',{'bisections':49}),
            ('reverse',{'yield_increase':'1'}),('reverse',{'loan_loss_increase':'2'}),
            ('reverse',{'b_resource_drop':'13'}),('reverse',{'haircut_increase':'1'}),
            ('reverse',{'withdrawal_increase':'200'}),('reverse',{'operating_loss_increase':'13'})]
        for section,changes in bads:
            raw=deepcopy(data);raw[section].update(changes);reject(raw,section)
        for changes in ({'id':'Reference'}, {'yield':'-1'}, {'loan_loss_fraction':'2'},
                        {'haircut':'1'}, {'withdrawal':'138'}, {'operating_cash_loss':'13'},
                        {'facility_limit':'21'}, {'unexpected':'0'}):
            raw=deepcopy(data);raw['scenarios'][0].update(changes);reject(raw,'scenario')
        for rows in ([],[deepcopy(data['scenarios'][0])]*9,data['scenarios']+[data['scenarios'][0]]):
            raw=deepcopy(data);raw['scenarios']=rows;reject(raw,'scenario count/id')
        for section in ('institution','network','reference','reverse'):
            raw=deepcopy(data);del raw[section][next(iter(raw[section]))];reject(raw,'exact keys')
        raw=deepcopy(data);raw['schema']='future';reject(raw,'schema')
        portable_runs,cli_rejections=portable(a,result)
        structure=Structure();structure.feed((ROOT/'content/chapters/v11-c07.html').read_text())
        a.eq((structure.worked,structure.prompts,structure.answers),(4,8,8),'complete worked and solved structure')
        a.eq(len(structure.ids),len(set(structure.ids)),'unique chapter ids')
        for suffix in ('inputs.json','analysis.py','output.json','manifest.json','README.txt'):
            a.eq('v11-c07-'+suffix in structure.links,True,'flat asset link')
        a.eq('<code>python3 v11-c07-analysis.py --input v11-c07-inputs.json --output result.json</code>' in
             (ROOT/'content/chapters/v11-c07.html').read_text(),True,'reader command retains executable spacing')
        if require_bindings:bindings(a)
        return dict(chapter='v11-c07',status='passed',comparisons=a.comparisons,
            financial_interventions=a.interventions,invalid_api_inputs=a.rejections,
            journal_rows=a.journal_rows,portable_runs=portable_runs,cli_rejections=cli_rejections,
            bound_author_payloads=8 if require_bindings else 0)
    finally:sys.dont_write_bytecode=prior_bytecode


def portable(a,expected):
    runs=0;rejections=0
    with tempfile.TemporaryDirectory(prefix='c07-check-') as td:
        root=Path(td);lab=root/'lab';lab.mkdir()
        for end in ('analysis.py','inputs.json','output.json','README.txt','manifest.json'):
            shutil.copyfile(PROJECT/('v11-c07-'+end),lab/('v11-c07-'+end))
        script=lab/MODEL.name;inputfile=lab/'v11-c07-inputs.json'
        aliases=[inputfile,script]
        for protected in (inputfile,script):
            symbolic=root/(protected.name+'.symlink');symbolic.symlink_to(protected)
            hard=root/(protected.name+'.hard');os.link(protected,hard);aliases.extend((symbolic,hard))
        api="""import contextlib,copy,io,json,runpy,sys
sys.dont_write_bytecode=True
capture=io.StringIO()
with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
    run=runpy.run_path(sys.argv[1])['run'];data=json.load(open(sys.argv[2]));old=copy.deepcopy(data);result=run(data)
if capture.getvalue() or data!=old:raise RuntimeError('quiet/nonmutation failure')
print(json.dumps(result,sort_keys=True,allow_nan=False))
"""
        for optimize in (False,True):
            python=[sys.executable]+(['-O'] if optimize else [])
            proc=subprocess.run(python+['-c',api,str(script),str(inputfile)],cwd=root,capture_output=True,timeout=20)
            a.eq((proc.returncode,proc.stderr),(0,b''),'portable public API')
            a.eq(json.loads(proc.stdout),expected,'portable exact API result');runs+=1
            for default in (False,True):
                target=lab/'v11-c07-output.json' if default else root/'result.json'
                args=[] if default else ['--input',str(inputfile),'--output',str(target)]
                proc=subprocess.run(python+[str(script)]+args,cwd=root,capture_output=True,timeout=20)
                a.eq((proc.returncode,proc.stdout,proc.stderr),(0,b'',b''),'portable quiet CLI')
                a.eq(target.read_bytes(),(PROJECT/'v11-c07-output.json').read_bytes(),'exact CLI bytes');runs+=1
            text=inputfile.read_text()
            for raw in (text.replace('"schema":','"schema":"duplicate","schema":',1),
                        text.replace('"cash": "12"','"cash": NaN'),
                        text.replace('"cash": "12"','"cash": true'),' '*65537):
                bad=root/'bad.json';bad.write_text(raw);target=root/'preserve.json';target.write_bytes(b'old\n')
                proc=subprocess.run(python+[str(script),'--input',str(bad),'--output',str(target)],cwd=root,capture_output=True,timeout=20)
                a.eq((proc.returncode,proc.stdout,bool(proc.stderr)),(2,b'',True),'strict JSON CLI rejection')
                a.eq(target.read_bytes(),b'old\n','rejection preserves previous output');rejections+=1
            for target in aliases:
                saved=(script.read_bytes(),inputfile.read_bytes())
                proc=subprocess.run(python+[str(script),'--input',str(inputfile),'--output',str(target)],cwd=root,capture_output=True,timeout=20)
                a.eq((proc.returncode,proc.stdout,bool(proc.stderr)),(2,b'',True),'protected output identity')
                a.eq((script.read_bytes(),inputfile.read_bytes()),saved,'direct/symbolic/hard aliases preserve bytes');rejections+=1
    return runs,rejections


def bindings(a):
    files=['content/chapters/v11-c07.html']+['content/projects/v11-c07-'+end for end in
        ('inputs.json','analysis.py','output.json','manifest.json','README.txt')]+[
        'scripts/check_v11_c07.py','content/reviews/v11-c07-sources.json']
    author=json.loads((ROOT/'content/reviews/v11-c07-author.json').read_text())
    a.eq([r['path'] for r in author['reviewed_hashes']],files,'eight nonself author payloads')
    for row in author['reviewed_hashes']:
        raw=(ROOT/row['path']).read_bytes()
        a.eq((len(raw),sha256(raw).hexdigest()),(row['bytes'],row['sha256']),'author frozen hash '+row['path'])
    manifest=json.loads((PROJECT/'v11-c07-manifest.json').read_text())
    a.eq([r['file'] for r in manifest['files']],['v11-c07-'+s for s in ('inputs.json','analysis.py','output.json','README.txt')],
         'four portable manifest members')
    for row in manifest['files']:
        raw=(PROJECT/row['file']).read_bytes()
        a.eq((len(raw),sha256(raw).hexdigest()),(row['bytes'],row['sha256']),'portable manifest hash')


if __name__=='__main__':
    print(json.dumps(check(),sort_keys=True,allow_nan=False))
