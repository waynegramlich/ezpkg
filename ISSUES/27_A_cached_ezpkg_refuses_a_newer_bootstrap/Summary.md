# Summary of `I.cernb` A cached ezpkg refuses a newer bootstrap
Fixed 2026-10-26 in `ezpkg` 0.0.6, on pypi.org (tag `v0.0.6`,
`c615a2e`; rehearsal run 40409016110 28/28, `email_check.yml`
40409020562 13/13, release run 40409606288 28/28 after re-running one
macOS job that pypi.org's index cache served 0.0.5, `release_check.py
pypi 0.0.6` passed).  Reported from Wayne's `solidcraftcnc` demo: the
bootstrap never replaces `~/.ezpkg/ezpkg.whl`, so a cached 0.0.1
refused the `2026-10-26` bootstrap as edited.  Now a bootstrap dated
after every one this `ezpkg` knows (`newer_than_known`) makes
`EZPkg.outgrown` fetch the newest wheel from the index, check its
SHA-256, replace `ezpkg.whl` and restart the program with it; nothing
newer or no index leaves the usual check.  Seen for real with a fake
0.0.7 and bootstrap `2026-11-01` on a local index.  The Quick Start's
Part 1 is `ezpkg>=0.0.4,<0.1`.  0.0.1-0.0.5 caches cannot be rescued:
delete `ezpkg.whl` once.  README "How `EZPkg` Actually Works" has a
bullet.  Related: `I.dspef`, `I.mbicamp`, `I.r2birae`, `T.eui`.
