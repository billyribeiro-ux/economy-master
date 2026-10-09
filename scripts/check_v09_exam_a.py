"""Quiet independent reconstruction of all twenty original v09 Form A parts."""
from fractions import Fraction as F
from html.parser import HTMLParser
import json
from math import isclose, sqrt
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = ROOT / "content/assessments/parts/v09-exam-a.html"
SOURCES = ROOT / "content/reviews/v09-exam-a-sources.json"
COVERAGE = {
    "v09-a-q1a": ["v09-c01"], "v09-a-q1b": ["v09-c02"],
    "v09-a-q1c": ["v09-c03"], "v09-a-q1d": ["v09-c03"],
    "v09-a-q2a": ["v09-c04"], "v09-a-q2b": ["v09-c04"],
    "v09-a-q2c": ["v09-c05"], "v09-a-q2d": ["v09-c05"],
    "v09-a-q3a": ["v09-c06"], "v09-a-q3b": ["v09-c06"],
    "v09-a-q3c": ["v09-c07"], "v09-a-q3d": ["v09-c08"],
    "v09-a-q4a": ["v09-c09"], "v09-a-q4b": ["v09-c09"],
    "v09-a-q4c": ["v09-c10"], "v09-a-q4d": ["v09-c10"],
    "v09-a-q5a": ["v09-c11"], "v09-a-q5b": ["v09-c11", "v09-c12"],
    "v09-a-q5c": ["v09-c12"], "v09-a-q5d": ["v09-c12"],
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def demand(condition, message):
    if not condition:
        raise ValueError(message)


def exact_json(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: exact_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact_json(item) for item in value]
    return value


def moments(values, probabilities):
    demand(len(values) == len(probabilities) and len(values) > 0, "aligned finite states required")
    demand(all(p > 0 for p in probabilities) and sum(probabilities) == 1, "positive probabilities summing to one required")
    mean = sum((p * x for p, x in zip(probabilities, values)), F(0))
    variance = sum((p * (x - mean)**2 for p, x in zip(probabilities, values)), F(0))
    return mean, variance


def covariance(a, b, probabilities):
    ma = moments(a, probabilities)[0]
    mb = moments(b, probabilities)[0]
    return sum((p * (x - ma) * (y - mb) for p, x, y in zip(probabilities, a, b)), F(0))


def solve(matrix, rhs):
    n = len(rhs)
    demand(len(matrix) == n and all(len(row) == n for row in matrix), "square system required")
    work = [[F(x) for x in row] + [F(rhs[i])] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if work[i][col] != 0), None)
        demand(pivot is not None, "singular payoff system")
        work[col], work[pivot] = work[pivot], work[col]
        scale = work[col][col]
        work[col] = [x / scale for x in work[col]]
        for row in range(n):
            if row != col:
                scale = work[row][col]
                work[row] = [x - scale * y for x, y in zip(work[row], work[col])]
    return [work[i][-1] for i in range(n)]


def q1_check():
    start, value1, contribution, gross2, fee = F(100), F(110), F(90), F(11, 10), F(2)
    end = (value1 + contribution) * gross2 - fee
    period = [value1 / start - 1, end / (value1 + contribution) - 1]
    linked = (1 + period[0]) * (1 + period[1]) - 1
    # A unitization ledger independently removes the external contribution.
    units1, nav1 = F(100), F(11, 10)
    units_after = units1 + contribution / nav1
    final_nav = end / units_after
    require(end == 218 and period == [F(1, 10), F(9, 100)], "Q1a dated fee and flows")
    require(linked == F(199, 1000) == final_nav - 1 and end - start - contribution == 28, "Q1a unitized TWR and CU gain")
    probabilities = [F(1, 4)] * 4
    a = [F(x, 100) for x in (32, 32, -8, -8)]
    b = [F(x, 100) for x in (26, 6, 6, -14)]
    mean = [moments(x, probabilities)[0] for x in (a, b)]
    cov = [[covariance(x, y, probabilities) for y in (a, b)] for x in (a, b)]
    require(mean == [F(3, 25), F(3, 50)], "Q1b population means")
    require(cov == [[F(1, 25), F(1, 50)], [F(1, 50), F(1, 50)]], "Q1b full population covariance")
    equal = [(x + y) / 2 for x, y in zip(a, b)]
    require(moments(equal, probabilities)[1] == F(1, 40), "Q1b covariance-retaining diversification")
    determinant = cov[0][0] * cov[1][1] - cov[0][1]**2
    require(determinant == F(1, 2500) and cov[0][0] > 0, "Q1 covariance SPD")
    def score(w, shift=F(0), enforce=True):
        if enforce:
            demand(0 <= w <= F(3, 5), "mandate weight outside interval")
        returns = [w * (x + shift) + (1 - w) * y for x, y in zip(a, b)]
        mu, variance = moments(returns, probabilities)
        return mu - 2 * variance, mu, variance
    # Reconstruct each quadratic from direct state scores, not the printed polynomial.
    def coefficients(shift):
        j0, j1, j2 = [score(F(w), shift, False)[0] for w in (0, 1, 2)]
        quadratic = (j2 - 2 * j1 + j0) / 2
        linear = j1 - j0 - quadratic
        return j0, linear, quadratic
    nominal = coefficients(F(0))
    robust = coefficients(-F(1, 50))
    require(nominal == (F(1, 50), F(3, 50), -F(1, 25)), "Q1c independent objective polynomial")
    require(robust == (F(1, 50), F(1, 25), -F(1, 25)), "Q1d mean shift preserves covariance")
    stationary = -nominal[1] / (2 * nominal[2])
    worst_stationary = -robust[1] / (2 * robust[2])
    require(stationary == F(3, 4) and worst_stationary == F(1, 2), "Q1 stationary points")
    require(nominal[2] < 0 and nominal[1] + 2 * nominal[2] * F(3, 5) > 0, "Q1 constrained global derivative certificate")
    selected = score(F(3, 5))
    worst = score(F(1, 2), -F(1, 50))
    require(selected == (F(26, 625), F(12, 125), F(17, 625)), "Q1c chosen score/mean/variance")
    require(worst == (F(3, 100), F(2, 25), F(1, 40)), "Q1d chosen worst score/mean/variance")
    require(worst[0] - score(F(3, 5), -F(1, 50))[0] == F(1, 2500), "Q1d robust improvement")
    return {"q1a": {"ending": end, "period_returns": period, "TWR": linked, "gain": 28},
            "q1b": {"means": mean, "covariance": cov, "equal_variance": F(1, 40), "determinant": determinant},
            "q1c": {"stationary": stationary, "chosen": F(3, 5), "score_mean_variance": selected},
            "q1d": {"chosen": worst_stationary, "worst_score_mean_variance": worst}}, score


def q2_check():
    tolerance = F(1, 2) / 2 + F(1, 2) / 6
    coefficient, market_var, rf = 1 / tolerance, F(1, 25), F(1, 50)
    premium = coefficient * market_var
    beta = F(3, 50) / market_var
    required = rf + beta * premium
    alpha = (F(9, 50) - rf) - F(3, 2) * (F(7, 50) - rf)
    require((tolerance, coefficient, premium, rf + premium) == (F(1, 3), 3, F(3, 25), F(7, 50)), "Q2a aggregate tolerances")
    require(beta == F(3, 2) and required == F(1, 5) and alpha == -F(1, 50), "Q2b model and sample")
    # A compatible SPD covariance and supply witness checks that supplied CAPM moments coexist.
    sigma = [[F(4, 25), F(1, 100)], [F(1, 100), F(1, 25)]]
    market = [F(1, 3), F(2, 3)]
    sigma_market = [sum(sigma[i][j] * market[j] for j in range(2)) for i in range(2)]
    require(sigma_market == [F(3, 50), F(3, 100)], "CAPM covariance witness")
    require(sum(market[i] * sigma_market[i] for i in range(2)) == market_var, "CAPM market variance witness")
    risky = [[coefficient / g * w for w in market] for g in (2, 6)]
    require([(risky[0][j] + risky[1][j]) / 2 for j in range(2)] == market, "CAPM risky-market clearing")
    require(sum((1 - sum(x)) / 2 for x in risky) == 0, "CAPM zero net safe position")
    payoff = [[1, 2, 0], [1, 1, 1], [1, 0, 3]]
    prices = [F(1), F(9, 10), F(7, 5)]
    state_prices = solve(list(map(list, zip(*payoff))), prices)
    probability = [F(1, 4), F(1, 2), F(1, 4)]
    sdf = [q / p for q, p in zip(state_prices, probability)]
    require(state_prices == [F(1, 5), F(1, 2), F(3, 10)] and min(state_prices) > 0, "Q2c strictly positive state prices")
    require(sdf == [F(4, 5), F(1), F(6, 5)] and sum(p * m for p, m in zip(probability, sdf)) == 1, "Q2c SDF normalization")
    determinant = (1 * 3 - 1 * 0) - 2 * (1 * 3 - 1 * 1)
    require(determinant == -1, "Q2c complete payoff rank")
    claim = [3, 2, 4]
    replica = solve(payoff, claim)
    value = sum(q * x for q, x in zip(state_prices, claim))
    require(replica == [-5, 4, 3] and sum(h * p for h, p in zip(replica, prices)) == value == F(14, 5), "Q2d replica versus state-price value")
    quote = F(31, 10)
    holdings = [replica[0] + quote - value, replica[1], replica[2]]
    initial = sum(h * p for h, p in zip(holdings, prices)) - quote
    gains = [sum(h * x for h, x in zip(holdings, row)) - z for row, z in zip(payoff, claim)]
    require(initial == 0 and gains == [F(3, 10)] * 3, "Q2d financed arbitrage in every state")
    return {"q2a": {"aggregate_tolerance": tolerance, "risk_coefficient": coefficient, "market_premium": premium, "market_return": rf + premium},
            "q2b": {"beta": beta, "required_return": required, "sample_alpha": alpha},
            "q2c": {"state_prices": state_prices, "SDF": sdf, "determinant": determinant},
            "q2d": {"replica": replica, "fair_price": value, "arbitrage_initial_cost": initial, "arbitrage_payoffs": gains}}


def q3_check():
    probabilities = [F(1, 3)] * 3
    t = [F(-1), F(0), F(1)]
    h = [x*x - F(2, 3) for x in t]
    m = [1 - F(3, 10)*x - F(9, 20)*e for x, e in zip(t, h)]
    factor = [F(1, 5) + x for x in t]
    w = [F(9, 20) + 2*x + e/2 for x, e in zip(t, h)]
    mf, vf = moments(factor, probabilities)
    mw = moments(w, probabilities)[0]
    # Normal equations provide an independent population projection calculation.
    normal = [[1, mf], [mf, sum(p*x*x for p, x in zip(probabilities, factor))]]
    rhs = [mw, sum(p*x*y for p, x, y in zip(probabilities, factor, w))]
    intercept, beta = solve(normal, rhs)
    residual = [y - intercept - beta*x for x, y in zip(factor, w)]
    price = lambda values: sum(p*discount*x for p, discount, x in zip(probabilities, m, values))
    require(m == [F(23, 20), F(13, 10), F(11, 20)] and min(m) > 0, "Q3a full positive SDF support")
    require((intercept, beta) == (F(1, 20), F(2)), "Q3a normal-equation projection")
    require(residual == [F(1, 6), -F(1, 3), F(1, 6)], "Q3a nonlinear residual")
    require(moments(residual, probabilities)[0] == covariance(factor, residual, probabilities) == 0, "Q3a linear orthogonality")
    require(price(factor) == price(w) == 0 and covariance(m, residual, probabilities) == -F(1, 20), "Q3a zero claim prices with priced residual")
    require(residual[1] != residual[0] and len(set(factor)) == 3, "Q3a deterministic nonconstant residual dependence")
    g = [F(1, 10) + e for e in h]
    d = [y + F(3, 100) for y in w]
    risky_hedge = [y - 2*x for y, x in zip(w, factor)]
    exact_hedge = [y - 2*x - z/2 for y, x, z in zip(w, factor, g)]
    arbitrage = [y - 2*x - z/2 for y, x, z in zip(d, factor, g)]
    require(price(g) == 0 and price(d) == F(3, 100), "Q3b expanded factor span and D price")
    require(risky_hedge == [F(13, 60), -F(17, 60), F(13, 60)] and exact_hedge == [0, 0, 0], "Q3b residual risk versus exact cancellation")
    require(arbitrage == [F(3, 100)] * 3, "Q3b zero-cost constant-payoff arbitrage")
    # Enumerate all raw sign sequences, keeping the two orientations linked.
    wins = [bin(mask).count("1") for mask in range(2**11)]
    single = F(sum(k >= 9 for k in wins), len(wins))
    selected = F(sum(max(k, 11-k) >= 9 for k in wins), len(wins))
    require(single == F(67, 2048) and selected == F(67, 1024), "Q3c exact dependent-search tails")
    require(single < F(1, 20) < selected, "Q3c correction changes five-percent conclusion")
    require(selected != 1 - (1 - single)**2, "Q3c independent-tests counterfactual rejected")
    gross = [F(x, 1000) for x in (30, -5, 15, -10)]
    benchmark = [F(x, 1000) for x in (20, -10, 10, 0)]
    net = [x - F(1, 500) for x in gross]
    active = [x - b for x, b in zip(net, benchmark)]
    mean = sum(active) / 4
    variance = sum((x - mean)**2 for x in active) / 3
    tracking_error = sqrt(float(variance))
    ratio = float(mean) / tracking_error
    require(active == [F(x, 1000) for x in (8, 3, 3, -12)] and mean == F(1, 2000), "Q3d fee-base active returns")
    require(variance == F(3, 40000) and mean**2 / variance == F(1, 300), "Q3d sample denominator and squared IR")
    require(isclose(ratio, 0.057735026918962574, abs_tol=1e-14), "Q3d reported ratio")
    return {"q3a": {"SDF": m, "slope": beta, "intercept": intercept, "residual": residual, "W_price": price(w)},
            "q3b": {"F_only_hedge": risky_hedge, "D_fair_price": price(d), "arbitrage_payoffs": arbitrage},
            "q3c": {"fixed_tail": single, "searched_tail": selected, "sequences": len(wins)},
            "q3d": {"net_active": active, "mean": mean, "sample_variance": variance, "tracking_error": tracking_error, "IR": ratio}}


def private_cash(wealth):
    demand(wealth >= 0, "nonnegative initial wealth required")
    at0 = wealth - 40
    if at0 < 0:
        return {"funded": False, "failure_date": 0, "deficit": -at0}
    before_call = at0 * F(21, 20)
    after_call = before_call - 20
    if after_call < 0:
        return {"funded": False, "failure_date": 1, "deficit": -after_call, "after_initial": at0, "before_call": before_call}
    after_distribution = after_call + 8
    terminal = after_distribution * F(21, 20) + F(308, 5)
    return {"funded": True, "after_initial": at0, "before_call": before_call,
            "after_call": after_call, "after_distribution": after_distribution, "terminal": terminal}


def q4_check():
    probabilities = [F(1, 2)] * 2
    mus = [F(1, 25), -F(1, 50)]
    selected, conditional_means, conditional_vars, scores, all_payoffs = [], [], [], [], []
    def node_score(x, mu, enforce=True):
        if enforce:
            demand(0 <= x <= 100, "liability allocation outside available wealth")
        wealth = [100-x + x*(1+mu+F(1, 5)*u) for u in (-1, 1)]
        liability = [30+10*u for u in (-1, 1)]
        surplus = [w-d for w, d in zip(wealth, liability)]
        mean, variance = moments(surplus, probabilities)
        return mean-F(1, 20)*variance, mean, variance, surplus
    for mu in mus:
        j0, j1, j2 = [node_score(F(x), mu)[0] for x in (0, 1, 2)]
        a = (j2-2*j1+j0)/2
        b = j1-j0-a
        vertex = -b/(2*a)
        require(a < 0 and 0 <= vertex <= 100, "Q4a conditional strict-concavity certificate")
        score, mean, var, payoff = node_score(vertex, mu)
        selected.append(vertex); conditional_means.append(mean); conditional_vars.append(var)
        scores.append(score); all_payoffs.extend(payoff)
    require(selected == [60, 45], "Q4a liability-aware holdings")
    require(conditional_means == [F(362, 5), F(691, 10)] and conditional_vars == [4, 1], "Q4a conditional moments")
    mean, total_var = moments(all_payoffs, [F(1, 4)]*4)
    within = sum(conditional_vars)/2
    between = moments(conditional_means, probabilities)[1]
    initial_score = mean-F(1, 20)*total_var
    average_node = sum(scores)/2
    require(all_payoffs == [F(352, 5), F(372, 5), F(701, 10), F(681, 10)], "Q4b independent complete surplus support")
    require(total_var == within+between == F(2089, 400) and between == F(1089, 400), "Q4b total variance identity")
    require(initial_score == F(563911, 8000) and average_node == F(565, 8), "Q4b two different objectives")
    require(average_node-initial_score == F(1089, 8000) > 0, "Q4b omitted between-state penalty")
    gross_root = F(11, 10)
    cashflow = [-F(40), -F(12), F(308, 5)]
    npv_at_root = sum(cf/gross_root**t for t, cf in enumerate(cashflow))
    polynomial = lambda x: 40*x*x+12*x-F(308, 5)
    require(npv_at_root == polynomial(gross_root) == polynomial(-F(7, 5)) == 0, "Q4c both algebraic IRR roots")
    require(gross_root > 0 and 80*gross_root+12 > 0, "Q4c positive-gross root and monotonicity")
    # Compound gross contributions and distributions separately as a second route.
    fv_contributions = 40*F(21, 20)**2 + 20*F(21, 20)
    fv_distributions = 8*F(21, 20) + F(308, 5)
    excess = fv_distributions-fv_contributions
    npv = sum(cf/F(21, 20)**t for t, cf in enumerate(cashflow))
    require(excess == F(49, 10) and npv == excess/F(21, 20)**2 == F(40, 9), "Q4c gross-leg versus net-flow benchmark comparison")
    failed = private_cash(F(50))
    minimum = 40+20/F(21, 20)
    boundary = private_cash(minimum)
    below = private_cash(minimum-F(1, 100))
    require(not failed["funded"] and failed["failure_date"] == 1 and failed["deficit"] == F(19, 2), "Q4d gross call funding failure")
    require(minimum == F(1240, 21) and boundary["funded"] and boundary["after_call"] == 0, "Q4d exact funded boundary")
    require(not below["funded"] and below["failure_date"] == 1, "Q4d necessity of minimum reserve")
    return {"q4a": {"holdings": selected, "conditional_means": conditional_means, "conditional_variances": conditional_vars},
            "q4b": {"surplus_states": all_payoffs, "within_variance": within, "between_variance": between,
                     "total_variance": total_var, "initial_score": initial_score, "average_conditional_score": average_node},
            "q4c": {"net_cash": cashflow, "IRR": gross_root-1, "terminal_excess": excess, "NPV": npv},
            "q4d": {"wealth50": failed, "minimum_wealth": minimum, "boundary_ledger": boundary}}, node_score


def execution(fill=50, fee=F(1, 50)):
    demand(type(fill) is int and 0 <= fill <= 80, "fill exceeds original instruction")
    demand(fee >= 0, "fee must be nonnegative")
    actual_cash = 1000+fill*F(49, 5)-fill*fee
    demand(actual_cash >= 0, "sell fees cannot create borrowing")
    actual_shares = 200-fill
    actual_wealth = actual_cash+actual_shares*F(48, 5)
    paper_cash, paper_shares = F(1800), 120
    paper_wealth = paper_cash+paper_shares*F(48, 5)
    return actual_cash, actual_shares, actual_wealth, paper_cash, paper_shares, paper_wealth


def repair(n, temporary_exception):
    demand(type(n) is int and 0 <= n <= 30, "repair quantity outside original residual")
    demand(temporary_exception or n == 30, "full original instruction required without exception")
    cash = F(1489)+n*F(237, 25)
    shares = 150-n
    exposure = (shares-120)*F(48, 5)
    variance = exposure**2/F(100)
    wealth = cash+shares*F(48, 5)
    return {"cash": cash, "shares": shares, "active_exposure": exposure, "variance": variance,
            "wealth": wealth, "shortfall": 2952-wealth, "unfilled": 30-n,
            "hard_limits": cash >= 1600 and variance <= 400}


def q5_check():
    d, price, arrival, later, decision = -1, F(49, 5), F(99, 10), F(48, 5), F(10)
    spreads = [2*d*(price-arrival), 2*d*(price-later), 2*d*(later-arrival)]
    components = [d*80*(arrival-decision), d*50*(price-arrival), d*30*(later-arrival), F(1)]
    require(spreads == [F(1, 5), -F(2, 5), F(3, 5)] and spreads[0] == spreads[1]+spreads[2], "Q5a signed spread identity")
    require(components == [8, 5, 9, 1] and sum(components) == 23, "Q5a target shortfall decomposition")
    cash, shares, wealth, bcash, bshares, bwealth = execution()
    require((cash, shares, wealth, bcash, bshares, bwealth) == (1489, 150, 2929, 1800, 120, 2952), "Q5b actual/paper dated ledgers")
    require(bwealth-wealth == sum(components), "Q5b independently reconstructed wealth shortfall")
    active = (shares-bshares)*later
    # A two-state witness +/-10% proves the prospective CU active variance directly.
    differences = [cash+shares*later*(1+r)-(bcash+bshares*later*(1+r)) for r in (-F(1, 10), F(1, 10))]
    mean, variance = moments(differences, [F(1, 2)]*2)
    require(active == 288 and mean == -23 and variance == F(20736, 25), "Q5b constant loss versus future active risk")
    require(cash < 1600 and variance > 400, "Q5b both hard-limit breaches")
    rows = [repair(n, True) for n in range(31)]
    admitted = [n for n, row in enumerate(rows) if row["hard_limits"]]
    require(min(admitted) == 12 and not rows[11]["hard_limits"], "Q5c exhaustive minimal integer certificate")
    selected = rows[12]
    require(selected["cash"] == F(40069, 25) and selected["shares"] == 138 and selected["wealth"] == F(73189, 25), "Q5c funded repair ledger")
    require(selected["variance"] == F(186624, 625) and selected["unfilled"] == 18, "Q5c restored risk retains incomplete target")
    require(rows[10]["variance"] <= 400 and rows[10]["cash"] < 1600, "Q5c risk-only repair does not fund cash floor")
    complete = repair(30, False)
    require(complete["cash"] == F(8867, 5) and complete["wealth"] == F(14627, 5), "Q5d full completion ledger")
    require(complete["shares"] == 120 and complete["variance"] == 0 and complete["shortfall"] == F(133, 5), "Q5d zero active risk retains cash shortfall")
    require(selected["cash"]+18*F(237, 25) == complete["cash"] and selected["shares"]-18 == complete["shares"], "Q5d no double sale after temporary repair")
    return {"q5a": {"ES_RS_MC": spreads, "delay_execution_opportunity_fee": components, "IS": 23},
            "q5b": {"actual_cash_shares_wealth": [cash, shares, wealth], "paper_cash_shares_wealth": [bcash, bshares, bwealth], "active_variance": variance},
            "q5c": {"minimum_additional_shares": 12, "ledger": selected}, "q5d": complete}


def economic_domains(score, node_score):
    rejected = []
    def reject(label, call):
        try:
            call()
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError("contradictory economic domain accepted: " + label)
    reject("allocation-above-mandate-cap", lambda: score(F(61, 100)))
    reject("allocation-short-sale", lambda: score(-F(1, 100)))
    reject("probabilities-do-not-sum", lambda: moments([F(1), F(2)], [F(1, 4), F(1, 4)]))
    reject("zero-probability-claimed-support", lambda: moments([F(1), F(2)], [F(0), F(1)]))
    reject("singular-replication-not-complete", lambda: solve([[1, 1], [2, 2]], [1, 3]))
    reject("liability-hedge-requires-borrowing", lambda: node_score(F(101), F(1, 25)))
    reject("negative-initial-private-wealth", lambda: private_cash(-1))
    reject("execution-overfills-original-target", lambda: execution(81))
    reject("sell-fees-create-unfunded-account", lambda: execution(50, F(100)))
    reject("repair-sells-more-than-residual", lambda: repair(31, True))
    reject("partial-repair-without-authority", lambda: repair(12, False))
    # Infeasible private wealth is a reported decision outcome, not silently financed.
    require(private_cash(F(50))["funded"] is False, "value does not cure private funding failure")
    return rejected


class ExamParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = set()
        self.prompts = {}
        self.solutions = {}
        self.credit = {}
        self.links = []
        self.words = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            require(a["id"] not in self.ids, "unique exam anchors")
            self.ids.add(a["id"])
        require(tag != "h1", "assessment fragment must not duplicate page title")
        if "data-points" in a:
            require(tag == "li" and a.get("id") in COVERAGE, "scored semantic prompt")
            require(a["id"] not in self.prompts, "unique prompt score")
            self.prompts[a["id"]] = int(a["data-points"])
            require(not any(t == "details" for t, at in self.stack), "prompts before concealed solutions")
        if "data-solution-for" in a:
            key = a["data-solution-for"]
            require(tag == "li" and key in COVERAGE and key not in self.solutions, "one semantic answer per prompt")
            require(any(t == "details" and "solutions" in at.get("class", "").split() for t, at in self.stack), "answer inside details.solutions")
            self.solutions[key] = a.get("id")
            self.credit[key] = 0
        if "data-credit" in a:
            owners = [at["data-solution-for"] for t, at in self.stack if "data-solution-for" in at]
            require(len(owners) == 1, "credit allocated to exactly one solution")
            points = int(a["data-credit"])
            require(0 < points <= 5, "positive analytic credit")
            self.credit[owners[0]] += points
        if tag == "a":
            self.links.append(a.get("href", ""))
        if tag not in ("br", "hr", "img", "meta", "link", "input"):
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1][0] == tag, "balanced exam HTML: " + tag)
        self.stack.pop()

    def handle_data(self, data):
        self.words.append(data)


def structure_check():
    text = FRAGMENT.read_text()
    parsed = ExamParser()
    parsed.feed(text); parsed.close()
    require(not parsed.stack, "all exam elements closed")
    require(set(parsed.prompts) == set(parsed.solutions) == set(COVERAGE), "all twenty mapped prompts and answers")
    require(all(v == 5 for v in parsed.prompts.values()) and sum(parsed.prompts.values()) == 100, "100-point prompt total")
    require(all(v == 5 for v in parsed.credit.values()) and len(parsed.credit) == 20, "every analytic allocation totals five")
    for number in range(1, 6):
        require(sum(v for key, v in parsed.prompts.items() if key.startswith(f"v09-a-q{number}")) == 20, "each essential domain totals twenty")
    require({"form-a", "solutions-a"} <= parsed.ids, "assembly form and solution anchors")
    require("240 minutes" in text and "85/100" in text and "15/20" in text and "nonprogrammable" in text, "administration and advancement")
    require("carried earlier arithmetic error" in text and "Unresolved critical errors" in text, "error-carry-forward and critical remediation")
    require("eleven gross trade" in text and "67/2048" in text and "67/1024" in text, "final searched-sign prompt/solution version")
    covered = {c for chapters in COVERAGE.values() for c in chapters}
    require(covered == {f"v09-c{i:02}" for i in range(1, 13)}, "all twelve substantive chapter mappings")
    require({c + ".html" for c in covered} <= set(parsed.links), "all accepted chapter remediation routes")
    records = json.loads(SOURCES.read_text())
    catalog = {row["id"]: row for row in json.loads((ROOT / "content/sources.json").read_text())}
    require(len(records) == 11 and len({row["id"] for row in records}) == 11, "exact source proposal set")
    for row in records:
        require(row == catalog.get(row["id"]), "reused source record matches accepted scope exactly")
        require("sources.html#" + row["id"] in parsed.links, "source linked from exam")
    for path in (FRAGMENT, SOURCES, Path(__file__)):
        raw = path.read_bytes()
        require(raw.endswith(b"\n") and all(line.rstrip() == line for line in raw.splitlines()), "payload whitespace and final newline")
    return {"points": 100, "domains": 5, "parts": len(parsed.prompts), "mapped_solutions": len(parsed.solutions),
            "analytic_credit": parsed.credit, "coverage": COVERAGE, "reused_sources": 11,
            "words_including_solutions": len(re.findall(r"\S+", " ".join(parsed.words)))}


def check():
    """Return strict JSON without printing, network activity or file mutations."""
    q1, score = q1_check()
    q2 = q2_check()
    q3 = q3_check()
    q4, node_score = q4_check()
    q5 = q5_check()
    rejected = economic_domains(score, node_score)
    structure = structure_check()
    result = exact_json({"task": "v09-exam-a", "status": "passed", "groups": 6,
                         "checks": ["Dated returns and constrained robust allocation", "Equilibrium aggregation and complete-state pricing",
                                    "Nonlinear factor residual, dependent search and net performance", "Liability policy, total variance and gross private-call timing",
                                    "Signed whole-target execution and authorized policy repair", "All mapped scores, chapter routes and exact reused source scopes"],
                         "anchors": {**q1, **q2, **q3, **q4, **q5}, "rejected_economic_domains": rejected, "structure": structure})
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
