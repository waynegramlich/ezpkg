# 5 A real package server

Closed 2026-09-25.  Every `bootstrap.py` case fetches `alt_venv` from a
package server this project controls: `http.server` over the test
suite's PEP 503 tree, which serves the JSON API, misbehaves on request
and speaks TLS.
