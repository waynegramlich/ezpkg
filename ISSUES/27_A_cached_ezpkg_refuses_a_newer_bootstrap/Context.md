# LLM Agent Context Log

## 2026-10-26

Reported by Wayne's other Claude instance (solidcraftcnc demo): the
bootstrap never replaces `~/.ezpkg/ezpkg.whl` once it exists, so a
cached 0.0.1 (which knows bootstraps only up to `2026-10-23`) refuses
`2026-10-26` as "edited".  0.0.1-0.0.5 are out and cannot change.

Wayne's decisions: fix it (bootstrap names are dates, so the age is
plain); raise the Quick Start's Part 1 floor to the first `ezpkg` that
knows the current bootstrap (`ezpkg>=0.0.4,<0.1`).  Do not work around
it in the demo: Wayne is the one customer and wants the pain found.

Plan: a bootstrap name that is a date later than the newest this
`ezpkg` knows means this `ezpkg` is too old: fetch the newest from
the index, replace `ezpkg.whl`, run the program again with it.  Blocked
on `I.dspef`: a developer's stash pins `ezpkg==0.0.1`, so a newer
`ezpkg` would switch straight back (a loop).

Fixed: `newer_than_known` (a `DATED` name later than the newest in
`BOOTSTRAPS`) makes `EZPkg.outgrown`, called first by `install`,
fetch the newest wheel listed by the index's JSON (`json_api`),
check its SHA-256, replace `ezpkg.whl`, and `run_again` with it first
on `PYTHONPATH` (`EZPKG_SWITCHED`, as `switch` does).  Nothing newer,
or no index: this `ezpkg` judges as usual, so a made-up date is still
an edit.  Only `ezpkg` 0.0.6 on is fixed; 0.0.1-0.0.5 caches need
Part 1's floor (`T.eui` switch) or deleting `ezpkg.whl`.  The Quick
Start's Part 1 is now `ezpkg>=0.0.4,<0.1` (`quick_start.py`,
`QUICK_START`, README).  README: a proposed bullet in an HTML comment
under "How `EZPkg` Actually Works".  Tested with mocks
(`test_a_newer_bootstrap_fetches_a_newer_ezpkg`); a real run needs an
`ezpkg` newer than a cached 0.0.6.

Rehearsals, 2026-10-26: `release.yml` testpypi run 40400319739 28/28
(`0.0.6.dev202610262058`), `email_check.yml` 40400324441 13/13,
`./release_check.py testpypi` passed.  The newer-bootstrap fetch seen
for real: a cached 0.0.6 wheel of this tree, a made-up 0.0.7 knowing a
fake bootstrap `2026-11-01` (`None, 61`) served by a local static index
(`PIP_INDEX_URL`), and a program carrying it.  Run 1 said "`prog.py`
carries the bootstrap `2026-11-01`, which is newer than `ezpkg` 0.0.6,
so `ezpkg` 0.0.7 was fetched to run it." and ran with 0.0.7; run 2
started on 0.0.7 with nothing fetched.  README "How `EZPkg` Actually
Works" has a bullet for it (Wayne: small edits there are fine).
Wayne declined a Troubleshooting entry: he is the only user.
