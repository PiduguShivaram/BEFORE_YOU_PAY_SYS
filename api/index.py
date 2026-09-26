"""Vercel serverless function entrypoint.

Vercel's Python builder looks for ``api/index.py`` (or ``api/*.py``)
and exposes each file as a serverless function.  By importing ``app``
here, all FastAPI routes are served under ``/api/...`` via the rewrite
rules in ``vercel.json``.
"""

import sys
from pathlib import Path

# Resolve the repo root → src directory so absolute package imports work
# inside Vercel's sandboxed build environment.
_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from before_you_pay.main import app  # noqa: E402, F401

__all__ = ["app"]
