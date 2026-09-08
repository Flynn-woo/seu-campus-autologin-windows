"""只生成不包含账号、密码和网络标识的诊断信息。"""

import json
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

from . import __version__
from .automatic import automatic_paused
from .connectivity import internet_available, portal_network_ready
from .constants import PORTAL_HOST, TASK_NAME
from .credentials import credential_exists_without_secret
from .paths import app_data_dir, diagnostics_dir
from .system import edge_available


def scheduled_task_exists() -> bool:
    """检查公开版专属任务计划是否存在。"""

    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    schtasks = Path(system_root) / "System32" / "schtasks.exe"
    try:
        result = subprocess.run(
            [str(schtasks), "/Query", "/TN", TASK_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return False
    return result.returncode == 0


def collect_diagnostics() -> dict[str, object]:
    """收集可安全共享的最小诊断字段。"""

    return {
        "app_version": __version__,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "os": platform.system(),
        "os_release": platform.release(),
        "python": platform.python_version(),
        "edge_available": edge_available(),
        "credential_target_present": credential_exists_without_secret(),
        "internet_available": internet_available(timeout=2),
        "fixed_portal_host": PORTAL_HOST,
        "fixed_portal_reachable": portal_network_ready(timeout=2),
        "scheduled_task_present": scheduled_task_exists(),
        "autostart": collect_autostart_status(),
        "telemetry_enabled": False,
        "transport_warning": "portal_uses_http_without_tls",
    }


def collect_autostart_status() -> dict[str, object]:
    """读取任务实际状态，仅输出类别、时间和布尔值，不导出任务 XML 或用户路径。"""

    mode_file = app_data_dir() / "install_mode.txt"
    mode = mode_file.read_text(encoding="utf-8-sig").strip() if mode_file.exists() else "unknown"
    if mode not in {"scheduled-events-periodic", "scheduled-periodic", "startup-watch"}:
        mode = "unknown"
    status: dict[str, object] = {"mode": mode, "automatic_paused": automatic_paused()}
    try:
        from win32com.client import Dispatch
        from win32com.shell import shell, shellcon

        startup = Path(shell.SHGetFolderPath(0, shellcon.CSIDL_STARTUP, 0, 0))
        status["startup_link_present"] = (startup / "SEU Campus Auto Login OSS.lnk").is_file()
        service = Dispatch("Schedule.Service")
        service.Connect()
        task = service.GetFolder("\\").GetTask(TASK_NAME)
        definition = task.Definition
        kinds = []
        for trigger in definition.Triggers:
            if trigger.Type == 9:
                kinds.append("logon")
            elif trigger.Type == 0:
                subscription = trigger.Subscription
                if "NetworkProfile" in subscription:
                    kinds.append("network")
                elif "Power-Troubleshooter" in subscription:
                    kinds.append("resume")
            if trigger.Repetition.Interval:
                kinds.append("periodic")
        status.update({
            "task_enabled": bool(task.Enabled),
            "task_state": int(task.State),
            "last_task_result": int(task.LastTaskResult),
            "last_run_time": task.LastRunTime.isoformat(),
            "triggers": kinds,
            "action_files_present": all(
                Path(os.path.expandvars(action.Path)).is_file() for action in definition.Actions
            ),
        })
    except Exception:
        status["task_details_available"] = False
    else:
        status["task_details_available"] = True
    return status


def write_diagnostics() -> Path:
    """写入 UTF-8 JSON，并返回文件路径。"""

    destination = diagnostics_dir()
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = destination / f"diagnostics-{stamp}.json"
    output.write_text(
        json.dumps(collect_diagnostics(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output
