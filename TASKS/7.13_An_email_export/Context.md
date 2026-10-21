# LLM Agent Context Log

## 2026-10-20: Built (Wayne: "grind away on the `email` option")

* Why: a developer's `checksums` hold only what arrived on their own
  computer, so a package another computer alone needs (`tqdm`'s
  `colorama` on Windows) is refused there by `verify`.  Wayne's
  answer: a third export, `email`, which does the thorough work at a
  release.
* Measured: `pip download --platform win_amd64` (24.0 and 26.2.2)
  judges markers by this machine and never fetches `colorama`; `uv
  lock --script` resolves for every computer and lists every wheel's
  SHA-256.  So `email` needs `uv` on the developer's computer (refused
  with a plain line without it); the recipient needs only Python.
* Code: `EXPORT_FORMS` adds `"email"`; `release` names it
  `prog-X.Y.Z.py`; `build_email` locks a pinned, bootstrap-less copy
  in a scratch directory (`lock_script`, now shared with `build_uv`,
  with the `exclude-newer` date and a retry without it), checks the
  lock with `lock_mismatches`, and writes the program (bootstrap kept)
  with `checksums` from `everywhere_approvals`: the author's rows
  unchanged, plus one row per package the lock adds (a pure wheel, or
  the first compiled one with its `tag:`, version-only elsewhere as in
  S2.4d).  The program's own `checksums` are untouched.  Template
  `exports` line mentions `"email"` (`T.ept` may reword).
* Tests: `test_export_email_approves_what_other_computers_need` (index
  packages `paned`, needing `shutter` on `win32` only),
  `test_everywhere_approvals_adds_what_other_computers_need`; form
  lists updated.  Dogfooded against pypi.org with `tqdm`: the copy
  gained `colorama==0.4.6 id:4f1d9991f5acc0ca`, and ran as a new end
  user on Linux.
* README: proposals in `<!-- Claude: -->` comments (intro, `exports`
  bullet, Releasing with a new "Using `email`", Conclusion).

## Open

1. Wayne's decisions: default `exports` (`["email"]`?); the order of
   `EXPORT_FORMS`; the README proposals.
2. Not yet seen on a real Windows machine: a `check.yml` job running an
   `email` copy that needs `colorama` would prove it (needs a push).
3. Not done: warning at release when a compiled package has no wheel
   for some computer or Python `requires-python` admits (the friend
   would get "no version for this computer").  `ux/drive.py` has no
   `email` step yet.
