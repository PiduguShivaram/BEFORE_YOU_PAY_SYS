"""Vercel serverless function entrypoint.

Vercel's Python builder looks for ``api/index.py`` (or ``api/*.py``)
and exposes each file as a serverless function.  By importing ``app``
here, all FastAPI routes are served under ``/api/...`` via the rewrite
rules in ``vercel.json``.
"""

import sys
from pathlib import Path

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
        headers = dict(scope.get("headers", []))
        sys.stderr.write(f"ENTRYPOINT: path={scope.get('path')} headers={headers}\n")
        sys.stderr.flush()
        matched_path = headers.get(b"x-matched-path")
        if matched_path:
            path_str = matched_path.decode("utf-8", errors="replace")
            if path_str and path_str != "/api/index.py":
                scope["path"] = path_str
    await _fastapi_app(scope, receive, send)


__all__ = ["app"]
