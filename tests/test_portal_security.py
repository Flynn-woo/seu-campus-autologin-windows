"""固定门户允许列表和失败识别测试。"""

from types import SimpleNamespace

from seu_autologin import portal
from seu_autologin.models import Credential
from seu_autologin.portal import (
    _body_indicates_failure,
    is_allowed_portal_url,
    safe_portal_display,
)


def test_fixed_portal_and_same_host_resources_are_allowed() -> None:
    assert is_allowed_portal_url("http://10.9.10.100/")
    assert is_allowed_portal_url("http://10.9.10.100/a41.js?v=1")
    assert is_allowed_portal_url("http://10.9.10.100:80/0.htm")


def test_cross_host_redirects_and_credentials_in_url_are_blocked() -> None:
    assert not is_allowed_portal_url("https://10.9.10.100/")
    assert not is_allowed_portal_url("http://10.9.10.101/")
    assert not is_allowed_portal_url("http://example.com/")
    assert not is_allowed_portal_url("http://10.9.10.100:8080/")
    assert not is_allowed_portal_url("http://user:pass@10.9.10.100/")
    assert not is_allowed_portal_url("not-a-url")


def test_safe_display_never_contains_query_parameters() -> None:
    assert safe_portal_display("http://10.9.10.100/?DDDDD=123&upass=secret") == (
        "http://10.9.10.100/"
    )
    assert safe_portal_display("http://example.com/?upass=secret") == "<blocked>"


def test_explicit_failure_text_is_recognized() -> None:
    assert _body_indicates_failure("用户名或密码错误")
    assert _body_indicates_failure("CHECK THE NETWORK CONFIGURATION")
    assert not _body_indicates_failure("欢迎使用校园网")


class FakeLocator:
    def __init__(self, *, count=1, visible=True, body_text=""):
        self._count = count
        self._visible = visible
        self.body_text = body_text
        self.filled = None
        self.clicked = False

    def count(self):
        return self._count

    def is_visible(self):
        return self._visible

    def fill(self, value):
        self.filled = value

    def click(self):
        self.clicked = True

    def inner_text(self, timeout=0):
        return self.body_text


class FakePage:
    def __init__(self, *, title="", body_text=""):
        self.url = "http://10.9.10.100/"
        self._title = title
        self.locators = {
            'input[name="logout"]': FakeLocator(count=0, visible=False),
            'input[name="DDDDD"][type="text"]': FakeLocator(),
            'input[name="upass"][type="password"]': FakeLocator(),
            'input[name="0MKKey"][type="submit"]': FakeLocator(),
            'input[name="captcha"]': FakeLocator(count=0, visible=False),
            "body": FakeLocator(body_text=body_text),
        }

    def title(self):
        return self._title

    def locator(self, selector):
        return self.locators[selector]

    def wait_for_timeout(self, timeout):
        return None

    def goto(self, url, **kwargs):
        self.url = url


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.route_handler = None
        self.closed = False

    def route(self, pattern, handler):
        self.route_handler = handler

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context):
        self.context = context
        self.closed = False

    def new_context(self, **kwargs):
        return self.context

    def close(self):
        self.closed = True


class FakePlaywrightManager:
    def __init__(self, page):
        context = FakeContext(page)
        browser = FakeBrowser(context)
        chromium = SimpleNamespace(launch=lambda **kwargs: browser)
        self.playwright = SimpleNamespace(chromium=chromium)

    def __enter__(self):
        return self.playwright

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_portal_state_recognizes_authenticated_and_login() -> None:
    authenticated = FakePage(title="校园网注销页")
    assert portal.portal_state(authenticated, timeout_ms=1) == "authenticated"

    login = FakePage()
    assert portal.portal_state(login, timeout_ms=1) == "login"

    blocked = FakePage()
    blocked.url = "http://example.com/"
    assert portal.portal_state(blocked, timeout_ms=1) == "blocked"


def test_portal_state_unknown_when_deadline_expires() -> None:
    assert portal.portal_state(FakePage(), timeout_ms=0) == "unknown"


def test_route_allows_only_fixed_host_and_blocks_heavy_resources() -> None:
    class FakeRoute:
        def __init__(self, url, resource_type):
            self.request = SimpleNamespace(url=url, resource_type=resource_type)
            self.action = None

        def abort(self):
            self.action = "abort"

        def continue_(self):
            self.action = "continue"

    script = FakeRoute("http://10.9.10.100/a41.js", "script")
    portal._route_with_allowlist(script)
    assert script.action == "continue"

    image = FakeRoute("http://10.9.10.100/logo.png", "image")
    portal._route_with_allowlist(image)
    assert image.action == "abort"

    foreign = FakeRoute("https://example.com/collect", "script")
    portal._route_with_allowlist(foreign)
    assert foreign.action == "abort"


def test_submit_login_stops_when_edge_or_constant_is_invalid(monkeypatch) -> None:
    logger = SimpleNamespace(info=lambda *args: None, debug=lambda *args: None)
    monkeypatch.setattr(portal, "edge_available", lambda: False)
    result = portal.submit_login(Credential("u", "p"), logger)
    assert not result.submitted

    monkeypatch.setattr(portal, "edge_available", lambda: True)
    monkeypatch.setattr(portal, "PORTAL_URL", "http://example.com/")
    result = portal.submit_login(Credential("u", "p"), logger)
    assert result.explicit_failure


def test_submit_login_recognizes_authenticated_gateway(monkeypatch) -> None:
    page = FakePage()
    logger = SimpleNamespace(info=lambda *args: None, debug=lambda *args: None)
    monkeypatch.setattr(portal, "edge_available", lambda: True)
    monkeypatch.setattr(portal, "portal_state", lambda page: "authenticated")
    monkeypatch.setattr(portal, "sync_playwright", lambda: FakePlaywrightManager(page))
    result = portal.submit_login(Credential("u", "p"), logger)
    assert result.gateway_authenticated
    assert not result.submitted


def test_submit_login_fills_expected_fields_and_succeeds(monkeypatch) -> None:
    page = FakePage()
    logger = SimpleNamespace(info=lambda *args: None, debug=lambda *args: None)
    monkeypatch.setattr(portal, "edge_available", lambda: True)
    monkeypatch.setattr(portal, "portal_state", lambda page, **kwargs: "login")
    monkeypatch.setattr(portal, "sync_playwright", lambda: FakePlaywrightManager(page))
    monkeypatch.setattr(portal, "internet_available", lambda timeout=3: True)
    result = portal.submit_login(Credential("student", "secret"), logger)
    assert result.submitted
    assert page.locators['input[name="DDDDD"][type="text"]'].filled == "student"
    assert page.locators['input[name="upass"][type="password"]'].filled == "secret"
    assert page.locators['input[name="0MKKey"][type="submit"]'].clicked


def test_submit_login_reports_explicit_failure_without_retry(monkeypatch) -> None:
    page = FakePage(body_text="用户名或密码错误")
    logger = SimpleNamespace(info=lambda *args: None, debug=lambda *args: None)
    ticks = iter([0.0, 46.0])
    monkeypatch.setattr(portal, "edge_available", lambda: True)
    monkeypatch.setattr(portal, "portal_state", lambda page: "login")
    monkeypatch.setattr(portal, "sync_playwright", lambda: FakePlaywrightManager(page))
    monkeypatch.setattr(portal, "internet_available", lambda timeout=3: False)
    monkeypatch.setattr(portal.time, "monotonic", lambda: next(ticks))
    result = portal.submit_login(Credential("student", "secret"), logger)
    assert result.submitted
    assert result.explicit_failure


def test_inspect_portal_state_handles_success_and_missing_edge(monkeypatch) -> None:
    monkeypatch.setattr(portal, "edge_available", lambda: False)
    assert portal.inspect_portal_state() == "edge-missing"

    page = FakePage()
    monkeypatch.setattr(portal, "edge_available", lambda: True)
    monkeypatch.setattr(portal, "portal_state", lambda page: "authenticated")
    monkeypatch.setattr(portal, "sync_playwright", lambda: FakePlaywrightManager(page))
    assert portal.inspect_portal_state() == "authenticated"


def test_authenticated_result_page_succeeds_even_when_external_probes_fail(monkeypatch):
    page = FakePage()
    states = iter(["login", "authenticated"])
    monkeypatch.setattr(portal, "edge_available", lambda: True)
    monkeypatch.setattr(portal, "portal_state", lambda page, **kwargs: next(states))
    monkeypatch.setattr(portal, "sync_playwright", lambda: FakePlaywrightManager(page))
    monkeypatch.setattr(portal, "internet_available", lambda timeout=3: False)
    logger = SimpleNamespace(info=lambda *args: None, debug=lambda *args: None)
    result = portal.submit_login(Credential("test", "test"), logger)
    assert result.submitted and result.gateway_authenticated
    assert not result.explicit_failure


def test_malformed_port_is_rejected_without_exception():
    assert not is_allowed_portal_url("http://10.9.10.100:invalid/")
