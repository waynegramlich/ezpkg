# LLM Agent Context Log

## 2026-10-25

* Seen by Wayne on 2026-10-25 with `ezpkg` 0.0.1 from pypi.org: after
  removing `~/.ezpkg`, the Quick Start's first run asks its question,
  the second pauses (about 1.5 s) and the third runs at once.

  The pause is `refresh_pip` running `pip download pip`: `own_pip`
  fetches a new private `pip` on the first run but never wrote the
  `last_pip` stamp, so the second run thought a check was due.  Fixed
  for 0.0.2: `own_pip` writes the stamp, and `release_check.py` fails
  when a fresh `pip.whl` has no `last_pip`, so every rehearsal checks it
  on all of `check.yml`'s runners.
