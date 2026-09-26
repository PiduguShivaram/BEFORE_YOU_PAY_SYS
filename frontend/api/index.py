"""Vercel Python Serverless Function — FastAPI entrypoint.

When the Vercel project root is set to ``frontend/``, this file must live
at ``frontend/api/index.py`` so Vercel's Python builder discovers it and
routes all ``/api/...`` requests here.

sys.path is extended to reach ``../src`` (the monorepo's Python package
directory) so all ``before_you_pay.*`` imports resolve correctly.
"""

import sys
from pathlib import Path

# Resolve package directory across local, monorepo, and Vercel Lambda layouts
_possible_dirs = [
    Path(__file__).resolve().parent.parent / "src_py",
    Path(__file__).resolve().parent.parent / "src",
    Path(__file__).resolve().parent.parent.parent / "src",
]

for d in _possible_dirs:
    if (d / "before_you_pay").exists():
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
        break
else:
    fallback = Path(__file__).resolve().parent.parent / "src_py"
    if str(fallback) not in sys.path:
        sys.path.insert(0, str(fallback))

from before_you_pay.main import app as _fastapi_app  # noqa: E402


from urllib.parse import parse_qs, urlencode


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
