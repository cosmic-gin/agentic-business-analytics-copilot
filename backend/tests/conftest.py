import pytest

from scripts.build_database import build_database


@pytest.fixture(scope="session")
def database(tmp_path_factory):
    path = tmp_path_factory.mktemp("snapshot") / "test.sqlite"
    build_database(path)
    return path
