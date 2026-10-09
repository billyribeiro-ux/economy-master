# Economics & Finance Mastery — Production Contract

Edition boundary: 6 October 2026. Owner: Codex, acting as curriculum designer, author, and editorial judge. User brief: teach from the beginning through the knowledge, reasoning, research, teaching, and leadership capabilities needed for exceptional performance in leading academic and financial institutions; remove filler while retaining essential depth.

## Deliverable

A substantive original textbook library in static HTML, readable offline and privately hosted through Sites. A shared print edition supports browser Save as PDF without maintaining a separate manuscript. The complete scope is **18 volumes, 216 specified chapters**, 18 volume assessment packages, 18 substantial projects, cross-volume examinations, a glossary and notation guide, an indexed source catalogue, reproducible computation materials, and research/teaching/leadership portfolios.

The canonical chapter titles, outcomes, coverage, prerequisites, and production state are in `book/content/curriculum.json`. The current production checkpoint is `book/STATUS.json`. Each numbered volume has 12 chapters. The plan is complete; the manuscript becomes complete only when its acceptance gates pass. Topic coverage and the user's aspirational career outcomes must not be confused with a university credential or a guaranteed institutional appointment.

## Mastery definition

The learner must be able to (1) explain and derive central economic and financial results; (2) solve unfamiliar problems and choose appropriate methods; (3) identify credible empirical evidence and threats to inference; (4) implement reproducible analysis; (5) read, critique and extend research; (6) teach coherent advanced courses and supervise research; and (7) lead people, budgets, risk and governance under uncertainty.

Broad command is required throughout the common core. Frontier expertise is assessed in a defined specialization. The default primary field is macro-finance; the supporting field is financial econometrics. Alternative field portfolios can be added without weakening the common core. Research findings may be uncertain or contested: state what a model implies, what evidence supports, and what remains unresolved.

## Volume sequence

1. Foundations of economic and financial reasoning.
2. Mathematics for economics and finance.
3. Probability, statistics and decisions under uncertainty.
4. Data, computation and empirical reasoning.
5. Microeconomics and strategic interaction.
6. Macroeconomics and the international economy.
7. Accounting and business analysis.
8. Corporate finance and valuation.
9. Investments and asset pricing.
10. Fixed income, derivatives and quantitative finance.
11. Banking, risk and international finance.
12. Advanced econometrics and causal inference.
13. Graduate microeconomics and economic theory.
14. Graduate macroeconomics and macro-finance.
15. Economic fields, institutions, history and policy.
16. Specialization and original research.
17. Teaching, communication and research supervision.
18. Strategy, governance and institutional leadership.

The default reading path follows this sequence. Volume-level dependencies are a directed acyclic graph in the curriculum. Every chapter also declares local prerequisites. Advanced tools are taught before the chapters that rely on them. Teaching practice begins with simple explanation exercises in Volume 1; real leadership practice and seminar participation develop alongside later study.

## Minimum chapter package

Every chapter contains:

- A precise capability objective and explicit prerequisites.
- A motivating problem; definitions and notation before use.
- An intuitive explanation followed by the appropriate formal treatment.
- At least two fully worked examples; at least three in graduate technical chapters.
- Assumptions, units, boundary cases, and conditions under which conclusions change.
- At least eight original exercises, spanning recall, calculation, explanation, transfer and critique. Graduate technical chapters contain at least ten, including proof/derivation and research critique.
- Complete solutions for determinate problems; explicit evaluation criteria and illustrative reasoning for open-ended questions.
- A short teach-back prompt and a retention check.
- Sources and a clear extension into deeper study where the chapter is not exhaustive.
- A review record covering factual accuracy, mathematical reasoning, arithmetic, instruction and cross-references.

Length is subordinate to these requirements. Planning ranges are approximately 1,200–2,500 instructional words for foundations and 2,000–4,000 for advanced technical chapters, excluding some problem solutions. These are guides, not padding quotas. A short overview cannot substitute for a chapter that needs derivations, proofs or substantial evidence.

## Volume package

Each volume requires all 12 accepted chapter packages plus:

1. A cumulative examination and a distinct reassessment form, with solutions and explicit scoring.
2. An integrative project with inputs/data, deliverables, an evaluation rubric, and an instructor guide or benchmark implementation.
3. A prerequisite diagnostic, a remediation map and a delayed retention assessment.
4. A notation/concept index and a concise synthesis connecting the volume to its successors.

Closed-book conceptual/derivation tests and open-resource empirical/computational work serve different purposes and must be labeled accordingly. Determinate questions have correct answers. Open decisions may have several defensible answers; grade evidence, assumptions, reasoning and implementation rather than conformity to an opinion.

## Cross-volume assessments

- Foundation examination: Volumes 1–4, including a basic data-analysis task.
- Economics core examination: Volumes 5–6, using tools from 1–4.
- Finance core examination: Volumes 7–11, with valuation, portfolio and institutional-risk cases.
- Graduate qualifying sequence: Volumes 12–14, in econometrics, micro theory and macro-finance, with distinct reassessment forms.
- Integrated policy/investment case: economic mechanism, identification, valuation, distribution and institutional feasibility.
- Research portfolio: replication package, two referee reports, research proposal, original paper and oral-defense protocol.
- Teaching portfolio: undergraduate and graduate syllabi, sample teaching materials, assessments and rubrics, observed-teaching protocol and supervision plan.
- Leadership portfolio: strategy memo, budget, governance map, hiring/incentive plan, crisis exercise and retrospective on real responsibility.

Research, observed teaching and real leadership competence require external human evaluation and experience. The library supplies the instruction and assessment protocols; it must not claim those learner-specific achievements have already occurred.

## Scoring and advancement

Use criterion-based rubrics. Proposed default for author-created numerical/conceptual examinations: at least 85% overall and no essential skill domain below 75%, followed by a transfer problem and teach-back. These thresholds are our design choices, not Harvard or MIT requirements. A critical error in identification, units, budget balance, risk interpretation or integrity requires remediation even if the aggregate score passes. Advanced research assessment uses argument-specific rubrics and independent expert feedback, not a single percentage.

## Evidence and source policy

Benchmark the scope against the current official requirements of Harvard Economics, Harvard Business School Business Economics, MIT Economics and Wharton Finance. These sources establish curricular benchmarks; they do not certify this library. Use primary sources for methods, evidence and current institutional facts. Prefer authors' original papers, official course materials, open textbooks, official datasets and regulatory publications. Use classic textbooks as further-reading references when accessible; do not fabricate editions, page numbers or article claims.

The source catalogue records title, URL, use, date checked and verification status. A checked link does not mean the entirety of its contents has been independently verified. Chapter citations must support the associated claim. Derived examples and exercises are original. No wholesale paraphrase or reproduction of copyrighted books or exam banks.

Time-varying laws, policies, product specifications and market data require a date and jurisdiction. No invented October 2026 observations. Historical datasets retain their release/vintage information. Empirical projects must record provenance, units, transformations, availability and license/access constraints.

## Editorial workflow

For each dependency-ready chapter:

1. Read its specification, dependencies and established notation.
2. Retrieve only the sources required for unresolved facts or specialist methods; reuse verified stable references.
3. Write the chapter and problems directly in the editable manuscript.
4. Independently recompute numerical examples and verify derivations and counterexamples.
5. Solve every exercise and compare its solution to the exact prompt.
6. Check whether a learner has been taught every method required by the exercises.
7. Build and check links, citations, headings, accessibility and print behavior.
8. Record acceptance or concrete review issues; select the next dependency-ready item.

Chapter states: `planned`, `draft`, `review`, `accepted`. A written summary without the required package remains `draft`. Source/link checking is separate from subject-matter review. Volume states: `planned`, `writing`, `assessment`, `review`, `accepted`. Counters are generated from actual content and review records.

## Production batches

- Batch 0: freeze the curriculum, checkpoint/resumption rules, source catalogue and HTML architecture.
- Batches 1–18: complete each volume in order, including its exam/project package and corrections.
- Cumulative assessments can be produced as soon as their prerequisite volumes are accepted; the foundation examination follows Volumes 1–4. Their canonical specifications and individual states are recorded in `content/curriculum.json` under `cross_volume_assessments`.
- Batch 19: complete any remaining cross-volume examinations, glossary/notation consolidation and computational appendices.
- Batch 20: audit the entire prerequisite graph, coverage, all problems/solutions, citations, offline behavior, mobile layout and print edition; repair every material issue.
- Batch 21: publish the complete accepted edition privately; provide the finished offline archive and an honest validation report.

Publish meaningful intermediate editions only after coherent material exists; clearly distinguish finished reading content from the production map. Never publish fake chapters or treat a skeleton as the book. Reuse the same Site project throughout.

## Efficient implementation

Use plain HTML, local CSS/JavaScript, and standard-library Python to generate navigation, indexing and the print edition. Search must work from `file://` without network requests. Avoid frameworks, generated decorative imagery, paid APIs, dependency churn, redundant rewriting and repetitive browsing. This reduces overhead; it does not remove necessary derivations, practice or review. Do not use repeated boilerplate to inflate apparent coverage.

## Parallel production

On 7 October 2026 the user explicitly authorized parallel economics/finance specialists. Use up to three specialist authors alongside the coordinating author. Before dispatch, persist each assignment's exact chapter scope, owned paths, prerequisite assumptions, deliverables and review gates in `book/production/`. Preserve those boundaries throughout the assignment. Specialists may draft adjacent chapters simultaneously against the agreed prerequisite specifications; acceptance still follows the dependency graph.

Each specialist owns its chapter, distinctly prefixed supporting files, checker, proposed-source list and author review. The coordinator alone changes the canonical curriculum, source catalogue, checkpoint, shared build/verification code and hosting state; independently audits submitted content and solutions; and publishes coherent accepted batches. Specialists do not publish, overwrite another assignment or spawn further agents. Reuse verified stable sources and the existing implementation. Review reduces error risk but is not a guarantee of error-free work or independent human certification.

## Continuity protocol

On 9 October 2026 the user reaffirmed that the coordinating author is the chief architect and should resolve architecture, curriculum and production questions using hard evidence. Make those decisions independently, preserve the evidence and its limits, and continue authorized work without routine clarification requests. An inaccessible authenticated surface remains an observed limitation, not evidence that its checks passed.

Keep an active goal until the terminal checklist passes. After every coherent batch, update `book/STATUS.json` with the exact last completed work, pending review issues and next actions. On continuation, read this plan and checkpoint, inspect the current manuscripts, and continue from the first unfinished task. Do not restart planning, silently reduce scope or repeatedly ask the user to continue. User corrections amend the contract and checkpoint while preserving completed work.

If a source, credential or deployment step is temporarily unavailable, continue independent authoring and verification. Record the concrete blocker and return to it. A lost publishing credential does not justify a replacement Site. The same project ID and latest successful source state must be retained.

## Terminal acceptance checklist

- [ ] All 216 chapter specifications have complete accepted manuscripts.
- [ ] All 18 volume packages contain diagnostic, two exams, project, solutions, rubrics and retention check.
- [ ] All cross-volume assessments and research/teaching/leadership protocols exist.
- [ ] The glossary, notation guide, citations and source catalogue are internally consistent.
- [ ] All worked examples and determinate solutions have been checked; derivations/proofs have explicit assumptions.
- [ ] All material editorial review issues are resolved or honestly identified as limitations requiring external expert review.
- [ ] No planned or draft chapter is presented as accepted; coverage counts match real content.
- [ ] All internal links, offline search, keyboard navigation, mobile reading and print layouts work.
- [ ] Reproducible project code and supplied datasets have documented provenance and pass meaningful checks.
- [ ] The final private deployment succeeds, and the complete offline edition is delivered.
- [ ] The handoff reports the actual scope, verification and remaining limits without guaranteeing career outcomes.

The author judges manuscript completion. Becoming an exceptional researcher, teacher or leader is demonstrated through the learner's work and independent evaluation over time.
