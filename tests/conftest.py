from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINI_JUNE = FIXTURES / "mini_june"


@pytest.fixture
def mini_june_folder() -> Path:
    return MINI_JUNE
