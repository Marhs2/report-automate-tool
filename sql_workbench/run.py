#!/usr/bin/env python3
"""sql_workbench 폴더 안에서 실행할 때 사용:  python run.py"""

from __future__ import annotations

import sys
from pathlib import Path

# 이 폴더를 path에 넣어 db_manager / app 을 직접 import
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for p in (_HERE, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from app import main  # noqa: E402

if __name__ == "__main__":
    main()
