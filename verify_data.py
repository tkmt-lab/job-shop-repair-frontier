"""Verify all exported schedules, metrics, evidence labels and file hashes offline."""
import hashlib
import importlib.util
import json
from pathlib import Path
from checker import check, input_errors

ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads((ROOT / path).read_text())


def verify():
    manifest = load('MANIFEST.json')
    for name, expected in manifest['files'].items():
        data = (ROOT / name).read_bytes()
        assert len(data) == expected['bytes'], name
        assert hashlib.sha256(data).hexdigest() == expected['sha256'], name
    spec = importlib.util.spec_from_file_location('audit_integer', ROOT / 'evidence/verify_integer.py')
    independent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(independent)
    certs = {(p['event'], p['R'], p['M']) for p in load('evidence/highs/POINT-CERTIFICATES.json')}
    historical = {(p['event'], p['R'], p['M']): p['verdict'] for p in load('evidence/highs/FEASIBILITY.json')}
    total = highs = time_indexed = 0
    inputs = sorted((ROOT / 'data/events').glob('*.json'))
    assert len(inputs) == 20
    for path in inputs:
        request = json.loads(path.read_text())
        assert not input_errors(request), path.name
        assert request['x0'] == load(f"data/x0/{request['instance']}.json")
        benchmark = load(f"data/benchmarks/{request['instance']}.json")
        assert [[o['duration'] for o in job] for job in request['jobs']] == benchmark['duration_matrix']
        assert [[o['machine'] for o in job] for job in request['jobs']] == benchmark['machines_matrix']
        eid = request['event_id']
        frontier = load(f'data/frontiers/{eid}.json')
        primary = load(f'evidence/primary/{eid}.json')
        assert frontier['complete'] and frontier['unresolved_K_range'] is None
        assert len(frontier['points']) == len(primary['cp_sat_frontier_points'])
        previous_r, previous_m = -1, float('inf')
        for point, origin in zip(frontier['points'], primary['cp_sat_frontier_points']):
            verdict = check({**request, 'K': point['R']}, point['schedule'])
            assert verdict['valid'], (eid, verdict)
            assert (verdict['R'], verdict['makespan']) == (point['R'], point['M'])
            second = independent.check(request, point['schedule'])
            assert not second['errors'] and (second['R'], second['M']) == (point['R'], point['M'])
            assert point['R'] > previous_r and point['M'] < previous_m
            previous_r, previous_m = point['R'], point['M']
            assert point['schedule'] == origin['schedule']
            assert (point['R'], point['M'], point['status']) == (origin['R'], origin['makespan'], 'CP_SAT_OPTIMAL')
            assert historical[(eid, point['R'], point['M'])] == 'PASS'
            v = point['verification']
            is_ft06 = eid.startswith('ft06-')
            is_highs = is_ft06 or (eid, point['R'], point['M']) in certs
            assert v == dict(integer_feasibility=True, primary_cp_sat_optimal=True,
                time_indexed_cp_sat=is_ft06, highs_milp_optimality=is_highs, highs_complete_frontier=is_ft06)
            for idx in point['query_indices']:
                assert primary['trials'][idx]['result']['status'] == 'OPTIMAL'
            total += 1
            highs += is_highs
            time_indexed += is_ft06
    assert (total, highs, time_indexed) == (153, 24, 10)
    return dict(events=len(inputs), feasible_points=total, highs_optimality_points=highs,
                time_indexed_points=time_indexed, primary_only_optimality_points=total-highs,
                manifest_files=len(manifest['files']), status='PASS')


if __name__ == '__main__':
    print(json.dumps(verify(), sort_keys=True))
