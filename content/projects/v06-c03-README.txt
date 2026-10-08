V06 C03 — Innovation, skills, diffusion and identification
Original synthetic teaching lab. Created 8 October 2026.

Files
  v06-c03-models.json     Stated parameters, normalization and timing
  v06-c03-dynamics.py     Python 3 standard-library calculation
  v06-c03-output.json     Preserved default result
  v06-c03-README.txt      This guide

Place all four files in one directory and run:
  python3 v06-c03-dynamics.py
To preserve a fresh result under a different filename:
  python3 v06-c03-dynamics.py > my-v06-c03-output.json
An optional path supplies changed inputs:
  python3 v06-c03-dynamics.py my-models.json
Default input resolves relative to the program, not the shell directory.
No downloads, packages, network calls or input-file changes occur at runtime.

The parameters and four equiprobable IV states are authored, not observations
or estimates from the cited papers. No real-country inference, calendar-year
growth forecast, institutional ranking or empirical replication is claimed.

Representation and units
Quantities use exact integer/rational strings, e.g. "9/4", not JSON floats or
booleans. Output fractions remain exact strings. Horizon lengths are ordinary
JSON integers in [0,100]. Indices A/F and h/kappa use the chapter's fixed units;
rh is normalized research skill intensity, not the total research workforce.
Research r and schooling e are time shares. Goods are homogeneous quantities
per model period, with no USD/year interpretation. d is a date-1 utility weight.

Research is a two-date linear, no-capital specialization, h=L=1, no schooling.
Date-0 work produces A0(1-r). Research changes A1 and all date-1 time then goes
to goods production. No terminal research, capital choice or uncertainty is
modeled. theta captures only the future increment A1-A0. Uncaptured increments
are reported in date-1 goods; private payoff and J apply d to date-1 quantities.

The program compares the supplied research candidates. It does not claim that
a finite grid proves a continuous optimum. In the chapter J is strictly concave
and the endpoint/derivative argument proves the global optimum. In the three
provided cases the relevant exact optimum is among the supplied candidates.
For changed parameters it need not be, so best_supplied_* must retain its label.

Innovation paths hold r,h fixed. The growth increment is bounded, while the
knowledge stock can grow without bound over infinitely many periods. Schooling
changes next-period skills; the additive skill law need not imply sustained
percentage growth. delta=0 is an explicitly reported separate boundary.

Diffusion has an exogenous frontier, no own innovation, and constant h, hence
constant lambda. It uses the OLD frontier F_t for adoption, then computes F_t+1.
The ratio denominator is exactly 1+g. lambda=g=0 gives no unique ratio fixed
point (JSON null), not a numerical zero. If lambda=0 and g>0, A stays constant;
do not apply the positive-limiting-ratio growth conclusion to that boundary.
Combining changing schooling with diffusion needs time-varying lambda and a
new calculation; the constant-lambda closed form cannot silently be reused.

Targets
Research worked: r=1/2 gives (Y0,Y1,J)=(50,175,225). At theta=25/36 the private
choice r=1/4 gives (75,145,220), private payoff 25/4, uncaptured increment 55/4.
Exercise: r=1/2 gives (40,560/3,145), with d=9/16. Retention: r=1/4 gives
(60,105,165). All optimality statements use the chapter's global proof.
Innovation exercise: growth 1/2; stock path 80, 120, 180.
Schooling worked: 1,5/4,23/16,101/64; fixed point 2.
Diffusion worked: (F1,A1,a1)=(125,70,14/25); (F2,A2,a2)=(625/4,195/2,78/125),
relative fixed point 2/3 and contraction 2/5. Higher skills: a1=16/25, a*=8/11.
IV: Cov(Z,R)=-2, Cov(Z,y)=-1, ratio 1/2 in both worlds, but intervention effects
1/2 versus 1/5. In World II Cov(Z,u)=-3/5. Equal observed values do not validate
the instrument. The four states are population expectations, not sample SEs.

Audit and limits
The repository checker independently uses closed-form dynamics, exact objective
differences, finite sums and boundary checks rather than trusting this program's
output. It also tests mutation sensitivity and invalid input rejection. Those
checks verify implementation of maintained equations, not their truth for an
actual economy. Source scopes, policy exclusions and historical-design critique
remain in the chapter and source-review record. Visual/mobile/print QA is not
claimed. The source papers are linked, not redistributed in this lab.
