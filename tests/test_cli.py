"""命令行参数测试。"""

import pytest

from seu_autologin import cli


def test_negative_timing_is_clamped(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(cli, "build_logger", lambda verbose=False: object())

    def fake_run(logger, **kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(cli, "run_autologin", fake_run)
    assert (
        cli.main(
            [
                "run-once",
                "--initial-delay",
                "-3",
                "--network-wait-seconds",
                "-10",
            ]
        )
        == 0
    )
    assert captured["initial_delay"] == 0
    assert captured["network_wait_seconds"] == 0


def test_check_can_skip_portal(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(cli, "build_logger", lambda verbose=False: object())

    def fake_check(logger, *, inspect_portal):
        captured["inspect_portal"] = inspect_portal
        return 0

    monkeypatch.setattr(cli, "check_environment", fake_check)
    assert cli.main(["check", "--skip-portal"]) == 0
    assert captured["inspect_portal"] is False


def test_background_flags_and_watch_interval(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "build_logger", lambda verbose=False: object())
    monkeypatch.setattr(cli, "run_autologin", lambda logger, **kw: captured.update(kw) or 0)
    assert cli.main(["run-once", "--automatic", "--no-browser-fallback"]) == 0
    assert captured["automatic"] and not captured["browser_fallback"]
    monkeypatch.setattr(cli, "watch_network", lambda logger, **kw: captured.update(kw) or 0)
    assert cli.main(["watch", "--interval", "-10"]) == 0
    assert captured["interval"] == 30


def test_credential_status_and_console_pause(monkeypatch):
    monkeypatch.setattr(cli, "build_logger", lambda verbose=False: object())
    monkeypatch.setattr(cli, "credential_exists_without_secret", lambda: False)
    prompts = []
    monkeypatch.setattr("builtins.input", lambda text: prompts.append(text) or "")
    assert cli.main(["--pause", "credential-status"]) == 3
    assert len(prompts) == 1


def test_windowless_version_command_does_not_crash(monkeypatch):
    monkeypatch.setattr(cli.sys, "stdout", None)
    monkeypatch.setattr(cli.sys, "stderr", None)
    try:
        with pytest.raises(SystemExit) as raised:
            cli.main(["--version"])
        assert raised.value.code == 0
    finally:
        cli.sys.stdout.close()
        cli.sys.stderr.close()
