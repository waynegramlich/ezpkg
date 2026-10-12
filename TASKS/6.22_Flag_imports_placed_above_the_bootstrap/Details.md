# 6.22 Flag imports placed above the bootstrap

The README rule is that all of a program's own imports go after the
bootstrap.  An author who puts one above it anyway may never notice:

* On the author's machine, `import cowsay` above the bootstrap works
  when their own Python happens to have `cowsay` (installed by their
  Linux distribution or a `pip install --user`, say).  The packages in
  `~/.alt_venv` do not help: they are not importable until the
  bootstrap has run.
* On a friend's machine, the first run has an empty `~/.alt_venv`.
  Python reaches `import cowsay` before the bootstrap has run, so the
  bootstrap never gets the chance to fetch it, and the program fails
  with `ModuleNotFoundError` even though `cowsay` is in `dependencies`.

Because of the rule, the check is simple: any import above the
bootstrap other than `from __future__` and Part 2's seven is a
mistake.  `AltVEnv` can report it, with its line number, when the
program is exported (alongside `T.cibe`'s check) and during ordinary
runs (alongside `T.siofr`'s scan).
