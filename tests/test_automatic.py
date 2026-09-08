"""重连补查不会反复提交错误凭据，普通用户启动项能够持续工作。"""

import logging

from seu_autologin import automatic, runner
from seu_autologin.models import Credential, LoginResult


def _prepare(monkeypatch):
    monkeypatch.setattr(runner, "acquire_single_instance", lambda *args: object())
    monkeypatch.setattr(runner, "release_single_instance", lambda handle: None)
    monkeypatch.setattr(runner, "internet_available", lambda timeout=3: False)
    monkeypatch.setattr(runner, "portal_network_ready", lambda timeout=2: True)
    monkeypatch.setattr(runner, "load_credential", lambda: Credential("test", "test"))
    monkeypatch.setattr(runner.time, "sleep", lambda seconds: None)
    return logging.getLogger("automatic-tests")


def test_zero_network_wait_does_not_cancel_second_login_attempt(monkeypatch):
    logger = _prepare(monkeypatch)
    calls = []
    results = iter([
        LoginResult(True, False, "技术性超时"),
        LoginResult(True, False, "成功", gateway_authenticated=True),
    ])

    def submit(*args):
        calls.append(True)
        return next(results)

    monkeypatch.setattr(runner, "submit_login", submit)
    assert runner.run_autologin(logger, initial_delay=0, network_wait_seconds=0) == 0
    assert len(calls) == 2


def test_rejection_pauses_next_background_trigger_before_credential_read(monkeypatch):
    logger = _prepare(monkeypatch)
    monkeypatch.setattr(
        runner, "submit_login", lambda *args: LoginResult(True, True, "服务器拒绝"),
    )
    assert runner.run_autologin(
        logger, initial_delay=0, automatic=True, browser_fallback=False,
    ) == 4
    assert automatic.automatic_paused()

    def forbidden():
        raise AssertionError("后续后台触发不应再次读取凭据")

    monkeypatch.setattr(runner, "load_credential", forbidden)
    assert runner.run_autologin(logger, initial_delay=0, automatic=True) == 6
    automatic.resume_automatic()
    assert not automatic.automatic_paused()


def test_network_recovery_during_retry_delay_avoids_second_submission(monkeypatch):
    logger = _prepare(monkeypatch)
    states = iter([False, False, True])
    monkeypatch.setattr(runner, "internet_available", lambda timeout=3: next(states))
    calls = []
    monkeypatch.setattr(
        runner, "submit_login", lambda *args: calls.append(1) or LoginResult(True, False, "等待"),
    )
    assert runner.run_autologin(logger, initial_delay=0, network_wait_seconds=0) == 0
    assert calls == [1]


def test_startup_watch_survives_temporary_error_and_never_opens_browser(monkeypatch):
    logger = _prepare(monkeypatch)
    calls = []
    released = []

    def check(logger, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise OSError("临时错误")
        return 0

    def sleep(seconds):
        assert seconds == 120
        if len(calls) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(runner, "run_autologin", check)
    monkeypatch.setattr(runner.time, "sleep", sleep)
    monkeypatch.setattr(runner, "release_single_instance", released.append)
    assert runner.watch_network(logger) == 0
    assert len(calls) == 2
    assert all(call["automatic"] and not call["browser_fallback"] for call in calls)
    assert len(released) == 1


def test_duplicate_watcher_exits_without_network_work(monkeypatch):
    monkeypatch.setattr(runner, "acquire_single_instance", lambda *args: None)
    assert runner.watch_network(logging.getLogger("watch-test")) == 0
