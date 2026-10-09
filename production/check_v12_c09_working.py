"""Quiet exact finite checks for the four-file v12-c09 working chapter."""
from fractions import Fraction as F
from html.parser import HTMLParser
from pathlib import Path
import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = Path(__file__).resolve().parent
FILES = ('v12-c09-working.html', 'check_v12_c09_working.py',
         'v12-c09-sources-working.json', 'v12-c09-author-review-working.json')
SOURCES = {'v04-c10-mit-stationarity', 'v12-c09-mit-vars', 'v12-c09-mit-cointegration',
           'v12-c09-bollerslev-garch1986', 'v12-c09-diebold-forecast2012'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rational(value):
    require(type(value) is int or isinstance(value, F), 'exact rational required')
    result = F(value)
    require(abs(result) <= 10**6, 'bounded rational required')
    return result


def strict(text):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON member')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON: '+value)
    def finite(value):
        result = float(value)
        require(math.isfinite(result), 'overflowed JSON number')
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite)


def matrix_product(a, b):
    return [[sum((x*y for x, y in zip(row, col)), F()) for col in zip(*b)] for row in a]


def transpose(a):
    return [list(row) for row in zip(*a)]


def matrix_add(a, b):
    return [[x+y for x, y in zip(row, other)] for row, other in zip(a, b)]


def solve(a, b):
    require(type(a) is list and 1 <= len(a) <= 3, 'one to three equations')
    n = len(a)
    require(type(b) is list and len(b) == n and all(type(row) is list and len(row) == n for row in a), 'square system')
    rows = [[rational(x) for x in row]+[rational(b[i])] for i, row in enumerate(a)]
    for j in range(n):
        k = next((i for i in range(j, n) if rows[i][j]), None)
        require(k is not None, 'rank failure')
        rows[j], rows[k] = rows[k], rows[j]
        pivot = rows[j][j]; rows[j] = [x/pivot for x in rows[j]]
        for i in range(n):
            if i != j:
                q = rows[i][j]; rows[i] = [x-q*y for x, y in zip(rows[i], rows[j])]
    return [row[-1] for row in rows]


def arma(phi, theta, variance, horizon):
    phi, theta, variance = map(rational, (phi, theta, variance))
    require(abs(phi) < 1 and variance > 0, 'stable causal AR and positive innovation variance')
    require(type(horizon) is int and 1 <= horizon <= 16, 'horizon1..16')
    psi = [F(1)]+[(phi+theta)*phi**j for j in range(horizon-1)]
    gamma0 = variance*(1+(phi+theta)**2/(1-phi**2))
    gamma1 = variance*((phi+theta)+(phi+theta)**2*phi/(1-phi**2))
    return {'psi': psi, 'gamma0': gamma0, 'gamma1': gamma1,
            'forecast_variances': [variance*sum(v*v for v in psi[:h]) for h in range(1, horizon+1)]}


def recovery(phi, theta, count):
    phi, theta = rational(phi), rational(theta)
    require(abs(phi) < 1 and abs(theta) < 1, 'declared stable and invertible domain')
    require(type(count) is int and 1 <= count <= 16, 'recovery count1..16')
    return [F(1)]+[-(phi+theta)*(-theta)**(j-1) for j in range(1, count)]


def var_covariance(a, omega):
    require(type(a) is list and type(omega) is list and len(a) == len(omega) == 2,
            'two-dimensional VAR')
    require(all(type(row) is list and len(row) == 2 for row in a+omega), 'two-by-two matrices')
    a = [[rational(v) for v in row] for row in a]; o = [[rational(v) for v in row] for row in omega]
    require(sum(v*v for row in a for v in row) < 1, 'supported sufficient Frobenius contraction')
    require(o[0][1] == o[1][0] and o[0][0] > 0 and o[0][0]*o[1][1]-o[0][1]**2 > 0,
            'positive-definite symmetric innovation covariance')
    u, v = a[0]; w, z = a[1]
    g11, g12, g22 = solve([[1-u*u, -2*u*v, -v*v], [-u*w, 1-u*z-v*w, -v*z],
                          [-w*w, -2*w*z, 1-z*z]], [o[0][0], o[0][1], o[1][1]])
    return [[g11, g12], [g12, g22]]


def stationary_ar_covariance(phi, variance, count):
    phi, variance = rational(phi), rational(variance)
    require(abs(phi) < 1 and variance > 0, 'stationary AR covariance domain')
    require(type(count) is int and 1 <= count <= 16, 'covariance dimension1..16')
    return [[variance*phi**abs(i-j) for j in range(count)] for i in range(count)]


def score_form(phi, sigma2, count):
    phi, sigma2 = rational(phi), rational(sigma2)
    require(abs(phi) < 1 and sigma2 > 0, 'fixed stable score domain')
    require(type(count) is int and 1 <= count <= 16, 'score count1..16')
    gamma0 = sigma2/(1-phi**2)
    k = [[F() for _ in range(count+1)] for _ in range(count+1)]
    for t in range(1, count+1):
        k[0][t] = k[t][0] = phi**(t-1)/2
        for j in range(1, t):
            k[j][t] = k[t][j] = phi**(t-j-1)/2
    variances = [gamma0]+[sigma2]*count
    variance = 2*sum(k[i][j]**2*variances[i]*variances[j] for i in range(count+1) for j in range(count+1))
    # Raw independent coordinates are X0,epsilon1,...; scaling gives the manuscript K.
    return {'raw_K': k, 'coordinate_variances': variances, 'variance': variance, 'gamma0': gamma0}


def unit_root_record(innovations, initial=0):
    require(type(innovations) is list and 2 <= len(innovations) <= 16, 'two to sixteen unit-root increments')
    require(type(initial) is int and initial == 0, 'declared zero initial level')
    e = [rational(v) for v in innovations]; x = [F(0)]
    for v in e:
        x.append(x[-1]+v)
    den = sum(v*v for v in x[:-1]); require(den > 0, 'nonzero lagged design')
    cross = sum(a*b for a, b in zip(x[:-1], x[1:])); rho = cross/den
    residual = [b-rho*a for a, b in zip(x[:-1], x[1:])]
    ssr = sum(v*v for v in residual); require(ssr > 0, 'positive residual scale')
    score = sum(a*b for a, b in zip(x[:-1], e))
    return {'levels': x, 'D': den, 'cross': cross, 'score': score, 'rho': rho,
            'residuals': residual, 'SSR': ssr, 's2': ssr/len(e), 'scaled_change': len(e)*(rho-1),
            't_squared': score**2/(den*(ssr/len(e)))}


def garch(omega, alpha, beta, kappa, current_h, current_e2, horizon):
    omega, alpha, beta, kappa, current_h, current_e2 = map(rational, (omega, alpha, beta, kappa, current_h, current_e2))
    require(omega > 0 and alpha >= 0 and beta >= 0 and kappa >= 1, 'GARCH positive intercept, nonnegative coefficients and standardized fourth moment')
    require(current_h > 0 and current_e2 >= 0, 'valid current variance and squared shock')
    require(type(horizon) is int and 1 <= horizon <= 16, 'variance forecast horizon1..16')
    rho = alpha+beta; a2 = kappa*alpha**2+2*alpha*beta+beta**2
    mean = omega/(1-rho) if rho < 1 else None
    h2 = (omega**2+2*omega*rho*mean)/(1-a2) if a2 < 1 else None
    e4 = kappa*h2 if h2 is not None else None
    squared_variance = e4-mean**2 if e4 is not None else None
    squared_covariance = alpha*squared_variance+beta*(h2-mean**2) if e4 is not None else None
    forecasts = [omega+alpha*current_e2+beta*current_h]
    for _ in range(1, horizon):
        forecasts.append(omega+rho*forecasts[-1])
    return {'rho': rho, 'a2': a2, 'mean_h': mean, 'h2': h2, 'return_fourth': e4,
            'squared_variance': squared_variance, 'squared_covariance1': squared_covariance,
            'forecasts': forecasts, 'sum_variance': sum(forecasts)}


def overlap(count, horizon=2):
    require(type(count) is int and 1 <= count <= 16 and type(horizon) is int and 1 <= horizon <= 4,
            'bounded forecast origin count and horizon')
    design = [[F(j in range(i, i+horizon)) for j in range(count+horizon-1)] for i in range(count)]
    covariance = matrix_product(design, transpose(design))
    return design, covariance


def normalize(text):
    return re.sub(r'\s+', '', text).replace('−', '-')


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.ids = []; self.links = []; self.sources = []; self.text = []
        self.worked = 0; self.exercise_count = 0; self.solution_count = 0
        self.prompts = {}; self.answers = {}; self.capture = []
        self.exercise_depth = None; self.solution_depth = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); classes = a.get('class', '').split()
        if 'id' in a:
            self.ids.append(a['id'])
        if 'href' in a:
            self.links.append(a['href'])
        if 'data-source' in a:
            self.sources.append(a['data-source'])
        if 'worked' in classes:
            self.worked += 1
        if tag == 'ol' and 'exercises' in classes:
            self.exercise_depth = len(self.stack)
        if tag == 'details' and 'solutions' in classes:
            self.solution_depth = len(self.stack)
        if tag == 'li':
            if self.exercise_depth is not None:
                self.exercise_count += 1
                self.capture.append((len(self.stack), self.prompts, a.get('id'), []))
            if 'data-solution-for' in a:
                require(self.solution_depth is not None, 'answer outside solutions')
                self.solution_count += 1
                self.capture.append((len(self.stack), self.answers, a['data-solution-for'], []))
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input'):
            self.stack.append(tag)
    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1] == tag, 'unbalanced '+tag)
        depth = len(self.stack)-1
        if tag == 'li':
            for row in list(self.capture):
                level, dest, key, values = row
                if level == depth:
                    require(key and key not in dest, 'missing or duplicate solution key')
                    dest[key] = ' '.join(values); self.capture.remove(row)
        if tag == 'ol' and depth == self.exercise_depth:
            self.exercise_depth = None
        if tag == 'details' and depth == self.solution_depth:
            self.solution_depth = None
        self.stack.pop()
    def handle_data(self, value):
        self.text.append(value)
        for _, _, _, values in self.capture:
            values.append(value)


class Audit:
    def __init__(self):
        self.count = 0; self.rejections = 0; self.anchors = 0
    def eq(self, value, expected, label):
        self.count += 1
        require(value == expected, label+': '+repr(value)+' != '+repr(expected))
    def near(self, value, expected, label, tolerance=2e-12):
        self.count += 1
        require(math.isclose(value, expected, rel_tol=tolerance, abs_tol=tolerance), label)
    def reject(self, call, label):
        self.count += 1
        try:
            call()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError('invalid domain accepted: '+label)
    def anchor(self, page, exercise, *values):
        answer = normalize(page.answers['v12-c09-e'+str(exercise)])
        for value in values:
            self.eq(normalize(str(value)) in answer, True, 'solution '+str(exercise)+' anchor '+str(value))
            self.anchors += 1
    def body(self, page, value):
        self.eq(normalize(str(value)) in normalize(' '.join(page.text)), True, 'body anchor '+str(value))
        self.anchors += 1


def numerical(a, page):
    # Known filter moments, independently checked against recursion identities.
    phi, theta, s2 = F(1, 2), F(1, 3), F(9, 4)
    case = arma(phi, theta, s2, 8)
    a.eq(case['psi'][:3], [1, F(5, 6), F(5, 12)], 'ARMA impulse coefficients')
    a.eq((case['gamma0'], case['gamma1']), (F(13, 3), F(35, 12)), 'ARMA covariances')
    a.eq(case['gamma1'], phi*case['gamma0']+theta*s2, 'lag-one recursion covariance')
    a.eq(case['gamma0'], phi*phi*case['gamma0']+s2*(1+theta*theta)+2*phi*theta*s2, 'variance recursion covariance')
    forecasts = [phi**h*2+theta*phi**(h-1)*(-F(3, 2)) for h in (1, 2, 3)]
    a.eq(forecasts, [F(1, 2), F(1, 4), F(1, 8)], 'three conditional means')
    a.eq(case['forecast_variances'][:3], [F(9, 4), F(61, 16), F(269, 64)], 'three conditional variances')
    inverse = recovery(phi, theta, 8)
    for j in range(8):
        a.eq(sum(inverse[k]*case['psi'][j-k] for k in range(j+1)), F(j == 0), 'recovery/filter convolution')
    canceled = arma(phi, -phi, s2, 4)
    a.eq(canceled['psi'], [1, 0, 0, 0], 'minimal representation cancellation')
    a.eq(canceled['forecast_variances'], [s2]*4, 'canceled white-noise prediction variance')
    noninvertible = arma(0, 2, 1, 3); invertible = arma(0, F(1, 2), 4, 3)
    a.eq((noninvertible['gamma0'], noninvertible['gamma1']), (5, 2), 'noninvertible MA covariance')
    a.eq((invertible['gamma0'], invertible['gamma1']), (5, 2), 'same Gaussian process covariance')
    # Repeated-root coefficients arise from explicit convolution, not a simple-root formula.
    geometric = [F(1, 2)**j for j in range(7)]
    repeated = [sum(geometric[k]*geometric[j-k] for k in range(j+1)) for j in range(7)]
    a.eq(repeated, [(j+1)*F(1, 2)**j for j in range(7)], 'repeated inverse root coefficients')
    a.anchor(page, 1, 'Cauchy', 'binom', 'White noise', 'invertibility', 'conditional means')
    a.anchor(page, 2, '13/3', '35/12', '61/16', '269/64', '5,2', 'θ=−φ')

    A = [[F(1, 2), F(1, 4)], [F(0), F(1, 3)]]
    omega = [[F(1), F(1)], [F(1), F(2)]]
    cov = var_covariance(A, omega)
    a.eq(cov, [[F(479, 240), F(57, 40)], [F(57, 40), F(9, 4)]], 'VAR stationary covariance')
    a.eq(matrix_add(matrix_product(matrix_product(A, cov), transpose(A)), omega), cov, 'Lyapunov substitution')
    a.eq(sum(v*v for row in A for v in row), F(61, 144), 'explicit contraction certificate')
    A2 = matrix_product(A, A)
    a.eq(A2, [[F(1, 4), F(5, 24)], [0, F(1, 9)]], 'A squared')
    a.eq(matrix_product(A2, [[F(2)], [-F(1)]]), [[F(7, 24)], [-F(1, 9)]], 'VAR two-step mean')
    V2 = matrix_add(omega, matrix_product(matrix_product(A, omega), transpose(A)))
    a.eq(V2, [[F(13, 8), F(4, 3)], [F(4, 3), F(20, 9)]], 'VAR two-step covariance')
    # Finite covariance recursion plus the remaining stationary tail is exact.
    power = [[F(1), F(0)], [F(0), F(1)]]; partial = [[F(0)]*2 for _ in range(2)]
    for _ in range(4):
        partial = matrix_add(partial, matrix_product(matrix_product(power, omega), transpose(power)))
        power = matrix_product(power, A)
    a.eq(matrix_add(partial, matrix_product(matrix_product(power, cov), transpose(power))), cov, 'finite covariance sum and exact tail')
    B = [[F(1), F(0)], [F(1), F(1)]]
    Q = [[F(3, 5), -F(4, 5)], [F(4, 5), F(3, 5)]]; rotated = matrix_product(B, Q)
    a.eq(matrix_product(Q, transpose(Q)), [[1, 0], [0, 1]], 'orthogonal shock rotation')
    a.eq(rotated, [[F(3, 5), -F(4, 5)], [F(7, 5), -F(1, 5)]], 'rotated factor')
    for factor in (B, rotated):
        a.eq(matrix_product(factor, transpose(factor)), omega, 'same reduced-form innovation covariance')
    a.eq([row[0] for row in B], [1, 1], 'first original impact')
    a.eq([row[0] for row in rotated], [F(3, 5), F(7, 5)], 'first rotated impact')
    a.eq(matrix_product(A, [[row[0]] for row in B]), [[F(3, 4)], [F(1, 3)]], 'original lag-one response')
    a.eq(matrix_product(A, [[row[0]] for row in rotated]), [[F(13, 20)], [F(7, 15)]], 'rotated lag-one response')
    a.anchor(page, 3, '61/144', '479/240', '57/40', '9/4', '7/24,−1/9', '13/8', '4/3', '20/9', '13/20,7/15', 'causal ordering')

    for p in (F(1, 2), -F(1, 2)):
        for T in (1, 3, 6):
            form = score_form(p, F(3, 4), T); k = form['raw_K']; g0 = form['gamma0']
            a.eq(sum(k[i][i] for i in range(T+1)), 0, 'score matrix trace')
            a.eq(form['variance'], T*g0*F(3, 4), 'score variance from independent-coordinate quadratic form')
            coordinate = [F(1)]+[F((-1)**j*(j+1), 3) for j in range(T)]
            value = coordinate[0]; direct = F(0)
            for innovation in coordinate[1:]:
                direct += value*innovation; value = p*value+innovation
            quadratic = matrix_product(matrix_product([coordinate], k), transpose([coordinate]))[0][0]
            a.eq(quadratic, direct, 'full quadratic-form score identity')
            sd = [math.sqrt(float(v)) for v in form['coordinate_variances']]
            rowmax = max(sum(abs(float(k[i][j]))*sd[i]*sd[j] for j in range(T+1)) for i in range(T+1))
            sigma = math.sqrt(.75); r = abs(float(p)); gamma = float(g0)
            bound = max(sigma*math.sqrt(gamma)/(2*(1-r)), sigma*math.sqrt(gamma)/2+.75/(1-r))
            a.eq(rowmax <= bound+1e-14, True, 'uniform standard-normal score row bound')
            lagcov = stationary_ar_covariance(p, g0, T)
            den_var = 2*sum(v*v for row in lagcov for v in row)/T**2
            den_bound = 2*g0*g0/T*(1+2*p*p/(1-p*p))
            a.eq(den_var <= den_bound, True, 'Gaussian square covariance LLN bound')
    a.eq(F(3, 4)/(F(3, 4)/(1-F(1, 2)**2)), F(3, 4), 'stable coefficient root-T variance')
    a.eq(15+3*3+3*1+1, 28, 'normal third-absolute-moment upper bound')
    poly = [F(1), 0, 0, 0, -35, 84, -70, 20]
    def evaluate(coeff, x): return sum(v*x**j for j, v in enumerate(coeff))
    a.eq((evaluate(poly, 0), evaluate(poly, 1)), (1, 0), 'smooth CDF cutoff values')
    for order in (1, 2, 3):
        poly = [j*poly[j] for j in range(1, len(poly))]
        a.eq((evaluate(poly, 0), evaluate(poly, 1)), (0, 0), 'smooth CDF endpoint derivatives')
    # Full lag vector for T=2 fixes epsilon1; only epsilon2 remains random.
    lag = [F(1), F(2)]; p = F(1, 2); true_mean = lag[0]*(lag[1]-p*lag[0])
    a.eq((true_mean, F(3, 4)*lag[-1]**2), (F(3, 2), F(3)), 'correct full-design conditional Gaussian law')
    a.eq(F(3, 4)*sum(v*v for v in lag), F(15, 4), 'different false fixed-design conditional variance')
    a.anchor(page, 4, 'γ₀', '28', '14', 'C³', '3/4', 'nonzero mean', 'σ²X_{T−1}²', 'N(0,σ²D_T)')

    record = unit_root_record([1, -1, 2, 1])
    a.eq(record['levels'], [0, 1, 0, 2, 3], 'synthetic random-walk levels')
    for name, expected in [('D', F(5)), ('cross', F(6)), ('score', F(1)), ('rho', F(6, 5)),
                           ('SSR', F(34, 5)), ('s2', F(17, 10)), ('scaled_change', F(4, 5)), ('t_squared', F(2, 17))]:
        a.eq(record[name], expected, 'unit-root record '+name)
    a.eq(record['residuals'], [1, -F(6, 5), 2, F(3, 5)], 'finite regression residuals')
    a.eq(record['score'], (record['levels'][-1]**2-sum(F(v)**2 for v in (1, -1, 2, 1)))/2, 'telescoping unit-root score')
    a.eq(record['SSR'], sum(F(v)**2 for v in (1, -1, 2, 1))-record['score']**2/record['D'], 'residual variance exact identity')
    a.near(math.sqrt(float(record['t_squared'])), .342997170285, 'printed conventional statistic')
    scaled = unit_root_record([2, -2, 4, 2])
    a.eq((scaled['rho'], scaled['t_squared']), (record['rho'], record['t_squared']), 'measurement-unit invariance')
    a.eq(scaled['s2'], 4*record['s2'], 'measurement-unit residual variance')
    for count in (2, 4, 8):
        widths = [F(1, count)]*count
        a.eq((sum(widths), 2*sum(w*w for w in widths)), (1, F(2, count)), 'Brownian-grid QV moments')
    a.anchor(page, 5, 'J>0', '34/5', '17/10', '4/5', '2/17', '0.342997170285', 'intercept', 'non-Gaussian')

    x = [F(1), F(0), F(2), F(3)]; v = [F(1, 2), -F(1, 2), F(1), -F(1)]
    y = [2*r+s for r, s in zip(x, v)]; D = sum(t*t for t in x)
    a.eq(y, [F(5, 2), -F(1, 2), F(5), F(5)], 'cointegrated observed levels')
    a.eq((D, sum(r*s for r, s in zip(x, v))), (14, -F(1, 2)), 'level design and spread cross moment')
    a.eq(sum(r*s for r, s in zip(x, y))/D, F(55, 28), 'level slope')
    cv = stationary_ar_covariance(F(1, 2), 1, 4)
    quad = matrix_product(matrix_product([x], cv), transpose([x]))[0][0]
    a.eq((quad, quad/D**2), (F(87, 4), F(87, 784)), 'stationary spread conditional sampling variance')
    a.eq(F(1)/D, F(1, 14), 'false iid spread variance')
    iid = stationary_ar_covariance(0, 1, 4)
    a.eq(matrix_product(matrix_product([x], iid), transpose([x]))[0][0]/D**2, F(1, 14), 'genuinely changed iid spread law')
    initial_loading = [F(1, 2)**i for i in range(1, 5)]
    initial_contribution = sum(a*b for a, b in zip(x, initial_loading))**2
    a.eq(initial_contribution, F(225, 256), 'random stationary initialization contribution')
    a.eq((quad-initial_contribution)/D**2, F(5343, 50176), 'different zero-initial-spread law')
    a.eq(sum(abs(z) for z in cv[1]) <= 3, True, 'summable stationary covariance operator bound')
    innovations = [v[j]-F(1, 2)*v[j-1] for j in range(1, 4)]
    a.eq(innovations, [-F(3, 4), F(5, 4), -F(3, 2)], 'only t2 to t4 spread innovations')
    for j, eta in enumerate(innovations, 1):
        a.eq(y[j]-y[j-1], 2*(x[j]-x[j-1])-F(1, 2)*v[j-1]+eta, 'error-correction identity at recorded adjacent dates')
    a.eq(2*x[-1]+F(1, 4)*v[-1], F(23, 4), 'conditional two-step mean')
    a.eq(4*2+F(3, 4)*(1+F(1, 4)), F(143, 16), 'conditional two-step error variance')
    a.anchor(page, 6, '55/28', '87/4', '87/784', '1/14', '−3/4,5/4,−3/2', '23/4', '143/16', 'v₀', 'O_P(1)')

    vol = garch(F(1, 10), F(1, 10), F(4, 5), 3, 2, 9, 4)
    for name, expected in [('rho', F(9, 10)), ('a2', F(83, 100)), ('mean_h', F(1)), ('h2', F(19, 17)),
                           ('return_fourth', F(57, 17)), ('squared_variance', F(40, 17)),
                           ('squared_covariance1', F(28, 85)), ('sum_variance', F(5939, 625))]:
        a.eq(vol[name], expected, 'GARCH '+name)
    a.eq(vol['return_fourth']/vol['mean_h']**2-3, F(6, 17), 'excess versus raw kurtosis')
    a.eq(vol['squared_covariance1']/vol['squared_variance'], F(7, 50), 'squared-return lag-one correlation')
    a.eq(vol['forecasts'], [F(13, 5), F(61, 25), F(287, 125), F(1354, 625)], 'all conditional variance forecasts')
    for j, value in enumerate(vol['forecasts']):
        a.eq(value, 1+F(9, 10)**j*(F(13, 5)-1), 'tower recurrence versus closed forecast')
    nu_variance = 2*vol['h2']
    squared_arma = arma(F(9, 10), -F(4, 5), nu_variance, 3)
    a.eq((squared_arma['gamma0'], squared_arma['gamma1']),
         (vol['squared_variance'], vol['squared_covariance1']), 'independent squared-process covariance representation')
    heavy = garch(F(1, 10), F(2, 5), F(1, 2), 3, 2, 9, 2)
    a.eq((heavy['mean_h'], heavy['a2'], heavy['return_fourth']), (1, F(113, 100), None), 'finite second and infinite fourth region')
    probabilities = [F(1, 2), F(1, 4), F(1, 4)]; squares = [0, 2, 2]
    a.eq(sum(p*z for p, z in zip(probabilities, squares)), 1, 'discrete innovation variance normalization')
    a.eq(probabilities[1]-probabilities[2], 0, 'symmetric discrete innovation mean')
    multiplier = [F(9, 10)*z+F(1, 5) for z in squares]
    a.eq(multiplier, [F(1, 5), 2, 2], 'discrete positive multipliers')
    a.eq(sum(p*z for p, z in zip(probabilities, multiplier)), F(11, 10), 'infinite-second moment multiplier mean')
    elog = sum(float(p)*math.log(float(z)) for p, z in zip(probabilities, multiplier))
    a.near(elog, .5*math.log(.4), 'negative exact expected-log expression')
    a.near(elog, -.458145365937, 'printed expected log')
    a.eq(F(1, 5)*2 < 1, True, 'negative log sign without rounding')
    discrete = garch(1, F(9, 10), F(1, 5), 2, 2, 0, 2)
    a.eq(discrete['mean_h'], None, 'no invented finite variance beyond moment region')
    constant = garch(F(1, 10), 0, F(4, 5), 3, F(1, 2), 1, 2)
    a.eq((constant['mean_h'], constant['h2']), (F(1, 2), F(1, 4)), 'constant variance alpha-zero boundary')
    a.eq((constant['return_fourth']/constant['mean_h']**2-3, constant['squared_covariance1']), (0, 0), 'zero excess and zero squared covariance boundary')
    a.anchor(page, 7, 'positive', 'tight', 'E A', 'a₂', 'fourth', 'stationarity')
    a.anchor(page, 8, '83/100', '19/17', '57/17', '6/17', '1354/625', '5939/625', '40/17', '28/85', '7/50')
    a.anchor(page, 9, '113/100', '11/10', 'log(2/5)', '−0.458145365937', 'excess 0', 'E ε²=∞')

    design, error_cov = overlap(4)
    expected = [[2, 1, 0, 0], [1, 2, 1, 0], [0, 1, 2, 1], [0, 0, 1, 2]]
    a.eq(error_cov, expected, 'all overlapping-error covariances')
    loss_cov = [[2*z*z for z in row] for row in error_cov]
    a.eq(loss_cov, [[8, 2, 0, 0], [2, 8, 2, 0], [0, 2, 8, 2], [0, 0, 2, 8]], 'all Gaussian squared-loss covariances')
    mean_error_variance = sum(sum(row) for row in error_cov)/16
    a.eq(sum(sum(row) for row in loss_cov)/16, F(11, 4), 'mean squared-loss sampling variance')
    a.eq(F(loss_cov[0][0], 4), 2, 'false iid squared-loss variance')
    c = F(1, 2)
    a.eq((c*c, 4*c*c*mean_error_variance), (F(1, 4), F(7, 8)), 'fixed comparison mean and variance')
    a.eq(4*c*c*error_cov[0][0]/4, F(1, 2), 'false iid comparison variance')
    a.eq(4*F(0)**2*mean_error_variance, 0, 'identical-forecast degeneracy')
    _, one = overlap(4, 1)
    a.eq(one, [[F(i == j) for j in range(4)] for i in range(4)], 'nonoverlapping one-step intervention')
    a.eq((-mean_error_variance, mean_error_variance), (-F(7, 8), F(7, 8)), 'selected versus new-block expected comparison')
    errors = [row[0] for row in matrix_product(design, [[F(z)] for z in (1, 0, 2, -1, 1)])]
    selected = sum(errors)/4
    a.eq((errors, selected), ([1, 2, 1, 0], 1), 'selected synthetic offset')
    a.eq(sum((e-selected)**2-e**2 for e in errors)/4, -F(1), 'synthetic fitted loss improvement')
    a.eq(set(range(1, 6)).isdisjoint(range(6, 11)), True, 'independent new block innovation dates')
    a.eq(set(range(1, 6)).isdisjoint(range(5, 10)), False, 'adjacent overlap violates fresh-block independence')
    a.anchor(page, 10, '11/4', '7/8', '1/2', '1/4', 'c=0', 'always Z')
    a.anchor(page, 11, '−7/8', '+7/8', '1,2,1,0', '−1', 'u₅', 'u₆', 'independent')
    a.anchor(page, 12, 'Six objections', 'Two revised analyses', 'Conclusion', 'conditionally Gaussian', 'nonzero conditional mean', '113/100')

    domains = [
        (lambda: rational(True), 'boolean rational'), (lambda: rational(float('nan')), 'nonfinite rational'),
        (lambda: rational(10**7), 'magnitude limit'), (lambda: arma(1, 0, 1, 2), 'unit root in stable filter'),
        (lambda: arma(0, 0, 0, 2), 'zero innovation variance'), (lambda: arma(0, 0, 1, True), 'boolean horizon'),
        (lambda: recovery(F(1, 2), 2, 4), 'noninvertible recovery'),
        (lambda: solve([[1, 1], [1, 1]], [1, 1]), 'singular equation system'),
        (lambda: var_covariance([[1, 0], [0, 1]], omega), 'outside sufficient contraction domain'),
        (lambda: var_covariance(A, [[1, 2], [2, 1]]), 'indefinite shock covariance'),
        (lambda: var_covariance(A, [[1, 0], [1, 1]]), 'asymmetric covariance'),
        (lambda: stationary_ar_covariance(1, 1, 4), 'unit-root stationary spread'),
        (lambda: score_form(0, 1, 17), 'score size cap'),
        (lambda: unit_root_record([1]), 'one-point zero-start regression'),
        (lambda: unit_root_record([0, 0]), 'zero lagged design'),
        (lambda: unit_root_record([1, 2], initial=1), 'unsupported unit-root initialization'),
        (lambda: garch(0, F(1, 10), F(4, 5), 3, 2, 9, 4), 'zero GARCH intercept'),
        (lambda: garch(1, -1, 0, 3, 2, 9, 4), 'negative variance coefficient'),
        (lambda: garch(1, 0, 0, F(1, 2), 2, 9, 4), 'impossible standardized fourth moment'),
        (lambda: garch(1, 0, 0, 3, 0, 9, 4), 'zero current variance'),
        (lambda: overlap(True), 'boolean forecast origin count'), (lambda: overlap(4, 5), 'unsupported forecast horizon')]
    for call, label in domains:
        a.reject(call, label)
    return {'ARMA_forecast_variances': [str(v) for v in case['forecast_variances'][:3]],
            'VAR_stationary_covariance': [[str(v) for v in row] for row in cov],
            'Gaussian_score_designs': 6, 'unit_root_slope': str(record['rho']),
            'stationary_spread_conditional_variance': str(quad/D**2),
            'GARCH_moment_regions': 3, 'forecast_origin_count': 4,
            'selected_and_fresh_expected_difference': ['-7/8', '7/8']}


def hashrow(path):
    raw = (BASE/path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check():
    before = {p: (BASE/p).read_bytes() for p in FILES}; a = Audit(); page = Reader()
    page.feed(before[FILES[0]].decode('utf-8')); page.close()
    a.eq(page.stack, [], 'balanced fragment')
    a.eq((page.worked, page.exercise_count, page.solution_count), (6, 12, 12), 'reader markers')
    expected = {'v12-c09-e'+str(i) for i in range(1, 13)}
    a.eq(set(page.prompts), expected, 'twelve exact prompts')
    a.eq(set(page.answers), expected, 'twelve paired solutions')
    a.eq(len(page.ids), len(set(page.ids)), 'unique IDs')
    a.eq(set(page.sources), SOURCES, 'five scoped citations')
    allowed = {'v12-c08.html', 'v12-c01.html', 'v12-c02.html', 'v02-c10.html#spectral-proof',
               'v03-c06.html#clt-proof', 'v03-c12.html#integrable-strong-law-proof',
               'v10-c07.html#quadratic-variation', 'v12-c10.html'}
    for href in page.links:
        a.eq(href in allowed or href in {'sources.html#'+s for s in SOURCES}, True, 'flat declared route')
    finite_evidence = numerical(a, page)
    sources = strict(before[FILES[2]].decode('utf-8'))
    a.eq({row['id'] for row in sources['sources']}, SOURCES, 'source proposal IDs')
    a.eq(len(sources['sources']), 5, 'five exact source scopes')
    review = strict(before[FILES[3]].decode('utf-8'))
    a.eq(set(review['payloads']), set(FILES[:3]), 'three nonself payloads')
    for p in FILES[:3]:
        a.eq(review['payloads'][p], hashrow(p), 'payload hash '+p)
    rejected = 0
    for invalid in ('{"x":1,"x":2}', 'NaN', 'Infinity', '-Infinity', '1e10000', '{}{}'):
        try:
            strict(invalid)
        except ValueError:
            rejected += 1
        else:
            raise ValueError('permissive JSON parser')
    a.eq(rejected, 6, 'strict JSON boundaries')
    for p, raw in before.items():
        a.eq((BASE/p).read_bytes(), raw, 'read-only check '+p)
    result = {'chapter': 'v12-c09', 'status': 'author checks passed; separate review required',
              'comparisons': a.count, 'domain_rejections': a.rejections, 'strict_JSON_rejections': rejected,
              'worked_examples': 6, 'exact_prompts_and_solutions': 12, 'visible_anchors': a.anchors,
              'primary_scopes': 5, 'finite_evidence': finite_evidence,
              'limits': 'Finite original laws plus separate analytic proof audit; no general dependent-data, VAR, non-Gaussian unit-root, cointegration-rank, QMLE or reestimated-forecast inference theorem, empirical validation, rendered UI or human certification.'}
    strict(json.dumps(result, allow_nan=False))
    return result


def portable():
    with tempfile.TemporaryDirectory(prefix='v12-c09-author-') as directory:
        target = Path(directory)
        for p in FILES:
            shutil.copy2(BASE/p, target/p)
        before = {p: (target/p).read_bytes() for p in FILES}; results = []
        code = ("import contextlib,importlib.util,io,json;s=importlib.util.spec_from_file_location('a',"
                +repr(str(target/FILES[1]))+");m=importlib.util.module_from_spec(s)\n"
                "with contextlib.redirect_stdout(io.StringIO()) as o,contextlib.redirect_stderr(io.StringIO()) as e:\n"
                " s.loader.exec_module(m);r=m.check()\n"
                "if o.getvalue() or e.getvalue():raise ValueError('API noise')\n"
                "print(json.dumps(r,allow_nan=False,sort_keys=True))")
        for flags in ([], ['-O']):
            api = subprocess.run([sys.executable, '-B']+flags+['-c', code], cwd='/', capture_output=True,
                                 text=True, timeout=30, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(api.returncode == 0 and not api.stderr, 'isolated API failed '+api.stderr)
            results.append(strict(api.stdout))
            cli = subprocess.run([sys.executable, '-B']+flags+[str(target/FILES[1])], cwd='/', capture_output=True,
                                 text=True, timeout=30, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(cli.returncode == 0 and not cli.stdout and not cli.stderr, 'isolated CLI failed '+cli.stderr)
        require(results[0] == results[1], 'normal/optimized mismatch')
        require(before == {p: (target/p).read_bytes() for p in FILES}, 'isolated mutation')
        require({p.name for p in target.iterdir()} == set(FILES), 'exact four-file membership')
        return {'status': 'passed', 'files': 4, 'cwd': '/', 'normal_and_optimized_API_CLI': True,
                'no_mutation': True, 'summary': results[0]}


if __name__ == '__main__':
    check()
