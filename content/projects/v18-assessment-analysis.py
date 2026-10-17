"""Exact synthetic leadership event and resource audit; standard library, no external data."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

NAMES = ('v18-assessment-inputs.json', 'v18-assessment-analysis.py',
         'v18-assessment-README.txt', 'v18-assessment-manifest.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_loads(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('nonfinite JSON value')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


def number(value):
    require(type(value) in (int, str), 'exact numbers must be integers or rational strings')
    if isinstance(value, str):
        parts = value.split('/')
        require(1 <= len(parts) <= 2 and all(p.lstrip('-').isdigit() for p in parts), 'invalid rational')
    return Fraction(value)


def packed(value):
    if isinstance(value, Fraction):
        return value.numerator if value.denominator == 1 else str(value)
    if isinstance(value, (tuple, list)):
        return [packed(x) for x in value]
    if isinstance(value, dict):
        return {k: packed(v) for k, v in value.items()}
    return value


def academic(case):
    names=('unrestricted','restricted','fixed','floor','staff','grant','grant_day','complementarity');U,R,fixed,floor,H,grant,day,bonus=(number(case[k]) for k in names)
    require(min(U,R,fixed,floor,H,grant,day,bonus)>=0,'nonnegative academic primitive');require(R==0,'opening restricted fund absent in this model');require(day.denominator==1,'integer grant day')
    options=case['options'];require(len(options)==3 and [x['id'] for x in options]==['R','T','L'],'three named options')
    for row in options:
        require(all(number(row[k])>=0 for k in ('cost','staff','score','start_day')) and number(row['start_day']).denominator==1,'option domain');require(type(row['grant_eligible']) is bool and row['deliverable'],'option scope')
    rows=[]
    for mask in range(8):
        selected=[row for i,row in enumerate(options) if mask&(1<<i)];codes=[row['id'] for row in selected];cash=U-fixed;restricted=R;minimum=cash;spent=Fraction(0);history=[{'day':0,'event':'fixed','unrestricted':cash,'restricted':restricted}]
        timed=[(day,0,{'id':'grant'})]+[(number(row['start_day']),1,row) for row in selected]
        for date,kind,row in sorted(timed,key=lambda x:(x[0],x[1],x[2]['id'])):
            if kind==0:restricted+=grant
            else:
                cost=number(row['cost']);use=min(cost,restricted) if row['grant_eligible'] else Fraction(0);restricted-=use;cash-=cost-use;spent+=cost
            minimum=min(minimum,cash);history.append({'day':date,'event':row['id'],'unrestricted':cash,'restricted':restricted})
        staff=sum(number(row['staff']) for row in selected);score=sum(number(row['score']) for row in selected)+(bonus if 'R'in codes and 'T'in codes else 0);diagnostics=[]
        if staff>H:diagnostics.append('staff_capacity')
        if minimum<floor:diagnostics.append('dated_unrestricted_floor')
        rows.append({'bundle':'+'.join(codes) or 'none','cost':spent,'staff':staff,'score':score,'minimum_unrestricted':minimum,'closing_unrestricted':cash,'closing_restricted':restricted,'feasible':not diagnostics,'diagnostics':diagnostics,'timeline':history})
    feasible=[x for x in rows if x['feasible']];best=min(feasible,key=lambda x:(-x['score'],x['cost'],x['bundle']))['bundle'] if feasible else None
    return {'options':rows,'selected':best,'diagnostic':None if feasible else 'no_feasible_bundle_even_without_expansion'}

def people(data):
    rows=[]
    for person in data['candidates']:
        require(isinstance(person['id'],str) and person['id'],'candidate ID');submitted=person['submitted'];ratings=person['ratings'];require(len(submitted)==len(ratings)==2 and all(type(x)is bool for x in submitted),'candidate grid')
        for ok,score,text in zip(submitted,ratings,(person['research_work'],person['teaching_work'])):
            if ok:require(type(score)is int and 0<=score<=10 and text.strip(),'submitted rated work')
            else:require(score is None and not text,'missing work has no fabricated rating/text')
        lo=sum(score if ok else 0 for ok,score in zip(submitted,ratings))/Fraction(2);hi=sum(score if ok else 10 for ok,score in zip(submitted,ratings))/Fraction(2);rows.append({'id':person['id'],'eligible':all(submitted),'score':lo if all(submitted) else None,'possible_equal_weight_score':[lo,hi]})
    require(len({x['id'] for x in rows})==len(rows) and rows,'unique candidate IDs');eligible=[x for x in rows if x['eligible']];winner=sorted(x['id'] for x in eligible if x['score']==max(y['score'] for y in eligible)) if eligible else []
    inc=data['incentives'];w,rho,out,emin,qmin,envelope,nonpay=(number(inc[k]) for k in ('salary','intrinsic_quality','outside_utility','minimum_output','minimum_quality','personnel_envelope','nonpay_cost'));require(min(w,rho,envelope,nonpay)>=0 and 0<=emin<=1 and 0<=qmin<=1,'effort domain');contracts=[]
    bonuses=[number(x) for x in inc['bonuses']];require(bonuses and len(set(bonuses))==len(bonuses) and min(bonuses)>=0,'bonus menu')
    for b in bonuses:
        e=min(Fraction(1),max(Fraction(0),(1+b-rho)/2));q=1-e;utility=w+b*e+rho*q-(e*e+q*q)/2;reserve=w+b+nonpay;diagnostics=[]
        if e<emin:diagnostics.append('minimum_output')
        if q<qmin:diagnostics.append('minimum_quality')
        if utility<out:diagnostics.append('participation')
        if reserve>envelope:diagnostics.append('personnel_envelope')
        contracts.append({'bonus':b,'effort':e,'quality':q,'utility':utility,'actual_pay':w+b*e,'maximum_reserved_cost':reserve,'feasible':not diagnostics,'diagnostics':diagnostics})
    return {'candidates':rows,'eligible_winners':winner,'contracts':contracts}

def governance(row):
    members=row['members'];interested=row['interested'];present=row['present'];yes=row['yes'];no=row['no'];abstain=row['abstain'];quorum=row['quorum']
    for arr in (members,interested,present,yes,no,abstain):require(isinstance(arr,list) and all(isinstance(x,str) and x for x in arr) and len(set(arr))==len(arr),'distinct voter lists')
    require(set(interested)<=set(members) and set(present)<=set(members)-set(interested),'eligible attendance');require(set(yes)|set(no)|set(abstain)==set(present) and len(yes)+len(no)+len(abstain)==len(present),'complete partition of votes');require(type(quorum)is int and quorum>0,'positive quorum')
    needed=len(present)//2+1;return {'eligible_members':len(members)-len(interested),'present':len(present),'yes':len(yes),'required_yes':needed,'quorum':quorum,'approved':len(present)>=quorum and len(yes)>=needed,'scope':row['scope']}

def ledger(opening,events):
    from datetime import datetime
    C,S,L,D,E,cf,ef=(number(opening[k]) for k in ('cash','securities','loans','liabilities','equity','cash_floor','equity_floor'));require(min(C,S,L,D,E,cf,ef)>=0 and C+S+L==D+E,'opening identity/domain');history=[];approvals={};receipts=set();ids=set();previous=None;violations=[]
    for row in events:
        require(isinstance(row['id'],str) and row['id'] and row['id'] not in ids,'unique event');ids.add(row['id']);time=datetime.fromisoformat(row['time']);require(previous is None or time>=previous,'ordered events');previous=time;amount=number(row['amount']);require(amount>=0 and row['note'],'event amount/note');kind=row['kind'];status=row['status'];require(status in ('observed','forecast','proposed','missing'),'event status');require(kind in ('approval','expense','debt_payment','income','notification','completion'),'event kind');diagnostics=[];effect=False
        if status=='observed':
            if kind=='approval':approvals[row['id']]=amount
            elif kind=='expense':
                approval=row['approval']
                if approval not in approvals or approvals[approval]<amount:diagnostics.append('expense_without_sufficient_prior_approval')
                else:approvals[approval]-=amount
                C-=amount;E-=amount;effect=True
            elif kind=='debt_payment':require(amount<=D,'debt repayment exceeds debt');C-=amount;D-=amount;effect=True
            elif kind=='income':
                ref=row['reference'];require(isinstance(ref,str) and ref and ref not in receipts,'unique actual receipt');receipts.add(ref);C+=amount;E+=amount;effect=True
            elif kind=='notification':diagnostics.append('duplicate_receipt_notice' if row['reference']in receipts else 'unconfirmed_receipt_notice')
        if C<cf:diagnostics.append('cash_floor')
        if E<ef:diagnostics.append('equity_floor')
        require(C+S+L==D+E,'event balance identity');violations.extend({'event':row['id'],'reason':x} for x in diagnostics if x!='duplicate_receipt_notice')
        history.append({'id':row['id'],'status':status,'booked_cash_effect':effect,'cash':C,'assets':C+S+L,'liabilities':D,'equity':E,'diagnostics':diagnostics})
    return {'events':history,'closing':{'cash':C,'securities':S,'loans':L,'assets':C+S+L,'liabilities':D,'equity':E},'unique_receipts':len(receipts),'exceptions':violations}

def crisis(data,opening):
    deadline=number(data['deadline']);staff=number(data['staff']);require(min(deadline,staff)>=0,'crisis domain');actions=data['actions'];require([x['id'] for x in actions]==['H','M','B'],'crisis actions');releases=[]
    for release in data['releases']:
        minute,cash,equity=(number(release[k]) for k in ('minute','cash','equity'));require(min(minute,cash,equity)>=0 and isinstance(release['approved'],list) and set(release['approved'])<={'H','M','B'},'release domain');rows=[]
        for action in actions:
            cost,workers,duration,loss=(number(action[k]) for k in ('cost','staff','minutes','loss'));require(min(cost,workers,duration,loss)>=0 and type(action['requires_approval'])is bool,'action domain');why=[]
            if cash-cost<number(opening['cash_floor']):why.append('cash_floor')
            if equity-cost<number(opening['equity_floor']):why.append('equity_floor')
            if workers>staff:why.append('staff_capacity')
            if action['id']!='H' and minute+duration>deadline:why.append('setup_deadline')
            if action['requires_approval'] and action['id']not in release['approved']:why.append('approval_missing')
            rows.append({'action':action['id'],'loss':loss,'cash_after':cash-cost,'equity_after':equity-cost,'feasible':not why,'diagnostics':why})
        good=[x for x in rows if x['feasible']];releases.append({'release':release['id'],'actions':rows,'selected':min(good,key=lambda x:(x['loss'],x['action']))['action'] if good else None})
    require(len({x['release'] for x in releases})==len(releases),'release IDs');return releases

def run(data):
    require(isinstance(data,dict) and data.get('schema')=='v18-leadership-rehearsal-1','schema');domains=data['project_domains'];expected=['strategy_resources','people_organization','governance_academic','finance_operations','crisis_evidence_integration'];require([d['id'] for d in domains]==expected,'domains');tasks={}
    for d in domains:
        require(type(d['points'])is int and d['points']==20 and sum(d['tasks'].values())==20,'domain points')
        for k,v in d['tasks'].items():require(k in set(map(str,range(1,8))) and k not in tasks and type(v)is int and v>0,'task mapping');tasks[k]=v
    require(set(tasks)==set(map(str,range(1,8))),'seven tasks');require(data['fiction'] and all(data['policies'].values()) and all(data['feedback'].values()),'substantive records');records=data['actual_records'];require(len({x['id'] for x in records})==len(records),'record IDs')
    for row in records:require(row['status']in ('observed_in_fiction','missing','proposed') and row['text'],'evidence status/text')
    result={'schema':data['schema'],'academic':academic(data['academic']),'people':people(data),'governance':governance(data['vote']),'finance':ledger(data['finance_opening'],data['events']),'crisis':crisis(data['crisis'],data['finance_opening']),'evidence':{'observed_in_fiction':[x['id']for x in records if x['status']=='observed_in_fiction'],'missing':[x['id']for x in records if x['status']=='missing'],'proposed':[x['id']for x in records if x['status']=='proposed'],'actual_learner_achievement':'not supplied'},'scoring':{'domains':domains,'tasks':tasks,'total':sum(tasks.values())}}
    result=packed(result);json.dumps(result,allow_nan=False);return result

def guard_output(input_path, output_path):
    script = Path(__file__).resolve()
    protected = {script, input_path.resolve()}
    for directory in (script.parent, input_path.resolve().parent):
        protected.update(directory/name for name in NAMES)
    resolved = output_path.resolve()
    for path in protected:
        require(resolved != path.resolve(), 'output aliases a protected payload')
        if output_path.exists() and path.exists():
            require(not output_path.samefile(path), 'output hardlinks a protected payload')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path, default=Path(__file__).resolve().with_name(NAMES[0]))
    parser.add_argument('output', nargs='?', type=Path, default=Path(__file__).resolve().with_name('v18-assessment-output.json'))
    args = parser.parse_args()
    guard_output(args.input, args.output)
    result = run(strict_loads(args.input.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
