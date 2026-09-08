"""诊断报告最小化与隐私边界测试。"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from seu_autologin import diagnostics


def test_diagnostics_contains_no_identity_fields(monkeypatch) -> None:
    monkeypatch.setattr(diagnostics, "edge_available", lambda: True)
    monkeypatch.setattr(diagnostics, "credential_exists_without_secret", lambda: True)
    monkeypatch.setattr(diagnostics, "internet_available", lambda timeout=2: True)
    monkeypatch.setattr(diagnostics, "portal_network_ready", lambda timeout=2: True)
    monkeypatch.setattr(diagnostics, "scheduled_task_exists", lambda: False)
    report = diagnostics.collect_diagnostics()
    serialized = json.dumps(report, ensure_ascii=False).casefold()
    for forbidden in ("username", "password", "mac", "ssid", "cookie"):
        assert forbidden not in serialized
    assert report["telemetry_enabled"] is False
    assert report["fixed_portal_host"] == "10.9.10.100"


def test_write_diagnostics_uses_utf8_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(diagnostics, "diagnostics_dir", lambda: tmp_path)
    monkeypatch.setattr(
        diagnostics,
        "collect_diagnostics",
        lambda: {"status": "正常", "telemetry_enabled": False},
    )
    output = diagnostics.write_diagnostics()
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "正常"


def test_actual_task_fields_are_summarized_without_user_paths(monkeypatch, tmp_path):
    client = pytest.importorskip("win32com.client")
    from seu_autologin.paths import app_data_dir

    app_data_dir().mkdir()
    (app_data_dir() / "install_mode.txt").write_text("scheduled-events-periodic", encoding="utf-8")
    repetition = SimpleNamespace(Interval="")
    triggers = [
        SimpleNamespace(Type=9, Repetition=repetition),
        SimpleNamespace(Type=0, Subscription="NetworkProfile", Repetition=repetition),
        SimpleNamespace(Type=0, Subscription="Power-Troubleshooter", Repetition=repetition),
        SimpleNamespace(Type=1, Repetition=SimpleNamespace(Interval="PT2M")),
    ]
    action = SimpleNamespace(Path=str(tmp_path / "private-user-name" / "missing.exe"))
    task = SimpleNamespace(
        Enabled=True, State=3, LastTaskResult=0, LastRunTime=datetime(2026, 9, 8, 12),
        Definition=SimpleNamespace(Triggers=triggers, Actions=[action]),
    )
    folder = SimpleNamespace(GetTask=lambda name: task)
    service = SimpleNamespace(Connect=lambda: None, GetFolder=lambda name: folder)
    monkeypatch.setattr(client, "Dispatch", lambda name: service)
    status = diagnostics.collect_autostart_status()
    assert status["task_details_available"]
    assert status["triggers"] == ["logon", "network", "resume", "periodic"]
    assert status["last_task_result"] == 0
    assert status["action_files_present"] is False
    assert "private-user-name" not in json.dumps(status)
