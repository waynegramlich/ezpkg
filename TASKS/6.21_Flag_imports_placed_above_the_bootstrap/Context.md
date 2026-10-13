# LLM Agent Context Log

## 2026-10-11: Notes for whoever picks this up

* Allowed above the bootstrap: `from __future__` imports and Part 2's
  seven (`hashlib`, `importlib`, `json`, `pathlib`, `subprocess`,
  `sys`, `urllib.request as req`).  `bootstrap_node` finds the
  bootstrap's `try`; `program_imports` gives each import's line.
* Report at export (with `T.cibe`'s `check_imports`, refusing) and on
  ordinary runs (with `T.siofr`'s scan, warning only).
