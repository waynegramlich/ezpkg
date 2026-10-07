# 4 An already-importable package is installed anyway

All twelve cases ask whether the package is on disk at their own target, never
whether it is already importable.  With `coverage` present in an active virtual
environment, a case spends 1.42 s and 1.8 MB installing a copy it will not use,
where a leading `try: import` costs 0.10 s.  Cheap to fix; deliberately not
fixed yet.

Various thoughts:
* Wayne (2026-09-22): This can be dealt with much later since it is easy to
  fix.
* Claude (2026-09-24): Fixed in the second stage.  `AltVEnv.install`
  asks `contains` first and skips the install when the package is already in
  the cache.  The twelve cases are unchanged, so the measurement in Task 2
  still shows the defect.
* Claude (2026-09-25): A candidate for `### Closed Issues`, on the same
  terms as `I.whwnn`: fixed where it ships, unfixed in the pasted bootstrap.
  The two should close together or not at all.  Wayne's call.
* Claude (2026-09-26): The thought above no longer holds.  `I.whwnn`
  closed on its own, because Step 6.1 fixed the pasted half as well,
  and this issue's pasted half is still unfixed: all twelve cases test
  a path on disk rather than asking whether the package imports.  So
  it stays open on its own merits rather than as `I.whwnn`'s twin.  The
  fix is now cheaper than it was, since Step 6.3 has to rework the
  same guard for the versioned cache.
* Wayne (2026-10-01): Rejected.  I don't care if an extra download
  occurs.
