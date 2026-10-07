# 7 The stashed `pip` is never updated

(CLOSED 2026-10-01)  `pip.whl` is fetched once and kept until `~/.alt_venv` is
deleted, so a machine that bootstrapped this year is still running this year's
`pip` in five years, with whatever it did not yet know about indexes, wheel
tags and security fixes.  A possible solution is for `AltVEnv` to refresh it
during `cull`, which already runs about once a day.

Various thoughts:
* Claude (2026-10-01): Fixed by Step 6.15.16, close to the solution
  proposed but weekly rather than daily, and adding newer wheels
  beside `pip.whl` rather than replacing it.
