param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VersionFile = Join-Path $ProjectRoot "src\seu_autologin\__init__.py"
$VersionText = Get-Content -LiteralPath $VersionFile -Raw -Encoding UTF8
if ($VersionText -notmatch '__version__\s*=\s*"([^"]+)"') {
    throw "无法从 $VersionFile 读取版本号。"
}
$Version = $Matches[1]
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
$ReleaseDir = Join-Path $ProjectRoot "release"
$PackageName = "SEUCampusAutoLoginOSS-$Version-windows-x64"
$PackageDir = Join-Path $ReleaseDir $PackageName

# 保留历史版本，只清理本次构建与当前版本的解压目录。
foreach ($Target in @($BuildDir, $DistDir, $PackageDir)) {
    $FullTarget = [IO.Path]::GetFullPath($Target)
    $FullRoot = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\') + '\'
    if (-not $FullTarget.StartsWith($FullRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝清理项目目录之外的路径：$FullTarget"
    }
    if (Test-Path -LiteralPath $FullTarget) {
        Remove-Item -LiteralPath $FullTarget -Recurse -Force
    }
}

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $DistDir `
    --workpath $BuildDir `
    (Join-Path $ProjectRoot "packaging\windows.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败。"
}

New-Item -ItemType Directory -Path (Join-Path $PackageDir "app") -Force | Out-Null
Copy-Item -Path (Join-Path $DistDir "SEUCampusAutoLoginOSS\*") -Destination (Join-Path $PackageDir "app") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "installer") -Destination (Join-Path $PackageDir "installer") -Recurse -Force
foreach ($Name in @(
    "安装.cmd",
    "测试.cmd",
    "卸载.cmd",
    "README.md",
    "LICENSE"
)) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Name) -Destination (Join-Path $PackageDir $Name) -Force
}
Copy-Item -LiteralPath (Join-Path $ProjectRoot ".github\SECURITY.md") -Destination (Join-Path $PackageDir "SECURITY.md") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs\PRIVACY.md") -Destination (Join-Path $PackageDir "PRIVACY.md") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs\THIRD_PARTY_NOTICES.md") -Destination (Join-Path $PackageDir "THIRD_PARTY_NOTICES.md") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs") -Destination (Join-Path $PackageDir "docs") -Recurse -Force

$ZipPath = Join-Path $ReleaseDir "$PackageName.zip"
Compress-Archive -LiteralPath $PackageDir -DestinationPath $ZipPath -CompressionLevel Optimal -Force
$Hash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$ZipPath.sha256" -Value "$Hash  $PackageName.zip" -Encoding ascii

Write-Host "构建完成：$ZipPath" -ForegroundColor Green
Write-Host "SHA256：$Hash"
