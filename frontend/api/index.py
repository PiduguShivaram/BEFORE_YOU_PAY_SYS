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

from before_you_pay.main import app  # noqa: E402, F401

__all__ = ["app"]
