"""Independent combinatorial, covariance and resource audits for V11-C08."""
import contextlib
import copy
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'content/projects'
MODEL=PROJECT/'v11-c08-analysis.py'
COUNT=0


def need(ok,label):
    global COUNT
    COUNT+=1
    if not ok: raise RuntimeError(label)


def eq(a,b,label): need(a==b,label+': '+repr(a)+' != '+repr(b))
def near(a,b,label,tol=1e-10): need(math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol),label)


def audit(data,out):
    """Use direct count probabilities, covariance and conservation certificates.

    No implementation helper is called. Pension validation uses discounted
    wealth rather than independently copying its sale algorithm.
    """
    ins=data['insurance']; w,l=F(ins['wealth']),F(ins['loss'])
    offers=[{'id':'uninsured','premium':'0','indemnity':'0'}]+ins['contracts']
    poolp=sum(F(t['share'])*F(t['probability']) for t in ins['types'])
    for t,row in zip(ins['types'],out['insurance']['types']):
        p=F(t['probability']); u=(1-float(p))*math.sqrt(w)+float(p)*math.sqrt(w-l)
        near(row['no_insurance_utility_approx'],u,'independent expected utility')
        riskpremium=p*(1-p)*F(str((math.sqrt(w)-math.sqrt(w-l))**2))
        near(row['full_insurance_max_premium_approx'],float(p*l+riskpremium),'expanded risk premium')
        for offer,answer in zip(offers,row['offers']):
            premium,indemnity=F(offer['premium']),F(offer['indemnity'])
            eu=(1-float(p))*math.sqrt(w-premium)+float(p)*math.sqrt(w-premium-l+indemnity)
            near(answer['expected_utility_approx'],eu,'statewise menu utility')
            eq(F(answer['premium_minus_expected_claim']),premium-p*indemnity,'conditional underwriting margin')
    eq(F(out['insurance']['pooled_full_premium']),poolp*l,'original population premium')

    pool=data['pool']; n=pool['members']; b=F(pool['benefit']); r=n*F(pool['premium'])+F(pool['capital'])
    regs=[(F(z['weight']),F(z['claim_probability'])) for z in pool['regimes']]
    p=sum(a*q for a,q in regs)
    for name,law in [('independent',[(F(1),p)]),('common_regime',regs)]:
        masses=[sum(a*math.comb(n,k)*q**k*(1-q)**(n-k) for a,q in law) for k in range(n+1)]
        eq(sum(masses),1,'combinatorial law normalized')
        eq(sum(k*m for k,m in enumerate(masses)),n*p,'marginal count conserved')
        report=out['pool']['laws'][name]
        eq(F(report['shortfall_probability']),sum(m for k,m in enumerate(masses) if k*b>r),'strict resource tail by direct probabilities')
        unpaid=sum(m*(k*b-r) for k,m in enumerate(masses) if k*b>r)
        eq(F(report['expected_unpaid_claims']),unpaid,'positive claims deficit by direct sums')
        residual=sum(m*max(r-k*b,0) for k,m in enumerate(masses))
        eq(residual-unpaid,r-n*b*p,'signed expected resource reconciliation')
        within=sum(a*q*(1-q) for a,q in law); between=sum(a*(q-p)**2 for a,q in law)
        eq(F(report['variance_average_claim']),b*b*(within/n+between),'conditional variance certificate')

    ann=data['annuity']; n=ann['members']; d=list(map(F,ann['discounts'])); benefit=F(ann['benefit']); s=list(map(F,ann['survival']))
    coeff=[df*benefit for df in d]
    def covariance_moments(surv):
        mean=sum(a*q for a,q in zip(coeff,surv))
        variance=sum(a*c*(surv[max(i,j)]-surv[i]*surv[j]) for i,a in enumerate(coeff) for j,c in enumerate(coeff))
        return mean,variance
    mu,var=covariance_moments(s)
    eq(F(out['annuity']['mean_per_life']),mu,'annuity linear expectation')
    eq(F(out['annuity']['variance_per_life']),var,'nested covariance double sum')
    eq(F(out['annuity']['iid_variance_total']),n*var,'independent total variance')
    eq(F(out['annuity']['iid_variance_average']),var/n,'independent average variance')
    law=out['annuity']['single_life_states']
    eq(sum(F(row['probability']) for row in law),1,'disjoint lifetime mass')
    for t in range(len(s)):
        eq(sum(F(row['probability']) for row in law if row['payments_received']>t),s[t],'lifetime law reconstructs survival')
    within=between=F(0)
    for r,row in zip(ann['regimes'],out['annuity']['regimes']):
        mean,variance=covariance_moments(list(map(F,r['survival'])))
        eq((F(row['mean']),F(row['variance'])),(mean,variance),'regime covariance moments')
        within+=F(r['weight'])*variance; between+=F(r['weight'])*(mean-mu)**2
    eq(F(out['annuity']['common_regime_variance_average']),within/n+between,'total conditional variance')
    eq(within+between,var,'same one-person marginal law')
    eq(F(out['annuity']['stress_mean_per_life']),sum(a*F(q) for a,q in zip(coeff,ann['stress_survival'])),'longevity stress expectation')
    death=sum(df*(a-z) for df,a,z in zip(d,[F(1)]+s[:-1],s))*F(ann['death_benefit'])
    eq(F(out['annuity']['temporary_death_benefit_pv']),death,'end-year death timing')

    fund=data['pension']; faces=list(map(F,fund['zero_faces'])); initial=F(fund['money_account'])+sum(df*face for df,face in zip(d,faces))
    expected=[n*benefit*q for q in s]; liability=sum(df*c for df,c in zip(d,expected))
    eq((F(out['pension']['initial_asset_pv']),F(out['pension']['expected_liability_pv'])),(initial,liability),'asset liability basis')
    for path,result in zip(fund['paths'],out['pension']['paths']):
        cost=sum(df*k*benefit for df,k in zip(d,path['survivors'])); extra=max(cost-initial,0)
        eq(F(result['minimum_extra_initial_cash_with_stated_markets']),extra,'PV lower bound on support')
        for key,x in [('without_support',F(0)),('with_minimum_extra_cash',extra)]:
            report=result[key]; previous_faces=faces.copy(); old_cash=F(fund['money_account'])+x; previous_d=F(1); cumulative_paid=F(0)
            for row in report['rows']:
                t=row['date']-1; closing=list(map(F,row['remaining_faces'])); paid=F(row['paid']); due=benefit*path['survivors'][t]
                eq(F(row['matured_face']),previous_faces[t],'only retained face matures')
                eq(F(row['opening_cash']),old_cash,'cash carried once')
                eq(F(row['accrued_cash']),old_cash*previous_d/d[t],'money-account return')
                cash=old_cash*previous_d/d[t]+previous_faces[t]
                sales=row['sales']; maturities=[sale['maturity'] for sale in sales]
                eq(maturities,sorted(maturities,reverse=True),'declared latest-face sale order')
                sold_by_date={}
                for sale in sales:
                    j=sale['maturity']-1; sold=F(sale['face_sold']); receipt=F(sale['receipt'])
                    need(j>t and 0<sold<=previous_faces[j],'positive future sale within inventory')
                    eq(receipt*d[t],sold*d[j],'sale preserves discounted wealth')
                    eq(F(sale['price_per_face']),d[j]/d[t],'executable date-specific quote')
                    sold_by_date[j]=sold; cash+=receipt
                for j,value in enumerate(closing):
                    eq(value,F(0) if j<=t else previous_faces[j]-sold_by_date.get(j,0),'closing zero inventory')
                eq((F(row['due']),F(row['unpaid'])),(due,due-paid),'benefit and arrears identity')
                need(0<=paid<=due,'cannot overpay or negative pay')
                eq(F(row['closing_cash']),cash-paid,'actual cash conservation')
                need(F(row['closing_cash'])>=0,'no implicit borrowing')
                if paid<due:
                    eq(cash,paid,'all accessible cash used on failure')
                    eq(sum(closing),0,'no unsold accessible resources at failure')
                    eq(report['first_unpaid_date'],t+1,'first failure recorded')
                    eq(len(report['rows']),t+1,'path stops at failure')
                cumulative_paid+=paid*d[t]
                current_wealth=F(row['closing_cash'])*d[t]+sum(df*value for df,value in zip(d,closing))
                eq(current_wealth+cumulative_paid,initial+x,'global discounted resource certificate')
                previous_faces=closing; old_cash=F(row['closing_cash']); previous_d=d[t]
            eq(report['all_payments_met'],report['first_unpaid_date'] is None,'failure flag consistency')
            if report['all_payments_met']:
                eq(F(report['terminal_cash'])*d[-1],initial+x-cost,'terminal PV residual')
            else: eq(report['terminal_cash'],None,'no fabricated terminal cash after failure')
        need(result['with_minimum_extra_cash']['all_payments_met'],'sufficiency of explicit minimum support')
    shift=float(F(fund['parallel_continuous_rate_shift']))
    changed=[float(df)*math.exp(-(t+1)*shift) for t,df in enumerate(d)]
    surplus=float(F(fund['money_account']))+sum(df*float(a-l) for df,a,l in zip(changed,faces,expected))
    near(out['pension']['shifted_surplus_approx'],surplus,'single surplus cash vector repricing')
    eq(F(out['pension']['surplus_derivative_per_unit_parallel_continuous_rate']),sum((t+1)*df*(l-a) for t,(df,l,a) in enumerate(zip(d,expected,faces))),'parallel derivative units')

    g=data['guarantee']; promised=F(g['promised_benefit']); totals={k:F(0) for k in out['guarantee']['expectations']}
    for state,row in zip(g['states'],out['guarantee']['states']):
        assets=F(state['assets']); p=F(state['probability']); sp=F(row['actual_sponsor_payment']); gp=F(row['guarantor_payment']); paid=F(row['participant_payment'])
        eq(paid,min(promised,assets+F(state['sponsor_capacity'])+F(state['guarantor_capacity'])),'maximum feasible benefit with priority resources')
        need(0<=sp<=F(state['sponsor_capacity']) and 0<=gp<=F(state['guarantor_capacity']),'support capacity')
        eq(sp,min(F(state['sponsor_capacity']),max(promised-assets,0)),'sponsor priority')
        eq(assets+sp+gp,paid+F(row['residual_assets']),'statewise guarantee conservation')
        eq(F(row['participant_shortfall']),promised-paid,'participant shortfall')
        for k in totals: totals[k]+=p*F(row[k])
    for key,value in totals.items(): eq(F(out['guarantee']['expectations'][key]),value,'physical expectation '+key)

    h=data['household']
    for loan,result in zip(h['loans'],out['household']['loans']):
        principals=list(map(F,loan['principal_payments'])); interests=[F(loan['rate'])*(F(h['debt'])-sum(principals[:t])) for t in range(len(principals))]
        balances=[F(h['initial_liquid'])]
        for t,row in enumerate(result['rows']):
            cash=F(h['initial_liquid'])+sum(F(h['income'][j])-F(h['consumption'][j])-F(h['contributions'][j])-principals[j]-interests[j] for j in range(t+1))
            returns=list(map(F,h['pension_gross_returns']))
            account=F(h['initial_pension'])*math.prod(returns[:t+1])+sum(F(h['contributions'][j])*math.prod(returns[j+1:t+1]) for j in range(t+1))
            eq(F(row['projected_liquid']),cash,'closed prefix cash')
            eq(F(row['pension_account']),account,'contribution vintage accumulation')
            eq(F(row['debt_service']),principals[t]+interests[t],'opening-principal debt service')
            eq(F(row['remaining_debt']),F(h['debt'])-sum(principals[:t+1]),'remaining principal')
            balances.append(cash)
        eq(F(result['total_interest']),sum(interests),'total interest not coupon alone')
        eq(F(result['minimum_extra_initial_cash_for_floor']),max(F(h['liquid_floor'])-min(balances),0),'fixed-plan minimum theorem')
        eq(result['first_negative_cash'],next((t for t,x in enumerate(balances) if x<0),None),'first payment resource failure')
        eq(result['first_floor_breach'],next((t for t,x in enumerate(balances) if x<F(h['liquid_floor'])),None),'first reserve-floor breach')


class Chapter(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.worked=0; self.pairs=[]; self.sources=set(); self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'worked' in a.get('class','').split():self.worked+=1
        if 'data-solution-for' in a:self.pairs.append(a['data-solution-for'])
        if 'data-source' in a:self.sources.add(a['data-source'])
        if 'href' in a:self.links.append(a['href'])


def exercise_anchors():
    eq(F(144)-(F(3,4)*12+F(1,4)*8)**2,23,'exercise1 max premium')
    eq(F(23)-F(1,4)*80,3,'exercise1 risk premium')
    high=lambda a:.6*math.sqrt(100-.1*a)+.4*math.sqrt(36+.9*a)
    need(high(8)<math.sqrt(74.4)<high(10),'menu crosses with increased coverage')
    need(high(8.8461934)<math.sqrt(74.4)<high(8.8461935),'unique IC boundary numerical bracket')
    near(high(10),8.65320619432617,'exercise2 rounded utility',1e-8)
    eq(F(1)-F('.4')*10,-3,'exercise2 adverse-selection margin')
    eq(64**2*F('.1875')/400,F('1.92'),'exercise3 iid variance')
    eq(64**2*(F('.165')/400+F('.0225')),F('93.8496'),'exercise3 common variance')
    eq(F(6,16)*4+F(1,16)*14,F(19,8),'exercise4 iid unpaid')
    eq(F(1,4)*4+F(1,8)*14,F(11,4),'exercise4 common unpaid')
    eq(F('.3')*F('9.5')+F('.5')*F('18.5'),F('12.1'),'exercise5 mean')
    eq(F('9.5')**2*F('.16')+9**2*F('.25')+2*F('9.5')*9*F('.1'),F('51.79'),'exercise5 covariance')
    eq(50*(F('.95')*F('.2')+F('.9')*F('.3')),23,'exercise5 death value')
    eq(F('332.1008')/1000+F('29.5936'),F('29.9257008'),'exercise6 common average')
    eq(1000*(F('47.08')-F('41.64')),5440,'exercise6 mean liability change')
    eq(F('.96')*(1800-1000)-200,568,'exercise7 no-sale initial requirement')
    eq(F('.25')*85+F('.75')*100,F('96.25'),'exercise8 guaranteed expected payment')
    eq(F('1.2')-2,F('-.8'),'exercise9 amortizing income shock')
    eq(F('.24')-2,F('-1.76'),'exercise9 bullet income shock')
    eq(((30*F('1.04')+2)*F('.9')+3)*F('1.1')+3,F('39.168'),'exercise9 contribution vintage')
    eq(20*(F('.96')*F('.8')+F('.92')*F('.6')+F('.88')*F('.4')),F('33.44'),'retention annuity')


def check():
    global COUNT
    COUNT=0
    spec=importlib.util.spec_from_file_location('v11_c08_model',MODEL); model=importlib.util.module_from_spec(spec)
    buffer=io.StringIO()
    with contextlib.redirect_stdout(buffer),contextlib.redirect_stderr(buffer): spec.loader.exec_module(model)
    eq(buffer.getvalue(),'','quiet import')
    data=json.loads((PROJECT/'v11-c08-inputs.json').read_text()); original=copy.deepcopy(data)
    with contextlib.redirect_stdout(buffer),contextlib.redirect_stderr(buffer): out=model.run(data)
    eq(buffer.getvalue(),'','quiet API'); eq(data,original,'nonmutating API')
    eq(out,json.loads((PROJECT/'v11-c08-output.json').read_text()),'reference output current')
    audit(data,out); exercise_anchors()
    eq([t['maximizing_contracts_approx'] for t in out['insurance']['types']],[['partial'],['full']],'strict baseline menu incentives')
    eq(out['insurance']['margin_per_selected_policy'],'-48/5','pool selection destroys average margin')
    eq(F(out['annuity']['variance_per_life']),F('361.6944'),'annuity anchor')
    eq(F(out['pension']['paths'][1]['without_support']['rows'][-1]['unpaid']),F(5100,11),'longer-life unpaid benefit')
    eq(F(out['pension']['paths'][0]['without_support']['terminal_cash']),F(1700,11),'baseline discounted surplus')
    eq(F(out['guarantee']['expectations']['participant_shortfall']),F('8.75'),'limited sponsor shortfall')

    variants=[]
    def variant(label,mutate):
        d=copy.deepcopy(data); mutate(d); result=model.run(d); audit(d,result); variants.append(label); return result
    for capital,tail in [('200',.06934888914174188),('600',.002746143631693212)]:
        r=variant('capital '+capital,lambda d,k=capital:d['pool'].__setitem__('capital',k))
        near(F(r['pool']['laws']['independent']['shortfall_probability']),tail,'published capital table')
    r=variant('small tail law',lambda d:d.__setitem__('pool',{'members':2,'benefit':'10','premium':'3','capital':'0','regimes':[{'id':'none','weight':'0.5','claim_probability':'0'},{'id':'half','weight':'0.5','claim_probability':'0.5'}]}))
    eq([F(r['pool']['laws'][law]['expected_unpaid_claims']) for law in ['independent','common_regime']],[F(19,8),F(11,4)],'small-pool exact transfer')
    def menu(d):d['insurance']['contracts'][0].update(premium='1',indemnity='10')
    r=variant('screening menu breaks',menu)
    eq([x['maximizing_contracts_approx'] for x in r['insurance']['types']],[['partial'],['partial']],'actual menu intervention')
    r=variant('double annuity benefit',lambda d:d['annuity'].__setitem__('benefit','40'))
    eq(F(r['annuity']['variance_per_life']),4*F(out['annuity']['variance_per_life']),'quadratic payout variance')
    r=variant('all pension wealth initially liquid',lambda d:d['pension'].update(money_account='4300',zero_faces=['0','0','0']))
    eq(r['pension']['paths'][0]['without_support']['terminal_cash'],out['pension']['paths'][0]['without_support']['terminal_cash'],'same PV with executable money account')
    r=variant('zero pension assets',lambda d:d['pension'].update(money_account='0',zero_faces=['0','0','0']))
    eq(r['pension']['paths'][0]['without_support']['first_unpaid_date'],1,'early failure stops actual path')
    for capacity,short in [('20','3.75'),('35','0')]:
        r=variant('guarantor '+capacity,lambda d,c=capacity:d['guarantee']['states'][0].__setitem__('guarantor_capacity',c))
        eq(F(r['guarantee']['expectations']['participant_shortfall']),F(short),'guarantee intervention')
    r=variant('income shock',lambda d:d['household']['income'].__setitem__(2,'34'))
    eq([F(l['minimum_extra_initial_cash_for_floor']) for l in r['household']['loans']],[F('2.8'),F('3.76')],'cash repair after shock')
    r=variant('contribution timing',lambda d:d['household']['contributions'].__setitem__(0,'2'))
    eq(F(r['household']['loans'][0]['rows'][-1]['pension_account']),F('39.168'),'locked wealth intervention')
    for p in ['0','1']:
        r=variant('certain pool '+p,lambda d,p=p:[z.__setitem__('claim_probability',p) for z in d['pool']['regimes']])
        eq(F(r['pool']['laws']['common_regime']['variance_average_claim']),0,'boundary Bernoulli law')
    for s in ['0','1']:
        def sure(d,s=s):
            d['annuity']['survival']=[s]*3
            for row in d['annuity']['regimes']:row['survival']=[s]*3
        r=variant('certain survival '+s,sure)
        eq(F(r['annuity']['variance_per_life']),0,'boundary nested law')
    variant('negative rate shift',lambda d:d['pension'].__setitem__('parallel_continuous_rate_shift','-0.01'))

    invalid=[]
    def bad(label,mutate):
        d=copy.deepcopy(data); mutate(d); before=copy.deepcopy(d)
        try:model.run(d)
        except ValueError:pass
        else:raise RuntimeError('accepted invalid '+label)
        eq(d,before,'invalid input not mutated: '+label); invalid.append(label)
    for label,mutate in [
        ('schema bool',lambda d:d.__setitem__('schema',True)),('unknown root key',lambda d:d.__setitem__('extra',0)),
        ('float amount',lambda d:d['insurance'].__setitem__('wealth',100.0)),('exponent string',lambda d:d['insurance'].__setitem__('wealth','1e2')),
        ('loss beyond wealth',lambda d:d['insurance'].__setitem__('loss','101')),('negative state wealth',lambda d:d['insurance']['contracts'][0].__setitem__('premium','60')),
        ('duplicate type',lambda d:d['insurance']['types'][1].__setitem__('id','low')),('negative probability',lambda d:d['insurance']['types'][0].__setitem__('probability','-0.1')),
        ('wrong shares',lambda d:d['insurance']['types'][0].__setitem__('share','0.4')),('reserved contract',lambda d:d['insurance']['contracts'][0].__setitem__('id','uninsured')),
        ('pool member bool',lambda d:d['pool'].__setitem__('members',True)),('pool work bound',lambda d:d['pool'].__setitem__('members',201)),
        ('negative capital',lambda d:d['pool'].__setitem__('capital','-1')),('weight mass',lambda d:d['pool']['regimes'][0].__setitem__('weight','0.6')),
        ('discount zero',lambda d:d['annuity']['discounts'].__setitem__(0,'0')),('survival increases',lambda d:d['annuity']['survival'].__setitem__(1,'0.95')),
        ('regime marginal mismatch',lambda d:d['annuity']['regimes'][0]['survival'].__setitem__(0,'0.80')),('empty survival',lambda d:d['annuity'].__setitem__('survival',[])),
        ('survivor resurrects',lambda d:d['pension']['paths'][0].__setitem__('survivors',[90,91,60])),('noninteger survivor',lambda d:d['pension']['paths'][0]['survivors'].__setitem__(0,90.0)),
        ('negative inventory',lambda d:d['pension']['zero_faces'].__setitem__(0,'-1')),('excessive curve shock',lambda d:d['pension'].__setitem__('parallel_continuous_rate_shift','0.3')),
        ('negative support',lambda d:d['guarantee']['states'][0].__setitem__('sponsor_capacity','-1')),('guarantee mass',lambda d:d['guarantee']['states'][0].__setitem__('probability','0.3')),
        ('household vector length',lambda d:d['household'].__setitem__('income',['38'])),('zero gross return',lambda d:d['household']['pension_gross_returns'].__setitem__(0,'0')),
        ('unretired debt',lambda d:d['household']['loans'][0]['principal_payments'].__setitem__(0,'7')),('negative rate',lambda d:d['household']['loans'][0].__setitem__('rate','-0.1')),
        ('nan decimal text',lambda d:d['household'].__setitem__('initial_liquid','NaN')),('null insurance',lambda d:d.__setitem__('insurance',None))]:bad(label,mutate)

    protected_attempts=0; cli_errors=0
    with tempfile.TemporaryDirectory(prefix='v11-c08-check-') as directory:
        tmp=Path(directory); implementation=tmp/MODEL.name; implementation.write_bytes(MODEL.read_bytes())
        inp=tmp/'v11-c08-inputs.json'; inp.write_text(json.dumps(data)); saved={p:p.read_bytes() for p in [implementation,inp]}
        for opt in [[],['-O']]:
            command=[sys.executable,*opt,str(implementation)]
            r=subprocess.run(command,cwd='/',text=True,capture_output=True,timeout=30)
            eq((r.returncode,r.stderr),(0,''),'portable CLI succeeds quietly')
            eq(json.loads(r.stdout),out,'portable CLI output')
            output=tmp/('output'+str(len(opt))+'.json')
            r=subprocess.run(command+['--output',str(output)],cwd='/',text=True,capture_output=True,timeout=30)
            eq((r.returncode,r.stdout,r.stderr),(0,'',''),'output-file CLI quiet')
            eq(json.loads(output.read_text()),out,'written output equals report')
            for original_path in [inp,implementation]:
                symlink=tmp/(original_path.name+'.symlink'); hardlink=tmp/(original_path.name+'.hardlink')
                if not symlink.exists():symlink.symlink_to(original_path)
                if not hardlink.exists():os.link(original_path,hardlink)
                for destination in [original_path,symlink,hardlink]:
                    r=subprocess.run(command+['--output',str(destination)],cwd='/',text=True,capture_output=True,timeout=30)
                    need(r.returncode==2 and not r.stdout and 'output cannot replace' in r.stderr,'protected alias rejected')
                    for p,bytes_before in saved.items():eq(p.read_bytes(),bytes_before,'protected payload unchanged')
                    protected_attempts+=1
            for payload in ['{"schema":1,"schema":1}','{"schema":NaN}','[]']:
                broken=tmp/'invalid.json'; broken.write_text(payload); failed=tmp/'must-not-write.json'
                r=subprocess.run(command+['--input',str(broken),'--output',str(failed)],cwd='/',text=True,capture_output=True,timeout=30)
                need(r.returncode==2 and not r.stdout and not failed.exists(),'invalid CLI leaves no output'); cli_errors+=1

    chapter=Chapter(); text=(ROOT/'content/chapters/v11-c08.html').read_text(); chapter.feed(text)
    prompts={f'v11-c08-e{i}' for i in range(1,11)}
    eq(chapter.worked,6,'six complete worked cases'); need(prompts<=set(chapter.ids),'all exercise IDs present')
    eq(set(chapter.pairs),prompts,'every prompt paired'); eq(len(chapter.pairs),10,'one solution per prompt')
    eq(len(chapter.ids),len(set(chapter.ids)),'unique anchors')
    eq(chapter.sources,{'v11-c08-ssa-actuarial','v11-c08-dol-plans'},'scoped source IDs')
    for link in chapter.links:need(not link.startswith('projects/'),'flat offline asset link')
    for marker in ['Teach-back and delayed retention','Retention answers','8.846193408','93.8496','29.9257008','39.168']:
        need(marker in text,'instructional/exercise marker '+marker)
    manifest=json.loads((PROJECT/'v11-c08-manifest.json').read_text())
    expected_payloads={f'v11-c08-{suffix}' for suffix in ['inputs.json','analysis.py','output.json','README.txt']}
    eq({x['file'] for x in manifest['files']},expected_payloads,'manifest complete and scoped'); eq(len(manifest['files']),4,'manifest unique')
    for entry in manifest['files']:
        payload=(PROJECT/entry['file']).read_bytes(); eq((len(payload),hashlib.sha256(payload).hexdigest()),(entry['bytes'],entry['sha256']),'manifest exact payload')
    author=json.loads((ROOT/'content/reviews/v11-c08-author.json').read_text())
    expected_paths={'content/chapters/v11-c08.html','scripts/check_v11_c08.py','content/reviews/v11-c08-sources.json'}|{'content/projects/'+name for name in expected_payloads|{'v11-c08-manifest.json'}}
    eq({x['path'] for x in author['reviewed_hashes']},expected_paths,'author exact owned nonself paths'); eq(len(author['reviewed_hashes']),8,'eight distinct payloads')
    for entry in author['reviewed_hashes']:
        payload=(ROOT/entry['path']).read_bytes(); eq((len(payload),hashlib.sha256(payload).hexdigest()),(entry['bytes'],entry['sha256']),'author exact payload binding')
    return {'chapter':'v11-c08','status':'passed','comparisons':COUNT,'financial_interventions':len(variants),
            'invalid_api_inputs_rejected':len(invalid),'invalid_cli_inputs_rejected':cli_errors,'protected_output_attempts':protected_attempts,
            'worked_examples':6,'solved_exercises':10,'author_payload_hashes_verified':8,
            'independent_methods':['direct combinatorial claim-count probabilities','nested survival covariance','discounted cash and bond-inventory conservation','support priority and resource certificates','closed-form contribution-vintage and household cash sums','exact exercise transfers and analytical proof review'],
            'limits':'Author calculation and scoped evidence audit only; separate peer/coordinator acceptance and actual-law/calibration/whole-edition UI review remain distinct.'}


if __name__=='__main__': print(json.dumps(check(),indent=2,allow_nan=False))
