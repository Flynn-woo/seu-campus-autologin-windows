"""凭据规范化和只读存在性检查测试。"""

from types import SimpleNamespace

from seu_autologin import credentials
from seu_autologin.automatic import automatic_paused, pause_automatic


def test_normalize_username() -> None:
    assert credentials.normalize_username("  example_user  ") == "example_user"
    assert credentials.normalize_username("example_user@xyw") == "example_user"
    assert credentials.normalize_username("example_user@XYW") == "example_user"


def test_credential_exists_only_checks_target_name(monkeypatch) -> None:
    result = SimpleNamespace(
        stdout="Target: LegacyGeneric:target=SEUCampusAutoLoginOSS/SEU-WLAN\n",
        returncode=0,
    )
    monkeypatch.setattr(credentials.subprocess, "run", lambda *args, **kwargs: result)
    assert credentials.credential_exists_without_secret()


def test_credential_exists_returns_false_when_cmdkey_fails(monkeypatch) -> None:
    def raise_error(*args, **kwargs):
        raise OSError("cmdkey unavailable")

    monkeypatch.setattr(credentials.subprocess, "run", raise_error)
    assert not credentials.credential_exists_without_secret()


def test_save_rejects_blank_values() -> None:
    for username, password in (("", "x"), ("x", "")):
        try:
            credentials.save_credential(username, password)
        except ValueError:
            pass
        else:
            raise AssertionError("空凭据必须被拒绝")


class FakePyWinError(Exception):
    """模拟 pywintypes.error。"""

    def __init__(self, code):
        super().__init__(code, "fake", "fake")
        self.winerror = code


class FakeWin32Cred:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    def __init__(self, read_value=None, read_error=None, delete_error=None):
        self.read_value = read_value
        self.read_error = read_error
        self.delete_error = delete_error
        self.written = None
        self.deleted = None

    def CredWrite(self, value, flags):
        self.written = (value, flags)

    def CredRead(self, target, credential_type, flags):
        if self.read_error:
            raise self.read_error
        return self.read_value

    def CredDelete(self, target, credential_type, flags):
        if self.delete_error:
            raise self.delete_error
        self.deleted = (target, credential_type, flags)


def test_save_writes_public_target(monkeypatch) -> None:
    fake = FakeWin32Cred()
    monkeypatch.setattr(
        credentials,
        "_win32_modules",
        lambda: (SimpleNamespace(error=FakePyWinError), fake),
    )
    pause_automatic()
    credentials.save_credential("  user@xyw ", "secret")
    assert not automatic_paused()
    value, flags = fake.written
    assert value["TargetName"] == "SEUCampusAutoLoginOSS/SEU-WLAN"
    assert value["UserName"] == "user"
    assert value["CredentialBlob"] == "secret"
    assert flags == 0


def test_load_decodes_byte_password(monkeypatch) -> None:
    fake = FakeWin32Cred(
        read_value={"UserName": "user@xyw", "CredentialBlob": "口令".encode("utf-16-le")}
    )
    monkeypatch.setattr(
        credentials,
        "_win32_modules",
        lambda: (SimpleNamespace(error=FakePyWinError), fake),
    )
    result = credentials.load_credential()
    assert result.username == "user"
    assert result.password == "口令"


def test_missing_credential_returns_none(monkeypatch) -> None:
    fake = FakeWin32Cred(read_error=FakePyWinError(1168))
    monkeypatch.setattr(
        credentials,
        "_win32_modules",
        lambda: (SimpleNamespace(error=FakePyWinError), fake),
    )
    assert credentials.load_credential() is None


def test_delete_credential_success_and_not_found(monkeypatch) -> None:
    fake = FakeWin32Cred()
    monkeypatch.setattr(
        credentials,
        "_win32_modules",
        lambda: (SimpleNamespace(error=FakePyWinError), fake),
    )
    assert credentials.delete_credential()
    assert fake.deleted[0] == "SEUCampusAutoLoginOSS/SEU-WLAN"

    missing = FakeWin32Cred(delete_error=FakePyWinError(1168))
    monkeypatch.setattr(
        credentials,
        "_win32_modules",
        lambda: (SimpleNamespace(error=FakePyWinError), missing),
    )
    assert not credentials.delete_credential()


def test_configure_rejects_mismatched_confirmation(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "user")
    answers = iter(["first", "second"])
    monkeypatch.setattr(credentials.getpass, "getpass", lambda prompt: next(answers))
    assert credentials.configure_credential() == 2


def test_configure_saves_matching_values(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr("builtins.input", lambda prompt: "user")
    monkeypatch.setattr(credentials.getpass, "getpass", lambda prompt: "secret")
    monkeypatch.setattr(
        credentials,
        "save_credential",
        lambda username, password: captured.update(username=username, password=password),
    )
    assert credentials.configure_credential() == 0
    assert captured == {"username": "user", "password": "secret"}
