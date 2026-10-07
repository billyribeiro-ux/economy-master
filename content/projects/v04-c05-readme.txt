V04-C05 DESCRIPTIVE GRAPHICS — ORIGINAL SYNTHETIC LAB

Keep v04-c05-charts.py and v04-c05-data.json together. Python 3.10+ standard
library only. No network, package installation or empirical-data download.
  python3 v04-c05-charts.py
prints the original cases' numerical results without changing any file.
  python3 v04-c05-charts.py --write-figures figures
also creates/updates exactly four prefixed SVG files inside the specified
directory. Use a separate output directory, not the frozen input file's name.
The program locates its input relative to itself, not the working directory.

The supplied data metadata states units, grain, quantile convention, synthetic
provenance and permitted teaching reuse. This is a finite teaching fixture;
it does not implement validation of arbitrary external statistical datasets.

Expected values:
Income: mean25, midpoint median19, Q1=13.5, Q3=23.5, IQR10, upperfence38.5.
Bin counts4,3,1; shares1/2,3/8,1/8; densities1/40,3/160,1/320 per thousand USD.
Revenue indices A100,120,144,172.8; B100,110,121,133.1; growth .20/.10 yearly.
Scatter: pooled centered crossproduct86, squared-x58, squared-y154; each group
has centered crossproduct-2 and x/y sums of squares2, correlation-1.
Uncertainty: marginal intervals [92.16,107.84] and [104.16,119.84]; difference12,
SE sqrt(32), difference interval approximately [.91,23.09] USD under independence.

SVGs are editable/exportable vector data charts; open a copy to enlarge them.
The chapter supplies the same observations in text/tables and explains the
conclusions and assumptions. Exact fractions are used where inputs permit;
display coordinates and normal-interval calculations use floating arithmetic.
Numerical/coordinate verification is distinct from visual/browser rendering QA.

For reproduction, copy only the program/input into a clean directory, run the
report, generate SVGs in a fresh folder and compare the values above. Reordering
incomes cannot change the histogram, but changing edges can; do not treat bins
as a statistical truth. Reporting a synthetic uncertainty model does not make
these observations a real sample. Code/fixtures created2026-10-07 for the
2026-10-06 edition boundary. No causal result is inferred from the figures.

Modification exercise: figure descriptions, base-year labels and axis limits are
tailored to the supplied fixture. A new bin scheme/base year/dataset requires
reviewing and updating the figure function, labels, descriptions and limits
together. Check coverage and actual coordinates again; input edits alone do not
make hard-coded annotations correct. Keep the original fixture for reproduction.
