# LLM Agent Context Log

## 2026-10-12: done, uncommitted

* Module helpers: `script_toml`, `with_script_toml`, `uv_setting(toml,
  key, value | None)` (sets or removes one `[tool.uv]` key, verified by
  reparsing; refuses dotted keys or multi-line values).
  `pin_dependencies` uses them.
* `AltVEnv.cutoff()`, `AltVEnv.stamp(resolved)`; `approve` takes
  `resolved`; `gate`'s `write` branch stamps; `request_for` adds
  ` --uploaded-prior-to DATE`; `download(before=...)` retries without
  it on "does not provide upload-time metadata" or "no such option".
* `stamp` keeps encoding (via `tokenize.detect_encoding`), BOM and
  CRLF.  No block: silent.  Uneditable block: says to add it by hand.
* Behaviour changes Wayne should know:
  - `uv` export (`pin_dependencies`) now removes `exclude-newer` (pins
    and lock already fix versions, and `uv` with a date rejects files
    lacking upload times, which broke the uv export test).
  - `no-build = true` is now added to an author's existing `[tool.uv]`
    unless it already sets `no-build`; before, any `[tool.uv]` table
    suppressed it, and `write` now always creates one.
  - `write` edits the program, so in a `write`+export run the import
    check's line numbers are of the edited file (test updated).
* Tests: the test index serves PEP 691 JSON with upload times when
  `server.upload_times` is set (file mtime = upload time).  The
  end-to-end date test needs a `pip` >= 26, borrowed from the real
  `~/.alt_venv` by `dating_pip()`, skipped if none; `give_pip` also
  writes `last_pip` so `refresh_pip` does not swap in the index's
  older pip (it takes any version it has not got, which only bites in
  tests).
* `ALT_VENV_TEST=NONE`: 247 OK; ruff, mypy clean.
* README (`T.rd`) will want a line on the `[tool.uv]` table that
  `write` adds to Part 1.
* Wayne: editing the program needs a prompt first.  `AltVEnv.ask`
  (yes/no on `/dev/tty`, `ATTEMPTS` typos, no terminal = no) and
  `stamp` asks "alt_venv: could I add|change `exclude-newer = "..."` at
  line N of prog.py? [y=>Yes/n=>No]", N being the line after the edit.
  No or no terminal: file untouched, approvals still written, message
  says to add it by hand.  Tests: `test_ask_wants_a_yes_and_a_terminal`,
  `test_write_leaves_the_program_alone_unless_told`, and the stamp test
  now answers on a pty.  249 tests OK.
* Wayne on `refresh_pip`: the downloaded `pip` should be kept updated;
  left as it is (it may also step back to an older index `pip`).
