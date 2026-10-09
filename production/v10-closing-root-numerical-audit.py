"""Coordinator's separate cash, finite-law and quadrature checks; not a proof substitute."""
from fractions import Fraction as F
from itertools import combinations
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
comparisons=0


def eq(got,want,label):
    global comparisons
    comparisons+=1
    if isinstance(want,F):got=F(got)
    if got!=want:raise RuntimeError((label,got,want))


def near(got,want,label,tol=2e-8):
    global comparisons
    comparisons+=1
    if not math.isclose(got,want,rel_tol=tol,abs_tol=tol):raise RuntimeError((label,got,want))


def quadrature(fn,lo,hi,n=12000):
    step=(hi-lo)/n
    return step/3*math.fsum([fn(lo),fn(hi)]+[fn(lo+i*step)*(4 if i%2 else 2) for i in range(1,n)])


out09=json.loads((ROOT/'content/projects/v10-c09-output.json').read_text())
def call_integral(s=120,k=125,tau=.75,r=.03,q=.015,vol=.24):
    m=math.log(s)+(r-q-vol*vol/2)*tau;w=vol*math.sqrt(tau)
    threshold=(math.log(k)-m)/w
    return math.exp(-r*tau)*quadrature(lambda z:(math.exp(m+w*z)-k)*math.exp(-z*z/2)/math.sqrt(2*math.pi),threshold,12)
def five_point(fn,x,h):
    return (-fn(x+2*h)+8*fn(x+h)-8*fn(x-h)+fn(x-2*h))/(12*h)
price09=call_integral();delta09=five_point(lambda s:call_integral(s=s),120,.1)
gamma09=(-call_integral(s=120.2)+16*call_integral(s=120.1)-30*price09+16*call_integral(s=119.9)-call_integral(s=119.8))/(12*.1**2)
vega09=five_point(lambda sigma:call_integral(vol=sigma),.24,.0001)
theta09=-five_point(lambda tau:call_integral(tau=tau),.75,.0001)
for field,want in [('call',price09),('call_delta',delta09),('gamma',gamma09),('vega',vega09),('call_theta',theta09)]:
    near(out09['base'][field],want,'independent payoff-integral Greek '+field,2e-7)
near(out09['implied_volatility']['quote'],call_integral(vol=out09['implied_volatility']['sigma']),'IV price quadrature')
near(out09['portfolio']['vega_per_volatility_point'],-15*100*.01*vega09,'signed volatility-point exposure')
near(out09['shock']['spot_only_exact_change'],call_integral(s=123)-price09,'spot-only integral change')
near(out09['shock']['exact_repriced_change'],call_integral(s=123,vol=.255,tau=.75-1/252)-price09,'mixed-shock integral change')
near(out09['smile']['weighted_butterfly_costs'][0],-.5*3,'normalized butterfly cost')
# Independent quadrature-derived share schedule and a separate accumulated fee account.
hold=delta09;bank=price09-120*hold;fee_future=0.0;last=0.0
for date,stock,row in zip((.25,.5,.75),(126,113,130),out09['hedge']['ledger']):
    incoming=hold*math.exp(.015*(date-last));bank*=math.exp(.03*(date-last));wealth=incoming*stock+bank
    near(row['wealth_before_trade'],wealth,'independent funded wealth',5e-7)
    if date<.75:
        hold=five_point(lambda spot:call_integral(s=spot,tau=.75-date),stock,.05)
        trade=(hold-incoming)*stock;bank-=trade;fee_future+=abs(trade)*.002*math.exp(.03*(.75-date))
        near(row['stock_trade_cash'],trade,'independent delta trade',5e-7)
    else:
        near(row['ideal_terminal_error'],wealth-5,'funded terminal error',5e-7)
        near(row['funded_fee_terminal_error'],wealth-5-fee_future,'fees accumulated at payment dates',5e-7)
    last=date
near(out09['variance_account']['total_discounted_error'],.5*(50*(.25**2-.3**2)+200*(.25**2-.2**2)),'discounted cash-gamma worksheet')
eq(F('0.6')*17+F('0.4')*5-13,F('-.8'),'uneven-strike exercise')
near((3*1e-6/.003)**(1/3),.1,'optimal finite-difference bump')
near(.003*.1**2/6+1e-6/.1,.000015,'delta error budget')


out10=json.loads((ROOT/'content/projects/v10-c10-output.json').read_text())
s,k,r,q,sigma,t=96,100,.04,.015,.25,1.5
discount=math.exp(-r*t);mu=math.log(s)+(r-q-sigma*sigma/2)*t;width=sigma*math.sqrt(t)
cut=(math.log(k)-mu)/width
def density(z):return math.exp(-z*z/2)/math.sqrt(2*math.pi)
def terminal(z):return math.exp(mu+width*z)
put=quadrature(lambda z:discount*(k-terminal(z))*density(z),-12,cut)
second=quadrature(lambda z:(discount*(k-terminal(z)))**2*density(z),-12,cut)
cross=quadrature(lambda z:discount**2*(k-terminal(z))*terminal(z)*density(z),-12,cut)
stockmean=s*math.exp(-q*t)
stockvar=stockmean**2*math.expm1(sigma*sigma*t)
var=second-put*put;cov=cross-put*stockmean
near(out10['analytic']['european_put'],put,'Gaussian payoff quadrature')
near(out10['analytic']['european_call'],put+s*math.exp(-q*t)-k*discount,'dividend parity')
analytic=out10['monte_carlo']['ideal_analytic']
for field,want in [('put_mean',put),('put_variance',var),('discounted_stock_variance',stockvar),('put_stock_covariance',cov),
                   ('discounted_stock_mean',stockmean),('optimal_beta',cov/stockvar),('fixed_control_variance',var+.35**2*stockvar+.7*cov)]:
    near(analytic[field],want,'quadrature '+field)
for tree in out10['tree']:
    n=tree['steps'];dt=t/n;jump=sigma*math.sqrt(dt)
    probability=(math.exp((r-q)*dt)-math.exp(-jump))/(math.exp(jump)-math.exp(-jump))
    expected=math.exp(-r*t)*math.fsum(math.comb(n,j)*probability**j*(1-probability)**(n-j)*max(k-s*math.exp((2*j-n)*jump),0) for j in range(n+1))
    near(tree['european_put'],expected,'terminal binomial expectation')
    eq(tree['european_put']<=tree['bermudan_put']+1e-10<=tree['all_grid_dates_put']+2e-10,True,'same-tree exercise inclusion')
# Exact original finite tree and stencil exercises, independent of author routines.
p=F(8,15);R=F(26,25)
for strike,euro,amer in [(84,F(12845,1521),F(15050,1521)),(88,F(16870,1521),F(19180,1521))]:
    payments=[max(F(0),strike-stock) for stock in (F(256,5),F(80),F(125))]
    continuation=[((1-p)*payments[j]+p*payments[j+1])/R for j in range(2)]
    ev=((1-p)*continuation[0]+p*continuation[1])/R
    av=max(F(strike-80),((1-p)*max(F(strike-64),continuation[0])+p*max(F(0),continuation[1]))/R)
    eq(ev,euro,'exact European tree');eq(av,amer,'exact stopping value')
for step,want in [(F(1,5),(F(37,100),F(1,5),F(43,100))),(F(3,10),(F(111,200),F(-1,5),F(129,200)))]:
    a,b,h=F(1,50),F(3,100),F(1,10)
    eq((step*(a/h**2-b/(2*h)),1-2*a*step/h**2,step*(a/h**2+b/(2*h))),want,'positive/negative stencil')
eq(F(4,10000)+F(1,1000)*3/2+F(1,50)*F(2,100)**2*20/12+F(1,100)*F(2,100)**2*5/6,F(23,12000),'global residual bound')
eq(math.ceil(2500*math.log(40)/.5),18445,'Hoeffding sample plan')
eq(math.ceil((1.959963984540054*8/.5)**2),984,'normal sample plan')

out11=json.loads((ROOT/'content/projects/v10-c11-output.json').read_text())
stocks=[F(60),F(100),F(100),F(140)];D=F(25,26);forward=F(104)
vertices=[]
for i,j in combinations(range(4),2):
    if stocks[i]==stocks[j]:continue
    w=(stocks[j]-forward)/(stocks[j]-stocks[i])
    if 0<=w<=1:
        v=[F(0)]*4;v[i]=w;v[j]=1-w;vertices.append(v)
eq({tuple(map(F,row)) for row in out11['closed_pricing_vertices']},{tuple(row) for row in vertices},'finite calibrated vertices')
claims={'call':list(map(F,[0,10,10,50])),'up_out':list(map(F,[0,10,0,0])),
        'terminal_only_up_out':list(map(F,[0,10,10,0])),'asian':list(map(F,[0,0,20,30]))}
annuity=[F(50,101),F(50,51)+F(50,103),F(50,51)+D,F(50,51)+D]
protection=[F(75,2)*F(50,51),F(50)*D,F(0),F(0)]
net=[loss-3*ann for loss,ann in zip(protection,annuity)]
claims['credit_net']=[pv/D for pv in net];claims['stock']=stocks
for name,payoff in claims.items():
    expected=[D*sum((w*h for w,h in zip(vertex,payoff)),F(0)) for vertex in vertices]
    record=out11['claims'][name]
    eq(record['lower'],min(expected),'finite lower '+name)
    eq(record['upper'],max(expected),'finite upper '+name)
    for key,target,side in [('subhedge',min(expected),-1),('superhedge',max(expected),1)]:
        hedge=record[key];shares=F(hedge['stock_units']);cash=F(hedge['terminal_cash'])
        eq(100*shares+D*cash,target,'hedge attained cost '+name)
        for stock,h in zip(stocks,payoff):eq(side*(shares*stock+cash-h)>=0,True,'statewise hedge inequality '+name)
    for quote in out11['quotes']:
        weights=list(map(F,quote['probabilities']))
        eq(quote['prices'][name],D*sum((w*h for w,h in zip(weights,payoff)),F(0)),'original state cash '+name)
for row,a,l in zip(out11['credit_state_ledgers'],annuity,protection):
    eq(row['unit_annuity_pv'],a,'dated accrued premium');eq(row['protection_pv'],l,'dated seller protection')
    eq(row['net_pv'],l-3*a,'credit net cash')
spreads=[sum((w*l for w,l in zip(v,protection)),F(0))/(100*sum((w*a for w,a in zip(v,annuity)),F(0))) for v in vertices]
eq(out11['fair_spread_bounds']['lower'],min(spreads),'spread lower');eq(out11['fair_spread_bounds']['upper'],max(spreads),'spread upper')
eq(max(spreads),F(47277,165362),'published spread anchor')
eq((F(140)-forward)/40*D,F(45,52),'correct digital upper endpoint')
eq([(140-x)/40-h for x,h in zip((60,100,140),(0,1,0))],[2.0,0.0,0.0],'digital endpoint arbitrage residual')
for jump,expected in [(F(-20),F(56,5)),(F(50),F(175,2))]:
    eq(((100+jump)**3-100**3)/10000-3*jump,expected,'exact cubic jump remainder')
eq(F('.24')**2*F(-8)**2,F('3.6864'),'orthogonal factor exposure')
near(.5*math.erfc(1/math.sqrt(2)),.15865525393145707,'factor tilt digital')

report={'batch':'v10-closing','status':'passed','comparisons':comparisons,
        'count_definition':'Executed coordinator comparisons only; no author or peer counts included.',
        'independent_mc_moments':{'put':put,'variance_put':var,'variance_discounted_stock':stockvar,'covariance_put_stock':cov,'fixed_control_variance':var+.35**2*stockvar+.7*cov},
        'groups':['payoff-integral finite-difference Greeks, inversion, shocks and funded fee ledger','direct payoff/moment quadrature and terminal tree sums','exact finite stopping, stencil and sampling exercises',
                  'finite calibrated laws, original exotic and dated-credit cash expectations','corrected digital interval, jump residual and orthogonal exposure'],
        'limitations':'Separate coordinator arithmetic; final artifact hashes, full prompt/proof/source review and peer gates are recorded separately. No empirical validity or UI QA claim.'}
if __name__=='__main__':print(json.dumps(report,indent=2))
