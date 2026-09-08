"""所有测试使用隔离的数据目录，不修改真实用户的暂停标记和日志。"""

import pytest


@pytest.fixture(autouse=True)
def isolated_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("SEU_AUTOLOGIN_OSS_DATA_DIR", str(tmp_path / "app-data"))
