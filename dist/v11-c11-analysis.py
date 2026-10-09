"""Original Alder-Beacon run, sale and funded intervention teaching model.

Two funders act once; three runner counts exhaust the symmetric game. The
uniform-price auction, priorities, collateral rights and resolution are stated
fictional contracts. No market data, legal authority or probability is inferred.
run(data) is quiet/nonmutating. Only the CLI reads/writes explicit local files.
"""
import argparse
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
import json
from pathlib import Path
import re
import sys

SCHEMA = 'v11-c11-alder-beacon-1'
PROVENANCE = 'Original synthetic Alder-Beacon crisis game; no observed institution, empirical probability, national legal power or real intervention.'
NUMBER = re.compile(r'(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?\Z')
IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,39}\Z')
BAND = D('1e-24')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, label):
    require(type(value) is dict and set(value) == set(names.split()), label + ': exact fields required')


def number(value, low, high, label):
    require(type(value) is str and NUMBER.fullmatch(value) is not None, label + ': bounded unsigned plain decimal string required')
    result = F(value)
    require(low <= result <= high, label + ': outside range')
    return result


def identifier(value, label):
    require(type(value) is str and IDENTIFIER.fullmatch(value) is not None, label + ': invalid identifier')


def validate(data):
    fields(data, 'schema provenance bank beacon market policy terminal_states', 'input')
    require(data['schema'] == SCHEMA and data['provenance'] == PROVENANCE, 'unknown schema or provenance')
    b = data['bank']; fields(b, 'cash asset_units retail_due funder_principal wait_multiplier network_due opening_equity', 'bank')
    c = number(b['cash'], 0, 10000, 'bank cash')
    n = number(b['asset_units'], 1, 1000, 'asset units')
    e = number(b['retail_due'], 0, 1000, 'retail due')
    f = number(b['funder_principal'], F(1,100), 1000, 'each funder principal')
    number(b['wait_multiplier'], 1, F(3,2), 'wait multiplier')
    k = number(b['network_due'], 0, 1000, 'network due')
    equity = number(b['opening_equity'], 0, 20000, 'opening equity')
    require(c >= e, 'opening usable cash must fully fund the retail obligation')
    market = data['market']; fields(market, 'intercept impact benchmark_terminal_value', 'market')
    p0 = number(market['intercept'], F(1,100), 10, 'auction intercept')
    impact = number(market['impact'], 0, 1, 'auction impact')
    number(market['benchmark_terminal_value'], 0, 10, 'benchmark terminal payoff')
    require(2*impact*n <= p0, 'auction revenue must be increasing on the whole unpledged domain')
    require(c+n*p0 == e+2*f+k+equity, 'Alder opening principal balance sheet must reconcile')
    beacon = data['beacon']; fields(beacon, 'cash customer_due opening_equity', 'beacon')
    bc = number(beacon['cash'], 0, 10000, 'Beacon cash')
    bd = number(beacon['customer_due'], 0, 10000, 'Beacon customer due')
    be = number(beacon['opening_equity'], 0, 20000, 'Beacon opening equity')
    require(bc+k == bd+be, 'Beacon opening claim balance sheet must reconcile')
    policy = data['policy']; fields(policy, 'public_cash advance_fraction line_caps resolution_bridge_cap', 'policy')
    public = number(policy['public_cash'], 0, 10000, 'prepositioned taxpayer cash')
    number(policy['advance_fraction'], F(1,100), 1, 'advance fraction')
    require(type(policy['line_caps']) is list and 1 <= len(policy['line_caps']) <= 4, 'one to four alternative line caps required')
    caps = [number(x, 0, public, 'line cap') for x in policy['line_caps']]
    require(len(set(caps)) == len(caps), 'line caps must be distinct')
    number(policy['resolution_bridge_cap'], 0, public, 'resolution bridge cap')
    states = data['terminal_states']
    require(type(states) is list and 1 <= len(states) <= 4, 'one to four terminal stress states required')
    labels = set()
    for row in states:
        fields(row, 'label unit_payoff', 'terminal state')
        identifier(row['label'], 'state label')
        require(row['label'] not in labels, 'duplicate state label'); labels.add(row['label'])
        number(row['unit_payoff'], 0, 10, 'terminal unit payoff')


def decimal(x):
    if isinstance(x, F):
        return D(x.numerator) / D(x.denominator)
    return D(x)


def serial(value):
    if isinstance(value, D):
        require(value.is_finite(), 'nonfinite output')
        text = format(value, '.40f').rstrip('0').rstrip('.')
        return '0' if text in ('', '-0') else text
    if type(value) is dict:
        return {key: serial(item) for key, item in value.items()}
    if type(value) is list:
        return [serial(item) for item in value]
    return value


def beacon_cash(data, receipt1, receipt2, bridge):
    bc = decimal(data['beacon']['cash']); due = decimal(data['beacon']['customer_due'])
    paid1 = min(due, bc+receipt1+bridge)
    cash1 = bc+receipt1+bridge-paid1
    available2 = cash1+receipt2
    repaid = min(bridge, available2)
    paid2 = min(due-paid1, available2-repaid)
    equity = available2-repaid-paid2
    loss = due-paid1-paid2
    network_loss = decimal(data['bank']['network_due'])-receipt1-receipt2
    attribution = decimal(data['beacon']['opening_equity'])-equity+loss+bridge-repaid
    return {'receipt_cutoff1': receipt1, 'receipt_cutoff2': receipt2,
            'bridge_draw': bridge, 'customer_paid_cutoff1': paid1,
            'customer_missed_cutoff1': due-paid1, 'customer_paid_cutoff2': paid2,
            'customer_terminal_loss': loss, 'bridge_repayment': repaid,
            'public_bridge_loss': bridge-repaid, 'equity_terminal': equity,
            'network_asset_loss': network_loss, 'loss_attribution_residual': attribution-network_loss}


def opening(data, cap, runners):
    """Exact rational branch choice; one monotone uniform-price sale."""
    b, market, policy = data['bank'], data['market'], data['policy']
    c, n, e, f, k = (F(b[key]) for key in ('cash','asset_units','retail_due','funder_principal','network_due'))
    p0, impact = F(market['intercept']), F(market['impact'])
    advance = F(policy['advance_fraction'])*p0
    need = max(e+runners*f+k-c, F(0))
    loan = min(need, F(cap), advance*n)
    pledged = loan/advance
    maximum = n-pledged
    target = max(need-loan, F(0))
    max_proceeds = p0*maximum-impact*maximum**2
    if target >= max_proceeds:
        sale, proceeds = decimal(maximum), decimal(max_proceeds)
        regime = 'all_free_assets' if target > max_proceeds else 'exact_free_asset_boundary'
    elif target == 0:
        sale = proceeds = D(0); regime = 'no_sale'
    elif impact == 0:
        sale, proceeds = decimal(target/p0), decimal(target); regime = 'constant_price'
    else:
        discriminant = decimal(p0*p0-4*impact*target)
        sale = 2*decimal(target)/(decimal(p0)+discriminant.sqrt())
        proceeds = decimal(target); regime = 'interior_monotone_root'
    price = decimal(p0)-decimal(impact)*sale
    cash = decimal(c+loan)+proceeds
    retail = decimal(e); cash -= retail
    runner_due = decimal(runners*f); paid_runners = min(runner_due, cash); cash -= paid_runners
    paid_network = min(decimal(k), cash); cash -= paid_network
    private_principal_left = decimal(2*f+k)-paid_runners-paid_network
    marked_assets = cash+price*(decimal(n)-sale)
    marked_equity = marked_assets-private_principal_left-decimal(loan)
    identity = decimal(c)+price*decimal(n)-decimal(e+2*f+k)
    require(abs(price*sale-proceeds) < D('1e-60'), 'auction numerical residual')
    require(abs(marked_equity-identity) < D('1e-60'), 'mark identity residual')
    return {'runners': runners, 'loan': decimal(loan), 'pledged_units': decimal(pledged),
            'free_units': decimal(maximum), 'sale_units': sale, 'sale_price': price,
            'sale_proceeds': proceeds, 'sale_regime': regime,
            'retail_paid': retail, 'runners_paid': paid_runners,
            'runner_unpaid': runner_due-paid_runners, 'network_paid': paid_network,
            'network_unpaid': decimal(k)-paid_network, 'cash_remaining': cash,
            'retained_units': decimal(n)-sale, 'marked_assets': marked_assets,
            'principal_marked_equity': marked_equity,
            'assets_to_equity': marked_assets/marked_equity if marked_equity > BAND else None,
            'cash_residual': decimal(c+loan)+proceeds-retail-paid_runners-paid_network-cash,
            'sale_residual': price*sale-proceeds}


def finish(data, row, value):
    b = data['bank']; m = row['runners']; v = decimal(value)
    f = decimal(b['funder_principal']); multiplier = decimal(b['wait_multiplier'])
    waiting_due = (2-m)*f*multiplier
    available = row['cash_remaining']+v*row['retained_units']
    public_repaid = min(row['loan'], available)
    remainder = available-public_repaid
    private_due = waiting_due+row['runner_unpaid']+row['network_unpaid']
    recovery = min(D(1), remainder/private_due) if private_due else D(1)
    wait_paid = recovery*waiting_due
    late_runner = recovery*row['runner_unpaid']
    late_network = recovery*row['network_unpaid']
    shareholder = remainder-wait_paid-late_runner-late_network
    private_loss = private_due-wait_paid-late_runner-late_network
    public_loss = row['loan']-public_repaid
    buyer_gain = v*row['sale_units']-row['sale_proceeds']
    interest = (2-m)*f*(multiplier-1)
    fundamental_loss = decimal(b['asset_units'])*(decimal(data['market']['intercept'])-v)
    attribution = decimal(b['opening_equity'])-shareholder+private_loss+public_loss
    require(abs(attribution-fundamental_loss-interest-buyer_gain) < D('1e-60'), 'Alder loss attribution residual')
    beacon = beacon_cash(data, row['network_paid'], late_network, D(0))
    buyer_initial = decimal(b['asset_units'])*decimal(data['market']['intercept'])
    buyer_terminal = buyer_initial+buyer_gain
    resources = decimal(b['cash'])+decimal(data['beacon']['cash'])+decimal(data['policy']['public_cash'])+buyer_initial+v*decimal(b['asset_units'])
    recipients = (row['retail_paid']+row['runners_paid']+late_runner+wait_paid+shareholder
                  +beacon['customer_paid_cutoff1']+beacon['customer_paid_cutoff2']+beacon['equity_terminal']
                  +decimal(data['policy']['public_cash'])-public_loss+buyer_terminal)
    require(abs(recipients-resources) < D('1e-60'), 'consolidated resource residual')
    return {'unit_payoff': v, 'estate_available': available, 'public_repayment': public_repaid,
            'public_loss': public_loss, 'public_cash_terminal': decimal(data['policy']['public_cash'])-public_loss,
            'private_due': private_due, 'private_recovery_fraction': recovery,
            'waiters_paid': wait_paid, 'runners_paid_late': late_runner, 'network_paid_late': late_network,
            'private_claim_loss': private_loss, 'Alder_equity_terminal': shareholder,
            'runner_payoff_each': (row['runners_paid']+late_runner)/m if m else None,
            'waiter_payoff_each': wait_paid/(2-m) if m < 2 else None,
            'buyer_gain': buyer_gain, 'waiting_interest_due': interest,
            'buyer_initial_cash': buyer_initial, 'buyer_cash_after_sale': buyer_initial-row['sale_proceeds'],
            'buyer_terminal_wealth': buyer_terminal,
            'fundamental_asset_loss': fundamental_loss,
            'loss_attribution_residual': attribution-fundamental_loss-interest-buyer_gain,
            'estate_residual': available-public_repaid-wait_paid-late_runner-late_network-shareholder,
            'consolidated_resources': resources, 'consolidated_recipient_wealth': recipients,
            'consolidated_resource_residual': recipients-resources, 'beacon': beacon}


def game(payoffs):
    # Payoff differences for running versus waiting, conditional on the other.
    d0 = payoffs[1]['runner_payoff_each']-payoffs[0]['waiter_payoff_each']
    d1 = payoffs[2]['runner_payoff_each']-payoffs[1]['waiter_payoff_each']
    strict = []; candidates = []
    if d0 < -BAND: strict.append('WW')
    if d1 > BAND: strict.append('RR')
    if d0 > BAND and d1 < -BAND: strict.extend(['RW','WR'])
    if d0 <= BAND: candidates.append('WW')
    if d1 >= -BAND: candidates.append('RR')
    if d0 >= -BAND and d1 <= BAND: candidates.extend(['RW','WR'])
    mixed = -d0/(d1-d0) if ((d0 < -BAND and d1 > BAND) or (d0 > BAND and d1 < -BAND)) else None
    return {'run_minus_wait_if_other_waits': d0, 'run_minus_wait_if_other_runs': d1,
            'strict_pure_equilibria': strict, 'weak_pure_candidates_with_numeric_band': candidates,
            'symmetric_mixed_run_probability': mixed,
            'near_indifference_unresolved': abs(d0) <= BAND or abs(d1) <= BAND,
            'numerical_band': BAND,
            'scope': 'Two strategic funders, risk-neutral date2 consumption and a stipulated benchmark asset payoff. A mixed strategy is not an empirical crisis frequency. Near-band weak candidates are unresolved, not proved exact indifference; no equilibrium selection or global welfare theorem.'}


def resolution(data, value):
    b = data['bank']; f = decimal(b['funder_principal']); k = decimal(b['network_due'])
    retail = decimal(b['retail_due']); retained_cash = decimal(b['cash'])-retail
    estate = retained_cash+decimal(b['asset_units'])*decimal(value)
    claims = 2*f+k
    fraction = min(D(1), estate/claims)
    funders = 2*f*fraction; network = k*fraction
    equity = estate-funders-network
    needed_bridge = max(decimal(data['beacon']['customer_due'])-decimal(data['beacon']['cash']), D(0))
    bridge = min(needed_bridge, decimal(data['policy']['resolution_bridge_cap']))
    beacon = beacon_cash(data, D(0), network, bridge)
    buyer_cash = decimal(b['asset_units'])*decimal(data['market']['intercept'])
    public_terminal = decimal(data['policy']['public_cash'])-beacon['public_bridge_loss']
    resources = decimal(b['cash'])+decimal(data['beacon']['cash'])+decimal(data['policy']['public_cash'])+buyer_cash+decimal(value)*decimal(b['asset_units'])
    recipients = retail+funders+equity+beacon['customer_paid_cutoff1']+beacon['customer_paid_cutoff2']+beacon['equity_terminal']+public_terminal+buyer_cash
    require(abs(recipients-resources) < D('1e-60'), 'resolution consolidated resource residual')
    return {'unit_payoff': decimal(value), 'retail_paid_cutoff1': retail, 'retained_cash': retained_cash,
            'assets_sold': D(0), 'Alder_estate_cutoff2': estate,
            'restructured_principal_claims': claims, 'pari_passu_fraction': fraction,
            'funders_paid_cutoff2': funders, 'network_paid_cutoff2': network,
            'private_principal_loss': claims-funders-network, 'Alder_equity_terminal': equity,
            'cancelled_wait_premium_relative_to_WW': 2*f*(decimal(b['wait_multiplier'])-1),
            'estate_residual': estate-funders-network-equity,
            'beacon': beacon,
            'public_cash_terminal': public_terminal, 'buyer_unused_cash': buyer_cash,
            'consolidated_resources': resources, 'consolidated_recipient_wealth': recipients,
            'consolidated_resource_residual': recipients-resources}


def run(data):
    """Bounded, quiet, nonmutating result; amounts are 40-place decimal strings."""
    validate(data)
    with localcontext() as context:
        context.prec = 80
        alternatives = []
        for cap in data['policy']['line_caps']:
            profiles = []; benchmark = []
            for m in range(3):
                row = opening(data, cap, m)
                benchmark.append(finish(data, row, data['market']['benchmark_terminal_value']))
                profiles.append({'cutoff1': row, 'terminal_states': [dict(label=s['label'], **finish(data, row, s['unit_payoff'])) for s in data['terminal_states']]})
            alternatives.append({'line_cap': decimal(cap), 'profiles': profiles, 'benchmark_game': game(benchmark)})
        result = {'schema': SCHEMA+'-output', 'provenance': PROVENANCE,
                  'line_alternatives': alternatives,
                  'resolution_alternative': [dict(label=s['label'], **resolution(data, s['unit_payoff'])) for s in data['terminal_states']],
                  'limits': 'Each line cap and the resolution bridge are separate policies funded from the same declared prepositioned taxpayer cash, never concurrent free facilities. Loans have zero interest and senior estate repayment; pledged units cannot be sold. Resolution has stipulated timely authority, pays retail first, stays all other Alder principal to date2 and cancels the wait premium. Stress payoffs revalue a frozen date1 history and are not assigned probabilities or substituted silently into the benchmark game. Cash and asset-sale gains are transfers; no production destruction, empirical calibration, national law or policy optimum is proved.'}
        output = serial(result)
        json.dumps(output, allow_nan=False)
        return output


def load(path):
    require(path.stat().st_size <= 1000000, 'input exceeds one megabyte')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key '+key); result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON constant '+value)
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique, parse_constant=invalid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path(__file__).with_name('v11-c11-inputs.json'))
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('v11-c11-output.json'))
    args = parser.parse_args()
    try:
        for protected in (args.input, Path(__file__)):
            require(args.output.resolve() != protected.resolve(), 'output cannot overwrite input or implementation')
            require(not (args.output.exists() and protected.exists() and args.output.samefile(protected)), 'output cannot overwrite an input or implementation alias')
        text = json.dumps(run(load(args.input)), indent=2, allow_nan=False)+'\n'
        args.output.write_text(text, encoding='utf-8')
    except (ValueError, TypeError, KeyError, OSError, RecursionError, ArithmeticError) as error:
        print('error: '+str(error), file=sys.stderr); return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
