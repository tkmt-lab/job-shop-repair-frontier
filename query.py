"""One bounded optimization query guarded by the integer feasibility checker."""
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from checker import check as integer_check, input_errors


def checked(request, schedule):
    return integer_check({**request, 'deadline_ms': 10000}, schedule)


def query(request, formulation='primary', objective='makespan', makespan_cap=None, seconds=60):
    started = time.monotonic()
    deadline = started + min(60, max(0, seconds))
    errors = input_errors({**request, 'deadline_ms': 10000})
    if errors:
        raise ValueError(errors)
    if formulation != 'primary' or objective not in ('makespan','changes'):
        raise ValueError('invalid query')
    if makespan_cap is not None and (type(makespan_cap) is not int or makespan_cap < 0):
        raise ValueError('invalid makespan cap')
    payload = json.dumps({'request': request, 'formulation': formulation, 'objective': objective, 'makespan_cap': makespan_cap, 'deadline': deadline})
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    p = subprocess.Popen([sys.executable, '-B', str(Path(__file__).with_name('query_worker.py'))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    raw, peak = None, 0
    try:
        while time.monotonic() < deadline:
            try:
                out, err = p.communicate(input=payload, timeout=min(0.2, max(0.001, deadline-time.monotonic())))
                raw = json.loads(out) if p.returncode == 0 else {'status': 'UNKNOWN', 'reason': 'worker_error', 'stderr': err[-2000:], 'returncode': p.returncode}
                break
            except subprocess.TimeoutExpired:
                payload = None
                try:
                    ps = subprocess.run(['/bin/ps','-o','rss=','-p',f'{p.pid},{os.getpid()}'],capture_output=True,text=True,timeout=min(0.1,max(0.001,deadline-time.monotonic())))
                    peak = max(peak, sum(map(int,ps.stdout.split()))*1024)
                    if peak > 4*1024**3:
                        raw = {'status':'UNKNOWN','reason':'memory_limit'}
                        break
                except subprocess.TimeoutExpired:
                    pass
    except (OSError, ValueError) as exc:
        raw = {'status':'UNKNOWN','reason':'protocol_error','detail':str(exc)}
    finally:
        if p.poll() is None:
            p.kill()
        p.communicate()
    raw = raw or {'status':'TIMEOUT','reason':'watchdog_deadline'}
    result = {'status':raw['status'], 'schedule':None, 'check':None, 'formulation':formulation, 'objective_kind':objective, 'K':request['K'], 'makespan_cap':makespan_cap, 'detail':{k:v for k,v in raw.items() if k!='schedule'}}
    if raw['status'] in ('FEASIBLE','OPTIMAL'):
        verdict = checked(request, raw.get('schedule'))
        consistent = verdict['valid'] and verdict['R'] == raw.get('model_R') and verdict['makespan'] == raw.get('model_makespan') and (makespan_cap is None or verdict['makespan'] <= makespan_cap)
        if not consistent:
            result.update(status='UNKNOWN', reason='checker_rejected', stop_required=True, check=verdict, rejected_candidate=raw.get('schedule'))
        else:
            result.update(schedule=raw['schedule'],check=verdict)
    if raw.get('worker_peak_rss_bytes',0) > 4*1024**3:
        result.update(status='UNKNOWN',schedule=None,check=None,reason='memory_limit')
    json.dumps(result)
    if time.monotonic() >= deadline:
        result.update(status='TIMEOUT',schedule=None,check=None,reason='end_to_end_deadline')
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    result.update(elapsed_seconds=time.monotonic()-started, sampled_combined_rss_bytes=peak, child_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime)
    return result
