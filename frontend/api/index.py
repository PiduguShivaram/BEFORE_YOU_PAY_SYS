"""Vercel Python Serverless Function — FastAPI entrypoint.

When the Vercel project root is set to ``frontend/``, this file must live
at ``frontend/api/index.py`` so Vercel's Python builder discovers it and
routes all ``/api/...`` requests here.

sys.path is extended to reach ``../src`` (the monorepo's Python package
directory) so all ``before_you_pay.*`` imports resolve correctly.
"""

import sys
from pathlib import Path

# On the Vercel Lambda the project root is /var/task/:
#   __file__          = /var/task/api/index.py
#   .parent           = /var/task/api/
#   .parent.parent    = /var/task/          ← lambda root
#   / "src"           = /var/task/src/      ← where includeFiles bundles src/
# (Three .parent calls would reach /var/ — wrong.)
_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from before_you_pay.main import app  # noqa: E402, F401

__all__ = ["app"]
