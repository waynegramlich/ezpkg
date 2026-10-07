# Summary of `I.vpir` Vendor the packages into the repository

Rejected: Needs no network, but it bloats the repository and breaks on compiled
extensions -- the same `.so` problem as `I.nicav`.  Declined 2026-09-21, before
Experiment 1; Experiment 1 then confirmed the `.so` problem is real by
installing `tracer.cpython-312-x86_64-linux-gnu.so`.
