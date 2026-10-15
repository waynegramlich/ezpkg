# LLM Agent Context Log

## 2026-10-12

* Moved from 6.17 at Wayne's word, with children 7.1 Reconnect to git
  (`T.rtg`), 7.2 Upload to test.pypi (`T.utt`), 7.3 Upload to pypi
  (`T.utp`).  The project is now `ezpkg` (`T.rp`); `ezpkg`, `ez-pkg`
  and `ez_pkg` were free on pypi.org and test.pypi.org on 2026-10-12.

## 2026-10-13: Publishing by Trusted Publishing, not tokens

* Wayne wants PyPI updated semi-automatically from GitHub, and the
  test.pypi upload to rehearse the final one.  So the children became
  7.1 `T.rtg` (closed), 7.2 `T.suh2` hardware 2FA, 7.3 `T.wrw` the
  release workflow, 7.4 `T.utt` test.pypi, 7.5 `T.utp` pypi.
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
