import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    """tests/fixtures/<name>을 읽는다. JSON이면 dict로, 아니면 경로로 돌려준다."""

    def _load(name: str):
        path = FIXTURES / name
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        return path

    return _load
