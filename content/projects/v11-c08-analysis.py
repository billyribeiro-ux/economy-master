"""Original finite insurance, survival, pension funding and household cash lab.

Python standard library only. run(data) is quiet and nonmutating. All financial
arithmetic is exact rational arithmetic except explicitly labeled utility and
exponential curve-shift approximations. No external data or network requests.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction as F
import json
import math
from pathlib import Path
import re
import sys


def need(condition, message):
    if not condition:
        raise ValueError(message)


def obj(value, keys, name):
    need(type(value) is dict and set(value) == set(keys.split()), name + ': exact object keys required')


def seq(value, name, size=None, maximum=12):
    need(type(value) is list and 1 <= len(value) <= maximum, name + ': bounded nonempty list required')
    if size is not None:
        need(len(value) == size, name + ': wrong length')
    return value


def number(value, name, low=F(0), high=F(10**9), positive=False):
    need(type(value) is str and len(value) <= 32 and re.fullmatch(r'-?\d{1,12}(?:\.\d{1,12})?', value) is not None,
         name + ': bounded exact decimal string required')
    q = F(value)
    need(low <= q <= high and (not positive or q > 0), name + ': outside allowed range')
    return q


def integer(value, name, low=1, high=200):
    need(type(value) is int and low <= value <= high, name + ': bounded integer required')
    return value


def identifiers(rows, name):
    ids = [row.get('id') if type(row) is dict else None for row in rows]
    need(all(type(x) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,39}', x) for x in ids), name + ': invalid ID')
    need(len(set(ids)) == len(ids), name + ': duplicate ID')


def probabilities(rows, key, name):
    values = [number(row[key], name + '.' + key, high=F(1)) for row in rows]
    need(sum(values) == 1, name + ': weights must sum exactly to one')


def survival(values, name, size):
    seq(values, name, size)
    numbers = [number(x, name, high=F(1)) for x in values]
    need(all(a >= b for a, b in zip(numbers, numbers[1:])), name + ': survival must be nonincreasing')


def validate(data):
    obj(data, 'schema units insurance pool annuity pension guarantee household', 'input')
    need(type(data['schema']) is int and data['schema'] == 1, 'schema must be integer 1')
    need(type(data['units']) is str and 1 <= len(data['units']) <= 180, 'units must be a short string')
    ins = data['insurance']
    obj(ins, 'wealth loss types contracts', 'insurance')
    wealth = number(ins['wealth'], 'wealth', positive=True)
    loss = number(ins['loss'], 'loss', high=wealth)
    seq(ins['types'], 'types', maximum=8); identifiers(ins['types'], 'types')
    for t in ins['types']:
        obj(t, 'id probability share', 'type')
        number(t['probability'], 'claim probability', high=F(1))
        number(t['share'], 'type share', high=F(1), positive=True)
    probabilities(ins['types'], 'share', 'types')
    seq(ins['contracts'], 'contracts', maximum=8); identifiers(ins['contracts'], 'contracts')
    for c in ins['contracts']:
        obj(c, 'id premium indemnity', 'contract')
        need(c['id'] != 'uninsured', 'uninsured is reserved')
        premium = number(c['premium'], 'premium', high=wealth)
        indemnity = number(c['indemnity'], 'indemnity', high=loss)
        need(wealth-premium-loss+indemnity >= 0, 'negative loss-state utility wealth')
    pool = data['pool']
    obj(pool, 'members benefit premium capital regimes', 'pool')
    integer(pool['members'], 'pool members')
    for key in ['benefit', 'premium', 'capital']: number(pool[key], 'pool.'+key)
    seq(pool['regimes'], 'pool regimes', maximum=8); identifiers(pool['regimes'], 'pool regimes')
    for r in pool['regimes']:
        obj(r, 'id weight claim_probability', 'pool regime')
        number(r['claim_probability'], 'regime claim probability', high=F(1))
    probabilities(pool['regimes'], 'weight', 'pool regimes')
    ann = data['annuity']
    obj(ann, 'members benefit discounts survival stress_survival regimes death_benefit', 'annuity')
    integer(ann['members'], 'annuity members')
    number(ann['benefit'], 'annuity benefit'); number(ann['death_benefit'], 'death benefit')
    dates = len(seq(ann['discounts'], 'discounts'))
    for d in ann['discounts']: number(d, 'discount', low=F(1,10**6), high=F(100))
    survival(ann['survival'], 'baseline survival', dates)
    survival(ann['stress_survival'], 'stress survival', dates)
    seq(ann['regimes'], 'annuity regimes', maximum=8); identifiers(ann['regimes'], 'annuity regimes')
    for r in ann['regimes']:
        obj(r, 'id weight survival', 'annuity regime')
        survival(r['survival'], 'regime survival', dates)
    probabilities(ann['regimes'], 'weight', 'annuity regimes')
    for t in range(dates):
        need(sum(F(r['weight'])*F(r['survival'][t]) for r in ann['regimes']) == F(ann['survival'][t]),
             'annuity regimes must reproduce baseline marginal survival')
    fund = data['pension']
    obj(fund, 'money_account zero_faces parallel_continuous_rate_shift paths', 'pension')
    number(fund['money_account'], 'pension money account')
    for x in seq(fund['zero_faces'], 'zero faces', dates): number(x, 'zero face')
    number(fund['parallel_continuous_rate_shift'], 'curve shift', low=F(-1,5), high=F(1,5))
    seq(fund['paths'], 'pension paths', maximum=8); identifiers(fund['paths'], 'pension paths')
    for path in fund['paths']:
        obj(path, 'id survivors', 'pension path')
        counts = seq(path['survivors'], 'path survivors', dates)
        for x in counts: integer(x, 'survivor count', low=0, high=ann['members'])
        need(all(a >= b for a,b in zip(counts, counts[1:])), 'survivor counts must be nonincreasing')
    guarantee = data['guarantee']
    obj(guarantee, 'promised_benefit states', 'guarantee')
    number(guarantee['promised_benefit'], 'promised benefit')
    seq(guarantee['states'], 'guarantee states'); identifiers(guarantee['states'], 'guarantee states')
    for state in guarantee['states']:
        obj(state, 'id probability assets sponsor_capacity guarantor_capacity', 'guarantee state')
        for key in ['assets', 'sponsor_capacity', 'guarantor_capacity']: number(state[key], 'guarantee.'+key)
    probabilities(guarantee['states'], 'probability', 'guarantee states')
    h = data['household']
    obj(h, 'initial_liquid initial_pension liquid_floor income consumption contributions pension_gross_returns debt loans', 'household')
    for key in ['initial_liquid','initial_pension','liquid_floor','debt']: number(h[key], 'household.'+key)
    periods = len(seq(h['income'], 'household income'))
    for key in ['income','consumption','contributions','pension_gross_returns']:
        for x in seq(h[key], 'household.'+key, periods): number(x, 'household.'+key, positive=key=='pension_gross_returns')
    seq(h['loans'], 'household loans', maximum=8); identifiers(h['loans'], 'household loans')
    for loan in h['loans']:
        obj(loan, 'id rate principal_payments', 'household loan')
        number(loan['rate'], 'loan rate', high=F(1))
        principal = [number(x, 'principal payment') for x in seq(loan['principal_payments'], 'principal payments', periods)]
        need(sum(principal) == F(h['debt']), 'principal payments must retire exactly the initial debt')


def dec(q):
    return Decimal(q.numerator)/Decimal(q.denominator)


def expected_utility(wealth, loss, p, premium=F(0), indemnity=F(0)):
    return (1-dec(p))*dec(wealth-premium).sqrt()+dec(p)*dec(wealth-premium-loss+indemnity).sqrt()


def insurance_result(ins):
    wealth, loss = F(ins['wealth']), F(ins['loss'])
    pooled_p = sum(F(t['share'])*F(t['probability']) for t in ins['types'])
    pooled_premium = pooled_p*loss
    rows, buyers = [], []
    with localcontext() as ctx:
        ctx.prec = 40
        tolerance = Decimal('1e-30')
        contracts = [{'id':'uninsured','premium':'0','indemnity':'0'}] + ins['contracts']
        for t in ins['types']:
            p = F(t['probability']); uninsured = expected_utility(wealth,loss,p)
            offers = []
            for c in contracts:
                premium, indemnity = F(c['premium']), F(c['indemnity'])
                offers.append({'id':c['id'], 'expected_utility_approx':str(expected_utility(wealth,loss,p,premium,indemnity)),
                               'premium_minus_expected_claim':str(premium-p*indemnity)})
            best = max(Decimal(o['expected_utility_approx']) for o in offers)
            accepts_pool = dec(wealth-pooled_premium).sqrt() >= uninsured-tolerance
            if accepts_pool: buyers.append(t)
            rows.append({'id':t['id'], 'no_insurance_utility_approx':str(uninsured),
                         'full_insurance_max_premium_approx':str(dec(wealth)-uninsured**2),
                         'accepts_pooled_full_insurance':accepts_pool, 'offers':offers,
                         'maximizing_contracts_approx':[o['id'] for o in offers if best-Decimal(o['expected_utility_approx']) <= tolerance]})
    buyer_share = sum(F(t['share']) for t in buyers)
    claim_p = None if not buyers else sum(F(t['share'])*F(t['probability']) for t in buyers)/buyer_share
    return {'types':rows, 'pooled_claim_probability':str(pooled_p),'pooled_full_premium':str(pooled_premium),
            'buyer_share':str(buyer_share),'selected_claim_probability':None if claim_p is None else str(claim_p),
            'margin_per_selected_policy':None if claim_p is None else str(pooled_premium-claim_p*loss),
            'scope':'Square-root utility; solvent contractual payout assumed for choices. Decimal utility approximations use precision 40 and absolute tie tolerance 1e-30; pool purchase on indifference. Fixed menu only, no market equilibrium.'}


def binomial(n,p):
    if p == 1: return [F(0)]*n+[F(1)]
    values = [(1-p)**n]
    for k in range(n): values.append(values[-1]*(n-k)*p/((k+1)*(1-p)))
    return values


def pool_result(pool):
    n, benefit = pool['members'], F(pool['benefit'])
    regimes = [(F(r['weight']),F(r['claim_probability'])) for r in pool['regimes']]
    p = sum(w*q for w,q in regimes)
    resources = n*F(pool['premium'])+F(pool['capital'])
    mix = [F(0)]*(n+1)
    for w,q in regimes:
        for k,mass in enumerate(binomial(n,q)): mix[k] += w*mass
    rows = {}
    for name,law in [('independent',binomial(n,p)),('common_regime',mix)]:
        rows[name] = {'shortfall_probability':str(sum(m for k,m in enumerate(law) if k*benefit > resources)),
                      'expected_unpaid_claims':str(sum(m*max(k*benefit-resources,0) for k,m in enumerate(law))),
                      'variance_average_claim':str(sum(m*(k*benefit/n-benefit*p)**2 for k,m in enumerate(law)))}
    between = sum(w*(q-p)**2 for w,q in regimes)
    within = sum(w*q*(1-q) for w,q in regimes)
    return {'members':n,'marginal_probability':str(p),'resources':str(resources),
            'expected_claims':str(n*benefit*p), 'expected_premium_margin':str(n*(F(pool['premium'])-benefit*p)),
            'common_probability_variance':str(between), 'conditional_bernoulli_variance':str(within),
            'limiting_variance_average_claim':str(benefit**2*between), 'laws':rows,
            'scope':'Claims paid at one date, no expenses/interest/reinsurance; conditional independence within each stipulated common regime; strict resource shortfall. Expected unpaid claims are before any support or resolution.'}


def life_states(s,discounts,benefit):
    probabilities = [1-s[0]]+[s[i-1]-s[i] for i in range(1,len(s))]+[s[-1]]
    payoffs, accrued = [F(0)], F(0)
    for d in discounts:
        accrued += benefit*d
        payoffs.append(accrued)
    mean = sum(p*x for p,x in zip(probabilities,payoffs))
    variance = sum(p*(x-mean)**2 for p,x in zip(probabilities,payoffs))
    return probabilities,payoffs,mean,variance


def annuity_result(ann):
    s,d,b = list(map(F,ann['survival'])),list(map(F,ann['discounts'])),F(ann['benefit'])
    probs,values,mean,variance = life_states(s,d,b)
    n = ann['members']; regimes=[]
    for r in ann['regimes']:
        _,_,mu,var = life_states(list(map(F,r['survival'])),d,b)
        regimes.append({'id':r['id'],'weight':r['weight'],'mean':str(mu),'variance':str(var)})
    within = sum(F(r['weight'])*F(r['variance']) for r in regimes)
    between = sum(F(r['weight'])*(F(r['mean'])-mean)**2 for r in regimes)
    stress_mean = life_states(list(map(F,ann['stress_survival'])),d,b)[2]
    previous = [F(1)]+s[:-1]
    return {'single_life_states':[{'payments_received':k,'probability':str(p),'present_value':str(v)} for k,(p,v) in enumerate(zip(probs,values))],
            'mean_per_life':str(mean),'variance_per_life':str(variance),'expected_cohort_liability':str(n*mean),
            'iid_variance_average':str(variance/n),'iid_variance_total':str(n*variance),
            'regimes':regimes,'within_regime_variance':str(within),'between_regime_mean_variance':str(between),
            'common_regime_variance_average':str(within/n+between),'common_regime_variance_total':str(n*within+n*n*between),
            'stress_mean_per_life':str(stress_mean),'stress_expected_cohort_liability':str(n*stress_mean),
            'temporary_death_benefit_pv':str(F(ann['death_benefit'])*sum(df*(a-z) for df,a,z in zip(d,previous,s))),
            'scope':'Temporary end-year survivor payments only; deterministic discounts and physical survival law. Average and total variances have CU-squared units. Actuarial expectation is not automatically a market price.'}


def funding_path(fund,ann,path,extra=F(0)):
    discounts = list(map(F,ann['discounts'])); faces=list(map(F,fund['zero_faces']))
    cash = F(fund['money_account'])+extra; previous=F(1); rows=[]; failed=None
    for t,d in enumerate(discounts):
        opening=cash; accrued=cash*previous/d; matured=faces[t]; faces[t]=F(0)
        cash=accrued+matured; due=F(ann['benefit'])*path['survivors'][t]; sales=[]
        for j in range(len(faces)-1,t,-1):
            quote=discounts[j]/d
            sold=min(faces[j],max(due-cash,0)/quote)
            if sold:
                faces[j]-=sold; cash+=sold*quote
                sales.append({'maturity':j+1,'face_sold':str(sold),'price_per_face':str(quote),'receipt':str(sold*quote)})
        paid=min(cash,due); cash-=paid
        rows.append({'date':t+1,'opening_cash':str(opening),'accrued_cash':str(accrued),'matured_face':str(matured),
                     'sales':sales,'due':str(due),'paid':str(paid),'unpaid':str(due-paid),'closing_cash':str(cash),
                     'remaining_faces':[str(x) for x in faces]})
        if paid < due:
            failed=t+1
            break
        previous=d
    return {'rows':rows,'first_unpaid_date':failed,'all_payments_met':failed is None,
            'terminal_cash':str(cash) if failed is None else None,
            'scope':'Maturities and accrued cash arrive before payout; sell latest remaining maturities first at executable deterministic D[j]/D[t], before payout. No borrowing; stop at first unpaid benefit.'}


def pension_result(fund,ann):
    d=list(map(F,ann['discounts'])); faces=list(map(F,fund['zero_faces'])); b=F(ann['benefit']); n=ann['members']
    expected=[n*b*F(s) for s in ann['survival']]
    assets=F(fund['money_account'])+sum(df*x for df,x in zip(d,faces))
    liability=sum(df*x for df,x in zip(d,expected)); rows=[]
    for path in fund['paths']:
        cost=sum(df*b*k for df,k in zip(d,path['survivors'])); extra=max(cost-assets,0)
        rows.append({'id':path['id'],'path_liability_pv':str(cost),'initial_path_surplus':str(assets-cost),
                     'minimum_extra_initial_cash_with_stated_markets':str(extra),
                     'without_support':funding_path(fund,ann,path),
                     'with_minimum_extra_cash':funding_path(fund,ann,path,extra)})
    shift=float(F(fund['parallel_continuous_rate_shift'])); shifted=[float(df)*math.exp(-(t+1)*shift) for t,df in enumerate(d)]
    shifted_a=float(F(fund['money_account']))+sum(df*float(x) for df,x in zip(shifted,faces))
    shifted_l=sum(df*float(x) for df,x in zip(shifted,expected))
    return {'initial_asset_pv':str(assets),'expected_liability_pv':str(liability),'expected_surplus':str(assets-liability),
            'surplus_derivative_per_unit_parallel_continuous_rate':str(sum((t+1)*df*(l-a) for t,(df,l,a) in enumerate(zip(d,expected,faces)))),
            'curve_shift':fund['parallel_continuous_rate_shift'],'shifted_asset_pv_approx':shifted_a,
            'shifted_liability_pv_approx':shifted_l,'shifted_surplus_approx':shifted_a-shifted_l,'paths':rows}


def guarantee_result(g):
    benefit=F(g['promised_benefit']); rows=[]
    totals={key:F(0) for key in ['assets','required_sponsor_topup','actual_sponsor_payment','guarantor_payment','participant_payment','participant_shortfall','residual_assets']}
    for state in g['states']:
        a,p=F(state['assets']),F(state['probability']); gap=max(benefit-a,0)
        sponsor=min(gap,F(state['sponsor_capacity'])); guarantor=min(gap-sponsor,F(state['guarantor_capacity']))
        paid=min(benefit,a+sponsor+guarantor)
        result={'assets':a,'required_sponsor_topup':gap,'actual_sponsor_payment':sponsor,'guarantor_payment':guarantor,
                'participant_payment':paid,'participant_shortfall':benefit-paid,'residual_assets':max(a-benefit,0)}
        rows.append({'id':state['id'],'probability':str(p),**{key:str(value) for key,value in result.items()}})
        for key,value in result.items(): totals[key]+=p*value
    return {'states':rows,'expectations':{key:str(value) for key,value in totals.items()},
            'scope':'One terminal benefit; assets then sponsor then guarantor; separately available state-specific capacities are external to assets. No premiums, subrogation or statutory insurance is modeled. Residual assets belong to the stipulated sponsor.'}


def household_result(h):
    results=[]
    for loan in h['loans']:
        cash=F(h['initial_liquid']); account=F(h['initial_pension']); debt=F(h['debt']); rows=[]
        minimum=cash; interest_sum=F(0); cash_fail=0 if cash < 0 else None
        floor_fail=0 if cash < F(h['liquid_floor']) else None
        for t,principal_text in enumerate(loan['principal_payments']):
            principal=F(principal_text); interest=debt*F(loan['rate']); debt-=principal
            income,consumption,contribution=[F(h[key][t]) for key in ['income','consumption','contributions']]
            opening=cash; cash+=income-consumption-contribution-principal-interest
            previous_account=account; account=account*F(h['pension_gross_returns'][t])+contribution
            minimum=min(minimum,cash); interest_sum+=interest
            if cash_fail is None and cash < 0: cash_fail=t+1
            if floor_fail is None and cash < F(h['liquid_floor']): floor_fail=t+1
            rows.append({'date':t+1,'opening_cash':str(opening),'income':str(income),'consumption':str(consumption),
                         'contribution':str(contribution),'interest':str(interest),'principal':str(principal),
                         'debt_service':str(interest+principal),'remaining_debt':str(debt),'projected_liquid':str(cash),
                         'opening_pension':str(previous_account),'pension_account':str(account)})
        results.append({'id':loan['id'],'rows':rows,'total_interest':str(interest_sum),'minimum_projected_liquid':str(minimum),
                        'first_floor_breach':floor_fail,'first_negative_cash':cash_fail,
                        'minimum_extra_initial_cash_for_floor':str(max(F(h['liquid_floor'])-minimum,0))})
    return {'loans':results,'scope':'Debt already exists after a financed purchase; no fresh loan proceeds added. Liquid money earns zero; income precedes end-year obligations. Pension return precedes contribution; pension locked beyond final date. Negative projected cash signals failure, never an assumed borrowing facility. Fixed-plan cash minimum includes date zero.'}


def run(data):
    """Validate first; return a quiet JSON-safe report without changing data."""
    validate(data)
    return {'schema':1,'units':data['units'],'insurance':insurance_result(data['insurance']),
            'pool':pool_result(data['pool']),'annuity':annuity_result(data['annuity']),
            'pension':pension_result(data['pension'],data['annuity']),'guarantee':guarantee_result(data['guarantee']),
            'household':household_result(data['household']),
            'limits':['Original stipulated cases, not observed frequencies, legal advice, a solvency standard or a personal recommendation.',
                      'Exact fractions are strings; square-root utility and exponential curve shifts are explicitly approximate.',
                      'Conditional independence, execution access, survival laws and support capacities are assumptions requiring separate evidence in an actual application.']}


def pairs_hook(pairs):
    result={}
    for key,value in pairs:
        need(key not in result, 'duplicate JSON key: '+key)
        result[key]=value
    return result


def bad_constant(value):
    raise ValueError('nonfinite JSON constant: '+value)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v11-c08-inputs.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        if args.output is not None:
            protected=[args.input.resolve(),Path(__file__).resolve()]
            aliases=args.output.exists() and any(args.output.samefile(p) for p in protected if p.exists())
            need(args.output.resolve() not in protected and not aliases, 'output cannot replace input or implementation')
        data=json.loads(args.input.read_text(encoding='utf-8'),object_pairs_hook=pairs_hook,parse_constant=bad_constant)
        payload=json.dumps(run(data),indent=2,ensure_ascii=False,allow_nan=False)+'\n'
        if args.output is None: sys.stdout.write(payload)
        else: args.output.write_text(payload,encoding='utf-8')
    except (ValueError,TypeError,OSError,OverflowError) as error:
        print('Input/output error: '+str(error),file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
