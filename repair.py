"""Minimize completion time subject to the input's hard change cap K."""
import argparse
import json
from pathlib import Path
import sys
from checker import input_errors


def repair(request):
    errors = input_errors(request)
    if errors:
        raise ValueError(errors)
    from query import query
    return query(request, seconds=request['deadline_ms'] / 1000)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    args = parser.parse_args()
    try:
        result = repair(json.loads(Path(args.input).read_text()))
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result.get('schedule') or result['status'] == 'INFEASIBLE' else 3)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        raise SystemExit(2)
