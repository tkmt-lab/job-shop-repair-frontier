"""Return the R/M frontier under the input change cap K, or render saved data."""
import argparse
import json
import math
from pathlib import Path
import sys


def render(result):
    points = result.get('points', result.get('cp_sat_frontier_points', []))
    lines = ['R | M', '--: | --:']
    lines.extend(f"{p['R']} | {p.get('M', p.get('makespan'))}" for p in points)
    lines.append('Complete under the primary CP-SAT model: ' + str(result['complete']).lower())
    if not result['complete']:
        lines.append('Unresolved K range: ' + str(result['unresolved_K_range']))
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?')
    parser.add_argument('--saved-result', help='Render recorded data without importing OR-Tools')
    parser.add_argument('--budget-seconds', type=float, default=60)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        if not math.isfinite(args.budget_seconds) or not 0 <= args.budget_seconds <= 1800:
            raise ValueError('budget must be finite and in 0..1800 seconds')
        if args.saved_result:
            result = json.loads(Path(args.saved_result).read_text())
        else:
            if not args.input:
                parser.error('input or --saved-result is required')
            from enumeration import frontier
            result = frontier(json.loads(Path(args.input).read_text()), args.budget_seconds)
        print(json.dumps(result, indent=2) if args.json else render(result))
        return 0 if result['complete'] else 3
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
