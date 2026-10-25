# Summary of `T.ffrp` A fetch from the real PyPI
Done 2026-10-25: `ezpkg` 0.0.1 is on pypi.org (`T.utpat`), so the
Quick Start works for a new user.  `Details.md` holds the release
procedure every release follows: push the commit; `release.yml`
publishes a disposable `dev` build to test.pypi.org (approved on
GitHub) and its `check` job runs the Quick Start on Linux, Windows and
both Macs; `./release_check.py testpypi` and `email_check.yml` pass;
then the same commit is tagged `vX.Y.Z` (only the admin may, by the
`release tags` ruleset), and `release.yml --ref vX.Y.Z -f target=pypi`
publishes it after approval, and `./release_check.py pypi X.Y.Z`
confirms.  Wayne's only git step is `git commit`; Claude pushes, tags,
starts and approves runs, and does GitHub settings with `gh api`.  An
approval now needs a `comment`.  On the way: 2FA keys (`T.suh2`,
`T.p2rc`), the workflows (`T.wrw`, `T.gar`), Windows and macOS
(`T.towam`), the end user's question (`T.abfd`), releases (`T.ee`,
`T.ept`), the README sweep (`T.rsbr`), and S4: the Part 1 editing
code deleted, end-user tests using a real `email` copy, 342 tests and
17 unrun lines in `ezpkg.py`.  `History.md` has the detail.  Related:
`T.utpat`, `T.uttat`, `T.rsbr`.
