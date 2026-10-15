# LLM Agent Context Log

## 2026-10-12

* Moved from 6.17 at Wayne's word, with children 7.1 Reconnect to git
  (`T.rtg`), 7.2 Upload to test.pypi (`T.uttat`), 7.3 Upload to pypi
  (`T.utpat`).  The project is now `ezpkg` (`T.rp`); `ezpkg`, `ez-pkg`
  and `ez_pkg` were free on pypi.org and test.pypi.org on 2026-10-12.

## 2026-10-13: Publishing by Trusted Publishing, not tokens

* Wayne wants PyPI updated semi-automatically from GitHub, and the
  test.pypi upload to rehearse the final one.  So the children became
  7.1 `T.rtg` (closed), 7.2 `T.suh2` hardware 2FA, 7.3 `T.wrw` the
  release workflow, 7.4 `T.uttat` test.pypi, 7.5 `T.utpat` pypi.
* Trusted Publishing: PyPI trusts a named GitHub owner, repository,
  workflow file and (optionally) environment, and swaps GitHub's OIDC
  token for a 15-minute upload token.  A "pending publisher" can create
  a project that does not exist yet, so no API token is ever needed.
  test.pypi.org is configured separately.  `pypa/gh-action-pypi-publish`
  also attaches attestations.  From Claude's knowledge, not yet checked
  against docs.pypi.org/trusted-publishers.

## 2026-10-14

* `T.suh2` and `T.p2rc` are closed.  Most Trusted Publishing facts above
  were checked against docs.pypi.org (not the 15-minute token or the
  attestations); see `T.wrw`'s `Context.md`.

## 2026-10-15: The release procedure moved here

* Wayne's five-step procedure moved here from `T.wrw`, each step naming
  its task.  `T.utt` and `T.utp` were renamed "... and test", since
  testing against the index is part of each upload.
* Reordered so the tag comes after the test.pypi.org rehearsal: a pushed
  tag should never move, and `dev` uploads need no tag.
* Wayne: `v0.N.M` versions are disposable; a bad one is followed by the
  next number rather than repaired.

## 2026-10-15: `PyPI_Via_GitHub.md`

* Wayne asked for a reusable write-up of what was learned, for another
  project: `PyPI_Via_GitHub.md` at the top level, git-ignored for now.
  Bring it up to date when the `pypi` half works (`T.utpat`).

## 2026-10-15: Windows and macOS block shipping

* Wayne: `I.wmau` (Windows and macOS are untried) has to be closed
  before shipping to pypi.org (`T.utpat`).  Work on it starts after
  `T.kdaiis` closes.
