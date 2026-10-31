# Job-shop repair frontier

See how many operation start times must change to recover a given amount of
delay after a machine outage. The CLI returns a schedule under a hard change
cap **K**, or the trade-off frontier between the number of changed operations
**R** and the completion time **M**. Each returned schedule passes an integer
feasibility checker that uses no solver.

For the included `ft06-q25-d1` outage, changing 3 start times gives completion
time 62; changing 6 gives 58. The original plan finishes at 55. Times are
integer benchmark units.

## Try the recorded example

Python 3.12 or later, on Linux or macOS. Reading saved results and checking
the data require only the Python standard library:

```sh
python -B frontier.py --saved-result data/frontiers/ft06-q25-d1.json
python -S -B verify_data.py
```

The table is:

```text
R | M
--: | --:
3 | 62
6 | 58
Complete under the primary CP-SAT model: true
```

For this event, K=0..2 is infeasible, K=3..5 has minimum M=62, and K=6..28
has minimum M=58. HiGHS MILP also reproduced this entire frontier and the
infeasible range.

## Compute a repair or frontier

OR-Tools is the only direct package dependency; pip also installs its declared
dependencies. JobShopLib, PyJobShop and HiGHS are not needed to use this CLI.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -B repair.py data/events/ft06-q25-d1.json > repair-result.json
python -B checker.py data/events/ft06-q25-d1.json repair-result.json
python -B frontier.py data/events/ft06-q25-d1.json --budget-seconds 30 --json
python -B -m unittest discover -s tests -v
```

Edit `K` in a copy of an event input to select the maximum number of changed
start times. `repair.py` minimizes M under that cap. `frontier.py` enumerates
the nondominated R/M choices within `0..K`, stopping after the specified total
budget (default 60 seconds, maximum 1,800). Each optimization call uses one
CP-SAT worker for at most 60 seconds. For a single repair, `deadline_ms` sets
the total query budget, up to 60,000 ms. These are process watchdog budgets,
not guarantees for real-time control.

Successful repair results contain `status`, `schedule` and `check`; the checker
reports `R`, `makespan` and `changed_ids`. `INFEASIBLE` means the complete
primary model found no schedule under K. `FEASIBLE` is an integer-checked
incumbent with unproved optimality. `UNKNOWN` and `TIMEOUT` do not establish
infeasibility and return no schedule. A rejected solver output stops frontier
enumeration.

Live frontiers include points only when both optimization stages are
`OPTIMAL`. A time limit or unproved result leaves `complete=false`, with
`unresolved_K_range` and any `unconfirmed_candidates_not_frontier` explicitly
reported. Exit codes are 0 for a completed query/enumeration, 2 for invalid
input or an error, and 3 for an incomplete result; the checker returns 1 for
an invalid schedule. Inspect the JSON status even when the exit code is 0.

## Input contract

An input JSON contains:

| Field | Meaning |
| --- | --- |
| `jobs` | Ordered operations per job, each with a unique string `id`, fixed integer `machine`, and positive integer `duration` |
| `x0` | Original feasible schedule, mapping each operation ID to integer `start` and its fixed `machine` |
| `t` | Current nonnegative integer time |
| `breakdowns` | Known outages: `machine`, `start`, `end`, with half-open intervals `[start,end)` and `start <= t` |
| `K` | Maximum number of unstarted operations whose start time may change |
| `deadline_ms` | Single-query time budget, integer 0..60,000 |

Operations with original start `< t` keep their original start and machine,
including operations still running at t. All other operations start at or after
t. Job precedence, machine exclusivity and outage avoidance must hold.
An outage overlapping an operation already started is rejected, as is an outage
that contradicts completed history. Processing is nonpreemptive, machines are
fixed, and outage end times are known. The implementation accepts at most
200 operations and 200 outage intervals; see `integer_core.py` for numeric
bounds. An input example is [ft06-q25-d1.json](data/events/ft06-q25-d1.json).

## Data and evidence

The data contain three standard instances, their original schedules X0,
20 synthetic outage events and 153 recorded frontier points. Each point in
`data/frontiers/` contains its schedule, R, M, CP-SAT status and separate
verification labels. Original inputs, X0 and benchmark extracts preserve their
bytes; `PROVENANCE.json` records source commit and hashes, and `MANIFEST.json`
hashes the exported files.

| Evidence | Scope |
| --- | --- |
| Direct integer feasibility and reported R/M | All 153 schedules; repeated by `verify_data.py` using two checker implementations |
| Primary OR-Tools CP-SAT optimality and complete enumeration | All 20 events / 153 points, as recorded solver judgments |
| Separate time-indexed model, same CP-SAT solver | ft06: 4 events / 10 points, including the gaps and infeasible tail |
| Separate formulation with HiGHS MILP | ft06: complete 4 frontiers / 10 points; ft10 and abz5: 14 selected points |
| Optimality supported only by the primary CP-SAT model | Remaining 129 points |

The additional 14 MILP points belong to `ft10-q75-d1`, `ft10-q90-d1`,
`abz5-q75-d1` and `abz5-q90-d1`. Each has two infeasibility checks ruling out
a strict improvement in M or R, plus a fixed-schedule feasibility check. This
does not independently enumerate every point between them. HiGHS used floating
point MILP with zero requested MIP gaps; its judgments are not exact rational
or formally checkable infeasibility certificates. `evidence/highs/` preserves
the query records and selected-point certificates. The primary query records
are in `evidence/primary/`.

`verify_data.py` checks stored schedules, metrics, hashes and evidence labels;
it does not rerun historical optimizations or prove their optimality. The
separate-model checks were computational checks by AI agents, not human peer
review. Lean level: **L0**, because the artifact is software and finite schedule
data with executable integer checks, without a Lean formalization.

The event set was reused during development and is not an unseen evaluation
set. No new scheduling algorithm, speed advantage, or performance on real
equipment or real logs is claimed. Interrupting running operations, machine
reassignment and uncertain recovery times are outside the input contract.

## Method and reviewed tools

The interval model uses OR-Tools CP-SAT. To enumerate the frontier, first
minimize M under `R <= K`; then minimize R under that optimal M. Record the
point only if both calls prove optimality. Continue with `K = R - 1`. This
skips no nondominated point because the preceding optimum covers the whole
interval from its R to the previous K. A finite horizon is the maximum of t,
all original completion times and outage ends, plus the sum of durations.

As of **2026-10-31**, no free repair tool returning an R/M frontier with a hard
K cap was found within the reviewed tools and APIs below. This is a bounded
search observation, not a claim of priority or an exhaustive absence result.

| Reviewed tool | Version and inspection scope |
| --- | --- |
| [OR-Tools](https://pypi.org/project/ortools/9.15.6755/) | 9.15.6755; CP-SAT model and documented solver facilities; used to build the repair constraints |
| [JobShopLib](https://pypi.org/project/job-shop-lib/1.7.2/) | 1.7.2; benchmark loader and distribution data |
| [PyJobShop](https://pypi.org/project/pyjobshop/0.0.9/) | 0.0.9; Model/ProblemData APIs and ordinary re-solve with frozen history and outage constraints; that comparison did not impose hard K |

## Sources, credit and licenses

- J. F. Muth and G. L. Thompson, *Industrial Scheduling*, Prentice-Hall,
  1963: ft06 and ft10.
- J. Adams, E. Balas and D. Zawack, “The Shifting Bottleneck Procedure for
  Job Shop Scheduling,” *Management Science* 34(3), 391–401, 1988: abz5.
  [DOI](https://doi.org/10.1287/mnsc.34.3.391).
- Pablo Ariño's JobShopLib 1.7.2 provides the benchmark matrices used here.
  [Distribution URL and SHA-256](data/benchmarks/PROVENANCE.json), original
  instance metadata and [MIT notice](LICENSES/JobShopLib-MIT.txt) are included.
- OR-Tools supplies CP-SAT; PyJobShop supplied the ordinary re-solve comparison
  in development; HiGHS supplied the additional MILP checks.

I am grateful to the benchmark authors and the developers of these tools for
making this work possible. Their mention does not imply review or endorsement.

Code and CI are Apache-2.0. Original data and prose are CC BY 4.0. The
JobShopLib-derived benchmark matrices and metadata retain their MIT notice;
the CC license does not replace that license. See [LICENSE](LICENSE),
[CITATION.cff](CITATION.cff) and [claims.json](claims.json).
