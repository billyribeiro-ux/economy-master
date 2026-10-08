"""Exact, original information/pricing/selection/behavior/funding teaching cases.

Quiet import and run(data). Fixed small contracts, not a trading system or an
empirical efficiency test. All probabilities and observations are synthetic.
"""
import argparse
from fractions import Fraction as F
import json
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONVENTIONS = {
    'currency': 'CU', 'returns': 'simple_total_decimal', 'taxes': 'none',
    'safe_gross': '1', 'physical_probabilities': 'separate_from_state_prices',
    'panel_unit': 'one_CU_gross_win_or_loss_per_trade',
    'selection': 'max_training_wins_then_lexical_id_before_holdout',
    'null': 'independent_fair_signs_with_independent_candidate_tests_only_for_family_formula',
    'behavior': 'subjective_mean_variance_of_terminal_cash_wealth',
    'funding': 'integer_pairs_long_unpledgeable_short_proceeds_locked_full_liquidation_on_failed_margin',
    'fee_timing': 'all_pair_trading_fees_paid_after_closing_cash_release',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) in (str, int), 'Use finite rational strings or integers, not floats/bools.')
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('Invalid rational number.') from exc


def pair(value):
    require(isinstance(value, list) and len(value) == 2, 'Exactly two states are required.')
    return [number(x) for x in value]


def probabilities(value):
    result = pair(value)
    require(min(result) > 0 and sum(result) == 1, 'Physical probabilities must be positive and sum to one.')
    return result


def dot(a, b):
    return sum((x*y for x, y in zip(a, b)), F(0))


def pricing_case(data):
    payoff, physical = pair(data['payoffs']), probabilities(data['physical'])
    require(payoff[0] > payoff[1] > 0, 'Pricing payoffs must be positive, high then low.')
    require([row['id'] for row in data['regimes']] == ['quiet', 'stress'], 'Keep both named regimes.')
    rows = []
    for row in data['regimes']:
        q = pair(row['state_prices'])
        require(min(q) > 0 and sum(q) == 1, 'At safe gross one, positive state prices must sum to one.')
        price = dot(q, payoff)
        sdf = [q[i]/physical[i] for i in range(2)]
        gross = [x/price for x in payoff]
        expected_payoff = dot(physical, payoff)
        mean = expected_payoff/price-1
        covariance = sum(physical[i]*(sdf[i]-1)*(gross[i]-1-mean) for i in range(2))
        rows.append({'regime': row['id'], 'price': price, 'state_prices': q,
                     'SDF': sdf, 'gross_returns': gross, 'expected_return': mean,
                     'expected_SDF': dot(physical, sdf),
                     'priced_gross_return': sum(physical[i]*sdf[i]*gross[i] for i in range(2)),
                     'SDF_return_covariance': covariance,
                     'financed_one_share_payoffs': [x-price for x in payoff]})
    return {'payoffs': payoff, 'physical_probabilities': physical, 'regimes': rows,
            'constant_quiet_benchmark_stress_residual': rows[1]['expected_return']-rows[0]['expected_return']}


def sign_tail(n, wins):
    return F(sum(comb(n, j) for j in range(wins, n+1)), 2**n)


def selection_case(data):
    rules, cost = data['rules'], number(data['cost_per_trade'])
    require(cost >= 0, 'Trading cost must be nonnegative.')
    require(isinstance(rules, list) and len(rules) == 20, 'The disclosed search contains exactly twenty rules.')
    require([r['id'] for r in rules] == [f'A{i:02d}' for i in range(1, 21)], 'Keep the complete ordered candidate universe.')
    rows = []
    for row in rules:
        for field, length in [('training', 12), ('holdout', 8)]:
            require(isinstance(row[field], str) and len(row[field]) == length and set(row[field]) <= {'+', '-'},
                    'Each candidate needs twelve training and eight holdout signs.')
        wins = row['training'].count('+')
        rows.append({'id': row['id'], 'training_wins': wins,
                     'training_gross_profit': F(2*wins-12), 'training_net_profit': 2*wins-12-12*cost,
                     'holdout_wins': row['holdout'].count('+')})
    selected = min(rows, key=lambda row: (-row['training_wins'], row['id']))
    tail = sign_tail(12, selected['training_wins'])
    family = 1-(1-tail)**len(rows)
    holdout_wins = selected['holdout_wins']
    return {'candidates': rows, 'selected_before_holdout': selected['id'],
            'selected_training_wins': selected['training_wins'],
            'selected_training_gross_profit': selected['training_gross_profit'],
            'selected_training_net_profit': selected['training_net_profit'],
            'single_prespecified_rule_tail': tail,
            'independent_family_tail': family, 'independent_family_tail_approx': float(family),
            'bonferroni_bound': min(F(1), len(rows)*tail),
            'frozen_holdout_wins': holdout_wins, 'frozen_holdout_tail': sign_tail(8, holdout_wins),
            'frozen_holdout_gross_profit': F(2*holdout_wins-8),
            'frozen_holdout_net_profit': 2*holdout_wins-8-8*cost,
            'inference_scope': 'One-sided fair-sign null; family equality requires independent candidate tests; no risk-adjusted return or empirical skill claim.'}


def event_case(data):
    times = [data[k] for k in ['prior_quote_minute', 'information_minute', 'entry_minute', 'exit_minute']]
    require(all(type(x) is int for x in times) and 0 <= times[0] < times[1] <= times[2] < times[3] < 1440,
            'Quote precedes release; execution cannot precede release; all times share one fictional day.')
    prior, entry_mid, ask, exit_mid, bid = [number(data[k]) for k in ['prior_mid', 'entry_mid', 'entry_ask', 'exit_mid', 'exit_bid']]
    entry_fee, exit_fee, information_fee = [number(data[k]) for k in ['entry_fee', 'exit_fee', 'information_fee']]
    require(min(prior, entry_mid, ask, exit_mid, bid) > 0 and ask >= entry_mid and bid <= exit_mid,
            'Positive quotes and the declared sides of the spread are required.')
    require(min(entry_fee, exit_fee, information_fee) >= 0 and bid > exit_fee, 'Fees must be nonnegative with positive net sale proceeds.')
    cost = ask+entry_fee+information_fee
    proceeds = bid-exit_fee
    return {'unavailable_prior_mid_to_exit_mid_return': exit_mid/prior-1,
            'postrelease_mid_to_mid_return': exit_mid/entry_mid-1,
            'entry_cash_including_information': cost, 'exit_cash_after_fee': proceeds,
            'net_profit': proceeds-cost, 'net_return_on_total_cash': proceeds/cost-1,
            'net_profit_if_information_free': proceeds-ask-entry_fee,
            'break_even_information_fee': proceeds-ask-entry_fee,
            'information_minutes_before_execution': times[2]-times[1]}


def posterior(prior, likelihood):
    require(0 < prior < 1 and all(0 < x < 1 for x in likelihood), 'Prior and signal likelihoods must be interior probabilities.')
    return prior*likelihood[0]/(prior*likelihood[0]+(1-prior)*likelihood[1])


def belief_equilibrium(beliefs, payoff, aversion, supply, cash):
    high, low = payoff
    means = [p*high+(1-p)*low for p in beliefs]
    variances = [p*(1-p)*(high-low)**2 for p in beliefs]
    curvature = [a*v for a, v in zip(aversion, variances)]
    price = (sum(means[i]/curvature[i] for i in range(2))-supply)/sum(1/k for k in curvature)
    require(low < price < high, 'Named equilibrium requires a strictly positive two-state pricing vector.')
    holdings = [(means[i]-price)/curvature[i] for i in range(2)]
    initial_units = supply/2
    cash_after_trade = [cash+price*(initial_units-x) for x in holdings]
    terminal_wealth = [[cash_after_trade[i]+holdings[i]*x for x in payoff] for i in range(2)]
    q_high = (price-low)/(high-low)
    return {'beliefs_high': beliefs, 'subjective_means': means, 'subjective_variances': variances,
            'risk_curvatures': curvature, 'price': price, 'holdings': holdings,
            'cash_after_trade': cash_after_trade, 'terminal_wealth': terminal_wealth,
            'one_supporting_state_price_vector': [q_high, 1-q_high]}


def behavior_case(data):
    prior = number(data['prior_high'])
    true = posterior(prior, pair(data['true_good_likelihoods']))
    optimistic = posterior(prior, pair(data['optimistic_good_likelihoods']))
    payoff, aversion = pair(data['payoffs']), pair(data['risk_aversion'])
    supply, cash = number(data['supply']), number(data['initial_cash_each'])
    require(payoff[0] > payoff[1] > 0 and min(aversion) > 0 and supply > 0 and cash >= 0,
            'Positive payoffs, risk aversions and supply, nonnegative cash required.')
    current = belief_equilibrium([true, optimistic], payoff, aversion, supply, cash)
    corrected = belief_equilibrium([true, true], payoff, aversion, supply, cash)
    gains = [current['price']-x for x in payoff]
    return {'true_posterior': true, 'optimistic_posterior': optimistic,
            'belief_equilibrium': current, 'correct_belief_counterfactual': corrected,
            'price_difference_from_counterfactual': current['price']-corrected['price'],
            'one_share_short_terminal_gains': gains,
            'physical_expected_short_gain': true*gains[0]+(1-true)*gains[1]}


def information_case(data):
    require(data['contract'] == 'one_unit_optional_buy_fixed_quote_before_signal_not_equilibrium',
            'This is a capped fixed-quote information contract, not an equilibrium model.')
    payoff, probability = pair(data['payoffs']), probabilities(data['probabilities'])
    price, fee = number(data['fixed_price']), number(data['fee'])
    require(min(payoff) >= 0 and min(payoff) < price < max(payoff) and fee >= 0,
            'Fixed quote lies strictly between nonnegative payoffs; information fee is nonnegative.')
    no_information = max(F(0), dot(payoff, probability)-price)
    contingent_gains = [max(F(0), x-price) for x in payoff]
    informed_gross = dot(contingent_gains, probability)
    value = informed_gross-no_information
    status = 'buy' if value > fee else ('indifferent' if value == fee else 'do_not_buy')
    return {'best_without_information': no_information, 'conditional_optional_gains': contingent_gains,
            'informed_expected_gain_before_fee': informed_gross, 'gross_value_of_information': value,
            'incremental_value_after_fee': value-fee, 'optimal_acquisition': status,
            'if_signal_fully_reprices_quote_incremental_value': -fee}


def funding_case(data):
    names = ['wealth', 'cheap_entry', 'dear_entry', 'maintenance_margin', 'convergence_quote',
             'divergence_cheap', 'divergence_dear', 'divergence_probability', 'total_closing_fee_per_pair']
    wealth, cheap, dear, margin, convergence, cheap1, dear1, chance, fee = [number(data[k]) for k in names]
    n = data['pairs']
    terminal = pair(data['terminal_common_payoffs'])
    require(type(n) is int and n >= 0, 'Pairs must be a nonnegative integer.')
    require(wealth >= 0 and dear > cheap > 0 and min(convergence, cheap1, dear1, *terminal) > 0,
            'Nonnegative wealth and positive prices/payoffs with a positive entry spread required.')
    require(0 <= margin <= 1 and 0 <= chance <= 1 and fee >= 0, 'Invalid margin, probability or closing fee.')
    require(dear1 > dear and dear1 > cheap1 and convergence <= dear,
            'Named stress widens the short-side call; convergence has no extra call.')
    entry_per_pair = cheap+margin*dear
    restricted = (1+margin)*dear*n
    topup = (1+margin)*(dear1-dear)*n
    stress_per_pair = entry_per_pair+(1+margin)*(dear1-dear)
    result = {'entry_capital_per_pair': entry_per_pair, 'stress_survival_capital_per_pair': stress_per_pair,
              'maximum_entry_pairs': int(wealth//entry_per_pair), 'maximum_stress_surviving_pairs': int(wealth//stress_per_pair),
              'requested_pairs': n, 'entry_capital_required': entry_per_pair*n}
    if wealth < entry_per_pair*n:
        result['status'] = 'entry_infeasible'
        return result
    free = wealth-entry_per_pair*n
    survival = free >= topup
    gain_at_convergence = (dear-cheap-fee)*n
    gain_at_divergence = gain_at_convergence if survival else ((cheap1-cheap)+(dear-dear1)-fee)*n
    require(min(wealth+gain_at_convergence, wealth+gain_at_divergence) >= 0,
            'Named case excludes insolvency or closing fees exceeding released cash.')
    result.update({'status': 'entered', 'initial_long_asset': cheap*n, 'initial_short_liability': dear*n,
                   'initial_locked_collateral': restricted, 'initial_free_cash': free,
                   'stress_long_mark': cheap1*n, 'stress_short_mark': dear1*n,
                   'stress_marked_equity_before_fees': wealth+((cheap1-cheap)+(dear-dear1))*n,
                   'stress_required_collateral': (1+margin)*dear1*n, 'stress_topup_required': topup,
                   'stress_margin_survives': survival,
                   'stress_action': 'hold_to_common_terminal_payoff' if survival else 'fully_close_both_legs_at_stress_quotes',
                   'free_cash_after_stress_topup_if_survives': free-topup if survival else None,
                   'total_fee_at_closing': fee*n,
                   'convergence_net_gain': gain_at_convergence, 'divergence_net_gain': gain_at_divergence,
                   'convergence_final_wealth': wealth+gain_at_convergence,
                   'divergence_final_wealth': wealth+gain_at_divergence,
                   'physical_expected_net_gain': (1-chance)*gain_at_convergence+chance*gain_at_divergence,
                   'common_terminal_payoffs': terminal,
                   'scope': 'Specified two-path quotes and binding contract; not an unrestricted no-arbitrage equilibrium.'})
    return result


def serialize(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(x) for x in value]
    return value


def run(data=None):
    if data is None:
        data = json.loads((HERE/'v09-c07-inputs.json').read_text(encoding='utf-8'))
    require(isinstance(data, dict) and data.get('case_id') == 'v09-c07-efficiency-1', 'Only the named small fixture is supported.')
    require(data.get('conventions') == CONVENTIONS, 'Contradictory return, information, rights, null or fee-timing label.')
    result = serialize({'case_id': data['case_id'], 'status': 'calculated',
                        'pricing': pricing_case(data['pricing']), 'selection': selection_case(data['selection']),
                        'event': event_case(data['event']), 'behavior': behavior_case(data['behavior']),
                        'information': information_case(data['information']), 'funding': funding_case(data['funding']),
                        'limits': ['Original invented populations, beliefs, sign panel and contracts; no empirical efficiency finding.',
                                   'State prices differ from physical probabilities; selected profits are not identified alpha.',
                                   'Belief counterfactual holds preferences/supply fixed; observed prices alone do not identify biased beliefs.',
                                   'Funding outcomes depend on interim calls, locked proceeds, no long collateral and after-release fees.',
                                   'Rational values remain exact strings; only the named family-tail approximation is floating point.']})
    json.dumps(result, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=HERE/'v09-c07-inputs.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(run(json.loads(args.input.read_text(encoding='utf-8'))), ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result, end='')


if __name__ == '__main__':
    main()
