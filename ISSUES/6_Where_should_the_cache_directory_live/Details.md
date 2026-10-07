# 6 Where should the cache directory live?

(CLOSED 2026-10-01)  `~/.cache/<program>/` per the XDG spec, or beside the
program, or the `~/.alt_venv` that Experiment 1 assumed without examining?
This interacts with `I.nicav`: whatever the location, the name has to carry the
interpreter and platform.

Various thoughts:
* Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
  experiment when we get the chance.
* Wayne (2026-10-01): Clear it belongs in `~/.alt_venv` somewhere, so
  this can be closed.
