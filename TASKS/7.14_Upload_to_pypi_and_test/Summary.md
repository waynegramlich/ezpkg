# Summary of `T.utpat` Upload to pypi and test
Done 2026-10-25: `ezpkg` 0.0.1 is on pypi.org, from the tag `v0.0.1`
(`95dd84a`), by release run 40147698445 (build, publish, and the 25
`check` jobs: 27/27); `./release_check.py pypi 0.0.1` passed as a new
user.  Setup: Wayne added the pypi.org pending publisher (`ezpkg`,
`waynegramlich/ezpkg`, `release.yml`, environment `pypi`); Claude, by
`gh api`, gave the `pypi` environment Wayne as required reviewer and a
`v*` tag rule, and made the tag ruleset `release tags` (only the admin
creates, moves or deletes `v*` tags).  `release.yml` now ends with a
`check` job calling `check.yml` (`workflow_call`) for the version it
built, carried from `T.gar`, first proved on test.pypi.org
(`0.0.1.dev202610250032`).  Wayne's only git step is `git commit`:
Claude tagged, pushed, started and approved the run.  Related:
`T.ffrp`, `T.wrw`, `T.gar`, `T.uttat`.
