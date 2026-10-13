# LLM Agent Context Log

## 2026-10-12: the lock is in

* `AltVEnv.locked()` returns `pins()` on an ordinary run, and nothing
  under `write`, `skip` or with no approvals.  `provide` hands it to
  `download`, which writes `constraints.txt` into the holding directory
  and passes `--constraint`.  Constraints, not requirements, so a
  recorded package the program no longer asks for is not fetched.
* The request record's key gets ` -c ` plus the lock, so a warm record
  from an unlocked (`skip`) run cannot answer a locked one.
* A `pip` failure under a lock adds "the versions locked in ... may be
  the conflict: regenerate it with ALT_VENV_APPROVE=write".
* Tests: `test_an_unapproved_wheel_is_refused` now adds a new package
  (asking for `sprocket==2.0.0` is a conflict now, not a refusal).
  New: `test_the_approvals_lock_the_versions`,
  `test_the_lock_is_not_answered_by_an_unlocked_record`,
  `test_write_upgrades_past_the_lock`,
  `test_a_lock_dependencies_moved_past_names_the_file`.
  `ALT_VENV_TEST=NONE`: 240 tests OK; ruff and mypy clean.
* Wayne decided: `write` always fetches afresh (never answered from a
  request record), so it really is "upgrade and record".  The old
  warm-cache `write` branch in `provide` is gone;
  `test_approvals_can_be_written_from_a_warm_cache` became
  `test_approvals_are_written_afresh_from_a_warm_cache`.
* Wayne asked for a date: the file now carries `# Resolved:
  YYYY-MM-DDTHH:MM:SSZ` (UTC), the day `pip` chose the listed wheels.
  Still the plain-text format, one `wheel sha256` line each; the date
  is a comment so `approved` reads the file unchanged.
* `request_for(asking)` builds the record key (requirements plus the
  lock) for both `provide` and `build_zipapp`; before it, a zipapp
  export in a run of its own, from a cache with no unlocked record,
  failed "did not come from the cache".  Test:
  `test_export_zipapp_after_approving_in_another_run` (fails on the old
  lookup, checked).
* `pins` now raises a `RuntimeError` naming a non-wheel line (it runs on
  every ordinary run now).  Test: `test_pins_refuse_what_is_not_a_wheel`.
* Found, not changed: nothing reads the kept wheels in `wheels/` any
  more (only the old warm `write` did).  Could stop keeping them.
* `ALT_VENV_TEST=NONE`: 242 tests OK; ruff and mypy clean.
