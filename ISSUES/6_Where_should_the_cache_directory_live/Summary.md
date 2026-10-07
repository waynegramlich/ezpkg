# Summary of `I.wscdl` Where should the cache directory live?

`~/.cache/<program>/` per the XDG spec, or beside the program, or the
`~/.alt_venv` that Experiment 1 assumed without examining? This interacts with
`I.nicav`: whatever the location, the name has to carry the interpreter and
platform.

Last thought: Wayne (2026-10-01): Clear it belongs in `~/.alt_venv` somewhere,
so this can be closed.
