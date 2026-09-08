"""公开版命令行入口。"""

import argparse
import os
import sys
from contextlib import suppress

from . import __version__
from .checks import check_environment
from .credentials import configure_credential, credential_exists_without_secret, delete_credential
from .diagnostics import write_diagnostics
from .logging_config import build_logger
from .runner import run_autologin, watch_network


def build_parser() -> argparse.ArgumentParser:
    """创建带子命令的参数解析器。"""

    parser = argparse.ArgumentParser(description="东南大学校园网自动登录开源版")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--verbose", action="store_true", help="记录调试级别信息")
    parser.add_argument("--pause", action="store_true", help="完成后按回车关闭窗口")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("configure", help="保存或修改公开版凭据")
    commands.add_parser("credential-status", help="仅检查是否已配置公开版凭据")
    commands.add_parser("forget-credential", help="删除公开版保存的凭据")

    check = commands.add_parser("check", help="检查环境，不读取密码或提交表单")
    check.add_argument("--skip-portal", action="store_true", help="跳过浏览器门户检查")

    run = commands.add_parser("run-once", help="执行一次自动认证")
    run.add_argument("--initial-delay", type=int, default=3, help="首次离线检查后的等待秒数")
    run.add_argument(
        "--network-wait-seconds",
        type=int,
        default=60,
        help="等待固定门户就绪的最长秒数",
    )
    run.add_argument(
        "--no-browser-fallback",
        action="store_true",
        help="失败时不打开手动登录页",
    )
    run.add_argument("--automatic", action="store_true", help="后台触发，遵守认证暂停状态")
    watch = commands.add_parser("watch", help="任务计划不可用时持续监测网络")
    watch.add_argument("--interval", type=int, default=120, help="检查间隔秒数，最短 30 秒")

    commands.add_parser("diagnose", help="生成不含账号和密码的诊断报告")
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行命令并返回进程退出码。"""

    # 无窗口程序没有标准流，Python 3.10 的 argparse 仍会向其写入。
    # 使用空设备接收输出，防止后台版本检查或参数错误弹出异常对话框。
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if stream is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115
        elif hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = build_logger(verbose=args.verbose)
    try:
        return _execute(args, logger)
    finally:
        if args.pause:
            with suppress(EOFError, KeyboardInterrupt):
                input("\n按回车键关闭窗口……")


def _execute(args, logger) -> int:
    if args.command == "credential-status":
        return 0 if credential_exists_without_secret() else 3

    if args.command == "configure":
        return configure_credential()
    if args.command == "forget-credential":
        removed = delete_credential()
        print("已删除公开版凭据。" if removed else "没有找到公开版凭据。")
        return 0
    if args.command == "check":
        return check_environment(logger, inspect_portal=not args.skip_portal)
    if args.command == "diagnose":
        output = write_diagnostics()
        print(f"已生成脱敏诊断报告：{output}")
        return 0
    if args.command == "run-once":
        return run_autologin(
            logger,
            initial_delay=max(args.initial_delay, 0),
            network_wait_seconds=max(args.network_wait_seconds, 0),
            browser_fallback=not args.no_browser_fallback,
            automatic=args.automatic,
        )
    if args.command == "watch":
        return watch_network(logger, interval=max(args.interval, 30))
    return 2
