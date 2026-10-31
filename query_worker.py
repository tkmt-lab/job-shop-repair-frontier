import json
import resource
import sys

if __name__ == '__main__':
    payload = json.load(sys.stdin)
    resource.setrlimit(resource.RLIMIT_CPU, (65, 66))
    if payload['formulation'] == 'primary':
        from primary_model import solve
    else:
        raise ValueError('unknown formulation')
    result = solve(payload['request'], payload['objective'], payload['makespan_cap'], payload['deadline'])
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result['worker_cpu_seconds'] = usage.ru_utime + usage.ru_stime
    result['worker_peak_rss_bytes'] = usage.ru_maxrss if sys.platform == 'darwin' else usage.ru_maxrss * 1024
    print(json.dumps(result))
