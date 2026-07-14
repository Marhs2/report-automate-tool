"""python -m sql_workbench  (프로젝트 루트에서 실행)"""

from __future__ import annotations

import sys
from pathlib import Path

# 현재 작업 폴더가 sql_workbench 여도 동작하도록 루트를 path에 추가
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sql_workbench.app import main

if __name__ == "__main__":
    main()
