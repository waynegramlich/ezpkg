# Summary of `I.dspef` A developers stash pins ezpkg forever
Fixed 2026-10-26 in `ezpkg` 0.0.6 (see `I.cernb` for the runs), by
Wayne's choice (a).  A developer's stash pinned `ezpkg==0.0.1` with
its date, so a newer `ezpkg` could never run the program (with Part
1's floor raised: `ResolutionImpossible`), and a newer one would switch
back.  `BOOTSTRAP_FLOORS` names the first `ezpkg` that knows each
released bootstrap (`2026-10-23` 0.0.1, `2026-10-25` 0.0.3,
`2026-10-26` 0.0.4); publishing a bootstrap adds one.  A pin failing
Part 1's entry or that floor gives way (`stale_pin`, `chosen`):
`fetch` gets `ezpkg` by its own `pip`, without pin or date, and the
stash records the new pin; end users' release pins hold.  Rehearsed
on a copy of Wayne's `~/.ezpkg` with `ezpkg.whl` deleted: the demo ran
unchanged.  Related: `I.cernb`, `T.eui`.
