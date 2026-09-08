"""不提交凭据的环境检查。"""

import logging

from .connectivity import internet_available
from .credentials import credential_exists_without_secret
from .diagnostics import collect_autostart_status
from .portal import inspect_portal_state
from .system import edge_available


def check_environment(logger: logging.Logger, *, inspect_portal: bool = True) -> int:
    """输出最小环境状态；不会读取密码或填写表单。"""

    credential_ok = credential_exists_without_secret()
    online = internet_available(timeout=3)
    edge_ok = edge_available()
    print(f"公开版 Windows 凭据：{'已配置' if credential_ok else '未配置'}")
    print(f"Microsoft Edge：{'可用' if edge_ok else '未找到'}")
    print(f"外网连通性：{'正常' if online else '尚未认证或不可用'}")
    autostart = collect_autostart_status()
    modes = {
        "scheduled-events-periodic": "登录、重连、唤醒触发，并每两分钟补查",
        "scheduled-periodic": "登录触发，并每两分钟补查",
        "startup-watch": "启动项持续监测，每两分钟检查",
        "unknown": "未安装或仍为旧版，请运行新版安装.cmd",
    }
    print(f"自动启动模式：{modes[autostart['mode']]}")
    if autostart.get("task_details_available"):
        print(f"任务已启用：{'是' if autostart['task_enabled'] else '否，请重新安装'}")
        print(f"实际触发器：{', '.join(autostart['triggers'])}")
        print(f"上次运行：{autostart['last_run_time']}；结果码：{autostart['last_task_result']}")
        if not autostart["action_files_present"]:
            print("任务指向的程序已丢失，请重新安装。")
    elif autostart["mode"].startswith("scheduled"):
        print("无法读取任务状态，任务可能已删除或受系统策略限制，请重新安装。")
    if autostart["automatic_paused"]:
        print("后台认证已暂停：请先修正凭据，再运行手动测试。")

    portal_ok = True
    state = "skipped"
    if inspect_portal:
        state = inspect_portal_state()
        state_text = {
            "login": "登录表单可识别",
            "authenticated": "网关显示当前会话已认证",
            "blocked": "页面离开固定主机，已阻止",
            "unknown": "页面结构无法识别",
            "unreachable": "当前无法访问",
            "edge-missing": "缺少 Edge",
        }.get(state, state)
        portal_ok = state in {"login", "authenticated"}
        print(f"固定认证网关：{state_text}")

    logger.info(
        "环境检查：credential=%s edge=%s online=%s portal_state=%s",
        credential_ok,
        edge_ok,
        online,
        state,
    )
    return 0 if edge_ok and (online or portal_ok) else 5
