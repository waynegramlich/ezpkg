# 14 The bootstrap fetches the newest `pip` regardless of Python

(CLOSED 2026-10-01)  Case 13 takes whatever wheel the JSON API lists for the
current `pip` release.  `pip` 26.2.1 requires Python 3.10, so today that is
harmless, but when `pip` drops 3.11 every pasted copy of the bootstrap running
on 3.11 will fetch a `pip` it cannot run.  That is a defect in code pasted into
somebody else's program, where nobody is around to fix it, which is an argument
for priority 0.  A possible solution is to read `/pypi/pip/json` for every
release and pick the newest whose `requires_python` admits the running
interpreter, at the cost of some pasted lines.

Various thoughts:
* Wayne (2026-10-01): Needs more discussion.
* Claude (2026-10-01): Fixed by Step 6.15.7.  `nopip3` takes the newest
  upload whose `requires_python` floor this Python meets, so a Python
  that `pip` drops keeps the last `pip` that supported it.
