"""Integrate the complete, separately reviewed Volume 14 assessment package."""
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ('v14-support-opening.html', 'v14-exam-a.html', 'v14-exam-b.html',
         'v14-project.html', 'v14-support-closing.html')


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
                raise ValueError('Duplicate V14 assessment ID: ' + attrs['id'])
            self.ids.add(attrs['id'])
        if tag not in ('br', 'hr', 'img', 'meta', 'link', 'input', 'wbr'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError('Unbalanced V14 assessment HTML: ' + tag)


def check():
    from check_v14_support import check as support
    from check_v14_exam_a import check as exam_a
    from check_v14_exam_b import check as exam_b
    from check_v14_project import check as project
    from check_v14_support_peer import check as support_peer
    from check_v14_exam_a_peer import check as exam_a_peer
    from check_v14_exam_b_peer import check as exam_b_peer
    from check_v14_project_peer import check as project_peer

    parts = [(ROOT / 'content/assessments/parts' / name).read_text().strip()
             for name in PARTS]
    assembled = (ROOT / 'content/assessments/v14.html').read_text()
    if assembled != '\n\n'.join(parts) + '\n':
        raise ValueError('V14 assessment is not the exact five-part assembly')
    parsed = Assembly()
    parsed.feed(assembled)
    parsed.close()
    if parsed.stack:
        raise ValueError('V14 assessment has unclosed HTML')
    for anchor in ('diagnostic', 'exam-rules', 'form-a', 'solutions-a',
                   'form-b', 'solutions-b', 'project', 'oral-transfer',
                   'retention', 'remediation', 'notation-index',
                   'concept-index', 'volume-synthesis', 'assessment-source-scope'):
        if anchor not in parsed.ids:
            raise ValueError('Missing V14 assessment anchor: ' + anchor)
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
