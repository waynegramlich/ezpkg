# Summary of `I.mlmfpn` A missing local module fetches a PyPI namesake
Fixed 2026-10-26 in `ezpkg` 0.0.5, on pypi.org (tag `v0.0.5`,
`6fd240c`; rehearsal run 40371736487 28/28, `email_check.yml`
40372854639 13/13, release run 40374443534 28/28,
`release_check.py pypi 0.0.5` passed).  Reported by another Claude
instance: a scratch copy without its local `scplot.py` fetched PyPI's
unrelated `scplot`.  A developer is now asked about every import matched
to a package by its name alone ("`prog.py` line 43 imports `cowsay`.
Where should it come from?"; `EZPkg.choose`): each PyPI package that
provides it, numbered (several for `MODULE_CHOICES`' `cups`, `github`,
`xdg`), or "A local `cowsay.py`", which creates the empty file
(`Create Locally`).  A package that must be compiled is named but not
offered.  No terminal fetches nothing and says how to choose by hand;
a choice is kept in the stash's `chosen`.  `local` in `prog.py.toml`
names the program's own modules `ezpkg` cannot see; a release refuses a
program importing its own modules (`local_imports`);
`refuse_shadowing` stops a developer's run when the program's own
module shares a name with a module its packages brought (the cache
came first, so the local file was silently unused).  End users never
guess, so were never exposed.  README: Enabling, Releasing,
Troubleshooting.  Quick suite 353 OK, `ux/drive.py` 29/29.  Carried to
`T.zcpom`: a `zipapp` carrying the program's own modules.  Related:
`T.zcpom`, `T.ffrp`.
