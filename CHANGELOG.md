# Changelog

## 1.0.0 — 2026-11-18

- Provide a CLI for fixed-machine, nonpreemptive job-shop repair under a hard
  change cap K and for enumerating the trade-off frontier between changed
  operation start times R and completion time M.
- Include 20 synthetic outage events and 153 recorded frontier points. All
  saved schedules and their reported R/M values pass solver-free integer
  feasibility checks. The primary CP-SAT model reports complete frontiers
  for the 20 events.
- Record additional HiGHS MILP optimality checks for 24 points: all four
  ft06 frontiers (10 points), including their gaps and infeasible range, and
  14 selected ft10/abz5 points. Complete independent frontier reproduction
  covers ft06 only; the other 129 points have no additional HiGHS optimality
  check. HiGHS judgments use floating point MILP, not exact proof certificates.
- Preserve benchmark provenance and licenses. The event set was reused
  during development. No new scheduling algorithm, speed superiority, or
  performance on real equipment or real logs is claimed.
