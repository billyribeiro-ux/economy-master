Aster State Claims — v09-c05 reproducible laboratory

This is an original synthetic date-0/date-1 market, denominated in CU. It is
not market data. Three states have strictly positive physical probabilities.
Trades are unrestricted real quantities; there are no interim margin calls,
taxes, default, trading costs or short-sale restrictions. Those assumptions
are essential to the arbitrage certificates, not recommended trading terms.

Files: inputs.json, analysis.py, output.json and this README share the prefix
v09-c05-. The matching manifest hashes these four distributed files with
SHA-256. The program uses only the Python 3 standard library. Save them in one
directory; run from that directory or supply the program's absolute path:

  python3 v09-c05-analysis.py
  python3 v09-c05-analysis.py --input v09-c05-inputs.json --output result.json

The default input is resolved beside the script, independently of the shell
working directory. An explicit relative --input/--output is relative to the
shell working directory. Importing the module and calling run(data) are quiet
and make no filesystem writes. The command prints strict JSON unless an
output path is specified; that option writes the named destination. Compare
the entire parsed result with v09-c05-output.json, not only one price.

Every calculated number is an exact rational string (for example "24/25");
booleans describe logical conclusions, and rank is an integer. There is no
floating approximation in the supplied result. A square-root volatility in
the chapter is derived from its exact squared value, not separately fitted.

The complete market trades a unit-payoff bond, stock, and a call struck at the
middle stock payoff. The three stock payoffs must be positive, increasing and
equally spaced; this is a named three-state laboratory, not a general option
pricing engine or a continuous-time model. The call payoff is recomputed as
max(stock payoff - strike, 0). Its 3-by-3 payoff matrix is invertible, with
determinant equal to the square of the payoff spacing. Gaussian elimination
replicates arbitrary three-state claims and all three unit state claims.

Domain and changes
------------------
The input object must have exactly the supplied keys. Numeric entries accept
rational strings or integer JSON values; floats, booleans, invalid fractions,
zero denominators and nonfinite strings are rejected. Probabilities must be
three strictly positive values summing exactly to one. State names must be
three distinct nonempty strings. All payoff vectors have three entries.
Bond price, stock price, utility discount and current consumption must be
positive. Utility discount is a positive preference parameter; the program
does not impose impatience delta<=1. Claim payoffs and quote may be signed.

Base stock price must lie strictly between bond_price times the lowest and
highest stock payoffs. Base call price must give three strictly positive state
prices. This keeps the base pricing/MRS exercise in its declared no-arbitrage
domain. To inspect zero or negative state prices, change the separate
diagnostic_call_quotes instead: they allow any rational quote and produce an
arbitrage certificate when the unique resulting q is not strictly positive.
Each quote experiment list accepts 1 through 20 entries. Incomplete-market
digital quotes also allow any rational value, including both strict bounds
and values beyond them. Contradictory case, provenance, currency, horizon or
policy labels are rejected rather than silently changing the interpretation.

Useful changes include altering either physical probability vector, the claim
payoffs/quote, the stock price within the declared domain, or a diagnostic
quote. Changing probabilities changes m=q/pi and physical moments but leaves
state prices and replication prices unchanged. Changing base call price can
change the price of an unspanned claim even though bond/stock prices remain
fixed. Perturbing stock price changes the incomplete-market digital bounds;
the program does not hard-code the symmetric baseline family (t,.96-2t,t).

Output interpretation
---------------------
complete_market reports holdings in units of bond, stock and call. These are
not beginning-wealth weights. q gives date-0 prices per one terminal CU in a
state; q sums to the bond price, not to one. R_f is a gross safe return, while
the simple safe return is R_f-1. An Arrow claim is a unit state payoff, not
an actually listed security unless it is traded or synthetically replicated.

quote_experiment buys an underpriced claim and shorts its replica, or reverses
the trade if overpriced. It invests the date-0 receipt in the bond so the
reported total trade costs zero and has a strictly positive terminal payoff.
At the fair quote all positions are zero and arbitrage is false. This is a
conditional certificate with unrestricted shorting and exact matching dated
payoffs; it does not model counterparty, execution or interim funding risk.

call_quote_diagnostics replaces ONLY the call's price. A nonpositive state
price prices a replicable Arrow claim at zero or less. The certificate buys
that Arrow claim and banks any receipt, reporting actual dated asset units,
initial cost and every terminal state payoff. A positive solution certifies
no arbitrage here because the market is complete. In an incomplete market,
finding one negative solution would not prove that no positive solution exists.

incomplete_bond_stock_market removes the call. Let d be the stock-payoff gap,
a its lowest payoff, B the bond price, k=(stock_price-a*B)/d, and t=q_high.
All compatible state prices are (B-k+t,k-2t,t). Strict positivity requires
max(0,k-B)<t<k/2. The high-state digital has price t; a subhedge and superhedge
give the strict lower and upper bounds. If k<=B, the lower hedge is zero;
otherwise it is (stock-middle*unit_bond)/d. The upper hedge is
(stock-lowest*unit_bond)/(2*d). At either bound the digital and hedge differ
by a nonzero nonnegative payoff at zero cost. Outside the bounds there is
also a positive receipt, invested in the bond. The output lists certificates.
These are sufficient explicit arguments for this special grid, not a claim
that general incomplete-market bounds are always open or attained this way.

physical_pricing and alternative_physical_pricing keep identical traded prices
and q. Each reconstructs m=q/pi, Q=q/B, the fundamental price equation, the
gross return condition, covariance premium, and squared Sharpe/SDF bound.
All moments are population moments of the disclosed synthetic distribution,
not sample estimates. The bound_attaining_payoff G*=R_f+E[m^2]/E[m]-m costs
one and achieves equality in the Cauchy bound; it is replicable in this
complete unrestricted market. Its individual state values need not be
nonnegative for every allowed input. A negative terminal payoff is allowed
by the model; the program makes no limited-liability or feasible-wealth claim.

log_utility_euler constructs c_s=delta*c0/m_s>0 so log marginal utility gives
the same m. This is a local Euler-equation illustration with a possible
positive endowment allocation, not an estimated preference model or a
market-clearing aggregate-consumption equilibrium. Its derivative compares
the supplied claim quote with the marginal value. A buy-only boundary choice
requires a one-sided inequality, not the unrestricted equality.

Verification
------------
The repository's scripts/check_v09_c05.py independently reconstructs prices,
replicas, covariance identities, all arbitrage certificates and exercise
anchors with exact fractions; tests meaningful price/probability/payoff edits
and invalid-domain rejection; and copies the distributed package to a
temporary directory to check execution and full reference-output equality.
The chapter separately proves the finite-state theorems. Numerical tests
neither prove those theorems nor independently validate real market inputs.
