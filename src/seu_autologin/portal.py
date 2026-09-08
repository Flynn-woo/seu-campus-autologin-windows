"""固定校园网门户的浏览器自动化与请求允许列表。"""

import logging
import time
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from .connectivity import internet_available
from .constants import PORTAL_HOST, PORTAL_URL
from .models import Credential, LoginResult
from .system import edge_available


def is_allowed_portal_url(url: str) -> bool:
    """只有固定主机、标准 HTTP 端口和根路径属于可信门户。"""

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "http" or parts.hostname != PORTAL_HOST:
        return False
    if port not in (None, 80):
        return False
    return parts.username is None and parts.password is None


def safe_portal_display(url: str) -> str:
    """只返回协议和主机，确保查询参数不会进入日志。"""

    if not is_allowed_portal_url(url):
        return "<blocked>"
    return urlunsplit(("http", PORTAL_HOST, "/", "", ""))


def portal_state(page, timeout_ms: int = 30_000) -> str:
    """识别登录、已认证或未知状态。"""

    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if not is_allowed_portal_url(page.url):
            return "blocked"
        title = page.title()
        logout = page.locator('input[name="logout"]')
        if "注销页" in title or (logout.count() and logout.is_visible()):
            return "authenticated"
        username = page.locator('input[name="DDDDD"][type="text"]')
        password = page.locator('input[name="upass"][type="password"]')
        submit = page.locator('input[name="0MKKey"][type="submit"]')
        if all(
            locator.count() and locator.is_visible()
            for locator in (username, password, submit)
        ):
            return "login"
        page.wait_for_timeout(400)
    return "unknown"


def _route_with_allowlist(route) -> None:
    """阻止浏览器访问固定门户之外的网络地址。"""

    url = route.request.url
    scheme = urlsplit(url).scheme
    if scheme in {"about", "data", "blob"} or is_allowed_portal_url(url):
        if route.request.resource_type in {"image", "media", "font", "stylesheet"}:
            route.abort()
        else:
            route.continue_()
        return
    route.abort()


def _body_indicates_failure(body_text: str) -> bool:
    """判断页面是否明确拒绝认证。"""

    failure_words = (
        "账号及密码是否正确",
        "用户名或密码错误",
        "密码错误",
        "认证失败",
        "check the network configuration",
    )
    return any(word.casefold() in body_text.casefold() for word in failure_words)


def submit_login(credential: Credential, logger: logging.Logger) -> LoginResult:
    """向固定门户提交一次认证，禁止跨主机请求。"""

    if not edge_available():
        return LoginResult(False, False, "未找到 Microsoft Edge。")
    if not is_allowed_portal_url(PORTAL_URL):
        return LoginResult(False, True, "内置认证地址未通过安全校验。")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(ignore_https_errors=False)
            context.route("**/*", _route_with_allowlist)
            page = context.new_page()
            try:
                page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30_000)
                if not is_allowed_portal_url(page.url):
                    return LoginResult(False, True, "认证页重定向到未知地址，已阻止。")

                state = portal_state(page)
                if state == "authenticated":
                    return LoginResult(
                        False,
                        False,
                        "认证网关显示当前会话已经认证。",
                        gateway_authenticated=True,
                    )
                if state == "blocked":
                    return LoginResult(False, True, "认证页离开固定主机，已阻止。")
                if state != "login":
                    return LoginResult(False, False, "未识别到预期登录表单，未提交凭据。")

                captcha = page.locator('input[name="captcha"]')
                if captcha.count() and captcha.is_visible():
                    return LoginResult(False, True, "认证页要求验证码，需要手动登录。")

                page.locator('input[name="DDDDD"][type="text"]').fill(credential.username)
                page.locator('input[name="upass"][type="password"]').fill(credential.password)
                page.locator('input[name="0MKKey"][type="submit"]').click()
                logger.info("已向固定认证网关 %s 提交登录请求。", PORTAL_HOST)

                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    state = portal_state(page, timeout_ms=500)
                    if state == "authenticated":
                        return LoginResult(
                            True, False, "认证网关已确认登录成功。", gateway_authenticated=True,
                        )
                    if state == "blocked":
                        return LoginResult(True, True, "认证结果页离开固定主机，已阻止。")
                    if internet_available(timeout=3):
                        return LoginResult(True, False, "校园网认证成功。")
                    if _body_indicates_failure(page.locator("body").inner_text(timeout=5_000)):
                        return LoginResult(
                            True, True, "认证服务器拒绝登录，请核对账号、密码或套餐状态。",
                        )
                    page.wait_for_timeout(2_500)

                body_text = page.locator("body").inner_text(timeout=5_000)
                if _body_indicates_failure(body_text):
                    return LoginResult(
                        True,
                        True,
                        "认证服务器拒绝登录，请核对账号、密码或套餐状态。",
                    )
                return LoginResult(
                    True,
                    False,
                    "提交后仍未检测到外网，认证服务器可能暂时无响应。",
                )
            finally:
                context.close()
                browser.close()
    except (PlaywrightError, OSError) as exc:
        logger.debug("浏览器自动化异常类别：%s", type(exc).__name__)
        return LoginResult(False, False, f"浏览器自动化失败：{type(exc).__name__}")


def inspect_portal_state() -> str:
    """只检查门户页面，不读取或填写凭据。"""

    if not edge_available():
        return "edge-missing"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(ignore_https_errors=False)
            context.route("**/*", _route_with_allowlist)
            page = context.new_page()
            try:
                page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30_000)
                return portal_state(page)
            finally:
                context.close()
                browser.close()
    except (PlaywrightError, OSError):
        return "unreachable"
