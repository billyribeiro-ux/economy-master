"""Original two-state retrofit policy/investment case; exact stdlib reader."""
from fractions import Fraction as F
from pathlib import Path
import argparse,json,re

def need(ok,msg):
    if not ok:raise ValueError(msg)
def rat(x):
    need(type(x)in(int,str,F),'rational type; no bool/float')
    if isinstance(x,str):need(len(x)<80 and re.fullmatch(r'-?\d+(?:/\d+)?',x)is not None,'rational syntax')
    try:y=F(x)
    except (ValueError,ZeroDivisionError):raise ValueError('invalid rational')from None
    need(abs(y)<=10000,'rational magnitude');return y
def pack(x):
    if isinstance(x,F):return x.numerator if x.denominator==1 else str(x)
    if isinstance(x,dict):return{k:pack(v)for k,v in x.items()}
    if isinstance(x,(tuple,list)):return[pack(v)for v in x]
    return x

def price(q,pay):return sum(a*x for a,x in zip(q,pay))
def debt_face(q,cash,loan):
    need(len(q)==len(cash)>0 and min(q)>0 and min(cash)>=0 and loan>=0,'debt domain')
    if loan==0:return F(0)
    need(loan<=price(q,cash),'loan exceeds pledgeable cash value')
    last=F(0)
    for edge in sorted(set(cash)):
        slope=sum(prob for prob,x in zip(q,cash)if x>last);base=price(q,tuple(min(last,x)for x in cash))
        if slope and loan<=base+slope*(edge-last):return last+(loan-base)/slope
        last=edge
    raise ValueError('debt inversion')

def validate(data):
    need(type(data)is dict and data.get('schema')=='integrated-retrofit-1'and data.get('synthetic')is True,'schema/synthetic')
    menu=data['quantities'];need(type(menu)is list and menu and all(type(n)is int and 0<=n<=10 for n in menu)and len(set(menu))==len(menu)and 0 in menu,'finite unique quantity menu')
    p=tuple(map(rat,data['state_probabilities']));m=tuple(map(rat,data['sdf']));revenue=tuple(map(rat,data['revenue_per_unit']));benefit=tuple(map(rat,data['service_value_per_unit']));need(len(p)==len(m)==len(revenue)==len(benefit)==2 and min(p)>0 and sum(p)==1 and min(m)>0 and min(revenue)>=0 and min(benefit)>=0,'two economic states')
    keys=('installation_cost','operating_cost','grant','developer_equity_per_unit','grant_admin_rate','bank_endowment','developer_endowment','bank_loan_cap','treasury_limit','household_current_cash','household_future_income','external_congestion','transfer_admin_rate','observed_difference','high_endpoint_weight')
    x={k:rat(data[k])for k in keys};need(min(x[k]for k in keys if k!='observed_difference')>=0 and x['installation_cost']>0 and 0<=x['high_endpoint_weight']<=1,'primitive domain')
    need(x['grant']+x['developer_equity_per_unit']<x['installation_cost'],'positive bank finance');need(min(revenue)>=x['operating_cost'],'nonnegative firm cash');s=tuple(map(rat,data['selection_interval']));need(len(s)==2 and s[0]<=s[1],'closed selection interval')
    need(data['conventions']=={'procurement':'government selects quantity; developer accepts zero NPV','finance':'limited liability debt; no guarantee; bank equity financed','valuation':'state prices apply to consumption equivalents; not an empirical estimate','compensation':'current verified transfer; payer covers real administration'},'conventions')
    return menu,p,m,revenue,benefit,x,s

def run(data):
    menu,p,m,revenue,benefit,x,s=validate(data);q=tuple(a*b for a,b in zip(p,m));bond=sum(q);R=1/bond;theta=(x['observed_difference']-s[1],x['observed_difference']-s[0]);need(theta[0]<=theta[1],'effect interval');rows=[]
    for n in sorted(menu):
        install=x['installation_cost']*n;grant=x['grant']*n;equity=x['developer_equity_per_unit']*n;loan=install-grant-equity;admin=x['grant_admin_rate']*grant;levy=(grant+admin)/2;cash=tuple((r-x['operating_cost'])*n for r in revenue);fail=[]
        if loan>x['bank_endowment']or loan>x['bank_loan_cap']:fail.append('bank_funding')
        if equity>x['developer_endowment']:fail.append('developer_funding')
        if grant+admin>x['treasury_limit']:fail.append('public_appropriation')
        if levy>x['household_current_cash']:fail.append('initial_household_cash')
        if max(revenue)*n>x['household_future_income']:fail.append('service_bill')
        if loan>price(q,cash):fail.append('pledgeable_value')
        row={'quantity':n,'installation':install,'grant':grant,'grant_admin':admin,'levy_each':levy,'developer_equity':equity,'bank_loan':loan,'feasible':not fail,'failures':fail}
        if 'pledgeable_value'in fail:rows.append(row);continue
        face=debt_face(q,cash,loan);debt=tuple(min(face,v)for v in cash);stock=tuple(v-d for v,d in zip(cash,debt));eqpv=price(q,stock);private_npv=eqpv-equity
        if private_npv<0:row['feasible']=False;row['failures'].append('developer_participation')
        bankcash=x['bank_endowment']-loan;devcash=x['developer_endowment']-equity;bankfinal=tuple(d+bankcash*R for d in debt);devfinal=tuple(v+devcash*R for v in stock)
        row.update(debt_face=face,debt_payoffs=debt,equity_payoffs=stock,debt_value=price(q,debt),equity_value=eqpv,private_npv=private_npv,bank_cash=bankcash,bank_final=bankfinal,bank_npv=price(q,bankfinal)-x['bank_endowment'],developer_final=devfinal)
        accounts=[]
        for j in range(2):
            bill=revenue[j]*n;operating=x['operating_cost']*n;households=(x['household_future_income']-bill,x['household_future_income']);goods=sum(households)+bankfinal[j]+devfinal[j]+operating;available=2*x['household_future_income']+(bankcash+devcash)*R
            need(goods==available,'future goods identity');accounts.append({'service_bill':bill,'operating_resources':operating,'household_consumption':households,'goods_total_including_operations':goods,'available_goods':available,'debt_shortfall':face-debt[j]})
        initial_use=install+admin+bankcash+devcash+2*(x['household_current_cash']-levy);initial_resources=x['bank_endowment']+x['developer_endowment']+2*x['household_current_cash'];need(initial_use==initial_resources,'initial account')
        values=[];poor=[];rich=[];resource=[]
        for th in theta:
            external=th*n-x['external_congestion']*n*n;service=tuple((v-r)*n for v,r in zip(benefit,revenue));a=price(q,service)+bond*external/2-levy;b=bond*external/2-levy;w=a+b+private_npv+row['bank_npv'];direct=price(q,tuple((v-x['operating_cost'])*n+external for v in benefit))-install-admin;need(w==direct,'welfare consolidation');poor.append(a);rich.append(b);values.append(w);resource.append(direct)
        required=max(F(0),-min(rich));payer_upper=min(poor)/(1+x['transfer_admin_rate']);cash_upper=(x['household_current_cash']-levy)/(1+x['transfer_admin_rate']);upper=min(payer_upper,cash_upper);comp_feasible=row['feasible']and required<=upper
        comp={'lower':required,'upper':upper,'feasible':comp_feasible}
        if comp_feasible:comp.update(transfer=required,real_admin=x['transfer_admin_rate']*required,poor=tuple(a-(1+x['transfer_admin_rate'])*required for a in poor),rich=tuple(b+required for b in rich),total=tuple(w-x['transfer_admin_rate']*required for w in values))
        row.update(initial_resource_total=initial_resources,initial_uses=initial_use,state_accounts=accounts,poor_values=poor,rich_values=rich,social_values=values,direct_resource_values=resource,expected_value=(1-x['high_endpoint_weight'])*values[0]+x['high_endpoint_weight']*values[1],robust_compensation=comp)
        rows.append(row)
    feasible=[r for r in rows if r['feasible']];need(feasible,'no feasible action');best=tuple(max(r['social_values'][j]for r in feasible)for j in range(2))
    for row in feasible:row['regrets']=tuple(v-w for v,w in zip(best,row['social_values']));row['max_regret']=max(row['regrets'])
    def opt(field,minimum=False):
        val=(min if minimum else max)(r[field]for r in feasible);return{'value':val,'quantities':[r['quantity']for r in feasible if r[field]==val]}
    envelope=[]
    for row in feasible:
        lo,hi=F(0),F(1);a,bv=row['social_values'];slope=bv-a;possible=True
        for other in feasible:
            c,d=other['social_values'];ds=slope-(d-c);rhs=c-a
            if ds>0:lo=max(lo,rhs/ds)
            elif ds<0:hi=min(hi,rhs/ds)
            elif rhs>0:possible=False
        if possible and lo<=hi:envelope.append({'quantity':row['quantity'],'high_weight_interval':[lo,hi]})
    return pack({'schema':'integrated-retrofit-output-1','state_prices':q,'safe_price':bond,'safe_gross_return':R,'causal_interval':theta,'observationally_equivalent_endpoint_parameters':[(th,x['observed_difference']-th)for th in theta],'policies':rows,'expected_optimum':opt('expected_value'),'minimax_regret':opt('max_regret',True),'state_best_values':best,'forecast_envelope':envelope,'robust_compensable_quantities':[r['quantity']for r in feasible if r['robust_compensation']['feasible']]})

def main():
    here=Path(__file__).resolve().parent;ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,default=here/'integrated-case-inputs.json');ap.add_argument('--output',type=Path,default=here/'integrated-case-output.json');args=ap.parse_args();protected=[args.input,Path(__file__),here/'integrated-case-inputs.json',here/'integrated-case-README.txt',here/'integrated-case-manifest.json']
    for p in protected:
        need(args.output.resolve()!=p.resolve(),'protected output alias')
        if args.output.exists()and p.exists():need(not args.output.samefile(p),'protected hardlink alias')
    output=run(json.loads(args.input.read_text()));payload=json.dumps(output,indent=2,sort_keys=True,allow_nan=False)+'\n';args.output.write_text(payload)
if __name__=='__main__':main()
