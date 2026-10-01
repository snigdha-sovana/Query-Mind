from pathlib import Path

import pytest

FIXTURE_DB = Path(__file__).parent / "fixtures" / "fixture.sqlite"


@pytest.fixture(scope="session", autouse=True)
def fixture_database():
    path = Path(__file__).parent / "fixtures" / "build_fixture.py"
    ns = {"__name__": "build_fixture", "__file__": str(path)}
    exec(path.read_text(encoding="utf-8"), ns)
    ns["build"](FIXTURE_DB)
    return FIXTURE_DB
