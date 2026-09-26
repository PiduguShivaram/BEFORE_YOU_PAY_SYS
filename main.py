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
from before_you_pay.main import app  # noqa: E402, F401

__all__ = ["app"]

if __name__ == "__main__":
    from before_you_pay.main import run  # noqa: E402

    run()
