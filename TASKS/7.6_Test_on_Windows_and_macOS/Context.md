# LLM Agent Context Log

## 2026-10-16: Created

* Wayne's friend Chad ran `quick_start.py` on an old Mac with
  `PIP_EXTRA_INDEX_URL=https://test.pypi.org/simple` and `PIP_PRE=1`.
  It worked, so that Mac's `urllib` trusted pypi.org (`I.btosc`).  But
  both variables reach `EZPkg`'s own `pip download`, so it fetched
  test.pypi.org's stranger's `cowsay` 6.1.2; Chad is not worried.  His
  macOS and Python versions were not asked.
* Wayne wants a better way to run these tests, closing `I.wmau` before
  `T.utpat`.  Three children, all agreed: `T.gar` (GitHub Actions),
  `T.qvm` (QEMU), `T.fwrm` (friends).
* Wayne changed `T.wrw`'s decision: tests may now run on GitHub, not
  only on his machine.
* Held for later (Wayne): a safe recipe for friends (only the `ezpkg`
  wheel from test.pypi.org, via `PIP_FIND_LINKS`, no extra index), and
  dated notes on Chad's run in `I.wmau` and `I.btosc`.

## 2026-10-16: `T.gar` passed; `T.qvm` rejected

* `check.yml` run 38973983823: all 16 jobs passed (`T.gar`).
* `T.qvm` rejected (Wayne).  Its finding lives here until it becomes an
  issue: `EZPkg.terminal` opens `/dev/tty`, which Windows lacks, so a
  Windows user is never asked before a download, breaking README's
  "Download Prompt" promise.  Fix with `CONIN$`/`CONOUT$`; a person at
  a Windows console checks it (`T.fwrm`).  Blocks `T.utpat`.
* `T.fwrm` stays, narrowed to what runners cannot do (a person
  answering the prompt; Store, install manager, Homebrew and Apple
  Pythons).  Friends answer in days, not minutes (Wayne).
