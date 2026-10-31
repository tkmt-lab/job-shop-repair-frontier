# Working on this artifact

Preserve the fixed-machine, nonpreemptive input contract in README.md.
Do not label FEASIBLE incumbents as proved frontier points. Keep integer
feasibility, primary CP-SAT judgments, same-solver alternative formulation,
and separate HiGHS optimality checks distinct.

Recorded data and evidence are versioned. Do not silently regenerate or replace
them. Preserve source hashes, benchmark attribution and the JobShopLib MIT
notice, including for matrices embedded in event inputs.

Run `python -S -B verify_data.py` without dependencies, then install
requirements.txt and run `python -B -m unittest discover -s tests -v`.
After an intentional file change, review the diff and update MANIFEST.json.
Do not infer publication authorization from the existence of this directory.
