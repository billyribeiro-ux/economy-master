"""Independent stock, value-equation and dynamics audit of synthetic labor models.

Standard library only; exact fractions where possible. The equilibrium root is
bracketed independently, then checked against all original value equations.
"""
from fractions import Fraction as F
from math import isclose, sqrt
from pathlib import Path
import json

from check_v06_c01 import Chapter

ROOT = Path(__file__).resolve().parents[1]


def need(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b, label):
    need(isclose(a, b, rel_tol=1e-10, abs_tol=1e-10), label)


def stock_ledger(opening, rows):
    need(len(opening) == len(rows) == 3, 'three states')
    need(all(len(row) == 3 for row in rows), 'three destinations')
    need(all(v >= 0 for row in rows for v in row), 'nonnegative flows')
    need(all(sum(row) == n for row, n in zip(rows, opening)), 'row totals')
    ending = tuple(sum(row[j] for row in rows) for j in range(3))
    need(sum(ending) == sum(opening), 'population conservation')
    need(ending[1]-opening[1] == rows[0][1]+rows[2][1]-rows[1][0]-rows[1][2],
         'unemployment inflow/outflow')
    return ending


def transition(u, s, f):
    need(all(0 <= x <= 1 for x in (u, s, f)), 'probability bounds')
    return s*(1-u)+(1-f)*u


def bisect_increasing(fn, lo, hi):
    need(fn(lo) <= 0 <= fn(hi), 'root bracket')
    for _ in range(90):
        mid = (lo+hi)/2
        if fn(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo+hi)/2


def search_equilibrium(mu=.5, cost=8/3):
    beta, s, eta, z, b = .8, .25, .5, 12., 4.
    a = 1-beta*(1-s)
    # Independent zero-profit residual, evaluated from values rather than the
    # polynomial closed form printed in the manuscript.
    def excess_cost(x):
        f, h = mu*x, mu/x
        j = (1-eta)*(z-b)/(a+eta*beta*f)
        return cost-beta*h*j
    need(0 < mu <= 1, 'matching efficiency domain')
    lo, hi = mu, 1/mu
    if excess_cost(lo) > 1e-12 or excess_cost(hi) < -1e-12:
        raise ValueError('no root in the maintained probability domain')
    x = bisect_increasing(excess_cost, lo, hi)
    f, h = mu*x, mu/x
    j = cost/(beta*h)
    w = z-a*j
    surplus = (w-b)/(a+beta*f)
    vu = (b+beta*f*surplus)/(1-beta)
    ve = vu+surplus
    u = s/(s+f)
    close(ve, w+beta*((1-s)*ve+s*vu), 'search employed Bellman')
    close(vu, b+beta*(f*ve+(1-f)*vu), 'search unemployed Bellman')
    close(j, z-w+beta*(1-s)*j, 'filled-job Bellman')
    close(eta*j, (1-eta)*surplus, 'Nash surplus condition')
    close(cost, beta*h*j, 'entry cost')
    close(s*(1-u), f*u, 'stationary worker flows')
    need(0 < f <= 1+1e-12 and 0 < h <= 1+1e-12, 'matching feasibility')
    return dict(x=x, theta=x*x, f=f, h=h, j=j, w=w, surplus=surplus,
                vu=vu, ve=ve, u=u, v=x*x*u)


def effort_values(beta, s, f, q, e, b):
    need(0 < beta < 1 and 0 <= s < 1 and 0 <= f <= 1 and 0 < q <= 1
         and e > 0, 'effort model domain')
    gap_den = 1-beta*(1-s-f)
    w = b+e+e*gap_den/(beta*(1-s)*q)
    gap = (w-e-b)/gap_den
    vu = (b+beta*f*gap)/(1-beta)
    ve = vu+gap
    loss = s+(1-s)*q
    need(0 <= loss <= 1, 'conditional detection avoids double count')
    need(ve == w-e+beta*((1-s)*ve+s*vu), 'effort employed value')
    need(vu == b+beta*(f*ve+(1-f)*vu), 'effort unemployed value')
    need(ve == w+beta*((1-loss)*ve+loss*vu), 'one-period deviation tie')
    need(ve > vu, 'job acceptance')
    # Solve the alternative always-shirk policy holding the market outside
    # value fixed. This is another check on the binding effort condition.
    always_shirk = (w+beta*loss*vu)/(1-beta*(1-loss))
    need(always_shirk == ve, 'stationary alternative action value')
    return w, ve, vu, gap


def check():
    doc = Chapter()
    doc.feed((ROOT/'content/chapters/v06-c05.html').read_text())
    need(not doc.stack and len(doc.ids) == len(set(doc.ids)), 'chapter HTML')
    need((doc.worked, doc.exercises, doc.solutions) == (4, 8, 8), 'chapter package')
    sources = json.loads((ROOT/'content/reviews/v06-c05-sources.json').read_text())
    need(set(doc.sources) == {row['id'] for row in sources}, 'scoped sources')

    worked = stock_ledger((600,100,300), ((540,30,30),(40,50,10),(30,15,255)))
    exercise = stock_ledger((500,100,400), ((450,30,20),(25,45,30),(40,36,324)))
    need(worked == (610,95,295) and exercise == (515,111,374), 'stock targets')
    need(F(95,705) == F(19,141) and F(80,680) == F(2,17), 'denominators')
    need(F(598,1000)/F(92,100) == F(65,100), 'final participation')
    need(F(60,100)/F(90,100) == F(2,3), 'initial participation')

    # Forward flows are compared with the closed-form paths and convergence
    # bounds. Edge cases are included; no false universal convergence claim.
    transition_cases = 0
    for s in (F(0),F(1,100),F(1,20),F(1,4),F(3,4),F(1)):
        for f in (F(0),F(1,25),F(1,5),F(1,2),F(3,4),F(1)):
            for initial in (F(0),F(1,5),F(2,5),F(1)):
                u = initial
                for t in range(12):
                    need(0 <= u <= 1, 'invariant state interval')
                    if s+f:
                        target = s/(s+f)
                        need(u == target+(1-s-f)**t*(initial-target), 'affine path')
                    else:
                        need(u == initial, 'zero-flow state')
                    u = transition(u,s,f)
                transition_cases += 1
    need(transition(F(2,5),F(1,20),F(1,5)) == F(7,20), 'exercise first state')
    need(transition(F(7,20),F(1,20),F(1,5)) == F(5,16), 'exercise second state')
    need(transition(F(39,100),F(1,100),F(1,25)) == F(761,2000), 'slow second state')
    need(F(1,20)*F(4,5) == F(1,25) and F(1,100)*F(4,5) == F(1,125), 'incidence')
    need(F(4,5)**3 == F(64,125) and F(24,25)**3 == F(13824,15625), 'duration tails')
    need(1/(F(1,5)+F(1,10)) == F(10,3), 'competing exit duration')
    need(F(1,5)/(F(1,5)+F(1,10)) == F(2,3), 'competing job-exit chance')
    need(transition(F(3,10),F(2,25),F(8,25)) == F(13,50), 'retention state')

    close(.5*sqrt(80*20),20,'matching at boundary')
    close(.5*sqrt(80*5)/5,2,'infeasible formal fill probability')
    u,s,mu = F(1,5),F(1,10),F(1,2)
    v = s*s*(1-u)**2/(mu*mu*u)
    need(v == F(16,125) and v/u == F(16,25), 'Beveridge exercise')
    need(F(2,5)*u == s*(1-u) and F(5,8)*v == s*(1-u), 'matching flow agreement')
    for u in (.1,.3,.7,.9):
        eps = 1e-5
        fn = lambda t:.04*(1-t)**2/t
        derivative = (fn(u+eps)-fn(u-eps))/(2*eps)
        need(derivative < 0, 'negative numerical Beveridge slope')
        need(abs(derivative-.04*(1-1/u**2)) < 1e-6, 'Beveridge derivative')

    baseline = search_equilibrium()
    for key,target in dict(x=1,theta=1,f=.5,h=.5,j=20/3,w=28/3,
                           surplus=20/3,vu=100/3,ve=40,u=1/3,v=1/3).items():
        close(baseline[key],target,'baseline search '+key)
    weak = search_equilibrium(mu=.25)
    close(weak['x'],sqrt(7)-2,'changed matching root')
    close(weak['u'],(sqrt(7)+1)/6,'changed matching unemployment')
    close(weak['v'],.2533765295753557,'changed matching vacancies')
    close(weak['w'],8.555993007655516,'changed matching wage')
    cheap = search_equilibrium(cost=1)
    for key,target in dict(x=2,theta=4,f=1,h=.25,j=5,w=10,surplus=5,
                           vu=40,ve=45,u=.2,v=.8).items():
        close(cheap[key],target,'cheap recruitment '+key)
    try:
        search_equilibrium(cost=.5)
    except ValueError as exc:
        need('probability domain' in str(exc), 'correct rejected branch')
    else:
        raise ValueError('must reject invalid matching root')

    effort_cases = 0
    for beta in (F(1,2),F(4,5),F(9,10)):
        for s in (F(0),F(1,4),F(3,4)):
            for f in (F(0),F(1,4),F(1)):
                for q in (F(1,4),F(1,2),F(1)):
                    effort_values(beta,s,f,q,F(1),F(2))
                    effort_cases += 1
    w,ve,vu,gap = effort_values(F(4,5),F(1,4),F(1,4),F(1,2),F(1),F(2))
    need((w,ve,vu,gap) == (F(5),F(50,3),F(40,3),F(10,3)), 'worked effort values')
    w,ve,vu,gap = effort_values(F(4,5),F(1,4),F(1,4),F(1),F(1),F(2))
    need((w,ve,vu,gap) == (F(4),F(40,3),F(35,3),F(5,3)), 'monitoring exercise')

    # An independent labor-demand/intertemporal-incentive residual verifies
    # both equilibrium roots before comparing the printed closed forms.
    def required_wage(u):
        f = .25*(1-u)/u
        return 3+(1-.8*(1-.25-f))/(.8*.75*.5)
    for productivity, target in ((7.,.5),(8.,(sqrt(97)-1)/24)):
        u = bisect_increasing(lambda t: productivity-4*(1-t)-required_wage(t),.2,1.)
        close(u,target,'labor-demand closure root')
        f = .25*(1-u)/u
        need(0 <= f <= 1, 'closure job-finding feasibility')
        close(required_wage(u),productivity-4*(1-u),'closure wage equation')
        if productivity == 8:
            close(f,(sqrt(97)-3)/16,'exercise closure f')
            close(required_wage(u),(23+sqrt(97))/6,'exercise closure w')

    def hysteresis(u,s,high_f,low_f,cut):
        return transition(u,s,high_f if u < cut else low_f)
    hysteresis_cases = 0
    for s,fh,fl,cut,lo,hi,shock in (
            (F(1,20),F(2,5),F(1,10),F(1,5),F(1,9),F(1,3),F(1,4)),
            (F(1,25),F(9,25),F(3,50),F(1,4),F(1,10),F(2,5),F(3,10))):
        need(s+(1-s-fh)*cut < cut, 'low region limit invariant')
        need(s+(1-s-fl)*cut >= cut, 'high threshold invariant')
        need(hysteresis(lo,s,fh,fl,cut) == lo, 'low fixed point')
        need(hysteresis(hi,s,fh,fl,cut) == hi, 'high fixed point')
        u = shock
        for t in range(25):
            need(u == hi+(1-s-fl)**t*(shock-hi), 'post-shock exact path')
            need(cut <= u <= 1, 'high invariant trajectory')
            u = hysteresis(u,s,fh,fl,cut)
        for initial in (F(0),cut-F(1,100),cut,F(1)):
            out = hysteresis(initial,s,fh,fl,cut)
            need(0 <= out <= 1, 'global bounded feedback')
            need((out < cut) == (initial < cut), 'selected basin remains')
            hysteresis_cases += 1

    return {'chapter':'v06-c05','worked_examples':4,'solved_exercises':8,
            'transition_parameter_initial_cases':transition_cases,
            'effort_value_cases':effort_cases,'hysteresis_boundary_cases':hysteresis_cases,
            'stock_ledgers':[list(worked),list(exercise)],
            'matching_equilibria':[baseline,weak,cheap],
            'rejected_infeasible_entry_case':True,'status':'passed'}


if __name__ == '__main__':
    print(json.dumps(check(),indent=2))
