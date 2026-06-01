"""
conftest.py for tests/services/

Ensures the repo root (where scripts/ lives) is on sys.path so checkpoint tests
can import `scripts.ingest_phapdien` directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

# conftest.py lives at backend/tests/services/conftest.py
# _root = backend/tests/services/conftest.py -> tests -> backend -> VietNamLaw (4 levels)
_root = Path(__file__).parent.parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))