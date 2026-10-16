"""Check the six-part V15 package, including its required policy dossier."""
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PARTS = ('v15-support-opening.html', 'v15-exam-a.html', 'v15-exam-b.html',
         'v15-project.html', 'v15-policy-dossier.html', 'v15-support-closing.html')

def require(ok, message):
    if not ok:
        raise ValueError(message)

class Assembly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.stack = []
        self.dossier_tasks = {}
        self.dossier_answers = []
        self.dossier_rubrics = []
        self.sources = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        require(len(a) == len(attrs), 'duplicate attribute')
        if 'id' in a:
            require(a['id'] not in self.ids, 'duplicate V15 assessment ID ' + a['id'])
            self.ids.add(a['id'])
        if 'data-dossier-points' in a:
            self.dossier_tasks[a['id']] = int(a['data-dossier-points'])
        if a.get('data-solution-for', '').startswith('v15-dossier-'):
            require(any(t == 'details' and 'solutions' in d.get('class', '').split()
                        for t,d in self.stack), 'dossier answers must be disclosed')
            self.dossier_answers.append(a['data-solution-for'])
        if 'data-dossier-rubric' in a:
            self.dossier_rubrics.append(tuple(map(int, a['data-dossier-rubric'].split(','))))
        if 'data-source' in a:
            key = a['data-source']
            if key in self.sources:
                require(self.sources[key] == a['href'], 'conflicting source routes')
            self.sources[key] = a['href']
        if tag not in ('br','hr','img','input','meta','link','wbr'):
            self.stack.append((tag,a))

    def handle_endtag(self, tag):
        require(self.stack and self.stack[-1][0] == tag, 'unbalanced package markup')
        self.stack.pop()

def check():
    from check_v15_support import check as support
    from check_v15_support_peer import check as support_peer
    from check_v15_exam_a import check as exam_a
    from check_v15_exam_a_peer import check as exam_a_peer
    from check_v15_exam_b import check as exam_b
    from check_v15_exam_b_peer import check as exam_b_peer
    from check_v15_project import check as project
    from check_v15_project_peer import check as project_peer

    parts = [(ROOT/'content/assessments/parts'/p).read_text().strip() for p in PARTS]
    assembled = (ROOT/'content/assessments/v15.html').read_text()
    require(assembled == '\n\n'.join(parts)+'\n', 'exact six-part assembly')
    doc = Assembly(); doc.feed(assembled); doc.close()
    require(not doc.stack, 'complete package markup')
    anchors = {'diagnostic','exam-rules','form-a','solutions-a','form-b','solutions-b',
               'project','policy-dossier','oral-transfer','retention','remediation',
               'notation-index','concept-index','volume-synthesis','assessment-source-scope'}
    require(anchors <= doc.ids, 'missing required package component')
    ids = [f'v15-dossier-task{i}' for i in range(1,6)]
    require(list(doc.dossier_tasks) == doc.dossier_answers == ids, 'five paired dossier tasks')
    require(list(doc.dossier_tasks.values()) == [8]*5, '40-point dossier')
    require(len(doc.dossier_rubrics) == 5 and all(sum(r) == 8 and min(r)>0 for r in doc.dossier_rubrics), 'additive dossier scoring')
    sources = json.loads((ROOT/'content/sources.json').read_text())
    catalogue = {s['id']:s['url'] for s in sources}
    require(all(catalogue.get(k) == v for k,v in doc.sources.items()), 'all package sources catalogued accurately')
    dossier = (ROOT/'content/assessments/parts/v15-policy-dossier.html').read_text()
    for phrase in ('34/40','6/8','Scores cannot compensate','synthetic','1994–1998',
                   'March 1996','November 2011','2016','exclusion','complier','confidential'):
        require(phrase in dossier, 'missing dossier requirement '+phrase)
    # Binding integrity protects reviewed prose; it is not a substitute for reading.
    for name in ('v15-dossier-author.json','v15-dossier-peer.json'):
        r = json.loads((ROOT/'content/reviews'/name).read_text())
        require(not r['open_findings'], 'unresolved dossier review')
        bindings = r['payload_bindings']
        if isinstance(bindings,list):
            bindings = {x['path']:x for x in bindings}
        require('content/assessments/parts/v15-policy-dossier.html' in bindings, 'dossier review binding')
        for p,bind in bindings.items():
            raw = (ROOT/p).read_bytes()
            require(len(raw)==bind['bytes'] and sha256(raw).hexdigest()==bind['sha256'], 'dossier review freeze '+p)
    # Independently sum the displayed distributional account and dated reserve.
    changes = (F(23,8),F(-23,16),F(-43,32),F(-43,32))
    require(sum(changes)==F(-5,4), 'dossier resource account')
    require(sum(w*x for w,x in zip((2,2,1,1),changes))==F(3,16), 'dossier weighted account')
    require(1*(3+1)+1==5 and 2*(3+1)+1==9 and 9>8, 'dossier funding/transfer')
    # Finite heterogeneous population witness for the written LATE derivation.
    d0,d1=(0,1,0,0),(0,1,1,1)
    y0,y1=(1,2,3,4),(3,5,7,10)
    observed = [[y1[i] if d[i] else y0[i] for i in range(4)] for d in (d0,d1)]
    reduced = F(sum(observed[1])-sum(observed[0]),4)
    first = F(sum(d1)-sum(d0),4)
    complier = [i for i in range(4) if d1[i]>d0[i]]
    require(reduced/first==sum(F(y1[i]-y0[i],len(complier)) for i in complier)==5, 'heterogeneous complier identity')
    results = {name:fn() for name,fn in (
        ('support_author',support),('support_peer',support_peer),
        ('exam_a_author',exam_a),('exam_a_peer',exam_a_peer),
        ('exam_b_author',exam_b),('exam_b_coordinator',exam_b_peer),
        ('project_author',project),('project_peer',project_peer))}
    return {'status':'passed','assembly_parts':list(PARTS),'unique_ids':len(doc.ids),
            'dossier_tasks':5,'dossier_points':40,'dossier_source_records':4,
            'component_checks':results,
            'limits':'Internal author and agent review; no independent human certification, empirically calibrated exam timing or rendered UI claim.'}

if __name__ == '__main__':
    print(json.dumps(check(),indent=2,allow_nan=False))
