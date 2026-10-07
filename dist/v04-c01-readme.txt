V04-C01 — REPRODUCIBLE WORK AND DATA PROVENANCE

Purpose: reproduce two explicitly dated summaries of a synthetic three-month
spending history. This demonstrates vintages, units, validation and frozen input;
it is neither an empirical estimate nor a causal study.

Keep v04-c01-provenance.py, v04-c01-releases.json and this README together.
The input JSON supplies creator, permission, units, dictionary and coverage.
Python 3.10 or newer, standard library only; no package installation or network.
Record the precise runtime printed in the output for your run. Relative default
input paths are resolved from the program location, not your current directory.

From the directory containing these files, run:
  python3 v04-c01-provenance.py --cutoff 2025-04-20
  python3 v04-c01-provenance.py --cutoff 2025-05-20
To save the first output, redirect to a NEW file:
  python3 v04-c01-provenance.py --cutoff 2025-04-20 > april-result.json
Never use the input's filename as an output destination.

The complete result is printed as sorted JSON; no files are altered. Expected:
April cutoff: nominal total 353000 USD; real total 320000 base-price USD;
  real January-to-March growth 1/10; nominal growth 8/25.
May cutoff: nominal total 360000 USD; real total 2998000/9 base-price USD;
  real January-to-March growth 3/17; nominal growth 6/17.
Fractions are exact; decimals are display conversions. Growth is a fraction,
not percent. Multiply by 100 when reporting percent. Totals aggregate monthly
flows; growth compares endpoints and is not annualized.

Each report includes selected release rows, inclusive cutoff, input SHA-256 and
Python runtime. Byte-identical inputs must reproduce the digest. Reformatting
or reordering JSON changes its bytes/digest, even when the same observations
produce the same analytical result. SHA-256 is a fingerprint, not a source or
truth certificate. Compare to the separately supplied v04-c01-manifest.json.

Date convention: YYYY-MM-DD; after the listed day's release, no intraday data.
Both spending and prices are released jointly in this synthetic example.
In a real workflow independently released series need separate availability
records and an explicit timezone/intraday cutoff where relevant.

Failure demonstrations: --cutoff 2025-04-01 returns nonzero status because March
is unavailable; duplicate period/date rows, wrong units, missing fields, invalid
dates, negative spending or nonpositive index also fail. Zero first-period
spending is valid data but makes the specified growth output undefined, so that
summary fails explicitly. Use a separately named COPY to try modified inputs:
  python3 v04-c01-provenance.py --cutoff 2025-04-20 --input my-case.json

This case treats each monthly value as a completed realized flow, so its
availability date cannot precede that month's last day. Month-end itself is
permitted under the after-day convention. Forecasts/partial-month estimates
would need a different, explicitly labeled observation contract.

Reproduction audit: copy the supplied files into a clean folder; run both dates;
compare exact results and selected rows above, then confirm the supplied input
digest. A separate runtime version need not make the mathematical results
different; the runtime field itself will differ. There is no random sampling.

Creation and reuse: original library teaching material, 2026-10-07. The synthetic
fixture and this laboratory code may be used, modified and redistributed for
teaching and research with attribution to the Economics & Finance Mastery
Library. No external empirical data are included. This permission is specific
to these original materials and grants no rights over linked third-party data.
