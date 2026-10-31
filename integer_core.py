"""Integer-only, solver-independent validation for the R049 prototype."""
import json
import sys


def overlap(a, b, c, d):
    return a < d and c < b  # half-open intervals


def input_errors(request):
    """Validate the finite fixed-machine contract, including the original plan."""
    errors = []
    if not isinstance(request, dict):
        return ["input_not_object"]
    jobs = request.get("jobs")
    if not isinstance(jobs, list) or not jobs or len(jobs) > 200:
        return ["invalid_jobs"]
    ids = set()
    count = 0
    for job in jobs:
        if not isinstance(job, list) or not job:
            return ["invalid_job"]
        for op in job:
            count += 1
            if not isinstance(op, dict):
                return ["invalid_operation"]
            oid = op.get("id")
            if not isinstance(oid, str) or not oid or len(oid) > 100 or oid in ids:
                return ["invalid_or_duplicate_id"]
            ids.add(oid)
            if type(op.get("machine")) is not int or not 0 <= op["machine"] < 200:
                return ["invalid_machine"]
            if type(op.get("duration")) is not int or not 1 <= op["duration"] <= 10**9:
                return ["invalid_duration"]
    if count > 200:
        return ["too_many_operations"]
    for key in ("t", "K"):
        if type(request.get(key)) is not int or request[key] < 0:
            return ["invalid_" + key]
    if request["t"] > 10**9 or request["K"] > count:
        return ["t_or_K_out_of_range"]
    if type(request.get("deadline_ms")) is not int or not 0 <= request["deadline_ms"] <= 10000:
        return ["invalid_deadline_ms"]
    original = request.get("x0")
    errors.extend(schedule_structure_errors(jobs, original))
    if errors:
        return ["x0:" + e for e in errors]
    breaks = request.get("breakdowns")
    if not isinstance(breaks, list) or len(breaks) > 200:
        return ["invalid_breakdowns"]
    machines = {op["machine"] for job in jobs for op in job}
    for event in breaks:
        if not isinstance(event, dict) or any(type(event.get(k)) is not int for k in ("machine", "start", "end")):
            return ["invalid_breakdown"]
        if event["machine"] not in machines or not 0 <= event["start"] < event["end"] <= 10**9:
            return ["invalid_breakdown_interval"]
        if event["start"] > request["t"]:
            return ["unobserved_future_breakdown"]
        for job in jobs:
            for op in job:
                start = original[op["id"]]["start"]
                end = start + op["duration"]
                if op["machine"] == event["machine"] and start < request["t"] and overlap(start, end, event["start"], event["end"]):
                    errors.append("unsupported_in_progress_breakdown" if end > request["t"] else "breakdown_conflicts_with_history")
    return sorted(set(errors))


def schedule_structure_errors(jobs, schedule):
    """Direct pairwise comparisons, without solver intervals or model helpers."""
    ops = [op for job in jobs for op in job]
    if not isinstance(schedule, dict) or set(schedule) != {op["id"] for op in ops}:
        return ["schedule_ids_mismatch"]
    errors = []
    for op in ops:
        row = schedule[op["id"]]
        if not isinstance(row, dict) or type(row.get("start")) is not int or not 0 <= row["start"] <= 10**12:
            return ["invalid_start"]
        if type(row.get("machine")) is not int or row["machine"] != op["machine"]:
            errors.append("machine_changed:" + op["id"])
    if errors:
        return errors
    for job in jobs:
        for before, after in zip(job, job[1:]):
            if schedule[before["id"]]["start"] + before["duration"] > schedule[after["id"]]["start"]:
                errors.append("precedence:" + before["id"] + ":" + after["id"])
    for i, a in enumerate(ops):
        for b in ops[i + 1:]:
            if a["machine"] == b["machine"]:
                sa, sb = schedule[a["id"]]["start"], schedule[b["id"]]["start"]
                if overlap(sa, sa + a["duration"], sb, sb + b["duration"]):
                    errors.append("machine_overlap:" + a["id"] + ":" + b["id"])
    return errors


def check(request, schedule, claimed_changed=None):
    errors = input_errors(request)
    if errors:
        return {"valid": False, "errors": errors}
    errors = schedule_structure_errors(request["jobs"], schedule)
    if errors:
        return {"valid": False, "errors": errors}
    changed = []
    makespan = 0
    for job in request["jobs"]:
        for op in job:
            oid = op["id"]
            start = schedule[oid]["start"]
            old = request["x0"][oid]["start"]
            end = start + op["duration"]
            makespan = max(makespan, end)
            if old < request["t"]:
                if start != old:
                    errors.append("history_moved:" + oid)
            else:
                if start < request["t"]:
                    errors.append("starts_in_past:" + oid)
                if start != old:
                    changed.append(oid)
            for event in request["breakdowns"]:
                if op["machine"] == event["machine"] and overlap(start, end, event["start"], event["end"]):
                    errors.append("breakdown_overlap:" + oid)
    changed.sort()
    if len(changed) > request["K"]:
        errors.append("change_budget_exceeded")
    if claimed_changed is not None and claimed_changed != changed:
        errors.append("changed_ids_mismatch")
    return {"valid": not errors, "errors": errors, "changed_ids": changed, "R": len(changed), "makespan": makespan}


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        req = json.load(f)
    with open(sys.argv[2]) as f:
        result = json.load(f)
    verdict = check(req, result.get("schedule"), result.get("changed_ids"))
    print(json.dumps(verdict, sort_keys=True))
    sys.exit(0 if verdict["valid"] else 1)
