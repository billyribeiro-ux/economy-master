"""Separately authored exact-prompt audit for Volume 10 Form A.

No author checker, chapter model or saved output is a numerical oracle here.
Cash stripping, integrated density moments, rational Snell envelopes, a finite
control law and state-price/hedge constraints are reconstructed independently.
check() is quiet, strict-JSON-safe and portable with the four author files and
the two peer files. Proof hypotheses and source scope are recorded separately.
"""
from fractions import Fraction as F
import hashlib
from html.parser import HTMLParser
from itertools import product
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = "content/reviews/v10-exam-a-peer.json"
SELF = "scripts/check_v10_exam_a_peer.py"
AUTHOR_PATHS = (
    "content/assessments/parts/v10-exam-a.html", "scripts/check_v10_exam_a.py",
    "content/reviews/v10-exam-a-author.json", "content/reviews/v10-exam-a-sources.json",
)
POINTS = {f"v10-a-q{q}{letter}": score
          for q, scores in enumerate(((5, 5, 5, 5), (6, 3, 6, 5), (6, 6, 8),
                                      (6, 4, 6, 4), (5, 6, 3, 6)), 1)
          for letter, score in zip("abcd", scores)}


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.interventions = []

    def eq(self, got, want, label):
        self.comparisons += 1
        if got != want:
            raise RuntimeError(f"{label}: {got!r} != {want!r}")

    def ok(self, value, label):
        self.eq(bool(value), True, label)

    def near(self, got, want, label, tol=1e-10):
        self.ok(math.isfinite(float(got)) and abs(float(got)-float(want)) <= tol,
                f"{label}: {got!r} versus {want!r}")


def dot(x, y):
    if len(x) != len(y):
        raise ValueError("Same dated vector length required")
    return sum((v*w for v, w in zip(x, y)), F(0))


def integrate_exp_series(coefficient, horizon):
    """Integrate the exponential's power series term by term, not its closed form.

    Forty rational terms give error below 1e-70 for the bounded audit inputs.
    This is independent of the author's composite-Simpson reconstruction.
    """
    if abs(coefficient*horizon) > 1 or horizon <= 0:
        raise ValueError("Bounded integrated series domain required")
    power = F(1)
    total = horizon
    for n in range(1, 40):
        power *= coefficient*horizon/n
        total += horizon*power/(n+1)
    return total


def american_tree(strike=F(110), gross=F(21, 20)):
    """Rational Snell envelope with independently reconstructed node bank cash."""
    down, up, initial = F(4, 5), F(6, 5), F(100)
    if not down < gross < up:
        raise ValueError("Every possible branch needs a positive state price")
    p = (gross-down)/(up-down)
    stocks = [[initial * up**j * down**(n-j) for j in range(n+1)] for n in range(3)]
    intrinsic = [[max(strike-s, F(0)) for s in row] for row in stocks]
    values = [[], [], intrinsic[-1][:]]
    continuation = [[], []]
    for n in (1, 0):
        continuation[n] = [((1-p)*values[n+1][j]+p*values[n+1][j+1])/gross
                           for j in range(n+1)]
        values[n] = [max(stop, wait) for stop, wait in zip(intrinsic[n], continuation[n])]
    return stocks, intrinsic, values, continuation, p


def two_state_holdings(sd, su, vd, vu, gross):
    # Difference quotient determines stock; either cash equation determines bank.
    if sd >= su or gross <= 0:
        raise ValueError("Distinct states and positive bank accumulation required")
    shares = (vu-vd)/(su-sd)
    bank = (vd-shares*sd)/gross
    return shares, bank


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links = [], [], []
        self.points, self.domains, self.solutions = {}, {}, {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("html", "head", "body", "h1", "script"):
            raise ValueError("Only a static assessment fragment is allowed")
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if "data-points" in attrs:
            key = attrs.get("id")
            if tag != "li" or not key or key in self.points:
                raise ValueError("Scored prompt must be a unique list item")
            self.points[key] = int(attrs["data-points"])
            self.domains[key] = attrs.get("data-domain")
        if "data-solution-for" in attrs:
            self.current = attrs["data-solution-for"]
            if tag != "li" or self.current in self.solutions:
                raise ValueError("One semantic solution item required per prompt")
            self.solutions[self.current] = []
        if tag not in ("br", "hr", "img", "meta", "link", "input"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise ValueError("Unbalanced element " + tag)
        self.stack.pop()
        if tag == "li":
            self.current = None

    def handle_data(self, data):
        if self.current:
            self.solutions[self.current].append(data)


def check():
    a = Audit()
    # D1: build unit zeros as signed strips of the traded bonds.
    prices = tuple(map(F, ("98", "100.744", "101.955")))
    zero_half = (F(1, 100), F(0), F(0))
    zero_onehalf = (-4*zero_half[0]/104, F(1, 104), F(0))
    zero_twohalf = tuple((-5*zero_half[i]-5*zero_onehalf[i]+(1 if i==2 else 0))/105
                        for i in range(3))
    cash_rows = ((100, 4, 5), (0, 104, 5), (0, 0, 105))
    zeros = (zero_half, zero_onehalf, zero_twohalf)
    for j, holdings in enumerate(zeros):
        a.eq(tuple(dot(row, holdings) for row in cash_rows),
             tuple(int(i==j) for i in range(3)), "D1 actual unit-zero strip cash")
    ds = tuple(dot(h, prices) for h in zeros)
    a.eq(ds, (F(".98"), F(".931"), F(".88")), "D1 independently traded zero prices")
    accrued = 5*F(1, 2)
    a.eq((accrued, prices[2]-accrued), (F("2.5"), F("99.455")), "D1 clean/dirty elapsed accrual")
    liability = 100*ds[1]
    # Barycentric duration weights: t_mid lies halfway between the two hedge dates.
    dollar_early = liability*(F(5,2)-F(3,2))/(F(5,2)-F(1,2))
    dollar_late = liability-dollar_early
    hedge = (dollar_early/ds[0], dollar_late/ds[2])
    a.eq(hedge, (F("47.5"), F(4655,88)), "D1 independent duration barycentric holdings")
    a.eq(dollar_early+dollar_late, liability, "D1 present-value match")
    a.eq(F(1,2)*dollar_early+F(5,2)*dollar_late, F(3,2)*liability, "D1 derivative match")
    local = liability*F(3,2)*F(".01")
    exact = float(liability)*(-math.expm1(-.015))
    a.eq(local, F("1.3965"), "D1 local key shock")
    a.near(exact, 1.3860784229548675, "D1 exact liability-only shock")
    for shock in (-.03, .01, .04):
        parallel_surplus = float(liability)*math.exp(-1.5*shock)*(math.cosh(shock)-1)
        direct = (float(dollar_early)*math.exp(-.5*shock)
                  + float(dollar_late)*math.exp(-2.5*shock)
                  - float(liability)*math.exp(-1.5*shock))
        a.near(parallel_surplus, direct, "D1 exact parallel convexity identity")
        a.ok(parallel_surplus > 0, "D1 first-order duration match leaves curvature")
    dl, dh = F(".99"), F(".91")
    rl, rh = 1/dl-1, 1/dh-1
    forward, qmean, pmean = 1/((dl+dh)/2)-1, (rl+rh)/2, (3*rl+rh)/4
    a.eq(ds[0]*(dl+dh)/2, ds[1], "D1 finite rate model fits initial curve")
    a.eq((forward,qmean,pmean), (F(1,19),F(491,9009),F(97,3003)), "D1 forward and separate rate means")
    a.eq(qmean-forward, (dl-dh)**2/(2*dl*dh*(dl+dh)), "D1 Jensen gap closed exact identity")
    a.near(forward-qmean, -.00186947555368608, "D1 nonlinear component")
    a.near(qmean-pmean, .0222000222000222, "D1 measure component")
    a.near(forward-pmean, .020330546646336, "D1 complete forecast decomposition")
    a.ok((rl+3*rh)/4 != pmean, "D1 physical law intervention leaves Q curve unchanged")
    a.interventions += ["D1 traded coupon stripping and exact parallel-curvature repricing",
                        "D1 inverse-discount Jensen gap and independent physical-law change"]

    # D2: integrate default cash by rational power moments rather than quadrature.
    lam, horizon, recovery = F(".06"), F(2), F(50)
    def credit(rate):
        survival = 100*math.exp(-float((rate+lam)*horizon))
        immediate = survival+float(recovery*lam*integrate_exp_series(-(rate+lam), horizon))
        delayed = survival+math.exp(-float(rate*horizon))*float(recovery*lam*integrate_exp_series(-lam,horizon))
        return immediate, delayed
    immediate, delayed = credit(F(".04"))
    a.near(immediate, 87.31115271545872, "D2 immediate recovery by density moments")
    a.near(delayed, 87.09235497323088, "D2 maturity recovery by density moments")
    a.near(immediate-delayed, .2187977422278351, "D2 timing premium")
    mass = float(lam*integrate_exp_series(-lam,horizon))
    a.near(mass, .11307956328284252, "D2 integrated first-default probability")
    a.near(mass+math.exp(-.12), 1, "D2 default/survival path partition")
    for rate in (F("-.04"),F(0),F(".04")):
        vnow, vlater = credit(rate)
        a.eq((vnow>vlater)-(vnow<vlater), (rate>0)-(rate<0), "D2 recovery timing sign follows dated discounting")
    discounts = (F(1), F(".96"), F(".9"))
    floats = tuple(100*(discounts[i-1]/discounts[i]-1) for i in (1,2))
    float_pvs = tuple(floats[i]*discounts[i+1] for i in range(2))
    net_pvs = tuple((floats[i]-5)*discounts[i+1] for i in range(2))
    a.eq(float_pvs, (F(4),F(6)), "D2 rolling deposit coupon strips")
    a.eq(net_pvs, (F("-.8"),F("1.5")), "D2 actual payer coupon present values")
    annuity = sum(discounts[1:])
    a.eq((annuity, sum(float_pvs)/(100*annuity), sum(net_pvs)), (F("1.86"),F(5,93),F(".7")), "D2 swap annuity/par/existing value")
    # Basis spread changes projected coupons while preserving the discount prices.
    shifted = sum((floats[i]+F(".2"))*discounts[i+1] for i in range(2))
    a.eq(shifted-sum(float_pvs), F(".372"), "D2 unrelated index cannot inherit telescope")
    c_rate, b_rate = F("1.01"), F("1.06")
    c1, b1 = 12*c_rate, 12*b_rate
    release = c1-8
    b_after = b1-release
    c2, b2 = 8*c_rate, b_after*b_rate
    a.eq((c1,b1,release,b_after,c2,b2,c2-b2),
         tuple(map(F,("12.12","12.72","4.12","8.6","8.08","9.116","-1.036"))), "D2 collateral/debt cash reconciliation")
    # Independent funding-spread integral: first-period loss earns the debt rate,
    # then the remaining eight units incur the second-period spread.
    a.eq(12*(c_rate-b_rate)*b_rate+8*(c_rate-b_rate), c2-b2, "D2 funding-spread cohort decomposition")
    a.eq(12*c_rate*c_rate-12*b_rate*b_rate, F("-1.242"), "D2 delaying collateral release changes financing cost")
    a.interventions += ["D2 positive/zero/negative-rate recovery-date comparison",
                        "D2 projected-index basis and delayed collateral release"]

    # D3: a rational Snell envelope, with independently funded node cash.
    stocks, intrinsic, values, continuation, p = american_tree()
    gross = F(21,20)
    a.eq(p, F(5,8), "D3 stock-implied pricing probability")
    a.eq(stocks[-1], [64,96,144], "D3 terminal stocks")
    a.eq(intrinsic[-1], [46,14,0], "D3 terminal claim cash")
    a.eq(continuation[1], [F(520,21),F(5)], "D3 date-one continuation")
    a.eq(values[1], [F(30),F(5)], "D3 current-information exercise values")
    american = values[0][0]
    terminal_probabilities = ((1-p)**2, 2*p*(1-p), p*p)
    european = dot(intrinsic[-1],terminal_probabilities)/gross**2
    a.eq((american,european,american-european), (F(575,42),F(3475,294),F(275,147)), "D3 values under the same finite law")
    shares, bank = two_state_holdings(F(80),F(120),values[1][0],values[1][1],gross)
    next_shares, next_bank = two_state_holdings(F(96),F(144),F(14),F(0),gross)
    a.eq((shares,bank,next_shares,next_bank), (F(-5,8),F(1600,21),F(-7,24),F(40)), "D3 secant state hedges")
    a.eq(shares*100+bank,american,"D3 initial financed cost")
    a.eq((next_shares-shares)*120,40,"D3 actual up-node stock purchase")
    a.eq(bank*gross-40,next_bank,"D3 up-node cash after trading")
    a.eq(bank*gross+shares*80,30,"D3 down-node close and exercise")
    for s,payoff in ((F(96),F(14)),(F(144),F(0))):
        a.eq(next_shares*s+next_bank*gross,payoff,"D3 funded terminal up-branch payoff")
    # Explicit anticipative choice on four histories is a different information set.
    foresight=F(0)
    for first, second in product((False,True),repeat=2):
        s1=100*(F(6,5) if first else F(4,5));s2=s1*(F(6,5) if second else F(4,5))
        prob=(p if first else 1-p)*(p if second else 1-p)
        foresight += prob*max(F(10),max(110-s1,0)/gross,max(110-s2,0)/gross**2)
    a.ok(foresight>american,"D3 pathwise hindsight is not an adapted exercise policy")
    # A low strike removes the profitable early-down exercise branch in this tree.
    _, low_intrinsic, low_values, _, low_p=american_tree(F(60))
    a.eq(low_values[0][0],0,"D3 zero-payoff strike intervention")
    _, _, negative_rate_values, _, _=american_tree(F(110),F(".99"))
    a.ok(negative_rate_values[0][0]>american,"D3 changed bank return changes pricing and exercise")
    # Local PDE proof is also checked by algebraic substitution for power marks.
    for exponent in (-1,0,1,2):
        r,q,sigma,t,s=F(".03"),F(".01"),F(".2"),F(".4"),F(100)
        value=F(7);delta=exponent*value/s;gamma=exponent*(exponent-1)*value/s**2
        vt=r*value-(r-q)*s*delta-sigma*sigma*s*s*gamma/2
        for mu in (F(".01"),F(".09")):
            for wealth in (value,value+F(2)):
                mark_drift=vt+mu*s*delta+sigma*sigma*s*s*gamma/2
                gains_drift=delta*(mu+q)*s+r*(wealth-delta*s)
                a.eq(gains_drift-mark_drift,r*(wealth-value),"D3 funded tracking-error ODE")
    a.interventions += ["D3 adapted Snell exercise versus inadmissible hindsight",
                        "D3 strike and negative-bank-return changes with explicit node funding",
                        "D3 physical drift and nonzero initial-error PDE cancellation"]

    # D4: exact exposure geometry and full multidimensional remainder order.
    ga,va,gc,vc=F(".03"),F(30),F(".025"),F(50)
    a.eq(va/ga,1000,"D4 fixed-maturity gamma-vega relation")
    a.eq(F(20)/F(".02"),1000,"D4 second column identical risk direction")
    a.ok(F(5000)/4 != 1000,"D4 desired risk direction is outside A/B span")
    determinant=ga*vc-gc*va
    x=(4*vc-gc*5000)/determinant;y=(ga*5000-4*va)/determinant
    a.eq((x,y),(100,40),"D4 independent Cramer exposure solution")
    additional=-(-70+F(".5")*x+F(".4")*y+10)
    a.eq(additional,-6,"D4 additional stock includes existing shares")
    # Choose all omitted Hessian entries nonzero and compare exact quadratic moves.
    hessian=((F(2),F(3),F(5)),(F(3),F(7),F(11)),(F(5),F(11),F(13)))
    residuals=[]
    for eps in (F(1,10),F(1,20),F(1,40)):
        h=(eps,2*eps,3*eps)  # t, S, sigma
        full=sum(h[i]*hessian[i][j]*h[j]/2 for i in range(3) for j in range(3))
        retained=hessian[1][1]*h[1]**2/2
        omitted=hessian[0][0]*h[0]**2/2+hessian[2][2]*h[2]**2/2
        omitted+=hessian[0][1]*h[0]*h[1]+hessian[0][2]*h[0]*h[2]+hessian[1][2]*h[1]*h[2]
        a.eq(full-retained,omitted,"D4 all five omitted Hessian terms")
        residuals.append(omitted)
    a.eq(residuals[0]/residuals[1],4,"D4 omitted joint error is quadratic")
    a.eq(residuals[1]/residuals[2],4,"D4 quadratic error cannot become a uniform cubic bound")
    weights=(F(".2"),F(".65"),F(".1"))
    # The induced infinity norm is the maximum over extreme signed triples.
    a.eq(max(abs(dot(weights,triple)) for triple in product((-1,1),repeat=3)),F(".95"),"D4 exact induced stencil norm")
    a.ok(all(dot(weights,triple)>=0 for triple in product((0,1),repeat=3)),"D4 positive cone preserved")
    rho=F(".95");defect=F(".001");initial=F(".04");boundary=F(".01")
    bound=initial
    for n in range(1,21):
        bound=max(boundary,rho*bound+defect)
        finite_sum=rho**n*initial+defect*sum(rho**k for k in range(n))
        a.eq(bound,finite_sum,"D4 discrete variation-of-constants error bound")
    a.near(bound,.027169718448,"D4 printed 20-step bound",6e-13)
    ak=(weights[0]+weights[2])/2;bk=(weights[2]-weights[0])/2;rk=1-sum(weights)
    halved=(4*ak-2*bk,1-8*ak-rk,4*ak+2*bk)
    a.eq(halved,(F(".7"),F("-.25"),F(".5")),"D4 actual spatial refinement coefficients")
    a.eq(dot(halved,(0,1,0)),F("-.25"),"D4 concrete positivity failure")
    a.eq(max(abs(dot(halved,z)) for z in product((-1,1),repeat=3)),F("1.45"),"D4 true max norm after spatial refinement")
    # Independent rational finite law: X takes -6/0/6 with variance9; an
    # independent error takes -6/0/6 with variance12; Y=7+(2/3)X+error.
    atoms=[]
    for control,pc in zip((-6,0,6),(F(1,8),F(3,4),F(1,8))):
        for noise,pn in zip((-6,0,6),(F(1,6),F(2,3),F(1,6))):
            atoms.append((pc*pn,F(control),7+F(2,3)*control+noise))
    mx=sum(prob*x for prob,x,y in atoms);my=sum(prob*y for prob,x,y in atoms)
    vx=sum(prob*(x-mx)**2 for prob,x,y in atoms);vy=sum(prob*(y-my)**2 for prob,x,y in atoms)
    cov=sum(prob*(x-mx)*(y-my) for prob,x,y in atoms)
    a.eq((mx,my,vx,vy,cov),(0,7,9,16,6),"D4 independent rational joint-control law")
    beta=cov/vx
    vz=sum(prob*((y-beta*x)-my)**2 for prob,x,y in atoms)
    a.eq((beta,vz),(F(2,3),12),"D4 control optimizer and observation variance")
    for other_beta in (F(0),F(1,3),F(1),F(2)):
        other_var=sum(prob*((y-other_beta*x)-my)**2 for prob,x,y in atoms)
        a.eq(other_var-vz,9*(other_beta-beta)**2,"D4 variance penalty from coefficient perturbation")
    a.near(math.sqrt(float(vz)/400),.17320508075688773,"D4 path-mean standard error")
    a.near(1.96*math.sqrt(float(vz)/400),.3394819582834999,"D4 approximate controlled half-width")
    a.near(1.96*math.sqrt(float(vy)/400),.392,"D4 raw half-width")
    # With two evaluation paths, selecting beta_hat=Xbar creates bias -Var(X)/2.
    chosen_mean=F(0)
    for (pa,xa,ya),(pb,xb,yb) in product(atoms,repeat=2):
        xbar=(xa+xb)/2;ybar=(ya+yb)/2
        chosen_mean+=pa*pb*(ybar-xbar*xbar)
    a.eq(chosen_mean-my,-vx/2,"D4 same-evaluation coefficient selection bias")
    a.interventions += ["D4 full mixed Hessian and exact positive-cone/operator-norm checks",
                        "D4 fixed-time spatial refinement and its amplification witness",
                        "D4 rational joint-control law, coefficient perturbations and evaluation-selection bias"]

    # D5: solve the probability geometry using its free tail mass instead of p1.
    stock=(F(70),F(100),F(160));payoff=(F(0),F(10),F(10));discount=F(".95")
    for tail in (F(1,1000),F(1,10),F(9,38),F(1,3)-F(1,1000)):
        probs=(2*tail,1-3*tail,tail)
        a.ok(all(p>0 for p in probs),"D5 strict calibrated support")
        a.eq((sum(probs),discount*dot(probs,stock)),(1,95),"D5 bank/stock calibration")
        a.eq(discount*dot(probs,payoff),F("9.5")*(1-2*tail),"D5 independent tail-parameter value")
    low,high=F(19,6),F(19,2)
    lower_cash=tuple((s-70)/9 for s in stock);upper_cash=(F(10),)*3
    a.eq(lower_cash,(0,F(10,3),10),"D5 lower attainable stock/bank cash")
    a.ok(all(l<=g<=u for l,g,u in zip(lower_cash,payoff,upper_cash)),"D5 statewise hedge envelope")
    a.eq((F(95,9)-F(70,9)*discount,10*discount),(low,high),"D5 limiting hedge costs")
    a.eq(tuple(g-l for g,l in zip(payoff,lower_cash)),(0,F(20,3),0),"D5 lower endpoint zero-cost positive cash")
    a.eq(tuple(u-g for u,g in zip(upper_cash,payoff)),(10,0,0),"D5 upper endpoint zero-cost positive cash")
    for quote in (low+F(1,1000),F(5),high-F(1,1000)):
        tail=(1-quote/F("9.5"))/2
        probs=(2*tail,1-3*tail,tail)
        a.ok(all(p>0 for p in probs),"D5 every proposed interior price has positive extension")
        a.eq(discount*dot(probs,payoff),quote,"D5 full interval interior reproduction")
    a.eq(discount*sum(stock)/3,F("104.5"),"D5 physical equal weights fail market calibration")
    jump=F(60);s=F(100)
    change=((s+jump)**2-s*s)/100;delta_gain=2*s/100*jump
    a.eq((change,delta_gain,delta_gain-change),(156,120,-36),"D5 finite-jump marked residual")
    for moved in (F(-40),F(20),F(60)):
        a.eq(((s+moved)**2-s*s)/100-2*s/100*moved,moved*moved/100,"D5 positive nonlinear jump remainder for either jump sign")
    discrepancy=abs(F("5.006")-5);unit_up=high-5
    a.ok(discrepancy<=F(".010"),"D5 numerical gate independently passes")
    a.eq(unit_up*20,90,"D5 model-family liability gate independently fails")
    passing=[n for n in range(31) if n*unit_up<=60]
    a.eq(max(passing),13,"D5 exhaustive whole-position permission")
    a.eq((13*unit_up,14*unit_up),(F("58.5"),63),"D5 quantity boundary evidence")
    a.ok(20<=30 and 20 not in passing,"D5 count-only exception cannot waive liability gate")
    a.interventions += ["D5 strictly positive tail-family extensions and excluded endpoint cash",
                        "D5 jump direction changes and whole-position policy boundary"]

    # Structure, scoring/source scope and immutable reviewed payload bindings.
    f=Fragment();f.feed((ROOT/AUTHOR_PATHS[0]).read_text());f.close()
    a.eq(f.stack,[],"complete balanced fragment")
    a.eq(len(f.ids),len(set(f.ids)),"unique Form A IDs")
    a.eq(f.points,POINTS,"all nineteen exact scored prompts")
    a.eq(set(f.solutions),set(POINTS),"all nineteen prompt-specific complete solutions")
    a.eq(sum(f.points.values()),100,"total examination points")
    for q in range(1,6):
        a.eq(sum(v for k,v in f.points.items() if f.domains[k]==f"D{q}"),20,"essential domain floor basis")
    for key,fragments in f.solutions.items():
        a.ok(f"Scoring, {POINTS[key]}:" in "".join(fragments),"solution rubric total "+key)
    for chapter in range(1,13):
        a.ok(f"v10-c{chapter:02}.html" in f.links,"taught method route "+str(chapter))
    sources=json.loads((ROOT/AUTHOR_PATHS[3]).read_text())
    source_ids={row["id"] for row in sources["reused_sources"]}
    a.eq(source_ids,{url.split("#",1)[1] for url in f.links if url.startswith("sources.html#")},"exact twelve cited method records")
    a.eq(len(source_ids),12,"twelve scoped reused records")
    a.eq(sources["proposals"],[],"no unreviewed source expansion")
    for source in sources["reused_sources"]:
        a.ok(source["checked"]=="2026-10-09" and source["reused_body_scope"]
             and source["url"].startswith("https://"),"source body provenance "+source["id"])
    review=json.loads((ROOT/REVIEW).read_text())
    a.eq(set(review["reviewed_sha256"]),set(AUTHOR_PATHS),"exact four author payloads bound")
    for path,digest in review["reviewed_sha256"].items():
        a.eq(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,"frozen reviewed payload "+path)
    a.eq(hashlib.sha256((ROOT/SELF).read_bytes()).hexdigest(),review["peer_checker_sha256"],"own checker binding")
    a.eq({row["prompt"] for row in review["prompt_audit"]},set(POINTS),"independent review covers every exact prompt")
    for row in review["prompt_audit"]:
        a.eq(sum(row["scoring"]),POINTS[row["prompt"]],"independently audited rubric "+row["prompt"])
    result={"component":"v10-exam-a-peer","status":"pass","comparisons":a.comparisons,
            "scored_subparts":19,"points":100,"domains":{f"D{i}":20 for i in range(1,6)},
            "financial_interventions":len(a.interventions),"interventions":a.interventions,
            "author_payload_hashes_checked":4,"peer_checker_hashes_checked":1,
            "limits":"Separate machine-assisted peer audit, not human academic certification, statistical equating or proof of CLT coverage."}
    json.dumps(result,allow_nan=False)
    return result


if __name__=="__main__":
    print(json.dumps(check(),indent=2,allow_nan=False))
