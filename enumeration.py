"""Enumerate a CP-SAT-certified frontier, with explicit incomplete ranges."""
import argparse
import json
from pathlib import Path
import time

from query import query
from checker import input_errors


def frontier(request, total_seconds=1800, recorder=None, guard=None):
    """Descending epsilon constraints; each point uses two optimization calls.

    `complete` concerns the primary CP model. It is not an independent proof.
    A FEASIBLE incumbent is never inserted into cp_sat_frontier_points.
    """
    errors = input_errors(request)
    if errors:
        raise ValueError(errors)
    started = time.monotonic()
    cap = sum(row['start'] >= request['t'] for row in request['x0'].values())
    full = cap
    cap = min(cap, request['K'])
    initial_cap = cap
    points, trials, candidates, ranges = [], [], [], []
    complete, reason = False, None

    def call(objective, k, ceiling=None):
        nonlocal reason
        remaining = total_seconds - (time.monotonic()-started)
        if remaining <= 0 or (guard is not None and not guard()):
            reason = 'event_or_global_budget'
            return {'status':'TIMEOUT', 'schedule':None, 'check':None}
        query_request = {**request, 'K':k}
        if recorder:
            recorder({'index':len(trials),'objective':objective,'K':k,'makespan_cap':ceiling,'state':'started'})
        result = query(query_request, 'primary', objective, ceiling, min(60,remaining))
        trial = {'index':len(trials),'objective':objective,'K':k,'makespan_cap':ceiling,'state':'finished','result':result}
        if recorder:
            trial['artifact'] = recorder(trial)
        trials.append(trial)
        if result.get('stop_required'):
            raise RuntimeError('integer checker rejected a solver output')
        return result

    while cap >= 0:
        minimum = call('makespan',cap)
        if minimum['status'] == 'INFEASIBLE':
            complete, reason = True, 'no_feasible_point_below_previous'
            break
        if minimum['status'] != 'OPTIMAL':
            if minimum.get('schedule') is not None:
                candidates.append({'source':'makespan_query','status':minimum['status'],'R':minimum['check']['R'],'makespan':minimum['check']['makespan'],'schedule':minimum['schedule']})
            reason = reason or 'makespan_not_proved_optimal'
            break
        M = minimum['check']['makespan']
        least_changes = call('changes',cap,M)
        if least_changes['status'] != 'OPTIMAL':
            witness = least_changes if least_changes.get('schedule') else minimum
            candidates.append({'source':'change_minimization_unfinished','status':least_changes['status'],'R':witness['check']['R'],'makespan':witness['check']['makespan'],'schedule':witness['schedule']})
            reason = reason or 'change_count_not_proved_optimal'
            break
        R = least_changes['check']['R']
        if least_changes['check']['makespan'] != M:
            raise RuntimeError('two-stage lexicographic result contradicts first optimum')
        point = {'R':R,'makespan':M,'schedule':least_changes['schedule'],'status':'CP_SAT_OPTIMAL','verification':'primary_formulation_only','searched_K_cap':cap,'query_indices':[len(trials)-2,len(trials)-1]}
        points.append(point)
        ranges.append({'K_from':R,'K_to':cap,'minimum_makespan':M,'evidence':'primary_CP_SAT_OPTIMAL'})
        cap = R-1
    if cap < 0:
        complete, reason = True, 'nonnegative_change_count_exhausted'
    points.sort(key=lambda p:p['R'])
    return {'event_id':request.get('event_id'),'complete':complete,'completeness_scope':'primary CP-SAT formulation','reason':reason,'full_K':full,'requested_K_cap':initial_cap,'cp_sat_frontier_points':points,'confirmed_optimal_K_ranges':ranges,'confirmed_infeasible_K_range':[0,cap] if complete and cap>=0 else None,'unresolved_K_range':None if complete else [0,cap],'unconfirmed_candidates_not_frontier':candidates,'trials':trials,'elapsed_seconds':time.monotonic()-started}

