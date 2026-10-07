"""Independent exact arithmetic and fault/invariance audit for provenance chapter."""
from copy import deepcopy
from fractions import Fraction as F
from pathlib import Path
from itertools import permutations
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile

PROJECTS = Path(__file__).resolve().parents[1] / 'content' / 'projects'


def check():
    spec = importlib.util.spec_from_file_location('provenance_case', PROJECTS / 'v04-c01-provenance.py')
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    data = json.loads((PROJECTS / 'v04-c01-releases.json').read_text())
    manifest = json.loads((PROJECTS / 'v04-c01-manifest.json').read_text())
    raw = (PROJECTS / 'v04-c01-releases.json').read_bytes()
    assert len(raw) == manifest['inputs'][0]['bytes']
    assert hashlib.sha256(raw).hexdigest() == manifest['inputs'][0]['sha256']
    checks = []
    # Oracle uses an independent comprehension/max selection, then exact per-row arithmetic.
    def oracle(cutoff):
        rows = [max((r for r in data['rows'] if r['period'] == p and r['available_on'] <= cutoff),
                    key=lambda r:r['available_on']) for p in sorted(data['expected_periods'])]
        amounts = [F(r['nominal_spending']) / F(r['price_index'], 100) for r in rows]
        return rows, sum(amounts), (amounts[-1] - amounts[0]) / amounts[0]
    for cutoff,total,real,growth,nominal_growth in [
        ('2025-04-20',353000,F(320000),F(1,10),F(8,25)),
        ('2025-05-14',353000,F(320000),F(1,10),F(8,25)),
        ('2025-05-15',360000,F(2998000,9),F(3,17),F(6,17)),
        ('2025-05-20',360000,F(2998000,9),F(3,17),F(6,17)),
    ]:
        selected = lab.snapshot(data,cutoff)
        result = lab.summarize(selected)
        independent,real_total,real_growth = oracle(cutoff)
        assert selected == independent
        assert result['nominal_total_usd'] == total
        assert result['real_total_base_usd'] == real == real_total
        assert result['real_endpoint_growth'] == growth == real_growth
        assert result['nominal_endpoint_growth'] == nominal_growth
    assert F(353000,320000) == F(353,320)
    assert F(353000,320000)*100 == F(1765,16)
    assert F(353000*100,110) == F(3530000,11) != 320000
    assert sum(r['nominal_spending'] for r in data['rows']) == 713000
    assert F(713000-360000,360000) == F(353,360)
    checks.append('Two worked cases and numerical exercises: exact vintage totals, boundary inclusion, real/nominal growth, aggregate-deflator distinction and duplicate-vintage overstatement')

    base_a = lab.summarize(lab.snapshot(data,'2025-04-20'))
    base_m = lab.summarize(lab.snapshot(data,'2025-05-20'))
    for ordering in permutations(data['rows']):
        copy = deepcopy(data); copy['rows'] = list(ordering)
        assert lab.summarize(lab.snapshot(copy,'2025-04-20')) == base_a
        assert lab.summarize(lab.snapshot(copy,'2025-05-20')) == base_m
    changed = deepcopy(data)
    for row in changed['rows']: row['nominal_spending'] *= 1000
    for cutoff,base in [('2025-04-20',base_a),('2025-05-20',base_m)]:
        result = lab.summarize(lab.snapshot(changed,cutoff))
        assert result['nominal_total_usd'] == 1000*base['nominal_total_usd']
        assert result['real_total_base_usd'] == 1000*base['real_total_base_usd']
        assert result['real_endpoint_growth'] == base['real_endpoint_growth']
        assert result['nominal_endpoint_growth'] == base['nominal_endpoint_growth']
    checks.append('All 720 row permutations preserve both snapshots; thousandfold unit error changes levels but leaves endpoint growth unchanged')

    def rejects(fn):
        try: fn()
        except (ValueError,TypeError): return
        raise AssertionError('Invalid input was accepted')
    rejects(lambda:lab.snapshot(data,'2025-04-01'))
    for mutation in (
        lambda d:d['rows'].append(deepcopy(d['rows'][0])),
        lambda d:d['rows'][0].update(price_index=0),
        lambda d:d['rows'][0].update(price_index=-100),
        lambda d:d['rows'][0].update(nominal_spending=-1),
        lambda d:d['rows'][0].update(nominal_spending=True),
        lambda d:d['rows'][0].update(price_index='100'),
        lambda d:d['rows'][0].update(available_on='2025-02-30'),
        lambda d:d['rows'][0].update(available_on='20250215'),
        lambda d:d['rows'][2].update(available_on='2025-03-01'),
        lambda d:d['rows'][0].pop('period'),
        lambda d:d['units'].update(nominal_spending='USD thousands'),
        lambda d:d['expected_periods'].append('2025-04'),
    ):
        altered=deepcopy(data); mutation(altered)
        rejects(lambda:lab.snapshot(altered,'2025-05-20'))
    zero = deepcopy(data); zero['rows'][0]['nominal_spending']=0
    lab.validate(zero)
    rejects(lambda:lab.summarize(lab.snapshot(zero,'2025-04-20')))
    checks.append('Reject unavailable required month, premature complete-month release, duplicated vintage, missing fields, unsupported types/units, invalid dates and nonpositive index; distinguish valid zero level from undefined endpoint growth')

    with tempfile.TemporaryDirectory(prefix='mastery-v04-c01-') as tmp:
        folder=Path(tmp)
        for filename in ['v04-c01-provenance.py','v04-c01-releases.json']:
            shutil.copy2(PROJECTS / filename, folder / filename)
        script=folder / 'v04-c01-provenance.py'
        for flag in ([],['-O']):
            report=subprocess.run([sys.executable,*flag,str(script),'--cutoff','2025-05-20'],cwd=folder.parent,text=True,capture_output=True,check=True)
            result=json.loads(report.stdout)
            assert result['results']['real_total_base_usd']['exact']=='2998000/9'
            assert result['results']['real_endpoint_growth']['exact']=='3/17'
            assert result['input_sha256']==manifest['inputs'][0]['sha256']
            bad=subprocess.run([sys.executable,*flag,str(script),'--cutoff','2025-04-01'],cwd=folder.parent,text=True,capture_output=True)
            assert bad.returncode==2 and 'Unavailable required periods' in bad.stderr
        reordered=deepcopy(data);reordered['rows'].reverse()
        new=folder/'reformatted.json';new.write_text(json.dumps(reordered),encoding='utf-8')
        result=lab.run(new,'2025-05-20')
        assert result['input_sha256']!=manifest['inputs'][0]['sha256']
        assert result['results']==base_m
    checks.append('Clean-directory normal/optimized Python runs from a different working directory, frozen digest match, error exit behavior and semantic equality despite changed input bytes')
    return {'status':'passed','checks':checks,'limitations':['Synthetic finite case only; successful reproduction is not empirical or causal validation.','General provenance, permission and version-control reasoning reviewed in written record; visual UI checks remain pending.']}


if __name__ == '__main__':
    print(json.dumps(check(),indent=2))
