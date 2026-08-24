"""app/data/raw/(원본 경쟁 문서)는 .gitignore 대상이라 저장소/CI에는 없다.

raw 파일이 실제로 있는 로컬 환경에서만 파서·검색 테스트를 돌리고,
CI처럼 raw가 없는 환경에서는 두 모듈을 skip한다 (실패가 아니라 skip으로
표시해야 CI가 "raw 문서 없음"과 "코드 회귀"를 구분할 수 있다).
"""

from pathlib import Path

import pytest

_RAW_DIR = Path("app/data/raw")
_RAW_DEPENDENT_MODULES = {"test_parse_documents.py", "test_role_b_retrieval.py"}
# app/data/raw 없이도 통과하는 것으로 확인된 테스트만 skip에서 제외한다.
_NO_RAW_NEEDED = {"test_chunk_id_is_deterministic_for_same_input", "test_chunk_output_serializable"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if _RAW_DIR.exists():
        return
    skip = pytest.mark.skip(reason="app/data/raw/ 원본 문서가 없음 (.gitignore 대상, 로컬 전용)")
    for item in items:
        if Path(item.fspath).name in _RAW_DEPENDENT_MODULES and item.name not in _NO_RAW_NEEDED:
            item.add_marker(skip)
