Growth and the Solow model — original synthetic transition ledger

Save v06-c02-solow.py and this README in the same folder. With standard-library
Python 3, run:

    python3 v06-c02-solow.py

To save its output, optionally use:

    python3 v06-c02-solow.py > solow-output.json

No internet, installation or external data are needed. The printed JSON has
40 transition rows, dated 0 through 39, and a terminal state at date 40 for each
scenario. Each row uses beginning capital K and current A,L to produce Y; I=sY
becomes next capital after old-stock depreciation. The next ratio divides by
next_A*next_L. normalized_discrepancy compares the aggregate ledger with the
separately evaluated normalized recurrence and should be close to zero.

Scope and units are fixed: alpha=1/2, delta=1/25, n=g=1/10 per synthetic teaching
period; initial A=1 and L=100. Physical goods serve as output and capital units.
There are no dollar prices or measured chain-volume series. These unusually
large growth rates expose discrete-time approximation errors; they are not
estimates of annual growth. benchmark() runs only three original chapter cases.
simulate(initial_k, saving, periods=40) permits nonnegative finite initial k,
saving in [0,1], and an integer horizon from 1 to 200. It is not a general
parameter-calibration API. Changing the time unit or production/depreciation
convention requires a new fixture, not relabeling the current output.

Independent exact references:
- Accumulation: initial K=25, Y=50, I=25/2, C=75/2, next K=73/2;
  next effective labor=121; next k=73/242; positive steady k=1, c=3/4.
- Saving increase, initially k=1: new s=1/2 gives impact c=1/2,
  next k=146/121; positive steady k=4, c=1.
- Saving reduction, initially k=9: new s=1/2 gives impact c=3/2,
  next k=1014/121; positive steady k=4, c=1.

All subsequent non-square states require approximate arithmetic. Finite paths
supplement the manuscript's global proof; they do not establish it. The positive
steady entry describes the positive fixed point even when an optional run starts
at zero. zero_capital_boundary flags that case: the actual path then stays zero.
With saving=0 there is no positive steady state and positive capital decays.

The model assumes constant saving and exogenous labor efficiency. It supplies no
estimate of policy causation, lifetime-optimal saving or actual national growth.
