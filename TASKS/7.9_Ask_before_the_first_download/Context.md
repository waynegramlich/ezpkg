# LLM Agent Context Log

## 2026-10-16: Designed, not built

* `Details.md` holds the agreed design: "The Download Prompt" (three
  lines, onus on the author) and "Keep or Delete" (`n` on a first run
  deletes `~/.ezpkg`; if in doubt, delete).  Nothing is built; Wayne's
  dogfood `output` still shows the old messages, which confused him
  until Claude said so plainly.
* Possible split (asked, not answered): first the messages (the
  three-line question, `y`/`n` endings, the decline line instead of
  `fetch packages failed: RuntimeError('declined: ...')`), which need
  no bootstrap change; then capturing `pip`'s output and handing it to
  `EZPkg.__init__()`, which makes a new bootstrap (`nopip7`) and must
  follow `T.eui`'s rehearsal.
