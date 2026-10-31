"""CP-SAT interval model for fixed-machine job-shop repair."""
import json
import resource
import sys
import time


def solve(request, objective, makespan_cap, absolute_deadline):
    use_hint = True
    from ortools.sat.python import cp_model

    ops = [op for job in request["jobs"] for op in job]
    base = max([request["t"]] + [request["x0"][op["id"]]["start"] + op["duration"] for op in ops] + [event["end"] for event in request["breakdowns"]])
    horizon = base + sum(op["duration"] for op in ops)
    model = cp_model.CpModel()
    starts, ends, intervals, changes = {}, {}, {}, []
    for op in ops:
        oid, duration, machine = op["id"], op["duration"], op["machine"]
        old = request["x0"][oid]["start"]
        fixed = old < request["t"]
        start = model.new_int_var(old if fixed else request["t"], old if fixed else horizon - duration, "s_" + oid)
        end = model.new_int_var(0, horizon, "e_" + oid)
        interval = model.new_interval_var(start, duration, end, "i_" + oid)
        starts[oid], ends[oid] = start, end
        intervals.setdefault(machine, []).append(interval)
        if not fixed:
            change = model.new_bool_var("c_" + oid)
            model.add(start != old).only_enforce_if(change)
            model.add(start == old).only_enforce_if(change.Not())
            changes.append(change)
        if use_hint:
            model.add_hint(start, old)
    for job in request["jobs"]:
        for a, b in zip(job, job[1:]):
            model.add(ends[a["id"]] <= starts[b["id"]])
    # Merge overlapping/touching outage intervals before adding resource blocks.
    for machine, machine_intervals in intervals.items():
        outages = sorted((b["start"], b["end"]) for b in request["breakdowns"] if b["machine"] == machine)
        merged = []
        for a, b in outages:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for i, (a, b) in enumerate(merged):
            machine_intervals.append(model.new_fixed_size_interval_var(a, b - a, f"outage_{machine}_{i}"))
        model.add_no_overlap(machine_intervals)
    model.add(sum(changes) <= request["K"])
    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, list(ends.values()))
    if makespan_cap is not None:
        model.add(makespan <= makespan_cap)
    model.minimize(makespan if objective == "makespan" else sum(changes))
    invalid = model.validate()
    if invalid:
        return {"status": "UNKNOWN", "reason": "model_invalid", "detail": invalid}
    remaining = absolute_deadline - time.monotonic() - 0.5
    if remaining <= 0:
        return {"status": "TIMEOUT", "reason": "before_solve"}
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = min(60.0, remaining)
    status = solver.solve(model)
    name = solver.status_name(status)
    result = {"status": name if name in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"} else "UNKNOWN", "solver_status": name, "horizon": horizon, "hint": use_hint, "solver_wall_seconds": solver.wall_time, "branches": solver.num_branches, "conflicts": solver.num_conflicts, "response_stats": solver.response_stats()}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["schedule"] = {op["id"]: {"start": solver.value(starts[op["id"]]), "machine": op["machine"]} for op in ops}
        result["objective"] = solver.objective_value
        result["model_R"] = solver.value(sum(changes))
        result["model_makespan"] = solver.value(makespan)
        result["best_bound"] = solver.best_objective_bound
    return result
