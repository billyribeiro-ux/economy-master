#!/usr/bin/env python3
"""Rill: exact finite ledgers, Gaussian moment identities and GBM error analysis."""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction as F
from itertools import product
import json
from math import exp, expm1
from pathlib import Path
import re

CONTRACT = {
 'time_unit':'year','brownian_unit':'square root of year','price_unit':'CU',
 'law':'Brownian analytical statements and GBM moments use a supplied physical P law; no risk-neutral measure is inferred',
 'path':'Authored finite observations only; linear interpolation is a different finite-variation process',
 'cubature':'Independent three-point shocks match standard-normal moments through degree four only; not Gaussian paths'
}
PROVENANCE = 'Original authored rational observations and moment cubature; no market observations, random seed or simulated convergence proof.'


def need(ok, message):
    if not ok:raise ValueError(message)


def fields(obj, names):
    need(type(obj) is dict and set(obj)==set(names.split()),'missing or unknown input fields')


def number(v):
    need(type(v) is int or (type(v) is str and len(v)<=60 and re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*|\.[0-9]+)?',v)),
         'use integer or exact rational/decimal string, never bool or float')
    x=F(v);need(abs(x)<=10**6 and x.denominator<=10**6,'rational teaching bound exceeded');return x


def integers(v, upper):
    need(type(v) is list and 1<=len(v)<=12 and all(type(x) is int and 1<=x<=upper for x in v) and len(set(v))==len(v),
         'bounded nonempty distinct positive integer list required')
    return v


def validate(data):
    fields(data,'schema case provenance contract grid adapted_integrand chain_product gbm')
    need(data['schema']=='v10-c07-ito-1' and data['case']=='Rill stochastic-calculus workshop','fixed fixture identity')
    need(data['contract']==CONTRACT and data['provenance']==PROVENANCE,'fixed information/law/provenance contract')
    g=data['grid'];fields(g,'horizon increments blocks polygon_subdivisions theory_steps cubature_steps')
    T=number(g['horizon']);need(F(1,16)<=T<=2,'horizon between 1/16 and 2 years')
    values=g['increments'];need(type(values) is list and 2<=len(values)<=64 and len(values)&(len(values)-1)==0,'power-of-two path length from 2 through 64')
    need(all(abs(number(v))<=4 for v in values),'bounded authored increments')
    need(all(len(values)%n==0 for n in integers(g['blocks'],len(values))),'blocks must divide fine observation count')
    integers(g['polygon_subdivisions'],64);integers(g['theory_steps'],4096)
    need(type(g['cubature_steps']) is int and 1<=g['cubature_steps']<=7,'cubature horizon from 1 through 7 steps')
    fields(data['adapted_integrand'],'first_holding feedback')
    need(all(abs(number(v))<=10 for v in data['adapted_integrand'].values()),'bounded integrand coefficients')
    c=data['chain_product'];fields(c,'x0 x_drift x_diffusion y0 y_drift y_diffusion decay')
    need(all(abs(number(v))<=10 for v in c.values()) and number(c['decay'])>=0,'bounded affine coefficients and nonnegative decay')
    b=data['gbm'];fields(b,'initial_price drift diffusion euler_steps probe_time probe_increment')
    need(F(1,1000)<=number(b['initial_price'])<=10**6,'positive initial price')
    need(abs(number(b['drift']))<=F(1,2) and 0<=number(b['diffusion'])<=1,'bounded GBM drift/diffusion')
    integers(b['euler_steps'],4096)
    need(F(1,16)<=number(b['probe_time'])<=2 and abs(number(b['probe_increment']))<=4,'bounded numerical probe')


def path_ledger(increments, T):
    h=T/len(increments);w=F(0);left=right=quad=variation=F(0);rows=[]
    for k,v in enumerate(increments):
        before=w;w+=v;L=before*v;R=w*v
        left+=L;right+=R;quad+=v*v;variation+=abs(v)
        rows.append({'time':(k+1)*h,'increment':v,'W_before':before,'W_after':w,'left_gain':L,'right_gain':R})
    endpoint=(w*w-T)/2
    return {'steps':len(increments),'step':h,'rows':rows,'terminal_W':w,'squared_increment_sum':quad,
            'absolute_increment_sum':variation,'left_sum':left,'right_sum':right,'symmetric_sum':(left+right)/2,
            'brownian_endpoint_formula':endpoint,'left_minus_brownian_endpoint_formula':left-endpoint,
            'scope':'Finite authored observations; endpoint formula refers to a Brownian extension, not the ordinary integral of the polygon.'}


def gaussian_grid(T,n):
    sum_squares=T*T/n
    return {'steps':n,'step':T/n,'quadratic_sum_mean':T,'quadratic_sum_variance':2*sum_squares,
            'left_sum_mean':F(0),'left_sum_variance':(T*T-sum_squares)/2,
            'right_sum_mean':T,'right_sum_variance':(T*T+3*sum_squares)/2,
            'ito_W_integral_variance':T*T/2,'left_integral_mse':sum_squares/2}


def cubature(T,n):
    # z takes -1,0,+1; sqrt(3h)*z matches Gaussian moments through degree four.
    h=T/n;weights={-1:F(1,6),0:F(2,3),1:F(1,6)}
    total=meanQ=Q2=meanL=L2=meanR=R2=error2=WT2=WT4=F(0)
    for z in product((-1,0,1),repeat=n):
        weight=F(1)
        for v in z:weight*=weights[v]
        square=3*h*sum(z)**2;Q=3*h*sum(v*v for v in z);L=(square-Q)/2;R=(square+Q)/2
        target=(square-T)/2;total+=weight;meanQ+=weight*Q;Q2+=weight*Q*Q
        meanL+=weight*L;L2+=weight*L*L;meanR+=weight*R;R2+=weight*R*R
        error2+=weight*(L-target)**2;WT2+=weight*square;WT4+=weight*square*square
    return {'steps':n,'states':3**n,'probability_sum':total,'quadratic_sum_mean':meanQ,
            'quadratic_sum_variance':Q2-meanQ**2,'left_sum_mean':meanL,'left_sum_variance':L2-meanL**2,
            'right_sum_mean':meanR,'right_sum_variance':R2-meanR**2,'left_to_endpoint_mse':error2,
            'terminal_second_moment':WT2,'terminal_fourth_moment':WT4,
            'scope':'Degree-four moment cubature, not a Gaussian law or a Brownian existence/convergence proof.'}


def adapted(T, spec):
    a,b=number(spec['first_holding']),number(spec['feedback']);h=T/2
    variance=a*a*h+b*b*h*h
    fourth=3*h*h*(a**4+6*a*a*b*b*h+3*b**4*h*h)
    return {'switch_time':h,'mean':F(0),'variance':variance,'fourth_moment':fourth,
            'gaussian_fourth_if_same_variance':3*variance**2,
            'scope':'H=a on first half and H=b*W_(T/2) on second; true independent Brownian half-increments.'}


def chain(T,W,spec):
    x0,a,b,y0,c,d,k=[number(spec[key]) for key in ('x0','x_drift','x_diffusion','y0','y_drift','y_diffusion','decay')]
    x=x0+a*T+b*W;y=y0+c*T+d*W;e=exp(-float(k*T))
    return {'terminal_X':x,'terminal_Y':y,'discounted_square_approx':e*float(x*x),
            'discounted_square_drift_approx':e*float(-k*x*x+2*a*x+b*b),
            'discounted_square_diffusion_approx':e*float(2*b*x),
            'discounted_square_expectation_approx':e*float((x0+a*T)**2+b*b*T),
            'product_drift_at_endpoint':a*y+c*x+b*d,'product_diffusion_at_endpoint':b*y+d*x,
            'product_expectation':(x0+a*T)*(y0+c*T)+b*d*T,'cross_variation':b*d*T,
            'X_quadratic_variation':b*b*T,'Y_quadratic_variation':d*d*T}


def dec(value):
    return Decimal(value.numerator)/Decimal(value.denominator)


def gbm(T, increments, spec):
    S0,mu,sigma=[number(spec[k]) for k in ('initial_price','drift','diffusion')]
    h=T/len(increments);w=F(0);euler=S0;rows=[]
    for i,dw in enumerate(increments):
        w+=dw;t=(i+1)*h;euler*=1+mu*h+sigma*dw
        rows.append({'time':t,'W':w,'exact_price_approx':float(S0)*exp(float((mu-sigma*sigma/2)*t+sigma*w)),
                     'euler_price':euler,'euler_positive':euler>0})
    analysis=[]
    with localcontext() as ctx:
        ctx.prec=80
        initial,drift,vol,time=map(dec,(S0,mu,sigma,T))
        mean=initial*(drift*time).exp();second=initial*initial*((2*drift+vol*vol)*time).exp()
        for n in spec['euler_steps']:
            dt=time/Decimal(n);em=initial*(1+drift*dt)**n
            es=initial*initial*((1+drift*dt)**2+vol*vol*dt)**n
            cross=initial*initial*(drift*time).exp()*(1+(drift+vol*vol)*dt)**n
            mse=second+es-2*cross
            need(mse>=0,'unexpected negative high-precision mean-square error')
            analysis.append({'steps':n,'exact_mean_approx':float(mean),'euler_mean_approx':float(em),
                             'weak_mean_bias_approx':float(em-mean),'exact_second_moment_approx':float(second),
                             'euler_second_moment_approx':float(es),'coupled_cross_moment_approx':float(cross),
                             'coupled_strong_mse_approx':float(mse)})
    dt,dw=number(spec['probe_time']),number(spec['probe_increment'])
    probe_factor=1+mu*dt+sigma*dw
    return {'rows':rows,'log_return_mean':(mu-sigma*sigma/2)*T,'log_return_variance':sigma*sigma*T,
            'mean_price_approx':float(S0)*exp(float(mu*T)),
            'median_price_approx':float(S0)*exp(float((mu-sigma*sigma/2)*T)),
            'price_variance_approx':float(S0*S0)*exp(float(2*mu*T))*expm1(float(sigma*sigma*T)),
            'euler_analytical_error':analysis,
            'positivity_probe':{'time':dt,'increment':dw,'euler_factor':probe_factor,'euler_price':S0*probe_factor,
                                'exact_price_approx':float(S0)*exp(float((mu-sigma*sigma/2)*dt+sigma*dw)),
                                'euler_nonpositive':probe_factor<=0},
            'scope':'Exact GBM formula and Gaussian coupled Euler moments are distinct from the authored finite path and finite moment cubature.'}


def serial(value):
    if isinstance(value,F):return str(value)
    if isinstance(value,list):return [serial(x) for x in value]
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    return value


def run(data):
    validate(data);g=data['grid'];T=number(g['horizon']);dw=list(map(number,g['increments']))
    fine=path_ledger(dw,T);grids=[]
    for block in g['blocks']:
        inc=[sum(dw[i:i+block],F(0)) for i in range(0,len(dw),block)]
        grids.append({'block':block,'ledger':path_ledger(inc,T)})
    return serial({'case':data['case'],'contract':data['contract'],'finite_grids':grids,
                   'polygon_refinements':[{'subdivisions':m,'quadratic_sum':fine['squared_increment_sum']/m,
                                           'ordinary_integral_W_dW':fine['terminal_W']**2/2} for m in g['polygon_subdivisions']],
                   'brownian_grid_theory':[gaussian_grid(T,n) for n in g['theory_steps']],
                   'finite_moment_cubature':cubature(T,g['cubature_steps']),
                   'adapted_two_step_integral':adapted(T,data['adapted_integrand']),
                   'chain_and_product':chain(T,fine['terminal_W'],data['chain_product']),
                   'gbm':gbm(T,dw,data['gbm']),
                   'limits':'Proofs are in the chapter. Finite authored observations and cubature do not establish Brownian paths, empirical diffusion validity, almost-sure convergence or universal numerical stability.'})


def load_json(path):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate JSON key: '+k)
            result[k]=v
        return result
    def invalid(value):raise ValueError('nonfinite JSON token: '+value)
    return json.loads(path.read_text(),object_pairs_hook=pairs,parse_constant=invalid)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('v10-c07-inputs.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        result=run(load_json(args.input));text=json.dumps(result,indent=2,allow_nan=False)+'\n'
        if args.output:args.output.write_text(text)
        else:print(text,end='')
    except (ValueError,OSError) as err:parser.error(str(err))


if __name__=='__main__':main()
