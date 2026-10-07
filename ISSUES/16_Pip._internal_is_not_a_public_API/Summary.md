# Summary of `I.pinpa` `pip._internal` is not a public API

Six of the twelve cases import it.  The pip documentation says in as many words
not to, and the module path has moved before.  This is code pasted into
programs and never updated afterwards, so when it breaks it breaks on some
other person's machine, at their pip version, with no one around to fix it.

Last thought: Wayne (2026-10-01): Closed, because we are downloading `pip`, and
the cases that import `pip._internal` are going away.
