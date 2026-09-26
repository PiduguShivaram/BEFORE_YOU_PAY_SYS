"""Root entrypoint for FastAPI CLI and local development.

This file exists so that `fastapi run`, `fastapi dev`, and Vercel's
Python builder can all discover the FastAPI application without any
additional configuration.  The actual application factory lives in
``src/before_you_pay/main.py`` — this shim simply adds ``src`` to
``sys.path`` and re-exports ``app``.
"""

import sys
from pathlib import Path

# Ensure the 'src' package directory is resolvable before importing the
# application package.
_src_dir = Path(__file__).resolve().parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# Re-export the application instance so external tools find ``app`` here.
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

if __name__ == "__main__":
    from before_you_pay.main import run  # noqa: E402

    run()
