# LLM Agent Context Log

## 2026-10-11: Notes for whoever picks this up

* The Enabling block is not a text copy of `quick_start.py`: it has
  `dependencies = []`, a `"""TOP_LEVEL_DOCSTRING"""` placeholder, a
  `# Any from __future__ import ... goes here.` comment and a closing
  `# Your imports go here...` comment, and no Parts 4 and 5.  So
  compare what matters: the Part 2 imports, and Part 3 by
  `bootstrap_fingerprint` (which ignores comments and layout) against
  `list(alt_venv.BOOTSTRAPS)[-1]`, as `test_the_quick_start_is_current`
  does.  Find the block after the line "Immediately below is the
  `AltVEnv` bootstrap:" in `README.md`.
* Verified by hand on 2026-10-11: the block, pasted as a program, fails
  with `ModuleNotFoundError` under `dependencies = []` and runs once
  `cowsay` is added (needs `PYTHONPATH` at the repository until
  `alt_venv` is on PyPI, `T.ffrp`).
