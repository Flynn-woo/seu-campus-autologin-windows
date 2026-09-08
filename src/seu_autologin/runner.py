"""自动认证流程编排。"""

import logging
import time

from .automatic import automatic_paused, pause_automatic, resume_automatic
from .connectivity import internet_available, portal_network_ready
from .credentials import load_credential
from .portal import submit_login
from .system import acquire_single_instance, open_manual_portal, release_single_instance


def run_autologin(
    logger: logging.Logger,
    *,
    initial_delay: int = 3,
    network_wait_seconds: int = 60,
    browser_fallback: bool = True,
    automatic: bool = False,
) -> int:
    """检查网络并在确有需要时读取凭据、执行认证。"""

    mutex = acquire_single_instance()
    if mutex is None:
        logger.info("已有一个开源版实例正在运行，本次退出。")
        return 0

    try:
        logger.info("开始%s检查。", "后台自动" if automatic else "手动")
        # 已联网时尽快退出，而且完全不读取 Credential Manager 中的密码。
        if internet_available(timeout=2):
            logger.info("外网已经可用，无需认证。")
            return 0

        if initial_delay > 0:
            logger.info("网络尚未就绪，%d 秒后复查。", initial_delay)
            time.sleep(initial_delay)
            if internet_available(timeout=2):
                logger.info("外网已经可用，无需认证。")
                return 0

        deadline = time.monotonic() + max(network_wait_seconds, 0)
        waiting_logged = False
        while not portal_network_ready(timeout=2):
            if time.monotonic() >= deadline:
                logger.error("固定认证网关在 %d 秒内未就绪。", network_wait_seconds)
                if browser_fallback:
                    open_manual_portal()
                return 4
            if not waiting_logged:
                logger.info("每 2 秒检查一次固定认证网关，最长等待 %d 秒。", network_wait_seconds)
                waiting_logged = True
            time.sleep(2)
            if internet_available(timeout=2):
                logger.info("外网已经可用，无需认证。")
                return 0

        if automatic and automatic_paused():
            logger.warning("后台认证已暂停，请重新配置凭据或运行手动测试。")
            return 6

        # 只有确认离线且固定门户可达后才读取密码。
        credential = load_credential()
        if credential is None:
            logger.error("公开版尚未配置凭据，请先运行 configure。")
            return 3

        attempt = 0
        while True:
            attempt += 1
            result = submit_login(credential, logger)
            logger.info(result.message)

            if internet_available(timeout=3):
                resume_automatic()
                logger.info("外网连通性复核通过。")
                return 0
            if result.gateway_authenticated:
                logger.warning("网关已确认会话认证，不再重复提交。")
                return 0
            if result.explicit_failure:
                pause_automatic()
                break
            # 网络就绪期限不限制认证次数，慢启动和零等待测试也允许第二次尝试。
            if attempt >= 2:
                break
            logger.info("等待 15 秒后进行最后一次技术性重试。")
            time.sleep(15)
            if internet_available(timeout=3):
                logger.info("重试前外网已恢复，停止提交。")
                return 0

        logger.error("自动认证未完成。")
        if browser_fallback:
            if open_manual_portal():
                logger.info("已打开固定门户供手动处理。")
            else:
                logger.warning("无法打开固定门户。")
        return 4
    finally:
        release_single_instance(mutex)


def watch_network(logger: logging.Logger, *, interval: int = 120) -> int:
    """任务计划不可用时，通过启动项持续检查重连和唤醒后的网络。"""

    mutex = acquire_single_instance("-watch")
    if mutex is None:
        return 0
    logger.info("启动项后台监测已启动，每 %d 秒检查一次。", max(interval, 30))
    try:
        while True:
            try:
                run_autologin(
                    logger, initial_delay=0, network_wait_seconds=0,
                    browser_fallback=False, automatic=True,
                )
            except Exception as exc:
                # 只记录异常类型，避免凭据或门户响应进入日志；临时错误不终止监测。
                logger.error("后台检查异常：%s，下轮继续。", type(exc).__name__)
            time.sleep(max(interval, 30))
    except KeyboardInterrupt:
        return 0
    finally:
        release_single_instance(mutex)
