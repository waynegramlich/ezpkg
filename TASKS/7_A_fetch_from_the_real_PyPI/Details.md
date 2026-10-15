# 7 A fetch from the real PyPI

The overall goal is to publish `ezpkg` to `test.pypi.org` and then
`pypi.org`, so that the Quick Start works for a new user.

## The Release Procedure

Every release of `EZPkg` follows the same procedure:
1. The release commit is pushed to
   [github.com](https://github.com/waynegramlich/ezpkg), whose account is
   protected by two factor authentication (repository made in `T.rtg`,
   keys in `T.suh2`).  It is not tagged yet.
2. The OpenID Connect (OIDC) protocol is used to publish that commit to
   [test.pypi.org](https://test.pypi.org) as a disposable `dev` version:
   `gh workflow run release.yml -f target=testpypi` (or the Actions
   tab), then Wayne approves the deployment on GitHub.  `T.wrw` builds
   the workflow that does this; `T.uttat` runs it for the first time.
3. The Quick Start is run as a new user, with the `ezpkg` just
   published on `test.pypi.org`: `./release_check.py testpypi`
   (`T.uttat`).  Steps 1 to 3 are repeated until the result is
   acceptable.
4. The same commit is tagged `vX.Y.Z` and the tag is pushed.  Only Wayne
   can create `v*` tags (set up in `T.wrw`).
5. The tagged commit is published to `pypi.org` by the same workflow
   (`gh workflow run release.yml --ref vX.Y.Z -f target=pypi`, then
   approval), and `./release_check.py pypi` verifies that nothing
   changed (`T.utpat`).
