from pathlib import Path

import pytest

from copilot.config import Settings

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def settings(tmp_path) -> Settings:
    import shutil

    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    return Settings(llm_provider="offline", knowledge_dir=data, index_dir=tmp_path / "index")


@pytest.fixture
def order_log() -> str:
    return (ROOT / "samples" / "order-service.log").read_text()


@pytest.fixture
def syslog() -> str:
    return (ROOT / "samples" / "syslog.log").read_text()
