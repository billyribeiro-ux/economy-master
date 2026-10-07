"""Original exact-fraction laboratory for Volume 3 Chapters 1–2.

Run with standard-library Python: python3 v03-probability-lab.py
Small finite examples are enumerated, not simulated. No observed data are used.
"""
from fractions import Fraction as F
from itertools import combinations, product
import json


def archive_distribution(population, flags, draws, replacement=False):
    """Enumerate a small uniform archive; return flag-count probabilities.

    Without replacement, enumerate unordered distinct subsets.
    With replacement, enumerate ordered independently uniform draw records.
    Enumeration grows quickly; intended only for small teaching examples.
    """
    for number in (population, flags, draws):
        if isinstance(number,bool) or not isinstance(number,int):
            raise ValueError('Counts must be integers')
    if population<1 or not 0<=flags<=population or draws<0:
        raise ValueError('Invalid population, flag count or draw count')
    if not replacement and draws>population:
        raise ValueError('Distinct sample cannot exceed population')
    records=product(range(population),repeat=draws) if replacement else combinations(range(population),draws)
    counts={}; total=0
    for record in records:
        flagged=sum(label<flags for label in record)
        counts[flagged]=counts.get(flagged,0)+1
        total+=1
    return {k:F(count,total) for k,count in sorted(counts.items())}


def bayes(prior,likelihood):
    """Finite model inputs: hypothesis -> rational/decimal probability.

    Likelihood inputs are specified model probabilities, including hypothetical
    data laws for any zero-prior hypothesis. Zero prior weight stays zero.
    Return evidence probability and normalized posterior fractions.
    """
    if not prior or set(prior)!=set(likelihood):
        raise ValueError('Require the same nonempty hypothesis keys')
    priors={k:F(str(v)) for k,v in prior.items()}
    likelihoods={k:F(str(v)) for k,v in likelihood.items()}
    if any(not 0<=v<=1 for v in (*priors.values(),*likelihoods.values())):
        raise ValueError('Probabilities must be between zero and one')
    if sum(priors.values())!=1:
        raise ValueError('Prior probabilities must sum to one')
    weights={k:priors[k]*likelihoods[k] for k in prior}
    evidence=sum(weights.values())
    if evidence==0:
        raise ValueError('Zero-probability evidence: update undefined')
    return dict(evidence=evidence,posterior={k:v/evidence for k,v in weights.items()})


def example():
    prior={'error':F(1,50),'correct':F(49,50)}
    return {'archive_without_replacement':archive_distribution(12,3,4),
            'archive_independent_replacement':archive_distribution(12,3,4,True),
            'invoice_flag':bayes(prior,{'error':F(17,20),'correct':F(1,25)}),
            'invoice_nonflag':bayes(prior,{'error':F(3,20),'correct':F(24,25)}),
            'lot_two_separate_flags':bayes({'poor':F(1,4),'good':F(3,4)},
                                         {'poor':F(9,25),'good':F(1,25)}),
            'lot_duplicated_flag':bayes({'poor':F(1,4),'good':F(3,4)},
                                      {'poor':F(3,5),'good':F(1,5)})}


if __name__=='__main__':
    # Strings retain exact fractions in the displayed JSON.
    print(json.dumps(example(),default=str,indent=2))
