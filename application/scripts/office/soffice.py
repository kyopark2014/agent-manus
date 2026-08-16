"""
LibreOffice(soffice) 헬퍼 — `application/scripts/office/` 에서도 동일하게 사용.

구현은 `application/skills/pptx/scripts/office/soffice.py` 를 그대로 씁니다.

예:
    python scripts/office/soffice.py --headless --convert-to pdf artifacts/foo.pptx
"""

import sys
from pathlib import Path

# skills/pptx 쪽에서 `from office.soffice import ...` 패턴을 쓰므로 scripts 를 path 에 넣음
_PPTX_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "skills" / "pptx" / "scripts"
if str(_PPTX_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_PPTX_SCRIPTS))

from office.soffice import get_soffice_env, run_soffice  # noqa: E402

__all__ = ["get_soffice_env", "run_soffice"]


if __name__ == "__main__":
    result = run_soffice(sys.argv[1:])
    sys.exit(result.returncode)
