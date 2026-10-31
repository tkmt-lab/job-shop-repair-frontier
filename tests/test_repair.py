import copy
import itertools
import unittest
from unittest.mock import patch
from checker import check, input_errors
from enumeration import frontier
from repair import repair


def tiny(K=2):
    return {'jobs': [[{'id': 'a', 'machine': 0, 'duration': 1}],
                     [{'id': 'b', 'machine': 0, 'duration': 1}]],
            'x0': {'a': {'start': 0, 'machine': 0}, 'b': {'start': 1, 'machine': 0}},
            't': 0, 'breakdowns': [{'machine': 0, 'start': 0, 'end': 1}],
            'K': K, 'deadline_ms': 10000, 'event_id': 'tiny'}


class RepairTests(unittest.TestCase):
    def test_bounded_repair(self):
        req = tiny(1)
        result = repair(req)
        self.assertEqual(result['status'], 'OPTIMAL')
        self.assertTrue(result['check']['valid'])
        self.assertLessEqual(result['check']['R'], 1)

    def test_frontier_matches_exhaustive_integer_enumeration(self):
        for K in range(3):
            req = tiny(K)
            feasible = set()
            for a, b in itertools.product(range(5), repeat=2):
                v = check(req, {'a': {'start': a, 'machine': 0}, 'b': {'start': b, 'machine': 0}})
                if v['valid']:
                    feasible.add((v['R'], v['makespan']))
            expected = {p for p in feasible if not any(q != p and q[0] <= p[0] and q[1] <= p[1] for q in feasible)}
            result = frontier(req, 10)
            self.assertTrue(result['complete'])
            self.assertEqual({(p['R'], p['makespan']) for p in result['cp_sat_frontier_points']}, expected)
            self.assertTrue(all(p['R'] <= K for p in result['cp_sat_frontier_points']))

    def test_rejects_outage_and_history_corruption(self):
        req = tiny()
        self.assertFalse(check(req, req['x0'])['valid'])
        history = copy.deepcopy(req)
        history.update(t=1, breakdowns=[])
        shifted = copy.deepcopy(history['x0'])
        shifted['a']['start'] = 2
        self.assertIn('history_moved:a', check(history, shifted)['errors'])
        self.assertTrue(input_errors({**req, 't': True}))

    def test_in_progress_breakdown_is_rejected(self):
        req = tiny()
        req['jobs'][0][0]['duration'] = 2
        req['x0']['b']['start'] = 2
        req.update(t=1, breakdowns=[{'machine': 0, 'start': 1, 'end': 3}])
        self.assertIn('unsupported_in_progress_breakdown', input_errors(req))

    def test_unproved_incumbent_is_not_frontier(self):
        req = tiny()
        candidate = {'status': 'FEASIBLE', 'schedule': {'a': {'start': 2, 'machine': 0}, 'b': {'start': 1, 'machine': 0}},
                     'check': {'R': 1, 'makespan': 3}}
        with patch('enumeration.query', return_value=candidate):
            result = frontier(req, 10)
        self.assertFalse(result['complete'])
        self.assertEqual(result['cp_sat_frontier_points'], [])
        self.assertEqual(len(result['unconfirmed_candidates_not_frontier']), 1)
        timed_out = frontier(req, 0)
        self.assertFalse(timed_out['complete'])
        self.assertEqual(timed_out['trials'], [])


if __name__ == '__main__':
    unittest.main()
