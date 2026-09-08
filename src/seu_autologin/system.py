"""Windows 单实例、浏览器发现与安全打开网页。"""

import ctypes
import os
import subprocess
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlsplit

from .constants import EDGE_PATHS, MUTEX_NAME, PORTAL_HOST, PORTAL_URL


def edge_path() -> Path | None:
    """返回本机 Edge 可执行文件路径。"""

    return next((path for path in EDGE_PATHS if path.exists()), None)


def edge_available() -> bool:
    """检查本机 Edge 是否存在。"""

    return edge_path() is not None


def _kernel32():
    """声明 HANDLE 宽度，避免 64 位 Windows 上默认的 int 截断。"""

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def acquire_single_instance(suffix: str = "") -> object | None:
    """使用公开版专属命名互斥量，避免重复运行。"""

    if os.name != "nt":
        return object()
    kernel32 = _kernel32()
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME + suffix)
    if not handle:
        return None
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return None
    return handle


def release_single_instance(handle: object | None) -> None:
    """释放命名互斥量。"""

    if handle and os.name == "nt":
        # CreateMutexW 未请求所有权；关闭句柄即可释放命名实例。
        _kernel32().CloseHandle(handle)


def open_manual_portal() -> bool:
    """只允许用普通 Edge 打开固定门户。"""

    if urlsplit(PORTAL_URL).hostname != PORTAL_HOST:
        return False
    executable = edge_path()
    try:
        if executable:
            subprocess.Popen(
                [str(executable), PORTAL_URL],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.startfile(PORTAL_URL)  # type: ignore[attr-defined]
    except OSError:
        return False
    return True
