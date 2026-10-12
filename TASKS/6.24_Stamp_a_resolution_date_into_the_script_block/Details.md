# 6.24 Stamp a resolution date into the script block

A `.py` emailed on its own has no `prog.altvenv`, so nothing locks its
packages: the friend gets whatever is newest the day they run it.  Put
the date the author resolved the packages into Part 1, where it travels
with the file, and fetch only packages uploaded before it.

* The date lives in the PEP 723 block as `[tool.uv] exclude-newer =
  "2026-10-12T19:05:41Z"`, which `uv run` already honours, so one line
  serves both tools.  `AltVEnv` hands it to `pip` as
  `--uploaded-prior-to` (new in `pip` 26).
* `ALT_VENV_APPROVE=write` stamps it, the same moment as the
  `# Resolved:` line in `prog.altvenv`.
* With approvals present the lock decides and the date is not used;
  `write` and `skip` ignore it too.
* An index without upload times (only PEP 691 JSON carries them), or a
  `pip` without the option, makes `pip` fail outright, so `AltVEnv`
  fetches again without the date and says so.
