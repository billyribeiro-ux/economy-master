"""Package only reader-facing files and the production plan; never credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json

ROOT=Path(__file__).resolve().parents[1]
destination=ROOT.parent/'economics-finance-mastery-offline.zip'
report=json.loads((ROOT/'build-report.json').read_text())
readme=f'''Economics & Finance — Mastery Library

Open mastery-library/index.html in a browser. No installation or server is needed.
Chapter navigation, search and print work offline. External further-reading links
require internet access. To make a PDF, open print.html and use Print / Save as PDF.

Content edition: {report['chapters_available']} readable chapters in the 18-volume,
216-chapter curriculum. {report['chapters_accepted']} chapter packages have author
editorial/numerical review. This is not independent academic certification.
Volume assessment/project packages: {report['assessment_packages_available']}.
Cross-volume assessments and portfolios: {report['cross_volume_assessments_accepted']}.
Actual learner research, teaching and leadership require real work and human review.

PRODUCTION_PLAN.md defines the scope and completion standards.
Original synthetic teaching cases are labeled. Historical empirical extracts
identify their official sources, release vintages, units and access conditions.
The optional Python project benchmark needs only standard-library Python.
Edition boundary: 6 October 2026.
'''
with ZipFile(destination,'w',compression=ZIP_DEFLATED) as archive:
    for path in sorted((ROOT/'dist').iterdir()):
        if path.is_file(): archive.write(path,'mastery-library/'+path.name)
    archive.write(ROOT/'PRODUCTION_PLAN.md','PRODUCTION_PLAN.md')
    archive.writestr('READ-ME.txt',readme)
with ZipFile(destination) as archive:
    assert archive.testzip() is None
    assert 'mastery-library/index.html' in archive.namelist()
print(json.dumps({'archive':str(destination),'files':len(archive.namelist()),'bytes':destination.stat().st_size}))
