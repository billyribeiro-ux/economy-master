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

Working edition: {report['chapters_available']} readable chapters from an 18-volume,
216-chapter production plan. {report['chapters_accepted']} chapter packages have author
editorial/numerical review. This is not independent academic certification.
The whole library remains in production. Planned entries are not manuscripts.

PRODUCTION_PLAN.md defines the scope and completion standards.
All supplied business-case numbers are synthetic.
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
