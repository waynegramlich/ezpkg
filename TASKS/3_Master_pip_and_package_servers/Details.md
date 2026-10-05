# 3 Master `pip` and package servers

Closed 2026-09-24.  The pipeline works end to end: a wheel built from
`alt_venv.py`, served from a PEP 503 tree, fetched by a `bootstrap.py`
case, installed into `~/.alt_venv` and imported, using nothing but the
standard library.
