"""Vercel serverless function entrypoint.

Vercel's Python builder looks for ``api/index.py`` (or ``api/*.py``)
and exposes each file as a serverless function.  By importing ``app``
here, all FastAPI routes are served under ``/api/...`` via the rewrite
rules in ``vercel.json``.
"""

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode

_possible_dirs = [
    Path(__file__).resolve().parent.parent / "src",
    Path(__file__).resolve().parent / "src",
    Path(__file__).resolve().parent.parent / "src_py",
]

for d in _possible_dirs:
    if (d / "before_you_pay").exists():
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
        break
else:
    fallback = Path(__file__).resolve().parent.parent / "src"
    if str(fallback) not in sys.path:
        sys.path.insert(0, str(fallback))

from before_you_pay.main import app as _fastapi_app  # noqa: E402


async def app(scope, receive, send):
    """ASGI entrypoint routing rewritten requests back to their original paths."""
    if scope.get("type") == "http":
        qs_bytes = scope.get("query_string", b"")
        qs = qs_bytes.decode("utf-8", errors="replace")
        if "__orig_path__" in qs:
            params = parse_qs(qs, keep_blank_values=True)
            if "__orig_path__" in params:
                orig_path = params.pop("__orig_path__")[0]
                scope["path"] = orig_path
                if "raw_path" in scope:
                    scope["raw_path"] = orig_path.encode("utf-8")
                new_qs = urlencode(params, doseq=True)
                scope["query_string"] = new_qs.encode("utf-8")
        else:
            headers = dict(scope.get("headers", []))
            matched_path = headers.get(b"x-matched-path")
            if matched_path:
                path_str = matched_path.decode("utf-8", errors="replace")
                if path_str and path_str != "/api/index.py":
                    scope["path"] = path_str
                    if "raw_path" in scope:
                        scope["raw_path"] = path_str.encode("utf-8")
    await _fastapi_app(scope, receive, send)


__all__ = ["app"]
