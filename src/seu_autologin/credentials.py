"""Windows Credential Manager 凭据读写。"""

import getpass
import os
import subprocess
from pathlib import Path

from .automatic import resume_automatic
from .constants import CREDENTIAL_TARGET
from .models import Credential


def normalize_username(username: str) -> str:
    """校园用户页面会追加 ``@xyw``，本地只保存基础账号。"""

    value = username.strip()
    if value.lower().endswith("@xyw"):
        value = value[:-4]
    return value


def _win32_modules():
    """延迟导入 Windows 专用模块，便于测试纯逻辑。"""

    import pywintypes  # type: ignore[import-not-found]
    import win32cred  # type: ignore[import-not-found]

    return pywintypes, win32cred


def save_credential(username: str, password: str) -> None:
    """把凭据写入当前 Windows 用户的 Credential Manager。"""

    username = normalize_username(username)
    if not username:
        raise ValueError("账号不能为空。")
    if not password:
        raise ValueError("密码不能为空。")

    _, win32cred = _win32_modules()
    win32cred.CredWrite(
        {
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": CREDENTIAL_TARGET,
            "UserName": username,
            "CredentialBlob": password,
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
            "Comment": "东南大学校园网自动登录开源版",
        },
        0,
    )
    resume_automatic()


def load_credential() -> Credential | None:
    """仅在确认需要登录以后读取凭据。"""

    pywintypes, win32cred = _win32_modules()
    try:
        item = win32cred.CredRead(CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
    except pywintypes.error as exc:
        error_code = getattr(exc, "winerror", None) or exc.args[0]
        if error_code == 1168:
            return None
        raise

    blob = item.get("CredentialBlob", "")
    if isinstance(blob, bytes):
        try:
            password = blob.decode("utf-16-le")
        except UnicodeDecodeError:
            password = blob.decode("utf-8")
    else:
        password = str(blob)
    return Credential(normalize_username(item.get("UserName", "")), password)


def credential_exists_without_secret() -> bool:
    """通过 ``cmdkey /list`` 检查目标名称，不读取密码内容。"""

    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    cmdkey = Path(system_root) / "System32" / "cmdkey.exe"
    try:
        result = subprocess.run(
            [str(cmdkey), "/list"],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return False
    return CREDENTIAL_TARGET.casefold() in result.stdout.casefold()


def delete_credential() -> bool:
    """删除公开版保存的凭据，不触碰私人版本的凭据目标。"""

    pywintypes, win32cred = _win32_modules()
    try:
        win32cred.CredDelete(CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
        return True
    except pywintypes.error as exc:
        error_code = getattr(exc, "winerror", None) or exc.args[0]
        if error_code == 1168:
            return False
        raise


def configure_credential() -> int:
    """在本机控制台采集凭据，避免密码进入命令行和聊天记录。"""

    print("\n东南大学校园网自动登录开源版配置")
    print("凭据只会保存在当前 Windows 用户的 Credential Manager 中。")
    print("注意：当前认证门户使用 HTTP，传输过程不具备 TLS 保护。")
    username = input("统一身份认证账号（无需填写 @xyw）：").strip()
    password = getpass.getpass("统一身份认证密码（输入时不会显示）：")
    confirmation = getpass.getpass("再次输入密码：")
    if password != confirmation:
        print("两次输入的密码不一致，未保存。")
        return 2
    try:
        save_credential(username, password)
    except ValueError as exc:
        print(str(exc))
        return 2
    print("凭据已保存。")
    return 0
