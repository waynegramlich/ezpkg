# LLM Agent Context Log

## 2026-10-26

Found while designing `I.cernb`.  A developer's stash records
`ezpkg==0.0.1` in `checksums` (every stash in Wayne's `~/.ezpkg/develop/`
does), and `locked()` turns it into a constraint, with the stash's
`exclude-newer` date too.  Reproduced in `/tmp/claude-1000/-home-wayne-public-html-projects-ezpkg/0147b015-d3e2-4d9b-9a0a-d0d8181711b3/scratchpad/dev.794n`:
a developer's `prog.py` run once with 0.0.1, then given
`ezpkg>=0.0.5,<0.1` and the `2026-10-26` bootstrap, stops with
"`prog.py` did not run: ERROR: ResolutionImpossible".  So a developer
can never move to a newer `ezpkg`, and `chosen()` in a newer `ezpkg`
would switch back to the pinned old one.

Fixed (Wayne's #8a, 2026-10-26): `BOOTSTRAP_FLOORS` names the first
`ezpkg` that knows each released bootstrap (`2026-10-23` 0.0.1,
`2026-10-25` 0.0.3, `2026-10-26` 0.0.4); publishing a bootstrap adds
its entry.  `stale_pin`: a developer's stash pin failing Part 1's
`ezpkg` entry or the carried bootstrap's floor gives way; `chosen`
then ignores it, and `fetch` gets `ezpkg` by a `pip` of its own
without the lock or date (the newest meeting the entry and floor;
`ezpkg` has no dependencies), merged with the rest before recording,
so the stash records the new pin.  End users' release pins hold.
Seen end to end in the scratch home: the stash's 0.0.1 gave way,
`ezpkg==0.0.5` came alone from pypi.org, `cowsay` kept its pin and
date, and the next run fetched nothing.
