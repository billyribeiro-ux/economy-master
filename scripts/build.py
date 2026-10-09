"""Build a readable, offline HTML library. No dependencies or network required."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def plaintext(value):
    parser = Text(); parser.feed(value)
    return ' '.join(' '.join(parser.parts).split())

def status_label(value):
    return 'Author-reviewed' if value == 'accepted' else value.title()

def print_fragment(body, prefix):
    """Namespace local anchors when many independent pages share print.html."""
    ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', body))
    body = re.sub(r'\bid=(["\'])([^"\']+)\1',
                  lambda m: 'id='+m[1]+prefix+'--'+m[2]+m[1], body)
    return re.sub(r'\bhref=(["\'])#([^"\']+)\1',
                  lambda m: 'href='+m[1]+'#'+(prefix+'--' if m[2] in ids else '')+m[2]+m[1], body)

def main():
    original_plan = ROOT.parent/'MASTER_PLAN.md'
    if original_plan.exists():
        shutil.copyfile(original_plan, ROOT/'PRODUCTION_PLAN.md')
    plan = json.loads((ROOT/'content/curriculum.json').read_text())
    sources = json.loads((ROOT/'content/sources.json').read_text())
    source_map = {s['id']: s for s in sources}
    chapters = [(v, c) for v in plan['volumes'] for c in v['chapters']]
    manuscripts = {c['id']: (ROOT/'content'/c['manuscript']).read_text()
                   for _, c in chapters if (ROOT/'content'/c['manuscript']).exists()}
    # Forward references to unwritten chapters lead to their labeled curriculum
    # entry. Do not generate empty chapter pages or hide genuinely unknown links.
    planned_targets = {c['id'] for _, c in chapters if c['id'] not in manuscripts}
    def chapter_links(body):
        return re.sub(r'\bhref=(["\'])(v\d{2}-c\d{2})\.html(?:#[^"\']*)?\1',
                      lambda m: 'href='+m[1]+'curriculum.html#'+m[2]+m[1]
                      if m[2] in planned_targets else m[0], body)
    manuscripts = {cid: chapter_links(body) for cid, body in manuscripts.items()}
    packages = {v['id']: (ROOT/'content/assessments'/f'{v["id"]}.html').read_text()
                for v in plan['volumes'] if (ROOT/'content/assessments'/f'{v["id"]}.html').exists()}
    cross_specs = plan.get('cross_volume_assessments', [])
    cross_packages = {a['id']: (ROOT/'content'/a['manuscript']).read_text()
                      for a in cross_specs if (ROOT/'content'/a['manuscript']).is_file()}
    written = len(manuscripts)
    accepted = sum(c['status'] == 'accepted' for _, c in chapters)
    DIST.mkdir(exist_ok=True)
    for name in ('book.css', 'book.js'):
        shutil.copyfile(ROOT/'assets'/name, DIST/name)
    for path in (ROOT/'content/projects').glob('*'):
        if path.is_file():
            # Partial labs can precede their manuscripts during production.
            # Keep them in source, but do not distribute an unwritten chapter's
            # unfinished attachments as part of the reading edition.
            chapter_asset = re.match(r'^(v\d{2}-c\d{2})-', path.name)
            if chapter_asset and chapter_asset[1] not in manuscripts:
                generated = DIST/path.name
                if generated.is_file():
                    generated.unlink()
                continue
            shutil.copyfile(path,DIST/path.name)

    def source_list(ids):
        result = '<ul class="reading-list">'
        for sid in ids:
            s = source_map[sid]
            result += f'<li><a href="{escape(s["url"], quote=True)}">{escape(s["title"])}</a> — {escape(s["use"])}</li>'
        return result + '</ul>'

    def sidebar(current=''):
        result = '<aside class="sidebar" id="book-navigation"><a class="brand" href="index.html"><span>Mastery Library</span>Economics<br>&amp; Finance</a><p class="edition">Working edition · 6 October 2026</p>'
        for url, label in [('index.html','Reading guide'), ('curriculum.html','Full curriculum'), ('assessments.html','Assessment standard'), ('sources.html','Sources &amp; further study'), ('print.html','Print reading edition')]:
            result += f'<a href="{url}"' + (' aria-current="page"' if current == url else '') + f'>{label}</a>'
        result += '<hr><nav aria-label="Volumes">'
        for v in plan['volumes']:
            available = [c for c in v['chapters'] if c['id'] in manuscripts]
            opened = any(current == c['id']+'.html' for c in v['chapters'])
            result += f'<details{" open" if opened else ""}><summary>{v["number"]:02d} · {escape(v["title"])}</summary><ul>'
            for c in available:
                page = c['id']+'.html'
                result += f'<li><a href="{page}"' + (' aria-current="page"' if current == page else '') + f'>{c["number"]:02d}. {escape(c["title"])}</a></li>'
            remaining = len(v['chapters']) - len(available)
            if remaining:
                result += f'<li><a href="curriculum.html#{v["id"]}" class="planned">{remaining} chapter packages planned</a></li>'
            if v['id'] in packages:
                result += f'<li><a href="{v["id"]}-assessment.html">Diagnostic, exams &amp; project</a></li>'
            result += '</ul></details>'
        result += '</nav>'
        if cross_packages:
            result += '<hr><nav aria-label="Cumulative assessments">'
            for a in cross_specs:
                if a['id'] in cross_packages:
                    result += f'<a href="{a["page"]}"' + (' aria-current="page"' if current == a['page'] else '') + f'>{escape(a["title"])}</a>'
            result += '</nav>'
        return result + '</aside>'

    def write_page(filename, title, content, wide=False):
        favicon = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E%3Crect width=%2232%22 height=%2232%22 rx=%224%22 fill=%22%23111e31%22/%3E%3Cpath d=%22M7 8h8v17H7zm10 0h8v17h-8%22 fill=%22%23fff%22/%3E%3Cpath d=%22M15 8h2v17h-2%22 fill=%22%23ad253c%22/%3E%3C/svg%3E'
        html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Original instruction in economics and finance, from foundations through research, teaching and leadership."><title>{escape(title)} · Economics &amp; Finance</title><link rel="icon" type="image/svg+xml" href="{favicon}"><link rel="stylesheet" href="book.css"><script defer src="search-index.js"></script><script defer src="book.js"></script></head>
<body><a class="skip" href="#main">Skip to reading</a><div class="layout">{sidebar(filename)}<div class="workspace"><header class="toolbar"><button class="menu-toggle" aria-expanded="false" aria-controls="book-navigation">Contents</button><form class="search" role="search"><label class="skip" for="query">Search the book and curriculum</label><input id="query" name="query" type="search" placeholder="Search a concept or chapter" aria-label="Search the book and curriculum"><button type="submit">Search</button></form><button class="print-button" data-print>Print this page</button></header><section class="search-results" id="search-results" aria-live="polite" hidden></section><main id="main" class="reader{' wide' if wide else ''}">{content}<footer>Original instructional material · Edition boundary: 6 October 2026.<br>University curricula inform the benchmark. This independent library is not affiliated with or accredited by those institutions.</footer></main></div></div></body></html>'''
        (DIST/filename).write_text(html)

    reading = '<ul>' + ''.join(f'<li><a href="{c["id"]}.html">{escape(c["title"])}</a> <span class="status">{escape(status_label(c["status"]))}</span></li>' for _, c in chapters if c['id'] in manuscripts) + '</ul>'
    intro = f'''<p class="eyebrow">Reading guide</p><h1>Economics &amp; Finance</h1><p class="lead">Learn to reason, calculate, investigate, teach, and lead. Begin with the foundations; advance by demonstrating what you can do.</p><div class="stats"><div><strong>18</strong><span>Volumes specified</span></div><div><strong>216</strong><span>Chapter packages planned</span></div><div><strong>{written}</strong><span>Chapters available to read</span></div><div><strong>{accepted}</strong><span>Chapter packages author-reviewed</span></div></div><p class="notice">This is a growing manuscript. The complete production plan is defined; unfinished chapters are labeled Planned. Draft chapters remain subject to review. Author-reviewed means internal editorial and numerical checks, not independent academic certification. Reading a chapter and demonstrating mastery are separate steps.</p><h2>Read now</h2>{reading if written else '<p>The first chapter is being written. The complete curriculum and assessment standard are available below.</p>'}<h2>How to study</h2><div class="prose"><p>Read the objective and prerequisites first. Work through each example on paper, then close the explanation and reconstruct it. Attempt the exercises before opening the solutions. Explain the central mechanism in ordinary language and check the conditions under which it holds.</p><p>Use unfamiliar problems, cumulative examinations, reproducible projects, and teaching demonstrations to test transfer. A correct formula without an explanation of its assumptions is incomplete understanding.</p><p>The common core builds broad competence. The later research path develops depth in macro-finance and financial econometrics. Original research, observed teaching and real leadership require independent feedback and experience.</p></div><div class="toc-links"><a href="curriculum.html">Explore the full curriculum</a><a href="assessments.html">Read the assessment standard</a><a href="print.html">Open the printable reading edition</a></div><h2>The path</h2><ol class="volume-list">'''
    for v in plan['volumes']:
        intro += f'<li><p class="eyebrow">Volume {v["number"]:02d} · {v["level"]}</p><h2><a href="curriculum.html#{v["id"]}">{escape(v["title"])}</a></h2><p>{escape(v["assessment"])}</p></li>'
    write_page('index.html','Reading guide',intro+'</ol>')

    curriculum = '<p class="eyebrow">Complete production map</p><h1>The mastery curriculum</h1><p class="lead">18 volumes. 216 chapter packages. Every chapter has a defined objective, scope and prerequisite.</p><p class="notice">A curriculum entry is a specification, not a substitute for its manuscript. Only chapters with reading links have text available.</p>'
    for v in plan['volumes']:
        prereq = ', '.join(v['prerequisites']) or 'None — begin here'
        curriculum += f'<section id="{v["id"]}"><p class="eyebrow">Volume {v["number"]:02d} · {v["level"]}</p><h2>{escape(v["title"])}</h2><p class="meta">Prerequisites: {escape(prereq)}</p><p><strong>Demonstrate:</strong> {escape(v["assessment"])}</p><p><strong>Project:</strong> {escape(v["project"])}</p>'
        for c in v['chapters']:
            title = escape(c['title'])
            if c['id'] in manuscripts:
                title = f'<a href="{c["id"]}.html">{title}</a>'
            curriculum += f'<div class="curriculum-chapter" id="{c["id"]}"><h3>{c["number"]:02d}. {title} <span class="status">{status_label(c["status"])}</span></h3><p>{escape(c["outcome"])}</p><p class="coverage">Scope: {escape(" · ".join(c["coverage"]))}</p><p class="meta">Prerequisites: {escape(", ".join(c["prerequisites"]) or "None")} · {c["required_worked_examples"]} worked examples · {c["required_exercises"]} exercises with solutions or evaluation criteria</p></div>'
        curriculum += '</section>'
    write_page('curriculum.html','Full curriculum',curriculum,True)

    assessment = '''<p class="eyebrow">Assessment standard</p><h1>Demonstrate mastery</h1><div class="prose"><p>Progress is earned through correct reasoning, transfer to unfamiliar problems, credible empirical analysis, and clear explanation. Studying time and page counts are inputs; they do not establish competence.</p><h2>Every chapter</h2><p>Complete at least eight original exercises (ten in graduate technical chapters), reconstruct the worked examples, explain a mechanism without notes, and answer a later retention question. Determinate problems have complete solutions. Open questions have evaluation criteria and may admit several defensible answers.</p><h2>Every volume</h2><p>Complete a prerequisite diagnostic, cumulative examination, distinct reassessment form, integrative project, oral explanation, and delayed retention check. Projects specify inputs, outputs, assumptions, uncertainty, reproducibility and scoring. Volume-specific examination and project materials will appear when their packages are written.</p><h2>Advancement criteria</h2><p>Our proposed default for numerical/conceptual exams is at least 85% overall with no essential domain below 75%, plus a transfer problem and teach-back. These are design choices for this library, not university requirements. Critical errors in identification, units, budget balance, risk interpretation or integrity require correction regardless of the total.</p><h2>Graduate and research assessment</h2><p>Graduate work adds proofs, derivations, model critique, empirical identification and numerical diagnostics. The research portfolio includes replication, referee reports, a proposal, original work and an oral defense. Qualified researchers must evaluate its contribution and correctness; the book cannot award that judgment automatically.</p><h2>Teaching and leadership</h2><p>A teaching portfolio contains undergraduate and graduate syllabi, lessons, assessments, grading criteria, observed teaching and research-supervision plans. A leadership portfolio contains strategy, budgets, decision rights, hiring and incentives, risk and crisis decisions, and a retrospective on real responsibility. Independent observation and real experience are essential.</p><h2>Editorial acceptance</h2><p>A chapter package is accepted only after its instruction, worked examples, exercises, solutions, sources and review record satisfy the production contract. Source-link checks, numerical checks and subject-matter review are recorded separately. Draft is a transparent production state, not a mastery credential.</p></div>'''
    if packages:
        assessment += '<h2>Available volume packages</h2><ul>'
        for v in plan['volumes']:
            if v['id'] in packages:
                assessment += f'<li><a href="{v["id"]}-assessment.html">Volume {v["number"]:02d}: {escape(v["title"])}</a></li>'
        assessment += '</ul>'
    if cross_specs:
        assessment += '<h2>Cumulative examinations and portfolios</h2><p>Each assessment combines its prerequisite volumes. Planned entries specify future work; available links open written material.</p>'
        for a in cross_specs:
            title = escape(a['title'])
            if a['id'] in cross_packages:
                title = f'<a href="{a["page"]}">{title}</a>'
            assessment += f'<section id="{a["id"]}"><h3>{title} <span class="status">{status_label(a["status"])}</span></h3><p>{escape(a["outcome"])}</p><p>{escape(a["deliverables"])}</p><p class="meta">Prerequisites: {escape(", ".join(a["prerequisites"]))}</p></section>'
    write_page('assessments.html','Assessment standard',assessment)
    for v in plan['volumes']:
        if v['id'] in packages:
            write_page(v['id']+'-assessment.html',v['title']+' — assessment',packages[v['id']])
    for a in cross_specs:
        if a['id'] in cross_packages:
            write_page(a['page'],a['title'],f'<p class="meta">{status_label(a["status"])}</p>'+cross_packages[a['id']])

    catalogue = '<p class="eyebrow">Evidence and further study</p><h1>Source catalogue</h1><p class="lead">Curricular benchmarks establish scope. Method-specific sources and original papers support individual arguments.</p><p class="notice">These are sources and further-reading routes, not institutional endorsements. Checking a course page does not independently verify every topic taught in the course. Examples and exercises in this library are original.</p>'
    for s in sources:
        catalogue += f'<section id="{s["id"]}"><h2><a href="{escape(s["url"],quote=True)}">{escape(s["title"])}</a></h2><p>{escape(s["use"])}</p><p class="meta">Checked {s["checked"]} · {escape(s["verification"])}</p></section>'
    write_page('sources.html','Sources and further study',catalogue)

    search_index = []
    print_content = f'<section class="print-cover"><p class="eyebrow">Reading edition · {plan["edition"]}</p><h1>Economics &amp; Finance</h1><p class="lead">{written} available chapters from a planned 18-volume mastery library.</p><p>Edition boundary: 6 October 2026.</p><p class="notice">This print edition contains the actual manuscripts currently available. It does not include planned chapters as if they were written. Draft status remains visible. Solutions are expanded when printing.</p><button class="no-print" data-print>Print or save as PDF</button></section>'
    for position, (v,c) in enumerate(chapters):
        body = manuscripts.get(c['id'])
        search_index.append({'title': f'{v["number"]:02d}.{c["number"]:02d} · {c["title"]}',
                             'url': c['id']+'.html' if body else 'curriculum.html#'+c['id'],
                             'written': body is not None, 'status': status_label(c['status']),
                             'text': plaintext(body) if body else c['outcome']+' '+' '.join(c['coverage'])})
        if body is None:
            continue
        prereq = ', '.join(c['prerequisites']) or 'None — begin here'
        header = f'<p class="eyebrow">Volume {v["number"]:02d} · Chapter {c["number"]:02d}</p><h1>{escape(c["title"])}</h1><div class="meta"><p>{v["level"]} <span class="status">{status_label(c["status"])}</span> · Prerequisites: {escape(prereq)}</p></div><div class="objective"><span class="label">By the end</span>{escape(c["outcome"])}</div>'
        refs = re.findall(r'data-source="([^"]+)"',body)
        further = '<h2>Sources and further study</h2>'+source_list(list(dict.fromkeys(c['sources']+refs)))
        before = next((pc for _,pc in reversed(chapters[:position]) if pc['id'] in manuscripts),None)
        after = next((pc for _,pc in chapters[position+1:] if pc['id'] in manuscripts),None)
        navigation = '<nav class="chapter-navigation" aria-label="Chapter navigation">'
        if before:
            navigation += f'<a href="{before["id"]}.html">Previous: {escape(before["title"])}</a>'
        if after:
            navigation += f'<a href="{after["id"]}.html">Next: {escape(after["title"])}</a>'
        else:
            navigation += '<a href="curriculum.html">See the remaining curriculum</a>'
        navigation += '</nav>'
        write_page(c['id']+'.html',c['title'],header+'<article class="prose">'+body+'</article>'+further+navigation)
        print_content += f'<section class="print-chapter" id="{c["id"]}">{header}<article class="prose">{print_fragment(body,c["id"])}</article>{further}</section>'
        if c['number']==len(v['chapters']) and v['id'] in packages:
            print_content += f'<section class="print-chapter">{print_fragment(packages[v["id"]],v["id"]+"-assessment")}</section>'
        if c['number']==len(v['chapters']):
            for a in cross_specs:
                if a['after_volume']==v['number'] and a['id'] in cross_packages:
                    print_content += f'<section class="print-chapter"><p class="meta">{status_label(a["status"])}</p>{print_fragment(cross_packages[a["id"]],a["id"]+"-assessment")}</section>'
    for v in plan['volumes']:
        if v['id'] in packages:
            search_index.append({'title':f'Volume {v["number"]:02d} assessment · {v["title"]}',
                'url':v['id']+'-assessment.html','written':True,'status':status_label(v['status']),
                'text':plaintext(packages[v['id']])})
    for a in cross_specs:
        body = cross_packages.get(a['id'])
        search_index.append({'title':a['title'],'url':a['page'] if body else 'assessments.html#'+a['id'],
            'written':body is not None,'status':status_label(a['status']),
            'text':plaintext(body) if body else a['outcome']+' '+a['deliverables']})
    write_page('print.html','Printable reading edition',print_content)
    (DIST/'search-index.js').write_text('window.MASTERY_SEARCH = '+json.dumps(search_index,ensure_ascii=False).replace('</','<\\/')+';\n')
    summary = {'volumes_planned':len(plan['volumes']),'chapters_planned':len(chapters),
               'chapters_available':written,'chapters_accepted':accepted,
               'manuscript_words':sum(len(plaintext(body).split()) for body in manuscripts.values()),
               'assessment_packages_available':len(packages),
               'assessment_words':sum(len(plaintext(body).split()) for body in packages.values()),
               'cross_volume_assessments_available':len(cross_packages),
               'cross_volume_assessments_accepted':sum(a['status']=='accepted' for a in cross_specs),
               'cross_volume_assessment_words':sum(len(plaintext(body).split()) for body in cross_packages.values())}
    (ROOT/'build-report.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))

if __name__ == '__main__':
    main()
