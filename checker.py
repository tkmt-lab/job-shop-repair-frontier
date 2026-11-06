"""Solver-free integer feasibility checker; accepts the legacy 60 s budget field."""
import argparse
import json
from integer_core import check as integer_check, input_errors as core_errors


def input_errors(request):
    if not isinstance(request, dict):
        return ['input_not_object']
    budget = request.get('deadline_ms')
    if type(budget) is not int or not 0 <= budget <= 60000:
        return ['invalid_deadline_ms']
    return core_errors({**request, 'deadline_ms': min(budget, 10000)})


def check(request, schedule, claimed_changed=None):
    errors = input_errors(request)
    if errors:
        return {'valid': False, 'errors': errors}
    return integer_check({**request, 'deadline_ms': min(request['deadline_ms'], 10000)},
                         schedule, claimed_changed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('result', help='JSON object containing schedule')
    args = parser.parse_args()
    try:
        with open(args.input) as f:
            request = json.load(f)
        with open(args.result) as f:
            result = json.load(f)
        verdict = check(request, result.get('schedule'), result.get('changed_ids'))
    except (ValueError, OSError, AttributeError) as exc:
        verdict = {'valid': False, 'errors': [str(exc)]}
    print(json.dumps(verdict, sort_keys=True))
    raise SystemExit(0 if verdict['valid'] else 1)
