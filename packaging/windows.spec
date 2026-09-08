# 同一份依赖生成交互式和无窗口入口，避免定期后台检查弹出控制台。
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project = Path(SPECPATH).parent
datas, binaries, hiddenimports = collect_all("playwright")
analysis = Analysis(
    [str(project / "packaging" / "entrypoint.py")],
    pathex=[str(project / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["win32timezone"],
    # requests 使用 charset_normalizer；不打包共享开发环境中的可选 chardet。
    excludes=["chardet"],
)
pyz = PYZ(analysis.pure)
console = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True,
    name="SEUCampusAutoLoginOSS", console=True,
)
background = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True,
    name="SEUCampusAutoLoginOSSBackground", console=False,
)
package = COLLECT(
    console, background, analysis.binaries, analysis.datas,
    name="SEUCampusAutoLoginOSS",
)
