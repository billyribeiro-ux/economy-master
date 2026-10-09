"""Integrate the complete, separately reviewed Volume 12 assessment package."""
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ('v12-support-opening.html', 'v12-exam-a.html', 'v12-exam-b.html',
         'v12-project.html', 'v12-support-closing.html')


class Assembly(HTMLParser):
    """Check shared structure without imposing one component's rubric format."""
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                raise ValueError('Duplicate V12 assessment ID: ' + attrs['id'])
            self.ids.add(attrs['id'])
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input', 'wbr'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError('Unbalanced V12 assessment HTML: ' + tag)


def check():
    from check_v12_support import check as support
    from check_v12_exam_a import check as exam_a
    from check_v12_exam_b import check as exam_b
    from check_v12_project import check as project
    from check_v12_support_peer import check as support_peer
    from check_v12_exam_a_peer import check as exam_a_peer
    from check_v12_exam_b_peer import check as exam_b_peer
    from check_v12_project_peer import check as project_peer

    parts = [(ROOT / 'content/assessments/parts' / name).read_text().strip()
             for name in PARTS]
    assembled = (ROOT / 'content/assessments/v12.html').read_text()
    if assembled != '\n\n'.join(parts) + '\n':
        raise ValueError('V12 assessment is not the exact five-part assembly')
    parsed = Assembly()
    parsed.feed(assembled)
    parsed.close()
    if parsed.stack:
        raise ValueError('V12 assessment has unclosed HTML')
    for anchor in ('diagnostic', 'exam-rules', 'form-a', 'solutions-a',
                   'form-b', 'solutions-b', 'project', 'oral-transfer',
                   'retention', 'remediation', 'notation-index',
                   'concept-index', 'volume-synthesis', 'assessment-source-scope'):
        if anchor not in parsed.ids:
            raise ValueError('Missing V12 assessment anchor: ' + anchor)
    results = {name: routine() for name, routine in (
        ('support_author', support), ('exam_a_author', exam_a),
        ('exam_b_author', exam_b), ('project_author', project),
        ('support_peer', support_peer), ('exam_a_peer', exam_a_peer),
        ('exam_b_peer', exam_b_peer), ('project_peer', project_peer))}
    result = {'status': 'passed', 'assembly_parts': list(PARTS),
              'unique_ids': len(parsed.ids),
              'component_checks': results,
              'limits': 'Internal editorial and numerical validation; no rendered UI or external human assessment claim.'}
    json.dumps(result, allow_nan=False)
    return result


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, allow_nan=False))
