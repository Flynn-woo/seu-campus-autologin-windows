"""跨触发器保存自动认证的暂停状态，不保存任何凭据。"""

from .paths import app_data_dir


def automatic_paused() -> bool:
    """服务器明确拒绝后，暂停后续后台提交，等待用户修正凭据。"""

    return (app_data_dir() / "automatic-paused.txt").exists()


def pause_automatic() -> None:
    destination = app_data_dir()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "automatic-paused.txt").write_text(
        "认证被明确拒绝；请重新配置凭据或手动测试。\n", encoding="utf-8"
    )


def resume_automatic() -> None:
    (app_data_dir() / "automatic-paused.txt").unlink(missing_ok=True)
