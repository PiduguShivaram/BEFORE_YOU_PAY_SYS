"""Vercel Python Serverless Function — FastAPI entrypoint.

When the Vercel project root is set to ``frontend/``, this file must live
at ``frontend/api/index.py`` so Vercel's Python builder discovers it and
routes all ``/api/...`` requests here.

sys.path is extended to reach ``../src`` (the monorepo's Python package
directory) so all ``before_you_pay.*`` imports resolve correctly.
"""

import sys
from pathlib import Path

# api/index.py is at  <repo>/frontend/api/index.py
# src/             is at  <repo>/src/
_src_dir = Path(__file__).resolve().parent.parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from before_you_pay.main import app  # noqa: E402, F401

__all__ = ["app"]
