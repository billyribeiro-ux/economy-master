"""Canonical curriculum definition. Re-running preserves existing chapter state."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
VOLUMES = []

def volume(number, title, level, prerequisites, sources, assessment, project, rows):
    chapters = []
    for index, row in enumerate(rows.strip().splitlines(), 1):
        name, outcome, coverage = [item.strip() for item in row.split('|')]
        chapter_id = f'v{number:02d}-c{index:02d}'
        chapters.append({
            'id': chapter_id, 'number': index, 'title': name, 'outcome': outcome,
            'coverage': [item.strip() for item in coverage.split(';')],
            'prerequisites': ([f'v{number:02d}-c{index-1:02d}'] if index > 1 else prerequisites),
            'level': level, 'status': 'planned', 'manuscript': f'chapters/{chapter_id}.html',
            'sources': sources, 'required_worked_examples': 3 if level == 'Graduate' else 2,
            'required_exercises': 10 if level == 'Graduate' else 8,
            'review': {'arithmetic': False, 'reasoning': False, 'solutions': False,
                       'sources': False, 'instruction': False, 'structure': False}
        })
    assert len(chapters) == 12, (title, len(chapters))
    VOLUMES.append({'id': f'v{number:02d}', 'number': number, 'title': title,
                    'level': level, 'prerequisites': prerequisites, 'sources': sources,
                    'assessment': assessment, 'project': project, 'status': 'planned',
                    'chapters': chapters})

volume(1, 'Foundations of economic and financial reasoning', 'Foundation', [],
       ['openstax-economics', 'core-economy'],
       'Explain mechanisms, reconcile a balance sheet, compute returns and real values, and distinguish identity, model, evidence and decision.',
       'Build a household-and-small-business case: budget, three statements, financing comparison, opportunity cost, uncertainty and a defended decision.', '''
Scarcity, choice and opportunity cost | Identify the best forgone alternative and compare choices using relevant incremental consequences. | Scarcity; feasibility; opportunity cost; sunk costs; marginal reasoning
Numbers, units and percentage changes | Calculate rates and changes without confusing levels, units, bases or percentage points. | Fractions; ratios; percentages; weighted averages; dimensional analysis; nominal scales
Algebra, functions and graphs | Translate a verbal economic relationship into an equation and interpret its graph. | Variables; equation solving; functions; slopes; intercepts; inverse relationships; domains
Stocks, flows and balance sheets | Reconcile changes in a stock with the flows that cause them. | Assets; liabilities; equity; income; cash flow; double counting; accounting identities
Compounding and present value | Compare dated cash flows on a common valuation date with explicit timing and rate assumptions. | Compound growth; discount factors; annuities; effective rates; real rates; loan payments
Incentives, marginal decisions and equilibrium | Predict responses to incentives and distinguish individual optimization from market equilibrium. | Marginal benefits and costs; incentives; supply and demand intuition; equilibrium; disequilibrium
Prices, inflation and purchasing power | Deflate nominal values and explain what a price index does and does not measure. | Price baskets; index construction; inflation; real wages; relative prices; substitution
Risk, uncertainty and evidence | Organize uncertain outcomes and distinguish an expectation from a guaranteed outcome. | Scenarios; probability intuition; expected values; downside; ambiguity; evidence quality
Money, credit and financial institutions | Trace a payment and a credit contract through the parties' balance sheets. | Money functions; deposits; lending; central banks; securities; payment systems; intermediation
Models, causation and economic arguments | Identify assumptions, mechanisms and identification requirements in an economic claim. | Identities; hypotheses; counterfactuals; correlation; causal reasoning; falsifiability
Reading, writing and explaining analysis | Write a concise, reproducible analytical memo with an auditable chain of reasoning. | Claim-evidence reasoning; tables and graphs; source provenance; uncertainty; teach-back
Foundation integration and diagnostic | Solve an integrated unfamiliar case and identify prerequisite gaps before quantitative study. | Household finance; business accounts; policy trade-offs; financing decisions; comprehensive diagnostic
''')
volume(2, 'Mathematics for economics and finance', 'Undergraduate', ['v01'],
       ['mit-calculus', 'mit-linear-algebra'],
       'Derive optima, solve systems, analyze curvature and stability, and give valid proofs with boundary cases.',
       'Solve and document a constrained allocation model analytically and numerically, including sensitivity and numerical-error analysis.', '''
Mathematical language and proof | Construct valid arguments using sets, functions, quantifiers and proof methods. | Sets; relations; implication; necessity and sufficiency; induction; contradiction; counterexamples
Functions, limits and continuity | Determine limiting behavior and distinguish continuity from differentiability. | Domains; composition; sequences; limits; continuity; intermediate-value reasoning
Derivatives and economic change | Derive marginal quantities and elasticities using differentiation rules. | Derivative definition; product and chain rules; implicit differentiation; elasticity; Taylor approximation
Integrals and accumulated quantities | Recover totals from marginal quantities and evaluate definite integrals. | Antiderivatives; fundamental theorem; substitution; integration by parts; improper integrals
Vectors, matrices and linear systems | Solve linear systems and diagnose rank and identification. | Matrix operations; elimination; rank; inverse; linear independence; bases; null space
Eigenvalues, projections and quadratic forms | Interpret stability, least squares and covariance geometry using linear algebra. | Eigenvectors; positive definiteness; orthogonal projection; spectral decomposition; singular values
Multivariable calculus | Calculate gradients, Hessians and total derivatives in economic models. | Partial derivatives; Jacobian; Hessian; multivariate chain rule; implicit-function theorem
Unconstrained and constrained optimization | Solve constrained decisions and verify sufficient conditions rather than relying only on first-order conditions. | Concavity; Lagrange multipliers; inequality constraints; KKT; corner solutions; envelopes
Convexity, duality and comparative statics | Use curvature and duality to establish optimization results and parameter responses. | Convex sets; separating intuition; value functions; dual problems; sensitivity; comparative statics
Real analysis and convergence | Prove convergence results and recognize when interchange of limits requires justification. | Completeness; compactness; subsequences; uniform convergence; contraction mappings
Difference and differential equations | Solve simple dynamic systems and classify local stability. | First-order recursions; systems; steady states; eigenvalue stability; differential equations
Numerical methods and dynamic foundations | Implement root finding and approximation with explicit accuracy criteria. | Bisection; Newton methods; interpolation; numerical integration; conditioning; Bellman equation introduction
''')
volume(3, 'Probability, statistics and decisions under uncertainty', 'Undergraduate', ['v02'],
       ['harvard-probability'],
       'Derive conditional expectations, quantify sampling uncertainty, evaluate evidence and solve explicit risk decisions.',
       'Design and analyze a simulated decision problem with Bayesian updating, sampling diagnostics and sensitivity to loss functions.', '''
Probability spaces and counting | Build coherent event probabilities and explain independence assumptions. | Events; axioms; combinatorics; independence; inclusion-exclusion; sampling with replacement
Conditional probability and Bayes | Update beliefs correctly and diagnose base-rate errors. | Conditional events; Bayes rule; total probability; odds; likelihood ratios
Random variables and distributions | Work with discrete and continuous distributions and their support. | PMF; PDF; CDF; Bernoulli; binomial; Poisson; normal; exponential
Expectation, variance and covariance | Compute moments and explain diversification using joint distributions. | Expected value; variance; covariance; correlation; transformations; total expectation
Joint distributions and conditional expectation | Derive conditional moments and identify dependence beyond correlation. | Joint and marginal distributions; conditioning; total variance; iterated expectations
Large samples and convergence | Apply laws of large numbers and central-limit reasoning with stated conditions. | Convergence modes; LLN; CLT; heavy tails; dependence; finite-sample caveats
Sampling and estimation | Construct estimators and compare bias, variance and consistency. | Sampling designs; point estimation; standard errors; maximum likelihood introduction; bootstrap
Confidence intervals and hypothesis tests | Interpret intervals and tests without confusing statistical and economic significance. | Null and alternatives; test statistics; size; power; p-values; multiple testing
Bayesian inference and decisions | Combine likelihoods, priors and losses to make transparent decisions. | Posterior distributions; conjugacy; credible intervals; predictive distributions; sensitivity to priors
Expected utility and risk preferences | Solve decisions under uncertainty and identify the limits of expected-utility models. | Utility; certainty equivalents; risk premiums; Jensen; risk aversion; ambiguity
Information, forecasting and scoring | Evaluate predictions and the value of additional information using proper criteria. | Calibration; proper scoring; conditional forecasts; expected value of information; loss functions
Measure and stochastic foundations | Explain the formal probability tools needed for graduate econometrics and finance. | Sigma-algebras; measurability; Lebesgue integration; dominated convergence; conditional expectation; martingale introduction
''')
volume(4, 'Data, computation and empirical reasoning', 'Undergraduate', ['v03'],
       ['quantecon-python', 'core-doing-economics', 'fred', 'imf-data'],
       'Build a reproducible empirical workflow, fit basic models, diagnose errors and separate prediction from causal inference.',
       'Produce a documented economic-data report with a frozen input snapshot, executable analysis, uncertainty and a causal-identification critique.', '''
Reproducible work and data provenance | Create a workflow another analyst can reproduce from the supplied inputs. | Files; environments; README; version control; data dictionaries; vintages; licenses
Spreadsheets and financial models | Build auditable spreadsheet calculations and detect hidden modeling errors. | Cell references; formulas; cash-flow timelines; reconciliation; sensitivity tables; audit checks
Python fundamentals for analysis | Write clear executable programs for economic calculations. | Types; loops; functions; exceptions; assertions; files; standard library
Arrays, tables and SQL | Transform structured data without corrupting units, keys or populations. | Arrays; joins; aggregation; SQL; missing values; dates; duplicate keys
Visualization and descriptive evidence | Choose and interpret figures that expose rather than conceal evidence. | Distributions; time series; scatterplots; scales; uncertainty; misleading comparisons
Simulation and Monte Carlo | Estimate quantities by simulation and assess Monte Carlo error. | Random seeds; simulation design; sampling uncertainty; variance reduction; reproducibility
Regression as projection | Derive ordinary least squares and interpret fitted values and residuals. | Projection; normal equations; coefficients; residuals; fit; extrapolation
Identification and confounding | Distinguish descriptive associations from identified causal effects. | Potential outcomes introduction; selection; confounding; controls; bad controls; identification
Prediction and model validation | Evaluate models using splits that respect economic timing and information availability. | Train-validation-test; time splits; leakage; overfitting; baseline comparisons; losses
Time-series and panel data basics | Prepare longitudinal data and identify dependence and aggregation pitfalls. | Lags; trends; stationarity intuition; panel keys; survivorship; frequencies; deflation
Computational reliability and numerical audits | Verify outputs through invariants, simple cases and independent calculations. | Assertions; tests; edge cases; units; precision; numerical conditioning; peer reproduction
Empirical integration and replication | Reproduce a small empirical result and document departures from the original analysis. | Source retrieval; reconstruction; robustness; replication report; limits of inference
''')
volume(5, 'Microeconomics and strategic interaction', 'Undergraduate', ['v02', 'v03', 'v04'],
       ['openstax-economics', 'core-economy', 'mit-economics-curriculum'],
       'Solve choice and equilibrium problems and evaluate welfare, strategy and information mechanisms.',
       'Analyze a market intervention with explicit supply-demand or strategic foundations, welfare calculations and empirical limitations.', '''
Preferences and consumer choice | Derive demands and identify corner solutions under a budget constraint. | Preferences; utility; indifference curves; budget sets; Marshallian demand; revealed preference
Demand, duality and welfare | Decompose price responses and measure welfare with correct income concepts. | Hicksian demand; expenditure function; Slutsky; indirect utility; compensating variation
Production, costs and firm choice | Derive cost functions and output/input choices from technology. | Production sets; marginal products; cost minimization; fixed and sunk cost; supply
Competitive equilibrium and surplus | Solve partial equilibrium and distinguish efficiency from distribution. | Market clearing; consumer and producer surplus; elasticity; entry; tax incidence
General equilibrium and welfare | Analyze exchange and production interactions across markets. | Edgeworth box; Walras law; Pareto efficiency; welfare theorems; missing markets
Monopoly, oligopoly and pricing | Solve market-power models and compare price and quantity competition. | Monopoly; markup; price discrimination; Cournot; Bertrand; entry barriers
Game theory and strategic behavior | Identify equilibria and credible strategies in static and dynamic games. | Dominance; Nash; mixed strategies; extensive form; backward induction; commitment
Information, signaling and selection | Explain how asymmetric information changes trade and incentives. | Adverse selection; signaling; screening; pooling; separating equilibria; lemons
Contracts, incentives and organizations | Solve simple principal-agent problems and evaluate incentive trade-offs. | Moral hazard; participation; incentive compatibility; monitoring; multitasking; firm boundaries
Externalities and public goods | Compare corrective instruments under informational and institutional constraints. | External costs; Pigouvian taxes; public goods; free riding; Coase conditions; congestion
Auctions, matching and market design | Analyze allocation rules and incentive properties in designed markets. | Auction formats; revenue equivalence conditions; matching; stability; strategy-proofness
Behavioral economics and microeconomic evidence | Evaluate departures from standard choice and the evidence needed to support interventions. | Biases; reference dependence; time inconsistency; experiments; welfare interpretation; replication
''')
volume(6, 'Macroeconomics and the international economy', 'Undergraduate', ['v02', 'v03', 'v05'],
       ['openstax-economics', 'core-economy', 'fred', 'imf-data', 'mit-economics-curriculum'],
       'Reconcile aggregate accounts, derive basic growth and stabilization models, and evaluate open-economy mechanisms.',
       'Produce a country diagnostic using dated macro data, competing models, scenarios and a policy memo that distinguishes identification from forecasting.', '''
National accounts and macro measurement | Reconcile output, expenditure and income measures and explain what GDP omits. | GDP; value added; expenditure identity; deflators; real income; stocks versus flows
Growth and the Solow model | Derive steady states and distinguish level effects from sustained growth. | Capital accumulation; depreciation; population; technology; convergence; growth accounting
Innovation, human capital and institutions | Compare mechanisms of long-run development with appropriate evidence. | Endogenous growth; human capital; diffusion; institutions; geography; identification
Consumption, saving and investment | Derive intertemporal decisions and connect household and firm behavior to aggregates. | Permanent income; life cycle; liquidity constraints; investment; adjustment costs; expectations
Labor markets and unemployment | Explain employment dynamics using search, incentives and institutional mechanisms. | Participation; matching; unemployment flows; wage setting; efficiency wages; hysteresis
Money, banking and monetary transmission | Trace monetary-policy mechanisms without relying on a mechanical deposit multiplier. | Money demand; policy rates; reserves; bank balance sheets; credit; transmission
Inflation, expectations and nominal rigidity | Explain inflation dynamics and distinguish supply from demand disturbances. | Quantity theory conditions; Phillips curves; expectations; price stickiness; shocks
Business cycles and stabilization models | Compare short-run models and identify their assumptions and predictions. | IS-LM; aggregate demand-supply; RBC introduction; New Keynesian introduction; stabilization
Fiscal policy and public debt | Derive debt dynamics and evaluate fiscal trade-offs with explicit assumptions. | Budget constraint; debt-to-GDP; multipliers; automatic stabilizers; fiscal space; distribution
Trade and comparative advantage | Derive gains and distributional effects from trade models. | Ricardian; factor endowments; scale; firms; tariffs; terms of trade
Exchange rates and external balances | Connect international accounts, exchange-rate mechanisms and policy regimes. | Balance of payments; net foreign assets; exchange rates; PPP; interest parity; capital flows
Crises, policy regimes and macroeconomic judgment | Compare crisis mechanisms and evaluate a country case without claiming certainty from one model. | Financial crises; sudden stops; sovereign distress; historical comparison; scenario analysis
''')
volume(7, 'Accounting and business analysis', 'Undergraduate', ['v01'],
       ['mit-finance', 'hbs-finance-curriculum'],
       'Build and reconcile financial statements, assess earnings quality and translate accounting into economic cash flows.',
       'Construct a fully reconciled three-statement model from a supplied original business case and write a financial-quality assessment.', '''
Transactions and double-entry accounting | Record transactions and preserve the accounting equation. | Debits; credits; journals; accruals; recognition; transaction analysis
Balance sheet, income statement and cash flow | Explain and reconcile the three principal statements. | Assets; liabilities; equity; revenues; expenses; operating-investing-financing cash flows
Revenue, working capital and operating cycles | Model operating cash needs and distinguish reported sales from cash collection. | Receivables; inventory; payables; revenue timing; cash conversion cycle; allowances
Long-lived assets and investment accounting | Track asset investment and distinguish accounting expense from economic depreciation. | Capitalization; depreciation; amortization; impairment; disposals; investment assets
Debt, leases and financing obligations | Analyze financing obligations and their effects on performance and cash flow. | Borrowing; interest; leases; covenants; commitments; effective interest; disclosure
Equity, consolidation and ownership | Trace equity claims and distinguish ownership, control and reported group results. | Share capital; retained earnings; dilution; minority interests; consolidation concepts; buybacks
Taxes, accruals and earnings quality | Identify timing differences and assess sustainability of reported earnings. | Current and deferred tax concepts; accruals; provisions; one-offs; manipulation incentives
Managerial accounting and cost decisions | Use contribution margins and relevant costs for operational decisions. | Cost behavior; break-even; allocation; activity-based costing; make-or-buy; capacity
Financial ratios and business diagnosis | Interpret ratios in context and explain accounting comparability limitations. | Liquidity; leverage; margins; turnover; ROIC; DuPont; peer selection
Three-statement forecasting | Build linked forecasts with a transparent financing policy. | Revenue drivers; operating expenses; working capital; capex; financing; cash balancing
Accounting standards, disclosure and comparability | Identify where accounting-policy differences require adjustment and dated source verification. | IFRS and US GAAP concepts; disclosure; estimates; restatements; segment reporting; jurisdiction
Forensic analysis and accounting integration | Diagnose a business using reconciled accounts and explicit alternative explanations. | Cash-versus-profit gaps; covenant risk; red flags; normalization; business model economics
''')
volume(8, 'Corporate finance and valuation', 'Undergraduate', ['v03', 'v05', 'v07'],
       ['mit-finance', 'hbs-finance-curriculum', 'wharton-finance-courses'],
       'Value projects and firms, choose financing and payout policies, and defend decisions with sensitivity and incentive analysis.',
       'Deliver an investment-committee package: operating forecast, DCF, comparables, financing plan, downside scenario and defended recommendation.', '''
Value creation and capital budgeting | Evaluate incremental project cash flows and reconcile NPV with decision criteria. | NPV; IRR; opportunity costs; sunk costs; cash flow; mutually exclusive projects
Free cash flow and discounting | Derive cash flows to the firm and equity and choose consistent discount rates. | FCFF; FCFE; reinvestment; terminal value; nominal-real consistency; currency consistency
Valuation models and terminal assumptions | Value an operating business using explicit growth and reinvestment economics. | DCF; perpetuities; value drivers; ROIC; growth; fade; terminal constraints
Risk, cost of capital and WACC | Estimate financing costs and explain when WACC is inappropriate. | Cost of equity; beta introduction; debt costs; market weights; leverage; project risk
Capital structure and financing frictions | Compare financing policies under taxes, distress and incentive problems. | Modigliani-Miller assumptions; trade-off; pecking order; agency; debt overhang
Payout, liquidity and financial policy | Choose payout and liquidity policies consistent with investment and constraints. | Dividends; buybacks; retained cash; signaling; working capital; financial flexibility
Relative valuation and market evidence | Use comparable valuations with economically meaningful denominators and peer choices. | Enterprise-equity bridge; multiples; normalization; comparability; cycle effects; triangulation
Real options and investment timing | Value flexibility and identify where static NPV understates contingent choices. | Delay; expand; abandon; staged investment; decision trees; information value
Mergers, acquisitions and control | Evaluate acquisition economics and distinguish synergy from wealth transfers. | Purchase price; synergy; integration; control premiums; financing; dilution versus value
Private equity, venture capital and entrepreneurship | Analyze illiquid ownership structures and financing incentives. | LBO; venture rounds; cap tables; preferred claims; exits; fund economics; selection
Distress, restructuring and governance | Compare restructuring alternatives and their incentive and valuation consequences. | Insolvency concepts; priority; recovery; refinancing; governance; stakeholder conflicts
Corporate finance integration | Defend a financing and investment plan under alternative operating and market conditions. | Integrated valuation; capital allocation; downside; covenants; scenario consistency; board memo
''')
volume(9, 'Investments and asset pricing', 'Advanced', ['v03', 'v08'],
       ['mit-finance', 'wharton-finance-courses'],
       'Derive portfolio and pricing relations, evaluate investment evidence, and design mandates with transparent risk constraints.',
       'Construct an investment policy and reproducible portfolio analysis with costs, data-bias controls, scenario risk and benchmark-relative evaluation.', '''
Returns, payoffs and investment opportunity sets | Measure investment outcomes with correct timing, distributions and benchmark conventions. | Simple-log returns; total return; compounding; cash flows; gross-net returns; opportunity sets
Portfolio mathematics and diversification | Compute portfolio risk and explain the role of covariance and concentration. | Mean; covariance matrix; correlations; diversification; estimation error; leverage
Mean-variance optimization and allocation | Derive efficient portfolios and assess sensitivity to estimated inputs. | Efficient frontier; minimum variance; tangency; constraints; optimization; shrinkage
CAPM and equilibrium risk pricing | Derive the CAPM mechanism and distinguish its theoretical assumptions from empirical evidence. | Market portfolio; beta; security market line; alpha; equilibrium; testing limitations
Arbitrage, state prices and discount factors | Price contingent payoffs using no-arbitrage and stochastic discount-factor reasoning. | Replication; state prices; pricing kernel; completeness; fundamental pricing equation
Factor models and empirical asset pricing | Estimate factor exposures and distinguish explanatory fits from investable premiums. | APT; multifactor models; cross-sectional pricing; factor construction; omitted factors
Market efficiency, anomalies and behavior | Evaluate apparent predictability with information, risk and implementation costs in view. | Efficiency forms; joint hypothesis; anomalies; behavioral mechanisms; limits to arbitrage
Active management and performance evaluation | Assess whether performance reflects skill, risk, selection or luck. | Benchmark choice; alpha; attribution; information ratio; persistence; fees; survivorship
Strategic and dynamic asset allocation | Design allocation policies across horizons and investor constraints. | Lifecycle; liabilities; hedging demand; rebalancing; tactical decisions; estimation risk
Alternative assets and illiquidity | Compare nontraditional investments with transparent valuation and liquidity assumptions. | Real estate; private markets; commodities; hedge funds; appraisal smoothing; lockups
Execution, trading costs and market microstructure | Evaluate execution and liquidity effects on feasible investment strategies. | Bid-ask spread; impact; order types; information; execution benchmarks; capacity
Investment policy and portfolio integration | Defend a mandate and portfolio using economic objectives and robust evidence. | IPS; governance; benchmarks; risk budget; costs; stress scenarios; reporting
''')
volume(10, 'Fixed income, derivatives and quantitative finance', 'Graduate', ['v02', 'v03', 'v09'],
       ['mit-finance', 'wharton-finance-courses', 'quantecon-python'],
       'Price and hedge contingent claims, derive continuous-time results and explain model, credit and liquidity risk.',
       'Build a documented pricing-and-risk toolkit with bond valuation, curve construction, binomial options, Monte Carlo and hedge-error analysis.', '''
Bond cash flows and yield curves | Price cash flows with spot discount factors and distinguish yield conventions. | Coupon schedules; clean-dirty price; discount curves; YTM; spot-forward rates; day-count assumptions
Duration, convexity and immunization | Derive rate sensitivity and construct hedges with explicit residual risks. | Macaulay-modified duration; convexity; key rates; immunization; nonparallel shifts
Term-structure models and rate risk | Compare curve models and distinguish physical from risk-neutral dynamics. | Expectations; term premiums; short-rate models; no-arbitrage; calibration; curve scenarios
Credit risk and recovery | Value defaultable claims and separate hazard, recovery and liquidity assumptions. | Credit spreads; structural models; intensity; recovery; transition; correlation
Forwards, futures and swaps | Derive contract values and explain financing, collateral and basis effects. | Cost of carry; forward-futures distinction; swaps; collateral; basis; margin
Options and binomial replication | Construct replicating portfolios and price options through state-contingent payoffs. | Payoffs; put-call parity; binomial tree; risk-neutral probability; American exercise
Brownian motion and Ito calculus | Derive stochastic differentials and explain quadratic variation. | Filtrations; Brownian motion; stochastic integral; Ito lemma; SDE; drift-diffusion
Black-Scholes and risk-neutral valuation | Derive the pricing equation and distinguish a model's assumptions from market conventions. | Replication PDE; risk-neutral measure; Black-Scholes formula; dividends; boundaries
Greeks, volatility and hedging | Analyze hedge sensitivities and the implications of changing volatility assumptions. | Delta; gamma; vega; theta; implied volatility; smiles; discrete hedging
Numerical pricing and Monte Carlo | Implement pricing methods with convergence and error diagnostics. | Trees; finite differences; simulation; variance reduction; early exercise; numerical checks
Incomplete markets and advanced derivatives | Explain why some contingent claims cannot be uniquely priced by replication. | Incompleteness; stochastic volatility; jumps; exotic payoffs; credit derivatives; bounds
Quantitative model governance | Validate pricing and risk models against independent benchmarks and failure scenarios. | Calibration; model risk; implementation errors; limitations; validation; controlled use
''')
volume(11, 'Banking, risk and international finance', 'Advanced', ['v06', 'v07', 'v09', 'v10'],
       ['wharton-finance-courses', 'imf-data', 'hbs-finance-curriculum'],
       'Analyze financial balance sheets, funding and systemic risk, and design defensible stress and governance decisions.',
       'Build an original bank or fund stress case covering liquidity, solvency, collateral, currency mismatch, governance and crisis choices.', '''
Financial intermediation and bank economics | Explain the economic functions and fragilities of financial intermediaries. | Screening; monitoring; maturity transformation; deposits; bank income; capital
Bank balance sheets, capital and liquidity | Reconcile bank accounts and distinguish liquidity shortages from insolvency. | Assets; funding; equity; capital ratios concepts; liquidity buffers; accounting-economic value
Credit analysis and lending decisions | Evaluate creditworthiness using cash flow, incentives and downside protection. | Debt service; leverage; covenants; collateral; repayment sources; credit underwriting
Market risk and portfolio loss | Compare risk measures and state their information and distributional limitations. | VaR; expected shortfall; scenarios; tails; dependence; horizon; backtesting
Liquidity, funding and asset-liability management | Analyze funding gaps and contingent cash needs across scenarios. | Liquidity ladders; ALM; rollover; collateral; margin; maturity mismatch
Operational, legal and model risk | Design controls around human, operational and modeling failure mechanisms. | Process controls; cyber concepts; fraud; legal uncertainty; model validation; incident learning
Stress testing and risk aggregation | Build internally consistent stress scenarios without double counting exposures. | Scenario design; nonlinear losses; contagion; concentration; reverse stress; aggregation
Insurance, pensions and household finance | Evaluate long-horizon liabilities and intermediary incentives. | Insurance pooling; adverse selection; pensions; longevity; guarantees; household credit
Currency, sovereign and cross-border risk | Analyze international claims with explicit currency and jurisdiction assumptions. | FX exposure; hedging; sovereign debt; capital flows; country risk; convertibility
Financial regulation and incentives | Evaluate regulatory purposes and trade-offs using dated jurisdiction-specific sources. | Prudential regulation; resolution; conduct; systemic externalities; arbitrage; regulatory capture
Financial crises and systemic mechanisms | Trace balance-sheet feedback, runs and contagion in a crisis model. | Runs; fire sales; leverage cycles; networks; lender of last resort; resolution
Risk governance and institutional integration | Defend an institution's risk appetite and response to a combined stress scenario. | Risk limits; board oversight; escalation; incentives; decision logs; contingency plans
''')
volume(12, 'Advanced econometrics and causal inference', 'Graduate', ['v02', 'v03', 'v04', 'v05'],
       ['harvard-economics-requirements', 'mit-economics-curriculum', 'wharton-finance-courses'],
       'Derive and implement advanced estimators, defend identification and inference, and critique research designs.',
       'Produce an advanced replication-and-extension package with an identification memo, alternative specifications, inference diagnostics and referee report.', '''
Identification, estimands and asymptotic tools | Separate what data identify from what an estimator computes and justify limiting arguments. | Estimands; identification; consistency; asymptotic normality; delta method; stochastic orders
Linear models and robust inference | Derive linear estimators and choose inference appropriate to dependence and heterogeneity. | OLS; GLS; heteroskedasticity; clustering; serial correlation; finite-sample concerns
Instrumental variables and GMM | Derive moment-based estimators and evaluate instrument relevance and validity. | IV; 2SLS; weak instruments; exclusion; GMM; overidentification; local effects
Likelihood and nonlinear models | Estimate nonlinear models and distinguish functional-form identification from causal identification. | MLE; score; information; binary response; count; selection; marginal effects
Panel data and longitudinal identification | Evaluate within-unit identification and dynamic-panel assumptions. | Fixed-random effects; correlated heterogeneity; dynamic panels; attrition; dependence
Experiments and causal inference | Design and evaluate interventions with appropriate estimands and assignment mechanisms. | Potential outcomes; randomization; compliance; interference; attrition; power; randomization inference
Difference-in-differences and event studies | Defend counterfactual trends and handle treatment timing and heterogeneous effects. | Parallel trends; anticipation; staggered adoption; event studies; weighting; sensitivity
Regression discontinuity and synthetic controls | Evaluate local and comparative designs with transparent support and validity conditions. | Continuity; manipulation; bandwidth; fuzzy RD; donor pools; synthetic control; placebo analysis
Time series, forecasting and financial econometrics | Analyze persistent and dependent economic series with model-specific inference. | ARMA; VAR; unit roots; cointegration; volatility; GARCH; forecast evaluation
Structural estimation and economic mechanisms | Connect economic models to data and distinguish calibration from identified estimation. | Structural parameters; moments; simulation; equilibrium; indirect inference; sensitivity
Bayesian, high-dimensional and machine-learning methods | Apply modern methods while preserving valid inference and honest model evaluation. | Bayesian computation; regularization; cross-fitting; double robustness; causal ML; multiple testing
Econometric research audit | Independently audit a complete empirical paper and defend methodological choices. | Identification; robustness; inference; specification search; reproducibility; external validity
''')
volume(13, 'Graduate microeconomics and economic theory', 'Graduate', ['v02', 'v03', 'v05'],
       ['harvard-economics-requirements', 'mit-economics-curriculum'],
       'Prove and apply central results in choice, equilibrium, information and mechanism design with explicit conditions.',
       'Develop a theoretical research note: baseline model, existence or optimality argument, comparative statics, counterexample and economic interpretation.', '''
Preference representation and choice theory | Establish representation and choice results under precise axioms. | Preferences; continuity; utility representation; revealed preference; rationalizability
Consumer and producer duality | Derive duality identities and characterize economically admissible demand and cost functions. | Expenditure; profit; integrability; Slutsky symmetry; homogeneity; envelope identities
Uncertainty and information | Analyze risk attitudes and the economic value of information formally. | Expected utility; stochastic dominance; risk aversion; Bayesian information; Blackwell ordering
General equilibrium and existence | Explain and apply equilibrium existence arguments and their assumptions. | Exchange-production economies; fixed points; excess demand; Walras law; existence; uniqueness limits
Welfare, aggregation and social choice | Prove welfare results and assess aggregation and distributional restrictions. | Welfare theorems; aggregation; social welfare; impossibility; collective choice
Static games and refinements | Establish strategic equilibria and analyze equilibrium selection. | Mixed-strategy existence; Bayesian games; best responses; refinements; correlated equilibrium
Dynamic and repeated games | Analyze sequential incentives and intertemporal cooperation with credible strategies. | Subgame perfection; sequential equilibrium; repeated games; reputation; folk-theorem conditions
Information economics and screening | Solve screening and signaling models with participation and incentive constraints. | Single crossing; menus; adverse selection; signaling; equilibrium selection
Contracts and dynamic incentives | Derive optimal contracts under hidden action and limited commitment. | Principal-agent; sufficient statistics; limited liability; dynamic contracts; relational incentives
Mechanism design and auctions | Derive incentive-compatible allocation and payment rules with explicit informational assumptions. | Revelation principle; implementation; optimal auctions; incentive compatibility; transfers
Matching, networks and market design | Analyze stable allocations and strategic interactions on markets and networks. | Matching; stability; assignment; network games; externalities; design constraints
Theory synthesis and research critique | Evaluate a theoretical contribution through proofs, counterexamples and economic relevance. | Model choice; theorem scope; proof checking; robustness; interpretation; theoretical referee report
''')
volume(14, 'Graduate macroeconomics and macro-finance', 'Graduate', ['v06', 'v09', 'v10', 'v12', 'v13'],
       ['mit-economics-curriculum', 'wharton-finance-courses', 'quantecon-python'],
       'Solve dynamic stochastic models, connect financial mechanisms to aggregates and evaluate quantitative evidence.',
       'Solve and estimate or calibrate a transparent macro-finance model; report equilibrium conditions, numerical errors, moments and policy sensitivity.', '''
Dynamic optimization and recursive methods | Derive Bellman and Euler conditions and establish valid numerical solutions. | Bellman principle; contraction; Euler equations; transversality; policy iteration; value iteration
Stochastic growth and real business cycles | Solve a stochastic growth model and evaluate its empirical mechanisms. | Planner; competitive equilibrium; shocks; labor; perturbation; calibration; moments
Incomplete markets and heterogeneous agents | Analyze distributional state variables and precautionary decisions in incomplete markets. | Aiyagari; Huggett; borrowing constraints; distributions; aggregation; numerical methods
Search, matching and labor dynamics | Derive dynamic labor-market equilibria and evaluate their implications. | Matching functions; bargaining; vacancy creation; unemployment dynamics; shocks
New Keynesian models and monetary policy | Derive a nominal-rigidity model and compare policy rules under explicit approximations. | Household-firm problems; Calvo; NK Phillips curve; dynamic IS; Taylor rules; determinacy
Fiscal policy and sovereign debt | Analyze dynamic public finance and sovereign default mechanisms. | Government constraints; fiscal-monetary interaction; default; sustainability; redistribution
Consumption-based asset pricing | Derive stochastic discount factors and evaluate major pricing puzzles. | Euler equation; consumption risk; equity premium; risk-free rate; habits; long-run risks
Investment, debt and financial frictions | Derive how financing constraints alter investment and aggregate dynamics. | q theory; agency; collateral; debt overhang; financial accelerator; balance sheets
Intermediaries, liquidity and leverage cycles | Analyze financial-sector amplification and endogenous risk. | Intermediary capital; leverage; liquidity; runs; risk-bearing capacity; feedback
International macro-finance | Solve open-economy dynamic models with financial and exchange-rate mechanisms. | Risk sharing; sudden stops; sovereign risk; currencies; global financial conditions
Quantitative solution and model evaluation | Assess macroeconomic models through transparent estimation and numerical diagnostics. | Perturbation; global methods; likelihood-moment methods; identification; validation; sensitivity
Macro-finance research frontier | Critically compare frontier contributions and develop a tractable research question. | Heterogeneity; financial networks; monetary transmission; intermediary pricing; current literature protocol
''')
volume(15, 'Economic fields, institutions, history and policy', 'Advanced', ['v05', 'v06', 'v12', 'v13'],
       ['harvard-economics-requirements', 'core-economy', 'imf-data'],
       'Apply core theory and credible evidence across major fields, compare institutional settings and defend policy trade-offs.',
       'Develop a policy dossier with a literature map, institutional history, causal evidence, distributional analysis and feasible implementation.', '''
Public economics and taxation | Analyze tax and spending decisions with efficiency and distribution in view. | Tax incidence; optimal taxation; public goods; social insurance; welfare weights
Labor economics and human capital | Evaluate wage, employment and education mechanisms using credible designs. | Human capital; returns to education; labor supply-demand; discrimination; mobility
Industrial organization and competition | Assess market conduct and competitive policy using models and evidence. | Demand estimation; entry; pricing; merger analysis; platforms; market definition
Development, poverty and structural change | Compare poverty-reduction mechanisms and their institutional constraints. | Poverty measurement; credit; health; education; structural transformation; field experiments
International trade and global production | Analyze firm and worker responses to trade and production networks. | Heterogeneous firms; trade costs; global value chains; tariffs; distribution; adjustment
Political economy and institutions | Analyze collective decisions and institutional incentives with defensible identification. | Voting; accountability; lobbying; bureaucracy; state capacity; capture
Economic history and historical inference | Use historical evidence to distinguish mechanisms and avoid anachronistic causal claims. | Industrialization; institutions; crises; historical data; natural experiments; comparative inference
Behavioral and experimental economics | Design and critique evidence about nonstandard preferences and beliefs. | Behavioral models; experiments; replication; external validity; welfare; intervention
Environmental, energy and climate economics | Evaluate externalities and long-horizon choices under uncertainty. | Carbon pricing; discounting; resource economics; damages; energy markets; distribution
Health, education and demographic economics | Assess service provision and demographic change through incentives and evidence. | Insurance; health markets; education production; fertility; aging; public policy
Urban economics, housing and inequality | Analyze spatial decisions and distribution with equilibrium feedback. | Location; housing supply; amenities; sorting; migration; inequality; mobility
Policy synthesis and institutional feasibility | Defend an implementable policy with evidence, uncertainty and distributional consequences. | Cost-benefit; political constraints; administrative capacity; counterfactuals; monitoring; evaluation
''')
volume(16, 'Specialization and original research', 'Research', ['v12', 'v13', 'v14', 'v15'],
       ['harvard-economics-requirements', 'hbs-doctoral-requirements', 'wharton-finance-courses'],
       'Produce a defensible original contribution with a reproducible package, research ethics and an expert-facing defense.',
       'Complete a research portfolio: literature map, replication, two referee reports, proposal, original paper, code/data package and oral-defense materials.', '''
Choosing a field and a research agenda | Select a tractable specialization and define an economically significant question. | Comparative advantage; scope; feasibility; contribution; field boundaries; macro-finance default
Literature mapping and critical reading | Map a field by questions, methods and disagreements rather than accumulating citations. | Search strategy; seminal papers; frontier updates; evidence tables; citation chains
Replication and reproduction | Reproduce a research result and document discrepancies without overstating their meaning. | Data provenance; code reconstruction; measurement; versions; replication limits; reporting
Referee reports and research judgment | Write a fair report that distinguishes fatal identification issues from improvements. | Contribution; correctness; evidence; novelty; major-minor concerns; constructive criticism
Question design and identification strategy | Formulate a research question with an explicit path from data or assumptions to conclusions. | Estimand; mechanism; identification; counterfactual; feasibility; alternative explanations
Theory building and model discipline | Develop a parsimonious model that produces testable or interpretable implications. | Baseline; assumptions; equilibrium; comparative statics; falsifiable implications; extensions
Data construction, measurement and ethics | Build a defensible research dataset with documented measurement and access constraints. | Collection; linkage; proxies; privacy; consent concepts; missingness; research integrity
Research design, power and preregistration | Plan an empirical study that separates design from outcome-driven specification choices. | Power; assignment; analysis plan; preregistration; multiple outcomes; contingency decisions
Robustness, uncertainty and external validity | Evaluate whether a conclusion survives plausible alternative assumptions and populations. | Sensitivity; robustness; specification curves; transportability; structural stability; limits
Writing a scholarly paper | Organize a paper around its question, contribution, evidence and limitations. | Abstract; introduction; methods; results; tables; appendices; transparent claims
Seminars, revision and oral defense | Defend research under probing questions and revise based on justified criticism. | Presentation; questions; response memo; revision; defense; disagreement
Independent research portfolio | Assemble original work and an evaluation protocol for independent expert judgment. | Original contribution; reproducibility; ethics audit; external review; research agenda; next papers
''')
volume(17, 'Teaching, communication and research supervision', 'Professional', ['v16'],
       ['harvard-economics-requirements', 'hbs-doctoral-requirements'],
       'Design and teach coherent courses, assess transfer of understanding and supervise research responsibly.',
       'Create undergraduate and graduate teaching portfolios with syllabi, lessons, problems, grading, observation and research-supervision protocols.', '''
Learning objectives and prerequisite design | Translate disciplinary knowledge into assessable learning capabilities. | Objectives; prerequisite maps; cognitive load; course alignment; transfer
Explaining intuition, mathematics and evidence | Teach a concept across levels without changing its meaning or hiding assumptions. | First principles; representations; notation; derivation; empirical interpretation; analogies
Designing an undergraduate course | Build a coherent course from prerequisites to cumulative assessments. | Syllabus; sequencing; pacing; assignments; readings; integration
Designing a graduate seminar | Organize a research seminar around questions, methods and scholarly disagreement. | Paper selection; presentations; discussion; critique; replication; research proposals
Problem design and meaningful assessment | Write assessments that diagnose reasoning and transfer rather than template recognition. | Difficulty; validity; original problems; unseen transfer; rubrics; exam security
Grading, feedback and remediation | Grade consistently and give feedback that identifies the next learning action. | Calibration; fairness; partial credit; misconceptions; remediation; reassessment
Teaching cases and leading discussion | Lead analytical discussion while making assumptions and evidence visible. | Cases; questioning; participation; alternative decisions; synthesis; facilitation
Misconceptions and learning evidence | Diagnose persistent misunderstandings and evaluate whether instruction changed them. | Diagnostic questions; retrieval; formative feedback; retention; learning measurement
Research supervision and mentoring | Guide research toward independence with explicit responsibilities and ethical boundaries. | Scope; milestones; feedback; authorship; conflict; mentorship; independence
Communication to policymakers and boards | Translate technical findings into decisions without overstating certainty. | Executive memos; uncertainty; graphs; trade-offs; audience; actionable recommendations
Observed teaching and reflective practice | Evaluate teaching using observation and evidence of learner understanding. | Observation rubric; peer feedback; student work; revision; accessibility; reflection
Teaching and supervision portfolio | Defend a complete teaching program and its assessment evidence. | Syllabi; materials; teaching demonstration; exam design; supervision plan; external evaluation
''')
volume(18, 'Strategy, governance and institutional leadership', 'Professional', ['v07', 'v08', 'v11', 'v16', 'v17'],
       ['hbs-general-management', 'hbs-doctoral-requirements'],
       'Lead people, budgets, capital and governance with explicit accountability and defensible judgment under uncertainty.',
       'Complete an academic-and-financial leadership portfolio: strategy, budgets, governance, hiring, risk, crisis simulation and a real-project retrospective.', '''
Institutional purpose and strategy | Translate an institution's mission into coherent choices and resource priorities. | Mission; stakeholders; advantage; trade-offs; strategy; success measures
Resource allocation and institutional budgets | Build budgets and allocate resources under opportunity cost and uncertainty. | Operating budgets; capital budgets; endowments; research funding; P&L; scenario planning
Organizations, incentives and culture | Design organizational responsibilities and incentives that support desired behavior. | Structure; principal-agent; delegation; culture; coordination; measurement; unintended incentives
Hiring, evaluation and talent development | Build defensible hiring and development processes for expert organizations. | Selection; evidence; evaluation; promotion; feedback; succession; bias controls
Negotiation, conflict and stakeholder decisions | Negotiate institutional decisions using incentives, alternatives and principled process. | BATNA; interests; bargaining; coalition; conflict resolution; contracts
Governance, fiduciary duties and integrity | Map decision rights and accountability using jurisdiction-aware legal and ethical analysis. | Boards; duties; conflicts; disclosure; academic freedom; research integrity; escalation
Academic institution leadership | Design academic strategy while protecting scholarship and educational standards. | Faculty; curriculum; research; funding; admissions governance; donors; endowment; autonomy
Financial institution leadership | Integrate business strategy, capital, liquidity, risk and operating accountability. | Business model; capital allocation; risk appetite; controls; compensation; regulatory relations
Operations, innovation and change | Implement organizational improvements with measurable feedback and adaptation. | Process; bottlenecks; change; experimentation; technology; AI evaluation; execution
Crisis leadership and high-stakes judgment | Make and revise accountable crisis decisions with incomplete information. | Triage; uncertainty; scenarios; communication; decision logs; contingency; after-action review
Real responsibility and leadership evaluation | Assess leadership through observed decisions and outcomes rather than self-description. | Project ownership; people; budgets; delivery; external feedback; retrospective; attribution
Institutional leadership portfolio and final integration | Defend an integrated strategy and demonstrate the limits and strengths of one's preparation. | Academic-financial cases; governance; research; teaching; capital; risk; external evaluation; continuing development
''')

def main():
    destination = ROOT / 'content' / 'curriculum.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(destination.read_text()) if destination.exists() else {}
    previous_chapters = {c['id']: c for v in previous.get('volumes', []) for c in v['chapters']}
    previous_volumes = {v['id']: v for v in previous.get('volumes', [])}
    for v in VOLUMES:
        if v['id'] in previous_volumes:
            old_volume = previous_volumes[v['id']]
            for key in ('status', 'assessment_status', 'review_record', 'review_limitations'):
                if key in old_volume: v[key] = old_volume[key]
        for c in v['chapters']:
            old = previous_chapters.get(c['id'], {})
            c['status'] = old.get('status', c['status'])
            c['review'] = old.get('review', c['review'])
            if 'review_record' in old: c['review_record'] = old['review_record']
    plan = {'title': 'Economics & Finance — Mastery Library', 'edition': '0.1',
            'edition_boundary': '2026-10-06', 'planned_volumes': 18, 'planned_chapters': 216,
            'primary_research_field': 'Macro-finance', 'supporting_field': 'Financial econometrics',
            'volumes': VOLUMES}
    destination.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print(f'Defined {len(VOLUMES)} volumes and {sum(len(v["chapters"]) for v in VOLUMES)} chapter packages.')

if __name__ == '__main__':
    main()
