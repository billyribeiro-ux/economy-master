"""Quiet, bounded, independent finite checks for the V12-c02 chapter.

Standard library only. No network, random sampling, external model import or
file writes. Exact finite distributions and matrix arithmetic verify examples;
the probability theorems require the separately recorded full proof reading.
The final four-file package is portable together in any directory.
"""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
import json


BASE = Path(__file__).resolve().parents[1]
FILES = ("content/chapters/v12-c02.html", "scripts/check_v12_c02.py",
         "content/reviews/v12-c02-sources.json")


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0

    def equal(self, got, want, label):
        self.comparisons += 1
        if got != want:
            raise ValueError(label + ": " + repr(got) + " != " + repr(want))

    def reject(self, action, label):
        self.comparisons += 1
        try:
            action()
        except ValueError:
            self.rejections += 1
            return
        raise ValueError(label + ": missing explicit rejection")


def matrix(a):
    if not isinstance(a, (tuple, list)) or not a or not isinstance(a[0], (tuple, list)) or not a[0]:
        raise ValueError("Nonempty matrix required")
    width = len(a[0])
    if any(not isinstance(r, (tuple, list)) or len(r) != width for r in a):
        raise ValueError("Ragged matrix")
    if any(type(v) not in (int, F) for r in a for v in r):
        raise ValueError("Exact int/Fraction entries required; booleans and floats excluded")
    return [[F(v) for v in r] for r in a]


def tr(a):
    return list(map(list, zip(*a)))


def mul(a, b):
    a, b = matrix(a), matrix(b)
    if len(a[0]) != len(b):
        raise ValueError("Nonconformable product")
    return [[sum(u*v for u, v in zip(row, col)) for col in tr(b)] for row in a]


def add(a, b, sign=1):
    a, b = matrix(a), matrix(b)
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        raise ValueError("Nonconformable sum")
    return [[u+sign*v for u, v in zip(r, s)] for r, s in zip(a, b)]


def eye(n):
    return [[F(i == j) for j in range(n)] for i in range(n)]


def inverse(a):
    a = matrix(a)
    n = len(a)
    if len(a[0]) != n:
        raise ValueError("Square matrix required")
    z = [row+unit for row, unit in zip(a, eye(n))]
    for j in range(n):
        pivot = next((i for i in range(j, n) if z[i][j]), None)
        if pivot is None:
            raise ValueError("Singular matrix")
        z[j], z[pivot] = z[pivot], z[j]
        scale = z[j][j]
        z[j] = [v/scale for v in z[j]]
        for i in range(n):
            if i != j:
                scale = z[i][j]
                z[i] = [u-scale*v for u, v in zip(z[i], z[j])]
    return [row[n:] for row in z]


def pd(a):
    """Exact LDL pivots, not a floating eigenvalue claim."""
    a = matrix(a)
    if len(a) != len(a[0]) or a != tr(a):
        raise ValueError("Symmetric square covariance required")
    z = [r[:] for r in a]
    for k in range(len(z)):
        pivot = z[k][k]
        if pivot <= 0:
            raise ValueError("Positive-definite covariance required")
        for i in range(k+1, len(z)):
            for j in range(k+1, len(z)):
                z[i][j] -= z[i][k]*z[k][j]/pivot
    return True


def estimator(x, covariance=None):
    x = matrix(x)
    if covariance is None:
        w = eye(len(x))
    else:
        covariance = matrix(covariance)
        if len(covariance) != len(x):
            raise ValueError("Covariance/design dimension mismatch")
        pd(covariance)
        w = inverse(covariance)
    xtw = mul(tr(x), w)
    return mul(inverse(mul(xtw, x)), xtw)


def diag(v):
    return [[F(v[i]) if i == j else F(0) for j in range(len(v))] for i in range(len(v))]


def column(v):
    return [[F(t)] for t in v]


def mean_cov(vectors):
    vectors = matrix(vectors)
    n, k = len(vectors), len(vectors[0])
    means = [sum(v[j] for v in vectors)/n for j in range(k)]
    cov = [[sum((v[j]-means[j])*(v[l]-means[l]) for v in vectors)/n
            for l in range(k)] for j in range(k)]
    return means, cov


def hc(x, y, correction=0):
    if type(correction) is not int or correction not in (0, 1, 2, 3):
        raise ValueError("HC correction must be integer 0,1,2,3")
    a = estimator(x)
    beta = mul(a, column(y))
    residual = [u[0]-v[0] for u, v in zip(column(y), mul(x, beta))]
    h = mul(x, a)
    n, p = len(x), len(x[0])
    if correction and n <= p:
        raise ValueError("Positive residual degrees of freedom required")
    if correction in (2, 3) and any(h[i][i] == 1 for i in range(n)):
        raise ValueError("Unit leverage makes HC2/3 undefined")
    scales = [v*v for v in residual]
    if correction == 1:
        scales = [v*F(n, n-p) for v in scales]
    elif correction in (2, 3):
        scales = [v/(1-h[i][i])**(correction-1) for i, v in enumerate(scales)]
    return beta, residual, [h[i][i] for i in range(n)], mul(mul(a, diag(scales)), tr(a))


def bartlett(scores, lag):
    scores = matrix(scores)
    n, p = len(scores), len(scores[0])
    if type(lag) is not int or not 0 <= lag < n:
        raise ValueError("Integer bandwidth must satisfy 0 <= L < n")
    omega = [[sum(s[i]*s[j] for s in scores)/n for j in range(p)] for i in range(p)]
    for ell in range(1, lag+1):
        w = 1-F(ell, lag+1)
        for i in range(p):
            for j in range(p):
                omega[i][j] += w*sum(scores[t][i]*scores[t-ell][j]+scores[t-ell][i]*scores[t][j]
                                    for t in range(ell, n))/n
    return omega


def window_cov(scores, lag):
    """Independent moving-window representation with explicit zero extension."""
    n, p = len(scores), len(scores[0])
    windows = [[sum((scores[t][i] if 0 <= t < n else 0) for t in range(j-lag, j+1))
                for i in range(p)] for j in range(n+lag)]
    return [[sum(h[i]*h[j] for h in windows)/F(n*(lag+1)) for j in range(p)] for i in range(p)]


def group_feasible(y, groups, categories):
    if len(y) != len(groups) or not y or not categories or set(groups)-set(categories):
        raise ValueError("Finite group data required")
    mu = sum(map(F, y))/len(y)
    variances = []
    for h in categories:
        values = [F(v) for v, g in zip(y, groups) if g == h]
        if not values:
            return mu, None
        v = sum((t-mu)**2 for t in values)/len(values)
        if not v:
            return mu, None
        variances.append(v)
    w = {h: 1/v for h, v in zip(categories, variances)}
    return sum(w[h]*F(v) for v, h in zip(y, groups))/sum(w[h] for h in groups), variances


class Document(HTMLParser):
    VOID = {"br", "hr", "img", "input", "meta", "link"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links, self.sources, self.text = [], [], [], [], []
        self.examples = self.prompts = self.solutions = 0
        self.ol_depth = self.exercise_depth = self.solution_depth = 0
        self.detail_depth = 0
        self.solution_text = {}
        self.current_solution = None
        self.sections = {}
        self.section_id = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section":
            self.section_id = a.get("id")
            if self.section_id:
                self.sections[self.section_id] = []
        if "id" in a:
            self.ids.append(a["id"])
        if "data-source" in a:
            self.sources.append(a["data-source"])
        if tag == "a":
            self.links.append(a.get("href", ""))
        if "worked" in a.get("class", "").split():
            self.examples += 1
        if tag == "ol":
            self.ol_depth += 1
            if "exercises" in a.get("class", "").split():
                self.exercise_depth = self.ol_depth
        if tag == "details":
            self.detail_depth += 1
            if "solutions" in a.get("class", "").split():
                self.solution_depth = self.detail_depth
        if tag == "li":
            if self.exercise_depth == self.ol_depth and self.exercise_depth:
                self.prompts += 1
            if self.solution_depth:
                self.solutions += 1
                self.current_solution = a.get("data-solution-for")
                if not self.current_solution or self.current_solution in self.solution_text:
                    raise ValueError("Missing/duplicate solution target")
                self.solution_text[self.current_solution] = []
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError("Unbalanced markup at " + tag)
        if tag == "li":
            self.current_solution = None
        if tag == "ol":
            if self.exercise_depth == self.ol_depth:
                self.exercise_depth = 0
            self.ol_depth -= 1
        if tag == "details":
            if self.solution_depth == self.detail_depth:
                self.solution_depth = 0
            self.detail_depth -= 1
        if tag == "section":
            self.section_id = None

    def handle_data(self, data):
        self.text.append(data)
        if self.current_solution:
            self.solution_text[self.current_solution].append(data)
        if self.section_id:
            self.sections[self.section_id].append(data)


def numerical_check():
    a = Audit()
    page = Document()
    page.feed((BASE/FILES[0]).read_text())
    page.close()
    a.equal(page.stack, [], "balanced fragment")
    a.equal((page.examples, page.prompts, page.solutions), (6, 12, 12), "complete teaching package")
    a.equal(len(page.ids), len(set(page.ids)), "unique anchors")
    a.equal(set(page.solution_text), {"v12-c02-e"+str(i) for i in range(1, 13)}, "exact prompt/solution pairs")
    for target in page.solution_text:
        a.equal(target in page.ids, True, "solution target exists")
    a.equal(all(not x.startswith(("/", "projects/", "../")) for x in page.links), True, "flat reader links")
    sources = json.loads((BASE/FILES[2]).read_text())
    a.equal(set(page.sources), {s["id"] for s in sources["sources"]}, "all and only scoped source IDs")
    required = ("projection", "fixed-design", "gaussian-exact", "iid-hc", "feasible-weights", "clusters",
                "finite-dependence", "hac", "inference-audit", "exercises", "teach-retain", "sources-next")
    a.equal(set(page.sections), set(required), "complete proof/teaching sections")
    text = " ".join(page.text)
    a.equal("delayed" in text.lower(), True, "delayed practice")

    # The three-point projection: solve normal equations, then independently
    # enumerate raw population losses and score moments.
    z, y = (-1, 0, 1), (2, 2, 4)
    x = [[1, t] for t in z]
    beta = mul(estimator(x), column(y))
    weighted = mul(estimator(x, diag((1, F(1, 4), 1))), column(y))
    a.equal(beta, column((F(8, 3), 1)), "population projection")
    a.equal(weighted, column((F(7, 3), 1)), "weighted target")
    errors = [F(v)-beta[0][0]-beta[1][0]*t for t, v in zip(z, y)]
    errors_w = [F(v)-weighted[0][0]-weighted[1][0]*t for t, v in zip(z, y)]
    a.equal(errors, [F(1, 3), F(-2, 3), F(1, 3)], "projection residual law")
    a.equal([sum(errors), sum(t*e for t, e in zip(z, errors))], [0, 0], "projection score centering")
    a.equal([sum(w*e for w, e in zip((1, 4, 1), errors_w)),
             sum(w*t*e for w, t, e in zip((1, 4, 1), z, errors_w))], [0, 0], "weighted centering")
    a.equal(sum(e*e for e in errors)/3, F(2, 9), "optimal unweighted loss")
    a.equal(sum(e*e for e in errors_w)/3, F(1, 3), "changed-target loss")
    a.equal(mean_cov([[e, t*e] for t, e in zip(z, errors)])[1], diag((F(2, 9), F(2, 27))), "score covariance despite conditional misspecification")
    # Without an intercept, zero score cross moments need not mean covariance
    # orthogonality. This is a targeted counterexample to the repaired prose.
    no_intercept = mul(estimator([[1], [2]]), column((1, 1)))[0][0]
    no_intercept_errors = [1-no_intercept*t for t in (1, 2)]
    a.equal(no_intercept, F(3, 5), "no-intercept projection")
    a.equal(sum(t*e for t, e in zip((1, 2), no_intercept_errors)), 0, "zero cross moment")
    a.equal(mean_cov([[F(t), e] for t, e in zip((1, 2), no_intercept_errors)])[1][0][1],
            F(-3, 20), "nonzero covariance without intercept")

    # Partial regression with a regressor whose nonzero mean must be removed.
    t = (-2, -1, 0, 1, 2)
    nuisance = [[1, value] for value in t]
    remaining = column([value*value for value in t])
    full = [[1, value, value*value] for value in t]
    outcome = column((1, 2, 0, 6, 11))
    h = mul(nuisance, estimator(nuisance))
    m = add(eye(5), h, -1)
    a.equal(h, tr(h), "orthogonal hat symmetry")
    a.equal(mul(h, h), h, "projection idempotence")
    a.equal(mul(m, nuisance), [[0, 0] for _ in t], "nuisance residualization")
    partial = mul(estimator(mul(m, remaining)), mul(m, outcome))[0][0]
    a.equal(partial, mul(estimator(full), outcome)[2][0], "finite FWL coefficient identity")

    # Device estimators: realized outputs and finite sign enumeration provide
    # an independent covariance oracle, rather than reusing a variance formula.
    x1 = [[1], [1], [1]]
    cov = diag((1, 4, 9))
    aa = (estimator(x1), estimator(x1, cov), [[F(1, 14), F(2, 7), F(9, 14)]])
    estimates, variances = (F(14, 3), F(20, 7), F(45, 7)), (F(14, 9), F(36, 49), F(397, 98))
    for operator, estimate, variance in zip(aa, estimates, variances):
        a.equal(mul(operator, x1), [[F(1)]], "unbiased weight sum")
        a.equal(mul(operator, column((2, 4, 8)))[0][0], estimate, "device realized estimate")
        outcomes = [[mul(operator, column((s[0], 2*s[1], 3*s[2])))[0][0]] for s in product((-1, 1), repeat=3)]
        means, exact = mean_cov(outcomes)
        a.equal(means, [0], "finite device unbiasedness")
        a.equal(exact, [[variance]], "enumerated device covariance")
    a.equal(variances[0]-variances[1], F(362, 441), "efficiency improvement")
    a.equal(variances[2] > variances[0], True, "misspecified weighting costs precision")

    # A non-diagonal two-coefficient design tests the general matrix identity.
    design = [[1, -1], [1, 0], [1, 1]]
    loading = [[1, 0, 0], [1, 1, 0], [0, 1, 2]]
    sigma = mul(loading, tr(loading))
    ols, gls = estimator(design), estimator(design, sigma)
    d = add(ols, gls, -1)
    a.equal(pd(sigma), True, "non-diagonal covariance positive definite")
    a.equal(mul(d, design), [[0, 0], [0, 0]], "efficiency nullspace")
    difference = add(mul(mul(ols, sigma), tr(ols)), mul(mul(gls, sigma), tr(gls)), -1)
    a.equal(difference, mul(mul(d, sigma), tr(d)), "PSD difference identity")
    a.equal(all(difference[i][i] >= 0 for i in range(2)) and
            difference[0][0]*difference[1][1] >= difference[0][1]**2, True, "all principal minors nonnegative")
    for operator in (ols, gls):
        outcomes = [[r[0] for r in mul(operator, mul(loading, column(signs)))]
                    for signs in product((-1, 1), repeat=3)]
        a.equal(mean_cov(outcomes)[1], mul(mul(operator, sigma), tr(operator)), "enumerated multivariate covariance")

    # Four-row HC sample, including genuine leverage and units boundaries.
    x4 = [[1, t] for t in (-2, -1, 1, 2)]
    beta, residual, leverage, hc0 = hc(x4, [0, 2, 2, 8])
    a.equal(mul(tr(x4), x4), diag((4, 10)), "sample Gram")
    a.equal(beta, column((3, F(8, 5))), "sample coefficients")
    a.equal(residual, [F(t, 5) for t in (1, 3, -13, 9)], "sample residuals")
    a.equal(sum(v*v for v in residual), F(52, 5), "SSE")
    a.equal(leverage, [F(t, 20) for t in (13, 7, 7, 13)], "hat diagonal")
    a.equal(sum(leverage), 2, "projection trace")
    a.equal(hc0, [[F(13, 20), F(8, 25)], [F(8, 25), F(253, 1250)]], "all HC0 entries")
    a.equal(hc(x4, [0, 2, 2, 8], 2)[3][1][1], F(1102, 2275), "HC2 slope printed value")
    a.equal(hc(x4, [0, 2, 2, 8], 1)[3], [[2*t for t in r] for r in hc0], "HC1 normalization")
    a.equal(F(52, 5)/2/10, F(13, 25), "homoskedastic slope variance")
    transformed = hc([[1, 10*t] for t in (-2, -1, 1, 2)], [0, 2, 2, 8])
    a.equal(transformed[0], column((3, F(4, 25))), "units-adjusted coefficient")
    a.equal(transformed[1], residual, "units leave residuals fixed")
    a.equal(transformed[3], [[F(13, 20), F(4, 125)], [F(4, 125), F(253, 125000)]], "covariance units")
    singleton = hc([[1, 0], [1, 0], [1, 1]], [0, 2, 9])
    a.equal(singleton[2], [F(1, 2), F(1, 2), 1], "singleton leverage")
    a.equal(singleton[1][2], 0, "singleton always fits")

    # Non-Gaussian exact coverage: event enumeration, independent of t tables.
    covers = 0
    for signs in product((-1, 1), repeat=2):
        mean = F(sum(signs), 2)
        s2 = sum((v-mean)**2 for v in signs)
        # For any positive k, opposite signs center on zero; equal signs have
        # zero width and nonzero center. No approximate critical value needed.
        covers += int(mean == 0)
        a.equal(s2 == 0, signs[0] == signs[1], "zero-scale coverage boundary")
    a.equal(F(covers, 4), F(1, 2), "exact two-sign interval coverage")

    # Finite-group score laws: compute expected weighted scores and their squares.
    for p0, magnitude, want_ols, want_w in ((F(1, 2), (1, 3), 5, F(9, 5)),
                                          (F(1, 4), (2, 4), 13, F(64, 7))):
        law = [(prob/2, sign*mag, F(1, mag*mag))
               for prob, mag in zip((p0, 1-p0), magnitude) for sign in (-1, 1)]
        qw = sum(prob*w for prob, e, w in law)
        a.equal(sum(prob*e for prob, e, w in law), 0, "centered original score")
        a.equal(sum(prob*w*e for prob, e, w in law), 0, "centered weighted score")
        a.equal(sum(prob*e*e for prob, e, w in law), want_ols, "OLS group variance")
        a.equal(sum(prob*(w*e/qw)**2 for prob, e, w in law), want_w, "influence-based feasible oracle variance")
    a.equal(group_feasible([6, 8, 4, 10], [0, 0, 1, 1], (0, 1)), (F(7), [F(1), F(9)]), "feasible finite observed variances")
    a.equal(group_feasible([6, 8], [0, 0], (0, 1)), (F(7), None), "absent-group fallback")
    a.equal(group_feasible([7, 7, 7, 7], [0, 0, 1, 1], (0, 1)), (F(7), None), "zero-variance fallback")

    # Entire cluster law and two-cluster sampling distribution: 64 outcomes.
    team_law = [[3*a0+b, 3*a0+c] for a0, b, c in product((-1, 1), repeat=3)]
    a.equal(mean_cov(team_law)[1], [[10, 9], [9, 10]], "within-team covariance")
    a.equal(mean_cov([[sum(v)] for v in team_law])[1], [[38]], "cluster score variance")
    means, cr_values, hc_values = [], [], []
    for first, second in product(team_law, repeat=2):
        rows = first+second
        center = F(sum(rows), 4)
        means.append([center])
        cr = sum((sum(pair)-2*center)**2 for pair in (first, second))/16
        hh = sum((v-center)**2 for v in rows)/16
        cr_values.append(cr)
        hc_values.append(hh)
        a.equal(cr >= 0 and hh >= 0, True, "finite sandwich PSD")
    a.equal(mean_cov(means)[1], [[F(19, 4)]], "exact two-team grand-mean variance")
    a.equal(sum(cr_values)/64, F(19, 8), "CR0 expectation shrinkage")
    a.equal(2*sum(cr_values)/64, F(19, 4), "finite cluster correction unbiased here")
    a.equal(sum(hc_values)/64, F(21, 16), "HC0 misses common shock")
    observed = ((4, 2), (-2, -4), (4, 4), (-4, -4))
    a.equal(F(sum(sum(pair)**2 for pair in observed), 64), F(25, 8), "displayed CR0")
    a.equal(F(sum(v*v for pair in observed for v in pair), 64), F(13, 8), "displayed HC0")
    a.equal(F(38, 4*4), F(19, 8), "four-team true variance")
    a.equal((F(9)+F(1, 2))/20, F(19, 40), "twenty pairs")
    a.equal((F(9)+F(1, 4))/10, F(37, 40), "ten four-person teams")
    a.equal(F(10, 40), F(1, 4), "same wrong row variance")
    a.equal(F(0+12, 1+3), 3, "pooled-size target")
    a.equal(F(0+4, 2), 2, "cluster-mean target")
    a.equal(mean_cov([[-3], [3]])[1][0][0]/4, F(9, 4), "size-correlated pooled-score variance")
    a.equal(mean_cov([[0], [4]])[1][0][0], 4, "equal-cluster influence variance")

    # Serial covariance by finite innovation enumeration, not a fitted AR/MA
    # routine. Four economically distinct signs/degenerate limits are checked.
    serial = {}
    for rho in (F(1, 2), F(-1, 2), F(-1), F(1, 3)):
        triples = [[b+rho*c, a0+rho*b] for a0, b, c in product((-1, 1), repeat=3)]
        cv = mean_cov(triples)[1]
        gamma0, gamma1 = cv[0][0], cv[0][1]
        a.equal(gamma0, 1+rho*rho, "innovation marginal variance")
        a.equal(gamma1, rho, "innovation lag-one covariance")
        longrun = gamma0+2*gamma1
        a.equal(longrun, (1+rho)**2, "long-run variance")
        n = 4
        errors = [[signs[t]+rho*signs[t-1] for t in range(1, n+1)]
                  for signs in product((-1, 1), repeat=n+1)]
        a.equal(mean_cov([[sum(e)/n] for e in errors])[1][0][0],
                (n*gamma0+2*(n-1)*gamma1)/n**2, "finite serial mean variance")
        serial[rho] = (gamma0, gamma1, longrun)
        if rho == F(1, 2):
            for e in errors:
                center = sum(e)/n
                scores = [[v-center, F(i-1)*(v-center)] for i, v in enumerate(e)]
                for lag in (0, 1, 2):
                    b = bartlett(scores, lag)
                    a.equal(b, window_cov(scores, lag), "finite vector Bartlett identity")
                    a.equal(b[0][0] >= 0 and b[1][1] >= 0 and
                            b[0][0]*b[1][1] >= b[0][1]**2, True, "all two-dimensional PSD minors")
    a.equal((20*F(5, 4)+38*F(1, 2))/400, F(11, 100), "positive serial finite n20")
    a.equal((20*F(5, 4)-38*F(1, 2))/400, F(3, 200), "negative serial finite n20")
    a.equal(F(5, 4)+F(1, 2), F(7, 4), "fixed L1 positive limit")
    a.equal(F(5, 4)+F(4, 3)*F(1, 2), F(23, 12), "fixed L2 positive limit")
    a.equal(F(5, 4)-F(1, 2), F(3, 4), "fixed L1 negative limit")
    a.equal(F(10, 9)+F(1, 3), F(13, 9), "retention fixed L1")
    a.equal(serial[F(1, 3)][2], F(16, 9), "retention correct long-run")
    a.equal(F(1+4, 4), F(5, 4), "retention OLS")
    a.equal(F(4, 5)**2+4*F(1, 5)**2, F(4, 5), "retention GLS")
    scores = column((1, -2, 1))
    g0, g1, g2 = (F(2), F(-4, 3), F(1, 3))
    a.equal(g0+2*g1, F(-2, 3), "untapered negative example")
    a.equal(bartlett(scores, 1), [[F(2, 3)]], "small Bartlett L1")
    a.equal(bartlett(scores, 2), [[F(4, 9)]], "small Bartlett L2")
    for signs in product((-1, 1), repeat=5):
        e = [signs[t]-signs[t-1] for t in range(1, 5)]
        a.equal(sum(e), signs[-1]-signs[0], "degenerate limit telescoping identity")

    # The blocking bounds are illustrated on fixed finite calendars; the
    # asymptotic proof is read separately and is not claimed tested by a grid.
    for n, ell, gap in ((64, 4, 1), (125, 5, 3), (1000, 10, 0)):
        blocks, start = [], 0
        while start+ell <= n:
            blocks.append(set(range(start, start+ell)))
            start += ell+gap
        kept = set().union(*blocks)
        omitted = set(range(n))-kept
        a.equal(len(omitted) <= F(gap*n, ell)+ell+gap, True, "omitted index bound")
        a.equal(all(min(b)-max(prev) > gap for prev, b in zip(blocks, blocks[1:])), True, "retained blocks separated")
        a.equal(len(kept)+len(omitted), n, "no lost or duplicated indices")

    # Actual invalid-domain checks remain active under Python -O.
    bad = (
        (lambda: inverse([[1, 1], [1, 1]]), "rank failure"),
        (lambda: inverse([[1, 2]]), "nonsquare inverse"),
        (lambda: matrix([[1], [2, 3]]), "ragged input"),
        (lambda: matrix([[True]]), "boolean exact entry"),
        (lambda: matrix([[float('nan')]]), "nonfinite approximate entry"),
        (lambda: estimator([[1], [1]], [[1, 2], [2, 1]]), "indefinite covariance"),
        (lambda: estimator([[1], [1]], [[1, 1], [0, 1]]), "asymmetric covariance"),
        (lambda: estimator([[1], [1]], [[1]]), "wrong covariance size"),
        (lambda: estimator([[1, 1], [1, 1]]), "unidentified coefficient"),
        (lambda: hc([[1]], [2], 1), "no residual degrees of freedom"),
        (lambda: hc([[1, 0], [1, 0], [1, 1]], [0, 2, 9], 2), "HC2 unit leverage"),
        (lambda: hc([[1, 0], [1, 0], [1, 1]], [0, 2, 9], 3), "HC3 unit leverage"),
        (lambda: hc([[1], [1]], [0, 1], True), "boolean correction"),
        (lambda: bartlett([[1], [-1]], -1), "negative bandwidth"),
        (lambda: bartlett([[1], [-1]], 2), "excessive bandwidth"),
        (lambda: bartlett([[1], [-1]], True), "boolean bandwidth"),
        (lambda: group_feasible([1], [3], (0, 1)), "unknown group"),
    )
    for action, label in bad:
        a.reject(action, label)

    # Visible solution arithmetic is checked in the exact paired solution,
    # not merely against a hidden table or an occurrence elsewhere on the page.
    solutions = {
        1: ("8/3", "7/3", "2/9", "1/3", "1/9"),
        2: ("14/3", "14/9", "20/7", "36/49", "45/7", "397/98", "362/441"),
        3: ("52/5", "13/20", "8/25", "253/1250", "1102/2275", "4/25", "253/125000", "4/125"),
        4: ("1/2,1/2,1", "undefined"),
        5: ("1/2", "Non"),
        6: ("13", "7/64", "64/7", "centered"),
        7: ("19/40", "37/40", "1/4", "25/8", "13/8"),
        8: ("9/4", "variance 4", "≥2"),
        9: ("2/n²", "telescopes", "Cauchy–Schwarz"),
        10: ("−4/3", "1/3", "−2/3", "2/3", "4/9", "0<a<1/3"),
        11: ("5/4", "−1/2", "1/4", "3/200", "1/16", "3/4"),
        12: ("12 points", "two changes", "conditional Gaussian", "selection"),
    }
    # Case-sensitive exception below is intentionally a full-word reading
    # check; the finite-law equality above provides its numerical evidence.
    solutions[5] = ("1/2", "non-Gaussian")
    for number, phrases in solutions.items():
        solution = "".join(page.solution_text["v12-c02-e"+str(number)])
        for phrase in phrases:
            a.equal(phrase in solution, True, "visible exact solution "+str(number)+": "+phrase)
    sections = {
        "projection": ("8/3", "7/3", "different question"),
        "fixed-design": ("14/9", "36/49", "397/98", "362/441"),
        "iid-hc": ("13/20", "8/25", "253/1250", "fourth"),
        "feasible-weights": ("9/5", "5/9", "exceptional"),
        "clusters": ("19/(2G)", "25/8", "13/8", "19/8"),
        "finite-dependence": ("mutually independent", "third-order", "CDF"),
        "hac": ("11/100", "7/4", "23/12", "−2/3", "2/3", "4/9", "conservative"),
        "teach-retain": ("5/4", "4/5", "10/9", "1/3", "16/9", "13/9"),
    }
    for section, phrases in sections.items():
        visible = "".join(page.sections[section])
        for phrase in phrases:
            a.equal(phrase in visible, True, "visible worked/retention result "+section+": "+phrase)
    return {"chapter": "v12-c02", "state": "author checks passed; separate review recorded separately",
            "comparisons": a.comparisons, "worked_examples": 6, "solved_exercises": 12,
            "domain_rejections": a.rejections, "device_sign_states": 8,
            "cluster_sampling_states": 64, "serial_innovation_states_per_coefficient": 32,
            "vector_bartlett_cases": 96,
            "proof_limit": "Finite evidence and printed arithmetic only; general proofs require independent mathematical reading."}


def check():
    summary = numerical_check()
    review = json.loads((BASE/"content/reviews/v12-c02-author.json").read_text())
    bindings = review["payloads"]
    if set(bindings) != set(FILES):
        raise ValueError("Author record must bind exactly the three nonself payloads")
    for name in FILES:
        payload = (BASE/name).read_bytes()
        if bindings[name] != {"bytes": len(payload), "sha256": sha256(payload).hexdigest()}:
            raise ValueError("Author payload binding mismatch: " + name)
    summary["payload_bindings"] = len(FILES)
    summary["comparisons"] += len(FILES)
    return summary


if __name__ == "__main__":
    check()
